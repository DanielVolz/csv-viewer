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

# Map historical/alternative Call Manager column names to canonical targets
CALL_MANAGER_ALIASES = {
    "CallManagerActiveSub": "Call Manager Active Sub",
    "CallManagerStandbySub": "Call Manager Standby Sub",
    "Call Manager 1": "Call Manager Active Sub",
    "Call Manager 2": "Call Manager Standby Sub",
    "Call Manager 3": "Call Manager Standby Sub",
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


# LEGACY KNOWN_HEADERS - TEMPORARY (remove after 2025-10-27)
# Used only for legacy files without headers (netspeed.csv.0-29)
# Modern files (with timestamp) read headers from first row
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

# Auto-generate display names by adding spaces between CamelCase words
def _camel_to_display(name: str) -> str:
    """Convert CamelCase to Display Name with spaces.
    Examples:
      IPAddress -> IP Address
      MACAddress2 -> MAC Address 2
    """
    import re
    # Insert space before capitals (except first char and consecutive capitals)
    result = re.sub(r'(?<!^)(?=[A-Z][a-z])', ' ', name)
    # Insert space before numbers
    result = re.sub(r'(?<=[a-z])(?=[0-9])', ' ', result)
    return result

# Optional custom mappings for special cases (override auto-generated names)
# Only add entries here if you want a different display name than auto-generated
CUSTOM_DISPLAY_NAMES = {
    "IPAddress": "IP Address",
    "PhoneDirectoryNumber": "Line Number",
    "PhoneModel": "Model Name",
    "KeyExpansionModule1": "KEM",
    "KeyExpansionModule2": "KEM 2",
    "KEM1SerialNumber": "KEM 1 Serial Number",
    "KEM2SerialNumber": "KEM 2 Serial Number",
    "MACAddress": "MAC Address",
    "MACAddress1": "MAC Address",
    "MACAddress2": "MAC Address 2",
    "SubNetMask": "Subnet Mask",
    "VLANId": "Voice VLAN",
    "SwitchFQDN": "Switch Hostname",
    "SwitchPortDuplex": "Switch Port Mode",
    "PCPortDuplex": "PC Port Mode",
    "SwitchPortSpeed": "Phone Port Speed",
    "PCPortSpeed": "PC Port Speed",
    "CallManagerActiveSub": "Call Manager Active Sub",
    "CallManagerStandbySub": "Call Manager Standby Sub",
    "PhoneSerialNumber": "Serial Number",
    # CallManager1-3 will auto-generate as "Call Manager 1", "Call Manager 2", "Call Manager 3"
    # Add custom entries only if you want different names
}

def _get_display_name(source_header: str) -> str:
    """Get display name for a CSV header.
    First checks CUSTOM_DISPLAY_NAMES, then auto-generates from CamelCase.
    """
    return CUSTOM_DISPLAY_NAMES.get(source_header, _camel_to_display(source_header))


def get_column_order(file_path: Optional[str] = None) -> List[str]:
    """
    CENTRAL FUNCTION: Get column order for ALL endpoints.

    Returns columns in CSV file order with OpenSearch field names.
    This is the SINGLE SOURCE OF TRUTH for column ordering.

    Args:
        file_path: Optional path to CSV file. If None, uses current netspeed.csv

    Returns:
        List of column names in correct order (metadata + CSV columns)
    """
    metadata_fields = ["#", "File Name", "Creation Date"]

    try:
        # Find current file if not provided
        if not file_path:
            from utils.path_utils import resolve_current_file
            current_file = resolve_current_file()
            if not current_file or not current_file.exists():
                logger.warning("Could not find current CSV file for column order")
                return metadata_fields
            file_path = str(current_file)

        # Read first line to get CSV headers
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            first_line = f.readline().strip()
            # Determine delimiter
            if ';' in first_line:
                raw_headers = first_line.split(';')
            elif ',' in first_line:
                raw_headers = first_line.split(',')
            else:
                raw_headers = first_line.split()

            # Convert CamelCase headers to OpenSearch display names
            # _get_display_name uses CUSTOM_DISPLAY_NAMES for proper mapping
            csv_headers = []
            for raw_header in raw_headers:
                display_name = _get_display_name(raw_header.strip())
                csv_headers.append(display_name)

            # Return metadata + CSV columns
            return metadata_fields + csv_headers

    except Exception as e:
        logger.error(f"Error reading column order from {file_path}: {e}")
        return metadata_fields


# ============================================================================
# MODERN FORMAT: Header-based (fully automatic for any column count)
# ============================================================================

def _read_headers_from_file(file_path: str, delimiter: str = ',') -> List[str]:
    """Read headers from a CSV file's first row.

    This is used for MODERN files (with timestamps) that always have headers.
    Makes the system truly automatic - any new column in the CSV will be
    automatically recognized without code changes or container restarts.

    Args:
        file_path: Path to the CSV file
        delimiter: CSV delimiter (comma or semicolon)

    Returns:
        List of header names from first row, or empty list if not found
    """
    try:
        with open(file_path, 'r', newline='') as f:
            reader = csv.reader(f, delimiter=delimiter)
            first_row = next(reader, [])

            # Clean headers (remove BOM, whitespace)
            headers = [h.strip().lstrip('\ufeff') for h in first_row]

            # Verify first row looks like headers (not data)
            if headers and not any(h.replace('.', '').replace(':', '').replace('+', '').isdigit() for h in headers[:3]):
                return headers
    except Exception as e:
        logger.debug(f"Could not read headers from {file_path}: {e}")

    return []

def _build_display_order_from_headers(source_headers: List[str]) -> List[str]:
    """Build display order from CSV headers.

    For MODERN files: Uses actual headers from the file.
    For LEGACY files: Uses KNOWN_HEADERS mappings.

    Args:
        source_headers: Headers from CSV file (CamelCase for modern, spaces for legacy)

    Returns:
        List of column names in display order
    """
    # Start with special metadata columns
    order = ["#", "File Name", "Creation Date"]

    # Exclude KEM columns (merged into Line Number for display)
    excluded_from_display = {"KEM", "KEM 2"}

    # Convert source headers to display names
    for header in source_headers:
        canonical_name = _get_display_name(header)
        if canonical_name and canonical_name not in excluded_from_display:
            order.append(canonical_name)

    return order

# Default display order for legacy files (used as fallback)
DEFAULT_DISPLAY_ORDER = [
    "#", "File Name", "Creation Date",
    "IP Address", "Line Number", "Serial Number", "Model Name",
    "MAC Address", "MAC Address 2", "Subnet Mask", "Voice VLAN",
    "Switch Port Mode", "PC Port Mode", "Switch Hostname", "Switch Port",
    "Phone Port Speed", "PC Port Speed",
    "Call Manager Active Sub", "Call Manager Standby Sub"
]

# MODERN format: Column detection happens automatically by reading headers from CSV
# LEGACY format: Uses pattern detection (see _map_legacy_format_with_pattern_detection)


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
        try:
            is_path = isinstance(file_path, Path)
        except TypeError:
            is_path = False
        if isinstance(file_path, (str, bytes, os.PathLike)) or is_path:
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

def _is_header_row(row: List[str]) -> bool:
    """Check if row looks like headers (not data).

    Modern files: Headers are CamelCase without spaces (IPAddress, PhoneModel, etc.)
    Legacy files: Headers have spaces (IP Address, Phone Model, etc.)

    Returns True if row appears to be headers.
    """
    if not row:
        return False

    normalized = [cell.strip().lstrip("\ufeff") for cell in row]
    col_count = len(normalized)

    # Check if it matches known legacy header patterns
    if col_count in KNOWN_HEADERS:
        headers = KNOWN_HEADERS[col_count]
        if normalized == headers:
            return True
        if [cell.lower() for cell in normalized] == [h.lower() for h in headers]:
            return True

    # For modern files: Check if cells look like CamelCase headers (not data)
    # Data rows typically start with IP address, phone number, or serial number
    # Headers contain letters and no dots/colons/plus signs in first few cells
    first_cells = normalized[:3]
    if not any(h.replace('.', '').replace(':', '').replace('+', '').isdigit() for h in first_cells):
        # Looks like headers - contains mostly letters
        return True

    return False


def _map_modern_format_row(row: List[str], headers: List[str]) -> Dict[str, str]:
    """Map a row from MODERN netspeed files to canonical field names.

    MODERN files always have headers in the first row.
    This function makes the system fully automatic - any new column in the CSV
    will be recognized without code changes.

    Args:
        row: Data cells from CSV row
        headers: Header names from first row of CSV file

    Returns:
        Dictionary mapping canonical field names to values
    """
    cells = [c.strip() for c in row]
    mapped: Dict[str, str] = {}

    # Map each cell to its canonical name based on CSV headers
    # This automatically handles ANY column count and ANY new columns
    for idx, source_header in enumerate(headers):
        if idx >= len(cells):
            break
        canonical = _get_display_name(source_header)
        if canonical:
            mapped[canonical] = cells[idx]

    return mapped


def intelligent_column_mapping(row: List[str], headers: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Map CSV row to canonical field names.

    MODERN files (with headers): Uses header-based mapping - fully automatic.
    LEGACY files (no headers): Uses pattern detection - temporary solution.

    Args:
        row: List of cell values from a CSV row
        headers: Headers from CSV file (for modern files with headers)
                 If None, assumes legacy format without headers

    Returns:
        Dictionary mapping canonical field names to values
    """
    col_count = len(row)
    cells = [c.strip() for c in row]

    # MODERN format: Has headers, fully automatic
    if headers:
        return _map_modern_format_row(cells, headers)

    # LEGACY format: No headers, use pattern detection
    # TODO: Remove this after 2025-10-27 when legacy files are archived
    return _map_legacy_format_with_pattern_detection(cells)


# ============================================================================
# LEGACY FORMAT: Pattern-based detection (TEMPORARY - remove after 2025-10-27)
# ============================================================================
# Legacy files have NO headers and variable column counts (11-15 columns).
# After 2025-10-27, these files will only exist in archives.
# This entire section can be removed after that date.
# ============================================================================

def _map_legacy_format_with_pattern_detection(cells: List[str]) -> Dict[str, str]:
    """
    Map LEGACY format rows using pattern detection.

    LEGACY files (netspeed.csv.0-29) have no headers and inconsistent columns.
    This function detects field types by analyzing data patterns.

    TEMPORARY: Remove this function after 2025-10-27 when legacy files are archived.

    Args:
        cells: List of cell values from a CSV row

    Returns:
        Dictionary mapping column names to values
    """
    col_count = len(cells)
    out: Dict[str, str] = {}

    # Helper functions to detect field types based on data patterns
    def is_ip_address(s: str) -> bool:
        if not s or s.count('.') != 3:
            return False
        try:
            parts = s.split('.')
            return len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts)
        except (ValueError, AttributeError):
            return False

    def is_phone_number(s: str) -> bool:
        return s.startswith('+') and len(s) > 8 and s[1:].replace(' ', '').isdigit()

    def is_mac_address(s: str) -> bool:
        s_clean = s.replace(':', '').replace('-', '').upper()
        return len(s_clean) == 12 and all(c in '0123456789ABCDEF' for c in s_clean)

    def is_hostname(s: str) -> bool:
        s_lower = s.lower()
        return 'zsl' in s_lower and ('.juwin.bayern.de' in s_lower or '.de' in s_lower)

    def is_port_name(s: str) -> bool:
        s_lower = s.lower()
        return 'gigabit' in s_lower or 'ethernet' in s_lower or s_lower.startswith('gi')

    def is_subnet_mask(s: str) -> bool:
        return s.startswith('255.') and s.count('.') == 3

    def is_vlan(s: str) -> bool:
        try:
            return s.isdigit() and 1 <= int(s) <= 4094
        except:
            return False

    def is_speed(s: str) -> bool:
        s_lower = s.lower()
        return ('auto' in s_lower or 'voll' in s_lower or 'full' in s_lower or
                'half' in s_lower or 'down' in s_lower or 'abwärts' in s_lower or
                any(str(speed) in s for speed in ['10', '100', '1000']))

    # Special handling for 15-column format (has explicit KEM column)
    if col_count == 15:
        mapping_legacy15 = [
            "IP Address", "Line Number", "Serial Number", "Model Name", "KEM",
            "MAC Address", "MAC Address 2", "Subnet Mask", "Voice VLAN",
            "Switch Port Mode", "PC Port Mode", "Switch Hostname", "Switch Port",
            "Phone Port Speed", "PC Port Speed"
        ]
        for idx, header in enumerate(mapping_legacy15):
            out[header] = cells[idx] if idx < col_count else ""
        out.setdefault("KEM 2", "")
        return out

    # Intelligent pattern-based mapping for any other column count
    # Detect key fields by their data patterns
    ip_idx = mac1_idx = mac2_idx = hostname_idx = port_idx = -1

    for i, cell in enumerate(cells):
        if ip_idx == -1 and is_ip_address(cell):
            ip_idx = i
        elif mac1_idx == -1 and is_mac_address(cell) and 'SEP' not in cell.upper():
            mac1_idx = i
        elif mac2_idx == -1 and is_mac_address(cell) and i > mac1_idx:
            mac2_idx = i
        elif hostname_idx == -1 and is_hostname(cell):
            hostname_idx = i
        elif port_idx == -1 and is_port_name(cell) and i > hostname_idx:
            port_idx = i

    # Build mapping based on detected positions
    # Standard legacy format: IP, [Line], Serial, Model, [KEM], MAC1, MAC2, Subnet, VLAN, [Speeds], Hostname, Port, [Speeds]

    if ip_idx >= 0:
        out["IP Address"] = cells[ip_idx]

        # Line number usually right after IP
        if ip_idx + 1 < col_count and is_phone_number(cells[ip_idx + 1]):
            out["Line Number"] = cells[ip_idx + 1]
            out["Serial Number"] = cells[ip_idx + 2] if ip_idx + 2 < col_count else ""
            out["Model Name"] = cells[ip_idx + 3] if ip_idx + 3 < col_count else ""
        else:
            # Very old format without line number
            out["Line Number"] = ""
            out["Serial Number"] = cells[ip_idx + 1] if ip_idx + 1 < col_count else ""
            out["Model Name"] = cells[ip_idx + 2] if ip_idx + 2 < col_count else ""

    # MAC addresses
    if mac1_idx >= 0:
        out["MAC Address"] = cells[mac1_idx]
    if mac2_idx >= 0:
        out["MAC Address 2"] = cells[mac2_idx]

    # Hostname and Port
    if hostname_idx >= 0:
        out["Switch Hostname"] = cells[hostname_idx]
    if port_idx >= 0:
        out["Switch Port"] = cells[port_idx]

    # Find subnet mask and VLAN (between MAC and Hostname)
    if mac2_idx >= 0 and hostname_idx >= 0:
        for i in range(mac2_idx + 1, hostname_idx):
            if i < col_count:
                if is_subnet_mask(cells[i]):
                    out["Subnet Mask"] = cells[i]
                    out["Voice VLAN"] = cells[i]

    # Detect speeds (before and after hostname)
    speed_candidates = []
    if hostname_idx >= 0:
        # Speeds before hostname
        for i in range(max(mac2_idx + 1, 0), hostname_idx):
            if i < col_count and is_speed(cells[i]):
                speed_candidates.append((i, cells[i]))
        # Speeds after port
        if port_idx >= 0:
            for i in range(port_idx + 1, col_count):
                if is_speed(cells[i]):
                    speed_candidates.append((i, cells[i]))

    # Assign speeds to appropriate fields
    if len(speed_candidates) >= 1:
        out["Switch Port Mode"] = speed_candidates[0][1]
    if len(speed_candidates) >= 2:
        out["PC Port Mode"] = speed_candidates[1][1]
    if len(speed_candidates) >= 3:
        out["Phone Port Speed"] = speed_candidates[2][1]
    if len(speed_candidates) >= 4:
        out["PC Port Speed"] = speed_candidates[3][1]

    # Check for KEM column (usually between Model and MAC1)
    if mac1_idx > 4 and ip_idx >= 0:
        kem_idx = ip_idx + 4  # Position after Model Name
        if kem_idx < mac1_idx and kem_idx < col_count:
            kem_value = cells[kem_idx]
            if kem_value and kem_value.upper() == 'KEM':
                out["KEM"] = kem_value

    # Fill in missing fields with empty strings
    for field in ["IP Address", "Line Number", "Serial Number", "Model Name",
                  "KEM", "KEM 2", "MAC Address", "MAC Address 2", "Subnet Mask",
                  "Voice VLAN", "Switch Port Mode", "PC Port Mode", "Switch Hostname",
                  "Switch Port", "Phone Port Speed", "PC Port Speed"]:
        out.setdefault(field, "")

    return out

def generate_headers_for_legacy_file(column_count: int) -> List[str]:
    """
    Generate headers for LEGACY files without headers.

    TEMPORARY: Only used for legacy netspeed.csv.0-29 files.
    Remove after 2025-10-27 when legacy files are archived.

    Args:
        column_count: Number of columns in the legacy CSV file

    Returns:
        List of canonical header names
    """
    # Legacy format: Use KNOWN_HEADERS
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

    Uses get_csv_column_order() as SINGLE SOURCE OF TRUTH for column ordering.
    ALWAYS returns ALL columns from the CSV file, even if they're empty in the current result set.

    Args:
        headers: List of all available headers from the data source (may be alphabetically sorted by OpenSearch)
        data: List of data dictionaries

    Returns:
        Tuple of (filtered_headers, filtered_data) - all columns in CSV file order
    """
    # Get ALL columns from the current CSV file - this is the single source of truth
    # IMPORTANT: Always return ALL columns, even if they're empty in this particular result set
    # This ensures consistent column display across all searches and matches Settings configuration
    display_headers = get_csv_column_order()

    # Filter data to only include displayed columns, copying legacy values when necessary
    filtered_data = []
    for row in data:
        filtered_row = {}
        row_with_aliases = dict(row)
        for legacy, renamed in LEGACY_COLUMN_RENAMES.items():
            if legacy in row_with_aliases and renamed not in row_with_aliases:
                row_with_aliases[renamed] = row_with_aliases[legacy]
        for alias, canonical in CALL_MANAGER_ALIASES.items():
            if alias in row_with_aliases and canonical not in row_with_aliases:
                row_with_aliases[canonical] = row_with_aliases[alias]
        for header in display_headers:
            # Include column even if value is missing - will show as empty
            filtered_row[header] = row_with_aliases.get(header, "")
        filtered_data.append(filtered_row)

    return display_headers, filtered_data


def get_csv_column_order() -> list:
    """
    Liefert die Spaltenreihenfolge (inkl. OpenSearch-Mapping) gemäß aktueller CSV-Datei.
    Diese Funktion ist die zentrale Quelle für die Spaltenlogik.
    """
    metadata_fields = ["#", "File Name", "Creation Date"]
    csv_headers = []
    try:
        from utils.path_utils import resolve_current_file
        current_file = resolve_current_file()
        if current_file and current_file.exists():
            with open(current_file, 'r', encoding='utf-8-sig') as f:
                first_line = f.readline().strip()
                if ';' in first_line:
                    raw_headers = first_line.split(';')
                elif ',' in first_line:
                    raw_headers = first_line.split(',')
                else:
                    raw_headers = first_line.split()
                for raw_header in raw_headers:
                    display_name = _get_display_name(raw_header.strip())
                    csv_headers.append(display_name)
    except Exception as e:
        logger.warning(f"Could not read CSV header order, falling back to default: {e}")
    return metadata_fields + csv_headers


def read_csv_file(file_path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Read a CSV file and return headers and rows as dictionaries.

    MODERN files (with timestamp): Reads headers from first row - fully automatic.
    LEGACY files (without headers): Uses pattern detection - temporary solution.

    Args:
        file_path: Path to the CSV file

    Returns:
        Tuple containing (headers, rows)
        - headers: List of column names for display
        - rows: List of dictionaries where keys are headers and values are cell values
    """
    try:
        rows = []

        # Get file information
        file_name = os.path.basename(file_path)
        file_stat = os.stat(file_path)
        creation_date = datetime.fromtimestamp(file_stat.st_ctime).strftime('%Y-%m-%d')

        logger.info(f"Reading CSV file: {file_path}")

        # Read and parse CSV
        all_rows = []
        file_headers = None  # Will be populated if file has headers

        with open(file_path, 'r', newline='') as csv_file:
            content = csv_file.read()
            csv_file.seek(0)

            # Detect delimiter
            delimiter = ';' if ';' in content else ','
            logger.info(f"Detected delimiter '{delimiter}' for {file_path}")

            # Custom CSV reader that handles trailing delimiters
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
            all_rows = list(reader)

        if not all_rows:
            logger.warning(f"Empty file: {file_path}")
            return DEFAULT_DISPLAY_ORDER, []

        # Check if first row is headers
        first_row = [cell.strip().lstrip("\ufeff") for cell in all_rows[0]]
        if _is_header_row(first_row):
            file_headers = first_row
            all_rows = all_rows[1:]  # Skip header row
            logger.info(f"Detected {len(file_headers)}-column header row: {file_headers[:5]}...")
        else:
            logger.info(f"No header row detected - using pattern detection for legacy format")

        if not all_rows:
            logger.warning(f"No data rows in {file_path}")
            return DEFAULT_DISPLAY_ORDER, []

        # Build display order based on file headers or default for legacy
        if file_headers:
            display_order = _build_display_order_from_headers(file_headers)
        else:
            display_order = DEFAULT_DISPLAY_ORDER

        # Process data rows
        for idx, row in enumerate(all_rows, 1):
            if not row:
                continue

            cleaned_row = [cell.strip() for cell in row]

            # Map row using headers (modern) or pattern detection (legacy)
            row_dict = intelligent_column_mapping(cleaned_row, headers=file_headers)

            # Merge KEM information into Line Number for display
            line_number = row_dict.get("Line Number", "")
            kem_info_parts = []
            if row_dict.get("KEM", "").strip():
                kem_info_parts.append(row_dict["KEM"].strip())
            if row_dict.get("KEM 2", "").strip():
                kem_info_parts.append(row_dict["KEM 2"].strip())

            if kem_info_parts:
                kem_info = " " + " ".join(kem_info_parts)
                row_dict["Line Number"] = f"{line_number}{kem_info}".strip()

            # Add metadata
            row_dict["File Name"] = file_name
            row_dict["Creation Date"] = creation_date
            row_dict["#"] = str(idx)

            # Filter to display columns only
            filtered_row = {}
            for header in display_order:
                if header in row_dict:
                    filtered_row[header] = row_dict[header]

            rows.append(filtered_row)

        logger.info(f"Successfully read {len(rows)} rows from {file_path}")

        # Build display headers from actual data
        if rows:
            all_headers = set()
            for row in rows:
                all_headers.update(row.keys())

            display_headers = [h for h in display_order if h in all_headers]
            return display_headers, rows
        else:
            return display_order, rows

    except Exception as e:
        logger.error(f"Error reading CSV file {file_path}: {e}")
        return [], []


def read_csv_file_normalized(file_path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Read a CSV file and return normalized dictionaries with ALL fields preserved.

    MODERN files (with timestamp): Reads headers from first row - fully automatic.
    LEGACY files (without headers): Uses pattern detection - temporary solution.

    This variant preserves original KEM/KEM 2 fields (doesn't merge into Line Number).
    Intended for backend analytics (statistics) where full field access is required.

    Returns:
        Tuple of (headers, rows) where headers are canonical field names
    """
    try:
        # Read and parse CSV
        all_rows = []
        file_headers = None

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
            all_rows = list(reader)

        if not all_rows:
            return generate_headers_for_legacy_file(16), []

        # Check if first row is headers
        first_row = [cell.strip().lstrip("\ufeff") for cell in all_rows[0]]
        if _is_header_row(first_row):
            file_headers = first_row
            all_rows = all_rows[1:]  # Skip header row

        if not all_rows:
            if file_headers:
                return [_get_display_name(h) for h in file_headers], []
            return generate_headers_for_legacy_file(16), []

        # Process data rows
        normalized_rows: List[Dict[str, Any]] = []
        for row in all_rows:
            if not row:
                continue

            cleaned_row = [cell.strip() for cell in row]
            row_dict = intelligent_column_mapping(cleaned_row, headers=file_headers)
            normalized_rows.append(row_dict)

        # Determine headers list
        if file_headers:
            headers_list = [_get_display_name(h) for h in file_headers]
        else:
            # Legacy: Use standard headers
            headers_list = generate_headers_for_legacy_file(16)

        return headers_list, normalized_rows

    except Exception as e:
        logger.error(f"Error normalizing CSV file {file_path}: {e}")
        return generate_headers_for_legacy_file(16), []


def read_csv_file_preview(file_path: str, limit: int = 100) -> Tuple[List[str], List[Dict[str, Any]], int]:
    """Read only the first N rows of a CSV file for fast preview.

    PERFORMANCE-OPTIMIZED: Only reads header + limit rows instead of entire file.
    Returns headers, limited rows, and total row count (approximate from file size).

    Args:
        file_path: Path to CSV file
        limit: Maximum number of data rows to read (default 100)

    Returns:
        Tuple of (headers, rows, total_count) where:
        - headers: List of canonical field names
        - rows: List of at most 'limit' row dictionaries
        - total_count: Estimated total rows in file
    """
    try:
        file_headers = None
        rows_read = []
        total_lines = 0

        with open(file_path, 'r', newline='') as csv_file:
            # Quick delimiter detection from first few KB
            sample = csv_file.read(4096)
            csv_file.seek(0)
            delimiter = ';' if ';' in sample else ','

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

            # Read header row
            try:
                first_row = next(reader)
                first_row_cleaned = [cell.strip().lstrip("\ufeff") for cell in first_row]
                if _is_header_row(first_row_cleaned):
                    file_headers = first_row_cleaned
                else:
                    # No header, this is data - include it
                    rows_read.append(first_row)
            except StopIteration:
                return generate_headers_for_legacy_file(16), [], 0

            # Read only 'limit' data rows
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                if row:
                    rows_read.append([cell.strip() for cell in row])

            # Estimate total count by counting remaining lines quickly
            total_lines = len(rows_read)
            try:
                # Quick count of remaining lines
                for line in csv_file:
                    if line.strip():
                        total_lines += 1
            except Exception:
                # If counting fails, use what we have
                pass

        if not rows_read:
            headers = [_get_display_name(h) for h in file_headers] if file_headers else generate_headers_for_legacy_file(16)
            return headers, [], 0

        # Process the limited rows
        normalized_rows: List[Dict[str, Any]] = []
        for row in rows_read:
            if not row:
                continue
            row_dict = intelligent_column_mapping(row, headers=file_headers)
            normalized_rows.append(row_dict)

        # Determine headers
        if file_headers:
            headers_list = [_get_display_name(h) for h in file_headers]
        else:
            headers_list = generate_headers_for_legacy_file(16)

        return headers_list, normalized_rows, total_lines

    except Exception as e:
        logger.error(f"Error reading CSV preview {file_path}: {e}")
        return generate_headers_for_legacy_file(16), [], 0


# search_field_in_files() was removed as it's unused (replaced by OpenSearch-based search in tasks.py)
