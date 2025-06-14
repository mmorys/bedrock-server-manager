# bedrock_server_manager/core/server/process_mixin.py
"""
Provides the ServerProcessMixin class for BedrockServer.

This mixin is responsible for managing the Bedrock server process, including
starting, stopping, checking its running status, sending commands, and
retrieving process resource information. It uses platform-specific utilities
from `core.system`.
"""
import time
import os
import psutil
from datetime import timedelta
import shutil
import subprocess
from typing import Optional, Dict, Any, TYPE_CHECKING

# Third-party imports
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

if TYPE_CHECKING:
    import psutil as psutil_for_types


# Local imports
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
    """
    A mixin for the BedrockServer class that provides methods for managing
    the server's underlying system process. This includes starting, stopping,
    sending commands, and querying process status and resource usage.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the ServerProcessMixin.

        Calls super().__init__ for proper multiple inheritance setup.
        Relies on attributes (like server_name, base_dir, logger, settings,
        os_type, bedrock_executable_path, app_config_dir, get_pid_file_path)
        and methods (like is_installed, set_status_in_config, get_status_from_config)
        from other mixins or the base class.
        """
        super().__init__(*args, **kwargs)
        # Attributes: self.server_name, self.base_dir, self.logger, self.settings

    def is_running(self) -> bool:
        """
        Checks if the Bedrock server process for this server is currently running.
        Uses platform-specific checks from system_base.is_server_running.
        Does NOT update stored config status here; that's handled by get_status in StateMixin.
        """
        self.logger.debug(f"Checking if server '{self.server_name}' is running.")

        if not self.base_dir:
            self.logger.error(
                "is_running check failed: self.base_dir (from BASE_DIR setting) is not configured."
            )
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
        except ConfigurationError:  # Re-raise if it's from our own check
            raise
        except (
            Exception
        ) as e_unexp:  # Catch any other unexpected error from system_base.is_server_running
            self.logger.error(
                f"Unexpected error in system_base.is_server_running for '{self.server_name}': {e_unexp}",
                exc_info=True,
            )
            return False

    def send_command(self, command: str) -> None:
        """
        Sends a command string to the running server process.
        Implementation is platform-specific (screen on Linux, named pipes on Windows).

        Args:
            command: The command string to send to the server console.

        Raises: (as per original function, adapted for class context)
        """
        if not command:
            raise MissingArgumentError("Command cannot be empty.")

        if not self.is_running():
            self.logger.error(
                f"Cannot send command to server '{self.server_name}': Server is not running."
            )
            raise ServerNotRunningError(f"Server '{self.server_name}' is not running.")

        self.logger.info(
            f"Sending command '{command}' to server '{self.server_name}' on {self.os_type}..."
        )

        try:
            if self.os_type == "Linux":
                if not system_linux_proc:  # Should have been imported conditionally
                    raise NotImplementedError("Linux system module not available.")
                system_linux_proc._linux_send_command(self.server_name, command)
            elif self.os_type == "Windows":
                if not system_windows_proc:  # Should have been imported conditionally
                    raise NotImplementedError("Windows system module not available.")
                system_windows_proc._windows_send_command(self.server_name, command)
            else:
                self.logger.error(
                    f"Sending commands is not supported on this operating system: {self.os_type}"
                )
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
            # SystemError for pywin32 from _windows_send_command
            self.logger.error(
                f"Failed to send command '{command}' to server '{self.server_name}': {e}"
            )
            raise  # Re-raise known errors
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error sending command '{command}' to '{self.server_name}': {e_unexp}",
                exc_info=True,
            )
            raise SendCommandError(
                f"Unexpected error sending command to '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def start(self) -> None:
        """
        Starts the Bedrock server process.
        Uses systemd-compatible screen on Linux or starts directly on Windows (blocking call).
        Manages persistent status and waits for confirmation on Linux.

        Raises:
            ServerStartError: If the server is not installed, already running, or fails to start.
            CommandNotFoundError: If essential commands (like 'screen' on Linux) are missing.
            SystemError: For underlying system issues (e.g., missing Windows dependencies).
            FileOperationError: For issues related to file system access during start.
            ConfigurationError: If critical settings are misconfigured.
        """

        if (
            not self.is_installed()
        ):  # If using instance path, check standard installation
            raise ServerStartError(
                f"Cannot start server '{self.server_name}': Not installed or invalid installation at {self.server_dir}."
            )

        # is_running() will be self.is_running()
        if self.is_running():
            self.logger.warning(
                f"Attempted to start server '{self.server_name}' but it is already running."
            )
            raise ServerStartError(f"Server '{self.server_name}' is already running.")

        # manage_server_config for status is self.set_status_in_config (from StateMixin)
        try:
            self.set_status_in_config("STARTING")
        except Exception as e_stat:
            # Log but don't fail the start yet, process might still launch.
            self.logger.warning(
                f"Failed to set status to STARTING for '{self.server_name}': {e_stat}"
            )

        self.logger.info(
            f"Attempting to start server '{self.server_name}' on {self.os_type}..."
        )

        start_successful = False

        if self.os_type == "Linux":
            screen_cmd = shutil.which("screen")
            if not screen_cmd:
                self.logger.error(
                    "'screen' command not found. Cannot start server on Linux."
                )
                self.set_status_in_config("ERROR")
                raise CommandNotFoundError(
                    "screen", message="'screen' command not found. Cannot start server."
                )

            try:
                # system_linux_proc._linux_start_server uses self.server_name and self.server_dir
                system_linux_proc._linux_start_server(self.server_name, self.server_dir)
                self.logger.info(
                    f"Linux server '{self.server_name}' start process initiated via screen."
                )

                # Wait for confirmation
                attempts = 0
                max_attempts = (
                    self.settings.get("SERVER_START_TIMEOUT_SEC", 60) // 2
                )  # Default 60s, check every 2s
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
                    self.logger.error(
                        f"Server '{self.server_name}' failed to confirm running status after {max_attempts * sleep_interval}s."
                    )
                    self.set_status_in_config("ERROR")
                    raise ServerStartError(
                        f"Server '{self.server_name}' failed to start within timeout."
                    )

            except (
                CommandNotFoundError,
                ServerStartError,
            ) as e_start_linux:  # From _linux_start_server or our checks
                self.logger.error(
                    f"Failed to start server '{self.server_name}' on Linux: {e_start_linux}",
                    exc_info=True,
                )
                self.set_status_in_config("ERROR")  # Ensure status is ERROR
                raise
            except Exception as e_unexp_linux:  # Other unexpected errors
                self.logger.error(
                    f"Unexpected error starting server '{self.server_name}' on Linux: {e_unexp_linux}",
                    exc_info=True,
                )
                self.set_status_in_config("ERROR")
                raise ServerStartError(
                    f"Unexpected error starting Linux server '{self.server_name}': {e_unexp_linux}"
                ) from e_unexp_linux

        elif self.os_type == "Windows":
            self.logger.debug(
                f"Attempting to start server '{self.server_name}' via Windows process creation (foreground blocking call)."
            )
            try:
                system_windows_proc._windows_start_server(
                    self.server_name, self.server_dir, self.app_config_dir
                )
                self.logger.info(
                    f"Foreground Windows server session for '{self.server_name}' has ended."
                )
                # Check final status from config, as _windows_start_server might have set it.
                final_status = self.get_status_from_config()
                if (
                    final_status == "RUNNING"
                ):  # Should have been set to STOPPED by _windows_start_server on exit
                    self.logger.warning(
                        f"Windows server '{self.server_name}' ended, but status still RUNNING. Setting to STOPPED."
                    )
                    self.set_status_in_config("STOPPED")
                start_successful = (
                    final_status != "ERROR" and final_status != "STARTING"
                )  # Consider it "handled"

            except SystemError as e_mp:  # From pywin32 check in _windows_start_server
                self.logger.error(f"Missing packages for Windows server start: {e_mp}")
                self.set_status_in_config("ERROR")
                raise
            except (
                ServerStartError
            ) as e_start_win:  # Raised by _windows_start_server on failure
                self.logger.error(
                    f"Failed to start server '{self.server_name}' on Windows: {e_start_win}",
                    exc_info=True,
                )
                self.set_status_in_config("ERROR")  # Ensure status is ERROR
                raise
            except Exception as e_unexp_win:  # Other unexpected errors
                self.logger.error(
                    f"Unexpected error during Windows server start for '{self.server_name}': {e_unexp_win}",
                    exc_info=True,
                )
                self.set_status_in_config("ERROR")
                raise ServerStartError(
                    f"Unexpected error starting Windows server '{self.server_name}': {e_unexp_win}"
                ) from e_unexp_win
        else:
            self.logger.error(
                f"Starting server is not supported on this operating system: {self.os_type}"
            )
            self.set_status_in_config("ERROR")
            raise ServerStartError(
                f"Unsupported operating system for start: {self.os_type}"
            )

        if (
            not start_successful and self.os_type != "Windows"
        ):  # Windows start is blocking, so success is implied if no error
            if (
                self.get_status_from_config() != "RUNNING"
            ):  # Check if it somehow became RUNNING
                self.set_status_in_config(
                    "ERROR"
                )  # Fallback to ERROR if not explicitly successful
                raise ServerStartError(
                    f"Server '{self.server_name}' start did not complete successfully."
                )

    def stop(self) -> None:
        """
        Stops the Bedrock server process gracefully.
        Sends a 'stop' command, waits for the process to terminate.
        If graceful stop fails, it may attempt a more forceful termination.

        Raises:
            ServerStopError: If the server fails to stop after all attempts.
            ServerNotRunningError: Though typically handled by an initial check, could occur
                                   if server stops unexpectedly during the process.
            SendCommandError: If sending the initial 'stop' command fails.
            NotImplementedError: If stopping is not supported on the OS (should not happen).
            CommandNotFoundError: If required system commands are missing.
            SystemError: For underlying system issues during process management.
            FileOperationError: For issues related to PID file management.
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

        # Attempt graceful shutdown by sending "stop" command
        try:
            if not hasattr(self, "send_command"):
                self.logger.warning(
                    "send_command method not found on self. Cannot send graceful stop command."
                )
            else:
                self.send_command("stop")  # send_command will handle platform specifics
                self.logger.info(f"Sent 'stop' command to server '{self.server_name}'.")
        except (
            ServerNotRunningError,
            SendCommandError,
            NotImplementedError,
            CommandNotFoundError,
        ) as e_cmd:
            # If server died just before command, or send command failed, log and proceed to check/force stop
            self.logger.warning(
                f"Failed to send 'stop' command to '{self.server_name}': {e_cmd}. Will check process status."
            )
        except Exception as e_unexp_cmd:
            self.logger.error(
                f"Unexpected error sending 'stop' command to '{self.server_name}': {e_unexp_cmd}",
                exc_info=True,
            )

        # Wait for process to terminate
        attempts = 0
        # Use SERVER_STOP_TIMEOUT_SEC from settings
        max_attempts = self.settings.get("SERVER_STOP_TIMEOUT_SEC", 60) // 2
        sleep_interval = 2
        self.logger.info(
            f"Waiting up to {max_attempts * sleep_interval}s for '{self.server_name}' process to terminate..."
        )

        while attempts < max_attempts:
            if not self.is_running():
                self.set_status_in_config("STOPPED")
                self.logger.info(f"Server '{self.server_name}' stopped successfully.")

                # Original Linux screen cleanup logic
                if self.os_type == "Linux":
                    screen_session_name = f"bedrock-{self.server_name}"
                    screen_cmd = shutil.which("screen")
                    if screen_cmd:
                        try:
                            subprocess.run(
                                [screen_cmd, "-S", screen_session_name, "-X", "quit"],
                                check=False,
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                            )
                            self.logger.debug(
                                f"Attempted to quit screen session '{screen_session_name}' for '{self.server_name}'."
                            )
                        except FileNotFoundError:  # Should be caught by shutil.which
                            pass
                        except Exception as e_screen_quit:
                            self.logger.warning(
                                f"Error quitting screen session '{screen_session_name}': {e_screen_quit}"
                            )
                return  # Successfully stopped

            self.logger.debug(
                f"Waiting for '{self.server_name}' to stop... (Attempt {attempts + 1}/{max_attempts})"
            )
            time.sleep(sleep_interval)
            attempts += 1

        # If loop finishes, server hasn't stopped gracefully via command
        self.logger.error(
            f"Server '{self.server_name}' failed to stop after command and wait ({max_attempts * sleep_interval}s)."
        )

        # Additional step: If still running, attempt PID-based termination
        if self.is_running():
            self.logger.info(
                f"Server '{self.server_name}' still running. Attempting forceful PID-based termination."
            )
            pid_file_path = self.get_pid_file_path()  # From BaseMixin
            pid_to_terminate = None
            try:
                # system_process_utils is from bedrock_server_manager.core.system.process
                from bedrock_server_manager.core.system import (
                    process as system_process_utils,
                )

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

                    # Short wait for termination to take effect
                    time.sleep(sleep_interval)
                    if not self.is_running():
                        self.set_status_in_config("STOPPED")
                        self.logger.info(
                            f"Server '{self.server_name}' (PID {pid_to_terminate}) forcefully terminated and confirmed stopped."
                        )
                        return  # Successfully stopped
                    else:
                        self.logger.error(
                            f"Server '{self.server_name}' (PID {pid_to_terminate}) STILL RUNNING after forceful termination attempt."
                        )
                elif pid_to_terminate:
                    self.logger.info(
                        f"PID {pid_to_terminate} from file for '{self.server_name}' not running (stale at force stop stage)."
                    )
                    if not self.is_running():  # Double check main is_running
                        self.set_status_in_config("STOPPED")
                        return
            except FileOperationError as e_pid:
                self.logger.warning(
                    f"PID file error for '{self.server_name}' during force stop: {e_pid}. Cannot perform PID-based stop."
                )
            except (SystemError, ServerStopError) as e_pm:
                self.logger.error(
                    f"Error during forceful termination of PID {pid_to_terminate} for '{self.server_name}': {e_pm}"
                )
            except Exception as e_force:
                self.logger.error(
                    f"Unexpected error during forceful termination of '{self.server_name}': {e_force}",
                    exc_info=True,
                )

        # Final status update if not already set to STOPPED
        if self.get_status_from_config() != "STOPPED":
            self.set_status_in_config("ERROR")  # If it's not stopped, it's an error.

        # If we reach here, server did not stop cleanly after all attempts
        if self.is_running():  # Final check
            raise ServerStopError(
                f"Server '{self.server_name}' failed to stop within timeout and after forceful attempts. Manual intervention may be required."
            )
        else:  # It did stop, but maybe not cleanly (e.g. only after PID kill)
            self.logger.warning(
                f"Server '{self.server_name}' stopped, but possibly not gracefully (e.g., required PID termination). Status set accordingly."
            )
            if (
                self.get_status_from_config() != "STOPPED"
            ):  # Ensure it's STOPPED if truly not running
                self.set_status_in_config("STOPPED")

    def get_process_info(self) -> Optional[Dict[str, Any]]:
        """
        Gets resource usage information (PID, CPU%, Mem MB, Uptime) for the running server process.
        """
        return system_base._get_bedrock_process_info(self.server_name, self.base_dir)
