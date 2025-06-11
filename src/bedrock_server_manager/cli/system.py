# bedrock_server_manager/cli/system.py
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
    BSMError,
    InvalidServerNameError,
)
from bedrock_server_manager.utils.general import (
    select_option,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger(__name__)


def configure_service(server_name: str) -> None:
    """
    CLI handler to interactively configure OS-specific service settings for a server.

    Args:
        server_name: The name of the server.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Starting interactive service configuration for server '{server_name}'."
    )
    os_name = platform.system()

    try:
        # Check for supported operating systems first.
        if os_name not in ("Windows", "Linux"):
            print(
                f"{_ERROR_PREFIX}Automated service configuration is not supported on this OS ({os_name})."
            )
            return

        # --- Section 1: Autoupdate (Common to Windows & Linux) ---
        print(f"\n{_INFO_PREFIX}Configuring autoupdate setting for '{server_name}'...")
        enable_autoupdate = (
            select_option("Enable check for updates on server start?", "n", "y", "n")
            == "y"
        )
        autoupdate_value = "true" if enable_autoupdate else "false"

        logger.debug(
            f"Calling API: system_api.set_autoupdate (Value={autoupdate_value})"
        )
        autoupdate_response = system_api.set_autoupdate(server_name, autoupdate_value)

        # Process API response for autoupdate
        if autoupdate_response:
            if autoupdate_response.get("status") == "error":
                message = autoupdate_response.get(
                    "message", "Unknown error configuring autoupdate."
                )
                print(f"{_ERROR_PREFIX}{message}")
            else:
                message = autoupdate_response.get(
                    "message", "Autoupdate configured successfully."
                )
                print(f"{_OK_PREFIX}{message}")
        else:
            print(
                f"{_ERROR_PREFIX}Failed to configure autoupdate: No response from API."
            )

        # --- Section 2: Autostart (Linux-specific) ---
        if os_name == "Linux":
            print(
                f"\n{_INFO_PREFIX}Configuring systemd service for '{server_name}' (Linux)..."
            )
            enable_autostart = (
                select_option(
                    "Enable service to start automatically on system boot?",
                    "n",
                    "y",
                    "n",
                )
                == "y"
            )

            logger.debug(
                f"Calling API: system_api.create_systemd_service (Start={enable_autostart})"
            )
            autostart_response = system_api.create_systemd_service(
                server_name, enable_autoupdate, enable_autostart
            )

            # Process API response for autostart
            if autostart_response:
                if autostart_response.get("status") == "error":
                    message = autostart_response.get(
                        "message", "Unknown error configuring systemd service."
                    )
                    print(f"{_ERROR_PREFIX}{message}")
                else:
                    message = autostart_response.get(
                        "message", "Systemd service configured successfully."
                    )
                    print(f"{_OK_PREFIX}{message}")
            else:
                print(
                    f"{_ERROR_PREFIX}Failed to configure systemd service: No response from API."
                )

    except BSMError as e:
        print(f"{_ERROR_PREFIX}{e}")
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred during configuration: {e}")


def enable_service(server_name: str) -> None:
    """CLI handler to enable the systemd service for a server (autostart on login). (Linux-specific)"""
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Requesting to enable service for server '{server_name}'...")
    print(f"{_INFO_PREFIX}Attempting to enable service for '{server_name}'...")
    try:
        response = system_api.enable_server_service(server_name)
        if response.get("status") == "error":
            print(f"{_ERROR_PREFIX}{response.get('message', 'Unknown error.')}")
        else:
            print(f"{_OK_PREFIX}{response.get('message', 'Service enabled.')}")
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")


def disable_service(server_name: str) -> None:
    """CLI handler to disable the systemd service for a server. (Linux-specific)"""
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Requesting to disable service for server '{server_name}'...")
    print(f"{_INFO_PREFIX}Attempting to disable service for '{server_name}'...")
    try:
        response = system_api.disable_server_service(server_name)
        if response.get("status") == "error":
            print(f"{_ERROR_PREFIX}{response.get('message', 'Unknown error.')}")
        else:
            print(f"{_OK_PREFIX}{response.get('message', 'Service disabled.')}")
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")


def _monitor_loop(server_name: str) -> None:
    """Internal helper to continuously fetch and display server resource usage."""
    logger.debug(f"Starting monitoring loop for server '{server_name}'.")
    try:
        while True:
            response = system_api.get_bedrock_process_info(server_name)

            os.system("cls" if platform.system() == "Windows" else "clear")
            print(
                f"{Style.BRIGHT}{Fore.MAGENTA}--- Monitoring Server: {server_name} ---{Style.RESET_ALL}"
            )
            print("Press CTRL + C to exit monitor\n")

            if response.get("status") == "error":
                message = response.get("message", "Unknown error retrieving status.")
                print(f"{Fore.RED}Error: {message}{Style.RESET_ALL}")
            elif response.get("process_info") is None:
                print(
                    f"{Fore.YELLOW}Server process not found (likely stopped).{Style.RESET_ALL}"
                )
            else:
                process_info = response["process_info"]
                print(f"PID          : {process_info.get('pid', 'N/A')}")
                print(f"CPU Usage    : {process_info.get('cpu_percent', 0.0):.1f}%")
                print(f"Memory Usage : {process_info.get('memory_mb', 0.0):.1f} MB")
                print(f"Uptime       : {process_info.get('uptime', 'N/A')}")

            time.sleep(2)

    except KeyboardInterrupt:
        print(f"\n{_OK_PREFIX}Monitoring stopped by user.")
    except Exception as e:
        print(f"\n{_ERROR_PREFIX}An unexpected error occurred during monitoring: {e}")


def monitor_service_usage(server_name: str) -> None:
    """
    CLI handler to continuously monitor and display the CPU and memory usage of a server.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Starting resource monitoring for server '{server_name}'.")
    try:
        _monitor_loop(server_name)
    except BSMError as e:
        print(f"{_ERROR_PREFIX}{e}")
