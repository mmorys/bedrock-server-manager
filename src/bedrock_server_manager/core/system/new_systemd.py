# bedrock_server_manager/core/system/new_systemd.py
"""
Provides Linux-specific implementations for system interactions.

Includes functions for managing systemd user services (create, enable, disable, check)
and managing user cron jobs (list, add, modify, delete) for scheduling tasks related
to Bedrock servers. Relies on external commands like `systemctl`, `screen`, `pgrep`,
and `crontab`.
"""

import platform
import os
import logging
import subprocess
import shutil
from datetime import datetime
from typing import Optional

# Local imports
from bedrock_server_manager.error import (
    CommandNotFoundError,
    SystemdReloadError,
    ServiceError,
    MissingArgumentError,
    FileOperationError,
)

logger = logging.getLogger(__name__)


# --- Systemd Service Management ---


def get_systemd_user_service_file_path(service_name_full: str) -> str:
    """
    Generates the standard path for a given systemd user service file.
    Args:
        service_name_full: The full name of the service (e.g., "my-app.service" or "my-app" - .service will be appended if missing).
    """
    if not service_name_full:
        raise MissingArgumentError("Full service name cannot be empty.")

    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    return os.path.join(
        os.path.expanduser("~"), ".config", "systemd", "user", name_to_use
    )


def check_service_exists(service_name_full: str) -> bool:
    """Checks if a systemd user service file exists for the given full service name."""
    if platform.system() != "Linux":
        return False
    if not service_name_full:
        raise MissingArgumentError(
            "Full service name cannot be empty for service file check."
        )

    service_file_path = get_systemd_user_service_file_path(service_name_full)
    logger.debug(
        f"Checking for systemd user service file existence: '{service_file_path}'"
    )
    return os.path.isfile(service_file_path)


def create_systemd_service_file(
    service_name_full: str,
    description: str,
    working_directory: str,
    exec_start_command: str,
    exec_stop_command: Optional[str] = None,
    exec_start_pre_command: Optional[str] = None,
    service_type: str = "forking",  # Common types: simple, forking, oneshot
    restart_policy: str = "on-failure",
    restart_sec: int = 10,
    after_targets: str = "network.target",  # Comma-separated string if multiple
) -> None:
    """
    Creates or updates a generic systemd user service file.

    Args:
        service_name_full: The full name of the service (e.g., "my-app.service" or "my-app").
        description: Description for the service unit.
        working_directory: The WorkingDirectory for the service.
        exec_start_command: The command for ExecStart.
        exec_stop_command: Optional. The command for ExecStop.
        exec_start_pre_command: Optional. The command for ExecStartPre.
        service_type: Systemd service type (e.g., "simple", "forking").
        restart_policy: Systemd Restart policy (e.g., "no", "on-success", "on-failure").
        restart_sec: Seconds to wait before restarting.
        after_targets: Space-separated list of targets this service should start after.

    Raises:
        MissingArgumentError, ServiceError, CommandNotFoundError, SystemdReloadError, FileOperationError
    """
    if platform.system() != "Linux":
        logger.warning(
            f"Generic systemd service creation skipped: Not Linux. Service: '{service_name_full}'"
        )
        return

    if not all([service_name_full, description, working_directory, exec_start_command]):
        raise MissingArgumentError(
            "service_name_full, description, working_directory, and exec_start_command are required."
        )
    if not os.path.isdir(working_directory):  # Ensure working directory exists
        raise FileOperationError(
            f"WorkingDirectory '{working_directory}' does not exist or is not a directory."
        )

    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    systemd_user_dir = os.path.join(
        os.path.expanduser("~"), ".config", "systemd", "user"
    )
    service_file_path = os.path.join(systemd_user_dir, name_to_use)

    logger.info(
        f"Creating/Updating generic systemd user service file: '{service_file_path}'"
    )

    try:
        os.makedirs(systemd_user_dir, exist_ok=True)
    except OSError as e:
        raise ServiceError(
            f"Failed to create systemd user directory '{systemd_user_dir}': {e}"
        ) from e

    exec_start_pre_line = (
        f"ExecStartPre={exec_start_pre_command}" if exec_start_pre_command else ""
    )
    exec_stop_line = f"ExecStop={exec_stop_command}" if exec_stop_command else ""

    service_content = f"""[Unit]
Description={description}
After={after_targets}

[Service]
Type={service_type}
WorkingDirectory={working_directory}
{exec_start_pre_line}
ExecStart={exec_start_command}
{exec_stop_line}
Restart={restart_policy}
RestartSec={restart_sec}s

[Install]
WantedBy=default.target
"""
    # Remove empty lines from service_content that might occur if optional commands are not provided
    service_content = "\n".join(
        [line for line in service_content.splitlines() if line.strip()]
    )

    try:
        with open(service_file_path, "w", encoding="utf-8") as f:
            f.write(service_content)
        logger.info(
            f"Successfully wrote generic systemd service file: {service_file_path}"
        )
    except OSError as e:
        raise ServiceError(
            f"Failed to write service file '{service_file_path}': {e}"
        ) from e

    # Reload systemd daemon
    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        raise CommandNotFoundError("systemctl")
    try:
        subprocess.run(
            [systemctl_cmd, "--user", "daemon-reload"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(
            f"Systemd user daemon reloaded successfully for service '{name_to_use}'."
        )
    except subprocess.CalledProcessError as e:
        raise SystemdReloadError(
            f"Failed to reload systemd user daemon. Error: {e.stderr}"
        ) from e


def enable_systemd_service(service_name_full: str) -> None:
    """Enables a generic systemd user service to start on login."""
    if platform.system() != "Linux":
        return
    if not service_name_full:
        raise MissingArgumentError("Full service name cannot be empty.")
    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    logger.info(f"Enabling systemd user service '{name_to_use}'...")

    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        raise CommandNotFoundError("systemctl")

    if not check_service_exists(name_to_use):  # Check with .service suffix
        raise ServiceError(
            f"Cannot enable: Systemd service file for '{name_to_use}' does not exist."
        )

    try:
        # `is-enabled` returns 0 if enabled, non-zero otherwise (including not found, masked, static)
        process = subprocess.run(
            [systemctl_cmd, "--user", "is-enabled", name_to_use],
            capture_output=True,
            text=True,
            check=False,  # Don't check, just examine return code/output
        )
        status_output = process.stdout.strip()
        logger.debug(
            f"'systemctl is-enabled {name_to_use}' status: {status_output}, return code: {process.returncode}"
        )
        if status_output == "enabled":
            logger.info(f"Service '{name_to_use}' is already enabled.")
            return  # Already enabled
    except FileNotFoundError:  # Should be caught by shutil.which, but safeguard
        logger.error("'systemctl' command not found unexpectedly.")
        raise CommandNotFoundError("systemctl") from None
    except Exception as e:
        logger.warning(
            f"Could not reliably determine if service '{name_to_use}' is enabled: {e}. Attempting enable anyway.",
            exc_info=True,
        )

    try:
        subprocess.run(
            [systemctl_cmd, "--user", "enable", name_to_use],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Systemd service '{name_to_use}' enabled successfully.")
    except subprocess.CalledProcessError as e:
        raise ServiceError(
            f"Failed to enable systemd service '{name_to_use}'. Error: {e.stderr}"
        ) from e


def disable_systemd_service(service_name_full: str) -> None:
    """Disables a generic systemd user service from starting on login."""
    if platform.system() != "Linux":
        return
    if not service_name_full:
        raise MissingArgumentError("Full service name cannot be empty.")
    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    logger.info(f"Disabling systemd user service '{name_to_use}'...")

    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        raise CommandNotFoundError("systemctl")

    if not check_service_exists(name_to_use):
        logger.debug(
            f"Service file for '{name_to_use}' does not exist. Assuming already disabled/removed."
        )
        return

    try:
        process = subprocess.run(
            [systemctl_cmd, "--user", "is-enabled", name_to_use],
            capture_output=True,
            text=True,
            check=False,
        )
        status_output = process.stdout.strip()
        logger.debug(
            f"'systemctl is-enabled {name_to_use}' status: {status_output}, return code: {process.returncode}"
        )
        # is-enabled returns non-zero for disabled, static, masked, not-found
        if status_output != "enabled":  # Check if it's *not* enabled
            logger.info(
                f"Service '{name_to_use}' is already disabled or not in an enabled state."
            )
            return  # Already disabled or in a state where disable won't work/isn't needed
    except FileNotFoundError:  # Safeguard
        logger.error("'systemctl' command not found unexpectedly.")
        raise CommandNotFoundError("systemctl") from None
    except Exception as e:
        logger.warning(
            f"Could not reliably determine if service '{name_to_use}' is enabled: {e}. Attempting disable anyway.",
            exc_info=True,
        )

    try:
        subprocess.run(
            [systemctl_cmd, "--user", "disable", name_to_use],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Systemd service '{name_to_use}' disabled successfully.")
    except subprocess.CalledProcessError as e:
        if "static" in (e.stderr or "").lower() or "masked" in (e.stderr or "").lower():
            logger.info(
                f"Service '{name_to_use}' is static or masked, cannot be disabled via 'disable'."
            )
            return
        raise ServiceError(
            f"Failed to disable systemd service '{name_to_use}'. Error: {e.stderr}"
        ) from e
