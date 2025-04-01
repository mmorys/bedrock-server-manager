# bedrock-server-manager/bedrock_server_manager/api/install_config.py
import os
import logging
import re
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.core.download import downloader
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.api.server import write_server_config
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.api.utils import validate_server_name_format
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
    DownloadError,
    InstallUpdateError,
)


logger = logging.getLogger("bedrock_server_manager")


def configure_allowlist(server_name, base_dir=None, new_players_data=None):
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
        raise InvalidServerNameError("configure_allowlist: server_name is empty.")
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
        logger.debug("No new players provided to configure_allowlist.")
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


def configure_player_permission(
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
            "configure_player_permission: server_name is empty"
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


def read_server_properties(server_name, base_dir=None):
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


def validate_server_property_value(property_name, value):
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


def modify_server_properties(server_name, properties_to_update, base_dir=None):
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
        raise InvalidServerNameError("modify_server_properties: server_name is empty")
        # return {"status": "error", "message": "Server name cannot be empty."}

    for prop_name, prop_value in properties_to_update.items():
        # Validate each property before attempting to modify it.
        validation_result = validate_server_property_value(prop_name, prop_value)
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


def download_and_install_server(
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
            "download_and_install_server: server_name is empty."
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
        logger.info(f"Installed Bedrock server version: {current_version}")
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


def install_new_server(
    server_name,
    target_version="LATEST",
    base_dir=None,
    config_dir=None,
):
    """Installs a new Bedrock server.  Handles the entire workflow.

    This is the core api that orchestrates the installation.  It calls
    other apis to perform specific tasks.

    Args:
        server_name (str): The name of the server.
        target_version (str): The target version ("LATEST", "PREVIEW", or specific).
        base_dir (str, optional): The base directory. Defaults to None.
        config_dir (str, optional): The config directory. Defaults to None.
    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Installing new server {server_name}...")
    # --- Validate Server Name Format ---
    validation_result = validate_server_name_format(server_name)
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
    config_result = write_server_config(
        server_name, "server_name", server_name, config_dir
    )
    if config_result["status"] == "error":
        return config_result
    config_result = write_server_config(
        server_name, "target_version", target_version, config_dir
    )
    if config_result["status"] == "error":
        return config_result
    # --- Download and Install ---
    download_result = download_and_install_server(
        server_name, base_dir, target_version=target_version, in_update=False
    )
    if download_result["status"] == "error":
        return download_result

    # --- Write Status After Install ---
    config_result = write_server_config(server_name, "status", "INSTALLED", config_dir)
    if config_result["status"] == "error":
        return config_result

    logger.info(f"Server {server_name} installed successfully.")
    return {"status": "success", "server_name": server_name}


def update_server(server_name, base_dir=None, send_message=True, config_dir=None):
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
        raise InvalidServerNameError("update_server: server_name is empty.")
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
    download_result = download_and_install_server(
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
