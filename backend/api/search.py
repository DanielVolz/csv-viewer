from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Optional
import logging
from config import settings
from tasks.tasks import search_opensearch
from celery.result import AsyncResult
from utils.opensearch import opensearch_config

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
            task = search_opensearch.delay(
                query=query,
                field=field,
                include_historical=include_historical
            )

            # Wait for task to complete (with timeout)
            # This is a synchronous operation, but the work is done by Celery
            result = task.get(timeout=10)

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
        # Submit indexing task to Celery
        task = index_all_csv_files.delay("/app/data")

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
        # Delete indices
        deleted = opensearch_config.cleanup_indices_by_pattern("netspeed_*")
        logger.info(f"Rebuild requested: deleted {deleted} indices")

        from tasks.tasks import index_all_csv_files
        task = index_all_csv_files.delay("/app/data")
        return {
            "success": True,
            "message": f"Deleted {deleted} indices, started fresh indexing",
            "deleted_indices": deleted,
            "task_id": task.id
        }
    except Exception as e:
        logger.error(f"Error rebuilding indices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rebuild indices: {e}")


@router.get("/debug/line_numbers")
async def debug_line_numbers(
    query: str = Query(..., description="Raw user fragment, can include leading +"),
    include_historical: bool = Query(False, description="Search across all netspeed_* indices") ,
    size: int = Query(25, le=200, description="Maximum sample size")
):
    """Debug helper: shows how 'Line Number' values are stored and which variants match.

    Returns sample docs with File Name + Line Number for given fragment with different plus-handling variants.
    """
    try:
        client = opensearch_config.client
        indices = opensearch_config.get_search_indices(include_historical)

        raw = query.strip()
        no_plus = raw.lstrip('+') if raw.startswith('+') else raw
        plus_variant = raw if raw.startswith('+') else f"+{raw}"

        # Build unique variants (avoid duplicates)
        variants = []
        for v in [raw, no_plus, plus_variant]:
            if v and v not in variants:
                variants.append(v)

        should = []
        for v in variants:
            should.append({"wildcard": {"Line Number": f"*{v}*"}})
            # exact term attempt
            should.append({"term": {"Line Number": v}})

        body = {
            "query": {
                "bool": {
                    "should": should,
                    "minimum_should_match": 1
                }
            },
            "_source": ["Line Number", "File Name", "MAC Address", "Creation Date"],
            "size": size
        }

        logger.info(f"[debug_line_numbers] indices={indices} body={body}")
        resp = client.search(index=indices, body=body)
        hits = resp.get('hits', {}).get('hits', [])

        docs = []
        for h in hits:
            src = h.get('_source', {})
            docs.append({
                'line_number': src.get('Line Number'),
                'file': src.get('File Name'),
                'mac': src.get('MAC Address'),
                'creation_date': src.get('Creation Date'),
                'score': h.get('_score')
            })

        return {
            'success': True,
            'query_raw': raw,
            'variants_tested': variants,
            'sample_count': len(docs),
            'documents': docs
        }
    except Exception as e:
        logger.error(f"debug_line_numbers error: {e}")
        raise HTTPException(status_code=500, detail=f"debug_line_numbers failed: {e}")


@router.get("/debug/fields")
async def debug_fields(
    query: str = Query(..., description="Search fragment"),
    fields: str = Query("Line Number,MAC Address,MAC Address 2,IP Address,Switch Hostname,Switch Port,Serial Number,Model Name", description="Comma-separated field names to test"),
    include_historical: bool = Query(False, description="Search all netspeed_* indices"),
    size: int = Query(25, le=200, description="Sample size per combined query")
):
    """Generic debug endpoint: shows how partial variants behave for selected fields.

    It builds wildcard / term / prefix clauses for each field and returns sample matching docs
    with a best-effort guess of which fields matched (simple substring check client-side).
    """
    try:
        raw = query.strip()
        field_list = [f.strip() for f in fields.split(',') if f.strip()]
        client = opensearch_config.client
        indices = opensearch_config.get_search_indices(include_historical)

        def build_variants(val: str):
            base = [val]
            # plus handling
            if val.startswith('+'):
                base.append(val.lstrip('+'))
            else:
                base.append(f"+{val}")
            # case variants for alpha content
            if any(c.isalpha() for c in val):
                base.extend([val.lower(), val.upper()])
            # dedupe preserve order
            out = []
            seen = set()
            for v in base:
                if v and v not in seen:
                    seen.add(v)
                    out.append(v)
            return out

        all_variants = build_variants(raw)

        should = []
        for field_name in field_list:
            for variant in all_variants:
                should.append({"wildcard": {field_name: f"*{variant}*"}})
                should.append({"term": {field_name: variant}})
                # prefix only if variant length > 1
                if len(variant) > 1:
                    should.append({"prefix": {field_name: variant}})

        body = {
            "query": {"bool": {"should": should, "minimum_should_match": 1}},
            "_source": list({*field_list, "File Name", "Creation Date"}),
            "size": size
        }

        logger.info(f"[debug_fields] indices={indices} body={body}")
        resp = client.search(index=indices, body=body)
        hits = resp.get('hits', {}).get('hits', [])

        docs = []
        for h in hits:
            src = h.get('_source', {})
            matched_fields = []
            for fld in field_list:
                val = str(src.get(fld, ''))
                for variant in all_variants:
                    if variant and variant.lower() in val.lower():
                        matched_fields.append(fld)
                        break
            docs.append({
                'file': src.get('File Name'),
                'creation_date': src.get('Creation Date'),
                'score': h.get('_score'),
                'matched_fields': matched_fields,
                'data': {k: src.get(k) for k in field_list if k in src}
            })

        return {
            'success': True,
            'query': raw,
            'variants_tested': all_variants,
            'fields_tested': field_list,
            'total_docs': len(docs),
            'documents': docs
        }
    except Exception as e:
        logger.error(f"debug_fields error: {e}")
        raise HTTPException(status_code=500, detail=f"debug_fields failed: {e}")
