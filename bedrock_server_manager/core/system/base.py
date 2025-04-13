# bedrock-server-manager/bedrock_server_manager/core/system/base.py
"""
Provides base system utilities and cross-platform functionalities.

Includes prerequisite checks, internet connectivity verification, permission setting,
and process status/resource monitoring using platform-agnostic approaches where possible,
or acting as a dispatcher to platform-specific implementations.
"""

import platform
import shutil
import logging
import socket
import stat
import subprocess
import os
import time
from datetime import timedelta
from typing import Optional, Dict, Any

# Third-party imports
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Local imports
from bedrock_server_manager.error import (
    SetFolderPermissionsError,
    DirectoryError,
    MissingArgumentError,
    CommandNotFoundError,
    ResourceMonitorError,
    FileOperationError,
    MissingPackagesError,
    InternetConnectivityError,
)

logger = logging.getLogger("bedrock_server_manager")


def check_prerequisites() -> None:
    """
    Checks if essential command-line tools are available on the system.

    Currently checks for 'screen' and 'systemctl' (implicitly) on Linux. No-op on Windows.

    Raises:
        MissingPackagesError: If any required packages/commands are missing on Linux.
    """
    os_name = platform.system()
    logger.debug(f"Checking prerequisites for operating system: {os_name}")

    if os_name == "Linux":
        # Define essential Linux commands needed
        required_commands = [
            "screen",
            "systemctl",
            "pgrep",
            "crontab",
        ]
        missing_commands = []

        for command in required_commands:
            if shutil.which(command) is None:
                logger.warning(f"Required command '{command}' not found in PATH.")
                missing_commands.append(command)

        if missing_commands:
            error_msg = f"Missing required command(s) on Linux: {', '.join(missing_commands)}. Please install them."
            logger.error(error_msg)
            raise MissingPackagesError(error_msg)
        else:
            logger.debug("All required Linux prerequisites appear to be installed.")

    elif os_name == "Windows":
        # Check for optional but recommended psutil
        if not PSUTIL_AVAILABLE:
            logger.warning(
                "'psutil' package not found. Process monitoring features will be unavailable."
            )

        # Check for schtasks
        if shutil.which("schtasks") is None:
            error_msg = "'schtasks.exe' command not found. Task scheduling features will be unavailable."
            logger.error(error_msg)
            # Eaise MissingPackagesError
            raise MissingPackagesError(error_msg)

        logger.debug(
            "Windows prerequisites checked (schtasks found, psutil recommended)."
        )

    else:
        logger.warning(
            f"Prerequisite check not implemented for unsupported operating system: {os_name}"
        )


def check_internet_connectivity(
    host: str = "8.8.8.8", port: int = 53, timeout: int = 3
) -> None:
    """
    Checks for basic internet connectivity by attempting a TCP socket connection.

    Defaults to checking Google's public DNS server (8.8.8.8) on the standard DNS port (53).

    Args:
        host: The hostname or IP address to connect to.
        port: The port number to connect to.
        timeout: The connection timeout in seconds.

    Raises:
        InternetConnectivityError: If the socket connection fails within the timeout.
    """
    logger.debug(
        f"Checking internet connectivity by attempting connection to {host}:{port}..."
    )
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        logger.debug("Internet connectivity check successful.")
    except socket.timeout:
        error_msg = f"Connectivity check failed: Connection to {host}:{port} timed out after {timeout} seconds."
        logger.error(error_msg)
        raise InternetConnectivityError(error_msg) from None
    except (
        OSError
    ) as ex:  # Catches errors like "Network is unreachable" or DNS resolution failure
        error_msg = (
            f"Connectivity check failed: Cannot connect to {host}:{port}. Error: {ex}"
        )
        logger.error(error_msg)
        raise InternetConnectivityError(error_msg) from ex
    except Exception as e:  # Catch any other unexpected errors
        error_msg = f"An unexpected error occurred during connectivity check: {e}"
        logger.error(error_msg, exc_info=True)
        raise InternetConnectivityError(error_msg) from e


def set_server_folder_permissions(server_dir: str) -> None:
    """
    Sets appropriate file and directory permissions for the server installation directory.

    - Linux: Sets owner/group to current user/group, sets 775 for dirs, 664 for files,
             and 755 for the 'bedrock_server' executable.
    - Windows: Attempts to ensure the 'write' permission is set for files and directories
               (removes read-only attribute).

    Args:
        server_dir: The full path to the server's installation directory.

    Raises:
        MissingArgumentError: If `server_dir` is empty.
        DirectoryError: If `server_dir` does not exist or is not a directory.
        SetFolderPermissionsError: If setting permissions fails due to OS errors.
    """
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")
    if not os.path.isdir(server_dir):
        raise DirectoryError(
            f"Server directory does not exist or is not a directory: '{server_dir}'"
        )

    os_name = platform.system()
    logger.debug(
        f"Attempting to set appropriate permissions for server directory: {server_dir} (OS: {os_name})"
    )

    try:
        if os_name == "Linux":
            try:
                # Get effective UID/GID - use these for ownership
                current_uid = os.geteuid()
                current_gid = os.getegid()
                logger.debug(
                    f"Setting ownership to UID={current_uid}, GID={current_gid}"
                )

                # Set initial permissions on the base directory
                os.chown(server_dir, current_uid, current_gid)
                os.chmod(server_dir, 0o775)  # rwxrwxr-x

                # Walk through directory tree
                for root, dirs, files in os.walk(server_dir):
                    # Set ownership and permissions for subdirectories
                    for d in dirs:
                        dir_path = os.path.join(root, d)
                        os.chown(dir_path, current_uid, current_gid)
                        os.chmod(dir_path, 0o775)  # rwxrwxr-x
                        # logger.debug(f"Set permissions 775 on dir: {dir_path}")
                    # Set ownership and permissions for files
                    for f in files:
                        file_path = os.path.join(root, f)
                        os.chown(file_path, current_uid, current_gid)
                        if os.path.basename(file_path) == "bedrock_server":
                            # Executable needs execute permissions
                            os.chmod(
                                file_path, 0o775
                            )  # rwxrwxr-x (or 755 rwxr-xr-x if group write isn't needed)
                            logger.debug(
                                f"Set executable permissions (775) on: {file_path}"
                            )
                        else:
                            # Regular files
                            os.chmod(file_path, 0o664)  # rw-rw-r--
                            # logger.debug(f"Set permissions 664 on file: {file_path}")

                logger.info(f"Successfully set Linux permissions for: {server_dir}")
            except OSError as e:
                logger.error(
                    f"Failed to set Linux permissions for '{server_dir}': {e}",
                    exc_info=True,
                )
                raise SetFolderPermissionsError(
                    f"Failed to set permissions/ownership: {e}"
                ) from e

        elif os_name == "Windows":
            logger.debug(
                "Attempting to ensure write permissions (remove read-only) on Windows..."
            )
            # Use the separate remove_readonly function for clarity
            remove_readonly(server_dir)  # This function handles walking the tree
            logger.debug(f"Ensured write permissions for: {server_dir}")

        else:
            logger.warning(
                f"Permission setting not implemented for unsupported OS: {os_name}"
            )

    except Exception as e:  # Catch any unexpected errors
        logger.error(
            f"Unexpected error setting permissions for '{server_dir}': {e}",
            exc_info=True,
        )
        raise SetFolderPermissionsError(
            f"Unexpected error setting permissions: {e}"
        ) from e


def is_server_running(server_name: str, base_dir: str) -> bool:
    """
    Checks if a Bedrock server process corresponding to the server name is running.

    - Linux: Checks if a `screen` session named `bedrock-{server_name}` exists.
    - Windows: Checks if a `bedrock_server.exe` process exists whose executable path
               matches the expected location based on `base_dir` and `server_name`.

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server's folder.

    Returns:
        True if a matching server process is found, False otherwise.

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        CommandNotFoundError: If required commands (`screen` on Linux) are not found.
        ResourceMonitorError: If `psutil` is unavailable on Windows.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    os_name = platform.system()
    logger.debug(f"Checking running status for server '{server_name}' (OS: {os_name})")

    if os_name == "Linux":
        screen_cmd = shutil.which("screen")
        if not screen_cmd:
            logger.error("'screen' command not found. Cannot check server status.")
            raise CommandNotFoundError("screen")
        try:
            # Use screen -ls to list sessions and check for the specific session name
            screen_session_name = f"bedrock-{server_name}"
            process = subprocess.run(
                [screen_cmd, "-ls"],
                capture_output=True,
                text=True,
                check=False,  # Don't raise error if screen -ls fails (e.g., no sessions)
                encoding="utf-8",
                errors="replace",
            )
            # Check if the specific session name exists in the output (usually starts with PID.session_name)
            # Add dot prefix check for robustness as screen often lists as ".session_name"
            is_running = (
                f".{screen_session_name}\t" in process.stdout
                or f"\t{screen_session_name}\t" in process.stdout
            )
            logger.debug(f"Server '{server_name}' running (screen check): {is_running}")
            return is_running
        except FileNotFoundError:  # Safeguard
            logger.error("'screen' command not found unexpectedly.")
            raise CommandNotFoundError("screen") from None
        except Exception as e:
            logger.error(
                f"Error checking screen sessions for server '{server_name}': {e}",
                exc_info=True,
            )
            return False  # Assume not running if check fails

    elif os_name == "Windows":
        if not PSUTIL_AVAILABLE:
            logger.error(
                "'psutil' package not found. Cannot check server status on Windows."
            )
            raise ResourceMonitorError("'psutil' is required on Windows.")

        try:
            # Construct the expected full, normalized path to the target executable
            expected_exe_path = os.path.join(
                base_dir, server_name, "bedrock_server.exe"
            )
            normalized_expected_exe = os.path.normcase(
                os.path.abspath(expected_exe_path)
            )
            logger.debug(
                f"Searching for process with executable path: {normalized_expected_exe}"
            )

            for proc in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    proc_info = proc.info
                    # Quick check on name
                    if proc_info["name"] == "bedrock_server.exe":
                        proc_exe_path = proc_info.get("exe")
                        if proc_exe_path:
                            # Compare normalized absolute paths
                            normalized_proc_exe = os.path.normcase(
                                os.path.abspath(proc_exe_path)
                            )
                            if normalized_proc_exe == normalized_expected_exe:
                                logger.debug(
                                    f"Found matching process for server '{server_name}' with PID {proc_info['pid']}."
                                )
                                return True  # Found the specific server process

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue  # Ignore processes that ended, we can't access, or are zombies
                except Exception as proc_err:
                    logger.warning(
                        f"Error accessing info for process PID {proc.pid if proc else 'N/A'}: {proc_err}",
                        exc_info=True,
                    )

            # If loop finishes without returning True
            logger.debug(
                f"No running process found with executable path matching '{normalized_expected_exe}'."
            )
            return False

        except Exception as e:
            logger.error(f"Error iterating processes on Windows: {e}", exc_info=True)
            return False  # Assume not running if process iteration fails

    else:
        logger.error(f"Unsupported operating system for running check: {os_name}")
        return False


# --- Global state for delta CPU calculation ---
_last_cpu_times: Dict[int, psutil._common.scpustats] = (
    {}
)  # Store previous psutil._common.scpustat objects
_last_timestamp: Optional[float] = None  # Store timestamp of the last update
# --- End Global State ---


def _get_bedrock_process_info(
    server_name: str, base_dir: str
) -> Optional[Dict[str, Any]]:
    """
    Gets resource usage information (PID, CPU%, Mem MB, Uptime) for a running Bedrock server process.

    Identifies the process based on platform specifics. Uses `psutil` for details.
    Calculates CPU usage based on the difference in CPU times between consecutive calls
    (delta method).

    NOTE: The first call for a specific process after startup or after a period of
          inactivity in monitoring will report 0.0% CPU. Accuracy depends on regular calls.
          CPU% might still report 0% under Linux/screen due to process nesting.

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server's folder.

    Returns:
        A dictionary containing process information {'pid', 'cpu_percent', 'memory_mb', 'uptime'},
        or None if the server process is not found, inaccessible, or `psutil` is unavailable.

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        ResourceMonitorError: If `psutil` is unavailable, or if an unexpected error occurs
                              during process detail retrieval.
    """
    # Declare intent to modify global variables
    global _last_timestamp

    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    if not PSUTIL_AVAILABLE:
        logger.error("'psutil' package not found. Cannot get process info.")
        raise ResourceMonitorError("'psutil' is required for process monitoring.")

    logger.debug(
        f"Attempting to get process info for server '{server_name}' (using delta CPU)..."
    )
    bedrock_process: Optional[psutil.Process] = None
    pid: Optional[int] = None
    os_name = platform.system()
    target_server_dir = os.path.normpath(
        os.path.abspath(os.path.join(base_dir, server_name))
    )

    try:
        # --- Find the target Bedrock Process ---
        if os_name == "Linux":
            screen_session_name = f"bedrock-{server_name}"
            parent_screen_pid: Optional[int] = None
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if proc.info[
                        "name"
                    ] == "screen" and screen_session_name in " ".join(
                        proc.info.get("cmdline", [])
                    ):
                        parent_screen_pid = proc.info["pid"]
                        break
                except (psutil.Error, TypeError):
                    continue
            if not parent_screen_pid:
                return None  # Screen session not found

            found_child = False
            for proc in psutil.process_iter(["pid", "ppid", "name", "cwd", "status"]):
                try:
                    if (
                        proc.info["name"] == "bedrock_server"
                        and proc.info["status"] != psutil.STATUS_ZOMBIE
                        and proc.info.get("ppid") == parent_screen_pid
                        and proc.info.get("cwd")
                    ):
                        proc_cwd_normalized = os.path.normpath(
                            os.path.abspath(proc.info["cwd"])
                        )
                        if proc_cwd_normalized == target_server_dir:
                            pid = proc.info["pid"]
                            bedrock_process = psutil.Process(pid)
                            found_child = True
                            break
                except (psutil.Error, TypeError):
                    continue
            if not found_child:
                return None  # Child not found matching criteria

        elif os_name == "Windows":
            expected_exe_path = os.path.join(
                base_dir, server_name, "bedrock_server.exe"
            )
            normalized_expected_exe = os.path.normcase(
                os.path.abspath(expected_exe_path)
            )
            found_proc = False
            for proc in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    if proc.info["name"] == "bedrock_server.exe":
                        proc_exe = proc.info.get("exe")
                        if (
                            proc_exe
                            and os.path.normcase(os.path.abspath(proc_exe))
                            == normalized_expected_exe
                        ):
                            pid = proc.info["pid"]
                            bedrock_process = psutil.Process(pid)
                            found_proc = True
                            break
                except (psutil.Error, TypeError):
                    continue
            if not found_proc:
                return None
        else:
            logger.error(f"Process info retrieval not supported on OS: {os_name}")
            return None

        # --- Get Process Details using psutil AND Calculate Delta CPU ---
        if bedrock_process and pid:
            try:
                with bedrock_process.oneshot():
                    # --- CPU Delta Calculation ---
                    current_cpu_times: psutil._common.scpustats = (
                        bedrock_process.cpu_times()
                    )
                    current_timestamp = time.time()
                    cpu_percent = 0.0  # Default for first call or error

                    # Check if we have previous data for *this specific PID*
                    if pid in _last_cpu_times and _last_timestamp is not None:
                        time_delta = current_timestamp - _last_timestamp
                        if (
                            time_delta > 0.01
                        ):  # Avoid division by zero or tiny intervals
                            prev_cpu_times: psutil._common.scpustat = _last_cpu_times[
                                pid
                            ]
                            # Calculate total CPU time used (user + system) since last measurement
                            # Ensure attributes exist before subtraction
                            process_delta = (
                                current_cpu_times.user - prev_cpu_times.user
                            ) + (current_cpu_times.system - prev_cpu_times.system)

                            # Calculate percentage over the elapsed time window
                            # This represents utilization equivalent to one core. Can exceed 100 on multi-core.
                            cpu_percent = (process_delta / time_delta) * 100
                            logger.debug(
                                f"Delta CPU Calc: PID={pid}, TimeDelta={time_delta:.3f}s, CPUTimeDelta={process_delta:.4f}, CPU%={cpu_percent:.1f}"
                            )
                        else:
                            logger.debug(
                                f"Delta CPU Calc: Skipping for PID {pid} due to small time_delta ({time_delta:.3f}s)"
                            )
                    else:
                        logger.debug(
                            f"Delta CPU Calc: No previous data for PID {pid}. Reporting 0.0% CPU for first measurement."
                        )

                    # Update global state for the next call *for this PID*
                    _last_cpu_times[pid] = current_cpu_times
                    # Only update the *global* timestamp; time_delta uses this single point
                    _last_timestamp = current_timestamp
                    # --- End CPU Delta Calculation ---

                    # Memory Usage (RSS in MB)
                    memory_mb = bedrock_process.memory_info().rss / (1024 * 1024)

                    # Uptime
                    uptime_seconds = current_timestamp - bedrock_process.create_time()
                    uptime_str = str(timedelta(seconds=int(uptime_seconds)))

                    process_info = {
                        "pid": pid,
                        "cpu_percent": (
                            round(cpu_percent, 1) if cpu_percent is not None else 0.0
                        ),
                        "memory_mb": (
                            round(memory_mb, 1) if memory_mb is not None else 0.0
                        ),
                        "uptime": uptime_str,
                    }
                    logger.debug(
                        f"Retrieved process info for '{server_name}': {process_info}"
                    )
                    return process_info

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ) as e:
                logger.warning(
                    f"Process PID {pid} for '{server_name}' disappeared or access denied: {e}"
                )
                # Clean up stale PID entry from globals if process disappears
                if pid in _last_cpu_times:
                    try:
                        del _last_cpu_times[pid]
                    except KeyError:
                        pass
                    logger.debug(f"Removed stale PID {pid} from CPU time cache.")
                return None
            except Exception as detail_err:
                logger.error(
                    f"Error getting details for process PID {pid} ('{server_name}'): {detail_err}",
                    exc_info=True,
                )
                raise ResourceMonitorError(
                    f"Error getting process details for '{server_name}': {detail_err}"
                ) from detail_err
        else:
            logger.debug(f"Bedrock process object not obtained for '{server_name}'.")
            return None

    except Exception as e:
        # Catch unexpected errors during the process finding stage
        logger.error(
            f"Unexpected error getting process info for '{server_name}': {e}",
            exc_info=True,
        )
        raise ResourceMonitorError(
            f"Unexpected error getting process info for '{server_name}': {e}"
        ) from e


def remove_readonly(path: str) -> None:
    """
    Recursively removes the read-only attribute from a file or directory.

    Uses platform-specific methods (`chmod` on Linux, `attrib` on Windows).

    Args:
        path: The path to the file or directory.

    Raises:
        SetFolderPermissionsError: If removing the read-only attribute fails due to OS errors.
        FileOperationError: If an unexpected error occurs, or `attrib.exe` is not found on Windows.
        CommandNotFoundError: If `attrib.exe` cannot be found on Windows.
    """
    if not os.path.exists(path):
        logger.debug(f"Path '{path}' does not exist. Skipping remove_readonly.")
        return

    os_name = platform.system()
    logger.debug(
        f"Ensuring write permissions (removing read-only) for path: '{path}' (OS: {os_name})"
    )

    try:
        if os_name == "Windows":
            # Use attrib command as it reliably handles ACLs/inheritance issues sometimes missed by os.chmod
            attrib_cmd = shutil.which("attrib")
            if not attrib_cmd:
                # Try finding in System32 explicitly if not in PATH
                system32_attrib = os.path.join(
                    os.environ.get("SYSTEMROOT", "C:\\Windows"),
                    "System32",
                    "attrib.exe",
                )
                if os.path.isfile(system32_attrib):
                    attrib_cmd = system32_attrib
                else:
                    logger.error(
                        "'attrib.exe' command not found. Cannot remove read-only attribute."
                    )
                    raise CommandNotFoundError("attrib.exe")

            # Apply recursively (/S) and also process directories (/D)
            process = subprocess.run(
                [attrib_cmd, "-R", path, "/S", "/D"],
                check=True,
                capture_output=True,  # Capture output for logging/debugging
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            logger.debug(
                f"Windows 'attrib -R /S /D' executed for '{path}'. Output: {process.stdout}{process.stderr}"
            )
            logger.debug(
                f"Successfully ensured write permissions for '{path}' on Windows."
            )

        elif os_name == "Linux":
            # Set write permission for the owner (u+w) recursively
            logger.debug(
                f"Recursively adding write permission for owner on '{path}'..."
            )
            if os.path.isdir(path):
                # Set owner write on the top-level directory first
                os.chmod(path, os.stat(path).st_mode | stat.S_IWUSR)
                # Walk and set owner write on all contents
                for root, dirs, files in os.walk(path):
                    for name in dirs + files:
                        item_path = os.path.join(root, name)
                        try:
                            current_mode = os.stat(item_path).st_mode
                            os.chmod(item_path, current_mode | stat.S_IWUSR)
                        except OSError as chmod_err:
                            # Log warning but continue if possible
                            logger.warning(
                                f"Could not set write permission on '{item_path}': {chmod_err}",
                                exc_info=True,
                            )
            elif os.path.isfile(path):
                # Set owner write on the single file
                os.chmod(path, os.stat(path).st_mode | stat.S_IWUSR)
            else:
                logger.warning(
                    f"Path '{path}' is not a file or directory. Cannot set write permission."
                )

            logger.debug(
                f"Successfully ensured owner write permissions for '{path}' on Linux."
            )

        else:
            logger.warning(
                f"Read-only removal not implemented for unsupported OS: {os_name}"
            )

    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to remove read-only attribute using 'attrib' for '{path}'. Error: {e.stderr}"
        logger.error(error_msg, exc_info=True)
        raise SetFolderPermissionsError(error_msg) from e
    except FileNotFoundError:  # Should be caught by shutil.which, but safeguard
        logger.error("'attrib.exe' command not found unexpectedly.")
        raise CommandNotFoundError("attrib.exe") from None
    except OSError as e:
        logger.error(
            f"OS error while removing read-only attribute for '{path}': {e}",
            exc_info=True,
        )
        raise SetFolderPermissionsError(
            f"Failed to remove read-only attribute: {e}"
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error removing read-only attribute for '{path}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Unexpected error removing read-only attribute: {e}"
        ) from e
