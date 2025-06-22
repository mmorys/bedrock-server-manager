# bedrock_server_manager/plugins/default/server_lifecycle_notifications_plugin.py
"""
Example Plugin: Sends in-game messages and adds delays during key server
events like stopping, starting, or updating.
"""
import time
from bedrock_server_manager import PluginBase


class ServerLifecycleNotificationsPlugin(PluginBase):
    """
    For example, when a user stops a server, this plugin sends an in-game
    warning message like "Server is stopping in 10 seconds..." and then
    pauses for 10 seconds before allowing the server to shut down. This gives
    players time to log off safely.
    """

    def on_load(self):
        """
        Example: When the Plugin Manager first loads this plugin, it sets default
        delay values and logs a message: 'ServerLifecycleNotificationsPlugin is
        loaded and active...'
        """
        self.stop_delay_seconds = 10
        self.post_stop_delay_seconds = (
            3  # Example: Used for restarts to ensure the port is free.
        )
        self.logger.info(
            "ServerLifecycleNotificationsPlugin is loaded and active. It will handle server lifecycle notifications and delays."
        )

    def _is_server_running(self, server_name: str) -> bool:
        """
        Example: Before sending a message, this function checks if the server
        'my_server' is actually online. It calls an API function that might
        return `{"status": "success", "is_running": true}`.
        """
        try:
            response = self.api.get_server_running_status(server_name=server_name)
            # For example, a successful response looks like: {"status": "success", "is_running": True}
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
        # Default to false if the server status cannot be determined.
        return False

    def before_server_stop(self, server_name: str):
        """
        Example Scenario: A user runs `bsm stop my_server`. This function is
        triggered first. It sends the command "say Server is stopping in 10
        seconds..." to the game, then waits for 10 seconds before the stop
        process continues.
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

                # Example: Pause execution to give players time to react.
                self.logger.info(
                    f"Waiting {self.stop_delay_seconds} seconds before server '{server_name}' stops."
                )
                time.sleep(self.stop_delay_seconds)

            except AttributeError as e:
                self.logger.error(
                    f"API function error during before_server_stop for '{server_name}': {e}. Is 'send_command' registered?"
                )
            except Exception as e:
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
        Example Scenario: A user runs `bsm restart my_server`. After the server
        successfully stops, this function is called. It waits for 3 seconds
        to ensure the server process has fully terminated before the restart
        process attempts to start it again.
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
        Example Scenario: A user runs `bsm delete my_server --data`. Before the
        server's files are permanently removed, this function sends a final
        warning "say WARNING: Server is being deleted permanently!" to any
        players who might still be connected.
        """
        self.logger.debug(
            f"'{self.name}' handling before_delete_server_data for '{server_name}'"
        )
        if self._is_server_running(server_name):
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
        Example Scenario: A user runs `bsm update my_server`. Before the update
        process begins, this function sends the message "say Server is
        updating now..." to the game.
        """
        self.logger.debug(
            f"'{self.name}' handling before_server_update for '{server_name}' to version '{target_version}'"
        )
        if self._is_server_running(server_name):
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

    def after_server_start(self, server_name: str, result: dict):
        """
        Example: After `bsm start my_server` reports success, this function
        waits for 3 seconds. This short delay can help ensure the server is
        fully initialized and ready to accept commands before any subsequent
        actions are performed.
        """
        if result.get("status") == "success":
            try:
                time.sleep(3)
            except Exception as e:
                self.logger.warning(
                    f"Could not wait 3 seconds after '{server_name}' start: {e}"
                )
