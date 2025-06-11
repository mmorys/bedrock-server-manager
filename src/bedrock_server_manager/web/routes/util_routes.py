# bedrock_server_manager/web/routes/util_routes.py
"""
Flask Blueprint for utility routes within the web application.

Includes routes for serving dynamic content like world/server icons,
custom panoramas, the server monitoring page, and a catch-all route
for undefined paths.
"""

import os
import logging

# Third-party imports
from flask import (
    Blueprint,
    render_template,
    send_from_directory,
    current_app,
    url_for,
    redirect,
    Response,
)

# Local imports
## Refactor: Import BedrockServer to use its properties directly.
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.web.routes.auth_routes import login_required
from bedrock_server_manager.web.utils.auth_decorators import get_current_identity
from bedrock_server_manager.error import BSMError, AppFileNotFoundError

# Initialize logger
logger = logging.getLogger(__name__)

# Create Blueprint
util_bp = Blueprint(
    "util_routes", __name__, template_folder="../templates", static_folder="../static"
)


# --- Route: Serve World Icon ---
## Refactor: This route is now much cleaner. It instantiates a BedrockServer object
## and uses its `world_icon_filesystem_path` property. This removes all the complex
## API calls and path joining from the route itself.
@util_bp.route("/server_icon/<string:server_name>/world_icon.jpeg")
@login_required
def serve_world_icon(server_name: str) -> Response:
    """Serves the `world_icon.jpeg` file for a specific server's world."""
    logger.debug(f"Request to serve world icon for server '{server_name}'.")
    icon_path: str | None = None

    try:
        # Instantiate the server object to access its properties
        server = BedrockServer(server_name)
        icon_path = server.world_icon_filesystem_path

        if server.has_world_icon():
            logger.debug(f"Serving world icon from path: {icon_path}")
            # Use send_from_directory for security
            return send_from_directory(
                directory=os.path.dirname(icon_path),
                path=os.path.basename(icon_path),
                mimetype="image/jpeg",
            )
        else:
            # The path was invalid or the file doesn't exist.
            # The BedrockServer object would have already logged a warning if the path was None.
            raise AppFileNotFoundError(str(icon_path), "World icon")

    except BSMError as e:
        # Catches both file not found and config errors (like BASE_DIR missing) during server instantiation.
        if not isinstance(e, AppFileNotFoundError):
            logger.error(
                f"Configuration error serving world icon for '{server_name}': {e}",
                exc_info=True,
            )
        else:
            logger.info(f"World icon for '{server_name}' not found. Serving default.")

        # Fallback to default icon
        try:
            default_icon_dir = os.path.join(current_app.static_folder, "image", "icon")
            default_icon_file = "favicon.ico"
            return send_from_directory(
                directory=default_icon_dir,
                path=default_icon_file,
                mimetype="image/vnd.microsoft.icon",
            )
        except Exception as fallback_err:
            logger.error(
                f"Failed to serve default fallback icon: {fallback_err}", exc_info=True
            )
            return "Default icon not found", 404

    except Exception as e:
        logger.error(
            f"Unexpected error serving world icon for '{server_name}': {e}",
            exc_info=True,
        )
        return "Error serving icon", 500


# --- Route: Serve Custom Panorama ---
@util_bp.route("/background/custom_panorama.jpeg")
def serve_custom_panorama() -> Response:
    """Serves a custom `panorama.jpeg` background image if it exists."""
    logger.debug("Request received to serve custom panorama background.")
    try:
        config_dir = settings.get("CONFIG_DIR")
        if not config_dir:
            raise AppFileNotFoundError("CONFIG_DIR not set in settings.", "Setting")

        # send_from_directory handles security and file existence checks
        return send_from_directory(
            directory=config_dir,
            path="panorama.jpeg",
            mimetype="image/jpeg",
        )
    except AppFileNotFoundError:
        logger.info("Custom panorama not found. Serving default.")
        # Fallback to the default panorama from the static folder
        try:
            return send_from_directory(
                directory=os.path.join(current_app.static_folder, "image"),
                path="panorama.jpeg",
                mimetype="image/jpeg",
            )
        except Exception as fallback_err:
            logger.error(
                f"Failed to serve default panorama image: {fallback_err}", exc_info=True
            )
            return "Default panorama not found", 404
    except Exception as e:
        logger.error(f"Unexpected error serving custom panorama: {e}", exc_info=True)
        return "Error serving panorama image", 500


# --- Route: Server Monitor Page ---
@util_bp.route("/server/<string:server_name>/monitor")
@login_required
def monitor_server_route(server_name: str) -> Response:
    """Renders the server monitoring page for a specific server."""
    identity = get_current_identity()
    logger.info(f"User '{identity}' accessed monitor page for server '{server_name}'.")
    return render_template("monitor.html", server_name=server_name)


# --- Catch-all Route ---
@util_bp.route("/<path:unused_path>")
def catch_all(unused_path: str) -> Response:
    """Redirects any unmatched route to the main dashboard page."""
    logger.warning(
        f"Caught undefined path: '/{unused_path}'. Redirecting to dashboard."
    )
    return redirect(url_for("main_routes.index"))
