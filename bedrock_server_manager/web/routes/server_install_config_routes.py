# bedrock-server-manager/bedrock_server_manager/web/routes/server_install_config_routes.py
"""
Flask Blueprint handling web routes and API endpoints related to new server
installation and the configuration of existing servers (properties, allowlist,
permissions, OS services).
"""

import os
import re
import platform
import logging
import json
from typing import Dict, List, Any, Tuple

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
from bedrock_server_manager.api import server as server_api
from bedrock_server_manager.api import server_install_config
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.api import system as system_api
from bedrock_server_manager.api import utils as utils_api
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config.settings import (
    settings,
)
from bedrock_server_manager.core.server import (
    server as server_base,
)
from bedrock_server_manager.web.routes.auth_routes import login_required, csrf
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)

# Import specific errors
from bedrock_server_manager.error import (
    MissingArgumentError,
    CommandNotFoundError,
    ServiceError,
    SystemdReloadError,
    InvalidServerNameError,
    FileOperationError,
    InvalidInputError,
    TypeError,
)

# Initialize logger
logger = logging.getLogger("bedrock_server_manager")

# Create Blueprint
server_install_config_bp = Blueprint(
    "install_config_routes",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)


# --- Route: Install Server Page ---
@server_install_config_bp.route("/install", methods=["GET"])
@login_required  # Requires web session
def install_server_route() -> Response:
    """
    Renders the initial page for installing a new Bedrock server instance.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(f"User '{identity}' accessed new server install page ('/install').")
    # Pass default/empty values if template expects them for form fields
    return render_template(
        "install.html",
        server_name="",
        server_version="LATEST",
    )


# --- API Route: Install Server ---
@server_install_config_bp.route("/api/server/install", methods=["POST"])
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def install_server_api_route() -> Tuple[Response, int]:
    """
    API endpoint to handle the creation and installation of a new server instance.

    Validates input, checks for existing servers (handles overwrite), calls the
    installation handler, and returns the result.

    JSON Request Body Example:
        {
            "server_name": "MyNewServer",
            "server_version": "LATEST",
            "overwrite": false
        }
    """
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: New server install request received from user '{identity}'.")

    # --- Input Validation ---
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        logger.warning("API Install Server: Invalid/missing JSON request body.")
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    logger.debug(f"API Install Server: Received data: {data}")
    server_name = data.get("server_name")
    server_version = data.get("server_version")
    overwrite = data.get("overwrite", False)  # Default overwrite to False if missing

    # Validate presence and basic type
    if not server_name or not isinstance(server_name, str) or not server_name.strip():
        return jsonify(status="error", message="Server name (string) is required."), 400
    if (
        not server_version
        or not isinstance(server_version, str)
        or not server_version.strip()
    ):
        return (
            jsonify(status="error", message="Server version (string) is required."),
            400,
        )
    if not isinstance(overwrite, bool):
        return (
            jsonify(status="error", message="'overwrite' flag must be true or false."),
            400,
        )

    server_name = server_name.strip()  # Use trimmed name

    result: Dict[str, Any] = {}
    status_code = 500  # Default to internal error

    try:
        base_dir = get_base_dir()  # May raise FileOperationError
        config_dir = getattr(settings, "_config_dir", None)  # Get default config dir
        if not config_dir:
            raise FileOperationError("Base configuration directory not set.")

        # --- Server Name Format Validation ---
        logger.debug(f"Validating server name format for '{server_name}'...")
        validation_result = utils_api.validate_server_name_format(
            server_name
        )  # Returns dict
        if validation_result.get("status") == "error":
            logger.warning(
                f"API Install Server: Invalid name format: {validation_result.get('message')}"
            )
            return jsonify(validation_result), 400  # Return validation error dict

        # --- Check Existence & Handle Overwrite ---
        server_dir = os.path.join(base_dir, server_name)
        server_exists = os.path.isdir(server_dir)  # Check if directory exists
        logger.debug(
            f"Checking existence of server directory '{server_dir}': {server_exists}"
        )

        if server_exists and not overwrite:
            logger.info(
                f"Server '{server_name}' already exists and overwrite=false. Requesting client confirmation."
            )
            confirm_message = f"Server '{server_name}' already exists. Overwrite existing data and reinstall?"
            # Return special status for frontend to handle confirmation dialog
            return (
                jsonify(
                    status="confirm_needed",
                    message=confirm_message,
                    server_name=server_name,
                    server_version=server_version,
                ),
                200,
            )  # OK status code, but specific status in body

        # --- Proceed with Install/Overwrite ---
        # If server exists and overwrite is true, delete first
        if server_exists and overwrite:
            logger.warning(
                f"Overwrite requested for existing server '{server_name}'. Deleting existing data..."
            )
            # Use API delete function which returns dict
            delete_result = server_api.delete_server_data(
                server_name, base_dir, config_dir
            )
            if delete_result.get("status") == "error":
                error_msg = f"Failed to delete existing server data before overwrite: {delete_result.get('message')}"
                logger.error(f"API Install Server: {error_msg}")
                return jsonify(status="error", message=error_msg), 500

        # Call the main installation API function
        logger.info(
            f"Calling API handler install_new_server for '{server_name}', version '{server_version}'..."
        )
        result = server_install_config.install_new_server(
            server_name, server_version, base_dir, config_dir
        )
        logger.debug(f"API Install Server '{server_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 201  # Created
            success_msg = result.get(
                "message", f"Server '{server_name}' installed successfully."
            )
            logger.info(f"API Install Server: {success_msg}")
            result["message"] = success_msg
            # Add next step URL for UI flow
            result["next_step_url"] = url_for(
                ".configure_properties_route", server_name=server_name, new_install=True
            )
        else:
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error during installation.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Install Server failed for '{server_name}': {error_msg}")
            # Attempt cleanup of potentially partial install? Risky. Log error.
            result = {"status": "error", "message": error_msg}

    except (MissingArgumentError, InvalidServerNameError, TypeError) as e:
        logger.warning(
            f"API Install Server '{server_name}': Input error: {e}", exc_info=True
        )
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except FileOperationError as e:  # Catch config/base_dir errors
        logger.error(
            f"API Install Server '{server_name}': Configuration/File error: {e}",
            exc_info=True,
        )
        status_code = 500
        result = {"status": "error", "message": f"Configuration or File error: {e}"}
    except Exception as e:  # Catch unexpected errors
        logger.error(
            f"API Install Server '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {
            "status": "error",
            "message": f"An unexpected error occurred during installation: {e}",
        }

    return jsonify(result), status_code


# --- Route: Configure Server Properties Page ---
@server_install_config_bp.route(
    "/server/<string:server_name>/configure_properties", methods=["GET"]
)
@login_required  # Requires web session
def configure_properties_route(server_name: str) -> Response:
    """
    Renders the page for configuring the `server.properties` file.

    Displays current values and allows editing. Handles distinction between
    initial setup (new_install=True) and later modification.

    Args:
        server_name: The name of the server passed in the URL.

    Query Params:
        new_install (str, optional): "true" if part of the initial server setup workflow.

    Returns:
        Rendered HTML page ('configure_properties.html') with properties data,
        or redirects to index if properties cannot be loaded.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed configure properties page for server '{server_name}'."
    )

    properties_data: Dict[str, str] = {}
    try:
        base_dir = get_base_dir()

        # API call to read properties
        logger.debug(
            f"Calling API: server_install_config.read_server_properties for '{server_name}'"
        )
        properties_response = server_install_config.read_server_properties(
            server_name, base_dir
        )

        if properties_response.get("status") == "error":
            error_msg = f"Error loading properties: {properties_response.get('message', 'Unknown error')}"
            flash(error_msg, "error")
            logger.error(f"{error_msg} for server '{server_name}'")
            return redirect(url_for("main_routes.index"))  # Redirect on error

        properties_data = properties_response.get("properties", {})
        logger.debug(
            f"Successfully loaded {len(properties_data)} properties for '{server_name}'."
        )

    except FileOperationError as e:  # Error from get_base_dir
        flash(f"Configuration error accessing server properties: {e}", "danger")
        logger.error(
            f"Error accessing properties for '{server_name}': {e}", exc_info=True
        )
        return redirect(url_for("main_routes.index"))
    except Exception as e:  # Unexpected error
        flash("An unexpected error occurred while loading server properties.", "danger")
        logger.error(
            f"Unexpected error loading properties page for '{server_name}': {e}",
            exc_info=True,
        )
        return redirect(url_for("main_routes.index"))

    # Check query parameter for new installation flow
    new_install = request.args.get("new_install", "false").lower() == "true"
    logger.debug(
        f"Rendering configure_properties.html for '{server_name}'. New Install Flow: {new_install}"
    )

    return render_template(
        "configure_properties.html",
        server_name=server_name,
        properties=properties_data,
        new_install=new_install,
    )


# --- API Route: Configure Server Properties ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/properties", methods=["POST"]
)
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def configure_properties_api_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to validate and update specified key-value pairs in server.properties.

    Expects a JSON body containing the properties to update. Only updates keys
    present in an internal `allowed_keys` list. Performs validation before writing.

    Args:
        server_name: The name of the server passed in the URL.

    JSON Request Body Example:
        {
            "level-name": "My Awesome World",
            "max-players": "15",
            "server-port": "19133"
        }

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 200 OK: {"status": "success", "message": "..."}
        - 400 Bad Request: Invalid JSON or property validation failed.
        - 500 Internal Server Error: Failed to write properties file.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Configure properties request for server '{server_name}' by user '{identity}'."
    )

    # --- Input Validation ---
    properties_data = request.get_json(silent=True)
    if not properties_data or not isinstance(properties_data, dict):
        logger.warning(
            f"API Configure Properties '{server_name}': Invalid/missing JSON body."
        )
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    logger.debug(
        f"API Configure Properties '{server_name}': Received data: {properties_data}"
    )

    # Whitelist of properties allowed to be modified via this endpoint
    allowed_keys = [
        "server-name",
        "level-name",
        "gamemode",
        "difficulty",
        "allow-cheats",
        "max-players",
        "server-port",
        "server-portv6",
        "enable-lan-visibility",
        "allow-list",
        "default-player-permission-level",
        "view-distance",
        "tick-distance",
        "level-seed",
        "online-mode",
        "texturepack-required",
    ]
    logger.debug(f"Allowed property keys for update: {allowed_keys}")

    properties_to_update: Dict[str, str] = {}
    validation_errors: Dict[str, str] = {}

    # --- Validate Received Properties ---
    logger.debug("Validating received property values...")
    for key, value in properties_data.items():
        if key not in allowed_keys:
            logger.warning(
                f"API Configure Properties '{server_name}': Ignoring disallowed key '{key}'."
            )
            continue

        value_str = str(value).strip() if value is not None else ""

        # Clean level-name specifically
        if key == "level-name":
            original_value = value_str
            value_str = re.sub(r'[<>:"/\\|?* ]+', "_", original_value).strip(
                "_"
            )  # Replace invalid chars and spaces
            if value_str != original_value:
                logger.info(
                    f"Cleaned 'level-name' from '{original_value}' to '{value_str}'"
                )

        # Validate using the API util function
        validation_result = server_install_config.validate_server_property_value(
            key, value_str
        )
        if validation_result.get("status") == "error":
            validation_errors[key] = validation_result.get("message", "Invalid value.")
            logger.warning(
                f"API Validation Error for '{key}'='{value_str}': {validation_errors[key]}"
            )
        else:
            properties_to_update[key] = value_str  # Store validated string value

    if validation_errors:
        error_summary = "Validation failed for one or more properties."
        logger.error(
            f"API Configure Properties validation failed for '{server_name}': {validation_errors}"
        )
        return (
            jsonify(status="error", message=error_summary, errors=validation_errors),
            400,
        )

    # --- Apply Changes (if any valid properties remain) ---
    result: Dict[str, Any] = {}
    status_code = 500
    if not properties_to_update:
        logger.info(
            f"API Configure Properties '{server_name}': No valid properties to update."
        )
        return (
            jsonify(
                status="success",
                message="No valid properties provided or no changes needed.",
            ),
            200,
        )

    try:
        # Call the API function to modify the file
        logger.info(
            f"Calling API handler modify_server_properties for '{server_name}'..."
        )
        logger.debug(f"Properties to update: {properties_to_update}")
        result = server_install_config.modify_server_properties(
            server_name, properties_to_update
        )  # Handles base_dir
        logger.debug(
            f"API Modify Properties '{server_name}': Handler response: {result}"
        )

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            success_msg = result.get(
                "message",
                f"Server properties for '{server_name}' updated successfully.",
            )
            logger.info(f"API Modify Properties successful for '{server_name}'.")
            result["message"] = success_msg
        else:
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error modifying properties.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(
                f"API Modify Properties failed for '{server_name}': {error_msg}"
            )
            result = {"status": "error", "message": error_msg}

    except (
        FileNotFoundError,
        FileOperationError,
        InvalidInputError,
        InvalidServerNameError,
    ) as e:
        logger.error(
            f"API Modify Properties '{server_name}': Core error: {e}", exc_info=True
        )
        status_code = (
            500 if isinstance(e, FileOperationError) else 400
        )  # 400 for validation/name error
        result = {"status": "error", "message": f"Error updating properties: {e}"}
    except Exception as e:
        logger.error(
            f"API Modify Properties '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- Route: Configure Allowlist Page ---
@server_install_config_bp.route(
    "/server/<string:server_name>/configure_allowlist", methods=["GET"]
)
@login_required  # Requires web session
def configure_allowlist_route(server_name: str) -> Response:
    """
    Renders the page for configuring the server's allowlist (`allowlist.json`).

    Displays the current allowlist and allows adding/removing players (frontend logic).

    Args:
        server_name: The name of the server passed in the URL.

    Query Params:
        new_install (str, optional): "true" if part of the initial server setup workflow.

    Returns:
        Rendered HTML page ('configure_allowlist.html') with current allowlist data.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed configure allowlist page for server '{server_name}'."
    )

    existing_players: List[Dict[str, Any]] = []
    try:
        # API call to get current allowlist (read mode)
        logger.debug(
            f"Calling API: server_install_config.configure_allowlist (read mode) for '{server_name}'"
        )
        result = server_install_config.configure_allowlist(
            server_name
        )  # Handles base_dir

        if result.get("status") == "error":
            error_msg = f"Error loading current allowlist: {result.get('message', 'Unknown error')}"
            flash(error_msg, "error")
            logger.error(f"{error_msg} for server '{server_name}'")
        else:
            existing_players = result.get("existing_players", [])
            logger.info(
                f"Loaded {len(existing_players)} existing players from allowlist for '{server_name}'."
            )

    except (MissingArgumentError, InvalidServerNameError, FileOperationError) as e:
        flash(f"Error loading allowlist: {e}", "error")
        logger.error(
            f"Error preparing allowlist page for '{server_name}': {e}", exc_info=True
        )
        # Render template with empty list on config/input error
    except Exception as e:
        flash("An unexpected error occurred loading the allowlist.", "error")
        logger.error(
            f"Unexpected error loading allowlist page for '{server_name}': {e}",
            exc_info=True,
        )
        # Render template with empty list on unexpected error

    new_install = request.args.get("new_install", "false").lower() == "true"
    logger.debug(
        f"Rendering configure_allowlist.html for '{server_name}'. New Install Flow: {new_install}"
    )

    return render_template(
        "configure_allowlist.html",
        server_name=server_name,
        existing_players=existing_players,  # List of dicts {'name': ..., 'ignoresPlayerLimit': ...}
        new_install=new_install,
        # app_name from context processor
    )


# --- API Route: Save Allowlist (Replace) ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/allowlist", methods=["POST"]
)
@csrf.exempt  # API Endpoint
@auth_required  # Requires Session or JWT
def save_allowlist_api_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to **REPLACE** the server's entire allowlist.

    Expects JSON body containing a 'players' list (names) and 'ignoresPlayerLimit' flag.
    Use this for initial setup or full replacement actions from the UI.

    Args:
        server_name: The name of the server passed in the URL.

    JSON Request Body Example:
        {
            "players": ["Player1", "PlayerX"],
            "ignoresPlayerLimit": false
        }

    Returns:
        JSON response indicating success or failure.
        - 200 OK: {"status": "success", "message": "..."}
        - 400 Bad Request: Invalid JSON or input data.
        - 500 Internal Server Error: Failed to save allowlist.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: SAVE/REPLACE allowlist request for server '{server_name}' by user '{identity}'."
    )

    # --- Input Validation ---
    data = request.get_json(silent=True)
    if data is None:  # Allow empty dict {} but not non-dict/non-json
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    logger.debug(f"API Save Allowlist '{server_name}': Received data: {data}")
    players_list_names = data.get("players")
    ignore_limit = data.get("ignoresPlayerLimit", False)  # Default to false

    if players_list_names is None or not isinstance(players_list_names, list):
        return (
            jsonify(
                status="error",
                message="Request body must contain a 'players' list (can be empty).",
            ),
            400,
        )
    if not isinstance(ignore_limit, bool):
        return (
            jsonify(
                status="error", message="'ignoresPlayerLimit' must be true or false."
            ),
            400,
        )

    # Clean names, allow empty list to clear allowlist
    valid_player_names = [
        name.strip()
        for name in players_list_names
        if isinstance(name, str) and name.strip()
    ]
    logger.debug(
        f"API Save Allowlist '{server_name}': Validated player names: {valid_player_names}, IgnoreLimit: {ignore_limit}"
    )

    # Format for the handler
    new_allowlist_data = [
        {"name": name, "ignoresPlayerLimit": ignore_limit}
        for name in valid_player_names
    ]

    # --- Call API Handler ---
    result: Dict[str, Any] = {}
    status_code = 500
    try:
        # Call API function (handles base_dir)
        result = server_install_config.configure_allowlist(
            server_name, new_players_data=new_allowlist_data
        )
        logger.debug(f"API Save Allowlist '{server_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            # Message depends on whether list was cleared or saved
            player_count = len(valid_player_names)
            success_msg = (
                result.get(
                    "message",
                    f"Allowlist saved successfully with {player_count} player(s).",
                )
                if player_count > 0
                else result.get("message", "Allowlist cleared successfully.")
            )
            logger.info(
                f"API Save Allowlist successful for '{server_name}'. {success_msg}"
            )
            result["message"] = success_msg
        else:
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error saving allowlist.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Save Allowlist failed for '{server_name}': {error_msg}")
            result = {"status": "error", "message": error_msg}

    except (
        MissingArgumentError,
        InvalidServerNameError,
        TypeError,
        FileOperationError,
    ) as e:
        logger.warning(
            f"API Save Allowlist '{server_name}': Input/Config error: {e}",
            exc_info=True,
        )
        status_code = 400 if isinstance(e, (MissingArgumentError, TypeError)) else 500
        result = {"status": "error", "message": f"Error saving allowlist: {e}"}
    except Exception as e:
        logger.error(
            f"API Save Allowlist '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- API Route: Get Allowlist ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/allowlist", methods=["GET"]
)
@csrf.exempt  # GET request
@auth_required  # Requires session OR JWT
def get_allowlist_api_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to retrieve the current allowlist for a server.

    Args:
        server_name: The name of the server passed in the URL.

    Returns:
        JSON response containing the allowlist data or an error.
        - 200 OK: {"status": "success", "existing_players": List[Dict], "message": "..."}
        - 500 Internal Server Error: If reading the allowlist fails.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Get allowlist request for server '{server_name}' by user '{identity}'."
    )

    result: Dict[str, Any] = {}
    status_code = 500
    try:
        # Call API function (read mode)
        result = server_install_config.configure_allowlist(
            server_name, new_players_data=None
        )  # Handles base_dir
        logger.debug(f"API Get Allowlist '{server_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            player_count = len(result.get("existing_players", []))
            success_msg = result.get(
                "message",
                f"Successfully retrieved {player_count} players from allowlist.",
            )
            logger.info(f"API Get Allowlist successful for '{server_name}'.")
            result["message"] = success_msg
            # Ensure 'existing_players' key exists, even if empty
            if "existing_players" not in result:
                result["existing_players"] = []
        else:
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error retrieving allowlist.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Get Allowlist failed for '{server_name}': {error_msg}")
            result = {"status": "error", "message": error_msg}

    except (MissingArgumentError, InvalidServerNameError, FileOperationError) as e:
        logger.error(
            f"API Get Allowlist '{server_name}': Input/Config error: {e}", exc_info=True
        )
        status_code = 500  # Treat as internal error
        result = {"status": "error", "message": f"Error retrieving allowlist: {e}"}
    except Exception as e:
        logger.error(
            f"API Get Allowlist '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    # Return structure should include 'existing_players' on success
    return jsonify(result), status_code


# --- Route: Configure Permissions Page ---
@server_install_config_bp.route(
    "/server/<string:server_name>/configure_permissions", methods=["GET"]
)
@login_required  # Requires web session
def configure_permissions_route(server_name: str) -> Response:
    """
    Renders the page for configuring player permission levels (`permissions.json`).

    Displays known players (from `players.json`) and their current permission levels.

    Args:
        server_name: The name of the server passed in the URL.

    Query Params:
        new_install (str, optional): "true" if part of the initial server setup workflow.

    Returns:
        Rendered HTML page ('configure_permissions.html') with player and permission data.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed configure permissions page for server '{server_name}'."
    )

    players: List[Dict[str, Any]] = []
    permissions: Dict[str, str] = {}
    try:
        base_dir = get_base_dir()
        effective_config_dir = getattr(
            settings, "_config_dir", None
        )  # Needed for players.json
        if not effective_config_dir:
            raise FileOperationError("Base configuration directory not set.")

        # 1. Get list of known players (name/xuid) from players.json
        logger.debug("Calling API: player_api.get_players_from_json")
        players_response = player_api.get_players_from_json(
            config_dir=effective_config_dir
        )
        if players_response.get("status") == "error":
            flash(
                f"Warning: Could not load global player list: {players_response.get('message')}",
                "warning",
            )
            logger.warning(
                f"Could not load players.json: {players_response.get('message')}"
            )
        else:
            players = players_response.get("players", [])
            logger.info(f"Loaded {len(players)} players from global players.json.")

        # 2. Get current permissions map {xuid: level} from this server's permissions.json
        logger.debug(f"Reading current permissions for server '{server_name}'...")
        server_dir = os.path.join(base_dir, server_name)
        permissions_file = os.path.join(server_dir, "permissions.json")
        if os.path.isfile(permissions_file):
            try:
                with open(permissions_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        permissions_list = json.loads(content)
                        if isinstance(permissions_list, list):
                            # Convert list format [ {xuid:.., perm:..}, ...] to map {xuid: perm}
                            for entry in permissions_list:
                                if (
                                    isinstance(entry, dict)
                                    and "xuid" in entry
                                    and "permission" in entry
                                ):
                                    permissions[str(entry["xuid"])] = str(
                                        entry["permission"]
                                    )  # Ensure keys/values are strings
                            logger.debug(
                                f"Loaded {len(permissions)} entries from '{permissions_file}'."
                            )
                        else:
                            logger.warning(
                                f"Permissions file '{permissions_file}' does not contain a list. Ignoring."
                            )
                    else:
                        logger.debug(f"Permissions file '{permissions_file}' is empty.")
            except (OSError, json.JSONDecodeError) as e:
                flash(f"Error reading permissions file: {e}", "error")
                logger.error(
                    f"Error reading permissions file '{permissions_file}': {e}",
                    exc_info=True,
                )
                # Continue with empty permissions map
        else:
            logger.info(
                f"Permissions file not found at '{permissions_file}'. Assuming default permissions."
            )

        # 3. Augment player list with entries only present in permissions.json
        #    (Ensures all players with set permissions are shown, even if not in global list)
        known_player_xuids = {str(p.get("xuid")) for p in players if p.get("xuid")}
        xuids_only_in_permissions = set(permissions.keys()) - known_player_xuids
        if xuids_only_in_permissions:
            logger.debug(
                f"Found XUIDs in permissions but not global list: {xuids_only_in_permissions}"
            )
            for xuid in xuids_only_in_permissions:
                players.append(
                    {"xuid": xuid, "name": f"Unknown (XUID: {xuid})"}
                )  # Add placeholder

        # Sort final list for display
        players.sort(key=lambda p: p.get("name", "").lower())

    except FileOperationError as e:  # Catch config/base_dir errors
        flash(f"Configuration error loading permissions page: {e}", "danger")
        logger.error(
            f"Error preparing permissions page for '{server_name}': {e}", exc_info=True
        )
    except Exception as e:
        flash("An unexpected error occurred while loading permissions.", "danger")
        logger.error(
            f"Unexpected error loading permissions page for '{server_name}': {e}",
            exc_info=True,
        )

    new_install = request.args.get("new_install", "false").lower() == "true"
    logger.debug(
        f"Rendering configure_permissions.html for '{server_name}'. New Install: {new_install}, Players: {len(players)}, Permissions: {len(permissions)}"
    )

    return render_template(
        "configure_permissions.html",
        server_name=server_name,
        players=players,  # List of dicts [{'name': str, 'xuid': str}]
        permissions=permissions,  # Dict {xuid_str: permission_level_str}
        new_install=new_install,
    )


# --- API Route: Configure Permissions ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/permissions", methods=["PUT"]
)
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def configure_permissions_api_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to update player permissions based on submitted data.

    Expects a JSON body with a 'permissions' object mapping XUIDs to permission levels.
    It calls the single-player permission update handler for each entry.

    Args:
        server_name: The name of the server passed in the URL.

    JSON Request Body Example:
        {
            "permissions": {
                "2535416409681153": "operator",
                "2535457894355891": "member"
            }
        }

    Returns:
        JSON response indicating overall success or failure, potentially with details
        about individual player update errors.
        - 200 OK: {"status": "success", "message": "..."}
        - 400 Bad Request: Invalid JSON or permission levels.
        - 500 Internal Server Error: If one or more permission updates failed server-side.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Configure permissions request for server '{server_name}' by user '{identity}'."
    )

    # --- Input Validation ---
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict) or "permissions" not in data:
        return (
            jsonify(
                status="error",
                message="Request body must contain a 'permissions' object.",
            ),
            400,
        )

    permissions_map = data.get("permissions")
    if not isinstance(permissions_map, dict):
        return (
            jsonify(
                status="error",
                message="'permissions' value must be an object mapping XUIDs to levels.",
            ),
            400,
        )

    logger.debug(
        f"API Configure Permissions '{server_name}': Received map: {permissions_map}"
    )

    # Validate levels first
    valid_levels = ("visitor", "member", "operator")
    validation_errors: Dict[str, str] = {}
    players_to_process: Dict[str, str] = {}
    for xuid, level in permissions_map.items():
        if not isinstance(level, str) or level.lower() not in valid_levels:
            validation_errors[xuid] = (
                f"Invalid level '{level}'. Must be one of {valid_levels}."
            )
        else:
            players_to_process[xuid] = (
                level.lower()
            )  # Store validated, lowercased level

    if validation_errors:
        logger.warning(
            f"API Configure Permissions validation failed for '{server_name}': {validation_errors}"
        )
        return (
            jsonify(
                status="error",
                message="Validation failed for one or more permission levels.",
                errors=validation_errors,
            ),
            400,
        )

    # --- Apply Permissions (Loop through validated players) ---
    all_success = True
    handler_errors: Dict[str, str] = {}
    processed_count = 0
    result: Dict[str, Any] = {}
    status_code = 500

    if not players_to_process:
        logger.info(
            f"API Configure Permissions '{server_name}': No valid permissions to apply."
        )
        return (
            jsonify(status="success", message="No valid permission changes submitted."),
            200,
        )

    try:
        base_dir = get_base_dir()
        # Get player names map (optional but useful for the core function)
        players_map_result = (
            player_api.get_players_from_json()
        )  # Uses default config dir
        player_name_map = {
            p.get("xuid"): p.get("name")
            for p in players_map_result.get("players", [])
            if p.get("xuid")
        }

        logger.info(
            f"Processing {len(players_to_process)} permission updates for server '{server_name}'..."
        )
        for xuid, level in players_to_process.items():
            player_name = player_name_map.get(
                xuid
            )  # Can be None if player not in global list
            logger.debug(
                f"Calling API handler: configure_player_permission for XUID='{xuid}', Level='{level}'"
            )

            # Call API handler (which calls core handler)
            handler_result = server_install_config.configure_player_permission(
                server_name=server_name,
                xuid=xuid,
                player_name=player_name,  # Pass name if known, core func handles None
                permission=level,
                base_dir=base_dir,
            )
            processed_count += 1

            if handler_result.get("status") != "success":
                all_success = False
                error_msg = handler_result.get("message", "Unknown handler error")
                handler_errors[xuid] = error_msg
                logger.error(
                    f"Failed to set permission for XUID {xuid} on '{server_name}': {error_msg}"
                )

        # --- Determine Final Response ---
        if all_success:
            status_code = 200
            success_msg = f"Permissions updated successfully for {processed_count} player(s) on server '{server_name}'."
            logger.info(f"API Permissions Update successful for '{server_name}'.")
            result = {"status": "success", "message": success_msg}
        else:
            status_code = 500  # Indicate partial/full failure
            error_summary = f"One or more errors occurred while setting permissions for '{server_name}'."
            logger.error(
                f"API Permissions Update failed for '{server_name}'. Errors: {handler_errors}"
            )
            result = {
                "status": "error",
                "message": error_summary,
                "errors": handler_errors,
            }

    except FileOperationError as e:  # Catch config/base_dir errors
        logger.error(
            f"API Configure Permissions '{server_name}': Configuration/File error: {e}",
            exc_info=True,
        )
        status_code = 500
        result = {"status": "error", "message": f"Configuration or File error: {e}"}
    except Exception as e:  # Catch unexpected errors during orchestration
        logger.error(
            f"API Configure Permissions '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- Route: Configure Service Page ---
@server_install_config_bp.route(
    "/server/<string:server_name>/configure_service", methods=["GET"]
)
@login_required  # Requires web session
def configure_service_route(server_name: str) -> Response:
    """
    Renders the page for configuring OS-specific service settings (e.g., systemd autostart/autoupdate).

    Displays current settings based on the detected OS.

    Args:
        server_name: The name of the server passed in the URL.

    Query Params:
        new_install (str, optional): "true" if part of the initial server setup workflow.

    Returns:
        Rendered HTML page ('configure_service.html') with current service settings.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed configure service page for server '{server_name}'."
    )

    template_data: Dict[str, Any] = {
        "server_name": server_name,
        "os": platform.system(),
        "new_install": request.args.get("new_install", "false").lower() == "true",
        "autoupdate": False,  # Default
        "autostart": False,  # Default (Linux only)
    }
    logger.debug(f"Initial template data: {template_data}")

    try:
        config_dir = getattr(settings, "_config_dir", None)
        if not config_dir:
            raise FileOperationError("Base configuration directory not set.")

        if template_data["os"] == "Linux":
            # Check if service file exists and if it's enabled for autostart
            logger.debug(
                f"Checking Linux systemd status for service 'bedrock-{server_name}'..."
            )

            logger.info(
                "Linux detected. Service status checks (enabled/autoupdate) require further implementation in API/Core."
            )

        elif template_data["os"] == "Windows":
            # Read the autoupdate flag from the server's config json
            logger.debug(
                f"Reading 'autoupdate' flag from config for Windows server '{server_name}'..."
            )
            autoupdate_val = server_base.manage_server_config(
                server_name, "autoupdate", "read", config_dir=config_dir
            )
            # manage_server_config returns the value directly (or None)
            template_data["autoupdate"] = (
                autoupdate_val if isinstance(autoupdate_val, bool) else False
            )  # Default to false if not set or not bool
            logger.debug(
                f"Windows autoupdate setting read as: {template_data['autoupdate']}"
            )

        else:
            flash(
                f"Service configuration not applicable for OS: {template_data['os']}.",
                "info",
            )

    except FileOperationError as e:
        flash(f"Configuration error loading service page: {e}", "danger")
        logger.error(
            f"Error preparing service config page for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        flash("An unexpected error occurred loading service settings.", "danger")
        logger.error(
            f"Unexpected error loading service page for '{server_name}': {e}",
            exc_info=True,
        )

    logger.debug(f"Rendering configure_service.html for '{server_name}'")
    return render_template("configure_service.html", **template_data)


# --- API Route: Configure Service ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/service", methods=["POST"]
)
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def configure_service_api_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to configure OS-specific service settings based on JSON payload.

    Handles Linux (systemd autostart/autoupdate via service file recreation) and
    Windows (autoupdate flag via server config JSON).

    Args:
        server_name: The name of the server passed in the URL.

    JSON Request Body Example (Linux):
        {"autoupdate": true, "autostart": true}
    JSON Request Body Example (Windows):
        {"autoupdate": true}

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 200 OK: {"status": "success", "message": "..."}
        - 400 Bad Request: Invalid JSON or input values.
        - 403 Forbidden: Operation not supported on current OS.
        - 500 Internal Server Error: Failed to apply settings.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Configure service request for server '{server_name}' by user '{identity}'."
    )
    current_os = platform.system()

    # --- Input Validation ---
    data = request.get_json(silent=True)
    if data is None:  # Allow empty dict {}
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    logger.debug(f"API Configure Service '{server_name}': Received data: {data}")

    result: Dict[str, Any] = {}
    status_code = 500
    try:
        if current_os == "Linux":
            # Expect 'autoupdate' and 'autostart' booleans
            autoupdate = data.get("autoupdate", False)
            autostart = data.get("autostart", False)
            if not isinstance(autoupdate, bool) or not isinstance(autostart, bool):
                return (
                    jsonify(
                        status="error",
                        message="'autoupdate' and 'autostart' must be boolean values.",
                    ),
                    400,
                )

            logger.info(
                f"Calling API handler create_systemd_service for '{server_name}' (Update={autoupdate}, Start={autostart})..."
            )
            result = system_api.create_systemd_service(
                server_name, autoupdate=autoupdate, autostart=autostart
            )  # Handles base_dir

        elif current_os == "Windows":
            # Expect 'autoupdate' boolean
            autoupdate = data.get("autoupdate", False)
            if not isinstance(autoupdate, bool):
                return (
                    jsonify(
                        status="error", message="'autoupdate' must be a boolean value."
                    ),
                    400,
                )

            autoupdate_str = "true" if autoupdate else "false"  # Handler expects string
            logger.info(
                f"Calling API handler set_windows_autoupdate for '{server_name}' (Value='{autoupdate_str}')..."
            )
            result = system_api.set_windows_autoupdate(
                server_name, autoupdate_str
            )  # Handles config_dir

        else:
            msg = f"Service configuration is not supported on this operating system ({current_os})."
            logger.error(
                f"API Configure Service called on unsupported OS: {current_os}"
            )
            return (
                jsonify(status="error", message=msg),
                403,
            )  # Forbidden or 501 Not Implemented

        logger.debug(
            f"API Configure Service '{server_name}': Handler response: {result}"
        )

        # Process handler result
        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            success_msg = result.get(
                "message", f"Service settings for '{server_name}' updated successfully."
            )
            logger.info(f"API Configure Service successful for '{server_name}'.")
            result["message"] = success_msg
        else:
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error configuring service.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(
                f"API Configure Service failed for '{server_name}': {error_msg}"
            )
            result = {"status": "error", "message": error_msg}

    except (
        MissingArgumentError,
        InvalidServerNameError,
        InvalidInputError,
        TypeError,
    ) as e:
        logger.warning(
            f"API Configure Service '{server_name}': Input error: {e}", exc_info=True
        )
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except (
        FileOperationError,
        CommandNotFoundError,
        ServiceError,
        SystemdReloadError,
    ) as e:  # Catch specific core errors
        logger.error(
            f"API Configure Service '{server_name}': Core service error: {e}",
            exc_info=True,
        )
        status_code = 500
        result = {"status": "error", "message": f"Error configuring service: {e}"}
    except Exception as e:  # Catch unexpected errors
        logger.error(
            f"API Configure Service '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code
