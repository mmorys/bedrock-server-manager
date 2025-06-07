# bedrock_server_manager/api/backup_restore.py
"""
Provides API-level functions for managing server backups and restores.

This module acts as an interface layer, orchestrating calls to core backup/restore
logic, handling server stop/start operations, listing backups, and pruning old backups.
Functions typically return a dictionary indicating success or failure status.
"""

from multiprocessing import allow_connection_pickling
import os
import logging
import glob
from typing import Dict, List, Optional, Any

# Local imports
from bedrock_server_manager.api import world
from bedrock_server_manager.core.server import backup_restore as core_backup
from bedrock_server_manager.core.server import world as core_world
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.api.world import get_world_name as api_get_world_name
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.api.utils import _server_stop_start_manager
from bedrock_server_manager.error import (
    MissingArgumentError,
    InvalidInputError,
    FileNotFoundError,
    FileOperationError,
    DirectoryError,
    BackupWorldError,
    RestoreError,
    InvalidServerNameError,
    AddonExtractError,
)

logger = logging.getLogger(__name__)


def list_backup_files(server_name: str, backup_type: str) -> Dict[str, Any]:
    """
    API endpoint to list available backup files for a specific server and type.

    This function handles exceptions from the core logic and formats them into a
    standard API response dictionary.

    Args:
        server_name: The name of the server.
        backup_type: The type of backups to list ("world", "properties", "allowlist", "permissions", or "all").

    Returns:
        A dictionary with the API response:
        - {"status": "success", "backups": List[str] | Dict[str, List[str]]} on success.
        - {"status": "error", "message": str} on failure.
    """
    try:
        # 1. Call the core logic function to get the data
        backup_data = core_backup._get_backup_files(server_name, backup_type)

        # 2. Format the successful response
        return {"status": "success", "backups": backup_data}

    except (MissingArgumentError, InvalidInputError, FileOperationError) as e:
        # 3. Handle known, expected errors (e.g., bad user input)
        logger.warning(f"Client error listing backups for server '{server_name}': {e}")
        return {"status": "error", "message": str(e)}

    except Exception as e:
        # 4. Handle unexpected server errors
        logger.error(
            f"Unexpected error listing backups for '{server_name}': {e}",
            exc_info=True,
        )
        # Avoid leaking internal implementation details in the message
        return {"status": "error", "message": "An unexpected server error occurred."}


def backup_world(
    server_name: str, base_dir: Optional[str] = None, stop_start_server: bool = True
) -> Dict[str, str]:
    """
    Creates a backup of the server's world directory (.mcworld file).
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    logger.info(
        f"API: Initiating world backup for server '{server_name}'. Stop/Start: {stop_start_server}"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        backup_base_dir = settings.get("BACKUP_DIR")
        if not backup_base_dir:
            raise FileOperationError("BACKUP_DIR setting missing.")
        server_backup_dir = os.path.join(backup_base_dir, server_name)
        os.makedirs(server_backup_dir, exist_ok=True)

        world_name_res = api_get_world_name(
            server_name, effective_base_dir
        )  # Use API that returns dict
        if world_name_res.get("status") == "error":
            return world_name_res  # Propagate error
        world_name = world_name_res["world_name"]
        world_path = os.path.join(effective_base_dir, server_name, "worlds", world_name)

        if not os.path.isdir(world_path):
            raise DirectoryError(f"World directory does not exist: {world_path}")

        with _server_stop_start_manager(
            server_name, effective_base_dir, stop_start_server
        ):
            backup_file = core_backup.backup_world_data(
                world_path, server_backup_dir, world_name
            )

        return {
            "status": "success",
            "message": f"World backup '{os.path.basename(backup_file)}' created successfully for server '{server_name}'.",
        }
    except (
        MissingArgumentError,
        FileOperationError,
        DirectoryError,
        AddonExtractError,
        BackupWorldError,
    ) as e:
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
    file_to_backup: str,  # Relative path from server dir
    base_dir: Optional[str] = None,
    stop_start_server: bool = True,  # Usually False for single config
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
        effective_base_dir = get_base_dir(base_dir)
        backup_base_dir = settings.get("BACKUP_DIR")
        if not backup_base_dir:
            raise FileOperationError("BACKUP_DIR setting missing.")
        server_backup_dir = os.path.join(backup_base_dir, server_name)
        os.makedirs(server_backup_dir, exist_ok=True)

        full_file_path = os.path.join(effective_base_dir, server_name, file_to_backup)
        if not os.path.isfile(full_file_path):
            raise FileNotFoundError(f"Configuration file not found: {full_file_path}")

        with _server_stop_start_manager(
            server_name, effective_base_dir, stop_start_server
        ):
            backup_file = core_backup.backup_single_config_file(
                full_file_path, server_backup_dir
            )

        return {
            "status": "success",
            "message": f"Config file '{filename_base}' backed up as '{os.path.basename(backup_file)}' successfully.",
        }
    except (MissingArgumentError, FileOperationError, FileNotFoundError) as e:
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


def backup_all(
    server_name: str, base_dir: Optional[str] = None, stop_start_server: bool = True
) -> Dict[str, str]:
    """
    Performs a full backup (world and standard config files) for the specified server.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    logger.info(
        f"API: Initiating full backup for server '{server_name}'. Stop/Start: {stop_start_server}"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        # Core backup_all_server_data checks BACKUP_DIR setting

        with _server_stop_start_manager(
            server_name, effective_base_dir, stop_start_server
        ):
            results = core_backup.backup_all_server_data(
                server_name, effective_base_dir
            )

        failed_components = [comp for comp, path in results.items() if path is None]
        if failed_components:
            return {
                "status": "error",  # Or "partial_success" if you want to distinguish
                "message": f"Full backup for '{server_name}' completed with errors. Failed components: {', '.join(failed_components)}.",
                "details": results,
            }
        return {
            "status": "success",
            "message": f"Full backup completed successfully for server '{server_name}'.",
            "details": results,
        }
    except (
        MissingArgumentError,
        FileOperationError,
        BackupWorldError,
    ) as e:  # BackupWorldError from core
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


def restore_world(
    server_name: str,
    backup_file_path: str,
    base_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """
    Restores a server's world directory from a .mcworld backup file.
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
        effective_base_dir = get_base_dir(base_dir)
        if not os.path.isfile(backup_file_path):
            raise FileNotFoundError(f"Backup file not found: {backup_file_path}")

        with _server_stop_start_manager(
            server_name, effective_base_dir, stop_start_server
        ):
            # core_world.import_world handles the actual restoration.
            # It might need the server_name and base_dir to determine target paths correctly.
            core_world.import_world(server_name, backup_file_path, effective_base_dir)

        return {
            "status": "success",
            "message": f"World restore from '{backup_filename}' completed successfully for server '{server_name}'.",
        }
    except (
        MissingArgumentError,
        FileOperationError,
        FileNotFoundError,
        DirectoryError,
        AddonExtractError,
        RestoreError,
        InvalidServerNameError,
    ) as e:
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
    base_dir: Optional[str] = None,
    stop_start_server: bool = True,  # Usually False for single config
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
        f"API: Initiating config file restore for '{server_name}' from '{backup_filename}'. Stop/Start: {stop_start_server}"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_install_dir = os.path.join(
            effective_base_dir, server_name
        )  # Target for restore

        if not os.path.isfile(backup_file_path):
            raise FileNotFoundError(f"Backup file not found: {backup_file_path}")

        with _server_stop_start_manager(
            server_name,
            effective_base_dir,
            stop_start_server,
            restart_on_success_only=True,
        ):
            restored_file = core_backup.restore_config_file_data(
                backup_file_path, server_install_dir
            )

        return {
            "status": "success",
            "message": f"Config file '{os.path.basename(restored_file)}' restored successfully from '{backup_filename}'.",
        }
    except (
        MissingArgumentError,
        FileOperationError,
        FileNotFoundError,
        InvalidInputError,
    ) as e:
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


def restore_all(
    server_name: str, base_dir: Optional[str] = None, stop_start_server: bool = True
) -> Dict[str, str]:
    """
    Restores the server's world and configuration files from the latest available backups.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    logger.info(
        f"API: Initiating restore_all for server '{server_name}'. Stop/Start: {stop_start_server}"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        # Core restore_all_server_data checks BACKUP_DIR

        with _server_stop_start_manager(
            server_name,
            effective_base_dir,
            stop_start_server,
            restart_on_success_only=True,
        ):
            results = core_backup.restore_all_server_data(
                server_name, effective_base_dir
            )

        if not results:  # If core returned empty, means no backup dir
            return {
                "status": "success",  # Or "info"
                "message": f"No backups found for server '{server_name}'. Nothing restored.",
            }

        failed_components = [comp for comp, path in results.items() if path is None]
        if failed_components:
            return {
                "status": "error",
                "message": f"Restore_all for '{server_name}' completed with errors. Failed components: {', '.join(failed_components)}.",
                "details": results,
            }
        return {
            "status": "success",
            "message": f"Restore_all completed successfully for server '{server_name}'.",
            "details": results,
        }
    except (
        MissingArgumentError,
        FileOperationError,
        RestoreError,
    ) as e:  # RestoreError from core
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


def prune_old_backups(
    server_name: str, base_dir: Optional[str] = None, backup_keep: Optional[int] = None
) -> Dict[str, str]:
    """
    Prunes old backups for a specific server.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    logger.info(f"API: Initiating pruning of old backups for server '{server_name}'.")

    try:
        effective_base_dir = get_base_dir(base_dir)  # Needed for world name for prefix
        backup_base_dir = settings.get("BACKUP_DIR")
        if not backup_base_dir:
            raise FileOperationError("BACKUP_DIR setting missing.")
        server_backup_dir = os.path.join(backup_base_dir, server_name)

        effective_backup_keep: int
        if backup_keep is None:
            keep_setting = settings.get("BACKUP_KEEP", 3)
            try:
                effective_backup_keep = int(keep_setting)
                if effective_backup_keep < 0:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError(
                    f"Invalid BACKUP_KEEP setting: '{keep_setting}'. Must be non-negative integer."
                )
        else:
            try:
                effective_backup_keep = int(backup_keep)
                if effective_backup_keep < 0:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError(
                    f"Invalid backup_keep parameter: '{backup_keep}'. Must be non-negative integer."
                )

        if not os.path.isdir(server_backup_dir):
            return {
                "status": "success",
                "message": "No backup directory found, nothing to prune.",
            }

        pruning_errors = []

        # 1. World Backups
        world_name_prefix = ""
        try:
            world_name_res = api_get_world_name(server_name, effective_base_dir)
            if world_name_res.get("status") == "success":
                world_name_prefix = f"{world_name_res['world_name']}_backup_"
        except Exception as e:
            logger.warning(f"Could not determine world name for prefixing prune: {e}")

        try:
            core_backup.prune_old_backups(
                server_backup_dir, effective_backup_keep, world_name_prefix, "mcworld"
            )
        except Exception as e:
            pruning_errors.append(f"World backups ({type(e).__name__})")
            logger.error(
                f"Error pruning world backups for '{server_name}': {e}", exc_info=True
            )

        # 2. Config Backups (properties and json)
        config_file_types = {  # prefix: extension
            "server_backup_": "properties",
            "allowlist_backup_": "json",
            "permissions_backup_": "json",
            # Add other specific config backup prefixes if they exist
        }
        for prefix, ext in config_file_types.items():
            try:
                core_backup.prune_old_backups(
                    server_backup_dir, effective_backup_keep, prefix, ext
                )
            except Exception as e:
                pruning_errors.append(
                    f"Config backups ({prefix}*.{ext}) ({type(e).__name__})"
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

    except (
        MissingArgumentError,
        ValueError,
        FileOperationError,
        InvalidInputError,
    ) as e:
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
