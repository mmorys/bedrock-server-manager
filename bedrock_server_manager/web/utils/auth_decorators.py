# bedrock-server-manager/bedrock_server_manager/web/utils/auth_decorators.py
import functools
import logging
from flask import session, request, redirect, url_for, flash, jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, JWTManager
from flask_jwt_extended.exceptions import (
    NoAuthorizationError,
    InvalidHeaderError,
    JWTDecodeError,
    WrongTokenError,
)
from flask_wtf.csrf import validate_csrf, CSRFError

logger = logging.getLogger("bedrock_server_manager")


def auth_required(view):
    """
    Decorator that requires authentication via either:
    1. A valid JWT Bearer token in the Authorization header.
    2. A valid Flask web session ('logged_in' key).

    - If authenticated via JWT, CSRF is NOT checked.
    - If authenticated via session, CSRF IS checked for relevant methods (POST, PUT, etc.).
    - Handles redirecting browsers vs. returning JSON errors for API clients.
    """

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        auth_method = None  # Track how authentication succeeded
        identity = None

        # --- 1. Try JWT Authentication ---
        try:
            # Check for JWT in header/cookies/etc. as configured. Doesn't raise error if optional=True and token missing.
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()  # Returns None if no valid JWT was found
            if identity:
                auth_method = "jwt"
                logger.debug(
                    f"Auth check passed via JWT for identity '{identity}' for path '{request.path}'"
                )
                # JWT successful, proceed to view function (CSRF not needed for JWT)
                return view(**kwargs)

        except (NoAuthorizationError, InvalidHeaderError):
            # These specifically mean no JWT header was found or it was malformed
            logger.debug(
                f"No valid JWT header found for path '{request.path}', falling back to session check."
            )
            pass  # Fall through to session check
        except (JWTDecodeError, WrongTokenError) as e:
            # These mean a token WAS present but invalid (bad signature, expired, wrong type)
            logger.warning(
                f"Invalid JWT provided for path '{request.path}': {e}. Denying access."
            )
            # Treat invalid JWT as an immediate failure for API-like clients
            return (
                jsonify(error="Unauthorized", message=f"Invalid token: {e}"),
                401,
            )
        except Exception as e:
            # Catch other potential JWT verification errors
            logger.error(
                f"Unexpected error during JWT verification for path '{request.path}': {e}",
                exc_info=True,
            )
            return (
                jsonify(
                    error="Internal Server Error", message="Token verification failed."
                ),
                500,
            )

        # --- 2. Try Session Authentication (if JWT didn't authenticate) ---
        if "logged_in" in session:
            auth_method = "session"
            session_username = session.get("username", "unknown_session_user")
            logger.debug(
                f"Auth check passed via session for user '{session_username}' for path '{request.path}'"
            )

            # --- 2a. Perform CSRF Check for Session-Based Requests (if needed) ---
            # Only check CSRF for methods that typically need it (Flask-WTF default)
            if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
                csrf_token = request.headers.get(
                    "X-CSRFToken"
                )  # Common header from JS fetch
                if not csrf_token:
                    # Fallback: check form data (less common for JS APIs)
                    csrf_token = request.form.get("csrf_token")

                try:
                    validate_csrf(csrf_token)
                    logger.debug(
                        f"CSRF validation successful for session user '{session_username}' on path '{request.path}'"
                    )
                    # Session and CSRF are valid, proceed to view function
                    return view(**kwargs)
                except CSRFError as e:
                    logger.warning(
                        f"CSRF validation failed for session user '{session_username}' on path '{request.path}': {e}"
                    )
                    # Respond appropriately based on client type
                    best = request.accept_mimetypes.best_match(
                        ["application/json", "text/html"]
                    )
                    is_browser_like = best == "text/html"

                    if is_browser_like:
                        flash(
                            f"Security token mismatch or expired. Please try again. ({e})",
                            "warning",
                        )
                        return (
                            jsonify(error="CSRF Validation Failed", message=str(e)),
                            400,
                        )  # Return JSON error even for browser JS
                    else:
                        return (
                            jsonify(error="CSRF Validation Failed", message=str(e)),
                            400,
                        )  # Bad Request

            else:
                return view(**kwargs)

        # --- 3. Authentication Failed (Neither JWT nor Session) ---
        logger.warning(
            f"Authentication failed for path '{request.path}'. No valid JWT or session found."
        )

        # Differentiate response for browser vs. API
        best = request.accept_mimetypes.best_match(["application/json", "text/html"])
        is_browser_like = (
            best == "text/html"
            and request.accept_mimetypes[best]
            > request.accept_mimetypes["application/json"]
        )

        if is_browser_like:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        else:
            return (
                jsonify(
                    error="Unauthorized",
                    message="Authentication required. Provide session cookie or Bearer token.",
                ),
                401,
            )

    return wrapped_view


# Helper to get the identity regardless of auth method
def get_current_identity():
    """Returns the identity from JWT or session, prioritizing JWT."""
    identity = get_jwt_identity()  # Returns None if no valid JWT
    if identity:
        return identity
    return session.get("username")  # Fall back to session username
