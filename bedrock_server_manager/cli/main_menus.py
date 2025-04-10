# bedrock-server-manager/bedrock_server_manager/cli/main_menus.py
"""
Defines the main interactive menu flows for the Bedrock Server Manager CLI.

Handles displaying options, getting user input, and dispatching calls to
specific CLI handler functions based on user selections. Uses print() for menus
and user feedback, and logger for tracing internal flow and errors.
"""

import os
import platform
import logging
import sys
from typing import Optional

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
    _ERROR_PREFIX,
    _WARN_PREFIX,
    _INFO_PREFIX,
)
from bedrock_server_manager.utils.get_utils import _get_splash_text
from bedrock_server_manager.config.settings import (
    app_name,
    settings,
)
from bedrock_server_manager.cli import utils as cli_utils
from bedrock_server_manager.cli import (
    server_install_config as cli_server_install_config,
)
from bedrock_server_manager.cli import server as cli_server
from bedrock_server_manager.cli import world as cli_world
from bedrock_server_manager.cli import addon as cli_addon
from bedrock_server_manager.cli import system as cli_system
from bedrock_server_manager.cli import (
    task_scheduler as cli_task_scheduler,
)
from bedrock_server_manager.cli import backup_restore as cli_backup_restore

logger = logging.getLogger("bedrock_server_manager")


def main_menu(base_dir: str, config_dir: Optional[str] = None) -> None:
    """
    Displays the main application menu and handles top-level user choices.

    Args:
        base_dir: The base directory for server installations.
        config_dir: Optional. The base directory for configuration files. Uses default if None.
    """
    if config_dir is None:
        config_dir = getattr(settings, "_config_dir", None)
        if not config_dir:
            logger.critical(
                "Configuration directory cannot be determined in main_menu."
            )
            print(
                f"{_ERROR_PREFIX}Configuration error: Cannot determine config directory."
            )
            return  # Cannot proceed without config dir

    while True:
        try:
            # Clear screen and display header/status
            os.system("cls" if platform.system() == "Windows" else "clear")
            print(f"\n{Fore.MAGENTA}{app_name} - Main Menu{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}{_get_splash_text()}{Style.RESET_ALL}")
            cli_utils.list_servers_status(
                base_dir, config_dir
            )  # Display server status list

            # --- User Interaction: Print Menu Options ---
            print("\nChoose an action:")
            print("  1) Install New Server")
            print("  2) Manage Existing Server")
            print("  3) Install Content")
            print(
                "  4) Send Command to Server"
                + (" (Linux Only)" if platform.system() != "Linux" else "")
            )
            print("  5) Advanced")
            print("  6) Exit")
            prompt_range = "[1-6]"
            # --- End User Interaction ---

            # --- User Interaction: Get Choice ---
            choice = input(
                f"{Fore.CYAN}Select an option {prompt_range}{Style.RESET_ALL}: "
            ).strip()
            logger.debug(f"Main menu choice entered: '{choice}'")
            # --- End User Interaction ---

            # --- Process Choice ---
            if choice == "1":
                logger.debug("User selected 'Install New Server'.")
                # Call install handler (handles its own prints/logging)
                cli_server_install_config.install_new_server(base_dir, config_dir)
                input("Press Enter to continue...")  # Pause for user to see error
            elif choice == "2":
                logger.debug(
                    "User selected 'Manage Existing Server'. Entering manage server menu..."
                )
                manage_server(base_dir, config_dir)  # Enter sub-menu
            elif choice == "3":
                logger.debug(
                    "User selected 'Install Content'. Entering content menu..."
                )
                install_content(base_dir, config_dir)  # Enter sub-menu
            elif choice == "4":
                logger.debug("User selected 'Send Command to Server'.")
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    command = input(
                        f"{Fore.CYAN}Enter command to send:{Style.RESET_ALL} "
                    ).strip()
                    if not command:
                        print(f"{_WARN_PREFIX}No command entered. Operation canceled.")
                        logger.warning("User entered empty command for 'send command'.")
                    else:
                        # Call send command handler (handles prints/logging)
                        cli_server.send_command(server_name, command, base_dir)
                else:
                    logger.debug("Send command canceled by user (no server selected).")
            elif choice == "5":
                logger.debug(
                    "User selected 'Advanced Options'. Entering advanced menu..."
                )
                advanced_menu(base_dir, config_dir)  # Enter sub-menu
            elif choice == "6":
                logger.debug("User selected 'Exit'. Terminating application.")
                os.system("cls" if platform.system() == "Windows" else "clear")
                sys.exit(0)  # Use sys.exit for clean exit
            else:
                # --- User Interaction: Print Invalid Choice ---
                print(
                    f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose again."
                )
                # --- End User Interaction ---
                logger.warning(f"Invalid main menu choice entered: '{choice}'")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting application...")
            logger.debug("Exiting application due to KeyboardInterrupt or EOFError.")
            sys.exit(0)
        except Exception as e:
            # Catch unexpected errors from handlers, log them, and show user message
            print(f"\n{_ERROR_PREFIX}An unexpected error occurred: {e}")
            logger.error(f"An error occurred in the main menu loop: {e}", exc_info=True)
            input("Press Enter to continue...")  # Pause for user to see error

        # Loop continues unless exit is chosen or error occurs


def manage_server(base_dir: str, config_dir: str) -> None:
    """
    Displays the menu for managing an existing server and handles user choices.

    Args:
        base_dir: The base directory for server installations.
        config_dir: The base directory for configuration files.
    """
    logger.debug("Entering manage server menu.")
    while True:
        try:
            os.system("cls" if platform.system() == "Windows" else "clear")
            print(
                f"\n{Fore.MAGENTA}{app_name} - Manage Existing Server{Style.RESET_ALL}\n"
            )
            cli_utils.list_servers_status(
                base_dir, config_dir
            )  # Display server list/status

            # --- User Interaction: Print Menu Options ---
            print("\nChoose an action:")
            print("  1) Update Server")
            print("  2) Start Server")
            print("  3) Stop Server")
            print("  4) Restart Server")
            print("  5) Backup/Restore Menu")
            print("  6) Delete Server")
            print("  7) Back to Main Menu")
            # --- End User Interaction ---

            # --- User Interaction: Get Choice ---
            choice = input(
                f"{Fore.CYAN}Select an option [1-7]{Style.RESET_ALL}: "
            ).strip()
            logger.debug(f"Manage server menu choice entered: '{choice}'")
            # --- End User Interaction ---

            # --- Process Choice ---
            server_name: Optional[str] = None  # Initialize server_name

            if choice in [
                "1",
                "2",
                "3",
                "4",
                "6",
            ]:  # Actions requiring server selection first
                server_name = cli_utils.get_server_name(base_dir)  # Prompt user
                if not server_name:
                    logger.debug("Operation canceled by user (no server selected).")
                    continue  # Go back to menu start

            if choice == "1":
                logger.debug(f"User selected 'Update Server' for '{server_name}'.")
                # Call update handler
                cli_server_install_config.update_server(
                    server_name, base_dir
                )  # Handles prints/logging
            elif choice == "2":
                logger.debug(f"User selected 'Start Server' for '{server_name}'.")
                # Call start handler
                cli_server.start_server(server_name, base_dir)
            elif choice == "3":
                logger.debug(f"User selected 'Stop Server' for '{server_name}'.")
                # Call stop handler
                cli_server.stop_server(server_name, base_dir)
            elif choice == "4":
                logger.debug(f"User selected 'Restart Server' for '{server_name}'.")
                # Call restart handler
                cli_server.restart_server(server_name, base_dir)
            elif choice == "5":
                logger.debug(
                    "User selected 'Backup/Restore Menu'. Entering sub-menu..."
                )
                backup_restore_menu(base_dir, config_dir)  # Enter sub-menu
            elif choice == "6":
                logger.debug(f"User selected 'Delete Server' for '{server_name}'.")
                confirm = (
                    input(
                        f"{Fore.RED}Are you sure you want to delete ALL data for server '{server_name}'? This cannot be undone! (yes/no):{Style.RESET_ALL} "
                    )
                    .strip()
                    .lower()
                )
                if confirm == "yes":
                    logger.warning(
                        f"Deletion confirmed for server '{server_name}'. Proceeding..."
                    )
                    # Call delete handler
                    cli_server.delete_server(server_name, base_dir, config_dir)
                else:
                    print(f"{_INFO_PREFIX}Deletion canceled.")
                    logger.debug(
                        f"Deletion canceled by user for server '{server_name}'."
                    )
            elif choice == "7":
                logger.debug("Returning to main menu from manage server menu.")
                return  # Go back
            else:
                # --- User Interaction: Print Invalid Choice ---
                print(
                    f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose again."
                )
                # --- End User Interaction ---
                logger.warning(f"Invalid manage server menu choice entered: '{choice}'")

            # Pause after action before looping
            if choice != "7":
                input("\nPress Enter to continue...")

        except (KeyboardInterrupt, EOFError):
            print("\nReturning to main menu...")
            logger.debug(
                "Returning to main menu due to KeyboardInterrupt or EOFError in manage server menu."
            )
            return
        except Exception as e:
            print(f"\n{_ERROR_PREFIX}An unexpected error occurred: {e}")
            logger.error(
                f"An error occurred in the manage server menu loop: {e}", exc_info=True
            )
            input("Press Enter to continue...")


def install_content(base_dir: str, config_dir: str) -> None:
    """
    Displays the menu for installing content (worlds, addons) to a server.

    Args:
        base_dir: The base directory for server installations.
        config_dir: The base directory for configuration files.
    """
    logger.debug("Entering install content menu.")
    while True:
        try:
            os.system("cls" if platform.system() == "Windows" else "clear")
            print(f"\n{Fore.MAGENTA}{app_name} - Install Content{Style.RESET_ALL}\n")
            cli_utils.list_servers_status(base_dir, config_dir)  # Show servers

            # --- User Interaction: Print Menu Options ---
            print("\nChoose content type to install:")
            print("  1) Import World (.mcworld)")
            print("  2) Install Addon (.mcaddon / .mcpack)")
            print("  3) Back to Main Menu")
            # --- End User Interaction ---

            # --- User Interaction: Get Choice ---
            choice = input(
                f"{Fore.CYAN}Select an option [1-3]{Style.RESET_ALL}: "
            ).strip()
            logger.debug(f"Install content menu choice entered: '{choice}'")
            # --- End User Interaction ---

            # --- Process Choice ---
            server_name: Optional[str] = None  # Initialize

            if choice in ["1", "2"]:  # Actions requiring server selection first
                server_name = cli_utils.get_server_name(base_dir)
                if not server_name:
                    logger.debug("Operation canceled by user (no server selected).")
                    continue  # Go back to menu start

            if choice == "1":
                logger.debug(
                    f"User selected 'Import World' for server '{server_name}'."
                )
                # Call world import handler (which includes file selection menu)
                cli_world.install_worlds(
                    server_name, base_dir
                )  # Handles prints/logging
                input("Press Enter to continue...")  # Pause for user to see error
            elif choice == "2":
                logger.debug(
                    f"User selected 'Install Addon' for server '{server_name}'."
                )
                # Call addon install handler (which includes file selection menu)
                cli_addon.install_addons(
                    server_name, base_dir
                )  # Handles prints/logging
                input("Press Enter to continue...")  # Pause for user to see error
            elif choice == "3":
                logger.debug("Returning to main menu from install content menu.")
                return  # Go back
            else:
                # --- User Interaction: Print Invalid Choice ---
                print(
                    f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose again."
                )
                # --- End User Interaction ---
                logger.warning(
                    f"Invalid install content menu choice entered: '{choice}'"
                )

            # Pause after action before looping (unless returning)
            if choice != "3":
                input("\nPress Enter to continue...")

        except (KeyboardInterrupt, EOFError):
            print("\nReturning to main menu...")
            logger.debug(
                "Returning to main menu due to KeyboardInterrupt or EOFError in install content menu."
            )
            return
        except Exception as e:
            print(f"\n{_ERROR_PREFIX}An unexpected error occurred: {e}")
            logger.error(
                f"An error occurred in the install content menu loop: {e}",
                exc_info=True,
            )
            input("Press Enter to continue...")


def advanced_menu(base_dir: str, config_dir: str) -> None:
    """
    Displays the advanced options menu and handles user choices.

    Args:
        base_dir: The base directory for server installations.
        config_dir: The base directory for configuration files.
    """
    logger.debug("Entering advanced menu.")
    while True:
        try:
            os.system("cls" if platform.system() == "Windows" else "clear")
            print(f"\n{Fore.MAGENTA}{app_name} - Advanced Options{Style.RESET_ALL}\n")
            cli_utils.list_servers_status(base_dir, config_dir)

            # --- User Interaction: Print Menu Options ---
            print("\nChoose an advanced action:")
            print("  1) Configure Server Properties")
            print("  2) Configure Allowlist")
            print("  3) Configure Permissions")
            print(
                "  4) Attach to Server Console"
                + (" (Linux Only)" if platform.system() != "Linux" else "")
            )
            print("  5) Schedule Server Task")
            print("  6) View Server Resource Usage")
            print("  7) Reconfigure Auto-Update")
            print("  8) Back")
            prompt_range = "[1-8]"
            # --- End User Interaction ---

            # --- User Interaction: Get Choice ---
            choice = input(
                f"{Fore.CYAN}Select an option {prompt_range}{Style.RESET_ALL}: "
            ).strip()
            logger.debug(f"Advanced menu choice entered: '{choice}'")
            # --- End User Interaction ---

            # --- Process Choice ---
            server_name: Optional[str] = None  # Initialize

            if choice in [
                "1",
                "2",
                "3",
                "4",
                "5",
                "6",
                "7",
            ]:  # Actions needing server name (adjust based on OS)
                # Check if the choice is valid for the current OS before asking for server name
                os_check_needed = (platform.system() != "Linux" and choice == "4") or (
                    platform.system() not in ("Linux", "Windows")
                    and choice in ["4", "5", "6", "7"]
                )
                if os_check_needed:
                    print(
                        f"{_WARN_PREFIX}Option '{choice}' is not available on this operating system."
                    )
                    logger.warning(
                        f"User selected OS-specific option '{choice}' on unsupported OS '{platform.system()}'"
                    )
                    input("Press Enter to continue...")
                    continue

                # Get server name if action requires it
                server_name = cli_utils.get_server_name(base_dir)
                if not server_name:
                    logger.debug("Operation canceled by user (no server selected).")
                    continue  # Go back to menu start

            # Map choices based on OS
            if choice == "1":
                logger.debug(
                    f"User selected 'Configure Server Properties' for '{server_name}'."
                )
                cli_server_install_config.configure_server_properties(
                    server_name, base_dir
                )
                input("Press Enter to continue...")  # Pause for user to see error
            elif choice == "2":
                logger.debug(
                    f"User selected 'Configure Allowlist' for '{server_name}'."
                )
                cli_server_install_config.configure_allowlist(server_name, base_dir)
                input("Press Enter to continue...")  # Pause for user to see error
            elif choice == "3":
                logger.debug(
                    f"User selected 'Configure Player Permissions' for '{server_name}'."
                )
                cli_server_install_config.select_player_for_permission(
                    server_name, base_dir, config_dir
                )
                input("Press Enter to continue...")  # Pause for user to see error
            elif choice == "4":
                logger.debug(
                    f"User selected 'Attach to Server Console' for '{server_name}'."
                )
                cli_utils.attach_console(server_name)
            elif choice == "5":
                logger.debug(
                    f"User selected 'Schedule Server Task' for '{server_name}'."
                )
                cli_task_scheduler.task_scheduler(server_name)
                input("Press Enter to continue...")  # Pause for user to see error
            elif choice == "6":
                logger.debug(
                    f"User selected 'View Server Resource Usage' for '{server_name}'."
                )
                cli_system.monitor_service_usage(server_name, base_dir)
                input("Press Enter to continue...")  # Pause for user to see error
            elif choice == "7":
                logger.debug(f"User selected 'Configure Service' for '{server_name}'.")
                cli_system.configure_service(server_name, base_dir)
                input("Press Enter to continue...")  # Pause for user to see error
            elif choice == "8":
                logger.debug("Returning to main menu from advanced menu.")
                return
            else:  # Invalid choice
                # --- User Interaction: Print Invalid Choice ---
                print(
                    f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose again."
                )
                # --- End User Interaction ---
                logger.warning(
                    f"Invalid advanced menu choice entered: '{choice}' for OS '{platform.system()}'"
                )

            # Pause after action before looping (unless returning)
            if choice not in ("8"):
                input("\nPress Enter to continue...")

        except (KeyboardInterrupt, EOFError):
            print("\nReturning to main menu...")
            logger.debug(
                "Returning to main menu due to KeyboardInterrupt or EOFError in advanced menu."
            )
            return
        except Exception as e:
            print(f"\n{_ERROR_PREFIX}An unexpected error occurred: {e}")
            logger.error(
                f"An error occurred in the advanced menu loop: {e}", exc_info=True
            )
            input("Press Enter to continue...")


def backup_restore_menu(base_dir: str, config_dir: str) -> None:
    """
    Displays the backup and restore options menu and handles user choices.

    Args:
        base_dir: The base directory for server installations.
        config_dir: The base directory for configuration files.
    """
    logger.debug("Entering backup/restore menu.")
    while True:
        try:
            os.system("cls" if platform.system() == "Windows" else "clear")
            print(f"\n{Fore.MAGENTA}{app_name} - Backup / Restore{Style.RESET_ALL}\n")
            cli_utils.list_servers_status(base_dir, config_dir)  # Show servers

            # --- User Interaction: Print Menu Options ---
            print("\nChoose an action:")
            print("  1) Backup Server Menu")  # Go to backup type selection
            print("  2) Restore Server Menu")  # Go to restore type selection
            print("  3) Prune Old Backups")
            print("  4) Back to Manage Server Menu")
            # --- End User Interaction ---

            # --- User Interaction: Get Choice ---
            choice = input(
                f"{Fore.CYAN}Select an option [1-4]{Style.RESET_ALL}: "
            ).strip()
            logger.debug(f"Backup/Restore menu choice entered: '{choice}'")
            # --- End User Interaction ---

            server_name: Optional[str] = None  # Initialize

            if choice in ["1", "2", "3"]:  # Actions requiring server selection first
                server_name = cli_utils.get_server_name(base_dir)
                if not server_name:
                    logger.debug("Operation canceled by user (no server selected).")
                    continue  # Go back to menu start

            if choice == "1":
                logger.debug(f"User selected 'Backup Server Menu' for '{server_name}'.")
                # Go to the backup type selection menu within the cli_backup_restore module
                cli_backup_restore.backup_menu(server_name, base_dir)
                input("Press Enter to continue...")  # Pause for user to see error
            elif choice == "2":
                logger.debug(
                    f"User selected 'Restore Server Menu' for '{server_name}'."
                )
                # Go to the restore type selection menu within the cli_backup_restore module
                cli_backup_restore.restore_menu(server_name, base_dir)
                input("Press Enter to continue...")  # Pause for user to see error
            elif choice == "3":
                logger.debug(f"User selected 'Prune Old Backups' for '{server_name}'.")
                # Call prune handler directly
                cli_backup_restore.prune_old_backups(server_name, base_dir=base_dir)
                input("Press Enter to continue...")  # Pause for user to see error
            elif choice == "4":
                logger.debug(
                    "Returning to manage server menu from backup/restore menu."
                )
                return  # Go back
            else:
                # --- User Interaction: Print Invalid Choice ---
                print(
                    f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose again."
                )
                # --- End User Interaction ---
                logger.warning(
                    f"Invalid backup/restore menu choice entered: '{choice}'"
                )

            # No pause needed here as sub-menus handle flow or pruning adds its own pause

        except (KeyboardInterrupt, EOFError):
            print("\nReturning to previous menu...")
            logger.debug(
                "Returning to previous menu due to KeyboardInterrupt or EOFError in backup/restore menu."
            )
            return
        except Exception as e:
            print(f"\n{_ERROR_PREFIX}An unexpected error occurred: {e}")
            logger.error(
                f"An error occurred in the backup/restore menu loop: {e}", exc_info=True
            )
            input("Press Enter to continue...")
