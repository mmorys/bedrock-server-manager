# bedrock-server-manager/bedrock_server_manager/core/system/linux.py
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
from typing import List, Optional, Tuple, Dict

# Local imports
from bedrock_server_manager.config.settings import EXPATH
from bedrock_server_manager.error import (
    CommandNotFoundError,
    SystemdReloadError,
    ServiceError,
    InvalidServerNameError,
    ScheduleError,
    InvalidCronJobError,
    ServerStartError,
    ServerStopError,
    MissingArgumentError,
    FileOperationError,
    DirectoryError,
)

logger = logging.getLogger("bedrock_server_manager")


# --- Systemd Service Management ---


def check_service_exist(server_name: str) -> bool:
    """
    Checks if a systemd user service file exists for the given server name.

    Args:
        server_name: The name of the server (used to construct service name `bedrock-{server_name}`).

    Returns:
        True if the corresponding systemd user service file exists, False otherwise
        (including if not on Linux).

    Raises:
        MissingArgumentError: If `server_name` is empty.
    """
    if platform.system() != "Linux":
        logger.debug("Systemd check skipped: Not running on Linux.")
        return False
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty for service check.")

    service_name = f"bedrock-{server_name}"
    # Standard path for user systemd services
    service_file_path = os.path.join(
        os.path.expanduser("~"), ".config", "systemd", "user", f"{service_name}.service"
    )
    logger.debug(
        f"Checking for systemd user service file existence: '{service_file_path}'"
    )
    exists = os.path.isfile(service_file_path)  # Check if it's specifically a file
    logger.debug(f"Service file exists: {exists}")
    return exists


def _create_systemd_service(server_name: str, base_dir: str, autoupdate: bool) -> None:
    """
    Creates or updates a systemd user service file for managing a Bedrock server.

    (Linux-specific)

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server's installation folder.
        autoupdate: If True, adds an `ExecStartPre` command to update the server
                    before starting.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        MissingArgumentError: If `base_dir` is empty.
        ServiceError: If creating the systemd directory or writing the service file fails.
        CommandNotFoundError: If the 'systemctl' command is not found.
        SystemdReloadError: If `systemctl --user daemon-reload` fails.
        FileOperationError: If EXPATH is not set or invalid.
    """
    if platform.system() != "Linux":
        logger.warning("Systemd service creation skipped: Not running on Linux.")
        return

    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")
    if not EXPATH or not os.path.isfile(EXPATH):
        raise FileOperationError(
            f"Main script executable path (EXPATH) is invalid or not set: {EXPATH}"
        )

    server_dir = os.path.join(base_dir, server_name)
    service_name = f"bedrock-{server_name}"
    systemd_user_dir = os.path.join(
        os.path.expanduser("~"), ".config", "systemd", "user"
    )
    service_file_path = os.path.join(systemd_user_dir, f"{service_name}.service")

    logger.info(f"Creating/Updating systemd user service file: '{service_file_path}'")

    # Ensure the systemd user directory exists
    try:
        os.makedirs(systemd_user_dir, exist_ok=True)
        logger.debug(f"Ensured systemd user directory exists: {systemd_user_dir}")
    except OSError as e:
        logger.error(
            f"Failed to create systemd user directory '{systemd_user_dir}': {e}",
            exc_info=True,
        )
        raise ServiceError(
            f"Failed to create systemd directory '{systemd_user_dir}': {e}"
        ) from e

    # Prepare service file content
    autoupdate_line = ""
    if autoupdate:
        # Ensure server_name is quoted if it contains spaces
        autoupdate_line = (
            f'ExecStartPre={EXPATH} update-server --server "{server_name}"'
        )
        logger.debug(f"Autoupdate enabled for service '{service_name}'.")
    else:
        logger.debug(f"Autoupdate disabled for service '{service_name}'.")

    # Using Type=forking assumes the systemd-start script detaches correctly (e.g., via screen -dm)
    # Consider Type=simple or Type=exec if the script runs the server in the foreground.
    service_content = f"""[Unit]
Description=Minecraft Bedrock Server: {server_name}
# Ensure it starts after network is up, adjust if other dependencies exist
After=network.target

[Service]
# Type=forking requires the ExecStart process to exit after setup, while the main service continues.
# If systemd-start runs 'screen -dmS', this is appropriate.
# If systemd-start runs the server directly in the foreground, use Type=simple or Type=exec.
Type=forking
WorkingDirectory={server_dir}
# Define required environment variables if necessary
# Environment="LD_LIBRARY_PATH=."
{autoupdate_line}
# Use absolute path to EXPATH
ExecStart={EXPATH} systemd-start --server "{server_name}"
ExecStop={EXPATH} systemd-stop --server "{server_name}"
# ExecReload might not be necessary if stop/start works reliably
# ExecReload={EXPATH} systemd-stop --server "{server_name}" && {EXPATH} systemd-start --server "{server_name}"
# Restart behavior
Restart=on-failure
RestartSec=10s
# Limit restarts to prevent rapid looping on persistent failure
StartLimitIntervalSec=300s
StartLimitBurst=5

[Install]
WantedBy=default.target
"""

    # Write the service file
    try:
        with open(service_file_path, "w", encoding="utf-8") as f:
            f.write(service_content)
        logger.info(f"Successfully wrote systemd service file: {service_file_path}")
    except OSError as e:
        logger.error(
            f"Failed to write systemd service file '{service_file_path}': {e}",
            exc_info=True,
        )
        raise ServiceError(
            f"Failed to write service file '{service_file_path}': {e}"
        ) from e

    # Reload systemd daemon to recognize the new/changed file
    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        logger.error("'systemctl' command not found. Cannot reload systemd daemon.")
        raise CommandNotFoundError("systemctl")

    logger.debug("Reloading systemd user daemon...")
    try:
        process = subprocess.run(
            [systemctl_cmd, "--user", "daemon-reload"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Systemd user daemon reloaded successfully.")
        logger.debug(f"systemctl output: {process.stdout}{process.stderr}")
    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to reload systemd user daemon. Error: {e.stderr}"
        logger.error(error_msg, exc_info=True)
        raise SystemdReloadError(error_msg) from e
    except FileNotFoundError:  # Should be caught by shutil.which, but safeguard
        logger.error("'systemctl' command not found unexpectedly.")
        raise CommandNotFoundError("systemctl") from None


def _enable_systemd_service(server_name: str) -> None:
    """
    Enables a systemd user service to start on login.

    (Linux-specific)

    Args:
        server_name: The name of the server.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        ServiceError: If the service file does not exist or enabling fails.
        CommandNotFoundError: If the 'systemctl' command is not found.
    """
    if platform.system() != "Linux":
        logger.warning("Systemd service enabling skipped: Not running on Linux.")
        return
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    service_name = f"bedrock-{server_name}"
    logger.info(
        f"Enabling systemd user service '{service_name}' for autostart on login..."
    )

    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        logger.error("'systemctl' command not found. Cannot enable service.")
        raise CommandNotFoundError("systemctl")

    # Check if service file exists before attempting to enable
    if not check_service_exist(server_name):
        error_msg = f"Cannot enable service: Systemd service file for '{service_name}' does not exist."
        logger.error(error_msg)
        raise ServiceError(error_msg)

    # Check if already enabled
    try:
        # `is-enabled` returns 0 if enabled, non-zero otherwise (including not found, masked, static)
        process = subprocess.run(
            [systemctl_cmd, "--user", "is-enabled", service_name],
            capture_output=True,
            text=True,
            check=False,  # Don't check, just examine return code/output
        )
        status_output = process.stdout.strip()
        logger.debug(
            f"'systemctl is-enabled {service_name}' status: {status_output}, return code: {process.returncode}"
        )
        if status_output == "enabled":
            logger.info(f"Service '{service_name}' is already enabled.")
            return  # Already enabled
    except FileNotFoundError:  # Should be caught by shutil.which, but safeguard
        logger.error("'systemctl' command not found unexpectedly.")
        raise CommandNotFoundError("systemctl") from None
    except Exception as e:
        logger.warning(
            f"Could not reliably determine if service '{service_name}' is enabled: {e}. Attempting enable anyway.",
            exc_info=True,
        )

    # Attempt to enable the service
    try:
        process = subprocess.run(
            [systemctl_cmd, "--user", "enable", service_name],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Systemd service '{service_name}' enabled successfully.")
        logger.debug(f"systemctl output: {process.stdout}{process.stderr}")
    except subprocess.CalledProcessError as e:
        error_msg = (
            f"Failed to enable systemd service '{service_name}'. Error: {e.stderr}"
        )
        logger.error(error_msg, exc_info=True)
        raise ServiceError(error_msg) from e


def _disable_systemd_service(server_name: str) -> None:
    """
    Disables a systemd user service from starting on login.

    (Linux-specific)

    Args:
        server_name: The name of the server.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        ServiceError: If disabling the service fails.
        CommandNotFoundError: If the 'systemctl' command is not found.
    """
    if platform.system() != "Linux":
        logger.warning("Systemd service disabling skipped: Not running on Linux.")
        return
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    service_name = f"bedrock-{server_name}"
    logger.info(f"Disabling systemd user service '{service_name}'...")

    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        logger.error("'systemctl' command not found. Cannot disable service.")
        raise CommandNotFoundError("systemctl")

    # Check if service file exists first. If not, nothing to disable.
    if not check_service_exist(server_name):
        logger.debug(
            f"Service file for '{service_name}' does not exist. Assuming already disabled or removed."
        )
        return

    # Check if already disabled
    try:
        process = subprocess.run(
            [systemctl_cmd, "--user", "is-enabled", service_name],
            capture_output=True,
            text=True,
            check=False,
        )
        status_output = process.stdout.strip()
        logger.debug(
            f"'systemctl is-enabled {service_name}' status: {status_output}, return code: {process.returncode}"
        )
        # is-enabled returns non-zero for disabled, static, masked, not-found
        if status_output != "enabled":  # Check if it's *not* enabled
            logger.info(
                f"Service '{service_name}' is already disabled or not in an enabled state."
            )
            return  # Already disabled or in a state where disable won't work/isn't needed
    except FileNotFoundError:  # Safeguard
        logger.error("'systemctl' command not found unexpectedly.")
        raise CommandNotFoundError("systemctl") from None
    except Exception as e:
        logger.warning(
            f"Could not reliably determine if service '{service_name}' is enabled: {e}. Attempting disable anyway.",
            exc_info=True,
        )

    # Attempt to disable the service
    try:
        process = subprocess.run(
            [systemctl_cmd, "--user", "disable", service_name],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Systemd service '{service_name}' disabled successfully.")
        logger.debug(f"systemctl output: {process.stdout}{process.stderr}")
    except subprocess.CalledProcessError as e:
        # Check if error was because service was already static/masked etc.
        stderr_lower = (e.stderr or "").lower()
        if "static" in stderr_lower or "masked" in stderr_lower:
            logger.info(
                f"Service '{service_name}' is static or masked, cannot be disabled via 'disable' command."
            )
            # This isn't strictly a failure of the *disable* action's intent
            return
        error_msg = (
            f"Failed to disable systemd service '{service_name}'. Error: {e.stderr}"
        )
        logger.error(error_msg, exc_info=True)
        raise ServiceError(error_msg) from e


def _systemd_start_server(server_name: str, server_dir: str) -> None:
    """
    Starts the Bedrock server process within a detached 'screen' session.

    This function is typically called by the systemd service file (`ExecStart`).
    It clears the log file and launches `bedrock_server` inside screen.
    (Linux-specific)

    Args:
        server_name: The name of the server (used for screen session name).
        server_dir: The full path to the server's installation directory.

    Raises:
        MissingArgumentError: If `server_name` or `server_dir` is empty.
        DirectoryError: If `server_dir` does not exist or is not a directory.
        ServerStartError: If the `screen` command fails to execute.
        CommandNotFoundError: If the 'screen' or 'bash' command is not found.
        FileOperationError: If clearing the log file fails (optional, currently logs warning).
    """
    if platform.system() != "Linux":
        logger.error("Attempted to use Linux start method on non-Linux OS.")
        raise ServerStartError("Cannot use screen start method on non-Linux OS.")
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")

    if not os.path.isdir(server_dir):
        raise DirectoryError(f"Server directory not found: {server_dir}")
    bedrock_exe = os.path.join(server_dir, "bedrock_server")
    if not os.path.isfile(bedrock_exe):
        raise ServerStartError(
            f"Server executable 'bedrock_server' not found in {server_dir}"
        )
    if not os.access(bedrock_exe, os.X_OK):
        logger.warning(
            f"Server executable '{bedrock_exe}' is not executable. Attempting start anyway, but it may fail."
        )
        # Or raise ServerStartError("Server executable is not executable.")

    screen_cmd = shutil.which("screen")
    bash_cmd = shutil.which("bash")
    if not screen_cmd:
        raise CommandNotFoundError("screen")
    if not bash_cmd:
        raise CommandNotFoundError("bash")

    log_file_path = os.path.join(server_dir, "server_output.txt")
    logger.info(
        f"Starting server '{server_name}' via screen session 'bedrock-{server_name}'..."
    )
    logger.debug(f"Working directory: {server_dir}, Log file: {log_file_path}")

    # Clear/Initialize the server output log file
    try:
        # Open with 'w' to truncate if exists, create if not
        with open(log_file_path, "w", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] Starting Server via screen...\n")
        logger.debug(f"Initialized server log file: {log_file_path}")
    except OSError as e:
        # Log warning but don't necessarily fail the start if log init fails
        logger.warning(
            f"Failed to clear/initialize server log file '{log_file_path}': {e}. Continuing start...",
            exc_info=True,
        )

    # Construct the command to run inside screen
    # Use exec to replace the bash process with bedrock_server
    command_in_screen = f'cd "{server_dir}" && LD_LIBRARY_PATH=. exec ./bedrock_server'
    screen_session_name = f"bedrock-{server_name}"

    # Build the full screen command list
    full_screen_command = [
        screen_cmd,
        "-dmS",
        screen_session_name,  # Detached, named session
        "-L",  # Enable logging
        "-Logfile",
        log_file_path,  # Specify log file
        bash_cmd,  # Shell to run command in
        "-c",  # Option to run command string
        command_in_screen,
    ]
    logger.debug(f"Executing screen command: {' '.join(full_screen_command)}")

    try:
        process = subprocess.run(
            full_screen_command, check=True, capture_output=True, text=True
        )
        logger.info(
            f"Server '{server_name}' initiated successfully in screen session '{screen_session_name}'."
        )
        logger.debug(f"Screen command output: {process.stdout}{process.stderr}")
    except subprocess.CalledProcessError as e:
        error_msg = (
            f"Failed to start server '{server_name}' using screen. Error: {e.stderr}"
        )
        logger.error(error_msg, exc_info=True)
        raise ServerStartError(error_msg) from e
    except FileNotFoundError as e:  # Should be caught by shutil.which, but safeguard
        logger.error(f"Command not found during screen execution: {e}", exc_info=True)
        raise CommandNotFoundError(e.filename) from e


def _systemd_stop_server(server_name: str, server_dir: str) -> None:
    """
    Stops the Bedrock server running within a 'screen' session.

    This function is typically called by the systemd service file (`ExecStop`).
    It sends the "stop" command to the server via screen.
    (Linux-specific)

    Args:
        server_name: The name of the server (used for screen session name).
        server_dir: The server's installation directory (used for logging/context).

    Raises:
        MissingArgumentError: If `server_name` or `server_dir` is empty.
        ServerStopError: If sending the stop command via screen fails unexpectedly.
        CommandNotFoundError: If the 'screen' command is not found.
        # Does not raise error if screen session is not found (assumes already stopped).
    """
    if platform.system() != "Linux":
        logger.error("Attempted to use Linux stop method on non-Linux OS.")
        raise ServerStopError("Cannot use screen stop method on non-Linux OS.")
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not server_dir:
        raise MissingArgumentError(
            "Server directory cannot be empty."
        )  # Although not strictly used here

    screen_cmd = shutil.which("screen")
    if not screen_cmd:
        raise CommandNotFoundError("screen")

    screen_session_name = f"bedrock-{server_name}"
    logger.info(
        f"Attempting to stop server '{server_name}' by sending 'stop' command to screen session '{screen_session_name}'..."
    )

    try:
        # Send the "stop" command, followed by newline, to the screen session
        # Use 'stuff' to inject the command
        process = subprocess.run(
            [screen_cmd, "-S", screen_session_name, "-X", "stuff", "stop\n"],
            check=False,  # Don't raise if screen session doesn't exist
            capture_output=True,
            text=True,
        )

        if process.returncode == 0:
            logger.info(
                f"'stop' command sent successfully to screen session '{screen_session_name}'."
            )
            # Note: This only sends the command. The server still needs time to shut down.
            # The calling function (e.g., BedrockServer.stop) should handle waiting.
        elif "No screen session found" in process.stderr:
            logger.info(
                f"Screen session '{screen_session_name}' not found. Server likely already stopped."
            )
            # Not an error in this context
        else:
            # Screen command failed for other reasons
            error_msg = (
                f"Failed to send 'stop' command via screen. Error: {process.stderr}"
            )
            logger.error(error_msg, exc_info=True)
            raise ServerStopError(error_msg)

    except FileNotFoundError:  # Should be caught by shutil.which, but safeguard
        logger.error("'screen' command not found unexpectedly during stop.")
        raise CommandNotFoundError("screen") from None
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while sending stop command via screen: {e}",
            exc_info=True,
        )
        raise ServerStopError(f"Unexpected error sending stop via screen: {e}") from e


# --- Cron Job Management ---


_CRON_MONTHS_MAP = {
    "1": "January",
    "jan": "January",
    "january": "January",
    "2": "February",
    "feb": "February",
    "february": "February",
    "3": "March",
    "mar": "March",
    "march": "March",
    "4": "April",
    "apr": "April",
    "april": "April",
    "5": "May",
    "may": "May",
    "6": "June",
    "jun": "June",
    "june": "June",
    "7": "July",
    "jul": "July",
    "july": "July",
    "8": "August",
    "aug": "August",
    "august": "August",
    "9": "September",
    "sep": "September",
    "september": "September",
    "10": "October",
    "oct": "October",
    "october": "October",
    "11": "November",
    "nov": "November",
    "november": "November",
    "12": "December",
    "dec": "December",
    "december": "December",
}

_CRON_DAYS_MAP = {
    "0": "Sunday",
    "sun": "Sunday",
    "sunday": "Sunday",
    "1": "Monday",
    "mon": "Monday",
    "monday": "Monday",
    "2": "Tuesday",
    "tue": "Tuesday",
    "tuesday": "Tuesday",
    "3": "Wednesday",
    "wed": "Wednesday",
    "wednesday": "Wednesday",
    "4": "Thursday",
    "thu": "Thursday",
    "thursday": "Thursday",
    "5": "Friday",
    "fri": "Friday",
    "friday": "Friday",
    "6": "Saturday",
    "sat": "Saturday",
    "saturday": "Saturday",
    "7": "Sunday",  # Also map 7 to Sunday
}


def _get_cron_month_name(month_input: str) -> str:
    """Converts cron month input (number or name/abbr) to full month name."""
    month_str = str(month_input).strip().lower()
    if month_str in _CRON_MONTHS_MAP:
        return _CRON_MONTHS_MAP[month_str]
    else:
        raise InvalidCronJobError(
            f"Invalid month value: '{month_input}'. Use 1-12 or name/abbreviation."
        )


def _get_cron_dow_name(dow_input: str) -> str:
    """Converts cron day-of-week input (number or name/abbr) to full day name."""
    dow_str = str(dow_input).strip().lower()
    # Handle cron's 0 or 7 for Sunday mapping
    if dow_str == "7":
        dow_str = "0"  # Treat 7 as 0 for lookup
    if dow_str in _CRON_DAYS_MAP:
        return _CRON_DAYS_MAP[dow_str]
    else:
        raise InvalidCronJobError(
            f"Invalid day-of-week value: '{dow_input}'. Use 0-6, 7, or name/abbreviation (Sun-Sat)."
        )


def get_server_cron_jobs(server_name: str) -> List[str]:
    """
    Retrieves cron job lines from the user's crontab that relate to a specific server.

    Filters jobs containing `--server {server_name}` or potentially other known markers.
    (Linux-specific)

    Args:
        server_name: The name of the server to filter jobs for.

    Returns:
        A list of matching cron job command lines (strings). Returns an empty list
        if no matching jobs are found or if no crontab exists for the user.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        CommandNotFoundError: If the 'crontab' command is not found.
        ScheduleError: If running `crontab -l` fails for reasons other than 'no crontab'.
    """
    if platform.system() != "Linux":
        logger.debug("Cron job retrieval skipped: Not running on Linux.")
        return []
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    crontab_cmd = shutil.which("crontab")
    if not crontab_cmd:
        logger.error("'crontab' command not found. Cannot list cron jobs.")
        raise CommandNotFoundError("crontab")

    logger.debug(f"Retrieving cron jobs related to server '{server_name}'...")
    try:
        process = subprocess.run(
            [crontab_cmd, "-l"],
            capture_output=True,
            text=True,
            check=False,  # Handle 'no crontab' manually
            encoding="utf-8",
            errors="replace",
        )

        if process.returncode == 0:
            # Crontab exists and was read
            all_jobs = process.stdout
            logger.debug("Successfully read user crontab.")
            logger.debug(f"Found crons: {all_jobs}")
        elif process.returncode == 1 and "no crontab for" in process.stderr.lower():
            # No crontab file exists for the user
            logger.info("No crontab found for the current user.")
            return []
        else:
            # Another error occurred running crontab -l
            error_msg = f"Error running 'crontab -l'. Return code: {process.returncode}. Error: {process.stderr}"
            logger.error(error_msg)
            raise ScheduleError(error_msg)

        # Filter the jobs
        filtered_jobs: List[str] = []
        server_arg_pattern = f'--server "{server_name}"'  # Basic filter
        # command_pattern = f"{EXPATH} backup"

        for line in all_jobs.splitlines():
            line = line.strip()
            # Ignore comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Check if the line contains the server argument
            if (
                server_arg_pattern in line
            ):  # Add more conditions if needed (e.g., `or command_pattern in line`)
                filtered_jobs.append(line)

        if not filtered_jobs:
            logger.info(f"No cron jobs specifically found for server '{server_name}'.")
        else:
            logger.info(
                f"Found {len(filtered_jobs)} cron job(s) related to server '{server_name}'."
            )
            logger.debug(f"Filtered jobs: {filtered_jobs}")
        return filtered_jobs

    except FileNotFoundError:  # Should be caught by shutil.which, but safeguard
        logger.error("'crontab' command not found unexpectedly.")
        raise CommandNotFoundError("crontab") from None
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while getting cron jobs: {e}", exc_info=True
        )
        raise ScheduleError(f"Unexpected error getting cron jobs: {e}") from e


def _parse_cron_line(line: str) -> Optional[Tuple[str, str, str, str, str, str]]:
    """
    Parses a standard cron job line into its time/command components.

    Args:
        line: A single, non-commented line from crontab output.

    Returns:
        A tuple containing (minute, hour, day_of_month, month, day_of_week, command_string),
        or None if the line does not have at least 6 parts.
    """
    parts = line.strip().split(maxsplit=5)  # Split into max 6 parts (5 time + command)
    if len(parts) == 6:
        # minute, hour, day_of_month, month, day_of_week, command
        return tuple(parts)  # type: ignore
    else:
        logger.warning(f"Could not parse cron line (expected >= 6 parts): '{line}'")
        return None


def _format_cron_command(command_string: str) -> str:
    """
    Formats the command part of a cron job for display purposes.

    Attempts to remove the script path and python executable calls.

    Args:
        command_string: The full command string from the cron job line.

    Returns:
        A simplified command string (e.g., "backup", "update-server"). Returns
        the original string if formatting fails or is complex.
    """
    try:
        command = command_string.strip()
        script_path_str = str(EXPATH)  # Ensure it's a string

        # Remove potential prefixes like the absolute path to the script
        if command.startswith(script_path_str):
            command = command[len(script_path_str) :].strip()

        # Remove potential python executable prefix (e.g., /usr/bin/python3.10)
        parts = command.split()
        if parts and (
            parts[0].endswith("python")
            or parts[0].endswith("python3")
            or ".exe" in parts[0]
        ):
            command = " ".join(parts[1:])

        # The first remaining "word" is likely the intended command action
        main_command = command.split(maxsplit=1)[0]
        return (
            main_command if main_command else command_string
        )  # Return original if empty after parsing

    except Exception as e:
        logger.warning(
            f"Failed to format cron command '{command_string}' for display: {e}. Returning original.",
            exc_info=True,
        )
        return command_string  # Return original on error


def get_cron_jobs_table(cron_jobs: List[str]) -> List[Dict[str, str]]:
    """
    Formats a list of cron job strings into structured dictionaries for display.

    Includes both raw schedule/command and human-readable interpretations.

     Args:
        cron_jobs: A list of raw cron job strings.

    Returns:
        A list of dictionaries, each representing a job with keys like 'minute',
        'hour', 'command' (raw), 'command_display', 'schedule_time' (readable).
        Returns an empty list if input is empty or all lines fail parsing.
    """
    table_data: List[Dict[str, str]] = []
    if not cron_jobs:
        logger.debug("No cron job strings provided to format.")
        return table_data

    logger.debug(f"Formatting {len(cron_jobs)} cron job string(s) into table data...")

    for line in cron_jobs:
        parsed_job = _parse_cron_line(line)
        if not parsed_job:
            logger.warning(
                f"Skipping unparseable cron line during table formatting: '{line}'"
            )
            continue

        minute, hour, dom, month, dow, raw_command = parsed_job
        raw_schedule = f"{minute} {hour} {dom} {month} {dow}"

        # Get readable schedule (handle errors)
        try:
            readable_schedule = convert_to_readable_schedule(
                minute, hour, dom, month, dow
            )
        except InvalidCronJobError as e:
            logger.warning(
                f"Could not convert schedule '{raw_schedule}' to readable format: {e}. Using raw schedule."
            )
            readable_schedule = raw_schedule  # Fallback
        except Exception as e:
            logger.error(
                f"Unexpected error converting schedule '{raw_schedule}': {e}",
                exc_info=True,
            )
            readable_schedule = raw_schedule  # Fallback

        # Get display command (handle errors)
        try:
            display_command = _format_cron_command(raw_command)
        except Exception as e:
            logger.warning(
                f"Could not format command '{raw_command}' for display: {e}. Using raw command."
            )
            display_command = raw_command  # Fallback

        table_data.append(
            {
                "minute": minute,
                "hour": hour,
                "day_of_month": dom,
                "month": month,
                "day_of_week": dow,
                "command": raw_command,  # The original, full command
                "command_display": display_command,  # Simplified command for UI
                "schedule_time": readable_schedule,  # Human-readable schedule
            }
        )
        logger.debug(f"Formatted entry: {table_data[-1]}")

    logger.debug(f"Finished formatting cron jobs. Returning {len(table_data)} entries.")
    return table_data


def _add_cron_job(cron_string: str) -> None:
    """
    Adds a job string to the current user's crontab.

    (Linux-specific)

    Args:
        cron_string: The full cron job line to add (e.g., "0 * * * * /path/to/cmd --args").

    Raises:
        CommandNotFoundError: If 'crontab' command not found.
        ScheduleError: If reading the existing crontab or writing the new one fails.
        MissingArgumentError: If `cron_string` is empty.
    """
    if platform.system() != "Linux":
        logger.warning("Cron job addition skipped: Not running on Linux.")
        return
    if not cron_string or not cron_string.strip():
        raise MissingArgumentError("Cron job string cannot be empty.")

    cron_string = cron_string.strip()  # Ensure no leading/trailing whitespace

    crontab_cmd = shutil.which("crontab")
    if not crontab_cmd:
        raise CommandNotFoundError("crontab")

    logger.info(f"Adding cron job: '{cron_string}'")
    try:
        # 1. Get current crontab content
        process = subprocess.run(
            [crontab_cmd, "-l"],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        current_crontab = ""
        if process.returncode == 0:
            current_crontab = process.stdout
            logger.debug("Read existing crontab.")
        elif "no crontab for" in process.stderr.lower():
            logger.debug("No existing crontab found. Creating new one.")
            current_crontab = ""  # Start fresh
        else:
            error_msg = f"Error reading current crontab: {process.stderr}"
            logger.error(error_msg)
            raise ScheduleError(error_msg)

        # 2. Check if job already exists
        existing_lines = current_crontab.splitlines()
        if cron_string in [line.strip() for line in existing_lines]:
            logger.warning(
                f"Cron job '{cron_string}' already exists. Skipping addition."
            )
            return

        # 3. Append new job (ensure newline)
        new_crontab_content = current_crontab.strip() + "\n" + cron_string + "\n"

        # 4. Write back to crontab via stdin
        write_process = subprocess.Popen(
            [crontab_cmd, "-"],
            stdin=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout, stderr = write_process.communicate(
            input=new_crontab_content
        )  # Send content to stdin

        if write_process.returncode != 0:
            error_msg = f"Failed to write updated crontab. Return code: {write_process.returncode}. Stderr: {stderr}"
            logger.error(error_msg)
            raise ScheduleError(error_msg)

        logger.info(f"Successfully added cron job: '{cron_string}'")

    except FileNotFoundError:  # Should be caught by shutil.which, but safeguard
        logger.error("'crontab' command not found unexpectedly.")
        raise CommandNotFoundError("crontab") from None
    except (
        subprocess.CalledProcessError,
        OSError,
    ) as e:  # Catch errors during read/write
        logger.error(f"Failed to add cron job '{cron_string}': {e}", exc_info=True)
        raise ScheduleError(f"Failed to add cron job: {e}") from e
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while adding cron job: {e}", exc_info=True
        )
        raise ScheduleError(f"Unexpected error adding cron job: {e}") from e


def validate_cron_input(value: str, min_val: int, max_val: int) -> None:
    """
    Validates a single cron time field value (minute, hour, day, month, weekday).
    Allows '*' (wildcard) or an integer within the specified range.
    (This function can remain largely the same)

    Args:
        value: The cron field value string (e.g., "5", "*").
        min_val: The minimum allowed integer value for this field.
        max_val: The maximum allowed integer value for this field.

    Raises:
        InvalidCronJobError: If the input value is not '*' and not an integer within the
                             valid range [min_val, max_val].
    """
    if value == "*":
        return  # Wildcard is always valid

    try:
        # Check if it's a simple integer first
        num = int(value)
        if not (min_val <= num <= max_val):
            raise InvalidCronJobError(
                f"Value '{value}' is out of range ({min_val}-{max_val})."
            )
        # Basic validation passed for simple integer
        return
    except ValueError:
        # Log a debug message if it's not '*' or a simple int.
        logger.debug(
            f"Cron value '{value}' is not '*' or a simple integer; advanced validation skipped."
        )
        pass  # Allow complex values for now if not simple int/wildcard


def convert_to_readable_schedule(
    minute: str, hour: str, day_of_month: str, month: str, day_of_week: str
) -> str:
    """
    Converts standard cron time fields into a more human-readable schedule description.
    Handles common cases like "Every minute", "Daily at HH:MM", "Weekly on Day at HH:MM", etc.

    Args:
        minute: Cron minute field ('0'-'59' or '*').
        hour: Cron hour field ('0'-'23' or '*').
        day_of_month: Cron day of month field ('1'-'31' or '*').
        month: Cron month field ('1'-'12' or '*').
        day_of_week: Cron day of week field ('0'-'7' or '*', where 0 and 7 are Sunday).

    Returns:
        A human-readable string description of the schedule. Falls back to the
        raw cron string if the pattern is complex or unrecognized.

    Raises:
        InvalidCronJobError: If any input field fails basic validation or conversion.
    """
    # Validate inputs first using the function above
    validate_cron_input(minute, 0, 59)
    validate_cron_input(hour, 0, 23)
    validate_cron_input(day_of_month, 1, 31)
    validate_cron_input(month, 1, 12)
    validate_cron_input(day_of_week, 0, 7)  # Allow 0-7

    raw_schedule = f"{minute} {hour} {day_of_month} {month} {day_of_week}"
    logger.debug(f"Converting raw cron schedule '{raw_schedule}' to readable format.")

    # Handle common patterns (using integer conversion where needed)
    try:
        # Every Minute
        if (
            minute == "*"
            and hour == "*"
            and day_of_month == "*"
            and month == "*"
            and day_of_week == "*"
        ):
            return "Every minute"

        # Specific Time, Every Day
        if (
            minute != "*"
            and hour != "*"
            and day_of_month == "*"
            and month == "*"
            and day_of_week == "*"
        ):
            return f"Daily at {int(hour):02d}:{int(minute):02d}"

        # Specific Time, Specific Day(s) of Week
        if (
            minute != "*"
            and hour != "*"
            and day_of_month == "*"
            and month == "*"
            and day_of_week != "*"
        ):
            # Use internal helper to get day name (handles 0-7, names, abbr)
            day_name = _get_cron_dow_name(
                day_of_week
            )  # Raises InvalidCronJobError if invalid
            # Note: This doesn't handle lists or ranges in day_of_week yet (e.g., "1,3,5" or "1-5")
            return f"Weekly on {day_name} at {int(hour):02d}:{int(minute):02d}"

        # Specific Time, Specific Day of Month
        if (
            minute != "*"
            and hour != "*"
            and day_of_month != "*"
            and month == "*"
            and day_of_week == "*"
        ):
            # Note: Doesn't handle lists/ranges in day_of_month
            return f"Monthly on day {int(day_of_month)} at {int(hour):02d}:{int(minute):02d}"

        # Specific Time, Specific Month and Day of Month (Yearly)
        if (
            minute != "*"
            and hour != "*"
            and day_of_month != "*"
            and month != "*"
            and day_of_week == "*"
        ):
            # Use internal helper to get month name (handles 1-12, names, abbr)
            month_name = _get_cron_month_name(
                month
            )  # Raises InvalidCronJobError if invalid
            # Note: Doesn't handle lists/ranges
            return f"Yearly on {month_name} {int(day_of_month)} at {int(hour):02d}:{int(minute):02d}"

        # Fallback for other patterns (including steps, ranges, lists if validation allows them)
        logger.debug(
            f"Cron schedule '{raw_schedule}' complex or unrecognized pattern. Returning raw."
        )
        return f"Cron schedule: {raw_schedule}"

    except (
        ValueError
    ) as e:  # Catch errors during int() conversion for specific patterns
        logger.error(
            f"Invalid numeric value in specific cron schedule pattern '{raw_schedule}': {e}",
            exc_info=True,
        )
        raise InvalidCronJobError(
            f"Invalid numeric value in schedule: {raw_schedule}"
        ) from e


def _modify_cron_job(old_cron_string: str, new_cron_string: str) -> None:
    """
    Replaces an existing cron job line with a new one in the user's crontab.

    (Linux-specific)

    Args:
        old_cron_string: The exact existing cron job line to find and replace.
        new_cron_string: The new cron job line to insert.

    Raises:
        CommandNotFoundError: If 'crontab' command not found.
        ScheduleError: If reading/writing the crontab fails, or if the `old_cron_string`
                       is not found in the current crontab.
        MissingArgumentError: If either argument string is empty.
    """
    if platform.system() != "Linux":
        logger.warning("Cron job modification skipped: Not running on Linux.")
        return
    if not old_cron_string or not old_cron_string.strip():
        raise MissingArgumentError("Old cron string cannot be empty.")
    if not new_cron_string or not new_cron_string.strip():
        raise MissingArgumentError("New cron string cannot be empty.")

    old_cron_string = old_cron_string.strip()
    new_cron_string = new_cron_string.strip()

    if old_cron_string == new_cron_string:
        logger.info("Old and new cron strings are identical. No modification needed.")
        return

    crontab_cmd = shutil.which("crontab")
    if not crontab_cmd:
        raise CommandNotFoundError("crontab")

    logger.info(
        f"Attempting to modify cron job: Replace '{old_cron_string}' with '{new_cron_string}'"
    )

    try:
        # 1. Get current crontab
        process = subprocess.run(
            [crontab_cmd, "-l"],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        current_crontab = ""
        if process.returncode == 0:
            current_crontab = process.stdout
        elif "no crontab for" not in process.stderr.lower():
            error_msg = f"Error reading current crontab: {process.stderr}"
            logger.error(error_msg)
            raise ScheduleError(error_msg)

        # 2. Find and replace the line
        lines = current_crontab.splitlines()
        found = False
        updated_lines = []
        for line in lines:
            stripped_line = line.strip()
            if stripped_line == old_cron_string:
                updated_lines.append(new_cron_string)  # Replace with new string
                found = True
                logger.debug(f"Found matching line to replace: '{old_cron_string}'")
            else:
                updated_lines.append(line)  # Keep other lines

        if not found:
            error_msg = f"Cron job to modify was not found in the current crontab: '{old_cron_string}'"
            logger.error(error_msg)
            raise ScheduleError(error_msg)

        # 3. Write back the modified crontab
        new_crontab_content = "\n".join(updated_lines) + "\n"  # Ensure trailing newline

        write_process = subprocess.Popen(
            [crontab_cmd, "-"],
            stdin=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout, stderr = write_process.communicate(input=new_crontab_content)

        if write_process.returncode != 0:
            error_msg = f"Failed to write modified crontab. Return code: {write_process.returncode}. Stderr: {stderr}"
            logger.error(error_msg)
            raise ScheduleError(error_msg)

        logger.info(f"Successfully modified cron job.")

    except FileNotFoundError:  # Safeguard
        logger.error("'crontab' command not found unexpectedly.")
        raise CommandNotFoundError("crontab") from None
    except (subprocess.CalledProcessError, OSError) as e:
        logger.error(f"Failed to modify cron job: {e}", exc_info=True)
        raise ScheduleError(f"Failed to modify cron job: {e}") from e
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while modifying cron job: {e}", exc_info=True
        )
        raise ScheduleError(f"Unexpected error modifying cron job: {e}") from e


def _delete_cron_job(cron_string: str) -> None:
    """
    Deletes a specific job line from the current user's crontab.

    (Linux-specific)

    Args:
        cron_string: The exact cron job line to find and remove.

    Raises:
        CommandNotFoundError: If 'crontab' command not found.
        ScheduleError: If reading or writing the crontab fails.
        MissingArgumentError: If `cron_string` is empty.
    """
    if platform.system() != "Linux":
        logger.warning("Cron job deletion skipped: Not running on Linux.")
        return
    if not cron_string or not cron_string.strip():
        raise MissingArgumentError("Cron job string to delete cannot be empty.")

    cron_string = cron_string.strip()

    crontab_cmd = shutil.which("crontab")
    if not crontab_cmd:
        raise CommandNotFoundError("crontab")

    logger.info(f"Attempting to delete cron job: '{cron_string}'")

    try:
        # 1. Get current crontab
        process = subprocess.run(
            [crontab_cmd, "-l"],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        current_crontab = ""
        if process.returncode == 0:
            current_crontab = process.stdout
        elif "no crontab for" not in process.stderr.lower():
            error_msg = f"Error reading current crontab: {process.stderr}"
            logger.error(error_msg)
            raise ScheduleError(error_msg)

        # 2. Filter out the line to delete
        lines = current_crontab.splitlines()
        updated_lines = [line for line in lines if line.strip() != cron_string]

        if len(lines) == len(updated_lines):
            logger.warning(
                f"Cron job to delete was not found: '{cron_string}'. No changes made."
            )
            return  # Job wasn't there, nothing to do

        # 3. Write back the filtered crontab
        new_crontab_content = "\n".join(updated_lines)
        # Ensure trailing newline if content exists
        if new_crontab_content:
            new_crontab_content += "\n"

        write_process = subprocess.Popen(
            [crontab_cmd, "-"],
            stdin=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout, stderr = write_process.communicate(input=new_crontab_content)

        if write_process.returncode != 0:
            error_msg = f"Failed to write updated crontab after deletion. Return code: {write_process.returncode}. Stderr: {stderr}"
            logger.error(error_msg)
            raise ScheduleError(error_msg)

        logger.info(f"Successfully deleted cron job: '{cron_string}'")

    except FileNotFoundError:  # Safeguard
        logger.error("'crontab' command not found unexpectedly.")
        raise CommandNotFoundError("crontab") from None
    except (subprocess.CalledProcessError, OSError) as e:
        logger.error(f"Failed to delete cron job '{cron_string}': {e}", exc_info=True)
        raise ScheduleError(f"Failed to delete cron job: {e}") from e
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while deleting cron job: {e}", exc_info=True
        )
        raise ScheduleError(f"Unexpected error deleting cron job: {e}") from e
