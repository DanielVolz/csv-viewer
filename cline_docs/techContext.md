# CSV Viewer - Technical Context

## Technologies Used

### Backend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.x | Primary backend language |
| **FastAPI** | Latest | Web framework for creating API endpoints |
| **Celery** | Latest | Distributed task queue for async processing |
| **Redis** | Latest | Message broker for Celery tasks |
| **OpenSearch** | Latest | Search and analytics engine for CSV data |
| **Pandas** | Latest | Data manipulation and CSV processing |
| **Uvicorn** | Latest | ASGI server for running FastAPI applications |

### Frontend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| **JavaScript/ES6** | ES6+ | Primary frontend language |
| **React** | Latest | UI library for component-based development |
| **Material UI** | Latest | React component library for consistent styling |
| **Axios** | Latest | HTTP client for API communication |
| **React Context API** | Built-in | State management solution |
| **CSS-in-JS** | Material UI styled | Styling approach |
| **Jest** | Latest | Testing framework for frontend |
| **React Testing Library** | Latest | Testing utilities for React components |

### Infrastructure

| Technology | Version | Purpose |
|------------|---------|---------|
| **Docker** | v20.10+ | Containerization for consistent environments |
| **Docker Compose** | v2.0+ | Service orchestration |
| **Nginx** | Latest | Web server for serving frontend assets |

## Development Setup

### Local Environment Setup

1. **Prerequisites**:
   - Node.js (LTS version)
   - Python 3.x
   - Redis
   - OpenSearch (or Elasticsearch)

2. **Backend Setup**:
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Frontend Setup**:
   ```bash
   cd frontend
   npm install
   ```

4. **Running the Application**:
   ```bash
   # Use the provided script to start both frontend and backend
   ./start-app.sh
   ```

### Docker Setup

1. **Prerequisites**:
   - Docker (v20.10+)
   - Docker Compose (v2.0+)

2. **Configuration**:
   - Create `.env` file in the root directory with required environment variables
   - Configure OpenSearch credentials using `OPENSEARCH_INITIAL_ADMIN_PASSWORD`

3. **Docker Services**:
   - **Frontend**: React application served through Nginx on port 3000
   - **Backend**: FastAPI application running with Uvicorn, connecting to Redis and OpenSearch
   - **Redis**: Message broker for Celery with data persisted using Docker volume
   - **OpenSearch**: Search engine configured as a single-node cluster named "csv-viewer-cluster"

4. **Data Persistence**:
   - `redis-data`: Docker volume for Redis data
   - `opensearch-data`: Docker volume for OpenSearch indices
   - CSV files mounted from host machine's data directory

5. **Running with Docker**:
   ```bash
   # Start all services
   docker-compose up

   # Run in background
   docker-compose up -d

   # Stop all services
   docker-compose down
   # OR
   ./stop-app-docker.sh
   ```

6. **Development Workflow**:
   ```bash
   # Rebuild and restart specific services
   docker-compose up -d --build frontend
   docker-compose up -d --build backend
   ```

7. **Troubleshooting**:
   - For OpenSearch issues, adjust the `OPENSEARCH_JAVA_OPTS` in docker-compose.yml
   - For Redis connection issues, verify `REDIS_URL` environment variable
   - For frontend loading issues, check Nginx configuration in frontend/nginx.conf

### Development Workflow

1. Frontend development server runs on http://localhost:3000
2. Backend API is accessible at http://localhost:8000
3. API documentation available at http://localhost:8000/docs
4. The application uses hot-reloading for both frontend and backend

## Technical Constraints

### Data Handling

1. **CSV File Requirements**:
   - CSV files must be placed in the designated `/data` directory
   - Files must include specific network-related columns (IP Address, MAC Address, etc.)
   - Historical files should follow the naming convention `netspeed.csv.N` where N is a numeric suffix

2. **Search Performance**:
   - OpenSearch is required for efficient searching of large CSV files
   - The system is optimized for specific column ordering and data types

### System Requirements

1. **Memory Constraints**:
   - OpenSearch requires sufficient memory allocation (configurable in docker-compose.yml)
   - Large CSV files may require additional memory for processing

2. **Storage Requirements**:
   - Sufficient disk space needed for CSV files and OpenSearch indices
   - Docker volumes used for persistent data storage

### Development Constraints

1. **Code Style**:
   - Frontend follows standard React component patterns
   - Backend uses FastAPI dependency injection pattern
   - PEP 8 standards for Python code

2. **Testing Requirements**:
   - All components and hooks should have associated tests
   - Backend endpoints require test coverage
   - Tests should be run before merging new features

3. **Project-Specific Rules**:
   - Always use `./start-app.sh` to start the application for proper environment configuration
   - Never fix flake or general linter errors
   - Keep documentation up to date in the docs folder
