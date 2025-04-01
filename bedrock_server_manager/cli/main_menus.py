# bedrock-server-manager/bedrock_server_manager/cli/main_menus.py
import os
import sys
import logging
import platform
from colorama import Fore, Style
from bedrock_server_manager.config.settings import app_name
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.cli import utils as cli_utils
from bedrock_server_manager.cli import server_install_config
from bedrock_server_manager.cli import server as cli_server
from bedrock_server_manager.cli import world as cli_world
from bedrock_server_manager.cli import addon as cli_addon
from bedrock_server_manager.cli import system as cli_system
from bedrock_server_manager.cli import task_scheduler
from bedrock_server_manager.cli import backup_restore as cli_backup_restore

logger = logging.getLogger("bedrock_server_manager")


def main_menu(base_dir, config_dir):
    """Displays the main menu and handles user interaction."""
    os.system("cls" if platform.system() == "Windows" else "clear")
    while True:
        print(f"\n{Fore.MAGENTA}{app_name}{Style.RESET_ALL}")
        cli_utils.list_servers_status(base_dir, config_dir)

        print("1) Install New Server")
        print("2) Manage Existing Server")
        print("3) Install Content")
        print(
            "4) Send Command to Server"
            + (" (Linux Only)" if platform.system() != "Linux" else "")
        )
        print("5) Advanced")
        print("6) Exit")

        choice = input(f"{Fore.CYAN}Select an option [1-6]{Style.RESET_ALL}: ").strip()
        try:
            if choice == "1":
                server_install_config.install_new_server(base_dir, config_dir)
            elif choice == "2":
                manage_server(base_dir, config_dir)
            elif choice == "3":
                install_content(base_dir, config_dir)
            elif choice == "4":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    command = input(f"{Fore.CYAN}Enter command: ").strip()
                    if not command:
                        logger.warning("No command entered. Ignoring.")
                        continue  # Go back to the menu loop
                    cli_server.send_command(server_name, command, base_dir)
            elif choice == "5":
                advanced_menu(base_dir, config_dir)
            elif choice == "6":
                os.system("cls" if platform.system() == "Windows" else "clear")
                sys.exit(0)
            else:
                logger.warning("Invalid choice")
        except Exception as e:
            logger.exception(f"An error has occurred: {e}")


def manage_server(base_dir, config_dir=None):
    """Displays the manage server menu and handles user interaction."""
    if config_dir is None:
        config_dir = settings._config_dir

    os.system("cls" if platform.system() == "Windows" else "clear")
    while True:
        print(f"\n{Fore.MAGENTA}{app_name} - Manage Server{Style.RESET_ALL}")
        cli_utils.list_servers_status(base_dir, config_dir)
        print("1) Update Server")
        print("2) Start Server")
        print("3) Stop Server")
        print("4) Restart Server")
        print("5) Backup/Restore")
        print("6) Delete Server")
        print("7) Back")

        choice = input(f"{Fore.CYAN}Select an option [1-7]:{Style.RESET_ALL} ").strip()
        try:
            if choice == "1":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    server_install_config.update_server(server_name, base_dir)
                else:
                    logger.info("Update canceled.")
            elif choice == "2":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    cli_server.start_server(server_name, base_dir)
                else:
                    logger.info("Start canceled.")
            elif choice == "3":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    cli_server.stop_server(server_name, base_dir)
                else:
                    logger.info("Stop canceled.")
            elif choice == "4":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    cli_server.restart_server(server_name, base_dir)
                else:
                    logger.info("Restart canceled.")
            elif choice == "5":
                backup_restore(base_dir, config_dir)
            elif choice == "6":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    cli_server.delete_server(server_name, base_dir, config_dir)
                else:
                    logger.info("Delete canceled.")
            elif choice == "7":
                return  # Go back to the main menu
            else:
                logger.warning("Invalid choice")
        except Exception as e:
            logger.exception(f"An error has occurred: {e}")


def install_content(base_dir, config_dir=None):
    """Displays the install content menu and handles user interaction."""
    if config_dir is None:
        config_dir = settings._config_dir
    os.system("cls" if platform.system() == "Windows" else "clear")
    while True:
        print(f"\n{Fore.MAGENTA}{app_name} - Install Content{Style.RESET_ALL}")
        cli_utils.list_servers_status(base_dir, config_dir)
        print("1) Import World")
        print("2) Import Addon")
        print("3) Back")

        choice = input(f"{Fore.CYAN}Select an option [1-3]:{Style.RESET_ALL} ").strip()
        try:
            if choice == "1":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    cli_world.install_worlds(server_name, base_dir)
                else:
                    logger.info("Import canceled.")
            elif choice == "2":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    cli_addon.install_addons(server_name, base_dir)
                else:
                    logger.info("Import canceled.")
            elif choice == "3":
                return  # Go back to the main menu
            else:
                logger.warning("Invalid choice")
        except Exception as e:
            logger.exception(f"An error has occurred: {e}")


def advanced_menu(base_dir, config_dir=None):
    """Displays the advanced menu and handles user interaction."""
    if config_dir is None:
        config_dir = settings._config_dir

    os.system("cls" if platform.system() == "Windows" else "clear")
    while True:
        print(f"\n{Fore.MAGENTA}{app_name} - Advanced Menu{Style.RESET_ALL}")
        cli_utils.list_servers_status(base_dir, config_dir)
        print("1) Configure Server Properties")
        print("2) Configure Allowlist")
        print("3) Configure Permissions")
        print(
            "4) Attach to Server Console"
            + (" (Linux Only)" if platform.system() != "Linux" else "")
        )
        print("5) Schedule Server Task")
        print("6) View Server Resource Usage")
        print("7) Reconfigure Auto-Update")
        print("8) Back")

        choice = input(f"{Fore.CYAN}Select an option [1-8]:{Style.RESET_ALL} ").strip()

        try:
            if choice == "1":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    server_install_config.configure_server_properties(
                        server_name, base_dir
                    )
                else:
                    logger.info("Configuration canceled.")
            elif choice == "2":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    server_install_config.configure_allowlist(server_name, base_dir)
                else:
                    logger.info("Configuration canceled.")
            elif choice == "3":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    server_install_config.select_player_for_permission(
                        server_name, base_dir, config_dir
                    )
                else:
                    logger.info("Configuration canceled.")
            elif choice == "4":
                if platform.system() == "Linux":
                    server_name = cli_utils.get_server_name(base_dir)
                    if server_name:
                        cli_utils.attach_console(server_name, base_dir)
                    else:
                        logger.info("Attach canceled.")
                else:
                    logger.warning("Attach to console is only available on Linux.")

            elif choice == "5":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    task_scheduler.task_scheduler(server_name, base_dir)
                else:
                    logger.info("Schedule canceled.")
            elif choice == "6":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    cli_system.monitor_service_usage(server_name, base_dir)
                else:
                    logger.info("Monitoring canceled.")
            elif choice == "7":
                # Reconfigure systemd service / autoupdate
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    cli_system.create_service(server_name, base_dir)  # Use config
                else:
                    logger.info("Configuration canceled.")
            elif choice == "8":
                return  # Go back to the main menu
            else:
                logger.warning("Invalid choice")
        except Exception as e:
            logger.exception(f"An error has occurred: {e}")


def backup_restore(base_dir, config_dir=None):
    """Displays the backup/restore menu and handles user interaction."""

    if config_dir is None:
        config_dir = settings._config_dir

    os.system("cls" if platform.system() == "Windows" else "clear")
    while True:
        print(f"\n{Fore.MAGENTA}{app_name} - Backup/Restore{Style.RESET_ALL}")
        cli_utils.list_servers_status(base_dir, config_dir)
        print("1) Backup Server")
        print("2) Restore Server")
        print("3) Back")

        choice = input(f"{Fore.CYAN}Select an option [1-3]:{Style.RESET_ALL} ").strip()

        try:
            if choice == "1":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    cli_backup_restore.backup_menu(
                        server_name, base_dir
                    )  # Let it raise exceptions
                else:
                    logger.info("Backup canceled.")
            elif choice == "2":
                server_name = cli_utils.get_server_name(base_dir)
                if server_name:
                    cli_backup_restore.restore_menu(
                        server_name, base_dir
                    )  # Let it raise exceptions
                else:
                    logger.info("Restore canceled.")
            elif choice == "3":
                return  # Go back to the main menu
            else:
                logger.warning("Invalid choice")
        except Exception as e:
            logger.exception(f"An error has occurred: {e}")
