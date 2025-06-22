# bedrock_server_manager/plugins/default/auto_backup_on_start.py
"""An example plugin to automatically back up a server before it starts.

This plugin demonstrates how to use the `before_server_start` event hook to
trigger a full backup of a server each time a start command is initiated.
"""
from bedrock_server_manager import PluginBase


# Every plugin file must contain one class that inherits from PluginBase.
class AutoBackupOnStart(PluginBase):
    """Hooks into the server start process to perform a backup."""

    def on_load(self):
        """Called by the Plugin Manager when the plugin is first loaded.

        This method is a good place for one-time setup or logging a confirmation
        that the plugin is active.
        """
        self.logger.info(
            "Plugin 'AutoBackupOnStart' is loaded. Servers will be backed up before starting."
        )

    def before_server_start(self, server_name: str, mode: str):
        """Called by the Plugin Manager right before a server is started.

        This method uses the plugin API to call the `backup_all` function.
        It serves as the main logic for this plugin.

        Args:
            server_name: The name of the server being started.
            mode: The mode the server is being started in ('direct' or 'detached').
        """
        self.logger.info(
            f"Triggered pre-start action for server '{server_name}'. Performing automatic backup..."
        )

        try:
            # Use the provided API bridge to call the core `backup_all` function.
            # `stop_start_server` is set to False because the server is guaranteed
            # to be stopped at this point in the startup sequence, so managing
            # its lifecycle is unnecessary.
            result = self.api.backup_all(
                server_name=server_name, stop_start_server=False
            )

            # Check the 'status' key in the dictionary returned by the API call
            # to determine if the backup operation was successful.
            if result.get("status") == "success":
                self.logger.info(
                    f"Pre-start backup for '{server_name}' completed successfully."
                )
            else:
                # The API call was made, but the backup operation itself
                # reported an error (e.g., file permissions). Log this as a warning.
                error_message = result.get("message", "Unknown backup error")
                self.logger.warning(
                    f"Pre-start backup for '{server_name}' finished with an error: {error_message}"
                )

        except Exception as e:
            # A more serious error occurred where the API call itself failed.
            # This broad exception catch ensures the plugin does not crash the
            # main application and logs the error for debugging.
            self.logger.error(
                f"An unexpected error occurred during pre-start backup for '{server_name}': {e}",
                exc_info=True,
            )
