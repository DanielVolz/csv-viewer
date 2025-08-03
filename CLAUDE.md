# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# CSV Viewer - Documentation

## Project Overview

The CSV Viewer is a full-stack web application designed for viewing, searching, and managing network data stored in CSV files. It provides real-time search capabilities, file monitoring, and automatic indexing using modern web technologies.

### Primary Use Case
- View and search CSV files containing network device information (IP addresses, MAC addresses, switch configurations, etc.)
- Monitor file changes and automatically reindex data
- Provide historical file search capabilities
- Download and preview CSV data through a web interface

## System Architecture

### High-Level Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend │───▶│  FastAPI Backend │───▶│   OpenSearch    │
│  (Port 3000)    │    │   (Port 8000)   │    │   (Port 9200)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        │
                       ┌─────────────────┐               │
                       │  Celery Worker  │──────────────┘
                       │  + Redis Queue  │
                       │   (Port 6379)   │
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  File Watcher   │
                       │   (/app/data)   │
                       └─────────────────┘
```

### Technology Stack

#### Frontend
- **React 18** - UI framework
- **Material-UI (MUI) 6** - Component library and theming
- **Axios** - HTTP client for API communication
- **React Testing Library** - Testing framework
- **React Toast** - Notification system

#### Backend
- **FastAPI** - Modern Python web framework
- **Pydantic** - Data validation and settings management
- **Uvicorn** - ASGI server
- **Celery** - Distributed task queue
- **Redis** - Message broker and caching
- **OpenSearch** - Search and analytics engine
- **Watchdog** - File system monitoring

#### Infrastructure
- **Docker & Docker Compose** - Containerization
- **Nginx** - Reverse proxy (production)
- **Multi-architecture support** - AMD64 and ARM64

## Core Components

### Backend Structure (`/backend/`)

#### Main Application (`main.py`)
- FastAPI application setup with CORS middleware
- API router inclusion for files and search endpoints
- File watcher startup/shutdown management
- Health check endpoints

#### API Endpoints

**Files API (`api/files.py`)**
- `GET /api/files/` - List all CSV files with metadata
- `GET /api/files/netspeed_info` - Get current file information
- `GET /api/files/preview` - Preview CSV data with pagination
- `GET /api/files/download/{filename}` - Download specific files
- `POST /api/files/reindex` - Trigger manual reindexing

**Search API (`api/search.py`)**
- `GET /api/search/` - Search across CSV files using OpenSearch
- `GET /api/search/index/all` - Trigger background indexing
- `GET /api/search/index/status/{task_id}` - Check indexing status

#### Task Management (`tasks/tasks.py`)
- **Celery Tasks**:
  - `index_csv` - Index single CSV file
  - `index_all_csv_files` - Batch index all files in directory
  - `search_opensearch` - Execute search queries

#### Utilities

**File Watching (`utils/file_watcher.py`)**
- Monitors `/app/data` directory for CSV changes
- Automatically triggers reindexing when `netspeed.csv` is modified
- Handles file creation, modification, and cleanup

**OpenSearch Integration (`utils/opensearch.py`)**
- Manages OpenSearch client and index configuration
- Defines field mappings for CSV data structure
- Handles query building for various search types
- Implements result deduplication and filtering

**CSV Processing (`utils/csv_utils.py`)**
- Parses CSV files with delimiter detection (comma/semicolon)
- Handles multiple CSV formats (11-column old, 14-column new)
- Adds metadata (file name, creation date, row numbers)
- Filters and orders columns for display

#### Data Models (`models/file.py`)
- `FileModel` - Represents CSV file metadata
- Automatic format detection (old vs new CSV structure)
- File creation date extraction using Linux `stat` command

### Frontend Structure (`/frontend/src/`)

#### Main Application (`App.js`)
- Material-UI theme provider integration
- Component layout and routing
- Dark mode toggle in header

#### Core Components (`components/`)

**CSVSearch.js**
- Primary search interface with auto-complete
- Real-time search with typing delay (1 second)
- Pagination controls and result display
- Interactive elements (clickable MAC addresses, file downloads)
- Historical file inclusion toggle

**FileTable.js**
- Lists all available CSV files
- Shows file metadata (size, creation date, line count)
- File status indicators and download links

**FileInfoBox.js**
- Displays current file information
- Shows creation date and total line count
- Real-time updates from backend API

**DarkModeToggle.js**
- Theme switching component
- Persists preference to localStorage
- Respects system dark mode preference

#### Custom Hooks (`hooks/`)

**useSearchCSV.js**
- Manages search state and API calls
- Implements client-side pagination
- Handles search result caching and loading states

**useFilePreview.js**
- Fetches CSV preview data
- Configurable preview limits (10, 25, 50, 100 entries)
- Error handling and loading states

**useFiles.js**
- Manages file listing and metadata
- Handles file operations and status updates

#### Theming (`theme/`)
- Light and dark theme definitions
- Material-UI customization
- Theme context and persistence

### Docker Configuration

#### Production Setup (`docker-compose.yml`)
- Multi-service orchestration
- Health checks for service dependencies
- Volume mounts for data persistence
- Environment variable configuration

#### Development Setup (`docker-compose.dev.yml`)
- Hot reload for both frontend and backend
- Volume mounts for source code
- Development-specific configurations

#### Multi-Architecture Support
- AMD64 images: `docker-compose.yml`
- ARM64 images: `docker-compose.arm.yml`
- Automated image building and publishing

## Data Flow and Processing

### CSV File Processing Pipeline

1. **File Detection**
   - File watcher monitors `/app/data` directory
   - Detects creation/modification of `netspeed.csv`
   - Triggers cleanup of existing index

2. **CSV Parsing**
   - Automatic delimiter detection (comma vs semicolon)
   - Format detection (11-column old vs 14-column new)
   - Header generation and validation
   - Row processing with metadata addition

3. **Data Indexing**
   - Celery task queues CSV for OpenSearch indexing
   - Bulk document insertion with optimized settings
   - Field mapping for efficient search operations
   - Index naming convention: `netspeed_{filename}`

4. **Search Processing**
   - Query building with field-specific optimizations
   - Multi-field search with relevance scoring
   - Result deduplication and filtering
   - Pagination and result formatting

### Search Functionality

#### Query Types Supported
- **General text search** - Searches across all fields
- **Field-specific search** - Targets specific columns
- **IP address range queries** - Handles partial IP matching
- **MAC address lookup** - Exact and partial matching
- **Historical file inclusion** - Search across time periods

#### Search Features
- **Auto-complete with debouncing** - 1-second delay after typing
- **Real-time results** - Updates as user types (3+ characters)
- **Pagination** - Configurable page sizes (10, 25, 50, 100, 250)
- **Interactive results** - Clickable MAC addresses and file downloads
- **Result highlighting** - Visual indicators for data freshness

## Development Workflow

### Environment Setup

#### Required Environment Variables (`.env`)
```bash
# Port Configuration
FRONTEND_PORT=3000
BACKEND_PORT=8000
REDIS_PORT=6379
OPENSEARCH_PORT=9200
OPENSEARCH_TRANSPORT_PORT=9300
OPENSEARCH_DASHBOARDS_PORT=5601

# Data Directory
CSV_FILES_DIR=./data

# Security
OPENSEARCH_INITIAL_ADMIN_PASSWORD=your-secure-password
```

#### Development Commands

**Quick Start**
```bash
# Start full application stack
./app.sh start dev

# Production deployment
./app.sh start amd64  # or 'arm' for ARM64

# Stop application
./app.sh stop
```

**Component Development**
```bash
# Backend development
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend development
cd frontend
npm install
npm start

# Celery worker (separate terminal)
cd backend
celery -A tasks.tasks worker --loglevel=info
```

### Testing

#### Backend Tests
```bash
cd backend
pytest tests/ -v
```

**Test Coverage**
- API endpoint testing (`tests/backend/api/`)
- Utility function testing (`tests/backend/utils/`)
- Integration testing with test fixtures
- OpenSearch interaction testing

#### Frontend Tests
```bash
cd frontend
npm test
```

**Test Coverage**
- Component rendering tests
- Hook functionality tests
- User interaction simulation
- API integration testing with mocks

### Code Organization Patterns

#### Backend Patterns
- **Dependency Injection** - Settings and configuration management
- **Async/Await** - Non-blocking I/O operations
- **Background Tasks** - Celery for heavy operations
- **Error Handling** - Structured exception management
- **Logging** - Comprehensive logging throughout application

#### Frontend Patterns
- **Custom Hooks** - Reusable stateful logic
- **Component Composition** - Modular UI components
- **Context Providers** - Global state management (theme)
- **Error Boundaries** - Graceful error handling
- **Loading States** - User feedback during operations

## Key Configuration Files

### Backend Configuration
- `config.py` - Application settings and environment variable management
- `celeryconfig.py` - Celery worker and queue configuration
- `requirements.txt` - Python dependencies
- `pytest.ini` - Test configuration

### Frontend Configuration
- `package.json` - Node.js dependencies and scripts
- `babel.config.js` - JavaScript transpilation
- `jest.config.js` - Test framework configuration

### Infrastructure Configuration
- `docker-compose.yml` - Production container orchestration
- `docker-compose.dev.yml` - Development environment
- `nginx.conf` - Production web server configuration
- `opensearch.yml` - Search engine configuration

## Important Development Notes

### File Naming Conventions
- **Current file**: `netspeed.csv` (always indexed first)
- **Historical files**: `netspeed.csv.0`, `netspeed.csv.1`, etc.
- **Backup files**: `netspeed.csv_bak`

### CSV Format Support
- **Old format** (11 columns): Legacy network data structure
- **New format** (14 columns): Enhanced data with additional fields
- **Automatic detection** based on column count and content analysis

### Search Index Management
- **Index naming**: `netspeed_{sanitized_filename}`
- **Current file index**: `netspeed_netspeed_csv`
- **Historical search**: Searches across all `netspeed_*` indices
- **Auto-cleanup**: Old indices removed when files are updated

### Performance Considerations
- **Bulk indexing**: 1000-document chunks for optimal performance
- **Search limits**: 20,000 result maximum per query
- **Caching**: Redis for task results and temporary data
- **Debouncing**: 1-second delay for search queries

### Security Considerations
- **CORS Configuration**: Controlled origin access
- **OpenSearch Security**: Disabled for internal use
- **File Access**: Restricted to designated data directory
- **Input Validation**: Pydantic models for request validation

### Monitoring and Logging
- **Application logs**: Structured logging throughout codebase
- **Celery monitoring**: Task status and progress tracking
- **Health checks**: Service availability monitoring
- **Error tracking**: Comprehensive exception handling

## Troubleshooting Guide

### Common Issues

**File Processing Issues**
- Check file permissions on `/app/data` directory
- Verify CSV format compatibility
- Monitor Celery worker logs for processing errors

**Search Not Working**
- Verify OpenSearch service health
- Check index creation and population
- Review search query logs for debugging

**Development Environment**
- Ensure all required ports are available
- Check Docker service status
- Verify environment variable configuration

### Useful Debugging Commands
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

This documentation provides a comprehensive foundation for future Claude instances to understand and work effectively with the CSV Viewer codebase. The architecture is well-structured with clear separation of concerns, comprehensive testing, and modern development practices.