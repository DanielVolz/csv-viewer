#!/usr/bin/env python3
"""Direct test of trailing semicolon handling."""

import csv

# Create test files
with open('test_trailing.csv', 'w') as f:
    f.write("col1;col2;col3;\n")
    f.write("val1;val2;val3;\n")

with open('test_no_trailing.csv', 'w') as f:
    f.write("col1;col2;col3\n")
    f.write("val1;val2;val3\n")

# Define our custom CSV reader class to test
class TrailingDelimiterReader:
    def __init__(self, csv_file, delimiter):
        self.reader = csv.reader(csv_file, delimiter=delimiter)
        self.delimiter = delimiter
    
    def __iter__(self):
        return self
    
    def __next__(self):
        row = next(self.reader)
        # If the last element is empty and there was a trailing delimiter,
        # remove the last element
        if row and row[-1] == '':
            # Check if the original line ended with a delimiter by reconstructing it
            original_line = self.delimiter.join(row)
            if original_line.endswith(self.delimiter):
                return row[:-1]
        return row

# Test directly with our custom reader
print("=== Testing file with trailing semicolons ===")
with open('test_trailing.csv', 'r') as f:
    reader = TrailingDelimiterReader(f, ';')
    for row in reader:
        print(f"Row: {row}, Length: {len(row)}")

print("\n=== Testing file without trailing semicolons ===")
with open('test_no_trailing.csv', 'r') as f:
    reader = TrailingDelimiterReader(f, ';')
    for row in reader:
        print(f"Row: {row}, Length: {len(row)}")

# For comparison, check standard CSV reader behavior
print("\n=== Standard CSV reader with trailing semicolons ===")
with open('test_trailing.csv', 'r') as f:
    reader = csv.reader(f, delimiter=';')
    for row in reader:
        print(f"Row: {row}, Length: {len(row)}")

print("\n=== Standard CSV reader without trailing semicolons ===")
with open('test_no_trailing.csv', 'r') as f:
    reader = csv.reader(f, delimiter=';')
    for row in reader:
        print(f"Row: {row}, Length: {len(row)}")
