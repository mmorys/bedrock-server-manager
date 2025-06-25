# bedrock_server_manager/web/routes/plugin_routes.py
"""
Flask Blueprint for managing plugin configurations through the web UI.
"""
import logging
from typing import Tuple, Dict, Any

from flask import Blueprint, render_template, request, jsonify, Response

from bedrock_server_manager.web.routes.auth_routes import csrf, login_required
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.api import plugins as plugins_api  # Renamed for clarity
from bedrock_server_manager.error import BSMError, UserInputError

# Initialize logger
logger = logging.getLogger(__name__)

# Create Blueprint
plugin_bp = Blueprint("plugin_routes", __name__, template_folder="../templates")


# --- Route: Manage Plugins Page ---
@plugin_bp.route("/plugins")
@login_required  # Requires web session for page rendering
def manage_plugins_page() -> Response:
    """
    Renders the plugin management page.
    """
    identity = get_current_identity() or "Unknown User"
    logger.info(f"User '{identity}' accessed plugin management page.")
    return render_template("manage_plugins.html")


# --- API Route: Get Plugin Statuses ---
@plugin_bp.route("/api/plugins", methods=["GET"])
@csrf.exempt
@auth_required  # Requires token or web session for API access
def get_plugins_status_route() -> Tuple[Response, int]:
    """
    API endpoint to fetch the status of all discoverable plugins.
    """
    identity = get_current_identity() or "API Request"
    logger.info(f"API: Get plugin statuses request by '{identity}'.")

    result: Dict[str, Any]
    status_code: int

    try:
        # Calls the function from bedrock_server_manager.api.plugins
        result = plugins_api.get_plugin_statuses()

        if result.get("status") == "success":
            status_code = 200
            logger.debug(
                f"API Get Plugins: Succeeded. Found {len(result.get('plugins', {}))} plugins."
            )
        else:
            status_code = 500  # Operational error handled by the API layer
            logger.error(f"API Get Plugins: Failed. {result.get('message')}")

    except Exception as e:
        status_code = 500
        result = {
            "status": "error",
            "message": "An unexpected error occurred while fetching plugin statuses.",
        }
        logger.error(
            f"API Get Plugins: Unexpected error in route. {e}",
            exc_info=True,
        )
    return jsonify(result), status_code


# --- API Route: Trigger Custom Plugin Event ---
@plugin_bp.route("/api/plugins/trigger_event", methods=["POST"])
@csrf.exempt
@auth_required
def trigger_custom_event_route() -> Tuple[Response, int]:
    """
    API endpoint to allow external triggering of custom plugin events.
    Expects JSON: {"event_name": "some:event", "payload": {"key": "value"}}
    """
    identity = get_current_identity() or "External API Event Trigger"
    logger.info(f"API: Custom plugin event trigger request by '{identity}'.")

    data = request.get_json()
    if data is None:
        logger.warning(f"API Trigger Event: Invalid request - no JSON body.")
        return jsonify(status="error", message="Request must be JSON."), 400

    event_name = data.get("event_name")
    payload = data.get("payload")

    if not event_name:
        logger.warning(
            f"API Trigger Event: Invalid request - 'event_name' missing. Data: {data}"
        )
        return jsonify(status="error", message="'event_name' is a required field."), 400

    if payload is not None and not isinstance(payload, dict):
        logger.warning(
            f"API Trigger Event: Invalid request - 'payload' must be an object if provided. Data: {data}"
        )
        return (
            jsonify(
                status="error",
                message="'payload' must be an object (dictionary) if provided.",
            ),
            400,
        )

    result: Dict[str, Any]
    status_code: int

    try:
        result = plugins_api.trigger_external_plugin_event_api(event_name, payload)
        if result.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Trigger Event: Event '{event_name}' triggered successfully by '{identity}'."
            )
        else:
            status_code = 500  # Default if API layer had an issue but didn't specify
            logger.error(
                f"API Trigger Event: Failed to trigger event '{event_name}'. Message: {result.get('message')}"
            )

    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Trigger Event '{event_name}': Input error. {e}")
    except BSMError as e:  # Catch other application-specific errors
        status_code = 500
        result = {"status": "error", "message": str(e)}
        logger.error(f"API Trigger Event '{event_name}': Application error. {e}")
    except Exception as e:
        status_code = 500
        result = {
            "status": "error",
            "message": f"An unexpected error occurred while triggering event '{event_name}'.",
        }
        logger.error(
            f"API Trigger Event '{event_name}': Unexpected error in route. {e}",
            exc_info=True,
        )

    return jsonify(result), status_code


# --- API Route: Set Plugin Status ---
@plugin_bp.route("/api/plugins/<string:plugin_name>", methods=["POST"])
@csrf.exempt  # Exempt CSRF for this API endpoint if using token auth primarily
@auth_required  # Requires token or web session
def set_plugin_status_route(plugin_name: str) -> Tuple[Response, int]:
    """
    API endpoint to enable or disable a specific plugin.
    Expects a JSON body: {"enabled": true/false}
    """
    identity = get_current_identity() or "API Request"
    logger.info(f"API: Set plugin status request for '{plugin_name}' by '{identity}'.")

    data = request.get_json()
    if data is None or "enabled" not in data or not isinstance(data["enabled"], bool):
        logger.warning(
            f"API Set Plugin '{plugin_name}': Invalid request body. Data: {data}"
        )
        return (
            jsonify(
                status="error",
                message="Request must be JSON and contain an 'enabled' boolean field.",
            ),
            400,
        )

    enabled = data["enabled"]
    result: Dict[str, Any]
    status_code: int

    try:
        # Calls the function from bedrock_server_manager.api.plugins
        result = plugins_api.set_plugin_status(plugin_name, enabled)

        if result.get("status") == "success":
            status_code = 200
            action = "enabled" if enabled else "disabled"
            logger.info(f"API Set Plugin '{plugin_name}': Successfully {action}.")
        else:
            status_code = result.get(
                "error_code", 500
            )  # Allow API to suggest status code
            if status_code == 404:
                logger.warning(
                    f"API Set Plugin '{plugin_name}': Not found. {result.get('message')}"
                )
            else:
                logger.error(
                    f"API Set Plugin '{plugin_name}': Failed. {result.get('message')}"
                )

    except UserInputError as e:
        status_code = 400  # Bad request (e.g., plugin name invalid format, though API should catch specific not found)
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Set Plugin '{plugin_name}': Input error. {e}")
    except BSMError as e:  # Catch other application-specific errors
        status_code = 500
        result = {"status": "error", "message": str(e)}
        logger.error(f"API Set Plugin '{plugin_name}': Application error. {e}")
    except Exception as e:
        status_code = 500
        result = {
            "status": "error",
            "message": f"An unexpected error occurred while updating plugin '{plugin_name}'.",
        }
        logger.error(
            f"API Set Plugin '{plugin_name}': Unexpected error in route. {e}",
            exc_info=True,
        )

    return jsonify(result), status_code


@plugin_bp.route("/api/plugins/reload", methods=["POST"])
@csrf.exempt
@auth_required
def reload_plugins_route() -> Tuple[Response, int]:
    """
    API endpoint to trigger a reload of all plugins.
    """
    identity = get_current_identity() or "API Request"
    logger.info(f"API: Reload plugins request by '{identity}'.")

    result: Dict[str, Any]
    status_code: int

    try:
        result = plugins_api.reload_plugins()

        if result.get("status") == "success":
            status_code = 200
            logger.info("API Reload Plugins: Succeeded.")
        else:
            status_code = 500
            logger.error(f"API Reload Plugins: Failed. {result.get('message')}")

    except Exception as e:
        status_code = 500
        result = {
            "status": "error",
            "message": "An unexpected error occurred while reloading plugins.",
        }
        logger.error(
            f"API Reload Plugins: Unexpected error in route. {e}", exc_info=True
        )

    return jsonify(result), status_code
