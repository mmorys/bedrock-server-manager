# bedrock-server-manager/bedrock_server_manager/web/routes/util_routes.py
import os
import logging
from bedrock_server_manager.api import utils, world
from bedrock_server_manager.config.settings import app_name, settings
from bedrock_server_manager.web.routes.auth_routes import login_required
from flask import (
    Blueprint,
    render_template,
    send_from_directory,
    current_app,
)

# Initialize logger for this module
logger = logging.getLogger("bedrock_server_manager")

# Create Blueprint for main UI routes
util_bp = Blueprint("util_routes", __name__)


# --- Route: Main Dashboard ---
@util_bp.route("/server_icon/<path:server_name>/world_icon.jpeg")
@login_required
def serve_world_icon(server_name):
    """Serves the world_icon.jpeg for a given server."""
    try:
        base_dir = utils.get_base_dir()  # Get configured base dir
        if not base_dir:
            logger.error("SERVERS_BASE_PATH configuration is missing.")
            return "Server configuration error", 500

        # Get the world name (level-name) for this server
        world_name_response = world.get_world_name(server_name, base_dir=base_dir)
        if world_name_response["status"] != "success":
            logger.warning(
                f"Could not get world name for {server_name} to serve icon: {world_name_response.get('message')}"
            )
            # Optionally return default icon here instead of 404 later
            # return send_from_directory(os.path.join(current_app.static_folder, 'image', 'icon'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
            raise FileNotFoundError("World name not found")  # Treat as not found

        world_name = world_name_response["world_name"]

        # Construct the absolute directory path CONTAINING the world folder
        server_directory = os.path.join(base_dir, server_name, "worlds", world_name)
        # Construct the filename path RELATIVE to the server_directory
        filename_relative = os.path.join("world_icon.jpeg")

        logger.debug(
            f"Attempting to serve icon for {server_name}: Directory='{server_directory}', Relative Filename='{filename_relative}'"
        )

        # Use send_from_directory for security. It prevents path traversal.
        # It expects the directory path and the filename path relative to that directory.
        return send_from_directory(
            server_directory,
            filename_relative,
            mimetype="image/jpeg",
            as_attachment=False,  # Serve inline, not as download
        )

    except FileNotFoundError:
        logger.warning(f"world_icon.jpeg not found for server {server_name}.")
        # Return default icon instead of 404
        try:
            logger.debug("Serving default favicon.ico as world icon.")
            # Serve favicon.ico from static/image/icon/
            return send_from_directory(
                os.path.join(current_app.static_folder, "image", "icon"),
                "favicon.ico",
                mimetype="image/vnd.microsoft.icon",
            )
        except Exception as default_e:
            logger.error(f"Error serving default icon: {default_e}")
            return "Default icon not found", 404

    except Exception as e:
        logger.exception(f"Error serving world icon for {server_name}: {e}")
        # You could try serving the default icon here too on any error
        return "Error serving icon", 500


@util_bp.route("/background/custom_panorama.jpeg")
def serve_custom_panorama():
    try:
        config_dir = settings._config_dir
        if not config_dir:
            logger.error("CONFIG_DIR setting is not defined.")
            raise FileNotFoundError("Config dir not set")

        config_dir_abs = os.path.abspath(config_dir)

        filename = "panorama.jpeg"

        logger.debug(
            f"Attempting to serve custom panorama: Directory='{config_dir_abs}', Filename='{filename}'"
        )

        if not os.path.isdir(config_dir_abs):
            logger.error(f"Custom panorama directory does not exist: {config_dir_abs}")
            raise FileNotFoundError("Panorama directory not found")

        return send_from_directory(
            config_dir_abs, filename, mimetype="image/jpeg", as_attachment=False
        )
    except FileNotFoundError as e:
        logger.warning(
            f"Custom panorama.jpeg not found or error during lookup. Error: {e}"
        )
        return send_from_directory(
            os.path.join(current_app.static_folder, "image"),
            "panorama.jpeg",
            mimetype="image/jpeg",
        )
    except Exception as e:
        logger.exception(f"Error serving custom panorama: {e}")
        return "Error serving panorama", 500


# --- Route: Server Monitor Page ---
@util_bp.route("/server/<server_name>/monitor")
@login_required
def monitor_server_route(server_name):
    """Displays the server monitoring page (e.g., for console output, status)."""
    logger.info(
        f"Route '/server/{server_name}/monitor' accessed - Rendering monitoring page."
    )
    # The monitor page likely uses JavaScript to poll the status API,
    # so this route just needs to render the template.
    return render_template("monitor.html", server_name=server_name, app_name=app_name)
