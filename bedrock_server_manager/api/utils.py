# bedrock-server-manager/bedrock_server_manager/api/utils.py
import os
import re
import glob
import logging
import platform
import subprocess
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.core.error import InvalidServerNameError
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.core.system import base as system_base


logger = logging.getLogger("bedrock_server_manager")


def validate_server_exist(server_name, base_dir=None):
    """Validates the existence of a server.

    Args:
        server_name (str): The name of the server to validate.
        base_dir (str, optional): The base directory for servers. Defaults to None.

    Returns:
        dict: {"status": "success"} if valid, {"status": "error", "message": ...} if invalid.
    """
    base_dir = get_base_dir(base_dir)
    logger.debug(f"Validating server name: {server_name}")
    if not server_name:
        logger.error("Server name cannot be empty in validate_server_exist")
        return {"status": "error", "message": "Server name cannot be empty."}

    try:
        if server_base.validate_server(server_name, base_dir):
            logger.debug(f"Server {server_name} is valid.")
            return {"status": "success"}
        else:
            #  Validate_server might already raise an exception, making this redundant
            logger.warning(f"Server {server_name} not found.")
            return {"status": "error", "message": f"Server {server_name} not found."}
    except InvalidServerNameError as e:  # Catch specific exception
        logger.error(f"Invalid server name: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:  # Catch any other unexpected exceptions.
        logger.exception(f"An unexpected error occurred: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def validate_server_name_format(server_name):
    """Validates the format of a server name (alphanumeric, hyphens, underscores)."""
    logger.debug(f"Validating server name format: {server_name}")
    if not re.match(r"^[a-zA-Z0-9_-]+$", server_name):
        logger.warning(f"Invalid server name format: {server_name}")
        return {
            "status": "error",
            "message": "Invalid server folder name. Only alphanumeric characters, hyphens, and underscores are allowed.",
        }
    return {"status": "success"}


def get_all_servers_status(base_dir=None, config_dir=None):
    """Gets the status and version of all servers.

    Args:
        base_dir (str, optional): The base directory. Defaults to None.
        config_dir (str, optional): The configuration directory. Defaults to None.

    Returns:
        dict: {"status": "success", "servers": [...]} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    if config_dir is None:
        config_dir = settings._config_dir
    logger.debug(f"Getting status for all servers in: {base_dir}")

    if not os.path.isdir(base_dir):
        logger.error(f"{base_dir} does not exist or is not a directory.")
        return {
            "status": "error",
            "message": f"{base_dir} does not exist or is not a directory.",
        }

    servers_data = []
    for server_path in glob.glob(os.path.join(base_dir, "*")):
        if os.path.isdir(server_path):
            server_name = os.path.basename(server_path)
            try:
                status = server_base.get_server_status_from_config(
                    server_name, config_dir
                )
                version = server_base.get_installed_version(server_name, config_dir)
                servers_data.append(
                    {"name": server_name, "status": status, "version": version}
                )
            except Exception as e:
                logger.exception(f"Error getting data for {server_name}: {e}")
                return {
                    "status": "error",
                    "message": f"Error getting data for {server_name}: {e}",
                }
    logger.debug(f"Server statuses: {servers_data}")
    return {"status": "success", "servers": servers_data}


def update_server_statuses(base_dir=None, config_dir=None):
    """Updates the status in config.json for all servers, based on runtime checks.

    Iterates through all servers in the base directory.  If a server is
    NOT running, but its config file says it IS running (or starting, etc.),
    the config file is updated to reflect the STOPPED status.

    Args:
        base_dir (str, optional): The base directory for servers. Defaults to None.
        config_dir (str, optional): config directory

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    if config_dir is None:
        config_dir = settings._config_dir
    logger.debug("Updating server statuses in config files.")

    if not os.path.isdir(base_dir):
        logger.error(f"Base directory does not exist: {base_dir}")
        return {
            "status": "error",
            "message": f"Base directory does not exist: {base_dir}",
        }

    try:
        for server_folder in glob.glob(os.path.join(base_dir, "*/")):
            server_name = os.path.basename(os.path.normpath(server_folder))
            logger.debug(f"Checking status for server: {server_name}")

            is_running = system_base.is_server_running(server_name, base_dir)
            current_status = server_base.get_server_status_from_config(
                server_name, config_dir
            )
            logger.debug(
                f"Server {server_name}: Running={is_running}, Config Status={current_status}"
            )
            #  Statuses that indicate the server *should* be running
            running_statuses = ("RUNNING", "STARTING", "RESTARTING")

            if not is_running and current_status in running_statuses:
                logger.debug(
                    f"Updating status for {server_name}: Config says {current_status}, but server is not running.  Setting to STOPPED."
                )
                server_base.manage_server_config(
                    server_name, "status", "write", "STOPPED", config_dir
                )
            # Add this for consistency
            elif is_running and current_status == "STOPPED":
                logger.debug(
                    f"Updating status for {server_name}: Config says {current_status}, but server is running.  Setting to RUNNING."
                )
                server_base.manage_server_config(
                    server_name, "status", "write", "RUNNING", config_dir
                )

        logger.debug("Server status updates complete.")
        return {"status": "success"}

    except Exception as e:  # Catch any unexpected errors during the process
        logger.exception(f"Error updating server statuses: {e}")
        return {"status": "error", "message": f"Error updating server statuses: {e}"}


def list_content_files(content_dir, extensions):
    """Lists files in a directory with specified extensions.

    Args:
        content_dir (str): The directory to search.
        extensions (list): A list of file extensions (e.g., ["mcworld", "mcaddon"]).

    Returns:
        dict: {"status": "success", "files": [...]} or {"status": "error", "message": ...}
    """
    logger.debug(
        f"Listing content files in directory: {content_dir} with extensions: {extensions}"
    )
    if not os.path.isdir(content_dir):
        logger.error(f"Content directory not found: {content_dir}.")
        return {
            "status": "error",
            "message": f"Content directory not found: {content_dir}.",
        }

    files = []
    for ext in extensions:
        logger.debug(f"Searching for files with extension: .{ext}")
        found_files = glob.glob(os.path.join(content_dir, f"*.{ext}"))
        files.extend(found_files)
        logger.debug(f"Found files with extension .{ext}: {found_files}")

    if not files:
        logger.warning(f"No files found with extensions: {extensions} in {content_dir}")
        return {
            "status": "error",
            "message": f"No files found with extensions: {extensions}",
        }

    logger.debug(f"Total files found: {files}")
    return {"status": "success", "files": files}


def attach_to_screen_session(server_name, base_dir=None):
    """Attaches to the screen session for the Bedrock server (Linux only).

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Attaching to screen session for server: {server_name}")
    if not server_name:
        raise InvalidServerNameError("attach_to_screen_session: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}

    if platform.system() != "Linux":
        logger.warning("Attaching to screen session is only supported on Linux.")
        return {"status": "success"}  # Not applicable

    if not system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is not running.")
        return {"status": "error", "message": f"{server_name} is not running."}

    try:
        subprocess.run(["screen", "-r", f"bedrock-{server_name}"], check=True)
        logger.debug(f"Attached to screen session for: {server_name}")
        return {"status": "success"}
    except subprocess.CalledProcessError:
        # This likely means the screen session doesn't exist.
        logger.warning(f"Failed to attach to screen session for: {server_name}")
        return {
            "status": "error",
            "message": f"Failed to attach to screen session for: {server_name}",
        }
    except FileNotFoundError:
        logger.error("screen command not found. Is screen installed?")
        return {
            "status": "error",
            "message": "screen command not found. Is screen installed?",
        }
    except Exception as e:
        logger.exception(f"An unexpected error occurred attaching to screen: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
