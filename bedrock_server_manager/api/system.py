# bedrock-server-manager/bedrock_server_manager/api/system.py
import logging
import platform
from bedrock_server_manager.error import InvalidServerNameError
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
)
from bedrock_server_manager.utils.general import get_base_dir


logger = logging.getLogger("bedrock_server_manager")


def get_bedrock_process_info(server_name, base_dir=None):
    """Retrieves process information for the Bedrock server.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success", "process_info": {...}}
            or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.debug(f"Getting process info for server: {server_name}")
    if not server_name:
        raise InvalidServerNameError("get_bedrock_process_info: server_name is empty")
        # return {"status": "error", "message": "Server name cannot be empty."}

    try:
        process_info = system_base._get_bedrock_process_info(server_name, base_dir)
        if not process_info:
            logger.warning(f"Server process information not found for: {server_name}")
            return {
                "status": "error",
                "message": "Server process information not found.",
            }
        logger.debug(f"Retrieved process info: {process_info}")
        return {"status": "success", "process_info": process_info}
    except Exception as e:
        logger.exception(f"Error getting process info for {server_name}: {e}")
        return {"status": "error", "message": f"Error getting process info: {e}"}


def create_systemd_service(
    server_name, base_dir=None, autoupdate=False, autostart=False
):
    """Creates a systemd service on Linux.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.
        autoupdate (bool, optional): Whether to enable auto-update. Defaults to False.
        autostart(bool, optional): enable autostart

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    if platform.system() != "Linux":
        return {"status": "success"}  # Not applicable

    base_dir = get_base_dir(base_dir)
    logger.info(f"Creating systemd service for server: {server_name}")

    if not server_name:
        raise InvalidServerNameError("create_systemd_service: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}

    try:
        system_linux._create_systemd_service(server_name, base_dir, autoupdate)
        if autostart:
            system_linux._enable_systemd_service(server_name)
            logger.info(f"Enabled autostart for systemd service: {server_name}")
        else:
            system_linux._disable_systemd_service(server_name)
            logger.info(f"Disabled autostart for systemd service: {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Failed to create systemd service: {e}")
        return {"status": "error", "message": f"Failed to create systemd service: {e}"}


def set_windows_autoupdate(server_name, autoupdate_value, base_dir=None):
    """Sets the autoupdate configuration option on Windows.

    Args:
        server_name (str): The name of the server.
        autoupdate_value (str): "true" or "false".
        base_dir (str): The base directory for servers.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    if platform.system() != "Windows":
        return {"status": "success"}  # Not applicable
    logger.info(f"Setting autoupdate for {server_name} to {autoupdate_value}")
    if not server_name:
        raise InvalidServerNameError("set_windows_autoupdate: server_name is empty")
        # return {"status": "error", "message": "Server name cannot be empty."}

    try:
        server_base.manage_server_config(
            server_name, "autoupdate", "write", autoupdate_value, config_dir=base_dir
        )
        logger.debug(
            f"Successfully set autoupdate to {autoupdate_value} for {server_name}"
        )
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Failed to update autoupdate config: {e}")
        return {
            "status": "error",
            "message": f"Failed to update autoupdate config: {e}",
        }


def enable_server_service(server_name, base_dir=None):
    if platform.system() != "Linux":
        return {"status": "success"}
    base_dir = get_base_dir(base_dir)
    logger.info(f"Enabling systemd service for {server_name}")
    try:
        system_linux._enable_systemd_service(server_name)
        logger.debug(f"Enabled systemd service for {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Failed to enable systemd service: {e}")
        return {"status": "error", "message": f"Failed to enable service: {e}"}


def disable_server_service(server_name, base_dir=None):
    if platform.system() != "Linux":
        return {"status": "success"}
    base_dir = get_base_dir(base_dir)
    logger.info(f"Disabling systemd service for {server_name}")
    try:
        system_linux._disable_systemd_service(server_name)
        logger.debug(f"Disabled systemd service for {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Failed to disable systemd service: {e}")
        return {"status": "error", "message": f"Failed to disable service: {e}"}
