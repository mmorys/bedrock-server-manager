- [Bedrock Server Manager - HTTP API Documentation](#bedrock-server-manager---http-api-documentation)
  - [Introduction](#introduction)
  - [Global Server Validation (Request Pre-Processing)](#global-server-validation-request-pre-processing)
  - [Authentication](#authentication)
    - [`POST /api/login` - API Login](#post-apilogin---api-login)
  - [Server Information](#server-information)
    - [`GET /api/servers` - Get All Servers List and Status](#get-apiservers---get-all-servers-list-and-status)
    - [`GET /api/server/{server_name}/world_name` - Get World Name](#get-apiserverserver_nameworld_name---get-world-name)
    - [`GET /api/server/{server_name}/running_status` - Get Running Status](#get-apiserverserver_namerunning_status---get-running-status)
    - [`GET /api/server/{server_name}/config_status` - Get Config Status](#get-apiserverserver_nameconfig_status---get-config-status)
    - [`GET /api/server/{server_name}/version` - Get Installed Version](#get-apiserverserver_nameversion---get-installed-version)
    - [`GET /api/server/{server_name}/validate` - Validate Server Existence](#get-apiserverserver_namevalidate---validate-server-existence)
    - [`GET /api/server/{server_name}/status_info` - Get Server Status Info](#get-apiserverserver_namestatus_info---get-server-status-info)
  - [Server Actions](#server-actions)
    - [`POST /api/server/{server_name}/start` - Start Server](#post-apiserverserver_namestart---start-server)
    - [`POST /api/server/{server_name}/stop` - Stop Server](#post-apiserverserver_namestop---stop-server)
    - [`POST /api/server/{server_name}/restart` - Restart Server](#post-apiserverserver_namerestart---restart-server)
    - [`POST /api/server/{server_name}/send_command` - Send Command](#post-apiserverserver_namesend_command---send-command)
    - [`POST /api/server/{server_name}/update` - Update Server](#post-apiserverserver_nameupdate---update-server)
    - [`DELETE /api/server/{server_name}/delete` - Delete Server](#delete-apiserverserver_namedelete---delete-server)
  - [Backup & Restore](#backup--restore)
    - [`POST /api/server/{server_name}/backups/prune` - Prune Server Backups](#post-apiserverserver_namebackupsprune---prune-server-backups)
    - [`POST /api/server/{server_name}/backup/action` - Trigger Backup](#post-apiserverserver_namebackupaction---trigger-backup)
    - [`POST /api/server/{server_name}/restore/action` - Trigger Restore](#post-apiserverserver_namerestoreaction---trigger-restore)
    - [`POST /api/server/{server_name}/restore/all` - Trigger Restore All](#post-apiserverserver_namerestoreall---trigger-restore-all)
  - [World & Addon Management](#world--addon-management)
    - [`POST /api/server/{server_name}/world/export` - Export World](#post-apiserverserver_nameworldexport---export-world)
    - [`POST /api/server/{server_name}/world/install` - Install World](#post-apiserverserver_nameworldinstall---install-world)
    - [`POST /api/server/{server_name}/addon/install` - Install Addon](#post-apiserverserver_nameaddoninstall---install-addon)
  - [Player Management](#player-management)
    - [`POST /api/players/scan` - Scan Player Logs](#post-apiplayersscan---scan-player-logs)
    - [`GET /api/server/{server_name}/allowlist` - Get Allowlist](#get-apiserverserver_nameallowlist---get-allowlist)
    - [`POST /api/server/{server_name}/allowlist/add` - Add Players to Allowlist](#post-apiserverserver_nameallowlistadd---add-players-to-allowlist)
    - [`DELETE /api/server/{server_name}/allowlist/player/{player_name}` - Remove Player from Allowlist](#delete-apiserverserver_nameallowlistplayerplayer_name---remove-player-from-allowlist)
    - [`PUT /api/server/{server_name}/permissions` - Update Player Permissions](#put-apiserverserver_namepermissions---update-player-permissions)
  - [Configuration](#configuration)
    - [`POST /api/server/{server_name}/properties` - Update Server Properties](#post-apiserverserver_nameproperties---update-server-properties)
    - [`POST /api/server/{server_name}/service` - Configure OS Service Settings](#post-apiserverserver_nameservice---configure-os-service-settings)
  - [Downloads](#downloads)
    - [`POST /api/downloads/prune` - Prune Download Cache](#post-apidownloadsprune---prune-download-cache)
  - [Server Installation](#server-installation)
    - [`POST /api/server/install` - Install New Server](#post-apiserverinstall---install-new-server)
  - [Task Scheduler](#task-scheduler)
    - [`POST /api/server/{server_name}/cron_scheduler/add` - Add Cron Job (Linux Only)](#post-apiserverserver_namecron_scheduleradd---add-cron-job-linux-only)
    - [`POST /api/server/{server_name}/cron_scheduler/modify` - Modify Cron Job (Linux Only)](#post-apiserverserver_namecron_schedulermodify---modify-cron-job-linux-only)
    - [`DELETE /api/server/{server_name}/cron_scheduler/delete` - Delete Cron Job (Linux Only)](#delete-apiserverserver_namecron_schedulerdelete---delete-cron-job-linux-only)
    - [`POST /api/server/{server_name}/task_scheduler/add` - Add Windows Task (Windows Only)](#post-apiserverserver_nametask_scheduleradd---add-windows-task-windows-only)
    - [`POST /api/server/{server_name}/task_scheduler/details` - Get Windows Task Details (Windows Only)](#post-apiserverserver_nametask_schedulerdetails---get-windows-task-details-windows-only)
    - [`PUT /api/server/{server_name}/task_scheduler/task/{task_name}` - Modify Windows Task (Windows Only)](#put-apiserverserver_nametask_schedulertasktask_name---modify-windows-task-windows-only)
    - [`DELETE /api/server/{server_name}/task_scheduler/task/{task_name}` - Delete Windows Task (Windows Only)](#delete-apiserverserver_nametask_schedulertasktask_name---delete-windows-task-windows-only)

# Bedrock Server Manager - HTTP API Documentation

This document outlines the available HTTP API endpoints for interacting with the Bedrock Server Manager.

## Introduction

### Base URL

All endpoint paths are relative to the base URL where the manager's web server is running. Replace `http://<your-manager-host>:<port>` with the actual address. The default port is `11325` (configurable via the `WEB_PORT` setting).

### Authentication

Most API endpoints require authentication. This is done by providing a JSON Web Token (JWT) obtained from the `/api/login` endpoint. Include the token in the `Authorization` header as a Bearer token:

```
Authorization: Bearer YOUR_JWT_TOKEN
```

The token expiration duration is configurable via the `TOKEN_EXPIRES_WEEKS` setting, defaulting to 4 weeks.

### Content-Type

For requests that include data in the body (POST, PUT), the `Content-Type` header should be set to `application/json`. Responses from the API will typically have a `Content-Type` of `application/json`.

### Standard Responses

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

## Global Server Validation (Request Pre-Processing)

To enhance robustness and provide immediate feedback, the application implements a global pre-request validation check. This check runs **before** the actual route handler for most requests involving a specific server instance.

### Mechanism

*   Uses Flask's `@app.before_request` decorator.
*   Runs on **every** request received by the application.

### Targeted URLs

*   The validation logic specifically targets URL paths that contain the pattern `/server/<server_name>/`, where `<server_name>` is a segment in the path.
    *   Examples: `/server/MyServer/status_info`, `/api/server/AnotherServer/stop`, `/server/MyServer/backups/prune`.

### Bypassed URLs

*   Certain paths are explicitly excluded from this validation check, primarily those related to server creation where the server doesn't exist yet. Currently bypassed paths start with:
    *   `/server/install`
    *   `/api/server/install`

### Validation Process

1.  If the request path matches the target pattern (and is not bypassed), the `<server_name>` segment is extracted.
2.  The internal function `validate_server_exist` (which checks for the existence of the server's directory and executable) is called with the extracted `server_name`.
3.  The result of `validate_server_exist` determines the outcome.

### Outcomes

*   **Validation Success:** If `validate_server_exist` confirms the server exists (`{"status": "success", ...}`), the `before_request` handler does nothing, and the request proceeds normally to its intended route handler.
*   **Validation Failure (Server Not Found):** If `validate_server_exist` indicates the server does not exist (`{"status": "error", "message": "..."}`):
    *   **For API Requests (Paths starting with `/api/`):** The request is **aborted**, and a **`404 Not Found`** response is immediately returned with a JSON body:
        ```json
        {
            "status": "error",
            "message": "Server '<server_name>' not found." // Or more specific message from validator
        }
        ```
    *   **For Web UI Requests (Other paths):** The user is **redirected (`302 Found`)** to the main dashboard page (`/`). A flash message containing the error (e.g., "Server '<server_name>' not found.") is typically displayed on the dashboard.
*   **Internal Validation Error:** If an unexpected error occurs *during* the validation check itself (e.g., configuration error preventing validation, unexpected exception):
    *   The request is **aborted**, and a **`500 Internal Server Error`** response is returned with a JSON body:
        ```json
        {
            "status": "error",
            "message": "Internal server error during server validation." // Or similar generic message
        }
        ```
*   **No Match / Bypassed:** If the request path does not match the target pattern or is explicitly bypassed, the validation is skipped, and the request proceeds normally.

### Implications for API Users

*   Requests to API endpoints under `/api/server/<server_name>/...` for a server name that does not actually exist will result in an immediate `404 Not Found` response from this pre-validation step, rather than potentially reaching the endpoint handler and returning a different error.
*   Ensure the `server_name` used in API calls corresponds to a valid, existing server instance.

---

## Authentication

### `POST /api/login` - API Login

Authenticates using username and password provided in the JSON body and returns a JWT access token upon success. Credentials must match the `BEDROCK_SERVER_MANAGER_USERNAME` and `BEDROCK_SERVER_MANAGER_PASSWORD` environment variables (password must be the hashed value).

This endpoint is exempt from CSRF protection.

#### Authentication

None required for this endpoint.

#### Request Body (`application/json`)

```json
{
    "username": "your_web_ui_username",
    "password": "your_web_ui_password"
}
```
*   **`username`** (*string*, required): The username configured via the `BEDROCK_SERVER_MANAGER_USERNAME` environment variable.
*   **`password`** (*string*, required): The plain-text password corresponding to the hashed password configured via the `BEDROCK_SERVER_MANAGER_PASSWORD` environment variable.

#### Success Response (`200 OK`)

Returns a JSON object containing the JWT access token.

```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is not valid JSON:
        ```json
        {
            "message": "Request must be JSON"
        }
        ```
    *   If the `username` or `password` field is missing in the JSON body:
        ```json
        {
            "message": "Missing username or password parameter"
        }
        ```
*   **`401 Unauthorized`**:
    *   If the provided username or password does not match the configured credentials:
        ```json
        {
            "message": "Bad username or password"
        }
        ```
*   **`500 Internal Server Error`**:
    *   If the server is missing the necessary configuration (environment variables `BEDROCK_SERVER_MANAGER_USERNAME` or `BEDROCK_SERVER_MANAGER_PASSWORD` are not set):
        ```json
        {
            "message": "Server configuration error prevents login."
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"username": "your_username", "password": "your_password"}' \
     http://<your-manager-host>:<port>/api/login
```

#### PowerShell Example

```powershell
$body = @{ username = 'your_username'; password = 'your_password' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/login" -Body $body -ContentType 'application/json'
```

---

## Application Information

### `GET /api/info` - Get System and Application Information

Retrieves basic system information, specifically the operating system type, and the current version of the Bedrock Server Manager application.

This does NOT require authentication 

#### Authentication

None.

#### Path Parameters

None.

#### Query Parameters

None.

#### Request Body

None.

#### Success Response (`200 OK`)

Returns the operating system type and application version.

*   **Standard Success:**
    ```json
    {
        "status": "success",
        "data": {
            "os_type": "Linux",
            "app_version": "3.2.1"
        }
    }
    ```
    *or for Windows:*
    ```json
    {
        "status": "success",
        "data": {
            "os_type": "Windows",
            "app_version": "3.2.1"
        }
    }
    ```

*   **`status`**: (*string*) Always "success" for a 200 response.
*   **`data`**: (*object*) Contains the system and application information.
    *   **`os_type`** (*string*): The operating system type as reported by the system (e.g., "Linux", "Windows", "Darwin"). Retrieved via `platform.system()`.
    *   **`app_version`** (*string*): The current version of the Bedrock Server Manager application (e.g., "1.2.3"). Retrieved from the package's `__version__` attribute.

#### Error Responses

*   **`500 Internal Server Error`**:
    *   If there's an issue retrieving the OS type or application version from the core layer (e.g., `__version__` attribute is missing). The message comes from `CoreSystemError` caught within `get_system_and_app_info`.
        ```json
        {
            "status": "error",
            "message": "Application version attribute (__version__) not found."
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Could not determine operating system type."
        }
        ```
    *   If an unexpected error occurs during the API layer's orchestration logic within `get_system_and_app_info`.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred while retrieving system information."
        }
        ```
    *   If an unexpected error occurs within the Flask route handler (`get_system_info_api`) itself.
        ```json
        {
            "status": "error",
            "message": "An unexpected server error occurred."
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/info
```

#### PowerShell Example

```powershell
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/info"
```
___

## Server Information

### `GET /api/servers` - Get All Servers List and Status

Retrieves a list of all detected Bedrock server instances managed by this application, along with their last known status and installed version as recorded in their respective configuration files.

This endpoint scans the configured base server directory for potential server instance folders and reads metadata from each server's configuration file.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

None.

#### Query Parameters

None.

#### Request Body

None.

#### Success Response (`200 OK`)

Returns a list of all detected servers and their details.

*   **Standard Success:**
    ```json
    {
        "status": "success",
        "servers": [
            {
                "name": "survival_world",
                "status": "STOPPED",
                "version": "1.20.40.01"
            },
            {
                "name": "creative_flat",
                "status": "RUNNING",
                "version": "1.20.50.02"
            },
            {
                "name": "unconfigured_server",
                "status": "UNKNOWN",
                "version": "UNKNOWN"
            }
            // ... more servers
        ]
    }
    ```
*   **Partial Success (Errors occurred reading some servers):**
    If there were issues reading the configuration for one or more servers, the endpoint still returns a `200 OK` with the successfully retrieved data, but includes an additional `message` field detailing the errors encountered.
    ```json
    {
        "status": "success",
        "servers": [
            {
                "name": "survival_world",
                "status": "STOPPED",
                "version": "1.20.40.01"
            }
            // Server 'corrupt_config_server' might be missing due to errors
        ],
        "message": "Completed with errors: Could not get status/version for server 'corrupt_config_server': Config file read error: [Errno 2] No such file or directory: '/path/to/configs/corrupt_config_server/config.json'"
    }
    ```

*   **`status`**: Always "success" for a 200 response.
*   **`servers`**: (*list*): A list of server objects.
    *   **`name`** (*string*): The unique name of the server instance (directory name).
    *   **`status`** (*string*): The last known status recorded in the server's config file (e.g., "RUNNING", "STOPPED", etc). Retrieved via `get_server_status_from_config`.
    *   **`version`** (*string*): The installed version recorded in the server's config file (e.g., "1.20.40.01", "UNKNOWN"). Retrieved via `get_installed_version`.
*   **`message`** (*string*, optional): Included only if errors occurred while processing individual server configurations during the scan. Provides details about the errors encountered.

#### Error Responses

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid (handled by `@auth_required` decorator).
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```
        *(Or a more specific message for invalid tokens)*

*   **`500 Internal Server Error`**:
    *   If there's a fundamental issue accessing the base server directory or configuration directory needed to scan for servers (e.g., path doesn't exist, permissions error). The message comes from `DirectoryError` or `FileOperationError` caught within `get_all_servers_status`.
        ```json
        {
            "status": "error",
            "message": "Error accessing directories: Base directory does not exist or is not a directory: /path/to/nonexistent/base_dir"
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Error accessing directories: Base configuration directory not set."
        }
        ```
    *   If an unexpected error occurs during the directory scan or processing within `get_all_servers_status`.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred: [Specific error message from the backend exception]"
        }
        ```
    *   If an unexpected error occurs within the Flask route handler *itself* (less likely, but possible).
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred retrieving the server list."
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/servers
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/servers" -Headers $headers
```

---

### `GET /api/server/{server_name}/world_name` - Get World Name

Gets the configured world name (`level-name` property) from the `server.properties` file for the specified server.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance.

#### Request Body

None.

#### Success Response (`200 OK`)

Returns the world name if found successfully.

```json
{
    "status": "success",
    "world_name": "Bedrock level"
}
```
*   **`status`**: Always "success".
*   **`world_name`**: The value of the `level-name` property from the server's `server.properties` file.

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty, contains disallowed characters - specific rules depend on your `InvalidServerNameError` implementation). The message comes directly from the exception.
        ```json
        {
            "status": "error",
            "message": "Server name cannot be empty."
        }
        ```
        *or similar validation message*

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid (handled by `@auth_required` decorator).
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```
        *(Or a more specific message for invalid tokens)*

*   **`500 Internal Server Error`**:
    *   If the server's `server.properties` file cannot be found or read, or the `level-name` property is missing within the file. The message comes directly from the `FileOperationError` raised by the core logic.
        ```json
        {
            "status": "error",
            "message": "Failed to get world name: File not found: /path/to/servers/MyServer/server.properties"
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Failed to get world name: Property 'level-name' not found in /path/to/servers/MyServer/server.properties"
        }
        ```
    *   If the base directory configuration is invalid or inaccessible.
        ```json
        {
            "status": "error",
            "message": "Failed to get world name: Base directory '/invalid/path' not found or accessible."
        }
        ```
    *   If an unexpected error occurs during processing.
        ```json
        {
            "status": "error",
            "message": "Unexpected error getting world name."
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/world_name
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/world_name" -Headers $headers
```

---

### `GET /api/server/{server_name}/running_status` - Get Running Status

Checks if the Bedrock server process for the specified server instance is currently running.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance.

#### Request Body

None.

#### Success Response (`200 OK`)

Returns the running status of the server.

```json
{
    "status": "success",
    "is_running": true
}
```
*or*
```json
{
    "status": "success",
    "is_running": false
}
```
*   **`status`**: Always "success".
*   **`is_running`**: Boolean indicating whether the server process associated with `server_name` was found (`true`) or not (`false`).

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty). The message comes directly from the `InvalidServerNameError`.
        ```json
        {
            "status": "error",
            "message": "Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid (handled by `@auth_required` decorator).
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```
        *(Or a more specific message for invalid tokens)*

*   **`500 Internal Server Error`**:
    *   If there's a configuration issue preventing the check (e.g., invalid `BASE_DIR`, error accessing server files needed for the check like a PID file if used). The message comes from the `FileOperationError`.
        ```json
        {
            "status": "error",
            "message": "Configuration error: Base directory '/invalid/path' not found or accessible."
        }
        ```
        *or similar configuration-related message*
    *   If an unexpected error occurs during the process check (e.g., permission issues interacting with the process list, psutil errors).
        ```json
        {
            "status": "error",
            "message": "Unexpected error checking running status."
        }
        ```
        *(Note: The underlying API function might generate a more specific message like "Unexpected error checking running status: <original error>", but the route handler catches generic exceptions and returns this standardized message.)*

#### `curl` Example (Bash)

```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/running_status
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/running_status" -Headers $headers
```

---

### `GET /api/server/{server_name}/config_status` - Get Config Status

Gets the status string stored within the server's specific configuration file (`./.config/{server_name}/{server_name}.json`). This status usually reflects the server's intended state or last known state managed by the application (e.g., "Installed", "Stopped", "Running", "Updating").

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance.

#### Request Body

None.

#### Success Response (`200 OK`)

Returns the status string found in the server's configuration file.

```json
{
    "status": "success",
    "config_status": "Installed"
}
```
*   **`status`**: Always "success".
*   **`config_status`**: The string value associated with the status field within the server's JSON configuration file.

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty). The message comes directly from the `InvalidServerNameError`.
        ```json
        {
            "status": "error",
            "message": "Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid (handled by `@auth_required` decorator).
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```
        *(Or a more specific message for invalid tokens)*

*   **`500 Internal Server Error`**:
    *   If there's an error accessing or reading the server's configuration directory or specific JSON file (e.g., permissions, file not found, invalid JSON format). The message typically comes from a `FileOperationError`.
        ```json
        {
            "status": "error",
            "message": "Error retrieving config status: File not found: /path/to/.config/MyServer/MyServer_config.json"
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Error retrieving config status: Permission denied accessing /path/to/.config/MyServer/MyServer_config.json"
        }
        ```
    *   If an unexpected error occurs during processing.
        ```json
        {
            "status": "error",
            "message": "Unexpected error getting config status."
        }
        ```
        *(Note: This is the message from the route handler's generic exception catch. The underlying API function might provide more detail in its own catch block.)*

#### `curl` Example (Bash)

```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/config_status
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/config_status" -Headers $headers
```

---

### `GET /api/server/{server_name}/version` - Get Installed Version

Gets the installed Bedrock server version string stored within the server's specific configuration file (`./.config/{server_name}/{server_name}_config.json`).

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance.

#### Request Body

None.

#### Success Response (`200 OK`)

Returns the installed version string found in the server's configuration file.

```json
{
    "status": "success",
    "installed_version": "1.20.81.01"
}
```
*   **`status`**: Always "success".
*   **`installed_version`**: The string value associated with the `installed_version` key within the server's JSON configuration file (e.g., `./.config/<server_name>/<server_name>_config.json`). If the version is not found or couldn't be determined during installation/update, this might return a default value like "UNKNOWN" (based on the `server_base.get_installed_version` implementation).

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty). The message comes directly from the `InvalidServerNameError` raised by the API function and caught by the route handler.
        ```json
        {
            "status": "error",
            "message": "Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid (handled by `@auth_required` decorator).
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```
        *(Or a more specific message for invalid tokens)*

*   **`500 Internal Server Error`**:
    *   If there's an error accessing or reading the server's configuration directory or specific JSON file (e.g., permissions, file not found, invalid JSON format). The message comes from the API function's error handling, typically wrapping a `FileOperationError`.
        ```json
        {
            "status": "error",
            "message": "Error retrieving installed version: File not found: /path/to/.config/MyServer/MyServer_config.json"
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Error retrieving installed version: Permission denied accessing /path/to/config/MyServer/MyServer_config.json"
        }
        ```
    *   If an unexpected error occurs during processing (either within the API function or the route handler itself).
        ```json
        {
            "status": "error",
            "message": "Unexpected error getting installed version."
        }
        ```
        *(Note: This specific message comes from the route handler's final catch block)*

#### `curl` Example (Bash)

```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/version
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/version" -Headers $headers
```

---

### `GET /api/server/{server_name}/validate` - Validate Server Existence

Validates if the server directory and the main executable (`bedrock_server`) exist for the specified server name within the configured `BASE_DIR`.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance to validate.

#### Request Body

None.

#### Success Response (`200 OK`)

Returned when both the server directory and the `bedrock_server` executable are found within that directory.

```json
{
    "status": "success",
    "message": "Server '<server_name>' exists and is valid."
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty). The message comes from the `MissingArgumentError` (or potentially `InvalidServerNameError`) raised by the API function and caught by the route handler.
        ```json
        {
            "status": "error",
            "message": "Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid (handled by `@auth_required` decorator).
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```
        *(Or a more specific message for invalid tokens)*

*   **`404 Not Found`**:
    *   Returned specifically when the validation *fails* because either the server's directory or the `bedrock_server` executable within it does not exist. The message comes from the `ServerNotFoundError` raised by the core logic and returned by the API function.
        ```json
        {
            "status": "error",
            "message": "Server directory '/path/to/servers/MyServer' not found."
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Server executable '/path/to/servers/MyServer/bedrock_server' not found."
        }
        ```
        *(Specific message depends on the underlying `ServerNotFoundError`)*

*   **`500 Internal Server Error`**:
    *   If there is a configuration issue preventing the validation check (e.g., `BASE_DIR` is not configured correctly or inaccessible). The message comes from a `FileOperationError`.
        ```json
        {
            "status": "error",
            "message": "Configuration error: Base directory '/invalid/path' not found or accessible."
        }
        ```
    *   If an unexpected error occurs during the validation process.
        ```json
        {
            "status": "error",
            "message": "Unexpected error validating server."
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/validate
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/validate" -Headers $headers
```

---

### `GET /api/server/{server_name}/status_info` - Get Server Status Info

Retrieves runtime status information for a specific server process, including running state and basic resource usage (PID, CPU, Memory, Uptime) if the process is active and accessible.

*Note on CPU Usage:* CPU percentage is calculated based on the change in CPU time since the last request to this endpoint for *any* server. The first request after the manager starts or after a period of inactivity will report 0.0% CPU. Subsequent calls provide a more accurate reading. Accuracy might be limited on Linux when using `screen`.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance.

#### Request Body

None.

#### Success Response (`200 OK`)

Returned regardless of whether the server is running or not, as long as the request itself is valid and no internal errors occur during the check.

*   **If Server Process is Found:**
    ```json
    {
        "status": "success",
        "process_info": {
            "pid": 12345,
            "cpu_percent": 10.5,
            "memory_mb": 512.5,
            "uptime": "1:00:00"
        }
    }
    ```
    *   `status`: "success"
    *   `process_info` (*object*): Contains details about the running process:
        *   `pid` (*integer*): Process ID of the `bedrock_server` process.
        *   `cpu_percent` (*float*): Approximate CPU utilization percentage (delta calculation, see note above).
        *   `memory_mb` (*float*): Resident Set Size (RSS) memory usage in Megabytes.
        *   `uptime` (*string*): Process uptime formatted as H:MM:SS or similar (from `timedelta`).

*   **If Server Process is Not Found / Not Running:**
    ```json
    {
        "status": "success",
        "process_info": null,
        "message": "Server '<server_name>' is not running."
    }
    ```
    *   `status`: "success"
    *   `process_info`: `null`
    *   `message`: Indicates the server process was not found.

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty).
        ```json
        {
            "status": "error",
            "message": "Invalid input: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` are missing or invalid (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Server configuration error: BASE_DIR setting is missing or empty in configuration."
        }
        ```
    *   If the `psutil` library is required but not installed (`ResourceMonitorError`).
        ```json
        {
            "status": "error",
            "message": "Error getting process info: 'psutil' is required for process monitoring."
        }
        ```
    *   If there's an error retrieving process details using `psutil` (e.g., permission denied accessing process info, unexpected OS error) (`ResourceMonitorError`).
        ```json
        {
            "status": "error",
            "message": "Error getting process info: Error getting process details for '<server_name>': ..."
        }
        ```
    *   If an unexpected error occurs during the status retrieval process.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred: <original error message>"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/status_info
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/status_info" -Headers $headers
```

---

## Server Actions

### `POST /api/server/{server_name}/start` - Start Server

Starts the specified Bedrock server instance process. Uses systemd (with screen fallback) on Linux or direct process creation on Windows. Waits for confirmation that the server process is running.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance to start.

#### Request Body

None.

#### Success Response (`200 OK`)

Returned when the server process is successfully initiated and confirmed to be running within the timeout period.

```json
{
    "status": "success",
    "message": "Server '<server_name>' started successfully."
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty).
        ```json
        {
            "status": "error",
            "message": "Invalid input: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`404 Not Found`**:
    *   If the server's executable (`bedrock_server` or `bedrock_server.exe`) is not found within the server's directory (`ServerNotFoundError`).
        ```json
        {
            "status": "error",
            "message": "Server not found: Server executable 'bedrock_server.exe' not found in C:\\path\\to\\servers\\MyServer"
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` are missing or invalid (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Server configuration error: BASE_DIR setting is missing or empty in configuration."
        }
        ```
    *   If the server is already running (`ServerStartError` from core logic, returned as error status by API layer).
        ```json
        {
            "status": "error",
            "message": "Failed to start server '<server_name>': Server '<server_name>' is already running."
        }
        ```
    *   If the start process fails due to OS-specific issues (e.g., unsupported OS, systemd/screen failure, Windows process creation failure) (`ServerStartError`).
        ```json
        {
            "status": "error",
            "message": "Failed to start server '<server_name>': Unsupported operating system: Darwin"
        }
        ```
         *or*
        ```json
        {
            "status": "error",
            "message": "Failed to start server '<server_name>': Failed to start server executable 'C:\\path\\to\\bedrock_server.exe': [WinError 5] Access is denied"
        }
        ```
        *or (Linux screen)*
         ```json
        {
            "status": "error",
            "message": "Failed to start server '<server_name>': Failed to start server '<server_name>' using screen. Error: Must be connected to a terminal."
        }
        ```
    *   If required commands like `systemctl` or `screen` are not found on Linux (`CommandNotFoundError`).
        ```json
        {
            "status": "error",
            "message": "Failed to start server '<server_name>': Command 'screen' not found in system PATH."
        }
        ```
    *   If the server process starts but fails to confirm running status within the configured timeout (`ServerStartError`).
        ```json
        {
            "status": "error",
            "message": "Failed to start server '<server_name>': Server '<server_name>' failed to start within the timeout."
        }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred: <original error message>"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/start
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/start" -Headers $headers
```

---

### `POST /api/server/{server_name}/stop` - Stop Server

Stops the specified running Bedrock server instance. Attempts a graceful shutdown by sending the 'stop' command (Linux only, via screen or systemd service) or terminates the process directly (Windows). Waits for the process to terminate within a configured timeout period.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance to stop.

#### Request Body

None.

#### Success Response (`200 OK`)

Returned if the server process stops successfully within the timeout period, or if the server was already stopped when the request was made.

```json
{
    "status": "success",
    "message": "Server '<server_name>' stopped successfully."
}
```
*or*
```json
{
    "status": "success",
    "message": "Server '<server_name>' was already stopped."
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty).
        ```json
        {
            "status": "error",
            "message": "Invalid input: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` are missing or invalid (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Server configuration error: BASE_DIR setting is missing or empty in configuration."
        }
        ```
    *   If sending the 'stop' command fails (e.g., `screen` interaction error, process communication issue on Linux) (`SendCommandError`).
        ```json
        {
            "status": "error",
            "message": "Failed to stop server '<server_name>': Error sending command: Failed to find screen session 'bedrock-<server_name>' to send command to."
        }
        ```
    *   If the server process is found, but the corresponding executable file (`bedrock_server`/`.exe`) is missing, preventing certain stop methods (`ServerNotFoundError`).
        ```json
        {
            "status": "error",
            "message": "Server '<server_name>' process found but executable missing. Stop failed."
        }
        ```
    *   If the server fails to stop within the configured timeout period (`ServerStopError`).
        ```json
        {
            "status": "error",
            "message": "Failed to stop server '<server_name>': Server '<server_name>' failed to stop within the timeout. Manual intervention may be required."
        }
        ```
    *   If the underlying stop mechanism fails (e.g., `systemctl stop` error, Windows process termination error) (`ServerStopError`).
        ```json
        {
            "status": "error",
            "message": "Failed to stop server '<server_name>': Stopping via systemctl failed (maybe service wasn't running under systemd?): ..."
        }
        ```
         *or (Windows)*
         ```json
        {
            "status": "error",
            "message": "Failed to stop server '<server_name>': Unexpected error stopping server '<server_name>': ..."
        }
         ```
    *   If required commands like `systemctl` or `screen` are not found on Linux (`CommandNotFoundError`).
         ```json
        {
            "status": "error",
            "message": "Failed to stop server '<server_name>': Command 'screen' not found in system PATH."
        }
         ```
    *   If an unexpected error occurs during the process.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred: <original error message>"
        }
        ```
*   **`501 Not Implemented`**:
    *   If stopping the server (specifically sending commands for graceful shutdown) is attempted on an unsupported operating system. *(Note: Direct process termination might still work on some OSes like Windows, but sending the 'stop' command is typically Linux-only in this context).*
        ```json
        {
            "status": "error",
            "message": "Failed to stop server '<server_name>': Unsupported operating system: Darwin"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/stop
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/stop" -Headers $headers
```

---

### `POST /api/server/{server_name}/restart` - Restart Server

Restarts the specified Bedrock server instance.
If the server is currently running, it first attempts to send a "Restarting..." warning message to the server (Linux only, best effort), waits briefly, attempts a graceful stop, waits briefly again, and then starts the server. If the server is already stopped, it simply attempts to start it.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance to restart.

#### Request Body

None.

#### Success Response (`200 OK`)

Returned when the restart sequence (stop, if needed, then start) completes successfully.

```json
{
    "status": "success",
    "message": "Server '<server_name>' restarted successfully."
}
```
*or if the server was initially stopped:*
```json
{
    "status": "success",
    "message": "Server '<server_name>' was not running and was started."
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty).
        ```json
        {
            "status": "error",
            "message": "Invalid input: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` are missing or invalid (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Server configuration error: BASE_DIR setting is missing or empty in configuration."
        }
        ```
    *   If the **stop phase** fails (when restarting a running server). This could be due to command sending errors, timeout, OS-specific errors, or the server being in an unexpected state. (`ServerStopError`, `SendCommandError`, `CommandNotFoundError`).
        ```json
        {
            "status": "error",
            "message": "Restart failed during stop phase: Failed to stop server '<server_name>': Server '<server_name>' failed to stop within the timeout. Manual intervention may be required."
        }
        ```
         *or*
        ```json
        {
            "status": "error",
            "message": "Restart failed during stop phase: Failed to stop server '<server_name>': Error sending command: Failed to find screen session 'bedrock-<server_name>' to send command to."
        }
        ```
    *   If the **start phase** fails (either initially if stopped, or after a successful stop). This could be due to the server executable missing, configuration issues, OS-specific errors, timeout, etc. (`ServerStartError`, `ServerNotFoundError`, `CommandNotFoundError`).
        ```json
        {
            "status": "error",
            "message": "Restart failed during start phase: Failed to start server '<server_name>': Server executable 'bedrock_server' not found in /path/to/servers/<server_name>"
        }
        ```
         *or*
        ```json
        {
            "status": "error",
            "message": "Restart failed during start phase: Failed to start server '<server_name>': Server '<server_name>' failed to start within the timeout."
        }
        ```
    *   If an unexpected error occurs during the overall restart orchestration.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred: <original error message>"
        }
        ```
*   **`501 Not Implemented`**:
    *   If the underlying stop or start mechanisms are attempted on an unsupported operating system. This might also manifest as a `SendCommandError` during the stop phase if sending commands isn't supported.
        ```json
        {
             "status": "error",
             "message": "Restart failed during stop phase: Failed to stop server '<server_name>': Unsupported operating system: Darwin"
        }
        ```
         *or*
        ```json
        {
             "status": "error",
             "message": "Restart failed during start phase: Failed to start server '<server_name>': Unsupported operating system: Darwin"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/restart
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/restart" -Headers $headers
```

---

### `POST /api/server/{server_name}/send_command` - Send Command

Sends a command string to the specified running Bedrock server instance's console input. This relies on OS-specific mechanisms (`screen` on Linux, Named Pipes on Windows).

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the target server instance.

#### Request Body (`application/json`)

```json
{
    "command": "your server command here"
}
```
*   **Fields:**
    *   `command` (*string*, required): The command string to be sent to the server console. Must not be empty or whitespace only.

#### Success Response (`200 OK`)

Returned when the command is successfully sent to the server's input mechanism. Note: This only confirms the command was sent, not that the server successfully processed it.

```json
{
    "status": "success",
    "message": "Command '<command>' sent successfully."
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        {
            "status": "error",
            "message": "Invalid or missing JSON request body."
        }
        ```
    *   If the `command` field is missing, not a string, or empty/whitespace only.
        ```json
        {
            "status": "error",
            "message": "Request body must contain a non-empty string 'command' field."
        }
        ```
    *   If the `server_name` path parameter is considered invalid (e.g., empty).
        ```json
        {
            "status": "error",
            "message": "Invalid input: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`404 Not Found`**:
    *   If the server's executable (`bedrock_server` or `.exe`) is missing, even if trying to send a command (`ServerNotFoundError`). This error occurs during the server object initialization.
        ```json
        {
            "status": "error",
            "message": "Server not found: Server executable 'bedrock_server' not found in /path/to/servers/MyServer"
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` are missing or invalid (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Server configuration error: BASE_DIR setting is missing or empty in configuration."
        }
        ```
    *   If the target server process is not running or cannot be communicated with (`ServerNotRunningError`).
        ```json
        {
            "status": "error",
            "message": "Failed to send command: Server 'MyServer' is not running."
        }
        ```
         *or (Linux screen)*
        ```json
        {
            "status": "error",
            "message": "Failed to send command: Screen session 'bedrock-MyServer' not found."
        }
        ```
         *or (Windows pipe)*
        ```json
        {
            "status": "error",
            "message": "Failed to send command: Pipe '\\\\.\\pipe\\BedrockServerMyServer' does not exist. Server likely not running."
        }
        ```
    *   If there's an error during the command sending process (e.g., `screen` execution error, Windows pipe write error) (`SendCommandError`).
        ```json
        {
            "status": "error",
            "message": "Failed to send command: Failed to send command via screen: Command '['/usr/bin/screen', '-S', 'bedrock-MyServer', '-X', 'stuff', 'list\\n']' returned non-zero exit status 1."
        }
        ```
         *or (Windows pipe)*
         ```json
        {
             "status": "error",
             "message": "Failed to send command: Windows error sending command: (109, 'CreateFile', 'The pipe has been ended.')"
        }
         ```
    *   If required commands like `screen` are not found on Linux (`CommandNotFoundError`).
         ```json
         {
             "status": "error",
             "message": "Failed to send command: Command 'screen' not found. Is it installed?"
         }
         ```
    *   If an unexpected error occurs during the process.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred: <original error message>"
        }
        ```
*   **`501 Not Implemented`**:
    *   If sending commands is attempted on an unsupported operating system.
        ```json
        {
            "status": "error",
            "message": "Failed to send command: Sending commands not supported on Darwin"
        }
        ```
    *   If required Windows components (`pywin32`) are missing.
        ```json
        {
            "status": "error",
            "message": "Failed to send command: Cannot send command on Windows: 'pywin32' module not found."
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"command": "say Hello from API!"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/send_command
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ command = 'say Hello from API!' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/send_command" -Headers $headers -Body $body
```

---

### `POST /api/server/{server_name}/update` - Update Server

Checks for the latest Bedrock Dedicated Server version based on the server's configured target version (`target_version` in `./.config/<server_name>/<server_name>_config.json`, defaulting to "LATEST") and updates the specified server instance if a newer version is available or if the installed version is unknown. Handles downloading the new version, backing up the existing server (if updating), extracting files, and optionally sending an in-game notification.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance to update.

#### Request Body

None.

#### Success Response (`200 OK`)

Returned when the update check and/or process completes successfully.

*   If an update was performed:
    ```json
    {
        "status": "success",
        "updated": true,
        "new_version": "1.20.81.01",
        "message": "Server '<server_name>' update process completed. New version: 1.20.81.01."
    }
    ```
*   If the server was already up-to-date:
    ```json
    {
        "status": "success",
        "updated": false,
        "new_version": "1.20.73.02",
        "message": "Server is already up-to-date."
    }
    ```

*   **Fields:**
    *   `status`: Always "success".
    *   `updated` (*boolean*): `true` if a new version was installed, `false` otherwise.
    *   `new_version` (*string | null*): The version string that is now installed after the process. Can be `null` or "UNKNOWN" in some edge cases if version determination fails post-install.
    *   `message` (*string*): A descriptive message about the outcome.

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty).
        ```json
        {
            "status": "error",
            "message": "Invalid input: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR`, `DOWNLOAD_DIR`, or `BACKUP_DIR` are missing or invalid (`FileOperationError`, `DirectoryError`).
        ```json
        {
            "status": "error",
            "message": "Configuration or File error: BACKUP_DIR setting missing."
        }
        ```
    *   If reading the server's configuration (e.g., `target_version`) fails (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Configuration/File error: Error reading config for server '<server_name>': File not found: /path/to/.config/<server_name>/<server_name>_config.json"
        }
        ```
    *   If checking internet connectivity fails (`InternetConnectivityError`).
        ```json
        {
            "status": "error",
            "message": "Server Update failed: Failed to verify internet connectivity: No internet connection detected."
        }
        ```
    *   If looking up the download URL fails (e.g., cannot reach minecraft.net, page structure changed) (`InternetConnectivityError`, `DownloadExtractError`).
        ```json
        {
            "status": "error",
            "message": "Server Update failed: Failed to fetch download page 'https://www.minecraft.net/en-us/download/server/bedrock': ..."
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Server Update failed: Could not find a download URL matching OS 'Linux' and version type 'LATEST' on page ..."
        }
        ```
    *   If downloading the server ZIP file fails (`InternetConnectivityError`, `FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Server Update failed: Download failed for '<download_url>': 404 Client Error: Not Found for url: <download_url>"
        }
        ```
    *   If stopping the server before the update fails (e.g., timeout, command error) (`ServerStopError`).
        ```json
        {
            "status": "error",
            "message": "Server Update failed: Failed to stop server '<server_name>' before update."
        }
        ```
    *   If backing up the server before the update fails (`BackupWorldError`, `FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Server Update failed: Backup failed before update for '<server_name>'."
        }
        ```
    *   If extracting the downloaded ZIP file fails (e.g., corrupted file, permissions, disk full) (`DownloadExtractError`, `FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Server Update failed: Invalid ZIP file: '/path/to/downloads/stable/bedrock-server-1.20.xx.xx.zip'. Bad magic number for file header"
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Server Update failed: Error during file extraction: [Errno 13] Permission denied: '/path/to/servers/<server_name>/bedrock_server'"
        }
        ```
    *   If setting permissions after extraction fails (logged as warning, usually doesn't cause API error unless it prevents server start).
    *   If writing the new version/status to the server's config file fails (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Configuration or File error: Failed to write version/status config for '<server_name>'."
        }
        ```
    *   If restarting the server after the update fails (logged as error, usually doesn't cause API error, but manual start needed).
    *   If an unexpected error occurs during any phase.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred: <original error message>"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/update
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/update" -Headers $headers
```

---

### `DELETE /api/server/{server_name}/delete` - Delete Server

Permanently deletes all data associated with the specified server instance. **This action is irreversible.** It removes the server's installation directory (under `BASE_DIR`), its configuration files (under the manager's config directory), and its backups (under `BACKUP_DIR`). If the server process is running, it will attempt to stop it first before deleting the data.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance to delete.

#### Request Body

None.

#### Success Response (`200 OK`)

Returned when all associated server data (installation, config, backups) has been successfully removed.

```json
{
    "status": "success",
    "message": "All data for server '<server_name>' deleted successfully."
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty).
        ```json
        {
            "status": "error",
            "message": "Invalid input: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR`, `BACKUP_DIR`, or the main config directory path cannot be determined (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Configuration error: BACKUP_DIR setting missing."
        }
        ```
        *or*
         ```json
        {
            "status": "error",
            "message": "Configuration error: Base configuration directory is not set or available."
        }
        ```
    *   If the server is running and the attempt to stop it before deletion fails (e.g., timeout, command error). Deletion is aborted in this case. (`ServerStopError`)
        ```json
        {
            "status": "error",
            "message": "Failed to stop server '<server_name>' before deletion: Failed to stop server '<server_name>': Server '<server_name>' failed to stop within the timeout. Manual intervention may be required.. Deletion aborted."
        }
        ```
    *   If deleting the server's installation, configuration, or backup directories fails (e.g., permission errors, files in use) (`DirectoryError`). The message may list multiple failed items.
        ```json
        {
            "status": "error",
            "message": "Error deleting server directories: Failed to completely delete server '<server_name>'. Failed items: installation directory '/path/to/servers/<server_name>' ([Errno 13] Permission denied)"
        }
        ```
    *   If an unexpected error occurs during the stop or deletion process.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred: <original error message>"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X DELETE -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/delete
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Delete -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/delete" -Headers $headers
```

---

## Backup & Restore

### `POST /api/server/{server_name}/backups/prune` - Prune Server Backups

Deletes older backups for a specific server from its subdirectory within the configured `BACKUP_DIR` (e.g., `<BACKUP_DIR>/<server_name>`). It prunes world backups (`*.mcworld`), server properties backups (`server_backup_*.properties`), and other JSON configuration backups (`*_backup_*.json`) separately, keeping a specified number of the newest files (by modification time) for *each* type.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server whose backups should be pruned.

#### Query Parameters

None.

#### Request Body (`application/json`, optional)

An optional JSON object to specify the number of backups to keep.

```json
{
    "keep": 10
}
```
*   **`keep`** (*integer*, optional): The number of the most recent backups of *each type* (world, properties, json) to retain. If omitted or if the request body is empty, the value from the `BACKUP_KEEP` setting in the Bedrock Server Manager configuration will be used (defaulting to 3 if the setting is missing or invalid).

#### Success Response (`200 OK`)

Returned when the pruning process for all backup types completes without errors, or if the server's backup directory didn't exist.

*   If pruning occurred or was not needed:
    ```json
    {
        "status": "success",
        "message": "Backup pruning completed for server '<server_name>'."
    }
    ```
*   If the server's backup directory was not found:
    ```json
    {
        "status": "success",
        "message": "No backup directory found, nothing to prune."
    }
    ```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty).
        ```json
        {
            "status": "error",
            "message": "Server name cannot be empty."
        }
        ```
    *   If the `keep` value in the JSON body is provided but is not a valid integer.
        ```json
        {
            "status": "error",
            "message": "Invalid 'keep' value. Must be an integer."
        }
        ```
    *   If the resolved `keep` value (from request or settings) is negative or otherwise invalid.
        ```json
        {
            "status": "error",
            "message": "Configuration or input error: Invalid BACKUP_KEEP setting: must be non-negative integer"
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Configuration or input error: Invalid backup_keep parameter: Cannot be negative"
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid (handled by `@auth_required` decorator).
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```
        *(Or a more specific message for invalid tokens)*

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` or `BACKUP_DIR` are missing or invalid (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Configuration or input error: BACKUP_DIR setting missing."
        }
        ```
    *   If the server-specific backup directory path exists but is not a directory (`DirectoryError`).
        ```json
        {
             "status": "error",
             "message": "Pruning failed for some backup types: World backups (Backup path '/path/to/backups/MyServer' exists but is not a directory.)"
        }
        ```
    *   If an error occurs while trying to determine the world name for prefixing world backups (e.g., `server.properties` unreadable). Pruning for world backups might proceed without a prefix in this case, but the overall operation could still fail later.
        *(No specific distinct error response, but could contribute to a later pruning error)*
    *   If an error occurs during the file system operations (listing, sorting, deleting) for *any* of the backup types (`FileOperationError`, `OSError`). The message will indicate which type(s) failed.
        ```json
        {
            "status": "error",
            "message": "Pruning failed for some backup types: World backups (Failed to delete all required old backups (1 deletion(s) failed). Check logs.); JSON backups (Error pruning backups in '/path/to/backups/MyServer': [Errno 13] Permission denied)"
        }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        {
            "status": "error",
            "message": "Unexpected error pruning backups."
        }
        ```

#### `curl` Example (Bash)

```bash
# Using default keep count from server settings
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/backups/prune

# Specifying keep count
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"keep": 5}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/backups/prune
```

#### PowerShell Example

```powershell
# Using default keep count from server settings
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/backups/prune" -Headers $headers

# Specifying keep count
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ keep = 5 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/backups/prune" -Headers $headers -Body $body
```

---

### `POST /api/server/{server_name}/backup/action` - Trigger Backup

Triggers a backup operation (world, specific config file, or all) for the specified server. Backup files are created in a server-specific subdirectory within the globally configured `BACKUP_DIR`. Optionally stops/starts the server if it's running (default behavior, controlled by API layer).

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance to back up.

#### Request Body (`application/json`)

*   **For World Backup:**
    ```json
    {"backup_type": "world"}
    ```
*   **For Config File Backup:**
    ```json
    {"backup_type": "config", "file_to_backup": "server.properties"}
    ```
    *   `file_to_backup` should be the relative path within the server directory (e.g., "server.properties", "permissions.json", "allowlist.json").
*   **For Full Backup (World + Standard Configs):**
    ```json
    {"backup_type": "all"}
    ```

*   **Fields:**
    *   `backup_type` (*string*, required): Specifies the type of backup. Must be one of `"world"`, `"config"`, `"all"`. Case-insensitive.
    *   `file_to_backup` (*string*, required if `backup_type` is `"config"`): The relative path of the configuration file to back up within the server's directory.

#### Success Response (`200 OK`)

Returned when the specified backup operation completes successfully.

```json
{
    "status": "success",
    "message": "World backup completed successfully for server '<server_name>'."
}
```
*or*
```json
{
    "status": "success",
    "message": "Config file backup for 'server.properties' completed successfully."
}
```
*or*
```json
{
    "status": "success",
    "message": "Full backup completed successfully for server '<server_name>'."
}
```
*(Note: If the server was stopped for backup and failed to restart, the response will indicate the restart error instead.)*

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        {
            "status": "error",
            "message": "Invalid or missing JSON request body."
        }
        ```
    *   If `backup_type` is missing or invalid.
        ```json
        {
            "status": "error",
            "message": "Missing or invalid 'backup_type'. Must be one of: ['world', 'config', 'all']."
        }
        ```
    *   If `backup_type` is `"config"` but `file_to_backup` is missing or not a string.
        ```json
        {
            "status": "error",
            "message": "Missing or invalid 'file_to_backup' (string) required for config backup type."
        }
        ```
    *   If the specified `file_to_backup` does not exist within the server directory (`FileNotFoundError`).
        ```json
        {
            "status": "error",
            "message": "Invalid input or file not found: Configuration file not found at: /path/to/servers/MyServer/nonexistent.json"
        }
        ```
    *   If other input arguments are invalid (`MissingArgumentError`, `InvalidInputError`).
        ```json
        {
            "status": "error",
            "message": "Invalid input or file not found: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid (handled by `@auth_required` decorator).
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` or `BACKUP_DIR` are missing or invalid (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Server configuration error: BACKUP_DIR setting missing."
        }
        ```
    *   If an error occurs while stopping or starting the server (if applicable).
        ```json
        {
            "status": "error",
            "message": "Failed to stop server for backup: Server process with PID 1234 not found or already stopped."
        }
        ```
    *   If the world backup operation fails (e.g., cannot determine world name, cannot create zip archive, directory errors) (`BackupWorldError`, `FileOperationError`, `DirectoryError`).
        ```json
        {
            "status": "error",
            "message": "World backup failed: World backup failed for 'MyServer': Could not determine world name for server 'MyServer'. Cannot perform world backup."
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "World backup failed: World backup failed for 'MyServer': Failed to create world backup archive: [Errno 13] Permission denied: '/path/to/backups/MyServer/world_backup_...mcworld.zip'"
        }
        ```
    *   If a config file backup operation fails (e.g., cannot copy file, permission errors) (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Config file backup for 'server.properties' failed: Failed to copy config file 'server.properties': [Errno 13] Permission denied"
        }
        ```
    *   If the "all" backup fails on any component (`BackupWorldError`, `FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Full backup failed: World backup failed during full backup of 'MyServer'."
        }
        ```
         *or*
        ```json
        {
            "status": "error",
            "message": "Full backup failed: Full backup completed with errors. Failed to back up config file(s): permissions.json."
        }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred: <original error message>"
        }
        ```

#### `curl` Example (Bash - World Backup)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"backup_type": "world"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/backup/action
```

#### PowerShell Example (Config Backup)

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ backup_type = 'config'; file_to_backup = 'server.properties' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/backup/action" -Headers $headers -Body $body
```

---

### `POST /api/server/{server_name}/restore/action` - Trigger Restore

Restores a server's world or a specific configuration file from a specified backup file. **Warning:** This overwrites current files. It's recommended to stop the server before restoring (the API handles this by default). Ensures the backup file path is within the configured `BACKUP_DIR`.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance to restore to.

#### Request Body (`application/json`)

```json
{
    "restore_type": "world",
    "backup_file": "/full/path/to/backups/MyServer/backup_file.mcworld"
}
```
*or*
```json
{
    "restore_type": "config",
    "backup_file": "/full/path/to/backups/MyServer/server_backup_....properties"
}
```

*   **Fields:**
    *   `restore_type` (*string*, required): Type of restore. Must be `"world"` or `"config"`. Case-insensitive.
    *   `backup_file` (*string*, required): The full, absolute path to the backup file to restore from. This path *must* reside within the configured `BACKUP_DIR` hierarchy.

#### Success Response (`200 OK`)

Returned when the restore operation completes successfully.

```json
{
    "status": "success",
    "message": "Restoration from 'world_backup_xyz.mcworld' (type: world) completed successfully."
}
```
*(Note: If the server was stopped for restore and failed to restart, the response will indicate the restart error instead.)*

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        {
            "status": "error",
            "message": "Invalid or missing JSON request body."
        }
        ```
    *   If `restore_type` or `backup_file` is missing or invalid.
        ```json
        {
            "status": "error",
            "message": "Missing or invalid 'restore_type'. Must be one of: ['world', 'config']."
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Missing or invalid 'backup_file' path (string) in request."
        }
        ```
    *   If the provided `backup_file` path is outside the configured `BACKUP_DIR`.
        ```json
        {
            "status": "error",
            "message": "Invalid backup file path: Path is outside the allowed backup directory."
        }
        ```
    *   If other input arguments are invalid (`MissingArgumentError`, `InvalidInputError`).
        ```json
        {
            "status": "error",
            "message": "Invalid input or configuration: Server name cannot be empty."
        }
        ```
    *   If trying to restore a config backup with an invalid filename format (can't determine original name).
         ```json
        {
            "status": "error",
            "message": "Config restore failed: Could not determine original filename from backup file format: 'bad_backup_name.properties'"
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`404 Not Found`**:
    *   If the specified `backup_file` does not exist at the validated path.
        ```json
        {
            "status": "error",
            "message": "Backup file not found."
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` or `BACKUP_DIR` are missing or invalid (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Server configuration or file error: BACKUP_DIR setting is missing or empty in configuration."
        }
        ```
    *   If an error occurs while stopping or starting the server (if applicable).
        ```json
        {
            "status": "error",
            "message": "Failed to stop server for restore: Server process with PID 1234 not found or already stopped."
        }
        ```
    *   If the world restore (unzipping/import) fails (`RestoreError`, `AddonExtractError`, `FileOperationError`, `DirectoryError`).
        ```json
        {
            "status": "error",
            "message": "World restore failed: World import failed for server 'MyServer': Failed to extract archive: Error extracting zip file /path/to/backups/MyServer/world_backup_xyz.mcworld: Bad magic number for file header"
        }
        ```
    *   If the config file restore fails (e.g., cannot copy file, permission denied) (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Config file restore failed: Failed to restore config file 'server.properties': [Errno 13] Permission denied"
        }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred during restore: <original error message>"
        }
        ```

#### `curl` Example (Bash - World Restore)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"restore_type": "world", "backup_file": "/full/path/to/backups/MyServer/world_backup_xyz.mcworld"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/restore/action
```

#### PowerShell Example (Config Restore)

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ restore_type = 'config'; backup_file = 'C:\full\path\to\backups\MyServer\server_backup_abc.properties' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/restore/action" -Headers $headers -Body $body
```

---

### `POST /api/server/{server_name}/restore/all` - Trigger Restore All

Restores the server's world AND standard configuration files (`server.properties`, `allowlist.json`, `permissions.json`) from their respective *latest* available backups found within the server's subdirectory in the configured `BACKUP_DIR`. **Warning:** This overwrites current files. It's recommended to stop the server first (the API handles this by default).

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance to restore.

#### Request Body

None.

#### Success Response (`200 OK`)

Returned when the restore operation for all components completes without errors.

```json
{
    "status": "success",
    "message": "Restore all completed successfully for server '<server_name>'."
}
```
*(Note: If the server was stopped for restore and failed to restart, the response will indicate the restart error instead.)*

#### Error Responses

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` or `BACKUP_DIR` are missing or invalid (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Configuration or input error: BACKUP_DIR setting is missing or empty."
        }
        ```
    *   If the server's backup directory doesn't exist (note: the API function returns successfully in this case, logged as a warning, but the route would still return 200 OK according to the code).
    *   If an error occurs while stopping or starting the server (if applicable).
        ```json
        {
            "status": "error",
            "message": "Failed to stop server for restore: Server process with PID 1234 not found or already stopped."
        }
        ```
    *   If any part of the restore (world or any config file) fails. The error message will indicate the failed components (`RestoreError`).
        ```json
        {
            "status": "error",
            "message": "Restore all failed: Restore failed for server 'MyServer'. Failed components: World (World import failed for server 'MyServer': Failed to extract archive: ...), server.properties (Failed to restore config file 'server.properties': [Errno 13] Permission denied)"
        }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred during restore all: <original error message>"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/restore/all
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/restore/all" -Headers $headers
```

---

## World & Addon Management

### `POST /api/server/{server_name}/world/export` - Export World

Exports the currently active world directory associated with the specified server instance into a `.mcworld` archive file. The resulting file is saved within the `worlds` subdirectory of the configured `CONTENT_DIR`, making it available for installation on other servers managed by this application.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance whose world should be exported.

#### Request Body

None.

#### Success Response (`200 OK`)

Returned when the world export process completes successfully and the `.mcworld` file is created in the target directory (`<CONTENT_DIR>/worlds/`).

```json
{
    "status": "success",
    "message": "World for server '<server_name>' exported successfully as '<export_filename.mcworld>'.",
    "export_file": "/full/path/to/content/worlds/<export_filename.mcworld>"
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is considered invalid (e.g., empty) (`InvalidServerNameError`).
        ```json
        {
            "status": "error",
            "message": "Invalid server name provided: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` or `CONTENT_DIR` are missing or invalid (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Configuration or file system error: Required setting 'CONTENT_DIR' is missing."
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Configuration or file system error: BASE_DIR setting is missing or empty in configuration."
        }
        ```
    *   If the system fails to create the target export directory (`<CONTENT_DIR>/worlds/`) due to permissions or other OS issues (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Configuration or file system error: Cannot create export directory '/path/to/content/worlds': [Errno 13] Permission denied"
        }
        ```
    *   If the API fails to determine the current world name for the server (e.g., `server.properties` read error, returned as error status by `api_world.export_world`).
        ```json
        {
            "status": "error",
            "message": "Failed to export world: Could not read world name from properties file: /path/to/server/server.properties"
        }
        ```
    *   If the determined world directory does not exist or is not accessible (`DirectoryError`).
        ```json
        {
            "status": "error",
            "message": "World export process error: World directory 'MyWorldName' not found at expected location: /path/to/server/worlds/MyWorldName"
        }
        ```
    *   If creating the `.mcworld` ZIP archive fails due to disk space, permissions, or other `shutil` issues (`BackupWorldError`).
        ```json
        {
            "status": "error",
            "message": "World export process error: Failed to create world backup archive: [Errno 28] No space left on device"
        }
        ```
    *   If an unexpected error occurs during the export process.
        ```json
        {
            "status": "error",
            "message": "Unexpected error during world export: <original error message>"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/world/export
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/world/export" -Headers $headers
```

---

### `POST /api/server/{server_name}/world/install` - Install World

Installs a world from a `.mcworld` file into the specified server, replacing the existing world files. The `.mcworld` file must already exist within the configured `content/worlds` directory (defined by the `CONTENT_DIR` setting). **Warning:** This overwrites the server's current world defined by `level-name` in `server.properties`. It is recommended to stop the server before performing this action (the API handles this by default).

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The name of the server instance to install the world to.

#### Request Body (`application/json`)

```json
{
    "filename": "MyCoolWorld.mcworld"
}
```
*or (with subdirectories)*
```json
{
    "filename": "user_uploads/MyCoolWorld.mcworld"
}
```

*   **Fields:**
    *   `filename` (*string*, required): The path to the `.mcworld` file *relative* to the configured `content/worlds` directory (e.g., `<CONTENT_DIR>/worlds`). Path traversal attempts outside this directory are blocked.

#### Success Response (`200 OK`)

Returned when the world file is found, validated, and successfully extracted into the server's world directory.

```json
{
    "status": "success",
    "message": "World 'MyCoolWorld.mcworld' installed successfully for server '<server_name>'."
}
```
*(Note: If the server was stopped for the import and failed to restart, the response will indicate the restart error instead.)*

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        {
            "status": "error",
            "message": "Invalid or missing JSON request body."
        }
        ```
    *   If the `filename` field is missing or not a string.
        ```json
        {
            "status": "error",
            "message": "Missing or invalid 'filename' in request body. Expected relative path to .mcworld file."
        }
        ```
    *   If the resolved `filename` path attempts to go outside the allowed `content/worlds` directory (Path Traversal attempt).
        ```json
        {
            "status": "error",
            "message": "Invalid filename: Filename must be within the allowed content directory."
        }
        ```
    *   If other input validation fails (e.g., empty `server_name`).
        ```json
        {
            "status": "error",
            "message": "World installation error: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`404 Not Found`**:
    *   If the specified `.mcworld` file (resolved from `filename`) does not exist at the calculated path within `content/worlds`.
        ```json
        {
            "status": "error",
            "message": "Selected world file not found: /path/to/content/worlds/nonexistent.mcworld"
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` or `CONTENT_DIR` are missing or invalid (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "World installation error: Configuration error: BASE_DIR setting is missing or empty in configuration."
        }
        ```
    *   If an error occurs while stopping or starting the server (if applicable).
        ```json
        {
            "status": "error",
            "message": "Failed to stop server for import: Server process with PID 1234 not found or already stopped."
        }
        ```
    *   If the target world name cannot be determined from the server's `server.properties` file (`FileOperationError`).
        ```json
        {
             "status": "error",
             "message": "World installation error: World import failed: Cannot import world: Failed to get world name for server '<server_name>'."
        }
        ```
    *   If the world extraction fails (e.g., invalid `.mcworld` file format, disk full, permission denied) (`DownloadExtractError`, `FileOperationError`, `DirectoryError`).
        ```json
        {
             "status": "error",
             "message": "World installation error: World import failed: Error extracting archive '/path/to/content/worlds/MyCoolWorld.mcworld': File is not a zip file"
        }
        ```
        *or*
        ```json
        {
             "status": "error",
             "message": "World installation error: World import failed: Failed to remove existing world directory '/path/to/servers/MyServer/worlds/Bedrock level': [Errno 13] Permission denied"
        }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        {
            "status": "error",
            "message": "Unexpected error during world installation: <original error message>"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"filename": "MyDownloadedWorld.mcworld"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/world/install
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ filename = 'MyDownloadedWorld.mcworld' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/world/install" -Headers $headers -Body $body
```

---

### `POST /api/server/{server_name}/addon/install` - Install Addon

Installs an addon pack (`.mcaddon` or `.mcpack`) into the specified server. The addon file must already exist within the configured `content/addons` directory (defined by the `CONTENT_DIR` setting). Extracts behavior packs and/or resource packs from the addon file and installs them into the server's world directory, updating the necessary world manifest files (`world_behavior_packs.json`, `world_resource_packs.json`). It's recommended to stop the server before performing this action (the API handles this by default).

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The name of the server instance to install the addon to.

#### Request Body (`application/json`)

```json
{
    "filename": "CoolBehaviorPack.mcpack"
}
```
*or*
```json
{
    "filename": "collections/AwesomeAddonCollection.mcaddon"
}
```

*   **Fields:**
    *   `filename` (*string*, required): The path to the `.mcaddon` or `.mcpack` file *relative* to the configured `content/addons` directory (e.g., `<CONTENT_DIR>/addons`). Path traversal attempts outside this directory are blocked.

#### Success Response (`200 OK`)

Returned when the addon file is found, validated, processed, and successfully installed/activated within the server's world.

```json
{
    "status": "success",
    "message": "Addon 'AwesomeAddonCollection.mcaddon' installed successfully for server '<server_name>'."
}
```
*(Note: If the server was stopped for the install and failed to restart, the response will indicate the restart error instead.)*

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        {
            "status": "error",
            "message": "Invalid or missing JSON request body."
        }
        ```
    *   If the `filename` field is missing or not a string.
        ```json
        {
            "status": "error",
            "message": "Missing or invalid 'filename' in request body. Expected relative path to .mcaddon/.mcpack file."
        }
        ```
    *   If the resolved `filename` path attempts to go outside the allowed `content/addons` directory (Path Traversal attempt).
        ```json
        {
            "status": "error",
            "message": "Invalid filename: Filename must be within the allowed content directory."
        }
        ```
    *   If the specified addon file (`filename`) has an unsupported extension (not `.mcaddon` or `.mcpack`). (`InvalidAddonPackTypeError`)
        ```json
        {
            "status": "error",
            "message": "Addon installation error: Unsupported addon file type: 'MyAddon.zip'. Only .mcaddon and .mcpack are supported."
        }
        ```
    *   If the addon file (`.mcpack` or contained within `.mcaddon`) has an invalid or missing `manifest.json`. (`AddonExtractError`)
        ```json
        {
            "status": "error",
            "message": "Addon installation error: Invalid manifest structure in /path/to/temp/..../manifest.json. Missing fields: ['uuid']"
        }
        ```
        *or*
         ```json
        {
            "status": "error",
            "message": "Addon installation error: Manifest not found in pack: /path/to/temp/..."
        }
        ```
    *   If other input validation fails (e.g., empty `server_name`). (`MissingArgumentError`)
        ```json
        {
            "status": "error",
            "message": "Addon installation error: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`404 Not Found`**:
    *   If the specified addon file (resolved from `filename`) does not exist at the calculated path within `content/addons`.
        ```json
        {
            "status": "error",
            "message": "Selected addon file not found: /path/to/content/addons/nonexistent.mcpack"
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` or `CONTENT_DIR` are missing or invalid (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Addon installation error: Configuration error: BASE_DIR setting is missing or empty in configuration."
        }
        ```
    *   If an error occurs while stopping or starting the server (if applicable).
        ```json
        {
            "status": "error",
            "message": "Failed to stop server before import: Server process with PID 1234 not found or already stopped."
        }
        ```
    *   If the target world name cannot be determined from the server's `server.properties` file (needed for placing packs). (`FileOperationError`)
         ```json
        {
            "status": "error",
            "message": "Addon installation error: Failed to determine world name or paths for server '<server_name>': Could not determine world name for server '<server_name>'."
        }
        ```
    *   If the addon file is corrupted or not a valid ZIP archive (`.mcaddon`, `.mcpack`). (`AddonExtractError`)
        ```json
        {
            "status": "error",
            "message": "Addon installation error: Invalid .mcpack file (not a zip): CoolBehaviorPack.mcpack"
        }
        ```
    *   If file system errors occur during extraction or installation (copying pack files, creating directories, updating world JSON files, permissions, disk full). (`FileOperationError`, `DirectoryError`)
        ```json
        {
            "status": "error",
            "message": "Addon installation error: Failed to copy behavior pack files: [Errno 13] Permission denied: '/path/to/servers/MyServer/worlds/Bedrock level/behavior_packs/CoolPack_1.0.0/script.js'"
        }
        ```
        *or*
        ```json
        {
             "status": "error",
             "message": "Addon installation error: Failed to update world activation JSON 'world_resource_packs.json': Failed to write world pack JSON: world_resource_packs.json"
        }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        {
            "status": "error",
            "message": "Unexpected error during addon installation: <original error message>"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"filename": "AwesomeAddonCollection.mcaddon"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/addon/install
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ filename = 'AwesomeAddonCollection.mcaddon' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/addon/install" -Headers $headers -Body $body
```

---

## Player Management

### `POST /api/players/scan` - Scan Player Logs

Triggers a scan of all server log files (`server_output.txt`) found within subdirectories of the main `BASE_DIR`. It searches for player connection entries (extracting player name and XUID) and updates the central `players.json` file located in the application's configuration directory with any newly discovered or updated player information. Existing player entries are preserved, and duplicates (based on XUID) are handled.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

None.

#### Query Parameters

None.

#### Request Body

None.

#### Success Response (`200 OK`)

Indicates the scan process initiated and completed, potentially finding players. The exact message varies.

*   If players were found and saved/updated successfully:
    ```json
    {
        "status": "success",
        "players_found": true,
        "message": "Player scan completed and data saved."
    }
    ```
*   If the scan completed but no new player entries were found in any logs:
    ```json
    {
        "status": "success",
        "players_found": false,
        "message": "Player scan completed, no new player data found."
    }
    ```
*   If no server directories were found under `BASE_DIR`:
    ```json
    {
        "status": "success",
        "players_found": false,
        "message": "No server directories found."
    }
    ```

#### Error Responses

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid (handled by `@auth_required` decorator).
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```
        *(Or a more specific message for invalid tokens)*

*   **`500 Internal Server Error`**:
    *   If essential configuration directories (`BASE_DIR` or the application's main config directory) are missing, invalid, or inaccessible (`FileOperationError`, `DirectoryError`).
        ```json
        {
            "status": "error",
            "message": "Configuration or directory error: Base directory '/path/to/servers' does not exist or is not a directory."
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Configuration or directory error: Base configuration directory is not set or available."
        }
        ```
    *   If errors occurred while scanning log files for *some* servers (e.g., read permissions), but the process attempted to complete for others.
        ```json
        {
            "status": "error",
            "message": "Scan completed with errors for server(s): ServerA, ServerC. Player data found in other logs was saved."
        }
        ```
    *   If an error occurred while trying to save the collected player data to `players.json` (e.g., write permissions, invalid JSON loaded, disk full) (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Error saving player data to JSON: Failed to write players data to '/path/to/.config/players.json': [Errno 13] Permission denied"
        }
        ```
        *(Note: If both scan and save errors occur, the message might combine them)*
    *   If an unexpected error occurs during the overall scanning or saving process.
        ```json
        {
            "status": "error",
            "message": "Unexpected error scanning player logs."
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/players/scan
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/players/scan" -Headers $headers
```

---

### `GET /api/server/{server_name}/allowlist` - Get Allowlist

Retrieves the current list of players from the server's `allowlist.json` file.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The name of the server instance whose allowlist should be retrieved.

#### Query Parameters

None.

#### Request Body

None.

#### Success Response (`200 OK`)

Returns the list of players currently in the `allowlist.json` file. The list will be empty if the file does not exist, is empty, or contains invalid JSON.

```json
{
    "status": "success",
    "existing_players": [
        {
            "ignoresPlayerLimit": false,
            "name": "PlayerOne"
        },
        {
            "ignoresPlayerLimit": false,
            "name": "PlayerTwoXUID"
        }
    ],
    "message": "Successfully retrieved 2 players from allowlist."
}
```
*or if empty/not found:*
```json
{
    "status": "success",
    "existing_players": [],
    "message": "Successfully retrieved 0 players from allowlist."
}
```

*   **Fields:**
    *   `status`: Always "success".
    *   `existing_players` (*list[object]*): A list containing the player objects as stored in `allowlist.json`. Each object typically contains:
        *   `ignoresPlayerLimit` (*boolean*): Whether the player ignores the server's player limit.
        *   `name` (*string*): The player's Gamertag.
    *   `message` (*string*): A message indicating the number of players retrieved.

#### Error Responses

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`500 Internal Server Error`**:
    *   If `server_name` is invalid (e.g., empty) (`MissingArgumentError`, `InvalidServerNameError`).
        ```json
        { "status": "error", "message": "Error retrieving allowlist: Server name cannot be empty." }
        ```
    *   If essential configuration like `BASE_DIR` is missing or the server directory cannot be found (`FileOperationError`, `DirectoryError`).
        ```json
        { "status": "error", "message": "Error retrieving allowlist: Server directory not found: /path/to/servers/<server_name>" }
        ```
         *or*
        ```json
        { "status": "error", "message": "Error retrieving allowlist: Configuration error: BASE_DIR setting is missing..." }
        ```
    *   If reading the `allowlist.json` file fails due to permissions or other OS errors (`FileOperationError`).
        ```json
        { "status": "error", "message": "Error retrieving allowlist: Failed to read allowlist file: /path/to/servers/<server_name>/allowlist.json" }
        ```
    *   If the `allowlist.json` file contains invalid JSON and cannot be parsed (`FileOperationError` wrapping `JSONDecodeError`).
        ```json
        { "status": "error", "message": "Error retrieving allowlist: Invalid JSON in allowlist file: /path/to/servers/<server_name>/allowlist.json" }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        { "status": "error", "message": "An unexpected error occurred: <original error message>" }
        ```

#### `curl` Example (Bash)

```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/allowlist
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/allowlist" -Headers $headers
```

---

### `POST /api/server/{server_name}/allowlist/add` - Add Players to Allowlist

Adds players to the server's `allowlist.json` file. It reads the existing allowlist and appends only the players from the request body's `players` list that are not already present (comparison is case-insensitive by player name).

*Note: This endpoint performs an **ADD** operation, not a replace. To clear the allowlist, send an empty `players` list.*

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The name of the server instance whose allowlist should be modified.

#### Request Body (`application/json`)

```json
{
    "players": ["NewPlayer1", "AnotherPlayer"],
    "ignoresPlayerLimit": false
}
```
*   **Fields:**
    *   `players` (*list[string]*, required): A list of player names (Gamertags) to add to the allowlist. Empty or invalid names in the list will be ignored. Sending an empty list `[]` will not add any players but will rewrite the existing file (effectively no change unless the file was missing/invalid).
    *   `ignoresPlayerLimit` (*boolean*, optional): Defaults to `false`. Sets the `ignoresPlayerLimit` flag for *all* players being added in this request.

#### Success Response (`200 OK`)

Returned when the operation completes, even if no new players were actually added (e.g., all provided players were duplicates).

*   If new players were added:
    ```json
    {
        "status": "success",
        "message": "Allowlist saved successfully with X player(s)." // X = number of *new* players added
    }
    ```
*   If no new players were added (e.g., empty input list, all duplicates):
    ```json
    {
        "status": "success",
        "message": "No new players provided or all provided players were duplicates/invalid." // Or similar message from API layer
    }
    ```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        { "status": "error", "message": "Invalid or missing JSON request body." }
        ```
    *   If the `players` key is missing or its value is not a list.
        ```json
        { "status": "error", "message": "Request body must contain a 'players' list (can be empty)." }
        ```
    *   If the `ignoresPlayerLimit` key is present but its value is not a boolean (`true` or `false`).
        ```json
        { "status": "error", "message": "'ignoresPlayerLimit' must be true or false." }
        ```
    *   If `server_name` is invalid (e.g., empty).
        ```json
        { "status": "error", "message": "Error saving allowlist: Server name cannot be empty." }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration like `BASE_DIR` is missing or the server directory cannot be found (`FileOperationError`, `DirectoryError`).
        ```json
        { "status": "error", "message": "Error saving allowlist: Failed to access allowlist: Server directory not found: /path/to/servers/<server_name>" }
        ```
    *   If reading the existing `allowlist.json` fails (e.g., permissions, invalid JSON format). (`FileOperationError`).
        ```json
        { "status": "error", "message": "Error saving allowlist: Failed to read allowlist file: /path/to/servers/<server_name>/allowlist.json" }
        ```
    *   If writing the updated `allowlist.json` fails (e.g., permissions, disk full). (`FileOperationError`).
        ```json
        { "status": "error", "message": "Error saving allowlist: Failed to write allowlist file: /path/to/servers/<server_name>/allowlist.json" }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        { "status": "error", "message": "An unexpected error occurred: <original error message>" }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"players": ["AdminUser", "VIP_Player"], "ignoresPlayerLimit": false}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/allowlist/add
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ players = @('AdminUser', 'VIP_Player'); ignoresPlayerLimit = $false } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/allowlist/add" -Headers $headers -Body $body
```

---

### `DELETE /api/server/{server_name}/allowlist/player/{player_name}` - Remove Player from Allowlist

Removes a specific player from the `allowlist.json` file for the specified server instance. The player name matching is case-insensitive.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The unique name of the server instance.
*   `**player_name**` (*string*, required): The name of the player to remove from the allowlist (case-insensitive).

#### Request Body

None.

#### Success Response (`200 OK`)

Returned when the operation completes. The message indicates whether the player was found and removed, or if the player was not found on the list.

*   *Player found and removed:*
    ```json
    {
        "status": "success",
        "message": "Player '<player_name>' removed successfully from allowlist for server '<server_name>'."
    }
    ```
*   *Player not found:*
    ```json
    {
        "status": "success",
        "message": "Player '<player_name>' not found in the allowlist for server '<server_name}'. No changes made."
    }
    ```

#### Error Responses

*   **`400 Bad Request`**:
    *   If `server_name` or `player_name` path parameters are missing or empty (`MissingArgumentError`).
        ```json
        {
            "status": "error",
            "message": "Invalid input: Player name cannot be empty."
        }
        ```
        *or*
        ```json
        {
            "status": "error",
            "message": "Invalid input: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```

*   **`404 Not Found`**:
    *   If the specified server's directory cannot be found (`DirectoryError`).
        ```json
        {
            "status": "error",
            "message": "Server directory not found or inaccessible: Server directory not found: C:\\path\\to\\servers\\NonExistentServer"
        }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration like `BASE_DIR` is missing (`FileOperationError` during `get_base_dir`).
        ```json
        {
            "status": "error",
            "message": "File operation error during allowlist update: BASE_DIR setting is missing or empty in configuration."
        }
        ```
    *   If reading or writing the `allowlist.json` file fails due to permissions, disk errors, or invalid JSON content (`FileOperationError` from core).
        ```json
        {
            "status": "error",
            "message": "File operation error during allowlist update: Failed to write updated allowlist file: C:\\path\\to\\servers\\MyServer\\allowlist.json"
        }
        ```
        *or*
         ```json
        {
            "status": "error",
            "message": "File operation error during allowlist update: Invalid JSON in allowlist file: C:\\path\\to\\servers\\MyServer\\allowlist.json"
        }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        {
            "status": "error",
            "message": "Unexpected error during player removal: <original error message>"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X DELETE -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://<your-manager-host>:<port>/api/server/<server_name>/allowlist/player/<player_name>
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Delete -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/allowlist/player/<player_name>" -Headers $headers
```

---

### `PUT /api/server/{server_name}/permissions` - Update Player Permissions

Updates the permission levels for one or more players in the server's `permissions.json` file. Takes a JSON object mapping player XUIDs (as strings) to desired permission level strings (`"visitor"`, `"member"`, or `"operator"`). Invalid levels are rejected, and failures for individual players are reported.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The name of the server instance whose permissions should be modified.

#### Request Body (`application/json`)

```json
{
    "permissions": {
        "2535416409681153": "operator",
        "2535457894355891": "member",
        "2535400000000000": "visitor"
    }
}
```
*   **Fields:**
    *   `permissions` (*object*, required): An object where keys are player XUIDs (strings) and values are the desired permission level strings.
        *   **Valid Levels:** `"visitor"`, `"member"`, `"operator"` (case-insensitive in the request, stored lowercase).

#### Success Response (`200 OK`)

Returned if all submitted, valid permission changes were successfully applied, or if no valid changes were submitted.

*   If changes were applied:
    ```json
    {
        "status": "success",
        "message": "Permissions updated successfully for 2 player(s) on server '<server_name>'."
    }
    ```
*   If no valid changes were submitted (e.g., empty `permissions` object, only invalid levels provided):
    ```json
    {
        "status": "success",
        "message": "No valid permission changes submitted."
    }
    ```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing, not valid JSON, or does not contain the required `permissions` key.
        ```json
        { "status": "error", "message": "Request body must contain a 'permissions' object." }
        ```
    *   If the value associated with the `permissions` key is not a JSON object.
        ```json
        { "status": "error", "message": "'permissions' value must be an object mapping XUIDs to levels." }
        ```
    *   If one or more permission levels provided in the `permissions` map are invalid (not "visitor", "member", or "operator"). The response includes an `errors` object detailing the failures.
        ```json
        {
            "status": "error",
            "message": "Validation failed for one or more permission levels.",
            "errors": {
                "2535411111111111": "Invalid level 'guest'. Must be one of ('visitor', 'member', 'operator')."
            }
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration like `BASE_DIR` is missing or the server directory cannot be found (`FileOperationError`, `DirectoryError`).
        ```json
        { "status": "error", "message": "Configuration or File error: Server directory not found: /path/to/servers/<server_name>" }
        ```
    *   If reading or writing the `permissions.json` file fails for *any* player update (e.g., permissions, invalid JSON in file, disk full) (`FileOperationError`). The response includes an `errors` object detailing which XUID(s) failed and why.
        ```json
        {
            "status": "error",
            "message": "One or more errors occurred while setting permissions for '<server_name>'.",
            "errors": {
                "2535457894355891": "Failed to configure permission: Failed to write permissions file: /path/to/servers/<server_name>/permissions.json"
            }
        }
        ```
    *   If an unexpected error occurs during the overall process.
        ```json
        { "status": "error", "message": "An unexpected error occurred: <original error message>" }
        ```

#### `curl` Example (Bash)

```bash
curl -X PUT -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"permissions": {"2535416409681153": "operator", "2535457894355891": "member"}}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/permissions
```

#### PowerShell Example

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

---

## Configuration

### `POST /api/server/{server_name}/properties` - Update Server Properties

Updates specified key-value pairs in the `server.properties` file for the given server. Only properties present in a predefined allowlist can be modified. Input values undergo basic validation before being written to the file. The `level-name` property is automatically cleaned by replacing spaces and disallowed characters with underscores (`_`).

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The name of the server instance whose properties should be modified.

#### Request Body (`application/json`)

A JSON object where keys are the `server.properties` keys to update, and values are their new desired values (usually strings, but numbers are accepted for relevant fields like ports/max-players).

```json
{
    "level-name": "Updated World Name",
    "max-players": "20",
    "difficulty": "hard",
    "server-port": 19133
    // Only include keys you want to change
}
```

*   **Allowed Keys:** Only the following property keys can be modified via this endpoint:
    *   `server-name`
    *   `level-name` (Value automatically cleaned: spaces and `[<>:"/\\|?*]` replaced with `_`)
    *   `gamemode`
    *   `difficulty`
    *   `allow-cheats`
    *   `max-players`
    *   `server-port`
    *   `server-portv6`
    *   `enable-lan-visibility`
    *   `allow-list`
    *   `default-player-permission-level`
    *   `view-distance`
    *   `tick-distance`
    *   `level-seed`
    *   `online-mode`
    *   `texturepack-required`
*   Keys included in the request body that are *not* in this list will be ignored.

#### Success Response (`200 OK`)

Returned when the provided properties are successfully validated and written to the `server.properties` file, or if no valid/allowed properties were provided in the request.

```json
{
    "status": "success",
    "message": "Server properties for '<server_name>' updated successfully."
}
```
*or if no valid properties were provided:*
```json
{
    "status": "success",
    "message": "No valid properties provided or no changes needed."
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        { "status": "error", "message": "Invalid or missing JSON request body." }
        ```
    *   If validation fails for one or more provided property values (based on type, range, or format checks). The response includes an `errors` object detailing the specific failures.
        ```json
        {
            "status": "error",
            "message": "Validation failed for one or more properties.",
            "errors": {
                "server-port": "Invalid value for 'server-port'. Must be a number between 1024 and 65535.",
                "difficulty": "Invalid value for 'difficulty'. Must be one of peaceful, easy, normal, hard."
            }
        }
        ```
    *   If the `server.properties` file cannot be found for the specified server (`FileNotFoundError`).
        ```json
        {
            "status": "error",
            "message": "Error updating properties: server.properties file not found at: /path/to/servers/<server_name>/server.properties"
        }
        ```
    *   If the input `property_value` contains invalid control characters (`InvalidInputError` from core).
        ```json
        {
            "status": "error",
            "message": "Error updating properties: Property value for 'some-key' contains invalid control characters."
        }
        ```
    *   If the `server_name` is invalid (`InvalidServerNameError`).
        ```json
        {
            "status": "error",
            "message": "Error updating properties: Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`500 Internal Server Error`**:
    *   If reading or writing the `server.properties` file fails due to file system errors (e.g., permissions, disk full) (`FileOperationError`).
        ```json
        {
            "status": "error",
            "message": "Error updating properties: Failed to modify server.properties: [Errno 13] Permission denied: '/path/to/servers/<server_name>/server.properties'"
        }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred: <original error message>"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"max-players": "12", "allow-list": "true"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/properties
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
# Note: Quotes may be needed around keys with hyphens depending on PowerShell version/parsing
$body = @{ 'max-players' = '12'; 'allow-list' = 'true' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/properties" -Headers $headers -Body $body
```

---

### `GET /api/servers/<server_name>/read_properties` - Get Server Properties

Retrieves the parsed `server.properties` file content for a specified Bedrock server instance. This allows inspection of the server's configuration settings.

The endpoint attempts to locate and read the `server.properties` file within the server's directory. 

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   **`server_name`** (*string*, **required**): The unique name of the server instance whose `server.properties` file should be read. This corresponds to the server's directory name.

#### Request Body

None.

#### Success Response (`200 OK`)

Returns a dictionary of all key-value pairs found in the server's `server.properties` file.

*   **Example:**
    ```json
    {
        "status": "success",
        "properties": {
            "server-name": "My Bedrock Server",
            "gamemode": "survival",
            "difficulty": "normal",
            "allow-cheats": "false",
            "max-players": "10",
            "online-mode": "true",
            "level-name": "Bedrock level",
            "level-seed": "",
            "default-player-permission-level": "member",
            "texturepack-required": "false"
            // ... and other properties
        }
    }
    ```

*   **`status`**: (*string*) Always "success" for a 200 response.
*   **`properties`**: (*object*): A dictionary where keys are the property names from `server.properties` and values are their corresponding string values. Comments and empty lines from the original file are ignored. Malformed lines might be skipped with a warning in the server logs.

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `server_name` path parameter is invalid (e.g., empty).
        ```json
        {
            "status": "error",
            "message": "Server name cannot be empty."
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`404 Not Found`**:
    *   If the `server.properties` file cannot be found for the specified `server_name` at the determined path.
        ```json
        {
            "status": "error",
            "message": "server.properties file not found at: /path/to/your/servers/the_server_name/server.properties"
        }
        ```

*   **`500 Internal Server Error`**:
    *   If there's a fundamental configuration issue (e.g., `BASE_DIR` not set and no `base_dir` query param provided).
        ```json
        {
            "status": "error",
            "message": "Configuration error: Base directory for servers (BASE_DIR) is not configured."
        }
        ```
    *   If an OS-level error occurs while trying to read the file (e.g., permission denied).
        ```json
        {
            "status": "error",
            "message": "Failed to read server.properties: [Errno 13] Permission denied: '/path/to/server.properties'"
        }
        ```
    *   If an unexpected error occurs during file parsing or within the route handler.
        ```json
        {
            "status": "error",
            "message": "An unexpected error occurred while retrieving server properties."
        }
        ```
        *or a more specific message like:*
        ```json
        {
            "status": "error",
            "message": "Unexpected error reading properties: [specific error details]"
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X GET -H "Authorization: Bearer YOUR_JWT_TOKEN" \
        http://<your-manager-host>:<port>/api/servers/<server_name>/read_properties
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
Invoke-RestMethod -Method Get -Uri "http://<your-manager-host>:<port>/api/servers/<server_name>/read_properties" -Headers $headers
```
---

### `POST /api/server/{server_name}/service` - Configure OS Service Settings

Configures OS-specific service settings for the server instance. The behavior and expected request body depend on the host operating system where the Bedrock Server Manager is running.

*   **Linux:** Creates/updates a systemd user service file (`~/.config/systemd/user/bedrock-<server_name>.service`) and enables/disables it based on the request. Requires the `systemctl` command to be available.
*   **Windows:** Updates the `autoupdate` flag (boolean `true`/`false`) within the server's specific JSON configuration file (`./.config/<server_name>/<server_name>_config.json`).

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

*   `**server_name**` (*string*, required): The name of the server instance to configure.

#### Request Body (`application/json`)

*   **On Linux:**
    ```json
    {
        "autoupdate": true,
        "autostart": true
    }
    ```
    *   `autoupdate` (*boolean*, required): If `true`, configures the systemd service to run the update check (`ExecStartPre`) before starting the server.
    *   `autostart` (*boolean*, required): If `true`, enables the systemd service (`systemctl --user enable`); if `false`, disables it (`systemctl --user disable`).

*   **On Windows:**
    ```json
    {
        "autoupdate": true
    }
    ```
    *   `autoupdate` (*boolean*, required): The desired value (`true` or `false`) for the `autoupdate` setting in the server's JSON configuration file.

#### Success Response (`200 OK`)

Returned when the OS-specific configuration is successfully applied.

*   **On Linux:**
    ```json
    {
        "status": "success",
        "message": "Systemd service created and enabled successfully." // Message varies (enabled/disabled)
    }
    ```
*   **On Windows:**
    ```json
    {
        "status": "success",
        "message": "Autoupdate setting for '<server_name>' updated to true." // Message varies (true/false)
    }
    ```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        { "status": "error", "message": "Invalid or missing JSON request body." }
        ```
    *   **Linux:** If `autoupdate` or `autostart` keys are present but not boolean values.
        ```json
        { "status": "error", "message": "'autoupdate' and 'autostart' must be boolean values." }
        ```
    *   **Windows:** If `autoupdate` key is present but not a boolean value.
        ```json
        { "status": "error", "message": "'autoupdate' must be a boolean value." }
        ```
    *   If `server_name` is invalid (`InvalidServerNameError`).
        ```json
        { "status": "error", "message": "Invalid input: Server name cannot be empty." }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`403 Forbidden` / `500 Internal Server Error` (OS Mismatch):**
    *   If this endpoint is called on an OS other than Linux or Windows. The API route handler returns 403, but the underlying API functions might return a 500 error dict if called directly on the wrong OS.
        ```json
        { "status": "error", "message": "Service configuration is not supported on this operating system (Darwin)." } // Example for macOS
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR` are missing or invalid (`FileOperationError`).
        ```json
        { "status": "error", "message": "Error configuring service: Configuration error: BASE_DIR setting is missing..." }
        ```
    *   **Linux:** If creating the systemd directory or writing the service file fails (permissions, disk full) (`ServiceError`).
        ```json
        { "status": "error", "message": "Failed to configure systemd service: Failed to write service file '/home/user/.config/systemd/user/bedrock-<server_name>.service': [Errno 13] Permission denied" }
        ```
    *   **Linux:** If the `systemctl` command is not found (`CommandNotFoundError`).
        ```json
        { "status": "error", "message": "Failed to configure systemd service: Command 'systemctl' not found in system PATH." }
        ```
    *   **Linux:** If reloading the systemd daemon fails (`SystemdReloadError`).
        ```json
        { "status": "error", "message": "Failed to configure systemd service: Failed to reload systemd user daemon. Error: Failed to connect to bus: $DBUS_SESSION_BUS_ADDRESS ..." }
        ```
    *   **Linux:** If enabling or disabling the service via `systemctl` fails (`ServiceError`).
        ```json
        { "status": "error", "message": "Failed to configure systemd service: Failed to enable systemd service 'bedrock-<server_name>'. Error: Failed to execute operation: No such file or directory" }
        ```
    *   **Windows:** If writing the `autoupdate` flag to the server's JSON config fails (`FileOperationError`).
        ```json
        { "status": "error", "message": "Failed to set autoupdate config: Failed to write config file: /path/to/.config/<server_name>/<server_name>_config.json" }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        { "status": "error", "message": "An unexpected error occurred: <original error message>" }
        ```

#### `curl` Example (Bash - Linux)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"autoupdate": true, "autostart": true}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/service
```

#### PowerShell Example (Windows)

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ autoupdate = $true } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/service" -Headers $headers -Body $body
```

---

## Downloads

### `POST /api/downloads/prune` - Prune Download Cache

Deletes older downloaded server archives (matching `bedrock-server-*.zip`) from a specified directory, keeping a defined number of the newest files based on modification time.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

None.

#### Query Parameters

None.

#### Request Body (`application/json`)

```json
{
    "directory": "/path/to/your/download/cache",
    "keep": 5
}
```
*   **`directory`** (*string*, required): The absolute path to the specific directory containing the download files (e.g., `.zip` files) to be pruned.
*   **`keep`** (*integer*, optional): The number of the most recent files (by modification date) to retain. If omitted, the value from the `DOWNLOAD_KEEP` setting in the Bedrock Server Manager configuration will be used (defaulting to 3 if the setting is missing or invalid).

#### Success Response (`200 OK`)

Indicates that the pruning process completed successfully (even if no files were actually deleted because the count was already below the `keep` threshold).

```json
{
    "status": "success",
    "message": "Download cache pruned successfully for '/path/to/your/download/cache'."
}
```
*(Note: The success message does not currently detail the number of files deleted or kept.)*

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing, not valid JSON, or empty.
        ```json
        {
            "status": "error",
            "message": "Invalid or missing JSON request body."
        }
        ```
    *   If the required `directory` field is missing from the JSON body.
        ```json
        {
            "status": "error",
            "message": "Missing required 'directory' field in request body."
        }
        ```
    *   If the provided `keep` value is not an integer.
        ```json
        {
            "status": "error",
            "message": "Invalid 'keep' value. Must be an integer."
        }
        ```
    *   If the provided `directory` value is an empty string.
        ```json
        {
            "status": "error",
            "message": "Download directory cannot be empty."
        }
        ```
    *   If the resolved `keep` value (from request or settings) is negative or invalid.
        ```json
        {
            "status": "error",
            "message": "Failed to prune downloads: Keep count cannot be negative"
        }
        ```
        *or*
        ```json
        {
             "status": "error",
             "message": "Failed to prune downloads: Invalid DOWNLOAD_KEEP setting ('abc'): could not convert string to int: 'abc'"
        }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid (handled by `@auth_required` decorator).
        ```json
        {
            "error": "Unauthorized",
            "message": "Authentication required."
        }
        ```
        *(Or a more specific message for invalid tokens)*

*   **`500 Internal Server Error`**:
    *   If the specified `directory` does not exist or is not a directory (`DirectoryError`).
        ```json
        {
            "status": "error",
            "message": "Failed to prune downloads: Download directory '/path/does/not/exist' does not exist or is not a directory. Cannot prune."
        }
        ```
    *   If there's an error accessing files within the directory or deleting an old file (e.g., permission denied, disk errors) (`FileOperationError`, `OSError`).
        ```json
        {
            "status": "error",
            "message": "Failed to prune downloads: Failed to delete old server download '/path/to/cache/bedrock-server-old.zip': [Errno 13] Permission denied"
        }
        ```
        *or if multiple deletions were attempted but some failed:*
        ```json
        {
            "status": "error",
            "message": "Failed to prune downloads: Failed to delete all required old downloads (1 failed). Check logs."
        }
        ```
    *   If an unexpected error occurs during the pruning process.
        ```json
        {
            "status": "error",
            "message": "Unexpected error pruning downloads."
        }
        ```

#### `curl` Example (Bash)

```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"directory": "/opt/bedrock-server-manager/.downloads/stable", "keep": 3}' \
     http://<your-manager-host>:<port>/api/downloads/prune
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$body = @{ directory = 'C:\bedrock-server-manager\.downloads\stable'; keep = 3 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/downloads/prune" -Headers $headers -Body $body
```

---

## Server Installation

### `POST /api/server/install` - Install New Server

Creates and installs a new Bedrock server instance. This involves:
1.  Validating the requested server name and version.
2.  Checking if a server with the same name already exists.
3.  Optionally deleting existing data if `overwrite` is true.
4.  Downloading the specified server version (`LATEST`, `PREVIEW`, or a specific version number).
5.  Extracting server files.
6.  Setting up initial configuration files.

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Path Parameters

None.

#### Query Parameters

None.

#### Request Body (`application/json`)

```json
{
    "server_name": "UniqueServerName",
    "server_version": "LATEST",
    "overwrite": false
}
```
*   **Fields:**
    *   `server_name` (*string*, required): The desired unique name for the new server. Should not contain spaces or special characters other than hyphens (`-`) and underscores (`_`). Must be a valid directory name.
    *   `server_version` (*string*, required): The version to install. Valid options are:
        *   `"LATEST"`: Installs the latest stable version.
        *   `"PREVIEW"`: Installs the latest preview version.
        *   Specific version string (e.g., `"1.20.81.01"`): Installs that exact version.
    *   `overwrite` (*boolean*, optional): Defaults to `false`. If `true` and a server directory with the same `server_name` already exists, all existing data for that server (installation, config, backups) will be deleted *before* proceeding with the new installation.

#### Success Responses

*   **`201 Created`**: Returned when a new server is successfully installed (either for the first time or after a successful overwrite).
    ```json
    {
        "status": "success",
        "server_name": "UniqueServerName",
        "version": "1.20.81.01", // Actual version installed
        "message": "Server 'UniqueServerName' installed successfully (Version: 1.20.81.01).",
        "next_step_url": "/server/UniqueServerName/configure_properties?new_install=true" // Relative URL for UI flow
    }
    ```
    *(Note: The `message` might indicate a failure to update the final status config, even on overall success.)*

*   **`200 OK` (Confirmation Needed)**: Returned *only* if a server with the specified `server_name` already exists and the `overwrite` flag in the request is `false`. The client should typically prompt the user based on this response before resending with `overwrite: true`.
    ```json
    {
        "status": "confirm_needed",
        "message": "Server 'UniqueServerName' already exists. Overwrite existing data and reinstall?",
        "server_name": "UniqueServerName",
        "server_version": "LATEST" // Original requested version
    }
    ```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        { "status": "error", "message": "Invalid or missing JSON request body." }
        ```
    *   If `server_name` or `server_version` fields are missing or not strings.
        ```json
        { "status": "error", "message": "Server name (string) is required." }
        ```
         *or*
        ```json
        { "status": "error", "message": "Server version (string) is required." }
        ```
    *   If the `overwrite` field is present but not a boolean (`true` or `false`).
        ```json
        { "status": "error", "message": "'overwrite' flag must be true or false." }
        ```
    *   If the provided `server_name` contains invalid characters or format based on validation rules.
        ```json
        { "status": "error", "message": "Server name format is invalid: Cannot contain spaces." }
        ```
        *(Example validation message)*
    *   If other input validation fails (`TypeError`, `MissingArgumentError`).
        ```json
        { "status": "error", "message": "Invalid input: ..." }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration settings like `BASE_DIR`, `DOWNLOAD_DIR`, `BACKUP_DIR`, or the main config directory cannot be determined (`FileOperationError`).
        ```json
        { "status": "error", "message": "Configuration or File error: BASE_DIR setting is missing or empty in configuration." }
        ```
    *   If `overwrite` is `true` but deleting the existing server data fails (`DirectoryError` or errors from the delete process).
        ```json
        { "status": "error", "message": "Failed to delete existing server data before overwrite: Failed to stop server '<server_name>' before deletion: ... Deletion aborted." }
        ```
    *   If writing the initial server configuration fails (`FileOperationError`).
        ```json
        { "status": "error", "message": "Failed to write initial configuration for server '<server_name>'. Error: ..." }
        ```
    *   If any step of the `download_and_install_server` process fails:
        *   Internet connectivity check (`InternetConnectivityError`).
        *   Download URL lookup (`InternetConnectivityError`, `DownloadExtractError`).
        *   File download (`InternetConnectivityError`, `FileOperationError`).
        *   File extraction (`DownloadExtractError`, `FileOperationError`).
        *   Final config write (version/status) (`FileOperationError`).
        ```json
        { "status": "error", "message": "Server Installation failed: Failed to fetch download page ..." }
        ```
        *or*
        ```json
        { "status": "error", "message": "Server Installation failed: Failed to extract server files ..." }
        ```
        *(Specific error message from the underlying failure will be included)*
    *   If an unexpected error occurs during the process.
        ```json
        { "status": "error", "message": "An unexpected error occurred during installation: <original error message>" }
        ```

#### `curl` Example (Bash)

```bash
# Install new server (will fail if exists unless overwrite: true)
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"server_name": "MySurvivalServer", "server_version": "LATEST", "overwrite": false}' \
     http://<your-manager-host>:<port>/api/server/install

# Force overwrite existing server
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"server_name": "MySurvivalServer", "server_version": "LATEST", "overwrite": true}' \
     http://<your-manager-host>:<port>/api/server/install
```

#### PowerShell Example

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

---

## Task Scheduler

*Note: These endpoints interact with the host OS's native task scheduling system (Linux `cron` or Windows Task Scheduler). Availability and behavior depend entirely on the operating system where the Bedrock Server Manager is running.*

---

### `POST /api/server/{server_name}/cron_scheduler/add` - Add Cron Job (Linux Only)

Adds a new cron job entry to the crontab of the user running the Bedrock Server Manager process. **This endpoint is only functional on Linux systems.**

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Platform

Linux Only.

#### Path Parameters

*   `**server_name**` (*string*, required): Server context for the request (used for logging/authorization), but typically not included directly in the `new_cron_job` string itself unless the command being scheduled requires it (e.g., `/path/to/manager backup --server <server_name>`).

#### Request Body (`application/json`)

```json
{
    "new_cron_job": "0 3 * * * /path/to/bedrock-server-manager backup-all --server MyServer"
}
```
*   **Fields:**
    *   `new_cron_job` (*string*, required): The complete, raw cron job line string to be added. Must not be empty or whitespace only.

#### Success Response (`201 Created`)

Returned when the cron job line is successfully added to the crontab.

```json
{
    "status": "success",
    "message": "Cron job added successfully."
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        { "status": "error", "message": "Invalid or missing JSON request body." }
        ```
    *   If the `new_cron_job` field is missing, not a string, or empty/whitespace only.
        ```json
        { "status": "error", "message": "Cron job string ('new_cron_job') is required in request body." }
        ```
    *   If `server_name` is invalid (e.g. empty) (`MissingArgumentError` from API).
        ```json
        { "status": "error", "message": "Invalid input: Server name cannot be empty." }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`403 Forbidden`**:
    *   If the request is made on a non-Linux operating system.
        ```json
        { "status": "error", "message": "Adding cron jobs is only supported on Linux." }
        ```

*   **`500 Internal Server Error`**:
    *   If the `crontab` command is not found (`CommandNotFoundError`).
        ```json
        { "status": "error", "message": "Error adding cron job: Command 'crontab' not found in system PATH." }
        ```
    *   If reading or writing the crontab file fails (permissions, OS errors) (`ScheduleError`).
        ```json
        { "status": "error", "message": "Error adding cron job: Failed to write updated crontab. Return code: 1. Stderr: ..." }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        { "status": "error", "message": "An unexpected error occurred: <original error message>" }
        ```

#### `curl` Example (Bash)

```bash
# Note: Ensure the command path and server name within the cron string are correct for your setup
CRON_LINE="0 4 * * * /usr/local/bin/bedrock-server-manager restart-server --server MyProdServer"
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d "{\"new_cron_job\": \"$CRON_LINE\"}" \
     "http://<your-manager-host>:<port>/api/server/MyProdServer/cron_scheduler/add"
```

#### PowerShell Example

```powershell
# Note: Linux-only endpoint. This command sends the request but expects the target host to be Linux.
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$cronLine = "0 4 * * * /usr/local/bin/bedrock-server-manager restart-server --server MyProdServer"
$body = @{ new_cron_job = $cronLine } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/MyProdServer/cron_scheduler/add" -Headers $headers -Body $body
```

---

### `POST /api/server/{server_name}/cron_scheduler/modify` - Modify Cron Job (Linux Only)

Modifies an existing cron job entry in the user's crontab by exactly matching the `old_cron_job` string and replacing that entire line with the `new_cron_job` string. **This endpoint is only functional on Linux systems.**

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Platform

Linux Only.

#### Path Parameters

*   `**server_name**` (*string*, required): Server context for the request (used for logging/auth).

#### Request Body (`application/json`)

```json
{
    "old_cron_job": "0 3 * * * /path/to/old_command --args",
    "new_cron_job": "0 4 * * * /path/to/new_command --newargs"
}
```
*   **Fields:**
    *   `old_cron_job` (*string*, required): The exact, complete, existing cron job line string to find and replace. Must not be empty or whitespace only.
    *   `new_cron_job` (*string*, required): The new, complete cron job line string to replace the old one with. Must not be empty or whitespace only.

#### Success Response (`200 OK`)

Returned when the specified `old_cron_job` is found and successfully replaced with `new_cron_job`. Also returned if the old and new strings were identical (no change needed).

```json
{
    "status": "success",
    "message": "Cron job modified successfully."
}
```
*or if no change needed:*
```json
{
    "status": "success",
    "message": "No modification needed, jobs are identical."
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        { "status": "error", "message": "Invalid or missing JSON request body." }
        ```
    *   If `old_cron_job` or `new_cron_job` fields are missing, not strings, or empty/whitespace only.
        ```json
        { "status": "error", "message": "Original cron job string ('old_cron_job') is required." }
        ```
        *or*
        ```json
        { "status": "error", "message": "New cron job string ('new_cron_job') is required." }
        ```
    *   If `server_name` is invalid (e.g. empty).
        ```json
        { "status": "error", "message": "Invalid input: Server name cannot be empty." }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`403 Forbidden`**:
    *   If the request is made on a non-Linux operating system.
        ```json
        { "status": "error", "message": "Modifying cron jobs is only supported on Linux." }
        ```

*   **`404 Not Found`**:
    *   If the exact `old_cron_job` string is not found in the current user's crontab (`ScheduleError` from core).
        ```json
        { "status": "error", "message": "Could not modify: Cron job to modify was not found in the current crontab: '<old_cron_job_string>'" }
        ```

*   **`500 Internal Server Error`**:
    *   If the `crontab` command is not found (`CommandNotFoundError`).
        ```json
        { "status": "error", "message": "Error modifying cron job: Command 'crontab' not found in system PATH." }
        ```
    *   If reading or writing the crontab file fails (permissions, OS errors) (`ScheduleError`).
        ```json
        { "status": "error", "message": "Error modifying cron job: Failed to write modified crontab. Return code: 1. Stderr: ..." }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        { "status": "error", "message": "An unexpected error occurred: <original error message>" }
        ```

#### `curl` Example (Bash)

```bash
OLD_CRON="0 3 * * * /path/to/cmd --old"
NEW_CRON="0 4 * * * /path/to/cmd --new"
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d "{\"old_cron_job\": \"$OLD_CRON\", \"new_cron_job\": \"$NEW_CRON\"}" \
     "http://<your-manager-host>:<port>/api/server/MyServer/cron_scheduler/modify"
```

#### PowerShell Example

```powershell
# Note: Linux-only endpoint. This command sends the request but expects the target host to be Linux.
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$oldCron = "0 3 * * * /path/to/cmd --old"
$newCron = "0 4 * * * /path/to/cmd --new"
$body = @{ old_cron_job = $oldCron; new_cron_job = $newCron } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/MyServer/cron_scheduler/modify" -Headers $headers -Body $body
```

---

### `DELETE /api/server/{server_name}/cron_scheduler/delete` - Delete Cron Job (Linux Only)

Deletes a specific cron job line from the user's crontab by exact string match. **This endpoint is only functional on Linux systems.**

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Platform

Linux Only.

#### Path Parameters

*   `**server_name**` (*string*, required): Server context for the request (used for logging/auth).

#### Query Parameters

*   `**cron_string**` (*string*, required): The exact, complete cron job line string to find and delete. This string MUST be URL-encoded if passed in the query string.

#### Request Body

None.

#### Success Response (`200 OK`)

Returned when the deletion attempt completes. This response is returned even if the specified `cron_string` was not found in the crontab (idempotent behavior).

```json
{
    "status": "success",
    "message": "Cron job deleted successfully (if it existed)."
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `cron_string` query parameter is missing or empty.
        ```json
        { "status": "error", "message": "Cron job string ('cron_string') is required as a query parameter." }
        ```
    *   If `server_name` is invalid (e.g. empty).
        ```json
        { "status": "error", "message": "Invalid input: Server name cannot be empty." }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`403 Forbidden`**:
    *   If the request is made on a non-Linux operating system.
        ```json
        { "status": "error", "message": "Deleting cron jobs is only supported on Linux." }
        ```

*   **`500 Internal Server Error`**:
    *   If the `crontab` command is not found (`CommandNotFoundError`).
        ```json
        { "status": "error", "message": "Error deleting cron job: Command 'crontab' not found in system PATH." }
        ```
    *   If reading or writing the crontab file fails (permissions, OS errors) (`ScheduleError`).
        ```json
        { "status": "error", "message": "Error deleting cron job: Failed to write updated crontab after deletion. Return code: 1. Stderr: ..." }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        { "status": "error", "message": "An unexpected error occurred: <original error message>" }
        ```

#### `curl` Example (Bash)

```bash
# URL Encode the cron string (example using Python)
CRON_STRING_URLENCODED=$(python3 -c 'import urllib.parse; print(urllib.parse.quote_plus("0 4 * * * /path/to/bedrock-server-manager backup-all --server MyProdServer"))')

curl -X DELETE -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     "http://<your-manager-host>:<port>/api/server/MyServer/cron_scheduler/delete?cron_string=${CRON_STRING_URLENCODED}"
```

#### PowerShell Example

```powershell
# Note: Linux-only endpoint. This command sends the request but expects the target host to be Linux.
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
$cronString = "0 4 * * * /path/to/bedrock-server-manager backup-all --server MyProdServer"
# Use appropriate URL encoding method for your PowerShell version/environment
$encodedCronString = [System.Web.HttpUtility]::UrlEncode($cronString) # .NET Framework Example
# $encodedCronString = [uri]::EscapeDataString($cronString) # PowerShell Core Example
$uri = "http://<your-manager-host>:<port>/api/server/MyServer/cron_scheduler/delete?cron_string=$encodedCronString"
Invoke-RestMethod -Method Delete -Uri $uri -Headers $headers
```

---

### `POST /api/server/{server_name}/task_scheduler/add` - Add Windows Task (Windows Only)

Creates a new scheduled task in the Windows Task Scheduler to run a specified Bedrock Server Manager command (e.g., `backup-all`, `update-server`) for the given server. Generates a task XML definition file in the server's configuration subdirectory and imports it using `schtasks.exe`. **This endpoint is only functional on Windows systems.**

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Platform

Windows Only.

#### Path Parameters

*   `**server_name**` (*string*, required): The server context for the task. Used to construct command arguments (e.g., `--server <server_name>`) and the task XML storage path.

#### Request Body (`application/json`)

```json
{
    "command": "backup-all",
    "triggers": [
        {
            "type": "Daily",
            "start": "2024-01-16T03:00:00",
            "interval": 1
        },
        {
            "type": "Weekly",
            "start": "2024-01-20T05:00:00",
            "interval": 2,
            "days": ["Saturday", "Sunday"]
        }
    ]
}
```
*   **Fields:**
    *   `command` (*string*, required): The Bedrock Server Manager command to execute. Must be one of: `"update-server"`, `"backup-all"`, `"start-server"`, `"stop-server"`, `"restart-server"`, `"scan-players"`.
    *   `triggers` (*list[object]*, required): A non-empty list containing one or more trigger definition objects. Each object must contain:
        *   `type` (*string*, required): The type of trigger. Supported types include: `"Daily"`, `"Weekly"`, `"Monthly"`, `"TimeTrigger"` (for once), `"LogonTrigger"`.
        *   `start` (*string*, required for `Daily`, `Weekly`, `Monthly`, `TimeTrigger`): The start date and time in ISO 8601 format (e.g., `YYYY-MM-DDTHH:MM:SS`).
        *   `interval` (*integer*, optional, defaults to 1): Required for `Daily` (days interval) and `Weekly` (weeks interval).
        *   `days` (*list[string|integer]*, required for `Weekly`): List of days (e.g., `"Monday"`, `"Mon"`, `1`).
        *   `months` (*list[string|integer]*, required for `Monthly`): List of months (e.g., `"January"`, `"Jan"`, `1`).
        *   `days_of_month` (*list[string|integer]*, required for `Monthly`): List of day numbers (1-31).

#### Success Response (`201 Created`)

Returned when the task XML is generated and successfully imported into Task Scheduler. Includes the generated task name.

```json
{
    "status": "success",
    "message": "Windows task '<generated_task_name>' created successfully.",
    "created_task_name": "bedrock_MyWinServer_backup-all_20240115_103000"
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        { "status": "error", "message": "Invalid or missing JSON request body." }
        ```
    *   If the `command` field is missing or not one of the allowed values.
        ```json
        { "status": "error", "message": "Invalid or missing 'command'. Must be one of: [...]" }
        ```
    *   If the `triggers` list is missing, empty, or contains invalid trigger objects (missing `type`/`start`, invalid type, invalid interval/day/month format).
        ```json
        { "status": "error", "message": "Missing or invalid 'triggers' list in request body. At least one trigger is required." }
        ```
        *or*
        ```json
        { "status": "error", "message": "Invalid input: Weekly trigger requires a list of 'days'." }
        ```
        *or*
        ```json
        { "status": "error", "message": "Invalid input: Invalid day of week: 'Munday'. Use name, abbreviation, or number 1-7 (Mon-Sun)." }
        ```
    *   If `server_name` is invalid.
        ```json
        { "status": "error", "message": "Invalid input: Server name cannot be empty." }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`403 Forbidden`**:
    *   If the request is made on a non-Windows operating system.
        ```json
        { "status": "error", "message": "Adding Windows tasks is only supported on Windows." }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration like the main config directory or `EXPATH` (path to manager script) cannot be determined (`FileOperationError`).
        ```json
        { "status": "error", "message": "Error creating task: Base configuration directory is not set or available." }
        ```
    *   If creating the task XML file fails (permissions, disk full) (`TaskError`).
        ```json
        { "status": "error", "message": "Error creating task: Failed to write task XML file: [Errno 13] Permission denied: 'C:\\path\\config\\MyServer\\task_....xml'" }
        ```
    *   If the `schtasks` command is not found (`CommandNotFoundError`).
        ```json
        { "status": "error", "message": "Error creating task: Command 'schtasks' not found in system PATH." }
        ```
    *   If importing the generated XML using `schtasks /Create` fails (e.g., access denied, invalid XML content) (`TaskError`).
        ```json
        { "status": "error", "message": "Error creating task: Failed to import task '<task_name>' using 'schtasks /Create'. Return Code: 1. Error: ERROR: Access is denied." }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        { "status": "error", "message": "An unexpected error occurred: <original error message>" }
        ```

#### `curl` Example (Bash)

```bash
# Note: Windows-only endpoint. This command sends the request but expects the target host to be Windows.
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"command": "backup-all", "triggers": [{"type": "Daily", "start": "2024-01-16T02:30:00", "interval": 1}]}' \
     "http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/add"
```

#### PowerShell Example

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

---

### `POST /api/server/{server_name}/task_scheduler/details` - Get Windows Task Details (Windows Only)

Retrieves details (command, triggers) about a specific Windows scheduled task by locating and parsing its associated XML configuration file (stored in the server's configuration subdirectory). **This endpoint is only functional on Windows systems.**

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Platform

Windows Only.

#### Path Parameters

*   `**server_name**` (*string*, required): The server context used to locate the task's XML configuration file.

#### Request Body (`application/json`)

```json
{
    "task_name": "bedrock_MyWinServer_backup-all_..."
}
```
*   **Fields:**
    *   `task_name` (*string*, required): The full name of the task (as registered in Task Scheduler and usually found in the XML's URI element) whose details are to be retrieved.

#### Success Response (`200 OK`)

Returned when the task XML file is found and successfully parsed.

```json
{
    "status": "success",
    "task_details": {
        "command_path": "C:\\path\\to\\manager.exe",
        "command_args": "backup-all --server MyWinServer",
        "base_command": "backup-all",
        "triggers": [
            {
                "type": "Daily",
                "start": "2024-01-16T02:30:00",
                "interval": 1
            }
        ]
    }
}
```
*   **Fields:**
    *   `status`: "success"
    *   `task_details` (*object*): Contains the parsed details:
        *   `command_path` (*string*): Full path to the executable run by the task.
        *   `command_args` (*string*): Full arguments string passed to the executable.
        *   `base_command` (*string*): The inferred primary command action (first part of arguments).
        *   `triggers` (*list[object]*): A list of parsed trigger objects (structure matches the add/modify request format).

#### Error Responses

*   **`400 Bad Request`**:
    *   If the request body is missing or not valid JSON.
        ```json
        { "status": "error", "message": "Invalid or missing JSON request body." }
        ```
    *   If the `task_name` field is missing or not a string.
        ```json
        { "status": "error", "message": "Missing or invalid 'task_name' in request body." }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`403 Forbidden`**:
    *   If the request is made on a non-Windows operating system.
        ```json
        { "status": "error", "message": "Windows Task Scheduler functions are only supported on Windows." }
        ```

*   **`404 Not Found`**:
    *   If the XML configuration file corresponding to the provided `task_name` and `server_name` cannot be found in the expected location (`.config/<server_name>/...xml`).
        ```json
        { "status": "error", "message": "Task configuration not found: Configuration XML file for task '<task_name>' not found." }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration like the main config directory cannot be determined (`FileOperationError`).
        ```json
        { "status": "error", "message": "Configuration or input error: Base configuration directory not set." }
        ```
    *   If the found XML file cannot be parsed (invalid XML, missing essential elements) (`TaskError`).
        ```json
        { "status": "error", "message": "Error parsing task configuration: Error parsing task configuration XML: no element found: line 1, column 0" }
        ```
        *or*
        ```json
        { "status": "error", "message": "Error parsing task configuration: Invalid or incomplete task XML structure: ..." }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        { "status": "error", "message": "An unexpected error occurred: <original error message>" }
        ```

#### `curl` Example (Bash)

```bash
# Note: Windows-only endpoint.
TASK_NAME="bedrock_MyWinServer_backup-all_20240115103000"
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d "{\"task_name\": \"$TASK_NAME\"}" \
     "http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/details"
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$taskName = "bedrock_MyWinServer_backup-all_20240115103000"
$body = @{ task_name = $taskName } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/details" -Headers $headers -Body $body
```

---

### `PUT /api/server/{server_name}/task_scheduler/task/{task_name}` - Modify Windows Task (Windows Only)

Modifies an existing Windows scheduled task. This operation actually **deletes** the task specified by `task_name` (and its associated XML config file) and then **creates a new task** based on the details provided in the request body. The newly created task will have a new, timestamped name. **This endpoint is only functional on Windows systems.**

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Platform

Windows Only.

#### Path Parameters

*   `**server_name**` (*string*, required): The server context for the task.
*   `**task_name**` (*string*, required): The current, full name of the task to be replaced (as registered in Task Scheduler). URL encoding might be needed if the name contains special characters.

#### Request Body (`application/json`)

Same structure as the "Add Windows Task" request body, defining the *new* command and triggers for the replacement task.

```json
{
    "command": "restart-server",
    "triggers": [ { "type": "Weekly", "start": "...", "days": ["Saturday"] } ]
}
```
*   **Fields:** See `POST /api/server/{server_name}/task_scheduler/add` for details on `command` and `triggers`.

#### Success Response (`200 OK`)

Returned when the old task is successfully deleted (or wasn't found) and the new task is successfully created and imported. Includes the name of the newly created task.

```json
{
    "status": "success",
    "message": "Windows task modified successfully.", // API function returns this simple message
    "new_task_name": "bedrock_MyWinServer_restart-server_20240116_090000" // Added by route handler
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `task_name` is missing from the URL path.
        ```
        // Flask routing error, not JSON response
        404 Not Found
        ```
    *   If the request body is missing or not valid JSON.
        ```json
        { "status": "error", "message": "Invalid or missing JSON request body." }
        ```
    *   If validation of the *new* `command` or `triggers` in the request body fails (see "Add Windows Task" errors).
        ```json
        { "status": "error", "message": "Invalid or missing 'command'. Must be one of: [...]" }
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`403 Forbidden`**:
    *   If the request is made on a non-Windows operating system.
        ```json
        { "status": "error", "message": "Modifying Windows tasks is only supported on Windows." }
        ```

*   **`500 Internal Server Error`**:
    *   If deleting the *old* task from Task Scheduler fails (e.g., access denied) (`TaskError`).
        ```json
        { "status": "error", "message": "Error modifying task: Access denied deleting task '<old_task_name>'. Try running as Administrator." }
        ```
    *   If creating or importing the *new* task fails (config errors, XML errors, `schtasks` errors - see "Add Windows Task" errors) (`TaskError`, `FileOperationError`, `CommandNotFoundError`).
        ```json
        { "status": "error", "message": "Error modifying task: Error creating task: Failed to import task '<new_task_name>' using 'schtasks /Create'. ... " }
        ```
    *   If an unexpected error occurs during the delete or create phases.
        ```json
        { "status": "error", "message": "An unexpected error occurred: <original error message>" }
        ```

#### `curl` Example (Bash)

```bash
# Note: Windows-only endpoint.
OLD_TASK_NAME="bedrock_MyWinServer_backup-all_..."
# URL Encode the task name if it contains special characters
# Example using Python (adjust as needed for your shell)
ENCODED_OLD_TASK_NAME=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("'$OLD_TASK_NAME'"))')

curl -X PUT -H "Authorization: Bearer YOUR_JWT_TOKEN" -H "Content-Type: application/json" \
     -d '{"command": "restart-server", "triggers": [{"type": "Weekly", "start": "2024-01-20T05:00:00", "days": ["Saturday"]}]}' \
     "http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/task/${ENCODED_OLD_TASK_NAME}"
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN'; 'Content-Type' = 'application/json' }
$oldTaskName = "bedrock_MyWinServer_backup-all_..."
# URL encode the task name for the URI
$encodedOldTaskName = [uri]::EscapeDataString($oldTaskName) # PowerShell Core example

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

---

### `DELETE /api/server/{server_name}/task_scheduler/task/{task_name}` - Delete Windows Task (Windows Only)

Deletes an existing Windows scheduled task using `schtasks.exe /Delete` and also attempts to delete its corresponding XML configuration file from the server's configuration subdirectory. **This endpoint is only functional on Windows systems.**

This endpoint is exempt from CSRF protection but requires authentication.

#### Authentication

Required (JWT via `Authorization: Bearer <token>` header, or active Web UI session).

#### Platform

Windows Only.

#### Path Parameters

*   `**server_name**` (*string*, required): The server context used to locate the task's XML configuration file.
*   `**task_name**` (*string*, required): The full name of the task to delete (as registered in Task Scheduler). URL encoding may be needed if the name contains special characters.

#### Request Body

None.

#### Success Response (`200 OK`)

Returned when the task deletion from Task Scheduler completes (or if the task was already gone) and the XML file is successfully deleted (or wasn't found).

```json
{
    "status": "success",
    "message": "Task '<task_name>' and its definition file deleted successfully."
}
```

#### Error Responses

*   **`400 Bad Request`**:
    *   If the `task_name` is missing from the URL path.
        ```
        // Flask routing error, not JSON response
        404 Not Found
        ```

*   **`401 Unauthorized`**:
    *   If authentication (JWT or Session) is missing or invalid.
        ```json
        { "error": "Unauthorized", "message": "Authentication required." }
        ```

*   **`403 Forbidden`**:
    *   If the request is made on a non-Windows operating system.
        ```json
        { "status": "error", "message": "Deleting Windows tasks is only supported on Windows." }
        ```

*   **`500 Internal Server Error`**:
    *   If essential configuration like the main config directory cannot be determined (`FileOperationError`).
        ```json
        { "status": "error", "message": "Configuration or input error: Base configuration directory not set." }
        ```
    *   If deleting the task from Task Scheduler using `schtasks /Delete` fails (e.g., access denied) (`TaskError`).
        ```json
        { "status": "error", "message": "Task deletion completed with errors: Scheduler deletion failed (Access denied deleting task '<task_name>'. Try running as Administrator.)" }
        ```
    *   If deleting the task's XML configuration file fails (e.g., permissions) (`FileOperationError`, reported in message).
        ```json
        { "status": "error", "message": "Task deletion completed with errors: XML file deletion failed ([WinError 5] Access is denied: 'C:\\path\\.config\\<server_name>\\<task_name>.xml')" }
        ```
    *   If the `schtasks` command is not found (`CommandNotFoundError`).
        ```json
        { "status": "error", "message": "Error deleting task: Command 'schtasks' not found in system PATH." }
        ```
    *   If an unexpected error occurs during the process.
        ```json
        { "status": "error", "message": "An unexpected error occurred: <original error message>" }
        ```
     *(Note: The API function attempts both deletions; the response aggregates errors if multiple occur.)*

#### `curl` Example (Bash)

```bash
# Note: Windows-only endpoint.
TASK_NAME="bedrock_MyWinServer_backup-all_..."
# URL Encode the task name if it contains special characters
ENCODED_TASK_NAME=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("'$TASK_NAME'"))')
curl -X DELETE -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     "http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/task/${ENCODED_TASK_NAME}"
```

#### PowerShell Example

```powershell
$headers = @{ Authorization = 'Bearer YOUR_JWT_TOKEN' }
$taskName = "bedrock_MyWinServer_backup-all_..."
# URL encode the task name for the URI
$encodedTaskName = [uri]::EscapeDataString($taskName) # PowerShell Core example
$uri = "http://<your-manager-host>:<port>/api/server/MyWinServer/task_scheduler/task/$encodedTaskName"
Invoke-RestMethod -Method Delete -Uri $uri -Headers $headers
```

---
