from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Optional
import logging
from config import settings
from tasks.tasks import search_opensearch
from celery.result import AsyncResult

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
                    "data": result["data"]
                }
            else:
                return {
                    "success": False,
                    "message": result["message"],
                    "headers": result.get("headers", []),
                    "data": []
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
        task = index_all_csv_files.delay(settings.CSV_FILES_DIR)
        
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
