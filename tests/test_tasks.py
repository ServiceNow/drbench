import json
from pathlib import Path
from unittest.mock import mock_open, patch
import pandas as pd
import os

import pytest

from drbench.task_loader import get_data_path, get_tasks_df, get_task_from_id


class TestTasks:
    """Test cases for the get_task function."""

    def _check_filetype_counts(self, task_id, info_data, env_data):
        """Check that filetype counts in info.json match those in env.json"""

        # Count filetypes in info.json
        info_counts = {}
        for file_entry in info_data.get("files", []):
            filetype = file_entry.get("filetype", "unknown")
            file_type = file_entry.get("type", "unknown")  # supporting/distractor
            key = (filetype, file_type)
            info_counts[key] = info_counts.get(key, 0) + 1

        # Count filetypes in env.json by extracting from source paths
        env_counts = {}
        for env_file_entry in env_data.get("env_files", []):
            source_path = env_file_entry.get("source", "")
            qa_type = env_file_entry.get("qa_type", "unknown")

            # Map qa_type to file type
            file_type_mapping = {"insight": "supporting", "distractor": "distractor"}
            file_type = file_type_mapping.get(qa_type, qa_type)

            # Extract filetype from source path
            if source_path:
                # Get the file extension from the source path
                source_file = Path(source_path)
                filetype = source_file.suffix.lstrip(".").lower()

                # Handle special cases for jsonl files
                if filetype == "jsonl":
                    # Check if it's email or chat based on path or app field
                    app = env_file_entry.get("app", "")
                    if "roundcube" in source_path.lower() or app == "email":
                        filetype = "email"
                    elif "mattermost" in source_path.lower() or app == "mattermost":
                        filetype = "chat"

                key = (filetype, file_type)
                env_counts[key] = env_counts.get(key, 0) + 1

        # Compare counts
        all_keys = set(info_counts.keys()) | set(env_counts.keys())
        mismatches = []

        for key in all_keys:
            info_count = info_counts.get(key, 0)
            env_count = env_counts.get(key, 0)

            if info_count != env_count:
                filetype, file_type = key
                mismatches.append(
                    {"filetype": filetype, "type": file_type, "info_count": info_count, "env_count": env_count}
                )

        if mismatches:
            print(f"\nFiletype count mismatches for task {task_id}:")
            for mismatch in mismatches:
                print(
                    f"  {mismatch['filetype']} ({mismatch['type']}): "
                    f"info.json={mismatch['info_count']}, "
                    f"env.json={mismatch['env_count']}"
                )

        return mismatches

    def test_all_files_exist(self):
        """Test that the id in the json file matches the get_id function."""
        df = get_tasks_df()
        for task_id in df["task_id"]:
            path = get_data_path(f"drbench/data/tasks/{task_id}")
            assert Path(path).exists(), f"task {task_id} not found in {path}"

        # make sure each task has config/
        for task_id in list(df["task_id"]) + ["SANITY0"]:
            task = get_task_from_id(task_id)
            assert isinstance(task.task_config, dict), f"task config not found for task {task_id}"
            assert isinstance(task.eval_config, dict), f"eval config not found for task {task_id}"
            assert isinstance(task.env_config, dict), f"env config not found for task {task_id}"

            path = Path(get_data_path(f"drbench/data/tasks/{task_id}"))
            assert path.exists(), f"task {task_id} not found in {path}"
            assert (path / "config" / "task.json").exists(), f"config file not found for task {task_id}"
            assert (path / "config" / "eval.json").exists(), f"eval file not found for task {task_id}"
            assert (path / "config" / "env.json").exists(), f"env file not found for task {task_id}"

            # get task config and get task_id from task config
            with open(path / "config" / "task.json", "r") as f:
                task_config = json.load(f)
            task_id_from_config = task_config["task_id"]
            task_name = task_config["name"]
            assert task_id_from_config == task_id, f"task_id in config file does not match task_id in path {path}"
            assert task_name == task_id, f"task_name in config file does not match task_id in path {path}"

            # Check that all source files in env.json exist
            env_file = path / "config" / "env.json"
            with open(env_file, "r") as f:
                env_data = json.load(f)

            for env_file_entry in env_data.get("env_files", []):
                source_path = env_file_entry.get("source")
                if source_path:
                    full_source_path = Path(get_data_path(source_path))
                    assert full_source_path.exists(), f"Source file not found for task {task_id}: {source_path}"

            # Check that the number of files in env.json matches info.json
            info_file = path / "info.json"
            if info_file.exists():
                with open(info_file, "r") as f:
                    info_data = json.load(f)

                expected_file_count = len(info_data.get("files", []))
                actual_file_count = len(env_data.get("env_files", []))
                if expected_file_count != actual_file_count:
                    print(
                        "task",
                        task_id,
                        "file count mismatch",
                        expected_file_count,
                        actual_file_count,
                    )

                # Check filetype counts match between info.json and env.json
                self._check_filetype_counts(task_id, info_data, env_data)


if __name__ == "__main__":
    test = TestTasks()
    test.test_all_files_exist()
