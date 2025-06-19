# bedrock_server_manager/web/routes/backup_restore_routes.py
"""
Flask Blueprint handling web routes and API endpoints for server backup
and restore operations.
"""

import os
import logging
from typing import Dict, Any, Tuple

# Third-party imports
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    Response,
)

# Local imports
from bedrock_server_manager.api import backup_restore as backup_restore_api
from bedrock_server_manager.config.settings import (
    settings,
)
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.web.routes.auth_routes import login_required, csrf
from bedrock_server_manager.error import (
    BSMError,
    UserInputError,
    InvalidServerNameError,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Create Blueprint
backup_restore_bp = Blueprint(
    "backup_restore_routes",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)

# --- HTML Routes ---


@backup_restore_bp.route("/server/<string:server_name>/backup", methods=["GET"])
@login_required
def backup_menu_route(server_name: str) -> Response:
    """
    Renders the main backup menu page for a specific server.

    Args:
        server_name: The name of the server passed in the URL.

    Returns:
        Rendered HTML page ('backup_menu.html').
    """
    identity = get_current_identity()  # For logging
    logger.info(f"User '{identity}' accessed backup menu for server '{server_name}'.")
    return render_template(
        "backup_menu.html",
        server_name=server_name,
    )


@backup_restore_bp.route("/server/<string:server_name>/backup/select", methods=["GET"])
@login_required
def backup_config_select_route(server_name: str) -> Response:
    """
    Renders the page for selecting specific configuration files to back up.
    """
    identity = get_current_identity()  # For logging
    logger.info(
        f"User '{identity}' accessed config backup selection page for server '{server_name}'."
    )
    return render_template(
        "backup_config_options.html",
        server_name=server_name,
    )


@backup_restore_bp.route("/server/<string:server_name>/restore", methods=["GET"])
@login_required
def restore_menu_route(server_name: str) -> Response:
    """
    Renders the main restore menu page for a specific server.
    """
    identity = get_current_identity()
    logger.info(f"User '{identity}' accessed restore menu for server '{server_name}'.")
    return render_template(
        "restore_menu.html",
        server_name=server_name,
    )


@backup_restore_bp.route(
    "/server/<string:server_name>/restore/select", methods=["POST"]
)
@login_required
def restore_select_backup_route(server_name: str) -> Response:
    """
    Handles form submission to list available backups for a user to choose from.
    """
    identity = get_current_identity()
    restore_type = request.form.get("restore_type", "").lower()
    logger.info(
        f"User '{identity}' selected restore_type '{restore_type}' for server '{server_name}'."
    )

    valid_types = ["world", "properties", "allowlist", "permissions"]
    if restore_type not in valid_types:
        flash(f"Invalid restore type '{restore_type}' selected.", "warning")
        return redirect(url_for(".restore_menu_route", server_name=server_name))

    try:
        # Call the API function directly
        api_result = backup_restore_api.list_backup_files(server_name, restore_type)

        if api_result.get("status") == "success":
            full_paths = api_result.get("backups", [])
            if not full_paths:
                flash(
                    f"No '{restore_type}' backups found for server '{server_name}'.",
                    "info",
                )
                return redirect(url_for(".restore_menu_route", server_name=server_name))

            # Pass basenames to the template for user selection
            backups_for_template = []
            for p in full_paths:
                basename = os.path.basename(p)
                backups_for_template.append(
                    {
                        "name": basename,  # For display in the table
                        "path": basename,  # For the JavaScript function
                    }
                )
            return render_template(
                "restore_select_backup.html",
                server_name=server_name,
                restore_type=restore_type,
                backups=backups_for_template,  # Template will use these basenames
            )
        else:
            # Handle error reported by the API function
            error_msg = api_result.get("message", "Unknown error listing backups.")
            logger.error(f"Error listing backups for '{server_name}': {error_msg}")
            flash(f"Error listing backups: {error_msg}", "error")
            return redirect(url_for(".restore_menu_route", server_name=server_name))

    except Exception as e:
        logger.error(
            f"Unexpected error listing backups for '{server_name}': {e}", exc_info=True
        )
        flash("An unexpected error occurred while listing backups.", "error")
        return redirect(url_for(".restore_menu_route", server_name=server_name))


# ------

# --- API Routes ---


@backup_restore_bp.route(
    "/api/server/<string:server_name>/backups/prune", methods=["POST"]
)
@csrf.exempt
@auth_required
def prune_backups_api_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to prune old backups (world, configs) for a specific server.
    The number of backups to keep is determined by application settings.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Request to prune backups for server '{server_name}' by user '{identity}'."
    )

    logger.debug(f"API Prune Backups: Server='{server_name}'")

    result = {}
    status_code = 500
    try:
        # Call the backup API function
        result = backup_restore_api.prune_old_backups(server_name)
        status_code = (
            200
            if result.get("status") == "success"
            else 500 if result.get("status") == "error" else 500
        )
    except BSMError as e:
        status_code = 400 if isinstance(e, UserInputError) else 500
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API Prune Backups '{server_name}': Unexpected error: {e}", exc_info=True
        )
        result = {"status": "error", "message": "Unexpected error pruning backups."}

    return jsonify(result), status_code


@backup_restore_bp.route(
    "/api/server/<string:server_name>/backup/list/<string:backup_type>",
    methods=["GET"],
)
@csrf.exempt
@auth_required
def list_server_backups_route(
    server_name: str, backup_type: str
) -> Tuple[Response, int]:
    """
    API endpoint to list available backup files (basenames only) for a specific server and type.

    Args:
        server_name (str): The name of the server.
        backup_type (str): The type of backups to list ("world", "properties", etc.).

    Returns:
        JSON response with a list of backup file basenames or an error message.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Request to list '{backup_type}' backups for server '{server_name}' by user '{identity}'."
    )

    result_dict: Dict[str, Any]
    status_code: int

    try:
        # Call the API function which now handles its own internal errors
        api_result = backup_restore_api.list_backup_files(
            server_name=server_name, backup_type=backup_type
        )

        if api_result.get("status") == "success":
            full_paths = api_result.get("backups", [])
            basenames = [os.path.basename(p) for p in full_paths]
            result_dict = {"status": "success", "backups": basenames}
            status_code = 200
            logger.info(
                f"API List Backups: Successfully listed {len(basenames)} backups for '{server_name}' ({backup_type})."
            )
        else:
            # Pass the error from the API layer directly to the client
            result_dict = api_result
            status_code = 400  # Use 400 for client-side errors (e.g., invalid type)
            logger.warning(
                f"API List Backups: Handler for '{server_name}' returned error: {result_dict.get('message')}"
            )

    except BSMError as e:
        status_code = 400 if isinstance(e, UserInputError) else 500
        result_dict = {"status": "error", "message": str(e)}
        logger.warning(f"API List Backups: {type(e).__name__} for '{server_name}': {e}")
    except Exception as e:
        logger.error(
            f"API List Backups: Unexpected critical error in route for '{server_name}': {e}",
            exc_info=True,
        )
        result_dict = {
            "status": "error",
            "message": "A critical server error occurred while listing backups.",
        }
        status_code = 500

    return jsonify(result_dict), status_code


@backup_restore_bp.route(
    "/api/server/<string:server_name>/backup/action", methods=["POST"]
)
@csrf.exempt
@auth_required
def backup_action_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to trigger a server backup operation.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Backup action requested for server '{server_name}' by user '{identity}'."
    )

    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify(status="error", message="Invalid or missing JSON body."), 400

    backup_type = data.get("backup_type", "").lower()
    file_to_backup = data.get("file_to_backup")

    result_dict: Dict[str, Any]
    status_code: int

    try:
        if backup_type == "world":
            result_dict = backup_restore_api.backup_world(server_name)
        elif backup_type == "config":
            if not file_to_backup or not isinstance(file_to_backup, str):
                return (
                    jsonify(
                        status="error",
                        message="Missing 'file_to_backup' for config backup.",
                    ),
                    400,
                )
            result_dict = backup_restore_api.backup_config_file(
                server_name, file_to_backup.strip()
            )
        elif backup_type == "all":
            result_dict = backup_restore_api.backup_all(server_name)
        else:
            valid_types = ["world", "config", "all"]
            msg = f"Invalid 'backup_type'. Must be one of: {valid_types}."
            return jsonify(status="error", message=msg), 400

        # Determine status code based on the result from the API layer
        if result_dict.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Backup '{server_name}' ({backup_type}) succeeded: {result_dict.get('message')}"
            )
        else:
            status_code = 500  # API layer handled the error, so it's an internal/operational failure
            logger.error(
                f"API Backup '{server_name}' ({backup_type}) failed: {result_dict.get('message')}"
            )

    except BSMError as e:
        status_code = 404 if isinstance(e, InvalidServerNameError) else 500
        result_dict = {"status": "error", "message": f"Server operation error: {e}"}
        logger.error(
            f"API Backup '{server_name}': Application error: {e}", exc_info=True
        )
    except Exception as e:
        logger.error(
            f"API Backup '{server_name}': Unexpected error in route: {e}", exc_info=True
        )
        result_dict = {
            "status": "error",
            "message": "An unexpected server error occurred.",
        }
        status_code = 500

    return jsonify(result_dict), status_code


@backup_restore_bp.route(
    "/api/server/<string:server_name>/restore/action", methods=["POST"]
)
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def restore_action_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to trigger a server restoration from a specified backup file.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Restore action requested for server '{server_name}' by user '{identity}'."
    )

    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify(status="error", message="Invalid or missing JSON body."), 400

    restore_type = data.get("restore_type", "").lower()

    # --- Initial Input Validation ---
    valid_types = ["world", "properties", "allowlist", "permissions", "all"]
    if restore_type not in valid_types:
        return jsonify(status="error", message="Invalid 'restore_type' specified."), 400

    # --- LOGIC BRANCH 1: Handle 'all' restore type first ---
    # This case doesn't require a backup_file, so it has a separate, simpler logic path.
    if restore_type == "all":
        try:
            result_dict = backup_restore_api.restore_all(server_name)
            if result_dict.get("status") == "success":
                status_code = 200
                logger.info(
                    f"API Restore 'all' for '{server_name}' succeeded: {result_dict.get('message')}"
                )
            else:
                status_code = 500  # Operational error
                logger.error(
                    f"API Restore 'all' for '{server_name}' failed: {result_dict.get('message')}"
                )
            return jsonify(result_dict), status_code

        except BSMError as e:
            logger.error(
                f"API Restore 'all' for '{server_name}': Application error: {e}",
                exc_info=True,
            )
            return (
                jsonify(status="error", message=f"Server configuration error: {e}"),
                500,
            )
        except Exception as e:
            logger.error(
                f"API Restore 'all' for '{server_name}': Unexpected error in route: {e}",
                exc_info=True,
            )
            return (
                jsonify(status="error", message="An unexpected server error occurred."),
                500,
            )

    # --- LOGIC BRANCH 2: Handle all other restore types (world, properties, etc.) ---
    # These cases require a 'backup_file' to be specified.

    # --- Input Validation for specific file restore ---
    relative_backup_file = data.get("backup_file")
    if not relative_backup_file or not isinstance(relative_backup_file, str):
        return (
            jsonify(
                status="error",
                message="Missing or invalid 'backup_file' specified for this restore type.",
            ),
            400,
        )

    try:
        # --- Path Construction and Security Validation ---
        backup_base_dir = settings.get("BACKUP_DIR")
        if not backup_base_dir:
            raise BSMError("BACKUP_DIR is not configured in settings.")

        server_backup_dir = os.path.join(backup_base_dir, server_name)
        # Security: Prevent directory traversal by joining and then normalizing
        full_backup_path = os.path.normpath(
            os.path.join(server_backup_dir, relative_backup_file)
        )

        # Security check: Ensure the final path is within the server's backup directory
        if not os.path.abspath(full_backup_path).startswith(
            os.path.abspath(server_backup_dir)
        ):
            msg = "Invalid backup file path. Directory traversal attempt detected."
            logger.error(f"API Restore '{server_name}': Security violation - {msg}")
            return jsonify(status="error", message=msg), 400

        if not os.path.isfile(full_backup_path):
            return (
                jsonify(
                    status="error",
                    message=f"Backup file not found: {relative_backup_file}",
                ),
                404,
            )

        # --- Call Appropriate API Handler ---
        result_dict: Dict[str, Any]
        if restore_type == "world":
            result_dict = backup_restore_api.restore_world(
                server_name, full_backup_path
            )
        else:  # "properties", "allowlist", "permissions"
            result_dict = backup_restore_api.restore_config_file(
                server_name, full_backup_path
            )

        if result_dict.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Restore '{restore_type}' for '{server_name}' succeeded: {result_dict.get('message')}"
            )
        else:
            status_code = 500  # Operational error
            logger.error(
                f"API Restore '{restore_type}' for '{server_name}' failed: {result_dict.get('message')}"
            )

        return jsonify(result_dict), status_code

    except BSMError as e:
        logger.error(
            f"API Restore '{restore_type}' for '{server_name}': Application error: {e}",
            exc_info=True,
        )
        return jsonify(status="error", message=f"Server configuration error: {e}"), 500
    except Exception as e:
        logger.error(
            f"API Restore '{restore_type}' for '{server_name}': Unexpected error in route: {e}",
            exc_info=True,
        )
        return (
            jsonify(status="error", message="An unexpected server error occurred."),
            500,
        )
