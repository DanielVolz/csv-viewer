#!/bin/bash
set -e

# Get architecture from command line argument
ARCH="${1:-local}"
PUSH="${2:-no}"

echo "🔄 Building production images for CSV Viewer..."
echo "Target architecture: ${ARCH}"

if [ "$PUSH" == "push" ]; then
  echo "🔍 Push to Docker Hub enabled"
  # Check if logged in to Docker Hub
  if ! docker info 2>/dev/null | grep -q "Username"; then
    echo "❌ Not logged in to Docker Hub. Please run 'docker login' first."
    exit 1
  fi
  echo "✅ Docker Hub login verified"
fi

# Ensure scripts are executable
echo "🔒 Setting correct permissions for scripts..."
chmod +x backend/entrypoint.sh
chmod +x backend/dev-entrypoint.sh

if [ "$ARCH" == "amd64" ]; then
  # Check if buildx is available
  if ! docker buildx version > /dev/null 2>&1; then
    echo "❌ Docker buildx not available. Please make sure you have Docker Desktop with buildx or Docker Engine >= 19.03."
    exit 1
  fi

  # Create or use a builder instance
  echo "🔨 Setting up Docker buildx builder..."
  docker buildx use mybuilder 2>/dev/null || docker buildx create --name mybuilder --use

  # Build the images for linux/amd64
  echo "🏗️ Building linux/amd64 production images (this may take a few minutes)..."
  docker-compose -f docker-compose.amd64.yml build --pull --no-cache
  
  echo "✅ Linux/AMD64 images built successfully!"
  
  if [ "$PUSH" == "push" ]; then
    echo "📤 Pushing images to Docker Hub..."
    # Extract image names from docker-compose.amd64.yml
    FRONTEND_IMAGE=$(grep -A1 "frontend:" docker-compose.amd64.yml | grep "image:" | awk '{print $2}')
    BACKEND_IMAGE=$(grep -A1 "backend:" docker-compose.amd64.yml | grep "image:" | awk '{print $2}')
    
    echo "Pushing $FRONTEND_IMAGE..."
    docker push $FRONTEND_IMAGE
    
    echo "Pushing $BACKEND_IMAGE..."
    docker push $BACKEND_IMAGE
    
    echo "✅ Images pushed to Docker Hub successfully!"
  fi
  
  echo ""
  echo "Run the application with:"
  echo "  docker-compose -f docker-compose.amd64.yml up -d"
else
  # Build the images for local architecture
  echo "🏗️ Building production images for local architecture (this may take a few minutes)..."
  docker-compose build --pull --no-cache
  
  echo "✅ Production images built successfully!"
  echo ""
  echo "Run the application with:"
  echo "  docker-compose up -d"
fi

echo ""
echo "To monitor logs:"
echo "  docker-compose logs -f"

if [ "$PUSH" != "push" ] && [ "$ARCH" == "amd64" ]; then
  echo ""
  echo "To push images to Docker Hub, run:"
  echo "  docker login"
  echo "  ./build-production-images.sh amd64 push"
fi
