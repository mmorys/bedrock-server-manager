# bedrock_server_manager/core/system/linux.py
"""Provides Linux-specific implementations for system interactions.

This module includes functions for managing systemd user services (create,
enable, disable, check) for Bedrock servers. It also provides the logic for
starting a server in a blocking foreground mode, using a named pipe (FIFO)
for inter-process communication to send commands, and handling OS signals for
graceful shutdown.
"""

import platform
import os
import re
import signal
import threading
import logging
import subprocess
import shutil
import time
from typing import Optional

# Local application imports.
from bedrock_server_manager.core.system import process as core_process
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    CommandNotFoundError,
    ServerNotRunningError,
    SendCommandError,
    SystemError,
    ServerStartError,
    ServerStopError,
    MissingArgumentError,
    PermissionsError,
    FileOperationError,
    AppFileNotFoundError,
)

logger = logging.getLogger(__name__)


# --- Systemd Service Management ---
def get_systemd_user_service_file_path(service_name_full: str) -> str:
    """Generates the standard path for a given systemd user service file.

    Args:
        service_name_full: The full name of the service, with or without the
            `.service` suffix (e.g., "my-app.service" or "my-app").

    Returns:
        The absolute path to where the user service file should be located.

    Raises:
        MissingArgumentError: If `service_name_full` is empty.
    """
    if not service_name_full:
        raise MissingArgumentError("Full service name cannot be empty.")

    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    # User service files are typically located in ~/.config/systemd/user/
    return os.path.join(
        os.path.expanduser("~"), ".config", "systemd", "user", name_to_use
    )


def check_service_exists(service_name_full: str) -> bool:
    """Checks if a systemd user service file exists.

    Args:
        service_name_full: The full name of the service to check.

    Returns:
        True if the service file exists, False otherwise. Returns False
        on non-Linux systems.

    Raises:
        MissingArgumentError: If `service_name_full` is empty.
    """
    if platform.system() != "Linux":
        return False
    if not service_name_full:
        raise MissingArgumentError(
            "Full service name cannot be empty for service file check."
        )

    service_file_path = get_systemd_user_service_file_path(service_name_full)
    logger.debug(
        f"Checking for systemd user service file existence: '{service_file_path}'"
    )
    return os.path.isfile(service_file_path)


def create_systemd_service_file(
    service_name_full: str,
    description: str,
    working_directory: str,
    exec_start_command: str,
    exec_stop_command: Optional[str] = None,
    exec_start_pre_command: Optional[str] = None,
    service_type: str = "forking",
    restart_policy: str = "on-failure",
    restart_sec: int = 10,
    after_targets: str = "network.target",
) -> None:
    """Creates or updates a generic systemd user service file.

    After creating the file, it reloads the systemd daemon to recognize it.

    Args:
        service_name_full: The full name of the service (e.g., "my-app.service").
        description: A description for the service unit.
        working_directory: The `WorkingDirectory` for the service.
        exec_start_command: The command for `ExecStart`.
        exec_stop_command: Optional command for `ExecStop`.
        exec_start_pre_command: Optional command for `ExecStartPre`.
        service_type: The systemd service type (e.g., "simple", "forking").
        restart_policy: The systemd `Restart` policy (e.g., "on-failure").
        restart_sec: Seconds to wait before restarting.
        after_targets: Targets this service should start after (e.g., "network.target").

    Raises:
        MissingArgumentError: If required arguments are missing.
        AppFileNotFoundError: If `working_directory` does not exist.
        FileOperationError: If creating directories or writing the file fails.
        CommandNotFoundError: If `systemctl` is not found.
        SystemError: If reloading the systemd daemon fails.
    """
    if platform.system() != "Linux":
        logger.warning(
            f"Generic systemd service creation skipped: Not Linux. Service: '{service_name_full}'"
        )
        return

    if not all([service_name_full, description, working_directory, exec_start_command]):
        raise MissingArgumentError(
            "service_name_full, description, working_directory, and exec_start_command are required."
        )
    if not os.path.isdir(working_directory):
        raise AppFileNotFoundError(working_directory, "WorkingDirectory")

    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    systemd_user_dir = os.path.join(
        os.path.expanduser("~"), ".config", "systemd", "user"
    )
    service_file_path = os.path.join(systemd_user_dir, name_to_use)

    logger.info(
        f"Creating/Updating generic systemd user service file: '{service_file_path}'"
    )

    try:
        os.makedirs(systemd_user_dir, exist_ok=True)
    except OSError as e:
        raise FileOperationError(
            f"Failed to create systemd user directory '{systemd_user_dir}': {e}"
        ) from e

    # Build the service file content.
    exec_start_pre_line = (
        f"ExecStartPre={exec_start_pre_command}" if exec_start_pre_command else ""
    )
    exec_stop_line = f"ExecStop={exec_stop_command}" if exec_stop_command else ""

    service_content = f"""[Unit]
Description={description}
After={after_targets}

[Service]
Type={service_type}
WorkingDirectory={working_directory}
{exec_start_pre_line}
ExecStart={exec_start_command}
{exec_stop_line}
Restart={restart_policy}
RestartSec={restart_sec}s

[Install]
WantedBy=default.target
"""
    # Remove empty lines that might occur if optional commands are not provided.
    service_content = "\n".join(
        [line for line in service_content.splitlines() if line.strip()]
    )

    try:
        with open(service_file_path, "w", encoding="utf-8") as f:
            f.write(service_content)
        logger.info(
            f"Successfully wrote generic systemd service file: {service_file_path}"
        )
    except OSError as e:
        raise FileOperationError(
            f"Failed to write service file '{service_file_path}': {e}"
        ) from e

    # Reload systemd daemon to recognize the new/updated file.
    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        raise CommandNotFoundError("systemctl")
    try:
        subprocess.run(
            [systemctl_cmd, "--user", "daemon-reload"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(
            f"Systemd user daemon reloaded successfully for service '{name_to_use}'."
        )
    except subprocess.CalledProcessError as e:
        raise SystemError(
            f"Failed to reload systemd user daemon. Error: {e.stderr}"
        ) from e


def enable_systemd_service(service_name_full: str) -> None:
    """Enables a generic systemd user service to start on login.

    Raises:
        CommandNotFoundError: If `systemctl` is not found.
        SystemError: If the service file does not exist or the enable command fails.
    """
    if platform.system() != "Linux":
        return
    if not service_name_full:
        raise MissingArgumentError("Full service name cannot be empty.")
    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    logger.info(f"Enabling systemd user service '{name_to_use}'...")

    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        raise CommandNotFoundError("systemctl")

    if not check_service_exists(name_to_use):
        raise SystemError(
            f"Cannot enable: Systemd service file for '{name_to_use}' does not exist."
        )

    # Check if already enabled to avoid unnecessary calls.
    try:
        process = subprocess.run(
            [systemctl_cmd, "--user", "is-enabled", name_to_use],
            capture_output=True,
            text=True,
            check=False,
        )
        status_output = process.stdout.strip()
        logger.debug(
            f"'systemctl is-enabled {name_to_use}' status: {status_output}, return code: {process.returncode}"
        )
        if status_output == "enabled":
            logger.info(f"Service '{name_to_use}' is already enabled.")
            return
    except Exception as e:
        logger.warning(
            f"Could not reliably determine if service '{name_to_use}' is enabled: {e}. Attempting enable anyway.",
            exc_info=True,
        )

    try:
        subprocess.run(
            [systemctl_cmd, "--user", "enable", name_to_use],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Systemd service '{name_to_use}' enabled successfully.")
    except subprocess.CalledProcessError as e:
        raise SystemError(
            f"Failed to enable systemd service '{name_to_use}'. Error: {e.stderr}"
        ) from e


def disable_systemd_service(service_name_full: str) -> None:
    """Disables a generic systemd user service from starting on login.

    Raises:
        CommandNotFoundError: If `systemctl` is not found.
        SystemError: If the disable command fails.
    """
    if platform.system() != "Linux":
        return
    if not service_name_full:
        raise MissingArgumentError("Full service name cannot be empty.")
    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    logger.info(f"Disabling systemd user service '{name_to_use}'...")

    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        raise CommandNotFoundError("systemctl")

    if not check_service_exists(name_to_use):
        logger.debug(
            f"Service file for '{name_to_use}' does not exist. Assuming already disabled/removed."
        )
        return

    # Check if already disabled.
    try:
        process = subprocess.run(
            [systemctl_cmd, "--user", "is-enabled", name_to_use],
            capture_output=True,
            text=True,
            check=False,
        )
        status_output = process.stdout.strip()
        logger.debug(
            f"'systemctl is-enabled {name_to_use}' status: {status_output}, return code: {process.returncode}"
        )
        if status_output != "enabled":
            logger.info(
                f"Service '{name_to_use}' is already disabled or not in an enabled state."
            )
            return
    except Exception as e:
        logger.warning(
            f"Could not reliably determine if service '{name_to_use}' is enabled: {e}. Attempting disable anyway.",
            exc_info=True,
        )

    try:
        subprocess.run(
            [systemctl_cmd, "--user", "disable", name_to_use],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Systemd service '{name_to_use}' disabled successfully.")
    except subprocess.CalledProcessError as e:
        # It's not an error if the service is static or masked.
        if "static" in (e.stderr or "").lower() or "masked" in (e.stderr or "").lower():
            logger.info(
                f"Service '{name_to_use}' is static or masked, cannot be disabled via 'disable'."
            )
            return
        raise SystemError(
            f"Failed to disable systemd service '{name_to_use}'. Error: {e.stderr}"
        ) from e


# --- Constants ---
BEDROCK_EXECUTABLE_NAME = "bedrock_server"
PIPE_NAME_TEMPLATE = "/tmp/BedrockServerPipe_{server_name}"

# A module-level event to signal shutdown for servers running in the foreground.
_foreground_server_shutdown_event = threading.Event()


def _handle_os_signals(sig, frame):
    """A signal handler for SIGINT and SIGTERM to gracefully shut down a foreground server."""
    logger.info(f"OS Signal {sig} received. Setting foreground shutdown event.")
    _foreground_server_shutdown_event.set()


def _main_pipe_server_listener_thread(
    pipe_path: str,
    bedrock_process: subprocess.Popen,
    server_name: str,
    overall_shutdown_event: threading.Event,
):
    """A thread that listens on a named pipe (FIFO) for commands.

    This allows other processes to send commands to the Bedrock server process
    by writing to the pipe. It runs in a loop, handling one client connection
    at a time until the shutdown event is set.

    Args:
        pipe_path: The filesystem path to the named pipe.
        bedrock_process: The `subprocess.Popen` object for the Bedrock server.
        server_name: The name of the server, for logging.
        overall_shutdown_event: A `threading.Event` that signals this thread to exit.
    """
    logger.info(f"MAIN_PIPE_LISTENER: Starting for pipe '{pipe_path}'.")

    while not overall_shutdown_event.is_set() and bedrock_process.poll() is None:
        try:
            logger.info(
                f"MAIN_PIPE_LISTENER: Waiting for a client to connect to '{pipe_path}'..."
            )
            # Opening the pipe in read mode blocks until a client opens it for writing.
            with open(pipe_path, "r") as pipe_file:
                logger.info(f"MAIN_PIPE_LISTENER: Client connected to '{pipe_path}'.")
                # Read commands line by line from the pipe.
                for command_str in pipe_file:
                    if overall_shutdown_event.is_set():
                        break
                    command_str = command_str.strip()
                    if not command_str:
                        continue

                    # Forward the received command to the Bedrock server's stdin.
                    logger.info(
                        f"MAIN_PIPE_LISTENER: Received command: '{command_str}'"
                    )
                    if bedrock_process.stdin and not bedrock_process.stdin.closed:
                        bedrock_process.stdin.write(
                            (command_str + "\n").encode("utf-8")
                        )
                        bedrock_process.stdin.flush()
                    else:
                        logger.warning(
                            f"MAIN_PIPE_LISTENER: Stdin for server '{server_name}' is closed."
                        )
                        break
            if not overall_shutdown_event.is_set():
                logger.info(
                    f"MAIN_PIPE_LISTENER: Client disconnected. Awaiting next connection."
                )
        except Exception as e:
            if overall_shutdown_event.is_set():
                break
            logger.error(
                f"MAIN_PIPE_LISTENER: Unexpected error for '{pipe_path}': {e}",
                exc_info=True,
            )
            time.sleep(1)

    logger.info(
        f"MAIN_PIPE_LISTENER: Main pipe listener thread for '{pipe_path}' has EXITED."
    )


def _linux_start_server(server_name: str, server_dir: str, config_dir: str) -> None:
    """Starts a Bedrock server in the foreground and manages its lifecycle.

    This is a blocking function that launches the server, creates a named pipe
    (FIFO) for command injection, writes a PID file, and waits for a shutdown
    signal (like Ctrl+C) before cleaning up.

    Args:
        server_name: The name of the server.
        server_dir: The server's installation directory.
        config_dir: The application's configuration directory for storing the PID file.

    Raises:
        ServerStartError: If the server is already running or fails to start.
        AppFileNotFoundError: If the server executable is not found.
        PermissionsError: If the server executable is not executable.
        SystemError: If creating the named pipe fails.
    """
    if not all([server_name, server_dir, config_dir]):
        raise MissingArgumentError(
            "server_name, server_dir, and config_dir are required."
        )

    logger.info(
        f"Starting server '{server_name}' in FOREGROUND blocking mode (Linux)..."
    )
    _foreground_server_shutdown_event.clear()

    # --- Pre-start Check ---
    # Verify no other instance of this server is running.
    if core_process.get_verified_bedrock_process(server_name, server_dir, config_dir):
        msg = f"Server '{server_name}' appears to be already running and verified. Aborting start."
        logger.warning(msg)
        raise ServerStartError(msg)
    else:
        # Clean up any stale PID file from a previous unclean shutdown.
        try:
            server_pid_file_path = core_process.get_bedrock_server_pid_file_path(
                server_name, config_dir
            )
            core_process.remove_pid_file_if_exists(server_pid_file_path)
            # Also clean up stale LAUNCHER PID file if this is a direct start
            launcher_pid_file_path = core_process.get_bedrock_launcher_pid_file_path(
                server_name, config_dir
            )
            core_process.remove_pid_file_if_exists(launcher_pid_file_path)
        except Exception as e:
            logger.warning(
                f"Could not clean up stale PID files for '{server_name}': {e}. Proceeding."
            )

    # --- Setup ---
    server_exe_path = os.path.join(server_dir, BEDROCK_EXECUTABLE_NAME)
    if not os.path.isfile(server_exe_path):
        raise AppFileNotFoundError(server_exe_path, "Server executable")
    if not os.access(server_exe_path, os.X_OK):
        raise PermissionsError(
            f"Server executable is not executable: {server_exe_path}"
        )

    output_file = os.path.join(server_dir, "server_output.txt")
    pipe_path = PIPE_NAME_TEMPLATE.format(server_name=re.sub(r"\W+", "_", server_name))

    # Setup OS signal handlers and the named pipe for communication.
    signal.signal(signal.SIGINT, _handle_os_signals)
    signal.signal(signal.SIGTERM, _handle_os_signals)
    try:
        if os.path.exists(pipe_path):
            os.remove(pipe_path)
        os.mkfifo(pipe_path, mode=0o600)
    except OSError as e:
        raise SystemError(f"Failed to create named pipe '{pipe_path}': {e}") from e

    bedrock_process: Optional[subprocess.Popen] = None
    server_stdout_handle = None
    main_pipe_listener_thread_obj: Optional[threading.Thread] = None

    try:
        # --- Launch Process ---
        # Redirect stdout/stderr to a log file.
        with open(output_file, "wb") as f:
            f.write(f"Starting Bedrock Server '{server_name}'...\n".encode("utf-8"))
        server_stdout_handle = open(output_file, "ab")

        # Launch the Bedrock server executable as a subprocess.
        bedrock_process = subprocess.Popen(
            [server_exe_path],
            cwd=server_dir,
            env={**os.environ, "LD_LIBRARY_PATH": "."},
            stdin=subprocess.PIPE,
            stdout=server_stdout_handle,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=0,
        )
        logger.info(
            f"Bedrock Server '{server_name}' started with PID: {bedrock_process.pid}."
        )

        # --- Manage PID and Pipe ---
        # Write the new process ID to the PID file.
        pid_file_path = core_process.get_bedrock_server_pid_file_path(
            server_name, config_dir
        )
        core_process.write_pid_to_file(pid_file_path, bedrock_process.pid)

        # Start the listener thread for the named pipe.
        main_pipe_listener_thread_obj = threading.Thread(
            target=_main_pipe_server_listener_thread,
            args=(
                pipe_path,
                bedrock_process,
                server_name,
                _foreground_server_shutdown_event,
            ),
            daemon=True,
        )
        main_pipe_listener_thread_obj.start()

        # --- Main Blocking Loop ---
        # This loop keeps the main thread alive, waiting for a shutdown signal.
        logger.info(
            f"Server '{server_name}' is running. Holding console. Press Ctrl+C to stop."
        )
        while (
            not _foreground_server_shutdown_event.is_set()
            and bedrock_process.poll() is None
        ):
            try:
                _foreground_server_shutdown_event.wait(timeout=1.0)
            except KeyboardInterrupt:
                _foreground_server_shutdown_event.set()

        # If the server process terminates on its own, trigger a shutdown.
        if bedrock_process.poll() is not None:
            logger.warning(
                f"Bedrock server '{server_name}' terminated unexpectedly. Shutting down."
            )
            _foreground_server_shutdown_event.set()

    except Exception as e_start:
        raise ServerStartError(
            f"Failed to start or manage server '{server_name}': {e_start}"
        ) from e_start
    finally:
        # --- Cleanup ---
        # This block ensures resources are cleaned up on shutdown.
        logger.info(f"Initiating cleanup for wrapper of '{server_name}'...")
        _foreground_server_shutdown_event.set()

        # Unblock the pipe listener thread so it can exit cleanly.
        try:
            with open(pipe_path, "w") as f:
                pass
        except OSError:
            pass
        if main_pipe_listener_thread_obj and main_pipe_listener_thread_obj.is_alive():
            main_pipe_listener_thread_obj.join(timeout=3.0)

        # Gracefully stop the Bedrock server process if it's still running.
        if bedrock_process and bedrock_process.poll() is None:
            logger.info(f"Sending 'stop' command to Bedrock server '{server_name}'.")
            try:
                if bedrock_process.stdin and not bedrock_process.stdin.closed:
                    bedrock_process.stdin.write(b"stop\n")
                    bedrock_process.stdin.flush()
                    bedrock_process.stdin.close()
                bedrock_process.wait(
                    timeout=settings.get("SERVER_STOP_TIMEOUT_SEC", 30)
                )
            except (subprocess.TimeoutExpired, OSError, ValueError):
                logger.warning(
                    f"Graceful stop failed for '{server_name}'. Terminating process."
                )
                core_process.terminate_process_by_pid(bedrock_process.pid)

        # Clean up the PID and pipe files.
        try:
            # Clean up SERVER PID file
            server_pid_file_path_final = core_process.get_bedrock_server_pid_file_path(
                server_name, config_dir
            )
            core_process.remove_pid_file_if_exists(server_pid_file_path_final)
        except Exception as e:
            logger.debug(f"Could not remove PID files during final cleanup: {e}")

        # Close file handles and reset signal handlers.
        if server_stdout_handle and not server_stdout_handle.closed:
            server_stdout_handle.close()

        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        logger.info(f"Cleanup for server '{server_name}' finished.")


def _linux_send_command(server_name: str, command: str) -> None:
    """Sends a command to a running Bedrock server via its named pipe (FIFO).

    Raises:
        ServerNotRunningError: If the named pipe does not exist.
        SendCommandError: If writing to the pipe fails.
    """
    if not all([server_name, command]):
        raise MissingArgumentError("server_name and command cannot be empty.")

    pipe_path = PIPE_NAME_TEMPLATE.format(server_name=re.sub(r"\W+", "_", server_name))
    if not os.path.exists(pipe_path):
        raise ServerNotRunningError(
            f"Pipe '{pipe_path}' not found. Server likely not running."
        )

    try:
        with open(pipe_path, "w") as pipe_file:
            pipe_file.write(command + "\n")
            pipe_file.flush()
        logger.info(f"Sent command '{command}' to server '{server_name}'.")
    except (FileNotFoundError, BrokenPipeError) as e:
        raise ServerNotRunningError(
            f"Pipe '{pipe_path}' disconnected. Server likely not running."
        ) from e
    except OSError as e:
        raise SendCommandError(f"Failed to send command to '{pipe_path}': {e}") from e


def _linux_stop_server(server_name: str, config_dir: str) -> None:
    """Stops the Bedrock server by sending a 'stop' command or terminating its PID.

    This function first attempts a graceful shutdown by sending the 'stop'
    command via the named pipe. If that fails, it falls back to finding the
    process ID from the PID file and terminating it directly.

    Args:
        server_name: The name of the server to stop.
        config_dir: The application's configuration directory.

    Raises:
        ServerStopError: If terminating the process by PID fails.
    """
    if not all([server_name, config_dir]):
        raise MissingArgumentError("server_name and config_dir are required.")

    logger.info(f"Attempting to stop server '{server_name}' on Linux...")

    # First, try the graceful 'stop' command via the pipe.
    try:
        _linux_send_command(server_name, "stop")
        logger.info(
            f"'stop' command sent to '{server_name}'. Please allow time for it to shut down."
        )
        return
    except ServerNotRunningError:
        logger.warning(
            f"Could not send 'stop' command because pipe not found. Attempting to stop by PID."
        )
    except SendCommandError as e:
        logger.error(
            f"Failed to send 'stop' command to '{server_name}': {e}. Attempting to stop by PID."
        )

    # If sending the command fails, fall back to PID termination.
    try:
        pid_file_path = core_process.get_bedrock_server_pid_file_path(
            server_name, config_dir
        )
        pid_to_stop = core_process.read_pid_from_file(pid_file_path)

        if pid_to_stop is None or not core_process.is_process_running(pid_to_stop):
            logger.info(
                f"No running process found for PID from file. Cleaning up stale PID file if it exists."
            )
            core_process.remove_pid_file_if_exists(pid_file_path)
            return

        logger.info(
            f"Found running server '{server_name}' with PID {pid_to_stop}. Terminating process..."
        )
        core_process.terminate_process_by_pid(pid_to_stop)
        core_process.remove_pid_file_if_exists(pid_file_path)
        logger.info(f"Stop-by-PID sequence for server '{server_name}' completed.")

    except (AppFileNotFoundError, FileOperationError):
        logger.info(f"No PID file found for '{server_name}'. Assuming already stopped.")
    except (ServerStopError, SystemError) as e:
        raise ServerStopError(
            f"Failed to stop server '{server_name}' by PID: {e}"
        ) from e
