# bedrock_server_manager/plugins/plugin_manager.py
"""Manages the discovery, loading, lifecycle, and event dispatching for all plugins."""
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

logger = logging.getLogger(__name__)
_event_context = threading.local()
_custom_event_context = threading.local()

DEFAULT_ENABLED_PLUGINS = [
    "auto_reload_plugin",
    "autoupdate_plugin",
    "server_lifecycle_notifications_plugin",
    "world_operation_notifications_plugin",
]


class PluginManager:
    """Manages the discovery, loading, and lifecycle of all plugins."""

    def __init__(self):
        """Initializes the PluginManager."""
        self.settings = settings
        user_plugin_dir = Path(self.settings.get("PLUGIN_DIR"))
        default_plugin_dir = Path(__file__).parent / "default"
        self.plugin_dirs: List[Path] = [user_plugin_dir, default_plugin_dir]
        self.config_path = Path(self.settings.config_dir) / "plugins.json"
        self.plugin_config: Dict[str, Dict[str, Any]] = {}
        self.plugins: List[PluginBase] = []
        self.custom_event_listeners: Dict[str, List[Tuple[str, Callable]]] = {}

        for directory in self.plugin_dirs:
            directory.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict[str, Dict[str, Any]]:
        """Loads the plugin configuration from plugins.json."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, TypeError) as e: # Added TypeError for robustness
            logger.error(
                f"Error decoding {self.config_path} or format is outdated. Attempting to rebuild. Error: {e}",
                exc_info=True, # Keep exc_info for detailed trace
            )
            return {} # Return empty to force rebuild
        except Exception as e:
            logger.error(f"Failed to load plugin config: {e}", exc_info=True)
            return {}

    def _save_config(self):
        """Saves the current plugin configuration to plugins.json."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.plugin_config, f, indent=4, sort_keys=True)
        except Exception as e:
            logger.error(f"Failed to save plugin config: {e}", exc_info=True)

    def _find_plugin_path(self, plugin_name: str) -> Optional[Path]:
        """Searches all configured plugin directories for a given plugin file."""
        for directory in self.plugin_dirs:
            path = directory / f"{plugin_name}.py"
            if path.exists():
                return path
        return None

    def _get_plugin_class_from_path(self, path: Path) -> Optional[Type[PluginBase]]:
        """Dynamically loads a module and finds the PluginBase subclass within it."""
        plugin_name = path.stem
        try:
            spec = importlib.util.spec_from_file_location(plugin_name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not create module spec for {plugin_name}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for _, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, PluginBase)
                    and obj is not PluginBase
                ):
                    return obj
        except Exception as e:
            logger.error(f"Failed to inspect plugin file at {path}: {e}", exc_info=True)
        return None

    def _synchronize_config_with_disk(self):
        """
        Scans plugin directories, validates plugins (must have a version),
        extracts metadata, and updates/repairs plugins.json.
        """
        logger.debug("Synchronizing plugin configuration with disk.")
        self.plugin_config = self._load_config()
        config_changed = False
        
        valid_plugins_found_on_disk = set() # Keep track of valid plugins by name

        # Scan all plugin directories
        all_potential_plugin_files: Dict[str, Path] = {}
        for directory in self.plugin_dirs:
            if not directory.exists():
                continue
            for path in directory.glob("*.py"):
                if not path.name.startswith("_"):
                    # User plugins can override default ones if directories are ordered appropriately
                    if path.stem not in all_potential_plugin_files:
                        all_potential_plugin_files[path.stem] = path
        
        for plugin_name, path in all_potential_plugin_files.items():
            plugin_class = self._get_plugin_class_from_path(path)
            if not plugin_class:
                logger.warning(f"Could not find a valid PluginBase subclass in '{path}'. Skipping.")
                # If it was in config, mark for removal later if it's no longer valid
                if plugin_name in self.plugin_config:
                    self.plugin_config.pop(plugin_name) # Remove invalid entry
                    config_changed = True
                    logger.info(f"Removed invalid plugin entry '{plugin_name}' from config because its class could not be loaded.")
                continue

            # --- STRICT VERSION CHECK ---
            version = getattr(plugin_class, "version", None)
            if not version or not str(version).strip(): # Check if version is None, empty, or whitespace
                logger.warning(
                    f"Plugin file '{path}' is missing a valid 'version' class attribute or version is empty. "
                    "This plugin will be ignored and not loaded."
                )
                # If it was in config, remove it as it's no longer loadable
                if plugin_name in self.plugin_config:
                    self.plugin_config.pop(plugin_name)
                    config_changed = True
                    logger.info(f"Removed plugin entry '{plugin_name}' from config due to missing/invalid version.")
                continue # Skip this plugin entirely

            valid_plugins_found_on_disk.add(plugin_name) # Mark as valid for later cleanup
            version = str(version).strip() # Ensure version is a clean string

            description = inspect.getdoc(plugin_class) or "No description available."
            description = " ".join(description.strip().split())

            current_config_entry = self.plugin_config.get(plugin_name)
            needs_update = False

            # Case 1: New plugin or old format (bool) or fundamentally broken dict
            if not isinstance(current_config_entry, dict):
                is_enabled_default = plugin_name in DEFAULT_ENABLED_PLUGINS
                # If old format was bool, respect that, otherwise use default
                is_enabled = bool(current_config_entry) if isinstance(current_config_entry, bool) else is_enabled_default
                
                self.plugin_config[plugin_name] = {
                    "enabled": is_enabled,
                    "description": description,
                    "version": version,
                }
                config_changed = True
                needs_update = True # Flag that an update happened
                if current_config_entry is None:
                    logger.info(f"Discovered valid plugin '{plugin_name}' v{version}. Added to config.")
                else:
                    logger.info(f"Upgraded configuration format for plugin '{plugin_name}' v{version}.")
            
            # Case 2: Existing dictionary entry, check for missing keys or changed metadata
            else:
                updated_entry = current_config_entry.copy() # Work on a copy
                
                # Ensure 'enabled' key exists
                if "enabled" not in updated_entry:
                    updated_entry["enabled"] = plugin_name in DEFAULT_ENABLED_PLUGINS
                    needs_update = True
                
                # Ensure 'description' key exists and update if different
                if updated_entry.get("description") != description:
                    updated_entry["description"] = description
                    needs_update = True
                
                # Ensure 'version' key exists and update if different
                if updated_entry.get("version") != version:
                    updated_entry["version"] = version
                    needs_update = True
                
                if needs_update:
                    self.plugin_config[plugin_name] = updated_entry
                    config_changed = True
                    logger.info(f"Updated metadata/config for plugin '{plugin_name}' to v{version}.")

        # Clean up config entries for plugins that no longer exist on disk or were invalidated
        for plugin_name_in_config in list(self.plugin_config.keys()):
            if plugin_name_in_config not in valid_plugins_found_on_disk:
                del self.plugin_config[plugin_name_in_config]
                config_changed = True
                logger.info(
                    f"Removed stale or invalid (e.g., missing version) plugin entry '{plugin_name_in_config}' from config."
                )

        if config_changed:
            self._save_config()

    def load_plugins(self):
        """Discovers and loads enabled plugins based on the (now validated) configuration."""
        self._synchronize_config_with_disk() # Ensures config is up-to-date and valid
        logger.info(f"Loading plugins from: {[str(d) for d in self.plugin_dirs]}")

        # Clear existing plugins before loading to support reload functionality correctly
        if self.plugins: # Only log if there were plugins to clear
            logger.debug(f"Clearing {len(self.plugins)} previously loaded plugin instances before new load.")
            self.plugins.clear()


        for plugin_name, config_data in self.plugin_config.items():
            # config_data should always be a dict here due to _synchronize_config_with_disk
            if not config_data.get("enabled"): # Relies on 'enabled' key being present
                logger.debug(f"Plugin '{plugin_name}' is disabled in config. Skipping.")
                continue

            # Version check here is mostly a safeguard; primary validation is in _synchronize_config_with_disk
            plugin_version = config_data.get("version")
            if not plugin_version or plugin_version == "N/A": # N/A might be a default from an older sync
                 logger.warning(f"Plugin '{plugin_name}' has missing or invalid version ('{plugin_version}') in config despite sync. Skipping load.")
                 continue

            path = self._find_plugin_path(plugin_name)
            if not path: # Should not happen if sync worked, but good to check
                logger.warning(f"Enabled plugin '{plugin_name}' v{plugin_version} path not found. Skipping.")
                continue

            plugin_class = self._get_plugin_class_from_path(path)
            if plugin_class:
                try:
                    plugin_logger = logging.getLogger(f"plugin.{plugin_name}")
                    api_instance = PluginAPI(plugin_name=plugin_name, plugin_manager=self)
                    instance = plugin_class(plugin_name, api_instance, plugin_logger)
                    self.plugins.append(instance)
                    # Log version from config_data as it's the validated source of truth for metadata
                    logger.info(f"Loaded plugin: {plugin_name} v{plugin_version}")
                    self.dispatch_event(instance, "on_load")
                except Exception as e:
                    logger.error(f"Failed to instantiate plugin '{plugin_name}': {e}", exc_info=True)
            else:
                # This case should ideally be caught by _synchronize_config_with_disk
                logger.error(f"Could not get class for plugin '{plugin_name}' at path '{path}' during load. Skipping.")


    def register_plugin_event_listener(
        self, event_name: str, callback: Callable, listening_plugin_name: str
    ):
        """Registers a callback for a custom plugin event."""
        if not callable(callback):
            logger.error(f"Plugin '{listening_plugin_name}' attempted to register non-callable for '{event_name}'.")
            return
        self.custom_event_listeners.setdefault(event_name, []).append(
            (listening_plugin_name, callback)
        )
        logger.info(f"Plugin '{listening_plugin_name}' registered listener for custom event '{event_name}'.")

    def trigger_custom_plugin_event(
        self, event_name: str, triggering_plugin_name: str, *args, **kwargs
    ):
        """Triggers a custom event, calling all registered listeners."""
        if not hasattr(_custom_event_context, "stack"):
            _custom_event_context.stack = []
        if event_name in _custom_event_context.stack:
            logger.debug(f"Skipping recursive custom event '{event_name}' by '{triggering_plugin_name}'.")
            return

        _custom_event_context.stack.append(event_name)
        logger.info(f"Plugin '{triggering_plugin_name}' triggering custom event '{event_name}'.")
        try:
            listeners = self.custom_event_listeners.get(event_name, [])
            logger.debug(f"Found {len(listeners)} listeners for custom event '{event_name}'.")
            for listener_plugin_name, callback in listeners:
                try:
                    callback(*args, **kwargs, _triggering_plugin=triggering_plugin_name)
                except Exception as e:
                    logger.error(
                        f"Error in plugin '{listener_plugin_name}' handling custom event '{event_name}' "
                        f"(triggered by '{triggering_plugin_name}'): {e}",
                        exc_info=True,
                    )
        finally:
            _custom_event_context.stack.pop()

    def reload(self):
        """Unloads all current plugins and reloads them from disk and config."""
        logger.info("--- Starting Plugin Reload ---")
        
        # 1. Unload existing plugins safely
        if self.plugins:
            logger.info(f"Unloading {len(self.plugins)} currently active plugins...")
            for plugin in list(self.plugins): # Iterate over a copy
                self.dispatch_event(plugin, "on_unload")
                logger.debug(f"Dispatched unload event for '{plugin.name}'.")
        
        # self.plugins list is cleared by load_plugins if it's called after this.
        # If load_plugins doesn't clear, then clear it here:
        # self.plugins.clear() 
        # logger.info("Cleared active plugin list.")
        
        # Unregister all custom event listeners as plugins that registered them are unloaded
        self.custom_event_listeners.clear()
        logger.info("Cleared all custom plugin event listeners.")

        # 2. Re-run the loading process
        logger.info("Re-running plugin discovery and loading process...")
        self.load_plugins() # This will synchronize and load

        logger.info("--- Plugin Reload Complete ---")

    def dispatch_event(self, target_plugin: PluginBase, event: str, *args, **kwargs):
        """Dispatches a single event to a specific plugin instance."""
        if hasattr(target_plugin, event):
            try:
                getattr(target_plugin, event)(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error in plugin '{target_plugin.name}' during '{event}': {e}",
                    exc_info=True,
                )

    def trigger_event(self, event: str, *args, **kwargs):
        """Triggers an event on all loaded plugins with re-entrancy protection."""
        if not hasattr(_event_context, "stack"):
            _event_context.stack = []
        if event in _event_context.stack:
            logger.debug(f"Skipping recursive event trigger for '{event}'.")
            return

        _event_context.stack.append(event)
        try:
            logger.debug(f"Dispatching event '{event}'. Current stack: {_event_context.stack} (Plugins: {len(self.plugins)})")
            for plugin in self.plugins: # Iterate over current list of loaded plugins
                self.dispatch_event(plugin, event, *args, **kwargs)
        finally:
            _event_context.stack.pop()
            logger.debug(f"Finished event '{event}'. Current stack: {_event_context.stack}")


    def trigger_guarded_event(self, event: str, *args, **kwargs):
        """Triggers an event only if not in a guarded child process."""
        if os.environ.get(GUARD_VARIABLE):
            logger.debug(f"Skipping guarded event '{event}' due to GUARD_VARIABLE.")
            return
        self.trigger_event(event, *args, **kwargs)