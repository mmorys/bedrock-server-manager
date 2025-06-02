# bedrock-server-manager/src/bedrock_server_manager/core/server/server_actions.py
"""
Core module for managing Bedrock server instances.
"""
import os
import logging
import json
import platform
from typing import Optional, Any, Dict

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    ServerNotFoundError,
    InvalidServerNameError,
    MissingArgumentError,
    FileOperationError,
    InvalidInputError,
)
from bedrock_server_manager.core.system import base as system_base


logger = logging.getLogger(__name__)


def validate_server(server_name: str, base_dir: str) -> bool:
    """
    Validates if a server installation exists and seems minimally correct.

    Checks for the existence of the server executable within the expected directory.

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server's folder.

    Returns:
        True if the server executable exists.

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        ServerNotFoundError: If the server directory or the executable file within it
                             does not exist.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    server_dir = os.path.join(base_dir, server_name)
    logger.debug(f"Validating server '{server_name}' in directory: {server_dir}")

    if not os.path.isdir(server_dir):
        error_msg = f"Server directory not found: {server_dir}"
        logger.error(error_msg)
        raise ServerNotFoundError(error_msg)  # Treat missing dir as server not found

    # Determine expected executable name based on OS
    exe_name = (
        "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
    )
    exe_path = os.path.join(server_dir, exe_name)

    if not os.path.isfile(exe_path):
        error_msg = (
            f"Server executable '{exe_name}' not found in directory: {server_dir}"
        )
        logger.error(error_msg)
        raise ServerNotFoundError(error_msg)

    logger.debug(f"Server '{server_name}' validation successful (executable found).")
    return True


def manage_server_config(
    server_name: str,
    key: str,
    operation: str,
    value: Any = None,
    config_dir: Optional[str] = None,
) -> Optional[Any]:
    """
    Reads or writes a specific key-value pair in a server's JSON config file.

    The config file is located at '{config_dir}/{server_name}/{server_name}_config.json'.

    Args:
        server_name: The name of the server.
        key: The configuration key (string) to read or write.
        operation: The action to perform ("read" or "write").
        value: The value to write (required for "write" operation). Can be any
               JSON-serializable type. Defaults to None.
        config_dir: Optional. The base directory containing server config folders.
                    Defaults to `settings._config_dir` if None.

    Returns:
        The value read for the key if `operation` is "read", otherwise None.
        Returns None if the key doesn't exist during a "read".

    Raises:
        MissingArgumentError: If required arguments are empty (`server_name`, `key`,
                            `operation`), or if `value` is missing for "write".
        InvalidServerNameError: If `server_name` is invalid (currently just checks empty).
        InvalidInputError: If `operation` is not "read" or "write".
        FileOperationError: If creating directories fails, or reading/writing the
                            JSON config file fails (OS errors, JSON errors).
    """
    # Use default config dir from settings if not provided
    effective_config_dir = (
        config_dir if config_dir is not None else getattr(settings, "_config_dir", None)
    )
    if not effective_config_dir:
        # Handle case where settings object might not have _config_dir yet or it's None/empty
        raise FileOperationError(
            "Base configuration directory is not set or available."
        )

    # Basic argument validation
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not key:
        raise MissingArgumentError("Config key cannot be empty.")
    if not operation:
        raise MissingArgumentError("Operation ('read' or 'write') cannot be empty.")
    operation = operation.lower()  # Normalize operation

    server_config_subdir = os.path.join(effective_config_dir, server_name)
    config_file_path = os.path.join(server_config_subdir, f"{server_name}_config.json")

    logger.debug(
        f"Managing config for server '{server_name}': Key='{key}', Op='{operation}', File='{config_file_path}'"
    )

    # Ensure the subdirectory for the server's config exists
    try:
        os.makedirs(server_config_subdir, exist_ok=True)
    except OSError as e:
        logger.error(
            f"Failed to create server config subdirectory '{server_config_subdir}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to create directory '{server_config_subdir}': {e}"
        ) from e

    # --- Load or initialize config data ---
    current_config: Dict[str, Any] = {}
    try:
        if os.path.exists(config_file_path):
            with open(config_file_path, "r", encoding="utf-8") as f:
                try:
                    content = f.read()
                    if content.strip():  # Check if file is not empty
                        current_config = json.loads(content)
                        if not isinstance(current_config, dict):
                            logger.warning(
                                f"Config file '{config_file_path}' does not contain a JSON object. Will be overwritten on write."
                            )
                            current_config = {}  # Treat as empty if not a dict
                        else:
                            logger.debug(f"Loaded existing config: {current_config}")
                    else:
                        logger.debug(
                            f"Config file '{config_file_path}' exists but is empty. Initializing as empty dict."
                        )
                        current_config = {}
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Failed to parse JSON from config file '{config_file_path}'. Will be overwritten on write. Error: {e}",
                        exc_info=True,
                    )
                    current_config = {}  # Treat as empty if invalid JSON
        else:
            logger.debug(
                f"Config file '{config_file_path}' not found. Will create on write, empty for read."
            )
            current_config = {}  # Initialize empty if file doesn't exist

    except OSError as e:
        logger.error(
            f"Failed to read config file '{config_file_path}': {e}", exc_info=True
        )
        raise FileOperationError(
            f"Failed to read config file '{config_file_path}': {e}"
        ) from e
    except Exception as e:  # Catch other unexpected errors during load
        logger.error(
            f"Unexpected error loading config file '{config_file_path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Unexpected error loading config file '{config_file_path}': {e}"
        ) from e

    # --- Perform Operation ---
    if operation == "read":
        read_value = current_config.get(key)  # Safely gets value or None
        logger.debug(f"Read operation: Key='{key}', Value='{read_value}'")
        return read_value
    elif operation == "write":
        if (
            value is None and key != "installed_version"
        ):  # Allow writing None for some keys if explicitly intended, but 'value' itself is expected.
            # This check was: if value is None: raise MissingArgumentError.
            # Let's refine it: for write operations, value is generally expected.
            # If a specific key *can* be None, the caller should pass None explicitly.
            # The original raise MissingArgumentError("Value is required for 'write' operation.") is generally correct.
            # The warning about writing None and then raising seems slightly contradictory.
            # Let's stick to the original: value is required.
            raise MissingArgumentError(
                f"Value is required for 'write' operation on key '{key}'."
            )

        logger.debug(f"Write operation: Key='{key}', New Value='{value}'")
        current_config[key] = value

        try:
            # Write the entire updated dictionary back
            with open(config_file_path, "w", encoding="utf-8") as f:
                json.dump(
                    current_config, f, indent=4, sort_keys=True
                )  # Pretty print with sorted keys
            logger.debug(f"Successfully wrote updated config to '{config_file_path}'.")
            return None  # Write operation returns None
        except OSError as e:
            logger.error(
                f"Failed to write updated config to '{config_file_path}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to write config file '{config_file_path}': {e}"
            ) from e
        except TypeError as e:  # Catch non-serializable data errors
            logger.error(
                f"Failed to serialize config data for writing: {e}", exc_info=True
            )
            raise FileOperationError(
                f"Config data for key '{key}' is not JSON serializable."
            ) from e

    else:
        # Invalid operation string
        logger.error(
            f"Invalid operation specified: '{operation}'. Must be 'read' or 'write'."
        )
        raise InvalidInputError(
            f"Invalid operation: '{operation}'. Must be 'read' or 'write'."
        )


def _get_server_details(
    server_name: str, server_path_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Gathers and validates server paths and essential details.

    Args:
        server_name: The name of the server.
        server_path_override: Optional. The full path to the server executable.
                              If None, it's inferred based on OS and server_dir.

    Returns:
        A dictionary containing server details:
        - server_name (str)
        - base_dir (str): Base directory for all servers from settings.
        - server_dir (str): Path to this specific server's installation directory.
        - server_path (str): Full path to the server executable.
        - config_dir_base (str): Base directory for all server configs from settings.
        - server_config_dir (str): Path to this specific server's configuration directory.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If BASE_DIR or _config_dir setting is missing.
        ServerNotFoundError: If the server executable cannot be found.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty for server operations.")

    logger.debug(f"Getting details for server '{server_name}'")

    base_dir = settings.get("BASE_DIR")
    if not base_dir:
        raise FileOperationError(
            "BASE_DIR setting is missing or empty in configuration."
        )
    server_dir = os.path.join(base_dir, server_name)

    config_dir_base = settings._config_dir
    if not config_dir_base:
        raise FileOperationError(
            "Internal _config_dir setting is missing or empty. Ensure settings are loaded."
        )
    server_config_dir = os.path.join(config_dir_base, server_name)

    if server_path_override:
        server_executable_path = server_path_override
        logger.debug(f"Using provided server executable path: {server_executable_path}")
    else:
        exe_name = (
            "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
        )
        server_executable_path = os.path.join(server_dir, exe_name)
        logger.debug(f"Using default server executable path: {server_executable_path}")

    # Validate existence of executable immediately
    if not os.path.isfile(server_executable_path):
        error_msg = f"Server executable not found at path: {server_executable_path}"
        logger.error(error_msg)
        raise ServerNotFoundError(error_msg)

    return {
        "server_name": server_name,
        "base_dir": base_dir,
        "server_dir": server_dir,
        "server_path": server_executable_path,
        "config_dir_base": config_dir_base,
        "server_config_dir": server_config_dir,
    }


def get_installed_version(server_name: str, config_dir: Optional[str] = None) -> str:
    """
    Retrieves the installed version string for a server from its config file.

    Args:
        server_name: The name of the server.
        config_dir: Optional. The base directory containing server config folders.
                    Defaults to `settings._config_dir` if None.

    Returns:
        The installed version string, or "UNKNOWN" if the version key is not found
        or the config file cannot be read.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If reading the config fails for reasons other than missing key.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.debug(
        f"Getting installed version for server '{server_name}' from its config."
    )

    try:
        # Use manage_server_config to read the specific key
        installed_version = manage_server_config(
            server_name=server_name,
            key="installed_version",
            operation="read",
            config_dir=config_dir,
        )

        if installed_version is None:
            logger.warning(
                f"Key 'installed_version' not found in config for server '{server_name}'. Returning 'UNKNOWN'."
            )
            return "UNKNOWN"

        # Ensure it's a string before returning
        if not isinstance(installed_version, str):
            logger.warning(
                f"Value for 'installed_version' in config for '{server_name}' is not a string ({type(installed_version)}). Returning 'UNKNOWN'."
            )
            return "UNKNOWN"

        logger.debug(
            f"Retrieved installed version for '{server_name}': '{installed_version}'"
        )
        return installed_version

    except FileOperationError as e:
        # Log error but return UNKNOWN as per original behavior if reading fails non-critically
        logger.error(
            f"Could not read installed version for server '{server_name}' due to config file error: {e}",
            exc_info=True,
        )
        return "UNKNOWN"
    except Exception as e:  # Catch other unexpected errors
        logger.error(
            f"Unexpected error retrieving installed version for '{server_name}': {e}",
            exc_info=True,
        )
        return "UNKNOWN"


def get_world_name(server_name: str, base_dir: str) -> str:
    """
    Reads the world directory name from the server.properties file.

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server's folder.

    Returns:
        The value of the 'level-name' property.

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        FileOperationError: If server.properties cannot be found, read, or if
                            the 'level-name' property is missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    server_properties_path = os.path.join(base_dir, server_name, "server.properties")
    logger.debug(
        f"Reading world name for server '{server_name}' from: {server_properties_path}"
    )

    if not os.path.isfile(server_properties_path):
        error_msg = f"server.properties file not found at: {server_properties_path}"
        logger.error(error_msg)
        raise FileOperationError(error_msg)

    try:
        with open(server_properties_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("level-name="):
                    # Split only on the first '='
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        world_name = parts[1].strip()
                        if world_name:  # Ensure value is not empty
                            logger.debug(
                                f"Found world name (level-name): '{world_name}'"
                            )
                            return world_name
                        else:
                            logger.error(
                                f"'level-name' property found but has empty value in {server_properties_path}"
                            )
                            raise FileOperationError(
                                f"'level-name' has empty value in {server_properties_path}"
                            )
                    else:
                        # Line starts with "level-name=" but has no value? Unlikely but handle.
                        logger.error(
                            f"Malformed 'level-name' line found in {server_properties_path}: {line}"
                        )
                        raise FileOperationError(
                            f"Malformed 'level-name' line in {server_properties_path}"
                        )

    except OSError as e:
        logger.error(
            f"Failed to read server.properties file '{server_properties_path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(f"Failed to read server.properties: {e}") from e
    except Exception as e:
        logger.error(
            f"Unexpected error reading server.properties '{server_properties_path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Unexpected error reading server.properties: {e}"
        ) from e

    # If loop completes without finding the property
    logger.error(f"'level-name' property not found in {server_properties_path}")
    raise FileOperationError(f"'level-name' not found in {server_properties_path}")


def check_if_server_is_running(server_name: str) -> bool:
    """
    Checks if the server process associated with this name is currently running.
    """
    if not server_name:
        # Consistent with how _get_server_details handles server_name
        raise MissingArgumentError("Server name cannot be empty.")

    logger.debug(f"Checking running status for server '{server_name}'")
    base_dir = settings.get("BASE_DIR")
    if not base_dir:
        raise FileOperationError(
            "BASE_DIR setting is missing or empty in configuration."
        )

    is_running_flag = system_base.is_server_running(server_name, base_dir)
    logger.debug(f"Server '{server_name}' is_running result: {is_running_flag}")
    return is_running_flag


def get_server_status_from_config(
    server_name: str, config_dir: Optional[str] = None
) -> str:
    """
    Retrieves the last known server status stored in the server's config file.

    Args:
        server_name: The name of the server.
        config_dir: Optional. The base directory containing server config folders.
                    Defaults to `settings._config_dir` if None.

    Returns:
        The status string stored in the config file ("RUNNING", "STOPPED", etc.),
        or "UNKNOWN" if the status key is not found or the config cannot be read.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If reading the config fails for reasons other than missing key.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.debug(
        f"Getting last known status for server '{server_name}' from its config."
    )

    try:
        status = manage_server_config(
            server_name=server_name,
            key="status",
            operation="read",
            config_dir=config_dir,
        )

        if status is None:
            logger.warning(
                f"Key 'status' not found in config for server '{server_name}'. Returning 'UNKNOWN'."
            )
            return "UNKNOWN"

        if not isinstance(status, str):
            logger.warning(
                f"Value for 'status' in config for '{server_name}' is not a string ({type(status)}). Returning 'UNKNOWN'."
            )
            return "UNKNOWN"

        logger.debug(f"Retrieved status from config for '{server_name}': '{status}'")
        return status

    except FileOperationError as e:
        logger.error(
            f"Could not read status for server '{server_name}' due to config file error: {e}",
            exc_info=True,
        )
        return "UNKNOWN"
    except Exception as e:
        logger.error(
            f"Unexpected error retrieving status for '{server_name}': {e}",
            exc_info=True,
        )
        return "UNKNOWN"
