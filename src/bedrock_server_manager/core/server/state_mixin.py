# bedrock_server_manager/core/server/state_mixin.py
"""Provides the ServerStateMixin for the BedrockServer class.

This mixin is responsible for managing the persisted state of a server instance.
This includes its installed version, current status (e.g., RUNNING, STOPPED),
target version for updates, and other custom configuration values. These states
are typically stored in a server-specific JSON file in a nested format.
It also handles reading the world name from `server.properties`.
"""
import os
import json
from typing import Optional, Any, Dict, TYPE_CHECKING

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import (
    MissingArgumentError,
    UserInputError,
    FileOperationError,
    ConfigParseError,
    AppFileNotFoundError,
)

# Version for the server-specific JSON config schema
SERVER_CONFIG_SCHEMA_VERSION = 2


class ServerStateMixin(BedrockServerBaseMixin):
    """A mixin for BedrockServer to read and write persistent state information.

    This class manages the server-specific JSON configuration file (which stores
    status, version, etc. in a nested structure) and reads essential properties
    like the world name from `server.properties`.
    """

    def __init__(self, *args, **kwargs):
        """Initializes the ServerStateMixin.

        This constructor calls `super().__init__` to ensure proper method
        resolution order in the context of multiple inheritance. It relies on
        attributes (like `server_name`, `_server_specific_config_dir`) from
        the base class.
        """
        super().__init__(*args, **kwargs)

    @property
    def _server_specific_json_config_file_path(self) -> str:
        """Returns the path to this server's specific JSON configuration file."""
        return os.path.join(self.server_config_dir, f"{self.server_name}_config.json")

    def _get_default_server_config(self) -> Dict[str, Any]:
        """Returns the default structure for a server's JSON config."""
        return {
            "config_schema_version": SERVER_CONFIG_SCHEMA_VERSION,
            "server_info": {
                "installed_version": "UNKNOWN",
                "status": "UNKNOWN",
            },
            "settings": {
                "autoupdate": False,  # Default to boolean
                "target_version": "UNKNOWN",
            },
            "custom_values": {},
        }

    def _migrate_server_config_v1_to_v2(
        self, old_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Migrates a flat v1 server config to the nested v2 format."""
        self.logger.info(
            f"Migrating server config for '{self.server_name}' from v1 (flat) to v2 (nested)."
        )
        new_config = self._get_default_server_config()  # Start with a clean default

        # Migrate known server_info keys
        new_config["server_info"]["installed_version"] = old_config.get(
            "installed_version", new_config["server_info"]["installed_version"]
        )
        new_config["settings"]["target_version"] = old_config.get(
            "target_version", new_config["settings"]["target_version"]
        )
        new_config["server_info"]["status"] = old_config.get(
            "status", new_config["server_info"]["status"]
        )

        # Migrate known settings keys
        autoupdate_val = old_config.get("autoupdate")
        if isinstance(autoupdate_val, str):
            new_config["settings"]["autoupdate"] = autoupdate_val.lower() == "true"
        elif isinstance(autoupdate_val, bool):
            new_config["settings"]["autoupdate"] = autoupdate_val
        # If missing or other type, it keeps the default from _get_default_server_config

        # Migrate any other keys to custom_values
        known_v1_keys = {
            "installed_version",
            "target_version",
            "status",
            "autoupdate",
        }
        for key, value in old_config.items():
            if key not in known_v1_keys:
                new_config["custom_values"][key] = value

        return new_config

    def _load_server_config(self) -> Dict[str, Any]:
        """Loads server config, handles creation, and migration if needed."""
        config_file_path = self._server_specific_json_config_file_path
        server_json_config_subdir = self.server_config_dir

        try:
            os.makedirs(server_json_config_subdir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Failed to create directory '{server_json_config_subdir}': {e}"
            ) from e

        if not os.path.exists(config_file_path):
            self.logger.info(
                f"Server config file '{config_file_path}' not found. Initializing."
            )
            default_config = self._get_default_server_config()
            self._save_server_config(default_config)
            return default_config

        current_config: Dict[str, Any] = {}
        try:
            with open(config_file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():  # Empty file
                    self.logger.warning(
                        f"Server config file '{config_file_path}' is empty. Initializing."
                    )
                    current_config = self._get_default_server_config()
                    self._save_server_config(
                        current_config
                    )  # Save the initialized version
                    return current_config

                loaded_json = json.loads(content)
                if not isinstance(loaded_json, dict):
                    self.logger.warning(
                        f"Server config file '{config_file_path}' content is not a JSON object. "
                        "Attempting migration from presumed old format."
                    )
                    # Treat as old format; _migrate will handle it
                    current_config = self._migrate_server_config_v1_to_v2(
                        loaded_json if isinstance(loaded_json, dict) else {}
                    )
                    self._save_server_config(current_config)
                    return current_config
                current_config = loaded_json

        except ValueError as e:  # JSONDecodeError inherits from ValueError
            self.logger.warning(
                f"Failed to parse JSON from '{config_file_path}'. Assuming old/corrupt format and attempting migration. Error: {e}"
            )
            # Attempt migration with an empty dict if parsing failed completely
            # This will effectively create a new default config if old_config is unparsable
            current_config = self._migrate_server_config_v1_to_v2({})
            self._save_server_config(current_config)
            return current_config
        except OSError as e:
            raise FileOperationError(
                f"Failed to read config file '{config_file_path}': {e}"
            ) from e

        # Check schema version and migrate if structure is old (no version key)
        # or if version key indicates a known previous version we can migrate from.
        if current_config.get("config_schema_version") != SERVER_CONFIG_SCHEMA_VERSION:
            if (
                "config_schema_version" not in current_config
            ):  # Indicates v1 flat structure
                self.logger.info(
                    f"Old server config format (v1) detected in '{config_file_path}'. Migrating."
                )
                current_config = self._migrate_server_config_v1_to_v2(current_config)
                self._save_server_config(current_config)
            else:
                # Placeholder for future v2 -> v3, etc. migrations if needed
                self.logger.warning(
                    f"Server config schema version mismatch in '{config_file_path}'. "
                    f"Found {current_config.get('config_schema_version')}, expected {SERVER_CONFIG_SCHEMA_VERSION}. "
                    "Data might be incompatible. Using as is for now."
                )
        return current_config

    def _save_server_config(self, config_data: Dict[str, Any]):
        """Saves the server configuration data to its JSON file."""
        config_file_path = self._server_specific_json_config_file_path
        try:
            with open(config_file_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, sort_keys=True)
            self.logger.debug(
                f"Successfully wrote server config to '{config_file_path}'."
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to write server config file '{config_file_path}': {e}"
            ) from e
        except TypeError as e:  # For non-serializable data
            raise ConfigParseError(
                f"Server config data for '{self.server_name}' is not JSON serializable: {e}"
            ) from e

    def _manage_json_config(
        self,
        key: str,
        operation: str,
        value: Any = None,
    ) -> Optional[Any]:
        """A centralized helper to read/write to server's JSON config using dot-notation."""
        if not key:
            raise MissingArgumentError("Config key cannot be empty.")
        operation = str(operation).lower()
        if operation not in ["read", "write"]:
            raise UserInputError(
                f"Invalid operation: '{operation}'. Must be 'read' or 'write'."
            )

        current_config = (
            self._load_server_config()
        )  # Handles loading, creation, migration

        if operation == "read":
            d = current_config
            try:
                for k_part in key.split("."):
                    d = d[k_part]
                self.logger.debug(
                    f"Server Config Read: Key='{key}', Value='{d}' for '{self.server_name}'"
                )
                return d
            except (KeyError, TypeError):  # Path invalid or part of path not a dict
                self.logger.debug(
                    f"Server Config Read: Key='{key}' not found or path invalid for '{self.server_name}'. Returning None."
                )
                return None

        # Operation is "write"
        self.logger.debug(
            f"Server Config Write: Key='{key}', New Value='{value}' for '{self.server_name}'"
        )

        d = current_config
        keys_list = key.split(".")
        for k_part in keys_list[:-1]:  # Navigate to the parent dictionary
            d = d.setdefault(k_part, {})
            if not isinstance(d, dict):  # Should not happen with proper schema
                raise ConfigParseError(
                    f"Cannot create nested key '{key}': part '{k_part}' is not a dictionary in config for '{self.server_name}'."
                )
        d[keys_list[-1]] = value

        self._save_server_config(current_config)
        return None

    def get_version(self) -> str:
        """Retrieves the 'installed_version' from 'server_info'."""
        self.logger.debug(f"Getting installed version for server '{self.server_name}'.")
        try:
            version = self._manage_json_config(
                key="server_info.installed_version", operation="read"
            )
            return str(version) if version is not None else "UNKNOWN"
        except Exception as e:  # Catch broader errors from _manage_json_config if any
            self.logger.error(
                f"Error getting version for '{self.server_name}': {e}", exc_info=True
            )
            return "UNKNOWN"

    def set_version(self, version_string: str):
        """Sets the 'installed_version' in 'server_info'."""
        self.logger.debug(
            f"Setting installed version for '{self.server_name}' to '{version_string}'."
        )
        if not isinstance(version_string, str):
            raise UserInputError(
                f"Version for '{self.server_name}' must be a string, got {type(version_string)}."
            )
        self._manage_json_config(
            key="server_info.installed_version", operation="write", value=version_string
        )
        self.logger.info(f"Version for '{self.server_name}' set to '{version_string}'.")

    def get_autoupdate(self) -> str:
        """Retrieves the 'autoupdte' from 'settings'."""
        self.logger.debug(f"Getting autoupdate value for server '{self.server_name}'.")
        try:
            version = self._manage_json_config(
                key="settings.autoupdate", operation="read"
            )
            return str(version) if version is not None else "UNKNOWN"
        except Exception as e:  # Catch broader errors from _manage_json_config if any
            self.logger.error(
                f"Error getting value for '{self.server_name}': {e}", exc_info=True
            )
            return "UNKNOWN"

    def set_autoupdate(self, value: bool):
        """Sets the 'autoupdate' in 'settings'."""
        self.logger.debug(f"Setting autoupdate for '{self.server_name}' to '{value}'.")
        if not isinstance(value, bool):
            raise UserInputError(
                f"Vale for '{self.server_name}' must be a boolean, got {type(value)}."
            )
        self._manage_json_config(
            key="settings.autoupdate", operation="write", value=value
        )
        self.logger.info(f"Version for '{self.server_name}' set to '{value}'.")

    def get_status_from_config(self) -> str:
        """Retrieves the 'status' from 'server_info'."""
        self.logger.debug(
            f"Getting stored status for '{self.server_name}' from JSON config."
        )
        try:
            status = self._manage_json_config(
                key="server_info.status", operation="read"
            )
            return str(status) if status is not None else "UNKNOWN"
        except Exception as e:
            self.logger.error(
                f"Error getting status from JSON config for '{self.server_name}': {e}",
                exc_info=True,
            )
            return "UNKNOWN"

    def set_status_in_config(self, status_string: str):
        """Sets the 'status' in 'server_info'."""
        self.logger.debug(
            f"Setting status in JSON config for '{self.server_name}' to '{status_string}'."
        )
        if not isinstance(status_string, str):
            raise UserInputError(
                f"Status for '{self.server_name}' must be a string, got {type(status_string)}."
            )
        self._manage_json_config(
            key="server_info.status", operation="write", value=status_string
        )
        self.logger.info(
            f"Status in JSON config for '{self.server_name}' set to '{status_string}'."
        )

    def get_target_version(self) -> str:
        """Retrieves the 'target_version' from 'server_info'."""
        self.logger.debug(
            f"Getting stored target_version for '{self.server_name}' from JSON config."
        )
        try:
            version = self._manage_json_config(
                key="server_info.target_version", operation="read"
            )
            return str(version) if version is not None else "LATEST"
        except Exception as e:
            self.logger.error(
                f"Error getting target_version from config for '{self.server_name}': {e}",
                exc_info=True,
            )
            return "LATEST"

    def set_target_version(self, version_string: str):
        """Sets the 'target_version' in 'server_info'."""
        self.logger.debug(
            f"Setting target_version for '{self.server_name}' to '{version_string}'."
        )
        if not isinstance(version_string, str):
            raise UserInputError(
                f"target_version for '{self.server_name}' must be a string, got {type(version_string)}."
            )
        self._manage_json_config(
            key="server_info.target_version", operation="write", value=version_string
        )
        self.logger.info(
            f"target_version for '{self.server_name}' set to '{version_string}'."
        )

    def get_custom_config_value(self, key: str) -> Optional[Any]:
        """Retrieves a value from the 'custom_values' section."""
        self.logger.debug(
            f"Getting custom config key '{key}' for server '{self.server_name}'."
        )
        if not isinstance(key, str) or not key:
            raise UserInputError(
                f"Key for custom config on '{self.server_name}' must be a non-empty string."
            )
        # Key will be prefixed with "custom_values."
        full_key = f"custom_values.{key}"
        value = self._manage_json_config(key=full_key, operation="read")
        self.logger.debug(  # Changed from info to debug to reduce noise for simple gets
            f"Retrieved custom config for '{self.server_name}': Key='{key}', Value='{value}'."
        )
        return value

    def set_custom_config_value(self, key: str, value: Any):
        """Sets a key-value pair in the 'custom_values' section."""
        self.logger.debug(
            f"Setting custom config for '{self.server_name}': Key='{key}', Value='{value}'."
        )
        if not isinstance(key, str) or not key:
            raise UserInputError(
                f"Key for custom config on '{self.server_name}' must be a non-empty string."
            )
        full_key = f"custom_values.{key}"
        self._manage_json_config(key=full_key, operation="write", value=value)
        self.logger.info(  # Keep info for writes as they are significant actions
            f"Custom config for '{self.server_name}' set: Key='{key}', Value='{value}'."
        )

    @property
    def server_properties_path(self) -> str:
        """Returns the path to this server's `server.properties` file."""
        return os.path.join(self.server_dir, "server.properties")

    def get_world_name(self) -> str:
        """Reads the `level-name` property from `server.properties`.

        Returns:
            The name of the world as a string.

        Raises:
            AppFileNotFoundError: If `server.properties` does not exist.
            ConfigParseError: If the file cannot be read or `level-name` is
                missing or malformed.
        """
        self.logger.debug(
            f"Reading world name for server '{self.server_name}' from: {self.server_properties_path}"
        )
        if not os.path.isfile(self.server_properties_path):
            raise AppFileNotFoundError(
                self.server_properties_path, "server.properties file"
            )

        try:
            with open(self.server_properties_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("level-name="):
                        parts = line.split("=", 1)
                        if len(parts) == 2 and parts[1].strip():
                            world_name = parts[1].strip()
                            self.logger.debug(
                                f"Found world name (level-name): '{world_name}' for '{self.server_name}'"
                            )
                            return world_name
                        else:
                            raise ConfigParseError(
                                f"'level-name' property malformed or has empty value in {self.server_properties_path}"
                            )
        except OSError as e:
            raise ConfigParseError(
                f"Failed to read server.properties for '{self.server_name}': {e}"
            ) from e

        # This is reached if the loop completes without finding the level-name.
        raise ConfigParseError(
            f"'level-name' property not found in {self.server_properties_path}"
        )

    def get_status(self) -> str:
        """Determines the current operational status of the server.

        This method reconciles the actual runtime state of the server process
        with the status stored in the configuration file. For example, if the
        process is running but the config says 'STOPPED', it will update the
        config to 'RUNNING' and return 'RUNNING'.

        Returns:
            The reconciled status of the server as a string (e.g., 'RUNNING',
            'STOPPED', 'ERROR').
        """
        self.logger.debug(
            f"Determining overall status for server '{self.server_name}'."
        )

        actual_is_running = False
        try:
            # This method is expected to be provided by ServerProcessMixin.
            if not hasattr(self, "is_running"):
                self.logger.warning(
                    "is_running method not found. Falling back to stored config status."
                )
                return self.get_status_from_config()
            actual_is_running = self.is_running()
        except Exception as e_is_running_check:
            self.logger.error(
                f"Error calling self.is_running() for '{self.server_name}': {e_is_running_check}. Fallback to stored status."
            )
            return self.get_status_from_config()

        stored_status = self.get_status_from_config()
        final_status = "UNKNOWN"  # Default

        if actual_is_running:
            final_status = "RUNNING"
            # If there's a discrepancy, update the stored status.
            if stored_status != "RUNNING":
                self.logger.info(
                    f"Server '{self.server_name}' is running. Updating stored status from '{stored_status}' to RUNNING."
                )
                try:
                    self.set_status_in_config("RUNNING")
                except Exception as e_set_cfg:
                    self.logger.warning(
                        f"Failed to update stored status to RUNNING for '{self.server_name}': {e_set_cfg}"
                    )
        else:  # Not actually running.
            # If config thought it was running, correct it.
            if stored_status == "RUNNING":
                self.logger.info(
                    f"Server '{self.server_name}' not running but stored status was RUNNING. Updating to STOPPED."
                )
                final_status = "STOPPED"
                try:
                    self.set_status_in_config("STOPPED")
                except Exception as e_set_cfg:
                    self.logger.warning(
                        f"Failed to update stored status to STOPPED for '{self.server_name}': {e_set_cfg}"
                    )
            elif (
                stored_status == "UNKNOWN"
            ):  # If actual is not running and stored is unknown
                final_status = "STOPPED"
            else:  # Trust other stored statuses like UPDATING, ERROR, STARTING, STOPPING etc.
                final_status = stored_status

        self.logger.debug(
            f"Final determined status for '{self.server_name}': {final_status}"
        )
        return final_status
