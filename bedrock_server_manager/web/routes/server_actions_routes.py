# bedrock-server-manager/bedrock_server_manager/web/routes/action_routes.py
import logging
from flask_jwt_extended import jwt_required
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.web.routes.auth_routes import csrf
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from flask import (
    Blueprint,
    request,
    jsonify,
)
from bedrock_server_manager.api import (
    server,
    server_install_config,
    system,
)

# Initialize logger for this module
logger = logging.getLogger("bedrock_server_manager")

# Create Blueprint for server action API routes
server_actions_bp = Blueprint("action_routes", __name__)


# --- API Route: Start Server ---
@server_actions_bp.route("/api/server/<server_name>/start", methods=["POST"])
@csrf.exempt
@auth_required
def start_server_route(server_name):
    """API endpoint to start a specific server."""
    logger.info(f"API POST request received to start server: '{server_name}'.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the start server handler
    logger.debug(f"Calling start_server_handler for server '{server_name}'...")
    response = server.start_server(server_name, base_dir)
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
@server_actions_bp.route("/api/server/<server_name>/stop", methods=["POST"])
@csrf.exempt
@auth_required
def stop_server_route(server_name):
    """API endpoint to stop a specific server."""
    logger.info(f"API POST request received to stop server: '{server_name}'.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the stop server handler
    logger.debug(f"Calling stop_server_handler for server '{server_name}'...")
    response = server.stop_server(server_name, base_dir)
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
@server_actions_bp.route("/api/server/<server_name>/restart", methods=["POST"])
@csrf.exempt
@auth_required
def restart_server_route(server_name):
    """API endpoint to restart a specific server."""
    logger.info(f"API POST request received to restart server: '{server_name}'.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the restart server handler
    logger.debug(f"Calling restart_server_handler for server '{server_name}'...")
    response = server.restart_server_handler(server_name, base_dir)
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
@server_actions_bp.route("/api/server/<server_name>/send_command", methods=["POST"])
@csrf.exempt
@auth_required
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
    result = server.send_command(server_name, trimmed_command, base_dir)
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
@server_actions_bp.route("/api/server/<server_name>/update", methods=["POST"])
@csrf.exempt
@auth_required
def update_server_route(server_name):
    """API endpoint to update a specific server's Bedrock software."""
    logger.info(f"API POST request received to update server: '{server_name}'.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the update server handler
    logger.debug(f"Calling update_server_handler for server '{server_name}'...")
    response = server_install_config.update_server(server_name, base_dir=base_dir)
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


# --- API Route: Delete Server ---
@server_actions_bp.route("/api/server/<server_name>/delete", methods=["DELETE"])
@csrf.exempt
@auth_required
def delete_server_route(server_name):
    """API endpoint to delete a specific server's data."""
    logger.info(f"API DELETE request received to delete server: '{server_name}'.")
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    logger.debug(f"Base directory: {base_dir}, Config directory: {config_dir}")

    # Call the handler to delete the server data
    logger.debug(f"Calling delete_server_data_handler for '{server_name}'...")
    result = server.delete_server_data(server_name, base_dir, config_dir)
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


# --- API Route: Server Status ---
@server_actions_bp.route("/api/server/<server_name>/status")
@csrf.exempt
@auth_required
def server_status_api(server_name):
    """API endpoint providing server status information (running state, resource usage) as JSON."""
    logger.debug(f"API GET request for status of server: '{server_name}'.")
    base_dir = get_base_dir()
    logger.debug(f"Base directory: {base_dir}")

    # Call the handler to get process information
    logger.debug(f"Calling get_bedrock_process_info_handler for '{server_name}'...")
    result = system.get_bedrock_process_info(server_name, base_dir)
    logger.debug(f"Get process info handler result for '{server_name}': {result}")

    status_code = 200
    logger.debug(
        f"Returning JSON response for server status API '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code
