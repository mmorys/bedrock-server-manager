# bedrock_server_manager/core/server/base_server_mixin.py
"""
Provides the BedrockServerBaseMixin class, which forms the foundational layer
for the BedrockServer class and its other mixins.

This mixin initializes core attributes like server name, paths, settings,
and logger, which are common across all server-related operations.
"""
import os
import platform
import logging
import subprocess
import threading
from typing import Optional, TYPE_CHECKING, Any

# Local imports
from bedrock_server_manager.config.const import EXPATH as CONST_EXPATH
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.error import MissingArgumentError, ConfigurationError


class BedrockServerBaseMixin:
    """
    Base mixin providing common properties for a BedrockServer instance.
    The main BedrockServer class will inherit from this first.
    Mixins should also inherit from this (or a class that does) and call super().__init__.
    """

    def __init__(
        self,
        server_name: str,
        settings_instance: Optional[Settings] = None,
        manager_expath: Optional[str] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the base attributes for a Bedrock server instance.

        Args:
            server_name: The unique name of the server.
            settings_instance: An optional pre-configured Settings object.
                               If None, a new Settings object is created.
            manager_expath: Optional path to the BSM executable, used for
                            operations like systemd service creation.
            *args: Variable length argument list for multiple inheritance.
            **kwargs: Arbitrary keyword arguments for multiple inheritance.

        Raises:
            MissingArgumentError: If `server_name` is not provided.
            ConfigurationError: If critical settings like BASE_DIR are missing.
        """
        super().__init__(*args, **kwargs)  # For cooperative multiple inheritance

        if not server_name:
            # This basic validation should happen early.
            raise MissingArgumentError(
                "BedrockServer cannot be initialized without a server_name."
            )

        self.logger: logging.Logger = logging.getLogger(__name__)

        self.server_name: str = server_name

        if settings_instance:
            self.settings = settings_instance
        else:
            self.settings = Settings()
        self.logger.debug(
            f"BedrockServerBaseMixin for '{self.server_name}' initialized using settings from: {self.settings.config_path}"
        )

        if manager_expath:
            self.manager_expath: str = manager_expath
        else:
            self.manager_expath: str = CONST_EXPATH
            if not self.manager_expath:
                self.logger.warning(
                    "manager_expath not provided and const.EXPATH is not set. "
                    "Some features (like systemd service creation) may not work."
                )

        # Resolved paths and values from settings
        # Ensure critical settings are present
        _base_dir_val = self.settings.get("BASE_DIR")
        if not _base_dir_val:
            raise ConfigurationError(
                "BASE_DIR not configured in settings. Cannot initialize BedrockServer."
            )
        self.base_dir: str = _base_dir_val

        self.server_dir: str = os.path.join(self.base_dir, self.server_name)

        # Global application config directory (for PIDs, status flags relevant to this server)
        # This comes from settings.config_dir property
        _app_cfg_dir_val = self.settings.config_dir
        if not _app_cfg_dir_val:
            raise ConfigurationError(
                "Application config_dir not available from settings. Cannot initialize BedrockServer."
            )
        self.app_config_dir: str = _app_cfg_dir_val

        self.os_type: str = platform.system()

        # For process resource monitoring (used by ProcessMixin)
        self._last_proc_cpu_times_stats: Optional[Any] = (
            None  # Type: psutil._common.scpustats
        )
        self._last_proc_sample_time: Optional[float] = None

        # For Windows foreground process management (used by ProcessMixin)
        self._windows_popen_process: Optional[subprocess.Popen] = None
        self._windows_pipe_listener_thread: Optional[threading.Thread] = None
        self._windows_pipe_shutdown_event: Optional[threading.Event] = None
        self._windows_stdout_handle: Optional[Any] = None  # Type: file object
        self._windows_pid_file_path_managed: Optional[str] = None

        self.logger.debug(
            f"BedrockServerBaseMixin initialized for '{self.server_name}' "
            f"at '{self.server_dir}'. App Config Dir: '{self.app_config_dir}'"
        )

    @property
    def bedrock_executable_name(self) -> str:
        """Returns the platform-specific name of the Bedrock server executable."""
        return "bedrock_server.exe" if self.os_type == "Windows" else "bedrock_server"

    @property
    def bedrock_executable_path(self) -> str:
        """Returns the full path to the Bedrock server executable within this server's directory."""
        return os.path.join(self.server_dir, self.bedrock_executable_name)

    @property
    def server_log_path(self) -> str:
        """Returns the expected path to the server's main output log file."""
        return os.path.join(self.server_dir, "server_output.txt")

    @property
    def _server_specific_config_dir(
        self,
    ) -> str:
        """Path to this server's own subdirectory within the app_config_dir for its JSON config."""
        return os.path.join(self.app_config_dir, self.server_name)

    def _get_server_pid_filename_default(self) -> str:
        """Generates a standardized PID filename for this Bedrock server for general use."""
        # Example: bedrock_MyServerName.pid
        # Ensure server_name is filesystem-friendly if it contains special chars.
        return f"bedrock_{self.server_name}.pid"

    def get_pid_file_path(self) -> str:
        """
        Gets the full path to this server's PID file, stored in the global application config directory.
        """
        pid_filename = self._get_server_pid_filename_default()
        server_config_dir = self._server_specific_config_dir

        return os.path.join(server_config_dir, pid_filename)
