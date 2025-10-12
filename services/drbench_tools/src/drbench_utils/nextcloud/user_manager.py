"""Nextcloud user management utilities."""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger("nextcloud.user_manager")


class NextcloudUserManager:
    """Manages Nextcloud users and groups."""

    def __init__(self, nextcloud_user: str = None):
        """Initialize the Nextcloud user manager.

        Args:
            nextcloud_user: The system user running Nextcloud (default: www-data)
        """
        self.nextcloud_user = nextcloud_user or os.getenv("NEXTCLOUD_USER", "www-data")

    def run_occ_command(self, command: str) -> Optional[str]:
        """Run Nextcloud occ command and return the output.

        Args:
            command: The occ command to run (without 'occ' prefix)

        Returns:
            Command output as string, or None if command failed
        """
        full_command = f"cd /var/www/nextcloud && php occ {command}"
        logger.debug(f"[NC cmd]: {full_command}")

        process = subprocess.run(full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if process.returncode != 0:
            logger.error(f"Error running occ command: {command}")
            logger.error(f"STDERR: {process.stderr}")
            logger.error(f"STDOUT: {process.stdout}")
            return None

        return process.stdout.strip()

    def user_exists(self, username: str) -> bool:
        """Check if a user already exists in Nextcloud.

        Args:
            username: Username to check

        Returns:
            True if user exists, False otherwise
        """
        users_output = self.run_occ_command("user:list --output=json")
        if users_output:
            try:
                users = json.loads(users_output)
                return username in users
            except json.JSONDecodeError:
                logger.error("Failed to parse user list JSON")
        return False

    def update_user_password(self, username: str, password: str) -> bool:
        """Update password for an existing Nextcloud user.

        Args:
            username: Username to update password for
            password: New password

        Returns:
            True if password was updated successfully, False otherwise
        """
        try:
            if not self.user_exists(username):
                logger.error(f"User '{username}' does not exist in Nextcloud")
                return False

            logger.info(f"Updating password for Nextcloud user: {username}")

            # Set password via environment variable for security
            os.environ["OC_PASS"] = password
            result = self.run_occ_command(f'user:resetpassword "{username}" --password-from-env')
            os.environ.pop("OC_PASS")  # Clean up for security

            if result is not None:
                logger.info(f"Password updated successfully for user '{username}'")
                return True
            else:
                logger.error(f"Failed to update password for user '{username}'")
                return False
        except Exception as e:
            logger.error(f"Error updating password for user '{username}': {e}")
            return False

    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_admin: bool = False,
    ) -> bool:
        """Create a Nextcloud user.

        Args:
            username: Username for the user
            password: User's password
            email: Email address (optional)
            first_name: User's first name (optional)
            last_name: User's last name (optional)
            is_admin: Whether to make the user an admin

        Returns:
            True if user was created successfully, False otherwise
        """
        try:
            # Check if user already exists
            if self.user_exists(username):
                logger.info(f"User '{username}' already exists in Nextcloud. Updating password.")
                return self.update_user_password(username, password)

            # Build display name if provided
            display_name = None
            if first_name and last_name:
                display_name = f"{first_name} {last_name}"
            elif first_name:
                display_name = first_name
            elif last_name:
                display_name = last_name

            logger.info(f"Creating Nextcloud user: {username}" + (f" ({display_name})" if display_name else ""))

            # Build command with optional parameters
            create_cmd = f'user:add "{username}"'
            if display_name:
                create_cmd += f' --display-name="{display_name}"'
            if email:
                create_cmd += f' --email="{email}"'

            # Set password via environment variable
            os.environ["OC_PASS"] = password
            result = self.run_occ_command(create_cmd + " --password-from-env")
            os.environ.pop("OC_PASS")  # Clean up for security

            # Chown the user to the Nextcloud user
            user_dir = self.get_user_data_directory(username)
            user_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
            if user_dir and not self.set_file_permissions(user_dir):
                logger.error(f"Failed to set permissions for user directory: {user_dir}")
                return False

            if result and "was created successfully" in result:
                # Set user as admin if needed
                if is_admin:
                    self.run_occ_command(f"group:adduser admin {username}")
                    logger.info(f"Added {username} to admin group")
                return True
            else:
                logger.error(f"Failed to create user {username}")
                return False
        except Exception as e:
            logger.error(f"Error creating user '{username}': {e}")
            return False

    def create_group(self, group_name: str) -> bool:
        """Create a Nextcloud group if it doesn't exist.

        Args:
            group_name: Name of the group to create

        Returns:
            True if group was created or already exists, False on error
        """
        try:
            existing_groups = self.run_occ_command("group:list --output=json")

            if existing_groups:
                try:
                    groups = json.loads(existing_groups)
                    if group_name in groups:
                        logger.debug(f"Group '{group_name}' already exists. Skipping creation.")
                        return True
                except json.JSONDecodeError:
                    logger.warning("Failed to parse group list JSON")

            logger.info(f"Creating group: {group_name}")
            result = self.run_occ_command(f'group:add "{group_name}"')
            return result is not None
        except Exception as e:
            logger.error(f"Error creating group '{group_name}': {e}")
            return False

    def add_user_to_group(self, username: str, group_name: str) -> bool:
        """Add a user to a Nextcloud group.

        Args:
            username: Username to add
            group_name: Group name to add user to

        Returns:
            True if user was added successfully, False otherwise
        """
        try:
            logger.info(f"Adding user {username} to group {group_name}")
            result = self.run_occ_command(f'group:adduser "{group_name}" "{username}"')
            return result is not None
        except Exception as e:
            logger.error(f"Error adding user '{username}' to group '{group_name}': {e}")
            return False

    def create_all_users(self, users_data_path: str) -> bool:
        """Create all users from a CSV file.

        Args:
            users_data_path: Path to CSV file containing user data

        Returns:
            True if all users were created successfully, False otherwise
        """
        try:
            # Read user data from CSV
            users_df = pd.read_csv(users_data_path)
            logger.info(f"Found {len(users_df)} users in CSV file")

            # Create groups based on teams
            teams = users_df["team"].unique()
            for team in teams:
                team_group = team.replace(" ", "_")
                if not self.create_group(team_group):
                    logger.error(f"Failed to create group '{team_group}'")
                    return False

            # Create users
            for _, user in users_df.iterrows():
                username = user["username"]
                email = user["email"]
                first_name = user["first_name"]
                last_name = user["last_name"]
                password = user["passwd"]
                is_admin = user["is_admin"] == "true"
                team = user["team"]

                # Create user
                if not self.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=password,
                    is_admin=is_admin,
                ):
                    logger.error(f"Failed to create user '{username}'")
                    return False

                # Add user to team group
                team_group = team.replace(" ", "_")
                if not self.add_user_to_group(username, team_group):
                    logger.error(f"Failed to add user '{username}' to group '{team_group}'")
                    # Continue anyway, group membership is not critical

            return True
        except Exception as e:
            logger.error(f"Error creating users from CSV: {e}")
            import traceback

            traceback.print_exc()
            return False

    def get_user_data_directory(self, username: str) -> Optional[Path]:
        """Get the data directory path for a specific user.

        Args:
            username: Username to get directory for

        Returns:
            Path to user's data directory, or None if not found
        """
        try:
            user_info = self.run_occ_command(f"user:info {username}")
            if user_info:
                # Parse user directory from output
                import re

                m = re.search(r"user_directory: (.+)", user_info)
                if m:
                    return Path(m.group(1)) / "files"

            # Default fallback
            return Path("/var/www/nextcloud/data/") / username / "files"
        except Exception as e:
            logger.error(f"Error getting user directory for '{username}': {e}")
            return None

    def set_file_permissions(self, path: Path) -> bool:
        """Set correct permissions for Nextcloud files.

        Args:
            path: Path to set permissions for

        Returns:
            True if permissions were set successfully, False otherwise
        """
        try:
            subprocess.run(f"chown -R {self.nextcloud_user}:{self.nextcloud_user} {path}", shell=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error setting permissions on {path}: {e}")
            return False
