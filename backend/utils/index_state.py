import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

STATE_FILE = Path(os.environ.get("INDEX_STATE_FILE", "/app/data/.index_state.json"))

def _now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

def load_state() -> Dict[str, Any]:
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"last_run": None, "files": {}, "totals": {"files_processed": 0, "total_documents": 0}}

def save_state(state: Dict[str, Any]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(state, f)
        tmp.replace(STATE_FILE)
    except Exception:
        # Best-effort; ignore persistence errors
        pass

def file_signature(path: Path) -> Dict[str, Any]:
    st = path.stat()
    return {"size": st.st_size, "mtime": st.st_mtime}

def is_file_current(path: Path, recorded: Dict[str, Any]) -> bool:
    try:
        sig = file_signature(path)
        return recorded.get("size") == sig["size"] and recorded.get("mtime") == sig["mtime"]
    except FileNotFoundError:
        return False

def update_file_state(state: Dict[str, Any], path: Path, line_count: int, doc_count: int) -> None:
    sig = file_signature(path)
    state["files"][path.name] = {
        **sig,
        "line_count": line_count,
        "doc_count": doc_count,
        "last_indexed": _now_iso(),
    }

def update_totals(state: Dict[str, Any], files_processed: int, total_documents: int) -> None:
    state["last_run"] = _now_iso()
    state["totals"] = {"files_processed": files_processed, "total_documents": total_documents}
