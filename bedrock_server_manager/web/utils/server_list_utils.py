# bedrock-server-manager/bedrock_server_manager/web/utils/server_list_utils.py
import os
import glob
from bedrock_server_manager.core.server import server as server_core
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config import settings


def get_server_status_list(base_dir=None, config_dir=None):
    """Lists the status and version of all servers and returns data for web app."""

    base_dir = get_base_dir(base_dir)
    if config_dir is None:
        config_dir = settings.CONFIG_DIR

    server_data = []  # Initialize list to hold server data

    if not os.path.isdir(base_dir):
        return [
            {"server_name": "Error", "status": "Base directory not found"}
        ]  # Return error in data format

    found_servers = False
    for server_path in glob.glob(os.path.join(base_dir, "*")):  # Find directories
        if os.path.isdir(server_path):
            server_name = os.path.basename(server_path)

            status = "UNKNOWN"  # Default status if retrieval fails
            version = "UNKNOWN"  # Default version if retrieval fails

            status = server_core.get_server_status_from_config(server_name, config_dir)
            version = server_core.get_installed_version(server_name, config_dir)

            server_data.append(
                {  # Append server data as dictionary
                    "server_name": server_name,
                    "status": status,
                    "version": version,
                }
            )
            found_servers = True

    if not found_servers:
        return [
            {"server_name": "Info", "status": "No servers found"}
        ]  # Return info in data format

    return server_data  # Return the list of server data
