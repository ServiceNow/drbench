#!/bin/bash
set -e

echo "Setting up health check service..."

# Allow port to be configurable via environment variable
HEALTHCHECK_PORT=${HEALTHCHECK_PORT:-8099}

cd /app/drbench_tools/

# Start the service
echo "Starting health check service on port ${HEALTHCHECK_PORT}..."
HEALTHCHECK_PORT=${HEALTHCHECK_PORT} poetry run python src/health/healthcheck.py &


echo "Waiting for health check service to be ready..."
# Wait for the health check service to be ready
until curl -s http://localhost:${HEALTHCHECK_PORT}/health >/dev/null 2>&1; do
    echo "Waiting for health check service to be ready..."
    sleep 5
done
echo "Health check service is ready on port ${HEALTHCHECK_PORT}!"