# bedrock-server-manager/bedrock_server_manager/api/system.py
"""
Provides API-level functions for interacting with system-level information
and configurations related to Bedrock servers.

Includes retrieving process information (PID, CPU, memory, uptime) and managing
systemd services on Linux systems. Functions typically return a dictionary
indicating success or failure status.
"""

import logging
import platform
from typing import Dict, Optional, Any

# Local imports
from bedrock_server_manager.api.server_install_config import write_server_config
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
)
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
    CommandNotFoundError,
    ServiceError,
    SystemdReloadError,
    ResourceMonitorError,
    MissingArgumentError,
    InvalidInputError,
)


logger = logging.getLogger("bedrock_server_manager")


def get_bedrock_process_info(
    server_name: str, base_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves resource usage information (PID, CPU%, Memory MB, Uptime) for
    a specific running Bedrock server process.

    Args:
        server_name: The name of the server.
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "process_info": Dict[str, Any]} containing the process details.
        - {"status": "error", "message": str} if the server process is not found or an error occurs.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"Attempting to get process info for server '{server_name}'...")
    try:
        effective_base_dir = get_base_dir(base_dir)

        # Delegate to the core function which handles platform specifics and psutil
        process_info = system_base._get_bedrock_process_info(
            server_name, effective_base_dir
        )

        if process_info is None:
            # Core function returns None if process not found or inaccessible
            logger.warning(
                f"Process info not found or inaccessible for server '{server_name}'."
            )
            return {
                "status": "error",
                "message": f"Server process '{server_name}' not found or information is inaccessible.",
            }
        else:
            logger.debug(
                f"Successfully retrieved process info for server '{server_name}': {process_info}"
            )
            return {"status": "success", "process_info": process_info}

    except (
        ResourceMonitorError,
        FileOperationError,
    ) as e:  # Catch specific errors from core or get_base_dir
        logger.error(
            f"Failed to get process info for server '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error getting process info: {e}"}
    except Exception as e:
        # Catch unexpected errors
        logger.error(
            f"Unexpected error getting process info for server '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting process info: {e}",
        }


def create_systemd_service(
    server_name: str,
    base_dir: Optional[str] = None,
    autoupdate: bool = False,
    autostart: bool = False,
) -> Dict[str, str]:
    """
    Creates (or updates) and optionally enables a systemd user service for the server.

    (Linux-specific)

    Args:
        server_name: The name of the server.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        autoupdate: If True, configure the service to run update checks before starting.
        autostart: If True, enable the service to start automatically on user login.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined or EXPATH is invalid.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    if platform.system() != "Linux":
        logger.warning(
            "Attempted to create systemd service on non-Linux OS. Operation skipped."
        )
        return {
            "status": "error",
            "message": "Systemd services are only supported on Linux.",
        }

    logger.info(
        f"Creating/updating systemd service for server '{server_name}'. Autoupdate={autoupdate}, Autostart={autostart}"
    )
    try:
        effective_base_dir = get_base_dir(base_dir)

        # Call core function to create/update the .service file
        system_linux._create_systemd_service(
            server_name, effective_base_dir, autoupdate
        )

        # Enable or disable based on autostart flag
        if autostart:
            logger.info(f"Enabling autostart for systemd service '{server_name}'...")
            system_linux._enable_systemd_service(server_name)
            action = "created and enabled"
        else:
            logger.info(f"Disabling autostart for systemd service '{server_name}'...")
            system_linux._disable_systemd_service(server_name)
            action = "created and disabled"

        logger.info(
            f"Systemd service for server '{server_name}' successfully {action}."
        )
        return {
            "status": "success",
            "message": f"Systemd service {action} successfully.",
        }

    except (
        ServiceError,
        SystemdReloadError,
        CommandNotFoundError,
        FileOperationError,
        InvalidServerNameError,
    ) as e:
        # Catch specific errors from core functions or get_base_dir
        logger.error(
            f"Failed to create/configure systemd service for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Failed to configure systemd service: {e}",
        }
    except Exception as e:
        # Catch unexpected errors
        logger.error(
            f"Unexpected error creating systemd service for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error creating systemd service: {e}",
        }


def set_windows_autoupdate(
    server_name: str,
    autoupdate_value: str,  # Expect "true" or "false" as string input
    config_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    Sets the 'autoupdate' flag in the server's specific JSON configuration file.

    (Windows-specific - though the config setting could be used cross-platform,
    this function name implies Windows context).

    Args:
        server_name: The name of the server.
        autoupdate_value: The string value "true" or "false" to set. Case-insensitive.
        config_dir: Optional. The base directory for server configs. Uses default if None.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name` or `autoupdate_value` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        InvalidInputError: If `autoupdate_value` is not "true" or "false".
        FileOperationError: If `config_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not autoupdate_value:
        raise MissingArgumentError("Autoupdate value cannot be empty.")

    # Validate and normalize input value
    value_lower = autoupdate_value.lower()
    if value_lower not in ("true", "false"):
        raise InvalidInputError("Autoupdate value must be 'true' or 'false'.")
    # Store the boolean equivalent
    value_bool = value_lower == "true"

    if platform.system() != "Windows":
        logger.warning(
            "Attempted to set Windows autoupdate flag on non-Windows OS. Operation skipped."
        )
        return {
            "status": "error",
            "message": "'set_windows_autoupdate' is only applicable on Windows.",
        }

    logger.info(
        f"Setting 'autoupdate' config for server '{server_name}' to {value_bool}..."
    )
    try:
        # Use the API function which handles config dir resolution and returns dict
        result = write_server_config(
            server_name=server_name,
            key="autoupdate",
            value=value_bool,  # Write the boolean value
            config_dir=config_dir,
        )
        if result.get("status") == "success":
            logger.info(
                f"Successfully set autoupdate config for '{server_name}' to {value_bool}."
            )
            result["message"] = (
                f"Autoupdate setting for '{server_name}' updated to {value_bool}."
            )
        # else: error logged by write_server_config
        return result

    except (
        MissingArgumentError,
        InvalidInputError,
        FileOperationError,
        InvalidServerNameError,
    ) as e:
        # Catch errors from write_server_config call or initial checks
        logger.error(
            f"Failed to set autoupdate config for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to set autoupdate config: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error setting autoupdate config for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error setting autoupdate: {e}",
        }


def enable_server_service(server_name: str) -> Dict[str, str]:
    """
    Enables the systemd user service associated with the server for autostart.

    (Linux-specific)

    Args:
        server_name: The name of the server.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    if platform.system() != "Linux":
        logger.warning(
            "Attempted to enable systemd service on non-Linux OS. Operation skipped."
        )
        return {
            "status": "error",
            "message": "Systemd services are only supported on Linux.",
        }

    logger.info(f"Attempting to enable systemd service for server '{server_name}'...")
    try:
        # Call the core Linux function
        system_linux._enable_systemd_service(server_name)
        logger.info(f"Successfully enabled systemd service for server '{server_name}'.")
        return {
            "status": "success",
            "message": f"Service for '{server_name}' enabled successfully.",
        }
    except (ServiceError, CommandNotFoundError, InvalidServerNameError) as e:
        # Catch specific errors from the core function
        logger.error(
            f"Failed to enable systemd service for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to enable service: {e}"}
    except Exception as e:
        # Catch unexpected errors
        logger.error(
            f"Unexpected error enabling systemd service for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error enabling service: {e}"}


def disable_server_service(server_name: str) -> Dict[str, str]:
    """
    Disables the systemd user service associated with the server from autostarting.

    (Linux-specific)

    Args:
        server_name: The name of the server.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    if platform.system() != "Linux":
        logger.warning(
            "Attempted to disable systemd service on non-Linux OS. Operation skipped."
        )
        return {
            "status": "error",
            "message": "Systemd services are only supported on Linux.",
        }

    logger.info(f"Attempting to disable systemd service for server '{server_name}'...")
    try:
        # Call the core Linux function
        system_linux._disable_systemd_service(server_name)
        logger.info(
            f"Successfully disabled systemd service for server '{server_name}'."
        )
        return {
            "status": "success",
            "message": f"Service for '{server_name}' disabled successfully.",
        }
    except (ServiceError, CommandNotFoundError, InvalidServerNameError) as e:
        # Catch specific errors from the core function
        logger.error(
            f"Failed to disable systemd service for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to disable service: {e}"}
    except Exception as e:
        # Catch unexpected errors
        logger.error(
            f"Unexpected error disabling systemd service for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error disabling service: {e}",
        }
