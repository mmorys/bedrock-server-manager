# bedrock-server-manager/bedrock_server_manager/core/server/server_actions.py
"""
Core module for managing Bedrock server instances.
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
    CommandNotFoundError,
)
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
    windows as system_windows,
)

if platform.system() == "Windows":
    try:
        import win32file
        import pywintypes
        import win32pipe

        WINDOWS_IMPORTS_AVAILABLE = True
    except ImportError:
        WINDOWS_IMPORTS_AVAILABLE = False
else:
    WINDOWS_IMPORTS_AVAILABLE = False


logger = logging.getLogger("bedrock_server_manager")


# --- Helper function ---
def _get_server_details(
    server_name: str, server_path_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Gathers and validates server paths and essential details.
    This helper is used by functions that previously were methods of BedrockServer.

    Args:
        server_name: The name of the server.
        server_path_override: Optional. The full path to the server executable.
                              If None, it's inferred based on OS and server_dir.

    Returns:
        A dictionary containing server details:
        - server_name (str)
        - base_dir (str): Base directory for all servers from settings.
        - server_dir (str): Path to this specific server's installation directory.
        - server_path (str): Full path to the server executable.
        - config_dir_base (str): Base directory for all server configs from settings.
        - server_config_dir (str): Path to this specific server's configuration directory.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If BASE_DIR or _config_dir setting is missing.
        ServerNotFoundError: If the server executable cannot be found.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty for server operations.")

    logger.debug(f"Getting details for server '{server_name}'")

    base_dir = settings.get("BASE_DIR")
    if not base_dir:
        raise FileOperationError(
            "BASE_DIR setting is missing or empty in configuration."
        )
    server_dir = os.path.join(base_dir, server_name)

    config_dir_base = settings._config_dir
    if not config_dir_base:
        raise FileOperationError(
            "Internal _config_dir setting is missing or empty. Ensure settings are loaded."
        )
    server_config_dir = os.path.join(config_dir_base, server_name)

    if server_path_override:
        server_executable_path = server_path_override
        logger.debug(f"Using provided server executable path: {server_executable_path}")
    else:
        exe_name = (
            "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
        )
        server_executable_path = os.path.join(server_dir, exe_name)
        logger.debug(f"Using default server executable path: {server_executable_path}")

    # Validate existence of executable immediately
    if not os.path.isfile(server_executable_path):
        error_msg = f"Server executable not found at path: {server_executable_path}"
        logger.error(error_msg)
        raise ServerNotFoundError(error_msg)

    return {
        "server_name": server_name,
        "base_dir": base_dir,
        "server_dir": server_dir,
        "server_path": server_executable_path,
        "config_dir_base": config_dir_base,
        "server_config_dir": server_config_dir,
    }


# --- Standalone functions replacing BedrockServer methods ---


def check_if_server_is_running(server_name: str) -> bool:
    """
    Checks if the server process associated with this name is currently running.
    Equivalent to former BedrockServer.is_running().
    """
    if not server_name:
        # Consistent with how _get_server_details handles server_name
        raise MissingArgumentError("Server name cannot be empty.")

    logger.debug(f"Checking running status for server '{server_name}'")
    base_dir = settings.get("BASE_DIR")
    if not base_dir:
        raise FileOperationError(
            "BASE_DIR setting is missing or empty in configuration."
        )

    is_running_flag = system_base.is_server_running(server_name, base_dir)
    logger.debug(f"Server '{server_name}' is_running result: {is_running_flag}")
    return is_running_flag


def send_server_command(server_name: str, command: str) -> None:
    """
    Sends a command string to the running server process.
    Implementation is platform-specific (screen on Linux, named pipes on Windows).
    Equivalent to former BedrockServer.send_command().

    Args:
        server_name: The name of the server.
        command: The command string to send to the server console.

    Raises:
        MissingArgumentError: If `server_name` or `command` is empty.
        ServerNotRunningError: If the server process cannot be found or communicated with.
        SendCommandError: If there's a platform-specific error sending the command.
        CommandNotFoundError: If a required external command (like 'screen') is not found.
        NotImplementedError: If the current OS is not supported.
        FileOperationError: If BASE_DIR setting is missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty for send_command.")
    if not command:
        raise MissingArgumentError("Command cannot be empty.")

    if not check_if_server_is_running(server_name):
        logger.error(
            f"Cannot send command to server '{server_name}': Server is not running."
        )
        raise ServerNotRunningError(f"Server '{server_name}' is not running.")

    logger.info(f"Sending command '{command}' to server '{server_name}'...")

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
            screen_session_name = f"bedrock-{server_name}"
            command_with_newline = command if command.endswith("\n") else command + "\n"
            process = subprocess.run(
                [
                    screen_cmd_path,
                    "-S",
                    screen_session_name,
                    "-X",
                    "stuff",
                    command_with_newline,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.debug(
                f"'screen' command executed successfully for server '{server_name}'. stdout: {process.stdout}, stderr: {process.stderr}"
            )
            logger.info(
                f"Sent command '{command}' to server '{server_name}' via screen."
            )
        except subprocess.CalledProcessError as e:
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
                raise SendCommandError(f"Failed to send command via screen: {e}") from e
        except FileNotFoundError:
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

        pipe_name = rf"\\.\pipe\BedrockServerPipe_{server_name}"
        handle = win32file.INVALID_HANDLE_VALUE

        try:
            logger.debug(f"Attempting to connect to named pipe: {pipe_name}")
            handle = win32file.CreateFile(
                pipe_name,
                win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )

            if handle == win32file.INVALID_HANDLE_VALUE:
                logger.error(
                    f"Could not open named pipe '{pipe_name}'. Server might not be running or pipe setup failed. Error code: {pywintypes.GetLastError()}"
                )
                raise ServerNotRunningError(
                    f"Could not connect to server pipe '{pipe_name}'."
                )

            win32pipe.SetNamedPipeHandleState(
                handle, win32pipe.PIPE_READMODE_MESSAGE, None, None
            )

            command_bytes = (command + "\r\n").encode("utf-8")
            win32file.WriteFile(handle, command_bytes)
            logger.info(
                f"Sent command '{command}' to server '{server_name}' via named pipe."
            )

        except pywintypes.error as e:
            win_error_code = e.winerror
            logger.error(
                f"Windows error sending command via pipe '{pipe_name}': Code {win_error_code} - {e}",
                exc_info=True,
            )
            if win_error_code == 2:
                raise ServerNotRunningError(
                    f"Pipe '{pipe_name}' does not exist. Server likely not running."
                ) from e
            elif win_error_code == 231:
                raise SendCommandError(
                    "All pipe instances are busy. Try again later."
                ) from e
            elif win_error_code == 109:
                raise SendCommandError(
                    "Pipe connection broken (server may have closed it)."
                ) from e
            else:
                raise SendCommandError(f"Windows error sending command: {e}") from e
        except Exception as e:
            logger.error(
                f"Unexpected error sending command via pipe '{pipe_name}': {e}",
                exc_info=True,
            )
            raise SendCommandError(f"Unexpected error sending command: {e}") from e
        finally:
            if handle != win32file.INVALID_HANDLE_VALUE:
                try:
                    win32file.CloseHandle(handle)
                    logger.debug(f"Closed named pipe handle for '{pipe_name}'.")
                except pywintypes.error as close_err:
                    logger.warning(
                        f"Error closing pipe handle for '{pipe_name}': {close_err}",
                        exc_info=True,
                    )
    else:
        logger.error(
            f"Sending commands is not supported on this operating system: {os_name}"
        )
        raise NotImplementedError(f"Sending commands not supported on {os_name}")


def start_server(server_name: str, server_path_override: Optional[str] = None) -> None:
    """
    Starts the Bedrock server process.
    Uses systemd on Linux (if available, falling back to screen) or starts
    directly on Windows. Manages persistent status and waits for confirmation.
    Equivalent to former BedrockServer.start().

    Args:
        server_name: The name of the server.
        server_path_override: Optional. The full path to the server executable.

    Raises:
        ServerStartError: If the server is already running, if the OS is unsupported,
                          or if the server fails to start within the timeout.
        CommandNotFoundError: If required external commands (systemctl, screen) are missing.
        ServerNotFoundError: If the server executable cannot be found.
        MissingArgumentError: If server_name is empty.
        FileOperationError: If essential settings (BASE_DIR, _config_dir) are missing.
    """
    details = _get_server_details(server_name, server_path_override)
    # server_name is details["server_name"]
    # server_dir = details["server_dir"]
    # server_config_dir = details["server_config_dir"]
    # config_dir_base = details["config_dir_base"] (used for manage_server_config)

    if check_if_server_is_running(server_name):
        logger.warning(
            f"Attempted to start server '{server_name}' but it is already running."
        )
        raise ServerStartError(f"Server '{server_name}' is already running.")

    manage_server_config(
        server_name,
        "status",
        "write",
        "STARTING",
        config_dir=details["config_dir_base"],
    )
    logger.info(f"Attempting to start server '{server_name}'...")

    os_name = platform.system()
    start_successful_method = None

    if os_name == "Linux":
        screen_cmd_path = shutil.which("screen")
        if screen_cmd_path:
            logger.info("Starting server.")
            try:
                system_linux._linux_start_server(server_name, details["server_dir"])
                start_successful_method = "screen"
            except (CommandNotFoundError, ServerStartError) as e:
                logger.error(
                    f"Failed to start server using screen method: {e}",
                    exc_info=True,
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error starting server via screen method: {e}",
                    exc_info=True,
                )
        else:
            logger.error("'screen' command not found. Cannot start server.")
            manage_server_config(
                server_name,
                "status",
                "write",
                "ERROR",
                config_dir=details["config_dir_base"],
            )
            raise CommandNotFoundError(
                "screen", message="'screen' command not found. Cannot start server."
            )
            attempts = 0
            max_attempts = settings.get("SERVER_START_TIMEOUT_SEC", 60) // 2
            sleep_interval = 2

            logger.info(
                f"Waiting up to {max_attempts * sleep_interval} seconds for server '{server_name}' to start..."
            )
            while attempts < max_attempts:
                if check_if_server_is_running(server_name):
                    manage_server_config(
                        server_name,
                        "status",
                        "write",
                        "RUNNING",
                        config_dir=details["config_dir_base"],
                    )
                    logger.info(f"Server '{server_name}' started successfully.")
                    return
                logger.debug(
                    f"Waiting for server '{server_name}' to start... (Check {attempts + 1}/{max_attempts})"
                )
                time.sleep(sleep_interval)
                attempts += 1

            manage_server_config(
                server_name,
                "status",
                "write",
                "ERROR",
                config_dir=details["config_dir_base"],
            )
            logger.error(
                f"Server '{server_name}' failed to confirm running status within the timeout ({max_attempts * sleep_interval} seconds)."
            )
            raise ServerStartError(
                f"Server '{server_name}' failed to start within the timeout."
            )

    elif os_name == "Windows":
        logger.debug("Attempting to start server via Windows process creation.")

        try:
            manage_server_config(
                server_name,
                "status",
                "write",
                "RUNNING",
                config_dir=details["config_dir_base"],
            )
            _ = system_windows._windows_start_server(  # Popen object not stored/used further here
                server_name, details["server_dir"], details["server_config_dir"]
            )
            start_successful_method = "windows_process"
            logger.info(f"Exited named pipe cleaninly on Windows for '{server_name}'.")

            manage_server_config(
                server_name,
                "status",
                "write",
                "STOPPED",
                config_dir=details["config_dir_base"],
            )
        except ServerStartError as e:
            logger.error(
                f"Failed to start server process on Windows: {e}", exc_info=True
            )
        except Exception as e:
            logger.error(
                f"Unexpected error starting server process on Windows: {e}",
                exc_info=True,
            )

    else:
        logger.error(
            f"Starting server is not supported on this operating system: {os_name}"
        )
        manage_server_config(
            server_name,
            "status",
            "write",
            "ERROR",
            config_dir=details["config_dir_base"],
        )
        raise ServerStartError(f"Unsupported operating system: {os_name}")


def stop_server(server_name: str, server_path_override: Optional[str] = None) -> None:
    """
    Stops the Bedrock server process gracefully.
    Sends a 'stop' command, waits for the process to terminate.
    Equivalent to former BedrockServer.stop().

    Args:
        server_name: The name of the server.
        server_path_override: Optional. The full path to the server executable.

    Raises:
        ServerStopError: If the server is not running (when expected), OS unsupported,
                         or fails to stop within timeout.
        SendCommandError: If sending the initial 'stop' command fails.
        CommandNotFoundError: If required external commands are missing.
        ServerNotFoundError: If the server executable cannot be found (for checks).
        MissingArgumentError: If server_name is empty.
        FileOperationError: If essential settings (BASE_DIR, _config_dir) are missing.
    """
    # _get_server_details also validates executable existence, which is implicitly
    # part of the original BedrockServer's state.
    details = _get_server_details(server_name, server_path_override)
    # server_name = details["server_name"]
    # server_dir = details["server_dir"] (used by system_windows._windows_stop_server)
    # server_config_dir = details["server_config_dir"] (used by system_windows._windows_stop_server)
    # config_dir_base = details["config_dir_base"] (used for manage_server_config)

    if not check_if_server_is_running(server_name):
        logger.info(
            f"Attempted to stop server '{server_name}', but it is not currently running."
        )
        if (
            manage_server_config(
                server_name, "status", "read", config_dir=details["config_dir_base"]
            )
            != "STOPPED"
        ):
            manage_server_config(
                server_name,
                "status",
                "write",
                "STOPPED",
                config_dir=details["config_dir_base"],
            )
        return

    manage_server_config(
        server_name,
        "status",
        "write",
        "STOPPING",
        config_dir=details["config_dir_base"],
    )
    logger.info(f"Attempting to stop server '{server_name}'...")

    os_name = platform.system()
    stop_initiated_by_systemd = False  # Specific to systemd stop path

    if os_name == "Linux":
        try:
            logger.info("Sending 'stop' command to server process...")
            send_server_command(server_name, "stop")  # Uses the new standalone function
            # If send_server_command succeeds, we consider stop initiated for the wait loop.
        except (SendCommandError, ServerNotRunningError, CommandNotFoundError) as e:
            logger.error(
                f"Failed to send 'stop' command to server '{server_name}': {e}. Will attempt process termination.",
                exc_info=True,
            )
        except Exception as e:  # Catch other errors from send_server_command
            logger.error(
                f"Unexpected error sending 'stop' command to server '{server_name}': {e}. Will attempt process termination.",
                exc_info=True,
            )

    elif os_name == "Windows":
        try:
            system_windows._windows_stop_server(
                server_name, details["server_dir"], details["server_config_dir"]
            )
            # Assume this function either succeeds in initiating stop or raises an error
        except Exception as e:  # Catch errors from _windows_stop_server
            logger.error(
                f"Failed to stop server on Windows for '{server_name}': {e}",
                exc_info=True,
            )
            # Depending on the error, we might want to raise or let the timeout handle it.
            # For now, let the timeout proceed.
            manage_server_config(
                server_name,
                "status",
                "write",
                "ERROR",
                config_dir=details["config_dir_base"],
            )
            raise ServerStopError(
                f"Failed to initiate stop for server '{server_name}' on Windows: {e}"
            ) from e
    else:
        logger.error(
            f"Stopping server is not supported on this operating system: {os_name}"
        )
        manage_server_config(
            server_name,
            "status",
            "write",
            "ERROR",
            config_dir=details["config_dir_base"],
        )
        raise ServerStopError(f"Unsupported operating system: {os_name}")

    attempts = 0
    max_attempts = settings.get("SERVER_STOP_TIMEOUT_SEC", 60) // 2
    sleep_interval = 2
    logger.info(
        f"Waiting up to {max_attempts * sleep_interval} seconds for server '{server_name}' process to terminate..."
    )

    while attempts < max_attempts:
        if not check_if_server_is_running(server_name):
            manage_server_config(
                server_name,
                "status",
                "write",
                "STOPPED",
                config_dir=details["config_dir_base"],
            )
            logger.info(f"Server '{server_name}' stopped successfully.")
            if os_name == "Linux" and not stop_initiated_by_systemd:
                screen_session_name = f"bedrock-{server_name}"
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
                    pass
            return

        logger.debug(
            f"Waiting for server '{server_name}' to stop... (Check {attempts + 1}/{max_attempts})"
        )
        time.sleep(sleep_interval)
        attempts += 1

    logger.error(
        f"Server '{server_name}' failed to stop within the timeout ({max_attempts * sleep_interval} seconds). Process might still be running."
    )
    manage_server_config(
        server_name, "status", "write", "ERROR", config_dir=details["config_dir_base"]
    )
    raise ServerStopError(
        f"Server '{server_name}' failed to stop within the timeout. Manual intervention may be required."
    )


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
        if (
            value is None and key != "installed_version"
        ):  # Allow writing None for some keys if explicitly intended, but 'value' itself is expected.
            # This check was: if value is None: raise MissingArgumentError.
            # Let's refine it: for write operations, value is generally expected.
            # If a specific key *can* be None, the caller should pass None explicitly.
            # The original raise MissingArgumentError("Value is required for 'write' operation.") is generally correct.
            # The warning about writing None and then raising seems slightly contradictory.
            # Let's stick to the original: value is required.
            raise MissingArgumentError(
                f"Value is required for 'write' operation on key '{key}'."
            )

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
        FileOperationError: If settings (BACKUP_DIR, _config_dir) are missing.
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
            stop_server(server_name)  # Use standalone function
            logger.info(f"Server '{server_name}' stopped successfully.")
        else:
            logger.debug(f"Server '{server_name}' is not running.")
    except ServerNotFoundError:  # Raised by _get_server_details if exe is already gone
        logger.debug(
            "Server executable not found, cannot use stop_server standard procedure. Proceeding with deletion of remaining files."
        )
    except (
        ServerStopError,
        CommandNotFoundError,
        SendCommandError,
    ) as e:  # Errors from stop_server
        logger.error(
            f"Failed to stop server '{server_name}' before deletion: {e}. Deletion aborted.",
            exc_info=True,
        )
        raise DirectoryError(
            f"Failed to stop running server '{server_name}' before deletion."
        ) from e
    except Exception as e:  # Other unexpected errors
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
        logger.info(f"Successfully deleted all data for server: '{server_name}'.")
