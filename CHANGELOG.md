
## Bedrock Server Manager:

### 1.0.0
1. Initial Release

### 1.0.1
1. Perform validation on server folder name and level name
2. Fixed getting the scripts current directory
3. Script no longer needs root permissions

### 1.0.2
1. Execute update-server command and systemd prestart command
2. Make linger command optional

### 1.0.3
1. Added update-script command
2. Ask if you want to install pre-request packages first
3. Shutdown server before update if running
4. Send messages to online players about checking for server updates, when its shutting down, and when its restarting
5. Wait 10 seconds before shutdown/restart to allow players time to react to shutdown/restart messages

### 1.1.0
1. Added option to import .mcworld files from ./content/worlds folder
2. Added option to import .mcpack files from ./content/addons folder
3. Stop server before backup
4. Use values from server.properties file when reconfiguring server properties
5. Cleaned up some repetitive code

### 1.1.1
1. Optimized $SCRIPTDIR variable

### 1.1.2
1. Check for internet before download to prevent server fail to start (pings example.com)
2. No longer exit when you check for updates with the latest version already installed
3. Call send_command directly throughout script
4. Removed duplicate logging when calling certain functions
5. Backup function now only handles start/stop server if not in update

### 1.1.3
1. Better handle send-command arguments
2. Use say instead of tell

### 1.1.4
1. Fixed json format for world addon files
2. Set r/w permissions for extracted worlds/addons
3. Ask to restart after installing addon

### 1.2.0
1. Added enable-server and disable-server commands
   - Enable or disable systemd autostart service
2. Added interactive cron scheduler
   - You can view add modify delete cron jobs for your servers to automatically run certain script commands such as update-server at scheduled times
3. Backup now makes .mcworld files instead of a .tar.gz file
   - Added zip as required package
   - Fixed backups not working
4. View resource usage for server
5. Standardized yes/no prompts
6. Use allowlist reload command when updating allowlist and server is running
7. Rearranged code blocks to a more logical order
   - Centralized/Validate server name before call function
8. Add version to server download file
9. Rearranged menus
   - Added Advanced Menu

### 1.2.1
1. Added option to enable/disable update on start to systemd flow
   - Added Reconfigure Systemd Service option
2. Fixed Resource Usage page

### 1.3.0
1. BREAKING CHANGE: Migrate ./bedrock_server_manager to ./servers
   - The script will try to auto migrate servers+systemd services after the user confirms
   - Its recommended to take a backup BEFORE updating the script
2. Moved backups out of server folder to ./backups
3. Moved server downloads out of server folder to ./.downloads
4. Added support for .mcaddon file import (import in bulk)

### 1.4.0
1. Added list-servers command 
    - List all servers, their status, and version
    - Also shows in the menus
2. Added scan-players command
    - Scans server_output.txt for players+xuid and saves  it to ./.config/players.json
    - Used to add players to permissions.json file
    - Added to cron scheduler
3. Added add-players command 
    - Manually adds player+xuid to ./.config/players.json
4. Save script output to ./.logs/log_{$timestamp}.log
    - Redirect to file instead of /dev/null when applicable
5. Refactored backups
    - You can now choose to backup all files, just export the world to a .mcworld file, or backup an individual config file.
    - Backup all executed when running backup-server command
5. Added Restore menu
    - You can now restore all most recent files, a specific world file, or specific config file
    - Restore all executed when running update-server command
6. Moved server configurations such as installed/target version to ./.config/$server_name/config.json
    - The script will try to migrate existing configs (server name, installed version, and target version) to the new file
7. Perform validation on server.properties entries
8. Split most of the bigger functions such as download_server into smaller more modular functions 
9. Added permissions configuration
    - You can choose players saved in ./config/players.json to add to a server permissions file
10. Don't download server if target version is already downloaded
11. Moved script default values to ./config/script_config.json
    - Edit this file to set your own servers directory, how many backups and downloads to keep
12. Moved systemd commands to script, reconfigure systemd configuration to update

### 1.4.1
1. Check for internet in update function

### 1.4.2
1. Removed writing to version.txt

### 2.0.0
1. Complete rewrite of script in python
2. Added Windows support
   - Windows support has a few limitations such as:
     - No send-command support
     - No attach to console support
     - Doesn't auto restart if crashed

#### Bash vs Python

The short lived Bedrock Server Manager Bash script is being discontinued and replaced with a new Python-based version. The Bash script was originally designed to support only Debian-based systems, which limited its usability across different operating systems. The bash script will continue to be available but will no longer receive updates.

The switch to python allows cross platform support, standardized processes, and less dependencies. The new script has full feature parity to the bash script

##### To switch to the new version, follow these steps:

- Replace the bash script with the new python script:
  - Follow install instructions above
  - Place the .py file in the same folder as the .sh file
  - Delete the old .sh file if wanted
- Run the script, open the advanced menu then Reconfigure Auto-Update

### 2.0.1

1. Better handle send-command

### 2.0.2

1. Revaluated error codes
2. Ensure write permissions before certain operations such as delete server

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
