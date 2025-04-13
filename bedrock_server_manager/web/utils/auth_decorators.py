# bedrock-server-manager/bedrock_server_manager/web/utils/auth_decorators.py
"""
Decorators for handling authentication and authorization in the Flask web application.

Provides mechanisms to protect view functions, requiring either a valid JWT
or an active Flask session, and includes CSRF protection for session-based requests.
"""

import functools
import logging
from typing import Callable, Optional

# Third-party imports
from flask import (
    session,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    Response,
)
from flask_jwt_extended import (
    verify_jwt_in_request,
    get_jwt_identity,
)
from flask_jwt_extended.exceptions import (
    NoAuthorizationError,
    InvalidHeaderError,
    JWTDecodeError,
    WrongTokenError,
)
from flask_wtf.csrf import validate_csrf, CSRFError


logger = logging.getLogger("bedrock_server_manager")


def auth_required(view: Callable) -> Callable:
    """
    Decorator enforcing authentication for a view function.

    Checks for authentication in the following order:
    1. Valid JWT Bearer token in the 'Authorization' header. If present and valid,
       access is granted (CSRF check is skipped). If present but invalid,
       a 401 JSON error is returned immediately.
    2. Valid Flask web session (checks for 'logged_in' key). If found, CSRF
       protection is enforced for state-changing HTTP methods (POST, PUT, etc.).
       If session and CSRF are valid, access is granted. If CSRF fails, a 400
       JSON error is returned.

    If neither authentication method succeeds, behavior depends on the client:
    - Browser-like clients (Accept: text/html) are redirected to the login page.
    - API-like clients (Accept: application/json) receive a 401 JSON error.

    Args:
        view: The Flask view function to decorate.

    Returns:
        The decorated view function, which includes the authentication checks.
    """

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs) -> Response:
        identity: Optional[str] = None
        auth_method: Optional[str] = None
        auth_error: Optional[Exception] = None

        logger.debug(
            f"Auth required check initiated for path: {request.path} [{request.method}]"
        )

        # --- 1. Attempt JWT Authentication ---
        try:
            # `optional=True` prevents NoAuthorizationError if header is missing.
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()  # Returns None if no valid JWT verified

            if identity:
                auth_method = "jwt"
                logger.debug(
                    f"Auth successful via JWT for identity '{identity}' on path '{request.path}'."
                )
                # JWT auth successful, skip session/CSRF checks and proceed to view
                return view(*args, **kwargs)
            else:
                logger.debug(
                    f"No valid JWT found in request for path '{request.path}'. Proceeding to session check."
                )

        except (JWTDecodeError, WrongTokenError) as e:
            # A token was present but invalid (expired, bad signature, wrong type, etc.)
            # Treat this as an immediate failure, especially for APIs expecting JWT.
            auth_error = e
            logger.warning(
                f"Invalid JWT provided for path '{request.path}': {e}. Denying access."
            )
            return (
                jsonify(error="Unauthorized", message=f"Invalid or expired token: {e}"),
                401,
            )
        except (NoAuthorizationError, InvalidHeaderError) as e:
            # Should not happen with optional=True, but handle defensively.
            auth_error = e
            logger.debug(
                f"JWT header issue for path '{request.path}': {e}. Proceeding to session check."
            )
            # Fall through to session check
        except Exception as e:
            # Catch unexpected JWT verification errors (e.g., config issues)
            auth_error = e
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

        # --- 2. Attempt Session Authentication ---
        # Check only if JWT authentication did not succeed
        if "logged_in" in session and session.get("logged_in"):
            auth_method = "session"
            session_username = session.get(
                "username", "unknown_session_user"
            )  # Use .get for safety
            logger.debug(
                f"Auth successful via session for user '{session_username}' on path '{request.path}'."
            )

            # --- 2a. CSRF Check for Session Auth (State-Changing Methods) ---
            # Only apply CSRF check for methods typically modifying state
            csrf_needed_methods = ["POST", "PUT", "PATCH", "DELETE"]
            if request.method in csrf_needed_methods:
                logger.debug(
                    f"Session auth requires CSRF check for method '{request.method}'."
                )
                # Prioritize header (common for JS fetch), fallback to form data
                csrf_token = request.headers.get("X-CSRFToken") or request.form.get(
                    "csrf_token"
                )

                try:
                    validate_csrf(csrf_token)  # Raises CSRFError on failure
                    logger.debug(
                        f"CSRF validation successful for session user '{session_username}' on path '{request.path}'."
                    )
                    # Session and CSRF valid, proceed to view
                    return view(*args, **kwargs)
                except CSRFError as e:
                    auth_error = e
                    logger.warning(
                        f"CSRF validation failed for session user '{session_username}' on path '{request.path}': {e}",
                        exc_info=True,
                    )  # Log full error
                    # For CSRF errors, typically return 400 Bad Request
                    return jsonify(error="CSRF Validation Failed", message=str(e)), 400
            else:
                # Session auth valid, CSRF not needed for this method (e.g., GET, HEAD)
                logger.debug(
                    f"CSRF check not required for method '{request.method}'. Proceeding to view."
                )
                return view(*args, **kwargs)

        # --- 3. Authentication Failed ---
        # If code reaches here, neither JWT nor Session authentication succeeded.
        log_message = f"Authentication failed for path '{request.path}'."
        if auth_error:
            log_message += f" Reason (if known): {type(auth_error).__name__}"
        else:
            log_message += " No valid JWT or session cookie found."
        logger.warning(log_message)

        # Determine client type to provide appropriate response
        # Check if the client prefers HTML over JSON
        best_match = request.accept_mimetypes.best_match(
            ["application/json", "text/html"]
        )
        prefers_html = (
            best_match == "text/html"
            and request.accept_mimetypes[best_match]
            > request.accept_mimetypes["application/json"]
        )

        if prefers_html:
            # Browser-like client: Redirect to login
            flash("Please log in to access this page.", "warning")
            # Pass the original requested URL as 'next' parameter for redirect after login
            login_url = url_for("auth.login", next=request.url)
            logger.debug(f"Redirecting browser-like client to login: {login_url}")
            return redirect(login_url)
        else:
            # API-like client: Return 401 Unauthorized JSON response
            logger.debug("Returning 401 JSON response for API-like client.")
            return (
                jsonify(error="Unauthorized", message="Authentication required."),
                401,
            )

    return wrapped_view


def get_current_identity() -> Optional[str]:
    """
    Retrieves the identity of the currently authenticated user.

    Prioritizes the identity from a verified JWT token. If no valid JWT is
    present in the request context, it falls back to retrieving the 'username'
    stored in the Flask session.

    Returns:
        The identity string (e.g., username or JWT subject) if authenticated,
        otherwise None.
    """
    try:
        # Check JWT first (requires active request context where JWT might have been verified)
        # Returns None if verify_jwt_in_request hasn't been called or no valid token found
        jwt_identity = get_jwt_identity()
        if jwt_identity:
            logger.debug(f"Retrieved identity from JWT: {jwt_identity}")
            return jwt_identity
    except Exception as e:
        # Catch potential errors if called outside request context where JWT expects to be
        logger.warning(
            f"Error accessing JWT identity (may be outside request context): {e}",
            exc_info=True,
        )

    # Fallback to session if JWT identity is not available
    session_username = session.get("username")
    if session_username:
        logger.debug(f"Retrieved identity from session: {session_username}")
        return session_username

    logger.debug("Could not retrieve identity from JWT or session.")
    return None
