"""Container Manager Factory for DRBench"""

import logging
from typing import Any, Dict, Union

from omegaconf import OmegaConf

from drbench.container_manager.base import ContainerManager
from drbench.container_manager.docker_container_manager import DockerContainerManager

logger = logging.getLogger(__name__)

# Registry of available container managers
CONTAINER_MANAGERS = {
    "docker": DockerContainerManager,
    # Future: "podman": PodmanContainerManager,
}


class ContainerManagerFactory:
    """Factory class for creating container managers."""

    @staticmethod
    def create_container_manager(config: Union[Dict[str, Any], OmegaConf, None] = None, **kwargs) -> ContainerManager:
        """Create a container manager instance based on the config type."""
        # Get manager type from config, default to docker
        if config is None:
            manager_type = "docker"
        elif isinstance(config, dict):
            manager_type = config.get("type", "docker")
        else:  # OmegaConf
            manager_type = config.get("type", "docker")

        if manager_type not in CONTAINER_MANAGERS:
            available = list(CONTAINER_MANAGERS.keys())
            raise ValueError(f"Unsupported manager: {manager_type}. Available: {available}")

        manager_class = CONTAINER_MANAGERS[manager_type]
        logger.info(f"Creating {manager_type} container manager")
        return manager_class(config=config, **kwargs)

    @staticmethod
    def get_available_managers() -> list:
        """Get list of available container manager types."""
        return list(CONTAINER_MANAGERS.keys())


def create_container_manager(config=None, **kwargs) -> ContainerManager:
    """Convenience function to create a container manager."""
    return ContainerManagerFactory.create_container_manager(config, **kwargs)
