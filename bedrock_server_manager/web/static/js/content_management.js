// bedrock-server-manager/bedrock_server_manager/web/static/js/content_management.js

// Depends on: utils.js (showStatusMessage, sendServerActionRequest)

/**
 * Triggers the installation of a specific world file after confirmation.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} worldFile The full path or identifier of the world file to install (from backend).
 */
function triggerWorldInstall(buttonElement, serverName, worldFile) {
    // Log function entry
    console.log(`triggerWorldInstall called - Server: ${serverName}, File: ${worldFile}, Button:`, buttonElement);

    // Validate presence of worldFile
    if (!worldFile) {
        console.error("triggerWorldInstall called without worldFile!");
        showStatusMessage("Internal error: No world file specified for install.", "error");
        return;
    }

    // Extract filename for display messages (handle both / and \ separators)
    const worldFilenameForDisplay = worldFile.includes('\\') ? worldFile.substring(worldFile.lastIndexOf('\\') + 1) :
                                   worldFile.includes('/') ? worldFile.substring(worldFile.lastIndexOf('/') + 1) : worldFile;
    console.log(`Extracted filename for display: ${worldFilenameForDisplay}`);

    // Confirmation dialog with clear warning about overwriting
    console.log("Prompting user for world install confirmation.");
    if (!confirm(`Install world '${worldFilenameForDisplay}' for server '${serverName}'?\n\nWARNING: This will REPLACE the current world directory if one exists! Continue?`)) {
        console.log("World install cancelled by user.");
        showStatusMessage('World installation cancelled.', 'info');
        return; // Abort if user cancels
    }
    console.log("World install confirmed by user.");

    // Construct the request body containing the world file identifier
    const requestBody = {
        filename: worldFile // Send the full path/identifier received from the backend/onclick
    };
    console.log("Constructed request body for world install:", requestBody);

    // Call the action helper, targeting the specific API endpoint (absolute path)
    // Pass null for serverName because actionPath starts with /
    console.log("Calling sendServerActionRequest for world install API...");
    sendServerActionRequest(null, `/api/server/${serverName}/world/install`, 'POST', requestBody, buttonElement);
    console.log("Returned from initiating sendServerActionRequest call for world install (async).");
}


/**
 * Triggers the installation of a specific addon file after confirmation.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} addonFile The full path or identifier of the addon file to install (from backend).
 */
function triggerAddonInstall(buttonElement, serverName, addonFile) {
    // Log function entry
    console.log(`triggerAddonInstall called - Server: ${serverName}, File: ${addonFile}, Button:`, buttonElement);

    // Validate presence of addonFile
    if (!addonFile) {
        console.error("triggerAddonInstall called without addonFile!");
        showStatusMessage("Internal error: No addon file specified for install.", "error");
        return;
    }

    // Extract filename for display messages
    const addonFilenameForDisplay = addonFile.includes('\\') ? addonFile.substring(addonFile.lastIndexOf('\\') + 1) :
                                  addonFile.includes('/') ? addonFile.substring(addonFile.lastIndexOf('/') + 1) : addonFile;
    console.log(`Extracted filename for display: ${addonFilenameForDisplay}`);

    // Confirmation dialog
    console.log("Prompting user for addon install confirmation.");
    if (!confirm(`Install addon '${addonFilenameForDisplay}' for server '${serverName}'?`)) {
        console.log("Addon install cancelled by user.");
        showStatusMessage('Addon installation cancelled.', 'info');
        return; // Abort if user cancels
    }
    console.log("Addon install confirmed by user.");

    // Construct the request body containing the addon file identifier
    const requestBody = {
        filename: addonFile // Send the full path/identifier
    };
    console.log("Constructed request body for addon install:", requestBody);

    // Call the action helper, targeting the specific API endpoint (absolute path)
    console.log("Calling sendServerActionRequest for addon install API...");
    sendServerActionRequest(null, `/api/server/${serverName}/addon/install`, 'POST', requestBody, buttonElement);
    console.log("Returned from initiating sendServerActionRequest call for addon install (async).");
}