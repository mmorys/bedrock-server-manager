# bedrock_server_manager/plugins/plugin_manager.py
"""Manages the discovery, loading, lifecycle, and event dispatching for all plugins.

This module contains the `PluginManager`, which is the central component of the
plugin system. It is responsible for:
- Finding plugin files from the designated directory.
- Synchronizing a `plugins.json` configuration file with available plugins.
- Loading only the plugins that are enabled in the configuration file.
- Instantiating plugin classes and providing them with an API bridge and logger.
- Triggering events and dispatching them to all loaded plugins.
- Preventing infinite loops from re-entrant event calls using a thread-local stack.
- Guarding certain events from being triggered in subprocesses.
"""
import os
import importlib.util
import inspect
import logging
import threading
import json
from pathlib import Path
from typing import List, Dict, Any


from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.config.const import GUARD_VARIABLE
from .plugin_base import PluginBase
from .api_bridge import PluginAPI

logger = logging.getLogger(__name__)

# A thread-local storage object to manage the event call stack for each thread.
# This is crucial for the re-entrancy guard to prevent a plugin from causing
# an infinite loop by triggering the same event it is currently handling.
_event_context = threading.local()


class PluginManager:
    """Manages the discovery, loading, and lifecycle of all plugins."""

    def __init__(self):
        """Initializes the PluginManager.

        It determines the plugin directory and configuration path from application
        settings, creates them if they don't exist, and prepares to load plugins.
        """
        app_data_path = Path(settings.app_data_dir)
        self.plugin_dir = app_data_path / "plugins"
        self.config_path = app_data_path / "plugins.json"
        self.plugin_config: Dict[str, bool] = {}
        self.plugins: List[PluginBase] = []
        self.api_bridge = PluginAPI()
        # Ensure the plugin directory exists so the application doesn't crash.
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict[str, bool]:
        """Loads the plugin configuration from plugins.json."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(
                f"Error decoding {self.config_path}. Please check its format. "
                "Loading with default settings.",
                exc_info=True,
            )
            return {}
        except Exception as e:
            logger.error(f"Failed to load plugin config: {e}", exc_info=True)
            return {}

    def _save_config(self):
        """Saves the current plugin configuration to plugins.json."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.plugin_config, f, indent=4, sort_keys=True)
        except Exception as e:
            logger.error(f"Failed to save plugin config: {e}", exc_info=True)

    def _synchronize_config_with_disk(self):
        """
        Scans the plugin directory and updates plugins.json.

        Any new .py files found in the directory that are not in the config
        will be added and set to `false` (disabled) by default. This makes
        it easy for administrators to enable new plugins.
        """
        logger.debug("Synchronizing plugin configuration with disk.")
        self.plugin_config = self._load_config()
        config_changed = False

        # Find all potential plugins on disk
        available_plugins = {
            p.stem for p in self.plugin_dir.glob("*.py") if not p.name.startswith("_")
        }

        # Add new plugins found on disk to the config file as disabled
        for plugin_name in available_plugins:
            if plugin_name not in self.plugin_config:
                self.plugin_config[plugin_name] = False  # Default to disabled
                config_changed = True
                logger.info(
                    f"Discovered new plugin '{plugin_name}'. Added to "
                    f"{self.config_path} as disabled."
                )

        # Clean up config entries for plugins that no longer exist
        for plugin_name in list(self.plugin_config.keys()):
            if plugin_name not in available_plugins:
                del self.plugin_config[plugin_name]
                config_changed = True
                logger.info(
                    f"Removed stale config entry for deleted plugin '{plugin_name}'."
                )

        if config_changed:
            self._save_config()

    def load_plugins(self):
        """
        Discovers and loads enabled plugins based on the plugins.json config.

        This method first synchronizes the plugins on disk with the config file,
        then iterates through the configuration, loading only the plugins that
        are marked as `true`. For each enabled plugin, it dynamically imports
        the module, finds the class inheriting from `PluginBase`, instantiates
        it, and calls its `on_load` method.
        """
        self._synchronize_config_with_disk()
        logger.info(f"Loading plugins from: {self.plugin_dir}")
        logger.info(f"Using configuration file: {self.config_path}")

        for plugin_name, is_enabled in self.plugin_config.items():
            if not is_enabled:
                logger.debug(f"Skipping disabled plugin: {plugin_name}")
                continue

            path = self.plugin_dir / f"{plugin_name}.py"
            if not path.exists():
                logger.warning(
                    f"Plugin '{plugin_name}' is enabled in config but its file "
                    f"was not found at {path}. Skipping."
                )
                continue

            try:
                # Dynamically import the module from its file path.
                spec = importlib.util.spec_from_file_location(plugin_name, path)
                if spec is None or spec.loader is None:
                    raise ImportError("Could not create module spec.")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find the class within the module that inherits from PluginBase.
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, PluginBase)
                        and obj is not PluginBase
                    ):
                        # Create a dedicated logger for this specific plugin.
                        plugin_logger = logging.getLogger(f"plugin.{plugin_name}")
                        # Instantiate the plugin, passing it the API bridge and logger.
                        instance = obj(plugin_name, self.api_bridge, plugin_logger)
                        self.plugins.append(instance)
                        logger.info(f"Successfully loaded plugin: {plugin_name}")
                        # Call the on_load hook for the newly loaded plugin.
                        self.dispatch_event(instance, "on_load")
                        break  # Assume one plugin class per file
                else:
                    logger.error(
                        f"Could not find a valid Plugin class in '{plugin_name}.py'."
                    )

            except Exception as e:
                logger.error(
                    f"Failed to load plugin '{plugin_name}': {e}", exc_info=True
                )

    def dispatch_event(self, target_plugin: PluginBase, event: str, *args, **kwargs):
        """Dispatches a single event to a specific plugin instance.

        This method safely calls the event handler method on the plugin,
        logging any exceptions that occur within the plugin's code.

        Args:
            target_plugin: The specific plugin instance to dispatch the event to.
            event: The name of the event (and the method to call).
            *args: Positional arguments to pass to the event handler.
            **kwargs: Keyword arguments to pass to the event handler.
        """
        if hasattr(target_plugin, event):
            try:
                method = getattr(target_plugin, event)
                method(*args, **kwargs)
            except Exception as e:
                # Isolate plugin errors so one bad plugin doesn't crash the manager.
                logger.error(
                    f"Error in plugin '{target_plugin.name}' during event '{event}': {e}",
                    exc_info=True,
                )

    def trigger_event(self, event: str, *args, **kwargs):
        """Triggers an event on all loaded plugins with re-entrancy protection.

        This method iterates through all loaded plugins and calls their
        corresponding event handler. It uses a thread-local stack to prevent
        infinite recursion if a plugin's event handler triggers the same event.

        Args:
            event: The name of the event to trigger.
            *args: Positional arguments for the event handler.
            **kwargs: Keyword arguments for the event handler.
        """
        # Lazily initialize the event stack for the current thread if it doesn't exist.
        if not hasattr(_event_context, "stack"):
            _event_context.stack = []

        # --- RE-ENTRANCY GUARD ---
        # If the event is already in the current thread's call stack, skip it.
        if event in _event_context.stack:
            logger.debug(
                f"Skipping recursive event trigger for '{event}' to prevent infinite loop. "
                f"Current stack: {_event_context.stack}"
            )
            return

        # Add the current event to the stack to mark it as "in progress".
        _event_context.stack.append(event)
        try:
            logger.debug(
                f"Dispatching event '{event}'. Current stack: {_event_context.stack}"
            )
            for plugin in self.plugins:
                self.dispatch_event(plugin, event, *args, **kwargs)
        finally:
            # Always remove the event from the stack after it's been handled.
            _event_context.stack.pop()
            logger.debug(
                f"Finished event '{event}'. Current stack: {_event_context.stack}"
            )

    def trigger_guarded_event(self, event: str, *args, **kwargs):
        """Triggers an event only if not in a guarded child process.

        This wrapper should be used for events (like `before_server_start`) that
        could be triggered from a child process spawned by the manager itself.
        It checks for an environment variable to determine if it's in such a
        process and prevents the event from firing to avoid side effects.

        Args:
            event: The name of the event to trigger.
            *args: Positional arguments for the event handler.
            **kwargs: Keyword arguments for the event handler.
        """
        # If the guard variable is set, this is a worker process. Do not trigger the event.
        if os.environ.get(GUARD_VARIABLE):
            logger.debug(
                f"Skipping guarded event '{event}' due to presence of GUARD_VARIABLE."
            )
            return

        # If the guard is not set, this is the main process, so proceed normally.
        self.trigger_event(event, *args, **kwargs)
