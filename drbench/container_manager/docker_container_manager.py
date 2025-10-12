import io
import logging
import os
import sys
import tarfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Union

import docker
from docker.errors import DockerException
from omegaconf import OmegaConf

from drbench import config as drbench_config
from drbench.container_manager.base import ContainerManager

logger = logging.getLogger(__name__)

# Path to default configuration files
_CONF_DIR = Path(__file__).parent.parent.parent / "conf"


class DockerContainerManager(ContainerManager):
    """
    A class to manage Docker containers for the enterprise search space.
    Handles initialization, running, stopping, deleting, and resetting containers.
    """

    def __init__(self, config: Union[Dict[str, Any], OmegaConf, None] = None, **kwargs):
        """
        Initialize the Docker handler with a given configuration.

        Args:
            config: Configuration dict or OmegaConf object containing configuration
            **kwargs: Additional parameters to override config

        Raises:
            DockerException: If unable to connect to Docker daemon
        """
        # Initialize parent class
        super().__init__(config, **kwargs)

        # Convert dict to OmegaConf if needed, or load default config
        if config is None:
            config = self._load_default_config()
        elif isinstance(config, dict):
            config = OmegaConf.create(config)

        # Override with kwargs
        for key, value in kwargs.items():
            OmegaConf.update(config, key, value)

        self.config = config
        # Use config values from centralized config, fallback to config dict if provided
        default_image = f"{drbench_config.DRBENCH_DOCKER_IMAGE}:{drbench_config.DRBENCH_DOCKER_TAG}"
        self.image = config.get("image", default_image)
        self.client = None
        self.container = None

        try:
            self.client = docker.from_env()
            logger.info("Successfully connected to Docker daemon")
        except DockerException as e:
            logger.error(f"Failed to connect to Docker daemon: {e}")
            raise

        self._prepare_docker_params()

    def _load_default_config(self) -> OmegaConf:
        """Load default configuration from YAML files when no config is provided."""
        try:
            # Load default container configuration
            container_config_path = _CONF_DIR / "container" / "default.yaml"
            if not container_config_path.exists():
                logger.warning(
                    f"Default container config not found at {container_config_path}, using minimal defaults"
                )
                return self._get_minimal_defaults()

            container_config = OmegaConf.load(container_config_path)

            # Load default apps configuration (since container/default.yaml references it)
            apps_config_path = _CONF_DIR / "apps" / "default.yaml"
            if apps_config_path.exists():
                apps_config = OmegaConf.load(apps_config_path)
                # Merge apps into container config
                container_config.apps = apps_config
            else:
                logger.warning(f"Default apps config not found at {apps_config_path}")
                container_config.apps = []

            logger.info("Loaded default configuration from YAML files")
            return container_config

        except Exception as e:
            logger.warning(
                f"Failed to load default YAML configuration: {e}, using minimal defaults"
            )
            return self._get_minimal_defaults()

    def _get_minimal_defaults(self) -> OmegaConf:
        """Get minimal hardcoded defaults as fallback."""
        default_image = f"{drbench_config.DRBENCH_DOCKER_IMAGE}:{drbench_config.DRBENCH_DOCKER_TAG}"
        return OmegaConf.create(
            {
                "type": "docker",
                "host_url": "http://localhost",
                "image": default_image,
                "container_name": "drbench-services",
                "hostname": "drbench.com",
                "network": None,
                "volumes": None,
                "apps": [
                    {"name": "drbench", "port": 80, "host_port": 8080},
                    {
                        "name": "health",
                        "port": 8099,
                        "host_port": 8099,
                        "endpoint": "/health",
                    },
                ],
                "environment": {},
                "restart_policy": {"Name": "on-failure", "MaximumRetryCount": 3},
                "platform": None,
            }
        )

    def _prepare_docker_params(self):
        """Prepare Docker parameters from the config"""
        default_image = f"{drbench_config.DRBENCH_DOCKER_IMAGE}:{drbench_config.DRBENCH_DOCKER_TAG}"
        self.docker_params = {
            "image": self.config.get("image", default_image),
            "detach": True,
        }

        if self.config.get("container_name"):
            self.docker_params["name"] = self.config.get("container_name")

        if self.config.get("hostname"):
            self.docker_params["hostname"] = self.config.get("hostname")

        if self.config.get("network"):
            self.docker_params["network"] = self.config.get("network")

        if self.config.get("restart_policy"):
            self.docker_params["restart_policy"] = OmegaConf.to_container(
                self.config.restart_policy
            )

        if self.config.get("platform"):
            self.docker_params["platform"] = self.config.get("platform")

        if self.config.get("environment"):
            self.docker_params["environment"] = OmegaConf.to_container(
                self.config.environment
            )

        if self.config.get("volumes"):
            self.docker_params["volumes"] = OmegaConf.to_container(self.config.volumes)

        ports = {}
        if self.config.get("apps"):
            apps = OmegaConf.to_container(self.config.get("apps"))
            for app in apps:
                host_port = (
                    app["host_port"]
                    if app.get("host_port") is not None
                    else app["port"]
                )
                ports[f"{app['port']}/tcp"] = host_port

        if ports:
            self.docker_params["ports"] = ports

    def start_container(self) -> str:
        """
        Start a container from the specified image.

        Returns:
            The container ID

        Raises:
            RuntimeError: If Docker client is not initialized
            DockerException: If container fails to start due to Docker issues
            Exception: If container starts but is not in running state
        """
        if not self.client:
            error_msg = "Docker client not initialized. Cannot start container."
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        if self.container and self.container.status == "running":
            warn_msg = (
                "Container already running. Reset or stop it before starting a new one."
            )
            logger.warning(warn_msg)
            return self.container.id

        try:
            logger.info(f"Starting container with image {self.image}")
            self.container = self.client.containers.run(**self.docker_params)

            # Wait briefly and check container status
            time.sleep(1)
            self.container.reload()

            if self.container.status != "running":
                error_msg = f"Container started but status is {self.container.status}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            logger.info(f"Container started successfully with ID: {self.container.id}")
            return self.container.id

        except DockerException as e:
            logger.error(f"Docker error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error starting container: {e}")
            raise

    def stop_container(self) -> bool:
        """
        Stop the currently running container.

        Returns:
            True if successful

        Raises:
            RuntimeError: If no container to stop
            Exception: If any error occurs during stopping
        """
        if not self.container:
            error_msg = "No container to stop"
            logger.warning(error_msg)
            raise RuntimeError(error_msg)

        try:
            logger.info(f"Stopping container {self.container.id}")
            self.container.stop()
            logger.info("Container stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Error stopping container: {e}")
            raise

    def delete_container(self) -> bool:
        """
        Remove the current container.

        Returns:
            True if successful

        Raises:
            RuntimeError: If no container to delete
            Exception: If any error occurs during deletion
        """
        if not self.container:
            error_msg = "No container to delete"
            logger.warning(error_msg)
            raise RuntimeError(error_msg)

        try:
            logger.info(f"Removing container {self.container.id}")
            self.container.remove(force=True)
            self.container = None
            logger.info("Container removed successfully")
            return True
        except Exception as e:
            logger.error(f"Error removing container: {e}")
            raise

    def reset_container(self) -> str:
        """
        Reset the container by stopping, removing and starting a new one.

        Returns:
            The new container ID

        Raises:
            Exception: If any operation during reset fails
        """
        logger.info("Resetting container...")
        try:
            if self.container:
                self.stop_container()
                self.delete_container()
            return self.start_container()
        except Exception as e:
            logger.error(f"Error resetting container: {e}")
            raise

    def get_logs(self, lines=50) -> str:
        """
        Get the container logs.

        Args:
            lines: Number of lines to retrieve

        Returns:
            Container logs as string

        Raises:
            RuntimeError: If no container is running
            Exception: If error retrieving logs
        """
        if not self.container:
            error_msg = "No container running"
            logger.warning(error_msg)
            raise RuntimeError(error_msg)

        try:
            return self.container.logs(tail=lines).decode("utf-8")
        except Exception as e:
            logger.error(f"Error retrieving logs: {e}")
            raise

    def get_status(self) -> dict:
        """
        Get the current status of the container.

        Returns:
            Dictionary with container status information

        Raises:
            RuntimeError: If no container exists
            Exception: If error retrieving status
        """
        if not self.container:
            error_msg = "No container exists"
            logger.warning(error_msg)
            raise RuntimeError(error_msg)

        try:
            self.container.reload()
            status = {
                "id": self.container.id,
                "status": self.container.status,
                "name": self.container.name,
                "image": (
                    self.container.image.tags[0]
                    if self.container.image.tags
                    else self.container.image.id
                ),
                "created": self.container.attrs.get("Created", ""),
                "ports": self.container.attrs.get("NetworkSettings", {}).get(
                    "Ports", {}
                ),
                "apps": [
                    {
                        "name": app["name"],
                        "port": app["port"],
                        "host_port": app.get("host_port"),
                        "endpoint": app.get("endpoint"),
                    }
                    for app in OmegaConf.to_container(self.config.get("apps", []))
                ],
            }
            return status
        except Exception as e:
            logger.error(f"Error getting container status: {e}")
            raise

    def is_healthy(self) -> bool:
        """
        Check if the container is running and healthy.

        Returns:
            True if container is healthy, False otherwise

        Raises:
            RuntimeError: If no container exists
            Exception: If error checking health
        """
        if not self.container:
            error_msg = "No container exists"
            logger.warning(error_msg)
            raise RuntimeError(error_msg)

        try:
            self.container.reload()

            # Check if container has health check
            health_status = (
                self.container.attrs.get("State", {}).get("Health", {}).get("Status")
            )

            if health_status:
                # Container has health check
                return health_status == "healthy"
            else:
                # No health check, just check if running
                return self.container.status == "running"

        except Exception as e:
            logger.error(f"Error checking container health: {e}")
            raise

    def copy_file_to_container(self, src: str, dest: str) -> None:
        """
        Copy a file from host to container.

        Args:
            src: Source file path on host
            dest: Destination file path in container

        Raises:
            RuntimeError: If no container exists
            Exception: If error copying file
        """
        if not self.container:
            error_msg = "No container exists"
            logger.warning(error_msg)
            raise RuntimeError(error_msg)

        try:
            # Create in-memory tarfile
            tarstream = io.BytesIO()
            with tarfile.open(fileobj=tarstream, mode="w") as tar:
                tar.add(src, arcname=os.path.basename(src))

            # Reset stream position to beginning
            tarstream.seek(0)
            data = tarstream.getvalue()

            self.client.api.put_archive(self.container.id, dest, data)
            tarstream.close()

            logger.debug(
                f"File {src} copied to {dest} in container {self.container.id}"
            )
        except Exception as e:
            logger.error(f"Error copying file to container: {e}")
            raise

    def copy_dir_to_container(self, src: str, dest: str) -> None:
        """
        Copy a directory from host to container.

        Args:
            src: Source directory path on host
            dest: Destination directory path in container

        Raises:
            RuntimeError: If no container exists
            Exception: If error copying directory
        """
        if not self.container:
            error_msg = "No container exists"
            logger.warning(error_msg)
            raise RuntimeError(error_msg)

        try:
            self.client.api.put_archive(self.container.id, dest, src)
            logger.debug(
                f"Directory {src} copied to {dest} in container {self.container.id}"
            )
        except Exception as e:
            logger.error(f"Error copying directory to container: {e}")
            raise

    def run_command(self, command: str, log_to_container: bool = False) -> str:
        """
        Run a command in the container.

        Args:
            command: Command to run
            log_to_container: If True, also send output to container logs

        Returns:
            Command output

        Raises:
            RuntimeError: If no container exists
            Exception: If error running command
        """
        if not self.container:
            error_msg = "No container exists"
            logger.warning(error_msg)
            raise RuntimeError(error_msg)

        try:
            if log_to_container:
                # Run command with output redirected to container logs
                command = f'bash -c "{command} > /proc/1/fd/1 2>/proc/1/fd/2"'

            exec_id = self.client.api.exec_create(self.container.id, command)
            output = self.client.api.exec_start(exec_id)
            return output.decode("utf-8")
        except Exception as e:
            logger.error(f"Error running command in container: {e}")
            raise

    def get_host_port(self, port: int) -> int:
        """
        Get the host port mapped to a container port.

        Args:
            port: Container port

        Returns:
            Host port

        Raises:
            RuntimeError: If no container exists
            Exception: If error retrieving host port
        """
        if not self.container:
            error_msg = "No container exists"
            logger.warning(error_msg)
            raise RuntimeError(error_msg)

        try:
            self.container.reload()
            host_port = self.container.ports[f"{port}/tcp"][0]["HostPort"]
            return int(host_port)
        except Exception as e:
            logger.error(f"Error getting host port: {e}")
            raise

    def check_and_kill_ports(self, ports):
        """
        Check for containers using specified ports and optionally kill them.

        Args:
            ports: List of ports to check
        """
        for port in ports:
            logger.debug(f"Checking for containers using port {port}")
            matching_containers = []

            # Get all running containers
            containers = self.client.containers.list()

            # Find containers using the specified port
            for container in containers:
                container_info = self.client.api.inspect_container(container.id)
                port_bindings = (
                    container_info["HostConfig"]["PortBindings"]
                    if "PortBindings" in container_info["HostConfig"]
                    else {}
                )

                # Check port bindings
                found = False
                for container_port, host_bindings in port_bindings.items():
                    for binding in host_bindings:
                        if "HostPort" in binding and binding["HostPort"] == str(port):
                            matching_containers.append(
                                {
                                    "id": container.id[:12],
                                    "name": container.name,
                                    "port_mapping": f"{binding.get('HostIp', '0.0.0.0')}:{binding['HostPort']} -> {container_port}",
                                }
                            )
                            found = True
                            break
                    if found:
                        break

            # Display results
            if not matching_containers:
                logger.debug(f"No containers found using port {port}")
            else:
                header = f"{'CONTAINER ID':<15}{'NAME':<30}{'PORT MAPPING':<30}"
                separator = "-" * 75

                logger.info(f"Found containers using port {port}:")
                logger.info(header)
                logger.info(separator)

                for container in matching_containers:
                    logger.info(
                        f"{container['id']:<15}{container['name']:<30}{container['port_mapping']:<30}"
                    )

                # Ask user if they want to kill the containers
                # Default response
                global response, answer_provided
                response = "y"
                answer_provided = False

                def countdown_input():
                    global response, answer_provided

                    # Print prompt (keeping this as print for interactive user prompt)
                    sys.stdout.write(
                        f"Do you want to kill the container(s) using port {port}? ([y]/n): "
                    )
                    sys.stdout.flush()

                    # Countdown display
                    for i in range(5, 0, -1):
                        if answer_provided:
                            break
                        sys.stdout.write(f"{i}...")
                        sys.stdout.flush()
                        time.sleep(1)

                    if not answer_provided:
                        logger.info("No input received, defaulting to 'y'")
                        answer_provided = True
                        # Default already set earlier

                # Start countdown in separate thread
                t = threading.Thread(target=countdown_input)
                t.daemon = True
                t.start()

                # Use another thread to get user input
                def get_input():
                    global response, answer_provided
                    user_input = sys.stdin.readline().strip()
                    if user_input:
                        response = user_input
                    answer_provided = True

                input_thread = threading.Thread(target=get_input)
                input_thread.daemon = True
                input_thread.start()

                # Wait for either timeout or input
                t.join(6)  # Wait slightly longer than the countdown

                if response.lower() in ["y", "yes"]:
                    for container in matching_containers:
                        container_id = container["id"]
                        logger.info(f"Killing container {container_id}...")
                        try:
                            self.client.containers.get(container_id).kill()
                            logger.info(
                                f"Container {container_id} killed successfully."
                            )
                        except Exception as e:
                            logger.error(f"Error killing container {container_id}: {e}")
                else:
                    logger.warning(
                        f"Container(s) on port {port} left running. This will probably cause a clash with the new container."
                    )

            logger.debug("-" * 40)
