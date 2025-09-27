from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Optional
import logging
from config import settings
from tasks.tasks import search_opensearch
from tasks.tasks import backfill_location_snapshots
from tasks.tasks import backfill_stats_snapshots
from celery.result import AsyncResult
from utils.opensearch import (
    opensearch_config,
    OpenSearchConfig,
    OpenSearchUnavailableError,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/search",
    tags=["search"]
)


@router.get("/")
async def search_files(
    query: Optional[str] = Query(None, description="General search query"),
    include_historical: bool = Query(
        False,
        description="Whether to search historical files"
    ),
    field: Optional[str] = Query(
        None,
        description="Specific field to search (e.g., ip_address, mac_address)"
    ),
    limit: Optional[int] = Query(
        None,
        description="Maximum number of results to return (server will cap to 20000)."
    )
):
    """
    Search netspeed CSV files using Elasticsearch.

    Args:
        query: General search term
        include_historical: If True, search all files. If False, only current.
        field: Optional field name to limit search to

    Returns:
        Dictionary with search results
    """
    try:
        # Log search request
        logger.info(
            f"Search request - query: {query}, "
            f"include_historical: {include_historical}, field: {field}"
        )

        # General search
        if query:
            # Submit search task to Celery
            # Apply sane default and cap
            default_limit = getattr(settings, "SEARCH_MAX_RESULTS", 5000)
            req_limit = limit if (isinstance(limit, int) and limit > 0) else default_limit
            eff_limit = min(max(1, req_limit), 20000)

            # Shortcut 1: For phone-like queries (+digits), run synchronously and return exactly one result
            try:
                qn_phone = (query or "").strip()
                looks_like_phone = bool(isinstance(qn_phone, str) and __import__('re').fullmatch(r"\+?\d{7,}", qn_phone or ""))
            except Exception:
                looks_like_phone = False
            if looks_like_phone and (field is None or field == "Line Number"):
                from time import perf_counter
                t0 = perf_counter()
                try:
                    headers, documents = opensearch_config.search(
                        query=qn_phone,
                        field="Line Number" if field == "Line Number" else None,
                        include_historical=include_historical,
                        size=1,
                    )
                    from utils.csv_utils import filter_display_columns
                    filtered_headers, filtered_documents = filter_display_columns(headers, documents)
                    took_ms = int((perf_counter() - t0) * 1000)
                    return {
                        "success": True,
                        "message": f"Found {len(filtered_documents)} results for '{query}'",
                        "headers": filtered_headers,
                        "data": filtered_documents,
                        "took_ms": took_ms,
                    }
                except Exception as e:
                    logger.error(f"Synchronous exact phone search failed: {e}")
                    # Fallback to Celery path

            # Shortcut 2: For exact Serial Number-like queries (long alphanumeric, not pure digits), run synchronously
            try:
                qn_sn = (query or "").strip()
                looks_like_serial = bool(isinstance(qn_sn, str) and __import__('re').fullmatch(r"[A-Za-z0-9]{8,}", qn_sn or "") and not __import__('re').fullmatch(r"\d{8,}", qn_sn or ""))
            except Exception:
                looks_like_serial = False
            if looks_like_serial and (field is None or field == "Serial Number"):
                from time import perf_counter
                t0 = perf_counter()
                try:
                    headers, documents = opensearch_config.search(
                        query=qn_sn,
                        field="Serial Number" if field == "Serial Number" else None,
                        include_historical=include_historical,
                        size=limit or 200,
                    )
                    from utils.csv_utils import filter_display_columns
                    filtered_headers, filtered_documents = filter_display_columns(headers, documents)
                    took_ms = int((perf_counter() - t0) * 1000)
                    return {
                        "success": True,
                        "message": f"Found {len(filtered_documents)} results for '{query}'",
                        "headers": filtered_headers,
                        "data": filtered_documents,
                        "took_ms": took_ms,
                    }
                except Exception as e:
                    logger.error(f"Synchronous exact Serial Number search failed: {e}")
                    # Fallback to Celery path

            # Shortcut 3: For exact Switch Port-like queries, run synchronously to use latest in-process logic
            try:
                qn = (query or "").strip()
                looks_like_port = (isinstance(qn, str) and "/" in qn and len(qn) >= 5)
            except Exception:
                looks_like_port = False
            if looks_like_port and (field is None or field == "Switch Port"):
                from time import perf_counter
                t0 = perf_counter()
                try:
                    headers, documents = opensearch_config.search(
                        query=qn,
                        field="Switch Port" if field == "Switch Port" else None,
                        include_historical=include_historical,
                        size=eff_limit,
                    )
                    # Align with task's display filtering for consistency
                    from utils.csv_utils import filter_display_columns
                    filtered_headers, filtered_documents = filter_display_columns(headers, documents)
                    took_ms = int((perf_counter() - t0) * 1000)
                    return {
                        "success": True,
                        "message": f"Found {len(filtered_documents)} results for '{query}'",
                        "headers": filtered_headers,
                        "data": filtered_documents,
                        "took_ms": took_ms,
                    }
                except Exception as e:
                    logger.error(f"Synchronous exact Switch Port search failed: {e}")
                    # Fallback to Celery path

            task = search_opensearch.delay(
                query=query,
                field=field,
                include_historical=include_historical,
                size=eff_limit
            )

            # Wait for task to complete (with timeout)
            # This is a synchronous operation, but the work is done by Celery
            # Wait up to configured timeout (configurable via SEARCH_TIMEOUT_SECONDS)
            timeout_s = getattr(settings, "SEARCH_TIMEOUT_SECONDS", 10)
            result = task.get(timeout=timeout_s)

            if result["status"] == "success":
                return {
                    "success": True,
                    "message": result["message"],
                    "headers": result["headers"],
                    "data": result["data"],
                    "took_ms": result.get("took_ms")
                }
            else:
                return {
                    "success": False,
                    "message": result["message"],
                    "headers": result.get("headers", []),
                    "data": [],
                    "took_ms": result.get("took_ms")
                }

        # No search parameters provided
        else:
            return {
                "success": False,
                "message": "Please provide a search term in the 'query' parameter"
            }

    except AsyncResult.TimeoutError:
        logger.error(f"Search task timed out for query: {query}")
        raise HTTPException(
            status_code=504,
            detail="Search operation timed out. Try a more specific search term."
        )
    except Exception as e:
        logger.error(f"Error during search: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to perform search"
        )


@router.get("/index/all")
async def index_all_csv_files(
    background_tasks: BackgroundTasks
):
    """
    Index all CSV files in the configured directory.
    This is an asynchronous operation that runs in the background.

    Returns:
        Dictionary with status information
    """
    from tasks.tasks import index_all_csv_files

    try:
        # Invalidate in-process stats caches before starting a rebuild
        try:
            from api.stats import invalidate_caches as _invalidate
            _invalidate("index/all requested")
        except Exception:
            pass
        # Cleanup existing netspeed_* indices BEFORE starting a full rebuild to prevent duplicates
        try:
            cfg = OpenSearchConfig()
            should_wait = bool(getattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", True))
            if should_wait:
                cfg.wait_for_availability(
                    timeout=max(60.0, float(getattr(settings, "OPENSEARCH_STARTUP_TIMEOUT_SECONDS", 45))),
                    interval=float(getattr(settings, "OPENSEARCH_STARTUP_POLL_SECONDS", 3.0)),
                    reason="index_all_pre_cleanup",
                )
            elif not cfg.quick_ping():
                logger.warning("OpenSearch unavailable and wait disabled; skipping index/all trigger")
                raise HTTPException(
                    status_code=503,
                    detail="OpenSearch is unavailable and waits are disabled; skipping index/all run.",
                )
        except OpenSearchUnavailableError as exc:
            logger.warning(f"OpenSearch unavailable for index/all request: {exc}")
            raise HTTPException(
                status_code=503,
                detail="OpenSearch is not ready yet. Please wait a moment and retry."
            ) from exc

        try:
            deleted = cfg.cleanup_indices_by_pattern("netspeed_*")
            logger.info(f"Pre-rebuild cleanup removed {deleted} netspeed_* indices")
        except Exception as _e:
            logger.warning(f"Pre-rebuild cleanup skipped/failed: {_e}")

        # Submit indexing task to Celery
        task = index_all_csv_files.delay()

        return {
            "success": True,
            "message": "Indexing task started",
            "task_id": task.id
        }
    except Exception as e:
        logger.error(f"Error starting indexing task: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start indexing task: {str(e)}"
        )


@router.post("/index/backfill-locations")
async def backfill_locations():
    """Trigger a background job to backfill per-location snapshots (stats_netspeed_loc)."""
    try:
        task = backfill_location_snapshots.delay()
        return {"success": True, "message": "Backfill task started", "task_id": task.id}
    except Exception as e:
        logger.error(f"Error starting backfill task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start backfill task: {e}")


@router.post("/index/backfill-stats")
async def backfill_stats():
    """Trigger a background job to backfill global stats snapshots (stats_netspeed)."""
    try:
        task = backfill_stats_snapshots.delay()
        return {"success": True, "message": "Backfill task started", "task_id": task.id}
    except Exception as e:
        logger.error(f"Error starting backfill stats task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start backfill stats task: {e}")


@router.get("/index/status/{task_id}")
async def get_index_status(task_id: str):
    """
    Get status of an indexing task.

    Args:
        task_id: ID of the task to check

    Returns:
        Dictionary with task status
    """
    try:
        # Get task result
        task_result = AsyncResult(task_id)

        # Include meta if in PROGRESS state
        if task_result.state == 'PROGRESS':
            meta = task_result.info or {}
            return {
                "success": True,
                "status": "running",
                "progress": meta
            }
        if task_result.ready():
            if task_result.successful():
                result = task_result.result
                return {
                    "success": True,
                    "status": "completed",
                    "result": result
                }
            else:
                return {
                    "success": False,
                    "status": "failed",
                    "error": str(task_result.result)
                }
        else:
            return {
                "success": True,
                "status": "running"
            }
    except Exception as e:
        logger.error(f"Error checking task status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check task status: {str(e)}"
        )


@router.post("/index/rebuild")
async def rebuild_indices(include_historical: bool = True):
    """Delete all netspeed_* indices and trigger a fresh full indexing.

    Args:
        include_historical: kept for forward compatibility (currently always deletes all netspeed_* )
    """
    try:
        try:
            should_wait = bool(getattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", True))
            if should_wait:
                opensearch_config.wait_for_availability(
                    timeout=max(60.0, float(getattr(settings, "OPENSEARCH_STARTUP_TIMEOUT_SECONDS", 45))),
                    interval=float(getattr(settings, "OPENSEARCH_STARTUP_POLL_SECONDS", 3.0)),
                    reason="rebuild_indices",
                )
            elif not opensearch_config.quick_ping():
                logger.warning("OpenSearch unavailable and wait disabled; skipping rebuild request")
                raise HTTPException(
                    status_code=503,
                    detail="OpenSearch is unavailable and waits are disabled; skipping rebuild.",
                )
        except OpenSearchUnavailableError as exc:
            logger.warning(f"OpenSearch unavailable for rebuild request: {exc}")
            raise HTTPException(
                status_code=503,
                detail="OpenSearch is not ready yet. Please retry once the search service is up."
            ) from exc

        # Delete indices (best effort)
        deleted = opensearch_config.cleanup_indices_by_pattern("netspeed_*")
        logger.info(f"Rebuild requested: deleted {deleted} indices")

        from tasks.tasks import index_all_csv_files
        task = index_all_csv_files.delay()
        return {
            "success": True,
            "message": f"Deleted {deleted} indices, started fresh indexing",
            "deleted_indices": deleted,
            "task_id": task.id
        }
    except Exception as e:
        logger.error(f"Error rebuilding indices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rebuild indices: {e}")


# Debug endpoints were temporary for troubleshooting and have been removed.
