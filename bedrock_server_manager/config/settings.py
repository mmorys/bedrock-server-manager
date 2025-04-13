# bedrock-server-manager/bedrock_server_manager/config/settings.py
"""
Manages application configuration settings.

Handles loading settings from a JSON file, providing defaults,
saving changes, and determining appropriate application directories.
"""

import os
import json
import logging
from importlib.metadata import version, PackageNotFoundError
from bedrock_server_manager.error import ConfigError
from bedrock_server_manager.utils import package_finder

logger = logging.getLogger("bedrock_server_manager")

# --- Package Constants ---
package_name = "bedrock-server-manager"
executable_name = package_name
app_name = package_name.replace("-", " ").title()
env_name = package_name.replace("-", "_").upper()

# --- Package Information ---
EXPATH = package_finder.find_executable(package_name, executable_name)

try:
    # Attempt to get the installed package version
    __version__ = version(package_name)
except PackageNotFoundError:
    # Fallback if the package isn't installed
    __version__ = "0.0.0"
    logger.warning(
        f"Could not find package metadata for '{package_name}'. Version set to {__version__}."
    )


class Settings:
    """
    Manages application settings, loading from and saving to a JSON config file.

    Attributes:
        config_file_name (str): The name of the configuration file.
        config_path (str): The full path to the configuration file.
    """

    def __init__(self):
        """
        Initializes the Settings object.

        Determines configuration paths and loads existing settings
        or creates a default configuration file.
        """
        logger.debug("Initializing Settings")
        self._config_dir = self._get_app_config_dir()
        self.config_file_name = "script_config.json"
        self.config_path = os.path.join(self._config_dir, self.config_file_name)
        self._settings = {}  # Initialize empty settings dict
        self.load()  # Load settings from file or defaults

    def _get_app_data_dir(self) -> str:
        """
        Determines the application's data directory.

        Checks for a custom environment variable ({ENV_NAME}_DATA_DIR)
        and falls back to a directory within the user's home folder
        if the variable is not set. Creates the directory if it
        does not exist.

        Returns:
            str: The absolute path to the application data directory.
        """
        env_var_name = f"{env_name}_DATA_DIR"
        data_dir = os.environ.get(env_var_name)

        if data_dir:
            logger.info(
                f"Using custom data directory from environment variable {env_var_name}: {data_dir}"
            )
        else:
            # Default to ~/bedrock-server-manager
            data_dir = os.path.join(os.path.expanduser("~"), f"{package_name}")
            logger.info(
                f"Environment variable {env_var_name} not set. "
                f"Using default data directory: {data_dir}"
            )

        # Ensure the directory exists
        try:
            os.makedirs(data_dir, exist_ok=True)
            logger.debug(f"Ensured application data directory exists: {data_dir}")
        except OSError as e:
            logger.error(f"Failed to create data directory {data_dir}: {e}")
            # Decide if this is fatal - for now, let's raise ConfigError
            raise ConfigError(
                f"Could not create required data directory: {data_dir}"
            ) from e
        return data_dir

    def _get_app_config_dir(self) -> str:
        """
        Determines the application's configuration directory.

        This is typically a '.config' subdirectory within the main
        application data directory. Creates the directory if it
        does not exist.

        Returns:
            str: The absolute path to the application configuration directory.
        """
        app_data_dir = self._get_app_data_dir()
        app_config_dir = os.path.join(app_data_dir, ".config")

        # Ensure the directory exists
        try:
            os.makedirs(app_config_dir, exist_ok=True)
            logger.debug(
                f"Ensured application config directory exists: {app_config_dir}"
            )
        except OSError as e:
            logger.error(f"Failed to create config directory {app_config_dir}: {e}")
            raise ConfigError(
                f"Could not create required config directory: {app_config_dir}"
            ) from e
        return app_config_dir

    @property
    def default_config(self) -> dict:
        """
        Provides the default configuration values for the application.

        Returns:
            dict: A dictionary containing the default settings.
        """
        logger.debug("Generating default configuration settings.")
        # Get base data dir dynamically
        app_data_dir = self._get_app_data_dir()
        return {
            "BASE_DIR": os.path.join(app_data_dir, "servers"),
            "CONTENT_DIR": os.path.join(app_data_dir, "content"),
            "DOWNLOAD_DIR": os.path.join(app_data_dir, ".downloads"),
            "BACKUP_DIR": os.path.join(app_data_dir, "backups"),
            "LOG_DIR": os.path.join(app_data_dir, ".logs"),
            "BACKUP_KEEP": 3,
            "DOWNLOAD_KEEP": 3,
            "LOGS_KEEP": 3,
            "LOG_LEVEL": logging.INFO,  # Default logging level
            "WEB_PORT": 11325,  # Default port for web server
            "TOKEN_EXPIRES_WEEKS": 4,  # Defailt jwt token expire time
        }

    def load(self) -> None:
        """
        Loads settings from the JSON config file.

        Starts with default settings, then overrides them with values
        from the config file if it exists and is valid JSON.
        If the file doesn't exist, it's created with defaults.
        If the file is invalid, it's overwritten with defaults.
        """
        logger.debug(f"Attempting to load settings from: {self.config_path}")
        self._settings = self.default_config.copy()  # Start with defaults

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                logger.debug(f"Successfully read user config file: {self.config_path}")
                # Validate user_config keys if necessary here
                self._settings.update(user_config)  # Override defaults with user values
                logger.debug("Merged user config with defaults.")
        except FileNotFoundError:
            logger.info(
                f"Configuration file not found at {self.config_path}. Creating with default settings."
            )
            self._write_config()  # Create default config file
        except json.JSONDecodeError as e:
            logger.warning(
                f"Configuration file {self.config_path} contains invalid JSON: {e}. Overwriting with default settings."
            )
            self._write_config()  # Overwrite invalid config with defaults
        except OSError as e:
            logger.error(f"Error reading configuration file {self.config_path}: {e}")
            raise ConfigError(
                f"Error reading configuration file: {self.config_path}"
            ) from e
        except Exception as e:  # Catch unexpected errors during load/update
            logger.error(f"Unexpected error loading configuration: {e}")
            raise ConfigError(
                "An unexpected error occurred while loading configuration."
            ) from e

        # Ensure essential directories exist based on final loaded settings
        self._ensure_dirs_exist()
        logger.debug(f"Settings loaded successfully: {self._settings}")

    def _ensure_dirs_exist(self) -> None:
        """Ensures essential directories defined in settings exist."""
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
                    logger.debug(f"Ensured directory exists: {dir_path}")
                except OSError as e:
                    # Raise config error
                    logger.error(
                        f"Could not create configured directory {dir_path}: {e}"
                    )
                    raise ConfigError(
                        f"Could not create critical directory: {dir_path}"
                    ) from e
            elif not dir_path:
                logger.warning(
                    f"A required directory path setting is missing or empty in configuration."
                )
            elif not isinstance(dir_path, str):
                logger.warning(
                    f"Directory path setting expected string, got {type(dir_path)}: {dir_path}"
                )

    def _write_config(self) -> None:
        """Writes the current in-memory settings to the JSON config file."""
        logger.debug(f"Attempting to write configuration to: {self.config_path}")
        try:
            # Ensure the config directory exists before writing
            os.makedirs(self._config_dir, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(
                    self._settings, f, indent=4, sort_keys=True
                )  # Sort keys for consistency
            logger.info(f"Configuration successfully written to {self.config_path}")
        except OSError as e:
            logger.error(f"Failed to write configuration file {self.config_path}: {e}")
            raise ConfigError(
                f"Failed to write configuration file: {self.config_path}"
            ) from e
        except TypeError as e:
            logger.error(f"Configuration contains non-serializable data: {e}")
            raise ConfigError("Configuration contains non-serializable data.") from e

    def get(self, key: str, default=None):
        """
        Retrieves a configuration setting by its key.

        Args:
            key (str): The key of the setting to retrieve.
            default: The value to return if the key is not found. Defaults to None.

        Returns:
            The value of the setting, or the default value if the key is not found.
        """
        value = self._settings.get(key, default)
        logger.debug(f"Retrieved setting '{key}': {value}")
        return value

    def set(self, key: str, value) -> None:
        """
        Sets a configuration setting and immediately saves it to the config file.

        Args:
            key (str): The key of the setting to set.
            value: The value to assign to the setting.
        """
        logger.debug(f"Attempting to set setting '{key}' to '{value}'")
        if key in self._settings and self._settings[key] == value:
            logger.debug(f"Value for '{key}' is already '{value}'. No change made.")
            return  # Avoid unnecessary write if value hasn't changed

        self._settings[key] = value
        logger.info(f"Setting '{key}' updated to '{value}'. Saving configuration.")
        self._write_config()  # Persist the change immediately


# --- Global Settings Instance ---
# Create a single, globally accessible instance of the Settings class.
# This instance will be loaded upon import and can be used throughout the application.
logger.debug("Creating global settings object.")
settings = Settings()
