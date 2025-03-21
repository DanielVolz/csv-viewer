FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for CSV files if it doesn't exist
RUN mkdir -p ./data

# Expose port
EXPOSE 8000

# Expose Celery port
EXPOSE 5555

# Create necessary directory for Celery
RUN mkdir -p /app/celery

# Set environment variable for Celery
ENV C_FORCE_ROOT=true

# Copy the search test script
COPY search_test.py /app/backend/search_test.py

# Script to start both Celery and Uvicorn
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Command to run the application and Celery worker
CMD ["/app/entrypoint.sh"]
