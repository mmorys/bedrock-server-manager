# bedrock-server-manager/bedrock_server_manager/core/server/backup.py
"""
Provides functions for creating and managing backups of Bedrock server worlds
and configuration files, as well as restoring from these backups.
"""

import os
import glob
import re
import shutil
import logging
from typing import Optional

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.core.server import world
from bedrock_server_manager.core.server import server
from bedrock_server_manager.error import (
    MissingArgumentError,
    FileOperationError,
    DirectoryError,
    InvalidInputError,
    BackupWorldError,
    RestoreError,
    AddonExtractError,
)
from bedrock_server_manager.utils import general

logger = logging.getLogger("bedrock_server_manager")


def prune_old_backups(
    backup_dir: str, backup_keep: int, file_prefix: str = "", file_extension: str = ""
) -> None:
    """
    Removes the oldest backup files in a directory, keeping a specified number.

    Args:
        backup_dir: The directory containing the backup files.
        backup_keep: The maximum number of backup files to retain. Files are
                     sorted by modification time (newest first).
        file_prefix: Optional prefix to filter backup files (e.g., "world_backup_").
        file_extension: Optional extension to filter backup files (e.g., "mcworld").
                        Do not include the leading dot.

    Raises:
        MissingArgumentError: If `backup_dir` is empty.
        ValueError: If `backup_keep` cannot be converted to a valid integer >= 0.
        DirectoryError: If `backup_dir` exists but is not a directory.
        InvalidInputError: If neither `file_prefix` nor `file_extension` is provided.
        FileOperationError: If deleting an old backup file fails due to an OS error.
    """
    if not backup_dir:
        raise MissingArgumentError("Backup directory cannot be empty for pruning.")

    logger.info(
        f"Checking backup directory for pruning: '{backup_dir}' (keeping {backup_keep})"
    )

    if not os.path.isdir(backup_dir):
        # It's okay if the directory doesn't exist yet, just means no backups to prune.
        if os.path.exists(backup_dir):
            error_msg = f"Backup path '{backup_dir}' exists but is not a directory."
            logger.error(error_msg)
            raise DirectoryError(error_msg)
        else:
            logger.info(
                f"Backup directory '{backup_dir}' does not exist. Nothing to prune."
            )
            return

    try:
        num_to_keep = int(backup_keep)
        if num_to_keep < 0:
            raise ValueError("Number of backups to keep cannot be negative.")
    except ValueError as e:
        logger.error(
            f"Invalid value for backups to keep: '{backup_keep}'. Must be an integer >= 0."
        )
        raise ValueError(f"Invalid value for backups to keep: {e}") from e

    # Construct the search pattern for glob
    if not file_prefix and not file_extension:
        error_msg = "Cannot prune backups without specifying either a file_prefix or file_extension."
        logger.error(error_msg)
        raise InvalidInputError(error_msg)

    # Build pattern
    pattern = file_prefix + "*"
    if file_extension:
        # Ensure extension doesn't start with a dot if provided that way
        cleaned_extension = file_extension.lstrip(".")
        pattern += "." + cleaned_extension

    glob_pattern = os.path.join(backup_dir, pattern)
    logger.debug(f"Using glob pattern for pruning: '{glob_pattern}'")

    try:
        # Find matching backup files
        # Sort by modification time, newest first (reverse=True)
        backup_files = sorted(
            glob.glob(glob_pattern), key=os.path.getmtime, reverse=True
        )
        logger.debug(
            f"Found {len(backup_files)} potential backup file(s) matching pattern."
        )

        if len(backup_files) > num_to_keep:
            num_to_delete = len(backup_files) - num_to_keep
            files_to_delete = backup_files[num_to_keep:]  # Get the oldest files
            logger.info(
                f"Found {len(backup_files)} backups. Deleting {num_to_delete} oldest file(s) to keep {num_to_keep}."
            )

            deleted_count = 0
            for old_backup_path in files_to_delete:
                try:
                    logger.info(
                        f"Removing old backup: {os.path.basename(old_backup_path)}"
                    )
                    os.remove(old_backup_path)
                    deleted_count += 1
                except OSError as e:
                    logger.error(
                        f"Failed to remove old backup '{old_backup_path}': {e}",
                        exc_info=True,
                    )
                    # Continue trying to delete others, but report the overall failure later
            if deleted_count < num_to_delete:
                # If some deletions failed, raise error after trying all
                raise FileOperationError(
                    f"Failed to delete all required old backups ({num_to_delete - deleted_count} deletion(s) failed). Check logs."
                )
            logger.info(f"Successfully deleted {deleted_count} old backup(s).")

        else:
            logger.info(
                f"Found {len(backup_files)} backup(s), which is not more than the {num_to_keep} to keep. No files deleted."
            )

    except OSError as e:
        logger.error(
            f"OS error occurred while accessing or pruning backups in '{backup_dir}': {e}",
            exc_info=True,
        )
        raise FileOperationError(f"Error pruning backups in '{backup_dir}': {e}") from e
    except Exception as e:
        # Catch unexpected errors during glob or sorting
        logger.error(
            f"Unexpected error during backup pruning process: {e}", exc_info=True
        )
        raise FileOperationError(f"Unexpected error during backup pruning: {e}") from e


def backup_world(world_path: str, backup_dir: str, world_name: str) -> None:
    """
    Creates a backup of a specific world directory as an .mcworld file.

    Args:
        world_path: The full path to the source world directory.
        backup_dir: The directory where the .mcworld backup file will be saved.
        world_name: The name of the world (used for the backup filename).

    Raises:
        MissingArgumentError: If required arguments are empty.
        DirectoryError: If `world_path` does not exist or is not a directory.
        FileOperationError: If creating the backup directory fails, or if
                            the world export process fails (raised by world.export_world).
        AddonExtractError: If zipping the world fails (raised by world.export_world).
    """
    if not world_path:
        raise MissingArgumentError("World path cannot be empty.")
    if not backup_dir:
        raise MissingArgumentError("Backup directory cannot be empty.")
    if not world_name:
        raise MissingArgumentError("World name cannot be empty.")

    logger.info(f"Starting world backup for path: '{world_path}'")

    if not os.path.isdir(world_path):
        error_msg = (
            f"Source world directory not found or is not a directory: '{world_path}'"
        )
        logger.error(error_msg)
        raise DirectoryError(error_msg)

    # Ensure backup directory exists
    try:
        os.makedirs(backup_dir, exist_ok=True)
        logger.debug(f"Ensured backup directory exists: {backup_dir}")
    except OSError as e:
        logger.error(
            f"Failed to create backup directory '{backup_dir}': {e}", exc_info=True
        )
        raise FileOperationError(
            f"Cannot create backup directory '{backup_dir}': {e}"
        ) from e

    timestamp = general.get_timestamp()
    # Use the provided world_name for the filename base
    backup_filename = f"{world_name}_backup_{timestamp}.mcworld"
    backup_file_path = os.path.join(backup_dir, backup_filename)

    logger.info(f"Creating world backup file: '{backup_filename}' in '{backup_dir}'...")

    try:
        # Delegate the actual zipping process to the world module
        world.export_world(
            world_path, backup_file_path
        )  # Raises AddonExtractError, FileOperationError
        logger.info(f"World backup created successfully: {backup_file_path}")
    except (AddonExtractError, FileOperationError) as e:
        logger.error(
            f"Failed to export world '{world_path}' to '{backup_file_path}': {e}",
            exc_info=True,
        )
        raise  # Re-raise the specific error from world.export_world
    except Exception as e:
        logger.error(f"Unexpected error during world export: {e}", exc_info=True)
        raise FileOperationError(
            f"Unexpected error exporting world '{world_name}': {e}"
        ) from e


def backup_config_file(file_to_backup: str, backup_dir: str) -> None:
    """
    Creates a timestamped backup copy of a single configuration file.

    Args:
        file_to_backup: The full path to the configuration file to back up.
        backup_dir: The directory where the backup copy will be saved.

    Raises:
        MissingArgumentError: If `file_to_backup` or `backup_dir` is empty.
        FileNotFoundError: If `file_to_backup` does not exist.
        FileOperationError: If creating the backup directory fails or copying the file fails.
    """
    if not file_to_backup:
        raise MissingArgumentError("File path to backup cannot be empty.")
    if not backup_dir:
        raise MissingArgumentError("Backup directory cannot be empty.")

    file_basename = os.path.basename(file_to_backup)
    logger.info(f"Starting backup for config file: '{file_basename}'")

    if not os.path.isfile(file_to_backup):
        error_msg = f"Configuration file not found or is not a file: '{file_to_backup}'"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    # Ensure backup directory exists
    try:
        os.makedirs(backup_dir, exist_ok=True)
        logger.debug(f"Ensured backup directory exists: {backup_dir}")
    except OSError as e:
        logger.error(
            f"Failed to create backup directory '{backup_dir}': {e}", exc_info=True
        )
        raise FileOperationError(
            f"Cannot create backup directory '{backup_dir}': {e}"
        ) from e

    # Construct backup filename (e.g., server.properties -> server_backup_YYYYMMDD_HHMMSS.properties)
    name_part, ext_part = os.path.splitext(file_basename)
    timestamp = general.get_timestamp()
    backup_filename = f"{name_part}_backup_{timestamp}{ext_part}"
    destination_path = os.path.join(backup_dir, backup_filename)

    logger.debug(
        f"Copying '{file_basename}' to backup destination: '{destination_path}'"
    )
    try:
        # copy2 preserves metadata like modification time
        shutil.copy2(file_to_backup, destination_path)
        logger.info(
            f"Config file '{file_basename}' backed up successfully to '{backup_filename}' in '{backup_dir}'."
        )
    except OSError as e:
        logger.error(
            f"Failed to copy config file '{file_to_backup}' to '{destination_path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to copy config file '{file_basename}': {e}"
        ) from e


def backup_server(
    server_name: str,
    backup_type: str,
    base_dir: str,
    file_to_backup: Optional[str] = None,
) -> None:
    """
    Manages the backup process for either a server's world or a specific config file.

    Coordinates determining paths, creating backup directories, and calling the
    appropriate backup function (`backup_world` or `backup_config_file`). Also handles pruning.

    Args:
        server_name: The name of the server.
        backup_type: The type of backup to perform ("world" or "config").
        base_dir: The base directory containing all server installations.
        file_to_backup: The relative path (from server base) of the config file
                        to back up if `backup_type` is "config". Required in that case.

    Raises:
        MissingArgumentError: If required arguments are missing for the specified `backup_type`.
        InvalidInputError: If `backup_type` is not "world" or "config".
        BackupWorldError: If a world backup fails (wraps underlying errors).
        FileOperationError: If getting world name fails, config backup fails, or pruning fails.
        DirectoryError: If world directory is not found.
        ValueError: If backup_keep setting is invalid during pruning.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not backup_type:
        raise MissingArgumentError("Backup type cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    # Normalize backup type
    backup_type = backup_type.lower()
    logger.info(f"Initiating '{backup_type}' backup for server '{server_name}'.")

    # Determine backup directory path
    backup_base_dir = settings.get("BACKUP_DIR")
    if not backup_base_dir:
        raise FileOperationError(
            "BACKUP_DIR setting is missing or empty in configuration."
        )
    server_backup_dir = os.path.join(backup_base_dir, server_name)

    # Ensure the server-specific backup directory exists (needed for both types)
    try:
        os.makedirs(server_backup_dir, exist_ok=True)
        logger.debug(f"Ensured server backup directory exists: {server_backup_dir}")
    except OSError as e:
        logger.error(
            f"Failed to create server backup directory '{server_backup_dir}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Cannot create server backup directory '{server_backup_dir}': {e}"
        ) from e

    if backup_type == "world":
        try:
            # Determine world path
            world_name = server.get_world_name(
                server_name, base_dir
            )  # Raises FileOperationError
            if not world_name:
                raise FileOperationError(
                    f"Could not determine world name for server '{server_name}'. Cannot perform world backup."
                )
            world_path = os.path.join(base_dir, server_name, "worlds", world_name)

            # Perform world backup
            backup_world(
                world_path, server_backup_dir, world_name
            )  # Raises DirectoryError, FileOperationError, AddonExtractError

        except (
            DirectoryError,
            AddonExtractError,
            FileOperationError,
        ) as e:
            logger.error(
                f"World backup process failed for server '{server_name}': {e}",
                exc_info=True,
            )
            raise BackupWorldError(
                f"World backup failed for '{server_name}': {e}"
            ) from e
        except Exception as e:
            logger.error(
                f"Unexpected error during world backup for server '{server_name}': {e}",
                exc_info=True,
            )
            raise BackupWorldError(
                f"Unexpected world backup error for '{server_name}': {e}"
            ) from e

    elif backup_type == "config":
        if not file_to_backup:
            raise MissingArgumentError(
                "Config file path is required for backup type 'config'."
            )

        full_config_path = os.path.join(base_dir, server_name, file_to_backup)
        config_filename = os.path.basename(file_to_backup)
        name_part, ext_part = os.path.splitext(config_filename)

        try:
            # Perform config file backup
            backup_config_file(
                full_config_path, server_backup_dir
            )  # Raises FileNotFoundError, FileOperationError

        except (
            FileNotFoundError,
            FileOperationError,
        ) as e:
            logger.error(
                f"Config backup process failed for '{config_filename}' on server '{server_name}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Config backup failed for '{config_filename}': {e}"
            ) from e
        except Exception as e:
            logger.error(
                f"Unexpected error during config backup for '{config_filename}' on server '{server_name}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Unexpected config backup error for '{config_filename}': {e}"
            ) from e

    else:
        logger.error(
            f"Invalid backup type provided: '{backup_type}'. Must be 'world' or 'config'."
        )
        raise InvalidInputError(f"Invalid backup type: {backup_type}")


def backup_all(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    Performs a full backup of a server, including its world and standard config files.

    Args:
        server_name: The name of the server to back up.
        base_dir: Optional. The base directory containing all server installations.
                  Defaults to the value from application settings if None.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        BackupWorldError: If the world backup fails.
        FileOperationError: If any configuration file backup fails, or if determining
                            world name fails. Also raised if BACKUP_DIR setting is missing.
        # Other exceptions related to pruning might be raised indirectly.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty for backup_all.")

    # Use provided base_dir or get from settings
    effective_base_dir = base_dir if base_dir is not None else settings.get("BASE_DIR")
    if not effective_base_dir:
        raise FileOperationError(
            "BASE_DIR setting is missing or empty in configuration."
        )

    logger.info(f"Starting full backup process for server: '{server_name}'")

    # 1. Backup World
    try:
        logger.info("Backing up server world...")
        backup_server(server_name, "world", effective_base_dir)
        logger.info("World backup completed.")
    except BackupWorldError as e:
        # Log the specific error and re-raise as BackupWorldError to signal overall failure
        logger.error(
            f"Full backup failed: World backup step failed for server '{server_name}'. Error: {e}",
            exc_info=True,
        )
        raise BackupWorldError(
            f"World backup failed during full backup of '{server_name}'."
        ) from e
    except Exception as e:  # Catch unexpected errors during world backup step
        logger.error(
            f"Full backup failed: Unexpected error during world backup step for server '{server_name}'. Error: {e}",
            exc_info=True,
        )
        raise BackupWorldError(
            f"Unexpected error during world backup of '{server_name}'."
        ) from e

    # 2. Backup Configuration Files
    config_files_to_backup = ["allowlist.json", "permissions.json", "server.properties"]
    failed_configs = []
    for config_file in config_files_to_backup:
        logger.info(f"Backing up config file: '{config_file}'...")
        try:
            # Check if file exists before attempting backup to avoid unnecessary errors if optional files are missing
            full_config_path = os.path.join(
                effective_base_dir, server_name, config_file
            )
            if os.path.exists(full_config_path):
                backup_server(
                    server_name,
                    "config",
                    effective_base_dir,
                    file_to_backup=config_file,
                )
                logger.info(f"Config file '{config_file}' backup completed.")
            else:
                logger.warning(
                    f"Config file '{config_file}' not found for server '{server_name}'. Skipping backup for this file."
                )
        except FileOperationError as e:
            logger.error(
                f"Failed to back up config file '{config_file}' for server '{server_name}': {e}",
                exc_info=True,
            )
            failed_configs.append(config_file)
        except Exception as e:  # Catch unexpected errors during this config backup
            logger.error(
                f"Unexpected error backing up config file '{config_file}' for server '{server_name}': {e}",
                exc_info=True,
            )
            failed_configs.append(config_file)

    # Report overall success or partial failure
    if failed_configs:
        error_msg = f"Full backup completed with errors. Failed to back up config file(s): {', '.join(failed_configs)}."
        logger.error(error_msg)
        # Raise FileOperationError to indicate partial failure
        raise FileOperationError(error_msg)
    else:
        logger.info(f"Full backup completed successfully for server: '{server_name}'.")


def restore_config_file(backup_file_path: str, server_dir: str) -> None:
    """
    Restores a single configuration file from a backup copy to the server directory.

    Determines the original filename based on the backup filename pattern
    (e.g., 'server_backup_TIMESTAMP.properties' -> 'server.properties').

    Args:
        backup_file_path: The full path to the backup file.
        server_dir: The full path to the target server's base directory.

    Raises:
        MissingArgumentError: If `backup_file_path` or `server_dir` is empty.
        FileNotFoundError: If `backup_file_path` does not exist.
        FileOperationError: If `server_dir` does not exist or is not a directory,
                            or if copying the file fails.
        InvalidInputError: If the original filename cannot be determined from the backup filename.
    """
    if not backup_file_path:
        raise MissingArgumentError("Backup file path cannot be empty.")
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")

    backup_filename = os.path.basename(backup_file_path)
    logger.info(f"Attempting to restore config file from backup: '{backup_filename}'")

    if not os.path.exists(backup_file_path):
        raise FileNotFoundError(f"Backup file not found: '{backup_file_path}'")
    if not os.path.isdir(server_dir):
        raise FileOperationError(
            f"Target server directory does not exist or is not a directory: '{server_dir}'"
        )

    # Extract original filename (e.g., server.properties from server_backup_....properties)
    match = re.match(r"^(.*?)_backup_\d{8}_\d{6}(\..*)$", backup_filename)
    if not match:
        error_msg = f"Could not determine original filename from backup file format: '{backup_filename}'"
        logger.error(error_msg)
        raise InvalidInputError(error_msg)

    original_name_part = match.group(1)
    original_ext_part = match.group(2)
    target_filename = f"{original_name_part}{original_ext_part}"
    target_file_path = os.path.join(server_dir, target_filename)

    logger.info(
        f"Restoring '{backup_filename}' as '{target_filename}' in '{server_dir}'..."
    )
    try:
        # copy2 preserves metadata
        shutil.copy2(backup_file_path, target_file_path)
        logger.info(f"Successfully restored config file to: {target_file_path}")
    except OSError as e:
        logger.error(
            f"Failed to copy backup file '{backup_filename}' to '{target_file_path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to restore config file '{target_filename}': {e}"
        ) from e


def restore_server(
    server_name: str, backup_file_path: str, restore_type: str, base_dir: str
) -> None:
    """
    Manages the restoration process for either a server's world or a config file.

    Args:
        server_name: The name of the target server.
        backup_file_path: The full path to the backup file (.mcworld or config backup).
        restore_type: The type of restoration ("world" or "config").
        base_dir: The base directory containing all server installations.

    Raises:
        MissingArgumentError: If required arguments are empty.
        InvalidInputError: If `restore_type` is not "world" or "config".
        FileNotFoundError: If `backup_file_path` does not exist.
        FileOperationError: If restoration fails (raised by delegates or path issues).
        DirectoryError: If server directory structure is invalid.
        AddonExtractError: If world restoration (unzipping) fails.
        RestoreError: If world import fails for other reasons.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not backup_file_path:
        raise MissingArgumentError("Backup file path cannot be empty.")
    if not restore_type:
        raise MissingArgumentError("Restore type cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    # Normalize restore type
    restore_type = restore_type.lower()
    backup_filename = os.path.basename(backup_file_path)
    logger.info(
        f"Initiating '{restore_type}' restore for server '{server_name}' from '{backup_filename}'."
    )

    # Validate backup file existence early
    if not os.path.exists(backup_file_path):
        raise FileNotFoundError(f"Backup file not found: '{backup_file_path}'")

    server_dir = os.path.join(base_dir, server_name)
    # Ensure server directory exists for config restore target
    if not os.path.isdir(server_dir):
        logger.warning(f"Server directory '{server_dir}' does not exist...")
        # Depending on strictness, could raise DirectoryError here.

    if restore_type == "world":
        logger.debug("Delegating to world import function.")
        try:
            # world.import_world handles finding world name, extracting, etc.
            world.import_world(
                server_name, backup_file_path, base_dir
            )  # Raises various errors
            logger.info(
                f"World restore from '{backup_filename}' completed successfully for server '{server_name}'."
            )
        except (
            AddonExtractError,
            FileOperationError,
            DirectoryError,
            RestoreError,
        ) as e:
            logger.error(
                f"World restore failed for server '{server_name}' from '{backup_filename}': {e}",
                exc_info=True,
            )
            raise  # Re-raise specific error from import_world
        except Exception as e:
            logger.error(
                f"Unexpected error during world restore for '{server_name}': {e}",
                exc_info=True,
            )
            raise RestoreError(
                f"Unexpected world restore error for '{server_name}': {e}"
            ) from e

    elif restore_type == "config":
        logger.debug("Delegating to config restore function.")
        try:
            restore_config_file(
                backup_file_path, server_dir
            )  # Raises FileNotFoundError, FileOperationError, InvalidInputError
            # Success message is logged within restore_config_file
        except (FileNotFoundError, FileOperationError, InvalidInputError) as e:
            logger.error(
                f"Config restore failed for server '{server_name}' from '{backup_filename}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Config restore failed for '{backup_filename}': {e}"
            ) from e  # Wrap as FileOperationError for consistency? Or keep original? Let's keep original.
            # raise e
        except Exception as e:
            logger.error(
                f"Unexpected error during config restore for '{server_name}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Unexpected config restore error for '{server_name}': {e}"
            ) from e
    else:
        logger.error(
            f"Invalid restore type provided: '{restore_type}'. Must be 'world' or 'config'."
        )
        raise InvalidInputError(f"Invalid restore type: {restore_type}")


def restore_all(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    Restores a server to its latest backed-up state (world and config files).

    Finds the newest backup file for the world and each standard configuration
    file within the server's backup directory and restores them.

    Args:
        server_name: The name of the server to restore.
        base_dir: Optional. The base directory containing all server installations.
                  Defaults to the value from application settings if None.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        RestoreError: If any restore operation (world or config) fails. The function
                      attempts all restores even if one fails, but raises at the end
                      if any failures occurred.
        FileOperationError: If the server's backup directory cannot be accessed, or
                            if the BASE_DIR/BACKUP_DIR settings are missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty for restore_all.")

    effective_base_dir = base_dir if base_dir is not None else settings.get("BASE_DIR")
    backup_base_dir = settings.get("BACKUP_DIR")

    if not effective_base_dir:
        raise FileOperationError("BASE_DIR setting is missing or empty.")
    if not backup_base_dir:
        raise FileOperationError("BACKUP_DIR setting is missing or empty.")

    server_backup_dir = os.path.join(backup_base_dir, server_name)
    logger.info(
        f"Starting restore_all process for server '{server_name}' from backups in '{server_backup_dir}'."
    )

    if not os.path.isdir(server_backup_dir):
        logger.warning(
            f"No backup directory found for server '{server_name}' at '{server_backup_dir}'. Cannot restore."
        )
        # Return gracefully if no backups exist for the server
        return

    failures = []  # Keep track of failed restore operations

    # 1. Restore World (Latest .mcworld)
    try:
        logger.debug("Searching for latest world backup (.mcworld)...")
        world_backups = glob.glob(os.path.join(server_backup_dir, "*.mcworld"))
        if world_backups:
            latest_world_backup = max(world_backups, key=os.path.getmtime)
            logger.info(
                f"Found latest world backup: {os.path.basename(latest_world_backup)}"
            )
            restore_server(
                server_name, latest_world_backup, "world", effective_base_dir
            )
        else:
            logger.info("No .mcworld backup files found. Skipping world restore.")
    except Exception as e:
        logger.error(
            f"Failed to restore world for server '{server_name}': {e}", exc_info=True
        )
        failures.append(f"World ({e})")

    # 2. Restore Config Files (Latest of each type)
    config_patterns = {
        "server.properties": os.path.join(
            server_backup_dir, "server_backup_*.properties"
        ),
        "allowlist.json": os.path.join(server_backup_dir, "allowlist_backup_*.json"),
        "permissions.json": os.path.join(
            server_backup_dir, "permissions_backup_*.json"
        ),
    }

    for config_type, pattern in config_patterns.items():
        try:
            logger.debug(
                f"Searching for latest '{config_type}' backup (pattern: '{os.path.basename(pattern)}')..."
            )
            config_backups = glob.glob(pattern)
            if config_backups:
                latest_config_backup = max(config_backups, key=os.path.getmtime)
                logger.info(
                    f"Found latest '{config_type}' backup: {os.path.basename(latest_config_backup)}"
                )
                restore_server(
                    server_name, latest_config_backup, "config", effective_base_dir
                )
            else:
                logger.info(
                    f"No backup found for '{config_type}'. Skipping restore for this file."
                )
        except Exception as e:
            logger.error(
                f"Failed to restore '{config_type}' for server '{server_name}': {e}",
                exc_info=True,
            )
            failures.append(f"{config_type} ({e})")

    # 3. Report final status
    if failures:
        error_summary = ", ".join(failures)
        logger.error(
            f"Restore process for server '{server_name}' completed with errors. Failed components: {error_summary}"
        )
        raise RestoreError(
            f"Restore failed for server '{server_name}'. Failed components: {error_summary}"
        )
    else:
        logger.info(
            f"Restore process completed successfully for server '{server_name}'."
        )
