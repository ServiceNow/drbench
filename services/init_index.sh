#!/bin/bash
set -e

echo "[init_index] Starting index.php generation..."

# Check if port mappings file exists
if [ ! -f "/tmp/port_mappings.json" ]; then
    echo "[init_index] WARNING: /tmp/port_mappings.json not found, using default JavaScript version"
    exit 0
fi

# Read port mappings
PORT_MAPPINGS=$(cat /tmp/port_mappings.json)
echo "[init_index] Port mappings: $PORT_MAPPINGS"

# Generate index.php with actual ports
echo "[init_index] Generating index.php with embedded port mappings..."
php /generate_index.php "$PORT_MAPPINGS" > /var/www/html/index.php

# Verify the file was created
if [ -f "/var/www/html/index.php" ]; then
    echo "[init_index] index.php generated successfully"
    # Show a preview of the generated URLs for debugging
    grep -o 'href="[^"]*"' /var/www/html/index.php | head -5 | while read line; do
        echo "[init_index] Generated URL: $line"
    done
else
    echo "[init_index] ERROR: Failed to generate index.php"
    exit 1
fi

echo "[init_index] Index generation completed"