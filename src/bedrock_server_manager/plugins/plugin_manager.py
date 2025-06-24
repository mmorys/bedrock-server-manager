# bedrock_server_manager/plugins/plugin_manager.py
"""Manages plugin discovery, loading, configuration, lifecycle, and event dispatch.

This module is central to the plugin architecture of the Bedrock Server Manager.
The `PluginManager` class handles all aspects of plugin interaction, including:
  - Locating plugin files in designated directories.
  - Reading and writing plugin configurations (e.g., enabled status, metadata)
    from/to a JSON file (`plugins.json`).
  - Validating plugins (e.g., ensuring they subclass `PluginBase` and have a
    `version` attribute).
  - Dynamically loading valid and enabled plugins.
  - Managing the lifecycle of plugins (e.g., calling `on_load`, `on_unload`).
  - Dispatching application-wide events to all loaded plugins.
  - Facilitating custom inter-plugin event communication.
  - Providing a mechanism to reload all plugins.
"""
import os
import importlib.util
import inspect
import logging
import threading
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Type, Callable, Tuple

from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.config.const import GUARD_VARIABLE
from .plugin_base import PluginBase
from .api_bridge import PluginAPI

# Standard logger for this module.
logger = logging.getLogger(__name__)

# Thread-local storage for tracking the call stack of standard application events.
# This is used to prevent re-entrancy issues (infinite loops) if an event handler
# triggers an action that would cause the same event to be dispatched again
# within the same thread of execution.
_event_context = threading.local()

# Thread-local storage for tracking the call stack of custom inter-plugin events.
# Similar to `_event_context`, but specifically for events sent via `send_event()`
# and handled by `trigger_custom_plugin_event()`.
_custom_event_context = threading.local()

# A list of plugin names (module names without .py) that are enabled by default
# when they are first discovered. Users can subsequently disable them.
DEFAULT_ENABLED_PLUGINS = [
    "auto_reload_plugin",
    "autoupdate_plugin",
    "server_lifecycle_notifications_plugin",
    "world_operation_notifications_plugin",
]


class PluginManager:
    """Manages the discovery, loading, configuration, and lifecycle of all plugins.

    This class is the core of the plugin system. It scans for plugins,
    manages their configuration in `plugins.json`, loads enabled plugins,
    and dispatches various events to them.
    """

    def __init__(self):
        """Initializes the PluginManager.

        Sets up plugin directories, configuration paths, and ensures directories exist.
        """
        self.settings = settings
        user_plugin_dir = Path(self.settings.get("PLUGIN_DIR"))
        default_plugin_dir = Path(__file__).parent / "default"

        # List of directories to scan for plugins.
        # User plugins can override default plugins if `user_plugin_dir` appears first
        # and they share the same plugin name. The current order is user then default,
        # but `_synchronize_config_with_disk` prioritizes the first found path.
        # For true override, user_plugin_dir should be checked first by _find_plugin_path
        # or the logic in _synchronize_config_with_disk adjusted.
        # Current logic: all_potential_plugin_files uses dict insertion order, which
        # depends on glob order and then dict key uniqueness. If user dir is scanned
        # first, its plugins are added. If default dir is scanned next, same-named
        # plugins won't overwrite. This is effectively user > default.
        self.plugin_dirs: List[Path] = [user_plugin_dir, default_plugin_dir]
        logger.debug(f"Plugin directories configured: {self.plugin_dirs}")

        self.config_path: Path = Path(self.settings.config_dir) / "plugins.json"
        logger.debug(f"Plugin configuration file path: {self.config_path}")

        # In-memory store for plugin configurations (name -> {enabled, description, version}).
        self.plugin_config: Dict[str, Dict[str, Any]] = {}
        # List of currently loaded and active plugin instances.
        self.plugins: List[PluginBase] = []
        # Registry for custom event listeners (event_name -> list of (plugin_name, callback)).
        self.custom_event_listeners: Dict[str, List[Tuple[str, Callable]]] = {}

        # Ensure all configured plugin directories exist.
        for directory in self.plugin_dirs:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured plugin directory exists: {directory}")
            except OSError as e:
                logger.error(
                    f"Failed to create plugin directory {directory}: {e}", exc_info=True
                )
                # Potentially raise an error or handle this more gracefully if essential.

        logger.info("PluginManager initialized.")

    def _load_config(self) -> Dict[str, Dict[str, Any]]:
        """Loads plugin configurations from the `plugins.json` file.

        If the file doesn't exist or is malformed, it returns an empty dictionary,
        prompting a rebuild of the configuration.

        Returns:
            Dict[str, Dict[str, Any]]: The loaded plugin configuration data.
            Returns an empty dict if loading fails or file not found.
        """
        if not self.config_path.exists():
            logger.debug(
                f"Plugin configuration file '{self.config_path}' not found. Returning empty config."
            )
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                logger.debug(
                    f"Successfully loaded plugin configuration from '{self.config_path}'."
                )
                return config_data
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(
                f"Error decoding plugin configuration file '{self.config_path}' or its format is outdated. "
                f"Attempting to rebuild configuration. Error: {e}",
                exc_info=True,
            )
            return (
                {}
            )  # Return empty config to force rebuild by _synchronize_config_with_disk
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while loading plugin configuration from '{self.config_path}': {e}",
                exc_info=True,
            )
            return {}

    def _save_config(self):
        """Saves the current in-memory plugin configuration to `plugins.json`.

        The configuration is saved in a human-readable JSON format.
        """
        logger.debug(
            f"Attempting to save plugin configuration to '{self.config_path}'."
        )
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.plugin_config, f, indent=4, sort_keys=True)
            logger.info(
                f"Plugin configuration successfully saved to '{self.config_path}'."
            )
        except Exception as e:
            logger.error(
                f"Failed to save plugin configuration to '{self.config_path}': {e}",
                exc_info=True,
            )

    def _find_plugin_path(self, plugin_name: str) -> Optional[Path]:
        """Searches all configured plugin directories for a specific plugin file.

        It looks for a Python file named `{plugin_name}.py`. The search order
        is determined by the order of directories in `self.plugin_dirs`.
        The first match found is returned.

        Args:
            plugin_name (str): The name of the plugin (module name without .py).

        Returns:
            Optional[Path]: The `Path` object to the plugin file if found,
            otherwise `None`.
        """
        logger.debug(
            f"Searching for plugin file for '{plugin_name}' in {self.plugin_dirs}."
        )
        for directory in self.plugin_dirs:
            path = directory / f"{plugin_name}.py"
            if path.exists():
                logger.debug(f"Found plugin file for '{plugin_name}' at: {path}")
                return path
        logger.debug(
            f"Plugin file for '{plugin_name}' not found in any configured directory."
        )
        return None

    def _get_plugin_class_from_path(self, path: Path) -> Optional[Type[PluginBase]]:
        """Dynamically loads a Python module from the given path and finds the `PluginBase` subclass.

        It imports the module specified by `path`, then inspects its members to
        find a class that is a subclass of `PluginBase` but is not `PluginBase`
        itself.

        Args:
            path (Path): The `Path` object pointing to the plugin's Python file.

        Returns:
            Optional[Type[PluginBase]]: The `PluginBase` subclass found in the
            module, or `None` if no such class is found or if an error occurs
            during loading/inspection.
        """
        plugin_name = path.stem
        logger.debug(f"Attempting to load module '{plugin_name}' from path: {path}")
        try:
            # Create a module spec from the file location.
            spec = importlib.util.spec_from_file_location(plugin_name, path)
            if spec is None or spec.loader is None:
                logger.error(
                    f"Could not create module spec for plugin '{plugin_name}' at {path}."
                )
                raise ImportError(f"Could not create module spec for {plugin_name}")

            # Create a new module based on the spec.
            module = importlib.util.module_from_spec(spec)
            # Execute the module in its own namespace.
            spec.loader.exec_module(module)
            logger.debug(f"Successfully executed module '{plugin_name}' from {path}.")

            # Inspect the module for PluginBase subclasses.
            for member_name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)  # Is it a class?
                    and issubclass(obj, PluginBase)  # Is it a subclass of PluginBase?
                    and obj is not PluginBase  # Is it not PluginBase itself?
                ):
                    logger.debug(
                        f"Found PluginBase subclass '{obj.__name__}' in module '{plugin_name}'."
                    )
                    return obj
            logger.warning(
                f"No PluginBase subclass found in module '{plugin_name}' at {path}."
            )
        except Exception as e:
            logger.error(
                f"Failed to load or inspect plugin file at '{path}' for plugin class: {e}",
                exc_info=True,
            )
        return None

    def _synchronize_config_with_disk(self):
        """Scans plugin directories, validates plugins, extracts metadata, and updates `plugins.json`.

        This crucial method ensures the `plugins.json` configuration file is
        consistent with the actual plugin files found on disk. It performs:
        1.  Loading of the existing `plugins.json`.
        2.  Scanning all `self.plugin_dirs` for potential plugin files (`*.py`
            not starting with `_`).
        3.  For each potential plugin:
            a.  Attempts to load its class using `_get_plugin_class_from_path`.
            b.  Validates the plugin class:
                i.  Must be a `PluginBase` subclass.
                ii. Must have a non-empty `version` class attribute.
            c.  If valid, extracts metadata (description from docstring, version).
            d.  Updates `self.plugin_config`:
                i.  Adds new valid plugins (defaulting to enabled if in
                    `DEFAULT_ENABLED_PLUGINS`).
                ii. Updates metadata (description, version) for existing plugins if changed.
                iii.Migrates old boolean config entries to the new dictionary format.
                iv. Ensures essential keys like 'enabled', 'description', 'version' exist.
        4.  Removes entries from `self.plugin_config` for plugins that are no
            longer found on disk or have become invalid (e.g., missing version).
        5.  If any changes were made to `self.plugin_config`, it saves the updated
            configuration back to `plugins.json` using `_save_config()`.

        This method is vital for maintaining an accurate and up-to-date registry
        of discoverable plugins and their states.
        """
        logger.info("Starting synchronization of plugin configuration with disk.")
        self.plugin_config = (
            self._load_config()
        )  # Load current config or empty if issues
        config_changed = False  # Flag to track if plugins.json needs to be re-saved

        # Keep track of valid plugins found on disk by their names (module names)
        # This helps in identifying and removing stale entries from the config later.
        valid_plugins_found_on_disk = set()

        # Scan all configured plugin directories to find all potential plugin files.
        # A dictionary is used to ensure that if a plugin name exists in multiple
        # directories, only the first one encountered (based on self.plugin_dirs order) is considered.
        all_potential_plugin_files: Dict[str, Path] = {}
        logger.debug(f"Scanning for plugin files in directories: {self.plugin_dirs}")
        for directory in self.plugin_dirs:
            if not directory.exists():
                logger.warning(
                    f"Plugin directory '{directory}' does not exist. Skipping scan for this directory."
                )
                continue
            logger.debug(f"Scanning directory: {directory}")
            for path in directory.glob("*.py"):
                # Ignore files starting with '_' (e.g., __init__.py or internal modules)
                if not path.name.startswith("_"):
                    plugin_name_stem = path.stem
                    # If this plugin name hasn't been added yet, add it.
                    # This respects the order of plugin_dirs for overriding.
                    if plugin_name_stem not in all_potential_plugin_files:
                        all_potential_plugin_files[plugin_name_stem] = path
                        logger.debug(
                            f"Discovered potential plugin file: '{path}' for plugin '{plugin_name_stem}'."
                        )
        logger.info(
            f"Found {len(all_potential_plugin_files)} potential plugin files across all directories."
        )

        # Process each potential plugin file found.
        for plugin_name, path in all_potential_plugin_files.items():
            logger.debug(
                f"Processing plugin file: '{path}' for plugin '{plugin_name}'."
            )
            plugin_class = self._get_plugin_class_from_path(path)

            if not plugin_class:
                logger.warning(
                    f"Could not find a valid PluginBase subclass in '{path}' for plugin '{plugin_name}'. "
                    "This file will be ignored."
                )
                # If this invalid plugin was previously in the config, remove it.
                if plugin_name in self.plugin_config:
                    self.plugin_config.pop(plugin_name)
                    config_changed = True
                    logger.info(
                        f"Removed invalid plugin entry '{plugin_name}' from configuration because its class "
                        "could not be loaded or is not a valid PluginBase subclass."
                    )
                continue  # Skip to the next plugin file.

            # --- Strict Version Check ---
            # Plugins *must* have a 'version' class attribute.
            version_attr = getattr(plugin_class, "version", None)
            if (
                not version_attr or not str(version_attr).strip()
            ):  # Check if version is None, empty, or just whitespace
                logger.warning(
                    f"Plugin class '{plugin_class.__name__}' in file '{path}' (for plugin '{plugin_name}') "
                    "is missing a valid 'version' class attribute or the version is empty. "
                    "This plugin will be ignored and cannot be loaded."
                )
                # If this plugin (now invalid due to missing version) was in config, remove it.
                if plugin_name in self.plugin_config:
                    self.plugin_config.pop(plugin_name)
                    config_changed = True
                    logger.info(
                        f"Removed plugin entry '{plugin_name}' from configuration due to missing or invalid 'version' attribute."
                    )
                continue  # Skip this plugin entirely.

            # If we reach here, the plugin class is valid and has a version.
            valid_plugins_found_on_disk.add(plugin_name)
            version = str(version_attr).strip()  # Ensure version is a clean string.

            # Extract description from the plugin class's docstring.
            description = inspect.getdoc(plugin_class) or "No description available."
            description = " ".join(description.strip().split())  # Normalize whitespace.

            current_config_entry = self.plugin_config.get(plugin_name)
            needs_update_in_config = (
                False  # Flag if this specific plugin's entry needs updating.
            )

            # Case 1: Plugin is new to the config, or config entry is in an old format (e.g., bool)
            # or is a dict but fundamentally broken (e.g. missing essential keys after a manual edit).
            if not isinstance(current_config_entry, dict):
                is_enabled_by_default = plugin_name in DEFAULT_ENABLED_PLUGINS
                # If old format was a boolean, respect that enabled/disabled state.
                # Otherwise, use the default enablement status.
                is_enabled = (
                    bool(current_config_entry)
                    if isinstance(current_config_entry, bool)
                    else is_enabled_by_default
                )

                self.plugin_config[plugin_name] = {
                    "enabled": is_enabled,
                    "description": description,
                    "version": version,
                }
                config_changed = True
                needs_update_in_config = (
                    True  # Indicates an update or creation happened.
                )
                if current_config_entry is None:
                    logger.info(
                        f"Discovered new valid plugin '{plugin_name}' v{version}. Added to configuration "
                        f"with enabled state: {is_enabled}."
                    )
                else:
                    logger.info(
                        f"Upgraded configuration format for plugin '{plugin_name}' v{version}. "
                        f"Set enabled state to: {is_enabled}."
                    )
            # Case 2: Plugin exists in config as a dictionary. Check for metadata updates or missing keys.
            else:
                updated_entry = current_config_entry.copy()  # Work on a copy.

                # Ensure 'enabled' key exists; if not, set to default.
                if "enabled" not in updated_entry:
                    updated_entry["enabled"] = plugin_name in DEFAULT_ENABLED_PLUGINS
                    needs_update_in_config = True
                    logger.debug(
                        f"Added missing 'enabled' key for plugin '{plugin_name}' in config."
                    )

                # Update description if it has changed.
                if updated_entry.get("description") != description:
                    updated_entry["description"] = description
                    needs_update_in_config = True
                    logger.debug(
                        f"Updated 'description' for plugin '{plugin_name}' in config."
                    )

                # Update version if it has changed.
                if updated_entry.get("version") != version:
                    updated_entry["version"] = version
                    needs_update_in_config = True
                    logger.debug(
                        f"Updated 'version' for plugin '{plugin_name}' to v{version} in config."
                    )

                if needs_update_in_config:
                    self.plugin_config[plugin_name] = updated_entry
                    config_changed = True
                    logger.info(
                        f"Updated metadata/config entry for plugin '{plugin_name}' (now v{version})."
                    )

        # Clean up: Remove entries from config for plugins that no longer exist on disk
        # or were invalidated during the scan (e.g., due to missing version).
        plugins_in_config_to_remove = []
        for plugin_name_in_config in self.plugin_config.keys():
            if plugin_name_in_config not in valid_plugins_found_on_disk:
                plugins_in_config_to_remove.append(plugin_name_in_config)

        if plugins_in_config_to_remove:
            for plugin_name_to_remove in plugins_in_config_to_remove:
                del self.plugin_config[plugin_name_to_remove]
                config_changed = True
                logger.info(
                    f"Removed stale or invalidated plugin entry '{plugin_name_to_remove}' from configuration "
                    "as it's no longer found on disk or is invalid (e.g., missing version)."
                )

        # If any changes were made to the configuration, save it back to plugins.json.
        if config_changed:
            logger.info(
                "Plugin configuration has changed during synchronization. Saving updated configuration."
            )
            self._save_config()
        else:
            logger.debug(
                "Plugin configuration synchronization complete. No changes detected."
            )

    def load_plugins(self):
        """Discovers, validates, and loads all enabled plugins.

        This method orchestrates the entire plugin loading process:
        1.  Calls `_synchronize_config_with_disk()` to ensure the plugin
            configuration (`self.plugin_config`) is up-to-date with files
            on disk and that all entries are valid.
        2.  Clears any previously loaded plugin instances from `self.plugins`.
            This is important for supporting the `reload()` functionality.
        3.  Iterates through the synchronized `self.plugin_config`:
            a.  If a plugin is marked as `enabled` and has a valid `version`:
                i.  Finds the plugin's file path using `_find_plugin_path()`.
                ii. Loads the plugin class from the file using `_get_plugin_class_from_path()`.
                iii.If successful, instantiates the plugin class, providing it with
                    its name, a `PluginAPI` instance, and a dedicated logger.
                iv. Appends the new plugin instance to `self.plugins`.
                v.  Dispatches the `on_load` event to the newly loaded plugin instance.
        """
        logger.info("Starting plugin loading process...")
        self._synchronize_config_with_disk()  # Ensure config is current and valid.

        logger.info(
            f"Attempting to load plugins from configured directories: {[str(d) for d in self.plugin_dirs]}"
        )

        # Clear any existing loaded plugin instances. This is crucial for reload functionality.
        if self.plugins:
            logger.info(
                f"Clearing {len(self.plugins)} previously loaded plugin instances before attempting new load."
            )
            # Note: The on_unload for these plugins should be handled by the reload() method
            # if this load_plugins call is part of a reload.
            # If load_plugins is called directly, on_unload is not called here.
            self.plugins.clear()

        loaded_plugin_count = 0
        for plugin_name, config_data in self.plugin_config.items():
            # Due to _synchronize_config_with_disk, config_data should always be a dictionary
            # and contain 'enabled' and 'version' keys if the plugin is valid.
            if not isinstance(config_data, dict):
                logger.error(
                    f"Plugin '{plugin_name}' has malformed config data (not a dict). Skipping. Data: {config_data}"
                )
                continue

            if not config_data.get("enabled"):
                logger.debug(
                    f"Plugin '{plugin_name}' is disabled in configuration. Skipping load."
                )
                continue

            plugin_version = config_data.get("version")
            # This version check is mostly a safeguard; primary validation occurs in _synchronize_config_with_disk.
            if (
                not plugin_version or plugin_version == "N/A"
            ):  # "N/A" might be a remnant.
                logger.warning(
                    f"Plugin '{plugin_name}' is marked enabled but has a missing or invalid version ('{plugin_version}') "
                    "in its configuration. This might indicate an issue with synchronization. Skipping load."
                )
                continue

            logger.debug(
                f"Attempting to load enabled plugin: '{plugin_name}' v{plugin_version}."
            )
            path = self._find_plugin_path(plugin_name)
            if not path:
                # This should ideally not happen if _synchronize_config_with_disk worked correctly,
                # as it would have removed plugins from config if their files are missing.
                logger.warning(
                    f"Enabled plugin '{plugin_name}' v{plugin_version} path not found on disk, though it exists in config. "
                    "Skipping load. Consider re-synchronizing plugins."
                )
                continue

            plugin_class = self._get_plugin_class_from_path(path)
            if plugin_class:
                try:
                    # Create a dedicated logger for this plugin instance.
                    # Logs from this logger will be prefixed e.g., "plugin.my_plugin_name".
                    plugin_logger = logging.getLogger(f"plugin.{plugin_name}")
                    api_instance = PluginAPI(
                        plugin_name=plugin_name, plugin_manager=self
                    )
                    logger.debug(
                        f"Instantiating plugin class '{plugin_class.__name__}' for '{plugin_name}'."
                    )
                    instance = plugin_class(plugin_name, api_instance, plugin_logger)
                    self.plugins.append(instance)
                    loaded_plugin_count += 1
                    # Log with the version from config_data, as it's the validated source of truth for metadata.
                    logger.info(
                        f"Successfully loaded and initialized plugin: '{plugin_name}' v{plugin_version}."
                    )

                    # Dispatch the 'on_load' event to the newly loaded plugin.
                    logger.debug(
                        f"Dispatching 'on_load' event to plugin '{plugin_name}'."
                    )
                    self.dispatch_event(instance, "on_load")

                except Exception as e:
                    logger.error(
                        f"Failed to instantiate or initialize plugin '{plugin_name}' from class '{plugin_class.__name__}': {e}",
                        exc_info=True,
                    )
            else:
                # This case should ideally be caught by _synchronize_config_with_disk earlier.
                logger.error(
                    f"Could not retrieve class for plugin '{plugin_name}' from path '{path}' during load phase, "
                    "despite it being enabled in config. Skipping."
                )
        logger.info(
            f"Plugin loading process complete. Loaded {loaded_plugin_count} plugins."
        )

    def register_plugin_event_listener(
        self, event_name: str, callback: Callable, listening_plugin_name: str
    ):
        """Registers a callback function from a plugin to listen for a custom event.

        Args:
            event_name (str): The name of the custom event to listen for.
            callback (Callable): The function/method in the listening plugin
                that will be called when the event is triggered.
            listening_plugin_name (str): The name of the plugin registering
                the listener. Used for logging and context.
        """
        if not callable(callback):
            logger.error(
                f"Plugin '{listening_plugin_name}' attempted to register a non-callable object "
                f"as a listener for custom event '{event_name}'. Registration failed."
            )
            return

        # Ensure the event name exists as a key in the listeners dictionary.
        self.custom_event_listeners.setdefault(event_name, [])
        # Append a tuple of (plugin_name, callback) to the list of listeners for this event.
        self.custom_event_listeners[event_name].append(
            (listening_plugin_name, callback)
        )
        logger.info(
            f"Plugin '{listening_plugin_name}' successfully registered a listener "
            f"for custom event '{event_name}' with callback '{callback.__name__}'."
        )
        logger.debug(
            f"Current listeners for '{event_name}': {len(self.custom_event_listeners[event_name])}"
        )

    def trigger_custom_plugin_event(
        self, event_name: str, triggering_plugin_name: str, *args, **kwargs
    ):
        """Triggers a custom event, invoking all registered listener callbacks.

        This method manages the dispatch of custom events sent by plugins.
        It includes re-entrancy protection using `_custom_event_context` to
        prevent infinite loops if a listener, in turn, triggers the same event.

        Args:
            event_name (str): The name of the custom event being triggered.
            triggering_plugin_name (str): The name of the plugin that initiated
                this event. This is passed to listeners as `_triggering_plugin`.
            *args: Positional arguments to pass to the listener callbacks.
            **kwargs: Keyword arguments to pass to the listener callbacks.
        """
        # Initialize the re-entrancy guard stack if it doesn't exist for this thread.
        if not hasattr(_custom_event_context, "stack"):
            _custom_event_context.stack = []

        # Re-entrancy check: If this event is already in the current call stack, skip.
        if event_name in _custom_event_context.stack:
            logger.debug(
                f"Skipping recursive trigger of custom event '{event_name}' by plugin "
                f"'{triggering_plugin_name}'. Event is already in the processing stack: {_custom_event_context.stack}"
            )
            return

        # Add the current event to the stack to mark it as being processed.
        _custom_event_context.stack.append(event_name)
        logger.info(
            f"Plugin '{triggering_plugin_name}' is triggering custom event '{event_name}'. "
            f"Args: {args}, Kwargs: {kwargs}. Current stack: {_custom_event_context.stack}"
        )

        try:
            listeners_for_event = self.custom_event_listeners.get(event_name, [])
            logger.debug(
                f"Found {len(listeners_for_event)} registered listeners for custom event '{event_name}'."
            )

            for listener_plugin_name, callback in listeners_for_event:
                logger.debug(
                    f"Dispatching custom event '{event_name}' (triggered by '{triggering_plugin_name}') "
                    f"to listener in plugin '{listener_plugin_name}' (callback: '{callback.__name__}')."
                )
                try:
                    # Pass the triggering plugin's name as a special kwarg.
                    callback(*args, **kwargs, _triggering_plugin=triggering_plugin_name)
                except Exception as e:
                    logger.error(
                        f"Error encountered in plugin '{listener_plugin_name}' while handling custom event "
                        f"'{event_name}' (triggered by '{triggering_plugin_name}'). Callback: '{callback.__name__}'. Error: {e}",
                        exc_info=True,
                    )
        finally:
            # Remove the event from the stack once all its listeners have been processed.
            _custom_event_context.stack.pop()
            logger.debug(
                f"Finished processing custom event '{event_name}'. "
                f"Stack after pop: {_custom_event_context.stack}"
            )

    def reload(self):
        """Unloads all currently active plugins and then reloads all plugins.

        This method provides a way to refresh the plugin system without restarting
        the entire application. It involves:
        1.  Dispatching the `on_unload` event to all currently loaded plugins.
        2.  Clearing all registered custom event listeners (as the plugins that
            registered them are being unloaded).
        3.  Calling `load_plugins()` to re-run the discovery, synchronization,
            and loading process for all plugins based on the current disk state
            and configuration.
        """
        logger.info("--- Starting Full Plugin Reload Process ---")

        # 1. Unload existing plugins safely by calling their on_unload method.
        if self.plugins:
            logger.info(f"Unloading {len(self.plugins)} currently active plugins...")
            # Iterate over a copy of the list because plugins might modify it indirectly,
            # though `dispatch_event` doesn't typically do that.
            for plugin_instance in list(self.plugins):
                logger.debug(
                    f"Dispatching 'on_unload' event to plugin '{plugin_instance.name}'."
                )
                self.dispatch_event(plugin_instance, "on_unload")
            logger.info(
                f"Finished dispatching 'on_unload' to {len(self.plugins)} plugins."
            )
        else:
            logger.info("No plugins were active to unload.")

        # self.plugins list will be cleared by load_plugins() when it's called next.
        # No need to clear it explicitly here if load_plugins() handles it.

        # 2. Unregister all custom event listeners.
        # Since plugins are being unloaded, their listeners are no longer valid.
        if self.custom_event_listeners:
            logger.info(
                f"Clearing {sum(len(v) for v in self.custom_event_listeners.values())} custom plugin event listeners from {len(self.custom_event_listeners)} event types."
            )
            self.custom_event_listeners.clear()
        else:
            logger.info("No custom plugin event listeners to clear.")

        # 3. Re-run the loading process.
        logger.info(
            "Re-running plugin discovery, synchronization, and loading process..."
        )
        self.load_plugins()  # This will call _synchronize_config_with_disk and load plugins.

        logger.info("--- Plugin Reload Process Complete ---")

    def dispatch_event(self, target_plugin: PluginBase, event: str, *args, **kwargs):
        """Dispatches a single standard application event to a specific plugin instance.

        This method attempts to call the method corresponding to `event` on the
        `target_plugin` instance, passing `*args` and `**kwargs`.

        Args:
            target_plugin (PluginBase): The plugin instance to which the event
                should be dispatched.
            event (str): The name of the event method to call on the plugin
                (e.g., "on_load", "before_server_start").
            *args: Positional arguments to pass to the event handler method.
            **kwargs: Keyword arguments to pass to the event handler method.
        """
        if hasattr(target_plugin, event):
            handler_method = getattr(target_plugin, event)
            logger.debug(
                f"Dispatching standard event '{event}' to plugin '{target_plugin.name}' "
                f"(handler: '{handler_method.__name__}'). Args: {args}, Kwargs: {kwargs}"
            )
            try:
                handler_method(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error encountered in plugin '{target_plugin.name}' during event handler "
                    f"'{event}': {e}",
                    exc_info=True,
                )
        else:
            logger.debug(
                f"Plugin '{target_plugin.name}' does not have a handler method for event '{event}'. Skipping."
            )

    def trigger_event(self, event: str, *args, **kwargs):
        """Triggers a standard application event on all loaded plugins.

        This method iterates through all currently loaded and active plugins
        and calls `dispatch_event()` for each one. It includes re-entrancy
        protection using `_event_context` to prevent infinite loops if an
        event handler triggers an action that causes the same event to be
        dispatched again.

        Args:
            event (str): The name of the event to trigger (e.g., "before_server_start").
            *args: Positional arguments to pass to each plugin's event handler.
            **kwargs: Keyword arguments to pass to each plugin's event handler.
        """
        # Initialize the re-entrancy guard stack if it doesn't exist for this thread.
        if not hasattr(_event_context, "stack"):
            _event_context.stack = []

        # Re-entrancy check: If this event is already in the current call stack, skip.
        if event in _event_context.stack:
            logger.debug(
                f"Skipping recursive trigger of standard event '{event}'. "
                f"Event is already in the processing stack: {_event_context.stack}"
            )
            return

        # Add the current event to the stack.
        _event_context.stack.append(event)
        logger.debug(
            f"Dispatching standard event '{event}' to {len(self.plugins)} loaded plugins. "
            f"Args: {args}, Kwargs: {kwargs}. Current stack: {_event_context.stack}"
        )

        try:
            # Iterate over a copy of the plugins list in case a plugin's event handler
            # somehow modifies the list of loaded plugins (though this is not typical).
            for plugin_instance in list(self.plugins):
                self.dispatch_event(plugin_instance, event, *args, **kwargs)
        finally:
            # Remove the event from the stack once dispatched to all plugins.
            _event_context.stack.pop()
            logger.debug(
                f"Finished dispatching standard event '{event}'. "
                f"Stack after pop: {_event_context.stack}"
            )

    def trigger_guarded_event(self, event: str, *args, **kwargs):
        """Triggers a standard application event only if not in a guarded child process.

        This method checks for the presence of the `GUARD_VARIABLE` environment
        variable. If this variable is set (indicating the current process might
        be a specially managed child process where certain events should not occur),
        the event dispatch is skipped. Otherwise, it calls `trigger_event()`.

        Args:
            event (str): The name of the event to trigger.
            *args: Positional arguments for the event handler.
            **kwargs: Keyword arguments for the event handler.
        """
        if os.environ.get(GUARD_VARIABLE):
            logger.debug(
                f"Skipping guarded event '{event}' because GUARD_VARIABLE ('{GUARD_VARIABLE}') is set in environment."
            )
            return
        logger.debug(f"GUARD_VARIABLE not set. Proceeding to trigger event '{event}'.")
        self.trigger_event(event, *args, **kwargs)
