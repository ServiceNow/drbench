"""Mattermost user management utilities."""

import json
import logging
import re
import subprocess
from typing import Any, List, Optional

import pandas as pd

logger = logging.getLogger("mattermost.user_manager")


class MattermostUserManager:
    """Manages Mattermost users, teams, and channels."""

    def __init__(self):
        """Initialize the Mattermost user manager."""
        pass

    @staticmethod
    def process_name(text: str) -> str:
        """Convert text to Mattermost-compatible name format.

        Args:
            text: The text to process

        Returns:
            Processed text with only alphanumeric characters and hyphens
        """
        return re.sub(r"\W+", "-", text).lower()

    @staticmethod
    def run_command(cmd: str, log_error: bool = True) -> Any:
        """Run a shell command and return the result.

        Args:
            cmd: The command to run
            log_error: Whether to log errors

        Returns:
            Command result object with stdout attribute
        """
        logger.debug(f"[MM cmd]: {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                check=True,
                text=True,
                encoding="utf-8",
                capture_output=True,
            )
            return result
        except subprocess.CalledProcessError as e:
            if log_error:
                logger.error(f"Command failed: {e}\nCommand output: {e.stdout}\nCommand error: {e.stderr}")
            # Return a result with empty stdout to handle gracefully
            return type("obj", (object,), {"stdout": "[]"})

    def user_exists(self, username: str) -> bool:
        """Check if a user exists in Mattermost.

        Args:
            username: The username to check

        Returns:
            True if user exists, False otherwise
        """
        try:
            cmd = f"mmctl --local user search {username} --format json"
            result = self.run_command(cmd, log_error=False)
            if not result or not result.stdout.strip():
                return False

            data = json.loads(result.stdout)
            # Handle both single dict and list responses
            if isinstance(data, dict):
                return data.get("username") == username
            elif isinstance(data, list):
                return any(u.get("username") == username for u in data if isinstance(u, dict))
            return False
        except (json.JSONDecodeError, Exception):
            return False

    def create_team(self, team: str) -> bool:
        """Create a Mattermost team if it doesn't exist.

        Args:
            team: The team display name

        Returns:
            True if team was created or already exists, False on error
        """
        try:
            # mmctl gracefully handles "already exists" so just try to create
            cmd = f'mmctl team create --name {self.process_name(team)} --display-name "{team}" --local'
            result = self.run_command(cmd, log_error=False)

            # Consider success if command succeeded or team already exists
            if result or "already exists" in getattr(result, "stderr", ""):
                logger.info(f"Team '{team}' ready")
                return True
            else:
                logger.error(f"Failed to create team '{team}'")
                return False
        except Exception as e:
            logger.error(f"Error creating team '{team}': {e}")
            return False

    def create_channel(self, channel: str, team: str) -> bool:
        """Create a Mattermost channel in a team if it doesn't exist.

        Args:
            channel: The channel display name
            team: The team display name

        Returns:
            True if channel was created or already exists, False on error
        """
        try:
            # mmctl gracefully handles "already exists" so just try to create
            cmd = f'mmctl channel create --team {self.process_name(team)} --name {self.process_name(channel)} --display-name "{channel}" --local'
            result = self.run_command(cmd, log_error=False)

            # Consider success if command succeeded or channel already exists
            if result or "already exists" in getattr(result, "stderr", ""):
                logger.info(f"Channel '{channel}' ready in team '{team}'")
                return True
            else:
                logger.error(f"Failed to create channel '{channel}' in team '{team}'")
                return False
        except Exception as e:
            logger.error(f"Error creating channel '{channel}' in team '{team}': {e}")
            return False

    def _add_user_to_team_and_channels(self, username: str, team: str, channels: Optional[List[str]] = None):
        """Helper method to add user to team and channels."""
        processed_team = self.process_name(team)
        cmd = f"mmctl team users add {processed_team} {username} --local"
        self.run_command(cmd, log_error=False)  # Don't log if already member
        logger.info(f"User '{username}' added to team '{processed_team}'")

        if channels:
            for channel in channels:
                processed_channel = self.process_name(channel.strip())
                if processed_channel:
                    cmd = f"mmctl channel users add {processed_team}:{processed_channel} {username} --local"
                    self.run_command(cmd, log_error=False)  # Don't log if already member
                    logger.info(f"User '{username}' added to channel '{processed_channel}' in team '{processed_team}'")

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        team: Optional[str] = None,
        channels: Optional[List[str]] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_admin: bool = False,
    ) -> bool:
        """Create a Mattermost user and add to team/channels.

        Args:
            username: Username for the user (mandatory)
            email: Email address (mandatory)
            password: User's password (mandatory)
            team: Team name to add user to (optional)
            channels: List of channel names to add user to (optional)
            first_name: User's first name (optional)
            last_name: User's last name (optional)
            is_admin: Whether to make the user a system admin (optional)

        Returns:
            True if user was created successfully, False otherwise
        """
        try:
            logger.info(f"Creating user: {username}")

            if self.user_exists(username):
                logger.info(f"User '{username}' already exists. Skipping creation.")
                return True

            # Build create command
            cmd = f"mmctl user create --username {username} --email {email} --password {password} --locale en --email-verified --local"
            if first_name:
                cmd += f' --firstname "{first_name}"'
            if last_name:
                cmd += f' --lastname "{last_name}"'
            if is_admin:
                cmd += " --system-admin"

            result = self.run_command(cmd)
            if not result:
                return False

            # Add user to team and channels
            if team:
                self._add_user_to_team_and_channels(username, team, channels)

            return True
        except Exception as e:
            logger.error(f"Error creating user '{username}': {e}")
            return False

    def update_user(
        self,
        username: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
        team: Optional[str] = None,
        channels: Optional[List[str]] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_admin: Optional[bool] = None,
    ) -> bool:
        """
        Create or update a Mattermost user. If the user does not exist, create them. If they exist, update provided fields.

        Args:
            username: Username for the user (mandatory)
            email: Email address (optional for update, mandatory for create)
            password: User's password
            team: Team name to add user to (optional)
            channels: List of channel names to add user to (optional)
            first_name: User's first name (optional)
            last_name: User's last name (optional)
            is_admin: Whether to make the user a system admin (optional)
        Returns:
            True if user was created/updated successfully, False otherwise
        """
        try:
            logger.info(f"Updating or creating user: {username}")

            if not self.user_exists(username):
                # Create user if not exists
                if not email:
                    email = f"{username}@drbench.com"
                if not password:
                    logger.error("Password required to create new user.")
                    return False
                return self.create_user(
                    username=username,
                    email=email,
                    password=password,
                    team=team,
                    channels=channels,
                    first_name=first_name,
                    last_name=last_name,
                    is_admin=is_admin if is_admin is not None else False,
                )

            # Update existing user fields
            if password:
                cmd = f"mmctl --local user change-password {username} --password {password}"
                if not self.run_command(cmd):
                    logger.error(f"Failed to update password for '{username}'")
                    return False
                logger.info(f"Password updated for user '{username}'")

            # Update other fields with single command where possible
            update_parts = []
            if first_name:
                update_parts.append(f'--firstname "{first_name}"')
            if last_name:
                update_parts.append(f'--lastname "{last_name}"')
            if is_admin is not None:
                update_parts.append("--system-admin" if is_admin else "--no-system-admin")

            if update_parts:
                cmd = f"mmctl user update {username} {' '.join(update_parts)} --local"
                self.run_command(cmd)
                logger.info(f"User profile updated for '{username}'")

            if email:
                cmd = f"mmctl user email {username} {email} --local"
                self.run_command(cmd)
                logger.info(f"Email updated for user '{username}'")

            # Add user to team and channels
            if team:
                self._add_user_to_team_and_channels(username, team, channels)

            return True
        except Exception as e:
            logger.error(f"Error updating/creating user '{username}': {e}")
            return False

    def create_all_users(self, users_data_path: str) -> bool:
        """Create all users from a CSV file.

        Args:
            users_data_path: Path to CSV file containing user data

        Returns:
            True if all users were created successfully, False otherwise
        """
        try:
            users = pd.read_csv(users_data_path)

            # Read and create all teams
            teams = users["team"].unique()
            for team in teams:
                if not self.create_team(team):
                    logger.error(f"Failed to create team '{team}'")
                    return False

            # Read all team, channel pairs but split channels by ,
            team_channels = []
            for _, row in users.iterrows():
                team = row["team"]
                channels = row["channels"].split(",")
                team_channels.extend([(team, channel.strip()) for channel in channels if channel.strip()])
            team_channels = sorted(set(team_channels))

            for t, c in team_channels:
                if not self.create_channel(channel=c, team=t):
                    logger.error(f"Failed to create channel '{c}' in team '{t}'")
                    return False

            # Create users
            for _, user in users.iterrows():
                username = user["username"]
                email = user["email"]
                first_name = user["first_name"]
                last_name = user["last_name"]
                password = user["passwd"]
                team = user["team"]
                channels = [ch.strip() for ch in user["channels"].split(",") if ch.strip()]
                is_admin = user["is_admin"] == "true"

                if not self.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=password,
                    team=team,
                    channels=channels,
                    is_admin=is_admin,
                ):
                    logger.error(f"Failed to create user '{username}'")
                    return False

            return True
        except Exception as e:
            logger.error(f"Error creating users from CSV: {e}")
            import traceback

            traceback.print_exc()
            return False
