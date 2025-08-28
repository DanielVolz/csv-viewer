import csv
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define base headers for different known formats
KNOWN_HEADERS = {
    11: [  # OLD format
        "IP Address", "Serial Number", "Model Name", "MAC Address", "MAC Address 2",
        "Switch Hostname", "Switch Port"
    ],
    14: [  # OLD format without KEM
        "IP Address", "Line Number", "Serial Number", "Model Name", "MAC Address",
        "MAC Address 2", "Subnet Mask", "Voice VLAN", "Speed 1", "Speed 2",
        "Switch Hostname", "Switch Port", "Speed Switch-Port", "Speed PC-Port"
    ],
    15: [  # TRANSITION format with 1 KEM column
        "IP Address", "Line Number", "Serial Number", "Model Name", "KEM",
        "MAC Address", "MAC Address 2", "Subnet Mask", "Voice VLAN", "Speed 1", "Speed 2",
        "Switch Hostname", "Switch Port", "Speed Switch-Port", "Speed PC-Port"
    ],
    16: [  # NEW STANDARD format with KEM columns (current and future files)
        "IP Address", "Line Number", "Serial Number", "Model Name", "KEM", "KEM 2",
        "MAC Address", "MAC Address 2", "Subnet Mask", "Voice VLAN", "Speed 1", "Speed 2",
        "Switch Hostname", "Switch Port", "Speed Switch-Port", "Speed PC-Port"
    ]
}

# Define the desired display order for columns (what Frontend should show)
# KEM and KEM 2 are included in backend processing but merged into Line Number for display
DESIRED_ORDER = [
    "#", "File Name", "Creation Date", "IP Address", "Line Number",
    "MAC Address", "MAC Address 2", "Subnet Mask", "Voice VLAN", "Speed 1", "Speed 2",
    "Switch Hostname", "Switch Port", "Speed Switch-Port", "Speed PC-Port", "Serial Number", "Model Name"
]

# Regex patterns for intelligent column detection
COLUMN_PATTERNS = {
    "IP Address": re.compile(r'^(?:10\.|172\.|192\.|169\.254\.|127\.)[0-9.]+$'),  # More specific IP ranges
    "Line Number": re.compile(r'^\+?\d{7,15}$'),  # Phone numbers with 7-15 digits
    "Serial Number": re.compile(r'^[A-Z][A-Z0-9]{8,14}$'),  # Cisco serial numbers starting with letter
    "Model Name": re.compile(r'^(CP-\d+|DP-\d+)$'),  # Cisco phone models
    "KEM": re.compile(r'^KEM[12]?$', re.IGNORECASE),
    "MAC Address": re.compile(r'^[0-9A-F]{12}$', re.IGNORECASE),  # Pure MAC without SEP prefix
    "MAC Address 2": re.compile(r'^SEP[0-9A-F]{12}$', re.IGNORECASE),  # SEP prefixed MAC
    "Subnet Mask": re.compile(r'^255\.[\d.]+$'),  # Subnet masks starting with 255
    "Voice VLAN": re.compile(r'^\d{1,4}$'),  # VLAN IDs (1-4 digits)
    "Speed 1": re.compile(r'^(Autom\.|Auto|Fixed|\d+\s*(Mbps|Kbps)?|[0-9.]+).*', re.IGNORECASE),
    "Speed 2": re.compile(r'^(Autom\.|Auto|Fixed|\d+\s*(Mbps|Kbps)?|[0-9.]+).*', re.IGNORECASE),
    "Switch Hostname": re.compile(r'^[A-Za-z0-9\-_.]+\.juwin\.bayern\.de$', re.IGNORECASE),
    "Switch Port": re.compile(r'^(GigabitEthernet|FastEthernet|Ethernet)\d+/\d+/\d+$', re.IGNORECASE),
    "Speed Switch-Port": re.compile(r'^(Voll|Half|Auto|[0-9.]+\s*(Mbps|Kbps)?)', re.IGNORECASE),
    "Speed PC-Port": re.compile(r'^(Voll|Half|Auto|[0-9.]+\s*(Mbps|Kbps)?|\d+)', re.IGNORECASE)
}


def detect_column_type(value: str) -> Optional[str]:
    """
    Detect the type of a column value using regex patterns.

    Args:
        value: The cell value to analyze

    Returns:
        The detected column type or None if no pattern matches
    """
    if not value or not value.strip():
        return None

    value = value.strip()

    # Check each pattern
    for column_type, pattern in COLUMN_PATTERNS.items():
        if pattern.match(value):
            return column_type

    return None


def intelligent_column_mapping(row: List[str]) -> Dict[str, str]:
    """
    Use intelligent pattern matching to map CSV columns to the correct headers.
    This handles cases where phones without KEM modules have shifted columns.

    Args:
        row: List of cell values from a CSV row

    Returns:
        Dictionary mapping column names to values
    """
    result = {}
    used_indices = set()

    # Define matching order priority (higher priority items are matched first)
    priority_order = [
        "Switch Hostname",     # Very specific pattern
        "Switch Port",         # Very specific pattern
        "Model Name",          # Very specific pattern
        "MAC Address 2",       # SEP prefix is very specific
        "IP Address",          # Specific IP ranges
        "Line Number",         # Phone number pattern
        "Subnet Mask",         # 255.x.x.x pattern
        "Voice VLAN",          # Numeric VLAN
        "MAC Address",         # Pure MAC pattern
        "Serial Number",       # More general alphanumeric
        "Speed 1",             # Speed patterns
        "Speed 2",
        "Speed Switch-Port",
        "Speed PC-Port",
        "KEM",                 # KEM patterns
        "KEM 2"
    ]

    # First pass: identify columns with high-confidence patterns in priority order
    for column_type in priority_order:
        if column_type in result:
            continue  # Already assigned

        pattern = COLUMN_PATTERNS.get(column_type)
        if not pattern:
            continue

        for i, cell in enumerate(row):
            if i in used_indices or not cell or not cell.strip():
                continue

            cell_value = cell.strip()
            if pattern.match(cell_value):
                result[column_type] = cell_value
                used_indices.add(i)
                logger.debug(f"Priority match: '{column_type}' at index {i}: {cell_value}")
                break

    # Second pass: assign remaining cells to missing fields using positional logic
    remaining_cells = [(i, cell) for i, cell in enumerate(row) if i not in used_indices and cell.strip()]

    # List of all expected fields in order
    expected_fields = KNOWN_HEADERS[16]  # Use 16-column format as reference
    missing_fields = [field for field in expected_fields if field not in result]

    # For remaining cells, try to assign based on typical order
    for i, (cell_idx, cell_value) in enumerate(remaining_cells):
        if i < len(missing_fields):
            field_name = missing_fields[i]
            cell_val = cell_value.strip()

            # Skip obviously wrong assignments
            if field_name == "IP Address" and cell_val.startswith("255."):
                continue
            elif field_name == "Subnet Mask" and not cell_val.startswith("255."):
                continue
            elif field_name == "Voice VLAN" and not cell_val.isdigit():
                continue

            result[field_name] = cell_val
            used_indices.add(cell_idx)
            logger.debug(f"Assigned remaining field '{field_name}': {cell_val}")

    # Ensure all required fields exist with empty values if not found
    for header in expected_fields:
        if header not in result:
            result[header] = ""

    return result


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
    if column_count >= 16:
        base_headers = KNOWN_HEADERS[16].copy()
    elif column_count >= 14:
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

            # Generate headers based on detected column count (we'll use 16-column format as standard)
            file_headers = KNOWN_HEADERS[16].copy()
            logger.info(f"Using 16-column standard headers for {file_path}: {file_headers}")

            # All files will be normalized to 16-column format for consistent processing
            logger.info(f"Processing {file_path} with mixed format support (per-row normalization)")

            # Process rows with intelligent column detection
            for idx, row in enumerate(all_rows, 1):  # Start counting from 1
                # Skip empty rows
                if len(row) == 0:
                    logger.warning(f"Skipping empty row {idx} in {file_path}")
                    continue

                # Clean row data
                cleaned_row = [cell.strip() for cell in row]

                # Use intelligent column mapping instead of positional mapping
                logger.debug(f"Row {idx}: Processing {len(cleaned_row)} columns with intelligent mapping")
                row_dict = intelligent_column_mapping(cleaned_row)

                # Merge KEM information into Line Number for display (but keep KEM columns in data)
                line_number = row_dict.get("Line Number", "")
                kem_info_parts = []

                if row_dict.get("KEM", "").strip():
                    kem_info_parts.append(row_dict["KEM"].strip())

                if row_dict.get("KEM 2", "").strip():
                    kem_info_parts.append(row_dict["KEM 2"].strip())

                # Merge KEM info into Line Number for display
                if kem_info_parts:
                    kem_info = " " + " ".join(kem_info_parts)
                    row_dict["Line Number"] = f"{line_number}{kem_info}".strip()

                # Add file name, creation date, and row number
                row_dict["File Name"] = file_name
                row_dict["Creation Date"] = creation_date
                row_dict["#"] = str(idx)

                # Filter row to only include desired columns for consistent frontend display
                filtered_row = {}
                for header in DESIRED_ORDER:
                    if header in row_dict:
                        filtered_row[header] = row_dict[header]

                rows.append(filtered_row)

                # Log debugging info for CP-8832 phones
                if row_dict.get("Model Name", "").strip() == "CP-8832":
                    logger.info(f"CP-8832 detected at row {idx}: Switch Hostname='{row_dict.get('Switch Hostname', '')}', Voice VLAN='{row_dict.get('Voice VLAN', '')}'")
                    logger.debug(f"Full row mapping: {row_dict}")

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


def read_csv_file_normalized(file_path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Read a CSV file and return per-row normalized dictionaries using the 16-column standard.

    This variant preserves the original KEM/KEM 2 fields and does not merge them into
    Line Number or filter columns. It is intended for backend analytics (e.g., statistics)
    where full access to all fields is required.

    Returns a tuple of (headers, rows) where headers are the 16 standard column names.
    """
    try:
        # Detect delimiter by sampling content
        with open(file_path, 'r') as csv_file:
            content = csv_file.read()
            csv_file.seek(0)

            delimiter = ';' if ';' in content else ','

            class TrailingDelimiterReader:
                def __init__(self, csv_file, delimiter):
                    self.reader = csv.reader(csv_file, delimiter=delimiter)
                    self.delimiter = delimiter

                def __iter__(self):
                    return self

                def __next__(self):
                    row = next(self.reader)
                    if row and row[-1] == '':
                        original_line = self.delimiter.join(row)
                        if original_line.endswith(self.delimiter):
                            return row[:-1]
                    return row

            reader = TrailingDelimiterReader(csv_file, delimiter)
            raw_rows = list(reader)

        if not raw_rows:
            return KNOWN_HEADERS[16].copy(), []

        # Normalize each row to 16 columns
        headers16 = KNOWN_HEADERS[16].copy()
        normalized_rows: List[Dict[str, Any]] = []

        for idx, row in enumerate(raw_rows, 1):
            if not row:
                continue
            cleaned_row = [cell.strip() for cell in row]

            # Use intelligent column mapping instead of positional mapping
            row_dict = intelligent_column_mapping(cleaned_row)
            normalized_rows.append(row_dict)

        return headers16, normalized_rows
    except Exception as e:
        logger.error(f"Error normalizing CSV file {file_path}: {e}")
        return KNOWN_HEADERS[16].copy(), []


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
