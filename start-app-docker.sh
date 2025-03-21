#!/bin/bash

# Function to check if docker is running
check_docker() {
  echo "Checking if Docker is running..."
  if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    return 1
  else
    echo "✅ Docker is running"
    return 0
  fi
}

# Function to check if containers are healthy
check_containers_health() {
  echo "Checking container health..."
  
  # Check if backend container is running
  if docker-compose ps backend | grep -q "Up"; then
    echo "✅ Backend container is running"
  else
    echo "❌ Backend container is not running"
    return 1
  fi
  
  # Check if frontend container is running
  if docker-compose ps frontend | grep -q "Up"; then
    echo "✅ Frontend container is running"
  else
    echo "❌ Frontend container is not running"
    return 1
  fi
  
  # Check if redis container is running
  if docker-compose ps redis | grep -q "Up"; then
    echo "✅ Redis container is running"
  else
    echo "❌ Redis container is not running"
    return 1
  fi
  
  # Check if opensearch container is running
  if docker-compose ps opensearch | grep -q "Up"; then
    echo "✅ OpenSearch container is running"
  else
    echo "❌ OpenSearch container is not running"
    return 1
  fi
  
  return 0
}

# Index CSV files
index_csv_files() {
  echo "Indexing CSV files..."
  
  # First check if the backend is running by making a health check
  if ! curl -s "http://localhost:8000/health" > /dev/null; then
    echo "❌ Backend is not running or not accessible, cannot index CSV files"
    return 1
  fi
  
  # Wait a moment to ensure all backend services are fully initialized
  echo "Waiting for backend services to initialize completely..."
  sleep 5
  
  # Request indexing of all CSV files
  echo "Sending request to index all CSV files..."
  RESPONSE=$(curl -s -X POST "http://localhost:8000/api/search/index/all")
  echo "Response: $RESPONSE"
  
  TASK_ID=$(echo $RESPONSE | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4)
  
  if [ -z "$TASK_ID" ]; then
    echo "❌ Failed to start indexing task"
    # Try alternative endpoint format
    echo "Trying alternative endpoint format..."
    RESPONSE=$(curl -s "http://localhost:8000/api/search/index/all")
    echo "Response: $RESPONSE"
    TASK_ID=$(echo $RESPONSE | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4)
    
    if [ -z "$TASK_ID" ]; then
      echo "❌ Still failed to start indexing task"
      # List available files to check if they're accessible
      echo "Available files in mounted directory:"
      docker-compose exec backend ls -la /app/example-data
      return 1
    fi
  fi
  
  echo "✅ Indexing task started with ID: $TASK_ID"
  echo "Check status at: http://localhost:8000/api/search/index/status/$TASK_ID"
  
  # Wait and check for task completion
  echo "Waiting for indexing task to complete..."
  for i in {1..30}; do
    STATUS_RESPONSE=$(curl -s "http://localhost:8000/api/search/index/status/$TASK_ID")
    STATUS=$(echo $STATUS_RESPONSE | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    echo "Current status: $STATUS"
    
    if [ "$STATUS" = "SUCCESS" ]; then
      echo "✅ Indexing completed successfully"
      break
    elif [ "$STATUS" = "FAILURE" ]; then
      echo "❌ Indexing failed"
      echo "Error details: $STATUS_RESPONSE"
      return 1
    fi
    
    sleep 2
    if [ $i -eq 30 ]; then
      echo "⚠️ Indexing task took too long, check status manually"
    fi
  done
  
  return 0
}

# Main function
main() {
  echo "Starting CSV Viewer Application with Docker Compose..."
  
  # Check if Docker is running
  if ! check_docker; then
    exit 1
  fi
  
  # Start all services with docker-compose
  echo "Starting services with docker-compose..."
  docker-compose up -d
  
  # Wait for services to be healthy
  echo "Waiting for services to be ready..."
  for i in {1..30}; do
    if check_containers_health; then
      echo "✅ All containers are running"
      break
    fi
    sleep 2
    if [ $i -eq 30 ]; then
      echo "⚠️  Timed out waiting for containers to start"
      echo "Check logs with 'docker-compose logs'"
      exit 1
    fi
  done
  
  # Wait for backend to be ready
  echo "Waiting for backend to be responsive..."
  for i in {1..30}; do
    if curl -s "http://localhost:8000/health" > /dev/null; then
      echo "✅ Backend is ready"
      break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
      echo "⚠️  Timed out waiting for backend to be responsive"
      echo "Check backend logs with 'docker-compose logs backend'"
      exit 1
    fi
  done
  
  # Wait for frontend to be ready
  echo "Waiting for frontend to be responsive..."
  for i in {1..30}; do
    if curl -s -I "http://localhost:3000" > /dev/null 2>&1; then
      echo "✅ Frontend is ready"
      break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
      echo "⚠️  Timed out waiting for frontend to be responsive"
      echo "Check frontend logs with 'docker-compose logs frontend'"
      exit 1
    fi
  done
  
  # Index CSV files
  index_csv_files
  
  echo "✅ CSV Viewer Application is now running!"
  echo "Access the application at: http://localhost:3000"
  echo ""
  echo "To view logs:"
  echo "  docker-compose logs -f"
  echo ""
  echo "To stop the application:"
  echo "  docker-compose down"
}

# Clean up function
cleanup() {
  echo "Use 'docker-compose down' to stop the application"
}

# Run the main function
main

# Register cleanup function
trap cleanup EXIT
