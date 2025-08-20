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
_TIMELINE_TOP_CACHE: Dict[Tuple[int, Tuple[str, ...], int], Tuple[float, Dict]] = {}
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
    - If limit > 0, returns the first N days from earliest; 0 = full history.
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

        from utils.opensearch import opensearch_config
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
                    from tasks.tasks import backfill_location_snapshots
                    backfill_location_snapshots("/app/data")
                    try:
                        client.indices.refresh(index=opensearch_config.stats_loc_index)
                    except Exception:
                        pass
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
            by_date[d] = {
                "file": None,
                "date": d,
                "metrics": {
                    "totalPhones": int(b.get("sumPhones", {}).get("value", 0) or 0),
                    "totalSwitches": int(b.get("sumSwitches", {}).get("value", 0) or 0),
                    "phonesWithKEM": int(b.get("sumKEM", {}).get("value", 0) or 0),
                    "phonesByModel": [],
                    "cityCodes": [],
                }
            }
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

        from utils.opensearch import opensearch_config
        client = opensearch_config.client

        # Ensure index exists
        try:
            exists = client.indices.exists(index=opensearch_config.stats_loc_index)
        except Exception:
            exists = False
        if not exists:
            try:
                from tasks.tasks import backfill_location_snapshots
                backfill_location_snapshots("/app/data")
                try:
                    client.indices.refresh(index=opensearch_config.stats_loc_index)
                except Exception:
                    pass
            except Exception:
                pass

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
                body_series = {
                    "size": 0,
                    "query": {"bool": {"filter": ([
                        {"bool": {"should": [{"prefix": {"key": {"value": c}}} for c in selected_keys], "minimum_should_match": 1}}
                    ] + date_filters)}},
                    "aggs": {
                        "by_date": {
                            "date_histogram": {"field": "date", "calendar_interval": "1d"},
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
            for b in buckets:
                d = b.get("key_as_string")
                if not d:
                    continue
                by_date[d] = {"file": None, "date": d, "metrics": {
                    "totalPhones": int(b.get("sumPhones", {}).get("value", 0) or 0),
                    "totalSwitches": int(b.get("sumSwitches", {}).get("value", 0) or 0),
                    "phonesWithKEM": int(b.get("sumKEM", {}).get("value", 0) or 0),
                }}
            series: List[Dict] = []
            if by_date:
                window = build_anchor_window(min(by_date.keys()), max(by_date.keys()))
                current = by_date.get(window[0])
                for dstr in window:
                    if dstr in by_date:
                        current = by_date[dstr]
                    if current is not None:
                        series.append({"file": None, "date": dstr, "metrics": current.get("metrics", {})})
            label = "cities" if (group or "city").lower() == "city" else "locations"
            result = {"success": True, "message": f"Computed {len(series)} top-{label} timeline points (aggregate)", "series": series, "selected": selected_keys, "mode": "aggregate", "group": (group or "city").lower()}
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
                    "aggs": {"by_key": {"terms": {"field": "key", "size": len(selected_keys)}, "aggs": {
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
