# bedrock_server_manager/api/server.py
"""Provides API functions for managing Bedrock server instances.

This module acts as the primary interface layer for server operations. It uses
the `BedrockServer` core class to perform actions like starting, stopping, and
configuring servers. It returns structured dictionary responses suitable for
use by web routes, CLI commands, or other application logic. It also initializes
and manages the plugin system.
"""

import os
import logging
from typing import Dict, Any
import platform
import time
import shutil
import subprocess

# Plugin system imports to bridge API functionality.
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
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


@plugin_method("write_server_config")
def write_server_config(server_name: str, key: str, value: Any) -> Dict[str, Any]:
    """Writes a key-value pair to a server's custom JSON configuration.

    Args:
        server_name: The name of the server.
        key: The configuration key to write.
        value: The value to associate with the key.

    Returns:
        A dictionary with the operation status and a message.
        On success: `{"status": "success", "message": "..."}`.
        On error: `{"status": "error", "message": "..."}`.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        MissingArgumentError: If `key` is not provided.
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


@plugin_method("start_server")
def start_server(
    server_name: str,
    mode: str = "direct",
) -> Dict[str, Any]:
    """Starts the specified Bedrock server.

    Autoupdating (if enabled by a plugin) is handled via the 'before_server_start'
    plugin event. This function manages platform-specific start methods.
    - 'direct': Runs the server in the current process (blocks until server stops).
    - 'detached': Starts the server in the background. On Linux, it uses
      systemd if a service file is present. Otherwise (and on all other
      platforms like Windows), it launches a new, independent background process.

    Args:
        server_name: The name of the server to start.
        mode: The start mode, either 'direct' or 'detached'. Defaults to 'direct'.

    Returns:
        A dictionary with the operation status and a message.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        UserInputError: If `mode` is invalid.
    """
    mode = mode.lower()

    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if mode not in ["direct", "detached"]:
        raise UserInputError(
            f"Invalid start mode '{mode}'. Must be 'direct' or 'detached'."
        )

    # --- Plugin Hook ---
    plugin_manager.trigger_guarded_event(
        "before_server_start", server_name=server_name, mode=mode
    )

    logger.info(f"API: Attempting to start server '{server_name}' in '{mode}' mode...")
    result = {}
    try:
        server = BedrockServer(server_name)
        server.start_method = mode

        if server.is_running():
            logger.warning(
                f"API: Server '{server_name}' is already running. Start request ignored."
            )
            return {
                "status": "error",
                "message": f"Server '{server_name}' is already running.",
            }

        if mode == "direct":
            logger.debug(
                f"API: Calling server.start() for '{server_name}' (direct mode)."
            )
            server.start()  # This is a blocking call.
            logger.info(f"API: Direct start for server '{server_name}' completed.")
            result = {
                "status": "success",
                "message": f"Server '{server_name}' (direct mode) process finished.",
            }
            return result

        elif mode == "detached":
            server.set_custom_config_value("start_method", "detached")

            # --- Linux/systemd Detached Start (Preferred method on Linux) ---
            if (
                platform.system() == "Linux"
                and server.check_systemd_service_file_exists()
            ):
                logger.debug(f"API: Using systemctl to start server '{server_name}'.")
                systemctl_cmd_path = shutil.which("systemctl")
                if systemctl_cmd_path:
                    service_name = f"bedrock-{server.server_name}"
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
                            "message": f"Server '{server_name}' started via systemd.",
                        }
                    except subprocess.CalledProcessError as e:
                        logger.warning(
                            f"systemd service '{service_name}' failed to start: {e.stderr.strip()}. "
                            "Falling back to generic detached process."
                        )
                else:
                    logger.warning(
                        "'systemctl' command not found, falling back to generic detached process."
                    )

            # --- Generic Detached Start (Fallback for Linux, Default for Windows/Other) ---
            logger.info(
                f"API: Starting server '{server_name}' using generic detached process launcher."
            )
            cli_command_parts = [
                EXPATH,
                "server",
                "start",
                "--server",
                server_name,
                "--mode",
                "direct",  # The detached process runs the server directly
            ]
            cli_command_str_list = [os.fspath(part) for part in cli_command_parts]
            launcher_pid_file_path = system_process.get_bedrock_launcher_pid_file_path(
                server.server_name,
                server.server_config_dir,  # Use BedrockServer instance properties
            )

            launcher_pid = system_process.launch_detached_process(
                cli_command_str_list,
                launcher_pid_file_path,  # Pass the launcher PID file path
            )
            logger.info(
                f"API: Detached server starter for '{server_name}' launched with PID {launcher_pid}."
            )
            result = {
                "status": "success",
                "message": f"Server '{server_name}' start initiated in detached mode (Launcher PID: {launcher_pid}).",
                "pid": launcher_pid,
            }
            return result

        # This should not be reachable.
        result = {
            "status": "error",
            "message": "Internal error: Invalid mode fell through.",
        }
        return result

    except BSMError as e:
        logger.error(f"API: Failed to start server '{server_name}': {e}", exc_info=True)
        result = {
            "status": "error",
            "message": f"Failed to start server '{server_name}': {e}",
        }
        return result
    except Exception as e:
        logger.error(
            f"API: Unexpected error starting server '{server_name}': {e}", exc_info=True
        )
        result = {
            "status": "error",
            "message": f"Unexpected error starting server '{server_name}': {e}",
        }
        return result
    finally:
        # --- Plugin Hook ---
        plugin_manager.trigger_guarded_event(
            "after_server_start", server_name=server_name, result=result
        )


@plugin_method("stop_server")
def stop_server(server_name: str, mode: str = "direct") -> Dict[str, str]:
    """Stops the specified Bedrock server.

    On Linux, it will attempt to use systemd to stop the service if it is
    active. Otherwise, it performs a direct stop by sending commands and
    terminating the process. On Windows, it always uses the direct method.

    Args:
        server_name: The name of the server to stop.
        mode: The stop mode (primarily for consistency, logic adapts).
            Defaults to "direct".

    Returns:
        A dictionary with the operation status and a message.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    mode = mode.lower()
    if platform.system() == "Windows":
        mode = "direct"  # Windows only supports direct stop logic.

    # --- Plugin Hook ---
    plugin_manager.trigger_guarded_event(
        "before_server_stop", server_name=server_name, mode=mode
    )

    logger.info(f"API: Attempting to stop server '{server_name}' (mode: {mode})...")
    result = {}
    try:
        server = BedrockServer(server_name)
        server.set_custom_config_value("start_method", "")

        if not server.is_running():
            logger.warning(
                f"API: Server '{server_name}' is not running. Stop request ignored."
            )
            server.set_status_in_config("STOPPED")
            result = {
                "status": "error",
                "message": f"Server '{server_name}' was already stopped.",
            }
            return result

        # On Linux, prefer to use systemd if the service is active.
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
                result = {
                    "status": "success",
                    "message": f"Server '{server_name}' stop initiated via systemd.",
                }
                return result
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                logger.warning(
                    f"API: Stopping via systemctl failed: {e}. Falling back to direct stop.",
                    exc_info=True,
                )

        # Fallback to direct stop method (send command, then terminate).

        server.stop()
        logger.info(f"API: Server '{server_name}' stopped successfully.")
        result = {
            "status": "success",
            "message": f"Server '{server_name}' stopped successfully.",
        }

        try:
            launcher_pid_file = system_process.get_bedrock_launcher_pid_file_path(
                server.server_name, server.server_config_dir
            )
            system_process.remove_pid_file_if_exists(launcher_pid_file)
        except Exception as e_launcher_cleanup:
            logger.debug(
                f"Error during launcher PID cleanup for '{server_name}': {e_launcher_cleanup}"
            )

        return result

    except BSMError as e:
        logger.error(f"API: Failed to stop server '{server_name}': {e}", exc_info=True)
        result = {
            "status": "error",
            "message": f"Failed to stop server '{server_name}': {e}",
        }
        return result
    except Exception as e:
        logger.error(
            f"API: Unexpected error stopping server '{server_name}': {e}", exc_info=True
        )
        result = {
            "status": "error",
            "message": f"Unexpected error stopping server '{server_name}': {e}",
        }
        return result
    finally:
        # --- Plugin Hook ---
        plugin_manager.trigger_guarded_event(
            "after_server_stop", server_name=server_name, result=result
        )


@plugin_method("restart_server")
def restart_server(server_name: str, send_message: bool = True) -> Dict[str, str]:
    """Restarts the specified Bedrock server by orchestrating stop and start.

    If the server is already stopped, this function will simply start it.
    If running, it will stop it, wait briefly, and then start it again in
    detached mode.

    Args:
        server_name: The name of the server to restart.
        send_message: If True, attempts to send a "restarting" message to the
            server before stopping. Defaults to True.

    Returns:
        A dictionary with the operation status and a message.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"API: Initiating restart for server '{server_name}'. Send message: {send_message}"
    )
    try:
        server = BedrockServer(server_name)
        is_running = server.is_running()

        # If server is not running, just start it.
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

        # If server is running, perform the stop-start cycle.
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


@plugin_method("send_command")
def send_command(server_name: str, command: str) -> Dict[str, str]:
    """Sends a command to a running Bedrock server.

    The command is checked against a blacklist defined in the configuration
    before being sent.

    Args:
        server_name: The name of the server to send the command to.
        command: The command string to send.

    Returns:
        A dictionary with the operation status and a message.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        MissingArgumentError: If `command` is empty.
        BlockedCommandError: If the command is in the API blacklist.
        ServerError: For underlying server communication issues.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not command or not command.strip():
        raise MissingArgumentError("Command cannot be empty.")

    command_clean = command.strip()

    # --- Plugin Hook ---
    plugin_manager.trigger_event(
        "before_command_send", server_name=server_name, command=command_clean
    )

    logger.info(
        f"API: Attempting to send command to server '{server_name}': '{command_clean}'"
    )
    result = {}
    try:
        # Check command against the configured blacklist.
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

        server = BedrockServer(server_name)
        server.send_command(command_clean)

        logger.info(
            f"API: Command '{command_clean}' sent successfully to server '{server_name}'."
        )
        result = {
            "status": "success",
            "message": f"Command '{command_clean}' sent successfully.",
        }
        return result

    except BSMError as e:
        logger.error(
            f"API: Failed to send command to server '{server_name}': {e}", exc_info=True
        )
        # Re-raise to allow higher-level handlers to catch specific BSM errors.
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error sending command to '{server_name}': {e}",
            exc_info=True,
        )
        # Wrap unexpected errors in a generic ServerError.
        raise ServerError(f"Unexpected error sending command: {e}") from e
    finally:
        # --- Plugin Hook ---
        plugin_manager.trigger_event(
            "after_command_send",
            server_name=server_name,
            command=command_clean,
            result=result,
        )


def delete_server_data(
    server_name: str, stop_if_running: bool = True
) -> Dict[str, str]:
    """Deletes all data associated with a Bedrock server.

    This is a destructive operation. It will remove the server's installation
    directory, its configuration file, and its backup directory.

    Args:
        server_name: The name of the server to delete.
        stop_if_running: If True, the server will be stopped before its data
            is deleted. If False and the server is running, the operation
            will likely fail due to file locks. Defaults to True.

    Returns:
        A dictionary with the operation status and a message.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    # --- Plugin Hook ---
    plugin_manager.trigger_event("before_delete_server_data", server_name=server_name)

    # High-visibility warning for a destructive operation.
    logger.warning(
        f"API: !!! Initiating deletion of ALL data for server '{server_name}'. Stop if running: {stop_if_running} !!!"
    )
    result = {}
    try:
        server = BedrockServer(server_name)

        # Stop the server first if requested and it's running.
        if stop_if_running and server.is_running():
            logger.info(
                f"API: Server '{server_name}' is running. Stopping before deletion..."
            )

            stop_result = stop_server(server_name)
            # If the stop fails, abort the deletion to prevent data corruption.
            if stop_result.get("status") == "error":
                error_msg = f"Failed to stop server '{server_name}' before deletion: {stop_result.get('message')}. Deletion aborted."
                logger.error(error_msg)
                result = {"status": "error", "message": error_msg}
                return result

            logger.info(f"API: Server '{server_name}' stopped.")

        logger.debug(
            f"API: Proceeding with deletion of data for server '{server_name}'..."
        )
        server.delete_all_data()
        logger.info(f"API: Successfully deleted all data for server '{server_name}'.")
        result = {
            "status": "success",
            "message": f"All data for server '{server_name}' deleted successfully.",
        }
        return result

    except BSMError as e:
        logger.error(
            f"API: Failed to delete server data for '{server_name}': {e}", exc_info=True
        )
        result = {"status": "error", "message": f"Failed to delete server data: {e}"}
        return result
    except Exception as e:
        logger.error(
            f"API: Unexpected error deleting server data for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Unexpected error deleting server data: {e}",
        }
        return result
    finally:
        # --- Plugin Hook ---
        plugin_manager.trigger_event(
            "after_delete_server_data", server_name=server_name, result=result
        )
