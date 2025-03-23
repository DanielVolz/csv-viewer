#!/bin/bash

# Stop any existing docker containers first
echo "Stopping any existing containers..."
./stop-app-dev.sh

# Use a different port for frontend in development mode
echo "Modifying frontend port for development..."
FRONTEND_PORT=3001

# Check if port 3001 is in use
PORT_3001_PID=$(lsof -t -i:$FRONTEND_PORT 2>/dev/null)
if [ ! -z "$PORT_3001_PID" ]; then
  echo "Port $FRONTEND_PORT is in use by process $PORT_3001_PID. Killing process..."
  kill -9 $PORT_3001_PID
fi

# Check if port 8000 is in use
PORT_8000_PID=$(lsof -t -i:8000 2>/dev/null)
if [ ! -z "$PORT_8000_PID" ]; then
  echo "Port 8000 is in use by process $PORT_8000_PID. Killing process..."
  kill -9 $PORT_8000_PID
fi

# Start docker containers in development mode with the modified port
echo "Starting containers in development mode..."
FRONTEND_PORT=$FRONTEND_PORT docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

exit 0
