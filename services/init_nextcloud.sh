#!/bin/bash
set -e

NC_PREFIX="[Nextcloud]"

echo "$NC_PREFIX Starting Nextcloud services..."

# Add at the beginning of the script
echo "$NC_PREFIX Running script as user: $(whoami)"
echo "$NC_PREFIX User ID: $(id -u)"
echo "$NC_PREFIX Group ID: $(id -g)"
echo "$NC_PREFIX Permissions on config directory: $(ls -la /var/www/nextcloud/config/)"

# Check if it's the first time running the container
if [ ! -f "/var/www/nextcloud/config/config.php" ]; then
    echo "$NC_PREFIX Setting up Nextcloud..."
    cd /var/www/nextcloud

    sleep 5

    # Log the current directory and list the contents of the config directory
    echo "$NC_PREFIX Current directory: $(pwd)"
    echo "$NC_PREFIX Contents of /var/www/nextcloud/config/: $(ls -l /var/www/nextcloud/config/)"

    # Run commands directly without su since the script is already running as toolkit user
    php occ maintenance:install --database sqlite --database-name nextcloud \
      --database-user drbench --database-pass drbench_pwd --admin-user admin --admin-pass admin_pwd \
      --data-dir /var/www/nextcloud/data | sed "s/^/$NC_PREFIX /"

    php occ config:system:set trusted_domains 0 --value=localhost | sed "s/^/$NC_PREFIX /"

    # Add trusted domains from environment variable if set
    if [ -n "$NC_TRUSTED_DOMAINS" ]; then
      echo "$NC_PREFIX Adding trusted domains from environment variable..."
      IFS=',' read -ra DOMAINS <<< "$NC_TRUSTED_DOMAINS"
      for i in "${!DOMAINS[@]}"; do
        # Start from index 1 since we already have 0 set
        idx=$((i + 1))
        domain="${DOMAINS[$i]}"
        echo "$NC_PREFIX Adding trusted domain: $domain at index $idx"
        php occ config:system:set trusted_domains $idx --value="$domain" | sed "s/^/$NC_PREFIX /"
      done
    fi

    echo "$NC_PREFIX Contents of /var/www/nextcloud/config/: $(ls -l /var/www/nextcloud/config/)"
    
    # Disable the firstrunwizard app to prevent welcome video on first login
    echo "$NC_PREFIX Disabling first run wizard..."
    php occ app:disable firstrunwizard | sed "s/^/$NC_PREFIX /"

    # Set default entry point to the files page
    php occ config:system:set defaultapp --value="files" | sed "s/^/$NC_PREFIX /"

else
    echo "$NC_PREFIX Nextcloud is already configured."
fi

echo "$NC_PREFIX Nextcloud is ready!"
