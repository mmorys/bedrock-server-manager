# bedrock-server-manager/bedrock_server_manager/web/routes/main_routes.py
"""
Flask Blueprint for the main user interface routes of the application,
primarily the server dashboard.
"""

import os
import platform
import logging
from typing import List, Dict, Any, Optional

# Third-party imports
from flask import Blueprint, render_template, redirect, url_for, flash, Response

# Local imports
from bedrock_server_manager.api import utils as api_utils
from bedrock_server_manager.api import world as api_world
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.web.routes.auth_routes import login_required
from bedrock_server_manager.web.utils.auth_decorators import get_current_identity
from bedrock_server_manager.error import FileOperationError

# Initialize logger
logger = logging.getLogger("bedrock_server_manager")

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
    processed_servers: List[Dict[str, Any]] = []  # Ensure type consistency
    base_dir: Optional[str] = None

    try:
        base_dir = get_base_dir()  # May raise FileOperationError
        logger.debug(f"Using base directory: {base_dir}")

        # API call to get status for all servers
        logger.debug("Calling API: api_utils.get_all_servers_status")
        status_response = api_utils.get_all_servers_status(
            base_dir=base_dir
        )  # Returns dict

        if status_response.get("status") == "error":
            error_msg = f"Error retrieving server statuses: {status_response.get('message', 'Unknown error')}"
            flash(error_msg, "error")
            logger.error(error_msg)
            # Render template with empty list on error
        else:
            original_servers = status_response.get("servers", [])
            logger.info(
                f"Retrieved status for {len(original_servers)} servers. Fetching icons..."
            )

            # Process each server to add icon URL if available
            for server_info in original_servers:
                server_name = server_info.get("name")
                icon_url: Optional[str] = None  # Default icon to None

                if server_name and base_dir:  # Need base_dir to construct paths
                    try:
                        # API call to get world name for this server
                        # logger.debug(f"Calling API: api_world.get_world_name for '{server_name}'")
                        world_name_response = api_world.get_world_name(
                            server_name, base_dir=base_dir
                        )

                        if world_name_response.get("status") == "success":
                            world_name = world_name_response.get("world_name")
                            if world_name:
                                # Construct path to potential icon file
                                icon_fs_path = os.path.join(
                                    base_dir,
                                    server_name,
                                    "worlds",
                                    world_name,
                                    "world_icon.jpeg",
                                )
                                if os.path.isfile(icon_fs_path):  # Check if it's a file
                                    # Generate URL using the util_routes blueprint endpoint
                                    icon_url = url_for(
                                        "util_routes.serve_world_icon",
                                        server_name=server_name,
                                    )
                                    logger.debug(
                                        f"Icon found for server '{server_name}'. URL: {icon_url}"
                                    )
                                else:
                                    logger.debug(
                                        f"World icon file not found for server '{server_name}' at: {icon_fs_path}"
                                    )
                            else:
                                logger.debug(
                                    f"World name for server '{server_name}' is empty. Cannot check for icon."
                                )
                        else:
                            # Log warning if getting world name failed for this server
                            logger.warning(
                                f"Could not get world name for server '{server_name}' to check icon: {world_name_response.get('message')}"
                            )

                    except Exception as e:
                        # Catch unexpected errors during icon processing for *this* server, log and continue
                        logger.error(
                            f"Error processing icon check for server '{server_name}': {e}",
                            exc_info=True,
                        )
                        # icon_url remains None

                server_info["icon_url"] = (
                    icon_url  # Add icon_url key (will be None if not found)
                )
                processed_servers.append(server_info)

            logger.debug(f"Finished processing servers for dashboard display.")

    except FileOperationError as e:  # Catch error from get_base_dir
        flash(f"Configuration error: Cannot determine base directory. {e}", "danger")
        logger.critical(
            f"Configuration error preventing dashboard load: {e}", exc_info=True
        )
        # Render template with empty list
    except Exception as e:
        flash(
            "An unexpected error occurred while loading server information.", "danger"
        )
        logger.error("Unexpected error loading dashboard data.", exc_info=True)
        # Render template with empty list

    # Render the main dashboard template, passing the processed server list
    # Global variables like app_name are injected by context processor
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

    Args:
        server_name: The name of the server passed in the URL.

    Returns:
        A Flask redirect Response to either the Linux or Windows scheduler route.
        Redirects to the main index if the OS is not recognized.
    """
    current_os = platform.system()
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed scheduler route for server '{server_name}'. OS detected: {current_os}."
    )

    # Note: Server existence validation happens globally via before_request handler

    if current_os == "Linux":
        # Redirect to the Linux cron job scheduling route
        linux_scheduler_url = url_for(
            "schedule_tasks_routes.schedule_tasks_route", server_name=server_name
        )
        logger.debug(f"Redirecting to Linux scheduler route: {linux_scheduler_url}")
        return redirect(linux_scheduler_url)
    elif current_os == "Windows":
        # Redirect to the Windows Task Scheduler route
        windows_scheduler_url = url_for(
            "schedule_tasks_routes.schedule_tasks_windows_route",
            server_name=server_name,
        )
        logger.debug(f"Redirecting to Windows scheduler route: {windows_scheduler_url}")
        return redirect(windows_scheduler_url)
    else:
        # Fallback for unsupported OS
        logger.warning(
            f"Task scheduling not supported on OS '{current_os}'. Redirecting to dashboard."
        )
        flash(
            f"Task scheduling is not supported on this operating system ({current_os}).",
            "warning",
        )
        index_url = url_for(".index")  # Relative within blueprint
        return redirect(index_url)
