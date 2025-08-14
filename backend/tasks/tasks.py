import os
from celery import Celery
import logging
from pathlib import Path
from typing import Optional, Dict, List
from utils.opensearch import opensearch_config
from datetime import datetime
from utils.index_state import load_state, save_state, update_file_state, update_totals, is_file_current, start_active, update_active, clear_active

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
        path = Path(directory_path)
        patterns = ["netspeed.csv", "netspeed.csv.*", "netspeed.csv_bak"]
        files: List[Path] = []
        for pattern in patterns:
            glob_results = sorted(path.glob(pattern), key=lambda x: str(x))
            files.extend(glob_results)

        netspeed_files = [f for f in files if f.name.startswith("netspeed.csv") and f.name != "netspeed.csv_bak" and not f.name.endswith("_bak")]
        # Separate backup files explicitly
        backup_files = [f for f in files if f.name.endswith("_bak") or f.name == "netspeed.csv_bak"]
        # Always include all netspeed files (base + all historical), backups last
        base_files = [f for f in netspeed_files if f.name == "netspeed.csv"]
        historical_files_all = [f for f in netspeed_files if f.name != "netspeed.csv"]
        files = base_files + historical_files_all + backup_files

        logger.info(f"Found {len(files)} files matching patterns {patterns}: {[f.name for f in files]}")

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
            task_id = os.environ.get('CELERY_TASK_ID', 'manual')
            start_active(index_state, task_id, len(ordered_files))
            save_state(index_state)
        except Exception as e:
            logger.debug(f"Initial progress update failed: {e}")

        start_time = datetime.utcnow()

        for i, file_path in enumerate(ordered_files):
            logger.info(f"Processing file {i+1}/{len(ordered_files)}: {file_path}")
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
    from time import perf_counter
    t0 = perf_counter()
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

                # Only add Creation Date if it's missing from the document
                if 'Creation Date' not in doc or not doc['Creation Date']:
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
                    except Exception as e:
                        logger.warning(f"Error getting file info for {file_name}: {e}")

                # For file format, always add it if missing
                if 'File Format' not in doc:
                    try:
                        file_path = f"/app/data/{file_name}"
                        from models.file import FileModel
                        file_model = FileModel.from_path(file_path)
                        doc['File Format'] = file_model.format
                    except Exception as e:
                        logger.warning(f"Error getting file format for {file_name}: {e}")
                        doc['File Format'] = 'unknown'

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
