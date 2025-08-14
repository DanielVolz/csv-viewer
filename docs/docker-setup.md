# Docker Setup for CSV Viewer Application

This document describes how to run the CSV Viewer application using Docker and Docker Compose.

## Architecture

The dockerized application consists of four services:

1. **Frontend**: React application served through Nginx
2. **Backend**: FastAPI application running with Uvicorn
3. **Redis**: Message broker for Celery tasks
4. **OpenSearch**: Search engine for indexing and querying CSV data

The services are orchestrated using Docker Compose, which manages networking, volumes, and environment variables.

## Prerequisites

- Docker (v20.10+)
- Docker Compose (v2.0+)

## Configuration

Before starting the application, create an `.env` file in the root directory with the following content:

```
# OpenSearch credentials
OPENSEARCH_INITIAL_ADMIN_PASSWORD=YourStrongPasswordHere
```

Make sure to replace `YourStrongPasswordHere` with a secure password.

## Quick Start

To start the application, run the following command in the project root directory:

```bash
docker-compose up
```

To run the application in the background, use:

```bash
docker-compose up -d
```

To stop the application, you can use either of the following methods:

```bash
# Using Docker Compose directly
docker-compose down

# Using the stop script
./stop-app-docker.sh
```

The stop script provides additional checks to ensure all services are properly shut down.

## Service Details

### Frontend

- Built using React with Material UI
- Served using Nginx on port 3000
- Automatically proxies API requests to the backend service

### Backend

- FastAPI application with Uvicorn server
- Connects to Redis and OpenSearch
- Uses Celery for asynchronous task processing
- CSV files are mounted from the host machine's example-data directory

### Redis

- Used as a message broker for Celery
- Data is persisted using a Docker volume

### OpenSearch

- Used for indexing and searching CSV data
- Configured as a single-node cluster named "csv-viewer-cluster"
- Data and logs are persisted using Docker volumes
- Security plugin is disabled for development simplicity
- Memory settings optimized for performance with bootstrap memory lock

## Configuration

Environment variables for the backend service are set in the `docker-compose.yml` file. The main configuration includes:

- `REDIS_URL`: URL for Redis connection
- `OPENSEARCH_URL`: URL for OpenSearch connection
- `CSV_FILES_DIR`: Directory containing CSV files

## Data Persistence

The application uses Docker volumes for data persistence:

- `redis-data`: Stores Redis data
- `opensearch-data`: Stores OpenSearch indices

These volumes ensure that data is preserved even when containers are stopped or removed.

## Development Workflow

For development purposes, you can rebuild and restart individual services:

```bash
# Rebuild and restart the frontend
docker-compose up -d --build frontend

# Rebuild and restart the backend
docker-compose up -d --build backend
```

## Troubleshooting

### OpenSearch Issues

If OpenSearch fails to start, it may be due to memory settings. Adjust the `OPENSEARCH_JAVA_OPTS` in the `docker-compose.yml` file.

### Redis Connection Issues

If the backend can't connect to Redis, check that the `REDIS_URL` environment variable is correctly set in the `docker-compose.yml` file.

### Frontend Not Loading

If the frontend is not loading, check that the Nginx configuration is correctly set up in `frontend/nginx.conf`.

## Build verification (dev)

- Date: 2025-08-11
- Frontend (dev target): built successfully with buildx and loaded locally.
- Backend (dev target): built successfully with buildx and loaded locally.
- Note: Builds were executed in a restricted network environment using a proxy. Specific proxy details are intentionally omitted from this document.

## Build with buildx behind a proxy (dev targets)

Use placeholders for your proxy. Do not commit real credentials.

- Replace PROXY_URL with your proxy URL, e.g. `http://user:password@proxy.example.com:8080`
- Adjust NO_PROXY hosts to your environment as needed

Backend (dev target):

```zsh
docker buildx build \
	--build-arg HTTP_PROXY=PROXY_URL \
	--build-arg HTTPS_PROXY=PROXY_URL \
	--build-arg NO_PROXY=localhost,127.0.0.1,backend,opensearch,redis \
	--target dev -t csv-viewer-backend-dev --load ./backend
```

Frontend (dev target):

```zsh
docker buildx build \
	--build-arg HTTP_PROXY=PROXY_URL \
	--build-arg HTTPS_PROXY=PROXY_URL \
	--build-arg NO_PROXY=localhost,127.0.0.1,backend,opensearch,redis \
	--target dev -t csv-viewer-frontend-dev --load ./frontend
```

Note:
- If base image pulls fail, configure a docker-container builder with proxy env and rerun the builds. Keep proxy details out of version control.
