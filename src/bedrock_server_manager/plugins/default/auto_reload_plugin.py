# bedrock_server_manager/plugins/default/auto_reload_plugin.py
"""
Example Plugin: Automatically sends a `reload` command to a running server
after its configuration files (like `allowlist.json` or `permissions.json`)
are modified.
"""
from bedrock_server_manager import PluginBase


class AutoReloadPlugin(PluginBase):
    """
    For example, if you add a player to the allowlist of a running server
    named 'creative_world', this plugin will automatically execute the
    `allowlist reload` command on the server so the change takes effect
    immediately without manual intervention.
    """

    def on_load(self):
        """
        Example: When the Plugin Manager loads this plugin, it will log a
        message like: 'AutoReloadPlugin is loaded and active. It will handle
        automatic reloads after configuration changes.'
        """
        self.logger.info(
            "AutoReloadPlugin is loaded and active. It will handle automatic reloads after configuration changes."
        )

    def _is_server_running(self, server_name: str) -> bool:
        """
        Example: Before sending a reload command, this function checks if
        'creative_world' is actually online. It calls an internal API
        function that might return `{'status': 'success', 'is_running': true}`.
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
        Example helper function: If `_is_server_running` confirms the server
        is online, this function sends the specified command. For instance,
        it would send `allowlist reload` to the 'creative_world' server.
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
        Example Scenario: A user runs a command to add 'Player123' to the
        allowlist of 'survival_server'. After the `allowlist.json` file is
        successfully updated, this function is triggered. It inspects the result
        to see if players were actually added or removed and then calls
        `_send_reload_command`.
        """
        self.logger.debug(
            f"'{self.name}' handling after_allowlist_change for '{server_name}'. Result: {result}"
        )

        if result.get("status") == "success":
            # For example, when adding players, the result might be {'added_count': 1}
            added_count = result.get("added_count", 0)
            # When removing players, the result could be {'details': {'removed': ['Player456']}}
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
        Example Scenario: An admin changes the permission level of a player
        (identified by XUID) on 'survival_server' from 'member' to 'operator'.
        Once the `permissions.json` file is updated successfully, this function
        is triggered and calls `_send_reload_command` to send `permission reload`.
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
