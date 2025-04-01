# bedrock-server-manager/bedrock_server_manager/cli/web.py
import logging
from bedrock_server_manager.utils.general import (
    _OK_PREFIX,
    _ERROR_PREFIX,
)

from bedrock_server_manager.api import web

logger = logging.getLogger("bedrock_server_manager")


def start_web_server(host=None, debug=False, mode="direct"):
    """Restores a server from a backup file."""

    print("Starting web server...")

    response = web.start_web_server(host, debug, mode)

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Web server started successfully.")


def stop_web_server():
    """Restores a server from a backup file."""

    print("Stopping web server...")

    response = web.stop_web_server()

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Web server stopeed successfully.")
