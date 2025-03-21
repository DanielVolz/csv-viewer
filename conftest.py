import pytest
import os
import sys

# Add both project root and backend directory to the Python path
root_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, root_dir)
backend_dir = os.path.join(root_dir, 'backend')
if os.path.exists(backend_dir):
    sys.path.insert(0, backend_dir)

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
