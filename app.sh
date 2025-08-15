#!/bin/bash
set -e

# This script provides a unified interface for managing the CSV Viewer application
# New simple mode:
#   ./app.sh up   dev|prod
#   ./app.sh down dev|prod
#   ./app.sh restart dev|prod
#   ./app.sh status dev|prod
#
# Backward-compatible mode (legacy):
#   ./app.sh start|stop [amd64|arm|dev]

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
TARGET=${2:-}
DEV_PROJECT="csv-viewer-dev"
PROD_PROJECT="csv-viewer-prod"

# Help function
show_help() {
  echo "CSV Viewer Application Manager"
  echo ""
  echo "Usage:"
  echo "  Simple (recommended):"
  echo "    ./app.sh up|down|restart|status dev|prod"
  echo ""
  echo "  Legacy (still works):"
  echo "    ./app.sh start|stop|status [amd64|arm|dev]"
  echo ""
  echo "Commands:"
  echo "  up        Start services"
  echo "  down      Stop services"
  echo "  restart   Restart services (down+up)"
  echo "  status    Show the application status"
  echo "  start     (legacy) Start services"
  echo "  stop      (legacy) Stop services"
  echo "  help      Show this help message"
  echo ""
  echo "Targets:"
  echo "  dev       Development stack (docker-compose.dev.yml)"
  echo "  prod      Production-like stack (docker-compose.prod.yml)"
  echo "  amd64     (legacy) default docker-compose.yml)"
  echo "  arm       (legacy) docker-compose.arm.yml)"
  echo ""
  echo "Examples:"
  echo "  ./app.sh up dev         # Start development stack"
  echo "  ./app.sh down prod      # Stop production-like stack"
  echo "  ./app.sh restart dev    # Restart development stack"
  echo "  ./app.sh status prod    # Show status of prod stack"
}

# Restart a list of containers if they exist (POSIX-compatible)
restart_named_if_exist() {
  found=""
  for n in "$@"; do
    if docker ps -a --format '{{.Names}}' | grep -qx "$n"; then
      found="$found $n"
    fi
  done
  if [ -n "$found" ]; then
    echo "Restarting existing containers:$found"
    docker restart $found >/dev/null
    return 0
  fi
  return 1
}

# Check if docker compose is installed
check_docker_compose() {
  if ! command -v docker compose &> /dev/null; then
    echo "❌ docker compose is not installed. Please install Docker and Docker Compose."
    exit 1
  fi
}

# Check if .env file exists
check_env_file() {
  local file="$1"
  if [ -z "$file" ]; then file=".env"; fi
  if [ ! -f "$file" ]; then
    echo "❌ $file file not found."
    exit 1
  fi
}

# Make sure data directory exists
ensure_data_dir() {
  mkdir -p ./data
}

# Ensure dev network exists (docker-compose.dev.yml uses external network csv-viewer_app-network)
ensure_dev_network() {
  if ! docker network inspect csv-viewer_app-network >/dev/null 2>&1; then
    echo "🔧 Creating dev Docker network csv-viewer_app-network"
    docker network create csv-viewer_app-network >/dev/null
  fi
}

# Start application with AMD64 images
start_amd64() {
  echo "🚀 Starting CSV Viewer application (AMD64 version)..."
  echo "📋 Using default configuration from docker compose.yml"

  # Pull images from Docker Hub
  echo "📥 Pulling images from Docker Hub..."
  docker compose pull

  # Start the application
  echo "🏁 Starting application services..."
  docker compose up -d

  # Show status
  echo "✅ Application started! You can access it at:"
  echo "   Frontend: http://localhost:${FRONTEND_PORT}"
  echo "   Backend API: http://localhost:${BACKEND_PORT}"
  echo ""
  echo "📊 To view logs, run: docker compose logs -f"
}

# Start application with ARM images
start_arm() {
  echo "🚀 Starting CSV Viewer application (Development mode)..."
  echo "📋 Using configuration from docker-compose.dev.yml"

  # Start the application
  echo "🏁 Starting application services..."
  ensure_dev_network
  docker compose -p "$DEV_PROJECT" -f docker-compose.dev.yml --env-file .env.dev up -d

  # Show status with dev-specific ports from .env.dev if available
  set +u
  set -a; . ./.env.dev 2>/dev/null || true; set +a
  echo "✅ Application started in development mode! You can access it at:"
  echo "   Frontend: http://localhost:${FRONTEND_DEV_PORT:-3000}"
  echo "   Backend API: http://localhost:${BACKEND_DEV_PORT:-8000}"
  echo ""
  echo "📊 To view logs, run: docker compose -f docker-compose.dev.yml logs -f"
  docker compose -f docker-compose.arm.yml up -d

  # Show status
  echo "✅ Application started! You can access it at:"
  echo "   Frontend: http://localhost:${FRONTEND_PORT}"
  echo "   Backend API: http://localhost:${BACKEND_PORT}"
  echo ""
  echo "📊 To view logs, run: docker compose -f docker-compose.arm.yml logs -f"
}

# Start application in development mode
start_dev() {
  echo "� Status (dev)"
  docker ps \
    --filter "label=com.docker.compose.project=$DEV_PROJECT" \
    --format 'table {{.Names}}\t{{.Image}}\t{{.Label "com.docker.compose.service"}}\t{{.Status}}\t{{.Ports}}'
  echo "✅ Application started in development mode! You can access it at:"
  echo "   Frontend: http://localhost:${FRONTEND_PORT:-3001}"  # Use env variable with fallback
  echo "   Backend API: http://localhost:${BACKEND_PORT}"
  echo ""
  echo "📊 To view logs, run: docker compose -f docker-compose.dev.yml logs -f"
}

# New simple commands for dev stack
up_dev() {
  check_docker_compose
  check_env_file .env.dev
  ensure_dev_network
  echo "🚀 Up (dev)"
  docker compose -p "$DEV_PROJECT" -f docker-compose.dev.yml --env-file .env.dev up -d
  # Load ports for nicer output
  set +u
  set -a; . ./.env.dev 2>/dev/null || true; set +a
  echo "✅ Dev started:"
  echo "   Frontend: http://localhost:${FRONTEND_DEV_PORT:-3000}"
  echo "   Backend API: http://localhost:${BACKEND_DEV_PORT:-8000}"
}

down_dev() {
  check_docker_compose
  echo "🛑 Down (dev)"
  # Try named project first
  if ! docker compose -p "$DEV_PROJECT" -f docker-compose.dev.yml --env-file .env.dev down 2>/dev/null; then
    echo "ℹ️  No services under project $DEV_PROJECT or compose returned error. Trying legacy project..."
    docker compose -f docker-compose.dev.yml --env-file .env.dev down || true
  fi
}

status_dev() {
  echo "📊 Status (dev)"
  # List only services defined in the dev compose file
  local SVCS
  SVCS=$(docker compose -f docker-compose.dev.yml --env-file .env.dev config --services 2>/dev/null | xargs)
  if [ -z "$SVCS" ]; then
    echo "(no services defined in docker-compose.dev.yml)"
    return 0
  fi
  docker compose -f docker-compose.dev.yml --env-file .env.dev ps $SVCS
}

restart_dev() {
  check_docker_compose
  check_env_file .env.dev
  echo "🔄 Restart (dev)"
  # Restart only services defined in the dev compose file
  local SVCS
  SVCS=$(docker compose -f docker-compose.dev.yml --env-file .env.dev config --services 2>/dev/null | xargs)
  if [ -z "$SVCS" ]; then
    echo "(no services defined in docker-compose.dev.yml)"
    return 0
  fi
  # If there are no containers for this project yet, bring them up instead of no-op
  local RUNNING
  RUNNING=$(docker compose -p "$DEV_PROJECT" -f docker-compose.dev.yml --env-file .env.dev ps -q)
  if [ -z "$RUNNING" ]; then
    # Try restarting known named dev containers to avoid name conflicts
    if restart_named_if_exist opensearch-dev redis-dev csv-viewer-backend-dev csv-viewer-frontend-dev; then
      return 0
    fi
    # Try default compose project (no -p)
    local ALT_RUNNING
    ALT_RUNNING=$(docker compose -f docker-compose.dev.yml --env-file .env.dev ps -q)
    if [ -n "$ALT_RUNNING" ]; then
      echo "(found existing dev containers under default project; restarting them)"
      docker compose -f docker-compose.dev.yml --env-file .env.dev restart
      return 0
    fi
    echo "(no existing dev containers found, starting stack instead)"
    up_dev
    return 0
  fi
  docker compose -p "$DEV_PROJECT" -f docker-compose.dev.yml --env-file .env.dev restart
}

# New simple commands for prod stack
up_prod() {
  check_docker_compose
  check_env_file .env.prod
  echo "🚀 Up (prod)"
  docker compose -p "$PROD_PROJECT" -f docker-compose.prod.yml --env-file .env.prod up -d
  set +u
  set -a; . ./.env.prod 2>/dev/null || true; set +a
  echo "✅ Prod started:"
  echo "   Frontend: http://localhost:${FRONTEND_PORT:-8123}"
  echo "   Backend API: http://localhost:${BACKEND_PORT:-8001}"
}

down_prod() {
  check_docker_compose
  echo "🛑 Down (prod)"
  docker compose -p "$PROD_PROJECT" -f docker-compose.prod.yml --env-file .env.prod down
}

status_prod() {
  echo "📊 Status (prod)"
  # List only services defined in the prod compose file
  local SVCS
  SVCS=$(docker compose -f docker-compose.prod.yml --env-file .env.prod config --services 2>/dev/null | xargs)
  if [ -z "$SVCS" ]; then
    echo "(no services defined in docker-compose.prod.yml)"
    return 0
  fi
  docker compose -f docker-compose.prod.yml --env-file .env.prod ps $SVCS
}

restart_prod() {
  check_docker_compose
  check_env_file .env.prod
  echo "🔄 Restart (prod)"
  # Restart only services defined in the prod compose file
  local SVCS
  SVCS=$(docker compose -f docker-compose.prod.yml --env-file .env.prod config --services 2>/dev/null | xargs)
  if [ -z "$SVCS" ]; then
    echo "(no services defined in docker-compose.prod.yml)"
    return 0
  fi
  local RUNNING
  RUNNING=$(docker compose -p "$PROD_PROJECT" -f docker-compose.prod.yml --env-file .env.prod ps -q)
  if [ -z "$RUNNING" ]; then
    echo "(no existing prod containers found, starting stack instead)"
    up_prod
    return 0
  fi
  docker compose -p "$PROD_PROJECT" -f docker-compose.prod.yml --env-file .env.prod restart
}

# Stop application with AMD64 images
stop_amd64() {
  echo "🛑 Stopping CSV Viewer application (AMD64 version)..."
  docker compose down
  echo "✅ Application stopped successfully!"
}

# Stop application with ARM images
stop_arm() {
  echo "🛑 Stopping CSV Viewer application (ARM version)..."
  docker compose -f docker-compose.arm.yml down
  echo "✅ Application stopped successfully!"
}

# Stop application in development mode
stop_dev() {
  echo "🛑 Stopping CSV Viewer application (Development mode)..."
  docker compose -p "$DEV_PROJECT" -f docker-compose.dev.yml --env-file .env.dev down
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
  if curl -s -I http://localhost:${FRONTEND_PORT} > /dev/null 2>&1; then
    echo "✅ Frontend is running"
  else
    echo "❌ Frontend is not running"
  fi

  # Check backend
  if curl -s http://localhost:${BACKEND_PORT}/health > /dev/null 2>&1; then
    echo "✅ Backend is running"
  else
    echo "❌ Backend is not running"
  fi

  echo ""
  echo "For more details, run: docker compose ps"
}

# Main execution
case "$ACTION" in
  up)
    case "$TARGET" in
      dev) up_dev ;;
      prod) up_prod ;;
      *) show_help; exit 1 ;;
    esac
    ;;
  down)
    case "$TARGET" in
      dev) down_dev ;;
      prod) down_prod ;;
      *) show_help; exit 1 ;;
    esac
    ;;
  restart)
    case "$TARGET" in
      dev) restart_dev ;;
      prod) restart_prod ;;
      *) show_help; exit 1 ;;
    esac
    ;;
  status)
    case "$TARGET" in
      dev) status_dev ;;
      prod) status_prod ;;
      *) show_status ;;
    esac
    ;;
  start)
    check_docker_compose
    check_env_file .env
    ensure_data_dir

    case "$TARGET" in
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

    case "$TARGET" in
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

  status_legacy)
    show_status
    ;;

  help|*)
    show_help
    ;;
esac
