// bedrock_server_manager/web/static/js/scripts.js
// --- Helper: Display Status Messages ---
/**
 * Displays a status message in the dedicated area.
 * @param {string} message The message text.
 * @param {string} type 'info', 'success', 'error', or 'warning'.
 */
function showStatusMessage(message, type = 'info') {
    const area = document.getElementById('status-message-area');
    if (!area) {
        console.warn("Element with ID 'status-message-area' not found. Falling back to alert.");
        alert(`${type.toUpperCase()}: ${message}`);
        return;
    }

    area.className = `message-box message-${type}`;
    area.textContent = message;
    area.style.opacity = '1';

    setTimeout(() => {
        // Only clear if the message hasn't been replaced by another one
        if (area.textContent === message) {
            area.style.transition = 'opacity 0.5s ease-out';
            area.style.opacity = '0';
            setTimeout(() => {
                // Check again before clearing, in case a new message appeared quickly
                if (area.textContent === message && area.style.opacity === '0') {
                     area.textContent = '';
                     area.className = 'message-box'; // Reset classes
                     area.style.transition = ''; // Reset transition
                }
            }, 500); // Wait for fade out
        }
    }, 5000); // Start fade out after 5 seconds
}


// --- Helper: Send API Request ---
/**
 * Sends an asynchronous request to a server action endpoint.
 * Returns a Promise that resolves to the parsed JSON response data object
 * if the HTTP request itself was successful (status 200-299), otherwise resolves to false.
 * It displays status/error messages internally using showStatusMessage.
 * Validation errors (status 400 with data.errors) are handled specifically.
 *
 * @param {string|null} serverName The name of the target server (can be null if actionPath starts with '/').
 * @param {string} actionPath The path relative to the server OR an absolute path for the action (starting with '/').
 * @param {string} method The HTTP method ('POST', 'DELETE', 'PUT', etc.). Defaults to 'POST'.
 * @param {object|null} body Optional JSON body for the request.
 * @param {HTMLElement|null} buttonElement Optional button element to disable during request.
 * @returns {Promise<object|false>} A promise that resolves to the parsed JSON data object on HTTP success, or false on failure.
 */
async function sendServerActionRequest(serverName, actionPath, method = 'POST', body = null, buttonElement = null) {
    // --- Construct URL ---
    let url;
    if (actionPath.startsWith('/')) {
        url = actionPath;
    } else if (serverName) {
        url = `/server/${serverName}/${actionPath}`;
    } else {
        console.error("sendServerActionRequest requires a serverName for relative paths, or an absolute actionPath starting with '/'");
        showStatusMessage("Internal script error: Invalid request path configuration.", "error");
        if (buttonElement) buttonElement.disabled = false;
        return false; // Indicate failure
    }

    console.log(`API Request: ${method} for ${serverName || 'N/A'}, Path: ${actionPath}, URL: ${url}, Body:`, body);
    showStatusMessage(`Sending ${method} request to ${url}...`, 'info');
    if (buttonElement) buttonElement.disabled = true;

    let responseData = null; // To store parsed data from response body
    let httpSuccess = false; // To track if the HTTP request itself was ok (2xx)

    try {
        // --- Setup Fetch ---
        const fetchOptions = {
            method: method,
            headers: {
                'Accept': 'application/json',
                // Add CSRF token header if needed
                // 'X-CSRFToken': getCsrfTokenFromSomewhere(),
            }
        };
        if (body && (method === 'POST' || method === 'PUT')) {
            fetchOptions.headers['Content-Type'] = 'application/json';
            fetchOptions.body = JSON.stringify(body);
        }

        // --- Make Fetch Request ---
        const response = await fetch(url, fetchOptions);
        console.log(`Fetch response received: Status=${response.status}`, response);
        httpSuccess = response.ok; // Store if status is 200-299

        // --- Process Response Body ---
        const contentType = response.headers.get('content-type');
        if (response.status === 204) {
            // Handle No Content success
             console.log("Received 204 No Content - treating as success.");
             responseData = { status: 'success', message: `Action at ${url} successful (No Content).` };
             // httpSuccess is already true here
        } else if (contentType && contentType.includes('application/json')) {
            // If JSON content type, parse it regardless of status code (to get error details)
            responseData = await response.json();
            console.log(`Parsed JSON data:`, responseData);
        } else {
            // Handle non-JSON responses
            const textResponse = await response.text();
            console.warn(`Response from ${url} was not JSON or 204:`, textResponse);
            if (!httpSuccess) { // If status code indicates error
                // Create a generic error message for non-JSON errors
                responseData = { status: 'error', message: `Request failed (Status ${response.status}): ${textResponse.substring(0, 150)}...` };
                // httpSuccess remains false
            } else { // If status code is 2xx but content is not JSON (and not 204)
                 showStatusMessage(`Received OK status (${response.status}) but unexpected response format from ${url}. Check console/server logs.`, 'warning');
                 // Return false because we didn't get the expected JSON structure, even if HTTP was ok
                 if (buttonElement) buttonElement.disabled = false; // Re-enable button
                 return false;
            }
        }

        // --- Handle HTTP Errors & Validation ---
        if (!httpSuccess) {
            const errorMessage = responseData?.message || `Request failed with status ${response.status}`;
             // Specific handling for 400 validation errors if responseData has .errors
            if (response.status === 400 && responseData?.errors && typeof responseData.errors === 'object') {
                console.warn("Validation errors received:", responseData.errors);
                showStatusMessage(errorMessage || "Validation failed. See errors below.", "error");
                 // Display field-specific errors
                 const generalErrorArea = document.getElementById('validation-error-area');
                 let generalErrors = [];
                 Object.entries(responseData.errors).forEach(([field, message]) => {
                     const fieldErrorElement = document.querySelector(`.validation-error[data-field="${field}"]`);
                     if (fieldErrorElement) {
                         fieldErrorElement.textContent = message;
                     } else {
                         generalErrors.push(`${field}: ${message}`);
                     }
                 });
                 if (generalErrorArea && generalErrors.length > 0) {
                     generalErrorArea.innerHTML = '<strong>Field Errors:</strong><ul><li>' + generalErrors.join('</li><li>') + '</li></ul>';
                 }
            } else {
                 // For other non-2xx errors, just show the main message
                  showStatusMessage(errorMessage, "error");
            }
            // Return false because HTTP request failed
            if (buttonElement) buttonElement.disabled = false; // Re-enable
            return false;
        }

        // --- Handle Application-Level Status for SUCCESSFUL (2xx) HTTP responses ---
        // (Show message based on data.status, but always return the data object)
        if (responseData.status === 'success') {
            showStatusMessage(responseData.message || `Action at ${url} successful.`, 'success');
             // --- Specific UI Update for DELETE ---
             if (method === 'DELETE' && url.includes('/delete')) {
                 /* ... delete row logic ... */
             }
             // TODO: Add other success UI updates?
        } else if (responseData.status === 'confirm_needed') {
            // Don't show a message here, let the caller handle confirmation logic
            console.log("Confirmation needed response received and returned.");
        } else { // Status is 2xx, but data.status is 'error' or something else unexpected
            showStatusMessage(responseData.message || `Action failed at ${url}. Server reported status: ${responseData.status || 'unknown'}.`, 'error');
            // We still return the data object here as the HTTP request succeeded,
            // but the caller should check the status within it.
        }

    } catch (error) { // Catch network errors, JSON parsing errors, etc.
        console.error(`Error during ${method} request to ${url}:`, error);
        showStatusMessage(`Error performing action at ${url}: ${error.message}`, 'error');
        if (buttonElement) buttonElement.disabled = false; // Re-enable on catch
        return false; // Indicate failure
    } finally {
        // Re-enable button logic in finally needs refinement for confirm_needed case
        // Button should only be re-enabled if the operation definitively finished (error or final success)
        // It should remain disabled if 'confirm_needed' status is returned.
        if (!httpSuccess || (responseData && responseData.status !== 'confirm_needed')) {
             if (buttonElement) buttonElement.disabled = false;
        }
    }

    console.log(`sendServerActionRequest for ${url} returning data object:`, responseData);
    // Return the parsed data object if HTTP succeeded, otherwise false was returned earlier
    return responseData;
} 


// --- Helper: Get Selected Server ---
function getSelectedServer() {
    const serverSelect = document.getElementById('server-select');
    if (!serverSelect) {
        console.error("Element with ID 'server-select' not found!");
        showStatusMessage('Error: Server selection dropdown missing.', 'error');
        return null;
    }
    const selectedServer = serverSelect.value;
    if (!selectedServer) {
        showStatusMessage('Please select a server first.', 'warning');
        return null;
    }
    return selectedServer;
}


// --- Global Functions Called by HTML onclick="..." Attributes ---

function startServer(buttonElement) {
    console.log("startServer() called");
    const serverName = getSelectedServer();
    if (serverName) {
        // Call sendServerActionRequest with default POST method
        sendServerActionRequest(serverName, 'start', 'POST', null, buttonElement);
    }
}

function stopServer(buttonElement) {
    console.log("stopServer() called");
    const serverName = getSelectedServer();
    if (serverName) {
        sendServerActionRequest(serverName, 'stop', 'POST', null, buttonElement);
    }
}

function restartServer(buttonElement) {
    console.log("restartServer() called");
    const serverName = getSelectedServer();
    if (serverName) {
        sendServerActionRequest(serverName, 'restart', 'POST', null, buttonElement);
    }
}

function promptCommand(buttonElement) {
    console.log("promptCommand() called");
    const serverName = getSelectedServer();
    if (!serverName) {
        return; // Error message shown by getSelectedServer
    }

    const command = prompt(`Enter command to send to server '${serverName}':`);

    if (command === null) { // User pressed Cancel
        console.log("Command prompt cancelled.");
        return;
    }

    const trimmedCommand = command.trim();
    if (trimmedCommand === "") {
        showStatusMessage('Command cannot be empty.', 'warning');
        return;
    }

    // Call the helper with the 'send' action, POST method, the command in the body
    sendServerActionRequest(serverName, 'send', 'POST', { command: trimmedCommand }, buttonElement);
}

function deleteServer(buttonElement, serverName) {
    console.log(`deleteServer() called for: ${serverName}`);
    if (confirm(`Are you sure you want to delete server '${serverName}'? This action is irreversible!`)) {
        console.log(`Deletion confirmed for ${serverName}. Sending API request.`);
        sendServerActionRequest(serverName, 'delete', 'DELETE', null, buttonElement);
    } else {
        console.log(`Deletion cancelled for ${serverName}.`);
        showStatusMessage('Deletion cancelled.', 'info');
    }
}


function triggerBackup(buttonElement, serverName, backupType) {

    console.log(`ENTERED triggerBackup - Server: ${serverName}, Type: ${backupType}, Button:`, buttonElement);

    if (backupType === 'all') {
        console.log("Checking confirmation for 'all' backup...");
        if (!confirm(`Performing a full backup (world + config) for '${serverName}'. This might take a moment. Continue?`)) {
            console.log("Full backup cancelled by user.");
            showStatusMessage('Full backup cancelled.', 'info');
            return;
        }
        console.log("Confirmation received for 'all' backup.");
    }

    const requestBody = {
        backup_type: backupType
    };
    console.log("Constructed request body:", requestBody);

    // Call the helper function, sending the type in the JSON body
    console.log("Calling sendServerActionRequest..."); // --- Log before call ---
    sendServerActionRequest(serverName, 'backup/action', 'POST', requestBody, buttonElement);
    console.log("Returned from sendServerActionRequest call (async)."); // --- Log after call ---
}

/**
 * Triggers a backup operation for a specific config file passed directly.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} filename The specific config file to backup.
 */
function triggerSpecificConfigBackup(buttonElement, serverName, filename) {
    if (!filename) {
        console.error("triggerSpecificConfigBackup called without a filename!");
        showStatusMessage("Internal error: No filename specified for backup.", "error");
        return;
    }

    console.log(`ENTERED triggerBackup - Server: ${serverName}, Type: ${backupType}, Button:`, buttonElement);
    console.log(`triggerSpecificConfigBackup called for server: ${serverName}, file: ${filename}`);

    const requestBody = {
        backup_type: 'config',
        file_to_backup: filename
    };

    // Call the helper function, sending type and file in the JSON body
    // Use the updated sendServerActionRequest which handles the path 'backup/action'
    sendServerActionRequest(serverName, 'backup/action', 'POST', requestBody, buttonElement);
}

/**
 * Triggers a restoration operation from a specific backup file.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} restoreType 'world' or 'config'.
 * @param {string} backupFile The filename of the backup to restore.
 */
function triggerRestore(buttonElement, serverName, restoreType, backupFile) {
    if (!backupFile) {
        console.error("triggerRestore called without backupFile!");
        showStatusMessage("Internal error: No backup file specified for restore.", "error");
        return;
    }
    if (!restoreType) {
        console.error("triggerRestore called without restoreType!");
        showStatusMessage("Internal error: No restore type specified.", "error");
        return;
    }


    console.log(`triggerRestore called for server: ${serverName}, type: ${restoreType}, file: ${backupFile}`);

    // Confirmation dialog
    if (!confirm(`Are you sure you want to restore '${backupFile}' for server '${serverName}'?\nThis will overwrite current ${restoreType} data.`)) {
        console.log("Restore cancelled by user.");
        showStatusMessage('Restore operation cancelled.', 'info');
        return;
    }
    console.log("Restore confirmed by user.");

    const requestBody = {
        restore_type: restoreType,
        backup_file: backupFile
    };

    // Call the helper function, using the modified actionPath structure
    // The action path should match the Flask route
    sendServerActionRequest(serverName, 'restore/action', 'POST', requestBody, buttonElement);
}

/**
 * Triggers restoring all files for a server.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 */
function triggerRestoreAll(buttonElement, serverName) {
    console.log(`triggerRestoreAll called for server: ${serverName}`);

    // Confirmation dialog
    if (!confirm(`Are you sure you want to restore ALL backup files for server '${serverName}'?\nThis will overwrite current world and config files.`)) {
        console.log("Restore All cancelled by user.");
        showStatusMessage('Restore All operation cancelled.', 'info');
        return;
    }
    console.log("Restore All confirmed by user.");

    sendServerActionRequest(serverName, 'restore/all', 'POST', null, buttonElement);
}

/**
 * Triggers the installation of a specific world file.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} worldFile The full path or identifier of the world file to install.
 */
function triggerWorldInstall(buttonElement, serverName, worldFile) {

    if (!worldFile) {
        console.error("triggerWorldInstall called without worldFile!");
        showStatusMessage("Internal error: No world file specified for install.", "error");
        return;
    }

    // Use basename for display messages if desired (requires a helper or simple split)
    const worldFilenameForDisplay = worldFile.includes('\\') ? worldFile.substring(worldFile.lastIndexOf('\\') + 1) :
                                   worldFile.includes('/') ? worldFile.substring(worldFile.lastIndexOf('/') + 1) : worldFile;


    console.log(`triggerWorldInstall called for server: ${serverName}, file: ${worldFile}`);
    console.log(`Displaying filename as: ${worldFilenameForDisplay}`);


    // Confirmation dialog with overwrite warning
    if (!confirm(`Install world '${worldFilenameForDisplay}' for server '${serverName}'?\n\nWARNING: This will replace the current world directory if one exists! Continue?`)) {
        console.log("World install cancelled by user.");
        showStatusMessage('World installation cancelled.', 'info');
        return;
    }
    console.log("World install confirmed by user.");

    const requestBody = {
        filename: worldFile // Send the full path/identifier received from onclick
    };

    // Call the helper function, targeting the API endpoint
    // Pass null for serverName because actionPath starts with /
    sendServerActionRequest(null, `/api/server/${serverName}/world/install`, 'POST', requestBody, buttonElement);
}


/**
 * Triggers the installation of a specific addon file.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} addonFile The full path or identifier of the addon file to install.
 */
function triggerAddonInstall(buttonElement, serverName, addonFile) {
    if (!addonFile) {
        console.error("triggerAddonInstall called without addonFile!");
        showStatusMessage("Internal error: No addon file specified for install.", "error");
        return;
    }

    const addonFilenameForDisplay = addonFile.includes('\\') ? addonFile.substring(addonFile.lastIndexOf('\\') + 1) :
                                  addonFile.includes('/') ? addonFile.substring(addonFile.lastIndexOf('/') + 1) : addonFile;

    console.log(`triggerAddonInstall called for server: ${serverName}, file: ${addonFile}`);

    if (!confirm(`Install addon '${addonFilenameForDisplay}' for server '${serverName}'?`)) {
        console.log("Addon install cancelled by user.");
        showStatusMessage('Addon installation cancelled.', 'info');
        return;
    }
    console.log("Addon install confirmed by user.");

    const requestBody = {
        filename: addonFile
    };

    sendServerActionRequest(null, `/api/server/${serverName}/addon/install`, 'POST', requestBody, buttonElement);
}


/**
 * Saves the allowlist configuration via API.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function saveAllowlist(buttonElement, serverName, isNewInstall) {
    const textArea = document.getElementById('player-names');
    const ignoreLimitCheckbox = document.getElementById('ignore-limit-checkbox');

    if (!textArea || !ignoreLimitCheckbox) {
        console.error("Required elements ('player-names' textarea or 'ignore-limit-checkbox') not found!");
        showStatusMessage("Internal page error: Form elements missing.", "error");
        return;
    }

    // Get player names from textarea, split by line, trim, filter empty
    const playerNamesRaw = textArea.value;
    const playerNames = playerNamesRaw.split('\n')
                                    .map(name => name.trim())
                                    .filter(name => name.length > 0);

    const ignoresPlayerLimit = ignoreLimitCheckbox.checked;

    console.log(`saveAllowlist called for: ${serverName}, NewInstall: ${isNewInstall}`);
    console.log("Player names:", playerNames);
    console.log("Ignore player limit:", ignoresPlayerLimit);


    const requestBody = {
        players: playerNames,
        ignoresPlayerLimit: ignoresPlayerLimit
    };

    // Call the helper function, targeting the new API endpoint
    // Use sendServerActionRequest for consistency
    sendServerActionRequest(null, `/api/server/${serverName}/allowlist`, 'POST', requestBody, buttonElement)
        .then(success => {
             // This .then() assumes sendServerActionRequest might return true/false
             // based on success/error for sequencing. Let's modify it slightly.
             if (success && isNewInstall) {
                 // If save was successful AND it's a new install, navigate to the next step
                 console.log("Allowlist saved during new install, navigating to permissions...");
                 // Short delay to allow user to read success message
                 setTimeout(() => {
                     window.location.href = `/server/${serverName}/configure_permissions?new_install=True`;
                 }, 1000);
             } else if (success && !isNewInstall) {
                  // Optional: Maybe disable the button briefly or give extra confirmation
                  console.log("Allowlist saved successfully (not new install).");
             } else {
                  // Error message was already shown by sendServerActionRequest
                  console.log("Allowlist save failed or was not part of new install sequence for navigation.");
             }
        });
}


/**
 * Adds players to the allowlist via API.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 */
function addAllowlistPlayers(buttonElement, serverName) {
    const textArea = document.getElementById('player-names-add');
    const ignoreLimitCheckbox = document.getElementById('ignore-limit-add');

    if (!textArea || !ignoreLimitCheckbox) {
        console.error("Required elements ('player-names-add' textarea or 'ignore-limit-add' checkbox) not found!");
        showStatusMessage("Internal page error: Form elements missing.", "error");
        return;
    }

    // Get player names from textarea, split by line, trim, filter empty
    const playerNamesRaw = textArea.value;
    const playersToAdd = playerNamesRaw.split('\n')
                                    .map(name => name.trim())
                                    .filter(name => name.length > 0);

    if (playersToAdd.length === 0) {
         showStatusMessage("Please enter at least one player name to add.", "warning");
         return;
    }

    const ignoresPlayerLimit = ignoreLimitCheckbox.checked;

    console.log(`addAllowlistPlayers called for: ${serverName}`);
    console.log("Players to add:", playersToAdd);
    console.log("Ignore player limit:", ignoresPlayerLimit);

    const requestBody = {
        players: playersToAdd,
        ignoresPlayerLimit: ignoresPlayerLimit
    };

    // Call sendServerActionRequest targeting the ADD endpoint
    // Remember sendServerActionRequest now returns a promise resolving to true/false
    sendServerActionRequest(null, `/api/server/${serverName}/allowlist/add`, 'POST', requestBody, buttonElement)
        .then(success => {
            if (success) {
                // Clear the textarea after successful submission
                textArea.value = '';
                // Optionally uncheck the box
                // ignoreLimitCheckbox.checked = false;

                // --- Refresh the Current Allowlist display ---
                // We need a way to get the updated list.
                // Option 1: Reload the whole page (simple but jarring)
                 // showStatusMessage("Players added. Reloading page...", "success");
                 // setTimeout(() => { window.location.reload(); }, 1000);

                 // Option 2: Fetch the updated list and redraw it (better UX)
                 fetchAndUpdateAllowlistDisplay(serverName); // Call a new helper function

            } // Error message already shown by sendServerActionRequest if !success
        });
}

/**
 * Helper function to fetch the current allowlist and update the display.
 * @param {string} serverName
 */
async function fetchAndUpdateAllowlistDisplay(serverName) {
     console.log(`Fetching updated allowlist for ${serverName}...`);
     const displayList = document.getElementById('current-allowlist-display');
     const noPlayersLi = document.getElementById('no-players-message');
     if (!displayList) return; // Should not happen if HTML is correct

     try {
        // We need a GET API endpoint to just retrieve the current list
        // Let's assume /api/server/<server_name>/allowlist (GET) exists
        const response = await fetch(`/api/server/${serverName}/allowlist`); // GET request implicit
        if (!response.ok) {
            throw new Error(`Failed to fetch allowlist (Status: ${response.status})`);
        }
        const data = await response.json();

        if (data.status === 'success' && data.existing_players) {
            console.log("Updating allowlist display with:", data.existing_players);
            // Clear current list items (excluding the potential 'no players' message)
            displayList.querySelectorAll('li:not(#no-players-message)').forEach(li => li.remove());

            if (data.existing_players.length > 0) {
                 // Hide or remove the 'no players' message if it exists
                 if (noPlayersLi) noPlayersLi.style.display = 'none';
                 // Add new list items
                 data.existing_players.forEach(player => {
                     const li = document.createElement('li');
                     li.textContent = `${player.name} (Ignores Limit: ${player.ignoresPlayerLimit})`;
                     displayList.appendChild(li);
                 });
            } else {
                 // Show the 'no players' message if it exists, otherwise create it
                 if (noPlayersLi) {
                     noPlayersLi.style.display = ''; // Make it visible
                 } else {
                     const li = document.createElement('li');
                     li.id = 'no-players-message';
                     li.textContent = 'No players currently in allowlist.';
                     displayList.appendChild(li);
                 }
            }
        } else {
             console.error("Failed to get updated allowlist data from API:", data.message || 'Unknown API error');
             showStatusMessage("Could not refresh the current allowlist display.", "warning");
        }

     } catch (error) {
          console.error("Error fetching or updating allowlist display:", error);
          showStatusMessage("Error refreshing the current allowlist display.", "error");
     }
}


/**
 * Gathers property data from form and saves via API.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function saveProperties(buttonElement, serverName, isNewInstall) {
    console.log(`saveProperties called for: ${serverName}, NewInstall: ${isNewInstall}`);

    // --- गैदर Form Data ---
    const propertiesData = {};
    // List the IDs of the input/select elements (which match the 'name' attributes now)
    const propertyIds = [
        'server-name', 'level-name', 'gamemode', 'difficulty', 'allow-cheats',
        'max-players', 'server-port', 'server-portv6', 'enable-lan-visibility',
        'allow-list', 'default-player-permission-level', 'view-distance',
        'tick-distance', 'level-seed', 'online-mode', 'texturepack-required'
        // Add any other property IDs from your form
    ];

    propertyIds.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            // Use the element's 'id' or 'name' as the key (they match in this case)
            const propertyName = element.getAttribute('name') || id; // Fallback to id if name missing
            let value = element.value;

            // Add specific handling if needed (e.g., checkboxes if you used them)
            // if (element.type === 'checkbox') {
            //     value = element.checked; // Send boolean
            // }

            propertiesData[propertyName] = value;
        } else {
             console.warn(`Element with ID '${id}' not found in the form.`);
        }
    });

    console.log("Properties data gathered:", propertiesData);

    // --- Clear previous validation errors ---
    // Clear general area
    const generalErrorArea = document.getElementById('validation-error-area');
    if (generalErrorArea) generalErrorArea.textContent = '';
     // Clear specific field areas
    document.querySelectorAll('.validation-error').forEach(el => el.textContent = '');

    // --- Call API ---
    // Use the updated sendServerActionRequest that handles validation display
    sendServerActionRequest(null, `/api/server/${serverName}/properties`, 'POST', propertiesData, buttonElement)
        .then(success => {
            if (success && isNewInstall) {
                console.log("Properties saved during new install, navigating to allowlist...");
                showStatusMessage("Properties saved successfully! Proceeding to Allowlist...", "success"); // Give feedback before nav
                setTimeout(() => {
                    window.location.href = `/server/${serverName}/configure_allowlist?new_install=True`;
                }, 1500); // Slightly longer delay
            } else if (success && !isNewInstall) {
                 console.log("Properties saved successfully (not new install).");
                 // Message already shown by sendServerActionRequest
            } else {
                 // Failure case - validation or other error
                 // Messages already shown by sendServerActionRequest
                 console.log("Properties save failed.");
            }
        });
}

/**
 * Gathers player permissions from form and saves via API.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function savePermissions(buttonElement, serverName, isNewInstall) {
    console.log(`savePermissions called for: ${serverName}, NewInstall: ${isNewInstall}`);

    // --- Gather Permissions Data ---
    const permissionsMap = {};
    const permissionSelects = document.querySelectorAll('select.permission-select'); // Select by class

    if (permissionSelects.length === 0) {
         console.warn("No permission select elements found.");
    }

    permissionSelects.forEach(select => {
        const xuid = select.dataset.xuid; // Get XUID from data attribute
        const selectedLevel = select.value;
        if (xuid) {
            permissionsMap[xuid] = selectedLevel;
        } else {
             console.warn("Found permission select without data-xuid:", select);
        }
    });

    console.log("Permissions map gathered:", permissionsMap);

    // --- Clear previous validation errors ---
    const generalErrorArea = document.getElementById('validation-error-area');
    if (generalErrorArea) generalErrorArea.textContent = '';
    document.querySelectorAll('.validation-error').forEach(el => el.textContent = '');


    // --- Prepare request body ---
    const requestBody = {
        permissions: permissionsMap
    };

    // --- Call API ---
    // Use PUT method as we are replacing the entire state
    sendServerActionRequest(null, `/api/server/${serverName}/permissions`, 'PUT', requestBody, buttonElement)
        .then(success => {
            if (success && isNewInstall) {
                console.log("Permissions saved during new install, navigating to service config...");
                 showStatusMessage("Permissions saved successfully! Proceeding to Service Config...", "success");
                setTimeout(() => {
                    window.location.href = `/server/${serverName}/configure_service?new_install=True`;
                }, 1500);
            } else if (success && !isNewInstall) {
                 console.log("Permissions saved successfully (not new install).");
                 // Message shown by sendServerActionRequest
            } else {
                 console.log("Permissions save failed.");
                 // Error messages (including validation) shown by sendServerActionRequest
            }
        });
}


/**
 * Gathers service settings and saves via API.
 * Optionally triggers server start via separate API call.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} currentOs The OS detected by the backend ('Linux', 'Windows', etc.).
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function saveServiceSettings(buttonElement, serverName, currentOs, isNewInstall) {
    console.log(`saveServiceSettings called for: ${serverName}, OS: ${currentOs}, NewInstall: ${isNewInstall}`);

    const requestBody = {};
    let startServerAfter = false; // Flag to start server later

    // --- Gather Data Based on OS ---
    if (currentOs === 'Linux') {
        const autoupdateCheckbox = document.getElementById('service-autoupdate');
        const autostartCheckbox = document.getElementById('service-autostart');
        requestBody.autoupdate = autoupdateCheckbox ? autoupdateCheckbox.checked : false;
        requestBody.autostart = autostartCheckbox ? autostartCheckbox.checked : false;
    } else if (currentOs === 'Windows') {
        const autoupdateCheckbox = document.getElementById('service-autoupdate');
        requestBody.autoupdate = autoupdateCheckbox ? autoupdateCheckbox.checked : false;
        // No separate autostart setting gathered from this form for Windows
    } else {
        showStatusMessage("Cannot save settings: Unsupported operating system.", "error");
        return; // Don't proceed if OS not supported by UI
    }

    // Check if server should be started afterwards (only if new install)
    if (isNewInstall) {
        const startServerCheckbox = document.getElementById('service-start-server');
        startServerAfter = startServerCheckbox ? startServerCheckbox.checked : false;
    }

    console.log("Service settings gathered:", requestBody);
    console.log("Start server after save:", startServerAfter);


    // --- Call API to Save Settings ---
    sendServerActionRequest(null, `/api/server/${serverName}/service`, 'POST', requestBody, buttonElement)
        .then(success => {
            if (success) {
                console.log("Service settings saved successfully.");
                // Message shown by sendServerActionRequest
                if (startServerAfter) {
                    console.log("Proceeding to start server via API...");
                    showStatusMessage("Service settings saved. Attempting to start server...", "info");
                    // Call the existing start API - find the start button if possible for disable, else null
                    const startButton = document.getElementById('start-server-btn');
                    // Use the sendServerActionRequest helper to call the start endpoint
                    sendServerActionRequest(serverName, 'start', 'POST', null, startButton) // Or null for button
                       .then(startSuccess => {
                           if (startSuccess && isNewInstall) {
                               // Optionally navigate after successful start
                               console.log("Server started successfully after new install config.");
                               showStatusMessage("Server started successfully! Redirecting...", "success");
                               setTimeout(() => { window.location.href = "/"; }, 2000); // Redirect to index
                           } else if (!startSuccess){
                                showStatusMessage("Service settings saved, but failed to start server.", "warning");
                           } else {
                               // Started ok, but not new install - message already shown
                           }
                       });
                } else if (isNewInstall) {
                    // Saved settings, but didn't need to start - navigate?
                    console.log("Service settings saved, proceeding without starting server.");
                     showStatusMessage("Service settings saved! Redirecting...", "success");
                    setTimeout(() => { window.location.href = "/"; }, 1500); // Redirect to index
                }
            } else {
                 console.log("Saving service settings failed.");
                 // Error message shown by sendServerActionRequest
            }
        });
}


/**
 * Triggers the server installation process via API, handling overwrite confirmation.
 * @param {HTMLElement} buttonElement The button that was clicked.
 */
function triggerInstallServer(buttonElement) {
    const serverNameInput = document.getElementById('install-server-name');
    const serverVersionInput = document.getElementById('install-server-version');

    if (!serverNameInput || !serverVersionInput) {
        console.error("Required input elements ('install-server-name', 'install-server-version') not found!");
        showStatusMessage("Internal page error: Form elements missing.", "error");
        return;
    }

    const serverName = serverNameInput.value.trim();
    const serverVersion = serverVersionInput.value.trim();

    if (!serverName || !serverVersion) { /* ... frontend validation ... */ return; }
    if (serverName.includes(';')) { /* ... frontend validation ... */ return; }

    console.log(`triggerInstallServer called for: ${serverName}, Version: ${serverVersion}`);

    // --- Clear previous validation errors ---
    const generalErrorArea = document.getElementById('validation-error-area');
    if (generalErrorArea) generalErrorArea.textContent = '';
    document.querySelectorAll('.validation-error').forEach(el => el.textContent = '');

    const requestBody = {
        server_name: serverName,
        server_version: serverVersion,
        overwrite: false
    };

    // --- Initial API Call ---
    sendServerActionRequest(null, '/api/server/install', 'POST', requestBody, buttonElement)
        .then(apiResponseData => { // apiResponseData is the JSON object or false

            if (apiResponseData === false) {
                 console.log("Initial install API call failed.");
                 // Button re-enabled in finally block of sendServerActionRequest
                 return;
            }

            if (apiResponseData.status === 'confirm_needed') {
                // --- Handle Confirmation ---
                console.log("Confirmation needed:", apiResponseData.message);
                if (confirm(apiResponseData.message)) {
                    console.log("Overwrite confirmed by user. Sending second API request.");
                    showStatusMessage("Overwrite confirmed. Re-attempting installation...", "info");

                    const overwriteRequestBody = {
                        server_name: serverName,
                        server_version: serverVersion,
                        overwrite: true
                    };

                    // --- Second API Call with overwrite: true ---
                    sendServerActionRequest(null, '/api/server/install', 'POST', overwriteRequestBody, buttonElement)
                        // --- Use a descriptive variable name ---
                        .then(finalApiResponseData => {

                            // Check if second call failed (returned false)
                            if (finalApiResponseData === false) {
                                console.log("Install/Overwrite (second call) failed at HTTP/Network level.");
                                return;
                            }

                            // Check status *within* the second response object
                            if (finalApiResponseData.status === 'success') {
                                // --- Success on Overwrite ---
                                // --- Check for URL in the *SECOND* response ---
                                const nextUrl = finalApiResponseData.next_step_url;
                                console.log("DEBUG: Extracted nextUrl (overwrite):", nextUrl);

                                if (nextUrl) {
                                    console.log("Install/Overwrite successful, navigating to configuration...");
                                    setTimeout(() => {
                                        window.location.href = nextUrl;
                                    }, 1500);
                                } else {
                                     console.log("Install/Overwrite successful, but no next step URL provided in final response.");
                                }
                            } else {
                                 console.log(`Install/Overwrite failed (application status: ${finalApiResponseData.status}).`);
                            }
                        });

                } else { // User cancelled confirmation
                    console.log("Overwrite cancelled by user.");
                    showStatusMessage("Installation cancelled.", "info");
                    if (buttonElement) buttonElement.disabled = false;
                }
            } else if (apiResponseData.status === 'success') {
                 // --- Handle Direct Success (New Install) ---
                 // --- Check for URL in the *FIRST* response ---
                 const nextUrl = apiResponseData.next_step_url;
                 console.log("DEBUG: Extracted nextUrl (new install):", nextUrl);

                 if (nextUrl) {
                      console.log("New install successful, navigating to configuration...");
                      setTimeout(() => {
                         window.location.href = nextUrl;
                      }, 1500);
                 } else {
                      console.log("New install successful, but no next step URL provided in initial response.");
                 }
            } else {
                 // --- Handle other non-success statuses from initial call ---
                 console.log(`Initial install attempt resulted in status: ${apiResponseData.status}.`);
            }
        });
}