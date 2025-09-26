# CSV Viewer AI Coding Instructions

## Architecture Overview

This is a dockerized full-stack CSV search application designed for viewing, searching, and managing network data stored in CSV files. It provides real-time search capabilities, file monitoring, and automatic indexing using modern web technologies.

### Primary Use Case
- View and search CSV files containing network device information (IP addresses, MAC addresses, switch configurations, etc.)
- Monitor file changes and automatically reindex data
- Provide historical file search capabilities
- Download and preview CSV data through a web interface

### Key Components
- **Frontend**: React 18 + Material-UI (MUI) 6, served on port 3000
- **Backend**: FastAPI + Pydantic + Uvicorn, served on port 8000
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

### Critical Port Information
- **Frontend Dev**: Port 5000 (FRONTEND_DEV_PORT in .env.dev) - NOT 3000!
- **Backend Dev**: Port 8000 (BACKEND_DEV_PORT in .env.dev)
- **OpenSearch**: Port 9200
- **Redis**: Port 6379
- Frontend container internally runs on port 3000, but is exposed on port 5000 in development

### Testing Endpoints
Use `curl` instead of browser for endpoint validation:
```bash
# Health check
curl http://localhost:8000/api/files/

# Search test
curl "http://localhost:8000/api/search/?query=test&include_historical=true"

# Location statistics (requires query parameter)
curl "http://localhost:8000/api/stats/fast/by_location?q=ABX01"

# Reindex netspeed.csv only (fast, for development testing)
curl http://localhost:8000/api/files/reindex/current

# Reindex all CSV files (slower, comprehensive)
curl http://localhost:8000/api/files/reindex

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
- `netspeed.csv` - Current/active file (always indexed first)
- `netspeed.csv.0`, `netspeed.csv.1` - Historical files
- `netspeed.csv_bak` - Backup files

### CSV Format Detection
The system auto-detects two CSV formats:
- **Old format**: 11 columns
- **New format**: 14 columns

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
Core settings in `.env`:
```bash
CSV_FILES_DIR=/app/data  # Always use absolute path
# Optional split layout (if current and historical netspeed files are stored separately)
# If unset they fall back to CSV_FILES_DIR
NETSPEED_CURRENT_DIR=/usr/scripts/netspeed/data/netspeed
NETSPEED_HISTORY_DIR=/usr/scripts/netspeed/data/history/netspeed
FRONTEND_DEV_PORT=3001   # Dev port differs from prod
BACKEND_PORT=8000
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
- **NEVER assume frontend runs on port 3000 in development**
- Frontend development port is configured as `FRONTEND_DEV_PORT=5000` in `.env.dev`
- Container internally runs on port 3000, but host mapping is to port 5000
- Always check `.env.dev` for actual port configurations

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

**Development Workflow**: Use `/reindex/current` for rapid iteration when testing:
```bash
# 1. Make code changes to statistics/counting logic
# 2. Quick reindex for testing
curl http://localhost:8000/api/files/reindex/current
# 3. Verify results
curl "http://localhost:8000/api/stats/fast/by_location?q=ABX01"
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
docker exec -it csv-viewer-backend-dev python -c "from tasks.tasks import index_csv; print(index_csv('/app/data/netspeed.csv'))"

# Check environment variables and volume mounts
docker exec -it csv-viewer-backend-dev env | grep CSV_FILES_DIR
docker exec -it csv-viewer-backend-dev ls -la /app/data/
```
