# src/bedrock_server_manager/core/bedrock_process_manager.py
import os
import platform
import subprocess
import threading
import time
import logging
from typing import Dict, Optional, TYPE_CHECKING

from ..core.system import process as core_process
from ..error import (
    BSMError,
    ServerNotRunningError,
    ServerStartError,
    FileOperationError,
)
from ..config.settings import Settings
from ..context import AppContext

if TYPE_CHECKING:
    from .bedrock_server import BedrockServer


class BedrockProcessManager:
    """
    Manages Bedrock server processes, including monitoring and restarting.
    """

    def __init__(
        self,
        app_context: AppContext,
    ):
        """Initializes the BedrockProcessManager."""
        self.servers: Dict[str, "BedrockServer"] = {}
        self.logger = logging.getLogger(__name__)
        self.app_context = app_context
        self.settings = self.app_context.settings
        self.monitoring_thread = threading.Thread(
            target=self._monitor_servers, daemon=True
        )
        self.monitoring_thread.start()
        self.logger.info("BedrockProcessManager initialized.")

    def add_server(self, server: "BedrockServer"):
        """Adds a server to be managed by the process manager."""
        self.logger.info(
            f"Adding server '{server.server_name}' to process manager for monitoring."
        )
        self.servers[server.server_name] = server

    def remove_server(self, server_name: str):
        """Removes a server from the process manager."""
        if server_name in self.servers:
            self.logger.info(f"Removing server '{server_name}' from process manager.")
            del self.servers[server_name]

    def _monitor_servers(self):
        """Monitors server processes and restarts them if they crash."""
        try:
            monitoring_interval = self.settings.get(
                "SERVER_MONITORING_INTERVAL_SEC", 10
            )
        except Exception:
            monitoring_interval = 10

        self.logger.info(
            f"Server monitoring thread started with a {monitoring_interval} second interval."
        )
        while True:
            time.sleep(monitoring_interval)
            for server_name, server in list(self.servers.items()):
                if not server.is_running():
                    if not server.intentionally_stopped:
                        self.logger.warning(
                            f"Monitored server '{server.server_name}' has crashed."
                        )
                        server.failure_count += 1
                        self._try_restart_server(server)
                    else:
                        self.logger.info(
                            f"Server '{server.server_name}' was stopped intentionally. Removing from monitoring."
                        )
                        self.remove_server(server_name)

    def _try_restart_server(self, server: "BedrockServer"):
        """Tries to restart a crashed server."""
        max_retries = self.settings.get("SERVER_MAX_RESTART_RETRIES", 3)

        if server.failure_count > max_retries:
            self.logger.critical(
                f"Server '{server.server_name}' has reached the maximum restart limit of {max_retries}. Will not attempt to restart again."
            )
            self.write_error_status(server.server_name)
            self.remove_server(server.server_name)  # Stop monitoring
            return

        self.logger.info(
            f"Attempting to restart server '{server.server_name}'. Attempt {server.failure_count}/{max_retries}."
        )
        try:
            server.start()
            self.logger.info(f"Server '{server.server_name}' restarted successfully.")
        except ServerStartError as e:
            self.logger.critical(
                f"Failed to restart server '{server.server_name}': {e}", exc_info=True
            )
            time.sleep(5)

    def write_error_status(self, server_name: str):
        """Writes 'ERROR' to server config status."""
        server = self.app_context.get_server(server_name)
        try:
            server.set_status_in_config("ERROR")
        except BSMError as e:
            self.logger.error(f"Error writing status for server '{server_name}': {e}")
            raise FileOperationError(
                f"Failed to write status for server '{server_name}'."
            )
