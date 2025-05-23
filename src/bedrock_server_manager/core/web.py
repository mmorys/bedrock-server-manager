# bedrock-server-manager/bedrock_server_manager/core/web.py
import os
import logging
import sys  # To get sys.executable as the default EXPATH
from typing import Optional, List

# Import generic process utilities
from bedrock_server_manager.core.system import process as core_process

# Import specific errors
from bedrock_server_manager.error import (
    ConfigurationError,
    ExecutableNotFoundError,
    ProcessManagementError,
    PIDFileError,
    ProcessVerificationError,
)

logger = logging.getLogger("bedrock_server_manager")


# --- Web Server Specific Constants ---
WEB_SERVER_PID_FILENAME = "web_server.pid"
# The argument that identifies our web server process, e.g., "start-web-server"
EXPECTED_WEB_SERVER_START_ARG = "start-web-server"


def get_web_pid_file_path(config_dir: str) -> str:
    """
    Gets the expected path for the web server PID file using the generic utility.

    Args:
        config_dir: The application's configuration directory.

    Returns:
        The absolute path to the web server's PID file.

    Raises:
        ConfigurationError: If config_dir is invalid.
        ValueError: If the PID filename is empty (unlikely with constant).
    """
    # core_process.get_pid_file_path can raise ConfigurationError or ValueError
    return core_process.get_pid_file_path(config_dir, WEB_SERVER_PID_FILENAME)


def start_detached_web_server(
    # expath could be an absolute path to a specific python executable
    # or a compiled binary. If running as `python script.py`, then expath is sys.executable.
    expath: str,
    config_dir: str,  # To determine PID file path
    host_args: Optional[List[str]] = None,  # e.g., ["--host", "0.0.0.0"]
    debug_flag: bool = False,
) -> int:
    """
    Starts the web server as a detached background process.

    Args:
        expath: Path to the main application executable/script used to launch the web server.
                (e.g., the Python interpreter path, if `python your_script.py start-web-server` is used).
        config_dir: Application's configuration directory (to store PID file).
        host_args: List of host arguments for the web server command.
        debug_flag: Whether to include the --debug flag in the web server command.

    Returns:
        The PID of the newly started web server process.

    Raises:
        ConfigurationError: If config_dir is invalid.
        ExecutableNotFoundError: If expath is invalid or the command's executable isn't found.
        ProcessManagementError: If subprocess.Popen fails.
        PIDFileError: If writing the PID file fails.
        ValueError: If expath is empty or command list is empty internally.
    """
    function_name = "core.web.start_detached_web_server"
    logger.info(f"{function_name}: Preparing to start detached web server.")

    # Determine PID file path
    pid_file_path = get_web_pid_file_path(config_dir)  # Can raise ConfigurationError

    # Construct the web-server specific command list
    command = [str(expath), EXPECTED_WEB_SERVER_START_ARG]  # Base command

    # Add web-server specific arguments for the 'direct' mode it will run in
    command.append("--mode")
    command.append("direct")

    if host_args:
        command.extend(host_args)
    if debug_flag:
        command.append("--debug")

    logger.debug(f"{function_name}: Constructed command: {' '.join(command)}")

    # Use the generic process launching function
    try:
        pid = core_process.launch_detached_process(command, pid_file_path)
        logger.info(
            f"{function_name}: Web server launched with PID {pid}. PID file: {pid_file_path}"
        )
        return pid
    except (
        ExecutableNotFoundError,
        ProcessManagementError,
        PIDFileError,
        ValueError,
    ) as e:
        logger.error(
            f"{function_name}: Failed to launch detached web server: {e}", exc_info=True
        )
        raise  # Re-raise the specific error from core.process or local validation


def stop_running_web_server(
    config_dir: str,
    # This should typically be sys.executable if your server is started by python
    # or the path to your compiled app if it's a binary.
    expected_server_executable_path: str,
    terminate_timeout: int = 5,
    kill_timeout: int = 2,
) -> Optional[int]:
    """
    Stops the running web server process if found and verified.

    Args:
        config_dir: Application's configuration directory.
        expected_server_executable_path: The path to the executable that should have started the server.
                                         Used for verifying the process's identity.
        terminate_timeout: Timeout in seconds for graceful termination.
        kill_timeout: Timeout in seconds for forceful kill.

    Returns:
        The PID of the stopped process if successful, or None if the server
        was not running (no PID file, stale PID file, or process already stopped).

    Raises:
        ConfigurationError: If config_dir is invalid for PID file path.
        PIDFileError: If PID file is corrupt or unreadable (but exists).
        ProcessManagementError: For issues like psutil not available, access denied during termination.
        ProcessVerificationError: If a running process is found but doesn't match the web server's signature.
    """
    function_name = "core.web.stop_running_web_server"
    logger.info(f"{function_name}: Attempting to stop web server.")

    pid_file_path = get_web_pid_file_path(config_dir)  # Can raise ConfigurationError

    # Read PID from file
    pid: Optional[int] = None
    try:
        pid = core_process.read_pid_from_file(pid_file_path)
    except PIDFileError as e:
        # If PID file exists but is empty or invalid, treat it as an error but try to clean up.
        logger.warning(
            f"{function_name}: Problematic PID file '{pid_file_path}': {e}. Attempting removal."
        )
        core_process.remove_pid_file_if_exists(pid_file_path)
        raise  # Re-raise the specific PIDFileError as a stopping error

    if (
        pid is None
    ):  # PID file not found or was empty and read_pid_from_file handled it by not returning a PID
        logger.info(
            f"{function_name}: No PID file found at '{pid_file_path}' or it was empty. Assuming web server not running."
        )
        return None  # Server effectively stopped

    # PID found in file, now check if process is running and verify its identity
    try:
        if not core_process.is_process_running(
            pid
        ):  # Can raise ProcessManagementError (e.g. if psutil is not available)
            logger.warning(
                f"{function_name}: Process with PID {pid} from '{pid_file_path}' not running (stale PID file). Cleaning up."
            )
            core_process.remove_pid_file_if_exists(pid_file_path)
            return None  # Server effectively stopped

        # Process is running, verify its identity as *our* web server
        logger.info(
            f"{function_name}: Process PID {pid} is running. Verifying its identity as the web server..."
        )
        core_process.verify_process_identity(
            pid,
            expected_executable_path=expected_server_executable_path,
            expected_command_arg=EXPECTED_WEB_SERVER_START_ARG,
        )  # Can raise ProcessVerificationError, ProcessManagementError

        # Process verified as our web server, terminate it
        logger.info(f"{function_name}: Web server PID {pid} verified. Terminating...")
        core_process.terminate_process_by_pid(
            pid, terminate_timeout, kill_timeout
        )  # Can raise ProcessManagementError

        # Clean up PID file after successful termination attempt
        core_process.remove_pid_file_if_exists(pid_file_path)
        logger.info(
            f"{function_name}: Web server (PID: {pid}) stopped successfully and PID file removed."
        )
        return pid

    except core_process.ProcessVerificationError as e:
        logger.error(
            f"{function_name}: Verification failed for PID {pid} from '{pid_file_path}': {e}. Removing stale PID file."
        )
        core_process.remove_pid_file_if_exists(
            pid_file_path
        )  # PID file points to wrong process
        raise  # Re-raise for API layer to handle as an error
    except core_process.ProcessManagementError as e:
        # If the process disappeared (NoSuchProcess) during termination attempt, core_process.terminate_process_by_pid
        # logs a warning and doesn't raise, which means it's effectively stopped.
        # Other ProcessManagementErrors (e.g., AccessDenied) should still be re-raised.
        # Check if the error message implies the process is no longer there.
        if "disappeared or was already stopped" in str(e).lower():
            logger.warning(
                f"{function_name}: Process PID {pid} unexpectedly disappeared during stop attempt. Assuming it stopped."
            )
            core_process.remove_pid_file_if_exists(
                pid_file_path
            )  # It's gone, so PID file is stale
            return pid  # It was stopped
        else:
            logger.error(
                f"{function_name}: Process management error for PID {pid}: {e}",
                exc_info=True,
            )
            raise  # Re-raise other ProcessManagementErrors
