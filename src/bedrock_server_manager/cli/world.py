# bedrock_server_manager/cli/world.py
"""
Command-line interface functions for managing server worlds.

Provides handlers for CLI commands related to exporting, importing, and resetting
server worlds. Uses print() for user interaction and feedback.
"""

import os
import logging
from typing import Optional, Dict, Any

# Third-party imports
try:
    from colorama import Fore, Style

    COLORAMA_AVAILABLE = True
except ImportError:
    # Define dummy Fore, Style, init if colorama is not installed
    class DummyStyle:
        def __getattr__(self, name):
            return ""

    Fore = DummyStyle()
    Style = DummyStyle()


# Local imports
from bedrock_server_manager.api import application as api_application
from bedrock_server_manager.api import world as world_api
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    MissingArgumentError,
)
from bedrock_server_manager.utils.general import (
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger(__name__)


def import_world_cli(
    server_name: str,
    selected_file_path: str,
    stop_start_server: bool = True,
) -> None:
    """
    CLI handler function to import a world from a .mcworld file.

    Args:
        server_name: The name of the target server.
        selected_file_path: The full path to the .mcworld file to import.
        stop_start_server: If True, stop server before import and restart after.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not selected_file_path:
        raise MissingArgumentError(".mcworld file path cannot be empty.")

    filename = os.path.basename(selected_file_path)
    logger.debug(f"CLI: Requesting world import for '{server_name}' from '{filename}'.")

    try:
        response: Dict[str, Any] = world_api.import_world(
            server_name,
            selected_file_path,
            stop_start_server=stop_start_server,
        )
        logger.debug(f"API response from import_world: {response}")

        if response.get("status") == "error":
            message = response.get("message", "Unknown error importing world.")
            print(f"{_ERROR_PREFIX}{message}")
        else:
            message = response.get(
                "message", f"World '{filename}' imported successfully."
            )
            print(f"{_OK_PREFIX}{message}")

    except BSMError as e:
        print(f"{_ERROR_PREFIX}An application error occurred: {e}")
        logger.error(
            f"CLI: BSMError importing world for '{server_name}': {e}", exc_info=True
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred during world import: {e}")
        logger.error(
            f"CLI: Unexpected error importing world for '{server_name}': {e}",
            exc_info=True,
        )


def export_world(server_name: str) -> None:
    """
    CLI handler to export the current world of a server to a .mcworld file.

    Args:
        server_name: The name of the server whose world to export.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Requesting world export for server '{server_name}'.")
    print(f"{_INFO_PREFIX}Attempting to export world for server '{server_name}'...")

    try:
        response: Dict[str, Any] = world_api.export_world(server_name)
        logger.debug(f"API response from export_world: {response}")

        if response.get("status") == "error":
            message = response.get("message", "Unknown error exporting world.")
            print(f"{_ERROR_PREFIX}{message}")
        else:
            export_file = response.get("export_file", "UNKNOWN_PATH")
            message = response.get(
                "message", f"World exported successfully to: {export_file}"
            )
            print(f"{_OK_PREFIX}{message}")

    except BSMError as e:
        print(f"{_ERROR_PREFIX}An application error occurred: {e}")
        logger.error(
            f"CLI: BSMError exporting world for '{server_name}': {e}", exc_info=True
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred during world export: {e}")
        logger.error(
            f"CLI: Unexpected error exporting world for '{server_name}': {e}",
            exc_info=True,
        )


def install_worlds(server_name: str) -> None:
    """
    CLI handler to present a menu for selecting and installing a .mcworld file.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Starting interactive world installation for server '{server_name}'."
    )
    try:
        logger.debug("Calling API: api_application.list_available_worlds_api")
        list_response = api_application.list_available_worlds_api()
        logger.debug(f"API list_available_worlds_api response: {list_response}")

        if list_response.get("status") == "error":
            message = list_response.get("message", "Unknown error listing world files.")
            print(f"{_ERROR_PREFIX}{message}")
            return

        mcworld_file_paths = list_response.get("files", [])
        if not mcworld_file_paths:
            # Get the content directory from the API for a more informative message
            app_info = api_application.get_application_info_api()
            world_dir = "the content/worlds directory"
            if app_info.get("status") == "success":
                world_dir = os.path.join(
                    app_info["data"]["content_directory"], "worlds"
                )

            print(f"{_INFO_PREFIX}No world files (.mcworld) found in '{world_dir}'.")
            return

        file_basenames = [os.path.basename(f) for f in mcworld_file_paths]
        num_files, cancel_option_num = len(file_basenames), len(file_basenames) + 1

        print(f"\n{Fore.MAGENTA}Available worlds to install:{Style.RESET_ALL}")
        for i, name in enumerate(file_basenames):
            print(f"  {i + 1}. {name}")
        print(f"  {cancel_option_num}. Cancel")

        selected_file_path: Optional[str] = None
        while not selected_file_path:
            try:
                choice = int(
                    input(
                        f"{Fore.CYAN}Select a world (1-{cancel_option_num}):{Style.RESET_ALL} "
                    ).strip()
                )
                if 1 <= choice <= num_files:
                    selected_file_path = mcworld_file_paths[choice - 1]
                elif choice == cancel_option_num:
                    print(f"{_INFO_PREFIX}World installation canceled.")
                    return
                else:
                    print(
                        f"{_WARN_PREFIX}Invalid selection. Please choose a valid option."
                    )
            except ValueError:
                print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

        print(
            f"\n{_WARN_PREFIX}Warning: Installing '{os.path.basename(selected_file_path)}' will REPLACE the current world directory for server '{server_name}'!"
        )
        confirm_str = (
            input(f"{Fore.RED}Are you sure? (yes/no):{Style.RESET_ALL} ")
            .strip()
            .lower()
        )
        if confirm_str not in ("yes", "y"):
            print(f"{_INFO_PREFIX}World installation canceled.")
            return

        print(f"{_INFO_PREFIX}Installing selected world...")
        import_world_cli(server_name, selected_file_path)

    except BSMError as e:
        print(f"{_ERROR_PREFIX}An application error occurred: {e}")
        logger.error(
            f"CLI: BSMError during world installation setup for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(
            f"{_ERROR_PREFIX}An unexpected error occurred during world installation: {e}"
        )
        logger.error(
            f"CLI: Unexpected error during world installation setup for '{server_name}': {e}",
            exc_info=True,
        )


def reset_world_cli(server_name: str, skip_confirmation: bool = False) -> None:
    """
    CLI handler function to reset the current world of a server.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    if not skip_confirmation:
        print(
            f"{_WARN_PREFIX}You are about to delete all world data for server '{server_name}'."
        )
        print(
            f"{_WARN_PREFIX}This includes all player inventories, builds, and installed content."
        )
        confirm = (
            input(
                f"{Fore.RED}This action cannot be undone. Are you sure? (yes/no):{Style.RESET_ALL} "
            )
            .strip()
            .lower()
        )

        if confirm not in ("y", "yes"):
            print(f"{_INFO_PREFIX}World reset canceled by user.")
            return
        logger.warning(f"User confirmed world reset for server '{server_name}'.")
    else:
        logger.warning(
            f"Skipping confirmation prompt for resetting world on '{server_name}'."
        )

    print(f"{_INFO_PREFIX}Attempting to reset world for server '{server_name}'...")
    try:
        response = world_api.reset_world(server_name)
        if response.get("status") == "error":
            print(f"{_ERROR_PREFIX}{response.get('message', 'Unknown error.')}")
        else:
            print(f"{_OK_PREFIX}{response.get('message', 'World reset successfully.')}")

    except BSMError as e:
        print(f"{_ERROR_PREFIX}An application error occurred: {e}")
        logger.error(
            f"CLI: BSMError resetting world for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred during world reset: {e}")
        logger.error(
            f"CLI: Unexpected error resetting world for '{server_name}': {e}",
            exc_info=True,
        )
