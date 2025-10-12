from typing import Any, Dict, Union

from omegaconf import OmegaConf


class ContainerManager:
    """
    Base class for container managers.
    Defines the interface that all container manager implementations should follow.
    """

    def __init__(self, config: Union[Dict[str, Any], OmegaConf, None] = None, **kwargs):
        """
        Initialize the container manager with configuration.

        Args:
            config: Configuration dict or OmegaConf object
            **kwargs: Additional parameters to override config
        """
        self.config = config
        self.container = None

    def start_container(self) -> str:
        """
        Start a container from the specified image.

        Returns:
            The container ID

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement start_container()")

    def stop_container(self) -> bool:
        """
        Stop the currently running container.

        Returns:
            True if successful

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement stop_container()")

    def delete_container(self) -> bool:
        """
        Remove the current container.

        Returns:
            True if successful

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement delete_container()")

    def reset_container(self) -> str:
        """
        Reset the container by stopping, removing and starting a new one.

        Returns:
            The new container ID

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement reset_container()")

    def get_logs(self, lines=50) -> str:
        """
        Get the container logs.

        Args:
            lines: Number of lines to retrieve

        Returns:
            Container logs as string

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement get_logs()")

    def get_status(self) -> dict:
        """
        Get the current status of the container.

        Returns:
            Dictionary with container status information

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement get_status()")

    def is_healthy(self) -> bool:
        """
        Check if the container is running and healthy.

        Returns:
            True if container is healthy, False otherwise

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement is_healthy()")

    def copy_file_to_container(self, src: str, dest: str) -> None:
        """
        Copy a file from host to container.

        Args:
            src: Source file path on host
            dest: Destination file path in container

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement copy_file_to_container()")

    def copy_dir_to_container(self, src: str, dest: str) -> None:
        """
        Copy a directory from host to container.

        Args:
            src: Source directory path on host
            dest: Destination directory path in container

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement copy_dir_to_container()")

    def run_command(self, command: str, log_to_container: bool = False) -> str:
        """
        Run a command in the container.

        Args:
            command: Command to run
            log_to_container: Whether to log the command output to the container logs

        Returns:
            Command output

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement run_command()")

    def get_host_port(self, port: int) -> int:
        """
        Get the host port mapped to a container port.

        Args:
            port: Container port

        Returns:
            Host port

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement get_host_port()")

    def check_and_kill_ports(self, ports):
        """
        Check for containers using specified ports and optionally kill them.

        Args:
            ports: List of ports to check

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement check_and_kill_ports()")
