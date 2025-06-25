# bedrock_server_manager/api/info.py
"""Provides API functions for retrieving server-specific information.

This module contains functions that wrap methods of the `BedrockServer` class
to expose server status and details through a consistent API layer. Each
function returns a dictionary suitable for JSON serialization, indicating the
outcome of the request.
"""

import logging
from typing import Dict, Any

# Plugin system imports to bridge API functionality.
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
)

logger = logging.getLogger(__name__)


@plugin_method("get_server_running_status")
def get_server_running_status(server_name: str) -> Dict[str, Any]:
    """Checks if the server process is currently running.

    This function queries the operating system to determine if the Bedrock
    server process associated with the given server name is active.

    Args:
        server_name: The name of the server to check.

    Returns:
        A dictionary with the result.
        On success: `{"status": "success", "is_running": bool}`.
        On error: `{"status": "error", "message": str}`.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Checking running status for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)
        is_running = server.is_running()
        logger.debug(
            f"API: is_running() check for '{server_name}' returned: {is_running}"
        )
        return {"status": "success", "is_running": is_running}
    except BSMError as e:
        logger.error(
            f"API: Error checking running status for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Error checking running status: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error checking running status for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error checking running status: {e}",
        }


@plugin_method("get_server_config_status")
def get_server_config_status(server_name: str) -> Dict[str, Any]:
    """Gets the status from the server's configuration file.

    This function reads the 'status' field (e.g., 'RUNNING', 'STOPPED')
    from the server's configuration file. Note that this reflects the last
    known state and may not match the actual process status if the server
    crashed.

    Args:
        server_name: The name of the server.

    Returns:
        A dictionary with the result.
        On success: `{"status": "success", "config_status": str}`.
        On error: `{"status": "error", "message": str}`.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Getting config status for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)
        status = server.get_status_from_config()
        logger.debug(
            f"API: get_status_from_config() for '{server_name}' returned: '{status}'"
        )
        return {"status": "success", "config_status": status}
    except BSMError as e:
        logger.error(
            f"API: Error retrieving config status for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Error retrieving config status: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting config status for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting config status: {e}",
        }


@plugin_method("get_server_installed_version")
def get_server_installed_version(server_name: str) -> Dict[str, Any]:
    """Gets the installed version from the server's configuration file.

    This function reads the 'installed_version' field from the server's
    configuration file. If the version is not found, it returns 'UNKNOWN'.

    Args:
        server_name: The name of the server.

    Returns:
        A dictionary with the result.
        On success: `{"status": "success", "installed_version": str}`.
        On error: `{"status": "error", "message": str}`.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Getting installed version for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)
        version = server.get_version()
        logger.debug(f"API: get_version() for '{server_name}' returned: '{version}'")
        return {"status": "success", "installed_version": version}
    except BSMError as e:
        logger.error(
            f"API: Error retrieving installed version for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Error retrieving installed version: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting installed version for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting installed version: {e}",
        }
