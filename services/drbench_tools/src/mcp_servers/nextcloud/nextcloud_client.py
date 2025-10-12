"""
Nextcloud API client wrapper - Simplified version.
"""

import logging
from typing import Any, Dict, List

from mcp_servers.nextcloud.config import NEXTCLOUD_PASSWORD, NEXTCLOUD_URL, NEXTCLOUD_USER
from nc_py_api import Nextcloud

logger = logging.getLogger(__name__)


class NextcloudClient:
    """Wrapper for Nextcloud API client with simplified methods."""

    def __init__(self):
        """Initialize the Nextcloud client."""
        self.client = Nextcloud(
            nextcloud_url=NEXTCLOUD_URL, nc_auth_user=NEXTCLOUD_USER, nc_auth_pass=NEXTCLOUD_PASSWORD
        )
        logger.info(f"Initialized Nextcloud client for {NEXTCLOUD_URL}")

    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Login to Nextcloud with different credentials.

        Args:
            username: Nextcloud username
            password: Nextcloud password

        Returns:
            Status dictionary
        """
        logger.info(f"Attempting login for user {username}")
        try:
            # Create a new client with the provided credentials
            self.client = Nextcloud(nextcloud_url=NEXTCLOUD_URL, nc_auth_user=username, nc_auth_pass=password)

            # Test the connection by listing files in root
            self.client.files.listdir()

            logger.info(f"Login successful for user {username}")
            return {"success": True, "username": username}
        except Exception as e:
            logger.error(f"Login failed for user {username}: {str(e)}")

            # Revert to original credentials
            self.client = Nextcloud(
                nextcloud_url=NEXTCLOUD_URL, nc_auth_user=NEXTCLOUD_USER, nc_auth_pass=NEXTCLOUD_PASSWORD
            )

            return {"success": False, "error": str(e)}

    async def list_files(self, path: str) -> List[Dict[str, Any]]:
        """
        List files and folders in a directory.

        Args:
            path: The directory path to list

        Returns:
            List of file/folder metadata dictionaries
        """
        logger.debug(f"Listing files in {path}")

        files = self.client.files.listdir(path)

        result = []
        for file in files:
            result.append(
                {
                    "name": file.name,
                    "path": file.user_path,
                    "size": file.info.size,
                    "mime_type": file.info.mimetype,
                    "is_directory": file.is_dir,
                    "last_modified": str(file.info.last_modified),
                }
            )

        return result

    async def get_file_content(self, path: str) -> bytes:
        """
        Get file content as bytes.

        Args:
            path: The file path

        Returns:
            File content as bytes
        """
        logger.debug(f"Getting content for file {path}")
        return self.client.files.download(path)

    async def search_files(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for files and folders whose name contains the `query` string.

        Args:
            query: The search query

        Returns:
            List of matching file/folder metadata dictionaries
        """
        logger.debug(f"Searching for files matching {query}")
        # Use the find method with name criteria
        results = self.client.files.find(req=["like", "name", f"%{query}%"])

        result = []
        for file in results:
            result.append(
                {
                    "name": file.name,
                    "path": file.user_path,
                    "size": file.info.size,
                    "mime_type": file.info.mimetype,
                    "is_directory": file.is_dir,
                    "last_modified": str(file.info.last_modified),
                }
            )

        return result

    async def create_folder(self, path: str) -> Dict[str, Any]:
        """
        Create a new folder.

        Args:
            path: The folder path to create

        Returns:
            Status dictionary
        """
        logger.debug(f"Creating folder at {path}")
        try:
            # Use the mkdir method from the official API
            fs_node = self.client.files.mkdir(path)
            return {"success": True, "path": path, "file_id": fs_node.file_id if hasattr(fs_node, "file_id") else None}
        except Exception as e:
            logger.error(f"Failed to create folder: {str(e)}")
            return {"success": False, "error": str(e)}

    async def delete_item(self, path: str) -> Dict[str, Any]:
        """
        Delete a file or folder.

        Args:
            path: The path to delete

        Returns:
            Status dictionary
        """
        logger.debug(f"Deleting item at {path}")
        try:
            self.client.files.delete(path)
            return {"success": True, "path": path}
        except Exception as e:
            logger.error(f"Failed to delete item: {str(e)}")
            return {"success": False, "error": str(e)}

    async def copy_item(self, source_path: str, destination_path: str, overwrite: bool = False) -> Dict[str, Any]:
        """
        Copy a file or folder.

        Args:
            source_path: The source path
            destination_path: The destination path
            overwrite: Whether to overwrite if destination exists

        Returns:
            Status dictionary
        """
        logger.debug(f"Copying from {source_path} to {destination_path}")
        try:
            # Use the copy method from the official API
            fs_node = self.client.files.copy(source_path, destination_path, overwrite=overwrite)
            return {
                "success": True,
                "source_path": source_path,
                "destination_path": destination_path,
                "file_id": fs_node.file_id if hasattr(fs_node, "file_id") else None,
            }
        except Exception as e:
            logger.error(f"Failed to copy item: {str(e)}")
            return {"success": False, "error": str(e)}
