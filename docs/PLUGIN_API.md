﻿﻿﻿<div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg" alt="BSM Logo" width="150">
</div>

# Bedrock Server Manager: Plugin API

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
    *   [Web Server Events](#web-server-events)
6.  [Custom Plugin Events (Inter-Plugin Communication)](#6-custom-plugin-events-inter-plugin-communication)
7.  [Using the Plugin API (`self.api`)](#7-using-the-plugin-api-selfapi)
8.  [Available API Functions](#8-available-api-functions)
    *   [Server Management](#server-management)
    *   [Server Installation & Configuration](#server-installation--configuration)
    *   [Custom Server Configuration (config.json)](#custom-server-configuration-configjson)
    *   [Plugin Configuration API](#plugin-configuration-api)
    *   [World Management](#world-management)
    *   [Addon Management](#addon-management)
    *   [Backup & Restore](#backup--restore)
    *   [Player Database](#player-database)
    *   [System & Application](#system--application)
    *   [Web Server](#web-server)
    *   [Inter-Plugin Communication / Custom Events](#inter-plugin-communication--custom-events)
9. [Best Practices](#10-best-practices)

---

## 1. Getting Started: Your First Plugin

Creating a plugin is straightforward:

1.  **Locate the `plugins` directory:** Find the application's data directory. Inside, there will be a `plugins` folder. If it doesn't exist, the application will create it on first run.
2.  **Create a Python file:** Inside the `plugins` directory, create a new file (e.g., `my_first_plugin.py`). The filename (without the `.py`) will be used as your plugin's name.
3.  **Write the code:** In your new file, create a class that inherits from `PluginBase` and implement the event hooks you're interested in.

Here is the most basic "Hello World" plugin:

```python
# my_first_plugin.py
from bedrock_server_manager import PluginBase

class MyFirstPlugin(PluginBase):
    """
    This is a example description that will be saved in plugins.json
    """
    version = "1.0.0"  # Mandatory version attribute
    def on_load(self):
        """This event is called when the plugin is loaded by the manager."""
        self.logger.info("Hello from MyFirstPlugin!")

    def after_server_start(self, server_name: str, result: dict):
        """This event is called after a server has started."""
        if result.get("status") == "success":
            self.logger.info(f"Server '{server_name}' has started successfully!")
```

4.  **Run the application:** Start the Bedrock Server Manager. You should see your "Hello from MyFirstPlugin!" message in the logs.
5.  **Enable your plugin:** If it's not a default-enabled plugin, use the `bedrock-server-manager plugin enable my_first_plugin` command to activate it. (See [Managing Plugins](#2-managing-plugins) for more details).


## 2. Managing Plugins

The Bedrock Server Manager allows users to control which plugins are active through a `plugins.json` configuration file and new CLI commands.

### `plugins.json` Configuration File

-   **Location:** This file is located in your application's configuration directory (typically `~/.bedrock-server-manager/.config/plugins.json`).
-   **Functionality:** It stores a JSON object where keys are plugin names (derived from their filenames, e.g., `"MyAwesomePlugin"`) and values are booleans (`true` to enable, `false` to disable).
-   **Discovery:** When the application starts, the `PluginManager` scans the plugin directories (`<app_data_dir>/plugins/` and the application's internal `default_plugins/` directory).
    -   Any new `.py` files found that are not already in `plugins.json` will be added to it.
-   **Default State for New Plugins:**
    -   **Standard Plugins:** By default, newly discovered user-added plugins are added to `plugins.json` as `disabled` (`false`).
    -   **Default Enabled Plugins:** A predefined list of essential built-in plugins (e.g., `ServerLifecycleNotificationsPlugin`, `AutoReloadPlugin`) are automatically enabled (`true`) by default when first discovered. This ensures core extended functionalities are active out-of-the-box. You can still disable them manually if needed.
    The current list of default-enabled plugins includes:
        - `server_lifecycle_notifications`
        - `world_operation_notifications`
        - `auto_reload_config`
        - `update_before_start`

### CLI Commands for Plugin Management

You can easily manage which plugins are active using the `bedrock-server-manager plugin` command-line interface:

-   **`bedrock-server-manager plugin list`**
    -   Displays all discovered plugins and their current status (Enabled/Disabled).
    -   Example:
        ```
        $ bedrock-server-manager plugin list
        Fetching plugin statuses...
        Plugin Statuses:
        Plugin Name                         | Status
        ------------------------------------|----------
        ServerLifecycleNotificationsPlugin  | Enabled
        MyCustomPlugin                      | Disabled
        ```

-   **`bedrock-server-manager plugin enable <plugin_name>`**
    -   Enables the specified plugin (sets its value to `true` in `plugins.json`).
    -   Example: `bedrock-server-manager plugin enable MyCustomPlugin`

-   **`bedrock-server-manager plugin disable <plugin_name>`**
    -   Disables the specified plugin (sets its value to `false` in `plugins.json`).
    -   Example: `bedrock-server-manager plugin disable server_lifecycle_notifications`

Changes made via these CLI commands are immediately saved to `plugins.json`. The application will load or ignore plugins based on this configuration the next time it fully initializes its plugin system (typically on startup, of after reloading all plugins).

## 3. The `PluginBase` Class

Every plugin **must** inherit from `bedrock_server_manager.PluginBase`. When your plugin is initialized, you are provided with three essential attributes:

-   `self.name` (str): The name of your plugin, derived from its filename.
-   `self.logger` (logging.Logger): A pre-configured Python logger instance. All messages sent through this logger will be automatically prefixed with your plugin's name. **Always use this for logging.**
-   `self.api` (PluginAPI): Your gateway to interacting with the main application. This object allows you to call core functions like starting servers, sending commands, etc.

**Important Plugin Class Requirements:**

*   **`version` Attribute (Mandatory):** Your plugin class **must** define a class-level attribute named `version` as a string (e.g., `version = "1.0.0"`). This version is used by the Plugin Manager for display and potential compatibility checks. Plugins without a valid, non-empty `version` attribute will not be loaded.
*   **Description (from Docstring):** The description for your plugin (shown in plugin listings and management UIs) is automatically extracted from the main docstring of your plugin class. Make sure to write a clear and concise docstring for your class.

    ```python
    class MyAwesomePlugin(PluginBase):
        """
        This is the description of MyAwesomePlugin.
        It will be saved in the plugins.json.
        """
        version = "1.2.3" # Mandatory

        def on_load(self):
            self.logger.info("MyAwesomePlugin loaded!")
    ```

## 4. Understanding Event Hooks

Event hooks are methods from the `PluginBase` class that you can override in your plugin. The Plugin Manager will automatically call these methods when the corresponding event occurs in the application.

-   **`before_*` events:** These are called *before* an action is attempted. They allow you to prepare for an action or potentially log that it's about to happen.
-   **`after_*` events:** These are called *after* an action has been attempted. They are always passed a `result` dictionary, which is the exact return value from the API function that was called. You can inspect this dictionary (`result['status']`, `result['message']`, etc.) to see if the action succeeded or failed.

## 5. Complete List of Event Hooks

Here are all the methods you can implement in your plugin class to react to application events.

### Plugin Lifecycle Events
-   `on_load(self)`
    -   Required, called once when your plugin is successfully loaded by the Plugin Manager.
-   `on_unload(self)`
    -   Optional, called once when the application is shutting down.

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
-   `before_server_stop(self, server_name: str, mode: str)`
    -   Called just before a server stop is attempted.
    -   **Args:**
        -   `server_name` (str): The name of the server being stopped.
        -   `mode` (str): The mode or reason for stopping.
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
        -   `**kwargs`: Additional context. If `backup_type` is `'config_file'`, this will include `file_to_backup: str` (the name of the config file being backed up, e.g., "server.properties"). May also include `stop_start_server: bool` reflecting the API call's parameter.
-   `after_backup(self, server_name: str, backup_type: str, result: dict, **kwargs)`
    -   Called after a backup operation completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `backup_type` (str): The type of backup.
        -   `result` (dict): The dictionary returned by the backup API call.
        -   `**kwargs`: Additional context, mirrors `before_backup`.
-   `before_restore(self, server_name: str, restore_type: str, **kwargs)`
    -   Called before a restore operation begins.
    -   **Args:**
        -   `server_name` (str): The name of the server being restored.
        -   `restore_type` (str): The type of restore (`'world'`, `'config_file'`, or `'all'`).
        -   `**kwargs`: Additional context. This will include `backup_file_path: str` (the full path to the backup file being used for restore) if `restore_type` is `'world'` or `'config_file'`. May also include `stop_start_server: bool`.
-   `after_restore(self, server_name: str, restore_type: str, result: dict, **kwargs)`
    -   Called after a restore operation completes.
    -   **Args:**
        -   `server_name` (str): The name of the server.
        -   `restore_type` (str): The type of restore.
        -   `result` (dict): The dictionary returned by the restore API call.
        -   `**kwargs`: Additional context, mirrors `before_restore`.
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
-   `on_manager_startup(self)`
    -   Called once when the Plugin Manager finishes loading all plugins and the API is ready. This signifies that the application is fully initialized.

### Web Server Events
-   `before_web_server_start(self, mode: str)`
    -   Called just before the web server start is attempted.
    -   **Args:**
        -   `mode` (str): The start mode (`'direct'` or `'detached'`).
-   `after_web_server_start(self, result: dict)`
    -   Called just after a web server start has been attempted.
    -   **Args:**
        -   `result` (dict): The dictionary returned by the `start_web_server` API call.
-   `before_web_server_stop(self)`
    -   Called just before a web server stop is attempted.
-   `after_web_server_stop(self, result: dict)`
    -   Called just after a web server stop has been attempted.
    -   **Args:**
        -   `result` (dict): The dictionary returned by the `stop_web_server` API call.


## 6. Custom Plugin Events (Inter-Plugin Communication)

The plugin system includes a powerful feature allowing plugins to define, send, and listen to their own custom events. This enables more complex interactions and communication:
*   Between different plugins.
*   Between external triggers (like an HTTP API call or a CLI command) and plugins.

This system promotes decoupling, as event senders and listeners don't need direct knowledge of each other's implementations.

**Core Concepts:**

*   **Event Names:** Events are identified by string names. It is highly recommended to **namespace** your event names, typically by prefixing them with your plugin's name or a relevant context (e.g., `"myplugin:custom_action"`, `"automation:im_home"`, `"system:high_load"`). This helps prevent naming conflicts.
*   **Sending Events:**
    *   **From a Plugin:** A plugin can broadcast an event using `self.api.send_event("your:event_name", arg1, arg2, keyword_arg="value")`.
    *   **From an External Source:**
        *   **HTTP API:** Use the `POST /api/plugins/trigger_event` endpoint.
        *   **CLI:** Use the `bsm plugin trigger_event <EVENT_NAME> --payload-json '{...}'` command.
        Both methods allow passing a JSON payload that becomes keyword arguments for listeners.
*   **Listening for Events:** A plugin can register a callback function to be executed whenever a specific event is sent. This is typically done in the plugin's `on_load` method using `self.api.listen_for_event("some:event_to_listen_for", self.my_callback_method)`.
*   **Callback Arguments:** The callback method will receive:
    *   Any positional arguments (`*args`) passed if the event was sent by `self.api.send_event()` from another plugin.
    *   Any keyword arguments (`**kwargs`) passed during `self.api.send_event()`, or derived from the `payload` object if the event was triggered via the HTTP API or CLI.
    *   An additional special keyword argument `_triggering_plugin` (str): This is automatically injected by the Plugin Manager.
        *   If sent by another plugin, it's the name of that plugin.
        *   If sent via the `/api/plugins/trigger_event` HTTP endpoint or the `bsm plugin trigger_event` CLI command, this will be `"external_api_trigger"` (assuming the CLI command internally calls the same API function `trigger_external_plugin_event_api`).

**Example 1: Ping-Pong Plugins (Inter-Plugin Communication)**

This example illustrates a simple request-response style interaction directly between two plugins. `PingPlugin` sends a "ping" and `PongPlugin` listens for it and can send a "pong" back.

**`ping_plugin.py`:**
```python
# <PLUGIN_DIR>/ping_plugin.py
import time
from bedrock_server_manager import PluginBase

class PingPlugin(PluginBase):
    version = "1.0.1"

    def after_server_start(self, server_name: str, result: dict):
        if result.get("status") == "success":
            self.logger.info(f"Server '{server_name}' started. Sending 'pingplugin:ping' from '{self.name}'.")
            ping_payload = {
                "message": f"Ping from {self.name} for server {server_name}!",
                "timestamp": time.time()
            }
            # Send the custom event to other plugins
            self.api.send_event("pingplugin:ping", server_name=server_name, data=ping_payload)
```

**`pong_plugin.py`:**
```python
# <PLUGIN_DIR>/pong_plugin.py
from bedrock_server_manager import PluginBase

class PongPlugin(PluginBase):
    version = "1.0.1"

    def on_load(self):
        self.logger.info(f"'{self.name}' loaded. Listening for 'pingplugin:ping' events.")
        # Register a listener for the custom event from PingPlugin
        self.api.listen_for_event("pingplugin:ping", self.handle_ping_event)

    def handle_ping_event(self, *args, **kwargs): # Using *args, **kwargs for flexibility
        triggering_plugin = kwargs.pop('_triggering_plugin', 'UnknownPlugin') # Expected: "ping_plugin"
        server_name = kwargs.get('server_name', 'N/A')
        data_payload = kwargs.get('data', {})
        message = data_payload.get('message', 'No message')
        timestamp = data_payload.get('timestamp', 0)

        self.logger.info(
            f"'{self.name}' received 'pingplugin:ping' from '{triggering_plugin}'!"
        )
        self.logger.info(f"  Server: {server_name}, Message: {message}, Timestamp: {timestamp}")
        
        self.logger.info(f"'{self.name}' sending 'pongplugin:pong' in response.")
        self.api.send_event("pongplugin:pong", original_server=server_name, response_to=triggering_plugin)

    def on_unload(self):
        self.logger.info(f"'{self.name}' is unloading.")
```

---

**Example 2: "I'm Home" Automation (Triggered via HTTP API)**

This example shows how an external home automation system can trigger a plugin to start a server when a user arrives home. The external system would use the `/api/plugins/trigger_event` HTTP endpoint.

**Triggering the Event (External System):**
An HTTP POST request to `/api/plugins/trigger_event` with the following JSON body:
```json
{
    "event_name": "automation:user_arrived_home",
    "payload": {
        "user_id": "user123",
        "location_name": "Home"
    }
}
```

**`home_automation_starter_plugin.py`:**
```python
# <PLUGIN_DIR>/home_automation_starter_plugin.py
from bedrock_server_manager import PluginBase

TARGET_SERVER_NAME = "main_survival" # Server to start

class HomeAutomationStarterPlugin(PluginBase):
    version = "1.0.0"

    def on_load(self):
        self.logger.info(
            f"'{self.name}' loaded. Listening for 'automation:user_arrived_home' to start '{TARGET_SERVER_NAME}'."
        )
        self.api.listen_for_event("automation:user_arrived_home", self.handle_user_arrival)

    def handle_user_arrival(self, *args, **kwargs):
        trigger_source = kwargs.pop('_triggering_plugin', 'UnknownSource') # Expected: "external_api_trigger"
        user_id = kwargs.get('user_id', 'UnknownUser')
        
        self.logger.info(
            f"'{self.name}' received 'automation:user_arrived_home' from '{trigger_source}' for user '{user_id}'."
        )
        
        self.logger.info(f"Attempting to start server '{TARGET_SERVER_NAME}'.")
        try:
            status = self.api.get_server_running_status(server_name=TARGET_SERVER_NAME) # Assumes this API function exists
            if status.get("running"):
                 self.logger.info(f"Server '{TARGET_SERVER_NAME}' is already running.")
                 return

            start_result = self.api.start_server(server_name=TARGET_SERVER_NAME, mode="detached")
            if start_result and start_result.get("status") == "success":
                self.logger.info(f"Successfully initiated start for '{TARGET_SERVER_NAME}'.")
            else:
                self.logger.error(f"Failed to start '{TARGET_SERVER_NAME}': {start_result.get('message')}")
        except Exception as e:
            self.logger.error(f"Error starting server '{TARGET_SERVER_NAME}': {e}", exc_info=True)

    def on_unload(self):
        self.logger.info(f"'{self.name}' is unloading.")
```

---

**Example 3: System Resource Monitor (Triggered via CLI)**

This example demonstrates using the `bsm plugin trigger_event` CLI command to notify a plugin about system resource status, which could then take action like warning players or shutting down a server.

**Triggering the Event (CLI):**
```bash
bsm plugin trigger_event system:high_resource_load --payload-json \
  '{"cpu_percent": 92, "memory_free_mb": 512, "target_server": "creative_builds", "severity": "critical"}'
```

**`system_resource_guardian_plugin.py`:**
```python
# <PLUGIN_DIR>/system_resource_guardian_plugin.py
from bedrock_server_manager import PluginBase

class SystemResourceGuardianPlugin(PluginBase):
    version = "1.0.0"

    CPU_CRITICAL_THRESHOLD = 90.0  # Percent
    MEMORY_CRITICAL_MB = 1024    # Megabytes

    def on_load(self):
        self.logger.info(f"'{self.name}' loaded. Listening for 'system:high_resource_load'.")
        self.api.listen_for_event("system:high_resource_load", self.handle_resource_alert)

    def handle_resource_alert(self, *args, **kwargs):
        trigger_source = kwargs.pop('_triggering_plugin', 'UnknownSource') # Expected: "external_api_trigger" or similar
        
        cpu = kwargs.get('cpu_percent', 0.0)
        mem_free = kwargs.get('memory_free_mb', float('inf'))
        target_server = kwargs.get('target_server')
        severity = kwargs.get('severity', 'warning')

        self.logger.info(
            f"'{self.name}' received 'system:high_resource_load' from '{trigger_source}'."
        )
        self.logger.info(
            f"  Details: CPU={cpu}%, MemFreeMB={mem_free}, Target='{target_server}', Severity='{severity}'"
        )

        if not target_server:
            self.logger.warning("  No 'target_server' in payload. No action taken.")
            return

        message_to_server = None
        should_shutdown = False

        if severity == "critical" or cpu >= self.CPU_CRITICAL_THRESHOLD or mem_free <= self.MEMORY_CRITICAL_MB:
            message_to_server = f"WARNING: Critical system load detected (CPU: {cpu}%, MemFree: {mem_free}MB). Server '{target_server}' may be shut down soon."
            should_shutdown = True # Or based on severity == "critical"
            self.logger.critical(f"  CRITICAL LOAD! {message_to_server}")
        elif cpu > 75 or mem_free < 2048: # Example warning thresholds
             message_to_server = f"Notice: System resource usage is high (CPU: {cpu}%, MemFree: {mem_free}MB)."
             self.logger.warning(f"  High load warning. {message_to_server}")
        
        if message_to_server:
            try:
                self.api.send_command(server_name=target_server, command=f"say {message_to_server}")
            except Exception as e:
                self.logger.error(f"  Failed to send warning to '{target_server}': {e}")
        
        if should_shutdown:
            self.logger.info(f"  Attempting to shut down server '{target_server}' due to critical load.")
            try:
                # Consider adding a delay here or a more graceful sequence if needed
                stop_result = self.api.stop_server(server_name=target_server, mode="graceful")
                if stop_result and stop_result.get("status") == "success":
                    self.logger.info(f"  Shutdown initiated for '{target_server}'.")
                else:
                    self.logger.error(f"  Failed to initiate shutdown for '{target_server}'.")
            except Exception as e:
                self.logger.error(f"  Error during shutdown of '{target_server}': {e}", exc_info=True)

    def on_unload(self):
        self.logger.info(f"'{self.name}' is unloading.")
```

This custom event system, combined with external triggers like CLI commands or HTTP API calls, allows for the creation of reactive and automated management tasks, enhancing the server manager's capabilities through modular plugin logic.

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

### Server Installation & Configuration

-   `install_new_server(server_name: str, target_version: str = "LATEST") -> Dict[str, Any]`
    -   Installs a new server.
-   `update_server(server_name: str, send_message: bool = True) -> Dict[str, Any]`
    -   Updates an existing server to its configured target version.
-   `get_server_properties_api(server_name: str) -> Dict[str, Any]`
    -   Reads and returns the `server.properties` as a dictionary.
-   `modify_server_properties(server_name: str, properties_to_update: Dict[str, str], restart_after_modify: bool = True) -> Dict[str, str]`
    -   Modifies one or more properties in `server.properties`.
-   `validate_server_property_value(property_name: str, value: str) -> Dict[str, str]`
    -   Validates a single server property value based on known rules.
-   `get_server_allowlist_api(server_name: str) -> Dict[str, Any]`
    -   Retrieves the `allowlist.json` content.
-   `add_players_to_allowlist_api(server_name: str, new_players_data: List[Dict[str, Any]]) -> Dict[str, Any]`
    -   Adds players to the allowlist.
-   `remove_players_from_allowlist(server_name: str, player_names: List[str]) -> Dict[str, Any]`
    -   Removes players from the allowlist by name.
-   `get_server_permissions_api(server_name: str) -> Dict[str, Any]`
    -   Retrieves the `permissions.json` content, enriched with player names.
-   `configure_player_permission(server_name: str, xuid: str, player_name: Optional[str], permission: str) -> Dict[str, str]`
    -   Sets a player's permission level (e.g., 'member', 'operator').

### Custom Server Configuration (config.json)

-   `write_server_config(server_name: str, key: str, value: Any) -> Dict[str, Any]`
    -   Writes a key-value pair to a server's JSON configuration file (`server_name_config.json`). This is for plugin-specific or user-defined settings, separate from `server.properties`.

### Plugin System API

-   `get_plugin_statuses() -> Dict[str, Any]`
    -   Retrieves the statuses and metadata of all discovered plugins.
    -   **Returns:** A dictionary, where the `plugins` key contains an object mapping plugin names to their configuration (e.g., `{"status": "success", "plugins": {"MyPlugin": {"enabled": true, "version": "1.0", ...}}}`).
  
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
-   `list_available_worlds_api() -> Dict[str, Any]`
    -   Lists available .mcworld files from the content directory.
-   `list_available_addons_api() -> Dict[str, Any]`
    -   Lists available .mcaddon and .mcpack files from the content directory.

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

-   `get_all_known_players_api() -> Dict[str, Any]`
    -   Retrieves all player data from the central `players.json`. 
-   `add_players_manually_api(player_strings: List[str]) -> Dict[str, Any]`
    -   Adds players to the central `players.json`. `player_strings` is a list like `["Gamertag,XUID"]`.
-   `scan_and_update_player_db_api() -> Dict[str, Any]`
    -   Scans all server logs to find and save new player data.

### System & Application

-   `get_application_info_api() -> Dict[str, Any]`
    -   Returns general info like application name, version, OS type, and key directories. (Replaces `get_system_and_app_info` and provides more detail)
-   `get_all_servers_data() -> Dict[str, Any]`
    -   Retrieves status and version for all detected servers.
-   `get_server_running_status(server_name: str) -> Dict[str, Any]`
    -   Checks if the server process is currently running. (Added from `api.info`)
-   `get_server_config_status(server_name: str) -> Dict[str, Any]`
    -   Gets the status from the server's configuration file. (Added from `api.info`)
-   `get_server_installed_version(server_name: str) -> Dict[str, Any]`
    -   Gets the installed version from the server's configuration file. (Added from `api.info`)
-   `get_bedrock_process_info(server_name: str) -> Dict[str, Any]`
    -   Retrieves resource usage (CPU, RAM) for a running server process.
-   `prune_download_cache(download_dir: str, keep_count: Optional[int] = None) -> Dict[str, str]`
    -   Prunes old downloaded server archives from the specified directory.
-   `validate_server_exist(server_name: str) -> Dict[str, Any]`
    -   Checks if a server's directory and executable exist, indicating a valid installation.
-   `validate_server_name_format(server_name: str) -> Dict[str, str]`
    -   Validates if a given string is a permissible format for a server name.
   
### Web Server

-   `get_web_server_status() -> Dict[str, Any]`
    -   Checks the status of the web server process.
 
### Inter-Plugin Communication / Custom Events

These functions enable plugins to send and receive custom events, allowing for more advanced interactions between different plugins.

-   `send_event(self, event_name: str, *args: Any, **kwargs: Any)`
    -   Triggers a custom plugin event, notifying all registered listeners.
    -   **Args:**
        -   `event_name` (str): The name of the custom event to trigger (e.g., `"myplugin:my_custom_action"`). It's good practice to namespace your event names with your plugin's name to avoid collisions.
        -   `*args`: Positional arguments to pass to the event listeners' callback functions.
        -   `**kwargs`: Keyword arguments to pass to the event listeners' callback functions.
    -   **Example:**
        ```python
        # In MySendingPlugin
        def some_action(self, server_name):
            self.logger.info(f"Sending 'myplugin:action_completed' event for server {server_name}")
            self.api.send_event(
                "myplugin:action_completed",
                server_name, # positional argument
                status="success", 
                item_count=5   # keyword arguments
            )
        ```

-   `listen_for_event(self, event_name: str, callback: Callable[..., None])`
    -   Registers a callback function to be executed when a specific custom plugin event is triggered.
    -   This is typically called in your plugin's `on_load` method.
    -   **Args:**
        -   `event_name` (str): The name of the custom event to listen for.
        -   `callback` (Callable): The function within your plugin to call when the event is triggered.
            -   This callback function will receive any `*args` and `**kwargs` that were passed when `send_event` was called.
            -   Additionally, the `PluginManager` will automatically inject a special keyword argument `_triggering_plugin` (str) into your callback, which holds the name of the plugin that sent the event.
    -   **Example:**
        ```python
        # In MyListeningPlugin
        def on_load(self):
            self.api.listen_for_event("myplugin:action_completed", self.handle_action_completed)
            self.logger.info("Listening for 'myplugin:action_completed' events.")

        def handle_action_completed(self, server_name_arg, status=None, item_count=0, _triggering_plugin=None):
            # server_name_arg was the positional argument from send_event
            # status and item_count were keyword arguments
            # _triggering_plugin is automatically added
            self.logger.info(
                f"Event 'myplugin:action_completed' received from plugin '{_triggering_plugin}' "
                f"for server '{server_name_arg}'. Status: {status}, Items: {item_count}"
            )
            # ... do something with the event data ...
        ```

## 8. Best Practices

-   **Always use `self.logger`:** Do not use `print()`. The provided logger is configured to work with the application's logging system.
-   **Handle exceptions:** When using `self.api`, wrap your calls in `try...except` blocks. An API call can fail for many reasons (e.g., server is stopped, files don't exist), and your plugin should handle this gracefully without crashing.
-   **Check the `result` dictionary:** The `after_*` events provide you with the outcome of the operation. Always check `result['status']` before assuming an action was successful.
-   **Be mindful of blocking operations:** Your plugin code runs in the main application thread. Avoid long-running or blocking tasks inside your event handlers, as this will freeze the application.
-   **Use the API for ooperations:** Do not directly manipulate files or directories related to the application. Always use the provided `self.api` functions to ensure consistency and proper error handling. 
    - If you need a method that is not available in the `self.api`, you can directly use the available [`BedrockServer`, `BedrockServerManager`, `BedrodkDownloader`, `Settings`] class methods, but ensure you handle any exceptions and log appropriately, and take note these methods may change at anytime in future versions.