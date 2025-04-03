// bedrock-server-manager/bedrock_server_manager/web/static/js/install_config.js

// Depends on: utils.js (showStatusMessage, sendServerActionRequest)

// --- Initialization for New Controls (Segmented & Toggles) ---
document.addEventListener('DOMContentLoaded', () => {
    console.log("Initializing controls for properties/config pages...");

    // --- Segmented Control Logic ---
    const segmentedControls = document.querySelectorAll('.segmented-control');
    console.log(`Found ${segmentedControls.length} segmented control wrappers.`);

    segmentedControls.forEach(controlWrapper => {
        const linkedInputId = controlWrapper.dataset.inputId; // Get ID of hidden input
        const linkedInput = document.getElementById(linkedInputId);
        const segments = controlWrapper.querySelectorAll('.segment');
        // console.log(`Processing segmented control linked to input: #${linkedInputId}`); // Verbose log

        if (!linkedInput) {
            console.warn(`Segmented control cannot find linked hidden input with ID: ${linkedInputId}`, controlWrapper);
            return; // Skip if hidden input is missing
        }

        segments.forEach(segment => {
            segment.addEventListener('click', (event) => {
                event.preventDefault(); // Prevent any default button behavior
                const clickedSegment = event.currentTarget;
                const newValue = clickedSegment.dataset.value; // Get value from data-value

                // console.log(`Segment clicked. Control: ${linkedInputId}, New Value: ${newValue}`); // Verbose log

                // 1. Update hidden input value
                linkedInput.value = newValue;
                // console.log(`Updated hidden input #${linkedInputId} value to: ${linkedInput.value}`); // Verbose log

                // 2. Update active class on segments within this group
                segments.forEach(s => s.classList.remove('active')); // Deactivate all in group
                clickedSegment.classList.add('active'); // Activate the clicked one
                // console.log(`Updated active class for segment with value: ${newValue}`); // Verbose log

                // Optional: Dispatch a 'change' event on the hidden input if other scripts need to react
                // linkedInput.dispatchEvent(new Event('change', { bubbles: true }));
            });
        });
    });

    // --- Toggle Switch Logic (Handling hidden 'false' value) ---
    const toggleInputs = document.querySelectorAll('.toggle-input');
    console.log(`Found ${toggleInputs.length} toggle switch input checkboxes.`);

    toggleInputs.forEach(input => {
        // Find the corresponding hidden input for the 'false' value
        const baseName = input.name.replace('-cb', ''); // Infer base name
        const hiddenFalseInput = input.closest('.form-group-toggle-container')?.querySelector(`.toggle-hidden-false[name="${baseName}"]`);

        if (!hiddenFalseInput) {
            console.warn(`Could not find hidden 'false' input for toggle: ${input.name} (name="${baseName}")`);
        }

        const syncHiddenFalse = () => {
            if (hiddenFalseInput) {
                // Disable the hidden 'false' input if the checkbox is checked
                hiddenFalseInput.disabled = input.checked;
                 // console.log(`Toggle ${input.id} checked: ${input.checked}, hidden input ${hiddenFalseInput.name} disabled: ${hiddenFalseInput.disabled}`); // Verbose log
            }
        };

        input.addEventListener('change', syncHiddenFalse);
        syncHiddenFalse(); // Initial state sync on page load
    });

     console.log("Controls initialized.");
});


// --- Action Functions ---

/**
 * Triggers the server installation process via API.
 * Handles backend response indicating if an overwrite confirmation is needed.
 * Sends a second request with `overwrite: true` if confirmed by the user.
 * Navigates to the first configuration step upon successful installation.
 * @param {HTMLElement} buttonElement The button that was clicked.
 */
function triggerInstallServer(buttonElement) {
    // Log function entry
    console.log("triggerInstallServer called. Button:", buttonElement);

    // Get references to input elements
    const serverNameInput = document.getElementById('install-server-name');
    const serverVersionInput = document.getElementById('install-server-version');

    // Validate that elements were found
    if (!serverNameInput || !serverVersionInput) {
        console.error("Required input elements ('install-server-name', 'install-server-version') not found!");
        showStatusMessage("Internal page error: Form elements missing.", "error");
        return;
    }
    console.log("Found install form input elements.");

    // Get and trim input values
    const serverName = serverNameInput.value.trim();
    const serverVersion = serverVersionInput.value.trim();
    console.log(`Server Name entered: "${serverName}", Server Version entered: "${serverVersion}"`);

    // --- Basic Frontend Validation ---
    if (!serverName) {
        console.warn("Validation failed: Server name is empty.");
        showStatusMessage('Server name cannot be empty.', 'warning');
        return;
    }
    if (!serverVersion) {
        console.warn("Validation failed: Server version is empty.");
        showStatusMessage('Server version cannot be empty.', 'warning');
        return;
    }
    // Example: Prevent potentially problematic characters in server names (like path separators or shell metacharacters)
    if (serverName.includes('/') || serverName.includes('\\') || serverName.includes(';') || serverName.includes('&') || serverName.includes('|')) {
        console.warn("Validation failed: Server name contains invalid characters.");
        showStatusMessage('Server name contains invalid characters (e.g., /, \\, ;, &, |). Please use a simple name.', 'error');
        return;
    }
    console.log("Frontend validation passed.");

    // --- Clear previous validation errors ---
    console.log("Clearing previous validation error messages.");
    const generalErrorArea = document.getElementById('validation-error-area');
    if (generalErrorArea) {
        generalErrorArea.textContent = '';
        generalErrorArea.innerHTML = '';
        generalErrorArea.style.display = 'none'; // Hide it
        console.log("Cleared general validation error area.");
    }
    document.querySelectorAll('.validation-error').forEach(el => {
        el.textContent = '';
    });
    console.log("Cleared specific field validation error elements.");

    // Construct the initial request body with overwrite set to false
    const requestBody = {
        server_name: serverName,
        server_version: serverVersion,
        overwrite: false // Initial request assumes no overwrite
    };
    console.log("Constructed initial install request body:", requestBody);

    // --- Initial API Call (Attempt install without overwrite) ---
    console.log("Calling sendServerActionRequest for initial install attempt...");
    sendServerActionRequest(null, '/api/server/install', 'POST', requestBody, buttonElement)
        .then(apiResponseData => { // This holds the parsed JSON object or `false`
            console.log("Initial install API call completed. Response data:", apiResponseData);

            // Check if the API call itself failed (returned false)
            if (apiResponseData === false) {
                 console.error("Initial install API call failed at HTTP/Network level or returned false.");
                 // Button should be re-enabled by sendServerActionRequest's finally block
                 return;
            }

            // --- Handle Application-Level Status from Response ---
            if (apiResponseData.status === 'confirm_needed') {
                // --- Handle Confirmation Needed for Overwrite ---
                console.log("Server response indicates confirmation needed (likely server exists). Message:", apiResponseData.message);
                if (confirm(apiResponseData.message || `Server '${serverName}' already exists. Overwrite all its files? THIS CANNOT BE UNDONE.`)) {
                    // User confirmed overwrite
                    console.log("Overwrite confirmed by user. Preparing second API request with overwrite: true.");
                    showStatusMessage("Overwrite confirmed. Re-attempting installation...", "info");

                    const overwriteRequestBody = {
                        server_name: serverName,
                        server_version: serverVersion,
                        overwrite: true
                    };
                    console.log("Constructed overwrite install request body:", overwriteRequestBody);

                    // --- Second API Call (Attempt install WITH overwrite) ---
                    console.log("Calling sendServerActionRequest for overwrite install attempt...");
                    sendServerActionRequest(null, '/api/server/install', 'POST', overwriteRequestBody, buttonElement)
                        .then(finalApiResponseData => {
                            console.log("Overwrite install API call completed. Response data:", finalApiResponseData);

                            if (finalApiResponseData === false) {
                                console.error("Install/Overwrite (second call) failed at HTTP/Network level or returned false.");
                                return;
                            }

                            if (finalApiResponseData.status === 'success') {
                                // --- Success on Overwrite Install ---
                                console.log("Install/Overwrite successful (application status: success).");
                                const nextUrl = finalApiResponseData.next_step_url;
                                console.log("Extracted next_step_url from overwrite response:", nextUrl);

                                if (nextUrl) {
                                    console.log("Navigating to configuration sequence after successful overwrite...");
                                    showStatusMessage("Server installed (overwrite successful)! Proceeding to configuration...", "success");
                                    setTimeout(() => {
                                        console.log(`Navigating to: ${nextUrl}`);
                                        window.location.href = nextUrl;
                                    }, 1500);
                                } else {
                                     console.warn("Install/Overwrite successful, but no next_step_url provided in the final response. Staying on page.");
                                     showStatusMessage("Server installed (overwrite successful)! Configuration URL missing.", "warning");
                                }
                            } else {
                                 console.error(`Install/Overwrite failed (application status: ${finalApiResponseData.status}). Message: ${finalApiResponseData.message}`);
                                 // Error message shown by sendServerActionRequest
                            }
                        }); // End of .then() for second API call

                } else { // User cancelled the confirmation dialog
                    console.log("Overwrite cancelled by user.");
                    showStatusMessage("Installation cancelled (overwrite not confirmed).", "info");
                    if (buttonElement) {
                        console.log("Re-enabling button after user cancelled confirmation.");
                        buttonElement.disabled = false;
                    }
                }
            } else if (apiResponseData.status === 'success') {
                 // --- Handle Direct Success (New Install, no overwrite needed) ---
                 console.log("New install successful (application status: success).");
                 const nextUrl = apiResponseData.next_step_url;
                 console.log("Extracted next_step_url from initial response:", nextUrl);

                 if (nextUrl) {
                      console.log("Navigating to configuration sequence after successful new install...");
                      showStatusMessage("Server installed successfully! Proceeding to configuration...", "success");
                      setTimeout(() => {
                          console.log(`Navigating to: ${nextUrl}`);
                          window.location.href = nextUrl;
                      }, 1500);
                 } else {
                      console.warn("New install successful, but no next_step_url provided in the initial response. Staying on page.");
                      showStatusMessage("Server installed successfully! Configuration URL missing.", "warning");
                 }
            } else {
                 // --- Handle other non-success, non-confirm_needed statuses from initial call ---
                 console.error(`Initial install attempt failed (application status: ${apiResponseData.status}). Message: ${apiResponseData.message}`);
                 // Error/validation messages should have been displayed by sendServerActionRequest
            }
        }); // End of .then() for initial API call
    console.log("Returned from initiating sendServerActionRequest call for trigger install server (async).");
}

/**
 * Gathers server property data from the form (including new controls) and saves it via API.
 * Handles navigation to the next step if part of a new server installation sequence.
 * Clears previous validation errors before sending the request.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function saveProperties(buttonElement, serverName, isNewInstall) {
    console.log(`saveProperties called - Server: ${serverName}, NewInstall: ${isNewInstall}, Button:`, buttonElement);

    // --- Gather Form Data ---
    const propertiesData = {};
    // Query ALL relevant input, select, textarea fields within the section/form
    const formElements = document.querySelectorAll('.properties-config-section .form-input, .properties-config-section .toggle-input, .properties-config-section input[type="hidden"]');
    console.log(`Found ${formElements.length} potential form elements for properties.`);

    formElements.forEach(element => {
        const name = element.getAttribute('name');
        if (!name) {
            // console.warn("Form element found without a 'name' attribute:", element); // Can be noisy
            return; // Skip elements without a name
        }

        // --- Handle different input types ---
        if (element.type === 'checkbox') {
            // For toggles, we rely on the hidden input for the 'false' value,
            // so only include the checkbox name/value if it's checked
            if (element.classList.contains('toggle-input') && element.checked) {
                 // Use the *base* name (without '-cb') as the key
                const baseName = name.replace('-cb', '');
                // Submit 'true' string (standard for properties)
                propertiesData[baseName] = 'true';
                // console.log(`Processed CHECKED toggle '${baseName}': ${propertiesData[baseName]}`); // Verbose
            } else if (!element.classList.contains('toggle-input')) {
                 // Handle standard checkboxes if any exist (unlikely in this form)
                 propertiesData[name] = element.checked ? 'true' : 'false';
            }
             // If toggle is unchecked, its value is handled by the enabled hidden input
        } else if (element.type === 'hidden') {
            // Include hidden inputs only if they are NOT disabled
            // (Handles segmented controls and 'false' for unchecked toggles)
            if (!element.disabled) {
                propertiesData[name] = element.value;
                 // console.log(`Processed ENABLED hidden input '${name}': ${propertiesData[name]}`); // Verbose
            } else {
                 // console.log(`Skipped DISABLED hidden input '${name}' (likely toggle false value)`); // Verbose
            }
        } else if (element.tagName === 'SELECT' || element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
             // Handle other standard inputs (text, number, select, textarea)
             propertiesData[name] = element.value;
             // console.log(`Processed input/select/textarea '${name}': ${propertiesData[name]}`); // Verbose
        }
    });

    console.log("Properties data gathered for submission:", propertiesData);

    // --- Clear validation ---
    console.log("Clearing previous validation error messages.");
    const generalErrorArea = document.getElementById('validation-error-area');
    if (generalErrorArea) { generalErrorArea.textContent = ''; generalErrorArea.style.display = 'none'; }
    document.querySelectorAll('.validation-error').forEach(el => el.textContent = '');
    console.log("Cleared validation messages.");


    // --- Call API ---
    console.log("Calling sendServerActionRequest to save properties...");
    sendServerActionRequest(null, `/api/server/${serverName}/properties`, 'POST', propertiesData, buttonElement)
        .then(apiResponseData => {
             console.log("saveProperties API call completed. Response data:", apiResponseData);
            if (apiResponseData && apiResponseData.status === 'success') {
                console.log("Properties save API call successful.");
                if (isNewInstall) {
                    console.log("Properties saved during new install, navigating to allowlist configuration after delay...");
                    showStatusMessage("Properties saved successfully! Proceeding to Allowlist...", "success");
                    setTimeout(() => {
                        const nextUrl = `/server/${encodeURIComponent(serverName)}/configure_allowlist?new_install=True`;
                        console.log(`Navigating to: ${nextUrl}`);
                        window.location.href = nextUrl;
                    }, 1500);
                } else {
                     console.log("Properties saved successfully (not new install).");
                     showStatusMessage(apiResponseData.message || "Properties saved successfully.", "success"); // Show success message
                }
            } else {
                 console.log("Properties save failed or had validation errors. No navigation.");
                 // Error/Validation message handled by sendServerActionRequest
            }
        });
    console.log("Returned from initiating sendServerActionRequest call for save properties (async).");
}


/**
 * Gathers player permission level data from the form and saves it via API using PUT.
 * Handles navigation to the next step if part of a new server installation sequence.
 * Clears previous validation errors before sending the request.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function savePermissions(buttonElement, serverName, isNewInstall) {
    // Log function entry
    console.log(`savePermissions called - Server: ${serverName}, NewInstall: ${isNewInstall}, Button:`, buttonElement);

    // --- Gather Permissions Data ---
    const permissionsMap = {}; // Object to map XUID -> permission level string
    // Select all dropdowns with the class 'permission-select'
    const permissionSelects = document.querySelectorAll('select.permission-select');
    console.log(`Found ${permissionSelects.length} permission select elements.`);

    if (permissionSelects.length === 0) {
         console.warn("No permission select elements found on the page. Permissions data will be empty.");
    }

    // Iterate over each select element found
    permissionSelects.forEach(select => {
        // Get the player's XUID from the 'data-xuid' attribute
        const xuid = select.dataset.xuid;
        // Get the selected permission level from the dropdown's value
        const selectedLevel = select.value;
        if (xuid) {
            // If XUID exists, add the mapping to the object
            permissionsMap[xuid] = selectedLevel;
            // console.log(`Mapped XUID ${xuid} to permission level '${selectedLevel}'`); // Verbose
        } else {
             // Log a warning if a select element is missing the data attribute
             console.warn("Found permission select element without a data-xuid attribute:", select);
        }
    });

    console.log("Permissions map gathered:", permissionsMap);

    // --- Clear previous validation errors ---
    console.log("Clearing previous validation error messages.");
    const generalErrorArea = document.getElementById('validation-error-area');
    if (generalErrorArea) {
        generalErrorArea.textContent = '';
        generalErrorArea.innerHTML = '';
        generalErrorArea.style.display = 'none';
        console.log("Cleared general validation error area.");
    }
    document.querySelectorAll('.validation-error').forEach(el => {
        el.textContent = '';
    });
    console.log("Cleared specific field validation error elements.");


    // --- Prepare request body ---
    const requestBody = {
        permissions: permissionsMap // Send the map under the 'permissions' key
    };
    console.log("Constructed request body for saving permissions:", requestBody);

    // --- Call API ---
    // Use PUT method, as we are typically replacing the entire permissions state for listed players
    console.log("Calling sendServerActionRequest to save permissions (PUT)...");
    sendServerActionRequest(null, `/api/server/${serverName}/permissions`, 'PUT', requestBody, buttonElement)
        .then(apiResponseData => { // Check the actual response data
            console.log("savePermissions API call completed. Response data:", apiResponseData);
            // Check if the API call was successful (returned data object with status 'success')
            if (apiResponseData && apiResponseData.status === 'success') {
                console.log("Permissions save API call successful.");
                if (isNewInstall) {
                    // If save was successful AND it's part of a new install, navigate to the next step
                    console.log("Permissions saved during new install, navigating to service configuration after delay...");
                    showStatusMessage("Permissions saved successfully! Proceeding to Service Config...", "success");
                    setTimeout(() => {
                        const nextUrl = `/server/${encodeURIComponent(serverName)}/configure_service?new_install=True`; // Use encodeURIComponent
                        console.log(`Navigating to: ${nextUrl}`);
                        window.location.href = nextUrl;
                    }, 1500);
                } else {
                     // Permissions saved successfully, but not part of new install sequence
                     console.log("Permissions saved successfully (not new install).");
                     showStatusMessage(apiResponseData.message || "Permissions saved successfully.", "success"); // Show success
                }
            } else {
                 // API call failed, had validation errors, or app status wasn't 'success'
                 // Error messages (including validation) shown by sendServerActionRequest
                 console.log("Permissions save failed or had validation errors. No navigation.");
            }
        });
    console.log("Returned from initiating sendServerActionRequest call for save permissions (async).");
}


/**
 * Gathers service settings (including new toggles) from the form and saves them via API.
 * Optionally triggers a server start via a separate API call if `isNewInstall` is true and the user checked the 'start server' box.
 * Handles navigation to the main page upon completion if `isNewInstall` is true.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} currentOs The OS detected by the backend ('Linux', 'Windows', etc.), used to determine relevant settings.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function saveServiceSettings(buttonElement, serverName, currentOs, isNewInstall) {
    console.log(`saveServiceSettings called - Server: ${serverName}, OS: ${currentOs}, NewInstall: ${isNewInstall}, Button:`, buttonElement);

    const requestBody = {};
    let startServerAfter = false;

    console.log(`Gathering service settings based on OS: ${currentOs}`);
    const section = document.querySelector('.service-config-section');
    if (!section) {
         console.error("Service config section not found!");
         showStatusMessage("Internal page error: Cannot find settings form.", "error");
         return;
    }

    // --- Gather Common Settings (Handles toggles correctly) ---
    const autoupdateCheckbox = section.querySelector('#service-autoupdate'); // This is the .toggle-input
    // Value will be 'true' or 'false' string based on checkbox state + hidden input logic
    if (autoupdateCheckbox) {
         const autoupdateHidden = section.querySelector('input[name="autoupdate"].toggle-hidden-false');
         requestBody.autoupdate = autoupdateCheckbox.checked ? 'true' : (autoupdateHidden ? 'false' : 'true'); // Default to true if hidden missing? Or error?
    }

    // --- Gather OS-Specific Settings ---
    if (currentOs === 'Linux') {
        const autostartCheckbox = section.querySelector('#service-autostart'); // The .toggle-input
        if (autostartCheckbox) {
             const autostartHidden = section.querySelector('input[name="autostart"].toggle-hidden-false');
            requestBody.autostart = autostartCheckbox.checked ? 'true' : (autostartHidden ? 'false' : 'true');
        }
        console.log(`Linux settings gathered: autoupdate=${requestBody.autoupdate}, autostart=${requestBody.autostart}`);
    } else if (currentOs === 'Windows') {
        console.log(`Windows settings gathered: autoupdate=${requestBody.autoupdate}`);
    } else {
        console.error(`Unsupported OS detected: ${currentOs}. Cannot determine service settings.`);
        showStatusMessage("Cannot save settings: Unsupported operating system detected.", "error");
        return;
    }

    // Check if server should be started afterwards (new install only)
    if (isNewInstall) {
        const startServerCheckbox = section.querySelector('#service-start-server'); // The .toggle-input
        startServerAfter = startServerCheckbox ? startServerCheckbox.checked : false;
        console.log(`New install sequence: Checkbox 'service-start-server' checked = ${startServerAfter}`);
    }

    console.log("Final service settings request body:", requestBody);
    console.log("Start server after save:", startServerAfter);

    // --- Call API to Save Settings ---
    console.log("Calling sendServerActionRequest to save service settings...");
    sendServerActionRequest(null, `/api/server/${serverName}/service`, 'POST', requestBody, buttonElement)
        .then(saveSuccessData => {
            console.log("Save service settings API call completed. Response data:", saveSuccessData);
            if (saveSuccessData && saveSuccessData.status === 'success') {
                console.log("Service settings saved successfully.");
                // Success message is shown by sendServerActionRequest

                if (startServerAfter) {
                    console.log("Proceeding to start server via API call as requested...");
                    showStatusMessage("Service settings saved. Attempting to start server...", "info");
                    const startButton = document.getElementById('start-server-btn'); // May be null
                    console.log("Attempting to find start button for disable:", startButton);
                    sendServerActionRequest(serverName, 'start', 'POST', null, startButton) // Pass null if button not found
                       .then(startSuccessData => {
                           console.log("Start server API call completed. Response data:", startSuccessData);
                           if (startSuccessData && startSuccessData.status === 'success') {
                               console.log("Server started successfully after new install configuration.");
                               if (isNewInstall) {
                                   showStatusMessage("Server started successfully! Redirecting to dashboard...", "success");
                                   setTimeout(() => {
                                       console.log("Redirecting to /");
                                       window.location.href = "/";
                                    }, 2000);
                               } else {
                                    // showStatusMessage(startSuccessData.message || "Server started successfully.", "success"); // Handled by sendServer..
                               }
                           } else {
                                console.warn("Failed to start server after saving service settings.");
                                showStatusMessage("Service settings saved, but the server failed to start. Check server logs.", "warning");
                                if (buttonElement) buttonElement.disabled = false;
                           }
                       });
                } else if (isNewInstall) {
                    console.log("Service settings saved, server start not requested. Proceeding with navigation for new install.");
                    showStatusMessage("Service settings saved! Redirecting to dashboard...", "success");
                    setTimeout(() => {
                        console.log("Redirecting to /");
                        window.location.href = "/";
                    }, 1500);
                } else {
                     console.log("Service settings saved successfully (not new install).");
                     showStatusMessage(saveSuccessData.message || "Service settings saved successfully.", "success"); // Show success
                }
            } else {
                 console.error("Saving service settings failed. API response indicated failure or error.");
            }
        });
    console.log("Returned from initiating sendServerActionRequest call for save service settings (async).");
}