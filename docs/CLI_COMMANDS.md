# Bedrock Server Manager CLI Commands

This document outlines the commands available in the Bedrock Server Manager CLI.

**General Usage:**

To use a command, type `bedrock-server-manager` followed by the command and any necessary options or arguments. For example:
`bedrock-server-manager server start --server my_server1`

If you run `bedrock-server-manager` without any command, the interactive menu system will launch.
Option choices like `[world|config|all]` or `[direct|detached]` are generally case-insensitive. Options expecting paths will be noted.

**Note on Server Names:**
In most commands, `SERVER_NAME` refers to the name of the server's folder (e.g., `my_server1`), which is also displayed in the `list-servers` command.

---

## Top-Level Commands

These commands are invoked directly after `bedrock-server-manager`.

| Command                          | Description                                                                  | Arguments & Options                                                                                                                                                                                                                            | Platform      |
|----------------------------------|------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|
| `install-addon`                  | Installs an addon to the specified Bedrock server.                           | `-s, --server SERVER_NAME` (required): Name of the target server.<br>`-f, --file ADDON_FILE_PATH` (Path): Full path to the addon file (.mcpack, .mcaddon). Skips interactive menu if provided.                                                 | All           |
| `generate-password`              | Generates a secure password hash for the web server.                         | *(None - Interactive)*                                                                                                                                                                                                                         | All           |
| `list-servers`                   | Lists all servers and their statuses.                                        | `--loop` (flag): Continuously list server statuses every 5 seconds.<br>`--server-name-filter SERVER_NAME`: Display status for only a specific server.                                                                                          | All           |
| `attach-console`                 | Attaches the terminal to a server's screen session.                          | `-s, --server SERVER_NAME` (required): Name of the server's screen session to attach to.                                                                                                                                                       | Linux only    |
| `cleanup`                        | Cleans up generated files such as logs and Python cache.                     | `-c, --cache` (flag): Clean up Python cache files (__pycache__).<br>`-l, --logs` (flag): Clean up application log files (*.log).<br>`--log-dir LOG_DIR_OVERRIDE` (Path): Override the log directory specified in settings.                     | All           |

---

## `allowlist` Commands

Group of commands for managing server access via `allowlist.json`. (`bedrock-server-manager allowlist [subcommand]`)

| Command  | Description                                                                                                | Arguments & Options                                                                                                                                                                                                                            | Platform |
|----------|------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|
| `add`    | Adds players to the allowlist. Launches interactive wizard if `--player` is omitted.                       | `-s, --server SERVER_NAME` (required): The name of the server.<br>`-p, --player PLAYER_GAMETAG` (multiple): Gamertag of the player to add. Use multiple times.<br>`--ignore-limit` (flag): Allow player(s) to join even if the server is full. | All      |
| `remove` | Removes one or more players from the allowlist.                                                            | `-s, --server SERVER_NAME` (required): The name of the server.<br>`-p, --player PLAYER_GAMETAG` (required, multiple): Gamertag of the player to remove. Use multiple times.                                                                    | All      |
| `list`   | Lists all players on a server's allowlist.                                                                 | `-s, --server SERVER_NAME` (required): The name of the server.                                                                                                                                                                                 | All      |

---

## `backup` Commands

Group of commands for server backup, restore, and management. (`bedrock-server-manager backup [subcommand]`)

| Command         | Description                                                                                                 | Arguments & Options                                                                                                                                                                                                                            | Platform |
|-----------------|-------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|
| `create`        | Backs up server data. Launches an interactive menu if `--type` is not specified.                            | `-s, --server SERVER_NAME` (required): Name of the target server.<br>`-t, --type [world\|config\|all]` (case-insensitive): Type of backup. Skips interactive menu.<br>`-f, --file FILE_TO_BACKUP`: File to backup (for type 'config').<br>`--no-stop` (flag): Attempt backup without stopping server. | All      |
| `restore`       | Restores server data from a backup. Launches an interactive menu if `--file` is not provided.               | `-s, --server SERVER_NAME` (required): Name of the target server.<br>`-f, --file BACKUP_FILE_PATH` (Path): Full path to the backup file to restore. Skips interactive menu.<br>`--no-stop` (flag): Attempt restore without stopping server.    | All      |
| `prune`         | Deletes old backups for a server, keeping the newest ones based on configuration.                           | `-s, --server SERVER_NAME` (required): Name of the server whose backups to prune.                                                                                                                                                              | All      |

---

## `permissions` Commands

Group of commands for managing player permission levels in `permissions.json`. (`bedrock-server-manager permissions [subcommand]`)

| Command | Description                                                                                                   | Arguments & Options                                                                                                                                                                                                                            | Platform |
|---------|---------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|
| `set`   | Sets a permission level for a player. Launches interactive wizard if `--player` and `--level` are omitted.    | `-s, --server SERVER_NAME` (required): The name of the target server.<br>`-p, --player PLAYER_NAME`: The gamertag of the player.<br>`-l, --level [visitor\|member\|operator]` (case-insensitive): The permission level.                        | All      |
| `list`  | Lists all configured player permissions for a server.                                                         | `-s, --server SERVER_NAME` (required): The name of the server.                                                                                                                                                                                 | All      |

---

## `player` Commands

Group of commands for managing the central player database. (`bedrock-server-manager player [subcommand]`)

| Command | Description                                                    | Arguments & Options                                                                                                     | Platform |
|---------|----------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|----------|
| `scan`  | Scans all server logs for players and updates the database.    | *(None - Interactive)*                                                                                                  | All      |
| `add`   | Manually adds one or more players to the player database.      | `-p, --player PLAYER_STRING` (required, multiple): Player in 'Gamertag:XUID' format. Use option multiple times.         | All      |

---

## `properties` Commands

Group of commands for viewing and modifying `server.properties`. (`bedrock-server-manager properties [subcommand]`)

| Command | Description                                                                                                   | Arguments & Options                                                                                                                                                                                                                            | Platform |
|---------|---------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|
| `get`   | Displays server properties. Shows specific property if `--prop` is used, otherwise lists all.                 | `-s, --server SERVER_NAME` (required): The name of the target server.<br>`-p, --prop PROPERTY_NAME`: Display a single property value.                                                                                                          | All      |
| `set`   | Sets one or more server properties. Launches interactive editor if `--prop` is omitted.                       | `-s, --server SERVER_NAME` (required): The name of the target server.<br>`-p, --prop KEY=VALUE` (multiple): A 'key=value' pair to set. Use multiple times.<br>`--no-restart` (flag): Do not restart server after changes.                      | All      |

---

## `server` Commands

Group of commands to manage the lifecycle of individual servers. (`bedrock-server-manager server [subcommand]`)

| Command        | Description                                                            | Arguments & Options                                                                                                                                                                                                                            | Platform |
|----------------|------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|
| `start`        | Starts a specific Bedrock server.                                      | `-s, --server SERVER_NAME` (required): Name of the server to start.<br>`-m, --mode [direct\|detached]` (default: detached, case-insensitive): Mode to start the server in.                                                                     | All      |
| `stop`         | Stops a specific Bedrock server.                                       | `-s, --server SERVER_NAME` (required): Name of the server to stop.                                                                                                                                                                             | All      |
| `restart`      | Restarts a specific Bedrock server.                                    | `-s, --server SERVER_NAME` (required): Name of the server to restart.                                                                                                                                                                          | All      |
| `install`      | Interactively installs and configures a new Bedrock server.            | *(None - Interactive)*                                                                                                                                                                                                                         | All      |
| `update`       | Checks for and applies updates to an existing server.                  | `-s, --server SERVER_NAME` (required): Name of the server to update.                                                                                                                                                                           | All      |
| `delete`       | Deletes all data for a server, including worlds and backups.           | `-s, --server SERVER_NAME` (required): Name of the server to delete.<br>`-y, --yes` (flag): Bypass the confirmation prompt.                                                                                                                    | All      |
| `send-command` | Sends a command to a running server (e.g., `say hello world`).         | `-s, --server SERVER_NAME` (required): Name of the target server.<br>`COMMAND_PARTS...` (required, multiple): The command and its arguments to send.                                                                                           | All      |
| `config`       | Sets a single key-value pair in a server's `server.properties`.        | `-s, --server SERVER_NAME` (required): Server to configure.<br>`-k, --key KEY` (required): Key to set (e.g., 'level-name').<br>`-v, --value VALUE` (required): Value for the key.                                                              | All      |


---

## `system` Commands

Group of commands for OS-level integrations and monitoring. (`bedrock-server-manager system [subcommand]`)

| Command             | Description                                                                  | Arguments & Options                                                                     | Platform        |
|---------------------|------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|-----------------|
| `configure-service` | Interactively configure OS-specific service settings (autoupdate, autostart).| `-s, --server SERVER_NAME` (required): Name of the server to configure.                 | Linux / Windows |
| `enable-service`    | Enables the systemd service to autostart.                                    | `-s, --server SERVER_NAME` (required): Name of the server.                              | Linux only      |
| `disable-service`   | Disables the systemd service from autostarting.                              | `-s, --server SERVER_NAME` (required): Name of the server.                              | Linux only      |
| `monitor`           | Continuously monitor CPU and memory usage of a server.                       | `-s, --server SERVER_NAME` (required): Name of the server to monitor.                   | All             |

---

## `schedule` Commands

Group of commands to manage scheduled tasks (cron/Windows Task Scheduler). (`bedrock-server-manager schedule [subcommand] -s SERVER_NAME`)
The `-s, --server SERVER_NAME` option is required for the `schedule` group itself. If no subcommand is given, an interactive menu for that server is launched.

| Command  | Description                                  | Arguments & Options       | Platform        |
|----------|----------------------------------------------|---------------------------|-----------------|
| `list`   | List all scheduled tasks for the server.     | *(Uses group server)*     | Linux / Windows |
| `add`    | Interactively add a new scheduled task.      | *(Uses group server)*     | Linux / Windows |
| `delete` | Interactively delete an existing scheduled task. | *(Uses group server)* | Linux / Windows |

---

## `web` Commands

Group of commands for managing the web management interface. (`bedrock-server-manager web [subcommand]`)

| Command | Description                                                    | Arguments & Options                                                                                                                                                                                                                            | Platform |
|---------|----------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|
| `start` | Starts the web management server.                              | `-H, --host HOST_ADDRESS` (multiple): Host address to bind to. Can be used multiple times.<br>`-d, --debug` (flag): Run in Flask's debug mode (NOT for production).<br>`-m, --mode [direct\|detached]` (default: direct, case-insensitive): Run mode. | All      |
| `stop`  | Stops the detached web server process.                         | *(None)*                                                                                                                                                                                                                                       | All      |

---

## `world` Commands

Group of commands for installing, exporting, and resetting server worlds. (`bedrock-server-manager world [subcommand]`)

| Command   | Description                                                                                               | Arguments & Options                                                                                                                                                                                                                            | Platform |
|-----------|-----------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|
| `install` | Installs a world from a .mcworld file. Replaces the current world. Lists available worlds if --file omitted. | `-s, --server SERVER_NAME` (required): Name of the target server.<br>`-f, --file WORLD_FILE_PATH` (Path): Path to the .mcworld file. Skips interactive menu.<br>`--no-stop` (flag): Attempt import without stopping the server.             | All      |
| `export`  | Exports the server's current world to a .mcworld file.                                                    | `-s, --server SERVER_NAME` (required): Name of the server whose world to export.                                                                                                                                                               | All      |
| `reset`   | Deletes the current world, allowing the server to generate a new one on next start.                       | `-s, --server SERVER_NAME` (required): Name of the server whose world to reset.<br>`-y, --yes` (flag): Bypass the confirmation prompt.                                                                                                         | All      |

---
