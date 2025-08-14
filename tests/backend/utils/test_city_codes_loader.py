import json
from pathlib import Path

from backend.utils.city_codes_loader import load_city_code_map


def test_load_city_code_map_normalizes_keys(tmp_path):
    # Given a JSON mapping with mixed-length codes
    data = {
        "M": "München",
        "HH": "Hamburg",
        "ABC": "Alpha City",
        "bad": 123,  # value made str
        "": "",     # skipped
    }
    fp = tmp_path / "city_codes.json"
    fp.write_text(json.dumps(data), encoding="utf-8")

    # When loading with explicit path
    out = load_city_code_map([str(fp)])

    # Then codes are padded to 3 letters and values stringified
    assert out == {
        "MXX": "München",
        "HHX": "Hamburg",
        "ABC": "Alpha City",
        "BAD": "123",
    }


def test_load_city_code_map_missing_returns_empty(tmp_path):
    # Non-existent file should yield empty dict
    out = load_city_code_map([str(tmp_path / "nope.json")])
    assert out == {}


def test_merge_base_then_override(tmp_path):
    # Base contains AOE and ALZ; override replaces AOE only
    base = {
        "AOE": "Altötting",
        "ALZ": "Alzenau",
        "M": "München",
    }
    override = {
        "AOE": "Altötting (Override)",
        "M": "Muenchen",  # also override 1-letter to padded MXX
    }
    base_fp = tmp_path / "base.json"
    ov_fp = tmp_path / "ov.json"
    base_fp.write_text(json.dumps(base), encoding="utf-8")
    ov_fp.write_text(json.dumps(override), encoding="utf-8")

    out = load_city_code_map([str(base_fp), str(ov_fp)])

    # Expect AOE and ALZ present, with AOE overridden; M padded to MXX and overridden
    assert out["AOE"] == "Altötting (Override)"
    assert out["ALZ"] == "Alzenau"
    assert out["MXX"] == "Muenchen"
