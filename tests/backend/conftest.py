import pytest
import os
import sys

# Add project root and backend directories to the Python path
root_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, root_dir)
backend_dir = os.path.join(root_dir, 'backend')
if os.path.exists(backend_dir):
    sys.path.insert(0, backend_dir)