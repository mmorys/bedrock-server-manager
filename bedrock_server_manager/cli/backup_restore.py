# bedrock-server-manager/bedrock_server_manager/cli/backup_restore.py
import os
import logging
from colorama import Fore, Style
from bedrock_server_manager.api import backup_restore
from bedrock_server_manager.utils.general import (
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)
from bedrock_server_manager.core.error import (
    MissingArgumentError,
    InvalidServerNameError,
    InvalidInputError,
)

logger = logging.getLogger("bedrock_server_manager")


def prune_old_backups(server_name, file_name=None, backup_keep=None, base_dir=None):
    """Prunes old backups, keeping only the most recent ones. (UI and setup)"""
    if not server_name:
        raise InvalidServerNameError("prune_old_backups: server_name is empty.")

    response = backup_restore.prune_old_backups(
        server_name, file_name, backup_keep, base_dir
    )
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Old backups pruned successfully.")


def backup_server(
    server_name, backup_type, file_to_backup=None, change_status=True, base_dir=None
):
    """Backs up a server's world or a specific configuration file."""
    if not server_name:
        raise InvalidServerNameError("backup_server: server_name is empty.")
    if not backup_type:
        raise MissingArgumentError("backup_server: backup_type is empty.")

    if backup_type == "world":
        response = backup_restore.backup_world(
            server_name, base_dir, stop_start_server=change_status
        )
    elif backup_type == "config":
        if not file_to_backup:
            raise MissingArgumentError(
                "backup_server: file_to_backup is empty when backup_type is config."
            )
        response = backup_restore.backup_config_file(
            server_name, file_to_backup, base_dir, stop_start_server=change_status
        )
    elif backup_type == "all":
        response = backup_restore.backup_all(
            server_name, base_dir, stop_start_server=change_status
        )
    else:
        raise InvalidInputError(f"Invalid backup type: {backup_type}")

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Backup completed successfully.")

    # Prune old backups after the backup is complete.
    prune_response = backup_restore.prune_old_backups(
        server_name=server_name, file_name=file_to_backup, base_dir=base_dir
    )
    if prune_response["status"] == "error":
        print(f"{_ERROR_PREFIX}Error pruning old backups: {prune_response['message']}")


def backup_menu(server_name, base_dir):
    """Displays the backup menu and handles user input."""

    if not server_name:
        raise InvalidServerNameError("backup_menu: server_name is empty.")

    while True:
        print(f"{Fore.MAGENTA}What do you want to backup:{Style.RESET_ALL}")
        print("1. Backup World")
        print("2. Backup Configuration File")
        print("3. Backup All")
        print("4. Cancel")

        choice = input(
            f"{Fore.CYAN}Select the type of backup:{Style.RESET_ALL} "
        ).strip()

        if choice == "1":
            backup_server(
                server_name, "world", change_status=True, base_dir=base_dir
            )  # Stop/start server
            break
        elif choice == "2":
            print(
                f"{Fore.MAGENTA}Select configuration file to backup:{Style.RESET_ALL}"
            )
            print("1. allowlist.json")
            print("2. permissions.json")
            print("3. server.properties")
            print("4. Cancel")

            config_choice = input(f"{Fore.CYAN}Choose file:{Style.RESET_ALL} ").strip()
            if config_choice == "1":
                file_to_backup = "allowlist.json"
            elif config_choice == "2":
                file_to_backup = "permissions.json"
            elif config_choice == "3":
                file_to_backup = "server.properties"
            elif config_choice == "4":
                print(f"{_INFO_PREFIX}Backup operation canceled.")
                return  # User canceled
            else:
                print(f"{_WARN_PREFIX}Invalid selection, please try again.")
                continue
            backup_server(
                server_name,
                "config",
                file_to_backup,
                change_status=True,
                base_dir=base_dir,
            )  # Stop/Start
            break
        elif choice == "3":
            backup_server(
                server_name, "all", change_status=True, base_dir=base_dir
            )  # Stop/Start
            break
        elif choice == "4":
            print(f"{_INFO_PREFIX}Backup operation canceled.")
            return
        else:
            print(f"{_WARN_PREFIX}Invalid selection, please try again.")


def restore_server(
    server_name, backup_file, restore_type, change_status=True, base_dir=None
):
    """Restores a server from a backup file."""

    if not server_name:
        raise InvalidServerNameError("restore_server: server_name is empty.")
    if not restore_type:
        raise MissingArgumentError("restore_server: restore_type is empty.")

    if restore_type == "world":
        if not backup_file:
            raise MissingArgumentError("restore_server: backup_file is empty.")
        response = backup_restore.restore_world(
            server_name, backup_file, base_dir, stop_start_server=change_status
        )
    elif restore_type == "config":
        if not backup_file:
            raise MissingArgumentError("restore_server: backup_file is empty.")
        response = backup_restore.restore_config_file(
            server_name, backup_file, base_dir, stop_start_server=change_status
        )
    elif restore_type == "all":
        response = backup_restore.restore_all(
            server_name, base_dir, stop_start_server=change_status
        )
    else:
        raise InvalidInputError(f"Invalid restore type: {restore_type}")

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Restoration completed successfully.")


def restore_menu(server_name, base_dir):
    """Displays the restore menu and handles user interaction."""

    if not server_name:
        raise InvalidServerNameError("restore_menu: server_name is empty.")

    while True:
        print(f"{Fore.MAGENTA}Select the type of backup to restore:{Style.RESET_ALL}")
        print("1. World")
        print("2. Configuration File")
        print("3. Restore All")
        print("4. Cancel")

        choice = input(
            f"{Fore.CYAN}What do you want to restore:{Style.RESET_ALL} "
        ).strip()
        if choice == "1":
            restore_type = "world"
        elif choice == "2":
            restore_type = "config"
        elif choice == "3":
            restore_server(server_name, None, "all", base_dir=base_dir)
            return
        elif choice == "4":
            print(f"{_INFO_PREFIX}Restore operation canceled.")
            return  # User canceled
        else:
            print(f"{_WARN_PREFIX}Invalid selection. Please choose again.")
            continue

        # List available backups
        list_response = backup_restore.list_backups_files(server_name, restore_type, base_dir)
        if list_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{list_response['message']}")
            return  # Exit if no backups found

        backup_files = list_response["backups"]

        # Create a numbered list of backup files (CLI-specific)
        backup_map = {}
        print(f"{Fore.MAGENTA}Available backups:{Style.RESET_ALL}")
        for i, file in enumerate(backup_files):
            backup_map[i + 1] = file
            print(f"{i + 1}. {os.path.basename(file)}")
        print(f"{len(backup_map) + 1}. Cancel")  # Add a cancel option

        while True:
            try:
                choice = int(
                    input(
                        f"{Fore.CYAN}Select a backup to restore (1-{len(backup_map) + 1}):{Style.RESET_ALL} "
                    ).strip()
                )
                if 1 <= choice <= len(backup_map):
                    selected_file = backup_map[choice]
                    restore_server(
                        server_name, selected_file, restore_type, True, base_dir
                    )  # Stop/Start
                    return
                elif choice == len(backup_map) + 1:
                    print(f"{_INFO_PREFIX}Restore operation canceled.")
                    return  # User canceled
                else:
                    print(f"{_WARN_PREFIX}Invalid selection. Please choose again.")
            except ValueError:
                print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
