# bedrock_server_manager/bedrock_server_manager/utils/get_utils.py
"""
Provides utility helper functions, primarily intended for use within a
Flask application context (e.g., context processors) to inject dynamic
data into templates.
"""

import os
import logging
import random
from typing import Optional

# Third-party imports
from flask import url_for, current_app

# Local imports
from bedrock_server_manager.utils.splash_text import SPLASH_TEXTS
from bedrock_server_manager.config.settings import settings, __version__

logger = logging.getLogger("bedrock_server_manager")

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
        config_dir = getattr(settings, "_config_dir", None)
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
    Retrieves the application name, primarily from the Flask app configuration.

    Requires a Flask application context to access 'current_app.config'.

    Returns:
        The application name string configured in Flask ('APP_NAME'),
        or a default name if not configured or if called outside a Flask context.
    """
    default_app_name: str = "Bedrock Server Manager"  # Default name
    app_name: str = default_app_name

    try:
        # Requires an active Flask application context
        app_name = current_app.config.get("APP_NAME", default_app_name)
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
    Retrieves the application version for web server display

    Requires a version string in a '#.#.#' format.

    Returns:
        The application version string pulled from app meta,
        or a default version if not found.
    """
    default_app_version: str = "0.0.0"  # Default version
    app_version: str = default_app_version

    try:
        # Get app version from settings
        app_version = __version__

    except Exception as e:
        logger.exception(
            f"Context Helper: Unexpected error getting app version: {e}", exc_info=True
        )
        app_veersion = default_app_version  # Fallback on unexpected errors

    return app_version
