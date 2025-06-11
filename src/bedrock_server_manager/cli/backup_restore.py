# bedrock_server_manager/cli/backup_restore.py
"""
Command-line interface functions for handling server backup and restore operations.

Provides user interaction menus and calls corresponding API functions to perform
backup, restore, and pruning tasks. Uses print() for user feedback.
"""

import os
import logging
from typing import Optional, Dict, Any, List

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

logger = logging.getLogger(__name__)


def prune_old_backups(server_name: str) -> None:
    """
    CLI handler function to prune old backups for a server.

    Calls the corresponding API function which uses global settings for retention count.

    Args:
        server_name: The name of the server whose backups to prune.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Initiating prune old backups for server '{server_name}'.")
    logger.debug(f"Calling API: backup_restore_api.prune_old_backups")

    try:
        response = backup_restore_api.prune_old_backups(server_name=server_name)
        logger.debug(f"API response for prune_old_backups: {response}")

        if response.get("status") == "error":
            message = response.get("message", "Unknown error during pruning.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Pruning backups failed for '{server_name}': {message}")
        else:
            message = response.get("message", "Old backups pruned successfully.")
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Pruning backups successful for '{server_name}'.")

    except (InvalidServerNameError, ValueError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(f"CLI: Failed to call prune backups API: {e}", exc_info=True)
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred during pruning: {e}")
        logger.error(f"CLI: Unexpected error during backup pruning: {e}", exc_info=True)


def backup_server(
    server_name: str,
    backup_type: str,
    file_to_backup: Optional[str] = None,
    change_status: bool = True,
) -> None:
    """
    CLI handler function to back up a server's world, a specific config file, or all.

    Calls the appropriate API backup function and handles pruning afterwards.

    Args:
        server_name: The name of the server.
        backup_type: Type of backup ("world", "config", "all").
        file_to_backup: Relative path of config file if `backup_type` is "config".
        change_status: If True, stop/start server if needed for the backup type.

    Raises:
        MissingArgumentError: If `backup_type` or required `file_to_backup` is empty.
        InvalidServerNameError: If `server_name` is empty.
        InvalidInputError: If `backup_type` is invalid.
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
        if backup_type_norm == "world":
            logger.debug("Calling API: backup_restore_api.backup_world")
            response = backup_restore_api.backup_world(
                server_name, stop_start_server=change_status
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
                server_name, file_to_backup, stop_start_server=change_status
            )
        elif backup_type_norm == "all":
            logger.debug("Calling API: backup_restore_api.backup_all")
            response = backup_restore_api.backup_all(
                server_name, stop_start_server=change_status
            )
        else:
            raise InvalidInputError(
                f"Invalid backup type specified: '{backup_type}'. Must be 'world', 'config', or 'all'."
            )

        logger.debug(f"API response for backup_{backup_type_norm}: {response}")

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

        logger.debug(
            f"CLI: Pruning old backups for '{server_name}' after successful backup."
        )
        prune_old_backups(server_name=server_name)

    except (MissingArgumentError, InvalidServerNameError, InvalidInputError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to initiate backup for '{server_name}': {e}", exc_info=True
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred during backup: {e}")
        logger.error(
            f"CLI: Unexpected error during '{backup_type_norm}' backup for '{server_name}': {e}",
            exc_info=True,
        )


def backup_menu(server_name: str) -> None:
    """
    Displays an interactive backup menu for the user to choose backup type.

    Args:
        server_name: The name of the server.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Displaying backup menu for server '{server_name}'.")
    while True:
        print(
            f"\n{Fore.MAGENTA}Backup Options for Server: {server_name}{Style.RESET_ALL}"
        )
        print("  1. Backup World Only")
        print("  2. Backup Specific Configuration File")
        print("  3. Backup Everything (World + Configs)")
        print("  4. Cancel")

        choice = input(
            f"{Fore.CYAN}Select backup option (1-4):{Style.RESET_ALL} "
        ).strip()
        logger.debug(f"User entered backup menu choice: '{choice}'")

        if choice == "1":
            backup_server(server_name, "world", change_status=True)
            break
        elif choice == "2":
            logger.debug("User selected 'Backup Specific Configuration File'.")
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

            file_map = {
                "1": "allowlist.json",
                "2": "permissions.json",
                "3": "server.properties",
            }
            file_to_backup = file_map.get(config_choice)

            if file_to_backup:
                backup_server(
                    server_name, "config", file_to_backup, change_status=False
                )
                break
            elif config_choice == "4":
                print(f"{_INFO_PREFIX}Configuration file backup canceled.")
                break  # Exit backup menu completely after cancel
            else:
                print(
                    f"{_WARN_PREFIX}Invalid selection '{config_choice}'. Please choose a valid option."
                )
                continue  # Ask for config choice again
        elif choice == "3":
            backup_server(server_name, "all", change_status=True)
            break
        elif choice == "4":
            print(f"{_INFO_PREFIX}Backup operation canceled.")
            return
        else:
            print(
                f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose a number between 1 and 4."
            )


def restore_server(
    server_name: str,
    restore_type: str,
    backup_file: Optional[str] = None,
    change_status: bool = True,
) -> None:
    """
    CLI handler function to restore a server's world, config file, or all from backups.

    Args:
        server_name: The name of the server.
        restore_type: Type of restore ("world", "config", "all").
        backup_file: Full path to the specific backup file to restore.
        change_status: If True, stop/start server if needed for the restore type.
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
        if restore_type_norm == "world":
            if not backup_file:
                raise MissingArgumentError(
                    "Backup file path is required for world restore."
                )
            logger.debug("Calling API: backup_restore_api.restore_world")

            response = backup_restore_api.restore_world(
                server_name=server_name,
                backup_file_path=backup_file,
                stop_start_server=change_status,
            )
        elif restore_type_norm in ["allowlist", "permissions", "properties"]:
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
                stop_start_server=change_status,
            )
        elif restore_type_norm == "all":
            logger.debug("Calling API: backup_restore_api.restore_all")

            response = backup_restore_api.restore_all(
                server_name=server_name, stop_start_server=change_status
            )
        else:
            raise InvalidInputError(
                f"Invalid restore type specified: '{restore_type}'. Must be 'world', 'allowlist', 'permissions', 'properties', or 'all'."
            )

        logger.debug(f"API response for restore_{restore_type_norm}: {response}")

        if response and response.get("status") == "error":
            message = response.get(
                "message", f"Unknown error during '{restore_type_norm}' restore."
            )
            print(f"{_ERROR_PREFIX}{message}")
        else:
            message = response.get(
                "message", f"Restore type '{restore_type_norm}' completed successfully."
            )
            print(f"{_OK_PREFIX}{message}")

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
        print(f"{_ERROR_PREFIX}An unexpected error occurred during restore: {e}")
        logger.error(
            f"CLI: Unexpected error during '{restore_type_norm}' restore for '{server_name}': {e}",
            exc_info=True,
        )


def restore_menu(server_name: str) -> None:
    """
    Displays an interactive restore menu for the user to choose restore type and backup file.

    Args:
        server_name: The name of the server.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Displaying restore menu for server '{server_name}'.")
    while True:
        print(
            f"\n{Fore.MAGENTA}Restore Options for Server: {server_name}{Style.RESET_ALL}"
        )
        print("  1. Restore World")
        print("  2. Restore Allowlist")
        print("  3. Restore Permissions")
        print("  4. Restore Properties")
        print("  5. Restore Everything (from latest backups)")
        print("  6. Cancel")

        choice = input(
            f"{Fore.CYAN}Select restore option (1-4):{Style.RESET_ALL} "
        ).strip()
        logger.debug(f"User entered main restore menu choice: '{choice}'")

        if choice == "5":
            print(
                f"{_INFO_PREFIX}Restoring server '{server_name}' from latest backups..."
            )
            restore_server(server_name=server_name, restore_type="all")
            return
        elif choice == "6":
            print(f"{_INFO_PREFIX}Restore operation canceled.")
            return

        restore_map = {
            "1": "world",
            "2": "allowlist",
            "3": "permissions",
            "4": "properties",
        }
        restore_type = restore_map.get(choice)

        if not restore_type:
            print(
                f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose a number between 1 and 4."
            )
            continue

        try:
            logger.debug(
                f"Listing '{restore_type}' backups for server '{server_name}'..."
            )
            list_response = backup_restore_api.list_backup_files(
                server_name, restore_type
            )
            logger.debug(f"List backup files API response: {list_response}")

            if list_response.get("status") == "error":
                message = list_response.get(
                    "message", f"Unknown error listing {restore_type} backups."
                )
                print(f"{_ERROR_PREFIX}{message}")
                continue

            backup_file_paths: List[str] = list_response.get("backups", [])
            if not backup_file_paths:
                print(
                    f"{_WARN_PREFIX}No '{restore_type}' backups found for server '{server_name}'."
                )
                continue

            # Show selection menu for the files
            selected_file = _select_file_from_list(
                backup_file_paths, f"'{restore_type}' backup"
            )

            if selected_file:
                print(
                    f"{_INFO_PREFIX}Restoring from '{os.path.basename(selected_file)}'..."
                )
                restore_server(
                    server_name=server_name,
                    backup_file=selected_file,
                    restore_type=restore_type,
                )
                return  # Exit menu after successful restore call
            else:
                # User canceled from the file selection menu
                print(f"{_INFO_PREFIX}Restore operation canceled.")
                return

        except Exception as e:
            print(
                f"{_ERROR_PREFIX}An unexpected error occurred while listing backups: {e}"
            )
            logger.error(f"CLI: Unexpected error listing backups: {e}", exc_info=True)
            continue


def _select_file_from_list(file_paths: List[str], item_type_name: str) -> Optional[str]:
    """Helper function to display a file selection menu and return the user's choice."""

    print(f"\n{Fore.MAGENTA}Available {item_type_name}s:{Style.RESET_ALL}")
    for i, file_path in enumerate(file_paths):
        print(f"  {i + 1}. {os.path.basename(file_path)}")
    cancel_option_num = len(file_paths) + 1
    print(f"  {cancel_option_num}. Cancel")

    while True:
        try:
            choice_str = input(
                f"{Fore.CYAN}Select a {item_type_name} to restore (1-{cancel_option_num}):{Style.RESET_ALL} "
            ).strip()
            choice_num = int(choice_str)

            if 1 <= choice_num <= len(file_paths):
                return file_paths[choice_num - 1]
            elif choice_num == cancel_option_num:
                return None
            else:
                print(
                    f"{_WARN_PREFIX}Invalid selection '{choice_num}'. Please choose again."
                )
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
