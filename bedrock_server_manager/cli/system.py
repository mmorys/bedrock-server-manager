# bedrock-server-manager/bedrock_server_manager/cli/system.py
import os
import time
import logging
import platform
from colorama import Fore, Style
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.api import system
from bedrock_server_manager.core.error import InvalidServerNameError
from bedrock_server_manager.utils.general import (
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger("bedrock_server_manager")


def create_service(server_name, base_dir=None):
    """Creates a systemd service (Linux) or sets autoupdate config (Windows)."""
    if base_dir is None:
        base_dir = settings.get("BASE_DIR")
    if not server_name:
        raise InvalidServerNameError("create_service: server_name is empty.")
    if platform.system() == "Linux":
        # Ask user if they want auto-update
        while True:
            response = (
                input(
                    f"{Fore.CYAN}Do you want to enable auto-update on start for {Fore.YELLOW}{server_name}{Fore.CYAN}? (y/n):{Style.RESET_ALL} "
                )
                .lower()
                .strip()
            )
            if response in ("yes", "y"):
                autoupdate = True
                break
            elif response in ("no", "n", ""):
                autoupdate = False
                break
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

        while True:
            response = (
                input(
                    f"{Fore.CYAN}Do you want to enable autostart for {Fore.YELLOW}{server_name}{Fore.CYAN}? (y/n):{Style.RESET_ALL} "
                )
                .lower()
                .strip()
            )
            if response in ("yes", "y"):
                autostart = True
                break
            elif response in ("no", "n", ""):
                autostart = False
                break
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

        response = system.create_systemd_service(
            server_name, base_dir, autoupdate, autostart
        )
        if response["status"] == "error":
            print(f"{_ERROR_PREFIX}{response['message']}")
            return

    elif platform.system() == "Windows":
        while True:
            response = (
                input(
                    f"{Fore.CYAN}Do you want to enable auto-update on start for {Fore.YELLOW}{server_name}{Fore.CYAN}? (y/n):{Style.RESET_ALL} "
                )
                .lower()
                .strip()
            )
            if response in ("yes", "y"):
                autoupdate_value = "true"
                break
            elif response in ("no", "n", ""):
                autoupdate_value = "false"
                break
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

        response = system.set_windows_autoupdate(
            server_name, autoupdate_value, base_dir
        )
        if response["status"] == "error":
            print(f"{_ERROR_PREFIX}{response['message']}")
        else:
            print(
                f"{_OK_PREFIX}Successfully updated autoupdate in config.json for server: {server_name}"
            )

    else:
        print(f"{_ERROR_PREFIX}Unsupported operating system for service creation.")
        raise OSError("Unsupported operating system for service creation.")


def enable_service(server_name, base_dir=None):
    """Enables a systemd service (Linux) or handles the Windows case."""
    if not server_name:
        raise InvalidServerNameError("enable_service: server_name is empty.")

    response = system.enable_server_service(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    elif platform.system() == "Windows":
        print(
            "Windows doesn't currently support all script features. You may want to look into Windows Subsystem Linux (wsl)."
        )
    elif platform.system() != "Linux":
        raise OSError("Unsupported OS")
    else:
        print(f"{_OK_PREFIX}Service enabled successfully.")


def disable_service(server_name, base_dir=None):
    """Disables a systemd service (Linux) or handles the Windows case."""
    if not server_name:
        raise InvalidServerNameError("disable_service: server_name is empty.")

    response = system.disable_server_service(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    elif platform.system() == "Windows":
        print(
            "Windows doesn't currently support all script features. You may want to look into Windows Subsystem Linux (wsl)."
        )
    elif platform.system() != "Linux":
        raise OSError("Unsupported OS")
    else:
        print(f"{_OK_PREFIX}Service disabled successfully.")


def _monitor(server_name, base_dir):
    """Monitor for Bedrock server (UI portion)."""

    if not server_name:
        raise InvalidServerNameError("_monitor: server_name is empty.")

    print(f"{_INFO_PREFIX}Monitoring resource usage for: {server_name}")
    try:
        while True:
            response = system.get_bedrock_process_info(server_name, base_dir)
            if response["status"] == "error":
                print(f"{_ERROR_PREFIX}{response['message']}")
                return  # Exit if process not found

            process_info = response["process_info"]

            # Clear screen and display output (CLI-specific)
            os.system("cls" if platform.system() == "Windows" else "clear")
            print("---------------------------------")
            print(f" Monitoring:  {server_name} ")
            print("---------------------------------")
            print(f"PID:          {process_info['pid']}")
            print(f"CPU Usage:    {process_info['cpu_percent']:.1f}%")
            print(f"Memory Usage: {process_info['memory_mb']:.1f} MB")
            print(f"Uptime:       {process_info['uptime']}")
            print("---------------------------------")
            print("Press CTRL + C to exit")

            time.sleep(2)  # Update interval

    except KeyboardInterrupt:
        print(f"{_OK_PREFIX}Monitoring stopped.")


def monitor_service_usage(server_name, base_dir=None):
    """Monitors the CPU and memory usage of the Bedrock server."""
    base_dir = get_base_dir(base_dir)
    _monitor(server_name, base_dir)
