#!/bin/bash
set -e


echo "[Entrypoint] Running script as user: $(whoami)"
echo "[Entrypoint] User ID: $(id -u)"
echo "[Entrypoint] Group ID: $(id -g)"
echo "[Entrypoint] POSTGRES_USER: $POSTGRES_USER"
echo "[Entrypoint] NEXTCLOUD_USER: $NEXTCLOUD_USER"
echo "[Entrypoint] MATTERMOST_USER: $MATTERMOST_USER"

echo "Starting Supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
