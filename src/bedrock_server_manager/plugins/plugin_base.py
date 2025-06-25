# bedrock_server_manager/plugins/plugin_base.py
"""Defines the abstract base class (ABC) for all plugins.

This module provides the `PluginBase` class, which serves as the foundational
template for all plugins within the Bedrock Server Manager ecosystem. Plugins
must inherit from this class to be recognized and loaded by the `PluginManager`.
By overriding the various event hook methods defined in this base class, plugins
can subscribe to and react to specific events triggered by the core application
or other parts of the server manager.
"""
from abc import ABC
from logging import Logger  # Used for type hinting the logger instance.
from .api_bridge import PluginAPI  # Used for type hinting the API bridge instance.

# The get_installed_version import seems unused in this file.
# If it were used, its purpose would be to fetch the application's version.
# from bedrock_server_manager.config.const import get_installed_version


class PluginBase(ABC):
    """The abstract base class (ABC) from which all plugins must inherit.

    Plugins should subclass `PluginBase` and are required to define a class
    attribute named `version` (e.g., `version = "1.0.0"`). This version string
    is used by the `PluginManager` for metadata and potential compatibility checks.

    Instances of concrete plugin subclasses are provided with:
        - `name` (str): The plugin's name, derived from its filename.
        - `api` (PluginAPI): An instance of `PluginAPI` for safe interaction
          with the core application's functionalities.
        - `logger` (Logger): A pre-configured logger instance, specific to the
          plugin, which automatically includes the plugin's name in log messages.

    Plugins implement their functionality by overriding the various `on_*`,
    `before_*`, and `after_*` event hook methods defined in this class. These
    methods are called by the `PluginManager` when corresponding application
    events occur. If a plugin does not override a specific hook method, the
    default `pass` implementation in this base class is used, meaning the
    plugin will simply ignore that event.
    """

    # Class attribute: version
    # All plugins *must* override this class attribute with their specific version string.
    # Example: version = "1.2.3"
    # The PluginManager uses this for display and potentially for compatibility.
    # If not defined by a subclass, it will default to "N/A" during instantiation,
    # but the PluginManager's synchronization step enforces its presence for a plugin
    # to be considered valid and loadable.
    version: str = "N/A"  # Default placeholder, should be overridden.

    def __init__(self, plugin_name: str, api: PluginAPI, logger: Logger):
        """Initializes the plugin instance.

        This constructor is called by the `PluginManager` when the plugin is
        successfully discovered, validated, and loaded. It sets up the essential
        attributes for the plugin instance.

        Args:
            plugin_name (str): The name of the plugin, typically derived from
                its Python module filename (e.g., "my_plugin" for "my_plugin.py").
            api (PluginAPI): An instance of `PluginAPI` that provides a safe
                bridge for the plugin to call core application functions.
            logger (Logger): A pre-configured `logging.Logger` instance that is
                scoped to this plugin. Log messages sent via `self.logger` will
                automatically be prefixed with the plugin's context.
        """
        self.name: str = plugin_name
        self.api: PluginAPI = api
        self.logger: Logger = logger

        # Retrieve the version from the class attribute of the concrete plugin.
        # This ensures that `self.version` reflects the version defined by the
        # actual plugin class, not the "N/A" placeholder from PluginBase.
        # The PluginManager's validation step should ensure `cls.version` exists
        # and is valid before instantiation.
        class_version = getattr(self.__class__, "version", "N/A")
        if class_version == "N/A" and self.__class__ is not PluginBase:
            # This situation should ideally be caught by PluginManager's validation,
            # but log a warning if a concrete plugin instance somehow ends up with N/A.
            self.logger.warning(
                f"Plugin '{self.name}' class is missing a 'version' attribute or it's 'N/A'. "
                "This should be defined in the plugin class."
            )
        self.version: str = class_version

        # Log the successful initialization of the plugin instance.
        # This is an INFO level log as it's a significant lifecycle event for the plugin.
        self.logger.info(
            f"Plugin '{self.name}' v{self.version} initialized and active."
        )

    # --- Plugin Lifecycle Hooks ---

    def on_load(self):
        """Called by the PluginManager when the plugin is first loaded and initialized.

        This method is invoked after the plugin's `__init__` has completed.
        It's an ideal place for the plugin to perform any setup tasks, such as
        registering listeners for custom events, loading its own configuration,
        or initializing internal state.

        Plugins should override this method to implement their load-time logic.
        The base implementation does nothing.
        """
        # self.logger.debug(f"Plugin '{self.name}' v{self.version}: on_load() called.")
        pass

    def on_unload(self):
        """Called by the PluginManager just before the plugin is unloaded.

        This can occur during application shutdown or when plugins are being
        reloaded. Plugins should use this method to perform any necessary
        cleanup, such as releasing resources, saving state, or unregistering
        from external services.

        Note: Custom event listeners registered via `self.api.listen_for_event()`
        are automatically cleared by the `PluginManager` during a full reload,
        so explicit unregistration is often not needed for those.

        Plugins should override this method to implement their unload-time logic.
        The base implementation does nothing.
        """
        # self.logger.debug(f"Plugin '{self.name}' v{self.version}: on_unload() called.")
        pass

    # --- Server Lifecycle Event Hooks ---

    def before_server_start(self, server_name: str, mode: str):
        """Called by the PluginManager just before a server start operation is attempted.

        Args:
            server_name (str): The name of the server that is about to be started.
            mode (str): The mode in which the server is being started (e.g.,
                "attached", "detached").
        """
        pass

    def after_server_start(self, server_name: str, result: dict):
        """Called by the PluginManager just after a server start operation has been attempted.

        Args:
            server_name (str): The name of the server for which the start was attempted.
            result (dict): A dictionary containing the outcome of the start operation.
                Typically includes a "status" key ("success" or "error") and
                potentially a "message" or other relevant data.
        """
        pass

    def before_server_stop(self, server_name: str, mode: str):
        """Called by the PluginManager just before a server stop operation is attempted.

        Args:
            server_name (str): The name of the server that is about to be stopped.
            mode (str): The mode or reason for stopping (e.g., "graceful", "force").
        """
        pass

    def after_server_stop(self, server_name: str, result: dict):
        """Called by the PluginManager just after a server stop operation has been attempted.

        Args:
            server_name (str): The name of the server for which the stop was attempted.
            result (dict): A dictionary containing the outcome of the stop operation.
        """
        pass

    # --- Server Command Event Hooks ---

    def before_command_send(self, server_name: str, command: str):
        """Called by the PluginManager before a command is sent to a running server's console.

        Args:
            server_name (str): The name of the server to which the command will be sent.
            command (str): The raw command string that is about to be sent.
        """
        pass

    def after_command_send(self, server_name: str, command: str, result: dict):
        """Called by the PluginManager after a command has been sent to a server's console.

        Args:
            server_name (str): The name of the server to which the command was sent.
            command (str): The command string that was sent.
            result (dict): A dictionary containing the outcome of sending the command.
                This might not reflect command execution success within the server,
                but rather the success of the send operation itself.
        """
        pass

    # --- Backup and Restore Event Hooks ---

    def before_backup(self, server_name: str, backup_type: str, **kwargs: dict):
        """Called by the PluginManager before a backup operation for a server begins.

        Args:
            server_name (str): The name of the server being backed up.
            backup_type (str): The type of backup being performed (e.g., "manual",
                "scheduled", "full", "incremental").
            **kwargs (dict): Additional keyword arguments related to the backup,
                which might include options like `comment` or `destination`.
        """
        pass

    def after_backup(
        self, server_name: str, backup_type: str, result: dict, **kwargs: dict
    ):
        """Called by the PluginManager after a backup operation for a server completes.

        Args:
            server_name (str): The name of the server that was backed up.
            backup_type (str): The type of backup that was performed.
            result (dict): A dictionary containing the outcome of the backup operation.
            **kwargs (dict): Additional keyword arguments related to the backup.
        """
        pass

    def before_restore(self, server_name: str, restore_type: str, **kwargs: dict):
        """Called by the PluginManager before a restore operation for a server begins.

        Args:
            server_name (str): The name of the server being restored.
            restore_type (str): The type of restore (e.g., "from_backup_id",
                "from_file").
            **kwargs (dict): Additional keyword arguments, such as `backup_id` or
                `file_path`.
        """
        pass

    def after_restore(
        self, server_name: str, restore_type: str, result: dict, **kwargs: dict
    ):
        """Called by the PluginManager after a restore operation for a server completes.

        Args:
            server_name (str): The name of the server that was restored.
            restore_type (str): The type of restore that was performed.
            result (dict): A dictionary containing the outcome of the restore operation.
            **kwargs (dict): Additional keyword arguments related to the restore.
        """
        pass

    def before_prune_backups(self, server_name: str):
        """Called by the PluginManager before old backups are pruned for a specific server.

        Args:
            server_name (str): The name of the server whose backups are about to be pruned.
        """
        pass

    def after_prune_backups(self, server_name: str, result: dict):
        """Called by the PluginManager after an attempt to prune old backups for a server completes.

        Args:
            server_name (str): The name of the server whose backups were pruned.
            result (dict): A dictionary containing the outcome, possibly including
                a list of pruned backups or a count.
        """
        pass

    # --- Server Configuration Event Hooks (Allowlist, Permissions, Properties) ---

    def before_allowlist_change(
        self, server_name: str, players_to_add: list[str], players_to_remove: list[str]
    ):
        """Called before a server's allowlist (allowlist.json) is modified.

        Args:
            server_name (str): The name of the server whose allowlist is changing.
            players_to_add (list[str]): A list of player identifiers (e.g., XUIDs or
                gamertags) to be added to the allowlist.
            players_to_remove (list[str]): A list of player identifiers to be
                removed from the allowlist.
        """
        pass

    def after_allowlist_change(self, server_name: str, result: dict):
        """Called after an attempt to modify a server's allowlist completes.

        Args:
            server_name (str): The name of the server whose allowlist was modified.
            result (dict): A dictionary containing the outcome of the allowlist change.
        """
        pass

    def before_permission_change(self, server_name: str, xuid: str, permission: str):
        """Called before a player's permission level (permissions.json) is changed for a server.

        Args:
            server_name (str): The name of the server where permissions are changing.
            xuid (str): The Xbox User ID (XUID) of the player whose permission is changing.
            permission (str): The new permission level to be assigned (e.g., "member",
                "operator").
        """
        pass

    def after_permission_change(self, server_name: str, xuid: str, result: dict):
        """Called after an attempt to change a player's permission level completes.

        Args:
            server_name (str): The name of the server where permissions were changed.
            xuid (str): The XUID of the player whose permission was targeted.
            result (dict): A dictionary containing the outcome of the permission change.
        """
        pass

    def before_properties_change(self, server_name: str, properties: dict):
        """Called before a server's `server.properties` file is modified.

        Args:
            server_name (str): The name of the server whose properties are changing.
            properties (dict): A dictionary representing the new or modified
                properties that will be written to the file.
        """
        pass

    def after_properties_change(self, server_name: str, result: dict):
        """Called after an attempt to modify `server.properties` completes.

        Args:
            server_name (str): The name of the server whose properties were modified.
            result (dict): A dictionary containing the outcome of the properties change.
        """
        pass

    # --- Server Installation and Update Event Hooks ---

    def before_server_install(self, server_name: str, target_version: str):
        """Called before a new Bedrock server instance installation begins.

        Args:
            server_name (str): The name for the new server instance being installed.
            target_version (str): The version of the Bedrock server software
                to be installed (e.g., "latest", "1.20.50.03").
        """
        pass

    def after_server_install(self, server_name: str, result: dict):
        """Called after a new Bedrock server installation attempt completes.

        Args:
            server_name (str): The name of the server instance that was installed.
            result (dict): A dictionary containing the outcome of the installation.
        """
        pass

    def before_server_update(self, server_name: str, target_version: str):
        """Called before an existing Bedrock server instance is updated to a new version.

        Args:
            server_name (str): The name of the server instance being updated.
            target_version (str): The target version for the update.
        """
        pass

    def after_server_update(self, server_name: str, result: dict):
        """Called after a Bedrock server update attempt completes.

        Args:
            server_name (str): The name of the server instance that was updated.
            result (dict): A dictionary containing the outcome of the update.
        """
        pass

    # --- Player Database Event Hooks ---

    def before_players_add(self, players_data: list[dict]):
        """Called before players are manually added to the central player database.

        Args:
            players_data (list[dict]): A list of dictionaries, where each
                dictionary contains data for a player to be added (e.g.,
                `{'xuid': '...', 'gamertag': '...'}`).
        """
        pass

    def after_players_add(self, result: dict):
        """Called after an attempt to manually add players to the central player database completes.

        Args:
            result (dict): A dictionary containing the outcome, possibly including
                counts of added or failed players.
        """
        pass

    def before_player_db_scan(self):
        """Called before a scan of all server logs (or other sources) for new players begins.
        This scan is typically used to automatically populate the central player database.
        """
        pass

    def after_player_db_scan(self, result: dict):
        """Called after a scan for new players has completed.

        Args:
            result (dict): A dictionary containing the outcome, such as the number
                of new players discovered and added.
        """
        pass

    # --- World Management Event Hooks ---

    def before_world_export(self, server_name: str, export_dir: str):
        """Called before a server's world is exported to a `.mcworld` file.

        Args:
            server_name (str): The name of the server whose world is being exported.
            export_dir (str): The target directory where the `.mcworld` file will be saved.
        """
        pass

    def after_world_export(self, server_name: str, result: dict):
        """Called after an attempt to export a server's world completes.

        Args:
            server_name (str): The name of the server whose world was exported.
            result (dict): A dictionary containing the outcome, including the path
                to the exported `.mcworld` file if successful.
        """
        pass

    def before_world_import(self, server_name: str, file_path: str):
        """Called before a `.mcworld` file is imported to replace a server's active world.

        Args:
            server_name (str): The name of the server to which the world will be imported.
            file_path (str): The path to the `.mcworld` file to be imported.
        """
        pass

    def after_world_import(self, server_name: str, result: dict):
        """Called after an attempt to import a world to a server completes.

        Args:
            server_name (str): The name of the server to which the world was imported.
            result (dict): A dictionary containing the outcome of the import operation.
        """
        pass

    def before_world_reset(self, server_name: str):
        """Called before a server's active world directory and its contents are deleted.
        This is a destructive operation.

        Args:
            server_name (str): The name of the server whose world is about to be reset.
        """
        pass

    def after_world_reset(self, server_name: str, result: dict):
        """Called after an attempt to reset a server's world completes.

        Args:
            server_name (str): The name of the server whose world was reset.
            result (dict): A dictionary containing the outcome of the reset operation.
        """
        pass

    # --- Addon Management Event Hooks ---

    def before_addon_import(self, server_name: str, addon_file_path: str):
        """Called before an addon file (e.g., .mcpack, .mcaddon) is imported to a server.

        Args:
            server_name (str): The name of the server to which the addon will be imported.
            addon_file_path (str): The path to the addon file.
        """
        pass

    def after_addon_import(self, server_name: str, result: dict):
        """Called after an attempt to import an addon to a server completes.

        Args:
            server_name (str): The name of the server to which the addon was imported.
            result (dict): A dictionary containing the outcome of the addon import.
        """
        pass

    # --- System Service and Application Setting Event Hooks ---

    def before_service_change(self, server_name: str, action: str):
        """Called before a system service related to a server (e.g., systemd unit)
        is changed (e.g., created, enabled, disabled, deleted).

        Args:
            server_name (str): The name of the server for which the service is changing.
            action (str): The action being performed on the service (e.g., "create",
                "enable", "disable", "delete", "reload").
        """
        pass

    def after_service_change(self, server_name: str, action: str, result: dict):
        """Called after an attempt to change a system service related to a server completes.

        Args:
            server_name (str): The name of the server for which the service was changed.
            action (str): The action that was performed on the service.
            result (dict): A dictionary containing the outcome of the service change.
        """
        pass

    def before_autoupdate_change(self, server_name: str, new_value: bool):
        """Called before a server's automatic update setting is changed.

        Args:
            server_name (str): The name of the server whose autoupdate setting is changing.
            new_value (bool): The new boolean value for the autoupdate setting
                (True if enabling, False if disabling).
        """
        pass

    def after_autoupdate_change(self, server_name: str, result: dict):
        """Called after an attempt to change a server's autoupdate setting completes.

        Args:
            server_name (str): The name of the server whose autoupdate setting was changed.
            result (dict): A dictionary containing the outcome of the change.
        """
        pass

    def before_prune_download_cache(self, download_dir: str, keep_count: int):
        """Called before the global download cache for server software is pruned.

        Args:
            download_dir (str): The path to the download cache directory.
            keep_count (int): The number of most recent versions of server software
                to keep in the cache for each variant/type.
        """
        pass

    def after_prune_download_cache(self, result: dict):
        """Called after an attempt to prune the global download cache completes.

        Args:
            result (dict): A dictionary containing the outcome, possibly including
                a list of pruned files or a count.
        """
        pass
