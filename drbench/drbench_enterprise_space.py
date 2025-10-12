import json
import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Union

import requests
from omegaconf import OmegaConf

from drbench import config as drbench_config
from drbench.container_manager.factory import create_container_manager
from drbench.task_loader import get_data_path

# Configure logger
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent

# Default Docker image from centralized config
_DEFAULT_DOCKER_IMAGE = f"{drbench_config.DRBENCH_DOCKER_IMAGE}:{drbench_config.DRBENCH_DOCKER_TAG}"

# Apps that are excluded from credential override (use their default passwords)
_EXCLUDED_CREDENTIAL_APPS = ["vnc", "novnc"]

# Default applications configuration for the DrBench Enterprise Search Space
_DEFAULT_APPS = [
    {
        "name": "drbench",
        "port": 8080,
        "host_port": 8080,
        "description": (
            "Main DrBench application interface providing access to benchmarking tools and datasets. "
            "This is the primary entry point for running benchmarks and accessing the DrBench ecosystem. "
            "Available at the main port when the container is running."
        ),
    },
    {
        "name": "nextcloud",
        "port": 8081,
        "host_port": 8081,
        "credentials": {"username": "admin", "password": "admin_pwd"},
        "description": (
            "File storage and collaboration platform similar to Dropbox or Google Drive. "
            "Provides secure file sharing, document editing, and team collaboration features. "
            "Access your files through the web interface for seamless file management."
        ),
    },
    {
        "name": "mattermost",
        "port": 8082,
        "host_port": 8082,
        "credentials": {"username": "admin@drbench.com", "password": "mm_admin_pwd"},
        "description": (
            "Team communication and messaging platform similar to Slack or Microsoft Teams. "
            "Enables real-time chat, file sharing, and team coordination capabilities. "
            "Join conversations and collaborate with your team through the web interface."
        ),
    },
    {
        "name": "vnc",
        "port": 5901,
        "host_port": 5901,
        "credentials": {"username": "", "password": "vnc_pwd"},
        "description": (
            "Virtual Network Computing server providing remote desktop access to the container. "
            "Allows full graphical interface control of the containerized environment. "
            "Connect using any VNC client for direct desktop access to the container."
        ),
    },
    {
        "name": "novnc",
        "port": 6080,
        "host_port": 6080,
        "credentials": {"username": "", "password": "vnc_pwd"},
        "description": (
            "Web-based VNC client that provides browser access to the container's desktop environment. "
            "No additional software needed - access the full desktop directly through your web browser. "
            "Navigate to this port in your browser for instant desktop access to the container."
        ),
    },
    {
        "name": "filebrowser",
        "port": 8090,
        "host_port": 8090,
        "credentials": {"username": "admin", "password": "admin_pwd"},
        "description": (
            "Filebrowser: Web-based file manager providing easy access to container filesystem and file operations. "
            "Upload, download, edit, and organize files directly through an intuitive web interface. "
            "Manage your container files efficiently through the browser-based interface."
        ),
    },
    {
        "name": "email",
        "port": 8085,
        "host_port": 8085,
        "credentials": {"username": "current.user", "password": "current_user_pwd"},
        "description": (
            "Roundcube webmail interface for accessing email services. "
            "Provides a user-friendly email client for sending and receiving messages. "
            "Access your email through the web interface at the specified port."
        ),
    },
    {
        "name": "email_imap",
        "port": 1143,
        "host_port": 1143,
        "credentials": {"username": "current.user", "password": "current_user_pwd"},
        "description": (
            "IMAP access for email services. "
            "Provides programmatic access to email via IMAP protocol. "
            "Use this configuration for agents and automated email processing."
        ),
    },
    {
        "name": "health",
        "port": 8099,
        "host_port": 8099,
        "endpoint": "/health",
        "description": (
            "Health monitoring service that provides status information for all running applications. "
            "Reports the operational status and readiness of each service in the container environment. "
            "Used internally by DrBench to ensure all services are properly initialized and running."
        ),
    },
    {
        "name": "mcp-nextcloud",
        "port": 9090,
        "host_port": 9090,
        "endpoint": "/sse",
        "description": (
            "MCP (Model Context Protocol) server (SSE transport) for nextcloud integration. "
            "Provides a set of tools and APIs for managing and interacting with the nextcloud instance. "
            "Any mcp client can connect to http://<host>:<port>/sse (e.g. http://localhost:9090/sse) to "
            "access the nextcloud services' MCP."
        ),
    },
]

_DEFAULT_CONFIG = {
    "type": "docker",
    "host_url": "http://localhost",
    "image": _DEFAULT_DOCKER_IMAGE,
    "container_name": "drbench-services",
    "hostname": "drbench.com",
    "network": None,
    "volumes": None,
    "environment": {},
    "restart_policy": {"Name": "on-failure", "MaximumRetryCount": 3},
    "platform": None,
    "apps": _DEFAULT_APPS,
}
DEFAULT_CONFIG = _DEFAULT_CONFIG


class DrBenchEnterpriseSearchSpace:

    CONTAINER_TASK_FOLDER = Path("/drbench/task")

    def __init__(
        self,
        task: Optional[Union[str, Path]] = None,
        *,
        config: Optional[Union[str, Dict, OmegaConf]] = None,
        start_container: bool = False,
        container_suffix: Optional[str] = None,
        free_ports: bool = False,
        auto_ports: bool = False,
        **kwargs,
    ):
        """
        Initialize the DrBench Enterprise Search Space.

        Args:
            task: Directory path to the task to load in the enterprise search space
            config: Configuration as path string, dictionary, or OmegaConf object
            start_container: Whether to start the container immediately
            container_suffix: Optional custom suffix for the container name
            free_ports: Whether to free the ports before starting the container
            auto_ports: Whether to automatically assign free ports to the apps
            **kwargs: Override configuration parameters
        """
        self.config = self._load_config(config)

        # Generate a unique ID for this container instance
        self.instance_id = container_suffix or self._generate_short_uuid()

        # Update the container name with the unique ID
        container_name = self.config.container_name
        if not container_name.endswith(self.instance_id):
            OmegaConf.update(self.config, "container_name", f"{container_name}-{self.instance_id}")
            logger.info(f"Container name set to: {self.config.container_name}")

        # Override with kwargs
        for key, value in kwargs.items():
            OmegaConf.update(self.config, key, value)

        # Port management
        if auto_ports:
            logger.info("auto_ports is enabled. Setting all host ports to 0 (free ports).")
            # Automatically assign free ports to the apps
            for app in self.config.apps:
                if app.get("host_port", -1) != 0:
                    # Change to 0 to indicate free port
                    app["host_port"] = 0

        self.container_manager = create_container_manager(config=self.config, **kwargs)

        if isinstance(task, str):
            task = Path(task)
        self.task = task
        self.root_dir = ROOT_DIR

        self.task_loaded = False

        if start_container:
            self.start(free_ports=free_ports)

    @property
    def container_id(self) -> Optional[str]:
        """Return the container object."""
        return self.container_manager.container.id if self.container_manager.container else None

    def _generate_short_uuid(self) -> str:
        """Generate a short unique identifier for the container name."""
        # Generate a random UUID and take the first 8 characters
        return str(uuid.uuid4()).split("-")[0]

    def _load_config(self, config: Optional[Union[str, Dict, OmegaConf]] = None) -> OmegaConf:
        """Load configuration from the provided source."""

        default_config = OmegaConf.create(_DEFAULT_CONFIG)
        if config is None:
            return default_config

        if isinstance(config, str):
            # Treat as file path
            if os.path.exists(config):
                file_config = OmegaConf.load(config)
                return OmegaConf.merge(default_config, file_config)
            else:
                error_msg = f"Config file {config} not found. Using default configuration."
                logger.warning(error_msg)
                return default_config

        elif isinstance(config, dict):
            # Treat as config dictionary
            return OmegaConf.merge(default_config, OmegaConf.create(config))

        elif isinstance(config, OmegaConf):
            # Already an OmegaConf object
            return OmegaConf.merge(default_config, config)

        else:
            # Invalid type
            error_msg = f"Config must be a string, dictionary, or OmegaConf object, got {type(config)}"
            raise TypeError(error_msg)

    def start(self, free_ports: bool = False) -> str:
        """Start the environment by running the container."""
        if free_ports:
            # Kill the Ports if Taken
            ports = [app["host_port"] for app in self.config.apps]
            ports = [port for port in ports if port != 0]  # Filter out ports that are set to 0
            self.container_manager.check_and_kill_ports(ports)

        try:
            print(f"Starting container with image: {self.config.image} and name: {self.config.container_name}")
            self.container_manager.start_container()

        except Exception as e:
            logger.exception("Error starting container: %s", e)
            raise

        # Inject port mappings into container for index.php generation
        self._inject_port_mappings()

        # If there's a health service, wait for all the apps in the container to be up and running
        self.wait_for_apps()

        # Once it's up and running, add the task to the container
        if self.task:
            self.add_task()
            self.task_loaded = True

        return self.container_id

    def reset(self) -> str:
        """Reset the environment by restarting the container."""
        logger.info("Resetting the container...")
        t0 = time.time()
        try:
            self.task_loaded = False
            # Stops and removes the container if it exists
            if self.container_manager.container:
                self.container_manager.stop_container()
                self.container_manager.delete_container()
            # Start a new container and wait for it to be up and running
            self.start()

        except Exception as e:
            logger.exception("Error resetting container: %s", e)
            raise
        finally:
            t1 = time.time()
            logger.info(f"Container reset in {t1 - t0:.2f} seconds.")
            return self.container_id

    def stop(self) -> bool:
        """Stop the environment."""
        try:
            return self.container_manager.stop_container()
        except Exception as e:
            logger.exception("Error stopping container: %s", e)
            raise

    def delete(self) -> bool:
        """Clean up resources."""
        try:
            return self.container_manager.delete_container()
        except Exception as e:
            logger.exception("Error deleting container: %s", e)
            raise

    def _inject_port_mappings(self) -> None:
        """Inject port mappings into container for index.php generation."""
        if not self.container_id:
            logger.warning("No container running, skipping port injection")
            return
            
        try:
            logger.info("Injecting port mappings into container for index.php generation...")
            
            # Get current port mappings from Docker
            port_mappings = {}
            if self.config.get("apps"):
                for app in self.config.apps:
                    app_name = app.get("name")
                    if app_name and app_name in ["nextcloud", "mattermost", "filebrowser", "novnc", "email"]:
                        host_port = self.container_manager.get_host_port(app.port)
                        port_mappings[app_name] = {
                            "host_port": host_port,
                            "container_port": app.port
                        }
            
            if not port_mappings:
                logger.warning("No service port mappings found, skipping index generation")
                return
                
            # Convert to JSON
            port_mappings_json = json.dumps(port_mappings)
            logger.info(f"Port mappings to inject: {port_mappings_json}")
            
            # Write port mappings to container using a safer approach
            import tempfile
            import os
            
            # Create temporary file on host
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
                temp_file.write(port_mappings_json)
                temp_file_path = temp_file.name
            
            try:
                # Copy file to container (destination should be directory)
                self.container_manager.copy_file_to_container(temp_file_path, "/tmp/")
                # Rename to correct filename in container
                self.container_manager.run_command(f"mv /tmp/{os.path.basename(temp_file_path)} /tmp/port_mappings.json")
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
            
            # Make init_index.sh executable and run it
            self.container_manager.run_command("chmod +x /init_index.sh")
            result = self.container_manager.run_command("/init_index.sh")
            logger.info(f"Index generation result: {result}")
            
        except Exception as e:
            logger.error(f"Error injecting port mappings: {e}")
            # Don't raise - this is not critical for container operation
            
    def wait_for_apps(self, max_wait: int = 45, raise_timeout: bool = True) -> None:
        """Wait for all apps to be up and running."""
        logger.info("Waiting for apps to be up and running...")
        available_apps = self.get_available_apps()

        if "health" not in available_apps:
            logger.warning("No health service found. Skipping wait.")
            return
        health_app = available_apps["health"]
        endpoint = health_app.get("endpoint", "") or ""
        health_url = f"{self.config.host_url}:{health_app['host_port']}{endpoint}"
        # Wait for all apps to be up and running up to max_wait seconds
        t0 = time.time()
        time.sleep(8)  # Give the container some time to start
        while time.time() - t0 < max_wait:
            try:
                response = requests.get(health_url, timeout=5)
                wait_secs = 5
                if response.status_code != 200:
                    logger.warning(
                        f"[Health Check] Waiting for services to start. Retrying in {wait_secs}s. max_wait: {max_wait}s Aborting in {round(max_wait-(time.time() - t0),0)}s..."
                    )
                    time.sleep(wait_secs)
                    continue

                health_data = response.json()
                services_status = [
                    (service, (attrs["status"], attrs["ready"])) for service, attrs in health_data["services"].items()
                ]

                status_str = "\n".join(
                    [
                        " - %s:\tStatus: %s\tReady: %s" % (name, status, ready)
                        for name, (
                            status,
                            ready,
                        ) in services_status
                    ]
                )
                logger.info(f"Services status:\n{status_str}")
                if all((status == "healthy") & ready for _, (status, ready) in services_status):
                    logger.info("All services are healthy.")
                    return
                logger.info("Waiting for services to be healthy...")
                time.sleep(3)
            except Exception as e:
                logger.warning(f"Error checking health: {e}")
                time.sleep(3)
                continue

        timeout_msg = f"Timeout waiting for apps to be up and running after {max_wait} seconds."
        if raise_timeout:
            logger.exception(timeout_msg)
            raise TimeoutError(timeout_msg)
        else:
            logger.warning(timeout_msg)
            return

    def add_task(self) -> None:
        """Add a task to the container."""
        logger.info("Adding task to the container...")
        task = self.task
        # FIXME: Check this by running a command in the container
        if self.task_loaded:
            logger.warning("Task already loaded. Reset the container to load a new task.")
            return
        if isinstance(task, str):
            task = Path(task)
        if not task.exists():
            raise FileNotFoundError(f"Task directory {task} does not exist.")
        if not task.is_dir():
            raise NotADirectoryError(f"Task {task} is not a directory.")

        # Copy the task to the container
        self.container_manager.copy_file_to_container(task / "task.json", self.CONTAINER_TASK_FOLDER)

        # Copy env files to the container
        with open(task / "task.json", "r") as f:
            task_json = f.read()
        with open(task / "env.json", "r") as f:
            env_json = f.read()

        task_config = OmegaConf.create(task_json)
        env_config = OmegaConf.create(env_json)
        if "env_files" in env_config:
            logger.info(f"Copying {len(env_config['env_files'])} environment files to the container.")
            for env_file in env_config["env_files"]:
                if not env_file["source"]:
                    logger.warning("No source file provided for env_file. Skipping...")
                    continue
                source = Path(env_file["source"])
                if not Path(env_file["source"]).is_absolute():
                    source = Path(get_data_path(env_file["source"]))
                if not source.exists():
                    raise FileNotFoundError(f"Source file {source} does not exist.")

                dest_dir = Path(env_file["source"]).parent
                # Remove leading slash to make files relative to the task folder
                dest = self.CONTAINER_TASK_FOLDER / str(dest_dir).lstrip("/")
                self.container_manager.run_command(f'/bin/bash -c "mkdir -p {dest}"')
                self.container_manager.copy_file_to_container(source, dest)

        # If password present in the task.json "persona", we create an username
        # and override all passwords in the default configuration
        app_credentials_list = []
        if "persona" in task_config:
            persona = task_config["persona"]
            if "password" in persona:
                password = persona["password"]
                # Create username for the task persona
                username = persona.get("username", None)
                if not username:
                    first_name = persona.get("first_name", "current")
                    last_name = persona.get("last_name", "user")
                    username = f"{first_name}.{last_name}".lower()
                for app in self.config.apps:
                    if "credentials" in app:
                        app_name = app["name"]
                        # Skip excluded apps - they keep their default passwords
                        if app_name in _EXCLUDED_CREDENTIAL_APPS:
                            continue
                            
                        app_credentials = {}
                        app_credentials["app"] = app_name
                        credentials = app["credentials"]
                        if "username" in credentials:
                            if credentials["username"].strip():
                                # Override username with the task persona username
                                credentials["username"] = username
                            app_credentials["username"] = credentials["username"]
                        if "password" in credentials:
                            if credentials["password"].strip():
                                # Override password with the task persona password
                                credentials["password"] = password
                            app_credentials["password"] = credentials["password"]
                        app_credentials_list.append(app_credentials)

        # Add app credentials to the env_config object
        env_config["app_credentials"] = app_credentials_list

        # Create temporary json file with env_config and copy it to the environment
        temp_dir = tempfile.mkdtemp()
        temp_env_file_path = os.path.join(temp_dir, "env.json")
        env_config_dict = OmegaConf.to_container(env_config, resolve=True)
        with open(temp_env_file_path, "w") as temp_env_file:
            temp_env_file.write(json.dumps(env_config_dict))
        self.container_manager.copy_file_to_container(temp_env_file_path, self.CONTAINER_TASK_FOLDER)

        # Run script to properly load the task in the container
        logger.info("Running load_task script in the container...")
        output = self.container_manager.run_command("/drbench/scripts/load_task.sh", log_to_container=True)
        logger.debug(f"Load task output: {output}")
        self.task_loaded = True
        logger.info(f"Task {task} loaded in the container.")

    def get_available_apps(self):
        """Get the list of available apps."""
        if not self.container_id:
            raise RuntimeError("Container is not running. Please start the container first.")

        available_apps = dict()

        # Check if apps configuration exists
        apps_config = OmegaConf.select(self.config, "apps")
        if not apps_config:
            # If no apps configuration, return empty dict or default apps
            logger.warning("No apps configuration found. Returning empty apps list.")
            return available_apps

        for app in apps_config:
            host_port = self.container_manager.get_host_port(app.port)
            # Safe access to optional fields with OmegaConf
            endpoint = OmegaConf.select(app, "endpoint") or ""
            description = OmegaConf.select(app, "description") or ""

            app_info = {
                "url": f"{self.config.host_url}:{host_port}{endpoint}",
                "name": app.name,
                "port": app.port,
                "host_port": host_port,
                "endpoint": endpoint,
                "description": description,
            }

            # Safe access to credentials
            credentials = OmegaConf.select(app, "credentials")
            if credentials:
                app_info["credentials"] = {
                    "username": credentials["username"],
                    "password": credentials["password"],
                }

            available_apps[app.name] = app_info
        return available_apps

    def get_filesystem(self):
        """Get the filesystem structure for the agent."""
        return {
            "data": {
                "nextcloud": "Use get_nextcloud_files() to browse Nextcloud files",
                "filebrowser": "Access files through the FileBrowser interface",
                "container": f"Files are accessible through container {self.container_id}",
                "task_folder": str(self.CONTAINER_TASK_FOLDER),
            },
            "message": "Retrieved available filesystem locations",
        }

    def get_desktop_vnc(self):
        """Get the VNC desktop connection details."""
        vnc_app = self.get_available_apps().get("novnc")
        if vnc_app:
            return {
                "data": vnc_app["url"],
                "message": "VNC connection details retrieved",
            }
        else:
            return {
                "data": "vnc://localhost:5900",
                "message": "Default VNC connection details (novnc app not available)",
            }

    def execute_tool(self, tool_cmd):
        """Execute a tool command in the enterprise environment."""
        # For now, this is a basic implementation
        # More sophisticated tool execution can be added as needed
        if "get_available_apps" in tool_cmd:
            return {
                "data": self.get_available_apps(),
                "message": "Retrieved available applications",
            }
        elif "get_filesystem" in tool_cmd:
            return self.get_filesystem()
        elif "get_desktop_vnc" in tool_cmd:
            return self.get_desktop_vnc()
        else:
            return {
                "data": None,
                "message": f"Tool command '{tool_cmd}' not implemented in enterprise environment",
            }


class DockerlessSearchSpace:
    def __init__(self, task: Optional[Union[str, Path]] = None, **kwargs):
        self.task = task

    def get_available_apps(self):
        return None

    def delete(self):
        pass


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Example usage
    search_space = DrBenchEnterpriseSearchSpace(
        task=get_data_path("drbench/data/task_groups/task_2"),
        config={
            "image": _DEFAULT_DOCKER_IMAGE,
            "container_name": "drbench-enterprise-task-example",
            "hostname": "drbench.com",
        },
        # A custom suffix can be provided, or one will be generated automatically
        # container_suffix="custom123"
    )
    # Log the container name that was used
    logger.info(f"Container name with generated UUID: {search_space.config.container_name}")
    import json

    def retrieve_nextcloud_file(file_path: str, credentials: Optional[Dict[str, str]] = None) -> bytes:
        """Retrieve a file from Nextcloud."""
        nextcloud_app = search_space.get_available_apps()["nextcloud"]
        url = f"{nextcloud_app['url']}/remote.php/webdav/{file_path}"
        credentials = credentials or nextcloud_app.get("credentials", None)
        if credentials is None:
            raise ValueError("No credentials provided for Nextcloud app.")
        response = requests.get(url, auth=(credentials["username"], credentials["password"]))
        if response.status_code == 200:
            return response.content
        else:
            raise Exception(f"Error retrieving file: {response.status_code} - {response.text}")

    search_space.reset()
    print(json.dumps(search_space.get_available_apps(), indent=2))
    search_space.reset()
    search_space.stop()
    search_space.delete()
