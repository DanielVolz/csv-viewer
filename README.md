# CSV Data Viewer

A dockerized full-stack web application for viewing, searching, and managing network data stored in CSV files.

## What is CSV Data Viewer?

CSV Data Viewer is a modern web application designed for viewing, searching, and managing network data stored in CSV files. It provides real-time search capabilities, file monitoring, and automatic indexing using modern web technologies.

The application allows users to:

- Browse available CSV files with metadata (size, creation date, line count)
- View and preview CSV file contents with pagination
- Search for network device information (IP addresses, MAC addresses, switch configurations, etc.)
- Include historical files in searches across time periods
- Download CSV files and access real-time file status
- Monitor file changes with automatic reindexing

The application consists of a React 18 frontend with Material-UI, a FastAPI backend with Pydantic validation, OpenSearch for indexing and search, Redis for task queuing, and Celery for background processing.

## Installation

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- Git (for cloning the repository)

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/DanielVolz/csv-viewer.git
   cd csv-viewer
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

3. **Start the application:**
   ```bash
   # Development mode with hot reload
   ./app.sh start dev

   # Production mode (AMD64)
   ./app.sh start amd64

   # Production mode (ARM64)
   ./app.sh start arm
   ```

4. **Access the application:**
   - Frontend: [http://localhost:3000](http://localhost:3000)
   - Backend API: [http://localhost:8000](http://localhost:8000)
   - OpenSearch Dashboards: [http://localhost:5601](http://localhost:5601)

### Development Setup

For development with hot reload and volume mounts:

```bash
# Start development environment
./app.sh start dev

# The application will automatically reload when you make changes to:
# - Frontend: /frontend/src and /frontend/public
# - Backend: /backend (entire directory)
```

**Important**: After running `docker-compose up`, wait 30 seconds before executing additional terminal commands to avoid canceling the startup process.

## Available Scripts

### Application Management

```bash
# Start application
./app.sh start [dev|amd64|arm]    # Start with specified environment
./app.sh stop                     # Stop application
./app.sh status                   # Show application status

# Examples:
./app.sh start dev               # Development with hot reload
./app.sh start amd64            # Production (AMD64 architecture)
./app.sh start arm              # Production (ARM64 architecture)
```

### Development Commands

```bash
# Backend development (if running outside Docker)
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend development (if running outside Docker)
cd frontend
npm install
npm start

# Run tests
python -m pytest tests/backend     # Backend tests
cd frontend && npm test            # Frontend tests
```

### Debugging Commands

```bash
# Check service health
curl http://localhost:8000/api/files/

# OpenSearch cluster health
curl -X GET "localhost:9200/_cluster/health"
curl -X GET "localhost:9200/_cat/indices"

# View logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f opensearch

# Celery monitoring
docker exec -it csv-viewer-backend celery -A tasks.tasks inspect active
```

## Architecture

### System Components
- **Frontend**: React 18 + Material-UI (MUI) 6 (Port 3000)
- **Backend**: FastAPI + Pydantic + Uvicorn (Port 8000)
- **Search Engine**: OpenSearch (Port 9200)
- **Task Queue**: Redis + Celery (Port 6379)
- **File Monitoring**: Watchdog monitors `/app/data`

### Data Processing Pipeline
1. File watcher detects CSV changes in `/app/data`
2. Celery tasks handle CSV parsing and OpenSearch indexing
3. Frontend provides real-time search with auto-complete
4. Historical file inclusion for time-based searches

## File Naming Conventions
- `netspeed.csv` - Current/active file (always indexed first)
- `netspeed.csv.0`, `netspeed.csv.1` - Historical files
- `netspeed.csv_bak` - Backup files

## CSV Format Support
- **Old format**: 11 columns (legacy network data)
- **New format**: 14 columns (enhanced data with additional fields)
- **Automatic detection** based on column count and content analysis

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python -m pytest tests/backend` and `npm test`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Analytics Helpers

### City Code Counting

Count unique city codes (prefix before the first dash in switch hostnames) from a `netspeed.csv` file.

Script: `scripts/analytics/count_cities.py`

Usage:

```bash
# Default (uses test-data/netspeed.csv)
python3 scripts/analytics/count_cities.py

# Specify a different file (e.g. production mounted path - new layout current file)
python3 scripts/analytics/count_cities.py --file /usr/scripts/netspeed/data/netspeed/netspeed.csv

# Historical snapshot example (.0 = yesterday in new layout)
python3 scripts/analytics/count_cities.py --file /usr/scripts/netspeed/data/history/netspeed/netspeed.csv.0

# Show top 10 cities by occurrence
python3 scripts/analytics/count_cities.py --file /usr/scripts/netspeed/data/netspeed/netspeed.csv --top 10
```

The script auto-detects the delimiter (`;` or `,`) and attempts several likely column positions or a fallback scan to find the switch hostname, then extracts the city code (substring before the first `-`).
