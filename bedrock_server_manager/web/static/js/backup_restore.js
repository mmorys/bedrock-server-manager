// bedrock-server-manager/web/static/js/backup_restore.js
/**
 * @fileoverview Frontend JavaScript functions for triggering server backup and restore operations.
 * These functions typically gather necessary info, show confirmation dialogs, and
 * then call `sendServerActionRequest` (from utils.js) to interact with the backend API.
 * Depends on functions defined in utils.js (showStatusMessage, sendServerActionRequest).
 */

// Ensure utils.js is loaded before this script
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("Error: Missing required functions from utils.js. Ensure utils.js is loaded first.");
    // Optionally display an error to the user on the page itself
}

/**
 * Initiates a backup operation via the API based on the specified type.
 * Shows a confirmation prompt for 'all' type backups.
 *
 * @param {HTMLButtonElement} buttonElement - The button element clicked, used for disabling during the request.
 * @param {string} serverName - The name of the server to back up.
 * @param {string} backupType - The type of backup requested ('world', 'config', 'all'). Note: 'config' type here implies backing up *all* standard config files unless `triggerSpecificConfigBackup` is used.
 */
function triggerBackup(buttonElement, serverName, backupType) {
    const functionName = 'triggerBackup';
    console.log(`${functionName}: Initiated. Server: '${serverName}', Type: '${backupType}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Confirmation for potentially long/impactful operations ---
    if (backupType === 'all') {
        console.debug(`${functionName}: Backup type is 'all'. Prompting user for confirmation.`);
        const confirmationMessage = `Perform a full backup (world + standard config files) for server '${serverName}'? This may take a few moments.`;
        if (!confirm(confirmationMessage)) {
            console.log(`${functionName}: Full backup cancelled by user.`);
            showStatusMessage('Full backup cancelled.', 'info');
            return; // Abort operation
        }
        console.log(`${functionName}: User confirmed 'all' backup.`);
    }
    // Add confirmation for 'world' backup too? It can also take time.
    // else if (backupType === 'world') { ... confirm(...) ... }

    // --- Prepare API Request ---
    const requestBody = {
        backup_type: backupType
        // 'file_to_backup' is NOT included here; this triggers backup of the type specified ('world' or 'all')
        // or implicitly backs up standard configs if backupType is 'config' without a specific file.
        // The backend API handler for 'config' without a file needs to handle this case if desired.
        // Usually, the UI would call triggerSpecificConfigBackup for individual files.
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Call API Helper ---
    const apiUrl = `/api/server/${serverName}/backup/action`;
    console.log(`${functionName}: Calling sendServerActionRequest to ${apiUrl} for backup type '${backupType}'...`);
    // sendServerActionRequest handles disabling button, showing status messages, and handling response
    sendServerActionRequest(serverName, 'backup/action', 'POST', requestBody, buttonElement);

    console.log(`${functionName}: Backup request initiated (asynchronous).`);
}

/**
 * Initiates a backup operation for a *specific* configuration file via the API.
 *
 * @param {HTMLButtonElement} buttonElement - The button element clicked.
 * @param {string} serverName - The name of the server.
 * @param {string} filename - The relative path or name of the specific configuration file to back up (e.g., "server.properties").
 */
function triggerSpecificConfigBackup(buttonElement, serverName, filename) {
    const functionName = 'triggerSpecificConfigBackup';
    console.log(`${functionName}: Initiated. Server: '${serverName}', File: '${filename}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Input Validation ---
    if (!filename || typeof filename !== 'string' || !filename.trim()) {
        const errorMsg = "Internal error: No filename provided for specific config backup.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }
    const trimmedFilename = filename.trim();

    // --- Confirmation (Optional but recommended) ---
    // const confirmationMessage = `Back up the specific configuration file '${trimmedFilename}' for server '${serverName}'?`;
    // if (!confirm(confirmationMessage)) {
    //     console.log(`${functionName}: Specific config backup cancelled by user.`);
    //     showStatusMessage(`Backup for '${trimmedFilename}' cancelled.`, 'info');
    //     return;
    // }
    // console.log(`${functionName}: User confirmed backup for '${trimmedFilename}'.`);

    // --- Prepare API Request ---
    const requestBody = {
        backup_type: 'config', // Specify config type
        file_to_backup: trimmedFilename // Provide the specific filename
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Call API Helper ---
    const apiUrl = `/api/server/${serverName}/backup/action`; // Same endpoint, body specifies action
    console.log(`${functionName}: Calling sendServerActionRequest to ${apiUrl} for specific config backup ('${trimmedFilename}')...`);
    sendServerActionRequest(serverName, 'backup/action', 'POST', requestBody, buttonElement);

    console.log(`${functionName}: Specific config backup request initiated (asynchronous).`);
}

/**
 * Initiates a restore operation for a specific backup file via the API, after user confirmation.
 *
 * @param {HTMLButtonElement} buttonElement - The button element clicked.
 * @param {string} serverName - The name of the server to restore to.
 * @param {string} restoreType - The type of restore ('world' or 'config').
 * @param {string} backupFilePath - The full path (as known by the server/backend) of the backup file to restore.
 */
function triggerRestore(buttonElement, serverName, restoreType, backupFilePath) {
    const functionName = 'triggerRestore';
    console.log(`${functionName}: Initiated. Server: '${serverName}', Type: '${restoreType}', File: '${backupFilePath}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Input Validation ---
    if (!backupFilePath || typeof backupFilePath !== 'string' || !backupFilePath.trim()) {
        const errorMsg = "Internal error: No backup file path provided for restore.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }
    const trimmedBackupFilePath = backupFilePath.trim();
    const backupFilename = trimmedBackupFilePath.split(/[\\/]/).pop(); // Extract filename for messages

    const validTypes = ['world', 'config'];
    if (!restoreType || !validTypes.includes(restoreType.toLowerCase())) {
        const errorMsg = `Internal error: Invalid restore type '${restoreType}'.`;
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }
    const normalizedRestoreType = restoreType.toLowerCase();

    // --- Confirmation ---
    console.debug(`${functionName}: Prompting user for restore confirmation.`);
    const confirmationMessage = `Are you sure you want to restore backup '${backupFilename}' for server '${serverName}'?\n\nThis will OVERWRITE the current server ${normalizedRestoreType} data!`;
    if (!confirm(confirmationMessage)) {
        console.log(`${functionName}: Restore operation cancelled by user.`);
        showStatusMessage('Restore operation cancelled.', 'info');
        return; // Abort if user cancels
    }
    console.log(`${functionName}: User confirmed restore operation.`);

    // --- Prepare API Request ---
    const requestBody = {
        restore_type: normalizedRestoreType,
        backup_file: trimmedBackupFilePath // Send the full path
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Call API Helper ---
    const apiUrl = `/api/server/${serverName}/restore/action`;
    console.log(`${functionName}: Calling sendServerActionRequest to ${apiUrl} for restore type '${normalizedRestoreType}'...`);
    sendServerActionRequest(serverName, 'restore/action', 'POST', requestBody, buttonElement);

    console.log(`${functionName}: Restore request initiated (asynchronous).`);
}

/**
 * Initiates restoring ALL latest backup files (world, configs) for a server via the API,
 * after user confirmation.
 *
 * @param {HTMLButtonElement} buttonElement - The button element clicked.
 * @param {string} serverName - The name of the server to restore.
 */
function triggerRestoreAll(buttonElement, serverName) {
    const functionName = 'triggerRestoreAll';
    console.log(`${functionName}: Initiated for server: '${serverName}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Confirmation ---
    console.debug(`${functionName}: Prompting user for Restore All confirmation.`);
    const confirmationMessage = `Are you sure you want to restore ALL latest backups for server '${serverName}'?\n\nThis will OVERWRITE the current world and configuration files!`;
    if (!confirm(confirmationMessage)) {
        console.log(`${functionName}: Restore All operation cancelled by user.`);
        showStatusMessage('Restore All operation cancelled.', 'info');
        return; // Abort if user cancels
    }
    console.log(`${functionName}: User confirmed Restore All operation.`);

    // --- Call API Helper ---
    // No request body needed for this specific action
    const apiUrl = `/api/server/${serverName}/restore/all`;
    console.log(`${functionName}: Calling sendServerActionRequest to ${apiUrl} for restore all...`);
    sendServerActionRequest(serverName, 'restore/all', 'POST', null, buttonElement);

    console.log(`${functionName}: Restore All request initiated (asynchronous).`);
}