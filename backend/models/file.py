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
            # For demonstration, detect format based on file path
            # In a real implementation, you would check the file content
            import csv
            with open(file_path, 'r') as f:
                first_row = next(csv.reader(f))
                # Check if the file has 14 columns (new format) or 11 columns (old format)
                if len(first_row) == 14:
                    format_type = "new"
                else:
                    format_type = "old"
        except Exception as e:
            # If we can't open or read the file, use a fallback detection by name
            # This is a simple heuristic that can be improved
            if name == "netspeed.csv" or name.endswith(".2"):
                # Assume that netspeed.csv and netspeed.csv.2 are in the new format
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
