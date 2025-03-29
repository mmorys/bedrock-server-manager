// bedrock_server_manager/web/static/js/scripts.js

// --- Helper: Display Status Messages ---
/**
 * Displays a status message in the dedicated area.
 * Clears the message automatically after a delay.
 * @param {string} message The message text.
 * @param {string} [type='info'] 'info', 'success', 'error', or 'warning'.
 */
function showStatusMessage(message, type = 'info') {
    // Log function entry and parameters
    console.log(`showStatusMessage called with message: "${message}", type: ${type}`);

    const area = document.getElementById('status-message-area');
    if (!area) {
        // Log a warning if the dedicated area is not found and fall back to alert
        console.warn("Element with ID 'status-message-area' not found. Falling back to alert.");
        alert(`${type.toUpperCase()}: ${message}`);
        return;
    }

    // Log applying the message and styles
    console.log("Applying message and styles to status area.");
    area.className = `message-box message-${type}`; // Set classes for styling
    area.textContent = message; // Set the message text
    area.style.opacity = '1'; // Make it visible immediately

    // Log setting up the timeout for clearing the message
    console.log("Setting timeout to clear status message in 5 seconds.");
    // Set a timeout to start fading out the message
    setTimeout(() => {
        // Check if the message currently displayed is still the one we set
        // This prevents clearing a newer message that might have appeared quickly
        if (area.textContent === message) {
            console.log(`Starting fade-out for message: "${message}"`);
            area.style.transition = 'opacity 0.5s ease-out'; // Add fade-out transition
            area.style.opacity = '0'; // Start fade-out

            // Set another timeout to clear the content after the fade-out completes
            setTimeout(() => {
                // Check again if the message is still the same and opacity is 0
                if (area.textContent === message && area.style.opacity === '0') {
                    console.log(`Clearing message content and resetting styles for: "${message}"`);
                    area.textContent = ''; // Clear the text
                    area.className = 'message-box'; // Reset classes to default
                    area.style.transition = ''; // Reset transition property
                } else {
                    console.log(`Message content changed or opacity not 0 before final clear for: "${message}". Aborting clear.`);
                }
            }, 500); // Wait for fade out duration (0.5s)
        } else {
            console.log(`Message content changed before timeout expired for: "${message}". Aborting fade-out.`);
        }
    }, 5000); // Start fade out after 5 seconds (5000 milliseconds)
}


// --- Helper: Send API Request ---
/**
 * Sends an asynchronous request to a server action endpoint using Fetch API.
 * Displays status/error messages using showStatusMessage.
 * Handles JSON responses, including specific handling for validation errors (status 400 with data.errors).
 * Handles 204 No Content responses as success.
 * Disables/re-enables an optional button element during the request lifecycle.
 *
 * @param {string|null} serverName The name of the target server (can be null if actionPath starts with '/').
 * @param {string} actionPath The path relative to the server OR an absolute path for the action (starting with '/').
 * @param {string} [method='POST'] The HTTP method ('POST', 'DELETE', 'PUT', etc.).
 * @param {object|null} [body=null] Optional JavaScript object to be sent as JSON in the request body.
 * @param {HTMLElement|null} [buttonElement=null] Optional button element to disable during request.
 * @returns {Promise<object|false>} A promise that resolves to the parsed JSON data object if the HTTP request was successful (status 200-299), otherwise resolves to false.
 */
async function sendServerActionRequest(serverName, actionPath, method = 'POST', body = null, buttonElement = null) {
    // Log function entry and parameters
    console.log(`sendServerActionRequest initiated. Server: ${serverName || 'N/A'}, Path: ${actionPath}, Method: ${method}, Body:`, body, "Button:", buttonElement);

    // --- Construct URL ---
    let url;
    if (actionPath.startsWith('/')) {
        // If actionPath starts with '/', use it as an absolute path
        url = actionPath;
        console.log(`Constructed absolute URL: ${url}`);
    } else if (serverName) {
        // If actionPath is relative and serverName is provided, construct the server-specific URL
        url = `/server/${serverName}/${actionPath}`;
        console.log(`Constructed relative URL: ${url}`);
    } else {
        // Log an error and show status message if URL construction is invalid
        console.error("sendServerActionRequest requires a serverName for relative paths, or an absolute actionPath starting with '/'");
        showStatusMessage("Internal script error: Invalid request path configuration.", "error");
        if (buttonElement) {
            console.log("Re-enabling button due to invalid URL configuration.");
            buttonElement.disabled = false;
        }
        return false; // Indicate failure immediately
    }

    // Log the request details before sending
    console.log(`API Request Details -> Method: ${method}, URL: ${url}, Body:`, body);
    showStatusMessage(`Sending ${method} request to ${url}...`, 'info'); // Inform user
    if (buttonElement) {
        console.log("Disabling button element during request.");
        buttonElement.disabled = true; // Disable button if provided
    }

    let responseData = null; // Variable to store parsed response data
    let httpSuccess = false; // Flag to track if HTTP status code indicates success (2xx)

    try {
        // --- Setup Fetch Options ---
        const fetchOptions = {
            method: method,
            headers: {
                'Accept': 'application/json', // Expect JSON response
                // Note: Add CSRF token header here if your framework requires it
                // 'X-CSRFToken': getCsrfTokenFromSomewhere(),
            }
        };
        // If a body is provided and method allows a body, stringify and set Content-Type
        if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) { // Added PATCH
            fetchOptions.headers['Content-Type'] = 'application/json';
            fetchOptions.body = JSON.stringify(body);
            console.log("Added JSON body and Content-Type header.");
        }

        // --- Make Fetch Request ---
        console.log(`Executing fetch request to ${url} with options:`, fetchOptions);
        const response = await fetch(url, fetchOptions);
        console.log(`Fetch response received: Status=${response.status}, OK=${response.ok}`, response);
        httpSuccess = response.ok; // Store if status is in the range 200-299

        // --- Process Response Body ---
        const contentType = response.headers.get('content-type');
        console.log(`Response content-type: ${contentType}`);

        if (response.status === 204) {
            // Handle HTTP 204 No Content as a success case
             console.log("Received 204 No Content - treating as success. Creating default success response data.");
             responseData = { status: 'success', message: `Action at ${url} successful (No Content).` };
             // httpSuccess is already true here
        } else if (contentType && contentType.includes('application/json')) {
            // If content type indicates JSON, parse the body
            console.log("Response is JSON, parsing body...");
            responseData = await response.json();
            console.log(`Parsed JSON response data:`, responseData);
        } else {
            // Handle non-JSON responses (e.g., HTML error pages, plain text)
            const textResponse = await response.text();
            console.warn(`Response from ${url} was not JSON or 204. Status: ${response.status}. Body Text (truncated):`, textResponse.substring(0, 200));
            if (!httpSuccess) { // If status code indicates an HTTP error
                // Create a generic error message using the text response
                console.log("Creating generic error response data from non-JSON error response.");
                responseData = { status: 'error', message: `Request failed (Status ${response.status}): ${textResponse.substring(0, 150)}...` };
                // httpSuccess remains false
            } else { // If status code is 2xx but content is not JSON/204 (unexpected)
                 console.warn(`Received OK status (${response.status}) but unexpected non-JSON/204 response format from ${url}.`);
                 showStatusMessage(`Received OK status (${response.status}) but unexpected response format from ${url}. Check console/server logs.`, 'warning');
                 // Return false because we didn't get the expected JSON structure, even though HTTP status was ok.
                 if (buttonElement) {
                     console.log("Re-enabling button due to unexpected successful response format.");
                     buttonElement.disabled = false; // Re-enable button
                 }
                 return false; // Indicate failure to meet expectations
            }
        }

        // --- Handle HTTP Errors & Validation Errors (triggered if !httpSuccess) ---
        if (!httpSuccess) {
            // Determine the error message from the parsed data or construct one
            const errorMessage = responseData?.message || `Request failed with status ${response.status}`;
            console.error(`HTTP Error: Status ${response.status}. Message: ${errorMessage}`);

             // Specific handling for 400 Bad Request potentially containing validation errors
            if (response.status === 400 && responseData?.errors && typeof responseData.errors === 'object') {
                console.warn("Validation errors received from server:", responseData.errors);
                showStatusMessage(errorMessage || "Validation failed. See form errors or console.", "error"); // Show main error
                 // Attempt to display field-specific errors on the page
                 const generalErrorArea = document.getElementById('validation-error-area');
                 let generalErrors = []; // Store errors that don't have a dedicated field element
                 console.log("Attempting to display validation errors on form fields.");
                 Object.entries(responseData.errors).forEach(([field, message]) => {
                     const fieldErrorElement = document.querySelector(`.validation-error[data-field="${field}"]`);
                     if (fieldErrorElement) {
                         console.log(`Displaying error for field "${field}"`);
                         fieldErrorElement.textContent = message;
                     } else {
                         console.log(`No specific display area found for field "${field}", adding to general errors.`);
                         generalErrors.push(`${field}: ${message}`);
                     }
                 });
                 // Display general errors if any exist and the area is present
                 if (generalErrorArea && generalErrors.length > 0) {
                     console.log("Displaying general validation errors.");
                     generalErrorArea.innerHTML = '<strong>Field Errors:</strong><ul><li>' + generalErrors.join('</li><li>') + '</li></ul>';
                 }
            } else {
                 // For other non-2xx errors (or 400 without specific .errors structure), just show the main message
                 console.log("Displaying general HTTP error message.");
                  showStatusMessage(errorMessage, "error");
            }
            // Return false because the HTTP request itself failed
            if (buttonElement) {
                console.log("Re-enabling button due to HTTP error.");
                buttonElement.disabled = false; // Re-enable button on failure
            }
            return false; // Indicate failure
        }

        // --- Handle Application-Level Status for SUCCESSFUL (2xx) HTTP responses ---
        // At this point, httpSuccess is true. We check the 'status' field within the responseData JSON.
        console.log("HTTP request successful (2xx). Processing application-level status in response data:", responseData?.status);
        if (responseData && responseData.status === 'success') {
            console.log("Application status is 'success'. Displaying success message:", responseData.message || `Action at ${url} successful.`);
            showStatusMessage(responseData.message || `Action at ${url} successful.`, 'success');
             // --- Specific UI Update for DELETE (Example) ---
             if (method === 'DELETE' && url.includes('/delete')) {
                 console.log("DELETE request successful, potentially removing UI element (logic currently commented out).");
                 /* Example: Find row corresponding to serverName/item and remove it */
                 // const row = document.getElementById(`server-row-${serverName}`); // Assuming rows have IDs like this
                 // if (row) row.remove();
             }
             // TODO: Add other success-specific UI updates here if needed.
        } else if (responseData && responseData.status === 'confirm_needed') {
            // Special status indicating the caller needs to handle confirmation logic
            console.log("Application status is 'confirm_needed'. Returning data for caller handling. Message:", responseData.message);
            // Don't show a message here; the caller will use the response data to prompt the user.
            // Button should remain disabled until confirmation is resolved by the caller.
        } else { // Status is 2xx, but data.status is 'error', missing, or unexpected
            const appStatus = responseData?.status || 'unknown';
            const appMessage = responseData?.message || `Action failed at ${url}. Server reported status: ${appStatus}.`;
            console.warn(`HTTP success (2xx), but application status is '${appStatus}'. Message: ${appMessage}`);
            showStatusMessage(appMessage, 'error'); // Show error message from the application
            // We still return the data object here as the HTTP request succeeded,
            // but the caller should check the status within it to confirm the action's success.
            // Example: return responseData might be appropriate if caller needs error details.
            // However, returning false might be simpler if the convention is boolean success/fail for the caller.
            // Let's stick to returning the object for now, as the initial comment suggested.
            // Re-enable button here as the operation did complete (albeit with an app-level failure).
            if (buttonElement) {
                console.log("Re-enabling button after HTTP success but application-level failure/unexpected status.");
                buttonElement.disabled = false;
            }
        }

    } catch (error) { // Catch network errors, JSON parsing errors, etc.
        console.error(`Error during ${method} request to ${url}:`, error);
        showStatusMessage(`Network or processing error during action at ${url}: ${error.message}`, 'error');
        if (buttonElement) {
            console.log("Re-enabling button due to caught error.");
            buttonElement.disabled = false; // Re-enable button on catch
        }
        return false; // Indicate failure
    } finally {
        // --- Button Re-enabling Logic ---
        // The button should be re-enabled if the operation is definitively finished:
        // 1. HTTP request failed (!httpSuccess)
        // 2. HTTP request succeeded (httpSuccess) AND the application status is NOT 'confirm_needed'.
        console.log(`Finally block check: httpSuccess=${httpSuccess}, responseData.status=${responseData?.status}`);
        if (!httpSuccess || (httpSuccess && responseData && responseData.status !== 'confirm_needed')) {
             if (buttonElement && buttonElement.disabled) {
                 console.log("Re-enabling button in finally block.");
                 buttonElement.disabled = false;
             } else if (buttonElement && !buttonElement.disabled) {
                  console.log("Button was already enabled in finally block (likely handled in error/success path).");
             }
        } else {
            console.log("Button remains disabled (likely due to 'confirm_needed' status or prior re-enabling).");
        }
    }

    // Log the data being returned (the parsed JSON object or false if errors occurred before this point)
    console.log(`sendServerActionRequest for ${url} returning data object (or false if previously failed):`, responseData);
    // Return the parsed data object if HTTP succeeded. If HTTP failed, `false` was returned earlier.
    // Note: If HTTP succeeded but app status was 'error', we still return the data object here.
    return httpSuccess ? responseData : false; // Ensure we return false if httpSuccess was false but wasn't caught earlier
}


// --- Helper: Get Selected Server ---
/**
 * Gets the value (server name) of the selected option in the 'server-select' dropdown.
 * Shows a status message if the dropdown is missing or no server is selected.
 * @returns {string|null} The selected server name, or null if none selected or error occurs.
 */
function getSelectedServer() {
    console.log("getSelectedServer() called.");
    const serverSelect = document.getElementById('server-select');
    if (!serverSelect) {
        // Log error and show message if dropdown element not found
        console.error("Element with ID 'server-select' not found!");
        showStatusMessage('Error: Server selection dropdown missing.', 'error');
        return null;
    }

    const selectedServer = serverSelect.value;
    console.log(`Selected server value: "${selectedServer}"`);

    if (!selectedServer) {
        // Show warning if no server is selected (value is empty)
        console.warn("No server selected in dropdown.");
        showStatusMessage('Please select a server first.', 'warning');
        return null;
    }

    // Return the selected server name
    console.log(`Returning selected server: ${selectedServer}`);
    return selectedServer;
}


// --- Global Functions Called by HTML onclick="..." Attributes ---

/**
 * Initiates the 'start' action for the currently selected server.
 * @param {HTMLElement} buttonElement The button that was clicked (passed to disable).
 */
function startServer(buttonElement) {
    console.log("startServer() called.");
    const serverName = getSelectedServer(); // Get the selected server
    if (serverName) {
        console.log(`Attempting to start server: ${serverName}`);
        // Call the generic action helper for the 'start' action
        sendServerActionRequest(serverName, 'start', 'POST', null, buttonElement);
    } else {
        console.log("startServer() aborted: No server selected.");
    }
}

/**
 * Initiates the 'stop' action for the currently selected server.
 * @param {HTMLElement} buttonElement The button that was clicked (passed to disable).
 */
function stopServer(buttonElement) {
    console.log("stopServer() called.");
    const serverName = getSelectedServer(); // Get the selected server
    if (serverName) {
        console.log(`Attempting to stop server: ${serverName}`);
        // Call the generic action helper for the 'stop' action
        sendServerActionRequest(serverName, 'stop', 'POST', null, buttonElement);
    } else {
        console.log("stopServer() aborted: No server selected.");
    }
}

/**
 * Initiates the 'restart' action for the currently selected server.
 * @param {HTMLElement} buttonElement The button that was clicked (passed to disable).
 */
function restartServer(buttonElement) {
    console.log("restartServer() called.");
    const serverName = getSelectedServer(); // Get the selected server
    if (serverName) {
        console.log(`Attempting to restart server: ${serverName}`);
        // Call the generic action helper for the 'restart' action
        sendServerActionRequest(serverName, 'restart', 'POST', null, buttonElement);
    } else {
        console.log("restartServer() aborted: No server selected.");
    }
}

/**
 * Prompts the user for a command and sends it to the currently selected server.
 * @param {HTMLElement} buttonElement The button that was clicked (passed to disable).
 */
function promptCommand(buttonElement) {
    console.log("promptCommand() called.");
    const serverName = getSelectedServer(); // Get the selected server
    if (!serverName) {
        console.log("promptCommand() aborted: No server selected.");
        return; // Error message already shown by getSelectedServer
    }

    // Prompt user for the command
    console.log(`Prompting user for command for server: ${serverName}`);
    const command = prompt(`Enter command to send to server '${serverName}':`);

    if (command === null) { // User pressed Cancel
        console.log("Command prompt cancelled by user.");
        showStatusMessage('Command input cancelled.', 'info'); // Inform user
        return;
    }

    // Trim whitespace from the command
    const trimmedCommand = command.trim();
    console.log(`User entered command: "${command}", Trimmed: "${trimmedCommand}"`);

    if (trimmedCommand === "") {
        // Show warning if command is empty after trimming
        console.warn("Command is empty after trimming.");
        showStatusMessage('Command cannot be empty.', 'warning');
        return;
    }

    // Call the generic action helper with the 'send' action and command in the body
    console.log(`Sending command "${trimmedCommand}" to server: ${serverName}`);
    sendServerActionRequest(serverName, 'send', 'POST', { command: trimmedCommand }, buttonElement);
}

/**
 * Prompts for confirmation and initiates the 'delete' action for a specific server.
 * @param {HTMLElement} buttonElement The button that was clicked (passed to disable).
 * @param {string} serverName The name of the server to delete.
 */
function deleteServer(buttonElement, serverName) {
    console.log(`deleteServer() called for server: ${serverName}`);
    // Confirm deletion with the user
    if (confirm(`Are you sure you want to delete server '${serverName}'? This action is irreversible!`)) {
        console.log(`Deletion confirmed by user for ${serverName}. Sending API request.`);
        // Call the generic action helper for the 'delete' action using DELETE method
        sendServerActionRequest(serverName, 'delete', 'DELETE', null, buttonElement);
    } else {
        // Log cancellation and inform user
        console.log(`Deletion cancelled by user for ${serverName}.`);
        showStatusMessage('Deletion cancelled.', 'info');
    }
}

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


/**
 * Gathers allowlist data from the form and saves it via API.
 * Handles navigation to the next step if part of a new server installation sequence.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function saveAllowlist(buttonElement, serverName, isNewInstall) {
    // Log function entry
    console.log(`saveAllowlist called - Server: ${serverName}, NewInstall: ${isNewInstall}, Button:`, buttonElement);

    // Get references to form elements
    const textArea = document.getElementById('player-names');
    const ignoreLimitCheckbox = document.getElementById('ignore-limit-checkbox');

    // Validate that elements were found
    if (!textArea || !ignoreLimitCheckbox) {
        console.error("Required elements ('player-names' textarea or 'ignore-limit-checkbox') not found!");
        showStatusMessage("Internal page error: Form elements missing.", "error");
        return;
    }
    console.log("Found allowlist form elements.");

    // Get player names from textarea: split by newline, trim whitespace, filter out empty lines
    const playerNamesRaw = textArea.value;
    const playerNames = playerNamesRaw.split('\n')
                                    .map(name => name.trim()) // Remove leading/trailing whitespace
                                    .filter(name => name.length > 0); // Remove empty strings

    // Get the state of the 'ignoresPlayerLimit' checkbox
    const ignoresPlayerLimit = ignoreLimitCheckbox.checked;

    console.log("Processed Player names:", playerNames);
    console.log("Ignore player limit:", ignoresPlayerLimit);

    // Construct the request body
    const requestBody = {
        players: playerNames,
        ignoresPlayerLimit: ignoresPlayerLimit
    };
    console.log("Constructed request body for saving allowlist:", requestBody);

    // Call the action helper, targeting the allowlist API endpoint (absolute path)
    console.log("Calling sendServerActionRequest to save allowlist...");
    sendServerActionRequest(null, `/api/server/${serverName}/allowlist`, 'POST', requestBody, buttonElement)
        .then(apiResponseData => { // Check the actual response data object
             console.log("saveAllowlist API call completed. Response data:", apiResponseData);
             // Check if the API call was successful (returned data object with status 'success')
             if (apiResponseData && apiResponseData.status === 'success') {
                 console.log("Allowlist save API call successful.");
                 if (isNewInstall) {
                     // If save was successful AND it's part of a new install, navigate to the next step
                     console.log("Allowlist saved during new install, navigating to permissions configuration after delay...");
                     // Show success message (already shown by sendServerActionRequest, but can add context)
                     showStatusMessage("Allowlist saved! Proceeding to Permissions...", "success");
                     // Short delay to allow user to read success message
                     setTimeout(() => {
                         const nextUrl = `/server/${serverName}/configure_permissions?new_install=True`;
                         console.log(`Navigating to: ${nextUrl}`);
                         window.location.href = nextUrl;
                     }, 1000); // 1 second delay
                 } else {
                      // Allowlist saved successfully, but not part of new install sequence
                      console.log("Allowlist saved successfully (not new install).");
                      // Optional: Give additional feedback or UI update if needed
                 }
             } else {
                  // API call failed (returned false) or application status was not 'success'
                  // Error message was already shown by sendServerActionRequest
                  console.log("Allowlist save failed or application status was not 'success'. No navigation.");
             }
        });
    console.log("Returned from initiating sendServerActionRequest call for save allowlist (async).");
}


/**
 * Gathers player names from the 'add players' form section and adds them to the allowlist via API.
 * Refreshes the displayed allowlist on success.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 */
function addAllowlistPlayers(buttonElement, serverName) {
    // Log function entry
    console.log(`addAllowlistPlayers called - Server: ${serverName}, Button:`, buttonElement);

    // Get references to form elements for adding players
    const textArea = document.getElementById('player-names-add');
    const ignoreLimitCheckbox = document.getElementById('ignore-limit-add');

    // Validate that elements were found
    if (!textArea || !ignoreLimitCheckbox) {
        console.error("Required elements ('player-names-add' textarea or 'ignore-limit-add' checkbox) not found!");
        showStatusMessage("Internal page error: Form elements missing.", "error");
        return;
    }
    console.log("Found 'add players' form elements.");

    // Get player names from textarea: split, trim, filter empty
    const playerNamesRaw = textArea.value;
    const playersToAdd = playerNamesRaw.split('\n')
                                    .map(name => name.trim())
                                    .filter(name => name.length > 0);

    // Check if any player names were actually entered
    if (playersToAdd.length === 0) {
         console.warn("No player names entered in the 'add players' textarea.");
         showStatusMessage("Please enter at least one player name to add.", "warning");
         return; // Don't send request if list is empty
    }

    // Get the state of the 'ignoresPlayerLimit' checkbox for the added players
    const ignoresPlayerLimit = ignoreLimitCheckbox.checked;

    console.log("Players to add:", playersToAdd);
    console.log("Ignore player limit for added players:", ignoresPlayerLimit);

    // Construct the request body
    const requestBody = {
        players: playersToAdd,
        ignoresPlayerLimit: ignoresPlayerLimit // Backend needs to handle applying this to the new players
    };
    console.log("Constructed request body for adding players:", requestBody);

    // Call sendServerActionRequest targeting the ADD endpoint
    console.log("Calling sendServerActionRequest to add players to allowlist...");
    sendServerActionRequest(null, `/api/server/${serverName}/allowlist/add`, 'POST', requestBody, buttonElement)
        .then(apiResponseData => { // Check the actual response data object
            console.log("addAllowlistPlayers API call completed. Response data:", apiResponseData);
             // Check if the API call was successful (returned data object with status 'success')
            if (apiResponseData && apiResponseData.status === 'success') {
                console.log("Add players API call successful.");
                // Clear the textarea after successful submission
                console.log("Clearing 'add players' textarea.");
                textArea.value = '';
                // Optionally uncheck the 'ignore limit' box for the next add operation
                // ignoreLimitCheckbox.checked = false; // Uncomment if desired behavior

                // Refresh the display of the current allowlist
                console.log("Initiating fetch and update for allowlist display.");
                fetchAndUpdateAllowlistDisplay(serverName); // Call helper to update UI

            } else {
                 // API call failed or application status was not 'success'
                 // Error message already shown by sendServerActionRequest
                 console.log("Adding players failed or application status was not 'success'.");
            }
        });
    console.log("Returned from initiating sendServerActionRequest call for add allowlist players (async).");
}

/**
 * Helper function to fetch the current allowlist from the API and update the display section on the page.
 * Assumes a specific HTML structure for the display list (`#current-allowlist-display` UL/OL and potentially `#no-players-message` LI).
 * @param {string} serverName The name of the server whose allowlist needs to be displayed.
 */
async function fetchAndUpdateAllowlistDisplay(serverName) {
     console.log(`fetchAndUpdateAllowlistDisplay called for server: ${serverName}`);
     const displayList = document.getElementById('current-allowlist-display'); // The UL or OL element
     const noPlayersLi = document.getElementById('no-players-message'); // The LI shown when list is empty

     // Check if the main display list element exists
     if (!displayList) {
         console.error("Allowlist display element '#current-allowlist-display' not found. Cannot update UI.");
         return;
     }
     console.log("Found allowlist display element.");

     try {
        // Fetch the current allowlist data using a GET request to the allowlist API endpoint
        console.log(`Fetching current allowlist from /api/server/${serverName}/allowlist`);
        // Assuming the API endpoint `/api/server/<server_name>/allowlist` handles GET requests to return the list
        const response = await fetch(`/api/server/${serverName}/allowlist`); // GET request is default

        if (!response.ok) {
            // Handle HTTP errors during fetch
            console.error(`Failed to fetch allowlist. Status: ${response.status}, StatusText: ${response.statusText}`);
            throw new Error(`Failed to fetch allowlist (Status: ${response.status})`);
        }

        // Parse the JSON response
        console.log("Allowlist fetch successful, parsing JSON response.");
        const data = await response.json();
        console.log("Parsed allowlist data:", data);

        // Check if the response indicates success and contains the expected player data
        if (data.status === 'success' && Array.isArray(data.existing_players)) { // Check if existing_players is an array
            console.log(`Successfully fetched ${data.existing_players.length} players from allowlist.`);
            // Clear current list items, but preserve the 'no players' message element if it exists
            console.log("Clearing existing allowlist entries from display (excluding 'no players' message).");
            displayList.querySelectorAll('li:not(#no-players-message)').forEach(li => li.remove());

            if (data.existing_players.length > 0) {
                 // If players exist, hide or remove the 'no players' message
                 if (noPlayersLi) {
                     console.log("Hiding 'no players' message.");
                     noPlayersLi.style.display = 'none';
                 }
                 // Add new list items for each player
                 console.log("Adding fetched players to the display list.");
                 data.existing_players.forEach(player => {
                     const li = document.createElement('li');
                     // Display player name and whether they ignore the player limit
                     li.textContent = `${player.name} (Ignores Limit: ${player.ignoresPlayerLimit ? 'Yes' : 'No'})`; // Improved display
                     // Optionally add data attributes or classes if needed for styling/interaction
                     // li.dataset.xuid = player.xuid; // If XUID is available and needed
                     displayList.appendChild(li);
                 });
            } else {
                 // If no players exist, ensure the 'no players' message is visible
                 console.log("No players in fetched allowlist. Ensuring 'no players' message is visible.");
                 if (noPlayersLi) {
                     console.log("Showing existing 'no players' message.");
                     noPlayersLi.style.display = ''; // Make existing message visible
                 } else {
                     // If the 'no players' message element doesn't exist, create and add it
                     console.warn("Creating 'no players' message element as it was not found.");
                     const li = document.createElement('li');
                     li.id = 'no-players-message'; // Assign ID for future reference
                     li.textContent = 'No players currently in allowlist.';
                     displayList.appendChild(li);
                 }
            }
            console.log("Allowlist display updated successfully.");
        } else {
             // Handle cases where the API response format is unexpected or indicates failure
             console.error("Failed to get valid allowlist data from API response:", data.message || 'Unknown API error or invalid format.');
             showStatusMessage("Could not refresh the current allowlist display (invalid data).", "warning");
        }

     } catch (error) {
          // Handle network errors or errors during JSON parsing/processing
          console.error("Error during fetch or update of allowlist display:", error);
          showStatusMessage("Error refreshing the current allowlist display.", "error");
     }
}


/**
 * Gathers server property data from the form and saves it via API.
 * Handles navigation to the next step if part of a new server installation sequence.
 * Clears previous validation errors before sending the request.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function saveProperties(buttonElement, serverName, isNewInstall) {
    // Log function entry
    console.log(`saveProperties called - Server: ${serverName}, NewInstall: ${isNewInstall}, Button:`, buttonElement);

    // --- गैदर Form Data ---
    const propertiesData = {}; // Object to hold property key-value pairs
    // List the IDs of the input/select elements whose values need to be collected
    // These IDs should ideally match the 'name' attributes used by the backend
    const propertyIds = [
        'server-name', 'level-name', 'gamemode', 'difficulty', 'allow-cheats',
        'max-players', 'server-port', 'server-portv6', 'enable-lan-visibility',
        'allow-list', 'default-player-permission-level', 'view-distance',
        'tick-distance', 'level-seed', 'online-mode', 'texturepack-required'
        // Add any other property IDs from your server.properties form here
    ];

    console.log("Gathering data from property form elements:", propertyIds);
    propertyIds.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            // Use the element's 'name' attribute as the key if available, otherwise fallback to ID
            // This ensures keys match what the backend expects based on form names
            const propertyName = element.getAttribute('name') || id;
            let value = element.value; // Get the value

            // --- Value Type Handling (Example) ---
            // If you have checkboxes representing boolean values, handle them explicitly:
            // if (element.type === 'checkbox') {
            //     value = element.checked; // Send true/false instead of 'on'/'off'
            //     console.log(`Processed checkbox '${propertyName}': ${value}`);
            // } else {
            //     console.log(`Processed input/select '${propertyName}': ${value}`);
            // }

            // Assign the value to the corresponding property name in the data object
            propertiesData[propertyName] = value;
        } else {
             // Log a warning if an expected form element is not found
             console.warn(`Element with ID '${id}' not found in the properties form.`);
        }
    });

    console.log("Properties data gathered:", propertiesData);

    // --- Clear previous validation errors ---
    console.log("Clearing previous validation error messages.");
    // Clear general error message area
    const generalErrorArea = document.getElementById('validation-error-area');
    if (generalErrorArea) {
        generalErrorArea.textContent = '';
        generalErrorArea.innerHTML = ''; // Clear potential HTML content too
        console.log("Cleared general validation error area.");
    }
     // Clear specific field error placeholders
    document.querySelectorAll('.validation-error').forEach(el => {
        el.textContent = '';
    });
    console.log("Cleared specific field validation error elements.");

    // --- Call API ---
    // Use the generic action helper, targeting the properties API endpoint (absolute path)
    console.log("Calling sendServerActionRequest to save properties...");
    sendServerActionRequest(null, `/api/server/${serverName}/properties`, 'POST', propertiesData, buttonElement)
        .then(apiResponseData => { // Check the actual response data
             console.log("saveProperties API call completed. Response data:", apiResponseData);
             // Check if the API call was successful (returned data object with status 'success')
            if (apiResponseData && apiResponseData.status === 'success') {
                console.log("Properties save API call successful.");
                if (isNewInstall) {
                    // If save was successful AND it's part of a new install, navigate to the next step
                    console.log("Properties saved during new install, navigating to allowlist configuration after delay...");
                    showStatusMessage("Properties saved successfully! Proceeding to Allowlist...", "success"); // Give feedback
                    setTimeout(() => {
                        const nextUrl = `/server/${serverName}/configure_allowlist?new_install=True`;
                        console.log(`Navigating to: ${nextUrl}`);
                        window.location.href = nextUrl;
                    }, 1500); // Slightly longer delay for reading message
                } else {
                     // Properties saved successfully, but not part of new install sequence
                     console.log("Properties saved successfully (not new install).");
                     // Success message already shown by sendServerActionRequest
                }
            } else {
                 // API call failed (returned false), had validation errors, or app status wasn't 'success'
                 // Error/validation messages already shown by sendServerActionRequest
                 console.log("Properties save failed or had validation errors. No navigation.");
            }
        });
    console.log("Returned from initiating sendServerActionRequest call for save properties (async).");
}

/**
 * Gathers player permission level data from the form and saves it via API using PUT.
 * Handles navigation to the next step if part of a new server installation sequence.
 * Clears previous validation errors before sending the request.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function savePermissions(buttonElement, serverName, isNewInstall) {
    // Log function entry
    console.log(`savePermissions called - Server: ${serverName}, NewInstall: ${isNewInstall}, Button:`, buttonElement);

    // --- Gather Permissions Data ---
    const permissionsMap = {}; // Object to map XUID -> permission level string
    // Select all dropdowns with the class 'permission-select'
    const permissionSelects = document.querySelectorAll('select.permission-select');
    console.log(`Found ${permissionSelects.length} permission select elements.`);

    if (permissionSelects.length === 0) {
         console.warn("No permission select elements found on the page. Permissions data will be empty.");
    }

    // Iterate over each select element found
    permissionSelects.forEach(select => {
        // Get the player's XUID from the 'data-xuid' attribute
        const xuid = select.dataset.xuid;
        // Get the selected permission level from the dropdown's value
        const selectedLevel = select.value;
        if (xuid) {
            // If XUID exists, add the mapping to the object
            permissionsMap[xuid] = selectedLevel;
            console.log(`Mapped XUID ${xuid} to permission level '${selectedLevel}'`);
        } else {
             // Log a warning if a select element is missing the data attribute
             console.warn("Found permission select element without a data-xuid attribute:", select);
        }
    });

    console.log("Permissions map gathered:", permissionsMap);

    // --- Clear previous validation errors ---
    console.log("Clearing previous validation error messages.");
    const generalErrorArea = document.getElementById('validation-error-area');
    if (generalErrorArea) {
        generalErrorArea.textContent = '';
        generalErrorArea.innerHTML = '';
        console.log("Cleared general validation error area.");
    }
    document.querySelectorAll('.validation-error').forEach(el => {
        el.textContent = '';
    });
    console.log("Cleared specific field validation error elements.");


    // --- Prepare request body ---
    const requestBody = {
        permissions: permissionsMap // Send the map under the 'permissions' key
    };
    console.log("Constructed request body for saving permissions:", requestBody);

    // --- Call API ---
    // Use PUT method, as we are typically replacing the entire permissions state for listed players
    console.log("Calling sendServerActionRequest to save permissions (PUT)...");
    sendServerActionRequest(null, `/api/server/${serverName}/permissions`, 'PUT', requestBody, buttonElement)
        .then(apiResponseData => { // Check the actual response data
            console.log("savePermissions API call completed. Response data:", apiResponseData);
            // Check if the API call was successful (returned data object with status 'success')
            if (apiResponseData && apiResponseData.status === 'success') {
                console.log("Permissions save API call successful.");
                if (isNewInstall) {
                    // If save was successful AND it's part of a new install, navigate to the next step
                    console.log("Permissions saved during new install, navigating to service configuration after delay...");
                    showStatusMessage("Permissions saved successfully! Proceeding to Service Config...", "success");
                    setTimeout(() => {
                        const nextUrl = `/server/${serverName}/configure_service?new_install=True`;
                        console.log(`Navigating to: ${nextUrl}`);
                        window.location.href = nextUrl;
                    }, 1500);
                } else {
                     // Permissions saved successfully, but not part of new install sequence
                     console.log("Permissions saved successfully (not new install).");
                     // Success message already shown by sendServerActionRequest
                }
            } else {
                 // API call failed, had validation errors, or app status wasn't 'success'
                 // Error messages (including validation) shown by sendServerActionRequest
                 console.log("Permissions save failed or had validation errors. No navigation.");
            }
        });
    console.log("Returned from initiating sendServerActionRequest call for save permissions (async).");
}


/**
 * Gathers service settings (like autostart, autoupdate) from the form and saves them via API.
 * Optionally triggers a server start via a separate API call if `isNewInstall` is true and the user checked the 'start server' box.
 * Handles navigation to the main page upon completion if `isNewInstall` is true.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} currentOs The OS detected by the backend ('Linux', 'Windows', etc.), used to determine relevant settings.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function saveServiceSettings(buttonElement, serverName, currentOs, isNewInstall) {
    // Log function entry
    console.log(`saveServiceSettings called - Server: ${serverName}, OS: ${currentOs}, NewInstall: ${isNewInstall}, Button:`, buttonElement);

    const requestBody = {}; // Object to hold service settings
    let startServerAfter = false; // Flag to determine if server should be started after saving

    // --- Gather Data Based on OS ---
    console.log(`Gathering service settings based on OS: ${currentOs}`);
    if (currentOs === 'Linux') {
        // Gather Linux-specific settings (e.g., systemd service options)
        const autoupdateCheckbox = document.getElementById('service-autoupdate');
        const autostartCheckbox = document.getElementById('service-autostart');
        requestBody.autoupdate = autoupdateCheckbox ? autoupdateCheckbox.checked : false;
        requestBody.autostart = autostartCheckbox ? autostartCheckbox.checked : false;
        console.log(`Linux settings gathered: autoupdate=${requestBody.autoupdate}, autostart=${requestBody.autostart}`);
    } else if (currentOs === 'Windows') {
        // Gather Windows-specific settings (e.g., Scheduled Task options)
        const autoupdateCheckbox = document.getElementById('service-autoupdate');
        requestBody.autoupdate = autoupdateCheckbox ? autoupdateCheckbox.checked : false;
        // Note: Autostart might be implicitly handled by service creation or other means on Windows,
        // so it might not have a dedicated checkbox in this specific form.
        console.log(`Windows settings gathered: autoupdate=${requestBody.autoupdate}`);
    } else {
        // Handle unsupported OS provided by backend (should ideally not happen if UI matches backend logic)
        console.error(`Unsupported OS detected: ${currentOs}. Cannot determine service settings.`);
        showStatusMessage("Cannot save settings: Unsupported operating system detected.", "error");
        return; // Stop execution
    }

    // Check if server should be started afterwards (only relevant during new install sequence)
    if (isNewInstall) {
        const startServerCheckbox = document.getElementById('service-start-server');
        startServerAfter = startServerCheckbox ? startServerCheckbox.checked : false;
        console.log(`New install sequence: Checkbox 'service-start-server' checked = ${startServerAfter}`);
    } else {
        console.log("Not a new install sequence, 'start server after save' option is ignored.");
    }

    console.log("Final service settings request body:", requestBody);
    console.log("Start server after save:", startServerAfter);


    // --- Call API to Save Settings ---
    console.log("Calling sendServerActionRequest to save service settings...");
    sendServerActionRequest(null, `/api/server/${serverName}/service`, 'POST', requestBody, buttonElement)
        .then(saveSuccessData => { // Check response from saving settings
            console.log("Save service settings API call completed. Response data:", saveSuccessData);

            if (saveSuccessData && saveSuccessData.status === 'success') {
                console.log("Service settings saved successfully.");
                // Success message is shown by sendServerActionRequest

                if (startServerAfter) {
                    // If settings saved AND user requested start during new install
                    console.log("Proceeding to start server via API call as requested...");
                    showStatusMessage("Service settings saved. Attempting to start server...", "info"); // Inform user

                    // Attempt to find the generic start button on the page to disable it during start request
                    // This might not exist on this specific config page, so handle null.
                    const startButton = document.getElementById('start-server-btn'); // May be null
                    console.log("Attempting to find start button for disable:", startButton);

                    // Call the standard server start action via the helper function
                    sendServerActionRequest(serverName, 'start', 'POST', null, startButton) // Pass null if button not found
                       .then(startSuccessData => { // Check response from starting server
                           console.log("Start server API call completed. Response data:", startSuccessData);
                           if (startSuccessData && startSuccessData.status === 'success') {
                               // Server started successfully
                               console.log("Server started successfully after new install configuration.");
                               if (isNewInstall) {
                                   // Navigate to main page after successful start in new install sequence
                                   showStatusMessage("Server started successfully! Redirecting to dashboard...", "success");
                                   setTimeout(() => {
                                       console.log("Redirecting to /");
                                       window.location.href = "/";
                                    }, 2000); // Redirect after 2 seconds
                               } else {
                                   // Server started successfully (not new install) - message already shown
                               }
                           } else {
                                // Server start failed
                                console.warn("Failed to start server after saving service settings.");
                                showStatusMessage("Service settings saved, but the server failed to start. Check server logs.", "warning");
                                // Don't redirect on failure, let user see the error and potentially retry starting manually
                                // Re-enable the main save button if it wasn't re-enabled automatically
                                if (buttonElement) buttonElement.disabled = false;
                           }
                       });
                } else if (isNewInstall) {
                    // Settings saved, but user didn't request start - navigate to main page for new install
                    console.log("Service settings saved, server start not requested. Proceeding with navigation for new install.");
                    showStatusMessage("Service settings saved! Redirecting to dashboard...", "success");
                    setTimeout(() => {
                        console.log("Redirecting to /");
                        window.location.href = "/";
                    }, 1500); // Redirect after 1.5 seconds
                } else {
                     // Settings saved successfully (not new install) - nothing more to do here
                     console.log("Service settings saved successfully (not new install).");
                }
            } else {
                 // Saving service settings failed
                 console.error("Saving service settings failed. API response indicated failure or error.");
                 // Error message already shown by sendServerActionRequest
                 // Button should have been re-enabled by sendServerActionRequest
            }
        });
    console.log("Returned from initiating sendServerActionRequest call for save service settings (async).");
}


/**
 * Triggers the server installation process via API.
 * Handles backend response indicating if an overwrite confirmation is needed.
 * Sends a second request with `overwrite: true` if confirmed by the user.
 * Navigates to the first configuration step upon successful installation.
 * @param {HTMLElement} buttonElement The button that was clicked.
 */
function triggerInstallServer(buttonElement) {
    // Log function entry
    console.log("triggerInstallServer called. Button:", buttonElement);

    // Get references to input elements
    const serverNameInput = document.getElementById('install-server-name');
    const serverVersionInput = document.getElementById('install-server-version');

    // Validate that elements were found
    if (!serverNameInput || !serverVersionInput) {
        console.error("Required input elements ('install-server-name', 'install-server-version') not found!");
        showStatusMessage("Internal page error: Form elements missing.", "error");
        return;
    }
    console.log("Found install form input elements.");

    // Get and trim input values
    const serverName = serverNameInput.value.trim();
    const serverVersion = serverVersionInput.value.trim();
    console.log(`Server Name entered: "${serverName}", Server Version entered: "${serverVersion}"`);

    // --- Basic Frontend Validation ---
    if (!serverName) {
        console.warn("Validation failed: Server name is empty.");
        showStatusMessage('Server name cannot be empty.', 'warning');
        return;
    }
    if (!serverVersion) {
        console.warn("Validation failed: Server version is empty.");
        showStatusMessage('Server version cannot be empty.', 'warning');
        return;
    }
    // Example: Prevent potentially problematic characters in server names (like path separators or shell metacharacters)
    if (serverName.includes('/') || serverName.includes('\\') || serverName.includes(';') || serverName.includes('&') || serverName.includes('|')) {
        console.warn("Validation failed: Server name contains invalid characters.");
        showStatusMessage('Server name contains invalid characters (e.g., /, \\, ;, &, |). Please use a simple name.', 'error');
        return;
    }
    console.log("Frontend validation passed.");

    // --- Clear previous validation errors ---
    console.log("Clearing previous validation error messages.");
    const generalErrorArea = document.getElementById('validation-error-area');
    if (generalErrorArea) {
        generalErrorArea.textContent = '';
        generalErrorArea.innerHTML = '';
        console.log("Cleared general validation error area.");
    }
    document.querySelectorAll('.validation-error').forEach(el => {
        el.textContent = '';
    });
    console.log("Cleared specific field validation error elements.");

    // Construct the initial request body with overwrite set to false
    const requestBody = {
        server_name: serverName,
        server_version: serverVersion,
        overwrite: false // Initial request assumes no overwrite
    };
    console.log("Constructed initial install request body:", requestBody);

    // --- Initial API Call (Attempt install without overwrite) ---
    console.log("Calling sendServerActionRequest for initial install attempt...");
    sendServerActionRequest(null, '/api/server/install', 'POST', requestBody, buttonElement)
        .then(apiResponseData => { // This holds the parsed JSON object or `false`
            console.log("Initial install API call completed. Response data:", apiResponseData);

            // Check if the API call itself failed (returned false)
            if (apiResponseData === false) {
                 console.error("Initial install API call failed at HTTP/Network level or returned false.");
                 // Button should be re-enabled by sendServerActionRequest's finally block
                 return;
            }

            // --- Handle Application-Level Status from Response ---

            if (apiResponseData.status === 'confirm_needed') {
                // --- Handle Confirmation Needed for Overwrite ---
                console.log("Server response indicates confirmation needed (likely server exists). Message:", apiResponseData.message);
                // Prompt the user with the message from the backend
                if (confirm(apiResponseData.message || `Server '${serverName}' already exists. Overwrite all its files? THIS CANNOT BE UNDONE.`)) {
                    // User confirmed overwrite
                    console.log("Overwrite confirmed by user. Preparing second API request with overwrite: true.");
                    showStatusMessage("Overwrite confirmed. Re-attempting installation...", "info"); // Inform user

                    // Construct request body for overwrite
                    const overwriteRequestBody = {
                        server_name: serverName,
                        server_version: serverVersion, // Send version again just in case
                        overwrite: true // Set overwrite flag
                    };
                    console.log("Constructed overwrite install request body:", overwriteRequestBody);

                    // --- Second API Call (Attempt install WITH overwrite) ---
                    console.log("Calling sendServerActionRequest for overwrite install attempt...");
                    // Pass the same button element to disable during the second request
                    sendServerActionRequest(null, '/api/server/install', 'POST', overwriteRequestBody, buttonElement)
                        .then(finalApiResponseData => { // Response from the second (overwrite) call
                            console.log("Overwrite install API call completed. Response data:", finalApiResponseData);

                            // Check if the second call failed at HTTP/Network level
                            if (finalApiResponseData === false) {
                                console.error("Install/Overwrite (second call) failed at HTTP/Network level or returned false.");
                                // Button should be re-enabled by sendServerActionRequest
                                return;
                            }

                            // Check application status *within* the second response object
                            if (finalApiResponseData.status === 'success') {
                                // --- Success on Overwrite Install ---
                                console.log("Install/Overwrite successful (application status: success).");
                                // Check for the next step URL provided in the *successful overwrite response*
                                const nextUrl = finalApiResponseData.next_step_url;
                                console.log("Extracted next_step_url from overwrite response:", nextUrl);

                                if (nextUrl) {
                                    console.log("Navigating to configuration sequence after successful overwrite...");
                                    showStatusMessage("Server installed (overwrite successful)! Proceeding to configuration...", "success");
                                    setTimeout(() => {
                                        console.log(`Navigating to: ${nextUrl}`);
                                        window.location.href = nextUrl;
                                    }, 1500); // Delay for user to read message
                                } else {
                                     console.warn("Install/Overwrite successful, but no next_step_url provided in the final response. Staying on page.");
                                     showStatusMessage("Server installed (overwrite successful)! Configuration URL missing.", "warning");
                                     // Button should be re-enabled by sendServerActionRequest
                                }
                            } else {
                                 // Overwrite attempt failed at the application level (e.g., permissions error during overwrite)
                                 console.error(`Install/Overwrite failed (application status: ${finalApiResponseData.status}). Message: ${finalApiResponseData.message}`);
                                 // Error message already shown by sendServerActionRequest based on finalApiResponseData
                                 // Button should be re-enabled by sendServerActionRequest
                            }
                        }); // End of .then() for second API call

                } else { // User cancelled the confirmation dialog
                    console.log("Overwrite cancelled by user.");
                    showStatusMessage("Installation cancelled (overwrite not confirmed).", "info");
                    // Manually re-enable the button because sendServerActionRequest kept it disabled for 'confirm_needed'
                    if (buttonElement) {
                        console.log("Re-enabling button after user cancelled confirmation.");
                        buttonElement.disabled = false;
                    }
                }
            } else if (apiResponseData.status === 'success') {
                 // --- Handle Direct Success (New Install, no overwrite needed) ---
                 console.log("New install successful (application status: success).");
                 // Check for the next step URL provided in the *initial successful response*
                 const nextUrl = apiResponseData.next_step_url;
                 console.log("Extracted next_step_url from initial response:", nextUrl);

                 if (nextUrl) {
                      console.log("Navigating to configuration sequence after successful new install...");
                      showStatusMessage("Server installed successfully! Proceeding to configuration...", "success");
                      setTimeout(() => {
                          console.log(`Navigating to: ${nextUrl}`);
                          window.location.href = nextUrl;
                      }, 1500); // Delay for user to read message
                 } else {
                      console.warn("New install successful, but no next_step_url provided in the initial response. Staying on page.");
                      showStatusMessage("Server installed successfully! Configuration URL missing.", "warning");
                      // Button should be re-enabled by sendServerActionRequest
                 }
            } else {
                 // --- Handle other non-success, non-confirm_needed statuses from initial call ---
                 // e.g., validation errors ('validation_error'), general errors ('error')
                 console.error(`Initial install attempt failed (application status: ${apiResponseData.status}). Message: ${apiResponseData.message}`);
                 // Error/validation messages should have been displayed by sendServerActionRequest
                 // Button should be re-enabled by sendServerActionRequest
            }
        }); // End of .then() for initial API call
    console.log("Returned from initiating sendServerActionRequest call for trigger install server (async).");
}


/**
 * Triggers the 'update' action for a specific server via API.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server to update.
 */
function triggerServerUpdate(buttonElement, serverName) {
    console.log(`triggerServerUpdate called for server: ${serverName}`);
    if (serverName) {
        // Call sendServerActionRequest:
        // - serverName: The name passed from the button
        // - actionPath: 'update' (matches the part of the URL after the server name)
        // - method: 'POST' (matches the method required by the Flask route)
        // - body: null (the update route doesn't need data in the body)
        // - buttonElement: Pass the button so it gets disabled during the request
        sendServerActionRequest(serverName, 'update', 'POST', null, buttonElement);
    } else {
        console.error("triggerServerUpdate called without serverName.");
        showStatusMessage("Error: Server name missing for update action.", "error");
    }
}