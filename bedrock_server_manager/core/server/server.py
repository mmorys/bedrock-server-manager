# bedrock-server-manager/bedrock_server_manager/core/server/server.py
import subprocess
import os
import logging
import time
import json
import platform
import shutil
from bedrock_server_manager.config import settings
from bedrock_server_manager.core.error import (
    ServerStartError,
    ServerStopError,
    ServerNotRunningError,
    SendCommandError,
    ServerNotFoundError,
    InvalidServerNameError,
    MissingArgumentError,
    FileOperationError,
    InvalidInputError,
    DirectoryError,
    InstallUpdateError,
    CommandNotFoundError,
)
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
    windows as system_windows,
)
from bedrock_server_manager.core.download import downloader
from bedrock_server_manager.core.server import backup

logger = logging.getLogger("bedrock_server_manager")


class BedrockServer:
    def __init__(self, server_name, server_path=None):
        self.server_name = server_name
        self.server_dir = os.path.join(settings.BASE_DIR, self.server_name)
        if server_path:
            self.server_path = server_path
        else:
            # Determine the executable name based on the platform
            if platform.system() == "Windows":
                exe_name = "bedrock_server.exe"
            else:
                exe_name = "bedrock_server"
            self.server_path = os.path.join(self.server_dir, exe_name)

        if not os.path.exists(self.server_path):
            raise ServerNotFoundError(self.server_path)
        self.process = None
        self.status = "STOPPED"

    def is_running(self):
        """Checks if the server process is currently running."""
        return system_base.is_server_running(self.server_name, settings.BASE_DIR)

    def get_pid(self):
        """Gets the process ID of the running server (if running)."""
        server_info = system_base._get_bedrock_process_info(
            self.server_name, settings.BASE_DIR
        )
        return server_info.get("pid") if server_info else None

    def get_cpu_usage(self):
        """Gets the current CPU usage of the server (if running)."""
        server_info = system_base._get_bedrock_process_info(
            self.server_name, settings.BASE_DIR
        )
        return server_info.get("cpu_percent") if server_info else None

    def get_memory_usage(self):
        """Gets the current memory usage of the server (if running)."""
        server_info = system_base._get_bedrock_process_info(
            self.server_name, settings.BASE_DIR
        )
        return server_info.get("memory_mb") if server_info else None

    def get_uptime(self):
        """Gets the server uptime (if running)."""
        server_info = system_base._get_bedrock_process_info(
            self.server_name, settings.BASE_DIR
        )
        return server_info.get("uptime") if server_info else None

    def send_command(self, command):
        """Sends a command to the running server process.
        Raises:
            MissingArgumentError: If command is empty
            ServerNotRunningError: If the server is not running.
            SendCommandError: If there is an error sending command.
            CommandNotFoundError: If screen not found on linux
        """
        if not command:
            raise MissingArgumentError("send_command: command is empty.")

        if not self.is_running():
            raise ServerNotRunningError("Cannot send command: Server is not running.")

        if platform.system() == "Linux":
            try:
                # Use screen -X stuff to send the command
                subprocess.run(
                    [
                        "screen",
                        "-S",
                        f"bedrock-{self.server_name}",
                        "-X",
                        "stuff",
                        f"{command}\n",
                    ],
                    check=True,  # Raise exception on error
                )
                logger.debug(f"Sent command '{command}' to server '{self.server_name}'")
            except subprocess.CalledProcessError as e:
                raise SendCommandError(f"Failed to send command to server: {e}") from e
            except FileNotFoundError:
                raise CommandNotFoundError(
                    "screen", message="screen command not found. Is screen installed?"
                ) from None

        elif platform.system() == "Windows":
            if self.process:  # Use the stored process object
                try:
                    self.process.stdin.write(f"{command}\n".encode())
                    self.process.stdin.flush()
                    logger.debug(
                        f"Sent command '{command}' to server '{self.server_name}'"
                    )
                except Exception as e:
                    raise SendCommandError(f"Error sending command: {e}") from e
            else:
                # This should, ideally, never happen if is_running() is accurate.
                raise ServerNotRunningError(
                    "Could not find running server process to send command to (process object missing)."
                )
        else:
            raise SendCommandError("Unsupported operating system for sending commands.")

    def start(self):
        if self.is_running():
            raise ServerStartError("Server is already running!")

        self.status = "STARTING"
        manage_server_config(self.server_name, "status", "write", "STARTING")
        logger.info(f"Starting server '{self.server_name}'...")

        if platform.system() == "Linux":
            try:
                # First, try starting via systemd
                service_name = f"bedrock-{self.server_name}"
                subprocess.run(
                    ["systemctl", "--user", "start", service_name], check=True
                )
                logger.info(f"Started {service_name} via systemctl.")

            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning(
                    "Failed to start via systemctl. Falling back to screen..."
                )
                # Fallback to screen if systemd fails
                system_linux._systemd_start_server(self.server_name, self.server_dir)

        elif platform.system() == "Windows":
            self.process = system_windows._windows_start_server(
                self.server_name, self.server_dir
            )
        else:
            raise ServerStartError("Unsupported operating system for starting server.")

        # Wait for the server to initialize
        attempts = 0
        max_attempts = 30
        while attempts < max_attempts:
            if self.is_running():
                self.status = "RUNNING"
                manage_server_config(self.server_name, "status", "write", "RUNNING")
                logger.info(f"Server '{self.server_name}' started successfully.")
                return
            logger.debug(
                f"Waiting for server '{self.server_name}' to start... (Attempt {attempts + 1}/{max_attempts})"
            )
            time.sleep(2)
            attempts += 1

        self.status = "ERROR"  # Update status to stopped if it didn't start
        manage_server_config(self.server_name, "status", "write", "ERROR")
        raise ServerStartError(
            f"Server '{self.server_name}' failed to start within the timeout."
        )

    def stop(self):
        """Stops the Bedrock server."""

        if not self.is_running():
            logger.info(f"Server '{self.server_name}' is not running.")
            return

        self.status = "STOPPING"
        manage_server_config(self.server_name, "status", "write", "STOPPING")
        logger.info(f"Stopping server '{self.server_name}'...")

        if platform.system() == "Linux":
            try:
                # First, try stopping via systemd
                service_name = f"bedrock-{self.server_name}"
                subprocess.run(
                    ["systemctl", "--user", "stop", service_name], check=True
                )
                logger.info(f"Stopped {service_name} via systemctl.")
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning(
                    "Failed to stop via systemctl. Falling back to screen..."
                )
                system_linux._systemd_stop_server(self.server_name, self.server_dir)
        elif platform.system() == "Windows":
            system_windows._windows_stop_server(self.server_name, self.server_dir)
        else:
            raise ServerStopError("Unsupported operating system for stopping server.")

        # Wait for the server to stop
        attempts = 0
        max_attempts = 30  # Same as the start timeout
        while attempts < max_attempts:
            if not self.is_running():
                self.status = "STOPPED"
                manage_server_config(self.server_name, "status", "write", "STOPPED")
                logger.info(f"Server '{self.server_name}' stopped successfully.")
                return

            logger.debug(
                f"Waiting for server '{self.server_name}' to stop... (Attempt {attempts + 1}/{max_attempts})"
            )
            time.sleep(2)
            attempts += 1
        # Did not stop cleanly
        raise ServerStopError(
            f"Server '{self.server_name}' failed to stop within the timeout"
        )


def get_world_name(server_name, base_dir):
    """Gets the world name from the server.properties file.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.

    Returns:
        str: The world name.

    Raises:
        MissingArgumentError: If server_name is empty.
        FileOperationError: If server.properties cannot be read or world name is not found
    """
    server_properties = os.path.join(base_dir, server_name, "server.properties")

    if not server_name:
        raise MissingArgumentError("get_world_name: server_name is empty")

    logger.debug(f"Getting world name for: {server_name}")

    if not os.path.exists(server_properties):
        raise FileOperationError(f"server.properties not found for {server_name}")

    try:
        with open(server_properties, "r") as f:
            for line in f:
                if line.startswith("level-name="):
                    world_name = line.split("=")[1].strip()
                    logger.debug(f"World name: {world_name}")
                    return world_name
    except OSError as e:
        raise FileOperationError(f"Failed to read server.properties: {e}") from e

    raise FileOperationError("Failed to extract world name from server.properties.")


def validate_server(server_name, base_dir):
    """Validates if a server exists by checking for the server executable.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory where servers are stored.

    Returns:
        bool: True if the server exists and is valid.

    Raises:
        MissingArgumentError: If server_name is empty.
        ServerNotFoundError: If the server executable is not found.
    """
    server_dir = os.path.join(base_dir, server_name)

    if not server_name:
        raise MissingArgumentError("validate_server: server_name is empty.")

    if platform.system() == "Windows":
        exe_name = "bedrock_server.exe"
    else:
        exe_name = "bedrock_server"

    exe_path = os.path.join(server_dir, exe_name)
    if not os.path.exists(exe_path):
        raise ServerNotFoundError(exe_path)

    logger.debug(f"{server_name} valid")
    return True  # keep the return of True


def manage_server_config(server_name, key, operation, value=None, config_dir=None):
    """Manages individual server configuration files (server_name_config.json).

    Args:
        server_name (str): The name of the server.
        key (str): The configuration key.
        operation (str): "read" or "write".
        value (str, optional): The value to write (required for "write").
        config_dir (str, optional): config directory. Defaults to main config

    Returns:
        any: Value for "read" operation (or None).

    Raises:
        MissingArgumentError: If server_name, key, or operation is empty, or if value is missing for 'write'.
        InvalidServerNameError: If server_name is invalid
        InvalidInputError: If the operation is invalid.
        FileOperationError: If there's an error reading or writing the config file.
    """
    if config_dir is None:
        config_dir = settings.CONFIG_DIR

    server_config_dir = os.path.join(config_dir, server_name)
    config_file = os.path.join(server_config_dir, f"{server_name}_config.json")

    if not server_name:
        raise InvalidServerNameError("manage_server_config: server_name is empty.")
    if not key or not operation:
        raise MissingArgumentError("manage_server_config: key or operation is empty.")

    os.makedirs(server_config_dir, exist_ok=True)

    if not os.path.exists(config_file):
        try:
            with open(config_file, "w") as f:
                json.dump({}, f)  # Create empty JSON file
        except OSError as e:
            raise FileOperationError(f"Failed to create config file: {e}") from e

    try:
        with open(config_file, "r") as f:
            current_config = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise FileOperationError(f"Failed to read/parse config file: {e}") from e

    if operation == "read":
        return current_config.get(key)  # Returns None if not found
    elif operation == "write":
        if value is None:
            raise MissingArgumentError("Value is required for 'write' operation.")
        current_config[key] = value
        try:
            with open(config_file, "w") as f:
                json.dump(current_config, f, indent=4)
            logger.debug(f"Updated '{key}' in config to: '{value}'")
        except OSError as e:
            raise FileOperationError(f"Failed to write to config file: {e}") from e
    else:
        raise InvalidInputError(
            f"Invalid operation: '{operation}'. Must be 'read' or 'write'."
        )


def get_installed_version(server_name, config_dir=None):
    """Gets the installed version of a server from its config.json.

    Args:
      server_name (str): The server name.
      config_dir (str): The config directory. Defaults to the main config directory.

    Returns:
        str: The installed version, or "UNKNOWN" if not found.

    Raises:
        MissingArgumentError: If server_name is empty.
        # Other exceptions may be raised by manage_server_config
    """
    logger.debug(f"Getting installed version for server: {server_name}")

    if not server_name:
        raise MissingArgumentError("No server name provided.")

    if config_dir is None:
        config_dir = settings.CONFIG_DIR

    installed_version = manage_server_config(
        server_name, "installed_version", "read", config_dir=config_dir
    )

    if installed_version is None:
        logger.warning(
            "No installed_version found in config.json, defaulting to UNKNOWN."
        )
        return "UNKNOWN"

    return installed_version


def check_server_status(
    server_name, base_dir, max_attempts=20, chunk_size=500, max_lines=5000
):
    """Checks the server status by reading server_output.txt.

    Args:
        server_name (str): The name of the server.
        base_dir (str): base directory.
        max_attempts (int): Max attempts to find the log
        chunk_size (int): Max lines of the log to read at once
        max_lines (int): Total amount of lines to read from the log

    Returns:
        str: The server status ("RUNNING", "STARTING", "RESTARTING",
             "STOPPING", "STOPPED", or "UNKNOWN").

    Raises:
        MissingArgumentError: if server_name is empty
        FileOperationError: if there is a problem reading the log
    """
    status = "UNKNOWN"
    log_file = os.path.join(base_dir, server_name, "server_output.txt")
    attempt = 0

    if not server_name:
        raise MissingArgumentError("check_server_status: server_name is empty.")

    # Wait for the log file to exist (up to max_attempts)
    while not os.path.exists(log_file) and attempt < max_attempts:
        time.sleep(0.5)  # Consider making the sleep duration configurable
        attempt += 1

    if not os.path.exists(log_file):
        logger.warning(f"Log file not found after {max_attempts} attempts: {log_file}")
        return "UNKNOWN"  # consistent return

    try:
        with open(log_file, "r") as f:
            lines = f.readlines()  # Read all lines
    except OSError as e:
        raise FileOperationError(f"Failed to read server log: {log_file}") from e

    total_lines = len(lines)
    read_lines = 0

    # Read log file in chunks, starting from the end
    while read_lines < max_lines and read_lines < total_lines:
        lines_to_read = min(chunk_size, total_lines - read_lines)
        log_chunk = lines[-(read_lines + lines_to_read) :]  # Read a chunk from the end
        log_chunk.reverse()  # Read lines in reverse (most recent first)

        for line in log_chunk:
            line = line.strip()
            if "Server started." in line:
                status = "RUNNING"
                break
            elif "Starting Server" in line:
                status = "STARTING"
                break
            elif "Restarting server in 10 seconds" in line:
                status = "RESTARTING"
                break
            elif "Shutting down server in 10 seconds" in line:
                status = "STOPPING"
                break
            elif "Quit correctly" in line:
                status = "STOPPED"
                break

        if status != "UNKNOWN":
            break  # Exit loop if status is found
        read_lines += lines_to_read

    logger.debug(f"{server_name} status from output file: {status}")
    return status


def get_server_status_from_config(server_name, config_dir=None):
    """Gets the server status from the server's config.json file.

    Args:
        server_name (str): The name of the server.
        config_dir (str, optional): config directory, defaults to main config.

    Returns:
        str: The server status ("RUNNING", "STARTING", etc., or "UNKNOWN").

    Raises:
        MissingArgumentError: If server_name is empty.
        # Other exceptions may be raised by manage_server_config
    """
    if not server_name:
        raise MissingArgumentError(
            "get_server_status_from_config: server_name is empty."
        )

    if config_dir is None:
        config_dir = settings.CONFIG_DIR

    status = manage_server_config(server_name, "status", "read", config_dir=config_dir)
    if status is None:
        return "UNKNOWN"

    return status


def update_server_status_in_config(server_name, base_dir, config_dir=None):
    """Updates the server status in the server's config.json file.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory where servers are stored.
        config_dir (str, optional): config directory. Defaults to main config.

    Raises:
        MissingArgumentError: If server_name is empty.
        InvalidServerNameError: If the server name is not valid.
        FileOperationError: If there's an error reading or writing the config file.
        # Other exceptions may be raised by get_server_status_from_config or check_server_status
    """
    if not server_name:
        raise InvalidServerNameError(
            "update_server_status_in_config: server_name is empty."
        )

    if config_dir is None:
        config_dir = settings.CONFIG_DIR

    current_status = get_server_status_from_config(server_name, config_dir)
    status = check_server_status(server_name, base_dir)

    if current_status == "installed" and status == "UNKNOWN":
        logger.debug(
            "Status is 'installed', retrieved status is 'UNKNOWN'. Not updating."
        )
        return  # No update needed

    manage_server_config(server_name, "status", "write", status, config_dir=config_dir)
    logger.debug(f"Successfully updated server status for {server_name} in config.json")


def configure_allowlist(server_dir):
    """Loads and returns the existing allowlist.json data.  Does *not* modify the file.

    Args:
        server_dir (str): The directory of the server.

    Returns:
        list: A list of existing player entries (dictionaries), or an empty list if the file doesn't exist.

    Raises:
        MissingArgumentError: If server_dir is empty.
        FileOperationError: If there's an error reading or parsing the JSON.
    """
    allowlist_file = os.path.join(server_dir, "allowlist.json")
    existing_players = []

    if not server_dir:
        raise MissingArgumentError("configure_allowlist: server_dir is empty.")

    if os.path.exists(allowlist_file):
        try:
            with open(allowlist_file, "r") as f:
                existing_players = json.load(f)
            logger.debug("Loaded existing allowlist.json.")
        except (OSError, json.JSONDecodeError) as e:
            raise FileOperationError(
                f"Failed to read existing allowlist.json: {e}"
            ) from e

    return existing_players


def add_players_to_allowlist(server_dir, new_players):
    """Adds new players to the allowlist.json file

    Args:
        server_dir (str): The directory of the server
        new_players (list): A list of dicts. Each dict should have
          'name' and 'ignoresPlayerLimit' keys.

    Raises:
        MissingArgumentError: If server_dir is None/empty
        FileOperationError: If reading/writing allowlist fails.

    """
    allowlist_file = os.path.join(server_dir, "allowlist.json")
    existing_players = []

    if not server_dir:
        raise MissingArgumentError("add_players_to_allowlist: server_dir is empty")
    if not isinstance(new_players, list):
        raise TypeError("new_players must be a list")

    # Load existing players
    if os.path.exists(allowlist_file):
        try:
            with open(allowlist_file, "r") as f:
                existing_players = json.load(f)
            logger.debug("Loaded existing allowlist.json.")
        except (OSError, json.JSONDecodeError) as e:
            raise FileOperationError(
                f"Failed to read existing allowlist.json: {e}"
            ) from e

    # Check for duplicates and add new players
    for player in new_players:
        if any(
            existing_player["name"] == player["name"]
            for existing_player in existing_players
        ):
            logger.warning(
                f"Player '{player['name']}' is already in the allowlist. Skipping."
            )
            continue  # Skip if already exists.
        existing_players.append(player)
    try:
        with open(allowlist_file, "w") as f:
            json.dump(existing_players, f, indent=4)
    except OSError as e:
        raise FileOperationError(f"Failed to save updated allowlist.json: {e}") from e

    logger.info(f"Updated allowlist.json with {len(new_players)} new players.")


def configure_permissions(server_dir, xuid, player_name, permission):
    """Updates permissions.json with a player and their permission level.

    Args:
        server_dir (str): The directory of the server.
        xuid (str): The player's XUID.
        player_name (str): The player's name.
        permission (str): The permission level ("operator", "member", "visitor").

    Raises:
        MissingArgumentError: If server_dir, xuid, or permission is empty.
        InvalidInputError: If permission is not a valid value.
        DirectoryError: If server_dir is not a valid directory.
        InvalidServerNameError: If server dir is invalid.
        FileOperationError: If there's an error creating, reading, or writing the permissions file.
    """
    permissions_file = os.path.join(server_dir, "permissions.json")

    if not server_dir:
        raise InvalidServerNameError("configure_permissions: server_dir is empty.")
    if not xuid:
        raise MissingArgumentError("configure_permissions: xuid is empty.")
    if not permission:
        raise MissingArgumentError("configure_permissions: permission is empty.")
    if permission.lower() not in ("operator", "member", "visitor"):
        raise InvalidInputError("configure_permissions: invalid permission level.")

    if not os.path.isdir(server_dir):
        raise DirectoryError(f"Server directory not found: {server_dir}")

    if not os.path.exists(permissions_file):
        try:
            with open(permissions_file, "w") as f:
                json.dump([], f)
            logger.debug(f"Created empty permissions file: {permissions_file}")
        except OSError as e:
            raise FileOperationError(
                f"Failed to initialize permissions.json: {e}"
            ) from e

    try:
        with open(permissions_file, "r") as f:
            permissions_data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise FileOperationError(
            f"Failed to read or parse permissions.json: {e}"
        ) from e

    # Check if the player already exists
    for i, player_entry in enumerate(permissions_data):
        if player_entry["xuid"] == xuid:
            if player_entry["permission"] == permission.lower():
                logger.warning(
                    f"Player: {player_name} with permission '{permission}' is already in permissions.json."
                )
                return  # Already exists with the same permission
            else:
                # Update existing player's permission
                permissions_data[i]["permission"] = permission.lower()
                logger.info(
                    f"Updated player: {player_name} to '{permission}' in permissions.json."
                )
                break
    else:
        # Add the new player
        new_player = {
            "permission": permission.lower(),
            "xuid": xuid,
            "name": player_name,
        }
        permissions_data.append(new_player)
        logger.info(
            f"Added player: {player_name} as '{permission}' in permissions.json."
        )

    # Write the updated data back to the file
    try:
        with open(permissions_file, "w") as f:
            json.dump(permissions_data, f, indent=4)
    except OSError as e:
        raise FileOperationError(f"Failed to update permissions.json: {e}") from e


def modify_server_properties(server_properties, property_name, property_value):
    """Modifies or adds a property in the server.properties file.

    Args:
        server_properties (str): Path to the server.properties file.
        property_name (str): The name of the property.
        property_value (str): The value of the property.

    Raises:
        MissingArgumentError: If server_properties or property_name is empty.
        FileOperationError: If server.properties file doesn't exist or there's an error reading/writing.
        InvalidInputError: If property_value contains control characters.
    """

    if not server_properties:
        raise MissingArgumentError(
            "modify_server_properties: server_properties file path is empty."
        )
    if not os.path.exists(server_properties):
        raise FileOperationError(
            f"modify_server_properties: server_properties file does not exist: {server_properties}"
        )
    if not property_name:
        raise MissingArgumentError("modify_server_properties: property_name is empty.")
    if any(ord(c) < 32 for c in property_value):
        raise InvalidInputError(
            "modify_server_properties: property_value contains control characters."
        )

    try:
        with open(server_properties, "r") as f:
            lines = f.readlines()

        property_found = False
        for i, line in enumerate(lines):
            if line.startswith(property_name + "="):
                lines[i] = f"{property_name}={property_value}\n"
                property_found = True
                logger.debug(f"Updated {property_name} to {property_value}")
                break

        if not property_found:
            lines.append(f"{property_name}={property_value}\n")
            logger.debug(f"Added {property_name} with value {property_value}")

        with open(server_properties, "w") as f:
            f.writelines(lines)

    except OSError as e:
        raise FileOperationError(
            f"Failed to modify property '{property_name}': {e}"
        ) from e


def _write_version_config(server_name, installed_version, config_dir=None):
    """Writes the installed version to the server's config.json.

    Args:
        server_name (str): The name of the server.
        installed_version (str): The installed version.
        config_dir (str, optional): Config directory.

    Raises:
        MissingArgumentError: If server_name is empty.
        InvalidServerNameError: if the server name is not valid
        # Other exceptions may be raised by manage_server_config
    """
    if not server_name:
        raise InvalidServerNameError("write_version_config: server_name is empty")

    if config_dir is None:
        config_dir = settings.CONFIG_DIR

    if not installed_version:
        logger.warning(
            "write_version_config: installed_version is empty.  Writing empty string to config."
        )

    manage_server_config(
        server_name,
        "installed_version",
        "write",
        installed_version,
        config_dir=config_dir,
    )
    logger.info(
        f"Successfully updated installed_version in config.json for server: {server_name}"
    )


def install_server(
    server_name, base_dir, current_version, zip_file, server_dir, in_update
):
    """Installs or updates the Bedrock server.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.
        current_version (str): The version to install
        zip_file (str): The path to the downloaded zip file
        server_dir (str): The servers directory
        in_update (bool): Whether the server is being updated or installed

    Raises:
        MissingArgumentError: if server_name is empty
        InvalidServerNameError: If server name is invalid
        InstallUpdateError: If any step in the install/update process fails.
    """
    if not server_name:
        raise InvalidServerNameError("install_server: server_name is empty.")

    # Cleanup old downloads
    downloader.prune_old_downloads(os.path.dirname(zip_file), settings.DOWNLOAD_KEEP)

    # Stop server if running for update
    was_running = False
    if in_update:
        was_running = stop_server_if_running(server_name, base_dir)

    # Backup server before update
    if in_update:
        try:
            backup.backup_all(server_name, base_dir)
            logger.info("Backup successful before update.")
        except Exception as e:
            raise InstallUpdateError(f"Backup failed before update: {e}") from e

    try:
        downloader.extract_server_files_from_zip(zip_file, server_dir, in_update)
    except Exception as e:
        raise InstallUpdateError(f"Failed to extract server files: {e}") from e

    # Restore all after update
    if in_update:
        try:
            backup.restore_all(server_name, base_dir)
            logger.info("Server data restored after update.")
        except Exception as e:
            raise InstallUpdateError(f"Restore failed after update: {e}") from e

    try:
        system_base.set_server_folder_permissions(server_dir)  # use core
    except Exception as e:
        logger.warning(f"Failed to set server folder permissions: {e}")

    try:
        _write_version_config(server_name, current_version)
    except Exception as e:
        raise InstallUpdateError(f"Failed to write version to config.json: {e}") from e

    # Start server if it was running
    if was_running:
        start_server_if_was_running(server_name, base_dir, was_running)  # Pass base_dir


def no_update_needed(server_name, installed_version, target_version):
    """Checks if an update is needed.

    Args:
        server_name (str): The name of the server.
        installed_version (str): The currently installed version.
        target_version (str): The desired version ("LATEST", "PREVIEW", or specific).

    Returns:
        bool: True if no update is needed, False otherwise.

    Raises:
        MissingArgumentError: If server_name is empty.
        InvalidServerNameError: If server name is not valid.
        # Other exceptions may be raised by downloader functions
    """
    if not server_name:
        raise InvalidServerNameError("no_update_needed: server_name is empty.")

    if not installed_version:
        logger.warning(
            "no_update_needed: installed_version is empty. Assuming update is needed."
        )
        return False  # Assume update is needed

    if target_version.upper() not in ("LATEST", "PREVIEW"):
        # Specific version requested, always update.
        return False

    try:
        download_url = downloader.lookup_bedrock_download_url(target_version)
        current_version = downloader.get_version_from_url(download_url)
    except Exception:
        # If we can't get the target version, assume an update is needed
        return False

    if installed_version == current_version:
        return True  # No update needed
    else:
        return False  # Update needed


def delete_server_data(server_name, base_dir, config_dir=None):
    """Deletes a Bedrock server's data and configuration.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.
        config_dir (str): The config directory.

    Raises:
        MissingArgumentError: If server_name is empty.
        InvalidServerNameError: If the server name is not valid.
        DirectoryError: If deleting the server data fails
    """
    if config_dir is None:
        config_dir = settings.CONFIG_DIR
    server_dir = os.path.join(base_dir, server_name)
    config_folder = os.path.join(config_dir, server_name)

    if not server_name:
        raise InvalidServerNameError("delete_server_data: server_name is empty.")

    if not os.path.exists(server_dir) and not os.path.exists(config_folder):
        logger.warning(
            f"Server {server_name} does not appear to exist (no server or config directory)."
        )
        return  # Not an error if it doesn't exist

    # Remove the systemd service file
    if platform.system() == "Linux":
        service_file = os.path.join(
            os.path.expanduser("~"),
            ".config",
            "systemd",
            "user",
            f"bedrock-{server_name}.service",
        )
        if os.path.exists(service_file):
            logger.debug(f"Removing user systemd service for {server_name}")
            try:
                system_linux._disable_systemd_service(server_name)
                os.remove(service_file)
                logger.debug(f"Removed service file: {service_file}")
                subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
                logger.debug("systemd daemon reloaded")
            except Exception as e:
                logger.warning(f"Failed to disable/remove/reload systemd service: {e}")

    elif platform.system() == "Windows":
        system_base.remove_readonly(server_dir)
        system_base.remove_readonly(config_dir)

    # Remove the server directory
    logger.debug(f"Deleting server directory: {server_dir}")
    try:
        shutil.rmtree(server_dir)
    except OSError as e:
        raise DirectoryError(
            f"Failed to delete server directory: {server_dir}: {e}"
        ) from e

    # Remove the config directory
    logger.debug(f"Deleting config directory: {config_folder}")
    try:
        shutil.rmtree(config_folder)
    except OSError as e:
        raise DirectoryError(
            f"Failed to delete config directory: {config_folder}: {e}"
        ) from e

    logger.info(f"Server {server_name} data deleted successfully.")


def start_server_if_was_running(server_name, base_dir, was_running):
    """Starts the server if it was previously running.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.
        was_running (bool): True if the server was running before, False otherwise.
    # Exceptions from start will be raised.
    """
    if was_running:
        logger.info(f"Restarting server {server_name} as it was running previously...")
        bedrock_server = BedrockServer(server_name)
        bedrock_server.start()  # Use start_server


def stop_server_if_running(server_name, base_dir):
    """Stops the server if it's running, and returns whether it was running.

    Args:
        server_name (str): The name of the server.
        base_dir (str): Server base directory

    Returns:
        bool: True if the server was running (and was stopped or an attempt
              was made to stop it), False otherwise.
    Raises:
        InvalidServerNameError: If the server name is empty.
        # Other exceptions may be raised by is_server_running or stop_server.
    """
    if not server_name:
        raise InvalidServerNameError("stop_server_if_running: server_name is empty.")

    logger.debug("Checking if server is running")
    if system_base.is_server_running(server_name, base_dir):
        try:
            logger.info(f"Stopping server: {server_name}")
            bedrock_server = BedrockServer(server_name)
            bedrock_server.stop()  # Use stop_server
            return True  # Was running and stopped successfully
        except Exception:
            # Even if stop_server raises an exception, we still return True,
            # because the server *was* running. We've already logged any
            # errors within stop_server.
            return True
    else:
        logger.debug(f"Server {server_name} is not currently running.")  # use debug
        return False  # Server was not running
