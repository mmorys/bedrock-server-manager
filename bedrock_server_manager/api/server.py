# bedrock-server-manager/bedrock_server_manager/api/server.py
"""
Provides API-level functions for managing Bedrock server instances.

This acts as an interface layer, orchestrating calls to core server management
functions (`server_base`, `system_linux`, etc.) and returning structured
dictionary responses indicating success or failure, suitable for use by web routes
or other higher-level application logic.
"""

import os
import logging
from typing import Dict, Optional, Any
import platform
import time

# Local imports
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
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
    except (FileOperationError, InvalidInputError, InvalidServerNameError) as e:
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


def start_server(server_name: str, base_dir: Optional[str] = None) -> Dict[str, str]:
    """
    Starts the specified Bedrock server using the BedrockServer class.

    Args:
        server_name: The name of the server to start.
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"Attempting to start server '{server_name}'...")
    try:
        effective_base_dir = get_base_dir(base_dir)

        # Check if already running before creating BedrockServer instance
        if system_base.is_server_running(server_name, effective_base_dir):
            logger.warning(
                f"Server '{server_name}' is already running. Start request ignored."
            )
            return {
                "status": "error",
                "message": f"Server '{server_name}' is already running.",
            }

        # Create instance (raises ServerNotFoundError if executable missing)
        # Pass only server_name, let the class determine paths
        bedrock_server = server_base.BedrockServer(server_name)
        # Call start method (raises ServerStartError, CommandNotFoundError)
        bedrock_server.start()
        logger.info(f"Server '{server_name}' started successfully.")
        return {
            "status": "success",
            "message": f"Server '{server_name}' started successfully.",
        }

    # Catch specific, expected exceptions from BedrockServer init/start
    except (ServerNotFoundError, ServerStartError, CommandNotFoundError) as e:
        logger.error(f"Failed to start server '{server_name}': {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to start server '{server_name}': {e}",
        }
    except FileOperationError as e:  # Catch error from get_base_dir
        logger.error(
            f"Configuration error preventing server start for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        # Catch unexpected errors
        logger.error(
            f"Unexpected error starting server '{server_name}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error starting server '{server_name}': {e}",
        }


def systemd_start_server(
    server_name: str, base_dir: Optional[str] = None
) -> Dict[str, str]:
    """
    Starts the Bedrock server using the Linux-specific screen method (typically via systemd).

    Args:
        server_name: The name of the server to start.
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if platform.system() != "Linux":
        return {
            "status": "error",
            "message": "Systemd start method is only supported on Linux.",
        }

    logger.info(
        f"Attempting to start server '{server_name}' via systemd/screen method..."
    )
    try:
        effective_base_dir = get_base_dir(base_dir)

        # Check if already running
        if system_base.is_server_running(server_name, effective_base_dir):
            logger.warning(
                f"Server '{server_name}' is already running (systemd start check)."
            )
            return {
                "status": "error",
                "message": f"Server '{server_name}' is already running.",
            }

        # Call the Linux-specific start function
        server_dir = os.path.join(effective_base_dir, server_name)
        system_linux._systemd_start_server(server_name, server_dir)
        logger.info(
            f"Server '{server_name}' started successfully via systemd/screen method."
        )
        return {
            "status": "success",
            "message": f"Server '{server_name}' start initiated via systemd/screen.",
        }

    except (ServerStartError, CommandNotFoundError, DirectoryError) as e:
        logger.error(
            f"Failed to start server '{server_name}' via systemd/screen: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Failed to start server via systemd/screen: {e}",
        }
    except FileOperationError as e:  # Catch error from get_base_dir
        logger.error(
            f"Configuration error preventing server start for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error starting server '{server_name}' via systemd/screen: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error starting server via systemd/screen: {e}",
        }


def stop_server(server_name: str, base_dir: Optional[str] = None) -> Dict[str, str]:
    """
    Stops the specified Bedrock server using the BedrockServer class.

    Args:
        server_name: The name of the server to stop.
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"Attempting to stop server '{server_name}'...")
    try:
        effective_base_dir = get_base_dir(base_dir)

        # Check if not running before creating instance
        if not system_base.is_server_running(server_name, effective_base_dir):
            logger.warning(
                f"Server '{server_name}' is not running. Stop request ignored."
            )
            # Return success as the desired state (stopped) is achieved
            return {
                "status": "success",
                "message": f"Server '{server_name}' was already stopped.",
            }

        # Create instance (raises ServerNotFoundError if executable missing but server IS running)
        bedrock_server = server_base.BedrockServer(server_name)
        # Call stop method (raises ServerStopError, SendCommandError, CommandNotFoundError)
        bedrock_server.stop()
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
    ) as e:
        logger.error(f"Failed to stop server '{server_name}': {e}", exc_info=True)
        # If ServerNotFoundError happens here, it means process is running but exe is gone - report specific error
        if isinstance(e, ServerNotFoundError):
            return {
                "status": "error",
                "message": f"Server '{server_name}' process found but executable missing. Stop failed.",
            }
        return {
            "status": "error",
            "message": f"Failed to stop server '{server_name}': {e}",
        }
    except FileOperationError as e:  # Catch error from get_base_dir
        logger.error(
            f"Configuration error preventing server stop for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error stopping server '{server_name}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error stopping server '{server_name}': {e}",
        }


def systemd_stop_server(
    server_name: str, base_dir: Optional[str] = None
) -> Dict[str, str]:
    """
    Stops the Bedrock server using the Linux-specific screen method (typically via systemd).

    Args:
        server_name: The name of the server to stop.
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if platform.system() != "Linux":
        return {
            "status": "error",
            "message": "Systemd stop method is only supported on Linux.",
        }

    logger.info(
        f"Attempting to stop server '{server_name}' via systemd/screen method..."
    )
    try:
        effective_base_dir = get_base_dir(base_dir)

        # Check if not running
        if not system_base.is_server_running(server_name, effective_base_dir):
            logger.warning(
                f"Server '{server_name}' is not running (systemd stop check)."
            )
            return {
                "status": "success",
                "message": f"Server '{server_name}' was already stopped.",
            }

        # Call the Linux-specific stop function
        server_dir = os.path.join(effective_base_dir, server_name)
        system_linux._systemd_stop_server(server_name, server_dir)
        logger.info(
            f"Server '{server_name}' stop command sent successfully via systemd/screen method."
        )
        # Note: This only sends the command, doesn't wait for full stop.
        return {
            "status": "success",
            "message": f"Server '{server_name}' stop initiated via systemd/screen.",
        }

    except (ServerStopError, CommandNotFoundError) as e:
        logger.error(
            f"Failed to stop server '{server_name}' via systemd/screen: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Failed to stop server via systemd/screen: {e}",
        }
    except FileOperationError as e:  # Catch error from get_base_dir
        logger.error(
            f"Configuration error preventing server stop for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error stopping server '{server_name}' via systemd/screen: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error stopping server via systemd/screen: {e}",
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
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"Initiating restart for server '{server_name}'. Send message: {send_message}"
    )
    try:
        effective_base_dir = get_base_dir(base_dir)

        is_running = system_base.is_server_running(server_name, effective_base_dir)

        if not is_running:
            logger.info(
                f"Server '{server_name}' was not running. Attempting to start..."
            )
            # Just call start_server API function
            start_result = start_server(server_name, effective_base_dir)
            # Adjust message slightly for restart context
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
                    # Create instance just to send command
                    bedrock_server = server_base.BedrockServer(server_name)
                    bedrock_server.send_command(
                        "say Server restarting in 10 seconds..."
                    )
                    logger.info(
                        f"Sent restart warning to server '{server_name}'. Waiting 10s..."
                    )
                    time.sleep(10)  # Give players time to see message
                except (
                    ServerNotFoundError,
                    SendCommandError,
                    ServerNotRunningError,
                    CommandNotFoundError,
                ) as msg_err:
                    # Log warning but don't fail the whole restart if message send fails
                    logger.warning(
                        f"Could not send restart warning message to server '{server_name}': {msg_err}. Proceeding with restart.",
                        exc_info=True,
                    )
                except Exception as msg_err:
                    logger.warning(
                        f"Unexpected error sending restart warning message to server '{server_name}': {msg_err}. Proceeding with restart.",
                        exc_info=True,
                    )

            # --- Stop Server ---
            logger.debug(f"Stopping server '{server_name}' for restart...")
            stop_result = stop_server(server_name, effective_base_dir)
            if stop_result.get("status") == "error":
                logger.error(
                    f"Restart failed: Could not stop server '{server_name}'. Error: {stop_result.get('message')}"
                )
                # Append context to the error message
                stop_result["message"] = (
                    f"Restart failed during stop phase: {stop_result.get('message')}"
                )
                return stop_result

            # Optional delay between stop and start
            logger.debug("Waiting briefly before restarting...")
            time.sleep(3)  # Short delay

            # --- Start Server ---
            logger.debug(f"Starting server '{server_name}' after stop...")
            start_result = start_server(server_name, effective_base_dir)
            if start_result.get("status") == "error":
                logger.error(
                    f"Restart failed: Could not start server '{server_name}' after stopping. Error: {start_result.get('message')}"
                )
                # Append context to the error message
                start_result["message"] = (
                    f"Restart failed during start phase: {start_result.get('message')}"
                )
                return start_result

            # If start was successful
            logger.info(f"Server '{server_name}' restarted successfully.")
            return {
                "status": "success",
                "message": f"Server '{server_name}' restarted successfully.",
            }

    except FileOperationError as e:  # Catch error from get_base_dir
        logger.error(
            f"Configuration error preventing server restart for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        # Catch unexpected errors during the restart orchestration
        logger.error(
            f"Unexpected error during restart process for server '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error during restart: {e}"}


def send_command(
    server_name: str, command: str, base_dir: Optional[str] = None
) -> Dict[str, str]:
    """
    Sends a command to a running Bedrock server instance.

    Args:
        server_name: The name of the target server.
        command: The command string to send to the server console.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `server_name` or `command` is empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileOperationError: If `base_dir` cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not command:
        raise MissingArgumentError("Command cannot be empty.")

    logger.info(f"Attempting to send command to server '{server_name}': '{command}'")
    try:
        effective_base_dir = get_base_dir(
            base_dir
        )  # Needed indirectly by BedrockServer init if path not given

        # Create instance (raises ServerNotFoundError if executable missing)
        # Pass only server_name, let the class determine paths
        bedrock_server = server_base.BedrockServer(server_name)
        # Send command (raises various errors on failure)
        bedrock_server.send_command(command)
        logger.info(f"Command '{command}' sent successfully to server '{server_name}'.")
        return {
            "status": "success",
            "message": f"Command '{command}' sent successfully.",
        }

    except (
        ServerNotFoundError,
        ServerNotRunningError,
        SendCommandError,
        CommandNotFoundError,
        MissingArgumentError,
    ) as e:
        # Catch specific, known errors from BedrockServer.send_command or init
        logger.error(
            f"Failed to send command to server '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to send command: {e}"}
    except FileOperationError as e:  # Catch error from get_base_dir
        logger.error(
            f"Configuration error preventing sending command to '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        # Catch unexpected errors
        logger.error(
            f"Unexpected error sending command to server '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error sending command: {e}"}


def delete_server_data(
    server_name: str,
    base_dir: Optional[str] = None,
    config_dir: Optional[str] = None,
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
        FileOperationError: If essential settings (BASE_DIR, BACKUP_DIR) are missing.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"!!! Initiating deletion of ALL data for server '{server_name}'. Stop if running: {stop_if_running} !!!"
    )
    try:
        effective_base_dir = get_base_dir(base_dir)
        # Ensure backup dir setting exists for core delete function
        if not settings.get("BACKUP_DIR"):
            raise FileOperationError("BACKUP_DIR setting missing.")

        # --- Stop Server (Optional) ---
        if stop_if_running:
            logger.debug(
                f"Checking if server '{server_name}' needs to be stopped before deletion..."
            )
            try:
                if system_base.is_server_running(server_name, effective_base_dir):
                    logger.info(
                        f"Server '{server_name}' is running. Stopping before deletion..."
                    )
                    stop_result = stop_server(
                        server_name, effective_base_dir
                    )  # Call API stop function
                    if stop_result.get("status") == "error":
                        # If stop fails, abort deletion to prevent data issues with running server
                        error_msg = f"Failed to stop server '{server_name}' before deletion: {stop_result.get('message')}. Deletion aborted."
                        logger.error(error_msg)
                        return {"status": "error", "message": error_msg}
                    logger.info(f"Server '{server_name}' stopped.")
                else:
                    logger.debug(
                        f"Server '{server_name}' is not running. No stop needed."
                    )
            except Exception as e:
                # Catch unexpected errors during stop check/attempt
                error_msg = f"Error occurred while stopping server '{server_name}' before deletion: {e}. Deletion aborted."
                logger.error(error_msg, exc_info=True)
                return {"status": "error", "message": error_msg}

        # --- Core Deletion Operation ---
        logger.debug(f"Proceeding with deletion of data for server '{server_name}'...")
        # Call core delete function
        server_base.delete_server_data(
            server_name, effective_base_dir, config_dir
        )  # Raises DirectoryError on failure
        logger.info(f"Successfully deleted data for server '{server_name}'.")
        return {
            "status": "success",
            "message": f"All data for server '{server_name}' deleted successfully.",
        }

    except (DirectoryError, InvalidServerNameError) as e:
        # Catch specific errors known to be raised by core delete_server_data
        logger.error(
            f"Failed to delete server data for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to delete server data: {e}"}
    except FileOperationError as e:  # Catch config/base_dir errors
        logger.error(
            f"Configuration error preventing server deletion for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        # Catch unexpected errors
        logger.error(
            f"Unexpected error deleting server data for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error deleting server data: {e}",
        }
