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
from bedrock_server_manager.core.error import (
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
        raise InternetConnectivityError(f"Connectivity test failed: {ex}") from ex
    except Exception as e:
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
                for f in files:
                    file_path = os.path.join(root, f)
                    os.chown(file_path, real_user, real_group)
                    if os.path.basename(file_path) == "bedrock_server":
                        os.chmod(file_path, 0o755)
                    else:
                        os.chmod(file_path, 0o664)
            logger.info("Folder permissions set.")
        except OSError as e:
            raise SetFolderPermissionsError(
                f"Failed to set server folder permissions: {e}"
            ) from e

    elif platform.system() == "Windows":
        logger.info("Setting folder permissions for Windows...")
        try:
            for root, dirs, files in os.walk(server_dir):
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    current_permissions = os.stat(dir_path).st_mode
                    if not (current_permissions & stat.S_IWRITE):
                        os.chmod(dir_path, current_permissions | stat.S_IWRITE)
                for f in files:
                    file_path = os.path.join(root, f)
                    current_permissions = os.stat(file_path).st_mode
                    if not (current_permissions & stat.S_IWRITE):
                        os.chmod(file_path, current_permissions | stat.S_IWRITE)
            logger.info("Folder permissions set for Windows (ensured write access).")
        except OSError as e:
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
    if platform.system() == "Linux":
        try:
            result = subprocess.run(
                ["screen", "-ls"],
                capture_output=True,
                text=True,
                check=False,
            )
            return f".bedrock-{server_name}" in result.stdout
        except FileNotFoundError:
            raise CommandNotFoundError(
                "screen", message="screen command not found."
            ) from None

    elif platform.system() == "Windows":
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
                try:
                    if (
                        proc.info["name"] == "bedrock_server.exe"
                        and proc.info["cwd"]
                        and base_dir.lower() in proc.info["cwd"].lower()
                    ):
                        return True
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    pass
            return False
        except Exception as e:
            logger.error(f"Error checking process: {e}")
            return False

    else:
        logger.error("Unsupported operating system for running check.")
        return False


def _get_bedrock_process_info(server_name, base_dir):
    """Gets resource usage information for the running Bedrock server.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers

    Returns:
        dict or None: A dictionary containing process information, or None
                      if the server is not running or an error occurs.  The
                      dictionary has the following keys:
                        - pid (int): The process ID.
                        - cpu_percent (float): The CPU usage percentage.
                        - memory_mb (float): The memory usage in megabytes.
                        - uptime (str): The server uptime as a string.
                      If any of these cannot be retrieved, they will be None.
    Raises:
        ResourceMonitorError: If there is any error during monitoring.
    """
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
                    pass

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
                with bedrock_process.oneshot():  # Improves performance
                    # CPU Usage: Real-time calculation
                    cpu_percent = (
                        bedrock_process.cpu_percent(interval=1.0) / psutil.cpu_count()
                    )  # per core usage

                    # Memory Usage
                    memory_mb = bedrock_process.memory_info().rss / (
                        1024 * 1024
                    )  # Convert to MB

                    # Uptime
                    uptime_seconds = time.time() - bedrock_process.create_time()
                    uptime_str = str(timedelta(seconds=int(uptime_seconds)))

                    return {
                        "pid": bedrock_pid,
                        "cpu_percent": cpu_percent,
                        "memory_mb": memory_mb,
                        "uptime": uptime_str,
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                return None

        except Exception as e:
            raise ResourceMonitorError(f"Error during monitoring: {e}") from e

    elif platform.system() == "Windows":
        # Find the Bedrock server process
        bedrock_pid = None
        try:
            for proc in psutil.process_iter(["pid", "name", "cwd"]):
                try:
                    if (
                        proc.info["name"] == "bedrock_server.exe"
                        and proc.info["cwd"]
                        and os.path.join(base_dir, server_name).lower()
                        == proc.info["cwd"].lower()
                    ):
                        bedrock_pid = proc.info["pid"]
                        break  # Exit loop once found
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    pass
            if not bedrock_pid:
                logger.warning(
                    f"No running Bedrock server process found for {server_name}."
                )
                return None

            # Get process details
            try:
                bedrock_process = psutil.Process(bedrock_pid)
                with (
                    bedrock_process.oneshot()
                ):  # Improves performance for multiple reads.
                    # CPU Usage
                    cpu_percent = (
                        bedrock_process.cpu_percent(interval=1.0) / psutil.cpu_count()
                    )

                    # Memory Usage
                    memory_mb = bedrock_process.memory_info().rss / (
                        1024 * 1024
                    )  # Convert to MB

                    # Uptime
                    uptime_seconds = time.time() - bedrock_process.create_time()
                    uptime_str = str(timedelta(seconds=int(uptime_seconds)))

                    return {
                        "pid": bedrock_pid,
                        "cpu_percent": cpu_percent,
                        "memory_mb": memory_mb,
                        "uptime": uptime_str,
                    }

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                return None
        except Exception as e:
            raise ResourceMonitorError(f"Error during monitoring: {e}") from e
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

    logger.debug(f"Ensuring write permissions for: {path}")

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
            raise SetFolderPermissionsError(
                f"Failed to remove read-only attribute on Windows: {e.stderr} {e.stdout}"
            ) from e
        except FileNotFoundError:
            # If SYSTEMROOT is not set, this is a serious system issue.
            raise FileOperationError(
                "attrib command not found (SYSTEMROOT environment variable not set)."
            ) from None
        except Exception as e:
            raise FileOperationError(
                f"Unexpected error using attrib command: {e}"
            ) from e

    elif platform.system() == "Linux":
        try:
            if os.path.isfile(path):
                if "bedrock_server" in path:
                    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IWUSR)
                else:
                    os.chmod(path, os.stat(path).st_mode | stat.S_IWUSR)
            elif os.path.isdir(path):
                os.chmod(path, os.stat(path).st_mode | stat.S_IWUSR | stat.S_IXUSR)
                for root, dirs, files in os.walk(path):
                    for d in dirs:
                        dir_path = os.path.join(root, d)
                        os.chmod(
                            dir_path,
                            os.stat(dir_path).st_mode | stat.S_IWUSR | stat.S_IXUSR,
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
                        else:
                            os.chmod(
                                file_path, os.stat(file_path).st_mode | stat.S_IWUSR
                            )
            else:
                logger.warning(f"Unsupported file type: {path}")
            logger.debug("Removed read-only attribute on Linux.")
        except OSError as e:
            raise SetFolderPermissionsError(
                f"Failed to remove read-only attribute on Linux: {e}"
            ) from e
    else:
        logger.warning(
            f"Unsupported operating system in remove_readonly: {platform.system()}"
        )
