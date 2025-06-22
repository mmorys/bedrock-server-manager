# bedrock_server_manager/plugins/default/autoupdate_plugin.py
"""
Plugin for handling automatic server updates before server start.
"""
import logging
from bedrock_server_manager.plugins.plugin_base import PluginBase
from bedrock_server_manager.plugins.api_bridge import PluginAPI
from bedrock_server_manager.core.bedrock_server import (
    BedrockServer,
)  # For get_custom_config_value
from bedrock_server_manager.error import BSMError  # For catching errors


class AutoupdatePlugin(PluginBase):
    """
    Checks for and performs autoupdates before the server starts, if enabled.
    """

    def on_load(self):
        """Called by the Plugin Manager when the plugin is first loaded."""
        self.logger.info(
            "AutoupdatePlugin is loaded and active. It will handle autoupdates before server start."
        )

    def before_server_start(self, server_name: str, mode: str):
        """
        Called just before a server start is attempted.
        Checks for 'autoupdate' flag and runs update if true.
        """
        self.logger.debug(
            f"'{self.name}' handling before_server_start for '{server_name}' (mode: {mode})"
        )

        try:
            server_instance = BedrockServer(server_name)
            autoupdate_enabled = server_instance.get_custom_config_value("autoupdate")

            if not autoupdate_enabled:
                self.logger.info(
                    f"Autoupdate is disabled for server '{server_name}'. Skipping check."
                )
                return

            self.logger.info(
                f"Autoupdate enabled for server '{server_name}'. Checking for updates..."
            )

            update_result = self.api.update_server(
                server_name=server_name, send_message=False
            )

            if update_result.get("status") == "success":
                if update_result.get("updated", False):
                    self.logger.info(
                        f"Autoupdate successful for server '{server_name}'. New version: {update_result.get('new_version')}"
                    )
                else:
                    self.logger.info(
                        f"Autoupdate check for server '{server_name}': Server is already up-to-date."
                    )
            else:
                # Log the error but don't block the server from starting, mirroring original _handle_autoupdate behavior.
                self.logger.error(
                    f"Autoupdate process failed for server '{server_name}': {update_result.get('message')}. Server start will continue."
                )

        except AttributeError as e:
            self.logger.error(
                f"API function error during autoupdate for '{server_name}': {e}. Is 'update_server' registered?",
                exc_info=True,
            )
            # Allow server start to proceed
        except (
            BSMError
        ) as e:  # Catch errors from BedrockServer instantiation or get_custom_config_value
            self.logger.error(
                f"Error accessing server config for autoupdate flag on '{server_name}': {e}. Server start will continue.",
                exc_info=True,
            )
            # Allow server start to proceed
        except Exception as e:
            self.logger.error(
                f"Unexpected error during autoupdate for server '{server_name}': {e}. Server start will continue.",
                exc_info=True,
            )
            # Allow server start to proceed
