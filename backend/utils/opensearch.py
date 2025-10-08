from opensearchpy import OpenSearch, helpers
from config import settings
import logging
import re
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Generator, Optional, Tuple
from .csv_utils import read_csv_file
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
                    "Speed 1": self.keyword_type,  # Legacy field retained for historical indices
                    "Speed 2": self.keyword_type,  # Legacy field retained for historical indices
                    # Legacy field names retained for historical indices
                    "Speed Switch-Port": self.keyword_type,
                    "Speed PC-Port": self.keyword_type,
                    # Canonical column names for switch/PC port mode
                    "Switch Port Mode": self.keyword_type,
                    "PC Port Mode": self.keyword_type,
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
                # Current-only search: use only the newest netspeed index
                if netspeed_ordered:
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
        """Fetch a small preview from the given netspeed index."""
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
            all_headers: list[str] = []
            seen = set()
            for row in rows:
                for key in row.keys():
                    if key not in seen:
                        seen.add(key)
                        all_headers.append(key)

            # Align with CSV display columns when possible
            try:
                from utils.csv_utils import filter_display_columns
                headers, filtered_rows = filter_display_columns(all_headers, rows)
                if headers:
                    return headers, filtered_rows
            except Exception:
                pass

            return all_headers, rows
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
        _, rows = read_csv_file(file_path)

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

        # Import DESIRED_ORDER for consistent column filtering
        from utils.csv_utils import DESIRED_ORDER

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

        try:
            # Get current file name to exclude it from historical search
            current_file_name = Path(file_path).name

            # Get all netspeed indices except the current one
            historical_indices = []
            try:
                indices = self.client.indices.get(index="netspeed_*")
                for index_name in indices.keys():
                    # Skip the current file's index
                    if current_file_name not in index_name:
                        historical_indices.append(index_name)
            except Exception as e:
                logger.warning(f"Could not get historical indices for data repair: {e}")
                return rows  # Return original rows if we can't get historical data

            if not historical_indices:
                print("[DATA REPAIR] No historical indices found for data repair")
                logger.warning("DATA REPAIR: No historical indices found")
                return rows

            print(f"[DATA REPAIR] Using {len(historical_indices)} historical indices for data repair")
            logger.warning(f"DATA REPAIR: Using {len(historical_indices)} historical indices: {historical_indices[:3]}...")

            repaired_rows = []
            repaired_count = 0
            total_missing = 0
            max_repairs = 50  # LIMIT: Maximum number of MAC repairs to prevent infinite loops

            for row in rows:
                # SAFETY LIMIT: Stop processing if we've already processed too many repairs
                if total_missing >= max_repairs:
                    print(f"[DATA REPAIR] LIMIT REACHED: Stopping after {max_repairs} repair attempts to prevent infinite loops")
                    logger.warning(f"DATA REPAIR LIMIT: Stopped after {max_repairs} repair attempts")
                    break

                # MAC address is the primary identifier - check both MAC Address fields
                mac_address = row.get("MAC Address", "").strip()
                mac_address_2 = row.get("MAC Address 2", "").strip()

                # Use whichever MAC address field has a value and is a valid MAC address
                primary_mac = None
                if mac_address and self._is_valid_mac_address(mac_address):
                    primary_mac = mac_address
                elif mac_address_2:
                    # Remove SEP prefix if present
                    clean_mac_2 = mac_address_2[3:] if mac_address_2.startswith("SEP") else mac_address_2
                    if self._is_valid_mac_address(clean_mac_2):
                        primary_mac = clean_mac_2

                # Find all missing fields in current row
                missing_fields = []
                for field, value in row.items():
                    # Check for empty, None, or null values
                    if value is None or str(value).strip() == "" or str(value).lower() == "null":
                        missing_fields.append(field)

                # Only repair if we have a valid MAC address and something is missing
                if missing_fields and primary_mac:
                    total_missing += 1
                    print(f"[DATA REPAIR] Processing MAC {primary_mac} (from {mac_address or mac_address_2}) with missing fields: {missing_fields}")

                    # Look up historical data by MAC address (primary identifier)
                    historical_data = self._lookup_historical_data_by_mac(primary_mac, historical_indices)

                    # Repair missing data if found
                    if historical_data:
                        print(f"[DATA REPAIR] Found historical data for MAC {primary_mac}")
                        repaired_this_row = False
                        repaired_fields = []

                        for field in missing_fields:
                            # Skip MAC Address itself as it's the identifier
                            if field == "MAC Address":
                                continue

                            historical_value = historical_data.get(field)
                            print(f"[DATA REPAIR] Field '{field}': historical_value = '{historical_value}' (type: {type(historical_value)})")
                            if historical_value and str(historical_value).strip() and str(historical_value).lower() != "null":
                                row[field] = historical_value
                                repaired_fields.append(field)
                                repaired_this_row = True
                                print(f"[DATA REPAIR] Successfully repaired field '{field}' with value '{historical_value}'")
                            else:
                                print(f"[DATA REPAIR] Field '{field}' could not be repaired: value is empty, null, or invalid")

                        if repaired_this_row:
                            repaired_count += 1
                            print(f"[DATA REPAIR] Repaired MAC {primary_mac}: {', '.join(repaired_fields)}")
                            logger.warning(f"DATA REPAIR: Repaired MAC {primary_mac} - fields: {repaired_fields}")
                        else:
                            print(f"[DATA REPAIR] No valid data found for MAC {primary_mac}")
                    else:
                        print(f"[DATA REPAIR] No historical data found for MAC {primary_mac}")

                repaired_rows.append(row)

            if repaired_count > 0:
                print(f"[DATA REPAIR] COMPLETED: {repaired_count}/{total_missing} entries repaired")
                logger.warning(f"DATA REPAIR COMPLETED: {repaired_count}/{total_missing} entries repaired from historical data using MAC address lookup")
            else:
                print(f"[DATA REPAIR] COMPLETED: No historical data found for {total_missing} missing entries")
                logger.warning(f"DATA REPAIR COMPLETED: No historical data found for {total_missing} missing entries")

            return repaired_rows

        except Exception as e:
            print(f"[DATA REPAIR] ERROR: {e}")
            logger.error(f"Error during data repair: {e}")
            return rows  # Return original rows on error

    def _lookup_historical_data_by_mac(self, mac_address: str, historical_indices: List[str]) -> Optional[Dict[str, Any]]:
        """
        Look up historical data by MAC address in historical indices.
        MAC address is the primary identifier since it remains constant across files.
        Returns all available fields from historical data for repair purposes.

        Args:
            mac_address: MAC address to search for (primary identifier)
            historical_indices: List of historical index names to search

        Returns:
            Optional[Dict[str, Any]]: Historical document data if found, None otherwise
        """
        try:
            query = {
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"MAC Address.keyword": mac_address}},
                            {"term": {"MAC Address 2.keyword": mac_address}},
                            {"term": {"MAC Address 2.keyword": f"SEP{mac_address}"}}
                        ],
                        "minimum_should_match": 1
                    }
                },
                "sort": [{"Creation Date": {"order": "desc"}}],  # Get most recent first
                "size": 1  # Only get the most recent one to avoid too many requests
                # Return all fields - no _source filtering
            }

            # LIMIT: Search only the first 5 historical indices to prevent infinite loops
            # Most recent data is usually in the first few indices anyway
            limited_indices = sorted(historical_indices, reverse=True)[:5]

            # Search across LIMITED historical indices
            for index in limited_indices:
                try:
                    response = self.client.search(index=index, body=query)
                    if response["hits"]["total"]["value"] > 0:
                        # Return the first match immediately - don't search all indices
                        hit = response["hits"]["hits"][0]
                        logger.debug(f"Found historical data for MAC {mac_address} in index {index}")
                        return hit["_source"]
                except Exception as e:
                    logger.debug(f"Error searching historical index {index} for MAC {mac_address}: {e}")
                    continue

            # No data found in any historical index
            return None

        except Exception as e:
            logger.debug(f"Error in MAC-based historical lookup for {mac_address}: {e}")
            return None

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
            # Use all columns including KEM fields for KEM searches
            all_columns = [
                "#", "File Name", "Creation Date", "IP Address", "Line Number", "Serial Number", "Model Name",
                "KEM", "KEM 2", "MAC Address", "MAC Address 2", "Subnet Mask", "Voice VLAN",
                "Phone Port Speed", "PC Port Speed", "Speed 1", "Speed 2",
                "Switch Hostname", "Switch Port", "Switch Port Mode", "PC Port Mode"
            ]
            # Semantics: phone has ≥1 KEM if KEM or KEM 2 is non-empty OR Line Number contains 'KEM'
            kem_query = {
                "query": {
                    "bool": {
                        "should": [
                            {"exists": {"field": "KEM"}},
                            {"exists": {"field": "KEM.keyword"}},
                            {"exists": {"field": "KEM 2"}},
                            {"exists": {"field": "KEM 2.keyword"}},
                            {"wildcard": {"KEM.keyword": "*KEM*"}},
                            {"wildcard": {"KEM 2.keyword": "*KEM*"}},
                            {"match": {"KEM": "KEM"}},
                            {"match": {"KEM 2": "KEM"}},
                            {"wildcard": {"Line Number.keyword": "*KEM*"}}
                        ],
                        "minimum_should_match": 1
                    }
                },
                "_source": all_columns,
                "size": size,
                "sort": [
                    {"Creation Date": {"order": "desc"}},
                    self._preferred_file_sort_clause(),
                    {"_score": {"order": "desc"}}
                ]
            }
            return kem_query

        if field:
            from utils.csv_utils import DESIRED_ORDER
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
                from utils.csv_utils import DESIRED_ORDER
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

            # Switch Hostname pattern without domain: 3 letters + 2 digits + other chars (like ABX01ZSL5210P)
            hostname_pattern_match = re.match(r'^[A-Za-z]{3}[0-9]{2}', qn or "") if isinstance(qn, str) else None
            if hostname_pattern_match and '.' not in qn and len(qn) >= 13:
                from utils.csv_utils import DESIRED_ORDER
                q_lower = qn.lower()
                return {
                    "query": {
                        "bool": {
                            "should": [
                                {"term": {"Switch Hostname.lower": q_lower}},
                                {"term": {"Switch Hostname": qn}},
                                {"term": {"Switch Hostname": qn.upper()}},
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
                    return {
                        "query": {"bool": {"should": [
                            {"term": {"Serial Number": qsn}},
                            {"term": {"Serial Number": qsn.upper()}},
                            {"wildcard": {"Serial Number": f"{qsn}*"}},
                            {"wildcard": {"Serial Number": f"{qsn.upper()}*"}}
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

            # Switch hostname prefix (e.g., Mxx08, ABX01, ABX01ZSL) - exactly 5 characters OR 6-12 with multiple continuing letters
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
                from utils.csv_utils import DESIRED_ORDER
                q_lower = qn.lower()
                q_upper = qn.upper()
                # Prefix search: matches ABX01*, ABX01ZSL*, etc.
                should_clauses = [
                    {"prefix": {"Switch Hostname.lower": q_lower}},
                    {"prefix": {"Switch Hostname": qn}},
                    {"prefix": {"Switch Hostname": q_upper}},
                    {"wildcard": {"Switch Hostname.lower": f"{q_lower}*"}},
                    {"wildcard": {"Switch Hostname": f"{qn}*"}},
                    {"wildcard": {"Switch Hostname": f"{q_upper}*"}},
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

            # Switch hostname codes (e.g., ABX01ZSL4750P) - exact match with 13+ characters
            hostname_code_match = re.match(r"^[A-Za-z]{3}[0-9]{2}", qn or "")
            if hostname_code_match and '.' not in qn and len(qn) >= 13:
                from utils.csv_utils import DESIRED_ORDER
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

            # MAC exact-only when 12-hex provided
            mac_core = re.sub(r"[^A-Fa-f0-9]", "", qn)
            if len(mac_core) == 12:
                from utils.csv_utils import DESIRED_ORDER
                mac_up = mac_core.upper()
                return {
                    "query": {"bool": {"should": [
                        {"term": {"MAC Address.keyword": mac_up}},
                        {"term": {"MAC Address 2.keyword": mac_up}},
                        {"term": {"MAC Address 2.keyword": f"SEP{mac_up}"}},
                        {"multi_match": {"query": mac_up, "fields": ["*"], "boost": 0.01}}
                    ], "minimum_should_match": 1}},
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        self._preferred_file_sort_clause(),
                        {"Creation Date": {"order": "desc"}}
                    ]
                }

            # 4-digit Model pattern (e.g., "8832", "8851") - search ONLY for exact model matches
            if re.fullmatch(r"\d{4}", qn or ""):
                from utils.csv_utils import DESIRED_ORDER
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
                from utils.csv_utils import DESIRED_ORDER
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

            # FQDN exact-only branch for hostname-like queries
            if (
                any(c.isalpha() for c in qn)
                and "." in qn
                and "/" not in qn
                and " " not in qn
                and not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", qn or "")
            ):
                from utils.csv_utils import DESIRED_ORDER
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
                                {"term": {"Switch Hostname.lower": qn.lower()}}
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

            # Serial Number prefix branch: alphanumeric tokens 3-10 chars use prefix wildcards
            if re.fullmatch(r"[A-Za-z0-9]{3,10}", qn or ""):
                from utils.csv_utils import DESIRED_ORDER

                variants = []
                if qn:
                    variants.append(qn)
                    upper_variant = qn.upper()
                    if upper_variant not in (None, qn) and upper_variant not in variants:
                        variants.append(upper_variant)

                wildcard_clauses = [
                    {"wildcard": {"Serial Number": f"{variant}*"}}
                    for variant in variants
                ]

                return {
                    "query": {"bool": {"should": wildcard_clauses, "minimum_should_match": 1}},
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        {"_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "def q = params.q; if (q == null) return 1; if (doc.containsKey('Serial Number') && doc['Serial Number'].size()>0) { def v = doc['Serial Number'].value; if (v != null && (v == q || v.equalsIgnoreCase(q))) { return 0; } } return 1;",
                            "params": {"q": qn}
                        }}},
                        {"Creation Date": {"order": "desc"}},
                        self._preferred_file_sort_clause(),
                        {"_score": {"order": "desc"}}
                    ]
                }

        # Broad query: allow partials but with exact-first sort
        # Exclude multi_match for hostname patterns to prevent false matches
        is_hostname_pattern = isinstance(query, str) and len(query) >= 5 and re.match(r'^[A-Za-z]{3}[0-9]{2}', query)

        file_name_boost_clauses = [
            {"term": {"File Name": {"value": name, "boost": 2.0}}}
            for name in preferred_files[:5]
        ]

        search_query = {
            "query": {"bool": {"should": [
                {"term": {"Switch Port": {"value": query, "boost": 10.0}}},
                *([] if is_hostname_pattern else [{"multi_match": {"query": query, "fields": ["*"]}}]),
                {"term": {"Line Number.keyword": query}},
                {"term": {"MAC Address": query}},
                {"term": {"Line Number.keyword": f"+{query}"}},
                *file_name_boost_clauses,

                {"wildcard": {"MAC Address.keyword": f"*{str(query).lower()}*"}},
                {"wildcard": {"MAC Address.keyword": f"*{str(query).upper()}*"}},
                                {"wildcard": {"MAC Address 2.keyword": f"*{str(query).lower()}*"}},
                                {"wildcard": {"MAC Address 2.keyword": f"*{str(query).upper()}*"}},

                                {"wildcard": {"Line Number.keyword": f"*{query}*"}},
                                                *([{"wildcard": {"Line Number.keyword": f"*{str(query).lstrip('+')}*"}}]
                                    if str(query).startswith('+') and str(query).lstrip('+') else
                                    [{"wildcard": {"Line Number.keyword": f"*+{query}*"}}]),


                {"wildcard": {"Switch Port": f"*{query}*"}},
                {"wildcard": {"Subnet Mask": f"*{query}*"}},
                {"wildcard": {"Voice VLAN": f"*{query}*"}},

                {"wildcard": {"Phone Port Speed": f"*{query}*"}},
                {"wildcard": {"PC Port Speed": f"*{query}*"}},
                {"wildcard": {"Speed 1": f"*{query}*"}},
                {"wildcard": {"Speed 2": f"*{query}*"}},
                {"wildcard": {"Speed 3": f"*{query}*"}},
                {"wildcard": {"Speed 4": f"*{query}*"}},

                {"wildcard": {"Model Name": f"*{str(query).lower()}*"}},
                {"wildcard": {"Model Name": f"*{str(query).upper()}*"}},
                {"wildcard": {"File Name": f"*{query}*"}},
                # If it looks like a bare hostname token (starts with 3 letters + 2 digits),
                # add a case-insensitive wildcard against the normalized hostname field
                *([{"wildcard": {"Switch Hostname.lower": f"*{str(query).lower()}*"}}] if is_hostname_pattern else [])
            ], "minimum_should_match": 1}},
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

        # Add IP prefix support for partial IPv4 fragments
        ip_pattern = re.compile(r'^[0-9]{1,3}(\.[0-9]{1,3}){0,2}\.?$')
        if isinstance(query, str) and ip_pattern.match(query):
            try:
                clean_query = query.rstrip('.')
                if clean_query:
                    # For general search, use only prefix to avoid false matches
                    search_query["query"]["bool"]["should"].append({"prefix": {"IP Address.keyword": clean_query}})
                    search_query["query"]["bool"]["should"].append({"prefix": {"IP Address.keyword": f"{clean_query}."}})
            except Exception as e:
                logger.warning(f"Failed to add IP prefix search for '{query}': {e}")

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

        from utils.csv_utils import DESIRED_ORDER, LEGACY_COLUMN_RENAMES
        legacy_fields = list(LEGACY_COLUMN_RENAMES.keys())
        search_query["_source"] = list(dict.fromkeys(DESIRED_ORDER + legacy_fields))

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

            # Helper to normalize user input into canonical 12-hex MAC (uppercase)
            def _normalize_mac(q: Optional[str]) -> Optional[str]:
                if not isinstance(q, str) or not q:
                    return None
                s = q.strip()
                import re as _re
                # Strip optional Cisco SEP prefix (case-insensitive) with optional separator
                s = _re.sub(r'(?i)^sep[-_:]?', '', s)
                # Remove all non-hex characters (handle '-', ':', '.')
                core = _re.sub(r'[^0-9A-Fa-f]', '', s)
                if len(core) == 12:
                    # Treat as MAC only if it likely is one: contains hex letters or had MAC separators or SEP prefix
                    if _re.search(r'[A-Fa-f]', q) or _re.search(r'[:\-\.]', q) or _re.match(r'(?i)^\s*sep', q.strip()):
                        return core.upper()
                return None

            # If the query looks like a MAC, first search the current index only to prefer today's file
            try:
                canonical_mac = _normalize_mac(query)
                looks_like_mac_first = canonical_mac is not None
            except Exception:
                canonical_mac = None
                looks_like_mac_first = False

            if looks_like_mac_first:
                try:
                    curr_indices_first = self.get_search_indices(False)
                    mac_upper_first = str(canonical_mac)
                    from utils.csv_utils import DESIRED_ORDER as _DO
                    must_clauses_first: List[Dict[str, Any]] = []
                    if preferred_files:
                        must_clauses_first.append({"terms": {"File Name": preferred_files[:5]}})
                    targeted_first = {
                        "query": {
                            "bool": {
                                "must": must_clauses_first,
                                "should": [
                                    {"term": {"MAC Address.keyword": mac_upper_first}},
                                    {"term": {"MAC Address 2.keyword": mac_upper_first}},
                                    {"term": {"MAC Address 2.keyword": f"SEP{mac_upper_first}"}},
                                    {"wildcard": {"MAC Address.keyword": f"*{mac_upper_first}*"}},
                                    {"wildcard": {"MAC Address 2.keyword": f"*{mac_upper_first}*"}}
                                ],
                                "minimum_should_match": 1
                            }
                        },
                        "_source": _DO,
                        "size": 200
                    }
                    logger.info(f"[MAC-first] indices={curr_indices_first} body={targeted_first}")
                    resp_first = self.client.search(index=curr_indices_first, body=targeted_first)
                    docs_first = [h.get('_source', {}) for h in resp_first.get('hits', {}).get('hits', [])]
                    # Fallback: older indices might lack 'File Name' field – retry without MUST clause
                    if not docs_first:
                        try:
                            fallback_body = targeted_first.copy()
                            fb_query = fallback_body.get('query', {}).get('bool', {})
                            if isinstance(fb_query, dict) and 'must' in fb_query:
                                fb_query.pop('must', None)
                                logger.info("[MAC-first] primary query empty, retrying without File Name must-clause")
                                resp_fb = self.client.search(index=curr_indices_first, body=fallback_body)
                                docs_first = [h.get('_source', {}) for h in resp_fb.get('hits', {}).get('hits', [])]
                        except Exception as _fb_e:
                            logger.debug(f"[MAC-first] fallback without must failed: {_fb_e}")
                    if docs_first:
                        documents.extend(docs_first)
                        logger.info(f"[MAC-first] seeded {len(docs_first)} docs from current index")
                except Exception as e:
                    logger.warning(f"[MAC-first] current-index search failed: {e}")

            # Early exact branch: phone-like (+digits) returns exactly 1 result
            try:
                looks_like_phone = False
                if isinstance(query, str):
                    qn_phone = query.strip()
                    looks_like_phone = bool(re.fullmatch(r"\+?\d{7,}", qn_phone or ""))
            except Exception:
                looks_like_phone = False
            if looks_like_phone:
                try:
                    qn_phone = query.strip()
                    # Always include both variants: with and without leading '+'
                    if qn_phone.startswith('+'):
                        digits = qn_phone.lstrip('+')
                        cands = [qn_phone]
                        if digits:
                            cands.append(digits)
                    else:
                        digits = qn_phone
                        cands = [digits, f"+{digits}"] if digits else []
                    from utils.csv_utils import DESIRED_ORDER
                    if include_historical:
                        # Return one exact match per netspeed file, newest first
                        netspeed_files = self._netspeed_filenames()
                        results: List[Dict[str, Any]] = []
                        for fname in netspeed_files:
                            try:
                                seed_body = {
                                    "query": {
                                        "bool": {
                                            "must": [
                                                {"term": {"File Name": fname}}
                                            ],
                                            "should": [{"term": {"Line Number.keyword": c}} for c in cands],
                                            "minimum_should_match": 1
                                        }
                                    },
                                    "_source": DESIRED_ORDER,
                                    "size": 1
                                }
                                # Search across current + historical indices to include netspeed.csv as well
                                resp = self.client.search(index=self.get_search_indices(True), body=seed_body)
                                hit = next((h.get('_source', {}) for h in resp.get('hits', {}).get('hits', [])), None)
                                if hit:
                                    results.append(hit)
                            except Exception as _e:
                                logger.debug(f"[PHONE] per-file seed failed for {fname}: {_e}")
                        return DESIRED_ORDER, results
                    else:
                        # Only current file (netspeed.csv): try exact (size=1), then fallback to partial wildcard if not found
                        indices_phone = self.get_search_indices(False)
                        phone_body_exact = {
                            "query": {"bool": {"should": [{"term": {"Line Number.keyword": c}} for c in cands], "minimum_should_match": 1}},
                            "_source": DESIRED_ORDER,
                            "size": 1
                        }
                        logger.info(f"[PHONE-exact] indices={indices_phone} body={phone_body_exact}")
                        resp_phone = self.client.search(index=indices_phone, body=phone_body_exact)
                        phone_hit = next((h.get('_source', {}) for h in resp_phone.get('hits', {}).get('hits', [])), None)
                        if phone_hit:
                            return DESIRED_ORDER, [phone_hit]
                        # Fallback: partial match within current netspeed.csv
                        digits = qn_phone.lstrip('+')
                        if digits:
                            phone_body_partial = {
                                "query": {"bool": {"should": [
                                    {"wildcard": {"Line Number.keyword": f"*{digits}*"}},
                                    {"wildcard": {"Line Number.keyword": f"*+{digits}*"}}
                                ], "minimum_should_match": 1}},
                                "_source": DESIRED_ORDER,
                                "size": 20000,
                                "sort": [{"Creation Date": {"order": "desc"}}]
                            }
                            logger.info(f"[PHONE-partial] indices={indices_phone} body={phone_body_partial}")
                            resp_part = self.client.search(index=indices_phone, body=phone_body_partial)
                            docs_part = [h.get('_source', {}) for h in resp_part.get('hits', {}).get('hits', [])]
                            # Deduplicate by MAC+File to avoid repeated identical rows
                            docs_part = self._deduplicate_documents_preserve_order(docs_part)
                            return DESIRED_ORDER, docs_part
                        return DESIRED_ORDER, []
                except Exception as e:
                    logger.warning(f"Phone exact search failed, falling back to general: {e}")

            looks_like_hostname_prefix = False
            try:
                if isinstance(query, str):
                    q_hostname_prefix = query.strip()
                    if (
                        q_hostname_prefix
                        and re.match(r'^[A-Za-z]{3}[0-9]{2}', q_hostname_prefix)
                        and '.' not in q_hostname_prefix
                        and 5 <= len(q_hostname_prefix) < 13
                    ):
                        # Exactly 5 characters: always a hostname prefix (e.g., ABX01, Mxx08)
                        if len(q_hostname_prefix) == 5:
                            looks_like_hostname_prefix = True
                        # 8+ characters: must have at least 2 consecutive letters after position 5
                        # This excludes patterns like ABC1234 (only digits) and ABC1234X (single letter at end)
                        elif len(q_hostname_prefix) >= 8:
                            remaining = q_hostname_prefix[5:]
                            if re.search(r'[A-Za-z]{2,}', remaining):
                                looks_like_hostname_prefix = True
            except Exception:
                looks_like_hostname_prefix = False

            # Early exact branch: Serial Number-like (long alphanumeric, not pure digits)
            try:
                looks_like_serial = False
                if isinstance(query, str):
                    qn_sn = query.strip()
                    # Check if it's alphanumeric 8+ chars and not pure digits
                    basic_serial_pattern = bool(re.fullmatch(r"[A-Za-z0-9]{8,}", qn_sn or "")) and not bool(re.fullmatch(r"\d{8,}", qn_sn or ""))

                    # Exclude hostname-like patterns (3 letters + 2 digits + more chars pattern)
                    looks_like_hostname = False
                    if basic_serial_pattern and len(qn_sn) >= 13:
                        # Switch hostnames follow pattern: 3 letters + 2 digits + other chars and are typically 13+ chars
                        hostname_pattern = re.match(r'^[A-Za-z]{3}[0-9]{2}', qn_sn)
                        looks_like_hostname = hostname_pattern is not None

                    looks_like_serial = basic_serial_pattern and not looks_like_hostname
            except Exception:
                looks_like_serial = False
            if looks_like_serial and not looks_like_mac_first:
                try:
                    qn_sn = query.strip()
                    variants = [qn_sn]
                    up = qn_sn.upper()
                    if up != qn_sn:
                        variants.append(up)
                    from utils.csv_utils import DESIRED_ORDER
                    indices_sn = self.get_search_indices(include_historical)
                    indices_sn_list = indices_sn if isinstance(indices_sn, list) else [indices_sn]
                    allow_archive_files_sn = any(idx == self.archive_index for idx in indices_sn_list)
                    allow_historical_files_sn = bool(include_historical)

                    # Support both exact and prefix search for serial numbers
                    # For 8-10 characters: add both exact and wildcard queries
                    # For 11+ characters: prefer exact match but also include wildcard as fallback
                    should_clauses = []

                    # Add exact match queries
                    should_clauses.extend([{ "term": {"Serial Number": v} } for v in variants])

                    # Add wildcard prefix queries for progressive search (especially for 8-10 char lengths)
                    if len(qn_sn) >= 3:
                        should_clauses.extend([{ "wildcard": {"Serial Number": f"{v}*"} } for v in variants])

                    body_sn = {
                        "query": {"bool": {"should": should_clauses, "minimum_should_match": 1}},
                        "_source": DESIRED_ORDER,
                        "size": (size if include_historical else 20000),  # Increase size for prefix searches
                        "sort": [
                            {"Creation Date": {"order": "desc"}},
                            self._preferred_file_sort_clause(),
                            {"_score": {"order": "desc"}}
                        ]
                    }
                    logger.info(f"[SERIAL] indices={indices_sn} body={body_sn}")
                    resp_sn = self.client.search(index=indices_sn, body=body_sn)
                    docs_sn = [h.get('_source', {}) for h in resp_sn.get('hits', {}).get('hits', [])]
                    # Filter out archived filenames; keep only netspeed.csv, netspeed_YYYYMMDD-HHMMSS.csv, and rotation files
                    def _is_allowed_file(fn: str) -> bool:
                        if not fn:
                            return False
                        if fn == 'netspeed.csv':
                            return True
                        # Always allow timestamp format (current file without rotation suffix)
                        if re.match(r'^netspeed_\d{8}-\d{6}\.csv$', fn):
                            return True
                        # Historical rotation files
                        if allow_historical_files_sn:
                            # Legacy rotation: netspeed.csv.N
                            if fn.startswith('netspeed.csv.'):
                                suf = fn.split('netspeed.csv.', 1)[1]
                                return suf.isdigit()
                            # Timestamped rotation: netspeed_YYYYMMDD-HHMMSS.csv.N
                            if re.match(r'^netspeed_\d{8}-\d{6}\.csv\.\d+$', fn):
                                return True
                        # Archive files
                        if allow_archive_files_sn and fn.startswith('netspeed_'):
                            return True
                        return False
                    docs_sn = [d for d in docs_sn if _is_allowed_file((d.get('File Name') or '').strip())]
                    if include_historical:
                        # Keep only one document per file name
                        seen_files = set()
                        dedup_by_file: List[Dict[str, Any]] = []
                        for d in docs_sn:
                            fn = (d.get('File Name') or '').strip()
                            if not fn or fn in seen_files:
                                continue
                            seen_files.add(fn)
                            dedup_by_file.append(d)
                        docs_sn = dedup_by_file
                    return DESIRED_ORDER, docs_sn
                except Exception as e:
                    logger.warning(f"Serial exact search failed, falling back to general: {e}")

            # Early exact branch: Hostname/FQDN (contains dot and letters, not IP)
            try:
                looks_like_hostname_early = False
                if isinstance(query, str):
                    qn_hn = query.strip()
                    looks_like_hostname_early = ('.' in qn_hn and any(c.isalpha() for c in qn_hn) and '/' not in qn_hn and ' ' not in qn_hn and not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", qn_hn or ""))
            except Exception:
                looks_like_hostname_early = False
            if looks_like_hostname_early and not looks_like_mac_first:
                try:
                    qn_hn = query.strip()
                    from utils.csv_utils import DESIRED_ORDER
                    indices_hn = self.get_search_indices(include_historical)
                    indices_hn_list = indices_hn if isinstance(indices_hn, list) else [indices_hn]
                    allow_archive_files_hn = any(idx == self.archive_index for idx in indices_hn_list)
                    allow_historical_files_hn = bool(include_historical)
                    body_hn = {
                        "query": {
                            "bool": {
                                "filter": [
                                    {
                                        "script": {
                                            "script": {
                                                "lang": "painless",
                                                "source": "def v = null; if (doc.containsKey('Switch Hostname') && doc['Switch Hostname'].size()>0) { v = doc['Switch Hostname'].value; } else { return false; } if (v == null) return false; return v.trim().equalsIgnoreCase(params.q.trim());",
                                                "params": {"q": qn_hn}
                                            }
                                        }
                                    }
                                ],
                                "should": [
                                    {"term": {"Switch Hostname": qn_hn}},
                                    {"term": {"Switch Hostname.lower": qn_hn.lower()}}
                                ],
                                "minimum_should_match": 0
                            }
                        },
                        "_source": DESIRED_ORDER,
                        "size": size,
                        "sort": [
                            {"Creation Date": {"order": "desc"}},
                            self._preferred_file_sort_clause()
                        ]
                    }
                    resp_hn = self.client.search(index=indices_hn, body=body_hn)
                    docs_hn = [h.get('_source', {}) for h in resp_hn.get('hits', {}).get('hits', [])]
                    # Filter allowed files
                    def _is_allowed_file(fn: str) -> bool:
                        if not fn:
                            return False
                        if fn == 'netspeed.csv':
                            return True
                        if allow_historical_files_hn and fn.startswith('netspeed.csv.'):
                            suf = fn.split('netspeed.csv.', 1)[1]
                            return suf.isdigit()
                        if allow_archive_files_hn and fn.startswith('netspeed_'):
                            return True
                        return False
                    docs_hn = [d for d in docs_hn if _is_allowed_file((d.get('File Name') or '').strip())]
                    return DESIRED_ORDER, docs_hn
                except Exception as e:
                    logger.warning(f"Hostname exact search failed, falling back to general: {e}")

            # Now run the general search across the selected indices
            # For MAC-like queries, always include historical indices to list results from all netspeed.csv files
            indices = self.get_search_indices(include_historical)
            if looks_like_mac_first:
                # Force historical for the general phase regardless of caller flag
                indices = self.get_search_indices(True)
            # Removed: hostname prefix override - respect user's include_historical flag
            indices_list = indices if isinstance(indices, list) else [indices]
            allow_archive_files_general = any(idx == self.archive_index for idx in indices_list)
            allow_historical_files_general = bool(include_historical or looks_like_mac_first)
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
            if looks_like_mac_seed and include_historical:
                try:
                    mac_upper_seed = str(mac_core_seed)
                    netspeed_files = self._netspeed_filenames()

                    # Determine which file names are already present in results
                    present_files = set((d.get('File Name') or '') for d in unique_documents)
                    seed_docs: List[Dict[str, Any]] = []
                    if netspeed_files:
                        # Build a small targeted body per file
                        for fname in netspeed_files:
                            if fname in present_files:
                                continue  # already represented
                            try:
                                from utils.csv_utils import DESIRED_ORDER as _DO2
                                seed_body = {
                                    'query': {
                                        'bool': {
                                            'must': [
                                                {'term': {'File Name': fname}}
                                            ],
                                            'should': [
                                                {'term': {'MAC Address.keyword': mac_upper_seed}},
                                                {'term': {'MAC Address 2.keyword': mac_upper_seed}},
                                                {'term': {'MAC Address 2.keyword': f'SEP{mac_upper_seed}'}},
                                                {'wildcard': {'MAC Address.keyword': f'*{mac_upper_seed}*'}},
                                                {'wildcard': {'MAC Address 2.keyword': f'*{mac_upper_seed}*'}}
                                            ],
                                            'minimum_should_match': 1
                                        }
                                    },
                                    '_source': _DO2,
                                    'size': 1
                                }
                                # Search across current + historical indices to include netspeed.csv as well
                                resp_seed = self.client.search(index=self.get_search_indices(True), body=seed_body)
                                hit = next((h.get('_source', {}) for h in resp_seed.get('hits', {}).get('hits', [])), None)
                                if hit:
                                    seed_docs.append(hit)
                            except Exception as _e:
                                logger.debug(f"Seed query for {fname} failed: {_e}")
                    if seed_docs:
                        # Prepend seeds to ensure they survive later capping; then re-dedupe preserving order
                        combined = seed_docs + unique_documents
                        unique_documents = self._deduplicate_documents_preserve_order(combined)
                except Exception as _e:
                    logger.debug(f"MAC per-file seeding failed: {_e}")

            # For MAC-like queries, promote one representative hit per netspeed file to the top
            # so the user immediately sees one row for each netspeed.csv(.N)
            promoted: List[Dict[str, Any]] = []
            if looks_like_mac_seed and include_historical:
                try:
                    # Build list of netspeed files in desired order using configured directories
                    netspeed_files2 = self._netspeed_filenames()

                    # First doc per file from current unique_documents
                    first_by_file: Dict[str, Dict[str, Any]] = {}
                    for d in unique_documents:
                        fn = (d.get('File Name') or '')
                        if not fn:
                            continue
                        if fn.startswith('netspeed.csv') and fn not in first_by_file:
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
                    mac_upper_fb = str(mac_core_fb)
                    from utils.csv_utils import DESIRED_ORDER as _DO3
                    fb_body = {
                        "query": {
                            "bool": {
                                "must": [
                                    {"term": {"File Name": "netspeed.csv"}}
                                ],
                                "should": [
                                    {"term": {"MAC Address.keyword": mac_upper_fb}},
                                    {"term": {"MAC Address 2.keyword": mac_upper_fb}},
                                    {"term": {"MAC Address 2.keyword": f"SEP{mac_upper_fb}"}},
                                    {"wildcard": {"MAC Address.keyword": f"*{mac_upper_fb}*"}},
                                    {"wildcard": {"MAC Address 2.keyword": f"*{mac_upper_fb}*"}}
                                ],
                                "minimum_should_match": 1
                            }
                        },
                        "_source": _DO3,
                        "size": 200
                    }
                    logger.info("[MAC-fallback] searching netspeed_* for File Name=netspeed.csv")
                    resp_fb = self.client.search(index=["netspeed_*"], body=fb_body)
                    docs_fb = [h.get('_source', {}) for h in resp_fb.get('hits', {}).get('hits', [])]
                    if docs_fb:
                        unique_documents.extend(docs_fb)
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
            def get_file_priority(doc):
                file_name = doc.get('File Name', '')

                if file_name == 'netspeed.csv':
                    return (0, 0) # Always first
                elif file_name.startswith('netspeed.csv.'):
                    try:
                        suffix = file_name.split('netspeed.csv.')[1]
                        file_number = int(suffix)
                        # Group netspeed files together, then sort by file number
                        # Use padding to ensure proper numeric order: 0, 1, 2, 3, ..., 10, 11, etc.
                        return (1, file_number)
                    except (IndexError, ValueError):
                        return (999, 999)
                else:
                    return (1000, 0)

            try:
                # Only enforce file priority order for MAC searches with historical enabled.
                # For general queries, keep OpenSearch's sort so exact field matches stay on top.
                if looks_like_mac_seed and include_historical:
                    unique_documents.sort(key=get_file_priority)
                    logger.info(f"Sorted {len(unique_documents)} unique documents by file name priority (MAC+historical)")
                    for i, doc in enumerate(unique_documents[:15]):
                        priority = get_file_priority(doc)
                        logger.info(f"  {i+1}. {doc.get('File Name', 'unknown')} - Priority: {priority}")
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
            from utils.csv_utils import DESIRED_ORDER

            # Enhance documents with KEM information in Line Number field for icon display
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

                enhanced_documents.append(enhanced_doc)

            # Filter documents to only include desired columns
            filtered_documents = []
            for doc in enhanced_documents:
                filtered_doc = {}
                for header in DESIRED_ORDER:
                    if header in doc:
                        filtered_doc[header] = doc[header]
                filtered_documents.append(filtered_doc)

            # Use only desired headers that exist in the filtered data
            headers = [h for h in DESIRED_ORDER if any(h in doc for doc in filtered_documents)]

            logger.info(f"Found {len(filtered_documents)} unique results for query '{query}' from {len(documents)} total matches")
            return headers, filtered_documents

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