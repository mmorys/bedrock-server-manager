# bedrock-server-manager/bedrock_server_manager/utils/general.py
import sys
from datetime import datetime
from colorama import Fore, Style, init
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.logging import log_separator
import os
import logging

logger = logging.getLogger("bedrock_server_manager")


def startup_checks(app_name=None, version=None):
    """Perform initial checks when the script starts."""

    if sys.version_info < (3, 10):
        logger.critical("Python version is less than 3.10. Exiting.")
        sys.exit("This script requires Python 3.10 or later.")

    log_separator(logger, app_name=app_name, app_version=version)

    logger.info(f"Starting {app_name} v{version}....")

    init(autoreset=True)  # Initialize colorama
    logger.debug("colorama initialized")

    content_dir = settings.get("CONTENT_DIR")
    # Create directory used by the script
    os.makedirs(settings.get("BASE_DIR"), exist_ok=True)
    logger.debug(f"Created directory: {settings.get('BASE_DIR')}")
    os.makedirs(content_dir, exist_ok=True)
    logger.debug(f"Created directory: {content_dir}")
    os.makedirs(f"{content_dir}/worlds", exist_ok=True)
    logger.debug(f"Created directory: {content_dir}/worlds")
    os.makedirs(f"{content_dir}/addons", exist_ok=True)
    logger.debug(f"Created directory: {content_dir}/addons")
    logger.debug("Startup checks complete")


def get_timestamp():
    """Returns the current timestamp in YYYYMMDD_HHMMSS format."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.debug(f"Generated timestamp: {timestamp}")
    return timestamp


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
                logger.debug(f"User selected default option: {default_value}")
                return default_value
            choice_num = int(choice)
            if 1 <= choice_num <= len(options):
                logger.debug(f"User selected option: {options[choice_num - 1]}")
                return options[choice_num - 1]
            else:
                print(f"{_ERROR_PREFIX}Invalid selection. Please try again.")
                logger.warning("Invalid selection in select_option")
        except ValueError:
            print(f"{_ERROR_PREFIX}Invalid input. Please enter a number.")
            logger.warning("Invalid input in select_option")


# Constants for message display
_INFO_PREFIX = Fore.CYAN + "[INFO] " + Style.RESET_ALL
_OK_PREFIX = Fore.GREEN + "[OK] " + Style.RESET_ALL
_WARN_PREFIX = Fore.YELLOW + "[WARN] " + Style.RESET_ALL
_ERROR_PREFIX = Fore.RED + "[ERROR] " + Style.RESET_ALL


def get_base_dir(base_dir=None):
    """Helper function to get the base directory.  Uses a provided value or the configured default."""
    base_dir_value = base_dir if base_dir is not None else settings.get("BASE_DIR")
    logger.debug(f"Base directory: {base_dir_value}")
    return base_dir_value
