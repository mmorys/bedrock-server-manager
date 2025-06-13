# bedrock_server_manager/core/system/process.py
"""
Provides generic, cross-platform process management utilities.

This module includes functions for:
- Handling PID files (reading, writing, removing).
- Checking if a process is running by its PID.
- Launching detached background processes.
- Verifying the identity of a running process.
- Terminating processes gracefully and forcefully.

It relies on the `psutil` library for many of its capabilities and abstracts
away platform-specific details where possible.
"""
import os
import logging
import subprocess
import platform
import sys
from typing import Optional, List, Tuple, Callable, Union

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

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


def get_pid_file_path(config_dir: str, pid_filename: str) -> str:
    """
    Determines the full path for a generic PID file.

    Args:
        config_dir: The application's configuration directory.
        pid_filename: The name of the PID file (e.g., "my_process.pid").

    Returns:
        The absolute path to the PID file.

    Raises:
        AppFileNotFoundError: If config_dir is not a valid directory.
        MissingArgumentError: If pid_filename is empty.
    """
    if not config_dir or not os.path.isdir(config_dir):
        raise AppFileNotFoundError(config_dir, "Configuration directory")
    if not pid_filename:
        raise MissingArgumentError("PID filename cannot be empty.")
    return os.path.join(config_dir, pid_filename)


def read_pid_from_file(pid_file_path: str) -> Optional[int]:
    """
    Reads and validates the PID from the given PID file. (Generic)

    Args:
        pid_file_path: Path to the PID file.

    Returns:
        The PID as an integer if the file exists, is readable, and contains a valid PID.
        None if the PID file does not exist.

    Raises:
        FileOperationError: If the file exists but is empty, unreadable, or contains invalid content.
    """
    function_name = "core.process.read_pid_from_file"
    if not os.path.isfile(pid_file_path):
        logger.debug(f"{function_name}: PID file '{pid_file_path}' not found.")
        return None

    try:
        with open(pid_file_path, "r") as f:
            pid_str = f.read().strip()
        if not pid_str:
            raise FileOperationError(f"PID file '{pid_file_path}' is empty.")
        try:
            pid = int(pid_str)
            logger.info(f"{function_name}: Found PID {pid} in file '{pid_file_path}'.")
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


def write_pid_to_file(pid_file_path: str, pid: int) -> None:
    """
    Writes the given PID to the specified PID file. (Generic)

    Args:
        pid_file_path: Path to the PID file.
        pid: The process ID to write.

    Raises:
        FileOperationError: If an OSError occurs during file writing.
    """
    try:
        with open(pid_file_path, "w") as f:
            f.write(str(pid))
        logger.info(
            f"core.process.write_pid_to_file: Saved PID {pid} to '{pid_file_path}'."
        )
    except OSError as e:
        raise FileOperationError(
            f"Failed to write PID {pid} to file '{pid_file_path}': {e}"
        ) from e


def is_process_running(pid: int) -> bool:
    """
    Checks if a process with the given PID is currently running. (Generic)
    Requires 'psutil' to be installed.

    Args:
        pid: The process ID to check.

    Returns:
        True if the process is running, False otherwise.

    Raises:
        SystemError: If psutil is not available.
    """
    if not PSUTIL_AVAILABLE:
        raise SystemError(
            "psutil package is required to check if a process is running."
        )
    return psutil.pid_exists(pid)


def launch_detached_process(
    command: List[str],
    pid_file_path: str,
) -> int:
    """
    Launches a generic command as a detached background process and writes its PID.

    Args:
        command: The command and its arguments as a list of strings.
        pid_file_path: Path to write the new process's PID.

    Returns:
        The PID of the newly started detached process.

    Raises:
        AppFileNotFoundError: If the command's executable is not found.
        SystemError: If subprocess.Popen fails.
        FileOperationError: If writing the PID file fails.
        UserInputError: If command list or executable is empty.
    """
    function_name = "core.process.launch_detached_process"
    if not command:
        raise UserInputError("Command list cannot be empty for launching a process.")

    # Check the executable part of the command
    if not command[0]:
        raise UserInputError("Command executable cannot be empty.")

    logger.info(f"{function_name}: Executing detached command: {' '.join(command)}")

    creation_flags = 0
    start_new_session = False
    if platform.system() == "Windows":
        # Detaches process on Windows
        creation_flags = (
            subprocess.CREATE_NO_WINDOW
        )  # For background execution without a console window
        # CREATE_NEW_PROCESS_GROUP is also useful for Windows, but CREATE_NO_WINDOW often implies it for console apps.
        # Alternatively, DETACHED_PROCESS = 0x00000008 can be used instead of CREATE_NO_WINDOW if you want a console.
        # However, for a truly detached server, CREATE_NO_WINDOW is common.
    elif platform.system() in ("Linux", "Darwin"):  # Darwin for macOS
        start_new_session = True  # For POSIX, detaches from controlling terminal

    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            start_new_session=start_new_session,
            close_fds=(
                platform.system() != "Windows"
            ),  # close_fds is not well-supported with CREATE_NO_WINDOW on Windows
        )
    except FileNotFoundError:
        raise AppFileNotFoundError(command[0], "Command executable") from None
    except OSError as e:
        raise SystemError(
            f"OS error starting detached process with command '{' '.join(command)}': {e}"
        ) from e

    pid = process.pid
    logger.info(
        f"{function_name}: Successfully started detached process with PID: {pid}"
    )
    write_pid_to_file(pid_file_path, pid)  # Can raise FileOperationError
    return pid


def verify_process_identity(
    pid: int,
    expected_executable_path: Optional[str] = None,
    expected_command_args: Optional[Union[str, List[str]]] = None,
    custom_verification_callback: Optional[Callable[[List[str]], bool]] = None,
) -> None:
    """
    Verifies if the process with the given PID matches an expected signature. (Generic)
    Checks executable path, optionally specific command line arguments, or a custom callback.

    Args:
        pid: The process ID to verify.
        expected_executable_path: Optional. The expected path of the main executable.
                                  If None, executable path is not checked.
        expected_command_args: Optional. A specific argument or list of arguments
                                   expected in the command line.
        custom_verification_callback: Optional. A callable that takes the process's
                                      cmdline (List[str]) and returns True if it's a match.

    Raises:
        SystemError: If psutil is not available or if process info cannot be retrieved.
        ServerProcessError: If the process does not match the expected signature.
        PermissionsError: If access to process information is denied.
        UserInputError: If an invalid combination of verification methods is provided.
        MissingArgumentError: If required verification arguments are not provided.
    """
    function_name = "core.process.verify_process_identity"

    if not PSUTIL_AVAILABLE:
        raise SystemError("psutil package is required for process verification.")

    if custom_verification_callback and (
        expected_executable_path or expected_command_args
    ):
        raise UserInputError(
            "Cannot provide both a custom_verification_callback and expected_executable_path/expected_command_args."
        )
    if not custom_verification_callback and not (
        expected_executable_path or expected_command_args
    ):
        raise MissingArgumentError(
            "At least one verification method (executable path, command args, or custom callback) must be provided."
        )

    try:
        process = psutil.Process(pid)
        cmdline = process.cmdline()
        proc_name = process.name()
    except psutil.NoSuchProcess:
        logger.warning(
            f"{function_name}: Process with PID {pid} does not exist (for verification)."
        )
        raise ServerProcessError(
            f"Process with PID {pid} does not exist (for verification)."
        )
    except psutil.AccessDenied:
        logger.error(
            f"{function_name}: Access denied for PID {pid} (Name: {process.name() if 'process' in locals() and hasattr(process, 'name') else 'unknown'})."
        )
        raise PermissionsError(
            f"Access denied when trying to get command line for PID {pid}."
        )
    except psutil.Error as e_psutil:
        logger.error(f"{function_name}: psutil error for PID {pid}: {e_psutil}.")
        raise SystemError(f"Error getting process info for PID {pid}: {e_psutil}.")

    if not cmdline:
        logger.warning(
            f"{function_name}: Process PID {pid} (Name: {proc_name}) has empty cmdline."
        )
        raise ServerProcessError(
            f"Process PID {pid} (Name: {proc_name}) has an empty command line. Cannot verify."
        )

    # --- Custom Verification ---
    if custom_verification_callback:
        if not custom_verification_callback(cmdline):
            raise ServerProcessError(
                f"Custom verification failed for PID {pid} (Cmd: {' '.join(cmdline)})."
            )
        logger.info(f"{function_name}: Process {pid} verified by custom callback.")
        return

    # --- Standard Verification ---
    executable_matches = True
    if expected_executable_path:
        executable_matches = False
        try:
            actual_proc_exe_resolved = os.path.realpath(cmdline[0])
            expected_exe_resolved = os.path.realpath(expected_executable_path)
            if actual_proc_exe_resolved.lower() == expected_exe_resolved.lower():
                executable_matches = True
        except (OSError, FileNotFoundError, IndexError):
            if cmdline and os.path.basename(cmdline[0]) == os.path.basename(
                expected_executable_path
            ):
                executable_matches = True
                logger.debug(
                    f"{function_name}: Matched PID {pid} executable by basename: {cmdline[0]}"
                )
            else:
                logger.warning(
                    f"{function_name}: Could not resolve or match executable for PID {pid}. Cmdline[0]: {cmdline[0] if cmdline else 'N/A'}, Expected: {expected_executable_path}"
                )

    arguments_present = True
    if expected_command_args:
        args_to_check = []
        if isinstance(expected_command_args, str):
            args_to_check = [expected_command_args]
        elif isinstance(expected_command_args, list):
            args_to_check = expected_command_args

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

        mismatched_msg = (
            f"PID {pid} (Name: {proc_name}, Cmd: {' '.join(cmdline)}) "
            f"does not match expected signature. Verification failed: {verification_details}."
        )
        raise ServerProcessError(mismatched_msg)

    logger.info(
        f"{function_name}: Process {pid} (Name: {proc_name}, Cmd: {' '.join(cmdline)}) confirmed against signature."
    )


def terminate_process_by_pid(
    pid: int, terminate_timeout: int = 5, kill_timeout: int = 2
) -> None:
    """
    Attempts to gracefully terminate, then forcefully kill, a process by its PID. (Generic)

    Args:
        pid: The PID of the process to terminate.
        terminate_timeout: Seconds to wait for graceful termination.
        kill_timeout: Seconds to wait after sending SIGKILL.

    Raises:
        SystemError: If psutil is not available.
        PermissionsError: If access is denied to terminate the process.
        ServerStopError: If other psutil or unexpected errors occur during termination.
    """
    function_name = "core.process.terminate_process_by_pid"
    if not PSUTIL_AVAILABLE:
        raise SystemError("psutil package is required to terminate processes.")
    try:
        process = psutil.Process(pid)
        logger.info(
            f"{function_name}: Attempting graceful termination (SIGTERM) for PID {pid}..."
        )
        process.terminate()
        try:
            process.wait(timeout=terminate_timeout)
            logger.info(f"{function_name}: Process {pid} terminated gracefully.")
            return
        except psutil.TimeoutExpired:
            logger.warning(
                f"{function_name}: Process {pid} did not terminate gracefully within {terminate_timeout}s. Attempting kill (SIGKILL)..."
            )
            process.kill()
            process.wait(timeout=kill_timeout)  # Wait for kill confirmation
            logger.info(f"{function_name}: Process {pid} forcefully killed.")
            return
    except psutil.NoSuchProcess:
        logger.warning(
            f"{function_name}: Process with PID {pid} disappeared or was already stopped during termination attempt."
        )
        # This is not an error for termination, it's already gone.
    except psutil.AccessDenied:
        raise PermissionsError(
            f"Permission denied trying to terminate process with PID {pid}."
        )
    except Exception as e:  # Catch other psutil or unexpected errors
        raise ServerStopError(
            f"Unexpected error terminating process PID {pid}: {e}"
        ) from e


def remove_pid_file_if_exists(pid_file_path: str) -> bool:
    """
    Removes the PID file if it exists. (Generic)

    Args:
        pid_file_path: Path to the PID file.

    Returns:
        True if the file was removed or did not exist, False if removal failed.
    """
    if os.path.exists(pid_file_path):
        try:
            os.remove(pid_file_path)
            logger.info(
                f"core.process.remove_pid_file_if_exists: Removed PID file '{pid_file_path}'."
            )
            return True
        except OSError as e:
            logger.warning(
                f"core.process.remove_pid_file_if_exists: Could not remove PID file '{pid_file_path}': {e}"
            )
            return False
    return True  # File didn't exist, so effectively "removed"
