#!/bin/bash
set -e

echo "Populating services with data"

cd /app/drbench_tools/

# echo "Populating Mattermost"
poetry run python src/scripts/init_mattermost_data.py src/data/users/admins.csv

# Wait for Nextcloud to be fully initialized
until [ -f "/var/www/nextcloud/config/config.php" ]; do
    echo "Waiting for Nextcloud to be initialized..."
    sleep 5
done
# echo "Populating Nextcloud"
poetry run python src/scripts/init_nextcloud_data.py src/data/users/admins.csv

# Wait for mail system to be initialized
until [ -f "/tmp/mail_initialized" ]; do
    echo "Waiting for mail system to be initialized..."
    sleep 5
done
# echo "Populating Email system"
poetry run python src/scripts/init_mail_data.py src/data/users/admins.csv
# Creating common email user for all task
poetry run python src/scripts/init_mail_data.py src/data/users/common_users.csv

echo "Data population completed successfully!"
