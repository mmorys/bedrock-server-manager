// bedrock-server-manager/bedrock_server_manager/web/static/js/server_actions.js

// Depends on: utils.js (showStatusMessage, sendServerActionRequest)

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
    sendServerActionRequest(serverName, 'send_command', 'POST', { command: trimmedCommand }, buttonElement);
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