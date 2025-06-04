# bedrock-server-manager/src/bedrock_server_manager/api/application.py
import logging
from typing import Dict, Any

from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.error import DirectoryError, FileOperationError

logger = logging.getLogger(__name__)
bsm = BedrockServerManager()


def get_application_info_api() -> Dict[str, Any]:
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
    logger.debug("API: Requesting list of available worlds.")
    try:
        worlds = bsm.list_available_worlds()
        return {"status": "success", "files": worlds}
    except (DirectoryError, FileOperationError) as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error listing worlds: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


def list_available_addons_api() -> Dict[str, Any]:
    logger.debug("API: Requesting list of available addons.")
    try:
        addons = bsm.list_available_addons()
        return {"status": "success", "files": addons}
    except (DirectoryError, FileOperationError) as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error listing addons: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


def get_all_servers_data() -> Dict[str, Any]:
    """
    Retrieves the last known status and installed version for all detected servers.
    (API orchestrator using core_server_actions functions)
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

    except (
        FileOperationError,
        DirectoryError,
    ) as e:  # Catch setup/IO errors from API or Core
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
