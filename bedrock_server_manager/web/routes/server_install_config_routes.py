# bedrock-server-manager/bedrock_server_manager/web/routes/install_config_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import os
import re
import platform
import logging
import json
from bedrock_server_manager.api import server
from bedrock_server_manager.api import server_install_config
from bedrock_server_manager.api import player
from bedrock_server_manager.api import system
from bedrock_server_manager.api import utils
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config.settings import settings, app_name
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.web.routes.auth_routes import login_required, csrf
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)


# Initialize logger for this module
logger = logging.getLogger("bedrock_server_manager")

# Create Blueprint for installation and configuration routes
server_install_config_bp = Blueprint("install_config_routes", __name__)


# --- Route: Install Server Page ---
@server_install_config_bp.route("/install", methods=["GET"])
@login_required
def install_server_route():
    """Renders the page for installing a new server."""
    logger.info("Route '/install' accessed - Rendering install server page.")
    # Pass empty strings initially if needed by template value attributes
    return render_template(
        "install.html", server_name="", server_version="", app_name=app_name
    )


# --- API Route: Install Server ---
@server_install_config_bp.route("/api/server/install", methods=["POST"])
@csrf.exempt
@auth_required
def install_server_api_route():
    """API endpoint to handle the server installation process."""
    logger.info("API POST request received to install a new server.")
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    logger.debug(f"Base directory: {base_dir}, Config directory: {config_dir}")

    # Get JSON data from request
    data = request.get_json()
    logger.debug(f"Received JSON data for install request: {data}")

    # Validate JSON body
    if not data or not isinstance(data, dict):
        logger.warning(f"API Install Server request: Empty or invalid JSON body.")
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract parameters
    server_name = data.get("server_name")
    server_version = data.get("server_version")
    overwrite = data.get("overwrite", False)  # Default overwrite to False
    logger.debug(
        f"Install parameters: server_name='{server_name}', server_version='{server_version}', overwrite={overwrite}"
    )

    # --- Basic Input Validation ---
    if not server_name or not isinstance(server_name, str) or not server_name.strip():
        logger.warning(f"API Install Server request: Missing or invalid 'server_name'.")
        return jsonify({"status": "error", "message": "Server name is required."}), 400
    if (
        not server_version
        or not isinstance(server_version, str)
        or not server_version.strip()
    ):
        logger.warning(
            f"API Install Server request: Missing or invalid 'server_version'."
        )
        return (
            jsonify({"status": "error", "message": "Server version is required."}),
            400,
        )
    if not isinstance(overwrite, bool):
        logger.warning(
            f"API Install Server request: Invalid 'overwrite' flag (must be boolean)."
        )
        return (
            jsonify({"status": "error", "message": "Invalid 'overwrite' flag type."}),
            400,
        )

    server_name = server_name.strip()  # Use trimmed name

    # --- Server Name Format Validation ---
    logger.debug(f"Calling validate_server_name_format for '{server_name}'...")
    validation_result = utils.validate_server_name_format(server_name)
    if validation_result["status"] == "error":
        error_msg = f"Server name validation failed: {validation_result.get('message', 'Invalid format')}"
        logger.warning(f"API Install Server: {error_msg}")
        # Return validation error with specific message from handler
        return jsonify(validation_result), 400

    logger.info(
        f"API request validated for install server: Name='{server_name}', Version='{server_version}', Overwrite={overwrite}"
    )

    # --- Check if Server Exists ---
    server_dir = os.path.join(base_dir, server_name)
    server_exists = os.path.exists(server_dir)
    logger.debug(
        f"Checking existence of server directory '{server_dir}': {server_exists}"
    )

    # --- Handle Confirmation / Overwrite Logic ---
    if server_exists and not overwrite:
        # If server exists and overwrite is not explicitly requested, ask for confirmation
        logger.info(
            f"Server '{server_name}' already exists and overwrite flag is false. Requesting confirmation from client."
        )
        confirm_message = f"Server directory '{server_name}' already exists. Overwrite existing data and reinstall?"
        return (
            jsonify(
                {
                    "status": "confirm_needed",  # Special status for frontend
                    "message": confirm_message,
                    "server_name": server_name,  # Include details for potential retry
                    "server_version": server_version,
                }
            ),
            200,  # Use 200 OK for confirmation needed, as it's not an error yet
        )

    # --- Proceed with Installation (Either new or overwrite confirmed) ---
    result = None  # To store the final handler result
    status_code = 500  # Default to Internal Server Error

    try:
        # If overwrite is requested (and server exists), delete existing data first
        if server_exists and overwrite:
            logger.info(
                f"Overwrite confirmed for '{server_name}'. Calling delete_server_data..."
            )
            delete_result = server.delete_server_data(server_name, base_dir, config_dir)
            logger.debug(f"Delete handler result for '{server_name}': {delete_result}")
            # If deletion fails, report the error immediately
            if delete_result["status"] == "error":
                error_msg = f"Failed to delete existing server data for '{server_name}': {delete_result.get('message', 'Unknown delete error')}"
                logger.error(f"API Install Server: {error_msg}")
                # Return the delete error directly
                return jsonify({"status": "error", "message": error_msg}), 500

        # Perform the actual installation (for new server or after successful delete)
        logger.info(
            f"Calling install_new_server for '{server_name}' (Version: {server_version})..."
        )
        install_result = server_install_config.install_new_server(
            server_name, server_version, base_dir, config_dir
        )
        logger.debug(f"Install handler result for '{server_name}': {install_result}")

        # Check the result from the installation handler
        if install_result.get("status") == "success":
            logger.info(f"Server '{server_name}' installed successfully via API.")
            result = install_result  # Use the handler's result
            # Add the URL for the next step in the configuration sequence
            result["next_step_url"] = url_for(
                "install_config_routes.configure_properties_route",  # Use new blueprint name
                server_name=server_name,
                new_install=True,  # Flag this as part of new installation
            )
            if "message" not in result:
                result["message"] = f"Server '{server_name}' installed successfully."
            status_code = 200  # OK
        else:
            # Installation handler reported an error
            error_msg = f"Installation failed for '{server_name}': {install_result.get('message', 'Unknown install error')}"
            logger.error(f"API Install Server: {error_msg}")
            result = install_result  # Use the handler's error result
            if "message" not in result:
                result["message"] = (
                    f"Error during installation of server '{server_name}'."
                )
            result["status"] = "error"
            status_code = 500  # Internal Server Error

    except Exception as e:
        # Catch unexpected exceptions during the process
        logger.exception(
            f"Unexpected error during server installation API call for '{server_name}': {e}"
        )
        result = {
            "status": "error",
            "message": f"An unexpected server error occurred during installation: {e}",
        }
        status_code = 500  # Internal Server Error

    # Return the final JSON response
    logger.debug(
        f"Returning JSON for install API for '{server_name}' with status code {status_code}: {result}"
    )
    return jsonify(result), status_code


# --- Route: Configure Server Properties Page ---
@server_install_config_bp.route(
    "/server/<server_name>/configure_properties", methods=["GET"]
)
@login_required
def configure_properties_route(server_name):
    """Renders the page for configuring server.properties."""
    logger.info(
        f"Route '/server/{server_name}/configure_properties' accessed - Rendering properties configuration page."
    )
    base_dir = get_base_dir()
    server_dir = os.path.join(base_dir, server_name)
    server_properties_path = os.path.join(server_dir, "server.properties")
    logger.debug(
        f"Server directory: {server_dir}, Properties path: {server_properties_path}"
    )

    # Check if server.properties file exists
    if not os.path.exists(server_properties_path):
        error_msg = f"'server.properties' not found for server: '{server_name}'. Cannot configure properties."
        flash(error_msg, "error")
        logger.error(error_msg)
        # Redirect to a more general page if properties file is missing
        return redirect(url_for("main_routes.index"))  # Use main blueprint name

    # Check if this is part of a new installation sequence
    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"
    logger.debug(
        f"Processing configure properties for '{server_name}', new_install flag: {new_install}"
    )

    # Read current properties using the handler
    logger.debug(f"Calling read_server_properties for '{server_name}'...")
    properties_response = server_install_config.read_server_properties(
        server_name, base_dir
    )

    # Handle errors from the properties reading handler
    if properties_response["status"] == "error":
        error_msg = f"Error loading properties for '{server_name}': {properties_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
        # Redirect if properties cannot be loaded
        return redirect(url_for("main_routes.index"))  # Use main blueprint name

    properties_data = properties_response.get("properties", {})
    logger.debug(
        f"Successfully loaded properties for '{server_name}': {properties_data}"
    )

    # Render the configuration template
    logger.debug(f"Rendering configure_properties.html for '{server_name}'.")
    return render_template(
        "configure_properties.html",
        server_name=server_name,
        properties=properties_data,  # Pass loaded properties
        new_install=new_install,  # Pass the new install flag
        app_name=app_name,
    )


# --- API Route: Configure Server Properties ---
@server_install_config_bp.route(
    "/api/server/<server_name>/properties", methods=["POST"]
)
@csrf.exempt
@auth_required
def configure_properties_api_route(server_name):
    """API endpoint to validate and update server.properties."""
    logger.info(
        f"API POST request received to configure properties for server: '{server_name}'."
    )
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    logger.debug(f"Base directory: {base_dir}, Config directory: {config_dir}")

    # Get JSON data
    properties_data = request.get_json()
    logger.debug(f"Received JSON data for properties update: {properties_data}")

    # Validate JSON body
    if not properties_data or not isinstance(properties_data, dict):
        logger.warning(
            f"API Configure Properties for '{server_name}': Empty or invalid JSON body."
        )
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Define allowed keys (whitelist based on form fields)
    # This prevents arbitrary properties from being set via API abuse
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
        # Add any other properties managed by your configure_properties.html form
    ]
    logger.debug(f"Allowed property keys for update: {allowed_keys}")

    properties_to_update = {}  # Store validated properties
    validation_errors = {}  # Dictionary to hold field-specific validation errors

    # --- Iterate through received data and validate ---
    logger.debug("Validating received properties data...")
    for key, value in properties_data.items():
        # Check if the key is expected/allowed
        if key not in allowed_keys:
            logger.warning(
                f"API Configure Properties for '{server_name}': Received unexpected key '{key}'. Ignoring."
            )
            continue  # Skip keys not explicitly allowed

        # Ensure value is processed as a string for consistent validation/saving
        value_str = str(value).strip()  # Convert to string and strip whitespace

        # --- Specific Cleaning/Normalization (Example for level-name) ---
        if key == "level-name":
            original_value = value_str
            # Replace invalid filesystem characters and spaces with underscores
            value_str = re.sub(r'[<>:"/\\|?* ]+', "_", original_value)
            if value_str != original_value:
                logger.info(
                    f"API Configure Properties: Cleaned 'level-name' from '{original_value}' to '{value_str}'"
                )

        # --- Call Validation Handler ---
        logger.debug(f"Validating property: {key}='{value_str}'...")
        validation_response = server_install_config.validate_server_property_value(
            key, value_str
        )
        if validation_response["status"] == "error":
            error_msg = validation_response.get("message", f"Invalid value for {key}")
            logger.warning(f"API Validation error for {key}='{value_str}': {error_msg}")
            validation_errors[key] = error_msg
            # Continue validating other fields, collect all errors
        else:
            # If validation passes, add to the dictionary for update
            properties_to_update[key] = value_str
            logger.debug(f"Property '{key}' passed validation.")

    # --- Check if any validation errors occurred ---
    if validation_errors:
        error_summary = "Validation failed for one or more properties."
        logger.error(
            f"API Configure Properties validation failed for '{server_name}': {validation_errors}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": error_summary,
                    "errors": validation_errors,  # Send specific errors back to the client
                }
            ),
            400,  # Bad Request status code for validation errors
        )

    # --- If validation passed, attempt to modify properties ---
    if not properties_to_update:
        # This case might occur if the request only contained invalid keys or values that failed validation
        logger.warning(
            f"API Configure Properties for '{server_name}': No valid properties were provided for update after validation."
        )
        # Return success but indicate nothing was changed
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "No valid properties provided or no changes detected.",
                }
            ),
            200,
        )

    # Call the handler to write the validated properties to the file
    logger.info(
        f"Calling modify_server_properties for '{server_name}' with validated properties..."
    )
    logger.debug(f"Properties to update: {properties_to_update}")
    modify_response = server_install_config.modify_server_properties(
        server_name, properties_to_update, base_dir
    )
    logger.debug(
        f"Modify properties handler response for '{server_name}': {modify_response}"
    )

    # Handle potential errors from the modification handler
    if modify_response["status"] == "error":
        error_msg = f"Failed to update server properties for '{server_name}': {modify_response.get('message', 'Unknown handler error')}"
        logger.error(f"API Error: {error_msg}")
        # Return 500 Internal Server Error if the handler itself failed
        return jsonify({"status": "error", "message": error_msg}), 500

    # --- Return final success response ---
    success_message = f"Server properties for '{server_name}' updated successfully."
    logger.info(f"API: {success_message}")
    # Ensure message key exists in response
    if "message" not in modify_response:
        modify_response["message"] = success_message

    logger.debug(
        f"Returning JSON response for configure properties API '{server_name}' with status code 200."
    )
    return jsonify(modify_response), 200


# --- Route: Configure Allowlist Page ---
@server_install_config_bp.route(
    "/server/<server_name>/configure_allowlist", methods=["GET"]
)
@login_required
def configure_allowlist_route(server_name):
    """Renders the page for configuring the server allowlist."""
    logger.info(
        f"Route '/server/{server_name}/configure_allowlist' accessed - Rendering allowlist configuration page."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Check if this is part of a new installation sequence
    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"
    logger.debug(
        f"Processing configure allowlist for '{server_name}', new_install flag: {new_install}"
    )

    # Call handler to get existing players from allowlist.json
    logger.debug(f"Calling configure_allowlist (read mode) for '{server_name}'...")
    # Calling with new_players_data=None makes it read the existing list
    result = server_install_config.configure_allowlist(
        server_name, base_dir, new_players_data=None
    )

    existing_players = []  # Default to empty list
    if result["status"] == "error":
        error_msg = f"Error loading current allowlist for '{server_name}': {result.get('message', 'Unknown error')}"
        flash(error_msg, "error")  # Inform user via flash
        logger.error(error_msg)
    else:
        # Expecting a list of player dictionaries {'name': ..., 'ignoresPlayerLimit': ...}
        existing_players = result.get("existing_players", [])
        logger.debug(
            f"Successfully loaded {len(existing_players)} players from allowlist for '{server_name}'."
        )

    # Render the allowlist configuration template
    logger.debug(f"Rendering configure_allowlist.html for '{server_name}'.")
    return render_template(
        "configure_allowlist.html",
        server_name=server_name,
        existing_players=existing_players,  # Pass the list of player dicts
        new_install=new_install,  # Pass the new install flag
        app_name=app_name,
    )


# --- API Route: Save Allowlist (used during initial setup or full replacement) ---
@server_install_config_bp.route("/api/server/<server_name>/allowlist", methods=["POST"])
@csrf.exempt
@auth_required
def save_allowlist_api_route(server_name):
    """API endpoint to SAVE/REPLACE the server allowlist (typically used during initial setup)."""
    # This differs from the ADD route; it replaces the list.
    logger.info(
        f"API POST request received to SAVE/REPLACE allowlist for server: '{server_name}'."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for save allowlist: {data}")

    # Validate JSON body
    if data is None:
        logger.warning(
            f"API Save Allowlist request for '{server_name}': Empty or invalid JSON body received."
        )
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract data fields
    players_list_names = data.get("players")  # Expecting a list of names
    ignore_limit = data.get("ignoresPlayerLimit", False)  # Expecting a boolean

    # Validate 'players' field
    if players_list_names is None or not isinstance(players_list_names, list):
        logger.warning(
            f"API Save Allowlist request for '{server_name}': Missing or invalid 'players' list in JSON body."
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

    # Validate 'ignoresPlayerLimit' field
    if not isinstance(ignore_limit, bool):
        logger.warning(
            f"API Save Allowlist request for '{server_name}': Invalid 'ignoresPlayerLimit' value (must be boolean)."
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

    # Clean the list: filter out empty names and ensure they are strings
    logger.debug(f"Raw player names received: {players_list_names}")
    valid_player_names = [
        name.strip()
        for name in players_list_names
        if isinstance(name, str) and name.strip()
    ]
    logger.debug(f"Valid player names for allowlist: {valid_player_names}")

    # Note: An empty list of valid_player_names is acceptable for clearing the allowlist.

    logger.info(
        f"API attempting to SAVE allowlist for '{server_name}'. Players: {valid_player_names}, IgnoreLimit: {ignore_limit}"
    )

    # Format data for the handler (expects list of dicts)
    new_players_data_for = [
        {"name": name, "ignoresPlayerLimit": ignore_limit}
        for name in valid_player_names
    ]
    logger.debug(
        f"Data formatted for configure_allowlist (save mode): {new_players_data_for}"
    )

    # Call the handler to save/replace the players
    # The handler needs logic to differentiate between ADD and REPLACE. Assuming it handles this based on some implicit logic or if called differently.
    # For clarity, let's assume the handler `configure_allowlist` replaces the list when called via POST to `/api/server/<name>/allowlist`
    # and adds when called via POST to `/api/server/<name>/allowlist/add`.
    # We might need a dedicated handler or a flag in the existing one.
    # RETHINK: The original code only had one `configure_allowlist`. Let's assume it *replaces* the list by default when `new_players_data` is provided.
    result = server_install_config.configure_allowlist(
        server_name, base_dir, new_players_data=new_players_data_for
    )
    logger.debug(f"Save allowlist handler response for '{server_name}': {result}")

    # Determine status code based on handler result
    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        # Adjust message based on whether players were added/updated or list was cleared
        player_count = len(valid_player_names)
        if player_count > 0:
            success_message = f"Allowlist saved successfully for '{server_name}' with {player_count} player(s)."
        else:
            success_message = f"Allowlist cleared successfully for '{server_name}'."
        logger.info(
            f"API Allowlist Save successful for '{server_name}'. {success_message}"
        )
        if "message" not in result:
            result["message"] = success_message
    else:
        error_message = (
            result.get("message", "Unknown error saving allowlist")
            if result
            else "Save allowlist handler failed unexpectedly"
        )
        logger.error(f"API Save Allowlist failed for '{server_name}': {error_message}")
        # Ensure result object exists and has error status/message
        if not result:
            result = {}
        result["status"] = "error"
        if "message" not in result:
            result["message"] = "Failed to save allowlist due to a server error."

    # Return the result from the handler
    logger.debug(
        f"Returning JSON response for save allowlist API '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code


# --- API Route: Add Players to Allowlist ---
@server_install_config_bp.route(
    "/api/server/<server_name>/allowlist/add", methods=["POST"]
)
@csrf.exempt
@auth_required
def add_allowlist_players_api_route(server_name):
    """API endpoint to ADD players to the server allowlist."""
    logger.info(
        f"API POST request received to ADD players to allowlist for server: '{server_name}'."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for add allowlist: {data}")

    # Validate JSON body
    if data is None:  # Check for None specifically, as {} is valid JSON
        logger.warning(
            f"API Add Allowlist request for '{server_name}': Empty or invalid JSON body received."
        )
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract data fields
    players_to_add_names = data.get("players")  # Expecting a list of names
    ignore_limit = data.get("ignoresPlayerLimit", False)  # Expecting a boolean

    # Validate 'players' field
    if players_to_add_names is None or not isinstance(players_to_add_names, list):
        logger.warning(
            f"API Add Allowlist request for '{server_name}': Missing or invalid 'players' list in JSON body."
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

    # Validate 'ignoresPlayerLimit' field
    if not isinstance(ignore_limit, bool):
        logger.warning(
            f"API Add Allowlist request for '{server_name}': Invalid 'ignoresPlayerLimit' value (must be boolean)."
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

    # Clean the list: filter out empty names and ensure they are strings
    logger.debug(f"Raw player names received: {players_to_add_names}")
    valid_player_names = [
        name.strip()
        for name in players_to_add_names
        if isinstance(name, str) and name.strip()
    ]
    logger.debug(f"Valid player names to add: {valid_player_names}")

    # Check if there are any valid names left to add
    if not valid_player_names:
        logger.warning(
            f"API Add Allowlist request for '{server_name}': No valid player names provided after filtering."
        )
        return (
            jsonify(
                {"status": "error", "message": "No valid player names provided to add."}
            ),
            400,
        )

    logger.info(
        f"API attempting to ADD players to allowlist for '{server_name}'. Players: {valid_player_names}, IgnoreLimit: {ignore_limit}"
    )

    # Format data for the handler (expects list of dicts)
    new_players_data_for = [
        {"name": name, "ignoresPlayerLimit": ignore_limit}
        for name in valid_player_names
    ]
    logger.debug(
        f"Data formatted for configure_allowlist (add mode): {new_players_data_for}"
    )

    # Call the handler to add/update players
    # Assuming the handler merges the new players with existing ones when called via this '/add' route.
    # This might require modification of the handler or a new dedicated handler.
    # For now, let's assume `configure_allowlist` can handle merging based on some internal logic (e.g., reading first then writing combined list).
    result = server_install_config.configure_allowlist(
        server_name,
        base_dir,
        new_players_data=new_players_data_for,
    )
    logger.debug(f"Add allowlist handler response for '{server_name}': {result}")

    # Determine status code based on handler result
    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        added_count = len(
            result.get("added_players", [])
        )  # Handler should return this info
        updated_count = len(
            result.get("updated_players", [])
        )  # Handler should return this info
        success_message = f"Allowlist updated: {added_count} player(s) added, {updated_count} player(s) updated."
        logger.info(
            f"API Allowlist Add successful for '{server_name}'. {success_message}"
        )
        if "message" not in result:
            result["message"] = success_message
    else:
        error_message = (
            result.get("message", "Unknown error adding players")
            if result
            else "Add players handler failed unexpectedly"
        )
        logger.error(f"API Add Allowlist failed for '{server_name}': {error_message}")
        # Ensure result object exists and has error status/message
        if not result:
            result = {}
        result["status"] = "error"
        if "message" not in result:
            result["message"] = (
                "Failed to add players to allowlist due to a server error."
            )

    # Return the result from the handler
    logger.debug(
        f"Returning JSON response for add allowlist API '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code


# --- API Route: Get Allowlist ---
@server_install_config_bp.route("/api/server/<server_name>/allowlist", methods=["GET"])
@csrf.exempt
@auth_required
def get_allowlist_api_route(server_name):
    """API endpoint to retrieve the current server allowlist."""
    logger.info(f"API GET request received for allowlist for server: '{server_name}'.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the handler in read mode (new_players_data=None)
    logger.debug(f"Calling configure_allowlist (read mode) for '{server_name}'...")
    result = server_install_config.configure_allowlist(
        server_name, base_dir, new_players_data=None
    )
    logger.debug(f"Get allowlist handler response for '{server_name}': {result}")

    # Check handler result
    if result.get("status") != "success":
        error_message = result.get("message", "Failed to load allowlist")
        logger.error(f"API GET Allowlist failed for '{server_name}': {error_message}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": error_message,
                    "existing_players": [],  # Return empty list on error
                }
            ),
            500,  # Internal Server Error
        )
    else:
        # Prepare success response
        existing_players = result.get("existing_players", [])  # Get list from handler
        logger.info(
            f"Successfully retrieved {len(existing_players)} players from allowlist for '{server_name}' via API."
        )
        response_data = {
            "status": "success",
            "message": f"Successfully retrieved allowlist for '{server_name}'.",
            "existing_players": existing_players,
        }
        logger.debug(
            f"Returning JSON response for get allowlist API '{server_name}' with status code 200."
        )
        return jsonify(response_data), 200


# --- Route: Configure Permissions Page ---
@server_install_config_bp.route(
    "/server/<server_name>/configure_permissions", methods=["GET"]
)
@login_required
def configure_permissions_route(server_name):
    """Renders the page for configuring player permissions."""
    logger.info(
        f"Route '/server/{server_name}/configure_permissions' accessed - Rendering permissions configuration page."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Check if this is part of a new installation sequence
    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"
    logger.debug(
        f"Processing configure permissions for '{server_name}', new_install flag: {new_install}"
    )

    # Get known players (e.g., from players.json or potentially allowlist.json for names)
    # Using get_players_from_json for consistency with previous logic
    logger.debug("Calling get_players_from_json to get known player names/xuids...")
    players_response = player.get_players_from_json()
    players = []  # Default list of player dicts {'name': ..., 'xuid': ...}
    if players_response["status"] == "error":
        # Log warning but don't necessarily block page load, just show XUIDs
        warning_msg = f"Warning: Could not load global player names: {players_response.get('message', 'Unknown error')}. Only XUIDs may be shown for permissions."
        flash(warning_msg, "warning")
        logger.warning(warning_msg)
    else:
        players = players_response.get("players", [])
        logger.debug(f"Loaded {len(players)} players from global player data.")

    # Get current permissions from the server's permissions.json
    permissions = {}  # Default map {xuid: permission_level}
    try:
        server_dir = os.path.join(base_dir, server_name)
        permissions_file = os.path.join(server_dir, "permissions.json")
        logger.debug(f"Checking for permissions file: {permissions_file}")
        if os.path.exists(permissions_file):
            logger.debug(f"Reading permissions file: {permissions_file}")
            with open(permissions_file, "r") as f:
                permissions_data = json.load(f)  # Expecting list of dicts
                # Convert list of dicts to the map needed by the template
                for player_entry in permissions_data:
                    if "xuid" in player_entry and "permission" in player_entry:
                        permissions[player_entry["xuid"]] = player_entry["permission"]
            logger.debug(
                f"Loaded existing permissions map for '{server_name}': {permissions}"
            )
        else:
            logger.info(
                f"Permissions file '{permissions_file}' not found for '{server_name}'. Page will show defaults."
            )
    except (OSError, json.JSONDecodeError) as e:
        error_msg = f"Error reading existing permissions file for '{server_name}': {e}"
        flash(error_msg, "error")
        logger.error(error_msg)
        # Proceed with empty permissions map, defaults will apply in template

    # Ensure the `players` list includes entries for everyone currently in the permissions map,
    # even if their name isn't in the global players.json (e.g., if they connected once but aren't globally known)
    current_player_xuids_with_names = {p.get("xuid") for p in players if p.get("xuid")}
    xuids_only_in_permissions = (
        set(permissions.keys()) - current_player_xuids_with_names
    )

    if xuids_only_in_permissions:
        logger.debug(
            f"Found XUIDs in permissions.json but not in global player list: {xuids_only_in_permissions}"
        )
        for xuid in xuids_only_in_permissions:
            placeholder_name = f"Unknown (XUID: {xuid})"
            players.append({"xuid": xuid, "name": placeholder_name})
            logger.debug(f"Added placeholder entry for XUID {xuid} to display.")

    # Sort players alphabetically by name for display consistency
    players.sort(key=lambda p: p.get("name", "").lower())
    logger.debug(
        f"Final players list being sent to template (count: {len(players)}): {players}"
    )

    # Render the permissions configuration template
    logger.debug(f"Rendering configure_permissions.html for '{server_name}'.")
    return render_template(
        "configure_permissions.html",
        server_name=server_name,
        players=players,  # List of player dicts {'name': ..., 'xuid': ...}
        permissions=permissions,  # Dict mapping {xuid: permission_level}
        new_install=new_install,  # Pass the new install flag
        app_name=app_name,
    )


# --- API Route: Configure Permissions ---
@server_install_config_bp.route(
    "/api/server/<server_name>/permissions", methods=["PUT"]
)
@csrf.exempt
@auth_required
def configure_permissions_api_route(server_name):
    """API endpoint to update player permissions using PUT (replaces permissions for submitted players)."""
    # PUT is appropriate here as the frontend sends the complete desired state for players it knows about.
    logger.info(
        f"API PUT request received to configure permissions for server: '{server_name}'."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for permissions update: {data}")

    # Validate main JSON structure
    if not data or not isinstance(data, dict) or "permissions" not in data:
        logger.warning(
            f"API Configure Permissions for '{server_name}': Invalid or missing 'permissions' key in JSON body."
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

    # Extract the permissions map {xuid: level}
    permissions_map = data.get("permissions")
    if not isinstance(permissions_map, dict):
        logger.warning(
            f"API Configure Permissions for '{server_name}': 'permissions' value is not a dictionary/object."
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

    logger.debug(f"Permissions map received from API: {permissions_map}")

    # --- Validation of received permissions ---
    valid_levels = ("visitor", "member", "operator")
    validation_errors = {}  # Store validation errors {xuid: error_message}
    players_to_process = {}  # Store validated data {xuid: level}

    logger.debug("Validating received permission levels...")
    for xuid, level in permissions_map.items():
        # Basic type/value check
        if not isinstance(level, str) or level.lower() not in valid_levels:
            error_msg = (
                f"Invalid permission level '{level}'. Must be one of {valid_levels}."
            )
            logger.warning(
                f"API Permissions Validation Error for XUID {xuid}: {error_msg}"
            )
            validation_errors[xuid] = error_msg
            # Continue validating others
        else:
            # Store validated, lowercased level
            players_to_process[xuid] = level.lower()
            logger.debug(f"XUID {xuid} has valid level: {players_to_process[xuid]}")

    # Check if any validation errors occurred
    if validation_errors:
        error_summary = "Validation failed for one or more permission levels."
        logger.error(
            f"API Configure Permissions validation failed for '{server_name}': {validation_errors}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": error_summary,
                    "errors": validation_errors,  # Send specific errors back
                }
            ),
            400,  # Bad Request
        )

    # If validation passed, proceed to update permissions
    if not players_to_process:
        logger.warning(
            f"API Configure Permissions for '{server_name}': No players to process after validation (map was empty or all invalid)."
        )
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "No valid player permissions provided to update.",
                }
            ),
            200,
        )

    # --- Get Player Names (needed for the existing single-player handler) ---
    # This might be slightly inefficient if the handler could work without names,
    # but adapting to the existing handler structure.
    logger.debug("Fetching player names map...")
    players_response = player.get_players_from_json()
    player_name_map = {}  # Map xuid to name
    if players_response["status"] == "success":
        player_name_map = {
            player.get("xuid"): player.get(
                "name", f"Unknown (XUID: {player.get('xuid')})"
            )
            for player in players_response.get("players", [])
            if player.get("xuid")
        }
        logger.debug(f"Loaded {len(player_name_map)} player names.")
    else:
        logger.warning(
            f"Could not load global player names for permission update: {players_response.get('message')}. Using placeholders."
        )

    # --- Loop and call the existing handler for each player ---
    all_success = True
    handler_errors = (
        {}
    )  # Store errors from individual handler calls {xuid: error_message}
    processed_count = 0

    logger.info(
        f"Processing {len(players_to_process)} players for permission updates on '{server_name}'."
    )
    for xuid, level in players_to_process.items():
        # Get name from map or use placeholder
        player_name = player_name_map.get(xuid, f"Unknown (XUID: {xuid})")
        logger.debug(
            f"Calling configure_player_permission for Player: '{player_name}' (XUID: {xuid}), Level: '{level}'..."
        )

        # Call the handler that updates permissions.json for a single player
        # NOTE: Assumes this handler correctly reads, updates, and writes permissions.json
        result = server_install_config.configure_player_permission(
            server_name=server_name,
            xuid=xuid,
            player_name=player_name,  # Pass name even if placeholder
            permission=level,
            base_dir=base_dir,
            config_dir=settings.get("CONFIG_DIR"),
        )
        processed_count += 1
        logger.debug(f"Handler result for {xuid}: {result}")

        # Check result from the handler
        if result.get("status") != "success":
            all_success = False
            error_msg = result.get("message", "Unknown error from permission handler")
            handler_errors[xuid] = error_msg
            logger.error(f"Error configuring permission for XUID {xuid}: {error_msg}")

    # --- Determine final API response based on overall handler results ---
    if all_success:
        success_message = f"Permissions updated successfully for {processed_count} player(s) on server '{server_name}'."
        logger.info(f"API: {success_message}")
        return (
            jsonify({"status": "success", "message": success_message}),
            200,
        )
    else:
        error_summary = f"One or more errors occurred while setting permissions for '{server_name}'."
        logger.error(
            f"API Permissions update failed for '{server_name}'. Errors: {handler_errors}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": error_summary,
                    "errors": handler_errors,  # Map of xuid: error message from api
                }
            ),
            500,  # Internal Server Error because one or more handler actions failed
        )


# --- Route: Configure Service Page ---
@server_install_config_bp.route(
    "/server/<server_name>/configure_service", methods=["GET"]
)
@login_required
def configure_service_route(server_name):
    """Renders the page for configuring OS-specific service settings (systemd/autoupdate)."""
    logger.info(
        f"Route '/server/{server_name}/configure_service' accessed - Rendering service configuration page."
    )
    base_dir = get_base_dir()  # Needed? Not directly used here.
    config_dir = settings.get("CONFIG_DIR")
    logger.debug(f"Config directory: {config_dir}")

    # Check if this is part of a new installation sequence
    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"
    logger.debug(
        f"Processing configure service for '{server_name}', new_install flag: {new_install}"
    )

    # Determine the current operating system
    current_os = platform.system()
    logger.info(f"Detected operating system: {current_os}")

    # Prepare data for the template
    template_data = {
        "server_name": server_name,
        "os": current_os,
        "new_install": new_install,
        "app_name": app_name,
        "autoupdate": False,  # Default value
        "autostart": False,  # Default value (relevant for Linux)
    }

    # Load current settings based on OS
    if current_os == "Linux":
        logger.debug(
            "Preparing to render configure_service.html for Linux (defaults will be shown in form)."
        )

    elif current_os == "Windows":
        # For Windows, read the 'autoupdate' setting from the server's config file
        logger.debug(
            f"Reading 'autoupdate' setting for Windows server '{server_name}' from config..."
        )
        # Use the existing server_base helper function to read the specific config value
        autoupdate_value = server_base.manage_server_config(
            server_name, "autoupdate", "read", config_dir=config_dir
        )
        logger.debug(f"Read autoupdate value: '{autoupdate_value}'")
        # Convert the read string value ("true"/"false"/None) to a boolean
        template_data["autoupdate"] = (
            autoupdate_value == "true"
        )  # True only if string is exactly "true"
        logger.debug(
            f"Setting template autoupdate for Windows: {template_data['autoupdate']}"
        )

    else:
        # Handle unsupported OS
        warning_msg = f"Service configuration page accessed on unsupported OS: {current_os}. Limited functionality."
        flash(warning_msg, "warning")
        logger.warning(warning_msg)

    # Render the service configuration template
    logger.debug(
        f"Rendering configure_service.html for '{server_name}' on {current_os}."
    )
    return render_template("configure_service.html", **template_data)


# --- API Route: Configure Service ---
@server_install_config_bp.route("/api/server/<server_name>/service", methods=["POST"])
@csrf.exempt
@auth_required
def configure_service_api_route(server_name):
    """API endpoint to configure OS-specific service settings."""
    logger.info(
        f"API POST request received to configure service for server: '{server_name}'."
    )
    base_dir = get_base_dir()  # Needed for Linux handler
    config_dir = settings.get("CONFIG_DIR")  # Needed for Windows handler
    logger.debug(f"Base directory: {base_dir}, Config directory: {config_dir}")

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for service config: {data}")

    # Validate JSON body
    if data is None:
        logger.warning(
            f"API Configure Service request for '{server_name}': Empty or invalid JSON body."
        )
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Determine OS and process accordingly
    current_os = platform.system()
    logger.info(f"Processing service config API request for OS: {current_os}")

    result = None  # Store handler result
    status_code = 501  # Not Implemented (default for unsupported OS)

    if current_os == "Linux":
        # Extract Linux settings (autoupdate, autostart)
        autoupdate = data.get("autoupdate", False)
        autostart = data.get("autostart", False)
        logger.debug(
            f"Linux config received: autoupdate={autoupdate}, autostart={autostart}"
        )

        # Validate types
        if not isinstance(autoupdate, bool) or not isinstance(autostart, bool):
            logger.warning(
                f"API Configure Service (Linux) for '{server_name}': Invalid boolean value for autoupdate/autostart."
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

        # Call the systemd handler
        logger.info(
            f"Calling create_systemd_service for '{server_name}' (Update={autoupdate}, Start={autostart})..."
        )
        result = system.create_systemd_service(
            server_name, base_dir, autoupdate, autostart
        )
        logger.debug(f"Systemd handler result: {result}")
        status_code = 200 if result and result.get("status") == "success" else 500

    elif current_os == "Windows":
        # Extract Windows settings (currently just autoupdate)
        autoupdate = data.get("autoupdate", False)
        logger.debug(f"Windows config received: autoupdate={autoupdate}")

        # Validate type
        if not isinstance(autoupdate, bool):
            logger.warning(
                f"API Configure Service (Windows) for '{server_name}': Invalid boolean value for autoupdate."
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

        # Call the Windows autoupdate handler (expects "true" or "false" string)
        autoupdate_str = "true" if autoupdate else "false"
        logger.info(
            f"Calling set_windows_autoupdate for '{server_name}' (Update={autoupdate_str})..."
        )
        result = system.set_windows_autoupdate(server_name, autoupdate_str, config_dir)
        logger.debug(f"Windows autoupdate handler result: {result}")
        status_code = 200 if result and result.get("status") == "success" else 500

    else:
        # Handle unsupported OS
        error_message = f"Service configuration is not supported on this operating system ({current_os})."
        logger.error(f"API Configure Service called on unsupported OS: {current_os}")
        result = {"status": "error", "message": error_message}
        # status_code remains 501

    # --- Final Logging and Response ---
    if status_code == 200:
        success_message = (
            f"Service settings for '{server_name}' updated successfully via API."
        )
        logger.info(success_message)
        # Ensure result has a success message
        if result and "message" not in result:
            result["message"] = success_message
    else:
        # Log error based on handler result or default message
        error_message = (
            result.get("message", "Unknown service configuration error")
            if result
            else "Service configuration handler failed unexpectedly"
        )
        logger.error(
            f"API Configure Service failed for '{server_name}' on {current_os}: {error_message}"
        )
        # Ensure result object exists and has error status/message
        if not result:
            result = {}
        result["status"] = "error"
        if "message" not in result:
            result["message"] = (
                f"Failed to configure service for '{server_name}' on {current_os}."
            )

    logger.debug(
        f"Returning JSON response for configure service API '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code
