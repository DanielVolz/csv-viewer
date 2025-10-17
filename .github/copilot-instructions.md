# CSV Viewer AI Coding Instructions

## Architecture Overview

This is a dockerized full-stack CSV search application designed for viewing, searching, and managing network data stored in CSV files. It provides real-time search capabilities, file monitoring, and automatic indexing using modern web technologies.

### Primary Use Case
- View and search CSV files containing network device information (IP addresses, MAC addresses, switch configurations, etc.)
- Monitor file changes and automatically reindex data
- Provide historical file search capabilities
- Download and preview CSV data through a web interface

### Key Components
- **Frontend**: React 18 + Material-UI (MUI) 6, served on port 3000 (exposed as 5000 in dev)
- **Backend**: FastAPI + Pydantic + Uvicorn, container listens on 8000 (exposed as 8002 in dev)
- **Search**: OpenSearch cluster on port 9200
- **Queue**: Redis for Celery task management on port 6379
- **File Monitoring**: Watchdog monitors `/app/data` for CSV changes

## Development Workflow

### Starting the Application
```bash
# Development mode with hot reload
./app.sh start dev

# Production mode (AMD64/ARM)
./app.sh start amd64
./app.sh stop
```

**Critical**: After `docker-compose up`, wait 30 seconds before running additional terminal commands to avoid canceling the startup process.

Startup behavior update
- The backend no longer blocks on OpenSearch cluster health at startup. Indexing is triggered best‑effort and will proceed once services are ready. Use the curl diagnostics below to check OpenSearch health, but backend startup won’t wait for green/yellow.

### Development Environment
- Uses dockerized dev environment - no need to restart on code changes
- Frontend: Volume mounts `/src` and `/public` for hot reload
- Backend: Volume mounts entire `/backend` directory with uvicorn reload
- Both services auto-restart on file changes

**CRITICAL Hot-Reload Limitation**:
- ✅ **Uvicorn (FastAPI endpoints)**: Hot reload WORKS - code changes take effect immediately
- ❌ **Celery Workers**: Hot reload DOES NOT WORK - workers run in separate process
- **Solution**: Manual container restart required after Celery task code changes:
  ```bash
  docker restart csv-viewer-backend-dev
  ```
- **Why**: Celery ForkPoolWorkers spawn from initial process and don't watch for file changes
- **Debugging Hint**: If code changes don't take effect but no errors appear, check if the code path involves Celery tasks

### Critical Port Information
- Frontend Dev (host): 5000 (FRONTEND_DEV_PORT in .env.dev) - NOT 3000!
- Backend Dev (host): 8002 (BACKEND_DEV_PORT in .env.dev) -> container 8000
- OpenSearch: 9200
- Redis: 6379
Notes:
- Frontend container runs on 3000, exposed on 5000 in development
- Backend container listens on 8000, exposed on 8002 in development

### Testing Endpoints
Use `curl` instead of browser for endpoint validation (dev host backend is on 8002):
```bash
# Health check
curl http://localhost:8002/api/files/

# Search test
curl "http://localhost:8002/api/search/?query=test&include_historical=true"

# Location statistics (requires query parameter)
curl "http://localhost:8002/api/stats/fast/by_location?q=ABX01"

# Reindex netspeed.csv only (fast, for development testing)
curl http://localhost:8002/api/files/reindex/current

# Reindex all CSV files (slower, comprehensive)
curl http://localhost:8002/api/files/reindex

# OpenSearch debugging
curl -X GET "localhost:9200/_cluster/health"
curl -X GET "localhost:9200/_cat/indices"

# Direct OpenSearch document inspection
curl -X GET "localhost:9200/stats_netspeed_loc/_search" -H 'Content-Type: application/json' -d '{"query": {"term": {"key": "ABX01"}}, "size": 1}'
```

Caching behavior and invalidation
- Statistics endpoints (`/api/stats/*`) use small in‑memory caches (typically 30–60s TTL) for speed.
- Caches are invalidated immediately when any reindex is triggered, so development changes are visible on the next request:
  - Full rebuild: `GET /api/search/index/all`
  - Fast dev reindex: `GET /api/files/reindex/current`
  - File watcher detects netspeed file changes
- You generally don’t need manual cache clears; waiting is unnecessary after a reindex.

## Project-Specific Patterns

### File Naming Convention
- **Modern files**: `netspeed_YYYYMMDD-HHMMSS.csv` (with timestamp, ALWAYS has headers)
- **Legacy files**: `netspeed.csv.0-29` (no headers, variable column counts 11-15)
- Legacy files archived after: **2025-10-27**

### File Locations in Container
- **Current netspeed file**: `/app/data/netspeed/netspeed_YYYYMMDD-HHMMSS.csv` (tagesaktuelle Datei mit Timestamp, z.B. `netspeed_20251016-062247.csv`)
- **Historical files**: `/app/data/history/netspeed/` (if separate directory configured)
- **Archive**: `/app/data/archive/` (older archived files)
- **File watcher monitors**: `/app/data` directory for changes

### CSV Format Handling - CRITICAL ARCHITECTURE

The system uses **TWO COMPLETELY SEPARATE approaches** for modern vs legacy files:

#### MODERN Files (with timestamp, >= 16 columns)
- **Fully Automatic**: Headers read from first row of EACH file
- **No code changes needed**: New columns automatically recognized
- **No container restart needed**: Headers detected per-file at read time
- **Implementation**: `_map_modern_format_row()` + `_read_headers_from_file()`
- **Key principle**: Never cache headers, always read from file

**CRITICAL: Feldnamen für Call Manager müssen exakt lauten:**
  - `Call Manager Active Sub`
  - `Call Manager Standby Sub`
Diese Namen müssen in OpenSearch-Mapping und CSV identisch sein. Die alten Felder `CallManager 1/2/3` sind nur für Legacy-Indices und werden nicht mehr verwendet.

#### LEGACY Files (no timestamp, < 16 columns)
- **Pattern Detection**: Detects fields by analyzing data (IP, MAC, hostname patterns)
- **Temporary Solution**: Code marked for removal after 2025-10-27
- **Implementation**: `_map_legacy_format_with_pattern_detection()`
- **Known formats**: 11, 14, 15 columns (defined in `KNOWN_HEADERS`)
- **Purpose**: Bridge until all legacy files archived

**NEVER mix these approaches!** Modern files must NEVER use pattern detection.
Legacy files must NEVER use header-based mapping.

Handle both in `utils/csv_utils.py` with format detection logic.

### OpenSearch Index Management
- Index naming: `netspeed_{sanitized_filename}`
- Current file index: `netspeed_netspeed_csv`
- Historical search queries across all `netspeed_*` indices
- Auto-cleanup of old indices when files update
- Pre-clean on full rebuild: calling `GET /api/search/index/all` deletes existing `netspeed_*` indices up-front to avoid duplicates and index bloat (file watcher performs the same cleanup).

### Celery Task Patterns
Tasks are defined in `backend/tasks/tasks.py`:
```python
@app.task(name='tasks.index_csv')
def index_csv(file_path: str) -> dict:
    # Always return structured dict with status/message/count
```

### React Hook Patterns
Custom hooks in `frontend/src/hooks/` follow this structure:
```javascript
function useSearchCSV() {
  // State management with loading/error/data pattern
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Return object with functions and state
  return { searchAll, results, loading, error };
}
```

### File Watcher Integration
The `utils/file_watcher.py` automatically triggers reindexing:
- Monitors `/app/data` directory
- Triggers cleanup of existing indices before reindexing
- Handles both file creation and modification events
- Waits 2 seconds after modification to ensure file is completely written

### Key API Endpoints
**Files API** (`api/files.py`):
- `GET /api/files/` - List all CSV files with metadata
- `GET /api/files/netspeed_info` - Get current file information
- `GET /api/files/preview` - Preview CSV data with pagination
- `GET /api/files/download/{filename}` - Download specific files
- `GET /api/files/reindex` - Trigger manual reindexing of all CSV files (Celery-based, async)
- `GET /api/files/reindex/current` - **Development**: Fast reindex of netspeed.csv only (direct, synchronous)
  - Also invalidates stats caches immediately so the UI reflects changes on the very next request.

**Search API** (`api/search.py`):
- `GET /api/search/` - Search across CSV files using OpenSearch
- `GET /api/search/index/all` - Trigger background indexing
- `GET /api/search/index/status/{task_id}` - Check indexing status
  - On `index/all`, caches are invalidated first and existing `netspeed_*` indices are cleaned before the rebuild begins.

**Statistics API** (`api/stats.py`):
- `GET /api/stats/current` - Get current file statistics from OpenSearch snapshots
- `GET /api/stats/fast/by_location?q={location}` - Get location-specific statistics with VLAN usage, switches, and KEM phones
- `GET /api/stats/locations` - List all available locations
- **CRITICAL**: Location stats endpoints require `q` parameter, will return 422 error if missing

## Configuration Management

### Environment Variables
Core settings in `.env` (dev host ports shown):
```bash
CSV_FILES_DIR=/app/data  # Always use absolute path
# Optional split layout (if current and historical netspeed files are stored separately)
# If unset they fall back to CSV_FILES_DIR
NETSPEED_CURRENT_DIR=/usr/scripts/netspeed/data/netspeed
NETSPEED_HISTORY_DIR=/usr/scripts/netspeed/data/history/netspeed
FRONTEND_DEV_PORT=5000   # Dev host port for frontend
BACKEND_DEV_PORT=8002    # Dev host port for backend
BACKEND_PORT=8000        # Backend container listen port
OPENSEARCH_PORT=9200
OPENSEARCH_TRANSPORT_PORT=9300
OPENSEARCH_DASHBOARDS_PORT=5601
OPENSEARCH_INITIAL_ADMIN_PASSWORD=your-secure-password
ARCHIVE_RETENTION_YEARS=4   # OpenSearch archive retention (min 1, defaults to 4 if unset)
```
Notes:
- Archive retention applies to the `archive_netspeed` OpenSearch index and is enforced during archive indexing. Filesystem archives in `/app/data/archive/` are separate.

### Multi-Architecture Support
- `docker-compose.yml` - AMD64 production
- `docker-compose.arm.yml` - ARM64 production
- `docker-compose.dev.yml` - Development (architecture-agnostic)

### Settings Pattern
Backend uses Pydantic BaseSettings in `config.py`:
```python
class Settings(BaseSettings):
    CSV_FILES_DIR: str = "/app/data"
    OPENSEARCH_URL: str = "http://opensearch:{OPENSEARCH_PORT}"
  ARCHIVE_RETENTION_YEARS: int = 4  # OpenSearch archive retention (min 1)
```

## Testing Strategy

### Backend Tests
Located in `tests/backend/`:
- Use pytest with fixtures in `conftest.py`
- Mock external dependencies (OpenSearch, Redis)
- Run with: `python -m pytest tests/backend`

### Frontend Tests
Located in component `__tests__/` directories:
- Use Jest + React Testing Library
- Mock all API calls
- Run with: `npm test` in frontend directory

## Key Integration Points

### API Communication
- Frontend uses axios with relative URLs (`/api/search/`)
- Backend serves API on `/api/` prefix
- CORS configured for development origins

### Search Query Flow
1. Frontend debounces search input (1 second delay)
2. API calls `GET /api/search/` with query params
3. Backend queues Celery task for OpenSearch query
4. Results returned with pagination metadata

### File Processing Pipeline
1. File watcher detects CSV changes
2. Triggers `index_csv` Celery task
3. CSV parsed with delimiter/format detection
4. Bulk indexed to OpenSearch (1000-doc chunks)
5. Frontend search reflects new data immediately

## Search Query Architecture

### Pattern-Based Query Detection
The search system uses intelligent pattern detection to determine which OpenSearch query to execute. Pattern checks occur in `backend/utils/opensearch.py` in the `_build_query_body()` function with an **early return strategy** - once a pattern matches, the specific query is returned immediately.

**Critical Pattern Order** (lines ~2220-2420):
1. **Phone Pattern** (7-15 digits): Routes to phone number search
2. **Hostname Pattern** (contains dots): Routes to hostname search
3. **4-Digit Model Pattern**: Routes to model search
4. **Full IP Pattern** (4 octets with dots): Routes to IP search
5. **Partial IP Pattern** (has dot): Routes to partial IP search
6. **Serial Number Pattern** (5+ alphanumeric): Routes to serial search
7. **3-Digit Voice VLAN Pattern** (exactly 3 digits): Routes to Voice VLAN field-specific search
8. **Broad Query** (fallback): Multi-field wildcard search

### Voice VLAN Search Implementation
**Problem Solved**: Query "802" was matching ALL 19,169 documents instead of only the 5,958 with Voice VLAN "802".

**Root Cause**:
- Without 3-digit pattern check, "802" triggered broad multi-field query
- Matched IP addresses (10.802.x.x), phone numbers (+498028...), and other fields
- IP pattern required dots but broad query didn't

**Solution** (lines 2369-2383):
```python
# Check for 3-digit Voice VLAN pattern (e.g., "801", "802", "803")
if re.fullmatch(r"\d{3}", qn or ""):
    from utils.csv_utils import DEFAULT_DISPLAY_ORDER as DESIRED_ORDER
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

**Key Design Principles**:
1. **Pattern Order Matters**: More specific patterns (3-digit) must come BEFORE broad patterns
2. **Early Return Strategy**: Once a pattern matches, return immediately - don't continue checking
3. **Field-Specific Queries**: Use `term` query for exact field matching when possible
4. **Dot Requirement for IPs**: IP patterns require dots to avoid false matches
5. **Minimum Length Requirements**: Serial numbers require 5+ characters to avoid matching short numbers

**Validation Strategy**:
```bash
# Direct OpenSearch query to verify expected count
curl -X GET "localhost:9200/netspeed_*/_count" -H 'Content-Type: application/json' \
  -d '{"query": {"term": {"Voice VLAN": "802"}}}'

# API search query
curl "http://localhost:8002/api/search/?query=802"

# Both should return identical counts
```

**Performance**: Pattern check with early return is extremely fast (~0.4s for 5,958 results).

## Common Gotchas

- Never restart the app during development - use volume mounts for hot reload
- Always use absolute paths for file operations (`/app/data/`)
- OpenSearch field mappings are critical - defined in `utils/opensearch.py`
- Celery tasks must return structured dicts for proper error handling
- Frontend pagination expects backend to return `totalItems` and `totalPages`
- If stats/timelines look stale, remember they are cached briefly. Any reindex or a netspeed file change clears caches immediately; otherwise, caches expire automatically within ~30–60 seconds.

## Critical Debugging Patterns

### Location Statistics Enhancement Issues
When adding new fields to location statistics (like VLAN usage, switches, KEM phones):

1. **Data Collection**: Enhance `location_details` collection in `tasks/tasks.py` `index_csv()` function
2. **Document Creation**: Add new fields to `loc_docs.append()` dictionary in same function
3. **OpenSearch Persistence**: **CRITICAL** - Update `index_stats_location_snapshots()` in `utils/opensearch.py` to include new fields in the `body` dictionary
4. **API Response**: Fields will automatically appear in `/api/stats/fast/by_location` responses

**Common Error**: New fields collected in `location_details` but not persisting to OpenSearch because `index_stats_location_snapshots()` function doesn't include them in the `body` dictionary.

### Data Source Confusion
- **Container Path**: Data files are mounted as `/app/data` inside container
- **Host Path**: Controlled by `CSV_FILES_DIR` environment variable in `.env.dev`
- **Volume Mount**: `${CSV_FILES_DIR}:/app/data` in `docker-compose.dev.yml`
- **Never assume data location** - always check volume mounts and environment variables

### OpenSearch Index Management
- Location statistics stored in `stats_netspeed_loc` index
- Document ID format: `{file}:{date}:{location_key}`
- Test documents can interfere with real data queries
- Use `delete_by_query` to clean test data before production queries

## Critical Lessons Learned

### Port Configuration Errors
- NEVER assume frontend runs on port 3000 in development
- Frontend dev host port: `FRONTEND_DEV_PORT=5000` in `.env.dev`
- Backend dev host port: `BACKEND_DEV_PORT=8002` in `.env.dev` (container 8000)
- Always check `.env.dev` for actual port configurations and mappings

### Volume Mount Issues
- Real data location is controlled by `CSV_FILES_DIR` in environment files
- Do not assume `/app/data` contains test data - it is production data
- Always verify data source with: `docker exec -it csv-viewer-backend-dev ls -la /app/data/`
- Volume mount: `${CSV_FILES_DIR}:/app/data` means host `CSV_FILES_DIR` maps to container `/app/data`

### OpenSearch Field Addition Workflow
**Critical 3-Step Process** for adding new fields to location statistics:
1. **Data Collection**: Add field collection logic in `tasks/tasks.py` `location_details` dictionary
2. **Document Structure**: Include new fields in `loc_docs.append()` call
3. **Persistence Fix**: **MUST** update `index_stats_location_snapshots()` in `utils/opensearch.py` to include new fields in `body` dictionary

**Most Common Error**: Steps 1-2 completed but step 3 forgotten, causing data to be collected but never saved to OpenSearch.

### Startup health checks
- Backend startup no longer waits for OpenSearch to report green/yellow. Prefer using the provided curl checks to validate OpenSearch separately; the backend will trigger indexing without blocking.

### API Endpoint Patterns
- Location statistics endpoints **require** `q` parameter (will return 422 if missing)
- Use `/api/stats/fast/by_location` instead of deprecated `/api/stats/by_location`
- Always test with `curl` not browser to avoid caching issues
- OpenSearch document queries should target specific indices like `stats_netspeed_loc`

### Development Debugging Strategy
1. **Verify data collection** with direct Python execution in container
2. **Check OpenSearch document structure** with direct curl queries
3. **Test API endpoint** with curl using query parameters
4. **Validate volume mounts** and environment variables when data seems wrong

### Development Reindex Capabilities
**Critical for Testing Changes**: The system provides dedicated development reindex functionality:

- **Fast Development Reindex**: `GET /api/files/reindex/current`
  - **Purpose**: Quick testing of code changes affecting netspeed.csv only
  - **Behavior**: Synchronous, direct execution (no Celery task)
  - **Index Management**: Deletes existing `netspeed_netspeed_csv` index before recreation
  - **Performance**: Fast execution suitable for iterative development
  - **Use Case**: Testing statistics calculations, counting logic fixes, field additions

- **Full Production Reindex**: `GET /api/files/reindex`
  - **Purpose**: Complete reindexing of all CSV files
  - **Behavior**: Asynchronous Celery task with progress tracking
  - **Index Management**: Deletes all existing indices before recreation
  - **Performance**: Slower, comprehensive processing
  - **Use Case**: Production deployments, major schema changes

**Development Workflow**: Use `/reindex/current` for rapid iteration when testing (dev host backend on 8002):
```bash
# 1. Make code changes to statistics/counting logic
# 2. Quick reindex for testing
curl http://localhost:8002/api/files/reindex/current
# 3. Verify results
curl "http://localhost:8002/api/stats/fast/by_location?q=ABX01"
```

## Operational Practices
- Always execute diagnostic CLI commands yourself from within the repo; do not delegate routine curl checks to the user. Capture and summarize the outputs in your response.
- When sharing shell commands, place each single command in its own fenced block and avoid chaining multiple commands in one terminal invocation.
- Production reindex trigger (run from project root):
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend-prod curl -s http://localhost:8001/api/search/index/all
  ```

## Useful Debugging Commands

```bash
# Check service health
./app.sh status

# View logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f opensearch

# OpenSearch debugging
curl -X GET "localhost:9200/_cluster/health"
curl -X GET "localhost:9200/_cat/indices"

# Celery monitoring
docker exec -it csv-viewer-backend celery -A tasks.tasks inspect active

# Location statistics debugging
curl -X GET "localhost:9200/stats_netspeed_loc/_search" -H 'Content-Type: application/json' -d '{"query": {"term": {"key": "ABX01"}}, "size": 1}'

# Test single file indexing (development)
docker exec -it csv-viewer-backend-dev python -c "from tasks.tasks import index_csv; print(index_csv('/app/data/netspeed/*'))"

# Check environment variables and volume mounts
docker exec -it csv-viewer-backend-dev env | grep CSV_FILES_DIR
docker exec -it csv-viewer-backend-dev ls -la /app/data/
```

## Recent Verification
- `curl -s http://localhost:9200/_cluster/health` returns `status: green` with 1 data node (verified 2025-09-29)
- `/api/stats/fast/by_location?q=<code>` now returns populated `switches` and `kemPhones` arrays for `netspeed.csv` snapshots after the September 2025 fix
