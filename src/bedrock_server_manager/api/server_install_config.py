# bedrock_server_manager/api/server_install_config.py
"""
Provides API-level functions for installing, updating, and configuring Bedrock servers
by orchestrating calls to BedrockServer class methods.
"""
import os
import logging
import re
from typing import Dict, List, Optional, Any

# Local imports
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
def add_players_to_allowlist_api(
    server_name: str, new_players_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """API endpoint to add new players to the allowlist for a specific server."""
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not isinstance(new_players_data, list):
        return {
            "status": "error",
            "message": "Invalid input: new_players_data must be a list.",
        }

    logger.info(
        f"API: Adding {len(new_players_data)} player(s) to allowlist for '{server_name}'."
    )
    try:
        server = BedrockServer(server_name)
        added_count = server.add_to_allowlist(new_players_data)

        if added_count > 0 and server.is_running():
            try:
                server.send_command("allowlist reload")
            except BSMError as e:
                logger.warning(
                    f"API: Allowlist updated, but failed to send reload command: {e}"
                )

        return {
            "status": "success",
            "message": f"Successfully added {added_count} new players to the allowlist.",
            "added_count": added_count,
        }
    except (FileOperationError, TypeError) as e:
        logger.error(
            f"API: Failed to update allowlist for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to update allowlist: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error updating allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error updating allowlist: {e}",
        }


def get_server_allowlist_api(server_name: str) -> Dict[str, Any]:
    """API endpoint to retrieve the allowlist for a specific server."""
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


def remove_players_from_allowlist(
    server_name: str, player_names: List[str]
) -> Dict[str, Any]:
    """
    Removes one or more players from the server's allowlist.

    Args:
        server_name: The name of the server.
        player_names: A list of player names (gamertags) to remove.

    Returns:
        A dictionary detailing the outcome of the operation.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not player_names:
        return {
            "status": "success",
            "message": "No players specified for removal.",
            "details": {"removed": [], "not_found": []},
        }

    try:
        server = BedrockServer(server_name)
        removed_players = []
        not_found_players = []

        # Process all players first
        for player in player_names:
            was_removed = server.remove_from_allowlist(player)
            if was_removed:
                removed_players.append(player)
            else:
                not_found_players.append(player)

        # If any player was actually removed and the server is running, reload the allowlist once.
        if removed_players and server.is_running():
            try:
                server.send_command("allowlist reload")
                logger.info(f"API: Sent 'allowlist reload' to server '{server_name}'.")
            except BSMError as e:
                logger.warning(
                    f"API: Players removed, but failed to send reload command: {e}"
                )

        return {
            "status": "success",
            "message": "Allowlist update process completed.",
            "details": {
                "removed": removed_players,
                "not_found": not_found_players,
            },
        }
    except BSMError as e:
        logger.error(
            f"API: Failed to remove players from allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Failed to process allowlist removal: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error removing players for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}


# --- Player Permissions ---
def configure_player_permission(
    server_name: str, xuid: str, player_name: Optional[str], permission: str
) -> Dict[str, str]:
    """Sets a player's permission level."""
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    try:
        server = BedrockServer(server_name)
        server.set_player_permission(xuid, permission, player_name)

        if server.is_running():
            try:
                server.send_command("permission reload")
            except BSMError as e:
                logger.warning(
                    f"API: Permission set, but failed to send reload command: {e}"
                )

        return {
            "status": "success",
            "message": f"Permission for XUID '{xuid}' set to '{permission.lower()}'.",
        }
    except BSMError as e:
        logger.error(
            f"API: Failed to configure permission for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to configure permission: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error configuring permission for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}


def get_server_permissions_api(server_name: str) -> Dict[str, Any]:
    """Retrieves processed permissions data for a specific server."""
    if not server_name:
        return {"status": "error", "message": "Server name cannot be empty."}

    try:
        server = BedrockServer(server_name)
        player_name_map: Dict[str, str] = {}

        # Fetch global player data for XUID-to-name mapping
        players_response = player_api.get_all_known_players_api()
        if players_response.get("status") == "success":
            for p_data in players_response.get("players", []):
                if p_data.get("xuid") and p_data.get("name"):
                    player_name_map[str(p_data["xuid"])] = str(p_data["name"])

        permissions = server.get_formatted_permissions(player_name_map)
        return {"status": "success", "data": {"permissions": permissions}}
    except AppFileNotFoundError as e:
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
def get_server_properties_api(server_name: str) -> Dict[str, Any]:
    """Reads and returns server.properties for a specific server."""
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


def validate_server_property_value(property_name: str, value: str) -> Dict[str, str]:
    """Validates a server property value. This is a stateless helper function."""
    logger.debug(
        f"API: Validating server property: '{property_name}', Value: '{value}'"
    )
    if value is None:
        value = ""
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
    return {"status": "success"}


def modify_server_properties(
    server_name: str,
    properties_to_update: Dict[str, str],
    restart_after_modify: bool = True,
) -> Dict[str, str]:
    """Modifies one or more properties in server.properties."""
    if not server_name:
        raise InvalidServerNameError("Server name required.")
    if not isinstance(properties_to_update, dict):
        raise TypeError("Properties must be a dict.")

    try:
        server = BedrockServer(server_name)

        for name, val_str in properties_to_update.items():
            val_res = validate_server_property_value(
                name, str(val_str) if val_str is not None else ""
            )
            if val_res.get("status") == "error":
                return {
                    "status": "error",
                    "message": f"Validation failed for '{name}': {val_res.get('message')}",
                }

        with server_lifecycle_manager(
            server_name, stop_before=restart_after_modify, restart_on_success_only=True
        ):
            for prop_name, prop_value in properties_to_update.items():
                server.set_server_property(prop_name, prop_value)

        return {
            "status": "success",
            "message": "Server properties updated successfully.",
        }
    except (BSMError, FileNotFoundError) as e:
        logger.error(
            f"API: Failed to modify properties for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to modify properties: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error modifying properties for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}


# --- INSTALL/UPDATE FUNCTIONS ---
def install_new_server(
    server_name: str, target_version: str = "LATEST"
) -> Dict[str, Any]:
    """Installs a new server."""
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    val_res = validate_server_name_format(server_name)
    if val_res.get("status") == "error":
        return val_res

    base_dir = settings.get("BASE_DIR")
    if not base_dir:
        raise FileOperationError("BASE_DIR not configured in settings.")
    if os.path.exists(os.path.join(base_dir, server_name)):
        return {
            "status": "error",
            "message": f"Directory for server '{server_name}' already exists.",
        }

    logger.info(
        f"API: Installing new server '{server_name}', target version '{target_version}'."
    )
    try:
        server = BedrockServer(server_name)
        server.install_or_update(target_version)
        return {
            "status": "success",
            "version": server.get_version(),
            "message": f"Server '{server_name}' installed successfully to version {server.get_version()}.",
        }
    except BSMError as e:
        logger.error(
            f"API: Installation failed for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Server installation failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error installing '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def update_server(server_name: str, send_message: bool = True) -> Dict[str, Any]:
    """Updates an existing server to its configured target version."""
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Updating server '{server_name}'. Send message: {send_message}")
    try:
        server = BedrockServer(server_name)
        target_version = (
            server.get_target_version()
        )  # Get target version from server's config

        if not server.is_update_needed(target_version):
            return {
                "status": "success",
                "updated": False,
                "message": "Server is already up-to-date.",
            }

        if send_message and server.is_running():
            try:
                server.send_command("say Server is updating now...")
            except BSMError as e:
                logger.warning(
                    f"API: Failed to send update notification to '{server_name}': {e}"
                )

        # Orchestrate backup and update
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

        return {
            "status": "success",
            "updated": True,
            "new_version": server.get_version(),
            "message": f"Server '{server_name}' updated successfully to {server.get_version()}.",
        }
    except BSMError as e:
        logger.error(f"API: Update failed for '{server_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Server update failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error updating '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
