# bedrock-server-manager/bedrock_server_manager/web/routes/main_routes.py
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_from_directory,
    current_app,
)
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
@main_bp.route("/")
@login_required
def index():
    """Renders the main dashboard page displaying the status of all servers."""
    logger.info("Route '/' accessed - Rendering main dashboard.")
    base_dir = utils.get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    logger.debug("Calling get_all_servers_status...")
    status_response = utils.get_all_servers_status(base_dir=base_dir)

    processed_servers = []

    if status_response["status"] == "error":
        error_msg = f"Error retrieving server statuses: {status_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
    else:
        original_servers = status_response.get("servers", [])
        logger.debug(
            f"Successfully retrieved status for {len(original_servers)} servers. Processing for icons..."
        )

        for server_info in original_servers:
            server_name = server_info.get("name")
            icon_url = None

            if server_name and base_dir:
                try:
                    world_name_response = world.get_world_name(
                        server_name, base_dir=base_dir
                    )
                    if world_name_response["status"] == "success":
                        world_name = world_name_response["world_name"]
                        icon_fs_path = os.path.join(
                            base_dir,
                            server_name,
                            "worlds",
                            world_name,
                            "world_icon.jpeg",
                        )
                        if os.path.exists(icon_fs_path):
                            icon_url = url_for(
                                "util_routes.serve_world_icon", server_name=server_name
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

            server_info["icon_url"] = icon_url
            processed_servers.append(server_info)

    logger.debug(f"Rendering index.html with {len(processed_servers)} servers.")
    # --- No need to pass panorama_url or splash_text here anymore ---
    return render_template("index.html", servers=processed_servers)


# --- Schedule Task ---
@main_bp.route("/server/<server_name>/scheduler")
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
                "schedule_tasks_routes.schedule_tasks_windows_route",
                server_name=server_name,
            )
        )
    else:
        return redirect(url_for("main_routes.index", server_name=server_name))
