from unittest.mock import MagicMock
from pathlib import Path

import pytest

from backend.utils.opensearch import opensearch_config


@pytest.fixture(autouse=True)
def _silence_logging(monkeypatch):
    import logging
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


def _fake_netspeed_files(n):
    # netspeed.csv plus .0.. .(n-2) to total n files
    names = ["netspeed.csv"]
    for i in range(n - 1):
        names.append(f"netspeed.csv.{i}")
    return names


def test_mac_historical_limits_to_one_per_file_max_31(monkeypatch):
    cfg = opensearch_config

    # Simulate 31 netspeed files
    files = _fake_netspeed_files(31)

    # Patch Path.glob to return our fake files
    class _P:
        def __init__(self, name):
            self.name = name
    def fake_glob(pattern):
        return [_P(name) for name in files]
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "glob", lambda self, pat: fake_glob(pat))

    # Mock indices and client
    monkeypatch.setattr(cfg, "get_search_indices", lambda include: ["netspeed_*"])
    mock_client = MagicMock()
    cfg._client = mock_client

    # 1) MAC-first exact current: one hit
    mac_first_resp = {"hits": {"hits": [{"_source": {"File Name": "netspeed.csv", "MAC Address": "AA:BB:CC:DD:EE:FF"}}]}}

    # 2) General search: return one hit per file
    gen_hits = [{"_source": {"File Name": fn, "MAC Address": "AA:BB:CC:DD:EE:FF"}} for fn in files]
    general_resp = {"hits": {"hits": gen_hits}}

    mock_client.search.side_effect = [mac_first_resp, general_resp]

    headers, docs = cfg.search("aa:bb:cc:dd:ee:ff", include_historical=True)

    assert len(docs) == len(files) == 31
    assert set(d.get("File Name") for d in docs) == set(files)


def test_line_number_exact_current_only_one(monkeypatch):
    cfg = opensearch_config
    monkeypatch.setattr(cfg, "get_search_indices", lambda include: ["netspeed_netspeed_csv"])  # current-only

    mock_client = MagicMock()
    cfg._client = mock_client

    exact_resp = {"hits": {"hits": [{"_source": {"Line Number": "+4960213981023", "File Name": "netspeed.csv"}}]}}
    mock_client.search.return_value = exact_resp

    headers, docs = cfg.search("+4960213981023", include_historical=False)

    # Exactly one
    assert len(docs) == 1


def test_line_number_exact_historical_one_per_file(monkeypatch):
    cfg = opensearch_config

    files = _fake_netspeed_files(5)
    class _P:
        def __init__(self, name):
            self.name = name
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "glob", lambda self, pat: [_P(name) for name in files])

    # Client returns one hit for each per-file seed request
    mock_client = MagicMock()
    cfg._client = mock_client

    side_effects = []
    for fn in files:
        side_effects.append({"hits": {"hits": [{"_source": {"Line Number": "+4960213981023", "File Name": fn}}]}})

    mock_client.search.side_effect = side_effects

    headers, docs = cfg.search("+4960213981023", include_historical=True)
    assert len(docs) == len(files) == 5
    assert set(d.get("File Name") for d in docs) == set(files)


def test_serial_current_only_one(monkeypatch):
    cfg = opensearch_config
    monkeypatch.setattr(cfg, "get_search_indices", lambda include: ["netspeed_netspeed_csv"])  # current-only

    mock_client = MagicMock()
    cfg._client = mock_client

    resp = {"hits": {"hits": [{"_source": {"Serial Number": "FCH2325E9S5", "File Name": "netspeed.csv"}}]}}
    mock_client.search.return_value = resp

    headers, docs = cfg.search("FCH2325E9S5", include_historical=False)
    assert len(docs) == 1


def test_serial_historical_one_per_file(monkeypatch):
    cfg = opensearch_config
    monkeypatch.setattr(cfg, "get_search_indices", lambda include: ["netspeed_*"])  # any

    mock_client = MagicMock()
    cfg._client = mock_client

    # Return multiple hits across files (with duplicates per file)
    hits = [
        {"_source": {"Serial Number": "FCH2325E9S5", "File Name": "netspeed.csv"}},
        {"_source": {"Serial Number": "FCH2325E9S5", "File Name": "netspeed.csv.0"}},
        {"_source": {"Serial Number": "FCH2325E9S5", "File Name": "netspeed.csv.0"}},
        {"_source": {"Serial Number": "FCH2325E9S5", "File Name": "netspeed.csv.1"}},
    ]
    mock_client.search.return_value = {"hits": {"hits": hits}}

    headers, docs = cfg.search("FCH2325E9S5", include_historical=True)

    # One per file name
    assert len(docs) == 3
    assert set(d.get("File Name") for d in docs) == {"netspeed.csv", "netspeed.csv.0", "netspeed.csv.1"}
