# bedrock-server-manager/bedrock_server_manager/core/server/server_install_config.py
"""
Core module for managing Bedrock server instances.
"""

import os
import logging
import json
import platform
from typing import Optional, Any, Dict, List

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.core.server import server_utils as core_server_utils
from bedrock_server_manager.error import (
    InvalidServerNameError,
    MissingArgumentError,
    FileOperationError,
    InvalidInputError,
    DirectoryError,
    InstallUpdateError,
    DownloadExtractError,
    InternetConnectivityError,
    PermissionsFileNotFoundError,
    PermissionsFileError,
    PropertiesFileNotFoundError,
    PropertiesFileReadError,
)
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
    windows as system_windows,
)
from bedrock_server_manager.core.downloader import BedrockDownloader


logger = logging.getLogger("bedrock_server_manager")


# --- ALLOWLIST ---


def read_allowlist(server_dir: str) -> list:
    """
    Loads and returns the current content of the server's allowlist.json file.

    Args:
        server_dir: The full path to the server's installation directory.

    Returns:
        A list of player entries (dictionaries) currently in the allowlist.
        Returns an empty list if the file doesn't exist.

    Raises:
        MissingArgumentError: If `server_dir` is empty.
        DirectoryError: If `server_dir` does not exist or is not a directory.
        FileOperationError: If reading or parsing `allowlist.json` fails.
    """
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")
    if not os.path.isdir(server_dir):
        raise DirectoryError(f"Server directory not found: {server_dir}")

    allowlist_file = os.path.join(server_dir, "allowlist.json")
    logger.debug(f"Loading allowlist file: {allowlist_file}")

    existing_players = []
    if os.path.exists(allowlist_file):
        try:
            with open(allowlist_file, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():  # Check if not empty
                    existing_players = json.loads(content)
                    if not isinstance(existing_players, list):
                        logger.warning(
                            f"Allowlist file '{allowlist_file}' does not contain a JSON list. Treating as empty."
                        )
                        existing_players = []
                    else:
                        logger.debug(
                            f"Loaded {len(existing_players)} players from allowlist.json."
                        )
                else:
                    logger.debug("Allowlist file exists but is empty.")
                    existing_players = []
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON from allowlist file '{allowlist_file}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Invalid JSON in allowlist file: {allowlist_file}"
            ) from e
        except OSError as e:
            logger.error(
                f"Failed to read allowlist file '{allowlist_file}': {e}", exc_info=True
            )
            raise FileOperationError(
                f"Failed to read allowlist file: {allowlist_file}"
            ) from e
    else:
        logger.debug("Allowlist file does not exist. Returning empty list.")

    return existing_players


def add_players_to_allowlist(
    server_dir: str, new_players: list[Dict[str, Any]]
) -> None:
    """
    Adds one or more players to the server's allowlist.json file.

    Avoids adding duplicate players based on the 'name' key.

    Args:
        server_dir: The full path to the server's installation directory.
        new_players: A list of dictionaries, where each dictionary represents a player
                     and must contain at least a 'name' key (string). Other keys like
                     'ignoresPlayerLimit' (boolean) are typically included.

    Raises:
        MissingArgumentError: If `server_dir` is empty.
        TypeError: If `new_players` is not a list or contains non-dictionary items,
                   or if a player dict lacks a 'name'.
        DirectoryError: If `server_dir` does not exist or is not a directory.
        FileOperationError: If reading or writing `allowlist.json` fails.
    """
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")
    if not os.path.isdir(server_dir):
        raise DirectoryError(f"Server directory not found: {server_dir}")
    if not isinstance(new_players, list):
        raise TypeError("Input 'new_players' must be a list.")

    allowlist_file = os.path.join(server_dir, "allowlist.json")
    logger.info(f"Adding {len(new_players)} player(s) to allowlist: {allowlist_file}")

    try:
        # Load existing players first
        existing_players = read_allowlist(server_dir)  # Uses the function above
        existing_names = {
            p.get("name", "").lower()
            for p in existing_players
            if isinstance(p, dict) and "name" in p
        }
        added_count = 0

        # Validate and add new players
        for player_dict in new_players:
            if not isinstance(player_dict, dict):
                logger.warning(
                    f"Skipping invalid item in new_players list (not a dict): {player_dict}"
                )
                continue
            player_name = player_dict.get("name")
            if not player_name or not isinstance(player_name, str):
                logger.warning(
                    f"Skipping invalid player entry (missing or invalid 'name'): {player_dict}"
                )
                continue

            if player_name.lower() in existing_names:
                logger.warning(
                    f"Player '{player_name}' is already in the allowlist. Skipping."
                )
            else:
                if "ignoresPlayerLimit" not in player_dict:
                    player_dict["ignoresPlayerLimit"] = False
                existing_players.append(player_dict)
                existing_names.add(player_name.lower())
                added_count += 1
                logger.debug(f"Added player '{player_name}' to allowlist.")

        # Write updated list back if changes were made
        if added_count > 0:
            logger.debug(
                f"Writing updated allowlist with {len(existing_players)} total players."
            )
            try:
                with open(allowlist_file, "w", encoding="utf-8") as f:
                    json.dump(existing_players, f, indent=4, sort_keys=True)
                logger.info(
                    f"Successfully updated allowlist.json ({added_count} players added)."
                )
            except OSError as e:
                logger.error(
                    f"Failed to write updated allowlist file '{allowlist_file}': {e}",
                    exc_info=True,
                )
                raise FileOperationError(
                    f"Failed to write allowlist file: {allowlist_file}"
                ) from e
        else:
            logger.info(
                "No new players added to the allowlist (all duplicates or input empty/invalid)."
            )

    except (DirectoryError, FileOperationError) as e:
        # Catch errors from configure_allowlist or writing
        logger.error(f"Failed to process allowlist: {e}", exc_info=True)
        raise  # Re-raise
    except Exception as e:
        logger.error(f"Unexpected error updating allowlist: {e}", exc_info=True)
        raise FileOperationError(f"Unexpected error updating allowlist: {e}") from e


def remove_player_from_allowlist(server_dir: str, player_name: str) -> bool:
    """
    Removes a player from the server's allowlist.json file based on their name.

    The comparison is case-insensitive.

    Args:
        server_dir: The full path to the server's installation directory.
        player_name: The name of the player to remove (case-insensitive).

    Returns:
        True if the player was found and removed, False otherwise.

    Raises:
        MissingArgumentError: If `server_dir` or `player_name` is empty.
        DirectoryError: If `server_dir` does not exist or is not a directory.
        FileOperationError: If reading or writing `allowlist.json` fails.
    """
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")
    if not player_name:
        raise MissingArgumentError("Player name cannot be empty.")
    if not os.path.isdir(server_dir):
        raise DirectoryError(f"Server directory not found: {server_dir}")

    allowlist_file = os.path.join(server_dir, "allowlist.json")
    player_name_lower = player_name.lower()  # For case-insensitive comparison
    logger.info(
        f"Attempting to remove player '{player_name}' from allowlist: {allowlist_file}"
    )

    try:
        # Load existing players using the same robust logic
        existing_players = read_allowlist(server_dir)
        original_count = len(existing_players)

        # Filter out the player to be removed
        updated_players = [
            player_dict
            for player_dict in existing_players
            if not (
                isinstance(player_dict, dict)
                and player_dict.get("name", "").lower() == player_name_lower
            )
        ]

        # Check if any player was actually removed
        if len(updated_players) < original_count:
            logger.debug(
                f"Player '{player_name}' found. Writing updated allowlist with {len(updated_players)} players."
            )
            # Write the updated list back to the file
            try:
                with open(allowlist_file, "w", encoding="utf-8") as f:
                    # Use indent for readability, matching common practice
                    json.dump(updated_players, f, indent=4, sort_keys=True)
                logger.info(
                    f"Successfully removed player '{player_name}' from allowlist.json."
                )
                return True  # Indicate player was removed
            except OSError as e:
                logger.error(
                    f"Failed to write updated allowlist file '{allowlist_file}' after removing player: {e}",
                    exc_info=True,
                )
                raise FileOperationError(
                    f"Failed to write updated allowlist file: {allowlist_file}"
                ) from e
        else:
            # Player name was not found in the list
            logger.warning(
                f"Player '{player_name}' not found in allowlist '{allowlist_file}'. No changes made."
            )
            return False  # Indicate player was not found

    except (DirectoryError, FileOperationError) as e:
        # Catch errors from configure_allowlist reading or potential DirectoryError re-check
        logger.error(f"Failed to process allowlist for removal: {e}", exc_info=True)
        raise  # Re-raise the specific error
    except Exception as e:
        # Catch unexpected errors during the process
        logger.error(
            f"Unexpected error removing player from allowlist: {e}", exc_info=True
        )
        raise FileOperationError(
            f"Unexpected error removing player from allowlist: {e}"
        ) from e


# --- PERMISSIONS ---


def configure_permissions(
    server_dir: str, xuid: str, player_name: Optional[str], permission: str
) -> None:
    """
    Sets or updates a player's permission level in the server's permissions.json file.

    Args:
        server_dir: The full path to the server's installation directory.
        xuid: The player's unique Xbox User ID (XUID) string.
        player_name: Optional. The player's in-game name (used if adding new, ignored if updating).
        permission: The desired permission level ("operator", "member", "visitor"). Case-insensitive.

    Raises:
        MissingArgumentError: If `server_dir`, `xuid`, or `permission` is empty.
        InvalidInputError: If `permission` is not one of the allowed values.
        DirectoryError: If `server_dir` does not exist or is not a directory.
        FileOperationError: If reading or writing `permissions.json` fails.
    """
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")
    if not os.path.isdir(server_dir):
        raise DirectoryError(f"Server directory not found: {server_dir}")
    if not xuid:
        raise MissingArgumentError("Player XUID cannot be empty.")
    if not permission:
        raise MissingArgumentError("Permission level cannot be empty.")

    permission = permission.lower()  # Normalize permission level
    valid_permissions = ("operator", "member", "visitor")
    if permission not in valid_permissions:
        raise InvalidInputError(
            f"Invalid permission level '{permission}'. Must be one of: {valid_permissions}"
        )

    permissions_file = os.path.join(server_dir, "permissions.json")
    logger.info(
        f"Configuring permission for XUID '{xuid}' to '{permission}' in: {permissions_file}"
    )

    permissions_data = []
    # Load existing permissions or initialize if file doesn't exist/is invalid
    try:
        if os.path.exists(permissions_file):
            with open(permissions_file, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    permissions_data = json.loads(content)
                    if not isinstance(permissions_data, list):
                        logger.warning(
                            f"Permissions file '{permissions_file}' does not contain a JSON list. Overwriting."
                        )
                        permissions_data = []
                    else:
                        logger.debug(
                            f"Loaded {len(permissions_data)} entries from permissions.json."
                        )
                else:
                    logger.debug("Permissions file exists but is empty.")
                    permissions_data = []
        else:
            logger.debug("Permissions file does not exist. Will create.")
            permissions_data = []
    except json.JSONDecodeError as e:
        logger.warning(
            f"Failed to parse JSON from permissions file '{permissions_file}'. File will be overwritten. Error: {e}",
            exc_info=True,
        )
        permissions_data = []
    except OSError as e:
        logger.error(
            f"Failed to read permissions file '{permissions_file}': {e}", exc_info=True
        )
        raise FileOperationError(
            f"Failed to read permissions file: {permissions_file}"
        ) from e

    # Find player by XUID and update/add
    player_found = False
    updated = False
    for i, entry in enumerate(permissions_data):
        if isinstance(entry, dict) and entry.get("xuid") == xuid:
            player_found = True
            if entry.get("permission") != permission:
                logger.info(
                    f"Updating permission for XUID '{xuid}' from '{entry.get('permission')}' to '{permission}'."
                )
                permissions_data[i]["permission"] = permission
                if (
                    player_name and entry.get("name") != player_name
                ):  # Also update name if provided and different
                    logger.debug(f"Updating name for XUID '{xuid}' to '{player_name}'.")
                    permissions_data[i]["name"] = player_name
                updated = True
            else:
                # If permission is the same, check if name needs updating
                if player_name and entry.get("name") != player_name:
                    logger.info(
                        f"Updating name for XUID '{xuid}' (permission unchanged) to '{player_name}'."
                    )
                    permissions_data[i]["name"] = player_name
                    updated = True
                else:
                    logger.info(
                        f"Player with XUID '{xuid}' already has permission '{permission}' and matching name (if provided). No changes needed."
                    )
                    # updated remains False if no changes were made
            break

    if not player_found:
        if not player_name:
            logger.warning(
                f"Adding new player with XUID '{xuid}' but no player_name provided. Using XUID as name."
            )
            # Consider if using XUID as name is the best default or if player_name should be mandatory for new entries.
            # For now, matching original behavior: if player_name is None, it implies it might not be set.
            # However, the JSON structure seems to always have a name.
            # Let's ensure 'name' is always present in the new entry.
            effective_player_name = player_name if player_name is not None else xuid
        else:
            effective_player_name = player_name

        logger.info(
            f"Adding new player XUID '{xuid}' (Name: '{effective_player_name}') with permission '{permission}'."
        )
        new_entry = {
            "permission": permission,
            "xuid": xuid,
            "name": effective_player_name,
        }
        permissions_data.append(new_entry)
        updated = True

    # Write back only if changes were made
    if updated:
        try:
            logger.debug(
                f"Writing updated permissions data ({len(permissions_data)} entries) to '{permissions_file}'."
            )
            with open(permissions_file, "w", encoding="utf-8") as f:
                json.dump(permissions_data, f, indent=4, sort_keys=True)
            logger.debug(f"Successfully updated permissions.json for XUID '{xuid}'.")
        except OSError as e:
            logger.error(
                f"Failed to write updated permissions file '{permissions_file}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to write permissions file: {permissions_file}"
            ) from e


def read_and_process_permissions_file(
    server_instance_dir: str,
    player_name_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Reads, parses, and processes the permissions.json file for a server instance.

    Args:
        server_instance_dir: The full path to the server's instance directory.
        player_name_map: A dictionary mapping player XUIDs (as strings) to their names.

    Returns:
        A list of dictionaries, each representing a player's permission entry,
        enhanced with player names and sorted by name.
        Example: [{"xuid": "123", "name": "PlayerA", "permission_level": "operator"}]

    Raises:
        PermissionsFileNotFoundError: If permissions.json does not exist.
        OSError: If there's an issue reading the file.
        json.JSONDecodeError: If the file content is not valid JSON.
        PermissionsFileError: If the JSON structure is not a list or entries are malformed.
    """
    if not os.path.isdir(server_instance_dir):
        # This check might be redundant if the caller ensures it, but good for a core function
        raise FileNotFoundError(
            f"Core: Server instance directory not found: {server_instance_dir}"
        )

    permissions_file_path = os.path.join(server_instance_dir, "permissions.json")
    logger.debug(f"Core: Attempting to read permissions file: {permissions_file_path}")

    if not os.path.isfile(permissions_file_path):
        logger.warning(f"Core: Permissions file not found at {permissions_file_path}")
        raise PermissionsFileNotFoundError(
            f"Permissions file not found: {permissions_file_path}"
        )

    try:
        with open(permissions_file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        logger.error(
            f"Core: OSError reading permissions file '{permissions_file_path}': {e}",
            exc_info=True,
        )
        raise  # Re-raise to be caught by API layer

    if not content.strip():
        logger.info(f"Core: Permissions file '{permissions_file_path}' is empty.")
        return []  # Return empty list for an empty file

    try:
        permissions_from_file = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(
            f"Core: JSONDecodeError parsing permissions file '{permissions_file_path}': {e}",
            exc_info=True,
        )
        raise  # Re-raise

    if not isinstance(permissions_from_file, list):
        logger.error(
            f"Core: Permissions file '{permissions_file_path}' does not contain a JSON list."
        )
        raise PermissionsFileError("Permissions file content is not a list.")

    processed_permissions: List[Dict[str, Any]] = []
    for entry in permissions_from_file:
        if isinstance(entry, dict) and "xuid" in entry and "permission" in entry:
            xuid_str = str(entry["xuid"])
            name = player_name_map.get(xuid_str, f"Unknown (XUID: {xuid_str})")
            processed_permissions.append(
                {
                    "xuid": xuid_str,
                    "name": name,
                    "permission_level": str(entry["permission"]),
                }
            )
        else:
            logger.warning(
                f"Core: Skipping malformed entry in '{permissions_file_path}': {entry}"
            )

    # Sort by player name (case-insensitive)
    processed_permissions.sort(key=lambda p: p.get("name", "").lower())
    logger.debug(f"Core: Processed {len(processed_permissions)} permission entries.")
    return processed_permissions


# --- SERVER PROPERTIES ---
def modify_server_properties(
    server_properties_path: str, property_name: str, property_value: str
) -> None:
    """
    Modifies or adds a property in the server.properties file.

    Preserves comments and blank lines.

    Args:
        server_properties_path: The full path to the server.properties file.
        property_name: The name of the property to set (e.g., "level-name").
        property_value: The value to assign to the property.

    Raises:
        MissingArgumentError: If `server_properties_path` or `property_name` is empty.
        FileNotFoundError: If `server_properties_path` does not exist or is not a file.
        InvalidInputError: If `property_value` contains control characters (ASCII < 32).
        FileOperationError: If reading or writing the file fails due to OS errors.
    """
    if not server_properties_path:
        raise MissingArgumentError("Server properties file path cannot be empty.")
    if not property_name:
        raise MissingArgumentError("Property name cannot be empty.")
    # Allow empty string value, but check for control chars which might break the file
    if property_value is None:
        property_value = ""  # Treat None as empty string
    if any(
        ord(c) < 32 for c in property_value if c not in ("\t")
    ):  # Allow tabs, disallow others < 32
        raise InvalidInputError(
            f"Property value for '{property_name}' contains invalid control characters."
        )

    logger.debug(
        f"Modifying property '{property_name}' to '{property_value}' in: {server_properties_path}"
    )

    if not os.path.isfile(server_properties_path):
        raise FileNotFoundError(
            f"Server properties file not found: {server_properties_path}"
        )

    try:
        with open(server_properties_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        property_found = False
        output_lines = []
        property_line = f"{property_name}={property_value}\n"

        for line in lines:
            stripped_line = line.strip()
            # Ignore comments and blank lines when searching for the property
            if not stripped_line or stripped_line.startswith("#"):
                output_lines.append(line)
                continue

            # Check if line starts with property_name=
            if stripped_line.startswith(property_name + "="):
                if not property_found:  # Only replace the first occurrence found
                    logger.debug(
                        f"Replacing existing line: {line.strip()} with: {property_line.strip()}"
                    )
                    output_lines.append(property_line)
                    property_found = True
                else:
                    logger.warning(
                        f"Duplicate property '{property_name}' found. Keeping first occurrence, ignoring line: {line.strip()}"
                    )
                    output_lines.append("# DUPLICATE IGNORED: " + line)
            else:
                # Keep other valid lines
                output_lines.append(line)

        # If property was not found anywhere, append it to the end
        if not property_found:
            logger.debug(f"Property '{property_name}' not found. Appending to end.")
            # Add a newline before appending if the last line wasn't empty
            if output_lines and not output_lines[-1].endswith("\n"):
                output_lines[-1] += "\n"
            output_lines.append(property_line)

        # Write the modified lines back to the file
        with open(server_properties_path, "w", encoding="utf-8") as f:
            f.writelines(output_lines)
        logger.debug(
            f"Successfully modified server.properties for property '{property_name}'."
        )

    except OSError as e:
        logger.error(
            f"Failed to read or write server.properties file '{server_properties_path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(f"Failed to modify server.properties: {e}") from e
    except Exception as e:
        logger.error(
            f"Unexpected error modifying server.properties: {e}", exc_info=True
        )
        raise FileOperationError(
            f"Unexpected error modifying server.properties: {e}"
        ) from e


def parse_properties_file_content(file_path: str) -> Dict[str, str]:
    """
    Reads and parses a server.properties-style file.

    Args:
        file_path: The full path to the properties file.

    Returns:
        A dictionary of key-value pairs from the properties file.

    Raises:
        PropertiesFileNotFoundError: If the file does not exist at file_path.
        PropertiesFileReadError: If an OS error occurs while reading the file.
                                 Malformed lines are logged and skipped, not raised as errors.
    """
    logger.debug(f"Core: Attempting to read and parse properties file: {file_path}")

    if not os.path.isfile(file_path):
        logger.warning(f"Core: Properties file not found at {file_path}")
        raise PropertiesFileNotFoundError(f"Properties file not found: {file_path}")

    properties: Dict[str, str] = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line_content in enumerate(f, 1):
                line_content = line_content.strip()
                if not line_content or line_content.startswith("#"):
                    continue  # Skip empty lines and comments

                parts = line_content.split("=", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if key:  # Ensure the key is not empty after stripping
                        properties[key] = value
                    else:
                        logger.warning(
                            f"Core: Skipping line {line_num} with empty key in '{file_path}': \"{line_content}\""
                        )
                else:
                    logger.warning(
                        f"Core: Skipping malformed line {line_num} in '{file_path}': \"{line_content}\""
                    )
    except OSError as e:
        logger.error(
            f"Core: OSError reading properties file '{file_path}': {e}", exc_info=True
        )
        raise PropertiesFileReadError(
            f"Failed to read properties file '{file_path}': {e}"
        ) from e

    logger.debug(
        f"Core: Successfully parsed {len(properties)} properties from '{file_path}'."
    )
    return properties


# --- INSTALL ---
def _write_version_config(
    server_name: str, installed_version: str, config_dir: Optional[str] = None
) -> None:
    """
    Helper function to write the 'installed_version' key to a server's config file.

    Args:
        server_name: The name of the server.
        installed_version: The version string to write.
        config_dir: Optional. The base directory for server configs.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If writing to the config file fails.
    """
    # server_name validity already checked by caller usually, but check again
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    if (
        not installed_version
    ):  # installed_version itself should not be empty string if it's a valid version
        logger.warning(
            f"Empty installed_version for server '{server_name}' provided to _write_version_config."
        )
        # Depending on policy, this could be an error or default to "UNKNOWN"
        raise InvalidInputError(
            "installed_version cannot be empty when writing to config."
        )

    logger.debug(
        f"Writing installed_version '{installed_version}' to config for server '{server_name}'."
    )
    try:
        core_server_utils.manage_server_config(
            server_name=server_name,
            key="installed_version",
            operation="write",
            value=installed_version,
            config_dir=config_dir,
        )
        logger.debug("Successfully wrote installed_version to config.")
    except (
        MissingArgumentError,
        InvalidInputError,
        FileOperationError,
        InvalidServerNameError,
    ) as e:
        # Catch errors from manage_server_config
        logger.error(
            f"Failed to write installed_version to config for '{server_name}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to write version config for '{server_name}': {e}"
        ) from e


def setup_server_files(downloader_instance: BedrockDownloader, is_update: bool) -> None:
    """
    CORE: Extracts server files using the BedrockDownloader instance
    and sets appropriate file permissions.

    Args:
        downloader_instance: An initialized BedrockDownloader instance that has
                             successfully prepared download assets (i.e., zip_file_path is set).
        is_update: True if this is an update (preserves some files), False for fresh install.

    Raises:
        InstallUpdateError: If extraction or permission setting fails.
        MissingArgumentError, FileNotFoundError, DownloadExtractError, FileOperationError:
                             Propagated from downloader_instance.extract_server_files().
    """
    if not downloader_instance:
        raise MissingArgumentError(
            "BedrockDownloader instance cannot be None for setup_server_files."
        )
    if (
        downloader_instance.get_zip_file_path() is None
    ):  # Or self.zip_file_path directly
        raise MissingArgumentError(
            "Downloader instance has no ZIP file path set. Call prepare_download_assets() first."
        )

    server_dir = downloader_instance.server_dir
    zip_file_name = os.path.basename(
        downloader_instance.get_zip_file_path() or "Unknown.zip"
    )

    logger.info(
        f"CORE: Setting up server files in '{server_dir}' from '{zip_file_name}'. Update: {is_update}"
    )

    # 1. Extract server files using the BedrockDownloader instance's method
    try:
        downloader_instance.extract_server_files(is_update)
        logger.info("CORE: Server file extraction completed successfully.")
    except (
        DownloadExtractError,
        FileOperationError,
        MissingArgumentError,  # From extract_server_files if its prereqs not met
        FileNotFoundError,  # If zip_file_path points to non-existent file
    ) as e:
        logger.error(
            f"CORE: Failed to extract server files into '{server_dir}': {e}",
            exc_info=True,
        )
        raise InstallUpdateError(
            f"Extraction phase failed for server setup in '{server_dir}'."
        ) from e
    except Exception as e:  # Catch other unexpected errors from extraction
        logger.error(
            f"CORE: Unexpected error during server file extraction into '{server_dir}': {e}",
            exc_info=True,
        )
        raise InstallUpdateError(
            f"Unexpected error during extraction phase in '{server_dir}'."
        ) from e

    # 2. Set permissions (especially important on Linux)
    logger.debug(f"CORE: Setting permissions for server directory: {server_dir}")
    try:
        system_base.set_server_folder_permissions(server_dir)
        logger.debug("CORE: Server folder permissions set successfully.")
    except Exception as e:
        logger.warning(
            f"CORE: Failed to set server folder permissions for '{server_dir}': {e}. "
            "Manual adjustment might be needed.",
            exc_info=True,
        )
        # Depending on strictness, you might raise InstallUpdateError here too:
        # raise InstallUpdateError(f"Failed to set permissions for '{server_dir}'.") from e

    logger.info(f"CORE: Server file setup completed for '{server_dir}'.")


def no_update_needed(
    settings_obj,  # Pass the global settings object or instance
    server_name: str,
    server_dir: str,  # Directory of the server being checked, for downloader instantiation
    installed_version: str,
    target_version_spec: str,
) -> bool:
    """
    Checks if the installed server version matches the latest available version
    based on the target specification or a specific version.

    Args:
        settings_obj: The application's settings object.
        server_name: The name of the server (for logging).
        server_dir: The directory of the server installation (can be a placeholder
                    if only doing a remote version check for LATEST/PREVIEW, but
                    BedrockDownloader requires it).
        installed_version: The currently installed version string (e.g., "1.20.1.2").
        target_version_spec: The desired version specification ("LATEST", "PREVIEW",
                             or a specific version like "X.Y.Z.W" or "X.Y.Z.W-PREVIEW").

    Returns:
        True if no update is needed, False otherwise.

    Raises:
        MissingArgumentError: If required arguments are missing.
        InvalidServerNameError: If `server_name` is invalid.
        DirectoryError: If DOWNLOAD_DIR setting is missing (from BedrockDownloader).
        # Exceptions from BedrockDownloader.get_version_for_target_spec may propagate
        # (InternetConnectivityError, DownloadExtractError, OSError).
    """
    if not settings_obj:
        raise MissingArgumentError(
            "Settings object cannot be None for no_update_needed."
        )
    if not server_name:
        raise InvalidServerNameError(
            "Server name cannot be empty for no_update_needed."
        )
    if not server_dir:
        # BedrockDownloader requires server_dir. If it's truly optional for this check,
        # the downloader class would need adjustment. Assume it's available.
        raise MissingArgumentError(
            "Server directory cannot be empty for no_update_needed."
        )
    if not target_version_spec:
        raise MissingArgumentError("Target version specification cannot be empty.")

    target_upper = target_version_spec.strip().upper()
    is_latest_or_preview_spec = target_upper in ("LATEST", "PREVIEW")

    if not is_latest_or_preview_spec:
        # Target is a specific version (e.g., "1.20.1.2" or "1.20.1.2-PREVIEW")
        # We need to compare the numeric part of target_version_spec with installed_version.
        # The BedrockDownloader can parse this for us.
        try:
            downloader_for_spec_parse = BedrockDownloader(
                settings_obj=settings_obj,
                server_dir=server_dir,  # Placeholder or actual, not used for file ops here
                target_version=target_version_spec,
            )
            # _custom_version_number holds the "X.Y.Z.W" part from "X.Y.Z.W" or "X.Y.Z.W-PREVIEW"
            specific_target_numeric_version = (
                downloader_for_spec_parse._custom_version_number
            )
            if (
                not specific_target_numeric_version
            ):  # Should be set if not LATEST/PREVIEW
                logger.error(
                    f"Could not parse numeric version from specific target '{target_version_spec}'."
                )
                return False  # Cannot compare, assume update needed

            if installed_version == specific_target_numeric_version:
                logger.debug(
                    f"Server '{server_name}' installed version '{installed_version}' matches specific target '{target_version_spec}' (numeric: {specific_target_numeric_version}). No update needed."
                )
                return True
            else:
                logger.info(
                    f"Update needed for server '{server_name}'. Installed: {installed_version}, Specific Target: {target_version_spec} (numeric: {specific_target_numeric_version})"
                )
                return False
        except Exception as e:  # Catch errors from BedrockDownloader init or logic
            logger.warning(
                f"Error determining numeric version for specific target '{target_version_spec}': {e}. Assuming update might be needed.",
                exc_info=True,
            )
            return False

    # For LATEST or PREVIEW specification
    if not installed_version or installed_version == "UNKNOWN":
        logger.info(
            f"Installed version for server '{server_name}' is '{installed_version}'. Cannot compare with '{target_upper}'. Assuming update needed."
        )
        return False

    logger.debug(
        f"Checking if update is needed for server '{server_name}': Installed='{installed_version}', Target Spec='{target_upper}'"
    )

    try:
        # Create a BedrockDownloader instance to check the latest version for LATEST/PREVIEW
        downloader_for_check = BedrockDownloader(
            settings_obj=settings_obj,
            server_dir=server_dir,  # Actual server_dir or a valid placeholder path
            target_version=target_upper,  # "LATEST" or "PREVIEW"
        )

        latest_available_version = downloader_for_check.get_version_for_target_spec()
        logger.debug(
            f"Latest available version for '{target_upper}' spec found: '{latest_available_version}'"
        )

        if installed_version == latest_available_version:
            logger.debug(
                f"Server '{server_name}' is already up-to-date (Version: {installed_version} matches latest for {target_upper}). No update needed."
            )
            return True
        else:
            logger.info(
                f"Update needed for server '{server_name}'. Installed: {installed_version}, Latest Available ({target_upper}): {latest_available_version}"
            )
            return False

    except (
        InternetConnectivityError,
        DownloadExtractError,
        OSError,
        DirectoryError,
        MissingArgumentError,
    ) as e:
        logger.warning(
            f"Could not determine the latest available version for '{target_upper}' due to an error: {e}. Assuming update might be needed.",
            exc_info=True,
        )
        return False
    except Exception as e:  # Catch any other unexpected error
        logger.error(
            f"Unexpected error during update check for server '{server_name}' against '{target_upper}': {e}",
            exc_info=True,
        )
        return False
