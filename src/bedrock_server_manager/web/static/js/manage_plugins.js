// bedrock_server_manager/web/static/js/manage_plugins.js

document.addEventListener('DOMContentLoaded', () => {
    const functionName = 'PluginManagerUI';

    // --- DOM Elements ---
    const pluginList = document.getElementById('plugin-list');
    const pluginItemTemplate = document.getElementById('plugin-item-template');
    const noPluginsTemplate = document.getElementById('no-plugins-template');
    const loadErrorTemplate = document.getElementById('load-error-template');
    const pluginLoader = document.getElementById('plugin-loader');
    const reloadPluginsBtn = document.getElementById('reload-plugins-btn'); // Get the reload button

    if (!pluginList || !pluginItemTemplate || !noPluginsTemplate || !loadErrorTemplate || !pluginLoader || !reloadPluginsBtn) {
        console.error(`${functionName}: Critical template, container, or button element missing.`);
        if (pluginList) {
            pluginList.innerHTML = '<li class="list-item-error"><p>Page setup error. Required elements missing.</p></li>';
        }
        return;
    }

    // Attach event listener to the reload button
    reloadPluginsBtn.addEventListener('click', handleReloadClick);

    /**
     * Handles the click event for the Reload Plugins button.
     */
    async function handleReloadClick() {
        console.log(`${functionName}: Reloading plugins...`);
        reloadPluginsBtn.disabled = true;
        const originalButtonText = reloadPluginsBtn.innerHTML; // Store original content (including icon)
        reloadPluginsBtn.innerHTML = '<div class="spinner-small"></div> Reloading...'; // Show loading state

        // Assuming showStatusMessage is globally available from utils.js
        if (typeof showStatusMessage === 'function') {
            showStatusMessage('Sending reload request...', "success");
        }

        const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute('content') : null;

        if (!csrfToken) {
            if (typeof showStatusMessage === 'function') {
                showStatusMessage('CSRF token not found. Cannot reload plugins.', 'error');
            }
            reloadPluginsBtn.disabled = false;
            reloadPluginsBtn.innerHTML = originalButtonText;
            return;
        }

        try {
            const response = await fetch('/api/plugins/reload', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            });

            const result = await response.json();

            if (result.status === 'success') {
                if (typeof showStatusMessage === 'function') {
                    showStatusMessage(result.message || 'Plugins reloaded successfully.', 'success');
                }
                // Refresh the plugin list on the page to reflect any changes
                await fetchAndRenderPlugins();
            } else {
                if (typeof showStatusMessage === 'function') {
                    showStatusMessage(result.message || 'Failed to reload plugins.', 'error');
                }
            }
        } catch (error) {
            console.error(`${functionName}: Error reloading plugins:`, error);
            if (typeof showStatusMessage === 'function') {
                showStatusMessage(`Error during plugin reload: ${error.message}`, 'error');
            }
        } finally {
            reloadPluginsBtn.disabled = false;
            reloadPluginsBtn.innerHTML = originalButtonText; // Restore original button content
        }
    }


    /**
     * Fetches plugin statuses from the API and renders them.
     */
    async function fetchAndRenderPlugins() {
        pluginLoader.style.display = 'flex';
        // Clear only plugin items, empty messages, or error messages, not the loader itself
        pluginList.querySelectorAll('li:not(#plugin-loader)').forEach(el => el.remove());

        try {
            const response = await fetch('/api/plugins');
            const data = await response.json();

            pluginLoader.style.display = 'none'; // Hide loader after fetch

            if (!response.ok || data.status !== 'success') {
                throw new Error(data.message || `Failed to load plugins (HTTP ${response.status})`);
            }

            const plugins = data.plugins;
            if (plugins && Object.keys(plugins).length > 0) {
                const sortedPluginNames = Object.keys(plugins).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));

                sortedPluginNames.forEach(pluginName => {
                    const pluginData = plugins[pluginName];
                    const isEnabled = pluginData.enabled;
                    const version = pluginData.version || 'N/A';

                    const itemClone = pluginItemTemplate.content.cloneNode(true);
                    const nameSpan = itemClone.querySelector('.plugin-name');
                    const versionSpan = itemClone.querySelector('.plugin-version');
                    const toggleSwitch = itemClone.querySelector('.plugin-toggle-switch');

                    nameSpan.textContent = pluginName;
                    versionSpan.textContent = `v${version}`;
                    toggleSwitch.checked = isEnabled;
                    toggleSwitch.dataset.pluginName = pluginName;

                    toggleSwitch.addEventListener('change', handlePluginToggle);
                    pluginList.appendChild(itemClone);
                });
            } else {
                pluginList.appendChild(noPluginsTemplate.content.cloneNode(true));
            }
        } catch (error) {
            console.error(`${functionName}: Error fetching or rendering plugins:`, error);
            pluginLoader.style.display = 'none'; // Ensure loader is hidden on error
            // Check if error template exists before appending
            if (loadErrorTemplate) {
                pluginList.appendChild(loadErrorTemplate.content.cloneNode(true));
            }
            if (typeof showStatusMessage === 'function') {
                showStatusMessage(`Error fetching plugin data: ${error.message}`, 'error');
            }
        }
    }

    /**
     * Handles the change event of a plugin toggle switch.
     */
    async function handlePluginToggle(event) {
        const toggleSwitch = event.target;
        const pluginName = toggleSwitch.dataset.pluginName;
        const isEnabled = toggleSwitch.checked;

        // Temporarily disable the switch to prevent rapid toggling
        toggleSwitch.disabled = true;

        const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute('content') : null;

        if (!csrfToken) {
            if (typeof showStatusMessage === 'function') {
                showStatusMessage('CSRF token not found. Cannot update plugin status.', 'error');
            }
            toggleSwitch.checked = !isEnabled; // Revert UI change
            toggleSwitch.disabled = false;
            return;
        }

        try {
            const response = await fetch(`/api/plugins/${pluginName}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ enabled: isEnabled })
            });

            const result = await response.json();

            if (result.status === 'success') {
                if (typeof showStatusMessage === 'function') {
                    showStatusMessage(result.message || `Plugin '${pluginName}' status updated. Reload plugins to apply changes.`, 'success');
                }
            } else {
                if (typeof showStatusMessage === 'function') {
                    showStatusMessage(result.message || `Failed to update plugin '${pluginName}'.`, 'error');
                }
                toggleSwitch.checked = !isEnabled; // Revert UI change on error
            }
        } catch (error) {
            console.error(`${functionName}: Error updating plugin '${pluginName}':`, error);
            if (typeof showStatusMessage === 'function') {
                showStatusMessage(`Error updating plugin '${pluginName}': ${error.message}`, 'error');
            }
            toggleSwitch.checked = !isEnabled; // Revert UI change on error
        } finally {
            toggleSwitch.disabled = false; // Re-enable the switch
        }
    }

    // --- Initial Load ---
    fetchAndRenderPlugins();

    console.log(`${functionName}: Plugin management page initialization complete.`);
});