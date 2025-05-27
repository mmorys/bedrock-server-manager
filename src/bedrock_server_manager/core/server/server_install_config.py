# bedrock-server-manager/bedrock_server_manager/core/server/server_install_config.py
"""
Core module for managing Bedrock server instances.
"""

import os
import logging
import json
import platform
from typing import Optional, Any, Dict

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.core.server import server_utils as core_server_utils
from bedrock_server_manager.error import (
    ServerNotFoundError,
    InvalidServerNameError,
    MissingArgumentError,
    FileOperationError,
    InvalidInputError,
    DirectoryError,
    InstallUpdateError,
    DownloadExtractError,
    InternetConnectivityError,
)
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
    windows as system_windows,
)
from bedrock_server_manager.core import downloader


logger = logging.getLogger("bedrock_server_manager")


# --- Helper function ---


def configure_allowlist(server_dir: str) -> list:
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
        existing_players = configure_allowlist(server_dir)  # Uses the function above
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
        existing_players = configure_allowlist(server_dir)
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


def setup_server_files(zip_file_path: str, server_dir: str, is_update: bool) -> None:
    """
    CORE: Extracts server files from a ZIP archive into the server directory
    and sets appropriate file permissions. This is a focused part of the
    installation/update process.

    Args:
        zip_file_path: Path to the downloaded server ZIP file.
        server_dir: The target directory for the server installation.
        is_update: True if this is an update (preserves some files), False for fresh install.

    Raises:
        InstallUpdateError: If extraction or permission setting fails.
        MissingArgumentError, FileNotFoundError, DownloadExtractError, FileOperationError: from downloader.
    """
    logger.info(
        f"CORE: Setting up server files in '{server_dir}' from '{os.path.basename(zip_file_path)}'. Update: {is_update}"
    )

    # 1. Extract server files (using the function from the downloader module)
    try:
        # This function resides in core.downloader and handles the actual extraction logic,
        # including preserving files during an update.
        downloader.extract_server_files_from_zip(zip_file_path, server_dir, is_update)
        logger.info("CORE: Server file extraction completed successfully.")
    except (
        DownloadExtractError,
        FileOperationError,
        MissingArgumentError,
        FileNotFoundError,
    ) as e:
        logger.error(
            f"CORE: Failed to extract server files into '{server_dir}': {e}",
            exc_info=True,
        )
        # Wrap in InstallUpdateError to signify failure at this stage of installation
        raise InstallUpdateError(
            f"Extraction phase failed for server setup in '{server_dir}'."
        ) from e
    except Exception as e:
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
        # Log warning, but don't necessarily fail the whole install if permissions fail.
        # However, for consistency, an InstallUpdateError could be raised if permissions are critical.
        logger.warning(
            f"CORE: Failed to set server folder permissions for '{server_dir}': {e}. "
            "Manual adjustment might be needed.",
            exc_info=True,
        )
        # Optionally raise:
        # raise InstallUpdateError(f"Failed to set permissions for '{server_dir}'.") from e
    logger.info(f"CORE: Server file setup completed for '{server_dir}'.")


def no_update_needed(
    server_name: str, installed_version: str, target_version_spec: str
) -> bool:
    """
    Checks if the installed server version matches the latest available version
    based on the target specification ("LATEST" or "PREVIEW").

    Args:
        server_name: The name of the server.
        installed_version: The currently installed version string (e.g., "1.20.1.2").
        target_version_spec: The desired version specification ("LATEST", "PREVIEW").
                             If a specific version number is passed, this function
                             assumes an update *is* needed (returns False).

    Returns:
        True if the installed version matches the latest available for the spec,
        False otherwise (or if the latest version cannot be determined).

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        # Exceptions from downloader.lookup_bedrock_download_url / get_version_from_url may propagate
        # (InternetConnectivityError, DownloadExtractError, OSError)
    """
    if not server_name:
        raise InvalidServerNameError(
            "Server name cannot be empty."
        )  # Or MissingArgumentError

    target_upper = target_version_spec.upper()

    # If a specific version is requested, we treat it as needing an "update"
    # unless the specific version matches exactly what's installed.
    # However, the primary use case here is checking against LATEST/PREVIEW.
    if target_upper not in ("LATEST", "PREVIEW"):
        logger.debug(
            f"Target version '{target_version_spec}' is specific. Assuming update check is not applicable in this context (always attempt install/update)."
        )
        return False  # Assume 'update' needed if specific version given

    if not installed_version or installed_version == "UNKNOWN":
        logger.info(
            f"Installed version for server '{server_name}' is '{installed_version}'. Update check requires a known installed version. Assuming update needed."
        )
        return False  # Cannot compare if installed version is unknown

    logger.debug(
        f"Checking if update is needed for server '{server_name}': Installed='{installed_version}', Target='{target_upper}'"
    )

    try:
        # Find the download URL for the target spec (LATEST or PREVIEW)
        latest_download_url = downloader.lookup_bedrock_download_url(target_upper)
        # Extract the actual version number from that URL
        latest_available_version = downloader.get_version_from_url(latest_download_url)
        logger.debug(
            f"Latest available version for '{target_upper}' spec found: '{latest_available_version}'"
        )

        # Compare installed version with the latest available
        if installed_version == latest_available_version:
            logger.debug(
                f"Server '{server_name}' is already up-to-date (Version: {installed_version}). No update needed."
            )
            return True
        else:
            logger.info(
                f"Update needed for server '{server_name}'. Installed: {installed_version}, Latest Available ({target_upper}): {latest_available_version}"
            )
            return False

    except (InternetConnectivityError, DownloadExtractError, OSError) as e:
        # If we fail to get the latest version info, log warning and assume update needed
        logger.warning(
            f"Could not determine the latest available version for '{target_upper}' due to an error: {e}. Assuming update might be needed.",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error during update check for server '{server_name}': {e}",
            exc_info=True,
        )
        return False
