# bedrock-server-manager/bedrock_server_manager/api/server_install_config.py
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
from bedrock_server_manager.core import downloader as core_downloader
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.api.server import (
    write_server_config as api_write_server_config,
)
from bedrock_server_manager.api.server import send_command as api_send_command
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.core.server import server as core_server_base
from bedrock_server_manager.core.server import backup as core_backup
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
    DownloadExtractError,
    InternetConnectivityError,
    BackupWorldError,
)

logger = logging.getLogger("bedrock_server_manager")


# --- Functions from your previous version (Allowlist, Permissions, Properties Read/Validate) ---


def configure_allowlist(
    server_name: str,
    base_dir: Optional[str] = None,
    new_players_data: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Configures the allowlist for a specific server. Reads the existing list and
    optionally adds new players if provided.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if new_players_data is not None and not isinstance(new_players_data, list):
        raise TypeError("If provided, new_players_data must be a list of dictionaries.")

    logger.info(f"API: Configuring allowlist for server '{server_name}'.")

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_dir = os.path.join(effective_base_dir, server_name)

        if not os.path.isdir(server_dir):
            raise DirectoryError(f"Server directory not found: {server_dir}")

        existing_players = core_server_base.configure_allowlist(server_dir)
        logger.debug(
            f"API: Found {len(existing_players)} players in existing allowlist."
        )

    except (FileOperationError, DirectoryError) as e:
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

    added_players_list_final: List[Dict[str, Any]] = []
    if new_players_data:
        logger.info(
            f"API: Processing {len(new_players_data)} new player entries for '{server_name}'..."
        )
        existing_names_lower = {
            p.get("name", "").lower() for p in existing_players if isinstance(p, dict)
        }
        processed_in_batch = set()

        for player_entry in new_players_data:
            if (
                not isinstance(player_entry, dict)
                or not player_entry.get("name")
                or not isinstance(player_entry.get("name"), str)
            ):
                logger.warning(f"API: Skipping invalid player entry: {player_entry}")
                continue
            player_name = player_entry["name"]
            player_name_lower = player_name.lower()
            if (
                player_name_lower in existing_names_lower
                or player_name_lower in processed_in_batch
            ):
                logger.debug(
                    f"API: Player '{player_name}' already exists or processed. Skipping."
                )
                continue

            player_obj = {
                "name": player_name,
                "ignoresPlayerLimit": player_entry.get("ignoresPlayerLimit", False),
            }
            added_players_list_final.append(player_obj)
            processed_in_batch.add(player_name_lower)
            logger.debug(f"API: Prepared player '{player_name}' for addition.")

        if added_players_list_final:
            logger.info(
                f"API: Adding {len(added_players_list_final)} new players to allowlist for '{server_name}'..."
            )
            try:
                core_server_base.add_players_to_allowlist(
                    server_dir, added_players_list_final
                )
                # Optionally send reload command
                if core_server_base.check_if_server_is_running(
                    server_name
                ):  # Pass base_dir if needed
                    cmd_res = api_send_command(server_name, "allowlist reload")
                    if cmd_res.get("status") == "error":
                        logger.warning(
                            f"API: Failed to send 'allowlist reload' to '{server_name}': {cmd_res.get('message')}"
                        )

                message = f"Successfully added {len(added_players_list_final)} players."
                return {
                    "status": "success",
                    "existing_players": existing_players,
                    "added_players": added_players_list_final,
                    "message": message,
                }
            except (FileOperationError, TypeError) as e:
                logger.error(
                    f"API: Failed to save allowlist for '{server_name}': {e}",
                    exc_info=True,
                )
                return {"status": "error", "message": f"Error saving allowlist: {e}"}
        else:
            message = "No new valid players to add."
            return {
                "status": "success",
                "existing_players": existing_players,
                "added_players": [],
                "message": message,
            }
    else:
        message = "Read existing allowlist. No new players provided."
        return {
            "status": "success",
            "existing_players": existing_players,
            "added_players": [],
            "message": message,
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

        was_removed = core_server_base.remove_player_from_allowlist(
            server_dir, player_name
        )
        if was_removed:
            if core_server_base.check_if_server_is_running(server_name):
                cmd_res = api_send_command(server_name, "whitelist reload")
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
        core_server_base.configure_permissions(
            server_dir, xuid, player_name, permission
        )
        if core_server_base.check_if_server_is_running(server_name):
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


def get_server_permissions_data(
    server_name: str,
    base_dir_override: Optional[str] = None,
    config_dir_override: Optional[str] = None,
) -> Dict[str, Any]:
    if not server_name:
        return {"status": "error", "message": "Server name cannot be empty."}
    logger.info(f"API: Getting server permissions data for server '{server_name}'.")
    server_permissions_list_for_ui: List[Dict[str, Any]] = []
    error_messages = []
    player_name_map: Dict[str, str] = {}
    try:
        effective_server_base_dir = get_base_dir(base_dir_override)
        server_instance_dir = os.path.join(effective_server_base_dir, server_name)
        if not os.path.isdir(server_instance_dir):
            raise InvalidServerNameError(
                f"Server directory not found: {server_instance_dir}"
            )
        try:
            effective_app_config_dir = (
                config_dir_override
                if config_dir_override is not None
                else getattr(settings, "_config_dir", None)
            )
            if effective_app_config_dir:
                players_response = player_api.get_players_from_json(
                    config_dir=effective_app_config_dir
                )
                if players_response.get("status") == "success":
                    for p_data in players_response.get("players", []):
                        if p_data.get("xuid") and p_data.get("name"):
                            player_name_map[str(p_data["xuid"])] = str(p_data["name"])
                else:
                    error_messages.append(
                        f"Could not load global player list: {players_response.get('message')}"
                    )
        except Exception as e_players:
            error_messages.append(f"Error loading global player names: {e_players}")
        permissions_file_path = os.path.join(server_instance_dir, "permissions.json")
        if not os.path.isfile(permissions_file_path):
            return {
                "status": "success",
                "data": {"permissions": []},
                "message": "Server permissions file not found.",
            }
        try:
            with open(permissions_file_path, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                return {
                    "status": "success",
                    "data": {"permissions": []},
                    "message": "Server permissions file is empty.",
                }
            permissions_from_file = json.loads(content)
            if not isinstance(permissions_from_file, list):
                raise ValueError("Permissions file not a list.")
            for entry in permissions_from_file:
                if (
                    isinstance(entry, dict)
                    and "xuid" in entry
                    and "permission" in entry
                ):
                    xuid_str = str(entry["xuid"])
                    name = player_name_map.get(xuid_str, f"Unknown (XUID: {xuid_str})")
                    server_permissions_list_for_ui.append(
                        {
                            "xuid": xuid_str,
                            "name": name,
                            "permission_level": str(entry["permission"]),
                        }
                    )
                else:
                    logger.warning(
                        f"API: Skipping malformed entry in '{permissions_file_path}': {entry}"
                    )
        except (OSError, json.JSONDecodeError, ValueError) as e:
            return {
                "status": "error",
                "message": f"Failed to process server permissions file: {e}",
            }
        server_permissions_list_for_ui.sort(key=lambda p: p.get("name", "").lower())
        final_message = (
            "; ".join(error_messages)
            if error_messages
            else "Successfully retrieved server permissions."
        )
        return {
            "status": "success",
            "data": {"permissions": server_permissions_list_for_ui},
            "message": (
                final_message
                if error_messages or not server_permissions_list_for_ui
                else None
            ),
        }
    except (FileOperationError, InvalidServerNameError) as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def read_server_properties(
    server_name: str, base_dir: Optional[str] = None
) -> Dict[str, Any]:
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    logger.debug(f"API: Reading server.properties for server '{server_name}'...")
    properties: Dict[str, str] = {}
    try:
        effective_base_dir = get_base_dir(base_dir)
        server_properties_path = os.path.join(
            effective_base_dir, server_name, "server.properties"
        )
        if not os.path.isfile(server_properties_path):
            raise FileNotFoundError(
                f"server.properties not found: {server_properties_path}"
            )
        with open(server_properties_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("=", 1)
                if len(parts) == 2:
                    properties[parts[0].strip()] = parts[1].strip()
                else:
                    logger.warning(
                        f"API: Skipping malformed line {line_num} in '{server_properties_path}': {line}"
                    )
        return {"status": "success", "properties": properties}
    except FileNotFoundError as e:
        return {"status": "error", "message": str(e)}
    except FileOperationError as e:
        return {"status": "error", "message": f"Configuration error: {e}"}
    except OSError as e:
        return {"status": "error", "message": f"Failed to read server.properties: {e}"}
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error reading properties: {e}",
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
        if not re.fullmatch(r"[a-zA-Z0-9_\-]+", value):
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
                core_server_base.modify_server_properties(
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
        raise InvalidServerNameError("Server name cannot be empty.")
    action = "Updating" if is_update else "Installing"
    logger.info(
        f"API: Starting server {action.lower()} process for '{server_name}', target version '{target_version}'."
    )

    # Define app_config_dir early for use in error handlers if needed
    app_config_dir = settings._config_dir
    if not app_config_dir:
        # This is a critical configuration error
        logger.critical(
            "API: Application configuration directory (_config_dir) not set in settings. Cannot proceed."
        )
        return {
            "status": "error",
            "message": "Application configuration error: _config_dir not set.",
        }

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_dir = os.path.join(effective_base_dir, server_name)

        # --- 1. Download Phase ---
        logger.info("API: Step 1 - Downloading server software...")
        actual_version, zip_file_path, _ = core_downloader.download_bedrock_server(
            server_dir=server_dir, target_version=target_version
        )
        logger.debug(
            f"API: Download complete. Version: {actual_version}, ZIP: {zip_file_path}"
        )

        # --- 2. Orchestrate Stop, Backup (if update), File Setup, Start ---
        with _server_stop_start_manager(
            server_name,
            effective_base_dir,
            stop_start_flag=is_update,
            restart_on_success_only=True,  # Only restart if backup & setup are fine
        ):
            if is_update:
                logger.info(
                    f"API: Step 2a - Backing up server '{server_name}' before update..."
                )
                core_backup.backup_all_server_data(server_name, effective_base_dir)
                logger.info(f"API: Pre-update backup for '{server_name}' successful.")

            logger.info(
                f"API: Step 2b - Setting up server files from '{os.path.basename(zip_file_path)}'..."
            )
            core_server_base.setup_server_files(
                zip_file_path=zip_file_path, server_dir=server_dir, is_update=is_update
            )
            logger.info("API: Server file setup successful.")

            # --- 3. Finalizing Configuration ---
            logger.info(
                f"API: Step 3 - Writing version '{actual_version}' and status for '{server_name}'."
            )
            core_server_base._write_version_config(
                server_name, actual_version, config_dir=app_config_dir
            )

            if not is_update:
                core_server_base.manage_server_config(
                    server_name,
                    "status",
                    "write",
                    "INSTALLED",
                    config_dir=app_config_dir,
                )
            else:  # For updates, server is currently stopped by context manager.
                # If it was running, context manager's 'finally' will restart it.
                # core_server_base.start_server called by API start will set status to RUNNING.
                # If it wasn't running, it should remain STOPPED.
                core_server_base.manage_server_config(
                    server_name, "status", "write", "STOPPED", config_dir=app_config_dir
                )

        # Message after context manager, reflecting potential restart
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
        core_downloader.DownloadExtractError,
        core_downloader.InternetConnectivityError,
        InstallUpdateError,
        DirectoryError,
        FileOperationError,
        BackupWorldError,
        MissingArgumentError,
        InvalidServerNameError,
    ) as e:
        logger.error(
            f"API: Server {action.lower()} process failed for '{server_name}': {e}",
            exc_info=True,
        )
        try:
            if app_config_dir:  # Check if app_config_dir was resolved
                core_server_base.manage_server_config(
                    server_name, "status", "write", "ERROR", config_dir=app_config_dir
                )
        except Exception as e_cfg:
            logger.error(
                f"API: Additionally failed to set error status for '{server_name}': {e_cfg}"
            )
        return {"status": "error", "message": f"Server {action.lower()} failed: {e}"}
    except Exception as e:  # Catch-all for truly unexpected issues
        logger.critical(
            f"API: CRITICAL UNEXPECTED error during server {action.lower()} for '{server_name}': {e}",
            exc_info=True,
        )
        try:
            if app_config_dir:
                core_server_base.manage_server_config(
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
    config_dir: Optional[str] = None,
) -> Dict[str, str]:
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    logger.info(
        f"API: Installing new server '{server_name}', target version '{target_version}'."
    )

    # Define app_config_dir early for consistent use
    effective_app_config_dir = (
        config_dir if config_dir is not None else settings._config_dir
    )
    if not effective_app_config_dir:
        logger.critical(
            "API: Application configuration directory (_config_dir) not set. Cannot install new server."
        )
        return {
            "status": "error",
            "message": "Application configuration error: _config_dir not set.",
        }

    try:
        effective_base_dir = get_base_dir(base_dir)

        validation_result = validate_server_name_format(server_name)
        if validation_result.get("status") == "error":
            return validation_result

        server_dir_check = os.path.join(effective_base_dir, server_name)
        if os.path.exists(server_dir_check):
            return {
                "status": "error",
                "message": f"Directory '{server_dir_check}' already exists.",
            }

        # Write initial config (name, target version, initial status)
        # Use api_write_server_config as it returns dicts, easy to check status
        init_configs = {
            "server_name": server_name,
            "target_version": target_version,
            "status": "INSTALLING",  # Initial status before download
        }
        for key, value in init_configs.items():
            cfg_res = api_write_server_config(
                server_name, key, value, config_dir=effective_app_config_dir
            )
            if cfg_res.get("status") == "error":
                logger.error(
                    f"API: Failed to write initial config '{key}' for '{server_name}': {cfg_res.get('message')}"
                )
                return {
                    "status": "error",
                    "message": f"Initial config write failed for '{key}': {cfg_res.get('message')}",
                }

        # Call the main orchestrator for download and file setup
        # is_update=False means _server_stop_start_manager will effectively be a no-op for stop/start
        install_result = download_and_install_server(
            server_name=server_name,
            base_dir=effective_base_dir,
            target_version=target_version,
            is_update=False,
        )

        # download_and_install_server will set status to "INSTALLED" on success for new install.
        return install_result  # Return the result from the main orchestrator

    except (MissingArgumentError, FileOperationError, InvalidServerNameError) as e:
        logger.error(
            f"API: Setup error for new server '{server_name}': {e}", exc_info=True
        )
        # Attempt to set server status to ERROR in config
        try:
            if effective_app_config_dir:
                core_server_base.manage_server_config(
                    server_name,
                    "status",
                    "write",
                    "ERROR",
                    config_dir=effective_app_config_dir,
                )
        except Exception as e_cfg:
            logger.error(
                f"API: Additionally failed to set error status for '{server_name}': {e_cfg}"
            )
        return {"status": "error", "message": f"Setup error for new server: {e}"}
    except Exception as e:
        logger.critical(
            f"API: CRITICAL UNEXPECTED error installing new server '{server_name}': {e}",
            exc_info=True,
        )
        try:
            if effective_app_config_dir:
                core_server_base.manage_server_config(
                    server_name,
                    "status",
                    "write",
                    "ERROR",
                    config_dir=effective_app_config_dir,
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
        raise InvalidServerNameError("Server name cannot be empty.")
    logger.info(f"API: Updating server '{server_name}'. Send message: {send_message}")

    # Define app_config_dir early
    effective_app_config_dir = settings._config_dir
    if not effective_app_config_dir:
        logger.critical(
            "API: Application configuration directory (_config_dir) not set. Cannot update server."
        )
        return {
            "status": "error",
            "message": "Application configuration error: _config_dir not set.",
        }

    try:
        effective_base_dir = get_base_dir(base_dir)

        if send_message and core_server_base.check_if_server_is_running(
            server_name
        ):  # Pass base_dir if core func needs it
            logger.info(
                f"API: Server '{server_name}' running. Sending update check notification..."
            )
            cmd_res = api_send_command(
                server_name, "say Checking for server updates..."
            )
            if cmd_res.get("status") == "error":
                logger.warning(
                    f"API: Failed to send update notification to '{server_name}': {cmd_res.get('message')}"
                )

        installed_version = core_server_base.get_installed_version(
            server_name, config_dir=effective_app_config_dir
        )
        target_version_cfg = core_server_base.manage_server_config(
            server_name, "target_version", "read", config_dir=effective_app_config_dir
        )

        target_version_to_use = (
            str(target_version_cfg) if target_version_cfg is not None else "LATEST"
        )
        if target_version_cfg is None:
            logger.warning(
                f"API: Target version not set for '{server_name}', defaulting to 'LATEST'."
            )

        if core_server_base.no_update_needed(
            server_name, installed_version, target_version_to_use
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

        # Call the main orchestrator for download and file setup, with is_update=True
        update_result = download_and_install_server(
            server_name=server_name,
            base_dir=effective_base_dir,
            target_version=target_version_to_use,
            is_update=True,
        )

        # download_and_install_server's message already reflects success and version.
        # We just need to adjust the 'updated' flag logic if needed, but it's better if
        # download_and_install_server's response is comprehensive.
        if update_result.get("status") == "success":
            new_actual_version = update_result.get("version", "UNKNOWN")
            return {
                "status": "success",
                "updated": installed_version
                != new_actual_version,  # Compare old installed with new actual
                "new_version": new_actual_version,
                "message": update_result.get(
                    "message",
                    f"Server '{server_name}' update process completed. New version: {new_actual_version}.",
                ),
            }
        else:
            return update_result

    except (FileOperationError, InvalidServerNameError, MissingArgumentError) as e:
        logger.error(
            f"API: Setup error for server update '{server_name}': {e}", exc_info=True
        )
        try:
            if effective_app_config_dir:
                core_server_base.manage_server_config(
                    server_name,
                    "status",
                    "write",
                    "ERROR",
                    config_dir=effective_app_config_dir,
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
            if effective_app_config_dir:
                core_server_base.manage_server_config(
                    server_name,
                    "status",
                    "write",
                    "ERROR",
                    config_dir=effective_app_config_dir,
                )
        except Exception as e_cfg:
            logger.error(
                f"API: Additionally failed to set error status for '{server_name}': {e_cfg}"
            )
        return {
            "status": "error",
            "message": f"An critical unexpected error occurred updating server: {e}",
        }
