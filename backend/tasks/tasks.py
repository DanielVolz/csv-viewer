import os
from celery import Celery
import logging
from pathlib import Path
from typing import Optional, Dict, List
from utils.opensearch import opensearch_config

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
def index_all_csv_files(directory_path: str) -> dict:
    """
    Task to index all CSV files in a directory.
    
    Args:
        directory_path: Path to the directory containing CSV files
        
    Returns:
        dict: A dictionary containing the indexing results
    """
    logger.info(f"Indexing all CSV files in {directory_path}")
    
    try:
        # Get the maximum number of netspeed files to index from the environment variable
        max_netspeed_files = int(os.environ.get("NETSPEED_FILES", "2"))
        logger.info(f"Maximum netspeed files to index: {max_netspeed_files}")

        # Find all CSV files including historical ones
        path = Path(directory_path)

        # Use a list comprehension with multiple patterns to find all relevant files
        patterns = ["netspeed.csv", "netspeed.csv.*", "netspeed.csv_bak"]
        files = []
        for pattern in patterns:
            # Sort the glob results to ensure consistent ordering
            glob_results = sorted(path.glob(pattern), key=lambda x: str(x))
            files.extend(glob_results)

        # Filter netspeed.csv.* files based on NETSPEED_FILES
        netspeed_files = [f for f in files if "netspeed.csv" in str(f) and "netspeed.csv_bak" not in str(f)]
        limited_netspeed_files = netspeed_files[:max_netspeed_files]

        # Add back the netspeed.csv_bak files
        other_files = [f for f in files if "netspeed.csv" not in str(f) or "netspeed.csv_bak" in str(f)]
        files = limited_netspeed_files + other_files

        logger.info(f"Found {len(files)} files matching patterns: {patterns}")

        if not files:
            return {
                "status": "warning",
                "message": f"No CSV files found in {directory_path}",
                "directory": directory_path,
                "files_processed": 0,
                "total_documents": 0,
            }
        
        # Process files in optimized order: current file first, then historical files
        current_files = [f for f in files if f.name == "netspeed.csv"]
        historical_files = [f for f in files if f.name != "netspeed.csv"]
        ordered_files = current_files + sorted(historical_files, key=lambda x: x.name)
        
        # Process each file
        results = []
        total_documents = 0
        
        for i, file_path in enumerate(ordered_files):
            logger.info(f"Processing file {i+1}/{len(ordered_files)}: {file_path}")
            try:
                success, count = opensearch_config.index_csv_file(str(file_path))
                total_documents += count
                
                results.append({
                    "file": str(file_path),
                    "success": success,
                    "count": count
                })
                logger.info(f"Completed {file_path}: {count} documents indexed")
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


@app.task(name='tasks.search_opensearch')
def search_opensearch(query: str, field: Optional[str] = None, include_historical: bool = False) -> dict:
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
    
    try:
        headers, documents = opensearch_config.search(
            query=query,
            field=field,
            include_historical=include_historical
        )
        
        # Process documents to ensure file creation dates are included
        for doc in documents:
            # Check if the document has a file name
            if 'File Name' in doc:
                file_name = doc['File Name']
                # Create a file model to get the date info
                try:
                    file_path = f"/app/data/{file_name}"
                    # Get a complete FileModel to get the correct date
                    from models.file import FileModel
                    file_model = FileModel.from_path(file_path)
                    
                    # Use the date from FileModel which already handles all the details correctly
                    if file_model.date:
                        doc['Creation Date'] = file_model.date.strftime('%Y-%m-%d')
                    else:
                        # Fallback if date is not available
                        import subprocess
                        from pathlib import Path
                        from datetime import datetime
                        
                        try:
                            # Match the same stat command used in FileModel.from_path
                            process = subprocess.run(
                                ["stat", "-c", "%w", file_path],
                                capture_output=True,
                                text=True,
                                check=True
                            )
                            creation_time_str = process.stdout.strip()
                            # Extract just the date part (YYYY-MM-DD) from the timestamp
                            date_part = creation_time_str.split()[0]
                            doc['Creation Date'] = date_part
                        except subprocess.CalledProcessError:
                            # Fallback to modification time if stat fails
                            file_path_obj = Path(file_path)
                            mtime = file_path_obj.stat().st_mtime
                            date = datetime.fromtimestamp(mtime)
                            doc['Creation Date'] = date.strftime('%Y-%m-%d')
                    
                    # For file format, still use FileModel
                    from models.file import FileModel
                    file_model = FileModel.from_path(file_path)
                    doc['File Format'] = file_model.format
                except Exception as e:
                    logger.warning(f"Error getting file info for {file_name}: {e}")
        
        # Apply same column filtering as Preview API for consistency
        from utils.csv_utils import filter_display_columns
        
        # Filter headers and data to match display preferences
        filtered_headers, filtered_documents = filter_display_columns(headers, documents)
        
        return {
            "status": "success",
            "message": f"Found {len(filtered_documents)} results for '{query}'",
            "headers": filtered_headers,
            "data": filtered_documents
        }
    except Exception as e:
        logger.error(f"Error searching for '{query}': {e}")
        return {
            "status": "error",
            "message": f"Error searching: {str(e)}",
            "headers": [],
            "data": []
        }
