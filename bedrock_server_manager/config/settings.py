# bedrock-server-manager/bedrock_server_manager/config/settings.py
import os
import json
import logging
from bedrock_server_manager.core.error import ConfigError
from bedrock_server_manager.utils import package_finder

logger = logging.getLogger("bedrock_server_manager")

package_name = "bedrock-server-manager"
executable_name = package_name

# Find bin/exe
EXPATH = package_finder.find_executable(package_name, executable_name)


class Settings:
    """
    Manages application settings, loading from and saving to a JSON config file.
    """

    def __init__(self):
        self._config_dir = self._get_app_config_dir()
        self.config_file_name = "script_config.json"
        self.config_path = os.path.join(self._config_dir, self.config_file_name)
        self._settings = {}  # Initialize empty settings
        self.load()  # Load settings

    def _get_app_data_dir(self):
        """
        Gets the application data directory, checking for a custom environment
        variable and falling back to the user's home directory.
        Creates the directory if it does not exist.
        """
        env_var_name = "BEDROCK_SERVER_MANAGER_DATA_DIR"
        data_dir = os.environ.get(env_var_name)

        if data_dir:
            logger.debug(f"Data Dir (from env): {data_dir}")
        else:
            data_dir = os.path.expanduser("~")
            logger.debug(
                f"{env_var_name} doesn't exist, defaulting to home directory: {data_dir}"
            )

        data_dir = os.path.join(data_dir, "bedrock-server-manager")
        os.makedirs(data_dir, exist_ok=True)  # Ensure directory exists
        return data_dir

    def _get_app_config_dir(self):
        """
        Returns the application configuration directory.
        Creates the directory if it does not exist.
        """
        app_config_dir = os.path.join(self._get_app_data_dir(), ".config")
        os.makedirs(app_config_dir, exist_ok=True)  # Ensure directory exists
        return app_config_dir

    @property
    def default_config(self):
        """
        Defines the default configuration values.
        """
        app_data_dir = self._get_app_data_dir()  # Get app data dir
        return {
            "BASE_DIR": os.path.join(app_data_dir, "servers"),
            "CONTENT_DIR": os.path.join(app_data_dir, "content"),
            "DOWNLOAD_DIR": os.path.join(app_data_dir, ".downloads"),
            "BACKUP_DIR": os.path.join(app_data_dir, "backups"),
            "LOG_DIR": os.path.join(app_data_dir, ".logs"),
            "BACKUP_KEEP": 3,
            "DOWNLOAD_KEEP": 3,
            "LOGS_KEEP": 3,
            "LOG_LEVEL": logging.INFO,
            "LOG_LEVEL": logging.INFO,
            "BEDROCK_SERVER_MANAGER_PORT": 5000,
        }

    def load(self):
        """Loads settings from the JSON config file, overriding defaults."""
        self._settings = self.default_config.copy()  # Start with defaults

        try:
            with open(self.config_path, "r") as f:
                user_config = json.load(f)
                self._settings.update(user_config)  # Override defaults
        except FileNotFoundError:
            logger.debug(
                "Configuration file not found. Creating with default settings."
            )
            self._write_config()  # Create default config
        except json.JSONDecodeError:
            logger.warning("Configuration file is not valid JSON. Overwriting...")
            self._write_config()  # Overwrite invalid config
        except OSError as e:
            raise ConfigError(f"Error reading config file: {e}") from e

    def _write_config(self):
        """Writes the current configuration to the config file."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._settings, f, indent=4)
            logger.debug(f"Configuration written to {self.config_path}")
        except OSError as e:
            raise ConfigError(f"Failed to write to config file: {e}") from e

    def get(self, key):
        """Gets a configuration setting."""
        return self._settings.get(key)

    def set(self, key, value):
        """Sets a configuration setting and saves it to the config file."""
        # Update the specific key in the *in-memory* settings.
        self._settings[key] = value
        # Write the *entire* updated configuration back to the file.
        self._write_config()


# --- Initialize Settings ---
settings = Settings()
