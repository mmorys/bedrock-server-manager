// bedrock-server-manager/bedrock_server_manager/web/static/js/linux_task.js

const serverName = pageConfig.serverName; // Get server name from Jinja2

function fillModifyForm(minute, hour, day, month, weekday, command) {
    document.getElementById('minute').value = minute;
    document.getElementById('hour').value = hour;
    document.getElementById('day').value = day;
    document.getElementById('month').value = month;
    document.getElementById('weekday').value = weekday;
    // Store the original cron string for the modify API call
    document.getElementById('original_cron_string').value = `${minute} ${hour} ${day} ${month} ${weekday} ${command}`;

    // --- Extract the base command part to select in the dropdown ---
    // 1. Take everything before the first '--' (like --server)
    let commandPart = command.split('--')[0].trim();
     // 2. Get the last part after any path separators ('/' or '\')
    commandPart = commandPart.split('/').pop().split('\\').pop();
    // 3. Remove common executable suffixes and prefixes used by the manager
    commandPart = commandPart.replace(/\.(?:exe|py)$/i, '') // Remove .exe or .py (case-insensitive)
                         .replace(/^bedrock-server-manager-?/i, '') // Remove prefix bedrock-server-manager- (case-insensitive)
                         .replace(/^bedrock_server_manager_?/i, ''); // Remove prefix bedrock_server_manager_ (case-insensitive)

    const commandSelect = document.getElementById('command');
    let foundOption = false;
    for (let i = 0; i < commandSelect.options.length; i++) {
        // Compare values case-insensitively
        if (commandSelect.options[i].value.toLowerCase() === commandPart.toLowerCase()) {
            commandSelect.value = commandSelect.options[i].value;
            foundOption = true;
            break;
        }
    }
    if (!foundOption) {
         console.warn(`Could not find matching option in dropdown for command: '${commandPart}'. The full command was: '${command}'`);
         // Set dropdown to default or clear it
         commandSelect.value = ""; // Set to the disabled default option
    }
    // --- End Command Extraction ---

    console.log(`Form filled for modifying job. Original string set to: ${document.getElementById('original_cron_string').value}`);
    // Scroll the form into view for better UX
    document.getElementById('cron-form').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// --- Function to handle deletion confirmation and API call ---
async function confirmDelete(cronString) {
    if (confirm(`Are you sure you want to delete the cron job:\n${cronString}?`)) {
        const serverName = "{{ server_name }}"; // Get server name from Jinja2 context
        // Define the path for the delete API endpoint
        const actionPath = 'cron_scheduler/delete'; // Will be combined with serverName by utils.js
        const method = 'DELETE';
        // The backend delete route expects the cron string in a 'cron_string' field
        const body = { cron_string: cronString };

        console.log(`Attempting to delete cron job via API: Server=${serverName}, Path=${actionPath}`);
        // Call the utility function, passing serverName and the relative actionPath
        const responseData = await sendServerActionRequest(serverName, actionPath, method, body, null); // No specific button for delete link

        // Check the result returned by the utility function
        if (responseData && responseData.status === 'success') {
            console.log(`Cron job deletion successful for: ${cronString}. Reloading page.`);
            // Reload after a short delay to allow user to see success message
            setTimeout(() => {
                window.location.reload();
            }, 1500); // Reload after 1.5 seconds
        } else {
            // Error messages are handled by sendServerActionRequest via showStatusMessage
            console.warn(`Cron job deletion reported non-success or failed for: ${cronString}. See status message area or console logs.`);
            // No page reload on failure.
        }
    } else {
         console.log("User cancelled cron job deletion.");
    }
}

// --- Add/Modify Form Submission Handler ---
document.addEventListener('DOMContentLoaded', function() {
    const serverName = "{{ server_name }}";
    // EXPATH is the path/command prefix needed for the full command string
    const EXPATH = "{{ EXPATH | e }}"; // Use 'e' filter for safety if EXPATH might contain special chars
    const cronForm = document.getElementById('cron-form');
    const submitButton = cronForm.querySelector('button[type="submit"]');

    // Basic check to ensure form and button exist
    if (!cronForm) {
        console.error("Fatal Error: Cron form element (#cron-form) not found!");
        alert("Error: Could not initialize the scheduling form. Please contact support.");
        return;
    }
    if (!submitButton) {
        console.error("Error: Submit button not found within the cron form!");
        // Allow script to continue but log warning
    }

    cronForm.addEventListener('submit', async function(event) { // Mark the listener as async
        event.preventDefault(); // Prevent the browser's default form submission

        // Get values from form fields, trim whitespace
        const command = document.getElementById('command').value;
        const minute = document.getElementById('minute').value.trim();
        const hour = document.getElementById('hour').value.trim();
        const day = document.getElementById('day').value.trim();
        const month = document.getElementById('month').value.trim();
        const weekday = document.getElementById('weekday').value.trim();
        const originalCronString = document.getElementById('original_cron_string').value; // Get value from hidden field

        // Client-side validation
        if (!command) {
            showStatusMessage("Please select a command.", "error");
            console.warn("Form submission stopped: Command not selected.");
            return; // Stop processing
        }
        if (!minute || !hour || !day || !month || !weekday) {
            showStatusMessage("Please fill in all time fields (Minute, Hour, Day, Month, Weekday). Use '*' for any.", "error");
            console.warn("Form submission stopped: Missing time fields.");
            return; // Stop processing
        }

        // Construct the full command part of the cron string
        const fullCommand = `${EXPATH} ${command} --server ${serverName}`;
        // Construct the complete new cron string
        const newCronString = `${minute} ${hour} ${day} ${month} ${weekday} ${fullCommand}`;

        let actionPath; // Relative API path ('schedule/add' or 'schedule/modify')
        let requestBody;
        const method = 'POST'; // Both add and modify routes use POST

        if (originalCronString) {
            // --- This is a MODIFY operation ---
            actionPath = 'cron_scheduler/modify';
            // The modify API endpoint expects 'old_cron_job' and 'new_cron_job'
            requestBody = {
                old_cron_job: originalCronString,
                new_cron_job: newCronString
            };
            console.log(`Preparing MODIFY request: Server=${serverName}, Path=${actionPath}, From='${originalCronString}', To='${newCronString}'`);
        } else {
            // --- This is an ADD operation ---
            actionPath = 'cron_scheduler/add';
            // The add API endpoint expects 'new_cron_job'
            requestBody = {
                new_cron_job: newCronString
            };
            console.log(`Preparing ADD request: Server=${serverName}, Path=${actionPath}, Job='${newCronString}'`);
        }

        // Use the utility function to send the request
        // Pass serverName, relative actionPath, method, JSON body, and the button element
        const responseData = await sendServerActionRequest(serverName, actionPath, method, requestBody, submitButton);

        // Check the result
        if (responseData && responseData.status === 'success') {
            console.log(`Cron job add/modify successful. Response:`, responseData);
            // Clear the hidden field to reset form state to 'Add' mode
            document.getElementById('original_cron_string').value = '';
            // cronForm.reset(); // Resets all fields to initial values (like '*')
            // document.getElementById('command').value = ""; // Reset command dropdown

            // Reload the page to show the updated table after a short delay
            setTimeout(() => {
                 window.location.reload();
            }, 1500);
        } else {
             // Error messages are handled by sendServerActionRequest
             console.warn(`Cron job add/modify failed or reported non-success. Response:`, responseData);
             // Do NOT clear original_cron_string on failure, allow user to correct and retry modification
             // The button is re-enabled automatically by the utility function on failure.
        }
    });
});