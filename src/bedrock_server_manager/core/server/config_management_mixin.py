# bedrock_server_manager/core/server/config_management_mixin.py
"""
Provides the ServerConfigManagementMixin class for BedrockServer.

This mixin is responsible for managing server-specific configuration files,
including `allowlist.json`, `permissions.json`, and `server.properties`.
It handles reading, writing, and modifying these files.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

# Local imports
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import (
    MissingArgumentError,
    FileOperationError,
    UserInputError,
    AppFileNotFoundError,
    ConfigParseError,
)


class ServerConfigManagementMixin(BedrockServerBaseMixin):
    """
    A mixin for the BedrockServer class that provides methods for managing
    key server configuration files such as `allowlist.json`, `permissions.json`,
    and `server.properties`.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the ServerConfigManagementMixin.

        Calls super().__init__ for proper multiple inheritance setup.
        Relies on attributes (like server_dir, logger) from the base class.
        """
        super().__init__(*args, **kwargs)
        # self.server_dir, self.logger are available

    # --- ALLOWLIST METHODS ---
    @property
    def allowlist_json_path(self) -> str:
        """Returns the full path to this server's allowlist.json file."""
        return os.path.join(self.server_dir, "allowlist.json")

    def get_allowlist(self) -> List[Dict[str, Any]]:
        """Loads and returns the current content of this server's allowlist.json."""
        self.logger.debug(
            f"Server '{self.server_name}': Loading allowlist from {self.allowlist_json_path}"
        )

        if not os.path.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")

        allowlist_entries: List[Dict[str, Any]] = []
        if os.path.isfile(self.allowlist_json_path):
            try:
                with open(self.allowlist_json_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        loaded_data = json.loads(content)
                        if isinstance(loaded_data, list):
                            allowlist_entries = loaded_data
                        else:
                            self.logger.warning(
                                f"Allowlist file '{self.allowlist_json_path}' not a JSON list. Treating as empty."
                            )
            except ValueError as e:
                raise ConfigParseError(
                    f"Invalid JSON in allowlist '{self.allowlist_json_path}': {e}"
                ) from e
            except OSError as e:
                raise FileOperationError(
                    f"Failed to read allowlist '{self.allowlist_json_path}': {e}"
                ) from e
        else:
            self.logger.debug(
                f"Allowlist file '{self.allowlist_json_path}' does not exist. Returning empty list."
            )

        return allowlist_entries

    def add_to_allowlist(self, players_to_add: List[Dict[str, Any]]) -> int:
        """Adds players to this server's allowlist.json, avoiding duplicates by name (case-insensitive)."""
        if not isinstance(players_to_add, list):
            raise TypeError("Input 'players_to_add' must be a list of dictionaries.")
        if not os.path.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")

        self.logger.info(
            f"Server '{self.server_name}': Adding {len(players_to_add)} player(s) to allowlist."
        )

        current_allowlist = self.get_allowlist()
        existing_names_lower = {
            p.get("name", "").lower()
            for p in current_allowlist
            if isinstance(p, dict) and p.get("name")
        }

        added_count = 0
        for player_entry in players_to_add:
            if (
                not isinstance(player_entry, dict)
                or not player_entry.get("name")
                or not isinstance(player_entry.get("name"), str)
            ):
                self.logger.warning(
                    f"Skipping invalid player entry for allowlist: {player_entry}"
                )
                continue

            player_name = player_entry["name"]
            if player_name.lower() not in existing_names_lower:
                # Ensure 'ignoresPlayerLimit' exists, defaulting to False
                if "ignoresPlayerLimit" not in player_entry:
                    player_entry["ignoresPlayerLimit"] = False
                current_allowlist.append(player_entry)
                existing_names_lower.add(
                    player_name.lower()
                )  # Keep track of names added in this run
                added_count += 1
                self.logger.debug(
                    f"Player '{player_name}' prepared for allowlist addition."
                )
            else:
                self.logger.warning(
                    f"Player '{player_name}' already in allowlist or added in this batch. Skipping."
                )

        if added_count > 0:
            try:
                with open(self.allowlist_json_path, "w", encoding="utf-8") as f:
                    json.dump(current_allowlist, f, indent=4, sort_keys=True)
                self.logger.info(
                    f"Successfully updated allowlist for '{self.server_name}'. {added_count} players added."
                )
            except OSError as e:
                raise FileOperationError(
                    f"Failed to write allowlist '{self.allowlist_json_path}': {e}"
                ) from e
        else:
            self.logger.info(
                f"No new players added to allowlist for '{self.server_name}'."
            )
        return added_count

    def remove_from_allowlist(self, player_name_to_remove: str) -> bool:
        """Removes a player from this server's allowlist.json by name (case-insensitive)."""
        if not player_name_to_remove:
            raise MissingArgumentError("Player name to remove cannot be empty.")
        if not os.path.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")

        self.logger.info(
            f"Server '{self.server_name}': Removing player '{player_name_to_remove}' from allowlist."
        )

        current_allowlist = self.get_allowlist()
        name_lower_to_remove = player_name_to_remove.lower()

        updated_allowlist = [
            p
            for p in current_allowlist
            if not (
                isinstance(p, dict)
                and p.get("name", "").lower() == name_lower_to_remove
            )
        ]

        if len(updated_allowlist) < len(current_allowlist):
            try:
                with open(self.allowlist_json_path, "w", encoding="utf-8") as f:
                    json.dump(updated_allowlist, f, indent=4, sort_keys=True)
                self.logger.info(
                    f"Successfully removed '{player_name_to_remove}' from allowlist for '{self.server_name}'."
                )
                return True
            except OSError as e:
                raise FileOperationError(
                    f"Failed to write allowlist '{self.allowlist_json_path}': {e}"
                ) from e
        else:
            self.logger.warning(
                f"Player '{player_name_to_remove}' not found in allowlist for '{self.server_name}'."
            )
            return False

    # --- PERMISSIONS.JSON METHODS ---
    @property
    def permissions_json_path(self) -> str:
        """Returns the full path to this server's permissions.json file."""
        return os.path.join(self.server_dir, "permissions.json")

    def set_player_permission(
        self, xuid: str, permission_level: str, player_name: Optional[str] = None
    ) -> None:
        """Sets or updates a player's permission level in this server's permissions.json."""
        if not os.path.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")
        if not xuid:
            raise MissingArgumentError("Player XUID cannot be empty.")
        if not permission_level:
            raise MissingArgumentError("Permission level cannot be empty.")

        perm_level_lower = permission_level.lower()
        valid_perms = ("operator", "member", "visitor")
        if perm_level_lower not in valid_perms:
            raise UserInputError(
                f"Invalid permission '{perm_level_lower}'. Must be one of: {valid_perms}"
            )

        self.logger.info(
            f"Server '{self.server_name}': Setting permission for XUID '{xuid}' to '{perm_level_lower}'."
        )

        permissions_list: List[Dict[str, Any]] = []
        if os.path.isfile(self.permissions_json_path):
            try:
                with open(self.permissions_json_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        loaded_data = json.loads(content)
                        if isinstance(loaded_data, list):
                            permissions_list = loaded_data
                        else:
                            self.logger.warning(
                                f"Permissions file '{self.permissions_json_path}' not a list. Overwriting."
                            )
            except ValueError as e:
                self.logger.warning(
                    f"Invalid JSON in permissions '{self.permissions_json_path}'. Overwriting. Error: {e}"
                )
            except OSError as e:
                raise FileOperationError(
                    f"Failed to read permissions '{self.permissions_json_path}': {e}"
                ) from e

        entry_found = False
        modified = False
        for entry in permissions_list:
            if isinstance(entry, dict) and entry.get("xuid") == xuid:
                entry_found = True
                if entry.get("permission") != perm_level_lower:
                    entry["permission"] = perm_level_lower
                    modified = True
                if (
                    player_name and entry.get("name") != player_name
                ):  # Update name if provided and different
                    entry["name"] = player_name
                    modified = True
                break

        if not entry_found:
            effective_name = (
                player_name if player_name else xuid
            )  # Default name to XUID if not provided
            permissions_list.append(
                {"permission": perm_level_lower, "xuid": xuid, "name": effective_name}
            )
            modified = True

        if modified:
            try:
                with open(self.permissions_json_path, "w", encoding="utf-8") as f:
                    json.dump(permissions_list, f, indent=4, sort_keys=True)
                self.logger.info(
                    f"Successfully updated permissions for XUID '{xuid}' for '{self.server_name}'."
                )
            except OSError as e:
                raise FileOperationError(
                    f"Failed to write permissions '{self.permissions_json_path}': {e}"
                ) from e
        else:
            self.logger.info(
                f"No changes needed for XUID '{xuid}' permissions for '{self.server_name}'."
            )

    def get_formatted_permissions(
        self, player_xuid_to_name_map: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Reads, parses, and processes permissions.json, enriching with player names."""
        if not os.path.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")
        if not os.path.isfile(self.permissions_json_path):
            raise AppFileNotFoundError(self.permissions_json_path, "Permissions file")

        self.logger.debug(
            f"Server '{self.server_name}': Reading and processing permissions from {self.permissions_json_path}"
        )

        raw_permissions: List[Dict[str, Any]] = []
        try:
            with open(self.permissions_json_path, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    loaded_data = json.loads(content)
                    if isinstance(loaded_data, list):
                        raw_permissions = loaded_data
                    else:
                        raise ConfigParseError(
                            "Permissions file content is not a list."
                        )
        except ValueError as e:
            raise ConfigParseError(f"Invalid JSON in permissions file: {e}") from e
        except OSError as e:
            raise FileOperationError(
                f"OSError reading permissions file '{self.permissions_json_path}': {e}"
            ) from e

        processed_list: List[Dict[str, Any]] = []
        for entry in raw_permissions:
            if isinstance(entry, dict) and "xuid" in entry and "permission" in entry:
                xuid = str(entry["xuid"])
                name = player_xuid_to_name_map.get(xuid, f"Unknown (XUID: {xuid})")
                processed_list.append(
                    {
                        "xuid": xuid,
                        "name": name,
                        "permission_level": str(entry["permission"]),
                    }
                )
            else:
                self.logger.warning(
                    f"Skipping malformed entry in '{self.permissions_json_path}': {entry}"
                )

        processed_list.sort(key=lambda p: p.get("name", "").lower())
        return processed_list

    # --- SERVER.PROPERTIES METHODS ---

    def set_server_property(self, property_key: str, property_value: Any) -> None:
        """Modifies or adds a property in this server's server.properties file."""
        if not property_key:
            raise MissingArgumentError("Property name cannot be empty.")

        str_value = str(property_value)  # Ensure value is string for properties file
        if any(ord(c) < 32 for c in str_value if c != "\t"):  # Allow tabs
            raise UserInputError(
                f"Property value for '{property_key}' contains invalid control characters."
            )

        if not os.path.isfile(self.server_properties_path):
            raise AppFileNotFoundError(
                self.server_properties_path, "Server properties file"
            )

        self.logger.debug(
            f"Server '{self.server_name}': Setting property '{property_key}' to '{str_value}' in {self.server_properties_path}"
        )

        try:
            with open(self.server_properties_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            raise FileOperationError(
                f"Failed to read '{self.server_properties_path}': {e}"
            ) from e

        output_lines = []
        property_found_and_set = False
        new_property_line = f"{property_key}={str_value}\n"

        for line_content in lines:
            stripped_line = line_content.strip()
            if not stripped_line or stripped_line.startswith(
                "#"
            ):  # Preserve comments/blank lines
                output_lines.append(line_content)
                continue

            if stripped_line.startswith(property_key + "="):
                if not property_found_and_set:  # Replace first occurrence
                    output_lines.append(new_property_line)
                    property_found_and_set = True
                else:  # Comment out duplicates
                    output_lines.append("# DUPLICATE IGNORED: " + line_content)
            else:
                output_lines.append(line_content)

        if not property_found_and_set:  # Add new property if not found
            if output_lines and not output_lines[-1].endswith("\n"):
                output_lines[-1] += "\n"
            output_lines.append(new_property_line)

        try:
            with open(self.server_properties_path, "w", encoding="utf-8") as f:
                f.writelines(output_lines)
            self.logger.info(
                f"Successfully set property '{property_key}' for '{self.server_name}'."
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to write '{self.server_properties_path}': {e}"
            ) from e

    def get_server_properties(
        self,
    ) -> Dict[str, str]:
        """Reads and parses this server's server.properties file."""
        if not os.path.isfile(self.server_properties_path):
            raise AppFileNotFoundError(
                self.server_properties_path, "Server properties file"
            )

        self.logger.debug(
            f"Server '{self.server_name}': Parsing {self.server_properties_path}"
        )
        properties: Dict[str, str] = {}
        try:
            with open(self.server_properties_path, "r", encoding="utf-8") as f:
                for line_num, line_content in enumerate(f, 1):
                    line = line_content.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("=", 1)
                    if len(parts) == 2 and parts[0].strip():
                        properties[parts[0].strip()] = parts[1].strip()
                    else:
                        self.logger.warning(
                            f"Skipping malformed line {line_num} in '{self.server_properties_path}': \"{line}\""
                        )
        except OSError as e:
            raise ConfigParseError(
                f"Failed to read '{self.server_properties_path}': {e}"
            ) from e

        return properties

    def get_server_property(
        self, property_key: str, default: Optional[Any] = None
    ) -> Optional[Any]:
        """Gets a specific property value from server.properties, returning default if not found."""
        try:
            props = self.get_server_properties()
            return props.get(property_key, default)
        except AppFileNotFoundError:
            return default
