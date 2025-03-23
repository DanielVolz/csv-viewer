#!/bin/bash

# Stop docker containers from development mode
echo "Stopping development containers..."
docker-compose -f docker-compose.yml -f docker-compose.dev.yml down

echo "Development environment stopped."
exit 0
