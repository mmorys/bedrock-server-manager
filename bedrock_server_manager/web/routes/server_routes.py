# bedrock-server-manager/bedrock_server_manager/web/routes/server_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import os
import re
import platform
import logging
import json
from bedrock_server_manager import handlers
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.config.settings import EXPATH, app_name
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.web.routes.auth_routes import login_required

logger = logging.getLogger("bedrock_server_manager")

server_bp = Blueprint("server_routes", __name__)


@server_bp.route("/")
@login_required
def index():
    base_dir = get_base_dir()
    # Use the handler to get server status.
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)
    if status_response["status"] == "error":
        flash(f"Error getting server status: {status_response['message']}", "error")
        servers = []  # Provide an empty list so the template doesn't break
    else:
        servers = status_response["servers"]
    logger.debug(f"Rendering index.html with servers: {servers}")
    return render_template("index.html", servers=servers, app_name=app_name)


@server_bp.route("/manage_servers")
@login_required
def manage_server_route():
    base_dir = get_base_dir()
    # Use the handler to get server status.
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)
    if status_response["status"] == "error":
        flash(f"Error getting server status: {status_response['message']}", "error")
        servers = []  # Provide an empty list so the template doesn't break
    else:
        servers = status_response["servers"]
    logger.debug(f"Rendering manage_servers.html with servers: {servers}")
    return render_template("manage_servers.html", servers=servers, app_name=app_name)


@server_bp.route("/advanced_menu")
@login_required
def advanced_menu_route():
    base_dir = get_base_dir()
    # Use the handler to get server status.
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)
    if status_response["status"] == "error":
        flash(f"Error getting server status: {status_response['message']}", "error")
        servers = []  # Provide an empty list so the template doesn't break
    else:
        servers = status_response["servers"]
    logger.debug(f"Rendering advanced_menu.html with servers: {servers}")
    return render_template("advanced_menu.html", servers=servers, app_name=app_name)


@server_bp.route("/server/<server_name>/start", methods=["POST"])
@login_required
def start_server_route(server_name):
    """API endpoint to start a server."""
    base_dir = get_base_dir()
    logger.info(f"API request received to start server: {server_name}")
    response = handlers.start_server_handler(server_name, base_dir)

    status_code = 200 if response.get("status") == "success" else 500

    if status_code == 200:
        logger.info(f"Server '{server_name}' started successfully via API.")
    else:
        logger.error(
            f"API Error starting server '{server_name}': {response.get('message', 'Unknown error')}"
        )

    return jsonify(response), status_code


@server_bp.route("/server/<server_name>/stop", methods=["POST"])
@login_required
def stop_server_route(server_name):
    """API endpoint to stop a server."""
    base_dir = get_base_dir()
    logger.info(f"API request received to stop server: {server_name}")
    response = handlers.stop_server_handler(server_name, base_dir)

    status_code = 200 if response.get("status") == "success" else 500

    if status_code == 200:
        logger.info(f"Server '{server_name}' stopped successfully via API.")
    else:
        logger.error(
            f"API Error stopping server '{server_name}': {response.get('message', 'Unknown error')}"
        )

    return jsonify(response), status_code


@server_bp.route("/server/<server_name>/restart", methods=["POST"])
@login_required
def restart_server_route(server_name):
    """API endpoint to restart a server."""
    base_dir = get_base_dir()
    logger.info(f"API request received to restart server: {server_name}")
    response = handlers.restart_server_handler(server_name, base_dir)

    status_code = 200 if response.get("status") == "success" else 500

    if status_code == 200:
        logger.info(f"Server '{server_name}' restarted successfully via API.")
    else:
        logger.error(
            f"API Error restarting server '{server_name}': {response.get('message', 'Unknown error')}"
        )

    return jsonify(response), status_code


@server_bp.route("/server/<server_name>/send", methods=["POST"])
@login_required
def send_command_route(server_name):
    """API endpoint to send a command to a server."""
    base_dir = get_base_dir()
    data = request.get_json()

    if not data or not isinstance(data, dict):
        logger.warning(
            f"API send_command for {server_name}: Invalid or empty JSON body received."
        )
        return jsonify({"status": "error", "message": "Invalid JSON body."}), 400

    command = data.get("command")

    if not command:
        logger.warning(f"API send_command for {server_name}: Received empty 'command'.")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Request body must contain a non-empty 'command' field.",
                }
            ),
            400,
        )

    logger.info(f"API request received for {server_name}, command: {command}")
    result = handlers.send_command_handler(server_name, command, base_dir)

    status_code = 200 if result.get("status") == "success" else 500
    if status_code != 200:
        logger.error(
            f"API Error sending command to {server_name}: {result.get('message', 'Unknown error')}"
        )

    return jsonify(result), status_code


@server_bp.route("/server/<server_name>/update", methods=["POST"])
@login_required
def update_server_route(server_name):
    """API endpoint to update a server."""
    base_dir = get_base_dir()
    logger.info(f"API request received to update server: {server_name}")
    response = handlers.update_server_handler(server_name, base_dir=base_dir)

    status_code = 200 if response.get("status") == "success" else 500

    if status_code == 200:
        logger.info(f"Server '{server_name}' updated successfully via API.")
    else:
        logger.error(
            f"API Error updating server '{server_name}': {response.get('message', 'Unknown error')}"
        )

    return jsonify(response), status_code


@server_bp.route("/install", methods=["GET"])
@login_required
def install_server_route():
    logger.debug("Displaying install server page.")
    # Pass empty strings initially if needed by template value attributes
    return render_template(
        "install.html", server_name="", server_version="", app_name=app_name
    )


@server_bp.route("/api/server/install", methods=["POST"])
@login_required
def install_server_api_route():
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    data = request.get_json()

    if not data:
        logger.warning(f"API Install Server request: Empty or invalid JSON body.")
        return (
            jsonify({"status": "error", "message": "Invalid or empty JSON body."}),
            400,
        )

    server_name = data.get("server_name")
    server_version = data.get("server_version")
    overwrite = data.get("overwrite", False)

    # --- Basic Input Validation ---
    if not server_name or not server_version:
        logger.warning(
            f"API Install Server request: Missing server_name or server_version."
        )
        return (
            jsonify(
                {"status": "error", "message": "Missing server_name or server_version."}
            ),
            400,
        )

    # --- Server Name Format Validation ---
    if ";" in server_name:  # Simple semicolon check from old route
        logger.warning(
            f"API Install Server: Invalid server name format (contains ';'): {server_name}"
        )
        return (
            jsonify(
                {"status": "error", "message": "Server name cannot contain semicolons."}
            ),
            400,
        )
    # Call specific format validation handler
    validation_result = handlers.validate_server_name_format_handler(server_name)
    if validation_result["status"] == "error":
        logger.warning(
            f"API Install Server: Server name validation failed: {validation_result['message']}"
        )
        return jsonify(validation_result), 400  # Return validation error

    logger.info(
        f"API request received to install server: {server_name}, Version: {server_version}, Overwrite: {overwrite}"
    )

    # --- Check if Server Exists ---
    server_dir = os.path.join(base_dir, server_name)
    server_exists = os.path.exists(server_dir)

    # --- Handle Confirmation / Overwrite Logic ---
    if server_exists and not overwrite:
        logger.info(
            f"Server '{server_name}' already exists. Requesting confirmation from client."
        )
        return (
            jsonify(
                {
                    "status": "confirm_needed",
                    "message": f"Server directory '{server_name}' already exists. Do you want to delete existing data and reinstall?",
                    "server_name": server_name,
                    "server_version": server_version,
                }
            ),
            200,
        )

    # --- Proceed with Installation (Either new or overwrite confirmed) ---
    result = None
    status_code = 500  # Default to error

    try:
        if server_exists and overwrite:
            # Delete existing data first
            logger.info(
                f"Overwrite confirmed for '{server_name}'. Deleting existing data..."
            )
            delete_result = handlers.delete_server_data_handler(
                server_name, base_dir, config_dir
            )
            if delete_result["status"] == "error":
                logger.error(
                    f"API Install Server: Failed to delete existing data for '{server_name}': {delete_result['message']}"
                )
                # Return the delete error
                return jsonify(delete_result), 500

        # Perform the installation (for new or after successful delete)
        logger.info(f"Proceeding with installation for '{server_name}'...")
        install_result = handlers.install_new_server_handler(
            server_name, server_version, base_dir, config_dir
        )

        # Check install result status
        if install_result.get("status") == "success":
            logger.info(f"Server '{server_name}' installed successfully via API.")
            result = install_result
            result["next_step_url"] = url_for(
                "server_routes.configure_properties_route",
                server_name=server_name,
                new_install=True,
            )
            status_code = 200
        else:
            logger.error(
                f"API Install Server: Installation handler failed for '{server_name}': {install_result.get('message')}"
            )
            result = install_result
            status_code = 500

    except Exception as e:
        logger.exception(
            f"Unexpected error during server installation process for '{server_name}': {e}"
        )
        result = {
            "status": "error",
            "message": f"An unexpected error occurred during installation: {e}",
        }
        status_code = 500

    logger.debug(f"Returning JSON for install API: {result}")

    return jsonify(result), status_code


@server_bp.route("/server/<server_name>/delete", methods=["DELETE"])
@login_required
def delete_server_route(server_name):
    """API endpoint to delete a server."""
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    logger.info(f"API request received to delete server: {server_name}")

    # Call the handler to delete the server data
    result = handlers.delete_server_data_handler(server_name, base_dir, config_dir)

    # Determine appropriate status code
    status_code = 200 if result.get("status") == "success" else 500

    if status_code == 200:
        logger.info(f"Server '{server_name}' deleted successfully.")
    else:
        logger.error(
            f"API Error deleting server '{server_name}': {result.get('message', 'Unknown error')}"
        )

    # Return JSON response
    return jsonify(result), status_code


@server_bp.route("/server/<server_name>/configure_properties", methods=["GET"])
@login_required
def configure_properties_route(server_name):
    base_dir = get_base_dir()
    server_dir = os.path.join(base_dir, server_name)
    server_properties_path = os.path.join(server_dir, "server.properties")

    if not os.path.exists(server_properties_path):
        flash(f"server.properties not found for server: {server_name}", "error")
        logger.error(f"server.properties not found for server: {server_name}")
        return redirect(url_for("server_routes.advanced_menu_route"))

    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"
    logger.debug(
        f"Displaying configure properties page for {server_name}, new_install: {new_install}"
    )

    properties_response = handlers.read_server_properties_handler(server_name, base_dir)
    if properties_response["status"] == "error":
        flash(f"Error loading properties: {properties_response['message']}", "error")
        logger.error(
            f"Error loading properties for {server_name}: {properties_response['message']}"
        )
        return redirect(url_for("server_routes.advanced_menu_route"))

    return render_template(
        "configure_properties.html",  # Ensure this template exists and is updated next
        server_name=server_name,
        properties=properties_response.get("properties", {}),  # Use .get with default
        new_install=new_install,
        app_name=app_name,
    )


@server_bp.route("/api/server/<server_name>/properties", methods=["POST"])
@login_required
def configure_properties_api_route(server_name):
    """API endpoint to update server properties."""
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")  # Get config dir early
    properties_data = request.get_json()

    if not properties_data or not isinstance(properties_data, dict):
        logger.warning(
            f"API Configure Properties for {server_name}: Empty or invalid JSON body."
        )
        return (
            jsonify({"status": "error", "message": "Invalid or empty JSON body."}),
            400,
        )

    logger.info(
        f"API request received to configure properties for server: {server_name}"
    )
    logger.debug(f"Properties data received: {properties_data}")

    # Define allowed keys and maybe default values/types for stricter validation
    allowed_keys = [
        "server-name",
        "level-name",
        "gamemode",
        "difficulty",
        "allow-cheats",
        "server-port",
        "server-portv6",
        "enable-lan-visibility",
        "allow-list",
        "max-players",
        "default-player-permission-level",
        "view-distance",
        "tick-distance",
        "level-seed",
        "online-mode",
        "texturepack-required",
        # Add any other properties your form allows editing
    ]

    properties_to_update = {}
    validation_errors = {}  # Dictionary to hold field-specific errors

    # Iterate through data received FROM THE API request
    for key, value in properties_data.items():
        if key not in allowed_keys:
            logger.warning(
                f"API Configure Properties: Received unexpected key '{key}'. Ignoring."
            )
            continue  # Skip keys not explicitly allowed/handled by the form

        # --- Validation ---
        # Ensure value is a string before validation (JSON might send numbers/booleans)
        value_str = str(value)

        # Specific cleaning (like level-name)
        if key == "level-name":
            original_value = value_str
            value_str = re.sub(
                r'[<>:"/\\|?* ]+', "_", original_value.strip()
            )  # Replace invalid chars + spaces with _
            if value_str != original_value:
                logger.info(
                    f"Cleaned 'level-name' from '{original_value}' to '{value_str}'"
                )

        # Call your existing validation handler
        validation_response = handlers.validate_property_value_handler(key, value_str)
        if validation_response["status"] == "error":
            logger.warning(
                f"API Validation error for {key}='{value_str}': {validation_response['message']}"
            )
            validation_errors[key] = validation_response["message"]
            # Don't return immediately - collect all errors
        else:
            # Only add valid properties to the update dict
            properties_to_update[key] = value_str

    # --- Check if any validation errors occurred ---
    if validation_errors:
        logger.error(
            f"API Configure Properties validation failed for {server_name}: {validation_errors}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Validation failed for one or more properties.",
                    "errors": validation_errors,  # Send specific errors back to the client
                }
            ),
            400,
        )  # Bad Request status code for validation errors

    # --- If validation passed, attempt to modify properties ---
    if not properties_to_update:
        logger.warning(
            f"API Configure Properties for {server_name}: No valid properties were provided for update."
        )
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "No valid properties provided to update.",
                }
            ),
            200,
        )  # Or maybe 400?

    logger.debug(
        f"Calling modify_server_properties_handler with: {properties_to_update}"
    )
    modify_response = handlers.modify_server_properties_handler(
        server_name, properties_to_update, base_dir
    )

    if modify_response["status"] == "error":
        logger.error(
            f"API Error updating server properties for {server_name}: {modify_response['message']}"
        )
        # Return 500 Internal Server Error if the handler itself fails
        return jsonify(modify_response), 500

    # --- Return final success response ---
    logger.info(f"Server properties for '{server_name}' updated successfully via API!")
    # Ensure message exists
    if "message" not in modify_response:
        modify_response["message"] = (
            f"Server properties for '{server_name}' updated successfully!"
        )

    return jsonify(modify_response), 200


@server_bp.route("/server/<server_name>/configure_allowlist", methods=["GET"])
@login_required
def configure_allowlist_route(server_name):
    base_dir = get_base_dir()
    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"
    logger.debug(
        f"Displaying configure allowlist page for server: {server_name}, new_install: {new_install}"
    )

    # --- Call handler to get existing players ---
    result = handlers.configure_allowlist_handler(server_name, base_dir)
    existing_players = []  # Default
    if result["status"] == "error":
        flash(f"Error loading current allowlist: {result['message']}", "error")
        logger.error(f"Error loading allowlist for {server_name}: {result['message']}")
    else:
        existing_players = result.get("existing_players", [])  # Get list of dicts

    return render_template(
        "configure_allowlist.html",
        server_name=server_name,
        existing_players=existing_players,  # Pass the list of player dicts
        new_install=new_install,
        app_name=app_name,
    )


@server_bp.route("/api/server/<server_name>/allowlist/add", methods=["POST"])
@login_required
def add_allowlist_players_api_route(server_name):
    """API endpoint to ADD players to the server allowlist."""
    base_dir = get_base_dir()
    data = request.get_json()

    if data is None:
        logger.warning(
            f"API Add Allowlist request for {server_name}: Empty or invalid JSON body received."
        )
        return (
            jsonify({"status": "error", "message": "Invalid or empty JSON body."}),
            400,
        )

    players_to_add_names = data.get("players")  # List of names from JSON
    ignore_limit = data.get("ignoresPlayerLimit", False)

    if players_to_add_names is None or not isinstance(players_to_add_names, list):
        logger.warning(
            f"API Add Allowlist request for {server_name}: Missing or invalid 'players' list in JSON body."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Request body must contain a 'players' list.",
                }
            ),
            400,
        )
    if not isinstance(ignore_limit, bool):
        logger.warning(
            f"API Add Allowlist request for {server_name}: Invalid 'ignoresPlayerLimit' value."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "'ignoresPlayerLimit' must be true or false.",
                }
            ),
            400,
        )

    # Filter out empty names
    players_to_add_names = [
        name.strip()
        for name in players_to_add_names
        if isinstance(name, str) and name.strip()
    ]

    if not players_to_add_names:
        logger.warning(
            f"API Add Allowlist request for {server_name}: No valid player names provided to add."
        )
        return (
            jsonify({"status": "error", "message": "No player names provided to add."}),
            400,
        )

    logger.info(
        f"API request received to ADD players to allowlist for server: {server_name}. Players: {players_to_add_names}"
    )

    new_players_data_for_handler = [
        {"name": name, "ignoresPlayerLimit": ignore_limit}
        for name in players_to_add_names
    ]
    logger.debug(
        f"Data formatted for configure_allowlist_handler: {new_players_data_for_handler}"
    )

    result = handlers.configure_allowlist_handler(
        server_name, base_dir, new_players_data=new_players_data_for_handler
    )

    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        logger.info(
            f"Players processed for allowlist add for '{server_name}' successfully via API. Added: {result.get('added_players', [])}"
        )
    else:
        error_message = (
            result.get("message", "Unknown error adding players")
            if result
            else "Add players handler failed unexpectedly"
        )
        logger.error(f"API Add Allowlist failed for {server_name}: {error_message}")
        if not result:
            result = {
                "status": "error",
                "message": "Add players handler failed unexpectedly",
            }
        elif "status" not in result:
            result["status"] = "error"

    # Return the result from the handler
    return jsonify(result), status_code


@server_bp.route("/api/server/<server_name>/allowlist", methods=["GET"])
@login_required
def get_allowlist_api_route(server_name):
    """API endpoint to retrieve the current server allowlist."""
    base_dir = get_base_dir()
    logger.debug(f"API GET request for allowlist for server: {server_name}")
    # Call the handler with new_players_data=None to read existing
    result = handlers.configure_allowlist_handler(
        server_name, base_dir, new_players_data=None
    )
    if result.get("status") != "success":
        logger.error(
            f"Failed to retrieve allowlist for API GET: {result.get('message')}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": result.get("message", "Failed to load allowlist"),
                    "existing_players": [],
                }
            ),
            500,
        )
    else:
        response_data = {
            "status": "success",
            "existing_players": result.get(
                "existing_players", []
            ),  # Use the key returned by the handler
        }
        return jsonify(response_data), 200


@server_bp.route("/server/<server_name>/configure_permissions", methods=["GET"])
@login_required
def configure_permissions_route(server_name):
    base_dir = get_base_dir()
    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"
    logger.debug(
        f"Displaying configure permissions page for {server_name}, new_install: {new_install}"
    )

    # Get known players (e.g., from players.json or allowlist.json)
    # Using get_players_from_json_handler as before
    players_response = handlers.get_players_from_json_handler()
    players = []  # Default
    if players_response["status"] == "error":
        flash(
            f"Warning: Could not load player names: {players_response['message']}. Only XUIDs may be shown.",
            "warning",
        )
        logger.warning(
            f"Error loading player data for permissions page: {players_response['message']}"
        )
    else:
        players = players_response.get("players", [])
        logger.debug(f"Loaded players for permissions configuration: {players}")

    # Get current permissions from permissions.json
    permissions = {}  # Default
    try:
        server_dir = os.path.join(base_dir, server_name)
        permissions_file = os.path.join(server_dir, "permissions.json")
        if os.path.exists(permissions_file):
            with open(permissions_file, "r") as f:
                permissions_data = json.load(f)  # Should be a list of dicts
                # Convert list of dicts to map {xuid: permission} for easier template lookup
                for player_entry in permissions_data:
                    if "xuid" in player_entry and "permission" in player_entry:
                        permissions[player_entry["xuid"]] = player_entry["permission"]
            logger.debug(f"Loaded existing permissions map: {permissions}")
        else:
            logger.debug(
                f"permissions.json not found for {server_name}. Will use defaults."
            )

    except (OSError, json.JSONDecodeError) as e:
        flash(f"Error reading existing permissions.json: {e}", "error")
        logger.error(f"Error reading permissions.json for {server_name}: {e}")
        # Proceed with empty permissions map, defaults will apply in template

    # Ensure players list contains entries for everyone in the permissions map, even if name unknown
    current_player_xuids = {p.get("xuid") for p in players if p.get("xuid")}
    for xuid in permissions:
        if xuid not in current_player_xuids:
            players.append(
                {"xuid": xuid, "name": f"Unknown (XUID: {xuid})"}
            )  # Add placeholder entry
            logger.debug(
                f"Added placeholder for XUID {xuid} found only in permissions.json"
            )

    return render_template(
        "configure_permissions.html",  # Ensure this template exists and is updated next
        server_name=server_name,
        players=players,  # List of player dicts {'name': ..., 'xuid': ...}
        permissions=permissions,  # Dict mapping {xuid: permission_level}
        new_install=new_install,
        app_name=app_name,
    )


@server_bp.route("/api/server/<server_name>/permissions", methods=["PUT"])
@login_required
def configure_permissions_api_route(server_name):
    """API endpoint to update permissions by applying changes for each player."""
    base_dir = get_base_dir()
    data = request.get_json()

    if not data or not isinstance(data, dict) or "permissions" not in data:
        logger.warning(
            f"API Configure Permissions for {server_name}: Invalid or missing 'permissions' key in JSON body."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Request body must contain a 'permissions' object.",
                }
            ),
            400,
        )

    permissions_map = data.get("permissions")
    if not isinstance(permissions_map, dict):
        logger.warning(
            f"API Configure Permissions for {server_name}: 'permissions' value is not an object."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "'permissions' value must be an object mapping XUIDs to permission levels.",
                }
            ),
            400,
        )

    logger.info(
        f"API request received to configure permissions for server: {server_name}"
    )
    logger.debug(f"Permissions map received: {permissions_map}")

    # --- Validation ---
    valid_levels = ("visitor", "member", "operator")
    validation_errors = {}
    players_to_process = {}  # Store validated data {xuid: level}
    for xuid, level in permissions_map.items():
        if not isinstance(level, str) or level.lower() not in valid_levels:
            validation_errors[xuid] = (
                f"Invalid permission level '{level}'. Must be one of {valid_levels}."
            )
        else:
            players_to_process[xuid] = level.lower()

    if validation_errors:
        logger.error(
            f"API Configure Permissions validation failed for {server_name}: {validation_errors}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Validation failed for one or more permission levels.",
                    "errors": validation_errors,
                }
            ),
            400,
        )

    # --- Get Player Names (needed for existing handler) ---
    # It's inefficient to do this here AND in the GET route, but necessary
    # if the single-player handler requires the name.
    players_response = handlers.get_players_from_json_handler()
    player_name_map = {}  # Map xuid to name
    if players_response["status"] == "success":
        player_name_map = {
            player.get("xuid"): player.get(
                "name", f"Unknown (XUID: {player.get('xuid')})"
            )
            for player in players_response.get("players", [])
            if player.get("xuid")
        }
    else:
        logger.warning(
            f"Could not load player names for permission update: {players_response.get('message')}. Using placeholders."
        )

    # --- Loop and call existing handler for each player ---
    all_success = True
    handler_errors = {}  # Store errors from the handler calls
    processed_count = 0

    for xuid, level in players_to_process.items():
        player_name = player_name_map.get(
            xuid, f"Unknown (XUID: {xuid})"
        )  # Get name or use placeholder
        logger.debug(
            f"Calling configure_player_permission_handler for {player_name} ({xuid}) -> {level}"
        )

        # Call the existing handler for each player
        result = handlers.configure_player_permission_handler(
            server_name,
            xuid,
            player_name,
            level,
            base_dir,
            # Pass config_dir if your handler uses it, otherwise remove
            # config_dir=settings.get("CONFIG_DIR")
        )
        processed_count += 1

        if result.get("status") != "success":
            all_success = False
            handler_errors[xuid] = result.get("message", "Unknown handler error")
            logger.error(
                f"Error configuring permission for {xuid}: {handler_errors[xuid]}"
            )
            # Decide whether to stop on first error or continue processing others
            # Let's continue processing others for now

    # --- Determine final response based on handler results ---
    if all_success:
        logger.info(
            f"Permissions updated successfully via API for {server_name} ({processed_count} players processed)."
        )
        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Permissions updated successfully for {processed_count} players.",
                }
            ),
            200,
        )
    else:
        logger.error(
            f"Errors occurred during permission configuration for {server_name}: {handler_errors}"
        )
        # Return a summary error, including specific errors if needed
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "One or more errors occurred while setting permissions.",
                    "errors": handler_errors,  # Map of xuid: error message
                }
            ),
            500,
        )  # Internal Server Error because the handler failed


@server_bp.route(
    "/server/<server_name>/configure_service", methods=["GET"]
)  # REMOVED POST
@login_required
def configure_service_route(server_name):
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"
    current_os = platform.system()

    logger.debug(
        f"Displaying configure service page for {server_name}, OS: {current_os}, new_install: {new_install}"
    )

    template_data = {
        "server_name": server_name,
        "os": current_os,
        "new_install": new_install,
        "app_name": app_name,
        "autoupdate": False,
        "autostart": False,
    }

    if current_os == "Linux":
        logger.debug("Rendering configure_service.html for Linux (defaults shown)")

    elif current_os == "Windows":
        autoupdate_value = server_base.manage_server_config(
            server_name, "autoupdate", "read", config_dir=config_dir
        )

        template_data["autoupdate"] = (
            autoupdate_value == "true" if autoupdate_value else False
        )
        logger.debug(
            f"Rendering configure_service.html for Windows, autoupdate: {template_data['autoupdate']}"
        )

    else:
        flash("Unsupported operating system for service configuration.", "warning")
        logger.warning(
            f"Rendering configure_service page but OS is unsupported: {current_os}"
        )

    return render_template("configure_service.html", **template_data)


@server_bp.route("/api/server/<server_name>/service", methods=["POST"])
@login_required
def configure_service_api_route(server_name):
    """API endpoint to configure service settings (systemd or windows autoupdate)."""
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    data = request.get_json()
    current_os = platform.system()

    if data is None:
        logger.warning(
            f"API Configure Service request for {server_name}: Empty or invalid JSON body."
        )
        return (
            jsonify({"status": "error", "message": "Invalid or empty JSON body."}),
            400,
        )

    logger.info(
        f"API request received to configure service for server: {server_name} on OS: {current_os}"
    )
    logger.debug(f"Service config data received: {data}")

    result = {"status": "error", "message": "Unsupported operating system"}
    status_code = 501

    if current_os == "Linux":
        autoupdate = data.get("autoupdate", False)
        autostart = data.get("autostart", False)
        if not isinstance(autoupdate, bool) or not isinstance(autostart, bool):
            logger.warning(
                f"API Configure Service (Linux) for {server_name}: Invalid boolean value for autoupdate/autostart."
            )
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "'autoupdate' and 'autostart' must be true or false.",
                    }
                ),
                400,
            )

        logger.info(
            f"Calling create_systemd_service_handler for {server_name} (Update={autoupdate}, Start={autostart})"
        )
        result = handlers.create_systemd_service_handler(
            server_name, base_dir, autoupdate, autostart
        )
        status_code = 200 if result and result.get("status") == "success" else 500

    elif current_os == "Windows":
        autoupdate = data.get("autoupdate", False)
        if not isinstance(autoupdate, bool):
            logger.warning(
                f"API Configure Service (Windows) for {server_name}: Invalid boolean value for autoupdate."
            )
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "'autoupdate' must be true or false.",
                    }
                ),
                400,
            )

        logger.info(
            f"Calling set_windows_autoupdate_handler for {server_name} (Update={autoupdate})"
        )
        result = handlers.set_windows_autoupdate_handler(
            server_name, "true" if autoupdate else "false", config_dir
        )
        status_code = 200 if result and result.get("status") == "success" else 500
    else:
        logger.error(f"API Configure Service called on unsupported OS: {current_os}")

    # Log final result
    if status_code == 200:
        logger.info(
            f"Service settings for '{server_name}' updated successfully via API."
        )
    else:
        error_message = (
            result.get("message", "Unknown service configuration error")
            if result
            else "Service configuration handler failed unexpectedly"
        )
        logger.error(
            f"API Configure Service failed for {server_name} on {current_os}: {error_message}"
        )
        if not result:
            result = {
                "status": "error",
                "message": "Service configuration handler failed unexpectedly",
            }
        elif "status" not in result:
            result["status"] = "error"

    return jsonify(result), status_code


@server_bp.route("/server/<server_name>/backup", methods=["GET"])
@login_required
def backup_menu_route(server_name):
    return render_template(
        "backup_menu.html", server_name=server_name, app_name=app_name
    )


@server_bp.route("/server/<server_name>/backup/config", methods=["GET"])
@login_required
def backup_config_select_route(server_name):
    return render_template(
        "backup_config_options.html", server_name=server_name, app_name=app_name
    )


@server_bp.route("/server/<server_name>/backup/action", methods=["POST"])
@login_required
def backup_action_route(server_name):
    """API endpoint to trigger a server backup."""
    base_dir = get_base_dir()
    data = request.get_json()  # Expect JSON data

    if not data:
        logger.warning(
            f"API Backup request for {server_name}: Empty JSON body received."
        )
        return jsonify({"status": "error", "message": "Invalid JSON body."}), 400

    backup_type = data.get("backup_type")  # "world", "config", or "all"
    file_to_backup = data.get("file_to_backup")  # Optional, only for type "config"

    if not backup_type:
        logger.warning(
            f"API Backup request for {server_name}: Missing 'backup_type' in JSON body."
        )
        return (
            jsonify(
                {"status": "error", "message": "Missing 'backup_type' in request body."}
            ),
            400,
        )

    # Validate config backup request
    if backup_type == "config" and not file_to_backup:
        logger.warning(
            f"API Backup request for {server_name}: Missing 'file_to_backup' for config backup type."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Missing 'file_to_backup' for config backup type.",
                }
            ),
            400,
        )

    logger.info(
        f"API request received to perform backup for server: {server_name}, type: {backup_type}, file: {file_to_backup or 'N/A'}"
    )

    result = None
    if backup_type == "world":
        result = handlers.backup_world_handler(server_name, base_dir)
    elif backup_type == "config":
        result = handlers.backup_config_file_handler(
            server_name, file_to_backup, base_dir
        )
    elif backup_type == "all":
        result = handlers.backup_all_handler(server_name, base_dir)
    else:
        logger.error(
            f"API Backup request for {server_name}: Invalid backup_type specified: {backup_type}"
        )
        return (
            jsonify({"status": "error", "message": "Invalid backup type specified."}),
            400,
        )

    # Determine status code - backups might take time, so 202 Accepted could also be suitable
    # For now, let's use 200 on success reported by handler, 500 on error.
    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        logger.info(
            f"Backup API request for {server_name} (type: {backup_type}) completed successfully according to handler."
        )
    else:
        error_message = (
            result.get("message", "Unknown backup error")
            if result
            else "Backup handler failed unexpectedly"
        )
        logger.error(
            f"API Backup failed for {server_name} (type: {backup_type}): {error_message}"
        )
        # Ensure result is a dict even if handler failed badly
        if not result:
            result = {
                "status": "error",
                "message": "Backup handler failed unexpectedly",
            }
        elif "status" not in result:
            result["status"] = "error"  # Ensure status is set

    # Return JSON result from the handler
    return jsonify(result), status_code


@server_bp.route("/server/<server_name>/restore", methods=["GET"])
@login_required
def restore_menu_route(server_name):
    """Displays the restore menu."""
    logger.info(f"Displaying restore menu for server: {server_name}")
    return render_template(
        "restore_menu.html", server_name=server_name, app_name=app_name
    )


@server_bp.route("/server/<server_name>/restore/action", methods=["POST"])
@login_required
def restore_action_route(server_name):
    """API endpoint to trigger a server restoration from a specific backup."""
    base_dir = get_base_dir()
    data = request.get_json()  # Expect JSON data

    if not data:
        logger.warning(
            f"API Restore request for {server_name}: Empty JSON body received."
        )
        return jsonify({"status": "error", "message": "Invalid JSON body."}), 400

    backup_file = data.get("backup_file")
    restore_type = data.get("restore_type")  # "world" or "config"

    if not backup_file or not restore_type:
        logger.warning(
            f"API Restore request for {server_name}: Missing 'backup_file' or 'restore_type' in JSON body."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Missing 'backup_file' or 'restore_type' in request body.",
                }
            ),
            400,
        )

    logger.info(
        f"API request received to restore server: {server_name}, type: {restore_type}, file: {backup_file}"
    )

    result = None
    if restore_type == "world":
        result = handlers.restore_world_handler(server_name, backup_file, base_dir)
    elif restore_type == "config":

        result = handlers.restore_config_file_handler(
            server_name, backup_file, base_dir
        )

    else:
        logger.error(
            f"API Restore request for {server_name}: Invalid restore_type specified: {restore_type}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Invalid restore type specified (must be 'world' or 'config').",
                }
            ),
            400,
        )

    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        logger.info(
            f"Restore API request for {server_name} (type: {restore_type}, file: {backup_file}) completed successfully according to handler."
        )
    else:
        error_message = (
            result.get("message", "Unknown restore error")
            if result
            else "Restore handler failed unexpectedly"
        )
        logger.error(
            f"API Restore failed for {server_name} (type: {restore_type}, file: {backup_file}): {error_message}"
        )
        # Ensure result is a dict even if handler failed badly
        if not result:
            result = {
                "status": "error",
                "message": "Restore handler failed unexpectedly",
            }
        elif "status" not in result:
            result["status"] = "error"  # Ensure status is set

    return jsonify(result), status_code


@server_bp.route("/server/<server_name>/restore/select", methods=["POST"])
@login_required
def restore_select_backup_route(server_name):
    """Displays the list of available backups for the selected type (world or config)."""
    base_dir = get_base_dir()
    restore_type = request.form.get("restore_type")

    if not restore_type or restore_type not in ["world", "config"]:
        flash("Invalid restore type selected.", "error")
        logger.warning(
            f"Restore selection request for {server_name} with invalid type: {restore_type}"
        )
        # Redirect back to the menu where they came from
        return redirect(
            url_for("server_routes.restore_menu_route", server_name=server_name)
        )

    logger.info(
        f"Listing backups for restore type '{restore_type}' for server: {server_name}"
    )

    # List backups for 'world' or 'config'
    list_response = handlers.list_backups_handler(server_name, restore_type, base_dir)

    if list_response["status"] == "error":
        flash(f"Error listing backups: {list_response['message']}", "error")
        logger.error(
            f"Error listing backups for {server_name} ({restore_type}): {list_response['message']}"
        )
        # Redirect back to the menu
        return redirect(
            url_for("server_routes.restore_menu_route", server_name=server_name)
        )

    # Render the selection page
    return render_template(
        "restore_select_backup.html",
        server_name=server_name,
        restore_type=restore_type,
        backups=list_response.get("backups", []),
        app_name=app_name,
    )


@server_bp.route("/server/<server_name>/restore/all", methods=["POST"])
@login_required
def restore_all_api_route(server_name):
    """API endpoint to trigger restoring all files for a server."""
    base_dir = get_base_dir()
    logger.info(f"API request received to restore all files for server: {server_name}")

    # Call the handler directly
    result = handlers.restore_all_handler(server_name, base_dir)

    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        logger.info(
            f"Restore All API request for {server_name} completed successfully."
        )
    else:
        error_message = (
            result.get("message", "Unknown restore error")
            if result
            else "Restore All handler failed unexpectedly"
        )
        logger.error(f"API Restore All failed for {server_name}: {error_message}")
        if not result:
            result = {
                "status": "error",
                "message": "Restore All handler failed unexpectedly",
            }
        elif "status" not in result:
            result["status"] = "error"

    return jsonify(result), status_code


@server_bp.route("/install_content")
@login_required
def install_content_menu_route():
    base_dir = get_base_dir()
    # Use the handler to get server status.
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)
    if status_response["status"] == "error":
        flash(f"Error getting server status: {status_response['message']}", "error")
        servers = []  # Provide an empty list so the template doesn't break
    else:
        servers = status_response["servers"]
    logger.debug("Rendering install_content.html")
    return render_template("install_content.html", servers=servers, app_name=app_name)


@server_bp.route("/server/<server_name>/install_world")
@login_required
def install_world_route(server_name):
    base_dir = get_base_dir()
    content_dir = os.path.join(settings.get("CONTENT_DIR"), "worlds")
    logger.info(f"Displaying world selection page for server: {server_name}")
    result = handlers.list_content_files_handler(content_dir, ["mcworld"])
    if result["status"] == "error":
        flash(result["message"], "error")
        logger.error(f"Error listing world files: {result['message']}")
        world_files = []
    else:
        world_files = result.get("files", [])
        logger.debug(f"Found world files: {world_files}")
    return render_template(
        "select_world.html",
        server_name=server_name,
        world_files=world_files,
        app_name=app_name,
    )


@server_bp.route("/api/server/<server_name>/world/install", methods=["POST"])
@login_required
def install_world_api_route(server_name):
    """API endpoint to install a world from an .mcworld file."""
    base_dir = get_base_dir()
    data = request.get_json()

    if not data:
        logger.warning(
            f"API Install World request for {server_name}: Empty JSON body received."
        )
        return jsonify({"status": "error", "message": "Invalid JSON body."}), 400

    selected_file = data.get("filename")  # Expect 'filename' in JSON

    if not selected_file:
        logger.warning(
            f"API Install World request for {server_name}: Missing 'filename' in JSON body."
        )
        return (
            jsonify(
                {"status": "error", "message": "Missing 'filename' in request body."}
            ),
            400,
        )

    logger.info(
        f"API request received to install world '{selected_file}' for server: {server_name}"
    )

    result = handlers.extract_world_handler(server_name, selected_file, base_dir)

    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        logger.info(
            f"World '{selected_file}' installed successfully for {server_name} via API."
        )
    else:
        error_message = (
            result.get("message", "Unknown world extraction error")
            if result
            else "World extraction handler failed unexpectedly"
        )
        logger.error(
            f"API Install World failed for {server_name} (file: {selected_file}): {error_message}"
        )
        if not result:
            result = {
                "status": "error",
                "message": "World extraction handler failed unexpectedly",
            }
        elif "status" not in result:
            result["status"] = "error"

    return jsonify(result), status_code


@server_bp.route("/server/<server_name>/install_addon")
@login_required
def install_addon_route(server_name):
    base_dir = get_base_dir()
    content_dir = os.path.join(settings.get("CONTENT_DIR"), "addons")
    # --- Keep ONLY the GET request logic ---
    logger.info(f"Displaying addon selection page for server: {server_name}")
    result = handlers.list_content_files_handler(content_dir, ["mcaddon", "mcpack"])
    if result["status"] == "error":
        flash(result["message"], "error")
        logger.error(f"Error listing addon files: {result['message']}")
        addon_files = []
    else:
        addon_files = result.get("files", [])
        logger.debug(f"Found addon files: {addon_files}")
    return render_template(
        "select_addon.html",
        server_name=server_name,
        addon_files=addon_files,
        app_name=app_name,
    )


@server_bp.route("/api/server/<server_name>/addon/install", methods=["POST"])
@login_required
def install_addon_api_route(server_name):
    """API endpoint to install an addon (.mcaddon, .mcpack)"""
    base_dir = get_base_dir()
    data = request.get_json()

    if not data:
        logger.warning(
            f"API Install Addon request for {server_name}: Empty JSON body received."
        )
        return jsonify({"status": "error", "message": "Invalid JSON body."}), 400

    selected_file = data.get("filename")

    if not selected_file:
        logger.warning(
            f"API Install Addon request for {server_name}: Missing 'filename' in JSON body."
        )
        return (
            jsonify(
                {"status": "error", "message": "Missing 'filename' in request body."}
            ),
            400,
        )

    logger.info(
        f"API request received to install addon '{selected_file}' for server: {server_name}"
    )

    result = handlers.install_addon_handler(server_name, selected_file, base_dir)

    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        logger.info(
            f"Addon '{selected_file}' installed successfully for {server_name} via API."
        )
    else:
        error_message = (
            result.get("message", "Unknown addon installation error")
            if result
            else "Addon installation handler failed unexpectedly"
        )
        logger.error(
            f"API Install Addon failed for {server_name} (file: {selected_file}): {error_message}"
        )
        if not result:
            result = {
                "status": "error",
                "message": "Addon installation handler failed unexpectedly",
            }
        elif "status" not in result:
            result["status"] = "error"

    return jsonify(result), status_code


@server_bp.route("/server/<server_name>/monitor")
@login_required
def monitor_server_route(server_name):
    """Displays the server monitoring page."""
    logger.info(f"Displaying monitoring page for server: {server_name}")
    return render_template("monitor.html", server_name=server_name, app_name=app_name)


@server_bp.route("/api/server/<server_name>/status")
@login_required
def server_status_api(server_name):
    """Provides server status information as JSON."""
    base_dir = get_base_dir()
    result = handlers.get_bedrock_process_info_handler(server_name, base_dir)
    logger.debug(f"Providing server status API for {server_name}: {result}")
    return jsonify(result)  # Return JSON response


@server_bp.route("/server/<server_name>/schedule", methods=["GET"])
@login_required
def schedule_tasks_route(server_name):
    base_dir = get_base_dir()
    # Get cron jobs using the handler
    cron_jobs_response = handlers.get_server_cron_jobs_handler(server_name)
    if cron_jobs_response["status"] == "error":
        flash(cron_jobs_response["message"], "error")
        logger.error(
            f"Error getting cron jobs for {server_name}: {cron_jobs_response['message']}"
        )
        table_data = []  # Provide empty data if there's an error
    else:
        cron_jobs = cron_jobs_response["cron_jobs"]
        # Get formatted table data using the handler
        table_response = handlers.get_cron_jobs_table_handler(cron_jobs)
        if table_response["status"] == "error":
            flash(table_response["message"], "error")
            logger.error(
                f"Error formatting cron jobs for {server_name}: {table_response['message']}"
            )
            table_data = []
        else:
            table_data = table_response["table_data"]
    logger.info(f"Displaying schedule tasks page for server: {server_name}")
    return render_template(
        "schedule_tasks.html",
        server_name=server_name,
        table_data=table_data,
        EXPATH=EXPATH,
        app_name=app_name,
    )


@server_bp.route("/server/<server_name>/schedule/add", methods=["POST"])
@login_required
def add_cron_job_route(server_name):
    base_dir = get_base_dir()
    data = request.get_json()
    cron_string = data.get("new_cron_job")

    if not cron_string:
        logger.warning(
            f"Add cron job request for {server_name} with empty cron string."
        )
        return jsonify({"status": "error", "message": "Cron string is required."}), 400

    logger.info(f"Adding cron job for {server_name}: {cron_string}")
    add_response = handlers.add_cron_job_handler(cron_string)
    return jsonify(add_response)  # Return JSON response


@server_bp.route("/server/<server_name>/schedule/modify", methods=["POST"])
@login_required
def modify_cron_job_route(server_name):
    base_dir = get_base_dir()
    data = request.get_json()
    old_cron_string = data.get("old_cron_job")
    new_cron_string = data.get("new_cron_job")
    logger.info(
        f"Modifying cron job for {server_name}. Old: {old_cron_string}, New: {new_cron_string}"
    )
    if not old_cron_string or not new_cron_string:
        logger.warning(
            f"Modify cron job request for {server_name} with missing old or new cron string."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Both old and new cron strings are required.",
                }
            ),
            400,
        )

    modify_response = handlers.modify_cron_job_handler(old_cron_string, new_cron_string)
    return jsonify(modify_response)  # Return JSON response


@server_bp.route("/server/<server_name>/schedule/delete", methods=["POST"])
@login_required
def delete_cron_job_route(server_name):
    base_dir = get_base_dir()
    data = request.get_json()
    cron_string = data.get("cron_string")
    logger.info(f"Deleting cron job for {server_name}: {cron_string}")
    if not cron_string:
        logger.warning(
            f"Delete cron job request for {server_name} with empty cron string."
        )
        return jsonify({"status": "error", "message": "Cron string is required."}), 400
    delete_response = handlers.delete_cron_job_handler(cron_string)
    return jsonify(delete_response)  # Return JSON response


@server_bp.route("/server/<server_name>/tasks", methods=["GET"])
@login_required
def schedule_tasks_windows_route(server_name):
    """Displays the Windows Task Scheduler UI."""
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    logger.info(f"Displaying schedule tasks page for server: {server_name}")

    if platform.system() != "Windows":
        flash("Task scheduling is only available on Windows.", "error")
        logger.warning(
            f"Attempted to access Windows task scheduler from non-Windows system."
        )
        return redirect(url_for("server_routes.index"))

    task_names_response = handlers.get_server_task_names_handler(
        server_name, config_dir
    )
    if task_names_response["status"] == "error":
        flash(f"Error getting task names: {task_names_response['message']}", "error")
        logger.error(
            f"Error getting task names for {server_name}: {task_names_response['message']}"
        )
        tasks = []  # Provide an empty list so the template doesn't break
    else:
        task_names = task_names_response["task_names"]
        # Get detailed task info using the handler
        task_info_response = handlers.get_windows_task_info_handler(
            [task[0] for task in task_names]  # Extract task names
        )
        if task_info_response["status"] == "error":
            flash(f"Error getting task info: {task_info_response['message']}", "error")
            logger.error(
                f"Error getting task info for {server_name}: {task_info_response['message']}"
            )
            tasks = []
        else:
            tasks = task_info_response["task_info"]

    return render_template(
        "schedule_tasks_windows.html",
        server_name=server_name,
        tasks=tasks,
        app_name=app_name,
    )


@server_bp.route("/server/<server_name>/tasks/add", methods=["GET", "POST"])
@login_required
def add_windows_task_route(server_name):
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    logger.info(f"Adding Windows task for server: {server_name}")
    if request.method == "POST":
        command = request.form.get("command")
        command_args = f"--server {server_name}"
        if command == "update-server":
            pass  # command args already correct.
        elif command == "backup-all":
            pass
        elif command == "start-server":
            pass
        elif command == "stop-server":
            pass
        elif command == "restart-server":
            pass
        elif command == "scan-players":
            command_args = ""  # No args
        else:
            flash("Invalid command selected.", "error")
            logger.warning(f"Invalid command selected for Windows task: {command}")
            return render_template(
                "add_windows_task.html", server_name=server_name, app_name=app_name
            )

        task_name = f"bedrock_{server_name}_{command.replace('-', '_')}"
        triggers = []

        # Process trigger data (iterate through form data)
        trigger_num = 1
        while True:  # Loop until we run out of trigger data
            trigger_type = request.form.get(f"trigger_type_{trigger_num}")
            if not trigger_type:
                break  # No more triggers

            trigger_data = {"type": trigger_type}
            trigger_data["start"] = request.form.get(f"start_{trigger_num}")

            if trigger_type == "Daily":
                trigger_data["interval"] = int(
                    request.form.get(f"interval_{trigger_num}")
                )
            elif trigger_type == "Weekly":
                trigger_data["interval"] = int(
                    request.form.get(f"interval_{trigger_num}")
                )
                days_of_week_str = request.form.get(f"days_of_week_{trigger_num}", "")
                trigger_data["days"] = [
                    day.strip() for day in days_of_week_str.split(",") if day.strip()
                ]
            elif trigger_type == "Monthly":
                days_of_month_str = request.form.get(f"days_of_month_{trigger_num}", "")
                trigger_data["days"] = [
                    int(day.strip())
                    for day in days_of_month_str.split(",")
                    if day.strip().isdigit()
                ]
                months_str = request.form.get(f"months_{trigger_num}", "")
                trigger_data["months"] = [
                    month.strip() for month in months_str.split(",") if month.strip()
                ]

            triggers.append(trigger_data)
            trigger_num += 1

        # Call handler to create the task
        result = handlers.create_windows_task_handler(
            server_name,
            command,
            command_args,
            task_name,
            config_dir,
            triggers,
            base_dir,
        )

        if result["status"] == "success":
            flash(f"Task '{task_name}' added successfully!", "success")
            logger.info(f"Task '{task_name}' added successfully for {server_name}")
            return redirect(
                url_for(
                    "server_routes.schedule_tasks_windows_route",
                    server_name=server_name,
                )
            )
        else:
            flash(f"Error adding task: {result['message']}", "error")
            logger.error(
                f"Error adding task '{task_name}' for {server_name}: {result['message']}"
            )
            return render_template(
                "add_windows_task.html", server_name=server_name, app_name=app_name
            )

    return render_template(
        "add_windows_task.html", server_name=server_name, app_name=app_name
    )


@server_bp.route(
    "/server/<server_name>/tasks/modify/<task_name>", methods=["GET", "POST"]
)
@login_required
def modify_windows_task_route(server_name, task_name):
    base_dir = get_base_dir()
    config_dir = settings.CONFIG_DIR
    xml_file_path = os.path.join(config_dir, server_name, f"{task_name}.xml")
    logger.info(
        f"Modify Windows task route accessed for server: {server_name}, task: {task_name}, method: {request.method}"
    )

    if request.method == "POST":
        logger.debug(f"POST request received for modifying task: {task_name}")
        # Handle form submission (modify task)
        command = request.form.get("command")
        logger.debug(f"Received command: {command}")
        # Construct command arguments (similar to add)
        if command == "update-server":
            command_args = f"--server {server_name}"
        elif command == "backup-all":
            command_args = f"--server {server_name}"
        elif command == "start-server":
            command_args = f"--server {server_name}"
        elif command == "stop-server":
            command_args = f"--server {server_name}"
        elif command == "restart-server":
            command_args = f"--server {server_name}"
        elif command == "scan-players":
            command_args = ""
        else:
            logger.error(f"Invalid command selected: {command}")
            flash("Invalid command selected.", "error")
            # Reload existing data to re-render form with errors
            existing_task_data = handlers.get_windows_task_details_handler(
                xml_file_path
            )
            return render_template(
                "modify_windows_task.html",
                server_name=server_name,
                task_name=task_name,
                **existing_task_data,
                app_name=app_name,
            )

        new_task_name = (
            f"bedrock_{server_name}_{command.replace('-', '_')}"  # Rename task
        )
        logger.debug(f"New task name will be: {new_task_name}")

        triggers = []
        trigger_num = 1
        while True:
            trigger_type = request.form.get(f"trigger_type_{trigger_num}")
            if not trigger_type:
                break
            trigger_data = {"type": trigger_type}
            trigger_data["start"] = request.form.get(f"start_{trigger_num}")
            if trigger_type == "Daily":
                trigger_data["interval"] = int(
                    request.form.get(f"interval_{trigger_num}")
                )
            elif trigger_type == "Weekly":
                trigger_data["interval"] = int(
                    request.form.get(f"interval_{trigger_num}")
                )
                days_of_week_str = request.form.get(f"days_of_week_{trigger_num}", "")
                trigger_data["days"] = [
                    day.strip() for day in days_of_week_str.split(",") if day.strip()
                ]
            elif trigger_type == "Monthly":
                days_of_month_str = request.form.get(f"days_of_month_{trigger_num}", "")
                trigger_data["days"] = [
                    int(day.strip())
                    for day in days_of_month_str.split(",")
                    if day.strip().isdigit()
                ]
                months_str = request.form.get(f"months_{trigger_num}", "")
                trigger_data["months"] = [
                    month.strip() for month in months_str.split(",") if month.strip()
                ]
            triggers.append(trigger_data)
            trigger_num += 1
        logger.debug(f"Parsed triggers: {triggers}")

        # Call the handler to modify the task
        logger.info(
            f"Calling handler to modify task '{task_name}' to '{new_task_name}'"
        )
        result = handlers.modify_windows_task_handler(
            task_name,  # Old task name
            server_name,
            command,
            command_args,
            new_task_name,
            config_dir,
            triggers,
            base_dir,
        )

        if result["status"] == "success":
            logger.info(
                f"Task '{task_name}' modified successfully! (New name: {new_task_name})"
            )
            flash(
                f"Task '{task_name}' modified successfully! (New name: {new_task_name})",
                "success",
            )
            return redirect(
                url_for(
                    "server_routes.schedule_tasks_windows_route",
                    server_name=server_name,
                )
            )
        else:
            logger.error(f"Error modifying task '{task_name}': {result['message']}")
            flash(f"Error modifying task: {result['message']}", "error")
            # Load existing task data again for re-rendering
            existing_task_data = _load_existing_task_data_for_modify(
                xml_file_path
            )  # Call helper function
            return render_template(
                "modify_windows_task.html",
                server_name=server_name,
                task_name=task_name,
                **existing_task_data,
                app_name=app_name,
            )

    else:  # GET request
        logger.debug(f"GET request received for modifying task: {task_name}")
        # Load existing task data from XML to pre-populate the form
        existing_task_data = _load_existing_task_data_for_modify(xml_file_path)
        if "error" in existing_task_data:
            logger.error(
                f"Error loading task data for modification: {existing_task_data['error']}"
            )
            flash(f"Error loading task data: {existing_task_data['error']}", "error")
            return redirect(
                url_for(
                    "server_routes.schedule_tasks_windows_route",
                    server_name=server_name,
                )
            )

        logger.debug(f"Rendering modification form with data: {existing_task_data}")
        return render_template(
            "modify_windows_task.html",
            server_name=server_name,
            task_name=task_name,
            **existing_task_data,
            app_name=app_name,
        )


@server_bp.route("/server/<server_name>/tasks/delete", methods=["POST"])
@login_required
def delete_windows_task_route(server_name):
    base_dir = get_base_dir()
    config_dir = settings.CONFIG_DIR
    task_name = request.form.get("task_name")
    task_file_path = request.form.get("task_file_path")

    logger.info(f"Deleting Windows task: {task_name} for server: {server_name}")
    if not task_name or not task_file_path:
        flash("Invalid task deletion request.", "error")
        logger.warning(
            f"Invalid task deletion request for {server_name}: Missing task name or file path."
        )
        return redirect(url_for("server_routes.index"))

    result = handlers.delete_windows_task_handler(task_name, task_file_path, base_dir)

    if result["status"] == "error":
        flash(f"Error deleting task: {result['message']}", "error")
        logger.error(
            f"Error deleting task {task_name} for server {server_name}: {result['message']}"
        )
    else:
        flash(f"Task '{task_name}' deleted successfully!", "success")
        logger.info(f"Task '{task_name}' deleted successfully for {server_name}")
    return redirect(
        url_for("server_routes.schedule_tasks_windows_route", server_name=server_name)
    )  # redirect back to list of tasks
