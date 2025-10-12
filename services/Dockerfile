# syntax=docker/dockerfile:1
FROM php:8.2-fpm-bookworm AS services

###########################################
# Build-time configuration (ARG variables)
###########################################

# Configurable users
ARG POSTGRES_USER=postgres
ARG NEXTCLOUD_USER=www-data
ARG MATTERMOST_USER=mattermost
ARG VNC_USER=root
ARG VMAIL_USER=vmail
ARG DBENCH_USER=root
ARG WSERVER_USER=www-data

# Configurable versions and download sources
ARG MATTERMOST_VERSION=10.6.1
ARG NEXTCLOUD_VERSION="31.0.6"
ARG NEXTCLOUD_MIRROR=""
ARG NEXTCLOUD_URL="https://download.nextcloud.com/server/releases/nextcloud-${NEXTCLOUD_VERSION}.tar.bz2"

###########################################
# Environment variables
###########################################

# User configuration
ENV POSTGRES_USER=${POSTGRES_USER}
ENV NEXTCLOUD_USER=${NEXTCLOUD_USER}
ENV MATTERMOST_USER=${MATTERMOST_USER}
ENV VNC_USER=${VNC_USER}
ENV VMAIL_USER=${VMAIL_USER}
ENV DBENCH_USER=${DBENCH_USER}
ENV WSERVER_USER=${WSERVER_USER}

# Email configuration
ENV EMAIL_DOMAIN="drbench.com"

# Database configuration
ENV POSTGRES_DB=mattermost
ENV MM_SQLSETTINGS_DRIVERNAME=postgres
ENV MM_SQLSETTINGS_MAX_IDLE_CONNS=10
ENV MM_SQLSETTINGS_MAX_OPEN_CONNS=10

# X11 configuration
ENV DISPLAY=:1
ENV USER=${VNC_USER}

# Path configuration
ENV PATH="/opt/mattermost/bin:/root/.local/bin:${PATH}"

###########################################
# Base system packages installation
###########################################

# Install system essentials, database, and web server
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    # Core system utilities
    bash \
    curl \
    zip \
    unzip \
    git \
    gnupg \
    lsb-release \
    ca-certificates \
    # Database
    postgresql \
    postgresql-client \
    postgresql-contrib \
    sqlite3 \
    libsqlite3-dev \
    libpq-dev \
    # Web server and supervisor
    nginx \
    supervisor \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

###########################################
# Desktop environment (optional)
###########################################

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    # Desktop environment
    xfce4 \
    xfce4-goodies \
    tightvncserver \
    novnc \
    websockify \
    x11vnc \
    dbus \
    dbus-x11 \
    xvfb \
    xauth \
    xorg \
    at-spi2-core \
    # Desktop applications
    firefox-esr \
    xfce4-terminal \
    # Themes and icons
    adwaita-icon-theme \
    papirus-icon-theme \
    arc-theme \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

###########################################
# PHP extensions and build dependencies
###########################################

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    # Image processing
    imagemagick \
    libmagickwand-dev \
    # PHP extension dependencies
    libzip-dev \
    libfreetype6-dev \
    libpng-dev \
    libjpeg-dev \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Install PHP extensions in separate steps for better error handling
RUN docker-php-ext-install -j$(nproc) pdo_sqlite pdo pdo_pgsql pgsql 
RUN docker-php-ext-install -j$(nproc) zip exif pcntl

# Install additional PHP extensions required for Roundcube
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    # Email components
    postfix \
    dovecot-core \
    dovecot-imapd \
    dovecot-pop3d \
    dovecot-lmtpd \
    libonig-dev \
    libicu-dev \
    libc-client-dev \
    libkrb5-dev \
    && docker-php-ext-configure imap --with-kerberos --with-imap-ssl \
    && docker-php-ext-install -j$(nproc) intl mbstring imap \
    && docker-php-ext-install -j$(nproc) mysqli \
    && rm -rf /var/lib/apt/lists/*

RUN docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j1 gd
RUN docker-php-ext-enable opcache
RUN pecl install imagick \
    && docker-php-ext-enable imagick \
    && mkdir -p /usr/local/etc/php-fpm.d/


###########################################
# PostgreSQL setup
###########################################

RUN mkdir -p /var/run/postgresql && chown -R ${POSTGRES_USER}:${POSTGRES_USER} /var/run/postgresql


USER ${POSTGRES_USER}
RUN mkdir -p /var/lib/postgresql/data && chmod 700 /var/lib/postgresql/data \
    && pg_createcluster 15 main || echo "PostgreSQL cluster already exists"

USER root

COPY postgres/postgres.conf /var/lib/postgresql/15/main/postgresql.conf
RUN chown ${POSTGRES_USER}:${POSTGRES_USER} /var/lib/postgresql/15/main/postgresql.conf \
    && chmod 600 /var/lib/postgresql/15/main/postgresql.conf

###########################################
# Python tools installation
###########################################

RUN apt-get update && apt-get install -y python3 \
    python3-pip \
    python3-dev \
    build-essential \
    pipx \
    && python3 -m pipx ensurepath \
    && pipx install poetry \
    && rm -rf /var/lib/apt/lists/*

###########################################
# Nextcloud installation
###########################################

WORKDIR /var/www

RUN --mount=type=cache,target=/var/cache/nextcloud-downloads \
    export DOWNLOAD_URL=${NEXTCLOUD_MIRROR:-$NEXTCLOUD_URL} && \
    DOWNLOAD_PATH="/var/cache/nextcloud-downloads/nextcloud.tar.bz2" && \
    echo "Downloading Nextcloud from: $DOWNLOAD_URL to $DOWNLOAD_PATH" && \
    # Check if file exists in cache, if not, download it
    if [ ! -f "$DOWNLOAD_PATH" ]; then \
        curl -L -o "$DOWNLOAD_PATH" "$DOWNLOAD_URL"; \
    else \
        echo "Nextcloud already in cache, skipping download."; \
    fi && \
    # Extract from cache location to a temporary location for processing
    # Use a tmpfs mount for the extraction to avoid writing to the final image layer unnecessarily
    # and to ensure a clean state for each build without lingering extracted files.
    RUN_TMPDIR=$(mktemp -d) && \
    tar -xjf "$DOWNLOAD_PATH" -C "$RUN_TMPDIR" && \
    mv "$RUN_TMPDIR"/nextcloud /var/www/nextcloud && \
    rm -rf "$RUN_TMPDIR" && \
    # Set permissions
    chown -R ${NEXTCLOUD_USER}:${NEXTCLOUD_USER} /var/www/nextcloud && \
    mkdir -p /var/www/nextcloud/data && \
    chown -R ${NEXTCLOUD_USER}:${NEXTCLOUD_USER} /var/www/nextcloud/data && \
    chmod 770 /var/www/nextcloud/data && \
    # Clear default skeleton directory
    rm -rf /var/www/nextcloud/core/skeleton/* && \
    # Configure PHP for Nextcloud
    echo "memory_limit=512M" > /usr/local/etc/php/conf.d/nextcloud-memory.ini

###########################################
# Mattermost installation
###########################################

RUN if [ "$(uname -m)" = "x86_64" ]; then \
        MM_ARCH="linux-amd64"; \
    elif [ "$(uname -m)" = "aarch64" ]; then \
        MM_ARCH="linux-arm64"; \
    else \
        echo "Unsupported architecture: $(uname -m)"; \
        exit 1; \
    fi && \
    # Download and extract
    MM_FILENAME="mattermost-$MATTERMOST_VERSION-$MM_ARCH.tar.gz" && \
    MM_URL="https://releases.mattermost.com/$MATTERMOST_VERSION/$MM_FILENAME" && \
    echo "Downloading Mattermost from: $MM_URL" && \
    curl -L -o mattermost.tar.gz "$MM_URL" && \
    tar -xzf mattermost.tar.gz && \
    rm mattermost.tar.gz && \
    mv mattermost /opt/mattermost && \
    # Setup user and permissions
    useradd -r ${MATTERMOST_USER} && \
    chown -R ${MATTERMOST_USER}:${MATTERMOST_USER} /opt/mattermost && \
    chmod -R g+w /opt/mattermost/config && \
    mkdir -p /opt/mattermost/data && \
    chown -R ${MATTERMOST_USER}:${MATTERMOST_USER} /opt/mattermost/data

###########################################
# Roundcube installation
###########################################

ARG ROUNDCUBE_VERSION=1.6.4
RUN mkdir -p /usr/share/roundcube && \
    curl -o roundcube.tar.gz -L https://github.com/roundcube/roundcubemail/releases/download/${ROUNDCUBE_VERSION}/roundcubemail-${ROUNDCUBE_VERSION}-complete.tar.gz && \
    tar -xzf roundcube.tar.gz -C /usr/share/roundcube --strip-components=1 && \
    rm roundcube.tar.gz && \
    chown -R ${WSERVER_USER}:${WSERVER_USER} /usr/share/roundcube && \
    # Create default configuration
    echo "<?php" > /usr/share/roundcube/config/config.inc.php && \
    echo "\$config = array();" >> /usr/share/roundcube/config/config.inc.php && \
    echo "\$config['db_dsnw'] = 'sqlite:////var/lib/roundcube/roundcube.db?mode=0646';" >> /usr/share/roundcube/config/config.inc.php && \
    # Use the format where users will enter full email addresses, hostname is dynamically replaced at init
    echo "\$config['login_username_format'] = '%u';" >> /usr/share/roundcube/config/config.inc.php && \
    echo "\$config['login_password_format'] = '%p';" >> /usr/share/roundcube/config/config.inc.php && \
    # SMTP configuration for email sending
    echo "\$config['smtp_server'] = 'localhost:25';" >> /usr/share/roundcube/config/config.inc.php && \
    echo "\$config['smtp_auth_type'] = null;" >> /usr/share/roundcube/config/config.inc.php && \
    echo "\$config['smtp_user'] = '';" >> /usr/share/roundcube/config/config.inc.php && \
    echo "\$config['smtp_pass'] = '';" >> /usr/share/roundcube/config/config.inc.php && \
    echo "\$config['des_key'] = 'changeme1234567890abcdef';" >> /usr/share/roundcube/config/config.inc.php && \
    echo "\$config['plugins'] = array('archive', 'zipdownload');" >> /usr/share/roundcube/config/config.inc.php && \
    echo "\$config['skin'] = 'elastic';" >> /usr/share/roundcube/config/config.inc.php && \
    echo "\$config['debug_level'] = 1;" >> /usr/share/roundcube/config/config.inc.php && \
    # Create SQLite database directory
    mkdir -p /var/lib/roundcube && \
    touch /var/lib/roundcube/roundcube.db && \
    chown -R ${WSERVER_USER}:${WSERVER_USER} /var/lib/roundcube && \
    chmod 750 /var/lib/roundcube

###########################################
# VNC server setup
###########################################

# Set up VNC server
RUN mkdir -p /${VNC_USER}/.vnc \
    && echo "vnc_pwd" | vncpasswd -f > /${VNC_USER}/.vnc/passwd \
    && chmod 600 /${VNC_USER}/.vnc/passwd \
    && echo '#!/bin/bash\nxrdb $HOME/.Xresources\nstartxfce4 &' > /${VNC_USER}/.vnc/xstartup \
    && chmod +x /${VNC_USER}/.vnc/xstartup \
    # Set up noVNC for web access
    && mkdir -p /opt/novnc/utils/websockify \
    && ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

# X11 configuration
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix && \
    echo "#!/bin/sh\nexport DISPLAY=:1\nexec \"\$@\"" > /usr/local/bin/with-x11 && \
    chmod +x /usr/local/bin/with-x11 && \
    # Create Xauthority setup
    echo "#!/bin/sh\ntouch ~/.Xauthority\nxauth generate :1 . trusted\nexec \"\$@\"" > /usr/local/bin/with-xauth && \
    chmod +x /usr/local/bin/with-xauth

# Configure XFCE
RUN mkdir -p /${VNC_USER}/.config/xfce4/xfconf/xfce-perchannel-xml && \
    echo '<?xml version="1.0" encoding="UTF-8"?>\n\
<channel name="xfce4-session" version="1.0">\n\
  <property name="general" type="empty">\n\
    <property name="AutoSave" type="bool" value="false"/>\n\
  </property>\n\
  <property name="sessions" type="empty">\n\
    <property name="Failsafe" type="empty">\n\
      <property name="IsFailsafe" type="bool" value="true"/>\n\
      <property name="Count" type="int" value="5"/>\n\
      <property name="Client0_Command" type="array">\n\
        <value type="string">xfwm4</value>\n\
      </property>\n\
      <property name="Client1_Command" type="array">\n\
        <value type="string">xfce4-panel</value>\n\
      </property>\n\
      <property name="Client2_Command" type="array">\n\
        <value type="string">xfdesktop</value>\n\
      </property>\n\
      <property name="Client3_Command" type="array">\n\
        <value type="string">xfce4-settings-helper</value>\n\
      </property>\n\
      <property name="Client4_Command" type="array">\n\
        <value type="string">thunar</value>\n\
        <value type="string">--daemon</value>\n\
      </property>\n\
    </property>\n\
  </property>\n\
</channel>' > /${VNC_USER}/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-session.xml

# Configure D-Bus for the desktop environment
RUN mkdir -p /var/run/dbus && \
    mkdir -p /usr/share/dbus-1/system.d && \
    mkdir -p /etc/dbus-1/system.d && \
    mkdir -p /etc/dbus-1/session.d && \
    dbus-uuidgen > /var/lib/dbus/machine-id && \
    dbus-uuidgen > /etc/machine-id

###########################################
# Filebrowser setup
###########################################

# Install filebrowser
USER ${VNC_USER}
COPY filebrowser/.filebrowser.json /etc/filebrowser/.filebrowser.json
RUN curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash -s v2.35.0 \
    && mkdir -p /etc/filebrowser \
    && mkdir -p /var/lib/filebrowser \
    && touch /var/lib/filebrowser/filebrowser.db \
    && chown -R ${VNC_USER}:${VNC_USER} /var/lib/filebrowser /etc/filebrowser \
    && chmod 600 /etc/filebrowser/.filebrowser.json
USER root

###########################################
# Application setup
###########################################

# Copy Mattermost config
COPY mattermost/config.json /opt/mattermost/config/config.json
RUN chmod 644 /opt/mattermost/config/config.json \
    && chown ${MATTERMOST_USER}:${MATTERMOST_USER} /opt/mattermost/config/config.json

# Set up application directory
WORKDIR /app
# Separate dependency installation from application code
COPY ./drbench_tools/pyproject.toml ./drbench_tools/poetry.lock /app/drbench_tools/
WORKDIR /app/drbench_tools
RUN --mount=type=cache,target=/root/.cache/pypi \
    poetry config virtualenvs.in-project true \
    && poetry install --no-root --without dev

COPY ./drbench_tools/. .
# Install our applications
RUN poetry install --only-root

WORKDIR /app

# Copy web root files
COPY index/index.php /var/www/html/index.php
COPY index/images /var/www/html/images

# Setup nginx
COPY nginx/http.d/combined.conf /etc/nginx/sites-available/default
RUN ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Setup init scripts
COPY ./init_nextcloud.sh /init_nextcloud.sh
COPY ./init_mattermost.sh /init_mattermost.sh  
COPY ./init_drbench.sh /init_drbench.sh
COPY ./init_data.sh /init_data.sh
COPY ./init_db.sh /init_db.sh
COPY ./init_filebrowser.sh /init_filebrowser.sh
COPY ./init_healthcheck.sh /init_healthcheck.sh
COPY ./init_mail.sh /init_mail.sh
COPY ./init_index.sh /init_index.sh
COPY ./generate_index.php /generate_index.php
COPY ./entrypoint.sh /entrypoint.sh
COPY ./vnc-setup.sh /vnc-setup.sh
COPY ./start_scripts /start_scripts
RUN chmod +x /init_*.sh /entrypoint.sh /vnc-setup.sh /start_scripts/*.sh

# Create directories for supervisor
RUN mkdir -p /var/log/supervisor /etc/nginx/conf.d

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/supervisord.conf
COPY supervisord_mcp.conf /etc/supervisor/supervisord_mcp.conf

#############################################
# DrBench setup
#############################################
RUN mkdir -p /drbench \
    && mkdir -p /drbench/task \
    && mkdir -p /drbench/results \
    && mkdir -p /drbench/scripts \
    && chown -R ${DBENCH_USER}:${DBENCH_USER} /drbench \
    && chmod -R 755 /drbench
COPY ./load_task.sh /drbench/scripts/load_task.sh
RUN chmod +x /drbench/scripts/load_task.sh


###########################################
# Final configuration
###########################################

# Expose ports
EXPOSE 80 8080 8081 8082 5901 6080 8099 8085 8090 1025 1143

# MCP Ports
EXPOSE 9090

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
