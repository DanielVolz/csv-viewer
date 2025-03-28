#!/bin/bash
set -e

echo "🔄 Building production images for CSV Viewer..."

# Ensure scripts are executable
echo "🔒 Setting correct permissions for scripts..."
chmod +x backend/entrypoint.sh
chmod +x backend/dev-entrypoint.sh

# Build the images
echo "🏗️ Building production images (this may take a few minutes)..."
docker-compose build --pull --no-cache

echo "✅ Production images built successfully!"
echo ""
echo "Run the application with:"
echo "  docker-compose up -d"
echo ""
echo "To monitor logs:"
echo "  docker-compose logs -f"
