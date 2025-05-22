# bedrock-server-manager/bedrock_server_manager/api/web.py

import os
import logging
import subprocess
import platform
import signal
from typing import Dict, Optional, Any, List, Union

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
    host: Optional[Union[str, List[str]]] = None,  # MODIFIED: Allow List[str]
    debug: bool = False,
    mode: str = "direct",
) -> Dict[str, Any]:
    """
    Starts the Flask/Waitress web server.

    Can run in two modes:
    - 'direct': Runs the server in the current process (blocking).
    - 'detached': Starts the server as a new background process and saves its PID to a file.

    Args:
        host: Optional host address or list of host addresses.
        debug: If True, run in Flask's debug mode.
        mode: "direct" (default) or "detached".

    Returns:
        Dict indicating outcome.

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
            # Assuming run_web_server is now correctly hinted and handles Optional[Union[str, List[str]]]
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
            pid_file_path = _get_web_pid_file_path()
            if not pid_file_path:
                raise FileOperationError(
                    "Cannot start detached server: unable to determine PID file path."
                )

            if os.path.exists(pid_file_path):
                try:
                    with open(pid_file_path, "r") as f:
                        existing_pid_str = f.read().strip()
                        if existing_pid_str:
                            existing_pid = int(existing_pid_str)
                            if PSUTIL_AVAILABLE and psutil.pid_exists(existing_pid):
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
                except (ValueError, OSError) as read_err:
                    logger.warning(
                        f"Could not read or validate existing PID file '{pid_file_path}': {read_err}. Proceeding to overwrite."
                    )
                except ImportError:
                    logger.warning(
                        "psutil not available. Cannot verify if existing PID is running. Checking for PID file only."
                    )
                    logger.warning(
                        f"PID file '{pid_file_path}' exists, but process status cannot be verified without psutil. If the server is already running, starting another may cause issues."
                    )

            if not EXPATH or not os.path.exists(
                EXPATH
            ):  # Ensure EXPATH is a valid path to your script/executable
                raise FileOperationError(
                    f"Main application executable/script not found at EXPATH: {EXPATH}"
                )

            command = [str(EXPATH), "start-web-server", "--mode", "direct"]
            if host:
                if isinstance(host, list):
                    if host:  # Ensure the list is not empty
                        command.append("--host")  # Add the --host flag
                        # Extend with each host string from the list
                        # argparse with nargs='+' on the other side will re-assemble this into a list
                        command.extend(
                            [str(h) for h in host if h]
                        )  # Ensure all elements are strings
                elif isinstance(host, str):
                    command.extend(["--host", str(host)])  # Ensure host is a string
                else:
                    # Should not happen if type hints are respected, but defensive
                    logger.warning(
                        f"Unexpected type for host: {type(host)}. Ignoring host parameter for detached command."
                    )
            if debug:
                command.append("--debug")

            logger.info(
                f"Executing detached command: {' '.join(command)}"
            )  # This should now work

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
                close_fds=True,
            )

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
                logger.error(
                    f"Failed to write PID {pid} to file '{pid_file_path}': {e}. Server started but stopping via API may fail.",
                    exc_info=True,
                )
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

        except FileNotFoundError:  # This can happen if EXPATH is wrong
            error_msg = f"Executable or script not found at path: {EXPATH}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}
        except FileOperationError as e:
            logger.error(f"API: Cannot start detached server: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
        except OSError as e:  # subprocess.Popen can raise OSError
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

    This function locates the web server's Process ID (PID) from a PID file.
    It then verifies that the running process with this PID is the correct
    web server by inspecting its command line arguments. This verification
    checks if the process was launched by the expected Python executable and
    if it includes a specific server startup argument (e.g., 'start-web-server').

    If the process is confirmed as the target server, a graceful termination
    (SIGTERM or equivalent) is attempted. If the process does not terminate
    within a timeout period, it is forcefully killed (SIGKILL or equivalent).
    The PID file is automatically removed upon successful termination or if it
    is found to be stale (e.g., PID not running, empty, or points to an
    unrelated process).

    Returns:
        Dict[str, str]: Dictionary indicating the outcome of the stop attempt.
                        It contains a "status" key ('success' or 'error')
                        and a "message" key with a descriptive string.

    Raises:
        None: This function is designed to catch internal exceptions and report
              outcomes through the returned dictionary. Prerequisites, such as
              the 'psutil' package availability or PID file path configuration,
              are checked internally, and failures are reported in the
              returned dictionary's status and message.
    """

    function_name = "stop_web_server"
    EXPECTED_SERVER_ARGUMENT = "start-web-server"
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
                    # Treat empty PID file as if server is not running, but clean up the file.
                    try:
                        os.remove(pid_file_path)
                        logger.info(
                            f"{function_name}: Removed empty PID file '{pid_file_path}'."
                        )
                    except OSError as e:
                        logger.warning(
                            f"{function_name}: Could not remove empty PID file '{pid_file_path}': {e}"
                        )
                    return {
                        "status": "success",  # Or "error" depending on desired strictness
                        "message": "Web server not running (PID file was empty, now removed).",
                    }
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
            os.remove(pid_file_path)  # Corrupt file, remove it
            logger.info(f"{function_name}: Removed corrupt PID file '{pid_file_path}'.")
        except OSError:
            pass  # Best effort
        return {"status": "error", "message": "Invalid PID file content. File removed."}
    except OSError as e:
        logger.error(
            f"{function_name}: Error reading PID file '{pid_file_path}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Error reading PID file: {e}"}
    except Exception as e:  # Catch-all for unexpected issues during PID read
        logger.error(
            f"{function_name}: Unexpected error reading PID file: {e}", exc_info=True
        )
        return {"status": "error", "message": f"Unexpected error reading PID file: {e}"}

    if pid is None:  # Should have been handled by empty file case, but as a safeguard
        logger.error(
            f"{function_name}: Could not retrieve PID from file '{pid_file_path}' (file was likely empty or became empty)."
        )
        return {
            "status": "error",
            "message": "Could not retrieve PID from file (file was empty).",
        }

    # --- Stop Process using PID ---
    try:
        logger.debug(f"{function_name}: Checking if process with PID {pid} exists...")
        if not psutil.pid_exists(pid):
            logger.warning(
                f"{function_name}: Process with PID {pid} from file does not exist (stale PID file?). Cleaning up."
            )
            try:
                if os.path.exists(pid_file_path):  # Check existence before removing
                    os.remove(pid_file_path)
                    logger.info(
                        f"{function_name}: Removed stale PID file '{pid_file_path}'."
                    )
            except OSError:
                pass  # Best effort
            return {
                "status": "success",
                "message": f"Web server process (PID {pid}) not found. Removed stale PID file.",
            }

        process = psutil.Process(pid)

        # --- !!! NEW VERIFICATION STEP !!! ---
        cmdline: Optional[List[str]] = None
        proc_name: Optional[str] = None
        try:
            cmdline = process.cmdline()
            proc_name = process.name()
        except psutil.AccessDenied:
            logger.error(
                f"{function_name}: Access denied when trying to get command line for PID {pid} (Name: {process.name() if not proc_name else proc_name}). Cannot verify process identity."
            )
            return {
                "status": "error",
                "message": f"Access denied for PID {pid}, cannot verify it's the web server.",
            }
        except psutil.ZombieProcess:
            logger.warning(
                f"{function_name}: Process PID {pid} is a zombie. Assuming stopped or stopping."
            )
            try:  # Clean up PID file for zombie process
                if os.path.exists(pid_file_path):
                    os.remove(pid_file_path)
            except OSError:
                pass
            return {
                "status": "success",
                "message": f"Web server process (PID {pid}) is a zombie. PID file removed.",
            }
        # Catch other psutil errors if cmdline() or name() fail for other reasons
        except psutil.Error as e_psutil:
            logger.error(
                f"{function_name}: Error getting process info for PID {pid}: {e_psutil}. Cannot verify identity."
            )
            return {
                "status": "error",
                "message": f"Error getting info for PID {pid}: {e_psutil}. Cannot verify.",
            }

        if (
            not cmdline
        ):  # cmdline() can return empty list for some system processes or if permissions are weird
            logger.warning(
                f"{function_name}: Process PID {pid} (Name: {proc_name}) has an empty command line. Cannot verify. Assuming stale PID."
            )
            try:  # Clean up stale PID file
                if os.path.exists(pid_file_path):
                    os.remove(pid_file_path)
            except OSError:
                pass
            return {
                "status": "error",
                "message": f"Process PID {pid} (Name: {proc_name}) has empty command line. Removed potentially stale PID file.",
            }

        # EXPATH is the current executable.
        expected_executable_path = EXPATH

        # Check 1: Does the executable match?
        # We use os.path.samefile for a robust check (handles symlinks, different path representations)
        # Fallback to basename comparison if samefile fails (e.g., one path is relative, or permissions)
        executable_matches = False
        try:
            # Resolve both paths to their canonical form before comparing
            # This handles symlinks and relative paths better.
            actual_proc_exe_resolved = os.path.realpath(cmdline[0])
            expected_exe_resolved = os.path.realpath(expected_executable_path)
            if actual_proc_exe_resolved == expected_exe_resolved:
                executable_matches = True
        except (
            OSError,
            FileNotFoundError,
            IndexError,
        ):  # IndexError if cmdline is empty (already checked)
            # Fallback to basename comparison if realpath or samefile fails
            if os.path.basename(cmdline[0]) == os.path.basename(
                expected_executable_path
            ):
                executable_matches = True

        # Check 2: Does the command line contain the expected server argument?
        argument_present = (
            EXPECTED_SERVER_ARGUMENT in cmdline[1:]
        )  # Check in arguments, not the executable path itself

        if not (executable_matches and argument_present):
            mismatched_msg = (
                f"{function_name}: PID {pid} (Name: {proc_name}, Cmd: {' '.join(cmdline)}) "
                f"does not appear to be the correct web server process. "
                f"Expected executable like '{expected_executable_path}' and argument '{EXPECTED_SERVER_ARGUMENT}'. "
                "Not stopping this process to prevent killing an unrelated one."
            )
            logger.error(mismatched_msg)
            # The PID file is pointing to a wrong process or is stale. Remove it.
            try:
                if os.path.exists(pid_file_path):
                    os.remove(pid_file_path)
                    logger.info(
                        f"{function_name}: Removed stale PID file '{pid_file_path}' as it pointed to an unrelated process."
                    )
            except OSError as rm_err:
                logger.warning(
                    f"{function_name}: Could not remove stale PID file '{pid_file_path}': {rm_err}"
                )
            return {
                "status": "error",
                "message": f"PID {pid} is not the expected web server (Cmd: {' '.join(cmdline)[:100]}...). PID file removed as stale.",
            }

        logger.info(
            f"{function_name}: Process {pid} (Name: {proc_name}, Cmd: {' '.join(cmdline)}) "
            f"confirmed as target web server."
        )
        # --- END VERIFICATION STEP ---

        logger.info(
            f"{function_name}: Attempting graceful termination (terminate/SIGTERM) for PID {pid}..."
        )
        process.terminate()

        try:
            process.wait(timeout=5)  # Increased timeout slightly
            logger.info(f"{function_name}: Process {pid} terminated gracefully.")
        except psutil.TimeoutExpired:
            logger.warning(
                f"{function_name}: Process {pid} did not terminate gracefully within 5s. Attempting kill (SIGKILL)..."
            )
            process.kill()
            process.wait(timeout=2)  # Wait for kill confirmation
            logger.info(f"{function_name}: Process {pid} forcefully killed.")
        # psutil.NoSuchProcess can also be raised by wait() if already gone

        # Clean up PID file on successful termination (graceful or kill)
        try:
            if os.path.exists(pid_file_path):  # Check again before removing
                os.remove(pid_file_path)
                logger.debug(
                    f"{function_name}: Removed PID file '{pid_file_path}' after successful stop."
                )
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
            f"{function_name}: Process with PID {pid} disappeared during stop attempt or was already gone. Assuming stopped."
        )
        try:
            if os.path.exists(pid_file_path):
                os.remove(pid_file_path)
                logger.info(
                    f"{function_name}: Removed PID file for already stopped process PID {pid}."
                )
        except OSError:
            pass  # Best effort
        return {
            "status": "success",
            "message": f"Web server process (PID: {pid}) already stopped or disappeared. PID file removed.",
        }
    except psutil.AccessDenied:  # Could happen during terminate/kill too
        error_msg = f"Permission denied trying to terminate process with PID {pid}."
        logger.error(f"{function_name}: {error_msg}")
        return {"status": "error", "message": error_msg}
    except Exception as e:  # Catch-all for unexpected issues during process stop
        logger.error(
            f"{function_name}: Unexpected error stopping process PID {pid}: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error stopping web server (PID: {pid}): {e}",
        }
