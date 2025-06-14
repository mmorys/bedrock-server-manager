# bedrock_server_manager/api/backup_restore.py
"""
Provides API-level functions for managing server backups and restores.

This module acts as an interface layer, orchestrating calls to BedrockServer
methods, handling server stop/start operations, and formatting responses.
"""
import os
import logging
from typing import Dict, Any

# Local imports
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.api.utils import server_lifecycle_manager
from bedrock_server_manager.error import (
    BSMError,
    UserInputError,
    AppFileNotFoundError,
    MissingArgumentError,
    InvalidServerNameError,
)

logger = logging.getLogger(__name__)


def list_backup_files(server_name: str, backup_type: str) -> Dict[str, Any]:
    """
    API endpoint to list available backup files for a specific server and type.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    try:
        server = BedrockServer(server_name)
        backup_data = server.list_backups(backup_type)
        return {"status": "success", "backups": backup_data}
    except BSMError as e:
        logger.warning(f"Client error listing backups for server '{server_name}': {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"Unexpected error listing backups for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": "An unexpected server error occurred."}


def backup_world(server_name: str, stop_start_server: bool = True) -> Dict[str, str]:
    """
    Creates a backup of the server's world directory (.mcworld file).
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    logger.info(
        f"API: Initiating world backup for server '{server_name}'. Stop/Start: {stop_start_server}"
    )

    try:

        server = BedrockServer(server_name)

        with server_lifecycle_manager(server_name, stop_start_server):
            backup_file = server._backup_world_data_internal()

        return {
            "status": "success",
            "message": f"World backup '{os.path.basename(backup_file)}' created successfully for server '{server_name}'.",
        }
    except BSMError as e:
        logger.error(
            f"API: World backup failed for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"World backup failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error during world backup for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error during world backup: {e}",
        }


def backup_config_file(
    server_name: str,
    file_to_backup: str,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """
    Creates a backup of a specific configuration file from the server directory.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not file_to_backup:
        raise MissingArgumentError("File to backup cannot be empty.")

    filename_base = os.path.basename(file_to_backup)
    logger.info(
        f"API: Initiating config file backup for '{filename_base}' on server '{server_name}'. Stop/Start: {stop_start_server}"
    )

    try:
        server = BedrockServer(server_name)
        with server_lifecycle_manager(server_name, stop_start_server):
            backup_file = server._backup_config_file_internal(filename_base)

        return {
            "status": "success",
            "message": f"Config file '{filename_base}' backed up as '{os.path.basename(backup_file)}' successfully.",
        }
    except (BSMError, FileNotFoundError) as e:
        logger.error(
            f"API: Config file backup failed for '{filename_base}' on '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Config file backup failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error during config file backup for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error during config file backup: {e}",
        }


def backup_all(server_name: str, stop_start_server: bool = True) -> Dict[str, Any]:
    """
    Performs a full backup (world and standard config files) for the specified server.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    logger.info(
        f"API: Initiating full backup for server '{server_name}'. Stop/Start: {stop_start_server}"
    )

    try:
        server = BedrockServer(server_name)

        with server_lifecycle_manager(server_name, stop_before=stop_start_server):
            results = server.backup_all_data()

        return {
            "status": "success",
            "message": f"Full backup completed successfully for server '{server_name}'.",
            "details": results,
        }
    except BSMError as e:
        logger.error(f"API: Full backup failed for '{server_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Full backup failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error during full backup for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error during full backup: {e}",
        }


def restore_all(server_name: str, stop_start_server: bool = True) -> Dict[str, Any]:
    """
    Restores the server's world and configuration files from the latest available backups.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    logger.info(
        f"API: Initiating restore_all for server '{server_name}'. Stop/Start: {stop_start_server}"
    )

    try:
        server = BedrockServer(server_name)

        with server_lifecycle_manager(
            server_name, stop_before=stop_start_server, restart_on_success_only=True
        ):
            results = server.restore_all_data_from_latest()

        if not results:
            return {
                "status": "success",
                "message": f"No backups found for server '{server_name}'. Nothing restored.",
            }

        return {
            "status": "success",
            "message": f"Restore_all completed successfully for server '{server_name}'.",
            "details": results,
        }
    except BSMError as e:
        logger.error(f"API: Restore_all failed for '{server_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Restore_all failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error during restore_all for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error during restore_all: {e}",
        }


def restore_world(
    server_name: str,
    backup_file_path: str,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """
    Restores a server's world directory from a specific .mcworld backup file.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not backup_file_path:
        raise MissingArgumentError("Backup file path cannot be empty.")

    backup_filename = os.path.basename(backup_file_path)
    logger.info(
        f"API: Initiating world restore for '{server_name}' from '{backup_filename}'. Stop/Start: {stop_start_server}"
    )

    try:
        if not os.path.isfile(backup_file_path):
            raise AppFileNotFoundError(backup_file_path, "Backup file")

        server = BedrockServer(server_name)

        with server_lifecycle_manager(
            server_name, stop_before=stop_start_server, restart_on_success_only=True
        ):
            server.import_active_world_from_mcworld(backup_file_path)

        return {
            "status": "success",
            "message": f"World restore from '{backup_filename}' completed successfully for server '{server_name}'.",
        }
    except (BSMError, FileNotFoundError) as e:
        logger.error(
            f"API: World restore failed for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"World restore failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error during world restore for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error during world restore: {e}",
        }


def restore_config_file(
    server_name: str,
    backup_file_path: str,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """
    Restores a specific configuration file for a server from a backup copy.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not backup_file_path:
        raise MissingArgumentError("Backup file path cannot be empty.")

    backup_filename = os.path.basename(backup_file_path)
    logger.info(
        f"API: Initiating config restore for '{server_name}' from '{backup_filename}'. Stop/Start: {stop_start_server}"
    )

    try:
        if not os.path.isfile(backup_file_path):
            raise AppFileNotFoundError(backup_file_path, "Backup file")

        server = BedrockServer(server_name)

        with server_lifecycle_manager(
            server_name, stop_before=stop_start_server, restart_on_success_only=True
        ):
            restored_file = server._restore_config_file_internal(backup_file_path)

        return {
            "status": "success",
            "message": f"Config file '{os.path.basename(restored_file)}' restored successfully from '{backup_filename}'.",
        }
    except (BSMError, FileNotFoundError) as e:
        logger.error(
            f"API: Config file restore failed for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Config file restore failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error during config file restore for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error during config file restore: {e}",
        }


def prune_old_backups(server_name: str) -> Dict[str, str]:
    """
    Prunes old backups for all components of a specific server.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    logger.info(f"API: Initiating pruning of old backups for server '{server_name}'.")

    try:
        server = BedrockServer(server_name)

        # Check if backup directory exists to avoid unnecessary work/errors
        if not server.server_backup_directory or not os.path.isdir(
            server.server_backup_directory
        ):
            return {
                "status": "success",
                "message": "No backup directory found, nothing to prune.",
            }

        pruning_errors = []

        # 1. World Backups
        try:
            world_name = server.get_world_name()
            world_name_prefix = f"{world_name}_backup_"
            server.prune_server_backups(world_name_prefix, "mcworld")
        except Exception as e:
            pruning_errors.append(f"world backups ({type(e).__name__})")
            logger.error(
                f"Error pruning world backups for '{server_name}': {e}", exc_info=True
            )

        # 2. Config Backups
        config_file_types = {
            "server.properties_backup_": "properties",
            "allowlist_backup_": "json",
            "permissions_backup_": "json",
        }
        for prefix, ext in config_file_types.items():
            try:
                server.prune_server_backups(prefix, ext)
            except Exception as e:
                pruning_errors.append(
                    f"config backups ({prefix}*.{ext}) ({type(e).__name__})"
                )
                logger.error(
                    f"Error pruning {prefix}*.{ext} for '{server_name}': {e}",
                    exc_info=True,
                )

        if pruning_errors:
            return {
                "status": "error",
                "message": f"Pruning completed with errors: {'; '.join(pruning_errors)}",
            }

        return {
            "status": "success",
            "message": f"Backup pruning completed for server '{server_name}'.",
        }
    except (BSMError, ValueError) as e:
        logger.error(
            f"API: Cannot prune backups for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Pruning setup error: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error during backup pruning for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error during pruning: {e}"}
