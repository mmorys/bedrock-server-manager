# bedrock-server-manager/bedrock_server_manager/cli/server.py
"""
Command-line interface functions for direct server management actions.

Provides handlers for CLI commands like starting, stopping, restarting, deleting,
and sending commands to Bedrock server instances. Uses print() for user feedback.
"""

import logging
from typing import Optional, Dict, Any


# Third-party imports
try:
    from colorama import Fore, Style, init

    COLORAMA_AVAILABLE = True
except ImportError:
    # Define dummy Fore, Style, init if colorama is not installed
    class DummyStyle:
        def __getattr__(self, name):
            return ""

    Fore = DummyStyle()
    Style = DummyStyle()

    def init(*args, **kwargs):
        pass

    COLORAMA_AVAILABLE = True
except ImportError:
    # Define dummy Fore, Style, init if colorama is not installed
    class DummyStyle:
        def __getattr__(self, name):
            return ""

    Fore = DummyStyle()
    Style = DummyStyle()

    def init(*args, **kwargs):
        pass


# Local imports
from bedrock_server_manager.api import server as server_api
from bedrock_server_manager.error import (
    InvalidServerNameError,
    MissingArgumentError,
    FileOperationError,
)
from bedrock_server_manager.utils.general import (
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _ERROR_PREFIX,
    _WARN_PREFIX,
)

logger = logging.getLogger("bedrock_server_manager")


def start_server(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    CLI handler function to start a specific Bedrock server instance.

    Calls the corresponding API function and prints the result.

    Args:
        server_name: The name of the server to start.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Requesting to start server '{server_name}'...")
    print(f"{_INFO_PREFIX}Attempting to start server '{server_name}'...")

    try:
        # Call the API function
        logger.debug(f"Calling API: server_api.start_server for '{server_name}'")
        response: Dict[str, Any] = server_api.start_server(server_name, base_dir)
        logger.debug(f"API response from start_server: {response}")

        # --- User Interaction: Print Result ---
        if response.get("status") == "error":
            message = response.get("message", "Unknown error starting server.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Start server failed for '{server_name}': {message}")
        else:
            message = response.get(
                "message", f"Server '{server_name}' started successfully."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Start server successful for '{server_name}'.")
        # --- End User Interaction ---

    except (InvalidServerNameError, FileOperationError) as e:
        # Catch errors raised directly by the API call setup
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call start server API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        # Catch unexpected errors during API call
        print(f"{_ERROR_PREFIX}An unexpected error occurred while starting server: {e}")
        logger.error(
            f"CLI: Unexpected error starting server '{server_name}': {e}", exc_info=True
        )


def systemd_start_server(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    CLI handler function to start a Bedrock server using the systemd/screen method.

    (Linux-specific)

    Args:
        server_name: The name of the server to start.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    # Note: API function handles the platform check
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Requesting to start server '{server_name}' via systemd/screen..."
    )
    print(
        f"{_INFO_PREFIX}Attempting to start server '{server_name}' via systemd/screen..."
    )

    try:
        logger.debug(
            f"Calling API: server_api.systemd_start_server for '{server_name}'"
        )
        response = server_api.systemd_start_server(server_name, base_dir)
        logger.debug(f"API response from systemd_start_server: {response}")

        if response.get("status") == "error":
            message = response.get(
                "message", "Unknown error starting server via systemd/screen."
            )
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Systemd start failed for '{server_name}': {message}")
        else:
            message = response.get(
                "message", f"Server '{server_name}' start initiated via systemd/screen."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Systemd start successful for '{server_name}'.")

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call systemd start server API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error during systemd start for '{server_name}': {e}",
            exc_info=True,
        )


def stop_server(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    CLI handler function to stop a specific Bedrock server instance.

    Args:
        server_name: The name of the server to stop.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Requesting to stop server '{server_name}'...")
    print(f"{_INFO_PREFIX}Attempting to stop server '{server_name}'...")

    try:
        logger.debug(f"Calling API: server_api.stop_server for '{server_name}'")
        response = server_api.stop_server(server_name, base_dir)
        logger.debug(f"API response from stop_server: {response}")

        if response.get("status") == "error":
            message = response.get("message", "Unknown error stopping server.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Stop server failed for '{server_name}': {message}")
        else:
            message = response.get(
                "message",
                f"Server '{server_name}' stopped successfully or was already stopped.",
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Stop server successful for '{server_name}'.")

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call stop server API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred while stopping server: {e}")
        logger.error(
            f"CLI: Unexpected error stopping server '{server_name}': {e}", exc_info=True
        )


def systemd_stop_server(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    CLI handler function to stop a Bedrock server using the systemd/screen method.

    (Linux-specific)

    Args:
        server_name: The name of the server to stop.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    # Note: API function handles the platform check
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Requesting to stop server '{server_name}' via systemd/screen..."
    )
    print(
        f"{_INFO_PREFIX}Attempting to stop server '{server_name}' via systemd/screen..."
    )

    try:
        logger.debug(f"Calling API: server_api.systemd_stop_server for '{server_name}'")
        response = server_api.systemd_stop_server(server_name, base_dir)
        logger.debug(f"API response from systemd_stop_server: {response}")

        if response.get("status") == "error":
            message = response.get(
                "message", "Unknown error stopping server via systemd/screen."
            )
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Systemd stop failed for '{server_name}': {message}")
        else:
            message = response.get(
                "message", f"Server '{server_name}' stop initiated via systemd/screen."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Systemd stop successful for '{server_name}'.")

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call systemd stop server API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error during systemd stop for '{server_name}': {e}",
            exc_info=True,
        )


def restart_server(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    CLI handler function to restart a specific Bedrock server instance.

    Args:
        server_name: The name of the server to restart.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Requesting to restart server '{server_name}'...")
    print(f"{_INFO_PREFIX}Attempting to restart server '{server_name}'...")

    try:
        logger.debug(f"Calling API: server_api.restart_server for '{server_name}'")
        # API function handles stop/start logic and message sending
        response = server_api.restart_server(
            server_name, base_dir
        )  # send_message defaults true
        logger.debug(f"API response from restart_server: {response}")

        if response.get("status") == "error":
            message = response.get("message", "Unknown error restarting server.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Restart server failed for '{server_name}': {message}")
        else:
            message = response.get(
                "message", f"Server '{server_name}' restarted successfully."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Restart server successful for '{server_name}'.")

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call restart server API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(
            f"{_ERROR_PREFIX}An unexpected error occurred while restarting server: {e}"
        )
        logger.error(
            f"CLI: Unexpected error restarting server '{server_name}': {e}",
            exc_info=True,
        )


def send_command(
    server_name: str, command: str, base_dir: Optional[str] = None
) -> None:
    """
    CLI handler function to send a command to a running server.

    Args:
        server_name: The name of the target server.
        command: The command string to send.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        MissingArgumentError: If `command` is empty.
        InvalidServerNameError: If `server_name` is empty.
    """
    # Input validation for API call
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not command or not command.strip():
        raise MissingArgumentError("Command cannot be empty.")

    trimmed_command = command.strip()
    logger.debug(
        f"CLI: Requesting to send command to server '{server_name}': '{trimmed_command}'"
    )
    # No initial print needed, result will be printed

    try:
        logger.debug(f"Calling API: server_api.send_command for '{server_name}'")
        response = server_api.send_command(server_name, trimmed_command, base_dir)
        logger.debug(f"API response from send_command: {response}")

        # --- User Interaction: Print Result ---
        if response.get("status") == "error":
            message = response.get("message", "Unknown error sending command.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Send command failed for '{server_name}': {message}")
        else:
            message = response.get("message", "Command sent successfully.")
            print(f"{_OK_PREFIX}{message}")  # Simple confirmation
            logger.debug(f"CLI: Send command successful for '{server_name}'.")
        # --- End User Interaction ---

    except (MissingArgumentError, InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call send command API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred while sending command: {e}")
        logger.error(
            f"CLI: Unexpected error sending command to '{server_name}': {e}",
            exc_info=True,
        )


def delete_server(
    server_name: str,
    base_dir: Optional[str] = None,
    config_dir: Optional[str] = None,
    skip_confirmation: bool = False,  # Added flag
) -> None:
    """
    CLI handler function to delete a Bedrock server's data. Includes confirmation prompt.

    Args:
        server_name: The name of the server to delete.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        config_dir: Optional. Base directory for server configs. Uses default if None.
        skip_confirmation: If True, bypass the confirmation prompt (use with caution).

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Requesting to delete server '{server_name}'...")

    # --- User Interaction: Confirmation ---
    if not skip_confirmation:
        print(
            f"{_WARN_PREFIX}You are about to delete all data for server '{server_name}'."
        )
        print(
            f"{_WARN_PREFIX}This includes the installation directory, configuration, and backups."
        )
        confirm = (
            input(
                f"{Fore.RED}This action cannot be undone. Are you absolutely sure? (yes/no):{Style.RESET_ALL} "
            )
            .strip()
            .lower()
        )
        logger.debug(f"User confirmation input for delete: '{confirm}'")

        if confirm not in ("y", "yes"):
            print(f"{_INFO_PREFIX}Server deletion canceled by user.")
            logger.debug(f"Deletion of server '{server_name}' canceled by user.")
            return
        logger.warning(f"User confirmed deletion for server '{server_name}'.")
    else:
        logger.warning(
            f"Skipping confirmation prompt for deleting server '{server_name}'."
        )
    # --- End User Interaction ---

    print(f"{_INFO_PREFIX}Proceeding with deletion of server '{server_name}'...")
    try:
        # Determine directories (API function handles defaults if None passed)
        effective_base_dir = (
            get_base_dir(base_dir) if base_dir else None
        )  # Resolve only if needed, let API handle default
        effective_config_dir = (
            config_dir  # Pass None if not provided, let API handle default
        )

        logger.debug(f"Calling API: server_api.delete_server_data for '{server_name}'")
        # API function handles stop_if_running=True by default
        response = server_api.delete_server_data(
            server_name, effective_base_dir, effective_config_dir
        )
        logger.debug(f"API response from delete_server_data: {response}")

        # --- User Interaction: Print Result ---
        if response.get("status") == "error":
            message = response.get("message", "Unknown error deleting server.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Delete server failed for '{server_name}': {message}")
        else:
            message = response.get(
                "message", f"Server '{server_name}' deleted successfully."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Delete server successful for '{server_name}'.")
        # --- End User Interaction ---

    except (InvalidServerNameError, FileOperationError) as e:  # Catch setup errors
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call delete server API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        # Catch unexpected errors during API call
        print(f"{_ERROR_PREFIX}An unexpected error occurred while deleting server: {e}")
        logger.error(
            f"CLI: Unexpected error deleting server '{server_name}': {e}", exc_info=True
        )
