# bedrock_server_manager/api/__init__.py
import logging

# Import the single plugin_manager instance from the top-level package
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.core.system.process import GUARD_VARIABLE

logger = logging.getLogger(__name__)

# --- Import all API modules to ensure their functions are registered ---
# The act of importing these files will execute the @plugin_method() calls within them.
from . import application
from . import addon
from . import backup_restore
from . import info
from . import misc
from . import player
from . import server
from . import server_install_config
from . import system
from . import task_scheduler
from . import utils
from . import web

# --- LOAD PLUGINS AND FIRE STARTUP EVENT ---
# Now that all APIs are registered, we can safely load the plugins.
plugin_manager.load_plugins()

# Trigger the startup event, respecting the process guard.
plugin_manager.trigger_guarded_event("on_manager_startup")
