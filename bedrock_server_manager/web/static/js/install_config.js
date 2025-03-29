// bedrock-server-manager/bedrock_server_manager/web/static/js/install_config.js

// Depends on: utils.js (showStatusMessage, sendServerActionRequest)

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
                // Prompt the user with the message from the backend
                if (confirm(apiResponseData.message || `Server '${serverName}' already exists. Overwrite all its files? THIS CANNOT BE UNDONE.`)) {
                    // User confirmed overwrite
                    console.log("Overwrite confirmed by user. Preparing second API request with overwrite: true.");
                    showStatusMessage("Overwrite confirmed. Re-attempting installation...", "info"); // Inform user

                    // Construct request body for overwrite
                    const overwriteRequestBody = {
                        server_name: serverName,
                        server_version: serverVersion, // Send version again just in case
                        overwrite: true // Set overwrite flag
                    };
                    console.log("Constructed overwrite install request body:", overwriteRequestBody);

                    // --- Second API Call (Attempt install WITH overwrite) ---
                    console.log("Calling sendServerActionRequest for overwrite install attempt...");
                    // Pass the same button element to disable during the second request
                    sendServerActionRequest(null, '/api/server/install', 'POST', overwriteRequestBody, buttonElement)
                        .then(finalApiResponseData => { // Response from the second (overwrite) call
                            console.log("Overwrite install API call completed. Response data:", finalApiResponseData);

                            // Check if the second call failed at HTTP/Network level
                            if (finalApiResponseData === false) {
                                console.error("Install/Overwrite (second call) failed at HTTP/Network level or returned false.");
                                // Button should be re-enabled by sendServerActionRequest
                                return;
                            }

                            // Check application status *within* the second response object
                            if (finalApiResponseData.status === 'success') {
                                // --- Success on Overwrite Install ---
                                console.log("Install/Overwrite successful (application status: success).");
                                // Check for the next step URL provided in the *successful overwrite response*
                                const nextUrl = finalApiResponseData.next_step_url;
                                console.log("Extracted next_step_url from overwrite response:", nextUrl);

                                if (nextUrl) {
                                    console.log("Navigating to configuration sequence after successful overwrite...");
                                    showStatusMessage("Server installed (overwrite successful)! Proceeding to configuration...", "success");
                                    setTimeout(() => {
                                        console.log(`Navigating to: ${nextUrl}`);
                                        window.location.href = nextUrl;
                                    }, 1500); // Delay for user to read message
                                } else {
                                     console.warn("Install/Overwrite successful, but no next_step_url provided in the final response. Staying on page.");
                                     showStatusMessage("Server installed (overwrite successful)! Configuration URL missing.", "warning");
                                     // Button should be re-enabled by sendServerActionRequest
                                }
                            } else {
                                 // Overwrite attempt failed at the application level (e.g., permissions error during overwrite)
                                 console.error(`Install/Overwrite failed (application status: ${finalApiResponseData.status}). Message: ${finalApiResponseData.message}`);
                                 // Error message already shown by sendServerActionRequest based on finalApiResponseData
                                 // Button should be re-enabled by sendServerActionRequest
                            }
                        }); // End of .then() for second API call

                } else { // User cancelled the confirmation dialog
                    console.log("Overwrite cancelled by user.");
                    showStatusMessage("Installation cancelled (overwrite not confirmed).", "info");
                    // Manually re-enable the button because sendServerActionRequest kept it disabled for 'confirm_needed'
                    if (buttonElement) {
                        console.log("Re-enabling button after user cancelled confirmation.");
                        buttonElement.disabled = false;
                    }
                }
            } else if (apiResponseData.status === 'success') {
                 // --- Handle Direct Success (New Install, no overwrite needed) ---
                 console.log("New install successful (application status: success).");
                 // Check for the next step URL provided in the *initial successful response*
                 const nextUrl = apiResponseData.next_step_url;
                 console.log("Extracted next_step_url from initial response:", nextUrl);

                 if (nextUrl) {
                      console.log("Navigating to configuration sequence after successful new install...");
                      showStatusMessage("Server installed successfully! Proceeding to configuration...", "success");
                      setTimeout(() => {
                          console.log(`Navigating to: ${nextUrl}`);
                          window.location.href = nextUrl;
                      }, 1500); // Delay for user to read message
                 } else {
                      console.warn("New install successful, but no next_step_url provided in the initial response. Staying on page.");
                      showStatusMessage("Server installed successfully! Configuration URL missing.", "warning");
                      // Button should be re-enabled by sendServerActionRequest
                 }
            } else {
                 // --- Handle other non-success, non-confirm_needed statuses from initial call ---
                 // e.g., validation errors ('validation_error'), general errors ('error')
                 console.error(`Initial install attempt failed (application status: ${apiResponseData.status}). Message: ${apiResponseData.message}`);
                 // Error/validation messages should have been displayed by sendServerActionRequest
                 // Button should be re-enabled by sendServerActionRequest
            }
        }); // End of .then() for initial API call
    console.log("Returned from initiating sendServerActionRequest call for trigger install server (async).");
}

/**
 * Gathers server property data from the form and saves it via API.
 * Handles navigation to the next step if part of a new server installation sequence.
 * Clears previous validation errors before sending the request.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function saveProperties(buttonElement, serverName, isNewInstall) {
    // Log function entry
    console.log(`saveProperties called - Server: ${serverName}, NewInstall: ${isNewInstall}, Button:`, buttonElement);

    // --- गैदर Form Data ---
    const propertiesData = {}; // Object to hold property key-value pairs
    // List the IDs of the input/select elements whose values need to be collected
    // These IDs should ideally match the 'name' attributes used by the backend
    const propertyIds = [
        'server-name', 'level-name', 'gamemode', 'difficulty', 'allow-cheats',
        'max-players', 'server-port', 'server-portv6', 'enable-lan-visibility',
        'allow-list', 'default-player-permission-level', 'view-distance',
        'tick-distance', 'level-seed', 'online-mode', 'texturepack-required'
        // Add any other property IDs from your server.properties form here
    ];

    console.log("Gathering data from property form elements:", propertyIds);
    propertyIds.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            // Use the element's 'name' attribute as the key if available, otherwise fallback to ID
            // This ensures keys match what the backend expects based on form names
            const propertyName = element.getAttribute('name') || id;
            let value = element.value; // Get the value

            // --- Value Type Handling (Example) ---
            // If you have checkboxes representing boolean values, handle them explicitly:
            // if (element.type === 'checkbox') {
            //     value = element.checked; // Send true/false instead of 'on'/'off'
            //     console.log(`Processed checkbox '${propertyName}': ${value}`);
            // } else {
            //     console.log(`Processed input/select '${propertyName}': ${value}`);
            // }

            // Assign the value to the corresponding property name in the data object
            propertiesData[propertyName] = value;
        } else {
             // Log a warning if an expected form element is not found
             console.warn(`Element with ID '${id}' not found in the properties form.`);
        }
    });

    console.log("Properties data gathered:", propertiesData);

    // --- Clear previous validation errors ---
    console.log("Clearing previous validation error messages.");
    // Clear general error message area
    const generalErrorArea = document.getElementById('validation-error-area');
    if (generalErrorArea) {
        generalErrorArea.textContent = '';
        generalErrorArea.innerHTML = ''; // Clear potential HTML content too
        console.log("Cleared general validation error area.");
    }
     // Clear specific field error placeholders
    document.querySelectorAll('.validation-error').forEach(el => {
        el.textContent = '';
    });
    console.log("Cleared specific field validation error elements.");

    // --- Call API ---
    // Use the generic action helper, targeting the properties API endpoint (absolute path)
    console.log("Calling sendServerActionRequest to save properties...");
    sendServerActionRequest(null, `/api/server/${serverName}/properties`, 'POST', propertiesData, buttonElement)
        .then(apiResponseData => { // Check the actual response data
             console.log("saveProperties API call completed. Response data:", apiResponseData);
             // Check if the API call was successful (returned data object with status 'success')
            if (apiResponseData && apiResponseData.status === 'success') {
                console.log("Properties save API call successful.");
                if (isNewInstall) {
                    // If save was successful AND it's part of a new install, navigate to the next step
                    console.log("Properties saved during new install, navigating to allowlist configuration after delay...");
                    showStatusMessage("Properties saved successfully! Proceeding to Allowlist...", "success"); // Give feedback
                    setTimeout(() => {
                        const nextUrl = `/server/${serverName}/configure_allowlist?new_install=True`;
                        console.log(`Navigating to: ${nextUrl}`);
                        window.location.href = nextUrl;
                    }, 1500); // Slightly longer delay for reading message
                } else {
                     // Properties saved successfully, but not part of new install sequence
                     console.log("Properties saved successfully (not new install).");
                     // Success message already shown by sendServerActionRequest
                }
            } else {
                 // API call failed (returned false), had validation errors, or app status wasn't 'success'
                 // Error/validation messages already shown by sendServerActionRequest
                 console.log("Properties save failed or had validation errors. No navigation.");
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
            console.log(`Mapped XUID ${xuid} to permission level '${selectedLevel}'`);
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
                        const nextUrl = `/server/${serverName}/configure_service?new_install=True`;
                        console.log(`Navigating to: ${nextUrl}`);
                        window.location.href = nextUrl;
                    }, 1500);
                } else {
                     // Permissions saved successfully, but not part of new install sequence
                     console.log("Permissions saved successfully (not new install).");
                     // Success message already shown by sendServerActionRequest
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
 * Gathers service settings (like autostart, autoupdate) from the form and saves them via API.
 * Optionally triggers a server start via a separate API call if `isNewInstall` is true and the user checked the 'start server' box.
 * Handles navigation to the main page upon completion if `isNewInstall` is true.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {string} currentOs The OS detected by the backend ('Linux', 'Windows', etc.), used to determine relevant settings.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function saveServiceSettings(buttonElement, serverName, currentOs, isNewInstall) {
    // Log function entry
    console.log(`saveServiceSettings called - Server: ${serverName}, OS: ${currentOs}, NewInstall: ${isNewInstall}, Button:`, buttonElement);

    const requestBody = {}; // Object to hold service settings
    let startServerAfter = false; // Flag to determine if server should be started after saving

    // --- Gather Data Based on OS ---
    console.log(`Gathering service settings based on OS: ${currentOs}`);
    if (currentOs === 'Linux') {
        // Gather Linux-specific settings (e.g., systemd service options)
        const autoupdateCheckbox = document.getElementById('service-autoupdate');
        const autostartCheckbox = document.getElementById('service-autostart');
        requestBody.autoupdate = autoupdateCheckbox ? autoupdateCheckbox.checked : false;
        requestBody.autostart = autostartCheckbox ? autostartCheckbox.checked : false;
        console.log(`Linux settings gathered: autoupdate=${requestBody.autoupdate}, autostart=${requestBody.autostart}`);
    } else if (currentOs === 'Windows') {
        // Gather Windows-specific settings (e.g., Scheduled Task options)
        const autoupdateCheckbox = document.getElementById('service-autoupdate');
        requestBody.autoupdate = autoupdateCheckbox ? autoupdateCheckbox.checked : false;
        // Note: Autostart might be implicitly handled by service creation or other means on Windows,
        // so it might not have a dedicated checkbox in this specific form.
        console.log(`Windows settings gathered: autoupdate=${requestBody.autoupdate}`);
    } else {
        // Handle unsupported OS provided by backend (should ideally not happen if UI matches backend logic)
        console.error(`Unsupported OS detected: ${currentOs}. Cannot determine service settings.`);
        showStatusMessage("Cannot save settings: Unsupported operating system detected.", "error");
        return; // Stop execution
    }

    // Check if server should be started afterwards (only relevant during new install sequence)
    if (isNewInstall) {
        const startServerCheckbox = document.getElementById('service-start-server');
        startServerAfter = startServerCheckbox ? startServerCheckbox.checked : false;
        console.log(`New install sequence: Checkbox 'service-start-server' checked = ${startServerAfter}`);
    } else {
        console.log("Not a new install sequence, 'start server after save' option is ignored.");
    }

    console.log("Final service settings request body:", requestBody);
    console.log("Start server after save:", startServerAfter);


    // --- Call API to Save Settings ---
    console.log("Calling sendServerActionRequest to save service settings...");
    sendServerActionRequest(null, `/api/server/${serverName}/service`, 'POST', requestBody, buttonElement)
        .then(saveSuccessData => { // Check response from saving settings
            console.log("Save service settings API call completed. Response data:", saveSuccessData);

            if (saveSuccessData && saveSuccessData.status === 'success') {
                console.log("Service settings saved successfully.");
                // Success message is shown by sendServerActionRequest

                if (startServerAfter) {
                    // If settings saved AND user requested start during new install
                    console.log("Proceeding to start server via API call as requested...");
                    showStatusMessage("Service settings saved. Attempting to start server...", "info"); // Inform user

                    // Attempt to find the generic start button on the page to disable it during start request
                    // This might not exist on this specific config page, so handle null.
                    const startButton = document.getElementById('start-server-btn'); // May be null
                    console.log("Attempting to find start button for disable:", startButton);

                    // Call the standard server start action via the helper function
                    sendServerActionRequest(serverName, 'start', 'POST', null, startButton) // Pass null if button not found
                       .then(startSuccessData => { // Check response from starting server
                           console.log("Start server API call completed. Response data:", startSuccessData);
                           if (startSuccessData && startSuccessData.status === 'success') {
                               // Server started successfully
                               console.log("Server started successfully after new install configuration.");
                               if (isNewInstall) {
                                   // Navigate to main page after successful start in new install sequence
                                   showStatusMessage("Server started successfully! Redirecting to dashboard...", "success");
                                   setTimeout(() => {
                                       console.log("Redirecting to /");
                                       window.location.href = "/";
                                    }, 2000); // Redirect after 2 seconds
                               } else {
                                   // Server started successfully (not new install) - message already shown
                               }
                           } else {
                                // Server start failed
                                console.warn("Failed to start server after saving service settings.");
                                showStatusMessage("Service settings saved, but the server failed to start. Check server logs.", "warning");
                                // Don't redirect on failure, let user see the error and potentially retry starting manually
                                // Re-enable the main save button if it wasn't re-enabled automatically
                                if (buttonElement) buttonElement.disabled = false;
                           }
                       });
                } else if (isNewInstall) {
                    // Settings saved, but user didn't request start - navigate to main page for new install
                    console.log("Service settings saved, server start not requested. Proceeding with navigation for new install.");
                    showStatusMessage("Service settings saved! Redirecting to dashboard...", "success");
                    setTimeout(() => {
                        console.log("Redirecting to /");
                        window.location.href = "/";
                    }, 1500); // Redirect after 1.5 seconds
                } else {
                     // Settings saved successfully (not new install) - nothing more to do here
                     console.log("Service settings saved successfully (not new install).");
                }
            } else {
                 // Saving service settings failed
                 console.error("Saving service settings failed. API response indicated failure or error.");
                 // Error message already shown by sendServerActionRequest
                 // Button should have been re-enabled by sendServerActionRequest
            }
        });
    console.log("Returned from initiating sendServerActionRequest call for save service settings (async).");
}