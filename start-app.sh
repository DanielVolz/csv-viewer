#!/bin/bash

# Check if Elasticsearch is running
check_elasticsearch() {
  echo "Checking Elasticsearch..."
  if curl -s "http://localhost:9200" > /dev/null; then
    echo "✅ Elasticsearch is running"
    return 0
  else
    echo "❌ Elasticsearch is not running"
    return 1
  fi
}

# Check if Redis is running
check_redis() {
  echo "Checking Redis..."
  if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is running"
    return 0
  else
    echo "❌ Redis is not running"
    return 1
  fi
}

# Start Elasticsearch
start_elasticsearch() {
  echo "Starting Elasticsearch..."
  brew services start elastic/tap/elasticsearch-full
  
  # Wait for Elasticsearch to start
  echo "Waiting for Elasticsearch to start (this may take a minute)..."
  for i in {1..30}; do
    if check_elasticsearch; then
      return 0
    fi
    sleep 2
  done
  
  echo "⚠️  Timed out waiting for Elasticsearch to start"
  return 1
}

# Start Redis
start_redis() {
  echo "Starting Redis..."
  brew services start redis
  
  # Wait for Redis to start
  echo "Waiting for Redis to start..."
  for i in {1..10}; do
    if check_redis; then
      return 0
    fi
    sleep 1
  done
  
  echo "⚠️  Timed out waiting for Redis to start"
  return 1
}

# Index CSV files
index_csv_files() {
  echo "Indexing CSV files..."
  
  # First check if the backend is running by making a health check
  if ! curl -s "http://localhost:8000/health" > /dev/null; then
    echo "❌ Backend is not running, cannot index CSV files"
    return 1
  fi
  
  # Request indexing of all CSV files
  RESPONSE=$(curl -s "http://localhost:8000/api/search/index/all")
  TASK_ID=$(echo $RESPONSE | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4)
  
  if [ -z "$TASK_ID" ]; then
    echo "❌ Failed to start indexing task"
    return 1
  fi
  
  echo "✅ Indexing task started with ID: $TASK_ID"
  echo "Check status at: http://localhost:8000/api/search/index/status/$TASK_ID"
  return 0
}

# Main function
main() {
  echo "Starting CSV Viewer Application..."
  
  # Check and start Elasticsearch if needed
  if ! check_elasticsearch; then
    if ! start_elasticsearch; then
      echo "Failed to start Elasticsearch. Please start it manually with 'brew services start elasticsearch'."
      exit 1
    fi
  fi
  
  # Check and start Redis if needed
  if ! check_redis; then
    if ! start_redis; then
      echo "Failed to start Redis. Please start it manually with 'brew services start redis'."
      exit 1
    fi
  fi
  
  # Start Celery worker (in background)
  echo "Starting Celery worker..."
  cd backend
  celery -A tasks.tasks worker --loglevel=info > celery.log 2>&1 &
  CELERY_PID=$!
  cd ..
  echo "✅ Celery worker started (PID: $CELERY_PID)"
  
  # Start backend server (in background)
  echo "Starting backend server..."
  cd backend
  uvicorn main:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
  BACKEND_PID=$!
  cd ..
  echo "✅ Backend server started (PID: $BACKEND_PID)"
  
  # Wait for backend to be ready
  echo "Waiting for backend to be ready..."
  for i in {1..10}; do
    if curl -s "http://localhost:8000/health" > /dev/null; then
      echo "✅ Backend is ready"
      break
    fi
    sleep 1
    if [ $i -eq 10 ]; then
      echo "⚠️  Timed out waiting for backend to start"
    fi
  done
  
  # Start frontend (in foreground)
  echo "Starting frontend..."
  cd frontend
  npm start
  
  # Clean up on exit
  trap cleanup EXIT
}

# Cleanup function
cleanup() {
  echo "Cleaning up..."
  if [ ! -z "$CELERY_PID" ]; then
    echo "Stopping Celery worker..."
    kill $CELERY_PID
  fi
  if [ ! -z "$BACKEND_PID" ]; then
    echo "Stopping backend server..."
    kill $BACKEND_PID
  fi
  echo "Done. You may want to stop Elasticsearch and Redis manually with:"
  echo "brew services stop elasticsearch"
  echo "brew services stop redis"
}

# Run the main function
main
