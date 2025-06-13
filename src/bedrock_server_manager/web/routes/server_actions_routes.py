# bedrock_server_manager/web/routes/action_routes.py
"""
Flask Blueprint defining API endpoints for controlling Bedrock server instances.
"""

import logging
from typing import Tuple, Dict, Any

# Third-party imports
from flask import Blueprint, request, jsonify, Response

# Local imports
from bedrock_server_manager.web.routes.auth_routes import csrf
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.api import server as server_api, server_install_config
from bedrock_server_manager.api import system as system_api
from bedrock_server_manager.api import application as application_api
from bedrock_server_manager.error import (
    BSMError,
    UserInputError,
    InvalidServerNameError,
    AppFileNotFoundError,
    ServerNotRunningError,
    BlockedCommandError,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Create Blueprint
server_actions_bp = Blueprint("action_routes", __name__)


# --- API Route: Start Server ---
@server_actions_bp.route("/api/server/<string:server_name>/start", methods=["POST"])
@csrf.exempt
@auth_required
def start_server_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to start a specific Bedrock server instance."""
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Start server request for '{server_name}' by user '{identity}'.")

    result: Dict[str, Any]
    status_code: int

    try:
        result = server_api.start_server(server_name, mode="detached")

        if result.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Start Server '{server_name}': Succeeded. {result.get('message')}"
            )
        else:
            status_code = 500  # Operational error handled by the API layer
            logger.error(
                f"API Start Server '{server_name}': Failed. {result.get('message')}"
            )

    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Start Server '{server_name}': Input error. {e}")
    except BSMError as e:
        status_code = 500
        result = {"status": "error", "message": str(e)}
        logger.error(f"API Start Server '{server_name}': Application error. {e}")
    except Exception as e:
        status_code = 500
        result = {"status": "error", "message": "An unexpected error occurred."}
        logger.error(
            f"API Start Server '{server_name}': Unexpected error in route. {e}",
            exc_info=True,
        )

    return jsonify(result), status_code


# --- API Route: Stop Server ---
@server_actions_bp.route("/api/server/<string:server_name>/stop", methods=["POST"])
@csrf.exempt
@auth_required
def stop_server_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to stop a specific running Bedrock server instance."""
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Stop server request for '{server_name}' by user '{identity}'.")

    result: Dict[str, Any]
    status_code: int

    try:
        # Route no longer needs to know about start_method, API layer handles it.
        result = server_api.stop_server(server_name)

        if result.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Stop Server '{server_name}': Succeeded. {result.get('message')}"
            )
        else:
            status_code = 500
            logger.error(
                f"API Stop Server '{server_name}': Failed. {result.get('message')}"
            )

    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Stop Server '{server_name}': Input error. {e}")
    except Exception as e:
        status_code = 500
        result = {"status": "error", "message": "An unexpected error occurred."}
        logger.error(
            f"API Stop Server '{server_name}': Unexpected error in route. {e}",
            exc_info=True,
        )

    return jsonify(result), status_code


# --- API Route: Restart Server ---
@server_actions_bp.route("/api/server/<string:server_name>/restart", methods=["POST"])
@csrf.exempt
@auth_required
def restart_server_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to restart a specific Bedrock server instance."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Restart server request for '{server_name}' by user '{identity}'."
    )

    result: Dict[str, Any]
    status_code: int

    try:
        result = server_api.restart_server(server_name)

        if result.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Restart Server '{server_name}': Succeeded. {result.get('message')}"
            )
        else:
            status_code = 500
            logger.error(
                f"API Restart Server '{server_name}': Failed. {result.get('message')}"
            )

    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Restart Server '{server_name}': Input error. {e}")
    except Exception as e:
        status_code = 500
        result = {"status": "error", "message": "An unexpected error occurred."}
        logger.error(
            f"API Restart Server '{server_name}': Unexpected error in route. {e}",
            exc_info=True,
        )

    return jsonify(result), status_code


# --- API Route: Send Command ---
@server_actions_bp.route(
    "/api/server/<string:server_name>/send_command", methods=["POST"]
)
@csrf.exempt
@auth_required
def send_command_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to send a command to a running Bedrock server instance."""
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Send command request for '{server_name}' by user '{identity}'.")

    data = request.get_json()
    if not data or "command" not in data or not data["command"].strip():
        return (
            jsonify(
                status="error", message="Request must contain a non-empty 'command'."
            ),
            400,
        )

    command = data["command"].strip()
    result: Dict[str, Any]
    status_code: int

    try:
        result = server_api.send_command(server_name, command)
        status_code = 200
        logger.info(f"API Send Command '{server_name}': Succeeded.")

    except BlockedCommandError as e:
        status_code = 403  # Forbidden
        result = {"status": "error", "message": str(e)}
        logger.warning(
            f"API Send Command '{server_name}': Blocked command attempt. {e}"
        )
    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Send Command '{server_name}': Input error. {e}")
    except AppFileNotFoundError as e:
        status_code = 404
        result = {"status": "error", "message": str(e)}
        logger.error(f"API Send Command '{server_name}': Server not found. {e}")
    except ServerNotRunningError as e:
        status_code = 409  # Conflict - server is in the wrong state
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Send Command '{server_name}': Server not running. {e}")
    except Exception as e:
        status_code = 500
        result = {
            "status": "error",
            "message": "An unexpected error occurred while sending the command.",
        }
        logger.error(
            f"API Send Command '{server_name}': Unexpected error in route. {e}",
            exc_info=True,
        )

    return jsonify(result), status_code


# --- API Route: Update Server ---
@server_actions_bp.route("/api/server/<string:server_name>/update", methods=["POST"])
@csrf.exempt
@auth_required
def update_server_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to trigger an update for a specific Bedrock server instance."""
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Update server request for '{server_name}' by user '{identity}'.")

    result: Dict[str, Any]
    status_code: int

    try:
        # The update function is now in the 'application' API module.
        result = server_install_config.update_server(server_name)

        if result.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Update Server '{server_name}': Succeeded. {result.get('message')}"
            )
        else:
            status_code = 500
            logger.error(
                f"API Update Server '{server_name}': Failed. {result.get('message')}"
            )

    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Update Server '{server_name}': Input error. {e}")
    except Exception as e:
        status_code = 500
        result = {
            "status": "error",
            "message": "An unexpected error occurred during update.",
        }
        logger.error(
            f"API Update Server '{server_name}': Unexpected error in route. {e}",
            exc_info=True,
        )

    return jsonify(result), status_code


# --- API Route: Delete Server ---
@server_actions_bp.route("/api/server/<string:server_name>/delete", methods=["DELETE"])
@csrf.exempt
@auth_required
def delete_server_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to delete a specific server's data."""
    identity = get_current_identity() or "Unknown"
    logger.warning(
        f"API: DELETE server request for '{server_name}' by user '{identity}'."
    )

    result: Dict[str, Any]
    status_code: int

    try:
        result = server_api.delete_server_data(server_name)

        if result.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Delete Server '{server_name}': Succeeded. {result.get('message')}"
            )
        else:
            status_code = 500
            logger.error(
                f"API Delete Server '{server_name}': Failed. {result.get('message')}"
            )

    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Delete Server '{server_name}': Input error. {e}")
    except Exception as e:
        status_code = 500
        result = {
            "status": "error",
            "message": "An unexpected error occurred during deletion.",
        }
        logger.error(
            f"API Delete Server '{server_name}': Unexpected error in route. {e}",
            exc_info=True,
        )

    return jsonify(result), status_code


# --- API Route: Server Status ---
@server_actions_bp.route(
    "/api/server/<string:server_name>/status_info", methods=["GET"]
)
@csrf.exempt
@auth_required
def server_status_api(server_name: str) -> Tuple[Response, int]:
    """API endpoint to retrieve status information for a specific server."""
    identity = get_current_identity() or "Unknown"
    logger.debug(f"API: Status info request for '{server_name}' by user '{identity}'.")

    result: Dict[str, Any]
    status_code: int

    try:
        # The system API handles the logic of finding the process or returning None
        result = system_api.get_bedrock_process_info(server_name)
        status_code = (
            200  # This API call is successful even if the process is not found
        )
        logger.debug(f"API Status Info '{server_name}': Succeeded.")

    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Status Info '{server_name}': Input error. {e}")
    except Exception as e:
        status_code = 500
        result = {
            "status": "error",
            "message": "An unexpected error occurred getting status.",
        }
        logger.error(
            f"API Status Info '{server_name}': Unexpected error in route. {e}",
            exc_info=True,
        )

    return jsonify(result), status_code
