# bedrock_server_manager/api/plugins.py
"""
Provides API functions for managing plugin configurations and lifecycle.
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
register_api("reload_plugins", lambda **kwargs: reload_plugins(**kwargs))


def get_plugin_statuses() -> Dict[str, Any]:
    """
    Retrieves the statuses and metadata of all discovered plugins.
    """
    logger.debug("API: Attempting to get plugin statuses.")
    try:
        plugin_manager._synchronize_config_with_disk()
        # The config contains dicts like: {"enabled": bool, "description": str, "version": str}
        statuses = plugin_manager.plugin_config

        logger.info(f"API: Retrieved data for {len(statuses)} plugins.")
        return {"status": "success", "plugins": statuses.copy()}
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
    """
    if not plugin_name:
        raise UserInputError("Plugin name cannot be empty.")

    logger.info(f"API: Setting status for plugin '{plugin_name}' to {enabled}.")
    try:
        # Ensure the plugin manager's config is up-to-date with disk.
        # This will also ensure plugin_name exists if it's a valid plugin.
        plugin_manager._synchronize_config_with_disk()

        if plugin_name not in plugin_manager.plugin_config:
            logger.warning(
                f"API: Attempted to configure non-existent or undiscovered plugin '{plugin_name}'."
            )
            raise UserInputError(
                f"Plugin '{plugin_name}' not found or not discoverable."
            )

        # Check if the entry for plugin_name is indeed a dictionary
        # This is a defensive check, especially if _synchronize_config_with_disk has robust migration
        if not isinstance(plugin_manager.plugin_config.get(plugin_name), dict):
            logger.error(
                f"API: Plugin '{plugin_name}' has an invalid configuration format. Expected a dictionary."
            )

            return {
                "status": "error",
                "message": f"Plugin '{plugin_name}' has an invalid configuration. Please try reloading plugins.",
            }

        # Update the 'enabled' key within the plugin's config dictionary
        plugin_manager.plugin_config[plugin_name]["enabled"] = bool(enabled)
        plugin_manager._save_config()

        action = "enabled" if enabled else "disabled"
        logger.info(f"API: Plugin '{plugin_name}' successfully {action}.")
        return {
            "status": "success",
            "message": f"Plugin '{plugin_name}' has been {action}. Reload plugins for changes to take full effect.",
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


def reload_plugins() -> Dict[str, Any]:
    """
    Triggers the plugin manager to unload all active plugins and then reload
    all plugins based on the current configuration.
    """
    logger.info("API: Attempting to reload all plugins.")
    try:
        plugin_manager.reload()  # Call the reload method on the global instance
        logger.info("API: Plugins reloaded successfully.")
        return {
            "status": "success",
            "message": "Plugins have been reloaded successfully.",
        }
    except Exception as e:
        logger.error(f"API: Failed to reload plugins: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An unexpected error occurred during plugin reload: {e}",
        }
