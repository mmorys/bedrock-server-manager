// bedrock-server-manager/bedrock_server_manager/web/static/js/utils.js

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
        url = `/api/server/${serverName}/${actionPath}`;
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