# bedrock_server_manager/core/system/linux.py
"""
Provides Linux-specific implementations for system interactions.

Includes functions for managing systemd user services (create, enable, disable, check)
for Bedrock servers. It also provides helpers for starting, stopping, and sending
commands to server processes managed via `screen`. Relies on external commands
like `systemctl` and `screen`.
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
    ServerNotRunningError,
    SendCommandError,
    SystemError,
    InvalidServerNameError,
    ServerStartError,
    ServerStopError,
    MissingArgumentError,
    FileOperationError,
    AppFileNotFoundError,
)

logger = logging.getLogger(__name__)


# --- Systemd Service Management ---


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
        MissingArgumentError: If required arguments are missing.
        AppFileNotFoundError: If the specified `working_directory` does not exist.
        FileOperationError: If creating directories or writing the service file fails.
        CommandNotFoundError: If `systemctl` is not found.
        SystemError: If reloading the systemd daemon fails.
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
        raise AppFileNotFoundError(working_directory, "WorkingDirectory")

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
        raise FileOperationError(
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
        raise FileOperationError(
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
        raise SystemError(
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
        raise SystemError(
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
        raise SystemError(
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
        raise SystemError(
            f"Failed to disable systemd service '{name_to_use}'. Error: {e.stderr}"
        ) from e


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
        AppFileNotFoundError: If `server_dir` or the server executable does not exist.
        ServerStartError: If the `screen` command fails to execute.
        CommandNotFoundError: If the 'screen' or 'bash' command is not found.
        SystemError: If not run on Linux.
    """
    if platform.system() != "Linux":
        logger.error("Attempted to use Linux start method on non-Linux OS.")
        raise SystemError("Cannot use screen start method on non-Linux OS.")
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")

    if not os.path.isdir(server_dir):
        raise AppFileNotFoundError(server_dir, "Server directory")
    bedrock_exe = os.path.join(server_dir, "bedrock_server")
    if not os.path.isfile(bedrock_exe):
        raise AppFileNotFoundError(bedrock_exe, "Server executable")
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


def _linux_send_command(server_name: str, command: str) -> None:
    """
    Sends a command to a Bedrock server running in a 'screen' session.
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


# -- UNUSED --
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
        SystemError: If not run on Linux.
    """
    if platform.system() != "Linux":
        logger.error("Attempted to use Linux stop method on non-Linux OS.")
        raise SystemError("Cannot use screen stop method on non-Linux OS.")
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


# ---
