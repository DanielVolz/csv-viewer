from opensearchpy import OpenSearch, helpers
from config import settings
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Generator, Optional, Tuple
from .csv_utils import read_csv_file


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenSearchConfig:
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
        """Initialize OpenSearch configuration."""
        self.hosts = [settings.OPENSEARCH_URL]
        self._client = None
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
                    "Speed 1": self.keyword_type,
                    "Speed 2": self.keyword_type,
                    "Speed Switch-Port": self.keyword_type,
                    "Speed PC-Port": self.keyword_type,
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
                    "phonesWithKEM": {"type": "long"}
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
            # Create client with connection parameters
            opensearch_params = {
                'hosts': self.hosts,
                'http_auth': ('admin', settings.OPENSEARCH_PASSWORD),  # Use from settings
                'verify_certs': False,
                'ssl_show_warn': False,
                'request_timeout': 30,
                'retry_on_timeout': True,
                'max_retries': 3
            }
            self._client = OpenSearch(**opensearch_params)
            # Test connection
            try:
                if self._client.ping():
                    logger.info("Successfully connected to OpenSearch")
                else:
                    logger.warning("Could not connect to OpenSearch")
            except Exception as e:
                logger.error(f"Error connecting to OpenSearch: {e}")

        return self._client

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

            if include_historical:
                # If including historical files, prefer the current index first (if present)
                # and then include all netspeed_* indices. This guarantees the current file
                # (netspeed.csv) is part of the search even if wildcard expansion behaves unexpectedly
                # in some environments.
                current_index = "netspeed_netspeed_csv"
                legacy_index = "netspeed_netspeed"  # backward-compat older naming
                ordered: list[str] = []
                if current_index in indices:
                    ordered.append(current_index)
                elif legacy_index in indices:
                    ordered.append(legacy_index)
                # Add wildcard covering only canonical netspeed.csv.N indices (exclude archives)
                ordered.append("netspeed_netspeed_csv_*")
                return ordered
            else:
                # If not including historical files, search only the current netspeed file index
                # A netspeed.csv file should be indexed as "netspeed_netspeed_csv"
                current_index = "netspeed_netspeed_csv"

                # Check if the current index exists
                if current_index in indices:
                    return [current_index]
                elif "netspeed_netspeed" in indices:
                    # Backward compatibility for older index naming
                    return ["netspeed_netspeed"]
                else:
                    # If no appropriate index is found, log a warning but don't default to all indices
                    logger.warning("No current netspeed index found. Search results may be empty.")
                    # Return a non-existent index name to ensure no results rather than wrong results
                    return ["netspeed_current_only"]
        except Exception as e:
            logger.error(f"Error getting search indices: {e}")
            return ["netspeed_*"] if include_historical else ["netspeed_current_only"]

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

    def index_stats_location_snapshots(self, *, file: str, date: str | None, loc_docs: List[Dict[str, Any]]) -> bool:
        """Bulk index per-location snapshot docs for a given file/date.

        Each doc in loc_docs must contain: { key, mode='code', totalPhones, totalSwitches, phonesWithKEM }
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
                self.purge_archive_older_than_years(4)
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
            # Use FileModel to get the proper date calculation
            try:
                from models.file import FileModel
                file_model = FileModel.from_path(file_path)

                if file_model.date:
                    file_creation_date = file_model.date.strftime('%Y-%m-%d')
                    logger.info(f"Using FileModel date for {file_path}: {file_creation_date}")
                else:
                    raise ValueError("FileModel returned no date")
            except (ImportError, ValueError) as model_error:
                logger.warning(f"FileModel not available for {file_path}: {model_error}, using fallback calculation")
                # Fallback to manual calculation if FileModel fails
                file_name = Path(file_path).name.lower()
                if file_name.startswith("netspeed.csv"):
                    from datetime import datetime, timedelta

                    # Get today's date
                    today = datetime.now().date()

                    if file_name == "netspeed.csv":
                        # Current file = today
                        file_creation_date = today.strftime('%Y-%m-%d')
                    elif file_name.startswith("netspeed.csv."):
                        try:
                            # Extract number after the dot (e.g., "netspeed.csv.1" -> 1)
                            suffix = file_name.split("netspeed.csv.")[1]
                            days_back = int(suffix)

                            # Special handling for .0 file - it should be 1 day back (yesterday)
                            if days_back == 0:
                                days_back = 1
                            else:
                                # For .1, .2, etc. add 1 more day since .0 is already yesterday
                                days_back = days_back + 1

                            # Calculate date: today minus days_back
                            file_date = today - timedelta(days=days_back)
                            file_creation_date = file_date.strftime('%Y-%m-%d')
                            logger.info(f"Calculated fallback date for {file_path}: {file_creation_date} (today - {days_back} days)")
                        except (IndexError, ValueError) as e:
                            logger.warning(f"Error parsing netspeed file suffix '{file_name}': {e}")
                            # Final fallback to filesystem timestamp
                            file_path_obj = Path(file_path)
                            creation_timestamp = file_path_obj.stat().st_mtime
                            file_creation_date = datetime.fromtimestamp(creation_timestamp).strftime('%Y-%m-%d')
                else:
                    # For non-netspeed files, use filesystem timestamp
                    from datetime import datetime
                    file_path_obj = Path(file_path)
                    creation_timestamp = file_path_obj.stat().st_mtime
                    file_creation_date = datetime.fromtimestamp(creation_timestamp).strftime('%Y-%m-%d')

        except Exception as e:
            logger.warning(f"Error getting file creation date for {file_path}: {e}, using filesystem fallback")
            try:
                # Final fallback to filesystem timestamp
                from datetime import datetime
                file_path_obj = Path(file_path)
                creation_timestamp = file_path_obj.stat().st_mtime
                file_creation_date = datetime.fromtimestamp(creation_timestamp).strftime('%Y-%m-%d')
            except Exception as inner_e:
                logger.warning(f"Error getting fallback date: {inner_e}")
                from datetime import datetime
                file_creation_date = datetime.now().strftime('%Y-%m-%d')

        # Import DESIRED_ORDER for consistent column filtering
        from utils.csv_utils import DESIRED_ORDER

        for row in rows:
            # Clean up data as needed (handle nulls, etc.)
            doc = {k: (v if v else "") for k, v in row.items()}

            # Use the pre-calculated file creation date
            if "Creation Date" in doc and file_creation_date:
                doc["Creation Date"] = file_creation_date

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
        logger.debug(f"Building query body for query: {query}, field: {field}, size: {size}")

        if field:
            from utils.csv_utils import DESIRED_ORDER
            # Phone-like Line Number exact-only
            if field == "Line Number" and isinstance(query, str):
                qn = query.strip()
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
                            {"_script": {"type": "number", "order": "asc", "script": {
                                "lang": "painless",
                                "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                                "params": {"f": "netspeed.csv"}
                            }}},
                            {"_score": {"order": "desc"}}
                        ]
                    }

            # Switch Port exact-only
            if field == "Switch Port":
                # Enforce exact match ignoring surrounding spaces and case
                return {
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "script": {
                                        "script": {
                                            "lang": "painless",
                                            "source": "return doc.containsKey('Switch Port') && doc['Switch Port'].size()>0 && doc['Switch Port'].value != null && doc['Switch Port'].value.trim().equalsIgnoreCase(params.q.trim());",
                                            "params": {"q": str(query)}
                                        }
                                    }
                                }
                            ],
                            "should": [
                                {"term": {"Switch Port": query}}
                            ],
                            "minimum_should_match": 0
                        }
                    },
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [{"Creation Date": {"order": "desc"}}, {"_score": {"order": "desc"}}]
                }

            # MAC exact-only when 12-hex provided
            if field in ("MAC Address", "MAC Address 2") and isinstance(query, str):
                mac_core = re.sub(r"[^A-Fa-f0-9]", "", query)
                if len(mac_core) == 12:
                    mac_up = mac_core.upper()
                    target_field = f"{field}.keyword"
                    should = [{"term": {target_field: mac_up}}]
                    if field == "MAC Address 2":
                        should.append({"term": {target_field: f"SEP{mac_up}"}})
                    return {
                        "query": {"bool": {"should": should, "minimum_should_match": 1}},
                        "_source": DESIRED_ORDER,
                        "size": size,
                        "sort": [{"Creation Date": {"order": "desc"}}, {"_score": {"order": "desc"}}]
                    }

            # IP search: exact for full IPv4, partial support for prefixes (e.g., 10., 10.20, 10.20.30)
            if field == "IP Address" and isinstance(query, str):
                qip = query.strip()
                full_ipv4 = re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", qip or "") is not None
                if full_ipv4:
                    return {
                        "query": {"bool": {"must": [{"term": {"IP Address.keyword": qip}}]}},
                        "_source": DESIRED_ORDER,
                        "size": size,
                        "sort": [{"Creation Date": {"order": "desc"}}, {"_score": {"order": "desc"}}]
                    }
                # Partial IP prefix (1-3 octets, optional trailing dot)
                if re.fullmatch(r"\d{1,3}(\.\d{1,3}){0,2}\.??", qip or "") or re.fullmatch(r"\d{1,3}(\.\d{1,3}){0,2}", qip or ""):
                    clean = qip.rstrip('.')
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
            eff_field = f"{field}.keyword" if field in ("Line Number", "MAC Address", "MAC Address 2") else field
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
                }, {"Creation Date": {"order": "desc"}}, {"_score": {"order": "desc"}}]
            }

        # General search across all fields
        if isinstance(query, str):
            qn = query.strip()
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
                    "sort": [{"Creation Date": {"order": "desc"}}, {
                        "_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                            "params": {"f": "netspeed.csv"}
                        }}
                    }]
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

            # Switch Hostname-like (FQDN) exact-only: contains dot and letters (not IP)
            if any(c.isalpha() for c in qn) and "." in qn and "/" not in qn and " " not in qn:
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
                        {"_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                            "params": {"f": "netspeed.csv"}
                        }}},
                        {"_score": {"order": "desc"}}
                    ]
                }

            # Switch Hostname pattern without domain: 3 letters + 2 digits + other chars (like ABx01ZSL5210P)
            hostname_pattern_match = re.match(r'^[A-Za-z]{3}[0-9]{2}', qn or "") if qn else None
            if hostname_pattern_match and '.' not in qn and len(qn) >= 13:
                from utils.csv_utils import DESIRED_ORDER
                return {
                    "query": {
                        "bool": {
                            "should": [
                                # Exact match for hostname without domain
                                {"term": {"Switch Hostname.keyword": qn}},
                                {"term": {"Switch Hostname.keyword": qn.lower()}},
                                {"term": {"Switch Hostname.keyword": qn.upper()}},

                                # Prefix match for full hostname with domain
                                {"prefix": {"Switch Hostname": f"{qn}."}},
                                {"prefix": {"Switch Hostname": f"{qn.lower()}."}},
                                {"prefix": {"Switch Hostname": f"{qn.upper()}."}},
                            ],
                            "minimum_should_match": 1
                        }
                    },
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [
                        {"Creation Date": {"order": "desc"}},
                        {"_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                            "params": {"f": "netspeed.csv"}
                        }}},
                        {"_score": {"order": "desc"}}
                    ]
                }

            # Full IPv4 exact-only
            if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", qn or ""):
                from utils.csv_utils import DESIRED_ORDER
                return {
                    "query": {"bool": {"must": [{"term": {"IP Address.keyword": qn}}]}},
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [{"Creation Date": {"order": "desc"}}, {
                        "_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                            "params": {"f": "netspeed.csv"}
                        }}
                    }]
                }

            # Partial IPv4 prefix-only (e.g., "10.216.73." or "192.168.")
            if re.fullmatch(r"\d{1,3}(\.\d{1,3}){0,2}\.?", qn or ""):
                from utils.csv_utils import DESIRED_ORDER
                clean_query = qn.rstrip('.')
                return {
                    "query": {"bool": {"should": [
                        {"prefix": {"IP Address.keyword": clean_query}},
                        {"prefix": {"IP Address.keyword": f"{clean_query}."}}
                    ], "minimum_should_match": 1}},
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [{"Creation Date": {"order": "desc"}}, {
                        "_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                            "params": {"f": "netspeed.csv"}
                        }}
                    }]
                }

            # Switch Port pattern exact-only
            if '/' in qn and len(qn) >= 5:
                from utils.csv_utils import DESIRED_ORDER
                # Enforce exact match ignoring surrounding spaces and case
                return {
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "script": {
                                        "script": {
                                            "lang": "painless",
                                            "source": "return doc.containsKey('Switch Port') && doc['Switch Port'].size()>0 && doc['Switch Port'].value != null && doc['Switch Port'].value.trim().equalsIgnoreCase(params.q.trim());",
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
                    "sort": [{"Creation Date": {"order": "desc"}}, {
                        "_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                            "params": {"f": "netspeed.csv"}
                        }}
                    }]
                }

            # Serial Number exact-only (general): full-length alphanumeric token (11+ chars, not pure digits, not hostname)
            alphanumeric_11_plus = re.fullmatch(r"[A-Za-z0-9]{11,}", qn or "") and not re.fullmatch(r"\d{11,}", qn or "")
            hostname_pattern_match = re.match(r'^[A-Za-z]{3}[0-9]{2}', qn or "") if qn else None
            if alphanumeric_11_plus and not hostname_pattern_match:
                from utils.csv_utils import DESIRED_ORDER
                variants = [qn]
                up = qn.upper()
                if up != qn:
                    variants.append(up)
                return {
                    "query": {"bool": {"should": [
                        *([{ "term": {"Serial Number": v} } for v in variants])
                    ], "minimum_should_match": 1}},
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [{"Creation Date": {"order": "desc"}}, {
                        "_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                            "params": {"f": "netspeed.csv"}
                        }}
                    }, {"_score": {"order": "desc"}}]
                }

            # Serial Number prefix (general): partial alphanumeric token for prefix search (3-10 chars)
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9]{2,9}", qn or ""):
                from utils.csv_utils import DESIRED_ORDER
                variants = [qn]
                up = qn.upper()
                if up != qn:
                    variants.append(up)
                return {
                    "query": {"bool": {"should": [
                        *([{ "wildcard": {"Serial Number": f"{v}*"} } for v in variants])
                    ], "minimum_should_match": 1}},
                    "_source": DESIRED_ORDER,
                    "size": size,
                    "sort": [{"Creation Date": {"order": "desc"}}, {
                        "_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                            "params": {"f": "netspeed.csv"}
                        }}
                    }, {"_score": {"order": "desc"}}]
                }

            # Phone-like exact-only
            if re.fullmatch(r"\+?\d{7,}", qn or ""):
                from utils.csv_utils import DESIRED_ORDER
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
                    "sort": [{"Creation Date": {"order": "desc"}}, {
                        "_script": {"type": "number", "order": "asc", "script": {
                            "lang": "painless",
                            "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                            "params": {"f": "netspeed.csv"}
                        }}
                    }, {"_score": {"order": "desc"}}]
                }

            # Model-like pattern (e.g., "8851", "7841") - focus search ONLY on exact Model Name matches
            if re.fullmatch(r"\d{4}", qn or ""):
                from utils.csv_utils import DESIRED_ORDER
                return {
                    "query": {"bool": {"should": [
                        # ONLY exact model name matches - no wildcards or other fields
                        {"term": {"Model Name.keyword": f"CP-{qn}"}},
                        {"term": {"Model Name.keyword": f"DP-{qn}"}},
                        # Also add text matches for the exact patterns
                        {"match": {"Model Name": f"CP-{qn}"}},
                        {"match": {"Model Name": f"DP-{qn}"}}
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

        # Broad query: allow partials but with exact-first sort
        # Exclude multi_match for hostname patterns to prevent false matches
        is_hostname_pattern = isinstance(query, str) and len(query) >= 5 and re.match(r'^[A-Za-z]{3}[0-9]{2}', query)

        search_query = {
            "query": {"bool": {"should": [
                {"term": {"Switch Port": {"value": query, "boost": 10.0}}},
                *([] if is_hostname_pattern else [{"multi_match": {"query": query, "fields": ["*"]}}]),
                {"term": {"Line Number.keyword": query}},
                {"term": {"MAC Address": query}},
                {"term": {"Line Number.keyword": f"+{query}"}},
                {"term": {"File Name": {"value": "netspeed.csv", "boost": 2.0}}},

                {"wildcard": {"MAC Address.keyword": f"*{str(query).lower()}*"}},
                {"wildcard": {"MAC Address.keyword": f"*{str(query).upper()}*"}},
                {"wildcard": {"MAC Address 2.keyword": f"*{str(query).lower()}*"}},
                {"wildcard": {"MAC Address 2.keyword": f"*{str(query).upper()}*"}},

                # Serial Number wildcards for partial matches (only if not hostname-like)
                *([] if isinstance(query, str) and len(query) >= 5 and re.match(r'^[A-Za-z]{3}[0-9]{2}', query) else [
                    {"wildcard": {"Serial Number": f"*{str(query).lower()}*"}},
                    {"wildcard": {"Serial Number": f"*{str(query).upper()}*"}},
                ]),

                # No Serial Number wildcards to keep serial searches exact-only
                                {"wildcard": {"Line Number.keyword": f"*{query}*"}},
                                *([ {"wildcard": {"Line Number.keyword": f"*{str(query).lstrip('+')}*"}} ]
                  if str(query).startswith('+') and str(query).lstrip('+') else
                                    [ {"wildcard": {"Line Number.keyword": f"*+{query}*"}} ]),


                {"wildcard": {"Switch Port": f"*{query}*"}},
                {"wildcard": {"Subnet Mask": f"*{query}*"}},
                {"wildcard": {"Voice VLAN": f"*{query}*"}},

                {"wildcard": {"Speed 1": f"*{query}*"}},
                {"wildcard": {"Speed 2": f"*{query}*"}},
                {"wildcard": {"Speed 3": f"*{query}*"}},
                {"wildcard": {"Speed 4": f"*{query}*"}},

                {"wildcard": {"Model Name": f"*{str(query).lower()}*"}},
                {"wildcard": {"Model Name": f"*{str(query).upper()}*"}},
                {"wildcard": {"File Name": f"*{query}*"}}
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

        from utils.csv_utils import DESIRED_ORDER
        search_query["_source"] = DESIRED_ORDER

        search_query["sort"] = [
            {"_script": {"type": "number", "order": "asc", "script": {
                "lang": "painless",
                "source": "def q = params.q; if (q == null) return 1; if (doc.containsKey('Switch Port') && doc['Switch Port'].size()>0 && doc['Switch Port'].value == q) return 0; if (doc.containsKey('Line Number.keyword') && doc['Line Number.keyword'].size()>0 && doc['Line Number.keyword'].value == q) return 0; if (doc.containsKey('MAC Address.keyword') && doc['MAC Address.keyword'].size()>0 && doc['MAC Address.keyword'].value == q) return 0; if (doc.containsKey('MAC Address 2.keyword') && doc['MAC Address 2.keyword'].size()>0 && doc['MAC Address 2.keyword'].value == q) return 0; if (doc.containsKey('IP Address.keyword') && doc['IP Address.keyword'].size()>0 && doc['IP Address.keyword'].value == q) return 0; if (doc.containsKey('Serial Number') && doc['Serial Number'].size()>0 && doc['Serial Number'].value == q) return 0; return 1;",
                "params": {"q": query}
            }}},
            {"Creation Date": {"order": "desc"}},
            {"_script": {"type": "number", "order": "asc", "script": {
                "lang": "painless",
                "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                "params": {"f": "netspeed.csv"}
            }}},
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
                    targeted_first = {
                        "query": {
                            "bool": {
                                "must": [
                                    {"term": {"File Name": "netspeed.csv"}}
                                ],
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
                        from pathlib import Path as _Path
                        data_dir = _Path('/app/data')
                        netspeed_files: List[str] = []
                        if data_dir.exists():
                            for p in sorted(data_dir.glob('netspeed.csv*'), key=lambda x: x.name):
                                n = p.name
                                if n == 'netspeed.csv' or (n.startswith('netspeed.csv.') and n.replace('netspeed.csv.', '').isdigit()):
                                    netspeed_files.append(n)
                        def _prio(name: str):
                            if name == 'netspeed.csv':
                                return (0, 0)
                            try:
                                return (1, int(name.split('netspeed.csv.')[1]))
                            except Exception:
                                return (999, 999)
                        netspeed_files.sort(key=_prio)

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
                        "sort": [{"Creation Date": {"order": "desc"}}, {
                            "_script": {"type": "number", "order": "asc", "script": {
                                "lang": "painless",
                                "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                                "params": {"f": "netspeed.csv"}
                            }}
                        }, {"_score": {"order": "desc"}}]
                    }
                    logger.info(f"[SERIAL] indices={indices_sn} body={body_sn}")
                    resp_sn = self.client.search(index=indices_sn, body=body_sn)
                    docs_sn = [h.get('_source', {}) for h in resp_sn.get('hits', {}).get('hits', [])]
                    # Filter out archived filenames; keep only netspeed.csv and netspeed.csv.N
                    def _is_allowed_file(fn: str) -> bool:
                        if not fn:
                            return False
                        if fn == 'netspeed.csv':
                            return True
                        if fn.startswith('netspeed.csv.'):
                            suf = fn.split('netspeed.csv.', 1)[1]
                            return suf.isdigit()
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
                            {"_script": {"type": "number", "order": "asc", "script": {
                                "lang": "painless",
                                "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                                "params": {"f": "netspeed.csv"}
                            }}}
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
                        if fn.startswith('netspeed.csv.'):
                            suf = fn.split('netspeed.csv.', 1)[1]
                            return suf.isdigit()
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
            unique_documents = self._deduplicate_documents_preserve_order(documents)

            # Always restrict results to canonical netspeed files only:
            # - netspeed.csv
            # - netspeed.csv.N (where N is a number)
            def _is_allowed_file(fn: str) -> bool:
                if not fn:
                    return False
                if fn == 'netspeed.csv':
                    return True
                if fn.startswith('netspeed.csv.'):
                    suf = fn.split('netspeed.csv.', 1)[1]
                    return suf.isdigit()
                return False

            before_cnt = len(unique_documents)
            unique_documents = [d for d in unique_documents if _is_allowed_file((d.get('File Name') or '').strip())]
            after_cnt = len(unique_documents)
            if after_cnt != before_cnt:
                logger.info(f"Filtered out {before_cnt - after_cnt} non-canonical files (kept netspeed.csv and netspeed.csv.N only)")

            # (Removed) Hostname deduplication: return all exact matches for a host

            # For MAC-like searches, ensure at least one matching document per netspeed file present in /app/data
            # This guarantees all netspeed.csv* files show up in the results list
            try:
                mac_core_seed = canonical_mac
                looks_like_mac_seed = mac_core_seed is not None
            except Exception:
                looks_like_mac_seed = False
            if looks_like_mac_seed and include_historical:
                try:
                    from pathlib import Path as _Path
                    mac_upper_seed = str(mac_core_seed)
                    data_dir = _Path('/app/data')
                    netspeed_files = []
                    if data_dir.exists():
                        # Collect netspeed.csv and numeric suffixed history (.0, .1, ...)
                        for p in sorted(data_dir.glob('netspeed.csv*'), key=lambda x: x.name):
                            n = p.name
                            if n == 'netspeed.csv' or (n.startswith('netspeed.csv.') and n.replace('netspeed.csv.', '').isdigit()):
                                netspeed_files.append(n)
                    # Seed order: current first, then .0, .1, ...
                    def _seed_priority(name: str):
                        if name == 'netspeed.csv':
                            return (0, 0)
                        try:
                            return (1, int(name.split('netspeed.csv.')[1]))
                        except Exception:
                            return (999, 999)
                    netspeed_files.sort(key=_seed_priority)

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
                                # Search across netspeed_* indices; avoid relying on exact index per file
                                resp_seed = self.client.search(index=['netspeed_netspeed_csv_*'], body=seed_body)
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
                    # Build list of netspeed files from /app/data in desired order
                    from pathlib import Path as _Path
                    data_dir2 = _Path('/app/data')
                    netspeed_files2: List[str] = []
                    if data_dir2.exists():
                        for p in sorted(data_dir2.glob('netspeed.csv*'), key=lambda x: x.name):
                            n = p.name
                            if n == 'netspeed.csv' or (n.startswith('netspeed.csv.') and n.replace('netspeed.csv.', '').isdigit()):
                                netspeed_files2.append(n)
                    def _prio2(name: str):
                        if name == 'netspeed.csv':
                            return (0, 0)
                        try:
                            return (1, int(name.split('netspeed.csv.')[1]))
                        except Exception:
                            return (999, 999)
                    netspeed_files2.sort(key=_prio2)

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
                    return (0, 0)  # Always first
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

            # Filter documents to only include desired columns
            filtered_documents = []
            for doc in unique_documents:
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

    def repair_current_file_after_indexing(self, current_file_path: str = "/app/data/netspeed.csv") -> Dict[str, Any]:
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


# Create a global instance
opensearch_config = OpenSearchConfig()
