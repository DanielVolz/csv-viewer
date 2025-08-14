#!/bin/bash
set -euo pipefail

# Send notification function
send_notification() {
  message="$1"
  title="$2"
  priority="${3:-low}"

  echo "📱 Sending notification: $title"
  curl -u pi:m5QtrF8hY \
    -d "$message" \
    -H "Title: $title" \
    -H "Priority: $priority" \
    -H "Tags: docker" \
    https://ntfy.danielvolz.org/docker-build
}

# Display usage information
show_usage() {
  echo "CSV Viewer Image Builder"
  echo ""
  echo "Usage: ./build-production-images.sh [ARCH] [PUSH] [ENV_FILE] [COMPOSE_FILE]"
  echo ""
  echo "Arguments:"
  echo "  ARCH    Architecture to build for: amd64 (default) or arm"
  echo "  PUSH    Whether to push to Docker Hub: push or no (default)"
  echo "  ENV_FILE     Optional path to .env file (default: .env.prod)"
  echo "  COMPOSE_FILE Optional path to compose file (default: prod for amd64, arm for arm)"
  echo ""
  echo "Examples:"
  echo "  ./build-production-images.sh                 # Build AMD64 prod images"
  echo "  ./build-production-images.sh arm             # Build ARM images"
  echo "  ./build-production-images.sh amd64 push      # Build and push AMD64 images"
  echo "  ./build-production-images.sh amd64 no .env.prod docker-compose.prod.yml"
  echo ""
}

# Get architecture from command line argument
ARCH="${1:-amd64}"
PUSH="${2:-no}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_ENV_FILE="$SCRIPT_DIR/.env.prod"
DEFAULT_COMPOSE_AMD64="$SCRIPT_DIR/docker-compose.prod.yml"
DEFAULT_COMPOSE_ARM="$SCRIPT_DIR/docker-compose.arm.yml"

ENV_FILE="${3:-$DEFAULT_ENV_FILE}"
if [ "$ARCH" = "arm" ]; then
  COMPOSE_FILE="${4:-$DEFAULT_COMPOSE_ARM}"
else
  COMPOSE_FILE="${4:-$DEFAULT_COMPOSE_AMD64}"
fi

# Show usage information for first run
if [ -z "$1" ]; then
  show_usage
  echo "------------------------------------------------------------------------"
  echo "No architecture specified. Defaulting to AMD64."
  echo "------------------------------------------------------------------------"
  echo ""
fi

echo "🔄 Building production images for CSV Viewer..."
echo "Target architecture: ${ARCH}"
echo "Using env file: ${ENV_FILE}"
echo "Using compose file: ${COMPOSE_FILE}"

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ Env file not found: $ENV_FILE"; exit 1;
fi
if [ ! -f "$COMPOSE_FILE" ]; then
  echo "❌ Compose file not found: $COMPOSE_FILE"; exit 1;
fi

if [ "$PUSH" == "push" ]; then
  echo "🔍 Push to Docker Hub enabled"
fi

# Ensure scripts are executable
echo "🔒 Setting correct permissions for scripts..."
chmod +x backend/entrypoint.sh
chmod +x backend/dev-entrypoint.sh

if [ "$ARCH" == "arm" ]; then
  # Check if buildx is available
  if ! docker buildx version > /dev/null 2>&1; then
    echo "❌ Docker buildx not available. Please make sure you have Docker Desktop with buildx or Docker Engine >= 19.03."
    exit 1
  fi

  # Create or use a builder instance
  echo "🔨 Setting up Docker buildx builder..."
  docker buildx use mybuilder 2>/dev/null || docker buildx create --name mybuilder --use

  # Build the images for linux/arm64
  echo "🏗️ Building linux/arm64 production images (this may take a few minutes)..."
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build --no-cache --pull frontend backend

  echo "✅ Linux/ARM images built successfully!"
  send_notification "🚀 ARM64 images built successfully!" "CSV Viewer ARM Build Complete"

  if [ "$PUSH" == "push" ]; then
    echo "📤 Pushing images to Docker Hub..."
  # Extract image names from compose (ARM)
  FRONTEND_IMAGE=$(grep -A1 "^[[:space:]]*frontend:" "$COMPOSE_FILE" | grep -m1 "image:" | awk '{print $2}')
  BACKEND_IMAGE=$(grep -A1 "^[[:space:]]*backend:" "$COMPOSE_FILE" | grep -m1 "image:" | awk '{print $2}')

    # Ensure images are pushed to danielvolz23 repository
    FRONTEND_IMAGE_NAME=$(echo $FRONTEND_IMAGE | awk -F/ '{print $NF}')
    BACKEND_IMAGE_NAME=$(echo $BACKEND_IMAGE | awk -F/ '{print $NF}')

    FRONTEND_PUSH_IMAGE="danielvolz23/$FRONTEND_IMAGE_NAME"
    BACKEND_PUSH_IMAGE="danielvolz23/$BACKEND_IMAGE_NAME"

    echo "Tagging $FRONTEND_IMAGE as $FRONTEND_PUSH_IMAGE..."
    docker tag $FRONTEND_IMAGE $FRONTEND_PUSH_IMAGE
    echo "Pushing $FRONTEND_PUSH_IMAGE..."
    docker push $FRONTEND_PUSH_IMAGE

    echo "Tagging $BACKEND_IMAGE as $BACKEND_PUSH_IMAGE..."
    docker tag $BACKEND_IMAGE $BACKEND_PUSH_IMAGE
    echo "Pushing $BACKEND_PUSH_IMAGE..."
    docker push $BACKEND_PUSH_IMAGE

    echo "✅ Images pushed to Docker Hub successfully!"
    send_notification "📤 ARM64 images pushed to Docker Hub!" "CSV Viewer ARM Push Complete" "high"
  fi

  echo ""
  echo "Starting ARM stack..."
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
  echo "Run logs with: docker compose --env-file \"$ENV_FILE\" -f \"$COMPOSE_FILE\" logs -f"
elif [ "$ARCH" == "amd64" ] || [ "$ARCH" == "default" ]; then
  # Check if buildx is available
  if ! docker buildx version > /dev/null 2>&1; then
    echo "❌ Docker buildx not available. Please make sure you have Docker Desktop with buildx or Docker Engine >= 19.03."
    exit 1
  fi

  # Create or use a builder instance
  echo "🔨 Setting up Docker buildx builder..."
  docker buildx use mybuilder 2>/dev/null || docker buildx create --name mybuilder --use

  # Build the images for linux/amd64 (now the default)
  echo "🏗️ Building linux/amd64 production images (this may take a few minutes)..."
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build --no-cache --pull frontend-prod backend-prod

  echo "✅ Linux/AMD64 images built successfully!"
  send_notification "🚀 AMD64 images built successfully!" "CSV Viewer AMD64 Build Complete"

  if [ "$PUSH" == "push" ]; then
    echo "📤 Pushing images to Docker Hub..."
  # Extract image names from compose (PROD amd64)
  FRONTEND_IMAGE=$(grep -A1 "^[[:space:]]*frontend-prod:" "$COMPOSE_FILE" | grep -m1 "image:" | awk '{print $2}')
  BACKEND_IMAGE=$(grep -A1 "^[[:space:]]*backend-prod:" "$COMPOSE_FILE" | grep -m1 "image:" | awk '{print $2}')

    # Ensure images are pushed to danielvolz23 repository
    FRONTEND_IMAGE_NAME=$(echo $FRONTEND_IMAGE | awk -F/ '{print $NF}')
    BACKEND_IMAGE_NAME=$(echo $BACKEND_IMAGE | awk -F/ '{print $NF}')

    FRONTEND_PUSH_IMAGE="danielvolz23/$FRONTEND_IMAGE_NAME"
    BACKEND_PUSH_IMAGE="danielvolz23/$BACKEND_IMAGE_NAME"

    echo "Tagging $FRONTEND_IMAGE as $FRONTEND_PUSH_IMAGE..."
    docker tag $FRONTEND_IMAGE $FRONTEND_PUSH_IMAGE
    echo "Pushing $FRONTEND_PUSH_IMAGE..."
    docker push $FRONTEND_PUSH_IMAGE

    echo "Tagging $BACKEND_IMAGE as $BACKEND_PUSH_IMAGE..."
    docker tag $BACKEND_IMAGE $BACKEND_PUSH_IMAGE
    echo "Pushing $BACKEND_PUSH_IMAGE..."
    docker push $BACKEND_PUSH_IMAGE

    echo "✅ Images pushed to Docker Hub successfully!"
    send_notification "📤 AMD64 images pushed to Docker Hub!" "CSV Viewer AMD64 Push Complete" "high"
  fi

  echo ""
  echo "Starting PROD stack..."
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
  echo "Run logs with: docker compose --env-file \"$ENV_FILE\" -f \"$COMPOSE_FILE\" logs -f"
else
  echo "❌ Unknown architecture: $ARCH"
  echo "Valid options are: amd64 (default), arm"
  exit 1
fi

echo ""
echo "To monitor logs:"
echo "  docker compose --env-file \"$ENV_FILE\" -f \"$COMPOSE_FILE\" logs -f"

if [ "$PUSH" != "push" ]; then
  echo ""
  echo "To push images to Docker Hub, run:"
  echo "  docker login"
  echo "  ./build-production-images.sh $ARCH push $ENV_FILE $COMPOSE_FILE"
fi
