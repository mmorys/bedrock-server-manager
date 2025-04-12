# bedrock-server-manager/bedrock_server_manager/web/app.py
"""
Initializes and configures the Flask web application instance.

Sets up configurations (secret keys, JWT, authentication), registers blueprints
for different application sections, initializes extensions (CSRF, JWT), defines
context processors, and provides a function to run the web server using Waitress
(production) or Flask's built-in development server.
"""

import os
import sys
import logging
import ipaddress
import datetime
import secrets
from typing import Optional, Dict

# Third-party imports
from flask import (
    Flask,
    session,
)

try:
    from waitress import serve

    WAITRESS_AVAILABLE = True
except ImportError:
    WAITRESS_AVAILABLE = False

# Local imports
from bedrock_server_manager.config.settings import settings, env_name
from bedrock_server_manager.web.routes.main_routes import main_bp
from bedrock_server_manager.web.utils.variable_inject import inject_global_variables
from bedrock_server_manager.web.routes.schedule_tasks_routes import schedule_tasks_bp
from bedrock_server_manager.web.routes.server_actions_routes import server_actions_bp
from bedrock_server_manager.web.routes.backup_restore_routes import backup_restore_bp
from bedrock_server_manager.web.routes.api_info_routes import api_info_bp
from bedrock_server_manager.web.routes.content_routes import content_bp
from bedrock_server_manager.web.routes.util_routes import util_bp
from bedrock_server_manager.web.routes.doc_routes import doc_bp
from bedrock_server_manager.web.routes.auth_routes import (
    auth_bp,
    csrf,
    jwt,
)
from bedrock_server_manager.web.utils.validators import register_server_validation
from bedrock_server_manager.web.routes.server_install_config_routes import (
    server_install_config_bp,
)
from bedrock_server_manager.error import FileOperationError

logger = logging.getLogger("bedrock_server_manager")


def create_app() -> Flask:
    """
    Factory function to create and configure the Flask application instance.

    Initializes Flask, sets up secret keys, configures CSRF protection and JWT,
    loads authentication credentials, registers blueprints, and sets up context processors.

    Returns:
        The configured Flask application instance.

    Raises:
        RuntimeError: If essential configurations like SECRET_KEY or JWT_SECRET_KEY
                      cannot be properly set.
        FileOperationError: If required settings like BASE_DIR are missing.
    """
    app = Flask(
        __name__,
        template_folder="templates",  # Relative to this file's location initially
        static_folder="static",  # Relative to this file's location initially
    )
    logger.info("Creating and configuring Flask application instance...")

    # --- Basic App Setup (Paths) ---
    # Ensure paths are absolute relative to this file's directory
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))
    app.template_folder = os.path.join(APP_ROOT, "templates")
    app.static_folder = os.path.join(APP_ROOT, "static")
    # Static URL path defaults to /static, no need to set explicitly unless changing
    app.static_url_path = "/static"
    app.jinja_env.filters["basename"] = os.path.basename
    logger.debug(f"Application Root: {APP_ROOT}")
    logger.debug(f"Template Folder: {app.template_folder}")
    logger.debug(f"Static Folder: {app.static_folder}")

    # --- Validate Essential Settings ---
    if not settings.get("BASE_DIR"):
        logger.critical("Configuration error: BASE_DIR setting is missing or empty.")
        raise FileOperationError("Essential setting BASE_DIR is not configured.")

    # --- Configure Secret Key (CSRF, Session) ---
    secret_key_env = f"{env_name}_SECRET"
    secret_key_value = os.environ.get(secret_key_env)
    if secret_key_value:
        app.config["SECRET_KEY"] = secret_key_value
        logger.info(f"Loaded SECRET_KEY from environment variable '{secret_key_env}'.")
    else:
        app.config["SECRET_KEY"] = secrets.token_hex(16)  # Generate secure random key
        logger.warning(
            f"!!! SECURITY WARNING !!! Using randomly generated SECRET_KEY. "
            f"Flask sessions will not persist across application restarts. "
            f"Set the '{secret_key_env}' environment variable for production."
        )
    # Ensure secret key is truly set before initializing extensions that need it
    if not app.config.get("SECRET_KEY"):
        # This path is highly unlikely with the logic above but is a critical failure
        logger.critical(
            "FATAL: SECRET_KEY is missing after configuration attempt. Cannot initialize CSRF/Session."
        )
        raise RuntimeError(
            "SECRET_KEY must be set for CSRF protection and session management."
        )
    logger.debug("SECRET_KEY configured.")

    # --- Initialize CSRF Protection ---
    csrf.init_app(app)
    # Exempt specific blueprints if needed (e.g., API endpoints using JWT)
    # csrf.exempt(server_actions_bp) # Example if needed
    logger.debug("Initialized Flask-WTF CSRF Protection.")

    # --- Configure JWT ---
    jwt_secret_key_env = f"{env_name}_TOKEN"
    jwt_secret_key_value = os.environ.get(jwt_secret_key_env)
    if jwt_secret_key_value:
        app.config["JWT_SECRET_KEY"] = jwt_secret_key_value
        logger.info(
            f"Loaded JWT_SECRET_KEY from environment variable '{jwt_secret_key_env}'."
        )
    else:
        app.config["JWT_SECRET_KEY"] = secrets.token_urlsafe(
            32
        )  # Generate strong random key
        logger.critical(
            f"!!! SECURITY WARNING !!! Using randomly generated JWT_SECRET_KEY. "
            f"This is NOT suitable for production deployments. Existing JWTs will become invalid "
            f"after application restarts. Set the '{jwt_secret_key_env}' environment variable "
            f"with a persistent, strong, secret key!"
        )
    # Ensure JWT key is set
    if not app.config.get("JWT_SECRET_KEY"):
        logger.critical(
            "FATAL: JWT_SECRET_KEY is missing after configuration attempt. JWT functionality will fail."
        )
        raise RuntimeError("JWT_SECRET_KEY must be set for JWT functionality.")
    logger.debug("JWT_SECRET_KEY configured.")

    # Configure JWT expiration time (get from settings or use default)
    try:
        # For simplicity, let's just do weeks for now, stored as an int/float
        jwt_expires_weeks = float(settings.get("TOKEN_EXPIRES_WEEKS", 4.0))
        app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(
            weeks=jwt_expires_weeks
        )
        logger.debug(f"JWT access token expiration set to {jwt_expires_weeks} weeks.")
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Invalid format for TOKEN_EXPIRES_WEEKS setting. Using default (4 weeks). Error: {e}",
            exc_info=True,
        )
        app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(weeks=4)

    # Initialize JWT Manager
    jwt.init_app(app)
    logger.debug("Initialized Flask-JWT-Extended.")

    # --- Load Web UI Authentication Credentials ---
    username_env = f"{env_name}_USERNAME"
    password_env = f"{env_name}_PASSWORD"
    # Store them in app.config for access within views (e.g., auth route)
    app.config[username_env] = os.environ.get(username_env)
    app.config[password_env] = os.environ.get(password_env)

    if not app.config[username_env] or not app.config[password_env]:
        logger.warning(
            f"Web authentication environment variables ('{username_env}', '{password_env}') "
            f"are not set. Web UI login will not function correctly."
        )
    else:
        logger.info("Web authentication credentials loaded from environment variables.")

    # --- Register Blueprints ---
    app.register_blueprint(main_bp)
    app.register_blueprint(schedule_tasks_bp)
    app.register_blueprint(server_actions_bp)
    app.register_blueprint(server_install_config_bp)
    app.register_blueprint(backup_restore_bp)
    app.register_blueprint(content_bp)
    app.register_blueprint(util_bp)
    app.register_blueprint(api_info_bp)
    app.register_blueprint(doc_bp)
    app.register_blueprint(auth_bp)
    logger.debug("Registered application blueprints.")

    # --- Register Context Processors ---
    # Inject global variables for templates
    app.context_processor(inject_global_variables)
    logger.debug("Registered context processor: inject_global_variables.")

    # Inject login status for templates
    @app.context_processor
    def inject_user() -> Dict[str, bool]:
        is_logged_in = session.get("logged_in", False)
        # logger.debug(f"Injecting context: is_logged_in={is_logged_in}") # Can be noisy
        return dict(is_logged_in=is_logged_in)

    logger.debug("Registered context processor: inject_user (login status).")

    # --- Register Request Validators ---
    register_server_validation(app)
    logger.debug("Registered before_request handler: register_server_validation.")

    logger.info("Flask application creation and configuration complete.")
    return app


def run_web_server(host: Optional[str] = None, debug: bool = False) -> None:
    """
    Starts the Flask web server using Waitress (production) or Flask dev server (debug).

    Checks for required authentication credentials before starting. Determines listening
    addresses based on the `host` parameter (dual-stack IPv4/IPv6 if host is None).

    Args:
        host: The host address to bind to.
              - None (default): Bind to '127.0.0.1' (IPv4) and '::1' (IPv6).
              - Specific IP (v4 or v6): Bind only to that IP.
              - Hostname: Bind to the address(es) the hostname resolves to.
        debug: If True, run using Flask's built-in development server (auto-reload, debugger).
               If False (default), run using Waitress production WSGI server.

    Raises:
        RuntimeError: If required authentication environment variables are not set.
        FileOperationError: If required settings (PORT) are missing.
    """
    app = create_app()  # Create the configured Flask app

    # --- Critical Prerequisite Check: Authentication Credentials ---
    username_env = f"{env_name}_USERNAME"
    password_env = f"{env_name}_PASSWORD"
    if not app.config.get(username_env) or not app.config.get(password_env):
        error_msg = (
            f"Cannot start web server: Required authentication environment variables "
            f"('{username_env}', '{password_env}') are not set."
        )
        logger.critical(error_msg)
        # Raise RuntimeError
        raise RuntimeError(error_msg)

    # --- Get Port ---
    port_setting_key = f"WEB_PORT"
    port = settings.get(port_setting_key, 11325)
    try:
        port = int(port)
        if not (0 < port < 65536):
            raise ValueError("Port out of range")
    except (ValueError, TypeError):
        logger.error(
            f"Invalid port number configured in setting '{port_setting_key}': {port}. Using default 11325."
        )
        port = 11325
    logger.info(f"Web server configured to run on port: {port}")

    # --- Determine Listening Addresses ---
    listen_addresses = []
    host_info = ""

    # Check if host list was provided and is not empty
    if host and isinstance(host, list) and len(host) > 0:
        host_info = f"specified address(es): {', '.join(host)}"
        for h in host:
            # Format each host correctly (add brackets for IPv6)
            try:
                ip = ipaddress.ip_address(h)
                if isinstance(ip, ipaddress.IPv6Address):
                    listen_addresses.append(f"[{h}]:{port}")
                else:
                    listen_addresses.append(f"{h}:{port}")
            except ValueError:
                # Assume hostname
                listen_addresses.append(f"{h}:{port}")
        logger.info(f"Binding to {host_info} -> {listen_addresses}")
    else:
        # Default: Listen on local host only IPv4 and IPv6 interfaces
        listen_addresses = [f"127.0.0.1:{port}", f"[::1]:{port}"]
        host_info = "local host only interfaces (IPv4 and IPv6 dual-stack)"
        logger.info(f"Binding to {host_info} -> {listen_addresses}")

    # --- Start Server (Debug vs. Production) ---
    server_mode = (
        "DEBUG (Flask Development Server)" if debug else "PRODUCTION (Waitress)"
    )
    logger.info(f"Starting web server in {server_mode} mode...")

    if debug:
        # Flask's development server
        logger.warning(
            "Running in DEBUG mode with Flask development server. NOT suitable for production."
        )

        debug_host = None
        if host is None:
            # If user didn't specify --host, default Flask debug to listen on standard IPv4 loopback
            debug_host = "127.0.0.1"
            logger.warning(
                "Debug mode: No host specified, binding only to IPv4 loopback (127.0.0.1). Use --host '::' for all IPv6+IPv4 or --host '::1' for IPv6 loopback."
            )
        elif isinstance(host, list):
            # Extract host part, removing brackets if present
            debug_host = host[0].split(":")[0].strip("[]")
            logger.warning(
                f"Debug mode: Multiple hosts specified, binding only to the first: {debug_host}"
            )
        else:  # A single host string was provided
            # Extract host part, removing brackets if present
            debug_host = host.split(":")[0].strip("[]")

        logger.info(
            f"Attempting to start Flask development server on host='{debug_host}', port={port}..."
        )
        try:
            # Pass the determined host to app.run
            app.run(host=debug_host, port=port, debug=True)
        except OSError as e:
            logger.critical(
                f"Failed to start Flask development server on {debug_host}:{port}. Error: {e}",
                exc_info=True,
            )
            # Common errors: Address already in use, Permission denied (for low ports), Invalid address format
            sys.exit(1)  # Exit if debug server fails to start
        except Exception as e:  # Catch other unexpected errors
            logger.critical(
                f"Unexpected error starting Flask development server: {e}",
                exc_info=True,
            )
            sys.exit(1)
    else:
        # Production server (Waitress)
        if not WAITRESS_AVAILABLE:
            raise ImportError("Waitress package not found.")

        listen_string = " ".join(listen_addresses)  # Join the list for Waitress
        logger.info(
            f"Starting Waitress production server. Listening on: {listen_string}"
        )
        try:
            serve(app, listen=listen_string, threads=4)
        except Exception as e:
            logger.critical(
                f"Failed to start Waitress server. Error: {e}", exc_info=True
            )
            raise
