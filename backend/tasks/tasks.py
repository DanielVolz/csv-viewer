import os
from celery import Celery
import logging
from pathlib import Path
from typing import Optional, Dict, List
from utils.opensearch import opensearch_config
from datetime import datetime
from utils.index_state import load_state, save_state, update_file_state, update_totals, is_file_current, start_active, update_active, clear_active
from utils.csv_utils import read_csv_file_normalized

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery
app = Celery('csv_viewer')

# Load Celery configuration
app.config_from_object('celeryconfig')


@app.task(name='tasks.index_csv')
def index_csv(file_path: str) -> dict:
    """
    Task to index a CSV file in OpenSearch.

    Args:
        file_path: Path to the CSV file to index

    Returns:
        dict: A dictionary containing the indexing result
    """
    logger.info(f"Indexing CSV file at {file_path}")

    try:
        success, count = opensearch_config.index_csv_file(file_path)

        if success:
            # Best-effort: persist stats snapshot for this file
            try:
                from models.file import FileModel as _FM
                fm = _FM.from_path(file_path)
                date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
                _, _rows = read_csv_file_normalized(file_path)
                total_phones = len(_rows)
                switches = set()
                locations = set()
                city_codes = set()
                phones_with_kem = 0
                model_counts: Dict[str, int] = {}
                for r in _rows:
                    sh = (r.get("Switch Hostname") or "").strip()
                    if sh:
                        switches.add(sh)
                        try:
                            from api.stats import extract_location
                            loc = extract_location(sh)
                            if loc:
                                locations.add(loc)
                                city_codes.add(loc[:3])
                        except Exception:
                            pass
                    if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                        phones_with_kem += 1
                    model = (r.get("Model Name") or "").strip() or "Unknown"
                    if model != "Unknown":
                        model_counts[model] = model_counts.get(model, 0) + 1
                phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]
                metrics = {
                    "totalPhones": total_phones,
                    "totalSwitches": len(switches),
                    "totalLocations": len(locations),
                    "totalCities": len(city_codes),
                    "phonesWithKEM": phones_with_kem,
                    "phonesByModel": phones_by_model,
                    "cityCodes": sorted(list(city_codes)),
                }
                opensearch_config.index_stats_snapshot(file=fm.name, date=date_str, metrics=metrics)
                # Additionally: build per-location snapshot docs and index in bulk
                # Aggregate per 5-char location code for speed at query-time
                per_loc_counts: Dict[str, Dict[str, int]] = {}
                per_loc_switches: Dict[str, set] = {}
                for r in _rows:
                    sh = (r.get("Switch Hostname") or "").strip()
                    if not sh:
                        continue
                    try:
                        from api.stats import extract_location as _extract_location
                        loc = _extract_location(sh)
                    except Exception:
                        loc = None
                    if not loc:
                        continue
                    plc = per_loc_counts.setdefault(loc, {"totalPhones": 0, "phonesWithKEM": 0, "totalSwitches": 0})
                    plc["totalPhones"] += 1
                    sset = per_loc_switches.setdefault(loc, set())
                    if sh not in sset:
                        sset.add(sh)
                        plc["totalSwitches"] += 1
                    if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                        plc["phonesWithKEM"] += 1
                loc_docs = []
                for k, agg in per_loc_counts.items():
                    loc_docs.append({
                        "key": k,
                        "mode": "code",
                        "totalPhones": agg["totalPhones"],
                        "totalSwitches": agg["totalSwitches"],
                        "phonesWithKEM": agg["phonesWithKEM"],
                    })
                try:
                    opensearch_config.index_stats_location_snapshots(file=fm.name, date=date_str, loc_docs=loc_docs)
                except Exception as _e:
                    logger.debug(f"Indexing per-location snapshots failed for {file_path}: {_e}")
            except Exception as _e:
                logger.debug(f"Stats snapshot failed for {file_path}: {_e}")
            # Best-effort: persist full archive snapshot
            try:
                if '_rows' not in locals():
                    _, _rows = read_csv_file_normalized(file_path)
                opensearch_config.index_archive_snapshot(file=fm.name, date=date_str, rows=_rows)
            except Exception as _e:
                logger.debug(f"Archive snapshot failed for {file_path}: {_e}")
            return {
                "status": "success",
                "message": f"Successfully indexed {count} documents from {file_path}",
                "file_path": file_path,
                "count": count
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to index {file_path}",
                "file_path": file_path,
                "count": 0
            }
    except Exception as e:
        logger.error(f"Error indexing CSV file {file_path}: {e}")
        return {
            "status": "error",
            "message": f"Error indexing file: {str(e)}",
            "file_path": file_path,
            "count": 0
        }


@app.task(name='tasks.backfill_location_snapshots')
def backfill_location_snapshots(directory_path: str = "/app/data") -> dict:
    """Backfill per-location snapshots (stats_netspeed_loc) for all netspeed files.

    Useful if stats_netspeed_loc is empty or partially populated.
    """
    try:
        path = Path(directory_path)
        files = []
        for p in sorted(path.glob("netspeed.csv*"), key=lambda x: x.name):
            name = p.name
            if name == "netspeed.csv" or (name.startswith("netspeed.csv.") and name.replace("netspeed.csv.", "").isdigit()):
                files.append(p)
        processed = 0
        total_loc_docs = 0
        for f in files:
            try:
                from models.file import FileModel as _FM
                fm = _FM.from_path(str(f))
                date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
                _, rows = read_csv_file_normalized(str(f))
                per_loc_counts: Dict[str, Dict[str, int]] = {}
                per_loc_switches: Dict[str, set] = {}
                for r in rows:
                    sh = (r.get("Switch Hostname") or "").strip()
                    if not sh:
                        continue
                    try:
                        from api.stats import extract_location as _extract_location
                        loc = _extract_location(sh)
                    except Exception:
                        loc = None
                    if not loc:
                        continue
                    plc = per_loc_counts.setdefault(loc, {"totalPhones": 0, "phonesWithKEM": 0, "totalSwitches": 0})
                    plc["totalPhones"] += 1
                    sset = per_loc_switches.setdefault(loc, set())
                    if sh not in sset:
                        sset.add(sh)
                        plc["totalSwitches"] += 1
                    if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                        plc["phonesWithKEM"] += 1
                loc_docs = []
                for k, agg in per_loc_counts.items():
                    loc_docs.append({
                        "key": k,
                        "mode": "code",
                        "totalPhones": agg["totalPhones"],
                        "totalSwitches": agg["totalSwitches"],
                        "phonesWithKEM": agg["phonesWithKEM"],
                    })
                if loc_docs:
                    opensearch_config.index_stats_location_snapshots(file=fm.name, date=date_str, loc_docs=loc_docs)
                    total_loc_docs += len(loc_docs)
                processed += 1
            except Exception as _e:
                logger.warning(f"Backfill failed for {f}: {_e}")
        return {"status": "success", "files": processed, "loc_docs": total_loc_docs}
    except Exception as e:
        logger.error(f"Backfill error: {e}")
        return {"status": "error", "message": str(e)}


@app.task(name='tasks.backfill_stats_snapshots')
def backfill_stats_snapshots(directory_path: str = "/app/data") -> dict:
    """Backfill global stats snapshots (stats_netspeed) for all netspeed files.

    This computes metrics from CSV files only and does not touch netspeed_* search indices.
    Useful when stats_netspeed is empty and you want fast timelines without full reindex.
    """
    try:
        path = Path(directory_path)
        files = []
        for p in sorted(path.glob("netspeed.csv*"), key=lambda x: x.name):
            name = p.name
            if name == "netspeed.csv" or (name.startswith("netspeed.csv.") and name.replace("netspeed.csv.", "").isdigit()):
                files.append(p)
        processed = 0
        for f in files:
            try:
                from models.file import FileModel as _FM
                fm = _FM.from_path(str(f))
                date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
                _, rows = read_csv_file_normalized(str(f))
                total_phones = len(rows)
                switches = set()
                locations = set()
                city_codes = set()
                phones_with_kem = 0
                model_counts: Dict[str, int] = {}
                for r in rows:
                    sh = (r.get("Switch Hostname") or "").strip()
                    if sh:
                        switches.add(sh)
                        try:
                            from api.stats import extract_location
                            loc = extract_location(sh)
                            if loc:
                                locations.add(loc)
                                city_codes.add(loc[:3])
                        except Exception:
                            pass
                    if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                        phones_with_kem += 1
                    model = (r.get("Model Name") or "").strip() or "Unknown"
                    if model != "Unknown":
                        model_counts[model] = model_counts.get(model, 0) + 1
                phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]
                metrics = {
                    "totalPhones": total_phones,
                    "totalSwitches": len(switches),
                    "totalLocations": len(locations),
                    "totalCities": len(city_codes),
                    "phonesWithKEM": phones_with_kem,
                    "phonesByModel": phones_by_model,
                    "cityCodes": sorted(list(city_codes)),
                }
                opensearch_config.index_stats_snapshot(file=fm.name, date=date_str, metrics=metrics)
                processed += 1
            except Exception as _e:
                logger.warning(f"Backfill stats failed for {f}: {_e}")
        return {"status": "success", "files": processed}
    except Exception as e:
        logger.error(f"Backfill stats error: {e}")
        return {"status": "error", "message": str(e)}

@app.task(bind=True, name='tasks.index_all_csv_files')
def index_all_csv_files(self, directory_path: str) -> dict:
    """
    Task to index all CSV files in a directory.

    Args:
        directory_path: Path to the directory containing CSV files

    Returns:
        dict: A dictionary containing the indexing results
    """
    logger.info(f"Indexing all CSV files in {directory_path}")

    try:
        path = Path(directory_path)
        patterns = ["netspeed.csv", "netspeed.csv.*", "netspeed.csv_bak"]
        files: List[Path] = []
        for pattern in patterns:
            glob_results = sorted(path.glob(pattern), key=lambda x: str(x))
            files.extend(glob_results)

        # Also include archived daily CSV copies under /archive
        archive_dir = path / "archive"
        if archive_dir.exists():
            # Expect file names like netspeed_YYYY-MM-DDTHHMMSSZ.csv
            archived = sorted(archive_dir.glob("netspeed_*.csv"), key=lambda x: str(x))
            files.extend(archived)

        netspeed_files = [
            f for f in files
            if (f.name.startswith("netspeed.csv") and f.name != "netspeed.csv_bak" and not f.name.endswith("_bak"))
            or (f.parent.name == "archive" and f.name.startswith("netspeed_"))
        ]
        # Separate backup files explicitly
        backup_files = [f for f in files if f.name.endswith("_bak") or f.name == "netspeed.csv_bak"]
        # Always include all netspeed files (base + all historical), backups last
        base_files = [f for f in netspeed_files if f.name == "netspeed.csv"]
        historical_files_all = [f for f in netspeed_files if f.name != "netspeed.csv"]
        files = base_files + historical_files_all + backup_files

        logger.info(f"Found {len(files)} files matching patterns {patterns} and archive: {[str(f.relative_to(path)) for f in files]}")

        if not files:
            return {
                "status": "warning",
                "message": f"No CSV files found in {directory_path}",
                "directory": directory_path,
                "files_processed": 0,
                "total_documents": 0,
            }

        current_files = [f for f in files if f.name == "netspeed.csv"]
        other_files = [f for f in files if f.name != "netspeed.csv"]
        ordered_files = current_files + sorted(other_files, key=lambda x: x.name)

        results: List[Dict] = []
        total_documents = 0
        index_state = load_state()

        # Send initial progress and persist an active record
        try:
            task_id = getattr(self.request, 'id', os.environ.get('CELERY_TASK_ID', 'manual'))
            start_active(index_state, task_id, len(ordered_files))
            save_state(index_state)
            # Attach environment signature for isolation (dev vs prod): broker & opensearch URLs
            try:
                from config import settings as _settings
                update_active(index_state,
                              broker=_settings.REDIS_URL,
                              opensearch=_settings.OPENSEARCH_URL)
                save_state(index_state)
            except Exception:
                pass
            # Also expose Celery PROGRESS meta for /api/search/index/status/{task_id}
            try:
                self.update_state(state='PROGRESS', meta={
                    "task_id": task_id,
                    "status": "running",
                    "current_file": None,
                    "index": 0,
                    "total_files": len(ordered_files),
                    "documents_indexed": 0,
                    "last_file_docs": 0,
                })
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"Initial progress update failed: {e}")

        start_time = datetime.utcnow()

        for i, file_path in enumerate(ordered_files):
            logger.info(f"Processing file {i+1}/{len(ordered_files)}: {file_path}")
            # Emit a pre-index progress update so UI immediately shows the current file
            try:
                update_active(index_state,
                              current_file=file_path.name,
                              index=i + 1,
                              last_file_docs=0)
                save_state(index_state)
                try:
                    self.update_state(state='PROGRESS', meta={
                        "task_id": getattr(self.request, 'id', None),
                        "status": "running",
                        "current_file": file_path.name,
                        "index": i + 1,
                        "total_files": len(ordered_files),
                        "documents_indexed": total_documents,
                        "last_file_docs": 0,
                    })
                except Exception:
                    pass
            except Exception:
                pass
            try:
                success, count = opensearch_config.index_csv_file(str(file_path))
                total_documents += count

                # Count lines (excluding header)
                line_count = 0
                try:
                    with open(file_path, 'r') as fh:
                        total_lines = sum(1 for _ in fh)
                        if total_lines > 0:
                            line_count = total_lines - 1
                except Exception:
                    line_count = 0

                try:
                    update_file_state(index_state, file_path, line_count, count)
                except Exception as e:
                    logger.warning(f"Failed to update index state for {file_path}: {e}")

                results.append({
                    "file": str(file_path),
                    "success": success,
                    "count": count,
                    "line_count": line_count
                })
                logger.info(f"Completed {file_path}: {count} documents indexed")

                # Persist a stats snapshot for timeline (best-effort)
                try:
                    from models.file import FileModel as _FM
                    fm = _FM.from_path(str(file_path))
                    date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
                    # Compute metrics from normalized CSV (local, no opensearch read)
                    _, _rows = read_csv_file_normalized(str(file_path))
                    # Minimal recomputation to avoid duplicating logic
                    total_phones = len(_rows)
                    switches = set()
                    locations = set()
                    city_codes = set()
                    phones_with_kem = 0
                    model_counts: Dict[str, int] = {}
                    for r in _rows:
                        sh = (r.get("Switch Hostname") or "").strip()
                        if sh:
                            switches.add(sh)
                            # Reuse extract_location from stats via a local import
                            try:
                                from api.stats import extract_location
                                loc = extract_location(sh)
                                if loc:
                                    locations.add(loc)
                                    city_codes.add(loc[:3])
                            except Exception:
                                pass
                        if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                            phones_with_kem += 1
                        model = (r.get("Model Name") or "").strip() or "Unknown"
                        if model != "Unknown":
                            model_counts[model] = model_counts.get(model, 0) + 1
                    phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]
                    metrics = {
                        "totalPhones": total_phones,
                        "totalSwitches": len(switches),
                        "totalLocations": len(locations),
                        "totalCities": len(city_codes),
                        "phonesWithKEM": phones_with_kem,
                        "phonesByModel": phones_by_model,
                        "cityCodes": sorted(list(city_codes)),
                    }
                    opensearch_config.index_stats_snapshot(file=fm.name, date=date_str, metrics=metrics)
                    # Additionally: precompute per-location snapshots for fast location timelines
                    try:
                        # Aggregate per 5-char location code
                        per_loc_counts: Dict[str, Dict[str, int]] = {}
                        per_loc_switches: Dict[str, set] = {}
                        for r in _rows:
                            sh2 = (r.get("Switch Hostname") or "").strip()
                            if not sh2:
                                continue
                            try:
                                from api.stats import extract_location as _extract_location
                                loc2 = _extract_location(sh2)
                            except Exception:
                                loc2 = None
                            if not loc2:
                                continue
                            plc = per_loc_counts.setdefault(loc2, {"totalPhones": 0, "phonesWithKEM": 0, "totalSwitches": 0})
                            plc["totalPhones"] += 1
                            sset = per_loc_switches.setdefault(loc2, set())
                            if sh2 not in sset:
                                sset.add(sh2)
                                plc["totalSwitches"] += 1
                            if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                                plc["phonesWithKEM"] += 1
                        loc_docs = []
                        for k, agg in per_loc_counts.items():
                            loc_docs.append({
                                "key": k,
                                "mode": "code",
                                "totalPhones": agg["totalPhones"],
                                "totalSwitches": agg["totalSwitches"],
                                "phonesWithKEM": agg["phonesWithKEM"],
                            })
                        if loc_docs:
                            opensearch_config.index_stats_location_snapshots(file=fm.name, date=date_str, loc_docs=loc_docs)
                    except Exception as _e:
                        logger.debug(f"Per-location snapshot indexing failed for {file_path}: {_e}")
                except Exception as _e:
                    logger.debug(f"Stats snapshot failed for {file_path}: {_e}")

                # Persist a full archive snapshot of rows (best-effort, excludes external city names)
                try:
                    if '_rows' not in locals():
                        _, _rows = read_csv_file_normalized(str(file_path))
                    opensearch_config.index_archive_snapshot(file=file_path.name, date=date_str, rows=_rows)
                except Exception as _e:
                    logger.debug(f"Archive snapshot failed for {file_path}: {_e}")

                # Progress update (persist)
                try:
                    update_active(index_state,
                                  current_file=file_path.name,
                                  index=i + 1,
                                  documents_indexed=total_documents,
                                  last_file_docs=count)
                    save_state(index_state)
                except Exception as e:
                    logger.debug(f"Progress update failed: {e}")
                # Emit Celery PROGRESS meta for UI polling
                try:
                    self.update_state(state='PROGRESS', meta={
                        "task_id": task_id,
                        "status": "running",
                        "current_file": file_path.name,
                        "index": i + 1,
                        "total_files": len(ordered_files),
                        "documents_indexed": total_documents,
                        "last_file_docs": count,
                    })
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")
                results.append({
                    "file": str(file_path),
                    "success": False,
                    "error": str(e),
                    "count": 0
                })

        # Persist state
        last_success_ts = None
        try:
            update_totals(index_state, len(ordered_files), total_documents)
            last_success_ts = datetime.utcnow().isoformat() + 'Z'
            index_state['last_success'] = last_success_ts
            clear_active(index_state, 'completed')
            save_state(index_state)
        except Exception as e:
            logger.warning(f"Failed saving index state: {e}")

        return {
            "status": "success",
            "message": f"Processed {len(ordered_files)} files, indexed {total_documents} documents",
            "directory": directory_path,
            "files_processed": len(ordered_files),
            "total_documents": total_documents,
            "results": results,
            "started_at": start_time.isoformat() + 'Z',
            "finished_at": last_success_ts
        }
    except Exception as e:
        logger.error(f"Error indexing directory {directory_path}: {e}")
        try:
            clear_active(index_state, 'failed')
            save_state(index_state)
        except Exception:
            pass
        return {
            "status": "error",
            "message": f"Error processing directory: {str(e)}",
            "directory": directory_path,
            "files_processed": 0,
            "total_documents": 0
        }


@app.task(name='tasks.search_opensearch')
def search_opensearch(query: str, field: Optional[str] = None, include_historical: bool = False, size: int = 20000) -> dict:
    """
    Task to search OpenSearch.

    Args:
        query: Search query
        field: Optional field to search in
        include_historical: Whether to include historical indices

    Returns:
        dict: A dictionary containing the search results including file creation dates
    """
    logger.info(f"Searching OpenSearch for '{query}'")
    from time import perf_counter
    t0 = perf_counter()
    try:
        headers, documents = opensearch_config.search(
            query=query,
            field=field,
            include_historical=include_historical,
            size=size
        )

        # Process documents to ensure file creation dates and formats are included
        # Avoid heavy per-row filesystem work by caching per file name within this search
        meta_cache: dict[str, dict] = {}

        def get_file_meta(_file_name: str) -> dict:
            if _file_name in meta_cache:
                return meta_cache[_file_name]
            meta: dict = {"date": None, "format": None}
            file_path = f"/app/data/{_file_name}"
            try:
                from models.file import FileModel as _FM
                fm = _FM.from_path(file_path)
                meta["date"] = fm.date.strftime('%Y-%m-%d') if fm.date else None
                meta["format"] = fm.format or None
            except Exception as _e:
                logger.debug(f"File meta probe failed for {_file_name}: {_e}")
            # Minimal fallbacks
            if meta["date"] is None:
                try:
                    from pathlib import Path as _Path
                    from datetime import datetime as _dt
                    p = _Path(file_path)
                    if p.exists():
                        meta["date"] = _dt.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d')
                except Exception:
                    pass
            if meta["format"] is None:
                # Heuristic: current netspeed.csv likely "new", historical default to "old"
                meta["format"] = "new" if _file_name == "netspeed.csv" else "old"
            meta_cache[_file_name] = meta
            return meta

        for doc in documents:
            file_name = doc.get('File Name')
            if not file_name:
                continue
            meta = None
            # Only fetch meta if any field is missing
            need_date = ('Creation Date' not in doc) or (not doc.get('Creation Date'))
            need_format = ('File Format' not in doc)
            if need_date or need_format:
                meta = get_file_meta(file_name)
            if need_date and meta and meta.get('date'):
                doc['Creation Date'] = meta['date']
            if need_format and meta and meta.get('format'):
                doc['File Format'] = meta['format']

    # Note: CSV fallback used during testing has been removed. OpenSearch results are used exclusively.

        # Apply same column filtering as Preview API for consistency
        from utils.csv_utils import filter_display_columns

        # Filter headers and data to match display preferences
        filtered_headers, filtered_documents = filter_display_columns(headers, documents)

        elapsed_ms = int((perf_counter() - t0) * 1000)
        return {
            "status": "success",
            "message": f"Found {len(filtered_documents)} results for '{query}'",
            "headers": filtered_headers,
            "data": filtered_documents,
            "took_ms": elapsed_ms
        }
    except Exception as e:
        logger.error(f"Error searching for '{query}': {e}")
        return {
            "status": "error",
            "message": f"Error searching: {str(e)}",
            "headers": [],
            "data": [],
            "took_ms": None
        }


# Removed: morning_reindex task (scheduler deprecated; file watcher handles reindexing)


@app.task(name='tasks.snapshot_current_stats')
def snapshot_current_stats(directory_path: str = "/app/data") -> dict:
    """Snapshot today's global and per-location statistics from the current netspeed.csv.

    This precaches timeline data in stats_netspeed and stats_netspeed_loc so the UI is fast.
    CSV remains a fallback only.
    """
    try:
        path = Path(directory_path)
        file_path = (path / "netspeed.csv").resolve()
        if not file_path.exists():
            return {"status": "warning", "message": f"{file_path} not found"}

        from models.file import FileModel as _FM
        fm = _FM.from_path(str(file_path))
        date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None

        # Read CSV once
        _, rows = read_csv_file_normalized(str(file_path))

        # Global metrics
        total_phones = len(rows)
        switches = set()
        locations = set()
        city_codes = set()
        phones_with_kem = 0
        model_counts: Dict[str, int] = {}
        for r in rows:
            sh = (r.get("Switch Hostname") or "").strip()
            if sh:
                switches.add(sh)
                try:
                    from api.stats import extract_location
                    loc = extract_location(sh)
                    if loc:
                        locations.add(loc)
                        city_codes.add(loc[:3])
                except Exception:
                    pass
            if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                phones_with_kem += 1
            model = (r.get("Model Name") or "").strip() or "Unknown"
            if model != "Unknown":
                model_counts[model] = model_counts.get(model, 0) + 1

        phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]
        metrics = {
            "totalPhones": total_phones,
            "totalSwitches": len(switches),
            "totalLocations": len(locations),
            "totalCities": len(city_codes),
            "phonesWithKEM": phones_with_kem,
            "phonesByModel": phones_by_model,
            "cityCodes": sorted(list(city_codes)),
        }
        opensearch_config.index_stats_snapshot(file=fm.name, date=date_str, metrics=metrics)

        # Per-location metrics (aggregate per 5-char code)
        per_loc_counts: Dict[str, Dict[str, int]] = {}
        per_loc_switches: Dict[str, set] = {}
        for r in rows:
            sh2 = (r.get("Switch Hostname") or "").strip()
            if not sh2:
                continue
            try:
                from api.stats import extract_location as _extract_location
                loc2 = _extract_location(sh2)
            except Exception:
                loc2 = None
            if not loc2:
                continue
            plc = per_loc_counts.setdefault(loc2, {"totalPhones": 0, "phonesWithKEM": 0, "totalSwitches": 0})
            plc["totalPhones"] += 1
            sset = per_loc_switches.setdefault(loc2, set())
            if sh2 not in sset:
                sset.add(sh2)
                plc["totalSwitches"] += 1
            if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                plc["phonesWithKEM"] += 1
        loc_docs = []
        for k, agg in per_loc_counts.items():
            loc_docs.append({
                "key": k,
                "mode": "code",
                "totalPhones": agg["totalPhones"],
                "totalSwitches": agg["totalSwitches"],
                "phonesWithKEM": agg["phonesWithKEM"],
            })
        if loc_docs:
            opensearch_config.index_stats_location_snapshots(file=fm.name, date=date_str, loc_docs=loc_docs)

        # Optional: persist archive snapshot for the day
        try:
            opensearch_config.index_archive_snapshot(file=fm.name, date=date_str, rows=rows)
        except Exception:
            pass

        return {"status": "success", "file": fm.name, "date": date_str, "loc_docs": len(loc_docs)}
    except Exception as e:
        logger.error(f"snapshot_current_stats error: {e}")
        return {"status": "error", "message": str(e)}
