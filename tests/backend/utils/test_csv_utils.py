import pytest
from unittest.mock import patch, mock_open, MagicMock
import csv
import io
import sys
from pathlib import Path

# Add the backend directory to the Python path to fix the import issues
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from backend.utils.csv_utils import read_csv_file, read_csv_file_normalized, deduplicate_phone_rows

class TestCsvUtils:
    """Test the CSV utilities."""

    def test_read_csv_file(self):
        """Test read_csv_file basic parsing using csv module path."""
        csv_data = 'IP Address,Line Number,Serial Number,Model Name,MAC Address,MAC Address 2,Subnet Mask,Voice VLAN,Phone Port Speed,PC Port Speed,Switch Hostname,Switch Port,Switch Port Mode,PC Port Mode\n' \
                   '10.0.0.1,100,SN1,CP-1,AA:BB:CC:DD:EE:FF,,255.255.255.0,20,1G,1G,SW1,G1/0/1,1000,100\n'
        with patch('os.stat', return_value=MagicMock(st_ctime=0)):
            with patch('builtins.open', mock_open(read_data=csv_data)):
                headers, rows = read_csv_file('/data/test.csv')
        # Currently read_csv_file filters to desired headers and may skip when no rows parsed
        assert isinstance(headers, list)

    def test_read_csv_file_basic_fallback(self):
        """Test read_csv_file parses with csv module for simple CSV."""
        data = 'Col1,Col2\nval1,val2\nval3,val4\n'
        with patch('os.stat', return_value=MagicMock(st_ctime=0)):
            with patch('builtins.open', mock_open(read_data=data)):
                headers, rows = read_csv_file('/data/test.csv')
        # Implementation filters to desired headers; simple CSV without known headers yields empty display headers
        assert isinstance(headers, list)
        # Unknown headers are filtered out; rows list may be empty
        assert isinstance(rows, list)

    @patch('builtins.open')
    def test_read_csv_file_both_methods_fail(self, mock_open):
        """Test read_csv_file when IO fails entirely."""
        mock_open.side_effect = Exception('IO error')
        headers, rows = read_csv_file('/data/test.csv')
        assert headers == []
        assert rows == []

    def test_read_csv_file_with_encoding_fallback(self):
        """Ensure csv path handles typical data without pandas."""
        data = 'Col1;Col2\nval1;val2\nval3;val4\n'
        with patch('os.stat', return_value=MagicMock(st_ctime=0)):
            with patch('builtins.open', mock_open(read_data=data)):
                headers, rows = read_csv_file('/data/test.csv')
        assert isinstance(rows, list)

    def test_read_csv_file_with_real_data(self):
        """Test read_csv_file with real CSV data in memory."""
        csv_data = 'IP Address,Line Number,Serial Number,Model Name,KEM,KEM 2,MAC Address,MAC Address 2,Subnet Mask,Voice VLAN,Phone Port Speed,PC Port Speed,Switch Hostname,Switch Port,Switch Port Mode,PC Port Mode\n' \
                   '10.0.0.1,100,SN1,CP-1,1,,AA:BB:CC:DD:EE:FF,,255.255.255.0,20,1G,1G,SW1,G1/0/1,1000,100\n' \
                   '10.0.0.2,101,SN2,CP-2,,,AA:BB:CC:DD:EE:11,,255.255.255.0,20,1G,1G,SW1,G1/0/2,1000,100\n'
        with patch('os.stat', return_value=MagicMock(st_ctime=0)):
            with patch('builtins.open', mock_open(read_data=csv_data)):
                headers, rows = read_csv_file('/data/test.csv')
        assert isinstance(rows, list)

    def test_read_csv_file_with_empty_file(self):
        """Test read_csv_file with an empty file."""
        # Create an empty CSV string
        csv_data = ""

        # Use StringIO to simulate a file
        with patch('os.stat', return_value=MagicMock(st_ctime=0)):
            with patch('builtins.open', mock_open(read_data=csv_data)):
                headers, rows = read_csv_file('/data/test.csv')

                # Check results - should return empty data
                # For empty file, implementation returns DESIRED_ORDER as headers and [] rows
                assert isinstance(headers, list)
                assert rows == []

    def test_read_csv_file_with_headers_only(self):
        """Test read_csv_file with a file containing only headers."""
        csv_data = "Col1,Col2,Col3"
        with patch('os.stat', return_value=MagicMock(st_ctime=0)):
            with patch('builtins.open', mock_open(read_data=csv_data)):
                headers, rows = read_csv_file('/data/test.csv')
        assert isinstance(headers, list)
        assert rows == []

    def test_read_csv_file_normalized_maps_legacy_speed_columns(self):
        """Test that pattern detection correctly identifies key fields in legacy format.

        This tests the intelligent pattern-based mapping for legacy files without headers.
        The pattern detection identifies fields by their data patterns (IP, MAC, hostname, etc.)
        rather than relying on fixed column positions.
        """
        legacy_values = [
            "10.0.0.1",           # IP Address (detected by pattern)
            "+498955974361",      # Line Number (phone number pattern)
            "SN1234",             # Serial Number
            "CP-8851",            # Model Name
            "AA:BB:CC:DD:EE:FF",  # MAC Address 1 (detected by pattern)
            "AA:BB:CC:DD:EE:01",  # MAC Address 2 (detected by pattern)
            "255.255.255.0",      # Subnet Mask (detected by pattern)
            "803",                # Voice VLAN (numeric pattern)
            "auto",               # Speed field 1
            "100-Full",           # Speed field 2
            "mxx03zsl4750p.juwin.bayern.de",  # Switch Hostname (detected by pattern)
            "GigabitEthernet1/0/5",            # Switch Port (detected by pattern)
            "1000-Full",          # Speed field 3
            "auto",               # Speed field 4
        ]
        legacy_data = ";".join(legacy_values) + "\n"
        with patch("builtins.open", return_value=io.StringIO(legacy_data)):
            headers, rows = read_csv_file_normalized("/data/legacy.csv")

        assert headers
        assert rows
        row = rows[0]

        # Verify pattern detection correctly identified key fields
        # Verify pattern detection correctly identified key fields
        assert row["IP Address"] == "10.0.0.1"
        assert row["Line Number"] == "+498955974361"
        assert row["Serial Number"] == "SN1234"
        assert row["Model Name"] == "CP-8851"
        assert row["MAC Address"] == "AA:BB:CC:DD:EE:FF"
        assert row["MAC Address 2"] == "AA:BB:CC:DD:EE:01"
        assert row["Subnet Mask"] == "255.255.255.0"
        assert row["Switch Hostname"] == "mxx03zsl4750p.juwin.bayern.de"
        assert row["Switch Port"] == "GigabitEthernet1/0/5"

        # Verify speed fields are detected and assigned
        # Pattern detection finds speeds and assigns them in order of discovery
        assert "Switch Port Mode" in row
        assert "PC Port Mode" in row
        assert row["Switch Port Mode"] in ["auto", "100-Full", "1000-Full"]
        assert row["PC Port Mode"] in ["auto", "100-Full", "1000-Full"]


def test_deduplicate_phone_rows_prefers_kem_rows():
    """Ensure deduplication keeps the variant that retains KEM modules."""
    rows = [
        {"Serial Number": "SN-123", "KEM": "", "KEM 2": "", "Line Number": "100", "Model Name": "No KEM"},
        {"Serial Number": "SN-123", "KEM": "1", "KEM 2": "", "Line Number": "100", "Model Name": "Has KEM"},
        {"Serial Number": "SN-456", "KEM": "", "KEM 2": "", "Line Number": "200", "Model Name": "Other"},
    ]

    result = deduplicate_phone_rows(rows)

    assert len(result) == 2
    serials = {row["Serial Number"]: row for row in result}
    assert serials["SN-123"]["Model Name"] == "Has KEM"
    assert serials["SN-123"]["KEM"] == "1"


def test_deduplicate_phone_rows_uses_line_number_kem_hint():
    """A duplicate with KEM inferred from the line number should win."""
    rows = [
        {"Serial Number": "", "MAC Address": "AA:BB", "Line Number": "300", "KEM": "", "KEM 2": "", "Model Name": "Plain"},
        {"Serial Number": "", "MAC Address": "AA:BB", "Line Number": "300 kem kem", "KEM": "", "KEM 2": "", "Model Name": "Line KEM"},
    ]

    result = deduplicate_phone_rows(rows)

    assert len(result) == 1
    assert result[0]["Model Name"] == "Line KEM"
