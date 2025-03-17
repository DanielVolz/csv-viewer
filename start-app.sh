#!/bin/bash

echo "Starting CSV Viewer Application..."

# Start the backend server
echo "Starting backend server..."
cd backend
source .venv/bin/activate && uvicorn main:app --reload &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 2

# Start the frontend server
echo "Starting frontend server..."
cd frontend
npm start &
FRONTEND_PID=$!

# Function to handle script termination
function cleanup {
  echo "Shutting down servers..."
  kill $BACKEND_PID
  kill $FRONTEND_PID
  exit
}

# Trap SIGINT (Ctrl+C) and call cleanup
trap cleanup SIGINT

# Keep script running
echo "Both servers are now running!"
echo "Access the application at: http://localhost:3000"
echo "Press Ctrl+C to stop all servers"

wait
