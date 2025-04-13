# bedrock-server-manager/bedrock_server_manager/api/addon.py
"""
Provides API-level functions for managing addons on Bedrock servers.

This acts as an interface layer, orchestrating calls to core addon processing
functions and handling potential server stop/start operations during installation.
"""

import os
import logging
from typing import Dict, Optional

# Local imports
from bedrock_server_manager.core.server import addon as core_addon
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.error import (
    MissingArgumentError,
    FileOperationError,
    FileNotFoundError,
)
from bedrock_server_manager.api.server import (
    start_server,
    stop_server,
)

logger = logging.getLogger("bedrock_server_manager")


def import_addon(
    server_name: str,
    addon_file_path: str,
    base_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """
    Installs an addon (.mcaddon or .mcpack) to the specified server.

    Handles finding the server directory, optionally stopping the server before
    installation and restarting it afterwards, processing the addon file using
    core functions, and returning a status dictionary.

    Args:
        server_name: The name of the target server.
        addon_file_path: The full path to the addon file to install.
        base_dir: Optional. The base directory containing server installations.
                  If None, uses the configured default.
        stop_start_server: If True (default), attempts to stop the server before
                           installing and restart it afterwards if it was initially running.

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "message": "Addon installed successfully."} on success.
        - {"status": "error", "message": "Error description..."} on failure.

    Raises:
        MissingArgumentError: If `server_name` or `addon_file_path` is empty.
        FileNotFoundError: If `addon_file_path` does not point to an existing file.
        FileOperationError: If `base_dir` cannot be determined (e.g., setting missing).
        # Underlying exceptions from server stop/start/addon processing are caught
        # and converted into the error dictionary return format.
    """
    addon_filename = os.path.basename(addon_file_path) if addon_file_path else "N/A"
    logger.info(
        f"Initiating addon import process for server '{server_name}' from file '{addon_filename}'."
    )

    # --- Input Validation ---
    if not server_name:
        # Raise immediately for invalid input
        raise MissingArgumentError("Server name cannot be empty.")
    if not addon_file_path:
        raise MissingArgumentError("Addon file path cannot be empty.")
    if not os.path.isfile(addon_file_path):
        # Check if it's specifically a file, not just exists
        error_msg = f"Addon file does not exist or is not a file: {addon_file_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        # Determine base directory (raises FileOperationError if setting missing)
        effective_base_dir = get_base_dir(base_dir)
        logger.debug(f"Using base directory: {effective_base_dir}")
    except FileOperationError as e:
        logger.error(f"Cannot proceed with addon import: {e}", exc_info=True)
        # Convert to the return dict format for API consistency at this boundary
        return {"status": "error", "message": f"Configuration error: {e}"}

    # --- Server Stop (Optional) ---
    was_running = False
    if stop_start_server:
        try:
            logger.debug(
                f"Checking if server '{server_name}' is running before addon import..."
            )
            # Check running status before attempting stop
            if system_base.is_server_running(server_name, effective_base_dir):
                was_running = True
                logger.info(
                    f"Server '{server_name}' is running. Stopping before addon installation..."
                )
                stop_result = stop_server(
                    server_name, effective_base_dir
                )  # This function returns a dict
                if stop_result.get("status") == "error":
                    logger.error(
                        f"Failed to stop server '{server_name}' before addon import: {stop_result.get('message')}"
                    )
                    # Return the error from stop_server directly
                    return stop_result
                logger.info(f"Server '{server_name}' stopped successfully.")
            else:
                logger.debug(f"Server '{server_name}' is not running. No stop needed.")
        except Exception as e:
            # Catch unexpected errors during check/stop
            logger.error(
                f"Error stopping server '{server_name}' before addon import: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Failed to stop server before import: {e}",
            }

    # --- Addon Installation ---
    install_error = None
    try:
        logger.info(
            f"Processing addon file '{addon_filename}' for server '{server_name}'..."
        )
        # Delegate to the core addon processing function
        core_addon.process_addon(addon_file_path, server_name, effective_base_dir)
        logger.info(
            f"Core addon processing completed for '{addon_filename}' on server '{server_name}'."
        )
        # Success is determined after potential restart below

    except Exception as e:
        # Catch errors from core_addon.process_addon and store them
        install_error = e
        logger.error(
            f"Core addon processing failed for '{addon_filename}' on server '{server_name}': {e}",
            exc_info=True,
        )
        # Don't return yet, proceed to finally block for potential restart

    # --- Server Start (Optional, runs even if install failed) ---
    finally:
        restart_error = None
        if stop_start_server and was_running:
            if install_error:
                logger.warning(
                    f"Attempting to restart server '{server_name}' even though addon processing failed."
                )
            else:
                logger.info(
                    f"Restarting server '{server_name}' after addon processing..."
                )

            try:
                start_result = start_server(
                    server_name, effective_base_dir
                )  # This function returns a dict
                if start_result.get("status") == "error":
                    logger.error(
                        f"Failed to restart server '{server_name}' after addon processing: {start_result.get('message')}"
                    )
                    restart_error = start_result  # Store the error dict
                else:
                    logger.info(
                        f"Server '{server_name}' restart initiated successfully."
                    )
            except Exception as e:
                logger.error(
                    f"Unexpected error restarting server '{server_name}' after addon processing: {e}",
                    exc_info=True,
                )
                restart_error = {
                    "status": "error",
                    "message": f"Unexpected error restarting server: {e}",
                }

    # --- Determine Final Result ---
    if install_error:
        # If installation failed, report that error primarily
        return {
            "status": "error",
            "message": f"Error installing addon '{addon_filename}': {install_error}",
        }
    elif restart_error:
        # If installation succeeded but restart failed, report the restart error
        # This indicates addon files might be present but server isn't running as expected
        return restart_error
    else:
        # Installation succeeded, and restart either wasn't needed, wasn't attempted, or succeeded
        return {
            "status": "success",
            "message": f"Addon '{addon_filename}' installed successfully for server '{server_name}'.",
        }
