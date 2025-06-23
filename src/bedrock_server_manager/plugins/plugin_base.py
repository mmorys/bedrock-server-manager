# bedrock_server_manager/plugins/plugin_base.py
"""Defines the abstract base class for all plugins.

This module provides the `PluginBase` class, which serves as a template for
all plugins. Plugins must inherit from this class and can override its methods
to subscribe to and handle various events triggered by the application.
"""
from abc import ABC
from logging import Logger
from .api_bridge import PluginAPI

from bedrock_server_manager.config.const import get_installed_version


class PluginBase(ABC):
    """The abstract base class for all plugins.

    Plugins should inherit from this class, define a `version` class attribute,
    and implement the event hook methods they wish to subscribe to. An
    instance of this class provides access to the core application API and a
    dedicated logger.
    """

    version: str = get_installed_version

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

        self.version = getattr(self.__class__, "version", "N/A")

        self.logger.info(f"Plugin '{self.name}' v{self.version} initialized.")

    def on_load(self):
        """Called by the Plugin Manager when the plugin is first loaded."""
        pass

    def on_unload(self):
        """Called by the Plugin Manager when the application is shutting down or reloading."""
        pass

    def before_server_start(self, server_name: str, mode: str):
        """Called just before a server start is attempted."""
        pass

    def after_server_start(self, server_name: str, result: dict):
        """Called just after a server start has been attempted."""
        pass

    def before_server_stop(self, server_name: str, mode: str):
        """Called just before a server stop is attempted."""
        pass

    def after_server_stop(self, server_name: str, result: dict):
        """Called just after a server stop has been attempted."""
        pass

    def before_command_send(self, server_name: str, command: str):
        """Called before a command is sent to a server."""
        pass

    def after_command_send(self, server_name: str, command: str, result: dict):
        """Called after a command has been sent to a server."""
        pass

    def before_backup(self, server_name: str, backup_type: str, **kwargs):
        """Called before a backup operation begins."""
        pass

    def after_backup(self, server_name: str, backup_type: str, result: dict, **kwargs):
        """Called after a backup operation completes."""
        pass

    def before_restore(self, server_name: str, restore_type: str, **kwargs):
        """Called before a restore operation begins."""
        pass

    def after_restore(
        self, server_name: str, restore_type: str, result: dict, **kwargs
    ):
        """Called after a restore operation completes."""
        pass

    def before_prune_backups(self, server_name: str):
        """Called before old backups are pruned for a server."""
        pass

    def after_prune_backups(self, server_name: str, result: dict):
        """Called after an attempt to prune old backups completes."""
        pass

    def before_allowlist_change(
        self, server_name: str, players_to_add: list, players_to_remove: list
    ):
        """Called before a server's allowlist.json is modified."""
        pass

    def after_allowlist_change(self, server_name: str, result: dict):
        """Called after an attempt to modify the allowlist completes."""
        pass

    def before_permission_change(self, server_name: str, xuid: str, permission: str):
        """Called before a player's permission level is changed."""
        pass

    def after_permission_change(self, server_name: str, xuid: str, result: dict):
        """Called after an attempt to change a player's permission completes."""
        pass

    def before_properties_change(self, server_name: str, properties: dict):
        """Called before server.properties is modified."""
        pass

    def after_properties_change(self, server_name: str, result: dict):
        """Called after an attempt to modify server.properties completes."""
        pass

    def before_server_install(self, server_name: str, target_version: str):
        """Called before a new server installation begins."""
        pass

    def after_server_install(self, server_name: str, result: dict):
        """Called after a new server installation attempt completes."""
        pass

    def before_server_update(self, server_name: str, target_version: str):
        """Called before an existing server is updated."""
        pass

    def after_server_update(self, server_name: str, result: dict):
        """Called after a server update attempt completes."""
        pass

    def before_players_add(self, players_data: list):
        """Called before players are manually added to the central player DB."""
        pass

    def after_players_add(self, result: dict):
        """Called after an attempt to manually add players completes."""
        pass

    def before_player_db_scan(self):
        """Called before a scan of all server logs for new players begins."""
        pass

    def after_player_db_scan(self, result: dict):
        """Called after a scan of server logs for players has completed."""
        pass

    def before_world_export(self, server_name: str, export_dir: str):
        """Called before a server's world is exported to a .mcworld file."""
        pass

    def after_world_export(self, server_name: str, result: dict):
        """Called after an attempt to export a world completes."""
        pass

    def before_world_import(self, server_name: str, file_path: str):
        """Called before a .mcworld file is imported to a server."""
        pass

    def after_world_import(self, server_name: str, result: dict):
        """Called after an attempt to import a world completes."""
        pass

    def before_world_reset(self, server_name: str):
        """Called before a server's active world directory is deleted."""
        pass

    def after_world_reset(self, server_name: str, result: dict):
        """Called after an attempt to reset a world completes."""
        pass

    def before_addon_import(self, server_name: str, addon_file_path: str):
        """Called before an addon file is imported to a server."""
        pass

    def after_addon_import(self, server_name: str, result: dict):
        """Called after an attempt to import an addon completes."""
        pass

    def before_service_change(self, server_name: str, action: str):
        """Called before a system service (e.g., systemd) is changed."""
        pass

    def after_service_change(self, server_name: str, action: str, result: dict):
        """Called after an attempt to change a system service completes."""
        pass

    def before_autoupdate_change(self, server_name: str, new_value: bool):
        """Called before a server's autoupdate setting is changed."""
        pass

    def after_autoupdate_change(self, server_name: str, result: dict):
        """Called after an attempt to change the autoupdate setting completes."""
        pass

    def before_prune_download_cache(self, download_dir: str, keep_count: int):
        """Called before the global download cache is pruned."""
        pass

    def after_prune_download_cache(self, result: dict):
        """Called after an attempt to prune the download cache completes."""
        pass
