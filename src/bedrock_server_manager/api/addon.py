# bedrock_server_manager/api/addon.py
"""
Provides API-level functions for managing addons on Bedrock servers.

This acts as an interface layer, orchestrating calls to the BedrockServer's
addon processing methods and handling the server lifecycle during installation.
"""
import os
import logging
from typing import Dict

# Local imports
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


def import_addon(
    server_name: str,
    addon_file_path: str,
    stop_start_server: bool = True,
    restart_only_on_success: bool = True,
) -> Dict[str, str]:
    """
    Installs an addon (.mcaddon or .mcpack) to the specified server.

    Args:
        server_name: The name of the target server.
        addon_file_path: The full path to the addon file to install.
        stop_start_server: If True, stops the server before installation and restarts it after.
        restart_only_on_success: If True, only restarts the server if the addon installation succeeds.

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
        raise AppFileNotFoundError(addon_file_path, "Addon file")

    try:
        server = BedrockServer(server_name)

        if server.is_running():
            try:
                server.send_command("say Installing addon...")
            except (SendCommandError, ServerNotRunningError) as e:
                logger.warning(
                    f"API: Failed to send addon installation warning to '{server_name}': {e}"
                )

        # Use the lifecycle manager to handle stopping and restarting the server.
        with server_lifecycle_manager(
            server_name,
            stop_before=stop_start_server,
            start_after=stop_start_server,  # Ensure start_after is also controlled by this flag
            restart_on_success_only=restart_only_on_success,
        ):
            logger.info(
                f"API: Processing addon file '{addon_filename}' for server '{server_name}'..."
            )
            server.process_addon_file(addon_file_path)
            logger.info(
                f"API: Core addon processing completed for '{addon_filename}' on '{server_name}'."
            )

        message = f"Addon '{addon_filename}' installed successfully for server '{server_name}'."
        if stop_start_server:
            message += " Server stop/start cycle handled."
        return {"status": "success", "message": message}

    except BSMError as e:
        logger.error(
            f"API: Addon import failed for '{addon_filename}' on '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Error installing addon '{addon_filename}': {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error during addon import for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error installing addon: {e}"}
