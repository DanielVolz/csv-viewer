from fastapi import APIRouter, HTTPException, Request
import os
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from datetime import datetime
import logging
import subprocess

from models.file import FileModel
from config import settings, get_settings
from utils.csv_utils import read_csv_file, read_csv_file_normalized, read_csv_file_preview, DEFAULT_DISPLAY_ORDER, count_unique_data_rows
from tasks.tasks import index_all_csv_files, app
from utils.index_state import load_state, save_state
from celery import current_app
from config import settings
from utils.path_utils import (
    collect_netspeed_files,
    resolve_current_file,
    NETSPEED_TIMESTAMP_PATTERN,
    get_data_root,
)

from utils.opensearch import OpenSearchUnavailableError, opensearch_config
from utils.preview_cache import preview_cache

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/files",
    tags=["files"]
)


def _extra_search_paths() -> List[Path | str]:
    extras: List[Path | str] = []
    for attr in ("NETSPEED_CURRENT_DIR", "NETSPEED_HISTORY_DIR", "CSV_FILES_DIR"):
        value = getattr(settings, attr, None)
        if value:
            try:
                extras.append(Path(value))
            except Exception:
                continue
    try:
        extras.append(get_data_root())
    except Exception:
        pass
    return extras


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except Exception:
        return 0.0


def _sorted_existing(paths: Iterable[Path]) -> List[Path]:
    existing = []
    for path in paths:
        if path.exists():
            existing.append(path)
    return sorted(existing, key=_safe_mtime, reverse=True)


def _collect_inventory(extras: Optional[List[Path | str]] = None) -> Tuple[dict[str, Path], List[Path], Optional[Path], List[Path]]:
    extras = extras or _extra_search_paths()
    historical, current, backups = collect_netspeed_files(extras)
    inventory: dict[str, Path] = {}

    for path in historical:
        if path.exists():
            inventory[path.name] = path

    if current and current.exists():
        inventory[current.name] = current
        inventory.setdefault("netspeed.csv", current)

    for path in backups:
        if path.exists():
            inventory[path.name] = path

    return inventory, historical, current, backups


def _latest_opensearch_snapshot() -> Optional[dict]:
    try:
        return opensearch_config.get_latest_netspeed_snapshot()
    except Exception as exc:
        logger.debug(f"OpenSearch snapshot lookup failed: {exc}")
        return None


def _format_snapshot_date(snapshot: dict) -> Optional[str]:
    if not snapshot:
        return None
    value = snapshot.get("creation_date")
    if isinstance(value, str) and value:
        return value
    ms = snapshot.get("creation_date_ms")
    if isinstance(ms, (int, float)) and ms > 0:
        try:
            return datetime.utcfromtimestamp(ms / 1000).strftime('%Y-%m-%d')
        except Exception:
            return None
    return None


def _opensearch_preview(limit: int = 25) -> Optional[dict]:
    snapshot = _latest_opensearch_snapshot()
    if not snapshot or not snapshot.get("index"):
        return None

    headers, rows = opensearch_config.preview_index_rows(snapshot["index"], limit=limit)
    if not rows:
        return None

    creation_date = _format_snapshot_date(snapshot)
    file_name = snapshot.get("file_name") or snapshot.get("index")
    return {
        "success": True,
        "message": "Displaying latest data available in OpenSearch.",
        "headers": headers,
        "data": rows,
        "creation_date": creation_date,
        "file_name": file_name,
        "using_fallback": True,
        "fallback_file": file_name,
        "source": "opensearch",
    }

@router.get("/health")
async def files_health():
    """Diagnostic endpoint: reports environment paths, resolved container paths,
    existence, size, and basic permission bits for current & history netspeed files.
    """
    try:
        from config import settings as _settings
        import os, stat
        cur_env = _settings.NETSPEED_CURRENT_DIR
        hist_env = _settings.NETSPEED_HISTORY_DIR
        mount_env = _settings.CSV_FILES_DIR
        # Inside container expected mapping
        container_mount = get_data_root()
        current_expected = container_mount / "netspeed" / "netspeed.csv"
        history_dir_expected = container_mount / "history" / "netspeed"
        history_files = []
        if history_dir_expected.exists():
            for p in sorted(history_dir_expected.glob("netspeed.csv.*")):
                try:
                    st = p.stat()
                    history_files.append({
                        "name": p.name,
                        "size": st.st_size,
                        "mtime": st.st_mtime
                    })
                except Exception:
                    pass
        def _file_info(p: Path):
            if not p.exists():
                return {"exists": False}
            try:
                st = p.stat()
                mode = stat.S_IMODE(st.st_mode)
                return {
                    "exists": True,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "perm_octal": oct(mode),
                    "readable": os.access(p, os.R_OK)
                }
            except Exception as e:
                return {"exists": True, "error": str(e)}
        return {
            "mountEnv": mount_env,
            "currentEnv": cur_env,
            "historyEnv": hist_env,
            "containerMount": str(container_mount),
            "currentFile": _file_info(current_expected),
            "historyCount": len(history_files),
            "historyFilesSample": history_files[:10]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/", response_model=List[dict])
async def list_files():
    """
    List all available netspeed CSV files.
    Returns them sorted with the newest export first, followed by historical files.
    Includes line counts and filesystem timestamps for each file.
    """
    try:
        extras: list[Path | str] = []
        for attr in ("NETSPEED_CURRENT_DIR", "NETSPEED_HISTORY_DIR", "CSV_FILES_DIR"):
            value = getattr(settings, attr, None)
            if value:
                extras.append(Path(value))

        historical_files, current_file, backup_files = collect_netspeed_files(extras)

        ordered_paths: List[Path] = []
        if current_file and current_file.exists():
            ordered_paths.append(current_file)

        def _mtime_or_zero(path: Path) -> float:
            try:
                return path.stat().st_mtime
            except Exception:
                return 0.0

        historical_sorted = sorted(
            (p for p in historical_files if p.exists()),
            key=_mtime_or_zero,
            reverse=True,
        )
        ordered_paths.extend(historical_sorted)

        ordered_paths.extend(p for p in backup_files if p.exists())

        files: list[dict] = []
        seen: set[str] = set()

        def add_file(path: Path) -> None:
            try:
                resolved = str(path.resolve())
            except Exception:
                resolved = str(path)
            if resolved in seen:
                return
            seen.add(resolved)
            if not path.exists():
                return
            try:
                file_model = FileModel.from_path(str(path))
            except Exception as model_err:
                logger.debug(f"Skipping file {path}: {model_err}")
                return

            line_count = count_unique_data_rows(path, opener=open)

            metadata = file_model.dict()
            try:
                from datetime import datetime as _dt, timezone as _tz
                mtime = path.stat().st_mtime
                metadata['date'] = _dt.fromtimestamp(mtime).strftime('%Y-%m-%d')
                metadata['mtime'] = mtime
                metadata['datetime'] = _dt.fromtimestamp(mtime, tz=_tz.utc).isoformat()
                metadata['time'] = _dt.fromtimestamp(mtime).strftime('%H:%M')
            except Exception:
                metadata['date'] = None
            metadata['line_count'] = line_count
            files.append(metadata)

        for candidate in ordered_paths:
            add_file(candidate)

        if not files:
            snapshot = _latest_opensearch_snapshot()
            if snapshot:
                creation_date = _format_snapshot_date(snapshot)
                file_name = snapshot.get("file_name") or snapshot.get("index") or "OpenSearch snapshot"
                creation_mtime = None
                creation_ms = snapshot.get("creation_date_ms")
                if isinstance(creation_ms, (int, float)) and creation_ms > 0:
                    creation_mtime = creation_ms / 1000.0
                files.append({
                    "name": file_name,
                    "path": f"opensearch://{snapshot.get('index')}",
                    "is_current": True,
                    "date": creation_date,
                    "datetime": creation_date,
                    "time": None,
                    "mtime": creation_mtime,
                    "line_count": snapshot.get("documents", 0) or 0,
                    "using_fallback": True,
                    "fallback_file": file_name,
                    "source": "opensearch",
                    "index": snapshot.get("index"),
                    "message": "Displaying latest data available in OpenSearch (filesystem export missing).",
                    "downloadable": False,
                })

        return files

    except Exception as e:
        logger.error(f"Error listing CSV files: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list CSV files"
        )


@router.get("/netspeed_info")
async def get_netspeed_info():
    """
    Get information about the current netspeed.csv file.
    If netspeed.csv doesn't exist, fall back to netspeed.csv.0 until the new file is generated.

    Returns:
        Dictionary with creation date, line count, and fallback information
    """
    try:
        extras: list[Path | str] = []
        for attr in ("NETSPEED_CURRENT_DIR", "NETSPEED_HISTORY_DIR", "CSV_FILES_DIR"):
            value = getattr(settings, attr, None)
            if value:
                extras.append(Path(value))

        current_file = resolve_current_file(extras)
        historical_files, _, _ = collect_netspeed_files(extras)

        using_fallback = False
        fallback_file: Optional[Path] = None

        def _mtime_or_zero(path: Path) -> float:
            try:
                return path.stat().st_mtime
            except Exception:
                return 0.0

        if current_file and current_file.exists():
            file_to_use = current_file
        else:
            candidates = sorted((p for p in historical_files if p.exists()), key=_mtime_or_zero, reverse=True)
            if not candidates:
                snapshot = _latest_opensearch_snapshot()
                if snapshot:
                    creation_date = _format_snapshot_date(snapshot)
                    fallback_name = snapshot.get("file_name") or snapshot.get("index")
                    return JSONResponse(
                        content={
                            "success": True,
                            "message": "Using OpenSearch snapshot data because no filesystem export is available.",
                            "date": creation_date,
                            "line_count": snapshot.get("documents", 0),
                            "using_fallback": True,
                            "fallback_file": fallback_name,
                            "source": "opensearch",
                            "index": snapshot.get("index"),
                        }
                    )
                data_root = get_data_root()
                return {
                    "success": False,
                    "message": f"No netspeed export found — place a file in {data_root} and refresh. The exporter should create a new file around 06:55 AM.",
                    "date": None,
                    "line_count": 0,
                    "using_fallback": False,
                    "fallback_file": None
                }
            fallback_file = candidates[0]
            file_to_use = fallback_file
            using_fallback = True

        file_model = FileModel.from_path(str(file_to_use))

        # Count lines first for current file; if it's empty and not using fallback, try to pick a historical file with data
        def _count_lines(fp: Path | str) -> int:
            return count_unique_data_rows(fp, opener=open)

        initial_count = _count_lines(file_to_use)
        if not using_fallback and initial_count <= 0:
            candidates = [p for p in historical_files if p.exists() and _count_lines(p) > 0]
            candidates.sort(key=_mtime_or_zero, reverse=True)
            if candidates:
                fallback_file = candidates[0]
                using_fallback = True
                file_to_use = fallback_file

        # Recompute date/time from filesystem so UI reflects the real file date
        from datetime import datetime as _dt
        modification_time = file_to_use.stat().st_mtime
        creation_date = _dt.fromtimestamp(modification_time).strftime('%Y-%m-%d')
        line_count = _count_lines(file_to_use)

        fb_name = fallback_file.name if (using_fallback and fallback_file is not None) else None
        actual_name = file_to_use.name if file_to_use else None
        result = {
            "success": True,
            "message": (
                f"Using data from {fb_name} until a new netspeed export is generated."
                if using_fallback else "Current netspeed export information retrieved successfully"
            ),
            "date": creation_date,
            "line_count": line_count,
            "last_modified": modification_time,
            "using_fallback": using_fallback,
            "fallback_file": fb_name,
            "actual_file_name": actual_name
        }
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error getting netspeed file info: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get netspeed file information"
        )


def _extract_location_from_hostname(hostname: str) -> str | None:
    """Extract a 5-char code (AAA01) from a switch hostname.

    Algorithm matches the implementation in stats: collect first 3 letters then next 2 digits.
    Returns the concatenated code or None if not found.
    """
    if not hostname:
        return None
    h = hostname.strip().upper()
    letters = []
    digits = []
    i = 0
    while i < len(h) and len(letters) < 3:
        ch = h[i]
        if 'A' <= ch <= 'Z':
            letters.append(ch)
        i += 1
    while i < len(h) and len(digits) < 2:
        ch = h[i]
        if '0' <= ch <= '9':
            digits.append(ch)
        i += 1
    if len(letters) == 3 and len(digits) == 2:
        return ''.join(letters) + ''.join(digits)
    return None


@router.get("/preview")
async def preview_current_file(limit: int = 25, filename: str = "netspeed.csv", loc: Optional[str] = None):
    """
    Get a preview of a CSV file (first N entries) along with its creation date.
    If netspeed.csv doesn't exist, fall back to netspeed.csv.0 until the new file is generated.

    Args:
        limit: Maximum number of entries to return (default 25)
        filename: Name of the file to preview (default "netspeed.csv")

        Returns:
        Dictionary with headers, preview rows, and file creation date
    """
    try:
        # Optimized: Only one inventory lookup, fast cache, minimal row processing
        extras = _extra_search_paths()
        inventory, historical_files, current_file, _ = _collect_inventory(extras)

        file_path: Optional[Path] = None
        using_fallback = False
        actual_filename = filename

        # Only cache preview for default (no loc filter, netspeed.csv, not fallback)
        cache_key = None
        cache_enabled = (filename == "netspeed.csv" and (not loc or loc.strip() == ""))
        mtime = None
        if cache_enabled:
            candidate = inventory.get("netspeed.csv")
            if candidate and candidate.exists():
                mtime = str(candidate.stat().st_mtime)
                cache_key = f"preview:{filename}:{limit}:{mtime}"
                cached = preview_cache.get(cache_key)
                if cached:
                    logger.info(f"Preview cache HIT for key: {cache_key}")
                    return cached
                else:
                    logger.info(f"Preview cache MISS for key: {cache_key}")

        # File selection logic
        if filename == "netspeed.csv":
            candidate = inventory.get("netspeed.csv")
            if candidate and candidate.exists():
                file_path = candidate
                actual_filename = candidate.name
            else:
                latest_hist = _sorted_existing(historical_files)
                if latest_hist:
                    file_path = latest_hist[0]
                    actual_filename = file_path.name
                    using_fallback = True
                else:
                    fallback_preview = _opensearch_preview(limit)
                    if fallback_preview:
                        return fallback_preview
                    return {
                        "success": False,
                        "message": "No netspeed export available. Upload a file and retry.",
                        "headers": [],
                        "data": [],
                        "creation_date": None,
                        "file_name": filename,
                        "using_fallback": False,
                        "fallback_file": None
                    }
        else:
            candidate = inventory.get(filename)
            if candidate and candidate.exists():
                file_path = candidate
                actual_filename = candidate.name
            else:
                direct = get_data_root() / filename
                # Fix: Ensure resolved path is within data root to block traversal
                try:
                    resolved_direct = direct.resolve()
                    data_root = get_data_root().resolve()
                except Exception:
                    return {
                        "success": False,
                        "message": "Error resolving file path",
                        "headers": [],
                        "data": [],
                        "creation_date": None,
                        "file_name": filename,
                        "using_fallback": False,
                        "fallback_file": None
                    }
                try:
                    # Python <3.9 compatibility for is_relative_to
                    resolved_direct.relative_to(data_root)
                except ValueError:
                    return {
                        "success": False,
                        "message": "Invalid file path (outside data directory)",
                        "headers": [],
                        "data": [],
                        "creation_date": None,
                        "file_name": filename,
                        "using_fallback": False,
                        "fallback_file": None
                    }
                if resolved_direct.exists():
                    file_path = resolved_direct
                    actual_filename = resolved_direct.name
                else:
                    fallback_preview = _opensearch_preview(limit)
                    if fallback_preview:
                        return fallback_preview
                    return {
                        "success": False,
                        "message": f"File {filename} not found",
                        "headers": [],
                        "data": [],
                        "creation_date": None,
                        "file_name": filename,
                        "using_fallback": False,
                        "fallback_file": None
                    }

        # If requested file exists but has no data (only header or 0 bytes), try historical netspeed export with data
        def _count_lines(fp: Path | str) -> int:
            return count_unique_data_rows(fp, opener=open)

        if filename == "netspeed.csv" and file_path.exists() and _count_lines(file_path) <= 0:
            viable_historical = [p for p in _sorted_existing(historical_files) if _count_lines(p) > 0]
            if viable_historical:
                file_path = viable_historical[0]
                actual_filename = file_path.name
                using_fallback = True

        # Get file creation date from filesystem mtime for consistency with file list
        file_model = FileModel.from_path(str(file_path))
        try:
            from datetime import datetime as _dt
            creation_date = _dt.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d')
        except Exception:
            creation_date = file_model.date.strftime('%Y-%m-%d') if file_model.date else None

        # Read only the first N rows from the CSV file (fast preview)
        csv_headers, rows, total_count = read_csv_file_preview(str(file_path), limit=limit)

        # Use central function as SINGLE SOURCE OF TRUTH for column order
        from utils.csv_utils import get_csv_column_order
        all_headers = get_csv_column_order()

        # Filter out hidden columns (KEM, KEM 2)
        hidden_fields = {"KEM", "KEM 2"}
        headers = [h for h in all_headers if h not in hidden_fields]

        # Add metadata to each row and filter out hidden fields
        enriched_rows = []
        for i, row in enumerate(rows, start=1):
            enriched_row = {
                "#": str(i),
                "File Name": actual_filename,
                "Creation Date": creation_date
            }
            for key, value in row.items():
                if key not in hidden_fields:
                    enriched_row[key] = value
            enriched_rows.append(enriched_row)
        rows = enriched_rows

        # Optional: filter by location code/prefix if provided
        loc_filter = (loc or "").strip().upper()
        if loc_filter:
            from re import match
            is_prefix = bool(match(r"^[A-Z]{3}$", loc_filter))
            is_code = bool(match(r"^[A-Z]{3}[0-9]{2}$", loc_filter))
            if not (is_prefix or is_code):
                return {
                    "success": False,
                    "message": "Invalid loc parameter. Use 3-letter prefix (AAA) or 5-char code (AAA01).",
                    "headers": headers,
                    "data": [],
                    "creation_date": None,
                    "file_name": filename,
                    "using_fallback": using_fallback,
                    "fallback_file": actual_filename if using_fallback else None
                }
            filtered = []
            for r in rows:
                sh = str((r.get("Switch Hostname") or "").strip())
                code = _extract_location_from_hostname(sh) or ""
                if is_code:
                    if code == loc_filter:
                        filtered.append(r)
                else:
                    if code.startswith(loc_filter):
                        filtered.append(r)
            rows = filtered

        # No need to slice rows again, already limited
        fallback_message = (
            f" (using data from {actual_filename} until the next export is available)" if using_fallback else ""
        )

        result = {
            "success": True,
            "message": (f"Showing first {len(rows)} entries of "
                        f"{total_count} total" + (f" (filtered by {loc_filter})" if loc_filter else "") + fallback_message),
            "headers": headers,
            "data": rows,
            "creation_date": creation_date,
            "file_format": file_model.format,
            "file_name": filename,
            "actual_file_name": actual_filename,
            "using_fallback": using_fallback,
            "fallback_file": actual_filename if using_fallback else None
        }
        # Set cache if enabled and not fallback/filtered
        if cache_enabled and not using_fallback and not loc_filter and cache_key:
            preview_cache.set(cache_key, result)
            logger.info(f"Preview cache SET for key: {cache_key}")
        return result
    except Exception as e:
        logger.error(f"Error getting file preview: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get file preview"
        )


@router.get("/reload_celery")
async def reload_celery():
    """Reload Celery configuration."""
    try:
        app.control.purge()
        return {"message": "Celery configuration reloaded"}
    except Exception as e:
        logger.error(f"Error reloading Celery configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to reload Celery configuration"
        )


@router.get("/reindex")
async def reindex_all_files():
    """
    Trigger reindexing of all CSV files while the app is running.

    Returns:
        Dictionary with the status of the reindexing task
    """
    try:
        # Get path to CSV files directory
        csv_dir = str(get_data_root())

        # Trigger the Celery task asynchronously
        task = index_all_csv_files.delay(csv_dir)

        # Best-effort: queue snapshot task (global + per-location) AFTER bulk reindex
        snapshot_queued = False
        try:
            from tasks.tasks import snapshot_current_with_details as _snap
            try:
                _snap.delay()  # default path resolves via settings/get_data_root
                snapshot_queued = True
                logger.info("Queued snapshot_current_with_details after reindex_all_files")
            except Exception as e:
                logger.debug(f"Could not queue snapshot_current_with_details (bulk): {e}")
            if not snapshot_queued:
                try:
                    logger.info("Running snapshot_current_with_details inline (fallback after reindex_all_files)")
                    _ = _snap()
                except Exception as e:
                    logger.warning(f"Inline snapshot_current_with_details failed after reindex_all_files: {e}")
        except Exception as e:
            logger.debug(f"snapshot_current_with_details import failed after reindex_all_files: {e}")

        return {
            "success": True,
            "message": "Reindexing task has been triggered (snapshot queued)" if snapshot_queued else "Reindexing task has been triggered (snapshot fallback attempted)",
            "task_id": task.id,
            "snapshot_queued": snapshot_queued
        }

    except Exception as e:
        logger.error(f"Error triggering reindexing task: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger reindexing task"
        )


@router.get("/reindex/current")
async def reindex_current_file():
    """
    Trigger reindexing of only the current netspeed.csv file for quick testing.

    Returns:
        Dictionary with the status of the reindexing task
    """
    try:
        # Invalidate stats caches so dev sees updates instantly
        try:
            from api.stats import invalidate_caches as _invalidate
            _invalidate("reindex/current requested")
        except Exception:
            pass

        extras = _extra_search_paths()
        csv_file_path = resolve_current_file(extras)
        if csv_file_path is None or not Path(csv_file_path).exists():
            _, historical_files, _, _ = _collect_inventory(extras)
            sorted_hist = _sorted_existing(historical_files)
            csv_file_path = sorted_hist[0] if sorted_hist else None
        if not csv_file_path or not Path(csv_file_path).exists():
            raise HTTPException(status_code=404, detail="No current netspeed export found")
        csv_file_path = Path(csv_file_path)
        csv_file = str(csv_file_path)

        # Check if file exists
        if not Path(csv_file).exists():
            raise HTTPException(
                status_code=404,
                detail="netspeed.csv file not found"
            )

        # Reuse shared OpenSearch config and index the single file
        should_wait = bool(getattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", True))
        if should_wait:
            try:
                opensearch_config.wait_for_availability(
                    timeout=getattr(settings, "OPENSEARCH_STARTUP_TIMEOUT_SECONDS", 45),
                    interval=getattr(settings, "OPENSEARCH_STARTUP_POLL_SECONDS", 3.0),
                    reason="reindex_current",
                )
            except OpenSearchUnavailableError as exc:
                logger.warning(f"OpenSearch unavailable for fast reindex: {exc}")
                raise HTTPException(status_code=503, detail="OpenSearch is not ready. Please try again shortly.") from exc
        else:
            if not opensearch_config.quick_ping():
                logger.warning("OpenSearch unavailable and wait disabled; skipping reindex_current")
                raise HTTPException(
                    status_code=503,
                    detail="OpenSearch is unavailable and waits are disabled; skipping reindex.",
                )

        # Delete the current index first
        index_name = opensearch_config.get_index_name(csv_file)
        try:
            opensearch_config.client.indices.delete(index=index_name)
            logger.info(f"Deleted existing index: {index_name}")
        except Exception as e:
            logger.info(f"Index {index_name} did not exist or could not be deleted: {e}")

        # Index the current file
        success, count = opensearch_config.index_csv_file(csv_file)

        if success:
            # Apply data repair after indexing (only for current file)
            try:
                logger.info("Starting post-indexing data repair for current file")
                repair_result = opensearch_config.repair_current_file_after_indexing(csv_file)
                if repair_result.get("success"):
                    logger.info(f"Data repair completed: {repair_result}")
                    repair_message = f" (with data repair: {repair_result.get('documents_repaired', 0)} docs)"
                else:
                    logger.warning(f"Data repair failed: {repair_result}")
                    repair_message = " (data repair failed)"
            except Exception as e:
                logger.error(f"Post-indexing data repair failed: {e}")
                repair_message = f" (data repair error: {e})"

            # Trigger a fresh snapshot WITH details (global & per-location) so Statistics has up-to-date details
            try:
                from tasks.tasks import snapshot_current_with_details as _snap
                queued = False
                try:
                    _snap.delay(csv_file)
                    queued = True
                    logger.info("Queued snapshot_current_with_details after fast reindex")
                except Exception as e:
                    logger.debug(f"Could not queue snapshot_current_with_details (will run inline): {e}")
                if not queued:
                    try:
                        logger.info("Running snapshot_current_with_details inline (dev fallback)")
                        _ = _snap(csv_file)
                    except Exception as e:
                        logger.warning(f"Inline snapshot_current_with_details failed: {e}")
                if os.environ.get("NODE_ENV") == "development":
                    try:
                        logger.info("Development mode: also executing snapshot_current_with_details inline for determinism")
                        _ = _snap(csv_file)
                    except Exception as e:
                        logger.warning(f"Dev inline snapshot_current_with_details failed: {e}")
            except Exception as e:
                logger.debug(f"Could not queue snapshot_current_with_details: {e}")

            return {
                "success": True,
                "message": f"Indexed current file {csv_file_path.name} with {count} documents" + repair_message,
                "file": csv_file_path.name,
                "documents_indexed": count
            }
        else:
            raise HTTPException(status_code=500, detail=f"Indexing failed for {csv_file_path.name}")

    except Exception as e:
        logger.error(f"Error reindexing current file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reindex current file: {e}"
        )


@router.get("/download/{filename}")
async def download_file(filename: str, request: Request):
    """Download a CSV file by name with safety checks & explicit headers.

    Args:
        filename: Name of the file to download (e.g., netspeed.csv, netspeed.csv.1)
    """
    try:
        raw_name = filename.strip()

        # Disallow path traversal
        if any(token in raw_name for token in ("..", "/", "\\")):
            logger.warning(f"Blocked traversal attempt: {raw_name}")
            raise HTTPException(status_code=400, detail="Invalid filename")

        allowed = False
        if raw_name == "netspeed.csv":
            allowed = True
        elif raw_name.startswith("netspeed.csv."):
            suffix = raw_name.split("netspeed.csv.", 1)[1]
            if suffix.endswith("_bak"):
                suffix = suffix[:-4]
            allowed = suffix.isdigit()
        elif raw_name.endswith("_bak") and raw_name.startswith("netspeed.csv"):
            allowed = True
        elif NETSPEED_TIMESTAMP_PATTERN.match(raw_name):
            allowed = True

        if not allowed:
            logger.warning(f"Blocked download attempt for disallowed filename: {raw_name}")
            raise HTTPException(status_code=400, detail="Invalid filename")

        extras = _extra_search_paths()
        inventory, _, _, _ = _collect_inventory(extras)

        file_path = None
        if raw_name == "netspeed.csv":
            file_path = inventory.get("netspeed.csv")
        if file_path is None:
            file_path = inventory.get(raw_name)

        if file_path is None or not file_path.exists():
            fallback_candidates = []
            data_root = get_data_root()
            fallback_candidates.append(data_root / "netspeed" / raw_name)
            fallback_candidates.append(data_root / "history" / "netspeed" / raw_name)
            fallback_candidates.append(data_root / raw_name)
            for candidate in fallback_candidates:
                if candidate.exists():
                    file_path = candidate
                    break

        if file_path is None or not file_path.exists():
            logger.error(f"File not found: {raw_name}")
            raise HTTPException(status_code=404, detail=f"File {raw_name} not found")

        import pathlib

        base_dir_value = getattr(settings, "CSV_FILES_DIR", None)
        if base_dir_value:
            try:
                csv_dir = pathlib.Path(base_dir_value).resolve()
            except Exception:
                csv_dir = pathlib.Path(base_dir_value)
        else:
            csv_dir = get_data_root().resolve()
        file_path = file_path.resolve()

        csv_dir_str = str(csv_dir)
        file_path_str = str(file_path)
        logger.debug("download_file security context csv_dir=%s file_path=%s", csv_dir_str, file_path_str)

        normalized_dir = csv_dir_str.rstrip("/") or "/"
        normalized_dir_with_sep = normalized_dir if normalized_dir.endswith("/") else normalized_dir + "/"
        if not (
            file_path_str == normalized_dir
            or file_path_str.startswith(normalized_dir_with_sep)
        ):
            logger.warning(f"Blocked escape attempt: {file_path}")
            raise HTTPException(status_code=400, detail="Invalid filename")

        size = file_path.stat().st_size
        logger.info(
            "Downloading file",
            extra={
                "client": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "file": str(file_path),
                "size": size
            }
        )

        headers = {
            "Content-Disposition": f"attachment; filename=\"{raw_name}\"",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-cache",
            "Content-Length": str(size)
        }

        return FileResponse(
            path=str(file_path),
            filename=raw_name,
            media_type="text/csv; charset=utf-8",
            headers=headers
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {e}")


@router.get("/columns")
async def get_available_columns():
    """
    Get the available columns from the current CSV format.

    Dynamically reads headers from the current netspeed.csv file to include
    all available columns (including new ones added to the CSV format).

    Returns columns in the SAME ORDER as search results to ensure consistent UX.

    Returns:
        List of column definitions with id, label, and default enabled state
    """
    try:
        # Find current CSV file
        extras = _extra_search_paths()
        inventory, historical_files, current_file, _ = _collect_inventory(extras)

        file_path: Optional[Path] = None
        if current_file and current_file.exists():
            file_path = current_file
        else:
            sorted_hist = _sorted_existing(historical_files)
            if sorted_hist:
                file_path = sorted_hist[0]

        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail="No CSV file available to read columns from")

        # Use central function as SINGLE SOURCE OF TRUTH for column order
        from utils.csv_utils import get_csv_column_order
        ordered_columns = get_csv_column_order()

        # Define core columns that are enabled by default
        core_enabled_columns = {
            "#", "File Name", "Creation Date", "IP Address", "Line Number",
            "MAC Address", "Voice VLAN", "Switch Hostname", "Switch Port",
            "Serial Number", "Model Name"
        }

        # Columns to NEVER expose in settings (internal use only)
        hidden_columns = {"KEM", "KEM 2"}

        # Custom display labels (shorter names for UI)
        display_labels = {
            "Creation Date": "Date",
            "IP Address": "IP Addr.",
            "Voice VLAN": "V-VLAN",
            "Serial Number": "Serial",
            "Model Name": "Model",
            "MAC Address 2": "MAC Addr. 2",
        }

        # Build column definitions from ordered columns
        available_columns = []
        for column_id in ordered_columns:
            # Skip hidden/internal columns
            if column_id in hidden_columns:
                continue

            # Determine if column should be enabled by default
            is_enabled = column_id in core_enabled_columns

            available_columns.append({
                "id": column_id,
                "label": display_labels.get(column_id, column_id),
                "enabled": is_enabled
            })

        return {
            "success": True,
            "columns": available_columns,
            "message": f"Retrieved {len(available_columns)} available columns from CSV"
        }

    except Exception as e:
        logger.error(f"Error getting available columns: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get available columns"
        )


# Removed: trigger_morning_reindex endpoint (scheduler deprecated; file watcher handles reindexing)




@router.get("/index/status")
async def get_index_status():
    """Return last indexing state (files, totals, timestamps) including any active progress.

    If an active indexing run is persisted with status 'running', frontend can resume progress display
    after a page reload without needing the original Celery task id client-side.
    """
    try:
        state = load_state()
        active = state.get("active") if isinstance(state, dict) else None

        # Auto-clear stale 'running' states left from previous containers/brokers
        try:
            if active and active.get("status") == "running":
                # If we can query Celery and it's not running, or if it's too old, mark as interrupted
                too_old = False
                try:
                    from datetime import datetime, timezone
                    started_at = active.get("started_at")
                    if started_at:
                        # Pydantic isoformat with timezone; fallback if naive
                        try:
                            dt = datetime.fromisoformat(started_at)
                        except Exception:
                            dt = None
                        if dt:
                            if not dt.tzinfo:
                                dt = dt.replace(tzinfo=timezone.utc)
                            age_sec = (datetime.now(tz=timezone.utc) - dt).total_seconds()
                            # Consider older than 10 minutes as stale
                            if age_sec > 10 * 60:
                                too_old = True
                except Exception:
                    pass

                celery_not_running = False
                try:
                    from celery.result import AsyncResult
                    task_id = active.get("task_id")
                    if task_id:
                        r = AsyncResult(task_id)
                        if r.state not in ("PENDING", "PROGRESS", "STARTED"):
                            celery_not_running = True
                except Exception:
                    # If broker changed or unavailable, prefer time-based stale detection
                    pass

                # If the stored environment signature doesn't match this environment, clear it
                env_mismatch = False
                try:
                    stored_broker = active.get("broker")
                    stored_os = active.get("opensearch")
                    if (stored_broker and stored_broker != settings.REDIS_URL) or (stored_os and stored_os != settings.OPENSEARCH_URL):
                        env_mismatch = True
                except Exception:
                    pass

                if too_old or celery_not_running or env_mismatch:
                    active["status"] = "interrupted"
                    if env_mismatch:
                        active["note"] = "cleared_due_to_env_mismatch"
                    state["active"] = active
                    save_state(state)

        except Exception:
            pass

        return {"success": True, "state": state, "active": state.get("active")}
    except Exception as e:
        logger.error(f"Error reading index state: {e}")
        raise HTTPException(status_code=500, detail="Failed to read index state")