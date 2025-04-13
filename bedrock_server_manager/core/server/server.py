# bedrock-server-manager/bedrock_server_manager/core/server/server.py
"""
Core module for managing Bedrock server instances.

Provides the `BedrockServer` class to interact with running server processes
(start, stop, status, commands) and standalone functions for installation,
updates, configuration management (server.properties, JSON files), status checks,
and validation.
"""

import subprocess
import os
import logging
import time
import json
import platform
import shutil
from typing import Optional, Any, Dict

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    ServerStartError,
    ServerStopError,
    ServerNotRunningError,
    SendCommandError,
    ServerNotFoundError,
    InvalidServerNameError,
    MissingArgumentError,
    FileOperationError,
    InvalidInputError,
    DirectoryError,
    InstallUpdateError,
    CommandNotFoundError,
    BackupWorldError,
    DownloadExtractError,
    InternetConnectivityError,
)
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
    windows as system_windows,
)
from bedrock_server_manager.core.download import downloader
from bedrock_server_manager.core.server import backup

if platform.system() == "Windows":
    try:
        import win32file
        import pywintypes
        import win32pipe

        WINDOWS_IMPORTS_AVAILABLE = True
    except ImportError:
        WINDOWS_IMPORTS_AVAILABLE = False
        # Log warning handled within the relevant function if needed
else:
    WINDOWS_IMPORTS_AVAILABLE = False


logger = logging.getLogger("bedrock_server_manager")


class BedrockServer:
    """
    Represents and manages a specific Bedrock server instance.

    Handles starting, stopping, checking status, getting process information
    (PID, CPU, memory, uptime), and sending commands to the running server process.

    Attributes:
        server_name (str): The unique name identifier for the server.
        server_dir (str): The base directory path for the server installation.
        server_path (str): The full path to the server executable.
        process: Platform-specific process handle (e.g., Popen object on Windows).
                 May be None if not started by this instance or not applicable.
        status (str): An internal indicator of the server's perceived state
                      ("STOPPED", "STARTING", "RUNNING", "STOPPING", "ERROR").
                      Note: For actual running status, use `is_running()`.
    """

    def __init__(self, server_name: str, server_path: Optional[str] = None):
        """
        Initializes the BedrockServer object.

        Args:
            server_name: The name of the server.
            server_path: Optional. The full path to the server executable.
                         If None, it's inferred based on OS and server_dir.

        Raises:
            MissingArgumentError: If `server_name` is empty.
            FileOperationError: If BASE_DIR setting is missing.
            ServerNotFoundError: If the server executable cannot be found at the
                                 determined `server_path`.
        """
        if not server_name:
            raise MissingArgumentError(
                "Server name cannot be empty for BedrockServer initialization."
            )

        logger.debug(f"Initializing BedrockServer instance for '{server_name}'")
        self.server_name = server_name

        base_dir = settings.get("BASE_DIR")
        if not base_dir:
            raise FileOperationError(
                "BASE_DIR setting is missing or empty in configuration."
            )
        self.server_dir = os.path.join(base_dir, self.server_name)

        if server_path:
            self.server_path = server_path
            logger.debug(f"Using provided server executable path: {self.server_path}")
        else:
            # Determine the executable name based on the platform
            exe_name = (
                "bedrock_server.exe"
                if platform.system() == "Windows"
                else "bedrock_server"
            )
            self.server_path = os.path.join(self.server_dir, exe_name)
            logger.debug(f"Using default server executable path: {self.server_path}")

        # Validate existence immediately on init
        if not os.path.isfile(self.server_path):
            error_msg = f"Server executable not found at path: {self.server_path}"
            logger.error(error_msg)
            raise ServerNotFoundError(error_msg)

        self.process = None  # Platform specific process object (e.g., subprocess.Popen)
        self.status = "STOPPED"  # Internal status tracking
        logger.debug(
            f"BedrockServer '{self.server_name}' initialized. Executable: {self.server_path}"
        )

    def is_running(self) -> bool:
        """Checks if the server process associated with this name is currently running."""
        logger.debug(f"Checking running status for server '{self.server_name}'")
        # Relies on the system-specific implementation
        is_running = system_base.is_server_running(
            self.server_name, settings.get("BASE_DIR")
        )
        logger.debug(f"Server '{self.server_name}' is_running result: {is_running}")
        return is_running

    def get_pid(self) -> Optional[int]:
        """Gets the process ID (PID) of the running server, if found."""
        logger.debug(f"Attempting to get PID for server '{self.server_name}'")
        server_info = system_base._get_bedrock_process_info(
            self.server_name, settings.get("BASE_DIR")
        )
        pid = server_info.get("pid") if server_info else None
        logger.debug(f"Server '{self.server_name}' PID: {pid}")
        return pid

    def get_cpu_usage(self) -> Optional[float]:
        """Gets the current CPU usage percentage of the server process, if running."""
        logger.debug(f"Attempting to get CPU usage for server '{self.server_name}'")
        server_info = system_base._get_bedrock_process_info(
            self.server_name, settings.get("BASE_DIR")
        )
        cpu_usage = server_info.get("cpu_percent") if server_info else None
        logger.debug(f"Server '{self.server_name}' CPU usage: {cpu_usage}%")
        return cpu_usage

    def get_memory_usage(self) -> Optional[float]:
        """Gets the current memory usage (in MB) of the server process, if running."""
        logger.debug(f"Attempting to get memory usage for server '{self.server_name}'")
        server_info = system_base._get_bedrock_process_info(
            self.server_name, settings.get("BASE_DIR")
        )
        memory_usage = server_info.get("memory_mb") if server_info else None
        logger.debug(f"Server '{self.server_name}' memory usage: {memory_usage} MB")
        return memory_usage

    def get_uptime(self) -> Optional[float]:
        """Gets the server process uptime in seconds, if running."""
        logger.debug(f"Attempting to get uptime for server '{self.server_name}'")
        server_info = system_base._get_bedrock_process_info(
            self.server_name, settings.get("BASE_DIR")
        )
        uptime = server_info.get("uptime") if server_info else None
        logger.debug(f"Server '{self.server_name}' uptime: {uptime} seconds")
        return uptime

    def send_command(self, command: str) -> None:
        """
        Sends a command string to the running server process.

        Implementation is platform-specific (screen on Linux, named pipes on Windows).

        Args:
            command: The command string to send to the server console.

        Raises:
            MissingArgumentError: If `command` is empty.
            ServerNotRunningError: If the server process cannot be found or communicated with.
            SendCommandError: If there's a platform-specific error sending the command
                              (e.g., pipe errors, screen errors).
            CommandNotFoundError: If a required external command (like 'screen') is not found.
            NotImplementedError: If the current OS is not supported.
        """
        if not command:
            raise MissingArgumentError("Command cannot be empty.")

        # Check if running *before* attempting platform-specific methods
        if not self.is_running():
            # Use is_running() for consistency, though _get_bedrock_process_info is also checked later
            logger.error(
                f"Cannot send command to server '{self.server_name}': Server is not running."
            )
            raise ServerNotRunningError(f"Server '{self.server_name}' is not running.")

        logger.info(f"Sending command '{command}' to server '{self.server_name}'...")

        os_name = platform.system()
        if os_name == "Linux":
            screen_cmd_path = shutil.which("screen")
            if not screen_cmd_path:
                logger.error(
                    "'screen' command not found. Cannot send command. Is 'screen' installed and in PATH?"
                )
                raise CommandNotFoundError(
                    "screen", message="'screen' command not found. Is it installed?"
                )

            try:
                # Use screen -S <session_name> -X stuff "command\n"
                screen_session_name = f"bedrock-{self.server_name}"
                # Ensure command ends with a newline for execution in screen
                command_with_newline = (
                    command if command.endswith("\n") else command + "\n"
                )
                process = subprocess.run(
                    [
                        screen_cmd_path,
                        "-S",
                        screen_session_name,
                        "-X",
                        "stuff",
                        command_with_newline,
                    ],
                    check=True,  # Raise exception on non-zero exit code
                    capture_output=True,  # Capture stdout/stderr
                    text=True,  # Decode output as text
                )
                logger.debug(
                    f"'screen' command executed successfully for server '{self.server_name}'. stdout: {process.stdout}, stderr: {process.stderr}"
                )
                logger.info(
                    f"Sent command '{command}' to server '{self.server_name}' via screen."
                )
            except subprocess.CalledProcessError as e:
                # Common error: screen session doesn't exist (server not running in expected screen)
                if "No screen session found" in e.stderr:
                    logger.error(
                        f"Failed to send command: Screen session '{screen_session_name}' not found. Is the server running correctly in screen?"
                    )
                    raise ServerNotRunningError(
                        f"Screen session '{screen_session_name}' not found."
                    ) from e
                else:
                    logger.error(
                        f"Failed to send command via screen: {e}. stderr: {e.stderr}",
                        exc_info=True,
                    )
                    raise SendCommandError(
                        f"Failed to send command via screen: {e}"
                    ) from e
            except (
                FileNotFoundError
            ):  # Should be caught by shutil.which check, but safeguard
                logger.error("'screen' command not found unexpectedly.")
                raise CommandNotFoundError(
                    "screen", message="'screen' command not found."
                ) from None

        elif os_name == "Windows":
            if not WINDOWS_IMPORTS_AVAILABLE:
                logger.error(
                    "Cannot send command on Windows: Required 'pywin32' module is not installed."
                )
                raise SendCommandError(
                    "Cannot send command on Windows: 'pywin32' module not found."
                )
            pass

            pipe_name = rf"\\.\pipe\BedrockServer{self.server_name}"
            handle = win32file.INVALID_HANDLE_VALUE

            try:
                logger.debug(f"Attempting to connect to named pipe: {pipe_name}")
                handle = win32file.CreateFile(
                    pipe_name,
                    win32file.GENERIC_WRITE,  # Access rights
                    0,  # Share mode (0 for exclusive access)
                    None,  # Security attributes
                    win32file.OPEN_EXISTING,  # Open only if exists
                    0,  # Flags and attributes
                    None,  # Template file handle
                )

                # Check if CreateFile failed immediately
                if handle == win32file.INVALID_HANDLE_VALUE:
                    # This usually means the pipe doesn't exist (server not running or pipe not created)
                    logger.error(
                        f"Could not open named pipe '{pipe_name}'. Server might not be running or pipe setup failed. Error code: {pywintypes.GetLastError()}"
                    )
                    raise ServerNotRunningError(
                        f"Could not connect to server pipe '{pipe_name}'."
                    )

                # Set pipe to message mode
                win32pipe.SetNamedPipeHandleState(
                    handle, win32pipe.PIPE_READMODE_MESSAGE, None, None
                )

                # Write command (ensure CRLF line ending)
                command_bytes = (command + "\r\n").encode("utf-8")  # Use UTF-8 encoding
                win32file.WriteFile(handle, command_bytes)
                logger.info(
                    f"Sent command '{command}' to server '{self.server_name}' via named pipe."
                )

            except pywintypes.error as e:
                # Handle specific Windows errors
                win_error_code = e.winerror
                logger.error(
                    f"Windows error sending command via pipe '{pipe_name}': Code {win_error_code} - {e}",
                    exc_info=True,
                )
                if win_error_code == 2:  # ERROR_FILE_NOT_FOUND
                    raise ServerNotRunningError(
                        f"Pipe '{pipe_name}' does not exist. Server likely not running."
                    ) from e
                elif win_error_code == 231:  # ERROR_PIPE_BUSY
                    raise SendCommandError(
                        "All pipe instances are busy. Try again later."
                    ) from e
                elif win_error_code == 109:  # ERROR_BROKEN_PIPE
                    raise SendCommandError(
                        "Pipe connection broken (server may have closed it)."
                    ) from e
                else:
                    raise SendCommandError(f"Windows error sending command: {e}") from e
            except Exception as e:  # Catch other potential errors
                logger.error(
                    f"Unexpected error sending command via pipe '{pipe_name}': {e}",
                    exc_info=True,
                )
                raise SendCommandError(f"Unexpected error sending command: {e}") from e
            finally:
                # Always ensure the handle is closed if it was opened
                if handle != win32file.INVALID_HANDLE_VALUE:
                    try:
                        win32file.CloseHandle(handle)
                        logger.debug(f"Closed named pipe handle for '{pipe_name}'.")
                    except pywintypes.error as close_err:
                        # Log error during close but don't mask original error if one occurred
                        logger.warning(
                            f"Error closing pipe handle for '{pipe_name}': {close_err}",
                            exc_info=True,
                        )
        else:
            logger.error(
                f"Sending commands is not supported on this operating system: {os_name}"
            )
            raise NotImplementedError(f"Sending commands not supported on {os_name}")

    def start(self) -> None:
        """
        Starts the Bedrock server process.

        Uses systemd on Linux (if available, falling back to screen) or starts
        directly on Windows. Manages internal status and waits for confirmation.

        Raises:
            ServerStartError: If the server is already running, if the OS is unsupported,
                              or if the server fails to start within the timeout.
            CommandNotFoundError: If required external commands (systemctl, screen) are missing.
        """
        if self.is_running():
            logger.warning(
                f"Attempted to start server '{self.server_name}' but it is already running."
            )
            # Decide if this should be an error or just a warning. Let's make it an error.
            raise ServerStartError(f"Server '{self.server_name}' is already running.")

        self.status = "STARTING"
        manage_server_config(
            self.server_name, "status", "write", self.status
        )  # Update persistent status
        logger.info(f"Attempting to start server '{self.server_name}'...")

        os_name = platform.system()
        start_successful_method = None

        if os_name == "Linux":
            # Try systemd first
            systemctl_cmd_path = shutil.which("systemctl")
            service_name = f"bedrock-{self.server_name}"
            if systemctl_cmd_path:
                logger.debug("Attempting to start server via systemd user service.")
                try:
                    # Check if service exists and is enabled before starting? Optional.
                    process = subprocess.run(
                        [systemctl_cmd_path, "--user", "start", service_name],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    logger.info(
                        f"Successfully initiated start for systemd service '{service_name}'."
                    )
                    start_successful_method = "systemd"
                except (
                    FileNotFoundError
                ):  # Should be caught by shutil.which, but safeguard
                    logger.error("'systemctl' command not found unexpectedly.")
                    start_successful_method = None  # Ensure it proceeds to fallback
                except subprocess.CalledProcessError as e:
                    logger.warning(
                        f"Starting via systemctl failed (maybe service not found/enabled?): {e}. stderr: {e.stderr}",
                        exc_info=True,
                    )
                    # Fall through to screen method
            else:
                logger.warning(
                    "'systemctl' command not found. Cannot use systemd method."
                )

            # Fallback to screen if systemd didn't work or wasn't available
            if start_successful_method != "systemd":
                screen_cmd_path = shutil.which("screen")
                if screen_cmd_path:
                    logger.info("Falling back to starting server via 'screen'.")
                    try:
                        system_linux._systemd_start_server(
                            self.server_name, self.server_dir
                        )
                        start_successful_method = "screen"
                    except (CommandNotFoundError, ServerStartError) as e:
                        logger.error(
                            f"Failed to start server using screen method: {e}",
                            exc_info=True,
                        )
                        # Let the final timeout handle the overall failure
                    except Exception as e:
                        logger.error(
                            f"Unexpected error starting server via screen method: {e}",
                            exc_info=True,
                        )
                else:
                    logger.error("'screen' command not found. Cannot start server.")
                    manage_server_config(self.server_name, "status", "write", "ERROR")
                    raise CommandNotFoundError(
                        "screen",
                        message="'screen' command not found. Cannot start server.",
                    )

        elif os_name == "Windows":
            logger.debug("Attempting to start server via Windows process creation.")
            try:
                # This function should return the Popen object or raise ServerStartError
                self.process = system_windows._windows_start_server(
                    self.server_name, self.server_dir
                )
                start_successful_method = "windows_process"
                logger.info(
                    f"Initiated server start process on Windows for '{self.server_name}'."
                )
            except ServerStartError as e:
                logger.error(
                    f"Failed to start server process on Windows: {e}", exc_info=True
                )
                # Let the final timeout handle the overall failure
            except Exception as e:
                logger.error(
                    f"Unexpected error starting server process on Windows: {e}",
                    exc_info=True,
                )

        else:
            logger.error(
                f"Starting server is not supported on this operating system: {os_name}"
            )
            manage_server_config(self.server_name, "status", "write", "ERROR")
            raise ServerStartError(f"Unsupported operating system: {os_name}")

        # Wait for confirmation that the server is actually running
        attempts = 0
        # Make max_attempts configurable?
        max_attempts = (
            settings.get("SERVER_START_TIMEOUT_SEC", 60) // 2
        )  # Use setting, default 60s, check every 2s
        sleep_interval = 2

        logger.info(
            f"Waiting up to {max_attempts * sleep_interval} seconds for server '{self.server_name}' to start..."
        )
        while attempts < max_attempts:
            if self.is_running():
                self.status = "RUNNING"
                manage_server_config(self.server_name, "status", "write", self.status)
                logger.info(f"Server '{self.server_name}' started successfully.")
                return  # Success!
            logger.debug(
                f"Waiting for server '{self.server_name}' to start... (Check {attempts + 1}/{max_attempts})"
            )
            time.sleep(sleep_interval)
            attempts += 1

        # If loop finishes without returning, the server failed to start
        self.status = "ERROR"
        manage_server_config(self.server_name, "status", "write", self.status)
        logger.error(
            f"Server '{self.server_name}' failed to confirm running status within the timeout ({max_attempts * sleep_interval} seconds)."
        )
        raise ServerStartError(
            f"Server '{self.server_name}' failed to start within the timeout."
        )

    def stop(self) -> None:
        """
        Stops the Bedrock server process gracefully.

        Sends a 'stop' command, waits for the process to terminate.
        Uses systemd on Linux (if available/managed), otherwise uses screen/Windows methods.

        Raises:
            ServerStopError: If the server is not running, if the OS is unsupported,
                             or if the server fails to stop within the timeout.
            SendCommandError: If sending the initial 'stop' command fails.
            CommandNotFoundError: If required external commands are missing.
        """
        if not self.is_running():
            logger.info(
                f"Attempted to stop server '{self.server_name}', but it is not currently running."
            )
            # Update status just in case config was out of sync
            if manage_server_config(self.server_name, "status", "read") != "STOPPED":
                manage_server_config(self.server_name, "status", "write", "STOPPED")
            self.status = "STOPPED"
            return  # Nothing to do

        self.status = "STOPPING"
        manage_server_config(self.server_name, "status", "write", self.status)
        logger.info(f"Attempting to stop server '{self.server_name}'...")

        os_name = platform.system()
        stop_initiated = False

        if os_name == "Linux":
            # Try systemd first if it seems managed
            systemctl_cmd_path = shutil.which("systemctl")
            service_name = f"bedrock-{self.server_name}"
            # Basic check: does the service file exist? A better check might involve `systemctl is-active` etc.
            service_file_path = os.path.join(
                os.path.expanduser("~/.config/systemd/user/"), f"{service_name}.service"
            )

            if systemctl_cmd_path and os.path.exists(service_file_path):
                logger.debug("Attempting to stop server via systemd user service.")
                try:
                    process = subprocess.run(
                        [systemctl_cmd_path, "--user", "stop", service_name],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    logger.info(
                        f"Successfully initiated stop for systemd service '{service_name}'."
                    )
                    stop_initiated = True
                except (
                    FileNotFoundError
                ):  # Should be caught by shutil.which, but safeguard
                    logger.error("'systemctl' command not found unexpectedly.")
                except subprocess.CalledProcessError as e:
                    logger.warning(
                        f"Stopping via systemctl failed (maybe service wasn't running under systemd?): {e}. stderr: {e.stderr}",
                        exc_info=True,
                    )
                    # Fall through to screen/command method if systemd fails
            else:
                logger.debug(
                    "Systemctl not found or service file doesn't exist. Will try sending 'stop' command directly."
                )

            # If systemd didn't work or wasn't used, try sending 'stop' command
            if not stop_initiated:
                try:
                    logger.info("Sending 'stop' command to server process...")
                    self.send_command("stop")  # Use the instance method
                    stop_initiated = True  # Command sent, now wait
                except (
                    SendCommandError,
                    ServerNotRunningError,
                    CommandNotFoundError,
                ) as e:
                    logger.error(
                        f"Failed to send 'stop' command to server '{self.server_name}': {e}. Will attempt process termination.",
                        exc_info=True,
                    )
                    # Proceed to wait loop anyway, maybe it's shutting down due to other reasons
                except Exception as e:
                    logger.error(
                        f"Unexpected error sending 'stop' command to server '{self.server_name}': {e}. Will attempt process termination.",
                        exc_info=True,
                    )

        elif os_name == "Windows":
            system_windows._windows_stop_server(self.server_name, self.server_dir)
        else:
            logger.error(
                f"Stopping server is not supported on this operating system: {os_name}"
            )
            manage_server_config(
                self.server_name, "status", "write", "ERROR"
            )  # Mark as error state
            raise ServerStopError(f"Unsupported operating system: {os_name}")

        # Wait for the server process to actually exit
        attempts = 0
        max_attempts = (
            settings.get("SERVER_STOP_TIMEOUT_SEC", 60) // 2
        )  # Use setting, default 60s, check every 2s
        sleep_interval = 2
        logger.info(
            f"Waiting up to {max_attempts * sleep_interval} seconds for server '{self.server_name}' process to terminate..."
        )

        while attempts < max_attempts:
            if not self.is_running():
                self.status = "STOPPED"
                manage_server_config(self.server_name, "status", "write", self.status)
                logger.info(f"Server '{self.server_name}' stopped successfully.")
                # Clean up screen session if it exists and wasn't managed by systemd
                if (
                    os_name == "Linux" and not stop_initiated
                ):  # Or check if screen was used specifically
                    screen_session_name = f"bedrock-{self.server_name}"
                    try:
                        subprocess.run(
                            ["screen", "-S", screen_session_name, "-X", "quit"],
                            check=False,
                            capture_output=True,
                        )
                        logger.debug(
                            f"Attempted to quit potentially lingering screen session '{screen_session_name}'."
                        )
                    except FileNotFoundError:
                        pass  # Screen not found, already handled
                return  # Success!

            logger.debug(
                f"Waiting for server '{self.server_name}' to stop... (Check {attempts + 1}/{max_attempts})"
            )
            time.sleep(sleep_interval)
            attempts += 1

        # If loop finishes, server didn't stop gracefully
        logger.error(
            f"Server '{self.server_name}' failed to stop within the timeout ({max_attempts * sleep_interval} seconds). Process might still be running."
        )
        self.status = "ERROR"  # Mark as error state
        manage_server_config(self.server_name, "status", "write", self.status)
        raise ServerStopError(
            f"Server '{self.server_name}' failed to stop within the timeout. Manual intervention may be required."
        )


# --- Standalone Functions ---


def get_world_name(server_name: str, base_dir: str) -> str:
    """
    Reads the world directory name from the server.properties file.

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server's folder.

    Returns:
        The value of the 'level-name' property.

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        FileOperationError: If server.properties cannot be found, read, or if
                            the 'level-name' property is missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    server_properties_path = os.path.join(base_dir, server_name, "server.properties")
    logger.debug(
        f"Reading world name for server '{server_name}' from: {server_properties_path}"
    )

    if not os.path.isfile(server_properties_path):
        error_msg = f"server.properties file not found at: {server_properties_path}"
        logger.error(error_msg)
        raise FileOperationError(error_msg)

    try:
        with open(server_properties_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("level-name="):
                    # Split only on the first '='
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        world_name = parts[1].strip()
                        if world_name:  # Ensure value is not empty
                            logger.debug(
                                f"Found world name (level-name): '{world_name}'"
                            )
                            return world_name
                        else:
                            logger.error(
                                f"'level-name' property found but has empty value in {server_properties_path}"
                            )
                            raise FileOperationError(
                                f"'level-name' has empty value in {server_properties_path}"
                            )
                    else:
                        # Line starts with "level-name=" but has no value? Unlikely but handle.
                        logger.error(
                            f"Malformed 'level-name' line found in {server_properties_path}: {line}"
                        )
                        raise FileOperationError(
                            f"Malformed 'level-name' line in {server_properties_path}"
                        )

    except OSError as e:
        logger.error(
            f"Failed to read server.properties file '{server_properties_path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(f"Failed to read server.properties: {e}") from e
    except Exception as e:
        logger.error(
            f"Unexpected error reading server.properties '{server_properties_path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Unexpected error reading server.properties: {e}"
        ) from e

    # If loop completes without finding the property
    logger.error(f"'level-name' property not found in {server_properties_path}")
    raise FileOperationError(f"'level-name' not found in {server_properties_path}")


def validate_server(server_name: str, base_dir: str) -> bool:
    """
    Validates if a server installation exists and seems minimally correct.

    Checks for the existence of the server executable within the expected directory.

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server's folder.

    Returns:
        True if the server executable exists.

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        ServerNotFoundError: If the server directory or the executable file within it
                             does not exist.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    server_dir = os.path.join(base_dir, server_name)
    logger.debug(f"Validating server '{server_name}' in directory: {server_dir}")

    if not os.path.isdir(server_dir):
        error_msg = f"Server directory not found: {server_dir}"
        logger.error(error_msg)
        raise ServerNotFoundError(error_msg)  # Treat missing dir as server not found

    # Determine expected executable name based on OS
    exe_name = (
        "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
    )
    exe_path = os.path.join(server_dir, exe_name)

    if not os.path.isfile(exe_path):
        error_msg = (
            f"Server executable '{exe_name}' not found in directory: {server_dir}"
        )
        logger.error(error_msg)
        raise ServerNotFoundError(error_msg)

    logger.debug(f"Server '{server_name}' validation successful (executable found).")
    return True


def manage_server_config(
    server_name: str,
    key: str,
    operation: str,
    value: Any = None,
    config_dir: Optional[str] = None,
) -> Optional[Any]:
    """
    Reads or writes a specific key-value pair in a server's JSON config file.

    The config file is located at '{config_dir}/{server_name}/{server_name}_config.json'.

    Args:
        server_name: The name of the server.
        key: The configuration key (string) to read or write.
        operation: The action to perform ("read" or "write").
        value: The value to write (required for "write" operation). Can be any
               JSON-serializable type. Defaults to None.
        config_dir: Optional. The base directory containing server config folders.
                    Defaults to `settings._config_dir` if None.

    Returns:
        The value read for the key if `operation` is "read", otherwise None.
        Returns None if the key doesn't exist during a "read".

    Raises:
        MissingArgumentError: If required arguments are empty (`server_name`, `key`,
                            `operation`), or if `value` is missing for "write".
        InvalidServerNameError: If `server_name` is invalid (currently just checks empty).
        InvalidInputError: If `operation` is not "read" or "write".
        FileOperationError: If creating directories fails, or reading/writing the
                            JSON config file fails (OS errors, JSON errors).
    """
    # Use default config dir from settings if not provided
    effective_config_dir = (
        config_dir if config_dir is not None else getattr(settings, "_config_dir", None)
    )
    if not effective_config_dir:
        # Handle case where settings object might not have _config_dir yet or it's None/empty
        raise FileOperationError(
            "Base configuration directory is not set or available."
        )

    # Basic argument validation
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not key:
        raise MissingArgumentError("Config key cannot be empty.")
    if not operation:
        raise MissingArgumentError("Operation ('read' or 'write') cannot be empty.")
    operation = operation.lower()  # Normalize operation

    server_config_subdir = os.path.join(effective_config_dir, server_name)
    config_file_path = os.path.join(server_config_subdir, f"{server_name}_config.json")

    logger.debug(
        f"Managing config for server '{server_name}': Key='{key}', Op='{operation}', File='{config_file_path}'"
    )

    # Ensure the subdirectory for the server's config exists
    try:
        os.makedirs(server_config_subdir, exist_ok=True)
    except OSError as e:
        logger.error(
            f"Failed to create server config subdirectory '{server_config_subdir}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to create directory '{server_config_subdir}': {e}"
        ) from e

    # --- Load or initialize config data ---
    current_config: Dict[str, Any] = {}
    try:
        if os.path.exists(config_file_path):
            with open(config_file_path, "r", encoding="utf-8") as f:
                try:
                    content = f.read()
                    if content.strip():  # Check if file is not empty
                        current_config = json.loads(content)
                        if not isinstance(current_config, dict):
                            logger.warning(
                                f"Config file '{config_file_path}' does not contain a JSON object. Will be overwritten on write."
                            )
                            current_config = {}  # Treat as empty if not a dict
                        else:
                            logger.debug(f"Loaded existing config: {current_config}")
                    else:
                        logger.debug(
                            f"Config file '{config_file_path}' exists but is empty. Initializing as empty dict."
                        )
                        current_config = {}
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Failed to parse JSON from config file '{config_file_path}'. Will be overwritten on write. Error: {e}",
                        exc_info=True,
                    )
                    current_config = {}  # Treat as empty if invalid JSON
        else:
            logger.debug(
                f"Config file '{config_file_path}' not found. Will create on write, empty for read."
            )
            current_config = {}  # Initialize empty if file doesn't exist

    except OSError as e:
        logger.error(
            f"Failed to read config file '{config_file_path}': {e}", exc_info=True
        )
        raise FileOperationError(
            f"Failed to read config file '{config_file_path}': {e}"
        ) from e
    except Exception as e:  # Catch other unexpected errors during load
        logger.error(
            f"Unexpected error loading config file '{config_file_path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Unexpected error loading config file '{config_file_path}': {e}"
        ) from e

    # --- Perform Operation ---
    if operation == "read":
        read_value = current_config.get(key)  # Safely gets value or None
        logger.debug(f"Read operation: Key='{key}', Value='{read_value}'")
        return read_value
    elif operation == "write":
        if value is None:
            logger.warning(
                f"Write operation called for key '{key}' but value is None. Writing None to config."
            )
            raise MissingArgumentError("Value is required for 'write' operation.")

        logger.debug(f"Write operation: Key='{key}', New Value='{value}'")
        current_config[key] = value

        try:
            # Write the entire updated dictionary back
            with open(config_file_path, "w", encoding="utf-8") as f:
                json.dump(
                    current_config, f, indent=4, sort_keys=True
                )  # Pretty print with sorted keys
            logger.debug(f"Successfully wrote updated config to '{config_file_path}'.")
            return None  # Write operation returns None
        except OSError as e:
            logger.error(
                f"Failed to write updated config to '{config_file_path}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to write config file '{config_file_path}': {e}"
            ) from e
        except TypeError as e:  # Catch non-serializable data errors
            logger.error(
                f"Failed to serialize config data for writing: {e}", exc_info=True
            )
            raise FileOperationError(
                f"Config data for key '{key}' is not JSON serializable."
            ) from e

    else:
        # Invalid operation string
        logger.error(
            f"Invalid operation specified: '{operation}'. Must be 'read' or 'write'."
        )
        raise InvalidInputError(
            f"Invalid operation: '{operation}'. Must be 'read' or 'write'."
        )


def get_installed_version(server_name: str, config_dir: Optional[str] = None) -> str:
    """
    Retrieves the installed version string for a server from its config file.

    Args:
        server_name: The name of the server.
        config_dir: Optional. The base directory containing server config folders.
                    Defaults to `settings._config_dir` if None.

    Returns:
        The installed version string, or "UNKNOWN" if the version key is not found
        or the config file cannot be read.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If reading the config fails for reasons other than missing key.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.debug(
        f"Getting installed version for server '{server_name}' from its config."
    )

    try:
        # Use manage_server_config to read the specific key
        installed_version = manage_server_config(
            server_name=server_name,
            key="installed_version",
            operation="read",
            config_dir=config_dir,
        )

        if installed_version is None:
            logger.warning(
                f"Key 'installed_version' not found in config for server '{server_name}'. Returning 'UNKNOWN'."
            )
            return "UNKNOWN"

        # Ensure it's a string before returning
        if not isinstance(installed_version, str):
            logger.warning(
                f"Value for 'installed_version' in config for '{server_name}' is not a string ({type(installed_version)}). Returning 'UNKNOWN'."
            )
            return "UNKNOWN"

        logger.debug(
            f"Retrieved installed version for '{server_name}': '{installed_version}'"
        )
        return installed_version

    except FileOperationError as e:
        # Log error but return UNKNOWN as per original behavior if reading fails non-critically
        logger.error(
            f"Could not read installed version for server '{server_name}' due to config file error: {e}",
            exc_info=True,
        )
        return "UNKNOWN"
    except Exception as e:  # Catch other unexpected errors
        logger.error(
            f"Unexpected error retrieving installed version for '{server_name}': {e}",
            exc_info=True,
        )
        return "UNKNOWN"


def check_server_status(
    server_name: str,
    base_dir: str,
    max_attempts: int = 10,
    chunk_size_bytes: int = 8192,
    max_scan_bytes: int = 1 * 1024 * 1024,
) -> str:
    """
    Determines the server's status by reading the end of its log file.

    Efficiently reads the log file ('server_output.txt') backwards in chunks
    to find the most recent status indicator ("Server started.", "Quit correctly", etc.).

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server's folder.
        max_attempts: Max attempts to wait for the log file to appear (0.5s sleep each).
        chunk_size_bytes: How many bytes to read from the end of the file at a time.
        max_scan_bytes: Maximum total bytes to scan backwards from the end of the file.

    Returns:
        The determined server status string ("RUNNING", "STARTING", "RESTARTING",
        "STOPPING", "STOPPED", or "UNKNOWN").

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        FileOperationError: If reading the log file fails due to OS errors.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    log_file_path = os.path.join(base_dir, server_name, "server_output.txt")
    status = "UNKNOWN"  # Default status

    logger.info(
        f"Checking server status for '{server_name}' by reading log file: {log_file_path}"
    )

    # --- Wait for log file existence ---
    attempt = 0
    sleep_interval = 0.5
    while not os.path.exists(log_file_path) and attempt < max_attempts:
        logger.debug(
            f"Log file '{log_file_path}' not found. Waiting... (Attempt {attempt + 1}/{max_attempts})"
        )
        time.sleep(sleep_interval)
        attempt += 1

    if not os.path.exists(log_file_path):
        logger.warning(
            f"Log file '{log_file_path}' did not appear within {max_attempts * sleep_interval} seconds."
        )
        # If log doesn't exist, maybe server hasn't started or was deleted?
        # Return UNKNOWN based purely on log check.
        return "UNKNOWN"

    # --- Read log file efficiently from the end ---
    try:
        with open(log_file_path, "rb") as f:  # Open in binary mode for seeking
            f.seek(0, os.SEEK_END)  # Go to the end of the file
            file_size = f.tell()
            bytes_scanned = 0
            buffer = b""

            # Read backwards in chunks
            while bytes_scanned < max_scan_bytes and bytes_scanned < file_size:
                read_size = min(chunk_size_bytes, file_size - bytes_scanned)
                f.seek(file_size - bytes_scanned - read_size)
                chunk = f.read(read_size)
                bytes_scanned += read_size
                buffer = chunk + buffer  # Prepend chunk to buffer

                # Process lines in the buffer (handle partial lines across chunks)
                # Decode using utf-8, ignore errors
                lines = buffer.decode("utf-8", errors="ignore").splitlines()

                # Process lines from most recent (end of buffer) first
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue  # Skip empty lines

                    # Check for status indicators (most recent match wins)
                    if "Server started." in line:
                        status = "RUNNING"
                        break
                    elif (
                        "Starting Server" in line
                    ):  # Check if this is still relevant/accurate
                        status = "STARTING"
                        break
                    # elif "Restarting server in 10 seconds" in line:
                    #     status = "RESTARTING"
                    #     break
                    # elif "Shutting down server in 10 seconds" in line:
                    #     status = "STOPPING"
                    #     break
                    elif "Quit correctly." in line:  # Check exact wording
                        status = "STOPPED"
                        break
                    # Add more specific start/stop messages if available

                if status != "UNKNOWN":
                    logger.debug(f"Status '{status}' determined from log content.")
                    break  # Found status, exit reading loop

                # If buffer starts with partial line, keep it for next iteration
                if (
                    not buffer.startswith(b"\n")
                    and not buffer.startswith(b"\r")
                    and bytes_scanned < file_size
                ):
                    # Find last newline to determine partial line start
                    last_newline = max(buffer.rfind(b"\n"), buffer.rfind(b"\r"))
                    if last_newline != -1:
                        buffer = buffer[: last_newline + 1]

            if status == "UNKNOWN":
                logger.warning(
                    f"Could not determine server status after scanning last {bytes_scanned} bytes of log file '{log_file_path}'."
                )

    except OSError as e:
        logger.error(
            f"Failed to read server log file '{log_file_path}': {e}", exc_info=True
        )
        raise FileOperationError(
            f"Failed to read server log '{log_file_path}': {e}"
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error processing log file '{log_file_path}': {e}",
            exc_info=True,
        )
        # Return UNKNOWN in case of unexpected processing errors
        return "UNKNOWN"

    logger.info(
        f"Determined status for server '{server_name}': {status} (from log check)"
    )
    return status


def get_server_status_from_config(
    server_name: str, config_dir: Optional[str] = None
) -> str:
    """
    Retrieves the last known server status stored in the server's config file.

    Args:
        server_name: The name of the server.
        config_dir: Optional. The base directory containing server config folders.
                    Defaults to `settings._config_dir` if None.

    Returns:
        The status string stored in the config file ("RUNNING", "STOPPED", etc.),
        or "UNKNOWN" if the status key is not found or the config cannot be read.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If reading the config fails for reasons other than missing key.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.debug(
        f"Getting last known status for server '{server_name}' from its config."
    )

    try:
        status = manage_server_config(
            server_name=server_name,
            key="status",
            operation="read",
            config_dir=config_dir,
        )

        if status is None:
            logger.warning(
                f"Key 'status' not found in config for server '{server_name}'. Returning 'UNKNOWN'."
            )
            return "UNKNOWN"

        if not isinstance(status, str):
            logger.warning(
                f"Value for 'status' in config for '{server_name}' is not a string ({type(status)}). Returning 'UNKNOWN'."
            )
            return "UNKNOWN"

        logger.debug(f"Retrieved status from config for '{server_name}': '{status}'")
        return status

    except FileOperationError as e:
        logger.error(
            f"Could not read status for server '{server_name}' due to config file error: {e}",
            exc_info=True,
        )
        return "UNKNOWN"
    except Exception as e:
        logger.error(
            f"Unexpected error retrieving status for '{server_name}': {e}",
            exc_info=True,
        )
        return "UNKNOWN"


def update_server_status_in_config(
    server_name: str, base_dir: str, config_dir: Optional[str] = None
) -> None:
    """
    Checks the server's current status via log file and updates the server's config file.

    Compares the status found in the log file with the last known status in the config.
    Writes the new status to the config file if it has changed or is informative.

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server's folder (for log file path).
        config_dir: Optional. The base directory containing server config folders.
                    Defaults to `settings._config_dir` if None.

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If reading the log or reading/writing the config file fails.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    logger.debug(
        f"Updating status in config for server '{server_name}' based on log check."
    )

    try:
        # Get status by checking the log file
        checked_status = check_server_status(server_name, base_dir)

        # Get the last status recorded in the config
        current_config_status = get_server_status_from_config(server_name, config_dir)

        logger.debug(
            f"Server '{server_name}': Status from log='{checked_status}', Status from config='{current_config_status}'"
        )

        # Update config only if checked status is different and informative
        if checked_status != current_config_status and checked_status != "UNKNOWN":
            logger.info(
                f"Status mismatch or update needed for server '{server_name}'. Updating config from '{current_config_status}' to '{checked_status}'."
            )
            manage_server_config(
                server_name=server_name,
                key="status",
                operation="write",
                value=checked_status,
                config_dir=config_dir,
            )
            logger.info(
                f"Successfully updated server status in config for '{server_name}' to '{checked_status}'."
            )
        elif checked_status == "UNKNOWN" and current_config_status not in (
            "UNKNOWN",
            "STOPPED",
        ):
            logger.warning(
                f"Log check resulted in UNKNOWN status for server '{server_name}', but config status is '{current_config_status}'. Config status not updated."
            )
        else:
            logger.debug(
                f"Server '{server_name}' status ('{checked_status}') matches config or is UNKNOWN. No config update needed."
            )

    except (FileOperationError, MissingArgumentError, InvalidServerNameError) as e:
        # Catch errors from check_server_status or manage_server_config
        logger.error(
            f"Failed to update server status in config for '{server_name}': {e}",
            exc_info=True,
        )
        raise  # Re-raise the caught error
    except Exception as e:
        logger.error(
            f"Unexpected error updating server status in config for '{server_name}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Unexpected error updating server status config for '{server_name}': {e}"
        ) from e


# --- Allowlist and Permissions ---


def configure_allowlist(server_dir: str) -> list:
    """
    Loads and returns the current content of the server's allowlist.json file.

    Args:
        server_dir: The full path to the server's installation directory.

    Returns:
        A list of player entries (dictionaries) currently in the allowlist.
        Returns an empty list if the file doesn't exist.

    Raises:
        MissingArgumentError: If `server_dir` is empty.
        DirectoryError: If `server_dir` does not exist or is not a directory.
        FileOperationError: If reading or parsing `allowlist.json` fails.
    """
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")
    if not os.path.isdir(server_dir):
        raise DirectoryError(f"Server directory not found: {server_dir}")

    allowlist_file = os.path.join(server_dir, "allowlist.json")
    logger.debug(f"Loading allowlist file: {allowlist_file}")

    existing_players = []
    if os.path.exists(allowlist_file):
        try:
            with open(allowlist_file, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():  # Check if not empty
                    existing_players = json.loads(content)
                    if not isinstance(existing_players, list):
                        logger.warning(
                            f"Allowlist file '{allowlist_file}' does not contain a JSON list. Treating as empty."
                        )
                        existing_players = []
                    else:
                        logger.debug(
                            f"Loaded {len(existing_players)} players from allowlist.json."
                        )
                else:
                    logger.debug("Allowlist file exists but is empty.")
                    existing_players = []
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON from allowlist file '{allowlist_file}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Invalid JSON in allowlist file: {allowlist_file}"
            ) from e
        except OSError as e:
            logger.error(
                f"Failed to read allowlist file '{allowlist_file}': {e}", exc_info=True
            )
            raise FileOperationError(
                f"Failed to read allowlist file: {allowlist_file}"
            ) from e
    else:
        logger.debug("Allowlist file does not exist. Returning empty list.")

    return existing_players


def add_players_to_allowlist(
    server_dir: str, new_players: list[Dict[str, Any]]
) -> None:
    """
    Adds one or more players to the server's allowlist.json file.

    Avoids adding duplicate players based on the 'name' key.

    Args:
        server_dir: The full path to the server's installation directory.
        new_players: A list of dictionaries, where each dictionary represents a player
                     and must contain at least a 'name' key (string). Other keys like
                     'ignoresPlayerLimit' (boolean) are typically included.

    Raises:
        MissingArgumentError: If `server_dir` is empty.
        TypeError: If `new_players` is not a list or contains non-dictionary items,
                   or if a player dict lacks a 'name'.
        DirectoryError: If `server_dir` does not exist or is not a directory.
        FileOperationError: If reading or writing `allowlist.json` fails.
    """
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")
    if not os.path.isdir(server_dir):
        raise DirectoryError(f"Server directory not found: {server_dir}")
    if not isinstance(new_players, list):
        raise TypeError("Input 'new_players' must be a list.")

    allowlist_file = os.path.join(server_dir, "allowlist.json")
    logger.info(f"Adding {len(new_players)} player(s) to allowlist: {allowlist_file}")

    try:
        # Load existing players first
        existing_players = configure_allowlist(server_dir)  # Uses the function above
        existing_names = {
            p.get("name", "").lower()
            for p in existing_players
            if isinstance(p, dict) and "name" in p
        }
        added_count = 0

        # Validate and add new players
        for player_dict in new_players:
            if not isinstance(player_dict, dict):
                logger.warning(
                    f"Skipping invalid item in new_players list (not a dict): {player_dict}"
                )
                continue
            player_name = player_dict.get("name")
            if not player_name or not isinstance(player_name, str):
                logger.warning(
                    f"Skipping invalid player entry (missing or invalid 'name'): {player_dict}"
                )
                continue

            if player_name.lower() in existing_names:
                logger.warning(
                    f"Player '{player_name}' is already in the allowlist. Skipping."
                )
            else:
                if "ignoresPlayerLimit" not in player_dict:
                    player_dict["ignoresPlayerLimit"] = False
                existing_players.append(player_dict)
                existing_names.add(player_name.lower())
                added_count += 1
                logger.debug(f"Added player '{player_name}' to allowlist.")

        # Write updated list back if changes were made
        if added_count > 0:
            logger.debug(
                f"Writing updated allowlist with {len(existing_players)} total players."
            )
            try:
                with open(allowlist_file, "w", encoding="utf-8") as f:
                    json.dump(existing_players, f, indent=4, sort_keys=True)
                logger.info(
                    f"Successfully updated allowlist.json ({added_count} players added)."
                )
            except OSError as e:
                logger.error(
                    f"Failed to write updated allowlist file '{allowlist_file}': {e}",
                    exc_info=True,
                )
                raise FileOperationError(
                    f"Failed to write allowlist file: {allowlist_file}"
                ) from e
        else:
            logger.info(
                "No new players added to the allowlist (all duplicates or input empty/invalid)."
            )

    except (DirectoryError, FileOperationError) as e:
        # Catch errors from configure_allowlist or writing
        logger.error(f"Failed to process allowlist: {e}", exc_info=True)
        raise  # Re-raise
    except Exception as e:
        logger.error(f"Unexpected error updating allowlist: {e}", exc_info=True)
        raise FileOperationError(f"Unexpected error updating allowlist: {e}") from e


def configure_permissions(
    server_dir: str, xuid: str, player_name: Optional[str], permission: str
) -> None:
    """
    Sets or updates a player's permission level in the server's permissions.json file.

    Args:
        server_dir: The full path to the server's installation directory.
        xuid: The player's unique Xbox User ID (XUID) string.
        player_name: Optional. The player's in-game name (used if adding new, ignored if updating).
        permission: The desired permission level ("operator", "member", "visitor"). Case-insensitive.

    Raises:
        MissingArgumentError: If `server_dir`, `xuid`, or `permission` is empty.
        InvalidInputError: If `permission` is not one of the allowed values.
        DirectoryError: If `server_dir` does not exist or is not a directory.
        FileOperationError: If reading or writing `permissions.json` fails.
    """
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")
    if not os.path.isdir(server_dir):
        raise DirectoryError(f"Server directory not found: {server_dir}")
    if not xuid:
        raise MissingArgumentError("Player XUID cannot be empty.")
    if not permission:
        raise MissingArgumentError("Permission level cannot be empty.")

    permission = permission.lower()  # Normalize permission level
    valid_permissions = ("operator", "member", "visitor")
    if permission not in valid_permissions:
        raise InvalidInputError(
            f"Invalid permission level '{permission}'. Must be one of: {valid_permissions}"
        )

    permissions_file = os.path.join(server_dir, "permissions.json")
    logger.info(
        f"Configuring permission for XUID '{xuid}' to '{permission}' in: {permissions_file}"
    )

    permissions_data = []
    # Load existing permissions or initialize if file doesn't exist/is invalid
    try:
        if os.path.exists(permissions_file):
            with open(permissions_file, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    permissions_data = json.loads(content)
                    if not isinstance(permissions_data, list):
                        logger.warning(
                            f"Permissions file '{permissions_file}' does not contain a JSON list. Overwriting."
                        )
                        permissions_data = []
                    else:
                        logger.debug(
                            f"Loaded {len(permissions_data)} entries from permissions.json."
                        )
                else:
                    logger.debug("Permissions file exists but is empty.")
                    permissions_data = []
        else:
            logger.debug("Permissions file does not exist. Will create.")
            permissions_data = []
    except json.JSONDecodeError as e:
        logger.warning(
            f"Failed to parse JSON from permissions file '{permissions_file}'. File will be overwritten. Error: {e}",
            exc_info=True,
        )
        permissions_data = []
    except OSError as e:
        logger.error(
            f"Failed to read permissions file '{permissions_file}': {e}", exc_info=True
        )
        raise FileOperationError(
            f"Failed to read permissions file: {permissions_file}"
        ) from e

    # Find player by XUID and update/add
    player_found = False
    updated = False
    for i, entry in enumerate(permissions_data):
        if isinstance(entry, dict) and entry.get("xuid") == xuid:
            player_found = True
            if entry.get("permission") != permission:
                logger.info(
                    f"Updating permission for XUID '{xuid}' from '{entry.get('permission')}' to '{permission}'."
                )
                permissions_data[i]["permission"] = permission
                if player_name and entry.get("name") != player_name:
                    logger.debug(f"Updating name for XUID '{xuid}' to '{player_name}'.")
                    permissions_data[i]["name"] = player_name
                updated = True
            else:
                logger.info(
                    f"Player with XUID '{xuid}' already has permission '{permission}'. No changes needed."
                )
                updated = False  # Explicitly set updated to False if no change
            break

    if not player_found:
        if not player_name:
            logger.warning(
                f"Adding new player with XUID '{xuid}' but no player_name provided. Using XUID as name."
            )
            player_name = xuid  # Use XUID as fallback name

        logger.info(
            f"Adding new player XUID '{xuid}' (Name: '{player_name}') with permission '{permission}'."
        )
        new_entry = {"permission": permission, "xuid": xuid, "name": player_name}
        permissions_data.append(new_entry)
        updated = True

    # Write back only if changes were made
    if updated:
        try:
            logger.debug(
                f"Writing updated permissions data ({len(permissions_data)} entries) to '{permissions_file}'."
            )
            with open(permissions_file, "w", encoding="utf-8") as f:
                json.dump(permissions_data, f, indent=4, sort_keys=True)
            logger.debug(f"Successfully updated permissions.json for XUID '{xuid}'.")
        except OSError as e:
            logger.error(
                f"Failed to write updated permissions file '{permissions_file}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to write permissions file: {permissions_file}"
            ) from e


def modify_server_properties(
    server_properties_path: str, property_name: str, property_value: str
) -> None:
    """
    Modifies or adds a property in the server.properties file.

    Preserves comments and blank lines.

    Args:
        server_properties_path: The full path to the server.properties file.
        property_name: The name of the property to set (e.g., "level-name").
        property_value: The value to assign to the property.

    Raises:
        MissingArgumentError: If `server_properties_path` or `property_name` is empty.
        FileNotFoundError: If `server_properties_path` does not exist or is not a file.
        InvalidInputError: If `property_value` contains control characters (ASCII < 32).
        FileOperationError: If reading or writing the file fails due to OS errors.
    """
    if not server_properties_path:
        raise MissingArgumentError("Server properties file path cannot be empty.")
    if not property_name:
        raise MissingArgumentError("Property name cannot be empty.")
    # Allow empty string value, but check for control chars which might break the file
    if property_value is None:
        property_value = ""  # Treat None as empty string
    if any(
        ord(c) < 32 for c in property_value if c not in ("\t")
    ):  # Allow tabs, disallow others < 32
        raise InvalidInputError(
            f"Property value for '{property_name}' contains invalid control characters."
        )

    logger.debug(
        f"Modifying property '{property_name}' to '{property_value}' in: {server_properties_path}"
    )

    if not os.path.isfile(server_properties_path):
        raise FileNotFoundError(
            f"Server properties file not found: {server_properties_path}"
        )

    try:
        with open(server_properties_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        property_found = False
        output_lines = []
        property_line = f"{property_name}={property_value}\n"

        for line in lines:
            stripped_line = line.strip()
            # Ignore comments and blank lines when searching for the property
            if not stripped_line or stripped_line.startswith("#"):
                output_lines.append(line)
                continue

            # Check if line starts with property_name=
            if stripped_line.startswith(property_name + "="):
                if not property_found:  # Only replace the first occurrence found
                    logger.debug(
                        f"Replacing existing line: {line.strip()} with: {property_line.strip()}"
                    )
                    output_lines.append(property_line)
                    property_found = True
                else:
                    logger.warning(
                        f"Duplicate property '{property_name}' found. Keeping first occurrence, ignoring line: {line.strip()}"
                    )
                    output_lines.append("# DUPLICATE IGNORED: " + line)
            else:
                # Keep other valid lines
                output_lines.append(line)

        # If property was not found anywhere, append it to the end
        if not property_found:
            logger.debug(f"Property '{property_name}' not found. Appending to end.")
            # Add a newline before appending if the last line wasn't empty
            if output_lines and not output_lines[-1].endswith("\n"):
                output_lines[-1] += "\n"
            output_lines.append(property_line)

        # Write the modified lines back to the file
        with open(server_properties_path, "w", encoding="utf-8") as f:
            f.writelines(output_lines)
        logger.debug(
            f"Successfully modified server.properties for property '{property_name}'."
        )

    except OSError as e:
        logger.error(
            f"Failed to read or write server.properties file '{server_properties_path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(f"Failed to modify server.properties: {e}") from e
    except Exception as e:
        logger.error(
            f"Unexpected error modifying server.properties: {e}", exc_info=True
        )
        raise FileOperationError(
            f"Unexpected error modifying server.properties: {e}"
        ) from e


def _write_version_config(
    server_name: str, installed_version: str, config_dir: Optional[str] = None
) -> None:
    """
    Helper function to write the 'installed_version' key to a server's config file.

    Args:
        server_name: The name of the server.
        installed_version: The version string to write.
        config_dir: Optional. The base directory for server configs.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If writing to the config file fails.
    """
    # server_name validity already checked by caller usually, but check again
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    if not installed_version:
        logger.warning(f"Empty installed_version for server '{server_name}' provided.")
        raise InvalidInputError("installed_version required")

    logger.debug(
        f"Writing installed_version '{installed_version}' to config for server '{server_name}'."
    )
    try:
        manage_server_config(
            server_name=server_name,
            key="installed_version",
            operation="write",
            value=installed_version,  # Value can be None or empty string based on check above
            config_dir=config_dir,
        )
        logger.debug("Successfully wrote installed_version to config.")
    except (
        MissingArgumentError,
        InvalidInputError,
        FileOperationError,
        InvalidServerNameError,
    ) as e:
        # Catch errors from manage_server_config
        logger.error(
            f"Failed to write installed_version to config for '{server_name}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to write version config for '{server_name}': {e}"
        ) from e


def install_server(
    server_name: str,
    base_dir: str,
    target_version: str,
    zip_file_path: str,
    server_dir: str,
    is_update: bool,
) -> None:
    """
    Installs or updates the Bedrock server files and configuration.

    Handles stopping/starting, backup/restore during updates, file extraction,
    permissions setting, and version recording.

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing server installations.
        target_version: The version string being installed/updated (used for logging/config).
        zip_file_path: The full path to the downloaded server ZIP file.
        server_dir: The full path to the target server installation directory.
        is_update: True if performing an update on an existing server, False for a fresh install.

    Raises:
        MissingArgumentError: If required arguments are empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If settings (DOWNLOAD_KEEP) are missing, backup/restore fails,
                            or setting permissions/writing version config fails.
        DirectoryError: If server directory is invalid.
        InstallUpdateError: Wraps failures during critical steps like backup, extraction, restore.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")
    if not target_version:
        raise MissingArgumentError("Target version cannot be empty.")
    if not zip_file_path:
        raise MissingArgumentError("ZIP file path cannot be empty.")
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")

    action = "Updating" if is_update else "Installing"
    logger.info(f"{action} server '{server_name}' to version '{target_version}'...")
    logger.debug(f"Source ZIP: {zip_file_path}, Target Dir: {server_dir}")

    # 1. Stop server if it's an update and the server is running
    was_running = False
    if is_update:
        try:
            # This function stops the server if running and returns True if it was running
            was_running = stop_server_if_running(server_name, base_dir)
        except (InvalidServerNameError, ServerStopError, CommandNotFoundError) as e:
            # Abort the update if stopping fails, as extraction might fail otherwise.
            logger.error(
                f"Failed to stop server '{server_name}' before update: {e}. Aborting update.",
                exc_info=True,
            )
            raise InstallUpdateError(
                f"Failed to stop server '{server_name}' before update."
            ) from e
        except Exception as e:
            logger.error(
                f"Unexpected error stopping server '{server_name}' before update: {e}. Aborting update.",
                exc_info=True,
            )
            raise InstallUpdateError(
                f"Unexpected error stopping server '{server_name}' before update."
            ) from e

    # 3. Backup server if it's an update
    if is_update:
        logger.info(f"Performing backup of server '{server_name}' before update...")
        try:
            backup.backup_all(server_name, base_dir)
            logger.info("Pre-update backup completed successfully.")
        except (BackupWorldError, FileOperationError, MissingArgumentError) as e:
            logger.error(
                f"Backup failed before update for server '{server_name}': {e}. Aborting update.",
                exc_info=True,
            )
            # If backup fails, don't proceed with update
            raise InstallUpdateError(
                f"Backup failed before update for '{server_name}'."
            ) from e
        except Exception as e:
            logger.error(
                f"Unexpected error during pre-update backup for '{server_name}': {e}. Aborting update.",
                exc_info=True,
            )
            raise InstallUpdateError(
                f"Unexpected error during pre-update backup for '{server_name}'."
            ) from e

    # 4. Extract server files
    logger.debug(
        f"Extracting server files from '{os.path.basename(zip_file_path)}' to '{server_dir}'..."
    )
    try:
        downloader.extract_server_files_from_zip(zip_file_path, server_dir, is_update)
        logger.info("Server file extraction completed successfully.")
    except (
        DownloadExtractError,
        FileOperationError,
        MissingArgumentError,
        FileNotFoundError,
    ) as e:
        logger.error(
            f"Failed to extract server files for '{server_name}': {e}", exc_info=True
        )
        # If extraction fails, the installation/update cannot proceed.
        raise InstallUpdateError(
            f"Failed to extract server files for '{server_name}'."
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error during server file extraction for '{server_name}': {e}",
            exc_info=True,
        )
        raise InstallUpdateError(
            f"Unexpected error during server file extraction for '{server_name}'."
        ) from e

    # 5. Set permissions (especially important on Linux)
    logger.debug(f"Setting permissions for server directory: {server_dir}")
    try:
        system_base.set_server_folder_permissions(server_dir)
        logger.debug("Server folder permissions set successfully.")
    except Exception as e:
        # Log warning, but don't necessarily fail the whole install if permissions fail
        logger.warning(
            f"Failed to set server folder permissions for '{server_dir}': {e}. Manual adjustment might be needed.",
            exc_info=True,
        )

    # 6. Write installed version to config
    logger.debug(
        f"Writing installed version '{target_version}' to config for server '{server_name}'."
    )
    try:
        _write_version_config(server_name, target_version)
        manage_server_config(
            server_name, "status", "write", "STOPPED"
        )  # Set status to STOPPED after install/update
        logger.debug("Successfully wrote version and updated status in config.")
    except (FileOperationError, InvalidServerNameError) as e:
        # If writing config fails, the server might work but manager won't know version/status.
        logger.error(
            f"Failed to write version/status to config file for '{server_name}': {e}. Installation complete but metadata missing.",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to write version/status config for '{server_name}'."
        ) from e

    # 8. Restart server if it was running before the update
    if was_running:
        logger.info(
            f"Attempting to restart server '{server_name}' as it was running before update..."
        )
        try:
            start_server_if_was_running(server_name, base_dir, was_running)
            logger.info(f"Server '{server_name}' restart initiated.")
        except (ServerStartError, CommandNotFoundError) as e:
            # Log error but installation itself was successful
            logger.error(
                f"Installation/update complete, but failed to automatically restart server '{server_name}': {e}. Please start it manually.",
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"Installation/update complete, but unexpected error occurred during automatic restart of server '{server_name}': {e}. Please start it manually.",
                exc_info=True,
            )

    logger.info(f"Server '{server_name}' {action.lower()} process completed.")


def no_update_needed(
    server_name: str, installed_version: str, target_version_spec: str
) -> bool:
    """
    Checks if the installed server version matches the latest available version
    based on the target specification ("LATEST" or "PREVIEW").

    Args:
        server_name: The name of the server.
        installed_version: The currently installed version string (e.g., "1.20.1.2").
        target_version_spec: The desired version specification ("LATEST", "PREVIEW").
                             If a specific version number is passed, this function
                             assumes an update *is* needed (returns False).

    Returns:
        True if the installed version matches the latest available for the spec,
        False otherwise (or if the latest version cannot be determined).

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        # Exceptions from downloader.lookup_bedrock_download_url / get_version_from_url may propagate
        # (InternetConnectivityError, DownloadExtractError, OSError)
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    target_upper = target_version_spec.upper()

    # If a specific version is requested, we treat it as needing an "update"
    # unless the specific version matches exactly what's installed.
    # However, the primary use case here is checking against LATEST/PREVIEW.
    if target_upper not in ("LATEST", "PREVIEW"):
        logger.debug(
            f"Target version '{target_version_spec}' is specific. Assuming update check is not applicable in this context (always attempt install/update)."
        )
        return False  # Assume 'update' needed if specific version given

    if not installed_version or installed_version == "UNKNOWN":
        logger.info(
            f"Installed version for server '{server_name}' is '{installed_version}'. Update check requires a known installed version. Assuming update needed."
        )
        return False  # Cannot compare if installed version is unknown

    logger.debug(
        f"Checking if update is needed for server '{server_name}': Installed='{installed_version}', Target='{target_upper}'"
    )

    try:
        # Find the download URL for the target spec (LATEST or PREVIEW)
        latest_download_url = downloader.lookup_bedrock_download_url(target_upper)
        # Extract the actual version number from that URL
        latest_available_version = downloader.get_version_from_url(latest_download_url)
        logger.debug(
            f"Latest available version for '{target_upper}' spec found: '{latest_available_version}'"
        )

        # Compare installed version with the latest available
        if installed_version == latest_available_version:
            logger.debug(
                f"Server '{server_name}' is already up-to-date (Version: {installed_version}). No update needed."
            )
            return True
        else:
            logger.info(
                f"Update needed for server '{server_name}'. Installed: {installed_version}, Latest Available ({target_upper}): {latest_available_version}"
            )
            return False

    except (InternetConnectivityError, DownloadExtractError, OSError) as e:
        # If we fail to get the latest version info, log warning and assume update needed
        logger.warning(
            f"Could not determine the latest available version for '{target_upper}' due to an error: {e}. Assuming update might be needed.",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error during update check for server '{server_name}': {e}",
            exc_info=True,
        )
        return False  # Assume update needed on unexpected error


def delete_server_data(
    server_name: str, base_dir: str, config_dir: Optional[str] = None
) -> None:
    """
    Deletes all data associated with a Bedrock server, including its installation
    directory, configuration folder, and systemd service file (on Linux).

    Args:
        server_name: The name of the server to delete.
        base_dir: The base directory containing server installations.
        config_dir: Optional. The base directory for server configs. Defaults if None.

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        DirectoryError: If deleting the server data or config directories fails.
        FileOperationError: If settings (BACKUP_DIR) are missing.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    effective_config_dir = (
        config_dir if config_dir is not None else getattr(settings, "_config_dir", None)
    )
    if not effective_config_dir:
        raise FileOperationError(
            "Base configuration directory is not set or available."
        )

    server_install_dir = os.path.join(base_dir, server_name)
    server_config_subdir = os.path.join(effective_config_dir, server_name)
    # Also consider backup directory
    backup_base_dir = settings.get("BACKUP_DIR")
    server_backup_dir = (
        os.path.join(backup_base_dir, server_name) if backup_base_dir else None
    )

    logger.warning(f"!!! Preparing to delete all data for server '{server_name}' !!!")
    logger.debug(f"Target installation directory: {server_install_dir}")
    logger.debug(f"Target configuration directory: {server_config_subdir}")
    if server_backup_dir:
        logger.debug(f"Target backup directory: {server_backup_dir}")

    # --- Pre-checks and Stop Server ---
    if not os.path.exists(server_install_dir) and not os.path.exists(
        server_config_subdir
    ):
        logger.warning(
            f"Server '{server_name}' data not found (neither install nor config dir exists). Skipping deletion."
        )
        return

    # Attempt to stop the server if it's running
    try:
        if system_base.is_server_running(server_name, base_dir):
            logger.info(
                f"Server '{server_name}' is running. Attempting to stop before deletion..."
            )
            # Use BedrockServer class to handle stop logic
            server_instance = BedrockServer(
                server_name
            )  # Assumes executable exists if running
            server_instance.stop()  # Raises ServerStopError on failure
            logger.info(f"Server '{server_name}' stopped successfully.")
        else:
            logger.debug(f"Server '{server_name}' is not running.")
    except ServerNotFoundError:
        logger.debug(
            "Server executable not found, cannot use BedrockServer class to stop. Proceeding with deletion."
        )
    except (ServerStopError, CommandNotFoundError) as e:
        logger.error(
            f"Failed to stop server '{server_name}' before deletion: {e}. Deletion aborted.",
            exc_info=True,
        )
        raise DirectoryError(
            f"Failed to stop running server '{server_name}' before deletion."
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error stopping server '{server_name}' before deletion: {e}. Deletion aborted.",
            exc_info=True,
        )
        raise DirectoryError(
            f"Unexpected error stopping server '{server_name}' before deletion."
        ) from e

    # --- Remove systemd service (Linux) ---
    if platform.system() == "Linux":
        service_name = f"bedrock-{server_name}"
        service_file_path = os.path.join(
            os.path.expanduser("~/.config/systemd/user/"), f"{service_name}.service"
        )
        systemctl_cmd_path = shutil.which("systemctl")

        if os.path.exists(service_file_path) and systemctl_cmd_path:
            logger.info(
                f"Disabling and removing systemd user service '{service_name}'..."
            )
            try:
                # Disable first (stops it if running, prevents auto-start)
                subprocess.run(
                    [systemctl_cmd_path, "--user", "disable", "--now", service_name],
                    check=False,
                    capture_output=True,
                )  # --now stops it too
                logger.debug(f"Attempted disable --now for service '{service_name}'.")
                # Remove the service file
                os.remove(service_file_path)
                logger.debug(f"Removed service file: {service_file_path}")
                # Reload systemd daemon
                subprocess.run(
                    [systemctl_cmd_path, "--user", "daemon-reload"],
                    check=False,
                    capture_output=True,
                )
                subprocess.run(
                    [systemctl_cmd_path, "--user", "reset-failed"],
                    check=False,
                    capture_output=True,
                )  # Clean up failed state
                logger.info(
                    f"Systemd service '{service_name}' removed and daemon reloaded."
                )
            except OSError as e:
                logger.warning(
                    f"Failed to remove systemd service file '{service_file_path}': {e}. Manual cleanup might be needed.",
                    exc_info=True,
                )
            except Exception as e:
                logger.warning(
                    f"Failed during systemd service removal/reload for '{service_name}': {e}. Manual cleanup might be needed.",
                    exc_info=True,
                )
        elif os.path.exists(service_file_path):
            logger.warning(
                f"Systemd service file found for '{service_name}', but 'systemctl' command not found. Cannot remove service automatically."
            )

    # --- Remove directories ---
    dirs_to_delete = {
        "installation": server_install_dir,
        "configuration": server_config_subdir,
        "backup": server_backup_dir,
    }
    deletion_errors = []

    for dir_type, dir_path in dirs_to_delete.items():
        if dir_path and os.path.exists(dir_path):
            logger.info(f"Deleting server {dir_type} directory: {dir_path}")
            try:
                # On Windows, try removing read-only first
                if platform.system() == "Windows":
                    logger.debug(
                        f"Attempting to remove read-only attributes for: {dir_path}"
                    )
                    system_base.remove_readonly(dir_path)
                # Remove the directory tree
                shutil.rmtree(dir_path)
                logger.info(f"Successfully deleted {dir_type} directory: {dir_path}")
            except OSError as e:
                logger.error(
                    f"Failed to delete server {dir_type} directory '{dir_path}': {e}",
                    exc_info=True,
                )
                deletion_errors.append(f"{dir_type} directory '{dir_path}' ({e})")
            except Exception as e:
                logger.error(
                    f"Unexpected error deleting server {dir_type} directory '{dir_path}': {e}",
                    exc_info=True,
                )
                deletion_errors.append(
                    f"{dir_type} directory '{dir_path}' (Unexpected error: {e})"
                )
        elif dir_path:
            logger.debug(
                f"Server {dir_type} directory not found, skipping deletion: {dir_path}"
            )

    # Report final status
    if deletion_errors:
        error_summary = "; ".join(deletion_errors)
        logger.error(
            f"Deletion process for server '{server_name}' completed with errors. Failed to delete: {error_summary}"
        )
        raise DirectoryError(
            f"Failed to completely delete server '{server_name}'. Failed items: {error_summary}"
        )
    else:
        logger.debug(f"Successfully deleted all data for server: '{server_name}'.")


# --- Helper Functions for Start/Stop Logic ---


def start_server_if_was_running(
    server_name: str, base_dir: str, was_running: bool
) -> None:
    """
    Starts the server using the BedrockServer class, but only if `was_running` is True.

    Helper function primarily for use after updates/installs.

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server folder.
        was_running: Boolean indicating if the server was running prior to an operation.

    Raises:
        # Propagates exceptions from BedrockServer.start()
        ServerStartError, CommandNotFoundError, ServerNotFoundError, etc.
    """
    if was_running:
        logger.info(
            f"Server '{server_name}' was running previously. Attempting to restart..."
        )
        try:
            # Create instance and start it
            server_instance = BedrockServer(
                server_name
            )  # Assumes server executable exists now
            server_instance.start()
            logger.info(f"Server '{server_name}' restart initiated successfully.")
        except (ServerNotFoundError, ServerStartError, CommandNotFoundError) as e:
            logger.error(
                f"Failed to automatically restart server '{server_name}': {e}. Please start it manually.",
                exc_info=True,
            )
            raise  # Re-raise the specific error from start()
        except Exception as e:
            logger.error(
                f"Unexpected error automatically restarting server '{server_name}': {e}. Please start it manually.",
                exc_info=True,
            )
            raise ServerStartError(
                f"Unexpected error restarting server '{server_name}': {e}"
            ) from e
    else:
        logger.debug(
            f"Server '{server_name}' was not running previously. No restart attempted."
        )


def stop_server_if_running(server_name: str, base_dir: str) -> bool:
    """
    Checks if a server is running and stops it if it is.

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server folder.

    Returns:
        True if the server was running (and a stop was attempted), False otherwise.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        # Propagates exceptions from BedrockServer.stop() if stopping fails
        ServerStopError, SendCommandError, CommandNotFoundError, ServerNotFoundError, etc.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"Checking if server '{server_name}' needs to be stopped...")

    try:
        # Check running status first
        if system_base.is_server_running(server_name, base_dir):
            logger.info(f"Server '{server_name}' is running. Attempting to stop...")
            try:
                # Use BedrockServer class to handle stop logic
                server_instance = BedrockServer(
                    server_name
                )  # Raises ServerNotFoundError if exe missing
                server_instance.stop()  # Raises ServerStopError etc. on failure
                logger.info(f"Stop initiated successfully for server '{server_name}'.")
                return True  # Server was running, stop attempt made (successful or not)
            except (ServerStopError, SendCommandError, CommandNotFoundError) as e:
                logger.error(
                    f"Attempt to stop server '{server_name}' failed: {e}", exc_info=True
                )
                # Even though stop failed, it *was* running. Raise the error.
                raise
            except ServerNotFoundError:
                logger.warning(
                    f"Server process '{server_name}' seems to be running, but executable not found. Cannot use class stop method."
                )
                # Report that it was running but couldn't be stopped cleanly.
                raise ServerStopError(
                    f"Server '{server_name}' running but executable missing. Stop failed."
                )

        else:
            logger.debug(f"Server '{server_name}' is not currently running.")
            return False  # Server was not running

    except Exception as e:  # Catch unexpected errors during the check/stop process
        logger.error(
            f"Unexpected error during stop_server_if_running for '{server_name}': {e}",
            exc_info=True,
        )
        raise ServerStopError(
            f"Unexpected error stopping server '{server_name}': {e}"
        ) from e
