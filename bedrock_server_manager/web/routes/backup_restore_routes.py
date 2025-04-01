# bedrock-server-manager/bedrock_server_manager/web/routes/backup_restore_routes.py
import os
import logging
from bedrock_server_manager.api import backup_restore
from bedrock_server_manager.config.settings import app_name
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.web.routes.auth_routes import login_required
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)

# Initialize logger for this module
logger = logging.getLogger("bedrock_server_manager")

# Create Blueprint for backup and restore routes
backup_restore_bp = Blueprint("backup_restore_routes", __name__)


# --- Route: Backup Menu Page ---
@backup_restore_bp.route("/server/<server_name>/backup", methods=["GET"])
@login_required
def backup_menu_route(server_name):
    """Renders the main backup menu page for a specific server."""
    logger.info(
        f"Route '/server/{server_name}/backup' accessed - Rendering backup menu."
    )
    return render_template(
        "backup_menu.html", server_name=server_name, app_name=app_name
    )


# --- Route: Backup Config Selection Page ---
@backup_restore_bp.route("/server/<server_name>/backup/config", methods=["GET"])
@login_required
def backup_config_select_route(server_name):
    """Renders the page for selecting specific config files to backup."""
    logger.info(
        f"Route '/server/{server_name}/backup/config' accessed - Rendering config backup options page."
    )
    return render_template(
        "backup_config_options.html", server_name=server_name, app_name=app_name
    )


# --- API Route: Backup Action ---
@backup_restore_bp.route("/api/server/<server_name>/backup/action", methods=["POST"])
@login_required
def backup_action_route(server_name):
    """API endpoint to trigger a server backup (world, config file, or all)."""
    logger.info(
        f"API POST request received to perform backup action for server: '{server_name}'."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for backup action: {data}")

    # Validate JSON body
    if not data or not isinstance(data, dict):
        logger.warning(
            f"API Backup request for '{server_name}': Empty or invalid JSON body received."
        )
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract parameters
    backup_type = data.get("backup_type")  # Expected: "world", "config", or "all"
    file_to_backup = data.get(
        "file_to_backup"
    )  # Optional, only used if backup_type is "config"
    logger.debug(
        f"Backup parameters: type='{backup_type}', file_to_backup='{file_to_backup}'"
    )

    # --- Input Validation ---
    valid_types = ["world", "config", "all"]
    if not backup_type or backup_type not in valid_types:
        logger.warning(
            f"API Backup request for '{server_name}': Missing or invalid 'backup_type'. Must be one of {valid_types}."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Missing or invalid 'backup_type'. Must be one of {valid_types}.",
                }
            ),
            400,
        )

    # Validate specifically for config backup type
    if backup_type == "config":
        if (
            not file_to_backup
            or not isinstance(file_to_backup, str)
            or not file_to_backup.strip()
        ):
            logger.warning(
                f"API Backup request for '{server_name}': Missing or invalid 'file_to_backup' for config backup type."
            )
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing or invalid 'file_to_backup' for config backup type.",
                    }
                ),
                400,
            )
        file_to_backup = file_to_backup.strip()  # Use trimmed filename

    logger.info(
        f"API request validated for backup action: Server='{server_name}', Type='{backup_type}', File='{file_to_backup or 'N/A'}'"
    )

    # --- Call Appropriate Handler ---
    result = None  # Store handler result
    if backup_type == "world":
        logger.debug(f"Calling backup_world_handler for '{server_name}'...")
        result = backup_restore.backup_world(server_name, base_dir)
    elif backup_type == "config":
        logger.debug(
            f"Calling backup_config_file_handler for '{server_name}', file: '{file_to_backup}'..."
        )
        result = backup_restore.backup_config_file(
            server_name, file_to_backup, base_dir
        )
    elif backup_type == "all":
        logger.debug(f"Calling backup_all_handler for '{server_name}'...")
        result = backup_restore.backup_all(server_name, base_dir)

    logger.debug(
        f"Backup handler response for '{server_name}' (type: {backup_type}): {result}"
    )

    # --- Determine Status Code and Final Response ---
    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        success_message = f"Backup type '{backup_type}' for server '{server_name}' completed successfully."
        logger.info(f"API: {success_message}")
        if result and "message" not in result:
            result["message"] = success_message
    else:
        error_message = (
            result.get("message", "Unknown backup error")
            if result
            else "Backup handler failed unexpectedly"
        )
        logger.error(
            f"API Backup failed for '{server_name}' (type: {backup_type}): {error_message}"
        )
        # Ensure result object exists and has error status/message
        if not result:
            result = {}
        result["status"] = "error"
        if "message" not in result:
            result["message"] = (
                f"Failed to perform '{backup_type}' backup for '{server_name}'."
            )

    # Return JSON result from the handler
    logger.debug(
        f"Returning JSON response for backup action API '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code


# --- Route: Restore Menu Page ---
@backup_restore_bp.route("/server/<server_name>/restore", methods=["GET"])
@login_required
def restore_menu_route(server_name):
    """Displays the main restore menu page for a specific server."""
    logger.info(
        f"Route '/server/{server_name}/restore' accessed - Rendering restore menu."
    )
    return render_template(
        "restore_menu.html", server_name=server_name, app_name=app_name
    )


# --- API Route: Restore Action ---
@backup_restore_bp.route("/api/server/<server_name>/restore/action", methods=["POST"])
@login_required
def restore_action_route(server_name):
    """API endpoint to trigger a server restoration from a specific backup file."""
    logger.info(
        f"API POST request received to perform restore action for server: '{server_name}'."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for restore action: {data}")

    # Validate JSON body
    if not data or not isinstance(data, dict):
        logger.warning(
            f"API Restore request for '{server_name}': Empty or invalid JSON body received."
        )
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract parameters
    backup_file = data.get("backup_file")  # Filename of the backup archive
    restore_type = data.get("restore_type")  # Expected: "world" or "config"
    logger.debug(
        f"Restore parameters: type='{restore_type}', backup_file='{backup_file}'"
    )

    # --- Input Validation ---
    valid_types = ["world", "config"]
    if not restore_type or restore_type not in valid_types:
        logger.warning(
            f"API Restore request for '{server_name}': Missing or invalid 'restore_type'. Must be one of {valid_types}."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Missing or invalid 'restore_type'. Must be 'world' or 'config'.",
                }
            ),
            400,
        )

    if not backup_file or not isinstance(backup_file, str) or not backup_file.strip():
        logger.warning(
            f"API Restore request for '{server_name}': Missing or invalid 'backup_file' name."
        )
        return (
            jsonify(
                {"status": "error", "message": "Missing or invalid 'backup_file' name."}
            ),
            400,
        )

    backup_file = backup_file.strip()  # Use trimmed filename

    logger.info(
        f"API request validated for restore action: Server='{server_name}', Type='{restore_type}', File='{backup_file}'"
    )

    # --- Call Appropriate Handler ---
    result = None  # Store handler result
    if restore_type == "world":
        logger.debug(
            f"Calling restore_world_handler for '{server_name}', file: '{backup_file}'..."
        )
        result = backup_restore.restore_world(server_name, backup_file, base_dir)
    elif restore_type == "config":
        # Note: Restoring a specific config file might require more complex logic
        # if the backup contains multiple files. Assuming the handler manages this.
        logger.debug(
            f"Calling restore_config_file_handler for '{server_name}', file: '{backup_file}'..."
        )
        result = backup_restore.restore_config_file(server_name, backup_file, base_dir)
    # No else needed due to prior validation

    logger.debug(
        f"Restore handler response for '{server_name}' (type: {restore_type}, file: {backup_file}): {result}"
    )

    # --- Determine Status Code and Final Response ---
    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        success_message = f"Restoration of '{backup_file}' (type: {restore_type}) for server '{server_name}' completed successfully."
        logger.info(f"API: {success_message}")
        if result and "message" not in result:
            result["message"] = success_message
    else:
        error_message = (
            result.get("message", "Unknown restore error")
            if result
            else "Restore handler failed unexpectedly"
        )
        logger.error(
            f"API Restore failed for '{server_name}' (type: {restore_type}, file: {backup_file}): {error_message}"
        )
        # Ensure result object exists and has error status/message
        if not result:
            result = {}
        result["status"] = "error"
        if "message" not in result:
            result["message"] = (
                f"Failed to restore '{backup_file}' (type: {restore_type}) for '{server_name}'."
            )

    # Return JSON result from the handler
    logger.debug(
        f"Returning JSON response for restore action API '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code


# --- Route: Select Backup for Restore Page ---
@backup_restore_bp.route("/server/<server_name>/restore/select", methods=["POST"])
@login_required
def restore_select_backup_route(server_name):
    """Displays the list of available backups for the selected type (world or config) to restore."""
    # This route expects POST data from the restore_menu.html form
    logger.info(
        f"Route '/server/{server_name}/restore/select' accessed (POST) - Listing backups for selection."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get restore type from form data
    restore_type = request.form.get("restore_type")
    logger.debug(f"Restore type selected from form: '{restore_type}'")

    # Validate restore type
    valid_types = ["world", "config"]
    if not restore_type or restore_type not in valid_types:
        error_msg = f"Invalid restore type selected: '{restore_type}'. Please select 'world' or 'config'."
        flash(error_msg, "error")
        logger.warning(
            f"Restore selection request for '{server_name}' with invalid type: {restore_type}"
        )
        # Redirect back to the initial restore menu
        return redirect(
            url_for(
                "backup_restore_routes.restore_menu_route", server_name=server_name
            )  # Use new blueprint name
        )

    logger.info(
        f"Listing available backups of type '{restore_type}' for server: '{server_name}'..."
    )

    # Call the api to list available backups of the specified type
    logger.debug(
        f"Calling list_backups_handler for '{server_name}', type: '{restore_type}'..."
    )
    list_response = backup_restore.list_backups_files(
        server_name, restore_type, base_dir
    )
    logger.debug(f"List backups handler response: {list_response}")

    # Handle errors from the listing handler
    if list_response["status"] == "error":
        error_msg = f"Error listing backups for type '{restore_type}': {list_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(
            f"Error listing backups for '{server_name}' ({restore_type}): {error_msg}"
        )
        # Redirect back to the menu on error
        return redirect(
            url_for(
                "backup_restore_routes.restore_menu_route", server_name=server_name
            )  # Use new blueprint name
        )

    # Render the selection page with the list of backups
    backups_list = list_response.get("backups", [])
    logger.debug(
        f"Rendering restore_select_backup.html with {len(backups_list)} backups."
    )
    return render_template(
        "restore_select_backup.html",
        server_name=server_name,
        restore_type=restore_type,
        backups=backups_list,  # Pass the list of backup filenames/details
        app_name=app_name,
    )


# --- API Route: Restore All ---
@backup_restore_bp.route("/api/server/<server_name>/restore/all", methods=["POST"])
@login_required
def restore_all_api_route(server_name):
    """API endpoint to trigger restoring all files (world and configs) from the latest backups."""
    logger.info(
        f"API POST request received to restore all files for server: '{server_name}'."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the restore_all handler directly
    logger.debug(f"Calling restore_all_handler for '{server_name}'...")
    result = backup_restore.restore_all(server_name, base_dir)
    logger.debug(f"Restore all handler response for '{server_name}': {result}")

    # Determine status code
    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        success_message = (
            f"Restore All operation for server '{server_name}' completed successfully."
        )
        logger.info(f"API: {success_message}")
        if result and "message" not in result:
            result["message"] = success_message
    else:
        error_message = (
            result.get("message", "Unknown restore error")
            if result
            else "Restore All handler failed unexpectedly"
        )
        logger.error(f"API Restore All failed for '{server_name}': {error_message}")
        # Ensure result object exists and has error status/message
        if not result:
            result = {}
        result["status"] = "error"
        if "message" not in result:
            result["message"] = f"Failed to restore all files for '{server_name}'."

    # Return JSON response
    logger.debug(
        f"Returning JSON response for restore all API '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code
