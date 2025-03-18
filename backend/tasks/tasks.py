from celery import Celery
import logging
from pathlib import Path
from typing import Optional, Dict, List
from utils.elastic import elastic_config

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
    Task to index a CSV file in Elasticsearch.
    
    Args:
        file_path: Path to the CSV file to index
        
    Returns:
        dict: A dictionary containing the indexing result
    """
    logger.info(f"Indexing CSV file at {file_path}")
    
    try:
        success, count = elastic_config.index_csv_file(file_path)
        
        if success:
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


@app.task(name='tasks.index_all_csv_files')
def index_all_csv_files(directory_path: str, pattern: str = "*.csv") -> dict:
    """
    Task to index all CSV files in a directory.
    
    Args:
        directory_path: Path to the directory containing CSV files
        pattern: Pattern to match CSV files
        
    Returns:
        dict: A dictionary containing the indexing results
    """
    logger.info(f"Indexing all CSV files in {directory_path}")
    
    try:
        # Find all CSV files
        path = Path(directory_path)
        files = list(path.glob(pattern))
        
        if not files:
            return {
                "status": "warning",
                "message": f"No CSV files found in {directory_path}",
                "directory": directory_path,
                "files_processed": 0,
                "total_documents": 0
            }
        
        # Process each file
        results = []
        total_documents = 0
        
        for file_path in files:
            # Process synchronously in this task to avoid task queue overload
            try:
                success, count = elastic_config.index_csv_file(str(file_path))
                total_documents += count
                
                results.append({
                    "file": str(file_path),
                    "success": success,
                    "count": count
                })
            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")
                results.append({
                    "file": str(file_path),
                    "success": False,
                    "error": str(e),
                    "count": 0
                })
        
        return {
            "status": "success",
            "message": f"Processed {len(files)} files, indexed {total_documents} documents",
            "directory": directory_path,
            "files_processed": len(files),
            "total_documents": total_documents,
            "results": results
        }
    except Exception as e:
        logger.error(f"Error indexing directory {directory_path}: {e}")
        return {
            "status": "error",
            "message": f"Error processing directory: {str(e)}",
            "directory": directory_path,
            "files_processed": 0,
            "total_documents": 0
        }


@app.task(name='tasks.search_elasticsearch')
def search_elasticsearch(query: str, field: Optional[str] = None, include_historical: bool = False) -> dict:
    """
    Task to search Elasticsearch.
    
    Args:
        query: Search query
        field: Optional field to search in
        include_historical: Whether to include historical indices
        
    Returns:
        dict: A dictionary containing the search results
    """
    logger.info(f"Searching Elasticsearch for '{query}'")
    
    try:
        headers, documents = elastic_config.search(
            query=query,
            field=field,
            include_historical=include_historical
        )
        
        return {
            "status": "success",
            "message": f"Found {len(documents)} results for '{query}'",
            "headers": headers,
            "data": documents
        }
    except Exception as e:
        logger.error(f"Error searching for '{query}': {e}")
        return {
            "status": "error",
            "message": f"Error searching: {str(e)}",
            "headers": [],
            "data": []
        }
