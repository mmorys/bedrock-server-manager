# bedrock_server_manager/core/server/process_mixin.py
"""Provides the ServerProcessMixin for the BedrockServer class.

This mixin is responsible for managing the Bedrock server's system process.
This includes starting, stopping, checking its running status, sending commands,
and retrieving process resource information. It abstracts away platform-specific
details by using helper functions from the `core.system` module.
"""
import time
import os
import psutil
from datetime import timedelta
import shutil
import subprocess
from typing import Optional, Dict, Any, TYPE_CHECKING

# psutil is an optional dependency, but required for process management.
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

if TYPE_CHECKING:
    # This helps type checkers understand psutil types without making it a hard dependency.
    import psutil as psutil_for_types


# Local application imports.
from bedrock_server_manager.core.system import linux as system_linux_proc
from bedrock_server_manager.core.system import windows as system_windows_proc
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.error import (
    ConfigurationError,
    MissingArgumentError,
    CommandNotFoundError,
    ServerNotRunningError,
    ServerStopError,
    SendCommandError,
    FileOperationError,
    ServerStartError,
    SystemError,
    ServerProcessError,
)


class ServerProcessMixin(BedrockServerBaseMixin):
    """A mixin for BedrockServer providing process management methods.

    This class handles starting, stopping, sending commands to, and querying
    the status and resource usage of the server's underlying system process.
    """

    def __init__(self, *args, **kwargs):
        """Initializes the ServerProcessMixin.

        This constructor calls `super().__init__` to ensure proper method
        resolution order in the context of multiple inheritance. It relies on
        attributes and methods from other mixins or the base class.
        """
        super().__init__(*args, **kwargs)
        # self.server_name, self.base_dir, self.logger, self.settings, etc., are available from BaseMixin.
        # Methods like self.is_installed(), self.set_status_in_config(), etc., are expected
        # to be available from other mixins on the final BedrockServer class.

    def is_running(self) -> bool:
        """Checks if the Bedrock server process is currently running.

        This method delegates the platform-specific checks to the `core.system`
        module. It does not update the server's stored status but simply returns
        the current runtime state.

        Returns:
            True if the server process is running, False otherwise.

        Raises:
            ConfigurationError: If the `BASE_DIR` setting is not configured.
        """
        self.logger.debug(f"Checking if server '{self.server_name}' is running.")

        if not self.base_dir:
            raise ConfigurationError(
                "BASE_DIR not configured, cannot check server running status."
            )

        try:
            is_running_flag = system_base.is_server_running(
                self.server_name, self.base_dir
            )
            self.logger.debug(
                f"system_base.is_server_running for '{self.server_name}' returned: {is_running_flag}"
            )
            return is_running_flag
        except (
            MissingArgumentError,
            CommandNotFoundError,
            SystemError,
            ServerProcessError,
        ) as e_check:
            self.logger.warning(
                f"Error during system_base.is_server_running for '{self.server_name}': {e_check}"
            )
            return False  # Treat check failures as "not running" for safety.
        except ConfigurationError:
            raise  # Re-raise if it's a critical configuration error.
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error in system_base.is_server_running for '{self.server_name}': {e_unexp}",
                exc_info=True,
            )
            return False

    def send_command(self, command: str):
        """Sends a command string to the running server process.

        The implementation is platform-specific, using `screen` on Linux and
        named pipes on Windows.

        Args:
            command: The command string to send to the server console.

        Raises:
            MissingArgumentError: If the command string is empty.
            ServerNotRunningError: If the server is not running.
            NotImplementedError: If the OS is not supported.
            SendCommandError: For other failures during the send operation.
        """
        if not command:
            raise MissingArgumentError("Command cannot be empty.")

        if not self.is_running():
            raise ServerNotRunningError(f"Server '{self.server_name}' is not running.")

        self.logger.info(
            f"Sending command '{command}' to server '{self.server_name}' on {self.os_type}..."
        )

        try:
            # Delegate to the appropriate platform-specific system function.
            if self.os_type == "Linux":
                if not system_linux_proc:
                    raise NotImplementedError("Linux system module not available.")
                system_linux_proc._linux_send_command(self.server_name, command)
            elif self.os_type == "Windows":
                if not system_windows_proc:
                    raise NotImplementedError("Windows system module not available.")
                system_windows_proc._windows_send_command(self.server_name, command)
            else:
                raise NotImplementedError(
                    f"Sending commands not supported on {self.os_type}"
                )

            self.logger.info(
                f"Command '{command}' sent successfully to '{self.server_name}'."
            )

        except (
            MissingArgumentError,
            ServerNotRunningError,
            SendCommandError,
            CommandNotFoundError,
            NotImplementedError,
            SystemError,
        ) as e:
            self.logger.error(
                f"Failed to send command '{command}' to server '{self.server_name}': {e}"
            )
            raise  # Re-raise known, specific errors.
        except Exception as e_unexp:
            raise SendCommandError(
                f"Unexpected error sending command to '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def start(self):
        """Starts the Bedrock server process.

        This method handles platform-specific start procedures. On Linux, it
        uses a `screen` session. On Windows, it starts the process directly,
        which is a blocking call. It manages the server's status in the
        configuration file throughout the process.

        Raises:
            ServerStartError: If the server is not installed, already running,
                or fails to start within the configured timeout.
            CommandNotFoundError: If required commands (like 'screen') are missing.
        """
        if not self.is_installed():
            raise ServerStartError(
                f"Cannot start server '{self.server_name}': Not installed or invalid installation at {self.server_dir}."
            )

        if self.is_running():
            self.logger.warning(
                f"Attempted to start server '{self.server_name}' but it is already running."
            )
            raise ServerStartError(f"Server '{self.server_name}' is already running.")

        try:
            self.set_status_in_config("STARTING")
        except Exception as e_stat:
            self.logger.warning(
                f"Failed to set status to STARTING for '{self.server_name}': {e_stat}"
            )

        self.logger.info(
            f"Attempting to start server '{self.server_name}' on {self.os_type}..."
        )

        start_successful = False
        # --- Linux Start Logic ---
        if self.os_type == "Linux":
            if not shutil.which("screen"):
                self.set_status_in_config("ERROR")
                raise CommandNotFoundError(
                    "screen", message="'screen' command not found. Cannot start server."
                )

            try:
                system_linux_proc._linux_start_server(self.server_name, self.server_dir)
                self.logger.info(
                    f"Linux server '{self.server_name}' start process initiated via screen."
                )

                # Wait for confirmation that the process is running.
                attempts = 0
                max_attempts = self.settings.get("SERVER_START_TIMEOUT_SEC", 60) // 2
                sleep_interval = 2
                self.logger.info(
                    f"Waiting up to {max_attempts * sleep_interval}s for '{self.server_name}' to confirm running..."
                )

                while attempts < max_attempts:
                    if self.is_running():
                        self.set_status_in_config("RUNNING")
                        self.logger.info(
                            f"Server '{self.server_name}' started successfully and confirmed running."
                        )
                        start_successful = True
                        break
                    self.logger.debug(
                        f"Waiting for '{self.server_name}' to start... (Attempt {attempts + 1}/{max_attempts})"
                    )
                    time.sleep(sleep_interval)
                    attempts += 1

                if not start_successful:
                    self.set_status_in_config("ERROR")
                    raise ServerStartError(
                        f"Server '{self.server_name}' failed to start within timeout."
                    )

            except (CommandNotFoundError, ServerStartError) as e_start_linux:
                self.set_status_in_config("ERROR")
                raise
            except Exception as e_unexp_linux:
                self.set_status_in_config("ERROR")
                raise ServerStartError(
                    f"Unexpected error starting Linux server '{self.server_name}': {e_unexp_linux}"
                ) from e_unexp_linux

        # --- Windows Start Logic ---
        elif self.os_type == "Windows":
            self.logger.debug(
                "Attempting to start server via Windows process creation (foreground blocking call)."
            )
            try:
                system_windows_proc._windows_start_server(
                    self.server_name, self.server_dir, self.app_config_dir
                )
                self.logger.info(
                    f"Foreground Windows server session for '{self.server_name}' has ended."
                )
                # The status should be set to STOPPED by the windows helper on exit.
                final_status = self.get_status_from_config()
                if final_status == "RUNNING":
                    self.logger.warning(
                        f"Windows server '{self.server_name}' ended, but status still RUNNING. Setting to STOPPED."
                    )
                    self.set_status_in_config("STOPPED")
                start_successful = final_status not in ("ERROR", "STARTING")

            except (SystemError, ServerStartError) as e_start_win:
                self.set_status_in_config("ERROR")
                raise
            except Exception as e_unexp_win:
                self.set_status_in_config("ERROR")
                raise ServerStartError(
                    f"Unexpected error starting Windows server '{self.server_name}': {e_unexp_win}"
                ) from e_unexp_win
        else:
            self.set_status_in_config("ERROR")
            raise ServerStartError(
                f"Unsupported operating system for start: {self.os_type}"
            )

        if not start_successful and self.os_type != "Windows":
            if self.get_status_from_config() != "RUNNING":
                self.set_status_in_config("ERROR")
                raise ServerStartError(
                    f"Server '{self.server_name}' start did not complete successfully."
                )

    def stop(self):
        """Stops the Bedrock server process gracefully, with a forceful fallback.

        This method first sends a 'stop' command to the server. It then waits
        for the process to terminate. If the process does not terminate within
        the configured timeout, it will attempt a forceful, PID-based termination.

        Raises:
            ServerStopError: If the server fails to stop after all attempts.
        """
        if not self.is_running():
            self.logger.info(
                f"Attempted to stop server '{self.server_name}', but it is not currently running."
            )
            if self.get_status_from_config() != "STOPPED":
                try:
                    self.set_status_in_config("STOPPED")
                except Exception as e_stat:
                    self.logger.warning(
                        f"Failed to set status to STOPPED for non-running server '{self.server_name}': {e_stat}"
                    )
            return

        try:
            self.set_status_in_config("STOPPING")
        except Exception as e_stat:
            self.logger.warning(
                f"Failed to set status to STOPPING for '{self.server_name}': {e_stat}"
            )

        self.logger.info(f"Attempting to stop server '{self.server_name}'...")

        # --- 1. Attempt graceful shutdown via command ---
        try:
            if hasattr(self, "send_command"):
                self.send_command("stop")
                self.logger.info(f"Sent 'stop' command to server '{self.server_name}'.")
            else:
                self.logger.warning(
                    "send_command method not found on self. Cannot send graceful stop command."
                )
        except (
            ServerNotRunningError,
            SendCommandError,
            NotImplementedError,
            CommandNotFoundError,
        ) as e_cmd:
            self.logger.warning(
                f"Failed to send 'stop' command to '{self.server_name}': {e_cmd}. Will check process status."
            )
        except Exception as e_unexp_cmd:
            self.logger.error(
                f"Unexpected error sending 'stop' command to '{self.server_name}': {e_unexp_cmd}",
                exc_info=True,
            )

        # --- 2. Wait for process to terminate ---
        max_attempts = self.settings.get("SERVER_STOP_TIMEOUT_SEC", 60) // 2
        sleep_interval = 2
        self.logger.info(
            f"Waiting up to {max_attempts * sleep_interval}s for '{self.server_name}' process to terminate..."
        )

        for _ in range(max_attempts):
            if not self.is_running():
                self.set_status_in_config("STOPPED")
                self.logger.info(f"Server '{self.server_name}' stopped successfully.")
                # On Linux, also clean up the screen session.
                if self.os_type == "Linux":
                    system_linux_proc._cleanup_linux_screen_session(self.server_name)
                return  # Successfully stopped.

            self.logger.debug(f"Waiting for '{self.server_name}' to stop...")
            time.sleep(sleep_interval)

        # --- 3. If still running, attempt forceful PID-based termination ---
        self.logger.error(
            f"Server '{self.server_name}' failed to stop after command and wait."
        )
        if self.is_running():
            self.logger.info(
                f"Server '{self.server_name}' still running. Attempting forceful PID-based termination."
            )
            from bedrock_server_manager.core.system import (
                process as system_process_utils,
            )

            pid_file_path = self.get_pid_file_path()
            try:
                pid_to_terminate = system_process_utils.read_pid_from_file(
                    pid_file_path
                )
                if pid_to_terminate and system_process_utils.is_process_running(
                    pid_to_terminate
                ):
                    self.logger.info(
                        f"Terminating PID {pid_to_terminate} for '{self.server_name}'."
                    )
                    system_process_utils.terminate_process_by_pid(pid_to_terminate)
                    time.sleep(sleep_interval)
                    if not self.is_running():
                        self.set_status_in_config("STOPPED")
                        self.logger.info(
                            f"Server '{self.server_name}' (PID {pid_to_terminate}) forcefully terminated and confirmed stopped."
                        )
                        return
                    else:
                        self.logger.error(
                            f"Server '{self.server_name}' (PID {pid_to_terminate}) STILL RUNNING after forceful termination."
                        )
            except (
                FileOperationError,
                SystemError,
                ServerStopError,
                Exception,
            ) as e_force:
                self.logger.error(
                    f"Error during forceful termination of '{self.server_name}': {e_force}",
                    exc_info=True,
                )

        # --- 4. Final status check ---
        if self.get_status_from_config() != "STOPPED":
            self.set_status_in_config("ERROR")

        if self.is_running():
            raise ServerStopError(
                f"Server '{self.server_name}' failed to stop after all attempts. Manual intervention may be required."
            )
        else:
            self.logger.warning(
                f"Server '{self.server_name}' stopped, but possibly not gracefully."
            )
            if self.get_status_from_config() != "STOPPED":
                self.set_status_in_config("STOPPED")

    def get_process_info(self) -> Optional[Dict[str, Any]]:
        """Gets resource usage information for the running server process.

        This includes PID, CPU usage percentage, memory in MB, and uptime.

        Returns:
            A dictionary containing process information, or `None` if the
            server is not running or `psutil` is not available.
        """
        return system_base._get_bedrock_process_info(self.server_name, self.base_dir)
