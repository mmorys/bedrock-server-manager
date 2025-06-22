# bedrock_server_manager/plugins/default/server_lifecycle_notifications_plugin.py
"""
Plugin for sending notifications and managing delays during server lifecycle events.
"""
import time
import logging
from bedrock_server_manager.plugins.plugin_base import PluginBase
from bedrock_server_manager.plugins.api_bridge import PluginAPI


class ServerLifecycleNotificationsPlugin(PluginBase):
    """
    Handles notifications and delays for server start, stop, restart, delete, and update.
    """

    def __init__(self, plugin_name: str, api: PluginAPI, logger: logging.Logger):
        super().__init__(plugin_name, api, logger)
        # Default stop delay, can be made configurable later if needed
        self.stop_delay_seconds = 10
        self.post_stop_delay_seconds = 3  # For restart and delete scenarios

    def on_load(self):
        """Called by the Plugin Manager when the plugin is first loaded."""
        self.logger.info(
            "ServerLifecycleNotificationsPlugin is loaded and active. It will handle server lifecycle notifications and delays."
        )

    def _is_server_running(self, server_name: str) -> bool:
        """
        Checks if the server is running using the registered API.
        Checks if the server is running using the registered 'get_server_running_status' API function.
        """
        try:
            response = self.api.get_server_running_status(server_name=server_name)
            # Expected response: {"status": "success", "is_running": bool}
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
        return (
            False  # Default to false if status cannot be determined or an error occurs
        )

    def before_server_stop(self, server_name: str):
        """
        Called just before a server stop is attempted.
        Sends a warning message and waits for a configured delay.
        """
        self.logger.debug(
            f"'{self.name}' handling before_server_stop for '{server_name}'"
        )
        if self._is_server_running(server_name):
            warning_message = (
                f"say Server is stopping in {self.stop_delay_seconds} seconds..."
            )
            try:
                self.api.send_command(server_name=server_name, command=warning_message)
                self.logger.info(
                    f"Sent shutdown warning to '{server_name}': {warning_message}"
                )

                # Perform the delay
                self.logger.info(
                    f"Waiting {self.stop_delay_seconds} seconds before server '{server_name}' stops."
                )
                time.sleep(self.stop_delay_seconds)

            except AttributeError as e:
                self.logger.error(
                    f"API function error during before_server_stop for '{server_name}': {e}. Is 'send_command' registered?"
                )
            except (
                Exception
            ) as e:  # Catch other potential errors from send_command or time.sleep
                self.logger.error(
                    f"Error during before_server_stop for '{server_name}': {e}",
                    exc_info=True,
                )
        else:
            self.logger.info(
                f"Server '{server_name}' is not running, skipping stop notification and delay."
            )

    def after_server_stop(self, server_name: str, result: dict):
        """
        Called just after a server stop has been attempted.
        Adds a small delay, useful in restart or delete scenarios.
        """
        self.logger.debug(
            f"'{self.name}' handling after_server_stop for '{server_name}'"
        )

        if result.get("status") == "success":
            self.logger.info(
                f"Waiting {self.post_stop_delay_seconds} seconds after server '{server_name}' stopped."
            )
            time.sleep(self.post_stop_delay_seconds)
        else:
            self.logger.info(
                f"Server '{server_name}' stop attempt was not successful, skipping post-stop delay."
            )

    def before_delete_server_data(self, server_name: str):
        """
        Called before server data is deleted.
        Sends a critical warning message.
        """
        self.logger.debug(
            f"'{self.name}' handling before_delete_server_data for '{server_name}'"
        )
        if self._is_server_running(
            server_name
        ):  # Check if running before sending command
            try:
                self.api.send_command(
                    server_name=server_name,
                    command="say WARNING: Server is being deleted permanently!",
                )
                self.logger.info(f"Sent data deletion warning to '{server_name}'.")
            except AttributeError as e:
                self.logger.error(
                    f"API function error during before_delete_server_data for '{server_name}': {e}. Is 'send_command' registered?"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to send data deletion warning to '{server_name}': {e}",
                    exc_info=True,
                )
        else:
            self.logger.info(
                f"Server '{server_name}' is not running, skipping deletion warning message."
            )

    def before_server_update(self, server_name: str, target_version: str):
        """
        Called before an existing server is updated.
        Sends a notification message.
        """
        self.logger.debug(
            f"'{self.name}' handling before_server_update for '{server_name}' to version '{target_version}'"
        )
        if self._is_server_running(server_name):  # Check if running
            try:
                self.api.send_command(
                    server_name=server_name, command="say Server is updating now..."
                )
                self.logger.info(f"Sent server update notification to '{server_name}'.")
            except AttributeError as e:
                self.logger.error(
                    f"API function error during before_server_update for '{server_name}': {e}. Is 'send_command' registered?"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to send update notification to '{server_name}': {e}",
                    exc_info=True,
                )
        else:
            self.logger.info(
                f"Server '{server_name}' is not running, skipping update notification."
            )

    # Small delay after server start
    def after_server_start(self, server_name: str, result: dict):
        if result.get("status") == "success":
            try:
                time.sleep(3)  # Wait for server to stabilize after start
            except Exception as e:
                self.logger.warning(
                    f"Could wait 3 seconds after '{server_name}' start: {e}"
                )
