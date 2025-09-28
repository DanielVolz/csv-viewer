import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def patch_opensearch(monkeypatch):
    class DummyClient:
        def __init__(self):
            self.indices = MagicMock()
            self.indices.exists.return_value = True
        def search(self, index, body):
            # Simulate different responses based on query body
            # For prefix searches size:0 with aggs
            if body.get('size') == 0 and 'aggs' in body:
                # Return buckets for three locations starting with ABC
                return {
                    'aggregations': {
                        'locations': {
                            'buckets': [
                                {
                                    'key': 'ABC01',
                                    'latest': {
                                        'hits': {
                                            'hits': [
                                                {
                                                    '_source': {
                                                        'totalPhones': 10,
                                                        'totalSwitches': 1,
                                                        'phonesWithKEM': 2,
                                                        'phonesByModel': [{'model': 'M1', 'count': 5}],
                                                        'phonesByModelJustiz': [],
                                                        'phonesByModelJVA': [],
                                                        'vlanUsage': [{'vlan': '10', 'count': 5}],
                                                        'topVLANs': [{'vlan': '10', 'count': 5}],
                                                        'uniqueVLANCount': 1,
                                                        'switches': [{'hostname': 'sw1', 'vlans': [{'vlan': '10', 'count': 5}]}],
                                                        'kemPhones': ['P1', 'P2']
                                                    }
                                                }
                                            ]
                                        }
                                    }
                                },
                                {
                                    'key': 'ABC02',
                                    'latest': {
                                        'hits': {
                                            'hits': [
                                                {
                                                    '_source': {
                                                        'totalPhones': 5,
                                                        'totalSwitches': 1,
                                                        'phonesWithKEM': 1,
                                                        'phonesByModel': [{'model': 'M1', 'count': 3}],
                                                        'phonesByModelJustiz': [],
                                                        'phonesByModelJVA': [],
                                                        'vlanUsage': [{'vlan': '10', 'count': 3}],
                                                        'topVLANs': [{'vlan': '10', 'count': 3}],
                                                        'uniqueVLANCount': 1,
                                                        'switches': [{'hostname': 'sw2', 'vlans': [{'vlan': '10', 'count': 3}]}],
                                                        'kemPhones': ['P3']
                                                    }
                                                }
                                            ]
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            else:
                # Code mode: return single doc (today)
                    return {'hits': {'hits': [{'_source': {
                        'key': 'ABC01', 'query': 'ABC01', 'mode': 'code', 'date': '2099-01-01',
                        'totalPhones': 7, 'totalSwitches': 1,
                        'phonesWithKEM': 1, 'phonesByModel': [{'model': 'M2', 'count': 7}],
                        'phonesByModelJustiz': [], 'phonesByModelJVA': [],
                        'vlanUsage': [], 'topVLANs': [], 'uniqueVLANCount': 0,
                        'switches': [], 'kemPhones': ['K1']
                    }}]}}
    class DummyConfig:
        def __init__(self):
            self.client = DummyClient()
            self.stats_loc_index = 'stats_netspeed_loc'
    # Patch the utils.opensearch.OpenSearchConfig class used inside endpoint
    # The API imports OpenSearch helpers via `from utils.opensearch import opensearch_config`
    # but some modules also refer to `backend.utils.opensearch`, so patch both.
    monkeypatch.setattr('utils.opensearch.OpenSearchConfig', DummyConfig)
    monkeypatch.setattr('backend.utils.opensearch.OpenSearchConfig', DummyConfig)
    monkeypatch.setattr('utils.opensearch.opensearch_config', DummyConfig(), raising=False)
    monkeypatch.setattr('backend.utils.opensearch.opensearch_config', DummyConfig(), raising=False)
    yield

@pytest.mark.parametrize('query,mode', [
    ('A', 'prefix'),
    ('AB', 'prefix'),
    ('ABC', 'prefix'),
    ('ABC0', 'prefix'),
])
def test_fast_by_location_prefix_variants(query, mode):
    r = client.get(f'/api/stats/fast/by_location?q={query}')
    assert r.status_code == 200
    data = r.json()
    assert data['success'] is True, data
    assert data['data']['mode'] == 'prefix'
    assert 'uniqueVLANCount' in data['data']
    assert 'topVLANs' in data['data']
    assert isinstance(data['data']['uniqueVLANCount'], int)
    assert isinstance(data['data']['topVLANs'], list)


def test_fast_by_location_code():
    r = client.get('/api/stats/fast/by_location?q=ABC01')
    assert r.status_code == 200
    body = r.json()
    assert body['success'] is True
    assert body['data']['query'] == 'ABC01'
    assert 'uniqueVLANCount' in body['data']
    assert 'topVLANs' in body['data']
    assert isinstance(body['data']['uniqueVLANCount'], int)
    assert isinstance(body['data']['topVLANs'], list)


def test_fast_by_location_invalid():
    # Invalid pattern (contains dash)
    r = client.get('/api/stats/fast/by_location?q=AB-')
    assert r.status_code == 200
    body = r.json()
    assert body['success'] is False
    assert 'Query must be' in body['message']
