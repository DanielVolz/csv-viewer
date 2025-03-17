from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Optional, List, Any
import logging
from config import settings
from utils.csv_utils import search_mac_address_in_files

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
    mac_address: Optional[str] = Query(None, description="MAC address to search for"),
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
    Search netspeed CSV files.
    
    Args:
        query: General search term
        mac_address: Specific MAC address to search for
        include_historical: If True, search all files. If False, only current.
        field: Optional field name to limit search to
        
    Returns:
        Dictionary with search results
    """
    try:
        # Log search request
        logger.info(
            f"Search request - query: {query}, mac_address: {mac_address}, "
            f"include_historical: {include_historical}, field: {field}"
        )
        
        # MAC address search
        if mac_address:
            headers, result = search_mac_address_in_files(
                settings.CSV_FILES_DIR,
                mac_address,
                include_historical
            )
            
            if result:
                return {
                    "success": True,
                    "message": f"Found MAC address {mac_address}",
                    "headers": headers,
                    "data": result
                }
            else:
                return {
                    "success": False,
                    "message": f"MAC address {mac_address} not found",
                    "headers": headers,
                    "data": None
                }
        
        # General search (stub)
        elif query:
            return {
                "message": "General search endpoint stub",
                "parameters": {
                    "query": query,
                    "include_historical": include_historical,
                    "field": field
                }
            }
        
        # No search parameters provided
        else:
            return {
                "success": False,
                "message": "Please provide either 'query' or 'mac_address' parameter"
            }
        
    except Exception as e:
        logger.error(f"Error during search: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to perform search"
        )
