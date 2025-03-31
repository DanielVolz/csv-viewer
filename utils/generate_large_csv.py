#!/usr/bin/env python3
import random
import string
import csv
import os
from pathlib import Path
import argparse
import sys
from datetime import datetime

def generate_large_csv(input_file, output_file, num_rows=17000, use_new_format=False):
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
        if len(row) >= 9:  # Need at least up to the subnet mask field
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
                        speed1 = int(row[5])
                        speed2 = int(row[6])
                        speeds.add((speed1, speed2))
                    except (ValueError, TypeError):
                        pass
            except IndexError:
                # Skip rows with missing fields
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
    if use_new_format:
        print("Generating files in new 14-column format with phone numbers")
    else:
        print("Generating files in old 11-column format")
    
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
        
        # Switch name
        switch = random.choice(list(switches))
        
        # Switch port
        port_prefix = random.choice(list(ports))
        port_segment = random.randint(1, 10)  # Additional port segment
        port_num = random.randint(1, 96)  # Most switches have up to 96 ports
        
        # Different port format for new vs old
        if use_new_format:
            # New format has GigabitEthernet1/0/2/89 format
            port = f"{port_prefix}/2/{port_num}"
        else:
            # Old format has GigabitEthernet1/0/93 format
            port = f"{port_prefix}/{port_num}"
        
        # Generate phone number
        phone = f"+49555{random.randint(100000, 999999)}"
        
        # Subnet mask
        subnet_mask = random.choice(list(subnet_masks))
        
        # Voice VLAN
        voice_vlan = random.choice(list(voice_vlans))
        
        if use_new_format:
            # Create the row with the new 14-column format
            # 10.0.0.42,+49555674250,GHI236CLE,ModelB,A0B1C2A6DBD9,SEPA0B1C2A6DBD9,255.255.0.0,20,10,10,switch1.example.com,GigabitEthernet1/0/2/89,10,10
            row = [
                ip, phone, serial, model, mac, mac2, 
                subnet_mask, voice_vlan, str(speed1), str(speed2),
                switch, port, str(speed1), str(speed2)
            ]
        else:
            # Create the row with the old 11-column format
            # 172.16.0.24,GHI798RST,ModelC,11223344556F,SEP11223344556F,1000,1000,switch3.example.com,GigabitEthernet1/0/93,1000,1000
            row = [
                ip, serial, model, mac, mac2, 
                str(speed1), str(speed2), switch, port, 
                str(speed1), str(speed2)
            ]
        new_data.append(row)
    
    # Write to output file
    try:
        with open(output_file, 'w', newline='') as f:
            # Instead of using csv.writer, we'll write lines directly with a trailing semicolon
            for row in new_data:
                # Join with semicolons and add trailing semicolon
                line = ';'.join(row) + ';\n'
                f.write(line)
        
        print(f"Successfully generated {num_rows} rows in {output_file} with trailing semicolons")
        return True
    except Exception as e:
        print(f"Error writing output file: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate a large CSV file based on a template CSV')
    parser.add_argument('--input', '-i', default='data/netspeed.csv.1', 
                       help='Path to input CSV file (template)')
    parser.add_argument('--output', '-o', default='data/netspeed.csv.2', 
                       help='Path to output CSV file')
    parser.add_argument('--rows', '-r', type=int, default=17000, 
                       help='Number of rows to generate')
    parser.add_argument('--new-format', '-n', action='store_true',
                       help='Generate file in new 14-column format with phone numbers')
    
    args = parser.parse_args()
    
    # Convert relative paths to absolute if needed
    if not os.path.isabs(args.input):
        script_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
        input_file = os.path.join(script_dir, args.input)
    else:
        input_file = args.input
        
    if not os.path.isabs(args.output):
        script_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
        output_file = os.path.join(script_dir, args.output)
    else:
        output_file = args.output
    
    # Generate large CSV
    success = generate_large_csv(input_file, output_file, args.rows, args.new_format)
    if not success:
        sys.exit(1)
