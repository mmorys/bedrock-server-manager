# bedrock-server-manager/bedrock_server_manager/web/routes/util_routes.py
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
from bedrock_server_manager.api import utils as api_utils
from bedrock_server_manager.api import world as api_world
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.web.routes.auth_routes import login_required
from bedrock_server_manager.web.utils.auth_decorators import get_current_identity
from bedrock_server_manager.error import FileOperationError

# Initialize logger
logger = logging.getLogger("bedrock_server_manager")

# Create Blueprint
util_bp = Blueprint(
    "util_routes", __name__, template_folder="../templates", static_folder="../static"
)


# --- Route: Serve World Icon ---
# Ensure the parameter type is string, path might be too broad if slashes aren't expected in server_name
@util_bp.route("/server_icon/<string:server_name>/world_icon.jpeg")
@login_required  # Requires web session (or consider if icons should be public/require JWT)
def serve_world_icon(server_name: str) -> Response:
    """
    Serves the `world_icon.jpeg` file for a specific server's world directory.

    If the icon is not found or the world name cannot be determined, serves a
    default fallback icon (`favicon.ico`).

    Args:
        server_name: The name of the server whose icon should be served.

    Returns:
        A Flask Response object containing the image data or a 404/500 error.
    """
    logger.debug(f"Request received to serve world icon for server '{server_name}'.")
    try:
        # Note: Server existence is checked by the global before_request handler

        # Determine base directory (raises FileOperationError if setting missing)
        base_dir = api_utils.get_base_dir()

        # Get the world name for this server
        # logger.debug(f"Calling API: api_world.get_world_name for '{server_name}'")
        world_name_response = api_world.get_world_name(server_name, base_dir=base_dir)

        if world_name_response.get("status") != "success":
            error_msg = world_name_response.get(
                "message", "Could not determine world name"
            )
            logger.warning(
                f"Cannot serve icon for '{server_name}': {error_msg}. Serving default."
            )
            raise FileNotFoundError(
                "World name not found, serving default."
            )  # Trigger fallback

        world_name = world_name_response.get("world_name")
        if not world_name:
            logger.warning(
                f"World name for '{server_name}' is empty. Serving default icon."
            )
            raise FileNotFoundError(
                "World name is empty, serving default."
            )  # Trigger fallback

        # Construct the absolute path to the directory containing the world icon
        world_dir_path = os.path.abspath(
            os.path.join(base_dir, server_name, "worlds", world_name)
        )
        icon_filename = "world_icon.jpeg"

        logger.debug(
            f"Attempting to serve icon for '{server_name}': Directory='{world_dir_path}', Filename='{icon_filename}'"
        )

        # Use send_from_directory for security (prevents path traversal)
        return send_from_directory(
            directory=world_dir_path,
            path=icon_filename,  # Changed from 'filename' to 'path' kwarg
            mimetype="image/jpeg",
            as_attachment=False,  # Display inline
        )

    except FileNotFoundError:
        # This catches both file not found by send_from_directory and the explicit raises above
        logger.info(
            f"World icon not found for server '{server_name}'. Serving default icon."
        )
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

    except FileOperationError as e:  # Catch config errors (e.g., BASE_DIR missing)
        logger.error(
            f"Configuration error serving world icon for '{server_name}': {e}",
            exc_info=True,
        )
        return "Server configuration error", 500
    except Exception as e:
        logger.error(
            f"Unexpected error serving world icon for '{server_name}': {e}",
            exc_info=True,
        )
        # Consider serving default icon on unexpected errors too? Or return 500?
        return "Error serving icon", 500


# --- Route: Serve Custom Panorama ---
# No server name context needed here
@util_bp.route("/background/custom_panorama.jpeg")
def serve_custom_panorama() -> Response:
    """
    Serves a custom `panorama.jpeg` background image if it exists in the config directory.

    If the custom file is not found, serves a default panorama image from the static folder.

    Returns:
        A Flask Response object containing the image data or a 404/500 error.
    """
    logger.debug("Request received to serve custom panorama background.")
    try:
        # Use the potentially private attribute for now, assuming it's reliable
        config_dir = getattr(settings, "_config_dir", None)
        if not config_dir or not os.path.isdir(config_dir):
            # Config dir doesn't exist or isn't set, definitely use default
            logger.warning(
                "Application config directory not found or not set. Serving default panorama."
            )
            raise FileNotFoundError("Config directory not found.")  # Trigger fallback

        config_dir_abs = os.path.abspath(config_dir)
        filename = "panorama.jpeg"
        custom_path_abs = os.path.join(config_dir_abs, filename)

        logger.debug(f"Attempting to serve custom panorama from: {custom_path_abs}")

        if not os.path.isfile(custom_path_abs):
            logger.info(
                f"Custom panorama not found at '{custom_path_abs}'. Serving default."
            )
            raise FileNotFoundError("Custom panorama not found.")  # Trigger fallback

        # Serve the custom panorama from the config directory
        return send_from_directory(
            directory=config_dir_abs,
            path=filename,
            mimetype="image/jpeg",
            as_attachment=False,
        )

    except FileNotFoundError:
        # Serve the default panorama from the static folder
        try:
            default_panorama_dir = os.path.join(current_app.static_folder, "image")
            default_panorama_file = (
                "panorama.jpeg"  # Assuming default is also named this
            )
            logger.debug(
                f"Serving default panorama from: {os.path.join(default_panorama_dir, default_panorama_file)}"
            )
            return send_from_directory(
                directory=default_panorama_dir,
                path=default_panorama_file,
                mimetype="image/jpeg",
            )
        except Exception as fallback_err:
            logger.error(
                f"Failed to serve default panorama image: {fallback_err}", exc_info=True
            )
            return "Default panorama not found", 404

    except Exception as e:
        # Catch unexpected errors during file access/serving
        logger.error(f"Unexpected error serving custom panorama: {e}", exc_info=True)
        # You might want to attempt serving the default here as well
        return "Error serving panorama image", 500


# --- Route: Server Monitor Page ---
@util_bp.route("/server/<string:server_name>/monitor")
@login_required  # Requires web session
def monitor_server_route(server_name: str) -> Response:
    """
    Renders the server monitoring page for a specific server.

    This page typically uses JavaScript to poll status APIs for real-time information.

    Args:
        server_name: The name of the server passed in the URL.

    Returns:
        Rendered HTML page ('monitor.html').
    """
    identity = get_current_identity() or "Unknown"
    logger.info(f"User '{identity}' accessed monitor page for server '{server_name}'.")
    # Server existence is checked by the global before_request handler

    # This route just renders the template; dynamic data is fetched via API calls from the page
    logger.debug(f"Rendering 'monitor.html' template for server '{server_name}'.")
    return render_template(
        "monitor.html",
        server_name=server_name,
        # app_name comes from context processor
    )


# --- Catch-all Route ---
@util_bp.route("/<path:unused_path>")
def catch_all(unused_path: str) -> Response:
    """
    Redirects any unmatched route within this blueprint (or potentially globally
    if registered last without a prefix) to the main dashboard page.

    Args:
        unused_path: The captured path that did not match any other route.

    Returns:
        A Flask redirect Response to the main index page.
    """
    logger.warning(
        f"Caught undefined path: '/{unused_path}'. Redirecting to dashboard."
    )
    # Redirect to the main dashboard route
    return redirect(url_for("main_routes.index"))
