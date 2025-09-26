import os
from celery import Celery
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from utils.opensearch import opensearch_config
from datetime import datetime
from utils.index_state import load_state, save_state, update_file_state, update_totals, is_file_current, start_active, update_active, clear_active
from utils.csv_utils import read_csv_file_normalized

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

        # Ensure consistent display columns (idempotent if already filtered)
        try:
            from utils.csv_utils import filter_display_columns
            filtered_headers, filtered_documents = filter_display_columns(headers, documents)
        except Exception:
            filtered_headers, filtered_documents = headers, documents

        took_ms = int((perf_counter() - t0) * 1000)
        return {
            "status": "success",
            "message": f"Found {len(filtered_documents)} results for '{query}'",
            "headers": filtered_headers or [],
            "data": filtered_documents or [],
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
def snapshot_current_stats(directory_path: str = "/app/data") -> dict:
    """Compute and persist today's stats snapshot for netspeed.csv only.

    phonesWithKEM counts unique phones with >=1 KEM; totalKEMs counts modules.
    """
    try:
        from models.file import FileModel as _FM
        # Allow override via ENV NETSPEED_DATA_DIR
        env_dir = os.environ.get("NETSPEED_DATA_DIR")
        if env_dir:
            directory_path = env_dir
        data_dir = Path(directory_path)
        file_path = data_dir / "netspeed.csv"
        if not file_path.exists():
            # Fallback real path
            alt = Path("/usr/scripts/netspeed/netspeed.csv")
            if alt.exists():
                file_path = alt
        if not file_path.exists():
            return {"status": "warning", "message": f"Current file not found: {file_path}"}

        fm = _FM.from_path(str(file_path))
        date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
        _, rows = read_csv_file_normalized(str(file_path))

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
            # Always assign to institution-specific counts, even for devices without switch hostname
            try:
                from api.stats import is_jva_switch
                if is_jva_switch(sh):
                    jva_model_counts[model] = jva_model_counts.get(model, 0) + 1
                else:
                    # Devices without switch hostname default to Justiz
                    justiz_model_counts[model] = justiz_model_counts.get(model, 0) + 1
            except Exception:
                # Fallback: assign to Justiz on any error
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
def snapshot_current_with_details(file_path: str = "/app/data/netspeed.csv", force_date: Optional[str] = None) -> dict:
    """Compute and persist stats snapshot with detailed per-location documents.

    - Writes stats_netspeed (global) incl. Justiz/JVA model breakdown + details arrays
    - Writes stats_netspeed_loc with per-location model lists, VLAN usage, switch VLAN mapping, KEM phones
    - force_date allows overriding the file date (UI expects today's date for details)
    """
    try:
        # ENV override
        if file_path.endswith("netspeed.csv") and not Path(file_path).exists():
            env_dir = os.environ.get("NETSPEED_DATA_DIR")
            if env_dir:
                candidate = Path(env_dir) / "netspeed.csv"
                if candidate.exists():
                    file_path = str(candidate)
        p = Path(file_path)
        if not p.exists():
            # Fallback to real prod path
            alt = Path("/usr/scripts/netspeed/netspeed.csv")
            if alt.exists():
                p = alt
                file_path = str(alt)
        if not p.exists():
            return {"status": "warning", "message": f"File not found: {file_path}"}
        from models.file import FileModel as _FM
        fm = _FM.from_path(str(p))
        date_str = force_date or (fm.date.strftime('%Y-%m-%d') if fm.date else None)
        _, rows = read_csv_file_normalized(str(p))

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


@app.task(name='tasks.index_csv')
def index_csv(file_path: str) -> dict:
    """
    Task to index a CSV file in OpenSearch.

    Args:
        file_path: Path to the CSV file to index

    Returns:
        dict: A dictionary containing the indexing result
    """
    logger.info(f"Indexing CSV file at {file_path}")

    try:
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
        else:
            return {
                "status": "error",
                "message": f"Failed to index {file_path}",
                "file_path": file_path,
                "count": 0
            }
    except Exception as e:
        logger.error(f"Error indexing CSV file {file_path}: {e}")
        return {
            "status": "error",
            "message": f"Error indexing file: {str(e)}",
            "file_path": file_path,
            "count": 0
        }


@app.task(name='tasks.backfill_location_snapshots')
def backfill_location_snapshots(directory_path: str = "/app/data") -> dict:
    """Backfill per-location snapshots (stats_netspeed_loc) for all netspeed files.

    Useful if stats_netspeed_loc is empty or partially populated.
    """
    try:
        path = Path(directory_path)
        files = []
        for p in sorted(path.glob("netspeed.csv*"), key=lambda x: x.name):
            name = p.name
            if name == "netspeed.csv" or (name.startswith("netspeed.csv.") and name.replace("netspeed.csv.", "").isdigit()):
                files.append(p)
        processed = 0
        total_loc_docs = 0
        for f in files:
            try:
                from models.file import FileModel as _FM
                fm = _FM.from_path(str(f))
                date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
                _, rows = read_csv_file_normalized(str(f))

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

                    # Format VLAN usage
                    vlan_usage = [{"vlan": v, "count": c} for v, c in details["vlans"].items()]
                    # Sort VLANs numerically
                    def vlan_key(item):
                        v = item["vlan"]
                        try:
                            return (0, int(v))
                        except:
                            return (1, v)
                    vlan_usage.sort(key=vlan_key)

                    # Format switches
                    switches = [{"hostname": sw} for sw in sorted(details["switches"])]

                    loc_docs.append({
                        "key": k,
                        "mode": "code",
                        "totalPhones": agg["totalPhones"],
                        "totalSwitches": agg["totalSwitches"],
                        # Consistency: set to kem_phones length when available
                        "phonesWithKEM": int(len(details["kem_phones"])) if isinstance(details.get("kem_phones"), list) else int(agg.get("phonesWithKEM", 0)),
                        "phonesByModel": loc_all_models_list,
                        "phonesByModelJustiz": loc_justiz_models,
                        "phonesByModelJVA": loc_jva_models,
                        "vlanUsage": vlan_usage,
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
def backfill_stats_snapshots(directory_path: str = "/app/data") -> dict:
    """Backfill global stats snapshots (stats_netspeed) for all netspeed files.

    Computes from CSV only; does not touch netspeed_* search indices.
    phonesWithKEM = unique phones with >=1 KEM; totalKEMs = number of modules.
    """
    try:
        path = Path(directory_path)
        files: List[Path] = []
        for p in sorted(path.glob("netspeed.csv*"), key=lambda x: x.name):
            name = p.name
            if name == "netspeed.csv" or (name.startswith("netspeed.csv.") and name.replace("netspeed.csv.", "").isdigit()):
                files.append(p)
        processed = 0
        for f in files:
            try:
                from models.file import FileModel as _FM
                fm = _FM.from_path(str(f))
                date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
                _, rows = read_csv_file_normalized(str(f))

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


@app.task(bind=True, name='tasks.index_all_csv_files')
def index_all_csv_files(self, directory_path: str) -> dict:
    """Index all CSV files and persist snapshots with correct KEM semantics.

    - Index historical first, then current file
    - phonesWithKEM = unique phones; totalKEMs = modules
    - Also writes per-location snapshots with unique KEM phone counting
    """
    logger.info(f"Indexing all CSV files in {directory_path}")

    # Protection against concurrent indexing tasks
    try:
        index_state = load_state()
        # Determine current file path (support nested layout /<root>/netspeed/netspeed.csv first)
        current_candidates = [
            Path(directory_path) / "netspeed" / "netspeed.csv",
            Path(directory_path) / "netspeed.csv",
        ]
        current_file_path = None
        for cand in current_candidates:
            if cand.exists():
                current_file_path = cand
                break
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
        active_task = index_state.get("active_task", {})
        if active_task.get("status") == "running":
            existing_task_id = active_task.get("task_id")
            current_task_id = getattr(self.request, 'id', 'unknown')
            if existing_task_id and existing_task_id != current_task_id:
                logger.warning(f"Another indexing task {existing_task_id} is already running. Aborting task {current_task_id}")
                return {
                    "status": "aborted",
                    "message": f"Another indexing task {existing_task_id} is already running",
                    "directory": directory_path,
                    "files_processed": 0,
                    "total_documents": 0,
                }
    except Exception as e:
        logger.warning(f"Failed to check for concurrent tasks: {e}")

    try:
        path = Path(directory_path)
        scanned_dirs: List[Path] = [path]
        nested_current_dir = path / "netspeed"
        nested_history_dir = path / "history" / "netspeed"
        for d in (nested_current_dir, nested_history_dir):
            if d.exists() and d.is_dir():
                scanned_dirs.append(d)
        patterns = ["netspeed.csv", "netspeed.csv.*", "netspeed.csv_bak"]
        files_set: dict[str, Path] = {}
        def _add(p: Path):
            try:
                rp = str(p.resolve())
                if rp not in files_set:
                    files_set[rp] = p
            except Exception:
                pass
        for d in scanned_dirs:
            for pattern in patterns:
                for p in d.glob(pattern):
                    if p.is_file() and p.name.startswith("netspeed.csv"):
                        _add(p)
        all_found_files = list(files_set.values())
        netspeed_files = [f for f in all_found_files if (f.name.startswith("netspeed.csv") and f.name != "netspeed.csv_bak" and not f.name.endswith("_bak"))]
        backup_files = [f for f in all_found_files if f.name.endswith("_bak") or f.name == "netspeed.csv_bak"]

        # Separate current vs historical (support multiple current candidates – dedupe by resolved path)
        current_files = [f for f in netspeed_files if f.name == "netspeed.csv"]
        historical_files_all = [f for f in netspeed_files if f.name != "netspeed.csv"]

        # Sort historical numerically by suffix netspeed.csv.N
        def _hist_key(p: Path):
            name = p.name
            if name.startswith("netspeed.csv."):
                suf = name.split("netspeed.csv.", 1)[1]
                if suf.isdigit():
                    return int(suf)
            return 1_000_000  # large number to push unexpected names to end
        historical_files_all.sort(key=_hist_key)
        files = historical_files_all + current_files + backup_files

        logger.info(
            "Discovered %d netspeed-related files (hist=%d, current=%d, backups=%d) in directories: %s",
            len(files), len(historical_files_all), len(current_files), len(backup_files),
            ", ".join(str(d) for d in scanned_dirs)
        )
        if not files:
            return {"status": "warning", "message": f"No CSV files found in {directory_path} (scanned nested dirs)", "directory": directory_path, "files_processed": 0, "total_documents": 0}

        ordered_files = files  # already ordered: historical numeric -> current -> backups

        results: List[Dict] = []
        total_documents = 0
        index_state = load_state()

        # Start progress
        try:
            task_id = getattr(self.request, 'id', os.environ.get('CELERY_TASK_ID', 'manual'))
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
                line_count = 0
                try:
                    with open(file_path, 'r') as fh:
                        total_lines = sum(1 for _ in fh)
                        if total_lines > 0:
                            line_count = total_lines - 1
                except Exception:
                    line_count = 0

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
                    _, _rows = read_csv_file_normalized(str(file_path))

                    total_phones = len(_rows)
                    switches = set(); locations = set(); city_codes = set()
                    phones_with_kem_unique = 0; total_kem_modules = 0
                    model_counts: Dict[str, int] = {}; justiz_model_counts: Dict[str, int] = {}; jva_model_counts: Dict[str, int] = {}
                    justiz_switches = set(); justiz_locations = set(); justiz_city_codes = set(); justiz_phones_with_kem_unique = 0; justiz_total_kem_modules = 0
                    jva_switches = set(); jva_locations = set(); jva_city_codes = set(); jva_phones_with_kem_unique = 0; jva_total_kem_modules = 0

                    for r in _rows:
                        sh = (r.get("Switch Hostname") or "").strip(); is_jva = False
                        if sh:
                            switches.add(sh)
                            try:
                                from api.stats import is_jva_switch
                                is_jva = is_jva_switch(sh)
                            except Exception:
                                is_jva = False
                            # (Kein finaler Snapshot innerhalb der Loop – verschoben ans Ende)

                        model = (r.get("Model Name") or "").strip() or "Unknown"
                        if model != "Unknown":
                            try:
                                from api.stats import is_mac_like
                                if len(model) < 4 or is_mac_like(model):
                                    model = "Unknown"
                            except Exception:
                                pass
                        model_counts[model] = model_counts.get(model, 0) + 1
                        if sh:
                            try:
                                from api.stats import is_jva_switch
                                if is_jva_switch(sh):
                                    jva_model_counts[model] = jva_model_counts.get(model, 0) + 1
                                else:
                                    justiz_model_counts[model] = justiz_model_counts.get(model, 0) + 1
                            except Exception:
                                justiz_model_counts[model] = justiz_model_counts.get(model, 0) + 1

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
                    opensearch_config.index_stats_snapshot(file=fm.name, date=date_str, metrics=metrics)

                    # Basic per-location snapshots (unique KEM phones)
                    try:
                        per_loc_counts: Dict[str, Dict[str, int]] = {}
                        per_loc_switches: Dict[str, set] = {}
                        for r in _rows:
                            sh2 = (r.get("Switch Hostname") or "").strip()
                            if not sh2: continue
                            try:
                                from api.stats import extract_location as _extract_location
                                loc2 = _extract_location(sh2)
                            except Exception:
                                loc2 = None
                            if not loc2: continue
                            plc = per_loc_counts.setdefault(loc2, {"totalPhones": 0, "phonesWithKEM": 0, "totalSwitches": 0})
                            plc["totalPhones"] += 1
                            sset = per_loc_switches.setdefault(loc2, set())
                            if sh2 not in sset:
                                sset.add(sh2); plc["totalSwitches"] += 1
                            kem1 = (r.get("KEM") or "").strip(); kem2 = (r.get("KEM 2") or "").strip()
                            has_kem = bool(kem1) or bool(kem2)
                            if not has_kem:
                                ln = (r.get("Line Number") or "").strip()
                                if "KEM" in ln:
                                    has_kem = True
                            if has_kem:
                                plc["phonesWithKEM"] += 1
                        loc_docs = [{"key": k, "mode": "code", "totalPhones": agg["totalPhones"], "totalSwitches": agg["totalSwitches"], "phonesWithKEM": agg["phonesWithKEM"]} for k, agg in per_loc_counts.items()]
                        if loc_docs:
                            opensearch_config.index_stats_location_snapshots(file=fm.name, date=date_str, loc_docs=loc_docs)
                    except Exception as _e:
                        logger.debug(f"Per-location snapshot indexing failed for {file_path}: {_e}")
                except Exception as _e:
                    logger.debug(f"Stats snapshot failed for {file_path}: {_e}")

                # Archive snapshot
                try:
                    if '_rows' not in locals():
                        _, _rows = read_csv_file_normalized(str(file_path))
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
        # Detect current file in nested or flat layout
        current_candidates_final = [
            Path(directory_path) / "netspeed" / "netspeed.csv",
            Path(directory_path) / "netspeed.csv",
        ]
        current_file_path = None
        for cand in current_candidates_final:
            if cand.exists():
                current_file_path = cand
                break
        if current_file_path and current_file_path.exists():
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
                min_snap_res = _snap_min(directory_path=directory_path)
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
            "directory": directory_path,
            "files_processed": len(ordered_files),
            "total_documents": total_documents,
            "results": results,
            "started_at": start_time.isoformat() + 'Z',
            "finished_at": last_success_ts,
        }
    except Exception as e:
        logger.error(f"Error indexing directory {directory_path}: {e}")
        try:
            clear_active(index_state, 'failed')
            save_state(index_state)
        except Exception:
            pass
        return {"status": "error", "message": f"Error processing directory: {str(e)}", "directory": directory_path, "files_processed": 0, "total_documents": 0}
