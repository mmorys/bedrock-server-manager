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
from typing import Optional, Dict

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.core.server import world as core_world
from bedrock_server_manager.core.server import server as core_server_utils
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

    if not file_prefix and not file_extension:
        error_msg = "Cannot prune backups without specifying either a file_prefix or file_extension."
        logger.error(error_msg)
        raise InvalidInputError(error_msg)

    pattern = file_prefix + "*"
    if file_extension:
        cleaned_extension = file_extension.lstrip(".")
        pattern += "." + cleaned_extension

    glob_pattern = os.path.join(backup_dir, pattern)
    logger.debug(f"Using glob pattern for pruning: '{glob_pattern}'")

    try:
        backup_files = sorted(
            glob.glob(glob_pattern), key=os.path.getmtime, reverse=True
        )
        logger.debug(
            f"Found {len(backup_files)} potential backup file(s) matching pattern."
        )

        if len(backup_files) > num_to_keep:
            num_to_delete = len(backup_files) - num_to_keep
            files_to_delete = backup_files[num_to_keep:]
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
            if deleted_count < num_to_delete:
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
        logger.error(
            f"Unexpected error during backup pruning process: {e}", exc_info=True
        )
        raise FileOperationError(f"Unexpected error during backup pruning: {e}") from e


def backup_world_data(world_path: str, backup_dir: str, world_name: str) -> str:
    """
    Creates a backup of a specific world directory as an .mcworld file.
    This function now returns the path to the created backup file.

    Args:
        world_path: The full path to the source world directory.
        backup_dir: The directory where the .mcworld backup file will be saved.
        world_name: The name of the world (used for the backup filename).

    Returns:
        The full path to the created .mcworld backup file.

    Raises:
        MissingArgumentError: If required arguments are empty.
        DirectoryError: If `world_path` does not exist or is not a directory.
        FileOperationError: If creating the backup directory fails, or if
                            the world export process fails (raised by core_world.export_world).
        AddonExtractError: If zipping the world fails (raised by core_world.export_world).
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
    backup_filename = f"{world_name}_backup_{timestamp}.mcworld"
    backup_file_path = os.path.join(backup_dir, backup_filename)

    logger.info(f"Creating world backup file: '{backup_filename}' in '{backup_dir}'...")

    try:
        core_world.export_world(world_path, backup_file_path)
        logger.info(f"World backup created successfully: {backup_file_path}")
        return backup_file_path
    except (AddonExtractError, FileOperationError) as e:
        logger.error(
            f"Failed to export world '{world_path}' to '{backup_file_path}': {e}",
            exc_info=True,
        )
        raise
    except Exception as e:
        logger.error(f"Unexpected error during world export: {e}", exc_info=True)
        raise FileOperationError(
            f"Unexpected error exporting world '{world_name}': {e}"
        ) from e


def backup_single_config_file(file_to_backup: str, backup_dir: str) -> str:
    """
    Creates a timestamped backup copy of a single configuration file.
    This function now returns the path to the created backup file.

    Args:
        file_to_backup: The full path to the configuration file to back up.
        backup_dir: The directory where the backup copy will be saved.

    Returns:
        The full path to the created backup config file.

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

    name_part, ext_part = os.path.splitext(file_basename)
    timestamp = general.get_timestamp()
    backup_filename = f"{name_part}_backup_{timestamp}{ext_part}"
    destination_path = os.path.join(backup_dir, backup_filename)

    logger.debug(
        f"Copying '{file_basename}' to backup destination: '{destination_path}'"
    )
    try:
        shutil.copy2(file_to_backup, destination_path)
        logger.info(
            f"Config file '{file_basename}' backed up successfully to '{backup_filename}' in '{backup_dir}'."
        )
        return destination_path
    except OSError as e:
        logger.error(
            f"Failed to copy config file '{file_to_backup}' to '{destination_path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to copy config file '{file_basename}': {e}"
        ) from e


def backup_all_server_data(server_name: str, base_dir: str) -> Dict[str, Optional[str]]:
    """
    Performs a full backup of a server: its world and standard config files.
    Returns a dictionary of backed up components and their paths, or None if failed.

    Args:
        server_name: The name of the server to back up.
        base_dir: The base directory containing all server installations.

    Returns:
        A dictionary mapping component type (e.g., "world", "server.properties")
        to the path of its backup file, or None if that component's backup failed.

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        FileOperationError: If essential settings (BACKUP_DIR) are missing, or if
                            determining world name fails.
        BackupWorldError: If the world backup specifically fails catastrophically.
                          Other config backup failures are reported in the return dict.
    """
    if not server_name:
        raise MissingArgumentError(
            "Server name cannot be empty for backup_all_server_data."
        )
    if not base_dir:
        raise MissingArgumentError(
            "Base directory cannot be empty for backup_all_server_data."
        )

    backup_base_dir = settings.get("BACKUP_DIR")
    if not backup_base_dir:
        raise FileOperationError(
            "BACKUP_DIR setting is missing or empty in configuration."
        )
    server_backup_dir = os.path.join(backup_base_dir, server_name)

    try:
        os.makedirs(server_backup_dir, exist_ok=True)
    except OSError as e:
        raise FileOperationError(
            f"Cannot create server backup directory '{server_backup_dir}': {e}"
        ) from e

    logger.info(
        f"Starting full backup process for server: '{server_name}' into '{server_backup_dir}'"
    )
    backup_results: Dict[str, Optional[str]] = {}

    # 1. Backup World
    try:
        logger.info("Backing up server world...")
        world_name = core_server_utils.get_world_name(server_name, base_dir)
        world_path = os.path.join(base_dir, server_name, "worlds", world_name)
        backup_results["world"] = backup_world_data(
            world_path, server_backup_dir, world_name
        )
        logger.info("World backup completed.")
    except Exception as e:  # Catching broader exceptions here for the component
        logger.error(
            f"World backup failed for server '{server_name}': {e}", exc_info=True
        )
        backup_results["world"] = None
        # Depending on desired atomicity, you might choose to raise BackupWorldError here
        # and halt, or continue with configs. Current approach: continue.

    # 2. Backup Configuration Files
    config_files_to_backup = ["allowlist.json", "permissions.json", "server.properties"]
    for config_file_name in config_files_to_backup:
        logger.info(f"Backing up config file: '{config_file_name}'...")
        full_config_path = os.path.join(base_dir, server_name, config_file_name)
        if os.path.exists(full_config_path):
            try:
                backup_results[config_file_name] = backup_single_config_file(
                    full_config_path, server_backup_dir
                )
                logger.info(f"Config file '{config_file_name}' backup completed.")
            except Exception as e:
                logger.error(
                    f"Failed to back up config file '{config_file_name}' for server '{server_name}': {e}",
                    exc_info=True,
                )
                backup_results[config_file_name] = None
        else:
            logger.warning(
                f"Config file '{config_file_name}' not found for server '{server_name}'. Skipping backup for this file."
            )
            backup_results[config_file_name] = (
                None  # Explicitly mark as not backed up / skipped
            )

    if all(
        value is None for value in backup_results.values() if value is not None
    ):  # if all attempted backups failed
        if (
            backup_results.get("world") is None and "world" in backup_results
        ):  # Check if world backup was attempted and failed
            raise BackupWorldError(
                f"Core world backup failed for '{server_name}' and no other components succeeded."
            )

    return backup_results


def restore_config_file_data(backup_file_path: str, server_dir: str) -> str:
    """
    Restores a single configuration file from a backup copy to the server directory.
    Returns the path of the restored file.

    Args:
        backup_file_path: The full path to the backup file.
        server_dir: The full path to the target server's base directory.

    Returns:
        The full path of the file that was restored in the server directory.

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
    if not os.path.isdir(server_dir):  # server_dir must exist for restore
        os.makedirs(server_dir, exist_ok=True)  # Create if not exists
        # raise FileOperationError(
        #     f"Target server directory does not exist or is not a directory: '{server_dir}'"
        # )

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
        shutil.copy2(backup_file_path, target_file_path)
        logger.info(f"Successfully restored config file to: {target_file_path}")
        return target_file_path
    except OSError as e:
        logger.error(
            f"Failed to copy backup file '{backup_filename}' to '{target_file_path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to restore config file '{target_filename}': {e}"
        ) from e


def restore_all_server_data(
    server_name: str, base_dir: str
) -> Dict[str, Optional[str]]:
    """
    Restores a server to its latest backed-up state (world and config files).
    Returns a dictionary of restored components and their original paths, or None if failed.

    Args:
        server_name: The name of the server to restore.
        base_dir: The base directory containing all server installations.

    Returns:
        A dictionary mapping component type (e.g., "world", "server.properties")
        to the path where it was restored in the server directory, or None if failed.

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        FileOperationError: If the server's backup directory cannot be accessed, or
                            if the BASE_DIR/BACKUP_DIR settings are missing.
        RestoreError: If any critical restore operation fails.
    """
    if not server_name:
        raise MissingArgumentError(
            "Server name cannot be empty for restore_all_server_data."
        )
    if not base_dir:
        raise MissingArgumentError(
            "Base directory cannot be empty for restore_all_server_data."
        )

    backup_base_dir = settings.get("BACKUP_DIR")
    if not backup_base_dir:
        raise FileOperationError("BACKUP_DIR setting is missing or empty.")

    server_backup_dir = os.path.join(backup_base_dir, server_name)
    server_install_dir = os.path.join(base_dir, server_name)

    logger.info(
        f"Starting restore_all process for server '{server_name}' from backups in '{server_backup_dir}' to '{server_install_dir}'."
    )

    if not os.path.isdir(server_backup_dir):
        logger.warning(
            f"No backup directory found for server '{server_name}' at '{server_backup_dir}'. Cannot restore."
        )
        return {}  # Return empty if no backup dir

    os.makedirs(server_install_dir, exist_ok=True)  # Ensure server install dir exists

    restore_results: Dict[str, Optional[str]] = {}
    failures = []

    # 1. Restore World (Latest .mcworld)
    try:
        logger.debug("Searching for latest world backup (.mcworld)...")
        world_backups = glob.glob(os.path.join(server_backup_dir, "*.mcworld"))
        if world_backups:
            latest_world_backup = max(world_backups, key=os.path.getmtime)
            logger.info(
                f"Found latest world backup: {os.path.basename(latest_world_backup)}"
            )
            # core_world.import_world returns the name of the imported world directory
            imported_world_name = core_world.import_world(
                server_name, latest_world_backup, base_dir
            )
            restore_results["world"] = os.path.join(
                server_install_dir, "worlds", imported_world_name
            )
        else:
            logger.info("No .mcworld backup files found. Skipping world restore.")
            restore_results["world"] = None
    except Exception as e:
        logger.error(
            f"Failed to restore world for server '{server_name}': {e}", exc_info=True
        )
        failures.append(f"World ({type(e).__name__})")
        restore_results["world"] = None

    # 2. Restore Config Files (Latest of each type)
    config_file_map = {  # maps original name to backup prefix
        "server.properties": "server_backup_",
        "allowlist.json": "allowlist_backup_",
        "permissions.json": "permissions_backup_",
    }

    for original_filename, backup_prefix in config_file_map.items():
        name_part, ext_part = os.path.splitext(original_filename)
        pattern = os.path.join(server_backup_dir, f"{backup_prefix}*{ext_part}")
        try:
            logger.debug(
                f"Searching for latest '{original_filename}' backup (pattern: '{os.path.basename(pattern)}')..."
            )
            config_backups = glob.glob(pattern)
            # Further filter to ensure the prefix matches correctly before the timestamp part
            # e.g. world_backup_....json should not match permissions_backup_....json
            # This regex is basic, might need refinement for complex prefixes
            valid_config_backups = [
                b_path
                for b_path in config_backups
                if re.match(
                    f"^{re.escape(name_part)}_backup_\\d{{8}}_\\d{{6}}{re.escape(ext_part)}$",
                    os.path.basename(b_path),
                )
            ]

            if valid_config_backups:
                latest_config_backup = max(valid_config_backups, key=os.path.getmtime)
                logger.info(
                    f"Found latest '{original_filename}' backup: {os.path.basename(latest_config_backup)}"
                )
                restored_path = restore_config_file_data(
                    latest_config_backup, server_install_dir
                )
                restore_results[original_filename] = restored_path
            else:
                logger.info(
                    f"No backup found for '{original_filename}'. Skipping restore for this file."
                )
                restore_results[original_filename] = None
        except Exception as e:
            logger.error(
                f"Failed to restore '{original_filename}' for server '{server_name}': {e}",
                exc_info=True,
            )
            failures.append(f"{original_filename} ({type(e).__name__})")
            restore_results[original_filename] = None

    if failures:
        error_summary = ", ".join(failures)
        logger.error(
            f"Restore_all_server_data for server '{server_name}' completed with errors. Failed components: {error_summary}"
        )
        # Raise a comprehensive error if any part failed
        raise RestoreError(
            f"Restore failed for server '{server_name}'. Failed components: {error_summary}"
        )

    logger.info(
        f"Restore_all_server_data process completed for server '{server_name}'."
    )
    return restore_results
