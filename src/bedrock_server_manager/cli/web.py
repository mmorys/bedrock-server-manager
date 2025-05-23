# bedrock-server-manager/bedrock_server_manager/cli/web.py
"""
Command-line interface functions for managing the application's web server process.

Provides handlers for CLI commands to start the web server (directly or detached)
and potentially stop it (though stopping is not currently implemented).
Uses print() for user feedback.
"""

import logging
from typing import Optional, Dict, Any, List, Union

# Third-party imports
try:
    from colorama import Fore, Style, init

    COLORAMA_AVAILABLE = True
except ImportError:
    # Define dummy Fore, Style, init if colorama is not installed
    class DummyStyle:
        def __getattr__(self, name):
            return ""

    Fore = DummyStyle()
    Style = DummyStyle()

    def init(*args, **kwargs):
        pass


# Local imports
from bedrock_server_manager.utils.general import (
    _OK_PREFIX,
    _ERROR_PREFIX,
    _INFO_PREFIX,
)
from bedrock_server_manager.api import web as web_api

# Import errors that might be raised by API layer
from bedrock_server_manager.error import FileOperationError

logger = logging.getLogger("bedrock_server_manager")


def start_web_server(
    host: Optional[Union[str, List[str]]] = None,
    debug: bool = False,
    mode: str = "direct",
) -> None:
    """
    CLI handler function to start the application's web server.
    Calls the corresponding API function based on the specified mode.
    Args:
        host: Optional. The host address or list of addresses to bind to.
        debug: If True, run in Flask's debug mode.
        mode: Startup mode: "direct" (blocking) or "detached" (background).
    """
    logger.debug(
        f"CLI: Requesting to start web server. Host='{host}', Debug={debug}, Mode='{mode}'"
    )

    print(f"{_INFO_PREFIX}Attempting to start web server in '{mode}' mode...")
    if mode == "direct":
        print(f"{_INFO_PREFIX}Server will run in this terminal. Press Ctrl+C to stop.")

    try:
        logger.debug(
            f"Calling API: web_api.start_web_server (Host='{host}', Debug={debug}, Mode='{mode}')"
        )
        # The `host` argument passed here is now Optional[Union[str, List[str]]],
        # matching the updated signature of web_api.start_web_server
        response: Dict[str, Any] = web_api.start_web_server(host, debug, mode)
        logger.debug(f"API response from start_web_server: {response}")

        if response.get("status") == "error":
            message = response.get("message", "Unknown error starting web server.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Start web server failed: {message}")
        else:
            if mode == "detached":
                pid = response.get("pid")
                message = response.get(
                    "message",
                    f"Web server started successfully in detached mode (PID: {pid}).",
                )
                print(f"{_OK_PREFIX}{message}")
                logger.debug(
                    f"CLI: Detached web server started successfully (PID: {pid})."
                )
            else:  # direct mode
                # Message for direct mode shutdown is handled by web_api.start_web_server
                # or user sees server output directly.
                logger.info(
                    "CLI: Web server (direct mode) has started and is blocking. It will log its own shutdown or user will Ctrl+C."
                )
                pass

    except (ValueError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(f"CLI: Failed to call start web server API: {e}", exc_info=True)
    except Exception as e:
        print(
            f"{_ERROR_PREFIX}An unexpected error occurred while starting the web server: {e}"
        )
        logger.error(f"CLI: Unexpected error starting web server: {e}", exc_info=True)


def stop_web_server() -> None:
    """
    CLI handler function to stop the detached web server process.

    *** Currently Not Implemented ***
    Prints a message indicating lack of implementation.
    """
    logger.debug("CLI: Requesting to stop web server...")
    # --- User Interaction: Initial Message ---
    print(f"{_INFO_PREFIX}Attempting to stop web server...")
    # --- End User Interaction ---

    try:
        # Call the API function
        logger.debug("Calling API: web_api.stop_web_server")
        response: Dict[str, str] = web_api.stop_web_server()  # Returns dict
        logger.debug(f"API response from stop_web_server: {response}")

        # --- User Interaction: Print Result ---
        if response.get("status") == "error":
            message = response.get("message", "Unknown error stopping web server.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Stop web server failed: {message}")
        else:
            message = response.get("message", "Web server stopped successfully.")
            print(f"{_OK_PREFIX}{message}")
            logger.debug("CLI: Stop web server successful.")
        # --- End User Interaction ---

    except Exception as e:
        # Catch unexpected errors during API call
        print(
            f"{_ERROR_PREFIX}An unexpected error occurred while stopping the web server: {e}"
        )
        logger.error(f"CLI: Unexpected error stopping web server: {e}", exc_info=True)
