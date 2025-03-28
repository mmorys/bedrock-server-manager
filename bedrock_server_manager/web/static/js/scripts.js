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
 * @param {string} serverName The name of the target server.
 * @param {string} action The action ('start', 'stop', 'restart', 'send', 'update', 'delete').
 * @param {string} method The HTTP method ('POST', 'DELETE', etc.). Defaults to 'POST'.
 * @param {object|null} body Optional JSON body for the request (used for 'send').
 * @param {HTMLElement|null} buttonElement Optional button element to disable during request.
 */
async function sendServerActionRequest(serverName, action, method = 'POST', body = null, buttonElement = null) {
    // Construct URL carefully, handling potential 'delete' action which might not be part of the standard path structure
    let url;
    if (action === 'delete') {
        url = `/server/${serverName}/delete`; // Specific URL for delete
    } else {
        url = `/server/${serverName}/${action}`; // Standard URL structure
    }

    console.log(`API Request: ${method} ${action} for ${serverName}, URL: ${url}, Body:`, body);
    showStatusMessage(`Sending ${action} request for ${serverName}...`, 'info');

    if (buttonElement) buttonElement.disabled = true; // Disable button if provided

    try {
        const fetchOptions = {
            method: method, // Use the provided method
            headers: {
                'Accept': 'application/json',

            }
        };

        // Add Content-Type and body only if body is provided
        if (body && (method === 'POST' || method === 'PUT')) {
            fetchOptions.headers['Content-Type'] = 'application/json';
            fetchOptions.body = JSON.stringify(body);
        }

        const response = await fetch(url, fetchOptions);
        console.log(`Fetch response received: Status=${response.status}`, response);

        // Try to parse JSON, handle non-JSON and check response.ok
        let data;
        const contentType = response.headers.get('content-type');

        // Handle 204 No Content specifically (common success for DELETE)
        if (response.status === 204) {
             console.log("Received 204 No Content - treating as success.");
             // Create a success object similar to what the backend might send
             data = { status: 'success', message: `Server ${serverName} ${action} successful.` };
        } else if (contentType && contentType.includes('application/json')) {
            // If response has JSON content type, parse it
            data = await response.json();
            console.log(`Parsed JSON data:`, data);
        } else {
            // Handle non-JSON responses
            const textResponse = await response.text();
            console.warn("Response was not JSON or 204:", textResponse);
            if (!response.ok) { // If status code indicates error
                throw new Error(`Request failed (Status ${response.status}): ${textResponse.substring(0, 150)}...`);
            } else { // If status code is 2xx but content is not JSON (and not 204)
                // Treat as warning, might need specific handling depending on API design
                showStatusMessage(`Received OK status (${response.status}) but unexpected response format for ${action}. Check console/server logs.`, 'warning');
                // Consider returning here if this state is unexpected/unrecoverable
                return;
            }
        }

        // Check response.ok *again* in case the non-JSON response parsing logic didn't throw
        if (!response.ok) {
            // Use message from JSON if available, otherwise use a generic one
            const errorMessage = data?.message || `Request failed with status ${response.status}`;
            throw new Error(errorMessage);
        }

        // Handle application-level success/error status in the data object
        if (data.status === 'success') {
            showStatusMessage(data.message || `Server ${serverName} ${action} action successful.`, 'success');

            // --- UI Update after successful delete ---
            if (action === 'delete') {
                // Attempt to remove the row dynamically
                let row = buttonElement ? buttonElement.closest('tr') : null;
                if (row) {
                    console.log("Attempting to remove table row for deleted server:", row);
                    row.style.transition = 'opacity 0.5s ease-out';
                    row.style.opacity = '0';
                    setTimeout(() => { row.remove(); }, 500); // Remove after fade
                } else {
                    console.warn("Could not find table row (tr) for the button. Reloading page instead.");
                    // Fallback if row couldn't be found - reload needed
                    showStatusMessage(`Server ${serverName} deleted. Reloading list...`, 'success');
                    setTimeout(() => { window.location.reload(); }, 1500); // Reload after 1.5 secs
                }
            }
        } else {
            // Handle failure status from JSON response ('status' != 'success')
            showStatusMessage(data.message || `Failed to ${action} server ${serverName}. See server logs.`, 'error');
        }

    } catch (error) {
        // Handle network errors or errors thrown during fetch/response processing
        console.error(`Error during ${action} request for ${serverName}:`, error);
        // Display the message property of the caught error object
        showStatusMessage(`Error performing ${action} on server ${serverName}: ${error.message}`, 'error');
    } finally {
        // Re-enable button if it was provided
        if (buttonElement) buttonElement.disabled = false;
    }
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