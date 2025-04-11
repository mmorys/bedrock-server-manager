# bedrock-server-manager/bedrock_server_manager/cli/backup_restore.py
"""
Command-line interface functions for handling server backup and restore operations.

Provides user interaction menus and calls corresponding API functions to perform
backup, restore, and pruning tasks. Uses print() for user feedback.
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
from bedrock_server_manager.api import (
    backup_restore as backup_restore_api,
)
from bedrock_server_manager.utils.general import (
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)
from bedrock_server_manager.error import (
    MissingArgumentError,
    InvalidServerNameError,
    InvalidInputError,
    FileOperationError,
)

logger = logging.getLogger("bedrock_server_manager")


def prune_old_backups(
    server_name: str,
    backup_keep: Optional[int] = None,
    base_dir: Optional[str] = None,
) -> None:
    """
    CLI handler function to prune old backups for a server.

    Calls the corresponding API function and prints the result.

    Args:
        server_name: The name of the server whose backups to prune.
        backup_keep: Optional. Number of backups to keep. Uses config default if None.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        ValueError: If `backup_keep` is not a valid integer (raised by API).
        FileOperationError: If config settings are missing (raised by API).
        # Other API errors are caught and printed
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Initiating prune old backups for server '{server_name}', Keep: {backup_keep}"
    )
    logger.debug(f"Calling API: backup_restore_api.prune_old_backups")

    try:
        # API function handles None for backup_keep and base_dir correctly
        response = backup_restore_api.prune_old_backups(
            server_name=server_name, backup_keep=backup_keep, base_dir=base_dir
        )
        logger.debug(f"API response for prune_old_backups: {response}")

        # --- User Interaction: Print Result ---
        if response.get("status") == "error":
            message = response.get("message", "Unknown error during pruning.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Pruning backups failed for '{server_name}': {message}")
        else:
            message = response.get("message", "Old backups pruned successfully.")
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Pruning backups successful for '{server_name}'.")
        # --- End User Interaction ---

    except (InvalidServerNameError, ValueError, FileOperationError) as e:
        # Catch errors raised directly by the API call setup
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(f"CLI: Failed to call prune backups API: {e}", exc_info=True)
    except Exception as e:
        # Catch unexpected errors during API call
        print(f"{_ERROR_PREFIX}An unexpected error occurred during pruning: {e}")
        logger.error(f"CLI: Unexpected error during backup pruning: {e}", exc_info=True)


def backup_server(
    server_name: str,
    backup_type: str,
    file_to_backup: Optional[str] = None,
    change_status: bool = True,  # Corresponds to stop_start_server in API
    base_dir: Optional[str] = None,
) -> None:
    """
    CLI handler function to back up a server's world, a specific config file, or all.

    Calls the appropriate API backup function and handles pruning afterwards.

    Args:
        server_name: The name of the server.
        backup_type: Type of backup ("world", "config", "all").
        file_to_backup: Relative path of config file if `backup_type` is "config".
        change_status: If True, stop/start server if needed for the backup type.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        MissingArgumentError: If `backup_type` or required `file_to_backup` is empty.
        InvalidServerNameError: If `server_name` is empty.
        InvalidInputError: If `backup_type` is invalid.
        # API errors are caught and printed.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not backup_type:
        raise MissingArgumentError("Backup type cannot be empty.")

    backup_type_norm = backup_type.lower()
    logger.debug(
        f"CLI: Initiating '{backup_type_norm}' backup for server '{server_name}'. Change Status: {change_status}"
    )

    response: Optional[Dict[str, Any]] = None
    try:
        # --- Call appropriate API function ---
        if backup_type_norm == "world":
            logger.debug("Calling API: backup_restore_api.backup_world")
            response = backup_restore_api.backup_world(
                server_name, base_dir, stop_start_server=change_status
            )
        elif backup_type_norm == "config":
            if not file_to_backup:
                raise MissingArgumentError(
                    "File path is required for config backup type."
                )
            logger.debug(
                f"Calling API: backup_restore_api.backup_config_file for file '{file_to_backup}'"
            )
            response = backup_restore_api.backup_config_file(
                server_name, file_to_backup, base_dir, stop_start_server=change_status
            )
        elif backup_type_norm == "all":
            logger.debug("Calling API: backup_restore_api.backup_all")
            response = backup_restore_api.backup_all(
                server_name, base_dir, stop_start_server=change_status
            )
        else:
            # Raise error for invalid type passed from CLI command parsing
            raise InvalidInputError(
                f"Invalid backup type specified: '{backup_type}'. Must be 'world', 'config', or 'all'."
            )

        logger.debug(f"API response for backup_{backup_type_norm}: {response}")

        # --- User Interaction: Print Backup Result ---
        if response and response.get("status") == "error":
            message = response.get(
                "message", f"Unknown error during '{backup_type_norm}' backup."
            )
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(
                f"CLI: Backup type '{backup_type_norm}' failed for '{server_name}': {message}"
            )
            return
        else:
            message = response.get(
                "message", f"Backup type '{backup_type_norm}' completed successfully."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(
                f"CLI: Backup type '{backup_type_norm}' successful for '{server_name}'."
            )
        # --- End User Interaction ---

        # --- Prune old backups automatically after successful backup ---
        logger.debug(
            f"CLI: Pruning old backups for '{server_name}' after successful '{backup_type_norm}' backup."
        )
        prune_file = (
            file_to_backup if backup_type_norm == "config" else None
        )  # Only pass filename if config was backed up
        # Call the CLI prune function (which handles API call and printing results)
        prune_old_backups(server_name=server_name, base_dir=base_dir, backup_keep=None)
        # Note: prune_old_backups has its own try/except and printing

    except (MissingArgumentError, InvalidServerNameError, InvalidInputError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to initiate backup for '{server_name}': {e}", exc_info=True
        )
    except Exception as e:
        # Catch unexpected errors calling the API
        print(f"{_ERROR_PREFIX}An unexpected error occurred during backup: {e}")
        logger.error(
            f"CLI: Unexpected error during '{backup_type_norm}' backup for '{server_name}': {e}",
            exc_info=True,
        )


def backup_menu(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    Displays an interactive backup menu for the user to choose backup type.

    Args:
        server_name: The name of the server.
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Displaying backup menu for server '{server_name}'.")
    while True:
        # --- User Interaction: Print Menu ---
        print(
            f"\n{Fore.MAGENTA}Backup Options for Server: {server_name}{Style.RESET_ALL}"
        )
        print("  1. Backup World Only")
        print("  2. Backup Specific Configuration File")
        print("  3. Backup Everything (World + Configs)")
        print("  4. Cancel")
        # --- End User Interaction ---

        # --- User Interaction: Get Choice ---
        choice = input(
            f"{Fore.CYAN}Select backup option (1-4):{Style.RESET_ALL} "
        ).strip()
        logger.debug(f"User entered backup menu choice: '{choice}'")
        # --- End User Interaction ---

        if choice == "1":
            logger.debug("User selected 'Backup World Only'.")
            # Call handler (stop/start needed for world)
            backup_server(server_name, "world", change_status=True, base_dir=base_dir)
            break  # Exit menu loop
        elif choice == "2":
            logger.debug("User selected 'Backup Specific Configuration File'.")
            # --- User Interaction: Config File Sub-Menu ---
            print(
                f"{Fore.MAGENTA}Select configuration file to backup:{Style.RESET_ALL}"
            )
            print("  1. allowlist.json")
            print("  2. permissions.json")
            print("  3. server.properties")
            print("  4. Cancel Config Backup")
            config_choice = input(
                f"{Fore.CYAN}Choose file (1-4):{Style.RESET_ALL} "
            ).strip()
            logger.debug(f"User entered config file choice: '{config_choice}'")
            # --- End User Interaction ---

            file_to_backup: Optional[str] = None
            if config_choice == "1":
                file_to_backup = "allowlist.json"
            elif config_choice == "2":
                file_to_backup = "permissions.json"
            elif config_choice == "3":
                file_to_backup = "server.properties"
            elif config_choice == "4":
                # --- User Interaction: Print Cancellation ---
                print(f"{_INFO_PREFIX}Configuration file backup canceled.")
                # --- End User Interaction ---
                logger.debug("User canceled config file backup.")
                # continue # Go back to main backup menu
                break  # Exit backup menu completely after cancel
            else:
                # --- User Interaction: Print Invalid Choice ---
                print(
                    f"{_WARN_PREFIX}Invalid selection '{config_choice}'. Please choose a valid option."
                )
                # --- End User Interaction ---
                logger.debug("User entered invalid config file choice.")
                continue  # Ask for config choice again

            if file_to_backup:
                # Call handler (stop/start generally not needed for single config file)
                backup_server(
                    server_name,
                    "config",
                    file_to_backup,
                    change_status=False,
                    base_dir=base_dir,
                )
                break  # Exit menu loop
        elif choice == "3":
            logger.debug("User selected 'Backup Everything'.")
            # Call handler (stop/start needed because world is included)
            backup_server(server_name, "all", change_status=True, base_dir=base_dir)
            break  # Exit menu loop
        elif choice == "4":
            # --- User Interaction: Print Cancellation ---
            print(f"{_INFO_PREFIX}Backup operation canceled.")
            # --- End User Interaction ---
            logger.debug("User canceled backup operation from main menu.")
            return  # Exit function
        else:
            # --- User Interaction: Print Invalid Choice ---
            print(
                f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose a number between 1 and 4."
            )
            # --- End User Interaction ---
            logger.debug("User entered invalid main backup menu choice.")
            # Loop continues


def restore_server(
    server_name: str,
    restore_type: str,
    backup_file: Optional[str] = None,  # Optional only if restore_type is 'all'
    change_status: bool = True,
    base_dir: Optional[str] = None,
) -> None:
    """
    CLI handler function to restore a server's world, config file, or all from backups.

    Calls the appropriate API restore function.

    Args:
        server_name: The name of the server.
        restore_type: Type of restore ("world", "config", "all").
        backup_file: Full path to the specific backup file to restore (required for
                     "world" and "config" types).
        change_status: If True, stop/start server if needed for the restore type.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        MissingArgumentError: If `restore_type` or required `backup_file` is empty.
        InvalidServerNameError: If `server_name` is empty.
        InvalidInputError: If `restore_type` is invalid.
        # API errors are caught and printed.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not restore_type:
        raise MissingArgumentError("Restore type cannot be empty.")

    restore_type_norm = restore_type.lower()
    log_target = (
        f"'{os.path.basename(backup_file)}'" if backup_file else "latest backups"
    )
    logger.debug(
        f"CLI: Initiating '{restore_type_norm}' restore for server '{server_name}' from {log_target}. Change Status: {change_status}"
    )

    response: Optional[Dict[str, Any]] = None
    try:
        # --- Validate inputs and call API function ---
        if restore_type_norm == "world":
            if not backup_file:
                raise MissingArgumentError(
                    "Backup file path is required for world restore."
                )
            logger.debug("Calling API: backup_restore_api.restore_world")
            response = backup_restore_api.restore_world(
                server_name=server_name,
                backup_file_path=backup_file,
                base_dir=base_dir,
                stop_start_server=change_status,
            )
        elif restore_type_norm == "config":
            if not backup_file:
                raise MissingArgumentError(
                    "Backup file path is required for config restore."
                )
            logger.debug(
                f"Calling API: backup_restore_api.restore_config_file for file '{backup_file}'"
            )
            response = backup_restore_api.restore_config_file(
                server_name=server_name,
                backup_file_path=backup_file,
                base_dir=base_dir,
                stop_start_server=change_status,
            )
        elif restore_type_norm == "all":
            logger.debug("Calling API: backup_restore_api.restore_all")
            response = backup_restore_api.restore_all(
                server_name=server_name,
                base_dir=base_dir,
                stop_start_server=change_status,
            )
        else:
            raise InvalidInputError(
                f"Invalid restore type specified: '{restore_type}'. Must be 'world', 'config', or 'all'."
            )

        logger.debug(f"API response for restore_{restore_type_norm}: {response}")

        # --- User Interaction: Print Restore Result ---
        if response and response.get("status") == "error":
            message = response.get(
                "message", f"Unknown error during '{restore_type_norm}' restore."
            )
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(
                f"CLI: Restore type '{restore_type_norm}' failed for '{server_name}': {message}"
            )
        else:
            message = response.get(
                "message", f"Restore type '{restore_type_norm}' completed successfully."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(
                f"CLI: Restore type '{restore_type_norm}' successful for '{server_name}'."
            )
        # --- End User Interaction ---

    except (
        MissingArgumentError,
        InvalidServerNameError,
        InvalidInputError,
        FileNotFoundError,
    ) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to initiate restore for '{server_name}': {e}", exc_info=True
        )
    except Exception as e:
        # Catch unexpected errors calling the API
        print(f"{_ERROR_PREFIX}An unexpected error occurred during restore: {e}")
        logger.error(
            f"CLI: Unexpected error during '{restore_type_norm}' restore for '{server_name}': {e}",
            exc_info=True,
        )


def restore_menu(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    Displays an interactive restore menu for the user to choose restore type and backup file.

    Args:
        server_name: The name of the server.
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Displaying restore menu for server '{server_name}'.")
    while True:
        # --- User Interaction: Main Restore Menu ---
        print(
            f"\n{Fore.MAGENTA}Restore Options for Server: {server_name}{Style.RESET_ALL}"
        )
        print("  1. Restore World")
        print("  2. Restore Specific Configuration File")
        print("  3. Restore Everything (Latest Backups)")
        print("  4. Cancel")
        # --- End User Interaction ---

        # --- User Interaction: Get Main Choice ---
        choice = input(
            f"{Fore.CYAN}Select restore option (1-4):{Style.RESET_ALL} "
        ).strip()
        logger.debug(f"User entered main restore menu choice: '{choice}'")
        # --- End User Interaction ---

        restore_type: Optional[str] = None
        if choice == "1":
            restore_type = "world"
        elif choice == "2":
            restore_type = "config"
        elif choice == "3":
            logger.debug("User selected 'Restore Everything'.")
            print(
                f"{_INFO_PREFIX}Restoring server '{server_name}' from latest backups..."
            )
            restore_server(
                server_name=server_name,
                restore_type="all",
                backup_file=None,
                base_dir=base_dir,
            )  # stop/start defaults True
            return  # Exit function after restore all
        elif choice == "4":
            # --- User Interaction: Print Cancellation ---
            print(f"{_INFO_PREFIX}Restore operation canceled.")
            # --- End User Interaction ---
            logger.debug("User canceled restore operation from main menu.")
            return  # Exit function
        else:
            # --- User Interaction: Print Invalid Choice ---
            print(
                f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose a number between 1 and 4."
            )
            # --- End User Interaction ---
            logger.debug("User entered invalid main restore menu choice.")
            continue  # Ask again

        # --- List Available Backups for Selected Type ---
        logger.debug(f"Listing '{restore_type}' backups for server '{server_name}'...")
        try:
            # Call API to list backup files
            list_response = backup_restore_api.list_backup_files(
                server_name, restore_type
            )  # Handles base_dir internally
            logger.debug(f"List backup files API response: {list_response}")

            if list_response.get("status") == "error":
                message = list_response.get(
                    "message", f"Unknown error listing {restore_type} backups."
                )
                print(f"{_ERROR_PREFIX}{message}")
                logger.error(f"CLI: Failed to list backups for restore menu: {message}")
                continue  # Go back to main menu if listing fails

            backup_file_paths = list_response.get("backups", [])
            if not backup_file_paths:
                print(
                    f"{_WARN_PREFIX}No '{restore_type}' backups found for server '{server_name}'."
                )
                logger.warning(
                    f"No '{restore_type}' backups found for '{server_name}'."
                )
                continue  # Go back to main menu

        except (MissingArgumentError, FileOperationError) as e:
            print(f"{_ERROR_PREFIX}Error listing backups: {e}")
            logger.error(f"CLI: Failed to list backups: {e}", exc_info=True)
            continue  # Go back to main menu
        except Exception as e:
            print(
                f"{_ERROR_PREFIX}An unexpected error occurred while listing backups: {e}"
            )
            logger.error(f"CLI: Unexpected error listing backups: {e}", exc_info=True)
            continue  # Go back to main menu

        # --- User Interaction: Backup Selection Sub-Menu ---
        backup_map: Dict[int, str] = {}
        print(f"\n{Fore.MAGENTA}Available '{restore_type}' backups:{Style.RESET_ALL}")
        for i, file_path in enumerate(backup_file_paths):
            backup_map[i + 1] = file_path
            print(f"  {i + 1}. {os.path.basename(file_path)}")
        cancel_option_num = len(backup_map) + 1
        print(f"  {cancel_option_num}. Cancel")
        # --- End User Interaction ---

        while True:  # Inner loop for backup file choice
            try:
                # --- User Interaction: Get Backup Choice ---
                choice_str = input(
                    f"{Fore.CYAN}Select a backup to restore (1-{cancel_option_num}):{Style.RESET_ALL} "
                ).strip()
                choice_num = int(choice_str)
                logger.debug(f"User entered backup selection: {choice_num}")
                # --- End User Interaction ---

                if 1 <= choice_num <= len(backup_map):
                    selected_file = backup_map[choice_num]
                    logger.debug(f"User selected backup file: {selected_file}")
                    print(
                        f"{_INFO_PREFIX}Restoring from '{os.path.basename(selected_file)}'..."
                    )
                    # Call the restore handler function
                    restore_server(
                        server_name=server_name,
                        backup_file=selected_file,
                        restore_type=restore_type,
                        change_status=True,
                        base_dir=base_dir,
                    )
                    return  # Exit function after successful restore call
                elif choice_num == cancel_option_num:
                    # --- User Interaction: Print Cancellation ---
                    print(f"{_INFO_PREFIX}Restore operation canceled.")
                    # --- End User Interaction ---
                    logger.debug("User canceled restore from file selection menu.")
                    return  # Exit function
                else:
                    # --- User Interaction: Print Invalid Choice ---
                    print(
                        f"{_WARN_PREFIX}Invalid selection '{choice_num}'. Please choose again."
                    )
                    # --- End User Interaction ---
                    logger.debug(
                        f"User entered invalid backup selection number: {choice_num}"
                    )
            except ValueError:
                # --- User Interaction: Print Invalid Input ---
                print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
                # --- End User Interaction ---
                logger.debug(
                    f"User entered non-numeric input for backup selection: '{choice_str}'"
                )
            # Inner loop continues for invalid backup selection
