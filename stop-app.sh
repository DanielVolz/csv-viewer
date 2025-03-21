#!/bin/bash

echo "Stopping CSV Viewer Application..."

# Stop backend processes
echo "Stopping backend processes..."

# Find and kill Celery worker
CELERY_PID=$(pgrep -f "celery -A tasks.tasks worker")
if [ ! -z "$CELERY_PID" ]; then
  echo "Stopping Celery worker (PID: $CELERY_PID)..."
  kill $CELERY_PID
  echo "✅ Celery worker stopped"
else
  echo "No Celery worker process found"
fi

# Find and kill Uvicorn/backend server
BACKEND_PID=$(lsof -ti:8000)
if [ ! -z "$BACKEND_PID" ]; then
  echo "Stopping backend server (PID: $BACKEND_PID)..."
  kill $BACKEND_PID
  echo "✅ Backend server stopped"
else
  echo "No backend server process found on port 8000"
fi

# Find and kill AgentDeskAI browser tools server
BROWSER_TOOLS_PID=$(pgrep -f "@agentdeskai/browser-tools-server")
if [ ! -z "$BROWSER_TOOLS_PID" ]; then
  echo "Stopping AgentDeskAI browser tools server (PID: $BROWSER_TOOLS_PID)..."
  kill $BROWSER_TOOLS_PID
  echo "✅ AgentDeskAI browser tools server stopped"
else
  echo "No AgentDeskAI browser tools server process found"
fi

# Find and kill frontend (npm start)
FRONTEND_PID=$(lsof -ti:3000)
if [ ! -z "$FRONTEND_PID" ]; then
  echo "Stopping frontend server (PID: $FRONTEND_PID)..."
  kill $FRONTEND_PID
  echo "✅ Frontend server stopped"
else
  echo "No frontend server process found on port 3000"
fi

# Stop Redis
echo "Stopping Redis..."
brew services stop redis
if [ $? -eq 0 ]; then
  echo "✅ Redis stopped"
else
  echo "⚠️ Failed to stop Redis"
fi

# Stop OpenSearch
echo "Stopping OpenSearch..."
docker-compose -f /Users/danielvolz/docker/opensearch/docker-compose.yml down
if [ $? -eq 0 ]; then
  echo "✅ OpenSearch stopped"
else
  echo "⚠️ Failed to stop OpenSearch"
fi

echo "✅ CSV Viewer Application has been stopped"
