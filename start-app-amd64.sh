#!/bin/bash
set -e

# This script starts the application in production mode using the AMD64 images

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed. Please install Docker and Docker Compose."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please create one based on .env.example."
    exit 1
fi

# Make sure volumes exist
mkdir -p ./data

echo "🚀 Starting CSV Viewer application (AMD64 version)..."
echo "📋 Using configuration from docker-compose.amd64.yml"

# Pull images from Docker Hub
echo "📥 Pulling images from Docker Hub..."
docker-compose -f docker-compose.amd64.yml pull

# Start the application
echo "🏁 Starting application services..."
docker-compose -f docker-compose.amd64.yml up -d

# Show status
echo "✅ Application started! You can access it at:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo ""
echo "📊 To view logs, run: docker-compose -f docker-compose.amd64.yml logs -f"
echo "🛑 To stop the application, run: docker-compose -f docker-compose.amd64.yml down"
