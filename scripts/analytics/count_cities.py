#!/usr/bin/env python3
"""Count unique city codes from a netspeed CSV file.

City code definition:
  Extract the prefix (substring before the first dash '-') from the 'Switch Hostname' column.

Assumptions:
  - Delimiter is ';' if present in file, otherwise ','.
  - 'Switch Hostname' resides in normalized 16-column format at index 12 (0-based) if using KNOWN_HEADERS[16].
    But historical / varied formats are handled by a fallback heuristic scanning columns for a value containing '.juwin.' or other domain parts.

Usage:
  python scripts/analytics/count_cities.py --file /usr/scripts/netspeed/netspeed.csv
  python scripts/analytics/count_cities.py  # defaults to ./test-data/netspeed.csv

Output:
  Prints total unique cities and an alphabetical list.
"""
from __future__ import annotations
import argparse
import csv
import os
import sys
from collections import Counter
from typing import Iterable, Set, Tuple

DOMAIN_MARKERS = ('.juwin.', '.corp', '.lan', '.local', '.example')

# Pattern variants we might encounter:
# 1. Classic: BER18-EDGE2.lan (city code before first dash)
# 2. New compressed: ABx01ZSL4120P.juwin.bayern.de (no dash; we want the leading alpha sequence before first digit cluster)
COMPRESSED_CITY_REGEX = __import__('re').compile(r'^(?P<city>[A-Za-zÄÖÜäöüß]{2,6})\d')


def detect_delimiter(path: str) -> str:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        sample = f.read(4096)
    return ';' if ';' in sample else ','


def extract_hostname(row: Iterable[str]) -> str | None:
    # Try direct positions where Switch Hostname commonly appears (12, 10, 9, 11)
    preferred_indices = [12, 10, 9, 11]
    row_list = list(row)
    for idx in preferred_indices:
        if idx < len(row_list):
            val = row_list[idx].strip()
            if any(m in val for m in DOMAIN_MARKERS):
                return val
    # Fallback scan
    for cell in row_list:
        c = cell.strip()
        if any(m in c for m in DOMAIN_MARKERS):
            return c
    return None


def city_from_hostname(host: str) -> str | None:
    if not host:
        return None
    host = host.strip()
    # Case 1: has dash pattern
    if '-' in host:
        city = host.split('-', 1)[0].strip()
        return city.upper() if city else None
    # Case 2: compressed pattern without dash (e.g. ABx01ZSL4120P.juwin.bayern.de)
    # Strip domain first
    core = host.split('.', 1)[0]
    m = COMPRESSED_CITY_REGEX.match(core)
    if m:
        return m.group('city').upper()
    return None


def count_cities(csv_path: str) -> Tuple[Set[str], Counter]:
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"File not found: {csv_path}")
    delimiter = detect_delimiter(csv_path)
    cities: Set[str] = set()
    city_counter: Counter = Counter()

    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f, delimiter=delimiter)
        for row in reader:
            if not row or all(not c.strip() for c in row):
                continue
            host = extract_hostname(row)
            if not host:
                continue
            city = city_from_hostname(host)
            if city:
                cities.add(city)
                city_counter[city] += 1
    # Ensure all cities are uppercase (defensive) and merge any accidental mixed case duplicates
    normalized_counter: Counter = Counter()
    for city, cnt in city_counter.items():
        normalized_counter[city.upper()] += cnt
    cities = {c.upper() for c in cities}
    return cities, normalized_counter


def main() -> int:
    parser = argparse.ArgumentParser(description="Count unique city codes in netspeed CSV")
    parser.add_argument('--file', '-f', default='test-data/netspeed.csv', help='Path to netspeed CSV (default: test-data/netspeed.csv)')
    parser.add_argument('--top', type=int, default=0, help='Show top N cities by occurrence (0 = skip)')
    args = parser.parse_args()

    try:
        cities, counts = count_cities(args.file)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    sorted_cities = sorted(cities)
    print(f"Total unique cities: {len(sorted_cities)}")
    print(', '.join(sorted_cities))

    if args.top > 0:
        print('\nTop cities:')
        for city, cnt in counts.most_common(args.top):
            print(f"  {city}: {cnt}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
