import os
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tasks.tasks import index_csv
from utils.opensearch import opensearch_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CSVFileHandler(FileSystemEventHandler):
    """Handler for monitoring CSV file changes."""
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.current_csv_path = self.data_dir / "netspeed.csv"
        
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Check if netspeed.csv was created/replaced
        if file_path.name == "netspeed.csv":
            logger.info(f"New netspeed.csv detected: {file_path}")
            self._handle_new_netspeed_csv(str(file_path))
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Check if netspeed.csv was modified
        if file_path.name == "netspeed.csv":
            logger.info(f"netspeed.csv modified: {file_path}")
            # Wait a moment to ensure file is completely written
            time.sleep(2)
            self._handle_new_netspeed_csv(str(file_path))
    
    def _handle_new_netspeed_csv(self, file_path: str):
        """
        Handle new or updated netspeed.csv file.
        
        Args:
            file_path: Path to the netspeed.csv file
        """
        try:
            logger.info("Processing new netspeed.csv file...")
            
            # Step 1: Delete existing netspeed.csv index to avoid stale data
            logger.info("Cleaning up existing netspeed.csv index...")
            index_name = opensearch_config.get_index_name(file_path)
            if opensearch_config.delete_index(index_name):
                logger.info(f"Successfully deleted index: {index_name}")
            else:
                logger.warning(f"Could not delete index: {index_name}")
            
            # Step 2: Trigger reindexing of the new file
            logger.info("Triggering reindexing of new netspeed.csv...")
            task = index_csv.delay(file_path)
            logger.info(f"Reindexing task started with ID: {task.id}")
            
        except Exception as e:
            logger.error(f"Error handling new netspeed.csv: {e}")


class FileWatcher:
    """File system watcher for CSV files."""
    
    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = data_dir
        self.observer = Observer()
        self.handler = CSVFileHandler(data_dir)
        
    def start(self):
        """Start watching for file changes."""
        try:
            # Ensure the data directory exists
            Path(self.data_dir).mkdir(parents=True, exist_ok=True)
            
            self.observer.schedule(self.handler, self.data_dir, recursive=False)
            self.observer.start()
            logger.info(f"File watcher started for directory: {self.data_dir}")
            
        except Exception as e:
            logger.error(f"Error starting file watcher: {e}")
            raise
    
    def stop(self):
        """Stop watching for file changes."""
        try:
            self.observer.stop()
            self.observer.join()
            logger.info("File watcher stopped")
        except Exception as e:
            logger.error(f"Error stopping file watcher: {e}")
    
    def is_alive(self):
        """Check if the file watcher is running."""
        return self.observer.is_alive()


# Global file watcher instance
file_watcher = None


def start_file_watcher(data_dir: str = "/app/data"):
    """
    Start the global file watcher.
    
    Args:
        data_dir: Directory to watch for CSV files
    """
    global file_watcher
    
    if file_watcher is None or not file_watcher.is_alive():
        file_watcher = FileWatcher(data_dir)
        file_watcher.start()
        logger.info("Global file watcher started")
    else:
        logger.info("File watcher is already running")


def stop_file_watcher():
    """Stop the global file watcher."""
    global file_watcher
    
    if file_watcher and file_watcher.is_alive():
        file_watcher.stop()
        file_watcher = None
        logger.info("Global file watcher stopped")
    else:
        logger.info("File watcher is not running")