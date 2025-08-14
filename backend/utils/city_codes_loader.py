import json
import os
from pathlib import Path
from typing import Dict, List, Optional


def _pad_code(code: str) -> str:
    """Normalize license plate code to 3-letter padded form using 'X' (e.g., M->MXX, HH->HHX)."""
    c = (code or "").strip().upper()
    if not c:
        return c
    if len(c) >= 3:
        return c[:3]
    return (c + "XXX")[:3]


_DEFAULT_PATHS: List[str] = [
    str(Path(__file__).parent / "city_codes.json"),
    "/app/data/city_codes.json",
]

_CACHE_MAP: Dict[str, str] = {}
_CACHE_MTIMES: Dict[str, float] = {}


def load_city_code_map(paths: Optional[List[str]] = None) -> Dict[str, str]:
    """Load a mapping of 3-letter city codes to names from JSON files.

    The JSON may contain keys in 1-3 letter natural form (e.g., "M", "HH", "ABC")
    or already padded (e.g., "MXX", "HHX", "ABC"). All keys are normalized to
    a 3-letter padded form.

    Merge order (later files override earlier ones):
      1) backend/utils/city_codes.json (bundled base)
      2) /app/data/city_codes.json (deployment override)

    Returns an empty dict if nothing could be loaded.
    """
    if paths is None:
        paths = list(_DEFAULT_PATHS)
    out: Dict[str, str] = {}
    for p in paths:
        try:
            fp = Path(p)
            if not fp.exists():
                continue
            with fp.open("r", encoding="utf-8") as f:
                raw = json.load(f)
                if not isinstance(raw, dict):
                    continue
                tmp: Dict[str, str] = {}
                for k, v in raw.items():
                    key = _pad_code(str(k))
                    name = str(v).strip()
                    if key and name:
                        tmp[key] = name
                # overlay
                out.update(tmp)
        except Exception:
            # Ignore and continue with next path
            continue
    return out


def get_city_code_map(paths: Optional[List[str]] = None) -> Dict[str, str]:
    """Return a cached city code map, reloading if any source file changed.

    Checks the modification time (mtime) of the known JSON files; if any mtime
    differs from the cached one, reloads and updates the cache.
    """
    global _CACHE_MAP, _CACHE_MTIMES
    if paths is None:
        paths = list(_DEFAULT_PATHS)

    changed = False
    current_mtimes: Dict[str, float] = {}
    for p in paths:
        try:
            st = os.stat(p)
            current_mtimes[p] = st.st_mtime
        except FileNotFoundError:
            current_mtimes[p] = -1.0
        if _CACHE_MTIMES.get(p, None) != current_mtimes[p]:
            changed = True

    if changed or not _CACHE_MAP:
        _CACHE_MAP = load_city_code_map(paths)
        _CACHE_MTIMES = current_mtimes

    return _CACHE_MAP
