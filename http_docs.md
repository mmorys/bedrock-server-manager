# Bedrock Server Manager - HTTP API Documentation

This document outlines the available HTTP API endpoints for interacting with the Bedrock Server Manager.

#### Base URL:

All endpoint paths are relative to the base URL where the manager's web server is running. Replace `http://<your-manager-host>:<port>` with the actual address. The default port is `11325` (configurable via the `WEB_PORT` setting).

#### Authentication:

Most API endpoints require authentication. This is done by providing a JSON Web Token (JWT) obtained from the `/api/login` endpoint. Include the token in the `Authorization` header as a Bearer token:

```
Authorization: Bearer YOUR_JWT_TOKEN
```

The token expiration duration is configurable via the `TOKEN_EXPIRES_WEEKS` setting, defaulting to 4 weeks.

#### Content-Type:

For requests that include data in the body (POST, PUT), the `Content-Type` header should be set to `application/json`. Responses from the API will typically have a `Content-Type` of `application/json`.

#### Standard Responses:

*   **Success:** Typically returns HTTP status `200 OK`, `201 Created` with a JSON body like:
    ```json
    {
        "status": "success",
        "message": "Operation completed successfully.",
        "data_key": "optional_data"
    }
    ```
    *(Specific `data_key` names vary by endpoint)*

*   **Error:** Typically returns HTTP status `4xx` (Client Error) or `5xx` (Server Error) with a JSON body like:
    ```json
    {
        "status": "error",
        "message": "A description of the error.",
        "errors": { // Optional: Field-specific validation errors
            "field_name": "Specific error for this field."
        }
    }
    ```
    Common error codes:
    *   `400 Bad Request`: Invalid input, missing parameters, validation failed, invalid format (e.g., not JSON).
    *   `401 Unauthorized`: Authentication token missing or invalid (for JWT protected routes).
    *   `403 Forbidden`: Authenticated user lacks permission (or OS mismatch for platform-specific endpoints like scheduling).
    *   `404 Not Found`: Server, task, file, or endpoint not found.
    *   `500 Internal Server Error`: An unexpected error occurred on the server during processing (e.g., file operation failure, configuration issue).
    *   `501 Not Implemented`: Feature not supported on the current OS (e.g., sending commands on Windows).

---

## Authentication

### `POST` `/api/login` - API Login

Authenticates using username and password provided in the JSON body and returns a JWT access token upon success. Credentials must match the `BEDROCK_SERVER_MANAGER_USERNAME` and `BEDROCK_SERVER_MANAGER_PASSWORD` environment variables (password must be the hashed value).

#### Authentication:

None required for this endpoint.

#### Request Body (JSON):

```json
{
    "username": "your_web_ui_username",
    "password": "your_web_ui_password"
}
```

#### Success Response (200 OK):

```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Error Responses:

*   `400 Bad Request`: Missing or non-JSON body, missing username/password field.
*   `401 Unauthorized`: Invalid username or password.
*   `500 Internal Server Error`: Server configuration issue (env vars `BEDROCK_SERVER_MANAGER_USERNAME` or `BEDROCK_SERVER_MANAGER_PASSWORD` not set).

#### `curl` Example (Bash):

```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"username": "your_username", "password": "your_password"}' \
     http://<your-manager-host>:<port>/api/login
```

#### PowerShell Example:

```powershell
$body = @{ username = 'your_username'; password = 'your_password' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/login" -Body $body -ContentType 'application/json'
```

---

## Server Actions

### `POST` `/api/server/{server_name}/start` - Start Server

Starts the specified server instance.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "message": "Server '<server_name>' start initiated successfully."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `404 Not Found`: Server executable (`bedrock_server`) not found within the server directory.
*   `500 Internal Server Error`: Server start failed (e.g., process error, configuration issue like missing BASE_DIR).

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/start
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/start" -Headers $headers
```

### `POST` `/api/server/{server_name}/stop` - Stop Server

Stops the specified running server instance gracefully (sends 'stop' command).

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "message": "Server '<server_name>' stopped successfully or was already stopped."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Stop failed (e.g., server not running, command send failed, process interaction error, timeout, configuration issue).
*   `501 Not Implemented`: Sending commands not supported on the OS (relevant for stopping).

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/stop
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/stop" -Headers $headers
```

### `POST` `/api/server/{server_name}/restart` - Restart Server

Restarts the specified server instance. Sends an in-game warning first if running. If stopped, it will just start the server.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "message": "Server '<server_name>' restart completed successfully."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `404 Not Found`: Server executable missing (during start phase).
*   `500 Internal Server Error`: Stop or start phase failed (e.g., process error, timeout, configuration issue).
*   `501 Not Implemented`: Sending commands not supported on the OS (relevant for stop/warning phase).

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/restart
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/restart" -Headers $headers
```

### `POST` `/api/server/{server_name}/send_command` - Send Command

Sends a command to the specified running server instance.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body (JSON):
```json
{
    "command": "your server command here"
}
```

#### Success Response (200 OK):
```json
{"status": "success", "message": "Command '<command>' sent successfully."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body or empty `command` field, invalid server name.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `404 Not Found`: Server executable missing.
*   `500 Internal Server Error`: Server is not running, command sending failed (process interaction error), configuration issue.
*   `501 Not Implemented`: Sending commands is not supported on the current operating system (e.g., Windows).

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"command": "say Hello from API!"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/send_command
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ command = 'say Hello from API!' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/send_command" -Headers $headers -Body $body
```

### `POST` `/api/server/{server_name}/update` - Update Server

Checks for the latest Bedrock Dedicated Server version (based on server's configured target: LATEST or PREVIEW) and updates the specified server instance if a newer version is available.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{
    "status": "success",
    "updated": true, // boolean: true if an update was performed, false otherwise
    "new_version": "1.20.x.x", // string: version installed (if updated), null otherwise
    "message": "Server '<server_name>' updated to version x.x.x.x." // Example message
}
```
*(Message varies depending on whether an update was needed)*

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Update process failed (download error, extraction error, file operation error, configuration issue).

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/update
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/update" -Headers $headers
```

### `DELETE` `/api/server/{server_name}/delete` - Delete Server

Deletes the specified server instance's data, including installation files, configuration, and backups. **This action is irreversible.** The server process will be stopped if running.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server to delete.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "message": "Server '<server_name>' deleted successfully."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Deletion failed (directory removal error, configuration issue, error stopping server).

#### `curl` Example (Bash):
```bash
curl -X DELETE -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/delete
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Delete -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/delete" -Headers $headers
```

### `GET` `/api/server/{server_name}/status_info` - Get Server Status Info

Retrieves runtime status information for a specific server, including running state and basic resource usage (PID, CPU, Memory, Uptime) if the process is active.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body:
None.

#### Success Response (200 OK):

*   If Running:
    ```json
    {
        "status": "success",
        "process_info": {
            "pid": 12345,
            "name": "bedrock_server",
            "cpu_percent": 10.5,
            "memory_percent": 2.3,
            "memory_mb": 512.5,
            "uptime_seconds": 3600,
            "status": "running" // or sleeping, etc.
        },
        "message": "Retrieved process info for server '<server_name>'."
    }
    ```
*   If Not Running / Not Found:
    ```json
    {
        "status": "success",
        "process_info": null,
        "message": "Server '<server_name>' is not running."
    }
    ```

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Error retrieving process information (e.g., permission issue, psutil error, configuration error).

#### `curl` Example (Bash):
```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/status_info
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/status_info" -Headers $headers
```

---

## Server Information

### `GET` `/api/server/{server_name}/world_name` - Get World Name

Gets the configured world name (`level-name` from `server.properties`) for the specified server.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "world_name": "YourWorldName"}
```

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Failed to read `server.properties` file, configuration error.

#### `curl` Example (Bash):
```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/world_name
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/world_name" -Headers $headers
```

### `GET` `/api/server/{server_name}/running_status` - Get Running Status

Checks if the server process for the specified server is currently running.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "running": true}
```
or
```json
{"status": "success", "running": false}
```

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Error checking process status (e.g., permission issue, configuration error).

#### `curl` Example (Bash):
```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/running_status
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/running_status" -Headers $headers
```

### `GET` `/api/server/{server_name}/config_status` - Get Config Status

Gets the status string stored in the server's configuration file (`config/{server_name}.json`).

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "config_status": "Installed"}
```
*(Example status)*

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Failed to read configuration file, configuration error.

#### `curl` Example (Bash):
```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/config_status
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/config_status" -Headers $headers
```

### `GET` `/api/server/{server_name}/version` - Get Installed Version

Gets the installed version string stored in the server's configuration file (`config/{server_name}.json`).

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "installed_version": "1.20.x.x"}
```

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Failed to read configuration file, configuration error.

#### `curl` Example (Bash):
```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/version
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/version" -Headers $headers
```

### `GET` `/api/server/{server_name}/validate` - Validate Server Existence

Validates if the server directory and the main executable (`bedrock_server`) exist for the specified server name.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "message": "Server directory and executable exist."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `404 Not Found`: Server directory or executable does not exist. Response body:
    ```json
    {"status": "error", "message": "Server validation failed..."}
    ```
*   `500 Internal Server Error`: Configuration error (e.g., missing BASE_DIR).

#### `curl` Example (Bash):
```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/validate
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/validate" -Headers $headers
```

### `POST` `/api/server/{server_name}/export_world` - Export World

Exports the server's current world to a `.mcworld` file in the configured `BACKUP_DIR` (defined in settings). The filename will include the server name, world name, and a timestamp.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "message": "World 'YourWorldName' exported successfully to 'export/path/...'."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Export failed (e.g., world directory not found, zip creation error, file operation error, configuration issue).

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/export_world
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/export_world" -Headers $headers
```

---

## Global Actions

### `POST` `/api/players/scan` - Scan Player Logs

Triggers a scan of all server logs (`logs/` directory within each server folder under `BASE_DIR`) to update the central `players.json` file in the configuration directory with discovered player names and XUIDs.

#### Authentication:
Required (JWT).

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "message": "Scan complete. Found X players, added Y new players."}
```
*(Message details may vary)*

#### Error Responses:
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Scan failed (e.g., error reading logs, error writing `players.json`, configuration error).

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/players/scan
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/players/scan" -Headers $headers
```

### `POST` `/api/downloads/prune` - Prune Download Cache

Deletes older downloaded server archives (e.g., `.zip` files from updates) from a specified directory, keeping a defined number of the newest files.

#### Authentication:
Required (JWT).

#### Request Body (JSON):
```json
{
    "directory": "/path/to/your/download/cache", // Required: Absolute path to the directory to prune
    "keep": 5 // Optional: Integer number of files to keep (defaults to value in Bedrock Server Manager settings if omitted)
}
```

#### Success Response (200 OK):
```json
{"status": "success", "message": "Pruned X files from '/path/to/your/download/cache', kept Y files."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, missing `directory` field, invalid `keep` value (must be integer).
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Pruning failed (e.g., directory not found, file operation error).

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"directory": "/opt/bedrock-server-manager/.downloads/stable", "keep": 3}' \
     http://<your-manager-host>:<port>/api/downloads/prune
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ directory = 'C:\bedrock-server-manager\.downloads\stable'; keep = 3 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/downloads/prune" -Headers $headers -Body $body
```

### `POST` `/api/server/{server_name}/backups/prune` - Prune Server Backups

Deletes older backups (world `.mcworld` and configuration files) for a specific server from the configured `BACKUP_DIR`, keeping a specified number of the newest backups of each type (world/config).

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server whose backups to prune.

#### Request Body (JSON):
```json
{
    "keep": 10 // Optional: Integer number of backups to keep (defaults to BACKUP_KEEP setting if omitted)
}
```

#### Success Response (200 OK):
```json
{"status": "success", "message": "Pruned backups for server '<server_name>'. Deleted X world backups, Y config backups."}
```
*(Message details may vary)*

#### Error Responses:
*   `400 Bad Request`: Invalid server name format, invalid `keep` value (must be integer).
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Pruning failed (e.g., backup directory not found, file operation error, configuration error).

#### `curl` Example (Bash):
```bash
# Using default keep count
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/backups/prune

# Specifying keep count
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"keep": 5}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/backups/prune
```

#### PowerShell Example:
```powershell
# Using default keep count
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/backups/prune" -Headers $headers

# Specifying keep count
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ keep = 5 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/backups/prune" -Headers $headers -Body $body
```

---

## Backup & Restore

### `POST` `/api/server/{server_name}/backup/action` - Trigger Backup

Triggers a backup operation for the specified server. Backup files are stored in the configured `BACKUP_DIR`.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body (JSON):
*   For World Backup:
    ```json
    {"backup_type": "world"}
    ```
*   For Config Backup:
    ```json
    {"backup_type": "config", "file_to_backup": "server.properties"}
    ```
    (or other config file like `permissions.json`, `allowlist.json`)
*   For All (World + Configs):
    ```json
    {"backup_type": "all"}
    ```

#### Success Response (200 OK):
```json
{"status": "success", "message": "Backup type '<type>' for server '<server_name>' completed successfully."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, invalid `backup_type`, missing `file_to_backup` for config type, invalid server name, file not found for config backup.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Backup failed (e.g., world directory not found, zip error, file operation error, configuration error).

#### `curl` Example (Bash - World Backup):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"backup_type": "world"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/backup/action
```

#### PowerShell Example (Config Backup):
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ backup_type = 'config'; file_to_backup = 'server.properties' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/backup/action" -Headers $headers -Body $body
```

### `POST` `/api/server/{server_name}/restore/action` - Trigger Restore

Restores a server's world or a specific configuration file from a specified backup file. **Warning:** This overwrites current files. It's recommended to stop the server before restoring.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body (JSON):
```json
{
    "restore_type": "world", // or "config"
    "backup_file": "/full/path/to/backups/ServerName/backup_file.mcworld" // Required: Full path to the backup file (must be within configured BACKUP_DIR)
}
```

#### Success Response (200 OK):
```json
{"status": "success", "message": "Restoration from '<backup_filename>' (type: <type>) completed successfully."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, missing/invalid `restore_type` or `backup_file`, backup file path outside allowed `BACKUP_DIR`.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `404 Not Found`: Specified `backup_file` does not exist.
*   `500 Internal Server Error`: Restore failed (e.g., extraction error, file operation error, configuration error).

#### `curl` Example (Bash - World Restore):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"restore_type": "world", "backup_file": "/full/path/to/backups/MyServer/world_backup_xyz.mcworld"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/restore/action
```

#### PowerShell Example (Config Restore):
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ restore_type = 'config'; backup_file = 'C:\full\path\to\backups\MyServer\server.properties_backup_abc.zip' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/restore/action" -Headers $headers -Body $body
```

### `POST` `/api/server/{server_name}/restore/all` - Trigger Restore All

Restores the server's world AND configuration files (`server.properties`, `allowlist.json`, `permissions.json`) from their respective *latest* available backups found in the configured `BACKUP_DIR`. **Warning:** This overwrites current files. It's recommended to stop the server first.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The unique name of the server.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "message": "Restore All operation for server '<server_name>' completed successfully."}
```
*(May include details about which files were restored)*

#### Error Responses:
*   `400 Bad Request`: Invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Restore failed (e.g., no backups found, extraction error, file operation error, configuration error).

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/restore/all
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/restore/all" -Headers $headers
```

---

## Content Management (Worlds & Addons)

### `POST` `/api/server/{server_name}/world/install` - Install World

Installs a world from a `.mcworld` file into the specified server. The `.mcworld` file must already exist within the configured `content/worlds` directory. **Warning:** This replaces the existing world directory.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The name of the server to install the world to.

#### Request Body (JSON):
```json
{
    "filename": "MyCoolWorld.mcworld" // Required: Filename (relative path within content/worlds is okay, but just name is typical)
}
```

#### Success Response (200 OK):
```json
{"status": "success", "message": "World '<filename>' installed successfully for server '<server_name>'."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, missing/invalid `filename`, filename path traversal attempt.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `404 Not Found`: The specified world file (`.mcworld`) was not found in the `content/worlds` directory.
*   `500 Internal Server Error`: World import failed (e.g., extraction error, file operation error, configuration error).

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"filename": "MyDownloadedWorld.mcworld"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/world/install
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ filename = 'MyDownloadedWorld.mcworld' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/world/install" -Headers $headers -Body $body
```

### `POST` `/api/server/{server_name}/addon/install` - Install Addon

Installs an addon pack (`.mcaddon` or `.mcpack`) into the specified server. The addon file must already exist within the configured `content/addons` directory. Installs behavior packs and resource packs found within the file.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The name of the server to install the addon to.

#### Request Body (JSON):
```json
{
    "filename": "CoolBehaviorPack.mcpack" // Required: Filename (relative path within content/addons okay, just name typical)
}
```

#### Success Response (200 OK):
```json
{"status": "success", "message": "Addon '<filename>' installed successfully for server '<server_name>'."}
```
*(May list packs installed)*

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, missing/invalid `filename`, invalid addon type, filename path traversal attempt.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `404 Not Found`: The specified addon file (`.mcaddon` / `.mcpack`) was not found in the `content/addons` directory.
*   `500 Internal Server Error`: Addon import failed (e.g., extraction error, file operation error, configuration error).

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"filename": "AwesomeAddonCollection.mcaddon"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/addon/install
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ filename = 'AwesomeAddonCollection.mcaddon' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/addon/install" -Headers $headers -Body $body
```

---

## Server Installation & Configuration

### `POST` `/api/server/install` - Install New Server

Creates and installs a new Bedrock server instance. Downloads the specified version, sets up directories, and creates initial configuration files. Allows overwriting an existing server with the same name if `overwrite` is true.

#### Authentication:
Required (JWT).

#### Request Body (JSON):
```json
{
    "server_name": "UniqueServerName", // Required: String, no spaces or special chars except '-' and '_'
    "server_version": "LATEST", // Required: "LATEST", "PREVIEW", or specific version "1.20.x.x"
    "overwrite": false // Optional: Boolean, defaults to false. If true, deletes existing server data first.
}
```

#### Success Response (201 Created):
```json
{
    "status": "success",
    "message": "Server '<server_name>' installed successfully.",
    "next_step_url": "/server/<server_name>/configure_properties?new_install=true" // URL for UI to proceed
}
```

#### Success Response (200 OK - Confirmation Needed):
If server exists and `overwrite` is false.
```json
{
    "status": "confirm_needed",
    "message": "Server '<server_name>' already exists. Overwrite existing data and reinstall?",
    "server_name": "UniqueServerName",
    "server_version": "LATEST"
}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, missing/invalid `server_name` or `server_version`, invalid `overwrite` value, invalid server name format.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Installation failed (download error, extraction error, file operation error, configuration error, error deleting existing server during overwrite).

#### `curl` Example (Bash):
```bash
# Install new server
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"server_name": "MySurvivalServer", "server_version": "LATEST", "overwrite": false}' \
     http://<your-manager-host>:<port>/api/server/install

# Force overwrite existing server
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"server_name": "MySurvivalServer", "server_version": "LATEST", "overwrite": true}' \
     http://<your-manager-host>:<port>/api/server/install
```

#### PowerShell Example:
```powershell
# Install new server
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ server_name = 'MySurvivalServer'; server_version = 'LATEST'; overwrite = $false } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/install" -Headers $headers -Body $body

# Force overwrite existing server
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ server_name = 'MySurvivalServer'; server_version = 'LATEST'; overwrite = $true } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/install" -Headers $headers -Body $body
```

### `POST` `/api/server/{server_name}/properties` - Update Server Properties

Updates specific key-value pairs in the `server.properties` file for the given server. Only updates keys allowed by the backend whitelist and performs validation on values.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The name of the server whose properties to modify.

#### Request Body (JSON):
An object containing the properties to update.
```json
{
    "level-name": "Updated World Name",
    "max-players": "20",
    "difficulty": "hard"
    // Only include keys you want to change
}
```
*Allowed Keys (example list, check backend `server_install_config_routes.py` for current list):* `server-name`, `level-name`, `gamemode`, `difficulty`, `allow-cheats`, `max-players`, `server-port`, `server-portv6`, `enable-lan-visibility`, `allow-list`, `default-player-permission-level`, `view-distance`, `tick-distance`, `level-seed`, `online-mode`, `texturepack-required`.

#### Success Response (200 OK):
```json
{"status": "success", "message": "Server properties for '<server_name>' updated successfully."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, validation failed for one or more property values (response body will contain specific field errors).
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Failed to read or write `server.properties`, configuration error.

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"max-players": "12", "allow-list": "true"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/properties
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ 'max-players' = '12'; 'allow-list' = 'true' } | ConvertTo-Json # Note: quotes around keys with hyphens
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/properties" -Headers $headers -Body $body
```

### `GET` `/api/server/{server_name}/allowlist` - Get Allowlist

Retrieves the current list of players from the server's `allowlist.json` file.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The name of the server.

#### Request Body:
None.

#### Success Response (200 OK):
```json
{
    "status": "success",
    "existing_players": [
        {"ignoresPlayerLimit": false, "name": "PlayerOne"},
        {"ignoresPlayerLimit": false, "name": "PlayerTwo"}
    ],
    "message": "Successfully retrieved X players from allowlist."
}
```

#### Error Responses:
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Failed to read `allowlist.json`, configuration error.

#### `curl` Example (Bash):
```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/allowlist
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/allowlist" -Headers $headers
```

### `POST` `/api/server/{server_name}/allowlist` - Save/Replace Allowlist

Replaces the entire content of the server's `allowlist.json` file with the provided list of players. An empty list will clear the allowlist.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The name of the server.

#### Request Body (JSON):
```json
{
    "players": ["NewPlayer1", "AnotherPlayer"], // List of player names (strings)
    "ignoresPlayerLimit": false // Boolean: whether these players ignore max-players limit
}
```

#### Success Response (200 OK):
```json
{"status": "success", "message": "Allowlist saved successfully with X player(s)."}
```
or
```json
{"status": "success", "message": "Allowlist cleared successfully."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, `players` key missing or not a list, `ignoresPlayerLimit` not a boolean.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Failed to write `allowlist.json`, configuration error.

#### `curl` Example (Bash):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"players": ["AdminUser", "VIP_Player"], "ignoresPlayerLimit": false}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/allowlist
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ players = @('AdminUser', 'VIP_Player'); ignoresPlayerLimit = $false } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/allowlist" -Headers $headers -Body $body
```

### `PUT` `/api/server/{server_name}/permissions` - Update Player Permissions

Updates the permission levels for specified players in the server's `permissions.json` file. Takes a map of XUIDs to permission levels.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The name of the server.

#### Request Body (JSON):
```json
{
    "permissions": {
        "2535416409681153": "operator", // XUID string mapped to level string
        "2535457894355891": "member",
        "2535400000000000": "visitor"
    }
}
```
*Valid Levels:* `"visitor"`, `"member"`, `"operator"` (case-insensitive in request, stored lowercase).

#### Success Response (200 OK):
```json
{"status": "success", "message": "Permissions updated successfully for X player(s)..."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, `permissions` key missing or not an object, invalid permission level provided for one or more XUIDs (response body will contain specific field errors).
*   `401 Unauthorized`: Invalid/missing JWT.
*   `500 Internal Server Error`: Failed to read or write `permissions.json`, failure setting permission for one or more players (response body may contain details), configuration error.

#### `curl` Example (Bash):
```bash
curl -X PUT -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"permissions": {"2535416409681153": "operator", "2535457894355891": "member"}}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/permissions
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$permBody = @{
    permissions = @{
        '2535416409681153' = 'operator'
        '2535457894355891' = 'member'
    }
}
$bodyJson = $permBody | ConvertTo-Json -Depth 3
Invoke-RestMethod -Method Put -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/permissions" -Headers $headers -Body $bodyJson
```

### `POST` `/api/server/{server_name}/service` - Configure OS Service Settings

Configures OS-specific service settings for the server (e.g., autostart, autoupdate). Behavior depends on the host OS.

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The name of the server.

#### Request Body (JSON):
*   **Linux (systemd):**
    ```json
    {
        "autoupdate": true, // Boolean: Enable autoupdate timer/service
        "autostart": true   // Boolean: Enable service to start on boot
    }
    ```
    *(Setting these will create/overwrite the systemd service and timer files and enable/disable them)*
*   **Windows:**
    ```json
    {
        "autoupdate": true // Boolean: Set autoupdate flag in server's config JSON
    }
    ```

#### Success Response (200 OK):
```json
{"status": "success", "message": "Service settings for '<server_name>' updated successfully."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, incorrect boolean values for expected keys.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `403 Forbidden`: Service configuration not supported on the current OS.
*   `500 Internal Server Error`: Failed to create/modify service files (Linux), failed to update config JSON (Windows), error enabling/disabling services, command not found (e.g., `systemctl`), configuration error.

#### `curl` Example (Bash - Linux):
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"autoupdate": true, "autostart": true}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/service
```

#### PowerShell Example (Windows):
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ autoupdate = $true } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/service" -Headers $headers -Body $body
```

---

## Scheduled Tasks (OS Specific)

*Note: These endpoints interact with Linux `cron` or Windows Task Scheduler based on the host OS.*

### `POST` `/api/server/{server_name}/cron_scheduler/add` - Add Cron Job (Linux Only)

Adds a new cron job entry to the system's crontab for the user running Bedrock Server Manager. **Linux only.**

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): Server context (used for logging/auth), not directly part of the cron command typically.

#### Request Body (JSON):
```json
{
    "new_cron_job": "0 3 * * * /path/to/bedrock-server-manager backup-all --server MyServer" // Required: The full cron job line string
}
```

#### Success Response (201 Created):
```json
{"status": "success", "message": "Cron job added successfully."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, missing/empty `new_cron_job`.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `403 Forbidden`: Attempted on a non-Linux OS.
*   `500 Internal Server Error`: Failed to add job (e.g., `crontab` command error).

#### `curl` Example (Bash):
```bash
CRON_LINE="0 4 * * * /usr/local/bin/bedrock-server-manager restart-server --server MyProdServer"
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d "{\"new_cron_job\": \"$CRON_LINE\"}" \
     http://<your-manager-host>:<port>/api/server/MyProdServer/cron_scheduler/add
```

#### PowerShell Example:
```powershell
# Note: Linux-only endpoint
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$cronLine = "0 4 * * * /usr/local/bin/bedrock-server-manager restart-server --server MyProdServer"
$body = @{ new_cron_job = $cronLine } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/MyProdServer/cron_scheduler/add" -Headers $headers -Body $body
```

### `POST` `/api/server/{server_name}/cron_scheduler/modify` - Modify Cron Job (Linux Only)

Modifies an existing cron job by replacing the line matching `old_cron_job` with `new_cron_job`. **Linux only.**

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): Server context.

#### Request Body (JSON):
```json
{
    "old_cron_job": "0 3 * * * /path/to/bedrock-server-manager backup-all --server MyProdServer", // Required: Exact existing line
    "new_cron_job": "0 4 * * * /path/to/bedrock-server-manager backup-all --server MyProdServer"  // Required: The replacement line
}
```

#### Success Response (200 OK):
```json
{"status": "success", "message": "Cron job modified successfully."}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, missing/empty `old_cron_job` or `new_cron_job`.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `403 Forbidden`: Attempted on a non-Linux OS.
*   `404 Not Found`: The specified `old_cron_job` was not found in the crontab.
*   `500 Internal Server Error`: Failed to modify job (e.g., `crontab` command error).

#### `curl` Example (Bash):
```bash
OLD_CRON="0 3 * * * ..."
NEW_CRON="0 4 * * * ..."
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d "{\"old_cron_job\": \"$OLD_CRON\", \"new_cron_job\": \"$NEW_CRON\"}" \
     http://<your-manager-host>:<port>/api/server/MyServer/cron_scheduler/modify
```

#### PowerShell Example:
```powershell
# Note: Linux-only endpoint
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$oldCron = "0 3 * * * ..."
$newCron = "0 4 * * * ..."
$body = @{ old_cron_job = $oldCron; new_cron_job = $newCron } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/MyServer/cron_scheduler/modify" -Headers $headers -Body $body
```

### `DELETE` `/api/server/{server_name}/cron_scheduler/delete` - Delete Cron Job (Linux Only)

Deletes a specific cron job line from the crontab. **Linux only.**

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): Server context.

#### Query Parameters:
*   `**cron_string**` (*string*) (*Required*): The exact cron job line string to delete (URL encoded).

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "message": "Cron job '...' deleted successfully (if it existed)."}
```

#### Error Responses:
*   `400 Bad Request`: Missing or empty `cron_string` query parameter.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `403 Forbidden`: Attempted on a non-Linux OS.
*   `500 Internal Server Error`: Failed to delete job (e.g., `crontab` command error).

#### `curl` Example (Bash):
```bash
# URL Encode the cron string (example using Python)
CRON_STRING_URLENCODED=$(python3 -c 'import urllib.parse; print(urllib.parse.quote_plus("0 4 * * * /path/to/bedrock-server-manager backup-all --server MyProdServer"))')

curl -X DELETE -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     "http://<your-manager-host>:<port>/api/server/MyServer/cron_scheduler/delete?cron_string=${CRON_STRING_URLENCODED}"
```

#### PowerShell Example:
```powershell
# Note: Linux-only endpoint
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
$cronString = "0 4 * * * /path/to/bedrock-server-manager backup-all --server MyProdServer"
$encodedCronString = [System.Web.HttpUtility]::UrlEncode($cronString) # Requires .NET Framework access or similar encoding method
$uri = "http://<your-manager-host>:<port>/api/server/MyServer/cron_scheduler/delete?cron_string=$encodedCronString"
Invoke-RestMethod -Method Delete -Uri $uri -Headers $headers
```

### `POST` `/api/server/{server_name}/task_scheduler/add` - Add Windows Task (Windows Only)

Creates a new scheduled task in Windows Task Scheduler to run a Bedrock Server Manager command. Saves task XML config in the config dir. **Windows only.**

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The server context for the task command (e.g., `--server <server_name>`).

#### Request Body (JSON):
```json
{
    "command": "backup-all", // Required: Bedrock Server Manager command (e.g., "update-server", "start-server", "scan-players")
    "triggers": [ // Required: List containing one or more trigger objects
        {
            "type": "Daily", // Required: "Daily", "Weekly", "Monthly", "Once", "OnLogon", "OnStartup", "OnIdle"
            "start": "2024-01-15T03:00:00", // Required: ISO 8601 format start time
            "interval": 1, // Optional: Day/Week/Month interval (default 1)
            "days": ["Sunday", "Wednesday"] // Optional: For Weekly trigger (list of day names)
            // Other type-specific options may exist (e.g., monthDays for Monthly)
        }
    ]
}
```
*Valid Commands:* `update-server`, `backup-all`, `start-server`, `stop-server`, `restart-server`, `scan-players`.

#### Success Response (201 Created):
```json
{"status": "success", "message": "Task '<generated_task_name>' created successfully.", "created_task_name": "<generated_task_name>"}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, invalid `command`, invalid/missing `triggers` list, invalid trigger structure/type/start time.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `403 Forbidden`: Attempted on a non-Windows OS.
*   `500 Internal Server Error`: Failed to create task (e.g., `schtasks.exe` error, XML generation error, file operation error).

#### `curl` Example (Bash):
```bash
# Note: Windows-only endpoint
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"command": "backup-all", "triggers": [{"type": "Daily", "start": "2024-01-16T02:30:00", "interval": 1}]}' \
     http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/add
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$taskBody = @{
    command = 'backup-all'
    triggers = @(
        @{ type = 'Daily'; start = '2024-01-16T02:30:00'; interval = 1 }
    )
}
$bodyJson = $taskBody | ConvertTo-Json -Depth 3
# Expect error if Bedrock Server Manager host is not Windows
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/add" -Headers $headers -Body $bodyJson
```

### `POST` `/api/server/{server_name}/task_scheduler/details` - Get Windows Task Details (Windows Only)

Retrieves details (command, triggers) about a specific Windows scheduled task by parsing its saved XML configuration file. **Windows only.**

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): The server context (used to help locate the task XML).

#### Request Body (JSON):
```json
{
    "task_name": "bedrock_MyWinServer_backup-all_..." // Required: The full name of the task
}
```

#### Success Response (200 OK):
```json
{
    "status": "success",
    "task_details": {
         "base_command": "backup-all", // The core Bedrock Server Manager command
         "triggers": [ // List of parsed trigger objects
            { "type": "Daily", "start": "...", ... }
         ]
    },
    "message": "Successfully retrieved details for task '...'"
}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, missing/invalid `task_name`.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `403 Forbidden`: Attempted on a non-Windows OS.
*   `404 Not Found`: Task configuration XML file not found for the given name/server context.
*   `500 Internal Server Error`: Error parsing XML file, configuration error.

#### `curl` Example (Bash):
```bash
# Note: Windows-only endpoint
TASK_NAME="bedrock_MyWinServer_backup-all_20240115103000"
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d "{\"task_name\": \"$TASK_NAME\"}" \
     http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/details
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$taskName = "bedrock_MyWinServer_backup-all_20240115103000"
$body = @{ task_name = $taskName } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/details" -Headers $headers -Body $body
```

### `PUT` `/api/server/{server_name}/task_scheduler/task/{task_name}` - Modify Windows Task (Windows Only)

Modifies an existing Windows scheduled task by deleting the old task and creating a new one with the provided details. The new task will have a newly generated name. **Windows only.**

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): Server context.
*   `**task_name**` (*string*) (*Required*): The current, full name of the task to modify (URL encoded if needed).

#### Request Body (JSON):
Same structure as the "Add Windows Task" request body, defining the *new* command and triggers.
```json
{
    "command": "restart-server", // New Bedrock Server Manager command
    "triggers": [ { "type": "Weekly", "start": "...", "days": ["Saturday"] } ] // New triggers
}
```

#### Success Response (200 OK):
```json
{"status": "success", "message": "Task '<old_task_name>' modified successfully (new name: '<new_task_name>').", "new_task_name": "<new_task_name>"}
```

#### Error Responses:
*   `400 Bad Request`: Invalid/missing JSON body, invalid command/triggers, missing task name in URL.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `403 Forbidden`: Attempted on a non-Windows OS.
*   `500 Internal Server Error`: Failed to delete old task or create new task (`schtasks.exe` error, file error).

#### `curl` Example (Bash):
```bash
# Note: Windows-only endpoint
OLD_TASK_NAME="bedrock_MyWinServer_backup-all_..."
# URL Encode the task name if it contains special characters
ENCODED_OLD_TASK_NAME=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("'$OLD_TASK_NAME'"))')

curl -X PUT -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"command": "restart-server", "triggers": [{"type": "Weekly", "start": "2024-01-20T05:00:00", "days": ["Saturday"]}]}' \
     "http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/task/${ENCODED_OLD_TASK_NAME}"
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$oldTaskName = "bedrock_MyWinServer_backup-all_..."
$encodedOldTaskName = [uri]::EscapeDataString($oldTaskName) # PowerShell Core URI encoding

$newTaskBody = @{
    command = 'restart-server'
    triggers = @(
        @{ type = 'Weekly'; start = '2024-01-20T05:00:00'; days = @('Saturday') }
    )
}
$bodyJson = $newTaskBody | ConvertTo-Json -Depth 3
$uri = "http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/task/$encodedOldTaskName"
Invoke-RestMethod -Method Put -Uri $uri -Headers $headers -Body $bodyJson
```

### `DELETE` `/api/server/{server_name}/task_scheduler/task/{task_name}` - Delete Windows Task (Windows Only)

Deletes an existing Windows scheduled task and its associated XML configuration file from the config directory. **Windows only.**

#### Authentication:
Required (JWT).

#### Path Parameters:
*   `**server_name**` (*string*) (*Required*): Server context.
*   `**task_name**` (*string*) (*Required*): The full name of the task to delete (URL encoded if needed).

#### Request Body:
None.

#### Success Response (200 OK):
```json
{"status": "success", "message": "Task '<task_name>' deleted successfully."}
```

#### Error Responses:
*   `400 Bad Request`: Missing task name in URL.
*   `401 Unauthorized`: Invalid/missing JWT.
*   `403 Forbidden`: Attempted on a non-Windows OS.
*   `500 Internal Server Error`: Failed to delete task (`schtasks.exe` error), failed to delete XML file.

#### `curl` Example (Bash):
```bash
# Note: Windows-only endpoint
TASK_NAME="bedrock_MyWinServer_backup-all_..."
ENCODED_TASK_NAME=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("'$TASK_NAME'"))')
curl -X DELETE -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     "http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/task/${ENCODED_TASK_NAME}"
```

#### PowerShell Example:
```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
$taskName = "bedrock_MyWinServer_backup-all_..."
$encodedTaskName = [uri]::EscapeDataString($taskName)
$uri = "http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/task/$encodedTaskName"
Invoke-RestMethod -Method Delete -Uri $uri -Headers $headers
```

---