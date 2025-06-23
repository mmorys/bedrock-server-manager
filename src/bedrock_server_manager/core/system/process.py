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
    """Constructs the full, absolute path for a generic PID file.

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


def get_bedrock_server_pid_file_path(server_name: str, config_dir: str) -> str:
    """Constructs the standardized path to a Bedrock server's PID file.

    This helper creates a path to a PID file within a server-specific
    subdirectory of the main application configuration directory.

    Args:
        server_name: The name of the server instance.
        config_dir: The main configuration directory for the application.

    Returns:
        The absolute path to where the server's PID file should be located.

    Raises:
        MissingArgumentError: If `server_name` or `config_dir` is empty.
        AppFileNotFoundError: If the server-specific config subdirectory does
            not exist.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not config_dir:
        raise MissingArgumentError("Configuration directory cannot be empty.")

    server_config_path = os.path.join(config_dir, server_name)
    if not os.path.isdir(server_config_path):
        raise AppFileNotFoundError(
            server_config_path, f"Configuration directory for server '{server_name}'"
        )

    pid_filename = f"bedrock_{server_name}.pid"
    return os.path.join(server_config_path, pid_filename)


def get_bedrock_launcher_pid_file_path(server_name: str, config_dir: str) -> str:
    """Constructs the standardized path to a Bedrock server's LAUNCHER PID file."""
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not config_dir:
        raise MissingArgumentError("Configuration directory cannot be empty.")

    server_config_path = config_dir
    if not os.path.isdir(server_config_path):
        try:
            os.makedirs(server_config_path, exist_ok=True)
        except OSError as e:
            raise AppFileNotFoundError(
                server_config_path,
                f"Launcher PID: Config directory for server '{server_name}' (could not create: {e})",
            ) from e

    pid_filename = f"bedrock_{server_name}_launcher.pid"  # For the BSM launcher process
    return os.path.join(server_config_path, pid_filename)


def read_pid_from_file(pid_file_path: str) -> Optional[int]:
    """Reads and validates a PID from a specified file.

    Args:
        pid_file_path: The path to the PID file.

    Returns:
        The PID as an integer if the file exists and contains a valid number.
        Returns `None` if the PID file does not exist.

    Raises:
        FileOperationError: If the file exists but is unreadable or contains
            non-integer content.
    """
    if not os.path.isfile(pid_file_path):
        logger.debug(f"PID file '{pid_file_path}' not found.")
        return None
    try:
        with open(pid_file_path, "r") as f:
            pid_str = f.read().strip()
        if not pid_str.isdigit():
            raise FileOperationError(
                f"Invalid content in PID file '{pid_file_path}': '{pid_str}'."
            )
        return int(pid_str)
    except (OSError, ValueError) as e:
        raise FileOperationError(
            f"Error reading or parsing PID file '{pid_file_path}': {e}"
        ) from e


def write_pid_to_file(pid_file_path: str, pid: int):
    """Writes a process ID to the specified file, overwriting existing content.

    This function will create the parent directory if it does not exist.

    Args:
        pid_file_path: The path to the PID file.
        pid: The process ID to write to the file.

    Raises:
        FileOperationError: If an `OSError` occurs during file writing.
    """
    try:
        os.makedirs(os.path.dirname(pid_file_path), exist_ok=True)
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


def launch_detached_process(command: List[str], launcher_pid_file_path: str) -> int:
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
    else:  # Linux, Darwin, etc.
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
    write_pid_to_file(launcher_pid_file_path, pid)
    return pid


def verify_process_identity(
    pid: int,
    expected_executable_path: Optional[str] = None,
    expected_cwd: Optional[str] = None,
    expected_command_args: Optional[Union[str, List[str]]] = None,
):
    """Verifies if a process matches an expected signature.

    Checks the process's executable path, current working directory (CWD),
    and/or specific command-line arguments to confirm it's the process we
    expect it to be.

    Args:
        pid: The process ID to verify.
        expected_executable_path: Optional expected path of the main executable.
        expected_cwd: Optional expected current working directory of the process.
        expected_command_args: Optional specific argument(s) expected in the command line.

    Raises:
        SystemError: If `psutil` is not available or fails.
        ServerProcessError: If the process does not exist or does not match
            the expected signature.
        PermissionsError: If access to process information is denied.
        MissingArgumentError: If no verification criteria are provided.
    """
    if not PSUTIL_AVAILABLE:
        raise SystemError("psutil package is required for process verification.")
    if not any([expected_executable_path, expected_cwd, expected_command_args]):
        raise MissingArgumentError(
            "At least one verification criteria must be provided."
        )

    try:
        proc = psutil.Process(pid)
        # Use oneshot() for performance, as it caches process info for subsequent calls.
        with proc.oneshot():
            proc_name = proc.name()
            proc_exe = proc.exe()
            proc_cwd = proc.cwd()
            proc_cmdline = proc.cmdline()
    except psutil.NoSuchProcess:
        raise ServerProcessError(
            f"Process with PID {pid} does not exist for verification."
        )
    except psutil.AccessDenied:
        raise PermissionsError(f"Access denied when trying to get info for PID {pid}.")
    except psutil.Error as e_psutil:
        raise SystemError(f"Error getting process info for PID {pid}: {e_psutil}.")

    mismatches = []
    # Verify Executable Path
    if expected_executable_path:
        expected_exe_norm = os.path.normcase(os.path.abspath(expected_executable_path))
        proc_exe_norm = os.path.normcase(os.path.abspath(proc_exe))
        if proc_exe_norm != expected_exe_norm:
            mismatches.append(
                f"Executable path mismatch (Expected: '{expected_exe_norm}', Got: '{proc_exe_norm}')"
            )

    # Verify Current Working Directory
    if expected_cwd:
        expected_cwd_norm = os.path.normcase(os.path.abspath(expected_cwd))
        proc_cwd_norm = os.path.normcase(os.path.abspath(proc_cwd))
        if proc_cwd_norm != expected_cwd_norm:
            mismatches.append(
                f"CWD mismatch (Expected: '{expected_cwd_norm}', Got: '{proc_cwd_norm}')"
            )

    # Verify Command Arguments
    if expected_command_args:
        args_to_check = (
            [expected_command_args]
            if isinstance(expected_command_args, str)
            else expected_command_args
        )
        if not all(arg in proc_cmdline for arg in args_to_check):
            mismatches.append(
                f"Argument mismatch (Expected '{args_to_check}' in command line)"
            )

    if mismatches:
        details = ", ".join(mismatches)
        raise ServerProcessError(
            f"PID {pid} (Name: {proc_name}) failed verification: {details}. Cmd: '{' '.join(proc_cmdline)}'"
        )

    logger.debug(
        f"Process {pid} (Name: {proc_name}) verified successfully against signature."
    )


def get_verified_bedrock_process(
    server_name: str, server_dir: str, config_dir: str
) -> Optional["psutil.Process"]:
    """Finds and verifies the Bedrock server process using its PID file.

    This function encapsulates the entire logic of:
    1. Finding the server-specific PID file.
    2. Reading the PID from the file.
    3. Checking if a process with that PID is running.
    4. Verifying the process's executable path and working directory.

    Args:
        server_name: The name of the server instance.
        server_dir: The server's installation directory.
        config_dir: The main application configuration directory.

    Returns:
        A `psutil.Process` object if the server is running and verified,
        otherwise `None`.
    """
    if not PSUTIL_AVAILABLE:
        logger.error("'psutil' is required for this function. Returning None.")
        return None

    try:
        pid_file_path = get_bedrock_server_pid_file_path(server_name, config_dir)
        pid = read_pid_from_file(pid_file_path)

        if pid is None or not is_process_running(pid):
            if pid:
                logger.debug(
                    f"Stale PID {pid} found for '{server_name}'. Process not running."
                )
            return None

        # Define the platform-specific executable name to verify against.
        exe_name = (
            "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
        )
        expected_exe = os.path.join(server_dir, exe_name)

        # Verify the running process matches our expectations.
        verify_process_identity(
            pid, expected_executable_path=expected_exe, expected_cwd=server_dir
        )

        return psutil.Process(pid)

    except (
        AppFileNotFoundError,
        FileOperationError,
        ServerProcessError,
        PermissionsError,
    ) as e:
        # These are expected "not running" or "mismatch" scenarios.
        logger.debug(f"Verification failed for server '{server_name}': {e}")
        return None
    except (SystemError, Exception) as e:
        # These are more serious, unexpected errors.
        logger.error(
            f"Unexpected error getting verified process for '{server_name}': {e}",
            exc_info=True,
        )
        return None


def terminate_process_by_pid(
    pid: int, terminate_timeout: int = 5, kill_timeout: int = 2
):
    """Gracefully terminates, then forcefully kills, a process by its PID.

    This function first sends a SIGTERM signal and waits for the process to
    exit. If it doesn't exit within the `terminate_timeout`, it sends a
    SIGKILL signal and waits for `kill_timeout`.

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
        # 1. Attempt graceful termination first.
        logger.info(f"Attempting graceful termination (SIGTERM) for PID {pid}...")
        process.terminate()
        try:
            process.wait(timeout=terminate_timeout)
            logger.info(f"Process {pid} terminated gracefully.")
            return
        except psutil.TimeoutExpired:
            # 2. If graceful termination fails, resort to forceful killing.
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
            f"Process with PID {pid} disappeared or was already stopped during termination attempt."
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
    return True
