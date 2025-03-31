#!/usr/bin/env python3
"""Test script to verify NETSPEED_FILES filtering."""

import os
import sys
from pathlib import Path
import time

# Add a sleep so we can see the output more clearly
print("Starting test for NETSPEED_FILES filtering...")
time.sleep(1)

# Set the NETSPEED_FILES environment variable
os.environ["NETSPEED_FILES"] = "2"
max_netspeed_files = int(os.environ.get("NETSPEED_FILES", "2"))
print(f"Maximum netspeed files to index: {max_netspeed_files}")

# Find all CSV files in the data directory
data_dir = Path("data")
patterns = ["netspeed.csv", "netspeed.csv.*", "netspeed.csv_bak"]
files = []
for pattern in patterns:
    # Sort the glob results to ensure consistent ordering
    glob_results = sorted(data_dir.glob(pattern), key=lambda x: str(x))
    files.extend(glob_results)

print("\nAll files found:")
for f in files:
    print(f"  - {f}")

# Filter netspeed.csv.* files based on NETSPEED_FILES
netspeed_files = [f for f in files if "netspeed.csv" in str(f) and "netspeed.csv_bak" not in str(f)]
limited_netspeed_files = netspeed_files[:max_netspeed_files]

# Add back the netspeed.csv_bak files
other_files = [f for f in files if "netspeed.csv" not in str(f) or "netspeed.csv_bak" in str(f)]
files_to_process = limited_netspeed_files + other_files

print("\nFiles that would be processed (limited by NETSPEED_FILES=2):")
for f in files_to_process:
    print(f"  - {f}")
