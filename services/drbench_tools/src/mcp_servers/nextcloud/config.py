"""
Configuration settings for the Nextcloud MCP server.
"""

import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Nextcloud connection settings
NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "http://localhost:8081")
NEXTCLOUD_USER = os.getenv("NEXTCLOUD_USER", "admin")
NEXTCLOUD_PASSWORD = os.getenv("NEXTCLOUD_PASSWORD", "admin_pwd")

# MCP server settings
MCP_SERVER_NAME = "nextcloud-mcp"
MCP_SERVER_VERSION = "0.1.0"
MCP_SERVER_DESCRIPTION = "Model Context Protocol server for Nextcloud integration"
MCP_NC_SERVER_PORT = 9090

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Security settings
TOKEN_EXPIRY_SECONDS = 3600  # 1 hour
ALLOWED_CLIENTS = os.getenv("ALLOWED_CLIENTS", "*").split(",")
