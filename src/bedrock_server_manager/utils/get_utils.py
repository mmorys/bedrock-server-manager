# bedrock_server_manager/bedrock_server_manager/utils/get_utils.py
"""
Provides utility helper functions, primarily intended for use within a
Flask application context (e.g., context processors) to inject dynamic
data into templates.
"""

import os
import platform
import logging
import random
from typing import Optional

# Third-party imports
from flask import url_for

# Local imports
from bedrock_server_manager.config.splash_text import SPLASH_TEXTS
from bedrock_server_manager.config.const import app_name_title, get_installed_version
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import SystemError

logger = logging.getLogger(__name__)

# --- Template Context Helper Functions ---


def _get_panorama_url() -> Optional[str]:
    """
    Determines the URL for a custom panorama image if it exists.

    Checks for 'panorama.jpeg' within the application's configuration directory.
    Requires a Flask application context to generate the URL using 'url_for'.

    Returns:
        The URL string for the custom panorama endpoint if the image file exists,
        otherwise None.
    """
    panorama_url: Optional[str] = None
    try:
        # Accessing _config_dir directly; consider adding a public getter to Settings class
        config_dir = getattr(settings, "config_dir", None)
        if config_dir:
            # Construct the expected path to the panorama file
            panorama_fs_path = os.path.join(config_dir, "panorama.jpeg")
            logger.debug(
                f"Context Helper: Checking for panorama at: {panorama_fs_path}"
            )

            if os.path.exists(panorama_fs_path):
                # This requires an active Flask application context.
                try:
                    panorama_url = url_for("util_routes.serve_custom_panorama")
                    logger.debug(
                        f"Context Helper: Custom panorama found. Generated URL: {panorama_url}"
                    )
                except Exception as url_err:
                    logger.error(
                        f"Context Helper: Found panorama file but failed to generate URL: {url_err}",
                        exc_info=True,
                    )
                    panorama_url = None  # Ensure None if URL generation fails
            else:
                logger.debug("Context Helper: Custom panorama file not found.")
        else:
            logger.warning(
                "Context Helper: Settings object lacks '_config_dir'. Cannot check for custom panorama."
            )

    except Exception as e:
        # Catch any unexpected errors during the process
        logger.exception(
            f"Context Helper: Unexpected error checking for custom panorama: {e}",
            exc_info=True,
        )
        panorama_url = None  # Ensure None is returned on error

    return panorama_url


def _get_splash_text() -> str:
    """
    Selects and returns a random splash text message.

    Pulls from the SPLASH_TEXTS constant defined in 'splash_text.py'.
    Handles cases where SPLASH_TEXTS might be a dictionary of lists, a simple list/tuple,
    empty, or not defined.

    Returns:
        A randomly chosen splash text string, or a fallback message if none can be selected.
    """
    fallback_splash: str = "Amazing Error Handling!"
    chosen_splash: str = fallback_splash

    try:
        # Check if SPLASH_TEXTS is defined and accessible
        if "SPLASH_TEXTS" not in globals() and "SPLASH_TEXTS" not in locals():
            logger.warning(
                "Context Helper: SPLASH_TEXTS constant not found or not imported."
            )
            return fallback_splash  # Return fallback if constant isn't available

        all_texts = []
        if isinstance(SPLASH_TEXTS, dict) and SPLASH_TEXTS:
            # If it's a dictionary, flatten all its list/tuple values into one list
            for category_list in SPLASH_TEXTS.values():
                if isinstance(category_list, (list, tuple)):
                    all_texts.extend(category_list)
            logger.debug("Context Helper: Processing SPLASH_TEXTS as dictionary.")
        elif isinstance(SPLASH_TEXTS, (list, tuple)) and SPLASH_TEXTS:
            # If it's already a list or tuple, use it directly
            all_texts = list(SPLASH_TEXTS)  # Ensure it's a list for consistency
            logger.debug("Context Helper: Processing SPLASH_TEXTS as list/tuple.")
        else:
            logger.debug(
                f"Context Helper: SPLASH_TEXTS is empty or has an unexpected type ({type(SPLASH_TEXTS)}). Using fallback."
            )
            # all_texts remains empty, will use fallback

        if all_texts:
            chosen_splash = random.choice(all_texts)
        else:
            # Log if we had the constant but it resulted in no usable texts
            if "SPLASH_TEXTS" in globals() or "SPLASH_TEXTS" in locals():
                logger.debug(
                    "Context Helper: No valid splash texts found after processing SPLASH_TEXTS constant. Using fallback."
                )
            # Otherwise, the warning about the constant not being found was already logged.
            chosen_splash = fallback_splash  # Ensure fallback if list is empty

    except NameError:
        # This case should be caught by the initial check, but kept for safety
        logger.warning(
            "Context Helper: SPLASH_TEXTS constant is not defined (NameError)."
        )
        chosen_splash = fallback_splash
    except Exception as e:
        logger.exception(
            f"Context Helper: Error choosing splash text: {e}", exc_info=True
        )
        chosen_splash = "Error retrieving splash!"  # Fallback indicating an error state

    logger.debug(f"Context Helper: Selected splash text: '{chosen_splash}'")
    return chosen_splash


def _get_app_name() -> str:
    """
    Retrieves the application's user-friendly title.

    Returns:
        The application name string, derived from `app_name_title` constant.
    """
    default_app_name: str = app_name_title  # Default name
    app_name: str = default_app_name

    try:
        # Requires an active Flask application context
        app_name = app_name_title  # Access the app name from settings
        logger.debug(
            f"Context Helper: Retrieved app name from Flask config: '{app_name}'"
        )
    except RuntimeError:
        # This occurs if 'current_app' is accessed outside of an active Flask context.
        logger.warning(
            "Context Helper: _get_app_name called outside of Flask application context. Using default name."
        )
        app_name = default_app_name  # Ensure default is used
    except Exception as e:
        logger.exception(
            f"Context Helper: Unexpected error getting app name: {e}", exc_info=True
        )
        app_name = default_app_name  # Fallback on unexpected errors

    return app_name


def _get_app_version() -> str:
    """
    Retrieves the installed application version.

    Returns:
        The application version string (e.g., "1.2.3") by accessing
        `settings.version`, or "0.0.0" if not found.
    """
    default_app_version: str = "0.0.0"  # Default version
    app_version: str = default_app_version

    try:
        # Get app version from settings
        app_version = settings.version

    except Exception as e:
        logger.exception(
            f"Context Helper: Unexpected error getting app version: {e}", exc_info=True
        )
        app_veersion = default_app_version  # Fallback on unexpected errors

    return app_version


def get_operating_system_type() -> str:
    """
    Retrieves the operating system type.

    Returns:
        A string representing the OS type (e.g., "Linux", "Windows", "Darwin").

    Raises:
        SystemError: If the OS type cannot be determined (highly unlikely).
    """
    try:
        os_type = platform.system()
        if not os_type:
            # This case is extremely rare with platform.system()
            raise SystemError("Could not determine operating system type.")
        logger.debug(f"Core: Determined OS Type: {os_type}")
        return os_type
    except Exception as e:
        logger.error(f"Core: Error getting OS type: {e}", exc_info=True)
        # Re-raise as a custom error or handle differently if preferred
        raise SystemError(f"Failed to get OS type: {e}")
