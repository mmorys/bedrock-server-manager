# bedrock-server-manager/bedrock_server_manager/api/world.py
"""
Provides API-level functions for managing Bedrock server worlds.

This module acts as an interface layer, orchestrating calls to core world
and server functions for tasks like retrieving the current world name,
exporting the world to a .mcworld archive, and importing a world from
a .mcworld archive. Functions typically return a dictionary indicating
success or failure status.
"""

import os
import logging
from typing import Dict, Optional, Any

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
    DirectoryError,
    BackupWorldError,
    RestoreError,
    DownloadExtractError,
    MissingArgumentError,
    FileNotFoundError,
)
from bedrock_server_manager.api.server import start_server, stop_server
from bedrock_server_manager.utils.general import get_base_dir, get_timestamp
from bedrock_server_manager.core.server import (
    server as server_base,
    world as core_world,
)

logger = logging.getLogger("bedrock_server_manager")


def get_world_name(server_name: str, base_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves the configured world name (level-name) for a server.

    Reads the value from the server's `server.properties` file via core functions.

    Args:
        server_name: The name of the server.
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "world_name": str} on success.
        - {"status": "error", "message": str} if the name cannot be retrieved or an error occurs.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"Attempting to get world name for server '{server_name}'...")
    try:
        effective_base_dir = get_base_dir(base_dir)

        # Call the core function which reads server.properties
        # It raises FileOperationError if file/property missing or unreadable
        world_name_str = server_base.get_world_name(server_name, effective_base_dir)

        # The core function now raises if name isn't found, so direct return on success
        logger.info(
            f"Retrieved world name for server '{server_name}': '{world_name_str}'"
        )
        return {"status": "success", "world_name": world_name_str}

    except (
        FileOperationError,
        InvalidServerNameError,
    ) as e:  # Catch specific errors from core or validation
        logger.error(
            f"Failed to get world name for server '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to get world name: {e}"}
    except Exception as e:
        # Catch unexpected errors
        logger.error(
            f"Unexpected error getting world name for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting world name: {e}",
        }


def export_world(
    server_name: str, base_dir: Optional[str] = None, export_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Exports the server's currently configured world to a .mcworld archive file.

    Determines the world path, creates the archive in the specified or default
    export directory (BACKUP_DIR).

    Args:
        server_name: The name of the server whose world should be exported.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        export_dir: Optional. Directory to save the exported .mcworld file.
                    Defaults to the configured BACKUP_DIR setting if None.

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "export_file": str, "message": str} full path to the created file.
        - {"status": "error", "message": str} on failure.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If essential settings (BASE_DIR, BACKUP_DIR) are missing or
                            `base_dir`/`export_dir` cannot be determined/created.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"Initiating world export for server '{server_name}'...")
    try:
        effective_base_dir = get_base_dir(base_dir)

        # Determine and ensure export directory exists
        effective_export_dir: str
        if export_dir:
            effective_export_dir = export_dir
        else:
            backup_base_dir = settings.get("BACKUP_DIR")
            if not backup_base_dir:
                raise FileOperationError("BACKUP_DIR setting missing.")
            # Save into server-specific subfolder within backup dir
            effective_export_dir = os.path.join(backup_base_dir, server_name)

        os.makedirs(effective_export_dir, exist_ok=True)
        logger.debug(f"Using export directory: {effective_export_dir}")

        # Get the world name using the API function (which returns a dict)
        world_name_result = get_world_name(server_name, effective_base_dir)
        if world_name_result.get("status") == "error":
            # Propagate the error message if world name couldn't be found
            logger.error(
                f"Cannot export world for '{server_name}': {world_name_result.get('message')}"
            )
            return world_name_result

        world_name = world_name_result["world_name"]
        world_path = os.path.join(effective_base_dir, server_name, "worlds", world_name)

        # Check world directory exists before attempting export
        if not os.path.isdir(world_path):
            raise DirectoryError(
                f"World directory '{world_name}' not found at expected location: {world_path}"
            )

        # Construct export filename
        timestamp = get_timestamp()
        export_filename = f"{world_name}_export_{timestamp}.mcworld"
        export_file_path = os.path.join(effective_export_dir, export_filename)

        logger.info(
            f"Exporting world '{world_name}' from '{world_path}' to '{export_file_path}'..."
        )

        # Call the core export function
        core_world.export_world(
            world_path, export_file_path
        )  # Raises BackupWorldError, DirectoryError, FileOperationError

        logger.info(
            f"World for server '{server_name}' exported successfully to '{export_file_path}'."
        )
        return {
            "status": "success",
            "export_file": export_file_path,
            "message": "World exported successfully.",
        }

    except (
        DirectoryError,
        BackupWorldError,
        FileOperationError,
        InvalidServerNameError,
    ) as e:
        # Catch specific errors from core functions or setup
        logger.error(
            f"Failed to export world for server '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to export world: {e}"}
    except Exception as e:
        # Catch unexpected errors
        logger.error(
            f"Unexpected error exporting world for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Unexpected error exporting world: {e}"}


def import_world(
    server_name: str,
    selected_file_path: str,
    base_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """
    Imports a world from a .mcworld file, replacing the server's current world.

    Determines the target world directory based on `server.properties`, optionally
    stops/starts the server, and calls the core extraction function.

    Args:
        server_name: The name of the server to import the world into.
        selected_file_path: The full path to the .mcworld file to import.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        stop_start_server: If True, stop server before import and restart after if it was running.

    Returns:
        A dictionary indicating the outcome: `{"status": "success", "message": ...}` or
        `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name` or `selected_file_path` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileNotFoundError: If `selected_file_path` does not exist.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not selected_file_path:
        raise MissingArgumentError(".mcworld file path cannot be empty.")

    selected_filename = os.path.basename(selected_file_path)
    logger.info(
        f"Initiating world import for server '{server_name}' from file '{selected_filename}'. Stop/Start: {stop_start_server}"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        # Check source file exists before potentially stopping server
        if not os.path.isfile(selected_file_path):
            raise FileNotFoundError(
                f"Source .mcworld file not found: {selected_file_path}"
            )

    except (FileOperationError, FileNotFoundError) as e:
        logger.error(
            f"Pre-import check failed for world import on server '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Configuration error or source file not found: {e}",
        }

    was_running = False
    # --- Server Stop ---
    if stop_start_server:
        try:
            logger.debug(
                f"Checking running status for '{server_name}' before world import..."
            )
            if system_base.is_server_running(server_name, effective_base_dir):
                was_running = True
                logger.info(
                    f"Server '{server_name}' is running. Stopping for world import..."
                )
                stop_result = stop_server(
                    server_name, effective_base_dir
                )  # API func returns dict
                if stop_result.get("status") == "error":
                    logger.error(
                        f"Failed to stop server '{server_name}' for import: {stop_result.get('message')}"
                    )
                    return stop_result
                logger.info(f"Server '{server_name}' stopped.")
            else:
                logger.debug(f"Server '{server_name}' is not running.")
        except Exception as e:
            logger.error(
                f"Error stopping server '{server_name}' for world import: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Failed to stop server for import: {e}",
            }

    # --- Core Import/Extraction Operation ---
    import_error = None
    try:
        # Get world name (API function returns dict)
        world_name_result = get_world_name(server_name, effective_base_dir)
        if world_name_result.get("status") == "error":
            raise FileOperationError(
                world_name_result.get("message", "Could not determine world name.")
            )

        world_name = world_name_result["world_name"]
        # Construct full path to target world directory
        target_world_dir = os.path.join(
            effective_base_dir, server_name, "worlds", world_name
        )
        logger.info(f"Target directory for world import: {target_world_dir}")

        # Call core function to extract (handles cleaning target dir)
        # Raises FileNotFoundError, DownloadExtractError, FileOperationError
        core_world.extract_world(selected_file_path, target_world_dir)
        logger.info(
            f"Core world extraction function completed for server '{server_name}'."
        )

    except (
        FileNotFoundError,
        DownloadExtractError,
        FileOperationError,
        DirectoryError,
        InvalidServerNameError,
    ) as e:
        import_error = e
        logger.error(
            f"World import failed for server '{server_name}' from '{selected_filename}': {e}",
            exc_info=True,
        )
    except Exception as e:
        import_error = e
        logger.error(
            f"Unexpected error during world import for server '{server_name}': {e}",
            exc_info=True,
        )

    # --- Server Restart ---
    finally:
        restart_error_dict = None
        if stop_start_server and was_running:
            if import_error:
                logger.warning(
                    f"Attempting to restart server '{server_name}' even though world import failed."
                )
            else:
                logger.info(f"Restarting server '{server_name}' after world import...")
            try:
                start_result = start_server(
                    server_name, effective_base_dir
                )  # API func returns dict
                if start_result.get("status") == "error":
                    logger.error(
                        f"Failed to restart server '{server_name}' after import: {start_result.get('message')}"
                    )
                    restart_error_dict = start_result
                else:
                    logger.info(f"Server '{server_name}' restart initiated.")
            except Exception as e:
                logger.error(
                    f"Unexpected error restarting server '{server_name}' after import: {e}",
                    exc_info=True,
                )
                restart_error_dict = {
                    "status": "error",
                    "message": f"Unexpected error restarting server: {e}",
                }

    # --- Final Result ---
    if import_error:
        # Use RestoreError conceptually for import failures at API level
        wrapped_error = RestoreError(f"World import failed: {import_error}")
        return {"status": "error", "message": str(wrapped_error)}
    elif restart_error_dict:
        return restart_error_dict
    else:
        return {
            "status": "success",
            "message": f"World import from '{selected_filename}' completed successfully.",
        }
