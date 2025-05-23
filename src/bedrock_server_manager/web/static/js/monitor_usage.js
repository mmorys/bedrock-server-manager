// bedrock-server-manager/bedrock_server_manager/web/static/js/monitor_usage.js
/**
 * @fileoverview Frontend JavaScript for the server resource usage monitor page.
 * Periodically fetches status (CPU, Memory, Uptime, PID) for a specific server
 * from the backend API and updates the designated display area on the page.
 *
 * @requires serverName - A global JavaScript variable (typically set via Jinja2 template)
 *                         containing the name of the server to monitor.
 * @requires utils.js - Assumed implicitly if status messages beyond console logs are needed,
 *                     but this script primarily updates a dedicated element.
 */

// --- Initialization checks ---
// Although serverName check is inside updateStatus, a check here could prevent intervals starting unnecessarily.
// if (typeof serverName === 'undefined') {
//     console.error(`[${new Date().toISOString()}] Monitor Script Error: Global 'serverName' is not defined. Monitoring cannot start.`);
//     // Optionally alert the user or display a static error message
//     const statusElement = document.getElementById('status-info');
//     if (statusElement) statusElement.textContent = "Error: Server name not specified for monitoring.";
// }

/**
 * Fetches the current server resource usage status from the API
 * and updates the content of the '#status-info' DOM element.
 * This function is intended to be called repeatedly by `setInterval`.
 * Handles API success, API errors, and network/fetch errors gracefully.
 * @async
 */
async function updateStatus() {
    const timestamp = new Date().toISOString();
    const functionName = 'updateStatus';

    // --- Pre-check: Ensure serverName is defined ---
    // This check is crucial as the interval will keep calling this function.
    if (typeof serverName === 'undefined' || !serverName) {
        // Log error only once maybe? Or rely on initial check outside interval.
        // For robustness, keep check here but maybe reduce logging frequency if needed.
        console.error(`[${timestamp}] ${functionName}: CRITICAL - 'serverName' variable is not defined or empty. Cannot fetch status.`);
        const statusElement = document.getElementById('status-info');
        if (statusElement) { statusElement.textContent = "Configuration Error: Server name missing."; }
        // Consider clearing the interval if this state persists?
        // clearInterval(statusIntervalId); // Need interval ID reference
        return;
    }

    console.debug(`[${timestamp}] ${functionName}: Initiating status fetch for server: '${serverName}'`);

    // --- Get Target DOM Element ---
    const statusElement = document.getElementById('status-info');
    if (!statusElement) {
        console.error(`[${timestamp}] ${functionName}: Error - Target display element '#status-info' not found in the DOM. Cannot update status.`);
        // Consider clearing interval if the target element disappears?
        return; // Cannot proceed without the display element
    }

    // --- Fetch Data ---
    const apiUrl = `/api/server/${serverName}/status_info`; // Corrected API endpoint name based on previous refinement
    console.debug(`[${timestamp}] ${functionName}: Fetching URL: ${apiUrl}`);

    try {
        const response = await fetch(apiUrl);
        console.debug(`[${timestamp}] ${functionName}: Received response - Status: ${response.status}, OK: ${response.ok}`);

        if (!response.ok) {
            // Attempt to get more specific error info from response body if possible
            let errorDetail = `Status: ${response.status} ${response.statusText}`;
            try {
                const errorData = await response.json(); // Try parsing error response
                if (errorData && errorData.message) {
                     errorDetail += ` - ${errorData.message}`;
                }
            } catch (parseError) { /* Ignore if error response is not JSON */ }
            throw new Error(`HTTP error! ${errorDetail}`); // Throw to trigger catch block
        }

        const data = await response.json(); // Parse successful JSON response
        console.debug(`[${timestamp}] ${functionName}: Received data:`, data);

        // --- Update Display based on API Response Data ---
        if (data.status === 'success') {
            const info = data.process_info; // Process info might be null if server stopped gracefully

            if (info) {
                // Server is running, format and display stats
                const statusText = `
PID          : ${info.pid ?? 'N/A'}
CPU Usage    : ${info.cpu_percent != null ? info.cpu_percent.toFixed(1) + '%' : 'N/A'}
Memory Usage : ${info.memory_mb != null ? info.memory_mb.toFixed(1) + ' MB' : 'N/A'}
Uptime       : ${info.uptime ?? 'N/A'}
                `.trim(); // Use trim() to remove leading/trailing whitespace from template literal

                statusElement.textContent = statusText;
                console.log(`[${timestamp}] ${functionName}: Status display updated for running server '${serverName}'.`);
            } else {
                 // API call successful, but process_info is null/missing -> Server is likely stopped
                 statusElement.textContent = "Server Status: STOPPED (Process info not found)";
                 console.log(`[${timestamp}] ${functionName}: Server '${serverName}' appears to be stopped (no process info).`);
            }
        } else {
            // API call succeeded (HTTP 2xx) but reported an application-level error
            const errorMessage = `API Error: ${data.message || 'Unknown error from server API.'}`;
            statusElement.textContent = errorMessage;
            console.warn(`[${timestamp}] ${functionName}: API reported error for server '${serverName}': ${data.message || '(No message provided)'}`);
        }

    } catch (error) {
        // Handle fetch errors (network, DNS, CORS) or errors thrown above
        console.error(`[${timestamp}] ${functionName}: Failed to fetch or process server status for '${serverName}':`, error);
        statusElement.textContent = `Error fetching status: ${error.message}`; // Display error to user
    }
}

// --- Global Interval ID ---
let statusIntervalId = null; // Variable to hold the interval ID

// --- DOMContentLoaded Listener ---
document.addEventListener('DOMContentLoaded', () => {
    const timestamp = new Date().toISOString();
    const functionName = 'DOMContentLoaded (Monitor)';
    console.log(`[${timestamp}] ${functionName}: Page loaded. Initializing server status monitoring.`);

    // Check if serverName is defined *before* setting up interval
    if (typeof serverName === 'undefined' || !serverName) {
         console.error(`[${timestamp}] ${functionName}: CRITICAL - Global 'serverName' is not defined. Monitoring cannot start.`);
         const statusElement = document.getElementById('status-info');
         if (statusElement) { statusElement.textContent = "Error: Server name not specified for monitoring."; }
         return; // Exit initialization
    }

    // Perform initial update immediately
    console.log(`[${timestamp}] ${functionName}: Performing initial status update for server '${serverName}'.`);
    updateStatus(); // Call once immediately

    // Set up repeating interval
    const updateIntervalMilliseconds = 2000; // Update every 2 seconds (2000 ms)
    console.log(`[${timestamp}] ${functionName}: Setting status update interval to ${updateIntervalMilliseconds}ms.`);
    // Store the interval ID so it could potentially be cleared later if needed
    statusIntervalId = setInterval(updateStatus, updateIntervalMilliseconds);
});

// --- Optional: Clean up interval on page unload ---
// window.addEventListener('beforeunload', () => {
//     if (statusIntervalId) {
//         console.log(`[${new Date().toISOString()}] Clearing status update interval (ID: ${statusIntervalId}) on page unload.`);
//         clearInterval(statusIntervalId);
//     }
// });