from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from config import settings

NETSPEED_TIMESTAMP_PATTERN = re.compile(r"^netspeed_(\d{8})-(\d{6})\.csv(?:\.(\d+))?$")


def get_data_root() -> Path:
    """Return the canonical container path that holds netspeed data."""
    explicit_roots = _configured_roots()
    if explicit_roots:
        return explicit_roots[0]
    candidates = [
        getattr(settings, "NETSPEED_CURRENT_DIR", None),
        getattr(settings, "NETSPEED_HISTORY_DIR", None),
        getattr(settings, "CSV_FILES_DIR", None),
        "/app/data",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            path = Path(candidate)
            if path.is_file():
                return path.parent
            return path
        except Exception:
            continue
    return Path("/app/data")


def _path_key(path: Path) -> str:
    """Return a normalized key for deduplicating paths."""
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path
    return os.path.normcase(os.path.normpath(str(resolved)))


def _iter_raw_paths(raws: Optional[Iterable[Path | str]]) -> List[Path]:
    out: List[Path] = []
    if not raws:
        return out
    for raw in raws:
        if raw is None:
            continue
        try:
            out.append(Path(raw))
        except Exception:
            continue
    return out


def _as_directory_candidates(path: Path) -> List[Path]:
    """Expand a path into useful directory candidates (keep files and their parents)."""
    candidates: List[Path] = []
    try:
        if path.is_file():
            candidates.append(path.parent)
            candidates.append(path)
        elif path.is_dir():
            candidates.append(path)
        else:
            candidates.append(path)
    except Exception:
        candidates.append(path)
    return candidates


def _dedupe_paths(paths: Iterable[Path]) -> List[Path]:
    seen: set[str] = set()
    unique: List[Path] = []
    for path in paths:
        key = _path_key(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _configured_roots() -> List[Path]:
    raw_roots = getattr(settings, "_explicit_data_roots", ()) or ()
    collected: List[Path] = []
    for raw in raw_roots:
        try:
            path = Path(raw)
        except Exception:
            continue
        if str(path).strip() == "" or path == Path("/"):
            continue
        collected.append(path)
    if not collected:
        return []
    return _dedupe_paths(collected)


def _within_allowed_roots(path: Path, roots: Iterable[Path]) -> bool:
    if not roots:
        return True
    for root in roots:
        try:
            if path == root or path.is_relative_to(root):
                return True
        except AttributeError:
            # Python <3.9 fallback not required in current runtime, but keep safe
            pass
        except Exception:
            pass
        try:
            if root.is_relative_to(path):
                return True
        except AttributeError:
            pass
        except Exception:
            pass
    return False


def _candidate_search_dirs(root: Path) -> List[Path]:
    """Return directories to inspect for netspeed files given a root path."""
    dirs: List[Path] = []
    dirs.append(root)
    dirs.append(root / "netspeed")
    dirs.append(root / "history" / "netspeed")
    return _dedupe_paths(dirs)


def current_directory_candidates(extra: Optional[Iterable[Path | str]] = None) -> List[Path]:
    """Return candidate paths that may contain the current netspeed.csv file."""
    base = get_data_root()
    candidates: List[Path] = []
    for raw in _iter_raw_paths(extra):
        candidates.extend(_as_directory_candidates(raw))
    env_cur = getattr(settings, "NETSPEED_CURRENT_DIR", None)
    if env_cur:
        candidates.extend(_as_directory_candidates(Path(env_cur)))
    candidates.append(base / "netspeed")
    candidates.append(base)
    return _dedupe_paths(candidates)


def history_directory_candidates(extra: Optional[Iterable[Path | str]] = None) -> List[Path]:
    """Return candidate directories that may contain historical netspeed files."""
    base = get_data_root()
    candidates: List[Path] = []
    for raw in _iter_raw_paths(extra):
        candidates.extend(_as_directory_candidates(raw))
    env_hist = getattr(settings, "NETSPEED_HISTORY_DIR", None)
    if env_hist:
        candidates.extend(_as_directory_candidates(Path(env_hist)))
    env_cur = getattr(settings, "NETSPEED_CURRENT_DIR", None)
    if env_cur:
        cur_path = Path(env_cur)
        candidates.extend(_as_directory_candidates(cur_path.parent / "history" / "netspeed"))
        candidates.extend(_as_directory_candidates(cur_path.parent / "history"))
    candidates.append(base / "history" / "netspeed")
    candidates.append(base / "history")
    candidates.append(base)
    return _dedupe_paths(candidates)


def resolve_current_file(extra_candidates: Optional[Iterable[Path | str]] = None) -> Optional[Path]:
    """Resolve the most likely path to the current netspeed.csv file."""
    explicit_roots = _configured_roots()
    candidates = current_directory_candidates(extra_candidates)
    seen: set[str] = set()
    timestamped: List[Tuple[str, int, Path]] = []
    legacy_current: List[Path] = []

    def _consider(path: Path) -> None:
        try:
            if not path.exists() or not path.is_file():
                return
        except Exception:
            return
        key = _path_key(path)
        if key in seen:
            return
        seen.add(key)
        name = path.name
        match = NETSPEED_TIMESTAMP_PATTERN.match(name)
        if match:
            timestamp_key = f"{match.group(1)}{match.group(2)}"
            rotation = match.group(3)
            rotation_order = int(rotation) if rotation is not None else -1
            timestamped.append((timestamp_key, rotation_order, path))
        elif name == "netspeed.csv":
            legacy_current.append(path)

    for cand in candidates:
        try:
            if cand.is_file():
                _consider(cand)
            else:
                for path in cand.glob("netspeed_*.csv*"):
                    _consider(path)
                _consider(cand / "netspeed.csv")
                _consider(cand / "netspeed" / "netspeed.csv")
        except Exception:
            continue

    if timestamped:
        timestamped.sort(key=lambda item: (item[0], item[1]))
        latest_timestamp = timestamped[-1][0]
        latest_group = [item for item in timestamped if item[0] == latest_timestamp]
        latest_group.sort(key=lambda item: item[1])
        return latest_group[0][2]

    if legacy_current:
        legacy_current.sort(key=_current_sort_key)
        return legacy_current[0]

    fallback_candidates: List[Path] = []
    env_current = getattr(settings, "NETSPEED_CURRENT_DIR", None)
    if env_current:
        cur_path = Path(env_current)
        if cur_path.is_file():
            fallback_candidates.append(cur_path)
        else:
            fallback_candidates.append(cur_path / "netspeed.csv")
    try:
        base_dir = get_data_root()
        fallback_candidates.append(base_dir / "netspeed" / "netspeed.csv")
        fallback_candidates.append(base_dir / "netspeed.csv")
    except Exception:
        pass
    fallback_candidates.extend([
        Path("/usr/scripts/netspeed/netspeed.csv"),
        Path("/usr/scripts/netspeed/data/netspeed.csv"),
    ])

    if explicit_roots:
        filtered: List[Path] = []
        for candidate in fallback_candidates:
            target = candidate
            try:
                if not candidate.is_dir():
                    target = candidate.parent
            except Exception:
                target = candidate
            if _within_allowed_roots(target, explicit_roots):
                filtered.append(candidate)
        fallback_candidates = filtered
        if not fallback_candidates:
            return None

    for fallback in fallback_candidates:
        if fallback.exists() and fallback.is_file():
            return fallback
    return None


def resolve_current_directory(extra_candidates: Optional[Iterable[Path | str]] = None) -> Path:
    """Resolve the directory that should contain the current netspeed.csv file."""
    current = resolve_current_file(extra_candidates)
    if current:
        return current.parent
    for cand in current_directory_candidates(extra_candidates):
        try:
            if cand.exists() and cand.is_dir():
                return cand
        except Exception:
            continue
    return get_data_root()


def _is_historical_file(path: Path) -> bool:
    name = path.name
    match = NETSPEED_TIMESTAMP_PATTERN.match(name)
    if match:
        rotation = match.group(3)
        return rotation is not None
    if not name.startswith("netspeed.csv"):
        return False
    if name == "netspeed.csv":
        return False
    if name.startswith("netspeed.csv."):
        suffix = name.split("netspeed.csv.", 1)[1]
        if suffix.endswith("_bak"):
            suffix = suffix[:-4]
        return suffix.isdigit()
    return False


def _is_backup_file(path: Path) -> bool:
    name = path.name
    if name.endswith("_bak"):
        return True
    if name.startswith("netspeed.csv") and name.count("_bak") > 0:
        return True
    return False


def _historical_sort_key(path: Path) -> tuple[int, str, int]:
    name = path.name
    match = NETSPEED_TIMESTAMP_PATTERN.match(name)
    if match:
        rotation = match.group(3)
        rotation_order = int(rotation) if rotation is not None else -1
        return (0, f"{match.group(1)}{match.group(2)}", rotation_order)
    if name.startswith("netspeed.csv."):
        suffix = name.split("netspeed.csv.", 1)[1]
        if suffix.endswith("_bak"):
            suffix = suffix[:-4]
        if suffix.isdigit():
            return (1, f"{int(suffix):06d}", 0)
    return (2, name, 0)


def _current_sort_key(path: Path) -> Tuple[int, str]:
    parent_name = path.parent.name.lower()
    preferred = 0 if parent_name == "netspeed" else 1
    return (preferred, str(path))


def collect_netspeed_files(
    extra_candidates: Optional[Iterable[Path | str]] = None,
    include_backups: bool = True,
) -> Tuple[List[Path], Optional[Path], List[Path]]:
    """Collect netspeed-related files.

    Returns a tuple of (historical_files_sorted, current_file, backup_files_sorted).
    Historical files are sorted ascending by numeric suffix. The current file prefers
    nested layouts (…/netspeed/netspeed.csv). Backups are optional.
    """
    directories: List[Path] = []
    file_candidates: List[Path] = []
    for cand in current_directory_candidates(extra_candidates) + history_directory_candidates(extra_candidates):
        if cand.is_file():
            file_candidates.append(cand)
            directories.append(cand.parent)
        else:
            directories.append(cand)
    directories = _dedupe_paths(directories)

    explicit_roots = _configured_roots()
    if explicit_roots:
        directories = [p for p in directories if _within_allowed_roots(p, explicit_roots)]
        file_candidates = [p for p in file_candidates if _within_allowed_roots(p, explicit_roots)]

    files_map: dict[str, Path] = {}

    def _store(path: Path) -> None:
        try:
            if not path.exists() or not path.is_file():
                return
        except Exception:
            return
        files_map[_path_key(path)] = path

    for file_path in file_candidates:
        _store(file_path)

    for base_dir in directories:
        for search_dir in _candidate_search_dirs(base_dir):
            if explicit_roots and not _within_allowed_roots(search_dir, explicit_roots):
                continue
            if not search_dir.exists() or not search_dir.is_dir():
                continue
            for pattern in ("netspeed.csv*", "netspeed_*.csv*"):
                for path in search_dir.glob(pattern):
                    if not path.is_file():
                        continue
                    _store(path)

    historical: List[Path] = []
    timestamped: List[Tuple[str, int, Path]] = []
    legacy_current: List[Path] = []
    backups: List[Path] = []

    for path in files_map.values():
        name = path.name
        match = NETSPEED_TIMESTAMP_PATTERN.match(name)
        if match:
            timestamp_key = f"{match.group(1)}{match.group(2)}"
            rotation = match.group(3)
            rotation_order = int(rotation) if rotation is not None else -1
            timestamped.append((timestamp_key, rotation_order, path))
        elif name == "netspeed.csv":
            legacy_current.append(path)
        elif _is_historical_file(path):
            historical.append(path)
        elif include_backups and _is_backup_file(path):
            backups.append(path)
        elif include_backups:
            backups.append(path)

    historical.sort(key=_historical_sort_key)
    timestamped.sort(key=lambda item: (item[0], item[1]))
    legacy_current.sort(key=_current_sort_key)
    backups.sort(key=lambda p: (p.parent.name, p.name))

    current_file: Optional[Path] = None

    if timestamped:
        latest_timestamp = timestamped[-1][0]
        latest_group = [item for item in timestamped if item[0] == latest_timestamp]
        latest_group.sort(key=lambda item: item[1])
        current_entry = latest_group[0]
        current_file = current_entry[2]
        for entry in timestamped:
            if entry[2] == current_file:
                continue
            historical.append(entry[2])

    # Ensure historical remains sorted after adding timestamped entries
    historical = sorted({_path_key(path): path for path in historical}.values(), key=_historical_sort_key)

    if current_file is None and legacy_current:
        current_file = legacy_current[0]

    return historical, current_file, backups if include_backups else []


def netspeed_files_ordered(
    extra_candidates: Optional[Iterable[Path | str]] = None,
    include_backups: bool = True,
) -> List[Path]:
    """Return netspeed files ordered as historical -> current -> backups."""
    historical, current, backups = collect_netspeed_files(extra_candidates, include_backups)
    ordered: List[Path] = []
    ordered.extend(historical)
    if current:
        ordered.append(current)
    if include_backups:
        ordered.extend(backups)
    return ordered


__all__ = [
    "get_data_root",
    "current_directory_candidates",
    "history_directory_candidates",
    "resolve_current_file",
    "resolve_current_directory",
    "collect_netspeed_files",
    "netspeed_files_ordered",
]
