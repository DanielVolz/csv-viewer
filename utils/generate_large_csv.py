#!/usr/bin/env python3
import random
import string
import csv
import os
from pathlib import Path
import argparse
import sys
from datetime import datetime
from typing import List, Tuple

# Current standard netspeed.csv format (16 columns, semicolon-delimited, no header)
CURRENT_HEADERS_16 = [
    "IP Address", "Line Number", "Serial Number", "Model Name", "KEM", "KEM 2",
    "MAC Address", "MAC Address 2", "Subnet Mask", "Voice VLAN", "Phone Port Speed", "PC Port Speed",
    "Switch Hostname", "Switch Port", "Switch Port Mode", "PC Port Mode"
]


def _random_location_prefix(pref_list=None):
    # Prefer some realistic-looking codes; ensure MXX is present for testing
    base = pref_list or [
        "MXX", "BER", "MUN", "HAM", "FRA", "DUS", "STU", "HAN", "LEI", "KOL",
        "NUR", "AUG", "ULM", "KIE", "LUB", "ROS", "ESS", "BOC", "DOR", "BON"
    ]
    # Also randomly synthesize some generic codes
    if random.random() < 0.3:
        return ''.join(random.choices(string.ascii_uppercase, k=3))
    return random.choice(base)


def _random_location_code():
    prefix = _random_location_prefix()
    suffix = f"{random.randint(1, 20):02d}"
    return prefix + suffix


def _random_switch_hostname():
    loc = _random_location_code()
    # Example: MXX01-SW1.local or MXX12-ACCESS-2.example
    role = random.choice(["SW", "EDGE", "ACCESS", "DIST", "CORE"])  # simple roles
    num = random.randint(1, 4)
    domain = random.choice(["local", "example", "corp", "lan"])  # harmless domains
    return f"{loc}-{role}{num}.{domain}"


def _detect_delimiter(file_path: str) -> str:
    """Detect CSV delimiter, defaulting to ';' for netspeed files."""
    try:
        with open(file_path, 'r', newline='') as f:
            sample = f.read(8192)
            try:
                # csv.Sniffer expects a string of possible delimiters, not a list
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                return dialect.delimiter
            except Exception:
                return ';'
    except Exception:
        return ';'


def _read_template_rows(file_path: str) -> Tuple[List[List[str]], str]:
    """Read template rows using detected delimiter and trim trailing empty columns."""
    delimiter = _detect_delimiter(file_path)
    rows: List[List[str]] = []
    with open(file_path, 'r', newline='') as f:
        reader = csv.reader(f, delimiter=delimiter)
        for row in reader:
            # Strip whitespace around cells
            row = [c.strip() for c in row]
            # Drop trailing empty cells caused by a terminal delimiter
            while row and (row[-1] is None or row[-1] == ''):
                row.pop()
            # Skip fully empty rows
            if not row or all(c == '' for c in row):
                continue
            rows.append(row)
    return rows, delimiter


def generate_large_csv(input_file, output_file, num_rows=17000, fmt="16"):
    """Generate a large CSV file that matches current netspeed.csv expectations.

    - Default (fmt='16'): 16-column standard with KEM/KEM 2 and location-coded switch names
    - fmt='14': legacy 14-col (kept for backwards compatibility)
    - fmt='11': old 11-col (kept for backwards compatibility)
    """

    print(f"Reading template data from {input_file}...")

    # Read original data for templates (with delimiter detection)
    try:
        original_data, detected_delim = _read_template_rows(input_file)
    except Exception as e:
        print(f"Error reading input file: {e}")
        return False

    print(f"Read {len(original_data)} template rows")
    print(f"Detected delimiter: '{detected_delim}'")

    # Debug information about row lengths
    row_lengths = [len(row) for row in original_data]
    if row_lengths:
        print(f"Row lengths - Min: {min(row_lengths)}, Max: {max(row_lengths)}")
    else:
        print("Warning: No rows found in input file")
        return False

    # Extract unique values from original data to use as templates
    ip_prefixes = set()
    serial_patterns = set()
    models = set()
    mac_patterns = set()
    switches = set()
    ports = set()
    speeds = set()

    for row in original_data:
        # Map fields by supported format lengths
        L = len(row)
        if L >= 16:
            # Current 16-col format
            idx = {
                'ip': 0,
                'serial': 2,
                'model': 3,
                'mac': 6,
                'speed1': 10,
                'speed2': 11,
                'switch': 12,
                'port': 13,
            }
        elif L >= 14:
            # 14-col legacy (writer order in this script)
            idx = {
                'ip': 0,
                'serial': 2,
                'model': 3,
                'mac': 4,
                'speed1': 8,
                'speed2': 9,
                'switch': 10,
                'port': 11,
            }
        elif L >= 11:
            # 11-col old legacy (writer order in this script)
            idx = {
                'ip': 0,
                'serial': 1,
                'model': 2,
                'mac': 3,
                'speed1': 5,
                'speed2': 6,
                'switch': 7,
                'port': 8,
            }
        else:
            # Not enough columns to extract patterns
            continue

        try:
            # IP prefix (first three octets)
            ip_cell = row[idx['ip']]
            if ip_cell and '.' in ip_cell:
                ip_parts = ip_cell.split('.')
                if len(ip_parts) >= 3:
                    ip_prefixes.add('.'.join(ip_parts[:3]))

            # Serial pattern
            serial_cell = row[idx['serial']]
            if serial_cell and len(serial_cell) >= 3:
                serial_patterns.add(serial_cell[:3])

            # Model
            model_cell = row[idx['model']]
            if model_cell:
                models.add(model_cell)

            # MAC prefix (first 6 hex chars)
            mac_cell = row[idx['mac']]
            if mac_cell and len(mac_cell) >= 6:
                mac_patterns.add(mac_cell[:6])

            # Switch name
            switch_cell = row[idx['switch']]
            if switch_cell:
                switches.add(switch_cell)

            # Port pattern (first two segments)
            port_cell = row[idx['port']]
            if port_cell and '/' in port_cell:
                port_parts = port_cell.split('/')
                if len(port_parts) >= 2:
                    ports.add(f"{port_parts[0]}/{port_parts[1]}")

            # Speeds
            s1 = row[idx['speed1']]
            s2 = row[idx['speed2']]
            try:
                speed1 = int(str(s1).strip())
                speed2 = int(str(s2).strip())
                speeds.add((speed1, speed2))
            except (ValueError, TypeError):
                pass
        except Exception:
            continue

    # Generate subnet masks (not in original data)
    subnet_masks = {"255.255.255.0", "255.255.0.0", "255.255.255.128",
                    "255.255.255.192", "255.255.255.240"}

    # Generate voice VLANs
    voice_vlans = {"100", "200", "300", "400", "500"}

    # Print diagnostics
    print(f"Extracted patterns:")
    print(f"- IP prefixes: {len(ip_prefixes)}")
    print(f"- Serial patterns: {len(serial_patterns)}")
    print(f"- Models: {len(models)}")
    print(f"- MAC patterns: {len(mac_patterns)}")
    print(f"- Switches: {len(switches)}")
    print(f"- Port patterns: {len(ports)}")
    print(f"- Unique speed combinations: {len(speeds)}")
    print(f"- Using generated subnet masks: {len(subnet_masks)}")
    print(f"- Using generated voice VLANs: {len(voice_vlans)}")

    # Check if we have enough data to generate rows
    if not (ip_prefixes and serial_patterns and models and mac_patterns and switches and ports):
        print("Error: Could not extract required patterns from input file")

        # Create default patterns if needed
        if not ip_prefixes:
            ip_prefixes = {"192.168.1", "10.0.0", "172.16.0"}
            print("Using default IP prefixes")

        if not serial_patterns:
            serial_patterns = {"ABC", "DEF", "GHI"}
            print("Using default serial patterns")

        if not models:
            models = {"ModelA", "ModelB", "ModelC"}
            print("Using default model patterns")

        if not mac_patterns:
            mac_patterns = {"AABBCC", "112233", "445566"}
            print("Using default MAC patterns")

        if not switches:
            switches = {"switch1.example.com", "switch2.example.com", "switch3.example.com"}
            print("Using default switch names")

        if not ports:
            ports = {"GigabitEthernet1/0", "GigabitEthernet2/0"}
            print("Using default port patterns")

        if not speeds:
            speeds = {(10, 10), (100, 10), (1000, 100), (100, 100),
                    (1000, 1000), (10, 100), (100, 1000), (1000, 10)}
            print("Using default speed combinations")

    print(f"Generating {num_rows} rows of data...")

    # Generate new data
    new_data = []

    # No header row for CSV files

    # Determine format to use
    if fmt == "16":
        print("Generating files in current 16-column standard format")
    elif fmt == "14":
        print("Generating files in 14-column legacy format (deprecated)")
    elif fmt == "11":
        print("Generating files in 11-column legacy format (deprecated)")
    else:
        print(f"Unknown format '{fmt}', defaulting to 16-column current format")
        fmt = "16"

    # Properly indented row generation loop
    for i in range(1, num_rows + 1):
        if i > 0 and i % 1000 == 0:
            print(f"Generated {i} rows...")

        # IP address
        ip_prefix = random.choice(list(ip_prefixes))
        last_octet = random.randint(1, 254)
        ip = f"{ip_prefix}.{last_octet}"

        # Serial number - 3 letter prefix + 3 digits + 3 letters
        serial_prefix = random.choice(list(serial_patterns))
        serial = f"{serial_prefix}{random.randint(100, 999)}{''.join(random.choices(string.ascii_uppercase, k=3))}"

        # Model
        model = random.choice(list(models))

        # MAC address - use pattern from originals but randomize
        mac_prefix = random.choice(list(mac_patterns))
        mac_suffix = ''.join(random.choices('0123456789ABCDEF', k=6))
        mac = f"{mac_prefix}{mac_suffix}"

        # MAC address 2 (SEP ID) - add SEP prefix to MAC
        mac2 = f"SEP{mac}"

        # Speed values from input combinations
        if speeds:
            speed1, speed2 = random.choice(list(speeds))
        else:
            # Fallback if no speeds were extracted
            speeds_options = [(10, 10), (100, 10), (1000, 100), (100, 100),
                              (1000, 1000), (10, 100), (100, 1000), (1000, 10)]
            speed1, speed2 = random.choice(speeds_options)

        # Switch name (synthesize location-coded hostname for stats compatibility)
        switch = _random_switch_hostname()

        # Switch port
        port_prefix = random.choice(list(ports))
        port_segment = random.randint(1, 10)  # Additional port segment
        port_num = random.randint(1, 96)  # Most switches have up to 96 ports

        # Port format depends on format
        if fmt == "16" or fmt == "14":
            # Modern formats use stacked path like GigabitEthernet1/0/2/89
            port = f"{port_prefix}/2/{port_num}"
        else:
            # Old format has GigabitEthernet1/0/93 format
            port = f"{port_prefix}/{port_num}"

        # Generate phone number (Line Number)
        phone = f"+49555{random.randint(100000, 999999)}"

        # Subnet mask
        subnet_mask = random.choice(list(subnet_masks))

        # Voice VLAN
        voice_vlan = random.choice(list(voice_vlans))

        if fmt == "16":
            # Current standard 16-column format
            # Include KEM tokens on a subset of rows; use canonical 'KEM'
            kem = ""
            kem2 = ""
            r = random.random()
            if r < 0.12:
                kem = "KEM"
            if r < 0.03 and kem:
                kem2 = "KEM"

            # Switch/PC port speeds can mirror the negotiated speeds
            row = [
                ip, phone, serial, model, kem, kem2,
                mac, mac2, subnet_mask, voice_vlan, str(speed1), str(speed2),
                switch, port, str(speed1), str(speed2)
            ]
        elif fmt == "14":
            # 14-column legacy format with Line Number
            row = [
                ip, phone, serial, model, mac, mac2,
                subnet_mask, voice_vlan, str(speed1), str(speed2),
                switch, port, str(speed1), str(speed2)
            ]
        else:  # fmt == '11'
            # 11-column old legacy format
            row = [
                ip, serial, model, mac, mac2,
                str(speed1), str(speed2), switch, port,
                str(speed1), str(speed2)
            ]
        new_data.append(row)

    # Write to output file with correct indentation
    try:
        # Ensure output directory exists
        out_dir = os.path.dirname(os.path.abspath(output_file))
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        with open(output_file, 'w', newline='') as f:
            # Write lines directly with a single trailing semicolon
            for row in new_data:
                line = ';'.join(row) + ';\n'
                f.write(line)

        print(f"Successfully generated {num_rows} rows in {output_file} (format: {fmt}, 16-col when '16')")
        return True
    except Exception as e:
        print(f"Error writing output file: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate netspeed.csv test data (semicolon-delimited, 16 columns, no header). Only rows and historical are configurable.')
    parser.add_argument('--rows', '-r', type=int, default=17000,
               help='Number of rows to generate for the main file (default: 17000)')
    parser.add_argument('--historical', '-H', type=int, default=0,
               help='Also generate N historical files with suffix .0..N next to the main file (default: 0)')

    # Show help when called without any flags
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    # Fixed defaults: input template and output path under repo's data/
    script_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
    input_file = os.path.join(script_dir, 'data', 'netspeed.csv.1')
    output_file = os.path.join(script_dir, 'data', 'netspeed.csv')

    # Always use 16-column current format
    effective_fmt = '16'

    # Generate main file
    success = generate_large_csv(input_file, output_file, args.rows, effective_fmt)
    if not success:
        sys.exit(1)

    # Generate historical files if requested
    hist_n = max(0, int(args.historical or 0))
    hist_rows = args.rows
    for i in range(hist_n + 1):
        # Create netspeed.csv.0 .. .N (skip if main output already has such suffix and i==0)
        hist_path = f"{output_file}.{i}"
        # Use a varied random seed per file for diversity
        try:
            random.seed(10007 * (i + 1) + hist_rows)
        except Exception:
            pass
        ok = generate_large_csv(input_file, hist_path, hist_rows, effective_fmt)
        if not ok:
            print(f"Warning: failed to generate historical file {hist_path}")
