from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import List
from datetime import datetime
import logging

from models.file import FileModel
from config import settings
from utils.csv_utils import read_csv_file

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
        csv_dir = Path(settings.CSV_FILES_DIR)
        
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
        csv_dir = Path(settings.CSV_FILES_DIR)
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
            "%Y-%m-%d %H:%M:%S")
        
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
        csv_dir = Path(settings.CSV_FILES_DIR)
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
