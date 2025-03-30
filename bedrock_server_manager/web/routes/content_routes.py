# bedrock-server-manager/bedrock_server_manager/web/routes/content_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import os
import logging
from bedrock_server_manager import handlers
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config.settings import settings, app_name
from bedrock_server_manager.web.routes.auth_routes import login_required

# Initialize logger for this module
logger = logging.getLogger("bedrock_server_manager")

# Create Blueprint for content installation routes
content_bp = Blueprint("content_routes", __name__)


# --- Route: Install World Selection Page ---
@content_bp.route("/server/<server_name>/install_world")
@login_required
def install_world_route(server_name):
    """Renders the page for selecting a world (.mcworld) file to install."""
    logger.info(
        f"Route '/server/{server_name}/install_world' accessed - Rendering world selection page."
    )
    # Define the expected content directory for worlds
    content_dir = os.path.join(settings.get("CONTENT_DIR"), "worlds")
    logger.debug(f"World content directory: {content_dir}")

    # List available .mcworld files using the handler
    logger.debug("Calling list_content_files_handler for .mcworld files...")
    result = handlers.list_content_files_handler(
        content_dir, ["mcworld"]
    )  # Specify extension
    logger.debug(f"List content files handler result: {result}")

    world_files = []  # Default empty list
    if result["status"] == "error":
        error_msg = f"Error listing available world files: {result.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
    else:
        world_files = result.get("files", [])
        logger.debug(f"Found {len(world_files)} world files: {world_files}")

    # Render the world selection template
    logger.debug(f"Rendering select_world.html for '{server_name}'.")
    return render_template(
        "select_world.html",
        server_name=server_name,
        world_files=world_files,  # Pass the list of filenames
        app_name=app_name,
    )


# --- API Route: Install World ---
@content_bp.route("/api/server/<server_name>/world/install", methods=["POST"])
@login_required
def install_world_api_route(server_name):
    """API endpoint to install a selected world from an .mcworld file."""
    logger.info(
        f"API POST request received to install world for server: '{server_name}'."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for world install: {data}")

    # Validate JSON body
    if not data or not isinstance(data, dict):
        logger.warning(
            f"API Install World request for '{server_name}': Empty or invalid JSON body received."
        )
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract filename from JSON
    selected_file = data.get(
        "filename"
    )  # Expecting the full path or identifier from the selection page
    logger.debug(f"Selected world file from JSON: '{selected_file}'")

    # Validate filename presence
    if (
        not selected_file
        or not isinstance(selected_file, str)
        or not selected_file.strip()
    ):
        logger.warning(
            f"API Install World request for '{server_name}': Missing or invalid 'filename' in JSON body."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Missing or invalid 'filename' in request body.",
                }
            ),
            400,
        )

    selected_file = selected_file.strip()  # Use trimmed filename/path

    logger.info(
        f"API request validated to install world '{selected_file}' for server: '{server_name}'"
    )

    # Call the handler to extract/install the world
    logger.debug(
        f"Calling extract_world_handler for '{server_name}', file: '{selected_file}'..."
    )
    result = handlers.extract_world_handler(server_name, selected_file, base_dir)
    logger.debug(f"Extract world handler response: {result}")

    # Determine status code
    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        success_message = f"World '{os.path.basename(selected_file)}' installed successfully for server '{server_name}'."
        logger.info(f"API: {success_message}")
        if result and "message" not in result:
            result["message"] = success_message
    else:
        error_message = (
            result.get("message", "Unknown world extraction error")
            if result
            else "World extraction handler failed unexpectedly"
        )
        logger.error(
            f"API Install World failed for '{server_name}' (file: '{selected_file}'): {error_message}"
        )
        # Ensure result object exists and has error status/message
        if not result:
            result = {}
        result["status"] = "error"
        if "message" not in result:
            result["message"] = (
                f"Failed to install world '{os.path.basename(selected_file)}' for '{server_name}'."
            )

    # Return JSON response
    logger.debug(
        f"Returning JSON response for install world API '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code


# --- Route: Install Addon Selection Page ---
@content_bp.route("/server/<server_name>/install_addon")
@login_required
def install_addon_route(server_name):
    """Renders the page for selecting an addon (.mcaddon, .mcpack) file to install."""
    logger.info(
        f"Route '/server/{server_name}/install_addon' accessed - Rendering addon selection page."
    )
    # Define the expected content directory for addons
    content_dir = os.path.join(settings.get("CONTENT_DIR"), "addons")
    logger.debug(f"Addon content directory: {content_dir}")

    # List available addon files using the handler
    allowed_extensions = ["mcaddon", "mcpack"]
    logger.debug(
        f"Calling list_content_files_handler for extensions: {allowed_extensions}..."
    )
    result = handlers.list_content_files_handler(content_dir, allowed_extensions)
    logger.debug(f"List content files handler result: {result}")

    addon_files = []  # Default empty list
    if result["status"] == "error":
        error_msg = f"Error listing available addon files: {result.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
    else:
        addon_files = result.get("files", [])
        logger.debug(f"Found {len(addon_files)} addon files: {addon_files}")

    # Render the addon selection template
    logger.debug(f"Rendering select_addon.html for '{server_name}'.")
    return render_template(
        "select_addon.html",
        server_name=server_name,
        addon_files=addon_files,  # Pass the list of filenames
        app_name=app_name,
    )


# --- API Route: Install Addon ---
@content_bp.route("/api/server/<server_name>/addon/install", methods=["POST"])
@login_required
def install_addon_api_route(server_name):
    """API endpoint to install a selected addon (.mcaddon, .mcpack)."""
    logger.info(
        f"API POST request received to install addon for server: '{server_name}'."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for addon install: {data}")

    # Validate JSON body
    if not data or not isinstance(data, dict):
        logger.warning(
            f"API Install Addon request for '{server_name}': Empty or invalid JSON body received."
        )
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract filename from JSON
    selected_file = data.get("filename")  # Expecting the full path or identifier
    logger.debug(f"Selected addon file from JSON: '{selected_file}'")

    # Validate filename presence
    if (
        not selected_file
        or not isinstance(selected_file, str)
        or not selected_file.strip()
    ):
        logger.warning(
            f"API Install Addon request for '{server_name}': Missing or invalid 'filename' in JSON body."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Missing or invalid 'filename' in request body.",
                }
            ),
            400,
        )

    selected_file = selected_file.strip()  # Use trimmed filename/path

    logger.info(
        f"API request validated to install addon '{selected_file}' for server: '{server_name}'"
    )

    # Call the handler to install the addon
    logger.debug(
        f"Calling install_addon_handler for '{server_name}', file: '{selected_file}'..."
    )
    result = handlers.install_addon_handler(server_name, selected_file, base_dir)
    logger.debug(f"Install addon handler response: {result}")

    # Determine status code
    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        success_message = f"Addon '{os.path.basename(selected_file)}' installed successfully for server '{server_name}'."
        logger.info(f"API: {success_message}")
        if result and "message" not in result:
            result["message"] = success_message
    else:
        error_message = (
            result.get("message", "Unknown addon installation error")
            if result
            else "Addon installation handler failed unexpectedly"
        )
        logger.error(
            f"API Install Addon failed for '{server_name}' (file: '{selected_file}'): {error_message}"
        )
        # Ensure result object exists and has error status/message
        if not result:
            result = {}
        result["status"] = "error"
        if "message" not in result:
            result["message"] = (
                f"Failed to install addon '{os.path.basename(selected_file)}' for '{server_name}'."
            )

    # Return JSON response
    logger.debug(
        f"Returning JSON response for install addon API '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code
