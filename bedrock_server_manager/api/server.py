# bedrock-server-manager/bedrock_server_manager/api/server.py
import os
import logging
import time
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
)
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
    CommandNotFoundError,
    MissingArgumentError,
    ServerNotRunningError,
    SendCommandError,
)

logger = logging.getLogger("bedrock_server_manager")


def write_server_config(server_name, key, value, config_dir=None):
    """Writes a key-value pair to the server's config.

    Args:
        server_name (str): The name of the server.
        key (str): The configuration key.
        value (str): The configuration value.
        config_dir (str, optional): The config directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    logger.debug(
        f"Writing server config: server={server_name}, key={key}, value={value}"
    )
    try:
        server_base.manage_server_config(server_name, key, "write", value, config_dir)
        logger.debug(f"Successfully wrote config: {key}={value} for {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Failed to write server config: {e}")
        return {"status": "error", "message": f"Failed to write server config: {e}"}


def start_server(server_name, base_dir=None, Mode=None):
    """Starts the Bedrock server.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Starting server: {server_name}")
    if not server_name:
        raise InvalidServerNameError("start_server: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}

    if system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is already running.")
        return {"status": "error", "message": f"{server_name} is already running."}

    try:
        bedrock_server = server_base.BedrockServer(
            server_name, os.path.join(base_dir, server_name)
        )
        bedrock_server.start()  # Call start method
        logger.debug(f"Started server: {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error starting server {server_name}: {e}")
        return {
            "status": "error",
            "message": f"Failed to start server: {e}",
        }  # Provide error message


def systemd_start_server(server_name, base_dir=None):
    """Starts the Bedrock server via systemd.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Starting server via systemd: {server_name}")
    if not server_name:
        raise InvalidServerNameError("systemd_start_server: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}

    if system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is already running (systemd start).")
        return {"status": "error", "message": f"{server_name} is already running."}

    try:
        system_linux._systemd_start_server(
            server_name, os.path.join(base_dir, server_name)
        )
        logger.debug(f"Started server via systemd: {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error starting server via systemd: {e}")
        return {
            "status": "error",
            "message": f"Failed to start server via systemd: {e}",
        }


def stop_server(server_name, base_dir=None):
    """Stops the Bedrock server.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Stopping server: {server_name}")

    if not server_name:
        raise InvalidServerNameError("stop_server: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}

    if not system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is not running.")
        return {"status": "error", "message": f"{server_name} is not running."}

    try:
        bedrock_server = server_base.BedrockServer(
            server_name, os.path.join(base_dir, server_name)
        )
        bedrock_server.stop()  # Stop the server
        logger.debug(f"Stopped server: {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error stopping server {server_name}: {e}")
        return {"status": "error", "message": f"Failed to stop server: {e}"}


def systemd_stop_server(server_name, base_dir=None):
    """Stops the Bedrock server via systemd.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Stopping server via systemd: {server_name}")
    if not server_name:
        raise InvalidServerNameError("systemd_stop_server: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}

    if not system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is not running (systemd stop).")
        return {"status": "error", "message": f"{server_name} is not running."}

    try:
        system_linux._systemd_stop_server(
            server_name, os.path.join(base_dir, server_name)
        )
        logger.debug(f"Stopped server via systemd: {server_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error stopping server via systemd: {e}")
        return {"status": "error", "message": f"Failed to stop server via systemd: {e}"}


def restart_server(server_name, base_dir=None, send_message=True):
    """Restarts the Bedrock server.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory.  Defaults to None.
        send_message (bool, optional): Whether to send an in-game message.
            Defaults to True.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Restarting server: {server_name}")
    if not server_name:
        raise InvalidServerNameError("restart_server: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}

    if not system_base.is_server_running(server_name, base_dir):
        logger.info(f"{server_name} is not running, starting it.")
        #  If not running, just start it.  Don't return an error.
        return start_server(server_name, base_dir)

    logger.info(f"Restarting {server_name}...")

    # Send restart message
    if send_message:
        try:
            bedrock_server = server_base.BedrockServer(server_name, base_dir)
            bedrock_server.send_command("say Restarting server in 10 seconds..")
            logger.info(f"Sent restart warning to server: {server_name}")
            time.sleep(10)
        except Exception as e:
            #  Don't fail the entire restart if sending the message fails.
            logger.warning(f"Failed to send message to server: {e}")

    # Stop and then start the server.
    stop_result = stop_server(server_name, base_dir)
    if stop_result["status"] == "error":
        return stop_result

    # Small delay before restarting
    time.sleep(2)

    start_result = start_server(server_name, base_dir)
    if start_result["status"] == "error":
        return start_result
    logger.debug(f"Restarted server: {server_name}")
    return {"status": "success"}


def send_command(server_name, command, base_dir=None):
    """Sends a command to the running Bedrock server.

    Args:
        server_name (str): The name of the server.
        command (str): The command to send.
        base_dir (str, optional): The base directory. Defaults to None.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Sending command to {server_name}: {command}")
    try:
        bedrock_server = server_base.BedrockServer(
            server_name, os.path.join(base_dir, server_name)
        )
        bedrock_server.send_command(command)
        logger.debug(f"Command sent to {server_name}: {command}")
        return {"status": "success"}
    except (
        MissingArgumentError,
        ServerNotRunningError,
        SendCommandError,
        CommandNotFoundError,
    ) as e:
        # Catch all the exceptions that BedrockServer.send_command can raise
        logger.error(f"Error sending command to {server_name}: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:  # also catch unexpected exceptions
        logger.exception(f"Unexpected error sending command to {server_name}: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def delete_server_data(
    server_name, base_dir=None, config_dir=None, stop_if_running=True
):
    """Deletes a Bedrock server's data.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): The base directory. Defaults to None.
        config_dir (str, optional): The config directory. Defaults to main config dir.
        stop_if_running (bool, optional): Whether to stop the server if its running.

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Deleting server data for: {server_name}")
    if not server_name:
        raise InvalidServerNameError("delete_server_data: server_name is empty.")
        # return {"status": "error", "message": "Server name cannot be empty."}

    # Stop the server if it's running
    if stop_if_running and system_base.is_server_running(server_name, base_dir):
        logger.info(f"Stopping server {server_name} before deletion...")
        stop_result = stop_server(server_name, base_dir)
        if stop_result["status"] == "error":
            return stop_result  # Return the error from stop_server

    try:
        server_base.delete_server_data(server_name, base_dir, config_dir)
        logger.info(f"Server data deleted for: {server_name}")
        return {"status": "success"}
    except FileOperationError as e:  # Catch specific exceptions
        logger.exception(f"Error deleting server data for {server_name}: {e}")
        return {"status": "error", "message": f"Error deleting server data: {e}"}
    except Exception as e:
        logger.exception(
            f"Unexpected error deleting server data for {server_name}: {e}"
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
