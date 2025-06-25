<div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg" alt="Bedrock Server Manager Icon" width="200" height="200">
</div>

## Bedrock Server Manager:

### 3.0.0
1. BREAKING CHANGE: Completely refactored .py script to a pip package
   - Now installed/updated with `pip` command
2. Use `BEDROCK_SERVER_MANAGER_DATA_DIR` Environment Variable for default data location
   - Defaults to `$HOME/bedrock-server-manager` if variable doesnt exist
   - Follow your platforms documentation for setting Environment Variables
3. Logging refactored to use standard python logging
   - Most functions now raise Exceptions instead of returning an error code
4. Removed windows-start/stop commands
5. Added new commands
6. The following variables were added to script_config.json
    - CONTENT_DIR
    - DOWNLOAD_DIR
    - BACKUP_DIR
    - LOG_DIR
    - LOGS_KEEP
    - LOG_LEVEL

### 3.0.1
1. Added handlers module
   - Refactored cli to use handlers
2. Refactored settings module
   - Migrated settings to a class
3. Fixed logger variables
4. [WIP] Send command support for Windows
    - Requires pywin32 module to be installed
    - Requires seperate start method not currently available

### 3.0.2
1. Fixed EXPATH variable in Linux scheduler
2. Fixed Modify Windows Task

### 3.0.3
1. Fixed Linux resource usage monitor
2. Fixed Linux systemd enable/disable

### 3.1.0                                                                        
1. Added Web Server
    1. Environment Variable: BEDROCK_SERVER_MANAGER_USERNAME
        1. Required. Plain text username for web UI and API login.
    2.  Environment Variable: BEDROCK_SERVER_MANAGER_PASSWORD
        1. Required. Hashed password for web UI and API login. Use the generate-password utility.
    3. Environment Variable: BEDROCK_SERVER_MANAGER_SECRET
        1. Strongly Recommended (Effectively Required for Web UI). A long, random, secret string. If not set, a temporary key is generated, and web UI sessions will not persist across restarts.
    4. Environment Variable: BEDROCK_SERVER_MANAGER_TOKEN
        1. Strongly Recommended. A long, random, secret string (different from _SECRET). If not set, a temporary key is generated, and JWT tokens used for API authentication will become invalid across restarts.
        2. JWT tokens expire every 4 weeks by default
    5. Set port in script_config.json : WEB_PORT
        1. Defaults to 11325
    6. Its recommended to run this behind a reverse proxy of your choice (NGINX, CADDY, etc etc)
    7. Uses Waitress WSGI server
    8. Customizable panorama
        1. Save any jpeg as panorama.jpeg in ./.config
    9. Mobile friendly experience
2. Added generate-password command
    1. Used to generate a hash to set as the BEDROCK_SERVER_MANAGER_PASSWORD Environment Variable
3. Added start-web-server command
    1. Command Arguments:
        1. -d | —debug : runs the server in the flask debug server
            1. Not recommend to use in production
        2. -m | -–mode : direct, detached . Sets which mode to run the server
            1. direct: Directly runs the web server in the foreground
            2. detached: Runs the web server in a separate background process
        3. -H | —host : Which host to listen to 
            1. Defaults to 127.0.0.1
4. Added stop-web-server command
    1. Stops a detached web server process 
5. Removed all related lingering configuration (linux only)
6. Refactored cli.py and handlers.py into cli/api modules
7. Added more detailed logging throughout code
8. Added more detailed docstrings/comments throughout code
9. Added html docs which covers the http apis, cli environment, and user guide
10. Removed redundant commands
11. Added WEB_PORT and TOKEN_EXPIRE_WEEKS to script_config.json
12. Added various documentation accessible in the web server
13. Added splash text to Main Menu in CLI
14. SEMI-BREAKING CHANGE: Changed data dir, you must add the bedrock-server-manager folder in the environment variable path if upgrading from older 3.0 versions

### 3.1.1
1. Fixed missing js files and images for web server
2. Added missing generate-password command
3. Fixed manage-script-config command

### 3.1.2
1. Fixed wrong longer in some js files
2. Fixed allowlist configuration on web
3. Fixed restoring backups on web
4. Fixed warning about jwt token for web sessions

### 3.1.3
1. Revised docs included with web server

### 3.1.4
1. Revised HTTP docs included with web server
    - Only includes basic api info, full detailed docs can be found in the docs folder of the repository
2. Added /api/servers endpoint
    - Returns a list of all servers and their status

### 3.2.0
1. Added export world to web GUI
    - Refactored export world endpoint
    - export-world on web and cli now export to the content folder
2. Added remove player from allowlist to web and cli
    - Added remove-allowlist-player command
3. Added a blacklist for commands such as stop or allowlist off
4. Added more splash text

### 3.2.1
1. Added /api/info route
2. Added /api/server/{server_name}/read_properties route
3. Stop server before export world

### 3.2.2
1. Fixed wrong module for read server properties route

### 3.2.3
1. Added /api/server/{server_name}/backups/list/{type} route
   - List all backups of one type for a server
2. Added /api/content/worlds route
   - List all worlds in the content folder
3. Added /api/content/addons route
   - List all addons in the content folder
4. Added /api/players/get route
   - List all players in the global players.json file
5. Added /api/players/add route
   - Add players to the global players.json file
6. Added /api/server/{server_name}/permissions_data
   - List all players in the server permissions file
7. File path for backups in http restore api must now be relative to the servers backup folder
8. Folder path for download prune in http prune api must now be relative to the download folder
9. /api/servers/{server_name}/ routes are now /api/server/{server_name}
   - Only the read properties route should be affected
10. Fixed passing host argument to web server

### 3.2.4

1. Fix restart-server command in CLI

### 3.2.5

1. Fix download server function to use updated minecraft site

### 3.3.0

#### MAJOR BREAKING CHANGES - READ FULL CHANGELOG BEFORE UPDATING

#### STOP SERVERS BEFORE UPDATING

Start/Stop methods have been revamped and require the servers be restarted with the new method. If you update before turning off your servers you may need to manually terminate the running process.

1.  Revamped all CLI modules: Anything using the CLI commands, such as systemd, external scripts, and task scheduler commands, need to be removed/recreated.
    - Please see the updated `CLI_COMMANDS.md` doc for an updated list of commands.
    - A few commands were removed and may or may not be replaced with a new command in the future.
    - The entire CLI has been revamped to use a more consistent modern structure.
    - Added `questionary` module for interactive CLI questions and prompts.
    - Added `click` module for CLI commands.
    - Vastly improved CLI user experience.
2.  Changed allowlist remove player route:
    - Now uses `/api/server/{server_name}/allowlist/remove`
3.  Revamped start server actions:
    - Windows:
      - Starting a server now creates a named pipe in the background, allowing commands to be sent to the server.
      - Takes an optional `-m/-–mode` variable:
        - `detached` mode will start a named pipe process in the background (similar to web start).
        - `direct` mode will start the named pipe process in the foreground.
    - Linux:
      - Start remains mostly the same, but the systemd command has also been merged into the base server start command.
      - Takes an optional `-m/–-mode` variable:
        - `detached` mode will try to start the server with `systemctl`. If the service file doesn't exist or is considered inactive, it falls back to `direct`.
        - `direct` mode will start the server directly with `screen`.
      - Systemd files must be recreated: As part of the start/stop revamp, you must recreate your systemd service files (Reconfigure autostart).
      - Removed systemd specific start/stop methods.
4.  Added `reset-world` action:
    - Deletes the server’s world folder.
    - Available in the CLI and web ui.
5.  Added command sending for various actions:
    - Send messages to running servers when shutting down, reloading the allowlist, or other configurations when changed.
6.  Application can now be run as a module:
    - Moved main `__init__.py` to `__main__.py`, allowing you to run the app with `python -m bedrock_server_manager <command>`.
    - This makes some logic easier, as only `sys.executable` is needed instead of manually finding the bedrock-server-manager(.exe) in various installation paths.
7.  Changed `list-backups` function:
    - `backup-type` changed from ’config’ to ‘allowlist’, ‘properties’, ‘permissions’.
8.  CLI and FILE log levels now use separate values:
    - Set ‘CLI_LOG_LEVEL’ and ‘FILE_LOG_LEVEL’ in `script_config.json`.
9.  Fixed `stop-web-server` bug:
    - The `stop-web-server` command was killing any process that happened to match the PID saved in the file. It now validates that it's the `bedrock-server-manager` process being killed.
10.  Removed web server content:
    - Removed the getting started guide and extras from the web server.
11.  Refactored some global core functions into a `BedrockServerManager` class:
    - Some functions that were migrated to this class include:
        - Scan for players
        - List content files
        - Start web server
        - List all servers
12.  Recreated the `BedrockServer` class in a more capable, feature-complete form.
13.  Refactored `core.downloader` into a `BedorckDownloader` class.
14.  Migrated task schedulers to their own classes, reducing redundant logic.
15.  Cleaned up various background code:
    - Removed the orignal `BedrockServer` class as it was underutilized.
    - Revamped `core.server_actions.delete_server_data`.
    - Splitting/renaming various files.
    - Removed redundant core backup/restore functions as the `api.backup` module can just call the config/world functions directly.

## 3.3.1

1. Fix panorama in web ui
2. Fix server process in web api
3. Fix task commands in web ui

## 3.4.0

1. BREAKING CHANGE: linux systemd service files have been changed
   - STOP SERVERS BEFORE UPDATING
   - You must reconfigure autoupdate to update your systemd service files
   - Note: Linux users, I apologize for all the times you have had to reconfigure your systemd service files, but this is the last time I promise!
     - This is due to the type being changed to `simple` instead of `forking`
     - BSM now directly manages the bedrock_server process, as a result screen has been removed as a dependency
     - You can remove screen from your system if you no longer need it with the command `sudo apt remove screen`
2. The bigest feature since the web server was added: PLUGINS!
   - Plugins are a new way to extend the functionality of BSM
   - Plugins can be installed by placing the .py file in the plugins folder (`./bedrock-server-manager/plugins` by default)
   - Plugins can be enabled/disabled with the `plugins.json` file located in the config directory (`./bedrock-server-manager/.config`)
     - Plugins are disabled by default when first installed, you must enable them in the `plugins.json` file
   - See the [docs/PLUGIN_DOCS.md](https://github.com/DMedina559/bedrock-server-manager/blob/main/docs/PLUGIN_DOC.md) file for more information on how to create and use plugins
     - See [src/bedrock_server_manager/plugins/default/](https://github.com/DMedina559/bedrock-server-manager/tree/main/src/bedrock_server_manager/plugins/default) for example plugins
   - Added plugin command see updated [CLI_COMMANDS.md](https://github.com/DMedina559/bedrock-server-manager/blob/main/docs/CLI_COMMANDS.md)
   - Added plugin management to the cli and web interface
     - Allows you to enable/disable plugins, and view plugin information
   - Default plugins included
     - Can be enabled/disabled in the `plugins.json` file
     - Can be overridden by creating a new plugin with the same name in the plugins folder
   - Custom event system
     - Plugins can send and receive custom events from other plugins and external sources from the web api/cli commands
3. BREAKING CHANGE: Removed /restore/all route
   - Moved to /restore/action similar to the backup route, all is now a type parameter in the json body
4. BREAKING CHANGE: Removed /world_name route
   - Use the get properties route instead
5. Changed /backups/list/ to /backup/list/
6. Optimized various html routes
   - HTML routes now only render and dont pull data from the backend, that logic is now handled by the javascript
   - As a result, the html routes are now much faster and more responsive
   - The servers table in the web ui now dynamically updates when a server is started or stopped instead of requiring a page refresh
7. Improved resource usage monitoring
   - Refactored function into a generic ResourceMonitor class allowing for more flexibility in the future (web server usage?)
8. Improved some filesystem functions by using thread.locking to prevent race conditions