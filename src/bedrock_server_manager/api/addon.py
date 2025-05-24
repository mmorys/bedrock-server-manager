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
from bedrock_server_manager.error import (
    MissingArgumentError,
    FileOperationError,
    FileNotFoundError,
    InvalidAddonPackTypeError,
    AddonExtractError,
    DirectoryError,
    InvalidServerNameError,
    RestoreError,
)
from bedrock_server_manager.api.utils import _server_stop_start_manager

logger = logging.getLogger("bedrock_server_manager")


def import_addon(
    server_name: str,
    addon_file_path: str,
    base_dir: Optional[str] = None,
    stop_start_server: bool = True,
    restart_only_on_success: bool = True,
) -> Dict[str, str]:
    """
    Installs an addon (.mcaddon or .mcpack) to the specified server.

    Args:
        server_name: The name of the target server.
        addon_file_path: The full path to the addon file to install.
        base_dir: Optional. Base directory for server installations.
        stop_start_server: If True, attempts to stop/start server around addon processing.
        restart_only_on_success: If stop_start_server is True, only restart if addon
                                 processing itself was successful.

    Returns:
        A dictionary indicating the outcome.
    """
    addon_filename = os.path.basename(addon_file_path) if addon_file_path else "N/A"
    logger.info(
        f"API: Initiating addon import for '{server_name}' from '{addon_filename}'. "
        f"Stop/Start: {stop_start_server}, RestartOnSuccess: {restart_only_on_success}"
    )

    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not addon_file_path:
        raise MissingArgumentError("Addon file path cannot be empty.")
    if not os.path.isfile(addon_file_path):
        raise FileNotFoundError(f"Addon file not found: {addon_file_path}")

    try:
        effective_base_dir = get_base_dir(base_dir)
        logger.debug(f"API: Using base directory: {effective_base_dir}")

        # The _server_stop_start_manager will handle stopping the server if stop_start_server is True,
        # and restarting it in its finally block based on was_running and restart_only_on_success.
        with _server_stop_start_manager(
            server_name,
            effective_base_dir,
            stop_start_flag=stop_start_server,
            restart_on_success_only=restart_only_on_success,
        ):
            logger.info(
                f"API: Processing addon file '{addon_filename}' for server '{server_name}'..."
            )
            # Delegate to the core addon processing function.
            # This function will raise specific errors (AddonExtractError, FileOperationError, etc.) on failure.
            core_addon.process_addon(addon_file_path, server_name, effective_base_dir)
            logger.info(
                f"API: Core addon processing completed for '{addon_filename}' on '{server_name}'."
            )

        # If the 'with' block completed without an exception, the main operation was successful.
        # The context manager handles the restart if needed.
        message = f"Addon '{addon_filename}' installed successfully for server '{server_name}'."
        if stop_start_server:
            message += " Server stop/start cycle handled."
        return {"status": "success", "message": message}

    # Catch specific errors that can be raised by core_addon.process_addon or the context manager
    except (
        MissingArgumentError,
        FileNotFoundError,
        FileOperationError,
        AddonExtractError,
        InvalidAddonPackTypeError,
        DirectoryError,
        InvalidServerNameError,
        RestoreError,
    ) as e:
        logger.error(
            f"API: Addon import failed for '{addon_filename}' on '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Error installing addon '{addon_filename}': {e}",
        }
    except (
        Exception
    ) as e:  # Catch any other unexpected errors, including from _server_stop_start_manager's finally block
        logger.error(
            f"API: Unexpected error during addon import for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error installing addon: {e}"}
