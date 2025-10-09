import os
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import settings
from tasks.tasks import index_csv, index_all_csv_files
from utils.opensearch import opensearch_config, OpenSearchUnavailableError
from utils.archiver import archive_current_netspeed
from utils.path_utils import resolve_current_file, NETSPEED_TIMESTAMP_PATTERN


def _resolve_data_dir(data_dir: str | Path | None) -> Path:
    """Resolve the directory that should be watched for netspeed changes."""
    try:
        if isinstance(data_dir, Path):
            data_dir = str(data_dir)
    except TypeError:
        # Path is mocked in tests, assume it's not a Path
        pass

    raw_roots = getattr(settings, "_explicit_data_roots", ()) or ()
    explicit_roots = tuple(
        str(root)
        for root in raw_roots
        if isinstance(root, str) and root.strip()
    )

    chosen_path: str | None
    if data_dir:
        chosen_path = data_dir  # type: ignore
    elif explicit_roots:
        chosen_path = explicit_roots[0]
    else:
        chosen_path = getattr(settings, "CSV_FILES_DIR", "/app/data")

    if not chosen_path or not str(chosen_path).strip():
        chosen_path = "/app/data"

    try:
        candidate = Path(chosen_path).expanduser().resolve()
    except Exception:
        candidate = Path(chosen_path)

    if explicit_roots:
        allowed: list[Path] = []
        for root in explicit_roots:
            try:
                allowed.append(Path(root))
            except Exception:
                continue
        for root in allowed:
            try:
                if candidate == root or candidate.is_relative_to(root):
                    break
            except AttributeError:
                # Python <3.9 compatibility
                if candidate == root or str(candidate).startswith(f"{root}/"):
                    break
            except Exception:
                continue
        else:
            fallback = next((root for root in allowed if str(root).strip()), None)
            if fallback is not None:
                if candidate != fallback:
                    logger.info("File watcher overriding watch directory %s -> %s to honor explicit data roots", candidate, fallback)
                candidate = fallback

    return candidate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CSVFileHandler(FileSystemEventHandler):
    """Handler for monitoring CSV file changes."""

    def __init__(self, data_dir: str | None):
        self.data_dir = _resolve_data_dir(data_dir)
        current_candidate = None
        try:
            current_candidate = resolve_current_file([self.data_dir])
        except Exception:
            current_candidate = None
        if current_candidate is None:
            candidates = [
                self.data_dir / "netspeed" / "netspeed.csv",
                self.data_dir / "netspeed.csv",
            ]
            current_candidate = next((c for c in candidates if c.exists()), candidates[0])
        self.current_csv_path = Path(current_candidate)
        self.last_reindex_time = 0
        self.reindex_cooldown = 30  # 30 seconds cooldown between reindexing
        self.safety_threads = []  # Track safety net threads

    def _is_netspeed_file(self, file_path: Path) -> bool:
        """Check if the file is a netspeed CSV file."""
        try:
            if file_path.is_relative_to(self.data_dir / "archive"):
                return False
        except Exception:
            # For Python <3.9 compatibility in container, do a manual check
            archive_prefix = str(self.data_dir / "archive")
            file_str = str(file_path)
            if file_str.startswith(archive_prefix + "/") or file_str.startswith(archive_prefix + os.sep):
                return False
                return False
        name = file_path.name
        if NETSPEED_TIMESTAMP_PATTERN.match(name):
            return True
        if name == "netspeed.csv":
            return True
        if name.startswith("netspeed.csv."):
            suffix = name.split("netspeed.csv.", 1)[1]
            if suffix.endswith("_bak"):
                suffix = suffix[:-4]
            if suffix.isdigit():
                return True
        return False

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

            try:
                current_candidate = resolve_current_file([self.data_dir])
                if current_candidate and current_candidate.exists():
                    self.current_csv_path = current_candidate
            except Exception:
                pass

            # Step -1: Archive the current netspeed.csv so we keep every version
            try:
                arch = archive_current_netspeed(str(self.data_dir))
                if arch.get("status") == "success":
                    logger.info(f"Archived current file to {arch.get('path')}")
                else:
                    logger.debug(f"Archive skipped or failed: {arch}")
            except Exception as e:
                logger.debug(f"Archival step failed: {e}")

            wait_timeout = max(60.0, float(getattr(settings, "OPENSEARCH_STARTUP_TIMEOUT_SECONDS", 45)))
            wait_interval = float(getattr(settings, "OPENSEARCH_STARTUP_POLL_SECONDS", 3.0))

            try:
                opensearch_config.wait_for_availability(
                    timeout=wait_timeout,
                    interval=wait_interval,
                    reason="file_watcher_actions",
                )
            except OpenSearchUnavailableError as exc:
                logger.warning(f"OpenSearch unavailable during file watcher processing: {exc}")
                return

            # Step 0: Quickly snapshot today's stats from current netspeed.csv (best-effort)
            try:
                logger.info("Queuing snapshot of current stats for timelines (global & per-location)...")
                from tasks.tasks import snapshot_current_stats
                snapshot_current_stats.delay(str(self.data_dir))
            except Exception as e:
                logger.debug(f"Failed to queue snapshot_current_stats: {e}")

            # Also queue a richer snapshot that computes detail arrays and per-location details
            # Also queue a richer snapshot that computes detail arrays and per-location details
            try:
                logger.info("Executing detailed current stats snapshot (models by location, KEM phones, VLANs)...")
                from tasks.tasks import snapshot_current_with_details
                csv_file = str(self.current_csv_path)

                # Queue for async execution
                snapshot_current_with_details.delay(csv_file)
                logger.info("Queued detailed snapshot task")

            except Exception as e:
                logger.warning(f"Failed to execute detailed snapshot: {e}")
                try:
                    logger.info("Also queued backup snapshot task")
                except Exception as e:
                    logger.debug(f"Could not queue backup snapshot_current_with_details: {e}")

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

            # Prune completed threads
            self.safety_threads = [t for t in self.safety_threads if t.is_alive()]

            # Check concurrency limit (max 3)
            if len(self.safety_threads) >= 3:
                logger.info("Safety net thread limit reached, skipping")
                return

            # Start safety net in background thread (non-daemon, tracked)
            safety_thread = threading.Thread(target=ensure_location_stats)
            self.safety_threads.append(safety_thread)
            safety_thread.start()
            logger.info("Started safety net thread for location statistics")

        except Exception as e:
            logger.error(f"Error handling netspeed files change: {e}")


class FileWatcher:
    """File system watcher for CSV files."""

    def __init__(self, data_dir: str | None = None):
        resolved_dir = _resolve_data_dir(data_dir)
        self.data_dir = str(resolved_dir)
        self.observer = Observer()
        self.handler = CSVFileHandler(self.data_dir)

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


def start_file_watcher(data_dir: str | None = None):
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
