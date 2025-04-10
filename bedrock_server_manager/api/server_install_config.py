# bedrock-server-manager/bedrock_server_manager/api/server_install_config.py
"""
Provides API-level functions for installing new Bedrock servers and configuring
existing ones (allowlist, player permissions, server properties).

This module acts as an interface layer, orchestrating calls to core server/player/download
functions and returning structured dictionary responses indicating success or failure.
"""

import os
import logging
import re
from typing import Dict, List, Optional, Any

# Local imports
from bedrock_server_manager.core.download import downloader
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.api.server import write_server_config, send_command
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.api.utils import validate_server_name_format
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
    RestoreError,
)

logger = logging.getLogger("bedrock_server_manager")


def configure_allowlist(
    server_name: str,
    base_dir: Optional[str] = None,
    new_players_data: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Configures the allowlist for a specific server. Reads the existing list and
    optionally adds new players if provided.

    Args:
        server_name: The name of the server.
        base_dir: Optional. The base directory for server installations. Uses config default if None.
        new_players_data: Optional. A list of dictionaries for new players to add.
                          Each dictionary must have 'name' (str) and should typically have
                          'ignoresPlayerLimit' (bool). Defaults to None (no players added).

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "existing_players": List[Dict], "added_players": List[Dict], "message": str}
        - {"status": "error", "message": str}

    Raises:
        MissingArgumentError: If `server_name` is empty.
        TypeError: If `new_players_data` is provided but is not a list.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if new_players_data is not None and not isinstance(new_players_data, list):
        raise TypeError("If provided, new_players_data must be a list of dictionaries.")

    logger.info(f"Configuring allowlist for server '{server_name}'.")

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_dir = os.path.join(effective_base_dir, server_name)

        # Ensure server directory exists before proceeding
        if not os.path.isdir(server_dir):
            raise DirectoryError(f"Server directory not found: {server_dir}")

        # 1. Read existing allowlist
        logger.debug("Reading existing allowlist...")
        existing_players = server_base.configure_allowlist(
            server_dir
        )  # Core function reads/returns list
        logger.debug(f"Found {len(existing_players)} players in existing allowlist.")

    except (FileOperationError, DirectoryError) as e:
        logger.error(
            f"Failed to read or access allowlist directory for server '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to access allowlist: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error reading allowlist for server '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error reading allowlist: {e}",
        }

    # 2. Process new players if provided
    added_players_list: List[Dict[str, Any]] = []
    if new_players_data:
        logger.info(
            f"Processing {len(new_players_data)} new player entries to potentially add..."
        )
        existing_names_lower = {
            p.get("name", "").lower() for p in existing_players if isinstance(p, dict)
        }
        added_names_lower = set()

        for player_entry in new_players_data:
            if (
                not isinstance(player_entry, dict)
                or not isinstance(player_entry.get("name"), str)
                or not player_entry.get("name")
            ):
                logger.warning(
                    f"Skipping invalid player entry in new_players_data (missing/invalid name): {player_entry}"
                )
                continue

            player_name = player_entry["name"]
            player_name_lower = player_name.lower()

            if player_name_lower in existing_names_lower:
                logger.debug(
                    f"Player '{player_name}' already exists in allowlist. Skipping."
                )
                continue
            if player_name_lower in added_names_lower:
                logger.debug(
                    f"Player '{player_name}' already processed in this batch. Skipping duplicate."
                )
                continue

            # Add default ignoresPlayerLimit if missing (optional, based on need)
            if "ignoresPlayerLimit" not in player_entry:
                player_entry["ignoresPlayerLimit"] = False

            added_players_list.append(player_entry)
            added_names_lower.add(player_name_lower)
            logger.debug(f"Prepared player '{player_name}' for addition.")

        # 3. Add the validated new players if any exist
        if added_players_list:
            logger.info(
                f"Adding {len(added_players_list)} new valid players to allowlist..."
            )
            try:
                # Core function handles writing the file
                server_base.add_players_to_allowlist(server_dir, added_players_list)
                message = f"Successfully added {len(added_players_list)} players to allowlist."
                logger.info(message)
                return {
                    "status": "success",
                    "existing_players": existing_players,
                    "added_players": added_players_list,
                    "message": message,
                }
            except (FileOperationError, TypeError) as e:
                logger.error(
                    f"Failed to add players to allowlist file for server '{server_name}': {e}",
                    exc_info=True,
                )
                return {"status": "error", "message": f"Error saving allowlist: {e}"}
            except Exception as e:
                logger.error(
                    f"Unexpected error adding players for server '{server_name}': {e}",
                    exc_info=True,
                )
                return {
                    "status": "error",
                    "message": f"Unexpected error saving allowlist: {e}",
                }
        else:
            message = "No new players provided or all provided players were duplicates/invalid."
            logger.info(message)
            return {
                "status": "success",
                "existing_players": existing_players,
                "added_players": [],
                "message": message,
            }
    else:
        # No new players provided, just return existing list
        message = (
            "Read existing allowlist successfully. No new players provided to add."
        )
        logger.debug(message)
        return {
            "status": "success",
            "existing_players": existing_players,
            "added_players": [],
            "message": message,
        }


def configure_player_permission(
    server_name: str,
    xuid: str,
    player_name: Optional[str],
    permission: str,
    base_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    Configures the permission level for a specific player on a server.

    Updates the `permissions.json` file within the server's directory.

    Args:
        server_name: The name of the server.
        xuid: The player's XUID string.
        player_name: Optional. The player's name (used if adding a new entry).
        permission: The desired permission level ("member", "operator", or "visitor"). Case-insensitive.
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name`, `xuid`, or `permission` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not xuid:
        raise MissingArgumentError("Player XUID cannot be empty.")
    if not permission:
        raise MissingArgumentError("Permission level cannot be empty.")
    # Core function validates permission value ("operator", "member", "visitor")

    logger.info(
        f"Configuring permission for XUID '{xuid}' on server '{server_name}' to '{permission}'."
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_dir = os.path.join(effective_base_dir, server_name)

        # Delegate to core function which handles file I/O, validation, and logic
        server_base.configure_permissions(server_dir, xuid, player_name, permission)

        logger.info(
            f"Successfully configured permission for XUID '{xuid}' on server '{server_name}'."
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
        # Catch specific errors raised by core function or path issues
        logger.error(
            f"Failed to configure permission for XUID '{xuid}' on server '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to configure permission: {e}"}
    except Exception as e:
        # Catch unexpected errors
        logger.error(
            f"Unexpected error configuring permission for XUID '{xuid}' on server '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error configuring permission: {e}",
        }


def read_server_properties(
    server_name: str, base_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Reads and parses the `server.properties` file for a given server.

    Args:
        server_name: The name of the server.
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "properties": Dict[str, str]} on success.
        - {"status": "error", "message": str} if the file is not found or cannot be read/parsed.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"Reading server.properties for server '{server_name}'...")
    properties: Dict[str, str] = {}

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_properties_path = os.path.join(
            effective_base_dir, server_name, "server.properties"
        )

        logger.debug(f"Attempting to read properties file: {server_properties_path}")
        if not os.path.isfile(server_properties_path):
            raise FileNotFoundError(
                f"server.properties file not found at: {server_properties_path}"
            )

        with open(server_properties_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Split only on the first equals sign
                parts = line.split("=", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    properties[key] = value
                else:
                    logger.warning(
                        f"Skipping malformed line {line_num} in '{server_properties_path}': {line}"
                    )

        logger.debug(
            f"Successfully read and parsed {len(properties)} properties for server '{server_name}'."
        )
        return {"status": "success", "properties": properties}

    except FileNotFoundError as e:
        logger.error(f"Could not read properties for server '{server_name}': {e}")
        return {
            "status": "error",
            "message": str(e),
        }  # Return FileNotFoundError message
    except FileOperationError as e:  # Catch error from get_base_dir
        logger.error(
            f"Configuration error preventing reading properties for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except OSError as e:
        logger.error(
            f"Failed to read server.properties file '{server_properties_path}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to read server.properties: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error reading server.properties for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error reading properties: {e}",
        }


def validate_server_property_value(property_name: str, value: str) -> Dict[str, str]:
    """
    Validates the value for common server properties based on expected format or range.

    Note: This provides basic client-side or API-level validation. The core
    `modify_server_properties` should ideally rely on the server itself for
    ultimate validation, but this can catch common errors early.

    Args:
        property_name: The name of the property being validated (e.g., "server-port").
        value: The string value to validate.

    Returns:
        `{"status": "success"}` if validation passes, or
        `{"status": "error", "message": "Validation error description..."}` if it fails.
    """
    logger.debug(
        f"Validating server property value: Property='{property_name}', Value='{value}'"
    )

    # Allow empty values for some properties? Handle None input.
    if value is None:
        value = ""

    # Example Validations (Expand as needed)
    if property_name == "server-name":
        # Minecraft allows most characters, but ';' can break parsing sometimes. Limit length?
        if ";" in value:
            msg = f"Value for '{property_name}' cannot contain semicolons."
            logger.warning(msg + f" Value: '{value}'")
            return {"status": "error", "message": msg}
        if len(value) > 100:  # Arbitrary length limit example
            msg = f"Value for '{property_name}' is excessively long (max 100 chars)."
            logger.warning(msg + f" Value: '{value[:50]}...'")
            return {"status": "error", "message": msg}

    elif property_name == "level-name":
        # Official recommendation: Avoid special characters that might cause issues on file systems.
        # Let's enforce alphanumeric, underscore, hyphen.
        if not re.fullmatch(r"[a-zA-Z0-9_\-]+", value):
            msg = f"Invalid value for '{property_name}'. Only use letters, numbers, underscore (_), and hyphen (-)."
            logger.warning(msg + f" Value: '{value}'")
            return {"status": "error", "message": msg}
        if len(value) > 80:  # Arbitrary length limit
            msg = f"Value for '{property_name}' is too long (max 80 chars)."
            logger.warning(msg + f" Value: '{value[:50]}...'")
            return {"status": "error", "message": msg}

    elif property_name in ("server-port", "server-portv6"):
        try:
            port_num = int(value)
            # Standard port range, avoiding privileged ports (<1024)
            if not (1024 <= port_num <= 65535):
                raise ValueError("Port number out of valid range.")
        except (ValueError, TypeError):
            msg = f"Invalid value for '{property_name}'. Must be a number between 1024 and 65535."
            logger.warning(msg + f" Value: '{value}'")
            return {"status": "error", "message": msg}

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
            logger.warning(msg + f" Value: '{value}'")
            return {"status": "error", "message": msg}

    logger.debug(
        f"Validation successful for Property='{property_name}', Value='{value}'"
    )
    return {"status": "success"}


def modify_server_properties(
    server_name: str,
    properties_to_update: Dict[str, str],
    base_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    Modifies one or more properties in the server's `server.properties` file.

    Performs basic validation on values before attempting to write.

    Args:
        server_name: The name of the server.
        properties_to_update: A dictionary where keys are property names and values
                              are the new string values to set.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.
        If multiple validation errors occur, only the first one encountered is returned.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        TypeError: If `properties_to_update` is not a dictionary.
        FileOperationError: If `base_dir` cannot be determined or core modification fails.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not isinstance(properties_to_update, dict):
        raise TypeError("properties_to_update must be a dictionary.")
    if not properties_to_update:
        logger.warning(f"No properties provided to modify for server '{server_name}'.")
        return {
            "status": "success",
            "message": "No properties specified for modification.",
        }

    logger.debug(
        f"Modifying server properties for server '{server_name}': {list(properties_to_update.keys())}"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_properties_path = os.path.join(
            effective_base_dir, server_name, "server.properties"
        )

        if not os.path.isfile(server_properties_path):
            raise FileNotFoundError(
                f"server.properties file not found at: {server_properties_path}"
            )

        # --- Validate all properties ---
        validation_errors = {}
        validated_properties = {}
        for prop_name, prop_value in properties_to_update.items():
            # Ensure value is string for validation and writing
            prop_value_str = str(prop_value) if prop_value is not None else ""
            validation_result = validate_server_property_value(
                prop_name, prop_value_str
            )
            if validation_result.get("status") == "error":
                validation_errors[prop_name] = validation_result.get("message")
            else:
                validated_properties[prop_name] = (
                    prop_value_str  # Store validated string value
                )

        if validation_errors:
            error_msg = "Validation failed for one or more properties: " + "; ".join(
                [f"{k}: {v}" for k, v in validation_errors.items()]
            )
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

        # --- Apply validated properties ---
        for prop_name, prop_value in validated_properties.items():
            logger.info(f"Applying change: {prop_name}={prop_value}")
            # Core function raises FileOperationError, InvalidInputError
            server_base.modify_server_properties(
                server_properties_path, prop_name, prop_value
            )

        logger.info(f"Successfully modified properties for server '{server_name}'.")
        return {
            "status": "success",
            "message": "Server properties updated successfully.",
        }

    except (FileNotFoundError, FileOperationError, InvalidInputError) as e:
        logger.error(
            f"Failed to modify server properties for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to modify properties: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error modifying server properties for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error modifying properties: {e}",
        }


def download_and_install_server(
    server_name: str,
    base_dir: Optional[str] = None,
    target_version: str = "LATEST",
    in_update: bool = False,
) -> Dict[str, Any]:
    """
    Downloads the specified Bedrock server version and installs/updates it.

    Orchestrates calls to core downloader and server installation functions.

    Args:
        server_name: The name of the server.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        target_version: Version to download ("LATEST", "PREVIEW", or specific "1.x.y.z").
        in_update: True if updating an existing server, False for a fresh install.

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "version": str, "message": str} on success.
        - {"status": "error", "message": str} on failure.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    action = "Updating" if in_update else "Installing"
    logger.debug(
        f"Starting server download and {action.lower()} process for '{server_name}', target version '{target_version}'."
    )

    try:
        effective_base_dir = get_base_dir(base_dir)
        server_dir = os.path.join(effective_base_dir, server_name)

        # 1. Download phase (core function handles checks, returns paths)
        logger.info("Step 1: Downloading server files...")
        # download_bedrock_server raises: InternetConnectivityError, DirectoryError, DownloadExtractError, FileOperationError
        actual_version, zip_file_path, _ = downloader.download_bedrock_server(
            server_dir=server_dir,  # Pass server dir (it ensures it exists)
            target_version=target_version,
        )
        logger.debug(
            f"Download complete. Version: {actual_version}, ZIP: {zip_file_path}"
        )

        # 2. Installation phase (core function handles extraction, permissions, version config)
        logger.info(f"Step 2: {action} server files...")
        # install_server raises: InstallUpdateError, FileOperationError, BackupWorldError, RestoreError, etc.
        server_base.install_server(
            server_name=server_name,
            base_dir=effective_base_dir,
            target_version=actual_version,
            zip_file_path=zip_file_path,
            server_dir=server_dir,
            is_update=in_update,
        )
        logger.info(
            f"Server {action.lower()} completed successfully for version {actual_version}."
        )

        return {
            "status": "success",
            "version": actual_version,
            "message": f"Server '{server_name}' {action.lower()} successful (Version: {actual_version}).",
        }

    # Catch specific errors from download/install phases
    except (
        DownloadExtractError,
        InternetConnectivityError,
        InstallUpdateError,
        DirectoryError,
        FileOperationError,
        BackupWorldError,
        RestoreError,
    ) as e:
        logger.error(
            f"Server download/install process failed for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Server {action.lower()} failed: {e}"}
    except FileOperationError as e:  # Catch error from get_base_dir
        logger.error(
            f"Configuration error preventing server download/install for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error during server download/install for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def install_new_server(
    server_name: str,
    target_version: str = "LATEST",
    base_dir: Optional[str] = None,
    config_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    Installs a completely new Bedrock server instance.

    Validates name, checks for existing server, writes initial config,
    downloads/installs files, and sets initial status.

    Args:
        server_name: The desired name for the new server.
        target_version: Version to install ("LATEST", "PREVIEW", or specific "1.x.y.z").
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        config_dir: Optional. Base directory for server configs. Uses default if None.

    Returns:
        A dictionary indicating the outcome: `{"status": "success", "server_name": str, "message": ...}`
        or `{"status": "error", "message": str}`.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.debug(
        f"Starting installation process for new server '{server_name}', target version '{target_version}'."
    )

    try:
        effective_base_dir = get_base_dir(base_dir)

        # --- 1. Validate Name Format ---
        validation_result = validate_server_name_format(server_name)  # Returns dict
        if validation_result.get("status") == "error":
            logger.error(
                f"Invalid server name format for '{server_name}': {validation_result.get('message')}"
            )
            return validation_result  # Return the validation error dict

        # --- 2. Check if Server Already Exists ---
        server_dir = os.path.join(effective_base_dir, server_name)
        if os.path.exists(server_dir):
            # Check if it's just an empty dir or actually contains files? For now, any existence is error.
            error_msg = (
                f"Cannot install new server: Directory '{server_dir}' already exists."
            )
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

        # --- 3. Write Initial Config (Name, Target Version) ---
        logger.debug("Writing initial server configuration...")
        config_results = []
        config_results.append(
            write_server_config(server_name, "server_name", server_name, config_dir)
        )
        config_results.append(
            write_server_config(
                server_name, "target_version", target_version, config_dir
            )
        )
        # Check if any config write failed
        for result in config_results:
            if result.get("status") == "error":
                logger.error(
                    f"Failed to write initial configuration for server '{server_name}'. Error: {result.get('message')}"
                )
                return result  # Return the first config write error

        # --- 4. Download and Install ---
        logger.debug(
            f"Proceeding with download and installation for server '{server_name}'..."
        )
        # Use the API function which returns dict
        install_result = download_and_install_server(
            server_name=server_name,
            base_dir=effective_base_dir,
            target_version=target_version,
            in_update=False,  # Explicitly False for new install
        )
        if install_result.get("status") == "error":
            logger.error(
                f"Download/installation failed for new server '{server_name}'. Error: {install_result.get('message')}"
            )
            return install_result  # Return the install error

        installed_version = install_result.get(
            "version", "UNKNOWN"
        )  # Get version from successful result

        # --- 5. Write Final Status ---
        logger.debug("Writing final status ('INSTALLED') to server configuration...")
        status_result = write_server_config(
            server_name, "status", "INSTALLED", config_dir
        )
        if status_result.get("status") == "error":
            # Installation succeeded but status write failed - log warning, but return success for install itself?
            logger.warning(
                f"Server '{server_name}' installed successfully (Version: {installed_version}), but failed to write final status to config: {status_result.get('message')}"
            )
            # Let's return success but mention the status issue
            return {
                "status": "success",
                "server_name": server_name,
                "message": f"Server '{server_name}' installed (Version: {installed_version}), but status update failed.",
            }

        logger.info(
            f"New server '{server_name}' (Version: {installed_version}) installed successfully."
        )
        return {
            "status": "success",
            "server_name": server_name,
            "version": installed_version,
            "message": f"Server '{server_name}' installed successfully (Version: {installed_version}).",
        }

    except FileOperationError as e:  # Catch error from get_base_dir
        logger.error(
            f"Configuration error preventing server installation for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        # Catch unexpected errors during orchestration
        logger.error(
            f"Unexpected error during new server installation for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error installing server: {e}",
        }


def update_server(
    server_name: str,
    base_dir: Optional[str] = None,
    send_message: bool = True,
) -> Dict[str, Any]:
    """
    Updates an existing Bedrock server to the target version specified in its config.

    Checks if an update is needed, handles download/installation, and optionally
    sends an in-game warning message if the server is running.

    Args:
        server_name: The name of the server to update.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        send_message: If True, attempt to send "say Checking for updates..." message
                      to the server if it's running.

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "updated": bool, "new_version": Optional[str], "message": str}
        - {"status": "error", "message": str}

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined or essential config cannot be read.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"Starting update check process for server '{server_name}'. Send message: {send_message}"
    )

    try:
        effective_base_dir = get_base_dir(base_dir)

        # --- Check if server is running and send message (optional) ---
        if send_message:
            try:
                if system_base.is_server_running(server_name, effective_base_dir):
                    logger.info(
                        f"Server '{server_name}' is running. Sending update check notification..."
                    )
                    # Use API send_command which returns dict
                    cmd_result = send_command(
                        server_name,
                        "say Checking for server updates...",
                        effective_base_dir,
                    )
                    if cmd_result.get("status") == "error":
                        # Log warning but don't abort update if message fails
                        logger.warning(
                            f"Failed to send update notification message to server '{server_name}': {cmd_result.get('message')}"
                        )
                    else:
                        logger.debug("Update notification sent.")
                else:
                    logger.debug(
                        f"Server '{server_name}' is not running. Skipping update notification."
                    )
            except Exception as e:
                # Catch any error during running check or message sending, log warning and continue
                logger.warning(
                    f"Could not send update notification to server '{server_name}': {e}",
                    exc_info=True,
                )

        # --- Get Installed and Target Versions ---
        logger.debug("Retrieving installed and target versions...")
        installed_version = server_base.get_installed_version(server_name)
        target_version = server_base.manage_server_config(
            server_name, "target_version", "read"
        )

        if installed_version == "UNKNOWN":
            logger.warning(
                f"Cannot determine installed version for server '{server_name}'. Assuming update is needed."
            )
            # Proceed, but download_and_install will handle actual version check logic if target is LATEST/PREVIEW
        if target_version is None:
            logger.warning(
                f"Target version not found in config for server '{server_name}'. Defaulting to 'LATEST'."
            )
            target_version = "LATEST"  # Default behavior if not set

        logger.debug(
            f"Server '{server_name}': Installed Version='{installed_version}', Target Version='{target_version}'"
        )

        # --- Check if Update is Needed ---
        if server_base.no_update_needed(server_name, installed_version, target_version):
            logger.info(
                f"Server '{server_name}' is already up-to-date (Version: {installed_version})."
            )
            return {
                "status": "success",
                "updated": False,
                "new_version": installed_version,
                "message": "Server is already up-to-date.",
            }

        # --- Perform Download and Installation (as update) ---
        logger.info(f"Proceeding with update attempt for server '{server_name}'...")
        update_result = download_and_install_server(
            server_name=server_name,
            base_dir=effective_base_dir,
            target_version=target_version,
            in_update=True,  # Explicitly True for update
        )

        # --- Process Result ---
        if update_result.get("status") == "success":
            new_version = update_result.get("version", "UNKNOWN")
            updated_flag = (
                installed_version != new_version
            )  # Set flag based on actual version change
            message = f"Server '{server_name}' update process completed. "
            if updated_flag:
                message += f"New version: {new_version}."
            else:
                message += f"Server already at target version ({installed_version})."
            logger.info(message)
            return {
                "status": "success",
                "updated": updated_flag,
                "new_version": new_version,
                "message": message,
            }
        else:
            # Update failed during download/install phase
            logger.error(
                f"Update failed for server '{server_name}'. Error: {update_result.get('message')}"
            )
            return (
                update_result  # Return the error dict from download_and_install_server
            )

    except (InvalidServerNameError, MissingArgumentError) as e:
        # Re-raise input validation errors
        raise
    except FileOperationError as e:  # Catch error from get_base_dir or core functions
        logger.error(
            f"Configuration or File error preventing server update for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration/File error: {e}"}
    except Exception as e:
        # Catch unexpected errors during orchestration
        logger.error(
            f"Unexpected error during update process for server '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error during update: {e}"}
