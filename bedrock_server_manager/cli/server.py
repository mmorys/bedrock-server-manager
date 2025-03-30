# bedrock-server-manager/bedrock_server_manager/cli/server.py
import logging
from colorama import Fore, Style
from bedrock_server_manager.api import server
from bedrock_server_manager.core.error import (
    InvalidServerNameError,
)
from bedrock_server_manager.utils.general import (
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger("bedrock_server_manager")


def start_server(server_name, base_dir=None):
    """Starts the Bedrock server."""
    if not server_name:
        raise InvalidServerNameError("start_server: server_name is empty.")

    response = server.start_server(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Server started successfully.")


def systemd_start(server_name, base_dir=None):
    """Starts the Bedrock server."""
    if not server_name:
        raise InvalidServerNameError("start_server: server_name is empty.")

    response = server.systemd_start_server(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Server started successfully.")


def stop_server(server_name, base_dir=None):
    """Stops the Bedrock server."""
    if not server_name:
        raise InvalidServerNameError("stop_server: server_name is empty.")

    response = server.stop_server(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Server stopped successfully.")


def systemd_stop(server_name, base_dir=None):
    """Stops the Bedrock server."""

    if not server_name:
        raise InvalidServerNameError("start_server: server_name is empty.")

    response = server.systemd_stop_server(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Server stopped successfully.")


def restart_server(server_name, base_dir=None):
    """Restarts the Bedrock server."""
    if not server_name:
        raise InvalidServerNameError("restart_server: server_name is empty.")

    response = server.restart_server(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Server restarted successfully.")


def send_command(server_name, command, base_dir=None):
    """Handles sending a command."""

    response = server.send_command(server_name, command, base_dir)

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
        return
    print("Command sent successfully.")


def delete_server(server_name, base_dir=None, config_dir=None):
    """Deletes a Bedrock server."""
    base_dir = get_base_dir(base_dir)

    if not server_name:
        raise InvalidServerNameError("delete_server: server_name is empty.")

    # Confirm deletion
    confirm = (
        input(
            f"{Fore.RED}Are you sure you want to delete the server {Fore.YELLOW}{server_name}{Fore.RED}? This action is irreversible! (y/n):{Style.RESET_ALL} "
        )
        .lower()
        .strip()
    )
    if confirm not in ("y", "yes"):
        print(f"{_INFO_PREFIX}Server deletion canceled.")
        return

    # Delete server data
    response = server.delete_server_data(server_name, base_dir, config_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Server {server_name} deleted successfully.")
