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

### Development Environment
- Uses dockerized dev environment - no need to restart on code changes
- Frontend: Volume mounts `/src` and `/public` for hot reload
- Backend: Volume mounts entire `/backend` directory with uvicorn reload
- Both services auto-restart on file changes

### Testing Endpoints
Use `curl` instead of browser for endpoint validation:
```bash
# Health check
curl http://localhost:8000/api/files/

# Search test
curl "http://localhost:8000/api/search/?query=test&include_historical=true"

# OpenSearch debugging
curl -X GET "localhost:9200/_cluster/health"
curl -X GET "localhost:9200/_cat/indices"
```

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
- `POST /api/files/reindex` - Trigger manual reindexing

**Search API** (`api/search.py`):
- `GET /api/search/` - Search across CSV files using OpenSearch
- `GET /api/search/index/all` - Trigger background indexing
- `GET /api/search/index/status/{task_id}` - Check indexing status

## Configuration Management

### Environment Variables
Core settings in `.env`:
```bash
CSV_FILES_DIR=/app/data  # Always use absolute path
FRONTEND_DEV_PORT=3001   # Dev port differs from prod
BACKEND_PORT=8000
OPENSEARCH_PORT=9200
OPENSEARCH_TRANSPORT_PORT=9300
OPENSEARCH_DASHBOARDS_PORT=5601
OPENSEARCH_INITIAL_ADMIN_PASSWORD=your-secure-password
```

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
```
