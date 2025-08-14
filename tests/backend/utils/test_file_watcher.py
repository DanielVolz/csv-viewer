from types import SimpleNamespace
from pathlib import Path
import pytest


@pytest.fixture
def fake_index_all(monkeypatch):
    """Provide a fake index_all_csv_files with a .delay method that records calls."""
    calls = []

    class FakeTask:
        def __init__(self, task_id="task-123"):
            self.id = task_id

    class FakeIndexAll:
        def delay(self, data_dir):
            calls.append(data_dir)
            return FakeTask()

    import backend.utils.file_watcher as fw
    fake = FakeIndexAll()
    monkeypatch.setattr(fw, "index_all_csv_files", fake)
    return calls


@pytest.fixture
def fake_cleanup(monkeypatch):
    """Patch cleanup_indices_by_pattern to record patterns and return a count."""
    calls = []

    class FakeOSCfg:
        def cleanup_indices_by_pattern(self, pattern):
            calls.append(pattern)
            return 3

    import backend.utils.file_watcher as fw
    monkeypatch.setattr(fw, "opensearch_config", FakeOSCfg())
    return calls


def make_event(path, is_directory=False, dest_path=None):
    return SimpleNamespace(src_path=str(path), is_directory=is_directory, dest_path=str(dest_path) if dest_path else None)


def test_is_netspeed_file_variants():
    from backend.utils.file_watcher import CSVFileHandler

    h = CSVFileHandler("/tmp/data")
    # True cases (based on current implementation)
    assert h._is_netspeed_file(Path("/tmp/data/netspeed.csv"))
    # Historical numeric suffix files do not match with current suffix check
    assert not h._is_netspeed_file(Path("/tmp/data/netspeed.csv.0"))
    assert not h._is_netspeed_file(Path("/tmp/data/netspeed.csv.12"))
    # Other false cases
    assert not h._is_netspeed_file(Path("/tmp/data/netspeed.csv_bak"))
    assert not h._is_netspeed_file(Path("/tmp/data/other.csv"))
    assert not h._is_netspeed_file(Path("/tmp/data/netspeed.csv.0.bak"))


def test_created_event_triggers_reindex(monkeypatch, fake_index_all, fake_cleanup):
    import backend.utils.file_watcher as fw
    from backend.utils.file_watcher import CSVFileHandler

    # Avoid actual sleep in handler
    monkeypatch.setattr(fw.time, "sleep", lambda s: None)
    # Fix time to a stable value
    monkeypatch.setattr(fw.time, "time", lambda: 1000.0)

    h = CSVFileHandler("/app/data")
    ev = make_event("/app/data/netspeed.csv")
    h.on_created(ev)

    # Should clean up indices and schedule reindex once
    assert fake_cleanup == ["netspeed_*"]
    assert fake_index_all == ["/app/data"]


def test_cooldown_prevents_rapid_reindex(monkeypatch, fake_index_all, fake_cleanup):
    import backend.utils.file_watcher as fw
    from backend.utils.file_watcher import CSVFileHandler

    monkeypatch.setattr(fw.time, "sleep", lambda s: None)

    # First call at t=2000.0
    monkeypatch.setattr(fw.time, "time", lambda: 2000.0)
    h = CSVFileHandler("/app/data")
    h.on_modified(make_event("/app/data/netspeed.csv"))

    # Second call within cooldown at same t
    h.on_modified(make_event("/app/data/netspeed.csv"))

    # Now move time past cooldown and call again
    monkeypatch.setattr(fw.time, "time", lambda: 2035.0)  # > 30s cooldown
    h.on_modified(make_event("/app/data/netspeed.csv"))

    # Expect two reindex triggers (first and third calls)
    assert fake_index_all == ["/app/data", "/app/data"]
    assert fake_cleanup == ["netspeed_*", "netspeed_*"]


def test_moved_event_triggers_reindex(monkeypatch, fake_index_all, fake_cleanup):
    import backend.utils.file_watcher as fw
    from backend.utils.file_watcher import CSVFileHandler

    monkeypatch.setattr(fw.time, "sleep", lambda s: None)
    monkeypatch.setattr(fw.time, "time", lambda: 3000.0)

    h = CSVFileHandler("/app/data")
    # Moving netspeed.csv should be detected
    ev = make_event("/app/data/netspeed.csv", dest_path="/app/data/netspeed.csv_bak")
    h.on_moved(ev)

    assert fake_index_all == ["/app/data"]
    assert fake_cleanup == ["netspeed_*"]
