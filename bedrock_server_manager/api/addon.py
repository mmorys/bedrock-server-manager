# bedrock-server-manager/bedrock_server_manager/api/addon.py
import os
import logging
from bedrock_server_manager.core.server import addon
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.core.error import InvalidServerNameError
from bedrock_server_manager.api.server import start_server, stop_server


logger = logging.getLogger("bedrock_server_manager")


def import_addon(server_name, addon_file, base_dir=None, stop_start_server=True):
    """Installs an addon to the server.

    Args:
        server_name (str): The name of the server.
        addon_file (str): The path to the addon file.
        base_dir (str, optional): The base directory. Defaults to None.
        stop_start_server (bool, optional): Whether to stop/start the server.
            Defaults to True.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Installing addon {addon_file} for server: {server_name}")
    if not server_name:
        raise InvalidServerNameError("import_addon: server_name is empty.")
    if not addon_file:
        logger.error("Addon file cannot be empty.")
        return {"status": "error", "message": "Addon file cannot be empty."}
    if not os.path.exists(addon_file):
        logger.error(f"Addon file does not exist: {addon_file}")
        return {
            "status": "error",
            "message": f"Addon file does not exist: {addon_file}",
        }

    was_running = False
    if stop_start_server:
        was_running = system_base.is_server_running(server_name, base_dir)
        if was_running:
            logger.debug(f"Stopping server {server_name} before addon installation")
            stop_result = stop_server(server_name, base_dir)
            if stop_result["status"] == "error":
                return stop_result

    try:
        addon.process_addon(addon_file, server_name, base_dir)
        logger.info(f"Addon {addon_file} installed successfully for {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error installing addon {addon_file} for {server_name}: {e}")
        return {"status": "error", "message": f"Error installing addon: {e}"}
    finally:  # Always restart if needed, even if process_addon fails
        if stop_start_server and was_running:
            logger.debug(f"Restarting server {server_name} after addon installation")
            start_result = start_server(server_name, base_dir)
            if start_result["status"] == "error":
                return start_result
