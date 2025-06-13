# bedrock_server_manager/api/server.py
"""
Provides API-level functions for managing Bedrock server instances.

This acts as an interface layer, instantiating the BedrockServer class to perform
core operations and returning structured dictionary responses suitable for use by web
routes or other higher-level application logic.
"""

import os
import logging
from typing import Dict, Any
import platform
import time
import shutil
import subprocess

# Local imports
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.config.const import EXPATH
from bedrock_server_manager.config.blocked_commands import API_COMMAND_BLACKLIST
from bedrock_server_manager.core.system import process as system_process
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    FileError,
    UserInputError,
    ServerError,
    BlockedCommandError,
    MissingArgumentError,
)

logger = logging.getLogger(__name__)


def write_server_config(server_name: str, key: str, value: Any) -> Dict[str, Any]:
    """
    Writes a key-value pair to a specific server's JSON configuration file.

    This is a thin wrapper around the BedrockServer's config management.

    Args:
        server_name: The name of the server.
        key: The configuration key string.
        value: The value to write (must be JSON serializable).

    Returns:
        A dictionary: `{"status": "success"}` or `{"status": "error", "message": str}`.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not key:
        raise MissingArgumentError("Configuration key cannot be empty.")

    logger.debug(
        f"API: Attempting to write config for server '{server_name}': Key='{key}', Value='{value}'"
    )
    try:
        server = BedrockServer(server_name)

        server.set_custom_config_value(key, value)
        logger.debug(
            f"API: Successfully wrote config key '{key}' for server '{server_name}'."
        )
        return {
            "status": "success",
            "message": f"Configuration key '{key}' updated successfully.",
        }
    except BSMError as e:
        logger.error(
            f"API: Failed to write server config for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to write server config: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error writing server config for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error writing server config: {e}",
        }


def _handle_autoupdate(server: "BedrockServer") -> Dict[str, Any]:
    """
    Handles the server autoupdate process if enabled.

    Args:
        server: The BedrockServer instance.

    Returns:
        A dictionary indicating the outcome.
        {"status": "success"} if the process should continue (even if update fails with a known error).
        {"status": "error", "message": ...} if an unexpected error occurs that should halt the server start.
    """
    try:
        # Determine if autoupdate is enabled for the start mode
        autoupdate = server.get_custom_config_value("autoupdate")
        if not autoupdate:
            return {"status": "success"}  # Autoupdate is disabled, continue normally.

        logger.info(
            f"API: Autoupdate enabled for server '{server.server_name}'. Checking for updates..."
        )
        target_version = server.get_target_version()
        server.install_or_update(target_version)
        logger.info(
            f"API: Autoupdate check completed for server '{server.server_name}'."
        )

    except BSMError as e:  # Catch specific, non-critical exceptions
        logger.error(
            f"API: Autoupdate failed for server '{server.server_name}'. Continuing with start.",
            exc_info=True,
        )
        # Non-fatal error, we can still attempt to start the server.
        return {"status": "success"}

    except Exception as e:  # Catch unexpected, critical exceptions
        logger.error(
            f"API: Unexpected error during autoupdate for server '{server.server_name}': {e}",
            exc_info=True,
        )
        # This is a fatal error, we should not attempt to start the server.
        return {
            "status": "error",
            "message": f"Unexpected error during autoupdate: {e}",
        }

    return {"status": "success"}


def start_server(
    server_name: str,
    mode: str = "direct",
) -> Dict[str, Any]:
    """
    Starts the specified Bedrock server.

    Args:
        server_name: The name of the server to start.
        mode: "direct" to start server synchronously (blocking on Windows, screen on Linux).
              "detached" to launch as a new background process (Windows) or use systemd (Linux).

    Returns:
        A dictionary: {"status": "success", "message": ...} or {"status": "error", "message": ...}.
    """
    mode = mode.lower()

    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if mode not in ["direct", "detached"]:
        raise UserInputError(
            f"Invalid start mode '{mode}'. Must be 'direct' or 'detached'."
        )

    logger.info(f"API: Attempting to start server '{server_name}' in '{mode}' mode...")

    try:
        server = BedrockServer(server_name)
        server.start_method = mode  # Pass mode to the server object

        # --- Call the new autoupdate handler ---
        update_result = _handle_autoupdate(server)
        if update_result["status"] == "error":
            return update_result  # Propagate critical update errors and stop

        if server.is_running():
            logger.warning(
                f"API: Server '{server_name}' is already running. Start request (mode: {mode}) ignored."
            )
            return {
                "status": "error",
                "message": f"Server '{server_name}' is already running.",
            }

        # --- Direct Mode ---
        # On Linux, this uses 'screen'. On Windows, this is a blocking call.
        if mode == "direct":
            logger.debug(
                f"API: Calling server.start() for '{server_name}' (direct mode)."
            )
            server.start()
            logger.info(f"API: Direct start for server '{server_name}' completed.")
            return {
                "status": "success",
                "message": f"Server '{server_name}' (direct mode) process finished.",
            }

        # --- Detached Mode ---
        elif mode == "detached":
            server.set_custom_config_value("start_method", "detached")

            if platform.system() == "Windows":
                # Launch a new instance of the manager to run the blocking start command.
                cli_command_parts = [
                    EXPATH,
                    "server",
                    "start",
                    "--server",
                    server_name,
                    "--mode",
                    "direct",
                ]
                cli_command_str_list = [os.fspath(part) for part in cli_command_parts]

                logger.info(
                    f"API: Launching detached starter for '{server_name}' with command: {' '.join(cli_command_str_list)}"
                )

                launcher_pid_file_path = server.get_pid_file_path()
                os.makedirs(os.path.dirname(launcher_pid_file_path), exist_ok=True)

                launcher_pid = system_process.launch_detached_process(
                    cli_command_str_list, launcher_pid_file_path
                )
                logger.info(
                    f"API: Detached server starter for '{server_name}' launched with PID {launcher_pid}."
                )
                return {
                    "status": "success",
                    "message": f"Server '{server_name}' start initiated in detached mode (Launcher PID: {launcher_pid}).",
                    "pid": launcher_pid,
                }

            elif platform.system() == "Linux":
                # Use systemd if the service file exists.
                if server.check_systemd_service_file_exists():
                    logger.debug(
                        f"API: Using systemctl to start server '{server_name}'."
                    )
                    systemctl_cmd_path = shutil.which("systemctl")
                    service_name = f"bedrock-{server.server_name}"

                    if systemctl_cmd_path:
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
                            "message": f"Server '{server_name}' started via systemd.",
                        }
                    else:
                        logger.warning(
                            "'systemctl' command not found, falling back to screen."
                        )

                # Fallback for non-systemd or if systemctl is missing. 'screen' is inherently detached.
                logger.info(
                    f"API: Starting server '{server_name}' in detached mode via screen."
                )
                server.start()
                return {
                    "status": "success",
                    "message": f"Server '{server_name}' started successfully in a screen session.",
                }

        return {
            "status": "error",
            "message": "Internal error: Invalid mode fell through.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to start server '{server_name}' (mode: {mode}): {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Failed to start server '{server_name}': {e}",
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


def stop_server(server_name: str, mode: str = "direct") -> Dict[str, str]:
    """
    Stops the specified Bedrock server.

    Args:
        server_name: The name of the server to stop.
        mode: "direct" or "detached". On Linux, "detached" uses systemd if available.

    Returns:
        A dictionary: {"status": "success", "message": ...} or {"status": "error", "message": ...}.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    mode = mode.lower()
    if platform.system() == "Windows":
        mode = "direct"

    logger.info(f"API: Attempting to stop server '{server_name}' (mode: {mode})...")

    try:
        server = BedrockServer(server_name)
        server.set_custom_config_value("start_method", "")

        if not server.is_running():
            logger.warning(
                f"API: Server '{server_name}' is not running. Stop request ignored."
            )
            server.set_status_in_config("STOPPED")
            return {
                "status": "success",
                "message": f"Server '{server_name}' was already stopped.",
            }

        # --- Systemd Mode for Linux ---
        if (
            platform.system() == "Linux"
            and server.check_systemd_service_file_exists()
            and server.is_systemd_service_active()
        ):
            logger.debug(
                f"API: Attempting to stop server '{server_name}' using systemd..."
            )
            systemctl_cmd_path = shutil.which("systemctl")
            service_name = f"bedrock-{server.server_name}"
            try:
                subprocess.run(
                    [systemctl_cmd_path, "--user", "stop", service_name],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logger.info(
                    f"API: Successfully initiated stop for systemd service '{service_name}'."
                )
                return {
                    "status": "success",
                    "message": f"Server '{server_name}' stop initiated via systemd.",
                }
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                logger.warning(
                    f"API: Stopping via systemctl failed: {e}. Falling back to direct stop.",
                    exc_info=True,
                )
                # Fall through to direct stop method

        # --- Direct Stop (all platforms, and Linux fallback) ---
        try:
            server.send_command("say Stopping server in 10 seconds...")
            time.sleep(10)
        except BSMError as e:
            logger.warning(
                f"API: Could not send shutdown warning to '{server_name}': {e}. Proceeding with stop."
            )

        server.stop()
        logger.info(f"API: Server '{server_name}' stopped successfully.")
        return {
            "status": "success",
            "message": f"Server '{server_name}' stopped successfully.",
        }

    except BSMError as e:
        logger.error(f"API: Failed to stop server '{server_name}': {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to stop server '{server_name}': {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error stopping server '{server_name}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error stopping server '{server_name}': {e}",
        }


def restart_server(server_name: str, send_message: bool = True) -> Dict[str, str]:
    """
    Restarts the specified Bedrock server by orchestrating stop and start calls.

    Args:
        server_name: The name of the server to restart.
        send_message: If True, attempts to send "say Restarting..." to the server before stopping.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"API: Initiating restart for server '{server_name}'. Send message: {send_message}"
    )

    try:
        server = BedrockServer(server_name)
        is_running = server.is_running()

        if not is_running:
            logger.info(
                f"API: Server '{server_name}' was not running. Attempting to start..."
            )
            start_result = start_server(server_name, mode="detached")
            if start_result.get("status") == "success":
                start_result["message"] = (
                    f"Server '{server_name}' was not running and has been started."
                )
            return start_result

        logger.info(
            f"API: Server '{server_name}' is running. Proceeding with stop/start cycle."
        )

        if send_message:
            try:
                server.send_command("say Restarting server...")
            except BSMError as e:
                logger.warning(
                    f"API: Failed to send restart warning to '{server_name}': {e}"
                )

        stop_result = stop_server(server_name)
        if stop_result.get("status") == "error":
            stop_result["message"] = (
                f"Restart failed during stop phase: {stop_result.get('message')}"
            )
            return stop_result

        logger.debug("API: Waiting briefly before restarting...")
        time.sleep(3)

        start_result = start_server(server_name, mode="detached")
        if start_result.get("status") == "error":
            start_result["message"] = (
                f"Restart failed during start phase: {start_result.get('message')}"
            )
            return start_result

        logger.info(f"API: Server '{server_name}' restarted successfully.")
        return {
            "status": "success",
            "message": f"Server '{server_name}' restarted successfully.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to restart server '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Restart failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error during restart for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error during restart: {e}"}


def send_command(server_name: str, command: str) -> Dict[str, str]:
    """
    Sends a command to a running Bedrock server instance.

    Args:
        server_name: The name of the target server.
        command: The command string to send to the server console.

    Returns:
        A dictionary `{"status": "success", "message": "Command sent successfully."}` on success.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        MissingArgumentError: If `command` is empty.
        BlockedCommandError: If the command is in the API_COMMAND_BLACKLIST.
        BSMError: For other application-specific errors during command sending.
        ServerError: For unexpected errors.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not command or not command.strip():
        raise MissingArgumentError("Command cannot be empty.")

    command_clean = command.strip()
    logger.info(
        f"API: Attempting to send command to server '{server_name}': '{command_clean}'"
    )

    # --- Blacklist Check ---
    blacklist = API_COMMAND_BLACKLIST or []
    command_check = command_clean.lower().lstrip("/")
    for blocked_cmd_prefix in blacklist:
        if isinstance(blocked_cmd_prefix, str) and command_check.startswith(
            blocked_cmd_prefix.lower()
        ):
            error_msg = f"Command '{command_clean}' is blocked by configuration."
            logger.warning(
                f"API: Blocked command attempt for '{server_name}': {error_msg}"
            )
            raise BlockedCommandError(error_msg)

    try:
        server = BedrockServer(server_name)
        server.send_command(command_clean)

        logger.info(
            f"API: Command '{command_clean}' sent successfully to server '{server_name}'."
        )
        return {
            "status": "success",
            "message": f"Command '{command_clean}' sent successfully.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to send command to server '{server_name}': {e}", exc_info=True
        )
        raise  # Re-raise to be handled by the route
    except Exception as e:
        logger.error(
            f"API: Unexpected error sending command to '{server_name}': {e}",
            exc_info=True,
        )
        raise ServerError(f"Unexpected error sending command: {e}") from e


def delete_server_data(
    server_name: str, stop_if_running: bool = True
) -> Dict[str, str]:
    """
    Deletes all data associated with a Bedrock server (installation, config, backups).

    Args:
        server_name: The name of the server to delete.
        stop_if_running: If True, attempt to stop the server before deleting data.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.warning(
        f"API: !!! Initiating deletion of ALL data for server '{server_name}'. Stop if running: {stop_if_running} !!!"
    )

    try:
        server = BedrockServer(server_name)

        if stop_if_running and server.is_running():
            logger.info(
                f"API: Server '{server_name}' is running. Stopping before deletion..."
            )
            try:
                server.send_command("say WARNING: Server is being deleted permanently!")
            except Exception as e:
                logger.warning(
                    f"API: Could not send deletion warning to '{server_name}': {e}"
                )

            stop_result = stop_server(server_name)
            if stop_result.get("status") == "error":
                error_msg = f"Failed to stop server '{server_name}' before deletion: {stop_result.get('message')}. Deletion aborted."
                logger.error(error_msg)
                return {"status": "error", "message": error_msg}

            time.sleep(3)  # Allow time for the server to stop gracefully
            logger.info(f"API: Server '{server_name}' stopped.")

        logger.debug(
            f"API: Proceeding with deletion of data for server '{server_name}'..."
        )
        server.delete_all_data()
        logger.info(f"API: Successfully deleted all data for server '{server_name}'.")
        return {
            "status": "success",
            "message": f"All data for server '{server_name}' deleted successfully.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to delete server data for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to delete server data: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error deleting server data for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error deleting server data: {e}",
        }
