# bedrock_server_manager/cli/utils.py
"""
Provides utility functions specifically for the command-line interface (CLI).

Includes functions for prompting users, displaying formatted lists (like server status),
and handling platform-specific CLI actions like attaching to screen sessions.
Uses print() for user interaction and feedback.
"""

import os
import time
import logging
import platform
from typing import Optional, Dict, Any, List

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
from bedrock_server_manager.api import (
    utils as api_utils,
    application as api_application,
)
from bedrock_server_manager.utils.general import (
    _INFO_PREFIX,
    _ERROR_PREFIX,
    _WARN_PREFIX,
)
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
)

logger = logging.getLogger(__name__)


def get_server_name() -> Optional[str]:
    """
    Prompts the user to enter a server name and validates its existence using the API.

    Loops until a valid existing server name is entered or the user cancels.

    Returns:
        The validated server name as a string, or None if the user cancels.
    """
    logger.debug("Prompting user for server name.")
    while True:
        try:
            server_name_input = input(
                f"{Fore.MAGENTA}Enter the server name (or type 'exit' to cancel):{Style.RESET_ALL} "
            ).strip()
            logger.debug(f"User input for server name: '{server_name_input}'")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{_INFO_PREFIX}Operation canceled.")
            return None

        if not server_name_input:
            print(f"{_WARN_PREFIX}Server name cannot be empty.")
            continue
        if server_name_input.lower() == "exit":
            print(f"{_INFO_PREFIX}Operation canceled.")
            return None

        try:
            logger.debug(
                f"Calling API: api_utils.validate_server_exist for '{server_name_input}'"
            )
            response = api_utils.validate_server_exist(server_name_input)
            logger.debug(f"API response from validate_server_exist: {response}")

            if response.get("status") == "success":
                return server_name_input
            else:
                message = response.get(
                    "message", f"Server '{server_name_input}' not found or invalid."
                )
                print(f"{_ERROR_PREFIX}{message}")

        except Exception as e:
            print(f"{_ERROR_PREFIX}An unexpected error occurred during validation: {e}")
            logger.error(
                f"CLI: Unexpected error validating server '{server_name_input}': {e}",
                exc_info=True,
            )
            # Loop to let the user try again


def list_servers_status() -> None:
    """Retrieves and prints a formatted list of all detected servers with their status and version."""
    logger.debug("CLI: Requesting list of all server statuses.")
    try:
        response: Dict[str, Any] = api_application.get_all_servers_data()
        logger.debug(f"API response from get_all_servers_data: {response}")

        print(f"\n{Fore.MAGENTA}Detected Servers Status:{Style.RESET_ALL}")
        print("-" * 65)
        print(
            f"{Style.BRIGHT}{'SERVER NAME':<25} {'STATUS':<20} {'VERSION':<15}{Style.RESET_ALL}"
        )
        print("-" * 65)

        if response.get("status") == "error":
            message = response.get("message", "Unknown error retrieving server list.")
            print(f"{Fore.RED}  Error: {message}{Style.RESET_ALL}")
        else:
            servers: List[Dict[str, str]] = response.get("servers", [])
            if not servers:
                print("  No servers found.")
            else:
                for server_data in servers:
                    name = server_data.get("name", "N/A")
                    status = server_data.get("status", "UNKNOWN").upper()
                    version = server_data.get("version", "UNKNOWN")

                    status_color = {
                        "RUNNING": Fore.GREEN,
                        "STARTING": Fore.YELLOW,
                        "RESTARTING": Fore.YELLOW,
                        "STOPPING": Fore.YELLOW,
                        "INSTALLED": Fore.BLUE,
                        "STOPPED": Fore.RED,
                    }.get(status, Fore.RED)

                    status_str = f"{status_color}{status:<10}{Style.RESET_ALL}"
                    version_color = Fore.WHITE if version != "UNKNOWN" else Fore.RED
                    version_str = f"{version_color}{version}{Style.RESET_ALL}"
                    print(
                        f"  {Fore.CYAN}{name:<23}{Style.RESET_ALL} {status_str:<29} {version_str:<15}"
                    )

        print("-" * 65)
        print()

    except Exception as e:
        print(
            f"{_ERROR_PREFIX}An unexpected error occurred while listing server status: {e}"
        )
        logger.error(f"CLI: Unexpected error listing server status: {e}", exc_info=True)


def list_servers_loop() -> None:
    """Continuously clears the screen and lists servers with their statuses."""
    logger.debug("CLI: Starting server status monitoring loop.")
    try:
        while True:
            os.system("cls" if platform.system() == "Windows" else "clear")
            list_servers_status()
            time.sleep(5)
    except (KeyboardInterrupt, EOFError):
        print("\nExiting status monitor.")
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred starting the monitor: {e}")
        logger.error(
            f"CLI: Unexpected error starting status monitor loop: {e}", exc_info=True
        )


def attach_console(server_name: str) -> None:
    """
    CLI handler function to attach the current terminal to a server's screen session. (Linux-specific)
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Requesting to attach console for server '{server_name}'...")
    try:
        logger.debug(
            f"Calling API: api_utils.attach_to_screen_session for '{server_name}'"
        )
        response = api_utils.attach_to_screen_session(server_name)
        logger.debug(f"API response from attach_to_screen_session: {response}")

        if response.get("status") == "error":
            message = response.get("message", "Unknown error attaching to console.")
            print(f"{_ERROR_PREFIX}{message}")
        else:
            logger.debug(f"CLI: Screen attach command executed for '{server_name}'.")

    except Exception as e:
        print(
            f"{_ERROR_PREFIX}An unexpected error occurred while trying to attach: {e}"
        )
        logger.error(
            f"CLI: Unexpected error attaching console for '{server_name}': {e}",
            exc_info=True,
        )
