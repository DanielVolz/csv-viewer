import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from backend.main import app

client = TestClient(app)


class _FakeIndices:
    def __init__(self, exists_map=None):
        self._exists_map = exists_map or {}

    def exists(self, index: str) -> bool:
        # default True for both indices used by stats
        return self._exists_map.get(index, True)

    def refresh(self, index: str):
        return None


class _FakeClient:
    def __init__(self, scenario: str):
        self.indices = _FakeIndices()
        self._scenario = scenario

    def search(self, *, index: str, body: dict):
        if self._scenario == "global_timeline" and index == "stats_netspeed":
            # Return three days (14..16), with 15 missing in hits; prefer netspeed.csv over backups
            hits = [
                {"_source": {"file": "netspeed.csv", "date": "2025-08-14", "totalPhones": 10, "totalSwitches": 1, "totalLocations": 1, "totalCities": 1, "phonesWithKEM": 2}},
                {"_source": {"file": "netspeed.csv.1", "date": "2025-08-16", "totalPhones": 25, "totalSwitches": 3, "totalLocations": 2, "totalCities": 2, "phonesWithKEM": 4}},
                {"_source": {"file": "netspeed.csv", "date": "2025-08-16", "totalPhones": 20, "totalSwitches": 3, "totalLocations": 2, "totalCities": 2, "phonesWithKEM": 4}},
            ]
            return {"hits": {"hits": hits}}

        if index == "stats_netspeed_loc":
            # Latest date query
            aggs = body.get("aggs", {})
            if "max_date" in aggs:
                return {"aggregations": {"max_date": {"value": 1.0, "value_as_string": "2025-08-20"}}}

            # Top keys by city
            if "top_keys" in aggs:
                if self._scenario == "top_cities":
                    buckets = [
                        {"key": "MXX", "doc_count": 1, "sumPhones": {"value": 100}},
                        {"key": "NXX", "doc_count": 1, "sumPhones": {"value": 80}},
                    ]
                    return {"aggregations": {"top_keys": {"buckets": buckets}}}

            # Per-key series for cities: by_city -> by_date buckets with sum values
            if self._scenario == "top_cities" and "by_city" in aggs:
                return {
                    "aggregations": {
                        "by_city": {
                            "buckets": [
                                {
                                    "key": "MXX",
                                    "by_date": {
                                        "buckets": [
                                            {"key_as_string": "2025-08-18", "sumPhones": {"value": 2}, "sumSwitches": {"value": 1}, "sumKEM": {"value": 1}},
                                            {"key_as_string": "2025-08-20", "sumPhones": {"value": 3}, "sumSwitches": {"value": 2}, "sumKEM": {"value": 1}},
                                        ]
                                    },
                                },
                                {
                                    "key": "NXX",
                                    "by_date": {
                                        "buckets": [
                                            {"key_as_string": "2025-08-19", "sumPhones": {"value": 5}, "sumSwitches": {"value": 2}, "sumKEM": {"value": 2}},
                                            {"key_as_string": "2025-08-20", "sumPhones": {"value": 6}, "sumSwitches": {"value": 2}, "sumKEM": {"value": 2}},
                                        ]
                                    },
                                },
                            ]
                        }
                    }
                }

            # By-location timeline aggregation: by_date buckets with sum values
            if self._scenario == "by_location" and "by_date" in aggs:
                buckets = [
                    {"key_as_string": "2025-08-10", "sumPhones": {"value": 5}, "sumSwitches": {"value": 1}, "sumKEM": {"value": 1}},
                    {"key_as_string": "2025-08-12", "sumPhones": {"value": 7}, "sumSwitches": {"value": 1}, "sumKEM": {"value": 2}},
                ]
                return {"aggregations": {"by_date": {"buckets": buckets}}}

        # Default empty
        return {"hits": {"hits": []}}


class _FakeOSConfig:
    def __init__(self, scenario: str):
        self.client = _FakeClient(scenario)
        self.stats_index = "stats_netspeed"
        self.stats_loc_index = "stats_netspeed_loc"
        self.archive_index = "archive_netspeed"


@pytest.fixture
def patch_opensearch_global(monkeypatch):
    monkeypatch.setattr("utils.opensearch.opensearch_config", _FakeOSConfig("global_timeline"), raising=True)


@pytest.fixture
def patch_opensearch_by_loc(monkeypatch):
    monkeypatch.setattr("utils.opensearch.opensearch_config", _FakeOSConfig("by_location"), raising=True)


@pytest.fixture
def patch_opensearch_top(monkeypatch):
    monkeypatch.setattr("utils.opensearch.opensearch_config", _FakeOSConfig("top_cities"), raising=True)


def test_global_timeline_earliest_and_carry_forward(patch_opensearch_global):
    r = client.get("/api/stats/timeline?limit=0")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    series = body.get("series") or []
    # Expect 3 days: 14, 15 (carried), 16
    assert len(series) == 3
    dates = [p.get("date") for p in series]
    assert dates == ["2025-08-14", "2025-08-15", "2025-08-16"]
    # Day 15 carries values from day 14
    assert series[1]["metrics"]["totalPhones"] == series[0]["metrics"]["totalPhones"] == 10
    # Day 16 prefers netspeed.csv (20) over backup (25)
    assert series[2]["metrics"]["totalPhones"] == 20


def test_by_location_timeline_prefix_earliest_and_carry_forward(patch_opensearch_by_loc):
    r = client.get("/api/stats/timeline/by_location?q=ABC&limit=0")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    series = body.get("series") or []
    # Expect 3 days window 10..12 with carry-forward on 11
    assert len(series) == 3
    assert [p.get("date") for p in series] == ["2025-08-10", "2025-08-11", "2025-08-12"]
    assert series[0]["metrics"]["totalPhones"] == 5
    assert series[1]["metrics"]["totalPhones"] == 5  # carried forward
    assert series[2]["metrics"]["totalPhones"] == 7


def test_top_cities_timeline_per_key_with_labels(patch_opensearch_top):
    r = client.get("/api/stats/timeline/top_locations?count=2&limit=0&mode=per_key&group=city")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    dates = body.get("dates") or []
    keys = body.get("keys") or []
    series = body.get("seriesByKey") or {}
    labels = body.get("labels") or {}
    # Window should span 18..20 (3 days)
    assert dates == ["2025-08-18", "2025-08-19", "2025-08-20"]
    # Keys include the two cities
    assert set(keys) == {"MXX", "NXX"}
    # Labels include human-readable names; fallback to code if missing
    assert isinstance(labels.get("MXX", "MXX"), str) and labels["MXX"].endswith("(MXX)")
    # Series carry-forward within each key
    assert series["MXX"]["totalPhones"] == [2, 2, 3]
    assert series["NXX"]["totalPhones"] == [0, 5, 6]


def test_top_cities_timeline_limit_last_n_days(patch_opensearch_top):
    r = client.get("/api/stats/timeline/top_locations?count=2&limit=2&mode=per_key&group=city")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    dates = body.get("dates") or []
    # With limit=2 and no anchor, expect last two dates of the window: 19, 20
    assert dates == ["2025-08-19", "2025-08-20"]
