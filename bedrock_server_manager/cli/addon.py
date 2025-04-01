# bedrock-server-manager/bedrock_server_manager/cli/addon.py
import os
import logging
from colorama import Fore, Style
from bedrock_server_manager.api import addon
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.api.utils import list_content_files
from bedrock_server_manager.error import (
    MissingArgumentError,
    InvalidServerNameError,
)
from bedrock_server_manager.utils.general import (
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger("bedrock_server_manager")


def import_addon(server_name, addon_file, base_dir=None):
    """Handles the installation of an addon, including stopping/starting the server."""

    if not server_name:
        raise InvalidServerNameError("import_addon: server_name is empty.")

    response = addon.import_addon(server_name, addon_file, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Addon installed successfully.")


def install_addons(server_name, base_dir, content_dir=None):
    """Installs addons (.mcaddon or .mcpack files) to the server."""

    if not server_name:
        raise InvalidServerNameError("install_addons: server_name is empty.")

    base_dir = get_base_dir(base_dir)
    if content_dir is None:
        content_dir = os.path.join(settings.get("CONTENT_DIR"), "addons")

    # Use api to list files
    list_response = list_content_files(content_dir, ["mcaddon", "mcpack"])
    if list_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{list_response['message']}")
        return

    addon_files = list_response["files"]
    show_addon_selection_menu(server_name, addon_files, base_dir)


def show_addon_selection_menu(server_name, addon_files, base_dir):
    """Displays the addon selection menu and processes the selected addon."""

    if not server_name:
        raise InvalidServerNameError("show_addon_selection_menu: server_name is empty.")
    if not addon_files:
        raise MissingArgumentError(
            "show_addon_selection_menu: addon_files array is empty."
        )

    addon_names = [os.path.basename(file) for file in addon_files]

    print(f"{_INFO_PREFIX}Available addons to install:{Style.RESET_ALL}")
    for i, addon_name in enumerate(addon_names):
        print(f"{i + 1}. {addon_name}")
    print(f"{len(addon_names) + 1}. Cancel")  # Add cancel option

    while True:
        try:
            choice = int(
                input(
                    f"{Fore.CYAN}Select an addon to install (1-{len(addon_names) + 1}):{Style.RESET_ALL} "
                ).strip()
            )
            if 1 <= choice <= len(addon_names):
                selected_addon = addon_files[choice - 1]  # Use passed in files
                break  # Valid choice
            elif choice == len(addon_names) + 1:
                print(f"{_INFO_PREFIX}Addon installation canceled.")
                return  # User canceled
            else:
                print(f"{_WARN_PREFIX}Invalid selection. Please choose a valid option.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    # Use the to install the addon
    install_response = addon.import_addon(
        server_name, selected_addon, base_dir
    )  # Always stop/start
    if install_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{install_response['message']}")
    else:
        print(f"{_OK_PREFIX}Addon installed successfully.")
