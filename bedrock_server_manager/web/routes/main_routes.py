# bedrock-server-manager/bedrock_server_manager/web/routes/main_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, current_app
import os
import platform
import logging
from bedrock_server_manager.api import utils, world
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config.settings import app_name, settings
from bedrock_server_manager.web.routes.auth_routes import login_required

# Initialize logger for this module
logger = logging.getLogger("bedrock_server_manager")

# Create Blueprint for main UI routes
main_bp = Blueprint("main_routes", __name__)


# --- Route: Main Dashboard ---
@main_bp.route("/server_icon/<path:server_name>/world_icon.jpeg")
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


@main_bp.route("/")
@login_required
def index():
    """Renders the main dashboard page displaying the status of all servers."""
    logger.info("Route '/' accessed - Rendering main dashboard.")
    base_dir = utils.get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    logger.debug("Calling get_all_servers_status...")
    status_response = utils.get_all_servers_status(base_dir=base_dir)

    processed_servers = []  # List to hold final server data with icon URL

    if status_response["status"] == "error":
        error_msg = f"Error retrieving server statuses: {status_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
        # servers = [] # Keep this empty if needed downstream
    else:
        original_servers = status_response.get("servers", [])
        logger.debug(
            f"Successfully retrieved status for {len(original_servers)} servers. Processing for icons..."
        )

        # --- Loop to add icon URL ---
        for server_info in original_servers:
            server_name = server_info.get("name")
            icon_url = None  # Default to no specific icon

            if server_name and base_dir:  # Need base_dir to check path
                try:
                    # Get world name for this server
                    world_name_response = world.get_world_name(
                        server_name, base_dir=base_dir
                    )

                    if world_name_response["status"] == "success":
                        world_name = world_name_response["world_name"]
                        # Construct the FULL Filesystem path to check existence
                        icon_fs_path = os.path.join(
                            base_dir, server_name, "worlds", world_name, "world_icon.jpeg"
                        )

                        if os.path.exists(icon_fs_path):
                            # If it exists, generate the URL using our new serving route
                            icon_url = url_for(
                                "main_routes.serve_world_icon", server_name=server_name
                            )
                            logger.debug(
                                f"Icon found for {server_name}. URL: {icon_url}"
                            )
                        else:
                            logger.debug(f"Icon file not found at path: {icon_fs_path}")
                    else:
                        logger.warning(
                            f"Could not get world name for {server_name} to check icon: {world_name_response.get('message')}"
                        )

                except Exception as e:
                    logger.exception(
                        f"Error processing icon for server {server_name}: {e}"
                    )

            server_info["icon_url"] = icon_url  # Add the URL (or None) to the dict
            processed_servers.append(server_info)  # Add modified dict to new list
        # --- End Loop ---

    # Render the template using the processed list
    logger.debug(
        f"Rendering index.html with {len(processed_servers)} processed servers."
    )
    return render_template("index.html", servers=processed_servers, app_name=app_name)


# --- Route: Server Monitor Page ---
@main_bp.route("/server/<server_name>/monitor")
@login_required
def monitor_server_route(server_name):
    """Displays the server monitoring page (e.g., for console output, status)."""
    logger.info(
        f"Route '/server/{server_name}/monitor' accessed - Rendering monitoring page."
    )
    # The monitor page likely uses JavaScript to poll the status API,
    # so this route just needs to render the template.
    return render_template("monitor.html", server_name=server_name, app_name=app_name)


# --- API Route: Configure Service ---
@main_bp.route("/server/<server_name>/task_scheduler")
@login_required
def task_scheduler_route(server_name):
    # Determine OS and process accordingly
    current_os = platform.system()

    if current_os == "Linux":
        return redirect(
            url_for(
                "task_scheduler_routes.schedule_tasks_route", server_name=server_name
            )
        )
    elif current_os == "Windows":
        return redirect(
            url_for(
                "schedule_tasks_routes.schedule_tasks_windows_route", server_name=server_name
            )
        )
    else:
        return redirect(
            url_for(
                "main_routes.index", server_name=server_name
            )  # Use new blueprint name
        )
    