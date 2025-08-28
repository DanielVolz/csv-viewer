import pytest

from backend.api.stats import is_mac_like, extract_location


def test_is_mac_like_various():
    assert is_mac_like("aabbccddeeff")
    assert is_mac_like("AA:BB:CC:DD:EE:FF")
    assert is_mac_like("SEPAA:BB:CC:DD:EE:FF")
    assert is_mac_like("AA-BB-CC-DD-EE-FF")
    assert not is_mac_like("")
    assert not is_mac_like("foo")
    assert not is_mac_like("SEP-foo")


def test_extract_location_happy_and_none():
    # Happy path: letters then digits at start
    assert extract_location("abc01-sw01") == "ABC01"
    # Valid 2-letter city code with X padding
    assert extract_location("ABX01-host") == "ABX01"
    # Invalid: 2 letters + digits without X (should be None)
    assert extract_location("AB01-host") is None
    # Invalid: scattered letters and digits (should be None)
    assert extract_location("xxABC01yy") is None
    # Not enough digits
    assert extract_location("ABC-host") is None
    # Wrong order
    assert extract_location("01ABC-host") is None
    # Empty
    assert extract_location("") is None


# EXCLUDED_LOCATIONS removed: CSV normalization and parsing fixes make exclusions unnecessary.
