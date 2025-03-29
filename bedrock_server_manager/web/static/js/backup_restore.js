// bedrock-server-manager/bedrock_server_manager/web/static/js/backup_restore.js

// Depends on: utils.js (showStatusMessage, sendServerActionRequest)

/**
 * Triggers a backup operation for the specified server and type (e.g., 'world', 'config', 'all').
 * Prompts for confirmation if backupType is 'all'.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} backupType The type of backup ('world', 'config', 'all').
 */
function triggerBackup(buttonElement, serverName, backupType) {
    // Log function entry with parameters
    console.log(`triggerBackup called - Server: ${serverName}, Type: ${backupType}, Button:`, buttonElement);

    // Specific confirmation for 'all' type backup due to potential size/time
    if (backupType === 'all') {
        console.log("Backup type is 'all', prompting for confirmation.");
        if (!confirm(`Performing a full backup (world + config) for '${serverName}'. This might take a moment. Continue?`)) {
            // Log cancellation and inform user
            console.log("Full backup cancelled by user.");
            showStatusMessage('Full backup cancelled.', 'info');
            return; // Abort if user cancels
        }
        console.log("Confirmation received for 'all' backup.");
    }

    // Construct the request body with the backup type
    const requestBody = {
        backup_type: backupType
    };
    console.log("Constructed request body for backup:", requestBody);

    // Call the generic action helper to send the request
    console.log("Calling sendServerActionRequest for backup/action...");
    sendServerActionRequest(serverName, 'backup/action', 'POST', requestBody, buttonElement);
    // Note: Execution continues immediately after this async call is initiated.
    console.log("Returned from initiating sendServerActionRequest call for backup (operation running asynchronously).");
}

/**
 * Triggers a backup operation for a specific config file.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} filename The specific config file to backup (relative to server config dir).
 */
function triggerSpecificConfigBackup(buttonElement, serverName, filename) {
    // Log function entry with parameters
    console.log(`triggerSpecificConfigBackup called - Server: ${serverName}, Filename: ${filename}, Button:`, buttonElement);

    // Validate filename presence
    if (!filename) {
        console.error("triggerSpecificConfigBackup called without a filename!");
        showStatusMessage("Internal error: No filename specified for backup.", "error");
        return;
    }

    // Construct the request body with backup type 'config' and the specific file
    const requestBody = {
        backup_type: 'config',
        file_to_backup: filename
    };
    console.log("Constructed request body for specific config backup:", requestBody);

    // Call the generic action helper to send the request
    console.log("Calling sendServerActionRequest for backup/action (specific config)...");
    sendServerActionRequest(serverName, 'backup/action', 'POST', requestBody, buttonElement);
    console.log("Returned from initiating sendServerActionRequest call for specific config backup (async).");
}

/**
 * Triggers a restoration operation from a specific backup file after confirmation.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} restoreType 'world' or 'config' (determines where to restore).
 * @param {string} backupFile The filename of the backup archive to restore.
 */
function triggerRestore(buttonElement, serverName, restoreType, backupFile) {
    // Log function entry with parameters
    console.log(`triggerRestore called - Server: ${serverName}, Type: ${restoreType}, File: ${backupFile}, Button:`, buttonElement);

    // Validate presence of backupFile and restoreType
    if (!backupFile) {
        console.error("triggerRestore called without backupFile!");
        showStatusMessage("Internal error: No backup file specified for restore.", "error");
        return;
    }
    if (!restoreType || (restoreType !== 'world' && restoreType !== 'config')) { // Added type check
        console.error(`triggerRestore called with invalid restoreType: ${restoreType}`);
        showStatusMessage(`Internal error: Invalid restore type specified (${restoreType}).`, "error");
        return;
    }

    // Confirmation dialog to prevent accidental overwrite
    console.log("Prompting user for restore confirmation.");
    if (!confirm(`Are you sure you want to restore '${backupFile}' for server '${serverName}'?\nThis will OVERWRITE current ${restoreType} data!`)) {
        console.log("Restore cancelled by user.");
        showStatusMessage('Restore operation cancelled.', 'info');
        return; // Abort if user cancels
    }
    console.log("Restore confirmed by user.");

    // Construct the request body with restore type and filename
    const requestBody = {
        restore_type: restoreType,
        backup_file: backupFile
    };
    console.log("Constructed request body for restore:", requestBody);

    // Call the generic action helper for the restore action
    console.log("Calling sendServerActionRequest for restore/action...");
    sendServerActionRequest(serverName, 'restore/action', 'POST', requestBody, buttonElement);
    console.log("Returned from initiating sendServerActionRequest call for restore (async).");
}

/**
 * Triggers restoring ALL available backup files for a server after confirmation.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 */
function triggerRestoreAll(buttonElement, serverName) {
    // Log function entry
    console.log(`triggerRestoreAll called for server: ${serverName}, Button:`, buttonElement);

    // Confirmation dialog for restoring all (potentially dangerous)
    console.log("Prompting user for Restore All confirmation.");
    if (!confirm(`Are you sure you want to restore ALL latest backup files for server '${serverName}'?\nThis will OVERWRITE current world and config files with the newest available backups.`)) {
        console.log("Restore All cancelled by user.");
        showStatusMessage('Restore All operation cancelled.', 'info');
        return; // Abort if user cancels
    }
    console.log("Restore All confirmed by user.");

    // Call the generic action helper for the restore all action (no body needed)
    console.log("Calling sendServerActionRequest for restore/all...");
    sendServerActionRequest(serverName, 'restore/all', 'POST', null, buttonElement);
    console.log("Returned from initiating sendServerActionRequest call for restore all (async).");
}