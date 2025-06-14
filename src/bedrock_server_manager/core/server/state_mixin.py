# bedrock_server_manager/core/server/state_mixin.py
"""
Provides the ServerStateMixin class for BedrockServer.

This mixin is responsible for managing the persisted state of a server instance,
including its installed version, current status (RUNNING, STOPPED, etc.),
target version for updates, and custom configuration values. These are typically
stored in a server-specific JSON configuration file. It also handles reading
the world name from server.properties.
"""
import os
import json
from typing import Optional, Any, Dict, TYPE_CHECKING

# Local imports
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import (
    MissingArgumentError,
    UserInputError,
    FileOperationError,
    ConfigParseError,
    AppFileNotFoundError,
)


class ServerStateMixin(BedrockServerBaseMixin):
    """
    A mixin for the BedrockServer class that handles reading and writing
    persistent state information for the server. This includes managing the
    server-specific JSON configuration file (for status, version, etc.)
    and reading the world name from `server.properties`.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the ServerStateMixin.

        Calls super().__init__ for proper multiple inheritance setup.
        Relies on attributes (like server_name, _server_specific_config_dir,
        server_dir, logger) from the base class.
        """
        super().__init__(*args, **kwargs)

    @property
    def _server_specific_json_config_file_path(self) -> str:
        """Path to this server's JSON configuration file (e.g., MyServerName_config.json)."""
        return os.path.join(
            self._server_specific_config_dir, f"{self.server_name}_config.json"
        )

    def _manage_json_config(
        self,
        key: str,
        operation: str,
        value: Any = None,  # Default for read, required by caller for write
    ) -> Optional[Any]:
        """
        Reads or writes a specific key-value pair in this server's JSON config file.
        """
        if not key:
            raise MissingArgumentError("Config key cannot be empty.")
        operation = str(operation).lower()
        if operation not in ["read", "write"]:
            raise UserInputError(
                f"Invalid operation: '{operation}'. Must be 'read' or 'write'."
            )

        config_file_path = self._server_specific_json_config_file_path
        server_json_config_subdir = self._server_specific_config_dir

        self.logger.debug(
            f"Managing JSON config for server '{self.server_name}': Key='{key}', Op='{operation}', File='{config_file_path}'"
        )

        try:
            os.makedirs(server_json_config_subdir, exist_ok=True)
        except OSError as e:
            self.logger.error(
                f"Failed to create server JSON config subdir '{server_json_config_subdir}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to create directory '{server_json_config_subdir}': {e}"
            ) from e

        current_config: Dict[str, Any] = {}
        if os.path.exists(config_file_path):
            try:
                with open(config_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        loaded_json = json.loads(content)
                        if isinstance(loaded_json, dict):
                            current_config = loaded_json
                        else:
                            self.logger.warning(
                                f"Config file '{config_file_path}' is not a JSON object. Will be overwritten on write."
                            )
                            # current_config remains {}
            except ValueError as e:
                self.logger.warning(
                    f"Failed to parse JSON from '{config_file_path}'. Will be overwritten on write. Error: {e}"
                )
                # current_config remains {}
            except OSError as e:  # Read error
                self.logger.error(
                    f"Failed to read config file '{config_file_path}': {e}",
                    exc_info=True,
                )
                raise FileOperationError(
                    f"Failed to read config file '{config_file_path}': {e}"
                ) from e

        # Perform Operation
        if operation == "read":
            read_value = current_config.get(key)
            self.logger.debug(
                f"JSON Config Read: Key='{key}', Value='{read_value}' for '{self.server_name}'"
            )
            return read_value

        # Operation is "write"
        self.logger.debug(
            f"JSON Config Write: Key='{key}', New Value='{value}' for '{self.server_name}'"
        )
        current_config[key] = value
        try:
            with open(config_file_path, "w", encoding="utf-8") as f:
                json.dump(current_config, f, indent=4, sort_keys=True)
            self.logger.debug(
                f"Successfully wrote updated JSON config to '{config_file_path}'."
            )
            return None  # Write operation returns None
        except OSError as e:  # Write error
            self.logger.error(
                f"Failed to write JSON config to '{config_file_path}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to write config file '{config_file_path}': {e}"
            ) from e
        except TypeError as e:  # JSON serialization error
            self.logger.error(
                f"Failed to serialize config data for writing (key: {key}): {e}",
                exc_info=True,
            )
            raise ConfigParseError(
                f"Config data for key '{key}' is not JSON serializable for '{self.server_name}'."
            ) from e

    def get_version(self) -> str:
        """Retrieves the 'installed_version' from this server's JSON configuration file."""
        self.logger.debug(f"Getting installed version for server '{self.server_name}'.")
        try:
            version = self._manage_json_config(
                key="installed_version", operation="read"
            )
            if version is None or not isinstance(version, str):
                self.logger.debug(
                    f"'installed_version' for '{self.server_name}' is missing or not a string. Defaulting to UNKNOWN."
                )
                return "UNKNOWN"
            self.logger.debug(
                f"Retrieved version for '{self.server_name}': '{version}'"
            )
            return version
        except FileOperationError as e:
            self.logger.error(
                f"File error getting version for '{self.server_name}': {e}"
            )
            return "UNKNOWN"
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error getting version for '{self.server_name}': {e_unexp}",
                exc_info=True,
            )
            return "UNKNOWN"  # Default to UNKNOWN on error

    def set_version(self, version_string: str) -> None:
        """Sets the 'installed_version' in this server's JSON configuration file."""
        self.logger.debug(
            f"Setting installed version for server '{self.server_name}' to '{version_string}'."
        )
        if not isinstance(version_string, str):
            raise UserInputError(
                f"Version for '{self.server_name}' must be a string, got {type(version_string)}."
            )
        self._manage_json_config(
            key="installed_version", operation="write", value=version_string
        )
        self.logger.info(f"Version for '{self.server_name}' set to '{version_string}'.")

    def get_status_from_config(self) -> str:
        """Retrieves the 'status' from this server's JSON configuration file."""
        self.logger.debug(
            f"Getting stored status for server '{self.server_name}' from JSON config."
        )
        try:
            status = self._manage_json_config(key="status", operation="read")
            if status is None or not isinstance(status, str):
                self.logger.debug(
                    f"'status' for '{self.server_name}' from JSON config is missing or not a string. Defaulting to UNKNOWN."
                )
                return "UNKNOWN"
            self.logger.debug(
                f"Retrieved status from JSON config for '{self.server_name}': '{status}'"
            )
            return status
        except FileOperationError as e:
            self.logger.error(
                f"File error getting status from JSON config for '{self.server_name}': {e}"
            )
            return "UNKNOWN"
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error getting status from JSON config for '{self.server_name}': {e_unexp}",
                exc_info=True,
            )
            return "UNKNOWN"  # Default to UNKNOWN on error

    def set_status_in_config(self, status_string: str) -> None:
        """Sets the 'status' in this server's JSON configuration file."""
        self.logger.debug(
            f"Setting status in JSON config for server '{self.server_name}' to '{status_string}'."
        )
        if not isinstance(status_string, str):
            raise UserInputError(
                f"Status for '{self.server_name}' must be a string, got {type(status_string)}."
            )
        self._manage_json_config(key="status", operation="write", value=status_string)
        self.logger.info(
            f"Status in JSON config for '{self.server_name}' set to '{status_string}'."
        )

    def get_target_version(self) -> str:
        """Retrieves the 'target_version' from this server's JSON configuration file."""
        self.logger.debug(
            f"Getting stored target_version for server '{self.server_name}' from JSON config."
        )
        try:
            status = self._manage_json_config(key="target_version", operation="read")
            if status is None or not isinstance(status, str):
                self.logger.debug(
                    f"'target_version' for '{self.server_name}' from JSON config is missing or not a string. Defaulting to LATEST."
                )
                return "LATEST"
            self.logger.debug(
                f"Retrieved target_version from JSON config for '{self.server_name}': '{status}'"
            )
            return status
        except FileOperationError as e:
            self.logger.error(
                f"File error getting target_version from JSON config for '{self.server_name}': {e}"
            )
            return "UNKNOWN"
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error getting target_version from JSON config for '{self.server_name}': {e_unexp}",
                exc_info=True,
            )
            return "UNKNOWN"  # Default to UNKNOWN on error (or LATEST if more appropriate for target_version)

    def set_target_version(self, status_string: str) -> None:
        """Sets the 'target_version' in this server's JSON configuration file."""
        self.logger.debug(
            f"Setting target_version in JSON config for server '{self.server_name}' to '{status_string}'."
        )
        if not isinstance(status_string, str):
            raise UserInputError(
                f"target_version for '{self.server_name}' must be a string, got {type(status_string)}."
            )
        self._manage_json_config(
            key="target_version", operation="write", value=status_string
        )
        self.logger.info(
            f"target_version in JSON config for '{self.server_name}' set to '{status_string}'."
        )

    def get_custom_config_value(self, key: str) -> Optional[Any]:
        """Retrieves a custom value from this server's JSON configuration file."""
        self.logger.debug(
            f"Getting custom config key '{key}' for server '{self.server_name}'."
        )
        if not isinstance(key, str):
            raise UserInputError(
                f"Key '{key}' for custom config on '{self.server_name}' must be a string, got {type(key)}."
            )
        value = self._manage_json_config(key=key, operation="read")
        self.logger.info(
            f"Retrieved custom config for '{self.server_name}': Key='{key}', Value='{value}'."
        )
        return value

    def set_custom_config_value(self, key: str, value: Any) -> None:
        """Sets a custom key-value pair in this server's JSON configuration file."""
        self.logger.debug(
            f"Setting custom config for server '{self.server_name}': Key='{key}', Value='{value}'."
        )
        self._manage_json_config(key=key, operation="write", value=value)
        self.logger.info(
            f"Custom config for '{self.server_name}' set: Key='{key}', Value='{value}'."
        )

    @property
    def server_properties_path(self) -> str:
        """Returns the path to this server's server.properties file."""
        return os.path.join(self.server_dir, "server.properties")

    def get_world_name(self) -> str:
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
                        else:  # Malformed or empty value
                            err_msg = f"'level-name' property malformed or has empty value in {self.server_properties_path}"
                            self.logger.error(err_msg)
                            raise ConfigParseError(err_msg)
        except OSError as e:
            self.logger.error(
                f"Failed to read {self.server_properties_path}: {e}", exc_info=True
            )
            raise ConfigParseError(
                f"Failed to read server.properties for '{self.server_name}': {e}"
            ) from e

        # If loop completes without returning
        final_err_msg = (
            f"'level-name' property not found in {self.server_properties_path}"
        )
        self.logger.error(final_err_msg)
        raise ConfigParseError(final_err_msg)

    def get_status(self) -> str:
        """
        Determines the current operational status of the server.
        Checks running state via self.is_running() (from ProcessMixin),
        then synchronizes with and consults the stored JSON config status.
        """

        self.logger.debug(
            f"Determining overall status for server '{self.server_name}'."
        )

        actual_is_running = False
        try:
            # is_running() method is expected to be provided by ServerProcessMixin
            if not hasattr(self, "is_running"):
                self.logger.warning(
                    "is_running method not found on self. Cannot determine live status. Falling back to stored config."
                )
                return (
                    self.get_status_from_config()
                )  # Fallback if ProcessMixin not fully integrated yet
            actual_is_running = self.is_running()
        except Exception as e_is_running_check:
            # If is_running itself fails, log it and rely on stored status.
            self.logger.error(
                f"Error calling self.is_running() for '{self.server_name}': {e_is_running_check}. Fallback to stored status."
            )
            return self.get_status_from_config()

        stored_status = self.get_status_from_config()

        final_status = "UNKNOWN"

        if actual_is_running:
            final_status = "RUNNING"
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
        else:  # Not actually running
            if (
                stored_status == "RUNNING"
            ):  # Discrepancy: config says running, but it's not
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
            elif stored_status == "UNKNOWN":
                final_status = (
                    "STOPPED"  # Default to STOPPED if unknown and not running
                )
            else:
                final_status = stored_status  # Trust stored status if not RUNNING (e.g. UPDATING, ERROR, STOPPED)

        self.logger.debug(
            f"Final determined status for '{self.server_name}': {final_status}"
        )
        return final_status
