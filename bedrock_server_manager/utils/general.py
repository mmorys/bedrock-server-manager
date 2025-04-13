# bedrock_server_manager/bedrock_server_manager/utils/general.py
"""
Provides general utility functions for the application.

Includes startup checks, timestamp generation, user interaction helpers,
and configuration accessors.
"""

import sys
import os
import logging
from datetime import datetime
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

    COLORAMA_AVAILABLE = False
    logging.getLogger("bedrock_server_manager").warning(
        "colorama package not found. Console output will lack color."
    )


# Local imports
from bedrock_server_manager.config.settings import settings


logger = logging.getLogger("bedrock_server_manager")

# --- Constants for colored console output ---
# Using _ prefix suggests these are primarily for internal use within utils/CLI
_INFO_PREFIX: str = (
    Fore.CYAN + "[INFO] " + Style.RESET_ALL if COLORAMA_AVAILABLE else "[INFO] "
)
_OK_PREFIX: str = (
    Fore.GREEN + "[OK] " + Style.RESET_ALL if COLORAMA_AVAILABLE else "[OK] "
)
_WARN_PREFIX: str = (
    Fore.YELLOW + "[WARN] " + Style.RESET_ALL if COLORAMA_AVAILABLE else "[WARN] "
)
_ERROR_PREFIX: str = (
    Fore.RED + "[ERROR] " + Style.RESET_ALL if COLORAMA_AVAILABLE else "[ERROR] "
)


def startup_checks(
    app_name: Optional[str] = "BedrockServerManager", version: Optional[str] = "0.0.0"
) -> None:
    """
    Performs initial checks and setup when the application starts.

    - Verifies Python version compatibility (>= 3.10).
    - Writes a separator to the log file.
    - Initializes colorama for colored console output.
    - Creates essential application directories based on settings.

    Args:
        app_name: The name of the application to display in logs.
        version: The version of the application to display in logs.
    """
    # Python Version Check
    if sys.version_info < (3, 10):
        message = "Python version 3.10 or later is required. You are running {}.{}.{}.".format(
            sys.version_info.major, sys.version_info.minor, sys.version_info.micro
        )
        logger.critical(message)
        # Rraising an exception for unsupported Python version
        raise RuntimeError(message)

    # Initialize Colorama
    if COLORAMA_AVAILABLE:
        init(autoreset=True)
        logger.debug("colorama initialized successfully.")
    else:
        logger.debug("colorama not available, skipping initialization.")

    # Ensure essential directories exist
    dirs_to_create = {
        "BASE_DIR": settings.get("BASE_DIR"),
        "CONTENT_DIR": settings.get("CONTENT_DIR"),
        "WORLDS_SUBDIR": (
            os.path.join(str(settings.get("CONTENT_DIR")), "worlds")
            if settings.get("CONTENT_DIR")
            else None
        ),
        "ADDONS_SUBDIR": (
            os.path.join(str(settings.get("CONTENT_DIR")), "addons")
            if settings.get("CONTENT_DIR")
            else None
        ),
        "DOWNLOAD_DIR": settings.get("DOWNLOAD_DIR"),
        "BACKUP_DIR": settings.get("BACKUP_DIR"),
        "LOG_DIR": settings.get("LOG_DIR"),
    }

    for name, dir_path in dirs_to_create.items():
        if dir_path and isinstance(dir_path, str):
            try:
                os.makedirs(dir_path, exist_ok=True)
                logger.debug(f"Ensured directory exists: {dir_path} (Setting: {name})")
            except OSError as e:
                logger.error(
                    f"Failed to create required directory {dir_path} (Setting: {name}): {e}",
                    exc_info=True,
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error creating directory {dir_path} (Setting: {name}): {e}",
                    exc_info=True,
                )
        elif not dir_path:
            logger.warning(
                f"Directory path for '{name}' is missing or empty in settings. Skipping creation."
            )
        else:
            logger.warning(
                f"Directory path for '{name}' expected string, got {type(dir_path)}: {dir_path}. Skipping creation."
            )

    logger.debug("Startup checks completed.")


def get_timestamp() -> str:
    """
    Generates a timestamp string suitable for filenames or logging.

    Returns:
        str: The current timestamp in YYYYMMDD_HHMMSS format.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.debug(f"Generated timestamp: {timestamp}")
    return timestamp


def select_option(prompt: str, default_value: str, *options: str) -> str:
    """
    Presents a numbered selection menu to the user in the console.

    Displays a prompt, lists the available options with numbers,
    and waits for the user to input a number corresponding to their choice.
    Handles invalid input and allows selection via Enter key for the default.

    Args:
        prompt: The question or instruction to display to the user.
        default_value: The option value to return if the user presses Enter without typing input.
        *options: A variable number of string arguments representing the choices.

    Returns:
        str: The option string chosen by the user.

    Raises:
        EOFError: If input stream is closed unexpectedly.
        KeyboardInterrupt: If the user interrupts the input prompt (e.g., Ctrl+C).
    """
    # Ensure default_value is actually one of the options for clarity
    if default_value not in options:
        logger.warning(
            f"Default value '{default_value}' is not in the provided options: {options}"
        )

    # Use print for direct user interaction here
    print(f"{Fore.MAGENTA}{prompt}{Style.RESET_ALL}")
    for i, option in enumerate(options):
        print(f"  {i + 1}. {option}")

    while True:
        try:
            # Construct the input prompt string
            input_prompt = f"{Fore.CYAN}Select an option (1-{len(options)}) [Default: {Fore.YELLOW}{default_value}{Fore.CYAN}]:{Style.RESET_ALL} "
            choice_str = input(input_prompt).strip()

            if not choice_str:
                print(
                    f"{_INFO_PREFIX}Using default selection: {Fore.YELLOW}{default_value}{Style.RESET_ALL}"
                )
                logger.debug(
                    f"User selected default option '{default_value}' for prompt: '{prompt}'"
                )
                return default_value

            choice_num = int(choice_str)  # Can raise ValueError

            if 1 <= choice_num <= len(options):
                selected_option = options[choice_num - 1]
                logger.debug(
                    f"User selected option #{choice_num} ('{selected_option}') for prompt: '{prompt}'"
                )
                return selected_option
            else:
                # Invalid number range
                print(
                    f"{_ERROR_PREFIX}Invalid selection. Please enter a number between 1 and {len(options)}."
                )
                logger.warning(
                    f"Invalid selection number '{choice_num}' entered for prompt: '{prompt}'"
                )

        except ValueError:
            # Input was not a number or empty string
            print(f"{_ERROR_PREFIX}Invalid input. Please enter a number.")
            logger.warning(
                f"Non-integer input '{choice_str}' entered for prompt: '{prompt}'"
            )
        # KeyboardInterrupt and EOFError will naturally propagate up if not caught here


def get_base_dir(base_dir: Optional[str] = None) -> str:
    """
    Determines the base directory for server installations.

    Uses the provided 'base_dir' if given, otherwise falls back to the
    'BASE_DIR' value configured in the application settings.

    Args:
        base_dir: An optional path string to use as the base directory.

    Returns:
        str: The determined base directory path.

    Raises:
        TypeError: If the resolved base directory from settings is not a string.
        # Or handle non-string case differently, e.g., return default or raise specific error
    """
    if base_dir is not None:
        logger.debug(f"Using provided base directory: {base_dir}")
        return base_dir
    else:
        configured_base_dir = settings.get("BASE_DIR")
        logger.debug(
            f"Using configured base directory from settings: {configured_base_dir}"
        )
        if not isinstance(configured_base_dir, str):
            # Handle error: Log, raise, or return a default?
            logger.error(
                f"Configured BASE_DIR is not a valid string path: {configured_base_dir}"
            )
            raise TypeError(
                f"Expected BASE_DIR setting to be a string, but got {type(configured_base_dir)}"
            )
        return configured_base_dir
