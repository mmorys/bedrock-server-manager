# bedrock_server_manager/web/routes/main_routes.py
"""
Flask Blueprint for the main user interface routes of the application,
primarily the server dashboard.
"""

import platform
import logging
from typing import List, Dict, Any

# Third-party imports
from flask import Blueprint, render_template, redirect, url_for, flash, Response

# Local imports
from bedrock_server_manager.api import application as api_application
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.web.routes.auth_routes import login_required
from bedrock_server_manager.web.utils.auth_decorators import get_current_identity
from bedrock_server_manager.error import BSMError

# Initialize logger
logger = logging.getLogger(__name__)

# Create Blueprint
main_bp = Blueprint(
    "main_routes", __name__, template_folder="../templates", static_folder="../static"
)


# --- Route: Main Dashboard ---
@main_bp.route("/")
@login_required  # Requires web session
def index() -> Response:
    """
    Renders the main dashboard page.

    Displays a list of all detected servers, their status, version, and world icon (if available).
    """
    logger.info("Dashboard route '/' accessed. Rendering server list.")
    processed_servers: List[Dict[str, Any]] = []

    try:
        # API call to get status for all servers remains the same
        status_response = api_application.get_all_servers_data()

        if status_response.get("status") == "error":
            error_msg = f"Error retrieving server data: {status_response.get('message', 'Unknown error')}"
            flash(error_msg, "error")
            logger.error(error_msg)
        else:
            original_servers = status_response.get("servers", [])
            logger.info(
                f"Retrieved data for {len(original_servers)} servers. Processing for display..."
            )

            # Process each server to add icon URL if available
            for server_info in original_servers:
                server_name = server_info.get("name")
                icon_url = None

                if server_name:
                    try:
                        # Instantiate the server object
                        server = BedrockServer(server_name)

                        # Uheck for an icon
                        if server.has_world_icon():
                            icon_url = url_for(
                                "util_routes.serve_world_icon",
                                server_name=server_name,
                            )
                            logger.debug(
                                f"Icon found for server '{server_name}'. URL: {icon_url}"
                            )
                        else:
                            logger.debug(
                                f"No world icon found for server '{server_name}'."
                            )

                    except Exception as e:
                        # Catch errors instantiating or checking a single server, but don't stop the whole page
                        logger.error(
                            f"Error processing server '{server_name}' for dashboard: {e}",
                            exc_info=True,
                        )

                server_info["icon_url"] = icon_url
                processed_servers.append(server_info)

            logger.debug("Finished processing servers for dashboard display.")

    except BSMError as e:  # Catch configuration errors (e.g., BASE_DIR missing)
        flash(f"Configuration error: {e}", "danger")
        logger.critical(
            f"Configuration error preventing dashboard load: {e}", exc_info=True
        )
    except Exception as e:
        flash(
            "An unexpected error occurred while loading server information.", "danger"
        )
        logger.error("Unexpected error loading dashboard data.", exc_info=True)

    logger.debug(
        f"Rendering index.html template with {len(processed_servers)} processed server(s)."
    )
    return render_template("index.html", servers=processed_servers)


# --- Route: Redirect to OS-Specific Scheduler Page ---
@main_bp.route("/server/<string:server_name>/scheduler")
@login_required  # Requires web session
def task_scheduler_route(server_name: str) -> Response:
    """
    Redirects the user to the appropriate task scheduling page based on the host OS.
    """
    current_os = platform.system()
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed scheduler route for server '{server_name}'. OS detected: {current_os}."
    )

    if current_os == "Linux":
        return redirect(
            url_for(
                "schedule_tasks_routes.schedule_tasks_route", server_name=server_name
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
        flash(
            f"Task scheduling is not supported on this operating system ({current_os}).",
            "warning",
        )
        return redirect(url_for(".index"))
