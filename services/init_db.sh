#!/bin/bash
set -e

echo "[Init DB] Starting init_db script..."
# Log file for better debugging
LOGFILE="/var/log/init_db.log"
exec > >(tee -a ${LOGFILE}) 2>&1
echo "[Init DB] [$(date)] Starting PostgreSQL initialization..."

# Get PostgreSQL version and configuration directory
PG_VERSION=$(pg_config --version | grep -oE '[0-9]+' | head -1)
PG_CONF_DIR="/etc/postgresql/$PG_VERSION/main"
PG_DATA_DIR="/var/lib/postgresql/$PG_VERSION/main"
echo "[Init DB] Detected PostgreSQL version: $PG_VERSION"

# Wait for PostgreSQL to be ready if it's already running
sleep 5

# Initialize PostgreSQL cluster if it doesn't exist
if [ ! -d "$PG_DATA_DIR" ] || [ ! -f "$PG_DATA_DIR/PG_VERSION" ]; then
    echo "[Init DB] Initializing PostgreSQL cluster..."
    mkdir -p $PG_DATA_DIR
    chown -R ${POSTGRES_USER}:${POSTGRES_USER} $PG_DATA_DIR
    
    pg_createcluster $PG_VERSION main || true
    
    # Configure PostgreSQL to accept remote connections if the config files exist
    if [ -f "$PG_CONF_DIR/pg_hba.conf" ]; then
        echo "host all all 0.0.0.0/0 md5" >> "$PG_CONF_DIR/pg_hba.conf"
    fi
    if [ -f "$PG_CONF_DIR/postgresql.conf" ]; then
        echo "listen_addresses='*'" >> "$PG_CONF_DIR/postgresql.conf"
    fi
    echo "[Init DB] PostgreSQL cluster initialized."
else
    echo "[Init DB] PostgreSQL cluster already initialized."
fi

# Check if PostgreSQL is already running
if pg_isready -h localhost -p 5432 -U "${POSTGRES_USER}" >/dev/null 2>&1; then
    echo "[Init DB] PostgreSQL is already running."
else
    echo "[Init DB] Starting PostgreSQL service..."
    
    # Check for stale PID file
    PID_FILE="/var/lib/postgresql/$PG_VERSION/main/postmaster.pid"
    if [ -f "$PID_FILE" ]; then
        PID=$(head -1 "$PID_FILE")
        if ! ps -p $PID > /dev/null; then
            echo "[Init DB] Found stale PID file. Removing it..."
            rm -f "$PID_FILE"
        fi
    fi
    
    # Try different methods to start PostgreSQL
    if command -v pg_ctlcluster >/dev/null 2>&1; then
        pg_ctlcluster $PG_VERSION main start || true
    elif command -v service >/dev/null 2>&1; then
        service postgresql start || true
    elif [ -d "/etc/init.d" ] && [ -f "/etc/init.d/postgresql" ]; then
        /etc/init.d/postgresql start || true
    fi
    
    # Wait a bit for it to start
    sleep 5
fi

# Wait for PostgreSQL to be ready
echo "[Init DB] Waiting for PostgreSQL to start..."
until pg_isready -h localhost -p 5432 -U "${POSTGRES_USER}"; do
    echo "[Init DB] PostgreSQL is not ready yet. Sleeping for 2 seconds..."
    sleep 2
done
echo "[Init DB] PostgreSQL is ready!"


# Check if 'drbench_user' exists
if psql -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='drbench_user'" | grep -q 1; then
    echo "[Init DB] User drbench_user exists."
else
    echo "[Init DB] Creating user drbench_user..."
    psql -d postgres -c "CREATE USER drbench_user WITH PASSWORD 'drbenchpwd';"
fi

# Check if 'mattermost' database exists
if psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='mattermost'" | grep -q 1; then
    echo "[Init DB] Database mattermost exists."
else
    echo "[Init DB] Creating database mattermost..."
    psql -d postgres -c "CREATE DATABASE mattermost OWNER drbench_user;"
fi

# Grant necessary permissions to drbench_user
echo "[Init DB] Granting permissions to drbench_user..."
psql -d mattermost -c "GRANT ALL PRIVILEGES ON DATABASE mattermost TO drbench_user;"
psql -d mattermost -c "GRANT ALL PRIVILEGES ON SCHEMA public TO drbench_user;"

# Verify that Mattermost can now connect to the database
echo "[Init DB] Verifying Mattermost DB connection..."
MAX_RETRIES=5
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if PGPASSWORD="drbenchpwd" psql -U drbench_user -h localhost -d mattermost -c "SELECT 1" > /dev/null 2>&1; then
        echo "[Init DB] Mattermost database connection verified successfully!"
        # Touch a file to indicate successful DB setup for other services to check
        touch /tmp/db_initialized
        break
    else
        echo "[Init DB] Failed to verify Mattermost DB connection, retrying in 3 seconds... (Attempt $((RETRY_COUNT+1))/$MAX_RETRIES)"
        RETRY_COUNT=$((RETRY_COUNT+1))
        sleep 3
    fi
done

if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "[Init DB] ERROR: Failed to verify Mattermost DB connection after $MAX_RETRIES attempts!"
    exit 1
fi

sleep 10
echo "[Init DB] Database initialization completed successfully."
