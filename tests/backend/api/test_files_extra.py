import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from starlette.responses import Response

import pytest
from fastapi.testclient import TestClient

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from backend.main import app

client = TestClient(app)


class TestFilesExtraAPI:
    @patch('api.files.index_all_csv_files')
    def test_reindex_triggers_task(self, mock_index):
        mock_task = MagicMock()
        mock_task.id = 'task-123'
        mock_index.delay.return_value = mock_task
        r = client.get('/api/files/reindex')
        assert r.status_code == 200
        body = r.json()
        assert body['success'] is True
        assert body['task_id'] == 'task-123'

    @patch('api.files.Path')
    def test_download_invalid_filename_blocked(self, mock_path):
        # Use a disallowed filename (not starting with netspeed.csv)
        r = client.get('/api/files/download/malicious.txt')
        assert r.status_code == 400
        assert 'Invalid filename' in r.json()['detail']

    @patch('api.files.Path')
    def test_download_file_not_found(self, mock_path):
        # Simulate /app/data/netspeed.csv.9 not existing
        fake_dir = MagicMock()
        fake_path = MagicMock()
        fake_dir.resolve.return_value = Path('/app/data')
        fake_path.resolve.return_value = Path('/app/data/netspeed.csv.9')
        fake_path.exists.return_value = False
        # Configure Path mocks
        mock_path.side_effect = [fake_dir, fake_path]
        r = client.get('/api/files/download/netspeed.csv.9')
        assert r.status_code == 404

    @patch('api.files.FileResponse')
    def test_download_file_success_headers(self, mock_fileresponse):
        # Implement a minimal FakePath that mimics pathlib.Path used in the endpoint
        class FakePath:
            def __init__(self, p):
                self._p = Path(p)
            def resolve(self):
                return self
            @property
            def parents(self):
                return [FakePath(str(pp)) for pp in self._p.parents]
            def __truediv__(self, other):
                return FakePath(str(self._p / other))
            def exists(self):
                return True
            def stat(self):
                return MagicMock(st_size=123)
            def __eq__(self, other):
                try:
                    return str(self._p) == str(other._p)
                except AttributeError:
                    return str(self._p) == str(other)
            def __str__(self):
                return str(self._p)

        # Patch Path inside api.files to return our FakePath
        with patch('api.files.Path', side_effect=lambda p: FakePath(p)):
            # Mock FileResponse to return a real Response with headers
            mock_fileresponse.return_value = Response(
                content=b'',
                media_type='text/csv; charset=utf-8',
                headers={
                    'content-disposition': 'attachment; filename="netspeed.csv"',
                    'content-length': '123'
                }
            )

            r = client.get('/api/files/download/netspeed.csv')
            assert r.status_code == 200
            assert 'content-disposition' in r.headers
            assert r.headers['content-disposition'].startswith('attachment;')
            assert r.headers.get('content-length') == '123'

    def test_columns_success(self):
        r = client.get('/api/files/columns')
        assert r.status_code == 200
        body = r.json()
        assert body['success'] is True
        assert isinstance(body['columns'], list)
        assert any(col['id'] == 'IP Address' for col in body['columns'])

    @patch('api.files.load_state')
    def test_index_status_success(self, mock_load):
        mock_load.return_value = {"last_success": "2025-08-13T06:00:00Z", "active": None}
        r = client.get('/api/files/index/status')
        assert r.status_code == 200
        body = r.json()
        assert body['success'] is True
        assert body['state']['last_success'].startswith('2025')

    # Removed: trigger_morning_reindex endpoint is deprecated (file watcher handles reindexing)

    @patch('api.files.app')
    def test_reload_celery(self, mock_app):
        mock_app.control.purge.return_value = None
        r = client.get('/api/files/reload_celery')
        assert r.status_code == 200
        assert r.json()['message'].startswith('Celery configuration reloaded')
