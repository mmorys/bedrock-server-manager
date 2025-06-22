# bedrock_server_manager/api/plugins_config.py
"""
Provides API functions for managing plugin configurations (enable/disable).
"""
import logging
from typing import Dict, Any

from bedrock_server_manager import plugin_manager
from bedrock_server_manager.plugins.api_bridge import register_api
from bedrock_server_manager.error import UserInputError

logger = logging.getLogger(__name__)

# --- API REGISTRATION FOR PLUGINS ---
register_api("get_plugin_statuses", lambda **kwargs: get_plugin_statuses(**kwargs))
register_api("set_plugin_status", lambda **kwargs: set_plugin_status(**kwargs))


def get_plugin_statuses() -> Dict[str, Any]:
    """
    Retrieves the statuses of all discovered plugins.

    This function synchronizes the plugin configuration with discoverable
    plugins on disk and then returns their current enabled/disabled states.

    Returns:
        A dictionary with operation status and plugin data.
        On success: {"status": "success", "plugins": {"plugin_name": True/False, ...}}
        On error: {"status": "error", "message": "..."}
    """
    logger.debug("API: Attempting to get plugin statuses.")
    try:
        # Ensure the plugin manager's internal config is up-to-date with disk
        plugin_manager._synchronize_config_with_disk()

        # plugin_config is Dict[str, bool]
        statuses = plugin_manager.plugin_config

        logger.info(f"API: Retrieved {len(statuses)} plugin statuses.")
        return {"status": "success", "plugins": statuses.copy()}  # Return a copy
    except Exception as e:
        logger.error(f"API: Failed to get plugin statuses: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to get plugin statuses: {e}"}


def set_plugin_status(plugin_name: str, enabled: bool) -> Dict[str, Any]:
    """
    Sets the enabled/disabled status for a specific plugin.

    Args:
        plugin_name: The name of the plugin to configure.
        enabled: True to enable the plugin, False to disable it.

    Returns:
        A dictionary with operation status and a message.
        On success: {"status": "success", "message": "..."}
        On error: {"status": "error", "message": "..."}
    """
    if not plugin_name:
        raise UserInputError("Plugin name cannot be empty.")

    logger.info(
        f"API: Attempting to set status for plugin '{plugin_name}' to {enabled}."
    )
    try:
        # Synchronize first to ensure the plugin_name is known if it's a valid file
        plugin_manager._synchronize_config_with_disk()

        if plugin_name not in plugin_manager.plugin_config:
            logger.warning(
                f"API: Attempted to configure non-existent or undiscovered plugin '{plugin_name}'."
            )
            raise UserInputError(
                f"Plugin '{plugin_name}' not found or not discoverable."
            )

        plugin_manager.plugin_config[plugin_name] = bool(enabled)
        plugin_manager._save_config()

        action = "enabled" if enabled else "disabled"
        logger.info(f"API: Plugin '{plugin_name}' successfully {action}.")
        return {
            "status": "success",
            "message": f"Plugin '{plugin_name}' has been {action}.",
        }
    except UserInputError as e:  # Catch specific UserInputError to re-raise
        raise
    except Exception as e:
        logger.error(
            f"API: Failed to set status for plugin '{plugin_name}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Failed to set status for plugin '{plugin_name}': {e}",
        }
