# bedrock_server_manager/api/application.py
"""
Provides API-level functions for application-wide information and actions.

This module handles requests for general application details, listing available
content files (worlds, addons), and retrieving data for all managed servers.
It interfaces with the BedrockServerManager core class.
"""
import logging
from typing import Dict, Any

from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.error import BSMError, FileError

logger = logging.getLogger(__name__)
bsm = BedrockServerManager()


def get_application_info_api() -> Dict[str, Any]:
    """
    Retrieves general information about the application.

    Returns:
        A dictionary containing application details like name, version, OS, and key directories.
        Example: `{"status": "success", "data": {"application_name": "...", ...}}` or
                 `{"status": "error", "message": "..."}`
    """
    logger.debug("API: Requesting application info.")
    try:
        info = {
            "application_name": bsm._app_name_title,
            "version": bsm.get_app_version(),
            "os_type": bsm.get_os_type(),
            "base_directory": bsm._base_dir,
            "content_directory": bsm._content_dir,
            "config_directory": bsm._config_dir,
        }
        return {"status": "success", "data": info}
    except Exception as e:
        logger.error(f"API: Unexpected error getting app info: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


def list_available_worlds_api() -> Dict[str, Any]:
    """
    Lists available .mcworld files from the application's content directory.

    Returns:
        A dictionary with a list of world file paths.
        Example: `{"status": "success", "files": ["/path/to/world1.mcworld", ...]}` or
                 `{"status": "error", "message": "..."}`
    """
    logger.debug("API: Requesting list of available worlds.")
    try:
        worlds = bsm.list_available_worlds()
        return {"status": "success", "files": worlds}
    except FileError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error listing worlds: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


def list_available_addons_api() -> Dict[str, Any]:
    """
    Lists available .mcaddon and .mcpack files from the application's content directory.

    Returns:
        A dictionary with a list of addon file paths.
        Example: `{"status": "success", "files": ["/path/to/addon1.mcaddon", ...]}` or
                 `{"status": "error", "message": "..."}`
    """
    logger.debug("API: Requesting list of available addons.")
    try:
        addons = bsm.list_available_addons()
        return {"status": "success", "files": addons}
    except FileError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error listing addons: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


def get_all_servers_data() -> Dict[str, Any]:
    """
    Retrieves the last known status and installed version for all detected servers.

    (API orchestrator using core_server_actions functions)

    Returns:
        A dictionary containing a list of server data objects, or an error message.
        Example: `{"status": "success", "servers": [{"name": "s1", "status": "RUNNING", ...}]}` or
                 `{"status": "error", "message": "..."}`.
        If some servers have errors, status can be "success" but with a message field detailing partial failures.
    """
    logger.debug("API.get_all_servers_data: Getting status for all servers...")

    try:

        # Call the core function
        servers_data, bsm_error_messages = bsm.get_servers_data()

        if bsm_error_messages:
            # Log all individual errors that the core layer collected
            for err_msg in bsm_error_messages:
                logger.error(
                    f"API.get_all_servers_data: Individual server error: {err_msg}"
                )
            return {
                "status": "success",  # Partial success
                "servers": servers_data,
                "message": f"Completed with errors: {'; '.join(bsm_error_messages)}",
            }

        return {"status": "success", "servers": servers_data}

    except BSMError as e:  # Catch setup/IO errors from API or Core
        logger.error(f"API.get_all_servers_data: Setup or IO error: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error accessing directories or configuration: {e}",
        }
    except (
        Exception
    ) as e:  # Catch any other unexpected errors (e.g., from core_server_utils if not caught in get_all_servers_data)
        logger.error(
            f"API.get_all_servers_status: Unexpected error: {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
