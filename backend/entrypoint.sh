#!/bin/bash
set -e

# Create data directory if it doesn't exist
echo "Ensuring data directory exists..."
mkdir -p ./data

# Start Celery worker in the background
echo "Starting Celery worker..."
celery -A tasks.tasks worker --loglevel=info -Q search,csv_processing,celery --uid nobody &
CELERY_PID=$!

# Wait a moment to ensure Celery starts properly
sleep 3
echo "Celery worker started"

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

# Index CSV files
echo "Indexing CSV files..."
sleep 5  # Additional wait to ensure all services are fully initialized
curl -s -X GET "http://localhost:$PORT/api/search/index/all" > /dev/null
echo "Indexing task started"

# Wait for both processes
echo "All services started. Waiting for processes to finish..."
wait $UVICORN_PID
