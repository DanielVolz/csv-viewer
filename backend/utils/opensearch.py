from opensearchpy import OpenSearch, helpers
from config import settings
import logging
import re
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Generator, Optional, Tuple
from .csv_utils import read_csv_file, read_csv_file_normalized
from utils.path_utils import collect_netspeed_files, get_data_root, _configured_roots, _within_allowed_roots
import os


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenSearchUnavailableError(RuntimeError):
    """Raised when OpenSearch cannot be reached within a grace period."""

    def __init__(self, message: str, *, attempts: int = 0, last_error: Optional[Exception] = None):
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


class OpenSearchConfig:
    _startup_grace_consumed = False
    _startup_grace_logged = False
    _host_order_logged = False
    """OpenSearch configuration and client management.

    Improvements made during cleanup:
    - Created reusable field type definitions (keyword_type and text_with_keyword)
    - Extracted separate methods for duplicated logic (query building, deduplication)
    - Better parameter organization with opensearch_params dictionary
    - Added documentation for methods
    - Note: credentials should be moved to environment variables in the future
    - Renamed class and instance from Elastic to OpenSearch to match actual technology used
    """

    def __init__(self):
        """Initialize OpenSearch configuration.

        Adds multi-host fallback support: OPENSEARCH_URL may contain a comma-separated
        list of host URLs (e.g. "http://opensearch:9200,http://localhost:9200"). We
        also auto-append sensible localhost fallbacks if only a single unresolvable
        DNS name is provided. The first host that responds to ping() is used.
        """
        self.hosts = self._build_host_list(settings.OPENSEARCH_URL)
        self._client = None
        self._initial_grace_applied = OpenSearchConfig._startup_grace_consumed
        # NOTE: After changing field mappings (e.g. IP Address from ip->text) existing indices
        # must be deleted & rebuilt (reindex) for the new mapping to apply.
        # Define field types for reuse
        self.keyword_type = {"type": "keyword"}
        self.text_with_keyword = {
            "type": "text",
            "fields": {
                "keyword": {"type": "keyword"}
            }
        }

        self.index_mappings = {
            # IMPORTANT: If you change mappings (e.g., Switch Hostname multi-field), you MUST delete existing
            # netspeed_* indices and trigger a rebuild for changes to take effect.
            "mappings": {
                "dynamic": "true",  # Allow dynamic field mapping
                "properties": {
                    "File Name": self.keyword_type,
                    "Creation Date": {
                        "type": "date",
                        "format": "yyyy-MM-dd"
                    },
                    # Changed from type 'ip' to text for partial / wildcard search support.
                    # If numeric range queries are needed later, introduce a parallel long form field.
                    "IP Address": self.text_with_keyword,
                    "Line Number": self.text_with_keyword,  # Now contains KEM info
                    "MAC Address": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "MAC Address 2": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "Serial Number": self.keyword_type,
                    "Model Name": self.text_with_keyword,  # Changed to support both text and keyword searches
                    "Subnet Mask": self.keyword_type,
                    "Voice VLAN": self.keyword_type,
                    # Make Switch Hostname case-insensitive & partially searchable via multi-field (keyword + lowered keyword)
                    "Switch Hostname": {
                        "type": "keyword",
                        "fields": {
                            "lower": {
                                "type": "keyword",
                                "normalizer": "lowercase_normalizer"
                            }
                        }
                    },
                    "Switch Port": self.keyword_type,
                    "Phone Port Speed": self.keyword_type,
                    "PC Port Speed": self.keyword_type,
                    "KEM 1 Serial Number": self.keyword_type,
                    "KEM 2 Serial Number": self.keyword_type,
                    "Speed 1": self.keyword_type,  # Legacy field retained for historical indices
                    "Speed 2": self.keyword_type,  # Legacy field retained for historical indices
                    # Legacy field names retained for historical indices
                    "Speed Switch-Port": self.keyword_type,
                    "Speed PC-Port": self.keyword_type,
                    # Canonical column names for switch/PC port mode
                    "Switch Port Mode": self.keyword_type,
                    "PC Port Mode": self.keyword_type,
                    # Call Manager fields (IMPORTANT: Use exact field names as they appear in CSV/OpenSearch)
                    # These field names MUST match the CSV headers exactly (with spaces)
                    "Call Manager Active Sub": self.text_with_keyword,
                    "Call Manager Standby Sub": self.text_with_keyword,
                    # Additional port configuration fields
                    "PC Port Duplex": self.keyword_type,
                    "Switch Port Duplex": self.keyword_type,
                    "Switch Port Speed": self.keyword_type,
                    "PC Port Remote Config": self.keyword_type,
                    "SW Port Remote Config": self.keyword_type,
                    "Port Auto Link Sync": self.keyword_type,
                    # KEM fields (Key Expansion Module)
                    "KEM": self.keyword_type,
                    "KEM 2": self.keyword_type,
                    "KEM 1 Serial Number": self.keyword_type,
                    "KEM 2 Serial Number": self.keyword_type,
                },
                "dynamic_templates": [
                    {
                        "strings_as_keywords": {
                            "match_mapping_type": "string",
                            "match": "Column *",
                            "mapping": {
                                "type": "text",
                                "fields": {
                                    "keyword": {"type": "keyword"}
                                }
                            }
                        }
                    }
                ]
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,  # No replicas for faster indexing
                "max_result_window": 20000,  # Increase from default 10000
                "refresh_interval": "30s",  # Slower refresh for faster indexing
                "index": {
                    "translog.durability": "async",  # Faster writes
                    "translog.sync_interval": "30s"
                },
                # Add custom normalizer for lowercase keyword comparisons
                "analysis": {
                    "normalizer": {
                        "lowercase_normalizer": {
                            "type": "custom",
                            "filter": ["lowercase"]
                        }
                    }
                }
            }
        }

        # Separate index for persisted time-series snapshots (not prefixed with 'netspeed_')
        self.stats_index = "stats_netspeed"
        self.stats_index_mappings = {
            "mappings": {
                "dynamic": "true",
                "properties": {
                    "file": {"type": "keyword"},
                    "date": {"type": "date", "format": "yyyy-MM-dd"},
                    "totalPhones": {"type": "long"},
                    "totalSwitches": {"type": "long"},
                    "totalLocations": {"type": "long"},
                    "totalCities": {"type": "long"},
                    "phonesWithKEM": {"type": "long"},
                    "phonesByModel": {
                        "type": "nested",
                        "properties": {
                            "model": {"type": "keyword"},
                            "count": {"type": "long"}
                        }
                    },
                    # Extended model breakdowns
                    "phonesByModelJustiz": {
                        "type": "nested",
                        "properties": {
                            "model": {"type": "keyword"},
                            "count": {"type": "long"}
                        }
                    },
                    "phonesByModelJVA": {
                        "type": "nested",
                        "properties": {
                            "model": {"type": "keyword"},
                            "count": {"type": "long"}
                        }
                    },
                    # Per-location model detail arrays (global snapshot perspective)
                    "phonesByModelJustizDetails": {
                        "type": "nested",
                        "properties": {
                            "location": {"type": "keyword"},
                            "locationDisplay": {"type": "keyword"},
                            "totalPhones": {"type": "long"},
                            "models": {
                                "type": "nested",
                                "properties": {
                                    "model": {"type": "keyword"},
                                    "count": {"type": "long"}
                                }
                            }
                        }
                    },
                    "phonesByModelJVADetails": {
                        "type": "nested",
                        "properties": {
                            "location": {"type": "keyword"},
                            "locationDisplay": {"type": "keyword"},
                            "totalPhones": {"type": "long"},
                            "models": {
                                "type": "nested",
                                "properties": {
                                    "model": {"type": "keyword"},
                                    "count": {"type": "long"}
                                }
                            }
                        }
                    },
                    "totalJustizPhones": {"type": "long"},
                    "totalJVAPhones": {"type": "long"},
                    "justizSwitches": {"type": "long"},
                    "justizLocations": {"type": "long"},
                    "justizCities": {"type": "long"},
                    "justizPhonesWithKEM": {"type": "long"},
                    "totalJustizKEMs": {"type": "long"},
                    "jvaSwitches": {"type": "long"},
                    "jvaLocations": {"type": "long"},
                    "jvaCities": {"type": "long"},
                    "jvaPhonesWithKEM": {"type": "long"},
                    "totalJVAKEMs": {"type": "long"},
                    "cityCodes": {"type": "keyword"}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "30s"
            }
        }

        # Per-location stats snapshots index (one doc per file/date/location code)
        self.stats_loc_index = "stats_netspeed_loc"
        self.stats_loc_index_mappings = {
            "mappings": {
                "dynamic": "true",
                "properties": {
                    "file": {"type": "keyword"},
                    "date": {"type": "date", "format": "yyyy-MM-dd"},
                    "key": {"type": "keyword"},  # location code (AAA01)
                    "mode": {"type": "keyword"},  # 'code'
                    "totalPhones": {"type": "long"},
                    "totalSwitches": {"type": "long"},
                    "phonesWithKEM": {"type": "long"},
                    "phonesByModel": {
                        "type": "nested",
                        "properties": {
                            "model": {"type": "keyword"},
                            "count": {"type": "long"}
                        }
                    },
                    "phonesByModelJustiz": {
                        "type": "nested",
                        "properties": {
                            "model": {"type": "keyword"},
                            "count": {"type": "long"}
                        }
                    },
                    "phonesByModelJVA": {
                        "type": "nested",
                        "properties": {
                            "model": {"type": "keyword"},
                            "count": {"type": "long"}
                        }
                    },
                    "vlanUsage": {
                        "type": "nested",
                        "properties": {
                            "vlan": {"type": "keyword"},
                            "count": {"type": "long"}
                        }
                    },
                    "topVLANs": {
                        "type": "nested",
                        "properties": {
                            "vlan": {"type": "keyword"},
                            "count": {"type": "long"}
                        }
                    },
                    "uniqueVLANCount": {"type": "long"},
                    "switches": {
                        "type": "nested",
                        "properties": {
                            "hostname": {"type": "keyword"}
                        }
                    },
                    "kemPhones": {
                        "type": "nested",
                        "properties": {
                            "ip": {"type": "ip"},
                            "model": {"type": "keyword"},
                            "mac": {"type": "keyword"},
                            "serial": {"type": "keyword"},
                            "switch": {"type": "keyword"},
                            "kemModules": {"type": "integer"}
                        }
                    }
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "30s"
            }
        }

        # Archive index to persist full daily snapshots of netspeed.csv
        # Not deleted by file watcher (it only deletes netspeed_* patterns)
        self.archive_index = "archive_netspeed"
        # Build archive mappings by copying netspeed mappings and adding snapshot fields
        archive_props = dict(self.index_mappings["mappings"]["properties"])  # shallow copy
        archive_props.update({
            "snapshot_date": {"type": "date", "format": "yyyy-MM-dd"},
            "snapshot_file": {"type": "keyword"}
        })
        self.archive_index_mappings = {
            "mappings": {
                "dynamic": "true",
                "properties": archive_props
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "30s",
                # Ensure the same normalizer exists for fields referencing it (e.g., Switch Hostname.lower)
                "analysis": {
                    "normalizer": {
                        "lowercase_normalizer": {
                            "type": "custom",
                            "filter": ["lowercase"]
                        }
                    }
                }
            }
        }

    @property
    def client(self) -> OpenSearch:
        """
        Get or create OpenSearch client.

        Returns:
            OpenSearch: Configured OpenSearch client
        """
        if self._client is None:
            grace = float(getattr(settings, "OPENSEARCH_STARTUP_GRACE_SECONDS", 0.0) or 0.0)
            wait_enabled = bool(getattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", True))
            need_grace = (
                wait_enabled
                and grace > 0
                and not self._initial_grace_applied
                and not OpenSearchConfig._startup_grace_consumed
            )
            if need_grace:
                logger.info(
                    f"Delaying OpenSearch connection attempts for {grace:.1f}s to allow service startup"
                )
                try:
                    time.sleep(grace)
                except Exception:
                    pass
            elif not wait_enabled:
                if grace > 0:
                    logger.debug(
                        "Skipping OpenSearch startup grace delay because OPENSEARCH_WAIT_FOR_AVAILABILITY is disabled"
                    )
            if not OpenSearchConfig._startup_grace_consumed:
                OpenSearchConfig._startup_grace_consumed = True
            if not self._initial_grace_applied:
                self._initial_grace_applied = True
            pwd = getattr(settings, 'OPENSEARCH_PASSWORD', None)
            last_err: Optional[Exception] = None
            for host in self.hosts:
                opensearch_params = {
                    'hosts': [host],  # single host attempt
                    'verify_certs': False,
                    'ssl_show_warn': False,
                    'request_timeout': 30,
                    'retry_on_timeout': True,
                    'max_retries': 2
                }
                if pwd:
                    opensearch_params['http_auth'] = ('admin', pwd)
                try:
                    candidate = OpenSearch(**opensearch_params)
                    if candidate.ping():
                        logger.info(f"Connected to OpenSearch host: {host}")
                        self._client = candidate
                        break
                    else:
                        logger.warning(f"Ping failed for OpenSearch host: {host}")
                except Exception as e:  # noqa: BLE001 broad to keep trying fallbacks
                    last_err = e
                    logger.warning(f"OpenSearch connection attempt failed for {host}: {e}")
            if self._client is None:
                # As a last resort construct a client with the original host list (may still fail later)
                logger.error("All OpenSearch host attempts failed; creating client with original host list for deferred errors")
                try:
                    params = {
                        'hosts': self.hosts,
                        'verify_certs': False,
                        'ssl_show_warn': False,
                        'request_timeout': 30,
                        'retry_on_timeout': True,
                        'max_retries': 1
                    }
                    if pwd:
                        params['http_auth'] = ('admin', pwd)
                    self._client = OpenSearch(**params)
                except Exception as e2:  # noqa: BLE001
                    logger.error(f"Failed to create fallback OpenSearch client: {e2}")
                    if last_err:
                        raise last_err
                    raise

        return self._client

    # ------------------------------------------------------------------
    # Availability helpers
    # ------------------------------------------------------------------
    def quick_ping(self) -> bool:
        """Check OpenSearch availability once without retrying.

        Returns:
            bool: True if ping succeeds, otherwise False.
        """

        try:
            return bool(self.client.ping())
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Quick OpenSearch ping failed: {exc}")
            return False

    def wait_for_availability(
        self,
        *,
        timeout: Optional[float] = None,
        interval: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Ping OpenSearch until it responds or the timeout elapses.

        Args:
            timeout: Maximum number of seconds to wait. Defaults to
                settings.OPENSEARCH_STARTUP_TIMEOUT_SECONDS.
            interval: Delay between ping attempts. Defaults to
                settings.OPENSEARCH_STARTUP_POLL_SECONDS.
            reason: Context string for logging.

        Returns:
            bool: True if OpenSearch responded before timeout. When waiting is
            disabled via settings.OPENSEARCH_WAIT_FOR_AVAILABILITY, returns
            False immediately without performing a ping.

        Raises:
            OpenSearchUnavailableError: When OpenSearch does not respond within
                the timeout window.
        """

        ctx = f" ({reason})" if reason else ""
        should_wait = bool(getattr(settings, "OPENSEARCH_WAIT_FOR_AVAILABILITY", True))
        if not should_wait:
            logger.info(f"Skipping OpenSearch availability wait{ctx}: disabled via configuration")
            return False

        max_wait = timeout if timeout is not None else float(getattr(settings, "OPENSEARCH_STARTUP_TIMEOUT_SECONDS", 45))
        poll_delay = interval if interval is not None else float(getattr(settings, "OPENSEARCH_STARTUP_POLL_SECONDS", 3.0))
        poll_delay = max(0.1, poll_delay)

        deadline = time.monotonic() + max_wait
        attempts = 0
        last_exc: Optional[Exception] = None

        while True:
            attempts += 1
            try:
                if self.client.ping():
                    if attempts > 1:
                        logger.info(f"OpenSearch responded after {attempts} attempts{ctx}")
                    return True
                logger.debug(f"OpenSearch ping attempt {attempts} returned False{ctx}")
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.debug(f"OpenSearch ping attempt {attempts} raised {exc!r}{ctx}")

            if time.monotonic() >= deadline:
                message = f"OpenSearch unavailable after {attempts} attempts within {max_wait}s{ctx}"
                raise OpenSearchUnavailableError(message, attempts=attempts, last_error=last_exc)

            time.sleep(poll_delay)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_host_list(self, raw: str) -> List[str]:
        """Parse OPENSEARCH_URL env (possibly comma-separated) and append fallbacks.

        Args:
            raw: Raw OPENSEARCH_URL string (e.g. 'http://opensearch:9200')

        Returns:
            Ordered list of hosts to attempt.
        """
        hosts: List[str] = []
        if raw:
            parts = [p.strip() for p in raw.split(',') if p.strip()]
            hosts.extend(parts)
        # If only one host and it's a bare docker service name, add localhost fallbacks
        if len(hosts) == 1:
            h = hosts[0]
            # Simple heuristic: contains 'opensearch' and no localhost/127.0.0.1 already
            if 'opensearch' in h and 'localhost' not in h and '127.0.0.1' not in h:
                # Derive port (default 9200 if not parseable)
                port_match = re.search(r':(\d+)', h)
                port = port_match.group(1) if port_match else '9200'
                localhost_variants = [
                    f"http://localhost:{port}",
                    f"http://127.0.0.1:{port}"
                ]
                for v in localhost_variants:
                    if v not in hosts:
                        hosts.append(v)
        if not OpenSearchConfig._host_order_logged:
            logger.info(f"OpenSearch host attempt order: {hosts}")
            OpenSearchConfig._host_order_logged = True
        else:
            logger.debug(f"OpenSearch host attempt order (cached): {hosts}")
        return hosts

    def get_index_name(self, file_path: str) -> str:
        """
        Generate index name for a CSV file.

        Args:
            file_path: Path to the CSV file

        Returns:
            str: Index name for the file
        """
        # Get the full file name without directory path
        file_name = Path(file_path).name.lower()

        # Extract a proper index name that handles extensions like .csv.1
        # Replace dots with underscores except for the file extension separator
        if file_name.startswith("netspeed"):
            return f"netspeed_{file_name.replace('.', '_')}"
        else:
            # For other files, fall back to old behavior
            base_name = Path(file_path).stem.lower()
            return f"netspeed_{base_name}"

    def get_search_indices(self, include_historical: bool = False) -> list[str]:
        """
        Get list of indices to search.

        Args:
            include_historical: Whether to include historical indices

        Returns:
            list[str]: List of index names to search
        """
        try:
            # Get all indices that exist
            indices = list(self.client.indices.get(index="*").keys())

            # Log the found indices for debugging
            logger.info(f"Available indices: {indices}")

            def _dedupe(sequence: list[str]) -> list[str]:
                seen: set[str] = set()
                ordered_unique: list[str] = []
                for item in sequence:
                    if not item:
                        continue
                    if item in seen:
                        continue
                    seen.add(item)
                    ordered_unique.append(item)
                return ordered_unique

            # Get all netspeed indices sorted by creation date (newest first)
            netspeed_entries = self.list_netspeed_indices()
            netspeed_ordered: list[str] = []
            for entry in netspeed_entries:
                idx_value = entry.get("index")
                if isinstance(idx_value, str) and idx_value:
                    netspeed_ordered.append(idx_value)

            archive_available = False
            try:
                archive_available = bool(self.client.indices.exists(index=self.archive_index))
            except Exception as archive_err:
                logger.debug(f"Archive existence check failed: {archive_err}")

            if include_historical:
                # Historical search: include all netspeed indices
                combined: list[str] = []
                combined.extend(netspeed_ordered)
                # Always provide wildcard fallback to catch any indices created after discovery
                combined.append("netspeed_*")
                if archive_available:
                    combined.append(self.archive_index)
                result = _dedupe(combined)
                if result:
                    logger.info(f"Historical search indices: {result}")
                    return result
            else:
                # Current-only search: find index for current file (not just newest by creation time)
                if netspeed_ordered:
                    # Determine the current file name
                    try:
                        from utils.path_utils import resolve_current_file
                        current_file_path = resolve_current_file()
                        if current_file_path:
                            current_filename = current_file_path.name
                            logger.info(f"Current file determined as: {current_filename}")

                            # Find the index that matches the current filename
                            for entry in netspeed_entries:
                                idx_name = entry.get("index")
                                file_name = entry.get("file_name")
                                if file_name == current_filename and idx_name:
                                    logger.info(f"Found index for current file: {idx_name}")
                                    return [str(idx_name)]

                            logger.warning(f"No index found for current file {current_filename}, falling back to newest index")
                    except Exception as e:
                        logger.warning(f"Failed to determine current file: {e}, falling back to newest index by filename")

                    # Fallback: use newest index by FILENAME date (not index creation time)
                    # Extract dates from filenames like netspeed_20251013-061543.csv
                    newest_by_filename = None
                    newest_date_str = ""
                    for entry in netspeed_entries:
                        idx_name = entry.get("index", "")
                        file_name = entry.get("file_name", "")
                        # Extract YYYYMMDD from filename (e.g., netspeed_20251013-061543.csv -> 20251013)
                        import re
                        date_match = re.search(r'(\d{8})', file_name)
                        if date_match:
                            date_str = date_match.group(1)
                            if date_str > newest_date_str:
                                newest_date_str = date_str
                                newest_by_filename = idx_name

                    if newest_by_filename:
                        logger.info(f"Using newest netspeed index by filename date: {newest_by_filename}")
                        return [newest_by_filename]

                    # Ultimate fallback: use first in list (sorted by index creation time)
                    logger.info(f"Using latest netspeed index for current-only search: {netspeed_ordered[0]}")
                    return [netspeed_ordered[0]]
                if archive_available:
                    logger.info("Using archive_netspeed index as fallback for current search")
                    return [self.archive_index]

            # If we reach here, no netspeed index could be determined
            logger.warning("No current netspeed index found. Search results may be empty.")
            # Return a non-existent index name to ensure no results rather than wrong results
            if archive_available:
                return [self.archive_index]
            return ["netspeed_current_only"]
        except Exception as e:
            logger.error(f"Error getting search indices: {e}")
            return ["netspeed_*"] if include_historical else ["netspeed_current_only"]

    # --- Netspeed index discovery helpers -------------------------------------------------

    @staticmethod
    def _index_to_filename(index_name: str) -> str:
        """Convert a netspeed_* index name back into a plausible filename."""
        if not index_name.startswith("netspeed_"):
            return index_name
        suffix = index_name[len("netspeed_"):]
        if suffix == "netspeed_csv":
            return "netspeed.csv"
        if suffix.startswith("netspeed_csv_"):
            return f"netspeed.csv.{suffix[len('netspeed_csv_') :]}"
        if suffix.endswith("_csv"):
            return suffix[:-4] + ".csv"
        return suffix.replace("_", ".")

    def list_netspeed_indices(self) -> list[dict[str, Any]]:
        """Return metadata for all netspeed_* indices with counts and creation time."""
        try:
            meta = self.client.indices.get(index="netspeed_*")
            if not isinstance(meta, dict):
                return []

            stats = self.client.indices.stats(index="netspeed_*", metric="docs")
            stats_map = stats.get("indices", {}) if isinstance(stats, dict) else {}

            entries: list[dict[str, Any]] = []
            for index_name, descriptor in meta.items():
                if not index_name.startswith("netspeed_"):
                    continue
                settings = descriptor.get("settings", {}).get("index", {})
                creation_raw = settings.get("creation_date") or settings.get("provided_name_timestamp")
                try:
                    creation_ms = int(creation_raw)
                except Exception:
                    creation_ms = 0

                docs_count = 0
                try:
                    docs_count = int(stats_map.get(index_name, {}).get("total", {}).get("docs", {}).get("count", 0))
                except Exception:
                    docs_count = 0

                entries.append(
                    {
                        "index": index_name,
                        "file_name": self._index_to_filename(index_name),
                        "creation_date_ms": creation_ms,
                        "documents": docs_count,
                    }
                )

            entries.sort(key=lambda e: e.get("creation_date_ms", 0), reverse=True)
            return entries
        except Exception as exc:
            logger.warning(f"list_netspeed_indices failed: {exc}")
            return []

    def get_latest_netspeed_snapshot(self) -> Optional[dict[str, Any]]:
        """Return metadata and top-level info for the most recent netspeed or archive snapshot."""
        entries = self.list_netspeed_indices()
        if entries:
            latest = entries[0]
            index_name = latest.get("index")
            if not index_name:
                return None

            try:
                search_res = self.client.search(
                    index=index_name,
                    body={
                        "size": 1,
                        "sort": [{"Creation Date": {"order": "desc"}}],
                        "query": {"match_all": {}},
                    },
                )
                hits = search_res.get("hits", {}).get("hits", []) if isinstance(search_res, dict) else []
                top_doc = hits[0].get("_source", {}) if hits else {}
            except Exception as exc:
                logger.warning(f"Failed to fetch latest document from {index_name}: {exc}")
                top_doc = {}

            creation_date = None
            for key in ("Creation Date", "creation_date", "date"):
                val = top_doc.get(key)
                if val:
                    creation_date = val
                    break

            return {
                "index": index_name,
                "file_name": latest.get("file_name"),
                "documents": latest.get("documents", 0),
                "creation_date": creation_date,
                "creation_date_ms": latest.get("creation_date_ms"),
                "top_document": top_doc,
            }

        return self.get_latest_archive_snapshot()

    def get_latest_archive_snapshot(self) -> Optional[dict[str, Any]]:
        """Return the latest archived snapshot when no live netspeed indices exist."""
        try:
            if not self.client.indices.exists(index=self.archive_index):
                return None

            search_res = self.client.search(
                index=self.archive_index,
                body={
                    "size": 1,
                    "sort": [
                        {"snapshot_date": {"order": "desc"}},
                        {"_doc": {"order": "desc"}},
                    ],
                    "query": {"match_all": {}},
                },
            )
            hits = search_res.get("hits", {}).get("hits", []) if isinstance(search_res, dict) else []
            if not hits:
                return None

            top_doc = hits[0].get("_source", {}) or {}
            snapshot_file = top_doc.get("snapshot_file") or top_doc.get("File Name")
            snapshot_date = top_doc.get("snapshot_date")

            documents = 0;
            if snapshot_file and snapshot_date:
                try:
                    count_body = {
                        "query": {
                            "bool": {
                                "must": [
                                    {"term": {"snapshot_file": snapshot_file}},
                                    {"term": {"snapshot_date": snapshot_date}},
                                ]
                            }
                        }
                    }
                    count_res = self.client.count(index=self.archive_index, body=count_body)
                    documents = int(count_res.get("count", 0)) if isinstance(count_res, dict) else 0
                except Exception as exc:
                    logger.debug(f"Archive snapshot count failed for {snapshot_file}@{snapshot_date}: {exc}")
                    documents = len(hits)

            creation_date_ms: Optional[int] = None
            if snapshot_date:
                try:
                    creation_date_ms = int(
                        datetime.strptime(snapshot_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
                    )
                except Exception:
                    creation_date_ms = None

            return {
                "index": self.archive_index,
                "file_name": snapshot_file or "archive snapshot",
                "documents": documents,
                "creation_date": snapshot_date,
                "creation_date_ms": creation_date_ms,
                "top_document": top_doc,
            }
        except Exception as exc:
            logger.warning(f"Failed to fetch latest archive snapshot: {exc}")
            return None

    def preview_index_rows(self, index_name: str, limit: int = 25) -> tuple[list[str], list[dict[str, Any]]]:
        """Fetch a small preview from the given netspeed index.
        Returns headers in standard order (metadata → alphabetical → Call Manager) with hidden fields filtered.
        """
        try:
            sort_clause = [{"Creation Date": {"order": "desc"}}, {"_doc": {"order": "asc"}}]
            if index_name == self.archive_index:
                sort_clause = [{"snapshot_date": {"order": "desc"}}, {"_doc": {"order": "desc"}}]

            res = self.client.search(
                index=index_name,
                body={
                    "size": max(1, limit),
                    "sort": sort_clause,
                    "query": {"match_all": {}},
                },
            )
            hits = res.get("hits", {}).get("hits", []) if isinstance(res, dict) else []
            rows = [hit.get("_source", {}) for hit in hits]

            # Use same header building logic as search for consistency
            headers = self._build_headers_from_documents(rows)

            # Filter row data to only include visible headers (removes KEM, KEM 2)
            filtered_rows = []
            for row in rows:
                filtered_row = {k: v for k, v in row.items() if k in headers}
                filtered_rows.append(filtered_row)

            return headers, filtered_rows
        except Exception as exc:
            logger.warning(f"preview_index_rows failed for {index_name}: {exc}")
            return [], []

    def create_index(self, index_name: str) -> bool:
        """
        Create an OpenSearch index with the appropriate mappings.

        Args:
            index_name: Name of the index to create

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if index exists
            if self.client.indices.exists(index=index_name):
                logger.info(f"Index {index_name} already exists")
                return True

            # Create index with mappings
            self.client.indices.create(
                index=index_name,
                body=self.index_mappings
            )
            logger.info(f"Successfully created index {index_name}")
            return True
        except Exception as e:
            logger.error(f"Error creating index {index_name}: {e}")
            return False

    def create_stats_index(self) -> bool:
        """Create the stats timeline index if it doesn't exist."""
        try:
            if self.client.indices.exists(index=self.stats_index):
                return True
            self.client.indices.create(index=self.stats_index, body=self.stats_index_mappings)
            logger.info(f"Created stats index {self.stats_index}")
            return True
        except Exception as e:
            logger.error(f"Error creating stats index {self.stats_index}: {e}")
            return False

    def create_stats_loc_index(self) -> bool:
        """Create the per-location stats index if it doesn't exist."""
        try:
            if self.client.indices.exists(index=self.stats_loc_index):
                return True
            self.client.indices.create(index=self.stats_loc_index, body=self.stats_loc_index_mappings)
            logger.info(f"Created stats per-location index {self.stats_loc_index}")
            return True
        except Exception as e:
            logger.error(f"Error creating stats loc index {self.stats_loc_index}: {e}")
            return False

    def index_stats_snapshot(self, *, file: str, date: str | None, metrics: dict) -> bool:
        """Index a single timeline snapshot document.

        Args:
            file: filename (e.g., netspeed.csv or netspeed.csv.N)
            date: ISO date YYYY-MM-DD
            metrics: flat dict with numeric metrics and lists for by-model/city codes
        """
        try:
            self.create_stats_index()
            # Use deterministic id to avoid duplicates if re-run: file + date
            doc_id = None
            if date:
                doc_id = f"{file}:{date}"
            body = {"file": file, "date": date, **metrics}
            self.client.index(index=self.stats_index, id=doc_id, body=body)
            return True
        except Exception as e:
            logger.error(f"Error indexing stats snapshot for {file}@{date}: {e}")
            return False

    def get_stats_snapshot(self, *, file: str, date: Optional[str]) -> Optional[Dict[str, Any]]:
        """Fetch an existing stats snapshot document by file and date.

        Returns the document _source or None if not found.
        """
        try:
            self.create_stats_index()
            doc_id = f"{file}:{date}" if date else None
            if doc_id:
                try:
                    res = self.client.get(index=self.stats_index, id=doc_id)
                    return res.get("_source") if isinstance(res, dict) else None
                except Exception:
                    return None
            # If no date provided, attempt to find latest by searching
            try:
                q = {
                    "query": {"term": {"file": file}},
                    "sort": [{"date": {"order": "desc"}}],
                    "size": 1
                }
                res = self.client.search(index=self.stats_index, body=q)
                hits = res.get("hits", {}).get("hits", [])
                if hits:
                    return hits[0].get("_source")
                return None
            except Exception:
                return None
        except Exception as e:
            logger.error(f"Error fetching stats snapshot for {file}@{date}: {e}")
            return None

    def index_stats_location_snapshots(self, *, file: str, date: str | None, loc_docs: List[Dict[str, Any]]) -> bool:
        """Bulk index per-location snapshot docs for a given file/date.

        Each doc in loc_docs must contain: { key, mode='code', totalPhones, totalSwitches, phonesWithKEM, phonesByModel, phonesByModelJustiz, phonesByModelJVA }
        """
        try:
            self.create_stats_loc_index()
            if not date:
                from datetime import datetime as _dt
                date = _dt.utcnow().strftime('%Y-%m-%d')
            actions = []
            for d in loc_docs:
                key = d.get('key')
                if not key:
                    continue
                body = {
                    "file": file,
                    "date": date,
                    "key": key,
                    "mode": d.get('mode', 'code'),
                    "totalPhones": int(d.get('totalPhones', 0)),
                    "totalSwitches": int(d.get('totalSwitches', 0)),
                    "phonesWithKEM": int(d.get('phonesWithKEM', 0)),
                    "phonesByModel": d.get('phonesByModel', []),
                    "phonesByModelJustiz": d.get('phonesByModelJustiz', []),
                    "phonesByModelJVA": d.get('phonesByModelJVA', []),
                    "vlanUsage": d.get('vlanUsage', []),
                    "topVLANs": d.get('topVLANs', []),
                    "uniqueVLANCount": int(d.get('uniqueVLANCount', 0) or 0),
                    "switches": d.get('switches', []),
                    "kemPhones": d.get('kemPhones', []),
                }
                doc_id = f"{file}:{date}:{key}"
                actions.append({
                    "_op_type": "index",
                    "_index": self.stats_loc_index,
                    "_id": doc_id,
                    "_source": body,
                })
            if not actions:
                return True
            helpers.bulk(self.client, actions)
            return True
        except Exception as e:
            logger.error(f"Error indexing stats per-location for {file}@{date}: {e}")
            return False

    def delete_index(self, index_name: str) -> bool:
        """
        Delete an OpenSearch index.

        Args:
            index_name: Name of the index to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if index exists
            if not self.client.indices.exists(index=index_name):
                logger.info(f"Index {index_name} does not exist")
                return True

            # Delete index
            self.client.indices.delete(
                index=index_name
            )
            logger.info(f"Successfully deleted index {index_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting index {index_name}: {e}")
            return False

    def create_archive_index(self) -> bool:
        """Create the archive index if it doesn't exist."""
        try:
            if self.client.indices.exists(index=self.archive_index):
                return True
            self.client.indices.create(index=self.archive_index, body=self.archive_index_mappings)
            logger.info(f"Created archive index {self.archive_index}")
            return True
        except Exception as e:
            logger.error(f"Error creating archive index {self.archive_index}: {e}")
            return False

    def index_archive_snapshot(self, *, file: str, date: str | None, rows: List[Dict[str, Any]]) -> Tuple[bool, int]:
        """Persist a full snapshot of rows for a given file/date into the archive index.

        This deletes any existing snapshot for the same file+date, then bulk-indexes the rows
        with additional fields snapshot_date and snapshot_file. Uses sequential ids for idempotency.
        """
        try:
            if not self.create_archive_index():
                return False, 0
            # Retention: keep only the last 4 years (approx). Best-effort cleanup.
            try:
                from config import settings as _settings
                years = getattr(_settings, 'ARCHIVE_RETENTION_YEARS', 4)
                self.purge_archive_older_than_years(years)
            except Exception:
                pass
            snapshot_date = date or datetime.utcnow().strftime('%Y-%m-%d')
            # Delete existing snapshot docs (best-effort)
            try:
                self.client.delete_by_query(
                    index=self.archive_index,
                    body={
                        "query": {
                            "bool": {
                                "must": [
                                    {"term": {"snapshot_file": file}},
                                    {"term": {"snapshot_date": snapshot_date}}
                                ]
                            }
                        }
                    }
                )
            except Exception:
                pass

            def _actions() -> Generator[Dict[str, Any], None, None]:
                for i, r in enumerate(rows, start=1):
                    # Ensure string values; keep existing fields
                    doc = {k: (str(v) if v is not None else "") for k, v in r.items()}
                    doc["snapshot_date"] = snapshot_date
                    doc["snapshot_file"] = file
                    yield {
                        "_index": self.archive_index,
                        "_id": f"{file}:{snapshot_date}:{i}",
                        "_source": doc
                    }

            success, failed = helpers.bulk(
                self.client,
                _actions(),
                chunk_size=1000,
                max_chunk_bytes=10 * 1024 * 1024,
                request_timeout=60,
                refresh=False
            )
            self.client.indices.refresh(index=self.archive_index)
            if failed:
                logger.warning(f"Archive snapshot had {failed} failed docs for {file}@{snapshot_date}")
            return True, success
        except Exception as e:
            logger.error(f"Error indexing archive snapshot for {file}@{date}: {e}")
            return False, 0

    def purge_archive_older_than_years(self, years: int) -> int:
        """Delete archived snapshot docs older than the specified number of years.

        Returns number of deleted docs (best-effort; 0 if unknown).
        """
        try:
            from datetime import timedelta
            # Approximate 4 years as 1461 days (365*4 + 1 leap)
            days = max(1, int(years * 365 + years // 4))
            cutoff = (datetime.utcnow().date() - timedelta(days=days)).strftime('%Y-%m-%d')
            body = {
                "query": {
                    "range": {
                        "snapshot_date": {"lt": cutoff}
                    }
                }
            }
            res = self.client.delete_by_query(index=self.archive_index, body=body)
            deleted = int(res.get('deleted', 0)) if isinstance(res, dict) else 0
            if deleted:
                logger.info(f"Purged {deleted} archived docs older than {cutoff}")
            return deleted
        except Exception as e:
            logger.warning(f"Failed to purge archive older than {years} years: {e}")
            return 0

    def cleanup_indices_by_pattern(self, pattern: str) -> int:
        """
        Delete all indices matching a pattern.

        Args:
            pattern: Pattern to match index names (e.g., "netspeed_*")

        Returns:
            int: Number of indices deleted
        """
        try:
            # Get all indices matching the pattern
            try:
                response = self.client.indices.get(index=pattern)
            except Exception:
                response = {}

            if not response or response == {}:
                logger.info(f"No indices found matching pattern: {pattern}")
                return 0

            indices_to_delete = list(response.keys())
            deleted_count = 0

            for index_name in indices_to_delete:
                try:
                    self.client.indices.delete(index=index_name)
                    logger.info(f"Successfully deleted index: {index_name}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting index {index_name}: {e}")

            logger.info(f"Deleted {deleted_count} indices matching pattern: {pattern}")
            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up indices with pattern {pattern}: {e}")
            return 0

    def update_index_settings(self, index_name: str) -> bool:
        """
        Update settings for an existing index.

        Args:
            index_name: Name of the index to update

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if index exists
            if not self.client.indices.exists(index=index_name):
                logger.warning(f"Index {index_name} does not exist")
                return False

            # Update max_result_window setting
            settings_update = {
                "index": {
                    "max_result_window": 20000
                }
            }

            self.client.indices.put_settings(
                index=index_name,
                body=settings_update
            )

            logger.info(f"Successfully updated settings for index {index_name}")
            return True
        except Exception as e:
            logger.error(f"Error updating settings for {index_name}: {e}")
            return False

    def generate_actions(self, index_name: str, file_path: str) -> Generator[Dict[str, Any], None, None]:
        """
        Generate actions for bulk indexing (optimized version).

        Args:
            index_name: Name of the index to index into
            file_path: Path to the CSV file to index

        Yields:
            Dict[str, Any]: Action for bulk indexing
        """
        # Use read_csv_file_normalized to preserve ALL columns for indexing
        _, rows_raw = read_csv_file_normalized(file_path)

        # CRITICAL: Deduplicate phone rows before indexing to OpenSearch
        # This prevents duplicate entries in search results (e.g., KEM search returning 3628 instead of 1813)
        from utils.csv_utils import deduplicate_phone_rows
        rows = deduplicate_phone_rows(rows_raw)

        if len(rows) != len(rows_raw):
            logger.info(
                f"Deduplicated {file_path}: {len(rows_raw)} -> {len(rows)} rows "
                f"({len(rows_raw) - len(rows)} duplicates removed)"
            )

        # Note: Data repair is now handled separately after all files are indexed
        # This ensures historical data is available when repairing the current file
        current_file_name = Path(file_path).name.lower()
        logger.debug(f"Skipping data repair during indexing for: {file_path}")

        # Get file creation date ONCE per file, not per row
        file_creation_date = None
        try:
            from models.file import FileModel
            file_model = FileModel.from_path(file_path)
            if file_model.date:
                file_creation_date = file_model.date.strftime('%Y-%m-%d')
                logger.info(f"Using FileModel date for {file_path}: {file_creation_date}")
        except Exception as model_error:
            logger.warning(f"FileModel unavailable for {file_path}: {model_error}")

        if not file_creation_date:
            try:
                from datetime import datetime
                import subprocess
                file_path_obj = Path(file_path)
                if file_path_obj.exists():
                    try:
                        process = subprocess.run(
                            ["stat", "-c", "%w", str(file_path_obj)],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        creation_time_str = process.stdout.strip()
                        if creation_time_str and creation_time_str != "-":
                            file_creation_date = creation_time_str.split()[0]
                            logger.info(f"Using filesystem creation date for {file_path}: {file_creation_date}")
                    except (subprocess.CalledProcessError, ValueError, IndexError):
                        pass

                    if not file_creation_date:
                        creation_timestamp = file_path_obj.stat().st_mtime
                        file_creation_date = datetime.fromtimestamp(creation_timestamp).strftime('%Y-%m-%d')
                        logger.info(f"Using modification time for {file_path}: {file_creation_date}")
            except Exception as fallback_error:
                logger.warning(f"Error deriving creation date for {file_path}: {fallback_error}")

        if not file_creation_date:
            from datetime import datetime
            file_creation_date = datetime.now().strftime('%Y-%m-%d')

        for idx, row in enumerate(rows, start=1):
            # Clean up data as needed (handle nulls, etc.)
            doc = {k: (v if v else "") for k, v in row.items()}

            # Use the pre-calculated file creation date
            if file_creation_date:
                doc["Creation Date"] = file_creation_date

            # Ensure File Name field exists (not part of original CSV headers)
            if "File Name" not in doc:
                doc["File Name"] = Path(file_path).name
            else:
                # Overwrite to be sure it's consistent
                doc["File Name"] = Path(file_path).name

            # Add sequential row number column '#'
            try:
                doc["#"] = str(idx)
            except Exception:
                doc["#"] = str(idx)

            # Index all available columns (no filtering at index level)
            final_doc = {k: str(v) for k, v in doc.items()}

            yield {
                "_index": index_name,
                "_source": final_doc
            }

    def _is_valid_mac_address(self, mac: str) -> bool:
        """
        Validate if a string is a valid MAC address.
        MAC addresses should be 12 hex characters (with or without separators).
        """
        if not mac:
            return False

        # Skip obvious non-MAC patterns
        if "." in mac and mac.count(".") >= 3:  # IP addresses
            return False
        if mac.isdigit() and len(mac) <= 4:  # VLANs like 801, 802
            return False
        if mac.startswith("255."):  # Subnet masks
            return False

        # Remove common separators
        clean_mac = mac.replace(":", "").replace("-", "").replace(".", "").upper()

        # Must be exactly 12 characters
        if len(clean_mac) != 12:
            return False

        # Must be all hexadecimal characters
        try:
            int(clean_mac, 16)
            return True
        except ValueError:
            return False

    def repair_missing_data(self, rows: List[Dict[str, Any]], file_path: str) -> List[Dict[str, Any]]:
        """
        Repair missing data by looking up values in historical indices using MAC address as identifier.

        DISABLED: This system causes CSV corruption by modifying data structures without updating
        the source CSV file, leading to field misalignment and corrupted output.

        Args:
            rows: List of CSV row dictionaries from current file
            file_path: Path to current CSV file (to exclude from historical search)

        Returns:
            List[Dict[str, Any]]: Original rows unchanged (repair disabled)
        """
        logger.info(f"DATA REPAIR: DISABLED - Skipping repair for {file_path} to prevent CSV corruption")
        return rows  # Return original rows unchanged

    def index_csv_file(self, file_path: str) -> Tuple[bool, int]:
        """
        Index a CSV file into OpenSearch.

        Args:
            file_path: Path to the CSV file to index

        Returns:
            Tuple[bool, int]: (success, number of documents indexed)
        """
        try:
            # Get index name
            index_name = self.get_index_name(file_path)

            # Create index if it doesn't exist
            if not self.create_index(index_name):
                return False, 0

            # Bulk index documents with optimized settings
            success, failed = helpers.bulk(
                self.client,
                self.generate_actions(index_name, file_path),
                chunk_size=1000,  # Process in chunks of 1000 docs
                max_chunk_bytes=10 * 1024 * 1024,  # 10MB chunks
                request_timeout=60,  # 60 second timeout
                refresh=False  # Don't refresh after every bulk operation (faster)
            )

            # Refresh only once at the end
            self.client.indices.refresh(index=index_name)

            logger.info(f"Indexed {success} documents into {index_name}")
            if failed:
                logger.warning(f"Failed to index {failed} documents")

            return True, success
        except Exception as e:
            logger.error(f"Error indexing file {file_path}: {e}")
            return False, 0

    def _deduplicate_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate documents based on MAC address and file name.

        Args:
            documents: List of documents to deduplicate

        Returns:
            List[Dict[str, Any]]: Deduplicated list of documents
        """
        deduplicated = {}
        for doc in documents:
            key = f"{doc.get('MAC Address', '')}-{doc.get('File Name', '')}"
            if key not in deduplicated:
                deduplicated[key] = doc

        # Convert back to list
        return list(deduplicated.values())

    def _deduplicate_documents_preserve_order(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate documents based on MAC address and file name while preserving sort order.

        Args:
            documents: List of documents to deduplicate (should be pre-sorted)

        Returns:
            List[Dict[str, Any]]: Deduplicated list of documents in original order
        """
        seen_keys = set()
        unique_documents = []

        for doc in documents:
            key = f"{doc.get('MAC Address', '')}-{doc.get('File Name', '')}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_documents.append(doc)

        logger.info(f"Deduplicated {len(documents)} documents to {len(unique_documents)} unique documents")
        return unique_documents

    def _netspeed_filenames(self) -> List[str]:
        """Return canonical netspeed file names based on configured data directories."""
        extras: List[Path | str] = []
        try:
            extras.append(get_data_root())
        except Exception:
            pass

        ordered: List[str] = []
        historical: List[Any] = []
        current: Optional[Any] = None

        try:
            historical, current, _ = collect_netspeed_files(extras if extras else None)
        except Exception:
            historical, current = [], None

        if current is not None:
            name = getattr(current, "name", None)
            if name:
                ordered.append(name)
        for path in historical:
            name = getattr(path, "name", None)
            if name:
                ordered.append(name)

        if ordered:
            return ordered

        explicit_roots = _configured_roots()

        # Fallback: direct filesystem scan using configured base directories
        scan_bases: List[Path] = []
        if extras:
            for extra in extras:
                try:
                    scan_bases.append(Path(extra))
                except Exception:
                    continue
        if not scan_bases:
            try:
                scan_bases.append(get_data_root())
            except Exception:
                scan_bases.append(Path("/app/data"))

        if explicit_roots:
            filtered_bases: List[Path] = []
            for base in scan_bases:
                if _within_allowed_roots(base, explicit_roots):
                    filtered_bases.append(base)
            scan_bases = filtered_bases
            if not scan_bases:
                return ordered

        for base in scan_bases:
            for candidate in (
                base,
                base / "netspeed",
                base / "history" / "netspeed",
            ):
                try:
                    patterns = ("netspeed_*.csv*", "netspeed.csv*")
                    entries: List[Path] = []
                    for pattern in patterns:
                        entries.extend(candidate.glob(pattern))
                    entries = sorted(entries, key=lambda p: getattr(p, "name", ""))
                except Exception:
                    continue
                for entry in entries:
                    name = getattr(entry, "name", None)
                    if not name:
                        continue
                    if name.startswith("netspeed_") and (name.endswith(".csv") or ".csv." in name):
                        if name not in ordered:
                            ordered.append(name)
                        continue
                    if name == "netspeed.csv" or (name.startswith("netspeed.csv.") and name.split("netspeed.csv.", 1)[1].isdigit()):
                        if name not in ordered:
                            ordered.append(name)

        return ordered

    def _preferred_file_names(self) -> List[str]:
        """Return netspeed file names ordered with the active export first."""
        names = [n for n in self._netspeed_filenames() if n]
        if not names:
            try:
                entries = self.list_netspeed_indices()
                for entry in entries:
                    filename = entry.get("file_name")
                    if filename and filename not in names:
                        names.append(filename)
            except Exception as exc:
                logger.debug(f"Preferred file name discovery via indices failed: {exc}")

        if "netspeed.csv" not in names:
            names.append("netspeed.csv")

        def _weight(name: str) -> tuple[int, int, int, str]:
            if not name:
                return (5, 0, 0, "")
            if name == "netspeed.csv":
                return (0, 0, 0, name)
            ts_match = re.match(r"^netspeed_(\d{8})-(\d{6})\.csv(?:\.(\d+))?$", name)
            if ts_match:
                stamp = int(ts_match.group(1) + ts_match.group(2))
                rotation = int(ts_match.group(3)) if ts_match.group(3) is not None else -1
                return (1, -stamp, rotation, name)
            if name.startswith("netspeed.csv."):
                suffix = name.split("netspeed.csv.", 1)[1]
                if suffix.isdigit():
                    return (2, int(suffix), 0, name)
            return (4, 0, 0, name)

        if names:
            deduped = list(dict.fromkeys(names))
            names = sorted(deduped, key=_weight)
        return names

    def _preferred_file_sort_script(self) -> Dict[str, Any]:
        """Return a painless script that ranks documents by preferred file order."""
        preferred = self._preferred_file_names()
        return {
            "lang": "painless",
            "params": {"preferred": preferred},
            "source": (
                "def fname = null;"
                "if (doc.containsKey('File Name') && doc['File Name'].size() > 0) {"
                " fname = doc['File Name'].value;"
                "}"
                "if (fname == null) { return params.preferred.size(); }"
                "int idx = params.preferred.indexOf(fname);"
                "return idx >= 0 ? idx : params.preferred.size();"
            )
        }

    def _preferred_file_sort_clause(self) -> Dict[str, Any]:
        """Return the reusable sort clause that prioritizes preferred netspeed files."""
        return {
            "_script": {
                "type": "number",
                "order": "asc",
                "script": self._preferred_file_sort_script(),
            }
        }

    def _build_query_body(self, query: str, field: Optional[str] = None,
                          size: int = 20000) -> Dict[str, Any]:
        """
        Build query body for OpenSearch.

        Args:
            query: Query string
            field: Optional field to search in
            size: Maximum number of results to return

        Returns:
            Dict[str, Any]: Query body
        """
        preferred_files = self._preferred_file_names()
        logger.debug(f"Building query body for query: {query}, field: {field}, size: {size}")

        # Special handling for KEM searches - return all phones that have at least 1 KEM module
        if not field and isinstance(query, str) and query.upper().strip() == "KEM":
            from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
            # KEM fields contain "KEM" string when module is present, empty string otherwise
            # Search for documents where KEM or KEM 2 field contains "KEM" (wildcard ?* matches any non-empty value)
            # IMPORTANT: We must include KEM and KEM 2 in _source so they can be processed later in search()
            # where they get embedded into Line Number field and then removed from display
            all_fields_including_kem = DESIRED_ORDER + ["KEM", "KEM 2"]
            kem_query = {
                "query": {
                    "bool": {
                        "should": [
                            # Match documents where KEM field has value "KEM" or similar
                            {"wildcard": {"KEM": "?*"}},
                            {"wildcard": {"KEM.keyword": "?*"}},
                            # Match documents where KEM 2 field has value "KEM" or similar
                            {"wildcard": {"KEM 2": "?*"}},
                            {"wildcard": {"KEM 2.keyword": "?*"}}
                        ],
                        "minimum_should_match": 1
                    }
                },
                "_source": all_fields_including_kem,
                "size": size,
                "sort": [
                    {"Creation Date": {"order": "desc"}},
                    self._preferred_file_sort_clause(),
                    {"_score": {"order": "desc"}}
                ]
            }
            return kem_query

        if field:
            from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
            qn = query.strip() if isinstance(query, str) else query
            # Phone-like Line Number exact-only
            if field == "Line Number" and isinstance(query, str):
                if re.fullmatch(r"\+?\d{7,}", qn or ""):
                    # Include both variants: with and without leading plus
                    variants = [qn]
                    if qn.startswith('+'):
                        variants.append(qn.lstrip('+'))
                    else:
                        variants.append(f"+{qn}")
                    return {
                        "query": {"bool": {"should": [
                            *([{ "term": {"Line Number.keyword": v} } for v in variants])
                        ], "minimum_should_match": 1}},
                        "_source": DESIRED_ORDER,
                        "size": 1,
                        "sort": [{"Creation Date": {"order": "desc"}}, {"_score": {"order": "desc"}}]
                    }

            # Switch Hostname exact-only (case-insensitive; robust via script filter)
            if field == "Switch Hostname" and isinstance(query, str):
                qh = query.strip()
                if qh:
                    return {
                        "query": {
                            "bool": {
                                "filter": [
                                    {
                                        "script": {
                                            "script": {
                                                "lang": "painless",
                                                "source": "def v = null; if (doc.containsKey('Switch Hostname') && doc['Switch Hostname'].size()>0) { v = doc['Switch Hostname'].value; } else { return false; } if (v == null) return false; return v.trim().equalsIgnoreCase(params.q.trim());",
                                                "params": {"q": qh}
                                            }
                                        }
                                    }
                                ],
                                "should": [
                                    {"term": {"Switch Hostname": qh}},
                                    {"term": {"Switch Hostname.lower": qh.lower()}}
                                ],
                                "minimum_should_match": 0
                            }
                        },
                        "_source": DESIRED_ORDER,
                        "size": size,
                        "sort": [
                            {"Creation Date": {"order": "desc"}},
                            self._preferred_file_sort_clause(),
                            {"_score": {"order": "desc"}}
                        ]
                    }

            if field == "Switch Port" and isinstance(qn, str) and qn:
                return {
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "script": {
                                        "script": {
                                            "lang": "painless",
                                            "source": "def v = null; if (doc.containsKey('Switch Port') && doc['Switch Port'].size()>0) { v = doc['Switch Port'].value; } else { return false; } if (v == null) return false; return v.trim().equalsIgnoreCase(params.q.trim());",
                                            "params": {"q": qn}
                                        }
                                    }
                                }
                            ],
                            "should": [
                                {"term": {"Switch Port": qn}}
                            ],
                            "minimum_should_match": 0
                        }
                    },
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        {"Creation Date": {"order": "desc"}},
                        {"_score": {"order": "desc"}}
                    ]
                }

            # Switch Hostname-like (FQDN) exact-only: contains dot and letters (not IP)
            if isinstance(qn, str) and any(c.isalpha() for c in qn) and "." in qn and "/" not in qn and " " not in qn:
                from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
                return {
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "script": {
                                        "script": {
                                            "lang": "painless",
                                            "source": "def v = null; if (doc.containsKey('Switch Hostname') && doc['Switch Hostname'].size()>0) { v = doc['Switch Hostname'].value; } else { return false; } if (v == null) return false; return v.trim().equalsIgnoreCase(params.q.trim());",
                                            "params": {"q": qn}
                                        }
                                    }
                                }
                            ],
                            "should": [
                                {"term": {"Switch Hostname": qn}},
                                {"term": {"Switch Hostname.lower": qn.lower()}},
                            ],
                            "minimum_should_match": 0
                        }
                    },
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        {"Creation Date": {"order": "desc"}},
                        self._preferred_file_sort_clause(),
                        {"_score": {"order": "desc"}}
                    ]
                }

            # Switch Hostname pattern without domain: 3 letters + 2 digits + other chars (like ABX01ZSL5210P or Mxx03ZSL)
            # Minimum length 8: AAA00BBB (location code + 3 chars suffix)
            hostname_pattern_match = re.match(r'^[A-Za-z]{3}[0-9]{2}', qn or "") if isinstance(qn, str) else None
            if hostname_pattern_match and '.' not in qn and len(qn) >= 8:
                from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
                q_lower = qn.lower()
                return {
                    "query": {
                        "bool": {
                            "should": [
                                # Exact matches
                                {"term": {"Switch Hostname.lower": q_lower}},
                                {"term": {"Switch Hostname": qn}},
                                {"term": {"Switch Hostname": qn.upper()}},
                                # Prefix matches (hostname without domain or with domain)
                                {"prefix": {"Switch Hostname.lower": f"{q_lower}"}},
                                {"prefix": {"Switch Hostname": f"{qn}"}},
                                {"prefix": {"Switch Hostname": f"{qn.upper()}"}},
                                # Domain-qualified prefix matches
                                {"prefix": {"Switch Hostname.lower": f"{q_lower}."}},
                                {"prefix": {"Switch Hostname": f"{qn}."}},
                                {"prefix": {"Switch Hostname": f"{qn.upper()}."}},
                            ],
                            "minimum_should_match": 1
                        }
                    },
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        {"Creation Date": {"order": "desc"}},
                        self._preferred_file_sort_clause(),
                        {"_score": {"order": "desc"}}
                    ]
                }

            # Full IPv4 exact-only
            if field == "IP Address" and isinstance(qn, str):
                if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", qn or ""):
                    return {
                        "query": {"bool": {"must": [{"term": {"IP Address.keyword": qn}}]}},
                        "_source": DESIRED_ORDER,
                        "size": size,
                        "sort": [
                            {"Creation Date": {"order": "desc"}},
                            self._preferred_file_sort_clause()
                        ]
                    }

                # Partial IPv4 prefix-only (e.g., "10.216.73." or "192.168.")
                if re.fullmatch(r"\d{1,3}(\.\d{1,3}){0,2}\.??", qn or "") or re.fullmatch(r"\d{1,3}(\.\d{1,3}){0,2}", qn or ""):
                    clean = qn.rstrip('.')
                    # For partial IP, use only prefix to ensure exact prefix matching
                    should = [
                        {"prefix": {"IP Address.keyword": clean}},
                        {"prefix": {"IP Address.keyword": f"{clean}."}},  # Also match with trailing dot
                    ]
                    return {
                        "query": {"bool": {"should": should, "minimum_should_match": 1}},
                        "_source": DESIRED_ORDER,
                        "size": size,
                        "sort": [{"Creation Date": {"order": "desc"}}, {"_score": {"order": "desc"}}]
                    }

            # Serial Number field-specific: support both exact and prefix
            if field == "Serial Number" and isinstance(query, str):
                qsn = query.strip()
                if qsn:
                    # Search in Serial Number AND KEM Serial Number fields
                    logger.info(f"[DEBUG-SERIAL-FIELD] Executing fielded Serial Number query for: {qsn}")
                    return {
                        "query": {"bool": {"should": [
                            {"term": {"Serial Number": qsn}},
                            {"term": {"Serial Number": qsn.upper()}},
                            {"term": {"KEM 1 Serial Number": qsn}},
                            {"term": {"KEM 1 Serial Number": qsn.upper()}},
                            {"term": {"KEM 2 Serial Number": qsn}},
                            {"term": {"KEM 2 Serial Number": qsn.upper()}},
                            {"wildcard": {"Serial Number": f"{qsn}*"}},
                            {"wildcard": {"Serial Number": f"{qsn.upper()}*"}},
                            {"wildcard": {"KEM 1 Serial Number": f"{qsn}*"}},
                            {"wildcard": {"KEM 1 Serial Number": f"{qsn.upper()}*"}},
                            {"wildcard": {"KEM 2 Serial Number": f"{qsn}*"}},
                            {"wildcard": {"KEM 2 Serial Number": f"{qsn.upper()}*"}}
                        ], "minimum_should_match": 1}},
                        "_source": DESIRED_ORDER,
                        "size": size,
                        "sort": [{"Creation Date": {"order": "desc"}}, {"_score": {"order": "desc"}}]
                    }

            # Model Name field-specific: exact match for phone model patterns like CP-8851, DP-9861
            if field == "Model Name" and isinstance(query, str):
                qm = query.strip()
                if qm:
                    # Support both exact model names and partial model searches
                    should_clauses = [
                        {"term": {"Model Name.keyword": qm}},  # Exact match using keyword field
                        {"term": {"Model Name.keyword": qm.upper()}},  # Uppercase variant
                        {"term": {"Model Name.keyword": qm.lower()}},  # Lowercase variant
                        {"match": {"Model Name": qm}},  # Text match for analyzed field
                    ]

                    # If it looks like a model number (contains digits), add wildcard searches
                    if re.search(r'\d', qm):
                        should_clauses.extend([
                            {"wildcard": {"Model Name.keyword": f"CP-{qm}"}},  # CP-prefix
                            {"wildcard": {"Model Name.keyword": f"DP-{qm}"}},  # DP-prefix
                            {"wildcard": {"Model Name.keyword": f"*{qm}*"}},   # Contains
                        ])

                    return {
                        "query": {"bool": {"should": should_clauses, "minimum_should_match": 1}},
                        "_source": DESIRED_ORDER,
                        "size": size,
                        "sort": [
                            # Exact matches first
                            {"_script": {"type": "number", "order": "asc", "script": {
                                "lang": "painless",
                                "source": "def model = doc.containsKey('Model Name') && doc['Model Name'].size()>0 ? doc['Model Name'].value : ''; return model.equals(params.q) ? 0 : 1;",
                                "params": {"q": qm}
                            }}},
                            {"Creation Date": {"order": "desc"}},
                            {"_score": {"order": "desc"}}
                        ]
                    }

            # Field-specific: exact, prefix, wildcard
            # Prefer keyword subfield for exact/prefix/wildcard on certain fields
            eff_field = f"{field}.keyword" if field in ("Line Number", "MAC Address", "MAC Address  2") else field
            should_clauses = [
                {"term": {eff_field: query}},
                {"prefix": {eff_field: query}},
                {"wildcard": {eff_field: f"*{query}*"}}
            ]
            if field == "Line Number" and isinstance(query, str) and query.startswith('+'):
                cleaned = query.lstrip('+')
                if cleaned and not re.fullmatch(r"\d{7,}", cleaned or ""):
                    should_clauses.append({"wildcard": {eff_field: f"*{cleaned}*"}})
            if field in ("MAC Address", "MAC Address 2", "Model Name") and isinstance(query, str) and query.lower() != query.upper():
                should_clauses.append({"wildcard": {eff_field: f"*{query.lower()}*"}})
                should_clauses.append({"wildcard": {eff_field: f"*{query.upper()}*"}})

            fk = None
            if field in ("Line Number", "MAC Address", "MAC Address 2"):
                fk = f"{field}.keyword"

            return {
                "query": {"bool": {"should": should_clauses, "minimum_should_match": 1}},
                "_source": DESIRED_ORDER,
                "size": size,
                "sort": [{
                    "_script": {
                        "type": "number", "order": "asc",
                        "script": {
                            "lang": "painless",
                            "source": "def q = params.q; def f = params.f; def fk = params.fk; if (q == null) return 1; if (fk != null && doc.containsKey(fk) && doc[fk].size()>0 && doc[fk].value == q) return 0; if (doc.containsKey(f) && doc[f].size()>0 && doc[f].value == q) return 0; return 1;",
                            "params": {"q": query, "f": field, "fk": fk}
                        }
                    }
                }, self._preferred_file_sort_clause(), {"Creation Date": {"order": "desc"}}, {"_score": {"order": "desc"}}]
            }

        # General search across all fields
        if isinstance(query, str):
            qn = query.strip()

            # CRITICAL PATTERN ORDER: Switch Hostname patterns MUST be checked BEFORE Serial Number
            # because hostname codes like "ABX01ZSL4750P" (13 chars) would otherwise match serial pattern

            # Switch hostname codes (e.g., ABX01ZSL4750P) - exact match with 13+ characters
            # MUST come first to avoid false serial number matches
            hostname_code_match = re.match(r"^[A-Za-z]{3}[0-9]{2}", qn or "")
            if hostname_code_match and '.' not in qn and len(qn) >= 13:
                from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
                q_lower = qn.lower()
                should_clauses = [
                    {"term": {"Switch Hostname.lower": q_lower}},
                    {"term": {"Switch Hostname": qn}},
                    {"term": {"Switch Hostname": qn.upper()}},
                    {"prefix": {"Switch Hostname.lower": f"{q_lower}."}},
                    {"prefix": {"Switch Hostname": f"{qn}."}},
                    {"prefix": {"Switch Hostname": f"{qn.upper()}."}},
                ]
                return {
                    "query": {
                        "bool": {
                            "should": should_clauses,
                            "minimum_should_match": 1,
                            "filter": [
                                {
                                    "script": {
                                        "script": {
                                            "lang": "painless",
                                            "source": (
                                                "def raw = null; "
                                                "if (doc.containsKey('Switch Hostname') && doc['Switch Hostname'].size()>0) { raw = doc['Switch Hostname'].value; } "
                                                "if (raw == null) { return false; } "
                                                "String norm = raw.trim().toLowerCase(); "
                                                "String q = params.qLower; "
                                                "return norm.equals(q) || norm.startsWith(q + '.');"
                                            ),
                                            "params": {"qLower": q_lower},
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        {"Creation Date": {"order": "desc"}},
                        self._preferred_file_sort_clause(),
                        {"_score": {"order": "desc"}},
                    ]
                }

            # Switch hostname prefix (e.g., Mxx08, ABX01, ABX01ZSL) - exactly 5 characters OR 8-12 with multiple continuing letters
            # Excludes serial-like patterns such as ABC1234, ABC1234X (single letter at end)
            hostname_prefix_match = re.match(r"^[A-Za-z]{3}[0-9]{2}", qn or "")
            # Only treat as hostname prefix if:
            # - Exactly 5 chars (e.g., ABX01, Mxx08), OR
            # - 8+ chars with at least 2 consecutive letters after position 5 (e.g., ABX01ZSL, ABX01ZSL4750)
            # This excludes: ABC1234 (7 chars, only digits after pos 5), ABC1234X (8 chars, only single letter at end)
            is_hostname_prefix = False
            if hostname_prefix_match and '.' not in qn and 5 <= len(qn) < 13:
                if len(qn) == 5:
                    # Exactly 5 characters: always treat as hostname prefix
                    is_hostname_prefix = True
                elif len(qn) >= 8:
                    # 8+ characters: check if there are at least 2 consecutive letters after position 5
                    # This pattern matches hostname suffixes like ZSL, Z, etc. but not single letter serials like X
                    remaining = qn[5:]
                    # Look for at least 2 consecutive letters
                    if re.search(r'[A-Za-z]{2,}', remaining):
                        is_hostname_prefix = True
            if is_hostname_prefix:
                from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
                q_lower = qn.lower()
                q_upper = qn.upper()
                # Prefix search: matches ABX01*, ABX01ZSL*, etc.
                # IMPORTANT: Also search in ALL other fields via multi_match (e.g., Call Manager columns, KEM serials)
                should_clauses = [
                    # High-priority: Switch Hostname field
                    {"prefix": {"Switch Hostname.lower": {"value": q_lower, "boost": 3.0}}},
                    {"prefix": {"Switch Hostname": {"value": qn, "boost": 3.0}}},
                    {"prefix": {"Switch Hostname": {"value": q_upper, "boost": 3.0}}},
                    {"wildcard": {"Switch Hostname.lower": {"value": f"{q_lower}*", "boost": 3.0}}},
                    {"wildcard": {"Switch Hostname": {"value": f"{qn}*", "boost": 3.0}}},
                    {"wildcard": {"Switch Hostname": {"value": f"{q_upper}*", "boost": 3.0}}},
                    # High-priority: KEM Serial Number fields (case-sensitive)
                    {"term": {"KEM 1 Serial Number": qn}},
                    {"term": {"KEM 1 Serial Number": q_upper}},
                    {"term": {"KEM 2 Serial Number": qn}},
                    {"term": {"KEM 2 Serial Number": q_upper}},
                    {"wildcard": {"KEM 1 Serial Number": f"{qn}*"}},
                    {"wildcard": {"KEM 1 Serial Number": f"{q_upper}*"}},
                    {"wildcard": {"KEM 2 Serial Number": f"{qn}*"}},
                    {"wildcard": {"KEM 2 Serial Number": f"{q_upper}*"}},
                    # Also search in ALL fields (e.g., Call Manager Active/Standby Sub, etc.)
                    {"multi_match": {"query": qn, "fields": ["*"], "boost": 1.0, "type": "phrase_prefix"}},
                    {"match_phrase_prefix": {"Call Manager Active Sub": {"query": qn, "boost": 2.0}}},
                    {"match_phrase_prefix": {"Call Manager Standby Sub": {"query": qn, "boost": 2.0}}},
                ]
                return {
                    "query": {
                        "bool": {
                            "should": should_clauses,
                            "minimum_should_match": 1
                        }
                    },
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        {"Creation Date": {"order": "desc"}},
                        self._preferred_file_sort_clause(),
                        {"_score": {"order": "desc"}},
                    ]
                }

            # Serial Number prefix branch: alphanumeric tokens 5-15 chars use prefix wildcards
            # MUST come AFTER hostname patterns to avoid false matches for hostnames
            # Minimum 5 chars to avoid matching short numbers like VLANs (802, 803)
            # Maximum 15 chars covers typical serial number formats (e.g., FVH263803RN = 11 chars, FCH262128N8 = 11 chars)
            # Must contain at least one letter (alphanumeric, not pure digits)
            # Exclude patterns already matched by hostname checks above:
            # - Must NOT be exactly 5 chars with hostname pattern (e.g., "ABX01")
            # - Must NOT be 8+ chars with hostname pattern + 2+ consecutive letters after position 5 (e.g., "ABX01ZSL")
            # - Must NOT be 13+ chars with hostname pattern (e.g., "ABX01ZSL4750P")
            # BUT: "ABC1234" (7 chars), "ABC1234X" (8 chars, single letter) are OK as serials
            # AND: Must NOT be a 12-character hex string (MAC address without separators)

            # Check if this matches a hostname pattern that would have been caught above
            is_hostname_like = False
            if re.match(r"^[A-Za-z]{3}[0-9]{2}", qn or ""):
                qn_len = len(qn or "")
                if qn_len == 5:
                    # Exactly 5 chars - hostname pattern
                    is_hostname_like = True
                elif qn_len >= 13:
                    # 13+ chars - hostname code pattern
                    is_hostname_like = True
                elif qn_len >= 8:
                    # 8-12 chars: only hostname if 2+ consecutive letters after position 5
                    remaining = qn[5:]
                    if re.search(r'[A-Za-z]{2,}', remaining):
                        is_hostname_like = True

            is_likely_serial = (
                re.fullmatch(r"[A-Za-z0-9]{5,15}", qn or "") and
                re.search(r"[A-Za-z]", qn or "") and
                not is_hostname_like and  # Exclude queries that match hostname patterns above
                not (len(qn or "") == 12 and re.fullmatch(r"[A-Fa-f0-9]{12}", qn or ""))  # Exclude 12-hex MACs
            )
            if is_likely_serial:
                from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER

                variants = []
                if qn:
                    variants.append(qn)
                    upper_variant = qn.upper()
                    if upper_variant not in (None, qn) and upper_variant not in variants:
                        variants.append(upper_variant)

                # Search in Serial Number AND KEM Serial Number fields
                wildcard_clauses = []
                for variant in variants:
                    wildcard_clauses.extend([
                        {"wildcard": {"Serial Number": f"{variant}*"}},
                        {"wildcard": {"KEM 1 Serial Number": f"{variant}*"}},
                        {"wildcard": {"KEM 2 Serial Number": f"{variant}*"}},
                    ])

                return {
                    "query": {"bool": {"should": wildcard_clauses, "minimum_should_match": 1}},
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        {"_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "def q = params.q; if (q == null) return 1; if (doc.containsKey('Serial Number') && doc['Serial Number'].size()>0) { def v = doc['Serial Number'].value; if (v != null && (v == q || v.equalsIgnoreCase(q))) { return 0; } } if (doc.containsKey('KEM 1 Serial Number') && doc['KEM 1 Serial Number'].size()>0) { def v = doc['KEM 1 Serial Number'].value; if (v != null && (v == q || v.equalsIgnoreCase(q))) { return 0; } } if (doc.containsKey('KEM 2 Serial Number') && doc['KEM 2 Serial Number'].size()>0) { def v = doc['KEM 2 Serial Number'].value; if (v != null && (v == q || v.equalsIgnoreCase(q))) { return 0; } } return 1;",
                            "params": {"q": qn}
                        }}},
                        {"Creation Date": {"order": "desc"}},
                        self._preferred_file_sort_clause(),
                        {"_score": {"order": "desc"}}
                    ]
                }

            # MAC exact-only when 12-hex provided
            mac_core = re.sub(r"[^A-Fa-f0-9]", "", qn)
            if len(mac_core) == 12:
                canonical_mac = mac_core.upper()
                exact_terms, wildcard_terms = self._mac_query_variants(qn, canonical_mac)
                should_clauses = self._build_mac_should_clauses(exact_terms, wildcard_terms)

                multi_match_queries: List[str] = []
                if canonical_mac:
                    multi_match_queries.append(canonical_mac)
                if isinstance(qn, str):
                    q_stripped = qn.strip()
                    if q_stripped and q_stripped not in multi_match_queries:
                        multi_match_queries.append(q_stripped)

                for mm_query in multi_match_queries:
                    should_clauses.append({"multi_match": {"query": mm_query, "fields": ["*"], "boost": 0.01}})

                return {
                    "query": {"bool": {"should": should_clauses, "minimum_should_match": 1}},
                    "size": size,
                    "sort": [
                        self._preferred_file_sort_clause(),
                        {"Creation Date": {"order": "desc"}}
                    ]
                }

            # 4-digit Model pattern (e.g., "8832", "8851") - search ONLY for exact model matches
            if re.fullmatch(r"\d{4}", qn or ""):
                from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
                return {
                    "query": {"bool": {"should": [
                        # ONLY exact model name matches - no text matches to avoid partial matches
                        {"term": {"Model Name.keyword": f"CP-{qn}"}},
                        {"term": {"Model Name.keyword": f"DP-{qn}"}}
                    ], "minimum_should_match": 1}},
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        # Exact model matches first
                        {"_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "def model = doc.containsKey('Model Name.keyword') && doc['Model Name.keyword'].size()>0 ? doc['Model Name.keyword'].value : ''; return (model.equals('CP-' + params.q) || model.equals('DP-' + params.q)) ? 0 : 1;",
                            "params": {"q": qn}
                        }}},
                        {"Creation Date": {"order": "desc"}},
                        {"_score": {"order": "desc"}}
                    ]
                }

            # Phone number (Line Number) exact-only branch: enforce strict matching
            if re.fullmatch(r"\+?\d{7,15}", qn or ""):
                from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
                cleaned = qn.lstrip('+')
                variants = []
                if qn.startswith('+'):
                    variants.append(qn)
                    if cleaned:
                        variants.append(cleaned)
                else:
                    if qn:
                        variants.append(qn)
                    if cleaned and cleaned != qn:
                        variants.append(f"+{cleaned}")

                should_clauses = [
                    {"term": {"Line Number.keyword": variant}}
                    for variant in variants
                ]

                return {
                    "query": {"bool": {"should": should_clauses, "minimum_should_match": 1}},
                    "_source": DESIRED_ORDER,
                    "size": 1,
                    "sort": [
                        {"_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "def q = params.q; if (q == null) return 1; if (doc.containsKey('Line Number.keyword') && doc['Line Number.keyword'].size()>0 && doc['Line Number.keyword'].value == q) return 0; return 1;",
                            "params": {"q": qn}
                        }}},
                        {"Creation Date": {"order": "desc"}},
                        self._preferred_file_sort_clause(),
                        {"_score": {"order": "desc"}}
                    ]
                }

            # FQDN branch: contains dot and letters (not IP)
            # Support both exact match and wildcard/prefix search across multiple fields
            if (
                any(c.isalpha() for c in qn)
                and "." in qn
                and "/" not in qn
                and " " not in qn
                and not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", qn or "")
            ):
                from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
                q_lower = qn.lower()
                return {
                    "query": {
                        "bool": {
                            "should": [
                                # Exact matches on Switch Hostname (highest priority)
                                {"term": {"Switch Hostname": {"value": qn, "boost": 100.0}}},
                                {"term": {"Switch Hostname.lower": {"value": q_lower, "boost": 100.0}}},
                                # Wildcard matches on Switch Hostname
                                {"wildcard": {"Switch Hostname.lower": {"value": f"*{q_lower}*", "boost": 50.0}}},
                                {"wildcard": {"Switch Hostname": {"value": f"*{qn}*", "boost": 50.0}}},
                                # Also search across other text fields via multi_match
                                {"multi_match": {"query": qn, "fields": ["*"], "boost": 10.0}},
                                # Specific field wildcards for common FQDN locations
                                {"wildcard": {"IP Address.keyword": f"*{qn}*"}},
                                {"wildcard": {"Line Number.keyword": f"*{qn}*"}},
                                {"wildcard": {"Model Name": f"*{qn}*"}},
                            ],
                            "minimum_should_match": 1
                        }
                    },
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        # Exact Switch Hostname matches first
                        {"_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "def q = params.q; def ql = params.ql; if (doc.containsKey('Switch Hostname') && doc['Switch Hostname'].size()>0) { def v = doc['Switch Hostname'].value; if (v != null && (v.equals(q) || v.toLowerCase().equals(ql))) { return 0; } } return 1;",
                            "params": {"q": qn, "ql": q_lower}
                        }}},
                        {"Creation Date": {"order": "desc"}},
                        self._preferred_file_sort_clause(),
                        {"_score": {"order": "desc"}}
                    ]
                }

            # IP Address search: full or partial IPv4
            # Full IPv4: 10.216.10.7 (4 octets) - exact match only
            # Partial IPv4: 10.216.10 or 10.216 (1-3 octets) - prefix match
            # IMPORTANT: Must contain at least one dot to be treated as IP address (avoids matching VLANs like "802")
            if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", qn or ""):
                # Full IPv4 address - exact match first, then prefix
                from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
                return {
                    "query": {"bool": {"should": [
                        {"term": {"IP Address.keyword": {"value": qn, "boost": 100.0}}},
                        {"prefix": {"IP Address.keyword": {"value": qn, "boost": 10.0}}}
                    ], "minimum_should_match": 1}},
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        {"_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "def q = params.q; if (q == null) return 1; if (doc.containsKey('IP Address.keyword') && doc['IP Address.keyword'].size()>0 && doc['IP Address.keyword'].value == q) return 0; if (doc.containsKey('IP Address.keyword') && doc['IP Address.keyword'].size()>0 && doc['IP Address.keyword'].value.startsWith(q)) return 1; return 2;",
                            "params": {"q": qn}
                        }}},
                        {"Creation Date": {"order": "desc"}},
                        self._preferred_file_sort_clause(),
                        {"_score": {"order": "desc"}}
                    ]
                }
            elif "." in qn and re.fullmatch(r"\d{1,3}(\.\d{1,3}){0,2}\.?", qn or ""):
                # Partial IPv4 address - prefix match only
                # MUST contain at least one dot to avoid matching pure numbers like "802" (Voice VLAN)
                from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
                clean_query = qn.rstrip('.')
                return {
                    "query": {"bool": {"should": [
                        {"prefix": {"IP Address.keyword": clean_query}},
                        {"prefix": {"IP Address.keyword": f"{clean_query}."}}
                    ], "minimum_should_match": 1}},
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        {"_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "def q = params.q; if (q == null) return 1; if (doc.containsKey('IP Address.keyword') && doc['IP Address.keyword'].size()>0 && doc['IP Address.keyword'].value.startsWith(q)) return 0; return 1;",
                            "params": {"q": clean_query}
                        }}},
                        {"Creation Date": {"order": "desc"}},
                        self._preferred_file_sort_clause(),
                        {"_score": {"order": "desc"}}
                    ]
                }

            # Voice VLAN search: 3-digit numbers are likely VLAN IDs (e.g., 802, 803, 801)
            if re.fullmatch(r"\d{3}", qn or ""):
                from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
                return {
                    "query": {"term": {"Voice VLAN": qn}},
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        {"Creation Date": {"order": "desc"}},
                        self._preferred_file_sort_clause(),
                        {"_score": {"order": "desc"}}
                    ]
                }

        # Broad query: allow partials but with exact-first sort
        # ALWAYS include multi_match for comprehensive search across ALL fields
        is_hostname_pattern = isinstance(query, str) and len(query) >= 5 and re.match(r'^[A-Za-z]{3}[0-9]{2}', query)

        file_name_boost_clauses = [
            {"term": {"File Name": {"value": name, "boost": 2.0}}}
            for name in preferred_files[:5]
        ]


        # Multi-field search: BALANCED approach for performance and precision
        # For short queries (like VLANs), prefer exact matches to avoid false positives
        # For longer queries, use wildcards for flexible matching
        is_short_numeric = isinstance(query, str) and query.isdigit() and len(query) <= 4

        should_clauses = [
            # High-priority exact matches for common fields
            {"term": {"Voice VLAN": {"value": query, "boost": 10.0}}},
            {"term": {"Subnet Mask": {"value": query, "boost": 10.0}}},
            {"term": {"Switch Port": {"value": query, "boost": 10.0}}},
            {"term": {"Serial Number": {"value": query, "boost": 10.0}}},
            {"term": {"KEM 1 Serial Number": {"value": query, "boost": 10.0}}},  # Already keyword type, no .keyword needed
            {"term": {"KEM 2 Serial Number": {"value": query, "boost": 10.0}}},  # Already keyword type, no .keyword needed
            {"term": {"Model Name.keyword": {"value": query, "boost": 10.0}}},
            {"term": {"Switch Hostname": {"value": query, "boost": 10.0}}},
            {"term": {"Switch Hostname.lower": {"value": str(query).lower(), "boost": 10.0}}},
            *file_name_boost_clauses,

            # Multi-match for ALL text fields (Call Manager, IP Address, etc.)
            {"multi_match": {
                "query": query,
                "fields": ["*"],
                "type": "phrase_prefix",
                "boost": 5.0
            }},
        ]

        # For short numeric queries (VLANs, port numbers): use targeted wildcard only on specific fields
        if is_short_numeric:
            should_clauses.extend([
                {"wildcard": {"Switch Port": f"*{query}*"}},
                {"wildcard": {"Phone Port Speed": f"*{query}*"}},
                {"wildcard": {"PC Port Speed": f"*{query}*"}},
            ])
        else:
            # For longer queries: use query_string for comprehensive matching across ALL fields
            # Using "*" automatically includes new columns without code changes
            should_clauses.append({
                "query_string": {
                    "query": f"*{query}*",
                    "fields": ["*"],  # Search ALL fields automatically (including new CSV columns)
                    "boost": 3.0,
                    "analyze_wildcard": True
                }
            })

        # Additional MAC address exact matches
        should_clauses.extend([
            {"term": {"MAC Address.keyword": {"value": str(query).upper(), "boost": 8.0}}},
            {"term": {"MAC Address 2.keyword": {"value": str(query).upper(), "boost": 8.0}}},
        ])

        search_query = {
            "query": {
                "bool": {
                    "should": should_clauses,
                    "minimum_should_match": 1
                }
            },
            "size": size
        }

        # Strengthen MAC exact matches
        try:
            search_query["query"]["bool"]["should"].append({"term": {"MAC Address.keyword": query}})
            search_query["query"]["bool"]["should"].append({"term": {"MAC Address 2.keyword": query}})
            if isinstance(query, str) and len(query) >= 12:
                sep_variant = f"SEP{str(query).upper()}"
                search_query["query"]["bool"]["should"].append({"term": {"MAC Address 2.keyword": sep_variant}})
        except Exception as e:
            logger.warning(f"Failed to add strengthened MAC keyword terms: {e}")



        # Long numeric substring: add plus-prefixed exact variant
        if isinstance(query, str) and query.isdigit() and len(query) >= 5:
            try:
                pref_variant = f"+{query}"
                search_query["query"]["bool"]["should"].append({"term": {"Line Number.keyword": pref_variant}})
            except Exception as e:
                logger.warning(f"Failed to append plus-prefixed numeric variant for query '{query}': {e}")

        # MAC core wildcards for condensed entries
        if isinstance(query, str) and any(c.isalpha() for c in query) and len(query.replace(':','').replace('-','').replace('.','')) >= 6:
            mac_core = re.sub(r'[^A-Fa-f0-9]', '', query)
            if mac_core:
                try:
                    search_query["query"]["bool"]["should"].append({"wildcard": {"MAC Address.keyword": f"*{mac_core.lower()}*"}})
                    search_query["query"]["bool"]["should"].append({"wildcard": {"MAC Address.keyword": f"*{mac_core.upper()}*"}})
                    search_query["query"]["bool"]["should"].append({"wildcard": {"MAC Address 2.keyword": f"*{mac_core.lower()}*"}})
                    search_query["query"]["bool"]["should"].append({"wildcard": {"MAC Address 2.keyword": f"*{mac_core.upper()}*"}})
                except Exception as e:
                    logger.warning(f"Failed to add MAC core variants for '{query}': {e}")

        # Note: Switch Hostname patterns are handled by early return logic above

        # Hostname dotted-segment fallback (excluded if already handled by hostname pattern logic)
        if isinstance(query, str) and '.' in query and any(c.isalpha() for c in query):
            try:
                parts = [p for p in query.split('.') if p]
                if len(parts) >= 2:
                    short = parts[0]
                    # Skip if this looks like a hostname pattern (3 letters + 2 digits)
                    if not (len(short) >= 5 and re.match(r'^[A-Za-z]{3}[0-9]{2}', short)):
                        search_query["query"]["bool"]["should"].append({"wildcard": {"Switch Hostname": f"*{short.lower()}*"}})
                        search_query["query"]["bool"]["should"].append({"wildcard": {"Switch Hostname": f"*{short.upper()}*"}})
            except Exception as e:
                logger.warning(f"Failed to add hostname short variants for '{query}': {e}")

        # Alphanumeric model name variants
        if isinstance(query, str) and any(c.isalpha() for c in query) and any(c.isdigit() for c in query):
            try:
                search_query["query"]["bool"]["should"].append({"wildcard": {"Model Name": f"*{str(query).lower()}*"}})
                search_query["query"]["bool"]["should"].append({"wildcard": {"Model Name": f"*{str(query).upper()}*"}})
            except Exception as e:
                logger.warning(f"Failed to add model name variants for '{query}': {e}")

        # Return all fields from OpenSearch instead of limiting to DEFAULT_DISPLAY_ORDER
        # This allows filter_display_columns to work with complete data
        # search_query["_source"] is intentionally not set - returns all fields

        search_query["sort"] = [
            {"_script": {"type": "number", "order": "asc", "script": {
                "lang": "painless",
                "source": "def q = params.q; if (q == null) return 1; if (doc.containsKey('Switch Port') && doc['Switch Port'].size()>0 && doc['Switch Port'].value == q) return 0; if (doc.containsKey('Line Number.keyword') && doc['Line Number.keyword'].size()>0 && doc['Line Number.keyword'].value == q) return 0; if (doc.containsKey('MAC Address.keyword') && doc['MAC Address.keyword'].size()>0 && doc['MAC Address.keyword'].value == q) return 0; if (doc.containsKey('MAC Address 2.keyword') && doc['MAC Address 2.keyword'].size()>0 && doc['MAC Address 2.keyword'].value == q) return 0; if (doc.containsKey('IP Address.keyword') && doc['IP Address.keyword'].size()>0 && doc['IP Address.keyword'].value == q) return 0; if (doc.containsKey('Serial Number') && doc['Serial Number'].size()>0 && doc['Serial Number'].value == q) return 0; return 1;",
                "params": {"q": query}
            }}},
            {"Creation Date": {"order": "desc"}},
            self._preferred_file_sort_clause(),
            {"_score": {"order": "desc"}}
        ]

        return search_query

    def _build_headers_from_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Build headers list - ALWAYS returns all available columns, not just those in current results.

        This ensures consistent column display regardless of search results content.
        Uses DEFAULT_DISPLAY_ORDER + Call Manager fields as the authoritative column list.
        """
        from utils.csv_utils import DEFAULT_DISPLAY_ORDER

        # Collect all keys that actually exist in documents (for validation)
        doc_keys = set()
        for doc in documents:
            doc_keys.update(doc.keys())

        # Order headers: metadata fields first, then all other columns alphabetically
        metadata_fields = ["#", "File Name", "Creation Date"]

        # Start with metadata fields (always include these)
        headers = metadata_fields.copy()

        # Add ALL data columns from DEFAULT_DISPLAY_ORDER (excluding metadata we already added)
        data_columns = [col for col in DEFAULT_DISPLAY_ORDER if col not in metadata_fields]

        # Ensure KEM serial number columns are always present in headers
        kem_fields = ["KEM 1 Serial Number", "KEM 2 Serial Number"]
        for kem in kem_fields:
            if kem not in data_columns:
                # Prefer inserting KEM fields after Model Name when present
                try:
                    idx = data_columns.index("Model Name") + 1
                except ValueError:
                    idx = len(data_columns)
                data_columns.insert(idx, kem)

        # Sort remaining data columns alphabetically for consistency while keeping KEM placement
        # We'll keep KEM fields near Model Name by removing them, sorting, then reinserting
        kem_present = [c for c in data_columns if c in kem_fields]
        other_columns = [c for c in data_columns if c not in kem_fields]
        other_columns.sort()
        data_columns = other_columns + kem_present
        headers.extend(data_columns)

        # Add any additional columns from documents that aren't in DEFAULT_DISPLAY_ORDER
        # (this handles new columns added to CSV format)
        extra_columns = sorted([col for col in doc_keys if col not in headers])
        headers.extend(extra_columns)

        return headers

    def _normalize_mac(self, q: Optional[str]) -> Optional[str]:
        """
        Normalize user input into canonical 12-hex MAC (uppercase).

        Args:
            q: Query string that might be a MAC address

        Returns:
            Optional[str]: Normalized MAC address or None if invalid
        """
        if not isinstance(q, str) or not q:
            return None
        s = q.strip()
        # Strip optional Cisco SEP prefix (case-insensitive) with optional separator
        s = re.sub(r'(?i)^sep[-_:]?', '', s)
        # Remove all non-hex characters (handle '-', ':', '.')
        core = re.sub(r'[^0-9A-Fa-f]', '', s)
        if len(core) == 12:
            # Treat as MAC only if it likely is one: contains hex letters or had MAC separators or SEP prefix
            if re.search(r'[A-Fa-f]', q) or re.search(r'[:\-\.]', q) or re.match(r'(?i)^\s*sep', q.strip()):
                return core.upper()
        return None

    def _mac_query_variants(
        self,
        raw_query: Optional[str],
        canonical_mac: Optional[str]
    ) -> Tuple[List[str], List[str]]:
        """Build exact and wildcard-friendly variants for MAC address searches."""
        candidates: List[str] = []

        def _add(value: Optional[str]) -> None:
            if not value:
                return
            candidate = value.strip()
            if candidate:
                candidates.append(candidate)

        if canonical_mac:
            mac_up = canonical_mac.upper()
            _add(mac_up)
            _add(f"SEP{mac_up}")

            # Common separator formats: colon, hyphen, Cisco dotted
            pairs = [mac_up[i:i + 2] for i in range(0, 12, 2)]
            colon_variant = ":".join(pairs)
            hyphen_variant = "-".join(pairs)
            dotted_variant = ".".join([mac_up[i:i + 4] for i in range(0, 12, 4)])

            _add(colon_variant)
            _add(colon_variant.upper())
            _add(colon_variant.lower())
            _add(hyphen_variant)
            _add(hyphen_variant.upper())
            _add(hyphen_variant.lower())
            _add(dotted_variant)
            _add(dotted_variant.upper())
            _add(dotted_variant.lower())

            _add(f"SEP{colon_variant}")
            _add(f"SEP{hyphen_variant}")
            _add(f"SEP{dotted_variant}")

        if isinstance(raw_query, str):
            stripped = raw_query.strip()
            _add(stripped)
            upper = stripped.upper()
            lower = stripped.lower()
            if upper != stripped:
                _add(upper)
            if lower != stripped:
                _add(lower)

        # Deduplicate while preserving order
        seen_exact: set[str] = set()
        exact_terms: List[str] = []
        for candidate in candidates:
            if candidate not in seen_exact:
                seen_exact.add(candidate)
                exact_terms.append(candidate)

        seen_wildcard: set[str] = set()
        wildcard_terms: List[str] = []
        for term in exact_terms:
            if term not in seen_wildcard:
                seen_wildcard.add(term)
                wildcard_terms.append(term)

        return exact_terms, wildcard_terms

    def _build_mac_should_clauses(
        self,
        exact_terms: List[str],
        wildcard_terms: List[str]
    ) -> List[Dict[str, Any]]:
        """Construct shared MAC address should clauses for query bodies."""
        clauses: List[Dict[str, Any]] = []
        non_sep_exact = [t for t in exact_terms if not t.upper().startswith("SEP")]
        for term in non_sep_exact:
            clauses.append({"term": {"MAC Address.keyword": term}})
        for term in exact_terms:
            clauses.append({"term": {"MAC Address 2.keyword": term}})

        non_sep_wildcards = [t for t in wildcard_terms if not t.upper().startswith("SEP")]
        for term in non_sep_wildcards:
            clauses.append({"wildcard": {"MAC Address.keyword": f"*{term}*"}})
        for term in wildcard_terms:
            clauses.append({"wildcard": {"MAC Address 2.keyword": f"*{term}*"}})
        return clauses

    def _seed_mac_shortcut(self, query: str, preferred_files: List[str]) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
        """Seed results for MAC-address-like queries against the current index."""
        canonical_mac: Optional[str]
        looks_like_mac = False
        try:
            canonical_mac = self._normalize_mac(query)
            looks_like_mac = canonical_mac is not None
        except Exception:
            canonical_mac = None
            looks_like_mac = False

        seeded_documents: List[Dict[str, Any]] = []
        if not looks_like_mac or not canonical_mac:
            return looks_like_mac, canonical_mac, seeded_documents

        try:
            curr_indices = self.get_search_indices(False)
            must_clauses: List[Dict[str, Any]] = []
            if preferred_files:
                must_clauses.append({"terms": {"File Name": preferred_files[:5]}})

            exact_terms, wildcard_terms = self._mac_query_variants(query, canonical_mac)
            should_clauses = self._build_mac_should_clauses(exact_terms, wildcard_terms)

            targeted = {
                "query": {
                    "bool": {
                        "must": must_clauses,
                        "should": should_clauses,
                        "minimum_should_match": 1,
                    }
                },
                "size": 200,
            }
            logger.info(f"[MAC-first] indices={curr_indices} body={targeted}")
            resp = self.client.search(index=curr_indices, body=targeted)
            seeded_documents = [h.get('_source', {}) for h in resp.get('hits', {}).get('hits', [])]

            if not seeded_documents:
                try:
                    fallback_body = targeted.copy()
                    fb_query = fallback_body.get('query', {}).get('bool', {})
                    if isinstance(fb_query, dict) and 'must' in fb_query:
                        fb_query.pop('must', None)
                        logger.info("[MAC-first] primary query empty, retrying without File Name must-clause")
                        resp_fb = self.client.search(index=curr_indices, body=fallback_body)
                        seeded_documents = [h.get('_source', {}) for h in resp_fb.get('hits', {}).get('hits', [])]
                except Exception as fb_exc:
                    logger.debug(f"[MAC-first] fallback without must failed: {fb_exc}")

            if seeded_documents:
                logger.info(f"[MAC-first] seeded {len(seeded_documents)} docs from current index")
        except Exception as exc:
            logger.warning(f"[MAC-first] current-index search failed: {exc}")

        return looks_like_mac, canonical_mac, seeded_documents

    def _attempt_phone_shortcut(
        self,
        query: str,
        include_historical: bool,
        size: int,
    ) -> Optional[Tuple[List[str], List[Dict[str, Any]]]]:
        """Handle phone-number-like queries with targeted shortcuts."""
        try:
            qn_phone = query.strip() if isinstance(query, str) else None
            looks_like_phone = bool(qn_phone and re.fullmatch(r"\+?\d{7,}", qn_phone))
        except Exception:
            looks_like_phone = False
            qn_phone = None

        if not looks_like_phone or not qn_phone:
            return None

        try:
            if qn_phone.startswith('+'):
                digits = qn_phone.lstrip('+')
                candidates = [qn_phone]
                if digits:
                    candidates.append(digits)
            else:
                digits = qn_phone
                candidates = [digits, f"+{digits}"] if digits else []

            from utils.csv_utils import DEFAULT_DISPLAY_ORDER as desired_order

            if include_historical:
                netspeed_files = self._netspeed_filenames()
                results: List[Dict[str, Any]] = []
                for fname in netspeed_files:
                    try:
                        seed_body = {
                            "query": {
                                "bool": {
                                    "must": [{"term": {"File Name": fname}}],
                                    "should": [{"term": {"Line Number.keyword": cand}} for cand in candidates],
                                    "minimum_should_match": 1,
                                }
                            },
                            "_source": desired_order,
                            "size": 1,
                        }
                        resp = self.client.search(index=self.get_search_indices(True), body=seed_body)
                        hit = next((h.get('_source', {}) for h in resp.get('hits', {}).get('hits', [])), None)
                        if hit:
                            results.append(hit)
                    except Exception as seed_exc:
                        logger.debug(f"[PHONE] per-file seed failed for {fname}: {seed_exc}")
                return self._build_headers_from_documents(results), results

            indices = self.get_search_indices(False)
            phone_body_exact = {
                "query": {
                    "bool": {
                        "should": [{"term": {"Line Number.keyword": cand}} for cand in candidates],
                        "minimum_should_match": 1,
                    }
                },
                "size": 1,
            }
            logger.info(f"[PHONE-exact] indices={indices} body={phone_body_exact}")
            resp_phone = self.client.search(index=indices, body=phone_body_exact)
            phone_hit = next((h.get('_source', {}) for h in resp_phone.get('hits', {}).get('hits', [])), None)
            if phone_hit:
                return self._build_headers_from_documents([phone_hit]), [phone_hit]

            digits = qn_phone.lstrip('+')
            if digits:
                phone_body_partial = {
                    "query": {
                        "bool": {
                            "should": [
                                {"wildcard": {"Line Number.keyword": f"*{digits}*"}},
                                {"wildcard": {"Line Number.keyword": f"*+{digits}*"}},
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                    "size": max(size, 20000),
                    "sort": [{"Creation Date": {"order": "desc"}}],
                }
                logger.info(f"[PHONE-partial] indices={indices} body={phone_body_partial}")
                resp_part = self.client.search(index=indices, body=phone_body_partial)
                docs_part = [h.get('_source', {}) for h in resp_part.get('hits', {}).get('hits', [])]
                docs_part = self._deduplicate_documents_preserve_order(docs_part)
                return self._build_headers_from_documents(docs_part), docs_part

            return ([], [])
        except Exception as exc:
            logger.warning(f"Phone exact search failed, falling back to general: {exc}")
            return None

    def _attempt_serial_shortcut(
        self,
        query: str,
        include_historical: bool,
        size: int,
        skip_due_to_mac: bool,
    ) -> Optional[Tuple[List[str], List[Dict[str, Any]]]]:
        """Handle serial-number-like queries with targeted shortcuts."""
        try:
            qn_sn = query.strip() if isinstance(query, str) else None
            basic_serial_pattern = bool(qn_sn and re.fullmatch(r"[A-Za-z0-9]{8,}", qn_sn))
            not_all_digits = bool(qn_sn and not re.fullmatch(r"\d{8,}", qn_sn))
            looks_like_serial = False
            if basic_serial_pattern and not_all_digits:
                hostname_pattern = bool(re.match(r'^[A-Za-z]{3}[0-9]{2}', qn_sn))
                if hostname_pattern and len(qn_sn) >= 8:
                    remaining = qn_sn[5:]
                    looks_like_serial = not bool(re.search(r'[A-Za-z]{2,}', remaining))
                else:
                    looks_like_serial = True
            else:
                looks_like_serial = False
        except Exception:
            qn_sn = None
            looks_like_serial = False

        if skip_due_to_mac or not looks_like_serial or not qn_sn:
            return None

        try:
            variants = [qn_sn]
            upper_variant = qn_sn.upper()
            if upper_variant != qn_sn:
                variants.append(upper_variant)

            from utils.csv_utils import DEFAULT_DISPLAY_ORDER as desired_order
            indices = self.get_search_indices(include_historical)
            indices_list = indices if isinstance(indices, list) else [indices]
            allow_archive = any(idx == self.archive_index for idx in indices_list)
            allow_historical = bool(include_historical)

            should_clauses: List[Dict[str, Any]] = []
            for variant in variants:
                should_clauses.extend([
                    {"term": {"Serial Number": variant}},
                    {"term": {"KEM 1 Serial Number": variant}},
                    {"term": {"KEM 2 Serial Number": variant}},
                ])

            if len(qn_sn) >= 3:
                for variant in variants:
                    should_clauses.extend([
                        {"wildcard": {"Serial Number": f"{variant}*"}},
                        {"wildcard": {"KEM 1 Serial Number": f"{variant}*"}},
                        {"wildcard": {"KEM 2 Serial Number": f"{variant}*"}},
                    ])

            body = {
                "query": {"bool": {"should": should_clauses, "minimum_should_match": 1}},
                "_source": desired_order,
                "size": size if include_historical else 20000,
                "sort": [
                    {"Creation Date": {"order": "desc"}},
                    self._preferred_file_sort_clause(),
                    {"_score": {"order": "desc"}},
                ],
            }
            logger.info(f"[SERIAL] indices={indices} body={body}")
            resp = self.client.search(index=indices, body=body)
            docs = [h.get('_source', {}) for h in resp.get('hits', {}).get('hits', [])]

            def _is_allowed_file(fn: str) -> bool:
                if not fn:
                    return False
                if fn == 'netspeed.csv':
                    return True
                if re.match(r'^netspeed_\d{8}-\d{6}\.csv$', fn):
                    return True
                if allow_historical:
                    if fn.startswith('netspeed.csv.'):
                        suf = fn.split('netspeed.csv.', 1)[1]
                        return suf.isdigit()
                    if re.match(r'^netspeed_\d{8}-\d{6}\.csv\.\d+$', fn):
                        return True
                if allow_archive and fn.startswith('netspeed_'):
                    return True
                return False

            docs = [d for d in docs if _is_allowed_file((d.get('File Name') or '').strip())]

            if include_historical:
                seen_files: set[str] = set()
                dedup_by_file: List[Dict[str, Any]] = []
                for doc in docs:
                    fname = (doc.get('File Name') or '').strip()
                    if not fname or fname in seen_files:
                        continue
                    seen_files.add(fname)
                    dedup_by_file.append(doc)
                docs = dedup_by_file

            return self._build_headers_from_documents(docs), docs
        except Exception as exc:
            logger.warning(f"Serial exact search failed, falling back to general: {exc}")
            return None

    def _attempt_hostname_shortcut(
        self,
        query: str,
        include_historical: bool,
        skip_due_to_mac: bool,
        size: int,
    ) -> Optional[Tuple[List[str], List[Dict[str, Any]]]]:
        """Handle hostname/FQDN queries before general search."""
        try:
            qn_hn = query.strip() if isinstance(query, str) else None
            looks_like_hostname = bool(
                qn_hn
                and '.' in qn_hn
                and any(c.isalpha() for c in qn_hn)
                and '/' not in qn_hn
                and ' ' not in qn_hn
                and not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", qn_hn)
            )
        except Exception:
            qn_hn = None
            looks_like_hostname = False

        if skip_due_to_mac or not looks_like_hostname or not qn_hn:
            return None

        try:
            from utils.csv_utils import DEFAULT_DISPLAY_ORDER as desired_order
            indices = self.get_search_indices(include_historical)
            indices_list = indices if isinstance(indices, list) else [indices]
            allow_archive = any(idx == self.archive_index for idx in indices_list)
            allow_historical = bool(include_historical)

            body = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "script": {
                                    "script": {
                                        "lang": "painless",
                                        "source": "def v = null; if (doc.containsKey('Switch Hostname') && doc['Switch Hostname'].size()>0) { v = doc['Switch Hostname'].value; } else { return false; } if (v == null) return false; return v.trim().equalsIgnoreCase(params.q.trim());",
                                        "params": {"q": qn_hn},
                                    }
                                }
                            }
                        ],
                        "should": [
                            {"term": {"Switch Hostname": qn_hn}},
                            {"term": {"Switch Hostname.lower": qn_hn.lower()}},
                        ],
                        "minimum_should_match": 0,
                    }
                },
                "_source": desired_order,
                "size": size,
                "sort": [
                    {"Creation Date": {"order": "desc"}},
                    self._preferred_file_sort_clause(),
                ],
            }

            resp = self.client.search(index=indices, body=body)
            docs = [h.get('_source', {}) for h in resp.get('hits', {}).get('hits', [])]

            def _is_allowed_file(fn: str) -> bool:
                if not fn:
                    return False
                if fn == 'netspeed.csv':
                    return True
                if allow_historical and fn.startswith('netspeed.csv.'):
                    suf = fn.split('netspeed.csv.', 1)[1]
                    return suf.isdigit()
                if allow_archive and fn.startswith('netspeed_'):
                    return True
                return False

            docs = [d for d in docs if _is_allowed_file((d.get('File Name') or '').strip())]
            return self._build_headers_from_documents(docs), docs
        except Exception as exc:
            logger.warning(f"Hostname exact search failed, falling back to general: {exc}")
            return None

    def search(self, query: str, field: Optional[str] = None, include_historical: bool = False,
              size: int = 20000) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Search OpenSearch for documents matching the query.

        Args:
            query: Query string
            field: Optional field to search in (if None, searches across all fields)
            include_historical: Whether to include historical indices
            size: Maximum number of results to return

        Returns:
            Tuple[List[str], List[Dict[str, Any]]]: (headers, matching documents)
        """
        try:
            preferred_files = self._preferred_file_names()
            # Prepare containers for documents
            documents: List[Dict[str, Any]] = []

            looks_like_mac_first, canonical_mac, mac_seed_docs = self._seed_mac_shortcut(query, preferred_files)
            effective_include_historical = bool(include_historical or looks_like_mac_first)
            if mac_seed_docs:
                documents.extend(mac_seed_docs)

            phone_result = self._attempt_phone_shortcut(query, effective_include_historical if looks_like_mac_first else include_historical, size)
            if phone_result is not None:
                return phone_result

            serial_result = self._attempt_serial_shortcut(query, effective_include_historical, size, looks_like_mac_first)
            if serial_result is not None:
                return serial_result

            hostname_result = self._attempt_hostname_shortcut(query, effective_include_historical, looks_like_mac_first, size)
            if hostname_result is not None:
                return hostname_result

            # Now run the general search across the selected indices
            # For MAC-like queries, always include historical indices to list results from all netspeed.csv files
            indices = self.get_search_indices(effective_include_historical)
            # For MAC-like queries we must always search all netspeed indices (current + historical).
            # Use a wildcard index pattern to avoid depending on any cached or environment-specific
            # index enumeration which may occasionally omit historical rotation indices after restarts.
            if looks_like_mac_first:
                try:
                    indices = ["netspeed_*"]
                    logger.info("MAC-like query detected: forcing indices to ['netspeed_*'] to include all historical netspeed indices")
                except Exception as _e:
                    logger.debug(f"Could not force netspeed_* wildcard indices for MAC query: {_e}")

            # Removed: hostname prefix override - respect user's include_historical flag
            indices_list = indices if isinstance(indices, list) else [indices]
            allow_archive_files_general = any(idx == self.archive_index for idx in indices_list)
            allow_historical_files_general = bool(effective_include_historical)
            if allow_archive_files_general and size > 10000:
                logger.info(
                    "Clamping search size from %s to 10000 for archive_netspeed compatibility",
                    size,
                )
                size = 10000

            # Check if this is a KEM search - optimize performance but return ALL results
            is_kem_search = isinstance(query, str) and query.upper().strip() == "KEM"

            # Use canonical MAC inside the general body for MAC queries
            qb_query = str(canonical_mac) if looks_like_mac_first and canonical_mac else query
            if looks_like_mac_first:
                size = max(200, len(preferred_files) * 3)

            query_body = self._build_query_body(qb_query, field, size)

            logger.info(f"Search query: indices={indices}, query={query_body}")
            response = self.client.search(index=indices, body=query_body)
            logger.info(f"Search response: {response}")
            hits = response.get("hits", {}).get("hits", [])
            documents.extend([hit.get("_source", {}) for hit in hits])

            # Reduce noisy debug logging used during testing
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Raw documents sample: %s", [
                    {
                        'file': d.get('File Name'),
                        'date': d.get('Creation Date'),
                        'mac': d.get('MAC Address')
                    } for d in documents[:5]
                ])

            # Deduplicate documents while preserving sort order
            # Skip expensive deduplication for KEM searches to improve performance
            if is_kem_search:
                unique_documents = documents
                logger.info("Skipping deduplication for KEM search to improve performance")
            else:
                unique_documents = self._deduplicate_documents_preserve_order(documents)

            # Always restrict results to canonical netspeed files only:
            # - netspeed.csv (legacy current file)
            # - netspeed_YYYYMMDD-HHMMSS.csv (new current file format with timestamp)
            # - netspeed.csv.N (historical rotation files) - only if include_historical=True
            # - netspeed_YYYYMMDD-HHMMSS.csv.N (timestamped rotation files) - only if include_historical=True
            # - archive files - only if querying archive index
            def _is_allowed_file(fn: str) -> bool:
                if not fn:
                    return False
                # Always allow legacy current file name
                if fn == 'netspeed.csv':
                    return True
                # Always allow new timestamped format (current file without rotation suffix)
                if fn.startswith('netspeed_') and fn.endswith('.csv'):
                    # Check if it matches timestamp format: netspeed_YYYYMMDD-HHMMSS.csv
                    import re
                    if re.match(r'^netspeed_\d{8}-\d{6}\.csv$', fn):
                        return True
                    # Or from archive index
                    if allow_archive_files_general:
                        return True
                # Historical rotation files only if include_historical=True
                if allow_historical_files_general:
                    # Legacy rotation: netspeed.csv.N
                    if fn.startswith('netspeed.csv.'):
                        suf = fn.split('netspeed.csv.', 1)[1]
                        return suf.isdigit()
                    # Timestamped rotation: netspeed_YYYYMMDD-HHMMSS.csv.N
                    if fn.startswith('netspeed_'):
                        import re
                        if re.match(r'^netspeed_\d{8}-\d{6}\.csv\.\d+$', fn):
                            return True
                return False

            before_cnt = len(unique_documents)
            unique_documents = [d for d in unique_documents if _is_allowed_file((d.get('File Name') or '').strip())]
            after_cnt = len(unique_documents)
            if after_cnt != before_cnt:
                logger.info(f"Filtered out {before_cnt - after_cnt} non-canonical files (kept netspeed.csv and netspeed.csv.N only)")

            # (Removed) Hostname deduplication: return all exact matches for a host

            if looks_like_mac_first:
                try:
                    preferred_map = {name: idx for idx, name in enumerate(self._preferred_file_names())}

                    def _doc_sort_key(doc: Dict[str, Any]) -> tuple[int, float, int]:
                        fname = (doc.get("File Name") or "").strip()
                        weight = preferred_map.get(fname, len(preferred_map))
                        date_str = (doc.get("Creation Date") or "").strip()
                        try:
                            ts = datetime.strptime(date_str, "%Y-%m-%d").timestamp()
                        except Exception:
                            ts = 0.0
                        # Prefer newer dates (descending) by negating timestamp
                        return (weight, -ts, 0)

                    unique_documents = sorted(unique_documents, key=_doc_sort_key)
                except Exception as ordering_exc:
                    logger.debug(f"MAC result reordering failed: {ordering_exc}")

            # For MAC-like searches, ensure at least one matching document per netspeed file present in the data root
            # This guarantees all netspeed.csv* files show up in the results list
            try:
                mac_core_seed = canonical_mac
                looks_like_mac_seed = mac_core_seed is not None
            except Exception:
                looks_like_mac_seed = False
            if looks_like_mac_seed and effective_include_historical:
                try:
                    exact_terms_seed, wildcard_terms_seed = self._mac_query_variants(query, mac_core_seed)
                    should_seed = self._build_mac_should_clauses(exact_terms_seed, wildcard_terms_seed)
                    netspeed_files = self._netspeed_filenames()

                    # Determine which file names are already present in results
                    present_files = set((d.get('File Name') or '') for d in unique_documents)
                    seed_docs: List[Dict[str, Any]] = []
                    if netspeed_files:
                        missing_files = [fn for fn in netspeed_files if fn not in present_files]
                        if missing_files:
                            try:
                                from utils.csv_utils import DEFAULT_DISPLAY_ORDER as _DO2
                                seed_body = {
                                    'query': {
                                        'bool': {
                                            'filter': [
                                                {'terms': {'File Name': missing_files}}
                                            ],
                                            'should': should_seed,
                                            'minimum_should_match': 1
                                        }
                                    },
                                    '_source': _DO2,
                                    'size': max(len(missing_files) * 2, 20)
                                }
                                resp_seed = self.client.search(index=self.get_search_indices(True), body=seed_body)
                                hits_seed = resp_seed.get('hits', {}).get('hits', [])
                                missing_set = set(missing_files)
                                for hit in hits_seed:
                                    src = hit.get('_source', {})
                                    fname = (src.get('File Name') or '')
                                    if not fname or fname not in missing_set or fname in present_files:
                                        continue
                                    seed_docs.append(src)
                                    present_files.add(fname)
                                    if len(seed_docs) == len(missing_set):
                                        break
                            except Exception as _e:
                                logger.debug(f"Seed query for netspeed files failed: {_e}")
                    if seed_docs:
                        # Prepend seeds to ensure they survive later capping; then re-dedupe preserving order
                        combined = seed_docs + unique_documents
                        unique_documents = self._deduplicate_documents_preserve_order(combined)
                except Exception as _e:
                    logger.debug(f"MAC per-file seeding failed: {_e}")

            # For MAC-like queries, promote one representative hit per netspeed file to the top
            # so the user immediately sees one row for each netspeed.csv(.N)
            promoted: List[Dict[str, Any]] = []
            if looks_like_mac_seed and effective_include_historical:
                try:
                    # Build list of netspeed files in desired order using configured directories
                    netspeed_files2 = self._netspeed_filenames()

                    # First doc per netspeed file from current unique_documents
                    first_by_file: Dict[str, Dict[str, Any]] = {}
                    for d in unique_documents:
                        fn = (d.get('File Name') or '').strip()
                        if not fn:
                            continue
                        if fn.startswith('netspeed') and fn not in first_by_file:
                            first_by_file[fn] = d

                    # Assemble promoted list following netspeed order
                    for fn in netspeed_files2:
                        doc = first_by_file.get(fn)
                        if doc:
                            promoted.append(doc)

                    if promoted:
                        # For MAC searches: return exactly one row per netspeed file
                        # Replace full results with the promoted representatives
                        unique_documents = promoted
                        logger.info(f"Returning {len(promoted)} per-file representatives for MAC query")
                except Exception as _e:
                    logger.debug(f"Per-file promotion failed: {_e}")

            # If it's a MAC-like query and still no netspeed.csv in results, try a wildcard-indices fallback
            try:
                mac_core_fb = canonical_mac
                looks_like_mac_fb = mac_core_fb is not None
            except Exception:
                looks_like_mac_fb = False
            if looks_like_mac_fb and not any((d.get('File Name') or '') == 'netspeed.csv' for d in unique_documents):
                try:
                    exact_terms_fb, wildcard_terms_fb = self._mac_query_variants(query, mac_core_fb)
                    should_fb = self._build_mac_should_clauses(exact_terms_fb, wildcard_terms_fb)
                    from utils.csv_utils import DEFAULT_DISPLAY_ORDER as _DO3
                    fb_body = {
                        "query": {
                            "bool": {
                                "must": [
                                    {"term": {"File Name": "netspeed.csv"}}
                                ],
                                "should": should_fb,
                                "minimum_should_match": 1
                            }
                        },
                        "_source": _DO3,
                        "size": 200
                    }
                    logger.info("[MAC-fallback] searching netspeed_* for File Name=netspeed.csv")
                    resp_fb = self.client.search(index=["netspeed_*"] , body=fb_body)
                    docs_fb = [h.get('_source', {}) for h in resp_fb.get('hits', {}).get('hits', [])]
                    if docs_fb:
                        # Keep only the first netspeed.csv document to avoid large duplicates
                        primary_fb = next((doc for doc in docs_fb if (doc.get('File Name') or '') == 'netspeed.csv'), docs_fb[0])
                        unique_documents.append(primary_fb)
                        unique_documents = self._deduplicate_documents_preserve_order(unique_documents)
                except Exception as e:
                    logger.warning(f"[MAC-fallback] wildcard indices search failed: {e}")

            # (Removed: secondary MAC fallback, now handled up-front)

            # For Switch Port-like queries, return one row per switch (and per file when historical)
            looks_like_port = isinstance(query, str) and ('/' in str(query))
            if looks_like_port and not looks_like_mac_seed:
                try:
                    seen_keys = set()
                    deduped_by_switch: List[Dict[str, Any]] = []
                    for d in unique_documents:
                        sh = (d.get('Switch Hostname') or '').strip()
                        fn = (d.get('File Name') or '').strip()
                        key = f"{sh}||{fn}" if include_historical else sh
                        if not key:
                            # Keep rows without a hostname only once
                            key = f"__nohost__||{fn}" if include_historical else "__nohost__"
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        deduped_by_switch.append(d)
                    if deduped_by_switch:
                        unique_documents = deduped_by_switch
                        logger.info(f"Switch Port dedupe reduced results to {len(unique_documents)} entries ({'per switch+file' if include_historical else 'per switch'})")
                except Exception as _e:
                    logger.debug(f"Switch Port dedupe failed: {_e}")

            # Sort the deduplicated documents by file name priority, then by Creation Date
            preferred_lookup = {name: idx for idx, name in enumerate(preferred_files)}
            original_positions = {id(doc): idx for idx, doc in enumerate(unique_documents)}

            def get_file_priority(doc):
                file_name = (doc.get('File Name', '') or '').strip()
                if not file_name:
                    return (len(preferred_lookup), 0, 0, original_positions.get(id(doc), 0))

                primary = preferred_lookup.get(file_name, len(preferred_lookup))
                rotation = 0
                timestamp_key = 0

                # Handle current file explicitly
                if file_name == 'netspeed.csv':
                    return (primary, 0, -1, original_positions.get(id(doc), 0))

                ts_match = re.match(r"^netspeed[._](\d{8})-(\d{6})\\.csv(?:\\.(\d+))?$", file_name)
                if ts_match:
                    stamp = int(ts_match.group(1) + ts_match.group(2))
                    timestamp_key = -stamp
                    rotation = int(ts_match.group(3)) if ts_match.group(3) is not None else -1
                elif file_name.startswith('netspeed.csv.'):
                    suffix = file_name.split('netspeed.csv.', 1)[1]
                    if suffix.isdigit():
                        rotation = int(suffix)
                    # Legacy rotations lack timestamps; keep timestamp_key neutral
                else:
                    # Fallback to Creation Date/Time if available
                    date_part = ''.join(ch for ch in str(doc.get('Creation Date', '') or '') if ch.isdigit())
                    time_part = ''.join(ch for ch in str(doc.get('Creation Time', '') or '') if ch.isdigit())
                    if date_part:
                        if time_part:
                            if len(time_part) < 6:
                                time_part = time_part.ljust(6, '0')
                            else:
                                time_part = time_part[:6]
                        else:
                            time_part = '000000'
                        try:
                            timestamp_key = -int(f"{date_part}{time_part}")
                        except ValueError:
                            timestamp_key = 0

                return (
                    primary,
                    timestamp_key,
                    rotation,
                    original_positions.get(id(doc), 0)
                )

            try:
                # Only enforce file priority order for MAC searches with historical enabled.
                # For general queries, keep OpenSearch's sort so exact field matches stay on top.
                if looks_like_mac_seed and effective_include_historical:
                    unique_documents.sort(key=get_file_priority)
                    logger.info(f"Sorted {len(unique_documents)} unique documents by file name priority (MAC+historical)")
                    for i, doc in enumerate(unique_documents[:15]):
                        priority = get_file_priority(doc)
                        logger.info(f"  {i+1}. {doc.get('File Name', 'unknown')} - Priority tuple: {priority}")
            except Exception as e:
                logger.warning(f"Error sorting documents by file name priority: {e}")

            # CSV fallback used during testing has been removed. Search relies on OpenSearch only.

            # Enforce a hard cap on number of returned documents to avoid huge payloads
            try:
                cap = int(size) if isinstance(size, int) else 20000
            except Exception:
                cap = 20000
            if cap and len(unique_documents) > cap:
                before = len(unique_documents)
                unique_documents = unique_documents[:cap]
                logger.info(f"Capped results from {before} to {cap}")

            # Apply display column filtering for consistency
            from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER

            # Enhance documents with KEM information in Line Number field for icon display
            # and remove KEM columns from display
            hidden_fields = {"KEM", "KEM 2"}  # Internal fields not shown to users
            enhanced_documents = []
            for doc in unique_documents:
                enhanced_doc = doc.copy()

                # Embed KEM information in Line Number field for frontend icon display
                line_number = enhanced_doc.get('Line Number', '')
                kem_field = enhanced_doc.get('KEM', '')
                kem2_field = enhanced_doc.get('KEM 2', '')

                # Build KEM suffix for Line Number
                kem_parts = []
                if kem_field and str(kem_field).strip():
                    kem_parts.append('KEM')
                if kem2_field and str(kem2_field).strip():
                    kem_parts.append('KEM2')

                # Embed KEM info in Line Number if present
                if kem_parts:
                    enhanced_doc['Line Number'] = f"{line_number} {' '.join(kem_parts)}"

                # Remove hidden fields from display
                for hidden in hidden_fields:
                    enhanced_doc.pop(hidden, None)

                # Normalize KEM serial number field names: some indices use 'KEM1 Serial Number' (no space)
                # while tests and UI expect 'KEM 1 Serial Number' (with space). Provide both for safety.
                try:
                    if 'KEM1 Serial Number' in enhanced_doc and 'KEM 1 Serial Number' not in enhanced_doc:
                        enhanced_doc['KEM 1 Serial Number'] = enhanced_doc.get('KEM1 Serial Number', '')
                    if 'KEM2 Serial Number' in enhanced_doc and 'KEM 2 Serial Number' not in enhanced_doc:
                        enhanced_doc['KEM 2 Serial Number'] = enhanced_doc.get('KEM2 Serial Number', '')
                    # Also ensure legacy 'KEM 1 Serial Number' keys exist even if empty
                    if 'KEM 1 Serial Number' not in enhanced_doc:
                        enhanced_doc['KEM 1 Serial Number'] = enhanced_doc.get('KEM 1 Serial Number', '')
                    if 'KEM 2 Serial Number' not in enhanced_doc:
                        enhanced_doc['KEM 2 Serial Number'] = enhanced_doc.get('KEM 2 Serial Number', '')
                except Exception:
                    pass

                enhanced_documents.append(enhanced_doc)

            # Build headers from filtered documents (KEM fields already removed)
            headers = self._build_headers_from_documents(enhanced_documents)
            logger.info(f"Found {len(enhanced_documents)} unique results for query '{query}' with {len(headers)} columns")
            return headers, enhanced_documents

        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}")
            return [], []

    def repair_current_file_after_indexing(self, current_file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Repair missing data in the current netspeed.csv file AFTER all files have been indexed.
        This ensures historical indices are available for data lookup during repair.

        DISABLED: This system causes CSV corruption by creating inconsistencies between
        the CSV file and OpenSearch index. It repairs the index but not the CSV file.

        Args:
            current_file_path: Path to the current netspeed.csv file

        Returns:
            Dict[str, Any]: Repair results summary
        """
        if not current_file_path:
            candidates: List[str] = []
            current_dir = getattr(settings, "NETSPEED_CURRENT_DIR", None)
            if current_dir:
                candidates.append(str(current_dir))
                candidates.append(str(Path(current_dir) / "netspeed.csv"))
            try:
                candidates.append(str(get_data_root() / "netspeed.csv"))
            except Exception:
                pass
            for cand in candidates:
                try:
                    if Path(cand).exists():
                        current_file_path = cand
                        break
                except Exception:
                    continue
            if not current_file_path and candidates:
                current_file_path = candidates[0]

        logger.info(f"POST-INDEX REPAIR: DISABLED - Skipping data repair for {current_file_path}")
        return {
            "success": True,
            "message": "Data repair disabled to prevent CSV corruption",
            "documents_repaired": 0
        }

    def _reindex_file_with_repaired_data(self, file_path: str, repaired_rows: List[Dict[str, Any]]) -> Tuple[bool, int]:
        """
        Re-index a file with repaired data by deleting the current index and recreating it.

        Args:
            file_path: Path to the file being re-indexed
            repaired_rows: Repaired data rows

        Returns:
            Tuple[bool, int]: Success status and document count
        """
        try:
            # Determine index name
            index_name = self.get_index_name(file_path)

            # Delete existing index for current file
            if self.client.indices.exists(index=index_name):
                self.client.indices.delete(index=index_name)
                logger.info(f"Deleted existing index for re-indexing: {index_name}")

            # Create new index with mapping
            self.client.indices.create(index=index_name, body=self.index_mappings)
            logger.info(f"Created new index for repaired data: {index_name}")

            # Generate actions for bulk indexing with repaired data
            actions = list(self._generate_actions_for_repaired_data(index_name, file_path, repaired_rows))

            if not actions:
                logger.warning("No actions generated for re-indexing")
                return False, 0

            # Bulk index repaired data
            success, failed = helpers.bulk(self.client, actions, refresh=True)

            if failed:
                logger.error(f"Some documents failed during re-indexing: {failed}")
                return False, 0

            logger.info(f"Successfully re-indexed {len(actions)} documents with repaired data")
            return True, len(actions)

        except Exception as e:
            logger.error(f"Error re-indexing with repaired data: {e}")
            return False, 0

    def _generate_actions_for_repaired_data(self, index_name: str, file_path: str, repaired_rows: List[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
        """
        Generate bulk index actions for repaired data.

        Args:
            index_name: Target index name
            file_path: Source file path
            repaired_rows: Repaired data rows

        Yields:
            Dict[str, Any]: Bulk index actions
        """
        # Get file creation date
        file_creation_date = None
        try:
            from models.file import FileModel
            file_model = FileModel.from_path(file_path)
            if file_model.date:
                file_creation_date = file_model.date.strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"Could not get file date for repaired data: {e}")

        # Generate actions
        for row_num, row in enumerate(repaired_rows, start=1):
            try:
                # Add metadata fields
                row["#"] = str(row_num)
                row["File Name"] = Path(file_path).name
                if file_creation_date:
                    row["Creation Date"] = file_creation_date

                yield {
                    "_index": index_name,
                    "_source": row
                }
            except Exception as e:
                logger.warning(f"Error generating action for row {row_num}: {e}")


# Shared OpenSearchConfig instance for modules that expect a singleton
opensearch_config = OpenSearchConfig()