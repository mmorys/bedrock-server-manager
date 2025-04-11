# bedrock-server-manager/bedrock_server_manager/api/info.py
"""
Provides API-level functions for retrieving specific server information or status.
These typically wrap core functions to provide consistent dictionary outputs.
"""

import logging
from typing import Dict, Optional, Any

# Local imports
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
)

logger = logging.getLogger("bedrock_server_manager")


def get_server_running_status(
    server_name: str, base_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Checks if the server process is currently running.

    Args:
        server_name: The name of the server.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Returns:
        {"status": "success", "is_running": bool} or {"status": "error", "message": str}
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    logger.info(f"API: Checking running status for server '{server_name}'...")
    try:
        effective_base_dir = get_base_dir(base_dir)
        is_running = system_base.is_server_running(server_name, effective_base_dir)
        logger.debug(f"API: is_server_running check returned: {is_running}")
        return {"status": "success", "is_running": is_running}
    except FileOperationError as e:
        logger.error(
            f"API Running Status '{server_name}': Configuration error: {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"API Running Status '{server_name}': Unexpected error: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error checking running status: {e}",
        }


def get_server_config_status(
    server_name: str, config_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Gets the status field ('RUNNING', 'STOPPED', etc.) from the server's config JSON file.

    Args:
        server_name: The name of the server.
        config_dir: Optional. Base directory for server configs. Uses default if None.

    Returns:
        {"status": "success", "config_status": str} or {"status": "error", "message": str}
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    logger.info(f"API: Getting config status for server '{server_name}'...")
    try:
        # Core function already handles config_dir default and returns "UNKNOWN" if not found
        status = server_base.get_server_status_from_config(server_name, config_dir)
        logger.debug(f"API: get_server_status_from_config returned: '{status}'")
        return {"status": "success", "config_status": status}
    except (FileOperationError, InvalidServerNameError) as e:
        logger.error(
            f"API Config Status '{server_name}': Error calling core function: {e}",
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


def get_server_installed_version(
    server_name: str, config_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Gets the 'installed_version' field from the server's config JSON file.

    Args:
        server_name: The name of the server.
        config_dir: Optional. Base directory for server configs. Uses default if None.

    Returns:
        {"status": "success", "installed_version": str} ('UNKNOWN' if not found)
        or {"status": "error", "message": str}
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    logger.info(f"API: Getting installed version for server '{server_name}'...")
    try:
        # Core function handles config_dir default and returns "UNKNOWN" if not found/error
        version = server_base.get_installed_version(server_name, config_dir)
        logger.debug(f"API: get_installed_version returned: '{version}'")
        return {"status": "success", "installed_version": version}
    except (FileOperationError, InvalidServerNameError) as e:
        logger.error(
            f"API Installed Version '{server_name}': Error calling core function: {e}",
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
