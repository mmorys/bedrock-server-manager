# bedrock_server_manager/plugins/default/world_operation_notifications_plugin.py
"""
Plugin for sending notifications before world operations like export, import, and reset.
"""
import logging
from bedrock_server_manager.plugins.plugin_base import PluginBase
from bedrock_server_manager.plugins.api_bridge import PluginAPI


class WorldOperationNotificationsPlugin(PluginBase):
    """
    Handles sending 'say' commands to the server before world operations.
    """

    def on_load(self):
        """Called by the Plugin Manager when the plugin is first loaded."""
        self.logger.info(
            "WorldOperationNotificationsPlugin is loaded and active. It will handle notifications for world operations."
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
                f"Could not determine if server '{server_name}' is running. API response: {response}"
            )
        except AttributeError:
            self.logger.error(
                "Plugin API does not have 'get_server_running_status'. Cannot check server status."
            )
        except Exception as e:
            self.logger.error(
                f"Error checking server status for '{server_name}': {e}", exc_info=True
            )
        return False

    def _send_world_operation_warning(self, server_name: str, operation_message: str):
        """
        Helper function to send a warning message if the server is running.
        """
        if self._is_server_running(server_name):
            try:
                self.api.send_command(
                    server_name=server_name, command=f"say {operation_message}"
                )
                self.logger.info(
                    f"Sent world operation warning to '{server_name}': {operation_message}"
                )
            except AttributeError as e:
                self.logger.error(
                    f"API function error during world op warning for '{server_name}': {e}. Is 'send_command' or 'get_server_running_status' registered?"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to send world operation warning to '{server_name}': {e}",
                    exc_info=True,
                )
        else:
            self.logger.info(
                f"Server '{server_name}' is not running, skipping world operation warning: {operation_message}"
            )

    def before_world_export(self, server_name: str, export_dir: str):
        """
        Called before a server's world is exported.
        """
        self.logger.debug(
            f"'{self.name}' handling before_world_export for '{server_name}' to '{export_dir}'"
        )
        self._send_world_operation_warning(server_name, "Exporting world...")

    def before_world_import(self, server_name: str, file_path: str):
        """
        Called before a .mcworld file is imported to a server.
        """
        self.logger.debug(
            f"'{self.name}' handling before_world_import for '{server_name}' from '{file_path}'"
        )
        self._send_world_operation_warning(server_name, "Importing world...")

    def before_world_reset(self, server_name: str):
        """
        Called before a server's active world directory is deleted.
        """
        self.logger.debug(
            f"'{self.name}' handling before_world_reset for '{server_name}'"
        )
        self._send_world_operation_warning(server_name, "WARNING: Resetting world")
