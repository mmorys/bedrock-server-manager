# bedrock-server-manager/bedrock_server_manager/api/world.py
"""
Provides API-level functions for managing Bedrock server worlds.
"""

import os
import logging
from typing import Dict, Optional, Any

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.api.utils import _server_stop_start_manager
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
    DirectoryError,
    BackupWorldError,
    RestoreError,     
    DownloadExtractError,
    MissingArgumentError,
    FileNotFoundError,
    AddonExtractError,
)
from bedrock_server_manager.utils.general import get_base_dir, get_timestamp
from bedrock_server_manager.core.server import (
    server as core_server_base,
    world as core_world,
)

logger = logging.getLogger("bedrock_server_manager")


def get_world_name(server_name: str, base_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves the configured world name (level-name) for a server.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"API: Attempting to get world name for server '{server_name}'...")
    try:
        effective_base_dir = get_base_dir(base_dir)
        world_name_str = core_server_base.get_world_name(server_name, effective_base_dir)
        logger.info(f"API: Retrieved world name for '{server_name}': '{world_name_str}'")
        return {"status": "success", "world_name": world_name_str}
    except (FileOperationError, InvalidServerNameError) as e:
        logger.error(f"API: Failed to get world name for '{server_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to get world name: {e}"}
    except Exception as e:
        logger.error(f"API: Unexpected error getting world name for '{server_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error getting world name: {e}"}


def export_world(
    server_name: str,
    base_dir: Optional[str] = None,
    export_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> Dict[str, Any]:
    """
    Exports the server's currently configured world to a .mcworld archive file.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Initiating world export for server '{server_name}' (Stop/Start: {stop_start_server})")

    try:
        effective_base_dir = get_base_dir(base_dir)
        effective_export_dir: str
        if export_dir:
            effective_export_dir = export_dir
        else:
            backup_base_dir = settings.get("BACKUP_DIR")
            if not backup_base_dir:
                raise FileOperationError("BACKUP_DIR setting missing for default export directory.")
            effective_export_dir = os.path.join(backup_base_dir, server_name)
        os.makedirs(effective_export_dir, exist_ok=True)

        # Get world name directly from core
        world_name_str = core_server_base.get_world_name(server_name, effective_base_dir)
        world_path = os.path.join(effective_base_dir, server_name, "worlds", world_name_str)

        if not os.path.isdir(world_path):
            raise DirectoryError(f"World directory '{world_name_str}' not found at: {world_path}")

        timestamp = get_timestamp()
        export_filename = f"{world_name_str}_export_{timestamp}.mcworld"
        export_file_path = os.path.join(effective_export_dir, export_filename)

        with _server_stop_start_manager(server_name, effective_base_dir, stop_start_server):
            logger.info(f"API: Exporting world '{world_name_str}' from '{world_path}' to '{export_file_path}'...")
            core_world.export_world(world_path, export_file_path)
        
        logger.info(f"API: World for server '{server_name}' exported to '{export_file_path}'.")
        return {
            "status": "success",
            "export_file": export_file_path,
            "message": f"World '{world_name_str}' exported successfully to {export_filename}.",
        }
    except ( MissingArgumentError, InvalidServerNameError, FileOperationError, DirectoryError,
             BackupWorldError,
             AddonExtractError
            ) as e:
        logger.error(f"API: Failed to export world for '{server_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to export world: {e}"}
    except Exception as e:
        logger.error(f"API: Unexpected error exporting world for '{server_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error exporting world: {e}"}


def import_world(
    server_name: str,
    selected_file_path: str,
    base_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """
    Imports a world from a .mcworld file, replacing the server's current world.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not selected_file_path:
        raise MissingArgumentError(".mcworld file path cannot be empty.")

    selected_filename = os.path.basename(selected_file_path)
    logger.info(f"API: Initiating world import for '{server_name}' from '{selected_filename}' (Stop/Start: {stop_start_server})")

    try:
        effective_base_dir = get_base_dir(base_dir)
        if not os.path.isfile(selected_file_path):
            raise FileNotFoundError(f"Source .mcworld file not found: {selected_file_path}")

        imported_world_name: Optional[str] = None # To store the name for the message

        with _server_stop_start_manager(server_name, effective_base_dir, stop_start_server):
            logger.info(f"API: Importing world from '{selected_filename}' into server '{server_name}'...")
            # core_world.import_world handles getting level-name and extraction
            # It now returns the world_name string on success
            imported_world_name = core_world.import_world(server_name, selected_file_path, effective_base_dir)
        
        logger.info(f"API: World import from '{selected_filename}' for server '{server_name}' completed.")
        return {
            "status": "success",
            "message": f"World '{imported_world_name or 'Unknown'}' imported successfully from {selected_filename}.",
        }
    except ( MissingArgumentError, InvalidServerNameError, FileNotFoundError, FileOperationError, 
             DirectoryError, DownloadExtractError, RestoreError # From core_world.import_world
            ) as e:
        logger.error(f"API: Failed to import world for '{server_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to import world: {e}"}
    except Exception as e:
        logger.error(f"API: Unexpected error importing world for '{server_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error importing world: {e}"}