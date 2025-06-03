# bedrock-server-manager/src/bedrock_server_manager/api/utils.py
import os
import logging
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

# Local imports from API/App layer
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.core.server import server_actions as core_server_actions
from bedrock_server_manager.core.server import server_utils as core_server_utils
from bedrock_server_manager.core import utils as core_utils
from bedrock_server_manager.utils import get_utils
from bedrock_server_manager.manager import BedrockServerManager
from bedrock_server_manager.api.server import (
    start_server as api_start_server,
    stop_server as api_stop_server,
)  # For context manager
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
from bedrock_server_manager.core.system import (
    base as core_system,
)


logger = logging.getLogger(__name__)
bsm = BedrockServerManager()


def validate_server_exist(
    server_name: str, base_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates if a server installation directory and executable exist.
    (API wrapper for core_server_utils.validate_server)
    """
    if not server_name:
        # API level argument validation
        logger.error("API.validate_server_exist: Server name cannot be empty.")
        return {"status": "error", "message": "Server name cannot be empty."}
        # Or raise MissingArgumentError if preferred for API errors to be exceptions

    logger.debug(f"API.validate_server_exist: Validating '{server_name}'...")
    try:
        effective_base_dir = get_base_dir(base_dir)  # Can raise FileOperationError
        core_server_utils.validate_server(
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
    (API orchestrator using core_server_actions functions)
    """
    servers_data: List[Dict[str, str]] = []
    error_messages = []
    logger.debug("API.get_all_servers_status: Getting status for all servers...")

    try:
        effective_base_dir = get_base_dir(base_dir)
        effective_config_dir = (
            config_dir
            if config_dir is not None
            else getattr(settings, "config_dir", None)
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
                    # Using core_server_actions (core.server.server_actions)
                    status = core_server_utils.get_server_status_from_config(
                        server_name, effective_config_dir
                    )
                    version = core_server_utils.get_installed_version(
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
            else getattr(settings, "config_dir", None)
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
                    config_status = core_server_utils.get_server_status_from_config(
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
                        core_server_utils.manage_server_config(
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


def list_available_worlds_api() -> Dict[str, Any]:  # Renamed for clarity (API function)
    """
    API endpoint to list available world files (e.g., .mcworld)
    from the configured content directory.
    """
    logger.debug("API: Requesting list of available worlds.")
    try:
        # Call the BSM method directly
        world_files = bsm.list_available_worlds()

        if not world_files:
            return {
                "status": "success",
                "files": [],
                "message": "No world files found in the content directory.",
            }
        return {
            "status": "success",
            "files": world_files,  # BSM method already returns List[str] of basenames
        }
    except (DirectoryError, FileOperationError) as e:
        # These are exceptions that bsm.list_available_worlds might raise if
        # CONTENT_DIR is misconfigured or inaccessible.
        logger.error(f"API Error listing worlds: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        # Catch any other unexpected errors from BSM or this layer
        logger.error(
            f"API: Unexpected error listing available worlds: {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}


def list_available_addons_api() -> Dict[str, Any]:  # Renamed for clarity (API function)
    """
    API endpoint to list available addon files (e.g., .mcpack, .mcaddon)
    from the configured content directory.
    """
    logger.debug("API: Requesting list of available addons.")
    try:
        # Call the BSM method directly
        addon_files = bsm.list_available_addons()

        if not addon_files:
            return {
                "status": "success",
                "files": [],
                "message": "No addon files found in the content directory.",
            }
        return {
            "status": "success",
            "files": addon_files,  # BSM method already returns List[str] of basenames
        }
    except (DirectoryError, FileOperationError) as e:
        # These are exceptions that bsm.list_available_addons might raise
        logger.error(f"API Error listing addons: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        # Catch any other unexpected errors from BSM or this layer
        logger.error(
            f"API: Unexpected error listing available addons: {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}


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


@contextmanager
def _server_stop_start_manager(
    server_name: str,
    base_dir: str,
    stop_start_flag: bool,
    restart_on_success_only: bool = False,
):
    """
    Context manager to handle stopping a server before an operation and
    restarting it afterward if it was running.

    Args:
        server_name: The name of the server.
        base_dir: Base directory for the server.
        stop_start_flag: If True, perform stop/start.
        restart_on_success_only: If True, only attempt restart if the managed
                                 block ('yield') completed without exceptions.
    """
    was_running = False
    operation_succeeded = True

    if not stop_start_flag:
        logger.debug(
            f"Context Mgr: Stop/Start not flagged for '{server_name}'. Skipping."
        )
        yield
        return

    try:
        logger.debug(
            f"Context Mgr: Checking status for '{server_name}' (Stop/Start: {stop_start_flag})"
        )
        if core_server_actions.check_if_server_is_running(server_name):
            was_running = True
            logger.info(f"Context Mgr: Server '{server_name}' is running. Stopping...")
            stop_result = api_stop_server(server_name, base_dir)
            if stop_result.get("status") == "error":
                raise FileOperationError(
                    f"Context Mgr: Failed to stop server '{server_name}' for operation: {stop_result.get('message')}"
                )
            logger.info(f"Context Mgr: Server '{server_name}' stopped.")
        else:
            logger.debug(
                f"Context Mgr: Server '{server_name}' is not running. No stop needed."
            )

        yield

    except Exception:
        operation_succeeded = False
        logger.error(
            f"Context Mgr: Exception occurred during managed operation for '{server_name}'."
        )
        raise
    finally:
        if stop_start_flag and was_running:
            should_restart_based_on_success_flag = True
            if restart_on_success_only and not operation_succeeded:  # Check the flag
                should_restart_based_on_success_flag = False
                logger.warning(
                    f"Context Mgr: Operation for '{server_name}' failed, and restart_on_success_only is True. Skipping restart."
                )

            if should_restart_based_on_success_flag:
                if (
                    not operation_succeeded
                ):  # Still attempt if restart_on_success_only is False
                    logger.warning(
                        f"Context Mgr: Attempting to restart '{server_name}' despite operation error (restart_on_success_only is False or operation succeeded)."
                    )
                else:
                    logger.info(f"Context Mgr: Restarting server '{server_name}'...")

                start_result = api_start_server(server_name, base_dir, mode="detached")
                if start_result.get("status") == "error":
                    logger.error(
                        f"Context Mgr: Failed to restart '{server_name}': {start_result.get('message')}"
                    )
                    if (
                        operation_succeeded
                    ):  # If main op was fine, this error is now primary
                        raise FileOperationError(
                            f"Operation successful, but failed to restart server '{server_name}': {start_result.get('message')}"
                        )
                else:
                    logger.info(
                        f"Context Mgr: Server '{server_name}' restart initiated."
                    )
