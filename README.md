# Bedrock Server Manager

Bedrock Server Manager is a comprehensive python package designed for installing, managing, and maintaining Minecraft Bedrock Dedicated Servers with ease. The script is Linux and Windows compatable.

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


## Usage

### Download & Install The Package:

1. Go to the release section and download the latest release zip file to a folder on your device
2. Extract the `.zip` file on your device, you should see a `tar.gz` and `.whl` file
3. Open your command prompt and `cd` to the folder that contains the two extracted files
   - e.g. `cd /path/to/files`
4. Run the command `pip install .`
   - This will install the package and requirements (see requirements.txt)

### Setup The Configuration:

bedrock-server-manager will use the enviroment variable `BEDROCK_SERVER_MANAGER_DATA_DIR` for setting the default config/data location, if this variable does not exist it will default to `$HOME/bedrock-server-manager`

Follow your platforms documentation for setting Enviroment Variables

The script will create its data folders ( `./server`,`./backups`,`./.downloads` `./.config` `./.logs`  `./content/worlds`, and `./content/addons` ) in this location. This is where servers will be installed to and where the script will look when managing various server aspects. Most of these locations can be changed in the script_config.json

### Run the script:

```
bedrock-server-manager <command> [options]
```

#### Available commands:

<sub>When interacting with the script, server_name is the name of the servers folder (the name you chose durring the first step of instalation)</sub>

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
| **update-server-status-in-config**| Updates the server status in the server's config.json | `-s, --server`: Server name (required)                                                                       | All           |
| **get-world-name**   | Gets the world name from the server.properties     | `-s, --server`: Server name (required)                                                                       | All           |
| **check-internet**   | Checks for internet connectivity                    | None                                                                                                          | All           |
| **get-service-status-from-config**| Gets the server status from the server's config.json | `-s, --server`: Server name (required)                                                                       | All           |
| **cleanup**| Clean up project files (cache, logs)         | `-c, --cache`: Clean up __pycache__ directories <br> `-l, --logs`: Clean up log files | All           |


##### Linux-Specific Commands

| Command             | Description                                       | Arguments                                                                                                     |
|----------------------|---------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| **systemd-start**    | systemd start command (Linux only)                | `-s, --server`: Server name (required)                                                                       | Linux only    |
| **systemd-stop**     | systemd stop command (Linux only)                 | `-s, --server`: Server name (required)                                                                       | Linux only    |
| **check-service-exists**| Checks if a systemd service file exists (Linux only)| `-s, --server`: Server name (required)                                                                       | Linux only    |
| **enable-service**   | Enables a systemd service(Linux only)             | `-s, --server`: Server name (required)                                                                       | Linux only    |
| **disable-service**  | Disables a systemd service (Linux only)            | `-s, --server`: Server name (required)                                                                       | Linux only    |
| **send-command**     | Sends a command to the server (Linux only)        | `-s, --server`: Server name (required) <br> `-c, --command`: Command to send (required)                        | Linux only    |


###### Examples:

Open Main Menu:

```
bedrock-server-manager main
```

Send Command:
```
bedrock-server-manager send-command --server server_name --command "tell @a hello"
```

Update Server:

```
bedrock-server-manager update-server --server server_name
```


### Install Content:

With bedrock-server-manager you can easily import .mcworld and .mcpack files into your server. The script will look in `./content/worlds` and `./content/addons` respectively. 

For .mcworlds the script will scan the server.properties files for the `level-name` and extract the file to that folder.

For .mcpacks the script will extract them to a tmp folder and scan the manifest.json, looking for the pack type, name, version, and uuid. The script will then move the pack to it respective world folder (resource_packs, or behaviour_packs) with the name+verison used as the folder name, and the script will update the `world_behavior_packs.json` and `world_resource_packs.json` as needed with the packs uuid and version.

### Tested on these systems:
- Debian 12 (bookworm)
- Ubuntu 24.04
- Windows 11 24H2
- WSL2

### Platform Differences:
- Windows suppport has the following limitations such as:
 - No send-command support
 - No attach to console support
 - Doesn't auto restart if crashed