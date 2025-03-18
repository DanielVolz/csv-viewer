#!/usr/bin/env python3
import random
import string
import csv
import os
from pathlib import Path
import argparse
import sys

def generate_large_csv(input_file, output_file, num_rows=17000):
    """Generate a large CSV file based on patterns in an input CSV file"""
    
    print(f"Reading template data from {input_file}...")
    
    # Read original data for templates
    original_data = []
    try:
        with open(input_file, 'r') as f:
            for line in f:
                original_data.append(line.strip().split(','))
    except Exception as e:
        print(f"Error reading input file: {e}")
        return False
    
    print(f"Read {len(original_data)} template rows")
    
    # Debug information about row lengths
    row_lengths = [len(row) for row in original_data]
    if row_lengths:
        print(f"Row lengths - Min: {min(row_lengths)}, Max: {max(row_lengths)}")
    else:
        print("Warning: No rows found in input file")
        return False
    
    # Column mappings for the netspeed.csv.1 format:
    # 0: IP address
    # 1: Serial number
    # 2: Model
    # 3: MAC address
    # 4: SEP ID
    # 5: Upload speed (first occurrence)
    # 6: Download speed (first occurrence)
    # 7: Switch name
    # 8: Port
    # 9: Upload speed (repeated)
    # 10: Download speed (repeated)
    
    # Extract unique values from original data to use as templates
    ip_prefixes = set()
    serial_patterns = set()
    models = set()
    mac_patterns = set()
    switches = set()
    ports = set()
    speeds = set()
    
    for row in original_data:
        # Only process rows with enough data
        if len(row) >= 9:  # Need at least up to the port field
            try:
                # Extract IP prefix (first three octets)
                if '.' in row[0]:
                    ip_parts = row[0].split('.')
                    if len(ip_parts) >= 3:
                        ip_prefixes.add('.'.join(ip_parts[:3]))
                
                # Serial number pattern (first 3 characters)
                if len(row[1]) >= 3:
                    serial_patterns.add(row[1][:3])
                
                # Model
                if row[2]:
                    models.add(row[2])
                
                # MAC address pattern (first 6 characters)
                if len(row[3]) >= 6:
                    mac_patterns.add(row[3][:6])
                
                # Switch name
                if len(row) > 7 and row[7]:
                    switches.add(row[7])
                
                # Port pattern (first two segments)
                if len(row) > 8 and '/' in row[8]:
                    port_parts = row[8].split('/')
                    if len(port_parts) >= 2:
                        ports.add(f"{port_parts[0]}/{port_parts[1]}")
                
                # Speed values
                if len(row) > 6:
                    try:
                        up_speed = int(row[5])
                        down_speed = int(row[6])
                        speeds.add((up_speed, down_speed))
                    except (ValueError, TypeError):
                        pass
            except IndexError:
                # Skip rows with missing fields
                continue
    
    # Generate phone prefixes (not in original data)
    phone_prefixes = {"+49555"}
    
    # Generate subnet masks (not in original data)
    subnet_masks = {"255.255.255.0", "255.255.0.0", "255.255.255.128", 
                    "255.255.255.192", "255.255.255.240"}
    
    # Print diagnostics
    print(f"Extracted patterns:")
    print(f"- IP prefixes: {len(ip_prefixes)}")
    print(f"- Serial patterns: {len(serial_patterns)}")
    print(f"- Models: {len(models)}")
    print(f"- MAC patterns: {len(mac_patterns)}")
    print(f"- Switches: {len(switches)}")
    print(f"- Port patterns: {len(ports)}")
    print(f"- Unique speed combinations: {len(speeds)}")
    print(f"- Using generated phone prefixes: {len(phone_prefixes)}")
    print(f"- Using generated subnet masks: {len(subnet_masks)}")
    
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
    for i in range(num_rows):
        if i > 0 and i % 1000 == 0:
            print(f"Generated {i} rows...")
        
        # IP address
        ip_prefix = random.choice(list(ip_prefixes))
        last_octet = random.randint(1, 254)
        ip = f"{ip_prefix}.{last_octet}"
        
        # Phone number (generated - not from input)
        phone_prefix = random.choice(list(phone_prefixes))
        phone = f"{phone_prefix}{random.randint(100000, 999999)}"
        
        # Serial number - 3 letter prefix + 3 digits + 3 letters
        serial_prefix = random.choice(list(serial_patterns))
        serial = f"{serial_prefix}{random.randint(100, 999)}{''.join(random.choices(string.ascii_uppercase, k=3))}"
        
        # Model
        model = random.choice(list(models))
        
        # MAC address - use pattern from originals but randomize
        mac_prefix = random.choice(list(mac_patterns))
        mac = f"{mac_prefix}{''.join(random.choices('0123456789ABCDEF', k=6))}"
        
        # SEP ID - add SEP prefix to MAC
        sep_id = f"SEP{mac}"
        
        # Subnet mask (generated - not from input)
        subnet_mask = random.choice(list(subnet_masks))
        
        # Speed values from input combinations
        if speeds:
            upload_speed, download_speed = random.choice(list(speeds))
        else:
            # Fallback if no speeds were extracted
            speeds_options = [(10, 10), (100, 10), (1000, 100), (100, 100), 
                            (1000, 1000), (10, 100), (100, 1000), (1000, 10)]
            upload_speed, download_speed = random.choice(speeds_options)
        
        # Numeric value (generated - not from input)
        numeric_value = random.randint(10, 70)
        
        # Switch and port
        switch = random.choice(list(switches))
        port_prefix = random.choice(list(ports))
        port_num = random.randint(1, 96)  # Most switches have up to 96 ports
        port = f"{port_prefix}/2/{port_num}"
        
        # Create the row with the expected output format
        row = [
            ip, phone, serial, model, mac, sep_id, subnet_mask, 
            str(numeric_value), str(upload_speed), str(download_speed),
            switch, port, str(upload_speed), str(download_speed)
        ]
        new_data.append(row)
    
    # Write to output file
    try:
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            for row in new_data:
                writer.writerow(row)
        
        print(f"Successfully generated {num_rows} rows in {output_file}")
        return True
    except Exception as e:
        print(f"Error writing output file: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate a large CSV file based on a template CSV')
    parser.add_argument('--input', '-i', default='example-data/netspeed.csv', 
                       help='Path to input CSV file (template)')
    parser.add_argument('--output', '-o', default='example-data/netspeed_large.csv', 
                       help='Path to output CSV file')
    parser.add_argument('--rows', '-r', type=int, default=17000, 
                       help='Number of rows to generate')
    
    args = parser.parse_args()
    
    # Convert relative paths to absolute if needed
    script_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
    input_file = args.input if os.path.isabs(args.input) else os.path.join(script_dir, args.input)
    output_file = args.output if os.path.isabs(args.output) else os.path.join(script_dir, args.output)
    
    # Generate large CSV
    success = generate_large_csv(input_file, output_file, args.rows)
    if not success:
        sys.exit(1)
