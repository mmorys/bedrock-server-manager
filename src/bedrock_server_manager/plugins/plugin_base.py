# bedrock_server_manager/plugins/plugin_base.py
"""Defines the abstract base class for all plugins.

This module provides the `PluginBase` class, which serves as a template for
all plugins. Plugins must inherit from this class and can override its methods
to subscribe to and handle various events triggered by the application.
"""
from abc import ABC
from logging import Logger
from .api_bridge import PluginAPI


class PluginBase(ABC):
    """The abstract base class for all plugins.

    Plugins should inherit from this class and implement the event hook methods
    (e.g., `on_load`, `before_server_start`) they wish to subscribe to. An
    instance of this class provides access to the core application API and a
    dedicated logger.
    """

    def __init__(self, plugin_name: str, api: PluginAPI, logger: Logger):
        """Initializes the plugin instance.

        This constructor is called by the Plugin Manager when the plugin is loaded.

        Args:
            plugin_name: The name of the plugin, derived from its filename.
            api: An instance of `PluginAPI` for interacting with the core
                application's functions.
            logger: A pre-configured logger instance for the plugin to use,
                which automatically includes the plugin's name in log messages.
        """
        self.name = plugin_name
        self.api = api
        self.logger = logger
        self.logger.info(f"Plugin '{self.name}' initialized.")

    def on_load(self):
        """Called by the Plugin Manager when the plugin is first loaded."""
        pass

    def on_unload(self):
        """Called by the Plugin Manager when the application is shutting down."""
        pass

    def before_server_start(self, server_name: str, mode: str):
        """Called just before a server start is attempted.

        Args:
            server_name: The name of the server being started.
            mode: The start mode ('direct' or 'detached').
        """
        pass

    def after_server_start(self, server_name: str, result: dict):
        """Called just after a server start has been attempted.

        Args:
            server_name: The name of the server.
            result: The dictionary returned by the `start_server` API call.
        """
        pass

    def before_server_stop(self, server_name: str):
        """Called just before a server stop is attempted.

        Args:
            server_name: The name of the server being stopped.
        """
        pass

    def after_server_stop(self, server_name: str, result: dict):
        """Called just after a server stop has been attempted.

        Args:
            server_name: The name of the server.
            result: The dictionary returned by the `stop_server` API call.
        """
        pass

    def before_command_send(self, server_name: str, command: str):
        """Called before a command is sent to a server.

        Args:
            server_name: The name of the server receiving the command.
            command: The command string to be sent.
        """
        pass

    def after_command_send(self, server_name: str, command: str, result: dict):
        """Called after a command has been sent to a server.

        Args:
            server_name: The name of the server.
            command: The command string that was sent.
            result: The dictionary returned by the `send_command` API call.
        """
        pass

    def before_backup(self, server_name: str, backup_type: str, **kwargs):
        """Called before a backup operation begins.

        Args:
            server_name: The name of the server being backed up.
            backup_type: The type of backup ('world', 'config_file', or 'all').
            **kwargs: Additional context, like `file_to_backup`.
        """
        pass

    def after_backup(self, server_name: str, backup_type: str, result: dict, **kwargs):
        """Called after a backup operation completes.

        Args:
            server_name: The name of the server.
            backup_type: The type of backup ('world', 'config_file', or 'all').
            result: The dictionary returned by the backup API call.
            **kwargs: Additional context.
        """
        pass

    def before_restore(self, server_name: str, restore_type: str, **kwargs):
        """Called before a restore operation begins.

        Args:
            server_name: The name of the server being restored.
            restore_type: The type of restore ('world', 'config_file', or 'all').
            **kwargs: Additional context, like `backup_file_path`.
        """
        pass

    def after_restore(
        self, server_name: str, restore_type: str, result: dict, **kwargs
    ):
        """Called after a restore operation completes.

        Args:
            server_name: The name of the server.
            restore_type: The type of restore ('world', 'config_file', or 'all').
            result: The dictionary returned by the restore API call.
            **kwargs: Additional context.
        """
        pass

    def before_prune_backups(self, server_name: str):
        """Called before old backups are pruned for a server.

        Args:
            server_name: The name of the server whose backups are being pruned.
        """
        pass

    def after_prune_backups(self, server_name: str, result: dict):
        """Called after an attempt to prune old backups completes.

        Args:
            server_name: The name of the server.
            result: The dictionary returned by the `prune_old_backups` API call.
        """
        pass

    def before_allowlist_change(
        self, server_name: str, players_to_add: list, players_to_remove: list
    ):
        """Called before a server's allowlist.json is modified.

        Args:
            server_name: The name of the server.
            players_to_add: A list of player data dictionaries to be added.
            players_to_remove: A list of player name strings to be removed.
        """
        pass

    def after_allowlist_change(self, server_name: str, result: dict):
        """Called after an attempt to modify the allowlist completes.

        Args:
            server_name: The name of the server.
            result: The dictionary returned by the allowlist modification API call.
        """
        pass

    def before_permission_change(self, server_name: str, xuid: str, permission: str):
        """Called before a player's permission level is changed.

        Args:
            server_name: The name of the server.
            xuid: The XUID of the player whose permission is changing.
            permission: The new permission level (e.g., 'operator').
        """
        pass

    def after_permission_change(self, server_name: str, xuid: str, result: dict):
        """Called after an attempt to change a player's permission completes.

        Args:
            server_name: The name of the server.
            xuid: The XUID of the player.
            result: The dictionary returned by the permission change API call.
        """
        pass

    def before_properties_change(self, server_name: str, properties: dict):
        """Called before server.properties is modified.

        Args:
            server_name: The name of the server.
            properties: A dictionary of properties to be changed.
        """
        pass

    def after_properties_change(self, server_name: str, result: dict):
        """Called after an attempt to modify server.properties completes.

        Args:
            server_name: The name of the server.
            result: The dictionary returned by the `modify_server_properties` API call.
        """
        pass

    def before_server_install(self, server_name: str, target_version: str):
        """Called before a new server installation begins.

        Args:
            server_name: The name of the new server.
            target_version: The version of the server to be installed.
        """
        pass

    def after_server_install(self, server_name: str, result: dict):
        """Called after a new server installation attempt completes.

        Args:
            server_name: The name of the new server.
            result: The dictionary returned by the `install_new_server` API call.
        """
        pass

    def before_server_update(self, server_name: str, target_version: str):
        """Called before an existing server is updated.

        Args:
            server_name: The name of the server being updated.
            target_version: The version the server is being updated to.
        """
        pass

    def after_server_update(self, server_name: str, result: dict):
        """Called after a server update attempt completes.

        Args:
            server_name: The name of the server.
            result: The dictionary returned by the `update_server` API call.
        """
        pass

    def before_players_add(self, players_data: list):
        """Called before players are manually added to the central player DB.

        Args:
            players_data: A list of player dictionaries, each with 'name' and 'xuid'.
        """
        pass

    def after_players_add(self, result: dict):
        """Called after an attempt to manually add players completes.

        Args:
            result: The dictionary returned by the `add_players_manually` API call.
        """
        pass

    def before_player_db_scan(self):
        """Called before a scan of all server logs for new players begins."""
        pass

    def after_player_db_scan(self, result: dict):
        """Called after a scan of server logs for players has completed.

        Args:
            result: The dictionary returned by the `scan_and_update_player_db` API call.
        """
        pass

    def before_world_export(self, server_name: str, export_dir: str):
        """Called before a server's world is exported to a .mcworld file.

        Args:
            server_name: The name of the server.
            export_dir: The target directory for the exported .mcworld file.
        """
        pass

    def after_world_export(self, server_name: str, result: dict):
        """Called after an attempt to export a world completes.

        Args:
            server_name: The name of the server.
            result: The dictionary returned by the `export_world` API call.
        """
        pass

    def before_world_import(self, server_name: str, file_path: str):
        """Called before a .mcworld file is imported to a server.

        Args:
            server_name: The name of the server.
            file_path: The path to the .mcworld file being imported.
        """
        pass

    def after_world_import(self, server_name: str, result: dict):
        """Called after an attempt to import a world completes.

        Args:
            server_name: The name of the server.
            result: The dictionary returned by the `import_world` API call.
        """
        pass

    def before_world_reset(self, server_name: str):
        """Called before a server's active world directory is deleted.

        Args:
            server_name: The name of the server whose world is being reset.
        """
        pass

    def after_world_reset(self, server_name: str, result: dict):
        """Called after an attempt to reset a world completes.

        Args:
            server_name: The name of the server.
            result: The dictionary returned by the `reset_world` API call.
        """
        pass

    def before_addon_import(self, server_name: str, addon_file_path: str):
        """Called before an addon file is imported to a server.

        Args:
            server_name: The name of the server.
            addon_file_path: The path to the addon file being imported.
        """
        pass

    def after_addon_import(self, server_name: str, result: dict):
        """Called after an attempt to import an addon completes.

        Args:
            server_name: The name of the server.
            result: The dictionary returned by the `import_addon` API call.
        """
        pass

    def before_service_change(self, server_name: str, action: str):
        """Called before a system service (e.g., systemd) is changed.

        Args:
            server_name: The name of the server.
            action: The action being performed ('create', 'enable', 'disable').
        """
        pass

    def after_service_change(self, server_name: str, action: str, result: dict):
        """Called after an attempt to change a system service completes.

        Args:
            server_name: The name of the server.
            action: The action that was performed.
            result: The dictionary returned by the service change API call.
        """
        pass

    def before_autoupdate_change(self, server_name: str, new_value: bool):
        """Called before a server's autoupdate setting is changed.

        Args:
            server_name: The name of the server.
            new_value: The new boolean value for the autoupdate setting.
        """
        pass

    def after_autoupdate_change(self, server_name: str, result: dict):
        """Called after an attempt to change the autoupdate setting completes.

        Args:
            server_name: The name of the server.
            result: The dictionary returned by the `set_autoupdate` API call.
        """
        pass

    def before_prune_download_cache(self, download_dir: str, keep_count: int):
        """Called before the global download cache is pruned.

        Args:
            download_dir: The directory being pruned.
            keep_count: The number of files to keep.
        """
        pass

    def after_prune_download_cache(self, result: dict):
        """Called after an attempt to prune the download cache completes.

        Args:
            result: The dictionary returned by the `prune_download_cache` API call.
        """
        pass
