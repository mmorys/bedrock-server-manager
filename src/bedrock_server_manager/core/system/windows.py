# bedrock_server_manager/core/system/windows.py
"""
Provides Windows-specific implementations for system interactions related to
the Bedrock server.

This module includes functions for:
- Starting the Bedrock server process directly in the foreground.
- Managing a named pipe server for inter-process communication (IPC) to send
  commands to the running Bedrock server.
- Handling OS signals for graceful shutdown of the foreground server.
- Sending commands to the server via the named pipe.
- Stopping the server process (currently unused/experimental).

It relies on `pywin32` for named pipe functionality and `psutil` (optional)
for some process details if used by other parts of the system.
"""
import os
import threading
import time
import subprocess
import logging
import signal
import re
from typing import Optional, List, Dict, Any

# Third-party imports
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

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

# Local imports
from bedrock_server_manager.core.system import process as core_process
from bedrock_server_manager.config.settings import settings
from ...error import (
    MissingArgumentError,
    ServerStartError,
    AppFileNotFoundError,
    ServerStopError,
    FileOperationError,
    SystemError,
    ServerProcessError,
    SendCommandError,
    ServerNotRunningError,
    PermissionsError,
)

logger = logging.getLogger(__name__)

# --- Constants ---
BEDROCK_EXECUTABLE_NAME = "bedrock_server.exe"
PIPE_NAME_TEMPLATE = r"\\.\pipe\BedrockServerPipe_{server_name}"

# Global dictionary to keep track of running server processes and their control objects
managed_bedrock_servers: Dict[str, Dict[str, Any]] = {}

# Module-level event to signal foreground mode shutdown (e.g., by Ctrl+C)
_foreground_server_shutdown_event = threading.Event()


def _handle_os_signals(sig, frame):
    """
    Signal handler for SIGINT and SIGTERM to gracefully shut down the
    foreground Bedrock server process started by `_windows_start_server`.
    Sets a global event that the main server loop checks.
    """
    logger.info(
        f"OS Signal {sig} received by _windows_start_server. Setting foreground shutdown event."
    )
    _foreground_server_shutdown_event.set()


def _get_server_pid_filename(server_name: str) -> str:
    """Generates a standardized PID filename for a given Bedrock server."""
    return f"bedrock_{server_name}.pid"


# --- Named Pipe Server Helper Functions ---
def _handle_individual_pipe_client(
    pipe_handle,  # Handle for this specific client connection
    bedrock_process: subprocess.Popen,
    server_name_for_log: str,
):
    """Handles I/O for a single connected pipe client. Runs in its own thread."""
    client_thread_name = threading.current_thread().name
    client_info = f"client for server '{server_name_for_log}' (Handler {client_thread_name}, PipeHandle {pipe_handle})"
    logger.info(f"PIPE_CLIENT_HANDLER: Entered for {client_info}.")

    if not PYWIN32_AVAILABLE or not win32file or not bedrock_process:
        logger.error(
            f"PIPE_CLIENT_HANDLER: Pre-requisites not met (pywin32, bedrock_process) for {client_info}. Exiting."
        )
        if pipe_handle:
            try:
                win32file.CloseHandle(pipe_handle)
            except pywintypes.error:
                pass
        return

    try:
        while True:
            if bedrock_process.poll() is not None:
                logger.info(
                    f"PIPE_CLIENT_HANDLER: Bedrock server '{server_name_for_log}' (PID {bedrock_process.pid}) terminated. Closing {client_info}."
                )
                break

            logger.debug(f"PIPE_CLIENT_HANDLER: Waiting for data from {client_info}...")
            hr, data_read = win32file.ReadFile(pipe_handle, 65535)  # Blocking read

            if bedrock_process.poll() is not None:  # Check again after blocking read
                logger.info(
                    f"PIPE_CLIENT_HANDLER: Bedrock server '{server_name_for_log}' terminated after pipe read. Closing {client_info}."
                )
                break

            if hr == 0:  # ReadFile success
                command_str = data_read.decode(
                    "utf-8"
                ).strip()  # Decode received bytes to string
                if not command_str:
                    logger.info(
                        f"PIPE_CLIENT_HANDLER: Received empty data from {client_info}. Assuming client disconnected gracefully."
                    )
                    break

                logger.info(
                    f"PIPE_CLIENT_HANDLER: Received command string from {client_info}: '{command_str}'"
                )
                try:
                    if bedrock_process.stdin and not bedrock_process.stdin.closed:
                        # Encode the string command to bytes (e.g., UTF-8) before writing
                        command_bytes = (command_str + "\n").encode("utf-8")
                        bedrock_process.stdin.write(command_bytes)
                        bedrock_process.stdin.flush()
                        logger.debug(
                            f"PIPE_CLIENT_HANDLER: Command '{command_str}' (as bytes) written to stdin of server '{server_name_for_log}'."
                        )
                    else:
                        logger.warning(
                            f"PIPE_CLIENT_HANDLER: Stdin for server '{server_name_for_log}' is closed. Cannot send. Closing {client_info}."
                        )
                        break
                except (OSError, ValueError) as e_write:
                    logger.error(
                        f"PIPE_CLIENT_HANDLER: Error writing command to Bedrock stdin for '{server_name_for_log}': {e_write}. Closing {client_info}."
                    )
                    break
            elif hr == 109:  # ERROR_BROKEN_PIPE specific to ReadFile
                logger.info(
                    f"PIPE_CLIENT_HANDLER: ReadFile indicated broken pipe (error 109) for {client_info}. Client disconnected."
                )
                break
            else:  # Other ReadFile errors
                logger.error(
                    f"PIPE_CLIENT_HANDLER: Pipe ReadFile error for {client_info}, hr: {hr}. Closing."
                )
                break
    except pywintypes.error as e_pywin:
        # Error 109: ERROR_BROKEN_PIPE (The pipe has been ended.) - client disconnected or server process died
        # Error 233: ERROR_PIPE_NOT_CONNECTED (client disconnected before read could happen)
        if PYWIN32_AVAILABLE and e_pywin.winerror in (109, 233):
            logger.info(
                f"PIPE_CLIENT_HANDLER: Pipe for {client_info} broke or not connected (winerror {e_pywin.winerror}). Client likely disconnected."
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
        if PYWIN32_AVAILABLE and win32pipe and win32file and pipe_handle:
            try:
                logger.debug(
                    f"PIPE_CLIENT_HANDLER: Disconnecting pipe for {client_info}."
                )
                win32pipe.DisconnectNamedPipe(pipe_handle)
            except pywintypes.error:
                pass
            try:
                logger.debug(
                    f"PIPE_CLIENT_HANDLER: Closing pipe handle for {client_info}."
                )
                win32file.CloseHandle(pipe_handle)
            except pywintypes.error:
                pass
        logger.info(f"PIPE_CLIENT_HANDLER: Finished for {client_info}.")


def _main_pipe_server_listener_thread(
    pipe_name: str,
    bedrock_process: subprocess.Popen,
    server_name_for_log: str,
    # This is the event from _windows_start_server's foreground blocking loop.
    # When this event is set, this listener thread should stop trying to create new pipes.
    overall_shutdown_event: threading.Event,
):
    """Main listener thread for named pipe. Creates pipe instances & spawns client handler threads."""
    main_listener_thread_name = threading.current_thread().name
    logger.info(
        f"MAIN_PIPE_LISTENER ({server_name_for_log}, {main_listener_thread_name}): Starting for pipe '{pipe_name}'."
    )

    if not PYWIN32_AVAILABLE or not win32pipe or not win32file or not bedrock_process:
        logger.error(
            f"MAIN_PIPE_LISTENER ({server_name_for_log}): Pre-requisites not met. Exiting."
        )
        overall_shutdown_event.set()  # Signal problem to the _windows_start_server loop
        return

    active_client_handler_threads: List[threading.Thread] = []

    while not overall_shutdown_event.is_set():
        pipe_instance_handle = None
        try:
            if bedrock_process.poll() is not None:
                logger.info(
                    f"MAIN_PIPE_LISTENER ({server_name_for_log}): Bedrock server (PID {bedrock_process.pid}) terminated. Stopping listener."
                )
                overall_shutdown_event.set()
                break

            logger.debug(
                f"MAIN_PIPE_LISTENER ({server_name_for_log}): Creating new pipe instance for '{pipe_name}'."
            )
            # Note: Using default timeout (50ms) for CreateNamedPipe can be problematic if system is slow.
            # NMPWAIT_USE_DEFAULT_WAIT is usually implied by 0 or certain values, or specific timeout.
            # For now, default timeout of 0 (wait indefinitely for system resources) is fine.
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
                None,  # Using 0 for default timeout of CreateNamedPipe
            )
            logger.info(
                f"MAIN_PIPE_LISTENER ({server_name_for_log}): Pipe instance '{pipe_name}' (handle {pipe_instance_handle}) created. Waiting for a client..."
            )

            if overall_shutdown_event.is_set():
                break

            win32pipe.ConnectNamedPipe(pipe_instance_handle, None)  # Blocking call

            if overall_shutdown_event.is_set():
                logger.info(
                    f"MAIN_PIPE_LISTENER ({server_name_for_log}): Shutdown after client connected to '{pipe_name}'. Not spawning handler."
                )
                break

            logger.info(
                f"MAIN_PIPE_LISTENER ({server_name_for_log}): Client connected to pipe instance '{pipe_name}'. Spawning client handler thread."
            )

            client_handler_thread = threading.Thread(
                target=_handle_individual_pipe_client,
                args=(pipe_instance_handle, bedrock_process, server_name_for_log),
                daemon=True,
            )
            client_handler_thread.start()
            active_client_handler_threads.append(client_handler_thread)
            pipe_instance_handle = (
                None  # Ownership transferred to client_handler_thread
            )

        except pywintypes.error as e:
            if overall_shutdown_event.is_set():
                break
            logger.warning(
                f"MAIN_PIPE_LISTENER ({server_name_for_log}): pywintypes.error in main loop for '{pipe_name}' (winerror {e.winerror}): {e}"
            )
            # Handle common errors more gracefully
            if e.winerror == 231:  # ERROR_PIPE_BUSY (All pipe instances are busy)
                logger.warning(
                    f"MAIN_PIPE_LISTENER ({server_name_for_log}): All pipe instances for '{pipe_name}' appear busy. Retrying shortly."
                )
                time.sleep(0.1)  # Brief pause
            elif (
                e.winerror == 2
            ):  # ERROR_FILE_NOT_FOUND (often when pipe cannot be created)
                logger.error(
                    f"MAIN_PIPE_LISTENER ({server_name_for_log}): Pipe '{pipe_name}' could not be created (Error 2). Critical. Shutting down listener."
                )
                overall_shutdown_event.set()  # Signal main foreground loop to stop
                break
            else:  # Other errors
                time.sleep(
                    0.5
                )  # Pause before retrying CreateNamedPipe after other errors
            if bedrock_process.poll() is not None:
                overall_shutdown_event.set()
                break
        except Exception as e:  # Catch any other unexpected error
            if overall_shutdown_event.is_set():
                break
            logger.error(
                f"MAIN_PIPE_LISTENER ({server_name_for_log}): Unexpected error in main listener for '{pipe_name}': {e}",
                exc_info=True,
            )
            if bedrock_process.poll() is not None:
                overall_shutdown_event.set()
                break
            time.sleep(1)
        finally:
            if pipe_instance_handle:  # If handle was created but not passed to a thread
                logger.debug(
                    f"MAIN_PIPE_LISTENER ({server_name_for_log}): Ensuring orphaned pipe instance for '{pipe_name}' is closed."
                )
                if PYWIN32_AVAILABLE and win32file:
                    try:
                        win32file.CloseHandle(pipe_instance_handle)
                    except pywintypes.error:
                        pass

    logger.info(
        f"MAIN_PIPE_LISTENER ({server_name_for_log}): Exiting for pipe '{pipe_name}'. Waiting for active client handler threads to complete..."
    )
    # Wait for any spawned client handler threads to finish (they are daemon, but good to try joining)
    # These threads should self-terminate if bedrock_process dies or pipe breaks.
    for t_idx, t in enumerate(active_client_handler_threads):
        if t.is_alive():
            logger.debug(
                f"MAIN_PIPE_LISTENER ({server_name_for_log}): Joining client handler thread {t_idx+1}/{len(active_client_handler_threads)}..."
            )
            t.join(timeout=1.0)
    logger.info(
        f"MAIN_PIPE_LISTENER ({server_name_for_log}): Main pipe listener thread for '{pipe_name}' has fully EXITED."
    )


def _windows_start_server(
    server_name: str,
    server_dir: str,
    config_dir: str,
) -> None:  # Returns None because it blocks and manages its own lifecycle
    """
    Starts Bedrock server on Windows in foreground, manages PID & named pipe. Blocks until shutdown.
    """
    if not PYWIN32_AVAILABLE:
        raise SystemError(
            "The 'pywin32' package is required for Windows named pipe functionality."
        )
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")
    if not config_dir:
        raise MissingArgumentError("Configuration directory cannot be empty.")

    logger.info(
        f"Starting server '{server_name}' in FOREGROUND blocking mode (Windows)..."
    )

    _foreground_server_shutdown_event.clear()

    original_sigint_handler = signal.getsignal(signal.SIGINT)
    original_sigterm_handler = None
    try:  # Ensure signal handlers are always restored
        signal.signal(signal.SIGINT, _handle_os_signals)
        if hasattr(signal, "SIGTERM"):
            original_sigterm_handler = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, _handle_os_signals)

        server_exe_path = os.path.join(server_dir, BEDROCK_EXECUTABLE_NAME)
        output_file = os.path.join(server_dir, "server_output.txt")

        if not os.path.isfile(server_exe_path):
            raise AppFileNotFoundError(server_exe_path, "Server executable")

        pid_filename = _get_server_pid_filename(server_name)
        pid_file_path = None
        try:
            pid_file_path = core_process.get_pid_file_path(config_dir, pid_filename)
        except AppFileNotFoundError as e:
            raise ServerStartError(
                f"Invalid config_dir for PID file of '{server_name}': {e}"
            ) from e

        # Pre-start PID check
        existing_pid = None
        try:
            existing_pid = core_process.read_pid_from_file(pid_file_path)
            if existing_pid and core_process.is_process_running(existing_pid):
                # Define custom verifier inside, so it has access to server_dir, BEDROCK_EXECUTABLE_NAME
                def _verify_bedrock_process_start(cmdline_args: List[str]) -> bool:
                    try:
                        if not PSUTIL_AVAILABLE or not psutil:
                            return False
                        p = psutil.Process(existing_pid)
                        # Check 1: Executable Path
                        actual_exe = p.cmdline()[0] if p.cmdline() else ""
                        expected_exe = os.path.join(server_dir, BEDROCK_EXECUTABLE_NAME)
                        if not (
                            os.path.realpath(actual_exe)
                            == os.path.realpath(expected_exe)
                            or os.path.basename(actual_exe)
                            == os.path.basename(expected_exe)
                        ):
                            return False
                        # Check 2: Current Working Directory
                        actual_cwd = p.cwd()
                        if not (
                            actual_cwd
                            and os.path.normpath(actual_cwd).lower()
                            == os.path.normpath(server_dir).lower()
                        ):
                            return False
                        return True
                    except (psutil.Error, OSError, IndexError):
                        return False

                core_process.verify_process_identity(
                    existing_pid,
                    custom_verification_callback=_verify_bedrock_process_start,
                )
                msg = f"Server '{server_name}' (PID {existing_pid}) appears to be already running and verified. Aborting start."
                logger.warning(msg)
                raise ServerStartError(msg)
            elif existing_pid:
                logger.warning(
                    f"Stale PID file '{pid_file_path}' (PID {existing_pid} not running). Removing."
                )
                core_process.remove_pid_file_if_exists(pid_file_path)
        except ServerProcessError:
            logger.warning(
                f"PID {existing_pid} from '{pid_file_path}' is running but NOT server '{server_name}' at '{server_dir}'. Removing stale PID file."
            )
            core_process.remove_pid_file_if_exists(pid_file_path)
        except FileOperationError as e:
            logger.warning(
                f"Problematic PID file '{pid_file_path}': {e}. Removing and proceeding."
            )
            core_process.remove_pid_file_if_exists(pid_file_path)
        except (SystemError, PermissionsError) as e:
            raise ServerStartError(
                f"Cannot check existing process for server '{server_name}': {e}"
            ) from e

        server_stdout_handle = None
        bedrock_process: Optional[subprocess.Popen] = None
        main_pipe_listener_thread_obj: Optional[threading.Thread] = (
            None  # Changed name for clarity
        )

        try:
            # Truncate/Create output file
            with open(output_file, "wb") as f:  # Open in write binary to truncate
                f.write(f"Starting Bedrock Server '{server_name}'...\n".encode("utf-8"))
            server_stdout_handle = open(output_file, "ab")  # Reopen in append binary

            bedrock_process = subprocess.Popen(
                [server_exe_path],
                cwd=server_dir,
                stdin=subprocess.PIPE,
                stdout=server_stdout_handle,
                stderr=subprocess.STDOUT,
                text=False,
                bufsize=0,
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True,
            )
            logger.info(
                f"Bedrock Server '{server_name}' started with PID: {bedrock_process.pid}. Output to '{output_file}'."
            )

            core_process.write_pid_to_file(pid_file_path, bedrock_process.pid)
            logger.debug(
                f"PID {bedrock_process.pid} for '{server_name}' written to '{pid_file_path}'."
            )

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
            logger.info(
                f"Main named pipe listener thread started for server '{server_name}' on pipe '{pipe_name}'."
            )

            managed_bedrock_servers[server_name] = {
                "process": bedrock_process,
                "pipe_main_thread": main_pipe_listener_thread_obj,  # Store the main listener thread
                "stdout_handle": server_stdout_handle,
                "pid_file_path": pid_file_path,
                "server_dir": server_dir,
                "config_dir": config_dir,
            }
            logger.info(
                f"Server '{server_name}' is running. Holding console. Press Ctrl+C to stop."
            )

            while not _foreground_server_shutdown_event.is_set():
                if bedrock_process.poll() is not None:
                    logger.warning(
                        f"Bedrock server process '{server_name}' (PID: {bedrock_process.pid}) terminated. Shutting down console hold."
                    )
                    _foreground_server_shutdown_event.set()
                    break
                try:
                    _foreground_server_shutdown_event.wait(timeout=1.0)
                except KeyboardInterrupt:
                    logger.info(
                        "KeyboardInterrupt caught in _windows_start_server main loop. Initiating shutdown."
                    )
                    _foreground_server_shutdown_event.set()
                    break

            logger.info(f"Foreground mode for server '{server_name}' is ending.")

        except ServerStartError:
            raise  # Re-raise if it's from pre-checks
        except FileOperationError as e_pid:
            if server_stdout_handle:
                server_stdout_handle.close()
            if bedrock_process and bedrock_process.poll() is None:
                try:
                    bedrock_process.terminate()
                    bedrock_process.wait(timeout=2)
                except Exception:
                    bedrock_process.kill()
            raise ServerStartError(
                f"PID write failed for '{server_name}': {e_pid}. Server terminated."
            ) from e_pid
        except Exception as e_start:
            if server_stdout_handle:
                server_stdout_handle.close()
            if bedrock_process and bedrock_process.poll() is None:
                bedrock_process.kill()
            raise ServerStartError(
                f"Failed to start or manage server '{server_name}': {e_start}"
            ) from e_start
        finally:
            logger.info(
                f"WINDOWS_START_SERVER: Initiating cleanup for wrapper of '{server_name}' (PID: {os.getpid()})..."
            )

            # Explicitly signal shutdown to ensure all threads get it
            _foreground_server_shutdown_event.set()

            if (
                main_pipe_listener_thread_obj
                and main_pipe_listener_thread_obj.is_alive()
            ):
                logger.debug(
                    f"Waiting for main pipe listener thread of '{server_name}' to join..."
                )
                main_pipe_listener_thread_obj.join(timeout=5.0)
                if main_pipe_listener_thread_obj.is_alive():
                    logger.warning(
                        f"Main pipe listener thread for '{server_name}' did not join cleanly."
                    )

            # Determine if bedrock_server.exe was (or should be) stopped by this wrapper's actions
            bedrock_server_should_be_stopped_by_this_wrapper = False
            if (
                bedrock_process
            ):  # bedrock_process is the Popen object for bedrock_server.exe
                if bedrock_process.poll() is not None:
                    # Bedrock server already terminated (either on its own or previously stopped)
                    logger.info(
                        f"Bedrock server process '{server_name}' (PID: {bedrock_process.pid}) already terminated with code {bedrock_process.returncode}."
                    )
                    bedrock_server_should_be_stopped_by_this_wrapper = (
                        True  # It's stopped, so cleanup is appropriate
                    )
                elif (
                    _foreground_server_shutdown_event.is_set()
                ):  # Check if shutdown was signaled
                    # This implies an intentional shutdown was requested for this wrapper and its managed server
                    logger.info(
                        f"Shutdown event was set. Ensuring Bedrock server process '{server_name}' (PID: {bedrock_process.pid}) is terminated."
                    )
                    bedrock_server_should_be_stopped_by_this_wrapper = True
                    try:
                        # Attempt graceful stop via stdin if pipe listener didn't already do it
                        if bedrock_process.stdin and not bedrock_process.stdin.closed:
                            try:
                                logger.debug(
                                    f"Attempting to send 'stop' command to Bedrock server PID {bedrock_process.pid} via its stdin during wrapper cleanup."
                                )
                                bedrock_process.stdin.write(b"stop\r\n")
                                bedrock_process.stdin.flush()
                                bedrock_process.stdin.close()
                                bedrock_process.wait(
                                    timeout=settings.get("SERVER_STOP_TIMEOUT_SEC", 60)
                                    // 3
                                )  # Shorter wait
                                logger.info(
                                    f"Bedrock server PID {bedrock_process.pid} processed 'stop' or exited."
                                )
                            except (
                                OSError,
                                ValueError,
                                BrokenPipeError,
                                subprocess.TimeoutExpired,
                            ) as e_stdin:
                                logger.warning(
                                    f"Attempt to send 'stop' via stdin failed or timed out during cleanup: {e_stdin}. Proceeding to terminate."
                                )

                        if bedrock_process.poll() is None:  # If still running
                            core_process.terminate_process_by_pid(bedrock_process.pid)
                            logger.info(
                                f"Bedrock server PID {bedrock_process.pid} terminated by wrapper cleanup."
                            )
                    except (ServerStopError, PermissionsError, SystemError) as e_term:
                        logger.error(
                            f"Error during final termination of Bedrock server '{server_name}' by wrapper: {e_term}"
                        )
                    except Exception as e_final_stop:
                        logger.error(
                            f"Unexpected error during final stop sequence of Bedrock server by wrapper: {e_final_stop}"
                        )

            # --- Conditional PID File Removal ---
            # pid_file_path is for bedrock_server.exe (e.g., bedrock_{server_name}.pid)
            if pid_file_path and os.path.exists(pid_file_path):
                pid_in_file = core_process.read_pid_from_file(pid_file_path)
                if pid_in_file is not None:
                    # Check if the process in the PID file is our bedrock_process and if it's actually stopped
                    is_actual_server_running_final_check = (
                        core_process.is_process_running(pid_in_file)
                    )

                    if bedrock_process and pid_in_file == bedrock_process.pid:
                        # It's the PID of the server we managed
                        if (
                            not is_actual_server_running_final_check
                            or bedrock_process.poll() is not None
                        ):
                            logger.info(
                                f"Bedrock server (PID {pid_in_file}) confirmed stopped. Removing PID file '{pid_file_path}'."
                            )
                            core_process.remove_pid_file_if_exists(pid_file_path)
                        elif bedrock_server_should_be_stopped_by_this_wrapper:
                            logger.warning(
                                f"Bedrock server (PID {pid_in_file}) was targeted for stop by wrapper. Removing PID file '{pid_file_path}' even if termination was problematic."
                            )
                            core_process.remove_pid_file_if_exists(pid_file_path)
                        else:
                            # Wrapper is exiting, but bedrock_server.exe it started is intended to continue (detached case)
                            logger.info(
                                f"Foreground wrapper for '{server_name}' exiting, but actual Bedrock server "
                                f"(PID {pid_in_file}) is (or expected to be) still running. "
                                f"PID file '{pid_file_path}' will NOT be removed by this wrapper."
                            )
                    elif not is_actual_server_running_final_check:
                        # PID in file is not running (and wasn't our bedrock_process or bedrock_process is None)
                        logger.info(
                            f"Process (PID {pid_in_file} from file) not running. Removing PID file '{pid_file_path}'."
                        )
                        core_process.remove_pid_file_if_exists(pid_file_path)
                    else:
                        # PID in file is running but isn't the bedrock_process this wrapper directly managed (e.g. stale, or other instance)
                        logger.warning(
                            f"PID {pid_in_file} in '{pid_file_path}' is running but not the direct child of this wrapper instance. Not removing."
                        )
                else:
                    logger.warning(
                        f"PID file '{pid_file_path}' unreadable/empty during cleanup. Removing by wrapper."
                    )
                    core_process.remove_pid_file_if_exists(pid_file_path)

            if server_stdout_handle and not server_stdout_handle.closed:
                server_stdout_handle.close()

            if server_name in managed_bedrock_servers:
                del managed_bedrock_servers[server_name]

            logger.info(
                f"WINDOWS_START_SERVER: Foreground wrapper for server '{server_name}' finished cleanup."
            )

    finally:  # Outermost finally to restore OS signal handlers
        signal.signal(signal.SIGINT, original_sigint_handler)
        if hasattr(signal, "SIGTERM") and original_sigterm_handler is not None:
            if original_sigterm_handler is not None:  # Ensure it was captured
                try:
                    signal.signal(signal.SIGTERM, original_sigterm_handler)
                except OSError:
                    pass
        _foreground_server_shutdown_event.clear()


def _windows_send_command(server_name: str, command: str) -> None:
    """
    Sends a command to a running Bedrock server via its named pipe.
    (Windows-specific)

    Args:
        server_name: The name of the server (used for pipe name).
        command: The command to send to the server.

    Raises:
        MissingArgumentError: If `server_name` or `command` is empty.
        SystemError: If 'pywin32' is not available.
        SendCommandError: If a pipe communication error occurs (e.g., pipe busy, pipe broken, other Windows errors).
        ServerNotRunningError: If the named pipe for the server is not found (server likely not running).
    """
    ERROR_FILE_NOT_FOUND = 2
    ERROR_PIPE_BUSY = 231
    ERROR_BROKEN_PIPE = 109

    if not server_name:
        raise MissingArgumentError("server_name cannot be empty.")
    if not command:
        raise MissingArgumentError("command cannot be empty.")

    if not PYWIN32_AVAILABLE:  # Assume PYWIN32_AVAILABLE is defined globally
        logger.error(
            "Cannot send command on Windows: Required 'pywin32' module is not installed."
        )
        raise SystemError("Cannot send command on Windows: 'pywin32' module not found.")

    pipe_name = rf"\\.\pipe\BedrockServerPipe_{server_name}"
    handle = win32file.INVALID_HANDLE_VALUE

    try:
        logger.debug(f"Attempting to connect to named pipe: {pipe_name}")
        handle = win32file.CreateFile(
            pipe_name,
            win32file.GENERIC_WRITE,
            0,  # No sharing
            None,  # Default security attributes
            win32file.OPEN_EXISTING,
            0,  # Default attributes
            None,  # No template file
        )

        if handle == win32file.INVALID_HANDLE_VALUE:
            last_error = (
                pywintypes.GetLastError()
            )  # Use this instead of e.winerror here
            logger.error(
                f"Could not open named pipe '{pipe_name}'. Server might not be running or pipe setup failed. "
                f"Windows Error Code: {last_error}"
            )
            if last_error == ERROR_FILE_NOT_FOUND:
                raise ServerNotRunningError(
                    f"Could not connect to server: Pipe '{pipe_name}' not found."
                ) from None  # No underlying pywintypes.error to chain here
            else:
                # For other errors from CreateFile (e.g. access denied), raise a more general SendCommandError
                raise SendCommandError(
                    f"Failed to open pipe '{pipe_name}'. Windows Error Code: {last_error}"
                ) from None

        # Set pipe to message mode
        win32pipe.SetNamedPipeHandleState(
            handle, win32pipe.PIPE_READMODE_MESSAGE, None, None
        )

        # Commands to Bedrock server usually expect a newline
        command_bytes = (command + "\r\n").encode("utf-8")
        logger.debug(
            f"Writing {len(command_bytes)} bytes to pipe '{pipe_name}': {command_bytes!r}"
        )
        win32file.WriteFile(handle, command_bytes)
        logger.info(
            f"Sent command '{command}' to server '{server_name}' via named pipe."
        )

    except pywintypes.error as e:
        win_error_code = e.winerror
        logger.error(
            f"Windows error during communication with pipe '{pipe_name}': Code {win_error_code} - {e.strerror}",
            exc_info=True,
        )
        if win_error_code == ERROR_FILE_NOT_FOUND:
            raise ServerNotRunningError(
                f"Pipe '{pipe_name}' does not exist or was closed. Server likely not running."
            ) from e
        elif win_error_code == ERROR_PIPE_BUSY:  # All pipe instances are busy
            raise SendCommandError(
                f"All pipe instances for '{pipe_name}' are busy. Try again later."
            ) from e
        elif win_error_code == ERROR_BROKEN_PIPE:  # The pipe has been ended.
            raise SendCommandError(
                f"Pipe connection to '{pipe_name}' broken (server may have closed it or crashed)."
            ) from e
        else:
            raise SendCommandError(
                f"Windows error sending command via '{pipe_name}': {e.strerror} (Code: {win_error_code})"
            ) from e
    except Exception as e:  # Catch any other unexpected errors
        logger.error(
            f"Unexpected error sending command via pipe '{pipe_name}': {e}",
            exc_info=True,
        )
        raise SendCommandError(
            f"Unexpected error sending command via pipe '{pipe_name}': {e}"
        ) from e
    finally:
        if handle != win32file.INVALID_HANDLE_VALUE:
            try:
                win32file.CloseHandle(handle)
                logger.debug(f"Closed named pipe handle for '{pipe_name}'.")
            except pywintypes.error as close_err:
                # Log but don't re-raise, as we don't want to mask an original exception
                logger.warning(
                    f"Error closing pipe handle for '{pipe_name}': {close_err.strerror} (Code: {close_err.winerror})",
                    exc_info=True,  # Good to have stack trace for this warning
                )


# --- UNUSED ---
def _windows_stop_server(
    server_name: str,
    server_dir_override: Optional[str] = None,
    config_dir_override: Optional[str] = None,
) -> None:
    """
    Stops the Bedrock server on Windows. Uses managed_bedrock_servers if available,
    otherwise falls back to PID file and provided directories.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    logger.info(f"Attempting to stop server '{server_name}' on Windows...")

    server_control = managed_bedrock_servers.get(server_name)

    # Determine effective server_dir and config_dir
    effective_server_dir = server_dir_override
    effective_config_dir = config_dir_override
    pid_file_path_from_managed = None  # Store this to avoid re-calculating

    if server_control:
        logger.debug(f"Found managed entry for '{server_name}'.")
        if not effective_server_dir:
            effective_server_dir = server_control.get("server_dir")
        if not effective_config_dir:
            effective_config_dir = server_control.get("config_dir")
        pid_file_path_from_managed = server_control.get("pid_file_path")

        # The main shutdown event for foreground mode is _foreground_server_shutdown_event.
        # If _windows_stop_server is called externally while _windows_start_server is blocking,
        # setting this event will help that blocking loop terminate.
        # For servers started detached (if that mode existed) or by previous manager runs,
        # this event won't directly control their original pipe threads.
        # However, the named pipe thread (_main_pipe_server_listener_thread) itself checks
        # the bedrock_process.poll() and its *own passed shutdown_event*.
        # If _windows_start_server is currently blocking for this server, it will have stored
        # _foreground_server_shutdown_event as the 'pipe_shutdown_event' in managed_bedrock_servers.

        pipe_shutdown_event_to_signal: Optional[threading.Event] = server_control.get(
            "pipe_main_thread_shutdown_event"
        )  # Assuming we store this
        # For the current design where _windows_start_server blocks, the _foreground_server_shutdown_event is the one to set.
        # We assume that if a server is "managed" it was started by the current foreground _windows_start_server.
        if (
            _foreground_server_shutdown_event.is_set() == False
        ):  # check if it's already being shut down
            logger.debug(
                f"Signaling _foreground_server_shutdown_event for '{server_name}' (if it's the current foreground server)."
            )
            _foreground_server_shutdown_event.set()  # This will signal the blocking loop and its pipe thread

        main_pipe_thread: Optional[threading.Thread] = server_control.get(
            "pipe_main_thread"
        )
        if main_pipe_thread and main_pipe_thread.is_alive():
            logger.debug(
                f"Waiting for main pipe listener thread of '{server_name}' to exit..."
            )
            main_pipe_thread.join(timeout=3.0)
            if main_pipe_thread.is_alive():
                logger.warning(
                    f"Main pipe listener for '{server_name}' did not exit cleanly."
                )
            else:
                logger.info(f"Main pipe listener for '{server_name}' exited.")
    else:
        logger.warning(
            f"No active managed control for '{server_name}'. Cannot explicitly signal its pipe listener thread. Will rely on process termination only."
        )

    if not effective_server_dir:
        raise ServerStopError(
            f"Server directory for '{server_name}' could not be determined."
        )
    if not effective_config_dir:
        raise ServerStopError(
            f"Config directory for '{server_name}' could not be determined."
        )

    pid_file_path = pid_file_path_from_managed
    if not pid_file_path:  # If not from managed entry, construct it
        pid_filename = _get_server_pid_filename(server_name)
        try:
            pid_file_path = core_process.get_pid_file_path(
                effective_config_dir, pid_filename
            )
        except AppFileNotFoundError as e:
            if server_name in managed_bedrock_servers:
                del managed_bedrock_servers[server_name]
            raise ServerStopError(
                f"Config error for PID path of '{server_name}': {e}"
            ) from e

    # --- Proceed with PID-based termination ---
    pid_to_stop: Optional[int] = None
    try:
        pid_to_stop = core_process.read_pid_from_file(pid_file_path)
    except FileOperationError as e:
        if pid_file_path:
            core_process.remove_pid_file_if_exists(pid_file_path)
        if server_name in managed_bedrock_servers:
            del managed_bedrock_servers[server_name]
        raise ServerStopError(f"Corrupt PID file '{pid_file_path}': {e}") from e

    if pid_to_stop is None:
        logger.info(
            f"No PID for '{server_name}' in '{pid_file_path}'. Assuming not running."
        )
    else:
        # Process PID was found in file
        try:
            if not core_process.is_process_running(pid_to_stop):
                logger.info(
                    f"Process PID {pid_to_stop} from '{pid_file_path}' (server '{server_name}') not running (stale)."
                )
            else:
                # Process is running, verify and terminate
                expected_exe_for_verify = os.path.join(
                    effective_server_dir, BEDROCK_EXECUTABLE_NAME
                )

                def _verify_bedrock_process_stop(cmdline_args: List[str]) -> bool:
                    try:
                        if not PSUTIL_AVAILABLE or not psutil:
                            return False
                        p = psutil.Process(pid_to_stop)
                        actual_exe = p.cmdline()[0] if p.cmdline() else ""
                        if not (
                            os.path.realpath(actual_exe)
                            == os.path.realpath(expected_exe_for_verify)
                            or os.path.basename(actual_exe)
                            == os.path.basename(expected_exe_for_verify)
                        ):
                            return False
                        actual_cwd = p.cwd()
                        if not (
                            actual_cwd
                            and os.path.normpath(actual_cwd).lower()
                            == os.path.normpath(effective_server_dir).lower()
                        ):
                            return False
                        return True
                    except (psutil.Error, OSError, IndexError):
                        return False

                core_process.verify_process_identity(
                    pid_to_stop,
                    custom_verification_callback=_verify_bedrock_process_stop,
                )
                logger.info(
                    f"Server '{server_name}' (PID {pid_to_stop}) verified. Terminating process..."
                )
                core_process.terminate_process_by_pid(pid_to_stop)
                logger.info(
                    f"Server '{server_name}' (PID {pid_to_stop}) process termination signal sent."
                )
        except ServerProcessError as e:
            if pid_file_path:
                core_process.remove_pid_file_if_exists(pid_file_path)
            raise ServerStopError(
                f"Verification failed for '{server_name}' (PID {pid_to_stop}): {e}. PID file removed."
            ) from e
        except (SystemError, PermissionsError, ServerStopError) as e:
            if "disappeared or was already stopped" not in str(e).lower():
                # Only raise if it's a real management error, not if process just died.
                raise ServerStopError(
                    f"Error managing process for '{server_name}' (PID {pid_to_stop}): {e}"
                ) from e
            logger.warning(
                f"Process for '{server_name}' (PID {pid_to_stop}) stopped independently or during operation."
            )

    # Final cleanup steps
    if pid_file_path:
        core_process.remove_pid_file_if_exists(pid_file_path)
        logger.debug(f"Ensured PID file '{pid_file_path}' removed for '{server_name}'.")

    if server_control:  # If this instance was managing it
        stdout_h = server_control.get("stdout_handle")
        if stdout_h and not stdout_h.closed:
            try:
                stdout_h.close()
            except Exception as e_close:
                logger.debug(f"Error closing stdout for '{server_name}': {e_close}")

    if server_name in managed_bedrock_servers:
        del managed_bedrock_servers[server_name]
        logger.debug(
            f"Removed server '{server_name}' from managed list after stop sequence."
        )

    logger.info(f"Stop sequence for server '{server_name}' completed.")


# ---
