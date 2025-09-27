from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import logging

from utils.csv_utils import NEW_NETSPEED_HEADERS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from utils.path_utils import resolve_current_file, NETSPEED_TIMESTAMP_PATTERN
except Exception:  # Avoid hard failure on import cycles during startup
    resolve_current_file = None  # type: ignore
    NETSPEED_TIMESTAMP_PATTERN = None  # type: ignore


class FileModel(BaseModel):
    """Model representing a CSV file."""
    name: str
    path: str
    is_current: bool = False  # True for newest netspeed export, False for historical files
    date: Optional[datetime] = None  # For historical files, derived from file name
    format: str = "new"  # Format of the file: "new" (current standard) or "old" (legacy)

    @classmethod
    def from_path(cls, file_path: str) -> "FileModel":
        """
        Create a FileModel instance from a file path.

        Args:
            file_path: Path to the CSV file

        Returns:
            FileModel: Instance representing the file
        """
        # Import modules inside method to ensure they're available
        import os
        from pathlib import Path
        import subprocess
        import csv
        import logging

        # Create a local logger for use within this method
        local_logger = logging.getLogger(__name__)

        name = file_path.split("/")[-1]
        try:
            from pathlib import Path

            path_obj = Path(file_path)
            resolved_self = path_obj.resolve()
        except Exception:
            resolved_self = None
            path_obj = None  # type: ignore

        is_current = False
        current_candidate = None
        if callable(resolve_current_file):
            try:
                current_candidate = resolve_current_file()
            except Exception:
                current_candidate = None
        if current_candidate is not None:
            try:
                if resolved_self is not None and resolved_self == Path(current_candidate).resolve():
                    is_current = True
            except Exception:
                is_current = False
        if not is_current and name == "netspeed.csv":
            # Legacy deployments may still use fixed name
            is_current = True

        # Determine date using filename timestamp when available, otherwise filesystem metadata
        date = None
        pattern_match = NETSPEED_TIMESTAMP_PATTERN.match(name) if NETSPEED_TIMESTAMP_PATTERN else None
        if pattern_match:
            try:
                date = datetime.strptime(f"{pattern_match.group(1)}{pattern_match.group(2)}", "%Y%m%d%H%M%S")
            except Exception:
                date = None
        try:
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                try:
                    process = subprocess.run(
                        ["stat", "-c", "%w", file_path],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    creation_time_str = process.stdout.strip()
                    logging.getLogger(__name__).info(f"Raw creation time from stat: {creation_time_str}")
                    date_part = creation_time_str.split()[0]
                    if date_part and date_part != "-":
                        date = datetime.strptime(date_part, "%Y-%m-%d")
                        logging.getLogger(__name__).info(f"Successfully parsed creation date: {date}")
                    else:
                        raise ValueError("Creation time unavailable")
                except (subprocess.CalledProcessError, ValueError):
                    if date is None:
                        mtime = file_path_obj.stat().st_mtime
                        date = datetime.fromtimestamp(mtime)
                        logging.getLogger(__name__).info(f"Using modification time for {name}: {date}")
        except Exception as e:
            logging.getLogger(__name__).error(f"Error calculating date for {file_path}: {e}")
            date = None

        # Determine format based on file content or name patterns
        new_header_lower = [h.lower() for h in NEW_NETSPEED_HEADERS]
        format_type = "new"

        try:
            with open(file_path, 'r', newline='') as f:
                content = f.read()
                f.seek(0)

                delimiter = ';' if ';' in content else ','
                local_logger.debug(f"Detected delimiter '{delimiter}' for file {file_path}")

                csv_reader = csv.reader(f, delimiter=delimiter)
                first_row = next(csv_reader, [])
                normalized_first_row = [cell.strip().lstrip("\ufeff") for cell in first_row]
                header_lower = [cell.lower() for cell in normalized_first_row]

                if not normalized_first_row:
                    format_type = "new"
                elif header_lower == new_header_lower:
                    format_type = "new"
                elif len(normalized_first_row) == len(NEW_NETSPEED_HEADERS):
                    format_type = "new"
                else:
                    format_type = "old"
        except Exception as e:
            local_logger.error(f"Error detecting format for {file_path}: {e}")
            if name != "netspeed.csv":
                format_type = "old"

        return cls(
            name=name,
            path=file_path,
            is_current=is_current,
            date=date,
            format=format_type
        )
