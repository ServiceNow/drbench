#!/bin/bash
set -e

echo "loading task..."
cd /app/drbench_tools/

poetry run python src/scripts/load_task.py

echo "Task loaded!"