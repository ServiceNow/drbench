#!/usr/bin/env python3
"""Lightweight SMTP server for non-root environments where postfix cannot run.

Listens on port 1025 and delivers messages to mbox files under /var/mail/,
matching the format dovecot reads. This replaces postfix when the container
runs with no_new_privs (e.g. toolkit cluster).

Usage:
    python smtp_server.py [--port 1025] [--mail-dir /var/mail]
"""

import argparse
import asyncio
import email
import fcntl
import logging
import os
import time
from email.utils import formatdate
from pathlib import Path

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP as SMTPServer

logger = logging.getLogger("smtp_server")

VIRTUAL_DOMAINS = {"drbench.com", "company.com", "external.com"}


class MboxHandler:
    """Delivers incoming messages to mbox files."""

    def __init__(self, mail_dir: str = "/var/mail"):
        self.mail_dir = Path(mail_dir)

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        domain = address.rsplit("@", 1)[-1] if "@" in address else ""
        if domain not in VIRTUAL_DOMAINS:
            return f"550 5.1.1 <{address}>: Relay access denied"
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(self, server, session, envelope):
        msg_data = envelope.content
        if isinstance(msg_data, bytes):
            msg_data = msg_data.decode("utf-8", errors="replace")

        for rcpt in envelope.rcpt_tos:
            local_part = rcpt.split("@")[0]
            user_dir = self.mail_dir / local_part
            inbox_path = user_dir / "inbox"

            os.makedirs(user_dir, exist_ok=True)

            # Write in mbox format (From_ line + message + blank line)
            from_addr = envelope.mail_from or "MAILER-DAEMON"
            mbox_line = f"From {from_addr}  {time.strftime('%c')}\n"

            with open(inbox_path, "a") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(mbox_line)
                f.write(msg_data)
                if not msg_data.endswith("\n"):
                    f.write("\n")
                f.write("\n")
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            logger.info("Delivered message from %s to %s", envelope.mail_from, rcpt)

        return "250 Message accepted for delivery"


def main():
    parser = argparse.ArgumentParser(description="Lightweight SMTP server")
    parser.add_argument("--port", type=int, default=1025, help="SMTP port")
    parser.add_argument(
        "--mail-dir", default="/var/mail", help="Mail delivery directory"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )

    handler = MboxHandler(mail_dir=args.mail_dir)
    controller = Controller(handler, hostname="0.0.0.0", port=args.port)
    controller.start()
    logger.info("SMTP server listening on 0.0.0.0:%d, delivering to %s", args.port, args.mail_dir)

    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
