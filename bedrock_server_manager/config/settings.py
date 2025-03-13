# bedrock-server-manager/bedrock_server_manager/config/settings.py
import os
import json
import logging
from bedrock_server_manager.core.error import ConfigError
from bedrock_server_manager.utils import package_finder

logger = logging.getLogger("bedrock_server_manager")

package_name = "bedrock-server-manager"
executable_name = "bedrock-server-manager"

# Find bin/exe
EXPATH = package_finder.find_executable(package_name, executable_name)


# --- Determine Default Data and Config Directories ---
def get_app_data_dir():
    """
    Gets the application data directory, checking for a custom environment
    variable and falling back to the user's home directory if not found.
    The directory is *not* created here; that's handled later in the script.

    Returns:
        str: The path to the application data directory.
    """
    env_var_name = "BEDROCK_SERVER_MANAGER_DATA_DIR"
    data_dir = os.environ.get(env_var_name)

    if data_dir:

        return data_dir

    # Default to the user's home directory
    return os.path.expanduser("~")


# Get the application data directory:
APP_DATA_DIR = get_app_data_dir()
APP_DATA_DIR = os.path.join(APP_DATA_DIR, "bedrock-server-manager")
APP_CONFIG_DIR = os.path.join(APP_DATA_DIR, ".config")

# --- Default Configuration Values ---
# These are the *defaults*.  The JSON file will override these.
DEFAULT_CONFIG = {
    "BASE_DIR": os.path.join(APP_DATA_DIR, "servers"),
    "CONTENT_DIR": os.path.join(APP_DATA_DIR, "content"),
    "DOWNLOAD_DIR": os.path.join(APP_DATA_DIR, ".downloads"),
    "BACKUP_DIR": os.path.join(APP_DATA_DIR, "backups"),
    "LOG_DIR": os.path.join(APP_DATA_DIR, ".logs"),
    "GITHUB_REPO": "DMedina559/bedrock-server-manager",
    "GITHUB_TOKEN": "",  # USE ENV
    "RELEASE_TYPE": "latest",
    "BACKUP_KEEP": 3,
    "DOWNLOAD_KEEP": 3,
    "LOG_LEVEL": logging.INFO,
    "BEDROCK_SERVER_MANAGER_PORT": 5000,
}

CONFIG_DIR = APP_CONFIG_DIR
CONFIG_FILE_NAME = "script_config.json"
CONFIG_PATH = os.path.join(CONFIG_DIR, CONFIG_FILE_NAME)


def load_settings():
    """Loads settings from the JSON config file, overriding defaults."""
    config = DEFAULT_CONFIG.copy()  # Start with defaults

    # Create config directory if it doesn't exist
    os.makedirs(CONFIG_DIR, exist_ok=True)

    try:
        with open(CONFIG_PATH, "r") as f:
            user_config = json.load(f)
            config.update(user_config)  # Override defaults with user settings
    except FileNotFoundError:
        logger.info("Configuration file not found. Creating with default settings.")
        _write_default_config()  # write the config
    except json.JSONDecodeError:
        logger.warning("Configuration file is not valid JSON.  Using defaults.")
        _write_default_config()  # Overwrite invalid config file
    except OSError as e:
        raise ConfigError(f"Error reading config file: {e}") from e
    web_app_port_env = os.environ.get(
        "BEDROCK_SERVER_MANAGER_PORT"
    )  # Get BEDROCK_SERVER_MANAGER_PORT from env  <--- GET ENV VAR
    if web_app_port_env:
        try:
            config["BEDROCK_SERVER_MANAGER_PORT"] = int(
                web_app_port_env
            )  # Override from env if set and valid int  <--- OVERRIDE IF ENV VAR SET
        except ValueError:
            logger.warning(
                f"Invalid BEDROCK_SERVER_MANAGER_PORT environment variable value: '{web_app_port_env}'. Using config file or default value."
            )

    return config


def _write_default_config():
    """Writes the default configuration to the config file."""
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        logger.info(f"Default configuration written to {CONFIG_PATH}")
    except OSError as e:
        raise ConfigError(f"Failed to write default config: {e}") from e


# Load the settings
_settings = load_settings()

# --- Access Settings as Attributes ---
BASE_DIR = _settings["BASE_DIR"]
BACKUP_KEEP = _settings["BACKUP_KEEP"]
DOWNLOAD_KEEP = _settings["DOWNLOAD_KEEP"]
RELEASE_TYPE = _settings["RELEASE_TYPE"]
GITHUB_TOKEN = _settings["GITHUB_TOKEN"]
GITHUB_REPO = _settings["GITHUB_REPO"]
CONTENT_DIR = _settings["CONTENT_DIR"]
DOWNLOAD_DIR = _settings["DOWNLOAD_DIR"]
BACKUP_DIR = _settings["BACKUP_DIR"]
LOG_DIR = _settings["LOG_DIR"]
LOG_LEVEL = _settings["LOG_LEVEL"]
BEDROCK_SERVER_MANAGER_PORT = _settings["BEDROCK_SERVER_MANAGER_PORT"]


def get(key):
    """Gets a configuration setting."""
    return _settings.get(key)


def set(key, value):
    """Sets a configuration setting and saves it to the config file."""
    global _settings, BASE_DIR, BACKUP_KEEP, DOWNLOAD_KEEP, RELEASE_TYPE, GITHUB_TOKEN, GITHUB_REPO, CONTENT_DIR, DOWNLOAD_DIR, BACKUP_DIR, LOG_DIR, LOG_LEVEL, BEDROCK_SERVER_MANAGER_PORT
    # Load the *existing* configuration from the file.
    config = load_settings()

    # Update the specific key.
    config[key] = value

    # Write the updated configuration back to the file.
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=4)
    except OSError as e:
        raise ConfigError(f"Failed to write to config file: {e}") from e

    # Reload settings to update cached values
    _settings = load_settings()
    BASE_DIR = _settings["BASE_DIR"]
    BACKUP_KEEP = _settings["BACKUP_KEEP"]
    DOWNLOAD_KEEP = _settings["DOWNLOAD_KEEP"]
    RELEASE_TYPE = _settings["RELEASE_TYPE"]
    GITHUB_TOKEN = _settings["GITHUB_TOKEN"]
    GITHUB_REPO = _settings["GITHUB_REPO"]
    CONTENT_DIR = _settings["CONTENT_DIR"]
    DOWNLOAD_DIR = _settings["DOWNLOAD_DIR"]
    BACKUP_DIR = _settings["BACKUP_DIR"]
    LOG_DIR = _settings["LOG_DIR"]
    LOG_LEVEL = _settings["LOG_LEVEL"]
    BEDROCK_SERVER_MANAGER_PORT = _settings["BEDROCK_SERVER_MANAGER_PORT"]
