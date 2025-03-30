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
                        "format": "yyyy-MM-dd"
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
            
            # Handle Creation Date format specifically to ensure it matches the mapping
            if "Creation Date" in doc:
                try:
                    # Get the file's Linux creation date using stat command
                    import subprocess
                    
                    # Use Linux stat command to get creation date
                    process = subprocess.run(
                        ["stat", "-c", "%w", file_path],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    creation_time_str = process.stdout.strip()
                    # Parse the datetime string and format for indexing
                    creation_date = creation_time_str.split()[0]  # Extract just the date part
                    doc["Creation Date"] = creation_date
                    logger.info(f"Formatted Linux Creation Date for indexing: {doc['Creation Date']}")
                except Exception as e:
                    logger.warning(f"Error getting Linux creation date: {e}, falling back to modification time")
                    try:
                        # Fallback to modification time if stat command fails
                        file_path_obj = Path(file_path)
                        creation_timestamp = file_path_obj.stat().st_mtime
                        creation_date = datetime.fromtimestamp(creation_timestamp).strftime('%Y-%m-%d')
                        doc["Creation Date"] = creation_date
                    except Exception as inner_e:
                        logger.warning(f"Error getting fallback date: {inner_e}, using original: {doc.get('Creation Date', '')}")

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
        # Log what kind of query we're building for debugging
        logger.info(f"Building query body for query: {query}, field: {field}, size: {size}")

        if field:
            # Field-specific search with both exact and partial matching
            return {
                "query": {
                    "bool": {
                        "should": [
                            # Exact match
                            {"term": {field: query}},
                            # Prefix match
                            {"prefix": {field: query}},
                            # Wildcard for partial match
                            {"wildcard": {field: f"*{query}*"}}
                        ],
                        "minimum_should_match": 1
                    }
                },
                "size": size
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
                            
                            # Add case-insensitive wildcard search for all text/keyword fields
                            # MAC Address fields
                            {"wildcard": {"MAC Address": f"*{query.lower()}*"}},
                            {"wildcard": {"MAC Address": f"*{query.upper()}*"}},
                            {"wildcard": {"MAC Address 2": f"*{query.lower()}*"}},
                            {"wildcard": {"MAC Address 2": f"*{query.upper()}*"}},
                            
                            # Serial Number and IDs
                            {"wildcard": {"Serial Number": f"*{query.lower()}*"}},
                            {"wildcard": {"Serial Number": f"*{query.upper()}*"}},
                            {"wildcard": {"Line Number": f"*{query}*"}},
                            
                            # Network/Switch related fields
                            {"wildcard": {"Switch Hostname": f"*{query.lower()}*"}},
                            {"wildcard": {"Switch Hostname": f"*{query.upper()}*"}},
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
                            {"wildcard": {"File Name": f"*{query}*"}}
                            
                            # Fuzzy matching disabled per user request
                            # {"fuzzy": {"MAC Address": {"value": query, "fuzziness": "AUTO"}}},
                            # {"fuzzy": {"Model Name": {"value": query, "fuzziness": "AUTO"}}}
                        ],
                        "minimum_should_match": 1
                    }
                },
                "size": size
            }
            
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
            logger.info(f"Final search query: {search_query}")
            
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
