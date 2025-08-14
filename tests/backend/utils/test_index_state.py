from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.utils import index_state as ist


def test_load_state_default_when_missing(tmp_path):
    with patch.object(ist, 'STATE_FILE', tmp_path / '.index_state.json'):
        s = ist.load_state()
        assert isinstance(s, dict)
        assert s.get('files') == {}
        assert 'totals' in s


def test_save_and_load_roundtrip(tmp_path):
    with patch.object(ist, 'STATE_FILE', tmp_path / '.index_state.json'):
        initial = {"last_run": None, "last_success": None, "files": {}, "totals": {"files_processed": 1, "total_documents": 2}, "active": None}
        ist.save_state(initial)
        out = ist.load_state()
        assert out['totals']['files_processed'] == 1
        assert out['totals']['total_documents'] == 2


def test_update_helpers_use_signature(tmp_path):
    f = tmp_path / 'netspeed.csv'
    f.write_text('a')
    with patch.object(ist, 'STATE_FILE', tmp_path / '.index_state.json'):
        s = ist.load_state()
        ist.update_file_state(s, f, line_count=10, doc_count=9)
        assert 'netspeed.csv' in s['files']
        ist.update_totals(s, files_processed=1, total_documents=9)
        assert s['totals']['files_processed'] == 1
        ist.start_active(s, task_id='t1', total_files=2)
        assert s['active']['status'] == 'running'
        ist.update_active(s, index=1, current_file='netspeed.csv')
        assert s['active']['index'] == 1
        ist.clear_active(s, final_status='completed')
        assert s['active']['status'] == 'completed'


def test_is_file_current(tmp_path):
    f = tmp_path / 'netspeed.csv'
    f.write_text('abc')
    sig = ist.file_signature(f)
    assert ist.is_file_current(f, sig) is True
    # Modify file so signature changes
    f.write_text('abcd')
    assert ist.is_file_current(f, sig) is False
