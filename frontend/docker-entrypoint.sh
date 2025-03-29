#!/bin/sh
set -e

# Ensure the nginx config directory exists
mkdir -p /etc/nginx/conf.d

# Use development nginx config if NODE_ENV is development
if [ "$NODE_ENV" = "development" ]; then
  cp /app/nginx.dev.conf /etc/nginx/conf.d/default.conf
else
  # Replace environment variables in nginx config template
  envsubst '${BACKEND_PORT}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf
fi

# Execute the CMD
exec "$@"
