# bedrock-server-manager/bedrock_server_manager/api/utils.py
import os
import logging
from typing import Dict, List, Optional, Any

# Local imports from API/App layer
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.utils.general import (
    get_base_dir,
)
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
    ServerNotFoundError,
    CommandNotFoundError,
    MissingArgumentError,
    DirectoryError,
    ResourceMonitorError,
    SystemError,
)
from bedrock_server_manager.core.server import (
    server as core_server,
)
from bedrock_server_manager.core.system import (
    base as core_system,
) 
from bedrock_server_manager.core import utils as core_utils

from bedrock_server_manager.utils import get_utils


logger = logging.getLogger("bedrock_server_manager")


def validate_server_exist(
    server_name: str, base_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates if a server installation directory and executable exist.
    (API wrapper for core_server.validate_server)
    """
    if not server_name:
        # API level argument validation
        logger.error("API.validate_server_exist: Server name cannot be empty.")
        return {"status": "error", "message": "Server name cannot be empty."}
        # Or raise MissingArgumentError if preferred for API errors to be exceptions

    logger.debug(f"API.validate_server_exist: Validating '{server_name}'...")
    try:
        effective_base_dir = get_base_dir(base_dir)  # Can raise FileOperationError
        core_server.validate_server(
            server_name, effective_base_dir
        )  # Can raise ServerNotFoundError (from core)
        logger.debug(
            f"API.validate_server_exist: Server '{server_name}' validation successful."
        )
        return {
            "status": "success",
            "message": f"Server '{server_name}' exists and is valid.",
        }
    except ServerNotFoundError as e:  # Core server not found
        logger.warning(
            f"API.validate_server_exist: Validation failed for '{server_name}': {e}"
        )
        return {"status": "error", "message": str(e)}
    except FileOperationError as e:  # From get_base_dir
        logger.error(
            f"API.validate_server_exist: Config error for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:  # Catch-all for unexpected
        logger.error(
            f"API.validate_server_exist: Unexpected error for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"An unexpected validation error occurred: {e}",
        }


def validate_server_name_format(server_name: str) -> Dict[str, str]:
    """
    Validates the format of a potential server name using core utility.
    """
    logger.debug(
        f"API.validate_server_name_format: Validating format for '{server_name}'"
    )
    try:
        core_utils.core_validate_server_name_format(
            server_name
        )  # Raises ValueError on failure
        logger.debug(
            f"API.validate_server_name_format: Format valid for '{server_name}'."
        )
        return {"status": "success", "message": "Server name format is valid."}
    except ValueError as e:  # From core_validate_server_name_format
        logger.warning(
            f"API.validate_server_name_format: Invalid format for '{server_name}': {e}"
        )
        return {"status": "error", "message": str(e)}
    except Exception as e:  # Catch-all
        logger.error(
            f"API.validate_server_name_format: Unexpected error for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def get_all_servers_status(
    base_dir: Optional[str] = None, config_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves the last known status and installed version for all detected servers.
    (API orchestrator using core_server functions)
    """
    servers_data: List[Dict[str, str]] = []
    error_messages = []
    logger.debug("API.get_all_servers_status: Getting status for all servers...")

    try:
        effective_base_dir = get_base_dir(base_dir)
        effective_config_dir = (
            config_dir
            if config_dir is not None
            else getattr(settings, "_config_dir", None)
        )
        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory not set in settings."
            )
        if not os.path.isdir(effective_base_dir):
            raise DirectoryError(
                f"Server base directory does not exist: {effective_base_dir}"
            )

        for item_name in os.listdir(effective_base_dir):
            item_path = os.path.join(effective_base_dir, item_name)
            if os.path.isdir(item_path):
                server_name = item_name
                try:
                    # Using core_server (core.server)
                    status = core_server.get_server_status_from_config(
                        server_name, effective_config_dir
                    )
                    version = core_server.get_installed_version(
                        server_name, effective_config_dir
                    )
                    servers_data.append(
                        {"name": server_name, "status": status, "version": version}
                    )
                except (
                    FileOperationError,
                    InvalidServerNameError,
                ) as e:  # API level errors
                    msg = f"Could not get info for server '{server_name}': {e}"
                    logger.error(f"API.get_all_servers_status: {msg}", exc_info=True)
                    error_messages.append(msg)
                # Core functions might raise their own errors if not caught here, e.g. core.ConfigurationError

        if error_messages:
            return {
                "status": "success",  # Partial success
                "servers": servers_data,
                "message": f"Completed with errors: {'; '.join(error_messages)}",
            }
        return {"status": "success", "servers": servers_data}

    except (FileOperationError, DirectoryError) as e:  # API level setup errors
        logger.error(f"API.get_all_servers_status: Setup error: {e}", exc_info=True)
        return {"status": "error", "message": f"Error accessing directories: {e}"}
    except Exception as e:
        logger.error(
            f"API.get_all_servers_status: Unexpected error: {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def update_server_statuses(
    base_dir: Optional[str] = None, config_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Updates status in config files based on runtime checks.
    (API orchestrator using core_system_ops and core_server)
    """
    updated_servers_list: List[str] = []
    error_messages = []
    logger.debug("API.update_server_statuses: Updating server statuses...")

    try:
        effective_base_dir = get_base_dir(base_dir)
        effective_config_dir = (
            config_dir
            if config_dir is not None
            else getattr(settings, "_config_dir", None)
        )
        if not effective_config_dir:
            raise FileOperationError("Base configuration directory not set.")
        if not os.path.isdir(effective_base_dir):
            raise DirectoryError(
                f"Server base directory does not exist: {effective_base_dir}"
            )

        for item_name in os.listdir(effective_base_dir):
            item_path = os.path.join(effective_base_dir, item_name)
            if os.path.isdir(item_path):
                server_name = item_name
                try:
                    is_actually_running = core_system.is_server_running(
                        server_name, effective_base_dir
                    )
                    config_status = core_server.get_server_status_from_config(
                        server_name, effective_config_dir
                    )

                    needs_update = False
                    new_status = config_status
                    if is_actually_running and config_status in (
                        "STOPPED",
                        "INSTALLED",
                        "UNKNOWN",
                        "ERROR",
                    ):
                        needs_update = True
                        new_status = "RUNNING"
                    elif not is_actually_running and config_status in (
                        "RUNNING",
                        "STARTING",
                        "RESTARTING",
                        "STOPPING",
                    ):
                        needs_update = True
                        new_status = "STOPPED"

                    if needs_update:
                        core_server.manage_server_config(
                            server_name,
                            "status",
                            "write",
                            new_status,
                            effective_config_dir,
                        )
                        updated_servers_list.append(server_name)
                        logger.info(
                            f"API.update_server_statuses: Updated '{server_name}' to '{new_status}'."
                        )

                except (
                    CommandNotFoundError,
                    ResourceMonitorError,
                    FileOperationError,
                    InvalidServerNameError,
                ) as e:  # API Level errors
                    msg = f"Could not update status for server '{server_name}': {e}"
                    logger.error(f"API.update_server_statuses: {msg}", exc_info=True)
                    error_messages.append(msg)

        if error_messages:
            return {
                "status": "error",  # If any server failed, overall status is error for this operation
                "message": f"Completed with errors: {'; '.join(error_messages)}",
                "updated_servers": updated_servers_list,
            }
        return {"status": "success", "updated_servers": updated_servers_list}

    except (FileOperationError, DirectoryError) as e:
        logger.error(f"API.update_server_statuses: Setup error: {e}", exc_info=True)
        return {"status": "error", "message": f"Error accessing directories: {e}"}
    except Exception as e:
        logger.error(
            f"API.update_server_statuses: Unexpected error: {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def list_content_files_api_wrapper(
    content_type_name: str, sub_folder: str, extensions: List[str]
) -> Dict[str, Any]:
    """Generic API wrapper for listing content files using core_utils."""
    logger.info(f"API: Listing {content_type_name} content files.")
    try:
        base_content_dir = settings.get("CONTENT_DIR")
        if not base_content_dir:
            # Use API Level error
            raise FileOperationError(
                "CONTENT_DIR setting is missing or empty in configuration."
            )

        target_dir = os.path.join(base_content_dir, sub_folder)

        # Ensure the target directory exists before calling core, or let core handle it
        # For API, better to pre-check for a clearer error message if base content dir is setup wrong
        if not os.path.isdir(target_dir):
            # Check if base_content_dir itself exists to differentiate
            if not os.path.isdir(base_content_dir):
                raise DirectoryError(
                    f"Base content directory '{base_content_dir}' not found."
                )
            # If base exists but subfolder doesn't, it might be intentional (no content of this type yet)
            # In this case, core_list_files_by_extension will return an empty list, which is fine.
            # However, if the API contract implies the folder should always exist, this check is good.
            # For now, let's assume the folder might not exist and it means no files.
            logger.warning(
                f"API: Content sub-directory '{target_dir}' not found. Assuming no files."
            )

        found_files = core_utils.core_list_files_by_extension(
            directory=target_dir, extensions=extensions
        )

        if not found_files:
            return {
                "status": "success",
                "files": [],
                "message": f"No matching {content_type_name} files found in '{target_dir}'.",
            }
        return {"status": "success", "files": found_files}

    except (
        FileOperationError,
        DirectoryError,
        MissingArgumentError,
        TypeError,
        ValueError,
    ) as e:  # Catch API/config errors and core's ValueError
        logger.error(
            f"API Error listing {content_type_name} content: {e}", exc_info=True
        )
        return {"status": "error", "message": str(e)}
    except OSError as e:  # From core_list_files_by_extension
        logger.error(
            f"API OSError listing {content_type_name} content: {e}", exc_info=True
        )
        return {"status": "error", "message": f"File system error listing files: {e}"}
    except Exception as e:
        logger.error(
            f"API Unexpected error listing {content_type_name} content: {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def list_world_content_files() -> Dict[str, Any]:
    """Lists available world files (e.g., .mcworld)."""
    return list_content_files_api_wrapper(
        content_type_name="world", sub_folder="worlds", extensions=["mcworld"]
    )


def list_addon_content_files() -> Dict[str, Any]:
    """Lists available addon files (e.g., .mcpack, .mcaddon)."""
    return list_content_files_api_wrapper(
        content_type_name="addon", sub_folder="addons", extensions=["mcpack", "mcaddon"]
    )


def attach_to_screen_session(server_name: str) -> Dict[str, str]:
    """
    Attempts to attach to the screen session of a running Bedrock server. (Linux-specific)
    (API orchestrator using core_system_ops and core_utils)
    """
    if not server_name:
        # API level validation
        logger.error("API.attach_to_screen_session: Server name cannot be empty.")
        return {
            "status": "error",
            "message": "Server name cannot be empty.",
        }  # Or raise MissingArgumentError

    logger.info(
        f"API.attach_to_screen_session: Attempting for server '{server_name}'..."
    )
    try:
        # Core utility can raise RuntimeError for non-Linux or screen not found
        # No need to explicitly check platform.system() here if core does it.

        # Check if server is running first
        effective_base_dir = get_base_dir(None)  # Can raise FileOperationError
        if not core_system.is_server_running(
            server_name, effective_base_dir
        ):  # Can raise CommandNotFoundError, ResourceMonitorError
            msg = f"Cannot attach: Server '{server_name}' is not currently running."
            logger.warning(f"API.attach_to_screen_session: {msg}")
            return {"status": "error", "message": msg}

        screen_session_name = f"bedrock-{server_name}"
        success, message = core_utils.core_execute_screen_attach(screen_session_name)

        if success:
            logger.info(
                f"API.attach_to_screen_session: Core reported success for '{screen_session_name}'."
            )
            return {"status": "success", "message": message}
        else:
            logger.warning(
                f"API.attach_to_screen_session: Core reported failure for '{screen_session_name}': {message}"
            )
            return {"status": "error", "message": message}

    except (
        RuntimeError
    ) as e:  # From core_utils.core_execute_screen_attach or core_system_ops.is_server_running (if it uses screen)
        logger.error(
            f"API.attach_to_screen_session: Runtime error for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": str(e)}
    except (
        FileOperationError,
        CommandNotFoundError,
        ResourceMonitorError,
    ) as e:  # From get_base_dir or is_server_running
        logger.error(
            f"API.attach_to_screen_session: Prerequisite error for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Error preparing for screen attach: {e}"}
    except Exception as e:
        logger.error(
            f"API.attach_to_screen_session: Unexpected error for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def get_system_and_app_info() -> Dict[str, Any]:
    """
    Retrieves system information and application version using get_utils.
    """
    logger.debug("API.get_system_and_app_info: Request received.")
    try:
        os_type = get_utils.get_operating_system_type()
        app_version = get_utils._get_app_version()

        data = {"os_type": os_type, "app_version": app_version}
        logger.info(f"API.get_system_and_app_info: Successfully retrieved: {data}")
        return {"status": "success", "data": data}
    except SystemError as e:  # If get_utils can raise this API-level error
        logger.error(f"API.get_system_and_app_info: System error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API.get_system_and_app_info: Unexpected error: {e}", exc_info=True
        )
        return {"status": "error", "message": "An unexpected error occurred."}
