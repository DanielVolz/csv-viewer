# Backend Tests

This directory contains the complete test suite for the CSV Viewer backend.

## Quick Start

```bash
# Run all tests
python3 -m pytest tests/backend/

# Run with verbose output
python3 -m pytest tests/backend/ -v

# Run specific test file
python3 -m pytest tests/backend/tasks/test_backfill.py -v

# Run with coverage
python3 -m pytest tests/backend/ --cov=backend
```

## Test Statistics

- **Total Tests**: 152
- **Pass Rate**: 100% ✅
- **Runtime**: ~1.9 seconds
- **Framework**: pytest 8.3.4

## Test Structure

```
tests/backend/
├── api/           # 8 files - API endpoint tests
├── tasks/         # 4 files - Celery task tests
└── utils/         # 9 files - Utility function tests
```

## Key Features Tested

### ✅ Backfill Operations (NEW)
- Location snapshots backfill
- Statistics snapshots backfill
- Error handling and retry logic
- Large file set processing

### ✅ Statistics Timeline
- Global and location-specific timelines
- Date grouping (day/week/month)
- Limit parameters and pagination
- Error handling

### ✅ Search Functionality
- MAC address search (historical limits)
- IP address search (prefix matching)
- Serial number search
- Hostname and switch search

### ✅ CSV Processing
- Modern format (with timestamps)
- Legacy format (numbered files)
- Automatic format detection
- Deduplication logic

### ✅ OpenSearch Integration
- Index management
- Query building
- Aggregations
- Health checks

## Documentation

For detailed test documentation, see [docs/TESTING.md](../../docs/TESTING.md)

## Placeholder Tests

Some test files exist as placeholders for future features:
- `test_files_reindex_current.py`
- `test_snapshot_stats.py`
- `test_search_opensearch.py`
- `test_archiver.py`
- `test_opensearch_repair.py`
- `test_opensearch_stats.py`

These contain simple passing tests to prevent test runner errors.

## Requirements

```bash
pytest==8.3.4
pytest-asyncio==1.2.0
pytest-mock==3.15.1
```

## CI/CD

All tests should pass before merging to main branch.
