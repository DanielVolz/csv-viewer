#!/bin/bash
set -e

# Ensure local packages are importable (e.g., 'models', 'utils')
export PYTHONPATH="/app:${PYTHONPATH}"

# Create directory for CSV files if it doesn't exist
echo "Ensuring data directory exists..."
mkdir -p ./data

# Start Celery worker in the background
echo "Starting Celery worker (dev)..."
# Run as default container user to retain write permissions on mounted volume
celery -A tasks.tasks worker --loglevel=info -Q search,csv_processing,celery &
CELERY_PID=$!

# Wait a moment to ensure Celery starts properly
sleep 3
echo "Celery worker started"

# Start FastAPI application in the background
echo "Starting FastAPI application..."
# Use BACKEND_PORT from environment or default to 8000
PORT="${BACKEND_PORT:-8000}"
uvicorn main:app --host 0.0.0.0 --port $PORT --reload &
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

# Skip blocking OpenSearch health checks in dev; proceed immediately
echo "Skipping OpenSearch health wait in dev"

# Index CSV files (unless skipped)
if [ "${SKIP_AUTO_REINDEX:-false}" = "true" ]; then
  echo "Skipping automatic reindex (SKIP_AUTO_REINDEX=true)"
else
  echo "Indexing CSV files..."
  sleep 5  # Small grace period
  curl -s -X GET "http://localhost:$PORT/api/search/index/all" > /dev/null || true
  echo "Indexing task started"
fi

# Wait for both processes
echo "All services started. Waiting for processes to finish..."
wait $UVICORN_PID
