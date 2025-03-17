from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import List
from datetime import datetime
import logging

from models.file import FileModel
from config import settings

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
