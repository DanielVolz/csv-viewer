import logging
from pathlib import Path
from datetime import datetime
import shutil

from utils.path_utils import get_data_root, resolve_current_file


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def archive_current_netspeed(data_dir: str | None = None) -> dict:
    """Copy the current netspeed.csv into an archive folder with a timestamped name.

    Files are written under <data_dir>/archive as netspeed_YYYY-MM-DDTHHMMSSZ.csv
    (UTC). This ensures every version is preserved even if the source file is
    overwritten daily.

    Returns a dict with status and destination path (if created).
    """
    try:
        base_dir = Path(data_dir) if data_dir else get_data_root()
        extras = [data_dir] if data_dir else None
        src = resolve_current_file(extras)
        if not src or not Path(src).exists():
            return {"status": "warning", "message": "netspeed.csv not found"}
        src_path = Path(src)

        archive_dir = base_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Use UTC timestamp with microseconds to avoid collisions
        ts = datetime.utcnow().strftime("%Y-%m-%dT%H%M%S%fZ")
        dest = archive_dir / f"netspeed_{ts}.csv"

        # Copy with metadata
        shutil.copy2(src_path, dest)
        logger.info(f"Archived netspeed to {dest}")
        return {"status": "success", "path": str(dest)}
    except Exception as e:
        logger.warning(f"Failed to archive netspeed.csv: {e}")
        return {"status": "error", "message": str(e)}


def archive_path(file_path: str, data_dir: str | None = None) -> dict:
    """Archive any given file into <data_dir>/archive using name '<basename>__<UTC>.ext'.

    Preserves metadata (mtime/atime) via copy2; returns a dict with status and dest.
    """
    try:
        src = Path(file_path)
        if not src.exists():
            return {"status": "warning", "message": f"{file_path} not found"}
        base_dir = Path(data_dir) if data_dir else get_data_root()
        archive_dir = base_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y-%m-%dT%H%M%S%fZ")
        dest = archive_dir / f"{src.name}__{ts}"
        shutil.copy2(src, dest)
        logger.info(f"Archived {src.name} -> {dest.name}")
        return {"status": "success", "path": str(dest)}
    except Exception as e:
        logger.warning(f"Failed to archive {file_path}: {e}")
        return {"status": "error", "message": str(e)}
