# bedrock-server-manager/web/routes/api_info_routes.py
"""
Flask Blueprint defining API endpoints for retrieving server/system information
and triggering global actions like scans or pruning. Secured via JWT.
"""

import logging
from typing import Tuple

# Third-party imports
from flask import Blueprint, jsonify, Response, request

# Local imports
from bedrock_server_manager.api import info as info_api
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.api import backup_restore as backup_restore_api
from bedrock_server_manager.api import world as api_world
from bedrock_server_manager.api import utils as utils_api
from bedrock_server_manager.api import misc as misc_api
from bedrock_server_manager.web.routes.auth_routes import csrf
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.error import (
    MissingArgumentError,
    InvalidServerNameError,
    FileOperationError,
    ValueError,
    DirectoryError,
)

logger = logging.getLogger("bedrock_server_manager")

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
        result = api_world.get_world_name(server_name)  # Handles base_dir internally
        status_code = (
            200
            if result.get("status") == "success"
            else 500 if result.get("status") == "error" else 500
        )
    except (MissingArgumentError, InvalidServerNameError, FileOperationError) as e:
        status_code = (
            400
            if isinstance(e, (MissingArgumentError, InvalidServerNameError))
            else 500
        )
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
        result = info_api.get_server_running_status(server_name)  # Handles base_dir
        status_code = 200 if result.get("status") == "success" else 500
    except (MissingArgumentError, InvalidServerNameError, FileOperationError) as e:
        status_code = (
            400
            if isinstance(e, (MissingArgumentError, InvalidServerNameError))
            else 500
        )
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
        result = info_api.get_server_config_status(server_name)  # Handles config_dir
        status_code = 200 if result.get("status") == "success" else 500
    except (MissingArgumentError, InvalidServerNameError, FileOperationError) as e:
        status_code = (
            400
            if isinstance(e, (MissingArgumentError, InvalidServerNameError))
            else 500
        )
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
        result = info_api.get_server_installed_version(
            server_name
        )  # Handles config_dir
        status_code = 200 if result.get("status") == "success" else 500
    except (MissingArgumentError, InvalidServerNameError, FileOperationError) as e:
        status_code = (
            400
            if isinstance(e, (MissingArgumentError, InvalidServerNameError))
            else 500
        )
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
        result = utils_api.validate_server_exist(server_name)  # Handles base_dir
        status_code = (
            200 if result.get("status") == "success" else 404
        )  # 404 if validation fails
    except (MissingArgumentError, InvalidServerNameError, FileOperationError) as e:
        status_code = (
            400
            if isinstance(e, (MissingArgumentError, InvalidServerNameError))
            else 500
        )
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API Validate Server '{server_name}': Unexpected error: {e}", exc_info=True
        )
        result = {"status": "error", "message": "Unexpected error validating server."}
    return jsonify(result), status_code


@api_info_bp.route("/api/server/<string:server_name>/export_world", methods=["POST"])
@csrf.exempt
@auth_required
def export_world_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to trigger exporting the server's world to a .mcworld file."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Request to export world for server '{server_name}' by user '{identity}'."
    )
    result = {}
    status_code = 500
    try:
        # Optional: Allow specifying export_dir via request body? For now, uses default.
        # data = request.get_json(silent=True) or {}
        # export_dir = data.get('export_dir')
        result = api_world.export_world(
            server_name
        )  # API handles base_dir and default export_dir
        status_code = 200 if result.get("status") == "success" else 500
    except (MissingArgumentError, InvalidServerNameError, FileOperationError) as e:
        status_code = (
            400
            if isinstance(e, (MissingArgumentError, InvalidServerNameError))
            else 500
        )
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API Export World '{server_name}': Unexpected error: {e}", exc_info=True
        )
        result = {"status": "error", "message": "Unexpected error exporting world."}
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
        result = player_api.scan_for_players()  # API handles defaults
        status_code = 200 if result.get("status") == "success" else 500
    except (
        FileOperationError,
        DirectoryError,
    ) as e:  # Catch config/dir errors from API
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
    API endpoint to prune old downloaded server archives (.zip).
    Requires 'directory' and optional 'keep' in JSON body.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Request to prune downloads by user '{identity}'.")

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    download_dir = data.get("directory")
    keep_count = data.get("keep")

    logger.debug(f"API Prune Downloads: Dir='{download_dir}', Keep='{keep_count}'")

    if not download_dir:
        return (
            jsonify(
                status="error",
                message="Missing required 'directory' field in request body.",
            ),
            400,
        )
    if keep_count is not None:
        try:
            keep_count = int(keep_count)  # Validate type early
        except (ValueError, TypeError):
            return (
                jsonify(
                    status="error", message="Invalid 'keep' value. Must be an integer."
                ),
                400,
            )

    result = {}
    status_code = 500
    try:
        # Call the new misc API function
        result = misc_api.prune_download_cache(download_dir, keep_count)
        status_code = (
            200
            if result.get("status") == "success"
            else 500 if result.get("status") == "error" else 500
        )
    except (MissingArgumentError, ValueError, DirectoryError, FileOperationError) as e:
        status_code = 400 if isinstance(e, (MissingArgumentError, ValueError)) else 500
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API Prune Downloads: Unexpected error for dir '{download_dir}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": "Unexpected error pruning downloads."}

    return jsonify(result), status_code


@api_info_bp.route("/api/server/<string:server_name>/backups/prune", methods=["POST"])
@csrf.exempt
@auth_required
def prune_backups_api_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to prune old backups (world, configs) for a specific server.
    Optional 'keep' count can be provided in JSON body.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Request to prune backups for server '{server_name}' by user '{identity}'."
    )

    data = request.get_json(silent=True) or {}  # Allow empty body, use default keep
    keep_count = data.get("keep")  # Optional

    logger.debug(f"API Prune Backups: Server='{server_name}', Keep='{keep_count}'")

    if keep_count is not None:
        try:
            keep_count = int(keep_count)  # Validate type early
        except (ValueError, TypeError):
            return (
                jsonify(
                    status="error", message="Invalid 'keep' value. Must be an integer."
                ),
                400,
            )

    result = {}
    status_code = 500
    try:
        # Call the backup API function (handles base_dir, uses setting for keep if None)
        result = backup_restore_api.prune_old_backups(
            server_name, backup_keep=keep_count
        )
        status_code = (
            200
            if result.get("status") == "success"
            else 500 if result.get("status") == "error" else 500
        )
    except (
        MissingArgumentError,
        InvalidServerNameError,
        ValueError,
        FileOperationError,
    ) as e:
        status_code = (
            400
            if isinstance(e, (MissingArgumentError, ValueError, InvalidServerNameError))
            else 500
        )
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API Prune Backups '{server_name}': Unexpected error: {e}", exc_info=True
        )
        result = {"status": "error", "message": "Unexpected error pruning backups."}

    return jsonify(result), status_code
