import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define base headers for different known formats (without Speed columns)
KNOWN_HEADERS = {
    11: [  # OLD format
        "IP Address", "Serial Number", "Model Name", "MAC Address", "MAC Address 2",
        "Switch Hostname", "Switch Port"
    ],
    14: [  # NEW format  
        "IP Address", "Line Number", "Serial Number", "Model Name", "MAC Address",
        "MAC Address 2", "Subnet Mask", "Voice VLAN", "Switch Hostname", "Switch Port"
    ]
}

# Define the desired display order for columns (what Frontend should show)
DESIRED_ORDER = [
    "#", "File Name", "Creation Date", "IP Address", "Line Number", "MAC Address",
    "MAC Address 2", "Subnet Mask", "Voice VLAN", "Switch Hostname", "Switch Port",
    "Serial Number", "Model Name"
]


def generate_headers(column_count: int) -> List[str]:
    """
    Generate headers for a CSV file based on column count.
    
    Args:
        column_count: Number of columns in the CSV file
        
    Returns:
        List of header names
    """
    # Check if we have predefined headers for this column count
    if column_count in KNOWN_HEADERS:
        return KNOWN_HEADERS[column_count].copy()
    
    # For unknown column counts, use known headers as base and extend
    base_headers = []
    
    # Use the largest known format as base
    if column_count >= 14:
        base_headers = KNOWN_HEADERS[14].copy()
    elif column_count >= 11:
        base_headers = KNOWN_HEADERS[11].copy()
    else:
        # For very small column counts, create generic headers
        base_headers = []
    
    # Extend with generic column names if needed
    while len(base_headers) < column_count:
        base_headers.append(f"Column {len(base_headers) + 1}")
    
    # Truncate if we have too many headers
    return base_headers[:column_count]


def filter_display_columns(headers: List[str], data: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Filter headers and data to show only desired columns in frontend.
    
    Args:
        headers: List of all available headers
        data: List of data dictionaries
        
    Returns:
        Tuple of (filtered_headers, filtered_data)
    """
    # Filter headers to only include desired columns
    display_headers = []
    for header in DESIRED_ORDER:
        if header in headers:
            display_headers.append(header)
    
    # Filter data to only include displayed columns
    filtered_data = []
    for row in data:
        filtered_row = {}
        for header in display_headers:
            if header in row:
                filtered_row[header] = row[header]
        filtered_data.append(filtered_row)
    
    return display_headers, filtered_data


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
        # Format the date to match the OpenSearch mapping format (yyyy-MM-dd)
        # This will remove any time component that may cause parsing issues
        creation_date = datetime.fromtimestamp(
            file_stat.st_ctime
        ).strftime('%Y-%m-%d')
        
        # Log the formatted date for debugging
        logger.info(f"Formatted date for {file_path}: {creation_date}")
        
        # First try with semicolon delimiter, then comma if needed
        all_rows = []
        
        with open(file_path, 'r') as csv_file:
            content = csv_file.read()
            csv_file.seek(0)  # Reset file pointer to start
            
            # Detect if file uses semicolons
            delimiter = ';' if ';' in content else ','
            logger.info(f"Detected delimiter '{delimiter}' for file {file_path}")
            
            # Custom CSV reader that handles trailing delimiters
            class TrailingDelimiterReader:
                def __init__(self, csv_file, delimiter):
                    self.reader = csv.reader(csv_file, delimiter=delimiter)
                    self.delimiter = delimiter
                
                def __iter__(self):
                    return self
                
                def __next__(self):
                    row = next(self.reader)
                    # If the last element is empty and there was a trailing delimiter,
                    # remove the last element
                    if row and row[-1] == '':
                        # Check if the original line ended with a delimiter by reconstructing it
                        original_line = self.delimiter.join(row)
                        if original_line.endswith(self.delimiter):
                            return row[:-1]
                    return row
            
            # Create the custom reader and process all rows
            reader = TrailingDelimiterReader(csv_file, delimiter)
            all_rows = list(reader)
            
            # Determine format based on number of columns
            if len(all_rows) == 0:
                logger.warning(f"Empty file: {file_path}")
                return DESIRED_ORDER, []
            
            # Detect column count from first few data rows
            num_rows_to_check = min(5, len(all_rows))  # Check up to 5 rows
            
            # Find the most common column count
            column_counts = [len(row) for row in all_rows[:num_rows_to_check] if len(row) > 0]
            
            if not column_counts:
                logger.warning(f"No valid rows found in {file_path}")
                return DESIRED_ORDER, []
            
            # Use the most common column count
            most_common_count = max(set(column_counts), key=column_counts.count)
            
            # Log the actual column counts for debugging
            for i, row in enumerate(all_rows[:num_rows_to_check]):
                logger.info(f"Row {i+1} in {file_path} has {len(row)} columns")
            
            logger.info(f"Detected {most_common_count} columns for {file_path}")
            
            # Generate headers based on detected column count
            file_headers = generate_headers(most_common_count)
            logger.info(f"Generated headers for {file_path}: {file_headers}")
            
            # Process rows
            for idx, row in enumerate(all_rows, 1):  # Start counting from 1
                # Skip empty rows
                if len(row) == 0:
                    logger.warning(f"Skipping empty row {idx} in {file_path}")
                    continue
                
                # Handle rows with different column counts gracefully
                processed_row = row.copy()
                
                # If row has fewer columns than expected, pad with empty strings
                if len(row) < len(file_headers):
                    processed_row = row + [''] * (len(file_headers) - len(row))
                    logger.info(
                        f"Row {idx} in {file_path} has {len(row)} columns, expected {len(file_headers)}. Padded with empty values."
                    )
                
                # If row has more columns than expected, extend headers dynamically
                elif len(row) > len(file_headers):
                    # Extend headers for this file to accommodate extra columns
                    extra_columns_needed = len(row) - len(file_headers)
                    for i in range(extra_columns_needed):
                        file_headers.append(f"Column {len(file_headers) + 1}")
                    
                    logger.info(
                        f"Row {idx} in {file_path} has {len(row)} columns, expected {len(file_headers) - extra_columns_needed}. Extended headers to accommodate extra columns."
                    )
                    processed_row = row  # Use the full row as-is
                
                # Create a dictionary with the appropriate headers
                row_dict = dict(zip(file_headers, processed_row))
                
                # Add file name, creation date, and row number
                row_dict["File Name"] = file_name
                row_dict["Creation Date"] = creation_date  # Make sure this has only the date part
                # Add row number as string to match other values
                row_dict["#"] = str(idx)
                
                # Filter row to only include desired columns for consistent data structure
                filtered_row = {}
                for header in DESIRED_ORDER:
                    if header in row_dict:
                        filtered_row[header] = row_dict[header]
                
                rows.append(filtered_row)
        
        logger.info(f"Successfully read {len(rows)} rows from {file_path}")
        
        # Create headers list for frontend display (filtered for known columns only)
        if rows:
            # Get all unique headers from the rows
            all_headers = set()
            for row in rows:
                all_headers.update(row.keys())
            
            # Build final headers list with only desired columns (for frontend display)
            display_headers = []
            for header in DESIRED_ORDER:
                if header in all_headers:
                    display_headers.append(header)
            
            # Note: We don't include "Column X" headers in frontend display
            # But they remain in the data for search functionality
            
            return display_headers, rows
        else:
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
        
        # Initialize current_file reference
        current_file = dir_path / "netspeed.csv"
        
        # Add files to search based on include_historical flag
        if include_historical:
            # Add current file
            if current_file.exists():
                files_to_search.append(current_file)
            
            # Add historical files
            historical_pattern = "netspeed.csv.*"
            for file_path in dir_path.glob(historical_pattern):
                files_to_search.append(file_path)
        else:
            # Only add current file when not including historical files
            if current_file.exists():
                files_to_search.append(current_file)
        
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
