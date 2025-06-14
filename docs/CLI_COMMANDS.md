# Bedrock Server Manager CLI Commands

This document outlines the commands available in the Bedrock Server Manager CLI.

**General Usage:**

To use a command, type `bedrock-server-manager` followed by the command and any necessary options or arguments. For example:
`bedrock-server-manager server start --server my_server1`

If you run `bedrock-server-manager` without any command, the interactive menu system will launch.

**Note on Server Names:**
In most commands, `SERVER_NAME` refers to the name of the server's folder (e.g., `my_server1`), which is also displayed in the `list-servers` command.

---

## Top-Level Commands

These commands are invoked directly after `bedrock-server-manager`.

| Command                          | Description                                                                  | Arguments & Options                                                                                                                                                                                                                            | Platform      |
|----------------------------------|------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|
| `install-addon`                  | Installs an addon to the specified Bedrock server.                           | `-s, --server SERVER_NAME` (required): Name of the target server.<br>`-f, --file FILE_PATH`: Full path to the addon file (.mcpack, .mcaddon). Skips interactive menu if provided.                                                              | All           |
| `generate-password`              | Generates a secure password hash for the web server.                         | *(None)*                                                                                                                                                                                                                                       | All           |
| `install-server`                 | Interactively installs and configures a new Bedrock server.                  | *(None - Interactive)*                                                                                                                                                                                                                         | All           |
| `update-server`                  | Checks for and applies updates to an existing server.                        | `-s, --server SERVER_NAME` (required): Name of the server to update.                                                                                                                                                                           | All           |
| `configure-allowlist`            | Interactively configure the allowlist for a server.                          | `-s, --server SERVER_NAME` (required): Name of the server to configure.                                                                                                                                                                        | All           |
| `configure-permissions`          | Interactively set permission levels for known players.                       | `-s, --server SERVER_NAME` (required): Name of the server to configure.                                                                                                                                                                        | All           |
| `configure-properties`           | Interactively configure common server.properties settings.                   | `-s, --server SERVER_NAME` (required): Name of the server to configure.                                                                                                                                                                        | All           |
| `remove-allowlist-players`       | Removes one or more players from a server's allowlist.                       | `-s, --server SERVER_NAME` (required): Name of the server.<br>`PLAYERS...` (required): One or more player names to remove.                                                                                                                     | All           |
| `list-servers`                   | Lists all servers and their statuses.                                        | `-l, --loop`: Continuously list server statuses every 5 seconds.                                                                                                                                                                               | All           |
| `attach-console`                 | Attaches the terminal to a server's screen session.                          | `-s, --server SERVER_NAME` (required): Name of the server's screen session to attach to.                                                                                                                                                       | Linux only    |
| `cleanup`                        | Cleans up generated files such as logs and Python cache.             | `-c, --cache`: Clean up Python cache files (__pycache__).<br>`-l, --logs`: Clean up application log files (*.log).<br>`--log-dir LOG_DIR_OVERRIDE`: Override the log directory specified in settings.                                                  | All           |

---

## `backup` Commands

Group of commands for server backup, restore, and management. (`bedrock-server-manager backup [subcommand]`)

| Command         | Description                                                                                                 | Arguments & Options                                                                                                                                                                                                                            | Platform |
|-----------------|-------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|
| `create`        | Backs up server data. Launches an interactive menu if `--type` is not specified.                            | `-s, --server SERVER_NAME` (required): Name of the target server.<br>`-t, --type [world\|config\|all]`: Type of backup. Skips interactive menu.<br>`-f, --file FILE_TO_BACKUP`: File to backup (for type 'config').<br>`--no-stop`: Attempt backup without stopping server. | All      |
| `restore`       | Restores server data from a backup. Launches an interactive menu if `--file` is not provided.               | `-s, --server SERVER_NAME` (required): Name of the target server.<br>`-f, --file BACKUP_FILE`: Full path to the backup file to restore. Skips interactive menu.<br>`--no-stop`: Attempt restore without stopping server.                       | All      |
| `prune`         | Deletes old backups for a server, keeping the newest N.                                                     | `-s, --server SERVER_NAME` (required): Name of the server whose backups to prune.                                                                                                                                                              | All      |

---

## `player` Commands

Group of commands for managing the central player database. (`bedrock-server-manager player [subcommand]`)

| Command | Description                                                    | Arguments & Options                                                                                              | Platform |
|---------|----------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|----------|
| `scan`  | Scans all server logs for players and updates the database.    | *(None)*                                                                                                         | All      |
| `add`   | Manually adds one or more players to the player database.      | `-p, --player PLAYER_INFO` (required, multiple): Player in 'PlayerName:XUID' format. Use option multiple times.  | All      |

---

## `server` Commands

Group of commands to manage the lifecycle of individual servers. (`bedrock-server-manager server [subcommand]`)

| Command        | Description                                                            | Arguments & Options                                                                                                                                                                                                                            | Platform |
|----------------|------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|
| `start`        | Starts a specific Bedrock server.                                      | `-s, --server SERVER_NAME` (required): Name of the server to start.<br>`-m, --mode [direct\|detached]` (default: detached): Mode to start the server in.                                                                                       | All      |
| `stop`         | Stops a specific Bedrock server.                                       | `-s, --server SERVER_NAME` (required): Name of the server to stop.                                                                                                                                                                             | All      |
| `restart`      | Restarts a specific Bedrock server.                                    | `-s, --server SERVER_NAME` (required): Name of the server to restart.                                                                                                                                                                          | All      |
| `delete`       | Deletes all data for a server, including worlds and backups.           | `-s, --server SERVER_NAME` (required): Name of the server to delete.<br>`-y, --yes`: Bypass the confirmation prompt.                                                                                                                           | All      |
| `send-command` | Sends a command to a running server (e.g., `/say hello world`).        | `-s, --server SERVER_NAME` (required): Name of the target server.<br>`COMMAND...` (required): The command and its arguments to send.                                                                                                           | All      |

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

Group of commands to manage scheduled tasks (cron/Windows Task Scheduler). (`bedrock-server-manager schedule [subcommand] --server SERVER_NAME`)
The `--server SERVER_NAME` option is required for the `schedule` group itself. If no subcommand is given, an interactive menu for that server is launched.

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
| `start` | Starts the web management server.                              | `-H, --host HOST_ADDRESS` (multiple): Host address to bind to. Can be used multiple times.<br>`-d, --debug`: Run in Flask's debug mode (NOT for production).<br>`-m, --mode [direct\|detached]` (default: direct): Run mode.                   | All      |
| `stop`  | Stops the detached web server process (if implemented).        | *(None)*                                                                                                                                                                                                                                       | All      |

---

## `world` Commands

Group of commands for installing, exporting, and resetting server worlds. (`bedrock-server-manager world [subcommand]`)

| Command   | Description                                                                                               | Arguments & Options                                                                                                                                                                                                                            | Platform |
|-----------|-----------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|
| `install` | Installs a world from a .mcworld file. Replaces the current world. Lists available worlds if --file omitted. | `-s, --server SERVER_NAME` (required): Name of the target server.<br>`-f, --file WORLD_FILE_PATH`: Path to the .mcworld file. Skips interactive menu.<br>`--no-stop`: Attempt import without stopping the server.                           | All      |
| `export`  | Exports the server's current world to a .mcworld file.                                                    | `-s, --server SERVER_NAME` (required): Name of the server whose world to export.                                                                                                                                                               | All      |
| `reset`   | Deletes the current world, allowing the server to generate a new one on next start.                       | `-s, --server SERVER_NAME` (required): Name of the server whose world to reset.<br>`-y, --yes`: Bypass the confirmation prompt.                                                                                                                | All      |

---
