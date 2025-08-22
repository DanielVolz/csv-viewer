#!/usr/bin/env python3
"""
Script to repair missing data in netspeed.csv by looking up values from older versions.
When network queries fail, this script can restore missing phone numbers and serial numbers
from previous CSV files.
"""

import csv
import os
import sys
from pathlib import Path
import argparse
from typing import Dict, List, Tuple, Optional

def read_csv_safely(file_path: str) -> List[List[str]]:
    """Read CSV file with proper encoding and semicolon delimiter."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            return [row for row in reader]
    except UnicodeDecodeError:
        # Fallback to latin-1 if UTF-8 fails
        with open(file_path, 'r', encoding='latin-1') as f:
            reader = csv.reader(f, delimiter=';')
            return [row for row in reader]

def write_csv_safely(file_path: str, rows: List[List[str]]):
    """Write CSV file with proper encoding and semicolon delimiter."""
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerows(rows)

def identify_kem_columns(row: List[str]) -> Tuple[int, int]:
    """
    Identify how many KEM modules a phone has and return the shift in column indices.
    Returns: (kem_count, phone_col_shift, serial_col_shift)
    """
    kem_count = 0
    if len(row) > 4 and row[4] == "KEM":
        kem_count += 1
    if len(row) > 5 and row[5] == "KEM":
        kem_count += 1
    return kem_count, kem_count

def get_key_indices(row: List[str]) -> Tuple[int, int, int]:
    """
    Get the correct column indices for phone number and serial number based on KEM count.
    Returns: (phone_col, serial_col, mac_col)
    """
    kem_count, shift = identify_kem_columns(row)

    # Base columns (0-indexed): IP=0, Phone=1, Serial=2, Model=3
    # With KEM: IP=0, Phone=1, Serial=2, Model=3, KEM=4, [KEM=5], MAC=4+shift, ...
    phone_col = 1
    serial_col = 2
    mac_col = 4 + shift  # MAC address position shifts with KEM modules

    return phone_col, serial_col, mac_col

def create_lookup_dict(rows: List[List[str]]) -> Dict[str, Dict[str, str]]:
    """
    Create a lookup dictionary with IP as key and phone/serial data as values.
    Also uses MAC address as secondary key for robustness.
    """
    lookup = {}

    for i, row in enumerate(rows):
        if i == 0 or len(row) < 5:  # Skip header or malformed rows
            continue

        ip = row[0].strip()
        phone_col, serial_col, mac_col = get_key_indices(row)

        phone = row[phone_col].strip() if phone_col < len(row) else ""
        serial = row[serial_col].strip() if serial_col < len(row) else ""
        mac = row[mac_col].strip() if mac_col < len(row) else ""

        # Use IP as primary key
        if ip and (phone or serial):
            lookup[ip] = {
                'phone': phone,
                'serial': serial,
                'mac': mac,
                'row_data': row.copy()
            }

        # Use MAC as secondary key (for cases where IP might have changed)
        if mac and (phone or serial):
            lookup[f"MAC:{mac}"] = {
                'phone': phone,
                'serial': serial,
                'mac': mac,
                'row_data': row.copy()
            }

    return lookup

def repair_missing_data(current_file: str, backup_files: List[str], output_file: str = None) -> Tuple[int, int]:
    """
    Repair missing data in current_file using data from backup_files.
    Returns: (repaired_count, total_missing_count)
    """
    if not output_file:
        output_file = current_file + ".repaired"

    print(f"Reading current file: {current_file}")
    current_rows = read_csv_safely(current_file)

    # Build lookup dictionary from backup files (newest first)
    combined_lookup = {}
    for backup_file in backup_files:
        if os.path.exists(backup_file):
            print(f"Reading backup file: {backup_file}")
            backup_rows = read_csv_safely(backup_file)
            backup_lookup = create_lookup_dict(backup_rows)

            # Add to combined lookup (don't overwrite existing entries - newest data wins)
            for key, data in backup_lookup.items():
                if key not in combined_lookup:
                    combined_lookup[key] = data

    print(f"Built lookup dictionary with {len(combined_lookup)} entries")

    # Repair current data
    repaired_count = 0
    total_missing_count = 0

    for i, row in enumerate(current_rows):
        if i == 0 or len(row) < 5:  # Skip header or malformed rows
            continue

        ip = row[0].strip()
        phone_col, serial_col, mac_col = get_key_indices(row)

        current_phone = row[phone_col].strip() if phone_col < len(row) else ""
        current_serial = row[serial_col].strip() if serial_col < len(row) else ""
        current_mac = row[mac_col].strip() if mac_col < len(row) else ""

        # Check if data is missing
        missing_phone = not current_phone
        missing_serial = not current_serial

        if missing_phone or missing_serial:
            total_missing_count += 1
            repaired = False

            # Try to find data by IP first
            if ip in combined_lookup:
                backup_data = combined_lookup[ip]
                if missing_phone and backup_data['phone']:
                    row[phone_col] = backup_data['phone']
                    repaired = True
                if missing_serial and backup_data['serial']:
                    row[serial_col] = backup_data['serial']
                    repaired = True

            # Try to find data by MAC address if IP lookup failed
            elif current_mac and f"MAC:{current_mac}" in combined_lookup:
                backup_data = combined_lookup[f"MAC:{current_mac}"]
                if missing_phone and backup_data['phone']:
                    row[phone_col] = backup_data['phone']
                    repaired = True
                if missing_serial and backup_data['serial']:
                    row[serial_col] = backup_data['serial']
                    repaired = True

            if repaired:
                repaired_count += 1
                print(f"Line {i+1}: Repaired IP {ip} - Phone: {missing_phone and 'FIXED' or 'OK'}, Serial: {missing_serial and 'FIXED' or 'OK'}")

    # Write repaired data
    print(f"Writing repaired data to: {output_file}")
    write_csv_safely(output_file, current_rows)

    return repaired_count, total_missing_count

def main():
    parser = argparse.ArgumentParser(description='Repair missing data in netspeed.csv')
    parser.add_argument('--current', default='/usr/scripts/netspeed/netspeed.csv',
                       help='Path to current netspeed.csv file')
    parser.add_argument('--backup-dir', default='/usr/scripts/netspeed',
                       help='Directory containing backup files')
    parser.add_argument('--output',
                       help='Output file path (default: current_file.repaired)')
    parser.add_argument('--backup-count', type=int, default=5,
                       help='Number of backup files to use (default: 5)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be repaired without making changes')

    args = parser.parse_args()

    # Find backup files
    backup_files = []
    backup_dir = Path(args.backup_dir)
    for i in range(args.backup_count):
        backup_file = backup_dir / f"netspeed.csv.{i}"
        if backup_file.exists():
            backup_files.append(str(backup_file))

    if not backup_files:
        print("No backup files found!")
        return 1

    print(f"Using backup files: {backup_files}")

    if args.dry_run:
        # TODO: Implement dry-run mode
        print("Dry-run mode not implemented yet")
        return 1

    try:
        repaired_count, total_missing_count = repair_missing_data(
            args.current, backup_files, args.output
        )

        print(f"\n=== REPAIR SUMMARY ===")
        print(f"Total entries with missing data: {total_missing_count}")
        print(f"Successfully repaired entries: {repaired_count}")
        print(f"Repair rate: {repaired_count/total_missing_count*100:.1f}%" if total_missing_count > 0 else "No missing data found")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
