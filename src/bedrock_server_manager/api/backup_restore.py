# bedrock_server_manager/api/backup_restore.py
"""Provides API functions for server backups and restores.

This module acts as a high-level interface for creating and restoring backups
of server data, including worlds and configuration files. It orchestrates
calls to the underlying BedrockServer methods, manages the server lifecycle
(stopping and starting the server as needed), and ensures that all
file-modifying operations are thread-safe.
"""
import os
import logging
import threading
from typing import Dict, Any

# Plugin system imports to bridge API functionality.
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
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

# A unified lock for all backup, restore, and prune operations.
# This ensures that only one file-modifying operation can run at a time across
# the entire module, preventing race conditions and potential data corruption.
_backup_restore_lock = threading.Lock()


@plugin_method("list_backup_files")
def list_backup_files(server_name: str, backup_type: str) -> Dict[str, Any]:
    """Lists available backup files for a given server and type.

    This is a read-only operation and does not require a lock.

    Args:
        server_name: The name of the server.
        backup_type: The type of backup to list (e.g., 'world', 'server.properties').

    Returns:
        A dictionary containing the status and a list of backup data.
        On success: `{"status": "success", "backups": [...]}`.
        On error: `{"status": "error", "message": "..."}`.

    Raises:
        InvalidServerNameError: If the server name is empty.
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


@plugin_method("backup_world")
def backup_world(server_name: str, stop_start_server: bool = True) -> Dict[str, str]:
    """Creates a backup of the server's world directory.

    This operation is thread-safe and guarded by a lock.

    Args:
        server_name: The name of the server to back up.
        stop_start_server: If True, stop the server before backup and
            restart it after. Defaults to True.

    Returns:
        A dictionary with the operation status and a message.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent world backup."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    result = {}
    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")

        plugin_manager.trigger_event(
            "before_backup",
            server_name=server_name,
            backup_type="world",
            stop_start_server=stop_start_server,
        )
        logger.info(
            f"API: Initiating world backup for server '{server_name}'. Stop/Start: {stop_start_server}"
        )

        try:
            # Use a context manager to handle stopping and starting the server.
            with server_lifecycle_manager(server_name, stop_start_server):
                server = BedrockServer(server_name)
                backup_file = server._backup_world_data_internal()
            result = {
                "status": "success",
                "message": f"World backup '{os.path.basename(backup_file)}' created successfully for server '{server_name}'.",
            }

        except BSMError as e:
            logger.error(
                f"API: World backup failed for '{server_name}': {e}", exc_info=True
            )
            result = {"status": "error", "message": f"World backup failed: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during world backup for '{server_name}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"Unexpected error during world backup: {e}",
            }
        finally:
            plugin_manager.trigger_event(
                "after_backup",
                server_name=server_name,
                backup_type="world",
                result=result,
            )

    finally:
        _backup_restore_lock.release()

    return result


@plugin_method("backup_config_file")
def backup_config_file(
    server_name: str, file_to_backup: str, stop_start_server: bool = True
) -> Dict[str, str]:
    """Creates a backup of a specific server configuration file.

    This operation is thread-safe and guarded by a lock.

    Args:
        server_name: The name of the server.
        file_to_backup: The name of the configuration file to back up (e.g., "server.properties").
        stop_start_server: If True, manage the server lifecycle. Defaults to True.

    Returns:
        A dictionary with the operation status and a message.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent config backup."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    result = {}
    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")
        if not file_to_backup:
            raise MissingArgumentError("File to backup cannot be empty.")

        filename_base = os.path.basename(file_to_backup)
        plugin_manager.trigger_event(
            "before_backup",
            server_name=server_name,
            backup_type="config_file",
            file_to_backup=file_to_backup,
            stop_start_server=stop_start_server,
        )
        logger.info(
            f"API: Initiating config file backup for '{filename_base}' on server '{server_name}'. Stop/Start: {stop_start_server}"
        )

        try:
            with server_lifecycle_manager(server_name, stop_start_server):
                server = BedrockServer(server_name)
                backup_file = server._backup_config_file_internal(filename_base)
            result = {
                "status": "success",
                "message": f"Config file '{filename_base}' backed up as '{os.path.basename(backup_file)}' successfully.",
            }

        except (BSMError, FileNotFoundError) as e:
            logger.error(
                f"API: Config file backup failed for '{filename_base}' on '{server_name}': {e}",
                exc_info=True,
            )
            result = {"status": "error", "message": f"Config file backup failed: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during config file backup for '{server_name}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"Unexpected error during config file backup: {e}",
            }
        finally:
            plugin_manager.trigger_event(
                "after_backup",
                server_name=server_name,
                backup_type="config_file",
                result=result,
            )

    finally:
        _backup_restore_lock.release()

    return result


@plugin_method("backup_all")
def backup_all(server_name: str, stop_start_server: bool = True) -> Dict[str, Any]:
    """Performs a full backup of the server's world and configuration files.

    This operation is thread-safe and guarded by a lock.

    Args:
        server_name: The name of the server.
        stop_start_server: If True, stop the server before backup. The server
            is not automatically restarted by this function. Defaults to True.

    Returns:
        A dictionary with the status, a message, and detailed results.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent full backup."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    result = {}
    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")

        plugin_manager.trigger_event(
            "before_backup",
            server_name=server_name,
            backup_type="all",
            stop_start_server=stop_start_server,
        )
        logger.info(
            f"API: Initiating full backup for server '{server_name}'. Stop/Start: {stop_start_server}"
        )

        try:
            # The server is stopped before the backup but not restarted after.
            with server_lifecycle_manager(server_name, stop_before=stop_start_server):
                server = BedrockServer(server_name)
                backup_results = server.backup_all_data()
            result = {
                "status": "success",
                "message": f"Full backup completed successfully for server '{server_name}'.",
                "details": backup_results,
            }

        except BSMError as e:
            logger.error(
                f"API: Full backup failed for '{server_name}': {e}", exc_info=True
            )
            result = {"status": "error", "message": f"Full backup failed: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during full backup for '{server_name}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"Unexpected error during full backup: {e}",
            }
        finally:
            plugin_manager.trigger_event(
                "after_backup",
                server_name=server_name,
                backup_type="all",
                result=result,
            )

    finally:
        _backup_restore_lock.release()

    return result


@plugin_method("restore_all")
def restore_all(server_name: str, stop_start_server: bool = True) -> Dict[str, Any]:
    """Restores the server from the latest available backups.

    This operation is thread-safe and guarded by a lock.

    Args:
        server_name: The name of the server.
        stop_start_server: If True, stop the server before restoring and
            restart it only if the restore is successful. Defaults to True.

    Returns:
        A dictionary with the status, a message, and detailed results.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent restore."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    result = {}
    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")

        plugin_manager.trigger_event(
            "before_restore",
            server_name=server_name,
            restore_type="all",
            stop_start_server=stop_start_server,
        )
        logger.info(
            f"API: Initiating restore_all for server '{server_name}'. Stop/Start: {stop_start_server}"
        )

        try:
            with server_lifecycle_manager(
                server_name, stop_before=stop_start_server, restart_on_success_only=True
            ):
                server = BedrockServer(server_name)
                restore_results = server.restore_all_data_from_latest()

            if not restore_results:
                result = {
                    "status": "success",
                    "message": f"No backups found for server '{server_name}'. Nothing restored.",
                }
            else:
                result = {
                    "status": "success",
                    "message": f"Restore_all completed successfully for server '{server_name}'.",
                    "details": restore_results,
                }

        except BSMError as e:
            logger.error(
                f"API: Restore_all failed for '{server_name}': {e}", exc_info=True
            )
            result = {"status": "error", "message": f"Restore_all failed: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during restore_all for '{server_name}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"Unexpected error during restore_all: {e}",
            }
        finally:
            plugin_manager.trigger_event(
                "after_restore",
                server_name=server_name,
                restore_type="all",
                result=result,
            )

    finally:
        _backup_restore_lock.release()

    return result


@plugin_method("restore_world")
def restore_world(
    server_name: str, backup_file_path: str, stop_start_server: bool = True
) -> Dict[str, str]:
    """Restores a server's world from a specific backup file.

    This operation is thread-safe and guarded by a lock.

    Args:
        server_name: The name of the server.
        backup_file_path: The absolute path to the .mcworld backup file.
        stop_start_server: If True, stop the server before restoring and
            restart it only if the restore is successful. Defaults to True.

    Returns:
        A dictionary with the operation status and a message.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent world restore."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    result = {}
    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")
        if not backup_file_path:
            raise MissingArgumentError("Backup file path cannot be empty.")

        plugin_manager.trigger_event(
            "before_restore",
            server_name=server_name,
            restore_type="world",
            backup_file_path=backup_file_path,
            stop_start_server=stop_start_server,
        )
        backup_filename = os.path.basename(backup_file_path)
        logger.info(
            f"API: Initiating world restore for '{server_name}' from '{backup_filename}'. Stop/Start: {stop_start_server}"
        )

        try:
            if not os.path.isfile(backup_file_path):
                raise AppFileNotFoundError(backup_file_path, "Backup file")

            with server_lifecycle_manager(
                server_name, stop_before=stop_start_server, restart_on_success_only=True
            ):
                server = BedrockServer(server_name)
                server.import_active_world_from_mcworld(backup_file_path)

            result = {
                "status": "success",
                "message": f"World restore from '{backup_filename}' completed successfully for server '{server_name}'.",
            }

        except (BSMError, FileNotFoundError) as e:
            logger.error(
                f"API: World restore failed for '{server_name}': {e}", exc_info=True
            )
            result = {"status": "error", "message": f"World restore failed: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during world restore for '{server_name}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"Unexpected error during world restore: {e}",
            }
        finally:
            plugin_manager.trigger_event(
                "after_restore",
                server_name=server_name,
                restore_type="world",
                result=result,
            )

    finally:
        _backup_restore_lock.release()

    return result


@plugin_method("restore_config_file")
def restore_config_file(
    server_name: str, backup_file_path: str, stop_start_server: bool = True
) -> Dict[str, str]:
    """Restores a specific config file from a backup.

    This operation is thread-safe and guarded by a lock.

    Args:
        server_name: The name of the server.
        backup_file_path: The absolute path to the configuration backup file.
        stop_start_server: If True, stop the server before restoring and
            restart it only if the restore is successful. Defaults to True.

    Returns:
        A dictionary with the operation status and a message.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent config restore."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    result = {}
    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")
        if not backup_file_path:
            raise MissingArgumentError("Backup file path cannot be empty.")

        plugin_manager.trigger_event(
            "before_restore",
            server_name=server_name,
            restore_type="config_file",
            backup_file_path=backup_file_path,
            stop_start_server=stop_start_server,
        )
        backup_filename = os.path.basename(backup_file_path)
        logger.info(
            f"API: Initiating config restore for '{server_name}' from '{backup_filename}'. Stop/Start: {stop_start_server}"
        )

        try:
            if not os.path.isfile(backup_file_path):
                raise AppFileNotFoundError(backup_file_path, "Backup file")

            with server_lifecycle_manager(
                server_name, stop_before=stop_start_server, restart_on_success_only=True
            ):
                server = BedrockServer(server_name)
                restored_file = server._restore_config_file_internal(backup_file_path)

            result = {
                "status": "success",
                "message": f"Config file '{os.path.basename(restored_file)}' restored successfully from '{backup_filename}'.",
            }

        except (BSMError, FileNotFoundError) as e:
            logger.error(
                f"API: Config file restore failed for '{server_name}': {e}",
                exc_info=True,
            )
            result = {"status": "error", "message": f"Config file restore failed: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during config file restore for '{server_name}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"Unexpected error during config file restore: {e}",
            }
        finally:
            plugin_manager.trigger_event(
                "after_restore",
                server_name=server_name,
                restore_type="config_file",
                result=result,
            )

    finally:
        _backup_restore_lock.release()

    return result


@plugin_method("prune_old_backups")
def prune_old_backups(server_name: str) -> Dict[str, str]:
    """Prunes old backups for a server based on retention settings.

    This operation is thread-safe and guarded by a lock. It removes old
    backups for the world and all standard configuration files.

    Args:
        server_name: The name of the server whose backups will be pruned.

    Returns:
        A dictionary with the operation status and a message. Can return an
        'error' status if some, but not all, pruning operations fail.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent prune."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    result = {}
    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")

        plugin_manager.trigger_event("before_prune_backups", server_name=server_name)
        logger.info(
            f"API: Initiating pruning of old backups for server '{server_name}'."
        )

        try:
            server = BedrockServer(server_name)
            # If the backup directory doesn't exist, there's nothing to do.
            if not server.server_backup_directory or not os.path.isdir(
                server.server_backup_directory
            ):
                result = {
                    "status": "success",
                    "message": "No backup directory found, nothing to prune.",
                }
                return result

            pruning_errors = []
            # Prune world backups.
            try:
                world_name = server.get_world_name()
                world_name_prefix = f"{world_name}_backup_"
                server.prune_server_backups(world_name_prefix, "mcworld")
            except Exception as e:
                err_msg = f"world backups ({type(e).__name__})"
                pruning_errors.append(err_msg)
                logger.error(
                    f"Error pruning world backups for '{server_name}': {e}",
                    exc_info=True,
                )

            # Define config files and their corresponding prefixes/extensions to prune.
            config_file_types = {
                "server.properties_backup_": "properties",
                "allowlist_backup_": "json",
                "permissions_backup_": "json",
            }
            # Prune each type of config file backup.
            for prefix, ext in config_file_types.items():
                try:
                    server.prune_server_backups(prefix, ext)
                except Exception as e:
                    err_msg = f"config backups ({prefix}*.{ext}) ({type(e).__name__})"
                    pruning_errors.append(err_msg)
                    logger.error(
                        f"Error pruning {prefix}*.{ext} for '{server_name}': {e}",
                        exc_info=True,
                    )

            # Report final status based on whether any errors occurred.
            if pruning_errors:
                result = {
                    "status": "error",
                    "message": f"Pruning completed with errors: {'; '.join(pruning_errors)}",
                }
            else:
                result = {
                    "status": "success",
                    "message": f"Backup pruning completed for server '{server_name}'.",
                }

        except (BSMError, ValueError) as e:
            logger.error(
                f"API: Cannot prune backups for '{server_name}': {e}", exc_info=True
            )
            result = {"status": "error", "message": f"Pruning setup error: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during backup pruning for '{server_name}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"Unexpected error during pruning: {e}",
            }
        finally:
            plugin_manager.trigger_event(
                "after_prune_backups", server_name=server_name, result=result
            )

    finally:
        _backup_restore_lock.release()

    return result
