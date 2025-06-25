# bedrock_server_manager/api/application.py
"""Provides API functions for application-wide information and actions.

This module handles requests for general application details, such as version
and directories. It also provides functions to list available content files
(e.g., worlds, addons) and to retrieve consolidated data for all managed
servers by interfacing with the `BedrockServerManager` core class.
"""
import logging
from typing import Dict, Any

# Plugin system imports to bridge API functionality.
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.error import BSMError, FileError

logger = logging.getLogger(__name__)

# Instantiate the core manager to be used by the API functions.
bsm = BedrockServerManager()


@plugin_method("get_application_info_api")
def get_application_info_api() -> Dict[str, Any]:
    """Retrieves general information about the application.

    Returns:
        A dictionary containing application details. On success, the format is
        `{"status": "success", "data": {"application_name": ..., "version": ...}}`.
        On error, the format is `{"status": "error", "message": "..."}`.
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


@plugin_method("list_available_worlds_api")
def list_available_worlds_api() -> Dict[str, Any]:
    """Lists available .mcworld files from the content directory.

    Returns:
        A dictionary containing a list of world file paths. On success, the
        format is `{"status": "success", "files": ["/path/to/world1.mcworld", ...]}`.
        On error, the format is `{"status": "error", "message": "..."}`.
    """
    logger.debug("API: Requesting list of available worlds.")
    try:
        worlds = bsm.list_available_worlds()
        return {"status": "success", "files": worlds}
    except FileError as e:
        # Handle specific file-related errors from the core manager.
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error listing worlds: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


@plugin_method("list_available_addons_api")
def list_available_addons_api() -> Dict[str, Any]:
    """Lists available .mcaddon and .mcpack files from the content directory.

    Returns:
        A dictionary containing a list of addon file paths. On success, the
        format is `{"status": "success", "files": ["/path/to/addon1.mcaddon", ...]}`.
        On error, the format is `{"status": "error", "message": "..."}`.
    """
    logger.debug("API: Requesting list of available addons.")
    try:
        addons = bsm.list_available_addons()
        return {"status": "success", "files": addons}
    except FileError as e:
        # Handle specific file-related errors from the core manager.
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error listing addons: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


@plugin_method("get_all_servers_data")
def get_all_servers_data() -> Dict[str, Any]:
    """Retrieves status and version for all detected servers.

    This function acts as an API orchestrator, calling the core manager
    to gather data from all individual server instances. It can handle
    partial failures, where data for some servers is retrieved successfully
    while others fail.

    Returns:
        A dictionary containing server data.
        - On full success: `{"status": "success", "servers": [...]}`.
        - On partial success: `{"status": "success", "servers": [...], "message": "..."}`.
          The `servers` list contains data for successful servers, and the `message`
          details the errors for the failed ones.
        - On total failure: `{"status": "error", "message": "..."}`.
    """
    logger.debug("API: Getting status for all servers...")

    try:
        # Call the core function which returns both data and potential errors.
        servers_data, bsm_error_messages = bsm.get_servers_data()

        # Check if the core layer collected any individual server errors.
        if bsm_error_messages:
            # Log each individual error for detailed debugging.
            for err_msg in bsm_error_messages:
                logger.error(
                    f"API: Individual server error during get_all_servers_data: {err_msg}"
                )
            # Return a partial success response.
            return {
                "status": "success",
                "servers": servers_data,
                "message": f"Completed with errors: {'; '.join(bsm_error_messages)}",
            }

        # If there were no errors, return a full success response.
        return {"status": "success", "servers": servers_data}

    except BSMError as e:  # Catch setup or I/O errors from the manager.
        logger.error(
            f"API: Setup or I/O error in get_all_servers_data: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Error accessing directories or configuration: {e}",
        }
    except Exception as e:  # Catch any other unexpected errors.
        logger.error(
            f"API: Unexpected error in get_all_servers_data: {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
