// bedrock_server_manager/web/static/js/monitor_usage.js
// ------------------------------------------------------
// This script monitors the status (CPU, Memory, Uptime, PID) of a specific
// Bedrock server instance by periodically fetching data from the backend API
// and updating the information displayed on the web page.
//
// Assumes 'serverName' is defined globally or within the scope where this script runs
// (e.g., embedded in an HTML template).

/**
 * @function updateStatus
 * @description Fetches the current server status (PID, CPU, Memory, Uptime) from the API
 *              and updates the content of the '#status-info' element on the page.
 *              Handles successful responses, API-reported errors, and network/fetch errors.
 */
function updateStatus() {
    // Log the start of the function execution, including the target server
    // Note: 'serverName' must be accessible in this scope
    if (typeof serverName === 'undefined') {
        console.error(`[${new Date().toISOString()}] updateStatus: CRITICAL - 'serverName' variable is not defined.`);
        // Optionally update the status element to indicate this critical configuration error
        const statusElement = document.getElementById('status-info');
        if (statusElement) {
            statusElement.textContent = "Configuration Error: serverName not set.";
        }
        return; // Stop execution if serverName is missing
    }
    console.log(`[${new Date().toISOString()}] updateStatus: Initiating status fetch for server: ${serverName}`);

    // Construct the API endpoint URL
    const apiUrl = `/api/server/${serverName}/status`;
    console.debug(`[${new Date().toISOString()}] updateStatus: Fetching URL: ${apiUrl}`); // Log the specific URL being requested

    // Perform the asynchronous fetch request
    fetch(apiUrl)
        .then(response => {
            // Log the HTTP status received
            console.debug(`[${new Date().toISOString()}] updateStatus: Received response status: ${response.status} ${response.statusText}`);

            // Check if the request was successful (status code 200-299)
            if (!response.ok) {
                // If not successful, throw an error to be caught by the .catch() block
                // Include status text for more context if available
                throw new Error(`HTTP error! Status: ${response.status} ${response.statusText}`);
            }
            // If successful, parse the JSON body of the response
            return response.json();
        })
        .then(data => {
            // Log the parsed data received from the API for debugging
            console.debug(`[${new Date().toISOString()}] updateStatus: Received data:`, data);

            // Get the target DOM element to display the status
            const statusElement = document.getElementById('status-info');

            // CRITICAL CHECK: Ensure the target element exists in the DOM
            if (!statusElement) {
                console.error(`[${new Date().toISOString()}] updateStatus: Error - Target element '#status-info' not found in the DOM.`);
                return; // Stop processing if the element is missing
            }

            // Check the status field within the API response data
            if (data.status === 'success' && data.process_info) {
                // API call was successful, and process info is present
                const info = data.process_info;

                // Format the process information for display
                // .toFixed(1) formats numbers to one decimal place
                // .trim() removes leading/trailing whitespace from the template literal string
                const statusText = `
PID:          ${info.pid !== null ? info.pid : 'N/A'}
CPU Usage:    ${info.cpu_percent !== null ? info.cpu_percent.toFixed(1) + '%' : 'N/A'}
Memory Usage: ${info.memory_mb !== null ? info.memory_mb.toFixed(1) + ' MB' : 'N/A'}
Uptime:       ${info.uptime !== null ? info.uptime : 'N/A'}
                        `.trim();

                // Update the text content of the status element
                statusElement.textContent = statusText;
                console.log(`[${new Date().toISOString()}] updateStatus: Successfully updated status display for server ${serverName}.`);

            } else {
                // API call was technically successful (HTTP 2xx) but reported an error condition
                const errorMessage = `Error: ${data.message || 'Unknown API error'}`;
                statusElement.textContent = errorMessage;
                // Log a warning as this is an expected error path from the API's perspective
                console.warn(`[${new Date().toISOString()}] updateStatus: API reported error for server ${serverName}: ${data.message || '(No message provided)'}`);
            }
        })
        .catch(error => {
            // Handle errors during the fetch operation (e.g., network issues, DNS errors, CORS problems)
            // or errors thrown from the .then() blocks (like the !response.ok check)
            console.error(`[${new Date().toISOString()}] updateStatus: Failed to fetch or process server status for ${serverName}:`, error);

            // Attempt to update the status element with an error message for the user
            const statusElement = document.getElementById('status-info');
            if (statusElement) {
                // Provide a user-friendly error message
                statusElement.textContent = `Error fetching server status. Check console for details.`;
            } else {
                // Log if the element is missing even during error handling
                 console.error(`[${new Date().toISOString()}] updateStatus: Critical error - Element '#status-info' not found during error handling.`);
            }
        });
}

// Add an event listener that runs when the initial HTML document has been completely loaded and parsed
document.addEventListener('DOMContentLoaded', function() {
    // Log that the monitoring script is initializing
    console.log(`[${new Date().toISOString()}] DOMContentLoaded: Initializing server status monitoring.`);

    // Perform an initial status update immediately when the page loads
    console.log(`[${new Date().toISOString()}] DOMContentLoaded: Performing initial status update.`);
    updateStatus();

    // Set up a recurring timer (interval) to call updateStatus repeatedly
    const updateIntervalMilliseconds = 2000; // Update every 2 seconds
    console.log(`[${new Date().toISOString()}] DOMContentLoaded: Setting status update interval to ${updateIntervalMilliseconds}ms.`);
    setInterval(updateStatus, updateIntervalMilliseconds);
});