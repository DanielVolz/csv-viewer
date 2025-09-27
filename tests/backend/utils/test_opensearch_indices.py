import pytest
from unittest.mock import MagicMock

from config import settings
from backend.utils.opensearch import OpenSearchConfig


class TestGetSearchIndices:
    @pytest.fixture()
    def config(self):
        cfg = OpenSearchConfig()
        cfg._client = MagicMock()
        return cfg

    def _setup_client(self, cfg, *, all_indices, netspeed_meta, docs_counts):
        client = cfg._client

        def _indices_get(index="*"):
            if index == "*":
                return {name: {} for name in all_indices}
            if index == "netspeed_*":
                return netspeed_meta
            raise AssertionError(f"Unexpected index pattern: {index}")

        def _indices_stats(index="*", metric=None):
            if index != "netspeed_*":
                raise AssertionError(f"Unexpected stats pattern: {index}")
            indices_payload = {}
            for name, count in docs_counts.items():
                indices_payload[name] = {"total": {"docs": {"count": count}}}
            return {"indices": indices_payload}

        client.indices.get.side_effect = _indices_get
        client.indices.stats.side_effect = _indices_stats

    def test_prefers_canonical_current_index(self, config):
        self._setup_client(
            config,
            all_indices=["netspeed_netspeed_csv", "netspeed_netspeed_csv_1"],
            netspeed_meta={
                "netspeed_netspeed_csv": {"settings": {"index": {"creation_date": "1700000000000"}}},
                "netspeed_netspeed_csv_1": {"settings": {"index": {"creation_date": "1690000000000"}}},
            },
            docs_counts={
                "netspeed_netspeed_csv": 100,
                "netspeed_netspeed_csv_1": 80,
            },
        )

        indices_current = config.get_search_indices(include_historical=False)
        assert indices_current == ["netspeed_netspeed_csv"]

        indices_hist = config.get_search_indices(include_historical=True)
        assert indices_hist[0] == "netspeed_netspeed_csv"
        assert "netspeed_netspeed_csv_1" in indices_hist
        assert indices_hist[-1] == "netspeed_*"

    def test_uses_latest_timestamped_index_when_canonical_missing(self, config):
        latest_index = "netspeed_netspeed_20250927-105500_csv"
        older_index = "netspeed_netspeed_20250926-105500_csv"
        self._setup_client(
            config,
            all_indices=[latest_index, older_index],
            netspeed_meta={
                latest_index: {"settings": {"index": {"creation_date": "1780000000000"}}},
                older_index: {"settings": {"index": {"creation_date": "1770000000000"}}},
            },
            docs_counts={
                latest_index: 50,
                older_index: 40,
            },
        )

        indices_current = config.get_search_indices(include_historical=False)
        assert indices_current == [latest_index]

        indices_hist = config.get_search_indices(include_historical=True)
        assert indices_hist[0] == latest_index
        assert older_index in indices_hist
        assert indices_hist[-1] == "netspeed_*"

    def test_returns_sentinel_when_no_netspeed_indices(self, config):
        self._setup_client(
            config,
            all_indices=["stats_netspeed_loc"],
            netspeed_meta={},
            docs_counts={},
        )

        indices_current = config.get_search_indices(include_historical=False)
        assert indices_current == ["netspeed_current_only"]

        indices_hist = config.get_search_indices(include_historical=True)
        assert indices_hist == ["netspeed_*"]


class TestWaitForAvailability:
    def test_skips_wait_when_disabled(self, monkeypatch):
        def _fail_client(_self):  # pragma: no cover - should never run if skip works
            raise AssertionError("client accessed despite wait being disabled")

        monkeypatch.setattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", False, raising=False)
        cfg = OpenSearchConfig()
        monkeypatch.setattr(OpenSearchConfig, "client", property(_fail_client))

        result = cfg.wait_for_availability(reason="unit-test")

        assert result is False
