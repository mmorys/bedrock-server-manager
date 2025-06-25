# bedrock_server_manager/core/system/base.py
"""Provides base system utilities and cross-platform functionalities.

This module includes functions for checking prerequisites, verifying internet
connectivity, setting filesystem permissions, and monitoring process status and
resource usage. It uses platform-agnostic approaches where possible or acts as
a dispatcher to platform-specific implementations.
"""

import platform
import shutil
import logging
import socket
import stat
import threading
import os
import time
from datetime import timedelta
from typing import Optional, Dict, Any, Tuple

# Third-party imports. psutil is optional but required for process monitoring.
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Local application imports.
from bedrock_server_manager.core.system import process as core_process
from bedrock_server_manager.error import (
    PermissionsError,
    AppFileNotFoundError,
    MissingArgumentError,
    CommandNotFoundError,
    ServerProcessError,
    SystemError,
    InternetConnectivityError,
    FileOperationError,
)

logger = logging.getLogger(__name__)


def check_internet_connectivity(
    host: str = "8.8.8.8", port: int = 53, timeout: int = 3
) -> None:
    """Checks for basic internet connectivity by attempting a TCP socket connection.

    Args:
        host: The hostname or IP address to connect to. Defaults to a Google DNS server.
        port: The port number to connect to. Defaults to the DNS port.
        timeout: The connection timeout in seconds.

    Raises:
        InternetConnectivityError: If the socket connection fails.
    """
    logger.debug(
        f"Checking internet connectivity by attempting connection to {host}:{port}..."
    )
    try:
        # Attempt to create a socket connection to a reliable external host.
        socket.create_connection((host, port), timeout=timeout).close()
        logger.debug("Internet connectivity check successful.")
    except socket.timeout:
        error_msg = f"Connectivity check failed: Connection to {host}:{port} timed out after {timeout} seconds."
        logger.error(error_msg)
        raise InternetConnectivityError(error_msg) from None
    except OSError as ex:
        error_msg = (
            f"Connectivity check failed: Cannot connect to {host}:{port}. Error: {ex}"
        )
        logger.error(error_msg)
        raise InternetConnectivityError(error_msg) from ex
    except Exception as e:
        error_msg = f"An unexpected error occurred during connectivity check: {e}"
        logger.error(error_msg, exc_info=True)
        raise InternetConnectivityError(error_msg) from e


def set_server_folder_permissions(server_dir: str) -> None:
    """Sets appropriate file and directory permissions for a server installation.

    - On Linux, it sets 775 for directories and the main executable, and 664 for
      other files, assigning ownership to the current user and group.
    - On Windows, it ensures the 'write' permission is set for all items.

    Args:
        server_dir: The full path to the server's installation directory.

    Raises:
        MissingArgumentError: If `server_dir` is empty.
        AppFileNotFoundError: If `server_dir` does not exist.
        PermissionsError: If setting permissions fails.
    """
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")
    if not os.path.isdir(server_dir):
        raise AppFileNotFoundError(server_dir, "Server directory")

    os_name = platform.system()
    logger.debug(
        f"Setting permissions for server directory: {server_dir} (OS: {os_name})"
    )

    try:
        if os_name == "Linux":
            current_uid = os.geteuid()
            current_gid = os.getegid()
            logger.debug(f"Setting ownership to UID={current_uid}, GID={current_gid}")

            for root, dirs, files in os.walk(server_dir, topdown=True):
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    os.chown(dir_path, current_uid, current_gid)
                    os.chmod(dir_path, 0o775)
                for f in files:
                    file_path = os.path.join(root, f)
                    os.chown(file_path, current_uid, current_gid)
                    # The main executable needs execute permissions.
                    if os.path.basename(file_path) == "bedrock_server":
                        os.chmod(file_path, 0o775)
                    else:
                        os.chmod(file_path, 0o664)
            # Set top-level permissions last.
            os.chown(server_dir, current_uid, current_gid)
            os.chmod(server_dir, 0o775)
            logger.info(f"Successfully set Linux permissions for: {server_dir}")

        elif os_name == "Windows":
            logger.debug("Ensuring write permissions (S_IWRITE) on Windows...")
            for root, dirs, files in os.walk(server_dir):
                for name in dirs + files:
                    path = os.path.join(root, name)
                    try:
                        current_mode = os.stat(path).st_mode
                        os.chmod(path, current_mode | stat.S_IWRITE | stat.S_IWUSR)
                    except OSError as e_chmod:
                        logger.warning(
                            f"Could not set write permission on '{path}': {e_chmod}"
                        )
            logger.info(
                f"Successfully ensured write permissions for: {server_dir} on Windows"
            )
        else:
            logger.warning(f"Permission setting not implemented for OS: {os_name}")

    except OSError as e:
        raise PermissionsError(
            f"Failed to set permissions for '{server_dir}': {e}"
        ) from e
    except Exception as e:
        raise PermissionsError(f"Unexpected error during permission setup: {e}") from e


def is_server_running(server_name: str, server_dir: str, config_dir: str) -> bool:
    """Checks if a Bedrock server process is running and verified.

    This method is a simple wrapper around `core_process.get_verified_bedrock_process`.

    Args:
        server_name: The name of the server.
        server_dir: The installation directory of the server.
        config_dir: The base configuration directory where the PID file is stored.

    Returns:
        True if a matching and verified server process is found, False otherwise.
    """
    if not all([server_name, server_dir, config_dir]):
        raise MissingArgumentError(
            "server_name, server_dir, and config_dir cannot be empty."
        )

    return (
        core_process.get_verified_bedrock_process(server_name, server_dir, config_dir)
        is not None
    )


def _handle_remove_readonly_onerror(func, path, exc_info):
    """An error handler for `shutil.rmtree` to handle read-only files.

    If an `OSError` occurs because a file is read-only, this handler attempts
    to change its permissions to be writable and then retries the operation.
    """
    if not os.access(path, os.W_OK):
        logger.debug(f"Path '{path}' is read-only. Attempting to make it writable.")
        try:
            os.chmod(path, stat.S_IWUSR | stat.S_IWRITE)
            func(path)  # Retry the original function (e.g., os.remove).
        except Exception as e:
            logger.warning(f"Failed to make '{path}' writable and retry operation: {e}")
            raise exc_info[1]
    else:
        # Re-raise the original exception if it wasn't a read-only issue.
        raise exc_info[1]


def delete_path_robustly(path_to_delete: str, item_description: str) -> bool:
    """Deletes a file or directory robustly, handling read-only attributes.

    Args:
        path_to_delete: The full path to the file or directory to delete.
        item_description: A human-readable description for logging purposes.

    Returns:
        True if deletion was successful or the path didn't exist, False otherwise.
    """
    if not os.path.exists(path_to_delete):
        logger.debug(
            f"{item_description.capitalize()} at '{path_to_delete}' not found, skipping."
        )
        return True

    logger.info(f"Preparing to delete {item_description}: {path_to_delete}")
    try:
        if os.path.isdir(path_to_delete):
            # Use the custom error handler for directories.
            shutil.rmtree(path_to_delete, onerror=_handle_remove_readonly_onerror)
            logger.info(
                f"Successfully deleted {item_description} directory: {path_to_delete}"
            )
        elif os.path.isfile(path_to_delete):
            # For single files, manually check and set permissions if needed.
            if not os.access(path_to_delete, os.W_OK):
                os.chmod(path_to_delete, stat.S_IWRITE | stat.S_IWUSR)
            os.remove(path_to_delete)
            logger.info(
                f"Successfully deleted {item_description} file: {path_to_delete}"
            )
        else:
            logger.warning(
                f"Path '{path_to_delete}' is not a file or directory. Skipping."
            )
            return False
        return True
    except Exception as e:
        logger.error(
            f"Failed to delete {item_description} at '{path_to_delete}': {e}",
            exc_info=True,
        )
        return False


# --- RESOURCE MONITOR ---
class ResourceMonitor:
    """
    A generic, singleton process resource monitor.

    This class ensures only one instance exists, preserving the state
    needed for calculations across multiple calls from different parts of the
    application. It correctly stores state on a per-process basis.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initializes the state for resource monitoring."""
        if not hasattr(self, "_initialized"):
            # THE FIX: Store a tuple of (cpu_times, timestamp) per PID.
            self._last_readings: Dict[int, Tuple[Any, float]] = {}
            self._initialized = True

    def get_stats(self, process: psutil.Process) -> Optional[Dict[str, Any]]:
        """
        Calculates resource usage statistics for the given process.
        """
        if not isinstance(process, psutil.Process):
            raise TypeError("Input must be a valid psutil.Process object.")

        pid = process.pid
        try:
            with process.oneshot():
                current_cpu_times = process.cpu_times()
                current_timestamp = time.time()
                cpu_percent = 0.0
                # Check if we have a previous reading for THIS specific PID.
                if pid in self._last_readings:
                    # Unpack the previous reading for this PID.
                    prev_cpu_times, prev_timestamp = self._last_readings[pid]

                    time_delta = current_timestamp - prev_timestamp
                    if time_delta > 0.01:
                        process_delta = (
                            current_cpu_times.user - prev_cpu_times.user
                        ) + (current_cpu_times.system - prev_cpu_times.system)

                        cpu_count = (
                            psutil.cpu_count() or 1
                        )  # Avoid division by zero on exotic systems
                        cpu_percent = (process_delta / time_delta) * 100 / cpu_count

                # Store the new reading (tuple) for THIS specific PID for the next call.
                self._last_readings[pid] = (current_cpu_times, current_timestamp)

                memory_mb = process.memory_info().rss / (1024 * 1024)
                uptime_seconds = current_timestamp - process.create_time()
                uptime_str = str(timedelta(seconds=int(uptime_seconds)))

                return {
                    "pid": pid,
                    "cpu_percent": round(cpu_percent, 1),
                    "memory_mb": round(memory_mb, 1),
                    "uptime": uptime_str,
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            if pid in self._last_readings:
                del self._last_readings[pid]
            return None
        except Exception as e:
            raise SystemError(f"Failed to get stats for PID {pid}: {e}") from e
