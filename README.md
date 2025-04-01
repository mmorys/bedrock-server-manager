# Bedrock Server Manager

Bedrock Server Manager is a comprehensive python package designed for installing, managing, and maintaining Minecraft Bedrock Dedicated Servers with ease, and is Linux/Windows compatable.

## Features

Install New Servers: Quickly set up a server with customizable options like version (LATEST, PREVIEW, or specific versions).

Update Existing Servers: Seamlessly download and update server files while preserving critical configuration files and backups.

Backup Management: Automatically backup worlds and configuration files, with pruning for older backups.

Server Configuration: Easily modify server properties, and allow-list interactively.

Auto-Update supported: Automatically update the server with a simple restart.

Command-Line Tools: Send game commands (Linux only), start, stop, and restart servers directly from the command line.

Interactive Menu: Access a user-friendly interface to manage servers without manually typing commands.

Install/Update Content: Easily import .mcworld/.mcpack files into your server.

Automate Various Server Task: Quickly create cron task to automate task such as backup-server or restart-server (Linux only).

View Resource Usage: View how much CPU and RAM your server is using.

## Prerequisites

This script requires `Python 3.10` or later, and you will need `pip` installed

On Linux, you'll also need:

*  screen
*  systemd


## Installation

### Install The Package:

1. Run the command 
```
pip install bedrock-server-manager
```

## Configuration

### Setup The Configuration:

bedrock-server-manager will use the Environment Variable `BEDROCK_SERVER_MANAGER_DATA_DIR` for setting the default config/data location, if this variable does not exist it will default to `$HOME/bedrock-server-manager`

Follow your platforms documentation for setting Enviroment Variables

The script will create its data folders in this location. This is where servers will be installed to and where the script will look when managing various server aspects. 

Certain variables can can be changed directly in the `./.config/script_config.json` or with the `manage-script-config` command

#### The following variables are configurable via json

* BASE_DIR: Directory where servers will be installed
* CONTENT_DIR: Directory where the app will look for addons/worlds
* DOWNLOAD_DIR: Directory where servers will download
* BACKUP_DIR: Directory where server backups will go
* LOG_DIR: Directory where app logs will be saved
* BACKUP_KEEP: How many backups to keep
* DOWNLOAD_KEEP: How many server downloads to keep
* LOGS_KEEP: How many logs to keep
* LOG_LEVEL: Level for logging

## Usage

### Run the script:

```
bedrock-server-manager <command> [options]
```

### Available commands:

<sub>When interacting with the script, server_name is the name of the servers folder (the name you chose durring the first step of instalation (also displayed in the Server Status table))</sub>

| Command             | Description                                       | Arguments                                                                                                     | Platform      |
|----------------------|---------------------------------------------------|---------------------------------------------------------------------------------------------------------------|---------------|
| **main**        | Open Bedrock Server Manager menu                  | None                                                                                                          | All           |
| **list-servers**     | List all servers and their statuses               | `-l, --loop`: Continuously list servers (optional)                                                          | All           |
| **get-status**       | Get the status of a specific server               | `-s, --server`: Server name (required)                                                                       | All           |
| **configure-allowlist** | Configure the allowlist for a server            | `-s, --server`: Server name (required)                                                                       | All           |
| **configure-permissions**| Configure permissions for a server             | `-s, --server`: Server name (required)                                                                       | All           |
| **configure-properties**| Configure individual server.properties           | `-s, --server`: Server name (required) <br> `-p, --property`: Name of the property to modify (required) <br> `-v, --value`: New value for the property (required) | All           |
| **install-server**   | Install a new server                              | None                                                                                                          | All           |
| **update-server**    | Update an existing server                         | `-s, --server`: Server name (required) <br> `-v, --version`: Server version to install (optional, default: LATEST) | All           |
| **start-server**     | Start a server                                    | `-s, --server`: Server Name (required)                                                                      | All           |
| **stop-server**      | Stop a server                                     | `-s, --server`: Server Name (required)                                                                      | All           |
| **install-world**    | Install a world from a .mcworld file             | `-s, --server`: Server name (required) <br> `-f, --file`: Path to the .mcworld file (optional)             | All           |
| **install-addon**    | Install an addon (.mcaddon or .mcpack)          | `-s, --server`: Server name (required) <br> `-f, --file`: Path to the .mcaddon or .mcpack file (optional) | All           |
| **restart-server**   | Restart a server                                  | `-s, --server`: Server name (required)                                                                       | All           |
| **delete-server**    | Delete a server                                   | `-s, --server`: Server name (required)                                                                       | All           |
| **backup-server**    | Backup server files                               | `-s, --server`: Server name (required) <br> `-t, --type`: Backup type (required) <br> `-f, --file`: Specific file to backup (optional, for config type) <br> `--no-stop`: Don't stop the server before backup (optional, flag) | All           |
| **backup-all**       | Restores all newest files (world and configuration files). | `-s, --server`: Server Name (required) <br> `--no-stop`: Don't stop the server before restore (optional, flag) | All           |
| **restore-server**   | Restore server files from backup                  | `-s, --server`: Server name (required) <br> `-f, --file`: Path to the backup file (required) <br> `-t, --type`: Restore type (required) <br> `--no-stop`: Don't stop the server before restore (optional, flag) | All           |
| **restore-all**      | Restores all newest files (world and configuration files). | `-s, --server`: Server Name (required) <br> `--no-stop`: Don't stop the server before restore (optional, flag) | All           |
| **create-service**   | Enable/Disable Auto-Update, Reconfigures Systemd file on Linux                         | `-s, --server`: Server name (required)                                                                       | All     |
| **scan-players**     | Scan server logs for player data                  | None                                                                                                          | All           |
| **monitor-usage**    | Monitor server resource usage                     | `-s, --server`: Server name (required)                                                                       | All           |
| **add-players**      | Manually add player:xuid to players.json        | `-p, --players`: `<player1:xuid> <player2:xuid> ...` (required)                                   | All           |
| **prune-old-backups**| Prunes old backups                                | `-s, --server`: Server Name (required) <br> `-f, --file-name`: Specific file name to prune (optional) <br> `-k, --keep`: How many backups to keep (optional) | All           |
| **manage-script-config**| Manages the script's configuration file         | `-k, --key`: The configuration key to read or write. (required) <br> `-o, --operation`: read or write (required, choices: ["read", "write"]) <br> `-v, --value`: The value to write (optional, required for 'write') | All           |
| **manage-server-config**| Manages individual server configuration files    | `-s, --server`: Server Name (required) <br> `-k, --key`: The configuration key to read or write. (required) <br> `-o, --operation`: read or write (required, choices: ["read", "write"]) <br> `-v, --value`: The value to write (optional, required for 'write') | All           |
| **get-installed-version**| Gets the installed version of a server          | `-s, --server`: Server Name (required)                                                                      | All           |
| **check-server-status**| Checks the server status by reading server_output.txt | `-s, --server`: Server Name (required)                                                                      | All           |
| **get-server-status-from-config**| Gets the server status from the server's config.json | `-s, --server`: Server name (required)                                                                       | All           |
| **get-world-name**   | Gets the world name from the server.properties     | `-s, --server`: Server name (required)                                                                       | All           |
| **check-internet**   | Checks for internet connectivity                    | None                                                                                                          | All           |
| **get-service-status-from-config**| Gets the server status from the server's config.json | `-s, --server`: Server name (required)                                                                       | All           |
| **cleanup**| Clean up project files (cache, logs)         | `-c, --cache`: Clean up __pycache__ directories <br> `-l, --logs`: Clean up log files | All           |


##### Linux-Specific Commands

| Command             | Description                                       | Arguments                                                                                                     |
|----------------------|---------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| **systemd-start**    | systemd start command (Linux only)                | `-s, --server`: Server name (required)                                                                       | Linux only    |
| **systemd-stop**     | systemd stop command (Linux only)                 | `-s, --server`: Server name (required)                                                                       | Linux only    |
| **send-command**     | Sends a command to the server (Linux only)        | `-s, --server`: Server name (required) <br> `-c, --command`: Command to send (required)                        | Linux only    |
| **enable-service**   | Enables a systemd service(Linux only)             | `-s, --server`: Server name (required)                                                                       | Linux only    |
| **disable-service**  | Disables a systemd service (Linux only)            | `-s, --server`: Server name (required)                                                                       | Linux only    |
| **check-service-exists**| Checks if a systemd service file exists (Linux only)| `-s, --server`: Server name (required)                                                                       | Linux only    |


###### Examples:

Open Main Menu:

```
bedrock-server-manager main
```

Send Command:
```
bedrock-server-manager send-command -s server_name -c "tell @a hello"
```

Update Server:

```
bedrock-server-manager update-server --server server_name
```

Manage Script Config:

```
bedrock-server-manager manage-script-config --key BACKUP_KEEP --operation write --value 5
```


## Install Content:

Easily import addons and worlds into your servers. The app will look in the configured `CONTENT_DIR` directories for addon files.

Place .mcworld files in `CONTENT_DIR/worlds` or .mcpack/.mcaddon files in `CONTENT_DIR/addons`

Use the interactive menu to choose which file to install or use the command:

```
bedrock-server-manager install-world --server server_name --file '/path/to/WORLD.mcworld'
```

```
bedrock-server-manager install-addon --server server_name --file '/path/to/ADDON.mcpack'
```

## Tested on these systems:
- Debian 12 (bookworm)
- Ubuntu 24.04
- Windows 11 24H2
- WSL2

## Platform Differences:
- Windows suppport has the following limitations such as:
 - send-command requires seperate start method (no yet available)
 - No attach to console support
 - Doesn't auto restart if crashed