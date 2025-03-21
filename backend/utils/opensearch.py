from opensearchpy import OpenSearch, helpers
from config import settings
import logging
from pathlib import Path
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
        # Define field types for reuse
        self.keyword_type = {"type": "keyword"}
        self.text_with_keyword = {
            "type": "text",
            "fields": {
                "keyword": {"type": "keyword"}
            }
        }

        self.index_mappings = {
            "mappings": {
                "properties": {
                    "File Name": self.keyword_type,
                    "Creation Date": {
                        "type": "date",
                        "format": (
                            "yyyy-MM-dd HH:mm:ss||"
                            "yyyy-MM-dd||epoch_millis"
                        )
                    },
                    "IP Address": {"type": "ip"},
                    "Line Number": self.keyword_type,
                    "MAC Address": self.text_with_keyword,
                    "MAC Address 2": self.text_with_keyword,
                    "Serial Number": self.keyword_type,
                    "Model Name": {"type": "text"},
                    "Subnet Mask": self.keyword_type,
                    "Voice VLAN": self.keyword_type,
                    "Switch Hostname": self.keyword_type,
                    "Switch Port": self.keyword_type,
                    "Speed 1": self.keyword_type,
                    "Speed 2": self.keyword_type,
                    "Speed 3": self.keyword_type,
                    "Speed 4": self.keyword_type,
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "max_result_window": 20000  # Increase from default 10000
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
                # If including historical files, search all indices starting with "netspeed_"
                return ["netspeed_*"]
            else:
                # If not including historical files, search only the "netspeed_netspeed" index if it exists
                if "netspeed_netspeed" in indices:
                    return ["netspeed_netspeed"]
                else:
                    # If the main index doesn't exist, return all netspeed indices as a fallback
                    netspeed_indices = [idx for idx in indices if idx.startswith("netspeed_")]
                    if netspeed_indices:
                        logger.warning(
                            f"No netspeed_netspeed index found, using all netspeed indices as fallback: {netspeed_indices}"
                        )
                        return netspeed_indices
                    else:
                        logger.warning("No netspeed indices found, using all indices")
                        return ["*"]
        except Exception as e:
            logger.error(f"Error getting search indices: {e}")
            return ["netspeed_*"] if include_historical else ["netspeed_netspeed"]

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
        Generate actions for bulk indexing.

        Args:
            index_name: Name of the index to index into
            file_path: Path to the CSV file to index

        Yields:
            Dict[str, Any]: Action for bulk indexing
        """
        _, rows = read_csv_file(file_path)

        for row in rows:
            # Clean up data as needed (handle nulls, etc.)
            doc = {k: (v if v else "") for k, v in row.items()}
            
            # Convert all values to strings to avoid mapping errors
            doc = {k: str(v) for k, v in doc.items()}

            yield {
                "_index": index_name,
                "_source": doc
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

            # Bulk index documents
            success, failed = helpers.bulk(
                self.client,
                self.generate_actions(index_name, file_path),
                refresh=True  # Make documents immediately available for search
            )

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
        if field:
            return {
                "query": {
                    "match": {
                        field: query
                    }
                },
                "size": size
            }
        else:
            # Construct precise search query
            return {
                "query": {
                    "bool": {
                        "should": [
                            # Exact match search across fields
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["*"],
                                    "type": "best_fields"
                                }
                            },
                            # Exact match for Line Number without prefix
                            {
                                "term": {
                                    "Line Number": query
                                }
                            },
                            # Exact match for MAC Address
                            {
                                "term": {
                                    "MAC Address": query
                                }
                            },
                            # Exact match for Line Number with plus prefix
                            {
                                "term": {
                                    "Line Number": f"+{query}"
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                },
                "size": size
            }

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
            # Get indices to search
            indices = self.get_search_indices(include_historical)

            # Build query
            query_body = self._build_query_body(query, field, size)

            # Log the query for debugging
            logger.info(f"Search query: indices={indices}, query={query_body}")

            # Execute search
            response = self.client.search(
                index=indices,
                body=query_body
            )

            # Log response for debugging
            logger.info(f"Search response: {response}")

            # Extract results
            hits = response["hits"]["hits"]
            documents = [hit["_source"] for hit in hits]

            # Deduplicate documents
            unique_documents = self._deduplicate_documents(documents)
            
            # Get headers (fields)
            headers = sorted(set().union(*(doc.keys() for doc in unique_documents))) if unique_documents else []

            logger.info(f"Found {len(unique_documents)} unique results for query '{query}' from {len(documents)} total matches")
            return headers, unique_documents

        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}")
            return [], []


# Create a global instance
opensearch_config = OpenSearchConfig()
