# bedrock-server-manager/bedrock_server_manager/web/app.py
import os
from waitress import serve
from os.path import basename
import logging
import ipaddress
from flask import Flask
import secrets
from bedrock_server_manager.config.settings import settings, env_name
from bedrock_server_manager.web.routes import server_routes


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

    APP_ROOT = os.path.dirname(os.path.abspath(__file__))
    template_folder = os.path.join(APP_ROOT, "templates")
    static_folder = os.path.join(APP_ROOT, "static")
    app.template_folder = template_folder
    app.static_folder = static_folder
    app.jinja_env.filters["basename"] = basename
    logger.debug(f"Template folder: {template_folder}")
    logger.debug(f"Static folder: {static_folder}")

    # --- Set a SECRET KEY ---
    app.config["SECRET_KEY"] = secrets.token_hex(16)

    app.register_blueprint(server_routes.server_bp)
    logger.debug("Registered blueprints")

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
    port = settings.get(f"{env_name}_PORT")
    logger.debug(f"Starting web server. Debug mode: {debug}, Port: {port}")

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
