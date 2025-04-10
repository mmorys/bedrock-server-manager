// bedrock-server-manager/bedrock_server_manager/web/static/js/windows_task.js
/**
 * @fileoverview Frontend JavaScript for managing Windows Scheduled Tasks via the web UI.
 * Handles dynamic form creation for triggers, populating the form for modification,
 * validating user input, confirming deletions, and interacting with the backend API
 * for add, modify, delete, and details retrieval operations.
 * Depends on functions defined in utils.js (showStatusMessage, sendServerActionRequest).
 */

// Ensure utils.js is loaded
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("CRITICAL ERROR: Missing required functions from utils.js. Ensure utils.js is loaded first.");
}

// --- Global Variables (potentially set by template or data attributes) ---
// It's generally better to read these from data attributes when needed than rely on globals.
// Example: const serverName = document.getElementById('task-form')?.dataset.serverName;

// --- Constants ---
let triggerCounter = 0; // Counter for generating unique IDs for dynamic trigger elements

// --- Helper: Get Required DOM Elements ---
/**
 * Gets references to essential DOM elements needed for the task scheduler UI.
 * Logs errors and potentially shows messages if elements are missing.
 * @returns {object|null} An object containing references to elements, or null if critical elements are missing.
 */
function getTaskSchedulerDOMElements() {
    const elements = {
        taskForm: document.getElementById('task-form'),
        formSection: document.getElementById('add-modify-task-section'),
        formTitle: document.getElementById('form-title'),
        commandSelect: document.getElementById('command'),
        originalTaskNameInput: document.getElementById('original_task_name'),
        triggersContainer: document.getElementById('triggers-container'),
        submitButton: document.getElementById('submit-task-btn'), // Changed selector
        addTriggerButton: document.getElementById('add-trigger-btn') // Added button reference
    };

    // Check for critical elements
    if (!elements.taskForm || !elements.formSection || !elements.triggersContainer) {
        console.error("Critical task scheduler elements missing:", elements);
        showStatusMessage("Internal page error: Task form structure incomplete.", "error");
        return null;
    }
    // Log warnings for potentially missing optional elements
    if (!elements.formTitle) console.warn("Element #form-title not found.");
    if (!elements.commandSelect) console.warn("Element #command select not found.");
    if (!elements.originalTaskNameInput) console.warn("Element #original_task_name input not found.");
    if (!elements.submitButton) console.warn("Element #submit-task-btn button not found.");
    if (!elements.addTriggerButton) console.warn("Element #add-trigger-btn button not found.");

    return elements;
}

// --- Delete Task Function ---
/**
 * Prompts the user for confirmation and initiates the deletion of a Windows scheduled task via API.
 * Reloads the page on success.
 *
 * @async
 * @param {string} taskName - The name of the task to delete (must be exact name from Task Scheduler).
 * @param {string} serverName - The server context name (used for API path construction).
 */
async function confirmDeleteWindows(taskName, serverName) {
    const functionName = 'confirmDeleteWindows';
    console.log(`${functionName}: Initiated for Task: '${taskName}', Server Context: '${serverName}'`);

    // Basic validation
    if (!taskName || !serverName) {
        const errorMsg = "Internal error: Task name and Server name are required for deletion.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }

    // --- Confirmation ---
    console.debug(`${functionName}: Prompting user for delete confirmation.`);
    const confirmationMessage = `Are you sure you want to delete the scheduled task '${taskName}'?\n\nThis will remove it from Windows Task Scheduler AND delete its configuration file from this manager. This action cannot be undone.`;
    if (!confirm(confirmationMessage)) {
        console.log(`${functionName}: Deletion cancelled by user for task '${taskName}'.`);
        showStatusMessage(`Deletion of task '${taskName}' cancelled.`, 'info');
        return; // Abort
    }
    console.log(`${functionName}: User confirmed deletion for task '${taskName}'.`);

    // --- Prepare and Send API Request ---
    // The task name is part of the URL path for the DELETE request
    const actionPath = `task_scheduler/task/${encodeURIComponent(taskName)}`; // Encode task name for URL safety
    const method = 'DELETE';

    console.log(`${functionName}: Calling sendServerActionRequest to ${method} ${actionPath} for server '${serverName}'...`);
    // No request body needed for delete. No specific button tied to this action usually (might be a link).
    const apiResponseData = await sendServerActionRequest(serverName, actionPath, method, null, null);
    console.log(`${functionName}: Delete task API call finished. Response data:`, apiResponseData);

    // --- Handle API Response ---
    if (apiResponseData && apiResponseData.status === 'success') {
        const successMsg = apiResponseData.message || `Task '${taskName}' deleted successfully. Reloading list...`;
        console.log(`${functionName}: ${successMsg}`);
        showStatusMessage(successMsg, 'success');
        // Reload after delay
        setTimeout(() => {
            console.log(`${functionName}: Reloading window.`);
            window.location.reload();
        }, 1500);
    } else {
        // Error message handled by sendServerActionRequest
        console.error(`${functionName}: Task '${taskName}' deletion failed or API reported an error.`);
    }
    console.log(`${functionName}: Execution finished.`);
}

/**
 * Fetches details for a specific Windows task via API and populates the add/modify form.
 * Handles errors during fetching or populating.
 *
 * @async
 * @param {string} taskName - The name of the task to load into the form for editing.
 * @param {string} serverName - The server context name (used for API path construction).
 */
async function fillModifyFormWindows(taskName, serverName) {
    const functionName = 'fillModifyFormWindows';
    console.log(`${functionName}: Preparing form to modify task '${taskName}' for server '${serverName}'.`);
    showStatusMessage(`Loading data for task '${taskName}'...`, 'info');

    // --- Get DOM Elements ---
    const elements = getTaskSchedulerDOMElements();
    if (!elements) return; // Stop if critical elements are missing

    // --- Prepare Form UI ---
    elements.formSection.style.display = 'block';
    elements.formTitle.textContent = `Modify Task: ${taskName}`;
    elements.originalTaskNameInput.value = taskName; // Store original name
    elements.triggersContainer.innerHTML = ''; // Clear previous triggers
    triggerCounter = 0; // Reset trigger counter
    if (elements.commandSelect) elements.commandSelect.disabled = true; // Disable while loading
    console.debug(`${functionName}: Form UI prepared for modification.`);

    // --- Fetch Task Details ---
    // Use the API endpoint that expects the task name in the JSON body (POST request)
    const actionPath = `task_scheduler/details`;
    const method = 'POST';
    const requestBody = { task_name: taskName }; // API expects name in body

    console.log(`${functionName}: Calling sendServerActionRequest to ${actionPath} to get details for task '${taskName}'...`);
    const apiResponseData = await sendServerActionRequest(serverName, actionPath, method, requestBody, null); // No button needed here
    console.log(`${functionName}: Get task details API call finished. Response data:`, apiResponseData);

    // --- Handle API Response ---
    if (!apiResponseData || apiResponseData.status !== 'success') {
        const errorMsg = apiResponseData?.message || `Error loading details for task '${taskName}'.`;
        console.error(`${functionName}: Failed to load task data. ${errorMsg}`);
        showStatusMessage(errorMsg, 'error');
        cancelTaskForm(); // Hide form on failure
        if (elements.commandSelect) elements.commandSelect.disabled = false; // Re-enable dropdown on failure
        return;
    }

    // --- Populate Form with Fetched Data ---
    console.log(`${functionName}: Successfully fetched task data. Populating form...`, apiResponseData);
    const taskDetails = apiResponseData; // Response is expected to be {status: 'success', base_command: ..., triggers: ...}

    // 1. Populate Command Dropdown
    if (elements.commandSelect) {
        const fetchedBaseCommand = taskDetails.base_command; // Use key from enhanced API response
        console.debug(`${functionName}: Populating command dropdown with value: '${fetchedBaseCommand}'`);
        let commandFound = false;
        if (fetchedBaseCommand) {
            for (let i = 0; i < elements.commandSelect.options.length; i++) {
                if (elements.commandSelect.options[i].value.toLowerCase() === fetchedBaseCommand.toLowerCase()) {
                    elements.commandSelect.value = elements.commandSelect.options[i].value;
                    commandFound = true;
                    break;
                }
            }
        }
        if (!commandFound) {
            console.warn(`${functionName}: Fetched base command '${fetchedBaseCommand}' not found in dropdown options.`);
            elements.commandSelect.value = ""; // Reset to default prompt
        }
        elements.commandSelect.disabled = false; // Re-enable after population
    }

    // 2. Populate Triggers
    elements.triggersContainer.innerHTML = ''; // Ensure container is empty
    triggerCounter = 0;
    const fetchedTriggers = taskDetails.triggers; // Use key from enhanced API response
    if (fetchedTriggers && Array.isArray(fetchedTriggers) && fetchedTriggers.length > 0) {
        console.debug(`${functionName}: Populating ${fetchedTriggers.length} triggers from fetched data.`);
        fetchedTriggers.forEach(trigger => {
            addTrigger(trigger); // Add trigger group populated with fetched data
        });
    } else {
        console.warn(`${functionName}: No triggers found in fetched data or 'triggers' is not an array. Adding a blank trigger group.`);
        addTrigger(); // Add a blank one if none exist
    }

    // --- Final UI Adjustments ---
    showStatusMessage(`Loaded details for task '${taskName}'. Ready to modify.`, 'info');
    elements.formSection.scrollIntoView({ behavior: 'smooth' });
    console.log(`${functionName}: Form population complete.`);
}

/**
 * Resets and displays the add/modify form section for adding a NEW task.
 * Clears existing trigger UI, sets the title, clears hidden fields, and adds a blank trigger.
 */
function prepareNewTaskForm() {
    const functionName = 'prepareNewTaskForm';
    console.log(`${functionName}: Preparing form for adding a new Windows task.`);

    const elements = getTaskSchedulerDOMElements();
    if (!elements) {
        console.error(`${functionName}: Cannot prepare form - critical elements missing.`);
        return; // Stop if critical elements like the form/section are missing
    }

    // Ensure elements used exist before manipulating
    if (elements.formSection) elements.formSection.style.display = 'block'; // Show section
    if (elements.formTitle) elements.formTitle.textContent = 'Add New Scheduled Task'; // Set title
    if (elements.taskForm) elements.taskForm.reset(); // Reset standard fields (command dropdown)
    if (elements.originalTaskNameInput) elements.originalTaskNameInput.value = ''; // Clear hidden field -> signifies ADD mode
    if (elements.triggersContainer) elements.triggersContainer.innerHTML = ''; // Clear existing trigger groups
    triggerCounter = 0; // Reset trigger counter
    if (elements.commandSelect) elements.commandSelect.disabled = false; // Ensure dropdown is enabled

    addTrigger(); // Add one blank trigger group to start

    if (elements.formSection) {
        elements.formSection.scrollIntoView({ behavior: 'smooth' }); // Scroll to form
        console.debug(`${functionName}: Scrolled form into view.`);
    }

    showStatusMessage("Enter details for the new task.", "info"); // User feedback
    console.log(`${functionName}: Form prepared for new task entry.`);
}

/**
 * Hides the add/modify task form section and resets its fields.
 */
function cancelTaskForm() {
    const functionName = 'cancelTaskForm';
    console.log(`${functionName}: Cancelling/hiding task form.`);

    const elements = getTaskSchedulerDOMElements();
    if (!elements) return; // Should already be logged if missing

    elements.formSection.style.display = 'none'; // Hide
    elements.taskForm.reset(); // Reset fields
    elements.originalTaskNameInput.value = ''; // Clear hidden field
    elements.triggersContainer.innerHTML = ''; // Clear triggers
    triggerCounter = 0; // Reset counter
    if (elements.commandSelect) elements.commandSelect.disabled = false; // Ensure enabled

    showStatusMessage("Task operation cancelled.", "info"); // Inform user
    console.log(`${functionName}: Task form hidden and reset.`);
}

// --- Dynamic Trigger UI Functions ---

/**
 * Adds a new UI group for defining a task trigger.
 * Optionally populates the fields if `existingTriggerData` is provided (for modify).
 *
 * @param {object|null} [existingTriggerData=null] - Optional data object for an existing trigger,
 *                                                as returned by the get_windows_task_details API.
 */
function addTrigger(existingTriggerData = null) {
    const functionName = 'addTrigger';
    triggerCounter++; // Increment global counter for unique IDs
    const triggerNum = triggerCounter;
    console.log(`${functionName}: Adding trigger group #${triggerNum}. Existing data:`, existingTriggerData);

    const elements = getTaskSchedulerDOMElements();
    if (!elements?.triggersContainer) {
        console.error(`${functionName}: Cannot add trigger - triggersContainer element not found.`);
        return;
    }

    // Create main container div for the trigger group
    const div = document.createElement('div');
    div.className = 'trigger-group';
    div.id = `trigger-group-${triggerNum}`;
    div.style.border = '1px solid #ccc'; // Add visual separation
    div.style.padding = '10px';
    div.style.marginBottom = '15px';

    // Basic structure: Remove button, Title, Type Selector, Fields Placeholder
    div.innerHTML = `
        <button type="button" class="remove-trigger-btn" onclick="removeTrigger(${triggerNum})" title="Remove This Trigger">×</button>
        <h4>Trigger ${triggerNum}</h4>
        <div class="form-group">
            <label for="trigger_type_${triggerNum}" class="form-label">Trigger Type:</label>
            <select id="trigger_type_${triggerNum}" name="trigger_type_${triggerNum}" class="form-input" onchange="showTriggerFields(${triggerNum})">
                <option value="">-- Select Type --</option>
                <option value="TimeTrigger">One Time</option>
                <option value="Daily">Daily</option>
                <option value="Weekly">Weekly</option>
                <option value="Monthly">Monthly</option>
                <!-- Add future types: LogonTrigger, BootTrigger etc. -->
            </select>
        </div>
        <div id="trigger_fields_${triggerNum}" class="trigger-fields-container">
            <!-- Dynamic fields appear here -->
        </div>
    `;
    elements.triggersContainer.appendChild(div);
    console.debug(`${functionName}: Appended trigger group #${triggerNum} structure to container.`);

    // --- Populate if existing data provided ---
    if (existingTriggerData) {
        const typeSelect = div.querySelector(`#trigger_type_${triggerNum}`);
        const triggerType = existingTriggerData.type; // Should be 'TimeTrigger', 'Daily', etc.

        if (triggerType && typeSelect) {
            console.debug(`${functionName}: Populating existing trigger #${triggerNum} with type '${triggerType}'`);
            // Try to find and select the matching option value
            let found = Array.from(typeSelect.options).some(option => {
                if (option.value === triggerType) {
                    option.selected = true;
                    return true;
                }
                return false;
            });
            if (!found) {
                console.warn(`${functionName}: Existing trigger type '${triggerType}' not found in select options for trigger #${triggerNum}.`);
            }
            // Call showTriggerFields AFTER setting the type to populate specific fields
            showTriggerFields(triggerNum, existingTriggerData);
        } else {
            console.warn(`${functionName}: Cannot populate trigger #${triggerNum} - type missing in data or select element not found. Data:`, existingTriggerData);
            showTriggerFields(triggerNum); // Show default fields for blank type
        }
    } else {
        // New trigger, just show default fields based on empty selection
        console.debug(`${functionName}: Showing default fields for new trigger #${triggerNum}.`);
        showTriggerFields(triggerNum);
    }
}

/**
 * Removes a trigger group UI element from the form.
 * Adds a new blank trigger if it was the last one.
 *
 * @param {number} triggerNum - The unique number suffix of the trigger group to remove.
 */
function removeTrigger(triggerNum) {
    const functionName = 'removeTrigger';
    console.log(`${functionName}: Attempting to remove trigger group #${triggerNum}.`);

    const elements = getTaskSchedulerDOMElements(); // Get container reference
    const triggerGroup = document.getElementById(`trigger-group-${triggerNum}`);

    if (triggerGroup) {
        triggerGroup.remove();
        console.log(`${functionName}: Removed trigger group #${triggerNum}.`);

        // If no triggers are left, add a new blank one automatically
        if (elements?.triggersContainer && elements.triggersContainer.querySelectorAll('.trigger-group').length === 0) {
            console.log(`${functionName}: Last trigger removed. Adding a new blank trigger group.`);
            addTrigger();
        }
    } else {
        console.warn(`${functionName}: Could not find trigger group #${triggerNum} to remove.`);
    }
}

/**
 * Dynamically generates and displays the appropriate input fields within a trigger group
 * based on the selected trigger type. Populates fields if existing data is provided.
 *
 * @param {number} triggerNum - The unique number suffix of the trigger group being updated.
 * @param {object|null} [data=null] - Optional data object for an existing trigger to populate fields.
 */
function showTriggerFields(triggerNum, data = null) {
    const functionName = 'showTriggerFields';
    console.debug(`${functionName}: Updating fields for trigger group #${triggerNum}. Data provided:`, data);

    const typeSelect = document.getElementById(`trigger_type_${triggerNum}`);
    const fieldsDiv = document.getElementById(`trigger_fields_${triggerNum}`);
    if (!typeSelect || !fieldsDiv) {
        console.error(`${functionName}: Critical elements missing for trigger #${triggerNum}. Cannot show fields.`);
        return;
    }
    const selectedType = typeSelect.value;
    fieldsDiv.innerHTML = ''; // Clear previous fields

    // --- Always Add Start Boundary (datetime-local input) ---
    // API provides 'start' in ISO format (e.g., 2023-10-27T03:00:00).
    // Input type="datetime-local" expects "YYYY-MM-DDTHH:MM".
    let startValueForInput = '';
    if (data?.start) {
        try {
            // Take the ISO string and format it for the input
            startValueForInput = data.start.substring(0, 16); // Extracts YYYY-MM-DDTHH:MM
        } catch (e) {
            console.warn(`${functionName}: Could not format existing start date '${data.start}' for input.`);
        }
    }
     console.debug(`${functionName}: Trigger ${triggerNum}: Type='${selectedType}'. Start value for input: '${startValueForInput}'`);
    fieldsDiv.innerHTML += `
        <div class="form-group">
            <label for="start_${triggerNum}" class="form-label">Start Date & Time:</label>
            <input type="datetime-local" id="start_${triggerNum}" name="start_${triggerNum}" class="form-input trigger-field" value="${startValueForInput}" required>
            <small>When the trigger first becomes active.</small>
        </div>
    `;

    // --- Add Type-Specific Fields ---
    switch (selectedType) {
        case 'Daily':
            const dailyInterval = data?.interval || '1'; // Default interval 1 day
            fieldsDiv.innerHTML += `
                <div class="form-group">
                    <label for="interval_${triggerNum}" class="form-label">Repeat Every (Days):</label>
                    <input type="number" id="interval_${triggerNum}" name="interval_${triggerNum}" class="form-input trigger-field" value="${dailyInterval}" min="1" required>
                    <small>Enter 1 for every day, 2 for every other day, etc.</small>
                </div>
            `;
            break;

        case 'Weekly':
            const weeklyInterval = data?.interval || '1'; // Default interval 1 week
            // API provides 'days' as potentially list ["Monday", "Friday"]
            const selectedDays = (data?.days && Array.isArray(data.days)) ? data.days.map(d => d.toLowerCase()) : [];
            console.debug(`${functionName}: Trigger ${triggerNum} Weekly: Populating days:`, selectedDays);
            const daysOfWeekOptions = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
            let checkboxesHTML = daysOfWeekOptions.map(dayName => {
                const isChecked = selectedDays.includes(dayName.toLowerCase());
                return `
                    <label class="checkbox-label" style="margin-right: 15px;">
                        <input type="checkbox" class="trigger-field" name="days_of_week_${triggerNum}" value="${dayName}" ${isChecked ? 'checked' : ''}> ${dayName}
                    </label>`;
            }).join('');

            fieldsDiv.innerHTML += `
                <div class="form-group">
                    <label for="interval_${triggerNum}" class="form-label">Repeat Every (Weeks):</label>
                    <input type="number" id="interval_${triggerNum}" name="interval_${triggerNum}" class="form-input trigger-field" value="${weeklyInterval}" min="1" required>
                     <small>Enter 1 for every week, 2 for every other week, etc.</small>
               </div>
                <div class="form-group">
                    <label class="form-label">Run on Days:</label><br>
                    <div class="checkbox-group">${checkboxesHTML}</div>
                </div>
            `;
            break;

        case 'Monthly':
            // API provides 'days_of_month' (List[str]) and 'months' (List[str] like "Jan")
            const daysValue = (data?.days_of_month && Array.isArray(data.days_of_month)) ? data.days_of_month.join(',') : '';
            const monthsValue = (data?.months && Array.isArray(data.months)) ? data.months.join(',') : '';
            console.debug(`${functionName}: Trigger ${triggerNum} Monthly: Populating days='${daysValue}', months='${monthsValue}'`);

            fieldsDiv.innerHTML += `
                <div class="form-group">
                    <label for="days_of_month_${triggerNum}" class="form-label">Days of Month (comma-separated):</label>
                    <input type="text" id="days_of_month_${triggerNum}" name="days_of_month_${triggerNum}" class="form-input trigger-field" value="${daysValue}" placeholder="e.g., 1,15,31" required>
                    <small>Enter numbers 1-31.</small>
                </div>
                <div class="form-group">
                    <label for="months_${triggerNum}" class="form-label">Months (comma-separated):</label>
                    <input type="text" id="months_${triggerNum}" name="months_${triggerNum}" class="form-input trigger-field" value="${monthsValue}" placeholder="e.g., Jan,Feb,Mar or 1,2,3" required>
                    <small>Enter month names/abbreviations or numbers 1-12.</small>
                </div>
            `;
            break;

        case 'TimeTrigger': // One Time - Only needs StartBoundary, already added
        case '': // No type selected yet
        default:
            // No additional fields needed for "One Time" or if no type selected
            console.debug(`${functionName}: No additional fields needed for type '${selectedType}' or empty type.`);
            break;
    }
    console.debug(`${functionName}: Finished updating fields for trigger #${triggerNum}.`);
} // --- End of showTriggerFields ---

// --- Form Submission Event Listener ---
document.addEventListener('DOMContentLoaded', () => { // Add listener only after defining functions
    const functionName = 'DOMContentLoaded (Task Form Listener)';
    console.log(`${functionName}: Attaching submit listener to task form.`);

    // Get references to form and potentially needed data attributes
    const elements = getTaskSchedulerDOMElements(); // Use helper to get all elements
    if (!elements?.taskForm) {
        console.error(`${functionName}: Cannot attach listener - Task form not found.`);
        return; // Stop if form doesn't exist
    }

    // Extract serverName and EXPATH from form data attributes
    // These are needed for constructing commands/API calls
    const serverName = elements.taskForm.dataset.serverName;
    const EXPATH = elements.taskForm.dataset.expath; // Needed? EXPATH might be handled purely backend now.

    if (!serverName) console.warn(`${functionName}: data-server-name attribute missing from task form.`);
    // EXPATH warning removed as it might not be needed client-side anymore

    // Attach the submit event listener
    elements.taskForm.addEventListener('submit', async (event) => {
        event.preventDefault(); // Prevent default browser form submission
        const submitFunctionName = 'TaskFormSubmitHandler';
        console.log(`${submitFunctionName}: Form submitted.`);

        // Re-get elements inside handler for safety and access to submit button
        const currentElements = getTaskSchedulerDOMElements();
        if (!currentElements || !currentElements.commandSelect || !currentElements.originalTaskNameInput || !currentElements.triggersContainer || !currentElements.submitButton) {
            console.error(`${submitFunctionName}: Required form elements missing on submit.`);
            showStatusMessage("Internal form error. Cannot process submission.", "error");
            return;
        }

        const originalTaskName = currentElements.originalTaskNameInput.value.trim(); // Original name if modifying
        const command = currentElements.commandSelect.value; // Selected command

        // --- Basic Form Validation ---
        if (!command) {
            showStatusMessage("Please select a command.", "warning");
            if (currentElements.commandSelect) currentElements.commandSelect.focus();
            return;
        }
        console.debug(`${submitFunctionName}: Command selected: '${command}'`);

        // --- Parse Triggers from Form ---
        let triggers = [];
        const triggerGroups = currentElements.triggersContainer.querySelectorAll('.trigger-group');
        let formIsValid = true; // Track overall validation

        if (triggerGroups.length === 0) {
            showStatusMessage("Please add at least one trigger for the task.", "warning");
            return;
        }
        console.debug(`${submitFunctionName}: Found ${triggerGroups.length} trigger group(s) to parse.`);

        triggerGroups.forEach((group, index) => {
            if (!formIsValid) return; // Stop if previous trigger failed

            const triggerNum = group.id.split('-').pop();
            const triggerTypeSelect = group.querySelector(`#trigger_type_${triggerNum}`);
            const triggerType = triggerTypeSelect ? triggerTypeSelect.value : null;
            const startInput = group.querySelector(`#start_${triggerNum}`);
            const startValue = startInput ? startInput.value : null; // YYYY-MM-DDTHH:MM

            console.debug(`${submitFunctionName}: Parsing Trigger #${triggerNum} - Type: '${triggerType}', Start: '${startValue}'`);

            // Validate common fields
            if (!triggerType) { formIsValid = false; showStatusMessage(`Trigger ${index + 1}: Please select a trigger type.`, "warning"); triggerTypeSelect?.focus(); }
            if (!startValue) { formIsValid = false; showStatusMessage(`Trigger ${index + 1}: Please select a start date & time.`, "warning"); startInput?.focus(); }
            if (!formIsValid) return;

            try {
                // Create base trigger object, converting start time to ISO UTC
                let triggerData = { type: triggerType, start: new Date(startValue).toISOString() };

                // Add type-specific data and validation
                switch (triggerType) {
                    case 'Daily':
                        const dailyIntervalInput = group.querySelector(`#interval_${triggerNum}`);
                        const dailyInterval = dailyIntervalInput ? parseInt(dailyIntervalInput.value, 10) : NaN;
                        if (isNaN(dailyInterval) || dailyInterval < 1) throw new Error("Daily interval must be 1 or greater.");
                        triggerData.interval = dailyInterval;
                        break;
                    case 'Weekly':
                        const weeklyIntervalInput = group.querySelector(`#interval_${triggerNum}`);
                        const weeklyInterval = weeklyIntervalInput ? parseInt(weeklyIntervalInput.value, 10) : NaN;
                        if (isNaN(weeklyInterval) || weeklyInterval < 1) throw new Error("Weekly interval must be 1 or greater.");
                        triggerData.interval = weeklyInterval;
                        const dayCheckboxes = group.querySelectorAll(`input[name="days_of_week_${triggerNum}"]:checked`);
                        triggerData.days = Array.from(dayCheckboxes).map(cb => cb.value);
                        if (triggerData.days.length === 0) throw new Error("Select at least one day for weekly trigger.");
                        break;
                    case 'Monthly':
                        const daysOfMonthInput = group.querySelector(`#days_of_month_${triggerNum}`);
                        const monthsInput = group.querySelector(`#months_${triggerNum}`);
                        triggerData.days = daysOfMonthInput ? daysOfMonthInput.value.split(',').map(d => d.trim()).filter(Boolean) : [];
                        triggerData.months = monthsInput ? monthsInput.value.split(',').map(m => m.trim()).filter(Boolean) : [];
                        // Basic validation for monthly fields
                        if (!triggerData.days.length || !triggerData.days.every(d => /^\d+$/.test(d) && parseInt(d) >= 1 && parseInt(d) <= 31)) throw new Error("Invalid Days of Month format (use 1-31, comma-separated).");
                        if (!triggerData.months.length || !triggerData.months.every(m => /^[a-zA-Z]+$/.test(m) || (/^\d+$/.test(m) && parseInt(m) >= 1 && parseInt(m) <= 12))) throw new Error("Invalid Months format (use Jan, Feb... or 1-12, comma-separated).");
                        break;
                    case 'TimeTrigger': // No extra fields
                        break;
                    default:
                        throw new Error(`Unsupported trigger type '${triggerType}' encountered during parsing.`);
                }
                triggers.push(triggerData); // Add valid trigger data
                console.debug(`${submitFunctionName}: Successfully parsed Trigger #${triggerNum}`, triggerData);
            } catch (validationError) {
                formIsValid = false;
                showStatusMessage(`Trigger ${index + 1}: ${validationError.message}`, "error");
                logger.warn(`${submitFunctionName}: Trigger validation failed.`, validationError);
            }
        }); // End triggerGroups.forEach

        if (!formIsValid) {
            console.warn(`${submitFunctionName}: Submission stopped due to trigger validation errors.`);
            return; // Stop if any trigger failed validation
        }
        if (triggers.length === 0) {
            showStatusMessage("Form submission failed: Could not parse any valid triggers.", "error");
            return;
        }
        console.log(`${submitFunctionName}: Final parsed triggers array:`, triggers);

        // --- Generate Task Name (JavaScript Version) ---
        const commandArgs = (command !== "scan-players") ? `--server ${serverName}` : ""; // Use JS ternary
        const nameDescriptor = commandArgs ? commandArgs : command;
        const sanitizedDescriptor = nameDescriptor.replace(/[^a-zA-Z0-9_]/g, '_').replace(/_+/g, '_').substring(0, 30);
        const timestamp = new Date().toISOString().replace(/[-:.]/g, '').substring(0, 15);
        let newTaskName = `bedrock_${serverName}_${sanitizedDescriptor}_${timestamp}`;
        newTaskName = newTaskName.replace(/_+/g, '_').substring(0, 200);
        console.debug(`${submitFunctionName}: Generated NEW task name (JS): '${newTaskName}'`);
        // --- End JS Name Generation ---

        // --- Prepare API Request ---
        let method;
        let actionPath;
        const requestBody = {
            command: command,
            triggers: triggers,
            command_args: commandArgs // Include determined command_args
        };

        if (originalTaskName) { // MODIFY
            method = 'PUT';
            actionPath = `task_scheduler/task/${encodeURIComponent(originalTaskName)}`;
            requestBody.new_task_name = newTaskName; // Send the newly generated name
            console.log(`${submitFunctionName}: Preparing MODIFY request to: ${actionPath}`);
        } else { // ADD
            method = 'POST';
            actionPath = 'task_scheduler/add';
            requestBody.task_name = newTaskName; // Send generated name for add
            console.log(`${submitFunctionName}: Preparing ADD request to: ${actionPath}`);
        }
        console.debug(`${submitFunctionName}: Request Body:`, requestBody);

        // --- Send API Request using utility function ---
        console.log(`${submitFunctionName}: Calling sendServerActionRequest...`);
        // Pass correct serverName read from dataset
        const apiResponseData = await sendServerActionRequest(
            serverName, // Use serverName read from form's data attribute
            actionPath,
            method,
            requestBody,
            currentElements.submitButton
        );
        console.log(`${submitFunctionName}: Add/Modify API call finished. Response data:`, apiResponseData);

        // --- Handle Response ---
        if (apiResponseData && apiResponseData.status === 'success') {
            console.log(`${submitFunctionName}: Task ${originalTaskName ? 'modification' : 'addition'} successful.`);
            showStatusMessage(apiResponseData.message || `Task ${originalTaskName ? 'modified' : 'added'} successfully! Reloading...`, 'success');
            cancelTaskForm(); // Hide/reset form
            setTimeout(() => { window.location.reload(); }, 1500); // Reload list
        } else {
            console.error(`${submitFunctionName}: Task ${originalTaskName ? 'modification' : 'addition'} failed.`);
            // Error message handled by sendServerActionRequest, including validation errors from API
            // Button is re-enabled automatically by the utility function on failure/error.
        }
    }); // --- End submit listener ---

    console.log(`${functionName}: Task form submit listener attached.`);
}); // --- End DOMContentLoaded ---