# bedrock-server-manager/src/bedrock_server_manager/config/settings.py
"""
Manages application configuration settings.

Handles loading settings from a JSON file, providing defaults,
saving changes, and determining appropriate application directories.
"""

import os
import json
import logging
from bedrock_server_manager.error import ConfigError
from bedrock_server_manager.config.const import (
    package_name,
    env_name,
    get_installed_version,
)


logger = logging.getLogger(__name__)


class Settings:
    def __init__(self):
        logger.debug("Initializing Settings")
        self._app_data_dir_path = self._determine_app_data_dir()
        self._config_dir_path = self._determine_app_config_dir()
        self.config_file_name = "script_config.json"
        self.config_path = os.path.join(self._config_dir_path, self.config_file_name)

        self._version_val = get_installed_version()

        self._settings = {}
        self.load()

    def _determine_app_data_dir(self) -> str:
        env_var_name = f"{env_name}_DATA_DIR"
        data_dir = os.environ.get(env_var_name)
        if not data_dir:
            data_dir = os.path.join(os.path.expanduser("~"), f"{package_name}")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def _determine_app_config_dir(self) -> str:
        config_dir = os.path.join(self._app_data_dir_path, ".config")
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    @property
    def default_config(self) -> dict:
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
        self._settings = self.default_config.copy()
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    self._settings.update(user_config)
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            logger.warning(
                f"Error loading config {self.config_path}: {e}. Using defaults/writing new."
            )
            self._write_config()  # Create/overwrite with defaults if load fails
        self._ensure_dirs_exist()

    def _ensure_dirs_exist(self) -> None:
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
                    raise ConfigError(
                        f"Could not create critical directory: {dir_path}"
                    ) from e

    def _write_config(self) -> None:
        try:
            os.makedirs(self._config_dir_path, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=4, sort_keys=True)
        except (OSError, TypeError) as e:
            raise ConfigError(f"Failed to write configuration: {e}") from e

    def get(self, key: str, default=None):
        return self._settings.get(key, default)

    def set(self, key: str, value) -> None:
        if key in self._settings and self._settings[key] == value:
            return
        self._settings[key] = value
        logger.info(f"Setting '{key}' updated to '{value}'. Saving configuration.")
        self._write_config()

    # Property getters for BSM
    @property
    def config_dir(self) -> str:
        return self._config_dir_path

    @property
    def app_data_dir(self) -> str:
        return self._app_data_dir_path

    @property
    def version(self) -> str:
        return self._version_val


settings = Settings()
