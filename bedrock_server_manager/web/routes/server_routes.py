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

# Initialize logger for this module
logger = logging.getLogger("bedrock_server_manager")

# Create Blueprint for server-related routes
server_bp = Blueprint("server_routes", __name__)


# --- Route: Main Dashboard ---
@server_bp.route("/")
@login_required
def index():
    """Renders the main dashboard page displaying the status of all servers."""
    logger.info("Route '/' accessed - Rendering main dashboard.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get status for all servers using the handler
    logger.debug("Calling get_all_servers_status_handler...")
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)

    if status_response["status"] == "error":
        # Flash an error message if the handler failed
        error_msg = f"Error retrieving server statuses: {status_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
        servers = []  # Provide an empty list to prevent template errors
    else:
        servers = status_response.get("servers", [])
        logger.debug(f"Successfully retrieved status for {len(servers)} servers.")

    # Render the main index template
    logger.debug(f"Rendering index.html with {len(servers)} servers.")
    return render_template("index.html", servers=servers, app_name=app_name)


# --- Route: Manage Servers Page ---
@server_bp.route("/manage_servers")
@login_required
def manage_server_route():
    """Renders the page for managing existing servers (e.g., delete)."""
    logger.info("Route '/manage_servers' accessed - Rendering server management page.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get status for all servers to list them
    logger.debug("Calling get_all_servers_status_handler...")
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)

    if status_response["status"] == "error":
        # Flash an error message if the handler failed
        error_msg = f"Error retrieving server statuses for management page: {status_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
        servers = []  # Provide an empty list
    else:
        servers = status_response.get("servers", [])
        logger.debug(
            f"Successfully retrieved status for {len(servers)} servers for management page."
        )

    # Render the manage servers template
    logger.debug(f"Rendering manage_servers.html with {len(servers)} servers.")
    return render_template("manage_servers.html", servers=servers, app_name=app_name)


# --- Route: Advanced Menu Page ---
@server_bp.route("/advanced_menu")
@login_required
def advanced_menu_route():
    """Renders the advanced menu page listing servers for configuration."""
    logger.info("Route '/advanced_menu' accessed - Rendering advanced menu page.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get status for all servers to populate the dropdown/list
    logger.debug("Calling get_all_servers_status_handler...")
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)

    if status_response["status"] == "error":
        # Flash an error message if the handler failed
        error_msg = f"Error retrieving server statuses for advanced menu: {status_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
        servers = []  # Provide an empty list
    else:
        servers = status_response.get("servers", [])
        logger.debug(
            f"Successfully retrieved status for {len(servers)} servers for advanced menu."
        )

    # Render the advanced menu template
    logger.debug(f"Rendering advanced_menu.html with {len(servers)} servers.")
    return render_template("advanced_menu.html", servers=servers, app_name=app_name)


# --- API Route: Start Server ---
@server_bp.route("/server/<server_name>/start", methods=["POST"])
@login_required
def start_server_route(server_name):
    """API endpoint to start a specific server."""
    logger.info(f"API POST request received to start server: '{server_name}'.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the start server handler
    logger.debug(f"Calling start_server_handler for server '{server_name}'...")
    response = handlers.start_server_handler(server_name, base_dir)
    logger.debug(f"Handler response for start server '{server_name}': {response}")

    # Determine HTTP status code based on handler response
    status_code = 200 if response.get("status") == "success" else 500

    if status_code == 200:
        logger.info(f"Server '{server_name}' start initiated successfully via API.")
        # Ensure a success message exists
        if "message" not in response:
            response["message"] = (
                f"Server '{server_name}' start initiated successfully."
            )
    else:
        logger.error(
            f"API Error starting server '{server_name}': {response.get('message', 'Unknown error')}"
        )
        # Ensure an error message exists
        if "message" not in response:
            response["message"] = f"Error starting server '{server_name}'."
        # Ensure status is 'error'
        response["status"] = "error"

    # Return JSON response
    logger.debug(
        f"Returning JSON response for start server '{server_name}' with status code {status_code}."
    )
    return jsonify(response), status_code


# --- API Route: Stop Server ---
@server_bp.route("/server/<server_name>/stop", methods=["POST"])
@login_required
def stop_server_route(server_name):
    """API endpoint to stop a specific server."""
    logger.info(f"API POST request received to stop server: '{server_name}'.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the stop server handler
    logger.debug(f"Calling stop_server_handler for server '{server_name}'...")
    response = handlers.stop_server_handler(server_name, base_dir)
    logger.debug(f"Handler response for stop server '{server_name}': {response}")

    # Determine HTTP status code
    status_code = 200 if response.get("status") == "success" else 500

    if status_code == 200:
        logger.info(f"Server '{server_name}' stop initiated successfully via API.")
        if "message" not in response:
            response["message"] = f"Server '{server_name}' stop initiated successfully."
    else:
        logger.error(
            f"API Error stopping server '{server_name}': {response.get('message', 'Unknown error')}"
        )
        if "message" not in response:
            response["message"] = f"Error stopping server '{server_name}'."
        response["status"] = "error"

    # Return JSON response
    logger.debug(
        f"Returning JSON response for stop server '{server_name}' with status code {status_code}."
    )
    return jsonify(response), status_code


# --- API Route: Restart Server ---
@server_bp.route("/server/<server_name>/restart", methods=["POST"])
@login_required
def restart_server_route(server_name):
    """API endpoint to restart a specific server."""
    logger.info(f"API POST request received to restart server: '{server_name}'.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the restart server handler
    logger.debug(f"Calling restart_server_handler for server '{server_name}'...")
    response = handlers.restart_server_handler(server_name, base_dir)
    logger.debug(f"Handler response for restart server '{server_name}': {response}")

    # Determine HTTP status code
    status_code = 200 if response.get("status") == "success" else 500

    if status_code == 200:
        logger.info(f"Server '{server_name}' restart initiated successfully via API.")
        if "message" not in response:
            response["message"] = (
                f"Server '{server_name}' restart initiated successfully."
            )
    else:
        logger.error(
            f"API Error restarting server '{server_name}': {response.get('message', 'Unknown error')}"
        )
        if "message" not in response:
            response["message"] = f"Error restarting server '{server_name}'."
        response["status"] = "error"

    # Return JSON response
    logger.debug(
        f"Returning JSON response for restart server '{server_name}' with status code {status_code}."
    )
    return jsonify(response), status_code


# --- API Route: Send Command ---
@server_bp.route("/server/<server_name>/send", methods=["POST"])
@login_required
def send_command_route(server_name):
    """API endpoint to send a command to a running server."""
    logger.info(
        f"API POST request received to send command to server: '{server_name}'."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get JSON data from request
    data = request.get_json()
    logger.debug(f"Received JSON data for send command: {data}")

    # Validate JSON body presence
    if not data or not isinstance(data, dict):
        logger.warning(
            f"API send_command for '{server_name}': Invalid or empty JSON body received."
        )
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract command from JSON data
    command = data.get("command")

    # Validate command presence and type
    if not command or not isinstance(command, str) or not command.strip():
        logger.warning(
            f"API send_command for '{server_name}': Received empty or invalid 'command' field."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Request body must contain a non-empty string 'command' field.",
                }
            ),
            400,  # Bad Request
        )

    trimmed_command = command.strip()
    logger.info(
        f"API attempting to send command to '{server_name}': '{trimmed_command}'"
    )

    # Call the send command handler
    logger.debug(f"Calling send_command_handler for server '{server_name}'...")
    result = handlers.send_command_handler(server_name, trimmed_command, base_dir)
    logger.debug(f"Handler response for send command '{server_name}': {result}")

    # Determine HTTP status code
    status_code = 200 if result.get("status") == "success" else 500

    if status_code == 200:
        logger.info(
            f"Command '{trimmed_command}' sent successfully to '{server_name}' via API."
        )
        if "message" not in result:
            result["message"] = f"Command sent successfully to server '{server_name}'."
    else:
        logger.error(
            f"API Error sending command to '{server_name}': {result.get('message', 'Unknown error')}"
        )
        if "message" not in result:
            result["message"] = f"Error sending command to server '{server_name}'."
        result["status"] = "error"

    # Return JSON response
    logger.debug(
        f"Returning JSON response for send command '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code


# --- API Route: Update Server ---
@server_bp.route("/server/<server_name>/update", methods=["POST"])
@login_required
def update_server_route(server_name):
    """API endpoint to update a specific server's Bedrock software."""
    logger.info(f"API POST request received to update server: '{server_name}'.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the update server handler
    logger.debug(f"Calling update_server_handler for server '{server_name}'...")
    response = handlers.update_server_handler(server_name, base_dir=base_dir)
    logger.debug(f"Handler response for update server '{server_name}': {response}")

    # Determine HTTP status code
    status_code = 200 if response.get("status") == "success" else 500

    if status_code == 200:
        logger.info(f"Server '{server_name}' update initiated successfully via API.")
        if "message" not in response:
            response["message"] = (
                f"Server '{server_name}' update initiated successfully."
            )
    else:
        logger.error(
            f"API Error updating server '{server_name}': {response.get('message', 'Unknown error')}"
        )
        if "message" not in response:
            response["message"] = f"Error updating server '{server_name}'."
        response["status"] = "error"

    # Return JSON response
    logger.debug(
        f"Returning JSON response for update server '{server_name}' with status code {status_code}."
    )
    return jsonify(response), status_code


# --- Route: Install Server Page ---
@server_bp.route("/install", methods=["GET"])
@login_required
def install_server_route():
    """Renders the page for installing a new server."""
    logger.info("Route '/install' accessed - Rendering install server page.")
    # Pass empty strings initially if needed by template value attributes
    return render_template(
        "install.html", server_name="", server_version="", app_name=app_name
    )


# --- API Route: Install Server ---
@server_bp.route("/api/server/install", methods=["POST"])
@login_required
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
    # Call specific format validation handler
    logger.debug(f"Calling validate_server_name_format_handler for '{server_name}'...")
    validation_result = handlers.validate_server_name_format_handler(server_name)
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
                f"Overwrite confirmed for '{server_name}'. Calling delete_server_data_handler..."
            )
            delete_result = handlers.delete_server_data_handler(
                server_name, base_dir, config_dir
            )
            logger.debug(f"Delete handler result for '{server_name}': {delete_result}")
            # If deletion fails, report the error immediately
            if delete_result["status"] == "error":
                error_msg = f"Failed to delete existing server data for '{server_name}': {delete_result.get('message', 'Unknown delete error')}"
                logger.error(f"API Install Server: {error_msg}")
                # Return the delete error directly
                return jsonify({"status": "error", "message": error_msg}), 500

        # Perform the actual installation (for new server or after successful delete)
        logger.info(
            f"Calling install_new_server_handler for '{server_name}' (Version: {server_version})..."
        )
        install_result = handlers.install_new_server_handler(
            server_name, server_version, base_dir, config_dir
        )
        logger.debug(f"Install handler result for '{server_name}': {install_result}")

        # Check the result from the installation handler
        if install_result.get("status") == "success":
            logger.info(f"Server '{server_name}' installed successfully via API.")
            result = install_result  # Use the handler's result
            # Add the URL for the next step in the configuration sequence
            result["next_step_url"] = url_for(
                "server_routes.configure_properties_route",
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


# --- API Route: Delete Server ---
@server_bp.route("/server/<server_name>/delete", methods=["DELETE"])
@login_required
def delete_server_route(server_name):
    """API endpoint to delete a specific server's data."""
    logger.info(f"API DELETE request received to delete server: '{server_name}'.")
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    logger.debug(f"Base directory: {base_dir}, Config directory: {config_dir}")

    # Call the handler to delete the server data
    logger.debug(f"Calling delete_server_data_handler for '{server_name}'...")
    result = handlers.delete_server_data_handler(server_name, base_dir, config_dir)
    logger.debug(f"Delete handler result for '{server_name}': {result}")

    # Determine appropriate HTTP status code
    status_code = 200 if result.get("status") == "success" else 500

    if status_code == 200:
        logger.info(f"Server '{server_name}' deleted successfully via API.")
        if "message" not in result:
            result["message"] = f"Server '{server_name}' deleted successfully."
    else:
        logger.error(
            f"API Error deleting server '{server_name}': {result.get('message', 'Unknown error')}"
        )
        if "message" not in result:
            result["message"] = f"Error deleting server '{server_name}'."
        result["status"] = "error"

    # Return JSON response
    logger.debug(
        f"Returning JSON response for delete server '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code


# --- Route: Configure Server Properties Page ---
@server_bp.route("/server/<server_name>/configure_properties", methods=["GET"])
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
        return redirect(url_for("server_routes.advanced_menu_route"))

    # Check if this is part of a new installation sequence
    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"
    logger.debug(
        f"Processing configure properties for '{server_name}', new_install flag: {new_install}"
    )

    # Read current properties using the handler
    logger.debug(f"Calling read_server_properties_handler for '{server_name}'...")
    properties_response = handlers.read_server_properties_handler(server_name, base_dir)

    # Handle errors from the properties reading handler
    if properties_response["status"] == "error":
        error_msg = f"Error loading properties for '{server_name}': {properties_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
        # Redirect if properties cannot be loaded
        return redirect(url_for("server_routes.advanced_menu_route"))

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
@server_bp.route("/api/server/<server_name>/properties", methods=["POST"])
@login_required
def configure_properties_api_route(server_name):
    """API endpoint to validate and update server.properties."""
    logger.info(
        f"API POST request received to configure properties for server: '{server_name}'."
    )
    base_dir = get_base_dir()
    # Note: config_dir isn't directly used here but might be needed if handlers change
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
        validation_response = handlers.validate_property_value_handler(key, value_str)
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
        f"Calling modify_server_properties_handler for '{server_name}' with validated properties..."
    )
    logger.debug(f"Properties to update: {properties_to_update}")
    modify_response = handlers.modify_server_properties_handler(
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
@server_bp.route("/server/<server_name>/configure_allowlist", methods=["GET"])
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
    logger.debug(
        f"Calling configure_allowlist_handler (read mode) for '{server_name}'..."
    )
    # Calling with new_players_data=None makes it read the existing list
    result = handlers.configure_allowlist_handler(
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


# --- API Route: Add Players to Allowlist ---
@server_bp.route("/api/server/<server_name>/allowlist/add", methods=["POST"])
@login_required
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
    new_players_data_for_handler = [
        {"name": name, "ignoresPlayerLimit": ignore_limit}
        for name in valid_player_names
    ]
    logger.debug(
        f"Data formatted for configure_allowlist_handler (add mode): {new_players_data_for_handler}"
    )

    # Call the handler to add/update players
    result = handlers.configure_allowlist_handler(
        server_name, base_dir, new_players_data=new_players_data_for_handler
    )
    logger.debug(f"Add allowlist handler response for '{server_name}': {result}")

    # Determine status code based on handler result
    status_code = 200 if result and result.get("status") == "success" else 500

    if status_code == 200:
        added_count = len(result.get("added_players", []))
        updated_count = len(result.get("updated_players", []))
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
@server_bp.route("/api/server/<server_name>/allowlist", methods=["GET"])
@login_required
def get_allowlist_api_route(server_name):
    """API endpoint to retrieve the current server allowlist."""
    logger.info(f"API GET request received for allowlist for server: '{server_name}'.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the handler in read mode (new_players_data=None)
    logger.debug(
        f"Calling configure_allowlist_handler (read mode) for '{server_name}'..."
    )
    result = handlers.configure_allowlist_handler(
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
@server_bp.route("/server/<server_name>/configure_permissions", methods=["GET"])
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
    # Using get_players_from_json_handler for consistency with previous logic
    logger.debug(
        "Calling get_players_from_json_handler to get known player names/xuids..."
    )
    players_response = handlers.get_players_from_json_handler()
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
@server_bp.route("/api/server/<server_name>/permissions", methods=["PUT"])
@login_required
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
            f"Calling configure_player_permission_handler for Player: '{player_name}' (XUID: {xuid}), Level: '{level}'..."
        )

        # Call the handler that updates permissions.json for a single player
        # NOTE: Assumes this handler correctly reads, updates, and writes permissions.json
        result = handlers.configure_player_permission_handler(
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
                    "errors": handler_errors,  # Map of xuid: error message from handlers
                }
            ),
            500,  # Internal Server Error because one or more handler actions failed
        )


# --- Route: Configure Service Page ---
@server_bp.route("/server/<server_name>/configure_service", methods=["GET"])
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
        # For Linux, systemd service might not directly store these in simple config.
        # The handler `create_systemd_service_handler` creates/updates the service file.
        # We might need a way to *read* the current state if we want to pre-populate accurately,
        # but for now, we'll just show the form elements with defaults.
        # TODO: Implement a handler to read current systemd service settings if needed for accurate display.
        logger.debug(
            "Preparing to render configure_service.html for Linux (defaults will be shown in form)."
        )
        # template_data['autoupdate'] = handlers.get_systemd_setting(server_name, 'autoupdate') # Hypothetical getter
        # template_data['autostart'] = handlers.get_systemd_setting(server_name, 'autostart') # Hypothetical getter

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
@server_bp.route("/api/server/<server_name>/service", methods=["POST"])
@login_required
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
            f"Calling create_systemd_service_handler for '{server_name}' (Update={autoupdate}, Start={autostart})..."
        )
        result = handlers.create_systemd_service_handler(
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
            f"Calling set_windows_autoupdate_handler for '{server_name}' (Update={autoupdate_str})..."
        )
        result = handlers.set_windows_autoupdate_handler(
            server_name, autoupdate_str, config_dir
        )
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


# --- Route: Backup Menu Page ---
@server_bp.route("/server/<server_name>/backup", methods=["GET"])
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
@server_bp.route("/server/<server_name>/backup/config", methods=["GET"])
@login_required
def backup_config_select_route(server_name):
    """Renders the page for selecting specific config files to backup."""
    # Note: This route currently just renders a template.
    # The actual selection might happen via JS or another mechanism in the template.
    # If dynamic listing of config files is needed, this route would need to call a handler.
    logger.info(
        f"Route '/server/{server_name}/backup/config' accessed - Rendering config backup options page."
    )
    # TODO: Potentially list available config files here by calling a handler.
    return render_template(
        "backup_config_options.html", server_name=server_name, app_name=app_name
    )


# --- API Route: Backup Action ---
@server_bp.route("/server/<server_name>/backup/action", methods=["POST"])
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
        result = handlers.backup_world_handler(server_name, base_dir)
    elif backup_type == "config":
        logger.debug(
            f"Calling backup_config_file_handler for '{server_name}', file: '{file_to_backup}'..."
        )
        result = handlers.backup_config_file_handler(
            server_name, file_to_backup, base_dir
        )
    elif backup_type == "all":
        logger.debug(f"Calling backup_all_handler for '{server_name}'...")
        result = handlers.backup_all_handler(server_name, base_dir)
    # No else needed due to prior validation

    logger.debug(
        f"Backup handler response for '{server_name}' (type: {backup_type}): {result}"
    )

    # --- Determine Status Code and Final Response ---
    # Backups can take time. 200 OK implies synchronous completion reported by handler.
    # 202 Accepted might be better if handlers initiate background tasks. Assuming 200 for now.
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
@server_bp.route("/server/<server_name>/restore", methods=["GET"])
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
@server_bp.route("/server/<server_name>/restore/action", methods=["POST"])
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
        result = handlers.restore_world_handler(server_name, backup_file, base_dir)
    elif restore_type == "config":
        # Note: Restoring a specific config file might require more complex logic
        # if the backup contains multiple files. Assuming the handler manages this.
        logger.debug(
            f"Calling restore_config_file_handler for '{server_name}', file: '{backup_file}'..."
        )
        result = handlers.restore_config_file_handler(
            server_name, backup_file, base_dir
        )
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
@server_bp.route("/server/<server_name>/restore/select", methods=["POST"])
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
            url_for("server_routes.restore_menu_route", server_name=server_name)
        )

    logger.info(
        f"Listing available backups of type '{restore_type}' for server: '{server_name}'..."
    )

    # Call the handler to list available backups of the specified type
    logger.debug(
        f"Calling list_backups_handler for '{server_name}', type: '{restore_type}'..."
    )
    list_response = handlers.list_backups_handler(server_name, restore_type, base_dir)
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
            url_for("server_routes.restore_menu_route", server_name=server_name)
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
@server_bp.route("/server/<server_name>/restore/all", methods=["POST"])
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
    result = handlers.restore_all_handler(server_name, base_dir)
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


# --- Route: Install Content Menu Page ---
@server_bp.route("/install_content")
@login_required
def install_content_menu_route():
    """Renders the menu page for installing content (worlds, addons)."""
    logger.info(
        "Route '/install_content' accessed - Rendering content installation menu."
    )
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Get server list for the dropdown selector
    logger.debug("Calling get_all_servers_status_handler for server list...")
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)

    if status_response["status"] == "error":
        error_msg = f"Error retrieving server list for content installation menu: {status_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
        servers = []  # Provide empty list
    else:
        servers = status_response.get("servers", [])
        logger.debug(f"Successfully retrieved {len(servers)} servers for content menu.")

    # Render the content installation menu template
    logger.debug(f"Rendering install_content.html with {len(servers)} servers.")
    return render_template("install_content.html", servers=servers, app_name=app_name)


# --- Route: Install World Selection Page ---
@server_bp.route("/server/<server_name>/install_world")
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
@server_bp.route("/api/server/<server_name>/world/install", methods=["POST"])
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
@server_bp.route("/server/<server_name>/install_addon")
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
@server_bp.route("/api/server/<server_name>/addon/install", methods=["POST"])
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


# --- Route: Server Monitor Page ---
@server_bp.route("/server/<server_name>/monitor")
@login_required
def monitor_server_route(server_name):
    """Displays the server monitoring page (e.g., for console output, status)."""
    logger.info(
        f"Route '/server/{server_name}/monitor' accessed - Rendering monitoring page."
    )
    # The monitor page likely uses JavaScript to poll the status API,
    # so this route just needs to render the template.
    return render_template("monitor.html", server_name=server_name, app_name=app_name)


# --- API Route: Server Status ---
@server_bp.route("/api/server/<server_name>/status")
@login_required
def server_status_api(server_name):
    """API endpoint providing server status information (running state, resource usage) as JSON."""
    logger.debug(f"API GET request for status of server: '{server_name}'.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the handler to get process information
    logger.debug(f"Calling get_bedrock_process_info_handler for '{server_name}'...")
    result = handlers.get_bedrock_process_info_handler(server_name, base_dir)
    logger.debug(f"Get process info handler result for '{server_name}': {result}")

    # This handler likely returns data regardless of success/error status internally
    # (e.g., status might be 'stopped', 'running', or 'error retrieving').
    # We'll return 200 OK as long as the handler executed.
    status_code = 200
    logger.debug(
        f"Returning JSON response for server status API '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code


# --- Route: Schedule Tasks Page (Linux/Cron) ---
@server_bp.route("/server/<server_name>/schedule", methods=["GET"])
@login_required
def schedule_tasks_route(server_name):
    """Displays the Linux cron job scheduling page for a server."""
    logger.info(
        f"Route '/server/{server_name}/schedule' accessed - Rendering Linux cron task schedule page."
    )

    # Check OS - redirect if not Linux? Or just show an error? For now, assume access implies Linux.
    if platform.system() != "Linux":
        flash("Cron job scheduling is only available on Linux.", "warning")
        logger.warning(
            f"Attempted to access Linux cron schedule page for '{server_name}' on non-Linux OS."
        )
        # Optionally redirect: return redirect(url_for('server_routes.index'))

    # Get current cron jobs related to this server using the handler
    logger.debug(f"Calling get_server_cron_jobs_handler for '{server_name}'...")
    cron_jobs_response = handlers.get_server_cron_jobs_handler(server_name)
    logger.debug(f"Get cron jobs handler response: {cron_jobs_response}")

    table_data = []  # Default empty list for template
    if cron_jobs_response["status"] == "error":
        error_msg = f"Error retrieving cron jobs for '{server_name}': {cron_jobs_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
    else:
        cron_jobs = cron_jobs_response.get("cron_jobs", [])  # List of raw cron strings
        logger.debug(f"Found {len(cron_jobs)} raw cron job lines for '{server_name}'.")
        # Get formatted table data using the formatting handler
        logger.debug(f"Calling get_cron_jobs_table_handler...")
        table_response = handlers.get_cron_jobs_table_handler(cron_jobs)
        logger.debug(f"Format cron jobs handler response: {table_response}")
        if table_response["status"] == "error":
            error_msg = f"Error formatting cron jobs table for '{server_name}': {table_response.get('message', 'Unknown error')}"
            flash(error_msg, "error")
            logger.error(error_msg)
        else:
            table_data = table_response.get("table_data", [])
            logger.debug(
                f"Successfully formatted {len(table_data)} cron jobs for display."
            )

    # Render the Linux scheduling template
    logger.debug(f"Rendering schedule_tasks.html for '{server_name}'.")
    return render_template(
        "schedule_tasks.html",
        server_name=server_name,
        table_data=table_data,  # Pass formatted data for table display
        EXPATH=EXPATH,  # Pass executable path if needed by template
        app_name=app_name,
    )


# --- API Route: Add Cron Job ---
# Note: These cron routes might need refinement based on how server-specific jobs are managed.
# Currently, they seem to operate on the system's crontab directly via handlers.
@server_bp.route("/server/<server_name>/schedule/add", methods=["POST"])
@login_required
def add_cron_job_route(server_name):
    """API endpoint to add a new cron job."""
    # The server_name is in the URL but might not be strictly needed by the handler if it adds globally?
    logger.info(
        f"API POST request received to add cron job (context: server '{server_name}')."
    )

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for add cron job: {data}")

    if not data or not isinstance(data, dict):
        logger.warning(f"API Add Cron Job request: Empty or invalid JSON body.")
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract the full cron job string
    cron_string = data.get("new_cron_job")
    logger.debug(f"Cron string received: '{cron_string}'")

    if not cron_string or not isinstance(cron_string, str) or not cron_string.strip():
        logger.warning(
            f"API Add Cron Job request: Missing or empty 'new_cron_job' string."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Cron job string ('new_cron_job') is required.",
                }
            ),
            400,
        )

    cron_string = cron_string.strip()  # Use trimmed string

    logger.info(f"Attempting to add cron job via handler: '{cron_string}'")
    # Call the handler to add the job
    logger.debug("Calling add_cron_job_handler...")
    add_response = handlers.add_cron_job_handler(cron_string)
    logger.debug(f"Add cron job handler response: {add_response}")

    # Determine status code
    status_code = (
        200 if add_response and add_response.get("status") == "success" else 500
    )

    if status_code == 200:
        logger.info(f"Cron job added successfully via API: '{cron_string}'")
        if add_response and "message" not in add_response:
            add_response["message"] = "Cron job added successfully."
    else:
        error_message = (
            add_response.get("message", "Unknown error adding cron job")
            if add_response
            else "Add cron handler failed unexpectedly"
        )
        logger.error(f"API Add Cron Job failed: {error_message}")
        if not add_response:
            add_response = {}
        add_response["status"] = "error"
        if "message" not in add_response:
            add_response["message"] = "Failed to add cron job."

    logger.debug(
        f"Returning JSON response for add cron job API with status code {status_code}."
    )
    return jsonify(add_response), status_code


# --- API Route: Modify Cron Job ---
@server_bp.route("/server/<server_name>/schedule/modify", methods=["POST"])
@login_required
def modify_cron_job_route(server_name):
    """API endpoint to modify an existing cron job."""
    logger.info(
        f"API POST request received to modify cron job (context: server '{server_name}')."
    )

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for modify cron job: {data}")

    if not data or not isinstance(data, dict):
        logger.warning(f"API Modify Cron Job request: Empty or invalid JSON body.")
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract old and new cron strings
    old_cron_string = data.get("old_cron_job")
    new_cron_string = data.get("new_cron_job")
    logger.debug(
        f"Old cron string: '{old_cron_string}', New cron string: '{new_cron_string}'"
    )

    # Validate presence
    if (
        not old_cron_string
        or not isinstance(old_cron_string, str)
        or not old_cron_string.strip()
    ):
        logger.warning(
            f"API Modify Cron Job request: Missing or empty 'old_cron_job' string."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Original cron job string ('old_cron_job') is required.",
                }
            ),
            400,
        )
    if (
        not new_cron_string
        or not isinstance(new_cron_string, str)
        or not new_cron_string.strip()
    ):
        logger.warning(
            f"API Modify Cron Job request: Missing or empty 'new_cron_job' string."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "New cron job string ('new_cron_job') is required.",
                }
            ),
            400,
        )

    old_cron_string = old_cron_string.strip()
    new_cron_string = new_cron_string.strip()

    logger.info(
        f"Attempting to modify cron job via handler. From: '{old_cron_string}' To: '{new_cron_string}'"
    )
    # Call the handler to modify the job
    logger.debug("Calling modify_cron_job_handler...")
    modify_response = handlers.modify_cron_job_handler(old_cron_string, new_cron_string)
    logger.debug(f"Modify cron job handler response: {modify_response}")

    # Determine status code
    status_code = (
        200 if modify_response and modify_response.get("status") == "success" else 500
    )

    if status_code == 200:
        logger.info(
            f"Cron job modified successfully via API. Old: '{old_cron_string}', New: '{new_cron_string}'"
        )
        if modify_response and "message" not in modify_response:
            modify_response["message"] = "Cron job modified successfully."
    else:
        error_message = (
            modify_response.get("message", "Unknown error modifying cron job")
            if modify_response
            else "Modify cron handler failed unexpectedly"
        )
        logger.error(f"API Modify Cron Job failed: {error_message}")
        if not modify_response:
            modify_response = {}
        modify_response["status"] = "error"
        if "message" not in modify_response:
            modify_response["message"] = "Failed to modify cron job."

    logger.debug(
        f"Returning JSON response for modify cron job API with status code {status_code}."
    )
    return jsonify(modify_response), status_code


# --- API Route: Delete Cron Job ---
@server_bp.route("/server/<server_name>/schedule/delete", methods=["POST"])
@login_required
def delete_cron_job_route(server_name):
    """API endpoint to delete a specific cron job."""
    logger.info(
        f"API POST request received to delete cron job (context: server '{server_name}')."
    )

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for delete cron job: {data}")

    if not data or not isinstance(data, dict):
        logger.warning(f"API Delete Cron Job request: Empty or invalid JSON body.")
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract the cron job string to delete
    cron_string = data.get("cron_string")
    logger.debug(f"Cron string to delete: '{cron_string}'")

    if not cron_string or not isinstance(cron_string, str) or not cron_string.strip():
        logger.warning(f"API Delete Cron Job request: Missing or empty 'cron_string'.")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Cron job string ('cron_string') is required.",
                }
            ),
            400,
        )

    cron_string = cron_string.strip()

    logger.info(f"Attempting to delete cron job via handler: '{cron_string}'")
    # Call the handler to delete the job
    logger.debug("Calling delete_cron_job_handler...")
    delete_response = handlers.delete_cron_job_handler(cron_string)
    logger.debug(f"Delete cron job handler response: {delete_response}")

    # Determine status code
    status_code = (
        200 if delete_response and delete_response.get("status") == "success" else 500
    )

    if status_code == 200:
        logger.info(f"Cron job deleted successfully via API: '{cron_string}'")
        if delete_response and "message" not in delete_response:
            delete_response["message"] = "Cron job deleted successfully."
    else:
        error_message = (
            delete_response.get("message", "Unknown error deleting cron job")
            if delete_response
            else "Delete cron handler failed unexpectedly"
        )
        logger.error(f"API Delete Cron Job failed: {error_message}")
        if not delete_response:
            delete_response = {}
        delete_response["status"] = "error"
        if "message" not in delete_response:
            delete_response["message"] = "Failed to delete cron job."

    logger.debug(
        f"Returning JSON response for delete cron job API with status code {status_code}."
    )
    return jsonify(delete_response), status_code


# --- Route: Schedule Tasks Page (Windows) ---
@server_bp.route("/server/<server_name>/tasks", methods=["GET"])
@login_required
def schedule_tasks_windows_route(server_name):
    """Displays the Windows Task Scheduler management page for a server."""
    logger.info(
        f"Route '/server/{server_name}/tasks' accessed - Rendering Windows task schedule page."
    )
    base_dir = get_base_dir()  # Needed? Not directly used here.
    config_dir = settings.get("CONFIG_DIR")
    logger.debug(f"Config directory: {config_dir}")

    # Ensure this is running on Windows
    if platform.system() != "Windows":
        flash("Windows Task Scheduling is only available on Windows.", "error")
        logger.error(
            f"Attempted to access Windows task scheduler page for '{server_name}' from non-Windows OS."
        )
        return redirect(url_for("server_routes.index"))  # Redirect away if not Windows

    # Get task names associated with this server from the config directory
    logger.debug(f"Calling get_server_task_names_handler for '{server_name}'...")
    task_names_response = handlers.get_server_task_names_handler(
        server_name, config_dir
    )
    logger.debug(f"Get task names handler response: {task_names_response}")

    tasks = []  # Default empty list for template
    if task_names_response["status"] == "error":
        error_msg = f"Error retrieving associated task names for '{server_name}': {task_names_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
    else:
        # Extract just the names from the handler response (which might include paths)
        task_names = [task[0] for task in task_names_response.get("task_names", [])]
        logger.debug(
            f"Found {len(task_names)} task names associated with '{server_name}': {task_names}"
        )

        if task_names:
            # Get detailed information for these tasks using the handler
            logger.debug(
                f"Calling get_windows_task_info_handler for tasks: {task_names}..."
            )
            task_info_response = handlers.get_windows_task_info_handler(task_names)
            logger.debug(f"Get task info handler response: {task_info_response}")

            if task_info_response["status"] == "error":
                error_msg = f"Error retrieving task details for '{server_name}': {task_info_response.get('message', 'Unknown error')}"
                flash(error_msg, "error")
                logger.error(error_msg)
            else:
                tasks = task_info_response.get("task_info", [])
                logger.debug(
                    f"Successfully retrieved details for {len(tasks)} Windows tasks."
                )
        else:
            logger.info(
                f"No Windows tasks found associated with server '{server_name}'."
            )

    # Render the Windows scheduling template
    logger.debug(f"Rendering schedule_tasks_windows.html for '{server_name}'.")
    return render_template(
        "schedule_tasks_windows.html",
        server_name=server_name,
        tasks=tasks,  # Pass the list of task detail dictionaries
        app_name=app_name,
    )


# --- Route: Add Windows Task Page ---
# Uses GET to display form, POST to handle submission
@server_bp.route("/server/<server_name>/tasks/add", methods=["GET", "POST"])
@login_required
def add_windows_task_route(server_name):
    """Displays form (GET) or handles submission (POST) for adding a new Windows scheduled task."""
    logger.info(
        f"Route '/server/{server_name}/tasks/add' accessed, method: {request.method}."
    )
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    logger.debug(f"Base directory: {base_dir}, Config directory: {config_dir}")

    # Ensure Windows OS
    if platform.system() != "Windows":
        flash("Windows Task Scheduling is only available on Windows.", "error")
        logger.error(
            f"Attempted to access add Windows task page for '{server_name}' from non-Windows OS."
        )
        return redirect(url_for("server_routes.index"))

    # Handle POST request (form submission)
    if request.method == "POST":
        logger.info(f"Processing POST request to add Windows task for '{server_name}'.")
        try:
            # Extract common task parameters
            command = request.form.get("command")
            logger.debug(f"Form data - command: '{command}'")

            # Determine command arguments based on selected command
            command_args = f"--server {server_name}"  # Default args
            valid_commands = [
                "update-server",
                "backup-all",
                "start-server",
                "stop-server",
                "restart-server",
                "scan-players",
            ]
            if command not in valid_commands:
                flash(
                    "Invalid command selected. Please choose a valid task action.",
                    "error",
                )
                logger.warning(
                    f"Invalid command '{command}' selected for Windows task creation."
                )
                # Re-render form on validation error
                return render_template(
                    "add_windows_task.html", server_name=server_name, app_name=app_name
                )

            if command == "scan-players":
                command_args = (
                    ""  # Scan players might not need server arg? Check handler.
                )

            logger.debug(f"Determined command_args: '{command_args}'")

            # Generate a task name (ensure uniqueness or handle collisions)
            task_name_base = command.replace(
                "-", "_"
            )  # Convert command to snake_case for task name
            task_name = f"bedrock_{server_name}_{task_name_base}"
            # TODO: Consider adding a timestamp or check for existing task_name to prevent collisions if needed.
            logger.debug(f"Generated task name: '{task_name}'")

            # --- Process Trigger Data ---
            triggers = []
            trigger_num = 1
            logger.debug("Parsing trigger data from form...")
            while (
                True
            ):  # Loop through potential trigger sections in the form (trigger_1, trigger_2, ...)
                trigger_type = request.form.get(f"trigger_type_{trigger_num}")
                if not trigger_type:
                    logger.debug(
                        f"No trigger data found for trigger number {trigger_num}. Stopping trigger parsing."
                    )
                    break  # No more triggers found in form

                logger.debug(f"Processing trigger {trigger_num}: Type='{trigger_type}'")
                trigger_data = {"type": trigger_type}

                # Get common start time/date
                start_datetime = request.form.get(f"start_{trigger_num}")
                if not start_datetime:
                    flash(
                        f"Missing start date/time for trigger {trigger_num}.", "error"
                    )
                    logger.warning(f"Missing start datetime for trigger {trigger_num}.")
                    # Re-render form on validation error
                    return render_template(
                        "add_windows_task.html",
                        server_name=server_name,
                        app_name=app_name,
                    )
                trigger_data["start"] = start_datetime
                logger.debug(f"Trigger {trigger_num} - Start: '{start_datetime}'")

                # Get type-specific details
                if trigger_type == "Daily":
                    interval_str = request.form.get(f"interval_{trigger_num}")
                    if (
                        not interval_str
                        or not interval_str.isdigit()
                        or int(interval_str) < 1
                    ):
                        flash(
                            f"Invalid daily interval for trigger {trigger_num}. Must be a positive number.",
                            "error",
                        )
                        logger.warning(
                            f"Invalid daily interval '{interval_str}' for trigger {trigger_num}."
                        )
                        return render_template(
                            "add_windows_task.html",
                            server_name=server_name,
                            app_name=app_name,
                        )
                    trigger_data["interval"] = int(interval_str)
                    logger.debug(
                        f"Trigger {trigger_num} - Daily Interval: {trigger_data['interval']}"
                    )
                elif trigger_type == "Weekly":
                    interval_str = request.form.get(f"interval_{trigger_num}")
                    days_of_week_str = request.form.get(
                        f"days_of_week_{trigger_num}", ""
                    )
                    if (
                        not interval_str
                        or not interval_str.isdigit()
                        or int(interval_str) < 1
                    ):
                        flash(
                            f"Invalid weekly interval for trigger {trigger_num}. Must be a positive number.",
                            "error",
                        )
                        logger.warning(
                            f"Invalid weekly interval '{interval_str}' for trigger {trigger_num}."
                        )
                        return render_template(
                            "add_windows_task.html",
                            server_name=server_name,
                            app_name=app_name,
                        )
                    trigger_data["interval"] = int(interval_str)
                    trigger_data["days"] = [
                        day.strip()
                        for day in days_of_week_str.split(",")
                        if day.strip()
                    ]
                    if not trigger_data["days"]:
                        flash(
                            f"At least one day must be selected for weekly trigger {trigger_num}.",
                            "error",
                        )
                        logger.warning(
                            f"No days selected for weekly trigger {trigger_num}."
                        )
                        return render_template(
                            "add_windows_task.html",
                            server_name=server_name,
                            app_name=app_name,
                        )
                    logger.debug(
                        f"Trigger {trigger_num} - Weekly Interval: {trigger_data['interval']}, Days: {trigger_data['days']}"
                    )
                elif trigger_type == "Monthly":
                    # Add validation for monthly triggers if needed (days, months)
                    days_of_month_str = request.form.get(
                        f"days_of_month_{trigger_num}", ""
                    )
                    months_str = request.form.get(f"months_{trigger_num}", "")
                    trigger_data["days"] = [
                        int(day.strip())
                        for day in days_of_month_str.split(",")
                        if day.strip().isdigit()
                    ]
                    trigger_data["months"] = [
                        month.strip()
                        for month in months_str.split(",")
                        if month.strip()
                    ]
                    # Add validation checks for days/months if necessary
                    logger.debug(
                        f"Trigger {trigger_num} - Monthly Days: {trigger_data['days']}, Months: {trigger_data['months']}"
                    )

                triggers.append(trigger_data)
                trigger_num += 1

            if not triggers:
                flash("At least one trigger must be defined for the task.", "error")
                logger.warning(
                    f"No triggers were defined for the new task '{task_name}'."
                )
                return render_template(
                    "add_windows_task.html", server_name=server_name, app_name=app_name
                )

            logger.debug(f"Parsed triggers for task creation: {triggers}")

            # --- Call handler to create the task ---
            logger.info(
                f"Calling create_windows_task_handler for task '{task_name}'..."
            )
            result = handlers.create_windows_task_handler(
                server_name=server_name,
                command=command,
                command_args=command_args,
                task_name=task_name,
                config_dir=config_dir,
                triggers=triggers,
                base_dir=base_dir,  # Pass base_dir if handler needs it
            )
            logger.debug(f"Create task handler result: {result}")

            # Handle handler response
            if result["status"] == "success":
                success_msg = f"Windows task '{task_name}' added successfully for server '{server_name}'!"
                flash(success_msg, "success")
                logger.info(success_msg)
                # Redirect to the task list page on success
                return redirect(
                    url_for(
                        "server_routes.schedule_tasks_windows_route",
                        server_name=server_name,
                    )
                )
            else:
                error_msg = f"Error adding Windows task '{task_name}': {result.get('message', 'Unknown handler error')}"
                flash(error_msg, "error")
                logger.error(error_msg)
                # Re-render the form, potentially pre-filling with submitted data (complex)
                # For simplicity, just re-render the blank form with the error message.
                return render_template(
                    "add_windows_task.html", server_name=server_name, app_name=app_name
                )

        except Exception as e:
            # Catch unexpected errors during form processing
            error_msg = f"An unexpected error occurred while processing the task creation form: {e}"
            flash(error_msg, "error")
            logger.exception(error_msg)  # Log full traceback
            return render_template(
                "add_windows_task.html", server_name=server_name, app_name=app_name
            )

    # Handle GET request (display the form)
    logger.debug(f"Rendering add_windows_task.html form for '{server_name}'.")
    return render_template(
        "add_windows_task.html", server_name=server_name, app_name=app_name
    )


# --- Helper Function for Modify Task Route ---
def _load_existing_task_data_for_modify(xml_file_path):
    """Helper to load task details for the modify form."""
    logger.debug(f"Loading existing task data from XML: {xml_file_path}")
    if not os.path.exists(xml_file_path):
        logger.error(f"Task XML file not found: {xml_file_path}")
        return {"error": "Task configuration file not found."}

    # Call handler to parse XML
    result = handlers.get_windows_task_details_handler(xml_file_path)
    if result.get("status") == "error":
        logger.error(f"Error parsing task XML {xml_file_path}: {result.get('message')}")
        return {"error": result.get("message", "Failed to parse task configuration.")}

    logger.debug(f"Successfully loaded task data from XML: {result}")
    # Return the dictionary containing 'command', 'triggers', etc.
    return result


# --- Route: Modify Windows Task Page ---
@server_bp.route(
    "/server/<server_name>/tasks/modify/<task_name>", methods=["GET", "POST"]
)
@login_required
def modify_windows_task_route(server_name, task_name):
    """Displays form (GET) or handles submission (POST) for modifying an existing Windows task."""
    logger.info(
        f"Route '/server/{server_name}/tasks/modify/{task_name}' accessed, method: {request.method}."
    )
    base_dir = get_base_dir()
    config_dir = settings.CONFIG_DIR  # Use attribute access if possible
    xml_file_path = os.path.join(config_dir, server_name, f"{task_name}.xml")
    logger.debug(
        f"Base directory: {base_dir}, Config directory: {config_dir}, XML path: {xml_file_path}"
    )

    # Ensure Windows OS
    if platform.system() != "Windows":
        flash("Windows Task Scheduling is only available on Windows.", "error")
        logger.error(
            f"Attempted to access modify Windows task page for '{task_name}' from non-Windows OS."
        )
        return redirect(url_for("server_routes.index"))

    # Handle POST request (form submission for modification)
    if request.method == "POST":
        logger.info(
            f"Processing POST request to modify Windows task '{task_name}' for '{server_name}'."
        )
        try:
            # Extract command from form
            command = request.form.get("command")
            logger.debug(f"Form data - command: '{command}'")

            # Determine command arguments (similar logic to add route)
            command_args = f"--server {server_name}"
            valid_commands = [
                "update-server",
                "backup-all",
                "start-server",
                "stop-server",
                "restart-server",
                "scan-players",
            ]
            if command not in valid_commands:
                flash("Invalid command selected.", "error")
                logger.warning(
                    f"Invalid command '{command}' selected for Windows task modification."
                )
                # Reload existing data to re-render form with error
                existing_task_data = _load_existing_task_data_for_modify(xml_file_path)
                return render_template(
                    "modify_windows_task.html",
                    server_name=server_name,
                    task_name=task_name,
                    **existing_task_data,
                    app_name=app_name,
                )

            if command == "scan-players":
                command_args = ""
            logger.debug(f"Determined command_args: '{command_args}'")

            # Generate the potentially new task name based on the selected command
            new_task_name_base = command.replace("-", "_")
            new_task_name = f"bedrock_{server_name}_{new_task_name_base}"
            logger.debug(
                f"New task name based on selected command: '{new_task_name}' (Old name: '{task_name}')"
            )

            # --- Process Trigger Data (similar logic to add route) ---
            triggers = []
            trigger_num = 1
            logger.debug("Parsing trigger data from modification form...")
            # (Include the same trigger parsing and validation as in the add route)
            while True:
                trigger_type = request.form.get(f"trigger_type_{trigger_num}")
                if not trigger_type:
                    break
                logger.debug(f"Processing trigger {trigger_num}: Type='{trigger_type}'")
                trigger_data = {"type": trigger_type}
                start_datetime = request.form.get(f"start_{trigger_num}")
                if not start_datetime:
                    flash(
                        f"Missing start date/time for trigger {trigger_num}.", "error"
                    )
                    logger.warning(
                        f"Missing start datetime for trigger {trigger_num} during modification."
                    )
                    existing_task_data = _load_existing_task_data_for_modify(
                        xml_file_path
                    )
                    return render_template(
                        "modify_windows_task.html",
                        server_name=server_name,
                        task_name=task_name,
                        **existing_task_data,
                        app_name=app_name,
                    )
                trigger_data["start"] = start_datetime
                if trigger_type == "Daily":
                    interval_str = request.form.get(f"interval_{trigger_num}")
                    if (
                        not interval_str
                        or not interval_str.isdigit()
                        or int(interval_str) < 1
                    ):
                        flash(
                            f"Invalid daily interval for trigger {trigger_num}.",
                            "error",
                        )
                        existing_task_data = _load_existing_task_data_for_modify(
                            xml_file_path
                        )
                        return render_template(
                            "modify_windows_task.html",
                            server_name=server_name,
                            task_name=task_name,
                            **existing_task_data,
                            app_name=app_name,
                        )
                    trigger_data["interval"] = int(interval_str)
                elif trigger_type == "Weekly":
                    interval_str = request.form.get(f"interval_{trigger_num}")
                    days_of_week_str = request.form.get(
                        f"days_of_week_{trigger_num}", ""
                    )
                    if (
                        not interval_str
                        or not interval_str.isdigit()
                        or int(interval_str) < 1
                    ):
                        flash(
                            f"Invalid weekly interval for trigger {trigger_num}.",
                            "error",
                        )
                        existing_task_data = _load_existing_task_data_for_modify(
                            xml_file_path
                        )
                        return render_template(
                            "modify_windows_task.html",
                            server_name=server_name,
                            task_name=task_name,
                            **existing_task_data,
                            app_name=app_name,
                        )
                    trigger_data["interval"] = int(interval_str)
                    trigger_data["days"] = [
                        day.strip()
                        for day in days_of_week_str.split(",")
                        if day.strip()
                    ]
                    if not trigger_data["days"]:
                        flash(
                            f"At least one day must be selected for weekly trigger {trigger_num}.",
                            "error",
                        )
                        existing_task_data = _load_existing_task_data_for_modify(
                            xml_file_path
                        )
                        return render_template(
                            "modify_windows_task.html",
                            server_name=server_name,
                            task_name=task_name,
                            **existing_task_data,
                            app_name=app_name,
                        )
                elif trigger_type == "Monthly":
                    days_of_month_str = request.form.get(
                        f"days_of_month_{trigger_num}", ""
                    )
                    months_str = request.form.get(f"months_{trigger_num}", "")
                    trigger_data["days"] = [
                        int(day.strip())
                        for day in days_of_month_str.split(",")
                        if day.strip().isdigit()
                    ]
                    trigger_data["months"] = [
                        month.strip()
                        for month in months_str.split(",")
                        if month.strip()
                    ]
                triggers.append(trigger_data)
                trigger_num += 1

            if not triggers:
                flash("At least one trigger must be defined for the task.", "error")
                logger.warning(
                    f"No triggers were defined during modification of task '{task_name}'."
                )
                existing_task_data = _load_existing_task_data_for_modify(xml_file_path)
                return render_template(
                    "modify_windows_task.html",
                    server_name=server_name,
                    task_name=task_name,
                    **existing_task_data,
                    app_name=app_name,
                )

            logger.debug(f"Parsed triggers for task modification: {triggers}")

            # --- Call handler to modify the task ---
            # This handler needs to potentially delete the old task and create the new one
            logger.info(
                f"Calling modify_windows_task_handler for old task '{task_name}', new task '{new_task_name}'..."
            )
            result = handlers.modify_windows_task_handler(
                old_task_name=task_name,  # Pass the original task name
                server_name=server_name,
                command=command,
                command_args=command_args,
                new_task_name=new_task_name,  # Pass the potentially new task name
                config_dir=config_dir,
                triggers=triggers,
                base_dir=base_dir,  # Pass base_dir if needed
            )
            logger.debug(f"Modify task handler result: {result}")

            # Handle handler response
            if result["status"] == "success":
                success_msg = f"Windows task '{task_name}' modified successfully! (New name may be '{new_task_name}')"
                flash(success_msg, "success")
                logger.info(success_msg)
                # Redirect to the task list page on success
                return redirect(
                    url_for(
                        "server_routes.schedule_tasks_windows_route",
                        server_name=server_name,
                    )
                )
            else:
                error_msg = f"Error modifying Windows task '{task_name}': {result.get('message', 'Unknown handler error')}"
                flash(error_msg, "error")
                logger.error(error_msg)
                # Re-load existing data (or maybe use submitted data?) and re-render form
                existing_task_data = _load_existing_task_data_for_modify(xml_file_path)
                return render_template(
                    "modify_windows_task.html",
                    server_name=server_name,
                    task_name=task_name,
                    **existing_task_data,
                    app_name=app_name,
                )

        except Exception as e:
            # Catch unexpected errors during form processing
            error_msg = f"An unexpected error occurred while processing the task modification form: {e}"
            flash(error_msg, "error")
            logger.exception(error_msg)  # Log full traceback
            existing_task_data = _load_existing_task_data_for_modify(xml_file_path)
            return render_template(
                "modify_windows_task.html",
                server_name=server_name,
                task_name=task_name,
                **existing_task_data,
                app_name=app_name,
            )

    # Handle GET request (display the modification form)
    else:
        logger.debug(
            f"GET request received for modifying task '{task_name}'. Loading existing data..."
        )
        # Load existing task data from XML to pre-populate the form
        existing_task_data = _load_existing_task_data_for_modify(xml_file_path)

        # Check if loading failed
        if "error" in existing_task_data:
            error_msg = f"Error loading data for task '{task_name}': {existing_task_data['error']}"
            logger.error(error_msg)
            flash(error_msg, "error")
            # Redirect back to the task list if data cannot be loaded
            return redirect(
                url_for(
                    "server_routes.schedule_tasks_windows_route",
                    server_name=server_name,
                )
            )

        # Render the modification form, passing existing data
        logger.debug(
            f"Rendering modify_windows_task.html form with data: {existing_task_data}"
        )
        return render_template(
            "modify_windows_task.html",
            server_name=server_name,
            task_name=task_name,  # Pass original task name
            **existing_task_data,  # Unpack loaded data (command, triggers, etc.)
            app_name=app_name,
        )


# --- Route: Delete Windows Task ---
@server_bp.route("/server/<server_name>/tasks/delete", methods=["POST"])
@login_required
def delete_windows_task_route(server_name):
    """Handles the POST request to delete an existing Windows scheduled task."""
    # This uses POST from a form, not a DELETE API endpoint currently
    logger.info(
        f"Route '/server/{server_name}/tasks/delete' accessed (POST) - Deleting Windows task."
    )
    base_dir = get_base_dir()  # Needed? Not directly used here.
    config_dir = settings.CONFIG_DIR
    logger.debug(f"Config directory: {config_dir}")

    # Ensure Windows OS
    if platform.system() != "Windows":
        flash("Windows Task Scheduling is only available on Windows.", "error")
        logger.error(
            f"Attempted to access delete Windows task action for '{server_name}' from non-Windows OS."
        )
        return redirect(url_for("server_routes.index"))

    # Get task name and potentially its config file path from the form
    task_name = request.form.get("task_name")
    task_file_path = request.form.get(
        "task_file_path"
    )  # Path to the XML file in config dir
    logger.debug(
        f"Received form data - task_name: '{task_name}', task_file_path: '{task_file_path}'"
    )

    # Validate required parameters
    if not task_name or not task_file_path:
        flash("Invalid task deletion request: Missing task name or file path.", "error")
        logger.warning(
            f"Invalid task deletion request for '{server_name}': Missing task name or file path."
        )
        # Redirect back to task list or index
        return redirect(
            url_for(
                "server_routes.schedule_tasks_windows_route", server_name=server_name
            )
        )

    logger.info(
        f"Attempting to delete Windows task '{task_name}' for server '{server_name}'..."
    )
    # Call the handler to delete the task from Task Scheduler and remove the XML file
    logger.debug("Calling delete_windows_task_handler...")
    result = handlers.delete_windows_task_handler(
        task_name, task_file_path, base_dir=None
    )  # base_dir might not be needed? check handler
    logger.debug(f"Delete task handler result: {result}")

    # Flash message based on handler result
    if result["status"] == "error":
        error_msg = f"Error deleting Windows task '{task_name}': {result.get('message', 'Unknown handler error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
    else:
        success_msg = f"Windows task '{task_name}' deleted successfully for server '{server_name}'!"
        flash(success_msg, "success")
        logger.info(success_msg)

    # Redirect back to the list of tasks for that server
    logger.debug(f"Redirecting back to Windows task list for '{server_name}'.")
    return redirect(
        url_for("server_routes.schedule_tasks_windows_route", server_name=server_name)
    )
