"""
Email system management utilities for DrBench services.

This module provides core functionality for managing email users and messages
in the DrBench containerized environment.
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

EMAIL_DOMAIN = "drbench.com"
VMAIL_USER = os.getenv("VMAIL_USER", "vmail")


class EmailManager:
    """Manages email system initialization and data loading."""

    def __init__(self, email_domain: str = EMAIL_DOMAIN, vmail_user: str = VMAIL_USER):
        self.email_domain = email_domain
        self.vmail_user = vmail_user
        self.vmail_uid = None
        self.vmail_gid = None

    def run_command(self, cmd: str, log_error: bool = True) -> Optional[subprocess.CompletedProcess]:
        """Run a shell command and return the result."""
        logger.debug(f"[Mail cmd]: {cmd}")
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
            return None

    def get_vmail_ids(self) -> Tuple[Optional[str], Optional[str]]:
        """Get the UID and GID for the vmail user."""
        if self.vmail_uid and self.vmail_gid:
            return self.vmail_uid, self.vmail_gid

        try:
            result = self.run_command(f"id -u {self.vmail_user}")
            if not result:
                return None, None
            self.vmail_uid = result.stdout.strip()

            result = self.run_command(f"id -g {self.vmail_user}")
            if not result:
                return None, None
            self.vmail_gid = result.stdout.strip()

            return self.vmail_uid, self.vmail_gid
        except Exception as e:
            logger.error(f"Failed to get vmail user IDs: {e}")
            return None, None

    def user_exists_in_dovecot(self, username: str) -> bool:
        """Check if a user already exists in the Dovecot password file."""
        passwd_file = Path("/etc/dovecot/passwd")
        if not passwd_file.exists():
            return False

        with open(passwd_file, "r") as f:
            for line in f:
                if line.startswith(f"{username}:"):
                    return True
        return False

    def create_dovecot_user(self, username: str, password: str, vmail_uid: str, vmail_gid: str) -> bool:
        """Add a user to the Dovecot password file if they don't already exist."""
        if self.user_exists_in_dovecot(username):
            logger.info(f"User {username} already exists in Dovecot configuration, skipping")
            return True

        passwd_line = f"{username}:{{PLAIN}}{password}:{vmail_uid}:{vmail_gid}::/var/mail/{username}:/bin/false\n"

        try:
            with open("/etc/dovecot/passwd", "a") as f:
                f.write(passwd_line)
            logger.info(f"Added user {username} to Dovecot configuration")
            return True
        except Exception as e:
            logger.error(f"Failed to add user {username} to Dovecot: {e}")
            return False

    def mailbox_exists(self, username: str) -> bool:
        """Check if a user's mailbox already exists."""
        mailbox_dir = Path(f"/var/mail/{username}")
        return mailbox_dir.exists()

    def update_virtual_mailboxes(self, username: str, email: str) -> bool:
        """Update Postfix virtual mailboxes file for email routing."""
        virtual_mailboxes_file = "/etc/postfix/virtual_mailboxes"
        mailbox_entry = f"{email} {username}/inbox\n"

        # Check if this email mapping already exists
        if Path(virtual_mailboxes_file).exists():
            with open(virtual_mailboxes_file, "r") as f:
                content = f.read()
                if f"{email} " in content:
                    logger.info(f"Virtual mailbox mapping for {email} already exists")
                    return True

        try:
            # Add the mapping
            with open(virtual_mailboxes_file, "a") as f:
                f.write(mailbox_entry)

            # Rebuild the hash database
            result = self.run_command("postmap /etc/postfix/virtual_mailboxes")
            if result:
                logger.info(f"Added virtual mailbox mapping: {email} -> {username}/inbox")
                return True
            else:
                logger.error(f"Failed to update virtual mailboxes for {email}")
                return False
        except Exception as e:
            logger.error(f"Failed to update virtual mailboxes for {email}: {e}")
            return False

    def create_user_mailbox(self, username: str, skip_welcome: bool = False) -> bool:
        """Create mailbox directory and initial inbox for a user."""
        mailbox_dir = Path(f"/var/mail/{username}")
        inbox_file = mailbox_dir / "inbox"

        if self.mailbox_exists(username):
            logger.info(f"Mailbox for user {username} already exists, skipping creation")
            return True

        try:
            mailbox_dir.mkdir(parents=True, exist_ok=True)
            inbox_file.touch(exist_ok=True)

            # Create sent folder for user's sent emails
            sent_file = mailbox_dir / "sent"
            sent_file.touch(exist_ok=True)

            # Set proper ownership for the mailbox directory and files
            vmail_uid, vmail_gid = self.get_vmail_ids()
            if vmail_uid and vmail_gid:
                self.run_command(f"chown -R {self.vmail_user}:{self.vmail_user} {mailbox_dir}")
                self.run_command(f"chmod 770 {mailbox_dir}")
                self.run_command(f"chmod 660 {inbox_file}")
                self.run_command(f"chmod 660 {sent_file}")

            # Add welcome message to inbox (mbox format) unless skipping
            if not skip_welcome:
                timestamp = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
                welcome_msg = f"""From system@{self.email_domain} {timestamp}
Return-Path: <system@{self.email_domain}>
Delivered-To: {username}@{self.email_domain}
Date: {datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}
From: System Administrator <system@{self.email_domain}>
To: {username}@{self.email_domain}
Subject: Welcome to Your DrBench Email Account
Message-ID: <welcome.{int(time.time())}.{username}@{self.email_domain}>
Content-Type: text/plain; charset=UTF-8

Welcome to your DrBench email account, {username}!

Your email system is now configured and ready to use.
You can send and receive emails between users on this system.

This is part of the DrBench enterprise research environment.

Best regards,
DrBench System Administrator

"""

                with open(inbox_file, "a") as f:
                    f.write(welcome_msg)

                # Fix ownership after writing welcome message
                vmail_uid, vmail_gid = self.get_vmail_ids()
                if vmail_uid and vmail_gid:
                    self.run_command(f"chown {self.vmail_user}:{self.vmail_user} {inbox_file}")

            logger.info(f"Created mailbox for user {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to create mailbox for {username}: {e}")
            return False

    def load_self_contained_jsonl(self, jsonl_path: Path) -> Tuple[List[Dict], List[Dict]]:
        """Load self-contained JSONL file with both users and emails."""
        users = []
        emails = []

        try:
            with open(jsonl_path, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:  # Skip empty lines
                        continue

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON on line {line_num}: {e}")
                        continue

                    if not isinstance(record, dict) or "type" not in record:
                        logger.error(f"Line {line_num}: Invalid record format, missing 'type' field")
                        continue

                    if record["type"] == "user":
                        users.append(record)
                    elif record["type"] == "email":
                        emails.append(record)
                    else:
                        logger.warning(f"Line {line_num}: Unknown record type '{record['type']}', skipping")

            logger.info(f"Loaded {len(users)} users and {len(emails)} emails from {jsonl_path}")
            return users, emails
        except Exception as e:
            logger.error(f"Failed to load self-contained JSONL from {jsonl_path}: {e}")
            return [], []

    def create_email_from_json(self, email_data: Dict, users_data: List[Dict]) -> bool:
        """Create an email message from JSON data."""
        try:
            # Map email addresses to usernames for lookups
            email_to_username = {}
            for user in users_data:
                # Handle both CSV format (with 'email' field) and JSONL user format
                user_email = user.get("email")
                username = user.get("username")
                if user_email and username:
                    # Ensure username is lowercase (Dovecot requirement)
                    email_to_username[user_email] = username.lower()

            # Extract sender info
            from_email = email_data.get("from", "")
            from_name = email_data.get("from_name", "")
            from_username = email_to_username.get(from_email, from_email.split("@")[0])

            # Process recipients
            to_emails = email_data.get("to", [])
            cc_emails = email_data.get("cc", [])

            # Parse date or use current time
            date_str = email_data.get("date", "")
            if date_str:
                try:
                    # Parse ISO format date
                    email_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    timestamp_str = email_date.strftime("%a %b %d %H:%M:%S %Y")
                    rfc_timestamp = email_date.strftime("%a, %d %b %Y %H:%M:%S %z")
                except:
                    timestamp_str = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
                    rfc_timestamp = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")
            else:
                timestamp_str = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
                rfc_timestamp = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

            # Build common email headers
            to_header = ", ".join(to_emails)
            cc_header = ""
            if cc_emails:
                cc_header = f"Cc: {', '.join(cc_emails)}\n"

            # Check if sender has a mailbox (for sent folder)
            sender_username = email_to_username.get(from_email, from_email.split("@")[0])
            sender_mailbox_exists = Path(f"/var/mail/{sender_username}/inbox").exists()

            # Check if this email should go to sent folder based on folder field
            email_folder = email_data.get("folder", "inbox").lower()

            # If email is marked as sent, put it directly in sender's sent folder
            if email_folder == "sent" and sender_mailbox_exists:
                self._create_sent_email(
                    email_data,
                    sender_username,
                    to_header,
                    cc_header,
                    timestamp_str,
                    rfc_timestamp,
                    from_name,
                    from_email,
                    from_username,
                )
                # Don't process recipients for sent emails
                return True

            # Create email for each recipient (to and cc) - inbox emails
            all_recipients = to_emails + cc_emails
            recipients_processed = 0

            for recipient_email in all_recipients:
                recipient_username = email_to_username.get(recipient_email, recipient_email.split("@")[0])

                # Skip if recipient doesn't have a mailbox
                inbox_file = Path(f"/var/mail/{recipient_username}/inbox")
                if not inbox_file.exists():
                    logger.warning(f"Skipping email to {recipient_username} - no mailbox found")
                    continue

                # Build email message in mbox format
                email_msg = f"""From {from_email} {timestamp_str}
Return-Path: <{from_email}>
Delivered-To: {recipient_email}
Date: {rfc_timestamp}
From: {from_name} <{from_email}>
To: {to_header}
{cc_header}Subject: {email_data.get('subject', 'No Subject')}
Message-ID: <{email_data.get('id', int(time.time()))}.{from_username}@{self.email_domain}>
Content-Type: text/plain; charset=UTF-8

{email_data.get('body', '')}

"""

                # Append to recipient's inbox
                with open(inbox_file, "a") as f:
                    f.write(email_msg)

                logger.info(f"Created email '{email_data.get('subject')}' from {from_email} to {recipient_email}")
                recipients_processed += 1

            # For inbox emails, also add to sender's sent folder if sender exists
            if sender_mailbox_exists and recipients_processed > 0:
                self._create_sent_email(
                    email_data,
                    sender_username,
                    to_header,
                    cc_header,
                    timestamp_str,
                    rfc_timestamp,
                    from_name,
                    from_email,
                    from_username,
                )

            return True
        except Exception as e:
            logger.error(f"Failed to create email {email_data.get('id', 'unknown')}: {e}")
            return False

    def _create_sent_email(
        self,
        email_data: Dict,
        sender_username: str,
        to_header: str,
        cc_header: str,
        timestamp_str: str,
        rfc_timestamp: str,
        from_name: str,
        from_email: str,
        from_username: str,
    ) -> bool:
        """Create a copy of the email in the sender's sent folder."""
        try:
            sent_file = Path(f"/var/mail/{sender_username}/sent")

            # Ensure sent folder exists
            if not sent_file.exists():
                sent_file.touch()

            # Build sent email message (similar to inbox but for sent folder)
            sent_email_msg = f"""From {from_email} {timestamp_str}
Return-Path: <{from_email}>
Date: {rfc_timestamp}
From: {from_name} <{from_email}>
To: {to_header}
{cc_header}Subject: {email_data.get('subject', 'No Subject')}
Message-ID: <{email_data.get('id', int(time.time()))}.{from_username}@{self.email_domain}>
Content-Type: text/plain; charset=UTF-8

{email_data.get('body', '')}

"""

            # Append to sender's sent folder
            with open(sent_file, "a") as f:
                f.write(sent_email_msg)

            logger.info(f"Added email '{email_data.get('subject')}' to {sender_username}'s sent folder")
            return True

        except Exception as e:
            logger.error(f"Failed to create sent email for {sender_username}: {e}")
            return False

    def create_emails_from_list(self, email_data_list: List[Dict], users_data: List[Dict]) -> bool:
        """Create emails from a list of email data."""
        logger.info(f"Creating {len(email_data_list)} emails...")

        success_count = 0
        for email_data in email_data_list:
            if self.create_email_from_json(email_data, users_data):
                success_count += 1

        logger.info(f"Successfully created {success_count}/{len(email_data_list)} emails")
        return success_count == len(email_data_list)

    def set_mail_permissions(self) -> bool:
        """Set proper permissions on mail directories."""
        logger.info("Setting mail directory permissions...")

        try:
            # Set ownership
            result = self.run_command(f"chown -R {self.vmail_user}:{self.vmail_user} /var/mail")
            if result is None:
                logger.error("Failed to set mail directory ownership")
                return False

            # Set permissions for mailbox directories
            result = self.run_command("chmod -R 770 /var/mail/*/")
            if result is None:
                logger.error("Failed to set mail directory permissions")
                return False

            # Set permissions for inbox files
            result = self.run_command("chmod 660 /var/mail/*/inbox")
            if result is None:
                logger.error("Failed to set inbox file permissions")
                return False

            logger.info("Mail permissions set successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to set mail permissions: {e}")
            return False

    def initialize_dovecot_config(self) -> bool:
        """Initialize the Dovecot password file."""
        logger.info("Initializing Dovecot configuration...")

        try:
            # Clear existing password file
            with open("/etc/dovecot/passwd", "w") as f:
                f.write("")  # Clear the file
            logger.info("Dovecot password file initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Dovecot config: {e}")
            return False

    def update_user_password(self, username: str, new_password: str, email: Optional[str] = None) -> bool:
        """Update the password for an email user, creating the user if they don't exist.

        Args:
            username: The username to update (will be converted to lowercase)
            new_password: The new password to set
            email: The email address for the user (required if creating new user)

        Returns:
            bool: True if password was updated or user created successfully, False otherwise
        """
        # Convert username to lowercase (Dovecot requirement)
        username = username.lower()

        try:
            # Get vmail user IDs
            vmail_uid, vmail_gid = self.get_vmail_ids()
            if vmail_uid is None or vmail_gid is None:
                logger.error("Could not get vmail user IDs for password update")
                return False

            passwd_file = Path("/etc/dovecot/passwd")

            # Check if user exists
            user_exists = False
            if passwd_file.exists():
                with open(passwd_file, "r") as f:
                    lines = f.readlines()

                # Find and update the user's line
                for i, line in enumerate(lines):
                    if line.startswith(f"{username}:"):
                        # User found, update their password
                        # Format: username:{PLAIN}password:uid:gid::homedir:shell
                        parts = line.strip().split(":")
                        if len(parts) >= 7:
                            # Update password field (index 1)
                            parts[1] = f"{{PLAIN}}{new_password}"
                            lines[i] = ":".join(parts) + "\n"
                            user_exists = True

                            # Write updated lines back to file
                            with open(passwd_file, "w") as f:
                                f.writelines(lines)

                            logger.info(f"Successfully updated password for existing user {username}")
                            return True

            # User doesn't exist, create them
            if not user_exists:
                logger.warning(
                    f"User {username} not found in Dovecot password file. Creating new user with empty mailbox."
                )

                # Generate email if not provided
                if not email:
                    email = f"{username}@{self.email_domain}"
                    logger.info(f"No email provided, using default: {email}")

                # Create Dovecot user entry
                if not self.create_dovecot_user(username, new_password, vmail_uid, vmail_gid):
                    logger.error(f"Failed to create Dovecot user: {username}")
                    return False

                # Create user mailbox (with welcome message)
                if not self.create_user_mailbox(username, skip_welcome=False):
                    logger.error(f"Failed to create mailbox for: {username}")
                    return False

                # Update virtual mailbox mappings for Postfix
                if not self.update_virtual_mailboxes(username, email):
                    logger.error(f"Failed to update virtual mailboxes for: {username}")
                    return False

                logger.info(f"Successfully created new email user {username} with password set")
                return True

        except Exception as e:
            logger.error(f"Failed to update/create user {username}: {e}")
            return False

    def create_completion_flag(self) -> bool:
        """Create a flag file to indicate mail initialization is complete."""
        try:
            logger.info("Creating completion flag file...")
            with open("/tmp/mail_data_initialized", "w") as f:
                f.write(f"Mail data initialized at {datetime.now().isoformat()}\n")
            return True
        except Exception as e:
            logger.error(f"Failed to create completion flag: {e}")
            return False

    def wait_for_dovecot_config(self, max_retries: int = 30) -> bool:
        """Wait for Dovecot configuration to be set up."""
        logger.info("Waiting for Dovecot configuration...")

        retries = 0
        while retries < max_retries:
            if Path("/etc/dovecot/dovecot.conf").exists():
                logger.info("Dovecot configuration found!")
                return True

            retries += 1
            logger.info(f"Retry {retries}/{max_retries}...")
            time.sleep(2)

        logger.warning("Dovecot configuration not found, proceeding anyway...")
        return True

    def load_email_data(self, jsonl_path: Path) -> bool:
        """
        Load self-contained email environment data from JSONL file.

        This function processes a self-contained JSONL file that includes both
        user definitions and email messages. It creates users, mailboxes, and
        emails all from a single file.
        """
        logger.info(f"Loading self-contained email data from {jsonl_path}")

        # Load both users and emails from the JSONL file
        users_data, emails_data = self.load_self_contained_jsonl(jsonl_path)

        if not users_data and not emails_data:
            logger.error("No valid users or emails found in JSONL file")
            return False

        # Get vmail user IDs
        vmail_uid, vmail_gid = self.get_vmail_ids()
        if vmail_uid is None or vmail_gid is None:
            logger.error("Could not get vmail user IDs")
            return False

        # Initialize Dovecot configuration if not already done
        if not Path("/etc/dovecot/passwd").exists():
            if not self.initialize_dovecot_config():
                return False

        # Create each user from JSONL data
        for user in users_data:
            username = user.get("username")
            password = user.get("password")
            email = user.get("email")

            if not username or not email:
                logger.error(f"Invalid user record missing required fields (username/email): {user}")
                continue

            # Generate default password if not provided
            if not password:
                password = f"{username}_pwd"
                logger.info(f"Generated default password for user {username}")

            # Convert username to lowercase (Dovecot requirement)
            original_username = username
            username = username.lower()
            if original_username != username:
                logger.info(
                    f"Converting username from '{original_username}' to '{username}' (Dovecot requires lowercase)"
                )

            logger.info(f"Creating mail user: {username} ({email})")

            # Create Dovecot user entry (idempotent)
            if not self.create_dovecot_user(username, password, vmail_uid, vmail_gid):
                logger.error(f"Failed to create Dovecot user: {username}")
                continue

            # Create user mailbox (idempotent, skip welcome message to avoid duplicates)
            if not self.create_user_mailbox(username, skip_welcome=True):
                logger.error(f"Failed to create mailbox for: {username}")
                continue

            # Update virtual mailbox mappings for Postfix
            if not self.update_virtual_mailboxes(username, email):
                logger.error(f"Failed to update virtual mailboxes for: {username}")
                continue

        # Create emails if any users were created
        if users_data and emails_data:
            if not self.create_emails_from_list(emails_data, users_data):
                logger.warning("Some emails failed to be created")

        # Set proper permissions
        if not self.set_mail_permissions():
            logger.warning("Failed to set mail permissions, but continuing")

        # Create completion flag
        if not self.create_completion_flag():
            logger.warning("Failed to create completion flag, but email data loaded")

        logger.info(
            f"Successfully loaded {len(users_data)} users and {len(emails_data)} emails from self-contained file"
        )
        return True


# Convenience function for backwards compatibility
def load_email_data(jsonl_path: Path) -> bool:
    """Load self-contained email data using the EmailManager."""
    manager = EmailManager()
    return manager.load_email_data(jsonl_path)
