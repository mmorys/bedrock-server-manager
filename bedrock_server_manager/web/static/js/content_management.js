// bedrock-server-manager/bedrock_server_manager/web/static/js/content_management.js
/**
 * @fileoverview Frontend JavaScript functions for triggering content installation
 * (worlds and addons) via API calls based on user interaction.
 * Depends on functions defined in utils.js (showStatusMessage, sendServerActionRequest).
 */

// Ensure utils.js is loaded before this script
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("Error: Missing required functions from utils.js. Ensure utils.js is loaded first.");
    // Optionally display an error to the user on the page itself
}

/**
 * Handles the user clicking an 'Install World' button.
 * Prompts for confirmation (warning about overwrites) and then calls the API
 * endpoint to install the specified world file.
 *
 * @param {HTMLButtonElement} buttonElement - The 'Install' button element that was clicked.
 * @param {string} serverName - The name of the target server.
 * @param {string} worldFilePath - The full path or unique identifier of the .mcworld file
 *                                (as provided by the backend/template).
 */
function triggerWorldInstall(buttonElement, serverName, worldFilePath) {
    const functionName = 'triggerWorldInstall';
    console.log(`${functionName}: Initiated. Server: '${serverName}', File: '${worldFilePath}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Input Validation ---
    if (!worldFilePath || typeof worldFilePath !== 'string' || !worldFilePath.trim()) {
        const errorMsg = "Internal error: World file path is missing or invalid.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }
    const trimmedWorldFilePath = worldFilePath.trim();

    // Extract filename for user messages (handles / and \ separators)
    const filenameForDisplay = trimmedWorldFilePath.split(/[\\/]/).pop() || trimmedWorldFilePath;
    console.debug(`${functionName}: Extracted filename for display: '${filenameForDisplay}'`);

    // --- Confirmation ---
    console.debug(`${functionName}: Prompting user for world install confirmation.`);
    const confirmationMessage = `Install world '${filenameForDisplay}' for server '${serverName}'?\n\n` +
                                `WARNING: This will permanently REPLACE the current world data for this server! Continue?`;
    if (!confirm(confirmationMessage)) {
        console.log(`${functionName}: World installation cancelled by user.`);
        showStatusMessage('World installation cancelled.', 'info');
        return; // Abort if user cancels
    }
    console.log(`${functionName}: User confirmed world installation.`);

    // --- Prepare API Request ---
    const requestBody = {
        filename: trimmedWorldFilePath // Send the path/identifier provided by the backend
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Call API Helper ---
    const apiUrl = `/api/server/${serverName}/world/install`;
    console.log(`${functionName}: Calling sendServerActionRequest to ${apiUrl}...`);
    // sendServerActionRequest handles button disabling, status messages, and response processing
    sendServerActionRequest(null, apiUrl, 'POST', requestBody, buttonElement);

    console.log(`${functionName}: World install request initiated (asynchronous).`);
}


/**
 * Handles the user clicking an 'Install Addon' button.
 * Prompts for confirmation and then calls the API endpoint to install the
 * specified addon file (.mcaddon or .mcpack).
 *
 * @param {HTMLButtonElement} buttonElement - The 'Install' button element that was clicked.
 * @param {string} serverName - The name of the target server.
 * @param {string} addonFilePath - The full path or unique identifier of the addon file
 *                                (as provided by the backend/template).
 */
function triggerAddonInstall(buttonElement, serverName, addonFilePath) {
    const functionName = 'triggerAddonInstall';
    console.log(`${functionName}: Initiated. Server: '${serverName}', File: '${addonFilePath}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Input Validation ---
    if (!addonFilePath || typeof addonFilePath !== 'string' || !addonFilePath.trim()) {
        const errorMsg = "Internal error: Addon file path is missing or invalid.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }
    const trimmedAddonFilePath = addonFilePath.trim();

    // Extract filename for user messages
    const filenameForDisplay = trimmedAddonFilePath.split(/[\\/]/).pop() || trimmedAddonFilePath;
    console.debug(`${functionName}: Extracted filename for display: '${filenameForDisplay}'`);

    // --- Confirmation ---
    console.debug(`${functionName}: Prompting user for addon install confirmation.`);
    // Confirmation message is less severe than world install, but still good practice
    const confirmationMessage = `Install addon '${filenameForDisplay}' for server '${serverName}'?`;
    if (!confirm(confirmationMessage)) {
        console.log(`${functionName}: Addon installation cancelled by user.`);
        showStatusMessage('Addon installation cancelled.', 'info');
        return; // Abort if user cancels
    }
    console.log(`${functionName}: User confirmed addon installation.`);

    // --- Prepare API Request ---
    const requestBody = {
        filename: trimmedAddonFilePath // Send the path/identifier provided by the backend
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Call API Helper ---
    const apiUrl = `/api/server/${serverName}/addon/install`;
    console.log(`${functionName}: Calling sendServerActionRequest to ${apiUrl}...`);
    sendServerActionRequest(null, apiUrl, 'POST', requestBody, buttonElement);

    console.log(`${functionName}: Addon install request initiated (asynchronous).`);
}