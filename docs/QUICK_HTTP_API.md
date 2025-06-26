﻿﻿﻿﻿﻿<div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg" alt="BSM Logo" width="150">
</div>

# Bedrock Server Manager - HTTP API Quick Reference

This document provides a concise overview of the HTTP API endpoints for the Bedrock Server Manager.

**Base URL:** `http://<your-manager-host>:<port>` (Default port: 11325)
**Content-Type:** Use `application/json` for request bodies (POST/PUT).
**Authentication:** Most endpoints require a JWT Bearer token in the `Authorization` header, obtained via `/api/login`.

---

## Authentication

### `POST /api/login`

Authenticates using username/password and returns a JWT.
*   **Auth:** None
*   **Request Body:**
    ```json
    {
        "username": "your_username",
        "password": "your_plain_text_password"
    }
    ```
*   **Success:** Returns `{"access_token": "YOUR_JWT_TOKEN"}`.

---

## Application Information

### `GET /api/info`

Retrieves the OS type and application version.
*   **Auth:** None
*   **Success:** Returns `{"status": "success", "data": {"os_type": "...", "app_version": "..."}}`.

---

## Server Information

### `GET /api/servers`

Lists all detected server instances with their configured status and version.
*   **Auth:** Required
*   **Success:** Returns `{"status": "success", "servers": [{"name": "...", "status": "...", "version": "..."}, ...]}`. May include a `message` field if partial errors occurred.

### `GET /api/server/{server_name}/status`

Checks if the server process is running.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Success:** Returns `{"status": "success", "is_running": true|false}`.

### `GET /api/server/{server_name}/config_status`

Gets the status stored in the manager's config file for the server.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Success:** Returns `{"status": "success", "config_status": "..."}`.

### `GET /api/server/{server_name}/version`

Gets the installed version stored in the manager's config file.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Success:** Returns `{"status": "success", "installed_version": "..."}`.

### `GET /api/server/{server_name}/validate`

Checks if the server directory and executable exist.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Success (200 OK):** `{"status": "success", "message": "Server '...' exists and is valid."}`.
*   **Failure (404 Not Found):** Server directory or executable missing. `{"status": "error", "message": "..."}`.

### `GET /api/server/{server_name}/process_info`

Gets runtime process info (PID, CPU, Mem, Uptime) if running.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Success:** Returns `{"status": "success", "process_info": {...} | null}`.
    *   *Note:* CPU % is relative to the previous check. First check shows 0%.

### `GET /api/server/{server_name}/world/icon`

Serves the server's `world_icon.jpeg`. Fallback to default application icon on error/not found.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Success:** JPEG image data.

---

## Server Actions

### `POST /api/server/{server_name}/start`

Starts the specified server instance. (No request body).
*   **Auth:** Required
*   **Path Params:** `server_name` (string)

### `POST /api/server/{server_name}/stop`

Stops the specified server instance (graceful if possible).
*   **Auth:** Required
*   **Path Params:** `server_name` (string)

### `POST /api/server/{server_name}/restart`

Restarts the specified server instance (stops if running, then starts).
*   **Auth:** Required
*   **Path Params:** `server_name` (string)

### `POST /api/server/{server_name}/send_command`

Sends a command to the running server's console.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:** `{"command": "your server command"}`

### `POST /api/server/{server_name}/update`

Checks for and installs the latest/preview/specific version for the server based on its config.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)

### `DELETE /api/server/{server_name}/delete`

**Irreversibly deletes** the server instance (installation, config, backups).
*   **Auth:** Required
*   **Path Params:** `server_name` (string)

---

## Backup & Restore

### `POST /api/server/{server_name}/backups/prune`

Deletes old backups for the server. Number to keep is based on `BACKUP_KEEP` setting.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:** None (parameter `keep` from body is not used).

### `GET /api/server/{server_name}/backups/list/{backup_type}`

Lists backup **filenames (basenames)** for a server by type.
*   **Auth:** Required
*   **Path Params:** `server_name` (required), `backup_type` (required: "world" or "config")
*   **Success (200 OK):** Returns `{"status": "success", "backups": ["filename1.ext", ...]}`.

### `POST /api/server/{server_name}/backup/action`

Triggers a backup.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:**
    *   `{"backup_type": "world"}`
    *   `{"backup_type": "config", "file_to_backup": "server.properties|allowlist.json|permissions.json"}`
    *   `{"backup_type": "all"}` (backs up world and all standard config files)

### `POST /api/server/{server_name}/restore/action`

**Overwrites current files** to restore from backup.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:**
    *   `{"restore_type": "world", "backup_file": "relative/path/to/world_backup.mcworld"}`
    *   `{"restore_type": "config", "backup_file": "relative/path/to/config_backup.json"}`
    *   `{"restore_type": "all"}` (restores world and standard configs from latest backups)

---

## World & Addon Management

### `GET /api/content/worlds`

Lists world **filenames (basenames)** from `CONTENT_DIR/worlds` (e.g., `.mcworld`).
*   **Auth:** Required
*   **Success (200 OK):** Returns `{"status": "success", "files": ["world1.mcworld", ...], "message": "..." (optional)}`.
*   **Errors:** 401 (unauthorized), 500 (CONTENT_DIR not set or `CONTENT_DIR/worlds` dir not found, file access error).

### `GET /api/content/addons`

Lists addon **filenames (basenames)** from `CONTENT_DIR/addons` (e.g., `.mcpack`, `.mcaddon`).
*   **Auth:** Required
*   **Success (200 OK):** Returns `{"status": "success", "files": ["addon1.mcpack", ...], "message": "..." (optional)}`.
*   **Errors:** 401 (unauthorized), 500 (CONTENT_DIR not set or `CONTENT_DIR/addons` dir not found, file access error).

### `POST /api/server/{server_name}/world/export`

Exports the server's current world to a `.mcworld` file inside the `CONTENT_DIR/worlds` directory.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Success:** `{"status": "success", "message": "...", "export_file": "/full/path/to/export.mcworld"}`.

### `DELETE /api/server/{server_name}/world/reset`

Resets the server's active world directory.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Success:** `{"status": "success", "message": "World for server '...' reset successfully."}`.

### `POST /api/server/{server_name}/world/install`

**Overwrites current world** to install a `.mcworld` file from the manager's `content/worlds` directory.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:** `{"filename": "relative/path/to/world.mcworld"}` (relative to `CONTENT_DIR/worlds`)

### `POST /api/server/{server_name}/addon/install`

Installs a `.mcpack` or `.mcaddon` from the manager's `content/addons` directory into the server's world.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:** `{"filename": "relative/path/to/addon.mcpack"}` (relative to `CONTENT_DIR/addons`)

---

## Player Management

### `POST /api/players/scan`

Scans all server logs for player connections and updates the central `players.json`.
*   **Auth:** Required
*   **Success:** `{"status": "success", "players_found": true|false, "message": "..."}`.

### `POST /api/players/add`

Adds/updates players in the global `players.json`.
*   **Auth:** Required
*   **Request Body (JSON):** `{"players": ["Name1:XUID1", "Name2:XUID2", ...]}`
*   **Success (200 OK):** Returns `{"status": "success", "message": "Players added successfully."}`.

### `GET /api/players/get`

Retrieves a list of all known players from `players.json`.
*   **Auth:** Required
*   **Success:** Returns `{"status": "success", "players": [{"name": "...", "xuid": "..."}, ...], "message": "..." (optional)}`.

### `GET /api/server/{server_name}/allowlist/get`

Gets the content of the server's `allowlist.json`.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Success:** Returns `{"status": "success", "existing_players": [...]}`.

### `POST /api/server/{server_name}/allowlist/add`

Adds players to the server's `allowlist.json`.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:** `{"players": ["Player1", "Player2"], "ignoresPlayerLimit": false|true}`

### `DELETE /api/server/{server_name}/allowlist/remove`

Removes one or more players (case-insensitive) from the server's allowlist.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:** `{"players": ["player1", "player2", ...]}`
*   **Success:** `{"status": "success", "message": "...", "details": {"removed": [...], "not_found": [...]}}`.

### `PUT /api/server/{server_name}/permissions/set`

Updates player permission levels in `permissions.json`.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:** `{"permissions": {"XUID_string": "visitor|member|operator", ...}}`

### `GET /api/server/{server_name}/permissions/get`

Retrieves player permissions from `permissions.json`, enriched with names from global `players.json`.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Success:** `{"status": "success", "data": {"permissions": [{"xuid": "...", "name": "...", "permission_level": "..."}]}, "message": "..." (optional)}`.

---

## Configuration

### `POST /api/server/{server_name}/properties/set`

Updates specified allowed keys in `server.properties`.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:** `{"property-key": "new-value", ...}` (See full docs for allowed keys).

### `GET /api/server/{server_name}/properties/get`

Retrieves the parsed `server.properties` for the specified server.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Success:** Returns `{"status": "success", "properties": {"key": "value", ...}}`.

### `POST /api/server/{server_name}/service/update`

Configures OS-specific service settings.
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body (Linux):** `{"autoupdate": boolean, "autostart": boolean}`
*   **Request Body (Windows):** `{"autoupdate": boolean}`

---

## Downloads

### `POST /api/downloads/prune`

Deletes old downloaded server archives from a specified *relative* directory within `DOWNLOAD_DIR`.
*   **Auth:** Required
*   **Request Body:** `{"directory": "stable|preview", "keep": number (optional, defaults to DOWNLOAD_KEEP setting)}`

---

## Server Installation

### `POST /api/server/install`

Installs a new server instance.
*   **Auth:** Required
*   **Request Body:** `{"server_name": "NewServer", "server_version": "LATEST|PREVIEW|1.x.y.z", "overwrite": false|true}`
*   **Success (New/Overwrite):** 201 Created `{"status": "success", ...}`
*   **Confirmation Needed (Exists, overwrite=false):** 200 OK `{"status": "confirm_needed", ...}`

---

## Task Scheduler (OS Specific)

### Linux (Cron)

#### `POST /api/server/{server_name}/cron_scheduler/add`

Adds a raw cron job line. (Linux Only)
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:** `{"new_cron_job": "0 3 * * * /path/to/cmd --args"}`

#### `POST /api/server/{server_name}/cron_scheduler/modify`

Replaces an existing cron job line. (Linux Only)
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:** `{"old_cron_job": "exact old string", "new_cron_job": "replacement string"}`

#### `DELETE /api/server/{server_name}/cron_scheduler/delete`

Deletes a cron job line. (Linux Only)
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Query Params:** `cron_string` (URL-encoded exact string)

### Windows (Task Scheduler)

#### `POST /api/server/{server_name}/task_scheduler/add`

Creates a new Windows scheduled task. (Windows Only)
*   **Auth:** Required
*   **Path Params:** `server_name` (string)
*   **Request Body:** `{"command": "backup-all|update-server|...", "triggers": [{"type": "Daily|Weekly|...", "start": "ISO8601", ...}]}` (See full docs for trigger details).

#### `PUT /api/server/{server_name}/task_scheduler/task/{task_name}`

Modifies a task by deleting old and creating new. (Windows Only)
*   **Auth:** Required
*   **Path Params:** `server_name` (string), `task_name` (string, URL-encoded if needed)
*   **Request Body:** Same as "Add Windows Task".
*   **Success:** `{"status": "success", "new_task_name": "..."}`.

#### `DELETE /api/server/{server_name}/task_scheduler/task/{task_name}`

Deletes a Windows scheduled task. (Windows Only)
*   **Auth:** Required
*   **Path Params:** `server_name` (string), `task_name` (string, URL-encoded if needed)

---

## Plugin Management API

### `GET /api/plugins`

Retrieves status, version, and description of all discovered plugins.
*   **Auth:** Required
*   **Success:** `{"status": "success", "plugins": {"PluginName": {"enabled": ..., "version": ..., "description": ...}}}`.

### `POST /api/plugins/{plugin_name}`

Enables or disables a specific plugin.
*   **Auth:** Required
*   **Path Params:** `plugin_name` (string)
*   **Request Body:** `{"enabled": true|false}`
*   **Success:** `{"status": "success", "message": "Plugin '...' has been enabled/disabled. Reload plugins..."}`.

### `POST /api/plugins/reload`

Triggers a full reload of all plugins.
*   **Auth:** Required
*   **Success:** `{"status": "success", "message": "Plugins have been reloaded successfully."}`.

### `POST /api/plugins/trigger_event`

Allows external triggering of a custom plugin event.
*   **Auth:** Required
*   **Request Body:** `{"event_name": "my:event", "payload": {"key": "value"}}`
*   **Success:** `{"status": "success", "message": "Event '...' triggered."}`.

---

*For detailed error responses and more information, please refer to the full `HTTP_API.md` documentation.*
