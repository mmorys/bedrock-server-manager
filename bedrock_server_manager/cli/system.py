# bedrock-server-manager/bedrock_server_manager/cli/system.py
"""
Command-line interface functions for system-level operations related to servers.

Provides handlers for CLI commands to create/configure OS services (systemd on Linux,
autoupdate flag on Windows) and monitor server resource usage. Uses print() for user
interaction and feedback.
"""

import os
import time
import logging
import platform
from typing import Optional

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


# Local imports
from bedrock_server_manager.api import system as system_api
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
)
from bedrock_server_manager.utils.general import (
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger("bedrock_server_manager")


def configure_service(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    CLI handler to interactively configure OS-specific service settings for a server.

    - Linux: Creates/updates a systemd service, prompting for autoupdate and autostart.
    - Windows: Prompts to set the 'autoupdate' flag in the server's config file.

    Args:
        server_name: The name of the server.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        # API/Core errors are caught and printed.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Starting interactive service configuration for server '{server_name}'."
    )
    os_name = platform.system()

    try:
        # Resolve base_dir only if needed (currently only by Linux API call)
        effective_base_dir = None
        if os_name == "Linux":
            effective_base_dir = get_base_dir(base_dir)  # May raise FileOperationError

        if os_name == "Linux":
            print(
                f"\n{_INFO_PREFIX}Configuring systemd service for '{server_name}' (Linux)..."
            )
            # --- User Interaction: Linux ---
            autoupdate = False  # Default
            while True:
                response = (
                    input(
                        f"{Fore.CYAN}Enable auto-update on server start? (y/n) [Default: n]:{Style.RESET_ALL} "
                    )
                    .strip()
                    .lower()
                )
                logger.debug(f"User input for autoupdate (Linux): '{response}'")
                if response in ("yes", "y"):
                    autoupdate = True
                    break
                elif response in ("no", "n", ""):
                    autoupdate = False
                    break
                else:
                    print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

            autostart = False  # Default
            while True:
                response = (
                    input(
                        f"{Fore.CYAN}Enable service to start automatically on login? (y/n) [Default: n]:{Style.RESET_ALL} "
                    )
                    .strip()
                    .lower()
                )
                logger.debug(f"User input for autostart (Linux): '{response}'")
                if response in ("yes", "y"):
                    autostart = True
                    break
                elif response in ("no", "n", ""):
                    autostart = False
                    break
                else:
                    print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")
            # --- End User Interaction ---

            logger.debug(
                f"Calling API: system_api.create_systemd_service (Update={autoupdate}, Start={autostart})"
            )
            api_response = system_api.create_systemd_service(
                server_name, effective_base_dir, autoupdate, autostart
            )

        elif os_name == "Windows":
            print(
                f"\n{_INFO_PREFIX}Configuring autoupdate setting for '{server_name}' (Windows)..."
            )
            # --- User Interaction: Windows ---
            autoupdate_value = "false"  # Default
            while True:
                response = (
                    input(
                        f"{Fore.CYAN}Enable check for updates on server start? (y/n) [Default: n]:{Style.RESET_ALL} "
                    )
                    .strip()
                    .lower()
                )
                logger.debug(f"User input for autoupdate (Windows): '{response}'")
                if response in ("yes", "y"):
                    autoupdate_value = "true"
                    break
                elif response in ("no", "n", ""):
                    autoupdate_value = "false"
                    break
                else:
                    print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")
            # --- End User Interaction ---

            logger.debug(
                f"Calling API: system_api.set_windows_autoupdate (Value={autoupdate_value})"
            )
            # API function handles config_dir resolution
            api_response = system_api.set_windows_autoupdate(
                server_name, autoupdate_value
            )

        else:
            # Unsupported OS
            message = f"Automated service configuration is not supported on this operating system ({os_name})."
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: {message}")
            return  # Exit function for unsupported OS

        # --- Process API Response ---
        logger.debug(f"API response for service configuration: {api_response}")
        if api_response.get("status") == "error":
            message = api_response.get("message", "Unknown error configuring service.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(
                f"CLI: Service configuration failed for '{server_name}': {message}"
            )
        else:
            message = api_response.get("message", "Service configured successfully.")
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Service configuration successful for '{server_name}'.")

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to configure service for '{server_name}': {e}", exc_info=True
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error configuring service for '{server_name}': {e}",
            exc_info=True,
        )


def enable_service(server_name: str) -> None:
    """
    CLI handler function to enable the systemd service for a server (autostart on login).

    (Linux-specific)

    Args:
        server_name: The name of the server.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    # API function handles platform check and returns error if not Linux
    logger.debug(f"CLI: Requesting to enable service for server '{server_name}'...")
    print(f"{_INFO_PREFIX}Attempting to enable service for '{server_name}'...")

    try:
        logger.debug(
            f"Calling API: system_api.enable_server_service for '{server_name}'"
        )
        response = system_api.enable_server_service(server_name)
        logger.debug(f"API response from enable_server_service: {response}")

        if response.get("status") == "error":
            message = response.get("message", "Unknown error enabling service.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(
                f"CLI: Failed to enable service for '{server_name}': {message}"
            )
        else:
            message = response.get(
                "message", f"Service for server '{server_name}' enabled successfully."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Enable service successful for '{server_name}'.")

    except InvalidServerNameError as e:  # Catch error raised here
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call enable service API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error enabling service for '{server_name}': {e}",
            exc_info=True,
        )


def disable_service(server_name: str) -> None:
    """
    CLI handler function to disable the systemd service for a server (prevent autostart on login).

    (Linux-specific)

    Args:
        server_name: The name of the server.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    # API function handles platform check and returns error if not Linux
    logger.debug(f"CLI: Requesting to disable service for server '{server_name}'...")
    print(f"{_INFO_PREFIX}Attempting to disable service for '{server_name}'...")

    try:
        logger.debug(
            f"Calling API: system_api.disable_server_service for '{server_name}'"
        )
        response = system_api.disable_server_service(server_name)
        logger.debug(f"API response from disable_server_service: {response}")

        if response.get("status") == "error":
            message = response.get("message", "Unknown error disabling service.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(
                f"CLI: Failed to disable service for '{server_name}': {message}"
            )
        else:
            message = response.get(
                "message", f"Service for server '{server_name}' disabled successfully."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Disable service successful for '{server_name}'.")

    except InvalidServerNameError as e:  # Catch error raised here
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call disable service API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error disabling service for '{server_name}': {e}",
            exc_info=True,
        )


def _monitor_loop(server_name: str, base_dir: str) -> None:
    """
    Internal helper function to continuously fetch and display server resource usage.

    Args:
        server_name: The name of the server to monitor.
        base_dir: The base directory for server installations.
    """
    logger.debug(f"Starting monitoring loop for server '{server_name}'.")
    try:
        while True:
            # Call API to get current process info
            # Log API call at debug level inside the loop? Maybe too noisy.
            response = system_api.get_bedrock_process_info(
                server_name, base_dir
            )  # Returns dict

            # --- User Interaction: Display Monitor Output ---
            os.system(
                "cls" if platform.system() == "Windows" else "clear"
            )  # Clear screen
            print(
                f"{Style.BRIGHT}{Fore.MAGENTA}--- Monitoring Server: {server_name} ---{Style.RESET_ALL}"
            )

            if response.get("status") == "error":
                message = response.get("message", "Unknown error retrieving status.")
                print(f"\n{Fore.RED}Error: {message}{Style.RESET_ALL}")
                print("\n---------------------------------")
                print("Press CTRL + C to exit monitor")
                logger.error(f"Monitor update failed for '{server_name}': {message}")
            elif response.get("process_info") is None:
                # API returned success but process_info is None (meaning server stopped)
                print(
                    f"\n{Fore.YELLOW}Server process not found (likely stopped).{Style.RESET_ALL}"
                )
                print("\n---------------------------------")
                print("Press CTRL + C to exit monitor")
                logger.debug(
                    f"Server '{server_name}' process not found during monitoring."
                )
                # Keep monitoring - it might restart
            else:
                # Process info found, display it
                process_info = response["process_info"]
                print(f"PID          : {process_info.get('pid', 'N/A')}")
                print(f"CPU Usage    : {process_info.get('cpu_percent', 0.0):.1f}%")
                print(f"Memory Usage : {process_info.get('memory_mb', 0.0):.1f} MB")
                print(f"Uptime       : {process_info.get('uptime', 'N/A')}")
                print("\n---------------------------------")
                print("Press CTRL + C to exit monitor")
                logger.debug(f"Monitor update for '{server_name}': {process_info}")
            # --- End User Interaction ---

            time.sleep(2)  # Interval between updates

    except KeyboardInterrupt:
        # --- User Interaction: Exit Message ---
        print(f"\n{_OK_PREFIX}Monitoring stopped by user.")
        # --- End User Interaction ---
        logger.debug(f"Monitoring stopped by user for server '{server_name}'.")
    except Exception as e:
        # Catch unexpected errors during the monitoring loop or API call
        print(f"\n{_ERROR_PREFIX}An unexpected error occurred during monitoring: {e}")
        logger.error(
            f"Unexpected error during monitor loop for '{server_name}': {e}",
            exc_info=True,
        )


def monitor_service_usage(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    CLI handler function to continuously monitor and display the CPU and memory usage
    of a specific Bedrock server instance.

    Args:
        server_name: The name of the server to monitor.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        # API/Core errors are caught within the loop and printed.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Starting resource monitoring for server '{server_name}'.")
    try:
        effective_base_dir = get_base_dir(base_dir)
        # Enter the monitoring loop (handles KeyboardInterrupt)
        _monitor_loop(server_name, effective_base_dir)
    except FileOperationError as e:  # Catch error from get_base_dir
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to start monitoring for '{server_name}': {e}", exc_info=True
        )
