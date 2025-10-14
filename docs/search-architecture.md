# Search Architecture

This document describes the search query architecture and pattern detection system used in the CSV Viewer application.

## Overview

The search system uses intelligent pattern detection to route queries to the most appropriate OpenSearch query type. This ensures fast, accurate results by avoiding broad multi-field searches when a specific field can be targeted.

## Pattern Detection Flow

Patterns are checked in `backend/utils/opensearch.py` in the `_build_query_body()` function using an **early return strategy**. Once a pattern matches, the function immediately returns the specific query - no further patterns are checked.

### Pattern Priority Order

The order of pattern checks is **critical** for correctness:

```python
# Located at lines ~2220-2420 in backend/utils/opensearch.py

1. Phone Pattern         (7-15 digits)
2. Hostname Pattern      (contains dots)
3. 4-Digit Model Pattern (exactly 4 digits)
4. Full IP Pattern       (4 octets with 3 dots)
5. Partial IP Pattern    (has at least one dot)
6. Serial Number Pattern (5+ alphanumeric characters)
7. 3-Digit VLAN Pattern  (exactly 3 digits) ← Added 2025-10-14
8. Broad Multi-Field     (fallback for everything else)
```

## Pattern Implementations

### 1. Phone Number Pattern

```python
# Pattern: 7-15 consecutive digits
if re.fullmatch(r"\d{7,15}", qn or ""):
    return {
        "query": {"wildcard": {"Line Number": f"*{qn}*"}},
        "_source": DESIRED_ORDER,
        "size": size
    }
```

**Example Queries**: `12345678`, `4912345678`, `+4912345678901`

### 2. Hostname Pattern

```python
# Pattern: Contains dot(s)
if '.' in qn:
    return {
        "query": {"wildcard": {"Switch Hostname": f"*{qn}*"}},
        "_source": DESIRED_ORDER,
        "size": size
    }
```

**Example Queries**: `switch01.domain.com`, `10.20.30.40`, `example.com`

### 3. 4-Digit Model Pattern

```python
# Pattern: Exactly 4 digits
if re.fullmatch(r"\d{4}", qn):
    return {
        "query": {"wildcard": {"Model Name": f"*{qn}*"}},
        "_source": DESIRED_ORDER,
        "size": size
    }
```

**Example Queries**: `7841`, `8851`, `9861`

### 4. Full IP Address Pattern

```python
# Pattern: 4 octets with dots (basic validation)
if re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", qn or ""):
    return {
        "query": {"term": {"IP Address": qn}},
        "_source": DESIRED_ORDER,
        "size": size
    }
```

**Example Queries**: `10.20.30.40`, `192.168.1.1`

### 5. Partial IP Pattern

```python
# Pattern: Has dot (but not full IP)
if '.' in (qn or ""):
    return {
        "query": {"wildcard": {"IP Address": f"{qn}*"}},
        "_source": DESIRED_ORDER,
        "size": size
    }
```

**Example Queries**: `10.20`, `192.168.1`

### 6. Serial Number Pattern

```python
# Pattern: 5+ alphanumeric characters
if len(qn or "") >= 5 and (qn or "").replace(" ", "").isalnum():
    return {
        "query": {"wildcard": {"Serial Number": f"*{qn}*"}},
        "_source": DESIRED_ORDER,
        "size": size
    }
```

**Example Queries**: `FVH28441`, `WZP25470`, `FCH26112`

**Why 5+ characters?**: Prevents false matches with short numbers like "802" or "123"

### 7. Voice VLAN Pattern (3-Digit Numbers)

```python
# Pattern: Exactly 3 digits
if re.fullmatch(r"\d{3}", qn or ""):
    return {
        "query": {"term": {"Voice VLAN": qn}},
        "_source": DESIRED_ORDER,
        "size": size,
        "sort": [
            {"Creation Date": {"order": "desc"}},
            self._preferred_file_sort_clause(),
            {"_score": {"order": "desc"}}
        ]
    }
```

**Example Queries**: `801`, `802`, `803`

**Why Added**: Without this pattern, 3-digit queries would fall through to the broad multi-field search, causing false matches in IP addresses, phone numbers, and other fields.

**Performance**: Uses OpenSearch `term` query for exact field matching - extremely fast.

### 8. Broad Multi-Field Search (Fallback)

```python
# Fallback for queries that don't match any specific pattern
return {
    "query": {
        "query_string": {
            "query": f"*{qn}*",
            "fields": ["*"],
            "default_operator": "AND"
        }
    },
    "_source": DESIRED_ORDER,
    "size": size,
    "sort": [...]
}
```

**Example Queries**: `switch`, `Munich`, `GigabitEthernet`, `ABCD`

## Case Study: Voice VLAN Search Fix

### Problem

Searching for "802" returned **all 19,169 documents** instead of the expected **5,958 documents** with Voice VLAN "802".

### Root Cause Analysis

Without the 3-digit pattern check, query "802" fell through to the broad multi-field search, which matched:

- **IP Addresses**: `10.802.x.x`, `192.168.802.x`
- **Phone Numbers**: `+498028...`, line numbers containing "802"
- **MAC Addresses**: Segments containing "802"
- **Hostnames**: Names containing "802"
- **Serial Numbers**: Serials containing "802"

### Solution Implementation

Added 3-digit pattern check at line 2369 (before broad query fallback):

```python
# Check for 3-digit Voice VLAN pattern
if re.fullmatch(r"\d{3}", qn or ""):
    from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
    logger.info(f"🔍 MATCHED 3-DIGIT VOICE VLAN PATTERN: query='{qn}'")
    return {
        "query": {"term": {"Voice VLAN": qn}},
        "_source": DESIRED_ORDER,
        "size": size,
        "sort": [
            {"Creation Date": {"order": "desc"}},
            self._preferred_file_sort_clause(),
            {"_score": {"order": "desc"}}
        ]
    }
```

### Validation

```bash
# Direct OpenSearch verification (expected: 5958)
curl -X GET "localhost:9200/netspeed_*/_count" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"term": {"Voice VLAN": "802"}}}'
# Result: {"count": 5958}

# API search (should match OpenSearch count)
curl "http://localhost:8002/api/search/?query=802"
# Result: "Found 5958 results for '802'"
```

### Results

- ✅ Correct document count: 5,958 (down from 19,169)
- ✅ All results have `"vlan": "802"`
- ✅ Fast query execution: ~0.4 seconds
- ✅ No false positives from other fields

## Pattern Design Principles

### 1. Specificity Before Generality

More specific patterns (3-digit, 4-digit) must be checked **before** less specific patterns (has dot, broad search).

**Example**: "802" should match Voice VLAN pattern before falling to broad search.

### 2. Early Return Strategy

Once a pattern matches, return immediately. Don't check additional patterns.

**Benefit**: Ensures correct query type and improves performance.

### 3. Field-Specific Queries When Possible

Use OpenSearch `term` queries for exact field matching instead of `wildcard` or `query_string`.

**Benefit**: Faster execution and more accurate results.

### 4. Pattern Constraints

Add constraints to prevent false positives:

- **IP patterns require dots**: Prevents "802" from matching IP field
- **Serial numbers require 5+ characters**: Prevents "802" from matching serial field
- **Phone numbers require 7+ digits**: Prevents short numbers from matching

### 5. Minimum Length Requirements

Short queries (1-2 characters) can cause performance issues with wildcard searches. Consider minimum lengths for patterns.

## Testing Pattern Changes

### Local Development Testing

```bash
# 1. Make pattern changes in backend/utils/opensearch.py
# 2. Restart container (Celery workers don't hot-reload!)
docker restart csv-viewer-backend-dev

# 3. Wait for restart
sleep 10

# 4. Test query
curl "http://localhost:8002/api/search/?query=802"

# 5. Verify against OpenSearch
curl -X GET "localhost:9200/netspeed_*/_count" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"term": {"Voice VLAN": "802"}}}'
```

### Verification Checklist

When adding or modifying patterns:

- [ ] Pattern is specific enough to avoid false matches
- [ ] Pattern is positioned correctly in priority order
- [ ] Early return is used (no fall-through to broad query)
- [ ] Direct OpenSearch count matches API search count
- [ ] Sample results verified manually
- [ ] Performance is acceptable (< 1 second for typical queries)
- [ ] Edge cases tested (empty, whitespace, special characters)

## Common Pattern Issues

### Issue: Pattern Too Broad

**Symptom**: Too many irrelevant results

**Solution**: Add more constraints to pattern regex or use more specific field query

**Example**: Original IP pattern `\d+\.\d+` matched "1.2" and "10.2" - needed full 4-octet pattern

### Issue: Pattern Order Wrong

**Symptom**: Correct pattern exists but wrong query executes

**Solution**: Move more specific pattern earlier in check order

**Example**: 3-digit VLAN pattern must come before broad query fallback

### Issue: Pattern Missing Constraints

**Symptom**: Short queries match when they shouldn't

**Solution**: Add minimum length or character requirements

**Example**: Serial pattern requires 5+ characters to avoid matching "802"

## Performance Considerations

### Query Types by Speed (Fastest to Slowest)

1. **term query** (exact match): ~0.01s
   - Used for: Full IP addresses, Voice VLAN

2. **prefix query**: ~0.05s
   - Used for: Partial IP addresses

3. **wildcard query** (single field): ~0.1s
   - Used for: Phone numbers, hostnames, serials, models

4. **query_string** (multi-field): ~0.5s+
   - Used for: Broad fallback search

### Optimization Strategy

Route queries to fastest applicable query type by using specific patterns.

## Future Enhancements

### Potential Pattern Additions

1. **MAC Address Pattern**: `XX:XX:XX:XX:XX:XX` or `XXXXXXXXXXXX`
2. **Switch Port Pattern**: `GigabitEthernet1/0/X`
3. **Location Code Pattern**: `ABC##` format
4. **Date Pattern**: `YYYY-MM-DD` or `YYYYMMDD`

### Pattern Improvements

1. **Fuzzy Matching**: Allow typos in hostname/serial searches
2. **Range Queries**: Support `10.20.30.1-50` IP ranges
3. **Boolean Operators**: Support `AND`, `OR`, `NOT` in queries
4. **Field Prefixes**: Support `ip:10.20.30.40` or `vlan:802` syntax

## Related Documentation

- [OpenSearch Query DSL](https://opensearch.org/docs/latest/query-dsl/)
- [Backend API Documentation](../backend/api/search.py)
- [Testing Guide](./TESTING.md)
- [Docker Setup](./docker-setup.md)

## Maintenance Notes

- Pattern detection code: `backend/utils/opensearch.py` lines ~2220-2420
- Test queries: `tests/backend/test_search.py`
- Last major update: 2025-10-14 (3-digit VLAN pattern added)
