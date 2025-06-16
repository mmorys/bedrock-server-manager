# bedrock_server_manager/api/web.py
"""
Provides API-level functions for managing the application's web server.

This module handles starting, stopping, and checking the status of the Flask-based
web UI. It interfaces with the BedrockServerManager for configuration details
and core process utilities for managing the web server process.
"""
import logging
from typing import Dict, Optional, Any, List, Union
import os

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.core.system import process as system_process_utils
from bedrock_server_manager.error import (
    BSMError,
    ConfigurationError,
    FileOperationError,
    ServerProcessError,
    SystemError,
)

logger = logging.getLogger(__name__)
bsm = BedrockServerManager()


def start_web_server_api(
    host: Optional[Union[str, List[str]]] = None,
    debug: bool = False,
    mode: str = "direct",
) -> Dict[str, Any]:
    """
    Starts the application's web server.

    The server can be started in 'direct' mode (blocking, in the current terminal)
    or 'detached' mode (background process).

    Args:
        host: Optional. The host address or list of addresses to bind to.
              Defaults to configured or Flask's default.
        debug: If True, run Flask in debug mode (intended for development).
        mode: "direct" or "detached".

    Returns:
        A dictionary indicating success or failure, and PID if started in detached mode.
        Example (detached): `{"status": "success", "pid": 1234, "message": "..."}`
        Example (direct): `{"status": "success", "message": "Web server shut down."}`
        Example (error): `{"status": "error", "message": "Error details..."}`
    """
    mode = mode.lower()
    if mode not in ["direct", "detached"]:
        return {
            "status": "error",
            "message": "Invalid mode. Must be 'direct' or 'detached'.",
        }

    logger.info(f"API: Attempting to start web server in '{mode}' mode...")
    if mode == "direct":
        try:
            bsm.start_web_ui_direct(host, debug)
            return {
                "status": "success",
                "message": "Web server (direct mode) shut down.",
            }
        except Exception as e:  # Catch-all for BSM errors or others
            logger.error(
                f"API: Error in BSM during direct web start: {e}", exc_info=True
            )
            return {
                "status": "error",
                "message": f"Unexpected error starting web server: {str(e)}",
            }

    elif mode == "detached":
        if not PSUTIL_AVAILABLE:  # Re-check as it's crucial for detached
            return {
                "status": "error",
                "message": "Cannot start in detached mode: 'psutil' is required.",
            }
        logger.info("API: Starting web server in detached mode...")
        try:
            pid_file_path = bsm.get_web_ui_pid_path()
            expected_exe = bsm.get_web_ui_executable_path()
            expected_arg = bsm.get_web_ui_expected_start_arg()

            existing_pid = None
            try:
                existing_pid = system_process_utils.read_pid_from_file(pid_file_path)
            except FileOperationError:  # Corrupt file
                system_process_utils.remove_pid_file_if_exists(pid_file_path)

            if existing_pid:
                if system_process_utils.is_process_running(existing_pid):
                    try:
                        system_process_utils.verify_process_identity(
                            existing_pid, expected_exe, expected_arg
                        )
                        return {
                            "status": "error",
                            "message": f"Web server already running (PID: {existing_pid}).",
                        }
                    except ServerProcessError:
                        system_process_utils.remove_pid_file_if_exists(
                            pid_file_path
                        )  # Stale
                else:  # Stale PID
                    system_process_utils.remove_pid_file_if_exists(pid_file_path)

            command = [str(expected_exe), "web", "start", "--mode", "direct"]

            # Normalize the host input into a list
            hosts_to_add = []
            if isinstance(host, str):
                hosts_to_add.append(host)
            elif isinstance(host, list):
                hosts_to_add.extend(host)

            # Append each host with its own --host flag
            for h in hosts_to_add:
                if h:  # Ensure not an empty string
                    command.extend(["--host", str(h)])

            if debug:
                command.append("--debug")

            new_pid = system_process_utils.launch_detached_process(
                command, pid_file_path
            )
            return {
                "status": "success",
                "pid": new_pid,
                "message": f"Web server started (PID: {new_pid}).",
            }
        except BSMError as e:
            return {"status": "error", "message": f"Failed to start web server: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error starting detached web server: {e}",
                exc_info=True,
            )
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}


def stop_web_server_api() -> Dict[str, str]:
    """
    Stops the detached web server process.

    It reads the PID from the stored PID file, verifies the process,
    and then terminates it.

    Returns:
        A dictionary indicating success or failure.
        Example: `{"status": "success", "message": "Web server stopped."}` or
                 `{"status": "error", "message": "Error details..."}`
    """
    logger.info("API: Attempting to stop detached web server...")
    if not PSUTIL_AVAILABLE:
        return {
            "status": "error",
            "message": "'psutil' not installed. Cannot manage processes.",
        }
    try:
        pid_file_path = bsm.get_web_ui_pid_path()
        expected_exe = bsm.get_web_ui_executable_path()
        expected_arg = bsm.get_web_ui_expected_start_arg()

        pid = system_process_utils.read_pid_from_file(pid_file_path)
        if pid is None:
            if os.path.exists(pid_file_path):  # Empty PID file
                system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "success",
                "message": "Web server not running (no valid PID file).",
            }

        if not system_process_utils.is_process_running(pid):
            system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "success",
                "message": f"Web server not running (stale PID {pid}).",
            }

        system_process_utils.verify_process_identity(pid, expected_exe, expected_arg)
        system_process_utils.terminate_process_by_pid(pid)  # Add timeouts if needed
        system_process_utils.remove_pid_file_if_exists(pid_file_path)
        return {"status": "success", "message": f"Web server (PID: {pid}) stopped."}
    except (FileOperationError, ServerProcessError) as e:
        system_process_utils.remove_pid_file_if_exists(bsm.get_web_ui_pid_path())
        error_type = (
            "PID file error"
            if isinstance(e, FileOperationError)
            else "Process verification failed"
        )
        return {"status": "error", "message": f"{error_type}: {e}. PID file removed."}
    except BSMError as e:
        return {"status": "error", "message": f"Error stopping web server: {e}"}
    except Exception as e:
        logger.error(f"API: Unexpected error stopping web server: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


def get_web_server_status_api() -> Dict[str, Any]:
    """
    Checks the status of the web server process.

    Verifies against a PID file and checks if the process is running and matches
    the expected web server process.

    Returns:
        A dictionary with the status ("RUNNING", "STOPPED", "MISMATCHED_PROCESS", "ERROR"),
        PID (if available), and a descriptive message.
        Example: `{"status": "RUNNING", "pid": 1234, "message": "..."}`
    """
    logger.debug("API: Getting web server status...")
    if not PSUTIL_AVAILABLE:
        return {
            "status": "error",
            "message": "'psutil' not installed. Cannot get process status.",
        }
    pid = None
    try:
        pid_file_path = bsm.get_web_ui_pid_path()
        expected_exe = bsm.get_web_ui_executable_path()
        expected_arg = bsm.get_web_ui_expected_start_arg()

        try:
            pid = system_process_utils.read_pid_from_file(pid_file_path)
        except FileOperationError:  # Corrupt
            system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "STOPPED",
                "pid": None,
                "message": "Corrupt PID file removed.",
            }

        if pid is None:
            if os.path.exists(pid_file_path):  # Empty
                system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "STOPPED",
                "pid": None,
                "message": "Web server not running (no PID file).",
            }

        if not system_process_utils.is_process_running(pid):
            system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "STOPPED",
                "pid": pid,
                "message": f"Stale PID {pid}, process not running.",
            }

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
            # PID file points to a WRONG process. Don't remove it here unless sure.
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
