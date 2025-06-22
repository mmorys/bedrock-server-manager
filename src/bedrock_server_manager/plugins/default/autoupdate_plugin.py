# bedrock_server_manager/plugins/default/autoupdate_plugin.py
"""
Example Plugin: Automatically updates a Bedrock server to the latest version before it starts.
"""
from bedrock_server_manager import PluginBase
from bedrock_server_manager import BedrockServer
from bedrock_server_manager.error import BSMError


class AutoupdatePlugin(PluginBase):
    """
    For example, if you have a server named 'my_server' with 'autoupdate'
    enabled in its configuration, this plugin will check for a new version of
    the Bedrock Dedicated Server and apply the update automatically right
    before the server launches.
    """

    def on_load(self):
        """
        Example: When the Plugin Manager loads this plugin, it will log a
        message like: 'AutoupdatePlugin is loaded and active. It will handle
        autoupdates before server start.'
        """
        self.logger.info(
            "AutoupdatePlugin is loaded and active. It will handle autoupdates before server start."
        )

    def before_server_start(self, server_name: str, mode: str):
        """
        Example Scenario:
        A user runs `bsm start my_server`. This function is then triggered.
        It will look inside the server's configuration for a setting like
        `autoupdate: true`.

        - If `true`, it runs the update process.
        - If `false` or not set, it logs that autoupdate is disabled and
          lets the server start normally.
        """
        self.logger.debug(
            f"'{self.name}' handling before_server_start for '{server_name}' (mode: {mode})"
        )

        try:
            # For example, create an object for the server named 'my_server'
            server_instance = BedrockServer(server_name)
            # Check for a custom config value, e.g., 'autoupdate: true'
            autoupdate_enabled = server_instance.get_custom_config_value("autoupdate")

            if not autoupdate_enabled:
                self.logger.info(
                    f"Autoupdate is disabled for server '{server_name}'. Skipping check."
                )
                return

            self.logger.info(
                f"Autoupdate enabled for server '{server_name}'. Checking for updates..."
            )

            # This calls the main API to perform the update
            update_result = self.api.update_server(
                server_name=server_name, send_message=False
            )

            if update_result.get("status") == "success":
                if update_result.get("updated", False):
                    # Example log: "Autoupdate successful for server 'my_server'. New version: 1.20.10.01"
                    self.logger.info(
                        f"Autoupdate successful for server '{server_name}'. New version: {update_result.get('new_version')}"
                    )
                else:
                    self.logger.info(
                        f"Autoupdate check for server '{server_name}': Server is already up-to-date."
                    )
            else:
                # For example, if the update download fails, we log the error
                # but still allow the server to attempt to start with its current version.
                self.logger.error(
                    f"Autoupdate process failed for server '{server_name}': {update_result.get('message')}. Server start will continue."
                )

        except AttributeError as e:
            # This might happen if the `update_server` function isn't available in the API.
            self.logger.error(
                f"API function error during autoupdate for '{server_name}': {e}. Is 'update_server' registered?",
                exc_info=True,
            )
            # Always allow the server start to proceed.
        except BSMError as e:
            # For instance, if 'my_server_config.json' is missing or has incorrect permissions.
            self.logger.error(
                f"Error accessing server config for autoupdate flag on '{server_name}': {e}. Server start will continue.",
                exc_info=True,
            )
            # Always allow the server start to proceed.
        except Exception as e:
            # Catch any other unexpected errors to prevent them from stopping the server.
            self.logger.error(
                f"Unexpected error during autoupdate for server '{server_name}': {e}. Server start will continue.",
                exc_info=True,
            )
            # Always allow the server start to proceed.
