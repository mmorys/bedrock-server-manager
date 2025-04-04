# bedrock-server-manager/bedrock_server_manager/web/utils/variable_inject.py
import os
import logging
import random
from bedrock_server_manager.web.utils.splash_text import SPLASH_TEXTS
from bedrock_server_manager.config.settings import app_name, settings
from flask import (
    url_for,
    current_app,
)

logger = logging.getLogger("bedrock_server_manager")


def inject_global_variables():
    """Injects variables needed by base.html into all template contexts."""
    global_vars = {}

    # --- Panorama URL Logic ---
    panorama_url = None
    try:
        config_dir = settings._config_dir
        if config_dir:
            # Prefer absolute path directly from settings if possible
            # Otherwise, construct it relative to app root or use get_base_dir logic carefully
            config_dir_abs = os.path.abspath(config_dir)  # Ensure absolute

            panorama_fs_path = os.path.join(config_dir_abs, "panorama.jpeg")
            if os.path.exists(panorama_fs_path):
                # Ensure the endpoint name is correct (matches the route definition)
                panorama_url = url_for("util_routes.serve_custom_panorama")
                logger.debug(
                    f"Context Processor: Custom panorama found. URL: {panorama_url}"
                )
            else:
                logger.debug(
                    f"Context Processor: Custom panorama file not found at: {panorama_fs_path}"
                )
        else:
            logger.debug(
                "Context Processor: CONFIG_DIR not set, skipping custom panorama check."
            )
    except Exception as e:
        # Log error but don't crash the app
        logger.exception(f"Context Processor: Error checking for custom panorama: {e}")
    global_vars["panorama_url"] = panorama_url

    # --- Splash Text Logic ---
    try:
        if isinstance(SPLASH_TEXTS, dict) and SPLASH_TEXTS:
            # If it's a dictionary, flatten all its list values into one list
            all_texts = [
                text
                for category_list in SPLASH_TEXTS.values()
                for text in category_list
            ]
            if all_texts:
                chosen_splash = random.choice(all_texts)
            else:
                chosen_splash = "Looking Good!"  # No texts found in dict values
        elif isinstance(SPLASH_TEXTS, (list, tuple)) and SPLASH_TEXTS:
            # If it's already a list or tuple (original format), use it directly
            chosen_splash = random.choice(SPLASH_TEXTS)
        else:
            # Fallback if SPLASH_TEXTS is empty or None or unexpected type
            chosen_splash = "Looking Good!"

    except Exception as e:
        logger.exception(f"Context Processor: Error choosing splash text: {e}")
        chosen_splash = "Error!"  # Fallback on any error during processing
    global_vars["splash_text"] = chosen_splash
    logger.debug(f"Context Processor: Injecting splash text: {chosen_splash}")

    # --- Add App Name  ---
    global_vars["app_name"] = current_app.config.get(
        "APP_NAME", "Bedrock Server Manager"
    )

    return global_vars  # Return dictionary of variables to inject
