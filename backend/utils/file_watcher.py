import os
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tasks.tasks import index_csv, index_all_csv_files
from utils.opensearch import opensearch_config
from utils.archiver import archive_current_netspeed

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CSVFileHandler(FileSystemEventHandler):
    """Handler for monitoring CSV file changes."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        # Prefer nested layout (/app/data/netspeed/netspeed.csv) then flat fallback
        candidates = [
            self.data_dir / "netspeed" / "netspeed.csv",
            self.data_dir / "netspeed.csv",
        ]
        self.current_csv_path = next((c for c in candidates if c.exists()), candidates[0])
        self.last_reindex_time = 0
        self.reindex_cooldown = 30  # 30 seconds cooldown between reindexing

    def _is_netspeed_file(self, file_path: Path) -> bool:
        """Check if the file is a netspeed CSV file."""
        # Ignore anything inside the archive dir
        try:
            if file_path.is_relative_to(self.data_dir / "archive"):
                return False
        except Exception:
            # For Python <3.9 compatibility in container, do a manual check
            if str(self.data_dir / "archive") in str(file_path):
                return False
        return (
            file_path.name == "netspeed.csv" or
            (
                file_path.name.startswith("netspeed.csv.") and
                file_path.suffix == '' and  # netspeed.csv.0, .1, etc. have no extension
                file_path.name.replace("netspeed.csv.", "").isdigit()
            )
        )

    def _should_trigger_reindex(self) -> bool:
        """Check if we should trigger reindexing (cooldown check)."""
        current_time = time.time()
        if current_time - self.last_reindex_time > self.reindex_cooldown:
            self.last_reindex_time = current_time
            return True
        return False

    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        file_path = Path(str(event.src_path))
        # Check if any netspeed file was created
        if self._is_netspeed_file(file_path):
            logger.info(f"New netspeed file detected: {file_path}")
            if self._should_trigger_reindex():
                self._handle_netspeed_files_change("created", str(file_path))

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        file_path = Path(str(event.src_path))
        # Check if any netspeed file was modified
        if self._is_netspeed_file(file_path):
            logger.info(f"netspeed file modified: {file_path}")
            # Wait a moment to ensure file is completely written
            time.sleep(2)
            if self._should_trigger_reindex():
                self._handle_netspeed_files_change("modified", str(file_path))

    def on_moved(self, event):
        """Handle file move/rename events."""
        if event.is_directory:
            return
        src_path = Path(str(event.src_path))
        dest_path = Path(str(event.dest_path))
        # Check if any netspeed file was moved/renamed
        if (self._is_netspeed_file(src_path) or self._is_netspeed_file(dest_path)):
            logger.info(f"netspeed file moved/renamed: {src_path} -> {dest_path}")
            if self._should_trigger_reindex():
                self._handle_netspeed_files_change("moved", f"{src_path} -> {dest_path}")

    def on_deleted(self, event):
        """Handle file deletion events."""
        if event.is_directory:
            return
        file_path = Path(str(event.src_path))
        # Check if any netspeed file was deleted
        if self._is_netspeed_file(file_path):
            logger.info(f"netspeed file deleted: {file_path}")
            if self._should_trigger_reindex():
                self._handle_netspeed_files_change("deleted", str(file_path))

    def _handle_netspeed_files_change(self, event_type: str, file_info: str):
        """
        Handle changes to netspeed files by triggering full reindexing.

        Args:
            event_type: Type of file system event (created, modified, moved, deleted)
            file_info: Information about the file(s) involved
        """
        try:
            logger.info(f"Processing netspeed files change ({event_type}): {file_info}")

            # Step -1: Archive the current netspeed.csv so we keep every version
            try:
                arch = archive_current_netspeed(str(self.data_dir))
                if arch.get("status") == "success":
                    logger.info(f"Archived current file to {arch.get('path')}")
                else:
                    logger.debug(f"Archive skipped or failed: {arch}")
            except Exception as e:
                logger.debug(f"Archival step failed: {e}")

            # Step 0: Quickly snapshot today's stats from current netspeed.csv (best-effort)
            try:
                logger.info("Queuing snapshot of current stats for timelines (global & per-location)...")
                from tasks.tasks import snapshot_current_stats
                snapshot_current_stats.delay(str(self.data_dir))
            except Exception as e:
                logger.debug(f"Failed to queue snapshot_current_stats: {e}")

            # Also queue a richer snapshot that computes detail arrays and per-location details
            try:
                logger.info("Executing detailed current stats snapshot (models by location, KEM phones, VLANs)...")
                from tasks.tasks import snapshot_current_with_details
                csv_file = str(self.current_csv_path)

                # Execute inline instead of queuing to ensure it runs immediately
                logger.info("Running detailed snapshot inline for immediate execution")
                result = snapshot_current_with_details(csv_file)
                logger.info(f"Detailed snapshot result: {result}")

                # Also try to queue for backup (best effort)
                try:
                    snapshot_current_with_details.delay(csv_file)
                    logger.info("Also queued backup snapshot task")
                except Exception as e:
                    logger.debug(f"Could not queue backup snapshot_current_with_details: {e}")

            except Exception as e:
                logger.warning(f"Failed to execute detailed snapshot: {e}")

            # Invalidate in-process stats caches so UI sees changes immediately
            try:
                from api.stats import invalidate_caches as _invalidate
                _invalidate(f"file watcher: {event_type}")
            except Exception:
                pass

            # Step 1: Clean up all existing netspeed indices
            logger.info("Cleaning up all existing netspeed indices...")

            # Delete all netspeed_* indices
            try:
                indices_deleted = opensearch_config.cleanup_indices_by_pattern("netspeed_*")
                logger.info(f"Successfully cleaned up {indices_deleted} netspeed indices")
            except Exception as e:
                logger.warning(f"Error cleaning up indices: {e}")

            # Step 2: Trigger full reindexing of all CSV files
            logger.info("Triggering full reindexing of all netspeed files...")
            task = index_all_csv_files.delay(str(self.data_dir))
            logger.info(f"Full reindexing task started with ID: {task.id}")

            # Step 3: Safety net - ensure location statistics are created after a delay
            import threading
            import time

            def ensure_location_stats():
                try:
                    # Wait for indexing to potentially complete
                    time.sleep(10)
                    logger.info("Safety net: Ensuring location statistics are created...")

                    from tasks.tasks import snapshot_current_with_details
                    from datetime import datetime

                    current_csv = str(self.current_csv_path)
                    today_str = datetime.now().strftime('%Y-%m-%d')

                    # Execute inline to guarantee execution
                    safety_result = snapshot_current_with_details(file_path=current_csv, force_date=today_str)
                    logger.info(f"Safety net location statistics result: {safety_result}")

                    # Final cache invalidation
                    try:
                        from api.stats import invalidate_caches as _invalidate
                        _invalidate("safety net location stats")
                        logger.info("Safety net cache invalidation completed")
                    except Exception as cache_e:
                        logger.debug(f"Safety net cache invalidation failed: {cache_e}")

                except Exception as safety_e:
                    logger.warning(f"Safety net location statistics creation failed: {safety_e}")

            # Start safety net in background thread
            safety_thread = threading.Thread(target=ensure_location_stats, daemon=True)
            safety_thread.start()
            logger.info("Started safety net thread for location statistics")

        except Exception as e:
            logger.error(f"Error handling netspeed files change: {e}")


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

            # Watch base directory recursively so nested netspeed/ and history/netspeed are captured
            self.observer.schedule(self.handler, self.data_dir, recursive=True)
            self.observer.start()
            logger.info(f"File watcher started (recursive) for directory: {self.data_dir}")

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
