# bedrock_server_manager/__init__.py
import logging

from bedrock_server_manager.config.const import get_installed_version
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.core.downloader import BedrockDownloader
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.plugins.plugin_base import PluginBase
from bedrock_server_manager import error as errors

# --- PLUGIN SYSTEM INITIALIZATION ---
from bedrock_server_manager.plugins.plugin_manager import PluginManager


logger = logging.getLogger(__name__)

__version__ = get_installed_version()


plugin_manager = PluginManager()
