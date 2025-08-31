import os
from celery import Celery
import logging
from pathlib import Path
from typing import Optional, Dict, List
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

        if success:
            # Best-effort: persist stats snapshot for this file
            try:
                from models.file import FileModel as _FM
                fm = _FM.from_path(file_path)
                date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
                _, _rows = read_csv_file_normalized(file_path)
                total_phones = len(_rows)
                switches = set()
                locations = set()
                city_codes = set()
                phones_with_kem = 0
                model_counts: Dict[str, int] = {}
                justiz_model_counts: Dict[str, int] = {}
                jva_model_counts: Dict[str, int] = {}
                global_kem_phones: List[Dict] = []  # Global KEM phone list

                for r in _rows:
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
                    if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                        phones_with_kem += 1

                        # Add to global KEM phones list
                        kem_data = {
                            "ip": r.get("IP Address", ""),
                            "mac": r.get("MAC Address", ""),
                            "hostname": r.get("Switch Hostname", ""),
                            "port": r.get("Switch Port", ""),
                            "model": (r.get("Model Name") or "").strip() or "Unknown",
                            "kem": r.get("KEM", "").strip(),
                            "kem2": r.get("KEM 2", "").strip(),
                            "vlan": r.get("VLAN", "")
                        }
                        # Extract location if available
                        if sh:
                            try:
                                from api.stats import extract_location
                                loc = extract_location(sh)
                                kem_data["location"] = loc
                            except Exception:
                                kem_data["location"] = ""
                        else:
                            kem_data["location"] = ""

                        global_kem_phones.append(kem_data)

                    # Process model name
                    model = (r.get("Model Name") or "").strip() or "Unknown"
                    # Skip invalid models (MAC-like strings)
                    if model != "Unknown":
                        try:
                            from api.stats import is_mac_like
                            if len(model) < 4 or is_mac_like(model):
                                model = "Unknown"
                        except Exception:
                            pass

                    # Count overall models
                    model_counts[model] = model_counts.get(model, 0) + 1

                    # Count Justiz/JVA breakdown
                    if sh:
                        try:
                            from api.stats import is_jva_switch
                            if is_jva_switch(sh):
                                jva_model_counts[model] = jva_model_counts.get(model, 0) + 1
                            else:
                                justiz_model_counts[model] = justiz_model_counts.get(model, 0) + 1
                        except Exception:
                            # Default to Justiz if can't determine
                            justiz_model_counts[model] = justiz_model_counts.get(model, 0) + 1

                # Format results
                phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]
                phones_by_model.sort(key=lambda x: (-x["count"], x["model"]))

                phones_by_model_justiz = [{"model": m, "count": c} for m, c in justiz_model_counts.items()]
                phones_by_model_justiz.sort(key=lambda x: (-x["count"], x["model"]))

                phones_by_model_jva = [{"model": m, "count": c} for m, c in jva_model_counts.items()]
                phones_by_model_jva.sort(key=lambda x: (-x["count"], x["model"]))

                total_justiz_phones = sum(justiz_model_counts.values())
                total_jva_phones = sum(jva_model_counts.values())

                # Calculate detailed breakdown by location for Justiz/JVA
                justiz_details_by_location: Dict[str, Dict[str, int]] = {}
                jva_details_by_location: Dict[str, Dict[str, int]] = {}

                for r in _rows:
                    sh = (r.get("Switch Hostname") or "").strip()
                    if not sh:
                        continue

                    # Extract location code
                    try:
                        from api.stats import extract_location
                        location = extract_location(sh)
                    except Exception:
                        location = None

                    if not location:
                        continue

                    # Process model name
                    model = (r.get("Model Name") or "").strip() or "Unknown"
                    if model != "Unknown":
                        try:
                            from api.stats import is_mac_like
                            if len(model) < 4 or is_mac_like(model):
                                model = "Unknown"
                        except Exception:
                            pass

                    # Determine if JVA or Justiz and count by location
                    try:
                        from api.stats import is_jva_switch
                        if is_jva_switch(sh):
                            # JVA location
                            if location not in jva_details_by_location:
                                jva_details_by_location[location] = {}
                            jva_details_by_location[location][model] = jva_details_by_location[location].get(model, 0) + 1
                        else:
                            # Justiz location
                            if location not in justiz_details_by_location:
                                justiz_details_by_location[location] = {}
                            justiz_details_by_location[location][model] = justiz_details_by_location[location].get(model, 0) + 1
                    except Exception:
                        # Default to Justiz
                        if location not in justiz_details_by_location:
                            justiz_details_by_location[location] = {}
                        justiz_details_by_location[location][model] = justiz_details_by_location[location].get(model, 0) + 1

                # Format details results
                phones_by_model_justiz_details = []
                for location, models in justiz_details_by_location.items():
                    location_total = sum(models.values())
                    model_list = [{"model": m, "count": c} for m, c in models.items()]
                    model_list.sort(key=lambda x: (-x["count"], x["model"]))

                    # Get city name for display
                    city_code = location[:3] if location and len(location) >= 3 else ""
                    city_name = ""
                    if city_code:
                        try:
                            from api.stats import resolve_city_name
                            city_name = resolve_city_name(city_code)
                        except Exception:
                            city_name = city_code

                    display_name = f"{location} - {city_name}" if city_name and city_name != city_code else location

                    phones_by_model_justiz_details.append({
                        "location": location,
                        "locationDisplay": display_name,
                        "totalPhones": location_total,
                        "models": model_list  # Frontend expects 'models' not 'phonesByModel'
                    })
                phones_by_model_justiz_details.sort(key=lambda x: (-x["totalPhones"], x["location"]))

                phones_by_model_jva_details = []
                for location, models in jva_details_by_location.items():
                    location_total = sum(models.values())
                    model_list = [{"model": m, "count": c} for m, c in models.items()]
                    model_list.sort(key=lambda x: (-x["count"], x["model"]))

                    # Get city name for display
                    city_code = location[:3] if location and len(location) >= 3 else ""
                    city_name = ""
                    if city_code:
                        try:
                            from api.stats import resolve_city_name
                            city_name = resolve_city_name(city_code)
                        except Exception:
                            city_name = city_code

                    display_name = f"{location} - {city_name}" if city_name and city_name != city_code else location

                    phones_by_model_jva_details.append({
                        "location": location,
                        "locationDisplay": display_name,
                        "totalPhones": location_total,
                        "models": model_list  # Frontend expects 'models' not 'phonesByModel'
                    })
                phones_by_model_jva_details.sort(key=lambda x: (-x["totalPhones"], x["location"]))

                metrics = {
                    "totalPhones": total_phones,
                    "totalSwitches": len(switches),
                    "totalLocations": len(locations),
                    "totalCities": len(city_codes),
                    "phonesWithKEM": phones_with_kem,
                    "totalJustizPhones": total_justiz_phones,
                    "totalJVAPhones": total_jva_phones,
                    "phonesByModel": phones_by_model,
                    "phonesByModelJustiz": phones_by_model_justiz,
                    "phonesByModelJVA": phones_by_model_jva,
                    "phonesByModelJustizDetails": phones_by_model_justiz_details,
                    "phonesByModelJVADetails": phones_by_model_jva_details,
                    "cityCodes": sorted(list(city_codes)),
                }
                logger.info(f"JUSTIZ/JVA DEBUG: total_justiz_phones={total_justiz_phones}, total_jva_phones={total_jva_phones}")
                logger.info(f"JUSTIZ/JVA DEBUG: justiz_model_counts={justiz_model_counts}")
                logger.info(f"JUSTIZ/JVA DEBUG: jva_model_counts={jva_model_counts}")
                opensearch_config.index_stats_snapshot(file=fm.name, date=date_str, metrics=metrics)
                # Additionally: build per-location snapshot docs and index in bulk
                # Aggregate per 5-char location code for speed at query-time
                per_loc_counts: Dict[str, Dict[str, int]] = {}
                per_loc_switches: Dict[str, set] = {}
                for r in _rows:
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
                    if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                        plc["phonesWithKEM"] += 1

                # Collect additional details for each location (VLANs, switches, KEM phones)
                location_details = {}
                for r in _rows:
                    sh = (r.get("Switch Hostname") or "").strip()
                    if not sh:
                        continue

                    # Extract location code
                    try:
                        from api.stats import extract_location
                        location = extract_location(sh)
                    except Exception:
                        location = None

                    if not location:
                        continue

                    if location not in location_details:
                        location_details[location] = {
                            "vlans": {},
                            "switches": set(),
                            "switch_vlans": {},  # NEW: VLANs per switch
                            "kem_phones": []
                        }

                    # Collect VLAN usage (total for location)
                    vlan = (r.get("Voice VLAN") or "").strip()
                    if vlan:
                        location_details[location]["vlans"][vlan] = location_details[location]["vlans"].get(vlan, 0) + 1

                        # NEW: Collect VLANs per switch
                        if sh not in location_details[location]["switch_vlans"]:
                            location_details[location]["switch_vlans"][sh] = {}
                        location_details[location]["switch_vlans"][sh][vlan] = location_details[location]["switch_vlans"][sh].get(vlan, 0) + 1

                    # Collect switches
                    location_details[location]["switches"].add(sh)

                    # Collect KEM phones
                    kem = (r.get("KEM") or "").strip()
                    if kem and kem.upper() == "KEM":
                        ip = (r.get("IP Address") or "").strip()
                        model = (r.get("Model Name") or "").strip() or "Unknown"
                        mac = (r.get("MAC Address") or "").strip()
                        serial = (r.get("Serial Number") or "").strip()

                        if ip:  # Only add if we have an IP address
                            location_details[location]["kem_phones"].append({
                                "ip": ip,
                                "model": model,
                                "mac": mac,
                                "serial": serial,
                                "switch": sh
                            })

                # Build loc_docs with model details from already calculated data
                loc_docs = []
                for k, agg in per_loc_counts.items():
                    # Find this location in the already calculated detail data
                    justiz_detail = next((item for item in phones_by_model_justiz_details if item["location"] == k), None)
                    jva_detail = next((item for item in phones_by_model_jva_details if item["location"] == k), None)

                    # Extract model data
                    loc_justiz_models = justiz_detail["models"] if justiz_detail else []
                    loc_jva_models = jva_detail["models"] if jva_detail else []

                    # Combine all models for this location
                    loc_all_models = {}
                    for model_data in loc_justiz_models:
                        model = model_data["model"]
                        count = model_data["count"]
                        loc_all_models[model] = loc_all_models.get(model, 0) + count

                    for model_data in loc_jva_models:
                        model = model_data["model"]
                        count = model_data["count"]
                        loc_all_models[model] = loc_all_models.get(model, 0) + count

                    # Convert to list format
                    loc_all_models_list = [{"model": m, "count": c} for m, c in loc_all_models.items()]
                    loc_all_models_list.sort(key=lambda x: (-x["count"], x["model"]))

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

                    # Format switches with their VLANs
                    switches = []
                    switch_vlans = details.get("switch_vlans", {})
                    for sw in sorted(details["switches"]):
                        sw_vlans = switch_vlans.get(sw, {})
                        vlan_list = [{"vlan": v, "count": c} for v, c in sw_vlans.items()]
                        vlan_list.sort(key=vlan_key)
                        switches.append({
                            "hostname": sw,
                            "vlans": vlan_list
                        })

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
                        "switches": switches,
                        "kemPhones": details["kem_phones"]
                    })
                try:
                    opensearch_config.index_stats_location_snapshots(file=fm.name, date=date_str, loc_docs=loc_docs)
                except Exception as _e:
                    logger.debug(f"Indexing per-location snapshots failed for {file_path}: {_e}")
            except Exception as _e:
                logger.debug(f"Stats snapshot failed for {file_path}: {_e}")
            # Best-effort: persist full archive snapshot
            try:
                if '_rows' not in locals():
                    _, _rows = read_csv_file_normalized(file_path)
                opensearch_config.index_archive_snapshot(file=fm.name, date=date_str, rows=_rows)
            except Exception as _e:
                logger.debug(f"Archive snapshot failed for {file_path}: {_e}")
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
                    if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
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

                    # Collect KEM phones
                    kem = (r.get("KEM") or "").strip()
                    if kem and kem.upper() == "KEM":
                        ip = (r.get("IP Address") or "").strip()
                        model = (r.get("Model Name") or "").strip() or "Unknown"
                        mac = (r.get("MAC Address") or "").strip()
                        serial = (r.get("Serial Number") or "").strip()

                        if ip:  # Only add if we have an IP address
                            location_details[location]["kem_phones"].append({
                                "ip": ip,
                                "model": model,
                                "mac": mac,
                                "serial": serial,
                                "switch": sh
                            })

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
                        "phonesWithKEM": agg["phonesWithKEM"],
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

    This computes metrics from CSV files only and does not touch netspeed_* search indices.
    Useful when stats_netspeed is empty and you want fast timelines without full reindex.
    """
    try:
        path = Path(directory_path)
        files = []
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
                switches = set()
                locations = set()
                city_codes = set()
                phones_with_kem = 0
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
                    if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                        phones_with_kem += 1
                    model = (r.get("Model Name") or "").strip() or "Unknown"
                    if model != "Unknown":
                        model_counts[model] = model_counts.get(model, 0) + 1
                phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]
                metrics = {
                    "totalPhones": total_phones,
                    "totalSwitches": len(switches),
                    "totalLocations": len(locations),
                    "totalCities": len(city_codes),
                    "phonesWithKEM": phones_with_kem,
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
    """
    Task to index all CSV files in a directory.
    Includes protection against concurrent execution.

    Args:
        directory_path: Path to the directory containing CSV files

    Returns:
        dict: A dictionary containing the indexing results
    """
    logger.info(f"Indexing all CSV files in {directory_path}")

    # Protection against concurrent indexing tasks
    try:
        index_state = load_state()
        active_task = index_state.get("active_task", {})
        if active_task.get("status") == "running":
            existing_task_id = active_task.get("task_id")
            current_task_id = getattr(self.request, 'id', 'unknown')

            # If another task is already running, abort this one
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
        patterns = ["netspeed.csv", "netspeed.csv.*", "netspeed.csv_bak"]
        files: List[Path] = []
        for pattern in patterns:
            glob_results = sorted(path.glob(pattern), key=lambda x: str(x))
            files.extend(glob_results)

        # Only consider canonical netspeed files (no archives): netspeed.csv and netspeed.csv.N
        netspeed_files = [
            f for f in files
            if (f.name.startswith("netspeed.csv") and f.name != "netspeed.csv_bak" and not f.name.endswith("_bak"))
        ]
        # Separate backup files explicitly
        backup_files = [f for f in files if f.name.endswith("_bak") or f.name == "netspeed.csv_bak"]
        # Always include all netspeed files (base + all historical), backups last
        base_files = [f for f in netspeed_files if f.name == "netspeed.csv"]
        historical_files_all = [f for f in netspeed_files if f.name != "netspeed.csv"]
        files = base_files + historical_files_all + backup_files

        logger.info(f"Found {len(files)} files matching patterns {patterns} and archive: {[str(f.relative_to(path)) for f in files]}")

        if not files:
            return {
                "status": "warning",
                "message": f"No CSV files found in {directory_path}",
                "directory": directory_path,
                "files_processed": 0,
                "total_documents": 0,
            }

        current_files = [f for f in files if f.name == "netspeed.csv"]
        other_files = [f for f in files if f.name != "netspeed.csv"]
        # Important: Index historical files FIRST, then current file for data repair to work
        ordered_files = sorted(other_files, key=lambda x: x.name) + current_files

        logger.info(f"Indexing order (historical files first for data repair): {[f.name for f in ordered_files]}")

        results: List[Dict] = []
        total_documents = 0
        index_state = load_state()

        # Send initial progress and persist an active record
        try:
            task_id = getattr(self.request, 'id', os.environ.get('CELERY_TASK_ID', 'manual'))
            start_active(index_state, task_id, len(ordered_files))
            save_state(index_state)
            # Attach environment signature for isolation (dev vs prod): broker & opensearch URLs
            try:
                from config import settings as _settings
                update_active(index_state,
                              broker=_settings.REDIS_URL,
                              opensearch=_settings.OPENSEARCH_URL)
                save_state(index_state)
            except Exception:
                pass
            # Also expose Celery PROGRESS meta for /api/search/index/status/{task_id}
            try:
                self.update_state(state='PROGRESS', meta={
                    "task_id": task_id,
                    "status": "running",
                    "current_file": None,
                    "index": 0,
                    "total_files": len(ordered_files),
                    "documents_indexed": 0,
                })
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"Initial progress update failed: {e}")

        start_time = datetime.utcnow()

        for i, file_path in enumerate(ordered_files):
            logger.info(f"Processing file {i+1}/{len(ordered_files)}: {file_path}")
            # Emit a pre-index progress update so UI immediately shows the current file
            try:
                update_active(index_state,
                              current_file=file_path.name,
                              index=i + 1)
                save_state(index_state)
                try:
                    self.update_state(state='PROGRESS', meta={
                        "task_id": getattr(self.request, 'id', None),
                        "status": "running",
                        "current_file": file_path.name,
                        "index": i + 1,
                        "total_files": len(ordered_files),
                        "documents_indexed": total_documents,
                    })
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

                results.append({
                    "file": str(file_path),
                    "success": success,
                    "count": count,
                    "line_count": line_count
                })
                logger.info(f"Completed {file_path}: {count} documents indexed")

                # Persist a stats snapshot for timeline (best-effort)
                try:
                    from models.file import FileModel as _FM
                    fm = _FM.from_path(str(file_path))
                    date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None
                    # Compute metrics from normalized CSV (local, no opensearch read)
                    _, _rows = read_csv_file_normalized(str(file_path))
                    # Minimal recomputation to avoid duplicating logic
                    total_phones = len(_rows)
                    switches = set()
                    locations = set()
                    city_codes = set()
                    phones_with_kem = 0
                    model_counts: Dict[str, int] = {}
                    justiz_model_counts: Dict[str, int] = {}
                    jva_model_counts: Dict[str, int] = {}

                    for r in _rows:
                        sh = (r.get("Switch Hostname") or "").strip()
                        if sh:
                            switches.add(sh)
                            # Reuse extract_location from stats via a local import
                            try:
                                from api.stats import extract_location
                                loc = extract_location(sh)
                                if loc:
                                    locations.add(loc)
                                    city_codes.add(loc[:3])
                            except Exception:
                                pass
                        if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                            phones_with_kem += 1

                        # Process model name
                        model = (r.get("Model Name") or "").strip() or "Unknown"
                        # Skip invalid models (MAC-like strings)
                        if model != "Unknown":
                            try:
                                from api.stats import is_mac_like
                                if len(model) < 4 or is_mac_like(model):
                                    model = "Unknown"
                            except Exception:
                                pass

                        # Count overall models
                        model_counts[model] = model_counts.get(model, 0) + 1

                        # Count Justiz/JVA breakdown
                        if sh:
                            try:
                                from api.stats import is_jva_switch
                                if is_jva_switch(sh):
                                    jva_model_counts[model] = jva_model_counts.get(model, 0) + 1
                                else:
                                    justiz_model_counts[model] = justiz_model_counts.get(model, 0) + 1
                            except Exception:
                                # Default to Justiz if can't determine
                                justiz_model_counts[model] = justiz_model_counts.get(model, 0) + 1

                    # Format results
                    phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]
                    phones_by_model.sort(key=lambda x: (-x["count"], x["model"]))

                    phones_by_model_justiz = [{"model": m, "count": c} for m, c in justiz_model_counts.items()]
                    phones_by_model_justiz.sort(key=lambda x: (-x["count"], x["model"]))

                    phones_by_model_jva = [{"model": m, "count": c} for m, c in jva_model_counts.items()]
                    phones_by_model_jva.sort(key=lambda x: (-x["count"], x["model"]))

                    total_justiz_phones = sum(justiz_model_counts.values())
                    total_jva_phones = sum(jva_model_counts.values())

                    # Calculate detailed breakdown by location for Justiz/JVA
                    justiz_details_by_location: Dict[str, Dict[str, int]] = {}
                    jva_details_by_location: Dict[str, Dict[str, int]] = {}

                    for r in _rows:
                        sh = (r.get("Switch Hostname") or "").strip()
                        if not sh:
                            continue

                        # Extract location code
                        try:
                            from api.stats import extract_location
                            location = extract_location(sh)
                        except Exception:
                            location = None

                        if not location:
                            continue

                        # Process model name
                        model = (r.get("Model Name") or "").strip() or "Unknown"
                        if model != "Unknown":
                            try:
                                from api.stats import is_mac_like
                                if len(model) < 4 or is_mac_like(model):
                                    model = "Unknown"
                            except Exception:
                                pass

                        # Determine if JVA or Justiz and count by location
                        try:
                            from api.stats import is_jva_switch
                            if is_jva_switch(sh):
                                # JVA location
                                if location not in jva_details_by_location:
                                    jva_details_by_location[location] = {}
                                jva_details_by_location[location][model] = jva_details_by_location[location].get(model, 0) + 1
                            else:
                                # Justiz location
                                if location not in justiz_details_by_location:
                                    justiz_details_by_location[location] = {}
                                justiz_details_by_location[location][model] = justiz_details_by_location[location].get(model, 0) + 1
                        except Exception:
                            # Default to Justiz
                            if location not in justiz_details_by_location:
                                justiz_details_by_location[location] = {}
                            justiz_details_by_location[location][model] = justiz_details_by_location[location].get(model, 0) + 1

                    # Format details results
                    phones_by_model_justiz_details = []
                    for location, models in justiz_details_by_location.items():
                        location_total = sum(models.values())
                        model_list = [{"model": m, "count": c} for m, c in models.items()]
                        model_list.sort(key=lambda x: (-x["count"], x["model"]))

                        # Get city name for display
                        city_code = location[:3] if location and len(location) >= 3 else ""
                        city_name = ""
                        if city_code:
                            try:
                                from api.stats import resolve_city_name
                                city_name = resolve_city_name(city_code)
                            except Exception:
                                city_name = city_code

                        display_name = f"{location} - {city_name}" if city_name and city_name != city_code else location

                        phones_by_model_justiz_details.append({
                            "location": location,
                            "locationDisplay": display_name,
                            "totalPhones": location_total,
                            "models": model_list  # Frontend expects 'models' not 'phonesByModel'
                        })
                    phones_by_model_justiz_details.sort(key=lambda x: (-x["totalPhones"], x["location"]))

                    phones_by_model_jva_details = []
                    for location, models in jva_details_by_location.items():
                        location_total = sum(models.values())
                        model_list = [{"model": m, "count": c} for m, c in models.items()]
                        model_list.sort(key=lambda x: (-x["count"], x["model"]))

                        # Get city name for display
                        city_code = location[:3] if location and len(location) >= 3 else ""
                        city_name = ""
                        if city_code:
                            try:
                                from api.stats import resolve_city_name
                                city_name = resolve_city_name(city_code)
                            except Exception:
                                city_name = city_code

                        display_name = f"{location} - {city_name}" if city_name and city_name != city_code else location

                        phones_by_model_jva_details.append({
                            "location": location,
                            "locationDisplay": display_name,
                            "totalPhones": location_total,
                            "models": model_list  # Frontend expects 'models' not 'phonesByModel'
                        })
                    phones_by_model_jva_details.sort(key=lambda x: (-x["totalPhones"], x["location"]))

                    metrics = {
                        "totalPhones": total_phones,
                        "totalSwitches": len(switches),
                        "totalLocations": len(locations),
                        "totalCities": len(city_codes),
                        "phonesWithKEM": phones_with_kem,
                        "totalJustizPhones": total_justiz_phones,
                        "totalJVAPhones": total_jva_phones,
                        "phonesByModel": phones_by_model,
                        "phonesByModelJustiz": phones_by_model_justiz,
                        "phonesByModelJVA": phones_by_model_jva,
                        "phonesByModelJustizDetails": phones_by_model_justiz_details,
                        "phonesByModelJVADetails": phones_by_model_jva_details,
                        "cityCodes": sorted(list(city_codes)),
                    }
                    opensearch_config.index_stats_snapshot(file=fm.name, date=date_str, metrics=metrics)
                    # Additionally: precompute per-location snapshots for fast location timelines
                    try:
                        # Aggregate per 5-char location code
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
                            if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                                plc["phonesWithKEM"] += 1
                        loc_docs = []
                        for k, agg in per_loc_counts.items():
                            loc_docs.append({
                                "key": k,
                                "mode": "code",
                                "totalPhones": agg["totalPhones"],
                                "totalSwitches": agg["totalSwitches"],
                                "phonesWithKEM": agg["phonesWithKEM"],
                            })
                        if loc_docs:
                            opensearch_config.index_stats_location_snapshots(file=fm.name, date=date_str, loc_docs=loc_docs)
                    except Exception as _e:
                        logger.debug(f"Per-location snapshot indexing failed for {file_path}: {_e}")
                except Exception as _e:
                    logger.debug(f"Stats snapshot failed for {file_path}: {_e}")

                # Persist a full archive snapshot of rows (best-effort, excludes external city names)
                try:
                    if '_rows' not in locals():
                        _, _rows = read_csv_file_normalized(str(file_path))
                    opensearch_config.index_archive_snapshot(file=file_path.name, date=date_str, rows=_rows)
                except Exception as _e:
                    logger.debug(f"Archive snapshot failed for {file_path}: {_e}")

                # Progress update (persist)
                try:
                    update_active(index_state,
                                  current_file=file_path.name,
                                  index=i + 1,
                                  documents_indexed=total_documents)
                    save_state(index_state)
                except Exception as e:
                    logger.debug(f"Progress update failed: {e}")
                # Emit Celery PROGRESS meta for UI polling
                try:
                    self.update_state(state='PROGRESS', meta={
                        "task_id": task_id,
                        "status": "running",
                        "current_file": file_path.name,
                        "index": i + 1,
                        "total_files": len(ordered_files),
                        "documents_indexed": total_documents,
                    })
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")
                results.append({
                    "file": str(file_path),
                    "success": False,
                    "error": str(e),
                    "count": 0
                })

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

        # IMPORTANT: Apply data repair AFTER all files are indexed
        # This ensures historical indices are available for data lookup
        current_file_path = Path(directory_path) / "netspeed.csv"
        if current_file_path.exists():
            try:
                logger.info("Starting post-indexing data repair for current file")
                repair_result = opensearch_config.repair_current_file_after_indexing(str(current_file_path))
                if repair_result.get("success"):
                    logger.info(f"Data repair completed successfully: {repair_result}")
                else:
                    logger.warning(f"Data repair failed: {repair_result}")
            except Exception as e:
                logger.error(f"Post-indexing data repair failed: {e}")
        else:
            logger.info(f"Current file not found for data repair: {current_file_path}")

        return {
            "status": "success",
            "message": f"Processed {len(ordered_files)} files, indexed {total_documents} documents",
            "directory": directory_path,
            "files_processed": len(ordered_files),
            "total_documents": total_documents,
            "results": results,
            "started_at": start_time.isoformat() + 'Z',
            "finished_at": last_success_ts
        }
    except Exception as e:
        logger.error(f"Error indexing directory {directory_path}: {e}")
        try:
            clear_active(index_state, 'failed')
            save_state(index_state)
        except Exception:
            pass
        return {
            "status": "error",
            "message": f"Error processing directory: {str(e)}",
            "directory": directory_path,
            "files_processed": 0,
            "total_documents": 0
        }


@app.task(name='tasks.search_opensearch')
def search_opensearch(query: str, field: Optional[str] = None, include_historical: bool = False, size: int = 20000) -> dict:
    """
    Task to search OpenSearch.

    Args:
        query: Search query
        field: Optional field to search in
        include_historical: Whether to include historical indices

    Returns:
        dict: A dictionary containing the search results including file creation dates
    """
    logger.info(f"Searching OpenSearch for '{query}'")
    from time import perf_counter
    t0 = perf_counter()
    try:
        # Dev-friendly: reload OpenSearch module to pick up recent code changes without restarting Celery
        try:
            import sys, importlib
            os_mod = sys.modules.get('utils.opensearch')
            if os_mod is not None:
                os_mod = importlib.reload(os_mod)
            else:
                import utils.opensearch as os_mod  # type: ignore
            cfg = getattr(os_mod, 'opensearch_config', opensearch_config)
        except Exception:
            cfg = opensearch_config

        headers, documents = cfg.search(
            query=query,
            field=field,
            include_historical=include_historical,
            size=size
        )

        # Process documents to ensure file creation dates and formats are included
        # Avoid heavy per-row filesystem work by caching per file name within this search
        meta_cache: dict[str, dict] = {}

        def get_file_meta(_file_name: str) -> dict:
            if _file_name in meta_cache:
                return meta_cache[_file_name]
            meta: dict = {"date": None, "format": None}
            file_path = f"/app/data/{_file_name}"
            try:
                from models.file import FileModel as _FM
                fm = _FM.from_path(file_path)
                meta["date"] = fm.date.strftime('%Y-%m-%d') if fm.date else None
                meta["format"] = fm.format or None
            except Exception as _e:
                logger.debug(f"File meta probe failed for {_file_name}: {_e}")
            # Minimal fallbacks
            if meta["date"] is None:
                try:
                    from pathlib import Path as _Path
                    from datetime import datetime as _dt
                    p = _Path(file_path)
                    if p.exists():
                        meta["date"] = _dt.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d')
                except Exception:
                    pass
            if meta["format"] is None:
                # Heuristic: current netspeed.csv likely "new", historical default to "old"
                meta["format"] = "new" if _file_name == "netspeed.csv" else "old"
            meta_cache[_file_name] = meta
            return meta

        for doc in documents:
            file_name = doc.get('File Name')
            if not file_name:
                continue
            meta = None
            # Only fetch meta if any field is missing
            need_date = ('Creation Date' not in doc) or (not doc.get('Creation Date'))
            need_format = ('File Format' not in doc)
            if need_date or need_format:
                meta = get_file_meta(file_name)
            if need_date and meta and meta.get('date'):
                doc['Creation Date'] = meta['date']
            if need_format and meta and meta.get('format'):
                doc['File Format'] = meta['format']

    # Note: CSV fallback used during testing has been removed. OpenSearch results are used exclusively.

        # Apply same column filtering as Preview API for consistency
        from utils.csv_utils import filter_display_columns

        # Filter headers and data to match display preferences
        filtered_headers, filtered_documents = filter_display_columns(headers, documents)

        elapsed_ms = int((perf_counter() - t0) * 1000)
        return {
            "status": "success",
            "message": f"Found {len(filtered_documents)} results for '{query}'",
            "headers": filtered_headers,
            "data": filtered_documents,
            "took_ms": elapsed_ms
        }
    except Exception as e:
        logger.error(f"Error searching for '{query}': {e}")
        return {
            "status": "error",
            "message": f"Error searching: {str(e)}",
            "headers": [],
            "data": [],
            "took_ms": None
        }


# Removed: morning_reindex task (scheduler deprecated; file watcher handles reindexing)


@app.task(name='tasks.snapshot_current_stats')
def snapshot_current_stats(directory_path: str = "/app/data") -> dict:
    """Snapshot today's global and per-location statistics from the current netspeed.csv.

    This precaches timeline data in stats_netspeed and stats_netspeed_loc so the UI is fast.
    CSV remains a fallback only.
    """
    try:
        path = Path(directory_path)
        file_path = (path / "netspeed.csv").resolve()
        if not file_path.exists():
            return {"status": "warning", "message": f"{file_path} not found"}

        from models.file import FileModel as _FM
        fm = _FM.from_path(str(file_path))
        date_str = fm.date.strftime('%Y-%m-%d') if fm.date else None

        # Read CSV once
        _, rows = read_csv_file_normalized(str(file_path))

        # Global metrics
        total_phones = len(rows)
        switches = set()
        locations = set()
        city_codes = set()
        phones_with_kem = 0
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
            if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                phones_with_kem += 1
            model = (r.get("Model Name") or "").strip() or "Unknown"
            if model != "Unknown":
                model_counts[model] = model_counts.get(model, 0) + 1

        phones_by_model = [{"model": m, "count": c} for m, c in model_counts.items()]
        metrics = {
            "totalPhones": total_phones,
            "totalSwitches": len(switches),
            "totalLocations": len(locations),
            "totalCities": len(city_codes),
            "phonesWithKEM": phones_with_kem,
            "phonesByModel": phones_by_model,
            "cityCodes": sorted(list(city_codes)),
        }
        opensearch_config.index_stats_snapshot(file=fm.name, date=date_str, metrics=metrics)

        # Per-location metrics (aggregate per 5-char code)
        per_loc_counts: Dict[str, Dict[str, int]] = {}
        per_loc_switches: Dict[str, set] = {}
        for r in rows:
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
            if (r.get("KEM") or "").strip() or (r.get("KEM 2") or "").strip():
                plc["phonesWithKEM"] += 1
        loc_docs = []
        for k, agg in per_loc_counts.items():
            loc_docs.append({
                "key": k,
                "mode": "code",
                "totalPhones": agg["totalPhones"],
                "totalSwitches": agg["totalSwitches"],
                "phonesWithKEM": agg["phonesWithKEM"],
            })
        if loc_docs:
            opensearch_config.index_stats_location_snapshots(file=fm.name, date=date_str, loc_docs=loc_docs)

        # Optional: persist archive snapshot for the day
        try:
            opensearch_config.index_archive_snapshot(file=fm.name, date=date_str, rows=rows)
        except Exception:
            pass

        return {"status": "success", "file": fm.name, "date": date_str, "loc_docs": len(loc_docs)}
    except Exception as e:
        logger.error(f"snapshot_current_stats error: {e}")
        return {"status": "error", "message": str(e)}
