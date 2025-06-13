# bedrock_server_manager/config/settings.py
"""
Manages application configuration settings.

Handles loading settings from a JSON file, providing defaults,
saving changes, and determining appropriate application directories.
"""

import os
import json
from typing import Any
import logging
from bedrock_server_manager.error import ConfigurationError
from bedrock_server_manager.config.const import (
    package_name,
    env_name,
    get_installed_version,
)


logger = logging.getLogger(__name__)


class Settings:
    """
    Manages application settings, loading from and saving to a JSON configuration file.

    This class handles the determination of application data and configuration
    directories, provides default settings, and ensures critical directories exist.
    It offers methods to get and set configuration values.
    """

    def __init__(self):
        """
        Initializes the Settings object.

        Determines application paths, loads existing configuration or creates
        a default one, and ensures necessary directories are present.
        """
        logger.debug("Initializing Settings")
        self._app_data_dir_path = self._determine_app_data_dir()
        self._config_dir_path = self._determine_app_config_dir()
        self.config_file_name = "script_config.json"
        self.config_path = os.path.join(self._config_dir_path, self.config_file_name)

        self._version_val = get_installed_version()

        self._settings = {}
        self.load()

    def _determine_app_data_dir(self) -> str:
        """
        Determines the main application data directory.

        Uses the BSM_DATA_DIR environment variable if set, otherwise defaults
        to a directory named 'bedrock-server-manager' in the user's home folder.
        Creates the directory if it doesn't exist.

        Returns:
            The absolute path to the application data directory.
        """
        env_var_name = f"{env_name}_DATA_DIR"
        data_dir = os.environ.get(env_var_name)
        if not data_dir:
            data_dir = os.path.join(os.path.expanduser("~"), f"{package_name}")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def _determine_app_config_dir(self) -> str:
        """
        Determines the application's '.config' directory, nested within the app data directory.

        Creates the directory if it doesn't exist.

        Returns:
            The absolute path to the application configuration directory.
        """
        config_dir = os.path.join(self._app_data_dir_path, ".config")
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    @property
    def default_config(self) -> dict:
        """
        Provides the default configuration values for the application.

        These are used when a configuration file is not found or is invalid.
        Paths are constructed based on the determined application data directory.

        Returns:
            A dictionary of default settings.
        """
        app_data_dir_val = self._app_data_dir_path
        return {
            "BASE_DIR": os.path.join(app_data_dir_val, "servers"),
            "CONTENT_DIR": os.path.join(app_data_dir_val, "content"),
            "DOWNLOAD_DIR": os.path.join(app_data_dir_val, ".downloads"),
            "BACKUP_DIR": os.path.join(app_data_dir_val, "backups"),
            "LOG_DIR": os.path.join(app_data_dir_val, ".logs"),
            "BACKUP_KEEP": 3,
            "DOWNLOAD_KEEP": 3,
            "LOGS_KEEP": 3,
            "FILE_LOG_LEVEL": logging.INFO,
            "CLI_LOG_LEVEL": logging.WARN,
            "WEB_PORT": 11325,
            "TOKEN_EXPIRES_WEEKS": 4,
        }

    def load(self) -> None:
        """
        Loads settings from the JSON configuration file.

        If the file doesn't exist, it initializes with default settings and
        writes a new configuration file. If the file is invalid, it logs a
        warning but continues with defaults.
        """
        # Always start with a fresh copy of the defaults
        default_settings = self.default_config.copy()

        if os.path.exists(self.config_path):
            # File exists, try to load and merge it
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    # Update defaults with user settings
                    default_settings.update(user_config)
            except (ValueError, OSError) as e:
                # File is corrupt or unreadable, log a warning and use defaults
                logger.warning(
                    f"Could not load config file at {self.config_path}: {e}. "
                    "Using default settings. The corrupt file will be overwritten on the next settings change."
                )
        else:
            # File does NOT exist, so create it with default values
            logger.info(
                f"Configuration file not found at {self.config_path}. Creating with default settings."
            )
            self._settings = default_settings
            self._write_config()

        # Set the final settings and ensure directories exist
        self._settings = default_settings
        self._ensure_dirs_exist()

    def _ensure_dirs_exist(self) -> None:
        """
        Ensures that all critical directories specified in the settings exist.

        Creates any missing directories.

        Raises:
            ConfigurationError: If a directory cannot be created.
        """
        dirs_to_check = [
            self.get("BASE_DIR"),
            self.get("CONTENT_DIR"),
            self.get("DOWNLOAD_DIR"),
            self.get("BACKUP_DIR"),
            self.get("LOG_DIR"),
        ]
        for dir_path in dirs_to_check:
            if dir_path and isinstance(dir_path, str):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except OSError as e:
                    raise ConfigurationError(
                        f"Could not create critical directory: {dir_path}"
                    ) from e

    def _write_config(self) -> None:
        """
        Writes the current settings dictionary to the JSON configuration file.

        Raises:
            ConfigurationError: If writing the configuration fails.
        """
        try:
            os.makedirs(self._config_dir_path, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=4, sort_keys=True)
        except (OSError, TypeError) as e:
            raise ConfigurationError(f"Failed to write configuration: {e}") from e

    def get(self, key: str, default=None) -> Any:
        """
        Retrieves a setting value for the given key.

        Args:
            key: The configuration key to retrieve.
            default: The default value to return if the key is not found.

        Returns:
            The value associated with the key, or the default value.
        """
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Sets a configuration value for the given key and saves the configuration.

        If the new value is the same as the existing value, no action is taken.

        Args:
            key: The configuration key to set.
            value: The value to associate with the key.
        """
        if key in self._settings and self._settings[key] == value:
            return
        self._settings[key] = value
        logger.info(f"Setting '{key}' updated to '{value}'. Saving configuration.")
        self._write_config()

    # Property getters for BSM
    @property
    def config_dir(self) -> str:
        """The application's configuration directory path."""
        return self._config_dir_path

    @property
    def app_data_dir(self) -> str:
        """The application's main data directory path."""
        return self._app_data_dir_path

    @property
    def version(self) -> str:
        """The installed version of the application package."""
        return self._version_val


settings = Settings()
