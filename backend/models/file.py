from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class FileModel(BaseModel):
    """Model representing a CSV file."""
    name: str
    path: str
    is_current: bool = False  # True for netspeed.csv, False for historical files
    date: Optional[datetime] = None  # For historical files, derived from file name
    format: str = "old"  # Format of the file: "new" (14 columns) or "old" (11 columns)
    
    @classmethod
    def from_path(cls, file_path: str) -> "FileModel":
        """
        Create a FileModel instance from a file path.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            FileModel: Instance representing the file
        """
        name = file_path.split("/")[-1]
        is_current = name == "netspeed.csv"
        
        # Get date for all files
        date = None
        try:
            import os
            from pathlib import Path
            
            # For all files, try to get the actual modification time
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                mtime = file_path_obj.stat().st_mtime
                date = datetime.fromtimestamp(mtime)
            
            # If modification time exists but for files with special naming patterns,
            # we might want to use calculated dates instead in some cases
            if name.startswith("netspeed.csv.") and name[13:].isdigit():
                try:
                    days_ago = int(name.split(".")[-1])
                    date = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    # Subtract days to get the file's date
                    date = date.fromtimestamp(
                        date.timestamp() - (days_ago * 24 * 60 * 60)
                    )
                except (ValueError, IndexError):
                    pass
        except Exception:
            # If any error occurs, just leave date as None
            pass
        
        # Determine format based on file content or name patterns
        # Default to old format
        format_type = "old"
        
        try:
            # Use a consistent approach for all files
            import csv
            import logging
            
            logger = logging.getLogger(__name__)
            
            with open(file_path, 'r') as f:
                # First read content to detect delimiter
                content = f.read()
                f.seek(0)  # Reset file pointer to start
                
                # Detect if file uses semicolons
                delimiter = ';' if ';' in content else ','
                logger.info(f"Detected delimiter '{delimiter}' for file {file_path}")
                
                # Parse with the detected delimiter
                csv_reader = csv.reader(f, delimiter=delimiter)
                # Read up to 5 rows to determine format
                rows = []
                for _ in range(5):
                    try:
                        rows.append(next(csv_reader))
                    except StopIteration:
                        break
                
                if not rows:
                    # Empty file, use fallback
                    if name == "netspeed.csv":
                        format_type = "new"  # Assume current file is new format
                    else:
                        format_type = "old"
                else:
                    # Log for debugging
                    for i, row in enumerate(rows[:2]):
                        logger.info(f"Row {i} in {name} has {len(row)} columns")
                    
                    # Check if any rows have 14 columns (new format)
                    new_format_count = sum(1 for row in rows if len(row) == 14)
                    logger.info(f"New format count for {name}: {new_format_count}/{len(rows)}")
                    
                    if new_format_count > 0:  # If any row has 14 columns
                        format_type = "new"
                    else:
                        format_type = "old"
        except Exception as e:
            # Log the exception for debugging
            import logging
            logging.getLogger(__name__).error(f"Error detecting format for {file_path}: {e}")
            # If we can't open or read the file, use a fallback detection by name
            if name == "netspeed.csv":
                # Assume that current netspeed.csv is in the new format
                format_type = "new"
            else:
                format_type = "old"
        
        return cls(
            name=name,
            path=file_path,
            is_current=is_current,
            date=date,
            format=format_type
        )
