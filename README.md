# Bedrock Server Manager

Bedrock Server Manager is a comprehensive python package designed for installing, managing, and maintaining Minecraft Bedrock Dedicated Servers with ease, and is Linux/Windows compatable.

## Features

Install New Servers: Quickly set up a server with customizable options like version (LATEST, PREVIEW, or specific versions).

Update Existing Servers: Seamlessly download and update server files while preserving critical configuration files and backups.

Backup Management: Automatically backup worlds and configuration files, with pruning for older backups.

Server Configuration: Easily modify server properties, and allow-list interactively.

Auto-Update supported: Automatically update the server with a simple restart.

Command-Line Tools: Send game commands, start, stop, and restart servers directly from the command line.

Interactive Menu: Access a user-friendly interface to manage servers without manually typing commands.

Install/Update Content: Easily import .mcworld/.mcpack files into your server.

Automate Various Server Task: Quickly create cron task to automate task such as backup-server or restart-server (Linux only).

View Resource Usage: View how much CPU and RAM your server is using.

Web Server: Easily manage your Minecraft servers in your browser, even if you're on mobile!

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

| Command                          | Description                                                                            | Arguments                                                                                                                                                                                                                                                        | Platform      |
|----------------------------------|----------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|
| **main**                         | Open Bedrock Server Manager menu                                                       | None                                                                                                                                                                                                                                                             | All           |
| **list-servers**                 | List all servers and their statuses                                                    | `-l, --loop`: Continuously list servers (optional)                                                                                                                                                                                                               | All           |
| **get-status**                   | Get the status of a specific server (from config)                                      | `-s, --server`: Server name (required)                                                                                                                                                                                                                           | All           |
| **configure-allowlist**          | Configure the allowlist for a server                                                   | `-s, --server`: Server name (required)                                                                                                                                                                                                                           | All           |
| **configure-permissions**        | Configure permissions for a server                                                     | `-s, --server`: Server name (required)                                                                                                                                                                                                                           | All           |
| **configure-properties**         | Configure individual server.properties                                                 | `-s, --server`: Server name (required) <br> `-p, --property`: Name of the property to modify (required) <br> `-v, --value`: New value for the property (required)                                                                                                | All           |
| **install-server**               | Install a new server                                                                   | None                                                                                                                                                                                                                                                             | All           |
| **update-server**                | Update an existing server                                                              | `-s, --server`: Server name (required)                                                                                                                                                                                                                           | All           |
| **start-server**                 | Start a server                                                                         | `-s, --server`: Server Name (required)                                                                                                                                                                                                                           | All           |
| **stop-server**                  | Stop a server                                                                          | `-s, --server`: Server Name (required)                                                                                                                                                                                                                           | All           |
| **install-world**                | Install a world from a .mcworld file                                                   | `-s, --server`: Server name (required) <br> `-f, --file`: Path to the .mcworld file (optional)                                                                                                                                                                   | All           |
| **install-addon**                | Install an addon (.mcaddon or .mcpack)                                                 | `-s, --server`: Server name (required) <br> `-f, --file`: Path to the .mcaddon or .mcpack file (optional)                                                                                                                                                        | All           |
| **restart-server**               | Restart a server                                                                       | `-s, --server`: Server name (required)                                                                                                                                                                                                                           | All           |
| **delete-server**                | Delete a server                                                                        | `-s, --server`: Server name (required)                                                                                                                                                                                                                           | All           |
| **backup-server**                | Backup server files                                                                    | `-s, --server`: Server name (required) <br> `-t, --type`: Backup type (required) <br> `-f, --file`: Specific file to backup (optional, for config type) <br> `--no-stop`: Don't stop the server before backup (optional, flag)                                   | All           |
| **backup-all**                   | Restores all newest files (world and configuration files).                             | `-s, --server`: Server Name (required) <br> `--no-stop`: Don't stop the server before restore (optional, flag)                                                                                                                                                   | All           |
| **restore-server**               | Restore server files from backup                                                       | `-s, --server`: Server name (required) <br> `-f, --file`: Path to the backup file (required) <br> `-t, --type`: Restore type (required) <br> `--no-stop`: Don't stop the server before restore (optional, flag)                                                  | All           |
| **restore-all**                  | Restores all newest files (world and configuration files).                             | `-s, --server`: Server Name (required) <br> `--no-stop`: Don't stop the server before restore (optional, flag)                                                                                                                                                   | All           |
| **scan-players**                 | Scan server logs for player data                                                       | None                                                                                                                                                                                                                                                             | All           |
| **add-players**                  | Manually add player:xuid to players.json                                               | `-p, --players`: `<player1:xuid> <player2:xuid> ...` (required)                                                                                                                                                                                                  | All           |
| **monitor-usage**                | Monitor server resource usage                                                          | `-s, --server`: Server name (required)                                                                                                                                                                                                                           | All           |
| **prune-old-backups**            | Prunes old backups                                                                     | `-s, --server`: Server Name (required) <br> `-f, --file-name`: Specific file name to prune (optional) <br> `-k, --keep`: How many backups to keep (optional)                                                                                                     | All           |
| **prune-old-downloads**          | Prunes old downloads                                                                   | `-d, --download-dir`: Full path to folder containing downloads <br> `-k, --keep`: How many backups to keep (optional)                                                                                                                                            | All           |
| **manage-script-config**         | Manages the script's configuration file                                                | `-k, --key`: The configuration key to read or write. (required) <br> `-o, --operation`: read or write (required, choices: ["read", "write"]) <br> `-v, --value`: The value to write (optional, required for 'write')                                             | All           |
| **manage-server-config**         | Manages individual server configuration files                                          | `-s, --server`: Server Name (required) <br> `-k, --key`: The configuration key to read or write. (required) <br> `-o, --operation`: read or write (required, choices: ["read", "write"]) <br> `-v, --value`: The value to write (optional, required for 'write') | All           |
| **get-installed-version**        | Gets the installed version of a server                                                 | `-s, --server`: Server Name (required)                                                                                                                                                                                                                           | All           |
| **check-server-status**          | Checks the server status by reading server_output.txt                                  | `-s, --server`: Server Name (required)                                                                                                                                                                                                                           | All           |
| **get-world-name**               | Gets the world name from the server.properties                                         | `-s, --server`: Server name (required)                                                                                                                                                                                                                           | All           |
| **create-service**               | Enable/Disable Auto-Update, Reconfigures Systemd file on Linux                         | `-s, --server`: Server name (required)                                                                                                                                                                                                                           | All           |
| **is-server-running**            | Checks if server process is running                                                    | `-s, --server`: Server name (required)                                                                                                                                                                                                                           | All           |
| **send-command**                 | Sends a command to the server                                                          | `-s, --server`: Server name (required) <br> `-c, --command`: Command to send (required)                                                                                                                                                                          | All           |
| **export-world**                 | Exports world to backup dir                                                            | `-s, --server`: Server name (required)                                                                                                                                                                                                                           | All           |
| **validate-server**              | Checks if server dir and executable exist                                              |  `-s, --server`: Server name (required)                                                                                                                                                                                                                          | All           |
| **check-internet**               | Checks for internet connectivity                                                       | None                                                                                                                                                                                                                                                             | All           |
| **cleanup**                      | Clean up project files (cache, logs)                                                   | `-c, --cache`: Clean up __pycache__ directories <br> `-l, --logs`: Clean up log files                                                                                                                                                                            | All           |
| **start-webserver**              | Start the web management interface.                                                    | `-H <host>`: Host to bind.<br> `-d`, `--debug`: Use Flask debug server.<br> `-m {direct\|detached}`: Run mode.                                                                                                                                                   | All           |
| **stop-webserver**               | Stop the detached web server process.                                                  | *(None)*                                                                                                                                                                                                                                                         | All           |


##### Linux-Specific Commands

| Command                          | Description                                                                            | Arguments                                                                                                     |
|----------------------------------|----------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| **attach-console**               | Attaches to screen session for a running server (Linux only)                           | `-s, --server`: Server name (required)                                                                        | Linux only    |
| **enable-service**               | Enables a systemd service(Linux only)                                                  | `-s, --server`: Server name (required)                                                                        | Linux only    |
| **disable-service**              | Disables a systemd service (Linux only)                                                | `-s, --server`: Server name (required)                                                                        | Linux only    |
| **check-service-exists**         | Checks if a systemd service file exists (Linux only)                                   | `-s, --server`: Server name (required)                                                                        | Linux only    |


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

## Web Server:

Bedrock Server Manager 3.1.0 includes a Web server you can run to easily manage your bedrock servers in your web browser, and is also mobile friendly!

The web ui has full parity with the CLI. With the web server you can:

- Install New Server
- Configure various server config files such as allowlist and permissions
- Start/Stop/Restart Bedrock server
- Update/Delete Bedrock server
- Monitor resource usage
- Schedule cron/task
- Install world/addons
- Backup and Restore all or individual files/worlds

### Configure the Web Server:

#### Environment Variables:

To get start using the web server you must first set these environment variables:

- **BEDROCK_SERVER_MANAGER_USERNAME**: Required. Plain text username for web UI and API login. **The web server will not start if this is not set**

- **BEDROCK_SERVER_MANAGER_PASSWORD**: Required. Hashed password for web UI and API login. Use the generate-password utility. **The web server will not start if this is not set**

- **BEDROCK_SERVER_MANAGER_SECRET**:   Recommended. A long, random, secret string. If not set, a temporary key is generated, and web UI sessions will not persist across restarts, and will require reauthentication.

- **BEDROCK_SERVER_MANAGER_TOKEN**:    Recommended. A long, random, secret string (different from _SECRET). If not set, a temporary key is generated, and JWT tokens used for API authentication will become invalid across restarts. **JWT tokens expire every 4 weeks**

Follow your platform's documentation for setting Environment Variables

#### Generate Password Hash:

For the web server to start you must first set the BEDROCK_SERVER_MANAGER_PASSWORD environment variable

This must be set to the password hash and NOT the plain text password

Use the following command to generate a password:

```
bedrock-server-manager generate-password
```
Follow the on-screen prompt to hash your password

#### Hosts:

By Default Bedrock Server Manager will only listen to local host only interfaces 127.0.0.1 and [::1]

To change which host to listen to start the web server with the specified host

Example: specify local host only ipv4 and ipv6:

```
bedrock-server-manager start-web-server --host 127.0.0.1 "::1"
```

#### Port:

By default Bedrock Server Manager will use port `11325`. This can be change in script_config.json

```
bedrock-server-manager manage-script-config --key WEB_PORT --operation write --value 11325
```

## Disclaimers:

### Platform Differences:
- Windows suppport has the following limitations such as:
 - send-command requires seperate start method (no yet available)
 - No attach to console support
 - No service integration

### Tested on these systems:
- Debian 12 (bookworm)
- Ubuntu 24.04
- Windows 11 24H2
- WSL2