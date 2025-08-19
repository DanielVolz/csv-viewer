from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import Dict, List, Tuple, Any
import logging
import time

from models.file import FileModel
from utils.csv_utils import read_csv_file_normalized

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
    """Extract a 5-char location code as 3 letters + 2 digits (e.g., ABC01) from the switch hostname.

    Algorithm:
    - Uppercase the hostname.
    - Scan left to right, first collect 3 ASCII letters [A-Z].
    - Then continue scanning to collect 2 digits [0-9].
    - Return the concatenation if and only if we found 3 letters and 2 digits in that order.
    - Otherwise return None.
    """
    if not hostname:
        return None
    h = hostname.strip().upper()
    letters = []
    digits = []
    i = 0
    # collect letters first
    while i < len(h) and len(letters) < 3:
        ch = h[i]
        if 'A' <= ch <= 'Z':
            letters.append(ch)
        i += 1
    # collect digits after letters
    while i < len(h) and len(digits) < 2:
        ch = h[i]
        if '0' <= ch <= '9':
            digits.append(ch)
        i += 1
    if len(letters) == 3 and len(digits) == 2:
        return ''.join(letters) + ''.join(digits)
    return None


@router.get("/current")
async def get_current_stats(filename: str = "netspeed.csv") -> Dict:
    """Compute statistics for the current CSV file.

    Returns a JSON object with:
      - totalPhones
      - totalSwitches
      - phonesWithKEM
      - phonesByModel: list[{model, count}]
      - file: { name, date }
    """
    try:
        data_dir = Path("/app/data")
        file_path = (data_dir / filename).resolve()

        if not file_path.exists():
            return {
                "success": False,
                "message": f"File {filename} not found",
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

        # Attempt fast path: serve from cache if file unchanged
        st = file_path.stat()
        cache_key = f"{file_path}:{st.st_mtime_ns}:{st.st_size}"
        if _CURRENT_STATS_CACHE.get("key") == cache_key and _CURRENT_STATS_CACHE.get("data"):
            return _CURRENT_STATS_CACHE["data"]  # type: ignore

        # Try OpenSearch snapshot first: if exists for file+date, use it
        file_model = FileModel.from_path(str(file_path))
        date_str = file_model.date.strftime('%Y-%m-%d') if file_model.date else None
        if date_str:
            try:
                from utils.opensearch import opensearch_config
                from opensearchpy.exceptions import NotFoundError
                # Deterministic id in indexer: f"{file}:{date}"
                doc_id = f"{file_model.name}:{date_str}"
                try:
                    snap = opensearch_config.client.get(index=opensearch_config.stats_index, id=doc_id)
                    src = snap.get("_source") if isinstance(snap, dict) else None
                except NotFoundError:
                    src = None
                if src:
                    result = {
                        "success": True,
                        "message": "Statistics loaded (snapshot)",
                        "data": {
                            "totalPhones": int(src.get("totalPhones", 0)),
                            "totalSwitches": int(src.get("totalSwitches", 0)),
                            "totalLocations": int(src.get("totalLocations", 0)),
                            "totalCities": int(src.get("totalCities", 0)),
                            "phonesWithKEM": int(src.get("phonesWithKEM", 0)),
                            "phonesByModel": src.get("phonesByModel", []),
                            "cities": sorted(
                                [{"code": c, "name": resolve_city_name(c)} for c in (src.get("cityCodes") or [])],
                                key=lambda x: x["name"]
                            ),
                        },
                        "file": {"name": file_model.name, "date": date_str},
                    }
                    _CURRENT_STATS_CACHE["key"] = cache_key
                    _CURRENT_STATS_CACHE["data"] = result
                    return result
            except Exception:
                pass

        # Compute from CSV as fallback
        headers, rows = read_csv_file_normalized(str(file_path))

        total_phones = len(rows)
        switches = set()
        phones_with_kem = 0
        model_counts: Dict[str, int] = {}
        locations = set()
        city_codes = set()

        for r in rows:
            sh = (r.get("Switch Hostname") or "").strip()
            if sh:
                switches.add(sh)
                loc = extract_location(sh)
                if loc:
                    locations.add(loc)
                    city_codes.add(loc[:3])

            if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                phones_with_kem += 1

            model = (r.get("Model Name") or "").strip() or "Unknown"
            if model != "Unknown" and (len(model) < 4 or is_mac_like(model)):
                continue
            model_counts[model] = model_counts.get(model, 0) + 1

        phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]
        phones_by_model.sort(key=lambda x: (-x["count"], x["model"]))

        result = {
            "success": True,
            "message": "Statistics computed",
            "data": {
                "totalPhones": total_phones,
                "totalSwitches": len(switches),
                "totalLocations": len(locations),
                "totalCities": len(city_codes),
                "phonesWithKEM": phones_with_kem,
                "phonesByModel": phones_by_model,
                "cities": sorted(
                    [{"code": c, "name": resolve_city_name(c)} for c in city_codes],
                    key=lambda x: x["name"]
                ),
            },
            "file": {"name": file_model.name, "date": date_str},
        }
        _CURRENT_STATS_CACHE["key"] = cache_key
        _CURRENT_STATS_CACHE["data"] = result
        return result
    except Exception as e:
        logger.error(f"Error computing stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute statistics")


def _compute_basic_stats(rows: List[Dict]) -> Tuple[int, int, int, int, List[Dict], List[str]]:
    """Return core metrics from normalized rows.

    Returns: (total_phones, total_switches, total_locations, total_cities, phones_by_model, city_codes_sorted)
    """
    total_phones = len(rows)
    switches = set()
    phones_with_kem = 0
    model_counts: Dict[str, int] = {}
    locations = set()
    city_codes = set()

    for r in rows:
        sh = (r.get("Switch Hostname") or "").strip()
        if sh:
            switches.add(sh)
            loc = extract_location(sh)
            if loc:
                locations.add(loc)
                city_codes.add(loc[:3])

        if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
            phones_with_kem += 1

        model = (r.get("Model Name") or "").strip() or "Unknown"
        if model != "Unknown" and (len(model) < 4 or is_mac_like(model)):
            continue
        model_counts[model] = model_counts.get(model, 0) + 1

    phones_by_model = [
        {"model": m, "count": c} for m, c in model_counts.items()
    ]
    phones_by_model.sort(key=lambda x: (-x["count"], x["model"]))
    return (
        total_phones,
        len(switches),
        len(locations),
        len(city_codes),
        phones_by_model,
        sorted(list(city_codes)),
    )


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
        from utils.opensearch import opensearch_config
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
                backfill_stats_snapshots("/app/data")
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
        result = {"success": True, "message": f"Computed {len(series)} timeline points (snapshot)", "series": series}
        _TIMELINE_CACHE[eff_limit] = (now + 60.0, result)
        return result
    except Exception as e:
        logger.error(f"Error building stats timeline: {e}")
        return {"success": True, "message": "No timeline data available (snapshot)", "series": []}


@router.get("/timeline/by_location")
async def get_stats_timeline_by_location(q: str, limit: int = 0, include_backups: bool = False) -> Dict:
    """Build a time series of key metrics for a specific location code (AAA01) or prefix (AAA).

    Scans recent netspeed files and computes metrics for the subset of rows matching the location query.
    Caches results for 60 seconds.
    """
    try:
        if not q or not q.strip():
            return {"success": False, "message": "Missing query parameter 'q'", "series": []}
        query = q.strip().upper()
        mode = "code" if len(query) == 5 else ("prefix" if len(query) == 3 else "invalid")
        if mode == "invalid":
            return {"success": False, "message": "Query must be a 5-char code (AAA01) or 3-letter prefix (AAA)", "series": []}

        # limit==0 means full history; otherwise truncate to first N days from earliest
        eff_limit = limit if limit and limit > 0 else 0
        now = time.time()
        cache_key = (query, eff_limit)
        cached = _TIMELINE_BY_LOC_CACHE.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

        # Only use OpenSearch snapshots, never CSV fallback
        from utils.opensearch import opensearch_config
        series: List[Dict] = []
        if mode == "code":
            # Fetch more than needed to build a continuous window ending at the latest date
            max_docs = 10000
            body = {
                "size": max_docs,
                "sort": [{"date": {"order": "asc"}}, {"file": {"order": "desc"}}],
                "query": {"term": {"key": {"value": query}}},
                "_source": ["file", "date", "totalPhones", "totalSwitches", "phonesWithKEM"],
            }
            # If per-location index is missing, try on-demand backfill once
            try:
                exists_loc = opensearch_config.client.indices.exists(index=opensearch_config.stats_loc_index)
            except Exception:
                exists_loc = False
            if not exists_loc:
                try:
                    from tasks.tasks import backfill_location_snapshots
                    backfill_location_snapshots("/app/data")
                    try:
                        opensearch_config.client.indices.refresh(index=opensearch_config.stats_loc_index)
                    except Exception:
                        pass
                except Exception:
                    pass
            res = opensearch_config.client.search(index=opensearch_config.stats_loc_index, body=body)
            hits = res.get("hits", {}).get("hits", [])
            if hits:
                # Reduce to one entry per date (prefer netspeed.csv if multiple)
                by_date: Dict[str, Dict] = {}
                for h in hits:
                    s = h.get("_source", {})
                    d = s.get("date")
                    if not d or d in by_date:
                        # allow update below if this one is netspeed.csv
                        if s.get("file") != "netspeed.csv":
                            continue
                    by_date[d] = {
                        "file": s.get("file"),
                        "date": d,
                        "metrics": {
                            "totalPhones": s.get("totalPhones", 0),
                            "totalSwitches": s.get("totalSwitches", 0),
                            "phonesWithKEM": s.get("phonesWithKEM", 0),
                            "phonesByModel": [],
                            "cityCodes": [],
                        },
                    }
                # Build window from earliest to latest, carry-forward gaps
                from datetime import datetime as _dt, timedelta as _td
                fmt = "%Y-%m-%d"
                if by_date:
                    min_date_str = min(by_date.keys())
                    max_date_str = max(by_date.keys())
                    min_date = _dt.strptime(min_date_str, fmt)
                    max_date = _dt.strptime(max_date_str, fmt)
                    current = by_date.get(min_date_str)
                    out: List[Dict] = []
                    day = min_date
                    while day <= max_date:
                        dstr = day.strftime(fmt)
                        if dstr in by_date:
                            current = by_date[dstr]
                        if current is not None:
                            out.append({
                                "file": current.get("file"),
                                "date": dstr,
                                "metrics": current.get("metrics", {}),
                            })
                        day += _td(days=1)
                    if eff_limit and len(out) > eff_limit:
                        out = out[:eff_limit]
                    series = out
        else:
            # prefix mode: aggregate sums per date over all matching location codes
            body = {
                "size": 0,
                "query": {"prefix": {"key": {"value": query}}},
                "aggs": {
                    "by_date": {
                        "date_histogram": {"field": "date", "calendar_interval": "1d"},
                        "aggs": {
                            "sumPhones": {"sum": {"field": "totalPhones"}},
                            "sumSwitches": {"sum": {"field": "totalSwitches"}},
                            "sumKEM": {"sum": {"field": "phonesWithKEM"}},
                        },
                    }
                }
            }
            res = opensearch_config.client.search(index=opensearch_config.stats_loc_index, body=body)
            buckets = res.get("aggregations", {}).get("by_date", {}).get("buckets", [])
            buckets_sorted = sorted(buckets, key=lambda b: b.get("key", 0))
            if buckets_sorted:
                # Map to per-date metrics
                by_date = {}
                for b in buckets_sorted:
                    d = b.get("key_as_string")
                    if not d:
                        continue
                    by_date[d] = {
                        "file": None,
                        "date": d,
                        "metrics": {
                            "totalPhones": int(b.get("sumPhones", {}).get("value", 0) or 0),
                            "totalSwitches": int(b.get("sumSwitches", {}).get("value", 0) or 0),
                            "phonesWithKEM": int(b.get("sumKEM", {}).get("value", 0) or 0),
                            "phonesByModel": [],
                            "cityCodes": [],
                        },
                    }
                from datetime import datetime as _dt, timedelta as _td
                fmt = "%Y-%m-%d"
                min_date_str = min(by_date.keys())
                max_date_str = max(by_date.keys())
                min_date = _dt.strptime(min_date_str, fmt)
                max_date = _dt.strptime(max_date_str, fmt)
                current = by_date.get(min_date_str)
                out: List[Dict] = []
                day = min_date
                while day <= max_date:
                    dstr = day.strftime(fmt)
                    if dstr in by_date:
                        current = by_date[dstr]
                    if current is not None:
                        out.append({
                            "file": None,
                            "date": dstr,
                            "metrics": current.get("metrics", {}),
                        })
                    day += _td(days=1)
                if eff_limit and len(out) > eff_limit:
                    out = out[:eff_limit]
                series = out

        result = {"success": True, "message": f"Computed {len(series)} location timeline points (snapshot)", "series": series}
        _TIMELINE_BY_LOC_CACHE[cache_key] = (now + 60.0, result)
        return result
    except Exception as e:
        logger.error(f"Error building location timeline: {e}")
        return {"success": True, "message": "No location timeline data available (snapshot)", "series": []}


@router.get("/archive")
async def get_archive(date: str, file: str | None = None, size: int = 1000) -> Dict:
    """Return archived rows for a specific snapshot date (and optional file name).

    Args:
        date: YYYY-MM-DD snapshot date
        file: optional file variant (e.g., netspeed.csv or netspeed.csv.3)
        size: max docs to return (default 1000)
    """
    try:
        from utils.opensearch import opensearch_config
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
    """Debug helper: compare distinct city prefixes found in CSV vs. mapping keys.

    Returns counts and small samples of differences to explain discrepancies like 84 vs 97.
    """
    try:
        mapping = {}
        if get_city_code_map:
            mapping = get_city_code_map()
        map_keys = set(mapping.keys())

        file_path = (Path("/app/data") / filename).resolve()
        if not file_path.exists():
            return {
                "success": True,
                "message": f"File {filename} not found",
                "data": {
                    "mappingCount": len(map_keys),
                    "csvCityCount": 0,
                    "missingInMapping": [],
                    "missingInCSV": sorted(list(map_keys))[:limit],
                },
            }

        _, rows = read_csv_file_normalized(str(file_path))
        prefixes = set()
        for r in rows:
            sh = (r.get("Switch Hostname") or "").strip()
            if not sh:
                continue
            loc = extract_location(sh)
            if not loc:
                continue
            prefixes.add(loc[:3])

        missing_in_mapping = sorted([p for p in prefixes if p not in map_keys])
        missing_in_csv = sorted([k for k in map_keys if k not in prefixes])

        if limit and limit > 0:
            missing_in_mapping = missing_in_mapping[:limit]
            missing_in_csv = missing_in_csv[:limit]

        return {
            "success": True,
            "message": "City mapping debug computed",
            "data": {
                "mappingCount": len(map_keys),
                "csvCityCount": len(prefixes),
                "missingInMapping": missing_in_mapping,
                "missingInCSV": missing_in_csv,
            },
        }
    except Exception as e:
        logger.error(f"Error debugging city mapping: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute city debug info")


@router.get("/locations")
async def list_locations(q: str = "", filename: str = "netspeed.csv", limit: int = 25) -> Dict:
    """Return distinct 5-letter location codes derived from Switch Hostname.

    Matching uses case-insensitive substring on the location code.
    """
    try:
        file_path = (Path("/app/data") / filename).resolve()
        if not file_path.exists():
            return {"success": True, "options": []}

        _, rows = read_csv_file_normalized(str(file_path))
        term = (q or "").strip().upper()
        locs = set()
        for r in rows:
            sh = (r.get("Switch Hostname") or "").strip()
            loc = extract_location(sh)
            if not loc:
                continue
            if not term or term in loc:
                locs.add(loc)
        options = sorted(locs)
        if limit and limit > 0:
            options = options[:limit]
        return {"success": True, "options": options}
    except Exception as e:
        logger.error(f"Error listing locations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list locations")


@router.get("/by_location")
async def stats_by_location(q: str, filename: str = "netspeed.csv") -> Dict:
    """Compute statistics for rows whose derived location code equals q (5-letter code).

    Returns totals and grouped aggregates (models, VLANs, switches) for the filtered subset.
    """
    try:
        if not q or not q.strip():
            return {"success": False, "message": "Missing query parameter 'q'", "data": {}}

        file_path = (Path("/app/data") / filename).resolve()
        if not file_path.exists():
            return {"success": False, "message": f"File {filename} not found", "data": {}}

        _, rows = read_csv_file_normalized(str(file_path))
        query = q.strip().upper()
        mode = "code" if len(query) == 5 else ("prefix" if len(query) == 3 else "invalid")
        if mode == "invalid":
            return {"success": False, "message": "Query must be a 5-char code (AAA01) or 3-letter prefix (AAA)", "data": {}}
        subset = []
        for r in rows:
            sh = (r.get("Switch Hostname") or "").strip()
            loc = extract_location(sh)
            if not loc:
                continue
            if mode == "code":
                if loc == query:
                    subset.append(r)
            else:  # prefix
                if loc.startswith(query):
                    subset.append(r)

        total_phones = len(subset)
        switches = sorted({(r.get("Switch Hostname") or "").strip() for r in subset if (r.get("Switch Hostname") or "").strip()})
        # Build per-switch VLAN usage (counts and distinct count)
        switch_vlan_counts: Dict[str, Dict[str, int]] = {}
        for r in subset:
            sh = (r.get("Switch Hostname") or "").strip()
            if not sh:
                continue
            vlan = (r.get("Voice VLAN") or "").strip()
            if not vlan:
                continue
            by_vlan = switch_vlan_counts.setdefault(sh, {})
            by_vlan[vlan] = by_vlan.get(vlan, 0) + 1
        switch_details = []
        for sh in switches:
            by_vlan = switch_vlan_counts.get(sh, {})
            detail = {
                "hostname": sh,
                "vlanCount": len(by_vlan.keys()),
                "vlans": [{"vlan": v, "count": c} for v, c in by_vlan.items()],
            }
            # Optional: sort vlans numerically
            def _vk(item):
                try:
                    return (0, int(item["vlan"]))
                except:
                    return (1, item["vlan"])
            detail["vlans"].sort(key=_vk)
            switch_details.append(detail)
        phones_with_kem = sum(1 for r in subset if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip())

        # Phones by Model
        model_counts: Dict[str, int] = {}
        for r in subset:
            model = (r.get("Model Name") or "").strip() or "Unknown"
            if model != "Unknown" and (len(model) < 4 or is_mac_like(model)):
                continue
            model_counts[model] = model_counts.get(model, 0) + 1
        phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]
        phones_by_model.sort(key=lambda x: (-x["count"], x["model"]))

        # VLAN usage
        vlan_counts: Dict[str, int] = {}
        for r in subset:
            vlan = (r.get("Voice VLAN") or "").strip()
            if not vlan:
                continue
            vlan_counts[vlan] = vlan_counts.get(vlan, 0) + 1
        vlan_usage = [{"vlan": v, "count": c} for v, c in vlan_counts.items()]
        # Sort numerically when possible
        def vlan_key(item):
            v = item["vlan"]
            try:
                return (0, int(v))
            except:
                return (1, v)
        vlan_usage.sort(key=vlan_key)

        # Build detailed list of phones with KEM for expandable UI
        kem_phones_fields = [
            "IP Address", "Model Name", "MAC Address", "Switch Hostname", "Switch Port", "KEM", "KEM 2",
        ]
        kem_phones = []
        for r in subset:
            if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                item = {k: (r.get(k) or "").strip() for k in kem_phones_fields}
                kem_phones.append(item)

        return {
            "success": True,
            "message": "Location statistics computed",
            "data": {
                "query": query,
                "mode": mode,
                "totalPhones": total_phones,
                "totalSwitches": len(switches),
                "phonesWithKEM": phones_with_kem,
                "phonesByModel": phones_by_model,
                "vlanUsage": vlan_usage,
                "switches": switches,
                "switchDetails": switch_details,
                "kemPhones": kem_phones,
            },
        }
    except Exception as e:
        logger.error(f"Error computing stats by location: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute location statistics")
