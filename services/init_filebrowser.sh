#!/bin/bash

DB_FILE="/var/lib/filebrowser/filebrowser.db"
echo "[Filebrowser] Starting init_filebrowser script..."

# Load environment variables if file exists
if [ -f "/tmp/filebrowser_env" ]; then
    echo "[Filebrowser] Loading environment variables from /tmp/filebrowser_env"
    source /tmp/filebrowser_env
fi

# Use environment variables or defaults for credentials
FILEBROWSER_USER="${FILEBROWSER_USER:-admin}"
FILEBROWSER_PASSWORD="${FILEBROWSER_PASSWORD:-admin_pwd}"

echo "[Filebrowser] Using username: $FILEBROWSER_USER"

# Determine the home directory based on VNC_USER
if [ -n "$VNC_USER" ]; then
    if [ "$VNC_USER" = "root" ]; then
        HOME_DIR="/root"
    else
        HOME_DIR="/home/$VNC_USER"
    fi
else
    # Default to root if VNC_USER is not set
    HOME_DIR="/root"
fi

echo "[Filebrowser] Using home directory: $HOME_DIR"
echo "[Filebrowser] Using database file: $DB_FILE"

# Remove any existing database
if [ -f "$DB_FILE" ]; then
    echo "[Filebrowser] Removing existing database..."
    rm -f $DB_FILE
fi

# Initialize database and set all configurations at once
echo "[Filebrowser] Initializing filebrowser database..."
filebrowser --database $DB_FILE config init

echo "[Filebrowser] Setting configuration..."
filebrowser --database $DB_FILE config set --minimum-password-length 8 --root "$HOME_DIR"

# Add user with credentials from environment or defaults
echo "[Filebrowser] Adding user: $FILEBROWSER_USER"
filebrowser --database $DB_FILE users add "$FILEBROWSER_USER" "$FILEBROWSER_PASSWORD" --perm.admin

# Create a marker file to indicate completion
touch /var/lib/filebrowser/.setup_complete

echo "[Filebrowser] Filebrowser setup complete"

echo "[Filebrowser] Starting filebrowser server..."
exec filebrowser --database $DB_FILE --port 8090 --address 0.0.0.0 --log stdout
