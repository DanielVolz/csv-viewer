from fastapi import APIRouter, HTTPException, Request
import os
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import logging
import subprocess

from models.file import FileModel
from config import settings, get_settings
from utils.csv_utils import read_csv_file, DESIRED_ORDER
from tasks.tasks import index_all_csv_files, app
from utils.index_state import load_state, save_state
from celery import current_app
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/files",
    tags=["files"]
)


@router.get("/", response_model=List[dict])
async def list_files():
    """
    List all available netspeed CSV files.
    Returns them sorted with most recent (netspeed.csv) first.
    Also includes line count for each file.
    """
    try:
        # Get path to CSV files directory
        csv_dir = Path("/app/data")

        # List all netspeed CSV files
        files = []
        if csv_dir.exists():
            for file_path in csv_dir.glob("netspeed.csv*"):
                file_model = FileModel.from_path(str(file_path))

                # Count lines in the file (subtract 1 for header if file has content)
                line_count = 0
                try:
                    with open(file_path, 'r') as f:
                        line_count = sum(1 for _ in f)
                        # Subtract 1 for header if file has content
                        if line_count > 0:
                            line_count -= 1
                except Exception as e:
                    logger.error(f"Error counting lines in {file_path}: {e}")

                # Convert to dict and add line count
                file_dict = file_model.dict()
                # Normalize date to YYYY-MM-DD for consistent frontend display
                try:
                    if file_model.date:
                        file_dict["date"] = file_model.date.strftime('%Y-%m-%d')
                    else:
                        file_dict["date"] = None
                except Exception:
                    file_dict["date"] = None

                # Add precise modification time information
                try:
                    mtime = file_path.stat().st_mtime
                    from datetime import datetime as _dt, timezone as _tz
                    # Expose raw epoch for consistent client-side local formatting
                    file_dict["mtime"] = mtime
                    # Also include a timezone-aware ISO string in UTC for diagnostics
                    dt_utc = _dt.fromtimestamp(mtime, tz=_tz.utc)
                    file_dict["datetime"] = dt_utc.isoformat()
                    # Keep legacy "time" for backward compatibility (server-local)
                    try:
                        dt_local = _dt.fromtimestamp(mtime)
                        file_dict["time"] = dt_local.strftime('%H:%M')
                    except Exception:
                        pass
                except Exception:
                    # Optional fields; ignore if stat fails
                    pass
                file_dict["line_count"] = line_count
                files.append(file_dict)

        # Sort files: netspeed.csv first, then netspeed.csv.0, netspeed.csv.1, etc.
        def sort_key(f):
            name = f["name"]
            if name == "netspeed.csv":
                return (0, 0)  # Always first
            elif name.startswith("netspeed.csv."):
                try:
                    # Extract number after the dot (e.g., "netspeed.csv.1" -> 1)
                    suffix = name.split("netspeed.csv.")[1]
                    return (1, int(suffix))
                except (IndexError, ValueError):
                    # If parsing fails, put at end
                    return (2, 999)
            else:
                # Other files at the end
                return (3, 0)

        files.sort(key=sort_key)

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
        # Get path to current CSV file
        csv_dir = Path("/app/data")
        current_file = csv_dir / "netspeed.csv"
        fallback_file = csv_dir / "netspeed.csv.0"

        using_fallback = False
        file_to_use = current_file

        # Check if current file exists, if not use fallback
        if not current_file.exists():
            if fallback_file.exists():
                using_fallback = True
                file_to_use = fallback_file
            else:
                return {
                    "success": False,
                    "message": "No netspeed.csv found — place a file in /app/data and refresh. The netspeed.csv should be created at 06:55 AM.",
                    "date": None,
                    "line_count": 0,
                    "using_fallback": False,
                    "fallback_file": None
                }

        # Use the file model which handles creation date properly with fallbacks
        file_model = FileModel.from_path(str(file_to_use))

        # Format date consistently
        creation_date = file_model.date.strftime('%Y-%m-%d') if file_model.date else None

        # Get file modification time for change detection
        modification_time = file_to_use.stat().st_mtime

        # Count lines (subtract 1 for header)
        with open(file_to_use, 'r') as f:
            line_count = sum(1 for _ in f) - 1

        result = {
            "success": True,
            "message": "Using yesterday's data from netspeed.csv.0 until new netspeed.csv is generated at 06:55 AM." if using_fallback else "Current netspeed.csv file information retrieved successfully",
            "date": creation_date,
            "line_count": line_count,
            "last_modified": modification_time,
            "using_fallback": using_fallback,
            "fallback_file": "netspeed.csv.0" if using_fallback else None
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
        # Get path to CSV file
        csv_dir = Path("/app/data")
        file_path = csv_dir / filename

        using_fallback = False
        actual_filename = filename

        # If requesting netspeed.csv but it doesn't exist, try fallback
        if filename == "netspeed.csv" and not file_path.exists():
            fallback_path = csv_dir / "netspeed.csv.0"
            if fallback_path.exists():
                file_path = fallback_path
                actual_filename = "netspeed.csv.0"
                using_fallback = True
            else:
                return {
                    "success": False,
                    "message": "No netspeed.csv found — place a file in /app/data and refresh. The netspeed.csv should be created at 06:55 AM.",
                    "headers": [],
                    "data": [],
                    "creation_date": None,
                    "file_name": filename,
                    "using_fallback": False,
                    "fallback_file": None
                }
        elif not file_path.exists():
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

        # Get file creation date
        file_model = FileModel.from_path(str(file_path))
        creation_date = file_model.date.strftime('%Y-%m-%d') if file_model.date else None

        # Read CSV file
        headers, rows = read_csv_file(str(file_path))

    # Optional: filter by location code/prefix if provided
        loc_filter = (loc or "").strip().upper()
        if loc_filter:
            # Accept either 3-letter prefix (AAA) or 5-char code (AAA01)
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
                    # prefix match against first 3 letters of code
                    if code.startswith(loc_filter):
                        filtered.append(r)
            rows = filtered

        # Limit number of rows
        preview_rows = rows[:limit]

        fallback_message = " (using yesterday's data from netspeed.csv.0 until new file is generated at 06:55 AM)" if using_fallback else ""

        return {
            "success": True,
            "message": (f"Showing first {len(preview_rows)} entries of "
                        f"{len(rows)} total" + (f" (filtered by {loc_filter})" if loc_filter else "") + fallback_message),
            "headers": headers,
            "data": preview_rows,
            "creation_date": creation_date,
            "file_format": file_model.format,
            "file_name": filename,
            "actual_file_name": actual_filename,
            "using_fallback": using_fallback,
            "fallback_file": actual_filename if using_fallback else None
        }

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
        csv_dir = "/app/data"

        # Trigger the Celery task asynchronously
        task = index_all_csv_files.delay(csv_dir)

        return {
            "success": True,
            "message": "Reindexing task has been triggered",
            "task_id": task.id
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
        from utils.opensearch import OpenSearchConfig

        # Get path to current CSV file
        csv_file = "/app/data/netspeed.csv"

        # Check if file exists
        if not Path(csv_file).exists():
            raise HTTPException(
                status_code=404,
                detail="netspeed.csv file not found"
            )

        # Initialize OpenSearch and index the single file
        opensearch_config = OpenSearchConfig()

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
                # Try Celery first
                queued = False
                try:
                    _snap.delay(csv_file)
                    queued = True
                    logger.info("Queued snapshot_current_with_details after fast reindex")
                except Exception as e:
                    logger.debug(f"Could not queue snapshot_current_with_details (will run inline): {e}")
                # Fallback: run inline to guarantee details in dev even if Celery lacks the task
                if not queued:
                    try:
                        logger.info("Running snapshot_current_with_details inline (dev fallback)")
                        _ = _snap(csv_file)
                    except Exception as e:
                        logger.warning(f"Inline snapshot_current_with_details failed: {e}")
                # Additionally, in development always run inline to avoid stale worker task registry
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
                "message": f"Successfully reindexed netspeed.csv with {count} documents{repair_message}",
                "file": csv_file,
                "documents_indexed": count
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to reindex netspeed.csv"
            )

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
        # Basic allow‑list: only netspeed.csv and variants netspeed.csv.N plus optional _bak
        if not raw_name.startswith("netspeed.csv"):
            logger.warning(f"Blocked download attempt for disallowed filename: {raw_name}")
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Disallow path traversal
        if any(token in raw_name for token in ("..", "/", "\\")):
            logger.warning(f"Blocked traversal attempt: {raw_name}")
            raise HTTPException(status_code=400, detail="Invalid filename")

        csv_dir = Path("/app/data").resolve()
        file_path = (csv_dir / raw_name).resolve()

        # Ensure the resolved path is still inside csv_dir
        if csv_dir not in file_path.parents and file_path != csv_dir:
            logger.warning(f"Blocked escape attempt: {file_path}")
            raise HTTPException(status_code=400, detail="Invalid filename")

        if not file_path.exists():
            logger.error(f"File not found: {raw_name}")
            raise HTTPException(status_code=404, detail=f"File {raw_name} not found")

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

    Returns:
        List of column definitions with id, label, and default enabled state
    """
    try:
        # Use DESIRED_ORDER from csv_utils which defines the current 16-column format
        available_columns = []

    # Define default enabled state for each column returned to the frontend settings
    # Note: Speed 1 and Speed 2 are excluded from settings (always hidden)
    # Additionally, "MAC Address 2" is intentionally excluded from settings and hidden by default
        default_enabled = {
            "#": True,
            "File Name": True,
            "Creation Date": True,
            "IP Address": True,
            "Line Number": True,
            "MAC Address": True,
            "Subnet Mask": False,
            "Voice VLAN": True,
            "Switch Hostname": True,
            "Switch Port": True,
            "Speed Switch-Port": False,
            "Speed PC-Port": False,
            "Serial Number": True,
            "Model Name": True
        }

        # Build column definitions from DESIRED_ORDER, but only include columns that should be in settings
        display_labels = {
            "Creation Date": "Date",
            "IP Address": "IP Addr.",
            "Voice VLAN": "V-VLAN",
            "Serial Number": "Serial",
            "Model Name": "Model",
        }
        for column_id in DESIRED_ORDER:
            # Only include columns that are defined in default_enabled (excludes Speed 1, Speed 2)
            if column_id in default_enabled:
                # Explicitly skip "MAC Address 2" so it doesn't appear in settings
                if column_id == "MAC Address 2":
                    continue
                available_columns.append({
                    "id": column_id,
                    "label": display_labels.get(column_id, column_id),
                    "enabled": default_enabled[column_id]
                })

        return {
            "success": True,
            "columns": available_columns,
            "message": f"Retrieved {len(available_columns)} available columns"
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