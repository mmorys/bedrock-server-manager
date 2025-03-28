// bedrock_server_manager/web/static/js/scripts.js
// --- Helper: Display Status Messages ---
/**
 * Displays a status message in the dedicated area.
 * @param {string} message The message text.
 * @param {string} type 'info', 'success', 'error', or 'warning'.
 */
function showStatusMessage(message, type = 'info') {
    // Ensure the status message area exists in your HTML (e.g., <div id="status-message-area"></div>)
    const area = document.getElementById('status-message-area');
    if (!area) {
        console.warn("Element with ID 'status-message-area' not found. Falling back to alert.");
        alert(`${type.toUpperCase()}: ${message}`);
        return;
    }
    area.className = `message-box message-${type}`;
    area.textContent = message;
    area.style.opacity = '1'; // Ensure it's visible

    setTimeout(() => {
        // Only clear if the message hasn't been replaced by another one
        if (area.textContent === message) {
            // Optional fade out effect
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
 * Sends an asynchronous POST request to a server action endpoint.
 * @param {string} serverName The name of the target server.
 * @param {string} action The action to perform ('start', 'stop', 'restart', 'send', 'update').
 * @param {object|null} body Optional JSON body for the request (used for 'send').
 * @param {HTMLElement|null} buttonElement Optional button element to disable during request.
 */
async function sendServerActionRequest(serverName, action, body = null, buttonElement = null) {
    const url = `/server/${serverName}/${action}`;
    console.log(`API Request: ${action} for ${serverName}, URL: ${url}, Body:`, body);
    showStatusMessage(`Sending ${action} request for ${serverName}...`, 'info');

    if (buttonElement) buttonElement.disabled = true; // Disable button if provided

    try {
        const fetchOptions = {
            method: 'POST',
            headers: {
                'Accept': 'application/json'
            }
        };

        // Add Content-Type and body only if body is provided
        if (body) {
            fetchOptions.headers['Content-Type'] = 'application/json';
            fetchOptions.body = JSON.stringify(body);
        }

        const response = await fetch(url, fetchOptions);
        console.log(`Fetch response received: Status=${response.status}`, response);

        // Try to parse JSON, but handle non-JSON responses gracefully
        let data;
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            data = await response.json();
            console.log(`Parsed JSON data:`, data);
        } else {
            // If not JSON, read as text and include in error message
            const textResponse = await response.text();
            console.warn("Response was not JSON:", textResponse);
             // Still check response.ok for HTTP status
             if (!response.ok) {
                 // Create a generic error message including status and text snippet
                 throw new Error(`Request failed (Status ${response.status}): ${textResponse.substring(0, 150)}...`);
             } else {
                 // Non-JSON 2xx response might be okay in some cases, or indicate an issue
                 showStatusMessage(`Received OK status (${response.status}) but unexpected response format for ${action}. Check console/server logs.`, 'warning');
                 return; // Exit processing for this case if unexpected
             }
        }

        // Handle potential HTTP errors even if JSON was parsed
        if (!response.ok) {
            // Use message from JSON if available, otherwise use a generic one
            const errorMessage = data?.message || `Request failed with status ${response.status}`;
            throw new Error(errorMessage);
        }

        // Handle application-level success/error status in the JSON response
        if (data.status === 'success') {
            showStatusMessage(data.message || `Server ${serverName} ${action} action successful.`, 'success');
             // TODO: Optionally refresh server status display here dynamically
             // Example: refreshServerStatusTable();
        } else {
            showStatusMessage(data.message || `Failed to ${action} server ${serverName}. See server logs.`, 'error');
        }

    } catch (error) {
        // Handle network errors or errors thrown during response processing
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

function startServer(buttonElement) { // Pass the button element itself
    console.log("startServer() called");
    const serverName = getSelectedServer();
    if (serverName) {
        sendServerActionRequest(serverName, 'start', null, buttonElement);
    }
}

function stopServer(buttonElement) {
    console.log("stopServer() called");
    const serverName = getSelectedServer();
    if (serverName) {
        sendServerActionRequest(serverName, 'stop', null, buttonElement);
    }
}

function restartServer(buttonElement) {
    console.log("restartServer() called");
    const serverName = getSelectedServer();
    if (serverName) {
        sendServerActionRequest(serverName, 'restart', null, buttonElement);
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

    // Call the helper with the 'send' action and the command in the body
    sendServerActionRequest(serverName, 'send', { command: trimmedCommand }, buttonElement);
}


function confirmDelete(serverName) {
    if (confirm(`Are you sure you want to delete server '${serverName}'? This action is irreversible!`)) {
        console.log(`Confirmed deletion for ${serverName}, creating and submitting form...`);
        var form = document.createElement('form');
        form.method = 'POST';
        form.action = `/server/${serverName}/delete`;

        document.body.appendChild(form);
        form.submit();
    } else {
        console.log(`Deletion cancelled for ${serverName}.`);
    }
}