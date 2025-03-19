# bedrock-server-manager/bedrock_server_manager/web/utils/server_actions.py
import os
import time
from bedrock_server_manager.core.server import server as server_core
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.core.download import downloader
from bedrock_server_manager.core.error import InstallUpdateError, InvalidServerNameError
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
)
from bedrock_server_manager.config.settings import settings


def start_server_action(server_name, base_dir=None):
    """Starts a server and returns a message."""
    try:
        base_dir = get_base_dir(base_dir)
        bedrock_server = server_core.BedrockServer(
            server_name, os.path.join(base_dir, server_name)
        )
        bedrock_server.start()
        return f"Server '{server_name}' started successfully."
    except Exception as e:
        return f"Error starting server '{server_name}': {e}"


def stop_server_action(server_name, base_dir=None):
    """Stops a server and returns a message."""
    try:
        base_dir = get_base_dir(base_dir)
        bedrock_server = server_core.BedrockServer(
            server_name, os.path.join(base_dir, server_name)
        )
        bedrock_server.stop()
        return f"Server '{server_name}' stopped successfully."
    except Exception as e:
        return f"Error stopping server '{server_name}': {e}"


def restart_server_action(server_name, base_dir=None):
    """Restarts a server and returns a message."""
    try:
        base_dir = get_base_dir(base_dir)
        message = stop_server_action(
            server_name, base_dir
        )  # Stop server first, reuse stop_server_action
        if (
            "Error" in message
        ):  # Check if stop action was successful, if not, return error message directly
            return message
        time.sleep(5)  # Give server a short delay to fully stop
        message = start_server_action(
            server_name, base_dir
        )  # Start server again, reuse start_server_action
        if (
            "Error" in message
        ):  # Check if start action was successful, if not, return error message
            return message
        return f"Server '{server_name}' restarted successfully."  # If both stop and start are successful, return success message
    except Exception as e:
        return f"Error restarting server '{server_name}': {e}"


def update_server_action(server_name, base_dir=None):
    """Updates a server and returns a message."""
    try:

        from bedrock_server_manager.cli import update_server

        base_dir = get_base_dir(base_dir)
        update_server(server_name, base_dir)
        return f"Server '{server_name}' update process initiated for '{server_name}'. Check console logs for details."
    except Exception as e:
        return f"Error initiating update process for '{server_name}': {e}"


def install_new_server_action(
    server_name, target_version, base_dir=None, config_dir=None
):
    """Installs a new server, handling download and setup, then returns data for configuration."""
    try:
        base_dir = get_base_dir(base_dir)
        if not config_dir:
            config_dir = settings.get("CONFIG_DIR")

        server_dir = os.path.join(base_dir, server_name)
        if os.path.exists(server_dir):
            return f"Error: Server '{server_name}' already exists."

        try:
            current_version, zip_file, download_dir = (
                downloader.download_bedrock_server(server_dir, target_version)
            )
        except Exception as e:
            return f"Download failed: {e}"

        try:
            server_core.install_server(
                server_name,
                base_dir,
                current_version,
                zip_file,
                server_dir,
                in_update=False,
            )
        except Exception as e:
            return f"Installation failed: {e}"

        # After successful download and extraction, get initial properties
        initial_properties = get_server_properties(server_name, base_dir)

        # Return the server_name and properties for configuration
        return {
            "server_name": server_name,
            "properties": initial_properties,  # Return the dictionary!
        }

    except Exception as e:
        return f"Error during server setup: {e}"


def get_server_properties(server_name, base_dir=None):
    """Retrieves server properties as a dictionary."""
    base_dir = get_base_dir(base_dir)
    server_dir = os.path.join(base_dir, server_name)
    server_properties_path = os.path.join(server_dir, "server.properties")

    properties = {}
    try:
        with open(server_properties_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line:
                    key, value = line.split("=", 1)
                    properties[key] = value
    except OSError as e:
        return {}
    return properties
