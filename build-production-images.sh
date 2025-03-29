#!/bin/bash
set -e

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
    -H "Tags: rbpi" \
    https://ntfy.danielvolz.org/docker-build
}

# Display usage information
show_usage() {
  echo "CSV Viewer Image Builder"
  echo ""
  echo "Usage: ./build-production-images.sh [ARCH] [PUSH]"
  echo ""
  echo "Arguments:"
  echo "  ARCH    Architecture to build for: amd64 (default) or arm"
  echo "  PUSH    Whether to push to Docker Hub: push or no (default)"
  echo ""
  echo "Examples:"
  echo "  ./build-production-images.sh           # Build AMD64 images"
  echo "  ./build-production-images.sh arm       # Build ARM images"
  echo "  ./build-production-images.sh amd64 push # Build and push AMD64 images"
  echo ""
}

# Get architecture from command line argument
ARCH="${1:-amd64}"
PUSH="${2:-no}"

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
  docker-compose -f docker-compose.arm.yml build --pull
  
  echo "✅ Linux/ARM images built successfully!"
  send_notification "🚀 ARM64 images built successfully!" "CSV Viewer ARM Build Complete"
  
  if [ "$PUSH" == "push" ]; then
    echo "📤 Pushing images to Docker Hub..."
    # Extract image names from docker-compose.arm.yml
    FRONTEND_IMAGE=$(grep -A1 "frontend:" docker-compose.arm.yml | grep "image:" | awk '{print $2}')
    BACKEND_IMAGE=$(grep -A1 "backend:" docker-compose.arm.yml | grep "image:" | awk '{print $2}')
    
    echo "Pushing $FRONTEND_IMAGE..."
    docker push $FRONTEND_IMAGE
    
    echo "Pushing $BACKEND_IMAGE..."
    docker push $BACKEND_IMAGE
    
    echo "✅ Images pushed to Docker Hub successfully!"
    send_notification "📤 ARM64 images pushed to Docker Hub!" "CSV Viewer ARM Push Complete" "high"
  fi
  
  echo ""
  echo "Run the application with:"
  echo "  ./app.sh start arm"
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
  docker-compose build --pull
  
  echo "✅ Linux/AMD64 images built successfully!"
  send_notification "🚀 AMD64 images built successfully!" "CSV Viewer AMD64 Build Complete"
  
  if [ "$PUSH" == "push" ]; then
    echo "📤 Pushing images to Docker Hub..."
    # Extract image names from docker-compose.yml
    FRONTEND_IMAGE=$(grep -A1 "frontend:" docker-compose.yml | grep "image:" | awk '{print $2}')
    BACKEND_IMAGE=$(grep -A1 "backend:" docker-compose.yml | grep "image:" | awk '{print $2}')
    
    echo "Pushing $FRONTEND_IMAGE..."
    docker push $FRONTEND_IMAGE
    
    echo "Pushing $BACKEND_IMAGE..."
    docker push $BACKEND_IMAGE
    
    echo "✅ Images pushed to Docker Hub successfully!"
    send_notification "📤 AMD64 images pushed to Docker Hub!" "CSV Viewer AMD64 Push Complete" "high"
  fi
  
  echo ""
  echo "Run the application with:"
  echo "  ./app.sh start"
else
  echo "❌ Unknown architecture: $ARCH"
  echo "Valid options are: amd64 (default), arm"
  exit 1
fi

echo ""
echo "To monitor logs:"
echo "  docker-compose logs -f"

if [ "$PUSH" != "push" ]; then
  echo ""
  echo "To push images to Docker Hub, run:"
  echo "  docker login"
  echo "  ./build-production-images.sh $ARCH push"
fi
