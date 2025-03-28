# Base stage for shared dependencies
FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies - no conditional logic, always install during build
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variable for Celery
ENV C_FORCE_ROOT=true

# Create necessary directories
RUN mkdir -p ./data
RUN mkdir -p /app/celery

# Production stage
FROM base AS production

# Copy only necessary application code for production
COPY main.py config.py celeryconfig.py ./
COPY api/ ./api/
COPY app/ ./app/
COPY models/ ./models/
COPY tasks/ ./tasks/
COPY utils/ ./utils/

# Copy and make improved entrypoint executable
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Expose ports
EXPOSE 8000
EXPOSE 5555

# Command to run the application and Celery worker
CMD ["/app/entrypoint.sh"]

# Development stage
FROM base AS dev

# In dev, we'll mount the code as a volume, so minimal copying needed here
COPY dev-entrypoint.sh /app/
RUN chmod +x /app/dev-entrypoint.sh

# Expose ports
EXPOSE 8000
EXPOSE 5555

# Use development entrypoint with hot-reload
CMD ["/app/dev-entrypoint.sh"]
