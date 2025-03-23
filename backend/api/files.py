from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from typing import List
from datetime import datetime
import logging

from models.file import FileModel
from config import settings
from utils.csv_utils import read_csv_file
from tasks.tasks import index_all_csv_files, app
from celery import current_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/files",
    tags=["files"]
)


@router.get("/", response_model=List[FileModel])
async def list_files():
    """
    List all available netspeed CSV files.
    Returns them sorted with most recent (netspeed.csv) first.
    """
    try:
        # Get path to CSV files directory
        csv_dir = Path("/app/data")
        
        # List all netspeed CSV files
        files = []
        if csv_dir.exists():
            for file_path in csv_dir.glob("netspeed.csv*"):
                files.append(FileModel.from_path(str(file_path)))
        
        # Sort files: current first, then by date descending
        files.sort(
            key=lambda f: (not f.is_current, f.date or datetime.max),
            reverse=False
        )
        
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
    
    Returns:
        Dictionary with creation date and line count
    """
    try:
        # Get path to current CSV file
        csv_dir = Path("/app/data")
        current_file = csv_dir / "netspeed.csv"
        
        if not current_file.exists():
            return {
                "success": False,
                "message": "Current netspeed.csv file not found",
                "date": None,
                "line_count": 0
            }
        
        # Get file creation date
        creation_time = current_file.stat().st_mtime
        creation_date = datetime.fromtimestamp(creation_time).strftime(
            "%Y-%m-%d")
        
        # Count lines (subtract 1 for header)
        with open(current_file, 'r') as f:
            line_count = sum(1 for _ in f) - 1
        
        result = {
            "success": True,
            "message": "Netspeed.csv file information retrieved successfully",
            "date": creation_date,
            "line_count": line_count
        }
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Error getting netspeed file info: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get netspeed file information"
        )


@router.get("/preview")
async def preview_current_file(limit: int = 25):
    """
    Get a preview of the current netspeed.csv file (first N entries).
    
    Args:
        limit: Maximum number of entries to return (default 25)
        
        Returns:
        Dictionary with headers and preview rows
    """
    try:
        # Get path to current CSV file
        csv_dir = Path("/app/data")
        current_file = csv_dir / "netspeed.csv"
        
        if not current_file.exists():
            return {
                "success": False,
                "message": "Current netspeed.csv file not found",
                "headers": [],
                "data": []
            }
        
        # Read CSV file
        headers, rows = read_csv_file(str(current_file))
        
        # Limit number of rows
        preview_rows = rows[:limit]
        
        return {
            "success": True,
            "message": (f"Showing first {len(preview_rows)} entries of "
                        f"{len(rows)} total"),
            "headers": headers,
            "data": preview_rows
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


@router.get("/download/{filename}")
async def download_file(filename: str):
    """
    Download a CSV file by name.
    
    Args:
        filename: Name of the file to download (e.g., netspeed.csv, netspeed.csv.1)
        
    Returns:
        The file for download
    """
    try:
        # Get path to CSV files directory
        csv_dir = Path("/app/data")
        file_path = csv_dir / filename
        
        # Check if file exists
        if not file_path.exists():
            logger.error(f"File not found: {filename}")
            raise HTTPException(
                status_code=404,
                detail=f"File {filename} not found"
            )
        
        # Return file as download response
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="text/csv"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {str(e)}"
        )
