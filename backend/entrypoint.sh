#!/bin/bash
set -e

# Ensure local packages are importable (e.g., 'models', 'utils')
export PYTHONPATH="/app:${PYTHONPATH}"

# Create data directory if it doesn't exist
echo "Ensuring data directory exists..."
mkdir -p ./data

# Ensure local index state directory exists (container-local, not in mounted CSV path)
mkdir -p /app/var/index_state || true

# Start Celery worker in the background
echo "Starting Celery worker..."
# Run without forcing nobody user so state file can be written if volume permissions require it
celery -A tasks.tasks worker --loglevel=info -Q search,csv_processing,celery &
CELERY_PID=$!

# Wait a moment to ensure Celery starts properly
sleep 3
echo "Celery worker started"

# Scheduler removed; file watcher handles reindexing.

# Start FastAPI application in the background
echo "Starting FastAPI application..."
# Use BACKEND_PORT from environment or default to 8000
PORT="${BACKEND_PORT:-8000}"
uvicorn main:app --host 0.0.0.0 --port $PORT &
UVICORN_PID=$!

# Wait for the FastAPI application to start
echo "Waiting for FastAPI application to be ready..."
for i in {1..30}; do
  if curl -s "http://localhost:$PORT/health" > /dev/null; then
    echo "FastAPI application is ready"
    break
  fi
  sleep 1
  if [ $i -eq 30 ]; then
    echo "Timed out waiting for FastAPI application to start"
  fi
done

# Wait for OpenSearch to be healthy before indexing (green or yellow)
PRIMARY_OS_URL="${OPENSEARCH_URL:-http://opensearch:9200}"
FALLBACK_OS_URL="http://opensearch:9200"
HEALTHY=0
for URL in "$PRIMARY_OS_URL" "$FALLBACK_OS_URL"; do
  echo "Waiting for OpenSearch at $URL to be healthy..."
  for i in {1..120}; do
    if curl -sf "$URL/_cluster/health" | grep -q '"status":"green"\|"status":"yellow"'; then
      echo "OpenSearch is healthy at $URL"
      HEALTHY=1
      break
    fi
    sleep 1
  done
  [ $HEALTHY -eq 1 ] && break
done
if [ $HEALTHY -ne 1 ]; then
  echo "Timed out waiting for OpenSearch to be healthy; proceeding anyway"
fi

# Index CSV files
echo "Indexing CSV files..."
sleep 5  # Additional wait to ensure all services are fully initialized
curl -s -X GET "http://localhost:$PORT/api/search/index/all" > /dev/null
echo "Indexing task started"

# Wait for both processes
echo "All services started. Waiting for processes to finish..."
wait $UVICORN_PID
