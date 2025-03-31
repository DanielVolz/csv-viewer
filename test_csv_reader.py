#!/usr/bin/env python3
"""Test script for CSV reader with trailing delimiter handling."""

import csv
import sys
import os

# Add the current directory to the Python path for imports
sys.path.insert(0, os.getcwd())

from backend.utils.csv_utils import read_csv_file

# Create test files
with open('test_trailing.csv', 'w') as f:
    f.write("col1;col2;col3;\n")
    f.write("val1;val2;val3;\n")
    f.write("val4;val5;val6;\n")

with open('test_no_trailing.csv', 'w') as f:
    f.write("col1;col2;col3\n")
    f.write("val1;val2;val3\n")
    f.write("val4;val5;val6\n")

# Test with trailing semicolons
print("=== Testing file with trailing semicolons ===")
headers, rows = read_csv_file('test_trailing.csv')
print(f"Headers: {headers}")
print(f"Number of rows: {len(rows)}")
if rows:
    for i, row in enumerate(rows):
        print(f"Row {i+1}: {row}")
        print(f"Column count: {len([v for k, v in row.items() if not (k.startswith('#') or k in ['File Name', 'Creation Date'])])}")

# Test without trailing semicolons
print("\n=== Testing file without trailing semicolons ===")
headers, rows = read_csv_file('test_no_trailing.csv')
print(f"Headers: {headers}")
print(f"Number of rows: {len(rows)}")
if rows:
    for i, row in enumerate(rows):
        print(f"Row {i+1}: {row}")
        print(f"Column count: {len([v for k, v in row.items() if not (k.startswith('#') or k in ['File Name', 'Creation Date'])])}")
