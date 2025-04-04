# bedrock-server-manager/bedrock_server_manager/web/utils/variable_inject.py
import os
import logging
import random
from bedrock_server_manager.utils.splash_text import SPLASH_TEXTS
from bedrock_server_manager.utils import get_utils
from bedrock_server_manager.config.settings import app_name, settings
from flask import (
    url_for,
    current_app,
)

logger = logging.getLogger("bedrock_server_manager")

def inject_global_variables():
    """
    Injects globally needed variables into all template contexts
    by calling helper functions for each variable.
    """
    global_vars = {
        "panorama_url": get_utils._get_panorama_url(),
        "splash_text": get_utils._get_splash_text(),
        "app_name": get_utils._get_app_name(),
    }
    logger.debug(f"Context Processor: Injecting global variables: {list(global_vars.keys())}")
    return global_vars
