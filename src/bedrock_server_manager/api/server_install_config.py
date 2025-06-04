# bedrock-server-manager/src/bedrock_server_manager/api/server_install_config.py
"""
Provides API-level functions for installing new Bedrock servers and configuring
existing ones (allowlist, player permissions, server properties).

This module acts as an interface layer, orchestrating calls to core server/player/download
functions and returning structured dictionary responses indicating success or failure.
"""

import os
import json
import logging
import re
from typing import Dict, List, Optional, Any

# Local imports
from bedrock_server_manager.core.downloader import BedrockDownloader
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.api.server import (
    write_server_config as api_write_server_config,
)
from bedrock_server_manager.core.server import (
    server_install_config as core_server_install_config,
    server_actions as core_server_actions,
    server_utils as core_server_utils,
)
from bedrock_server_manager.api.server import send_command as api_send_command
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.core.server import backup_restore as core_backup
from bedrock_server_manager.api.utils import (
    _server_stop_start_manager,
    validate_server_name_format,
)
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
    InstallUpdateError,
    MissingArgumentError,
    InvalidInputError,
    DirectoryError,
    BackupWorldError,
    PermissionsFileNotFoundError,
    PermissionsFileError,
    PropertiesFileNotFoundError,
    PropertiesFileReadError,
    DownloadExtractError,
    InternetConnectivityError,
)

logger = logging.getLogger(__name__)


# --- Allowlist ---
def add_players_to_allowlist_api(
    server_name: str,
    new_players_data: List[Dict[str, Any]],
    base_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    API endpoint to add new players to the allowlist for a specific server.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not isinstance(new_players_data, list):
        return {
            "status": "error",
            "message": "Invalid input: new_players_data must be a list of dictionaries.",
        }
    if not new_players_data:
        return {
            "status": "success",
            "message": "No new player data provided. Allowlist remains unchanged.",
            "added_players": [],
            "skipped_players": [],
        }

    logger.info(
        f"API: Request to add {len(new_players_data)} player(s) to allowlist for '{server_name}'."
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_dir = os.path.join(effective_base_dir, server_name)

        if not os.path.isdir(server_dir):
            raise DirectoryError(f"Server directory not found: {server_dir}")

        # 1. Read existing allowlist to determine who is new
        try:
            existing_players_before_add = core_server_install_config.read_allowlist(
                server_dir
            )
        except (FileOperationError, DirectoryError) as e:
            logger.error(
                f"API: Failed to read existing allowlist for '{server_name}' before adding: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Failed to read existing allowlist: {str(e)}",
            }

        existing_names_lower = {
            p.get("name", "").lower()
            for p in existing_players_before_add
            if isinstance(p, dict)
        }

        players_to_attempt_add: List[Dict[str, Any]] = []
        skipped_players_info: List[Dict[str, Any]] = []  # For reporting
        processed_in_this_batch_lower = (
            set()
        )  # To handle duplicates within new_players_data

        for player_entry in new_players_data:
            if (
                not isinstance(player_entry, dict)
                or not player_entry.get("name")
                or not isinstance(player_entry.get("name"), str)
            ):
                logger.warning(
                    f"API: Skipping invalid player entry format: {player_entry}"
                )
                skipped_players_info.append(
                    {"entry": player_entry, "reason": "Invalid format"}
                )
                continue

            player_name = player_entry["name"]
            player_name_lower = player_name.lower()

            if player_name_lower in existing_names_lower:
                logger.debug(
                    f"API: Player '{player_name}' already in allowlist. Skipping addition."
                )
                skipped_players_info.append(
                    {"name": player_name, "reason": "Already in allowlist"}
                )
                continue
            if player_name_lower in processed_in_this_batch_lower:
                logger.debug(
                    f"API: Player '{player_name}' was already processed in this batch. Skipping."
                )
                skipped_players_info.append(
                    {"name": player_name, "reason": "Duplicate in input batch"}
                )
                continue

            player_obj = {
                "name": player_name,
                "ignoresPlayerLimit": player_entry.get("ignoresPlayerLimit", False),
            }
            players_to_attempt_add.append(player_obj)
            processed_in_this_batch_lower.add(player_name_lower)
            logger.debug(f"API: Prepared player '{player_name}' for addition.")

        if not players_to_attempt_add:
            message = "No new valid players to add to the allowlist."
            if skipped_players_info:
                message += f" {len(skipped_players_info)} entries were skipped (duplicates or invalid)."
            logger.info(f"API: {message} For server '{server_name}'.")
            return {
                "status": "success",
                "message": message,
                "added_players": [],
                "skipped_players": skipped_players_info,
            }

        # 2. Call the core function to add the filtered new players
        core_server_install_config.add_players_to_allowlist(
            server_dir, players_to_attempt_add
        )
        logger.info(
            f"API: Successfully called core function to add {len(players_to_attempt_add)} players to allowlist for '{server_name}'."
        )

        # 3. Optionally send reload command
        reload_status = "Not attempted"
        if core_server_utils.check_if_server_is_running(server_name):
            logger.info(
                f"API: Server '{server_name}' is running. Attempting 'allowlist reload'."
            )
            cmd_res = api_send_command(
                server_name, "allowlist reload", base_dir=effective_base_dir
            )
            if cmd_res.get("status") == "error":
                reload_status = f"Failed: {cmd_res.get('message')}"
                logger.warning(
                    f"API: Failed to send 'allowlist reload' to '{server_name}': {cmd_res.get('message')}"
                )
            else:
                reload_status = "Success"
                logger.info(
                    f"API: 'allowlist reload' command sent successfully to '{server_name}'."
                )
        else:
            reload_status = "Server not running"
            logger.info(
                f"API: Server '{server_name}' is not running. 'allowlist reload' not sent."
            )

        final_message = f"Successfully processed addition request. Added {len(players_to_attempt_add)} players."
        if skipped_players_info:
            final_message += f" Skipped {len(skipped_players_info)} entries."

        return {
            "status": "success",
            "message": final_message,
            "added_players": players_to_attempt_add,  # These are the players we attempted to add
            "skipped_players": skipped_players_info,
            "reload_status": reload_status,
        }

    except (
        FileOperationError,
        DirectoryError,
        TypeError,
    ) as e:  # TypeError from core add_players
        logger.error(
            f"API: Failed to update allowlist for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to update allowlist: {str(e)}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error updating allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error updating allowlist: {str(e)}",
        }


def get_server_allowlist_api(
    server_name: str,
    base_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    API endpoint to retrieve the allowlist for a specific server.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.info(f"API: Request to get allowlist for server '{server_name}'.")

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_dir = os.path.join(effective_base_dir, server_name)

        if not os.path.isdir(server_dir):
            raise DirectoryError(f"Server directory not found: {server_dir}")

        players = core_server_install_config.read_allowlist(server_dir)
        logger.debug(
            f"API: Found {len(players)} players in allowlist for '{server_name}'."
        )
        return {
            "status": "success",
            "players": players,
            "message": f"Successfully retrieved allowlist with {len(players)} players.",
        }
    except (FileOperationError, DirectoryError) as e:
        logger.error(
            f"API: Failed to access allowlist for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to access allowlist: {str(e)}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error reading allowlist: {str(e)}",
        }


def remove_player_from_allowlist(
    server_name: str, player_name: str, base_dir: Optional[str] = None
) -> Dict[str, Any]:
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not player_name:
        raise MissingArgumentError("Player name cannot be empty.")
    logger.info(
        f"API: Removing player '{player_name}' from allowlist for '{server_name}'."
    )
    try:
        effective_base_dir = get_base_dir(base_dir)
        server_dir = os.path.join(effective_base_dir, server_name)
        if not os.path.isdir(server_dir):
            raise DirectoryError(f"Server directory not found: {server_dir}")

        was_removed = core_server_install_config.remove_player_from_allowlist(
            server_dir, player_name
        )
        if was_removed:
            if core_server_actions.check_if_server_is_running(server_name):
                cmd_res = api_send_command(server_name, "allowlist reload")
                if cmd_res.get("status") == "error":
                    logger.warning(
                        f"API: Failed to send 'whitelist reload' to '{server_name}': {cmd_res.get('message')}"
                    )
            return {
                "status": "success",
                "message": f"Player '{player_name}' removed successfully.",
            }
        else:
            return {
                "status": "success",
                "message": f"Player '{player_name}' not found in allowlist.",
            }
    except (FileOperationError, DirectoryError, MissingArgumentError) as e:
        logger.error(
            f"API: Failed to remove player from allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Failed to process allowlist removal: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error removing player for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}


# --- Player Permissions ---


def configure_player_permission(
    server_name: str,
    xuid: str,
    player_name: Optional[str],
    permission: str,
    base_dir: Optional[str] = None,
) -> Dict[str, str]:
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not xuid:
        raise MissingArgumentError("Player XUID cannot be empty.")
    if not permission:
        raise MissingArgumentError("Permission level cannot be empty.")
    logger.info(
        f"API: Configuring permission for XUID '{xuid}' on '{server_name}' to '{permission}'."
    )
    try:
        effective_base_dir = get_base_dir(base_dir)
        server_dir = os.path.join(effective_base_dir, server_name)
        core_server_install_config.configure_permissions(
            server_dir, xuid, player_name, permission
        )
        if core_server_actions.check_if_server_is_running(server_name):
            cmd_res = api_send_command(server_name, "permission reload")
            if cmd_res.get("status") == "error":
                logger.warning(
                    f"API: Failed to send 'permission reload' to '{server_name}': {cmd_res.get('message')}"
                )
        return {
            "status": "success",
            "message": f"Permission for XUID '{xuid}' set to '{permission.lower()}'.",
        }
    except (
        InvalidInputError,
        DirectoryError,
        FileOperationError,
        MissingArgumentError,
        InvalidServerNameError,
    ) as e:
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


def get_server_permissions_api(
    server_name: str,
    base_dir_override: Optional[str] = None,
    config_dir_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    API endpoint to retrieve processed permissions data for a specific server.
    """
    if not server_name:
        # This kind of basic validation is good at the API entry point
        return {"status": "error", "message": "Server name cannot be empty."}

    logger.info(f"API: Request to get server permissions for '{server_name}'.")
    api_error_messages: List[str] = []
    player_name_map: Dict[str, str] = {}

    try:
        # 1. Determine directories
        effective_server_base_dir = get_base_dir(base_dir_override)
        server_instance_dir = os.path.join(effective_server_base_dir, server_name)

        if not os.path.isdir(server_instance_dir):
            logger.warning(f"API: Server directory not found: {server_instance_dir}")
            # Using InvalidServerNameError as in original, but DirectoryNotFound from os might also be suitable
            raise InvalidServerNameError(
                f"Server directory not found: {server_instance_dir}"
            )

        # 2. Fetch global player data for XUID-to-name mapping
        effective_app_config_dir = (
            config_dir_override
            if config_dir_override is not None
            else getattr(settings, "config_dir", None)  # Safely get _config_dir
        )

        if effective_app_config_dir:
            try:
                players_response = player_api.get_players_from_json(
                    config_dir=effective_app_config_dir
                )
                if players_response.get("status") == "success":
                    for p_data in players_response.get("players", []):
                        if p_data.get("xuid") and p_data.get("name"):
                            # Ensure XUID is string for consistent map keys
                            player_name_map[str(p_data["xuid"])] = str(p_data["name"])
                    logger.debug(
                        f"API: Loaded {len(player_name_map)} players into name map."
                    )
                else:
                    msg = f"Could not load global player list: {players_response.get('message', 'Unknown player API error')}"
                    logger.warning(f"API: {msg}")
                    api_error_messages.append(msg)
            except Exception as e_players:
                msg = f"Error loading global player names: {e_players}"
                logger.error(f"API: {msg}", exc_info=True)
                api_error_messages.append(msg)
        else:
            msg = "Application configuration directory not set; cannot load global player names."
            logger.warning(f"API: {msg}")
            api_error_messages.append(msg)

        # 3. Call the core function to get processed permissions
        try:
            server_permissions_list = (
                core_server_install_config.read_and_process_permissions_file(
                    server_instance_dir, player_name_map
                )
            )
            message = "Successfully retrieved server permissions."
            if not server_permissions_list and not api_error_messages:
                message = "Server permissions file processed successfully, but no valid permission entries found or file is empty."

        except PermissionsFileNotFoundError:
            # Treat as success with empty data, as per original logic
            logger.info(
                f"API: Permissions file not found for '{server_name}', returning empty list."
            )
            server_permissions_list = []
            message = "Server permissions file not found. No permissions to display."
        except (OSError, json.JSONDecodeError, PermissionsFileError) as e_core:
            # These are errors from the core function indicating a problem with the file itself
            logger.error(
                f"API: Core function failed to process permissions file for '{server_name}': {e_core}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Failed to process server permissions file: {e_core}",
            }

        # 4. Construct final response
        if api_error_messages:
            # Prepend collected API-level errors to the main message if any
            full_message = "; ".join(api_error_messages) + (
                f"; {message}" if message else ""
            )
        else:
            full_message = message

        return {
            "status": "success",
            "data": {"permissions": server_permissions_list},
            "message": full_message,
        }

    except InvalidServerNameError as e_dir:  # Catch specific error for dir not found
        logger.error(
            f"API: Invalid server setup for '{server_name}': {e_dir}", exc_info=True
        )
        return {"status": "error", "message": str(e_dir)}
    except (
        FileOperationError
    ) as e_file_op:  # General file operation error if raised by get_base_dir etc.
        logger.error(
            f"API: File operation error for '{server_name}': {e_file_op}", exc_info=True
        )
        return {"status": "error", "message": str(e_file_op)}
    except Exception as e_unexpected:
        logger.error(
            f"API: Unexpected error for '{server_name}': {e_unexpected}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"An unexpected error occurred: {e_unexpected}",
        }


# --- Server Properties ---


def get_server_properties_api(
    server_name: str, base_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    API endpoint to read and return server.properties for a specific Bedrock server.
    """
    if not server_name:
        logger.warning("API: Call to get_server_properties_api with empty server name.")
        return {"status": "error", "message": "Server name cannot be empty."}

    logger.info(f"API: Request to read server.properties for server '{server_name}'.")

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_directory_path = os.path.join(effective_base_dir, server_name)

        # Check if the server instance directory exists first
        if not os.path.isdir(server_directory_path):
            message = f"Server directory not found: {server_directory_path}"
            logger.warning(f"API: {message} for server '{server_name}'.")
            # This indicates the server itself is not found, a higher-level issue
            raise InvalidServerNameError(message)

        server_properties_path = os.path.join(
            server_directory_path, "server.properties"
        )

        # Call the core function to parse the file
        properties_data = core_server_install_config.parse_properties_file_content(
            server_properties_path
        )

        return {"status": "success", "properties": properties_data}

    except InvalidServerNameError as e:
        # Raised if server_name is invalid or server directory doesn't exist
        logger.error(
            f"API: Invalid server setup for '{server_name}': {e}", exc_info=False
        )  # exc_info=False as it's handled
        return {"status": "error", "message": str(e)}
    except PropertiesFileNotFoundError as e:
        # Raised by core function if server.properties is missing
        logger.warning(
            f"API: server.properties not found for server '{server_name}'. Details: {e}"
        )
        return {"status": "error", "message": str(e)}  # Original was just str(e)
    except PropertiesFileReadError as e:
        # Raised by core function for OS errors during file read
        logger.error(
            f"API: Failed to read server.properties for server '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to read server.properties: {e}"}
    except FileOperationError as e:
        # Potentially raised by get_base_dir or other higher-level file ops
        logger.error(
            f"API: Configuration or File Operation error for server '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading properties for server '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error reading server properties: {e}",
        }


def validate_server_property_value(property_name: str, value: str) -> Dict[str, str]:
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
    elif property_name == "max-players":
        try:
            if int(value) < 1:
                raise ValueError()
        except (ValueError, TypeError):
            return {
                "status": "error",
                "message": "max-players: must be a positive number.",
            }

    return {"status": "success"}


def modify_server_properties(
    server_name: str,
    properties_to_update: Dict[str, str],
    base_dir: Optional[str] = None,
    restart_after_modify: bool = True,
) -> Dict[str, str]:
    if not server_name:
        raise InvalidServerNameError("Server name required.")
    if not isinstance(properties_to_update, dict):
        raise TypeError("Properties must be a dict.")
    if not properties_to_update:
        return {"status": "success", "message": "No properties specified."}

    logger.info(
        f"API: Modifying properties for '{server_name}'. Restart: {restart_after_modify}"
    )
    try:
        effective_base_dir = get_base_dir(base_dir)
        server_properties_path = os.path.join(
            effective_base_dir, server_name, "server.properties"
        )
        if not os.path.isfile(server_properties_path):
            raise FileNotFoundError(
                f"server.properties not found: {server_properties_path}"
            )

        validated_props = {}
        for name, val_str in properties_to_update.items():
            val_res = validate_server_property_value(
                name, str(val_str) if val_str is not None else ""
            )
            if val_res.get("status") == "error":
                return {
                    "status": "error",
                    "message": f"Validation failed for '{name}': {val_res.get('message')}",
                }
            validated_props[name] = str(val_str) if val_str is not None else ""

        with _server_stop_start_manager(
            server_name,
            effective_base_dir,
            stop_start_flag=restart_after_modify,
            restart_on_success_only=True,
        ):
            for prop_name, prop_value in validated_props.items():
                core_server_install_config.modify_server_properties(
                    server_properties_path, prop_name, prop_value
                )

        message = "Server properties updated."
        if restart_after_modify:
            message += (
                " Server restart handled (if it was running and properties changed)."
            )
        else:
            message += (
                " Manual server restart may be needed for changes to take effect."
            )
        return {"status": "success", "message": message}

    except (
        FileNotFoundError,
        FileOperationError,
        InvalidInputError,
        InvalidServerNameError,
    ) as e:
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


def download_and_install_server(
    server_name: str,
    base_dir: Optional[str] = None,
    target_version: str = "LATEST",
    is_update: bool = False,
) -> Dict[str, Any]:
    """
    API: Downloads the specified Bedrock server version and installs/updates it.
    This function orchestrates the entire process including stop/start for updates.
    """
    if not server_name:
        raise InvalidServerNameError(
            "Server name cannot be empty."
        )  # Or return error dict
    action = "Updating" if is_update else "Installing"
    logger.info(
        f"API: Starting server {action.lower()} process for '{server_name}', target version '{target_version}'."
    )

    app_config_dir = settings.config_dir
    if not app_config_dir:
        logger.critical(
            "API: Application configuration directory (_config_dir) not set. Cannot proceed."
        )
        return {
            "status": "error",
            "message": "Application configuration error: _config_dir not set.",
        }

    downloader_instance: Optional[BedrockDownloader] = None  # To hold the instance

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_dir = os.path.join(effective_base_dir, server_name)

        # --- 1. Initialize Downloader and Prepare Assets ---
        logger.info(
            f"API: Step 1 - Preparing download for server '{server_name}' target '{target_version}'..."
        )
        downloader_instance = BedrockDownloader(
            settings_obj=settings,  # Pass the global settings
            server_dir=server_dir,
            target_version=target_version,
        )
        actual_version, zip_file_path, _ = downloader_instance.prepare_download_assets()
        logger.debug(
            f"API: Download assets prepared. Actual Version: {actual_version}, ZIP: {zip_file_path}"
        )

        # --- 2. Orchestrate Stop, Backup (if update), File Setup, Start ---
        with _server_stop_start_manager(
            server_name,
            effective_base_dir,
            stop_start_flag=is_update,
            restart_on_success_only=True,
        ):
            if is_update:
                logger.info(
                    f"API: Step 2a - Backing up server '{server_name}' before update..."
                )

                core_backup.backup_all_server_data(
                    server_name, effective_base_dir, config_dir=app_config_dir
                )
                logger.info(f"API: Pre-update backup for '{server_name}' successful.")

            logger.info(
                f"API: Step 2b - Setting up server files from '{os.path.basename(zip_file_path)}'..."
            )
            # Pass the downloader_instance to setup_server_files
            core_server_install_config.setup_server_files(
                downloader_instance=downloader_instance,  # Key change here
                is_update=is_update,
            )
            logger.info("API: Server file setup successful.")

            # --- 3. Finalizing Configuration ---
            logger.info(
                f"API: Step 3 - Writing version '{actual_version}' and status for '{server_name}'."
            )
            core_server_install_config._write_version_config(
                server_name, actual_version, config_dir=app_config_dir
            )

            status_to_set = (
                "INSTALLED" if not is_update else "STOPPED"
            )  # STOPPED because context manager handles restart
            core_server_utils.manage_server_config(
                server_name, "status", "write", status_to_set, config_dir=app_config_dir
            )

        final_message = f"Server '{server_name}' {action.lower()} to version {actual_version} successful."
        if is_update:
            final_message += " Server restart handled if it was previously running."

        logger.info(
            f"API: Server {action.lower()} for '{server_name}' (v{actual_version}) orchestrated successfully."
        )
        return {
            "status": "success",
            "version": actual_version,
            "message": final_message,
        }

    except (
        DownloadExtractError,  # From BedrockDownloader
        InternetConnectivityError,  # From BedrockDownloader
        InstallUpdateError,  # From setup_server_files
        DirectoryError,  # From BedrockDownloader or path utils
        FileOperationError,  # From BedrockDownloader, setup_server_files, backup
        BackupWorldError,  # From core_backup
        MissingArgumentError,  # From BedrockDownloader or other core functions
        InvalidServerNameError,
        OSError,  # Can be from BedrockDownloader's network/file ops
    ) as e:
        logger.error(
            f"API: Server {action.lower()} process failed for '{server_name}': {e}",
            exc_info=True,
        )
        try:
            if app_config_dir:
                core_server_utils.manage_server_config(
                    server_name, "status", "write", "ERROR", config_dir=app_config_dir
                )
        except Exception as e_cfg:
            logger.error(
                f"API: Additionally failed to set error status for '{server_name}': {e_cfg}"
            )
        return {"status": "error", "message": f"Server {action.lower()} failed: {e}"}
    except Exception as e:
        logger.critical(
            f"API: CRITICAL UNEXPECTED error during server {action.lower()} for '{server_name}': {e}",
            exc_info=True,
        )
        try:
            if app_config_dir:
                core_server_utils.manage_server_config(
                    server_name, "status", "write", "ERROR", config_dir=app_config_dir
                )
        except Exception as e_cfg:
            logger.error(
                f"API: Additionally failed to set error status for '{server_name}': {e_cfg}"
            )
        return {
            "status": "error",
            "message": f"An critical unexpected error occurred: {e}",
        }


def install_new_server(
    server_name: str,
    target_version: str = "LATEST",
    base_dir: Optional[str] = None,
) -> Dict[str, Any]:
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    logger.info(
        f"API: Installing new server '{server_name}', target version '{target_version}'."
    )

    app_config_dir = settings.config_dir
    if not app_config_dir:
        logger.critical(
            "API: Application configuration directory (_config_dir) not set. Cannot install."
        )
        return {
            "status": "error",
            "message": "Application configuration error: _config_dir not set.",
        }

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_dir_check = os.path.join(effective_base_dir, server_name)

        validation_result = validate_server_name_format(server_name)
        if validation_result.get("status") == "error":
            return validation_result

        if os.path.exists(server_dir_check):
            return {
                "status": "error",
                "message": f"Directory '{server_dir_check}' already exists.",
            }

        init_configs = {
            "server_name": server_name,
            "target_version": target_version,
            "status": "INSTALLING",
        }
        for key, value in init_configs.items():
            cfg_res = api_write_server_config(
                server_name, key, value, config_dir=app_config_dir
            )
            if cfg_res.get("status") == "error":
                logger.error(
                    f"API: Failed to write initial config '{key}' for '{server_name}': {cfg_res.get('message')}"
                )
                return {
                    "status": "error",
                    "message": f"Initial config write failed for '{key}': {cfg_res.get('message')}",
                }

        # Call the main orchestrator
        install_result = download_and_install_server(
            server_name=server_name,
            base_dir=effective_base_dir,  # Pass the resolved base_dir
            target_version=target_version,
            is_update=False,  # Explicitly False for new install
        )
        return install_result

    except (
        MissingArgumentError,
        FileOperationError,
        InvalidServerNameError,
        DirectoryError,
    ) as e:
        logger.error(
            f"API: Setup error for new server '{server_name}': {e}", exc_info=True
        )
        try:
            if app_config_dir:
                core_server_utils.manage_server_config(
                    server_name, "status", "write", "ERROR", config_dir=app_config_dir
                )
        except Exception as e_cfg:
            logger.error(
                f"API: Additionally failed to set error status for '{server_name}': {e_cfg}"
            )
        return {
            "status": "error",
            "message": f"Setup error for new server: {e}",
        }  # Return type Dict[str, Any]
    except Exception as e:
        logger.critical(
            f"API: CRITICAL UNEXPECTED error installing new server '{server_name}': {e}",
            exc_info=True,
        )
        try:
            if app_config_dir:
                core_server_utils.manage_server_config(
                    server_name, "status", "write", "ERROR", config_dir=app_config_dir
                )
        except Exception as e_cfg:
            logger.error(
                f"API: Additionally failed to set error status for '{server_name}': {e_cfg}"
            )
        return {
            "status": "error",
            "message": f"An critical unexpected error occurred installing new server: {e}",
        }


def update_server(
    server_name: str, base_dir: Optional[str] = None, send_message: bool = True
) -> Dict[str, Any]:
    if not server_name:
        raise InvalidServerNameError(
            "Server name cannot be empty."
        )  # Or return error dict
    logger.info(f"API: Updating server '{server_name}'. Send message: {send_message}")

    app_config_dir = settings.config_dir
    if not app_config_dir:
        logger.critical(
            "API: Application configuration directory (_config_dir) not set. Cannot update."
        )
        return {
            "status": "error",
            "message": "Application configuration error: _config_dir not set.",
        }

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_dir = os.path.join(
            effective_base_dir, server_name
        )  # Needed for no_update_needed

        # Send initial message if server is running
        if send_message and core_server_actions.check_if_server_is_running(server_name):
            logger.info(
                f"API: Server '{server_name}' running. Sending update check notification..."
            )
            api_send_command(
                server_name, "say Checking for server updates..."
            )  # Fire and forget for notification

        installed_version = core_server_utils.get_installed_version(
            server_name, config_dir=app_config_dir
        )
        target_version_cfg = core_server_utils.manage_server_config(
            server_name, "target_version", "read", config_dir=app_config_dir
        )
        target_version_to_use = (
            str(target_version_cfg) if target_version_cfg is not None else "LATEST"
        )
        if target_version_cfg is None:
            logger.warning(
                f"API: Target version not set for '{server_name}', defaulting to 'LATEST'."
            )

        # Use the refactored no_update_needed
        if core_server_install_config.no_update_needed(
            settings_obj=settings,
            server_name=server_name,
            server_dir=server_dir,
            installed_version=installed_version,
            target_version_spec=target_version_to_use,
        ):
            logger.info(
                f"API: Server '{server_name}' (v{installed_version}) is already up-to-date with target '{target_version_to_use}'."
            )
            return {
                "status": "success",
                "updated": False,
                "new_version": installed_version,
                "message": "Server is already up-to-date.",
            }

        # Send "installing update" message if running
        if send_message and core_server_actions.check_if_server_is_running(server_name):
            api_send_command(
                server_name, "say Server is updating now..."
            )  # Fire and forget

        # Call the main orchestrator with is_update=True
        update_result = download_and_install_server(
            server_name=server_name,
            base_dir=effective_base_dir,
            target_version=target_version_to_use,
            is_update=True,
        )

        if update_result.get("status") == "success":
            new_actual_version = update_result.get(
                "version", "UNKNOWN"
            )  # Get version from result
            return {
                "status": "success",
                "updated": installed_version
                != new_actual_version,  # Compare old installed with new actual
                "new_version": new_actual_version,
                "message": update_result.get(
                    "message",
                    f"Server '{server_name}' updated to {new_actual_version}.",
                ),
            }
        else:
            return (
                update_result  # Propagate error result from download_and_install_server
            )

    except (
        FileOperationError,
        InvalidServerNameError,
        MissingArgumentError,
        DirectoryError,
        InternetConnectivityError,
        DownloadExtractError,
        OSError,
    ) as e:
        logger.error(
            f"API: Setup error for server update '{server_name}': {e}", exc_info=True
        )
        try:
            if app_config_dir:
                core_server_utils.manage_server_config(
                    server_name, "status", "write", "ERROR", config_dir=app_config_dir
                )
        except Exception as e_cfg:
            logger.error(
                f"API: Additionally failed to set error status for '{server_name}': {e_cfg}"
            )
        return {"status": "error", "message": f"Setup error for update: {e}"}
    except Exception as e:
        logger.critical(
            f"API: CRITICAL UNEXPECTED error updating server '{server_name}': {e}",
            exc_info=True,
        )
        try:
            if app_config_dir:
                core_server_utils.manage_server_config(
                    server_name, "status", "write", "ERROR", config_dir=app_config_dir
                )
        except Exception as e_cfg:
            logger.error(
                f"API: Additionally failed to set error status for '{server_name}': {e_cfg}"
            )
        return {
            "status": "error",
            "message": f"An critical unexpected error occurred updating server: {e}",
        }
