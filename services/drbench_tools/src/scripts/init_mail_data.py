#!/usr/bin/env python3
"""
Email system data initialization script for DrBench services.

This script initializes the email system with users and demo emails
from self-contained JSONL files or traditional CSV data files.
"""
import json
import logging
import sys
from pathlib import Path

import pandas as pd
from drbench_utils.email.mail_manager import EmailManager, load_email_data

logger = logging.getLogger("mail data init")


def create_mail_users_from_csv(users_data_path, emails_jsonl_path=None):
    """Create mail users from CSV data (legacy method)."""
    logger.info(f"Creating mail users from {users_data_path}")

    try:
        # Initialize EmailManager
        email_manager = EmailManager()

        # Wait for Dovecot configuration
        if not email_manager.wait_for_dovecot_config():
            logger.error("Failed to find Dovecot configuration")
            return False

        # Read user data from CSV
        users_df = pd.read_csv(users_data_path)
        logger.info(f"Found {len(users_df)} users in CSV file")

        # Get vmail user IDs
        vmail_uid, vmail_gid = email_manager.get_vmail_ids()
        if vmail_uid is None or vmail_gid is None:
            logger.error("Could not get vmail user IDs")
            return False

        # Initialize Dovecot configuration only if not already done
        if not Path("/etc/dovecot/passwd").exists():
            if not email_manager.initialize_dovecot_config():
                return False

        # Convert DataFrame to list of dictionaries for easier processing
        users_data = users_df.to_dict("records")

        # Create each user
        for user in users_data:
            username = user["username"]
            password = user["passwd"]  # Note: existing CSV uses "passwd" not "password"
            email = user["email"]

            logger.info(f"Creating mail user: {username} ({email})")

            # Create Dovecot user entry
            if not email_manager.create_dovecot_user(username, password, vmail_uid, vmail_gid):
                logger.error(f"Failed to create Dovecot user: {username}")
                continue

            # Create user mailbox
            if not email_manager.create_user_mailbox(username):
                logger.error(f"Failed to create mailbox for: {username}")
                continue

            # Update virtual mailbox mappings for Postfix
            if not email_manager.update_virtual_mailboxes(username, email):
                logger.error(f"Failed to update virtual mailboxes for: {username}")
                continue

        # Set proper permissions
        if not email_manager.set_mail_permissions():
            logger.warning("Failed to set mail permissions, but continuing")

        # Create demonstration emails if JSONL provided
        if emails_jsonl_path and Path(emails_jsonl_path).exists():
            logger.info(f"Loading emails from {emails_jsonl_path}")
            with open(emails_jsonl_path, "r") as f:
                email_data_list = []
                for line in f:
                    line = line.strip()
                    if line:
                        email_data_list.append(json.loads(line))
            email_manager.create_emails_from_list(email_data_list, users_data)

        # Create completion flag
        if not email_manager.create_completion_flag():
            logger.warning("Failed to create completion flag, but users created")

        logger.info("Mail users created successfully!")
        return True

    except Exception as e:
        logger.error(f"Error creating mail users: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main function to initialize mail data."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Mail data initialization script started.")

    args = sys.argv[1:]
    if len(args) < 1 or len(args) > 2:
        logger.error("Usage: init_mail_data.py <path_to_data_file> [path_to_emails_jsonl]")
        logger.error("  For CSV users: init_mail_data.py users.csv [emails.jsonl]")
        logger.error("  For self-contained JSONL: init_mail_data.py self_contained.jsonl")
        sys.exit(1)

    data_file_path = Path(args[0])
    emails_jsonl_path = Path(args[1]) if len(args) > 1 else None

    if not data_file_path.exists():
        logger.error(f"Data file not found: {data_file_path}")
        sys.exit(1)

    if emails_jsonl_path and not emails_jsonl_path.exists():
        logger.error(f"Emails JSONL file not found: {emails_jsonl_path}")
        sys.exit(1)

    # Determine processing mode based on file extension
    file_suffix = data_file_path.suffix.lower()

    if file_suffix == ".csv":
        # Traditional CSV user file approach
        if not create_mail_users_from_csv(data_file_path, emails_jsonl_path):
            logger.error("Failed to create mail users")
            sys.exit(1)
    elif file_suffix in [".jsonl", ".json"] and emails_jsonl_path is None:
        # Self-contained JSONL file with both users and emails
        if not load_email_data(data_file_path):
            logger.error("Failed to load self-contained email data")
            sys.exit(1)
    else:
        logger.error(f"Unsupported file type or invalid arguments: {data_file_path}")
        logger.error("Expected either a CSV file for users or a self-contained JSONL file")
        sys.exit(1)

    logger.info("Mail data initialization completed successfully!")


if __name__ == "__main__":
    main()
