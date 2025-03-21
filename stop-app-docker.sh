#!/bin/bash

# Function to check if docker is running
check_docker() {
  echo "Checking if Docker is running..."
  if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. No services to stop."
    return 1
  else
    echo "✅ Docker is running"
    return 0
  fi
}

# Function to check if any containers are running
check_if_running() {
  echo "Checking if any services are running..."
  
  # Check if any containers defined in docker-compose.yml are running
  if docker-compose ps -q | grep -q .; then
    echo "✅ Found running containers"
    return 0
  else
    echo "❌ No containers from docker-compose.yml are running"
    return 1
  fi
}

# Main function
main() {
  echo "Stopping CSV Viewer Application..."
  
  # Check if Docker is running
  if ! check_docker; then
    exit 1
  fi
  
  # Check if containers are running
  if ! check_if_running; then
    echo "No containers to stop."
    exit 0
  fi
  
  # Stop all services with docker-compose
  echo "Stopping all services with docker-compose..."
  docker-compose down
  
  # Check if services were successfully stopped
  if [ $? -eq 0 ]; then
    echo "✅ All services have been stopped successfully"
  else
    echo "⚠️  Error stopping services. Check docker-compose logs for details."
    exit 1
  fi
  
  echo "✅ CSV Viewer Application has been stopped"
}

# Run the main function
main
