# bedrock_server_manager/cli/main_menus.py
"""
Defines the main interactive menu flows for the Bedrock Server Manager CLI.

Handles displaying options, getting user input, and dispatching calls to
specific CLI handler functions based on user selections.
"""

import os
import platform
import logging
import sys
from typing import Optional

# Third-party imports
try:
    from colorama import Fore, Style

    COLORAMA_AVAILABLE = True
except ImportError:

    class DummyStyle:
        def __getattr__(self, name):
            return ""

    Fore = DummyStyle()
    Style = DummyStyle()


# Local imports
from bedrock_server_manager.utils.general import (
    _ERROR_PREFIX,
    _WARN_PREFIX,
    _INFO_PREFIX,
)
from bedrock_server_manager.utils.get_utils import _get_splash_text
from bedrock_server_manager.config.const import app_name_title
from bedrock_server_manager.cli import (
    utils as cli_utils,
    server_install_config as cli_server_install_config,
    server as cli_server,
    world as cli_world,
    addon as cli_addon,
    system as cli_system,
    task_scheduler as cli_task_scheduler,
    backup_restore as cli_backup_restore,
)

logger = logging.getLogger(__name__)


def main_menu() -> None:
    """Displays the main application menu and handles top-level user choices."""
    while True:
        try:
            os.system("cls" if platform.system() == "Windows" else "clear")
            print(f"\n{Fore.MAGENTA}{app_name_title} - Main Menu{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}{_get_splash_text()}{Style.RESET_ALL}")
            cli_utils.list_servers_status()

            print("\nChoose an action:")
            print("  1) Install New Server")
            print("  2) Manage Existing Server")
            print("  3) Install Content")
            print("  4) Send Command to Server")
            print("  5) Advanced")
            print("  6) Exit")

            choice = input(
                f"{Fore.CYAN}Select an option [1-6]:{Style.RESET_ALL} "
            ).strip()
            logger.debug(f"Main menu choice entered: '{choice}'")

            if choice == "1":
                cli_server_install_config.install_new_server()
            elif choice == "2":
                manage_server()
            elif choice == "3":
                install_content()
            elif choice == "4":
                server_name = cli_utils.get_server_name()
                if server_name:
                    command = input(
                        f"{Fore.CYAN}Enter command to send:{Style.RESET_ALL} "
                    ).strip()
                    if command:
                        cli_server.send_command(server_name, command)
                    else:
                        print(f"{_WARN_PREFIX}No command entered. Canceled.")
            elif choice == "5":
                advanced_menu()
            elif choice == "6":
                os.system("cls" if platform.system() == "Windows" else "clear")
                sys.exit(0)
            else:
                print(
                    f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose again."
                )

            # Pause for user to see output before clearing screen
            if choice in ["1", "2", "3", "4", "5"]:
                input("\nPress Enter to continue...")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting application...")
            sys.exit(0)
        except Exception as e:
            print(
                f"\n{_ERROR_PREFIX}An unexpected error occurred in the main menu: {e}"
            )
            logger.error(f"Main menu loop error: {e}", exc_info=True)
            input("Press Enter to continue...")


def manage_server() -> None:
    """Displays the menu for managing an existing server and handles user choices."""
    while True:
        try:
            os.system("cls" if platform.system() == "Windows" else "clear")
            print(
                f"\n{Fore.MAGENTA}{app_name_title} - Manage Existing Server{Style.RESET_ALL}\n"
            )
            cli_utils.list_servers_status()

            print("\nChoose an action:")
            print("  1) Update Server")
            print("  2) Start Server")
            print("  3) Stop Server")
            print("  4) Restart Server")
            print("  5) Backup/Restore Menu")
            print("  6) Delete Server")
            print("  7) Back to Main Menu")

            choice = input(
                f"{Fore.CYAN}Select an option [1-7]:{Style.RESET_ALL} "
            ).strip()
            logger.debug(f"Manage server menu choice entered: '{choice}'")

            if choice == "7":
                return

            # Get server name for actions that need it
            server_name: Optional[str] = None
            if choice in ["1", "2", "3", "4", "6"]:
                server_name = cli_utils.get_server_name()
                if not server_name:
                    continue

            if choice == "1":
                cli_server_install_config.update_server(server_name)
            elif choice == "2":
                cli_server.start_server(server_name, "detached")
            elif choice == "3":
                cli_server.stop_server(server_name)
            elif choice == "4":
                cli_server.restart_server(server_name)
            elif choice == "5":
                backup_restore_menu()
            elif choice == "6":
                cli_server.delete_server(server_name)
            else:
                if choice != "7":
                    print(f"{_WARN_PREFIX}Invalid selection '{choice}'.")

            input("\nPress Enter to continue...")

        except (KeyboardInterrupt, EOFError):
            print("\nReturning to main menu...")
            return
        except Exception as e:
            print(
                f"\n{_ERROR_PREFIX}An unexpected error occurred in the manage menu: {e}"
            )
            logger.error(f"Manage server menu loop error: {e}", exc_info=True)
            input("Press Enter to continue...")


def install_content() -> None:
    """Displays the menu for installing content (worlds, addons) to a server."""
    while True:
        try:
            os.system("cls" if platform.system() == "Windows" else "clear")
            print(
                f"\n{Fore.MAGENTA}{app_name_title} - Install Content{Style.RESET_ALL}\n"
            )
            cli_utils.list_servers_status()

            print("\nChoose content type to install:")
            print("  1) Import World (.mcworld)")
            print("  2) Install Addon (.mcaddon / .mcpack)")
            print("  3) Back to Main Menu")

            choice = input(
                f"{Fore.CYAN}Select an option [1-3]:{Style.RESET_ALL}: "
            ).strip()
            logger.debug(f"Install content menu choice entered: '{choice}'")

            if choice == "3":
                return

            server_name: Optional[str] = None
            if choice in ["1", "2"]:
                server_name = cli_utils.get_server_name()
                if not server_name:
                    continue

            if choice == "1":
                cli_world.install_worlds(server_name)
            elif choice == "2":
                cli_addon.install_addons(server_name)
            else:
                if choice != "3":
                    print(f"{_WARN_PREFIX}Invalid selection '{choice}'.")

            input("\nPress Enter to continue...")

        except (KeyboardInterrupt, EOFError):
            print("\nReturning to main menu...")
            return
        except Exception as e:
            print(
                f"\n{_ERROR_PREFIX}An unexpected error occurred in the content menu: {e}"
            )
            logger.error(f"Install content menu loop error: {e}", exc_info=True)
            input("Press Enter to continue...")


def advanced_menu() -> None:
    """Displays the advanced options menu and handles user choices."""
    while True:
        try:
            os.system("cls" if platform.system() == "Windows" else "clear")
            print(
                f"\n{Fore.MAGENTA}{app_name_title} - Advanced Options{Style.RESET_ALL}\n"
            )
            cli_utils.list_servers_status()

            print("\nChoose an advanced action:")
            print("  1) Configure Server Properties")
            print("  2) Configure Allowlist")
            print("  3) Configure Permissions")
            print(
                f"  4) Attach to Server Console{' (Linux Only)' if platform.system() != 'Linux' else ''}"
            )
            print("  5) Schedule Server Task")
            print("  6) View Server Resource Usage")
            print("  7) Reconfigure Auto-Update / Service")
            print("  8) Back")

            choice = input(
                f"{Fore.CYAN}Select an option [1-8]:{Style.RESET_ALL} "
            ).strip()
            logger.debug(f"Advanced menu choice entered: '{choice}'")

            if choice == "8":
                return

            server_name: Optional[str] = None
            if choice in ["1", "2", "3", "4", "5", "6", "7"]:
                server_name = cli_utils.get_server_name()
                if not server_name:
                    continue

            if choice == "1":
                cli_server_install_config.configure_server_properties(server_name)
            elif choice == "2":
                cli_server_install_config.configure_allowlist(server_name)
            elif choice == "3":
                cli_server_install_config.select_player_for_permission(server_name)
            elif choice == "4":
                cli_utils.attach_console(server_name)
            elif choice == "5":
                cli_task_scheduler.task_scheduler(server_name)
            elif choice == "6":
                cli_system.monitor_service_usage(server_name)
            elif choice == "7":
                cli_system.configure_service(server_name)
            else:
                if choice != "8":
                    print(f"{_WARN_PREFIX}Invalid selection '{choice}'.")

            # Pause unless attaching to console, which takes over the screen
            if choice != "4":
                input("\nPress Enter to continue...")

        except (KeyboardInterrupt, EOFError):
            print("\nReturning to main menu...")
            return
        except Exception as e:
            print(
                f"\n{_ERROR_PREFIX}An unexpected error occurred in the advanced menu: {e}"
            )
            logger.error(f"Advanced menu loop error: {e}", exc_info=True)
            input("Press Enter to continue...")


def backup_restore_menu() -> None:
    """Displays the backup and restore options menu and handles user choices."""
    while True:
        try:
            os.system("cls" if platform.system() == "Windows" else "clear")
            print(
                f"\n{Fore.MAGENTA}{app_name_title} - Backup / Restore{Style.RESET_ALL}\n"
            )
            cli_utils.list_servers_status()

            print("\nChoose an action:")
            print("  1) Backup Server Menu")
            print("  2) Restore Server Menu")
            print("  3) Prune Old Backups")
            print("  4) Back to Manage Server Menu")

            choice = input(
                f"{Fore.CYAN}Select an option [1-4]:{Style.RESET_ALL} "
            ).strip()
            logger.debug(f"Backup/Restore menu choice entered: '{choice}'")

            if choice == "4":
                return

            server_name: Optional[str] = None
            if choice in ["1", "2", "3"]:
                server_name = cli_utils.get_server_name()
                if not server_name:
                    continue

            if choice == "1":
                cli_backup_restore.backup_menu(server_name)
            elif choice == "2":
                cli_backup_restore.restore_menu(server_name)
            elif choice == "3":
                cli_backup_restore.prune_old_backups(server_name)
            else:
                if choice != "4":
                    print(f"{_WARN_PREFIX}Invalid selection '{choice}'.")

            input("\nPress Enter to continue...")

        except (KeyboardInterrupt, EOFError):
            print("\nReturning to previous menu...")
            return
        except Exception as e:
            print(
                f"\n{_ERROR_PREFIX}An unexpected error occurred in the backup/restore menu: {e}"
            )
            logger.error(f"Backup/restore menu loop error: {e}", exc_info=True)
            input("Press Enter to continue...")
