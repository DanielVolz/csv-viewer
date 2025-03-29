#!/usr/bin/env python3
import os
import sys

# Add the backend directory to the Python path to import modules
sys.path.append('./backend')

# Import our CSV utility
from utils.csv_utils import read_csv_file

def test_file(filename):
    """Test reading a CSV file and print the results."""
    print(f"\n{'='*50}")
    print(f"Testing file: {filename}")
    print(f"{'='*50}")
    
    # Call the read_csv_file function
    headers, rows = read_csv_file(filename)
    
    # Print results
    print(f"Headers: {headers}")
    print(f"Number of rows processed: {len(rows)}")
    
    # Print a few rows for verification
    max_rows = min(3, len(rows))
    for i in range(max_rows):
        print(f"\nRow {i+1}:")
        for key, value in rows[i].items():
            print(f"  {key}: {value}")

# Test both files
test_file('data/test.csv')
test_file('data/test_mismatch.csv')
