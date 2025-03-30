# bedrock-server-manager/bedrock_server_manager/api/world.py
import os
import logging
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.core.error import InvalidServerNameError
from bedrock_server_manager.api.server import start_server, stop_server
from bedrock_server_manager.utils.general import get_base_dir, get_timestamp
from bedrock_server_manager.core.server import (
    server as server_base,
    world,
)


logger = logging.getLogger("bedrock_server_manager")


def get_world_name(server_name, base_dir=None):
    """Retrieves the world name from server.properties.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success", "world_name": ...} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.debug(f"get_world_name: Getting world name for server: {server_name}")
    try:
        world_name = server_base.get_world_name(server_name, base_dir)
        if world_name is None or not world_name:  # Check for None or empty
            logger.error(
                f"Failed to get world name from server.properties for {server_name}"
            )
            return {
                "status": "error",
                "message": "Failed to get world name from server.properties.",
            }
        logger.debug(f"World name for {server_name}: {world_name}")
        return {"status": "success", "world_name": world_name}
    except Exception as e:
        logger.exception(f"Error getting world name for {server_name}: {e}")
        return {"status": "error", "message": f"Error getting world name: {e}"}


def export_world(server_name, base_dir=None, export_dir=None):
    """Exports a world from server.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.
        base_dir (str, optional): The base directory. Defaults to BACKUP_DIR.

    Returns:
        dict: {"status": "success", "export_file": ...} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Exporting world for server: {server_name}")
    if not server_name:
        raise InvalidServerNameError("export_world: server_name is empty.")

    if not export_dir:
        export_dir = settings.get("BACKUP_DIR")

    world_name_result = get_world_name(server_name, base_dir)
    if world_name_result["status"] == "error":
        return world_name_result  # Propagate the error
    world_folder = world_name_result["world_name"]

    world_path = os.path.join(base_dir, server_name, "worlds", world_folder)
    if not os.path.isdir(world_path):
        logger.error(
            f"World directory '{world_folder}' does not exist for {server_name}"
        )
        return {
            "status": "error",
            "message": f"World directory '{world_folder}' does not exist.",
        }

    timestamp = get_timestamp()

    export_file = os.path.join(export_dir, f"{world_folder}_{timestamp}.mcworld")
    logger.debug(f"Exporting world to: {export_file}")

    try:
        world.export_world(world_path, export_file)
        logger.info(f"World backup created: {export_file}")
        return {"status": "success", "export_file": export_file}
    except Exception as e:
        logger.exception(f"Error exporting world: {e}")
        return {"status": "error", "message": f"Error exporting world: {e}"}


def import_world(server_name, selected_file, base_dir=None, stop_start_server=True):
    """Imports a world to the server.

    Args:
        server_name (str): The name of the server.
        selected_file (str): Path to the .mcworld file.
        base_dir (str, optional): The base directory. Defaults to None.
        stop_start_server (bool, optional): Whether to stop/start the server.
            Defaults to True.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    if not server_name:
        raise InvalidServerNameError("extract_world: server_name is empty.")
    logger.info(f"Extracting world for server: {server_name}, file: {selected_file}")

    server_dir = os.path.join(base_dir, server_name)
    world_name_result = get_world_name(server_name, base_dir)
    if world_name_result["status"] == "error":
        return world_name_result  # Propagate the error

    world_name = world_name_result["world_name"]
    extract_dir = os.path.join(server_dir, "worlds", world_name)

    was_running = False
    if stop_start_server:
        was_running = system_base.is_server_running(server_name, base_dir)
        if was_running:
            logger.debug(f"Stopping server {server_name} before world extraction")
            # stop the server
            stop_result = stop_server(server_name, base_dir)
            if stop_result["status"] == "error":
                return stop_result

    try:
        world.extract_world(selected_file, extract_dir)
        logger.debug(f"Extracted world to: {extract_dir}")
    except Exception as e:
        logger.exception(f"Error extracting world: {e}")
        return {"status": "error", "message": f"Error extracting world: {e}"}

    if stop_start_server and was_running:
        logger.debug(f"Restarting server {server_name} after world extraction")
        # Start the server if it was running
        start_result = start_server(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result

    logger.info(f"Installed world to {extract_dir}")  # log success
    return {"status": "success"}
