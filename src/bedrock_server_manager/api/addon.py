# bedrock_server_manager/api/addon.py
"""API functions for managing addons on Bedrock servers.

This module provides high-level functions to install and manage addons
(e.g., .mcpack, .mcaddon files) for a given Bedrock server instance. It
acts as an interface layer, orchestrating calls to the BedrockServer's
addon processing methods and handling the server lifecycle (stop/start)
during the installation process.
"""
import os
import logging
import threading
from typing import Dict

# Plugin system imports to bridge API functionality.
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.api.utils import server_lifecycle_manager
from bedrock_server_manager.error import (
    BSMError,
    MissingArgumentError,
    AppFileNotFoundError,
    InvalidServerNameError,
    SendCommandError,
    ServerNotRunningError,
)

logger = logging.getLogger(__name__)

# A unified lock to prevent race conditions during addon file operations.
# This ensures that only one addon installation can occur at a time,
# preventing potential file corruption.
_addon_lock = threading.Lock()


@plugin_method("import_addon")
def import_addon(
    server_name: str,
    addon_file_path: str,
    stop_start_server: bool = True,
    restart_only_on_success: bool = True,
) -> Dict[str, str]:
    """Installs an addon to a specified Bedrock server.

    This function handles the import and installation of an addon file
    (.mcaddon or .mcpack) into the server's addon directories. It is
    thread-safe, using a lock to prevent concurrent addon operations which
    could lead to corrupted files.

    The function can optionally manage the server's lifecycle by stopping it
    before the installation and restarting it after.

    Args:
        server_name: The name of the server to install the addon on.
        addon_file_path: The absolute path to the addon file (.mcaddon, .mcpack).
        stop_start_server: If True, the server will be stopped before the
            installation and started afterward. Defaults to True.
        restart_only_on_success: If True and `stop_start_server` is True,
            the server will only be restarted if the addon installation
            succeeds. Defaults to True.

    Returns:
        A dictionary containing the status of the operation ('success', 'error',
        or 'skipped') and a descriptive message.

    Raises:
        MissingArgumentError: If `server_name` or `addon_file_path` is not provided.
        AppFileNotFoundError: If the file at `addon_file_path` does not exist.
        InvalidServerNameError: If the server name is not valid (raised from BedrockServer).
    """
    # Attempt to acquire the lock without blocking. If another addon operation
    # is in progress, skip this one to avoid conflicts.
    if not _addon_lock.acquire(blocking=False):
        logger.warning(
            f"An addon operation for '{server_name}' is already in progress. Skipping concurrent import."
        )
        return {
            "status": "skipped",
            "message": "An addon operation is already in progress.",
        }

    result = {}
    try:
        addon_filename = os.path.basename(addon_file_path) if addon_file_path else "N/A"
        logger.info(
            f"API: Initiating addon import for '{server_name}' from '{addon_filename}'. "
            f"Stop/Start: {stop_start_server}, RestartOnSuccess: {restart_only_on_success}"
        )

        # --- Pre-flight Checks ---
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")
        if not addon_file_path:
            raise MissingArgumentError("Addon file path cannot be empty.")
        if not os.path.isfile(addon_file_path):
            raise AppFileNotFoundError(addon_file_path, "Addon file")

        # --- Plugin Hook: Before Import ---
        plugin_manager.trigger_event(
            "before_addon_import",
            server_name=server_name,
            addon_file_path=addon_file_path,
        )

        try:
            server = BedrockServer(server_name)

            # If the server is running, send a warning message to players.
            if server.is_running():
                try:
                    server.send_command("say Installing addon...")
                except (SendCommandError, ServerNotRunningError) as e:
                    logger.warning(
                        f"API: Failed to send addon installation warning to '{server_name}': {e}"
                    )

            # Use a context manager to handle the server's start/stop lifecycle.
            with server_lifecycle_manager(
                server_name,
                stop_before=stop_start_server,
                start_after=stop_start_server,
                restart_on_success_only=restart_only_on_success,
            ):
                logger.info(
                    f"API: Processing addon file '{addon_filename}' for server '{server_name}'..."
                )
                # Delegate the core file extraction and placement to the server instance.
                server.process_addon_file(addon_file_path)
                logger.info(
                    f"API: Core addon processing completed for '{addon_filename}' on '{server_name}'."
                )

            message = f"Addon '{addon_filename}' installed successfully for server '{server_name}'."
            if stop_start_server:
                message += " Server stop/start cycle handled."
            result = {"status": "success", "message": message}

        except BSMError as e:
            # Handle application-specific errors.
            logger.error(
                f"API: Addon import failed for '{addon_filename}' on '{server_name}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"Error installing addon '{addon_filename}': {e}",
            }

        except Exception as e:
            # Handle any other unexpected errors.
            logger.error(
                f"API: Unexpected error during addon import for '{server_name}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"Unexpected error installing addon: {e}",
            }

        finally:
            # --- Plugin Hook: After Import ---
            # This hook runs regardless of whether the import succeeded or failed.
            plugin_manager.trigger_event(
                "after_addon_import", server_name=server_name, result=result
            )

    finally:
        # Ensure the lock is always released, even if errors occur.
        _addon_lock.release()

    return result
