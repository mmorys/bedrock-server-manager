# bedrock_server_manager/api/world.py
"""
Provides API-level functions for managing Bedrock server worlds by wrapping
methods of the BedrockServer class.
"""

import os
import logging
from typing import Dict, Optional, Any

# Local imports
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.api.utils import server_lifecycle_manager
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    FileOperationError,
    MissingArgumentError,
)
from bedrock_server_manager.utils.general import get_timestamp

logger = logging.getLogger(__name__)


def get_world_name(server_name: str) -> Dict[str, Any]:
    """
    Retrieves the configured world name (level-name) for a server.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"API: Attempting to get world name for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)
        world_name_str = server.get_world_name()
        logger.info(
            f"API: Retrieved world name for '{server_name}': '{world_name_str}'"
        )
        return {"status": "success", "world_name": world_name_str}
    except BSMError as e:
        logger.error(
            f"API: Failed to get world name for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to get world name: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting world name for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting world name: {e}",
        }


def export_world(
    server_name: str,
    export_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> Dict[str, Any]:
    """
    Exports the server's currently active world to a .mcworld archive file.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(
        f"API: Initiating world export for '{server_name}' (Stop/Start: {stop_start_server})"
    )

    try:
        server = BedrockServer(server_name)

        if server.is_running():
            try:
                server.send_command("say Exporting world...")
            except BSMError as e:
                logger.warning(
                    f"API: Failed to send world export warning to '{server_name}': {e}"
                )

        # Determine export directory
        if export_dir:
            effective_export_dir = export_dir
        else:
            content_base_dir = settings.get("CONTENT_DIR")
            if not content_base_dir:
                raise FileOperationError(
                    "BACKUP_DIR setting missing for default export directory."
                )
            effective_export_dir = os.path.join(content_base_dir, "worlds")
        os.makedirs(effective_export_dir, exist_ok=True)

        world_name_str = server.get_world_name()

        timestamp = get_timestamp()
        export_filename = f"{world_name_str}_export_{timestamp}.mcworld"
        export_file_path = os.path.join(effective_export_dir, export_filename)

        with server_lifecycle_manager(server_name, stop_before=stop_start_server):
            logger.info(
                f"API: Exporting world '{world_name_str}' to '{export_file_path}'..."
            )
            server.export_world_directory_to_mcworld(world_name_str, export_file_path)

        logger.info(
            f"API: World for server '{server_name}' exported to '{export_file_path}'."
        )
        return {
            "status": "success",
            "export_file": export_file_path,
            "message": f"World '{world_name_str}' exported successfully to {export_filename}.",
        }
    except (BSMError, ValueError) as e:
        logger.error(
            f"API: Failed to export world for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to export world: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error exporting world for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error exporting world: {e}"}


def import_world(
    server_name: str,
    selected_file_path: str,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """
    Imports a world from a .mcworld file, replacing the server's currently active world.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not selected_file_path:
        raise MissingArgumentError(".mcworld file path cannot be empty.")

    selected_filename = os.path.basename(selected_file_path)
    logger.info(
        f"API: Initiating world import for '{server_name}' from '{selected_filename}' (Stop/Start: {stop_start_server})"
    )

    try:
        server = BedrockServer(server_name)
        if not os.path.isfile(selected_file_path):
            raise FileNotFoundError(
                f"Source .mcworld file not found: {selected_file_path}"
            )

        if server.is_running():
            try:
                server.send_command("say Importing world...")
            except BSMError as e:
                logger.warning(
                    f"API: Failed to send world import warning to '{server_name}': {e}"
                )

        imported_world_name: Optional[str] = None
        with server_lifecycle_manager(server_name, stop_before=stop_start_server):
            logger.info(
                f"API: Importing world from '{selected_filename}' into server '{server_name}'..."
            )
            imported_world_name = server.import_active_world_from_mcworld(
                selected_file_path
            )

        logger.info(
            f"API: World import from '{selected_filename}' for server '{server_name}' completed."
        )
        return {
            "status": "success",
            "message": f"World '{imported_world_name or 'Unknown'}' imported successfully from {selected_filename}.",
        }
    except (BSMError, FileNotFoundError) as e:
        logger.error(
            f"API: Failed to import world for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to import world: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error importing world for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error importing world: {e}"}


def reset_world(server_name: str) -> Dict[str, str]:
    """
    Resets the server's world by deleting the currently active world directory.
    The server is stopped before deletion and restarted after if it was running.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty for API request.")

    logger.info(f"API: Initiating world reset for server '{server_name}'...")

    try:
        server = BedrockServer(server_name)
        world_name_for_msg = server.get_world_name()

        if server.is_running():
            try:
                server.send_command("say WARNING: Resetting world")
            except BSMError as e:
                logger.warning(
                    f"API: Failed to send world reset warning to '{server_name}': {e}"
                )

        # The context manager handles stop/start. restart_on_success_only is True
        # to prevent starting a server with a now-deleted world if deletion fails.
        with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
        ):
            logger.info(
                f"API: Attempting to delete world directory for world '{world_name_for_msg}'..."
            )
            server.delete_active_world_directory()

        logger.info(
            f"API: World '{world_name_for_msg}' for server '{server_name}' has been successfully reset."
        )
        return {
            "status": "success",
            "message": f"World '{world_name_for_msg}' reset successfully.",
        }
    except BSMError as e:
        logger.error(
            f"API: Failed to reset world for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to reset world: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error resetting world for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"An unexpected error occurred while resetting the world: {e}",
        }
