# bedrock_server_manager/api/web.py
"""Provides API functions for managing the application's web server.

This module contains the logic for starting, stopping, and checking the status
of the built-in web user interface, which is powered by Flask. It handles
both direct (blocking) and detached (background) modes of operation.
"""
import logging
from typing import Dict, Optional, Any, List, Union
import os

# psutil is an optional dependency required for detached mode process management.
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Plugin system imports to bridge API functionality.
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.core.system import process as system_process_utils
from bedrock_server_manager.error import (
    BSMError,
    FileOperationError,
    ServerProcessError,
    SystemError,
    UserInputError,
)

logger = logging.getLogger(__name__)
# A global BedrockServerManager instance for accessing web UI configuration.
bsm = BedrockServerManager()


def start_web_server_api(
    host: Optional[Union[str, List[str]]] = None,
    debug: bool = False,
    mode: str = "direct",
) -> Dict[str, Any]:
    """Starts the application's web server.

    This function can start the web server in two modes:
    - 'direct': A blocking call that runs the server in the current process.
      Useful for development or when managed by an external process manager.
    - 'detached': Launches the server as a new background process and creates
      a PID file to track it. Requires the `psutil` library.

    Args:
        host: The host address(es) to bind the web server to. Can be a single
            string or a list of strings. Defaults to the setting value.
        debug: If True, starts the Flask server in debug mode.
        mode: The start mode, either 'direct' or 'detached'.

    Returns:
        A dictionary containing the operation status, a message, and the PID
        if started in detached mode.

    Raises:
        UserInputError: If the provided `mode` is invalid.
        SystemError: If `detached` mode is used but `psutil` is not installed.
        ServerProcessError: If the web server is already running.
    """
    mode = mode.lower()

    plugin_manager.trigger_guarded_event("before_web_server_start", mode=mode)

    result = {}
    try:
        if mode not in ["direct", "detached"]:
            raise UserInputError("Invalid mode. Must be 'direct' or 'detached'.")

        logger.info(f"API: Attempting to start web server in '{mode}' mode...")
        # --- Direct (Blocking) Mode ---
        if mode == "direct":
            bsm.start_web_ui_direct(host, debug)
            result = {
                "status": "success",
                "message": "Web server (direct mode) shut down.",
            }

        # --- Detached (Background) Mode ---
        elif mode == "detached":
            if not PSUTIL_AVAILABLE:
                raise SystemError(
                    "Cannot start in detached mode: 'psutil' is required."
                )

            logger.info("API: Starting web server in detached mode...")
            pid_file_path = bsm.get_web_ui_pid_path()
            expected_exe = bsm.get_web_ui_executable_path()
            expected_arg = bsm.get_web_ui_expected_start_arg()

            # Check for an existing, valid PID file.
            existing_pid = None
            try:
                existing_pid = system_process_utils.read_pid_from_file(pid_file_path)
            except FileOperationError:  # Corrupt PID file.
                system_process_utils.remove_pid_file_if_exists(pid_file_path)

            # If a PID exists, verify the process is still running and correct.
            if existing_pid and system_process_utils.is_process_running(existing_pid):
                try:
                    system_process_utils.verify_process_identity(
                        existing_pid, expected_exe, expected_arg
                    )
                    # If verification passes, the server is already running.
                    raise ServerProcessError(
                        f"Web server already running (PID: {existing_pid})."
                    )
                except ServerProcessError:
                    # The PID points to the wrong process. Clean up the stale file.
                    system_process_utils.remove_pid_file_if_exists(pid_file_path)
            else:
                # The PID is stale or doesn't exist. Clean up the file.
                system_process_utils.remove_pid_file_if_exists(pid_file_path)

            # Construct the command to launch the new detached process.
            command = [str(expected_exe), "web", "start", "--mode", "direct"]
            hosts_to_add = []
            if isinstance(host, str):
                hosts_to_add.append(host)
            elif isinstance(host, list):
                hosts_to_add.extend(host)

            for h in hosts_to_add:
                if h:
                    command.extend(["--host", str(h)])
            if debug:
                command.append("--debug")

            # Launch the process and write the new PID to the file.
            new_pid = system_process_utils.launch_detached_process(
                command, pid_file_path
            )
            result = {
                "status": "success",
                "pid": new_pid,
                "message": f"Web server started (PID: {new_pid}).",
            }

    except BSMError as e:
        logger.error(f"API: Handled error starting web server: {e}", exc_info=True)
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error starting web server: {e}", exc_info=True)
        result = {"status": "error", "message": f"Unexpected error: {str(e)}"}
    finally:
        plugin_manager.trigger_guarded_event("after_web_server_start", result=result)

    return result


def stop_web_server_api() -> Dict[str, str]:
    """Stops the detached web server process.

    This function reads the PID from the web server's PID file, verifies that
    the process is the correct one, and terminates it. Requires the `psutil`
    library.

    Returns:
        A dictionary containing the operation status and a descriptive message.
    """
    plugin_manager.trigger_guarded_event("before_web_server_stop")

    result = {}
    try:
        logger.info("API: Attempting to stop detached web server...")
        if not PSUTIL_AVAILABLE:
            raise SystemError("'psutil' not installed. Cannot manage processes.")

        pid_file_path = bsm.get_web_ui_pid_path()
        expected_exe = bsm.get_web_ui_executable_path()
        expected_arg = bsm.get_web_ui_expected_start_arg()

        # Read the PID from the file.
        pid = system_process_utils.read_pid_from_file(pid_file_path)
        if pid is None:
            system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "success",
                "message": "Web server not running (no valid PID file).",
            }

        # Check if the process is actually running.
        if not system_process_utils.is_process_running(pid):
            system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "success",
                "message": f"Web server not running (stale PID {pid}).",
            }

        # Verify it's the correct process before terminating.
        system_process_utils.verify_process_identity(pid, expected_exe, expected_arg)
        system_process_utils.terminate_process_by_pid(pid)
        system_process_utils.remove_pid_file_if_exists(pid_file_path)
        result = {"status": "success", "message": f"Web server (PID: {pid}) stopped."}

    except (FileOperationError, ServerProcessError) as e:
        # Clean up the PID file if there's a file error or process mismatch.
        system_process_utils.remove_pid_file_if_exists(bsm.get_web_ui_pid_path())
        error_type = (
            "PID file error"
            if isinstance(e, FileOperationError)
            else "Process verification failed"
        )
        result = {"status": "error", "message": f"{error_type}: {e}. PID file removed."}
    except BSMError as e:
        result = {"status": "error", "message": f"Error stopping web server: {e}"}
    except Exception as e:
        logger.error(f"API: Unexpected error stopping web server: {e}", exc_info=True)
        result = {"status": "error", "message": f"Unexpected error: {str(e)}"}
    finally:
        plugin_manager.trigger_guarded_event("after_web_server_stop", result=result)

    return result


@plugin_method("get_web_server_status")
def get_web_server_status_api() -> Dict[str, Any]:
    """Checks the status of the web server process.

    This function verifies the web server's status by checking for a valid
    PID file and then inspecting the process itself to ensure it is running
    and is the correct executable. Requires the `psutil` library.

    Returns:
        A dictionary with the status, PID (if available), and a message.
        Possible statuses: "RUNNING", "STOPPED", "MISMATCHED_PROCESS", "ERROR".
        Example: `{"status": "RUNNING", "pid": 1234, "message": "..."}`
    """
    logger.debug("API: Getting web server status...")
    if not PSUTIL_AVAILABLE:
        return {
            "status": "ERROR",
            "message": "'psutil' not installed. Cannot get process status.",
        }
    pid = None
    try:
        pid_file_path = bsm.get_web_ui_pid_path()
        expected_exe = bsm.get_web_ui_executable_path()
        expected_arg = bsm.get_web_ui_expected_start_arg()

        try:
            pid = system_process_utils.read_pid_from_file(pid_file_path)
        except FileOperationError:  # Handle corrupt PID file.
            system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "STOPPED",
                "pid": None,
                "message": "Corrupt PID file removed.",
            }

        # Case: No PID file, or PID file was empty.
        if pid is None:
            if os.path.exists(pid_file_path):  # Clean up empty file.
                system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "STOPPED",
                "pid": None,
                "message": "Web server not running (no PID file).",
            }

        # Case: PID file exists, but process is not running.
        if not system_process_utils.is_process_running(pid):
            system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "STOPPED",
                "pid": pid,
                "message": f"Stale PID {pid}, process not running.",
            }

        # Case: Process is running, verify it's the correct one.
        try:
            system_process_utils.verify_process_identity(
                pid, expected_exe, expected_arg
            )
            return {
                "status": "RUNNING",
                "pid": pid,
                "message": f"Web server running with PID {pid}.",
            }
        except ServerProcessError as e:
            # Case: PID points to a different, unrelated process.
            return {"status": "MISMATCHED_PROCESS", "pid": pid, "message": str(e)}

    except BSMError as e:  # Catches ConfigurationError, SystemError, etc.
        return {
            "status": "ERROR",
            "pid": pid,
            "message": f"An application error occurred: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting web server status: {e}", exc_info=True
        )
        return {
            "status": "ERROR",
            "pid": None,
            "message": f"Unexpected error: {str(e)}",
        }
