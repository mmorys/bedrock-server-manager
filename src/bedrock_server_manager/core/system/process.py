# bedrock_server_manager/core/system/process.py
"""Provides generic, cross-platform process management utilities.

This module abstracts away the complexities of interacting with system processes.
It includes functions for:
- Handling PID files (reading, writing, removing).
- Checking if a process is running by its PID.
- Launching detached background processes with recursion protection.
- Verifying the identity of a running process by its path or arguments.
- Terminating processes gracefully and, if necessary, forcefully.

It relies on the `psutil` library for many of its capabilities and should be
considered a required dependency for process management features.
"""
import os
import logging
import subprocess
import platform
import sys
from typing import Optional, List, Dict, Callable, Union

# psutil is an optional dependency, but required for most functions here.
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from bedrock_server_manager.config.const import GUARD_VARIABLE
from bedrock_server_manager.error import (
    FileOperationError,
    SystemError,
    ServerProcessError,
    AppFileNotFoundError,
    UserInputError,
    MissingArgumentError,
    PermissionsError,
    ServerStopError,
)

logger = logging.getLogger(__name__)


class GuardedProcess:
    """A wrapper for `subprocess` that injects a recursion guard variable.

    When the application needs to call itself as a subprocess (e.g., to start
    a server in a detached window), this class ensures that an environment
    variable (`GUARD_VARIABLE`) is set. The application's startup logic can
    then check for this variable to prevent re-initializing components like
    the plugin system, avoiding infinite loops.
    """

    def __init__(self, command: List[Union[str, os.PathLike]]):
        """Initializes the GuardedProcess with the command to be run.

        Args:
            command: A list representing the command and its arguments.
        """
        self.command = command
        self.guard_env = self._create_guarded_environment()

    def _create_guarded_environment(self) -> Dict[str, str]:
        """Creates a copy of the current environment with the guard variable set."""
        child_env = os.environ.copy()
        child_env[GUARD_VARIABLE] = "1"
        return child_env

    def run(self, **kwargs) -> subprocess.CompletedProcess:
        """A wrapper for `subprocess.run` that injects the guarded environment.

        Args:
            **kwargs: Keyword arguments to pass to `subprocess.run`.

        Returns:
            A `subprocess.CompletedProcess` instance.
        """
        kwargs["env"] = self.guard_env
        return subprocess.run(self.command, **kwargs)

    def popen(self, **kwargs) -> subprocess.Popen:
        """A wrapper for `subprocess.Popen` that injects the guarded environment.

        Args:
            **kwargs: Keyword arguments to pass to `subprocess.Popen`.

        Returns:
            A `subprocess.Popen` instance.
        """
        kwargs["env"] = self.guard_env
        return subprocess.Popen(self.command, **kwargs)


def get_pid_file_path(config_dir: str, pid_filename: str) -> str:
    """Constructs the full, absolute path for a PID file.

    Args:
        config_dir: The application's configuration directory.
        pid_filename: The name of the PID file (e.g., "web_server.pid").

    Returns:
        The absolute path to where the PID file should be stored.

    Raises:
        AppFileNotFoundError: If `config_dir` is not a valid directory.
        MissingArgumentError: If `pid_filename` is empty.
    """
    if not config_dir or not os.path.isdir(config_dir):
        raise AppFileNotFoundError(config_dir, "Configuration directory")
    if not pid_filename:
        raise MissingArgumentError("PID filename cannot be empty.")
    return os.path.join(config_dir, pid_filename)


def read_pid_from_file(pid_file_path: str) -> Optional[int]:
    """Reads and validates a PID from a specified file.

    Args:
        pid_file_path: The path to the PID file.

    Returns:
        The PID as an integer if the file exists and contains a valid number.
        Returns `None` if the PID file does not exist.

    Raises:
        FileOperationError: If the file exists but is empty, unreadable, or
            contains non-integer content.
    """
    if not os.path.isfile(pid_file_path):
        logger.debug(f"PID file '{pid_file_path}' not found.")
        return None

    try:
        with open(pid_file_path, "r") as f:
            pid_str = f.read().strip()
        if not pid_str:
            raise FileOperationError(f"PID file '{pid_file_path}' is empty.")

        # Try to convert the file content to an integer.
        try:
            pid = int(pid_str)
            logger.info(f"Found PID {pid} in file '{pid_file_path}'.")
            return pid
        except ValueError:
            raise FileOperationError(
                f"Invalid content in PID file '{pid_file_path}'. Expected an integer, got '{pid_str}'."
            )
    except OSError as e:
        raise FileOperationError(
            f"Error reading PID file '{pid_file_path}': {e}"
        ) from e
    except Exception as e:
        raise FileOperationError(
            f"Unexpected error reading PID file '{pid_file_path}': {e}"
        ) from e


def write_pid_to_file(pid_file_path: str, pid: int):
    """Writes a process ID to the specified file, overwriting existing content.

    Args:
        pid_file_path: The path to the PID file.
        pid: The process ID to write to the file.

    Raises:
        FileOperationError: If an `OSError` occurs during file writing.
    """
    try:
        with open(pid_file_path, "w") as f:
            f.write(str(pid))
        logger.info(f"Saved PID {pid} to '{pid_file_path}'.")
    except OSError as e:
        raise FileOperationError(
            f"Failed to write PID {pid} to file '{pid_file_path}': {e}"
        ) from e


def is_process_running(pid: int) -> bool:
    """Checks if a process with the given PID is currently running.

    Args:
        pid: The process ID to check.

    Returns:
        True if the process is running, False otherwise.

    Raises:
        SystemError: If `psutil` is not available.
    """
    if not PSUTIL_AVAILABLE:
        raise SystemError(
            "psutil package is required to check if a process is running."
        )
    return psutil.pid_exists(pid)


def launch_detached_process(command: List[str], pid_file_path: str) -> int:
    """Launches a command as a detached background process and records its PID.

    This function uses `GuardedProcess` to prevent recursion and handles
    platform-specific flags to ensure the new process is fully independent
    of the parent.

    Args:
        command: The command and its arguments as a list of strings.
        pid_file_path: The path to write the new process's PID to.

    Returns:
        The PID of the newly launched process.

    Raises:
        UserInputError: If the command is empty.
        AppFileNotFoundError: If the command's executable is not found.
        SystemError: For other OS-level errors during process creation.
    """
    if not command or not command[0]:
        raise UserInputError("Command list and executable cannot be empty.")

    logger.info(f"Executing guarded detached command: {' '.join(command)}")

    guarded_proc = GuardedProcess(command)

    # Set platform-specific flags for detaching the process.
    creation_flags = 0
    start_new_session = False
    if platform.system() == "Windows":
        # Prevents the new process from opening a console window.
        creation_flags = subprocess.CREATE_NO_WINDOW
    elif platform.system() in ("Linux", "Darwin"):
        # Ensures the child process does not terminate when the parent does.
        start_new_session = True

    try:
        process = guarded_proc.popen(
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            start_new_session=start_new_session,
            close_fds=(platform.system() != "Windows"),
        )
    except FileNotFoundError:
        raise AppFileNotFoundError(command[0], "Command executable") from None
    except OSError as e:
        raise SystemError(f"OS error starting detached process: {e}") from e

    pid = process.pid
    logger.info(f"Successfully started guarded process with PID: {pid}")
    write_pid_to_file(pid_file_path, pid)
    return pid


def verify_process_identity(
    pid: int,
    expected_executable_path: Optional[str] = None,
    expected_command_args: Optional[Union[str, List[str]]] = None,
    custom_verification_callback: Optional[Callable[[List[str]], bool]] = None,
):
    """Verifies if a process matches an expected signature.

    Checks the process's executable path, command-line arguments, or a custom
    callback to confirm it's the process we expect it to be.

    Args:
        pid: The process ID to verify.
        expected_executable_path: The expected path of the main executable.
        expected_command_args: A specific argument or list of arguments
            expected in the command line.
        custom_verification_callback: A callable that receives the process's
            command line (as a list of strings) and returns True for a match.

    Raises:
        SystemError: If `psutil` is not available or fails.
        ServerProcessError: If the process does not exist or does not match
            the expected signature.
        PermissionsError: If access to process information is denied.
        UserInputError: If an invalid combination of arguments is provided.
        MissingArgumentError: If no verification method is provided.
    """
    if not PSUTIL_AVAILABLE:
        raise SystemError("psutil package is required for process verification.")

    # Validate that the caller provided a valid combination of verification methods.
    if custom_verification_callback and (
        expected_executable_path or expected_command_args
    ):
        raise UserInputError(
            "Cannot provide both a custom_verification_callback and other verification arguments."
        )
    if not custom_verification_callback and not (
        expected_executable_path or expected_command_args
    ):
        raise MissingArgumentError("At least one verification method must be provided.")

    try:
        process = psutil.Process(pid)
        cmdline = process.cmdline()
        proc_name = process.name()
    except psutil.NoSuchProcess:
        raise ServerProcessError(
            f"Process with PID {pid} does not exist for verification."
        )
    except psutil.AccessDenied:
        raise PermissionsError(
            f"Access denied when trying to get command line for PID {pid}."
        )
    except psutil.Error as e_psutil:
        raise SystemError(f"Error getting process info for PID {pid}: {e_psutil}.")

    if not cmdline:
        raise ServerProcessError(
            f"Process PID {pid} (Name: {proc_name}) has an empty command line and cannot be verified."
        )

    # --- Custom Verification (highest priority) ---
    if custom_verification_callback:
        if not custom_verification_callback(cmdline):
            raise ServerProcessError(
                f"Custom verification failed for PID {pid} (Cmd: {' '.join(cmdline)})."
            )
        logger.info(f"Process {pid} verified by custom callback.")
        return

    # --- Standard Verification (executable and/or arguments) ---
    executable_matches = True
    if expected_executable_path:
        executable_matches = False
        try:
            # Compare real, resolved paths to handle symlinks correctly.
            actual_proc_exe_resolved = os.path.realpath(cmdline[0])
            expected_exe_resolved = os.path.realpath(expected_executable_path)
            if actual_proc_exe_resolved.lower() == expected_exe_resolved.lower():
                executable_matches = True
        except (OSError, FileNotFoundError, IndexError):
            # Fallback to basename matching if path resolution fails.
            if cmdline and os.path.basename(cmdline[0]) == os.path.basename(
                expected_executable_path
            ):
                executable_matches = True
                logger.debug(f"Matched PID {pid} executable by basename: {cmdline[0]}")
            else:
                logger.warning(f"Could not resolve or match executable for PID {pid}.")

    arguments_present = True
    if expected_command_args:
        args_to_check = (
            [expected_command_args]
            if isinstance(expected_command_args, str)
            else expected_command_args
        )
        if args_to_check:
            proc_args = cmdline[1:]
            arguments_present = all(arg in proc_args for arg in args_to_check)

    if not (executable_matches and arguments_present):
        verification_details = f"Executable match: {executable_matches}" + (
            f" (Expected: '{expected_executable_path}')"
            if expected_executable_path
            else ""
        )
        if expected_command_args:
            expected_args_str = (
                f"'{' '.join(expected_command_args)}'"
                if isinstance(expected_command_args, list)
                else f"'{expected_command_args}'"
            )
            verification_details += (
                f", Arguments {expected_args_str} present: {arguments_present}"
            )
        mismatched_msg = f"PID {pid} (Name: {proc_name}, Cmd: {' '.join(cmdline)}) does not match expected signature. Verification failed: {verification_details}."
        raise ServerProcessError(mismatched_msg)

    logger.info(
        f"Process {pid} (Name: {proc_name}, Cmd: {' '.join(cmdline)}) confirmed against signature."
    )


def terminate_process_by_pid(
    pid: int, terminate_timeout: int = 5, kill_timeout: int = 2
):
    """Gracefully terminates, then forcefully kills, a process by its PID.

    This function first sends a SIGTERM signal and waits for the process to
    exit. If it doesn't exit within the timeout, it sends a SIGKILL signal.

    Args:
        pid: The PID of the process to terminate.
        terminate_timeout: Seconds to wait for graceful termination (SIGTERM).
        kill_timeout: Seconds to wait after sending the forceful kill (SIGKILL).

    Raises:
        SystemError: If `psutil` is not available.
        PermissionsError: If access is denied to terminate the process.
        ServerStopError: For other `psutil` or unexpected errors during termination.
    """
    if not PSUTIL_AVAILABLE:
        raise SystemError("psutil package is required to terminate processes.")
    try:
        process = psutil.Process(pid)
        # Attempt graceful termination first.
        logger.info(f"Attempting graceful termination (SIGTERM) for PID {pid}...")
        process.terminate()
        try:
            process.wait(timeout=terminate_timeout)
            logger.info(f"Process {pid} terminated gracefully.")
            return
        except psutil.TimeoutExpired:
            # If graceful termination fails, resort to forceful killing.
            logger.warning(
                f"Process {pid} did not terminate gracefully within {terminate_timeout}s. Attempting kill (SIGKILL)..."
            )
            process.kill()
            process.wait(timeout=kill_timeout)
            logger.info(f"Process {pid} forcefully killed.")
            return
    except psutil.NoSuchProcess:
        # This is not an error; the process is already gone.
        logger.warning(
            f"Process with PID {pid} was already stopped during termination attempt."
        )
    except psutil.AccessDenied:
        raise PermissionsError(
            f"Permission denied trying to terminate process with PID {pid}."
        )
    except Exception as e:
        raise ServerStopError(
            f"Unexpected error terminating process PID {pid}: {e}"
        ) from e


def remove_pid_file_if_exists(pid_file_path: str) -> bool:
    """Removes the specified PID file if it exists.

    Args:
        pid_file_path: The path to the PID file to remove.

    Returns:
        True if the file was removed or did not exist. False if removal failed
        due to an `OSError`.
    """
    if os.path.exists(pid_file_path):
        try:
            os.remove(pid_file_path)
            logger.info(f"Removed PID file '{pid_file_path}'.")
            return True
        except OSError as e:
            logger.warning(f"Could not remove PID file '{pid_file_path}': {e}")
            return False
    return True  # File didn't exist, which is a success state.
