# bedrock_server_manager/api/info.py
"""
Provides API-level functions for retrieving specific server information or status.
These functions wrap methods of the BedrockServer class to provide consistent
dictionary outputs for the API layer.
"""

import logging
from typing import Dict, Any

# Local imports
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
)

logger = logging.getLogger(__name__)


def get_server_running_status(server_name: str) -> Dict[str, Any]:
    """
    Checks if the server process is currently running using the BedrockServer class.

    Args:
        server_name: The name of the server.

    Returns:
        {"status": "success", "is_running": bool} or {"status": "error", "message": str}
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Checking running status for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)
        is_running = server.is_running()
        logger.debug(f"API: is_running() check returned: {is_running}")
        return {"status": "success", "is_running": is_running}
    except BSMError as e:
        logger.error(
            f"API Running Status '{server_name}': Error during check: {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Error checking running status: {e}"}
    except Exception as e:
        logger.error(
            f"API Running Status '{server_name}': Unexpected error: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error checking running status: {e}",
        }


def get_server_config_status(server_name: str) -> Dict[str, Any]:
    """
    Gets the status field ('RUNNING', 'STOPPED', etc.) from the server's config JSON file.

    Args:
        server_name: The name of the server.

    Returns:
        {"status": "success", "config_status": str} or {"status": "error", "message": str}
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Getting config status for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)
        status = server.get_status_from_config()
        logger.debug(f"API: get_status_from_config() returned: '{status}'")
        return {"status": "success", "config_status": status}
    except BSMError as e:
        logger.error(
            f"API Config Status '{server_name}': Error calling core method: {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Error retrieving config status: {e}"}
    except Exception as e:
        logger.error(
            f"API Config Status '{server_name}': Unexpected error: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting config status: {e}",
        }


def get_server_installed_version(server_name: str) -> Dict[str, Any]:
    """
    Gets the 'installed_version' field from the server's config JSON file.

    Args:
        server_name: The name of the server.

    Returns:
        {"status": "success", "installed_version": str} ('UNKNOWN' if not found)
        or {"status": "error", "message": str}
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Getting installed version for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)
        version = server.get_version()
        logger.debug(f"API: get_version() returned: '{version}'")
        return {"status": "success", "installed_version": version}
    except BSMError as e:
        logger.error(
            f"API Installed Version '{server_name}': Error calling core method: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Error retrieving installed version: {e}",
        }
    except Exception as e:
        logger.error(
            f"API Installed Version '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting installed version: {e}",
        }
