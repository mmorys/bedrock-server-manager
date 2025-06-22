# bedrock_server_manager/plugins/default/world_operation_notifications_plugin.py
"""
Example Plugin: Sends in-game notifications to players before the server's
world is changed, for example, through exporting, importing, or resetting.
"""
from bedrock_server_manager import PluginBase


class WorldOperationNotificationsPlugin(PluginBase):
    """
    For example, if an administrator starts a world export on a running server
    named 'survival_games', this plugin will send an in-game chat message like
    "Exporting world..." to notify any connected players of the operation.
    """

    def on_load(self):
        """
        Example: When the Plugin Manager loads this plugin, it will log a
        message like: 'WorldOperationNotificationsPlugin is loaded and active...'
        """
        self.logger.info(
            "WorldOperationNotificationsPlugin is loaded and active. It will handle notifications for world operations."
        )

    def _is_server_running(self, server_name: str) -> bool:
        """
        Example: Before sending a warning, this function checks if the server
        'survival_games' is actually online. It does this by calling an API
        function that might return `{'status': 'success', 'is_running': true}`.
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
        Example helper function: If `_is_server_running` confirms that the
        'survival_games' server is online, this function will send the provided
        message, for instance `say Exporting world...`, to the game.
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
        Example Scenario: An admin runs the command `bsm world export my_server`.
        Before the export process begins, this function is triggered and calls the
        helper to send the "Exporting world..." message to the game.
        """
        self.logger.debug(
            f"'{self.name}' handling before_world_export for '{server_name}' to '{export_dir}'"
        )
        self._send_world_operation_warning(server_name, "Exporting world...")

    def before_world_import(self, server_name: str, file_path: str):
        """
        Example Scenario: An admin runs `bsm world import my_server new_world.mcworld`.
        Before the existing world is overwritten, this function is triggered to send
        the "Importing world..." message.
        """
        self.logger.debug(
            f"'{self.name}' handling before_world_import for '{server_name}' from '{file_path}'"
        )
        self._send_world_operation_warning(server_name, "Importing world...")

    def before_world_reset(self, server_name: str):
        """
        Example Scenario: An admin runs the dangerous command `bsm world reset my_server`.
        This function is triggered just before the world files are deleted, sending a
        critical warning: "WARNING: Resetting world".
        """
        self.logger.debug(
            f"'{self.name}' handling before_world_reset for '{server_name}'"
        )
        self._send_world_operation_warning(server_name, "WARNING: Resetting world")
