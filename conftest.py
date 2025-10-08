import pytest
import os
import sys

# Add both project root and backend directory to the Python path
root_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, root_dir)
backend_dir = os.path.join(root_dir, 'backend')
if os.path.exists(backend_dir):
    sys.path.insert(0, backend_dir)

# Disable Celery Redis backend retries during tests
# This prevents 20-second retry timeouts when Redis is not available
# Set environment variable BEFORE Celery is imported
os.environ['CELERY_RESULT_BACKEND'] = 'cache+memory://'
os.environ['CELERY_BROKER_URL'] = 'memory://'

# Disable OpenSearch availability wait during tests
# This prevents 30-second timeouts when OpenSearch is not running
# OpenSearch wait is disabled via OPENSEARCH_WAIT_FOR_AVAILABILITY=false
os.environ['OPENSEARCH_WAIT_FOR_AVAILABILITY'] = 'false'
os.environ['OPENSEARCH_STARTUP_TIMEOUT_SECONDS'] = '1'

# This file can contain shared fixtures for your tests
@pytest.fixture
def sample_data():
    """Fixture to provide sample CSV data for tests."""
    return [
        ['Name', 'Age', 'Location'],
        ['John', '30', 'New York'],
        ['Mary', '25', 'San Francisco'],
        ['Bob', '40', 'Chicago']
    ]
