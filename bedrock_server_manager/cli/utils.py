# bedrock-server-manager/bedrock_server_manager/cli/utils.py
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
from bedrock_server_manager.api import utils as api_utils
from bedrock_server_manager.utils.general import (
    _INFO_PREFIX,
    _ERROR_PREFIX,
    _WARN_PREFIX,
)
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
)

logger = logging.getLogger("bedrock_server_manager")


def get_server_name(base_dir: Optional[str] = None) -> Optional[str]:
    """
    Prompts the user to enter a server name and validates its existence using the API.

    Loops until a valid existing server name is entered or the user cancels by typing 'exit'.

    Args:
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Returns:
        The validated server name as a string, or None if the user cancels.

    Raises:
        FileOperationError: If `base_dir` cannot be determined. # Propagated from API call setup
        # Other API errors are caught and printed within the loop.
    """
    logger.debug("Prompting user for server name.")
    while True:
        # --- User Interaction: Prompt ---
        try:
            server_name_input = input(
                f"{Fore.MAGENTA}Enter the server name (or type 'exit' to cancel):{Style.RESET_ALL} "
            ).strip()
            logger.debug(f"User input for server name: '{server_name_input}'")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{_INFO_PREFIX}Operation canceled.")
            logger.debug("User canceled server name selection (Ctrl+C/EOF).")
            return None
        # --- End User Interaction ---

        if not server_name_input:
            print(f"{_WARN_PREFIX}Server name cannot be empty.")
            continue

        if server_name_input.lower() == "exit":
            # --- User Interaction: Cancellation Message ---
            print(f"{_INFO_PREFIX}Operation canceled.")
            # --- End User Interaction ---
            logger.debug("User canceled server name selection by typing 'exit'.")
            return None

        # Validate existence via API call
        try:
            logger.debug(
                f"Calling API: api_utils.validate_server_exist for '{server_name_input}'"
            )
            # API function handles base_dir resolution
            response = api_utils.validate_server_exist(server_name_input, base_dir)
            logger.debug(f"API response from validate_server_exist: {response}")

            if response.get("status") == "success":
                # logger.debug(f"User selected valid server: '{server_name_input}'")
                return server_name_input  # Return the valid name
            else:
                # --- User Interaction: Print Validation Error ---
                message = response.get(
                    "message", f"Server '{server_name_input}' not found or invalid."
                )
                print(f"{_ERROR_PREFIX}{message}")
                # --- End User Interaction ---
                logger.warning(
                    f"Server validation failed for input '{server_name_input}': {message}"
                )
                # Loop continues to ask again

        except FileOperationError as e:
            # Handle errors during the API call setup (e.g., base_dir issue)
            print(f"{_ERROR_PREFIX}Configuration Error: {e}")
            logger.error(
                f"CLI: Failed to validate server '{server_name_input}': {e}",
                exc_info=True,
            )
            return None  # Abort selection on configuration error
        except Exception as e:
            # Handle unexpected errors during the API call
            print(f"{_ERROR_PREFIX}An unexpected error occurred during validation: {e}")
            logger.error(
                f"CLI: Unexpected error validating server '{server_name_input}': {e}",
                exc_info=True,
            )
            # Loop continues, maybe temporary issue? Or return None? Let's loop.


def list_servers_status(
    base_dir: Optional[str] = None, config_dir: Optional[str] = None
) -> None:
    """
    Retrieves and prints a formatted list of all detected servers with their status and version.

    Args:
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        config_dir: Optional. Base directory for server configs. Uses default if None.
    """
    logger.debug("CLI: Requesting list of all server statuses.")
    try:
        # Call API function to get status data
        logger.debug("Calling API: api_utils.get_all_servers_status")
        response: Dict[str, Any] = api_utils.get_all_servers_status(
            base_dir, config_dir
        )  # Returns dict
        logger.debug(f"API response from get_all_servers_status: {response}")

        # --- User Interaction: Print Table ---
        print(f"\n{Fore.MAGENTA}Detected Servers Status:{Style.RESET_ALL}")
        print("-" * 65)  # Adjusted width
        # Adjusted spacing for better alignment with colored output potentially varying in length
        print(
            f"{Style.BRIGHT}{'SERVER NAME':<25} {'STATUS':<20} {'VERSION':<15}{Style.RESET_ALL}"
        )
        print("-" * 65)

        if response.get("status") == "error":
            message = response.get("message", "Unknown error retrieving server list.")
            # Print error message spanning columns for visibility
            print(f"{Fore.RED}  Error: {message}{Style.RESET_ALL}")
            logger.error(f"CLI: Failed to retrieve server statuses: {message}")
        else:
            servers: List[Dict[str, str]] = response.get("servers", [])
            if not servers:
                print("  No servers found in the base directory.")
                logger.debug("CLI: No servers found to list status for.")
            else:
                logger.debug(f"CLI: Displaying status for {len(servers)} servers.")
                for server_data in servers:
                    name = server_data.get("name", "N/A")
                    status = server_data.get(
                        "status", "UNKNOWN"
                    ).upper()  # Normalize status case
                    version = server_data.get("version", "UNKNOWN")

                    # Color mapping for status
                    status_color = Fore.RED
                    if status == "RUNNING":
                        status_color = Fore.GREEN
                    elif status in ("STARTING", "RESTARTING", "STOPPING"):
                        status_color = Fore.YELLOW
                    elif status == "INSTALLED":
                        status_color = Fore.BLUE
                    elif status == "STOPPED":
                        status_color = Fore.RED

                    status_str = f"{status_color}{status:<10}{Style.RESET_ALL}"  # Fixed width for status name

                    version_color = Fore.WHITE if version != "UNKNOWN" else Fore.RED
                    version_str = f"{version_color}{version}{Style.RESET_ALL}"

                    # Print formatted row
                    print(
                        f"  {Fore.CYAN}{name:<23}{Style.RESET_ALL} {status_str:<29} {version_str:<15}"
                    )

        print("-" * 65)
        print()  # Add a blank line after the table
        # --- End User Interaction ---

    except Exception as e:
        # Catch unexpected errors during the API call or processing
        print(
            f"{_ERROR_PREFIX}An unexpected error occurred while listing server status: {e}"
        )
        logger.error(f"CLI: Unexpected error listing server status: {e}", exc_info=True)


def list_servers_loop(
    base_dir: Optional[str] = None, config_dir: Optional[str] = None
) -> None:
    """
    Continuously clears the screen and lists servers with their statuses every 5 seconds.

    Exits on KeyboardInterrupt (Ctrl+C).

    Args:
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        config_dir: Optional. Base directory for server configs. Uses default if None.
    """
    logger.debug("CLI: Starting server status monitoring loop.")
    try:
        while True:
            try:
                # Clear screen
                os.system("cls" if platform.system() == "Windows" else "clear")
                # List statuses (handles its own printing and logging)
                list_servers_status(base_dir, config_dir)
                # Wait
                time.sleep(5)
            except (KeyboardInterrupt, EOFError):
                # --- User Interaction: Exit Message ---
                print("\nExiting status monitor.")
                # --- End User Interaction ---
                logger.debug(
                    "Exiting server status loop due to KeyboardInterrupt or EOFError."
                )
                break  # Exit the loop
            except Exception as loop_err:
                # Log errors occurring within the loop but allow loop to continue (or break?)
                print(
                    f"\n{_ERROR_PREFIX}Error during status update: {loop_err}. Retrying..."
                )
                logger.error(
                    f"Error within server status loop: {loop_err}", exc_info=True
                )
                time.sleep(5)  # Wait before retrying after error
    except Exception as setup_err:
        # Catch errors during initial setup before the loop starts
        print(
            f"{_ERROR_PREFIX}An unexpected error occurred starting the monitor: {setup_err}"
        )
        logger.error(
            f"CLI: Unexpected error starting status monitor loop: {setup_err}",
            exc_info=True,
        )


def attach_console(server_name: str) -> None:
    """
    CLI handler function to attach the current terminal to a server's screen session.

    (Linux-specific)

    Args:
        server_name: The name of the server whose console to attach to.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Requesting to attach console for server '{server_name}'...")
    # Platform check and user message handled by API function

    try:
        # Call the API function
        logger.debug(
            f"Calling API: api_utils.attach_to_screen_session for '{server_name}'"
        )
        response = api_utils.attach_to_screen_session(server_name)  # Returns dict
        logger.debug(f"API response from attach_to_screen_session: {response}")

        # --- User Interaction: Print Result ---
        # The API function attempts the attach, this CLI function mainly reports success/failure of the *attempt*.
        # Actual attachment happens in the user's terminal if successful.
        if response.get("status") == "error":
            message = response.get("message", "Unknown error attaching to console.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Attach console failed for '{server_name}': {message}")
        else:
            # Don't print success here, as the screen attach command takes over the terminal
            logger.debug(
                f"CLI: Screen attach command executed for '{server_name}'. User terminal should now be attached."
            )
            # If the command fails immediately (e.g., screen not found), API returns error.
            # If session doesn't exist, API also returns error.
        # --- End User Interaction ---

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call attach console API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        # Catch unexpected errors during API call
        print(
            f"{_ERROR_PREFIX}An unexpected error occurred while trying to attach: {e}"
        )
        logger.error(
            f"CLI: Unexpected error attaching console for '{server_name}': {e}",
            exc_info=True,
        )
