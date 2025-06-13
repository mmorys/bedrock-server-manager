# bedrock_server_manager/api/utils.py
"""
Provides utility API functions that assist other API modules or perform general tasks.

This includes server validation, server name format checking, status updates,
console attachment (Linux-specific), and a server lifecycle context manager
for safely performing operations that require a server to be temporarily stopped.
"""
import os
import logging
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
import platform

# Local imports
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.core import utils as core_utils
from bedrock_server_manager.api.server import (
    start_server as api_start_server,
    stop_server as api_stop_server,
)
from bedrock_server_manager.error import (
    BSMError,
    UserInputError,
    ServerStartError,
)

logger = logging.getLogger(__name__)
# The global bsm instance can be useful for manager-level tasks like listing all servers
bsm = BedrockServerManager()


def validate_server_exist(server_name: str) -> Dict[str, Any]:
    """
    Validates if a server installation directory and executable exist
    by using the BedrockServer.is_installed() method.
    """
    if not server_name:
        return {"status": "error", "message": "Server name cannot be empty."}

    logger.debug(f"API: Validating existence of server '{server_name}'...")
    try:
        # Instantiate the server; this may raise config errors if settings are bad.
        server = BedrockServer(server_name)

        # is_installed() is a simple boolean check.
        if server.is_installed():
            logger.debug(f"API: Server '{server_name}' validation successful.")
            return {
                "status": "success",
                "message": f"Server '{server_name}' exists and is valid.",
            }
        else:
            logger.debug(
                f"API: Validation failed for '{server_name}'. It is not correctly installed."
            )
            # Providing more specific info from the server object could be useful.
            return {
                "status": "error",
                "message": f"Server '{server_name}' is not installed or the installation is invalid.",
            }

    except BSMError as e:  # Catches config issues from BedrockServer init
        logger.error(
            f"API: Configuration error during validation for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error validating server '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"An unexpected validation error occurred: {e}",
        }


def validate_server_name_format(server_name: str) -> Dict[str, str]:
    """
    Validates the format of a potential server name using core utility functions.

    This function does not depend on an existing server instance.

    Args:
        server_name: The server name string to validate.

    Returns:
        A dictionary indicating success or failure with a message.
    """
    logger.debug(f"API: Validating format for '{server_name}'")
    try:
        core_utils.core_validate_server_name_format(server_name)
        logger.debug(f"API: Format valid for '{server_name}'.")
        return {"status": "success", "message": "Server name format is valid."}
    except UserInputError as e:
        logger.debug(f"API: Invalid format for '{server_name}': {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error for '{server_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def update_server_statuses() -> Dict[str, Any]:
    """
    Updates status in config files based on runtime checks for all servers.
    """
    updated_servers_count = 0
    error_messages = []
    logger.debug("API: Updating all server statuses...")

    try:
        # Use the BSM instance to get the list of servers
        all_servers_data, discovery_errors = bsm.get_servers_data()
        if discovery_errors:
            error_messages.extend(discovery_errors)

        for server_data in all_servers_data:
            server_name = server_data.get("name")
            if not server_name:
                continue

            try:

                logger.info(
                    f"API: Status for '{server_name}' was reconciled by get_servers_data."
                )
                updated_servers_count += 1
            except Exception as e:
                msg = f"Could not update status for server '{server_name}': {e}"
                logger.error(f"API.update_server_statuses: {msg}", exc_info=True)
                error_messages.append(msg)

        if error_messages:
            return {
                "status": "error",
                "message": f"Completed with errors: {'; '.join(error_messages)}",
                "updated_servers_count": updated_servers_count,
            }
        return {
            "status": "success",
            "message": f"Status check completed for {updated_servers_count} servers.",
        }

    except BSMError as e:
        logger.error(f"API: Setup error during status update: {e}", exc_info=True)
        return {"status": "error", "message": f"Error accessing directories: {e}"}
    except Exception as e:
        logger.error(f"API: Unexpected error during status update: {e}", exc_info=True)
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def attach_to_screen_session(server_name: str) -> Dict[str, str]:
    """
    Attempts to attach to the screen session of a running Bedrock server. (Linux-specific).
    """
    if platform.system() != "Linux":
        return {
            "status": "error",
            "message": "Attaching to screen is only supported on Linux.",
        }

    if not server_name:
        return {"status": "error", "message": "Server name cannot be empty."}

    logger.info(f"API: Attempting screen attach for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)

        if not server.is_running():
            msg = f"Cannot attach: Server '{server_name}' is not currently running."
            logger.warning(f"API: {msg}")
            return {"status": "error", "message": msg}

        # The core logic for attaching is simple enough to live here or in a dedicated method.
        # Assuming core_utils.core_execute_screen_attach is still the preferred way.
        screen_session_name = f"bedrock-{server.server_name}"
        success, message = core_utils.core_execute_screen_attach(screen_session_name)

        if success:
            logger.info(
                f"API: Screen attach command issued for '{screen_session_name}'."
            )
            return {"status": "success", "message": message}
        else:
            logger.warning(
                f"API: Screen attach failed for '{screen_session_name}': {message}"
            )
            return {"status": "error", "message": message}

    except BSMError as e:
        logger.error(
            f"API: Prerequisite error for screen attach on '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Error preparing for screen attach: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error during screen attach for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def get_system_and_app_info() -> Dict[str, Any]:
    """
    Retrieves system information and application version using the BedrockServerManager instance.
    """
    logger.debug("API: Requesting system and app info.")
    try:
        data = {"os_type": bsm.get_os_type(), "app_version": bsm.get_app_version()}
        logger.info(f"API: Successfully retrieved system info: {data}")
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"API: Unexpected error getting system info: {e}", exc_info=True)
        return {"status": "error", "message": "An unexpected error occurred."}


@contextmanager
def server_lifecycle_manager(
    server_name: str,
    stop_before: bool,
    start_after: bool = True,
    restart_on_success_only: bool = False,
):
    """
    Context manager to handle stopping a server before an operation and
    restarting it afterward, using the BedrockServer class.

    Args:
        server_name: The name of the server.
        stop_before: If True, stop the server if it's running.
        start_after: If True, restart the server if it was stopped by this manager.
        restart_on_success_only: If True, only attempt restart if the managed
                                 block completed without exceptions.
    """
    server = BedrockServer(server_name)
    was_running = False
    operation_succeeded = True

    if not stop_before:
        logger.debug(
            f"Context Mgr: Stop/Start not flagged for '{server_name}'. Skipping."
        )
        yield
        return

    try:
        if server.is_running():
            was_running = True
            logger.info(f"Context Mgr: Server '{server_name}' is running. Stopping...")
            stop_result = api_stop_server(server_name)
            if stop_result.get("status") == "error":
                error_msg = f"Failed to stop server '{server_name}': {stop_result.get('message')}. Aborted."
                logger.error(error_msg)
                return {"status": "error", "message": error_msg}
            logger.info(f"Context Mgr: Server '{server_name}' stopped.")
        else:
            logger.debug(
                f"Context Mgr: Server '{server_name}' is not running. No stop needed."
            )

        yield  # The wrapped operation runs here

    except Exception:
        operation_succeeded = False
        logger.error(
            f"Context Mgr: Exception occurred during managed operation for '{server_name}'.",
            exc_info=True,
        )
        raise  # Re-raise the exception after logging it
    finally:
        if was_running and start_after:
            should_restart = True
            if restart_on_success_only and not operation_succeeded:
                should_restart = False
                logger.warning(
                    f"Context Mgr: Operation for '{server_name}' failed. Skipping restart as requested."
                )

            if should_restart:
                logger.info(f"Context Mgr: Restarting server '{server_name}'...")
                try:
                    # Using the API function for detached mode is often best here
                    start_result = api_start_server(server_name, mode="detached")
                    if start_result.get("status") == "error":
                        raise ServerStartError(
                            f"Failed to restart '{server_name}': {start_result.get('message')}"
                        )
                    logger.info(
                        f"Context Mgr: Server '{server_name}' restart initiated."
                    )
                except BSMError as e:
                    logger.error(
                        f"Context Mgr: FAILED to restart '{server_name}': {e}",
                        exc_info=True,
                    )
                    # Decide if this should be a critical failure
                    if operation_succeeded:
                        # If the main operation was fine, the failure to restart becomes the primary error.
                        raise
