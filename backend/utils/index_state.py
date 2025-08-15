import json
import os
import hashlib
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any


def _env_host(url: str) -> str:
    try:
        p = urlparse(url)
        return p.hostname or url
    except Exception:
        return url or ""


def _compute_state_file() -> Path:
    """Resolve a per-environment state file path.

    Priority:
    1) INDEX_STATE_FILE env var (explicit override)
    2) Namespaced file under /app/data based on Redis/OpenSearch hosts
    3) Fallback legacy path /app/data/.index_state.json
    """
    override = os.environ.get("INDEX_STATE_FILE")
    if override:
        return Path(override)

    # Store state inside the container/repo, not in the mounted CSV directory
    base_dir = Path("/app/var/index_state")
    try:
        # Late import to avoid circulars in some contexts
        from config import settings as _settings
        redis_url = getattr(_settings, "REDIS_URL", "") or ""
        os_url = getattr(_settings, "OPENSEARCH_URL", "") or ""
    except Exception:
        redis_url = os.environ.get("REDIS_URL", "")
        os_url = os.environ.get("OPENSEARCH_URL", "")

    key = f"{_env_host(redis_url)}|{_env_host(os_url)}".strip()
    if key:
        h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        name = f".index_state.{h}.json"
    else:
        # No env info available; use legacy name
        name = ".index_state.json"
    return base_dir / name


STATE_FILE = _compute_state_file()

def _now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

def load_state() -> Dict[str, Any]:
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                # Ensure new keys exist
                if "totals" not in state:
                    state["totals"] = {"files_processed": 0, "total_documents": 0}
                if "files" not in state:
                    state["files"] = {}
                if "active" not in state:
                    state["active"] = None
                if "last_run" not in state:
                    state["last_run"] = None
                if "last_success" not in state:
                    state["last_success"] = None
                return state
    except Exception:
        pass
    return {"last_run": None, "last_success": None, "files": {}, "totals": {"files_processed": 0, "total_documents": 0}, "active": None}

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

def start_active(state: Dict[str, Any], task_id: str, total_files: int) -> None:
    state["active"] = {
        "task_id": task_id,
        "status": "running",
        "started_at": _now_iso(),
        "current_file": None,
        "index": 0,
        "total_files": total_files,
        "documents_indexed": 0,
        "last_file_docs": 0
    }

def update_active(state: Dict[str, Any], **kwargs: Any) -> None:
    if not state.get("active"):
        return
    state["active"].update(kwargs)

def clear_active(state: Dict[str, Any], final_status: str) -> None:
    if not state.get("active"):
        return
    state["active"]["status"] = final_status
    # Keep a minimal history of last run inside active until next start; caller may also set last_success
    # Frontend treats non-running as finished and will rely on last_success timestamp for health.
    # Optionally could null it out:
    # state["active"] = None
