# bedrock-server-manager/bedrock_server_manager/api/backup_restore.py
"""
Provides API-level functions for managing server backups and restores.

This module acts as an interface layer, orchestrating calls to core backup/restore
logic, handling server stop/start operations, listing backups, and pruning old backups.
Functions typically return a dictionary indicating success or failure status.
"""

import os
import logging
import glob
from typing import Dict, List, Optional, Any

# Local imports
from bedrock_server_manager.core.server import backup as core_backup
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.api.world import get_world_name
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.api.server import start_server, stop_server
from bedrock_server_manager.error import (
    MissingArgumentError,
    InvalidInputError,
    FileNotFoundError,
    FileOperationError,
    DirectoryError,
    BackupWorldError,
    RestoreError,
    DownloadExtractError,
    InvalidServerNameError,
)

logger = logging.getLogger("bedrock_server_manager")


def list_backup_files(server_name: str, backup_type: str) -> Dict[str, Any]:
    """
    Lists available backup files for a specific server and type.

    Args:
        server_name: The name of the server.
        backup_type: The type of backups to list ("world" or "config").

    Returns:
        A dictionary:
        - {"status": "success", "backups": List[str]} containing a list of full backup file paths.
        - {"status": "error", "message": str} if an error occurs or no backups found.

    Raises:
        MissingArgumentError: If `server_name` or `backup_type` is empty.
        FileOperationError: If BACKUP_DIR setting is missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not backup_type:
        raise MissingArgumentError("Backup type cannot be empty.")

    backup_base_dir = settings.get("BACKUP_DIR")
    if not backup_base_dir:
        raise FileOperationError(
            "BACKUP_DIR setting is missing or empty in configuration."
        )

    backup_dir = os.path.join(backup_base_dir, server_name)
    backup_type_norm = backup_type.lower()
    logger.info(
        f"Listing '{backup_type_norm}' backups for server '{server_name}' in '{backup_dir}'..."
    )

    if not os.path.isdir(backup_dir):
        logger.warning(
            f"Backup directory not found: '{backup_dir}'. Returning empty list."
        )
        # Consistent with finding 0 files, return success with empty list
        return {"status": "success", "backups": []}

    try:
        backup_files: List[str] = []
        if backup_type_norm == "world":
            pattern = os.path.join(backup_dir, "*.mcworld")
            backup_files = glob.glob(pattern)
            logger.debug(
                f"Found {len(backup_files)} world backups matching pattern '{pattern}'."
            )
        elif backup_type_norm == "config":
            # Find JSON and properties backup files
            json_pattern = os.path.join(backup_dir, "*_backup_*.json")
            props_pattern = os.path.join(backup_dir, "server_backup_*.properties")
            backup_files.extend(glob.glob(json_pattern))
            backup_files.extend(glob.glob(props_pattern))
            logger.debug(f"Found {len(backup_files)} config backups matching patterns.")
        else:
            # Raise error for invalid type passed to API function
            raise InvalidInputError(
                f"Invalid backup type specified: '{backup_type}'. Must be 'world' or 'config'."
            )

        # Sort by modification time, newest first
        backup_files.sort(key=os.path.getmtime, reverse=True)

        return {"status": "success", "backups": backup_files}

    except OSError as e:
        logger.error(
            f"Error accessing backup directory '{backup_dir}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error listing backups: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error listing backups for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Unexpected error listing backups: {e}"}


def backup_world(
    server_name: str, base_dir: Optional[str] = None, stop_start_server: bool = True
) -> Dict[str, str]:
    """
    Creates a backup of the server's world directory (.mcworld file).

    Orchestrates optional server stop/start, finds the world path, calls the
    core backup function, and handles errors.

    Args:
        server_name: The name of the server.
        base_dir: Optional. The base directory for server installations. Uses config default if None.
        stop_start_server: If True, stop server before backup and restart after if it was running.

    Returns:
        A dictionary indicating the outcome: {"status": "success", "message": ...} or
        {"status": "error", "message": ...}.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If essential settings (BASE_DIR, BACKUP_DIR) are missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.info(
        f"Initiating world backup for server '{server_name}'. Stop/Start: {stop_start_server}"
    )

    try:
        effective_base_dir = get_base_dir(
            base_dir
        )  # Raises FileOperationError if setting missing
        backup_base_dir = settings.get("BACKUP_DIR")
        if not backup_base_dir:
            raise FileOperationError("BACKUP_DIR setting missing.")

        server_backup_dir = os.path.join(backup_base_dir, server_name)
        os.makedirs(server_backup_dir, exist_ok=True)  # Ensure backup dir exists

    except FileOperationError as e:
        logger.error(
            f"Configuration error preventing world backup for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}

    was_running = False
    # --- Server Stop ---
    if stop_start_server:
        try:
            logger.debug(
                f"Checking running status for '{server_name}' before world backup..."
            )
            if system_base.is_server_running(server_name, effective_base_dir):
                was_running = True
                logger.info(
                    f"Server '{server_name}' is running. Stopping for world backup..."
                )
                stop_result = stop_server(server_name, effective_base_dir)
                if stop_result.get("status") == "error":
                    logger.error(
                        f"Failed to stop server '{server_name}' for backup: {stop_result.get('message')}"
                    )
                    return stop_result  # Return error from stop_server
                logger.info(f"Server '{server_name}' stopped.")
            else:
                logger.debug(f"Server '{server_name}' is not running.")
        except Exception as e:
            logger.error(
                f"Error stopping server '{server_name}' for world backup: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Failed to stop server for backup: {e}",
            }

    # --- Core Backup Operation ---
    backup_error = None
    try:
        # Get world name (API function returns dict)
        world_name_result = get_world_name(server_name, effective_base_dir)
        if world_name_result.get("status") == "error":
            # Propagate error if world name couldn't be found
            raise FileOperationError(
                world_name_result.get("message", "Could not determine world name.")
            )

        world_name = world_name_result["world_name"]
        world_path = os.path.join(effective_base_dir, server_name, "worlds", world_name)

        # Check existence before calling core backup
        if not os.path.isdir(world_path):
            raise DirectoryError(f"World directory does not exist: {world_path}")

        # Call core backup function
        core_backup.backup_world(world_path, server_backup_dir, world_name)
        logger.info(f"Core world backup function completed for server '{server_name}'.")

    except (
        DirectoryError,
        FileOperationError,
        MissingArgumentError,
        BackupWorldError,
    ) as e:
        backup_error = e
        logger.error(
            f"World backup failed for server '{server_name}': {e}", exc_info=True
        )
        # Don't return yet, proceed to finally for potential restart
    except Exception as e:
        backup_error = e
        logger.error(
            f"Unexpected error during world backup for server '{server_name}': {e}",
            exc_info=True,
        )

    # --- Server Restart ---
    finally:
        restart_error_dict = None
        if stop_start_server and was_running:
            if backup_error:
                logger.warning(
                    f"Attempting to restart server '{server_name}' even though world backup failed."
                )
            else:
                logger.info(f"Restarting server '{server_name}' after world backup...")

            try:
                start_result = start_server(server_name, effective_base_dir)
                if start_result.get("status") == "error":
                    logger.error(
                        f"Failed to restart server '{server_name}' after backup: {start_result.get('message')}"
                    )
                    restart_error_dict = start_result  # Store restart error dict
                else:
                    logger.info(f"Server '{server_name}' restart initiated.")
            except Exception as e:
                logger.error(
                    f"Unexpected error restarting server '{server_name}' after backup: {e}",
                    exc_info=True,
                )
                restart_error_dict = {
                    "status": "error",
                    "message": f"Unexpected error restarting server: {e}",
                }

    # --- Final Result ---
    if backup_error:
        return {"status": "error", "message": f"World backup failed: {backup_error}"}
    elif restart_error_dict:
        # Backup succeeded, but restart failed
        return restart_error_dict
    else:
        return {
            "status": "success",
            "message": f"World backup completed successfully for server '{server_name}'.",
        }


def backup_config_file(
    server_name: str,
    file_to_backup: str,
    base_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """
    Creates a backup of a specific configuration file from the server directory.

    Args:
        server_name: The name of the server.
        file_to_backup: The relative path of the file within the server's directory
                        (e.g., "server.properties", "permissions.json").
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        stop_start_server: If True, stop/start server around backup (usually not necessary).

    Returns:
        A dictionary indicating the outcome: {"status": "success", "message": ...} or
        {"status": "error", "message": ...}.

    Raises:
        MissingArgumentError: If `server_name` or `file_to_backup` is empty.
        FileNotFoundError: If the configuration file to back up does not exist.
        FileOperationError: If essential settings (BASE_DIR, BACKUP_DIR) are missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not file_to_backup:
        raise MissingArgumentError("File to backup cannot be empty.")

    filename_base = os.path.basename(file_to_backup)
    logger.info(
        f"Initiating config file backup for '{filename_base}' on server '{server_name}'. Stop/Start: {stop_start_server}"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        backup_base_dir = settings.get("BACKUP_DIR")
        if not backup_base_dir:
            raise FileOperationError("BACKUP_DIR setting missing.")

        server_backup_dir = os.path.join(backup_base_dir, server_name)
        os.makedirs(server_backup_dir, exist_ok=True)

        full_file_path = os.path.join(effective_base_dir, server_name, file_to_backup)

        # Check existence before stopping server
        if not os.path.isfile(full_file_path):
            raise FileNotFoundError(
                f"Configuration file not found at: {full_file_path}"
            )

    except (
        FileOperationError,
        FileNotFoundError,
    ) as e:  # Catch config/validation errors early
        logger.error(
            f"Pre-backup check failed for config '{filename_base}' on server '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Configuration error or file not found: {e}",
        }

    was_running = False
    # --- Server Stop ---
    if stop_start_server:
        try:
            logger.debug(
                f"Checking running status for '{server_name}' before config backup..."
            )
            if system_base.is_server_running(server_name, effective_base_dir):
                was_running = True
                logger.info(
                    f"Server '{server_name}' is running. Stopping for config backup..."
                )
                stop_result = stop_server(server_name, effective_base_dir)
                if stop_result.get("status") == "error":
                    logger.error(
                        f"Failed to stop server '{server_name}' for backup: {stop_result.get('message')}"
                    )
                    return stop_result
                logger.info(f"Server '{server_name}' stopped.")
            else:
                logger.debug(f"Server '{server_name}' is not running.")
        except Exception as e:
            logger.error(
                f"Error stopping server '{server_name}' for config backup: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Failed to stop server for backup: {e}",
            }

    # --- Core Backup Operation ---
    backup_error = None
    try:
        # Call core backup function
        core_backup.backup_config_file(full_file_path, server_backup_dir)
        logger.info(
            f"Core config file backup function completed for '{filename_base}' on server '{server_name}'."
        )
    except (FileNotFoundError, FileOperationError, MissingArgumentError) as e:
        backup_error = e
        logger.error(
            f"Config file backup failed for '{filename_base}' on server '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        backup_error = e
        logger.error(
            f"Unexpected error during config file backup for '{filename_base}' on server '{server_name}': {e}",
            exc_info=True,
        )

    # --- Server Restart ---
    finally:
        restart_error_dict = None
        if stop_start_server and was_running:
            if backup_error:
                logger.warning(
                    f"Attempting to restart server '{server_name}' even though config backup failed."
                )
            else:
                logger.info(f"Restarting server '{server_name}' after config backup...")
            try:
                start_result = start_server(server_name, effective_base_dir)
                if start_result.get("status") == "error":
                    logger.error(
                        f"Failed to restart server '{server_name}' after backup: {start_result.get('message')}"
                    )
                    restart_error_dict = start_result
                else:
                    logger.info(f"Server '{server_name}' restart initiated.")
            except Exception as e:
                logger.error(
                    f"Unexpected error restarting server '{server_name}' after backup: {e}",
                    exc_info=True,
                )
                restart_error_dict = {
                    "status": "error",
                    "message": f"Unexpected error restarting server: {e}",
                }

    # --- Final Result ---
    if backup_error:
        return {
            "status": "error",
            "message": f"Config file backup for '{filename_base}' failed: {backup_error}",
        }
    elif restart_error_dict:
        return restart_error_dict
    else:
        return {
            "status": "success",
            "message": f"Config file backup for '{filename_base}' completed successfully.",
        }


def backup_all(
    server_name: str, base_dir: Optional[str] = None, stop_start_server: bool = True
) -> Dict[str, str]:
    """
    Performs a full backup (world and standard config files) for the specified server.

    Args:
        server_name: The name of the server.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        stop_start_server: If True, stop server before backup and restart after if it was running.

    Returns:
        A dictionary indicating the outcome: {"status": "success", "message": ...} or
        {"status": "error", "message": ...}. Will report partial success if some configs fail.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If essential settings (BASE_DIR, BACKUP_DIR) are missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.info(
        f"Initiating full backup for server '{server_name}'. Stop/Start: {stop_start_server}"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        # Check backup dir setting early
        if not settings.get("BACKUP_DIR"):
            raise FileOperationError("BACKUP_DIR setting missing.")
    except FileOperationError as e:
        logger.error(
            f"Configuration error preventing full backup for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}

    was_running = False
    # --- Server Stop ---
    if stop_start_server:
        try:
            logger.debug(
                f"Checking running status for '{server_name}' before full backup..."
            )
            if system_base.is_server_running(server_name, effective_base_dir):
                was_running = True
                logger.info(
                    f"Server '{server_name}' is running. Stopping for full backup..."
                )
                stop_result = stop_server(server_name, effective_base_dir)
                if stop_result.get("status") == "error":
                    logger.error(
                        f"Failed to stop server '{server_name}' for backup: {stop_result.get('message')}"
                    )
                    return stop_result
                logger.info(f"Server '{server_name}' stopped.")
            else:
                logger.debug(f"Server '{server_name}' is not running.")
        except Exception as e:
            logger.error(
                f"Error stopping server '{server_name}' for full backup: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Failed to stop server for backup: {e}",
            }

    # --- Core Backup Operation ---
    backup_error = None
    try:
        # Call core backup_all function
        core_backup.backup_all(server_name, effective_base_dir)
        logger.info(f"Core full backup function completed for server '{server_name}'.")
    except (BackupWorldError, FileOperationError, MissingArgumentError) as e:
        backup_error = e
        logger.error(
            f"Full backup failed for server '{server_name}': {e}", exc_info=True
        )
    except Exception as e:
        backup_error = e
        logger.error(
            f"Unexpected error during full backup for server '{server_name}': {e}",
            exc_info=True,
        )

    # --- Server Restart ---
    finally:
        restart_error_dict = None
        if stop_start_server and was_running:
            if backup_error:
                logger.warning(
                    f"Attempting to restart server '{server_name}' even though full backup failed."
                )
            else:
                logger.info(f"Restarting server '{server_name}' after full backup...")
            try:
                start_result = start_server(server_name, effective_base_dir)
                if start_result.get("status") == "error":
                    logger.error(
                        f"Failed to restart server '{server_name}' after backup: {start_result.get('message')}"
                    )
                    restart_error_dict = start_result
                else:
                    logger.info(f"Server '{server_name}' restart initiated.")
            except Exception as e:
                logger.error(
                    f"Unexpected error restarting server '{server_name}' after backup: {e}",
                    exc_info=True,
                )
                restart_error_dict = {
                    "status": "error",
                    "message": f"Unexpected error restarting server: {e}",
                }

    # --- Final Result ---
    if backup_error:
        # If core backup_all itself failed
        return {"status": "error", "message": f"Full backup failed: {backup_error}"}
    elif restart_error_dict:
        # Backup succeeded, but restart failed
        return restart_error_dict
    else:
        return {
            "status": "success",
            "message": f"Full backup completed successfully for server '{server_name}'.",
        }


# --- Restore Functions ---


def restore_world(
    server_name: str,
    backup_file_path: str,
    base_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """
    Restores a server's world directory from a .mcworld backup file.

    Orchestrates optional server stop/start, calls the core restore function,
    and handles errors.

    Args:
        server_name: The name of the server.
        backup_file_path: The full path to the .mcworld backup file.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        stop_start_server: If True, stop server before restore and restart after if it was running.

    Returns:
        A dictionary indicating the outcome: {"status": "success", "message": ...} or
        {"status": "error", "message": ...}.

    Raises:
        MissingArgumentError: If `server_name` or `backup_file_path` is empty.
        FileNotFoundError: If `backup_file_path` does not exist.
        FileOperationError: If essential settings (BASE_DIR) are missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not backup_file_path:
        raise MissingArgumentError("Backup file path cannot be empty.")

    backup_filename = os.path.basename(backup_file_path)
    logger.info(
        f"Initiating world restore for server '{server_name}' from '{backup_filename}'. Stop/Start: {stop_start_server}"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        # Check backup file existence *before* stopping server
        if not os.path.isfile(backup_file_path):
            raise FileNotFoundError(f"Backup file not found: {backup_file_path}")
    except (FileOperationError, FileNotFoundError) as e:
        logger.error(
            f"Pre-restore check failed for world restore on server '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Configuration error or backup file not found: {e}",
        }

    was_running = False
    # --- Server Stop ---
    if stop_start_server:
        try:
            logger.debug(
                f"Checking running status for '{server_name}' before world restore..."
            )
            if system_base.is_server_running(server_name, effective_base_dir):
                was_running = True
                logger.info(
                    f"Server '{server_name}' is running. Stopping for world restore..."
                )
                stop_result = stop_server(server_name, effective_base_dir)
                if stop_result.get("status") == "error":
                    logger.error(
                        f"Failed to stop server '{server_name}' for restore: {stop_result.get('message')}"
                    )
                    return stop_result
                logger.info(f"Server '{server_name}' stopped.")
            else:
                logger.debug(f"Server '{server_name}' is not running.")
        except Exception as e:
            logger.error(
                f"Error stopping server '{server_name}' for world restore: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Failed to stop server for restore: {e}",
            }

    # --- Core Restore Operation ---
    restore_error = None
    try:
        # Call core restore function (which internally calls import_world)
        core_backup.restore_server(
            server_name, backup_file_path, "world", effective_base_dir
        )
        logger.info(
            f"Core world restore function completed for server '{server_name}'."
        )
    except (
        RestoreError,
        FileOperationError,
        DirectoryError,
        DownloadExtractError,
        InvalidServerNameError,
    ) as e:
        # Catch specific errors known to be raised by restore_server/import_world
        restore_error = e
        logger.error(
            f"World restore failed for server '{server_name}' from '{backup_filename}': {e}",
            exc_info=True,
        )
    except Exception as e:
        restore_error = e
        logger.error(
            f"Unexpected error during world restore for server '{server_name}': {e}",
            exc_info=True,
        )

    # --- Server Restart ---
    finally:
        restart_error_dict = None
        if stop_start_server and was_running:
            if restore_error:
                logger.warning(
                    f"Attempting to restart server '{server_name}' even though world restore failed."
                )
            else:
                logger.info(f"Restarting server '{server_name}' after world restore...")
            try:
                start_result = start_server(server_name, effective_base_dir)
                if start_result.get("status") == "error":
                    logger.error(
                        f"Failed to restart server '{server_name}' after restore: {start_result.get('message')}"
                    )
                    restart_error_dict = start_result
                else:
                    logger.info(f"Server '{server_name}' restart initiated.")
            except Exception as e:
                logger.error(
                    f"Unexpected error restarting server '{server_name}' after restore: {e}",
                    exc_info=True,
                )
                restart_error_dict = {
                    "status": "error",
                    "message": f"Unexpected error restarting server: {e}",
                }

    # --- Final Result ---
    if restore_error:
        return {"status": "error", "message": f"World restore failed: {restore_error}"}
    elif restart_error_dict:
        return restart_error_dict
    else:
        return {
            "status": "success",
            "message": f"World restore from '{backup_filename}' completed successfully.",
        }


def restore_config_file(
    server_name: str,
    backup_file_path: str,
    base_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """
    Restores a specific configuration file for a server from a backup copy.

    Args:
        server_name: The name of the server.
        backup_file_path: The full path to the config backup file.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        stop_start_server: If True, stop/start server around restore (usually not necessary).

    Returns:
        A dictionary indicating the outcome: {"status": "success", "message": ...} or
        {"status": "error", "message": ...}.

    Raises:
        MissingArgumentError: If `server_name` or `backup_file_path` is empty.
        FileNotFoundError: If `backup_file_path` does not exist.
        FileOperationError: If essential settings (BASE_DIR) are missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not backup_file_path:
        raise MissingArgumentError("Backup file path cannot be empty.")

    backup_filename = os.path.basename(backup_file_path)
    logger.info(
        f"Initiating config file restore for server '{server_name}' from '{backup_filename}'. Stop/Start: {stop_start_server}"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        if not os.path.isfile(backup_file_path):
            raise FileNotFoundError(f"Backup file not found: {backup_file_path}")
    except (FileOperationError, FileNotFoundError) as e:
        logger.error(
            f"Pre-restore check failed for config restore on server '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Configuration error or backup file not found: {e}",
        }

    was_running = False
    # --- Server Stop ---
    if stop_start_server:
        try:
            logger.debug(
                f"Checking running status for '{server_name}' before config restore..."
            )
            if system_base.is_server_running(server_name, effective_base_dir):
                was_running = True
                logger.info(
                    f"Server '{server_name}' is running. Stopping for config restore..."
                )
                stop_result = stop_server(server_name, effective_base_dir)
                if stop_result.get("status") == "error":
                    logger.error(
                        f"Failed to stop server '{server_name}' for restore: {stop_result.get('message')}"
                    )
                    return stop_result
                logger.info(f"Server '{server_name}' stopped.")
            else:
                logger.debug(f"Server '{server_name}' is not running.")
        except Exception as e:
            logger.error(
                f"Error stopping server '{server_name}' for config restore: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Failed to stop server for restore: {e}",
            }

    # --- Core Restore Operation ---
    restore_error = None
    try:
        # Call core restore function
        core_backup.restore_server(
            server_name, backup_file_path, "config", effective_base_dir
        )
        logger.info(
            f"Core config file restore function completed for server '{server_name}'."
        )
    except (
        RestoreError,
        FileOperationError,
        InvalidInputError,
        FileNotFoundError,
    ) as e:
        restore_error = e
        logger.error(
            f"Config file restore failed for server '{server_name}' from '{backup_filename}': {e}",
            exc_info=True,
        )
    except Exception as e:
        restore_error = e
        logger.error(
            f"Unexpected error during config file restore for server '{server_name}': {e}",
            exc_info=True,
        )

    # --- Server Restart ---
    finally:
        restart_error_dict = None
        if stop_start_server and was_running:
            if restore_error:
                logger.warning(
                    f"Attempting to restart server '{server_name}' even though config restore failed."
                )
            else:
                logger.info(
                    f"Restarting server '{server_name}' after config restore..."
                )
            try:
                start_result = start_server(server_name, effective_base_dir)
                if start_result.get("status") == "error":
                    logger.error(
                        f"Failed to restart server '{server_name}' after restore: {start_result.get('message')}"
                    )
                    restart_error_dict = start_result
                else:
                    logger.info(f"Server '{server_name}' restart initiated.")
            except Exception as e:
                logger.error(
                    f"Unexpected error restarting server '{server_name}' after restore: {e}",
                    exc_info=True,
                )
                restart_error_dict = {
                    "status": "error",
                    "message": f"Unexpected error restarting server: {e}",
                }

    # --- Final Result ---
    if restore_error:
        return {
            "status": "error",
            "message": f"Config file restore failed: {restore_error}",
        }
    elif restart_error_dict:
        return restart_error_dict
    else:
        return {
            "status": "success",
            "message": f"Config file restore from '{backup_filename}' completed successfully.",
        }


def restore_all(
    server_name: str, base_dir: Optional[str] = None, stop_start_server: bool = True
) -> Dict[str, str]:
    """
    Restores the server's world and configuration files from the latest available backups.

    Args:
        server_name: The name of the server.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        stop_start_server: If True, stop server before restore and restart after if it was running.

    Returns:
        A dictionary indicating the outcome: {"status": "success", "message": ...} or
        {"status": "error", "message": ...}. Will report error if any part fails.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If essential settings (BASE_DIR, BACKUP_DIR) are missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.info(
        f"Initiating restore_all for server '{server_name}'. Stop/Start: {stop_start_server}"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        # Check backup dir setting early
        if not settings.get("BACKUP_DIR"):
            raise FileOperationError("BACKUP_DIR setting missing.")
    except FileOperationError as e:
        logger.error(
            f"Configuration error preventing restore_all for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}

    was_running = False
    # --- Server Stop ---
    if stop_start_server:
        try:
            logger.debug(
                f"Checking running status for '{server_name}' before restore_all..."
            )
            if system_base.is_server_running(server_name, effective_base_dir):
                was_running = True
                logger.info(
                    f"Server '{server_name}' is running. Stopping for restore_all..."
                )
                stop_result = stop_server(server_name, effective_base_dir)
                if stop_result.get("status") == "error":
                    logger.error(
                        f"Failed to stop server '{server_name}' for restore: {stop_result.get('message')}"
                    )
                    return stop_result
                logger.info(f"Server '{server_name}' stopped.")
            else:
                logger.debug(f"Server '{server_name}' is not running.")
        except Exception as e:
            logger.error(
                f"Error stopping server '{server_name}' for restore_all: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Failed to stop server for restore: {e}",
            }

    # --- Core Restore Operation ---
    restore_error = None
    try:
        # Call core restore_all function
        core_backup.restore_all(server_name, effective_base_dir)
        logger.info(f"Core restore_all function completed for server '{server_name}'.")
    except RestoreError as e:  # Catch the specific error from core restore_all
        restore_error = e
        logger.error(
            f"Restore all failed for server '{server_name}': {e}", exc_info=True
        )
    except (
        FileOperationError,
        DirectoryError,
        MissingArgumentError,
    ) as e:  # Other possible core errors
        restore_error = e
        logger.error(
            f"Restore all failed for server '{server_name}': {e}", exc_info=True
        )
    except Exception as e:
        restore_error = e
        logger.error(
            f"Unexpected error during restore_all for server '{server_name}': {e}",
            exc_info=True,
        )

    # --- Server Restart ---
    finally:
        restart_error_dict = None
        if stop_start_server and was_running:
            if restore_error:
                logger.warning(
                    f"Attempting to restart server '{server_name}' even though restore_all failed."
                )
            else:
                logger.info(f"Restarting server '{server_name}' after restore_all...")
            try:
                start_result = start_server(server_name, effective_base_dir)
                if start_result.get("status") == "error":
                    logger.error(
                        f"Failed to restart server '{server_name}' after restore: {start_result.get('message')}"
                    )
                    restart_error_dict = start_result
                else:
                    logger.info(f"Server '{server_name}' restart initiated.")
            except Exception as e:
                logger.error(
                    f"Unexpected error restarting server '{server_name}' after restore: {e}",
                    exc_info=True,
                )
                restart_error_dict = {
                    "status": "error",
                    "message": f"Unexpected error restarting server: {e}",
                }

    # --- Final Result ---
    if restore_error:
        # Use the message from the caught RestoreError if available
        error_message = getattr(restore_error, "message", str(restore_error))
        return {"status": "error", "message": f"Restore all failed: {error_message}"}
    elif restart_error_dict:
        return restart_error_dict
    else:
        return {
            "status": "success",
            "message": f"Restore all completed successfully for server '{server_name}'.",
        }


def prune_old_backups(
    server_name: str, base_dir: Optional[str] = None, backup_keep: Optional[int] = None
) -> Dict[str, str]:
    """
    Prunes old backups (world, properties, json) for a specific server,
    keeping a configured number of the most recent backups for each type.

    Args:
        server_name: The name of the server whose backups should be pruned.
        base_dir: Optional. Base directory for server installations (needed to find world name).
                  Uses config default if None.
        backup_keep: Optional. How many backups of each type to keep. If None, uses
                     the 'BACKUP_KEEP' value from application settings.

    Returns:
        A dictionary indicating the outcome: {"status": "success", "message": ...} or
        {"status": "error", "message": ...}. Will report error if any pruning step fails.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        ValueError: If `backup_keep` (or the setting value) is not a valid integer >= 0.
        FileOperationError: If essential settings (BASE_DIR, BACKUP_DIR) are missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.info(f"Initiating pruning of old backups for server '{server_name}'.")

    try:
        effective_base_dir = get_base_dir(base_dir)
        backup_base_dir = settings.get("BACKUP_DIR")
        if not backup_base_dir:
            raise FileOperationError("BACKUP_DIR setting missing.")

        server_backup_dir = os.path.join(backup_base_dir, server_name)

        # Determine how many backups to keep
        effective_backup_keep: int
        if backup_keep is None:
            keep_setting = settings.get("BACKUP_KEEP", 3)  # Default to 3
            try:
                effective_backup_keep = int(keep_setting)
                if effective_backup_keep < 0:
                    raise ValueError("Cannot be negative")
                logger.debug(f"Using BACKUP_KEEP setting: {effective_backup_keep}")
            except (ValueError, TypeError) as e:
                logger.error(
                    f"Invalid BACKUP_KEEP setting value '{keep_setting}': {e}. Must be a non-negative integer."
                )
                raise ValueError(f"Invalid BACKUP_KEEP setting: {e}") from e
        else:
            # Use provided value after validation
            try:
                effective_backup_keep = int(backup_keep)
                if effective_backup_keep < 0:
                    raise ValueError("Cannot be negative")
                logger.debug(
                    f"Using provided backup_keep value: {effective_backup_keep}"
                )
            except (ValueError, TypeError) as e:
                logger.error(
                    f"Invalid backup_keep parameter value '{backup_keep}': {e}. Must be a non-negative integer."
                )
                raise ValueError(f"Invalid backup_keep parameter: {e}") from e

        if not os.path.isdir(server_backup_dir):
            logger.info(
                f"Backup directory '{server_backup_dir}' does not exist. Nothing to prune."
            )
            return {
                "status": "success",
                "message": "No backup directory found, nothing to prune.",
            }

        # --- Prune Different Backup Types ---
        pruning_errors = []

        # 1. Prune World Backups (*.mcworld)
        logger.debug("Pruning world backups...")
        world_name = None
        try:
            world_name_result = get_world_name(server_name, effective_base_dir)
            if world_name_result.get("status") == "success":
                world_name = world_name_result["world_name"]
            else:
                logger.warning(
                    f"Could not determine world name for server '{server_name}'. Pruning *.mcworld without specific prefix."
                )
        except Exception as e:
            logger.warning(
                f"Error getting world name for prefix: {e}. Pruning *.mcworld without specific prefix.",
                exc_info=True,
            )

        try:
            core_backup.prune_old_backups(
                backup_dir=server_backup_dir,
                backup_keep=effective_backup_keep,
                file_prefix=(
                    f"{world_name}_backup_" if world_name else ""
                ),  # Use prefix if name found
                file_extension="mcworld",
            )
        except Exception as e:
            logger.error(
                f"Error pruning world backups for server '{server_name}': {e}",
                exc_info=True,
            )
            pruning_errors.append(f"World backups ({e})")

        # 2. Prune Properties Backups (server_backup_*.properties)
        logger.debug("Pruning server.properties backups...")
        try:
            core_backup.prune_old_backups(
                backup_dir=server_backup_dir,
                backup_keep=effective_backup_keep,
                file_prefix="server_backup_",
                file_extension="properties",
            )
        except Exception as e:
            logger.error(
                f"Error pruning server.properties backups for server '{server_name}': {e}",
                exc_info=True,
            )
            pruning_errors.append(f"Properties backups ({e})")

        # 3. Prune JSON Backups (*_backup_*.json) - Prune all JSON together for simplicity
        logger.debug("Pruning JSON config backups...")
        try:
            core_backup.prune_old_backups(
                backup_dir=server_backup_dir,
                backup_keep=effective_backup_keep,
                file_prefix="",  # Match any prefix ending in _backup_
                file_extension="json",
            )
        except Exception as e:
            logger.error(
                f"Error pruning JSON backups for server '{server_name}': {e}",
                exc_info=True,
            )
            pruning_errors.append(f"JSON backups ({e})")

        # --- Final Result ---
        if pruning_errors:
            error_summary = "; ".join(pruning_errors)
            logger.error(
                f"Pruning completed with errors for server '{server_name}': {error_summary}"
            )
            return {
                "status": "error",
                "message": f"Pruning failed for some backup types: {error_summary}",
            }
        else:
            logger.info(
                f"Backup pruning completed successfully for server '{server_name}'."
            )
            return {
                "status": "success",
                "message": f"Backup pruning completed for server '{server_name}'.",
            }

    except (ValueError, FileOperationError) as e:  # Catch setup/config errors
        logger.error(
            f"Cannot prune backups for server '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Configuration or input error: {e}"}
    except Exception as e:  # Catch unexpected errors
        logger.error(
            f"Unexpected error during backup pruning for server '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error during pruning: {e}"}
