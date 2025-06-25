# bedrock_server_manager/api/world.py
"""Provides API functions for managing Bedrock server worlds.

This module wraps methods of the `BedrockServer` class to provide high-level,
thread-safe operations for getting world information, exporting worlds to
`.mcworld` files, importing worlds, and resetting them. It uses a unified
lock to prevent concurrent file operations and a lifecycle manager to
safely stop and restart the server when required.
"""

import os
import logging
import threading
from typing import Dict, Optional, Any

# Plugin system imports to bridge API functionality.
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
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

# A unified lock to prevent race conditions during any world file operation
# (export, import, reset). This ensures data integrity.
_world_lock = threading.Lock()


@plugin_method("get_world_name")
def get_world_name(server_name: str) -> Dict[str, Any]:
    """Retrieves the configured world name (`level-name`) for a server.

    This function reads the `server.properties` file to get the name of the
    directory where the world data is stored.

    Args:
        server_name: The name of the server to query.

    Returns:
        A dictionary with the operation status and the world name.
        On success: `{"status": "success", "world_name": "..."}`.
        On error: `{"status": "error", "message": "..."}`.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
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


@plugin_method("export_world")
def export_world(
    server_name: str,
    export_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> Dict[str, Any]:
    """Exports the server's currently active world to a .mcworld archive.

    This operation is thread-safe. It can optionally stop the server before
    the export and restart it afterward to ensure file consistency.

    Args:
        server_name: The name of the server whose world will be exported.
        export_dir: The directory to save the exported file in. If None, it
            defaults to the application's content directory.
        stop_start_server: If True, the server will be stopped before the
            export and restarted after. Defaults to True.

    Returns:
        A dictionary with the operation status, the path to the exported
        file, and a message.
    """
    if not _world_lock.acquire(blocking=False):
        logger.warning(
            f"A world operation for '{server_name}' is already in progress. Skipping concurrent export."
        )
        return {
            "status": "skipped",
            "message": "A world operation is already in progress.",
        }

    result = {}
    try:
        if not server_name:
            raise InvalidServerNameError("Server name cannot be empty.")

        # Determine the effective export directory before triggering hooks.
        if export_dir:
            effective_export_dir = export_dir
        else:
            content_base_dir = settings.get("CONTENT_DIR")
            if not content_base_dir:
                raise FileOperationError(
                    "CONTENT_DIR setting missing for default export directory."
                )
            effective_export_dir = os.path.join(content_base_dir, "worlds")

        plugin_manager.trigger_event(
            "before_world_export",
            server_name=server_name,
            export_dir=effective_export_dir,
        )
        logger.info(
            f"API: Initiating world export for '{server_name}' (Stop/Start: {stop_start_server})"
        )

        try:
            server = BedrockServer(server_name)

            os.makedirs(effective_export_dir, exist_ok=True)
            world_name_str = server.get_world_name()
            timestamp = get_timestamp()
            export_filename = f"{world_name_str}_export_{timestamp}.mcworld"
            export_file_path = os.path.join(effective_export_dir, export_filename)

            # Use the lifecycle manager to handle stopping and starting the server.
            with server_lifecycle_manager(server_name, stop_before=stop_start_server):
                logger.info(
                    f"API: Exporting world '{world_name_str}' to '{export_file_path}'..."
                )
                server.export_world_directory_to_mcworld(
                    world_name_str, export_file_path
                )

            logger.info(
                f"API: World for server '{server_name}' exported to '{export_file_path}'."
            )
            result = {
                "status": "success",
                "export_file": export_file_path,
                "message": f"World '{world_name_str}' exported successfully to {export_filename}.",
            }

        except (BSMError, ValueError) as e:
            logger.error(
                f"API: Failed to export world for '{server_name}': {e}", exc_info=True
            )
            result = {"status": "error", "message": f"Failed to export world: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error exporting world for '{server_name}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"Unexpected error exporting world: {e}",
            }
        finally:
            plugin_manager.trigger_event(
                "after_world_export", server_name=server_name, result=result
            )

    finally:
        _world_lock.release()

    return result


@plugin_method("import_world")
def import_world(
    server_name: str,
    selected_file_path: str,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """Imports a world from a .mcworld file, replacing the active world.

    This is a destructive operation that replaces the current world. It is
    thread-safe and manages the server lifecycle to ensure data integrity.

    Args:
        server_name: The name of the server to import the world into.
        selected_file_path: The absolute path to the .mcworld file.
        stop_start_server: If True, the server will be stopped before the
            import and restarted after. Defaults to True.

    Returns:
        A dictionary with the operation status and a message.
    """
    if not _world_lock.acquire(blocking=False):
        logger.warning(
            f"A world operation for '{server_name}' is already in progress. Skipping concurrent import."
        )
        return {
            "status": "skipped",
            "message": "A world operation is already in progress.",
        }

    result = {}
    try:
        if not server_name:
            raise InvalidServerNameError("Server name cannot be empty.")
        if not selected_file_path:
            raise MissingArgumentError(".mcworld file path cannot be empty.")

        plugin_manager.trigger_event(
            "before_world_import", server_name=server_name, file_path=selected_file_path
        )
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

            imported_world_name: Optional[str] = None
            # Use the lifecycle manager to ensure the server is stopped during the import.
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
            result = {
                "status": "success",
                "message": f"World '{imported_world_name or 'Unknown'}' imported successfully from {selected_filename}.",
            }

        except (BSMError, FileNotFoundError) as e:
            logger.error(
                f"API: Failed to import world for '{server_name}': {e}", exc_info=True
            )
            result = {"status": "error", "message": f"Failed to import world: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error importing world for '{server_name}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"Unexpected error importing world: {e}",
            }
        finally:
            plugin_manager.trigger_event(
                "after_world_import", server_name=server_name, result=result
            )

    finally:
        _world_lock.release()

    return result


@plugin_method("reset_world")
def reset_world(server_name: str) -> Dict[str, str]:
    """Resets the server's world by deleting the active world directory.

    This is a destructive action. Upon next start, the server will generate
    a new world based on its `server.properties` configuration. This function
    is thread-safe and manages the server lifecycle.

    Args:
        server_name: The name of the server whose world will be reset.

    Returns:
        A dictionary with the operation status and a message.
    """
    if not _world_lock.acquire(blocking=False):
        logger.warning(
            f"A world operation for '{server_name}' is already in progress. Skipping concurrent reset."
        )
        return {
            "status": "skipped",
            "message": "A world operation is already in progress.",
        }

    result = {}
    try:
        if not server_name:
            raise InvalidServerNameError("Server name cannot be empty for API request.")

        plugin_manager.trigger_event("before_world_reset", server_name=server_name)
        logger.info(f"API: Initiating world reset for server '{server_name}'...")

        try:
            server = BedrockServer(server_name)
            world_name_for_msg = server.get_world_name()

            # The lifecycle manager ensures the server is stopped, the world is deleted,
            # and the server is restarted (which will generate the new world).
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
            result = {
                "status": "success",
                "message": f"World '{world_name_for_msg}' reset successfully.",
            }

        except BSMError as e:
            logger.error(
                f"API: Failed to reset world for '{server_name}': {e}", exc_info=True
            )
            result = {"status": "error", "message": f"Failed to reset world: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error resetting world for '{server_name}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"An unexpected error occurred while resetting the world: {e}",
            }
        finally:
            plugin_manager.trigger_event(
                "after_world_reset", server_name=server_name, result=result
            )

    finally:
        _world_lock.release()

    return result
