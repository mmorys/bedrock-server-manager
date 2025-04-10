// bedrock-server-manager/bedrock_server_manager/web/static/js/allowlist.js
/**
 * @fileoverview Frontend JavaScript for managing the server allowlist.
 * Handles user input, interacts with the allowlist API endpoints, and updates the UI.
 * Depends on functions defined in utils.js (showStatusMessage, sendServerActionRequest).
 */

// Ensure utils.js is loaded before this script
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("Error: Missing required functions from utils.js. Ensure utils.js is loaded first.");
    // Optionally display an error to the user on the page itself
}

/**
 * Gathers allowlist player names from the main form textarea, validates them,
 * constructs the request body including the 'ignoresPlayerLimit' flag, and sends
 * it to the API endpoint responsible for **replacing** the current allowlist.
 * On success, handles navigation to the next step if part of a new server installation sequence.
 *
 * @async
 * @param {HTMLButtonElement} buttonElement - The button element that triggered the save action (used for disabling).
 * @param {string} serverName - The name of the server whose allowlist is being configured.
 * @param {boolean} isNewInstall - Flag indicating if this operation is part of the new server setup workflow.
 */
async function saveAllowlist(buttonElement, serverName, isNewInstall) {
    const functionName = 'saveAllowlist';
    console.log(`${functionName}: Initiated. Server: ${serverName}, NewInstall: ${isNewInstall}`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Get DOM Elements ---
    const textArea = document.getElementById('player-names');
    const ignoreLimitCheckbox = document.getElementById('ignore-limit-checkbox');

    if (!textArea || !ignoreLimitCheckbox) {
        const errorMsg = "Required form elements ('player-names' textarea or 'ignore-limit-checkbox') not found on the page.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(`Internal page error: ${errorMsg}`, "error");
        return; // Stop execution if elements are missing
    }
    console.debug(`${functionName}: Found required form elements.`);

    // --- Process Input ---
    const playerNamesRaw = textArea.value;
    // Split by newline, trim whitespace from each line, filter out empty lines
    const playerNames = playerNamesRaw.split('\n')
                                    .map(name => name.trim())
                                    .filter(name => name.length > 0);

    const ignoresPlayerLimit = ignoreLimitCheckbox.checked;

    console.debug(`${functionName}: Processed player names (count: ${playerNames.length}):`, playerNames);
    console.debug(`${functionName}: Ignores Player Limit setting: ${ignoresPlayerLimit}`);

    // NOTE: Sending an empty playerNames array is valid and should clear the allowlist on the backend.

    // --- Construct API Request ---
    const requestBody = {
        players: playerNames, // List of names
        ignoresPlayerLimit: ignoresPlayerLimit // Single boolean for the entire list (backend applies)
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Send API Request ---
    // Use the API endpoint that REPLACES the allowlist (POST /api/server/.../allowlist)
    const apiUrl = `/api/server/${serverName}/allowlist`;
    console.log(`${functionName}: Calling sendServerActionRequest to save/replace allowlist at ${apiUrl}...`);

    // Use await to wait for the API call to complete before proceeding
    const apiResponseData = await sendServerActionRequest(null, apiUrl, 'POST', requestBody, buttonElement);

    console.log(`${functionName}: Save allowlist API call finished. Response data:`, apiResponseData);

    // --- Handle API Response ---
    // sendServerActionRequest returns false on HTTP/network errors, or the parsed JSON object on HTTP success.
    if (apiResponseData && apiResponseData.status === 'success') {
        // Application-level success
        console.log(`${functionName}: Allowlist save API call reported success.`);
        // Success message is typically shown by sendServerActionRequest, but we can add context.

        if (isNewInstall) {
            // Navigate to the next step in the installation sequence
            const nextStepMsg = "Allowlist configured! Proceeding to Player Permissions...";
            console.log(`${functionName}: ${nextStepMsg}`);
            showStatusMessage(nextStepMsg, "success"); // Provide specific feedback
            // Short delay before navigating
            setTimeout(() => {
                const nextUrl = `/server/${serverName}/configure_permissions?new_install=True`;
                console.log(`${functionName}: Navigating to next install step: ${nextUrl}`);
                window.location.href = nextUrl;
            }, 1500); // Slightly longer delay (1.5s)
        } else {
             // Standard save successful, maybe update UI if needed (though save replaces the whole list)
             console.log(`${functionName}: Allowlist saved successfully (standard configuration).`);
             // Optionally fetch and update display if needed, though save implies success.
             // fetchAndUpdateAllowlistDisplay(serverName);
        }
    } else {
        // API call failed (returned false) or application status was 'error'
        // Error messages (including validation errors) are shown by sendServerActionRequest
        console.error(`${functionName}: Allowlist save failed or application reported an error.`);
        // Button re-enabling is handled by sendServerActionRequest's finally block
    }
    console.log(`${functionName}: Execution finished.`);
}


/**
 * Gathers player names from the 'add players' textarea, validates them,
 * and sends a request to the API endpoint responsible for **adding** these
 * players to the existing allowlist. Refreshes the displayed allowlist on success.
 *
 * @async
 * @param {HTMLButtonElement} buttonElement - The 'Add Players' button element.
 * @param {string} serverName - The name of the server.
 */
async function addAllowlistPlayers(buttonElement, serverName) {
    const functionName = 'addAllowlistPlayers';
    console.log(`${functionName}: Initiated. Server: ${serverName}`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Get DOM Elements ---
    const textArea = document.getElementById('player-names-add'); // Specific textarea for adding
    const ignoreLimitCheckbox = document.getElementById('ignore-limit-add'); // Specific checkbox

    if (!textArea || !ignoreLimitCheckbox) {
        const errorMsg = "Required 'add player' form elements ('player-names-add', 'ignore-limit-add') not found.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(`Internal page error: ${errorMsg}`, "error");
        return;
    }
    console.debug(`${functionName}: Found 'add players' form elements.`);

    // --- Process Input ---
    const playerNamesRaw = textArea.value;
    const playersToAdd = playerNamesRaw.split('\n')
                                     .map(name => name.trim())
                                     .filter(name => name.length > 0);

    if (playersToAdd.length === 0) {
         const warnMsg = "No player names entered in the 'Add Players' text area.";
         console.warn(`${functionName}: ${warnMsg}`);
         showStatusMessage(warnMsg, "warning");
         return; // Don't proceed if no names provided
    }

    const ignoresPlayerLimit = ignoreLimitCheckbox.checked;
    console.debug(`${functionName}: Players to add (count: ${playersToAdd.length}):`, playersToAdd);
    console.debug(`${functionName}: Ignore player limit for these players: ${ignoresPlayerLimit}`);

    // --- Construct API Request ---
    const requestBody = {
        players: playersToAdd,
        ignoresPlayerLimit: ignoresPlayerLimit
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Send API Request ---
    // Use the specific endpoint for adding players (POST /api/server/.../allowlist/add)
    const apiUrl = `/api/server/${serverName}/allowlist/add`;
    console.log(`${functionName}: Calling sendServerActionRequest to add players at ${apiUrl}...`);

    const apiResponseData = await sendServerActionRequest(null, apiUrl, 'POST', requestBody, buttonElement);

    console.log(`${functionName}: Add players API call finished. Response data:`, apiResponseData);

    // --- Handle API Response ---
    if (apiResponseData && apiResponseData.status === 'success') {
        console.log(`${functionName}: Add players API call reported success.`);
        // Success message shown by sendServerActionRequest

        // Clear the 'add' text area on success
        console.debug(`${functionName}: Clearing 'add players' textarea.`);
        textArea.value = '';
        // Optionally reset checkbox
        // ignoreLimitCheckbox.checked = false;

        // Refresh the displayed allowlist to show the newly added players
        console.log(`${functionName}: Initiating allowlist display refresh.`);
        await fetchAndUpdateAllowlistDisplay(serverName); // Await the update

    } else {
        console.error(`${functionName}: Adding players failed or application reported an error.`);
        // Error message shown by sendServerActionRequest
        // Button re-enabling handled by sendServerActionRequest
    }
    console.log(`${functionName}: Execution finished.`);
}

/**
 * Fetches the current allowlist from the API and updates the
 * `#current-allowlist-display` list element on the page.
 * Handles showing/hiding/creating a 'no players' message element.
 *
 * @async
 * @param {string} serverName - The name of the server whose allowlist should be fetched and displayed.
 */
async function fetchAndUpdateAllowlistDisplay(serverName) {
    const functionName = 'fetchAndUpdateAllowlistDisplay';
    console.log(`${functionName}: Initiating for server: ${serverName}`);

    const displayList = document.getElementById('current-allowlist-display'); // The UL/OL element
    // Keep track of the 'no players' message dynamically
    let noPlayersLi = document.getElementById('no-players-message');

    if (!displayList) {
        console.error(`${functionName}: Target display element '#current-allowlist-display' not found. Cannot update UI.`);
        // Optionally show a general status message if the core UI element is missing
        // showStatusMessage("Error updating allowlist display: List element not found.", "error");
        return;
    }
    console.debug(`${functionName}: Found display list element.`);

    // Show a temporary loading state (optional)
    // displayList.innerHTML = '<li>Loading...</li>';

    try {
        // --- Fetch Current Allowlist ---
        const apiUrl = `/api/server/${serverName}/allowlist`;
        console.log(`${functionName}: Fetching current allowlist from ${apiUrl}`);
        const response = await fetch(apiUrl); // GET request by default

        console.debug(`${functionName}: Fetch response status: ${response.status}`);
        if (!response.ok) {
            // Handle HTTP errors during fetch
            const errorText = await response.text(); // Try to get error text from response
            throw new Error(`Failed to fetch allowlist (Status ${response.status}): ${errorText.substring(0,100)}`);
        }

        // --- Parse Response ---
        console.debug(`${functionName}: Parsing JSON response...`);
        const data = await response.json();
        console.debug(`${functionName}: Parsed allowlist data:`, data);

        // --- Update UI based on Parsed Data ---
        // Clear existing player list items (preserve the list element itself)
        displayList.querySelectorAll('li:not(#no-players-message)').forEach(li => li.remove());
        // Try finding the 'no players' item again in case it was removed/added dynamically
        noPlayersLi = document.getElementById('no-players-message');

        if (data.status === 'success' && Array.isArray(data.existing_players)) {
            const players = data.existing_players;
            console.log(`${functionName}: API success. Processing ${players.length} player entries.`);

            if (players.length > 0) {
                // Hide or remove the 'no players' message if it exists
                if (noPlayersLi) {
                    console.debug(`${functionName}: Hiding 'no players' message.`);
                    noPlayersLi.style.display = 'none';
                }
                // Populate list with current players
                players.forEach(player => {
                    const li = document.createElement('li');
                    // Ensure safe access to properties
                    const playerName = player.name || 'Unnamed Player';
                    const ignoresLimit = player.ignoresPlayerLimit ? 'Yes' : 'No';
                    li.textContent = `${playerName} (Ignores Limit: ${ignoresLimit})`;
                    // Optionally add other attributes like data-xuid if available and useful
                    displayList.appendChild(li);
                });
                 console.debug(`${functionName}: Added ${players.length} player items to the list.`);
            } else {
                 // Allowlist is empty, ensure 'no players' message is shown
                 console.log(`${functionName}: Allowlist is empty. Displaying 'no players' message.`);
                 if (noPlayersLi) {
                     console.debug(`${functionName}: Making existing 'no players' message visible.`);
                     noPlayersLi.style.display = ''; // Show existing element
                 } else {
                      // Create the message element if it doesn't exist at all
                      console.warn(`${functionName}: '#no-players-message' element not found. Creating it.`);
                      const li = document.createElement('li');
                      li.id = 'no-players-message';
                      li.textContent = 'No players currently in allowlist.';
                      li.style.fontStyle = 'italic'; // Example styling
                      displayList.appendChild(li);
                 }
            }
            console.log(`${functionName}: Allowlist display updated successfully.`);
        } else {
             // API reported failure or returned unexpected data format
             const errorMsg = `Could not refresh allowlist display: ${data.message || 'Invalid data format from API.'}`;
             console.error(`${functionName}: ${errorMsg}`);
             showStatusMessage(errorMsg, "warning");
             // Ensure 'no players' message is shown on error too?
             if (noPlayersLi) noPlayersLi.style.display = ''; else displayList.innerHTML = `<li id="no-players-message" style="color: red;">${errorMsg}</li>`;
        }

     } catch (error) {
          // Handle network errors or JSON parsing errors
          console.error(`${functionName}: Error during fetch or UI update:`, error);
          showStatusMessage(`Error refreshing allowlist: ${error.message}`, "error");
          // Optionally display error in the list area
           if (displayList) {
               displayList.innerHTML = `<li id="no-players-message" style="color: red;">Error loading allowlist.</li>`;
           }
     }
     console.log(`${functionName}: Execution finished.`);
}