# bedrock-server-manager/bedrock_server_manager/api/backup.py
import os
import glob
import logging
from bedrock_server_manager.core.server import backup
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.api.world import get_world_name
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.core.error import InvalidServerNameError
from bedrock_server_manager.api.server import start_server, stop_server

logger = logging.getLogger("bedrock_server_manager")


def list_backup_files(server_name, backup_type, base_dir=None):
    """Lists available backups for a server.

    Args:
        server_name (str): The name of the server.
        backup_type (str): "world" or "config".
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success", "backups": [...]} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    backup_dir = os.path.join(settings.get("BACKUP_DIR"), server_name)
    logger.info(f"Listing backups for server: {server_name}, type: {backup_type}")

    if not os.path.isdir(backup_dir):
        logger.warning(f"Backup directory does not exist: {backup_dir}")
        return {"status": "error", "message": f"No backups found for {server_name}."}

    if backup_type == "world":
        backup_files = glob.glob(os.path.join(backup_dir, "*.mcworld"))
        logger.debug(f"Found world backups: {backup_files}")
    elif backup_type == "config":
        backup_files = glob.glob(os.path.join(backup_dir, "*_backup_*.json"))
        backup_files += glob.glob(
            os.path.join(backup_dir, "server_backup_*.properties")
        )
        logger.debug(f"Found config backups: {backup_files}")
    else:
        logger.error(f"Invalid backup type: {backup_type}")
        return {"status": "error", "message": f"Invalid backup type: {backup_type}"}

    return {"status": "success", "backups": backup_files}


def backup_world(server_name, base_dir=None, stop_start_server=True):
    """Backs up a server's world.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.
        stop_start_server (bool, optional): Whether to stop/start the server.
            Defaults to True.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    server_dir = os.path.join(base_dir, server_name)
    backup_dir = os.path.join(settings.get("BACKUP_DIR"), server_name)
    os.makedirs(backup_dir, exist_ok=True)  # Ensure backup dir exists
    logger.info(f"Backing up world for server: {server_name}")

    if not server_name:
        raise InvalidServerNameError("backup_world: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}
    was_running = False
    if stop_start_server:
        was_running = system_base.is_server_running(server_name, base_dir)
        if was_running:
            logger.debug(f"Stopping server {server_name} for world backup")
            stop_result = stop_server(server_name, base_dir)
            if stop_result["status"] == "error":
                return stop_result

    try:
        world_name_result = get_world_name(server_name, base_dir)
        if world_name_result["status"] == "error":
            return world_name_result
        world_name = world_name_result["world_name"]
        world_path = os.path.join(server_dir, "worlds", world_name)
        if not os.path.exists(world_path):  # Changed to exists
            logger.error(f"World path does not exist: {world_path}")
            return {
                "status": "error",
                "message": f"World path does not exist: {world_path}",
            }
        backup.backup_world(server_name, world_path, backup_dir)
        logger.debug(f"World backed up for server: {server_name}")
    except Exception as e:
        logger.exception(f"World backup failed for {server_name}: {e}")
        return {"status": "error", "message": f"World backup failed: {e}"}
    if stop_start_server and was_running:
        logger.debug(f"Restarting server {server_name} after world backup")
        start_result = start_server(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result

    return {"status": "success"}  # Return success here


def backup_config_file(
    server_name, file_to_backup, base_dir=None, stop_start_server=True
):
    """Backs up a specific configuration file.

    Args:
        server_name (str): The name of the server.
        file_to_backup (str): The file to back up (relative to server dir).
        base_dir (str, optional): The base directory. Defaults to None.
        stop_start_server (bool, optional): Whether to stop/start the server.
            Defaults to True.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    server_dir = os.path.join(base_dir, server_name)
    backup_dir = os.path.join(settings.get("BACKUP_DIR"), server_name)
    os.makedirs(backup_dir, exist_ok=True)
    logger.info(f"Backing up config file for {server_name}: {file_to_backup}")
    if not server_name:
        raise InvalidServerNameError("backup_config_file: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}
    if not file_to_backup:
        logger.error(f"No file specified for config backup on server {server_name}.")
        return {"status": "error", "message": "File to backup cannot be empty."}

    was_running = False
    if stop_start_server:
        was_running = system_base.is_server_running(server_name, base_dir)
        if was_running:
            logger.debug(f"Stopping server {server_name} for config file backup")
            stop_result = stop_server(server_name, base_dir)
            if stop_result["status"] == "error":
                return stop_result

    full_file_path = os.path.join(server_dir, file_to_backup)
    if not os.path.exists(full_file_path):
        logger.error(f"Config file does not exist: {full_file_path}")
        return {
            "status": "error",
            "message": f"Config file does not exist: {full_file_path}",
        }
    try:
        backup.backup_config_file(full_file_path, backup_dir)
        logger.debug(f"Config file backed up for {server_name}: {file_to_backup}")

    except Exception as e:
        logger.exception(f"Config file backup failed for {server_name}: {e}")
        return {"status": "error", "message": f"Config file backup failed: {e}"}
    if stop_start_server and was_running:
        logger.debug(f"Restarting server {server_name} after config file backup")
        start_result = start_server(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result
    return {"status": "success"}


def backup_all(server_name, base_dir=None, stop_start_server=True):
    """
    Backs up all server files
    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.
        stop_start_server(bool, optional): wether to stop and restart server

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Performing full backup for server: {server_name}")
    if not server_name:
        raise InvalidServerNameError("backup_all: server_name is empty.")

    was_running = False
    if stop_start_server:
        was_running = system_base.is_server_running(server_name, base_dir)
        if was_running:
            logger.debug(f"Stopping server {server_name} for full backup")
            stop_result = stop_server(server_name, base_dir)
            if stop_result["status"] == "error":
                return stop_result
    try:
        backup.backup_all(server_name, base_dir)
        logger.info("All files backed up successfully.")
    except Exception as e:
        logger.exception(f"Error during full backup for {server_name}: {e}")
        return {"status": "error", "message": f"Error during full backup: {e}"}
    if stop_start_server and was_running:
        logger.debug(f"Restarting server {server_name} after full backup")
        start_result = start_server(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result
    return {"status": "success"}


def restore_world(server_name, backup_file, base_dir=None, stop_start_server=True):
    """Restores a server's world from a backup file.

    Args:
        server_name (str): The name of the server.
        backup_file (str): Path to the backup file.
        base_dir (str, optional): The base directory. Defaults to None.
        stop_start_server (bool, optional): Whether to stop/start the server.
            Defaults to True.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Restoring world for {server_name} from {backup_file}")
    if not server_name:
        raise InvalidServerNameError("restore_world: server_name is empty.")
    if not backup_file:
        logger.error(
            f"No backup file specified for world restore on server {server_name}."
        )
        return {"status": "error", "message": "Backup file cannot be empty."}
    if not os.path.exists(backup_file):
        logger.error(f"Backup file not found: {backup_file}")
        return {"status": "error", "message": f"Backup file '{backup_file}' not found."}

    was_running = False
    if stop_start_server:
        was_running = system_base.is_server_running(server_name, base_dir)
        if was_running:
            logger.debug(f"Stopping server {server_name} for world restore")
            stop_result = stop_server(server_name, base_dir)
            if stop_result["status"] == "error":
                return stop_result
    try:
        backup.restore_server(server_name, backup_file, "world", base_dir)
        logger.debug(f"World restored for {server_name} from {backup_file}")
    except Exception as e:
        logger.exception(f"Error restoring world for {server_name}: {e}")
        return {"status": "error", "message": f"Error restoring world: {e}"}
    if stop_start_server and was_running:
        logger.debug(f"Restarting server {server_name} after world restore")
        start_result = start_server(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result
    return {"status": "success"}


def restore_config_file(
    server_name, backup_file, base_dir=None, stop_start_server=True
):
    """Restores a server's configuration file from a backup file.

    Args:
        server_name (str): The name of the server.
        backup_file (str): Path to the backup file.
        base_dir (str, optional): The base directory. Defaults to None.
        stop_start_server (bool, optional): Whether to stop/start the server.
            Defaults to True.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Restoring config file for {server_name} from {backup_file}")
    if not server_name:
        raise InvalidServerNameError("restore_config_file: server_name is empty.")
    if not backup_file:
        logger.error(
            f"No backup file specified for config restore on server {server_name}"
        )
        return {"status": "error", "message": "Backup file cannot be empty."}
    if not os.path.exists(backup_file):
        logger.error(f"Backup file not found: {backup_file}")
        return {"status": "error", "message": f"Backup file '{backup_file}' not found."}

    was_running = False
    if stop_start_server:
        was_running = system_base.is_server_running(server_name, base_dir)
        if was_running:
            logger.debug(f"Stopping server {server_name} for config restore")
            stop_result = stop_server(server_name, base_dir)
            if stop_result["status"] == "error":
                return stop_result

    try:
        backup.restore_server(server_name, backup_file, "config", base_dir)
    except Exception as e:
        logger.exception(f"Error restoring config file for {server_name}: {e}")
        return {"status": "error", "message": f"Error restoring config file: {e}"}

    logger.debug(f"Config file restored for {server_name} from {backup_file}")

    if stop_start_server and was_running:
        logger.debug(f"Restarting server {server_name} after config file restore")
        start_result = start_server(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result
    return {"status": "success"}


def restore_all(server_name, base_dir=None, stop_start_server=True):
    """
    Restores the enitre server
    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.
        stop_start_server (bool, optional): Whether to stop/start the server.
            Defaults to True.
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Restoring all files for server: {server_name}")
    if not server_name:
        raise InvalidServerNameError("restore_all: server_name is empty.")
    was_running = False
    if stop_start_server:
        was_running = system_base.is_server_running(server_name, base_dir)
        if was_running:
            logger.debug(f"Stopping server {server_name} before restoring all files")
            stop_result = stop_server(server_name, base_dir)
            if stop_result["status"] == "error":
                return stop_result
    try:
        backup.restore_all(server_name, base_dir)
        logger.info(f"All files restored for {server_name}")
    except Exception as e:
        logger.exception(f"Error restoring all files for {server_name}: {e}")
        return {"status": "error", "message": f"Error restoring all files: {e}"}
    if stop_start_server and was_running:
        logger.debug(f"Restarting server {server_name} after restoring all files")
        start_result = start_server(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result
    return {"status": "success"}


def prune_old_backups(server_name, file_name=None, backup_keep=None, base_dir=None):
    """Prunes old backups, keeping only the most recent ones.

    Args:
        server_name (str): The name of the server.
        file_name (str, optional): Specific file name to prune (for config files).
        backup_keep (int, optional): How many backups to keep, defaults to config.
        base_dir (str, optional): base directory

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    backup_dir = os.path.join(settings.get("BACKUP_DIR"), server_name)
    logger.info(f"Pruning old backups for server: {server_name}")
    if not server_name:
        raise InvalidServerNameError("prune_old_backups: server_name is empty")
        # return {"status": "error", "message": "Server name cannot be empty."}

    if backup_keep is None:
        backup_keep = settings.get("BACKUP_KEEP")  # Get from config
        logger.debug(f"Using default backup keep value: {backup_keep}")
        try:
            backup_keep = int(backup_keep)
        except ValueError:
            logger.error(
                "Invalid value for BACKUP_KEEP in config file, must be an integer."
            )
            return {
                "status": "error",
                "message": "Invalid value for BACKUP_KEEP in config file, must be an integer.",
            }

    # Prune world backups (*.mcworld)
    world_name_result = get_world_name(server_name, base_dir)
    try:
        if world_name_result["status"] == "error":
            #  If we can't get the world name, still try to prune with just the extension
            logger.debug(
                f"Pruning world backups using only extension for: {server_name}"
            )
            backup.prune_old_backups(backup_dir, backup_keep, file_extension="mcworld")
        else:
            level_name = world_name_result["world_name"]
            logger.debug(
                f"Pruning world backups using prefix and extension for: {server_name}"
            )
            backup.prune_old_backups(
                backup_dir,
                backup_keep,
                file_prefix=f"{level_name}_backup_",
                file_extension="mcworld",
            )
    except Exception as e:
        logger.exception(f"Error pruning world backups for {server_name}: {e}")
        return {"status": "error", "message": f"Error pruning world backups: {e}"}

    # Prune config file backups (if file_name is provided)
    if file_name:
        logger.debug(
            f"Pruning config file backups for {server_name} with filename: {file_name}"
        )
        try:
            backup.prune_old_backups(
                backup_dir,
                backup_keep,
                file_prefix=f"{os.path.splitext(file_name)[0]}_backup_",
                file_extension=file_name.split(".")[-1],
            )
        except Exception as e:
            logger.exception(f"Error pruning config backups for {server_name}: {e}")
            return {"status": "error", "message": f"Error pruning config backups: {e}"}

    return {"status": "success"}
