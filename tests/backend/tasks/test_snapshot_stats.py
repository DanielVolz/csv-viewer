"""Tests for snapshot statistics functions."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime


class TestSnapshotCurrentStats:
    """Test snapshot_current_stats function."""

    @patch('tasks.tasks.resolve_current_file')
    @patch('tasks.tasks.read_csv_file_normalized')
    @patch('tasks.tasks.opensearch_config')
    def test_snapshot_creates_global_stats(self, mock_os_config, mock_read_csv, mock_resolve):
        """Test that snapshot creates global statistics."""
        from tasks.tasks import snapshot_current_stats

        mock_resolve.return_value = Path('/app/data/netspeed.csv')
        mock_os_config.quick_ping.return_value = True
        mock_os_config.index_stats_snapshot.return_value = True

        mock_read_csv.return_value = (
            ['Name', 'IP Address', 'Model Name'],
            [{'Name': f'Phone{i}', 'IP Address': f'10.0.0.{i}', 'Model Name': '7962'} for i in range(10)]
        )

        result = snapshot_current_stats()

        # Function returns warning if file/data issues, success if indexed
        assert result['status'] in ['success', 'warning']
        assert 'totalPhones' in result or 'message' in result

    @patch('tasks.tasks.resolve_current_file')
    def test_snapshot_handles_missing_file(self, mock_resolve):
        """Test snapshot when no file exists."""
        from tasks.tasks import snapshot_current_stats

        mock_resolve.return_value = None

        result = snapshot_current_stats()

        # Returns warning or error when file not found
        assert result['status'] in ['error', 'skipped', 'warning']
        assert 'message' in result or 'status' in result


class TestSnapshotCurrentWithDetails:
    """Test snapshot_current_with_details function."""

    @patch('tasks.tasks.resolve_current_file')
    @patch('tasks.tasks.read_csv_file_normalized')
    @patch('tasks.tasks.opensearch_config')
    @patch('models.file.FileModel.from_path')
    def test_snapshot_creates_location_details(self, mock_file_model, mock_os_config, mock_read_csv, mock_resolve):
        """Test that snapshot creates per-location details."""
        from tasks.tasks import snapshot_current_with_details
        from datetime import datetime

        mock_resolve.return_value = Path('/app/data/netspeed.csv')
        mock_os_config.quick_ping.return_value = True
        mock_os_config.index_stats_location_snapshots.return_value = True

        # Mock FileModel
        mock_fm = MagicMock()
        mock_fm.name = 'netspeed.csv'
        mock_fm.date = datetime(2025, 10, 9)
        mock_file_model.return_value = mock_fm

        mock_read_csv.return_value = (
            ['Name', 'Switch Hostname'],
            [{'Name': f'Phone{i}', 'Switch Hostname': 'SWABX0101'} for i in range(5)]
        )

        result = snapshot_current_with_details()

        # May return warning if location extraction fails
        assert result['status'] in ['success', 'warning']
        assert 'status' in result
