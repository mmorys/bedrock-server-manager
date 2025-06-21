# bedrock_server_manager/core/server/base_server_mixin.py
"""Provides the foundational `BedrockServerBaseMixin` class.

This mixin is the first in the inheritance chain for the main `BedrockServer`
class. Its primary responsibility is to initialize core attributes that are
common across all server-related operations, such as server name, directory
paths, application settings, and the logger. All other mixins should inherit
from this class to ensure these fundamental attributes are available.
"""
import os
import platform
import logging
import subprocess
import threading
from typing import Optional, Any
from functools import cached_property

# Local application imports.
from bedrock_server_manager.config.const import EXPATH as CONST_EXPATH
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.error import MissingArgumentError, ConfigurationError


class BedrockServerBaseMixin:
    """The base mixin providing common attributes for a BedrockServer instance.

    This class should be inherited from first by the main `BedrockServer` class.
    Other mixins should also inherit from this (or a class that does) and call
    `super().__init__` to ensure cooperative multiple inheritance works correctly.
    """

    def __init__(
        self,
        server_name: str,
        settings_instance: Optional[Settings] = None,
        manager_expath: Optional[str] = None,
        *args,
        **kwargs,
    ):
        """Initializes the base attributes for a Bedrock server instance.

        Args:
            server_name: The unique name of the server, used to determine its
                directory and configuration paths.
            settings_instance: An optional, pre-configured `Settings` object.
                If None, a new one is created. This allows for dependency
                injection during testing.
            manager_expath: An optional path to the main application executable.
                This is used for operations that require the application to
                call itself, such as creating a systemd service.
            *args: Variable length argument list to support multiple inheritance.
            **kwargs: Arbitrary keyword arguments to support multiple inheritance.

        Raises:
            MissingArgumentError: If `server_name` is not provided.
            ConfigurationError: If critical settings like `BASE_DIR` are missing.
        """
        # Call to super() is essential for cooperative multiple inheritance.
        super().__init__(*args, **kwargs)

        if not server_name:
            # A server instance is meaningless without a name.
            raise MissingArgumentError(
                "BedrockServer cannot be initialized without a server_name."
            )

        self.logger: logging.Logger = logging.getLogger(__name__)

        self.server_name: str = server_name

        # Use the provided settings instance or create a new one.
        if settings_instance:
            self.settings = settings_instance
        else:
            self.settings = Settings()
        self.logger.debug(
            f"BedrockServerBaseMixin for '{self.server_name}' initialized using settings from: {self.settings.config_path}"
        )

        # Determine the path to the main application executable.
        if manager_expath:
            self.manager_expath: str = manager_expath
        else:
            self.manager_expath: str = CONST_EXPATH
            if not self.manager_expath:
                self.logger.warning(
                    "manager_expath not provided and const.EXPATH is not set. "
                    "Some features (like systemd service creation) may not work."
                )

        # Resolve critical paths from settings.
        _base_dir_val = self.settings.get("BASE_DIR")
        if not _base_dir_val:
            raise ConfigurationError(
                "BASE_DIR not configured in settings. Cannot initialize BedrockServer."
            )
        self.base_dir: str = _base_dir_val

        # The main directory where this server's files are stored.
        self.server_dir: str = os.path.join(self.base_dir, self.server_name)

        # The global application config directory, used for storing server-specific
        # JSON config files, PID files, etc.
        _app_cfg_dir_val = self.settings.config_dir
        if not _app_cfg_dir_val:
            raise ConfigurationError(
                "Application config_dir not available from settings. Cannot initialize BedrockServer."
            )
        self.app_config_dir: str = _app_cfg_dir_val

        # The operating system type (e.g., 'Windows', 'Linux').
        self.os_type: str = platform.system()

        # --- State attributes for other mixins ---
        # These are initialized here but primarily used by other mixins.

        # For process resource monitoring.
        self._resource_monitor = system_base.ResourceMonitor()

        # For managing a server process started in the foreground on Windows (used by ProcessMixin).
        self._windows_popen_process: Optional[subprocess.Popen] = None
        self._windows_pipe_listener_thread: Optional[threading.Thread] = None
        self._windows_pipe_shutdown_event: Optional[threading.Event] = None
        self._windows_stdout_handle: Optional[Any] = None
        self._windows_pid_file_path_managed: Optional[str] = None

        self.logger.debug(
            f"BedrockServerBaseMixin initialized for '{self.server_name}' "
            f"at '{self.server_dir}'. App Config Dir: '{self.app_config_dir}'"
        )

    @cached_property
    def bedrock_executable_name(self) -> str:
        """Returns the platform-specific name of the Bedrock server executable."""
        return "bedrock_server.exe" if self.os_type == "Windows" else "bedrock_server"

    @cached_property
    def bedrock_executable_path(self) -> str:
        """Returns the full path to the Bedrock server executable."""
        return os.path.join(self.server_dir, self.bedrock_executable_name)

    @cached_property
    def server_log_path(self) -> str:
        """Returns the expected path to the server's main output log file."""
        return os.path.join(self.server_dir, "server_output.txt")

    @cached_property
    def server_config_dir(self) -> str:
        """Returns the path to this server's dedicated configuration subdirectory."""

        return os.path.join(self.app_config_dir, self.server_name)

    def _get_server_pid_filename_default(self) -> str:
        """Generates a standardized PID filename for this Bedrock server."""
        return f"bedrock_{self.server_name}.pid"

    def get_pid_file_path(self) -> str:
        """Gets the full path to this server's primary PID file.

        This file is used to track the process ID of the running server,
        especially when it's started in a detached mode.
        """
        pid_filename = self._get_server_pid_filename_default()
        server_config_dir = self.server_config_dir

        return os.path.join(server_config_dir, pid_filename)
