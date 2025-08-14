#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root (directory of this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE_DEFAULT="$SCRIPT_DIR/.env.prod"
COMPOSE_FILE_DEFAULT="$SCRIPT_DIR/docker-compose.prod.yml"

# Allow optional overrides via args: ENV_FILE COMPOSE_FILE
ENV_FILE="${1:-$ENV_FILE_DEFAULT}"
COMPOSE_FILE="${2:-$COMPOSE_FILE_DEFAULT}"

echo "Using env file: $ENV_FILE"
echo "Using compose file: $COMPOSE_FILE"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: env file not found: $ENV_FILE" >&2
  exit 1
fi
if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Error: compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

echo "Building production images (no cache): frontend-prod, backend-prod"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build --no-cache frontend-prod backend-prod

echo "Starting production stack in background"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d

echo "Done. To view logs: docker compose --env-file \"$ENV_FILE\" -f \"$COMPOSE_FILE\" logs -f"
