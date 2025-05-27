# bedrock-server-manager/bedrock_server_manager/api/world.py
"""
Provides API-level functions for managing Bedrock server worlds.
"""

import os
import logging
from typing import Dict, Optional, Any

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.api import server as api_server_actions
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
from bedrock_server_manager.core.system import base as core_system_base
from bedrock_server_manager.core.server import (
    server_actions as core_server_actions,
    server_utils as core_server_utils,
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
        world_name_str = core_server_utils.get_world_name(
            server_name, effective_base_dir
        )
        logger.info(
            f"API: Retrieved world name for '{server_name}': '{world_name_str}'"
        )
        return {"status": "success", "world_name": world_name_str}
    except (FileOperationError, InvalidServerNameError) as e:
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
    base_dir: Optional[str] = None,
    export_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> Dict[str, Any]:
    """
    Exports the server's currently configured world to a .mcworld archive file.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(
        f"API: Initiating world export for server '{server_name}' (Stop/Start: {stop_start_server})"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        effective_export_dir: str
        if export_dir:
            effective_export_dir = export_dir
        else:
            backup_base_dir = settings.get("BACKUP_DIR")
            if not backup_base_dir:
                raise FileOperationError(
                    "BACKUP_DIR setting missing for default export directory."
                )
            effective_export_dir = os.path.join(backup_base_dir, server_name)
        os.makedirs(effective_export_dir, exist_ok=True)

        # Get world name directly from core
        world_name_str = core_server_actions.get_world_name(
            server_name, effective_base_dir
        )
        world_path = os.path.join(
            effective_base_dir, server_name, "worlds", world_name_str
        )

        if not os.path.isdir(world_path):
            raise DirectoryError(
                f"World directory '{world_name_str}' not found at: {world_path}"
            )

        timestamp = get_timestamp()
        export_filename = f"{world_name_str}_export_{timestamp}.mcworld"
        export_file_path = os.path.join(effective_export_dir, export_filename)

        with _server_stop_start_manager(
            server_name, effective_base_dir, stop_start_server
        ):
            logger.info(
                f"API: Exporting world '{world_name_str}' from '{world_path}' to '{export_file_path}'..."
            )
            core_world.export_world(world_path, export_file_path)

        logger.info(
            f"API: World for server '{server_name}' exported to '{export_file_path}'."
        )
        return {
            "status": "success",
            "export_file": export_file_path,
            "message": f"World '{world_name_str}' exported successfully to {export_filename}.",
        }
    except (
        MissingArgumentError,
        InvalidServerNameError,
        FileOperationError,
        DirectoryError,
        BackupWorldError,
        AddonExtractError,
    ) as e:
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
    logger.info(
        f"API: Initiating world import for '{server_name}' from '{selected_filename}' (Stop/Start: {stop_start_server})"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        if not os.path.isfile(selected_file_path):
            raise FileNotFoundError(
                f"Source .mcworld file not found: {selected_file_path}"
            )

        imported_world_name: Optional[str] = None  # To store the name for the message

        with _server_stop_start_manager(
            server_name, effective_base_dir, stop_start_server
        ):
            logger.info(
                f"API: Importing world from '{selected_filename}' into server '{server_name}'..."
            )
            # core_world.import_world handles getting level-name and extraction
            # It now returns the world_name string on success
            imported_world_name = core_world.import_world(
                server_name, selected_file_path, effective_base_dir
            )

        logger.info(
            f"API: World import from '{selected_filename}' for server '{server_name}' completed."
        )
        return {
            "status": "success",
            "message": f"World '{imported_world_name or 'Unknown'}' imported successfully from {selected_filename}.",
        }
    except (
        MissingArgumentError,
        InvalidServerNameError,
        FileNotFoundError,
        FileOperationError,
        DirectoryError,
        DownloadExtractError,
        RestoreError,  # From core_world.import_world
    ) as e:
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


def reset_world(server_name: str):
    """
    Resets the server's world by deleting the current world directory.
    This function is specifically for Bedrock Dedicated Servers that store
    their world in a 'worlds/<level-name>' subdirectory.
    """
    if not server_name:
        # This should ideally be an error specific to API input validation if distinct from InvalidServerNameError
        raise InvalidServerNameError(
            "Server name cannot be empty for API request."
        )  # Or a more generic APIArgumentError

    logger.info(f"API: Initiating world reset for Bedrock server '{server_name}'...")
    try:
        effective_base_dir = get_base_dir()
        server_install_dir = os.path.join(effective_base_dir, server_name)

        if not os.path.isdir(server_install_dir):
            raise DirectoryError(
                f"Server installation directory not found: {server_install_dir}"
            )

        # world_name_str is the <level-name> from server.properties, e.g., "Bedrock level"
        world_name_response = get_world_name(server_name, effective_base_dir)
        if world_name_response.get("status") == "success":
            world_name_from_config = world_name_response.get("world_name")
        else:
            return {"status": "error", "message": f"Error getting world name..."}

        # Construct the full path to the world directory for BDS
        world_dir_path = os.path.join(
            server_install_dir, "worlds", world_name_from_config
        )

        if not os.path.isdir(world_dir_path):
            return {
                "status": "success",
                "message": f"World '{world_dir_path}' doesn't exist. Nothing to delete",
            }

        if core_server_actions.check_if_server_is_running(server_name):
            cmd_res = api_server_actions.send_command(server_name, "say WARNING: Resetting world")
            if cmd_res.get("status") == "error":
                logger.warning(
                    f"API: Failed to send warning to '{server_name}': {cmd_res.get('message')}"
                )

        with _server_stop_start_manager(server_name, effective_base_dir, True, True):
            logger.info(
                f"API: Server '{server_name}' context managed (stopped if running). "
                f"Attempting to delete world directory: '{world_dir_path}'..."
            )

            if core_system_base.delete_path_robustly(
                world_dir_path,
                f"Bedrock world '{world_name_from_config}' for server '{server_name}'",
            ):
                logger.info(
                    f"API: World '{world_name_from_config}' for server '{server_name}' has been successfully reset."
                )
                return {
                    "status": "success",
                    "message": f"World '{world_name_from_config}' reset successfully.",
                }
            else:
                # delete_path_robustly would have logged the specific reason for failure.
                logger.error(
                    f"API: core_system_base.delete_path_robustly failed to delete world directory '{world_dir_path}'."
                )
                return {
                    "status": "error",
                    "message": f"Failed to delete world directory '{world_name_from_config}'. "
                    "The server was stopped (and possibly restarted), but the world files remain. "
                    "Check system logs for deletion errors.",
                }
    # Catch specific, known exceptions first
    except (
        InvalidServerNameError
    ) as e:  # If your get_world_name or stop_manager can raise this
        logger.warning(
            f"API: Invalid server name during world reset for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": str(e)}
    except DirectoryError as e:
        logger.error(
            f"API: Directory error during world reset for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Directory error: {e}"}
    except FileOperationError as e:
        logger.error(
            f"API: File operation error during world reset for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"File operation error: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error resetting world for Bedrock server '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"An unexpected error occurred while resetting the world: {e}",
        }
