#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from drbench_utils.nextcloud import NextcloudUserManager

# Read users data from the same CSV used by Mattermost
USERS_DATA_PATH = Path("drbench_tools/src/data/users/company_users.csv")
NEXTCLOUD_USER = os.getenv("NEXTCLOUD_USER", "www-data")


def setup_skeleton_directory():
    """Set up the skeleton directory that will be used for new users."""
    print("Setting up skeleton directory...")

    # Clear default skeleton directory
    skeleton_dir = Path("/var/www/nextcloud/core/skeleton")
    if skeleton_dir.exists():
        # Delete existing skeleton directory contents
        for item in skeleton_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink()
    else:
        skeleton_dir.mkdir(parents=True, exist_ok=True)

    # Create new skeleton structure
    (skeleton_dir / "Documents").mkdir(parents=True, exist_ok=True)

    # Add common files to skeleton directory
    common_files_dir = Path("/app/drbench_tools/src/data/common")
    if common_files_dir.exists():
        for item in common_files_dir.glob("**/*"):
            if item.is_file():
                # Create destination directory if it doesn't exist
                rel_path = item.relative_to(common_files_dir)
                dest_dir = Path(skeleton_dir) / rel_path.parent
                dest_dir.mkdir(parents=True, exist_ok=True)

                # Copy file
                shutil.copy2(item, Path(skeleton_dir) / rel_path)

    # Create a default welcome file
    with open(skeleton_dir / "Documents" / "welcome.txt", "w") as f:
        f.write("Welcome to Nextcloud!\n\nThis file is shared with all users.")

    # Ensure correct permissions
    subprocess.run(f"chown -R {NEXTCLOUD_USER}:{NEXTCLOUD_USER} {skeleton_dir}", shell=True)
    print("Skeleton directory setup complete.")


def setup_user_personal_files(users_data_path=USERS_DATA_PATH):
    """Set up personalized files for existing users."""
    print("Setting up personalized files for users...")

    # Create user manager instance
    manager = NextcloudUserManager(nextcloud_user=NEXTCLOUD_USER)

    # Get all existing users
    users_output = manager.run_occ_command("user:list --output=json")
    if not users_output:
        print("Failed to get user list")
        return False

    try:
        import json
        import pandas as pd
        
        users = json.loads(users_output)

        # Read user data from CSV to get additional information
        try:
            users_df = pd.read_csv(users_data_path)
            user_info_dict = {row["username"]: row for _, row in users_df.iterrows()}
        except Exception as e:
            print(f"Error reading user CSV: {e}")
            user_info_dict = {}

        # Process each user
        for username in users.keys():
            print(f"Setting up personalized files for user: {username}")

            # Get user data directory
            data_dir = manager.get_user_data_directory(username)
            if not data_dir:
                print(f"Cannot find user directory for user {username}. Skipping.")
                continue

            # Create user-specific directories
            Path(data_dir).joinpath("Documents", "Personal").mkdir(parents=True, exist_ok=True)

            # Copy user-specific files if they exist
            user_files_dir = Path(f"/app/drbench_tools/src/data/users/{username}/nextcloud")
            if user_files_dir.exists():
                for item in user_files_dir.glob("**/*"):
                    if item.is_file():
                        # Create destination directory if it doesn't exist
                        rel_path = item.relative_to(user_files_dir)
                        dest_dir = Path(data_dir) / rel_path.parent
                        dest_dir.mkdir(parents=True, exist_ok=True)

                        # Copy file
                        shutil.copy2(item, Path(data_dir) / rel_path)
                        print("  Copied file:", item, "to", Path(data_dir) / rel_path)
                print(f"Copied user-specific files for {username}")

            # Add personalized welcome file with user info
            welcome_content = f"Welcome {username} to your personalized Nextcloud space!\n\n"

            # Add additional personalized content if we have info from CSV
            if username in user_info_dict:
                user_data = user_info_dict[username]
                team = user_data.get("team", "")
                welcome_content += f"Name: {user_data.get('first_name', '')} {user_data.get('last_name', '')}\n"
                welcome_content += f"Email: {user_data.get('email', '')}\n"
                welcome_content += f"Team: {team}\n"

                # Create a team folder if we have team info
                if team:
                    team_folder = Path(data_dir) / "Documents" / team
                    team_folder.mkdir(exist_ok=True, parents=True)
                    with open(team_folder / "team-info.txt", "w") as f:
                        f.write(f"This is the folder for the {team} team.\n")
                        f.write("Use this folder to share documents with your team members.")

            with open(Path(data_dir) / "Documents" / "Personal" / f"welcome-{username}.txt", "w") as f:
                f.write(welcome_content)

            # Ensure correct permissions
            manager.set_file_permissions(data_dir)

        return True
    except Exception as e:
        print(f"Error setting up user files: {e}")
        import traceback

        traceback.print_exc()
        return False


def wait_for_nextcloud():
    """Wait for Nextcloud to be fully initialized."""
    max_retries = 5  # Reduced as supervisord should have ensured Nextcloud is ready
    retries = 0

    print("Checking if Nextcloud is fully initialized...")
    manager = NextcloudUserManager(nextcloud_user=NEXTCLOUD_USER)
    
    while retries < max_retries:
        if Path("/var/www/nextcloud/config/config.php").exists():
            # Check if maintenance mode is off
            maintenance_status = manager.run_occ_command("maintenance:mode")
            if maintenance_status and "disabled" in maintenance_status:
                print("Nextcloud is ready!")
                return True

        retries += 1
        print(f"Retry {retries}/{max_retries}...")
        time.sleep(2)

    print("Nextcloud should be initialized by now, proceeding anyway...")
    return True  # Continue anyway as supervisord should have ensured Nextcloud is ready


def setup_nextcloud_data(users_data_path=USERS_DATA_PATH):
    """Main function to set up Nextcloud data."""
    # Wait for Nextcloud to be ready
    if not wait_for_nextcloud():
        return False

    # Set up the skeleton directory
    setup_skeleton_directory()

    # Create users based on CSV
    manager = NextcloudUserManager(nextcloud_user=NEXTCLOUD_USER)
    if not manager.create_all_users(str(users_data_path)):
        print("Failed to create users")
        return False

    # Set up personalized files for each user
    if not setup_user_personal_files(users_data_path=users_data_path):
        print("Failed to set up user files")
        return False

    print("Nextcloud data setup completed successfully!")
    return True


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        users_data_path = Path(args[0])
    else:
        users_data_path = USERS_DATA_PATH
    success = setup_nextcloud_data(users_data_path=users_data_path)
    exit(0 if success else 1)