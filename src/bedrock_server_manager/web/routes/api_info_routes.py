# bedrock-server-manager/web/routes/api_info_routes.py
"""
Flask Blueprint defining API endpoints for retrieving server/system information
and triggering global actions like scans or pruning. Secured via JWT.
"""

from email import utils
import logging
import os
from typing import Tuple, Dict, Any

# Third-party imports
from flask import Blueprint, jsonify, Response, request

# Local imports
from bedrock_server_manager.api import info as info_api
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.api import backup_restore as backup_restore_api
from bedrock_server_manager.api import world as api_world
from bedrock_server_manager.api import utils as utils_api
from bedrock_server_manager.api import application as api_application
from bedrock_server_manager.api import misc as misc_api
from bedrock_server_manager.web.routes.auth_routes import csrf
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.error import (
    BSMError,
    UserInputError,
)

logger = logging.getLogger(__name__)

# Create Blueprint
api_info_bp = Blueprint("api_info_routes", __name__)


# --- Server Info Endpoints ---


@api_info_bp.route("/api/server/<string:server_name>/world_name", methods=["GET"])
@csrf.exempt
@auth_required
def get_world_name_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to get the configured world name (level-name) for a server."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Request for world name for server '{server_name}' by user '{identity}'."
    )
    result = {}
    status_code = 500
    try:
        result = api_world.get_world_name(server_name)
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
            f"API World Name '{server_name}': Unexpected error: {e}", exc_info=True
        )
        result = {"status": "error", "message": "Unexpected error getting world name."}
    return jsonify(result), status_code


@api_info_bp.route("/api/server/<string:server_name>/running_status", methods=["GET"])
@csrf.exempt
@auth_required
def get_running_status_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to check if a server process is currently running."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Request for running status for server '{server_name}' by user '{identity}'."
    )
    result = {}
    status_code = 500
    try:
        result = info_api.get_server_running_status(server_name)
        status_code = 200 if result.get("status") == "success" else 500
    except BSMError as e:
        status_code = 400 if isinstance(e, UserInputError) else 500
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API Running Status '{server_name}': Unexpected error: {e}", exc_info=True
        )
        result = {
            "status": "error",
            "message": "Unexpected error checking running status.",
        }
    return jsonify(result), status_code


@api_info_bp.route("/api/server/<string:server_name>/config_status", methods=["GET"])
@csrf.exempt
@auth_required
def get_config_status_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to get the status string stored in the server's config file."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Request for config status for server '{server_name}' by user '{identity}'."
    )
    result = {}
    status_code = 500
    try:
        result = info_api.get_server_config_status(server_name)
        status_code = 200 if result.get("status") == "success" else 500
    except BSMError as e:
        status_code = 400 if isinstance(e, UserInputError) else 500
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API Config Status '{server_name}': Unexpected error: {e}", exc_info=True
        )
        result = {
            "status": "error",
            "message": "Unexpected error getting config status.",
        }
    return jsonify(result), status_code


@api_info_bp.route("/api/server/<string:server_name>/version", methods=["GET"])
@csrf.exempt
@auth_required
def get_version_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to get the installed version string from the server's config file."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Request for installed version for server '{server_name}' by user '{identity}'."
    )
    result = {}
    status_code = 500
    try:
        result = info_api.get_server_installed_version(server_name)
        status_code = 200 if result.get("status") == "success" else 500
    except BSMError as e:
        status_code = 400 if isinstance(e, UserInputError) else 500
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API Installed Version '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": "Unexpected error getting installed version.",
        }
    return jsonify(result), status_code


@api_info_bp.route("/api/server/<string:server_name>/validate", methods=["GET"])
@csrf.exempt
@auth_required
def validate_server_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to validate if a server directory and executable exist."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Request to validate server '{server_name}' by user '{identity}'."
    )
    result = {}
    status_code = 500
    try:
        result = utils_api.validate_server_exist(server_name)
        status_code = (
            200 if result.get("status") == "success" else 404
        )  # 404 if validation fails
    except BSMError as e:
        status_code = 400 if isinstance(e, UserInputError) else 500
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API Validate Server '{server_name}': Unexpected error: {e}", exc_info=True
        )
        result = {"status": "error", "message": "Unexpected error validating server."}
    return jsonify(result), status_code


# --- Global Action Endpoints ---


@api_info_bp.route("/api/players/scan", methods=["POST"])
@csrf.exempt
@auth_required
def scan_players_api_route() -> Tuple[Response, int]:
    """API endpoint to trigger scanning all server logs for player data."""
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Request to scan logs for players by user '{identity}'.")
    result = {}
    status_code = 500
    try:
        result = player_api.scan_and_update_player_db_api()
        status_code = 200 if result.get("status") == "success" else 500
    except BSMError as e:
        status_code = 500
        result = {
            "status": "error",
            "message": f"Configuration or Directory error: {e}",
        }
    except Exception as e:
        logger.error(f"API Scan Players: Unexpected error: {e}", exc_info=True)
        result = {
            "status": "error",
            "message": "Unexpected error scanning player logs.",
        }
    return jsonify(result), status_code


@api_info_bp.route("/api/downloads/prune", methods=["POST"])
@csrf.exempt
@auth_required
def prune_downloads_api_route() -> Tuple[Response, int]:
    """
    API endpoint to prune old downloaded archives (e.g., .zip files) from a specified directory.

    Expects JSON body with 'directory' (a path relative to the configured download directory)
    and optional 'keep' (number of newest files to retain, must be non-negative).

    JSON Request Body Example:
        {"directory": "stable", "keep": 5}
        (Where "stable" is relative to the DOWNLOAD_DIR setting)

    Returns:
        JSON response indicating success or failure of the pruning operation:
        - 200 OK: {"status": "success", "message": "...", "files_deleted": N, "files_kept": M}
        - 400 Bad Request: Invalid JSON, missing/invalid 'directory' or 'keep'.
        - 404 Not Found: If the specified relative cache directory does not resolve to an existing directory.
        - 500 Internal Server Error: Pruning process failed or critical configuration issues.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Request to prune downloads by user '{identity}'.")

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        logger.warning("API Prune Downloads: Invalid/missing JSON request body.")
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    # Expecting path relative to a base download cache directory
    relative_dir_name = data.get("directory")
    keep_count_input = data.get(
        "keep"
    )  # Can be None, int, or string representation of int
    keep_count: int | None = None  # Processed value

    logger.debug(f"API Prune Downloads: Received data: {data}")

    if (
        not relative_dir_name
        or not isinstance(relative_dir_name, str)
        or not relative_dir_name.strip()
    ):
        msg = "Missing or invalid 'directory' field. Expected a non-empty relative path string."
        logger.warning(f"API Prune Downloads: {msg}")
        return jsonify(status="error", message=msg), 400

    if keep_count_input is not None:
        try:
            keep_count = int(keep_count_input)
            if keep_count < 0:
                # This ValueError will be caught by the generic (ValueError, UserInputError) handler
                raise ValueError("Keep count cannot be negative.")
        except (ValueError, TypeError):
            msg = "Invalid 'keep' value. Must be a non-negative integer."
            logger.warning(f"API Prune Downloads: {msg} (Value: '{keep_count_input}')")
            return jsonify(status="error", message=msg), 400

    result: Dict[str, Any] = {}
    status_code = 500  # Default to internal server error
    try:
        download_cache_base_dir = settings.get("DOWNLOAD_DIR")
        if not download_cache_base_dir:
            # This will be caught by the BSMError handler below
            raise BSMError("DOWNLOAD_DIR setting is missing or empty in configuration.")

        # Construct the full path from the base and the relative directory name
        full_download_dir_path = os.path.normpath(
            os.path.join(download_cache_base_dir, relative_dir_name)
        )

        logger.debug(
            f"API Prune Downloads: Relative Dir='{relative_dir_name}', Keep='{keep_count}'. "
            f"Attempting to prune target: '{full_download_dir_path}'. "
            f"Allowed Base: '{download_cache_base_dir}'."
        )

        # Security Check: Ensure the target directory is within the allowed base cache directory
        # os.path.abspath is used to resolve any '..' and ensure a true comparison
        if not os.path.abspath(full_download_dir_path).startswith(
            os.path.abspath(download_cache_base_dir)
        ):
            msg = "Invalid directory path: Path is outside the allowed download cache base directory."
            logger.error(
                f"API Prune Downloads: Security violation - {msg} "
                f"Attempted Relative: '{relative_dir_name}', "
                f"Resolved Full: '{full_download_dir_path}'"
            )
            return jsonify(status="error", message=msg), 400

        # Check if the resolved path exists and is a directory
        if not os.path.isdir(full_download_dir_path):
            msg = (
                f"Specified download cache directory not found or is not a directory: "
                f"{full_download_dir_path} (from relative: '{relative_dir_name}')"
            )
            logger.warning(f"API Prune Downloads: {msg}")
            return (
                jsonify(status="error", message="Target cache directory not found."),
                404,  # Not Found for the target resource (directory)
            )

        # Call the misc API function with the full, validated path
        result = misc_api.prune_download_cache(full_download_dir_path, keep_count)
        logger.debug(f"API Prune Downloads: Handler response from misc_api: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            # Use handler's message if provided, otherwise create a generic one
            success_msg = result.get("message")
            if not success_msg:
                success_msg = f"Pruning operation for '{relative_dir_name}' completed successfully."
                result["message"] = success_msg  # Add to result if not present
            logger.info(f"API Prune Downloads: {success_msg}")
        else:
            status_code = (
                500  # Treat handler errors as internal server errors by default
            )
            error_msg = (
                result.get("message", "Unknown error during prune operation.")
                if isinstance(result, dict)
                else "Handler returned an unexpected response format."
            )
            logger.error(
                f"API Prune Downloads for '{relative_dir_name}' failed: {error_msg}"
            )
            # Ensure the result dictionary has a consistent error structure
            result = {"status": "error", "message": error_msg}

    except BSMError as e:  # Catches invalid keep_count or other input issues
        logger.warning(f"API Prune Downloads: Application error: {e}", exc_info=True)
        status_code = 400 if isinstance(e, UserInputError) else 500
        result = {"status": "error", "message": f"Invalid input or server error: {e}"}
    except Exception as e:
        logger.error(
            f"API Prune Downloads: Unexpected error for relative_dir '{relative_dir_name}': {e}",
            exc_info=True,
        )
        status_code = 500
        result = {
            "status": "error",
            "message": "An unexpected error occurred during the pruning process.",
        }

    return jsonify(result), status_code


@api_info_bp.route("/api/server/<string:server_name>/backups/prune", methods=["POST"])
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


@api_info_bp.route("/api/servers", methods=["GET"])
@csrf.exempt
@auth_required
def get_servers_list_api():
    """
    API Endpoint to retrieve the list of all managed servers and their status.
    Calls the internal api_application.get_all_servers_data function.
    """
    logger.debug(f"API request received for GET /api/servers")
    try:
        # Call the existing function from api/utils.py
        # It doesn't need base_dir/config_dir if defaults are okay
        result = api_application.get_all_servers_data()

        # The function returns a dict with 'status' and 'servers' or 'message'
        status_code = 200 if result.get("status") == "success" else 500
        logger.debug(f"Returning status {status_code} for /api/servers: {result}")
        return jsonify(result), status_code

    except Exception as e:
        # Catch any unexpected errors during the function call itself
        logger.error(f"Unexpected error in /api/servers endpoint: {e}", exc_info=True)
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "An unexpected error occurred retrieving the server list.",
                }
            ),
            500,
        )


@api_info_bp.route("/api/info", methods=["GET"])
def get_system_info_api():
    """
    API Endpoint to retrieve OS type and application version.
    Calls the internal api.system_api.get_system_and_app_info function.
    """
    logger.debug("API Route: Request received for GET /api/info")
    try:
        result = utils_api.get_system_and_app_info()

        status_code = 200 if result.get("status") == "success" else 500
        if (
            result.get("status") == "error"
            and "unauthorized" in result.get("message", "").lower()
        ):
            status_code = 401  # Or 403 depending on your auth logic

        logger.debug(
            f"API Route: Returning status {status_code} for /api/info: {result}"
        )
        return jsonify(result), status_code

    except Exception as e:
        # Catch any unexpected errors during the API layer call itself
        logger.error(
            f"API Route: Unexpected error in /api/info endpoint: {e}", exc_info=True
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "An unexpected server error occurred.",
                }
            ),
            500,
        )


@api_info_bp.route("/api/players/get", methods=["GET"])
@csrf.exempt
@auth_required
def get_all_players_api_route() -> Tuple[Response, int]:
    """
    API endpoint to retrieve the list of all known players.

    This endpoint reads player data from a central `players.json` file located
    in the application's main configuration directory.

    Returns:
        JSON response containing the list of players or an error message.
        - 200 OK on success:
            - {"status": "success", "players": List[Dict[str, str]]}
            - If players.json is not found or empty, "players" will be an empty list,
              and a "message" field might provide context.
        - 500 Internal Server Error: If there's an issue reading the file,
          parsing its content, or a configuration problem.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Request to retrieve all players by user '{identity}'.")

    status_code = 500  # Default to internal server error
    try:
        result_dict = player_api.get_all_known_players_api()

        if result_dict.get("status") == "success":
            status_code = 200
            logger.debug(
                f"API Get All Players: Successfully retrieved {len(result_dict.get('players', []))} players. "
                f"Message: {result_dict.get('message', 'N/A')}"
            )
        else:  # status == "error"
            status_code = 500  # Errors from the function are treated as server errors
            logger.warning(
                f"API Get All Players: Handler returned error: {result_dict.get('message')}"
            )

    except Exception as e:
        # This catch block is for truly unexpected errors *within the API route itself*
        # or if get_all_known_players_api were to raise an unhandled exception (which it aims not to).
        logger.error(
            f"API Get All Players: Unexpected critical error in route: {e}",
            exc_info=True,
        )
        result_dict = {
            "status": "error",
            "message": "A critical unexpected server error occurred while fetching players.",
        }
        status_code = 500

    return jsonify(result_dict), status_code


@api_info_bp.route("/api/players/add", methods=["POST"])
@csrf.exempt
@auth_required
def add_players_api_route() -> Tuple[Response, int]:
    """
    API endpoint to add one or more players to the central `players.json` file.

    Expects a JSON payload with a "players" key, which is a list of strings.
    Each string should be in the format "PlayerName:PlayerXUID".

    Args:
        None directly from URL. Player data is expected in the JSON request body.

    Request Body (JSON):
        {
            "players": ["PlayerOne:XUID1", "PlayerTwo:XUID2", ...]
        }

    Returns:
        JSON response indicating success or failure.
        - 200 OK (or 201 Created): {"status": "success", "message": "Players added successfully."}
        - 400 Bad Request: {"status": "error", "message": "Error description..."}
                           (e.g., missing 'players' field, invalid player format, empty list)
        - 500 Internal Server Error: {"status": "error", "message": "..."}
                                     (e.g., file system error, config directory issue, unexpected error)
    """
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Request to add players by user '{identity}'.")

    status_code = 500  # Default to internal server error
    result_dict: Dict[str, str]

    if not request.is_json:
        logger.warning("API Add Players: Request is not JSON.")
        result_dict = {"status": "error", "message": "Request body must be JSON."}
        return jsonify(result_dict), 415  # Unsupported Media Type

    try:
        data = request.get_json()
        if data is None:  # Handles empty JSON body {}
            logger.warning("API Add Players: Request JSON body is empty or malformed.")
            result_dict = {
                "status": "error",
                "message": "Request JSON body is empty or malformed.",
            }
            return jsonify(result_dict), 400

        players_list = data.get("players")

        if not isinstance(players_list, list):
            logger.warning("API Add Players: 'players' field is missing or not a list.")
            result_dict = {
                "status": "error",
                "message": "'players' field is required and must be a list.",
            }
            return jsonify(result_dict), 400

        # Call the API layer function
        # It raises TypeError, MissingArgumentError directly
        # It returns dict for UserInputError, other FileOperationError, Exception
        result_dict = player_api.add_players_manually_api(players=players_list)

        if result_dict.get("status") == "success":
            status_code = 200  # Or 201 Created if you prefer for new resources
            logger.info(
                f"API Add Players: Successfully processed add players request. Message: {result_dict.get('message')}"
            )
        else:  # status == "error" from add_players internal try-except

            msg_lower = result_dict.get("message", "").lower()
            if "invalid" in msg_lower or "format" in msg_lower:
                status_code = 400
            else:
                status_code = 500  # Default for other errors like file ops
            logger.warning(
                f"API Add Players: Handler returned error: {result_dict.get('message')}"
            )

    except (TypeError, BSMError) as e:
        logger.warning(f"API Add Players: Client or application error: {e}")
        status_code = 400 if isinstance(e, (TypeError, UserInputError)) else 500
        result_dict = {"status": "error", "message": str(e)}

    except Exception as e:
        # For truly unexpected errors *within the API route itself*
        logger.error(
            f"API Add Players: Unexpected critical error in route: {e}", exc_info=True
        )
        result_dict = {
            "status": "error",
            "message": "A critical unexpected server error occurred while adding players.",
        }
        status_code = 500

    return jsonify(result_dict), status_code
