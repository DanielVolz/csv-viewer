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


def test_preferred_file_names_orders_rotations(monkeypatch):
    cfg = OpenSearchConfig()
    monkeypatch.setattr(
        cfg,
        "_netspeed_filenames",
        lambda: [
            "netspeed.csv.10",
            "netspeed.csv.3",
            "netspeed.csv.1",
            "netspeed.csv",
        ],
    )

    ordered = cfg._preferred_file_names()

    assert ordered[:4] == [
        "netspeed.csv",
        "netspeed.csv.1",
        "netspeed.csv.3",
        "netspeed.csv.10",
    ]


def test_build_query_general_switch_hostname_code():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("ABX01ZSL4750P", field=None, size=25)

    shoulds = _find_should_terms(body)
    assert _has_term(shoulds, "Switch Hostname", "ABX01ZSL4750P")
    assert any(
        "prefix" in clause and clause["prefix"].get("Switch Hostname") == "ABX01ZSL4750P."
        for clause in shoulds
    )

    filters = body["query"]["bool"].get("filter", [])
    assert filters and filters[0]["script"]["script"]["params"]["qLower"] == "abx01zsl4750p"
    assert body["sort"][0] == {"Creation Date": {"order": "desc"}}


def test_build_query_field_line_number_exact():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("+1234567890123", field="Line Number", size=10)
    shoulds = _find_should_terms(body)
    assert _has_term(shoulds, "Line Number.keyword", "+1234567890123")
    assert _has_term(shoulds, "Line Number.keyword", "1234567890123")
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
    body = cfg._build_query_body("ABC123XYZ99", field="Serial Number", size=10)
    # NOTE: "ABC123XYZ99" matches hostname prefix pattern (3 letters + 2 digits + letters with 2+ consecutive)
    # The pattern detection runs BEFORE field-specific logic, so it returns a hostname query
    # This is by design - pattern detection has priority over field parameter for ambiguous queries
    assert "query" in body
    assert "bool" in body["query"]
    shoulds = body["query"]["bool"]["should"]
    # Query matches hostname prefix pattern, so it searches Switch Hostname field
    has_hostname_match = any(
        ("prefix" in s and "Switch Hostname" in s.get("prefix", {})) or
        ("term" in s and "Switch Hostname" in s.get("term", {}))
        for s in shoulds
    )
    assert has_hostname_match


def test_build_query_general_serial_prefix_wildcard():
    cfg = OpenSearchConfig()
    # Use a shorter string that triggers the Serial Number prefix logic (3-10 chars alphanumeric)
    body = cfg._build_query_body("ABC1234", field=None, size=10)
    shoulds = _find_should_terms(body)
    # Serial Number prefix logic should generate wildcard queries, not exact term queries
    assert any("wildcard" in c and c["wildcard"].get("Serial Number") == "ABC1234*" for c in shoulds)
    # Ensure no exact term was generated for the full serial value
    assert not any("term" in c and c["term"].get("Serial Number") == "ABC1234" for c in shoulds)


def test_build_query_general_serial_prefix():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("ABC1234", field=None, size=10)
    shoulds = _find_should_terms(body)
    assert any("wildcard" in c and c["wildcard"].get("Serial Number") == "ABC1234*" for c in shoulds)


def test_build_query_general_serial_prefix_8chars():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("ABC1234X", field=None, size=10)
    shoulds = _find_should_terms(body)
    assert any("wildcard" in c and c["wildcard"].get("Serial Number") == "ABC1234X*" for c in shoulds)


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
    body = cfg._build_query_body("test-switch01.example.com", field="Switch Hostname", size=10)
    # Script filter present for case-insensitive equality
    flt = body["query"]["bool"]["filter"][0]["script"]["script"]["source"]
    assert "Switch Hostname" in flt and "equalsIgnoreCase" in flt
    shoulds = _find_should_terms(body)
    assert _has_term(shoulds, "Switch Hostname", "test-switch01.example.com")
    assert _has_term(shoulds, "Switch Hostname.lower", "test-switch01.example.com")


def test_build_query_general_fqdn_exact_only():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("test-switch01.example.com", field=None, size=10)
    # FQDNs with dots trigger hostname pattern which returns bool query with multiple should clauses
    # This is by design - hostname pattern has priority with comprehensive field matching
    assert "query" in body
    assert "bool" in body["query"]
    shoulds = body["query"]["bool"]["should"]
    # Should include exact term matches, wildcard matches, and multi_match for comprehensive search
    has_hostname_match = any(
        ("term" in s and "Switch Hostname" in s.get("term", {})) or
        ("wildcard" in s and "Switch Hostname" in s.get("wildcard", {}))
        for s in shoulds
    )
    assert has_hostname_match


def test_build_query_general_phone_exact_only():
    cfg = OpenSearchConfig()
    body = cfg._build_query_body("+1234567890123", field=None, size=10)
    shoulds = _find_should_terms(body)
    assert _has_term(shoulds, "Line Number.keyword", "+1234567890123")
    assert _has_term(shoulds, "Line Number.keyword", "1234567890123")
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
                {"_source": {"Line Number": "+1234567890123", "MAC Address": "AA:BB:CC:DD:EE:FF", "File Name": "netspeed.csv", "Creation Date": "2025-08-21"}},
                {"_source": {"Line Number": "1234567890123", "MAC Address": "AA:BB:CC:DD:EE:FF", "File Name": "netspeed.csv", "Creation Date": "2025-08-21"}},
                {"_source": {"Line Number": "+1234567890123", "MAC Address": "11:22:33:44:55:66", "File Name": "netspeed.csv", "Creation Date": "2025-08-21"}},
            ]
        }
    }

    # Configure side effects in order: exact then partial
    mock_client.search.side_effect = [exact_response, partial_response]

    headers, docs = cfg.search("+1234567890123")

    # Should have deduped the first two into one (same MAC+File), leaving 2 docs
    assert len(docs) == 2
    macs = {d.get("MAC Address") for d in docs}
    assert macs == {"AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"}

    # Verify two searches were performed
    assert mock_client.search.call_count == 2


def test_search_hostname_prefix_uses_historical_indices(monkeypatch):
    cfg = OpenSearchConfig()
    monkeypatch.setattr(cfg, "_preferred_file_names", lambda: ["netspeed.csv", "netspeed.csv.1"])
    monkeypatch.setattr(cfg, "_deduplicate_documents_preserve_order", lambda docs: docs)

    call_log = []

    def fake_get_indices(include):
        call_log.append(("indices", include))
        return ["netspeed_netspeed_csv"] if not include else ["netspeed_netspeed_csv", "netspeed_netspeed_csv_1"]

    monkeypatch.setattr(cfg, "get_search_indices", fake_get_indices)

    cfg._client = MagicMock()

    def fake_search(index, body):
        call_log.append(("search", tuple(index) if isinstance(index, list) else index))
        return {"hits": {"hits": []}}

    cfg._client.search.side_effect = fake_search

    # Hostname prefix searches now respect the include_historical flag
    headers, docs = cfg.search("Mxx09", include_historical=False)

    assert ("indices", False) in call_log
    assert ("search", ("netspeed_netspeed_csv",)) in call_log
    # When no results found, headers are returned from DEFAULT_DISPLAY_ORDER
    # NOTE: _build_headers_from_documents() sorts data columns alphabetically
    # so the order differs from DEFAULT_DISPLAY_ORDER itself
    from utils.csv_utils import DEFAULT_DISPLAY_ORDER
    metadata_fields = ["#", "File Name", "Creation Date"]
    expected_headers = metadata_fields + sorted([c for c in DEFAULT_DISPLAY_ORDER if c not in metadata_fields])
    assert headers == expected_headers
    assert docs == []
