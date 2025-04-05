# bedrock-server-manager/bedrock_server_manager/utils/get_utils.py
import os
import logging
import random
from bedrock_server_manager.utils.splash_text import SPLASH_TEXTS
from bedrock_server_manager.config.settings import app_name, settings
from flask import (
    url_for,
    current_app,
)

logger = logging.getLogger("bedrock_server_manager")

# --- Helper Functions ---


def _get_panorama_url():
    """
    Determines the URL for the custom panorama image, if it exists.

    Returns:
        str or None: The URL to the custom panorama endpoint if found,
                     otherwise None.
    """
    panorama_url = None
    try:
        # Ensure settings and _config_dir attribute exist
        config_dir = getattr(settings, "_config_dir", None)
        if config_dir:
            # Prefer absolute path directly from settings if possible
            # Otherwise, construct it relative to app root or use get_base_dir logic carefully
            config_dir_abs = os.path.abspath(config_dir)  # Ensure absolute path

            panorama_fs_path = os.path.join(config_dir_abs, "panorama.jpeg")
            if os.path.exists(panorama_fs_path):
                # Ensure the endpoint name matches the route definition in your util_routes blueprint
                # Example: blueprint is named 'util_routes', function is 'serve_custom_panorama'
                panorama_url = url_for("util_routes.serve_custom_panorama")
                logger.debug(
                    f"Context Helper: Custom panorama found. URL: {panorama_url}"
                )
            else:
                logger.debug(
                    f"Context Helper: Custom panorama file not found at: {panorama_fs_path}"
                )
        else:
            logger.debug(
                "Context Helper: settings._config_dir not set, skipping custom panorama check."
            )
    except Exception as e:
        # Log error but don't crash the app; return None
        logger.exception(f"Context Helper: Error checking for custom panorama: {e}")
        panorama_url = None  # Ensure None is returned on error

    return panorama_url


def _get_splash_text():
    """
    Selects a random splash text from the configured SPLASH_TEXTS.

    Handles different structures for SPLASH_TEXTS (dict of lists, list/tuple).

    Returns:
        str: A randomly chosen splash text or a fallback message.
    """
    fallback_splash = "Looking Good!"
    chosen_splash = fallback_splash

    try:
        # Check if SPLASH_TEXTS is defined and accessible
        if "SPLASH_TEXTS" not in globals() and "SPLASH_TEXTS" not in locals():
            logger.warning("Context Helper: SPLASH_TEXTS constant not found.")
            return fallback_splash

        if isinstance(SPLASH_TEXTS, dict) and SPLASH_TEXTS:
            # If it's a dictionary, flatten all its list values into one list
            all_texts = [
                text
                for category_list in SPLASH_TEXTS.values()
                if isinstance(
                    category_list, (list, tuple)
                )  # Ensure values are iterable
                for text in category_list
            ]
            if all_texts:
                chosen_splash = random.choice(all_texts)
            # else: chosen_splash remains fallback_splash
        elif isinstance(SPLASH_TEXTS, (list, tuple)) and SPLASH_TEXTS:
            # If it's already a list or tuple, use it directly
            chosen_splash = random.choice(SPLASH_TEXTS)
        # else: SPLASH_TEXTS is empty, None, or unexpected type
        # chosen_splash remains fallback_splash

    except NameError:
        logger.warning("Context Helper: SPLASH_TEXTS constant is not defined.")
        chosen_splash = fallback_splash  # Explicitly set fallback if NameError occurs
    except Exception as e:
        logger.exception(f"Context Helper: Error choosing splash text: {e}")
        chosen_splash = "Error!"  # Fallback on any other processing error

    logger.debug(f"Context Helper: Selected splash text: {chosen_splash}")
    return chosen_splash


def _get_app_name():
    """
    Retrieves the application name from the Flask app config.

    Returns:
        str: The configured application name or a default value.
    """
    # Default name if 'APP_NAME' is not set in Flask config
    default_app_name = "Bedrock Server Manager"
    app_name = default_app_name
    try:
        # Use current_app which is available during request/application context
        app_name = current_app.config.get("APP_NAME", default_app_name)
    except RuntimeError:
        # This might happen if called outside of an app context, though
        # context processors usually run within one. Log and use default.
        logger.warning(
            "Context Helper: _get_app_name called outside of application context."
        )
        app_name = default_app_name
    except Exception as e:
        logger.exception(f"Context Helper: Error getting app name: {e}")
        app_name = default_app_name  # Fallback on unexpected errors

    return app_name
