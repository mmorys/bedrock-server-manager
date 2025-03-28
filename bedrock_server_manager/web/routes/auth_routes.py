# bedrock-server-manager/bedrock_server_manager/web/routes/auth_routes.py
import os
import functools
import logging
import secrets
from bedrock_server_manager.config.settings import env_name, app_name
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
    jsonify,
    abort,
)

logger = logging.getLogger("bedrock_server_manager")

auth_bp = Blueprint("auth", __name__)


# --- Helper Function / Decorator for Route Protection ---
def login_required(view):
    """
    Decorator that checks for a valid session or API token.
    Redirects browser users to login if not authenticated.
    Returns 401 JSON error for API requests if not authenticated.
    """

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        # 1. Check for active web session
        if "logged_in" in session:
            logger.debug(
                f"Login required check passed via session for user '{session.get('username', 'unknown')}' for path '{request.path}'"
            )
            return view(**kwargs)  # User is logged in via browser session

        # 2. Check for API Token Authentication
        expected_token = current_app.config.get(f"{env_name}_WEB_TOKEN")
        auth_header = request.headers.get("Authorization")

        if expected_token:
            logger.debug(
                f"API token is configured. Checking header for path '{request.path}'"
            )
            if auth_header:
                logger.debug(f"Authorization header found for path '{request.path}'")
                parts = auth_header.split()
                # Check if header is in "Bearer <token>" format
                if len(parts) == 2 and parts[0].lower() == "bearer":
                    provided_token = parts[1]
                    # Securely compare the provided token with the expected one
                    if secrets.compare_digest(provided_token, expected_token):
                        # --- API User Authenticated ---
                        logger.info(
                            f"Login required check passed via API token from {request.remote_addr} for path '{request.path}'"
                        )
                        return view(**kwargs)  # Token is valid
                    else:
                        # Provided token is incorrect
                        logger.warning(
                            f"Invalid API token received from {request.remote_addr} for path '{request.path}'"
                        )
                        return (
                            jsonify(
                                error="Unauthorized",
                                message="Invalid API token provided.",
                            ),
                            401,
                        )
                else:
                    # Authorization header format is incorrect
                    logger.warning(
                        f"Invalid Authorization header format from {request.remote_addr} for path '{request.path}'"
                    )
                    return (
                        jsonify(
                            error="Unauthorized",
                            message="Invalid Authorization header format. Use 'Bearer <token>'.",
                        ),
                        401,
                    )
            else:
                logger.debug(
                    f"No Authorization header found for API check on path '{request.path}'"
                )
        else:
            logger.debug(
                f"{env_name}_WEB_TOKEN is not configured. Skipping token check."
            )

        # 3. If neither session nor valid token found:
        # Differentiate between browser and API request failure
        best = request.accept_mimetypes.best_match(["application/json", "text/html"])
        is_browser_like = (
            best == "text/html"
            and request.accept_mimetypes[best]
            > request.accept_mimetypes["application/json"]
        )
        logger.debug(
            f"Authentication failed for path '{request.path}'. Browser-like client: {is_browser_like}"
        )

        if is_browser_like:
            # It's likely a browser, redirect to login page
            logger.warning(
                f"Unauthenticated browser access to {request.path} from {request.remote_addr}. Redirecting to login."
            )
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        else:
            # It's likely an API client (or doesn't prefer HTML), return 401 JSON
            if not expected_token:
                logger.error(
                    f"API access attempted to {request.path} from {request.remote_addr} but {env_name}_WEB_TOKEN is not configured."
                )
                return (
                    jsonify(
                        error="Unauthorized",
                        message="API access is not configured on the server.",
                    ),
                    401,
                )
            else:
                logger.warning(
                    f"Unauthenticated API access to {request.path} from {request.remote_addr}. Responding with 401."
                )
                return (
                    jsonify(
                        error="Unauthorized",
                        message="Authentication required. Provide session cookie or Bearer token.",
                    ),
                    401,
                )

    return wrapped_view


# --- Login Route ---
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handles user login."""
    # Redirect if already logged in
    if "logged_in" in session:
        logger.debug(
            f"User '{session.get('username')}' already logged in. Redirecting to index."
        )
        return redirect(url_for("server_routes.index"))

    if request.method == "POST":
        username_attempt = request.form.get("username")
        # Avoid logging password attempts directly
        logger.info(
            f"Login attempt for username: '{username_attempt}' from {request.remote_addr}"
        )
        password_attempt = request.form.get("password")

        # Get credentials from app config
        expected_username = current_app.config.get(f"{env_name}_WEB_USERNAME")
        expected_password = current_app.config.get(f"{env_name}_WEB_PASSWORD")

        # Basic validation (ensure env vars are set)
        if not expected_username or not expected_password:
            flash("Application authentication is not configured correctly.", "danger")
            # Log this error server-side as well
            logger.error(f"{env_name}_WEB_USERNAME or {env_name}_WEB_PASSWORD not set!")
            return render_template(
                "login.html", error="Server configuration error.", app_name=app_name
            )

        # Check credentials
        if (
            username_attempt == expected_username
            and password_attempt == expected_password
        ):
            session["logged_in"] = True
            session["username"] = username_attempt
            logger.info(
                f"User '{username_attempt}' logged in successfully from {request.remote_addr}."
            )
            flash("You were successfully logged in!", "success")
            next_url = request.args.get("next")  # For redirecting after login
            logger.debug(
                f"Redirecting logged in user to: {next_url or url_for('server_routes.index')}"
            )
            return redirect(
                next_url or url_for("server_routes.index")
            )  # Redirect to next or main page
        else:
            logger.warning(
                f"Invalid login attempt for username: '{username_attempt}' from {request.remote_addr}."
            )
            flash("Invalid username or password. Please try again.", "danger")
            return (
                render_template("login.html", app_name=app_name),
                401,
            )  # Unauthorized status code

    # GET request: show the login form
    logger.debug(f"Rendering login page for GET request from {request.remote_addr}")
    return render_template("login.html", app_name=app_name)


# --- Logout Route ---
@auth_bp.route("/logout")
def logout():
    """Logs the user out."""
    username = session.get("username", "Unknown user")  # Get username before popping
    session.pop("logged_in", None)
    session.pop("username", None)
    logger.info(f"User '{username}' logged out from {request.remote_addr}.")
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
