from opensearchpy import OpenSearch, helpers
from config import settings
import logging
from pathlib import Path
from typing import List, Dict, Any, Generator, Optional, Tuple
from .csv_utils import read_csv_file


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ElasticConfig:
    """OpenSearch configuration and client management."""
    
    def __init__(self):
        """Initialize OpenSearch configuration."""
        self.hosts = [settings.OPENSEARCH_URL]
        self._client = None
        self.index_mappings = {
            "mappings": {
                "properties": {
                    "File Name": {"type": "keyword"},
                    "Creation Date": {
                        "type": "date",
                        "format": (
                            "yyyy-MM-dd HH:mm:ss||"
                            "yyyy-MM-dd||epoch_millis"
                        )
                    },
                    "IP Address": {"type": "ip"},
                    "Line Number": {"type": "keyword"},
                    "MAC Address": {"type": "keyword"},
                    "MAC Address 2": {"type": "keyword"},
                    "Serial Number": {"type": "keyword"},
                    "Model Name": {"type": "text"},
                    "Subnet Mask": {"type": "keyword"},
                    "Voice VLAN": {"type": "keyword"},
                    "Switch Hostname": {"type": "keyword"},
                    "Switch Port": {"type": "keyword"},
                    "Speed 1": {"type": "keyword"},
                    "Speed 2": {"type": "keyword"},
                    "Speed 3": {"type": "keyword"},
                    "Speed 4": {"type": "keyword"},
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
            self._client = OpenSearch(
                hosts=self.hosts,
                http_auth=('admin', 'Alterichkotzepass23$'),  # Basic authentication
                verify_certs=False,  # Skip SSL verification
                ssl_show_warn=False,  # Suppress SSL warnings
                request_timeout=30,  # 30 second timeout
                retry_on_timeout=True,
                max_retries=3
            )
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
                # Search all netspeed indices
                return ["netspeed_*"]
            else:
                # If netspeed_netspeed exists, use that, otherwise use all indices
                if "netspeed_netspeed" in indices:
                    return ["netspeed_netspeed"]
                else:
                    netspeed_indices = [idx for idx in indices if idx.startswith("netspeed_")]
                    if netspeed_indices:
                        logger.info(f"No netspeed_netspeed index found, using: {netspeed_indices}")
                        return netspeed_indices
                    else:
                        # If no netspeed indices found, use all indices as fallback
                        logger.warning(f"No netspeed indices found, using all indices")
                        return ["*"]
        except Exception as e:
            logger.error(f"Error getting search indices: {e}")
            # Fallback to default behavior
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
            self.client.indices.delete(index=index_name)
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
            
            # Construct query
            if field:
                query_body = {
                    "query": {
                        "match": {
                            field: query
                        }
                    },
                    "size": size
                }
            else:
                # More flexible query that will match partial words
                query_body = {
                    "query": {
                        "bool": {
                            "should": [
                                # Full-text search across all text fields
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["*"],
                                        "type": "best_fields",
                                        "fuzziness": "AUTO"
                                    }
                                },
                                # Also do a wildcard search for partial matches
                                {
                                    "query_string": {
                                        "query": f"*{query}*",
                                        "fields": ["*"]
                                    }
                                }
                            ]
                        }
                    },
                    "size": size
                }
                
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
            
            # Get headers (fields)
            headers = sorted(set().union(*(doc.keys() for doc in documents))) if documents else []
            
            logger.info(f"Found {len(documents)} results for query '{query}'")
            return headers, documents
            
        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}")
            return [], []


# Create a global instance
elastic_config = ElasticConfig()
