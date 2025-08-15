from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import Dict, List, Tuple
import logging

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
            # Skip suspiciously short codes and MAC-like strings
            if model != "Unknown" and (len(model) < 4 or is_mac_like(model)):
                continue
            model_counts[model] = model_counts.get(model, 0) + 1

        phones_by_model = [
            {"model": m, "count": c} for m, c in model_counts.items()
        ]
        phones_by_model.sort(key=lambda x: (-x["count"], x["model"]))

        file_model = FileModel.from_path(str(file_path))
        date_str = file_model.date.strftime('%Y-%m-%d') if file_model.date else None

        return {
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
    """Build a time series of key metrics across netspeed files.

    - Scans /app/data for netspeed.csv and netspeed.csv.N files (optionally backups).
    - Computes basic metrics per file and returns a sorted timeline by date.
    - If limit > 0, return the most recent N entries.
    """
    try:
        data_dir = Path("/app/data")
        if not data_dir.exists():
            return {"success": True, "message": "No data directory", "series": []}

        candidates: List[Path] = []
        for p in data_dir.glob("netspeed.csv*"):
            name = p.name
            if not include_backups and (name.endswith("_bak") or name == "netspeed.csv_bak"):
                continue
            # Only accept base and numeric suffix variants
            if name == "netspeed.csv" or (name.startswith("netspeed.csv.") and name.replace("netspeed.csv.", "").isdigit()):
                candidates.append(p)

        series = []
        for file_path in candidates:
            try:
                # resolve date via FileModel
                fm = FileModel.from_path(str(file_path))
                date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
                # read & compute
                _, rows = read_csv_file_normalized(str(file_path))
                (total_phones, total_switches, total_locations, total_cities, phones_by_model, city_codes) = _compute_basic_stats(rows)
                series.append({
                    "file": fm.name,
                    "date": date_str,
                    "metrics": {
                        "totalPhones": total_phones,
                        "totalSwitches": total_switches,
                        "totalLocations": total_locations,
                        "totalCities": total_cities,
                        "phonesWithKEM": sum(1 for r in rows if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip()),
                        "phonesByModel": phones_by_model,
                        # City names resolved at read-time from mapping; no need to persist
                        "cityCodes": [
                            {"code": c, "name": resolve_city_name(c)} for c in city_codes
                        ],
                    }
                })
            except Exception as _e:
                # Skip problematic files but keep timeline building
                continue

        # If filesystem has no candidates, fall back to persisted OpenSearch snapshots
        if not series:
            try:
                from utils.opensearch import opensearch_config
                # Query all snapshot docs; sort ascending by date then file
                body = {
                    "size": 10000,
                    "sort": [
                        {"date": {"order": "asc", "missing": "_last"}},
                        {"file.keyword": {"order": "asc"}}
                    ],
                    "query": {"match_all": {}},
                    "_source": True,
                }
                res = opensearch_config.client.search(index=opensearch_config.stats_index, body=body)
                hits = res.get("hits", {}).get("hits", [])
                for h in hits:
                    s = h.get("_source", {})
                    date_str = s.get("date")
                    file_name = s.get("file")
                    # Rebuild metrics into the same shape
                    metrics = {
                        "totalPhones": s.get("totalPhones", 0),
                        "totalSwitches": s.get("totalSwitches", 0),
                        "totalLocations": s.get("totalLocations", 0),
                        "totalCities": s.get("totalCities", 0),
                        "phonesWithKEM": s.get("phonesWithKEM", 0),
                        "phonesByModel": s.get("phonesByModel", []),
                        # If old snapshots contained codes, map to names; else leave empty (not persisted)
                        "cityCodes": [
                            {"code": c, "name": resolve_city_name(c)} for c in (s.get("cityCodes") or [])
                        ],
                    }
                    series.append({"file": file_name, "date": date_str, "metrics": metrics})
            except Exception:
                # If OpenSearch not available, keep empty series
                pass

    # sort by date, then by filename fallback
        def k(item):
            d = item.get("date") or ""
            return (d, item.get("file"))

        series.sort(key=k)
        if limit and limit > 0:
            series = series[-limit:]

        return {"success": True, "message": f"Computed {len(series)} timeline points", "series": series}
    except Exception as e:
        logger.error(f"Error building stats timeline: {e}")
        raise HTTPException(status_code=500, detail="Failed to build stats timeline")


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
