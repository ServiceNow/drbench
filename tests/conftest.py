"""Pytest configuration and shared fixtures for DRBench tests."""

import docker
import pytest


@pytest.fixture(autouse=True, scope="session")
def cleanup_drbench_containers():
    """Kill any drbench-services containers left running after the test session.

    Runs once at the end of the full session. Catches leaked containers from
    tests that errored before task.close() could be called.
    """
    yield  # let the whole session run

    try:
        client = docker.from_env()
        leaked = [
            c for c in client.containers.list()
            if c.name.startswith("drbench-services-")
        ]
        for container in leaked:
            try:
                container.stop(timeout=5)
                container.remove()
            except Exception:
                pass
        if leaked:
            print(f"\n[conftest] Cleaned up {len(leaked)} leaked drbench container(s).")
    except Exception:
        pass
