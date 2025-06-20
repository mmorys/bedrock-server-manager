# bedrock_server_manager/plugins/plugin_manager.py
"""Manages the discovery, loading, lifecycle, and event dispatching for all plugins.

This module contains the `PluginManager`, which is the central component of the
plugin system. It is responsible for:
- Finding and loading plugin files from the designated directory.
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

        It determines the plugin directory from application settings, creates it
        if it doesn't exist, and prepares to load plugins.
        """
        plugin_dir = os.path.join(settings.app_data_dir, "plugins")
        self.plugin_dir = Path(plugin_dir)
        self.plugins: List[PluginBase] = []
        self.api_bridge = PluginAPI()
        # Ensure the plugin directory exists so the application doesn't crash.
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

    def load_plugins(self):
        """Discovers and loads all valid plugins from the plugin directory.

        This method iterates through all `.py` files in the plugin directory,
        dynamically imports them as modules, and looks for a class that
        inherits from `PluginBase`. It then instantiates the plugin and calls
        its `on_load` method.
        """
        logger.info(f"Loading plugins from: {self.plugin_dir}")
        for path in self.plugin_dir.glob("*.py"):
            # Ignore files that start with an underscore (e.g., `__init__.py`).
            if path.name.startswith("_"):
                continue

            plugin_name = path.stem
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
