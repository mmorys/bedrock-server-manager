# bedrock_server_manager/cli/addon.py
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
from bedrock_server_manager.api import application as api_application
from bedrock_server_manager.error import (
    MissingArgumentError,
    InvalidServerNameError,
    FileNotFoundError,
    FileOperationError,
)
from bedrock_server_manager.utils.general import (
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger(__name__)


def import_addon(server_name: str, addon_file_path: str) -> None:
    """
    CLI handler function to install a single specified addon file.

    Calls the corresponding API function and prints the result to the console.

    Args:
        server_name: The name of the target server.
        addon_file_path: The full path to the addon file (.mcworld, .mcaddon, .mcpack).

    Raises:
        MissingArgumentError: If `addon_file_path` is empty.
        InvalidServerNameError: If `server_name` is empty.
        # Other errors from addon_api.import_addon are caught and printed.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not addon_file_path:
        raise MissingArgumentError("Addon file path cannot be empty.")

    addon_filename = os.path.basename(addon_file_path)
    logger.debug(
        f"CLI: Initiating import for addon '{addon_filename}' to server '{server_name}'."
    )
    logger.debug(f"Calling API: addon_api.import_addon with file: {addon_file_path}")

    try:
        response = addon_api.import_addon(server_name, addon_file_path)
        logger.debug(f"API response for import_addon: {response}")

        if response.get("status") == "error":
            message = response.get("message", "Unknown error during addon import.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Addon import failed for '{addon_filename}': {message}")
        else:
            message = response.get(
                "message", f"Addon '{addon_filename}' installed successfully."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Addon import successful for '{addon_filename}'.")

    except (
        MissingArgumentError,
        InvalidServerNameError,
        FileNotFoundError,
        FileOperationError,
    ) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(f"CLI: Failed to call addon import API: {e}", exc_info=True)
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(f"CLI: Unexpected error during addon import: {e}", exc_info=True)


def install_addons(server_name: str) -> None:
    """
    CLI handler function to present a menu for installing addons (.mcaddon, .mcpack).

    Lists available addons by calling the API and prompts the user for selection.

    Args:
        server_name: The name of the target server.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Initiating interactive addon installation for server '{server_name}'."
    )
    try:
        logger.debug(
            "Calling API: api_application.list_available_addons_api to get addon list."
        )
        list_response = api_application.list_available_addons_api()
        logger.debug(f"API response for list_available_addons_api: {list_response}")

        if list_response.get("status") == "error":
            message = list_response.get("message", "Unknown error listing addon files.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Failed to list addon files: {message}")
            return

        addon_file_paths = list_response.get("files", [])
        if not addon_file_paths:
            app_info_response = api_application.get_application_info_api()
            addon_dir = "the content directory"  # Fallback message
            if app_info_response.get("status") == "success":
                addon_dir = os.path.join(
                    app_info_response["data"]["content_directory"], "addons"
                )

            print(
                f"{_WARN_PREFIX}No addon files (.mcaddon, .mcpack) found in '{addon_dir}'."
            )
            logger.warning(f"No addon files found when requested by the API.")
            return

        show_addon_selection_menu(server_name, addon_file_paths)

    except InvalidServerNameError as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Prerequisite for addon installation failed: {e}", exc_info=True
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error during addon installation setup: {e}", exc_info=True
        )


def show_addon_selection_menu(server_name: str, addon_file_paths: List[str]) -> None:
    """
    Displays an interactive menu for selecting an addon file and triggers its installation.

    Args:
        server_name: The name of the target server.
        addon_file_paths: A list of full paths to the available addon files.

    Raises:
        MissingArgumentError: If `addon_file_paths` list is empty.
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not addon_file_paths:
        raise MissingArgumentError("Addon files list cannot be empty.")

    addon_basenames = [os.path.basename(file) for file in addon_file_paths]
    num_addons = len(addon_basenames)
    cancel_option_num = num_addons + 1

    logger.debug(f"Displaying addon selection menu with {num_addons} options.")
    print(f"{_INFO_PREFIX}Available addons to install:")
    for i, name in enumerate(addon_basenames):
        print(f"  {i + 1}. {name}")
    print(f"  {cancel_option_num}. Cancel Installation")

    selected_addon_path: Optional[str] = None
    while True:
        try:
            choice_str = input(
                f"{Fore.CYAN}Select an addon to install (1-{cancel_option_num}):{Style.RESET_ALL} "
            ).strip()
            choice = int(choice_str)

            if 1 <= choice <= num_addons:
                selected_addon_path = addon_file_paths[choice - 1]
                logger.debug(f"User selected addon: {selected_addon_path}")
                break
            elif choice == cancel_option_num:
                print(f"{_INFO_PREFIX}Addon installation canceled by user.")
                logger.debug("User canceled addon installation from menu.")
                return
            else:
                print(
                    f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose a number between 1 and {cancel_option_num}."
                )
                logger.debug(f"User entered invalid menu choice: {choice}")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
            logger.debug(f"User entered non-numeric input: '{choice_str}'")

    if selected_addon_path:
        print(
            f"{_INFO_PREFIX}Installing selected addon: {os.path.basename(selected_addon_path)}..."
        )
        import_addon(server_name, selected_addon_path)
    else:
        logger.error(
            "Exited addon selection loop without a valid selection or cancellation."
        )
