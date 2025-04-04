# bedrock-server-manager/bedrock_server_manager/web/app.py
import os
import logging
import ipaddress
import datetime
import secrets
from waitress import serve
from os.path import basename
from flask import Flask, session
from flask_wtf.csrf import CSRFProtect
from bedrock_server_manager.config.settings import settings, env_name
from bedrock_server_manager.web.routes.main_routes import main_bp
from bedrock_server_manager.web.utils.variable_inject import inject_global_variables
from bedrock_server_manager.web.routes.schedule_tasks_routes import schedule_tasks_bp
from bedrock_server_manager.web.routes.server_actions_routes import server_actions_bp
from bedrock_server_manager.web.routes.server_install_config_routes import (
    server_install_config_bp,
)
from bedrock_server_manager.web.routes.backup_restore_routes import backup_restore_bp
from bedrock_server_manager.web.routes.content_routes import content_bp
from bedrock_server_manager.web.routes.auth_routes import auth_bp, csrf, jwt


logger = logging.getLogger("bedrock_server_manager")


def create_app():
    """Creates the Flask application instance."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )
    logger.debug("Creating Flask app")

    app.context_processor(inject_global_variables)
    logger.debug("Registered context processor: inject_global_variables")

    APP_ROOT = os.path.dirname(os.path.abspath(__file__))
    template_folder = os.path.join(APP_ROOT, "templates")
    static_folder = os.path.join(APP_ROOT, "static")
    app.template_folder = template_folder
    app.static_folder = static_folder
    app.jinja_env.filters["basename"] = basename
    logger.debug(f"Template folder: {template_folder}")
    logger.debug(f"Static folder: {static_folder}")

    # --- Set a SECRET KEY (Crucial for sessions) ---
    secret_key_env = f"{env_name}_SECRET"
    secret_key_value = os.environ.get(secret_key_env)
    if secret_key_value:
        app.config["SECRET_KEY"] = secret_key_value
        logger.info(f"Loaded SECRET_KEY from environment variable {secret_key_env}")
    else:
        app.config["SECRET_KEY"] = secrets.token_hex(16)
        logger.warning(
            f"Using randomly generated SECRET_KEY. "
            f"Set {secret_key_env} environment variable for persistent sessions across restarts."
        )
        # --- Ensure SECRET_KEY is always set before initializing CSRF ---
        if not app.config["SECRET_KEY"]:
            logger.error("SECRET_KEY is not set. Web server cannot be enabled.")
            raise RuntimeError("SECRET_KEY must be set for CSRF protection")
    logger.debug("SECRET_KEY set")

    csrf.init_app(app)
    csrf.exempt(server_actions_bp)
    logger.debug("Initialized Flask-WTF CSRF Protection")

    jwt_secret_key_env = f"{env_name}_TOKEN"
    jwt_secret_key_value = os.environ.get(jwt_secret_key_env)

    if not jwt_secret_key_value:
        # --- SECURITY WARNING ---
        app.config["JWT_SECRET_KEY"] = secrets.token_urlsafe(
            32
        )  # Generate a strong, URL-safe key
        logger.critical(
            f"!!! SECURITY WARNING !!! Using randomly generated JWT_SECRET_KEY. "
            f"This is NOT suitable for production. Existing JWTs will be invalid after restart. "
            f"Set the {jwt_secret_key_env} environment variable with a persistent, strong secret key!"
        )
        # --- END WARNING ---
    else:
        app.config["JWT_SECRET_KEY"] = jwt_secret_key_value
        logger.info(
            f"Loaded JWT_SECRET_KEY from environment variable {jwt_secret_key_env}"
        )

    if not app.config.get("JWT_SECRET_KEY"):
        # This should ideally not happen with the logic above, but double-check
        logger.error(
            "FATAL: JWT_SECRET_KEY is not configured. JWT functionality will fail."
        )
        raise RuntimeError("JWT_SECRET_KEY must be set")
    logger.debug("JWT_SECRET_KEY set")

    app.config["API_ONLY_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(hours=12)

    jwt.init_app(app)
    logger.debug("Initialized Flask-JWT-Extended")

    # --- Load Authentication Credentials ---
    username_env = f"{env_name}_USERNAME"
    password_env = f"{env_name}_PASSWORD"
    app.config[username_env] = os.environ.get(username_env)
    app.config[password_env] = os.environ.get(password_env)

    # --- Log a warning if credentials are not set ---
    if not app.config[username_env] or not app.config[password_env]:
        logger.warning(
            f"Authentication environment variables ({username_env}, {password_env}) are not set."
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
    app.register_blueprint(auth_bp)
    logger.debug("Registered blueprints...")

    # --- Add context processor to make login status available to templates ---
    @app.context_processor
    def inject_user():
        return dict(is_logged_in=session.get("logged_in", False))

    logger.debug("Registered context processor: inject_user")

    return app


def run_web_server(host=None, debug=False):
    """Starts the Flask web server, binding to both IPv4 and IPv6 if no host is specified.

    Args:
        host (str, optional):  The host address to bind to.
                               If None, binds to both IPv4 (0.0.0.0) and IPv6 (::).
                               Can be a specific IPv4, IPv6, or hostname.
        debug (bool): Whether to run in Flask's debug mode.
    """
    app = create_app()

    # --- Check credentials before starting server ---
    username_env = f"{env_name}_USERNAME"
    password_env = f"{env_name}_PASSWORD"
    if not app.config.get(username_env) or not app.config.get(password_env):
        logger.error(
            f"Cannot start web server: {username_env} or {password_env} environment variables are not set."
        )

        return

    port = settings.get(f"{env_name}_PORT")
    logger.info(f"Starting web server. Debug mode: {debug}, Port: {port}")

    if host is None:
        # Bind to both IPv4 and IPv6
        listen_addresses = [f"0.0.0.0:{port}", f"[::]:{port}"]  # List of addresses
        logger.info(
            f"No host specified, binding to both IPv4 and IPv6: {listen_addresses}"
        )
    else:
        # Bind to the specified host (IPv4, IPv6, or hostname)
        try:
            ip = ipaddress.ip_address(host)
            if isinstance(ip, ipaddress.IPv6Address):
                listen_addresses = [f"[{host}]:{port}"]
                logger.info(f"Binding to IPv6 address: {listen_addresses[0]}")
            else:
                listen_addresses = [f"{host}:{port}"]
                logger.info(f"Binding to IPv4 address: {listen_addresses[0]}")
        except ValueError:
            # Assume it's a hostname
            listen_addresses = [f"{host}:{port}"]
            logger.info(f"Binding to hostname: {listen_addresses[0]}")

    if debug:
        # Flask's debug mode (development)
        if host is None:
            logger.warning("Flask debug mode doesn't support dual-stack binding.")
            app.run(host="0.0.0.0", port=port, debug=True)
            logger.info("Started Flask development server (0.0.0.0) in debug mode.")
        else:
            # If a specific host was provided, use it.
            app.run(
                host=listen_addresses[0].split(":")[0].strip("[]"),
                port=port,
                debug=True,
            )  # strip []
            logger.info(
                f"Started Flask development server ({listen_addresses[0]}) in debug mode."
            )
    else:
        # Waitress (production)
        serve(
            app, listen=" ".join(listen_addresses), threads=4
        )  # Pass addresses as space-separated string
        logger.info(
            f"Started Waitress production server, listening on: {' '.join(listen_addresses)}"
        )
