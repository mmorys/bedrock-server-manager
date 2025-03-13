# bedrock-server-manager/bedrock_server_manager/utils/general.py
import sys
from datetime import datetime
from colorama import Fore, Style, init
from bedrock_server_manager.config import settings
import os


def startup_checks():
    """Perform initial checks when the script starts."""
    if sys.version_info < (3, 10):
        sys.exit("This script requires Python 3.10 or later.")
    init(autoreset=True)  # Initialize colorama

    # Create directory used by the script
    os.makedirs(settings.BASE_DIR, exist_ok=True)
    os.makedirs(settings.CONTENT_DIR, exist_ok=True)
    os.makedirs(f"{settings.CONTENT_DIR}/worlds", exist_ok=True)
    os.makedirs(f"{settings.CONTENT_DIR}/addons", exist_ok=True)


def get_timestamp():
    """Returns the current timestamp in YYYYMMDD_HHMMSS format."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def select_option(prompt, default_value, *options):
    """Presents a selection menu to the user.

    Args:
        prompt (str): The prompt to display.
        default_value (str): The default value if the user presses Enter.
        options (tuple): The options to present.

    Returns:
        str: The selected option.
    """
    print(f"{Fore.MAGENTA}{prompt}{Style.RESET_ALL}")
    for i, option in enumerate(options):
        print(f"{i + 1}. {option}")

    while True:
        try:
            choice = input(
                f"{Fore.CYAN}Select an option [Default: {Fore.YELLOW}{default_value}{Fore.CYAN}]:{Style.RESET_ALL} "
            ).strip()
            if not choice:
                print(f"Using default: {Fore.YELLOW}{default_value}{Style.RESET_ALL}")
                return default_value
            choice_num = int(choice)
            if 1 <= choice_num <= len(options):
                return options[choice_num - 1]
            else:
                print(f"{_ERROR_PREFIX}Invalid selection. Please try again.")
        except ValueError:
            print(f"{_ERROR_PREFIX}Invalid input. Please enter a number.")


# Constants for message display
_INFO_PREFIX = Fore.CYAN + "[INFO] " + Style.RESET_ALL
_OK_PREFIX = Fore.GREEN + "[OK] " + Style.RESET_ALL
_WARN_PREFIX = Fore.YELLOW + "[WARN] " + Style.RESET_ALL
_ERROR_PREFIX = Fore.RED + "[ERROR] " + Style.RESET_ALL


def get_base_dir(base_dir=None):
    """Helper function to get the base directory.  Uses a provided value or the configured default."""
    return base_dir if base_dir is not None else settings.BASE_DIR
