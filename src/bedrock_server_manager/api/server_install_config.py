# bedrock_server_manager/api/server_install_config.py
"""Provides API functions for server installation, updates, and configuration.

This module orchestrates calls to the `BedrockServer` class to manage server
files and settings. It handles operations related to installation, updates,
`server.properties`, `allowlist.json`, and `permissions.json`.
"""
import os
import logging
import re
from typing import Dict, List, Optional, Any

# Plugin system imports to bridge API functionality.
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.api.utils import (
    server_lifecycle_manager,
    validate_server_name_format,
)
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    FileOperationError,
    MissingArgumentError,
    UserInputError,
    AppFileNotFoundError,
)

logger = logging.getLogger(__name__)


# --- Allowlist ---
@plugin_method("add_players_to_allowlist_api")
def add_players_to_allowlist_api(
    server_name: str, new_players_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Adds new players to the allowlist for a specific server.

    This function updates the `allowlist.json` file. If the server is
    running, it will attempt to reload the allowlist via a server command.

    Args:
        server_name: The name of the server to modify.
        new_players_data: A list of player dictionaries to add. Each dictionary
            should contain at least a 'name' and 'xuid'.

    Returns:
        A dictionary with the operation status, a message, and the count of
        players added.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not isinstance(new_players_data, list):
        return {
            "status": "error",
            "message": "Invalid input: new_players_data must be a list.",
        }

    plugin_manager.trigger_event(
        "before_allowlist_change",
        server_name=server_name,
        players_to_add=new_players_data,
        players_to_remove=[],
    )

    logger.info(
        f"API: Adding {len(new_players_data)} player(s) to allowlist for '{server_name}'."
    )
    result = {}
    try:
        server = BedrockServer(server_name)
        added_count = server.add_to_allowlist(new_players_data)

        result = {
            "status": "success",
            "message": f"Successfully added {added_count} new players to the allowlist.",
            "added_count": added_count,
        }

    except (FileOperationError, TypeError) as e:
        logger.error(
            f"API: Failed to update allowlist for '{server_name}': {e}", exc_info=True
        )
        result = {"status": "error", "message": f"Failed to update allowlist: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error updating allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Unexpected error updating allowlist: {e}",
        }
    finally:
        plugin_manager.trigger_event(
            "after_allowlist_change", server_name=server_name, result=result
        )

    return result


@plugin_method("get_server_allowlist_api")
def get_server_allowlist_api(server_name: str) -> Dict[str, Any]:
    """Retrieves the allowlist for a specific server.

    Args:
        server_name: The name of the server.

    Returns:
        A dictionary containing the status and a list of players on the
        allowlist. On success: `{"status": "success", "players": [...]}`.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    try:
        server = BedrockServer(server_name)
        players = server.get_allowlist()
        return {"status": "success", "players": players}
    except BSMError as e:
        logger.error(
            f"API: Failed to access allowlist for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to access allowlist: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error reading allowlist: {e}",
        }


@plugin_method("remove_players_from_allowlist")
def remove_players_from_allowlist(
    server_name: str, player_names: List[str]
) -> Dict[str, Any]:
    """Removes one or more players from the server's allowlist by name.

    Args:
        server_name: The name of the server to modify.
        player_names: A list of player gamertags to remove.

    Returns:
        A dictionary with the operation status and details about which
        players were removed and which were not found.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    plugin_manager.trigger_event(
        "before_allowlist_change",
        server_name=server_name,
        players_to_add=[],
        players_to_remove=player_names,
    )

    result = {}
    try:
        if not player_names:
            return {
                "status": "success",
                "message": "No players specified for removal.",
                "details": {"removed": [], "not_found": []},
            }

        server = BedrockServer(server_name)
        removed_players, not_found_players = [], []

        # Iterate and remove each player, tracking success and failure.
        for player in player_names:
            if server.remove_from_allowlist(player):
                removed_players.append(player)
            else:
                not_found_players.append(player)

        result = {
            "status": "success",
            "message": "Allowlist update process completed.",
            "details": {"removed": removed_players, "not_found": not_found_players},
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to remove players from allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Failed to process allowlist removal: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error removing players for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Unexpected error: {e}"}
    finally:
        plugin_manager.trigger_event(
            "after_allowlist_change", server_name=server_name, result=result
        )

    return result


# --- Player Permissions ---
@plugin_method("configure_player_permission")
def configure_player_permission(
    server_name: str, xuid: str, player_name: Optional[str], permission: str
) -> Dict[str, str]:
    """Sets a player's permission level in permissions.json.

    Args:
        server_name: The name of the server.
        xuid: The player's XUID.
        player_name: The player's gamertag (optional, for reference).
        permission: The permission level to set (e.g., 'member', 'operator').

    Returns:
        A dictionary with the operation status and a message.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    plugin_manager.trigger_event(
        "before_permission_change",
        server_name=server_name,
        xuid=xuid,
        permission=permission,
    )

    result = {}
    try:
        server = BedrockServer(server_name)
        server.set_player_permission(xuid, permission, player_name)

        result = {
            "status": "success",
            "message": f"Permission for XUID '{xuid}' set to '{permission.lower()}'.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to configure permission for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Failed to configure permission: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error configuring permission for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Unexpected error: {e}"}
    finally:
        plugin_manager.trigger_event(
            "after_permission_change", server_name=server_name, xuid=xuid, result=result
        )

    return result


@plugin_method("get_server_permissions_api")
def get_server_permissions_api(server_name: str) -> Dict[str, Any]:
    """Retrieves processed permissions data for a server.

    This function reads `permissions.json` and enriches the data by mapping
    XUIDs to player names using the central player database.

    Args:
        server_name: The name of the server.

    Returns:
        A dictionary containing the status and the formatted permissions data.
    """
    if not server_name:
        return {"status": "error", "message": "Server name cannot be empty."}

    try:
        server = BedrockServer(server_name)
        player_name_map: Dict[str, str] = {}

        # Fetch global player data to create a XUID -> Name mapping.
        players_response = player_api.get_all_known_players_api()
        if players_response.get("status") == "success":
            for p_data in players_response.get("players", []):
                if p_data.get("xuid") and p_data.get("name"):
                    player_name_map[str(p_data["xuid"])] = str(p_data["name"])

        permissions = server.get_formatted_permissions(player_name_map)
        return {"status": "success", "data": {"permissions": permissions}}
    except AppFileNotFoundError as e:
        # It's not an error if the permissions file doesn't exist; it just means no permissions are set.
        return {
            "status": "success",
            "data": {"permissions": []},
            "message": f"{e}",
        }
    except BSMError as e:
        logger.error(
            f"API: Failed to get permissions for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to get permissions: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting permissions for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}


# --- Server Properties ---
@plugin_method("get_server_properties_api")
def get_server_properties_api(server_name: str) -> Dict[str, Any]:
    """Reads and returns the `server.properties` file for a server.

    Args:
        server_name: The name of the server.

    Returns:
        A dictionary containing the status and the server properties as a
        key-value mapping.
    """
    if not server_name:
        return {"status": "error", "message": "Server name cannot be empty."}
    try:
        server = BedrockServer(server_name)
        properties = server.get_server_properties()
        return {"status": "success", "properties": properties}
    except AppFileNotFoundError as e:
        return {"status": "error", "message": str(e)}
    except BSMError as e:
        logger.error(
            f"API: Failed to get properties for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to get properties: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting properties for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}


@plugin_method("validate_server_property_value")
def validate_server_property_value(property_name: str, value: str) -> Dict[str, str]:
    """Validates a single server property value based on known rules.

    This is a stateless helper function used before modifying properties.

    Args:
        property_name: The name of the property (e.g., 'level-name').
        value: The string value to validate.

    Returns:
        A dictionary with a 'status' of 'success' or 'error', and a 'message'
        if validation fails.
    """
    logger.debug(
        f"API: Validating server property: '{property_name}', Value: '{value}'"
    )
    if value is None:
        value = ""
    # Validate server-name (MOTD)
    if property_name == "server-name":
        if ";" in value:
            return {
                "status": "error",
                "message": "server-name cannot contain semicolons.",
            }
        if len(value) > 100:
            return {
                "status": "error",
                "message": "server-name is too long (max 100 chars).",
            }
    # Validate level-name (world folder name)
    elif property_name == "level-name":
        if not re.fullmatch(r"[a-zA-Z0-9_\-]+", value.replace(" ", "_")):
            return {
                "status": "error",
                "message": "level-name: use letters, numbers, underscore, hyphen.",
            }
        if len(value) > 80:
            return {
                "status": "error",
                "message": "level-name is too long (max 80 chars).",
            }
    # Validate network ports
    elif property_name in ("server-port", "server-portv6"):
        try:
            port = int(value)
            if not (1024 <= port <= 65535):
                raise ValueError()
        except (ValueError, TypeError):
            return {
                "status": "error",
                "message": f"{property_name}: must be a number 1024-65535.",
            }
    # Validate numeric game settings
    elif property_name in ("max-players", "view-distance", "tick-distance"):
        try:
            num_val = int(value)
            if property_name == "max-players" and num_val < 1:
                raise ValueError("Must be >= 1")
            if property_name == "view-distance" and num_val < 5:
                raise ValueError("Must be >= 5")
            if property_name == "tick-distance" and not (4 <= num_val <= 12):
                raise ValueError("Must be between 4-12")
        except (ValueError, TypeError):
            range_msg = "a positive number"
            if property_name == "view-distance":
                range_msg = "a number >= 5"
            if property_name == "tick-distance":
                range_msg = "a number between 4 and 12"
            msg = f"Invalid value for '{property_name}'. Must be {range_msg}."
            return {"status": "error", "message": msg}
    # Property is valid or has no specific validation rule.
    return {"status": "success"}


@plugin_method("modify_server_properties")
def modify_server_properties(
    server_name: str,
    properties_to_update: Dict[str, str],
    restart_after_modify: bool = True,
) -> Dict[str, str]:
    """Modifies one or more properties in `server.properties`.

    This function first validates all provided properties. If validation
    passes, it uses a lifecycle manager to stop the server (if requested),
    apply the changes, and restart it.

    Args:
        server_name: The name of the server to modify.
        properties_to_update: A dictionary of key-value pairs to update.
        restart_after_modify: If True, the server will be stopped before the
            change and restarted if the change is successful. Defaults to True.

    Returns:
        A dictionary with the operation status and a message.
    """
    if not server_name:
        raise InvalidServerNameError("Server name required.")
    if not isinstance(properties_to_update, dict):
        raise TypeError("Properties must be a dict.")

    plugin_manager.trigger_event(
        "before_properties_change",
        server_name=server_name,
        properties=properties_to_update,
    )

    result = {}
    try:
        # First, validate all properties before making any changes.
        for name, val_str in properties_to_update.items():
            val_res = validate_server_property_value(
                name, str(val_str) if val_str is not None else ""
            )
            if val_res.get("status") == "error":
                raise UserInputError(
                    f"Validation failed for '{name}': {val_res.get('message')}"
                )

        # Use a context manager to handle stopping and restarting the server.
        with server_lifecycle_manager(
            server_name, stop_before=restart_after_modify, restart_on_success_only=True
        ):
            server = BedrockServer(server_name)
            for prop_name, prop_value in properties_to_update.items():
                server.set_server_property(prop_name, prop_value)

        result = {
            "status": "success",
            "message": "Server properties updated successfully.",
        }

    except (BSMError, FileNotFoundError, UserInputError) as e:
        logger.error(
            f"API: Failed to modify properties for '{server_name}': {e}", exc_info=True
        )
        result = {"status": "error", "message": f"Failed to modify properties: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error modifying properties for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Unexpected error: {e}"}
    finally:
        plugin_manager.trigger_event(
            "after_properties_change", server_name=server_name, result=result
        )

    return result


# --- INSTALL/UPDATE FUNCTIONS ---
@plugin_method("install_new_server")
def install_new_server(
    server_name: str, target_version: str = "LATEST"
) -> Dict[str, Any]:
    """Installs a new Bedrock server.

    This involves creating the server directory, downloading the specified
    version of the server software, and setting up initial configuration.

    Args:
        server_name: The name for the new server. Must be unique and follow
            filesystem naming conventions.
        target_version: The server version to install (e.g., '1.20.10.01').
            Defaults to 'LATEST'.

    Returns:
        A dictionary with the operation status, final installed version,
        and a message.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    plugin_manager.trigger_event(
        "before_server_install", server_name=server_name, target_version=target_version
    )

    result = {}
    try:
        # Perform pre-flight checks before creating anything.
        val_res = validate_server_name_format(server_name)
        if val_res.get("status") == "error":
            raise UserInputError(val_res.get("message"))

        base_dir = settings.get("BASE_DIR")
        if not base_dir:
            raise FileOperationError("BASE_DIR not configured in settings.")
        if os.path.exists(os.path.join(base_dir, server_name)):
            raise UserInputError(
                f"Directory for server '{server_name}' already exists."
            )

        logger.info(
            f"API: Installing new server '{server_name}', target version '{target_version}'."
        )
        server = BedrockServer(server_name)
        server.install_or_update(target_version)
        result = {
            "status": "success",
            "version": server.get_version(),
            "message": f"Server '{server_name}' installed successfully to version {server.get_version()}.",
        }

    except BSMError as e:
        logger.error(
            f"API: Installation failed for '{server_name}': {e}", exc_info=True
        )
        result = {"status": "error", "message": f"Server installation failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error installing '{server_name}': {e}", exc_info=True
        )
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}
    finally:
        plugin_manager.trigger_event(
            "after_server_install", server_name=server_name, result=result
        )

    return result


@plugin_method("update_server")
def update_server(server_name: str, send_message: bool = True) -> Dict[str, Any]:
    """Updates an existing server to its configured target version.

    This function checks if an update is needed. If so, it backs up all
    server data, stops the server, performs the update, and restarts it.

    Args:
        server_name: The name of the server to update.
        send_message: If True, attempts to send a notification to the running
            server before shutting down for the update. Defaults to True.

    Returns:
        A dictionary with the operation status, whether an update was
        performed, the new version, and a message.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    result = {}
    try:
        server = BedrockServer(server_name)
        target_version = server.get_target_version()

        plugin_manager.trigger_event(
            "before_server_update",
            server_name=server_name,
            target_version=target_version,
        )

        logger.info(
            f"API: Updating server '{server_name}'. Send message: {send_message}"
        )
        # Check if an update is actually necessary.
        if not server.is_update_needed(target_version):
            return {
                "status": "success",
                "updated": False,
                "message": "Server is already up-to-date.",
            }

        # Use the lifecycle manager to handle the stop/start cycle.
        with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
        ):
            logger.info(f"API: Backing up '{server_name}' before update...")
            server.backup_all_data()
            logger.info(
                f"API: Performing update for '{server_name}' to target '{target_version}'..."
            )
            server.install_or_update(target_version)

        result = {
            "status": "success",
            "updated": True,
            "new_version": server.get_version(),
            "message": f"Server '{server_name}' updated successfully to {server.get_version()}.",
        }

    except BSMError as e:
        logger.error(f"API: Update failed for '{server_name}': {e}", exc_info=True)
        result = {"status": "error", "message": f"Server update failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error updating '{server_name}': {e}", exc_info=True
        )
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}
    finally:
        plugin_manager.trigger_event(
            "after_server_update", server_name=server_name, result=result
        )

    return result
