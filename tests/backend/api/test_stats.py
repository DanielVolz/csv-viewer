import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from backend.main import app

client = TestClient(app)


class TestStatsAPI:
    @patch('api.stats.Path')
    @patch('api.stats.FileModel')
    @patch('api.stats.read_csv_file_normalized')
    def test_current_stats_success(self, mock_read, mock_filemodel, mock_path):
        # Mock Path chain so (Path('/app/data') / filename).resolve().exists() -> True
        dir_mock = MagicMock()
        file_mock = MagicMock()
        dir_mock.__truediv__.return_value = file_mock
        file_mock.resolve.return_value = file_mock
        file_mock.exists.return_value = True
        mock_path.return_value = dir_mock

        # Mock rows
        rows = [
            {"Switch Hostname": "ABC01-SW1", "KEM": "1", "Model Name": "CP-8841"},
            {"Switch Hostname": "ABC01-SW2", "KEM": "", "Model Name": "CP-7841"},
            {"Switch Hostname": "XYZ02-SW3", "KEM": "", "Model Name": "Unknown"},
        ]
        mock_read.return_value = (["h1"], rows)

        # Mock FileModel
        fm = MagicMock()
        fm.name = 'netspeed.csv'
        fm.date = MagicMock()
        fm.date.strftime.return_value = '2025-08-13'
        mock_filemodel.from_path.return_value = fm

        r = client.get('/api/stats/current')
        assert r.status_code == 200
        data = r.json()
        assert data['success'] is True
        assert data['data']['totalPhones'] == 3
        assert data['data']['totalSwitches'] == 3
        # ABC01 and XYZ02 are two unique locations
        assert data['data']['totalLocations'] == 2
        assert data['data']['phonesWithKEM'] == 1
        assert any(m['model'] == 'CP-8841' for m in data['data']['phonesByModel'])

    @patch('api.stats.Path')
    def test_current_stats_not_found(self, mock_path):
        # Mimic Path('/app/data') / filename chain
        dir_mock = MagicMock()
        file_mock = MagicMock()
        dir_mock.__truediv__.return_value = file_mock
        file_mock.resolve.return_value = file_mock
        file_mock.exists.return_value = False
        mock_path.return_value = dir_mock
        r = client.get('/api/stats/current')
        assert r.status_code == 200
        body = r.json()
        assert body['success'] is False
        assert 'not found' in body['message'].lower()

    @patch('api.stats.Path')
    @patch('api.stats.read_csv_file_normalized')
    def test_list_locations(self, mock_read, mock_path):
        mock_path.return_value = MagicMock(**{"exists.return_value": True})
        rows = [
            {"Switch Hostname": "AAA01-SW1"},
            {"Switch Hostname": "AAA02-SW2"},
            {"Switch Hostname": "BBB03-SW3"},
            {"Switch Hostname": "invalid"},
        ]
        mock_read.return_value = ([], rows)
        r = client.get('/api/stats/locations?q=AAA')
        assert r.status_code == 200
        opts = r.json()['options']
        assert any(opt.startswith('AAA') for opt in opts)

    @patch('api.stats.Path')
    @patch('api.stats.read_csv_file_normalized')
    def test_stats_by_location_code_and_prefix(self, mock_read, mock_path):
        mock_path.return_value = MagicMock(**{"exists.return_value": True})
        rows = [
            {"Switch Hostname": "AAA01-SW1", "Model Name": "CP-8841", "Voice VLAN": "20", "KEM": ""},
            {"Switch Hostname": "AAA01-SW2", "Model Name": "CP-7841", "Voice VLAN": "20", "KEM": "1"},
            {"Switch Hostname": "BBB03-SW3", "Model Name": "CP-7841", "Voice VLAN": "30", "KEM": ""},
        ]
        mock_read.return_value = ([], rows)

        # exact code
        rc = client.get('/api/stats/by_location?q=AAA01')
        assert rc.status_code == 200
        dc = rc.json()['data']
        assert dc['totalPhones'] == 2
        # 3-letter prefix
        rp = client.get('/api/stats/by_location?q=AAA')
        assert rp.status_code == 200
        dp = rp.json()['data']
        assert dp['totalPhones'] == 2

    @patch('api.stats.Path')
    @patch('api.stats.read_csv_file_normalized')
    def test_stats_by_location_invalid(self, mock_read, mock_path):
        mock_path.return_value = MagicMock(**{"__truediv__.return_value.resolve.return_value.exists.return_value": True})
        mock_read.return_value = ([], [])
        r = client.get('/api/stats/by_location?q=AA')
        assert r.status_code == 200
        body = r.json()
        assert body['success'] is False
        assert '5-char code' in body['message'] or '5-char' in body['message']
