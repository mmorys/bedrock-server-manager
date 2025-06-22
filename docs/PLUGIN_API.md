# Bedrock Server Manager: Plugin Documentation

This guide will walk you through creating your own plugins to extend and customize the Bedrock Server Manager. The plugin system is designed to be simple yet powerful, allowing you to hook into various application events and use the core application's functions safely.

## Table of Contents
1.  [Getting Started: Your First Plugin](#1-getting-started-your-first-plugin)
2.  [Managing Plugins](#2-managing-plugins)
    *   [`plugins.json` Configuration File](#pluginsjson-configuration-file)
    *   [CLI Commands for Plugin Management](#cli-commands-for-plugin-management)
3.  [The `PluginBase` Class](#3-the-pluginbase-class)
4.  [Understanding Event Hooks](#4-understanding-event-hooks)
5.  [Complete List of Event Hooks](#5-complete-list-of-event-hooks)
    *   [Plugin Lifecycle Events](#plugin-lifecycle-events)
    *   [Server Start/Stop Events](#server-startstop-events)
    *   [Server Command Events](#server-command-events)
    *   [Backup & Restore Events](#backup--restore-events)
    *   [World Management Events](#world-management-events)
    *   [Addon Management Events](#addon-management-events)
    *   [Server Configuration Events](#server-configuration-events)
    *   [Server Installation & Update Events](#server-installation--update-events)
    *   [Player Database Events](#player-database-events)
    *   [System & Application Events](#system--application-events)
6.  [Using the Plugin API (`self.api`)](#6-using-the-plugin-api-selfapi)
7.  [Available API Functions](#7-available-api-functions)
    *   [Server Management](#server-management)
    *   [Server Installation & Configuration](#server-installation--configuration)
    *   [Plugin Configuration API](#plugin-configuration-api)
    *   [World Management](#world-management)
    *   [Addon Management](#addon-management)
    *   [Backup & Restore](#backup--restore)
    *   [Player Database](#player-database)
    *   [System & Application](#system--application)
    *   [Web Server](#web-server)
8.  [Example Plugin: Auto-Backup Announcer](#8-example-plugin-auto-backup-announcer)
9.  [Best Practices](#9-best-practices)

---

## 1. Getting Started: Your First Plugin

Creating a plugin is straightforward:

1.  **Locate the `plugins` directory:** Find the application's data directory. Inside, there will be a `plugins` folder. If it doesn't exist, the application will create it on first run.
2.  **Create a Python file:** Inside the `plugins` directory, create a new file (e.g., `my_first_plugin.py`). The filename (without the `.py`) will be used as your plugin's name.
3.  **Write the code:** In your new file, create a class that inherits from `PluginBase` and implement the event hooks you're interested in.

Here is the most basic "Hello World" plugin:

```python
# my_first_plugin.py
from bedrock_server_manager.plugins.plugin_base import PluginBase

class MyFirstPlugin(PluginBase):
    def on_load(self):
        """This event is called when the plugin is loaded by the manager."""
        self.logger.info("Hello from MyFirstPlugin!")

    def after_server_start(self, server_name: str, result: dict):
        """This event is called after a server has started."""
        if result.get("status") == "success":
            self.logger.info(f"Server '{server_name}' has started successfully!")
```

4.  **Run the application:** Start the Bedrock Server Manager. You should see your "Hello from MyFirstPlugin!" message in the logs.
5.  **Enable your plugin:** If it's not a default-enabled plugin, use the `bsm plugin enable my_first_plugin` command to activate it. (See [Managing Plugins](#2-managing-plugins) for more details).


## 2. Managing Plugins

The Bedrock Server Manager allows users to control which plugins are active through a `plugins.json` configuration file and new CLI commands.

### `plugins.json` Configuration File

-   **Location:** This file is located in your application's configuration directory (typically `~/.bedrock-server-manager/.config/plugins.json`).
-   **Functionality:** It stores a simple JSON object where keys are plugin names (derived from their filenames, e.g., `"MyAwesomePlugin"`) and values are booleans (`true` to enable, `false` to disable).
-   **Discovery:** When the application starts, the `PluginManager` scans the plugin directories (`<app_data_dir>/plugins/` and the application's internal `default_plugins/` directory).
    -   Any new `.py` files found that are not already in `plugins.json` will be added to it.
-   **Default State for New Plugins:**
    -   **Standard Plugins:** By default, newly discovered user-added plugins are added to `plugins.json` as `disabled` (`false`).
    -   **Default Enabled Plugins:** A predefined list of essential built-in plugins (e.g., `ServerLifecycleNotificationsPlugin`, `AutoReloadPlugin`) are automatically enabled (`true`) by default when first discovered. This ensures core extended functionalities are active out-of-the-box. You can still disable them manually if needed.
    The current list of default-enabled plugins includes:
        - `ServerLifecycleNotificationsPlugin`
        - `WorldOperationNotificationsPlugin`
        - `AutoReloadPlugin`
        - `AutoupdatePlugin`

### CLI Commands for Plugin Management

You can easily manage which plugins are active using the `bsm plugin` command-line interface:

-   **`bsm plugin list`**
    -   Displays all discovered plugins and their current status (Enabled/Disabled).
    -   Example:
        ```
        $ bsm plugin list
        Fetching plugin statuses...
        Plugin Statuses:
        Plugin Name                         | Status
        ------------------------------------|----------
        ServerLifecycleNotificationsPlugin  | Enabled
        MyCustomPlugin                      | Disabled
        ```

-   **`bsm plugin enable <plugin_name>`**
    -   Enables the specified plugin (sets its value to `true` in `plugins.json`).
    -   Example: `bsm plugin enable MyCustomPlugin`

-   **`bsm plugin disable <plugin_name>`**
    -   Disables the specified plugin (sets its value to `false` in `plugins.json`).
    -   Example: `bsm plugin disable ServerLifecycleNotificationsPlugin`

Changes made via these CLI commands are immediately saved to `plugins.json`. The application will load or ignore plugins based on this configuration the next time it fully initializes its plugin system (typically on startup).

## 3. The `PluginBase` Class

Every plugin **must** inherit from `bedrock_server_manager.plugins.plugin_base.PluginBase`. When your plugin is initialized, you are provided with three essential attributes:

-   `self.name` (str): The name of your plugin, derived from its filename.
-   `self.logger` (logging.Logger): A pre-configured Python logger instance. All messages sent through this logger will be automatically prefixed with your plugin's name. **Always use this for logging.**
-   `self.api` (PluginAPI): Your gateway to interacting with the main application. This object allows you to call core functions like starting servers, sending commands, etc.

## 3. Understanding Event Hooks

Event hooks are methods from the `PluginBase` class that you can override in your plugin. The Plugin Manager will automatically call these methods when the corresponding event occurs in the application.

-   **`before_*` events:** These are called *before* an action is attempted. They allow you to prepare for an action or potentially log that it's about to happen.
-   **`after_*` events:** These are called *after* an action has been attempted. They are always passed a `result` dictionary, which is the exact return value from the API function that was called. You can inspect this dictionary (`result['status']`, `result['message']`, etc.) to see if the action succeeded or failed.

## 4. Complete List of Event Hooks

Here are all the methods you can implement in your plugin class to react to application events.

### Plugin Lifecycle Events
-   `on_load(self)`
    -   Called once when your plugin is successfully loaded by the Plugin Manager.
-   `on_unload(self)`
    -   Called once when the application is shutting down.

### Server Start/Stop Events
-   `before_server_start(self, server_name: str, mode: str)`
    -   Called just before a server start is attempted.
    -   **Args:**
        -   `server_name` (str): The name of the server being started.
        -   `mode` (str): The start mode (`'direct'` or `'detached'`).
-   `after_server_start(self, server_name: str, result: dict)`
    -   Called just after a server start has been attempted.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `result` (dict): The dictionary returned by the `start_server` API call.
-   `before_server_stop(self, server_name: str)`
    -   Called just before a server stop is attempted.
    -   **Args:**
        -   `server_name` (str): The name of the server being stopped.
-   `after_server_stop(self, server_name: str, result: dict)`
    -   Called just after a server stop has been attempted.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `result` (dict): The dictionary returned by the `stop_server` API call.

### Server Command Events
-   `before_command_send(self, server_name: str, command: str)`
    -   Called before a command is sent to a server.
    -   **Args:**
        -   `server_name` (str): The name of the server receiving the command.
        -   `command` (str): The command string to be sent.
-   `after_command_send(self, server_name: str, command: str, result: dict)`
    -   Called after a command has been sent to a server.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `command` (str): The command string that was sent.
        -   `result` (dict): The dictionary returned by the `send_command` API call.

### Backup & Restore Events
-   `before_backup(self, server_name: str, backup_type: str, **kwargs)`
    -   Called before a backup operation begins.
    -   **Args:**
        -   `server_name` (str): The name of the server being backed up.
        -   `backup_type` (str): The type of backup (`'world'`, `'config_file'`, or `'all'`).
        -   `**kwargs`: Additional context, like `file_to_backup`.
-   `after_backup(self, server_name: str, backup_type: str, result: dict, **kwargs)`
    -   Called after a backup operation completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `backup_type` (str): The type of backup.
        -   `result` (dict): The dictionary returned by the backup API call.
-   `before_restore(self, server_name: str, restore_type: str, **kwargs)`
    -   Called before a restore operation begins.
    -   **Args:**
        -   `server_name` (str): The name of the server being restored.
        -   `restore_type` (str): The type of restore (`'world'`, `'config_file'`, or `'all'`).
        -   `**kwargs`: Additional context, like `backup_file_path`.
-   `after_restore(self, server_name: str, restore_type: str, result: dict, **kwargs)`
    -   Called after a restore operation completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `restore_type` (str): The type of restore.
        -   `result` (dict): The dictionary returned by the restore API call.
-   `before_prune_backups(self, server_name: str)`
    -   Called before old backups are pruned for a server.
    -   **Args:**
        -   `server_name` (str): The name of the server whose backups are being pruned.
-   `after_prune_backups(self, server_name: str, result: dict)`
    -   Called after an attempt to prune old backups completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `result` (dict): The dictionary returned by the `prune_old_backups` API call.

### World Management Events
-   `before_world_export(self, server_name: str, export_dir: str)`
    -   Called before a server's world is exported.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `export_dir` (str): The target directory for the exported `.mcworld` file.
-   `after_world_export(self, server_name: str, result: dict)`
    -   Called after an attempt to export a world completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `result` (dict): The dictionary returned by the `export_world` API call.
-   `before_world_import(self, server_name: str, file_path: str)`
    -   Called before a `.mcworld` file is imported to a server.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `file_path` (str): The path to the `.mcworld` file being imported.
-   `after_world_import(self, server_name: str, result: dict)`
    -   Called after an attempt to import a world completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `result` (dict): The dictionary returned by the `import_world` API call.
-   `before_world_reset(self, server_name: str)`
    -   Called before a server's active world directory is deleted.
    -   **Args:**
        -   `server_name` (str): The name of the server whose world is being reset.
-   `after_world_reset(self, server_name: str, result: dict)`
    -   Called after an attempt to reset a world completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `result` (dict): The dictionary returned by the `reset_world` API call.

### Addon Management Events
-   `before_addon_import(self, server_name: str, addon_file_path: str)`
    -   Called before an addon file is imported to a server.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `addon_file_path` (str): The path to the addon file being imported.
-   `after_addon_import(self, server_name: str, result: dict)`
    -   Called after an attempt to import an addon completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `result` (dict): The dictionary returned by the `import_addon` API call.

### Server Configuration Events
-   `before_allowlist_change(self, server_name: str, players_to_add: list, players_to_remove: list)`
    -   Called before a server's `allowlist.json` is modified.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `players_to_add` (list): A list of player data dictionaries to be added.
        -   `players_to_remove` (list): A list of player name strings to be removed.
-   `after_allowlist_change(self, server_name: str, result: dict)`
    -   Called after an attempt to modify the allowlist completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `result` (dict): The dictionary returned by the allowlist modification API call.
-   `before_permission_change(self, server_name: str, xuid: str, permission: str)`
    -   Called before a player's permission level is changed.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `xuid` (str): The XUID of the player whose permission is changing.
        -   `permission` (str): The new permission level (e.g., `'operator'`).
-   `after_permission_change(self, server_name: str, xuid: str, result: dict)`
    -   Called after an attempt to change a player's permission completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `xuid` (str): The XUID of the player.
        -   `result` (dict): The dictionary returned by the permission change API call.
-   `before_properties_change(self, server_name: str, properties: dict)`
    -   Called before `server.properties` is modified.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `properties` (dict): A dictionary of properties to be changed.
-   `after_properties_change(self, server_name: str, result: dict)`
    -   Called after an attempt to modify `server.properties` completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `result` (dict): The dictionary returned by the `modify_server_properties` API call.

### Server Installation & Update Events
-   `before_server_install(self, server_name: str, target_version: str)`
    -   Called before a new server installation begins.
    -   **Args:**
        -   `server_name` (str): The name of the new server.
        -   `target_version` (str): The version of the server to be installed.
-   `after_server_install(self, server_name: str, result: dict)`
    -   Called after a new server installation attempt completes.
    -   **Args:**
        -   `server_name` (str): The name of the new server.
        -   `result` (dict): The dictionary returned by the `install_new_server` API call.
-   `before_server_update(self, server_name: str, target_version: str)`
    -   Called before an existing server is updated.
    -   **Args:**
        -   `server_name` (str): The name of the server being updated.
        -   `target_version` (str): The version the server is being updated to.
-   `after_server_update(self, server_name: str, result: dict)`
    -   Called after a server update attempt completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `result` (dict): The dictionary returned by the `update_server` API call.

### Player Database Events
-   `before_players_add(self, players_data: list)`
    -   Called before players are manually added to the central player DB.
    -   **Args:**
        -   `players_data` (list): A list of player dictionaries, each with `'name'` and `'xuid'`.
-   `after_players_add(self, result: dict)`
    -   Called after an attempt to manually add players completes.
    -   **Args:**
        -   `result` (dict): The dictionary returned by the `add_players_manually` API call.
-   `before_player_db_scan(self)`
    -   Called before a scan of all server logs for new players begins.
-   `after_player_db_scan(self, result: dict)`
    -   Called after a scan of server logs for players has completed.
    -   **Args:**
        -   `result` (dict): The dictionary returned by the `scan_and_update_player_db` API call.

### System & Application Events
-   `before_service_change(self, server_name: str, action: str)`
    -   Called before a system service (e.g., systemd) is changed.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `action` (str): The action being performed (`'create'`, `'enable'`, `'disable'`).
-   `after_service_change(self, server_name: str, action: str, result: dict)`
    -   Called after an attempt to change a system service completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `action` (str): The action that was performed.
        -   `result` (dict): The dictionary returned by the service change API call.
-   `before_autoupdate_change(self, server_name: str, new_value: bool)`
    -   Called before a server's autoupdate setting is changed.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `new_value` (bool): The new boolean value for the autoupdate setting.
-   `after_autoupdate_change(self, server_name: str, result: dict)`
    -   Called after an attempt to change the autoupdate setting completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `result` (dict): The dictionary returned by the `set_autoupdate` API call.
-   `before_prune_download_cache(self, download_dir: str, keep_count: int)`
    -   Called before the global download cache is pruned.
    -   **Args:**
        -   `download_dir` (str): The directory being pruned.
        -   `keep_count` (int): The number of files to keep.
-   `after_prune_download_cache(self, result: dict)`
    -   Called after an attempt to prune the download cache completes.
    -   **Args:**
        -   `result` (dict): The dictionary returned by the `prune_download_cache` API call.

## 5. Using the Plugin API (`self.api`)
The `self.api` object is your tool for making the application perform actions. It's a bridge that safely exposes core functions to your plugin.

For example, to send a "say Hello" command to a server from within an event hook, you would do:

```python
def after_server_start(self, server_name: str, result: dict):
    if result.get("status") == "success":
        try:
            self.api.send_command(
                server_name=server_name,
                command="say The server is now online!"
            )
            self.logger.info("Sent welcome message.")
        except Exception as e:
            self.logger.error(f"Failed to send welcome message: {e}")
```

## 7. Available API Functions

The following is a list of functions available through `self.api`. All functions return a dictionary, typically with a `{"status": "success", ...}` or `{"status": "error", "message": "..."}` structure.

### Server Management

-   `start_server(server_name: str, mode: str = "direct") -> Dict[str, Any]`
    -   Starts the specified server. `mode` can be `'direct'` (blocking) or `'detached'` (background).
-   `stop_server(server_name: str, mode: str = "direct") -> Dict[str, str]`
    -   Stops the specified server.
-   `restart_server(server_name: str, send_message: bool = True) -> Dict[str, str]`
    -   Restarts the specified server by orchestrating stop and start calls.
-   `send_command(server_name: str, command: str) -> Dict[str, str]`
    -   Sends a command to a running server.
-   `delete_server_data(server_name: str, stop_if_running: bool = True) -> Dict[str, str]`
    -   **DESTRUCTIVE.** Deletes all data for a server (installation, config, backups).

### Server Installation & Configuration

-   `install_new_server(server_name: str, target_version: str = "LATEST") -> Dict[str, Any]`
    -   Installs a new server.
-   `update_server(server_name: str, send_message: bool = True) -> Dict[str, Any]`
    -   Updates an existing server to its configured target version.
-   `get_server_properties(server_name: str) -> Dict[str, Any]`
    -   Reads and returns the `server.properties` as a dictionary.
-   `modify_server_properties(server_name: str, properties_to_update: Dict[str, str], restart_after_modify: bool = True) -> Dict[str, str]`
    -   Modifies one or more properties in `server.properties`.
-   `get_server_allowlist(server_name: str) -> Dict[str, Any]`
    -   Retrieves the `allowlist.json` content.
-   `add_players_to_allowlist(server_name: str, new_players_data: List[Dict[str, Any]]) -> Dict[str, Any]`
    -   Adds players to the allowlist.
-   `remove_players_from_allowlist(server_name: str, player_names: List[str]) -> Dict[str, Any]`
    -   Removes players from the allowlist by name.
-   `get_server_permissions(server_name: str) -> Dict[str, Any]`
    -   Retrieves the `permissions.json` content, enriched with player names.
-   `configure_player_permission(server_name: str, xuid: str, player_name: Optional[str], permission: str) -> Dict[str, str]`
    -   Sets a player's permission level (e.g., 'member', 'operator').

### Plugin Configuration API

These functions allow programmatic management of plugin statuses. They are primarily used by the `bsm plugin` CLI commands but can also be called by other plugins if needed.

-   `get_plugin_statuses() -> Dict[str, Any]`
    -   Retrieves the statuses of all discovered plugins. Synchronizes with `plugins.json` and plugin files on disk before returning.
    -   **Returns:** A dictionary, where the `plugins` key contains an object mapping plugin names to their boolean enabled status (e.g., `{"status": "success", "plugins": {"MyPlugin": true, "AnotherPlugin": false}}`).
-   `set_plugin_status(plugin_name: str, enabled: bool) -> Dict[str, Any]`
    -   Sets the enabled/disabled status for a specific plugin in `plugins.json`.
    -   **Args:**
        -   `plugin_name` (str): The name of the plugin (filename without `.py`).
        -   `enabled` (bool): `True` to enable, `False` to disable.
    -   **Returns:** A dictionary indicating success or failure (e.g., `{"status": "success", "message": "Plugin 'MyPlugin' has been enabled."}`).
    -   **Raises:** `UserInputError` if the plugin name is not found among discoverable plugins.

### World Management

-   `get_world_name(server_name: str) -> Dict[str, Any]`
    -   Retrieves the `level-name` from `server.properties`.
-   `export_world(server_name: str, export_dir: Optional[str] = None, stop_start_server: bool = True) -> Dict[str, Any]`
    -   Exports the active world to a `.mcworld` file.
-   `import_world(server_name: str, selected_file_path: str, stop_start_server: bool = True) -> Dict[str, str]`
    -   **DESTRUCTIVE.** Imports a `.mcworld` file, replacing the active world.
-   `reset_world(server_name: str) -> Dict[str, str]`
    -   **DESTRUCTIVE.** Deletes the active world directory. A new world will be generated on next start.

### Addon Management

-   `import_addon(server_name: str, addon_file_path: str, stop_start_server: bool = True, restart_only_on_success: bool = True) -> Dict[str, str]`
    -   Installs an addon (`.mcaddon` or `.mcpack`) to the specified server.

### Backup & Restore

-   `list_backup_files(server_name: str, backup_type: str) -> Dict[str, Any]`
    -   Lists available backup files for a given type (e.g., 'world').
-   `backup_world(server_name: str, stop_start_server: bool = True) -> Dict[str, str]`
    -   Creates a backup of the server's world.
-   `backup_config_file(server_name: str, file_to_backup: str, stop_start_server: bool = True) -> Dict[str, str]`
    -   Creates a backup of a specific config file (e.g., `server.properties`).
-   `backup_all(server_name: str, stop_start_server: bool = True) -> Dict[str, Any]`
    -   Performs a full backup of the world and all config files.
-   `restore_world(server_name: str, backup_file_path: str, stop_start_server: bool = True) -> Dict[str, str]`
    -   **DESTRUCTIVE.** Restores a world from a specific backup file.
-   `restore_config_file(server_name: str, backup_file_path: str, stop_start_server: bool = True) -> Dict[str, str]`
    -   Restores a specific config file from a backup.
-   `restore_all(server_name: str, stop_start_server: bool = True) -> Dict[str, Any]`
    -   **DESTRUCTIVE.** Restores the server from the latest available backups of all types.
-   `prune_old_backups(server_name: str) -> Dict[str, str]`
    -   Deletes old backups based on retention settings.

### Player Database

-   `get_all_known_players() -> Dict[str, Any]`
    -   Retrieves all player data from the central `players.json`.
-   `add_players_manually(player_strings: List[str]) -> Dict[str, Any]`
    -   Adds players to the central `players.json`. `player_strings` is a list like `["Gamertag,XUID"]`.
-   `scan_and_update_player_db() -> Dict[str, Any]`
    -   Scans all server logs to find and save new player data.

### System & Application

-   `get_application_info() -> Dict[str, Any]`
    -   Returns general info like version, OS, and key directories.
-   `get_all_servers_data() -> Dict[str, Any]`
    -   Retrieves status and version for all detected servers.
-   `get_bedrock_process_info(server_name: str) -> Dict[str, Any]`
    -   Retrieves resource usage (CPU, RAM) for a running server process.
-   `create_systemd_service(server_name: str, autostart: bool = False) -> Dict[str, str]`
    -   (Linux-only) Creates a systemd user service for the server.
-   `enable_server_service(server_name: str) -> Dict[str, str]`
    -   (Linux-only) Enables the systemd service to start on boot.
-   `disable_server_service(server_name: str) -> Dict[str, str]`
    -   (Linux-only) Disables the systemd service from starting on boot.
-   `set_autoupdate(server_name: str, autoupdate_value: str) -> Dict[str, str]`
    -   Sets the 'autoupdate' flag for a server (`'true'` or `'false'`).
-   `prune_download_cache(download_dir: str, keep_count: Optional[int] = None) -> Dict[str, str]`
    -   Prunes old downloaded server archives.

### Web Server

-   `start_web_server(host: Optional[Union[str, List[str]]] = None, debug: bool = False, mode: str = "direct") -> Dict[str, Any]`
    -   Starts the application's web server.
-   `stop_web_server() -> Dict[str, str]`
    -   Stops the detached web server process.
-   `get_web_server_status() -> Dict[str, Any]`
    -   Checks the status of the web server process.

## 7. Example Plugin: Auto-Backup Announcer

This plugin announces in-game when a backup is starting and when it has completed.

```python
# backup_announcer.py
from bedrock_server_manager.plugins.plugin_base import PluginBase

class BackupAnnouncer(PluginBase):

    def before_backup(self, server_name: str, backup_type: str, **kwargs):
        """Called before any backup operation starts."""
        self.logger.info(f"A '{backup_type}' backup is starting for '{server_name}'. Announcing in-game.")
        try:
            # We use the API to send a command to the server
            self.api.send_command(
                server_name=server_name,
                command=f"say Starting {backup_type} backup... The server may shut down breifly."
            )
        except Exception as e:
            # It's possible the server is stopped, so send_command will fail.
            # We log this as a warning, not an error.
            self.logger.warning(f"Could not send backup start announcement to '{server_name}': {e}")

    def after_backup(self, server_name: str, backup_type: str, result: dict, **kwargs):
        """Called after any backup operation completes."""
        self.logger.info(f"Backup operation finished for '{server_name}'.")

        # Check the result dictionary to see if the backup was successful
        if result.get("status") == "success":
            message = f"say {backup_type.capitalize()} backup completed successfully!"
        else:
            message = f"say {backup_type.capitalize()} backup failed. Check server logs."

        try:
            self.api.send_command(server_name=server_name, command=message)
        except Exception as e:
            self.logger.warning(f"Could not send backup completion announcement to '{server_name}': {e}")

```

## 8. Best Practices

-   **Always use `self.logger`:** Do not use `print()`. The provided logger is configured to work with the application's logging system.
-   **Handle exceptions:** When using `self.api`, wrap your calls in `try...except` blocks. An API call can fail for many reasons (e.g., server is stopped, files don't exist), and your plugin should handle this gracefully without crashing.
-   **Check the `result` dictionary:** The `after_*` events provide you with the outcome of the operation. Always check `result['status']` before assuming an action was successful.
-   **Be mindful of blocking operations:** Your plugin code runs in the main application thread. Avoid long-running or blocking tasks inside your event handlers, as this will freeze the application.