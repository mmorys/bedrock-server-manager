# bedrock-server-manager/bedrock_server_manager/core/system/base.py
import platform
import shutil
import logging
import socket
import stat
import psutil
import subprocess
import os
import time
from datetime import timedelta
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


def check_prerequisites():
    """Checks for required command-line tools (Linux-specific).

    Raises:
        MissingPackagesError: If required packages are missing on Linux.
    """
    if platform.system() == "Linux":
        packages = ["screen", "systemd"]
        missing_packages = []

        for pkg in packages:
            if shutil.which(pkg) is None:
                missing_packages.append(pkg)

        if missing_packages:
            logger.error(f"Missing required packages: {missing_packages}")
            raise MissingPackagesError(f"Missing required packages: {missing_packages}")
        else:
            logger.debug("All required packages are installed.")

    elif platform.system() == "Windows":
        logger.debug("No checks needed")

    else:
        logger.warning("Unsupported operating system.")


def check_internet_connectivity(host="8.8.8.8", port=53, timeout=3):
    """Checks for internet connectivity by attempting a socket connection.

    Args:
        host (str): The hostname or IP address to connect to.
        port (int): The port number to connect to.
        timeout (int): The timeout in seconds.

    Raises:
        InternetConnectivityError: If the connection fails.
    """
    logger.debug(
        f"Checking internet connectivity to {host}:{port} with timeout {timeout}s"
    )
    try:
        # Attempt a socket connection.
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        logger.debug("Internet connectivity OK.")
    except socket.error as ex:
        logger.error(f"Connectivity test failed: {ex}")
        raise InternetConnectivityError(f"Connectivity test failed: {ex}") from ex
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise InternetConnectivityError(f"An unexpected error occurred: {e}") from e


def set_server_folder_permissions(server_dir):
    """Sets appropriate owner:group and permissions on the server directory.

    Args:
        server_dir (str): The server directory.

    Raises:
        MissingArgumentError: If server_dir is empty.
        DirectoryError: If server_dir does not exist or is not a directory.
        SetFolderPermissionsError: If setting permissions fails.
    """

    if not server_dir:
        raise MissingArgumentError(
            "set_server_folder_permissions: server_dir is empty."
        )
    if not os.path.isdir(server_dir):
        raise DirectoryError(
            f"set_server_folder_permissions: server_dir '{server_dir}' does not exist or is not a directory."
        )

    if platform.system() == "Linux":
        try:
            real_user = os.getuid()
            real_group = os.getgid()
            logger.info(f"Setting folder permissions to {real_user}:{real_group}")

            for root, dirs, files in os.walk(server_dir):
                for d in dirs:
                    os.chown(os.path.join(root, d), real_user, real_group)
                    os.chmod(os.path.join(root, d), 0o775)
                    """logger.debug(
                        f"Set permissions on directory: {os.path.join(root, d)}"
                    )"""
                for f in files:
                    file_path = os.path.join(root, f)
                    os.chown(file_path, real_user, real_group)
                    if os.path.basename(file_path) == "bedrock_server":
                        os.chmod(file_path, 0o755)
                        logger.debug(f"Set execute permissions on: {file_path}")
                    else:
                        os.chmod(file_path, 0o664)
                        """logger.debug(f"Set permissions on file: {file_path}")"""
            logger.info("Folder permissions set.")
        except OSError as e:
            logger.error(f"Failed to set server folder permissions: {e}")
            raise SetFolderPermissionsError(
                f"Failed to set server folder permissions: {e}"
            ) from e

    elif platform.system() == "Windows":
        logger.info("Setting folder permissions...")
        try:
            for root, dirs, files in os.walk(server_dir):
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    current_permissions = os.stat(dir_path).st_mode
                    if not (current_permissions & stat.S_IWRITE):
                        os.chmod(dir_path, current_permissions | stat.S_IWRITE)
                        logger.debug(f"Set write permissions on directory: {dir_path}")
                for f in files:
                    file_path = os.path.join(root, f)
                    current_permissions = os.stat(file_path).st_mode
                    if not (current_permissions & stat.S_IWRITE):
                        os.chmod(file_path, current_permissions | stat.S_IWRITE)
                        logger.debug(f"Set write permissions on file: {file_path}")
            logger.info("Folder permissions set.")
        except OSError as e:
            logger.error(f"Failed to set folder permissions: {e}")
            raise SetFolderPermissionsError(
                f"Failed to set folder permissions on Windows: {e}"
            ) from e

    else:
        logger.warning("set_server_folder_permissions: Unsupported operating system.")


def is_server_running(server_name, base_dir):
    """Checks if the server is running.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.

    Returns:
        bool: True if the server is running, False otherwise.
    Raises:
        CommandNotFoundError: If the 'screen' command is not found on Linux.

    """
    logger.debug(f"Checking if server {server_name} is running")
    if platform.system() == "Linux":
        try:
            result = subprocess.run(
                ["screen", "-ls"],
                capture_output=True,
                text=True,
                check=False,
            )
            is_running = f".bedrock-{server_name}" in result.stdout
            logger.debug(f"Server {server_name} running: {is_running} (Linux - screen)")
            return is_running
        except FileNotFoundError:
            logger.error("screen command not found.")
            raise CommandNotFoundError(
                "screen", message="screen command not found."
            ) from None

    elif platform.system() == "Windows":
        try:
            # Construct the expected full path to the target executable
            target_exe_path = os.path.join(base_dir, server_name, "bedrock_server.exe")

            normalized_target_exe = os.path.normcase(os.path.abspath(target_exe_path))
            logger.debug(
                f"Looking for server {server_name} with normalized executable path: {normalized_target_exe}"
            )

            found_matching_process = False
            # Add 'exe' to the attributes we fetch
            for proc in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    proc_info = proc.info
                    # Check name first (quick filter)
                    if proc_info["name"] == "bedrock_server.exe":
                        proc_exe = proc_info["exe"]
                        # Check if executable path is available and not empty
                        if proc_exe:
                            # Normalize the process's executable path for comparison
                            normalized_proc_exe = os.path.normcase(
                                os.path.abspath(proc_exe)
                            )

                            # --- Crucial Change: Compare normalized executable paths ---
                            if normalized_proc_exe == normalized_target_exe:
                                logger.debug(
                                    f"Server {server_name} running: True (Windows - process {proc.pid} found with matching executable path: {normalized_proc_exe})"
                                )
                                found_matching_process = True
                                break  # Found the specific server, no need to check further

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,  # Might occur when trying to access proc_info['exe']
                    psutil.ZombieProcess,
                ):
                    # Process might have terminated, access denied, or is a zombie
                    # Ignore and continue checking other processes
                    pass
                except Exception as proc_err:
                    # Log error accessing specific process info but continue iterating
                    logger.warning(
                        f"Error accessing info for process {proc.pid if proc else 'N/A'}: {proc_err}"
                    )

            if found_matching_process:
                return True
            else:
                logger.debug(
                    f"Server {server_name} running: False (Windows - no bedrock_server.exe process found with executable path exactly matching {normalized_target_exe})"
                )
                return False

        except Exception as e:
            # General error during process iteration
            logger.error(f"Error checking processes on Windows: {e}")
            return False
    else:
        logger.error("Unsupported operating system for running check.")
        return False


_last_cpu_times = {}
_last_timestamp = None


def _get_bedrock_process_info(server_name, base_dir):
    """Gets resource usage information for the running Bedrock server,
    using delta-based CPU usage calculation similar to _linux_monitor.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers

    Returns:
        dict or None: A dictionary containing process information, or None
                      if the server is not running or an error occurs.
                      The dictionary has the following keys:
                        - pid (int): The process ID.
                        - cpu_percent (float): The CPU usage percentage.
                        - memory_mb (float): The memory usage in megabytes.
                        - uptime (str): The server uptime as a string.
    Raises:
        ResourceMonitorError: If there is any error during monitoring.
    """

    global _last_timestamp
    logger.debug(f"Getting Bedrock process info for: {server_name}")

    if platform.system() == "Linux":
        try:
            # Find the screen process running the Bedrock server
            screen_pid = None
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if proc.info[
                        "name"
                    ] == "screen" and f"bedrock-{server_name}" in " ".join(
                        proc.info["cmdline"]
                    ):
                        screen_pid = proc.info["pid"]
                        break
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue

            if not screen_pid:
                logger.warning(
                    f"No running 'screen' process found for service {server_name}."
                )
                return None

            # Find the Bedrock server process (child of screen)
            bedrock_pid = None
            try:
                screen_process = psutil.Process(screen_pid)
                for child in screen_process.children(recursive=True):
                    if "bedrock_server" in child.name():
                        bedrock_pid = child.pid
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

            if not bedrock_pid:
                logger.warning(
                    f"No running Bedrock server process found for service {server_name}."
                )
                return None

            # Get process details
            try:
                bedrock_process = psutil.Process(bedrock_pid)
                with bedrock_process.oneshot():
                    current_cpu_times = bedrock_process.cpu_times()

                    # Get previous CPU times and timestamp; if not set, initialize them.
                    if _last_timestamp is None:
                        _last_cpu_times[bedrock_pid] = current_cpu_times
                        _last_timestamp = time.time()
                        # Not enough data to calculate delta; return 0% CPU usage.
                        cpu_percent = 0.0
                    else:
                        current_timestamp = time.time()
                        time_delta = current_timestamp - _last_timestamp

                        prev_cpu_times = _last_cpu_times.get(
                            bedrock_pid, current_cpu_times
                        )
                        cpu_time_delta = (
                            current_cpu_times.user + current_cpu_times.system
                        ) - (prev_cpu_times.user + prev_cpu_times.system)
                        cpu_percent = (
                            (cpu_time_delta / time_delta * 100)
                            if time_delta > 0
                            else 0.0
                        )

                        # Update globals for the next call
                        _last_cpu_times[bedrock_pid] = current_cpu_times
                        _last_timestamp = current_timestamp

                    # Memory Usage (in MB)
                    memory_mb = bedrock_process.memory_info().rss / (1024 * 1024)

                    # Uptime calculation
                    uptime_seconds = time.time() - bedrock_process.create_time()
                    uptime_str = str(timedelta(seconds=int(uptime_seconds)))

                    logger.debug(
                        f"Process info: pid={bedrock_pid}, cpu={cpu_percent:.2f}%, mem={memory_mb:.2f}MB, uptime={uptime_str}"
                    )
                    return {
                        "pid": bedrock_pid,
                        "cpu_percent": cpu_percent,
                        "memory_mb": memory_mb,
                        "uptime": uptime_str,
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                logger.warning(f"Process {bedrock_pid} not found or access denied.")
                return None

        except Exception as e:
            logger.error(f"Error during monitoring: {e}")
            raise ResourceMonitorError(f"Error during monitoring: {e}") from e

    elif platform.system() == "Windows":
        bedrock_pid = None
        try:

            target_exe_path = os.path.join(base_dir, server_name, "bedrock_server.exe")
            normalized_target_exe = os.path.normcase(os.path.abspath(target_exe_path))
            logger.debug(
                f"Looking for server process for {server_name} with exe path: {normalized_target_exe}"
            )

            for proc in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    proc_info = proc.info
                    # Check name first
                    if proc_info["name"] == "bedrock_server.exe":
                        proc_exe = proc_info.get("exe")
                        if proc_exe:
                            normalized_proc_exe = os.path.normcase(
                                os.path.abspath(proc_exe)
                            )

                            if normalized_proc_exe == normalized_target_exe:
                                bedrock_pid = proc_info["pid"]
                                logger.debug(
                                    f"Found matching process for {server_name}: PID {bedrock_pid}"
                                )
                                break  # Exit loop once found
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    pass  # Ignore processes that ended or we can't access
                except Exception as proc_err:
                    logger.warning(
                        f"Error accessing info for process {proc.pid if proc else 'N/A'}: {proc_err}"
                    )

            if not bedrock_pid:
                # Log updated to reflect the check performed
                logger.warning(
                    f"No running Bedrock server process found for {server_name} with exe path {normalized_target_exe}."
                )
                return None  # Or return an empty dict, depending on desired behaviour

            # Get process details (this part remains largely the same)
            try:
                bedrock_process = psutil.Process(bedrock_pid)
                with bedrock_process.oneshot():  # Improves performance
                    # CPU Usage
                    cpu_percent = (
                        bedrock_process.cpu_percent(interval=1.0) / psutil.cpu_count()
                    )

                    # Memory Usage (RSS is usually appropriate)
                    memory_info = bedrock_process.memory_info()
                    memory_mb = memory_info.rss / (
                        1024 * 1024
                    )  # Resident Set Size in MB

                    # Uptime
                    create_time = bedrock_process.create_time()
                    uptime_seconds = time.time() - create_time
                    uptime_str = str(timedelta(seconds=int(uptime_seconds)))

                    logger.debug(
                        f"Process info for {server_name}: pid={bedrock_pid}, cpu={cpu_percent:.2f}%, mem={memory_mb:.2f}MB, uptime={uptime_str}"
                    )
                    return {
                        "pid": bedrock_pid,
                        "cpu_percent": cpu_percent,
                        "memory_mb": memory_mb,
                        "uptime": uptime_str,
                    }

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process might have terminated between finding PID and getting details
                logger.warning(
                    f"Process {bedrock_pid} for {server_name} disappeared or access denied before getting details."
                )
                return None  # Or empty dict
            except Exception as detail_err:
                logger.error(
                    f"Error getting details for process {bedrock_pid} ({server_name}): {detail_err}"
                )
                return None

        except Exception as e:
            # General error during process iteration or setup
            logger.error(f"Error during monitoring setup for {server_name}: {e}")
            # Raising prevents silent failure if the monitoring loop itself errors out
            raise ResourceMonitorError(
                f"Error during monitoring setup for {server_name}: {e}"
            ) from e
    else:
        logger.error("Unsupported OS for monitoring")
        return None


def remove_readonly(path):
    """Removes the read-only attribute from a file or directory (cross-platform).

    Args:
        path (str): The path to the file or directory.

    Raises:
        SetFolderPermissionsError: If removing read-only fails
        FileOperationError: If an unexpected file operation error occurs.

    """
    if not os.path.exists(path):
        logger.debug(f"Path does not exist, nothing to do: {path}")
        return  # Not an error if it doesn't exist

    logger.info(f"Ensuring write permissions for: {path}")

    if platform.system() == "Windows":
        try:
            # Avoid shell=True by constructing the full path to attrib.exe
            attrib_path = os.path.join(
                os.environ["SYSTEMROOT"], "System32", "attrib.exe"
            )
            subprocess.run(
                [attrib_path, "-R", path, "/S"],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.debug("Removed read-only attribute on Windows.")
        except subprocess.CalledProcessError as e:
            logger.error(
                f"Failed to remove read-only attribute on Windows: {e.stderr} {e.stdout}"
            )
            raise SetFolderPermissionsError(
                f"Failed to remove read-only attribute on Windows: {e.stderr} {e.stdout}"
            ) from e
        except FileNotFoundError:
            # If SYSTEMROOT is not set, this is a serious system issue.
            logger.error(
                "attrib command not found (SYSTEMROOT environment variable not set)."
            )
            raise FileOperationError(
                "attrib command not found (SYSTEMROOT environment variable not set)."
            ) from None
        except Exception as e:
            logger.error(f"Unexpected error using attrib command: {e}")
            raise FileOperationError(
                f"Unexpected error using attrib command: {e}"
            ) from e

    elif platform.system() == "Linux":
        try:
            if os.path.isfile(path):
                if "bedrock_server" in path:
                    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IWUSR)
                    logger.debug(f"Set execute and write permissions on file: {path}")
                else:
                    os.chmod(path, os.stat(path).st_mode | stat.S_IWUSR)
                    logger.debug(f"Set write permissions on file: {path}")
            elif os.path.isdir(path):
                os.chmod(path, os.stat(path).st_mode | stat.S_IWUSR | stat.S_IXUSR)
                logger.debug(f"Set write and execute permissions on directory: {path}")
                for root, dirs, files in os.walk(path):
                    for d in dirs:
                        dir_path = os.path.join(root, d)
                        os.chmod(
                            dir_path,
                            os.stat(dir_path).st_mode | stat.S_IWUSR | stat.S_IXUSR,
                        )
                        logger.debug(
                            f"Set write and execute permissions on directory: {dir_path}"
                        )
                    for f in files:
                        file_path = os.path.join(root, f)
                        if "bedrock_server" in file_path:
                            os.chmod(
                                file_path,
                                os.stat(file_path).st_mode
                                | stat.S_IWUSR
                                | stat.S_IXUSR,
                            )
                            logger.debug(
                                f"Set execute and write permissions on file: {file_path}"
                            )
                        else:
                            os.chmod(
                                file_path, os.stat(file_path).st_mode | stat.S_IWUSR
                            )
                            logger.debug(f"Set write permissions on file: {file_path}")
            else:
                logger.warning(f"Unsupported file type: {path}")
            logger.debug("Removed read-only attribute on Linux.")
        except OSError as e:
            logger.error(f"Failed to remove read-only attribute on Linux: {e}")
            raise SetFolderPermissionsError(
                f"Failed to remove read-only attribute on Linux: {e}"
            ) from e
    else:
        logger.warning(
            f"Unsupported operating system in remove_readonly: {platform.system()}"
        )
