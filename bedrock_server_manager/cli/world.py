# bedrock-server-manager/bedrock_server_manager/cli/world.py
import os
import logging
from colorama import Fore, Style
from bedrock_server_manager.api import utils as api_utils
from bedrock_server_manager.api import world
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.core.error import InvalidServerNameError
from bedrock_server_manager.utils.general import (
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger("bedrock_server_manager")


def extract_world(server_name, selected_file, base_dir=None, from_addon=False):
    """Handles extracting a world, including stopping/starting the server."""

    if not server_name:
        raise InvalidServerNameError("extract_world: server_name is empty")

    # Call the api, controlling stop/start based on from_addon
    response = world.import_world(
        server_name, selected_file, base_dir, stop_start_server=not from_addon
    )
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}World extracted successfully.")


def export_world(server_name, base_dir=None):
    """Handles exporting the world."""
    if not server_name:
        raise InvalidServerNameError("export_world: server_name is empty.")

    response = world.export_world(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}World exported successfully to: {response['export_file']}")


def install_worlds(server_name, base_dir=None, content_dir=None):
    """Provides a menu to select and install .mcworld files."""
    if not server_name:
        raise InvalidServerNameError("install_worlds: server_name is empty.")

    base_dir = get_base_dir(base_dir)
    if content_dir is None:
        content_dir = settings.get("CONTENT_DIR")
        content_dir = os.path.join(content_dir, "worlds")

    # List files
    list_response = api_utils.list_content_files(content_dir, ["mcworld"])
    if list_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{list_response['message']}")
        return

    mcworld_files = list_response["files"]

    # Create a list of base file names
    file_names = [os.path.basename(file) for file in mcworld_files]

    # Display the menu and get user selection
    print(f"{Fore.MAGENTA}Available worlds to install:{Style.RESET_ALL}")
    for i, file_name in enumerate(file_names):
        print(f"{i + 1}. {file_name}")
    print(f"{len(file_names) + 1}. Cancel")

    while True:
        try:
            choice = int(
                input(
                    f"{Fore.CYAN}Select a world to install (1-{len(file_names) + 1}):{Style.RESET_ALL} "
                ).strip()
            )
            if 1 <= choice <= len(file_names):
                selected_file = mcworld_files[choice - 1]
                break  # Valid choice
            elif choice == len(file_names) + 1:
                print(f"{_INFO_PREFIX}World installation canceled.")
                return  # User canceled
            else:
                print(f"{_WARN_PREFIX}Invalid selection. Please choose a valid option.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    # Confirm deletion of existing world.
    print(f"{_WARN_PREFIX}Installing a new world will DELETE the existing world!")
    while True:
        confirm_choice = (
            input(
                f"{Fore.RED}Are you sure you want to proceed? (y/n):{Style.RESET_ALL} "
            )
            .lower()
            .strip()
        )
        if confirm_choice in ("yes", "y"):
            break
        elif confirm_choice in ("no", "n"):
            print(f"{_INFO_PREFIX}World installation canceled.")
            return  # User canceled
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

    # Extract the world
    extract_response = world.import_world(
        server_name, selected_file, base_dir
    )  # Always stop/start
    if extract_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{extract_response['message']}")
    else:
        print(f"{_OK_PREFIX}World extracted successfully.")
