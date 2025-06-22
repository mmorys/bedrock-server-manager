// bedrock_server_manager/web/static/js/manage_plugins.js
/**
 * @fileoverview JavaScript for the Plugin Management page.
 * Handles fetching plugin statuses, rendering them with toggle switches,
 * and sending requests to enable/disable plugins.
 */

document.addEventListener('DOMContentLoaded', () => {
    const functionName = 'PluginManagerUI';
    console.log(`${functionName}: Initializing plugin management page.`);

    // --- DOM Elements ---
    const pluginList = document.getElementById('plugin-list'); // Target the <ul> directly
    const pluginItemTemplate = document.getElementById('plugin-item-template');
    const noPluginsTemplate = document.getElementById('no-plugins-template');
    const loadErrorTemplate = document.getElementById('load-error-template');
    const pluginLoader = document.getElementById('plugin-loader');

    if (!pluginList || !pluginItemTemplate || !noPluginsTemplate || !loadErrorTemplate || !pluginLoader) {
        console.error(`${functionName}: Critical template or container element missing. UI cannot be rendered.`);
        if (pluginList) {
            pluginList.innerHTML = '<li class="list-item-error"><p>Page setup error. Required elements missing.</p></li>';
        }
        return;
    }

    /**
     * Fetches plugin statuses from the API and renders them.
     */
    async function fetchAndRenderPlugins() {
        console.log(`${functionName}: Fetching plugin statuses...`);
        pluginLoader.style.display = 'flex'; // Ensure loader is visible
        // Clear any previous items except the loader
        pluginList.querySelectorAll('.plugin-item, .list-item-empty, .list-item-error').forEach(el => el.remove());

        try {
            const response = await fetch('/api/plugins');
            const data = await response.json();

            pluginLoader.style.display = 'none'; // Hide loader

            if (!response.ok || data.status !== 'success') {
                const errorMsg = data.message || `Failed to load plugins (HTTP ${response.status})`;
                console.error(`${functionName}: ${errorMsg}`, data);
                pluginList.appendChild(loadErrorTemplate.content.cloneNode(true));
                showStatusMessage(errorMsg, 'error');
                return;
            }

            const plugins = data.plugins;
            if (plugins && Object.keys(plugins).length > 0) {
                const sortedPluginNames = Object.keys(plugins).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));

                sortedPluginNames.forEach(pluginName => {
                    const pluginData = plugins[pluginName];
                    const isEnabled = typeof pluginData === 'boolean' ? pluginData : pluginData.enabled;
                    const description = typeof pluginData === 'boolean' ? 'No description available.' : pluginData.description;

                    const itemClone = pluginItemTemplate.content.cloneNode(true);

                    const nameSpan = itemClone.querySelector('.plugin-name');
                    const descriptionP = itemClone.querySelector('.plugin-description');
                    const toggleSwitch = itemClone.querySelector('.plugin-toggle-switch');

                    nameSpan.textContent = pluginName;
                    descriptionP.textContent = description;
                    toggleSwitch.checked = isEnabled;
                    toggleSwitch.dataset.pluginName = pluginName;

                    // The unique ID and htmlFor are NOT needed because the input is inside the label.
                    // The browser handles the connection automatically.

                    toggleSwitch.addEventListener('change', handlePluginToggle);
                    pluginList.appendChild(itemClone);
                });
            } else {
                pluginList.appendChild(noPluginsTemplate.content.cloneNode(true));
                console.log(`${functionName}: No plugins found or returned by API.`);
            }
        } catch (error) {
            console.error(`${functionName}: Error fetching or rendering plugins:`, error);
            pluginLoader.style.display = 'none'; // Hide loader
            pluginList.appendChild(loadErrorTemplate.content.cloneNode(true));
            showStatusMessage(`Error fetching plugin data: ${error.message}`, 'error');
        }
    }

    /**
     * Handles the change event of a plugin toggle switch.
     * @param {Event} event - The change event from the toggle switch.
     */
    async function handlePluginToggle(event) {
        const toggleSwitch = event.target;
        const pluginName = toggleSwitch.dataset.pluginName;
        const isEnabled = toggleSwitch.checked;

        console.log(`${functionName}: Toggling plugin '${pluginName}' to ${isEnabled ? 'Enabled' : 'Disabled'}.`);
        toggleSwitch.disabled = true;

        const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute('content') : null;

        if (!csrfToken) {
            showStatusMessage('CSRF token not found. Cannot update plugin status.', 'error');
            toggleSwitch.checked = !isEnabled;
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
                showStatusMessage(result.message || `Plugin '${pluginName}' status updated.`, 'success');
            } else {
                showStatusMessage(result.message || `Failed to update plugin '${pluginName}'.`, 'error');
                toggleSwitch.checked = !isEnabled;
            }
        } catch (error) {
            console.error(`${functionName}: Error updating plugin '${pluginName}':`, error);
            showStatusMessage(`Error updating plugin '${pluginName}': ${error.message}`, 'error');
            toggleSwitch.checked = !isEnabled;
        } finally {
            toggleSwitch.disabled = false;
        }
    }

    // --- Initial Load ---
    fetchAndRenderPlugins();

    console.log(`${functionName}: Plugin management page initialization complete.`);
});