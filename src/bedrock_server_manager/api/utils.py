# bedrock_server_manager/api/utils.py
"""Provides utility functions and context managers for the API layer.

This module contains helper functions that support other API modules or
perform general tasks. It includes server existence and name format validation,
a function to reconcile the status of all servers, and a critical context
manager (`server_lifecycle_manager`) for safely performing operations that
require a server to be temporarily stopped.
"""
import os
import logging
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
import platform

# Plugin system imports to bridge API functionality.
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
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
# A global BedrockServerManager instance for manager-level tasks like listing all servers.
bsm = BedrockServerManager()


@plugin_method("validate_server_exist")
def validate_server_exist(server_name: str) -> Dict[str, Any]:
    """Validates if a server is correctly installed.

    This function checks for the existence of the server's directory and its
    executable by wrapping the `BedrockServer.is_installed()` method.

    Args:
        server_name: The name of the server to validate.

    Returns:
        A dictionary with the operation status and a message.
        On success: `{"status": "success", "message": "..."}`.
        On failure: `{"status": "error", "message": "..."}`.
    """
    if not server_name:
        return {"status": "error", "message": "Server name cannot be empty."}

    logger.debug(f"API: Validating existence of server '{server_name}'...")
    try:
        # Instantiating BedrockServer also validates underlying configurations.
        server = BedrockServer(server_name)

        # is_installed() returns a simple boolean.
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
            return {
                "status": "error",
                "message": f"Server '{server_name}' is not installed or the installation is invalid.",
            }

    except BSMError as e:  # Catches config issues from BedrockServer instantiation.
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


@plugin_method("validate_server_name_format")
def validate_server_name_format(server_name: str) -> Dict[str, str]:
    """Validates the format of a potential server name.

    This is a stateless check and does not verify if the server actually exists.
    It is used to ensure new server names are valid before creation.

    Args:
        server_name: The server name string to validate.

    Returns:
        A dictionary with a 'status' of 'success' or 'error', and a 'message'
        if validation fails.
    """
    logger.debug(f"API: Validating format for '{server_name}'")
    try:
        # Delegate validation to the core utility function.
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
    """Reconciles the status in config files with the runtime state for all servers.

    This function iterates through all detected servers and updates the 'status'
    field in their respective configuration files to match whether the server
    process is actually running.

    Returns:
        A dictionary summarizing the operation, including any errors that
        occurred for individual servers.
    """
    updated_servers_count = 0
    error_messages = []
    logger.debug("API: Updating all server statuses...")

    try:
        # get_servers_data() from the manager now handles the reconciliation internally.
        # It returns both the server data and any errors encountered during discovery.
        all_servers_data, discovery_errors = bsm.get_servers_data()
        if discovery_errors:
            error_messages.extend(discovery_errors)

        for server_data in all_servers_data:
            server_name = server_data.get("name")
            if not server_name:
                continue

            try:
                # The status is already reconciled by the get_servers_data call.
                logger.info(
                    f"API: Status for '{server_name}' was reconciled by get_servers_data."
                )
                updated_servers_count += 1
            except Exception as e:
                # This block catches errors if processing a specific server's data fails post-discovery.
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
    """Attaches the current terminal to a server's screen session (Linux-only).

    Args:
        server_name: The name of the server whose screen session to attach to.

    Returns:
        A dictionary with the operation status and a message. Returns an error
        on non-Linux systems or if the server is not running in a screen.
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

        # Delegate the actual screen command execution to the core utility.
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


@plugin_method("get_system_and_app_info")
def get_system_and_app_info() -> Dict[str, Any]:
    """Retrieves basic system and application information.

    Returns:
        A dictionary containing the OS type and the application version.
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
    """A context manager to safely stop and restart a server for an operation.

    This manager will stop a server if it is running, yield control to the
    wrapped code block, and then handle restarting the server in its `finally`
    clause, ensuring the server attempts to return to its original state even
    if the operation fails.

    Args:
        server_name: The name of the server to manage.
        stop_before: If True, the server will be stopped if it's running before
            the `with` block is entered.
        start_after: If True, the server will be restarted after the `with`
            block if it was running initially. Defaults to True.
        restart_on_success_only: If True, the server will only be restarted if
            the `with` block completes without raising an exception.
            Defaults to False.

    Yields:
        None.

    Raises:
        ServerStartError: If the server fails to restart after the operation.
        Exception: Re-raises any exception that occurs within the `with` block.
    """
    server = BedrockServer(server_name)
    was_running = False
    operation_succeeded = True

    # If the operation doesn't require a server stop, just yield and exit.
    if not stop_before:
        logger.debug(
            f"Context Mgr: Stop/Start not flagged for '{server_name}'. Skipping."
        )
        yield
        return

    try:
        # --- PRE-OPERATION: STOP SERVER ---
        if server.is_running():
            was_running = True
            logger.info(f"Context Mgr: Server '{server_name}' is running. Stopping...")
            stop_result = api_stop_server(server_name)
            if stop_result.get("status") == "error":
                error_msg = f"Failed to stop server '{server_name}': {stop_result.get('message')}. Aborted."
                logger.error(error_msg)
                # Do not proceed if the server can't be stopped.
                return {"status": "error", "message": error_msg}
            logger.info(f"Context Mgr: Server '{server_name}' stopped.")
        else:
            logger.debug(
                f"Context Mgr: Server '{server_name}' is not running. No stop needed."
            )

        # Yield control to the wrapped code block.
        yield

    except Exception:
        # If an error occurs in the `with` block, record it and re-raise.
        operation_succeeded = False
        logger.error(
            f"Context Mgr: Exception occurred during managed operation for '{server_name}'.",
            exc_info=True,
        )
        raise
    finally:
        # --- POST-OPERATION: RESTART SERVER ---
        # Only restart if the server was running initially and `start_after` is true.
        if was_running and start_after:
            should_restart = True
            # If `restart_on_success_only` is set, check if the operation failed.
            if restart_on_success_only and not operation_succeeded:
                should_restart = False
                logger.warning(
                    f"Context Mgr: Operation for '{server_name}' failed. Skipping restart as requested."
                )

            if should_restart:
                logger.info(f"Context Mgr: Restarting server '{server_name}'...")
                try:
                    # Use the API function to ensure detached mode and proper handling.
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
                    # If the original operation succeeded, the failure to restart
                    # becomes the primary error to report.
                    if operation_succeeded:
                        raise
