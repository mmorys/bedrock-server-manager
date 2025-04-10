# bedrock-server-manager/bedrock_server_manager/cli/addon.py
"""
Command-line interface functions for managing server addons (worlds, packs).

Provides functionality triggered by CLI commands to list and install addons.
Uses print() for user-facing output and prompts.
"""

import os
import logging
from typing import Optional, List

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
from bedrock_server_manager.api import addon as addon_api
from bedrock_server_manager.api import utils as api_utils
from bedrock_server_manager.config.settings import (
    settings,
)
from bedrock_server_manager.error import (
    MissingArgumentError,
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


def import_addon(
    server_name: str, addon_file_path: str, base_dir: Optional[str] = None
) -> None:
    """
    CLI handler function to install a single specified addon file.

    Calls the corresponding API function and prints the result to the console.

    Args:
        server_name: The name of the target server.
        addon_file_path: The full path to the addon file (.mcworld, .mcaddon, .mcpack).
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Raises:
        MissingArgumentError: If `addon_file_path` is empty.
        InvalidServerNameError: If `server_name` is empty.
        FileNotFoundError: If `addon_file_path` does not exist (raised by API).
        FileOperationError: If `base_dir` cannot be determined (raised by API).
        # Other errors from addon_api.import_addon are caught and printed.
    """
    if not server_name:
        # Let CLI main handler catch this
        raise InvalidServerNameError("Server name cannot be empty.")
    if not addon_file_path:
        raise MissingArgumentError("Addon file path cannot be empty.")

    addon_filename = os.path.basename(addon_file_path)
    logger.debug(
        f"CLI: Initiating import for addon '{addon_filename}' to server '{server_name}'."
    )
    logger.debug(f"Calling API: addon_api.import_addon with file: {addon_file_path}")

    try:
        response = addon_api.import_addon(
            server_name, addon_file_path, base_dir
        )  # API function handles errors internally
        logger.debug(f"API response for import_addon: {response}")

        if response.get("status") == "error":
            message = response.get("message", "Unknown error during addon import.")
            print(f"{_ERROR_PREFIX}{message}")  # Print API error to user
            logger.error(f"CLI: Addon import failed for '{addon_filename}': {message}")
        else:
            message = response.get(
                "message", f"Addon '{addon_filename}' installed successfully."
            )
            print(f"{_OK_PREFIX}{message}")  # Print API success message
            logger.debug(f"CLI: Addon import successful for '{addon_filename}'.")

    except (
        MissingArgumentError,
        InvalidServerNameError,
        FileNotFoundError,
        FileOperationError,
    ) as e:
        # Catch errors raised directly by the API function *before* it returns a dict
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(f"CLI: Failed to call addon import API: {e}", exc_info=True)
    except Exception as e:
        # Catch unexpected errors during API call
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(f"CLI: Unexpected error during addon import: {e}", exc_info=True)


def install_addons(
    server_name: str, base_dir: Optional[str] = None, content_dir: Optional[str] = None
) -> None:
    """
    CLI handler function to present a menu for installing addons (.mcaddon, .mcpack).

    Lists available addons from the content directory and prompts the user for selection.

    Args:
        server_name: The name of the target server.
        base_dir: Optional. The base directory for server installations. Uses config default if None.
        content_dir: Optional. The directory containing addon files. Uses default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        FileOperationError: If `base_dir` or content directory cannot be determined.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Initiating interactive addon installation for server '{server_name}'."
    )
    try:
        # Resolve directories
        effective_base_dir = get_base_dir(base_dir)
        effective_content_dir: str
        if content_dir:
            effective_content_dir = content_dir
        else:
            content_base = settings.get("CONTENT_DIR")
            if not content_base:
                raise FileOperationError("CONTENT_DIR setting is missing.")
            effective_content_dir = os.path.join(content_base, "addons")

        logger.debug(f"Using base directory: {effective_base_dir}")
        logger.debug(f"Using addon content directory: {effective_content_dir}")

        # Use API to list files
        logger.debug("Calling API: api_utils.list_content_files for addons")
        list_response = api_utils.list_content_files(
            effective_content_dir, ["mcaddon", "mcpack"]
        )  # Returns dict
        logger.debug(f"List content files API response: {list_response}")

        if list_response.get("status") == "error":
            # Print API error message to user
            message = list_response.get("message", "Unknown error listing addon files.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Failed to list addon files: {message}")
            return  # Exit if files cannot be listed

        addon_file_paths = list_response.get("files", [])
        if not addon_file_paths:
            print(
                f"{_WARN_PREFIX}No addon files (.mcaddon, .mcpack) found in '{effective_content_dir}'."
            )
            logger.warning(
                f"No addon files found in content directory '{effective_content_dir}'."
            )
            return

        # Show selection menu
        show_addon_selection_menu(server_name, addon_file_paths, effective_base_dir)

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to prepare for addon installation: {e}", exc_info=True
        )
    except Exception as e:
        # Catch unexpected errors during preparation
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error during addon installation setup: {e}", exc_info=True
        )


def show_addon_selection_menu(
    server_name: str, addon_file_paths: List[str], base_dir: str
) -> None:
    """
    Displays an interactive menu for selecting an addon file and triggers its installation.

    Args:
        server_name: The name of the target server.
        addon_file_paths: A list of full paths to the available addon files.
        base_dir: The base directory for server installations.

    Raises:
        MissingArgumentError: If `addon_file_paths` list is empty.
        InvalidServerNameError: If `server_name` is empty. # Should be caught earlier but good practice
        # Errors from the import_addon call within this function are handled internally.
    """
    if not server_name:
        raise InvalidServerNameError(
            "Server name cannot be empty."
        )  # Should be caught by caller
    if not addon_file_paths:
        raise MissingArgumentError(
            "Addon files list cannot be empty."
        )  # Should be caught by caller

    addon_basenames = [os.path.basename(file) for file in addon_file_paths]
    num_addons = len(addon_basenames)
    cancel_option_num = num_addons + 1

    logger.debug(f"Displaying addon selection menu with {num_addons} options.")
    # --- User Interaction: Print Menu ---
    print(f"{_INFO_PREFIX}Available addons to install:")
    for i, name in enumerate(addon_basenames):
        print(f"  {i + 1}. {name}")
    print(f"  {cancel_option_num}. Cancel Installation")
    # --- End User Interaction ---

    selected_addon_path: Optional[str] = None
    while True:
        try:
            # --- User Interaction: Get Input ---
            choice_str = input(
                f"{Fore.CYAN}Select an addon to install (1-{cancel_option_num}):{Style.RESET_ALL} "
            ).strip()
            choice = int(choice_str)
            # --- End User Interaction ---

            if 1 <= choice <= num_addons:
                selected_addon_path = addon_file_paths[choice - 1]
                logger.debug(f"User selected addon: {selected_addon_path}")
                break  # Valid choice, exit loop
            elif choice == cancel_option_num:
                # --- User Interaction: Print Cancellation ---
                print(f"{_INFO_PREFIX}Addon installation canceled by user.")
                # --- End User Interaction ---
                logger.debug("User canceled addon installation from menu.")
                return  # Exit function
            else:
                # --- User Interaction: Print Invalid Choice ---
                print(
                    f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose a number between 1 and {cancel_option_num}."
                )
                # --- End User Interaction ---
                logger.debug(f"User entered invalid menu choice: {choice}")
        except ValueError:
            # --- User Interaction: Print Invalid Input ---
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
            # --- End User Interaction ---
            logger.debug(f"User entered non-numeric input: '{choice_str}'")
        # Loop continues for invalid input

    # If loop exited with a valid choice
    if selected_addon_path:
        print(
            f"{_INFO_PREFIX}Installing selected addon: {os.path.basename(selected_addon_path)}..."
        )
        # Call the single import function (which handles API call and printing results)
        # Pass stop_start_server=True explicitly if needed, API default is True
        import_addon(server_name, selected_addon_path, base_dir)
    else:
        # This state should not be reachable due to loop logic, but log if it occurs
        logger.error(
            "Exited addon selection loop without a valid selection or cancellation."
        )
