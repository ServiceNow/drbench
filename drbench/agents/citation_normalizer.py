"""
Citation normalization utilities for DrBench.

This module provides functions to normalize various citation formats to the standard
formats expected by the evaluation metrics.
"""

import logging
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def normalize_citation(raw_citation: str) -> Optional[str]:
    """
    Normalize various citation formats to standard format.

    Handles flexible input formats and converts them to the expected format
    for evaluation metrics.

    Args:
        raw_citation: The raw citation string from agent output

    Returns:
        Normalized citation string or None if cannot be parsed
    """
    if not raw_citation or not isinstance(raw_citation, str):
        return None

    citation = raw_citation.strip()

    # Return URLs as-is
    if citation.startswith("http"):
        return citation

    # Try to extract URLs from markdown-style links first
    # Pattern: [text](url) or text (url)
    url_patterns = [
        r"\[([^\]]*)\]\((https?://[^\)]+)\)",  # [text](url)
        r"\(https?://([^\)]+)\)",  # (url)
        r"https?://[^\s\)]+",  # bare url
    ]

    for pattern in url_patterns:
        match = re.search(pattern, citation)
        if match:
            if pattern.startswith(r"\["):
                # [text](url) format - return the URL
                return match.group(2)
            elif pattern.startswith(r"\("):
                # (url) format - return the URL with https://
                return f"https://{match.group(1)}"
            else:
                # bare url - return as-is
                return match.group(0)

    # Try to normalize MatterMost citations
    mattermost_result = normalize_mattermost_citation(citation)
    if mattermost_result:
        return mattermost_result

    # Try to normalize email citations
    email_result = normalize_email_citation(citation)
    if email_result:
        return email_result

    # Try to normalize file citations
    file_result = normalize_file_citation(citation)
    if file_result:
        return file_result

    # If it's already in the expected format, return as-is
    if is_already_normalized(citation):
        return citation

    logger.debug(f"Could not normalize citation: {citation}")
    return citation  # Return as-is rather than None to be more permissive


def normalize_mattermost_citation(citation: str) -> Optional[str]:
    """
    Normalize various MatterMost citation formats to: MatterMost_Channel_Team_User

    Handles formats like:
    - "Mattermost Message - Enterprise Chat (User: john.doe, Team: Compliance, Channel: General)"
    - "MatterMost chat from user john.doe in team Compliance channel General"
    - "MatterMost-General-Compliance-john.doe" (already normalized)
    """
    citation_lower = citation.lower()

    # Skip if not a chat citation (various keywords for chat platforms)
    chat_keywords = ["mattermost", "matter most", "chat", "message", "conversation", "discussion"]
    if not any(keyword in citation_lower for keyword in chat_keywords):
        return None

    # If already in normalized format, return as-is (case-insensitive check)
    if citation_lower.startswith("mattermost_"):
        parts = citation_lower.split("_")
        if len(parts) >= 4:
            return citation  # Already in correct format

    # Pattern 1: "Mattermost Message - Enterprise Chat (User: X, Team: Y, Channel: Z)"
    pattern1 = r"mattermost.*?user:\s*([^,\)]+).*?team:\s*([^,\)]+).*?channel:\s*([^,\)]+)"
    match1 = re.search(pattern1, citation, re.IGNORECASE)
    if match1:
        user, team, channel = match1.groups()
        return f"MatterMost_{channel.strip()}_{team.strip()}_{user.strip()}"

    # Pattern 2: "Chat/Message from user X in team Y channel Z"
    pattern2 = r"(?:mattermost|chat|message|conversation).*?user\s+([^\s]+).*?team\s+([^\s]+).*?channel\s+([^\s]+)"
    match2 = re.search(pattern2, citation, re.IGNORECASE)
    if match2:
        user, team, channel = match2.groups()
        return f"MatterMost_{channel.strip()}_{team.strip()}_{user.strip()}"

    # Pattern 3: Extract from parenthetical expressions
    # "**Mattermost Message** - Enterprise Chat (User: john.doe, Team: compliance_team, Channel: fsma_compliance)"
    pattern3 = r"\(.*?user:\s*([^,\)]+).*?team:\s*([^,\)]+).*?channel:\s*([^,\)]+).*?\)"
    match3 = re.search(pattern3, citation, re.IGNORECASE)
    if match3:
        user, team, channel = match3.groups()
        return f"MatterMost_{channel.strip()}_{team.strip()}_{user.strip()}"

    # Pattern 4: Try to extract individual components with flexible separators
    user_match = re.search(r"(?:user|by|@)\s*[:\s]*([^\s,\)#]+)", citation, re.IGNORECASE)
    team_match = re.search(r"team[:\s]+([^\s,\)]+)", citation, re.IGNORECASE)
    channel_match = re.search(r"(?:channel|#)\s*[:\s]*([^\s,\)]+)", citation, re.IGNORECASE)

    if user_match and team_match and channel_match:
        user = user_match.group(1).strip()
        team = team_match.group(1).strip()
        channel = channel_match.group(1).strip()
        return f"MatterMost_{channel}_{team}_{user}"

    logger.debug(f"Could not normalize MatterMost citation: {citation}")
    return None


def normalize_email_citation(citation: str) -> Optional[str]:
    """
    Normalize various email citation formats to: RoundCube-from-to-subject

    Handles formats like:
    - "Email from sarah.johnson@company.com on 20 Jan 2025"
    - "Email from X to Y with subject Z"
    - "RoundCube-from@email-to@email-Subject" (already normalized)
    """
    citation_lower = citation.lower()

    # Skip if not an email citation
    email_keywords = ["email", "mail", "roundcube", "imap", "smtp", "outlook", "gmail", "exchange"]
    if not any(keyword in citation_lower for keyword in email_keywords):
        return None

    # If already in RoundCube format, return as-is
    if citation_lower.startswith("roundcube-"):
        return citation

    # Pattern 1: "Email/Mail from X@Y on DATE" (no explicit to/subject)
    pattern1 = r"(?:email|mail)\s+from\s+([^\s@]+@[^\s]+)\s+on\s+"
    match1 = re.search(pattern1, citation_lower, re.IGNORECASE)
    if match1:
        from_email = match1.group(1).strip()
        # For simple "email from X on DATE" format, we'll use from_email for both from and to
        # and use a generic subject
        return f"RoundCube-{from_email}--Email from {from_email}"

    # Pattern 2: "Email/Mail from X to Y with subject Z"
    pattern2 = r"(?:email|mail)\s+from\s+([^\s]+)\s+to\s+([^\s]+)(?:\s+with\s+subject\s+(.+))?"
    match2 = re.search(pattern2, citation, re.IGNORECASE)
    if match2:
        from_email = match2.group(1).strip()
        to_email = match2.group(2).strip()
        subject = match2.group(3).strip() if match2.group(3) else "Email"
        return f"RoundCube-{from_email}-{to_email}-{subject}"

    # Pattern 3: "Email/Mail from X@Y" (minimal format)
    pattern3 = r"(?:email|mail)\s+from\s+([^\s@]+@[^\s]+)"
    match3 = re.search(pattern3, citation_lower, re.IGNORECASE)
    if match3:
        from_email = match3.group(1).strip()
        return f"RoundCube-{from_email}--Email from {from_email}"

    # Pattern 4: "Message/Email between X and Y regarding Z" format
    pattern4 = r"(?:message|email|mail)\s+between\s+([^\s@]+@[^\s]+)\s+and\s+([^\s@]+@[^\s]+)\s+regarding\s+(.+)"
    match4 = re.search(pattern4, citation, re.IGNORECASE)
    if match4:
        from_email = match4.group(1).strip()
        to_email = match4.group(2).strip()
        subject = match4.group(3).strip()
        return f"RoundCube-{from_email}-{to_email}-{subject}"

    # Pattern 5: Handle "IMAP/SMTP/other email system" with email addresses
    pattern5 = r"(?:imap|smtp|outlook|gmail|exchange).*?(?:from|message)\s+([^\s@]+@[^\s]+)\s+to\s+([^\s@]+@[^\s]+)"
    match5 = re.search(pattern5, citation, re.IGNORECASE)
    if match5:
        from_email = match5.group(1).strip()
        to_email = match5.group(2).strip()
        # Try to extract subject
        subject_match = re.search(r"(?:subject|re)[:\s]+(.+)", citation, re.IGNORECASE)
        subject = subject_match.group(1).strip() if subject_match else f"Email"
        return f"RoundCube-{from_email}-{to_email}-{subject}"

    # Pattern 6: Extract email addresses and try to construct
    email_pattern = r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
    emails = re.findall(email_pattern, citation)

    if emails:
        from_email = emails[0]
        to_email = emails[1] if len(emails) > 1 else ""
        # Try to extract a subject if present
        subject_match = re.search(r"(?:subject|re)[:\s]+(.+)", citation, re.IGNORECASE)
        subject = subject_match.group(1).strip() if subject_match else f"Email from {from_email}"
        return f"RoundCube-{from_email}-{to_email}-{subject}"

    logger.debug(f"Could not normalize email citation: {citation}")
    return None


def normalize_file_citation(citation: str) -> Optional[str]:
    """
    Normalize file path citations to just the filename.

    Handles formats like:
    - "shared/compliance-risks-retail-operations.pdf"
    - "/path/to/file.pdf"
    - "Nextcloud File (shared/file.pdf)"
    - "file.pdf" (already normalized)
    """
    citation_lower = citation.lower()

    # Skip URLs
    if citation.startswith("http"):
        return None

    # Skip MatterMost and email citations (but not file citations that mention "file")
    skip_keywords = ["mattermost", "roundcube"]
    email_keywords = ["email", "mail", "imap", "smtp", "outlook", "gmail", "exchange"]

    # Skip if it's clearly a MatterMost citation
    if any(keyword in citation_lower for keyword in skip_keywords):
        return None

    # Skip if it's clearly an email citation (but not just because it says "file")
    if any(keyword in citation_lower for keyword in email_keywords):
        # But allow it if it's clearly about file access
        file_context_keywords = ["document:", "file retrieved:", "accessed file", "nextcloud file"]
        if not any(file_keyword in citation_lower for file_keyword in file_context_keywords):
            return None

    # Pattern 1: Extract from "Nextcloud File/Document (path/file.ext)" format
    nextcloud_match = re.search(
        r'nextcloud\s+(?:file|document|doc)\s*\([`\'"]*([^`\'"\)]+)[`\'"]*\)', citation, re.IGNORECASE
    )
    if nextcloud_match:
        file_path = nextcloud_match.group(1).strip()
        return file_path.split("/")[-1]  # Get just the filename

    # Pattern 2: Extract from backticks `path/file.ext`
    backtick_match = re.search(r"`([^`]+)`", citation)
    if backtick_match:
        file_path = backtick_match.group(1).strip()
        return file_path.split("/")[-1]  # Get just the filename

    # Pattern 3: If it looks like a file path (has extension), extract filename
    if re.search(r"\.[a-zA-Z0-9]{1,4}$", citation):
        # It ends with a file extension
        if "/" in citation:
            return citation.split("/")[-1]  # Get just the filename
        else:
            return citation  # Already just a filename

    # Pattern 4: Check if it contains file path patterns with document keywords
    path_patterns = [
        r"(?:document|doc|file|accessed\s+file|retrieved)\s*[:\s]*([^/\s]+\.[a-zA-Z0-9]{1,4})(?:\s|$)",  # "Document: filename.ext"
        r"([^/\s]+\.[a-zA-Z0-9]{1,4})(?:\s|$)",  # filename.ext
        r"([a-zA-Z0-9._-]+\.(?:pdf|docx?|xlsx?|txt|csv|json|md|html?))",  # common extensions
    ]

    for pattern in path_patterns:
        match = re.search(pattern, citation, re.IGNORECASE)
        if match:
            # For patterns with document keywords, use the captured filename
            # For patterns without keywords, use the whole match
            filename = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
            return filename

    return None


def is_already_normalized(citation: str) -> bool:
    """
    Check if citation is already in normalized format.
    """
    citation_lower = citation.lower()

    # Check normalized MatterMost format
    if citation_lower.startswith("mattermost-"):
        parts = citation_lower.split("-")
        return len(parts) >= 4

    # Check normalized email format
    if citation_lower.startswith("roundcube-"):
        parts = citation_lower.split("-")
        return len(parts) >= 4

    # URLs are always considered normalized
    if citation.startswith("http"):
        return True

    # File extensions suggest it's probably a filename
    if re.search(r"\.[a-zA-Z0-9]{1,4}$", citation):
        return True

    return False


def extract_citation_info(citation: str) -> Dict[str, str]:
    """
    Extract structured information from a normalized citation.

    Returns a dictionary with citation type and relevant fields.
    """
    if not citation:
        return {"type": "unknown"}

    citation_lower = citation.lower()

    if citation.startswith("http"):
        return {"type": "url", "url": citation}

    if citation_lower.startswith("mattermost-"):
        parts = citation.split("-", 3)
        if len(parts) >= 4:
            return {"type": "mattermost", "channel": parts[1], "team": parts[2], "user": parts[3]}

    if citation_lower.startswith("roundcube-"):
        parts = citation.split("-", 3)
        if len(parts) >= 4:
            return {"type": "email", "from": parts[1], "to": parts[2], "subject": parts[3]}

    if re.search(r"\.[a-zA-Z0-9]{1,4}$", citation):
        return {"type": "file", "filename": citation}

    return {"type": "unknown", "raw": citation}
