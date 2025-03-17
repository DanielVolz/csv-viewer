import csv
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def read_csv_file(file_path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Read a CSV file and return headers and rows as dictionaries.
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        Tuple containing (headers, rows)
            headers: List of column names
            rows: List of dictionaries where keys are headers and values are cell values
    """
    try:
        rows = []
        headers = []
        
        with open(file_path, 'r') as csv_file:
            csv_reader = csv.reader(csv_file)
            
            # Get headers (first row)
            headers_line = next(csv_reader, [])
            
            # Clean up headers - handle comment in header row
            headers = []
            for header in headers_line:
                # Strip any comment from the last header
                if '#' in header and headers_line.index(header) == len(headers_line) - 1:
                    header = header.split('#')[0].strip()
                headers.append(header)
            
            # Parse rows
            for row in csv_reader:
                if len(row) == len(headers):
                    row_dict = dict(zip(headers, row))
                    rows.append(row_dict)
                else:
                    logger.warning(f"Skipping row in {file_path} due to column mismatch.")
        
        logger.info(f"Successfully read {len(rows)} rows from {file_path}")
        return headers, rows
    
    except Exception as e:
        logger.error(f"Error reading CSV file {file_path}: {e}")
        return [], []

def search_mac_address(file_path: str, mac_address: str) -> Optional[Dict[str, Any]]:
    """
    Search for a MAC address in a CSV file.
    
    Args:
        file_path: Path to the CSV file
        mac_address: MAC address to search for
        
    Returns:
        Dictionary containing the row if found, None otherwise
    """
    try:
        headers, rows = read_csv_file(file_path)
        
        # Normalize the search MAC address (remove colons, lowercase)
        normalized_search_mac = mac_address.lower().replace(':', '').replace('-', '')
        
        # Look for the mac_address column
        mac_column = None
        for header in headers:
            if 'mac' in header.lower():
                mac_column = header
                break
        
        if not mac_column:
            logger.warning(f"No MAC address column found in {file_path}")
            return None
        
        # Search for the MAC address
        for row in rows:
            # Normalize the row's MAC address
            row_mac = row[mac_column].lower().replace(':', '').replace('-', '')
            
            if row_mac == normalized_search_mac:
                logger.info(f"Found MAC address {mac_address} in {file_path}")
                return row
        
        logger.info(f"MAC address {mac_address} not found in {file_path}")
        return None
    
    except Exception as e:
        logger.error(f"Error searching for MAC address in {file_path}: {e}")
        return None

def search_mac_address_in_files(directory_path: str, mac_address: str, include_historical: bool = False) -> Tuple[List[str], Optional[Dict[str, Any]]]:
    """
    Search for a MAC address in all netspeed CSV files in a directory.
    
    Args:
        directory_path: Path to the directory containing CSV files
        mac_address: MAC address to search for
        include_historical: Whether to include historical files
        
    Returns:
        Tuple containing (headers, row) if found, (headers, None) otherwise
    """
    try:
        dir_path = Path(directory_path)
        
        if not dir_path.exists() or not dir_path.is_dir():
            logger.error(f"Directory {directory_path} does not exist or is not a directory")
            return [], None
        
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
        
        logger.info(f"Searching for MAC address {mac_address} in {len(files_to_search)} files")
        
        # Search each file
        for file_path in files_to_search:
            headers, rows = read_csv_file(str(file_path))
            if not headers or not rows:
                continue
                
            result = search_mac_address(str(file_path), mac_address)
            if result:
                return headers, result
        
        # If we get here, no results were found
        logger.info(f"MAC address {mac_address} not found in any file")
        
        # Return headers from the current file anyway (if it exists)
        if current_file.exists():
            headers, _ = read_csv_file(str(current_file))
            return headers, None
        
        return [], None
    
    except Exception as e:
        logger.error(f"Error searching for MAC address in directory {directory_path}: {e}")
        return [], None
