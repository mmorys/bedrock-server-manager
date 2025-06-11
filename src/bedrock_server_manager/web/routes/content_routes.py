# bedrock_server_manager/web/routes/content_routes.py
"""
Flask Blueprint for handling web routes and API endpoints related to
server content management (Worlds, Addons).
"""

import os
import logging
from typing import Tuple, Dict, Any, List

# Third-party imports
from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    jsonify,
    Response,
    redirect,
    url_for,
)

# Local imports
from bedrock_server_manager.api import world as world_api
from bedrock_server_manager.api import addon as addon_api
from bedrock_server_manager.api import application as api_application
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.web.routes.auth_routes import login_required, csrf
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    UserInputError,
)

logger = logging.getLogger(__name__)

# Blueprint for content management routes
content_bp = Blueprint(
    "content_routes",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)


# -- List content files --


@content_bp.route("/api/content/worlds", methods=["GET"])
@csrf.exempt
@auth_required
def list_worlds_route() -> Tuple[Response, int]:
    """API endpoint to list available world content files."""
    logger.info("API Route: Request to list world content files.")
    try:
        api_result = api_application.list_available_worlds_api()
        if api_result.get("status") == "success":
            full_paths = api_result.get("files", [])
            basenames = [os.path.basename(p) for p in full_paths]
            return jsonify({"status": "success", "files": basenames}), 200
        else:
            logger.warning(
                f"API Route: Error listing worlds: {api_result.get('message')}"
            )
            return jsonify(api_result), 500
    except Exception as e:
        logger.error(
            f"API Route: Unexpected critical error listing worlds: {e}", exc_info=True
        )
        return (
            jsonify(
                {"status": "error", "message": "A critical server error occurred."}
            ),
            500,
        )


@content_bp.route("/api/content/addons", methods=["GET"])
@csrf.exempt
@auth_required
def list_addons_route() -> Tuple[Response, int]:
    """API endpoint to list available addon content files."""
    logger.info("API Route: Request to list addon content files.")
    try:
        api_result = api_application.list_available_addons_api()
        if api_result.get("status") == "success":
            full_paths = api_result.get("files", [])
            basenames = [os.path.basename(p) for p in full_paths]
            return jsonify({"status": "success", "files": basenames}), 200
        else:
            logger.warning(
                f"API Route: Error listing addons: {api_result.get('message')}"
            )
            return jsonify(api_result), 500
    except Exception as e:
        logger.error(
            f"API Route: Unexpected critical error listing addons: {e}", exc_info=True
        )
        return (
            jsonify(
                {"status": "error", "message": "A critical server error occurred."}
            ),
            500,
        )


# --- Route: Install World Selection Page ---
@content_bp.route("/server/<string:server_name>/install_world")
@login_required
def install_world_route(server_name: str) -> Response:
    """Renders the page allowing users to select a world for installation."""
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed world install selection page for server '{server_name}'."
    )

    list_result = api_application.list_available_worlds_api()
    world_files: List[str] = []
    if list_result.get("status") == "error":
        flash(
            f"Error listing world files: {list_result.get('message', 'Unknown error')}",
            "error",
        )
    else:
        full_paths = list_result.get("files", [])
        world_files = [os.path.basename(p) for p in full_paths]

    return render_template(
        "select_world.html",
        server_name=server_name,
        world_files=world_files,
    )


# --- Route: Install World API Endpoint ---
@content_bp.route("/api/server/<string:server_name>/world/install", methods=["POST"])
@csrf.exempt
@auth_required
def install_world_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to install a user-selected world to a server."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: World install requested for '{server_name}' by user '{identity}'."
    )

    data = request.get_json()
    if not data or "filename" not in data:
        return (
            jsonify(
                status="error",
                message="Invalid or missing JSON body with 'filename' key.",
            ),
            400,
        )

    selected_filename = data["filename"]
    result: Dict[str, Any]
    status_code: int

    try:
        content_base_dir = os.path.join(settings.get("CONTENT_DIR"), "worlds")
        full_world_file_path = os.path.normpath(
            os.path.join(content_base_dir, selected_filename)
        )

        # Security: Critical check to prevent directory traversal
        if not os.path.abspath(full_world_file_path).startswith(
            os.path.abspath(content_base_dir)
        ):
            return jsonify(status="error", message="Invalid file path."), 400

        if not os.path.isfile(full_world_file_path):
            return (
                jsonify(
                    status="error",
                    message=f"World file '{selected_filename}' not found.",
                ),
                404,
            )

        # Call the API function
        result = world_api.import_world(server_name, full_world_file_path)

        if result.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Install World '{server_name}': Succeeded. Message: {result.get('message')}"
            )
        else:
            status_code = 500  # API handled an operational error
            logger.error(
                f"API Install World '{server_name}': Failed. Message: {result.get('message')}"
            )

    except BSMError as e:
        status_code = 404 if isinstance(e, InvalidServerNameError) else 500
        result = {"status": "error", "message": str(e)}
        logger.error(
            f"API Install World '{server_name}': Config or server name error: {e}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"API Install World '{server_name}': Unexpected error in route: {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": "An unexpected server error occurred."}
        status_code = 500

    return jsonify(result), status_code


# --- Route: Export World API  ---
@content_bp.route("/api/server/<string:server_name>/world/export", methods=["POST"])
@csrf.exempt
@auth_required
def export_world_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to export the current world to the content directory."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: World export requested for '{server_name}' by user '{identity}'."
    )

    result: Dict[str, Any]
    status_code: int

    try:

        # Call the API function with the explicit export directory
        result = world_api.export_world(server_name)

        if result.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Export World '{server_name}': Succeeded. Message: {result.get('message')}"
            )
        else:
            status_code = 500
            logger.error(
                f"API Export World '{server_name}': Failed. Message: {result.get('message')}"
            )

    except BSMError as e:
        status_code = 404 if isinstance(e, InvalidServerNameError) else 500
        result = {"status": "error", "message": str(e)}
        logger.error(
            f"API Export World '{server_name}': Config or server name error: {e}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"API Export World '{server_name}': Unexpected error in route: {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": "An unexpected server error occurred."}
        status_code = 500

    return jsonify(result), status_code


# --- Route: Reset World API ---
@content_bp.route("/api/server/<string:server_name>/world/reset", methods=["DELETE"])
@csrf.exempt
@auth_required
def reset_world_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to delete the current world of a specified server."""
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: World reset requested for '{server_name}' by user '{identity}'.")

    result: Dict[str, Any]
    status_code: int

    try:
        result = world_api.reset_world(server_name)

        if result.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Reset World '{server_name}': Succeeded. Message: {result.get('message')}"
            )
        else:
            status_code = 500
            logger.error(
                f"API Reset World '{server_name}': Failed. Message: {result.get('message')}"
            )

    except BSMError as e:
        logger.warning(f"API Reset World '{server_name}': Application error: {e}")
        status_code = 404 if isinstance(e, InvalidServerNameError) else 500
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API Reset World '{server_name}': Unexpected error in route: {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": "An unexpected server error occurred."}
        status_code = 500

    return jsonify(result), status_code


# --- Route: Install Addon Selection Page ---
@content_bp.route("/server/<string:server_name>/install_addon")
@login_required
def install_addon_route(server_name: str) -> Response:
    """Renders the page for selecting an addon to install."""
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed addon install selection page for server '{server_name}'."
    )

    list_result = api_application.list_available_addons_api()
    addon_files: List[str] = []
    if list_result.get("status") == "error":
        flash(
            f"Error listing addon files: {list_result.get('message', 'Unknown error')}",
            "error",
        )
    else:
        full_paths = list_result.get("files", [])
        addon_files = [os.path.basename(p) for p in full_paths]

    return render_template(
        "select_addon.html",
        server_name=server_name,
        addon_files=addon_files,
    )


# --- Route: Install Addon API Endpoint ---
@content_bp.route("/api/server/<string:server_name>/addon/install", methods=["POST"])
@csrf.exempt
@auth_required
def install_addon_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to install a user-selected addon to a server."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Addon install requested for '{server_name}' by user '{identity}'."
    )

    data = request.get_json()
    if not data or "filename" not in data:
        return (
            jsonify(
                status="error",
                message="Invalid or missing JSON body with 'filename' key.",
            ),
            400,
        )

    selected_filename = data["filename"]
    result: Dict[str, Any]
    status_code: int

    try:
        content_base_dir = os.path.join(settings.get("CONTENT_DIR"), "addons")
        full_addon_file_path = os.path.normpath(
            os.path.join(content_base_dir, selected_filename)
        )

        # Security: Critical check to prevent directory traversal
        if not os.path.abspath(full_addon_file_path).startswith(
            os.path.abspath(content_base_dir)
        ):
            return jsonify(status="error", message="Invalid file path."), 400

        if not os.path.isfile(full_addon_file_path):
            return (
                jsonify(
                    status="error",
                    message=f"Addon file '{selected_filename}' not found.",
                ),
                404,
            )

        # Call the API function
        result = addon_api.import_addon(server_name, full_addon_file_path)

        if result.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Install Addon '{server_name}': Succeeded. Message: {result.get('message')}"
            )
        else:
            status_code = 500  # API handled an operational error
            logger.error(
                f"API Install Addon '{server_name}': Failed. Message: {result.get('message')}"
            )

    except BSMError as e:
        status_code = 404 if isinstance(e, InvalidServerNameError) else 500
        result = {"status": "error", "message": str(e)}
        logger.error(
            f"API Install Addon '{server_name}': Config or server name error: {e}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"API Install Addon '{server_name}': Unexpected error in route: {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": "An unexpected server error occurred."}
        status_code = 500

    return jsonify(result), status_code
