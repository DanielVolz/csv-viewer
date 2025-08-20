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
                    "Model Name": {"type": "text"},
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
                # Add wildcard covering all netspeed indices (including the current one)
                ordered.append("netspeed_*")
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
        # Log what kind of query we're building for debugging
        logger.debug(f"Building query body for query: {query}, field: {field}, size: {size}")

        if field:
            # Field-specific search with both exact and partial matching
            from utils.csv_utils import DESIRED_ORDER
            should_clauses = [
                {"term": {field: query}},
                {"prefix": {field: query}},
                {"wildcard": {field: f"*{query}*"}}
            ]
            # Add cleaned variant if searching Line Number with leading '+'
            if field == "Line Number" and query.startswith('+'):
                cleaned = query.lstrip('+')
                if cleaned:
                    should_clauses.append({"wildcard": {field: f"*{cleaned}*"}})
            # Add case variants for MAC/IP if relevant
            if field in ("MAC Address", "MAC Address 2", "Model Name", "Switch Hostname") and query.lower() != query.upper():
                should_clauses.append({"wildcard": {field: f"*{query.lower()}*"}})
                should_clauses.append({"wildcard": {field: f"*{query.upper()}*"}})
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
                    {"_score": {"order": "desc"}}
                ]
            }
        else:
            # General search across all fields with improved partial matching
            search_query = {
                "query": {
                    "bool": {
                        "should": [
                            # Original exact matches
                            {"multi_match": {"query": query, "fields": ["*"]}},
                            {"term": {"Line Number": query}},
                            {"term": {"MAC Address": query}},
                            {"term": {"Line Number": f"+{query}"}},
                            # Prefer current file where applicable
                            {"term": {"File Name": {"value": "netspeed.csv", "boost": 2.0}}},

                            # Add case-insensitive wildcard search for all text/keyword fields
                            # MAC Address fields (use keyword subfields for wildcard substring search)
                            {"wildcard": {"MAC Address.keyword": f"*{query.lower()}*"}},
                            {"wildcard": {"MAC Address.keyword": f"*{query.upper()}*"}},
                            {"wildcard": {"MAC Address 2.keyword": f"*{query.lower()}*"}},
                            {"wildcard": {"MAC Address 2.keyword": f"*{query.upper()}*"}},

                            # Serial Number and IDs
                            {"wildcard": {"Serial Number": f"*{query.lower()}*"}},
                            {"wildcard": {"Serial Number": f"*{query.upper()}*"}},
                            {"wildcard": {"Line Number": f"*{query}*"}},
                            # Plus handling for line numbers
                            # If query starts with '+', also search without it; else add a variant with leading '+'
                            *(
                                [ {"wildcard": {"Line Number": f"*{query.lstrip('+')}*"}} ]
                                if query.startswith('+') and query.lstrip('+') else
                                [ {"wildcard": {"Line Number": f"*+{query}*"}} ]
                            ),

                            # Network/Switch related fields
                            {"wildcard": {"Switch Hostname": f"*{query.lower()}*"}},
                            {"wildcard": {"Switch Hostname": f"*{query.upper()}*"}},
                            # Lowercased subfield (requires reindex after mapping change)
                            {"wildcard": {"Switch Hostname.lower": f"*{query.lower()}*"}},
                            {"wildcard": {"Switch Port": f"*{query}*"}},
                            {"wildcard": {"Subnet Mask": f"*{query}*"}},
                            {"wildcard": {"Voice VLAN": f"*{query}*"}},

                            # Speed measurements
                            {"wildcard": {"Speed 1": f"*{query}*"}},
                            {"wildcard": {"Speed 2": f"*{query}*"}},
                            {"wildcard": {"Speed 3": f"*{query}*"}},
                            {"wildcard": {"Speed 4": f"*{query}*"}},

                            # Model and file information
                            {"wildcard": {"Model Name": f"*{query.lower()}*"}},
                            {"wildcard": {"Model Name": f"*{query.upper()}*"}},
                            {"wildcard": {"File Name": f"*{query}*"}},
                            # IP Address partial match (now text field) – allow substring search
                            {"wildcard": {"IP Address": f"*{query}*"}},
                            # Additional variants (lowercase already same for digits / dots)
                            # Add plus-handling expansion for numeric-like queries for safety in Line Number
                            # Already covered above but reinforce without duplication risk

                            # Fuzzy matching disabled per user request
                            # {"fuzzy": {"MAC Address": {"value": query, "fuzziness": "AUTO"}}},
                            # {"fuzzy": {"Model Name": {"value": query, "fuzziness": "AUTO"}}}
                        ],
                        "minimum_should_match": 1
                    }
                },
                "size": size
            }

            # Strengthen MAC address matching: try exact keyword matches and SEP-prefixed variant
            try:
                # Exact match on keyword subfields (case-sensitive)
                search_query["query"]["bool"]["should"].append({"term": {"MAC Address.keyword": query}})
                search_query["query"]["bool"]["should"].append({"term": {"MAC Address 2.keyword": query}})
                # Also try SEP-prefixed form on MAC Address 2
                if isinstance(query, str) and len(query) >= 12:
                    sep_variant = f"SEP{query.upper()}"
                    search_query["query"]["bool"]["should"].append({"term": {"MAC Address 2.keyword": sep_variant}})
            except Exception as e:
                logger.warning(f"Failed to add strengthened MAC keyword terms: {e}")

            # Add IP Address partial search with range query if query looks like a valid IP prefix
            # Use a regex that allows for trailing dots to handle formats like "10.0.0."
            ip_pattern = re.compile(r'^[0-9]{1,3}(\.[0-9]{1,3}){0,2}\.?$')
            if ip_pattern.match(query):
                try:
                    # For partial IP matching, we'll construct a range query
                    # If query = "10.0", search all IPs from "10.0.0.0" to "10.0.255.255"
                    # First strip any trailing dot for processing
                    clean_query = query.rstrip('.')
                    ip_parts = clean_query.split('.')

                    if 1 <= len(ip_parts) <= 3:  # Partial IP with 1-3 octets
                        # Construct lower bound
                        lower_bound = clean_query
                        while lower_bound.count('.') < 3:
                            lower_bound += ".0"

                        # Construct upper bound
                        upper_bound = clean_query
                        while upper_bound.count('.') < 3:
                            upper_bound += ".255"

                        # Add the range query
                        search_query["query"]["bool"]["should"].append({
                            "range": {
                                "IP Address": {
                                    "gte": lower_bound,
                                    "lte": upper_bound
                                }
                            }
                        })
                except Exception as e:
                    logger.warning(f"Failed to add IP range search for '{query}': {e}")

            # Log the final query for debugging
            logger.debug(f"Final search query: {search_query}")

            # Additional heuristic: if query is a long numeric substring (>=5 digits) and does not already start with '+',
            # add variant with leading '+' to increase chances of match in 'Line Number' field that may store it so.
            if query.isdigit() and len(query) >= 5:
                try:
                    pref_variant = f"+{query}"
                    search_query["query"]["bool"]["should"].append({"wildcard": {"Line Number": f"*{pref_variant}*"}})
                except Exception as e:
                    logger.warning(f"Failed to append plus-prefixed numeric variant for query '{query}': {e}")

            # For MAC addresses that might be entered without separators, add a flexible wildcard with removal of common separators
            if any(c.isalpha() for c in query) and len(query.replace(':','').replace('-','').replace('.','')) >= 6:
                mac_core = re.sub(r'[^A-Fa-f0-9]', '', query)
                if mac_core:
                    try:
                        search_query["query"]["bool"]["should"].append({"wildcard": {"MAC Address.keyword": f"*{mac_core.lower()}*"}})
                        search_query["query"]["bool"]["should"].append({"wildcard": {"MAC Address.keyword": f"*{mac_core.upper()}*"}})
                        search_query["query"]["bool"]["should"].append({"wildcard": {"MAC Address 2.keyword": f"*{mac_core.lower()}*"}})
                        search_query["query"]["bool"]["should"].append({"wildcard": {"MAC Address 2.keyword": f"*{mac_core.upper()}*"}})
                    except Exception as e:
                        logger.warning(f"Failed to add MAC core variants for '{query}': {e}")

            # For switch hostname partials ensure lowercase + uppercase variants already there; add dotted-segment fallback
            if '.' in query and any(c.isalpha() for c in query):
                try:
                    parts = [p for p in query.split('.') if p]
                    if len(parts) >= 2:
                        short = parts[0]
                        search_query["query"]["bool"]["should"].append({"wildcard": {"Switch Hostname": f"*{short.lower()}*"}})
                        search_query["query"]["bool"]["should"].append({"wildcard": {"Switch Hostname": f"*{short.upper()}*"}})
                except Exception as e:
                    logger.warning(f"Failed to add hostname short variants for '{query}': {e}")

            # Ensure model name case variants present for partial alphanumeric queries
            if any(c.isalpha() for c in query) and any(c.isdigit() for c in query):
                try:
                    search_query["query"]["bool"]["should"].append({"wildcard": {"Model Name": f"*{query.lower()}*"}})
                    search_query["query"]["bool"]["should"].append({"wildcard": {"Model Name": f"*{query.upper()}*"}})
                except Exception as e:
                    logger.warning(f"Failed to add model name variants for '{query}': {e}")

            # Add _source filtering to only return desired columns
            from utils.csv_utils import DESIRED_ORDER
            search_query["_source"] = DESIRED_ORDER

            # Add sorting by Creation Date then a tie-breaker to prioritize netspeed.csv
            search_query["sort"] = [
                {"Creation Date": {"order": "desc"}},
                {
                    "_script": {
                        "type": "number",
                        "order": "asc",
                        "script": {
                            "lang": "painless",
                            "source": "doc.containsKey('File Name') && doc['File Name'].size()>0 && doc['File Name'].value == params.f ? 0 : 1",
                            "params": {"f": "netspeed.csv"}
                        }
                    }
                },
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

            # If the query looks like a MAC, first search the current index only to prefer today's file
            try:
                mac_core_first = re.sub(r'[^A-Fa-f0-9]', '', query or '')
                looks_like_mac_first = isinstance(query, str) and len(mac_core_first) == 12
            except Exception:
                looks_like_mac_first = False

            if looks_like_mac_first:
                try:
                    curr_indices_first = self.get_search_indices(False)
                    mac_upper_first = mac_core_first.upper()
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
                        "_source": ["File Name", "Creation Date", "MAC Address", "MAC Address 2", "IP Address", "Line Number", "Switch Hostname", "Switch Port", "Serial Number", "Model Name"],
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

            # Now run the general search across the selected indices
            # For MAC-like queries, always include historical indices to list results from all netspeed.csv files
            indices = self.get_search_indices(True if looks_like_mac_first else include_historical)
            query_body = self._build_query_body(query, field, size)
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

            # If it's a MAC-like query and still no netspeed.csv in results, try a wildcard-indices fallback
            try:
                mac_core_fb = re.sub(r'[^A-Fa-f0-9]', '', query or '')
                looks_like_mac_fb = isinstance(query, str) and len(mac_core_fb) == 12
            except Exception:
                looks_like_mac_fb = False
            if looks_like_mac_fb and not any((d.get('File Name') or '') == 'netspeed.csv' for d in unique_documents):
                try:
                    mac_upper_fb = mac_core_fb.upper()
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
                        "_source": ["File Name", "Creation Date", "MAC Address", "MAC Address 2", "IP Address", "Line Number", "Switch Hostname", "Switch Port", "Serial Number", "Model Name"],
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
                # Sort by file name priority: netspeed.csv first, then .0, .1, .2, etc.
                unique_documents.sort(key=get_file_priority)
                logger.info(f"Sorted {len(unique_documents)} unique documents by file name priority")

                # Debug: Log first 15 sorted documents to see the order
                for i, doc in enumerate(unique_documents[:15]):
                    priority = get_file_priority(doc)
                    logger.info(f"  {i+1}. {doc.get('File Name', 'unknown')} - Priority: {priority}")

            except Exception as e:
                logger.warning(f"Error sorting documents by file name priority: {e}")

            # CSV fallback used during testing has been removed. Search relies on OpenSearch only.

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


# Create a global instance
opensearch_config = OpenSearchConfig()
