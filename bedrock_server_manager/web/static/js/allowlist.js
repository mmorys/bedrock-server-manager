// bedrock-server-manager/bedrock_server_manager/web/static/js/allowlist.js

// Depends on: utils.js (showStatusMessage, sendServerActionRequest)

/**
 * Gathers allowlist data from the form and saves it via API.
 * Handles navigation to the next step if part of a new server installation sequence.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 * @param {boolean} isNewInstall Indicates if this is part of the new install sequence.
 */
function saveAllowlist(buttonElement, serverName, isNewInstall) {
    // Log function entry
    console.log(`saveAllowlist called - Server: ${serverName}, NewInstall: ${isNewInstall}, Button:`, buttonElement);

    // Get references to form elements
    const textArea = document.getElementById('player-names');
    const ignoreLimitCheckbox = document.getElementById('ignore-limit-checkbox');

    // Validate that elements were found
    if (!textArea || !ignoreLimitCheckbox) {
        console.error("Required elements ('player-names' textarea or 'ignore-limit-checkbox') not found!");
        showStatusMessage("Internal page error: Form elements missing.", "error");
        return;
    }
    console.log("Found allowlist form elements.");

    // Get player names from textarea: split by newline, trim whitespace, filter out empty lines
    const playerNamesRaw = textArea.value;
    const playerNames = playerNamesRaw.split('\n')
                                    .map(name => name.trim()) // Remove leading/trailing whitespace
                                    .filter(name => name.length > 0); // Remove empty strings

    // Get the state of the 'ignoresPlayerLimit' checkbox
    const ignoresPlayerLimit = ignoreLimitCheckbox.checked;

    console.log("Processed Player names:", playerNames);
    console.log("Ignore player limit:", ignoresPlayerLimit);

    // Construct the request body
    const requestBody = {
        players: playerNames,
        ignoresPlayerLimit: ignoresPlayerLimit
    };
    console.log("Constructed request body for saving allowlist:", requestBody);

    // Call the action helper, targeting the allowlist API endpoint (absolute path)
    console.log("Calling sendServerActionRequest to save allowlist...");
    sendServerActionRequest(null, `/api/server/${serverName}/allowlist`, 'POST', requestBody, buttonElement)
        .then(apiResponseData => { // Check the actual response data object
             console.log("saveAllowlist API call completed. Response data:", apiResponseData);
             // Check if the API call was successful (returned data object with status 'success')
             if (apiResponseData && apiResponseData.status === 'success') {
                 console.log("Allowlist save API call successful.");
                 if (isNewInstall) {
                     // If save was successful AND it's part of a new install, navigate to the next step
                     console.log("Allowlist saved during new install, navigating to permissions configuration after delay...");
                     // Show success message (already shown by sendServerActionRequest, but can add context)
                     showStatusMessage("Allowlist saved! Proceeding to Permissions...", "success");
                     // Short delay to allow user to read success message
                     setTimeout(() => {
                         const nextUrl = `/server/${serverName}/configure_permissions?new_install=True`;
                         console.log(`Navigating to: ${nextUrl}`);
                         window.location.href = nextUrl;
                     }, 1000); // 1 second delay
                 } else {
                      // Allowlist saved successfully, but not part of new install sequence
                      console.log("Allowlist saved successfully (not new install).");
                      // Optional: Give additional feedback or UI update if needed
                 }
             } else {
                  // API call failed (returned false) or application status was not 'success'
                  // Error message was already shown by sendServerActionRequest
                  console.log("Allowlist save failed or application status was not 'success'. No navigation.");
             }
        });
    console.log("Returned from initiating sendServerActionRequest call for save allowlist (async).");
}


/**
 * Gathers player names from the 'add players' form section and adds them to the allowlist via API.
 * Refreshes the displayed allowlist on success.
 * @param {HTMLElement} buttonElement The button that was clicked.
 * @param {string} serverName The name of the server.
 */
function addAllowlistPlayers(buttonElement, serverName) {
    // Log function entry
    console.log(`addAllowlistPlayers called - Server: ${serverName}, Button:`, buttonElement);

    // Get references to form elements for adding players
    const textArea = document.getElementById('player-names-add');
    const ignoreLimitCheckbox = document.getElementById('ignore-limit-add');

    // Validate that elements were found
    if (!textArea || !ignoreLimitCheckbox) {
        console.error("Required elements ('player-names-add' textarea or 'ignore-limit-add' checkbox) not found!");
        showStatusMessage("Internal page error: Form elements missing.", "error");
        return;
    }
    console.log("Found 'add players' form elements.");

    // Get player names from textarea: split, trim, filter empty
    const playerNamesRaw = textArea.value;
    const playersToAdd = playerNamesRaw.split('\n')
                                    .map(name => name.trim())
                                    .filter(name => name.length > 0);

    // Check if any player names were actually entered
    if (playersToAdd.length === 0) {
         console.warn("No player names entered in the 'add players' textarea.");
         showStatusMessage("Please enter at least one player name to add.", "warning");
         return; // Don't send request if list is empty
    }

    // Get the state of the 'ignoresPlayerLimit' checkbox for the added players
    const ignoresPlayerLimit = ignoreLimitCheckbox.checked;

    console.log("Players to add:", playersToAdd);
    console.log("Ignore player limit for added players:", ignoresPlayerLimit);

    // Construct the request body
    const requestBody = {
        players: playersToAdd,
        ignoresPlayerLimit: ignoresPlayerLimit // Backend needs to handle applying this to the new players
    };
    console.log("Constructed request body for adding players:", requestBody);

    // Call sendServerActionRequest targeting the ADD endpoint
    console.log("Calling sendServerActionRequest to add players to allowlist...");
    sendServerActionRequest(null, `/api/server/${serverName}/allowlist/add`, 'POST', requestBody, buttonElement)
        .then(apiResponseData => { // Check the actual response data object
            console.log("addAllowlistPlayers API call completed. Response data:", apiResponseData);
             // Check if the API call was successful (returned data object with status 'success')
            if (apiResponseData && apiResponseData.status === 'success') {
                console.log("Add players API call successful.");
                // Clear the textarea after successful submission
                console.log("Clearing 'add players' textarea.");
                textArea.value = '';
                // Optionally uncheck the 'ignore limit' box for the next add operation
                // ignoreLimitCheckbox.checked = false; // Uncomment if desired behavior

                // Refresh the display of the current allowlist
                console.log("Initiating fetch and update for allowlist display.");
                fetchAndUpdateAllowlistDisplay(serverName); // Call helper to update UI

            } else {
                 // API call failed or application status was not 'success'
                 // Error message already shown by sendServerActionRequest
                 console.log("Adding players failed or application status was not 'success'.");
            }
        });
    console.log("Returned from initiating sendServerActionRequest call for add allowlist players (async).");
}

/**
 * Helper function to fetch the current allowlist from the API and update the display section on the page.
 * Assumes a specific HTML structure for the display list (`#current-allowlist-display` UL/OL and potentially `#no-players-message` LI).
 * @param {string} serverName The name of the server whose allowlist needs to be displayed.
 */
async function fetchAndUpdateAllowlistDisplay(serverName) {
     console.log(`fetchAndUpdateAllowlistDisplay called for server: ${serverName}`);
     const displayList = document.getElementById('current-allowlist-display'); // The UL or OL element
     const noPlayersLi = document.getElementById('no-players-message'); // The LI shown when list is empty

     // Check if the main display list element exists
     if (!displayList) {
         console.error("Allowlist display element '#current-allowlist-display' not found. Cannot update UI.");
         return;
     }
     console.log("Found allowlist display element.");

     try {
        // Fetch the current allowlist data using a GET request to the allowlist API endpoint
        console.log(`Fetching current allowlist from /api/server/${serverName}/allowlist`);
        // Assuming the API endpoint `/api/server/<server_name>/allowlist` handles GET requests to return the list
        const response = await fetch(`/api/server/${serverName}/allowlist`); // GET request is default

        if (!response.ok) {
            // Handle HTTP errors during fetch
            console.error(`Failed to fetch allowlist. Status: ${response.status}, StatusText: ${response.statusText}`);
            throw new Error(`Failed to fetch allowlist (Status: ${response.status})`);
        }

        // Parse the JSON response
        console.log("Allowlist fetch successful, parsing JSON response.");
        const data = await response.json();
        console.log("Parsed allowlist data:", data);

        // Check if the response indicates success and contains the expected player data
        if (data.status === 'success' && Array.isArray(data.existing_players)) { // Check if existing_players is an array
            console.log(`Successfully fetched ${data.existing_players.length} players from allowlist.`);
            // Clear current list items, but preserve the 'no players' message element if it exists
            console.log("Clearing existing allowlist entries from display (excluding 'no players' message).");
            displayList.querySelectorAll('li:not(#no-players-message)').forEach(li => li.remove());

            if (data.existing_players.length > 0) {
                 // If players exist, hide or remove the 'no players' message
                 if (noPlayersLi) {
                     console.log("Hiding 'no players' message.");
                     noPlayersLi.style.display = 'none';
                 }
                 // Add new list items for each player
                 console.log("Adding fetched players to the display list.");
                 data.existing_players.forEach(player => {
                     const li = document.createElement('li');
                     // Display player name and whether they ignore the player limit
                     li.textContent = `${player.name} (Ignores Limit: ${player.ignoresPlayerLimit ? 'Yes' : 'No'})`; // Improved display
                     // Optionally add data attributes or classes if needed for styling/interaction
                     // li.dataset.xuid = player.xuid; // If XUID is available and needed
                     displayList.appendChild(li);
                 });
            } else {
                 // If no players exist, ensure the 'no players' message is visible
                 console.log("No players in fetched allowlist. Ensuring 'no players' message is visible.");
                 if (noPlayersLi) {
                     console.log("Showing existing 'no players' message.");
                     noPlayersLi.style.display = ''; // Make existing message visible
                 } else {
                     // If the 'no players' message element doesn't exist, create and add it
                     console.warn("Creating 'no players' message element as it was not found.");
                     const li = document.createElement('li');
                     li.id = 'no-players-message'; // Assign ID for future reference
                     li.textContent = 'No players currently in allowlist.';
                     displayList.appendChild(li);
                 }
            }
            console.log("Allowlist display updated successfully.");
        } else {
             // Handle cases where the API response format is unexpected or indicates failure
             console.error("Failed to get valid allowlist data from API response:", data.message || 'Unknown API error or invalid format.');
             showStatusMessage("Could not refresh the current allowlist display (invalid data).", "warning");
        }

     } catch (error) {
          // Handle network errors or errors during JSON parsing/processing
          console.error("Error during fetch or update of allowlist display:", error);
          showStatusMessage("Error refreshing the current allowlist display.", "error");
     }
}