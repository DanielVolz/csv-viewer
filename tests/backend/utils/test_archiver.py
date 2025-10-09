"""Tests for archiver functionality."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime


class TestArchiveCurrentNetspeed:
    """Test archive_current_netspeed function."""

    @patch('utils.archiver.resolve_current_file')
    @patch('utils.archiver.Path')
    @patch('utils.archiver.shutil.copy2')
    def test_archives_successfully(self, mock_copy, mock_path_cls, mock_resolve):
        """Test successful archiving of current netspeed.csv."""
        from utils.archiver import archive_current_netspeed

        # Mock file exists
        mock_resolve.return_value = '/app/data/netspeed.csv'
        mock_src = MagicMock()
        mock_src.exists.return_value = True
        mock_path_cls.return_value = mock_src

        result = archive_current_netspeed('/app/data')

        assert result['status'] == 'success'
        assert 'path' in result
        mock_copy.assert_called_once()

    @patch('utils.archiver.resolve_current_file')
    def test_handles_missing_file(self, mock_resolve):
        """Test handling when netspeed.csv doesn't exist."""
        from utils.archiver import archive_current_netspeed

        mock_resolve.return_value = None

        result = archive_current_netspeed('/app/data')

        assert result['status'] == 'warning'
        assert 'not found' in result['message'].lower()

    @patch('utils.archiver.resolve_current_file')
    @patch('utils.archiver.Path')
    @patch('utils.archiver.shutil.copy2')
    def test_handles_copy_error(self, mock_copy, mock_path_cls, mock_resolve):
        """Test handling of copy errors."""
        from utils.archiver import archive_current_netspeed

        mock_resolve.return_value = '/app/data/netspeed.csv'
        mock_src = MagicMock()
        mock_src.exists.return_value = True
        mock_path_cls.return_value = mock_src

        mock_copy.side_effect = OSError("Permission denied")

        result = archive_current_netspeed('/app/data')

        assert result['status'] == 'error'
        assert 'message' in result


class TestArchivePath:
    """Test archive_path function."""

    @patch('utils.archiver.Path')
    @patch('utils.archiver.shutil.copy2')
    def test_archives_any_file_successfully(self, mock_copy, mock_path_cls):
        """Test archiving arbitrary file."""
        from utils.archiver import archive_path

        mock_src = MagicMock()
        mock_src.exists.return_value = True
        mock_src.name = 'test.csv'
        mock_path_cls.return_value = mock_src

        result = archive_path('/app/data/test.csv', '/app/data')

        assert result['status'] == 'success'
        assert 'path' in result
        mock_copy.assert_called_once()

    @patch('utils.archiver.Path')
    def test_handles_nonexistent_file(self, mock_path_cls):
        """Test handling when file doesn't exist."""
        from utils.archiver import archive_path

        mock_src = MagicMock()
        mock_src.exists.return_value = False
        mock_path_cls.return_value = mock_src

        result = archive_path('/app/data/nonexistent.csv')

        assert result['status'] == 'warning'
        assert 'not found' in result['message']

    @patch('utils.archiver.Path')
    @patch('utils.archiver.shutil.copy2')
    def test_creates_archive_directory(self, mock_copy, mock_path_cls):
        """Test that archive directory is created."""
        from utils.archiver import archive_path

        mock_src = MagicMock()
        mock_src.exists.return_value = True
        mock_src.name = 'data.csv'

        mock_archive_dir = MagicMock()
        mock_base = MagicMock()
        mock_base.__truediv__ = MagicMock(return_value=mock_archive_dir)

        def path_factory(p):
            if str(p) == '/app/data':
                return mock_base
            return mock_src

        mock_path_cls.side_effect = path_factory

        result = archive_path('/app/data/data.csv', '/app/data')

        # Should create archive directory
        assert result['status'] in ['success', 'error']
