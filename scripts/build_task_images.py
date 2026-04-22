"""Build one Docker image per DRBench task.

Starts the base container, loads the task via add_task(), commits the container
state as a named image (drbench-services:DR0042), then cleans up.

Result: per-task images that start in ~8s instead of ~45s, since all services
are already in a loaded, healthy state.

Usage:
    # Build task images using the default local base image
    uv run python scripts/build_task_images.py --subset val
    uv run python scripts/build_task_images.py --all
    uv run python scripts/build_task_images.py --task-ids DR0001 DR0002
    uv run python scripts/build_task_images.py --subset val --dry-run
    uv run python scripts/build_task_images.py --subset val --force

    # Build task images on top of a custom base image (e.g. a custom base)
    uv run python scripts/build_task_images.py --base-image myregistry/drbench-services-custom:latest --subset val

    # Build + push to a registry (single architecture)
    uv run python scripts/build_task_images.py --all --push --registry ghcr.io/servicenow

    # Multi-arch workflow (run steps 1-2 on each architecture, step 3 once):
    #
    # Step 1 — on arm64 machine:
    #   uv run python scripts/build_task_images.py --all --push --registry ghcr.io/servicenow --arch-tag arm64
    #
    # Step 2 — on amd64 machine:
    #   uv run python scripts/build_task_images.py --all --push --registry ghcr.io/servicenow --arch-tag amd64
    #
    # Step 3 — create multi-arch manifests (run once, from either machine):
    #   uv run python scripts/build_task_images.py --all --create-manifests --registry ghcr.io/servicenow
"""

import argparse
import logging
import subprocess
from pathlib import Path

import docker

from drbench import config as drbench_config
from drbench.task_loader import get_tasks_from_subset, get_all_tasks

logger = logging.getLogger(__name__)

DEFAULT_IMAGE_PREFIX = drbench_config.DRBENCH_DOCKER_IMAGE  # e.g. "drbench-services"
DEFAULT_BASE_IMAGE = f"{DEFAULT_IMAGE_PREFIX}:{drbench_config.DRBENCH_DOCKER_TAG}"


def build_task_image(
    task,
    docker_client: docker.DockerClient,
    base_image: str,
    image_prefix: str,
    force: bool = False,
) -> str:
    """
    Load a task into a fresh container and commit it as a named image.

    Args:
        task: Task object with get_id() and get_path() methods.
        docker_client: Docker client instance.
        base_image: Full base image reference (e.g. "drbench-services:latest"
            or "myregistry/drbench-services-custom:latest").
        image_prefix: Repository name for the committed image (e.g.
            "drbench-services" or "myregistry/drbench-services-custom").
        force: Rebuild even if the image already exists.

    Returns the image tag, e.g. "drbench-services:DR0001".
    """
    from drbench.drbench_enterprise_space import DrBenchEnterpriseSearchSpace

    task_id = task.get_id()
    image_tag = f"{image_prefix}:{task_id}"

    if not force:
        try:
            docker_client.images.get(image_tag)
            logger.info(f"[{task_id}] Image {image_tag} already exists. Skipping (use --force to rebuild).")
            return image_tag
        except docker.errors.ImageNotFound:
            pass

    logger.info(f"[{task_id}] Building image {image_tag} from base {base_image}...")

    space = DrBenchEnterpriseSearchSpace(
        task=Path(task.get_path()),
        config={"image": base_image},
        auto_ports=True,
    )
    try:
        space.start()

        container = docker_client.containers.get(space.container_id)
        image = container.commit(
            repository=image_prefix,
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


def push_task_image(
    task_id: str,
    docker_client: docker.DockerClient,
    image_prefix: str,
    registry: str,
    arch_tag: str | None = None,
) -> str:
    """Tag and push a task image to a registry.

    Args:
        task_id: e.g. "DR0001"
        docker_client: Docker client instance.
        image_prefix: Local repository name (e.g. "drbench-services").
        registry: Registry prefix (e.g. "ghcr.io/servicenow").
        arch_tag: Optional architecture suffix. If set, the remote tag becomes
            ``<registry>/<prefix>:<task_id>-<arch_tag>`` (e.g. DR0001-arm64).
            Used for multi-arch workflows where each arch is pushed separately
            before creating a manifest.

    Returns the remote tag that was pushed.
    """
    local_tag = f"{image_prefix}:{task_id}"
    remote_repo = f"{registry}/{image_prefix}"
    remote_suffix = f"{task_id}-{arch_tag}" if arch_tag else task_id
    remote_tag = f"{remote_repo}:{remote_suffix}"

    image = docker_client.images.get(local_tag)
    image.tag(remote_repo, tag=remote_suffix)
    logger.info(f"[{task_id}] Pushing {remote_tag}...")
    docker_client.images.push(remote_repo, tag=remote_suffix)
    logger.info(f"[{task_id}] Pushed {remote_tag}")
    return remote_tag


def create_multiarch_manifest(
    task_id: str,
    image_prefix: str,
    registry: str,
    arch_tags: list[str],
) -> None:
    """Create and push a multi-arch manifest for a task image.

    Combines arch-specific tags (e.g. DR0001-arm64, DR0001-amd64) into
    a single manifest list at the canonical tag (e.g. DR0001).

    Requires ``docker manifest`` CLI support (Docker Desktop has this by default).
    """
    remote_repo = f"{registry}/{image_prefix}"
    manifest_tag = f"{remote_repo}:{task_id}"
    source_tags = [f"{remote_repo}:{task_id}-{arch}" for arch in arch_tags]

    logger.info(f"[{task_id}] Creating manifest {manifest_tag} from {arch_tags}")

    # Remove any existing local manifest (docker manifest create fails if it exists)
    subprocess.run(
        ["docker", "manifest", "rm", manifest_tag],
        capture_output=True,
    )

    subprocess.run(
        ["docker", "manifest", "create", manifest_tag, *source_tags],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["docker", "manifest", "push", manifest_tag],
        check=True,
        capture_output=True,
        text=True,
    )
    logger.info(f"[{task_id}] Manifest pushed: {manifest_tag}")


def get_tasks(args):
    """Resolve task list from CLI arguments."""
    if args.task_ids:
        from drbench.task_loader import get_task_from_id
        return [get_task_from_id(tid) for tid in args.task_ids]
    elif args.all:
        return get_all_tasks()
    else:
        return get_tasks_from_subset(args.subset)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Build per-task DRBench Docker images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Task selection
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--subset", default="val", help="Task subset to build images for (default: val)")
    group.add_argument("--all", action="store_true", help="Build images for all tasks")
    parser.add_argument("--task-ids", nargs="*", metavar="TASK_ID", help="Build only specific task IDs")

    # Build options
    parser.add_argument(
        "--base-image",
        default=None,
        help="Base image to start containers from (default: drbench-services:latest).",
    )
    parser.add_argument("--force", action="store_true", help="Rebuild even if image already exists")
    parser.add_argument("--dry-run", action="store_true", help="List tasks/images without building")

    # Push options
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push each task image to the registry after building. Requires --registry.",
    )
    parser.add_argument(
        "--registry",
        default=None,
        help="Registry prefix (e.g. ghcr.io/servicenow).",
    )
    parser.add_argument(
        "--arch-tag",
        default=None,
        help=(
            "Architecture suffix for remote tags (e.g. arm64 or amd64). "
            "Pushes as <registry>/<prefix>:<task_id>-<arch_tag>. "
            "Use with --create-manifests to combine architectures."
        ),
    )

    # Manifest creation (multi-arch)
    parser.add_argument(
        "--create-manifests",
        action="store_true",
        help=(
            "Create multi-arch manifests combining arch-specific tags. "
            "Expects <task_id>-arm64 and <task_id>-amd64 to already exist in the registry. "
            "Requires --registry."
        ),
    )
    parser.add_argument(
        "--architectures",
        nargs="*",
        default=["arm64", "amd64"],
        help="Architectures to include in manifests (default: arm64 amd64).",
    )

    args = parser.parse_args()

    if args.push and not args.registry:
        parser.error("--push requires --registry")
    if args.create_manifests and not args.registry:
        parser.error("--create-manifests requires --registry")
    if args.arch_tag and not args.push:
        parser.error("--arch-tag requires --push")

    docker_client = docker.from_env()

    # Determine base image and derive the image prefix (repository name without tag)
    base_image = args.base_image or DEFAULT_BASE_IMAGE
    image_prefix = base_image.rsplit(":", 1)[0] if ":" in base_image else base_image

    tasks = get_tasks(args)
    logger.info(f"Processing {len(tasks)} tasks (base: {base_image})...")

    # --- Manifest-only mode ---
    if args.create_manifests:
        ok, failed = [], []
        for task in tasks:
            task_id = task.get_id()
            try:
                create_multiarch_manifest(task_id, image_prefix, args.registry, args.architectures)
                ok.append(task_id)
            except Exception as e:
                logger.error(f"[{task_id}] Manifest failed: {e}")
                failed.append(task_id)
        print(f"\n=== Manifest Summary ===")
        print(f"  Registry: {args.registry}")
        print(f"  Architectures: {args.architectures}")
        print(f"  Created: {len(ok)}")
        print(f"  Failed:  {len(failed)}")
        if failed:
            print(f"  Failed task IDs: {failed}")
        return

    # --- Dry run ---
    if args.dry_run:
        print(f"\nBase image: {base_image}")
        suffix = f" (arch: {args.arch_tag})" if args.arch_tag else ""
        print(f"Registry: {args.registry or '(local only)'}{suffix}")
        print(f"{'Task ID':<12} {'Image':<60} {'Status'}")
        print("-" * 80)
        for task in tasks:
            tag = f"{image_prefix}:{task.get_id()}"
            try:
                docker_client.images.get(tag)
                status = "EXISTS"
            except docker.errors.ImageNotFound:
                status = "MISSING"
            print(f"{task.get_id():<12} {tag:<60} {status}")
        return

    # --- Build (and optionally push) ---
    results: dict[str, list] = {"success": [], "failed": [], "pushed": [], "push_failed": []}
    for task in tasks:
        task_id = task.get_id()
        try:
            tag = build_task_image(task, docker_client, base_image, image_prefix, force=args.force)
            results["success"].append(tag)

            if args.push:
                try:
                    remote = push_task_image(task_id, docker_client, image_prefix, args.registry, args.arch_tag)
                    results["pushed"].append(remote)
                except Exception as push_err:
                    logger.error(f"[{task_id}] Push failed: {push_err}")
                    results["push_failed"].append(task_id)

        except Exception as e:
            logger.error(f"[{task_id}] FAILED: {e}")
            results["failed"].append(task_id)

    print(f"\n=== Build Summary ===")
    print(f"  Base image: {base_image}")
    print(f"  Built:   {len(results['success'])}")
    print(f"  Failed:  {len(results['failed'])}")
    if results["failed"]:
        print(f"  Failed task IDs: {results['failed']}")
    if args.push:
        print(f"  Pushed:  {len(results['pushed'])}")
        if results["push_failed"]:
            print(f"  Push failed: {results['push_failed']}")


if __name__ == "__main__":
    main()
