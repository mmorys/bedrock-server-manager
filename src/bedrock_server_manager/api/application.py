# bedrock-server-manager/src/bedrock_server_manager/api/application.py
import logging
from typing import Dict, Any, List

from bedrock_server_manager.manager import BedrockServerManager
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


def list_potential_servers_api() -> Dict[str, Any]:
    logger.debug("API: Requesting list of potential server directories.")
    try:
        server_dirs = bsm.list_potential_server_dirs()
        return {"status": "success", "server_directories": server_dirs}
    except DirectoryError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error listing server dirs: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


def validate_server_name_format_api(server_name: str) -> Dict[str, str]:
    logger.debug(f"API: Validating server name format for '{server_name}'.")
    if not server_name or not isinstance(server_name, str):
        return {"status": "error", "message": "Server name must be a non-empty string."}

    if bsm.is_valid_server_name_format(server_name):
        return {"status": "success", "message": "Server name format is valid."}
    else:
        # BSM's method is boolean, so API provides a more descriptive error.
        # Could enhance BSM's method to return reason or raise InvalidInputError.
        return {
            "status": "error",
            "message": "Server name format is invalid (e.g., contains spaces, special characters, or is empty).",
        }
