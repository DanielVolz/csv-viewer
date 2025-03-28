#!/bin/bash
set -e

# This script stops the application running with AMD64 images

echo "🛑 Stopping CSV Viewer application (AMD64 version)..."

# Stop the application
docker-compose -f docker-compose.amd64.yml down

echo "✅ Application stopped successfully!"
