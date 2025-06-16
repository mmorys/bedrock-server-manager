# bedrock_server_manager/api/system.py
"""
Provides API-level functions for interacting with system-level information
and configurations related to Bedrock servers by orchestrating calls to the
BedrockServer class methods.
"""
import logging
import platform
from typing import Dict, Optional, Any

# Local imports
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    MissingArgumentError,
    UserInputError,
)

logger = logging.getLogger(__name__)


def get_bedrock_process_info(server_name: str) -> Dict[str, Any]:
    """
    Retrieves resource usage information (PID, CPU%, Memory MB, Uptime) for
    a specific running Bedrock server process.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"API: Getting process info for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)
        process_info = server.get_process_info()

        if process_info is None:
            return {
                "status": "error",
                "message": f"Server process '{server_name}' not found or information is inaccessible.",
            }
        else:
            return {"status": "success", "process_info": process_info}
    except BSMError as e:
        logger.error(
            f"API: Failed to get process info for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error getting process info: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting process info for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting process info: {e}",
        }


def create_systemd_service(server_name: str, autostart: bool = False) -> Dict[str, str]:
    """
    Creates (or updates) and optionally enables a systemd user service for the server.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    try:
        server = BedrockServer(server_name)
        # The mixin method will raise NotImplementedError on non-Linux systems.
        server.create_systemd_service_file()

        if autostart:
            server.enable_systemd_service()
            action = "created and enabled"
        else:
            server.disable_systemd_service()
            action = "created and disabled"

        return {
            "status": "success",
            "message": f"Systemd service {action} successfully.",
        }
    except NotImplementedError as e:
        return {"status": "error", "message": str(e)}
    except BSMError as e:
        logger.error(
            f"API: Failed to configure systemd service for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Failed to configure systemd service: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error creating systemd service for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error creating systemd service: {e}",
        }


def set_autoupdate(server_name: str, autoupdate_value: str) -> Dict[str, str]:
    """
    Sets the 'autoupdate' flag in the server's specific JSON configuration file.

    Args:
        server_name: The name of the server.
        autoupdate_value: String representation of boolean ('true' or 'false').

    Returns:
        A dictionary indicating success or failure.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if (
        autoupdate_value is None
    ):  # Should not happen with type hint but good for robustness
        raise MissingArgumentError("Autoupdate value cannot be empty.")

    value_lower = str(autoupdate_value).lower()  # Ensure it's a string for .lower()
    if value_lower not in ("true", "false"):
        raise UserInputError("Autoupdate value must be 'true' or 'false'.")
    value_bool = value_lower == "true"

    logger.info(
        f"API: Setting 'autoupdate' config for server '{server_name}' to {value_bool}..."
    )
    try:
        server = BedrockServer(server_name)
        server.set_custom_config_value("autoupdate", str(value_bool))
        return {
            "status": "success",
            "message": f"Autoupdate setting for '{server_name}' updated to {value_bool}.",
        }
    except BSMError as e:
        logger.error(
            f"API: Failed to set autoupdate config for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to set autoupdate config: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error setting autoupdate for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error setting autoupdate: {e}",
        }


def enable_server_service(server_name: str) -> Dict[str, str]:
    """Enables the systemd user service associated with the server for autostart."""
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    try:
        server = BedrockServer(server_name)
        server.enable_systemd_service()
        return {
            "status": "success",
            "message": f"Service for '{server_name}' enabled successfully.",
        }
    except NotImplementedError as e:
        return {"status": "error", "message": str(e)}
    except BSMError as e:
        logger.error(
            f"API: Failed to enable systemd service for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to enable service: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error enabling service for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error enabling service: {e}"}


def disable_server_service(server_name: str) -> Dict[str, str]:
    """Disables the systemd user service associated with the server from autostarting."""
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    try:
        server = BedrockServer(server_name)
        server.disable_systemd_service()
        return {
            "status": "success",
            "message": f"Service for '{server_name}' disabled successfully.",
        }
    except NotImplementedError as e:
        return {"status": "error", "message": str(e)}
    except BSMError as e:
        logger.error(
            f"API: Failed to disable systemd service for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to disable service: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error disabling service for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error disabling service: {e}",
        }
