import os
import pytest
from unittest.mock import MagicMock

# Ensure backend in path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from backend.utils.opensearch import opensearch_config

@pytest.fixture(autouse=True)
def disable_startup_tasks(monkeypatch):
    monkeypatch.setenv("DISABLE_STARTUP_TASKS", "1")

class TestMacSearch:
    def setup_method(self):
        # Fresh mock client per test
        self.mock_client = MagicMock()
        opensearch_config._client = self.mock_client

    def test_includes_current_and_historical_and_prioritizes_current(self, monkeypatch):
        # get_search_indices should behave as real: current first + wildcard when include_historical=True
        def get_indices(include_historical=False):
            return ["netspeed_netspeed_csv", "netspeed_*"] if include_historical else ["netspeed_netspeed_csv"]
        monkeypatch.setattr(opensearch_config, 'get_search_indices', get_indices)

        # search side effects based on body content and index param
        def search_side_effect(*, index=None, body=None, **kwargs):
            s = str(body or {})
            # MAC-first targeted current index call
            if index == ["netspeed_netspeed_csv"] and "File Name" in s and "netspeed.csv" in s and "MAC Address" in s:
                return { 'hits': { 'hits': [ { '_source': {
                    'File Name': 'netspeed.csv', 'Creation Date': '2025-08-20', 'MAC Address': 'AABBCCDDEEFF'
                }} ] } }
            # General search across indices (include wildcard)
            if (isinstance(index, list) and "netspeed_*" in index) or index == ["netspeed_*"]:
                return { 'hits': { 'hits': [
                    { '_source': { 'File Name': 'netspeed.csv.1', 'Creation Date': '2025-08-19', 'MAC Address': 'AABBCCDDEEFF' }},
                    { '_source': { 'File Name': 'netspeed.csv.2', 'Creation Date': '2025-08-18', 'MAC Address': 'AABBCCDDEEFF' }},
                ] } }
            return { 'hits': { 'hits': [] } }
        self.mock_client.search.side_effect = search_side_effect

        headers, docs = opensearch_config.search('AA:BB:CC:DD:EE:FF', include_historical=True, size=50)
        file_names = [d.get('File Name') for d in docs]
        # Must contain current and history
        assert 'netspeed.csv' in file_names
        assert any(n and n.startswith('netspeed.csv.') for n in file_names)
        # Current must be first
        assert file_names[0] == 'netspeed.csv'

    def test_fallback_finds_current_when_initial_phases_miss_it(self, monkeypatch):
        def get_indices(include_historical=False):
            return ["netspeed_netspeed_csv", "netspeed_*"] if include_historical else ["netspeed_netspeed_csv"]
        monkeypatch.setattr(opensearch_config, 'get_search_indices', get_indices)

        # Side effects: targeted returns empty; general returns historical; fallback targeted to wildcard returns current
        def search_side_effect(*, index=None, body=None, **kwargs):
            s = str(body or {})
            if index == ["netspeed_netspeed_csv"] and "File Name" in s and "netspeed.csv" in s:
                return { 'hits': { 'hits': [] } }
            if (isinstance(index, list) and "netspeed_*" in index) and "File Name" not in s:
                return { 'hits': { 'hits': [ { '_source': { 'File Name': 'netspeed.csv.3', 'MAC Address': 'AABBCCDDEEFF' } } ] } }
            if index == ["netspeed_*"] and "File Name" in s and "netspeed.csv" in s:
                return { 'hits': { 'hits': [ { '_source': { 'File Name': 'netspeed.csv', 'MAC Address': 'AABBCCDDEEFF' } } ] } }
            return { 'hits': { 'hits': [] } }
        self.mock_client.search.side_effect = search_side_effect

        headers, docs = opensearch_config.search('aabbccddeeff', include_historical=True, size=50)
        file_names = [d.get('File Name') for d in docs]
        assert 'netspeed.csv' in file_names
        assert file_names[0] == 'netspeed.csv'

    def test_mac_query_forces_historical_indices(self, monkeypatch):
        # Even when caller doesn't request historical, MAC-like query should include them
        def get_indices(include_historical=False):
            return ["netspeed_netspeed_csv", "netspeed_*"] if include_historical else ["netspeed_netspeed_csv"]
        monkeypatch.setattr(opensearch_config, 'get_search_indices', get_indices)

        # Track calls and return mixed results
        calls = { 'general_indices': [] }

        def search_side_effect(*, index=None, body=None, **kwargs):
            s = str(body or {})
            # Record general phase indices (not the MAC-first which targets current only)
            if "multi_match" in s:
                calls['general_indices'].append(index)
                return { 'hits': { 'hits': [
                    { '_source': { 'File Name': 'netspeed.csv.0', 'MAC Address': 'AABBCCDDEEFF' }},
                    { '_source': { 'File Name': 'netspeed.csv.1', 'MAC Address': 'AABBCCDDEEFF' }},
                ] } }
            if index == ["netspeed_netspeed_csv"] and "File Name" in s and "netspeed.csv" in s:
                return { 'hits': { 'hits': [ { '_source': { 'File Name': 'netspeed.csv', 'MAC Address': 'AABBCCDDEEFF' } } ] } }
            return { 'hits': { 'hits': [] } }

        self.mock_client.search.side_effect = search_side_effect

        headers, docs = opensearch_config.search('aa:bb:cc:dd:ee:ff', include_historical=False, size=50)
        # Verify that general phase used wildcard (historical) even though include_historical=False
        assert any((isinstance(idx, list) and 'netspeed_*' in idx) or idx == ['netspeed_*'] for idx in calls['general_indices'])
        # And that results span multiple files
        names = [d.get('File Name') for d in docs]
        assert 'netspeed.csv' in names and 'netspeed.csv.0' in names and 'netspeed.csv.1' in names

    def test_mac_query_includes_colon_formatted_historical_without_mac2(self, monkeypatch):
        def get_indices(include_historical=False):
            return ["netspeed_netspeed_csv", "netspeed_*"] if include_historical else ["netspeed_netspeed_csv"]

        monkeypatch.setattr(opensearch_config, 'get_search_indices', get_indices)

        colon_value = 'AA:BB:CC:DD:EE:FF'

        def search_side_effect(*, index=None, body=None, **kwargs):
            should_clauses = (body or {}).get('query', {}).get('bool', {}).get('should', [])

            if index == ["netspeed_netspeed_csv"] and should_clauses:
                colon_clause_present = any(
                    (
                        ('term' in clause and clause['term'].get('MAC Address.keyword') == colon_value)
                        or ('wildcard' in clause and clause['wildcard'].get('MAC Address.keyword') == f"*{colon_value}*")
                        or ('term' in clause and clause['term'].get('MAC Address 2.keyword') == colon_value)
                        or ('wildcard' in clause and clause['wildcard'].get('MAC Address 2.keyword') == f"*{colon_value}*")
                    )
                    for clause in should_clauses
                )
                if not colon_clause_present:
                    return {'hits': {'hits': []}}
                return {'hits': {'hits': [{'_source': {'File Name': 'netspeed.csv', 'MAC Address': colon_value}}]}}

            if (isinstance(index, list) and 'netspeed_*' in index) and should_clauses:
                colon_clause_present = any(
                    (
                        ('term' in clause and clause['term'].get('MAC Address.keyword') == colon_value)
                        or ('wildcard' in clause and clause['wildcard'].get('MAC Address.keyword') == f"*{colon_value}*")
                        or ('term' in clause and clause['term'].get('MAC Address 2.keyword') == colon_value)
                        or ('wildcard' in clause and clause['wildcard'].get('MAC Address 2.keyword') == f"*{colon_value}*")
                    )
                    for clause in should_clauses
                )
                if not colon_clause_present:
                    return {'hits': {'hits': []}}
                return {
                    'hits': {
                        'hits': [
                            {'_source': {'File Name': 'netspeed.csv.4', 'MAC Address': colon_value}},
                            {'_source': {'File Name': 'netspeed.csv.5', 'MAC Address': colon_value}},
                        ]
                    }
                }

            return {'hits': {'hits': []}}

        self.mock_client.search.side_effect = search_side_effect

        headers, docs = opensearch_config.search('aa:bb:cc:dd:ee:ff', include_historical=False, size=50)
        names = [d.get('File Name') for d in docs]
        assert 'netspeed.csv' in names
        assert any(n and n.startswith('netspeed.csv.') for n in names)

    def test_mac_timestamped_files_sorted_descending(self, monkeypatch):
        def get_indices(include_historical=False):
            return ["netspeed_netspeed_csv", "netspeed_*"] if include_historical else ["netspeed_netspeed_csv"]

        monkeypatch.setattr(opensearch_config, 'get_search_indices', get_indices)

        def search_side_effect(*, index=None, body=None, **kwargs):
            body_str = str(body or {})
            if index == ["netspeed_netspeed_csv"]:
                return {'hits': {'hits': []}}
            if (isinstance(index, list) and 'netspeed_*' in index) and 'multi_match' in body_str:
                return {
                    'hits': {
                        'hits': [
                            {'_source': {
                                'File Name': 'netspeed_20250927-150339.csv.24',
                                'Creation Date': '2025-09-27',
                                'MAC Address': '482E72E48944'
                            }},
                            {'_source': {
                                'File Name': 'netspeed_20251020-061607.csv',
                                'Creation Date': '2025-10-20',
                                'MAC Address': '482E72E48944'
                            }},
                            {'_source': {
                                'File Name': 'netspeed_20250928-012001.csv.23',
                                'Creation Date': '2025-09-28',
                                'MAC Address': '482E72E48944'
                            }},
                        ]
                    }
                }
            if index == ["netspeed_*"] and '"File Name": "netspeed.csv"' in body_str:
                return {'hits': {'hits': []}}
            return {'hits': {'hits': []}}

        self.mock_client.search.side_effect = search_side_effect

        _, docs = opensearch_config.search('482E72E48944', include_historical=False, size=50)
        names = [d.get('File Name') for d in docs]

        assert names[0] == 'netspeed_20251020-061607.csv'
        assert names[1] == 'netspeed_20250928-012001.csv.23'
        assert names[2] == 'netspeed_20250927-150339.csv.24'
