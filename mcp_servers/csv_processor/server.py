#!/usr/bin/env python3
"""
CSV Processor MCP Server

A Model Context Protocol server for processing and validating CSV files 
specifically designed for the CSV Viewer project.

This server provides tools for:
- Parsing CSV files with automatic format detection
- Validating network data (IP addresses, MAC addresses)
- Generating statistics about CSV content
- Converting between CSV formats
- Detecting data quality issues
"""

import asyncio
import logging
import os
import re
import csv
import ipaddress
from typing import List, Dict, Any
from datetime import datetime

import pandas as pd
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CSV format configurations from existing codebase
KNOWN_HEADERS = {
    11: [  # OLD format
        "IP Address", "Serial Number", "Model Name", "MAC Address", "MAC Address 2",
        "Switch Hostname", "Switch Port"
    ],
    14: [  # NEW format  
        "IP Address", "Line Number", "Serial Number", "Model Name", "MAC Address",
        "MAC Address 2", "Subnet Mask", "Voice VLAN", "Switch Hostname", "Switch Port"
    ]
}

DESIRED_ORDER = [
    "#", "File Name", "Creation Date", "IP Address", "Line Number", "MAC Address",
    "MAC Address 2", "Subnet Mask", "Voice VLAN", "Switch Hostname", "Switch Port",
    "Serial Number", "Model Name"
]

# Validation patterns
IP_PATTERN = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
MAC_PATTERN = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')

app = Server("csv-processor")

@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available CSV processing tools."""
    return [
        Tool(
            name="parse_csv",
            description="Parse CSV file and return structure information including format detection",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the CSV file to parse"},
                    "detect_delimiter": {"type": "boolean", "default": True, "description": "Auto-detect delimiter (comma vs semicolon)"}
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="validate_network_data", 
            description="Validate network-specific data in CSV (IP addresses, MAC addresses, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the CSV file to validate"},
                    "check_ip": {"type": "boolean", "default": True, "description": "Validate IP addresses"},
                    "check_mac": {"type": "boolean", "default": True, "description": "Validate MAC addresses"},
                    "check_duplicates": {"type": "boolean", "default": True, "description": "Check for duplicate entries"}
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="generate_csv_stats",
            description="Generate comprehensive statistics about CSV content",
            inputSchema={
                "type": "object", 
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the CSV file to analyze"},
                    "include_data_quality": {"type": "boolean", "default": True, "description": "Include data quality metrics"}
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="convert_csv_format",
            description="Convert CSV between old (11-column) and new (14-column) formats",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string", "description": "Path to input CSV file"},
                    "output_path": {"type": "string", "description": "Path for output CSV file"},
                    "target_format": {"type": "string", "enum": ["old", "new"], "description": "Target format to convert to"}
                },
                "required": ["input_path", "output_path", "target_format"]
            }
        ),
        Tool(
            name="detect_csv_issues",
            description="Detect common issues in CSV files (encoding, formatting, missing data)",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the CSV file to check"},
                    "check_encoding": {"type": "boolean", "default": True, "description": "Check file encoding issues"},
                    "check_formatting": {"type": "boolean", "default": True, "description": "Check formatting consistency"}
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="compare_csv_files",
            description="Compare two CSV files and identify differences",
            inputSchema={
                "type": "object",
                "properties": {
                    "file1_path": {"type": "string", "description": "Path to first CSV file"},
                    "file2_path": {"type": "string", "description": "Path to second CSV file"},
                    "key_columns": {"type": "array", "items": {"type": "string"}, "description": "Columns to use as unique identifiers"}
                },
                "required": ["file1_path", "file2_path"]
            }
        )
    ]

def detect_delimiter(file_path: str) -> str:
    """Detect CSV delimiter by reading file content."""
    try:
        with open(file_path, 'r') as f:
            content = f.read(1024)  # Read first 1KB
            return ';' if ';' in content else ','
    except Exception as e:
        logger.error(f"Error detecting delimiter: {e}")
        return ','

def validate_ip_address(ip: str) -> bool:
    """Validate IP address format."""
    if not ip or ip.strip() == '':
        return True  # Empty is acceptable
    
    try:
        ipaddress.ip_address(ip.strip())
        return True
    except ValueError:
        return False

def validate_mac_address(mac: str) -> bool:
    """Validate MAC address format."""
    if not mac or mac.strip() == '':
        return True  # Empty is acceptable
    
    return bool(MAC_PATTERN.match(mac.strip()))

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    
    if name == "parse_csv":
        file_path = arguments["file_path"]
        detect_delim = arguments.get("detect_delimiter", True)
        
        try:
            if not os.path.exists(file_path):
                return [TextContent(type="text", text=f"Error: File {file_path} does not exist")]
            
            # Detect delimiter if requested
            delimiter = detect_delimiter(file_path) if detect_delim else ','
            
            # Read CSV with pandas for analysis
            df = pd.read_csv(file_path, delimiter=delimiter)
            
            # Determine format
            column_count = len(df.columns)
            detected_format = "unknown"
            if column_count == 11:
                detected_format = "old"
            elif column_count == 14:
                detected_format = "new"
            
            # Generate headers
            headers = KNOWN_HEADERS.get(column_count, [f"Column_{i+1}" for i in range(column_count)])
            
            # Get file stats
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size
            creation_date = datetime.fromtimestamp(file_stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            
            result = {
                "file_path": file_path,
                "file_size_bytes": file_size,
                "creation_date": creation_date,
                "delimiter": delimiter,
                "columns": column_count,
                "rows": len(df),
                "detected_format": detected_format,
                "headers": headers,
                "column_names": df.columns.tolist(),
                "sample_data": df.head(3).to_dict('records') if len(df) > 0 else []
            }
            
            return [TextContent(type="text", text=f"CSV Analysis Result:\n{result}")]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error parsing CSV: {str(e)}")]
    
    elif name == "validate_network_data":
        file_path = arguments["file_path"]
        check_ip = arguments.get("check_ip", True)
        check_mac = arguments.get("check_mac", True)
        check_duplicates = arguments.get("check_duplicates", True)
        
        try:
            if not os.path.exists(file_path):
                return [TextContent(type="text", text=f"Error: File {file_path} does not exist")]
            
            delimiter = detect_delimiter(file_path)
            df = pd.read_csv(file_path, delimiter=delimiter)
            
            validation_results = {
                "total_rows": len(df),
                "validation_summary": {},
                "issues": []
            }
            
            # Validate IP addresses
            if check_ip and "IP Address" in df.columns:
                invalid_ips = []
                for idx, ip in enumerate(df["IP Address"]):
                    if pd.notna(ip) and not validate_ip_address(str(ip)):
                        invalid_ips.append({"row": idx + 1, "value": str(ip)})
                
                validation_results["validation_summary"]["invalid_ip_addresses"] = len(invalid_ips)
                if invalid_ips:
                    validation_results["issues"].extend([
                        f"Invalid IP at row {item['row']}: {item['value']}" for item in invalid_ips[:10]
                    ])
            
            # Validate MAC addresses
            if check_mac:
                for mac_col in ["MAC Address", "MAC Address 2"]:
                    if mac_col in df.columns:
                        invalid_macs = []
                        for idx, mac in enumerate(df[mac_col]):
                            if pd.notna(mac) and not validate_mac_address(str(mac)):
                                invalid_macs.append({"row": idx + 1, "value": str(mac)})
                        
                        validation_results["validation_summary"][f"invalid_{mac_col.lower().replace(' ', '_')}"] = len(invalid_macs)
                        if invalid_macs:
                            validation_results["issues"].extend([
                                f"Invalid {mac_col} at row {item['row']}: {item['value']}" for item in invalid_macs[:5]
                            ])
            
            # Check for duplicates
            if check_duplicates and "MAC Address" in df.columns:
                duplicates = df[df["MAC Address"].duplicated(keep=False) & df["MAC Address"].notna()]
                validation_results["validation_summary"]["duplicate_mac_addresses"] = len(duplicates)
                if len(duplicates) > 0:
                    validation_results["issues"].append(f"Found {len(duplicates)} rows with duplicate MAC addresses")
            
            return [TextContent(type="text", text=f"Network Data Validation:\n{validation_results}")]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error validating network data: {str(e)}")]
    
    elif name == "generate_csv_stats":
        file_path = arguments["file_path"]
        include_quality = arguments.get("include_data_quality", True)
        
        try:
            if not os.path.exists(file_path):
                return [TextContent(type="text", text=f"Error: File {file_path} does not exist")]
            
            delimiter = detect_delimiter(file_path)
            df = pd.read_csv(file_path, delimiter=delimiter)
            
            stats = {
                "basic_info": {
                    "file_name": os.path.basename(file_path),
                    "total_rows": len(df),
                    "total_columns": len(df.columns),
                    "file_size_mb": round(os.path.getsize(file_path) / 1024 / 1024, 2),
                    "delimiter": delimiter
                },
                "column_stats": {}
            }
            
            # Generate column statistics
            for col in df.columns:
                col_stats = {
                    "non_null_count": df[col].count(),
                    "null_count": df[col].isnull().sum(),
                    "unique_values": df[col].nunique(),
                    "data_type": str(df[col].dtype)
                }
                
                if df[col].dtype == 'object':
                    col_stats["most_common"] = df[col].value_counts().head(3).to_dict()
                
                stats["column_stats"][col] = col_stats
            
            # Data quality metrics
            if include_quality:
                stats["data_quality"] = {
                    "completeness_percentage": round((df.count().sum() / (len(df) * len(df.columns))) * 100, 2),
                    "rows_with_missing_data": len(df) - len(df.dropna()),
                    "completely_empty_rows": len(df[df.isnull().all(axis=1)])
                }
            
            return [TextContent(type="text", text=f"CSV Statistics:\n{stats}")]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error generating statistics: {str(e)}")]
    
    elif name == "convert_csv_format":
        input_path = arguments["input_path"]
        output_path = arguments["output_path"]
        target_format = arguments["target_format"]
        
        try:
            if not os.path.exists(input_path):
                return [TextContent(type="text", text=f"Error: Input file {input_path} does not exist")]
            
            delimiter = detect_delimiter(input_path)
            df = pd.read_csv(input_path, delimiter=delimiter)
            
            current_columns = len(df.columns)
            
            if target_format == "old" and current_columns == 14:
                # Convert from new (14) to old (11) format
                # Keep only the columns that exist in old format
                old_headers = KNOWN_HEADERS[11]
                df_converted = df[old_headers]
                
            elif target_format == "new" and current_columns == 11:
                # Convert from old (11) to new (14) format
                # Add missing columns with default values
                new_headers = KNOWN_HEADERS[14]
                for header in new_headers:
                    if header not in df.columns:
                        df[header] = ""  # Add empty columns
                df_converted = df[new_headers]
                
            else:
                return [TextContent(type="text", text=f"Conversion not needed or not supported: {current_columns} columns to {target_format} format")]
            
            # Save converted file
            df_converted.to_csv(output_path, index=False, sep=delimiter)
            
            result = {
                "input_file": input_path,
                "output_file": output_path,
                "original_columns": current_columns,
                "converted_columns": len(df_converted.columns),
                "target_format": target_format,
                "rows_processed": len(df_converted)
            }
            
            return [TextContent(type="text", text=f"CSV Format Conversion Completed:\n{result}")]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error converting CSV format: {str(e)}")]
    
    elif name == "detect_csv_issues":
        file_path = arguments["file_path"]
        check_encoding = arguments.get("check_encoding", True)
        check_formatting = arguments.get("check_formatting", True)
        
        try:
            if not os.path.exists(file_path):
                return [TextContent(type="text", text=f"Error: File {file_path} does not exist")]
            
            issues = []
            
            # Check encoding
            if check_encoding:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        f.read()
                except UnicodeDecodeError:
                    issues.append("File may have encoding issues (not UTF-8)")
            
            # Check formatting consistency
            if check_formatting:
                delimiter = detect_delimiter(file_path)
                with open(file_path, 'r') as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    row_lengths = []
                    for i, row in enumerate(reader):
                        row_lengths.append(len(row))
                        if i >= 100:  # Check first 100 rows
                            break
                
                if row_lengths:
                    most_common_length = max(set(row_lengths), key=row_lengths.count)
                    inconsistent_rows = [i+1 for i, length in enumerate(row_lengths) if length != most_common_length]
                    
                    if inconsistent_rows:
                        issues.append(f"Inconsistent row lengths found in rows: {inconsistent_rows[:10]}")
            
            result = {
                "file_path": file_path,
                "issues_found": len(issues),
                "issues": issues,
                "status": "healthy" if not issues else "issues_detected"
            }
            
            return [TextContent(type="text", text=f"CSV Issue Detection:\n{result}")]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error detecting CSV issues: {str(e)}")]
    
    elif name == "compare_csv_files":
        file1_path = arguments["file1_path"]
        file2_path = arguments["file2_path"]
        key_columns = arguments.get("key_columns", ["MAC Address"])
        
        try:
            if not os.path.exists(file1_path):
                return [TextContent(type="text", text=f"Error: File {file1_path} does not exist")]
            if not os.path.exists(file2_path):
                return [TextContent(type="text", text=f"Error: File {file2_path} does not exist")]
            
            # Read both files
            delimiter1 = detect_delimiter(file1_path)
            delimiter2 = detect_delimiter(file2_path)
            
            df1 = pd.read_csv(file1_path, delimiter=delimiter1)
            df2 = pd.read_csv(file2_path, delimiter=delimiter2)
            
            comparison = {
                "file1": {"path": file1_path, "rows": len(df1), "columns": len(df1.columns)},
                "file2": {"path": file2_path, "rows": len(df2), "columns": len(df2.columns)},
                "column_differences": {
                    "file1_only": list(set(df1.columns) - set(df2.columns)),
                    "file2_only": list(set(df2.columns) - set(df1.columns)),
                    "common": list(set(df1.columns) & set(df2.columns))
                }
            }
            
            # Compare data if key columns exist
            valid_keys = [col for col in key_columns if col in df1.columns and col in df2.columns]
            if valid_keys:
                # Create unique identifiers
                df1_keys = df1[valid_keys].apply(lambda x: '|'.join(x.astype(str)), axis=1)
                df2_keys = df2[valid_keys].apply(lambda x: '|'.join(x.astype(str)), axis=1)
                
                comparison["data_differences"] = {
                    "records_only_in_file1": len(set(df1_keys) - set(df2_keys)),
                    "records_only_in_file2": len(set(df2_keys) - set(df1_keys)),
                    "common_records": len(set(df1_keys) & set(df2_keys))
                }
            
            return [TextContent(type="text", text=f"CSV Comparison Result:\n{comparison}")]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error comparing CSV files: {str(e)}")]
    
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    """Main entry point for the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())