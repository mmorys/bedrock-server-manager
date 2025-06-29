// bedrock_server_manager/web/static/js/monitor_usage.js
/**
 * @fileoverview Frontend JavaScript for the server resource usage monitor page.
 * Periodically fetches status (CPU, Memory, Uptime, PID) for a specific server
 * from the backend API and updates the designated display area on the page.
 *
 * @requires serverName - A global JavaScript variable (typically set via Jinja2 template)
 *                         containing the name of the server to monitor.
 * @requires utils.js - For showStatusMessage and sendServerActionRequest.
 */

// Ensure utils.js is loaded
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("CRITICAL ERROR: Missing required functions from utils.js. Ensure utils.js is loaded first.");
    // Attempt to display an error on the page if possible, though showStatusMessage might not be available
    const statusElementFallback = document.getElementById('status-info');
    if (statusElementFallback) statusElementFallback.textContent = "CRITICAL PAGE ERROR: Utilities not loaded.";
}


async function updateStatus() {
    const timestamp = new Date().toISOString();
    const functionName = 'updateStatus';

    if (typeof serverName === 'undefined' || !serverName) {
        console.error(`[${timestamp}] ${functionName}: CRITICAL - 'serverName' variable is not defined or empty. Cannot fetch status.`);
        // Use showStatusMessage if available, otherwise fallback direct DOM manipulation
        if (typeof showStatusMessage === 'function') {
            showStatusMessage("Configuration Error: Server name missing for monitoring.", "error");
        } else {
            const statusElement = document.getElementById('status-info');
            if (statusElement) { statusElement.textContent = "Configuration Error: Server name missing."; }
        }
        return;
    }

    console.debug(`[${timestamp}] ${functionName}: Initiating status fetch for server: '${serverName}'`);
    const statusElement = document.getElementById('status-info');
    if (!statusElement) {
        console.error(`[${timestamp}] ${functionName}: Error - Target display element '#status-info' not found. Cannot update status.`);
        // No point in showStatusMessage if the primary display area for it might be part of what's missing.
        return;
    }

    // Use sendServerActionRequest to fetch data
    // serverName is part of the path, actionPath is relative to /api/server/<serverName>/
    const actionPath = 'process_info';

    try {
        const data = await sendServerActionRequest(serverName, actionPath, 'GET', null, null); // No button element to disable for polling

        if (data && data.status === 'success') {
            const info = data.process_info;

            if (info) {
                const statusText = `
PID          : ${info.pid ?? 'N/A'}
CPU Usage    : ${info.cpu_percent != null ? info.cpu_percent.toFixed(1) + '%' : 'N/A'}
Memory Usage : ${info.memory_mb != null ? info.memory_mb.toFixed(1) + ' MB' : 'N/A'}
Uptime       : ${info.uptime ?? 'N/A'}
                `.trim();
                statusElement.textContent = statusText; // This is data display, not a status message
                console.log(`[${timestamp}] ${functionName}: Status display updated for running server '${serverName}'.`);
            } else {
                statusElement.textContent = "Server Status: STOPPED (Process info not found)"; // This is data display
                console.log(`[${timestamp}] ${functionName}: Server '${serverName}' appears to be stopped (no process info).`);
            }
        } else if (data && data.status === 'error') {
            // Error message already shown by sendServerActionRequest
            console.warn(`[${timestamp}] ${functionName}: API reported error for server '${serverName}': ${data.message || '(No message provided)'}`);
            // We can choose to also update the statusElement or rely on showStatusMessage
            statusElement.textContent = `API Error: ${data.message || 'Unknown error from server API.'}`;
        } else if (data === false) {
            // sendServerActionRequest returned false, indicating a fetch/network error.
            // showStatusMessage was already called by sendServerActionRequest.
            // We can update the statusElement to reflect this too.
            statusElement.textContent = "Error fetching status: Network or server error.";
            console.error(`[${timestamp}] ${functionName}: Failed to fetch server status for '${serverName}' due to network/server issue.`);
        }
    } catch (error) {
        // This catch is for unexpected errors in this function's logic itself,
        // not for API call failures handled by sendServerActionRequest.
        console.error(`[${timestamp}] ${functionName}: Unexpected error in updateStatus for '${serverName}':`, error);
        if (typeof showStatusMessage === 'function') {
            showStatusMessage(`Client-side error fetching status: ${error.message}`, "error");
        }
        statusElement.textContent = `Client-side error: ${error.message}`;
    }
}

let statusIntervalId = null;

document.addEventListener('DOMContentLoaded', () => {
    const timestamp = new Date().toISOString();
    const functionName = 'DOMContentLoaded (Monitor)';
    console.log(`[${timestamp}] ${functionName}: Page loaded. Initializing server status monitoring.`);

    if (typeof serverName === 'undefined' || !serverName) {
        console.error(`[${timestamp}] ${functionName}: CRITICAL - Global 'serverName' is not defined. Monitoring cannot start.`);
        if (typeof showStatusMessage === 'function') {
            showStatusMessage("Error: Server name not specified for monitoring. Cannot start status updates.", "error");
        } else {
            const statusElement = document.getElementById('status-info');
            if (statusElement) { statusElement.textContent = "Error: Server name not specified for monitoring."; }
        }
        return;
    }

    console.log(`[${timestamp}] ${functionName}: Performing initial status update for server '${serverName}'.`);
    updateStatus();

    const updateIntervalMilliseconds = 2000;
    console.log(`[${timestamp}] ${functionName}: Setting status update interval to ${updateIntervalMilliseconds}ms.`);
    statusIntervalId = setInterval(updateStatus, updateIntervalMilliseconds);
});

// window.addEventListener('beforeunload', () => {
//     if (statusIntervalId) {
//         console.log(`[${new Date().toISOString()}] Clearing status update interval (ID: ${statusIntervalId}) on page unload.`);
//         clearInterval(statusIntervalId);
//     }
// });