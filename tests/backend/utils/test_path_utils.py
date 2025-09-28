import pytest

from backend.utils import path_utils
from backend.utils.path_utils import collect_netspeed_files


def test_collect_netspeed_files_includes_rotated_timestamp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(path_utils.settings, "CSV_FILES_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(path_utils.settings, "NETSPEED_CURRENT_DIR", None, raising=False)
    monkeypatch.setattr(path_utils.settings, "NETSPEED_HISTORY_DIR", None, raising=False)
    monkeypatch.setattr(path_utils.settings, "_explicit_data_roots", (), raising=False)
    monkeypatch.setattr(path_utils, "_configured_roots", lambda: [], raising=False)

    netspeed_dir = tmp_path / "netspeed"
    netspeed_dir.mkdir(parents=True)

    current = netspeed_dir / "netspeed_20250927-150339.csv"
    current.write_text("current")

    rotated = netspeed_dir / "netspeed_20250927-150339.csv.0"
    rotated.write_text("rotated")

    older = netspeed_dir / "netspeed_20250925-120000.csv"
    older.write_text("older")

    history_dir = tmp_path / "history" / "netspeed"
    history_dir.mkdir(parents=True)

    legacy = history_dir / "netspeed.csv.1"
    legacy.write_text("legacy")

    historical, current_path, backups = collect_netspeed_files(
        extra_candidates=[tmp_path],
        include_backups=False,
    )

    assert current_path == current
    assert rotated in historical
    assert older in historical
    assert legacy in historical
    assert backups == []
