import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define headers formats
NEW_HEADERS = [
    "IP Address", "Line Number", "Serial Number", "Model Name", "MAC Address",
    "MAC Address 2", "Subnet Mask", "Voice VLAN", "Speed 1", "Speed 2",
    "Switch Hostname", "Switch Port", "Speed 3", "Speed 4"
]

OLD_HEADERS = [
    "IP Address", "Serial Number", "Model Name", "MAC Address", "MAC Address 2",
    "Speed 1", "Speed 2", "Switch Hostname", "Switch Port", "Speed 3", "Speed 4"
]


# Define the desired display order for columns
DESIRED_ORDER = [
    "#", "File Name", "Creation Date", "IP Address", "Line Number", "MAC Address",
    "Subnet Mask", "Voice VLAN", "Switch Hostname", "Switch Port",
    "Serial Number", "Model Name"
]


def read_csv_file(file_path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Read a CSV file and return headers and rows as dictionaries.

    Detects whether the file is in the old or new format and handles accordingly.
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        Tuple containing (headers, rows)
        - headers: List of column names
        - rows: List of dictionaries where keys are headers and values are cell values
    """
    try:
        rows = []
        
        # Get file information
        file_name = os.path.basename(file_path)
        file_stat = os.stat(file_path)
        creation_date = datetime.fromtimestamp(
            file_stat.st_ctime
        ).strftime('%Y-%m-%d %H:%M:%S')
        
        with open(file_path, 'r') as csv_file:
            csv_reader = csv.reader(csv_file)
            
            # Read all rows as we need to count columns to determine format
            all_rows = list(csv_reader)
            
            # Determine format based on number of columns
            if len(all_rows) == 0:
                logger.warning(f"Empty file: {file_path}")
                return DESIRED_ORDER, []
            
            # Detect format based on number of columns in first data row
            if len(all_rows[0]) == 14:  # New format has 14 columns
                file_headers = NEW_HEADERS
            else:  # Old format has 11 columns
                file_headers = OLD_HEADERS
            
            # Process rows
            for idx, row in enumerate(all_rows, 1):  # Start counting from 1
                if len(row) == len(file_headers):
                    # Create a dictionary with the appropriate headers
                    row_dict = dict(zip(file_headers, row))
                    
                    # Add file name, creation date, and row number
                    row_dict["File Name"] = file_name
                    row_dict["Creation Date"] = creation_date
                    # Add row number as string to match other values
                    row_dict["#"] = str(idx)
                    
                    rows.append(row_dict)
                else:
                    logger.warning(
                        f"Skipping row in {file_path} due to column mismatch."
                    )
        
        logger.info(f"Successfully read {len(rows)} rows from {file_path}")
        return DESIRED_ORDER, rows
    
    except Exception as e:
        logger.error(f"Error reading CSV file {file_path}: {e}")
        return [], []


def search_field_in_files(
    directory_path: str,
    search_term: str,
    field_name: Optional[str] = None,
    include_historical: bool = False
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Search for a term in any field or a specific field in CSV files.
    
    Args:
        directory_path: Path to the directory containing CSV files
        search_term: Term to search for
        field_name: Optional specific field name to search in
            (if None, searches all fields)
        include_historical: Whether to include historical files
        
    Returns:
        Tuple containing (headers, matching_rows)
    """
    try:
        dir_path = Path(directory_path)
        
        if not dir_path.exists() or not dir_path.is_dir():
            logger.error(
                f"Directory {directory_path} does not exist or is not a directory"
            )
            return [], []
        
        # List of files to search
        files_to_search = []
        
        # Current file
        current_file = dir_path / "netspeed.csv"
        if current_file.exists():
            files_to_search.append(current_file)
        
        # Historical files if requested
        if include_historical:
            historical_pattern = "netspeed.csv.*"
            for file_path in dir_path.glob(historical_pattern):
                files_to_search.append(file_path)
        
        logger.info(
            f"Searching for term '{search_term}' in {len(files_to_search)} files"
        )
        
        # Normalize the search term (lowercase)
        normalized_search_term = search_term.lower()
        
        # Store matching rows
        matching_rows = []
        headers = []
        
        # Search each file
        for file_path in files_to_search:
            file_headers, rows = read_csv_file(str(file_path))
            
            # Store headers from first file (should be consistent across files)
            if not headers and file_headers:
                headers = file_headers
            
            # Search for term in each row
            for row in rows:
                # If a specific field is provided, only search that field
                if field_name:
                    if (field_name in row and row[field_name] and 
                            normalized_search_term in str(row[field_name]).lower()):
                        matching_rows.append(row)
                # Otherwise, search all fields
                else:
                    for key, value in row.items():
                        if value and normalized_search_term in str(value).lower():
                            matching_rows.append(row)
                            break  # Found in one field, no need to check others
        
        logger.info(
            f"Found {len(matching_rows)} matches for term '{search_term}'"
        )
        
        # Return headers and matching rows
        if current_file.exists() and not headers:
            headers, _ = read_csv_file(str(current_file))
        
        return headers, matching_rows
    
    except Exception as e:
        logger.error(
            f"Error searching in directory {directory_path}: {e}"
        )
        return [], []
