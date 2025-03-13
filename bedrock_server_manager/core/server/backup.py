# bedrock-server-manager/bedrock_server_manager/core/server/backup.py
import os
import glob
import shutil
import logging
from bedrock_server_manager.config import settings
from bedrock_server_manager.core.server import world
from bedrock_server_manager.core.error import (
    MissingArgumentError,
    FileOperationError,
    DirectoryError,
    InvalidInputError,
    BackupWorldError,
    RestoreError,
)
from bedrock_server_manager.utils import general
from bedrock_server_manager.core.server import server

logger = logging.getLogger("bedrock_server_manager")


def prune_old_backups(backup_dir, backup_keep, file_prefix="", file_extension=""):
    """Prunes old backups, keeping only the most recent ones.

    Args:
        backup_dir (str): The directory where backups are stored.
        backup_keep (int): How many backups to keep.
        file_prefix (str, optional):  Prefix of files to prune (e.g., "world_backup_").
        file_extension (str, optional): Extension of files to prune (e.g., "mcworld").

    Raises:
        MissingArgumentError: If backup_dir is empty.
        ValueError: If backup_keep is not a valid integer.
        DirectoryError: If backup_dir is not a directory.
        InvalidInputError: If no file_prefix and no file_extension are provided.
        FileOperationError: If file deletion fails.
    """

    if not backup_dir:
        raise MissingArgumentError("prune_old_backups: backup_dir is empty.")

    if not os.path.isdir(backup_dir):
        logger.debug(
            f"Backup directory does not exist: {backup_dir}.  Nothing to prune."
        )
        return  # Not an error if the directory doesn't exist

    logger.debug("Pruning old backups...")

    # Construct the glob pattern
    if file_prefix and file_extension:
        glob_pattern = os.path.join(backup_dir, f"{file_prefix}*.{file_extension}")
    elif file_prefix:
        glob_pattern = os.path.join(backup_dir, f"{file_prefix}*")
    elif file_extension:
        glob_pattern = os.path.join(backup_dir, f"*.{file_extension}")
    else:
        raise InvalidInputError("Must have either file prefix or file extension")

    # Prune backups
    try:
        backups = sorted(glob.glob(glob_pattern), key=os.path.getmtime, reverse=True)
        backups_to_keep = int(backup_keep)  # Could raise ValueError
        if len(backups) > backups_to_keep:
            logger.debug(f"Keeping the {backups_to_keep} most recent backups.")
            files_to_delete = backups[backups_to_keep:]
            for old_backup in files_to_delete:
                try:
                    logger.debug(f"Removing old backup: {old_backup}")
                    os.remove(old_backup)
                except OSError as e:
                    raise FileOperationError(
                        f"Failed to remove {old_backup}: {e}"
                    ) from e
    except ValueError:
        raise ValueError("backup_keep must be a valid integer.") from None


def backup_world(server_name, world_path, backup_dir):
    """Backs up a server's world.

    Args:
        server_name (str): The name of the server (for naming the backup).
        world_path (str): The path to the world directory.
        backup_dir (str): The directory to save the backup to.

    Raises:
        DirectoryError: If the world path is not a directory.
        # Other exceptions may be raised by world.export_world
    """
    if not os.path.isdir(world_path):
        raise DirectoryError(
            f"World directory '{world_path}' does not exist. Skipping world backup."
        )

    timestamp = general.get_timestamp()
    backup_file = os.path.join(
        backup_dir, f"{os.path.basename(world_path)}_backup_{timestamp}.mcworld"
    )

    logger.debug(f"Backing up world folder '{world_path}'...")
    world.export_world(world_path, backup_file)  # Let export_world raise exceptions


def backup_config_file(file_to_backup, backup_dir):
    """Backs up a specific configuration file.

    Args:
        file_to_backup (str): The path to the configuration file to back up.
        backup_dir (str): The directory to save the backup to.

    Raises:
        MissingArgumentError: If file_to_backup is empty.
        FileOperationError: If the file doesn't exist or copying fails.
    """
    if not file_to_backup:
        raise MissingArgumentError("backup_config_file: file_to_backup is empty.")
    if not os.path.exists(file_to_backup):
        raise FileOperationError(f"Configuration file '{file_to_backup}' not found!")

    file_name = os.path.basename(file_to_backup)
    timestamp = general.get_timestamp()
    destination = os.path.join(
        backup_dir,
        f"{os.path.splitext(file_name)[0]}_backup_{timestamp}.{file_name.split('.')[-1]}",
    )
    try:
        shutil.copy2(file_to_backup, destination)
        logger.debug(f"{file_name} backed up to {backup_dir}")
    except OSError as e:
        raise FileOperationError(
            f"Failed to copy '{file_to_backup}' to '{backup_dir}': {e}"
        ) from e


def backup_server(server_name, backup_type, base_dir, file_to_backup=None):
    """Backs up a server's world or a specific configuration file (core logic).

    Args:
        server_name (str): The name of the server.
        backup_type (str): "world" or "config".
        base_dir (str): The base directory for servers.
        file_to_backup (str, optional): The file to back up if backup_type is "config".

    Raises:
        MissingArgumentError: If required arguments are missing or invalid.
        InvalidInputError:  If backup_type is invalid.
        # Other exceptions may be raised by backup_world or backup_config_file
    """

    if not server_name:
        raise MissingArgumentError("backup_server: server_name is empty.")
    if not backup_type:
        raise MissingArgumentError("backup_server: backup_type is empty.")

    backup_dir = os.path.join(settings.BACKUP_DIR, server_name)
    os.makedirs(backup_dir, exist_ok=True)

    if backup_type == "world":
        try:
            world_name = server.get_world_name(server_name, base_dir)
            if world_name is None or not world_name:  # check for empty string
                raise BackupWorldError(
                    "Could not determine world name; backup may not function"
                )
            world_path = os.path.join(base_dir, server_name, "worlds", world_name)
            backup_world(server_name, world_path, backup_dir)
        except Exception as e:
            raise BackupWorldError(f"World backup failed: {e}") from e

    elif backup_type == "config":
        if not file_to_backup:
            raise MissingArgumentError(
                "backup_server: file_to_backup is empty when backup_type is config."
            )

        full_file_path = os.path.join(base_dir, server_name, file_to_backup)
        backup_config_file(full_file_path, backup_dir)  # Let it raise exceptions

    else:
        raise InvalidInputError(f"Invalid backup type: {backup_type}")


def backup_all(server_name, base_dir=None):
    """Backs up all files (world and configuration files) (core logic).

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory for servers. Defaults to settings.BASE_DIR.
    Raises:
        MissingArgumentError: If server name is empty.
        BackupWorldError: If any backup fails.
    """
    if base_dir is None:
        base_dir = settings.BASE_DIR

    if not server_name:
        raise MissingArgumentError("backup_all: server_name is empty.")

    try:
        backup_server(server_name, "world", base_dir, "")
    except Exception as e:  # Catch any exception
        raise BackupWorldError(f"World backup failed: {e}") from e

    config_files = ["allowlist.json", "permissions.json", "server.properties"]
    for config_file in config_files:
        try:
            backup_server(server_name, "config", base_dir, file_to_backup=config_file)
        except Exception as e:
            raise BackupWorldError(
                f"Config file backup failed ({config_file}): {e}"
            ) from e


def restore_config_file(backup_file, server_dir):
    """Restores a specific configuration file.

    Args:
        backup_file (str): The path to the backed-up configuration file.
        server_dir (str): The server's directory.

    Raises:
        MissingArgumentError: If backup_file or server_dir is empty.
        FileOperationError: If the backup file doesn't exist or restoring fails.
    """
    if not backup_file:
        raise MissingArgumentError("restore_config_file: backup_file is empty.")
    if not server_dir:
        raise MissingArgumentError("restore_config_file: server_dir is empty.")
    if not os.path.exists(backup_file):
        raise FileOperationError(f"Backup file '{backup_file}' not found!")

    base_name = os.path.basename(backup_file).split("_backup_")[0]
    file_extension = os.path.splitext(backup_file)[1]
    if file_extension == ".mcworld":
        file_extension = "mcworld"
    else:
        file_extension = file_extension[1:]  # Remove leading .

    target_file = os.path.join(server_dir, f"{base_name}.{file_extension}")

    logger.debug(f"Restoring configuration file: {os.path.basename(backup_file)}")
    try:
        shutil.copy2(backup_file, target_file)
        logger.info(f"Configuration file restored to {target_file}")
    except OSError as e:
        raise FileOperationError(f"Failed to restore configuration file: {e}") from e


def restore_server(server_name, backup_file, restore_type, base_dir):
    """Restores a server from a backup file (core logic).

    Args:
        server_name (str): The name of the server.
        backup_file (str): Path to the backup file.
        restore_type (str): "world" or "config".
        base_dir (str): The base directory for servers.

    Raises:
        MissingArgumentError: If server_name, backup_file, or restore_type is empty.
        InvalidInputError: If restore_type is invalid.
        FileOperationError: If backup file does not exist.
        # Other exceptions may be raised by world.import_world or restore_config_file

    """
    server_dir = os.path.join(base_dir, server_name)

    if not server_name:
        raise MissingArgumentError("restore_server: server_name is empty.")
    if not backup_file:
        raise MissingArgumentError("restore_server: backup_file is empty.")
    if not restore_type:
        raise MissingArgumentError("restore_server: restore_type is empty.")

    if not os.path.exists(backup_file):
        raise FileOperationError(f"Backup file '{backup_file}' not found!")

    if restore_type == "world":
        world.import_world(server_name, backup_file, base_dir)

    elif restore_type == "config":
        restore_config_file(backup_file, server_dir)
    else:
        raise InvalidInputError(
            f"Invalid restore type in restore_server: {restore_type}"
        )


def restore_all(server_name, base_dir):
    """Restores all newest files (world and configuration files) (core logic).

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.

    Raises:
        MissingArgumentError: If server_name is empty.
        RestoreError: If any restore operations fail
        FileOperationError: If backup directory does not exist.
    """
    backup_dir = os.path.join(settings.BACKUP_DIR, server_name)

    if not server_name:
        raise MissingArgumentError("restore_all: server_name is empty.")

    if not os.path.isdir(backup_dir):
        logger.debug(f"No backups found for {server_name}.")
        return  # Not an error if no backups exist

    # Find and restore the latest world backup
    world_backups = glob.glob(os.path.join(backup_dir, "*.mcworld"))
    if world_backups:
        latest_world = max(world_backups, key=os.path.getmtime)
        try:
            restore_server(server_name, latest_world, "world", base_dir)
        except Exception as e:
            raise RestoreError(f"Failed to restore world: {e}") from e
    else:
        logger.warning("No world backups found.")

    # Find and restore latest server.properties backup
    properties_backups = glob.glob(
        os.path.join(backup_dir, "server_backup_*.properties")
    )
    if properties_backups:
        latest_properties = max(properties_backups, key=os.path.getmtime)
        try:
            restore_server(server_name, latest_properties, "config", base_dir)
        except Exception as e:
            raise RestoreError(f"Failed to restore server.properties: {e}") from e
    else:
        logger.warning("No server.properties backup found to restore.")

    # Restore latest JSON backups
    json_backups = glob.glob(os.path.join(backup_dir, "*_backup_*.json"))
    restored_json_types = set()
    for config_file in sorted(json_backups, key=os.path.getmtime, reverse=True):
        filename = os.path.basename(config_file)
        config_type = filename.split("_backup_")[0]

        if config_type not in restored_json_types:
            try:
                restore_server(server_name, config_file, "config", base_dir)
            except Exception as e:
                raise RestoreError(
                    f"Failed to restore config file {config_file}: {e}"
                ) from e
            restored_json_types.add(config_type)
