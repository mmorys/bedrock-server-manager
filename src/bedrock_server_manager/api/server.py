# bedrock-server-manager/bedrock_server_manager/api/server.py
"""
Provides API-level functions for managing Bedrock server instances.

This acts as an interface layer, orchestrating calls to core server management
functions (from core.server.server, core.system, etc.) and returning structured
dictionary responses indicating success or failure, suitable for use by web routes
or other higher-level application logic.
"""

import os
import logging
from typing import Dict, Optional, Any
import platform
import time
import shutil
import subprocess

# Local imports
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config.settings import settings, EXPATH
from bedrock_server_manager.utils.blocked_commands import API_COMMAND_BLACKLIST
from bedrock_server_manager.core.server import (
    server as server_base,
)  # Alias for core server functions
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
    process as system_process,
)
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
    CommandNotFoundError,
    MissingArgumentError,
    ServerNotRunningError,
    SendCommandError,
    ServerNotFoundError,
    ServerStartError,
    ServerStopError,
    InvalidInputError,
    DirectoryError,
    BlockedCommandError,
)

logger = logging.getLogger("bedrock_server_manager")


def write_server_config(
    server_name: str, key: str, value: Any, config_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Writes a key-value pair to a specific server's JSON configuration file.

    Uses `server_base.manage_server_config` for the core operation.

    Args:
        server_name: The name of the server.
        key: The configuration key string.
        value: The value to write (must be JSON serializable).
        config_dir: Optional. The base directory for server configs. Uses default if None.

    Returns:
        A dictionary: `{"status": "success"}` or `{"status": "error", "message": str}`.

    Raises:
        MissingArgumentError: If `server_name`, `key` is empty.
        InvalidServerNameError: If `server_name` is invalid (currently checks empty).
        # ValueError/TypeError might be raised by core if value isn't serializable.
        # FileOperationError might be raised by core if config dir missing.
    """
    # Input validation - raise exceptions for invalid API calls
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not key:
        raise MissingArgumentError("Configuration key cannot be empty.")
    # Value can be None or other JSON types, core function handles validation

    logger.debug(
        f"Attempting to write config for server '{server_name}': Key='{key}', Value='{value}'"
    )
    try:
        # Delegate to core function, which handles file I/O and validation
        server_base.manage_server_config(
            server_name=server_name,
            key=key,
            operation="write",
            value=value,
            config_dir=config_dir,
        )
        logger.debug(
            f"Successfully wrote config key '{key}' for server '{server_name}'."
        )
        return {
            "status": "success",
            "message": f"Configuration key '{key}' updated successfully.",
        }
    except (
        FileOperationError,
        InvalidInputError,
        InvalidServerNameError,
        MissingArgumentError,
    ) as e:  # Added MissingArgumentError
        # Catch specific known errors from the core function
        logger.error(
            f"Failed to write server config for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to write server config: {e}"}
    except Exception as e:
        # Catch unexpected errors
        logger.error(
            f"Unexpected error writing server config for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error writing server config: {e}",
        }


def start_server(
    server_name: str,
    base_dir: Optional[str] = None,
    mode: str = "direct",  # "direct" or "detached"
) -> Dict[str, Any]:
    """
    Starts the specified Bedrock server.

    Args:
        server_name: The name of the server to start.
        base_dir: Optional. The base directory for server installations. Uses config default if None.
        mode: "direct" to start server synchronously in the current process's context (or as managed by OS service).
              "detached" to launch the server as a new background process (useful for Windows user-level starts).

    Returns:
        A dictionary: {"status": "success", "message": ..., "pid": Optional[int]} or
                      {"status": "error", "message": ...}.
                      "pid" is included for "detached" mode success, representing the PID of the launcher process.

    Raises:
        MissingArgumentError, InvalidServerNameError, FileOperationError, InvalidInputError
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if mode not in ["direct", "detached"]:
        raise InvalidInputError(
            f"Invalid start mode '{mode}'. Must be 'direct' or 'detached'."
        )

    logger.info(f"API: Attempting to start server '{server_name}' in '{mode}' mode...")

    try:
        effective_base_dir = get_base_dir(base_dir)

        if server_base.check_if_server_is_running(server_name):
            logger.warning(
                f"API: Server '{server_name}' is already running. Start request (mode: {mode}) ignored."
            )
            return {
                "status": "error",
                "message": f"Server '{server_name}' is already running.",
            }

        if mode == "direct":
            logger.debug(
                f"API: Calling core server_base.start_server for '{server_name}' (direct mode)."
            )
            server_base.start_server(server_name)
            logger.info(
                f"API: Direct start for server '{server_name}' completed successfully."
            )
            return {
                "status": "success",
                "message": f"Server '{server_name}' (direct mode) started successfully.",
            }

        elif mode == "detached":

            write_server_config(server_name, "start_method", "detached")

            if platform.system() == "Windows":
                cli_command_parts = [
                    EXPATH,
                    "start-server",
                    "--server",
                    server_name,
                    "--mode",
                    "direct",
                ]
                cli_command_str_list = [os.fspath(part) for part in cli_command_parts]

                logger.info(
                    f"API: Preparing to launch detached starter for '{server_name}' with command: {' '.join(cli_command_str_list)}"
                )

                app_config_dir = settings._config_dir
                if not app_config_dir:
                    raise FileOperationError(
                        "Application configuration directory (_config_dir) not set in settings for detached start."
                    )

                launcher_pid_dir = os.path.join(app_config_dir, server_name)
                os.makedirs(launcher_pid_dir, exist_ok=True)

                launcher_pid_file_path = os.path.join(
                    launcher_pid_dir, f"bedrock_{server_name}.pid"
                )

                try:
                    launcher_pid = system_process.launch_detached_process(
                        cli_command_str_list, launcher_pid_file_path
                    )
                    logger.info(
                        f"API: Detached server starter for '{server_name}' launched with PID {launcher_pid}."
                    )
                    return {
                        "status": "success",
                        "message": (
                            f"Server '{server_name}' start initiated in detached mode "
                            f"(Launcher PID: {launcher_pid}). Check status for confirmation."
                        ),
                        "pid": launcher_pid,
                    }

                except (
                    system_process.ExecutableNotFoundError,
                    system_process.ProcessManagementError,
                    system_process.PIDFileError,
                ) as e_proc:
                    logger.error(
                        f"API: Failed to launch detached starter for '{server_name}': {e_proc}",
                        exc_info=True,
                    )
                    return {
                        "status": "error",
                        "message": f"Failed to launch detached server starter: {e_proc}",
                    }

            elif platform.system() == "Linux":
                if system_linux.check_service_exist(server_name):
                    logger.debug("API: Using systemctl to start server.")
                    systemctl_cmd_path = shutil.which("systemctl")
                    service_name = f"bedrock-{server_name}"

                    if systemctl_cmd_path:
                        try:
                            subprocess.run(
                                [systemctl_cmd_path, "--user", "start", service_name],
                                check=True,
                                capture_output=True,
                                text=True,
                            )
                            logger.info(
                                f"Successfully initiated start for systemd service '{service_name}'."
                            )
                            return {
                                "status": "success",
                                "message": f"Server '{server_name}' (detached mode) started successfully.",
                            }

                        except FileNotFoundError:
                            logger.error("'systemctl' command not found unexpectedly.")
                        except subprocess.CalledProcessError as e:
                            logger.warning(
                                f"Starting via systemctl failed: {e}. stderr: {e.stderr}",
                                exc_info=True,
                            )
                    else:
                        logger.warning(
                            "'systemctl' command not found. Cannot use systemd method."
                        )
                else:
                    logger.warning(
                        f"Service file for '{server_name}' doesn't exist. Fallback to direct mode..."
                    )
                    server_base.start_server(server_name)
                    logger.info(
                        f"API: Direct start for server '{server_name}' completed successfully."
                    )
                    return {
                        "status": "success",
                        "message": f"Server '{server_name}' (direct mode) started successfully.",
                    }

        return {
            "status": "error",
            "message": "Internal error: Invalid mode fell through.",
        }

    except (
        ServerNotFoundError,
        ServerStartError,
        CommandNotFoundError,
        MissingArgumentError,
    ) as e:
        logger.error(
            f"API: Failed to start server '{server_name}' (mode: {mode}): {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Failed to start server '{server_name}': {e}",
        }
    except FileOperationError as e:
        logger.error(
            f"API: Configuration or FileOperation error for server '{server_name}' (mode: {mode}): {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Configuration or file operation error: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error starting server '{server_name}' (mode: {mode}): {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error starting server '{server_name}': {e}",
        }


def stop_server(
    server_name: str, base_dir: Optional[str] = None, mode: str = "direct"
) -> Dict[str, str]:
    """
    Stops the specified Bedrock server using the core server functions.

    Args:
        server_name: The name of the server to stop.
        base_dir: Optional. The base directory for server installations. Uses config default if None.
        mode: "direct" or "detached". On Linux, "detached" uses systemd if available.

    Returns:
        A dictionary: {"status": "success", "message": ...} or {"status": "error", "message": ...}.

    Raises:
        MissingArgumentError, InvalidServerNameError, FileOperationError
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    if mode not in ["direct", "detached"]:
        raise InvalidInputError(
            f"Invalid stop mode '{mode}'. Must be 'direct' or 'detached'."
        )

    if platform.system() == "Windows":
        mode = "direct"  # Normalize mode for Windows

    logger.info(f"Attempting to stop server '{server_name}'...")

    try:
        if mode == "direct":
            effective_base_dir = get_base_dir(base_dir)

            if not server_base.check_if_server_is_running(server_name):
                logger.warning(
                    f"Server '{server_name}' is not running. Stop request ignored."
                )
                return {
                    "status": "success",
                    "message": f"Server '{server_name}' was already stopped.",
                }

            server_base.stop_server(server_name)
            logger.info(f"Server '{server_name}' stopped successfully.")
            return {
                "status": "success",
                "message": f"Server '{server_name}' stopped successfully.",
            }

        elif mode == "detached":
            if platform.system() == "Linux":
                if system_linux.check_service_exist(server_name):
                    logger.debug(
                        f"Attempting to stop server '{server_name}' using systemd..."
                    )

                    systemctl_cmd_path = shutil.which("systemctl")
                    service_name = f"bedrock-{server_name}"
                    service_file_path = os.path.join(
                        os.path.expanduser("~/.config/systemd/user/"),
                        f"{service_name}.service",
                    )

                    if systemctl_cmd_path and os.path.exists(service_file_path):
                        try:
                            subprocess.run(
                                [systemctl_cmd_path, "--user", "stop", service_name],
                                check=True,
                                capture_output=True,
                                text=True,
                            )
                            logger.info(
                                f"Successfully initiated stop for systemd service '{service_name}'."
                            )
                            return {
                                "status": "success",
                                "message": f"Server '{server_name}' stopped successfully.",
                            }
                        except FileNotFoundError:
                            logger.error("'systemctl' command not found unexpectedly.")
                        except subprocess.CalledProcessError as e:
                            logger.warning(
                                f"Stopping via systemctl failed: {e}. stderr: {e.stderr}",
                                exc_info=True,
                            )

                    logger.debug(
                        "Systemctl not found or service file doesn't exist. Will try stopping directly."
                    )
                    server_base.stop_server(server_name)
                    logger.info(f"Server '{server_name}' stopped successfully.")
                    return {
                        "status": "success",
                        "message": f"Server '{server_name}' stopped successfully.",
                    }
                else:
                    logger.warning(
                        f"Service file for '{server_name}' doesn't exist. Will try stopping directly."
                    )
                    server_base.stop_server(server_name)
                    logger.info(f"Server '{server_name}' stopped successfully.")
                    return {
                        "status": "success",
                        "message": f"Server '{server_name}' stopped successfully.",
                    }

            elif platform.system() == "Windows":
                logger.debug(
                    f"Attempting to stop server '{server_name}' using direct stop method (Windows)."
                )
                server_base.stop_server(server_name)
                logger.info(f"Server '{server_name}' stopped successfully.")
                return {
                    "status": "success",
                    "message": f"Server '{server_name}' stopped successfully.",
                }

    except (
        ServerNotFoundError,
        ServerStopError,
        SendCommandError,
        CommandNotFoundError,
        MissingArgumentError,
    ) as e:
        logger.error(f"Failed to stop server '{server_name}': {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to stop server '{server_name}': {e}",
        }
    except FileOperationError as e:
        logger.error(
            f"Configuration error preventing server stop for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Configuration error: {e}",
        }
    except Exception as e:
        logger.error(
            f"Unexpected error stopping server '{server_name}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error stopping server '{server_name}': {e}",
        }


def restart_server(
    server_name: str, base_dir: Optional[str] = None, send_message: bool = True
) -> Dict[str, str]:
    """
    Restarts the specified Bedrock server.

    Stops the server (sending an optional warning message first) and then starts it again.
    If the server was not running, it simply starts it.

    Args:
        server_name: The name of the server to restart.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        send_message: If True, attempt to send "say Restarting..." to the server before stopping.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined or essential settings are missing.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"Initiating restart for server '{server_name}'. Send message: {send_message}"
    )
    try:
        effective_base_dir = get_base_dir(base_dir)  # Used for initial check

        # Use core check_if_server_is_running
        is_running = server_base.check_if_server_is_running(server_name)

        if not is_running:
            logger.info(
                f"Server '{server_name}' was not running. Attempting to start..."
            )
            # Just call start_server API function (which itself calls core start_server)
            start_result = start_server(server_name, effective_base_dir, "detached")
            if start_result.get("status") == "success":
                start_result["message"] = (
                    f"Server '{server_name}' was not running and was started."
                )
            return start_result
        else:
            logger.info(
                f"Server '{server_name}' is running. Proceeding with stop/start cycle."
            )

            # --- Send Warning Message (Optional) ---
            if send_message:
                logger.debug(
                    f"Attempting to send restart warning message to server '{server_name}'."
                )
                try:
                    # Use core standalone send_server_command
                    server_base.send_server_command(
                        server_name, "say Server restarting in 10 seconds..."
                    )
                    logger.info(
                        f"Sent restart warning to server '{server_name}'. Waiting 10s..."
                    )
                    time.sleep(10)  # Give players time to see message
                except (
                    ServerNotFoundError,
                    SendCommandError,
                    ServerNotRunningError,  # Should not happen if is_running was true, but possible race
                    CommandNotFoundError,
                    MissingArgumentError,  # from send_server_command
                ) as msg_err:
                    logger.warning(
                        f"Could not send restart warning message to server '{server_name}': {msg_err}. Proceeding with restart.",
                        exc_info=True,
                    )
                except Exception as msg_err:  # Catch other unexpected errors
                    logger.warning(
                        f"Unexpected error sending restart warning message to server '{server_name}': {msg_err}. Proceeding with restart.",
                        exc_info=True,
                    )

            # --- Stop Server ---
            logger.debug(f"Stopping server '{server_name}' for restart...")
            stop_result = stop_server(
                server_name, effective_base_dir
            )  # Calls API stop_server
            if stop_result.get("status") == "error":
                logger.error(
                    f"Restart failed: Could not stop server '{server_name}'. Error: {stop_result.get('message')}"
                )
                stop_result["message"] = (
                    f"Restart failed during stop phase: {stop_result.get('message')}"
                )
                return stop_result

            logger.debug("Waiting briefly before restarting...")
            time.sleep(3)

            # --- Start Server ---
            logger.debug(f"Starting server '{server_name}' after stop...")
            start_result = start_server(
                server_name, effective_base_dir, "detached"
            )  # Calls API start_server
            if start_result.get("status") == "error":
                logger.error(
                    f"Restart failed: Could not start server '{server_name}' after stopping. Error: {start_result.get('message')}"
                )
                start_result["message"] = (
                    f"Restart failed during start phase: {start_result.get('message')}"
                )
                return start_result

            logger.info(f"Server '{server_name}' restarted successfully.")
            return {
                "status": "success",
                "message": f"Server '{server_name}' restarted successfully.",
            }

    except (
        FileOperationError
    ) as e:  # Catch error from get_base_dir or core functions if settings missing
        logger.error(
            f"Configuration error preventing server restart for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error during restart process for server '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error during restart: {e}"}


def send_command(
    server_name: str,
    command: str,
    base_dir: Optional[
        str
    ] = None,  # base_dir not directly used by core send_server_command
) -> Dict[str, str]:
    """
    Sends a command to a running Bedrock server instance using core functions.
    Certain commands defined in the `API_COMMAND_BLACKLIST` setting may be blocked.

    Args:
        server_name: The name of the target server.
        command: The command string to send to the server console.
        base_dir: Optional. Base directory for server installations. (Not directly used by core send_server_command but kept for API consistency if needed elsewhere).

    Returns:
        A dictionary: `{"status": "success", "message": ...}`.
        (Errors are now raised as exceptions).

    Raises:
        MissingArgumentError: If `server_name` or `command` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        BlockedCommandError: If the command is forbidden by the blacklist configuration.
        FileOperationError: If `base_dir` cannot be determined (if used) or essential settings missing for core.
        ServerNotFoundError: If the server executable is missing (checked by core).
        ServerNotRunningError: If the target server process isn't running or reachable.
        SendCommandError: If sending the command via the OS mechanism fails.
        CommandNotFoundError: If required OS commands (e.g., screen) are missing.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not command:
        raise MissingArgumentError("Command cannot be empty.")

    command_clean = command.strip()
    if not command_clean:
        raise MissingArgumentError(
            "Command cannot be empty after stripping whitespace."
        )

    logger.info(
        f"Attempting to send command to server '{server_name}': '{command_clean}'"
    )

    # --- Blacklist Check ---
    blacklist = API_COMMAND_BLACKLIST  # This is from settings
    # Ensure API_COMMAND_BLACKLIST is actually loaded in settings
    # For safety, could default to an empty list if not found, or raise specific config error.
    if not isinstance(blacklist, list):
        logger.warning(
            f"API_COMMAND_BLACKLIST setting is not a list or not found. Defaulting to empty list for safety."
        )
        blacklist = []  # Or raise ConfigurationError

    command_check = command_clean.lower()
    if command_check.startswith("/"):
        command_check = command_check[1:]

    for blocked_cmd_prefix in blacklist:
        if isinstance(blocked_cmd_prefix, str) and command_check.startswith(
            blocked_cmd_prefix.lower()
        ):
            error_msg = f"Command '{command_clean}' is blocked by configuration (matches rule: '{blocked_cmd_prefix}')."
            logger.warning(
                f"Blocked command attempt for server '{server_name}': {error_msg}"
            )
            raise BlockedCommandError(error_msg)
    # --- End Blacklist Check ---

    try:
        # effective_base_dir = get_base_dir(base_dir) # Not strictly needed if send_server_command handles its paths

        # Call the standalone send_server_command from core.server.server
        server_base.send_server_command(server_name, command_clean)

        logger.info(
            f"Command '{command_clean}' sent successfully to server '{server_name}'."
        )
        return {
            "status": "success",
            "message": f"Command '{command_clean}' sent successfully.",
        }

    except (
        ServerNotFoundError,
        ServerNotRunningError,
        SendCommandError,
        CommandNotFoundError,
        MissingArgumentError,  # From send_server_command if args are empty
        FileOperationError,  # From send_server_command if settings are missing
        InvalidServerNameError,  # From send_server_command
    ) as e:
        logger.error(
            f"Failed to send command to server '{server_name}': {e}", exc_info=True
        )
        raise  # Re-raise the original exception to be handled by route

    except Exception as e:
        logger.error(
            f"Unexpected error sending command to server '{server_name}': {e}",
            exc_info=True,
        )
        # Re-raise as a generic error or a specific internal error type
        raise RuntimeError(f"Unexpected error sending command: {e}") from e


def delete_server_data(
    server_name: str,
    base_dir: Optional[str] = None,
    config_dir: Optional[str] = None,  # config_dir passed to core delete_server_data
    stop_if_running: bool = True,
) -> Dict[str, str]:
    """
    Deletes all data associated with a Bedrock server (installation, config, backups).

    Optionally stops the server first if it is running.

    Args:
        server_name: The name of the server to delete.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        config_dir: Optional. Base directory for server configs. Uses default if None.
        stop_if_running: If True (default), attempt to stop the server before deleting data.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If essential settings (BASE_DIR, BACKUP_DIR, _config_dir for core) are missing.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"!!! Initiating deletion of ALL data for server '{server_name}'. Stop if running: {stop_if_running} !!!"
    )
    try:
        effective_base_dir = get_base_dir(base_dir)
        # Ensure backup dir setting exists for core delete function (core already checks _config_dir)
        if not settings.get("BACKUP_DIR"):
            raise FileOperationError(
                "BACKUP_DIR setting missing in application configuration."
            )

        # --- Stop Server (Optional) ---
        if stop_if_running:
            logger.debug(
                f"Checking if server '{server_name}' needs to be stopped before deletion..."
            )
            try:
                # Use core check_if_server_is_running
                if server_base.check_if_server_is_running(server_name):
                    logger.info(
                        f"Server '{server_name}' is running. Stopping before deletion..."
                    )
                    # Call API stop_server function (which calls core stop_server)
                    stop_result = stop_server(server_name, effective_base_dir)
                    if stop_result.get("status") == "error":
                        error_msg = f"Failed to stop server '{server_name}' before deletion: {stop_result.get('message')}. Deletion aborted."
                        logger.error(error_msg)
                        return {"status": "error", "message": error_msg}
                    logger.info(f"Server '{server_name}' stopped.")
                else:
                    logger.debug(
                        f"Server '{server_name}' is not running. No stop needed."
                    )
            except (
                Exception
            ) as e:  # Catch unexpected errors during the stop check/attempt
                error_msg = f"Error occurred while stopping server '{server_name}' before deletion: {e}. Deletion aborted."
                logger.error(error_msg, exc_info=True)
                return {"status": "error", "message": error_msg}

        # --- Core Deletion Operation ---
        logger.debug(f"Proceeding with deletion of data for server '{server_name}'...")
        # Call core delete function, passing effective_base_dir and optional config_dir
        server_base.delete_server_data(
            server_name, effective_base_dir, config_dir=config_dir
        )
        logger.info(f"Successfully deleted data for server '{server_name}'.")
        return {
            "status": "success",
            "message": f"All data for server '{server_name}' deleted successfully.",
        }

    except (DirectoryError, InvalidServerNameError) as e:
        logger.error(
            f"Failed to delete server data for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to delete server data: {e}"}
    except (
        FileOperationError
    ) as e:  # Catches config/base_dir errors from get_base_dir or core
        logger.error(
            f"Configuration error preventing server deletion for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error deleting server data for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error deleting server data: {e}",
        }
