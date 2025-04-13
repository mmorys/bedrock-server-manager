# bedrock-server-manager/bedrock_server_manager/web/validators.py
"""
Registers Flask request preprocessors for validation tasks.

Currently includes a `before_request` handler to validate server existence
based on URL path segments before allowing the request to proceed to the view function.
"""

import logging
from typing import Optional

# Third-party imports
from flask import request, jsonify, redirect, url_for, flash, Flask, Response

# Local imports
from bedrock_server_manager.api.utils import validate_server_exist

logger = logging.getLogger("bedrock_server_manager")

# Define paths or patterns that should *not* trigger server validation
BYPASS_VALIDATION_PATHS = [
    "/server/install",
    "/api/server/install",
]


def register_server_validation(app: Flask) -> None:
    """
    Registers a `before_request` handler with the Flask app to validate
    server existence based on URL paths like '/server/<server_name>/...'.

    Args:
        app: The Flask application instance.
    """

    @app.before_request
    def check_server_exists() -> Optional[Response]:
        """
        Intercepts requests and validates server existence if the path matches pattern.

        Checks URLs like '/server/<server_name>/...'. If the server identified
        by <server_name> does not exist (based on `validate_server_exist`),
        it returns a 404 JSON error for API requests (path starting with '/api/')
        or redirects other requests (presumed browser) to the main index page
        with a flash message.

        Returns:
            A Flask Response object (JSON error or Redirect) if validation fails,
            otherwise None to allow the request to proceed normally.
        """
        current_path = request.path
        logger.debug(f"Before request validation triggered for path: {current_path}")

        # --- Bypass Check for Specific Paths ---
        for bypass_path in BYPASS_VALIDATION_PATHS:
            if current_path.startswith(bypass_path):
                logger.debug(
                    f"Path '{current_path}' matches bypass pattern '{bypass_path}'. Skipping server validation."
                )
                return None  # Allow request to proceed

        # --- Path Parsing and Server Name Extraction ---
        # Assumes URL structure like '/...(prefix)/server/<server_name>/...'
        # This logic might need adjustment if URL structure varies significantly.
        try:
            path_parts = current_path.strip("/").split("/")
            if "server" in path_parts:
                server_keyword_index = path_parts.index("server")
                server_name_index = server_keyword_index + 1

                if server_name_index < len(path_parts):
                    server_name = path_parts[server_name_index]
                    # Avoid validating if the segment is empty or clearly not a server name
                    if not server_name:
                        logger.debug(
                            "Empty server name segment found after '/server/'. Skipping validation."
                        )
                        return None

                    logger.debug(
                        f"Path contains '/server/'. Extracted potential server name: '{server_name}'"
                    )

                    # --- Perform Validation ---
                    try:
                        validation_result = validate_server_exist(server_name)
                        logger.debug(
                            f"Validation result for server '{server_name}': {validation_result}"
                        )

                        # Check if validation function returned expected format
                        if (
                            not isinstance(validation_result, dict)
                            or "status" not in validation_result
                        ):
                            logger.error(
                                f"Validation function for server '{server_name}' returned unexpected format: {validation_result}"
                            )
                            # Treat unexpected format as internal error
                            return (
                                jsonify(
                                    {
                                        "status": "error",
                                        "message": "Internal server error during validation.",
                                    }
                                ),
                                500,
                            )

                        # Handle validation failure
                        if validation_result["status"] == "error":
                            error_message = validation_result.get(
                                "message", f"Server '{server_name}' not found."
                            )
                            logger.warning(
                                f"Server validation failed for '{server_name}': {error_message}"
                            )

                            # Determine response type based on path prefix
                            # Using Accept header (request.accept_mimetypes) is more standard for API detection
                            if current_path.startswith("/api/"):
                                logger.debug(
                                    f"Returning 404 JSON error for API request to non-existent server '{server_name}'."
                                )
                                return (
                                    jsonify(
                                        {"status": "error", "message": error_message}
                                    ),
                                    404,
                                )
                            else:
                                logger.debug(
                                    f"Redirecting browser request for non-existent server '{server_name}' to index."
                                )
                                flash(error_message, "warning")
                                return redirect(
                                    url_for("main_routes.index")
                                )  # Assuming 'main_routes.index' is the correct endpoint name

                        else:
                            # Validation successful
                            logger.debug(
                                f"Server validation successful for '{server_name}'. Allowing request to proceed."
                            )
                            return None  # Allow request to proceed normally

                    except Exception as e:
                        # Catch unexpected errors during the validation call itself
                        logger.error(
                            f"An error occurred while validating server '{server_name}': {e}",
                            exc_info=True,
                        )
                        # Return a generic 500 error
                        return (
                            jsonify(
                                {
                                    "status": "error",
                                    "message": "Internal server error during server validation.",
                                }
                            ),
                            500,
                        )

                else:
                    # Path was just '/server' or '/prefix/server', no name followed
                    logger.debug(
                        "Path contains '/server/' but no server name segment followed. Skipping validation."
                    )
                    return None
            else:
                # Path does not contain the '/server/' segment in the expected structure
                logger.debug(
                    "Path does not contain '/server/' segment. Skipping validation."
                )
                return None

        except ValueError:
            # Handles potential errors from path_parts.index('server') if 'server' isn't present,
            logger.debug("Path parsing error (ValueError). Skipping validation.")
            return None
        except Exception as e:
            # Catch any other unexpected errors during path parsing/checking
            logger.error(
                f"Unexpected error during request path validation preprocessing: {e}",
                exc_info=True,
            )
            # Let the request proceed? Or return 500? Let's return 500 as something is wrong.
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Internal server error during request preprocessing.",
                    }
                ),
                500,
            )

        # Default: If path structure didn't match, allow request to proceed
        return None
