# bedrock_server_manager/web/routes/server_install_config_routes.py
"""
Flask Blueprint handling web routes and API endpoints related to new server
installation and the configuration of existing servers (properties, allowlist,
permissions, OS services).
"""

import logging
import platform
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
from bedrock_server_manager.api import server_install_config
from bedrock_server_manager.api import server as server_api
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.api import system as system_api
from bedrock_server_manager.api import utils as utils_api
from bedrock_server_manager.web.routes.auth_routes import login_required, csrf
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)

# Import specific errors
from bedrock_server_manager.error import (
    BSMError,
    UserInputError,
    InvalidServerNameError,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Create Blueprint
server_install_config_bp = Blueprint(
    "install_config_routes",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)


# --- Route: Install Server Page ---
@server_install_config_bp.route("/install", methods=["GET"])
@login_required
def install_server_route() -> Response:
    """Renders the initial page for installing a new Bedrock server instance."""
    identity = get_current_identity()
    logger.info(f"User '{identity}' accessed new server install page.")
    return render_template("install.html")


# --- API Route: Install Server ---
@server_install_config_bp.route("/api/server/install", methods=["POST"])
@csrf.exempt
@auth_required
def install_server_api_route() -> Tuple[Response, int]:
    """API endpoint to handle the creation and installation of a new server instance."""
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: New server install request from user '{identity}'.")

    data = request.get_json()
    if not data:
        return jsonify(status="error", message="Invalid or missing JSON body."), 400

    server_name = data.get("server_name", "").strip()
    server_version = data.get("server_version", "LATEST").strip()
    overwrite = data.get("overwrite", False)

    # Validate name format before proceeding
    validation_result = utils_api.validate_server_name_format(server_name)
    if validation_result.get("status") == "error":
        return jsonify(validation_result), 400

    result: Dict[str, Any]
    status_code: int

    try:
        # Check for existence and handle overwrite logic
        if not overwrite and utils_api.validate_server_exist(server_name):
            return (
                jsonify(
                    status="confirm_needed",
                    message=f"Server '{server_name}' already exists. Overwrite?",
                ),
                200,
            )

        # If overwriting, delete first
        if overwrite and utils_api.validate_server_exist(server_name):
            delete_result = server_api.delete_server_data(server_name)
            if delete_result.get("status") == "error":
                return (
                    jsonify(
                        status="error",
                        message=f"Failed to delete existing server for overwrite: {delete_result['message']}",
                    ),
                    500,
                )

        # Proceed with installation
        result = server_install_config.install_new_server(server_name, server_version)

        if result.get("status") == "success":
            status_code = 201  # Created
            result["next_step_url"] = url_for(
                ".configure_properties_route", server_name=server_name, new_install=True
            )
            logger.info(f"API Install Server successful for '{server_name}'.")
        else:
            status_code = 500
            logger.error(
                f"API Install Server failed for '{server_name}': {result.get('message')}"
            )

    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Install Server '{server_name}': Input error. {e}")
    except BSMError as e:
        status_code = 500
        result = {"status": "error", "message": str(e)}
        logger.error(f"API Install Server '{server_name}': Configuration error. {e}")
    except Exception as e:
        status_code = 500
        result = {"status": "error", "message": "An unexpected error occurred."}
        logger.error(
            f"API Install Server '{server_name}': Unexpected error in route. {e}",
            exc_info=True,
        )

    return jsonify(result), status_code


# --- Route: Configure Server Properties Page ---
@server_install_config_bp.route(
    "/server/<string:server_name>/configure_properties", methods=["GET"]
)
@login_required
def configure_properties_route(server_name: str) -> Response:
    """Renders the page for configuring the server.properties file."""
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed configure properties for server '{server_name}'."
    )

    try:
        properties_response = server_install_config.get_server_properties_api(
            server_name
        )
        if properties_response.get("status") == "error":
            flash(
                f"Error loading properties: {properties_response.get('message', 'Unknown error')}",
                "error",
            )
            return redirect(url_for("main_routes.index"))

        return render_template(
            "configure_properties.html",
            server_name=server_name,
            properties=properties_response.get("properties", {}),
            new_install=request.args.get("new_install", "false").lower() == "true",
        )
    except Exception as e:
        flash("An unexpected error occurred while loading server properties.", "danger")
        logger.error(
            f"Unexpected error loading properties page for '{server_name}': {e}",
            exc_info=True,
        )
        return redirect(url_for("main_routes.index"))


# --- API Route: Configure Server Properties ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/properties", methods=["POST"]
)
@csrf.exempt
@auth_required
def configure_properties_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to update server.properties."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Configure properties request for '{server_name}' by user '{identity}'."
    )

    properties_data = request.get_json()
    if not isinstance(properties_data, dict):
        return (
            jsonify(status="error", message="Invalid or missing JSON object body."),
            400,
        )

    result: Dict[str, Any]
    status_code: int

    try:
        # API layer handles validation and modification
        result = server_install_config.modify_server_properties(
            server_name, properties_data
        )

        if result.get("status") == "success":
            status_code = 200
            logger.info(f"API Modify Properties successful for '{server_name}'.")
        else:
            status_code = 400  # Assume bad input if validation in API fails
            logger.warning(
                f"API Modify Properties failed for '{server_name}': {result.get('message')}"
            )

    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Modify Properties '{server_name}': Input error. {e}")
    except Exception as e:
        status_code = 500
        result = {"status": "error", "message": "An unexpected error occurred."}
        logger.error(
            f"API Modify Properties '{server_name}': Unexpected error in route. {e}",
            exc_info=True,
        )

    return jsonify(result), status_code


# --- API Route: Get Server Properties ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/read_properties", methods=["GET"]
)
@csrf.exempt
@auth_required
def get_server_properties_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to retrieve the parsed server.properties for a specific server."""
    result = server_install_config.get_server_properties_api(server_name)
    if result.get("status") == "success":
        return jsonify(result), 200
    if "not found" in result.get("message", "").lower():
        return jsonify(result), 404
    return jsonify(result), 500


# --- Route: Configure Allowlist Page ---
@server_install_config_bp.route(
    "/server/<string:server_name>/configure_allowlist", methods=["GET"]
)
@login_required
def configure_allowlist_route(server_name: str) -> Response:
    """Renders the page for configuring the server's allowlist."""
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed configure allowlist for server '{server_name}'."
    )

    try:
        result = server_install_config.get_server_allowlist_api(server_name)
        if result.get("status") == "error":
            flash(
                f"Error loading allowlist: {result.get('message', 'Unknown error')}",
                "error",
            )

        return render_template(
            "configure_allowlist.html",
            server_name=server_name,
            existing_players=result.get("players", []),
            new_install=request.args.get("new_install", "false").lower() == "true",
        )
    except Exception as e:
        flash("An unexpected error occurred loading the allowlist.", "error")
        logger.error(
            f"Unexpected error loading allowlist page for '{server_name}': {e}",
            exc_info=True,
        )
        return render_template(
            "configure_allowlist.html", server_name=server_name, existing_players=[]
        )


# --- API Route: Add Players to Allowlist ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/allowlist/add", methods=["POST"]
)
@csrf.exempt
@auth_required
def add_to_allowlist_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to add players to the server's allowlist."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Add to allowlist request for '{server_name}' by user '{identity}'."
    )

    data = request.get_json()
    if not data or not isinstance(data.get("players"), list):
        return (
            jsonify(status="error", message="Request must contain a 'players' list."),
            400,
        )

    new_players = [
        {"name": p, "ignoresPlayerLimit": data.get("ignoresPlayerLimit", False)}
        for p in data["players"]
    ]

    try:
        result = server_install_config.add_players_to_allowlist_api(
            server_name, new_players
        )
        if result.get("status") == "success":
            return jsonify(result), 200
        else:
            return jsonify(result), 500
    except BSMError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.error(
            f"API Add Allowlist '{server_name}': Unexpected error. {e}", exc_info=True
        )
        return (
            jsonify({"status": "error", "message": "An unexpected error occurred."}),
            500,
        )


# --- API Route: Get Allowlist ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/allowlist", methods=["GET"]
)
@csrf.exempt
@auth_required
def get_allowlist_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to retrieve the current allowlist for a server."""
    result = server_install_config.get_server_allowlist_api(server_name)
    if result.get("status") == "success":
        return (
            jsonify(
                {"status": "success", "existing_players": result.get("players", [])}
            ),
            200,
        )
    return jsonify(result), 500


# --- API Route: Remove Player from Allowlist ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/allowlist/remove",
    methods=["DELETE"],
)
@csrf.exempt
@auth_required
def remove_allowlist_players_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to remove multiple players from a server's allowlist."""
    try:
        data = request.get_json()
        if not data or "players" not in data or not isinstance(data["players"], list):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Request body must be a JSON object with a 'players' key containing a list of names.",
                    }
                ),
                400,  # Bad Request
            )

        player_names = data["players"]
        # Call the new function that accepts a list
        result = server_install_config.remove_players_from_allowlist(
            server_name, player_names
        )
        return jsonify(result), 200

    except BSMError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.error(
            f"API Bulk Remove Allowlist Players '{server_name}': Unexpected error. {e}",
            exc_info=True,
        )
        return (
            jsonify(
                {"status": "error", "message": "An unexpected server error occurred."}
            ),
            500,
        )


# --- Route: Configure Permissions Page ---
@server_install_config_bp.route(
    "/server/<string:server_name>/configure_permissions", methods=["GET"]
)
@login_required
def configure_permissions_route(server_name: str) -> Response:
    """
    Renders the page for configuring player permission levels.
    """
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed configure permissions for server '{server_name}'."
    )

    all_players: list = []
    permissions_map: dict = {}

    try:
        # --- STEP 1: Fetch ALL known players from the global player list ---
        logger.debug("Calling Player API to get all known players...")
        players_response = player_api.get_all_known_players_api()

        if players_response.get("status") == "success":
            all_players = players_response.get("players", [])
            logger.info(f"Loaded {len(all_players)} players from global player API.")
        else:
            flash(
                f"Warning: Could not load global player list: {players_response.get('message')}",
                "warning",
            )

        # --- STEP 2: Fetch permissions for server ---
        logger.debug(f"Calling Server API to get permissions for '{server_name}'...")
        permissions_response = server_install_config.get_server_permissions_api(
            server_name
        )
        server_permissions_list = permissions_response.get("data", {}).get(
            "permissions", []
        )

        # --- STEP 3: MERGE the two data sources ---
        permissions_map = {
            str(p.get("xuid")): str(p.get("permission_level"))
            for p in server_permissions_list
            if p.get("xuid")
        }
        logger.debug(
            f"Created permissions map with {len(permissions_map)} entries for '{server_name}'."
        )

        known_player_xuids = {str(p.get("xuid")) for p in all_players if p.get("xuid")}
        xuids_only_in_permissions = set(permissions_map.keys()) - known_player_xuids

        if xuids_only_in_permissions:
            logger.info(
                f"Found {len(xuids_only_in_permissions)} players in server permissions not in global list. Adding them."
            )
            for xuid in xuids_only_in_permissions:
                all_players.append({"xuid": xuid, "name": f"Unknown (XUID: {xuid})"})

        all_players.sort(key=lambda p: p.get("name", "").lower())

    except Exception as e:
        flash(
            "An unexpected error occurred while preparing the permissions page.",
            "danger",
        )
        logger.error(
            f"Failed to orchestrate permissions page for '{server_name}': {e}",
            exc_info=True,
        )
        all_players = []
        permissions_map = {}

    new_install = request.args.get("new_install", "false").lower() == "true"

    return render_template(
        "configure_permissions.html",
        server_name=server_name,
        players=all_players,
        permissions=permissions_map,
        new_install=new_install,
    )


# --- API Route: Configure Permissions ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/permissions", methods=["PUT"]
)
@csrf.exempt
@auth_required
def configure_permissions_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to update player permissions."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Configure permissions request for '{server_name}' by user '{identity}'."
    )

    data = request.get_json()
    if not isinstance(data, dict) or not isinstance(data.get("permissions"), dict):
        return (
            jsonify(
                status="error", message="Request must contain a 'permissions' object."
            ),
            400,
        )

    permissions_map = data["permissions"]
    errors = {}
    success_count = 0

    for xuid, level in permissions_map.items():
        try:
            # Call API for each player. The API layer handles validation.
            result = server_install_config.configure_player_permission(
                server_name, xuid, None, level
            )
            if result.get("status") == "success":
                success_count += 1
            else:
                errors[xuid] = result.get("message", "Unknown error")
        except BSMError as e:
            errors[xuid] = str(e)
        except Exception as e:
            logger.error(
                f"API Permissions Update '{server_name}': Unexpected error for XUID {xuid}. {e}",
                exc_info=True,
            )
            errors[xuid] = "An unexpected server error occurred."

    if not errors:
        return (
            jsonify(
                status="success",
                message=f"Permissions updated for {success_count} player(s).",
            ),
            200,
        )
    else:
        return (
            jsonify(
                status="error", message="One or more errors occurred.", errors=errors
            ),
            500,
        )


# --- API Route: Get Permissions Data ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/permissions_data", methods=["GET"]
)
@csrf.exempt
@auth_required
def get_server_permissions_data_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to retrieve player permission levels for a specific server."""
    result = server_install_config.get_server_permissions_api(server_name)
    if result.get("status") == "success":
        return jsonify(result), 200
    if "not found" in result.get("message", "").lower():
        return jsonify(result), 404
    return jsonify(result), 500


# --- Route: Configure Service Page ---
@server_install_config_bp.route(
    "/server/<string:server_name>/configure_service", methods=["GET"]
)
@login_required
def configure_service_route(server_name: str) -> Response:
    """Renders the page for configuring OS-specific service settings."""
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed configure service page for server '{server_name}'."
    )

    try:
        service_status = False  # system_api.get_service_status(server_name)
        # if service_status.get("status") == "error":
        #    flash(
        #        f"Could not get service status: {service_status.get('message')}",
        #        "warning",
        #    )

        template_data = {
            "server_name": server_name,
            "os": platform.system(),
            "new_install": request.args.get("new_install", "false").lower() == "true",
            "service_exists": False,  # service_status.get("exists", False),
            "autostart_enabled": False,  # service_status.get("autostart_enabled", False),
            "autoupdate_enabled": False,  # service_status.get("autoupdate_enabled", False),
        }
        return render_template("configure_service.html", **template_data)
    except Exception as e:
        flash("An unexpected error occurred loading service settings.", "danger")
        logger.error(
            f"Unexpected error loading service page for '{server_name}': {e}",
            exc_info=True,
        )
        return render_template(
            "configure_service.html",
            os=platform.system(),
            new_install=request.args.get("new_install", "false").lower() == "true",
        )


# --- API Route: Configure Service ---
@server_install_config_bp.route(
    "/api/server/<string:server_name>/service", methods=["POST"]
)
@csrf.exempt
@auth_required
def configure_service_api_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to configure OS-specific service settings.
    Accepts a JSON body with optional 'autoupdate' and 'autostart' booleans.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Configure service request for '{server_name}' by user '{identity}'."
    )
    current_os = platform.system()

    # --- Validate Input ---
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify(status="error", message="Invalid JSON body."), 400

    # Use .get() with a default of None to see if the key was provided at all
    autoupdate = data.get("autoupdate")
    autostart = data.get("autostart")

    if autoupdate is None and autostart is None:
        return (
            jsonify(status="error", message="No configuration options provided."),
            400,
        )

    try:
        # --- Action 1: Handle Autoupdate (Common to Windows & Linux) ---
        if autoupdate is not None:
            if not isinstance(autoupdate, bool):
                return (
                    jsonify(status="error", message="'autoupdate' must be a boolean."),
                    400,
                )

            logger.info(f"API: Setting autoupdate to {autoupdate} for '{server_name}'.")
            result = system_api.set_autoupdate(server_name, str(autoupdate))

            if result.get("status") != "success":
                # Fail fast: if this fails, don't proceed.
                return jsonify(result), 500

        # --- Action 2: Handle Autostart (Linux-specific) ---
        if autostart is not None:
            if not isinstance(autostart, bool):
                return (
                    jsonify(status="error", message="'autostart' must be a boolean."),
                    400,
                )

            if current_os == "Linux":
                logger.info(
                    f"API: Setting autostart to {autostart} for '{server_name}'."
                )
                result = system_api.create_systemd_service(server_name, autostart)

                if result.get("status") != "success":
                    return jsonify(result), 500
            else:
                # Explicitly inform client that autostart is not supported on this OS
                logger.warning(
                    f"API: 'autostart' parameter ignored for '{server_name}': unsupported OS ({current_os})."
                )

        # If we've reached this point, all requested operations were successful.
        return (
            jsonify(
                {"status": "success", "message": "Configuration applied successfully."}
            ),
            200,
        )

    except BSMError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.error(
            f"API Configure Service '{server_name}': Unexpected error. {e}",
            exc_info=True,
        )
        return (
            jsonify(
                {"status": "error", "message": "An unexpected server error occurred."}
            ),
            500,
        )
