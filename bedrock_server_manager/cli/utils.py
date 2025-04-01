# bedrock-server-manager/bedrock_server_manager/cli/utils.py
import os
import time
import logging
import platform
from colorama import Fore, Style
from bedrock_server_manager.api import utils
from bedrock_server_manager.utils.general import (
    _OK_PREFIX,
    _ERROR_PREFIX,
)
from bedrock_server_manager.error import (
    InvalidServerNameError,
)

logger = logging.getLogger("bedrock_server_manager")


def get_server_name(base_dir=None):
    """Prompts the user for a server name and validates its existence.

    Args:
        base_dir (str): The base directory for servers.

    Returns:
        str: The validated server name, or None if the user cancels.
    """

    while True:
        server_name = input(
            f"{Fore.MAGENTA}Enter server name (or type 'exit' to cancel): {Style.RESET_ALL}"
        ).strip()

        if server_name.lower() == "exit":
            print(f"{_OK_PREFIX}Operation canceled.")
            return None  # User canceled

        response = utils.validate_server_exist(server_name, base_dir)

        if response["status"] == "success":
            print(f"{_OK_PREFIX}Server {server_name} found.")
            return server_name
        else:
            print(f"{_ERROR_PREFIX}{response['message']}")


def list_servers_status(base_dir=None, config_dir=None):
    """Lists the status and version of all servers."""

    response = utils.get_all_servers_status(base_dir, config_dir)

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
        return

    servers = response["servers"]

    print(f"{Fore.MAGENTA}Servers Status:{Style.RESET_ALL}")
    print("---------------------------------------------------")
    print(f"{'SERVER NAME':<20} {'STATUS':<20} {'VERSION':<10}")
    print("---------------------------------------------------")

    if not servers:
        print("No servers found.")
    else:
        for server_data in servers:
            status = server_data["status"]
            version = server_data["version"]

            if status == "RUNNING":
                status_str = f"{Fore.GREEN}{status}{Style.RESET_ALL}"
            elif status in ("STARTING", "RESTARTING", "STOPPING", "INSTALLED"):
                status_str = f"{Fore.YELLOW}{status}{Style.RESET_ALL}"
            elif status == "STOPPED":
                status_str = f"{Fore.RED}{status}{Style.RESET_ALL}"
            else:
                status_str = f"{Fore.RED}UNKNOWN{Style.RESET_ALL}"

            version_str = (
                f"{Fore.WHITE}{version}{Style.RESET_ALL}"
                if version != "UNKNOWN"
                else f"{Fore.RED}UNKNOWN{Style.RESET_ALL}"
            )
            print(
                f"{Fore.CYAN}{server_data['name']:<20}{Style.RESET_ALL} {status_str:<20}  {version_str:<10}"
            )

    print("---------------------------------------------------")
    print()


def list_servers_loop(base_dir=None, config_dir=None):
    """Continuously lists servers and their statuses."""
    while True:
        os.system("cls" if platform.system() == "Windows" else "clear")
        list_servers_status(base_dir, config_dir)
        time.sleep(5)


def attach_console(server_name, base_dir=None):
    """Attaches to the server console."""
    if not server_name:
        raise InvalidServerNameError("attach_console: server_name is empty.")

    if platform.system() == "Linux":
        response = utils.attach_to_screen_session(server_name, base_dir)
        if response["status"] == "error":
            print(f"{_ERROR_PREFIX}{response['message']}")
    elif platform.system() == "Windows":
        print(
            "Windows doesn't currently support attaching to the console. You may want to look into Windows Subsystem for Linux (WSL)."
        )
    else:
        print("attach_console not supported on this platform")
        raise OSError("Unsupported operating system")
