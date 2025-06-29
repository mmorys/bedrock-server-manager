# bedrock_server_manager/web/utils/auth_decorators.py
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
    g,
)
from flask_jwt_extended import (
    verify_jwt_in_request,
    get_jwt_identity,
)
from flask_wtf.csrf import validate_csrf, CSRFError

logger = logging.getLogger(__name__)


def auth_required(view: Callable) -> Callable:
    """
    Decorator enforcing authentication (JWT or Session + CSRF).

    Determines the user identity and stores it in flask.g.user_identity
    before calling the decorated view.
    """

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs) -> Response:
        identity: Optional[str] = None
        auth_method: Optional[str] = None
        auth_error: Optional[Exception] = None
        g.user_identity = None  # Initialize in request context

        logger.debug(
            f"Auth required check initiated for path: {request.path} [{request.method}]"
        )

        # --- 1. Attempt JWT Authentication ---
        try:
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()

            if identity:
                auth_method = "jwt"
                g.user_identity = identity  # Store JWT identity
                logger.debug(
                    f"Auth successful via JWT for identity '{identity}'. Stored in g."
                )
                return view(*args, **kwargs)  # Proceed to view
            else:
                logger.debug("No valid JWT found. Proceeding to session check.")

        except Exception as e:  # Catch JWT-related errors broadly here
            # Treat invalid/expired tokens, decode errors etc., as immediate failure for APIs
            # NoAuthorizationError/InvalidHeaderError will be skipped by optional=True logic anyway
            auth_error = e
            logger.warning(f"JWT validation failed for path '{request.path}': {e}.")
            # Prefer JSON for API errors regardless of Accept header if JWT was attempted
            return jsonify(error="Unauthorized", message=f"Invalid token: {e}"), 401

        # --- 2. Attempt Session Authentication ---
        if "logged_in" in session and session.get("logged_in"):
            auth_method = "session"
            session_username = session.get("username", "unknown_session_user")
            g.user_identity = session_username  # Store Session identity
            logger.debug(
                f"Auth successful via session for user '{session_username}'. Stored in g."
            )

            logger.debug(
                f"CSRF check skipped as CSRF protection has been removed. Proceeding for method '{request.method}'."
            )
            return view(*args, **kwargs) # Proceed to view

        # --- 3. Authentication Failed ---
        log_message = f"Authentication failed for path '{request.path}'."
        if auth_error:
            log_message += f" Reason: {type(auth_error).__name__}"
        else:
            log_message += " No valid JWT or session found."
        logger.warning(log_message)

        best_match = request.accept_mimetypes.best_match(
            ["application/json", "text/html"]
        )
        prefers_html = (
            best_match == "text/html"
            and request.accept_mimetypes[best_match]
            > request.accept_mimetypes["application/json"]
        )

        if prefers_html:
            flash("Please log in to access this page.", "warning")
            login_url = url_for("auth.login", next=request.url)
            logger.debug(f"Redirecting browser-like client to login: {login_url}")
            return redirect(login_url)
        else:
            logger.debug("Returning 401 JSON response for API-like client.")
            return (
                jsonify(error="Unauthorized", message="Authentication required."),
                401,
            )

    return wrapped_view


def get_current_identity() -> Optional[str]:
    """
    Retrieves the identity of the currently authenticated user,
    as determined by the @auth_required decorator and stored in flask.g.

    Returns:
        The identity string (e.g., username or JWT subject) if authenticated
        during the current request, otherwise None.
    """
    identity = getattr(g, "user_identity", None)
    if identity:
        logger.debug(f"Retrieved identity from g: {identity}")
        return identity
    else:
        # This case should ideally not happen if @auth_required is used correctly,
        # but provides a fallback message if called unexpectedly.
        logger.warning(
            "get_current_identity called but no identity found in flask.g. Was @auth_required used?"
        )
        return None
