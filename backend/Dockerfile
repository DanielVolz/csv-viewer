# Base stage for shared dependencies
# Support corporate proxies during build
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
FROM python:3.12-slim AS base

# Re-declare build args within the stage scope (required for use below)
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

WORKDIR /app

# Propagate proxy settings to build environment (pip, apt, curl)
# Provide empty defaults to avoid undefined var warnings when not set
ENV HTTP_PROXY=${HTTP_PROXY:-}
ENV HTTPS_PROXY=${HTTPS_PROXY:-}
ENV NO_PROXY=${NO_PROXY:-}

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
