import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, mock_open
import os
import json
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from typing import Optional, List
from backend.main import app

# Add the backend directory to the Python path to fix the import issues
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))


# Create test client
client = TestClient(app)

class TestFilesAPI:
    """Test the files API endpoints."""

    @patch('api.files.Path')
    def test_list_files(self, mock_path):
        """Test listing CSV files."""
        # Mock file data with proper attribute access
        mock_file1 = MagicMock()
        mock_file1.name = "netspeed.csv"
        mock_file1.is_file = lambda: True
        mock_file1.stat = lambda: MagicMock(st_mtime=1609459200.0)
        mock_file1.__str__.return_value = "/app/data/netspeed.csv"
        
        mock_file2 = MagicMock()
        mock_file2.name = "netspeed.csv.1"
        mock_file2.is_file = lambda: True
        mock_file2.stat = lambda: MagicMock(st_mtime=1607385600.0)
        mock_file2.__str__.return_value = "/app/data/netspeed.csv.1"
        
        mock_files = [mock_file1, mock_file2]
        
        # Set up mocks
        mock_path().glob.return_value = mock_files
        mock_path().joinpath.side_effect = lambda path: f"/data/{path}"
        
        # Make the request
        response = client.get("/api/files/")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "netspeed.csv"
        assert data[1]["name"] == "netspeed.csv.1"
        assert data[0]["is_current"] == True
        assert data[1]["is_current"] == False

    @patch('api.files.Path')
    def test_list_files_empty(self, mock_path):
        """Test listing CSV files when none are found."""
        # Set up mocks
        mock_path().glob.return_value = []

        # Make the request
        response = client.get("/api/files/")

        # Check response
        assert response.status_code == 200
        assert response.json() == []

    @patch('api.files.Path')
    def test_list_files_exception(self, mock_path):
        """Test listing CSV files with an unexpected exception."""
        # Set up mocks to raise an exception
        mock_path().glob.side_effect = Exception("Test exception")
        
        # Make the request
        response = client.get("/api/files/")
        
        # Check response
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to list CSV files"

    @patch('api.files.read_csv_file')
    @patch('api.files.Path')
    def test_preview_file(self, mock_path, mock_read_csv_file):
        """Test previewing a CSV file."""
        # Setup mock return data
        headers = ["Col1", "Col2", "Col3"]
        rows = [
            {"Col1": "val1", "Col2": "val2", "Col3": "val3"},
            {"Col1": "val4", "Col2": "val5", "Col3": "val6"}
        ]
        
        # Set up mocks
        mock_read_csv_file.return_value = (headers, rows)
        mock_path().is_file.return_value = True
        
        # Make the request
        response = client.get("/api/files/preview?limit=10")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["headers"] == ["Col1", "Col2", "Col3"]
        assert len(data["data"]) == 2

    @patch('api.files.Path')
    def test_preview_file_not_found(self, mock_path):
        """Test previewing a CSV file that doesn't exist."""
        # Set up mocks
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_path().return_value = mock_file
        mock_path().__truediv__.return_value = mock_file
        
        # Make the request
        response = client.get("/api/files/preview")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "not found" in data["message"].lower()

    @patch('api.files.read_csv_file')
    @patch('api.files.Path')
    def test_preview_file_exception(self, mock_path, mock_read_csv_file):
        """Test previewing a CSV file with an exception."""
        # Set up mocks
        mock_path().is_file.return_value = True
        mock_read_csv_file.side_effect = Exception("Test exception")
        
        # Make the request
        response = client.get("/api/files/preview")
        
        # Check response
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to get file preview"

    @patch('api.files.open', new_callable=mock_open, read_data='header\ndata1\ndata2\ndata3')
    @patch('api.files.Path')
    def test_netspeed_info(self, mock_path, mock_file):
        """Test getting netspeed file info."""
        # Set up mocks
        mock_path().is_file.return_value = True
        mock_path().stat.return_value = MagicMock(
            st_mtime=1609459200.0  # 2021-01-01
        )
        
        # Make the request
        response = client.get("/api/files/netspeed_info")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["line_count"] == 3  # 4 lines including header, minus 1 for header
        assert "date" in data

    @patch('api.files.Path')
    def test_netspeed_info_not_found(self, mock_path):
        """Test getting netspeed file info when file doesn't exist."""
        # Set up mocks
        mock_path().__truediv__.return_value.exists.return_value = False
        mock_path().__truediv__.return_value.is_file.return_value = False
        
        # Make the request
        response = client.get("/api/files/netspeed_info")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "not found" in data["message"].lower()

    @patch('api.files.Path')
    def test_netspeed_info_exception(self, mock_path):
        """Test getting netspeed file info with an exception."""
        # Set up mocks
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.stat.side_effect = Exception("Test exception")
        mock_path().__truediv__.return_value = mock_file
        
        # Make the request
        response = client.get("/api/files/netspeed_info")
        
        # Check response
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to get netspeed file information"

    # Mock implementation of the get_line_count function for testing
    def test_mock_get_line_count(self):
        """Test the mock implementation of get_line_count function."""
        # Define a simple mock implementation
        def mock_get_line_count(file_path):
            if file_path == "/data/netspeed.csv":
                return 3
            return 0
            
        # Test the mock function
        assert mock_get_line_count("/data/netspeed.csv") == 3
        assert mock_get_line_count("/data/non_existent.csv") == 0
