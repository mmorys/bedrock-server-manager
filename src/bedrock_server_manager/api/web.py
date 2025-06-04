# bedrock-server-manager/src/bedrock_server_manager/api/web.py
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
    ConfigError,
    ExecutableNotFoundError,
    PIDFileError,
    ProcessManagementError,
    ProcessVerificationError,
)

logger = logging.getLogger(__name__)
bsm = BedrockServerManager()


def start_web_server_api(
    host: Optional[Union[str, List[str]]] = None,
    debug: bool = False,
    mode: str = "direct",
) -> Dict[str, Any]:
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
        except (RuntimeError, ImportError) as e:
            return {
                "status": "error",
                "message": f"Failed to run web server directly: {e}",
            }
        except Exception as e:  # Catch-all for BSM errors
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
            except PIDFileError:  # Corrupt file
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
                    except ProcessVerificationError:
                        system_process_utils.remove_pid_file_if_exists(
                            pid_file_path
                        )  # Stale
                else:  # Stale PID
                    system_process_utils.remove_pid_file_if_exists(pid_file_path)

            command = [str(expected_exe), str(expected_arg), "--mode", "direct"]
            host_cmd_args_list = []
            if host:
                if isinstance(host, list):
                    host_cmd_args_list.extend(host)
                elif isinstance(host, str):
                    host_cmd_args_list.append(host)
            if host_cmd_args_list:
                command.append("--host")
                command.extend([str(h) for h in host_cmd_args_list if h])
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
        except ConfigError as e:
            return {"status": "error", "message": f"Configuration error: {e}"}
        except (ExecutableNotFoundError, ProcessManagementError, PIDFileError) as e:
            return {"status": "error", "message": f"Process management error: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error starting detached web server: {e}",
                exc_info=True,
            )
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}


def stop_web_server_api() -> Dict[str, str]:
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
    except ConfigError as e:
        return {"status": "error", "message": f"Configuration error: {e}"}
    except PIDFileError as e:
        system_process_utils.remove_pid_file_if_exists(bsm.get_web_ui_pid_path())
        return {"status": "error", "message": f"PID file error: {e}. File removed."}
    except ProcessVerificationError as e:
        system_process_utils.remove_pid_file_if_exists(bsm.get_web_ui_pid_path())
        return {
            "status": "error",
            "message": f"Process verification failed: {e}. PID file removed.",
        }
    except ProcessManagementError as e:
        if (
            "disappeared or was already stopped" in str(e).lower()
        ):  # from terminate_process_by_pid
            system_process_utils.remove_pid_file_if_exists(bsm.get_web_ui_pid_path())
            return {"status": "success", "message": "Web server was already stopped."}
        return {"status": "error", "message": f"Process management error: {e}"}
    except Exception as e:
        logger.error(f"API: Unexpected error stopping web server: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


def get_web_server_status_api() -> Dict[str, Any]:
    logger.debug("API: Getting web server status...")
    if not PSUTIL_AVAILABLE:
        return {
            "status": "error",
            "message": "'psutil' not installed. Cannot get process status.",
        }
    try:
        pid_file_path = bsm.get_web_ui_pid_path()
        expected_exe = bsm.get_web_ui_executable_path()
        expected_arg = bsm.get_web_ui_expected_start_arg()
        pid = None

        try:
            pid = system_process_utils.read_pid_from_file(pid_file_path)
        except PIDFileError:  # Corrupt
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
        except ProcessVerificationError as e:
            # PID file points to a WRONG process. Don't remove it here unless sure.
            return {"status": "MISMATCHED_PROCESS", "pid": pid, "message": str(e)}

    except ConfigError as e:
        return {"status": "ERROR", "pid": None, "message": f"Configuration error: {e}"}
    except ProcessManagementError as e:  # from is_process_running or verify
        return {
            "status": "ERROR",
            "pid": pid,
            "message": f"Process management error: {e}",
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
