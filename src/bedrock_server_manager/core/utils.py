# bedrock_server_manager/core/utils.py
"""
Provides core utility functions for server management tasks.

This includes server name validation, status checking by parsing log files (currently unused),
and platform-specific operations like attaching to screen sessions on Linux.
These functions are typically lower-level helpers used by other core modules or API layers.
"""

import os
import re
import glob
import logging
import platform
import subprocess
import time
import shutil
from typing import Tuple, Optional

# Local imports
from bedrock_server_manager.error import (
    MissingArgumentError,
    FileOperationError,
    InvalidServerNameError,
    SystemError,
    CommandNotFoundError,
)

# Dummy import
core_server_utils = None

logger = logging.getLogger(__name__)


# --- Server Stuff ---


def core_validate_server_name_format(server_name: str) -> None:
    """
    Validates the format of a server name.
    Checks if the name contains only alphanumeric characters, hyphens, and underscores.

    Args:
        server_name: The server name string to validate.

    Raises:
        InvalidServerNameError: If the server name is empty or has an invalid format.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not re.fullmatch(r"^[a-zA-Z0-9_-]+$", server_name):
        raise InvalidServerNameError(
            "Invalid server name format. Only use letters (a-z, A-Z), "
            "numbers (0-9), hyphens (-), and underscores (_)."
        )
    logger.debug(f"Server name '{server_name}' format is valid.")


# --- Currently Unused ---
def check_server_status(
    server_name: str,
    base_dir: str,
    max_attempts: int = 10,
    chunk_size_bytes: int = 8192,
    max_scan_bytes: int = 1 * 1024 * 1024,
) -> str:
    """
    Determines the server's status by reading the end of its log file.

    Efficiently reads the log file ('server_output.txt') backwards in chunks
    to find the most recent status indicator ("Server started.", "Quit correctly", etc.).

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server's folder.
        max_attempts: Max attempts to wait for the log file to appear (0.5s sleep each).
        chunk_size_bytes: How many bytes to read from the end of the file at a time.
        max_scan_bytes: Maximum total bytes to scan backwards from the end of the file.

    Returns:
        The determined server status string ("RUNNING", "STARTING", "RESTARTING",
        "STOPPING", "STOPPED", or "UNKNOWN").

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        FileOperationError: If reading the log file fails due to OS errors.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    log_file_path = os.path.join(base_dir, server_name, "server_output.txt")
    status = "UNKNOWN"  # Default status

    logger.info(
        f"Checking server status for '{server_name}' by reading log file: {log_file_path}"
    )

    # --- Wait for log file existence ---
    attempt = 0
    sleep_interval = 0.5
    while not os.path.exists(log_file_path) and attempt < max_attempts:
        logger.debug(
            f"Log file '{log_file_path}' not found. Waiting... (Attempt {attempt + 1}/{max_attempts})"
        )
        time.sleep(sleep_interval)
        attempt += 1

    if not os.path.exists(log_file_path):
        logger.warning(
            f"Log file '{log_file_path}' did not appear within {max_attempts * sleep_interval} seconds."
        )
        # If log doesn't exist, maybe server hasn't started or was deleted?
        # Return UNKNOWN based purely on log check.
        return "UNKNOWN"

    # --- Read log file efficiently from the end ---
    try:
        with open(log_file_path, "rb") as f:  # Open in binary mode for seeking
            f.seek(0, os.SEEK_END)  # Go to the end of the file
            file_size = f.tell()
            bytes_scanned = 0
            buffer = b""

            # Read backwards in chunks
            while bytes_scanned < max_scan_bytes and bytes_scanned < file_size:
                read_size = min(chunk_size_bytes, file_size - bytes_scanned)
                f.seek(file_size - bytes_scanned - read_size)
                chunk = f.read(read_size)
                bytes_scanned += read_size
                buffer = chunk + buffer  # Prepend chunk to buffer

                # Process lines in the buffer (handle partial lines across chunks)
                # Decode using utf-8, ignore errors
                lines = buffer.decode("utf-8", errors="ignore").splitlines()

                # Process lines from most recent (end of buffer) first
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue  # Skip empty lines

                    # Check for status indicators (most recent match wins)
                    if "Server started." in line:
                        status = "RUNNING"
                        break
                    elif "Starting Server" in line:
                        status = "STARTING"
                        break
                    elif "Restarting server in 10 seconds" in line:
                        status = "RESTARTING"
                        break
                    elif "Shutting down server in 10 seconds" in line:
                        status = "STOPPING"
                        break
                    elif "Quit correctly." in line:
                        status = "STOPPED"
                        break

                if status != "UNKNOWN":
                    logger.debug(f"Status '{status}' determined from log content.")
                    break  # Found status, exit reading loop

                # If buffer starts with partial line, keep it for next iteration
                if (
                    not buffer.startswith(b"\n")
                    and not buffer.startswith(b"\r")
                    and bytes_scanned < file_size
                ):
                    # Find last newline to determine partial line start
                    last_newline = max(buffer.rfind(b"\n"), buffer.rfind(b"\r"))
                    if last_newline != -1:
                        buffer = buffer[: last_newline + 1]

            if status == "UNKNOWN":
                logger.warning(
                    f"Could not determine server status after scanning last {bytes_scanned} bytes of log file '{log_file_path}'."
                )

    except OSError as e:
        logger.error(
            f"Failed to read server log file '{log_file_path}': {e}", exc_info=True
        )
        raise FileOperationError(
            f"Failed to read server log '{log_file_path}': {e}"
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error processing log file '{log_file_path}': {e}",
            exc_info=True,
        )
        # Return UNKNOWN in case of unexpected processing errors
        return "UNKNOWN"

    logger.info(
        f"Determined status for server '{server_name}': {status} (from log check)"
    )
    return status


def update_server_status_in_config(
    server_name: str, base_dir: str, config_dir: Optional[str] = None
) -> None:
    """
    Checks the server's current status via log file and updates the server's config file.

    Compares the status found in the log file with the last known status in the config.
    Writes the new status to the config file if it has changed or is informative.

    Args:
        server_name: The name of the server.
        base_dir: The base directory containing the server's folder (for log file path).
        config_dir: Optional. The base directory containing server config folders.
                    Defaults to `settings.config_dir` if None.

    Raises:
        MissingArgumentError: If `server_name` or `base_dir` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If reading the log or reading/writing the config file fails.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    logger.debug(
        f"Updating status in config for server '{server_name}' based on log check."
    )

    try:
        # Get status by checking the log file
        checked_status = check_server_status(server_name, base_dir)

        # Get the last status recorded in the config
        current_config_status = core_server_utils.get_server_status_from_config(
            server_name, config_dir
        )

        logger.debug(
            f"Server '{server_name}': Status from log='{checked_status}', Status from config='{current_config_status}'"
        )

        # Update config only if checked status is different and informative
        if checked_status != current_config_status and checked_status != "UNKNOWN":
            logger.info(
                f"Status mismatch or update needed for server '{server_name}'. Updating config from '{current_config_status}' to '{checked_status}'."
            )
            core_server_utils.manage_server_config(
                server_name=server_name,
                key="status",
                operation="write",
                value=checked_status,
                config_dir=config_dir,
            )
            logger.info(
                f"Successfully updated server status in config for '{server_name}' to '{checked_status}'."
            )
        elif checked_status == "UNKNOWN" and current_config_status not in (
            "UNKNOWN",
            "STOPPED",
        ):
            logger.warning(
                f"Log check resulted in UNKNOWN status for server '{server_name}', but config status is '{current_config_status}'. Config status not updated."
            )
        else:
            logger.debug(
                f"Server '{server_name}' status ('{checked_status}') matches config or is UNKNOWN. No config update needed."
            )

    except (FileOperationError, MissingArgumentError, InvalidServerNameError) as e:
        # Catch errors from check_server_status or manage_server_config
        logger.error(
            f"Failed to update server status in config for '{server_name}': {e}",
            exc_info=True,
        )
        raise  # Re-raise the caught error
    except Exception as e:
        logger.error(
            f"Unexpected error updating server status in config for '{server_name}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Unexpected error updating server status config for '{server_name}': {e}"
        ) from e


# ---


# --- Screen Attach ---
def core_execute_screen_attach(screen_session_name: str) -> Tuple[bool, str]:
    """
    Executes the command to attach to a Linux screen session.
    (Linux-specific)

    Args:
        screen_session_name: The name of the screen session (e.g., "bedrock-servername").

    Returns:
        A tuple (success: bool, message: str).
        Success is True if the command executes without a CalledProcessError.
        Message contains output or error details.

    Raises:
        SystemError: If not on Linux.
        CommandNotFoundError: If the 'screen' command is not found.
    """
    if platform.system() != "Linux":
        raise SystemError("Screen session attachment is only supported on Linux.")

    screen_cmd = shutil.which("screen")
    if not screen_cmd:
        raise CommandNotFoundError(
            "screen", "'screen' command not found. Is screen installed?"
        )

    command = [screen_cmd, "-r", screen_session_name]
    logger.debug(f"Executing screen attach command: {' '.join(command)}")
    try:
        # Using subprocess.run as the core function doesn't need to be interactive itself.
        # The API layer will decide how to present this to a user.
        process = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=10
        )
        output = process.stdout.strip() + (
            "\n" + process.stderr.strip() if process.stderr.strip() else ""
        )
        logger.info(
            f"Screen attach command executed for '{screen_session_name}'. Output: {output}"
        )
        return (
            True,
            f"Attach command executed for session '{screen_session_name}'. Output: {output}",
        )
    except subprocess.CalledProcessError as e:
        stderr_lower = (e.stderr or "").lower()
        if (
            "no screen session found" in stderr_lower
            or "there is no screen to be resumed" in stderr_lower
        ):
            msg = f"Screen session '{screen_session_name}' not found."
            logger.warning(msg)
            return False, msg
        else:
            msg = f"Failed to execute screen attach command for '{screen_session_name}'. Error: {e.stderr or 'Unknown error'}"
            logger.error(msg, exc_info=True)
            return False, msg
    except subprocess.TimeoutExpired:
        msg = (
            f"Timeout while trying to attach to screen session '{screen_session_name}'."
        )
        logger.error(msg)
        return False, msg
    except FileNotFoundError:  # Should be caught by shutil.which, but safeguard
        raise CommandNotFoundError(
            "screen",
            message="'screen' command not found unexpectedly during execution.",
        )
