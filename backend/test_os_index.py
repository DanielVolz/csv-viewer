#!/usr/bin/env python3

from utils.elastic import elastic_config
import sys
import logging

# Configure logging to console for this script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


logger = logging.getLogger("test_os_index")


def list_indices():
    """List all indices in OpenSearch"""
    try:
        # Test connection to OpenSearch
        if not elastic_config.client.ping():
            logger.error("Cannot connect to OpenSearch!")
            return
            
        logger.info("Successfully connected to OpenSearch")
        
        # Get all indices
        indices = elastic_config.client.indices.get(index="*")
        
        if not indices:
            logger.info("No indices found in OpenSearch!")
            return
            
        logger.info(f"Found {len(indices)} indices:")
        for idx in indices:
            doc_count = elastic_config.client.cat.count(
                index=idx, format="json"
            )
            logger.info(f"  - {idx}: {doc_count} documents")
            
            # Get mapping for this index
            mapping = elastic_config.client.indices.get_mapping(index=idx)
            logger.info(f"  - Mappings: {mapping[idx]['mappings']}")
            
    except Exception as e:
        logger.error(f"Error listing indices: {e}")


def trigger_indexing():
    """Trigger indexing of CSV files"""
    try:
        # Use the index_all_csv_files function from the ElasticConfig class
        from config import settings
        
        logger.info(f"Indexing CSV files from {settings.CSV_FILES_DIR}")
        
        # Index each CSV file
        from pathlib import Path
        csv_dir = Path(settings.CSV_FILES_DIR)
        csv_files = list(csv_dir.glob("*.csv*"))
        
        logger.info(f"Found {len(csv_files)} CSV files: {csv_files}")
        
        for file_path in csv_files:
            logger.info(f"Indexing {file_path}...")
            success, count = elastic_config.index_csv_file(str(file_path))
            logger.info(f"  - Success: {success}, Documents indexed: {count}")
            
    except Exception as e:
        logger.error(f"Error indexing CSV files: {e}")


def test_search():
    """Test search functionality"""
    try:
        search_term = "192"  # Should match IP addresses
        logger.info(f"Testing search for term '{search_term}'")
        
        headers, documents = elastic_config.search(search_term)
        
        logger.info(f"Found {len(documents)} results for term '{search_term}'")
        if documents:
            logger.info(f"First result: {documents[0]}")
            logger.info(f"Headers: {headers}")
        
    except Exception as e:
        logger.error(f"Error testing search: {e}")


def update_index_settings():
    """Update settings for all existing indices"""
    try:
        # Test connection to OpenSearch
        if not elastic_config.client.ping():
            logger.error("Cannot connect to OpenSearch!")
            return
            
        logger.info("Updating index settings...")
        
        # Get all indices
        indices = elastic_config.client.indices.get(index="*")
        
        if not indices:
            logger.info("No indices found to update!")
            return
            
        logger.info(f"Found {len(indices)} indices to update:")
        for idx in indices:
            logger.info(f"Updating settings for {idx}...")
            success = elastic_config.update_index_settings(idx)
            logger.info(f"  - Success: {success}")
            
    except Exception as e:
        logger.error(f"Error updating index settings: {e}")


if __name__ == "__main__":
    # Run tests
    list_indices()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--index":
        trigger_indexing()
        list_indices()  # Show indices after indexing
    
    # Always update index settings (to support increased result window)
    update_index_settings()
        
    test_search()
