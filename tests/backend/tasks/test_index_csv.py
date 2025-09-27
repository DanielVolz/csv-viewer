import types
from pathlib import Path

import pytest

from backend.tasks.tasks import index_csv, opensearch_config
from config import settings


@pytest.fixture(autouse=True)
def restore_settings():
    original = bool(getattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", True))
    yield
    setattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", original)


def test_index_csv_skips_when_wait_disabled(monkeypatch):
    monkeypatch.setattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", False, raising=False)

    def fake_quick_ping():
        return False

    monkeypatch.setattr(opensearch_config, "quick_ping", fake_quick_ping)

    def unexpected_index(*args, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("indexing should be skipped when OpenSearch is unavailable")

    monkeypatch.setattr(opensearch_config, "index_csv_file", unexpected_index)

    result = index_csv.run(str(Path("/tmp/netspeed.csv")))

    assert result["status"] == "skipped"
    assert "OpenSearch" in result["message"]
