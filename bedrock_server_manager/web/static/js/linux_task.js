// bedrock-server-manager/web/static/js/linux_task.js
/**
 * @fileoverview Frontend JavaScript for managing Linux cron jobs via the web UI.
 * Handles filling the form for modification, confirming deletions, submitting
 * add/modify requests, and interacting with the backend API.
 * Depends on functions defined in utils.js (showStatusMessage, sendServerActionRequest).
 */

// Ensure utils.js is loaded
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("CRITICAL ERROR: Missing required functions from utils.js. Ensure utils.js is loaded first.");
}

// Get server name from global JS variable set by Jinja2 (ensure this exists in the template)
// It's generally better to pass serverName directly to functions needing it,
// but keep this global if it's used widely in this specific file's context.
// const serverName = pageConfig.serverName; // Assumes pageConfig.serverName is set globally
// **Correction**: It seems serverName is passed to functions, so this global might not be needed.
// Will rely on serverName being passed as function arguments.

/**
 * Populates the cron job form fields with the details of an existing job
 * selected for modification by the user.
 *
 * @param {string} minute - The minute value (0-59 or '*').
 * @param {string} hour - The hour value (0-23 or '*').
 * @param {string} day - The day of the month value (1-31 or '*').
 * @param {string} month - The month value (1-12 or '*').
 * @param {string} weekday - The day of the week value (0-7 or '*').
 * @param {string} command - The full command string of the cron job.
 */
function fillModifyForm(minute, hour, day, month, weekday, command) {
    const functionName = 'fillModifyForm';
    console.log(`${functionName}: Populating form for modification.`);
    console.debug(`${functionName}: Data - min=${minute}, hr=${hour}, day=${day}, mon=${month}, wkday=${weekday}, cmd='${command}'`);

    try {
        // Populate time fields
        document.getElementById('minute').value = minute;
        document.getElementById('hour').value = hour;
        document.getElementById('day').value = day;
        document.getElementById('month').value = month;
        document.getElementById('weekday').value = weekday;

        // Store the full original cron string in the hidden field for comparison/modification on the backend
        const originalCronString = `${minute} ${hour} ${day} ${month} ${weekday} ${command}`;
        document.getElementById('original_cron_string').value = originalCronString;
        console.debug(`${functionName}: Set original_cron_string (hidden) to: '${originalCronString}'`);

        // --- Attempt to Select Command in Dropdown ---
        const commandSelect = document.getElementById('command');
        if (!commandSelect) {
             console.error(`${functionName}: Command select dropdown (#command) not found!`);
             return; // Cannot proceed without dropdown
        }

        // Extract the 'action' part of the command for matching the dropdown value
        // Example: '/path/to/bsm update-server --server MyServer' -> 'update-server'
        let baseCommand = '';
        // 1. Remove path prefix if present (assuming EXPATH is the prefix)
        const expathPrefix = document.getElementById('cron-form')?.dataset?.expath || ''; // Get EXPATH from form data attribute if set
        let commandPart = command.trim();
        if (expathPrefix && commandPart.startsWith(expathPrefix)) {
            commandPart = commandPart.substring(expathPrefix.length).trim();
        }
        // 2. Take the first word as the command slug
        if (commandPart) {
             baseCommand = commandPart.split(/\s+/)[0]; // Split on whitespace
        }

        console.debug(`${functionName}: Extracted base command slug '${baseCommand}' from full command '${command}'.`);

        let commandOptionFound = false;
        for (let i = 0; i < commandSelect.options.length; i++) {
            // Compare option value (e.g., "update-server") with extracted command slug
            if (commandSelect.options[i].value === baseCommand) {
                commandSelect.value = commandSelect.options[i].value;
                commandOptionFound = true;
                console.debug(`${functionName}: Matched and selected command '${baseCommand}' in dropdown.`);
                break;
            }
        }
        if (!commandOptionFound) {
            console.warn(`${functionName}: Could not find matching command option for slug '${baseCommand}'. Clearing selection.`);
            commandSelect.value = ""; // Set to default/empty option
            showStatusMessage(`Warning: Could not automatically select command '${baseCommand}' from dropdown. Please select manually if needed.`, "warning");
        }
        // --- End Command Selection ---

        console.log(`${functionName}: Form populated for modification.`);
        // Scroll form into view
        const cronForm = document.getElementById('cron-form');
        if (cronForm) {
            cronForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
            console.debug(`${functionName}: Scrolled form into view.`);
        } else {
            console.warn(`${functionName}: Could not find #cron-form to scroll into view.`);
        }

    } catch (error) {
        console.error(`${functionName}: Error populating form: ${error.message}`, error);
        showStatusMessage("Error preparing form for modification. Check console.", "error");
    }
}

/**
 * Prompts the user for confirmation and then initiates a request to delete the specified cron job line via the API.
 * Reloads the page on successful deletion.
 *
 * @async
 * @param {string} cronString - The exact cron job string to be deleted.
 * @param {string} serverName - The server context name (used for API path).
 */
async function confirmDelete(cronString, serverName) {
    const functionName = 'confirmDelete';
    console.log(`${functionName}: Initiated for cron string: '${cronString}', Server context: '${serverName}'`);

    // --- Input Validation ---
    if (!cronString || typeof cronString !== 'string' || !cronString.trim()) {
        const errorMsg = "Internal error: No cron job string provided for deletion.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }
     if (!serverName || typeof serverName !== 'string' || !serverName.trim()) {
        const errorMsg = "Internal error: Server name context missing for deletion.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }
    const trimmedCronString = cronString.trim();

    // --- Confirmation ---
    console.debug(`${functionName}: Prompting user for deletion confirmation.`);
    const confirmationMessage = `Are you sure you want to delete this cron job?\n\n${trimmedCronString}`;
    if (!confirm(confirmationMessage)) {
        console.log(`${functionName}: Deletion cancelled by user.`);
        showStatusMessage('Cron job deletion cancelled.', 'info');
        return; // Abort
    }
    console.log(`${functionName}: User confirmed deletion for '${trimmedCronString}'.`);

     // --- Prepare API Request ---
    // Encode the cron string for use as a URL query parameter
    const encodedCronString = encodeURIComponent(trimmedCronString);
    // Append as query parameter
    const actionPath = `cron_scheduler/delete?cron_string=${encodedCronString}`; // Relative path with query param
    const method = 'DELETE';
    const requestBody = null; // NO request body for DELETE with query params
    console.debug(`${functionName}: Prepared Action Path with Query Param: '${actionPath}'`);

    // --- Call API Helper ---
    const apiUrl = `/api/server/${serverName}/${actionPath}`; // Full path is constructed for logging
    console.log(`${functionName}: Calling sendServerActionRequest to ${method} ${apiUrl}...`);

    // Pass serverName, modified actionPath, method, NULL body
    const apiResponseData = await sendServerActionRequest(serverName, actionPath, method, requestBody, null);
    console.log(`${functionName}: Delete cron job API call finished. Response data:`, apiResponseData);

    // --- Handle API Response ---
    if (apiResponseData && apiResponseData.status === 'success') {
        // Success message shown by sendServerActionRequest
        console.log(`${functionName}: Cron job deletion successful for '${trimmedCronString}'. Reloading page...`);
        // Reload after a delay to allow user to see success message
        setTimeout(() => {
            console.log(`${functionName}: Reloading window.`);
            window.location.reload();
        }, 1500);
    } else {
        console.error(`${functionName}: Cron job deletion failed or application reported an error for '${trimmedCronString}'.`);
        // Error message shown by sendServerActionRequest
        // No page reload on failure
    }
    console.log(`${functionName}: Execution finished.`);
}

// --- Add/Modify Form Submission Handler ---
document.addEventListener('DOMContentLoaded', () => {
    const functionName = 'DOMContentLoaded (Cron Form)';
    console.log(`${functionName}: Setting up cron form submission handler.`);

    // Get server name and EXPATH from data attributes on the form itself
    const cronForm = document.getElementById('cron-form');
    if (!cronForm) {
        console.error(`${functionName}: Critical Error - Cron form element (#cron-form) not found! Cannot attach submit listener.`);
        alert("Error: Could not initialize the scheduling form. Please refresh or contact support.");
        return;
    }

    const serverName = cronForm.dataset.serverName;
    const EXPATH = cronForm.dataset.expath; // Get EXPATH needed for constructing command
    const submitButton = cronForm.querySelector('button[type="submit"]');

    if (!serverName) console.warn(`${functionName}: Server name not found in form data attribute (data-server-name). API calls may fail.`);
    if (!EXPATH) console.warn(`${functionName}: EXPATH not found in form data attribute (data-expath). Cron commands will be incomplete.`);
    if (!submitButton) console.warn(`${functionName}: Submit button not found in form. Submitting might not work as expected.`);

    cronForm.addEventListener('submit', async (event) => { // Mark the listener as async
        event.preventDefault(); // Prevent default browser form submission
        const submitFunctionName = 'CronFormSubmitHandler';
        console.log(`${submitFunctionName}: Form submitted.`);

        // --- Get Form Values ---
        const commandSelect = document.getElementById('command');
        const minuteInput = document.getElementById('minute');
        const hourInput = document.getElementById('hour');
        const dayInput = document.getElementById('day');
        const monthInput = document.getElementById('month');
        const weekdayInput = document.getElementById('weekday');
        const originalCronStringInput = document.getElementById('original_cron_string'); // Hidden field

        // Check if all elements exist before accessing values
        if (!commandSelect || !minuteInput || !hourInput || !dayInput || !monthInput || !weekdayInput || !originalCronStringInput) {
             const errorMsg = "One or more form fields are missing from the page.";
             console.error(`${submitFunctionName}: ${errorMsg}`);
             showStatusMessage(`Internal page error: ${errorMsg}`, "error");
             return;
        }

        const command = commandSelect.value;
        const minute = minuteInput.value.trim();
        const hour = hourInput.value.trim();
        const day = dayInput.value.trim();
        const month = monthInput.value.trim();
        const weekday = weekdayInput.value.trim();
        const originalCronString = originalCronStringInput.value.trim(); // Get value from hidden field

        console.debug(`${submitFunctionName}: Form values - Command: ${command}, Min: ${minute}, Hr: ${hour}, Day: ${day}, Mon: ${month}, Wkday: ${weekday}, Original: '${originalCronString}'`);

        // --- Client-Side Validation ---
        if (!command) { return showStatusMessage("Please select a command.", "warning"); }
        if (!minute || !hour || !day || !month || !weekday) {
            return showStatusMessage("Please fill in all time fields (Minute, Hour, Day, Month, Weekday). Use '*' for any.", "warning");
        }
        // Basic validation for '*' or number format - more robust validation happens server-side/via API
        const cronRegex = /^(\*|([0-9]|[1-5]?[0-9]))$/; // Very basic check for * or 0-59
        const cronDayRegex = /^(\*|([1-9]|[12]?[0-9]|3[01]))$/; // Basic * or 1-31
        const cronMonthRegex = /^(\*|([1-9]|1[0-2]))$/; // Basic * or 1-12
        const cronWeekdayRegex = /^(\*|[0-7])$/; // Basic * or 0-7
        if (!cronRegex.test(minute)) { return showStatusMessage("Invalid Minute format (use 0-59 or *).", "warning"); }
        if (!cronRegex.test(hour)) { return showStatusMessage("Invalid Hour format (use 0-23 or *).", "warning"); }
        if (!cronDayRegex.test(day)) { return showStatusMessage("Invalid Day of Month format (use 1-31 or *).", "warning"); }
        if (!cronMonthRegex.test(month)) { return showStatusMessage("Invalid Month format (use 1-12 or *).", "warning"); }
        if (!cronWeekdayRegex.test(weekday)) { return showStatusMessage("Invalid Day of Week format (use 0-7 or *).", "warning"); }

        console.debug(`${submitFunctionName}: Basic client-side validation passed.`);

        // --- Construct Full Command ---
        // Use EXPATH from data attribute (or default if missing)
        const effectiveExpath = EXPATH || 'bedrock-server-manager'; // Fallback if not set
        // Ensure server name quoting if needed, though server names shouldn't have spaces ideally
        const commandArg = `--server "${serverName}"`; // Add quotes just in case
        const fullCommand = `${effectiveExpath} ${command} ${commandArg}`.replace('  ', ' ').trim(); // Construct and clean spaces

        // --- Construct New Cron String ---
        const newCronString = `${minute} ${hour} ${day} ${month} ${weekday} ${fullCommand}`;
        console.debug(`${submitFunctionName}: Constructed new cron string: '${newCronString}'`);

        // --- Determine API Action (Add or Modify) ---
        let actionPath;
        let requestBody;
        const method = 'POST'; // Both use POST

        if (originalCronString) {
            // MODIFY operation
            actionPath = 'cron_scheduler/modify';
            requestBody = { old_cron_job: originalCronString, new_cron_job: newCronString };
            console.log(`${submitFunctionName}: Preparing MODIFY request to '${actionPath}'.`);
        } else {
            // ADD operation
            actionPath = 'cron_scheduler/add';
            requestBody = { new_cron_job: newCronString };
            console.log(`${submitFunctionName}: Preparing ADD request to '${actionPath}'.`);
        }
        console.debug(`${submitFunctionName}: Request Body:`, requestBody);

        // --- Send API Request ---
        console.log(`${submitFunctionName}: Calling sendServerActionRequest...`);
        const apiResponseData = await sendServerActionRequest(serverName, actionPath, method, requestBody, submitButton);
        console.log(`${submitFunctionName}: Add/Modify API call finished. Response data:`, apiResponseData);

        // --- Handle API Response ---
        if (apiResponseData && apiResponseData.status === 'success') {
            console.log(`${submitFunctionName}: Cron job ${originalCronString ? 'modification' : 'addition'} successful.`);
            // Clear the hidden field to reset to 'Add' mode for next time
            originalCronStringInput.value = '';
            // Optionally reset the form fields completely
            // cronForm.reset(); // Uncomment to clear all fields after success

            // Reload the page to show the updated cron table after a delay
            showStatusMessage(apiResponseData.message || `Cron job ${originalCronString ? 'modified' : 'added'} successfully. Reloading...`, "success");
            setTimeout(() => {
                console.log(`${submitFunctionName}: Reloading window.`);
                window.location.reload();
            }, 1500);
        } else {
             // Error occurred (validation or API failure)
             // Error message handled by sendServerActionRequest
             console.error(`${submitFunctionName}: Cron job ${originalCronString ? 'modification' : 'addition'} failed.`);
             // Do NOT clear original_cron_string on failure - allows user to retry modify
        }
    }); // End form submit listener

    console.log(`${functionName}: Cron form submit handler attached.`);
}); // End DOMContentLoaded listener