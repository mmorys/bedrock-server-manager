# bedrock-server-manager/bedrock_server_manager/core/server/server_actions.py
"""
Core module for managing Bedrock server instances.
"""

import subprocess
import os
import logging
import time
import json
import platform
import shutil
from typing import Optional, Any, Dict

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    ServerStartError,
    ServerStopError,
    ServerNotRunningError,
    SendCommandError,
    ServerNotFoundError,
    InvalidServerNameError,
    MissingArgumentError,
    FileOperationError,
    InvalidInputError,
    DirectoryError,
    CommandNotFoundError,
)
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.core.server.server_utils import (
    _get_server_details,
    check_if_server_is_running,
    manage_server_config,
)

if platform.system() == "Linux":
    from bedrock_server_manager.core.system import linux as system_linux

    system_windows = None
elif platform.system() == "Windows":
    from bedrock_server_manager.core.system import windows as system_windows

    system_linux = None
else:
    system_linux = None
    system_windows = None


logger = logging.getLogger("bedrock_server_manager")


def start_server(server_name: str, server_path_override: Optional[str] = None) -> None:
    """
    Starts the Bedrock server process.
    Uses systemd on Linux (if available, falling back to screen) or starts
    directly on Windows. Manages persistent status and waits for confirmation.

    Args:
        server_name: The name of the server.
        server_path_override: Optional. The full path to the server executable.

    Raises:
        ServerStartError: If the server is already running, if the OS is unsupported,
                          or if the server fails to start within the timeout.
        CommandNotFoundError: If required external commands (systemctl, screen) are missing.
        ServerNotFoundError: If the server executable cannot be found.
        MissingArgumentError: If server_name is empty.
        FileOperationError: If essential settings (BASE_DIR, _config_dir) are missing.
    """
    details = _get_server_details(server_name, server_path_override)
    # server_name is details["server_name"]
    # server_dir = details["server_dir"]
    # server_config_dir = details["server_config_dir"]
    # config_dir_base = details["config_dir_base"] (used for manage_server_config)

    if check_if_server_is_running(server_name):
        logger.warning(
            f"Attempted to start server '{server_name}' but it is already running."
        )
        raise ServerStartError(f"Server '{server_name}' is already running.")

    manage_server_config(
        server_name,
        "status",
        "write",
        "STARTING",
        config_dir=details["config_dir_base"],
    )
    logger.info(f"Attempting to start server '{server_name}'...")

    os_name = platform.system()
    start_successful_method = None

    if os_name == "Linux":
        screen_cmd_path = shutil.which("screen")
        if screen_cmd_path:
            logger.info("Starting server.")
            try:
                system_linux._linux_start_server(server_name, details["server_dir"])
                start_successful_method = "screen"
            except (CommandNotFoundError, ServerStartError) as e:
                logger.error(
                    f"Failed to start server using screen method: {e}",
                    exc_info=True,
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error starting server via screen method: {e}",
                    exc_info=True,
                )
        else:
            logger.error("'screen' command not found. Cannot start server.")
            manage_server_config(
                server_name,
                "status",
                "write",
                "ERROR",
                config_dir=details["config_dir_base"],
            )
            raise CommandNotFoundError(
                "screen", message="'screen' command not found. Cannot start server."
            )
            attempts = 0
            max_attempts = settings.get("SERVER_START_TIMEOUT_SEC", 60) // 2
            sleep_interval = 2

            logger.info(
                f"Waiting up to {max_attempts * sleep_interval} seconds for server '{server_name}' to start..."
            )
            while attempts < max_attempts:
                if check_if_server_is_running(server_name):
                    manage_server_config(
                        server_name,
                        "status",
                        "write",
                        "RUNNING",
                        config_dir=details["config_dir_base"],
                    )
                    logger.info(f"Server '{server_name}' started successfully.")
                    return
                logger.debug(
                    f"Waiting for server '{server_name}' to start... (Check {attempts + 1}/{max_attempts})"
                )
                time.sleep(sleep_interval)
                attempts += 1

            manage_server_config(
                server_name,
                "status",
                "write",
                "ERROR",
                config_dir=details["config_dir_base"],
            )
            logger.error(
                f"Server '{server_name}' failed to confirm running status within the timeout ({max_attempts * sleep_interval} seconds)."
            )
            raise ServerStartError(
                f"Server '{server_name}' failed to start within the timeout."
            )

    elif os_name == "Windows":
        logger.debug("Attempting to start server via Windows process creation.")

        try:
            manage_server_config(
                server_name,
                "status",
                "write",
                "RUNNING",
                config_dir=details["config_dir_base"],
            )
            _ = system_windows._windows_start_server(  # Popen object not stored/used further here
                server_name, details["server_dir"], details["server_config_dir"]
            )
            start_successful_method = "windows_process"
            logger.info(f"Exited named pipe cleaninly on Windows for '{server_name}'.")

            manage_server_config(
                server_name,
                "status",
                "write",
                "STOPPED",
                config_dir=details["config_dir_base"],
            )
        except ServerStartError as e:
            logger.error(
                f"Failed to start server process on Windows: {e}", exc_info=True
            )
        except Exception as e:
            logger.error(
                f"Unexpected error starting server process on Windows: {e}",
                exc_info=True,
            )

    else:
        logger.error(
            f"Starting server is not supported on this operating system: {os_name}"
        )
        manage_server_config(
            server_name,
            "status",
            "write",
            "ERROR",
            config_dir=details["config_dir_base"],
        )
        raise ServerStartError(f"Unsupported operating system: {os_name}")


def stop_server(server_name: str, server_path_override: Optional[str] = None) -> None:
    """
    Stops the Bedrock server process gracefully.
    Sends a 'stop' command, waits for the process to terminate.

    Args:
        server_name: The name of the server.
        server_path_override: Optional. The full path to the server executable.

    Raises:
        ServerStopError: If the server is not running (when expected), OS unsupported,
                         or fails to stop within timeout.
        SendCommandError: If sending the initial 'stop' command fails.
        CommandNotFoundError: If required external commands are missing.
        ServerNotFoundError: If the server executable cannot be found (for checks).
        MissingArgumentError: If server_name is empty.
        FileOperationError: If essential settings (BASE_DIR, _config_dir) are missing.
    """
    details = _get_server_details(server_name, server_path_override)
    # server_name = details["server_name"]
    # server_dir = details["server_dir"] (used by system_windows._windows_stop_server)
    # server_config_dir = details["server_config_dir"] (used by system_windows._windows_stop_server)
    # config_dir_base = details["config_dir_base"] (used for manage_server_config)

    if not check_if_server_is_running(server_name):
        logger.info(
            f"Attempted to stop server '{server_name}', but it is not currently running."
        )
        if (
            manage_server_config(
                server_name, "status", "read", config_dir=details["config_dir_base"]
            )
            != "STOPPED"
        ):
            manage_server_config(
                server_name,
                "status",
                "write",
                "STOPPED",
                config_dir=details["config_dir_base"],
            )
        return

    manage_server_config(
        server_name,
        "status",
        "write",
        "STOPPING",
        config_dir=details["config_dir_base"],
    )
    logger.info(f"Attempting to stop server '{server_name}'...")

    os_name = platform.system()
    stop_initiated_by_systemd = False  # Specific to systemd stop path

    send_server_command(server_name, "stop")

    attempts = 0
    max_attempts = settings.get("SERVER_STOP_TIMEOUT_SEC", 60) // 2
    sleep_interval = 2
    logger.info(
        f"Waiting up to {max_attempts * sleep_interval} seconds for server '{server_name}' process to terminate..."
    )

    while attempts < max_attempts:
        if not check_if_server_is_running(server_name):
            manage_server_config(
                server_name,
                "status",
                "write",
                "STOPPED",
                config_dir=details["config_dir_base"],
            )
            logger.info(f"Server '{server_name}' stopped successfully.")
            if os_name == "Linux" and not stop_initiated_by_systemd:
                screen_session_name = f"bedrock-{server_name}"
                try:
                    subprocess.run(
                        ["screen", "-S", screen_session_name, "-X", "quit"],
                        check=False,
                        capture_output=True,
                    )
                    logger.debug(
                        f"Attempted to quit potentially lingering screen session '{screen_session_name}'."
                    )
                except FileNotFoundError:
                    pass
            return

        logger.debug(
            f"Waiting for server '{server_name}' to stop... (Check {attempts + 1}/{max_attempts})"
        )
        time.sleep(sleep_interval)
        attempts += 1

    logger.error(
        f"Server '{server_name}' failed to stop within the timeout ({max_attempts * sleep_interval} seconds). Process might still be running."
    )
    manage_server_config(
        server_name, "status", "write", "ERROR", config_dir=details["config_dir_base"]
    )
    raise ServerStopError(
        f"Server '{server_name}' failed to stop within the timeout. Manual intervention may be required."
    )


def send_server_command(server_name: str, command: str) -> None:
    """
    Sends a command string to the running server process.
    Implementation is platform-specific (screen on Linux, named pipes on Windows).

    Args:
        server_name: The name of the server.
        command: The command string to send to the server console.

    Raises:
        MissingArgumentError: If `server_name` or `command` is empty.
        ServerNotRunningError: If the server process cannot be found or communicated with.
        SendCommandError: If there's a platform-specific error sending the command.
        CommandNotFoundError: If a required external command (like 'screen') is not found.
        NotImplementedError: If the current OS is not supported.
        FileOperationError: If BASE_DIR setting is missing.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty for send_command.")
    if not command:
        raise MissingArgumentError("Command cannot be empty.")

    if not check_if_server_is_running(server_name):
        logger.error(
            f"Cannot send command to server '{server_name}': Server is not running."
        )
        raise ServerNotRunningError(f"Server '{server_name}' is not running.")

    logger.info(f"Sending command '{command}' to server '{server_name}'...")

    os_name = platform.system()
    if os_name == "Linux":

        system_linux._linux_send_command(server_name, command)

    elif os_name == "Windows":
        system_windows._windows_send_command(server_name, command)
    else:
        logger.error(
            f"Sending commands is not supported on this operating system: {os_name}"
        )
        raise NotImplementedError(f"Sending commands not supported on {os_name}")


def delete_server_data(
    server_name: str, base_dir: str, config_dir: Optional[str] = None
) -> None:
    """
    Deletes all data associated with a Bedrock server, including its installation
    directory, configuration folder, and systemd service file (on Linux).

    Args:
        server_name: The name of the server to delete.
        base_dir: The base directory containing server installations.
        config_dir: Optional. The base directory for server configs. Defaults if None.

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        DirectoryError: If deleting the server data or config directories fails.
        FileOperationError: If settings (BACKUP_DIR, _config_dir) are missing.
    """
    if not server_name:
        # Assuming InvalidServerNameError is defined
        raise Exception(
            "Server name cannot be empty."
        )  # Replace with InvalidServerNameError
    if not base_dir:
        # Assuming MissingArgumentError is defined
        raise Exception(
            "Base directory cannot be empty."
        )  # Replace with MissingArgumentError

    effective_config_dir = (
        config_dir if config_dir is not None else getattr(settings, "_config_dir", None)
    )
    if not effective_config_dir:
        # Assuming FileOperationError is defined
        raise Exception(  # Replace with FileOperationError
            "Base configuration directory is not set or available."
        )

    server_install_dir = os.path.join(base_dir, server_name)
    server_config_subdir = os.path.join(effective_config_dir, server_name)
    backup_base_dir = settings.get("BACKUP_DIR")
    server_backup_dir = (
        os.path.join(backup_base_dir, server_name) if backup_base_dir else None
    )

    logger.warning(f"!!! Preparing to delete all data for server '{server_name}' !!!")
    logger.debug(f"Target installation directory: {server_install_dir}")
    logger.debug(f"Target configuration directory: {server_config_subdir}")
    if server_backup_dir:
        logger.debug(f"Target backup directory: {server_backup_dir}")

    # --- Pre-checks and Stop Server ---
    # Check if any primary data exists before trying to stop (to avoid error if server is already mostly gone)
    primary_data_exists = (
        os.path.exists(server_install_dir)
        or os.path.exists(server_config_subdir)
        or (server_backup_dir and os.path.exists(server_backup_dir))
    )

    if not primary_data_exists:
        # Also check systemd file on Linux, as it might be the only remnant
        systemd_file_might_exist = False
        if platform.system() == "Linux":
            service_name_check = f"bedrock-{server_name}"
            service_file_path_check = os.path.join(
                os.path.expanduser("~/.config/systemd/user/"),
                f"{service_name_check}.service",
            )
            if os.path.exists(service_file_path_check):
                systemd_file_might_exist = True

        if not systemd_file_might_exist:
            logger.warning(
                f"Server '{server_name}' data not found (no install, config, backup, or systemd file found). Skipping deletion."
            )
            return

    deletion_errors = []

    # --- Remove systemd service (Linux) ---
    if platform.system() == "Linux":
        service_name = f"bedrock-{server_name}"
        service_file_path = os.path.join(
            os.path.expanduser("~/.config/systemd/user/"), f"{service_name}.service"
        )
        systemctl_cmd_path = shutil.which("systemctl")

        if os.path.exists(service_file_path):  # Only proceed if file exists
            if systemctl_cmd_path:
                logger.info(
                    f"Disabling and preparing to remove systemd user service '{service_name}'..."
                )
                try:
                    # Disable first (stops it if running, prevents auto-start)
                    subprocess.run(
                        [
                            systemctl_cmd_path,
                            "--user",
                            "disable",
                            "--now",
                            service_name,
                        ],
                        check=False,  # Don't raise error if already disabled/not found by systemctl
                        capture_output=True,
                    )
                    logger.debug(
                        f"Attempted disable --now for service '{service_name}'."
                    )

                    # Remove the service file using the new robust deleter
                    if not system_base.delete_path_robustly(
                        service_file_path,
                        f"systemd service file for '{service_name}'",
                        logger,
                    ):
                        # Logged by delete_path_robustly, add to errors if critical
                        deletion_errors.append(
                            f"systemd service file '{service_file_path}'"
                        )
                        logger.warning(
                            f"Failed to remove systemd service file '{service_file_path}'. Manual cleanup might be needed."
                        )
                    else:
                        logger.debug(f"Removed service file: {service_file_path}")

                    # Reload systemd daemon
                    subprocess.run(
                        [systemctl_cmd_path, "--user", "daemon-reload"],
                        check=False,
                        capture_output=True,
                    )
                    subprocess.run(
                        [systemctl_cmd_path, "--user", "reset-failed"],
                        check=False,
                        capture_output=True,
                    )
                    logger.info(
                        f"Systemd service '{service_name}' processing complete and daemon reloaded."
                    )
                except Exception as e:  # Catch subprocess errors or others
                    logger.warning(
                        f"Failed during systemd service interaction for '{service_name}': {e}. Manual cleanup might be needed.",
                        exc_info=True,
                    )
            else:  # systemctl not found, but service file exists
                logger.warning(
                    f"Systemd service file found for '{service_name}', but 'systemctl' command not found. Attempting to delete file directly."
                )
                if not system_base.delete_path_robustly(
                    service_file_path,
                    f"systemd service file for '{service_name}' (no systemctl)",
                ):
                    deletion_errors.append(
                        f"systemd service file '{service_file_path}' (no systemctl)"
                    )
                    logger.warning(
                        f"Failed to remove systemd service file '{service_file_path}' without systemctl. Manual cleanup needed."
                    )

    # --- Remove directories ---
    paths_to_delete_map = {
        "backup": server_backup_dir,  # Delete backups first, often largest
        "installation": server_install_dir,
        "configuration": server_config_subdir,
    }

    for dir_type, dir_path in paths_to_delete_map.items():
        if dir_path:  # Ensure path is not None (e.g. if backup_base_dir was None)
            if not system_base.delete_path_robustly(dir_path, f"server {dir_type}"):
                deletion_errors.append(f"{dir_type} directory '{dir_path}'")
        else:
            logger.debug(f"Server {dir_type} path is not defined, skipping.")

    # Report final status
    if deletion_errors:
        error_summary = "; ".join(deletion_errors)
        logger.error(
            f"Deletion process for server '{server_name}' completed with errors. Failed to delete: {error_summary}"
        )
        raise Exception(  # Replace with DirectoryError
            f"Failed to completely delete server '{server_name}'. Failed items: {error_summary}"
        )
    else:
        logger.info(f"Successfully deleted all data for server: '{server_name}'.")
