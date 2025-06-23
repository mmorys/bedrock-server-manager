# bedrock_server_manager/plugins/api_bridge.py
"""A bridge to safely expose core application APIs to plugins.

This module provides a critical decoupling mechanism for the plugin system.
Instead of plugins importing API functions directly (which would create
circular dependencies), the core API modules register their functions here at
startup. Plugins are then given an instance of the `PluginAPI` class, which
provides dynamic, safe access to these registered functions.
"""
from typing import Dict, Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .plugin_manager import PluginManager  # To avoid circular import at runtime

# This private dictionary holds the mapping from a public API name (str)
# to the actual callable function from the core application. It is populated
# at runtime by the `register_api` function.
_api_registry: Dict[str, Callable[..., Any]] = {}


def register_api(name: str, func: Callable[..., Any]):
    """Registers a core application function to make it available to plugins.

    This function is intended to be called by the application's core API
    modules during their initialization phase.

    Args:
        name: The public string name that plugins will use to call the function.
        func: A reference to the callable API function.
    """
    _api_registry[name] = func


class PluginAPI:
    """Provides a safe, dynamic interface for plugins to access core APIs.

    An instance of this class is passed to each plugin upon initialization.
    Plugins use this instance to call core functions (e.g., `api.start_server(...)`)
    without needing to import them directly. It also provides methods for
    interacting with the custom plugin event system.
    """

    def __init__(self, plugin_name: str, plugin_manager: "PluginManager"):
        """
        Initializes the PluginAPI instance for a specific plugin.

        Args:
            plugin_name: The name of the plugin this API instance belongs to.
            plugin_manager: A reference to the PluginManager instance.
        """
        self._plugin_name = plugin_name
        self._plugin_manager = plugin_manager

    def __getattr__(self, name: str) -> Callable[..., Any]:
        """Dynamically retrieves a registered core API function when accessed as an attribute.

        This magic method is the core of the API bridge. When a plugin calls
        `api.some_function`, Python calls this method with `name='some_function'`.
        It then looks up the name in the registry and returns the corresponding
        function.

        Args:
            name: The name of the attribute (API function) being accessed.

        Returns:
            The callable API function from the registry.

        Raises:
            AttributeError: If the function `name` has not been registered.
        """
        if name not in _api_registry:
            raise AttributeError(
                f"The API function '{name}' has not been registered or does not exist."
            )
        return _api_registry[name]

    def list_available_apis(self) -> list[str]:
        """Returns a list of all registered API function names.

        This can be useful for introspection or debugging purposes.

        Returns:
            A list of strings, where each string is the name of an available
            API function.
        """
        return list(_api_registry.keys())

    def listen_for_event(self, event_name: str, callback: Callable[..., None]):
        """
        Registers a callback to be executed when a specific custom plugin event is triggered.

        Args:
            event_name: The name of the custom event to listen for (e.g., "myplugin:my_event").
                        It's good practice to namespace event names with the plugin name.
            callback: The function to call when the event is triggered.
                      It will receive any *args and **kwargs passed during `send_event`,
                      plus a `_triggering_plugin` keyword argument indicating the
                      name of the plugin that sent the event.
        """
        self._plugin_manager.register_plugin_event_listener(
            event_name, callback, self._plugin_name
        )

    def send_event(self, event_name: str, *args: Any, **kwargs: Any):
        """
        Triggers a custom plugin event, notifying all registered listeners.

        Args:
            event_name: The name of the custom event to trigger.
            *args: Positional arguments to pass to the event listeners.
            **kwargs: Keyword arguments to pass to the event listeners.
        """
        self._plugin_manager.trigger_custom_plugin_event(
            event_name, self._plugin_name, *args, **kwargs
        )
