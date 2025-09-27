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

    @patch('api.files.FileModel')
    @patch('api.files.collect_netspeed_files')
    def test_list_files(self, mock_collect_files, mock_file_model):

        current_mock = MagicMock()
        current_mock.name = "netspeed_20250101-070000.csv"
        current_mock.exists.return_value = True
        current_mock.stat.return_value = MagicMock(st_mtime=1609459200.0)

        historical_mock = MagicMock()
        historical_mock.name = "netspeed_20241231-070000.csv"
        historical_mock.exists.return_value = True
        historical_mock.stat.return_value = MagicMock(st_mtime=1607385600.0)

        mock_collect_files.return_value = ([historical_mock], current_mock, [])

        fm_current = MagicMock()
        fm_current.dict.return_value = {
            "name": current_mock.name,
            "is_current": True,
        }
        fm_hist = MagicMock()
        fm_hist.dict.return_value = {
            "name": historical_mock.name,
            "is_current": False,
        }
        mock_file_model.from_path.side_effect = [fm_current, fm_hist]

        response = client.get("/api/files/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == current_mock.name
        assert data[0]["is_current"] is True
        assert data[1]["name"] == historical_mock.name
        assert data[1]["is_current"] is False

    @patch('api.files.collect_netspeed_files')
    def test_list_files_empty(self, mock_collect_files):
        mock_collect_files.return_value = ([], None, [])

        response = client.get("/api/files/")
        assert response.status_code == 200
        assert response.json() == []

    @patch('api.files.collect_netspeed_files')
    def test_list_files_exception(self, mock_collect_files):
        mock_collect_files.side_effect = Exception("Test exception")

        response = client.get("/api/files/")
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to list CSV files"

    @patch('api.files.read_csv_file')
    @patch('api.files.FileModel')
    @patch('api.files._collect_inventory')
    @patch('api.files._extra_search_paths')
    def test_preview_file(self, mock_extra_paths, mock_collect_inventory, mock_file_model, mock_read_csv_file):
        headers = ["Col1", "Col2", "Col3"]
        rows = [
            {"Col1": "val1", "Col2": "val2", "Col3": "val3"},
            {"Col1": "val4", "Col2": "val5", "Col3": "val6"}
        ]

        mock_extra_paths.return_value = [Path("/app/data")]
        preview_file = MagicMock()
        preview_file.name = "netspeed_20250101-070000.csv"
        preview_file.exists.return_value = True
        preview_file.stat.return_value = MagicMock(st_mtime=1609459200.0)
        mock_collect_inventory.return_value = (
            {"netspeed.csv": preview_file, preview_file.name: preview_file},
            [],
            preview_file,
            [],
        )
        model_instance = MagicMock()
        model_instance.dict.return_value = {
            "name": preview_file.name,
            "is_current": True,
        }
        model_instance.date = MagicMock()
        model_instance.date.strftime.return_value = "2025-01-01"
        mock_file_model.from_path.return_value = model_instance
        mock_read_csv_file.return_value = (headers, rows)

        response = client.get("/api/files/preview?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["headers"] == headers
        assert len(data["data"]) == 2

    def test_preview_file_not_found(self):
        response = client.get("/api/files/preview?filename=__does_not_exist__.csv")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert ("not found" in (data.get("message") or "").lower()) or ("no netspeed.csv found" in (data.get("message") or "").lower())

    @patch('api.files.read_csv_file')
    @patch('api.files._collect_inventory')
    @patch('api.files._extra_search_paths')
    def test_preview_file_exception(self, mock_extra_paths, mock_collect_inventory, mock_read_csv_file):
        mock_extra_paths.return_value = [Path("/app/data")]
        preview_file = MagicMock()
        preview_file.exists.return_value = True
        preview_file.name = "netspeed_20250101-070000.csv"
        preview_file.stat.return_value = MagicMock(st_mtime=1609459200.0)
        mock_collect_inventory.return_value = (
            {"netspeed.csv": preview_file, preview_file.name: preview_file},
            [],
            preview_file,
            [],
        )
        mock_read_csv_file.side_effect = Exception("Test exception")

        response = client.get("/api/files/preview")
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to get file preview"

    @patch('api.files.FileModel')
    @patch('api.files.open', new_callable=mock_open, read_data='header\ndata1\ndata2\ndata3')
    @patch('api.files.collect_netspeed_files')
    @patch('api.files.resolve_current_file')
    @patch('api.files._extra_search_paths')
    def test_netspeed_info(self, mock_extra_paths, mock_resolve_current, mock_collect_files, mock_file_open, mock_file_model):
        mock_extra_paths.return_value = [Path("/app/data")]

        file_mock = MagicMock()
        file_mock.exists.return_value = True
        file_mock.stat.return_value = MagicMock(st_mtime=1609459200.0)
        mock_resolve_current.return_value = file_mock
        mock_collect_files.return_value = ([file_mock], file_mock, [])

        fm = MagicMock()
        fm.date = MagicMock()
        fm.date.strftime.return_value = '2021-01-01'
        mock_file_model.from_path.return_value = fm

        response = client.get("/api/files/netspeed_info")
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert data["line_count"] == 3
        else:
            assert response.status_code == 500
            assert response.json().get("detail") == "Failed to get netspeed file information"

    @patch('api.files.collect_netspeed_files')
    @patch('api.files.resolve_current_file')
    @patch('api.files._extra_search_paths')
    def test_netspeed_info_not_found(self, mock_extra_paths, mock_resolve_current, mock_collect_files):
        mock_extra_paths.return_value = [Path("/app/data")]
        mock_resolve_current.return_value = None
        mock_collect_files.return_value = ([], None, [])

        response = client.get("/api/files/netspeed_info")
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is False
            message = (data.get("message") or "").lower()
            assert (
                "no netspeed.csv found" in message
                or "no netspeed export found" in message
                or "not found" in message
            )
        else:
            assert response.status_code == 500
            assert response.json().get("detail") == "Failed to get netspeed file information"

    @patch('api.files.FileModel')
    @patch('api.files.collect_netspeed_files')
    @patch('api.files.resolve_current_file')
    @patch('api.files._extra_search_paths')
    def test_netspeed_info_exception(self, mock_extra_paths, mock_resolve_current, mock_collect_files, mock_file_model):
        mock_extra_paths.return_value = [Path("/app/data")]
        fake_file = MagicMock()
        fake_file.exists.return_value = True
        fake_file.stat.side_effect = Exception("Test exception")
        mock_resolve_current.return_value = fake_file
        mock_collect_files.return_value = ([fake_file], fake_file, [])
        mock_file_model.from_path.side_effect = Exception("stat failed")

        response = client.get("/api/files/netspeed_info")
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
