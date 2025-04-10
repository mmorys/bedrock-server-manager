# bedrock-server-manager/bedrock_server_manager/api/utils.py
"""
Provides miscellaneous utility functions supporting the API layer.

Includes functions for validating server existence and name formats, aggregating
status information across all servers, listing specific content files, and
interacting with Linux screen sessions. Functions typically return structured
dictionaries indicating success or failure.
"""

import os
import re
import glob
import logging
import shutil
import platform
import subprocess
from typing import Dict, List, Optional, Any

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
    ServerNotFoundError,
    CommandNotFoundError,
    MissingArgumentError,
    DirectoryError,
    ResourceMonitorError,
)
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.core.system import base as system_base


logger = logging.getLogger("bedrock_server_manager")


def validate_server_exist(
    server_name: str, base_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates if a server installation directory and executable exist.

    Args:
        server_name: The name of the server to validate.
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Returns:
        A dictionary: `{"status": "success", "message": "Server is valid."}` or
        `{"status": "error", "message": "Validation error description..."}`.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.debug(f"Validating existence of server '{server_name}'...")
    try:
        effective_base_dir = get_base_dir(base_dir)

        # Call the core validation function
        # It raises ServerNotFoundError if server dir or executable is missing
        server_base.validate_server(server_name, effective_base_dir)

        logger.debug(
            f"Server '{server_name}' validation successful (directory and executable exist)."
        )
        return {
            "status": "success",
            "message": f"Server '{server_name}' exists and is valid.",
        }

    except ServerNotFoundError as e:
        # Catch the specific error raised by the core function
        logger.warning(f"Server validation failed for '{server_name}': {e}")
        return {
            "status": "error",
            "message": str(e),
        }  # Return the error message from exception
    except FileOperationError as e:  # Catch error from get_base_dir
        logger.error(
            f"Configuration error preventing server validation for '{server_name}': {e}",
            exc_info=True,
        )
        # This indicates a higher-level problem, maybe return 500 upstream?
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        # Catch unexpected errors during validation
        logger.error(
            f"Unexpected error validating server '{server_name}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"An unexpected validation error occurred: {e}",
        }


def validate_server_name_format(server_name: str) -> Dict[str, str]:
    """
    Validates the format of a potential server name.

    Checks if the name contains only alphanumeric characters, hyphens, and underscores.

    Args:
        server_name: The server name string to validate.

    Returns:
        `{"status": "success"}` if the format is valid, or
        `{"status": "error", "message": "Validation error description..."}` if invalid.

    Raises:
        MissingArgumentError: If `server_name` is empty.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.debug(f"Validating server name format: '{server_name}'")
    # Regex: ^ start, [allowed chars]+ one or more, $ end
    if not re.fullmatch(r"^[a-zA-Z0-9_-]+$", server_name):
        msg = (
            "Invalid server name format. Only use letters (a-z, A-Z), "
            "numbers (0-9), hyphens (-), and underscores (_)."
        )
        logger.warning(f"Validation failed for server name '{server_name}': {msg}")
        return {"status": "error", "message": msg}
    else:
        logger.debug(f"Server name format validation successful for '{server_name}'.")
        return {"status": "success"}


def get_all_servers_status(
    base_dir: Optional[str] = None, config_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves the last known status and installed version for all detected servers.

    Scans the base directory for server folders and reads status/version info
    from each server's respective configuration file.

    Args:
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        config_dir: Optional. Base directory for server configs. Uses default if None.

    Returns:
        A dictionary: `{"status": "success", "servers": List[Dict[str, str]]}` where each inner
        dictionary contains 'name', 'status', 'version'. Returns `{"status": "error", "message": str}`
        if the base directory is invalid or errors occur reading configs.
    """
    servers_data: List[Dict[str, str]] = []
    errors_occurred = False
    error_messages = []

    logger.debug("Getting status for all detected servers...")
    try:
        effective_base_dir = get_base_dir(base_dir)
        effective_config_dir = (
            config_dir
            if config_dir is not None
            else getattr(settings, "_config_dir", None)
        )
        if not effective_config_dir:
            raise FileOperationError("Base configuration directory not set.")

        logger.debug(f"Scanning base directory: {effective_base_dir}")
        if not os.path.isdir(effective_base_dir):
            raise DirectoryError(
                f"Base directory does not exist or is not a directory: {effective_base_dir}"
            )

        # Iterate through items in base_dir
        for item_name in os.listdir(effective_base_dir):
            item_path = os.path.join(effective_base_dir, item_name)
            # Basic check: Is it a directory?
            if os.path.isdir(item_path):
                server_name = item_name  # Use directory name as server name
                logger.debug(f"Processing potential server directory: '{server_name}'")
                try:
                    # Get status and version from config using core functions
                    # These handle missing keys gracefully, returning "UNKNOWN"
                    status = server_base.get_server_status_from_config(
                        server_name, effective_config_dir
                    )
                    version = server_base.get_installed_version(
                        server_name, effective_config_dir
                    )
                    servers_data.append(
                        {"name": server_name, "status": status, "version": version}
                    )
                    logger.debug(
                        f"Server '{server_name}': Status='{status}', Version='{version}'"
                    )
                except (FileOperationError, InvalidServerNameError) as e:
                    # Log error for this specific server but continue with others
                    msg = (
                        f"Could not get status/version for server '{server_name}': {e}"
                    )
                    logger.error(msg, exc_info=True)
                    errors_occurred = True
                    error_messages.append(msg)
                except Exception as e:
                    # Catch unexpected errors for this server
                    msg = f"Unexpected error getting status/version for server '{server_name}': {e}"
                    logger.error(msg, exc_info=True)
                    errors_occurred = True
                    error_messages.append(msg)
            else:
                logger.debug(f"Skipping item (not a directory): '{item_name}'")

        if errors_occurred:
            # If errors occurred but we still got some data, return success but include errors in message
            combined_error_msg = "; ".join(error_messages)
            logger.warning(
                f"Finished getting server statuses with some errors: {combined_error_msg}"
            )
            return {
                "status": "success",  # Partial success
                "servers": servers_data,
                "message": f"Completed with errors: {combined_error_msg}",
            }
        else:
            logger.debug(
                f"Successfully retrieved status for {len(servers_data)} servers."
            )
            return {"status": "success", "servers": servers_data}

    except (FileOperationError, DirectoryError) as e:  # Catch setup errors
        logger.error(
            f"Failed to get server statuses due to configuration/directory error: {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Error accessing directories: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error retrieving server statuses: {e}", exc_info=True)
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def update_server_statuses(
    base_dir: Optional[str] = None, config_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Updates the status ('RUNNING' or 'STOPPED') in each server's configuration file
    based on the actual current running state of the process.

    Helps correct inconsistencies where a server might have crashed or been stopped
    externally, but the config file still shows it as running (or vice-versa).

    Args:
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        config_dir: Optional. Base directory for server configs. Uses default if None.

    Returns:
        A dictionary: `{"status": "success", "updated_servers": List[str]}` listing servers whose
        status was updated, or `{"status": "error", "message": str}` if a major error occurs.
        Individual server update errors are logged but don't cause a full failure.
    """
    updated_servers_list: List[str] = []
    errors_occurred = False
    error_messages = []

    logger.debug(
        "Updating server statuses in configuration files based on runtime checks..."
    )
    try:
        effective_base_dir = get_base_dir(base_dir)
        effective_config_dir = (
            config_dir
            if config_dir is not None
            else getattr(settings, "_config_dir", None)
        )
        if not effective_config_dir:
            raise FileOperationError("Base configuration directory not set.")

        logger.debug(f"Scanning base directory: {effective_base_dir}")
        if not os.path.isdir(effective_base_dir):
            raise DirectoryError(
                f"Base directory does not exist or is not a directory: {effective_base_dir}"
            )

        # Iterate through potential server directories
        for item_name in os.listdir(effective_base_dir):
            item_path = os.path.join(effective_base_dir, item_name)
            if os.path.isdir(item_path):
                server_name = item_name
                logger.debug(f"Checking status sync for server: '{server_name}'")
                try:
                    # Get current running state and config state
                    is_actually_running = system_base.is_server_running(
                        server_name, effective_base_dir
                    )
                    config_status = server_base.get_server_status_from_config(
                        server_name, effective_config_dir
                    )

                    logger.debug(
                        f"Server '{server_name}': Actual Running={is_actually_running}, Config Status='{config_status}'"
                    )

                    # Check for inconsistencies and update config if needed
                    needs_update = False
                    new_status = config_status  # Assume no change initially

                    # Case 1: Server IS running, but config says STOPPED or INSTALLED or UNKNOWN or ERROR
                    if is_actually_running and config_status in (
                        "STOPPED",
                        "INSTALLED",
                        "UNKNOWN",
                        "ERROR",
                    ):
                        needs_update = True
                        new_status = "RUNNING"
                        logger.debug(
                            f"Status mismatch for '{server_name}': Server is running, config says '{config_status}'. Updating config to '{new_status}'."
                        )
                    # Case 2: Server IS NOT running, but config indicates it should be
                    elif not is_actually_running and config_status in (
                        "RUNNING",
                        "STARTING",
                        "RESTARTING",
                        "STOPPING",
                    ):
                        needs_update = True
                        new_status = "STOPPED"  # Correct state is stopped
                        logger.info(
                            f"Status mismatch for '{server_name}': Server not running, config says '{config_status}'. Updating config to '{new_status}'."
                        )

                    # Perform the update if necessary
                    if needs_update:
                        server_base.manage_server_config(
                            server_name,
                            "status",
                            "write",
                            new_status,
                            effective_config_dir,
                        )
                        updated_servers_list.append(server_name)
                        logger.debug(
                            f"Successfully updated status for '{server_name}' to '{new_status}'."
                        )

                except (
                    CommandNotFoundError,
                    ResourceMonitorError,
                    FileOperationError,
                    InvalidServerNameError,
                ) as e:
                    # Log error for this server but continue checking others
                    msg = f"Could not update status for server '{server_name}': {e}"
                    logger.error(msg, exc_info=True)
                    errors_occurred = True
                    error_messages.append(msg)
                except Exception as e:
                    # Catch unexpected errors for this server
                    msg = f"Unexpected error updating status for server '{server_name}': {e}"
                    logger.error(msg, exc_info=True)
                    errors_occurred = True
                    error_messages.append(msg)

        # --- Final Result ---
        if errors_occurred:
            combined_error_msg = "; ".join(error_messages)
            logger.warning(
                f"Finished updating server statuses with errors: {combined_error_msg}"
            )
            return {
                "status": "error",  # Indicate overall process had issues
                "message": f"Completed with errors: {combined_error_msg}",
                "updated_servers": updated_servers_list,  # Still return servers that *were* updated
            }
        else:
            logger.debug(
                f"Server status update check completed. {len(updated_servers_list)} server(s) updated."
            )
            return {"status": "success", "updated_servers": updated_servers_list}

    except (FileOperationError, DirectoryError) as e:  # Catch setup errors
        logger.error(
            f"Failed to update server statuses due to configuration/directory error: {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Error accessing directories: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error updating server statuses: {e}", exc_info=True)
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def list_content_files(content_dir: str, extensions: List[str]) -> Dict[str, Any]:
    """
    Lists all files within a specified directory that match a list of extensions.

    Args:
        content_dir: The full path to the directory to search.
        extensions: A list of file extensions (strings, without the leading dot, e.g., ["mcworld", "mcpack"]).

    Returns:
        A dictionary: `{"status": "success", "files": List[str]}` containing full paths of found files,
        or `{"status": "error", "message": str}` if the directory is not found or other errors occur.

    Raises:
        MissingArgumentError: If `content_dir` or `extensions` is empty/None.
        TypeError: If `extensions` is not a list.
    """
    if not content_dir:
        raise MissingArgumentError("Content directory cannot be empty.")
    if not extensions:
        raise MissingArgumentError("Extensions list cannot be empty.")
    if not isinstance(extensions, list):
        raise TypeError("Extensions must be a list of strings.")

    logger.debug(
        f"Listing files in directory '{content_dir}' with extensions: {extensions}"
    )

    if not os.path.isdir(content_dir):
        msg = f"Content directory not found or is not a directory: {content_dir}"
        logger.error(msg)
        return {"status": "error", "message": msg}

    found_files: List[str] = []
    try:
        for ext in extensions:
            clean_ext = ext.lstrip(".")  # Remove leading dot if present
            if not clean_ext:
                continue  # Skip empty extensions
            pattern = os.path.join(content_dir, f"*.{clean_ext}")
            logger.debug(f"Searching with pattern: {pattern}")
            matched_files = glob.glob(pattern)
            found_files.extend(matched_files)
            logger.debug(
                f"Found {len(matched_files)} file(s) with extension '.{clean_ext}'."
            )

        if not found_files:
            logger.warning(
                f"No files found matching extensions {extensions} in directory '{content_dir}'."
            )
            # Return success with empty list, as the operation succeeded but found nothing
            return {
                "status": "success",
                "files": [],
                "message": "No matching files found.",
            }
        else:
            # Sort files alphabetically for consistent output
            found_files.sort()
            logger.debug(
                f"Found {len(found_files)} file(s) matching specified extensions in '{content_dir}'."
            )
            return {"status": "success", "files": found_files}

    except OSError as e:
        logger.error(
            f"Error accessing content directory '{content_dir}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error accessing content directory: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error listing content files in '{content_dir}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error listing files: {e}"}


def attach_to_screen_session(server_name: str) -> Dict[str, str]:
    """
    Attempts to attach the current terminal to the screen session of a running Bedrock server.

    (Linux-specific)

    Args:
        server_name: The name of the server whose screen session to attach to.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` if attachment command is executed,
        or `{"status": "error", "message": ...}` if the server isn't running, screen isn't found,
        or attaching fails. Note: Success only means the command ran; actual attachment depends
        on the environment where this function is called.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined (needed for running check).
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    if platform.system() != "Linux":
        msg = "Attaching to screen sessions is only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(f"Attempting to attach to screen session for server '{server_name}'...")
    screen_cmd = shutil.which("screen")
    if not screen_cmd:
        logger.error("'screen' command not found. Is screen installed?")
        return {
            "status": "error",
            "message": "screen command not found. Is screen installed?",
        }

    try:
        effective_base_dir = get_base_dir(None)  # Get default base dir

        # Check if server is running first
        if not system_base.is_server_running(server_name, effective_base_dir):
            msg = f"Cannot attach: Server '{server_name}' is not currently running."
            logger.warning(msg)
            return {"status": "error", "message": msg}

        screen_session_name = f"bedrock-{server_name}"
        command = [screen_cmd, "-r", screen_session_name]
        logger.debug(f"Sending server command: {' '.join(command)}")

        # Use Popen for interactive attachment, though this script won't interact.
        # Run might be sufficient just to see if it succeeds or fails.
        # For API context, success means command executed, not that user is attached.
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        # If check=True passes, command likely succeeded (though user needs interactive terminal)
        logger.info(
            f"Successfully executed attach command for screen session '{screen_session_name}'."
        )
        logger.debug(
            f"Screen attach output (may be empty): {process.stdout}{process.stderr}"
        )
        return {
            "status": "success",
            "message": f"Attach command executed for session '{screen_session_name}'. Requires interactive terminal.",
        }

    except subprocess.CalledProcessError as e:
        # Common error: screen session doesn't exist (server stopped between check and attach?)
        stderr_lower = (e.stderr or "").lower()
        if (
            "no screen session found" in stderr_lower
            or "there is no screen to be resumed" in stderr_lower
        ):
            msg = f"Failed to attach: Screen session '{screen_session_name}' not found (server may have stopped)."
            logger.warning(msg)
            return {"status": "error", "message": msg}
        else:
            msg = f"Failed to execute screen attach command for '{screen_session_name}'. Error: {e.stderr}"
            logger.error(msg, exc_info=True)
            return {"status": "error", "message": msg}
    except FileNotFoundError:  # Should be caught by shutil.which, but safeguard
        logger.error("'screen' command not found unexpectedly.")
        return {"status": "error", "message": "'screen' command not found."}
    except FileOperationError as e:  # Catch error from get_base_dir
        logger.error(
            f"Configuration error preventing screen attach for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"An unexpected error occurred attaching to screen session for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"An unexpected error occurred attaching to screen: {e}",
        }
