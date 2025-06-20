# bedrock_server_manager/core/server/state_mixin.py
"""Provides the ServerStateMixin for the BedrockServer class.

This mixin is responsible for managing the persisted state of a server instance.
This includes its installed version, current status (e.g., RUNNING, STOPPED),
target version for updates, and other custom configuration values. These states
are typically stored in a server-specific JSON file. It also handles reading
the world name from `server.properties`.
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


class ServerStateMixin(BedrockServerBaseMixin):
    """A mixin for BedrockServer to read and write persistent state information.

    This class manages the server-specific JSON configuration file (which stores
    status, version, etc.) and reads essential properties like the world name
    from `server.properties`.
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

    def _manage_json_config(
        self,
        key: str,
        operation: str,
        value: Any = None,
    ) -> Optional[Any]:
        """A centralized helper to read or write to the server's JSON config.

        This internal method handles the file I/O for the server-specific JSON
        configuration file, including creating the directory, reading existing
        data, and writing updated data.

        Args:
            key: The JSON key to read or write.
            operation: The operation to perform ('read' or 'write').
            value: The value to write (required for 'write' operations).

        Returns:
            The value read from the file for 'read' operations, otherwise None.

        Raises:
            MissingArgumentError: If `key` is empty.
            UserInputError: If `operation` is invalid.
            FileOperationError: If file I/O fails.
            ConfigParseError: If the data to be written is not JSON serializable.
        """
        if not key:
            raise MissingArgumentError("Config key cannot be empty.")
        operation = str(operation).lower()
        if operation not in ["read", "write"]:
            raise UserInputError(
                f"Invalid operation: '{operation}'. Must be 'read' or 'write'."
            )

        config_file_path = self._server_specific_json_config_file_path
        server_json_config_subdir = self.server_config_dir

        self.logger.debug(
            f"Managing JSON config for server '{self.server_name}': Key='{key}', Op='{operation}', File='{config_file_path}'"
        )

        try:
            # Ensure the server's config subdirectory exists.
            os.makedirs(server_json_config_subdir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Failed to create directory '{server_json_config_subdir}': {e}"
            ) from e

        # Safely read the existing configuration file.
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
            except ValueError as e:
                self.logger.warning(
                    f"Failed to parse JSON from '{config_file_path}'. Will be overwritten on write. Error: {e}"
                )
            except OSError as e:
                raise FileOperationError(
                    f"Failed to read config file '{config_file_path}': {e}"
                ) from e

        # Perform the requested operation.
        if operation == "read":
            read_value = current_config.get(key)
            self.logger.debug(
                f"JSON Config Read: Key='{key}', Value='{read_value}' for '{self.server_name}'"
            )
            return read_value

        # Operation is "write".
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
            return None  # Write operation returns None.
        except OSError as e:
            raise FileOperationError(
                f"Failed to write config file '{config_file_path}': {e}"
            ) from e
        except TypeError as e:
            raise ConfigParseError(
                f"Config data for key '{key}' is not JSON serializable for '{self.server_name}'."
            ) from e

    def get_version(self) -> str:
        """Retrieves the 'installed_version' from the server's JSON config.

        Returns:
            The installed version string, or "UNKNOWN" if not set or an error occurs.
        """
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
        except (FileOperationError, Exception) as e:
            self.logger.error(
                f"Error getting version for '{self.server_name}': {e}",
                exc_info=isinstance(e, Exception),
            )
            return "UNKNOWN"

    def set_version(self, version_string: str):
        """Sets the 'installed_version' in the server's JSON config.

        Args:
            version_string: The version string to save.

        Raises:
            UserInputError: If `version_string` is not a string.
        """
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
        """Retrieves the 'status' from the server's JSON config.

        Returns:
            The stored status string (e.g., 'RUNNING', 'STOPPED'), or "UNKNOWN".
        """
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
        except (FileOperationError, Exception) as e:
            self.logger.error(
                f"Error getting status from JSON config for '{self.server_name}': {e}",
                exc_info=isinstance(e, Exception),
            )
            return "UNKNOWN"

    def set_status_in_config(self, status_string: str):
        """Sets the 'status' in the server's JSON config.

        Args:
            status_string: The status string to save (e.g., 'STARTING').

        Raises:
            UserInputError: If `status_string` is not a string.
        """
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
        """Retrieves the 'target_version' from the server's JSON config.

        Returns:
            The target version string, defaulting to "LATEST" if not set.
        """
        self.logger.debug(
            f"Getting stored target_version for server '{self.server_name}' from JSON config."
        )
        try:
            status = self._manage_json_config(key="target_version", operation="read")
            if status is None or not isinstance(status, str):
                self.logger.debug(
                    f"'target_version' for '{self.server_name}' is missing. Defaulting to LATEST."
                )
                return "LATEST"
            self.logger.debug(
                f"Retrieved target_version from JSON config for '{self.server_name}': '{status}'"
            )
            return status
        except (FileOperationError, Exception) as e:
            self.logger.error(
                f"Error getting target_version from JSON config for '{self.server_name}': {e}",
                exc_info=isinstance(e, Exception),
            )
            return "LATEST"  # Default to LATEST on error.

    def set_target_version(self, status_string: str):
        """Sets the 'target_version' in the server's JSON config.

        Args:
            status_string: The target version string to save (e.g., '1.20.10.01').

        Raises:
            UserInputError: If `status_string` is not a string.
        """
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
        """Retrieves a custom value from the server's JSON config.

        Args:
            key: The key of the custom value to retrieve.

        Returns:
            The retrieved value, which can be of any JSON-compatible type,
            or None if the key is not found.
        """
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

    def set_custom_config_value(self, key: str, value: Any):
        """Sets a custom key-value pair in the server's JSON config.

        Args:
            key: The key for the custom value.
            value: The value to save. Must be JSON-serializable.
        """
        self.logger.debug(
            f"Setting custom config for server '{self.server_name}': Key='{key}', Value='{value}'."
        )
        self._manage_json_config(key=key, operation="write", value=value)
        self.logger.info(
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
        final_status = "UNKNOWN"

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
            elif stored_status == "UNKNOWN":
                final_status = "STOPPED"  # A non-running server with an unknown status is considered stopped.
            else:
                final_status = (
                    stored_status  # Trust other statuses like UPDATING, ERROR, etc.
                )

        self.logger.debug(
            f"Final determined status for '{self.server_name}': {final_status}"
        )
        return final_status
