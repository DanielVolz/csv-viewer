from elasticsearch import Elasticsearch
from config import settings
import logging
from pathlib import Path


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ElasticConfig:
    """Elasticsearch configuration and client management."""
    
    def __init__(self):
        """Initialize Elasticsearch configuration."""
        self.hosts = [settings.ELASTICSEARCH_URL]
        self._client = None
    
    @property
    def client(self) -> Elasticsearch:
        """
        Get or create Elasticsearch client.
        
        Returns:
            Elasticsearch: Configured Elasticsearch client
        """
        if self._client is None:
            self._client = Elasticsearch(
                hosts=self.hosts,
                request_timeout=30,  # 30 second timeout
                retry_on_timeout=True,
                max_retries=3
            )
            # Test connection
            try:
                if self._client.ping():
                    logger.info("Successfully connected to Elasticsearch")
                else:
                    logger.warning("Could not connect to Elasticsearch")
            except Exception as e:
                logger.error(f"Error connecting to Elasticsearch: {e}")
                
        return self._client
    
    def get_index_name(self, file_path: str) -> str:
        """
        Generate index name for a CSV file.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            str: Index name for the file
        """
        """Get stem (filename without extension) and convert to lowercase."""
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
        if include_historical:
            # Search all netspeed indices
            return ["netspeed_*"]
        else:
            # Search only current netspeed index
            return ["netspeed_netspeed"]

# Create a global instance
elastic_config = ElasticConfig()
