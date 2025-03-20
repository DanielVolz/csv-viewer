#!/bin/bash

# Restart OpenSearch if it's not responding
restart_opensearch() {
  echo "OpenSearch not responding, attempting restart..."
  docker-compose -f /Users/danielvolz/docker/opensearch/docker-compose.yml up -d
  
  # Wait for OpenSearch to start
  echo "Waiting for OpenSearch to start (this may take a minute)..."
  for i in {1..30}; do
    if check_opensearch; then
      return 0
    fi
    sleep 2
  done
  
  echo "⚠️  Timed out waiting for OpenSearch to start"
  return 1
}

# Restart Redis if it's not responding
restart_redis() {
  echo "Redis not responding, attempting restart..."
  brew services restart redis
  
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

# Check if OpenSearch is running
check_opensearch() {
  echo "Checking OpenSearch..."
  
  # First, check if the container is running
  if docker ps | grep -q opensearch; then
    CONTAINER_ID=$(docker ps | grep opensearch | awk '{print $1}')
    echo "OpenSearch container is running (ID: $CONTAINER_ID)"
  fi
  
  # Try multiple connection methods with HTTPS
  echo "Attempting to connect to OpenSearch..."
  
  # Try HTTPS with authentication and skip certificate validation
  if curl -s -k -u admin:Alterichkotzepass23$ "https://localhost:9200" > /dev/null 2>&1; then
    echo "✅ OpenSearch is running on HTTPS with authentication"
    return 0
  
  # Try with different curl binary that might have different SSL support
  elif /opt/homebrew/opt/curl/bin/curl -s -k -u admin:Alterichkotzepass23$ "https://localhost:9200" > /dev/null 2>&1; then
    echo "✅ OpenSearch is running on HTTPS (using Homebrew curl)"
    return 0
  
  # Try HTTP as a fallback
  elif curl -s -m 5 -u admin:Alterichkotzepass23$ "http://localhost:9200" > /dev/null 2>&1; then
    echo "✅ OpenSearch is running on HTTP with authentication"
    return 0
  
  else
    echo "❌ Failed to connect to OpenSearch"
    echo "Troubleshooting steps:"
    echo "1. Try connecting manually with: /opt/homebrew/opt/curl/bin/curl https://localhost:9200 -ku admin:Alterichkotzepass23$"
    echo "2. Check OpenSearch logs: docker logs $CONTAINER_ID"
    echo "3. Verify if OpenSearch is configured to use HTTPS instead of HTTP"
    
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
  
  # Check OpenSearch and restart only if not responding
  if ! check_opensearch; then
    if ! restart_opensearch; then
      echo "Failed to start OpenSearch. Please start it manually with 'docker-compose -f /Users/danielvolz/docker/opensearch/docker-compose.yml up -d'."
      exit 1
    fi
  fi
  
  # Check Redis and restart only if not responding
  if ! check_redis; then
    if ! restart_redis; then
      echo "Failed to start Redis. Please start it manually with 'brew services start redis'."
      exit 1
    fi
  fi
  
  # Start Celery worker (in background)
  echo "Starting Celery worker..."
  cd backend
  celery -A tasks.tasks worker --loglevel=info -Q search,csv_processing,celery > celery.log 2>&1 &
  CELERY_PID=$!
  cd ..
  echo "✅ Celery worker started (PID: $CELERY_PID)"
  
  # Check if backend is already running properly
  if curl -s "http://localhost:8000/health" > /dev/null; then
    echo "✅ Backend is already running and healthy"
  else
    # Only kill the process if health check fails
    echo "Backend not responding, checking for process on port 8000..."
    local PID=$(lsof -ti:8000)
    if [ ! -z "$PID" ]; then
      echo "Killing unresponsive backend process (PID: $PID)..."
      kill -9 $PID
      sleep 2
    fi
    
    # Start backend server (in background)
    echo "Starting backend server..."
    cd backend
    uvicorn main:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
    BACKEND_PID=$!
    cd ..
    echo "✅ Backend server started (PID: $BACKEND_PID)"
    
    # Wait for backend to be ready
    echo "Waiting for backend to be ready..."
    for i in {1..30}; do
      if curl -s "http://localhost:8000/health" > /dev/null; then
        echo "✅ Backend is ready"
        break
      fi
      sleep 1
      if [ $i -eq 30 ]; then
        echo "⚠️  Timed out waiting for backend to start"
      fi
    done
  fi
  
  # Start AgentDeskAI browser tools server (in background)
  echo "Starting AgentDeskAI browser tools server..."
  npx @agentdeskai/browser-tools-server@1.2.0 > browser-tools-server.log 2>&1 &
  BROWSER_TOOLS_PID=$!
  echo "✅ AgentDeskAI browser tools server started (PID: $BROWSER_TOOLS_PID)"

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
  if [ ! -z "$BROWSER_TOOLS_PID" ]; then
    echo "Stopping AgentDeskAI browser tools server..."
    kill $BROWSER_TOOLS_PID
  fi
  echo "Done. You may want to stop Elasticsearch and Redis manually with:"
  echo "docker-compose -f /Users/danielvolz/docker/opensearch/docker-compose.yml down"
  echo "brew services stop redis"
}

# Run the main function
main
