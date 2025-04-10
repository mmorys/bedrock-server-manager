# bedrock-server-manager/bedrock_server_manager/web/routes/content_routes.py
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
)

# Local imports
from bedrock_server_manager.api import world as world_api
from bedrock_server_manager.api import addon as addon_api
from bedrock_server_manager.api import utils as utils_api
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config.settings import settings, app_name
from bedrock_server_manager.web.routes.auth_routes import login_required, csrf
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.error import (
    FileOperationError,
    DownloadExtractError,
    DirectoryError,
    MissingArgumentError,
    InvalidServerNameError,
    InvalidInputError,
    AddonExtractError,
    InvalidAddonPackTypeError,
)

logger = logging.getLogger("bedrock_server_manager")

# Blueprint for content management routes
content_bp = Blueprint(
    "content_routes",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)


# --- Route: Install World Selection Page ---
@content_bp.route("/server/<string:server_name>/install_world")
@login_required  # Requires web session
def install_world_route(server_name: str) -> Response:
    """
    Renders the page allowing users to select a world (.mcworld file) for installation.

    Lists available .mcworld files from the content/worlds directory.

    Args:
        server_name: The name of the server to install the world to (from URL path).

    Returns:
        Rendered HTML page 'select_world.html' with a list of available world files.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed world install selection page for server '{server_name}'."
    )

    content_dir = os.path.join(settings.get("CONTENT_DIR"), "worlds")
    logger.debug(f"World content directory: {content_dir}")

    # API call to list available .mcworld files
    list_result: Dict[str, Any] = utils_api.list_content_files(content_dir, ["mcworld"])
    logger.debug(f"List content files API result: {list_result}")

    world_files: List[str] = []
    if list_result.get("status") == "error":
        error_msg = (
            f"Error listing world files: {list_result.get('message', 'Unknown error')}"
        )
        flash(error_msg, "error")
        logger.error(
            f"Error listing world files for server '{server_name}': {error_msg}"
        )
    else:
        world_files = list_result.get("files", [])  # Safely get files list

    logger.debug(
        f"Rendering 'select_world.html' template for server '{server_name}' with {len(world_files)} files."
    )
    return render_template(
        "select_world.html",
        server_name=server_name,
        world_files=world_files,  # List of full paths to .mcworld files
        app_name=app_name,
    )


# --- API Route: Install World ---
@content_bp.route("/api/server/<string:server_name>/world/install", methods=["POST"])
@csrf.exempt  # Exempt API endpoint from CSRF protection (using JWT or session auth)
@auth_required  # Requires session OR JWT authentication
def install_world_api_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to install a user-selected world (.mcworld file) to a server.

    Expects JSON body with 'filename' key containing the path to the .mcworld file
    (relative to the 'content/worlds' directory).

    Args:
        server_name: The name of the server to install the world to (from URL path).

    JSON Request Body Example:
        {"filename": "/path/relative/to/content/worlds/MyWorld.mcworld"}

    Returns:
        JSON response indicating success or failure of the world installation:
        - 200 OK: {"status": "success", "message": "World '...' installed successfully for server '...'."}
        - 400 Bad Request: Invalid JSON, missing filename.
        - 500 Internal Server Error: World import process failed.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: World install requested for server '{server_name}' by user '{identity}'."
    )

    # --- Input Validation ---
    data = request.get_json(
        silent=True
    )  # Use silent=True to avoid automatic 400 on bad JSON
    if not data or not isinstance(data, dict):
        logger.warning(
            f"API Install World '{server_name}': Invalid/missing JSON request body."
        )
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    selected_file_path = data.get(
        "filename"
    )  # Expecting *relative* path from selection page

    if not selected_file_path or not isinstance(selected_file_path, str):
        msg = "Missing or invalid 'filename' in request body. Expected relative path to .mcworld file."
        logger.warning(f"API Install World '{server_name}': {msg}")
        return jsonify(status="error", message=msg), 400

    content_base_dir = os.path.join(
        settings.get("CONTENT_DIR"), "worlds"
    )  # Base dir for worlds
    full_world_file_path = os.path.normpath(
        os.path.join(content_base_dir, selected_file_path)
    )  # Resolve relative path
    logger.debug(
        f"API Install World '{server_name}': Attempting to install from file: {full_world_file_path}"
    )

    # Security: Ensure path is still within the allowed content directory after joining and normalization
    if not os.path.abspath(full_world_file_path).startswith(
        os.path.abspath(content_base_dir)
    ):
        msg = "Invalid filename: Filename must be within the allowed content directory."
        logger.warning(
            f"API Install World '{server_name}': {msg} Attempted path: {full_world_file_path}"
        )
        return jsonify(status="error", message=msg), 400
    if not os.path.isfile(full_world_file_path):
        msg = f"Selected world file not found: {full_world_file_path}"
        logger.warning(f"API Install World '{server_name}': {msg}")
        return jsonify(status="error", message=msg), 404

    # --- Call API Handler ---
    result: Dict[str, Any] = {}
    status_code = 500  # Default to internal server error
    try:
        base_dir = get_base_dir()  # May raise FileOperationError

        # Call the core world import API function
        logger.debug(
            f"Calling API handler: world_api.import_world for '{server_name}', file: '{full_world_file_path}'"
        )
        result = world_api.import_world(
            server_name, full_world_file_path, base_dir
        )  # API func returns dict
        logger.debug(f"API Install World '{server_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            success_msg = f"World '{os.path.basename(selected_file_path)}' installed successfully for server '{server_name}'."
            logger.info(f"API: {success_msg}")
            result["message"] = success_msg  # Enhance success message
        else:
            # Handler indicated failure
            status_code = 500
            error_msg = (
                result.get("message", "Unknown world installation error.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Install World '{server_name}' failed: {error_msg}")
            result = {"status": "error", "message": error_msg}  # Ensure error status

    except (
        FileNotFoundError,
        FileOperationError,
        DownloadExtractError,
        DirectoryError,
        MissingArgumentError,
        InvalidServerNameError,
    ) as e:
        # Catch expected, specific errors from API call chain
        logger.warning(
            f"API Install World '{server_name}': Input/File error: {e}", exc_info=True
        )
        status_code = (
            400 if isinstance(e, (MissingArgumentError, InvalidInputError)) else 500
        )  # 400 for bad client input, 500 for server-side file/config errors
        result = {"status": "error", "message": f"World installation error: {e}"}
    except Exception as e:
        # Catch any unexpected errors during API operation
        logger.error(
            f"API Install World '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {
            "status": "error",
            "message": f"Unexpected error during world installation: {e}",
        }

    return jsonify(result), status_code


# --- Route: Install Addon Selection Page ---
@content_bp.route("/server/<string:server_name>/install_addon")
@login_required  # Requires web session
def install_addon_route(server_name: str) -> Response:
    """
    Renders the page for selecting an addon (.mcaddon or .mcpack file) to install.

    Lists available addon files from the content/addons directory.

    Args:
        server_name: The name of the server to install the addon to (from URL path).

    Returns:
        Rendered HTML page 'select_addon.html' with a list of available addon files.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed addon install selection page for server '{server_name}'."
    )

    content_dir = os.path.join(settings.get("CONTENT_DIR"), "addons")
    logger.debug(f"Addon content directory: {content_dir}")

    # API call to list available addon files
    allowed_extensions = ["mcaddon", "mcpack"]
    list_result = utils_api.list_content_files(content_dir, allowed_extensions)
    logger.debug(f"List content files API result: {list_result}")

    addon_files: List[str] = []
    if list_result.get("status") == "error":
        error_msg = (
            f"Error listing addon files: {list_result.get('message', 'Unknown error')}"
        )
        flash(error_msg, "error")
        logger.error(
            f"Error listing addon files for server '{server_name}': {error_msg}"
        )
    else:
        addon_files = list_result.get("files", [])

    logger.debug(
        f"Rendering 'select_addon.html' template for server '{server_name}' with {len(addon_files)} files."
    )
    return render_template(
        "select_addon.html",
        server_name=server_name,
        addon_files=addon_files,  # List of full paths to addon files
        app_name=app_name,
    )


# --- API Route: Install Addon ---
@content_bp.route("/api/server/<string:server_name>/addon/install", methods=["POST"])
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def install_addon_api_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to install a user-selected addon (.mcaddon or .mcpack file) to a server.

    Expects JSON body with 'filename' key (relative path to addon file in content/addons).

    Args:
        server_name: The name of the server to install the addon to (from URL path).

    JSON Request Body Example:
        {"filename": "/path/relative/to/content/addons/MyAddon.mcaddon"}

    Returns:
        JSON response indicating success or failure of the addon installation:
        - 200 OK: {"status": "success", "message": "Addon '...' installed successfully for server '...'."}
        - 400 Bad Request: Invalid JSON, missing filename, etc.
        - 500 Internal Server Error: Addon installation process failed.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Addon install requested for server '{server_name}' by user '{identity}'."
    )

    # --- Input Validation ---
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        logger.warning(f"API Install Addon '{server_name}': Invalid/missing JSON body.")
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    selected_file_path = data.get(
        "filename"
    )  # Expecting *relative* path from selection page
    if not selected_file_path or not isinstance(selected_file_path, str):
        msg = "Missing or invalid 'filename' in request body. Expected relative path to .mcaddon/.mcpack file."
        logger.warning(f"API Install Addon '{server_name}': {msg}")
        return jsonify(status="error", message=msg), 400

    content_base_dir = os.path.join(
        settings.get("CONTENT_DIR"), "addons"
    )  # Base addon dir
    full_addon_file_path = os.path.normpath(
        os.path.join(content_base_dir, selected_file_path)
    )  # Secure path join
    logger.debug(
        f"API Install Addon '{server_name}': Attempting to install from file: {full_addon_file_path}"
    )

    # Security: Ensure path is still within allowed content dir
    if not os.path.abspath(full_addon_file_path).startswith(
        os.path.abspath(content_base_dir)
    ):
        msg = "Invalid filename: Filename must be within the allowed content directory."
        logger.warning(
            f"API Install Addon '{server_name}': {msg} Attempted path: {full_addon_file_path}"
        )
        return jsonify(status="error", message=msg), 400
    if not os.path.isfile(full_addon_file_path):
        msg = f"Selected addon file not found: {full_addon_file_path}"
        logger.warning(msg)
        return jsonify(status="error", message=msg), 404

    # --- Call API Handler ---
    result: Dict[str, Any] = {}
    status_code = 500
    try:
        base_dir = get_base_dir()  # May raise FileOperationError

        # Call the core addon import API function
        logger.debug(
            f"Calling API handler: addon_api.import_addon for '{server_name}', file '{full_addon_file_path}'"
        )
        result = addon_api.import_addon(
            server_name, full_addon_file_path, base_dir
        )  # API function returns dict
        logger.debug(f"API Install Addon '{server_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            success_msg = f"Addon '{os.path.basename(selected_file_path)}' installed successfully for server '{server_name}'."
            logger.info(f"API: {success_msg}")
            result["message"] = success_msg  # Enhance success message
        else:
            # Handler indicated failure
            status_code = 500
            error_msg = (
                result.get("message", "Unknown addon installation error.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(
                f"API Install Addon failed for '{server_name}' (file: '{os.path.basename(selected_file_path)}'): {error_msg}"
            )
            result = {"status": "error", "message": error_msg}  # Ensure error status

    except (
        FileNotFoundError,
        FileOperationError,
        AddonExtractError,
        DirectoryError,
        MissingArgumentError,
        InvalidAddonPackTypeError,
    ) as e:
        # Catch specific, expected errors from API call chain
        logger.warning(
            f"API Install Addon '{server_name}': Input/File error: {e}", exc_info=True
        )
        status_code = (
            400
            if isinstance(
                e, (MissingArgumentError, InvalidInputError, InvalidAddonPackTypeError)
            )
            else 500
        )  # Differentiate client vs server errors
        result = {"status": "error", "message": f"Addon installation error: {e}"}
    except Exception as e:
        # Catch unexpected errors during API operation
        logger.error(
            f"API Install Addon '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {
            "status": "error",
            "message": f"Unexpected error during addon installation: {e}",
        }

    return jsonify(result), status_code
