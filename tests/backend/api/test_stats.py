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
    @patch('utils.opensearch.opensearch_config')
    def test_current_stats_success(self, mock_opensearch, mock_filemodel, mock_path):
        # Mock Path chain so (Path('/app/data') / filename).resolve().exists() -> True
        dir_mock = MagicMock()
        file_mock = MagicMock()
        dir_mock.__truediv__.return_value = file_mock
        file_mock.resolve.return_value = file_mock
        file_mock.exists.return_value = True
        mock_path.return_value = dir_mock

        # Mock FileModel
        fm = MagicMock()
        fm.name = 'netspeed.csv'
        fm.date = MagicMock()
        fm.date.strftime.return_value = '2025-08-13'
        mock_filemodel.from_path.return_value = fm

        # Mock OpenSearch response
        mock_client = MagicMock()
        mock_opensearch.client = mock_client
        mock_opensearch.stats_index = 'test_stats'

        # Mock OpenSearch get response with snapshot data
        mock_client.get.return_value = {
            "_source": {
                "totalPhones": 3,
                "totalSwitches": 3,
                "totalLocations": 2,
                "phonesWithKEM": 1,
                "phonesByModel": [{"model": "CP-8841", "count": 1}],
                "cityCodes": ["ABC", "XYZ"]
            }
        }

        r = client.get('/api/stats/current')
        assert r.status_code == 200
        data = r.json()
        assert data['success'] is True
        assert data['data']['totalPhones'] == 3
        assert data['data']['totalSwitches'] == 3
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

    @patch('utils.opensearch.opensearch_config')
    def test_list_locations(self, mock_opensearch):
        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_opensearch.client = mock_client

        # Mock indices exists
        mock_client.indices.exists.return_value = True

        # Mock search response for locations aggregation
        mock_client.search.return_value = {
            "aggregations": {
                "locations": {
                    "buckets": [
                        {"key": "AAA01"},
                        {"key": "AAA02"},
                        {"key": "BBB03"}
                    ]
                }
            }
        }

        r = client.get('/api/stats/locations?q=AAA')
        assert r.status_code == 200
        opts = r.json()['options']
        assert any(opt.startswith('AAA') for opt in opts)

    def test_stats_by_location_code_and_prefix(self):
        # This endpoint is now deprecated and should return an error
        rc = client.get('/api/stats/by_location?q=AAA01')
        assert rc.status_code == 200
        dc = rc.json()
        assert dc['success'] is False
        assert 'deprecated' in dc['message'].lower()

        # Test with prefix too
        rp = client.get('/api/stats/by_location?q=AAA')
        assert rp.status_code == 200
        dp = rp.json()
        assert dp['success'] is False
        assert 'deprecated' in dp['message'].lower()

    def test_stats_by_location_invalid(self):
        # This endpoint is now deprecated and should return an error message
        r = client.get('/api/stats/by_location?q=AA')
        assert r.status_code == 200
        body = r.json()
        assert body['success'] is False
        assert 'deprecated' in body['message'].lower()
