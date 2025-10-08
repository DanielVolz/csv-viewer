import csv
import hashlib
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

from utils.path_utils import collect_netspeed_files

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define base headers for different known formats
LEGACY_COLUMN_RENAMES = {
    "Speed Switch-Port": "Switch Port Mode",
    "Speed PC-Port": "PC Port Mode",
    "Speed 1": "Phone Port Speed",
    "Speed 2": "PC Port Speed",
}


def _canonicalize_header_name(name: str) -> str:
    if not name:
        return name
    return LEGACY_COLUMN_RENAMES.get(name, name)


def _canonicalize_header_row(headers: List[str]) -> List[str]:
    seen = set()
    canonical: List[str] = []
    for header in headers:
        normalized = _canonicalize_header_name(header)
        if normalized not in seen:
            seen.add(normalized)
            canonical.append(normalized)
    return canonical


# Legacy KNOWN_HEADERS kept only for old files (< 16 columns)
# Files with >= 16 columns use automatic detection via NEW_NETSPEED_HEADERS
KNOWN_HEADERS = {
    11: [  # OLD format
        "IP Address", "Serial Number", "Model Name", "MAC Address", "MAC Address 2",
        "Switch Hostname", "Switch Port"
    ],
    14: [  # OLD format without KEM
        "IP Address", "Line Number", "Serial Number", "Model Name", "MAC Address",
        "MAC Address 2", "Subnet Mask", "Voice VLAN", "Phone Port Speed", "PC Port Speed",
        "Switch Hostname", "Switch Port", "Switch Port Mode", "PC Port Mode"
    ],
    15: [  # TRANSITION format with 1 KEM column
        "IP Address", "Line Number", "Serial Number", "Model Name", "KEM",
        "MAC Address", "MAC Address 2", "Subnet Mask", "Voice VLAN", "Switch Port Mode", "PC Port Mode",
        "Switch Hostname", "Switch Port", "Phone Port Speed", "PC Port Speed"
    ]
}

NEW_NETSPEED_HEADERS = [
    "IPAddress",
    "PhoneDirectoryNumber",
    "SerialNumber",
    "PhoneModel",
    "KeyExpansionModule1",
    "KeyExpansionModule2",
    "MACAddress1",
    "MACAddress2",
    "SwitchPortMode",
    "PCPortMode",
    "SubNetMask",
    "VLANId",
    "SwitchFQDN",
    "SwitchPort",
    "PhonePortSpeed",
    "PCPortSpeed",
    "CallManager1",
    "CallManager2",
    "CallManager3",
]

NEW_TO_CANONICAL_HEADER_MAP = {
    "IPAddress": "IP Address",
    "PhoneDirectoryNumber": "Line Number",
    "SerialNumber": "Serial Number",
    "PhoneModel": "Model Name",
    "KeyExpansionModule1": "KEM",
    "KeyExpansionModule2": "KEM 2",
    "MACAddress1": "MAC Address",
    "MACAddress2": "MAC Address 2",
    "SwitchPortMode": "Switch Port Mode",
    "PCPortMode": "PC Port Mode",
    "SubNetMask": "Subnet Mask",
    "VLANId": "Voice VLAN",
    "SwitchFQDN": "Switch Hostname",
    "SwitchPort": "Switch Port",
    "PhonePortSpeed": "Phone Port Speed",
    "PCPortSpeed": "PC Port Speed",
    "CallManager1": "CallManager 1",
    "CallManager2": "CallManager 2",
    "CallManager3": "CallManager 3",
}

_NEW_HEADER_LOWER = [h.lower() for h in NEW_NETSPEED_HEADERS]

# Define the desired display order for columns (what Frontend should show)
# KEM and KEM 2 are included in backend processing but merged into Line Number for display
DESIRED_ORDER = [
    "#", "File Name", "Creation Date", "IP Address", "Line Number",
    "MAC Address", "MAC Address 2", "Subnet Mask", "Voice VLAN", "Phone Port Speed", "PC Port Speed",
    "Switch Hostname", "Switch Port", "Switch Port Mode", "PC Port Mode", "Serial Number", "Model Name",
    "CallManager 1", "CallManager 2", "CallManager 3"
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
    "Phone Port Speed": re.compile(r'^(Autom\.|Auto|Fixed|\d+\s*(Mbps|Kbps)?|[0-9.]+).*', re.IGNORECASE),
    "PC Port Speed": re.compile(r'^(Autom\.|Auto|Fixed|\d+\s*(Mbps|Kbps)?|[0-9.]+).*', re.IGNORECASE),
    "Switch Hostname": re.compile(r'^[A-Za-z0-9\-_.]+\.juwin\.bayern\.de$', re.IGNORECASE),
    "Switch Port": re.compile(r'^(GigabitEthernet|FastEthernet|Ethernet)\d+/\d+/\d+$', re.IGNORECASE),
    "Switch Port Mode": re.compile(r'^(Voll|Half|Auto|[0-9.]+\s*(Mbps|Kbps)?)', re.IGNORECASE),
    "PC Port Mode": re.compile(r'^(Voll|Half|Auto|Abwärts|Aufwärts|[0-9.]+\s*(Mbps|Kbps)?|\d+)', re.IGNORECASE),
    "CallManager 1": re.compile(r'^[A-Za-z0-9\-_.]+(\.[A-Za-z0-9\-_.]+)*$'),  # Hostname/FQDN pattern
    "CallManager 2": re.compile(r'^[A-Za-z0-9\-_.]+(\.[A-Za-z0-9\-_.]+)*$'),  # Hostname/FQDN pattern
    "CallManager 3": re.compile(r'^[A-Za-z0-9\-_.]+(\.[A-Za-z0-9\-_.]+)*$'),  # Hostname/FQDN pattern
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


def _normalize_field(value: Any, uppercase: bool = False) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text.upper() if uppercase else text


def phone_row_identity(row: Dict[str, Any]) -> str:
    """Derive a stable identity for a phone row to support de-duplication."""
    serial = _normalize_field(row.get("Serial Number"), uppercase=True)
    mac1 = _normalize_field(row.get("MAC Address"), uppercase=True)
    mac2 = _normalize_field(row.get("MAC Address 2"), uppercase=True)
    line_number = _normalize_field(row.get("Line Number"))
    ip_address = _normalize_field(row.get("IP Address"))

    if serial:
        return f"serial::{serial}"
    if mac1:
        return f"mac1::{mac1}"
    if mac2:
        return f"mac2::{mac2}"
    if line_number and ip_address:
        return f"line_ip::{line_number}::{ip_address}"
    if line_number:
        return f"line::{line_number}"
    if ip_address:
        return f"ip::{ip_address}"

    payload = {k: _normalize_field(v) for k, v in sorted(row.items())}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return f"hash::{hashlib.sha1(raw.encode('utf-8')).hexdigest()}"


def _kem_module_count(row: Dict[str, Any]) -> int:
    """Return the number of detected KEM modules for a phone row."""
    kem_modules = 0
    for field in ("KEM", "KEM 2"):
        value = (row.get(field) or "").strip()
        if value:
            kem_modules += 1
    if kem_modules:
        return kem_modules
    line_number = (row.get("Line Number") or "").upper()
    if "KEM" in line_number:
        count = line_number.count("KEM")
        return count or 1
    return 0


def deduplicate_phone_rows(rows: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Return a list of phone rows with duplicates (based on identity) removed."""
    if not rows:
        return []

    best_rows: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []

    for row in rows:
        try:
            identity = phone_row_identity(row)
        except Exception:
            identity = None
        if identity is None:
            try:
                payload = json.dumps(row, sort_keys=True, default=str)
            except Exception:
                payload = str(row)
            identity = f"raw::{hashlib.sha1(payload.encode('utf-8')).hexdigest()}"

        if identity not in best_rows:
            best_rows[identity] = row
            order.append(identity)
            continue

        current_best = best_rows[identity]
        if _kem_module_count(row) > _kem_module_count(current_best):
            # Prefer the duplicate that contains explicit KEM information.
            best_rows[identity] = row

    return [best_rows[identity] for identity in order]


def count_unique_data_rows(file_path: str | Path | Any, opener: Optional[Any] = None) -> int:
    """Count unique, non-empty data rows in a CSV export, excluding the header."""
    open_fn = opener or open
    try:
        # Determine a suitable target for the opener while accommodating mocks in unit tests
        if isinstance(file_path, (str, bytes, os.PathLike)) or isinstance(file_path, Path):
            target = file_path
        else:
            target = str(file_path)

        unique_rows: set[str] = set()
        with open_fn(target, 'r', newline='') as handle:
            first_line = handle.readline()
            if not first_line:
                return 0
            for raw_line in handle:
                normalized = raw_line.rstrip('\r\n')
                if not normalized.strip():
                    continue
                if normalized in unique_rows:
                    continue
                unique_rows.add(normalized)
        return len(unique_rows)
    except Exception as exc:
        logger.debug("Failed to count unique rows for %s: %s", file_path, exc)
        return 0

def _matches_new_header(row: List[str]) -> bool:
    """Check if row matches known header patterns.
    Recognizes NEW_NETSPEED_HEADERS (modern format) and legacy KNOWN_HEADERS.
    """
    normalized = [cell.strip().lstrip("\ufeff") for cell in row]
    col_count = len(normalized)

    # Check modern format headers (NEW_NETSPEED_HEADERS - without spaces)
    if col_count >= 16:  # Modern format
        if normalized[:col_count] == NEW_NETSPEED_HEADERS[:col_count]:
            return True
        if [cell.lower() for cell in normalized] == [h.lower() for h in NEW_NETSPEED_HEADERS[:col_count]]:
            return True

    # Check legacy format headers (KNOWN_HEADERS - with spaces)
    if col_count in KNOWN_HEADERS:
        headers = KNOWN_HEADERS[col_count]
        if normalized == headers:
            return True
        if [cell.lower() for cell in normalized] == [h.lower() for h in headers]:
            return True

    return False


def _map_new_format_row(row: List[str]) -> Dict[str, str]:
    """Map a row from the new netspeed export to canonical field names.
    Automatically handles any number of columns using NEW_TO_CANONICAL_HEADER_MAP.
    """
    cells = [c.strip() for c in row]
    mapped: Dict[str, str] = {}

    # Map cells to canonical headers based on NEW_NETSPEED_HEADERS order
    # This automatically handles 16, 19, or any future column count
    for idx, source_header in enumerate(NEW_NETSPEED_HEADERS):
        if idx >= len(cells):
            break
        canonical = NEW_TO_CANONICAL_HEADER_MAP.get(source_header)
        if canonical:
            mapped[canonical] = cells[idx]

    return mapped


def intelligent_column_mapping(row: List[str], new_format: bool = False) -> Dict[str, str]:
    """
    Use intelligent pattern matching to map CSV columns to the correct headers.
    Dynamically handles different column counts (16, 19, etc.).
    This handles cases where phones without KEM modules have shifted columns.

    Args:
        row: List of cell values from a CSV row
        new_format: Whether this is the new export format with explicit headers

    Returns:
        Dictionary mapping column names to values
    """

    col_count = len(row)
    cells = [c.strip() for c in row]

    # Modern format (>= 16 columns): Use automatic mapping via NEW_TO_CANONICAL_HEADER_MAP
    # This handles 16, 19, and any future column counts automatically without code changes
    if new_format or col_count >= 16:
        return _map_new_format_row(cells)

    # Legacy formats (< 16 columns): Use explicit mapping for old files
    out: Dict[str, str] = {}

    if col_count == 15:
        mapping_legacy15 = [
            "IP Address",
            "Line Number",
            "Serial Number",
            "Model Name",
            "KEM",
            "MAC Address",
            "MAC Address 2",
            "Subnet Mask",
            "Voice VLAN",
            "Switch Port Mode",
            "PC Port Mode",
            "Switch Hostname",
            "Switch Port",
            "Phone Port Speed",
            "PC Port Speed",
        ]
        for idx, header in enumerate(mapping_legacy15):
            if idx >= col_count:
                break
            out[header] = cells[idx]
        if not out.get("KEM 2"):
            out["KEM 2"] = ""
        return out
    elif col_count >= 13:  # 13 oder 14 Spalten
        # Erkennung von defekten CP-8832 Zeilen anhand der Datenstruktur
        # Normale Zeile: Spalte 5 und 6 sind MAC-Adressen, Spalte 10 ist Switch Hostname
        # Defekte Zeile: Spalte 5 und 6 sind MAC-Adressen, aber Spalte 9 ist Switch Hostname (verschoben)

        # Prüfe ob Spalte 9 wie ein Switch Hostname aussieht (enthält Domain)
        is_defective_cp8832 = False
        if col_count >= 10:
            col9_content = cells[9] if len(cells) > 9 else ""
            col10_content = cells[10] if len(cells) > 10 else ""

            # Defekte Zeile wenn Spalte 9 einen Switch Hostname enthält
            # (Format: xxxZSL####P.juwin.bayern.de)
            is_defective_cp8832 = (
                "ZSL" in col9_content and ".juwin.bayern.de" in col9_content
            )

        if is_defective_cp8832:
            # DEFEKTE CP-8832 Zeile: PC Port Speed fehlt, daher ist alles ab Switch Hostname verschoben
            # Format: IP, Line, Serial, Model, MAC, MAC2, Subnet, VLAN, Speed1, SwitchHost, SwitchPort, SpeedSw, [eventuell leer]
            mapping_defective = [
                "IP Address",        # 0
                "Line Number",       # 1
                "Serial Number",     # 2
                "Model Name",        # 3
                "MAC Address",       # 4
                "MAC Address 2",     # 5
                "Subnet Mask",       # 6
                "Voice VLAN",        # 7
                "Phone Port Speed",  # 8
                "Switch Hostname",   # 9  ← Hierher verschoben!
                "Switch Port",       # 10
                "Switch Port Mode"   # 11
            ]

            for i, header in enumerate(mapping_defective):
                if i < min(col_count, len(mapping_defective)):
                    out[header] = cells[i]

            # Fehlende Felder leer lassen
            out["KEM"] = ""
            out["KEM 2"] = ""
            out["PC Port Speed"] = ""
            out["PC Port Mode"] = ""

        else:
            mapping_legacy14 = [
                "IP Address",
                "Line Number",
                "Serial Number",
                "Model Name",
                "MAC Address",
                "MAC Address 2",
                "Subnet Mask",
                "Voice VLAN",
                "Switch Port Mode",
                "PC Port Mode",
                "Switch Hostname",
                "Switch Port",
                "Phone Port Speed",
                "PC Port Speed",
            ]
            for idx, header in enumerate(mapping_legacy14):
                if idx >= col_count:
                    break
                out[header] = cells[idx]
            out["KEM"] = out.get("KEM", "")
            out["KEM 2"] = out.get("KEM 2", "")
        return out
    elif col_count == 12:
        # SPECIAL CASE: CP-8832 und ähnliche Telefone ohne KEM-Spalten haben nur 12 Spalten
        # Diese Telefone haben KEINE KEM-Spalte, daher sind alle Spalten ab MAC Address um 2 nach links verschoben
    # Format: IP, Line, Serial, Model, MAC, MAC2, Subnet, VLAN, PhoneSpeed, SwitchHost, SwitchPort, SwitchSpeed
        mapping_12 = [
            "IP Address",        # 0
            "Line Number",       # 1
            "Serial Number",     # 2
            "Model Name",        # 3
            "MAC Address",       # 4 (keine KEM-Spalten davor)
            "MAC Address 2",     # 5
            "Subnet Mask",       # 6
            "Voice VLAN",        # 7
            "Phone Port Speed",  # 8
            "Switch Hostname",   # 9 (verschoben von Spalte 11 auf 9!)
            "Switch Port",       # 10
            "Switch Port Mode"   # 11
        ]

        for i, header in enumerate(mapping_12):
            if i < col_count:
                out[header] = cells[i]

        # KEM-Felder leer lassen
        out["KEM"] = ""
        out["KEM 2"] = ""
        out["PC Port Speed"] = ""  # PC Port Speed fehlt bei 12-Spalten Format
        out["PC Port Mode"] = ""  # Auch PC Port Mode fehlt

        return out
    else:
        # Weniger als 12 Spalten -> very old format, try to map what we can
        # Use 11-column format as fallback
        legacy_headers = KNOWN_HEADERS.get(11, [])
        for i, val in enumerate(cells):
            if i < len(legacy_headers):
                out[legacy_headers[i]] = val
        # Ensure all expected fields exist
        out.setdefault("KEM", "")
        out.setdefault("KEM 2", "")
        out.setdefault("Line Number", "")
    return out

def generate_headers(column_count: int) -> List[str]:
    """
    Generate headers for a CSV file based on column count.
    Modern files (>= 16 columns) use NEW_TO_CANONICAL_HEADER_MAP automatically.
    Legacy files use KNOWN_HEADERS.

    Args:
        column_count: Number of columns in the CSV file

    Returns:
        List of header names
    """
    # Modern format (>= 16 columns): Use NEW_TO_CANONICAL_HEADER_MAP
    # This automatically handles 16, 19, and any future column counts
    if column_count >= 16:
        headers = []
        for i in range(min(column_count, len(NEW_NETSPEED_HEADERS))):
            source_header = NEW_NETSPEED_HEADERS[i]
            canonical = NEW_TO_CANONICAL_HEADER_MAP.get(source_header, source_header)
            headers.append(canonical)
        # If more columns than known headers, add generic names
        while len(headers) < column_count:
            headers.append(f"Column {len(headers) + 1}")
        return headers

    # Legacy format (< 16 columns): Use KNOWN_HEADERS
    if column_count in KNOWN_HEADERS:
        return KNOWN_HEADERS[column_count].copy()

    # Fallback for unknown legacy column counts
    base_headers = KNOWN_HEADERS.get(11, []).copy()
    while len(base_headers) < column_count:
        base_headers.append(f"Column {len(base_headers) + 1}")
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
    # Normalize headers to canonical names (handles legacy Speed Switch-Port naming)
    canonical_headers = _canonicalize_header_row(headers or [])

    # Filter headers to only include desired columns
    display_headers: List[str] = []
    for header in DESIRED_ORDER:
        if header in canonical_headers:
            display_headers.append(header)

    # Filter data to only include displayed columns, copying legacy values when necessary
    filtered_data = []
    for row in data:
        filtered_row = {}
        row_with_aliases = dict(row)
        for legacy, renamed in LEGACY_COLUMN_RENAMES.items():
            if legacy in row_with_aliases and renamed not in row_with_aliases:
                row_with_aliases[renamed] = row_with_aliases[legacy]
        for header in display_headers:
            if header in row_with_aliases:
                filtered_row[header] = row_with_aliases[header]
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

        new_format_with_header = False

        with open(file_path, 'r', newline='') as csv_file:
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

            if all_rows:
                normalized_first_row = [cell.strip().lstrip("\ufeff") for cell in all_rows[0]]
                if _matches_new_header(normalized_first_row):
                    logger.info(f"Detected new-format header for {file_path}")
                    new_format_with_header = True
                    all_rows = all_rows[1:]
                elif _canonicalize_header_row(normalized_first_row) == KNOWN_HEADERS[16]:
                    logger.info(f"Detected legacy header row for {file_path}")
                    all_rows = all_rows[1:]

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
            # Use the appropriate format based on column count, or generate dynamically
            file_headers = generate_headers(most_common_count)
            logger.info(f"Using {most_common_count}-column format for {file_path}: {file_headers}")

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
                logger.debug(f"Row {idx}: Processing {len(cleaned_row)} columns with intelligent mapping (new_format={new_format_with_header})")
                row_dict = intelligent_column_mapping(cleaned_row, new_format=new_format_with_header)

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
        new_format_with_header = False

        # Detect delimiter by sampling content
        with open(file_path, 'r', newline='') as csv_file:
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
            # Return 16-column headers generated from NEW_TO_CANONICAL_HEADER_MAP
            return generate_headers(16), []

        normalized_first_row = [cell.strip().lstrip("\ufeff") for cell in raw_rows[0]] if raw_rows else []
        if _matches_new_header(normalized_first_row):
            new_format_with_header = True
            raw_rows = raw_rows[1:]
        elif len(normalized_first_row) >= 14 and _canonicalize_header_row(normalized_first_row) == generate_headers(len(normalized_first_row)):
            raw_rows = raw_rows[1:]

        # Normalize each row to standard headers (16+ columns)
        # For backward compatibility, return 16-column headers
        headers16 = generate_headers(16)
        normalized_rows: List[Dict[str, Any]] = []

        for idx, row in enumerate(raw_rows, 1):
            if not row:
                continue
            cleaned_row = [cell.strip() for cell in row]

            # Use intelligent column mapping instead of positional mapping
            row_dict = intelligent_column_mapping(cleaned_row, new_format=new_format_with_header)
            normalized_rows.append(row_dict)

        return headers16, normalized_rows
    except Exception as e:
        logger.error(f"Error normalizing CSV file {file_path}: {e}")
        return generate_headers(16), []


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

        historical_files, current_file, _ = collect_netspeed_files([dir_path])

        files_to_search: List[Path] = []
        if current_file:
            files_to_search.append(current_file)

        if include_historical:
            files_to_search.extend(historical_files)

        if not files_to_search:
            fallback = dir_path / "netspeed.csv"
            if fallback.exists():
                files_to_search.append(fallback)

        logger.info(f"Searching for term '{search_term}' in {len(files_to_search)} files")

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
        if current_file and current_file.exists() and not headers:
            headers, _ = read_csv_file(str(current_file))

        return headers, matching_rows

    except Exception as e:
        logger.error(
            f"Error searching in directory {directory_path}: {e}"
        )
        return [], []
