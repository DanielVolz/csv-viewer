import pytest
from unittest.mock import patch, mock_open, MagicMock
import csv
import io
import sys
from pathlib import Path

# Add the backend directory to the Python path to fix the import issues
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from backend.utils.csv_utils import read_csv_file

# Mock pandas for tests that use it
pytest.importorskip("pandas", reason="Pandas is optional for these tests")
try:
    import pandas as pd
except ImportError:
    pd = MagicMock()

class TestCsvUtils:
    """Test the CSV utilities."""

    @patch('pandas.read_csv')
    def test_read_csv_file(self, mock_read_csv):
        """Test read_csv_file function."""
        # Mock pandas DataFrame
        mock_df = pd.DataFrame({
            'Col1': ['val1', 'val3'],
            'Col2': ['val2', 'val4']
        })
        mock_read_csv.return_value = mock_df
        
        # Call read_csv_file
        headers, rows = read_csv_file('/data/test.csv')
        
        # Check results
        assert headers == ['Col1', 'Col2']
        assert len(rows) == 2
        assert rows[0]['Col1'] == 'val1'
        assert rows[0]['Col2'] == 'val2'
        assert rows[1]['Col1'] == 'val3'
        assert rows[1]['Col2'] == 'val4'
        
        # Verify pandas.read_csv was called correctly
        mock_read_csv.assert_called_once_with('/data/test.csv')

    @patch('builtins.open', new_callable=mock_open, read_data='Col1,Col2\nval1,val2\nval3,val4')
    @patch('pandas.read_csv')
    def test_read_csv_file_pandas_exception(self, mock_read_csv, mock_file):
        """Test read_csv_file when pandas.read_csv fails."""
        # Mock pandas.read_csv to raise an exception
        mock_read_csv.side_effect = Exception("Test pandas exception")
        
        # Call read_csv_file
        headers, rows = read_csv_file('/data/test.csv')
        
        # Check results - should fall back to csv module
        assert headers == ['Col1', 'Col2']
        assert len(rows) == 2
        assert rows[0]['Col1'] == 'val1'
        assert rows[0]['Col2'] == 'val2'
        assert rows[1]['Col1'] == 'val3'
        assert rows[1]['Col2'] == 'val4'

    @patch('builtins.open')
    @patch('pandas.read_csv')
    @patch('csv.DictReader')
    def test_read_csv_file_both_methods_fail(self, mock_dict_reader, mock_read_csv, mock_open):
        """Test read_csv_file when both pandas and csv module fail."""
        # Mock pandas.read_csv to raise an exception
        mock_read_csv.side_effect = Exception("Test pandas exception")
        
        # Mock csv.DictReader to raise an exception
        mock_dict_reader.side_effect = Exception("Test csv exception")
        
        # Mock open to return a file-like object
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Call read_csv_file
        headers, rows = read_csv_file('/data/test.csv')
        
        # Check results - should return empty data
        assert headers == []
        assert rows == []

    @patch('builtins.open', new_callable=mock_open, read_data='Col1,Col2\nval1,val2\nval3,val4')
    @patch('pandas.read_csv')
    @patch('csv.DictReader')
    def test_read_csv_file_with_encoding_fallback(self, mock_dict_reader, mock_read_csv, mock_file):
        """Test read_csv_file with encoding fallback."""
        # Mock pandas.read_csv to raise a UnicodeDecodeError
        mock_read_csv.side_effect = UnicodeDecodeError('utf-8', b'', 0, 1, 'Test unicode error')
        
        # Set up the DictReader mock to behave like a real DictReader
        mock_reader = MagicMock()
        mock_reader.__iter__.return_value = [
            {'Col1': 'val1', 'Col2': 'val2'},
            {'Col1': 'val3', 'Col2': 'val4'}
        ]
        mock_dict_reader.return_value = mock_reader
        
        # Call read_csv_file
        headers, rows = read_csv_file('/data/test.csv')
        
        # Check results
        assert len(rows) == 2
        
        # Should have tried different encodings
        assert mock_read_csv.call_count > 1

    def test_read_csv_file_with_real_data(self):
        """Test read_csv_file with real CSV data in memory."""
        # Create a CSV string
        csv_data = "Col1,Col2,Col3\nval1,val2,val3\nval4,val5,val6\nval7,val8,val9"
        
        # Use StringIO to simulate a file
        with patch('builtins.open', mock_open(read_data=csv_data)):
            with patch('pandas.read_csv', side_effect=Exception("Force csv module")):
                # Call read_csv_file
                headers, rows = read_csv_file('/data/test.csv')
                
                # Check results
                assert headers == ['Col1', 'Col2', 'Col3']
                assert len(rows) == 3
                assert rows[0]['Col1'] == 'val1'
                assert rows[0]['Col2'] == 'val2'
                assert rows[0]['Col3'] == 'val3'
                assert rows[1]['Col1'] == 'val4'
                assert rows[2]['Col1'] == 'val7'

    def test_read_csv_file_with_empty_file(self):
        """Test read_csv_file with an empty file."""
        # Create an empty CSV string
        csv_data = ""
        
        # Use StringIO to simulate a file
        with patch('builtins.open', mock_open(read_data=csv_data)):
            with patch('pandas.read_csv', side_effect=Exception("Empty file")):
                # Call read_csv_file
                headers, rows = read_csv_file('/data/test.csv')
                
                # Check results - should return empty data
                assert headers == []
                assert rows == []

    def test_read_csv_file_with_headers_only(self):
        """Test read_csv_file with a file containing only headers."""
        # Create a CSV string with only headers
        csv_data = "Col1,Col2,Col3"
        
        # Use StringIO to simulate a file
        with patch('builtins.open', mock_open(read_data=csv_data)):
            with patch('pandas.read_csv', side_effect=Exception("Headers only")):
                # Call read_csv_file
                headers, rows = read_csv_file('/data/test.csv')
                
                # Check results
                assert headers == ['Col1', 'Col2', 'Col3']
                assert rows == []
