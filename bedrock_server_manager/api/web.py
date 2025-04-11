# bedrock-server-manager/bedrock_server_manager/api/web.py

import os
import logging
import subprocess
import platform
import signal
from typing import Dict, Optional, Any

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Local imports
from bedrock_server_manager.config.settings import settings, EXPATH
from bedrock_server_manager.error import (
    FileOperationError,
)
from bedrock_server_manager.web.app import run_web_server

logger = logging.getLogger("bedrock_server_manager")


# --- Helper function to get PID file path ---
def _get_web_pid_file_path() -> Optional[str]:
    """Gets the expected path for the web server PID file."""
    config_dir = getattr(settings, "_config_dir", None)
    if not config_dir or not os.path.isdir(config_dir):
        logger.error(
            "Cannot determine PID file path: Configuration directory not found or invalid."
        )
        return None
    return os.path.join(config_dir, "web_server.pid")


def start_web_server(
    host: Optional[str] = None, debug: bool = False, mode: str = "direct"
) -> Dict[str, Any]:
    """
    Starts the Flask/Waitress web server.

    Can run in two modes:
    - 'direct': Runs the server in the current process (blocking).
    - 'detached': Starts the server as a new background process and saves its PID to a file.

    Args:
        host: Optional host address.
        debug: If True, run in Flask's debug mode.
        mode: "direct" (default) or "detached".

    Returns:
        Dict indicating outcome (see previous refinements).

    Raises:
        ValueError: If mode is invalid.
        FileOperationError: If EXPATH or config dir cannot be determined for detached mode.
    """
    mode = mode.lower()
    if mode not in ["direct", "detached"]:
        raise ValueError("Invalid mode specified. Must be 'direct' or 'detached'.")

    logger.info(f"API: Attempting to start web server in '{mode}' mode...")
    logger.debug(f"Host='{host}', Debug={debug}")

    if mode == "direct":
        logger.info("API: Running web server directly (blocking process)...")
        try:
            run_web_server(host, debug)  # This blocks
            logger.info("API: Web server (direct mode) stopped.")
            return {"status": "success", "message": "Web server shut down."}
        except RuntimeError as e:
            logger.critical(
                f"API: Failed to start web server due to configuration error: {e}",
                exc_info=True,
            )
            return {"status": "error", "message": f"Configuration error: {e}"}
        except ImportError as e:
            logger.critical(f"API: Failed to start web server: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"API: Error running web server directly: {e}", exc_info=True)
            return {"status": "error", "message": f"Error running web server: {e}"}

    elif mode == "detached":
        logger.info("API: Starting web server in detached mode (background process)...")
        pid_file_path: Optional[str] = None
        try:
            # --- Get PID File Path ---
            pid_file_path = _get_web_pid_file_path()
            if not pid_file_path:
                # Error logged by helper
                raise FileOperationError(
                    "Cannot start detached server: unable to determine PID file path."
                )

            # --- Check if PID File Exists and Process is Running ---
            if os.path.exists(pid_file_path):
                try:
                    with open(pid_file_path, "r") as f:
                        existing_pid_str = f.read().strip()
                        if existing_pid_str:
                            existing_pid = int(existing_pid_str)
                            if PSUTIL_AVAILABLE and psutil.pid_exists(existing_pid):
                                # Check if the existing process matches our command if possible? Complex.
                                logger.warning(
                                    f"Detached web server might already be running (PID {existing_pid} found in '{pid_file_path}'). Aborting start."
                                )
                                return {
                                    "status": "error",
                                    "message": f"Web server already running (PID: {existing_pid}). Stop it first or delete the PID file ({pid_file_path}) if it's stale.",
                                }
                            else:
                                logger.warning(
                                    f"Stale PID file found ('{pid_file_path}' with PID {existing_pid}). Overwriting."
                                )
                                # Proceed to overwrite stale file
                except (ValueError, OSError) as read_err:
                    logger.warning(
                        f"Could not read or validate existing PID file '{pid_file_path}': {read_err}. Proceeding to overwrite."
                    )
                except ImportError:  # psutil might not be installed
                    logger.warning(
                        "psutil not available. Cannot verify if existing PID is running. Checking for PID file only."
                    )
                    # If PID file exists but we can't check psutil, maybe don't start? Or let user handle? Let's proceed but warn heavily.
                    logger.warning(
                        f"PID file '{pid_file_path}' exists, but process status cannot be verified without psutil. If the server is already running, starting another may cause issues."
                    )

            # --- Prepare and Start Process ---
            if not EXPATH or not os.path.exists(EXPATH):
                raise FileOperationError(
                    f"Main application executable/script not found at EXPATH: {EXPATH}"
                )

            command = [str(EXPATH), "start-web-server", "--mode", "direct"]
            if host:
                command.extend(["--host", host])
            if debug:
                command.append("--debug")

            logger.info(f"Executing detached command: {' '.join(command)}")

            creation_flags = 0
            start_new_session = False
            if platform.system() == "Windows":
                creation_flags = subprocess.CREATE_NO_WINDOW
            elif platform.system() == "Linux":
                start_new_session = True

            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
                start_new_session=start_new_session,
            )

            # --- Save PID to file ---
            pid = process.pid
            logger.info(
                f"API: Successfully started detached web server process with PID: {pid}"
            )
            try:
                logger.debug(f"Writing PID {pid} to file: {pid_file_path}")
                with open(pid_file_path, "w") as f:
                    f.write(str(pid))
                logger.info(f"Saved web server PID to '{pid_file_path}'.")
            except OSError as e:
                # Log error but don't necessarily fail the *start* if PID file write fails
                logger.error(
                    f"Failed to write PID {pid} to file '{pid_file_path}': {e}. Server started but stopping via API may fail.",
                    exc_info=True,
                )
                # Return success but include a warning in the message?
                return {
                    "status": "success",
                    "pid": pid,
                    "message": f"Web server started (PID: {pid}), but failed to write PID file. Manual stop may be required.",
                }

            return {
                "status": "success",
                "pid": pid,
                "message": f"Web server started in detached mode (PID: {pid}).",
            }

        except FileNotFoundError:
            error_msg = f"Executable or script not found at path: {EXPATH}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
        except FileOperationError as e:  # Catch EXPATH or config dir errors
            logger.error(f"API: Cannot start detached server: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
        except OSError as e:
            logger.error(
                f"API: OS error starting detached web server process: {e}",
                exc_info=True,
            )
            return {"status": "error", "message": f"OS error starting process: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error starting detached web server process: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Unexpected error starting detached process: {e}",
            }


# --- stop_web_server ---
def stop_web_server() -> Dict[str, str]:
    """
    Attempts to stop the detached web server process using its stored PID file.
    # ... (rest of docstring) ...
    """
    function_name = "stop_web_server"
    logger.info(f"API: Request received to stop the detached web server process.")

    if not PSUTIL_AVAILABLE:
        msg = "Cannot stop server: 'psutil' package is required but not installed."
        logger.error(msg)
        return {"status": "error", "message": msg}

    pid_file_path = _get_web_pid_file_path()
    if not pid_file_path:
        return {
            "status": "error",
            "message": "Cannot determine PID file path due to configuration issue.",
        }

    logger.debug(f"{function_name}: Reading PID from file: {pid_file_path}")

    pid: Optional[int] = None
    try:
        if os.path.isfile(pid_file_path):
            with open(pid_file_path, "r") as f:
                pid_str = f.read().strip()
                if pid_str:
                    pid = int(pid_str)
                    logger.info(f"{function_name}: Found PID {pid} in file.")
                else:
                    logger.warning(
                        f"{function_name}: PID file '{pid_file_path}' is empty."
                    )
        else:
            logger.info(
                f"{function_name}: PID file '{pid_file_path}' not found. Assuming server is not running."
            )
            return {
                "status": "success",
                "message": "Web server process not running (no PID file).",
            }

    except ValueError:
        logger.error(
            f"{function_name}: Invalid content in PID file '{pid_file_path}'. Expected an integer.",
            exc_info=True,
        )
        try:
            os.remove(pid_file_path)
        except OSError:
            pass
        return {"status": "error", "message": "Invalid PID file content. File removed."}
    except OSError as e:
        logger.error(
            f"{function_name}: Error reading PID file '{pid_file_path}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Error reading PID file: {e}"}
    except Exception as e:
        logger.error(
            f"{function_name}: Unexpected error reading PID file: {e}", exc_info=True
        )
        return {"status": "error", "message": f"Unexpected error reading PID file: {e}"}

    if pid is None:
        return {"status": "error", "message": "Could not retrieve PID from file."}

    # --- Stop Process using PID ---
    try:
        logger.debug(f"{function_name}: Checking if process with PID {pid} exists...")
        if not psutil.pid_exists(pid):
            logger.warning(
                f"{function_name}: Process with PID {pid} from file does not exist (stale PID file?). Cleaning up."
            )
            try:
                os.remove(pid_file_path)
            except OSError:
                pass
            return {
                "status": "success",
                "message": f"Web server process (PID {pid}) not found. Removed stale PID file.",
            }

        process = psutil.Process(pid)
        logger.info(
            f"{function_name}: Found process {pid}. Name: {process.name()}, Cmdline: {' '.join(process.cmdline())}"
        )

        logger.info(
            f"{function_name}: Attempting graceful termination (terminate/SIGTERM) for PID {pid}..."
        )
        process.terminate()

        try:
            process.wait(timeout=5)
            logger.info(f"{function_name}: Process {pid} terminated gracefully.")
        except psutil.TimeoutExpired:
            logger.warning(
                f"Process {pid} did not terminate gracefully. Attempting kill (SIGKILL)..."
            )
            process.kill()
            process.wait(timeout=2)
            logger.info(f"Process {pid} forcefully killed.")

        # Clean up PID file on successful termination (graceful or kill)
        try:
            if os.path.exists(pid_file_path):  # Check again before removing
                os.remove(pid_file_path)
                logger.debug(f"Removed PID file '{pid_file_path}'.")
        except OSError as rm_err:
            logger.warning(
                f"Could not remove PID file '{pid_file_path}' after stop: {rm_err}"
            )

        return {
            "status": "success",
            "message": f"Web server process (PID: {pid}) stopped successfully.",
        }

    except psutil.NoSuchProcess:
        logger.warning(
            f"Process with PID {pid} disappeared during stop attempt. Assuming stopped."
        )
        try:
            if os.path.exists(pid_file_path):
                os.remove(pid_file_path)
        except OSError:
            pass
        return {
            "status": "success",
            "message": f"Web server process (PID: {pid}) already stopped.",
        }
    except psutil.AccessDenied:
        error_msg = f"Permission denied trying to terminate process with PID {pid}."
        logger.error(f"{error_msg}")
        return {"status": "error", "message": error_msg}
    except Exception as e:
        logger.error(
            f"Unexpected error stopping process PID {pid}: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error stopping web server: {e}",
        }
