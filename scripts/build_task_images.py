"""Build one Docker image per DRBench task.

Starts the base container, loads the task via add_task(), commits the container
state as a named image (drbench-services:DR0042), then cleans up.

Result: per-task images that start in ~8s instead of ~45s, since all services
are already in a loaded, healthy state.

Usage:
    uv run python scripts/build_task_images.py --subset val
    uv run python scripts/build_task_images.py --all
    uv run python scripts/build_task_images.py --task-ids DR0001 DR0002
    uv run python scripts/build_task_images.py --subset val --dry-run
    uv run python scripts/build_task_images.py --subset val --force
"""

import argparse
import logging
from pathlib import Path

import docker

from drbench import config as drbench_config
from drbench.task_loader import get_tasks_from_subset, get_all_tasks

logger = logging.getLogger(__name__)

DRBENCH_IMAGE_PREFIX = drbench_config.DRBENCH_DOCKER_IMAGE  # e.g. "drbench-services"
DRBENCH_BASE_IMAGE = f"{DRBENCH_IMAGE_PREFIX}:{drbench_config.DRBENCH_DOCKER_TAG}"


def build_task_image(task, docker_client: docker.DockerClient, force: bool = False) -> str:
    """
    Load a task into a fresh container and commit it as a named image.

    Returns the image tag, e.g. "drbench-services:DR0001".
    """
    from drbench.drbench_enterprise_space import DrBenchEnterpriseSearchSpace

    task_id = task.get_id()
    image_tag = f"{DRBENCH_IMAGE_PREFIX}:{task_id}"

    if not force:
        try:
            docker_client.images.get(image_tag)
            logger.info(f"[{task_id}] Image {image_tag} already exists. Skipping (use --force to rebuild).")
            return image_tag
        except docker.errors.ImageNotFound:
            pass

    logger.info(f"[{task_id}] Building image {image_tag}...")

    space = DrBenchEnterpriseSearchSpace(
        task=Path(task.get_path()),
        auto_ports=True,
    )
    try:
        space.start()

        container = docker_client.containers.get(space.container_id)
        image = container.commit(
            repository=DRBENCH_IMAGE_PREFIX,
            tag=task_id,
            message=f"DRBench task {task_id} pre-loaded",
            changes=[f'LABEL drbench.task_id="{task_id}"'],
        )
        logger.info(f"[{task_id}] Committed as {image.tags}")
    finally:
        try:
            space.stop()
            space.delete()
        except Exception as cleanup_err:
            logger.warning(f"[{task_id}] Cleanup error: {cleanup_err}")

    return image_tag


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Build per-task DRBench Docker images")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--subset", default="val", help="Task subset to build images for (default: val)")
    group.add_argument("--all", action="store_true", help="Build images for all tasks")
    parser.add_argument("--task-ids", nargs="*", metavar="TASK_ID", help="Build only specific task IDs")
    parser.add_argument("--force", action="store_true", help="Rebuild even if image already exists")
    parser.add_argument("--dry-run", action="store_true", help="List tasks/images without building")
    args = parser.parse_args()

    docker_client = docker.from_env()

    if args.task_ids:
        from drbench.task_loader import get_task_from_id
        tasks = [get_task_from_id(tid) for tid in args.task_ids]
    elif args.all:
        tasks = get_all_tasks()
    else:
        tasks = get_tasks_from_subset(args.subset)

    logger.info(f"Processing {len(tasks)} tasks...")

    if args.dry_run:
        print(f"\n{'Task ID':<12} {'Image':<40} {'Status'}")
        print("-" * 60)
        for task in tasks:
            tag = f"{DRBENCH_IMAGE_PREFIX}:{task.get_id()}"
            try:
                docker_client.images.get(tag)
                status = "EXISTS"
            except docker.errors.ImageNotFound:
                status = "MISSING"
            print(f"{task.get_id():<12} {tag:<40} {status}")
        return

    results: dict[str, list] = {"success": [], "failed": []}
    for task in tasks:
        try:
            tag = build_task_image(task, docker_client, force=args.force)
            results["success"].append(tag)
        except Exception as e:
            logger.error(f"[{task.get_id()}] FAILED: {e}")
            results["failed"].append(task.get_id())

    print(f"\n=== Build Summary ===")
    print(f"  Success: {len(results['success'])}")
    print(f"  Failed:  {len(results['failed'])}")
    if results["failed"]:
        print(f"  Failed task IDs: {results['failed']}")


if __name__ == "__main__":
    main()
