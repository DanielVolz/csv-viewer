from fastapi import Query
from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import Dict, List, Tuple, Any, cast
from celery.result import AsyncResult
import logging
import time
import os
import pathlib

from opensearchpy.exceptions import NotFoundError


from models.file import FileModel
from utils.path_utils import get_data_root, collect_netspeed_files
from config import settings
import utils.opensearch as _opensearch_module


class _OpenSearchConfigProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(_opensearch_module.opensearch_config, name)


opensearch_config = _OpenSearchConfigProxy()

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/stats",
    tags=["stats"],
)

# Note: We no longer filter MAC-like strings from model names; any missing model
# will be counted under "Unknown".

# City code map: resolve at call time via mtime-aware loader.
CITY_CODE_MAP: Dict[str, str] = {}
# Simple in-memory caches for speed
_CURRENT_STATS_CACHE: Dict[str, Any] = {"key": None, "data": None}
_TIMELINE_CACHE: Dict[int, Tuple[float, Dict]] = {}  # key: limit, value: (expires_at, result)
_TIMELINE_BY_LOC_CACHE: Dict[Tuple[str, int], Tuple[float, Dict]] = {}  # key: (q, limit)
_TIMELINE_TOP_CACHE: Dict[Tuple[int, Tuple[str, ...], int], Tuple[float, Dict]] = {}
def _preferred_stats_files(limit: int = 12) -> List[str]:
    """Return netspeed filenames prioritizing the currently active export."""
    extras: List[Path | str] = []
    for attr in ("NETSPEED_CURRENT_DIR", "NETSPEED_HISTORY_DIR", "CSV_FILES_DIR"):
        value = getattr(settings, attr, None)
        if value:
            extras.append(Path(value))
    try:
        historical, current, _ = collect_netspeed_files(extras)
    except Exception:
        historical, current = [], None

    names: List[str] = []
    if current:
        names.append(current.name)
    for path in reversed(historical):
        name = getattr(path, "name", None)
        if not name or name in names:
            continue
        names.append(name)
        if len(names) >= limit:
            break
    if "netspeed.csv" not in names:
        names.append("netspeed.csv")
    return names[:limit]


def invalidate_caches(reason: str | None = None) -> None:
    """Clear in-process stats caches so next calls recompute immediately.

    This is meant to be called when a reindex starts or completes.
    """
    try:
        _CURRENT_STATS_CACHE.clear()
    except Exception:
        pass
    try:
        _TIMELINE_CACHE.clear()
    except Exception:
        pass
    try:
        _TIMELINE_BY_LOC_CACHE.clear()
    except Exception:
        pass
    try:
        _TIMELINE_TOP_CACHE.clear()
    except Exception:
        pass
    if reason:
        logger.info(f"Stats caches invalidated: {reason}")

# Force cache invalidation for testing
import time
_CACHE_INVALIDATION_TIME = time.time() + 10
try:
    from utils.city_codes_loader import get_city_code_map
except Exception as _e:
    get_city_code_map = None  # type: ignore
    logger.warning(f"City code loader not available: {_e}")

def resolve_city_name(code3: str) -> str:
    """Return a human-readable city name for a 3-letter padded code (e.g., MXX -> München).

    Falls back to the code itself when unknown.
    """
    c = (code3 or "").strip().upper()
    # Try to read fresh map each call; falls back to last known or code itself.
    try:
        if get_city_code_map:
            m = get_city_code_map()
            return m.get(c, c)
    except Exception as _e:
        logger.warning(f"Failed to load city code map dynamically: {_e}")
    return CITY_CODE_MAP.get(c, c) or c

# Initial warm-up load (non-fatal if missing); further lookups use get_city_code_map()
try:
    if get_city_code_map:
        CITY_CODE_MAP.update(get_city_code_map())
        if CITY_CODE_MAP:
            logger.info(f"Loaded {len(CITY_CODE_MAP)} city codes from file")
except Exception as _e:
    logger.warning(f"City code map initial load failed: {_e}")


def _resolve_data_path(name: str | Path) -> Path:
    """Resolve a path relative to the configured data root."""
    base = get_data_root()
    try:
        if isinstance(name, Path):
            return name if name.is_absolute() else base / name
    except TypeError:
        # Handle case where Path is mocked (MagicMock) in tests
        pass
    text = str(name)
    if os.path.isabs(text):
        return Path(text)
    return base / text


def is_mac_like(value: str) -> bool:
    """Return True if value looks like a MAC address (12 hex, with/without separators, optional SEP prefix)."""
    s = str(value or "").strip().upper()
    if not s:
        return False
    if s.startswith("SEP"):
        s = s[3:]
    hex_only = "".join(ch for ch in s if ch in "0123456789ABCDEF")
    return len(hex_only) == 12


def extract_location(hostname: str) -> str | None:
    """Extract a location code from the switch hostname.

    For hostname formats like:
    - 'ABx01ZSL4120P.juwin.bayern.de' -> 'ABX01' (2 letters + x + 2 digits)
    - 'WORx51ZSL9999P.juwin.bayern.de' -> 'WOR51' (3 letters + 2 digits, skip the 'x')
    - 'ABC01ZSL1234P.juwin.bayern.de' -> 'ABC01' (3 letters + 2 digits)

    Algorithm:
    - Try pattern 1: [A-Z]{2}x[0-9]{2} (2 letters + x + 2 digits) at start
    - Try pattern 2: [A-Z]{3}x[0-9]{2} (3 letters + x + 2 digits, skip the 'x') at start
    - Try pattern 3: [A-Z]{3}[0-9]{2} (3 letters + 2 digits) at start

    Note: There are no 2-character location codes. If city code is 2 chars,
    third position is filled with 'X'.
    """
    if not hostname:
        return None
    h = hostname.strip().upper()
    if len(h) < 4:
        return None

    # Pattern 1: 2 letters + 'x' + 2 digits (e.g., ABX01)
    if (len(h) >= 5 and
        h[0].isalpha() and h[1].isalpha() and
        h[2] == 'X' and
        h[3].isdigit() and h[4].isdigit()):
        return h[:5]

    # Pattern 2: 3 letters + x + 2 digits (e.g., WORx51 -> WOR51)
    if (len(h) >= 6 and
        h[0].isalpha() and h[1].isalpha() and h[2].isalpha() and
        h[3] == 'X' and
        h[4].isdigit() and h[5].isdigit()):
        return h[0:3] + h[4:6]  # Take letters + digits, skip the 'x'

    # Pattern 3: 3 letters + 2 digits (e.g., ABC01)
    if (len(h) >= 5 and
        h[0].isalpha() and h[1].isalpha() and h[2].isalpha() and
        h[3].isdigit() and h[4].isdigit()):
        return h[:5]

    return None


def is_jva_switch(hostname: str) -> bool:
    """Determine if a switch hostname belongs to JVA (Prison) based on location pattern.

    JVA switches have 50 or 51 in the last 2 digits of the location code.
    For example: ABx50 (ABX50), WORx51 (WOR51) are JVA switches.
    All others are Justiz (Justice) switches.

    Args:
        hostname: Switch hostname to analyze

    Returns:
        True if JVA switch, False if Justiz switch
    """
    if not hostname:
        return False

    location = extract_location(hostname)
    if not location:
        return False

    # Check if the last 2 digits are 50 or 51
    if len(location) >= 2:
        last_two_digits = location[-2:]  # Last 2 characters
        return last_two_digits == '50' or last_two_digits == '51'

    return False


def extract_city_code(hostname: str) -> str | None:
    """Extract city code (KFZ-Kennzeichen) from switch hostname.

    For hostname formats like:
    - 'BOC04-DIST3.lan' -> 'BOC'
    - 'MXX17-SW4.example' -> 'MXX'
    - 'QZD18-EDGE3.local' -> 'QZD'

    Returns the first 3 characters before the first digit.
    """
    if not hostname:
        return None

    h = hostname.strip().upper()
    if len(h) < 3:
        return None

    # Find the first digit position
    for i, char in enumerate(h):
        if char.isdigit():
            # Return the letters before the first digit (up to 3 characters)
            city_code = h[:i]
            if len(city_code) >= 2 and city_code.isalpha():
                return city_code[:3]  # Take max 3 characters
            break

    return None


@router.get("/current")
async def get_current_stats(filename: str = "netspeed.csv") -> Dict:
    """Load statistics from OpenSearch snapshots only - NO CSV computation.

    Returns a JSON object with:
      - totalPhones
      - totalSwitches
      - phonesWithKEM
      - phonesByModel: list[{model, count}]
      - file: { name, date }
    """
    try:
        file_path = _resolve_data_path(filename)

        # Get file metadata
        file_model = FileModel.from_path(str(file_path))
        date_str = file_model.date.strftime('%Y-%m-%d') if file_model.date else None

        # ONLY load from OpenSearch snapshots - never CSV
        if date_str:
            try:
                # Try to get snapshot from stats index
                doc_id = f"{file_model.name}:{date_str}"
                try:
                    snap = opensearch_config.client.get(index=opensearch_config.stats_index, id=doc_id)
                    src = snap.get("_source") if isinstance(snap, dict) else None
                except NotFoundError:
                    src = None

                if src:
                    result = {
                        "success": True,
                        "message": "Statistics loaded from OpenSearch snapshot",
                        "data": {
                            "totalPhones": int(src.get("totalPhones", 0)),
                            "totalSwitches": int(src.get("totalSwitches", 0)),
                            "totalLocations": int(src.get("totalLocations", 0)),
                            "totalCities": int(src.get("totalCities", 0)),
                            "phonesWithKEM": int(src.get("phonesWithKEM", 0)),
                            "totalKEMs": int(src.get("totalKEMs", 0)),
                            "totalJustizPhones": int(src.get("totalJustizPhones", 0)),
                            "totalJVAPhones": int(src.get("totalJVAPhones", 0)),

                            # Justiz KPIs
                            "justizSwitches": int(src.get("justizSwitches", 0)),
                            "justizLocations": int(src.get("justizLocations", 0)),
                            "justizCities": int(src.get("justizCities", 0)),
                            "justizPhonesWithKEM": int(src.get("justizPhonesWithKEM", 0)),
                            "totalJustizKEMs": int(src.get("totalJustizKEMs", 0)),

                            # JVA KPIs
                            "jvaSwitches": int(src.get("jvaSwitches", 0)),
                            "jvaLocations": int(src.get("jvaLocations", 0)),
                            "jvaCities": int(src.get("jvaCities", 0)),
                            "jvaPhonesWithKEM": int(src.get("jvaPhonesWithKEM", 0)),
                            "totalJVAKEMs": int(src.get("totalJVAKEMs", 0)),

                            "phonesByModel": src.get("phonesByModel", []),
                            "phonesByModelJustiz": src.get("phonesByModelJustiz", []),
                            "phonesByModelJVA": src.get("phonesByModelJVA", []),
                            "phonesByModelJustizDetails": src.get("phonesByModelJustizDetails", []),
                            "phonesByModelJVADetails": src.get("phonesByModelJVADetails", []),
                            "cities": sorted(
                                [{"code": c, "name": resolve_city_name(c)} for c in (src.get("cityCodes") or [])],
                                key=lambda x: x["name"]
                            ),
                        },
                        "file": {"name": file_model.name, "date": date_str, "is_current": True, "using_fallback": False},
                    }
                    return result
                else:
                    # No snapshot found - trigger reindex
                    return {
                        "success": False,
                        "message": f"No statistics snapshot found for {filename}:{date_str}. Please trigger reindex.",
                        "data": {
                            "totalPhones": 0,
                            "totalSwitches": 0,
                            "totalLocations": 0,
                            "phonesWithKEM": 0,
                            "phonesByModel": [],
                            "totalCities": 0,
                            "cities": [],
                        },
                        "file": {"name": file_model.name, "date": date_str, "is_current": True, "using_fallback": False},
                        "needsReindex": True
                    }
            except Exception as e:
                logger.error(f"Error loading from OpenSearch: {e}")
                return {
                    "success": False,
                    "message": f"Failed to load statistics from OpenSearch: {e}",
                    "data": {
                        "totalPhones": 0,
                        "totalSwitches": 0,
                        "totalLocations": 0,
                        "phonesWithKEM": 0,
                        "phonesByModel": [],
                        "totalCities": 0,
                        "cities": [],
                    },
                    "file": {"name": file_model.name, "date": date_str},
                    "needsReindex": True
                }
        else:
            return {
                "success": False,
                "message": f"File {filename} not found or cannot determine date",
                "data": {
                    "totalPhones": 0,
                    "totalSwitches": 0,
                    "totalLocations": 0,
                    "phonesWithKEM": 0,
                    "phonesByModel": [],
                    "totalCities": 0,
                    "cities": [],
                },
                "file": {"name": filename, "date": None},
            }
    except Exception as e:
        logger.error(f"Error computing stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute statistics")


@router.get("/timeline")
async def get_stats_timeline(limit: int = 0, include_backups: bool = False) -> Dict:
    """Build a time series of key metrics across netspeed files (snapshot-only).

    Behavior change: the series always starts at the earliest available date and
    continues day-by-day to the latest date, carrying forward metrics for
    missing days. If limit > 0, the series is truncated to the first `limit`
    days (still starting from the earliest date). If limit == 0, return full
    history.
    """
    try:
        # limit==0 means full history; otherwise truncate to first N days from earliest
        eff_limit = limit if limit and limit > 0 else 0
        now = time.time()
        cached = _TIMELINE_CACHE.get(eff_limit)
        if cached and cached[0] > now:
            return cached[1]

        # Only use OpenSearch snapshots, never CSV fallback
        # Fetch many hits but respect default max_result_window (10k)
        max_docs = 10000
        # If stats index is missing, try an on-demand backfill once, then continue
        try:
            exists_stats = opensearch_config.client.indices.exists(index=opensearch_config.stats_index)
        except Exception:
            exists_stats = False
        if not exists_stats:
            try:
                from tasks.tasks import backfill_stats_snapshots
                backfill_stats_snapshots()
                try:
                    opensearch_config.client.indices.refresh(index=opensearch_config.stats_index)
                except Exception:
                    pass
            except Exception:
                # proceed; query below will just yield empty
                pass
        body = {
            "size": max_docs,
            "sort": [
                {"date": {"order": "asc", "missing": "_last"}},
                {"file": {"order": "desc"}}  # prefer netspeed.csv when collapsing
            ],
            "query": {"match_all": {}},
            "_source": [
                "file","date","totalPhones","totalSwitches","totalLocations","totalCities","phonesWithKEM"
            ],
        }
        res = opensearch_config.client.search(index=opensearch_config.stats_index, body=body)
        hits = res.get("hits", {}).get("hits", [])
        # Collapse to one point per date, preferring netspeed.csv when multiple files exist for same date
        by_date: Dict[str, Dict] = {}
        for h in hits:
            s = h.get("_source", {})
            d = s.get("date")
            f = s.get("file") or ""
            if not d:
                continue
            if d not in by_date:
                by_date[d] = {
                    "file": f,
                    "date": d,
                    "metrics": {
                        "totalPhones": s.get("totalPhones", 0),
                        "totalSwitches": s.get("totalSwitches", 0),
                        "totalLocations": s.get("totalLocations", 0),
                        "totalCities": s.get("totalCities", 0),
                        "phonesWithKEM": s.get("phonesWithKEM", 0),
                        "phonesByModel": [],
                        "cityCodes": [],
                    }
                }
            elif f == "netspeed.csv" and by_date.get(d, {}).get("file") != "netspeed.csv":
                by_date[d] = {
                    "file": f,
                    "date": d,
                    "metrics": {
                        "totalPhones": s.get("totalPhones", 0),
                        "totalSwitches": s.get("totalSwitches", 0),
                        "totalLocations": s.get("totalLocations", 0),
                        "totalCities": s.get("totalCities", 0),
                        "phonesWithKEM": s.get("phonesWithKEM", 0),
                        "phonesByModel": [],
                        "cityCodes": [],
                    }
                }
        # Build a continuous window starting at earliest and ending at latest; carry-forward missing days
        series: List[Dict] = []
        if by_date:
            from datetime import datetime as _dt, timedelta as _td
            fmt = "%Y-%m-%d"
            min_date_str = min(by_date.keys())
            max_date_str = max(by_date.keys())
            min_date = _dt.strptime(min_date_str, fmt)
            max_date = _dt.strptime(max_date_str, fmt)
            current = by_date.get(min_date_str)
            day = min_date
            while day <= max_date:
                dstr = day.strftime(fmt)
                if dstr in by_date:
                    current = by_date[dstr]
                if current is not None:
                    series.append({
                        "file": current.get("file"),
                        "date": dstr,
                        "metrics": current.get("metrics", {}),
                    })
                day += _td(days=1)
            # If a limit is set, keep the first N entries (oldest-first)
            if eff_limit and len(series) > eff_limit:
                series = series[:eff_limit]
        # Build result and cache
        result = {
            "success": True,
            "message": f"Computed {len(series)} stats timeline points (snapshot)",
            "series": series,
        } if by_date else {
            "success": True,
            "message": "No timeline data available (snapshot)",
            "series": [],
        }
        _TIMELINE_CACHE[eff_limit] = (now + 60.0, result)
        return result

    except Exception as e:
        logger.error(f"Error building stats timeline: {e}")
        return {"success": True, "message": "No timeline data available (snapshot)", "series": []}


@router.get("/timeline/by_location")
async def get_stats_timeline_by_location(q: str, limit: int = 0) -> Dict:
    """Build a time series for a location code (AAA01) or a 3-letter prefix (AAA).

    - Snapshot-only from stats_netspeed_loc.
    - Series starts at the earliest available date and carries forward gaps.
    - If limit > 0, returns the first N days from earliest; 0 returns full range from earliest.
    """
    try:
        if not q or not q.strip():
            return {"success": False, "message": "Missing query parameter 'q'", "series": []}
        term = q.strip().upper()
        mode = "code" if len(term) == 5 else ("prefix" if len(term) == 3 else "invalid")
        if mode == "invalid":
            return {"success": False, "message": "Query must be a 5-char code (AAA01) or 3-letter prefix (AAA)", "series": []}

        eff_limit = limit if limit and limit > 0 else 0
        now = time.time()
        cache_key = (f"{mode}:{term}", eff_limit)
        cached = _TIMELINE_BY_LOC_CACHE.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

        client = opensearch_config.client
        # Ensure index exists or try one-off backfill
        try:
            exists = client.indices.exists(index=opensearch_config.stats_loc_index)
        except Exception:
            exists = False
        if not exists:
            result = {"success": True, "message": "No timeline available for this location (index missing)", "series": [], "selected": []}
            _TIMELINE_BY_LOC_CACHE[cache_key] = (now + 30.0, result)
            return result
        else:
            # Index exists; ensure it's populated at least once
            try:
                c = client.count(index=opensearch_config.stats_loc_index, body={"query": {"match_all": {}}})
                if int(c.get("count", 0)) == 0:
                    # Location snapshots need rebuilding - instruct client to trigger rebuild
                    logger.warning("Location stats index exists but is empty - needs rebuilding")
                    return {
                        "success": False,
                        "message": "Location snapshots need rebuilding — call the rebuild endpoint or trigger the backfill task manually",
                        "series": [],
                        "selected": []
                    }
            except Exception:
                pass

        # Build query and aggregations across all snapshot files (dedup per day by key)
        filters: List[Dict] = []
        if mode == "code":
            filters.append({"term": {"key": {"value": term}}})
        else:
            filters.append({"prefix": {"key": {"value": term}}})
        body = {
            "size": 0,
            "query": {"bool": {"filter": filters}},
            "aggs": {
                "by_date": {
                    "date_histogram": {"field": "date", "calendar_interval": "1d"},
                    "aggs": {
                        "by_key": {
                            "terms": {"field": "key", "size": 10000},
                            "aggs": {
                                "mPhones": {"max": {"field": "totalPhones"}},
                                "mSwitches": {"max": {"field": "totalSwitches"}},
                                "mKEM": {"max": {"field": "phonesWithKEM"}},
                            }
                        },
                        "sumPhones": {"sum_bucket": {"buckets_path": "by_key>mPhones"}},
                        "sumSwitches": {"sum_bucket": {"buckets_path": "by_key>mSwitches"}},
                        "sumKEM": {"sum_bucket": {"buckets_path": "by_key>mKEM"}},
                    },
                }
            }
        }
        res = client.search(index=opensearch_config.stats_loc_index, body=body)
        buckets = res.get("aggregations", {}).get("by_date", {}).get("buckets", [])
        by_date: Dict[str, Dict] = {}
        for b in buckets:
            d = b.get("key_as_string")
            if not d:
                continue
            doc_count = b.get("doc_count")
            if doc_count is not None and not int(doc_count or 0):
                continue
            by_date[d] = {"file": None, "date": d, "metrics": {
                "totalPhones": int(b.get("sumPhones", {}).get("value", 0) or 0),
                "totalSwitches": int(b.get("sumSwitches", {}).get("value", 0) or 0),
                "phonesWithKEM": int(b.get("sumKEM", {}).get("value", 0) or 0),
            }}
        series: List[Dict] = []
        if by_date:
            from datetime import datetime as _dt, timedelta as _td
            fmt = "%Y-%m-%d"
            min_date_str = min(by_date.keys())
            max_date_str = max(by_date.keys())
            min_date = _dt.strptime(min_date_str, fmt)
            max_date = _dt.strptime(max_date_str, fmt)
            current = by_date.get(min_date_str)
            day = min_date
            while day <= max_date:
                dstr = day.strftime(fmt)
                if dstr in by_date:
                    current = by_date[dstr]
                if current is not None:
                    series.append({
                        "file": None,
                        "date": dstr,
                        "metrics": current.get("metrics", {}),
                    })
                day += _td(days=1)
            if eff_limit and len(series) > eff_limit:
                series = series[:eff_limit]

        result = {
            "success": True,
            "message": f"Computed {len(series)} location timeline points (snapshot)",
            "series": series,
            "mode": mode,
            "query": term,
        } if by_date else {
            "success": True,
            "message": "No timeline data available for this location (snapshot)",
            "series": [],
            "mode": mode,
            "query": term,
        }
        _TIMELINE_BY_LOC_CACHE[cache_key] = (now + 60.0, result)
        return result
    except Exception as e:
        logger.error(f"Error building timeline by location for {q}: {e}")
        return {"success": True, "message": "No timeline available for this location (snapshot)", "series": []}


@router.get("/timeline/top_locations")
async def get_stats_timeline_top_locations(count: int = 10, extra: str = "", limit: int = 0, mode: str = "per_key", from_mmdd: str = "", group: str = "city") -> Dict:
    """Top-N timeline from snapshots grouped by city (default) or location code.

    - mode=per_key returns per-group lines aligned by date; mode=aggregate returns a single summed series.
    - limit>0 returns last N days (or from anchor if from_mmdd provided); 0 returns full range from earliest.
    - group=city groups by first 3 letters of location key (e.g., NXX); group=location uses full codes (e.g., NXX01).
    """
    try:
        n = max(1, min(int(count or 10), 500))
        # Extras: allow full codes (NXX01) and prefixes (NXX)
        extras_list: List[str] = []
        if extra:
            for token in str(extra).replace(";", ",").split(','):
                s = token.strip().upper()
                if not s:
                    continue
                if len(s) == 5 and s[:3].isalpha() and s[3:].isdigit():
                    extras_list.append(s)
                elif len(s) == 3 and s.isalpha():
                    extras_list.append(s)
        extras_tuple = tuple(sorted(set(extras_list)))

        eff_limit = limit if limit and limit > 0 else 0
        now = time.time()
        cache_key = (
            n,
            ("mode:" + (mode or "per_key"), "from:" + (from_mmdd or ""), "group:" + (group or "")) + extras_tuple,
            eff_limit,
        )
        cached = _TIMELINE_TOP_CACHE.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

        client = opensearch_config.client

        # Ensure index exists
        try:
            exists = client.indices.exists(index=opensearch_config.stats_loc_index)
        except Exception:
            exists = False
        if not exists:
            return {
                "success": False,
                "message": "Location stats index not found. Please trigger reindex first.",
                "series": [],
                "selected": []
            }

        # Latest snapshot date (prefer netspeed.csv; fallback: any file)
        latest_date = None
        latest_date_current = None
        try:
            body_latest = {"size": 0, "query": {"term": {"file": {"value": "netspeed.csv"}}}, "aggs": {"max_date": {"max": {"field": "date"}}}}
            r_latest = client.search(index=opensearch_config.stats_loc_index, body=body_latest)
            max_date_val = r_latest.get("aggregations", {}).get("max_date", {}).get("value")
            latest_date_current = r_latest.get("aggregations", {}).get("max_date", {}).get("value_as_string") if max_date_val is not None else None
            latest_date = latest_date_current
        except Exception:
            latest_date = None
        if not latest_date:
            try:
                r_latest_any = client.search(index=opensearch_config.stats_loc_index, body={"size": 0, "aggs": {"max_date": {"max": {"field": "date"}}}})
                max_date_val = r_latest_any.get("aggregations", {}).get("max_date", {}).get("value")
                latest_date = r_latest_any.get("aggregations", {}).get("max_date", {}).get("value_as_string") if max_date_val is not None else None
            except Exception:
                latest_date = None
        if not latest_date:
            result = {"success": True, "message": "No top timeline data available (no snapshots)", "series": [], "selected": []}
            _TIMELINE_TOP_CACHE[cache_key] = (now + 30.0, result)
            return result
        had_current = latest_date_current is not None and latest_date_current == latest_date

        # Determine Top-N groups on latest date
        if (group or "city").lower() == "city":
            # Group by city using script-based terms (first 3 letters of key)
            body_top = {
                "size": 0,
                "query": {"bool": {"filter": ([
                    {"range": {"date": {"gte": latest_date, "lte": latest_date}}},
                ] + ([{"term": {"file": {"value": "netspeed.csv"}}}] if had_current else []))}},
                "aggs": {"top_keys": {"terms": {"script": {"source": "doc['key'].value.substring(0,3)"}, "size": n, "order": {"sumPhones": "desc"}}, "aggs": {"sumPhones": {"sum": {"field": "totalPhones"}}}}}
            }
            r_top = client.search(index=opensearch_config.stats_loc_index, body=body_top)
            buckets = r_top.get("aggregations", {}).get("top_keys", {}).get("buckets", [])
            keys = [b.get("key") for b in buckets if b.get("key")]
            extra_prefixes = [e[:3] for e in extras_tuple]
            selected_keys = sorted(set(keys) | set(extra_prefixes))
            # Fallback: if city terms failed, derive city prefixes from top locations on the latest date
            if not selected_keys:
                body_top_loc = {
                    "size": 0,
                    "query": {"bool": {"filter": [
                        {"term": {"file": {"value": "netspeed.csv"}}},
                        {"range": {"date": {"gte": latest_date, "lte": latest_date}}},
                    ]}},
                    "aggs": {"top_keys": {"terms": {"field": "key", "size": n, "order": {"sumPhones": "desc"}}, "aggs": {"sumPhones": {"sum": {"field": "totalPhones"}}}}}
                }
                r_top2 = client.search(index=opensearch_config.stats_loc_index, body=body_top_loc)
                buckets2 = r_top2.get("aggregations", {}).get("top_keys", {}).get("buckets", [])
                loc_keys = [b.get("key") for b in buckets2 if b.get("key")]
                prefixes = [k[:3] for k in loc_keys if isinstance(k, str) and len(k) >= 3]
                selected_keys = sorted(set(prefixes) | set(extra_prefixes))
        else:
            body_top = {
                "size": 0,
                "query": {"bool": {"filter": ([
                    {"range": {"date": {"gte": latest_date, "lte": latest_date}}},
                ] + ([{"term": {"file": {"value": "netspeed.csv"}}}] if had_current else []))}},
                "aggs": {"top_keys": {"terms": {"field": "key", "size": n, "order": {"sumPhones": "desc"}}, "aggs": {"sumPhones": {"sum": {"field": "totalPhones"}}}}}
            }
            r_top = client.search(index=opensearch_config.stats_loc_index, body=body_top)
            buckets = r_top.get("aggregations", {}).get("top_keys", {}).get("buckets", [])
            keys = [b.get("key") for b in buckets if b.get("key")]
            selected_keys = sorted(set(keys) | set(extras_tuple))
        if not selected_keys:
            result = {"success": True, "message": "No top groups found for latest date", "series": [], "selected": []}
            _TIMELINE_TOP_CACHE[cache_key] = (now + 60.0, result)
            return result

        def build_anchor_window(min_date_str: str, max_date_str: str) -> List[str]:
            from datetime import datetime as _dt, timedelta as _td
            fmt = "%Y-%m-%d"
            min_date = _dt.strptime(min_date_str, fmt)
            max_date = _dt.strptime(max_date_str, fmt)
            all_dates: List[str] = []
            day = min_date
            while day <= max_date:
                all_dates.append(day.strftime(fmt))
                day += _td(days=1)
            mmdd = (from_mmdd or "").strip()
            if eff_limit and eff_limit > 0:
                if len(mmdd) == 5 and mmdd[2] == '-':
                    start_idx = 0
                    for i, d in enumerate(all_dates):
                        if d[5:] == mmdd:
                            start_idx = i
                            break
                    return all_dates[start_idx: start_idx + eff_limit]
                return all_dates[-eff_limit:]
            if len(mmdd) == 5 and mmdd[2] == '-':
                for i, d in enumerate(all_dates):
                    if d[5:] == mmdd:
                        return all_dates[i:]
            return all_dates

        if (mode or "per_key").lower() == "aggregate":
            # Aggregate single series
            if (group or "city").lower() == "city":
                # Add date filter for last N days to reduce query load if limit is set and no anchor
                date_filters: List[Dict] = []
                mmdd = (from_mmdd or "").strip()
                if eff_limit and eff_limit > 0 and not (len(mmdd) == 5 and mmdd[2] == '-'):
                    from datetime import datetime as _dt, timedelta as _td
                    try:
                        end_dt = _dt.strptime(latest_date, "%Y-%m-%d")
                        start_dt = end_dt - _td(days=max(0, eff_limit - 1))
                        date_filters.append({"range": {"date": {"gte": start_dt.strftime("%Y-%m-%d"), "lte": end_dt.strftime("%Y-%m-%d")}}})
                    except Exception:
                        pass
                # Critical fix: Group by file first, then select best file per date in post-processing
                # This avoids summing duplicate file versions for same date
                body_series = {
                    "size": 0,
                    "query": {"bool": {"filter": ([
                        {"bool": {"should": [{"prefix": {"key": {"value": c}}} for c in selected_keys], "minimum_should_match": 1}}
                    ] + date_filters)}},
                    "aggs": {
                        "by_date": {
                            "date_histogram": {"field": "date", "calendar_interval": "1d"},
                            "aggs": {
                                # Group by file FIRST to separate different file versions
                                "by_file": {
                                    "terms": {"field": "file", "size": 50},
                                    "aggs": {
                                        "by_city": {
                                            "terms": {"script": {"source": "doc['key'].value.substring(0,3)"}, "size": len(selected_keys)},
                                            "aggs": {
                                                "by_key": {
                                                    "terms": {"field": "key", "size": 10000},
                                                    "aggs": {
                                                        "mPhones": {"max": {"field": "totalPhones"}},
                                                        "mSwitches": {"max": {"field": "totalSwitches"}},
                                                        "mKEM": {"max": {"field": "phonesWithKEM"}},
                                                    }
                                                },
                                                "cityPhones": {"sum_bucket": {"buckets_path": "by_key>mPhones"}},
                                                "citySwitches": {"sum_bucket": {"buckets_path": "by_key>mSwitches"}},
                                                "cityKEM": {"sum_bucket": {"buckets_path": "by_key>mKEM"}},
                                            }
                                        },
                                        "sumPhones": {"sum_bucket": {"buckets_path": "by_city>cityPhones"}},
                                        "sumSwitches": {"sum_bucket": {"buckets_path": "by_city>citySwitches"}},
                                        "sumKEM": {"sum_bucket": {"buckets_path": "by_city>cityKEM"}},
                                    }
                                }
                            }
                        }
                    }
                }
            else:
                body_series = {
                    "size": 0,
                    "query": {"bool": {"filter": [
                        {"terms": {"key": selected_keys}},
                    ]}},
                    "aggs": {
                        "by_date": {
                            "date_histogram": {"field": "date", "calendar_interval": "1d"},
                            "aggs": {
                                "by_key": {
                                    "terms": {"field": "key", "size": len(selected_keys)},
                                    "aggs": {
                                        "mPhones": {"max": {"field": "totalPhones"}},
                                        "mSwitches": {"max": {"field": "totalSwitches"}},
                                        "mKEM": {"max": {"field": "phonesWithKEM"}},
                                    }
                                },
                                "sumPhones": {"sum_bucket": {"buckets_path": "by_key>mPhones"}},
                                "sumSwitches": {"sum_bucket": {"buckets_path": "by_key>mSwitches"}},
                                "sumKEM": {"sum_bucket": {"buckets_path": "by_key>mKEM"}},
                            }
                        }
                    }
                }
            r_series = client.search(index=opensearch_config.stats_loc_index, body=body_series)
            buckets = r_series.get("aggregations", {}).get("by_date", {}).get("buckets", [])
            by_date: Dict[str, Dict] = {}

            # Helper function to select best file from multiple versions per date
            def select_best_file(file_buckets):
                """
                Prefer netspeed.csv (current), else highest numbered rotation (netspeed.csv.0 > netspeed.csv.29).
                Returns tuple: (file_name, metrics_dict)
                """
                if not file_buckets:
                    return None, {"totalPhones": 0, "totalSwitches": 0, "phonesWithKEM": 0}

                # Check if netspeed.csv exists
                for fb in file_buckets:
                    if fb.get("key") == "netspeed.csv":
                        return "netspeed.csv", {
                            "totalPhones": int(fb.get("sumPhones", {}).get("value", 0) or 0),
                            "totalSwitches": int(fb.get("sumSwitches", {}).get("value", 0) or 0),
                            "phonesWithKEM": int(fb.get("sumKEM", {}).get("value", 0) or 0),
                        }

                # Fall back to numbered files - prefer lowest number (most recent rotation)
                # netspeed.csv.0 is newest rotation, netspeed.csv.29 is oldest
                numbered_files = []
                for fb in file_buckets:
                    fname = fb.get("key", "")
                    if fname.startswith("netspeed.csv."):
                        try:
                            num = int(fname.split(".")[-1])
                            numbered_files.append((num, fname, fb))
                        except (ValueError, IndexError):
                            continue

                if numbered_files:
                    # Sort by number ascending (0 is best)
                    numbered_files.sort(key=lambda x: x[0])
                    _, fname, fb = numbered_files[0]
                    return fname, {
                        "totalPhones": int(fb.get("sumPhones", {}).get("value", 0) or 0),
                        "totalSwitches": int(fb.get("sumSwitches", {}).get("value", 0) or 0),
                        "phonesWithKEM": int(fb.get("sumKEM", {}).get("value", 0) or 0),
                    }

                # Fallback: use first file if no recognized pattern
                fb = file_buckets[0]
                return fb.get("key"), {
                    "totalPhones": int(fb.get("sumPhones", {}).get("value", 0) or 0),
                    "totalSwitches": int(fb.get("sumSwitches", {}).get("value", 0) or 0),
                    "phonesWithKEM": int(fb.get("sumKEM", {}).get("value", 0) or 0),
                }

            for b in buckets:
                d = b.get("key_as_string")
                if not d:
                    continue
                doc_count = b.get("doc_count")
                if doc_count is not None and not int(doc_count or 0):
                    continue

                # Extract file buckets from aggregation
                file_buckets = b.get("by_file", {}).get("buckets", [])
                best_file, metrics = select_best_file(file_buckets)

                by_date[d] = {"file": best_file, "date": d, "metrics": metrics}
            series: List[Dict] = []
            if by_date:
                from datetime import datetime as _dt, timedelta as _td
                fmt = "%Y-%m-%d"
                min_date_str = min(by_date.keys())
                max_date_str = max(by_date.keys())
                min_date = _dt.strptime(min_date_str, fmt)
                max_date = _dt.strptime(max_date_str, fmt)
                current = by_date.get(min_date_str)
                day = min_date
                while day <= max_date:
                    dstr = day.strftime(fmt)
                    if dstr in by_date:
                        current = by_date[dstr]
                    if current is not None:
                        series.append({
                            "file": current.get("file"),
                            "date": dstr,
                            "metrics": current.get("metrics", {}),
                        })
                    day += _td(days=1)
                if eff_limit and len(series) > eff_limit:
                    series = series[:eff_limit]

            label_str = (group or "city").lower()
            result = {
                "success": True,
                "message": f"Computed {len(series)} top-{label_str} timeline points (aggregate)",
                "series": series,
                "selected": selected_keys,
                "mode": "aggregate",
                "group": label_str
            }
        else:
            # Per-group series
            if (group or "city").lower() == "city":
                body_series = {
                    "size": 0,
                    "query": {"bool": {"filter": [
                        {"bool": {"should": [{"prefix": {"key": {"value": c}}} for c in selected_keys], "minimum_should_match": 1}}
                    ]}},
                    "aggs": {
                        "by_city": {
                            "terms": {"script": {"source": "doc['key'].value.substring(0,3)"}, "size": len(selected_keys)},
                            "aggs": {
                                "by_date": {
                                    "date_histogram": {"field": "date", "calendar_interval": "1d"},
                                    "aggs": {
                                        "by_key": {
                                            "terms": {"field": "key", "size": 10000},
                                            "aggs": {
                                                "mPhones": {"max": {"field": "totalPhones"}},
                                                "mSwitches": {"max": {"field": "totalSwitches"}},
                                                "mKEM": {"max": {"field": "phonesWithKEM"}},
                                            }
                                        },
                                        "sumPhones": {"sum_bucket": {"buckets_path": "by_key>mPhones"}},
                                        "sumSwitches": {"sum_bucket": {"buckets_path": "by_key>mSwitches"}},
                                        "sumKEM": {"sum_bucket": {"buckets_path": "by_key>mKEM"}},
                                    }
                                }
                            }
                        }
                    }
                }
                r_series = client.search(index=opensearch_config.stats_loc_index, body=body_series)
                buckets_by_city = r_series.get("aggregations", {}).get("by_city", {}).get("buckets", [])
                dates_set: set[str] = set()
                per_key_map: Dict[str, Dict[str, Dict[str, int]]] = {}
                for cb in buckets_by_city:
                    ckey = cb.get("key")
                    if ckey not in selected_keys:
                        continue
                    bdates = cb.get("by_date", {}).get("buckets", []) if isinstance(cb, dict) else []
                    dmap: Dict[str, Dict[str, int]] = {}
                    for b in bdates:
                        d = b.get("key_as_string")
                        if not d:
                            continue
                        dates_set.add(d)
                        doc_count = b.get("doc_count")
                        if doc_count is not None and not int(doc_count or 0):
                            continue
                        dmap[d] = {
                            "totalPhones": int(b.get("sumPhones", {}).get("value", 0) or 0),
                            "totalSwitches": int(b.get("sumSwitches", {}).get("value", 0) or 0),
                            "phonesWithKEM": int(b.get("sumKEM", {}).get("value", 0) or 0),
                        }
                    if ckey:
                        per_key_map[str(ckey)] = dmap
                if not dates_set:
                    labels_map = {str(k): f"{resolve_city_name(str(k))} ({str(k)})" for k in selected_keys}
                    result = {"success": True, "message": "No top-cities timeline data available (per_key)", "dates": [], "keys": selected_keys, "seriesByKey": {}, "labels": labels_map, "mode": "per_key", "group": "city"}
                    _TIMELINE_TOP_CACHE[cache_key] = (now + 60.0, result)
                    return result
                window = build_anchor_window(min(dates_set), max(dates_set))
                seriesByKey: Dict[str, Dict[str, List[int]]] = {}
                for k in selected_keys:
                    dmap = per_key_map.get(k, {})
                    last = {"totalPhones": 0, "totalSwitches": 0, "phonesWithKEM": 0}
                    arrays = {"totalPhones": [], "totalSwitches": [], "phonesWithKEM": []}
                    for dstr in window:
                        if dstr in dmap:
                            last = dmap[dstr]
                        arrays["totalPhones"].append(int(last.get("totalPhones", 0)))
                        arrays["totalSwitches"].append(int(last.get("totalSwitches", 0)))
                        arrays["phonesWithKEM"].append(int(last.get("phonesWithKEM", 0)))
                    seriesByKey[k] = arrays
                labels_map = {str(k): f"{resolve_city_name(str(k))} ({str(k)})" for k in selected_keys}
                result = {"success": True, "message": f"Computed top-cities per-key timeline over {len(window)} days (snapshot)", "dates": window, "keys": selected_keys, "seriesByKey": seriesByKey, "labels": labels_map, "mode": "per_key", "group": "city"}
            else:
                body_series = {
                    "size": 0,
                    "query": {"bool": {"filter": [
                        {"terms": {"key": selected_keys}},
                    ]}},
                    "aggs": {
                        "by_key": {"terms": {"field": "key", "size": len(selected_keys)}, "aggs": {
                            "by_date": {"date_histogram": {"field": "date", "calendar_interval": "1d"}, "aggs": {
                                "sumPhones": {"max": {"field": "totalPhones"}},
                                "sumSwitches": {"max": {"field": "totalSwitches"}},
                                "sumKEM": {"max": {"field": "phonesWithKEM"}},
                            }},
                        }}}
                }
                r_series = client.search(index=opensearch_config.stats_loc_index, body=body_series)
                buckets_by_key = r_series.get("aggregations", {}).get("by_key", {}).get("buckets", [])
                dates_set: set[str] = set()
                per_key_map: Dict[str, Dict[str, Dict[str, int]]] = {}
                for kb in buckets_by_key:
                    key_val = kb.get("key")
                    bdates = kb.get("by_date", {}).get("buckets", []) if isinstance(kb, dict) else []
                    dmap: Dict[str, Dict[str, int]] = {}
                    for b in bdates:
                        d = b.get("key_as_string")
                        if not d:
                            continue
                        dates_set.add(d)
                        doc_count = b.get("doc_count")
                        if doc_count is not None and not int(doc_count or 0):
                            continue
                        dmap[d] = {
                            "totalPhones": int(b.get("sumPhones", {}).get("value", 0) or 0),
                            "totalSwitches": int(b.get("sumSwitches", {}).get("value", 0) or 0),
                            "phonesWithKEM": int(b.get("sumKEM", {}).get("value", 0) or 0),
                        }
                    if key_val:
                        per_key_map[str(key_val)] = dmap
                if not dates_set:
                    label = "cities" if (group or "city").lower() == "city" else "locations"
                    result = {"success": True, "message": f"No top-{label} timeline data available (per_key)", "dates": [], "keys": selected_keys, "seriesByKey": {}, "mode": "per_key", "group": (group or "city").lower()}
                    _TIMELINE_TOP_CACHE[cache_key] = (now + 60.0, result)
                    return result
                window = build_anchor_window(min(dates_set), max(dates_set))
                seriesByKey: Dict[str, Dict[str, List[int]]] = {}
                for k in selected_keys:
                    dmap = per_key_map.get(k, {})
                    last = {"totalPhones": 0, "totalSwitches": 0, "phonesWithKEM": 0}
                    arrays = {"totalPhones": [], "totalSwitches": [], "phonesWithKEM": []}
                    for dstr in window:
                        if dstr in dmap:
                            last = dmap[dstr]
                        arrays["totalPhones"].append(int(last.get("totalPhones", 0)))
                        arrays["totalSwitches"].append(int(last.get("totalSwitches", 0)))
                        arrays["phonesWithKEM"].append(int(last.get("phonesWithKEM", 0)))
                    seriesByKey[k] = arrays
                label = "cities" if (group or "city").lower() == "city" else "locations"
                result = {"success": True, "message": f"Computed top-{label} per-key timeline over {len(window)} days (snapshot)", "dates": window, "keys": selected_keys, "seriesByKey": seriesByKey, "mode": "per_key", "group": (group or "city").lower()}

        _TIMELINE_TOP_CACHE[cache_key] = (now + 60.0, result)
        return result
    except Exception as e:
        logger.error(f"Error building top timeline: {e}")
        return {"success": True, "message": "No top timeline data available (snapshot)", "series": [], "selected": []}


@router.post("/timeline/rebuild")
async def rebuild_top_location_snapshots(directory: str = "") -> Dict:
    """Trigger a background rebuild of stats snapshots with deduplicated rows."""
    try:
        base_dir = directory.strip()
        if not base_dir:
            base_dir = getattr(settings, "CSV_FILES_DIR", None) or ""

        from tasks.tasks import rebuild_stats_snapshots_deduplicated

        if base_dir:
            task = rebuild_stats_snapshots_deduplicated.delay(base_dir)
        else:
            task = rebuild_stats_snapshots_deduplicated.delay()

        return {
            "success": True,
            "message": "Started deduplicated stats rebuild",
            "task_id": task.id,
            "base_directory": base_dir or None,
        }
    except Exception as e:
        logger.error(f"Failed to trigger stats rebuild: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger stats rebuild: {e}")


@router.get("/timeline/rebuild/status/{task_id}")
async def get_rebuild_top_location_status(task_id: str) -> Dict:
    """Return Celery status for the deduplicated stats rebuild task."""
    try:
        result = AsyncResult(task_id)
        if result.successful():
            return {
                "success": True,
                "status": "completed",
                "result": result.result,
            }
        if result.failed():
            return {
                "success": False,
                "status": "failed",
                "error": str(result.result),
            }
        if getattr(result, "state", None) in ("PENDING", "RETRY"):
            return {
                "success": True,
                "status": "pending",
            }
        state = getattr(result, "state", "running")
        return {
            "success": True,
            "status": str(state).lower(),
        }
    except Exception as e:
        logger.error(f"Failed to check stats rebuild status: {e}")
        return {
            "success": False,
            "status": "error",
            "error": str(e),
        }


@router.get("/archive")
async def get_archive(date: str, file: str | None = None, size: int = 1000) -> Dict:
    """Return archived rows for a specific snapshot date (and optional file name).

    Args:
        date: YYYY-MM-DD snapshot date
        file: optional file variant (e.g., netspeed.csv or netspeed.csv.3)
        size: max docs to return (default 1000)
    """
    try:
        # If archive index doesn't exist yet, return empty set gracefully
        try:
            if not opensearch_config.client.indices.exists(index=opensearch_config.archive_index):
                return {"success": True, "date": date, "file": file, "count": 0, "data": []}
        except Exception:
            # If existence check fails (e.g., OS down), return empty success to avoid 500s
            return {"success": True, "date": date, "file": file, "count": 0, "data": []}

        must_filters = [
            {"range": {"snapshot_date": {"gte": date, "lte": date}}}
        ]
        if file:
            must_filters.append({"term": {"snapshot_file": {"value": file}}})
        body = {
            "size": max(1, min(size, 10000)),
            "query": {"bool": {"filter": must_filters}},
            "_source": True,
            "sort": [{"_id": {"order": "asc"}}]
        }
        res = opensearch_config.client.search(index=opensearch_config.archive_index, body=body)
        hits = res.get("hits", {}).get("hits", [])
        data = [h.get("_source", {}) for h in hits]
        return {"success": True, "date": date, "file": file, "count": len(data), "data": data}
    except Exception as e:
        logger.error(f"Error reading archive {date}/{file}: {e}")
        # Return empty but successful to avoid breaking UI; user can investigate OS connectivity
        return {"success": True, "date": date, "file": file, "count": 0, "data": []}


@router.get("/cities/debug")
async def debug_cities(filename: str = "netspeed.csv", limit: int = 25) -> Dict:
    """Debug helper: compare distinct city prefixes found in OpenSearch snapshots vs. mapping keys.

    NO CSV computation - only uses OpenSearch data.
    """
    try:
        mapping = {}
        if get_city_code_map:
            mapping = get_city_code_map()
        map_keys = set(mapping.keys())

        # Get city codes from OpenSearch snapshots only
        try:
            file_model = FileModel.from_path(str(_resolve_data_path(filename)))
            date_str = file_model.date.strftime('%Y-%m-%d') if file_model.date else None

            if date_str:
                doc_id = f"{file_model.name}:{date_str}"
                try:
                    snap = opensearch_config.client.get(index=opensearch_config.stats_index, id=doc_id)
                    src = snap.get("_source") if isinstance(snap, dict) else None
                    if src:
                        city_codes = set(src.get("cityCodes", []))
                    else:
                        city_codes = set()
                except:
                    city_codes = set()
            else:
                city_codes = set()
        except Exception:
            city_codes = set()

        missing_in_mapping = sorted([p for p in city_codes if p not in map_keys])
        missing_in_csv = sorted([k for k in map_keys if k not in city_codes])

        if limit and limit > 0:
            missing_in_mapping = missing_in_mapping[:limit]
            missing_in_csv = missing_in_csv[:limit]

        return {
            "success": True,
            "message": "City mapping debug computed from OpenSearch",
            "data": {
                "mappingCount": len(map_keys),
                "csvCityCount": len(city_codes),
                "missingInMapping": missing_in_mapping,
                "missingInCSV": missing_in_csv,
            },
        }
    except Exception as e:
        logger.error(f"Error debugging city mapping: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute city debug info")


@router.get("/locations")
async def list_locations(q: str = "", filename: str = "netspeed.csv", limit: int = 25) -> Dict:
    """Return distinct 5-letter location codes from OpenSearch data only.

    NO CSV computation - only uses OpenSearch indices.
    """
    try:
        # Query current netspeed index for locations
        current_index = None
        try:
            if opensearch_config.client.indices.exists(index="netspeed_netspeed_csv"):
                current_index = "netspeed_netspeed_csv"
            else:
                indices = opensearch_config.client.indices.get(index="netspeed_*")
                if indices:
                    current_index = list(indices.keys())[0]
        except Exception:
            return {"success": True, "options": []}

        if not current_index:
            return {"success": True, "options": []}

        # Get distinct locations using terms aggregation
        term = (q or "").strip().upper()
        body = {
            "size": 0,
            "aggs": {
                "locations": {
                    "terms": {
                        "script": {
                            "source": """
                                def hostname = doc['Switch Hostname.keyword'].value;
                                if (hostname == null || hostname.length() < 4) return null;
                                def h = hostname.toUpperCase();
                                // Pattern matching like extract_location
                                if (h.length() >= 5 && h.charAt(0) >= 'A' && h.charAt(0) <= 'Z' &&
                                    h.charAt(1) >= 'A' && h.charAt(1) <= 'Z' && h.charAt(2) == 'X' &&
                                    h.charAt(3) >= '0' && h.charAt(3) <= '9' && h.charAt(4) >= '0' && h.charAt(4) <= '9') {
                                    return h.substring(0, 5);
                                }
                                if (h.length() >= 6 && h.charAt(0) >= 'A' && h.charAt(0) <= 'Z' &&
                                    h.charAt(1) >= 'A' && h.charAt(1) <= 'Z' && h.charAt(2) >= 'A' && h.charAt(2) <= 'Z' &&
                                    h.charAt(3) == 'X' && h.charAt(4) >= '0' && h.charAt(4) <= '9' && h.charAt(5) >= '0' && h.charAt(5) <= '9') {
                                    return h.substring(0, 3) + h.substring(4, 6);
                                }
                                if (h.length() >= 5 && h.charAt(0) >= 'A' && h.charAt(0) <= 'Z' &&
                                    h.charAt(1) >= 'A' && h.charAt(1) <= 'Z' && h.charAt(2) >= 'A' && h.charAt(2) <= 'Z' &&
                                    h.charAt(3) >= '0' && h.charAt(3) <= '9' && h.charAt(4) >= '0' && h.charAt(4) <= '9') {
                                    return h.substring(0, 5);
                                }
                                return null;
                            """
                        },
                        "size": limit if limit > 0 else 10000
                    }
                }
            }
        }

        res = opensearch_config.client.search(index=current_index, body=body)
        buckets = res.get("aggregations", {}).get("locations", {}).get("buckets", [])
        locations = [b.get("key") for b in buckets if b.get("key")]

        # Filter by query term if provided
        if term:
            locations = [loc for loc in locations if term in loc]

        return {"success": True, "options": sorted(locations)}
    except Exception as e:
        logger.error(f"Error listing locations from OpenSearch: {e}")
        return {"success": True, "options": []}


@router.get("/by_location")
async def stats_by_location(q: str, filename: str = "netspeed.csv") -> Dict:
    """DEPRECATED: Use /fast/by_location instead.

    This endpoint now returns an error to force using OpenSearch-based implementation.
    """
    return {
        "success": False,
        "message": "This endpoint is deprecated. Use /api/stats/fast/by_location instead for OpenSearch-based statistics.",
        "data": {}
    }


# ========================================
# FAST API ENDPOINTS (OpenSearch-based)
# ========================================

@router.get("/fast/current")
async def get_current_stats_fast() -> Dict:
    """
    Fast statistics using latest OpenSearch stats snapshot only - NO CSV fallbacks.
    Uses pre-computed values from reindexing.
    """
    try:
        # Check if stats index exists
        if not opensearch_config.client.indices.exists(index=opensearch_config.stats_index):
            return {
                "success": False,
                "message": "No stats index found. Please trigger reindex first.",
                "data": {
                    "totalPhones": 0,
                    "totalSwitches": 0,
                    "totalLocations": 0,
                    "totalCities": 0,
                    "phonesWithKEM": 0,
                    "totalKEMs": 0,
                    "totalJustizPhones": 0,
                    "totalJVAPhones": 0,
                    # New individual Justiz KPIs
                    "justizSwitches": 0,
                    "justizLocations": 0,
                    "justizCities": 0,
                    "justizPhonesWithKEM": 0,
                    "totalJustizKEMs": 0,
                    # New individual JVA KPIs
                    "jvaSwitches": 0,
                    "jvaLocations": 0,
                    "jvaCities": 0,
                    "jvaPhonesWithKEM": 0,
                    "totalJVAKEMs": 0,
                    "phonesByModel": [],
                    "phonesByModelJustiz": [],
                    "phonesByModelJVA": [],
                    "phonesByModelJustizDetails": [],
                    "phonesByModelJVADetails": [],
                    "cities": [],
                },
                "file": {"name": "netspeed.csv", "date": ""},
            }

        preferred_files = _preferred_stats_files()
        using_fallback = False
        latest_doc: Dict[str, Any] | None = None
        file_name = "netspeed.csv"
        date_str = ""

        for idx, candidate in enumerate(preferred_files):
            try:
                body_current = {
                    "size": 1,
                    "sort": [{"date": {"order": "desc"}}],
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"file": candidate}}
                            ]
                        }
                    }
                }
                res = opensearch_config.client.search(index=opensearch_config.stats_index, body=body_current)
            except Exception:
                continue
            hits = res.get("hits", {}).get("hits", []) if isinstance(res, dict) else []
            if hits:
                latest_doc = hits[0].get("_source", {}) or {}
                file_name = latest_doc.get("file", candidate) or candidate
                date_str = latest_doc.get("date", "") or ""
                if idx > 0:
                    using_fallback = True
                break

        if latest_doc is None:
            try:
                body_any = {
                    "size": 1,
                    "sort": [{"date": {"order": "desc"}}],
                    "query": {"match_all": {}}
                }
                res = opensearch_config.client.search(index=opensearch_config.stats_index, body=body_any)
                hits = res.get("hits", {}).get("hits", []) if isinstance(res, dict) else []
                if hits:
                    latest_doc = hits[0].get("_source", {}) or {}
                    file_name = latest_doc.get("file", file_name) or file_name
                    date_str = latest_doc.get("date", "") or ""
                    using_fallback = True
            except Exception:
                latest_doc = None

        if not latest_doc:
            return {
                "success": False,
                "message": "No stats snapshots found. Please trigger reindex first.",
                "data": {
                    "totalPhones": 0,
                    "totalSwitches": 0,
                    "totalLocations": 0,
                    "totalCities": 0,
                    "phonesWithKEM": 0,
                    "totalKEMs": 0,
                    "totalJustizPhones": 0,
                    "totalJVAPhones": 0,
                    # New individual Justiz KPIs
                    "justizSwitches": 0,
                    "justizLocations": 0,
                    "justizCities": 0,
                    "justizPhonesWithKEM": 0,
                    "totalJustizKEMs": 0,
                    # New individual JVA KPIs
                    "jvaSwitches": 0,
                    "jvaLocations": 0,
                    "jvaCities": 0,
                    "jvaPhonesWithKEM": 0,
                    "totalJVAKEMs": 0,
                    "phonesByModel": [],
                    "phonesByModelJustiz": [],
                    "phonesByModelJVA": [],
                    "phonesByModelJustizDetails": [],
                    "phonesByModelJVADetails": [],
                    "cities": [],
                },
                "file": {"name": "netspeed.csv", "date": ""},
            }

        # Extract latest snapshot data - all pre-computed during reindexing
        # Ensure we have sane defaults even if snapshot lacks file/date fields
        snapshot: Dict[str, Any] = cast(Dict[str, Any], latest_doc)
        file_name = snapshot.get("file", file_name) or file_name
        date_str = snapshot.get("date", date_str) or date_str

        # All data is already computed during reindexing - just use snapshot values directly
        justiz_models = snapshot.get("phonesByModelJustiz", [])
        jva_models = snapshot.get("phonesByModelJVA", [])
        total_justiz = snapshot.get("totalJustizPhones", 0)
        total_jva = snapshot.get("totalJVAPhones", 0)

        # If the latest current snapshot is effectively empty (no phones/switches/locations and no cities),
        # fallback to the latest non-empty snapshot across any file variant
        try:
            def _is_empty_snapshot(doc: dict) -> bool:
                return int(doc.get("totalPhones", 0) or 0) == 0 \
                    and int(doc.get("totalSwitches", 0) or 0) == 0 \
                    and int(doc.get("totalLocations", 0) or 0) == 0 \
                    and not (doc.get("cityCodes") or [])

            if _is_empty_snapshot(snapshot):
                body_scan = {"size": 20, "sort": [{"date": {"order": "desc"}}], "query": {"match_all": {}}, "_source": True}
                rscan = opensearch_config.client.search(index=opensearch_config.stats_index, body=body_scan)
                for hh in rscan.get("hits", {}).get("hits", []):
                    src2 = hh.get("_source", {})
                    if not _is_empty_snapshot(src2):
                        snapshot = cast(Dict[str, Any], src2)
                        latest_doc = snapshot
                        file_name = snapshot.get("file", file_name)
                        date_str = snapshot.get("date", date_str)
                        using_fallback = True
                        break
                # Re-bind derived structures after fallback
                justiz_models = snapshot.get("phonesByModelJustiz", [])
                jva_models = snapshot.get("phonesByModelJVA", [])
                total_justiz = snapshot.get("totalJustizPhones", 0)
                total_jva = snapshot.get("totalJVAPhones", 0)
        except Exception:
            pass

        # Get city codes and resolve names
        city_codes = snapshot.get("cityCodes", [])
        cities = []
        for code in city_codes:
            cities.append({"code": code, "name": resolve_city_name(code)})
        cities.sort(key=lambda x: x["name"])

        # Optional consistency correction: if per-location kemPhones exist for the same date,
        # recompute phonesWithKEM (unique phones) and totalKEMs (sum of modules) from details.
        corrected_phones_with_kem = None
        corrected_total_kems = None
        try:
            if date_str:
                body_loc = {
                    "size": 1000,
                    "_source": ["kemPhones"],
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"file": file_name}},
                                {"term": {"date": date_str}}
                            ]
                        }
                    }
                }
                res_loc = opensearch_config.client.search(index=opensearch_config.stats_loc_index, body=body_loc)
                if res_loc.get("hits", {}).get("hits"):
                    kem_total = 0
                    phone_total = 0
                    for h in res_loc["hits"]["hits"]:
                        src = h.get("_source", {})
                        kem_list = src.get("kemPhones", [])
                        if isinstance(kem_list, list):
                            phone_total += len(kem_list)
                            for item in kem_list:
                                try:
                                    km = int(item.get("kemModules", 1) or 1)
                                except Exception:
                                    km = 1
                                kem_total += km
                    # Only apply if we actually found any phones
                    if phone_total > 0:
                        corrected_phones_with_kem = phone_total
                        corrected_total_kems = kem_total
        except Exception:
            # Best-effort correction; ignore failures silently
            pass

        # Determine if this snapshot is the latest by date across any file variant
        is_latest = True
        try:
            body_max = {"size": 0, "aggs": {"max_date": {"max": {"field": "date"}}}}
            rmax = opensearch_config.client.search(index=opensearch_config.stats_index, body=body_max)
            max_date_val = rmax.get("aggregations", {}).get("max_date", {}).get("value")
            latest_any_date = rmax.get("aggregations", {}).get("max_date", {}).get("value_as_string") if max_date_val is not None else None
            if latest_any_date and date_str and str(latest_any_date) != str(date_str):
                is_latest = False
        except Exception:
            # best-effort; assume latest if check fails
            is_latest = True

        is_current = bool(preferred_files and file_name == preferred_files[0])

        return {
            "success": True,
            "message": "Statistics loaded from OpenSearch snapshot",
            "data": {
                "totalPhones": snapshot.get("totalPhones", 0),
                "totalSwitches": snapshot.get("totalSwitches", 0),
                "totalLocations": snapshot.get("totalLocations", 0),
                "totalCities": snapshot.get("totalCities", 0),
                "phonesWithKEM": int(corrected_phones_with_kem if corrected_phones_with_kem is not None else snapshot.get("phonesWithKEM", 0)),
                "totalKEMs": int(corrected_total_kems if corrected_total_kems is not None else snapshot.get("totalKEMs", 0)),
                "totalJustizPhones": total_justiz,
                "totalJVAPhones": total_jva,
                # New individual Justiz KPIs
                "justizSwitches": snapshot.get("justizSwitches", 0),
                "justizLocations": snapshot.get("justizLocations", 0),
                "justizCities": snapshot.get("justizCities", 0),
                "justizPhonesWithKEM": snapshot.get("justizPhonesWithKEM", 0),
                "totalJustizKEMs": snapshot.get("totalJustizKEMs", 0),
                # New individual JVA KPIs
                "jvaSwitches": snapshot.get("jvaSwitches", 0),
                "jvaLocations": snapshot.get("jvaLocations", 0),
                "jvaCities": snapshot.get("jvaCities", 0),
                "jvaPhonesWithKEM": snapshot.get("jvaPhonesWithKEM", 0),
                "totalJVAKEMs": snapshot.get("totalJVAKEMs", 0),
                "phonesByModel": snapshot.get("phonesByModel", []),
                "phonesByModelJustiz": justiz_models,
                "phonesByModelJVA": jva_models,
                "phonesByModelJustizDetails": snapshot.get("phonesByModelJustizDetails", []),
                "phonesByModelJVADetails": snapshot.get("phonesByModelJVADetails", []),
                "cities": cities,
            },
            "file": {
                "name": file_name,
                "date": date_str,
                "is_current": is_current,
                "is_latest": bool(is_latest),
                "using_fallback": bool(using_fallback or not is_current or not is_latest),
                       }
        }

    except Exception as e:
        logger.error(f"Error getting fast current stats: {e}")
        return {
            "success": False,
            "message": f"Failed to load stats from OpenSearch: {e}",
            "data": {
                "totalPhones": 0,
                "totalSwitches": 0,
                "totalLocations": 0,
                "totalCities": 0,
                "phonesWithKEM": 0,
                "totalKEMs": 0,
                "totalJustizPhones": 0,
                "totalJVAPhones": 0,
                # New individual Justiz KPIs
                "justizSwitches": 0,
                "justizLocations": 0,
                "justizCities": 0,
                "justizPhonesWithKEM": 0,
                "totalJustizKEMs": 0,
                # New individual JVA KPIs
                "jvaSwitches": 0,
                "jvaLocations": 0,
                "jvaCities": 0,
                "jvaPhonesWithKEM": 0,
                "totalJVAKEMs": 0,
                "phonesByModel": [],
                "phonesByModelJustiz": [],
                "phonesByModelJVA": [],
                "phonesByModelJustizDetails": [],
                "phonesByModelJVADetails": [],
                "cities": [],
            },
            "file": {"name": "netspeed.csv", "date": ""},
        }


@router.get("/fast/cities")
async def get_cities_fast() -> Dict:
    """
    Fast city mapping from OpenSearch snapshots only - NO CSV fallbacks.
    Returns city code to name mapping for location search.
    """
    try:
        # Prefer latest netspeed.csv snapshot; fallback to any snapshot
        body_current = {"size": 1, "sort": [{"date": {"order": "desc"}}], "query": {"term": {"file": {"value": "netspeed.csv"}}}}
        r = opensearch_config.client.search(index=opensearch_config.stats_index, body=body_current)
        if not r.get("hits", {}).get("hits"):
            body_any = {"size": 1, "sort": [{"date": {"order": "desc"}}], "query": {"match_all": {}}}
            r = opensearch_config.client.search(index=opensearch_config.stats_index, body=body_any)
        if not r.get("hits", {}).get("hits"):
            return {"success": False, "message": "No snapshots found", "cities": [], "cityMap": {}, "total": 0}
        src = r["hits"]["hits"][0].get("_source", {})
        codes = src.get("cityCodes", []) or []
        # If empty, scan a few recent snapshots for any cityCodes
        if not codes:
            rscan = opensearch_config.client.search(index=opensearch_config.stats_index, body={"size": 20, "sort": [{"date": {"order": "desc"}}], "query": {"match_all": {}}})
            for hh in rscan.get("hits", {}).get("hits", []):
                src2 = hh.get("_source", {})
                cc = src2.get("cityCodes", []) or []
                if cc:
                    src = src2
                    codes = cc
                    break
        # Resolve names
        cities = sorted([{"code": c, "name": resolve_city_name(c)} for c in codes], key=lambda x: x["name"])
        city_map = {c["code"]: c["name"] for c in cities}
        return {"success": True, "cities": cities, "cityMap": city_map, "total": len(cities)}
    except Exception as e:
        logger.error(f"Error getting fast cities: {e}")
        return {"success": False, "message": "Failed to load city data from OpenSearch", "cities": [], "cityMap": {}, "total": 0}


@router.get("/fast/locations")
async def get_locations_fast(limit: int = 1000) -> Dict:
    """
    Fast location listing using pre-computed location snapshots from OpenSearch only.
    NO CSV fallbacks - only uses location data from reindexing.
    """
    try:
        # Check if location stats index exists
        if not opensearch_config.client.indices.exists(index=opensearch_config.stats_loc_index):
            return {
                "success": False,
                "message": "No location stats index found. Please trigger reindex first.",
                "locations": [],
                "options": [],
                "total": 0,
                "mode": "fast"
            }

        # Get all unique locations from the stats_loc_index
        body = {
            "size": 0,
            "aggs": {
                "unique_locations": {
                    "terms": {
                        "field": "key",
                        "size": limit,
                        "order": {"_key": "asc"}
                    }
                }
            }
        }

        res = opensearch_config.client.search(index=opensearch_config.stats_loc_index, body=body)

        # Extract location codes from aggregation results
        locations = []
        if "aggregations" in res and "unique_locations" in res["aggregations"]:
            for bucket in res["aggregations"]["unique_locations"]["buckets"]:
                if bucket["key"] and bucket["key"] != "null":
                    locations.append(bucket["key"])

        return {
            "success": True,
            "locations": sorted(locations),
            "options": sorted(locations),  # Add for frontend compatibility
            "total": len(locations),
            "mode": "fast"
        }

    except Exception as e:
        logger.error(f"Error getting fast locations: {e}")
        return {
            "success": False,
            "message": f"Failed to load locations from OpenSearch: {e}",
            "locations": [],
            "options": [],
            "total": 0,
            "mode": "fast"
        }


@router.get("/fast/locations/suggest")
async def suggest_location_codes(q: str, limit: int = 50) -> Dict:
    """
    Ultra-fast location code suggestions with city names for instant search.

    Optimized for real-time search starting from first character:
    - 'n' -> all locations starting with N
    - 'nx' -> all locations starting with NX
    - 'nxx' -> all locations starting with NXX
    - 'nxx0' -> all locations starting with NXX0
    - 'nxx01' -> exact match for NXX01

    Returns format: [{"code": "NXX01", "display": "NXX01 (Nürnberg)"}]
    """
    try:
        # Helpers for normalization (accent-insensitive matching)
        import unicodedata
        def _norm_txt(s: str) -> str:
            if not s:
                return ""
            s = str(s)
            s = unicodedata.normalize('NFKD', s)
            s = ''.join(ch for ch in s if not unicodedata.combining(ch))
            return s.lower().strip()

        # Normalize input for two modes: code-like vs city-name
        raw = (q or "").strip()
        if not raw:
            return {"success": True, "suggestions": [], "total": 0}
        query = raw.upper()
        norm_query = _norm_txt(raw)

        # Limit code-like queries to 5 chars (AAA01)
        if len(query) > 48:
            # Allow longer for city names, but cap at reasonable length
            raw = raw[:48]
            query = raw.upper()
            norm_query = _norm_txt(raw)

        # Check if location stats index exists; if missing, try a one-off backfill (path layout changed)
        idx_exists = False
        try:
            idx_exists = opensearch_config.client.indices.exists(index=opensearch_config.stats_loc_index)
        except Exception:
            idx_exists = False
        if not idx_exists:
            return {"success": False, "message": "Location index not found. Please trigger reindex first.", "suggestions": []}

        suggestions: list[dict] = []

        # Determine if user typed a code-like prefix (AAA, AAA0, AAA01) or a city name
        is_code_like = False
        import re
        if re.fullmatch(r"[A-Z]{1,3}[0-9]{0,2}", query):
            is_code_like = True

        if is_code_like:
            # Use prefix query for ultra-fast code suggestions
            code_prefix = query[:5]
            body = {
                "size": 0,
                "_source": False,
                "aggs": {
                    "matching_locations": {
                        "terms": {
                            "field": "key",
                            "size": min(limit, 200),
                            "include": f"{code_prefix}.*",
                            "order": {"_key": "asc"}
                        }
                    }
                },
                "query": {"prefix": {"key": code_prefix}}
            }
            res = opensearch_config.client.search(index=opensearch_config.stats_loc_index, body=body)
            if "aggregations" in res and "matching_locations" in res["aggregations"]:
                for bucket in res["aggregations"]["matching_locations"]["buckets"]:
                    location_code = bucket["key"]
                    if location_code and len(location_code) >= 3:
                        city_code = location_code[:3]
                        try:
                            city_name = resolve_city_name(city_code)
                            display = f"{location_code} ({city_name})" if city_name and city_name != city_code else location_code
                        except Exception:
                            city_name = city_code
                            display = location_code
                        suggestions.append({
                            "code": location_code,
                            "display": display,
                            "city": city_name
                        })
        else:
            # City name search: find matching 3-letter city codes by name (accent-insensitive)
            codes_map = get_city_code_map() if get_city_code_map else {}
            if not isinstance(codes_map, dict):
                codes_map = {}
            # Build reverse lookup using normalized names
            matched_codes: list[str] = []
            for code3, name in codes_map.items():
                if not code3 or not name:
                    continue
                if norm_query in _norm_txt(name):
                    matched_codes.append(str(code3).upper())

            if matched_codes:
                # Single OS query to fetch all location codes for the matched city codes using regex include
                # Build a regex like ^(MXX|NXX).*
                pattern = "^(" + "|".join(re.escape(c) for c in matched_codes) + ").*"
                body = {
                    "size": 0,
                    "_source": False,
                    "aggs": {
                        "matching_locations": {
                            "terms": {
                                "field": "key",
                                "size": min(max(limit * 4, 200), 1000),
                                "include": pattern,
                                "order": {"_key": "asc"}
                            }
                        }
                    }
                }
                res = opensearch_config.client.search(index=opensearch_config.stats_loc_index, body=body)
                # Group results by city code
                by_city: dict[str, list[str]] = {c: [] for c in matched_codes}
                if "aggregations" in res and "matching_locations" in res["aggregations"]:
                    for bucket in res["aggregations"]["matching_locations"]["buckets"]:
                        k = bucket["key"]
                        if not k or len(k) < 3:
                            continue
                        c = k[:3]
                        if c in by_city:
                            by_city[c].append(k)

                # Compose suggestions: for each matched city, add an 'All locations' item and then its specific locations
                total_budget = max(limit, 10)
                for c in matched_codes:
                    city_name = resolve_city_name(c)
                    # Always add the city-level suggestion first
                    suggestions.append({
                        "code": c,
                        "display": f"{c} ({city_name}) – All locations",
                        "city": city_name
                    })
                    # Add individual locations for this city
                    locs = sorted(by_city.get(c, []))
                    for k in locs:
                        if len(suggestions) >= total_budget:
                            break
                        suggestions.append({
                            "code": k,
                            "display": f"{k} ({city_name})",
                            "city": city_name
                        })

        return {
            "success": True,
            "suggestions": suggestions,
            "total": len(suggestions),
            "query": query,
            "mode": "suggest"
        }

    except Exception as e:
        logger.error(f"Error in location code suggestions: {e}")
        return {
            "success": False,
            "message": f"Search failed: {str(e)}",
            "suggestions": []
        }


@router.get("/fast/by_location")
async def get_stats_by_location_fast(q: str) -> Dict:
    """
    Fast location-specific statistics using pre-computed OpenSearch location snapshots.
    Much faster than parsing CSV files - uses values computed during reindexing.

    Performance optimizations for city searches (3-letter codes):
    - Source field filtering to reduce payload size
    - Efficient aggregation using dictionaries
    - Early termination for basic stats
    """
    try:
        query = q.strip().upper()

        def _safe_int(value: Any) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                try:
                    return int(float(value))
                except (TypeError, ValueError):
                    return 0

        def _vlan_sort_key_from_value(value: str) -> tuple[int, Any]:
            try:
                return (0, int(value))
            except Exception:
                return (1, value)

        def _normalize_vlan_summary(doc: Dict[str, Any]) -> Dict[str, Any]:
            usage = doc.get("vlanUsage") or []
            aggregated: Dict[str, int] = {}
            for item in usage:
                if not isinstance(item, dict):
                    continue
                vlan = str(item.get("vlan", "")).strip()
                if not vlan:
                    continue
                count = max(_safe_int(item.get("count", 0)), 0)
                aggregated[vlan] = aggregated.get(vlan, 0) + count

            sanitized_usage = [{"vlan": vlan, "count": count} for vlan, count in aggregated.items()]
            sanitized_usage.sort(key=lambda entry: _vlan_sort_key_from_value(entry["vlan"]))

            stored_top = doc.get("topVLANs") or []
            sanitized_top: List[Dict[str, Any]] = []
            for entry in stored_top:
                if not isinstance(entry, dict):
                    continue
                vlan = str(entry.get("vlan", "")).strip()
                if not vlan:
                    continue
                count = aggregated.get(vlan, _safe_int(entry.get("count", 0)))
                sanitized_top.append({"vlan": vlan, "count": count})

            if not sanitized_top:
                sanitized_top = sorted(
                    [{"vlan": vlan, "count": count} for vlan, count in aggregated.items()],
                    key=lambda entry: (-_safe_int(entry.get("count", 0)), _vlan_sort_key_from_value(str(entry.get("vlan", ""))))
                )[:3]
            else:
                sanitized_top.sort(key=lambda entry: (-_safe_int(entry.get("count", 0)), _vlan_sort_key_from_value(str(entry.get("vlan", "")))))
                sanitized_top = sanitized_top[:3]

            doc["topVLANs"] = sanitized_top

            if aggregated or not sanitized_top:
                doc["vlanUsage"] = sanitized_usage
            else:
                fallback_usage = [
                    {"vlan": entry.get("vlan", ""), "count": _safe_int(entry.get("count", 0))}
                    for entry in sanitized_top if isinstance(entry, dict)
                ]
                fallback_usage.sort(key=lambda entry: _vlan_sort_key_from_value(str(entry["vlan"])) )
                doc["vlanUsage"] = fallback_usage

            if aggregated:
                unique_count = len(aggregated)
            else:
                unique_count = len({entry["vlan"] for entry in sanitized_top if isinstance(entry, dict) and entry.get("vlan")})
            doc["uniqueVLANCount"] = unique_count

            return doc

        if not query:
            return {"success": False, "message": "Location query is required"}

        # Determine mode based on query pattern
        # Supported now:
        #  - Full code: 3 letters + 2 digits (e.g. ABC01)
        #  - Prefixes: 1 or 2 letters (A, AB) -> broad search
        #  - City prefix: 3 letters (ABC)
        #  - Partial location: 3 letters + 1 digit (ABC0)
        import re
        if re.fullmatch(r"[A-Z]{3}[0-9]{2}", query):
            mode = "code"
        elif re.fullmatch(r"[A-Z]{3}[0-9]", query):
            mode = "prefix"  # 4-char partial code
        elif re.fullmatch(r"[A-Z]{1,3}", query):
            mode = "prefix"  # 1-3 letter prefix
        else:
            mode = "invalid"
        if mode == "invalid":
            return {"success": False, "message": "Query must be one of: full code ABC01, 1-3 letter prefix (A / AB / ABC), or partial code ABC0"}

        # Check if location stats index exists
        if not opensearch_config.client.indices.exists(index=opensearch_config.stats_loc_index):
            return {
                "success": False,
                "message": "No location stats index found. Please trigger reindex first.",
                "data": {
                    "query": query,
                    "mode": mode,
                    "totalPhones": 0,
                    "totalSwitches": 0,
                    "phonesWithKEM": 0,
                    "phonesByModel": [],
                    "phonesByModelJustiz": [],
                    "phonesByModelJVA": [],
                    "vlanUsage": [],
                    "topVLANs": [],
                    "uniqueVLANCount": 0,
                    "switches": [],
                    "kemPhones": [],
                }
            }

        # Re-evaluate mode (defensive – query may be reused later)
        if re.fullmatch(r"[A-Z]{3}[0-9]{2}", query):
            mode = "code"
        elif re.fullmatch(r"[A-Z]{3}[0-9]", query):
            mode = "prefix"
        elif re.fullmatch(r"[A-Z]{1,3}", query):
            mode = "prefix"
        else:
            mode = "invalid"
        if mode == "invalid":
            return {"success": False, "message": "Query must be one of: full code ABC01, 1-3 letter prefix (A / AB / ABC), or partial code ABC0"}

        if mode == "code":
            preferred_files = _preferred_stats_files(limit=8)
            if "netspeed.csv" not in preferred_files:
                preferred_files.insert(0, "netspeed.csv")
            location_doc: Dict[str, Any] | None = None
            for candidate in preferred_files:
                try:
                    res_candidate = opensearch_config.client.search(
                        index=opensearch_config.stats_loc_index,
                        body={
                            "size": 1,
                            "sort": [{"date": {"order": "desc"}}],
                            "query": {
                                "bool": {
                                    "filter": [
                                        {"term": {"key": {"value": query}}},
                                        {"term": {"file": {"value": candidate}}},
                                    ]
                                }
                            },
                        },
                    )
                except Exception:
                    continue
                candidate_hits = res_candidate.get("hits", {}).get("hits", [])
                if candidate_hits:
                    location_doc = candidate_hits[0].get("_source", {}) or {}
                    break
            if location_doc is None:
                try:
                    fallback = opensearch_config.client.search(
                        index=opensearch_config.stats_loc_index,
                        body={
                            "size": 1,
                            "sort": [
                                {"date": {"order": "desc"}},
                                {"file": {"order": "asc"}},
                            ],
                            "query": {
                                "bool": {
                                    "filter": [
                                        {"term": {"key": {"value": query}}},
                                    ]
                                }
                            },
                        },
                    )
                except Exception:
                    fallback = {}
                hits_latest = fallback.get("hits", {}).get("hits", [])
                if not hits_latest:
                    return {
                        "success": True,
                        "message": f"No data found for location {query}",
                        "data": {
                            "query": query,
                            "mode": "fast",
                            "totalPhones": 0,
                            "totalSwitches": 0,
                            "phonesWithKEM": 0,
                            "phonesByModel": [],
                            "phonesByModelJustiz": [],
                            "phonesByModelJVA": [],
                            "vlanUsage": [],
                            "topVLANs": [],
                            "uniqueVLANCount": 0,
                            "switches": [],
                            "kemPhones": [],
                        },
                    }
                location_doc = hits_latest[0].get("_source", {}) or {}
            if location_doc is None:
                location_doc = {}
            try:
                kem_list = location_doc.get("kemPhones")
                if isinstance(kem_list, list):
                    location_doc["kemPhonesCount"] = len(kem_list)
                    if kem_list and len(kem_list) != int(location_doc.get("phonesWithKEM", 0) or 0):
                        location_doc["phonesWithKEM"] = len(kem_list)
            except Exception:
                pass
        else:  # prefix mode - aggregate all locations starting with this prefix (1-4 chars)
            # Optimized: Only fetch necessary fields and use smaller payloads
            body = {
                "size": 0,
                "aggs": {
                    "locations": {
                        "terms": {
                            "field": "key",
                            # Broader prefixes (1-2 letters) can match many entries – cap size higher but reasonable
                            "size": 2000 if len(query) <= 2 else 1500 if len(query) == 3 else 1200
                        },
                        "aggs": {
                            "latest": {
                                "top_hits": {
                                    "sort": [{"date": {"order": "desc"}}],
                                    "size": 1,
                                    "_source": [
                                        "totalPhones", "totalSwitches", "phonesWithKEM",
                                        "phonesByModel", "phonesByModelJustiz", "phonesByModelJVA",
                                        "vlanUsage", "switches", "kemPhones"
                                    ]
                                }
                            }
                        }
                    }
                },
                "query": {
                    "bool": {
                        "filter": [
                            {"prefix": {"key": query}}
                        ]
                    }
                }
            }

            res = opensearch_config.client.search(index=opensearch_config.stats_loc_index, body=body)

            if not res["aggregations"]["locations"]["buckets"]:
                return {
                    "success": True,
                    "message": f"No data found for locations starting with {query}",
                    "data": {
                        "query": query,
                        "mode": "prefix",
                        "totalPhones": 0,
                        "totalSwitches": 0,
                        "phonesWithKEM": 0,
                        "phonesByModel": [],
                        "phonesByModelJustiz": [],
                        "phonesByModelJVA": [],
                        "vlanUsage": [],
                        "topVLANs": [],
                        "uniqueVLANCount": 0,
                        "switches": [],
                        "kemPhones": [],
                    }
                }

            # Efficient aggregation: Use direct dictionary operations instead of nested loops
            # Pre-allocate data structures for better performance
            phones_by_model = {}
            phones_by_model_justiz = {}
            phones_by_model_jva = {}
            vlan_usage = {}
            switches_dict = {}  # hostname -> {vlan -> count}
            kem_phones = []

            total_phones = 0
            total_switches = 0
            phones_with_kem = 0

            # Single pass aggregation for all data
            for bucket in res["aggregations"]["locations"]["buckets"]:
                if bucket["latest"]["hits"]["hits"]:
                    doc = bucket["latest"]["hits"]["hits"][0]["_source"]

                    # Basic counters
                    total_phones += doc.get("totalPhones", 0)
                    total_switches += doc.get("totalSwitches", 0)
                    phones_with_kem += doc.get("phonesWithKEM", 0)

                    # Efficient phone model aggregation
                    for model_data in doc.get("phonesByModel", []):
                        model = model_data.get("model", "Unknown")
                        count = model_data.get("count", 0)
                        phones_by_model[model] = phones_by_model.get(model, 0) + count

                    for model_data in doc.get("phonesByModelJustiz", []):
                        model = model_data.get("model", "Unknown")
                        count = model_data.get("count", 0)
                        phones_by_model_justiz[model] = phones_by_model_justiz.get(model, 0) + count

                    for model_data in doc.get("phonesByModelJVA", []):
                        model = model_data.get("model", "Unknown")
                        count = model_data.get("count", 0)
                        phones_by_model_jva[model] = phones_by_model_jva.get(model, 0) + count

                    # Efficient VLAN aggregation
                    for vlan_data in doc.get("vlanUsage", []):
                        vlan = vlan_data.get("vlan", "")
                        count = vlan_data.get("count", 0)
                        if vlan:
                            vlan_usage[vlan] = vlan_usage.get(vlan, 0) + count

                    # Efficient switch aggregation (ALL switches, no limits)
                    switches_data = doc.get("switches", [])
                    if switches_data:
                        for switch_data in switches_data:
                            if isinstance(switch_data, dict):
                                hostname = switch_data.get("hostname", "")
                                vlans_data = switch_data.get("vlans", [])
                                if hostname:
                                    if hostname not in switches_dict:
                                        switches_dict[hostname] = {}

                                    # Direct VLAN aggregation
                                    for vlan_obj in vlans_data:
                                        if isinstance(vlan_obj, dict):
                                            vlan = vlan_obj.get("vlan", "")
                                            count = vlan_obj.get("count", 0)
                                            if vlan:
                                                switches_dict[hostname][vlan] = switches_dict[hostname].get(vlan, 0) + count

                    # KEM phones aggregation
                    kem_phones_data = doc.get("kemPhones", [])
                    if kem_phones_data:
                        kem_phones.extend(kem_phones_data)

            # Convert aggregated data to final format efficiently
            location_doc = {
                "query": query,
                "mode": "prefix",
                "totalPhones": total_phones,
                "totalSwitches": total_switches,
                # Align semantics: phonesWithKEM equals kemPhones length (unique phones)
                "phonesWithKEM": len(kem_phones),
                "phonesByModel": [{"model": m, "count": c} for m, c in phones_by_model.items()],
                "phonesByModelJustiz": [{"model": m, "count": c} for m, c in phones_by_model_justiz.items()],
                "phonesByModelJVA": [{"model": m, "count": c} for m, c in phones_by_model_jva.items()],
                "vlanUsage": [{"vlan": v, "count": c} for v, c in vlan_usage.items()],
                "topVLANs": [],
                "uniqueVLANCount": 0,
                "switches": [],
                "kemPhones": kem_phones,
                "kemPhonesCount": len(kem_phones),
            }

            # Sort phone models by count (descending)
            location_doc["phonesByModel"].sort(key=lambda x: (-x["count"], x["model"]))
            location_doc["phonesByModelJustiz"].sort(key=lambda x: (-x["count"], x["model"]))
            location_doc["phonesByModelJVA"].sort(key=lambda x: (-x["count"], x["model"]))

            # Sort VLANs numerically
            def vlan_key(item):
                v = item["vlan"]
                try:
                    return (0, int(v))
                except:
                    return (1, v)
            location_doc["vlanUsage"].sort(key=vlan_key)

            # Convert switches to final format - ALL switches included
            switch_list = []
            for hostname, vlans_dict in switches_dict.items():
                vlans_list = [{"vlan": vlan, "count": count} for vlan, count in vlans_dict.items()]
                vlans_list.sort(key=vlan_key)
                switch_list.append({
                    "hostname": hostname,
                    "vlans": vlans_list
                })
            location_doc["switches"] = sorted(switch_list, key=lambda x: x["hostname"])

        location_doc = _normalize_vlan_summary(location_doc)

        # Check if we have sufficient detail data for the UI - NO FALLBACKS
        if not _has_sufficient_detail_data(location_doc):
            logger.warning(f"OpenSearch data for {query} lacks detail information. Please trigger reindex.")
            # Return the incomplete data but mark it as incomplete
            location_doc["incomplete"] = True
            location_doc["message"] = "Incomplete data - please trigger reindex"

        return {
            "success": True,
            "data": location_doc
        }

    except Exception as e:
        logger.error(f"Error in fast location stats: {e}")
        return {
            "success": False,
            "message": "Failed to load location stats from OpenSearch. Please try again later or contact support.",
            "data": {
                "query": query,
                "mode": "fast",
                "totalPhones": 0,
                "totalSwitches": 0,
                "phonesWithKEM": 0,
                "phonesByModel": [],
                "phonesByModelJustiz": [],
                "phonesByModelJVA": [],
                "vlanUsage": [],
                "topVLANs": [],
                "uniqueVLANCount": 0,
                "switches": [],
                "kemPhones": [],
            }
        }


# Helper function to check if OpenSearch data has sufficient detail information
def _has_sufficient_detail_data(location_doc: Dict) -> bool:
    """Check if the location document has enough detail data for the UI.

    Always returns True now since we only use OpenSearch data.
    """
    return True
