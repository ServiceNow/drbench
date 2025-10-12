"""
Simplified Nextcloud MCP server with core functionality.
"""

import base64
import logging
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP
from mcp_servers.nextcloud.config import MCP_NC_SERVER_PORT, MCP_SERVER_DESCRIPTION, MCP_SERVER_NAME, MCP_SERVER_VERSION
from mcp_servers.nextcloud.nextcloud_client import NextcloudClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize NextcloudClient
nc_client = NextcloudClient()

# Create MCP server with explicit port
mcp = FastMCP(
    name=MCP_SERVER_NAME,
    version=MCP_SERVER_VERSION,
    description=MCP_SERVER_DESCRIPTION,
    port=MCP_NC_SERVER_PORT,
)


# Simple info resource
@mcp.resource("nextcloud://info")
def get_info() -> Dict[str, str]:
    """Get information about the Nextcloud server."""
    return {
        "server_name": MCP_SERVER_NAME,
        "server_version": MCP_SERVER_VERSION,
        "description": MCP_SERVER_DESCRIPTION,
        "type": "Nextcloud Files MCP Server",
    }


@mcp.tool()
async def login(username: str, password: str) -> Dict[str, Any]:
    """
    Login to Nextcloud with credentials.

    Args:
        username: Nextcloud username
        password: Nextcloud password

    Returns:
        Status dictionary with login result
    """
    try:
        # Create a new client with provided credentials
        result = await nc_client.login(username, password)
        return {"success": True, "message": "Login successful", "username": username}
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def list_directory(path: str = "/") -> Dict[str, Any]:
    """
    List files and folders in a directory.

    Args:
        path: The directory path to list (default: root directory)

    Returns:
        Dictionary with files information
    """
    try:
        files = await nc_client.list_files(path)
        return {"success": True, "path": path, "items": files}
    except Exception as e:
        logger.error(f"Error listing directory: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_file(path: str, as_text: bool = True) -> Dict[str, Any]:
    """
    Get the content of a file.

    Args:
        path: The file path
        as_text: Whether to return the content as text (if False, returns base64 encoded binary)

    Returns:
        Dictionary with file content
    """
    try:
        content = await nc_client.get_file_content(path)

        if as_text:
            try:
                # Try to decode as UTF-8
                text_content = content.decode("utf-8")
                return {"success": True, "path": path, "content": text_content, "encoding": "utf-8", "is_binary": False}
            except UnicodeDecodeError:
                # If decoding fails, fall back to base64
                as_text = False

        if not as_text:
            base64_content = base64.b64encode(content).decode("ascii")
            return {"success": True, "path": path, "content": base64_content, "encoding": "base64", "is_binary": True}
    except Exception as e:
        logger.error(f"Error getting file: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def search_files(query: str) -> Dict[str, Any]:
    """
    Search for files and folders matching a query.

    Args:
        query: The search query

    Returns:
        Dictionary with search results
    """
    try:
        results = await nc_client.search_files(query)
        return {"success": True, "query": query, "results": results}
    except Exception as e:
        logger.error(f"Error searching files: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def create_folder(path: str) -> Dict[str, Any]:
    """
    Create a new folder.

    Args:
        path: The folder path to create

    Returns:
        Status dictionary
    """
    try:
        result = await nc_client.create_folder(path)
        return result
    except Exception as e:
        logger.error(f"Error creating folder: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def delete_item(path: str) -> Dict[str, Any]:
    """
    Delete a file or folder.

    Args:
        path: The path to delete

    Returns:
        Status dictionary
    """
    try:
        result = await nc_client.delete_item(path)
        return result
    except Exception as e:
        logger.error(f"Error deleting item: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def copy_item(source_path: str, destination_path: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Copy a file or folder.

    Args:
        source_path: The source path
        destination_path: The destination path
        overwrite: Whether to overwrite if destination exists

    Returns:
        Status dictionary
    """
    try:
        result = await nc_client.copy_item(source_path, destination_path, overwrite)
        return result
    except Exception as e:
        logger.error(f"Error copying item: {str(e)}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    try:
        logger.info(f"Starting Nextcloud MCP server on port {mcp.settings.port}")
        logger.info(f"Server has core file operations tools configured")

        # Running with SSE transport will make the server
        # listen on /sse for connections and /sse/messages or /messages for message handling
        logger.info("Using SSE transport")
        mcp.run(transport="sse")
    except KeyboardInterrupt:
        logger.info("Nextcloud MCP server stopped by user")
    except Exception as e:
        logger.error(f"Error starting Nextcloud MCP server: {str(e)}")
        raise
