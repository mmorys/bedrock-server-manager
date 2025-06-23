# bedrock_server_manager/plugins/plugin_manager.py
"""Manages the discovery, loading, lifecycle, and event dispatching for all plugins."""
import os
import importlib.util
import inspect
import logging
import threading
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Type

from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.config.const import GUARD_VARIABLE
from .plugin_base import PluginBase
from .api_bridge import PluginAPI

logger = logging.getLogger(__name__)
_event_context = threading.local()

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
        self.api_bridge = PluginAPI()

        for directory in self.plugin_dirs:
            directory.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict[str, Dict[str, Any]]:
        """Loads the plugin configuration from plugins.json."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, TypeError):
            logger.error(
                f"Error decoding {self.config_path} or format is outdated.",
                exc_info=True,
            )
            return {}
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
                raise ImportError("Could not create module spec.")
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
        """Scans plugin directories, extracts metadata, and updates plugins.json."""
        logger.debug("Synchronizing plugin configuration with disk.")
        self.plugin_config = self._load_config()
        config_changed = False

        available_plugins_on_disk: Dict[str, Path] = {}
        for directory in self.plugin_dirs:
            if not directory.exists():
                continue
            for path in directory.glob("*.py"):
                if not path.name.startswith("_"):
                    if path.stem not in available_plugins_on_disk:
                        available_plugins_on_disk[path.stem] = path

        for plugin_name, path in available_plugins_on_disk.items():
            plugin_class = self._get_plugin_class_from_path(path)
            if not plugin_class:
                logger.warning(
                    f"Could not find a valid plugin class in {path}. Skipping."
                )
                continue

            # --- VERSION & DESCRIPTION EXTRACTION ---
            # Get version from class attribute, with a fallback for older plugins.
            version = getattr(plugin_class, "version", "N/A")
            # Get description from docstring, with a fallback.
            description = inspect.getdoc(plugin_class) or "No description available."
            description = " ".join(description.strip().split())

            current_config = self.plugin_config.get(plugin_name)

            if not current_config:
                is_default_enabled = plugin_name in DEFAULT_ENABLED_PLUGINS
                self.plugin_config[plugin_name] = {
                    "enabled": is_default_enabled,
                    "description": description,
                    "version": version,
                }
                config_changed = True
                status = "enabled" if is_default_enabled else "disabled"
                logger.info(
                    f"Discovered '{plugin_name}' v{version}. Added to config as {status}."
                )
            # Update metadata if it has changed on disk
            elif (
                current_config.get("description") != description
                or current_config.get("version") != version
            ):
                current_config["description"] = description
                current_config["version"] = version
                config_changed = True
                logger.info(
                    f"Updated metadata for plugin '{plugin_name}' to v{version}."
                )

        for plugin_name in list(self.plugin_config.keys()):
            if plugin_name not in available_plugins_on_disk:
                del self.plugin_config[plugin_name]
                config_changed = True
                logger.info(
                    f"Removed stale config entry for deleted plugin '{plugin_name}'."
                )

        if config_changed:
            self._save_config()

    def load_plugins(self):
        """Discovers and loads enabled plugins based on the configuration."""
        self._synchronize_config_with_disk()
        logger.info(f"Loading plugins from: {[str(d) for d in self.plugin_dirs]}")

        for plugin_name, config_data in self.plugin_config.items():
            if not isinstance(config_data, dict) or not config_data.get("enabled"):
                continue

            path = self._find_plugin_path(plugin_name)
            if not path:
                logger.warning(f"Enabled plugin '{plugin_name}' not found. Skipping.")
                continue

            plugin_class = self._get_plugin_class_from_path(path)
            if plugin_class:
                try:
                    plugin_logger = logging.getLogger(f"plugin.{plugin_name}")
                    instance = plugin_class(plugin_name, self.api_bridge, plugin_logger)
                    self.plugins.append(instance)
                    logger.info(
                        f"Loaded plugin: {plugin_name} v{getattr(instance, 'version', 'N/A')}"
                    )
                    self.dispatch_event(instance, "on_load")
                except Exception as e:
                    logger.error(
                        f"Failed to instantiate plugin '{plugin_name}': {e}",
                        exc_info=True,
                    )

    def reload(self):
        """Unloads all current plugins and reloads them from disk and config."""
        logger.info("--- Starting Plugin Reload ---")
        logger.info(f"Unloading {len(self.plugins)} active plugins...")
        for plugin in list(self.plugins):
            self.dispatch_event(plugin, "on_unload")
        self.plugins.clear()
        logger.info("Cleared active plugin list. Reloading...")
        self.load_plugins()
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
            for plugin in self.plugins:
                self.dispatch_event(plugin, event, *args, **kwargs)
        finally:
            _event_context.stack.pop()

    def trigger_guarded_event(self, event: str, *args, **kwargs):
        """Triggers an event only if not in a guarded child process."""
        if os.environ.get(GUARD_VARIABLE):
            logger.debug(f"Skipping guarded event '{event}' due to GUARD_VARIABLE.")
            return
        self.trigger_event(event, *args, **kwargs)
