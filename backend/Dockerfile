# Base stage for shared dependencies
FROM python:3.12-slim as base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Generate requirements hash
RUN python -c "import hashlib; print(hashlib.md5(open('requirements.txt', 'rb').read()).hexdigest())" > requirements.hash

# Install Python dependencies
RUN if [ ! -f requirements.hash ]; then pip install --no-cache-dir -r requirements.txt; fi

# Set environment variable for Celery
ENV C_FORCE_ROOT=true

# Create necessary directories
RUN mkdir -p ./data
RUN mkdir -p /app/celery

# Production stage
FROM base as production

# Copy application code
COPY . .

# Copy and make entrypoint executable
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Expose ports
EXPOSE 8000
EXPOSE 5555

# Command to run the application and Celery worker
CMD ["/app/entrypoint.sh"]

# Development stage
FROM base as dev

# In dev, we'll mount the code as a volume, so minimal copying needed here
COPY dev-entrypoint.sh /app/
RUN chmod +x /app/dev-entrypoint.sh

# Expose ports
EXPOSE 8000
EXPOSE 5555

# Use development entrypoint with hot-reload
CMD ["/app/dev-entrypoint.sh"]
