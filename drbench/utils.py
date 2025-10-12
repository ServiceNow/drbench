import hashlib, tqdm
import json, glob
import pandas as pd
import os, zipfile
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def get_hash_from_string(s):
    return hashlib.md5(str(s).encode()).hexdigest()


def extract_tags(text, tags=None):
    """
    Extract content from XML-like tags in the given text.

    Args:
        text (str): Text containing XML-like tags
        tags (list): List of tag names to extract. If None, extracts all tags.

    Returns:
        list: List of dictionaries containing the extracted tag contents
    """
    import re

    # If no specific tags provided, find all unique tags in the text
    if tags is None:
        tag_pattern = r"<(\w+)>"
        tags = list(set(re.findall(tag_pattern, text)))

    results = []
    # Find all blocks of content (assuming they're numbered like insight_1, insight_2, etc.)
    block_pattern = r"<\w+_\d+>(.*?)</\w+_\d+>"
    blocks = re.findall(block_pattern, text, re.DOTALL)

    for block in blocks:
        tag_contents = {}
        # Extract content for each requested tag
        for tag in tags:
            pattern = f"<{tag}>(.*?)</{tag}>"
            match = re.search(pattern, block, re.DOTALL)
            if match:
                tag_contents[tag] = match.group(1).strip()

        if tag_contents:  # Only append if we found any tags
            results.append(tag_contents)

    return results


def save_json(fname, data):
    with open(fname, "w") as f:
        json.dump(data, f, indent=4)


def load_json(fname):
    with open(fname, "r") as f:
        return json.load(f)


def save_markdown(fname, list_of_dicts, item_name="Item"):
    # List of distinct emojis that can be used
    emojis = [
        "🎯",
        "📝",
        "🔗",
        "❓",
        "✅",
        "💡",
        "📊",
        "📈",
        "🎨",
        "🔍",
        "💪",
        "🌟",
        "🎉",
        "📌",
        "🔆",
    ]

    # Create emoji mapping for unique tags
    unique_tags = {tag for d in list_of_dicts for tag in d.keys()}
    emoji_map = dict(zip(unique_tags, emojis[: len(unique_tags)]))

    with open(fname, "w") as f:
        for i, dict_item in enumerate(list_of_dicts, 1):
            f.write(f"# {item_name} {i}\n")
            for tag, content in dict_item.items():
                emoji = emoji_map[tag]
                f.write(f"## {emoji} {tag}\n{content}\n\n")
            if i < len(list_of_dicts):  # Don't add separator after last item
                f.write("=" * 50 + "\n\n")


def unzip_each_file_in_folder(folder_path, verbose=False):
    """
    Unzip each file in a folder into a folder called "unzipped" and make the folder name in "unzipped" the same as the file name. Only unzip if the folder does not exist.
    """
    import os
    import zipfile

    # Create the unzipped directory if it doesn't exist
    unzipped_dir = os.path.join(folder_path, "unzipped")
    os.makedirs(unzipped_dir, exist_ok=True)

    # Iterate through all files in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".zip"):
            # Get the base name without .zip extension
            base_name = os.path.splitext(filename)[0]
            target_dir = os.path.join(unzipped_dir, base_name)

            # Only unzip if the target directory doesn't exist
            if not os.path.exists(target_dir):
                zip_path = os.path.join(folder_path, filename)
                try:
                    with zipfile.ZipFile(zip_path, "r") as zip_ref:
                        zip_ref.extractall(target_dir)
                except zipfile.BadZipFile:
                    if verbose:
                        print(f"Warning: {filename} is not a valid zip file")
                except Exception as e:
                    if verbose:
                        print(f"Error extracting {filename}: {str(e)}")


import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Tuple


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate Mattermost JSONL import file"
    )
    parser.add_argument("file", help="Path to the JSONL file to validate")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed validation information",
    )
    parser.add_argument(
        "--summary", "-s", action="store_true", help="Show summary statistics"
    )
    parser.add_argument("--output", "-o", help="Write validation report to file")
    return parser.parse_args()


def validate_team(team: Dict) -> List[str]:
    """Validate a team object."""
    errors = []
    required_fields = ["type", "display_name", "name"]

    # Check required fields
    for field in required_fields:
        if field not in team:
            errors.append(f"Missing required field '{field}' in team")

    # Check team type
    if "type" in team and team["type"] not in ["O", "I"]:
        errors.append(
            f"Invalid team type: {team['type']}. Must be 'O' (Open) or 'I' (Invite)"
        )

    # Check name format (lowercase alphanumeric, underscore, dash)
    if "name" in team and not all(
        c.islower() or c.isdigit() or c in ["-", "_"] for c in team["name"]
    ):
        errors.append(
            f"Invalid team name format: {team['name']}. Must be lowercase alphanumeric with dashes/underscores"
        )

    return errors


def validate_channel(channel: Dict) -> List[str]:
    """Validate a channel object."""
    errors = []
    required_fields = ["team", "name", "display_name", "type", "header", "purpose"]

    # Check required fields
    for field in required_fields:
        if field not in channel:
            errors.append(f"Missing required field '{field}' in channel")

    # Check channel type
    if "type" in channel and channel["type"] not in ["O", "P", "D"]:
        errors.append(
            f"Invalid channel type: {channel['type']}. Must be 'O' (Public), 'P' (Private), or 'D' (Direct)"
        )

    # Check name format (lowercase alphanumeric, underscore, dash)
    if "name" in channel and not all(
        c.islower() or c.isdigit() or c in ["-", "_"] for c in channel["name"]
    ):
        errors.append(
            f"Invalid channel name format: {channel['name']}. Must be lowercase alphanumeric with dashes/underscores"
        )

    return errors


def validate_user(user: Dict) -> List[str]:
    """Validate a user object."""
    errors = []
    required_fields = ["username", "email"]

    # Check required fields
    for field in required_fields:
        if field not in user:
            errors.append(f"Missing required field '{field}' in user")

    # Check username format
    if "username" in user and not all(
        c.islower() or c.isdigit() or c in [".", "-", "_"] for c in user["username"]
    ):
        errors.append(
            f"Invalid username format: {user['username']}. Must be lowercase alphanumeric with dots/dashes/underscores"
        )

    # Check email format (basic check)
    if "email" in user and "@" not in user["email"]:
        errors.append(f"Invalid email format: {user['email']}")

    # Check auth_service
    if "auth_service" in user and user["auth_service"] not in [
        "",
        "ldap",
        "saml",
        "google",
        "office365",
    ]:
        errors.append(f"Potentially invalid auth_service: {user['auth_service']}")

    return errors


def validate_post(post: Dict) -> List[str]:
    """Validate a post object."""
    errors = []
    required_fields = ["team", "channel", "user", "message", "create_at"]

    # Check required fields
    for field in required_fields:
        if field not in post:
            errors.append(f"Missing required field '{field}' in post")

    # Check timestamp format
    if "create_at" in post:
        try:
            # Mattermost uses milliseconds since epoch
            timestamp = int(post["create_at"])
            if timestamp < 0:
                errors.append(f"Invalid negative timestamp: {timestamp}")
            # Check if timestamp is too far in the future (1 year from now)
            if timestamp > (datetime.now().timestamp() + 31536000) * 1000:
                errors.append(f"Timestamp too far in the future: {timestamp}")
        except (ValueError, TypeError):
            errors.append(f"Invalid timestamp format: {post['create_at']}")

    # Check if message is empty
    if "message" in post and not post["message"].strip():
        errors.append("Empty message content")

    return errors


def validate_direct_channel(direct: Dict) -> List[str]:
    """Validate a direct channel object."""
    errors = []
    required_fields = ["members", "header"]

    # Check required fields
    for field in required_fields:
        if field not in direct:
            errors.append(f"Missing required field '{field}' in direct channel")

    # Check members
    if "members" in direct:
        if not isinstance(direct["members"], list):
            errors.append(f"'members' must be a list, got {type(direct['members'])}")
        elif len(direct["members"]) < 2:
            errors.append(
                f"Direct channel must have at least 2 members, got {len(direct['members'])}"
            )

    return errors


def validate_direct_post(direct_post: Dict) -> List[str]:
    """Validate a direct post object."""
    errors = []
    required_fields = ["user", "message", "create_at", "channel_members"]

    # Check required fields
    for field in required_fields:
        if field not in direct_post:
            errors.append(f"Missing required field '{field}' in direct post")

    # Check channel_members
    if "channel_members" in direct_post:
        if not isinstance(direct_post["channel_members"], list):
            errors.append(
                f"'channel_members' must be a list, got {type(direct_post['channel_members'])}"
            )
        elif len(direct_post["channel_members"]) < 2:
            errors.append(
                f"Direct post must have at least 2 channel members, got {len(direct_post['channel_members'])}"
            )

    # Check timestamp
    if "create_at" in direct_post:
        try:
            timestamp = int(direct_post["create_at"])
            if timestamp < 0:
                errors.append(f"Invalid negative timestamp: {timestamp}")
        except (ValueError, TypeError):
            errors.append(f"Invalid timestamp format: {direct_post['create_at']}")

    return errors


def validate_jsonl_file(filepath: str, verbose: bool = False) -> Tuple[bool, Dict]:
    """
    Validate a Mattermost JSONL import file.

    Args:
        filepath: Path to the JSONL file
        verbose: Whether to print detailed validation information

    Returns:
        Tuple of (is_valid, stats_dict)
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return False, {}

    # Statistics and validation tracking
    stats = {
        "total_lines": 0,
        "valid_lines": 0,
        "invalid_lines": 0,
        "teams": 0,
        "channels": 0,
        "users": 0,
        "posts": 0,
        "direct_channels": 0,
        "direct_posts": 0,
        "unknown_types": 0,
        "errors_by_type": {},
        "error_counts": {},
        "ordering_errors": 0,
        "reference_errors": 0,
    }

    # Track entities for reference validation
    known_teams = set()
    known_channels = {}  # Map channel names to their teams
    known_users = set()

    # Track if we've seen channels before teams or posts before channels/users
    seen_team = False
    seen_channel = False

    is_valid = True

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                stats["total_lines"] += 1

                # Skip comment lines
                if line.strip().startswith("//"):
                    continue

                try:
                    data = json.loads(line.strip())

                    # Check if the object has a type field
                    if "type" not in data:
                        if verbose:
                            print(f"Warning - Line {line_num}: Missing 'type' field")
                        stats["invalid_lines"] += 1
                        stats["error_counts"]["missing_type"] = (
                            stats["error_counts"].get("missing_type", 0) + 1
                        )
                        is_valid = False
                        continue

                    # Validate based on type
                    obj_type = data["type"]
                    errors = []

                    # Check version first
                    if obj_type == "version":
                        if "version" not in data:
                            errors.append("Missing version number in version object")
                        elif not isinstance(data["version"], int):
                            errors.append(
                                f"Version must be an integer, got {type(data['version']).__name__}: {data['version']}"
                            )

                    # Validate team objects
                    elif obj_type == "team":
                        if "team" not in data:
                            errors.append("Missing 'team' field in team object")
                            continue

                        team_data = data["team"]
                        stats["teams"] += 1
                        seen_team = True

                        # Track team name for reference validation
                        if "name" in team_data:
                            known_teams.add(team_data["name"])

                        errors.extend(validate_team(team_data))

                    # Validate channel objects
                    elif obj_type == "channel":
                        if "channel" not in data:
                            errors.append("Missing 'channel' field in channel object")
                            continue

                        channel_data = data["channel"]
                        stats["channels"] += 1
                        seen_channel = True

                        # Check if we've seen teams before channels
                        if not seen_team:
                            errors.append("Channel defined before any team")
                            stats["ordering_errors"] += 1

                        # Check if channel references an existing team
                        if "team" in channel_data and "name" in channel_data:
                            if channel_data["team"] not in known_teams:
                                errors.append(
                                    f"Channel references non-existent team: {channel_data['team']}"
                                )
                                stats["reference_errors"] += 1
                            else:
                                # Track this channel for post validation
                                known_channels[channel_data["name"]] = channel_data[
                                    "team"
                                ]

                        errors.extend(validate_channel(channel_data))

                    # Validate user objects
                    elif obj_type == "user":
                        if "user" not in data:
                            errors.append("Missing 'user' field in user object")
                            continue

                        user_data = data["user"]
                        stats["users"] += 1

                        # Track username for reference validation
                        if "username" in user_data:
                            known_users.add(user_data["username"])

                        errors.extend(validate_user(user_data))

                    # Validate post objects
                    elif obj_type == "post":
                        if "post" not in data:
                            errors.append("Missing 'post' field in post object")
                            continue

                        post_data = data["post"]
                        stats["posts"] += 1

                        # Check references
                        if "team" in post_data:
                            if post_data["team"] not in known_teams:
                                errors.append(
                                    f"Post references non-existent team: {post_data['team']}"
                                )
                                stats["reference_errors"] += 1

                        if "channel" in post_data:
                            if post_data["channel"] not in known_channels:
                                errors.append(
                                    f"Post references non-existent channel: {post_data['channel']}"
                                )
                                stats["reference_errors"] += 1
                            elif post_data.get("team") != known_channels.get(
                                post_data["channel"]
                            ):
                                errors.append(
                                    f"Post references channel '{post_data['channel']}' with incorrect team '{post_data['team']}'"
                                )
                                stats["reference_errors"] += 1

                        if "user" in post_data:
                            if post_data["user"] not in known_users:
                                errors.append(
                                    f"Post references non-existent user: {post_data['user']}"
                                )
                                stats["reference_errors"] += 1

                        errors.extend(validate_post(post_data))

                    # Validate direct channel objects
                    elif obj_type == "direct_channel":
                        if "direct_channel" not in data:
                            errors.append(
                                "Missing 'direct_channel' field in direct_channel object"
                            )
                            continue

                        direct_data = data["direct_channel"]
                        stats["direct_channels"] += 1

                        # Check if direct channel members exist
                        if "members" in direct_data:
                            for member in direct_data["members"]:
                                if member not in known_users:
                                    errors.append(
                                        f"Direct channel references non-existent user: {member}"
                                    )
                                    stats["reference_errors"] += 1

                        errors.extend(validate_direct_channel(direct_data))

                    # Validate direct post objects
                    elif obj_type == "direct_post":
                        if "direct_post" not in data:
                            errors.append(
                                "Missing 'direct_post' field in direct_post object"
                            )
                            continue

                        direct_post_data = data["direct_post"]
                        stats["direct_posts"] += 1

                        # Check user reference
                        if (
                            "user" in direct_post_data
                            and direct_post_data["user"] not in known_users
                        ):
                            errors.append(
                                f"Direct post references non-existent user: {direct_post_data['user']}"
                            )
                            stats["reference_errors"] += 1

                        # Check channel members
                        if "channel_members" in direct_post_data:
                            for member in direct_post_data["channel_members"]:
                                if member not in known_users:
                                    errors.append(
                                        f"Direct post references non-existent user in channel_members: {member}"
                                    )
                                    stats["reference_errors"] += 1

                        errors.extend(validate_direct_post(direct_post_data))

                    else:
                        stats["unknown_types"] += 1
                        errors = [f"Unknown object type: {obj_type}"]

                    if errors:
                        if verbose:
                            for error in errors:
                                print(f"Warning - Line {line_num}: {error}")
                        stats["invalid_lines"] += 1

                        # Track errors by type
                        if obj_type not in stats["errors_by_type"]:
                            stats["errors_by_type"][obj_type] = []
                        stats["errors_by_type"][obj_type].extend(errors)

                        # Count error occurrences
                        for error in errors:
                            stats["error_counts"][error] = (
                                stats["error_counts"].get(error, 0) + 1
                            )

                        is_valid = False
                    else:
                        stats["valid_lines"] += 1

                except json.JSONDecodeError as e:
                    if verbose:
                        print(f"Warning - Line {line_num}: Invalid JSON - {str(e)}")
                    stats["invalid_lines"] += 1
                    error_msg = f"Invalid JSON: {str(e)}"
                    stats["error_counts"][error_msg] = (
                        stats["error_counts"].get(error_msg, 0) + 1
                    )
                    is_valid = False

                except Exception as e:
                    if verbose:
                        print(f"Warning - Line {line_num}: Unexpected error - {str(e)}")
                    stats["invalid_lines"] += 1
                    error_msg = f"Unexpected error: {str(e)}"
                    stats["error_counts"][error_msg] = (
                        stats["error_counts"].get(error_msg, 0) + 1
                    )
                    is_valid = False

    except Exception as e:
        print(f"Error reading file: {str(e)}")
        return False, stats

    return is_valid, stats


def print_summary(stats: Dict):
    """Print a summary of the validation statistics."""
    print("=== Validation Summary ===")
    print(f"Total lines: {stats['total_lines']}")
    print(f"Valid lines: {stats['valid_lines']}")
    print(f"Invalid lines: {stats['invalid_lines']}")
    print()
    print("=== Object Counts ===")
    print(f"Teams: {stats['teams']}")
    print(f"Channels: {stats['channels']}")
    print(f"Users: {stats['users']}")
    print(f"Posts: {stats['posts']}")
    print(f"Direct Channels: {stats['direct_channels']}")
    print(f"Direct Posts: {stats['direct_posts']}")
    print(f"Unknown Types: {stats['unknown_types']}")

    if stats["invalid_lines"] > 0:
        print()
        print("=== Top 10 Most Common Errors ===")
        sorted_errors = sorted(
            stats["error_counts"].items(), key=lambda x: x[1], reverse=True
        )
        for error, count in sorted_errors[:10]:
            print(f"{count} occurrences: {error}")


def write_report(filepath: str, is_valid: bool, stats: Dict):
    """Write a validation report to a file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=== Mattermost Import Validation Report ===\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Overall validity: {'Valid' if is_valid else 'Invalid'}\n\n")

        f.write("=== Validation Summary ===\n")
        f.write(f"Total lines: {stats['total_lines']}\n")
        f.write(f"Valid lines: {stats['valid_lines']}\n")
        f.write(f"Invalid lines: {stats['invalid_lines']}\n\n")

        f.write("=== Object Counts ===\n")
        f.write(f"Teams: {stats['teams']}\n")
        f.write(f"Channels: {stats['channels']}\n")
        f.write(f"Users: {stats['users']}\n")
        f.write(f"Posts: {stats['posts']}\n")
        f.write(f"Direct Channels: {stats['direct_channels']}\n")
        f.write(f"Direct Posts: {stats['direct_posts']}\n")
        f.write(f"Unknown Types: {stats['unknown_types']}\n\n")

        if stats["invalid_lines"] > 0:
            f.write("=== All Errors ===\n")
            for obj_type, errors in stats["errors_by_type"].items():
                f.write(f"\n{obj_type.upper()} ERRORS:\n")
                for error in errors:
                    f.write(f"- {error}\n")

            f.write("\n=== Error Counts ===\n")
            sorted_errors = sorted(
                stats["error_counts"].items(), key=lambda x: x[1], reverse=True
            )
            for error, count in sorted_errors:
                f.write(f"{count} occurrences: {error}\n")


def validate_all_mm_files(fbase: str):
    failed = []
    passed = []
    for fname in os.listdir(fbase):
        if fname.endswith(".jsonl") and "mattermost" in fname:
            print(f"Validating Mattermost import file: {fname}")
            is_valid, stats = validate_jsonl_file(
                os.path.join(fbase, fname), verbose=True
            )


def get_env_files(task) -> List[Dict]:
    task_config = task.get_task_config()
    return task_config["env_files"]


if __name__ == "__main__":

    from drbench import task_loader, get_data_path

    tasks = task_loader.get_tasks_from_subset("snow_v2")
    env_files = []
    for task in tasks:
        env_files.extend([get_data_path(f["source"]) for f in get_env_files(task)])
    env_files = list(set(env_files))

    failed = []
    passed = []
    for fname in env_files:
        if fname.endswith(".jsonl") and "mattermost" in fname:
            print(f"Validating Mattermost import file: {fname}")
            is_valid, stats = validate_jsonl_file(fname, verbose=True)
            name = os.path.basename(fname)
            if is_valid:
                # print(f"✅ {name} is a valid Mattermost import file")
                passed.append(name)
            else:
                print(f"❌ {name} contains validation errors")
                # print_summary(stats)
                failed.append(name)
                print_summary(stats)
                print()
    assert len(failed) == 0
    print(f"Failed: {len(failed)}/{len(passed) + len(failed)}")
    print("failed files:")
    for f in failed:
        print(f)
    print()

    # write_report(fname, is_valid, stats)
    # print(f"Detailed report written to: {fname}")


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def get_timestamp() -> str:
    from datetime import datetime, timezone, timedelta

    return (
        datetime.now(timezone.utc)
        .astimezone(timezone(timedelta(hours=-7)))
        .strftime("%Y-%m-%d %H:%M")
    )


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)
    print(f"\nSaved to {path}\n")


def print_dict(dict):
    print("\n")
    for k in dict:
        print(f"{k}:\n   {dict[k]}\n")
    print("--------------------------------\n")


def print_list(list):
    print("\n")
    for i, item in enumerate(list):
        print(f"ITEM {i+1}:")
        for k in item:
            print(f"{k}: {item[k]}")
        print("--------------------------------\n")


from typing import Dict, Any, List
import json
import re


def extract_json_from_response(response: str) -> List[Dict[str, Any]]:
    """Extract JSON from AI response text"""
    import re

    # Try to find JSON array or object
    json_match = re.search(r"(\[.*\]|\{.*\})", response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try parsing the entire response
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        raise ValueError("Could not extract valid JSON from response")


# Helper: format persona context
def format_persona_context(persona):
    if not persona:
        return ""
    return f"- Name: {persona.get('name', 'N/A')}\n- Role: {persona.get('role', 'N/A')}\n- Department: {persona.get('department', 'N/A')}\n- Seniority: {persona.get('seniority', 'N/A')}\n- Responsibilities: {persona.get('responsibilities', 'N/A')}"


# Helper: format internal insights context
def format_insights_context(insights):
    if not insights:
        return "None"
    return "\n".join([f"- {insight.get('insight', '')}" for insight in insights])


# Helper: format external insights context
def format_external_context(insights):
    if not insights:
        return "None"
    return "\n".join([f"- {insight.get('insight', '')}" for insight in insights])
