# bedrock-server-manager/bedrock_server_manager/web/app.py
import os
from flask import Flask
import secrets
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.web.routes import server_routes
from waitress import serve
from os.path import basename
import logging

logger = logging.getLogger("bedrock_server_manager")


def create_app():
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
    app.config["SECRET_KEY"] = secrets.token_hex(16)  # Generate a random key
    # logger.debug(f"Secret key set: {app.config['SECRET_KEY']}")

    app.register_blueprint(server_routes.server_bp)
    logger.debug("Registered blueprints")

    return app


def main():
    app = create_app()
    port = settings.get("BEDROCK_SERVER_MANAGER_PORT")
    logger.info(f"Starting web app on port {port}")
    # Run with Flask's built-in server (for development) or waitress (for production)
    app.run(debug=True, port=port)
    # serve(app, listen=f"*:{port}")


if __name__ == "__main__":
    main()
