import os
from celery import Celery
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime
from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError

from config import settings
from utils.opensearch import OpenSearchUnavailableError, opensearch_config
from utils.index_state import load_state, save_state, update_file_state, update_totals, is_file_current, start_active, update_active, clear_active
from utils.csv_utils import (
    read_csv_file_normalized,
    count_unique_data_rows,
    deduplicate_phone_rows,
    phone_row_identity,
)
from utils.path_utils import (
    get_data_root,
    resolve_current_file,
    netspeed_files_ordered,
    collect_netspeed_files,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _calculate_retry_delay(attempt: int) -> int:
    """Compute exponential backoff with max cap for OpenSearch retries."""
    base = max(1, int(getattr(settings, "OPENSEARCH_RETRY_BASE_SECONDS", 5)))
    max_seconds = max(base, int(getattr(settings, "OPENSEARCH_RETRY_MAX_SECONDS", 60)))
    delay = base * (2 ** attempt)
    return min(delay, max_seconds)

# Initialize Celery
app = Celery('csv_viewer')

# Load Celery configuration
app.config_from_object('celeryconfig')


@app.task(name='tasks.search_opensearch')
def search_opensearch(query: str,
                      field: Optional[str] = None,
                      include_historical: bool = False,
                      size: int = 20000) -> dict:
    """Celery task to perform a search in OpenSearch.

    Returns a structured dict compatible with the API layer.
    """
    try:
        from time import perf_counter
        t0 = perf_counter()
        headers, documents = opensearch_config.search(
            query=query,
            field=field,
            include_historical=include_historical,
            size=size,
        )

        # Return all columns from OpenSearch without filtering
        # This allows search results to display all available columns from any CSV format
        took_ms = int((perf_counter() - t0) * 1000)
        return {
            "status": "success",
            "message": f"Found {len(documents)} results for '{query}'",
            "headers": headers or [],
            "data": documents or [],
            "took_ms": took_ms,
        }
    except Exception as e:
        logger.error(f"Error in search_opensearch task: {e}")
        return {
            "status": "error",
            "message": f"Search failed: {str(e)}",
            "headers": [],
            "data": [],
        }


@app.task(name='tasks.snapshot_current_stats')
def snapshot_current_stats(directory_path: Optional[str] = None) -> dict:
    """Compute and persist today's stats snapshot for netspeed.csv only.

    phonesWithKEM counts unique phones with >=1 KEM; totalKEMs counts modules.
    """
    try:
        from models.file import FileModel as _FM
        # Allow override via ENV NETSPEED_DATA_DIR
        env_dir = os.environ.get("NETSPEED_DATA_DIR")
        base_dir = directory_path or env_dir or getattr(settings, "CSV_FILES_DIR", None)
        if base_dir:
            data_dir = Path(base_dir)
        else:
            data_dir = get_data_root()

        extras: List[Path | str] = [data_dir]
        for extra in (
            getattr(settings, "NETSPEED_CURRENT_DIR", None),
            getattr(settings, "NETSPEED_HISTORY_DIR", None),
            get_data_root(),
        ):
            if extra:
                extras.append(extra)
        file_path: Optional[Path] = None
        try:
            candidate = resolve_current_file(extras)
            if candidate and candidate.exists():
                file_path = candidate
        except Exception:
            file_path = None

        if file_path is None:
            fallback_candidates: List[Path] = []
            # Prefer configured directories
            current_dir = getattr(settings, "NETSPEED_CURRENT_DIR", None)
            if current_dir:
                current_path = Path(current_dir)
                if current_path.is_file():
                    fallback_candidates.append(current_path)
                else:
                    fallback_candidates.append(current_path / "netspeed.csv")
            fallback_candidates.append(data_dir / "netspeed.csv")
            fallback_candidates.append(get_data_root() / "netspeed.csv")
            fallback_candidates.append(Path("/usr/scripts/netspeed/netspeed.csv"))
            for cand in fallback_candidates:
                if cand.exists():
                    file_path = cand
                    break

        if file_path is None:
            return {"status": "warning", "message": f"Current file not found near {directory_path}"}

        fm = _FM.from_path(str(file_path))
        date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
        _, rows_original = read_csv_file_normalized(str(file_path))
        rows = deduplicate_phone_rows(rows_original)
        if len(rows) != len(rows_original):
            logger.debug(
                "snapshot_current_stats deduplicated %s rows: %d -> %d",
                fm.name,
                len(rows_original),
                len(rows),
            )

        total_phones = len(rows)
        switches = set(); locations = set(); city_codes = set()
        phones_with_kem_unique = 0; total_kem_modules = 0
        model_counts: Dict[str, int] = {}
        justiz_model_counts: Dict[str, int] = {}; jva_model_counts: Dict[str, int] = {}
        justiz_switches = set(); justiz_locations = set(); justiz_city_codes = set(); justiz_phones_with_kem_unique = 0; justiz_total_kem_modules = 0
        jva_switches = set(); jva_locations = set(); jva_city_codes = set(); jva_phones_with_kem_unique = 0; jva_total_kem_modules = 0

        unknown_models_debug = []
        for r in rows:
            sh = (r.get("Switch Hostname") or "").strip(); is_jva = False
            if sh:
                switches.add(sh)
                try:
                    from api.stats import is_jva_switch
                    is_jva = is_jva_switch(sh)
                except Exception:
                    is_jva = False
                if is_jva:
                    jva_switches.add(sh)
                else:
                    justiz_switches.add(sh)
                try:
                    from api.stats import extract_location
                    loc = extract_location(sh)
                    if loc:
                        locations.add(loc); city_codes.add(loc[:3])
                        if is_jva:
                            jva_locations.add(loc); jva_city_codes.add(loc[:3])
                        else:
                            justiz_locations.add(loc); justiz_city_codes.add(loc[:3])
                except Exception:
                    pass

            kem_count = 0
            if (r.get("KEM") or "").strip(): kem_count += 1
            if (r.get("KEM 2") or "").strip(): kem_count += 1
            if kem_count == 0:
                ln = (r.get("Line Number") or "").strip()
                if "KEM" in ln: kem_count = ln.count("KEM") or 1
            if kem_count > 0:
                phones_with_kem_unique += 1; total_kem_modules += kem_count
                if is_jva:
                    jva_phones_with_kem_unique += 1; jva_total_kem_modules += kem_count
                else:
                    justiz_phones_with_kem_unique += 1; justiz_total_kem_modules += kem_count

            model_orig = (r.get("Model Name") or "").strip() or "Unknown"
            model = model_orig
            if model != "Unknown":
                try:
                    from api.stats import is_mac_like
                    if len(model) < 4 or is_mac_like(model):
                        unknown_models_debug.append(model_orig)
                        model = "Unknown"
                except Exception:
                    pass
            model_counts[model] = model_counts.get(model, 0) + 1
            if is_jva:
                jva_model_counts[model] = jva_model_counts.get(model, 0) + 1
            else:
                justiz_model_counts[model] = justiz_model_counts.get(model, 0) + 1

        if unknown_models_debug:
            logger.warning(f"DEBUG: Folgende Modelle wurden als 'Unknown' ersetzt: {unknown_models_debug}")

        phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]; phones_by_model.sort(key=lambda x: (-x["count"], x["model"]))
        phones_by_model_justiz = [{"model": m, "count": c} for m, c in justiz_model_counts.items()]; phones_by_model_justiz.sort(key=lambda x: (-x["count"], x["model"]))
        phones_by_model_jva = [{"model": m, "count": c} for m, c in jva_model_counts.items()]; phones_by_model_jva.sort(key=lambda x: (-x["count"], x["model"]))
        total_justiz_phones = sum(justiz_model_counts.values()); total_jva_phones = sum(jva_model_counts.values())

        metrics = {
            "totalPhones": total_phones,
            "totalSwitches": len(switches),
            "totalLocations": len(locations),
            "totalCities": len(city_codes),
            "phonesWithKEM": phones_with_kem_unique,
            "totalKEMs": total_kem_modules,
            "totalJustizPhones": total_justiz_phones,
            "totalJVAPhones": total_jva_phones,
            "justizSwitches": len(justiz_switches),
            "justizLocations": len(justiz_locations),
            "justizCities": len(justiz_city_codes),
            "justizPhonesWithKEM": justiz_phones_with_kem_unique,
            "totalJustizKEMs": justiz_total_kem_modules,
            "jvaSwitches": len(jva_switches),
            "jvaLocations": len(jva_locations),
            "jvaCities": len(jva_city_codes),
            "jvaPhonesWithKEM": jva_phones_with_kem_unique,
            "totalJVAKEMs": jva_total_kem_modules,
            "phonesByModel": phones_by_model,
            "phonesByModelJustiz": phones_by_model_justiz,
            "phonesByModelJVA": phones_by_model_jva,
            "cityCodes": sorted(list(city_codes)),
        }
        # Preserve detail arrays if an existing snapshot for the same day already has them
        try:
            existing = opensearch_config.get_stats_snapshot(file=fm.name, date=date_str)
            if isinstance(existing, dict):
                for key in ("phonesByModelJustizDetails", "phonesByModelJVADetails"):
                    if key in existing and isinstance(existing[key], list) and existing[key]:
                        metrics[key] = existing[key]
        except Exception as _e:
            logger.debug(f"Preserve details failed: {_e}")
        ok = opensearch_config.index_stats_snapshot(file=fm.name, date=date_str, metrics=metrics)
        return {"status": "success" if ok else "error", "message": "Snapshot indexed" if ok else "Failed to index snapshot", "file": fm.name, "date": date_str}
    except Exception as e:
        logger.error(f"snapshot_current_stats failed: {e}")
        return {"status": "error", "message": str(e)}


@app.task(name='tasks.snapshot_current_with_details')
def snapshot_current_with_details(file_path: Optional[str] = None, force_date: Optional[str] = None) -> dict:
    """Compute and persist stats snapshot with detailed per-location documents.

    - Writes stats_netspeed (global) incl. Justiz/JVA model breakdown + details arrays
    - Writes stats_netspeed_loc with per-location model lists, VLAN usage, switch VLAN mapping, KEM phones
    - force_date allows overriding the file date (UI expects today's date for details)
    """
    try:
        env_dir = os.environ.get("NETSPEED_DATA_DIR")
        extras: List[Path | str] = []
        if env_dir:
            extras.append(Path(env_dir))
        for extra in (
            getattr(settings, "CSV_FILES_DIR", None),
            getattr(settings, "NETSPEED_CURRENT_DIR", None),
            getattr(settings, "NETSPEED_HISTORY_DIR", None),
            get_data_root(),
        ):
            if extra:
                extras.append(extra)

        p: Optional[Path] = Path(file_path) if file_path else None
        if p and not p.exists():
            p = None

        if p is None:
            try:
                candidate = resolve_current_file(extras)
                if candidate and candidate.exists():
                    p = candidate
            except Exception:
                p = None

        if p is None:
            fallback_candidates: List[Path] = []
            current_dir = getattr(settings, "NETSPEED_CURRENT_DIR", None)
            if current_dir:
                current_path = Path(current_dir)
                if current_path.is_file():
                    fallback_candidates.append(current_path)
                else:
                    fallback_candidates.append(current_path / "netspeed.csv")
            fallback_candidates.append(get_data_root() / "netspeed.csv")
            fallback_candidates.append(Path("/usr/scripts/netspeed/netspeed.csv"))
            for cand in fallback_candidates:
                if cand.exists():
                    p = cand
                    break

        if p is None:
            return {"status": "warning", "message": "File not found for snapshot"}

        file_path = str(p)
        from models.file import FileModel as _FM
        fm = _FM.from_path(str(p))
        date_str = force_date or (fm.date.strftime('%Y-%m-%d') if fm.date else None)
        _, rows_original = read_csv_file_normalized(str(p))
        rows = deduplicate_phone_rows(rows_original)
        if len(rows) != len(rows_original):
            logger.debug(
                "snapshot_current_with_details deduplicated %s rows: %d -> %d",
                fm.name,
                len(rows_original),
                len(rows),
            )

        # Aggregators
        switches: set = set(); locations: set = set(); city_codes: set = set()
        model_counts: Dict[str, int] = {}; justiz_model_counts: Dict[str, int] = {}; jva_model_counts: Dict[str, int] = {}
        phones_with_kem_unique = 0; total_kem_modules = 0
        justiz_phones_with_kem_unique = 0; jva_phones_with_kem_unique = 0
        justiz_total_kem_modules = 0; jva_total_kem_modules = 0
        justiz_switches = set(); jva_switches = set(); justiz_locations=set(); jva_locations=set(); justiz_city_codes=set(); jva_city_codes=set()

        per_loc_counts: Dict[str, Dict[str, int]] = {}
        location_details: Dict[str, Dict[str, Any]] = {}
        justiz_details_by_location: Dict[str, Dict[str, int]] = {}
        jva_details_by_location: Dict[str, Dict[str, int]] = {}

        for r in rows:
            sh = (r.get("Switch Hostname") or "").strip(); loc=None; is_jva=False
            if sh:
                switches.add(sh)
                try:
                    from api.stats import is_jva_switch, extract_location, is_mac_like
                    is_jva = is_jva_switch(sh)
                    loc = extract_location(sh)
                except Exception:
                    pass
                (jva_switches if is_jva else justiz_switches).add(sh)
                if loc:
                    locations.add(loc); city_codes.add(loc[:3])
                    (jva_locations if is_jva else justiz_locations).add(loc)
                    (jva_city_codes if is_jva else justiz_city_codes).add(loc[:3])
                    plc = per_loc_counts.setdefault(loc,{"totalPhones":0,"phonesWithKEM":0,"totalSwitches":0})
                    plc["totalPhones"] += 1
                    det = location_details.setdefault(loc,{"vlans":{},"switches":set(),"switch_vlans":{},"kem_phones":[]})
                    if sh not in det["switches"]:
                        det["switches"].add(sh); plc["totalSwitches"] += 1

            # KEM counting (modules + unique phones)
            kem_modules = 0
            for fld in ("KEM","KEM 2"):
                if (r.get(fld) or "").strip(): kem_modules += 1
            if kem_modules == 0:  # fallback in line number
                ln = (r.get("Line Number") or "").strip()
                if "KEM" in ln:
                    kem_modules = ln.count("KEM") or 1
            if kem_modules>0:
                phones_with_kem_unique +=1; total_kem_modules += kem_modules
                if is_jva:
                    jva_phones_with_kem_unique +=1; jva_total_kem_modules += kem_modules
                else:
                    justiz_phones_with_kem_unique +=1; justiz_total_kem_modules += kem_modules
                if loc:
                    det = location_details.setdefault(loc,{"vlans":{},"switches":set(),"switch_vlans":{},"kem_phones":[]})
                    item = {"model": (r.get("Model Name") or "").strip() or "Unknown","mac":(r.get("MAC Address") or "").strip(),"serial":(r.get("Serial Number") or "").strip(),"switch":sh,"kemModules":kem_modules}
                    ip=(r.get("IP Address") or "").strip()
                    if ip: item["ip"]=ip
                    det["kem_phones"].append(item)
                    per_loc_counts[loc]["phonesWithKEM"] +=1

            # Model
            model = (r.get("Model Name") or "").strip() or "Unknown"
            if model != "Unknown":
                try:
                    from api.stats import is_mac_like
                    if len(model)<4 or is_mac_like(model):
                        model="Unknown"
                except Exception: pass
            model_counts[model] = model_counts.get(model,0)+1
            if sh and loc:
                if is_jva:
                    jva_model_counts[model] = jva_model_counts.get(model,0)+1
                    jva_details_by_location.setdefault(loc,{})[model] = jva_details_by_location.setdefault(loc,{}).get(model,0)+1
                else:
                    justiz_model_counts[model] = justiz_model_counts.get(model,0)+1
                    justiz_details_by_location.setdefault(loc,{})[model] = justiz_details_by_location.setdefault(loc,{}).get(model,0)+1

            # VLAN
            vlan = (r.get("Voice VLAN") or "").strip()
            if vlan and loc:
                det = location_details.setdefault(loc,{"vlans":{},"switches":set(),"switch_vlans":{},"kem_phones":[]})
                det["vlans"][vlan] = det["vlans"].get(vlan,0)+1
                if sh not in det["switch_vlans"]:
                    det["switch_vlans"][sh] = {}
                det["switch_vlans"][sh][vlan] = det["switch_vlans"][sh].get(vlan,0)+1

        # Format globals
        phones_by_model = sorted(([{"model":m,"count":c} for m,c in model_counts.items()]), key=lambda x: (-int(x["count"]), x["model"]))
        phones_by_model_justiz = sorted(([{"model":m,"count":c} for m,c in justiz_model_counts.items()]), key=lambda x: (-int(x["count"]), x["model"]))
        phones_by_model_jva = sorted(([{"model":m,"count":c} for m,c in jva_model_counts.items()]), key=lambda x: (-int(x["count"]), x["model"]))
        total_justiz_phones = sum(justiz_model_counts.values()); total_jva_phones = sum(jva_model_counts.values())

        def _city_name(cd: str) -> str:
            try:
                from api.stats import resolve_city_name
                return resolve_city_name(cd)
            except Exception: return cd

        phones_by_model_justiz_details = []
        for loc, models in justiz_details_by_location.items():
            ml = sorted(([{"model":m,"count":c} for m,c in models.items()]), key=lambda x: (-int(x["count"]), x["model"]))
            code3 = loc[:3] if len(loc)>=3 else ""; cname=_city_name(code3) if code3 else ""; disp=f"{loc} - {cname}" if cname and cname!=code3 else loc
            phones_by_model_justiz_details.append({"location":loc,"locationDisplay":disp,"totalPhones":sum(models.values()),"models":ml})
        phones_by_model_justiz_details.sort(key=lambda x:(-x["totalPhones"], x["location"]))

        phones_by_model_jva_details = []
        for loc, models in jva_details_by_location.items():
            ml = sorted(([{"model":m,"count":c} for m,c in models.items()]), key=lambda x: (-int(x["count"]), x["model"]))
            code3 = loc[:3] if len(loc)>=3 else ""; cname=_city_name(code3) if code3 else ""; disp=f"{loc} - {cname}" if cname and cname!=code3 else loc
            phones_by_model_jva_details.append({"location":loc,"locationDisplay":disp,"totalPhones":sum(models.values()),"models":ml})
        phones_by_model_jva_details.sort(key=lambda x:(-x["totalPhones"], x["location"]))

        metrics = {
            "totalPhones": len(rows),
            "totalSwitches": len(switches),
            "totalLocations": len(locations),
            "totalCities": len(city_codes),
            "phonesWithKEM": phones_with_kem_unique,
            "totalKEMs": total_kem_modules,
            "totalJustizPhones": total_justiz_phones,
            "totalJVAPhones": total_jva_phones,
            "justizSwitches": len(justiz_switches),
            "justizLocations": len(justiz_locations),
            "justizCities": len(justiz_city_codes),
            "justizPhonesWithKEM": justiz_phones_with_kem_unique,
            "totalJustizKEMs": justiz_total_kem_modules,
            "jvaSwitches": len(jva_switches),
            "jvaLocations": len(jva_locations),
            "jvaCities": len(jva_city_codes),
            "jvaPhonesWithKEM": jva_phones_with_kem_unique,
            "totalJVAKEMs": jva_total_kem_modules,
            "phonesByModel": phones_by_model,
            "phonesByModelJustiz": phones_by_model_justiz,
            "phonesByModelJVA": phones_by_model_jva,
            "phonesByModelJustizDetails": phones_by_model_justiz_details,
            "phonesByModelJVADetails": phones_by_model_jva_details,
            "cityCodes": sorted(list(city_codes)),
        }

        ok = opensearch_config.index_stats_snapshot(file=fm.name, date=date_str, metrics=metrics)

        def vlan_key(item: Dict[str, Any]):
            v = item["vlan"]
            try: return (0,int(v))
            except: return (1,v)

        loc_docs = []
        for loc, agg in per_loc_counts.items():
            det = location_details.get(loc,{"vlans":{} ,"switches":set(),"switch_vlans":{},"kem_phones":[]})
            vlan_usage = sorted(([{"vlan":v,"count":c} for v,c in det["vlans"].items()]), key=vlan_key)
            switches_fmt = []
            for sw in sorted(det["switches"]):
                vl = det.get("switch_vlans",{}).get(sw,{})
                sw_vlans_sorted = sorted(([{"vlan":v,"count":c} for v,c in vl.items()]), key=vlan_key)
                switches_fmt.append({"hostname": sw, "vlans": sw_vlans_sorted})
            jm_raw = justiz_details_by_location.get(loc, {})
            jvm_raw = jva_details_by_location.get(loc, {})
            all_raw: Dict[str,int] = {}
            for source in (jm_raw, jvm_raw):
                for m,c in source.items():
                    all_raw[m] = all_raw.get(m,0)+c
            tolist = lambda d: sorted(([{"model":m,"count":c} for m,c in d.items()]), key=lambda x:(-int(x["count"]), x["model"]))
            loc_docs.append({
                "key": loc,
                "mode": "code",
                "totalPhones": agg["totalPhones"],
                "totalSwitches": agg["totalSwitches"],
                "phonesWithKEM": agg.get("phonesWithKEM",0),
                "phonesByModel": tolist(all_raw),
                "phonesByModelJustiz": tolist(jm_raw),
                "phonesByModelJVA": tolist(jvm_raw),
                "vlanUsage": vlan_usage,
                "switches": switches_fmt,
                "kemPhones": det.get("kem_phones", []),
            })
        if loc_docs:
            logger.info(f"Indexing {len(loc_docs)} location documents to stats_netspeed_loc for file {fm.name}, date {date_str}")
            opensearch_config.index_stats_location_snapshots(file=fm.name, date=date_str, loc_docs=loc_docs)
            logger.info(f"Successfully indexed location statistics for {len(loc_docs)} locations")
        else:
            logger.warning("No location documents to index - this will cause missing View by Location data!")

        return {"status": "success" if ok else "error", "message": "Snapshot with details indexed" if ok else "Failed to index snapshot with details", "file": fm.name, "date": date_str, "loc_docs": len(loc_docs)}
    except Exception as e:
        logger.error(f"snapshot_current_with_details failed: {e}")
        return {"status": "error", "message": str(e)}


@app.task(
    name='tasks.index_csv',
    bind=True,
    max_retries=getattr(settings, "OPENSEARCH_RETRY_MAX_ATTEMPTS", 5),
)
def index_csv(self, file_path: str) -> dict:
    """
    Task to index a CSV file in OpenSearch.

    Args:
        file_path: Path to the CSV file to index

    Returns:
        dict: A dictionary containing the indexing result
    """
    logger.info(f"Indexing CSV file at {file_path}")

    try:
        should_wait = bool(getattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", True))
        if should_wait:
            opensearch_config.wait_for_availability(
                timeout=getattr(settings, "OPENSEARCH_STARTUP_TIMEOUT_SECONDS", 45),
                interval=getattr(settings, "OPENSEARCH_STARTUP_POLL_SECONDS", 3.0),
                reason=f"index_csv:{Path(file_path).name}",
            )
        else:
            if not opensearch_config.quick_ping():
                logger.warning(
                    "OpenSearch unavailable and wait disabled; skipping index for %s",
                    file_path,
                )
                return {
                    "status": "skipped",
                    "message": "Skipped indexing because OpenSearch is unavailable (wait disabled)",
                    "file_path": file_path,
                    "count": 0,
                }

        success, count = opensearch_config.index_csv_file(file_path)

        # NEU: Stats-Snapshot nach jedem erfolgreichen Index aktualisieren
        try:
            from models.file import FileModel as _FM
            fm = _FM.from_path(file_path)
            date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
            _, _rows = read_csv_file_normalized(file_path)
            # ...existing code für Statistiken, Modellzählung, Details...
            # (Kopiere die Logik aus snapshot_current_stats und snapshot_current_with_details falls nötig)
            # ...existing code...
            # Kurzfassung: Rufe snapshot_current_stats und snapshot_current_with_details direkt auf
            # (Dadurch werden alle Statistiken und Details aktualisiert)
            try:
                snapshot_current_stats(directory_path=str(Path(file_path).parent))
            except Exception as e:
                logger.warning(f"Fehler beim Aktualisieren des globalen Stats-Snapshots: {e}")
            try:
                snapshot_current_with_details(file_path=file_path)
            except Exception as e:
                logger.warning(f"Fehler beim Aktualisieren des Detail-Snapshots: {e}")
        except Exception as e:
            logger.warning(f"Fehler beim Stats-Snapshot nach Index: {e}")

        if success:
            return {
                "status": "success",
                "message": f"Successfully indexed {count} documents from {file_path}",
                "file_path": file_path,
                "count": count
            }
        elif not should_wait:
            logger.warning("Indexing reported failure; treating as skipped because waits are disabled")
            return {
                "status": "skipped",
                "message": f"Skipped indexing {file_path} because OpenSearch is unavailable",
                "file_path": file_path,
                "count": 0,
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to index {file_path}",
                "file_path": file_path,
                "count": 0
            }
    except OpenSearchUnavailableError as exc:
        should_wait = bool(getattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", True))
        if not should_wait:
            logger.warning(
                "OpenSearch unavailable during wait (disabled); skipping index for %s: %s",
                file_path,
                exc,
            )
            return {
                "status": "skipped",
                "message": f"Skipped indexing {file_path}: OpenSearch unavailable",
                "file_path": file_path,
                "count": 0,
            }

        attempt = getattr(self.request, "retries", 0)
        max_attempts = self.max_retries if getattr(self, "max_retries", None) is not None else getattr(settings, "OPENSEARCH_RETRY_MAX_ATTEMPTS", 5)
        if max_attempts is not None and attempt >= max_attempts:
            logger.error(f"OpenSearch unavailable and retry limit reached for {file_path}: {exc}")
            return {
                "status": "error",
                "message": f"OpenSearch unavailable for {file_path}: {exc}",
                "file_path": file_path,
                "count": 0,
            }

        delay = _calculate_retry_delay(attempt)
        max_attempts_label = max_attempts if max_attempts is not None else "∞"
        logger.warning(
            f"OpenSearch unavailable while indexing {file_path} (attempt {attempt + 1}/{max_attempts_label}). Retrying in {delay}s"
        )
        raise self.retry(exc=exc, countdown=delay)
    except OpenSearchConnectionError as exc:
        should_wait = bool(getattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", True))
        if not should_wait:
            logger.warning(
                "OpenSearch connection error with wait disabled; skipping index for %s: %s",
                file_path,
                exc,
            )
            return {
                "status": "skipped",
                "message": f"Skipped indexing {file_path}: OpenSearch unavailable",
                "file_path": file_path,
                "count": 0,
            }

        attempt = getattr(self.request, "retries", 0)
        max_attempts = self.max_retries if getattr(self, "max_retries", None) is not None else getattr(settings, "OPENSEARCH_RETRY_MAX_ATTEMPTS", 5)
        if max_attempts is not None and attempt >= max_attempts:
            logger.error(f"OpenSearch connection error and retry limit reached for {file_path}: {exc}")
            return {
                "status": "error",
                "message": f"OpenSearch connection error for {file_path}: {exc}",
                "file_path": file_path,
                "count": 0,
            }

        delay = _calculate_retry_delay(attempt)
        max_attempts_label = max_attempts if max_attempts is not None else "∞"
        logger.warning(
            f"OpenSearch connection refused while indexing {file_path} (attempt {attempt + 1}/{max_attempts_label}). Retrying in {delay}s"
        )
        raise self.retry(exc=exc, countdown=delay)
    except Exception as e:
        logger.error(f"Error indexing CSV file {file_path}: {e}")
        return {
            "status": "error",
            "message": f"Error indexing file: {str(e)}",
            "file_path": file_path,
            "count": 0
        }


@app.task(name='tasks.backfill_location_snapshots')
def backfill_location_snapshots(directory_path: str | None = None) -> dict:
    """Backfill per-location snapshots (stats_netspeed_loc) for all netspeed files.

    Useful if stats_netspeed_loc is empty or partially populated.
    """
    try:
        should_wait = bool(getattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", True))
        if should_wait:
            opensearch_config.wait_for_availability(
                timeout=getattr(settings, "OPENSEARCH_STARTUP_TIMEOUT_SECONDS", 45),
                interval=getattr(settings, "OPENSEARCH_STARTUP_POLL_SECONDS", 3.0),
                reason="backfill_location_snapshots",
            )
        elif not opensearch_config.quick_ping():
            logger.warning("OpenSearch unavailable and wait disabled; skipping backfill_location_snapshots")
            return {"status": "skipped", "message": "Skipped location backfill: OpenSearch unavailable"}

        extras = [directory_path] if directory_path else None
        ordered_files = netspeed_files_ordered(extras, include_backups=False)
        files: List[Path] = []
        for p in ordered_files:
            name = p.name
            if name == "netspeed.csv" or (name.startswith("netspeed.csv.") and name.replace("netspeed.csv.", "").isdigit()):
                files.append(p)
        if not files:
            base_dir = Path(directory_path) if directory_path else get_data_root()
            return {"status": "warning", "message": f"No netspeed files found under {base_dir}", "files": 0, "loc_docs": 0}
        processed = 0
        total_loc_docs = 0
        for f in files:
            try:
                from models.file import FileModel as _FM
                fm = _FM.from_path(str(f))
                date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
                _, rows_original = read_csv_file_normalized(str(f))
                rows = deduplicate_phone_rows(rows_original)
                if len(rows) != len(rows_original):
                    logger.debug(
                        "backfill_location_snapshots deduplicated %s rows: %d -> %d",
                        fm.name,
                        len(rows_original),
                        len(rows),
                    )

                # Calculate detailed model stats like index_csv does
                justiz_details_by_location: Dict[str, Dict[str, int]] = {}
                jva_details_by_location: Dict[str, Dict[str, int]] = {}

                # Process each row for detailed model calculations
                for r in rows:
                    sh = (r.get("Switch Hostname") or "").strip()
                    model = (r.get("Model Name") or "Unknown").strip()
                    if not sh:
                        continue

                    try:
                        from api.stats import extract_location as _extract_location
                        location = _extract_location(sh)
                    except Exception:
                        location = None
                    if not location:
                        continue

                    # Determine if this is JVA or Justiz
                    try:
                        from api.stats import is_jva_switch
                        is_jva = is_jva_switch(sh)
                    except Exception:
                        is_jva = False

                    if is_jva:
                        if location not in jva_details_by_location:
                            jva_details_by_location[location] = {}
                        jva_details_by_location[location][model] = jva_details_by_location[location].get(model, 0) + 1
                    else:
                        if location not in justiz_details_by_location:
                            justiz_details_by_location[location] = {}
                        justiz_details_by_location[location][model] = justiz_details_by_location[location].get(model, 0) + 1

                # Now do the basic location counting (for totalPhones, totalSwitches, phonesWithKEM)
                per_loc_counts: Dict[str, Dict[str, int]] = {}
                per_loc_switches: Dict[str, set] = {}
                for r in rows:
                    sh = (r.get("Switch Hostname") or "").strip()
                    if not sh:
                        continue
                    try:
                        from api.stats import extract_location as _extract_location
                        loc = _extract_location(sh)
                    except Exception:
                        loc = None
                    if not loc:
                        continue
                    plc = per_loc_counts.setdefault(loc, {"totalPhones": 0, "phonesWithKEM": 0, "totalSwitches": 0})
                    plc["totalPhones"] += 1
                    sset = per_loc_switches.setdefault(loc, set())
                    if sh not in sset:
                        sset.add(sh)
                        plc["totalSwitches"] += 1
                    # Unique phones with >=1 KEM considering KEM/KEM 2 and Line Number fallback
                    kem1 = (r.get("KEM") or "").strip()
                    kem2 = (r.get("KEM 2") or "").strip()
                    has_kem = bool(kem1) or bool(kem2)
                    if not has_kem:
                        ln = (r.get("Line Number") or "").strip()
                        if "KEM" in ln:
                            has_kem = True
                    if has_kem:
                        plc["phonesWithKEM"] += 1

                # Collect additional details for each location (VLANs, switches, KEM phones)
                location_details = {}
                for r in rows:
                    sh = (r.get("Switch Hostname") or "").strip()
                    if not sh:
                        continue

                    # Extract location code
                    try:
                        from api.stats import extract_location as _extract_location
                        location = _extract_location(sh)
                    except Exception:
                        location = None

                    if not location:
                        continue

                    if location not in location_details:
                        location_details[location] = {
                            "vlans": {},
                            "switches": set(),
                            "kem_phones": []
                        }

                    # Collect VLAN usage
                    vlan = (r.get("Voice VLAN") or "").strip()
                    if vlan:
                        location_details[location]["vlans"][vlan] = location_details[location]["vlans"].get(vlan, 0) + 1

                    # Collect switches
                    location_details[location]["switches"].add(sh)

                    # Collect KEM phones (>=1 KEM via KEM/KEM 2 or Line Number). Include even without IP. Track kemModules
                    kem1 = (r.get("KEM") or "").strip()
                    kem2 = (r.get("KEM 2") or "").strip()
                    kem_modules = 0
                    if kem1:
                        kem_modules += 1
                    if kem2:
                        kem_modules += 1
                    if kem_modules == 0:
                        ln = (r.get("Line Number") or "").strip()
                        if "KEM" in ln:
                            kem_modules = ln.count("KEM") or 1
                    if kem_modules > 0:
                        ip = (r.get("IP Address") or "").strip()
                        model = (r.get("Model Name") or "").strip() or "Unknown"
                        mac = (r.get("MAC Address") or "").strip()
                        serial = (r.get("Serial Number") or "").strip()
                        item = {
                            "model": model,
                            "mac": mac,
                            "serial": serial,
                            "switch": sh,
                            "kemModules": int(kem_modules)
                        }
                        if ip:
                            item["ip"] = ip
                        location_details[location]["kem_phones"].append(item)

                # Build loc_docs with model details from calculated data
                loc_docs = []
                for k, agg in per_loc_counts.items():
                    # Get model breakdowns for this location
                    loc_justiz_models = []
                    loc_jva_models = []
                    loc_all_models = {}

                    # Extract from justiz details
                    if k in justiz_details_by_location:
                        for model, count in justiz_details_by_location[k].items():
                            loc_justiz_models.append({"model": model, "count": count})
                            loc_all_models[model] = loc_all_models.get(model, 0) + count

                    # Extract from JVA details
                    if k in jva_details_by_location:
                        for model, count in jva_details_by_location[k].items():
                            loc_jva_models.append({"model": model, "count": count})
                            loc_all_models[model] = loc_all_models.get(model, 0) + count

                    # Create combined model list
                    loc_all_models_list = [{"model": m, "count": c} for m, c in loc_all_models.items()]
                    loc_all_models_list.sort(key=lambda x: (-x["count"], x["model"]))
                    loc_justiz_models.sort(key=lambda x: (-x["count"], x["model"]))
                    loc_jva_models.sort(key=lambda x: (-x["count"], x["model"]))

                    # Get additional details for this location
                    details = location_details.get(k, {"vlans": {}, "switches": set(), "kem_phones": []})

                    # Format VLAN usage and derive summary stats
                    vlans_dict = details.get("vlans", {}) or {}
                    raw_vlan_usage = [{"vlan": v, "count": c} for v, c in vlans_dict.items()]

                    # Sort VLANs numerically for full usage list
                    def vlan_key(item):
                        v = item["vlan"]
                        try:
                            return (0, int(v))
                        except:
                            return (1, v)

                    vlan_usage = sorted(raw_vlan_usage, key=vlan_key)

                    # Determine top three VLANs by count (desc) with numeric tie-breaker
                    top_vlans = sorted(raw_vlan_usage, key=lambda item: (-item["count"], vlan_key(item)))[:3]
                    unique_vlan_count = len(vlans_dict)

                    # Format switches
                    switches = [{"hostname": sw} for sw in sorted(details["switches"])]

                    loc_docs.append({
                        "key": k,
                        "mode": "code",
                        "totalPhones": agg["totalPhones"],
                        "totalSwitches": agg["totalSwitches"],
                        "phonesWithKEM": agg["phonesWithKEM"],
                        "phonesByModel": loc_all_models_list,
                        "phonesByModelJustiz": loc_justiz_models,
                        "phonesByModelJVA": loc_jva_models,
                        "vlanUsage": vlan_usage,
                        "topVLANs": top_vlans,
                        "uniqueVLANCount": int(unique_vlan_count),
                        "switches": switches,
                        "kemPhones": details["kem_phones"]
                    })
                if loc_docs:
                    opensearch_config.index_stats_location_snapshots(file=fm.name, date=date_str, loc_docs=loc_docs)
                    total_loc_docs += len(loc_docs)
                processed += 1
            except Exception as _e:
                logger.warning(f"Backfill failed for {f}: {_e}")
        return {"status": "success", "files": processed, "loc_docs": total_loc_docs}
    except Exception as e:
        logger.error(f"Backfill error: {e}")
        return {"status": "error", "message": str(e)}


@app.task(name='tasks.backfill_stats_snapshots')
def backfill_stats_snapshots(directory_path: str | None = None) -> dict:
    """Backfill global stats snapshots (stats_netspeed) for all netspeed files.

    Computes from CSV only; does not touch netspeed_* search indices.
    phonesWithKEM = unique phones with >=1 KEM; totalKEMs = number of modules.
    """
    try:
        should_wait = bool(getattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", True))
        if should_wait:
            opensearch_config.wait_for_availability(
                timeout=getattr(settings, "OPENSEARCH_STARTUP_TIMEOUT_SECONDS", 45),
                interval=getattr(settings, "OPENSEARCH_STARTUP_POLL_SECONDS", 3.0),
                reason="backfill_stats_snapshots",
            )
        elif not opensearch_config.quick_ping():
            logger.warning("OpenSearch unavailable and wait disabled; skipping backfill_stats_snapshots")
            return {"status": "skipped", "message": "Skipped stats backfill: OpenSearch unavailable"}

        extras = [directory_path] if directory_path else None
        ordered_files = netspeed_files_ordered(extras, include_backups=False)
        files: List[Path] = []
        for p in ordered_files:
            name = p.name
            if name == "netspeed.csv" or (name.startswith("netspeed.csv.") and name.replace("netspeed.csv.", "").isdigit()):
                files.append(p)
        if not files:
            base_dir = Path(directory_path) if directory_path else get_data_root()
            return {"status": "warning", "message": f"No netspeed files found under {base_dir}", "files": 0}
        processed = 0
        for f in files:
            try:
                from models.file import FileModel as _FM
                fm = _FM.from_path(str(f))
                date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
                _, rows_original = read_csv_file_normalized(str(f))
                rows = deduplicate_phone_rows(rows_original)
                if len(rows) != len(rows_original):
                    logger.debug(
                        "backfill_stats_snapshots deduplicated %s rows: %d -> %d",
                        fm.name,
                        len(rows_original),
                        len(rows),
                    )

                total_phones = len(rows)
                switches: set[str] = set()
                locations: set[str] = set()
                city_codes: set[str] = set()
                phones_with_kem_unique = 0
                total_kem_modules = 0
                model_counts: Dict[str, int] = {}

                for r in rows:
                    sh = (r.get("Switch Hostname") or "").strip()
                    if sh:
                        switches.add(sh)
                        try:
                            from api.stats import extract_location
                            loc = extract_location(sh)
                            if loc:
                                locations.add(loc)
                                city_codes.add(loc[:3])
                        except Exception:
                            pass

                    kem_count = 0
                    if (r.get("KEM") or "").strip():
                        kem_count += 1
                    if (r.get("KEM 2") or "").strip():
                        kem_count += 1
                    if kem_count == 0:
                        ln = (r.get("Line Number") or "").strip()
                        if "KEM" in ln:
                            kem_count = ln.count("KEM") or 1
                    if kem_count > 0:
                        phones_with_kem_unique += 1
                        total_kem_modules += kem_count

                    model = (r.get("Model Name") or "").strip() or "Unknown"
                    if model != "Unknown":
                        model_counts[model] = model_counts.get(model, 0) + 1

                phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]

                metrics = {
                    "totalPhones": total_phones,
                    "totalSwitches": len(switches),
                    "totalLocations": len(locations),
                    "totalCities": len(city_codes),
                    "phonesWithKEM": phones_with_kem_unique,
                    "totalKEMs": total_kem_modules,
                    "phonesByModel": phones_by_model,
                    "cityCodes": sorted(list(city_codes)),
                }
                opensearch_config.index_stats_snapshot(file=fm.name, date=date_str, metrics=metrics)
                processed += 1
            except Exception as _e:
                logger.warning(f"Backfill stats failed for {f}: {_e}")
        return {"status": "success", "files": processed}
    except Exception as e:
        logger.error(f"Backfill stats error: {e}")
        return {"status": "error", "message": str(e)}


@app.task(name='tasks.rebuild_stats_snapshots_deduplicated')
def rebuild_stats_snapshots_deduplicated(directory_path: str | None = None) -> dict:
    """Rebuild stats snapshots (global + per-location) using deduplicated CSV rows.

    This task ensures historical OpenSearch documents reflect the latest
    duplicate-protection semantics used for phones with KEM counts.
    """
    try:
        base_dir = directory_path or getattr(settings, "CSV_FILES_DIR", None)
        base_dir_text = str(base_dir) if base_dir else str(get_data_root())
        logger.info(f"Rebuilding stats snapshots with deduplicated rows (base={base_dir_text})")

        # Run global snapshot rebuild first
        stats_result = backfill_stats_snapshots(directory_path=base_dir_text)
        # Then rebuild per-location snapshots used by the timeline views
        loc_result = backfill_location_snapshots(directory_path=base_dir_text)

        try:
            client = opensearch_config.client
            client.indices.refresh(index=opensearch_config.stats_index)
            client.indices.refresh(index=opensearch_config.stats_loc_index)
        except Exception as refresh_err:
            logger.debug(f"Refresh after dedupe rebuild failed: {refresh_err}")

        try:
            from api.stats import invalidate_caches as _invalidate
            _invalidate("rebuild stats snapshots deduplicated")
        except Exception as cache_err:
            logger.debug(f"Cache invalidation after dedupe rebuild failed: {cache_err}")

        status_values = [
            stats_result.get("status") if isinstance(stats_result, dict) else None,
            loc_result.get("status") if isinstance(loc_result, dict) else None,
        ]
        overall_status = "success"
        if any(s == "error" for s in status_values):
            overall_status = "error"
        elif any(s not in ("success", "warning", "skipped") for s in status_values):
            overall_status = "warning"

        return {
            "status": overall_status,
            "message": "Rebuilt stats snapshots with deduplicated rows",
            "base_directory": base_dir_text,
            "details": {
                "global": stats_result,
                "locations": loc_result,
            },
        }
    except Exception as exc:
        logger.error(f"rebuild_stats_snapshots_deduplicated failed: {exc}")
        return {"status": "error", "message": str(exc)}


def _ensure_opensearch_available(directory_label: str) -> dict | None:
    """
    Check OpenSearch availability before indexing.

    Returns:
        dict | None: Error response dict if unavailable, None if available
    """
    should_wait = bool(getattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", True))
    if should_wait:
        try:
            opensearch_config.wait_for_availability(
                timeout=getattr(settings, "OPENSEARCH_STARTUP_TIMEOUT_SECONDS", 45),
                interval=getattr(settings, "OPENSEARCH_STARTUP_POLL_SECONDS", 3.0),
                reason="index_all_csv_files",
            )
        except OpenSearchUnavailableError as exc:
            logger.error(f"OpenSearch unavailable for index_all_csv_files: {exc}")
            return {
                "status": "error",
                "message": f"OpenSearch unavailable: {exc}",
                "directory": directory_label,
                "files_processed": 0,
                "total_documents": 0,
            }
    else:
        if not opensearch_config.quick_ping():
            logger.warning("OpenSearch unavailable and wait disabled; skipping full indexing run")
            return {
                "status": "skipped",
                "message": "Skipped index_all_csv_files because OpenSearch is unavailable (wait disabled)",
                "directory": directory_label,
                "files_processed": 0,
                "total_documents": 0,
            }
    return None


def _check_concurrent_indexing(task_request, directory_label: str, extras: List[str] | None) -> dict | None:
    """
    Check for concurrent indexing tasks and create pre-index snapshot.

    Returns:
        dict | None: Error response dict if concurrent task found, None if safe to proceed
    """
    try:
        pre_state = load_state()
        current_file_path = resolve_current_file(extras)
        if current_file_path is not None:
            try:
                logger.info("Executing snapshot_current_with_details for detected current netspeed.csv before bulk indexing (location stats fix)")
                from tasks.tasks import snapshot_current_with_details
                from datetime import datetime as _dt
                today_str = _dt.now().strftime('%Y-%m-%d')
                result = snapshot_current_with_details(file_path=str(current_file_path), force_date=today_str)
                logger.info(f"Pre-index snapshot_current_with_details result: {result}")
                try:
                    from api.stats import invalidate_caches as _invalidate
                    _invalidate("pre-index location stats creation")
                except Exception as cache_e:
                    logger.debug(f"Cache invalidation failed (pre-index): {cache_e}")
            except Exception as e:
                logger.warning(f"Pre-index snapshot_current_with_details failed: {e}")
        else:
            logger.info("No current netspeed.csv detected in candidates before indexing")
        active_task = pre_state.get("active_task", {})
        if active_task.get("status") == "running":
            existing_task_id = active_task.get("task_id")
            current_task_id = getattr(task_request, 'id', 'unknown')
            if existing_task_id and existing_task_id != current_task_id:
                logger.warning(f"Another indexing task {existing_task_id} is already running. Aborting task {current_task_id}")
                return {
                    "status": "aborted",
                    "message": f"Another indexing task {existing_task_id} is already running",
                    "directory": directory_label,
                    "files_processed": 0,
                    "total_documents": 0,
                }
    except Exception as e:
        logger.warning(f"Failed to check for concurrent tasks: {e}")
    return None


@app.task(bind=True, name='tasks.index_all_csv_files')
def index_all_csv_files(self, directory_path: str | None = None) -> dict:
    """Index all CSV files and persist snapshots with correct KEM semantics.

    - Index historical first, then current file
    - phonesWithKEM = unique phones; totalKEMs = modules
    - Also writes per-location snapshots with unique KEM phone counting
    """
    extras = [directory_path] if directory_path else None
    directory_label = directory_path or str(get_data_root())
    logger.info(f"Indexing all CSV files (base={directory_label})")

    # Check OpenSearch availability
    availability_error = _ensure_opensearch_available(directory_label)
    if availability_error:
        return availability_error

    # Protection against concurrent indexing tasks
    concurrent_error = _check_concurrent_indexing(self.request, directory_label, extras)
    if concurrent_error:
        return concurrent_error

    # Protection against concurrent indexing tasks
    try:
        pre_state = load_state()
        current_file_path = resolve_current_file(extras)
        if current_file_path is not None:
            try:
                logger.info("Executing snapshot_current_with_details for detected current netspeed.csv before bulk indexing (location stats fix)")
                from tasks.tasks import snapshot_current_with_details
                from datetime import datetime as _dt
                today_str = _dt.now().strftime('%Y-%m-%d')
                result = snapshot_current_with_details(file_path=str(current_file_path), force_date=today_str)
                logger.info(f"Pre-index snapshot_current_with_details result: {result}")
                try:
                    from api.stats import invalidate_caches as _invalidate
                    _invalidate("pre-index location stats creation")
                except Exception as cache_e:
                    logger.debug(f"Cache invalidation failed (pre-index): {cache_e}")
            except Exception as e:
                logger.warning(f"Pre-index snapshot_current_with_details failed: {e}")
        else:
            logger.info("No current netspeed.csv detected in candidates before indexing")
        active_task = pre_state.get("active_task", {})
        if active_task.get("status") == "running":
            existing_task_id = active_task.get("task_id")
            current_task_id = getattr(self.request, 'id', 'unknown')
            if existing_task_id and existing_task_id != current_task_id:
                logger.warning(f"Another indexing task {existing_task_id} is already running. Aborting task {current_task_id}")
                return {
                    "status": "aborted",
                    "message": f"Another indexing task {existing_task_id} is already running",
                    "directory": directory_label,
                    "files_processed": 0,
                    "total_documents": 0,
                }
    except Exception as e:
        logger.warning(f"Failed to check for concurrent tasks: {e}")

    historical_files, current_file_candidate, backup_files = collect_netspeed_files(extras, include_backups=True)
    ordered_files: List[Path] = []
    # CRITICAL: Index current file FIRST, then historical files
    # This ensures the most recent data is available immediately for searches
    if current_file_candidate:
        ordered_files.append(current_file_candidate)
    ordered_files.extend(historical_files)
    ordered_files.extend(backup_files)

    scanned_dirs = sorted({str(p.parent) for p in ordered_files})

    logger.info(
        "Discovered %d netspeed-related files (hist=%d, current=%d, backups=%d) across: %s",
        len(ordered_files), len(historical_files), 1 if current_file_candidate else 0, len(backup_files),
        ", ".join(scanned_dirs) if scanned_dirs else directory_label,
    )
    if not ordered_files:
        return {
            "status": "warning",
            "message": f"No CSV files found under {directory_label}",
            "directory": directory_label,
            "files_processed": 0,
            "total_documents": 0,
        }

    index_state: dict[str, Any] = {}
    try:
        results: List[Dict] = []
        total_documents = 0
        index_state = load_state()

        # Start progress
        task_id = getattr(self.request, 'id', os.environ.get('CELERY_TASK_ID', 'manual'))
        try:
            start_active(index_state, task_id, len(ordered_files))
            save_state(index_state)
            try:
                from config import settings as _settings
                update_active(index_state, broker=_settings.REDIS_URL, opensearch=_settings.OPENSEARCH_URL)
                save_state(index_state)
            except Exception:
                pass
            try:
                self.update_state(state='PROGRESS', meta={"task_id": task_id, "status": "running", "current_file": None, "index": 0, "total_files": len(ordered_files), "documents_indexed": 0})
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"Initial progress update failed: {e}")

        start_time = datetime.utcnow()

        for i, file_path in enumerate(ordered_files):
            logger.info(f"Processing file {i+1}/{len(ordered_files)}: {file_path}")
            try:
                update_active(index_state, current_file=file_path.name, index=i + 1)
                save_state(index_state)
                try:
                    self.update_state(state='PROGRESS', meta={"task_id": getattr(self.request, 'id', None), "status": "running", "current_file": file_path.name, "index": i + 1, "total_files": len(ordered_files), "documents_indexed": total_documents})
                except Exception:
                    pass
            except Exception:
                pass

            try:
                success, count = opensearch_config.index_csv_file(str(file_path))
                total_documents += count

                # Count lines (excluding header)
                line_count = count_unique_data_rows(file_path)

                try:
                    update_file_state(index_state, file_path, line_count, count)
                except Exception as e:
                    logger.warning(f"Failed to update index state for {file_path}: {e}")

                results.append({"file": str(file_path), "success": success, "count": count, "line_count": line_count})
                logger.info(f"Completed {file_path}: {count} documents indexed")

                # Stats snapshot for timeline (best-effort) using correct semantics
                try:
                    from models.file import FileModel as _FM
                    fm = _FM.from_path(str(file_path))
                    date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
                    _, _rows_original = read_csv_file_normalized(str(file_path))
                    _rows = deduplicate_phone_rows(_rows_original)
                    if len(_rows) != len(_rows_original):
                        logger.debug(
                            "index_all_csv_files deduplicated %s rows: %d -> %d",
                            fm.name,
                            len(_rows_original),
                            len(_rows),
                        )

                    total_phones = len(_rows)
                    switches = set(); locations = set(); city_codes = set()
                    phones_with_kem_unique = 0; total_kem_modules = 0
                    model_counts: Dict[str, int] = {}; justiz_model_counts: Dict[str, int] = {}; jva_model_counts: Dict[str, int] = {}
                    justiz_switches = set(); justiz_locations = set(); justiz_city_codes = set(); justiz_phones_with_kem_unique = 0; justiz_total_kem_modules = 0
                    jva_switches = set(); jva_locations = set(); jva_city_codes = set(); jva_phones_with_kem_unique = 0; jva_total_kem_modules = 0

                    try:
                        from api.stats import extract_location as _extract_location, is_jva_switch as _is_jva_switch, is_mac_like as _is_mac_like
                    except Exception:
                        _extract_location = lambda _value: None  # type: ignore
                        _is_jva_switch = lambda _value: False  # type: ignore
                        _is_mac_like = lambda _value: False  # type: ignore

                    for r in _rows:
                        sh = (r.get("Switch Hostname") or "").strip()
                        loc = None
                        is_jva = False
                        if sh:
                            switches.add(sh)
                            try:
                                loc = _extract_location(sh)
                            except Exception:
                                loc = None
                            if loc:
                                locations.add(loc)
                                city_codes.add(loc[:3])
                            try:
                                is_jva = _is_jva_switch(sh)
                            except Exception:
                                is_jva = False
                            if is_jva:
                                jva_switches.add(sh)
                                if loc:
                                    jva_locations.add(loc)
                                    jva_city_codes.add(loc[:3])
                            else:
                                justiz_switches.add(sh)
                                if loc:
                                    justiz_locations.add(loc)
                                    justiz_city_codes.add(loc[:3])

                        model = (r.get("Model Name") or "").strip() or "Unknown"
                        if model != "Unknown":
                            try:
                                if len(model) < 4 or _is_mac_like(model):
                                    model = "Unknown"
                            except Exception:
                                pass
                        model_counts[model] = model_counts.get(model, 0) + 1
                        if is_jva:
                            jva_model_counts[model] = jva_model_counts.get(model, 0) + 1
                        else:
                            justiz_model_counts[model] = justiz_model_counts.get(model, 0) + 1

                        kem_count = 0
                        if (r.get("KEM") or "").strip():
                            kem_count += 1
                        if (r.get("KEM 2") or "").strip():
                            kem_count += 1
                        if kem_count == 0:
                            ln = (r.get("Line Number") or "").strip()
                            if "KEM" in ln:
                                kem_count = ln.count("KEM") or 1
                        if kem_count > 0:
                            phones_with_kem_unique += 1
                            total_kem_modules += kem_count
                            if is_jva:
                                jva_phones_with_kem_unique += 1
                                jva_total_kem_modules += kem_count
                            else:
                                justiz_phones_with_kem_unique += 1
                                justiz_total_kem_modules += kem_count

                    phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]
                    phones_by_model.sort(key=lambda x: (-x["count"], x["model"]))
                    phones_by_model_justiz = [{"model": m, "count": c} for m, c in justiz_model_counts.items()]; phones_by_model_justiz.sort(key=lambda x: (-x["count"], x["model"]))
                    phones_by_model_jva = [{"model": m, "count": c} for m, c in jva_model_counts.items()]; phones_by_model_jva.sort(key=lambda x: (-x["count"], x["model"]))
                    total_justiz_phones = sum(justiz_model_counts.values()); total_jva_phones = sum(jva_model_counts.values())

                    metrics = {
                        "totalPhones": total_phones,
                        "totalSwitches": len(switches),
                        "totalLocations": len(locations),
                        "totalCities": len(city_codes),
                        "phonesWithKEM": phones_with_kem_unique,
                        "totalKEMs": total_kem_modules,
                        "totalJustizPhones": total_justiz_phones,
                        "totalJVAPhones": total_jva_phones,
                        "justizSwitches": len(justiz_switches),
                        "justizLocations": len(justiz_locations),
                        "justizCities": len(justiz_city_codes),
                        "justizPhonesWithKEM": justiz_phones_with_kem_unique,
                        "totalJustizKEMs": justiz_total_kem_modules,
                        "jvaSwitches": len(jva_switches),
                        "jvaLocations": len(jva_locations),
                        "jvaCities": len(jva_city_codes),
                        "jvaPhonesWithKEM": jva_phones_with_kem_unique,
                        "totalJVAKEMs": jva_total_kem_modules,
                        "phonesByModel": phones_by_model,
                        "phonesByModelJustiz": phones_by_model_justiz,
                        "phonesByModelJVA": phones_by_model_jva,
                        "cityCodes": sorted(list(city_codes)),
                    }
                    opensearch_config.index_stats_snapshot(file=fm.name, date=date_str, metrics=metrics)

                    # Basic per-location snapshots (unique KEM phones)
                    try:
                        per_loc_counts: Dict[str, Dict[str, int]] = {}
                        per_loc_switches: Dict[str, set] = {}
                        for r in _rows:
                            sh2 = (r.get("Switch Hostname") or "").strip()
                            if not sh2:
                                continue
                            try:
                                from api.stats import extract_location as _extract_location
                                loc2 = _extract_location(sh2)
                            except Exception:
                                loc2 = None
                            if not loc2:
                                continue
                            plc = per_loc_counts.setdefault(loc2, {"totalPhones": 0, "phonesWithKEM": 0, "totalSwitches": 0})
                            plc["totalPhones"] += 1
                            sset = per_loc_switches.setdefault(loc2, set())
                            if sh2 not in sset:
                                sset.add(sh2)
                                plc["totalSwitches"] += 1
                            kem1 = (r.get("KEM") or "").strip()
                            kem2 = (r.get("KEM 2") or "").strip()
                            has_kem = bool(kem1) or bool(kem2)
                            if not has_kem:
                                ln = (r.get("Line Number") or "").strip()
                                if "KEM" in ln:
                                    has_kem = True
                            if has_kem:
                                plc["phonesWithKEM"] += 1
                        loc_docs = [
                            {
                                "key": k,
                                "mode": "code",
                                "totalPhones": agg["totalPhones"],
                                "totalSwitches": agg["totalSwitches"],
                                "phonesWithKEM": agg["phonesWithKEM"],
                            }
                            for k, agg in per_loc_counts.items()
                        ]
                        if loc_docs:
                            opensearch_config.index_stats_location_snapshots(file=fm.name, date=date_str, loc_docs=loc_docs)
                    except Exception as _e:
                        logger.debug(f"Per-location snapshot indexing failed for {file_path}: {_e}")
                except Exception as _e:
                    logger.debug(f"Stats snapshot failed for {file_path}: {_e}")

                # Archive snapshot
                try:
                    if '_rows' not in locals():
                        _, _rows_fallback = read_csv_file_normalized(str(file_path))
                        _rows = deduplicate_phone_rows(_rows_fallback)
                    opensearch_config.index_archive_snapshot(file=file_path.name, date=date_str, rows=_rows)
                except Exception as _e:
                    logger.debug(f"Archive snapshot failed for {file_path}: {_e}")

                # Progress update
                try:
                    update_active(index_state, current_file=file_path.name, index=i + 1, documents_indexed=total_documents)
                    save_state(index_state)
                except Exception as e:
                    logger.debug(f"Progress update failed: {e}")
                try:
                    self.update_state(state='PROGRESS', meta={"task_id": task_id, "status": "running", "current_file": file_path.name, "index": i + 1, "total_files": len(ordered_files), "documents_indexed": total_documents})
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")
                results.append({"file": str(file_path), "success": False, "error": str(e), "count": 0})

        # Persist state
        last_success_ts = None
        try:
            update_totals(index_state, len(ordered_files), total_documents)
            last_success_ts = datetime.utcnow().isoformat() + 'Z'
            index_state['last_success'] = last_success_ts
            clear_active(index_state, 'completed')
            save_state(index_state)
        except Exception as e:
            logger.warning(f"Failed saving index state: {e}")

        # Post-index data repair & final snapshots for current file
        current_file_path = current_file_candidate
        if current_file_path is None or not current_file_path.exists():
            current_file_path = resolve_current_file(extras)

        if current_file_path and Path(current_file_path).exists():
            current_file_path = Path(current_file_path)
            from datetime import datetime as _dt
            today_str = _dt.now().strftime('%Y-%m-%d')
            try:
                logger.info("Starting post-indexing data repair for current file")
                repair_result = opensearch_config.repair_current_file_after_indexing(str(current_file_path))
                if repair_result.get("success"):
                    logger.info(f"Data repair completed successfully: {repair_result}")
                else:
                    logger.warning(f"Data repair failed: {repair_result}")
            except Exception as e:
                logger.error(f"Post-indexing data repair failed: {e}")

            # Comprehensive snapshot with details
            try:
                from tasks.tasks import snapshot_current_with_details as _snap_details
                logger.info("Running final detailed snapshot (snapshot_current_with_details)")
                final_details_res = _snap_details(file_path=str(current_file_path), force_date=today_str)
                logger.info(f"Final detailed snapshot result: {final_details_res}")
            except Exception as e:
                logger.error(f"Final detailed snapshot failed: {e}")

            # Minimal snapshot as safety net
            try:
                from tasks.tasks import snapshot_current_stats as _snap_min
                logger.info("Running minimal snapshot (snapshot_current_stats) for safety")
                fallback_dir = directory_path or getattr(settings, "CSV_FILES_DIR", None) or str(get_data_root())
                min_snap_res = _snap_min(directory_path=fallback_dir)
                logger.info(f"Minimal snapshot result: {min_snap_res}")
            except Exception as e:
                logger.debug(f"Minimal snapshot failed: {e}")

            # Cache invalidation after final snapshots
            try:
                from api.stats import invalidate_caches as _invalidate
                _invalidate("final snapshots complete")
                logger.info("Caches invalidated after final snapshots")
            except Exception as e:
                logger.debug(f"Cache invalidation after final snapshots failed: {e}")

            # Presence check for CP-8832
            try:
                from utils.opensearch import opensearch_config as _osc
                cur = _osc.get_stats_snapshot(file="netspeed.csv", date=today_str)
                if isinstance(cur, dict):
                    models_list = [m.get("model") for m in cur.get("phonesByModel", []) if isinstance(m, dict)]
                    if "CP-8832" not in models_list:
                        logger.warning("WARN: Modell CP-8832 fehlt nach finalen Snapshots. Bitte Daten prüfen.")
                    else:
                        logger.info("Validierung: Modell CP-8832 vorhanden nach finalen Snapshots.")
            except Exception as e:
                logger.debug(f"Presence check CP-8832 failed: {e}")
        else:
            logger.info(f"Current file not found for final snapshot operations: {current_file_path}")

        return {
            "status": "success",
            "message": f"Processed {len(ordered_files)} files, indexed {total_documents} documents",
            "directory": directory_label,
            "files_processed": len(ordered_files),
            "total_documents": total_documents,
            "results": results,
            "started_at": start_time.isoformat() + 'Z',
            "finished_at": last_success_ts,
        }
    except Exception as e:
        logger.error(f"Error indexing directory {directory_label}: {e}")
        try:
            clear_active(index_state, 'failed')
            save_state(index_state)
        except Exception:
            pass
        return {"status": "error", "message": f"Error processing directory: {str(e)}", "directory": directory_label, "files_processed": 0, "total_documents": 0}
