#!/bin/bash
set -e

MCP_PREFIX="[MCP Servers]"

echo "$MCP_PREFIX Starting MCP servers initialization..."

###########################  Initialize Nextcloud MCP server
echo "$MCP_PREFIX Initializing Nextcloud MCP server..."

# Check if Nextcloud is running
if [ ! -f "/var/www/nextcloud/config/config.php" ]; then
    echo "$MCP_PREFIX Waiting for Nextcloud to initialize..."
    
    # Wait for Nextcloud to start (timeout after 60 seconds)
    TIMEOUT=60
    COUNT=0
    while [ ! -f "/var/www/nextcloud/config/config.php" ] && [ $COUNT -lt $TIMEOUT ]; do
        sleep 1
        COUNT=$((COUNT+1))
    done
    
    if [ ! -f "/var/www/nextcloud/config/config.php" ]; then
        echo "$MCP_PREFIX Nextcloud did not start within timeout period. Skipping Nextcloud MCP server."
    else
        echo "$MCP_PREFIX Nextcloud is now running."
    fi
fi

if [ -f "/var/www/nextcloud/config/config.php" ]; then
    # Create .env file with default settings if it doesn't exist
    if [ ! -f "/app/drbench_tools/src/mcp_servers/nextcloud/.env" ]; then
        echo "$MCP_PREFIX Creating default .env file for Nextcloud MCP..."
        cat > /app/drbench_tools/src/mcp_servers/nextcloud/.env << EOF
NEXTCLOUD_URL=http://localhost/nextcloud
NEXTCLOUD_USER=admin
NEXTCLOUD_PASSWORD=admin_pwd
LOG_LEVEL=INFO
ALLOWED_CLIENTS=*
EOF
    fi
    
    echo "$MCP_PREFIX Nextcloud MCP server initialization complete!"
fi

# Create signal file to indicate initialization is complete
touch /tmp/mcp_initialized

# Initialize other MCP servers
# (Add similar blocks for other MCP servers here)

echo "$MCP_PREFIX All MCP servers initialized!"
echo "$MCP_PREFIX Servers will be managed by supervisord and should start automatically."
echo "$MCP_PREFIX You can check server status with: supervisorctl status"
