# bedrock-server-manager/bedrock_server_manager/core/utils.py

import os
import re
import glob
import logging
import platform
import subprocess
import shutil
from typing import List, Tuple, Optional

logger = logging.getLogger("bedrock_server_manager.core.utils")


# --- Server Name Validation ---
def core_validate_server_name_format(server_name: str) -> None:
    """
    Validates the format of a server name.
    Checks if the name contains only alphanumeric characters, hyphens, and underscores.

    Args:
        server_name: The server name string to validate.

    Raises:
        ValueError: If the server name is empty or has an invalid format.
    """
    if not server_name:
        raise ValueError("Server name cannot be empty.")
    if not re.fullmatch(r"^[a-zA-Z0-9_-]+$", server_name):
        raise ValueError(
            "Invalid server name format. Only use letters (a-z, A-Z), "
            "numbers (0-9), hyphens (-), and underscores (_)."
        )
    logger.debug(
        f"core.core_validate_server_name_format: Server name '{server_name}' format is valid."
    )


# --- File Listing ---
def core_list_files_by_extension(directory: str, extensions: List[str]) -> List[str]:
    """
    Lists all files within a specified directory that match a list of extensions.

    Args:
        directory: The full path to the directory to search.
        extensions: A list of file extensions (strings, without the leading dot).

    Returns:
        A list of full paths of found files, sorted alphabetically.
        Returns an empty list if no files are found or if directory doesn't exist.

    Raises:
        ValueError: If directory or extensions are empty/invalid.
        OSError: If underlying file system operations fail (e.g., permission issues).
    """
    if not directory:
        raise ValueError("Directory path cannot be empty.")
    if not extensions or not isinstance(extensions, list):
        raise ValueError("Extensions must be a non-empty list of strings.")
    if not all(isinstance(ext, str) for ext in extensions):
        raise ValueError("All items in extensions list must be strings.")

    logger.debug(
        f"core.core_list_files_by_extension: Listing in '{directory}' for extensions: {extensions}"
    )

    if not os.path.isdir(directory):
        logger.warning(
            f"core.core_list_files_by_extension: Directory not found: {directory}"
        )
        return []  # Consistent with glob.glob behavior for non-existent paths

    found_files: List[str] = []
    try:
        for ext in extensions:
            clean_ext = ext.lstrip(".").strip()
            if not clean_ext:
                logger.debug(
                    f"core.core_list_files_by_extension: Skipping empty extension string."
                )
                continue
            pattern = os.path.join(directory, f"*.{clean_ext}")
            logger.debug(
                f"core.core_list_files_by_extension: Searching with pattern: {pattern}"
            )
            matched_files = glob.glob(pattern)
            found_files.extend(matched_files)
        found_files.sort()
        logger.debug(
            f"core.core_list_files_by_extension: Found {len(found_files)} file(s)."
        )
        return found_files
    except OSError as e:  # Catch issues from glob or os.path.join if they occur
        logger.error(
            f"core.core_list_files_by_extension: OSError during file listing in '{directory}': {e}",
            exc_info=True,
        )
        raise  # Re-raise for API layer to handle


# --- Screen Session Interaction (Core Part) ---
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
        RuntimeError: If not on Linux or 'screen' command is not found.
    """
    if platform.system() != "Linux":
        raise RuntimeError("Screen session attachment is only supported on Linux.")

    screen_cmd = shutil.which("screen")
    if not screen_cmd:
        raise RuntimeError("'screen' command not found. Is screen installed?")

    command = [screen_cmd, "-r", screen_session_name]
    logger.debug(
        f"core.core_execute_screen_attach: Executing command: {' '.join(command)}"
    )
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
            f"core.core_execute_screen_attach: Screen attach command executed for '{screen_session_name}'. Output: {output}"
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
            logger.warning(f"core.core_execute_screen_attach: {msg}")
            return False, msg
        else:
            msg = f"Failed to execute screen attach command for '{screen_session_name}'. Error: {e.stderr or 'Unknown error'}"
            logger.error(f"core.core_execute_screen_attach: {msg}", exc_info=True)
            return False, msg
    except subprocess.TimeoutExpired:
        msg = (
            f"Timeout while trying to attach to screen session '{screen_session_name}'."
        )
        logger.error(f"core.core_execute_screen_attach: {msg}")
        return False, msg
    except FileNotFoundError:  # Should be caught by shutil.which, but safeguard
        raise RuntimeError(
            "'screen' command not found unexpectedly during execution."
        )  # Should be caught by shutil.which
