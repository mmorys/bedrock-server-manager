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
    ServerNotRunningError,
    SendCommandError,
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
ExecStart={EXPATH} start-server --server "{server_name}" --mode direct
ExecStop={EXPATH} systemd-stop --server "{server_name}"
# ExecReload might not be necessary if stop/start works reliably
# ExecReload={EXPATH} systemd-stop --server "{server_name}" && {EXPATH} start-server --server "{server_name}" -mode direct
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


def _linux_start_server(server_name: str, server_dir: str) -> None:
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


def _linux_stop_server(server_name: str, server_dir: str) -> None:
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


def _linux_send_command(server_name: str, command: str) -> None:
    """
    Sends a command to a Bedrock server running in a 'screen' session.
    This function is typically called by the systemd service file (`ExecReload`).
    It sends the specified command to the server via screen.
    (Linux-specific)

    Args:
        server_name: The name of the server (used for screen session name).
        command: The command to send to the server.

    Raises:
        MissingArgumentError: If `server_name` or `command` is empty.
        CommandNotFoundError: If the 'screen' command is not found.
        ServerNotRunningError: If the screen session for the server is not found.
        SendCommandError: If sending the command via screen fails unexpectedly.
    """
    if not server_name:
        raise MissingArgumentError("server_name cannot be empty.")
    if not command:
        raise MissingArgumentError("command cannot be empty.")

    screen_cmd_path = shutil.which("screen")
    if not screen_cmd_path:
        logger.error(
            "'screen' command not found. Cannot send command. Is 'screen' installed and in PATH?"
        )
        raise CommandNotFoundError(
            "screen", message="'screen' command not found. Is it installed?"
        )

    try:
        screen_session_name = f"bedrock-{server_name}"
        # Ensure the command ends with a newline, as 'stuff' simulates typing
        command_with_newline = command if command.endswith("\n") else command + "\n"

        process = subprocess.run(
            [
                screen_cmd_path,
                "-S",
                screen_session_name,
                "-X",
                "stuff",
                command_with_newline,
            ],
            check=True,  # Raise CalledProcessError on non-zero exit
            capture_output=True,  # Capture stdout and stderr
            text=True,  # Decode stdout/stderr as text
        )
        logger.debug(
            f"'screen' command executed successfully for server '{server_name}'. stdout: {process.stdout}, stderr: {process.stderr}"
        )
        logger.info(f"Sent command '{command}' to server '{server_name}' via screen.")

    except subprocess.CalledProcessError as e:
        # screen -X stuff usually exits 0, but if session doesn't exist,
        # it might exit non-zero on some versions or print to stderr.
        # More reliably, check stderr for the "No screen session found" message.
        if "No screen session found" in e.stderr or (
            hasattr(e, "stdout") and "No screen session found" in e.stdout
        ):  # Check stdout too, just in case
            logger.error(
                f"Failed to send command: Screen session '{screen_session_name}' not found. "
                f"Is the server running correctly in screen? stderr: {e.stderr}, stdout: {e.stdout}"
            )
            raise ServerNotRunningError(
                f"Screen session '{screen_session_name}' not found."
            ) from e
        else:
            logger.error(
                f"Failed to send command via screen for server '{server_name}': {e}. "
                f"stdout: {e.stdout}, stderr: {e.stderr}",
                exc_info=True,
            )
            raise SendCommandError(
                f"Failed to send command to '{server_name}' via screen: {e}"
            ) from e
    except FileNotFoundError:
        # This would typically only happen if 'screen' was deleted *after* shutil.which found it,
        # or if shutil.which somehow returned a path that became invalid.
        # The primary check for 'screen' not existing is handled before the try block.
        logger.error(
            f"'screen' command (path: {screen_cmd_path}) not found unexpectedly "
            f"when trying to send command to '{server_name}'."
        )
        raise CommandNotFoundError(
            "screen",
            message=f"'screen' command not found unexpectedly at path: {screen_cmd_path}.",
        ) from None
    except Exception as e:  # Catch-all for other unexpected errors
        logger.error(
            f"An unexpected error occurred while trying to send command to server '{server_name}': {e}",
            exc_info=True,
        )
        raise SendCommandError(
            f"Unexpected error sending command to '{server_name}': {e}"
        ) from e
