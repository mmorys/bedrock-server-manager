# bedrock_server_manager/api/settings.py
"""Provides an API for interacting with the global application settings.

This module contains functions exposed to the plugin system for reading,
writing, and reloading configuration values in the main
`bedrock_server_manager.json` file.
"""
import logging
from typing import Any, Dict

# Plugin system imports to bridge API functionality.
from bedrock_server_manager.plugins.api_bridge import plugin_method
from bedrock_server_manager.logging import setup_logging

# Local application imports.
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    BSMError,
    MissingArgumentError,
)

logger = logging.getLogger(__name__)


@plugin_method("get_global_setting")
def get_global_setting(key: str) -> Dict[str, Any]:
    """Reads a single value from the global application settings.

    Args:
        key: The dot-notation key for the setting (e.g., "paths.backups").

    Returns:
        A dictionary containing the operation status and the retrieved value.
        On success: `{"status": "success", "value": ...}`.
        On error: `{"status": "error", "message": "..."}`.

    Raises:
        MissingArgumentError: If `key` is not provided.
    """
    if not key:
        raise MissingArgumentError("A 'key' must be provided to get a setting.")

    logger.debug(f"API: Reading global setting '{key}'.")
    try:
        retrieved_value = settings.get(key)
        logger.debug(f"API: Successfully read global setting '{key}'.")
        return {
            "status": "success",
            "value": retrieved_value,
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading global setting '{key}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"An unexpected error occurred while reading setting '{key}': {e}",
        }


@plugin_method("get_all_global_settings")
def get_all_global_settings() -> Dict[str, Any]:
    """Reads the entire global application settings configuration.

    Returns:
        A dictionary containing the operation status and all settings data.
        On success: `{"status": "success", "data": ...}`.
        On error: `{"status": "error", "message": "..."}`.
    """
    logger.debug("API: Reading all global settings.")
    try:
        # Accessing _settings is an internal detail, but this API provides
        # a controlled public interface to it. A copy is returned.
        all_settings = settings._settings.copy()
        logger.debug("API: Successfully retrieved all global settings.")
        return {
            "status": "success",
            "data": all_settings,
        }
    except Exception as e:
        logger.error(f"API: Unexpected error reading all global settings: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An unexpected error occurred: {e}",
        }


def set_global_setting(key: str, value: Any) -> Dict[str, Any]:
    """Writes a value to the global application settings.

    Args:
        key: The dot-notation key for the setting to update (e.g., "web.port").
        value: The new value to set. This can be any JSON-serializable type.

    Returns:
        A dictionary containing the operation status and a message.
        On success: `{"status": "success", "message": "..."}`.
        On error: `{"status": "error", "message": "..."}`.

    Raises:
        MissingArgumentError: If `key` is not provided.
    """
    if not key:
        raise MissingArgumentError("A 'key' must be provided to set a setting.")

    logger.debug(f"API: Writing to global setting. Key='{key}', Value='{value}'")
    try:
        settings.set(key, value)
        logger.info(f"API: Successfully wrote to global setting '{key}'.")
        return {
            "status": "success",
            "message": f"Global setting '{key}' updated successfully.",
        }
    except BSMError as e:
        logger.error(
            f"API: Configuration error setting global key '{key}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Failed to set setting '{key}': {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error setting global key '{key}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"An unexpected error occurred while setting '{key}': {e}",
        }


def reload_global_settings() -> Dict[str, str]:
    """
    Forces a reload of settings and logging config from the file.

    This is useful if `bedrock_server_manager.json` has been edited
    manually and the application needs to pick up the changes without restarting.
    It will reload both the settings values and re-apply the logging configuration
    (e.g., to change log levels).

    Returns:
        A dictionary containing the operation status and a message.
    """
    logger.info("API: Received request to reload global settings and logging.")
    try:
        # Step 1: Reload the settings from the file
        settings.reload()
        logger.info("API: Global settings successfully reloaded.")

        # Step 2: Re-apply logging configuration with the new settings
        logger.info("API: Re-applying logging configuration...")
        setup_logging(
            log_dir=settings.get("paths.logs"),
            log_keep=settings.get("retention.logs"),
            file_log_level=settings.get("logging.file_level"),
            cli_log_level=settings.get("logging.cli_level"),
            force_reconfigure=True  # Crucial flag to force removal of old handlers
        )
        logger.info("API: Logging configuration successfully re-applied.")

        return {
            "status": "success",
            "message": "Global settings and logging configuration have been reloaded.",
        }
    except BSMError as e:
        logger.error(f"API: Error reloading settings/logging: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"A configuration error occurred during reload: {e}",
        }
    except Exception as e:
        logger.error(f"API: Unexpected error reloading settings/logging: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An unexpected error occurred during reload: {e}",
        }