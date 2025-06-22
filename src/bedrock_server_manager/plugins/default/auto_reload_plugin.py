# bedrock_server_manager/plugins/default/auto_reload_plugin.py
"""
Plugin for automatically sending reload commands to the server after certain configurations change.
"""
import logging
from bedrock_server_manager.plugins.plugin_base import PluginBase
from bedrock_server_manager.plugins.api_bridge import PluginAPI


class AutoReloadPlugin(PluginBase):
    """
    Handles sending reload commands (e.g., allowlist, permissions) after relevant changes.
    """

    def on_load(self):
        """Called by the Plugin Manager when the plugin is first loaded."""
        self.logger.info(
            "AutoReloadPlugin is loaded and active. It will handle automatic reloads after configuration changes."
        )

    def _is_server_running(self, server_name: str) -> bool:
        """
        Checks if the server is running using the registered 'get_server_running_status' API function.
        """
        try:
            response = self.api.get_server_running_status(server_name=server_name)
            if response and response.get("status") == "success":
                return response.get("is_running", False)
            self.logger.warning(
                f"Could not determine if server '{server_name}' is running for auto-reload. API response: {response}"
            )
        except AttributeError:
            self.logger.error(
                "Plugin API does not have 'get_server_running_status'. Cannot check server status for auto-reload."
            )
        except Exception as e:
            self.logger.error(
                f"Error checking server status for '{server_name}' for auto-reload: {e}",
                exc_info=True,
            )
        return False

    def _send_reload_command(self, server_name: str, command: str, context: str):
        """
        Helper function to send a reload command if the server is running.
        """
        if self._is_server_running(server_name):
            try:
                self.api.send_command(server_name=server_name, command=command)
                self.logger.info(
                    f"Sent '{command}' to server '{server_name}' after {context} change."
                )
            except AttributeError as e:
                self.logger.error(
                    f"API function error during auto-reload for '{server_name}': {e}. Is 'send_command' registered?"
                )
            except Exception as e:
                self.logger.warning(
                    f"Failed to send '{command}' to server '{server_name}' after {context} change: {e}",
                    exc_info=True,
                )
        else:
            self.logger.info(
                f"Server '{server_name}' is not running, skipping '{command}' after {context} change."
            )

    def after_allowlist_change(self, server_name: str, result: dict):
        """
        Called after an attempt to modify the allowlist completes.
        Reloads the allowlist if changes were successful.
        """
        self.logger.debug(
            f"'{self.name}' handling after_allowlist_change for '{server_name}'. Result: {result}"
        )

        if result.get("status") == "success":
            # For add_players_to_allowlist_api, result contains "added_count"
            added_count = result.get("added_count", 0)
            # For remove_players_from_allowlist, result contains "details": {"removed": [], ...}
            removed_players = result.get("details", {}).get("removed", [])

            if added_count > 0 or len(removed_players) > 0:
                self.logger.info(
                    f"Allowlist changed for '{server_name}', triggering reload."
                )
                self._send_reload_command(server_name, "allowlist reload", "allowlist")
            else:
                self.logger.info(
                    f"Allowlist operation successful for '{server_name}', but no actual changes to reload."
                )
        else:
            self.logger.info(
                f"Allowlist change for '{server_name}' was not successful, skipping reload."
            )

    def after_permission_change(self, server_name: str, xuid: str, result: dict):
        """
        Called after an attempt to change a player's permission completes.
        Reloads permissions if the change was successful.
        """
        self.logger.debug(
            f"'{self.name}' handling after_permission_change for '{server_name}', XUID '{xuid}'. Result: {result}"
        )
        if result.get("status") == "success":
            self._send_reload_command(server_name, "permission reload", "permission")
        else:
            self.logger.info(
                f"Permission change for '{server_name}' (XUID: {xuid}) was not successful, skipping reload."
            )
