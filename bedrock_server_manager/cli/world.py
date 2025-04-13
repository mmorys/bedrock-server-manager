# bedrock-server-manager/bedrock_server_manager/cli/world.py
"""
Command-line interface functions for managing server worlds.

Provides handlers for CLI commands related to exporting the current server world
and importing/installing worlds from .mcworld files. Uses print() for user
interaction and feedback.
"""

import os
import logging
from typing import Optional, Dict, Any

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
from bedrock_server_manager.api import utils as api_utils
from bedrock_server_manager.api import world as world_api
from bedrock_server_manager.config.settings import (
    settings,
)  # Needed for default content dir
from bedrock_server_manager.error import (
    InvalidServerNameError,
    MissingArgumentError,
    FileOperationError,
)  # Added errors
from bedrock_server_manager.utils.general import (
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger("bedrock_server_manager")


def import_world_cli(
    server_name: str,
    selected_file_path: str,
    base_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> None:
    """
    CLI handler function to import (extract) a world from a .mcworld file.

    Calls the corresponding API function and prints the result. Controls whether
    the server is stopped/started based on the `stop_start_server` flag.

    Args:
        server_name: The name of the target server.
        selected_file_path: The full path to the .mcworld file to import.
        base_dir: Optional. The base directory for server installations. Uses config default if None.
        stop_start_server: If True, stop server before import and restart after if it was running.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        MissingArgumentError: If `selected_file_path` is empty.
        # API/Core errors are caught and printed.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not selected_file_path:
        raise MissingArgumentError(".mcworld file path cannot be empty.")

    filename = os.path.basename(selected_file_path)
    logger.debug(
        f"CLI: Requesting world import for server '{server_name}' from file '{filename}'. Stop/Start: {stop_start_server}"
    )
    # User feedback provided by the calling function (e.g., install_worlds) or directly if called

    try:
        # Call the API function
        logger.debug(
            f"Calling API: world_api.import_world for '{server_name}', file '{selected_file_path}'"
        )
        response: Dict[str, Any] = world_api.import_world(
            server_name,
            selected_file_path,
            base_dir,
            stop_start_server=stop_start_server,
        )  # API func returns dict
        logger.debug(f"API response from import_world: {response}")

        # --- User Interaction: Print Result ---
        if response.get("status") == "error":
            message = response.get("message", "Unknown error importing world.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: World import failed for '{server_name}': {message}")
        else:
            message = response.get(
                "message", f"World '{filename}' imported successfully."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: World import successful for '{server_name}'.")
        # --- End User Interaction ---

    except (
        InvalidServerNameError,
        MissingArgumentError,
        FileNotFoundError,
        FileOperationError,
    ) as e:
        # Catch errors raised directly by API func setup
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call import world API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        # Catch unexpected errors during API call
        print(f"{_ERROR_PREFIX}An unexpected error occurred during world import: {e}")
        logger.error(
            f"CLI: Unexpected error importing world for '{server_name}': {e}",
            exc_info=True,
        )


def export_world(
    server_name: str, base_dir: Optional[str] = None, export_dir: Optional[str] = None
) -> None:
    """
    CLI handler function to export the current world of a server to a .mcworld file.

    Calls the corresponding API function and prints the result, including the path
    to the exported file on success.

    Args:
        server_name: The name of the server whose world to export.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        export_dir: Optional. Directory to save the exported file. Uses BACKUP_DIR default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        # API/Core errors are caught and printed.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Requesting world export for server '{server_name}'.")
    print(f"{_INFO_PREFIX}Attempting to export world for server '{server_name}'...")

    try:
        # Call the API function
        logger.debug(f"Calling API: world_api.export_world for '{server_name}'")
        response: Dict[str, Any] = world_api.export_world(
            server_name, base_dir, export_dir
        )  # API func returns dict
        logger.debug(f"API response from export_world: {response}")

        # --- User Interaction: Print Result ---
        if response.get("status") == "error":
            message = response.get("message", "Unknown error exporting world.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: World export failed for '{server_name}': {message}")
        else:
            export_file = response.get("export_file", "UNKNOWN_PATH")
            message = response.get(
                "message", f"World exported successfully to: {export_file}"
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(
                f"CLI: World export successful for '{server_name}'. File: {export_file}"
            )
        # --- End User Interaction ---

    except (InvalidServerNameError, FileOperationError) as e:
        # Catch setup errors raised directly by API func
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call export world API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        # Catch unexpected errors during API call
        print(f"{_ERROR_PREFIX}An unexpected error occurred during world export: {e}")
        logger.error(
            f"CLI: Unexpected error exporting world for '{server_name}': {e}",
            exc_info=True,
        )


def install_worlds(
    server_name: str, base_dir: Optional[str] = None, content_dir: Optional[str] = None
) -> None:
    """
    CLI handler function to present a menu for selecting and installing a .mcworld file.

    Lists available worlds, prompts for selection, confirms overwrite, and calls the
    import world handler.

    Args:
        server_name: The name of the target server.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        content_dir: Optional. Directory containing .mcworld files. Uses default content/worlds if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        FileOperationError: If base or content directory cannot be determined.
        # API/Core errors are caught and printed.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Starting interactive world installation for server '{server_name}'."
    )
    try:
        # Resolve directories
        effective_base_dir = get_base_dir(base_dir)
        effective_content_dir: str
        if content_dir:
            effective_content_dir = content_dir
        else:
            content_base = settings.get("CONTENT_DIR")
            if not content_base:
                raise FileOperationError("CONTENT_DIR setting is missing.")
            effective_content_dir = os.path.join(content_base, "worlds")

        logger.debug(f"Using base directory: {effective_base_dir}")
        logger.debug(f"Using world content directory: {effective_content_dir}")

        # API call to list available .mcworld files
        logger.debug("Calling API: api_utils.list_content_files for worlds")
        list_response = api_utils.list_content_files(
            effective_content_dir, ["mcworld"]
        )  # Returns dict
        logger.debug(f"API list_content_files response: {list_response}")

        if list_response.get("status") == "error":
            message = list_response.get("message", "Unknown error listing world files.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Failed to list world files: {message}")
            return  # Cannot proceed without file list

        mcworld_file_paths = list_response.get("files", [])
        if not mcworld_file_paths:
            print(
                f"{_INFO_PREFIX}No world files (.mcworld) found in '{effective_content_dir}'."
            )
            logger.warning(
                f"No world files found in content directory '{effective_content_dir}'."
            )
            return

        # --- User Interaction: World Selection Menu ---
        file_basenames = [os.path.basename(f) for f in mcworld_file_paths]
        num_files = len(file_basenames)
        cancel_option_num = num_files + 1

        print(f"\n{Fore.MAGENTA}Available worlds to install:{Style.RESET_ALL}")
        for i, name in enumerate(file_basenames):
            print(f"  {i + 1}. {name}")
        print(f"  {cancel_option_num}. Cancel")

        selected_file_path: Optional[str] = None
        while True:
            try:
                choice_str = input(
                    f"{Fore.CYAN}Select a world to install (1-{cancel_option_num}):{Style.RESET_ALL} "
                ).strip()
                choice = int(choice_str)
                logger.debug(f"User choice for world selection: {choice}")
                if 1 <= choice <= num_files:
                    selected_file_path = mcworld_file_paths[choice - 1]
                    logger.debug(f"User selected world file: {selected_file_path}")
                    break  # Valid choice
                elif choice == cancel_option_num:
                    print(f"{_INFO_PREFIX}World installation canceled.")
                    logger.debug("User canceled world installation at file selection.")
                    return  # Exit function
                else:
                    print(
                        f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose a valid option."
                    )
            except ValueError:
                print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
                logger.debug(
                    f"User entered non-numeric input for world selection: '{choice_str}'"
                )
        # --- End User Interaction ---

        # --- User Interaction: Overwrite Confirmation ---
        print(
            f"\n{_WARN_PREFIX}Warning: Installing '{os.path.basename(selected_file_path)}' will REPLACE the current world directory for server '{server_name}'!"
        )
        while True:
            confirm_str = (
                input(
                    f"{Fore.RED}Are you sure you want to proceed? (yes/no):{Style.RESET_ALL} "
                )
                .strip()
                .lower()
            )
            logger.debug(f"User confirmation for world overwrite: '{confirm_str}'")
            if confirm_str in ("yes", "y"):
                break  # Confirmed
            elif confirm_str in ("no", "n", ""):
                print(f"{_INFO_PREFIX}World installation canceled.")
                logger.debug("User canceled world installation at confirmation.")
                return  # Exit function
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")
        # --- End User Interaction ---

        # Call the import world CLI handler (which calls API and prints result)
        print(f"{_INFO_PREFIX}Installing selected world...")
        # Use the CLI handler function which already includes API call and printing
        import_world_cli(
            server_name, selected_file_path, effective_base_dir
        )  # stop/start defaults True

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to prepare for world installation: {e}", exc_info=True
        )
    except Exception as e:
        # Catch unexpected errors during preparation
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error during world installation setup: {e}", exc_info=True
        )
