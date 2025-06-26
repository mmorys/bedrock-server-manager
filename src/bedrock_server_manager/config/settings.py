# bedrock_server_manager/config/settings.py
"""Manages application-wide configuration settings.

This module provides the `Settings` class, which is responsible for loading
settings from a JSON file, providing default values for missing keys, saving
changes back to the file, and determining the appropriate application data and
configuration directories based on the environment.

The configuration is stored in a nested JSON format. Settings are accessed
programmatically using dot-notation (e.g., `settings.get('paths.base')`).
"""

import os
import json
import logging
import collections.abc
from typing import Any, Dict

from bedrock_server_manager.error import ConfigurationError
from bedrock_server_manager.config.const import (
    package_name,
    env_name,
    get_installed_version,
)

logger = logging.getLogger(__name__)

# The schema version for the configuration file. Used for migrations.
CONFIG_SCHEMA_VERSION = 2
NEW_CONFIG_FILE_NAME = "bedrock_server_manager.json"
OLD_CONFIG_FILE_NAME = "script_config.json"


def deep_merge(source: Dict, destination: Dict) -> Dict:
    """
    Recursively merges the `source` dictionary into the `destination` dictionary.

    Nested dictionaries are merged, while other values in `source` overwrite
    those in `destination`.

    Args:
        source: The dictionary with new or updated values.
        destination: The dictionary to be updated.

    Returns:
        The merged dictionary (`destination`).
    """
    for key, value in source.items():
        if isinstance(value, collections.abc.Mapping):
            node = destination.setdefault(key, {})
            deep_merge(value, node)
        else:
            destination[key] = value
    return destination


class Settings:
    """Manages loading, accessing, and saving application settings.

    This class acts as a single source of truth for configuration. It handles
    the logic for determining application data and config directories, provides
    sensible defaults in a nested structure, and ensures critical directories
    exist. It offers simple `get` and `set` methods using dot-notation for
    interacting with the configuration values, persisting any changes to a JSON file.
    """

    def __init__(self):
        """Initializes the Settings object.

        This constructor determines the application's file paths, loads any
        existing configuration from `script_config.json`, migrates old config
        formats if detected, creates a default configuration if one doesn't exist,
        and ensures all necessary directories are present on the filesystem.
        """
        logger.debug("Initializing Settings")
        # Determine the primary application data and config directories.
        self._app_data_dir_path = self._determine_app_data_dir()
        self._config_dir_path = self._determine_app_config_dir()
        self.config_file_name = NEW_CONFIG_FILE_NAME
        self._migrate_config_filename()
        self.config_path = os.path.join(self._config_dir_path, self.config_file_name)

        # Get the installed package version.
        self._version_val = get_installed_version()

        # Load settings from the config file or create a default one.
        self._settings: Dict[str, Any] = {}
        self.load()

    def _migrate_config_filename(self):
        """
        Checks for the old config filename and renames it to the new one.
        This is a one-time operation for existing installations.
        """
        old_config_path = os.path.join(self._config_dir_path, OLD_CONFIG_FILE_NAME)
        new_config_path = os.path.join(self._config_dir_path, NEW_CONFIG_FILE_NAME)

        if os.path.exists(old_config_path) and not os.path.exists(new_config_path):
            logger.info(
                f"Found old configuration file '{OLD_CONFIG_FILE_NAME}'. "
                f"Migrating to '{NEW_CONFIG_FILE_NAME}'..."
            )
            try:
                os.rename(old_config_path, new_config_path)
                logger.info(
                    "Successfully migrated configuration file name. "
                    f"The old file '{OLD_CONFIG_FILE_NAME}' has been renamed."
                )
            except OSError as e:
                raise ConfigurationError(
                    f"Failed to rename configuration file from '{old_config_path}' to "
                    f"'{new_config_path}'. Please check file permissions."
                ) from e

    def _determine_app_data_dir(self) -> str:
        """Determines the main application data directory.

        It prioritizes the `BSM_DATA_DIR` environment variable if set.
        Otherwise, it defaults to a 'bedrock-server-manager' directory in the
        user's home folder. The directory is created if it doesn't exist.

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
        """Determines the application's configuration directory.

        This directory is typically named `.config` and is nested within the main
        application data directory. It is created if it doesn't exist.

        Returns:
            The absolute path to the application configuration directory.
        """
        config_dir = os.path.join(self._app_data_dir_path, ".config")
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    @property
    def default_config(self) -> dict:
        """Provides the default configuration values for the application.

        These defaults are used when a configuration file is not found or a
        specific setting is missing. Paths are constructed dynamically based on
        the determined application data directory.

        Returns:
            A dictionary of default settings with a nested structure.
        """
        app_data_dir_val = self._app_data_dir_path
        return {
            "config_version": CONFIG_SCHEMA_VERSION,
            "paths": {
                "servers": os.path.join(app_data_dir_val, "servers"),
                "content": os.path.join(app_data_dir_val, "content"),
                "downloads": os.path.join(app_data_dir_val, ".downloads"),
                "backups": os.path.join(app_data_dir_val, "backups"),
                "plugins": os.path.join(app_data_dir_val, "plugins"),
                "logs": os.path.join(app_data_dir_val, ".logs"),
            },
            "retention": {
                "backups": 3,
                "downloads": 3,
                "logs": 3,
            },
            "logging": {
                "file_level": logging.INFO,
                "cli_level": logging.WARN,
            },
            "web": {
                "host": ["127.0.0.1", "::1"],
                "port": 11325,
                "token_expires_weeks": 4,
                "threads": 8,
            },
        }

    def load(self):
        """Loads settings from the JSON configuration file.

        If the file doesn't exist, it's created with defaults. If an old, flat
        config format is detected, it is automatically migrated to the new
        nested structure. User settings are then merged over the defaults.
        """
        # Always start with a fresh copy of the defaults to build upon.
        self._settings = self.default_config

        if not os.path.exists(self.config_path):
            logger.info(
                f"Configuration file not found at {self.config_path}. "
                "Creating with default settings."
            )
            self._write_config()
        else:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)

                # Check for old config format and migrate if necessary.
                if "config_version" not in user_config:
                    self._migrate_v1_to_v2(user_config)
                    # Reload config from the newly migrated file
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        user_config = json.load(f)

                # Deep merge user settings into the default settings.
                deep_merge(user_config, self._settings)

            except (ValueError, OSError) as e:
                logger.warning(
                    f"Could not load config file at {self.config_path}: {e}. "
                    "Using default settings. A new config will be saved on the next settings change."
                )

        self._ensure_dirs_exist()

    def _migrate_v1_to_v2(self, old_config: dict):
        """Migrates a flat v1 configuration to the nested v2 format.

        This method backs up the old configuration file before overwriting it with
        the new, structured format, preserving all user-defined values.

        Args:
            old_config: The loaded dictionary from the old, flat config file.

        Raises:
            ConfigurationError: If backing up the old config file fails.
        """
        logger.info(
            "Old configuration format (v1) detected. Migrating to new nested format (v2)..."
        )
        # 1. Back up the old file
        backup_path = f"{self.config_path}.v1.bak"
        try:
            os.rename(self.config_path, backup_path)
            logger.info(f"Old configuration file backed up to {backup_path}")
        except OSError as e:
            raise ConfigurationError(
                f"Failed to back up old config file to {backup_path}. "
                "Migration aborted. Please check file permissions."
            ) from e

        # 2. Create the new config by starting with defaults and overwriting with old values
        new_config = self.default_config
        key_map = {
            # Old Key: ("category", "new_key")
            "BASE_DIR": ("paths", "servers"),
            "CONTENT_DIR": ("paths", "content"),
            "DOWNLOAD_DIR": ("paths", "downloads"),
            "BACKUP_DIR": ("paths", "backups"),
            "PLUGIN_DIR": ("paths", "plugins"),
            "LOG_DIR": ("paths", "logs"),
            "BACKUP_KEEP": ("retention", "backups"),
            "DOWNLOAD_KEEP": ("retention", "downloads"),
            "LOGS_KEEP": ("retention", "logs"),
            "FILE_LOG_LEVEL": ("logging", "file_level"),
            "CLI_LOG_LEVEL": ("logging", "cli_level"),
            "WEB_PORT": ("web", "port"),
            "TOKEN_EXPIRES_WEEKS": ("web", "token_expires_weeks"),
        }
        for old_key, (category, new_key) in key_map.items():
            if old_key in old_config:
                new_config[category][new_key] = old_config[old_key]

        # 3. Save the new configuration file
        self._settings = new_config
        self._write_config()
        logger.info("Successfully migrated configuration to the new format.")

    def _ensure_dirs_exist(self):
        """Ensures that all critical directories specified in the settings exist.

        Raises:
            ConfigurationError: If a directory cannot be created.
        """
        dirs_to_check = [
            self.get("paths.base"),
            self.get("paths.content"),
            self.get("paths.downloads"),
            self.get("paths.backups"),
            self.get("paths.plugins"),
            self.get("paths.logs"),
        ]
        for dir_path in dirs_to_check:
            if dir_path and isinstance(dir_path, str):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except OSError as e:
                    raise ConfigurationError(
                        f"Could not create critical directory: {dir_path}"
                    ) from e

    def _write_config(self):
        """Writes the current settings dictionary to the JSON configuration file.

        Raises:
            ConfigurationError: If writing the configuration fails.
        """
        try:
            os.makedirs(self._config_dir_path, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=4, sort_keys=True)
        except (OSError, TypeError) as e:
            raise ConfigurationError(f"Failed to write configuration: {e}") from e

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting value using dot-notation for nested access.

        Example: `settings.get("paths.base")`

        Args:
            key: The dot-separated configuration key.
            default: The value to return if the key is not found.

        Returns:
            The value associated with the key, or the default value.
        """
        d = self._settings
        try:
            for k in key.split("."):
                d = d[k]
            return d
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
        """Sets a configuration value using dot-notation and saves the change.

        Intermediate dictionaries are created if they do not exist. The
        configuration is only written to disk if the new value is different
        from the old one.

        Example: `settings.set("retention.backups", 5)`

        Args:
            key: The dot-separated configuration key to set.
            value: The value to associate with the key.
        """
        # Avoid writing to file if the value hasn't changed.
        if self.get(key) == value:
            return

        keys = key.split(".")
        d = self._settings
        for k in keys[:-1]:
            d = d.setdefault(k, {})

        d[keys[-1]] = value
        logger.info(f"Setting '{key}' updated to '{value}'. Saving configuration.")
        self._write_config()

    @property
    def config_dir(self) -> str:
        """The absolute path to the application's configuration directory."""
        return self._config_dir_path

    @property
    def app_data_dir(self) -> str:
        """The absolute path to the application's main data directory."""
        return self._app_data_dir_path

    @property
    def version(self) -> str:
        """The installed version of the application package."""
        return self._version_val


# A singleton instance of the Settings class, used throughout the application.
settings = Settings()
