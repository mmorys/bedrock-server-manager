# bedrock-server-manager/bedrock_server_manager/web/routes/action_routes.py
"""
Flask Blueprint defining API endpoints for controlling Bedrock server instances.

Provides routes for actions like starting, stopping, restarting, sending commands,
updating, and deleting servers. These routes typically interact with the corresponding
functions in the `bedrock_server_manager.api` layer.
"""

import logging
from typing import Tuple, Dict, Any

# Third-party imports
from flask import Blueprint, request, jsonify, Response

# Local imports
from bedrock_server_manager.web.routes.auth_routes import (
    csrf,
)
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.api import server as server_api
from bedrock_server_manager.api import server_install_config
from bedrock_server_manager.api import system as system_api
from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
    MissingArgumentError,
    ServerNotFoundError,
    DirectoryError,
)

# Initialize logger
logger = logging.getLogger("bedrock_server_manager")

# Create Blueprint
server_actions_bp = Blueprint("action_routes", __name__)


# --- API Route: Start Server ---
@server_actions_bp.route("/api/server/<string:server_name>/start", methods=["POST"])
@csrf.exempt  # API endpoint, exempt from CSRF
@auth_required  # Requires session OR JWT authentication
def start_server_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to start a specific Bedrock server instance.

    Args:
        server_name: The name of the server passed in the URL.

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 200 OK: {"status": "success", "message": "..."}
        - 400 Bad Request: If server name is invalid (caught from API).
        - 404 Not Found: If server executable is missing (caught from API).
        - 500 Internal Server Error: If server fails to start or other errors occur.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Start server request for '{server_name}' by user '{identity}'.")

    result: Dict[str, Any] = {}
    status_code = 500  # Default to internal error

    try:
        # Call the start server API function
        # base_dir resolution handled within the api function
        result = server_api.start_server(server_name)  # Returns dict
        logger.debug(f"API Start Server '{server_name}': Handler response: {result}")

        # Determine HTTP status based on the handler's response
        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            success_msg = result.get(
                "message", f"Server '{server_name}' start initiated successfully."
            )
            logger.info(f"API Start Server '{server_name}': {success_msg}")
            result["message"] = success_msg
        else:
            # Handler indicated failure or returned unexpected format
            status_code = 500  # Treat handler errors as internal server errors
            error_msg = (
                result.get("message", "Unknown error starting server.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Start Server '{server_name}': Failed: {error_msg}")
            result = {"status": "error", "message": error_msg}  # Ensure error structure

    except (MissingArgumentError, InvalidServerNameError) as e:
        # Catch input validation errors raised directly by API function
        logger.warning(
            f"API Start Server '{server_name}': Input error: {e}", exc_info=True
        )
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except ServerNotFoundError as e:
        logger.error(
            f"API Start Server '{server_name}': Server not found error: {e}",
            exc_info=True,
        )
        status_code = 404  # Not Found for missing server executable
        result = {"status": "error", "message": f"Server not found: {e}"}
    except FileOperationError as e:  # Catch base_dir config errors
        logger.error(
            f"API Start Server '{server_name}': Configuration error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"Server configuration error: {e}"}
    except Exception as e:
        # Catch unexpected errors during API orchestration
        logger.error(
            f"API Start Server '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- API Route: Stop Server ---
@server_actions_bp.route("/api/server/<string:server_name>/stop", methods=["POST"])
@csrf.exempt
@auth_required
def stop_server_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to stop a specific running Bedrock server instance.

    Args:
        server_name: The name of the server passed in the URL.

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 200 OK: {"status": "success", "message": "..."} (also if already stopped)
        - 400 Bad Request: If server name is invalid.
        - 500 Internal Server Error: If server fails to stop or other errors occur.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Stop server request for '{server_name}' by user '{identity}'.")

    result: Dict[str, Any] = {}
    status_code = 500

    try:
        # Call the stop server API function
        result = server_api.stop_server(server_name)  # Returns dict
        logger.debug(f"API Stop Server '{server_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            success_msg = result.get(
                "message",
                f"Server '{server_name}' stopped successfully or was already stopped.",
            )
            logger.info(f"API Stop Server '{server_name}': {success_msg}")
            result["message"] = success_msg
        else:
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error stopping server.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Stop Server '{server_name}': Failed: {error_msg}")
            result = {"status": "error", "message": error_msg}

    except (MissingArgumentError, InvalidServerNameError) as e:
        logger.warning(
            f"API Stop Server '{server_name}': Input error: {e}", exc_info=True
        )
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except FileOperationError as e:  # Catch base_dir config errors
        logger.error(
            f"API Stop Server '{server_name}': Configuration error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"Server configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"API Stop Server '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- API Route: Restart Server ---
@server_actions_bp.route("/api/server/<string:server_name>/restart", methods=["POST"])
@csrf.exempt
@auth_required
def restart_server_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to restart a specific Bedrock server instance.

    If the server is running, it attempts to stop it gracefully (with warning)
    and then start it again. If stopped, it simply starts it.

    Args:
        server_name: The name of the server passed in the URL.

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 200 OK: {"status": "success", "message": "..."}
        - 400 Bad Request: If server name is invalid.
        - 500 Internal Server Error: If restart phases (stop/start) fail.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Restart server request for '{server_name}' by user '{identity}'."
    )

    result: Dict[str, Any] = {}
    status_code = 500

    try:
        # Call the restart server API function (takes care of stop/start logic)
        result = server_api.restart_server(server_name)  # Default send_message=True
        logger.debug(f"API Restart Server '{server_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            success_msg = result.get(
                "message", f"Server '{server_name}' restart completed successfully."
            )
            logger.info(f"API Restart Server '{server_name}': {success_msg}")
            result["message"] = success_msg
        else:
            # Restart involves multiple steps, failure could be stop or start
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error during restart.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Restart Server '{server_name}': Failed: {error_msg}")
            result = {"status": "error", "message": error_msg}

    except (MissingArgumentError, InvalidServerNameError) as e:
        logger.warning(
            f"API Restart Server '{server_name}': Input error: {e}", exc_info=True
        )
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except FileOperationError as e:  # Catch base_dir config errors
        logger.error(
            f"API Restart Server '{server_name}': Configuration error: {e}",
            exc_info=True,
        )
        status_code = 500
        result = {"status": "error", "message": f"Server configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"API Restart Server '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- API Route: Send Command ---
@server_actions_bp.route(
    "/api/server/<string:server_name>/send_command", methods=["POST"]
)
@csrf.exempt
@auth_required
def send_command_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to send a command to a running Bedrock server instance.

    Expects JSON body with 'command' key.

    Args:
        server_name: The name of the server passed in the URL.

    JSON Request Body Example:
        {"command": "say Hello World!"}

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 200 OK: {"status": "success", "message": "..."}
        - 400 Bad Request: Invalid JSON or missing/empty command.
        - 404 Not Found: Server executable missing.
        - 500 Internal Server Error: Server not running or command sending failed.
        - 501 Not Implemented: If OS is unsupported for sending commands.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Send command request for server '{server_name}' by user '{identity}'."
    )

    # --- Input Validation ---
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        logger.warning(
            f"API Send Command '{server_name}': Invalid/missing JSON request body."
        )
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    command = data.get("command")
    logger.debug(f"API Send Command '{server_name}': Received command='{command}'")

    if not command or not isinstance(command, str) or not command.strip():
        msg = "Request body must contain a non-empty string 'command' field."
        logger.warning(f"API Send Command '{server_name}': {msg}")
        return jsonify(status="error", message=msg), 400

    trimmed_command = command.strip()

    # --- Call API Handler ---
    result: Dict[str, Any] = {}
    status_code = 500
    try:
        result = server_api.send_command(
            server_name, trimmed_command
        )  # API func handles base_dir
        logger.debug(f"API Send Command '{server_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            success_msg = result.get(
                "message", f"Command '{trimmed_command}' sent successfully."
            )
            logger.info(f"API Send Command successful for server '{server_name}'.")
            result["message"] = success_msg
        else:
            # Check for specific failure reasons based on error message from API handler
            error_msg = (
                result.get("message", "Unknown error sending command.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            if "not running" in error_msg.lower():
                status_code = (
                    500  # Or maybe 409 Conflict? 500 seems okay for server state issue.
                )
                logger.warning(
                    f"API Send Command failed: Server '{server_name}' is not running."
                )
            elif "unsupported operating system" in error_msg.lower():
                status_code = 501  # Not Implemented
                logger.error(f"API Send Command failed: {error_msg}")
            else:
                status_code = 500
                logger.error(
                    f"API Send Command failed for server '{server_name}': {error_msg}"
                )
            result = {"status": "error", "message": error_msg}

    except (MissingArgumentError, InvalidServerNameError) as e:
        logger.warning(
            f"API Send Command '{server_name}': Input error: {e}", exc_info=True
        )
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except ServerNotFoundError as e:
        logger.error(
            f"API Send Command '{server_name}': Server executable not found: {e}",
            exc_info=True,
        )
        status_code = 404
        result = {"status": "error", "message": f"Server not found: {e}"}
    except FileOperationError as e:  # Catch base_dir config errors
        logger.error(
            f"API Send Command '{server_name}': Configuration error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"Server configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"API Send Command '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- API Route: Update Server ---
@server_actions_bp.route("/api/server/<string:server_name>/update", methods=["POST"])
@csrf.exempt
@auth_required
def update_server_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to trigger an update for a specific Bedrock server instance.

    Checks for the latest version based on the server's configured target
    (LATEST or PREVIEW) and performs the update if needed.

    Args:
        server_name: The name of the server passed in the URL.

    Returns:
        JSON response indicating success or failure, potentially including update status.
        - 200 OK: {"status": "success", "updated": bool, "new_version": Optional[str], "message": "..."}
        - 400 Bad Request: If server name is invalid.
        - 500 Internal Server Error: If update process fails or other errors occur.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Update server request for '{server_name}' by user '{identity}'.")

    result: Dict[str, Any] = {}
    status_code = 500

    try:
        # Call the update server API function
        result = server_install_config.update_server(
            server_name
        )  # API func handles base_dir
        logger.debug(f"API Update Server '{server_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            success_msg = result.get(
                "message", f"Server '{server_name}' update check/process completed."
            )
            logger.info(f"API Update Server '{server_name}': {success_msg}")
            result["message"] = success_msg
        else:
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error during update.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Update Server '{server_name}': Failed: {error_msg}")
            result = {"status": "error", "message": error_msg}

    except (MissingArgumentError, InvalidServerNameError) as e:
        logger.warning(
            f"API Update Server '{server_name}': Input error: {e}", exc_info=True
        )
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except FileOperationError as e:  # Catch base_dir/config errors
        logger.error(
            f"API Update Server '{server_name}': Configuration/File error: {e}",
            exc_info=True,
        )
        status_code = 500
        result = {"status": "error", "message": f"Configuration or File error: {e}"}
    except Exception as e:
        logger.error(
            f"API Update Server '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- API Route: Delete Server ---
@server_actions_bp.route("/api/server/<string:server_name>/delete", methods=["DELETE"])
@csrf.exempt
@auth_required
def delete_server_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to delete a specific server's data (installation, config, backups).

    Args:
        server_name: The name of the server passed in the URL.

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 200 OK: {"status": "success", "message": "..."}
        - 400 Bad Request: If server name is invalid.
        - 500 Internal Server Error: If deletion fails.
    """
    identity = get_current_identity() or "Unknown"
    logger.warning(
        f"API: DELETE server request for '{server_name}' by user '{identity}'. This is irreversible."
    )

    result: Dict[str, Any] = {}
    status_code = 500

    try:
        # Call the delete server API function
        # API function handles base_dir and config_dir resolution
        result = server_api.delete_server_data(
            server_name
        )  # stop_if_running defaults to True
        logger.debug(f"API Delete Server '{server_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            success_msg = result.get(
                "message", f"Server '{server_name}' deleted successfully."
            )
            logger.info(f"API Delete Server successful for '{server_name}'.")
            result["message"] = success_msg
        else:
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error deleting server.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Delete Server failed for '{server_name}': {error_msg}")
            result = {"status": "error", "message": error_msg}

    except (MissingArgumentError, InvalidServerNameError) as e:
        logger.warning(
            f"API Delete Server '{server_name}': Input error: {e}", exc_info=True
        )
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except DirectoryError as e:  # Catch core deletion error
        logger.error(
            f"API Delete Server '{server_name}': Directory deletion error: {e}",
            exc_info=True,
        )
        status_code = 500
        result = {
            "status": "error",
            "message": f"Error deleting server directories: {e}",
        }
    except FileOperationError as e:  # Catch config errors
        logger.error(
            f"API Delete Server '{server_name}': Configuration error: {e}",
            exc_info=True,
        )
        status_code = 500
        result = {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"API Delete Server '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- API Route: Server Status ---
# Changed route to avoid conflict if more specific status endpoints are added later
@server_actions_bp.route(
    "/api/server/<string:server_name>/status_info", methods=["GET"]
)
@csrf.exempt  # GET request, CSRF not typically needed, but auth is still required
@auth_required  # Requires session OR JWT
def server_status_api(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to retrieve status information for a specific server.

    Provides running state and basic resource usage (PID, CPU, Memory, Uptime) if running.

    Args:
        server_name: The name of the server passed in the URL.

    Returns:
        JSON response containing server status details or an error message.
        - 200 OK: {"status": "success", "process_info": Dict/None}
        - 400 Bad Request: If server name is invalid.
        - 500 Internal Server Error: If retrieving status fails.
    """
    identity = get_current_identity() or "Unknown"
    logger.debug(
        f"API: Status info request for server '{server_name}' by user '{identity}'."
    )

    result: Dict[str, Any] = {}
    status_code = 500

    try:
        # Call the system API function to get process info
        result = system_api.get_bedrock_process_info(
            server_name
        )  # API func handles base_dir
        logger.debug(f"API Status Info '{server_name}': Handler response: {result}")

        # get_bedrock_process_info returns error dict if server not found/error occurs
        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            logger.debug(
                f"API Status Info: Successfully retrieved process info for '{server_name}'."
            )
        elif (
            isinstance(result, dict)
            and result.get("status") == "error"
            and "not found" in result.get("message", "").lower()
        ):
            # If API explicitly says not found, return 200 but indicate not running
            status_code = 200
            logger.info(
                f"API Status Info: Server process '{server_name}' not found (considered stopped)."
            )
            result = {
                "status": "success",
                "process_info": None,
                "message": f"Server '{server_name}' is not running.",
            }
        else:
            # Other errors from the API handler
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error getting process info.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Status Info '{server_name}': Failed: {error_msg}")
            result = {"status": "error", "message": error_msg}

    except (MissingArgumentError, InvalidServerNameError) as e:
        logger.warning(
            f"API Status Info '{server_name}': Input error: {e}", exc_info=True
        )
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except FileOperationError as e:  # Catch base_dir config errors
        logger.error(
            f"API Status Info '{server_name}': Configuration error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"Server configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"API Status Info '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code
