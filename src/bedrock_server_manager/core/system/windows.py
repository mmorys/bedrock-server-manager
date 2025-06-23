# bedrock_server_manager/core/system/windows.py
"""Provides Windows-specific implementations for system interactions.

This module includes functions for:
- Starting the Bedrock server process directly in the foreground.
- Managing a named pipe server for inter-process communication (IPC) to send
  commands to the running Bedrock server.
- Handling OS signals for graceful shutdown of the foreground server.
- Sending commands to the server via the named pipe.
- Stopping the server process by PID.

It relies on the optional `pywin32` package for named pipe functionality.
"""
import os
import threading
import time
import subprocess
import logging
import signal
import re
from typing import Optional, List, Dict, Any

# Third-party imports. pywin32 is optional but required for IPC.
try:
    import win32pipe
    import win32file
    import pywintypes

    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    win32pipe = None
    win32file = None
    pywintypes = None

# Local application imports.
from bedrock_server_manager.core.system import process as core_process
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    MissingArgumentError,
    ServerStartError,
    AppFileNotFoundError,
    ServerStopError,
    FileOperationError,
    SystemError,
    SendCommandError,
    ServerNotRunningError,
)

logger = logging.getLogger(__name__)

# --- Constants ---
BEDROCK_EXECUTABLE_NAME = "bedrock_server.exe"
PIPE_NAME_TEMPLATE = r"\\.\pipe\BedrockServerPipe_{server_name}"

# A global dictionary to keep track of running server processes and their control objects.
# This is used to manage the state of servers started in the foreground.
managed_bedrock_servers: Dict[str, Dict[str, Any]] = {}

# A module-level event to signal a shutdown for servers running in the foreground.
_foreground_server_shutdown_event = threading.Event()


def _handle_os_signals(sig, frame):
    """A signal handler for SIGINT to gracefully shut down a foreground server process."""
    logger.info(f"OS Signal {sig} received. Setting foreground shutdown event.")
    _foreground_server_shutdown_event.set()


def _handle_individual_pipe_client(
    pipe_handle, bedrock_process: subprocess.Popen, server_name_for_log: str
):
    """Handles I/O for a single connected named pipe client.

    This function runs in its own thread for each client that connects to the
    pipe server. It reads commands from the client and forwards them to the
    Bedrock server's standard input.

    Args:
        pipe_handle: The handle to the named pipe instance for this client.
        bedrock_process: The `subprocess.Popen` object for the Bedrock server.
        server_name_for_log: The name of the server, for logging purposes.
    """
    client_thread_name = threading.current_thread().name
    client_info = (
        f"client for server '{server_name_for_log}' (Handler {client_thread_name})"
    )
    logger.info(f"PIPE_CLIENT_HANDLER: Entered for {client_info}.")

    if not all([PYWIN32_AVAILABLE, win32file, bedrock_process]):
        logger.error(
            f"PIPE_CLIENT_HANDLER: Pre-requisites not met for {client_info}. Exiting."
        )
        if pipe_handle:
            try:
                win32file.CloseHandle(pipe_handle)
            except (pywintypes.error, AttributeError):
                pass
        return

    try:
        # Loop to read data as long as the server process is running.
        while bedrock_process.poll() is None:
            logger.debug(f"PIPE_CLIENT_HANDLER: Waiting for data from {client_info}...")
            hr, data_read = win32file.ReadFile(pipe_handle, 65535)

            if bedrock_process.poll() is not None:
                break

            if hr == 0:  # Read success.
                command_str = data_read.decode("utf-8").strip()
                if not command_str:
                    logger.info(
                        f"PIPE_CLIENT_HANDLER: Client disconnected gracefully from {client_info}."
                    )
                    break

                logger.info(
                    f"PIPE_CLIENT_HANDLER: Received command from {client_info}: '{command_str}'"
                )
                try:
                    # Forward the command to the Bedrock server's stdin.
                    if bedrock_process.stdin and not bedrock_process.stdin.closed:
                        bedrock_process.stdin.write(
                            (command_str + "\n").encode("utf-8")
                        )
                        bedrock_process.stdin.flush()
                    else:
                        logger.warning(
                            f"PIPE_CLIENT_HANDLER: Stdin for server '{server_name_for_log}' is closed."
                        )
                        break
                except (OSError, ValueError) as e_write:
                    logger.error(
                        f"PIPE_CLIENT_HANDLER: Error writing to stdin for '{server_name_for_log}': {e_write}."
                    )
                    break
            elif hr == 109:  # ERROR_BROKEN_PIPE
                logger.info(
                    f"PIPE_CLIENT_HANDLER: Pipe broken for {client_info}. Client disconnected."
                )
                break
            else:
                logger.error(
                    f"PIPE_CLIENT_HANDLER: Pipe ReadFile error for {client_info}, hr: {hr}. Closing."
                )
                break
    except pywintypes.error as e_pywin:
        if e_pywin.winerror in (109, 233):  # Broken pipe or not connected.
            logger.info(
                f"PIPE_CLIENT_HANDLER: Pipe for {client_info} closed (winerror {e_pywin.winerror})."
            )
        else:
            logger.error(
                f"PIPE_CLIENT_HANDLER: pywintypes.error for {client_info}: {e_pywin}",
                exc_info=True,
            )
    except Exception as e_unexp:
        logger.error(
            f"PIPE_CLIENT_HANDLER: Unexpected error for {client_info}: {e_unexp}",
            exc_info=True,
        )
    finally:
        # Ensure the pipe handle is properly closed.
        if all([PYWIN32_AVAILABLE, win32pipe, win32file, pipe_handle]):
            try:
                win32pipe.DisconnectNamedPipe(pipe_handle)
            except (pywintypes.error, AttributeError):
                pass
            try:
                win32file.CloseHandle(pipe_handle)
            except (pywintypes.error, AttributeError):
                pass
        logger.info(f"PIPE_CLIENT_HANDLER: Finished for {client_info}.")


def _main_pipe_server_listener_thread(
    pipe_name: str,
    bedrock_process: subprocess.Popen,
    server_name: str,
    overall_shutdown_event: threading.Event,
):
    """The main listener thread for a named pipe server.

    This thread runs a loop that creates new named pipe instances and waits for
    clients to connect. When a client connects, it spawns a new thread
    (`_handle_individual_pipe_client`) to handle that specific client, allowing
    for multiple concurrent connections.

    Args:
        pipe_name: The name of the pipe to create (e.g., `\\.\\pipe\\MyPipe`).
        bedrock_process: The `subprocess.Popen` object for the Bedrock server.
        server_name: The name of the server, for logging.
        overall_shutdown_event: A `threading.Event` that signals this thread to exit.
    """
    logger.info(f"MAIN_PIPE_LISTENER: Starting for pipe '{pipe_name}'.")

    if not all([PYWIN32_AVAILABLE, win32pipe, win32file, bedrock_process]):
        logger.error("MAIN_PIPE_LISTENER: Pre-requisites not met. Exiting.")
        overall_shutdown_event.set()
        return

    while not overall_shutdown_event.is_set() and bedrock_process.poll() is None:
        pipe_instance_handle = None
        try:
            # Create a new instance of the named pipe.
            pipe_instance_handle = win32pipe.CreateNamedPipe(
                pipe_name,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE
                | win32pipe.PIPE_READMODE_MESSAGE
                | win32pipe.PIPE_WAIT,
                win32pipe.PIPE_UNLIMITED_INSTANCES,
                65536,
                65536,
                0,
                None,
            )
            logger.info(
                f"MAIN_PIPE_LISTENER: Pipe instance created. Waiting for client..."
            )
            # Block until a client connects.
            win32pipe.ConnectNamedPipe(pipe_instance_handle, None)

            if overall_shutdown_event.is_set():
                break

            # Spawn a new thread to handle the connected client.
            logger.info(
                f"MAIN_PIPE_LISTENER: Client connected. Spawning handler thread."
            )
            client_handler_thread = threading.Thread(
                target=_handle_individual_pipe_client,
                args=(pipe_instance_handle, bedrock_process, server_name),
                daemon=True,
            )
            client_handler_thread.start()
            pipe_instance_handle = None  # The handler thread now owns the handle.
        except pywintypes.error as e:
            if overall_shutdown_event.is_set():
                break
            if e.winerror == 231:  # All pipes busy
                time.sleep(0.1)
            elif e.winerror == 2:  # Cannot create pipe
                logger.error(
                    f"MAIN_PIPE_LISTENER: Pipe '{pipe_name}' could not be created. Shutting down."
                )
                overall_shutdown_event.set()
            else:
                logger.warning(
                    f"MAIN_PIPE_LISTENER: pywintypes.error in main loop (winerror {e.winerror}): {e}"
                )
                time.sleep(0.5)
        except Exception as e:
            if overall_shutdown_event.is_set():
                break
            logger.error(f"MAIN_PIPE_LISTENER: Unexpected error: {e}", exc_info=True)
            time.sleep(1)
        finally:
            # Clean up the handle if it wasn't passed to a handler thread.
            if pipe_instance_handle and all([PYWIN32_AVAILABLE, win32file]):
                try:
                    win32file.CloseHandle(pipe_instance_handle)
                except (pywintypes.error, AttributeError):
                    pass

    logger.info(
        f"MAIN_PIPE_LISTENER: Main pipe listener thread for '{pipe_name}' has EXITED."
    )


def _windows_start_server(server_name: str, server_dir: str, config_dir: str) -> None:
    """Starts a Bedrock server in the foreground and manages its lifecycle on Windows.

        This is a blocking function that launches the server, creates a named pipe
        for command injection, writes a PID file, and waits for a shutdown
    -   signal (like Ctrl+C) before cleaning up.

        Args:
            server_name: The name of the server.
            server_dir: The server's installation directory.
            config_dir: The application's configuration directory for storing the PID file.

        Raises:
            SystemError: If the `pywin32` package is not installed.
            ServerStartError: If the server is already running or fails to start.
            AppFileNotFoundError: If the server executable is not found.
    """
    if not PYWIN32_AVAILABLE:
        raise SystemError(
            "The 'pywin32' package is required for Windows named pipe functionality."
        )
    if not all([server_name, server_dir, config_dir]):
        raise MissingArgumentError(
            "server_name, server_dir, and config_dir are required."
        )

    logger.info(
        f"Starting server '{server_name}' in FOREGROUND blocking mode (Windows)..."
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

    output_file = os.path.join(server_dir, "server_output.txt")

    # Set up a signal handler to catch Ctrl+C.
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _handle_os_signals)

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
            stdin=subprocess.PIPE,
            stdout=server_stdout_handle,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=0,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        logger.info(
            f"Bedrock Server '{server_name}' started with PID: {bedrock_process.pid}."
        )

        # --- Manage PID and Pipe ---
        # Write the new process ID to the PID file.
        server_pid_file_path = core_process.get_bedrock_server_pid_file_path(
            server_name, config_dir
        )
        core_process.write_pid_to_file(server_pid_file_path, bedrock_process.pid)

        # Start the listener thread for the named pipe.
        pipe_name = PIPE_NAME_TEMPLATE.format(
            server_name=re.sub(r"\W+", "_", server_name)
        )
        main_pipe_listener_thread_obj = threading.Thread(
            target=_main_pipe_server_listener_thread,
            args=(
                pipe_name,
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
            f"Failed to start server '{server_name}': {e_start}"
        ) from e_start
    finally:
        # --- Cleanup ---
        # This block ensures resources are cleaned up on shutdown.
        logger.info(f"Initiating cleanup for wrapper of '{server_name}'...")
        _foreground_server_shutdown_event.set()

        if main_pipe_listener_thread_obj and main_pipe_listener_thread_obj.is_alive():
            main_pipe_listener_thread_obj.join(timeout=3.0)

        # Gracefully stop the Bedrock server process if it's still running.
        if bedrock_process and bedrock_process.poll() is None:
            logger.info(f"Sending 'stop' command to Bedrock server '{server_name}'.")
            try:
                if bedrock_process.stdin and not bedrock_process.stdin.closed:
                    bedrock_process.stdin.write(b"stop\r\n")
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

        # Clean up the PID file.
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

        if server_name in managed_bedrock_servers:
            del managed_bedrock_servers[server_name]

        signal.signal(signal.SIGINT, original_sigint_handler)
        logger.info(f"Cleanup for server '{server_name}' finished.")


def _windows_send_command(server_name: str, command: str) -> None:
    """Sends a command to a running Bedrock server via its named pipe.

    Raises:
        SystemError: If the `pywin32` module is not installed.
        ServerNotRunningError: If the named pipe does not exist.
        SendCommandError: If writing to the pipe fails.
    """
    if not PYWIN32_AVAILABLE:
        raise SystemError("Cannot send command: 'pywin32' module not found.")
    if not all([server_name, command]):
        raise MissingArgumentError("server_name and command cannot be empty.")

    pipe_name = PIPE_NAME_TEMPLATE.format(server_name=re.sub(r"\W+", "_", server_name))
    handle = None
    try:
        # Connect to the existing named pipe.
        handle = win32file.CreateFile(
            pipe_name,
            win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        )
        win32pipe.SetNamedPipeHandleState(
            handle, win32pipe.PIPE_READMODE_MESSAGE, None, None
        )
        # Write the command to the pipe.
        win32file.WriteFile(handle, (command + "\r\n").encode("utf-8"))
        logger.info(f"Sent command '{command}' to server '{server_name}'.")
    except pywintypes.error as e:
        if e.winerror == 2:  # ERROR_FILE_NOT_FOUND
            raise ServerNotRunningError(
                f"Pipe '{pipe_name}' not found. Server likely not running."
            ) from e
        else:
            raise SendCommandError(
                f"Windows error sending command via '{pipe_name}': {e.strerror}"
            ) from e
    except Exception as e:
        raise SendCommandError(
            f"Unexpected error sending command via pipe '{pipe_name}': {e}"
        ) from e
    finally:
        # Ensure the handle is closed.
        if handle and all([PYWIN32_AVAILABLE, win32file]):
            try:
                win32file.CloseHandle(handle)
            except (pywintypes.error, AttributeError):
                pass


def _windows_stop_server_by_pid(server_name: str, config_dir: str) -> None:
    """Stops the Bedrock server on Windows by terminating its process via PID.

    This function reads the PID from the server's PID file and uses the
    `terminate_process_by_pid` utility to stop it.

    Args:
        server_name: The name of the server to stop.
        config_dir: The application's configuration directory.

    Raises:
        ServerStopError: If terminating the process fails.
    """
    if not all([server_name, config_dir]):
        raise MissingArgumentError("server_name and config_dir are required.")

    logger.info(f"Attempting to stop server '{server_name}' by PID on Windows...")

    try:
        pid_file_path = core_process.get_bedrock_server_pid_file_path(
            server_name, config_dir
        )
        pid_to_stop = core_process.read_pid_from_file(pid_file_path)

        if pid_to_stop is None:
            logger.info(
                f"No PID file for '{server_name}'. Assuming server is not running."
            )
            return

        if not core_process.is_process_running(pid_to_stop):
            logger.warning(
                f"Stale PID {pid_to_stop} found for '{server_name}'. Removing PID file."
            )
            core_process.remove_pid_file_if_exists(pid_file_path)
            return

        # If the process is running, terminate it.
        logger.info(
            f"Found running server '{server_name}' with PID {pid_to_stop}. Terminating..."
        )
        core_process.terminate_process_by_pid(pid_to_stop)

        # Clean up the PID file after successful termination.
        core_process.remove_pid_file_if_exists(pid_file_path)
        logger.info(
            f"Stop sequence for server '{server_name}' (PID {pid_to_stop}) completed."
        )

    except (AppFileNotFoundError, FileOperationError):
        logger.info(
            f"Could not find or read PID file for '{server_name}'. Assuming it's already stopped."
        )
    except (ServerStopError, SystemError) as e:
        # Re-raise as a ServerStopError to signal failure to the caller.
        raise ServerStopError(f"Failed to stop server '{server_name}': {e}") from e
