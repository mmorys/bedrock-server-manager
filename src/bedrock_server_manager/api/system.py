# bedrock_server_manager/api/system.py
"""Provides API functions for system-level server interactions.

This module orchestrates calls to `BedrockServer` class methods to manage
system-related configurations and information, such as process resource usage
and systemd service management on Linux.
"""
import logging
import platform
from typing import Dict, Optional, Any

# Plugin system imports to bridge API functionality.
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.cli.plugins import plugin
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    MissingArgumentError,
    UserInputError,
)

logger = logging.getLogger(__name__)


@plugin_method("get_bedrock_process_info")
def get_bedrock_process_info(server_name: str) -> Dict[str, Any]:
    """Retrieves resource usage for a running Bedrock server process.

    This function queries the system for the server's process and returns
    details like PID, CPU usage, memory consumption, and uptime.

    Args:
        server_name: The name of the server to query.

    Returns:
        A dictionary with the operation status and process information.
        On success with a running process:
        `{"status": "success", "process_info": {"pid": ..., "cpu": ..., ...}}`.
        If the process is not found:
        `{"status": "success", "process_info": None, "message": "..."}`.
        On error: `{"status": "error", "message": "..."}`.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"API: Getting process info for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)
        process_info = server.get_process_info()

        # If get_process_info returns None, the server is not running or inaccessible.
        if process_info is None:
            return {
                "status": "success",
                "message": f"Server process '{server_name}' not found or is inaccessible.",
                "process_info": None,
            }
        else:
            return {"status": "success", "process_info": process_info}
    except BSMError as e:
        logger.error(
            f"API: Failed to get process info for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error getting process info: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting process info for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting process info: {e}",
        }


def create_systemd_service(server_name: str, autostart: bool = False) -> Dict[str, str]:
    """Creates (or updates) a systemd user service for the server (Linux-only).

    This function generates a systemd service file, allowing the server to be
    managed by `systemctl`. It can also enable the service to start on boot.

    Args:
        server_name: The name of the server.
        autostart: If True, the service will be enabled to start on system boot.
            If False, it will be disabled. Defaults to False.

    Returns:
        A dictionary with the operation status and a message. Returns an error
        on non-Linux systems.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    plugin_manager.trigger_event(
        "before_service_change", server_name=server_name, action="create"
    )

    result = {}
    try:
        server = BedrockServer(server_name)
        server.create_systemd_service_file()

        # Enable or disable the service for autostart based on the flag.
        if autostart:
            server.enable_systemd_service()
            action = "created and enabled"
        else:
            server.disable_systemd_service()
            action = "created and disabled"

        result = {
            "status": "success",
            "message": f"Systemd service {action} successfully.",
        }

    except NotImplementedError as e:
        # This error is raised by core methods on non-Linux systems.
        result = {"status": "error", "message": str(e)}
    except BSMError as e:
        logger.error(
            f"API: Failed to configure systemd service for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Failed to configure systemd service: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error creating systemd service for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Unexpected error creating systemd service: {e}",
        }
    finally:
        plugin_manager.trigger_event(
            "after_service_change",
            server_name=server_name,
            action="create",
            result=result,
        )

    return result


def set_autoupdate(server_name: str, autoupdate_value: str) -> Dict[str, str]:
    """Sets the 'autoupdate' flag in the server's custom configuration.

    This function modifies the server-specific JSON configuration file to
    enable or disable the automatic update check before the server starts.

    Args:
        server_name: The name of the server.
        autoupdate_value: The desired state, as a string ('true' or 'false').

    Returns:
        A dictionary with the operation status and a message.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        MissingArgumentError: If `autoupdate_value` is not provided.
        UserInputError: If `autoupdate_value` is not 'true' or 'false'.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if autoupdate_value is None:
        raise MissingArgumentError("Autoupdate value cannot be empty.")

    # Validate and convert the input string to a boolean.
    value_lower = str(autoupdate_value).lower()
    if value_lower not in ("true", "false"):
        raise UserInputError("Autoupdate value must be 'true' or 'false'.")
    value_bool = value_lower == "true"

    plugin_manager.trigger_event(
        "before_autoupdate_change", server_name=server_name, new_value=value_bool
    )

    result = {}
    try:
        logger.info(
            f"API: Setting 'autoupdate' config for server '{server_name}' to {value_bool}..."
        )
        server = BedrockServer(server_name)
        # The core method expects a string representation of the boolean.
        server.set_custom_config_value("autoupdate", str(value_bool))
        result = {
            "status": "success",
            "message": f"Autoupdate setting for '{server_name}' updated to {value_bool}.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to set autoupdate config for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Failed to set autoupdate config: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error setting autoupdate for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Unexpected error setting autoupdate: {e}",
        }
    finally:
        plugin_manager.trigger_event(
            "after_autoupdate_change", server_name=server_name, result=result
        )

    return result


def enable_server_service(server_name: str) -> Dict[str, str]:
    """Enables the systemd user service for autostart (Linux-only).

    Args:
        server_name: The name of the server whose service will be enabled.

    Returns:
        A dictionary with the operation status and a message.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    plugin_manager.trigger_event(
        "before_service_change", server_name=server_name, action="enable"
    )

    result = {}
    try:
        server = BedrockServer(server_name)
        server.enable_systemd_service()
        result = {
            "status": "success",
            "message": f"Service for '{server_name}' enabled successfully.",
        }

    except NotImplementedError as e:
        result = {"status": "error", "message": str(e)}
    except BSMError as e:
        logger.error(
            f"API: Failed to enable systemd service for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Failed to enable service: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error enabling service for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Unexpected error enabling service: {e}",
        }
    finally:
        plugin_manager.trigger_event(
            "after_service_change",
            server_name=server_name,
            action="enable",
            result=result,
        )

    return result


def disable_server_service(server_name: str) -> Dict[str, str]:
    """Disables the systemd user service from autostarting (Linux-only).

    Args:
        server_name: The name of the server whose service will be disabled.

    Returns:
        A dictionary with the operation status and a message.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    plugin_manager.trigger_event(
        "before_service_change", server_name=server_name, action="disable"
    )

    result = {}
    try:
        server = BedrockServer(server_name)
        server.disable_systemd_service()
        result = {
            "status": "success",
            "message": f"Service for '{server_name}' disabled successfully.",
        }

    except NotImplementedError as e:
        result = {"status": "error", "message": str(e)}
    except BSMError as e:
        logger.error(
            f"API: Failed to disable systemd service for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Failed to disable service: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error disabling service for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Unexpected error disabling service: {e}",
        }
    finally:
        plugin_manager.trigger_event(
            "after_service_change",
            server_name=server_name,
            action="disable",
            result=result,
        )

    return result
