#!/bin/bash
set -e

# This script provides a unified interface for managing the CSV Viewer application
# Usage: ./app.sh [start|stop] [amd64|arm|dev]
#   - First argument: action (start or stop)
#   - Second argument: architecture (amd64, arm, or dev)
#   - If no architecture is specified, amd64 is used by default

# Display usage banner for default help
if [ -z "$1" ]; then
  echo "CSV Viewer Application Manager"
  echo ""
  echo "No command specified. Use './app.sh help' for usage information."
  echo "------------------------------------------------------------------------"
  echo ""
fi

# Default values
ACTION=${1:-help}
ARCH=${2:-amd64}

# Help function
show_help() {
  echo "CSV Viewer Application Manager"
  echo ""
  echo "Usage: ./app.sh [start|stop|status] [amd64|arm|dev]"
  echo ""
  echo "Commands:"
  echo "  start     Start the application"
  echo "  stop      Stop the application"
  echo "  status    Show the application status"
  echo "  help      Show this help message"
  echo ""
  echo "Architectures:"
  echo "  amd64     AMD64 architecture (default)"
  echo "  arm       ARM architecture"
  echo "  dev       Development environment"
  echo ""
  echo "Examples:"
  echo "  ./app.sh start          # Start application with AMD64 images (default)"
  echo "  ./app.sh start arm      # Start application with ARM images"
  echo "  ./app.sh stop           # Stop application with AMD64 images (default)"
  echo "  ./app.sh stop arm       # Stop application with ARM images"
  echo "  ./app.sh status         # Show status of all application components"
}

# Check if docker-compose is installed
check_docker_compose() {
  if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed. Please install Docker and Docker Compose."
    exit 1
  fi
}

# Check if .env file exists
check_env_file() {
  if [ ! -f .env ]; then
    echo "❌ .env file not found. Please create one based on .env.example."
    exit 1
  fi
}

# Make sure data directory exists
ensure_data_dir() {
  mkdir -p ./data
}

# Start application with AMD64 images
start_amd64() {
  echo "🚀 Starting CSV Viewer application (AMD64 version)..."
  echo "📋 Using default configuration from docker-compose.yml"

  # Pull images from Docker Hub
  echo "📥 Pulling images from Docker Hub..."
  docker-compose pull

  # Start the application
  echo "🏁 Starting application services..."
  docker-compose up -d

  # Show status
  echo "✅ Application started! You can access it at:"
  echo "   Frontend: http://localhost:3000"
  echo "   Backend API: http://localhost:8000"
  echo ""
  echo "📊 To view logs, run: docker-compose logs -f"
}

# Start application with ARM images
start_arm() {
  echo "🚀 Starting CSV Viewer application (ARM version)..."
  echo "📋 Using configuration from docker-compose.arm.yml"

  # Pull images from Docker Hub
  echo "📥 Pulling images from Docker Hub..."
  docker-compose -f docker-compose.arm.yml pull

  # Start the application
  echo "🏁 Starting application services..."
  docker-compose -f docker-compose.arm.yml up -d

  # Show status
  echo "✅ Application started! You can access it at:"
  echo "   Frontend: http://localhost:3000"
  echo "   Backend API: http://localhost:8000"
  echo ""
  echo "📊 To view logs, run: docker-compose -f docker-compose.arm.yml logs -f"
}

# Start application in development mode
start_dev() {
  echo "🚀 Starting CSV Viewer application (Development mode)..."
  echo "📋 Using configuration from docker-compose.dev.yml"

  # Start the application
  echo "🏁 Starting application services..."
  docker-compose -f docker-compose.dev.yml up -d

  # Show status
  echo "✅ Application started in development mode! You can access it at:"
  echo "   Frontend: http://localhost:3001"
  echo "   Backend API: http://localhost:8000"
  echo ""
  echo "📊 To view logs, run: docker-compose -f docker-compose.dev.yml logs -f"
}

# Stop application with AMD64 images
stop_amd64() {
  echo "🛑 Stopping CSV Viewer application (AMD64 version)..."
  docker-compose down
  echo "✅ Application stopped successfully!"
}

# Stop application with ARM images
stop_arm() {
  echo "🛑 Stopping CSV Viewer application (ARM version)..."
  docker-compose -f docker-compose.arm.yml down
  echo "✅ Application stopped successfully!"
}

# Stop application in development mode
stop_dev() {
  echo "🛑 Stopping CSV Viewer application (Development mode)..."
  docker-compose -f docker-compose.dev.yml down
  echo "✅ Application stopped successfully!"
}

# Show application status
show_status() {
  echo "📊 CSV Viewer Application Status"
  echo ""
  
  echo "Docker Containers:"
  docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
  
  echo ""
  echo "Services Health:"
  
  # Check frontend
  if curl -s -I http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend is running"
  else
    echo "❌ Frontend is not running"
  fi
  
  # Check backend
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is running"
  else
    echo "❌ Backend is not running"
  fi
  
  echo ""
  echo "For more details, run: docker-compose ps"
}

# Main execution
case "$ACTION" in
  start)
    check_docker_compose
    check_env_file
    ensure_data_dir
    
    case "$ARCH" in
      amd64)
        start_amd64
        ;;
      arm)
        start_arm
        ;;
      dev)
        start_dev
        ;;
      *)
        echo "❌ Unknown architecture: $ARCH"
        echo "Valid options are: amd64, arm, dev"
        exit 1
        ;;
    esac
    ;;
    
  stop)
    check_docker_compose
    
    case "$ARCH" in
      amd64)
        stop_amd64
        ;;
      arm)
        stop_arm
        ;;
      dev)
        stop_dev
        ;;
      *)
        echo "❌ Unknown architecture: $ARCH"
        echo "Valid options are: amd64, arm, dev"
        exit 1
        ;;
    esac
    ;;
    
  status)
    show_status
    ;;
    
  help|*)
    show_help
    ;;
esac
