# bedrock-server-manager/bedrock_server_manager/web/utils/variable_inject.py
"""
Defines Flask context processors.

Context processors inject variables automatically into the context of Jinja2 templates,
making them globally available within the application's frontend rendering.
"""

import logging
from typing import Dict, Any

# Local imports
from bedrock_server_manager.utils import get_utils
from bedrock_server_manager.config import settings

logger = logging.getLogger("bedrock_server_manager")


def inject_global_variables() -> Dict[str, Any]:
    """
    Context processor to inject globally relevant variables into template contexts.

    Calls helper functions (typically from `bedrock_server_manager.utils.get_utils`)
    to retrieve dynamic values like custom panorama URLs, random splash texts,
    and the application name configured in Flask.

    Returns:
        A dictionary where keys are the variable names made available in templates
        and values are their corresponding resolved values.
    """
    logger.debug("Context Processor: Injecting global template variables...")

    # --- Define Helper Functions to Call ---
    # Using a dictionary allows easier checking and management
    helper_functions = {
        "panorama_url": getattr(get_utils, "_get_panorama_url", None),
        "splash_text": getattr(get_utils, "_get_splash_text", None),
        "app_name": getattr(get_utils, "_get_app_name", None),
        "app_version": getattr(get_utils, "_get_app_version", None),
    }

    global_vars: Dict[str, Any] = {}

    # --- Call Helpers and Populate Variables ---
    for var_name, getter_func in helper_functions.items():
        if getter_func and callable(getter_func):
            try:
                # Call the helper function to get the value
                value = getter_func()
                global_vars[var_name] = value
            except Exception as e:
                # Log error if a helper function unexpectedly fails
                logger.error(
                    f"Context Processor: Error calling helper function '{getter_func.__name__}' for variable '{var_name}': {e}",
                    exc_info=True,
                )
                # Assign a default/safe value (e.g., None or empty string) to prevent template errors
                global_vars[var_name] = None  # Or suitable default
        else:
            logger.warning(
                f"Context Processor: Helper function for global variable '{var_name}' not found or not callable in 'get_utils'. Skipping injection."
            )
            global_vars[var_name] = None  # Assign None if helper is missing

    logger.debug(
        f"Context Processor: Finished injecting variables: {list(global_vars.keys())}"
    )
    return global_vars
