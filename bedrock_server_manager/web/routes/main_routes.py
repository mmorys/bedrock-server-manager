# bedrock-server-manager/bedrock_server_manager/web/routes/main_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import os
import logging
from bedrock_server_manager import handlers
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
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get status for all servers using the handler
    logger.debug("Calling get_all_servers_status_handler...")
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)

    if status_response["status"] == "error":
        # Flash an error message if the handler failed
        error_msg = f"Error retrieving server statuses: {status_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
        servers = []  # Provide an empty list to prevent template errors
    else:
        servers = status_response.get("servers", [])
        logger.debug(f"Successfully retrieved status for {len(servers)} servers.")

    # Render the main index template
    logger.debug(f"Rendering index.html with {len(servers)} servers.")
    return render_template("index.html", servers=servers, app_name=app_name)


# --- Route: Manage Servers Page ---
@main_bp.route("/manage_servers")
@login_required
def manage_server_route():
    """Renders the page for managing existing servers (e.g., delete)."""
    logger.info("Route '/manage_servers' accessed - Rendering server management page.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get status for all servers to list them
    logger.debug("Calling get_all_servers_status_handler...")
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)

    if status_response["status"] == "error":
        # Flash an error message if the handler failed
        error_msg = f"Error retrieving server statuses for management page: {status_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
        servers = []  # Provide an empty list
    else:
        servers = status_response.get("servers", [])
        logger.debug(
            f"Successfully retrieved status for {len(servers)} servers for management page."
        )

    # Render the manage servers template
    logger.debug(f"Rendering manage_servers.html with {len(servers)} servers.")
    return render_template("manage_servers.html", servers=servers, app_name=app_name)


# --- Route: Advanced Menu Page ---
@main_bp.route("/advanced_menu")
@login_required
def advanced_menu_route():
    """Renders the advanced menu page listing servers for configuration."""
    logger.info("Route '/advanced_menu' accessed - Rendering advanced menu page.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get status for all servers to populate the dropdown/list
    logger.debug("Calling get_all_servers_status_handler...")
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)

    if status_response["status"] == "error":
        # Flash an error message if the handler failed
        error_msg = f"Error retrieving server statuses for advanced menu: {status_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
        servers = []  # Provide an empty list
    else:
        servers = status_response.get("servers", [])
        logger.debug(
            f"Successfully retrieved status for {len(servers)} servers for advanced menu."
        )

    # Render the advanced menu template
    logger.debug(f"Rendering advanced_menu.html with {len(servers)} servers.")
    return render_template("advanced_menu.html", servers=servers, app_name=app_name)


# --- Route: Install Content Menu Page ---
@main_bp.route("/install_content")
@login_required
def install_content_menu_route():
    """Renders the menu page for installing content (worlds, addons)."""
    logger.info(
        "Route '/install_content' accessed - Rendering content installation menu."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get server list for the dropdown selector
    logger.debug("Calling get_all_servers_status_handler for server list...")
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)

    if status_response["status"] == "error":
        error_msg = f"Error retrieving server list for content installation menu: {status_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
        servers = []  # Provide empty list
    else:
        servers = status_response.get("servers", [])
        logger.debug(f"Successfully retrieved {len(servers)} servers for content menu.")

    # Render the content installation menu template
    logger.debug(f"Rendering install_content.html with {len(servers)} servers.")
    return render_template("install_content.html", servers=servers, app_name=app_name)


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
