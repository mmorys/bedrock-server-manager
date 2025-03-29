# bedrock-server-manager/bedrock_server_manager/handlers.py
import os
import glob
import logging
import re
import subprocess
import getpass
import platform
import time
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from bedrock_server_manager.web.app import run_web_server
from bedrock_server_manager.core import SCRIPT_DIR
from bedrock_server_manager.config.settings import settings, EXPATH
from bedrock_server_manager.core.player import player as player_base
from bedrock_server_manager.core.download import downloader
from bedrock_server_manager.core.error import (
    InvalidServerNameError,
    FileOperationError,
    PlayerDataError,
    DownloadError,
    InstallUpdateError,
    CommandNotFoundError,
    InvalidCronJobError,
    MissingArgumentError,
    ServerNotRunningError,
    SendCommandError,
    CommandNotFoundError,
)
from bedrock_server_manager.core.server import (
    server as server_base,
    world,
    backup,
    addon,
)
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
    windows as system_windows,
)
from bedrock_server_manager.utils.general import get_base_dir, get_timestamp


logger = logging.getLogger("bedrock_server_manager")


def validate_server_name_handler(server_name, base_dir=None):
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
        logger.error("Server name cannot be empty in validate_server_name_handler")
        return {"status": "error", "message": "Server name cannot be empty."}

    try:
        if server_base.validate_server(server_name, base_dir):
            logger.debug(f"Server {server_name} is valid.")
            return {"status": "success"}
        else:
            #  validate_server might already raise an exception, making this redundant
            logger.warning(f"Server {server_name} not found.")
            return {"status": "error", "message": f"Server {server_name} not found."}
    except InvalidServerNameError as e:  # Catch specific exception
        logger.error(f"Invalid server name: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:  # Catch any other unexpected exceptions.
        logger.exception(f"An unexpected error occurred: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def get_all_servers_status_handler(base_dir=None, config_dir=None):
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


def update_server_statuses_handler(base_dir=None, config_dir=None):
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


def configure_allowlist_handler(server_name, base_dir=None, new_players_data=None):
    """Configures the allowlist for a server.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.
        new_players_data (list, optional): A list of dictionaries representing
            new players to add.  Each dictionary should have "name" and
            "ignoresPlayerLimit" keys. Defaults to None.

    Returns:
        dict: A dictionary indicating success or failure.
            On success: {"status": "success", "existing_players": [...], "added_players": [...]}
            On failure: {"status": "error", "message": ...}
    """
    if not server_name:
        raise InvalidServerNameError(
            "configure_allowlist_handler: server_name is empty."
        )
        # return {"status": "error", "message": "Server name cannot be empty."} # Consider raising the error.

    base_dir = get_base_dir(base_dir)
    server_dir = os.path.join(base_dir, server_name)
    logger.info(f"Configuring allowlist for server: {server_name}")

    try:
        existing_players = server_base.configure_allowlist(server_dir)
        if existing_players is None:
            existing_players = []
    except FileOperationError as e:
        logger.exception(f"Error reading existing allowlist: {e}")
        return {"status": "error", "message": f"Error reading existing allowlist: {e}"}
    except Exception as e:
        logger.exception(f"An unexpected error occurred reading allowlist: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}

    if new_players_data is None:  # No new players provided
        logger.debug("No new players provided to configure_allowlist_handler.")
        return {
            "status": "success",
            "existing_players": existing_players,
            "added_players": [],
        }

    # Remove duplicates *before* calling add_players_to_allowlist
    added_players = []
    for player in new_players_data:
        if not player["name"]:  # Check for bad data format
            logger.warning(f"Skipping player entry due to missing name: {player}")
            continue  # Skip this entry and log
        if any(p["name"] == player["name"] for p in existing_players):
            logger.info(
                f"Player {player['name']} is already in the allowlist. Skipping."
            )
            continue
        if any(p["name"] == player["name"] for p in added_players):
            logger.info(
                f"Player {player['name']} was already added in this batch. Skipping."
            )
            continue
        added_players.append(player)

    if added_players:
        try:
            server_base.add_players_to_allowlist(server_dir, added_players)
            logger.debug(f"Added players to allowlist: {added_players}")
            return {
                "status": "success",
                "existing_players": existing_players,
                "added_players": added_players,
            }
        except FileOperationError as e:
            logger.exception(f"Error adding players to allowlist: {e}")
            return {
                "status": "error",
                "message": f"Error adding players to allowlist: {e}",
            }
        except Exception as e:
            logger.exception(f"An unexpected error occurred adding players: {e}")
            return {"status": "error", "message": f"An unexpected error occurred: {e}"}
    else:
        logger.debug("No new players to add to allowlist.")
        return {
            "status": "success",
            "existing_players": existing_players,
            "added_players": [],
        }


def add_players_handler(players, config_dir):
    """Adds players to the players.json file.

    Args:
        players (list): A list of strings, where each string represents a player
                        in the format "playername:playerid".
        config_dir (str): The directory where the players.json file is located.

    Returns:
        dict: A dictionary indicating success or failure.
            On success: {"status": "success"}
            On failure: {"status": "error", "message": ...}
    """
    logger.info("Adding players to players.json...")
    try:
        player_string = ",".join(players)  # Join the list into a comma-separated string
        player_list = player_base.parse_player_argument(player_string)
        player_base.save_players_to_json(player_list, config_dir)
        logger.debug(f"Added players: {player_list}")
        return {"status": "success"}
    except PlayerDataError as e:  # Catch specific errors first
        logger.error(f"Error parsing player data: {e}")
        return {"status": "error", "message": f"Error parsing player data: {e}"}
    except FileOperationError as e:
        logger.error(f"Error saving player data: {e}")
        return {"status": "error", "message": f"Error saving player data: {e}"}
    except ValueError as e:
        logger.error(f"Invalid player data format: {e}")
        return {"status": "error", "message": f"Invalid player data format: {e}"}
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred: {type(e).__name__}: {e}"
        )  # Log unexpected errors
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def get_players_from_json_handler(config_dir=None):
    """Retrieves player data from players.json.

    Args:
        config_dir (str, optional): The configuration directory. Defaults to the main config dir.

    Returns:
        dict: {"status": "success", "players": [...]} or {"status": "error", "message": ...}
    """
    if config_dir is None:
        config_dir = settings._config_dir

    players_file = os.path.join(config_dir, "players.json")
    logger.info(f"Retrieving player data from: {players_file}")

    if not os.path.exists(players_file):
        logger.warning(f"No players.json file found at: {players_file}")
        return {
            "status": "error",
            "message": f"No players.json file found at: {players_file}",
        }

    try:
        with open(players_file, "r") as f:
            players_data = json.load(f)
            #  Validate that players_data is structured as expected.
            if (
                not isinstance(players_data, dict)
                or "players" not in players_data
                or not isinstance(players_data["players"], list)
            ):
                logger.error(f"Invalid players.json format in {players_file}")
                return {"status": "error", "message": f"Invalid players.json format."}
            logger.debug(f"Successfully loaded player data: {players_data}")
            return {"status": "success", "players": players_data["players"]}

    except (OSError, json.JSONDecodeError) as e:
        logger.exception(f"Failed to read or parse players.json: {e}")
        return {
            "status": "error",
            "message": f"Failed to read or parse players.json: {e}",
        }


def configure_player_permission_handler(
    server_name, xuid, player_name, permission, base_dir=None, config_dir=None
):
    """Configures a player's permission on a server.

    Args:
        server_name (str): The name of the server.
        xuid (str): The player's XUID.
        player_name (str): The player's name.
        permission (str): The permission level ("member", "operator", "visitor").
        base_dir (str, optional): The base directory. Defaults to None.
        config_dir(str, optional):

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    if config_dir is None:
        config_dir = settings._config_dir
    if not server_name:
        raise InvalidServerNameError(
            "configure_player_permission_handler: server_name is empty"
        )
        # return {"status": "error", "message": "Server name cannot be empty."}

    base_dir = get_base_dir(base_dir)
    server_dir = os.path.join(base_dir, server_name)
    logger.info(
        f"Configuring permission for {player_name} ({xuid}) on {server_name} to {permission}"
    )
    try:
        server_base.configure_permissions(server_dir, xuid, player_name, permission)
        logger.debug(f"Successfully configured permission for {player_name} ({xuid})")
        return {"status": "success"}
    except Exception as e:  # Catch potential exceptions from configure_permissions
        logger.exception(
            f"Error configuring permissions for {player_name} ({xuid}): {e}"
        )
        return {"status": "error", "message": f"Error configuring permissions: {e}"}


def read_server_properties_handler(server_name, base_dir=None):
    """Reads and parses the server.properties file.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success", "properties": {key: value}} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    server_dir = os.path.join(base_dir, server_name)
    server_properties_path = os.path.join(server_dir, "server.properties")
    logger.debug(f"Reading server.properties for server: {server_name}")
    if not os.path.exists(server_properties_path):
        logger.error(f"server.properties not found in: {server_properties_path}")
        return {
            "status": "error",
            "message": f"server.properties not found in: {server_properties_path}",
        }

    properties = {}
    try:
        with open(server_properties_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line:
                    key, value = line.split("=", 1)
                    properties[key] = value
        logger.debug(f"Successfully read server.properties: {properties}")
    except OSError as e:
        logger.exception(f"Failed to read server.properties: {e}")
        return {"status": "error", "message": f"Failed to read server.properties: {e}"}

    return {"status": "success", "properties": properties}


def validate_property_value_handler(property_name, value):
    """
    Validates a server property value
    Args:
        property_name: The name of the property
        value: The value to be validated

    Returns:
        {"status": "success"} or {"status": "error", "message": ...}
    """
    logger.debug(f"Validating property: {property_name} = {value}")
    if property_name == "server-name":
        if ";" in value:
            logger.warning(f"Invalid value for {property_name}: contains semicolons")
            return {
                "status": "error",
                "message": f"{property_name} cannot contain semicolons.",
            }
    elif property_name == "level-name":
        if not re.match(r"^[a-zA-Z0-9_-]+$", value):
            logger.warning(
                f"Invalid value for {property_name}: contains invalid characters"
            )
            return {
                "status": "error",
                "message": f"Invalid {property_name}. Only alphanumeric characters, hyphens, and underscores are allowed.",
            }
    elif property_name in ("server-port", "server-portv6"):
        if not (re.match(r"^[0-9]+$", value) and 1024 <= int(value) <= 65535):
            logger.warning(
                f"Invalid value for {property_name}: Not a valid port number"
            )
            return {
                "status": "error",
                "message": f"Invalid {property_name} number. Please enter a number between 1024 and 65535.",
            }
    elif property_name == "max-players":
        if not re.match(r"^[0-9]+$", value):
            logger.warning(f"Invalid value for {property_name}: Not a number")
            return {
                "status": "error",
                "message": f"Invalid number for {property_name}.",
            }
    elif property_name == "view-distance":
        if not (re.match(r"^[0-9]+$", value) and int(value) >= 5):
            logger.warning(f"Invalid value for {property_name}: Value less than 5")
            return {
                "status": "error",
                "message": f"Invalid {property_name}. Please enter a number greater than or equal to 5.",
            }
    elif property_name == "tick-distance":
        if not (re.match(r"^[0-9]+$", value) and 4 <= int(value) <= 12):
            logger.warning(
                f"Invalid value for {property_name}: Value not between 4 and 12."
            )
            return {
                "status": "error",
                "message": f"Invalid {property_name}. Please enter a number between 4 and 12.",
            }
    return {"status": "success"}


def modify_server_properties_handler(server_name, properties_to_update, base_dir=None):
    """Modifies server properties.

    Args:
        server_name (str): The name of the server.
        properties_to_update (dict): A dictionary of properties to update
            (key-value pairs).
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    server_dir = os.path.join(base_dir, server_name)
    server_properties_path = os.path.join(server_dir, "server.properties")
    logger.info(f"Modifying properties for server: {server_name}")

    if not server_name:
        raise InvalidServerNameError(
            "modify_server_properties_handler: server_name is empty"
        )
        # return {"status": "error", "message": "Server name cannot be empty."}

    for prop_name, prop_value in properties_to_update.items():
        # Validate each property before attempting to modify it.
        validation_result = validate_property_value_handler(prop_name, prop_value)
        if validation_result["status"] == "error":
            logger.error(
                f"Validation error for {prop_name}={prop_value}: {validation_result['message']}"
            )
            return validation_result  # Return immediately if validation fails

        try:
            server_base.modify_server_properties(
                server_properties_path, prop_name, prop_value
            )
        except Exception as e:
            logger.exception(f"Error modifying property {prop_name}: {e}")
            return {
                "status": "error",
                "message": f"Error modifying property {prop_name}: {e}",
            }

    return {"status": "success"}


def download_and_install_server_handler(
    server_name, base_dir=None, target_version="LATEST", in_update=False
):
    """Downloads and installs the Bedrock server.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.
        target_version (str, optional): "LATEST", "PREVIEW", or a specific
            version. Defaults to "LATEST".
        in_update (bool, optional): True if this is an update, False for
            a new install. Defaults to False.

    Returns:
        dict: {"status": "success", "version": ...} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    server_dir = os.path.join(base_dir, server_name)

    if not server_name:
        raise InvalidServerNameError(
            "download_and_install_server_handler: server_name is empty."
        )
        # return {"status": "error", "message": "Server name cannot be empty."}

    logger.info("Starting Bedrock server download process...")
    try:
        current_version, zip_file, download_dir = downloader.download_bedrock_server(
            server_dir, target_version
        )
        server_base.install_server(
            server_name, base_dir, current_version, zip_file, server_dir, in_update
        )
        logger.info(
            f"Installed Bedrock server version: {current_version}"
        )  # Log success within handler
        logger.info("Bedrock server download and installation process finished")
        return {"status": "success", "version": current_version}
    except DownloadError as e:  # Catch specific exceptions from downloader
        logger.exception(f"Download error: {e}")
        return {"status": "error", "message": f"Download error: {e}"}
    except InstallUpdateError as e:  # Catch specific exceptions from server_base
        logger.exception(f"Installation error: {e}")
        return {"status": "error", "message": f"Installation error: {e}"}
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {type(e).__name__}: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def validate_server_name_format_handler(server_name):
    """Validates the format of a server name (alphanumeric, hyphens, underscores)."""
    logger.debug(f"Validating server name format: {server_name}")
    if not re.match(r"^[a-zA-Z0-9_-]+$", server_name):
        logger.warning(f"Invalid server name format: {server_name}")
        return {
            "status": "error",
            "message": "Invalid server folder name. Only alphanumeric characters, hyphens, and underscores are allowed.",
        }
    return {"status": "success"}


def write_server_config_handler(server_name, key, value, config_dir=None):
    """Writes a key-value pair to the server's config.

    Args:
        server_name (str): The name of the server.
        key (str): The configuration key.
        value (str): The configuration value.
        config_dir (str, optional): The config directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    logger.debug(
        f"Writing server config: server={server_name}, key={key}, value={value}"
    )
    try:
        server_base.manage_server_config(server_name, key, "write", value, config_dir)
        logger.debug(f"Successfully wrote config: {key}={value} for {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Failed to write server config: {e}")
        return {"status": "error", "message": f"Failed to write server config: {e}"}


def install_new_server_handler(
    server_name,
    target_version="LATEST",
    base_dir=None,
    config_dir=None,
):
    """Installs a new Bedrock server.  Handles the entire workflow.

    This is the core handler that orchestrates the installation.  It calls
    other handlers to perform specific tasks.

    Args:
        server_name (str): The name of the server.
        target_version (str): The target version ("LATEST", "PREVIEW", or specific).
        base_dir (str, optional): The base directory. Defaults to None.
        config_dir (str, optional): The config directory. Defaults to None.
        configure_properties(bool, optional):
        configure_allowlist(bool, optional):
        configure_permissions(bool, optional):
    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Installing new server {server_name}...")
    # --- Validate Server Name Format ---
    validation_result = validate_server_name_format_handler(server_name)
    if validation_result["status"] == "error":
        return validation_result
    # --- Handle Existing Server ---
    server_dir = os.path.join(base_dir, server_name)
    if os.path.exists(server_dir):
        logger.warning(f"Server directory {server_name} already exists.")
        return {
            "status": "error",
            "message": f"Server directory {server_name} already exists.",
        }

    # --- Write Initial Server Config ---
    config_result = write_server_config_handler(
        server_name, "server_name", server_name, config_dir
    )
    if config_result["status"] == "error":
        return config_result
    config_result = write_server_config_handler(
        server_name, "target_version", target_version, config_dir
    )
    if config_result["status"] == "error":
        return config_result
    # --- Download and Install ---
    download_result = download_and_install_server_handler(
        server_name, base_dir, target_version=target_version, in_update=False
    )
    if download_result["status"] == "error":
        return download_result

    # --- Write Status After Install ---
    config_result = write_server_config_handler(
        server_name, "status", "INSTALLED", config_dir
    )
    if config_result["status"] == "error":
        return config_result

    logger.info(f"Server {server_name} installed successfully.")
    return {"status": "success", "server_name": server_name}


def update_server_handler(
    server_name, base_dir=None, send_message=True, config_dir=None
):
    """Updates an existing Bedrock server.

    Args:
        server_name (str): The name of the server to update.
        base_dir (str, optional): The base directory. Defaults to None.
        send_message (bool, optional): Whether to send a message if server is running

    Returns:
        dict: {"status": "success", "updated": True/False, "new_version": ...}
            or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    config_dir = settings._config_dir

    logger.info(f"Starting update process for: {server_name}")

    if not server_name:
        raise InvalidServerNameError("update_server_handler: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}
    # --- Check if server is running and send message  ---
    if send_message and system_base.is_server_running(server_name, base_dir):
        try:
            bedrock_server = server_base.BedrockServer(server_name, base_dir)
            bedrock_server.send_command("say Checking for server updates..")
            logger.info(f"Sent update notification to server: {server_name}")
        except Exception as e:
            #  Don't fail the entire update if sending the message fails.
            logger.warning(f"Failed to send message to server: {e}")
    # --- Get Installed and Target Versions ---
    try:
        installed_version = server_base.get_installed_version(server_name, config_dir)
        if installed_version == "UNKNOWN":
            logger.warning("Failed to get the installed version. Attempting update...")
    except Exception as e:
        logger.exception(f"Error getting installed version for {server_name}: {e}")
        return {"status": "error", "message": f"Error getting installed version: {e}"}

    try:
        target_version = server_base.manage_server_config(
            server_name, "target_version", "read", config_dir=config_dir
        )
        if target_version is None:
            logger.warning("Failed to read target_version from config. Using 'LATEST'.")
            target_version = "LATEST"
    except Exception as e:
        logger.exception(f"Error getting target version for {server_name}: {e}")
        return {"status": "error", "message": f"Error getting target version: {e}"}
    # --- Check if Update is Needed ---
    if server_base.no_update_needed(server_name, installed_version, target_version):
        logger.info(f"No update needed for {server_name}.")
        return {"status": "success", "updated": False}

    # --- Download and Install Update ---
    download_result = download_and_install_server_handler(
        server_name, base_dir, target_version=target_version, in_update=True
    )
    if download_result["status"] == "error":
        return download_result

    logger.info(
        f"{server_name} updated successfully to version {download_result['version']}."
    )
    return {
        "status": "success",
        "updated": True,
        "new_version": download_result["version"],
    }


def check_user_lingering_enabled_handler():
    """Checks if user lingering is already enabled.

    Returns:
        dict: {"status": "success", "enabled": True/False} or {"status": "error", "message": ...}
    """
    if platform.system() != "Linux":
        return {"status": "success", "enabled": False}  # Not applicable

    username = getpass.getuser()
    logger.debug(f"Checking if lingering is enabled for user: {username}")
    try:
        result = subprocess.run(
            ["loginctl", "show-user", username],
            capture_output=True,
            text=True,
            check=False,
        )
        if "Linger=yes" in result.stdout:
            logger.debug(f"Lingering is enabled for user: {username}")
            return {"status": "success", "enabled": True}
        else:
            logger.debug(f"Lingering is NOT enabled for user: {username}")
            return {"status": "success", "enabled": False}
    except FileNotFoundError:
        logger.error("loginctl command not found. Lingering cannot be checked.")
        return {
            "status": "error",
            "message": "loginctl command not found. Lingering cannot be checked.",
        }
    except Exception as e:
        logger.exception(f"Error checking lingering status: {e}")
        return {"status": "error", "message": f"Error checking lingering status: {e}"}


def enable_user_lingering_handler():
    """Enables user lingering.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    if platform.system() != "Linux":
        return {"status": "success"}  # Not applicable
    logger.debug("Attempting to enable user lingering.")
    try:
        system_linux.enable_user_lingering()
        logger.info("User lingering enabled.")
        return {"status": "success"}
    except CommandNotFoundError as e:  # Catch specific errors first.
        logger.error(f"Command error enabling lingering: {e}")
        return {"status": "error", "message": f"Command error: {e}"}
    except Exception as e:
        logger.exception(f"Failed to enable lingering: {e}")
        return {"status": "error", "message": f"Failed to enable lingering: {e}"}


def create_systemd_service_handler(
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
        raise InvalidServerNameError(
            "create_systemd_service_handler: server_name is empty."
        )
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


def set_windows_autoupdate_handler(server_name, autoupdate_value, base_dir=None):
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
        raise InvalidServerNameError(
            "set_windows_autoupdate_handler: server_name is empty"
        )
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


def enable_service_handler(server_name, base_dir=None):
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


def disable_service_handler(server_name, base_dir=None):
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


def start_server_handler(server_name, base_dir=None):
    """Starts the Bedrock server.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Starting server: {server_name}")
    if not server_name:
        raise InvalidServerNameError("start_server_handler: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}

    if system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is already running.")
        return {"status": "error", "message": f"{server_name} is already running."}

    try:
        bedrock_server = server_base.BedrockServer(
            server_name, os.path.join(base_dir, server_name)
        )
        bedrock_server.start()  # Call start method
        logger.debug(f"Started server: {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error starting server {server_name}: {e}")
        return {
            "status": "error",
            "message": f"Failed to start server: {e}",
        }  # Provide error message


def systemd_start_server_handler(server_name, base_dir=None):
    """Starts the Bedrock server via systemd.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Starting server via systemd: {server_name}")
    if not server_name:
        raise InvalidServerNameError(
            "systemd_start_server_handler: server_name is empty."
        )
        # return {"status": "error", "message": "Server name cannot be empty."}

    if system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is already running (systemd start).")
        return {"status": "error", "message": f"{server_name} is already running."}

    try:
        system_linux._systemd_start_server(
            server_name, os.path.join(base_dir, server_name)
        )
        logger.debug(f"Started server via systemd: {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error starting server via systemd: {e}")
        return {
            "status": "error",
            "message": f"Failed to start server via systemd: {e}",
        }


def stop_server_handler(server_name, base_dir=None):
    """Stops the Bedrock server.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Stopping server: {server_name}")

    if not server_name:
        raise InvalidServerNameError("stop_server_handler: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}

    if not system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is not running.")
        return {"status": "error", "message": f"{server_name} is not running."}

    try:
        bedrock_server = server_base.BedrockServer(
            server_name, os.path.join(base_dir, server_name)
        )
        bedrock_server.stop()  # Stop the server
        logger.debug(f"Stopped server: {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error stopping server {server_name}: {e}")
        return {"status": "error", "message": f"Failed to stop server: {e}"}


def systemd_stop_server_handler(server_name, base_dir=None):
    """Stops the Bedrock server via systemd.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Stopping server via systemd: {server_name}")
    if not server_name:
        raise InvalidServerNameError(
            "systemd_stop_server_handler: server_name is empty."
        )
        # return {"status": "error", "message": "Server name cannot be empty."}

    if not system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is not running (systemd stop).")
        return {"status": "error", "message": f"{server_name} is not running."}

    try:
        system_linux._systemd_stop_server(
            server_name, os.path.join(base_dir, server_name)
        )
        logger.debug(f"Stopped server via systemd: {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error stopping server via systemd: {e}")
        return {"status": "error", "message": f"Failed to stop server via systemd: {e}"}


def restart_server_handler(server_name, base_dir=None, send_message=True):
    """Restarts the Bedrock server.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory.  Defaults to None.
        send_message (bool, optional): Whether to send an in-game message.
            Defaults to True.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Restarting server: {server_name}")
    if not server_name:
        raise InvalidServerNameError("restart_server_handler: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}

    if not system_base.is_server_running(server_name, base_dir):
        logger.info(f"{server_name} is not running, starting it.")
        #  If not running, just start it.  Don't return an error.
        return start_server_handler(server_name, base_dir)

    logger.info(f"Restarting {server_name}...")

    # Send restart warning (optional)
    if send_message:
        try:
            bedrock_server = server_base.BedrockServer(server_name, base_dir)
            bedrock_server.send_command("say Restarting server in 10 seconds..")
            logger.info(f"Sent restart warning to server: {server_name}")
            time.sleep(10)
        except Exception as e:
            #  Don't fail the entire restart if sending the message fails.
            logger.warning(f"Failed to send message to server: {e}")

    # Stop and then start the server.
    stop_result = stop_server_handler(server_name, base_dir)
    if stop_result["status"] == "error":
        return stop_result

    # Small delay before restarting
    time.sleep(2)

    start_result = start_server_handler(server_name, base_dir)
    if start_result["status"] == "error":
        return start_result
    logger.debug(f"Restarted server: {server_name}")
    return {"status": "success"}


def get_bedrock_process_info_handler(server_name, base_dir=None):
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
        raise InvalidServerNameError(
            "get_bedrock_process_info_handler: server_name is empty"
        )
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


def send_command_handler(server_name, command, base_dir=None):
    """Sends a command to the running Bedrock server.

    Args:
        server_name (str): The name of the server.
        command (str): The command to send.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Sending command to {server_name}: {command}")
    try:
        bedrock_server = server_base.BedrockServer(
            server_name, os.path.join(base_dir, server_name)
        )
        bedrock_server.send_command(command)
        logger.debug(f"Command sent to {server_name}: {command}")
        return {"status": "success"}
    except (
        MissingArgumentError,
        ServerNotRunningError,
        SendCommandError,
        CommandNotFoundError,
    ) as e:
        # Catch all the exceptions that BedrockServer.send_command can raise
        logger.error(f"Error sending command to {server_name}: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:  # also catch unexpected exceptions
        logger.exception(f"Unexpected error sending command to {server_name}: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def attach_to_screen_session_handler(server_name, base_dir=None):
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
        raise InvalidServerNameError(
            "attach_to_screen_session_handler: server_name is empty."
        )
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


def delete_server_data_handler(
    server_name, base_dir=None, config_dir=None, stop_if_running=True
):
    """Deletes a Bedrock server's data.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.
        config_dir (str, optional): The config directory. Defaults to main config dir.
        stop_if_running (bool, optional): Whether to stop the server if its running.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Deleting server data for: {server_name}")
    if not server_name:
        raise InvalidServerNameError(
            "delete_server_data_handler: server_name is empty."
        )
        # return {"status": "error", "message": "Server name cannot be empty."}

    # Stop the server if it's running
    if stop_if_running and system_base.is_server_running(server_name, base_dir):
        logger.info(f"Stopping server {server_name} before deletion...")
        stop_result = stop_server_handler(server_name, base_dir)
        if stop_result["status"] == "error":
            return stop_result  # Return the error from stop_server_handler

    try:
        server_base.delete_server_data(server_name, base_dir, config_dir)
        logger.info(f"Server data deleted for: {server_name}")
        return {"status": "success"}
    except FileOperationError as e:  # Catch specific exceptions
        logger.exception(f"Error deleting server data for {server_name}: {e}")
        return {"status": "error", "message": f"Error deleting server data: {e}"}
    except Exception as e:
        logger.exception(
            f"Unexpected error deleting server data for {server_name}: {e}"
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def get_world_name_handler(server_name, base_dir=None):
    """Retrieves the world name from server.properties.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success", "world_name": ...} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.debug(
        f"get_world_name_handler: Getting world name for server: {server_name}"
    )
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


def extract_world_handler(
    server_name, selected_file, base_dir=None, stop_start_server=True
):
    """Extracts (imports) a world to the server.

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
        raise InvalidServerNameError("extract_world_handler: server_name is empty.")
    logger.info(f"Extracting world for server: {server_name}, file: {selected_file}")

    server_dir = os.path.join(base_dir, server_name)
    world_name_result = get_world_name_handler(server_name, base_dir)
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
            stop_result = stop_server_handler(server_name, base_dir)
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
        start_result = start_server_handler(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result

    logger.info(f"Installed world to {extract_dir}")  # log success
    return {"status": "success"}


def export_world_handler(server_name, base_dir=None):
    """Exports (backs up) the world.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success", "backup_file": ...} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Exporting world for server: {server_name}")
    if not server_name:
        raise InvalidServerNameError("export_world_handler: server_name is empty.")

    world_name_result = get_world_name_handler(server_name, base_dir)
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
    backup_dir = settings.get("BACKUP_DIR")
    backup_file = os.path.join(backup_dir, f"{world_folder}_backup_{timestamp}.mcworld")
    logger.debug(f"Exporting world to: {backup_file}")

    try:
        world.export_world(world_path, backup_file)
        logger.info(f"World backup created: {backup_file}")
        return {"status": "success", "backup_file": backup_file}
    except Exception as e:
        logger.exception(f"Error exporting world: {e}")
        return {"status": "error", "message": f"Error exporting world: {e}"}


def prune_old_backups_handler(
    server_name, file_name=None, backup_keep=None, base_dir=None
):
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
        raise InvalidServerNameError("prune_old_backups_handler: server_name is empty")
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
    world_name_result = get_world_name_handler(server_name, base_dir)
    # Prune world backups (*.mcworld)
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


def backup_world_handler(server_name, base_dir=None, stop_start_server=True):
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
        raise InvalidServerNameError("backup_world_handler: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}
    was_running = False
    if stop_start_server:
        was_running = system_base.is_server_running(server_name, base_dir)
        if was_running:
            logger.debug(f"Stopping server {server_name} for world backup")
            stop_result = stop_server_handler(server_name, base_dir)
            if stop_result["status"] == "error":
                return stop_result

    try:
        world_name_result = get_world_name_handler(server_name, base_dir)
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
        start_result = start_server_handler(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result

    return {"status": "success"}  # Return success here


def backup_config_file_handler(
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
        raise InvalidServerNameError(
            "backup_config_file_handler: server_name is empty."
        )
        # return {"status": "error", "message": "Server name cannot be empty."}
    if not file_to_backup:
        logger.error(f"No file specified for config backup on server {server_name}.")
        return {"status": "error", "message": "File to backup cannot be empty."}

    was_running = False
    if stop_start_server:
        was_running = system_base.is_server_running(server_name, base_dir)
        if was_running:
            logger.debug(f"Stopping server {server_name} for config file backup")
            stop_result = stop_server_handler(server_name, base_dir)
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
        start_result = start_server_handler(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result
    return {"status": "success"}


def backup_all_handler(server_name, base_dir=None, stop_start_server=True):
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
        raise InvalidServerNameError("backup_all_handler: server_name is empty.")

    was_running = False
    if stop_start_server:
        was_running = system_base.is_server_running(server_name, base_dir)
        if was_running:
            logger.debug(f"Stopping server {server_name} for full backup")
            stop_result = stop_server_handler(server_name, base_dir)
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
        start_result = start_server_handler(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result
    return {"status": "success"}


def list_backups_handler(server_name, backup_type, base_dir=None):
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
        logger.warning(f"No backups found for {server_name} in {backup_dir}")
        return {"status": "error", "message": f"No backups found for {server_name}."}

    if backup_type == "world":
        backup_files = glob.glob(os.path.join(backup_dir, "*.mcworld"))
    elif backup_type == "config":
        backup_files = glob.glob(os.path.join(backup_dir, "*_backup_*.json"))
        backup_files += glob.glob(
            os.path.join(backup_dir, "server_backup_*.properties")
        )
    else:
        logger.error(f"Invalid backup type specified: {backup_type}")
        return {"status": "error", "message": f"Invalid backup type: {backup_type}"}
    logger.debug(f"Found backups: {backup_files}")
    return {"status": "success", "backups": backup_files}


def restore_world_handler(
    server_name, backup_file, base_dir=None, stop_start_server=True
):
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
        raise InvalidServerNameError("restore_world_handler: server_name is empty.")
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
            stop_result = stop_server_handler(server_name, base_dir)
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
        start_result = start_server_handler(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result
    return {"status": "success"}


def restore_config_file_handler(
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
        raise InvalidServerNameError(
            "restore_config_file_handler: server_name is empty."
        )
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
            stop_result = stop_server_handler(server_name, base_dir)
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
        start_result = start_server_handler(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result
    return {"status": "success"}


def restore_all_handler(server_name, base_dir=None, stop_start_server=True):
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
        raise InvalidServerNameError("restore_all_handler: server_name is empty.")
    was_running = False
    if stop_start_server:
        was_running = system_base.is_server_running(server_name, base_dir)
        if was_running:
            logger.debug(f"Stopping server {server_name} before restoring all files")
            stop_result = stop_server_handler(server_name, base_dir)
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
        start_result = start_server_handler(server_name, base_dir)
        if start_result["status"] == "error":
            return start_result
    return {"status": "success"}


def list_backups_handler(server_name, backup_type, base_dir=None):
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


def list_content_files_handler(content_dir, extensions):
    """Lists files in a directory with specified extensions.

    Args:
        content_dir (str): The directory to search.
        extensions (list): A list of file extensions (e.g., ["mcworld", "mcaddon"]).

    Returns:
        dict: {"status": "success", "files": [...]} or {"status": "error", "message": ...}
    """
    logger.info(
        f"Listing content files in: {content_dir} with extensions: {extensions}"
    )
    if not os.path.isdir(content_dir):
        logger.error(f"Content directory not found: {content_dir}")
        return {
            "status": "error",
            "message": f"Content directory not found: {content_dir}.",
        }

    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(content_dir, f"*.{ext}")))

    if not files:
        logger.warning(f"No files found with extensions: {extensions} in {content_dir}")
        return {
            "status": "error",
            "message": f"No files found with extensions: {extensions}",
        }
    logger.debug(f"Found content files: {files}")
    return {"status": "success", "files": files}


def install_addon_handler(
    server_name, addon_file, base_dir=None, stop_start_server=True
):
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
        raise InvalidServerNameError("install_addon_handler: server_name is empty.")
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
            stop_result = stop_server_handler(server_name, base_dir)
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
            start_result = start_server_handler(server_name, base_dir)
            if start_result["status"] == "error":
                return start_result


def list_content_files_handler(content_dir, extensions):
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


def scan_player_data_handler(base_dir=None, config_dir=None):
    """Scans server_output.txt files for player data and saves it.

    Args:
        base_dir (str, optional): The base directory. Defaults to None.
        config_dir (str, optional): The config directory. Defaults to the
            main config dir.

    Returns:
        dict: {"status": "success", "players_found": True/False}
            or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    if config_dir is None:
        config_dir = settings._config_dir

    logger.info("Scanning for Players")
    all_players_data = []

    if not os.path.isdir(base_dir):
        logger.error(f"Error: {base_dir} does not exist or is not a directory.")
        return {
            "status": "error",
            "message": f"Error: {base_dir} does not exist or is not a directory.",
        }

    for server_folder in glob.glob(os.path.join(base_dir, "*/")):
        server_name = os.path.basename(os.path.normpath(server_folder))
        log_file = os.path.join(server_folder, "server_output.txt")
        logger.debug(f"Scanning for player data in: {log_file}")

        if not os.path.exists(log_file):
            logger.warning(f"Log file not found for {server_name}, skipping.")
            continue

        try:
            players_data = player_base.scan_log_for_players(log_file)
            if players_data:
                logger.debug(f"Found player data for {server_name}: {players_data}")
                all_players_data.extend(players_data)
        except Exception as e:
            logger.exception(f"Error scanning log for {server_name}: {e}")
            return {
                "status": "error",
                "message": f"Error scanning log for {server_name}: {e}",
            }

    if all_players_data:
        try:
            player_base.save_players_to_json(all_players_data, config_dir)
            logger.info(f"Saved player data to {config_dir}/players.json")
            return {"status": "success", "players_found": True}
        except Exception as e:
            logger.exception(f"Error saving player data: {e}")
            return {"status": "error", "message": f"Error saving player data: {e}"}
    else:
        logger.info("No player data found across all servers.")
        return {"status": "success", "players_found": False}


def get_server_cron_jobs_handler(server_name, base_dir=None):
    """Retrieves the cron jobs for a specific server.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): base directory. Defaults to None.

    Returns:
        dict: {"status": "success", "cron_jobs": [...]} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.debug(f"Getting cron jobs for server: {server_name}")
    try:
        cron_jobs = system_linux.get_server_cron_jobs(server_name)
        logger.debug(f"Cron jobs for {server_name}: {cron_jobs}")
        return {"status": "success", "cron_jobs": cron_jobs}
    except Exception as e:
        logger.exception(f"Failed to retrieve cron jobs for {server_name}: {e}")
        return {"status": "error", "message": f"Failed to retrieve cron jobs: {e}"}


def get_cron_jobs_table_handler(cron_jobs):
    """Formats cron job data for display in a table.

    Args:
        cron_jobs (list): A list of cron job strings.

    Returns:
        dict: {"status": "success", "table_data": [...]} or {"status": "error", "message": ...}
    """
    logger.debug(f"Formatting cron jobs for table display: {cron_jobs}")
    try:
        table_data = system_linux.get_cron_jobs_table(cron_jobs)
        logger.debug(f"Formatted cron job table data: {table_data}")
        return {"status": "success", "table_data": table_data}
    except Exception as e:
        logger.exception(f"Error formatting cron job table: {e}")
        return {"status": "error", "message": f"Error formatting cron job table: {e}"}


def add_cron_job_handler(cron_job_string, base_dir=None):
    """Adds a new cron job.

    Args:
        cron_job_string (str): The complete cron job string.
        base_dir (str, optional): The base_dir. defaults to none

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Adding cron job: {cron_job_string}")
    try:
        system_linux._add_cron_job(cron_job_string)
        logger.debug(f"Cron job added: {cron_job_string}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error adding cron job: {e}")
        return {"status": "error", "message": f"Error adding cron job: {e}"}


def modify_cron_job_handler(old_cron_job_string, new_cron_job_string, base_dir=None):
    """Modifies an existing cron job.

    Args:
        old_cron_job_string (str): The existing cron job string.
        new_cron_job_string (str): The new cron job string.
        base_dir (str, optional): The base_dir. defaults to none

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(
        f"Modifying cron job: Old: {old_cron_job_string} New: {new_cron_job_string}"
    )
    try:
        system_linux._modify_cron_job(old_cron_job_string, new_cron_job_string)
        logger.debug(
            f"Cron job modified. Old: {old_cron_job_string}  New: {new_cron_job_string}"
        )
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error modifying cron job: {e}")
        return {"status": "error", "message": f"Error modifying cron job: {e}"}


def delete_cron_job_handler(cron_job_string, base_dir=None):
    """Deletes a cron job.

    Args:
        cron_job_string (str): The cron job string to delete.
        base_dir (str, optional): The base_dir. defaults to none

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Deleting cron job: {cron_job_string}")
    try:
        system_linux._delete_cron_job(cron_job_string)
        logger.debug(f"Cron job deleted: {cron_job_string}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error deleting cron job {cron_job_string}: {e}")
        return {"status": "error", "message": f"Error deleting cron job: {e}"}


def validate_cron_input_handler(value, min_val, max_val):
    """Validates a single cron input value (minute, hour, day, etc.).
    This is now a handler.
    """
    logger.debug(f"Validating cron input: value={value}, min={min_val}, max={max_val}")
    try:
        system_linux.validate_cron_input(value, min_val, max_val)
        logger.debug(f"Cron input {value} is valid.")
        return {"status": "success"}
    except InvalidCronJobError as e:
        logger.error(f"Invalid cron input: {e}")
        return {"status": "error", "message": str(e)}


def convert_to_readable_schedule_handler(month, day, hour, minute, weekday):
    """Converts cron schedule components to a human-readable string."""
    logger.debug(
        f"Converting cron schedule to readable format: month={month}, day={day}, hour={hour}, minute={minute}, weekday={weekday}"
    )
    try:
        schedule_time = system_linux.convert_to_readable_schedule(
            month, day, hour, minute, weekday
        )
        if schedule_time is None:
            logger.error("Error converting schedule to readable format")
            return {"status": "error", "message": "Error Converting Schedule"}
        logger.debug(f"Converted schedule: {schedule_time}")
        return {"status": "success", "schedule_time": schedule_time}
    except Exception as e:
        logger.exception(f"Error converting schedule: {e}")
        return {"status": "error", "message": str(e)}


def get_server_task_names_handler(server_name, config_dir=None):
    """Retrieves the scheduled task names for a specific server.

    Args:
        server_name (str): The name of the server.
        config_dir (str, optional): The config directory. Defaults to main config dir.

    Returns:
        dict: {"status": "success", "task_names": [...]} or {"status": "error", "message": ...}
    """
    if config_dir is None:
        config_dir = settings._config_dir
    logger.debug(f"Getting task names for server: {server_name}")
    try:
        task_names = system_windows.get_server_task_names(server_name, config_dir)
        logger.debug(f"Task names for {server_name}: {task_names}")
        return {"status": "success", "task_names": task_names}
    except Exception as e:
        logger.exception(f"Error getting task names for {server_name}: {e}")
        return {"status": "error", "message": f"Error getting task names: {e}"}


def get_windows_task_info_handler(task_names):
    """Retrieves detailed information for a list of Windows tasks.

    Args:
        task_names (list): A list of task names.

    Returns:
        dict: {"status": "success", "task_info": [...]} or {"status": "error", "message": ...}
    """
    logger.debug(f"Getting Windows task info for tasks: {task_names}")
    try:
        task_info = system_windows.get_windows_task_info(task_names)
        logger.debug(f"Task info: {task_info}")
        return {"status": "success", "task_info": task_info}
    except Exception as e:
        logger.exception(f"Error getting task info: {e}")
        return {"status": "error", "message": f"Error getting task info: {e}"}


def create_windows_task_handler(
    server_name, command, command_args, task_name, config_dir, triggers, base_dir=None
):
    """Creates a Windows scheduled task.

    Args:
        server_name (str): The name of the server.
        command (str): The command to execute (e.g., "update-server").
        command_args (str): Arguments for the command.
        task_name (str): The name of the task.
        config_dir (str): The config directory.
        triggers (list): A list of trigger dictionaries (as returned by get_trigger_details).
        base_dir (str, optional): base directory. defaults to None
    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)  # Keep for consistency
    logger.info(f"Creating Windows task: {task_name} for server: {server_name}")
    try:
        xml_file_path = system_windows.create_windows_task_xml(
            server_name, command, command_args, task_name, config_dir, triggers
        )
        system_windows.import_task_xml(xml_file_path, task_name)
        logger.info(f"Created Windows task: {task_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error creating Windows task {task_name}: {e}")
        return {"status": "error", "message": f"Error creating task: {e}"}


def get_windows_task_details_handler(task_file_path):
    """Reads a Windows Task Scheduler XML file and extracts command and trigger details.

    Args:
        task_file_path (str): Path to the XML file for the scheduled task.

    Returns:
        dict: {"status": "success", "task_details": {"command": "...", "triggers": [...]}}
              or {"status": "error", "message": ...}
    """
    logger.debug(f"Loading existing task data from XML: {task_file_path}")
    if not os.path.exists(task_file_path):
        logger.error(f"Task XML file not found: {task_file_path}")
        return {"status": "error", "message": "Task XML file not found."}

    try:
        tree = ET.parse(task_file_path)
        root = tree.getroot()
        namespaces = {"ns": "http://schemas.microsoft.com/windows/2004/02/mit/task"}

        # --- Extract Command Part ---
        command_part = ""
        arguments_element = root.find(".//ns:Arguments", namespaces)
        if arguments_element is not None and arguments_element.text is not None:
            command_args = arguments_element.text.strip()
            if command_args:
                command_part = command_args.split()[
                    0
                ]  # Get the first argument as command
        logger.debug(f"Extracted command part: {command_part}")

        # --- Extract Triggers ---
        triggers = []
        trigger_elements = root.findall(".//ns:Triggers/*", namespaces)
        for trigger_elem in trigger_elements:
            trigger_data = {
                "type": trigger_elem.tag.replace(f"{{{namespaces['ns']}}}", "")
            }
            start_elem = trigger_elem.find("ns:StartBoundary", namespaces)
            if start_elem is not None and start_elem.text:
                try:
                    iso_dt = datetime.fromisoformat(start_elem.text)
                    # Format for <input type="datetime-local">
                    trigger_data["start"] = iso_dt.strftime("%Y-%m-%dT%H:%M")
                except ValueError:
                    logger.warning(
                        f"Could not parse start boundary format: {start_elem.text}"
                    )
                    trigger_data["start"] = ""

            # -- Parse Calendar Triggers --
            if trigger_data["type"] == "CalendarTrigger":
                schedule_by_day = trigger_elem.find("ns:ScheduleByDay", namespaces)
                schedule_by_week = trigger_elem.find("ns:ScheduleByWeek", namespaces)
                schedule_by_month = trigger_elem.find("ns:ScheduleByMonth", namespaces)

                if schedule_by_day is not None:
                    trigger_data["type"] = "Daily"
                    interval_elem = schedule_by_day.find("ns:DaysInterval", namespaces)
                    if interval_elem is not None and interval_elem.text:
                        trigger_data["interval"] = int(interval_elem.text)
                elif schedule_by_week is not None:
                    trigger_data["type"] = "Weekly"
                    interval_elem = schedule_by_week.find(
                        "ns:WeeksInterval", namespaces
                    )
                    if interval_elem is not None and interval_elem.text:
                        trigger_data["interval"] = int(interval_elem.text)
                    days_elem = schedule_by_week.find("ns:DaysOfWeek", namespaces)
                    if days_elem is not None:
                        # Map back to user-friendly input format (comma-separated)
                        day_mapping = {
                            "Sunday": "Sun",
                            "Monday": "Mon",
                            "Tuesday": "Tue",
                            "Wednesday": "Wed",
                            "Thursday": "Thu",
                            "Friday": "Fri",
                            "Saturday": "Sat",
                        }
                        days_list = [
                            day_mapping.get(
                                day.tag.replace(f"{{{namespaces['ns']}}}", ""),
                                day.tag.replace(f"{{{namespaces['ns']}}}", ""),
                            )
                            for day in days_elem
                        ]
                        trigger_data["days_of_week"] = ",".join(days_list)
                elif schedule_by_month is not None:
                    trigger_data["type"] = "Monthly"
                    days_elem = schedule_by_month.find("ns:DaysOfMonth", namespaces)
                    if days_elem is not None:
                        trigger_data["days_of_month"] = ",".join(
                            [
                                d.text
                                for d in days_elem.findall("ns:Day", namespaces)
                                if d.text
                            ]
                        )
                    months_elem = schedule_by_month.find("ns:Months", namespaces)
                    if months_elem is not None:
                        # Map back to user-friendly input format (comma-separated)
                        month_mapping = {
                            "January": "Jan",
                            "February": "Feb",
                            "March": "Mar",
                            "April": "Apr",
                            "May": "May",
                            "June": "Jun",
                            "July": "Jul",
                            "August": "Aug",
                            "September": "Sep",
                            "October": "Oct",
                            "November": "Nov",
                            "December": "Dec",
                        }
                        months_list = [
                            month_mapping.get(
                                m.tag.replace(f"{{{namespaces['ns']}}}", ""),
                                m.tag.replace(f"{{{namespaces['ns']}}}", ""),
                            )
                            for m in months_elem
                        ]
                        trigger_data["months"] = ",".join(months_list)
                else:
                    logger.warning(
                        f"Unknown CalendarTrigger subtype in {task_file_path}"
                    )
            triggers.append(trigger_data)

        logger.debug(
            f"Extracted task details: command={command_part}, triggers={triggers}"
        )
        return {
            "status": "success",
            "task_details": {"command": command_part, "triggers": triggers},
        }

    except ET.ParseError as e:
        logger.error(f"Error parsing task XML {task_file_path}: {e}")
        return {"status": "error", "message": f"Error parsing task XML: {e}"}
    except Exception as e:  # Catch unexpected errors
        logger.exception(f"Unexpected error loading task XML {task_file_path}: {e}")
        return {"status": "error", "message": f"Unexpected error loading task XML: {e}"}


def modify_windows_task_handler(
    old_task_name,
    server_name,
    command,
    command_args,
    new_task_name,
    config_dir,
    triggers,
    base_dir=None,
):
    """Modifies an existing Windows scheduled task (by deleting and recreating)."""
    base_dir = get_base_dir(base_dir)  # Keep for consistency
    logger.info(
        f"Modifying Windows task. Old: {old_task_name}, New: {new_task_name} for server: {server_name}"
    )
    old_xml_file_path = os.path.join(config_dir, server_name, f"{old_task_name}.xml")

    try:

        # 1. Create the new XML
        new_xml_file_path = system_windows.create_windows_task_xml(
            server_name, "", command_args, new_task_name, config_dir, triggers
        )

        # 2. Delete the old task
        try:
            system_windows.delete_task(old_task_name)
            logger.debug(f"Deleted old task: {old_task_name}")
        except Exception as e:
            logger.warning(f"Failed to remove task XML: {e}")

        if os.path.exists(old_xml_file_path):
            try:
                os.remove(old_xml_file_path)
                logger.debug(f"Deleted old task XML file: {old_xml_file_path}")
            except OSError as e:
                logger.warning(f"Failed to remove task XML file: {e}")

        # 3. Import the new task
        system_windows.import_task_xml(new_xml_file_path, new_task_name)
        logger.info(
            f"Modified Windows task. Old: {old_task_name}, New: {new_task_name}"
        )
        return {"status": "success"}
    except Exception as e:
        logger.exception(
            f"Error modifying Windows task. Old: {old_task_name}, New: {new_task_name}: {e}"
        )
        return {"status": "error", "message": f"Error modifying task: {e}"}


def create_task_name_handler(server_name, command_args):
    """Cleans up task names for modify windows task."""
    logger.debug(f"Creating task name for server: {server_name}, args: {command_args}")
    # Remove '--server' and the server name using regex
    cleaned_args = re.sub(
        r"--server\s+" + re.escape(server_name) + r"\s*", "", command_args
    ).strip()
    # Replace all non-alphanumeric characters with underscores
    sanitized_args = re.sub(r"\W+", "_", cleaned_args)

    new_task_name = f"bedrock_{server_name}_{sanitized_args}_{get_timestamp()}"
    logger.debug(f"Created task name: {new_task_name}")
    return new_task_name


def delete_windows_task_handler(task_name, task_file_path, base_dir=None):
    """Deletes a Windows scheduled task and its associated XML file.

    Args:
        task_name (str): The name of the task to delete.
        task_file_path (str): Path to the XML file.
        base_dir (str, optional): base directory

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Deleting Windows task: {task_name}")
    try:
        system_windows.delete_task(task_name)
        # Also remove the XML file
        try:
            os.remove(task_file_path)
            logger.debug(f"Deleted task XML file: {task_file_path}")
        except OSError as e:
            logger.warning(f"Failed to remove task XML file: {e}")  # Log but don't fail
        logger.debug(f"Deleted task: {task_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error deleting task {task_name}: {e}")
        return {"status": "error", "message": f"Error deleting task: {e}"}


def get_day_element_name_handler(day_input):
    """Gets the XML element name for a day of the week."""
    logger.debug(f"Getting day element name for: {day_input}")
    try:
        day_name = system_windows._get_day_element_name(day_input)
        logger.debug(f"Day element name: {day_name}")
        return {"status": "success", "day_name": day_name}
    except Exception as e:
        logger.exception(f"Error getting day element name for: {day_input} - {e}")
        return {"status": "error", "message": str(e)}


def get_month_element_name_handler(month_input):
    """Gets the XML element name for a month."""
    logger.debug(f"Getting month element name for: {month_input}")
    try:
        month_name = system_windows._get_month_element_name(month_input)
        logger.debug(f"Month element name: {month_name}")
        return {"status": "success", "month_name": month_name}
    except Exception as e:
        logger.exception(f"Error getting month element name for {month_input} - {e}")
        return {"status": "error", "message": str(e)}


def start_web_server_handler(host=None, debug=False, mode="direct"):
    """Starts the web server with defined host with optional debug mode

    Args:
        host (str, optional): The base directory for servers. Defaults to None.
        debug (bool, optional): Starts the server in debug mode
    """
    if mode == "direct":
        logger.info("Running web-server directly...")
        try:
            run_web_server(host, debug)
            return {"status": "success"}
        except Exception as e:
            logger.exception(f"Error updating server statuses: {e}")
            return {
                "status": "error",
                "message": f"Error updating server statuses: {e}",
            }

    elif mode == "detached":
        logger.info("Running web-server in detached mode...")
        try:
            command = [str(EXPATH), "start-webserver"]
            if host:
                command.extend(["--host", host])
            if debug:
                command.append("--debug")
            command.extend(["--mode", "direct"])

            process = subprocess.Popen(
                command,
                cwd=SCRIPT_DIR,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                ),  # Don't open a console
            )

            logger.info(f"Started web server with PID: {process.pid}")
            return {"status": "success", "process": process.pid}

        except FileNotFoundError:
            logger.error(f"Executable or script not found: {EXPATH}")
            return {"status": "error", "message": f"Executable not found: {EXPATH}"}
        except Exception as e:
            logger.exception(f"Error starting process: {e}")
            return {"status": "error", "message": str(e)}


def stop_web_server_handler(script_dir=SCRIPT_DIR):
    script_dir = settings.get("BASE_DIR")
    try:
        logger.warning("Not implemented")
    except Exception as e:
        logger.exception(f"Error starting process: {e}")
        return {"status": "error", "message": str(e)}
    return {"status": "success"}
