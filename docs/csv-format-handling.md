# CSV Format Handling Architecture

**Last Updated**: 2025-10-09
**Legacy Removal Date**: 2025-10-27

## Overview

The CSV Viewer handles two fundamentally different file types with **completely separate code paths**:

1. **MODERN files** (with headers) - Fully automatic, future-proof
2. **LEGACY files** (no headers) - Pattern detection, temporary solution

## MODERN Files (Header-Based) ✅

### Characteristics
- Filename pattern: `netspeed_YYYYMMDD-HHMMSS.csv`
- **ALWAYS has headers** in first row
- Headers are CamelCase without spaces: `IPAddress`, `PhoneModel`, `MACAddress1`, etc.
- Column count: Currently 19, but **system works with ANY count**

### How It Works
```python
# 1. Read first row from CSV file
file_headers = _read_headers_from_file(file_path, delimiter)
# Result: ['IPAddress', 'PhoneDirectoryNumber', 'PhoneModel', ...]

# 2. Convert to canonical display names
canonical_headers = [_get_display_name(h) for h in file_headers]
# Result: ['IP Address', 'Line Number', 'Model Name', ...]

# 3. Map data rows using headers
row_dict = _map_modern_format_row(row_cells, file_headers)
# Maps: cells[0] -> 'IP Address', cells[1] -> 'Line Number', etc.
```

### Key Functions
- `_read_headers_from_file()` - Reads headers from first row
- `_map_modern_format_row(row, headers)` - Maps cells to canonical names
- `_get_display_name()` - Converts CamelCase to "Display Name"
- `_build_display_order_from_headers()` - Builds column order for display

### Why It's Fully Automatic
1. **No header caching** - Headers read per-file every time
2. **No column count checks** - Works with 10, 19, 25, or ANY count
3. **No code changes** - New columns automatically recognized
4. **No container restart** - Changes instant

### Adding New Columns (For Admin)
```csv
# Old CSV:
IPAddress,PhoneDirectoryNumber,PhoneModel,...

# Add new column - JUST ADD IT!
IPAddress,PhoneDirectoryNumber,PhoneModel,NewColumn,...
```

That's it! The system will:
- ✓ Read the new header automatically
- ✓ Display it in the UI with spaces: "New Column"
- ✓ Store it in OpenSearch
- ✓ Make it searchable

**No code changes. No restarts. It just works.**

### Custom Display Names (Optional)
If you want a different display name than auto-generated:

```python
# In csv_utils.py:
CUSTOM_DISPLAY_NAMES = {
    "IPAddress": "IP Address",          # Custom
    "PhoneModel": "Model Name",         # Custom
    "NewAwesomeField": "Awesome Field"  # Will override "New Awesome Field"
}
```

But you usually don't need this - auto-generation works great!

## LEGACY Files (Pattern Detection) ⚠️

### Characteristics
- Filename pattern: `netspeed.csv.0`, `netspeed.csv.14`, etc.
- **NO headers** - First row is data
- Column counts: 11, 14, or 15 (variable)
- Fields at different positions in different files

### How It Works
```python
# NO headers available - must detect by content
row_cells = ['10.216.73.6', '+4960213981023', 'FCH2410L2L4', ...]

# Scan each cell for patterns
for i, cell in enumerate(row_cells):
    if is_ip_address(cell):  # Matches '10.216.73.6'
        ip_idx = i
    elif is_phone_number(cell):  # Matches '+4960213981023'
        line_idx = i
    elif is_mac_address(cell):  # Matches 'C064E4EC73F8'
        mac_idx = i
    elif is_hostname(cell):  # Matches 'ABx01ZSL4120P.juwin.bayern.de'
        hostname_idx = i

# Build mapping based on detected positions
row_dict = {
    "IP Address": cells[ip_idx],
    "Line Number": cells[line_idx],
    ...
}
```

### Pattern Detection Functions
Located in `_map_legacy_format_with_pattern_detection()`:

```python
def is_ip_address(s: str) -> bool:
    # Checks: 4 octets, each 0-255
    return True if '10.216.73.6' else False

def is_phone_number(s: str) -> bool:
    # Checks: starts with '+', 8+ digits
    return True if '+4960213981023' else False

def is_mac_address(s: str) -> bool:
    # Checks: 12 hex characters
    return True if 'C064E4EC73F8' else False

def is_hostname(s: str) -> bool:
    # Checks: contains 'zsl' and '.de'
    return True if 'ABx01ZSL4120P.juwin.bayern.de' else False

# ... more patterns for port name, subnet mask, VLAN, speed
```

### Why Pattern Detection Is Temporary
1. **Fragile** - Only works if patterns match exactly
2. **Limited** - Can't detect arbitrary new fields
3. **Slow** - Must scan every cell
4. **Complex** - Lots of if/elif logic

### Removal Plan
After **2025-10-27**, all legacy files will be in archives only.
At that point, DELETE the entire legacy section:

```python
# DELETE THIS ENTIRE SECTION (lines ~390-550):
# ============================================================================
# LEGACY FORMAT: Pattern-based detection (TEMPORARY - remove after 2025-10-27)
# ============================================================================
def _map_legacy_format_with_pattern_detection(cells: List[str]) -> Dict[str, str]:
    # ... all this code ...

# DELETE KNOWN_HEADERS dictionary (lines ~44-58)

# DELETE generate_headers_for_legacy_file() function
```

Keep only the modern header-based code!

## Code Structure

### Main Entry Points

#### read_csv_file()
Used by: API endpoints for file preview/download
```python
def read_csv_file(file_path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    # 1. Read CSV
    # 2. Check if first row is headers
    # 3. If headers -> modern path
    # 4. If no headers -> legacy path
    # 5. Merge KEM into Line Number for display
    # 6. Return (headers, rows)
```

#### read_csv_file_normalized()
Used by: Indexing, statistics, backend analytics
```python
def read_csv_file_normalized(file_path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    # 1. Read CSV
    # 2. Check if first row is headers
    # 3. If headers -> modern path
    # 4. If no headers -> legacy path
    # 5. Keep KEM separate (don't merge)
    # 6. Return (headers, rows)
```

### Helper Functions

#### Modern Path
```
_read_headers_from_file(file_path, delimiter)
    ↓
_get_display_name(header)  # Per header
    ↓
_map_modern_format_row(row, headers)
    ↓
_build_display_order_from_headers(headers)
```

#### Legacy Path
```
_is_header_row(row)  # Returns False for legacy
    ↓
_map_legacy_format_with_pattern_detection(cells)
    ↓
generate_headers_for_legacy_file(col_count)
```

## Testing

### Test Modern File
```bash
docker exec csv-viewer-backend-dev python3 -c "
from utils.csv_utils import read_csv_file_normalized
headers, rows = read_csv_file_normalized('/app/data/netspeed/netspeed_20251009-061722.csv')
print(f'Headers: {headers[:5]}...')
print(f'Rows: {len(rows)}')
"
```

### Test Legacy File
```bash
docker exec csv-viewer-backend-dev python3 -c "
from utils.csv_utils import read_csv_file_normalized
headers, rows = read_csv_file_normalized('/app/data/history/netspeed/netspeed.csv.29')
print(f'Headers: {headers[:5]}...')
print(f'Rows: {len(rows)}')
"
```

### Test New Column Addition
1. Add column to modern netspeed CSV: `IPAddress,NewField,PhoneModel,...`
2. Save file
3. File watcher triggers reindex
4. Check UI - "New Field" should appear automatically!

## FAQ

### Q: What if I add a column with 50 characters?
**A**: Works fine! `_get_display_name()` handles any CamelCase name.

### Q: What if the CSV has 100 columns?
**A**: Works fine! System loops through all headers automatically.

### Q: Do I need to update CUSTOM_DISPLAY_NAMES?
**A**: Only if you want a specific name different from auto-generated.

### Q: Can I rename "IP Address" to "Device IP"?
**A**: Yes, but users will see the change. Better to keep consistent names.

### Q: What happens to legacy files after 2025-10-27?
**A**: They go to archives. You can delete the legacy code section.

### Q: How do I know if a file is modern or legacy?
**A**:
- Modern: Has timestamp in filename (`netspeed_20251009-061722.csv`)
- Legacy: Has number suffix (`netspeed.csv.29`)

### Q: Can modern files have semicolon delimiters?
**A**: Yes! Delimiter detection works for both `,` and `;`.

### Q: What if header row is missing from a modern file?
**A**: System falls back to pattern detection (legacy mode).

### Q: Can I force a modern file to use legacy mode?
**A**: No. If it has headers, modern mode is used automatically.

## Summary

✅ **MODERN**: Header-based, fully automatic, future-proof
⚠️ **LEGACY**: Pattern detection, temporary until 2025-10-27
🚫 **NEVER**: Mix the two approaches - they are separate code paths

**Golden Rule**: If you add a new column to modern files, just add it to the CSV.
No code changes. No configuration. No restart. It just works! 🎉
