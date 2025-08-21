import re
from unittest.mock import MagicMock

import pytest


# Import the real OpenSearch implementation under test
from backend.utils.opensearch import OpenSearchConfig, opensearch_config


@pytest.fixture(autouse=True)
def _silence_logging(monkeypatch):
    import logging
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


def _find_should_terms(body):
    try:
        return body["query"]["bool"].get("should", [])
    except Exception:
        return []


def _has_term(shoulds, field, value):
    return any("term" in c and c["term"].get(field) == value for c in shoulds)


def _has_wildcard(shoulds, field, pattern):
    return any("wildcard" in c and c["wildcard"].get(field) == pattern for c in shoulds)


def test_build_query_field_line_number_exact():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("+4960213981023", field="Line Number", size=10)
    shoulds = _find_should_terms(body)
    assert _has_term(shoulds, "Line Number.keyword", "+4960213981023")
    assert _has_term(shoulds, "Line Number.keyword", "4960213981023")
    assert body["size"] == 1


def test_build_query_field_line_number_wildcard():
    cfg = OpenSearchConfig()
    # Not an exact phone (too short), falls back to fielded should with wildcard on keyword
    body = cfg._build_query_body("398", field="Line Number", size=10)
    shoulds = _find_should_terms(body)
    assert _has_wildcard(shoulds, "Line Number.keyword", "*398*")


def test_build_query_field_ip_exact():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("1.2.3.4", field="IP Address", size=10)
    musts = body["query"]["bool"]["must"]
    assert any("term" in m and m["term"].get("IP Address.keyword") == "1.2.3.4" for m in musts)


def test_build_query_field_ip_partial_prefix():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("10.20.", field="IP Address", size=10)
    shoulds = _find_should_terms(body)
    assert any("prefix" in c and c["prefix"].get("IP Address.keyword") == "10.20" for c in shoulds)
    assert any("prefix" in c and c["prefix"].get("IP Address.keyword") == "10.20." for c in shoulds)


def test_build_query_general_ip_partial_prefix():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("10.20", field=None, size=10)
    shoulds = _find_should_terms(body)
    assert any("prefix" in c and c["prefix"].get("IP Address.keyword") == "10.20" for c in shoulds)
    assert any("prefix" in c and c["prefix"].get("IP Address.keyword") == "10.20." for c in shoulds)


def test_build_query_field_serial_exact():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("FCH2325E9S5", field="Serial Number", size=10)
    musts = body["query"]["bool"]["must"]
    assert any("term" in m and m["term"].get("Serial Number") == "FCH2325E9S5" for m in musts)


def test_build_query_field_switch_port_exact():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("Gi1/0/24", field="Switch Port", size=10)
    # Script filter present and a term for the field
    flt = body["query"]["bool"]["filter"][0]["script"]["script"]["source"]
    assert "Switch Port" in flt and "equalsIgnoreCase" in flt
    shoulds = _find_should_terms(body)
    assert _has_term(shoulds, "Switch Port", "Gi1/0/24")


def test_build_query_field_switch_hostname_exact():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("abx01zsl4120p.juwin.bayern.de", field="Switch Hostname", size=10)
    # Script filter present for case-insensitive equality
    flt = body["query"]["bool"]["filter"][0]["script"]["script"]["source"]
    assert "Switch Hostname" in flt and "equalsIgnoreCase" in flt
    shoulds = _find_should_terms(body)
    assert _has_term(shoulds, "Switch Hostname", "abx01zsl4120p.juwin.bayern.de")
    assert _has_term(shoulds, "Switch Hostname.lower", "abx01zsl4120p.juwin.bayern.de")


def test_build_query_general_fqdn_exact_only():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("abx01zsl4120p.juwin.bayern.de", field=None, size=10)
    # Expect the exact-only FQDN branch with script filter and no hostname wildcards
    q = body["query"]["bool"]
    assert any("script" in f for f in q["filter"])  # script filter used
    shoulds = q["should"]
    assert _has_term(shoulds, "Switch Hostname", "abx01zsl4120p.juwin.bayern.de")
    assert _has_term(shoulds, "Switch Hostname.lower", "abx01zsl4120p.juwin.bayern.de")


def test_build_query_general_phone_exact_only():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("+4960213981023", field=None, size=10)
    shoulds = _find_should_terms(body)
    assert _has_term(shoulds, "Line Number.keyword", "+4960213981023")
    assert _has_term(shoulds, "Line Number.keyword", "4960213981023")
    assert body["size"] == 1


def test_search_phone_exact_then_partial_fallback_dedup(monkeypatch):
    # Use global opensearch_config instance
    cfg = opensearch_config

    # Ensure indices selection is deterministic
    monkeypatch.setattr(cfg, "get_search_indices", lambda include: ["netspeed_netspeed_csv"])  # current-only

    # Mock client
    mock_client = MagicMock()
    cfg._client = mock_client

    # First call (exact): return no hits
    exact_response = {"hits": {"hits": []}}

    # Second call (partial): return multiple hits with duplicates (same MAC+File)
    partial_response = {
        "hits": {
            "hits": [
                {"_source": {"Line Number": "+4960213981023", "MAC Address": "AA:BB:CC:DD:EE:FF", "File Name": "netspeed.csv", "Creation Date": "2025-08-21"}},
                {"_source": {"Line Number": "4960213981023", "MAC Address": "AA:BB:CC:DD:EE:FF", "File Name": "netspeed.csv", "Creation Date": "2025-08-21"}},
                {"_source": {"Line Number": "+4960213981023", "MAC Address": "11:22:33:44:55:66", "File Name": "netspeed.csv", "Creation Date": "2025-08-21"}},
            ]
        }
    }

    # Configure side effects in order: exact then partial
    mock_client.search.side_effect = [exact_response, partial_response]

    headers, docs = cfg.search("+4960213981023")

    # Should have deduped the first two into one (same MAC+File), leaving 2 docs
    assert len(docs) == 2
    macs = {d.get("MAC Address") for d in docs}
    assert macs == {"AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"}

    # Verify two searches were performed
    assert mock_client.search.call_count == 2
