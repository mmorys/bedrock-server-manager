# bedrock-server-manager/bedrock_server_manager/web/routes/auth_routes.py
"""
Flask Blueprint for handling user authentication.

Provides routes for:
- Web UI login (session-based) using Flask-WTF forms.
- API login (JWT-based) expecting JSON credentials.
- User logout (clears session).
Includes a decorator `login_required` specifically for protecting views requiring
a valid web session.
"""

import functools
import logging
from typing import Callable

# Third-party imports
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
    Response,
)

from werkzeug.security import check_password_hash
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length
from flask_jwt_extended import create_access_token, JWTManager

# Local imports
from bedrock_server_manager.config.settings import (
    env_name,
    app_name,
)

logger = logging.getLogger("bedrock_server_manager")

# --- Blueprint and Extension Setup ---
# Blueprint for authentication routes
auth_bp = Blueprint(
    "auth",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)

# Initialize extensions (these instances are configured in app.py)
csrf = CSRFProtect()
jwt = JWTManager()


# --- Forms ---
class LoginForm(FlaskForm):
    """Login form definition using Flask-WTF."""

    username = StringField(
        "Username",
        validators=[
            DataRequired(message="Username is required."),
            Length(
                min=1, max=80, message="Username length invalid."
            ),  # Example length validation
        ],
    )
    password = PasswordField(
        "Password", validators=[DataRequired(message="Password is required.")]
    )
    submit = SubmitField("Log In")  # Changed button text slightly


# --- Decorator for Session-Based Authentication ---
def login_required(view: Callable) -> Callable:
    """
    Decorator enforcing authentication via Flask web session ONLY.

    - If `session['logged_in']` is True, allows the request to proceed.
    - If not logged in via session:
        - Browser clients (Accept: text/html) are redirected to the login page.
        - API/non-browser clients receive a 401 Unauthorized JSON error.

    *** IMPORTANT: This decorator DOES NOT check for JWT tokens. ***
    Use the `auth_required` decorator from `auth_decorators.py` for routes
    that should accept either session OR JWT authentication.

    Args:
        view: The view function to protect.

    Returns:
        The decorated view function with session authentication check.
    """

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs) -> Response:
        # Check only for the presence and truthiness of 'logged_in' in the session
        if session.get("logged_in"):
            # Session exists and user is marked as logged in
            # logger.debug(f"Session authentication successful for path: {request.path}") # Can be noisy
            return view(*args, **kwargs)
        else:
            # No valid session found
            logger.warning(
                f"Session authentication failed for path '{request.path}' from {request.remote_addr}."
            )

            # Determine client type for appropriate response
            best_match = request.accept_mimetypes.best_match(
                ["application/json", "text/html"]
            )
            prefers_html = (
                best_match == "text/html"
                and request.accept_mimetypes[best_match]
                > request.accept_mimetypes["application/json"]
            )

            if prefers_html:
                # Redirect browser to login page
                flash("Please log in to access this page.", "warning")
                login_url = url_for("auth.login", next=request.url)  # Pass original URL
                logger.debug(f"Redirecting browser to login: {login_url}")
                return redirect(login_url)
            else:
                # Return JSON error for non-browser clients
                logger.debug("Returning 401 JSON response for non-browser client.")
                return (
                    jsonify(
                        error="Unauthorized",
                        message="Valid web session required for this endpoint.",
                    ),
                    401,
                )

    return wrapped_view


# --- Web UI Login Route ---
@auth_bp.route("/login", methods=["GET", "POST"])
def login() -> Response:
    """
    Handles user login for the web UI using username/password form (session-based).

    - GET: Displays the login form.
    - POST: Validates form data, checks credentials against configured environment
            variables, sets session variables on success, and redirects. Shows
            errors on failure.
    """
    # If user is already logged in via session, redirect to index
    if session.get("logged_in"):
        logger.debug("User already logged in via session, redirecting to index.")
        return redirect(url_for("main_routes.index"))

    form = LoginForm()
    logger.debug(f"Login route accessed: Method='{request.method}'")

    # validate_on_submit() checks if it's a POST request and if form data is valid
    if form.validate_on_submit():
        # Form was submitted via POST and passed WTForms validation
        username_attempt = form.username.data
        password_attempt = form.password.data
        logger.info(
            f"Web login attempt for username '{username_attempt}' from {request.remote_addr}"
        )

        # Retrieve configured credentials securely
        username_env = f"{env_name}_USERNAME"
        password_env = f"{env_name}_PASSWORD"
        expected_username = current_app.config.get(username_env)
        stored_password_hash = current_app.config.get(
            password_env
        )  # This should be a hash

        # --- Validate Server Configuration ---
        if not expected_username or not stored_password_hash:
            error_msg = f"Server authentication configuration error: '{username_env}' or '{password_env}' not set."
            logger.critical(error_msg)  # Critical failure if auth env vars missing
            flash(
                "Login failed due to server configuration issue. Please contact the administrator.",
                "danger",
            )
            # Return 500 status code as it's a server-side problem
            return render_template("login.html", app_name=app_name, form=form), 500

        # --- Validate Credentials ---
        # Compare submitted username and check hashed password
        # Ensure stored_password_hash is actually a hash, otherwise check_password_hash might error
        try:
            is_valid_password = check_password_hash(
                stored_password_hash, password_attempt
            )
        except Exception as hash_err:
            logger.error(
                f"Error during password hash check (is '{password_env}' correctly hashed?): {hash_err}",
                exc_info=True,
            )
            is_valid_password = False  # Treat hash errors as invalid password

        if username_attempt == expected_username and is_valid_password:
            # --- Login Success ---
            session["logged_in"] = True
            session["username"] = username_attempt
            # session.permanent = True # Optionally make session permanent (cookie expiration)
            logger.info(
                f"Web login successful for user '{username_attempt}' from {request.remote_addr}."
            )
            flash("You were successfully logged in!", "success")
            # Redirect to the originally requested page ('next') or default to index
            next_url = request.args.get("next") or url_for("main_routes.index")
            logger.debug(f"Redirecting logged in user to: {next_url}")
            return redirect(next_url)
        else:
            # --- Login Failure ---
            logger.warning(
                f"Invalid web login attempt for username '{username_attempt}' from {request.remote_addr}."
            )
            flash("Invalid username or password provided.", "danger")
            # Re-render login form, WTForms errors (if any) are implicitly passed via form object
            # Return 401 Unauthorized status code
            return render_template("login.html", app_name=app_name, form=form), 401

    # --- GET Request or Failed POST Validation ---
    # If it's a GET request, or if form.validate_on_submit() returned False (e.g., missing fields)
    # WTForms validation errors are automatically available in the template via `form.errors`.
    logger.debug(
        f"Rendering login page (GET request or failed POST validation) from {request.remote_addr}"
    )
    return render_template("login.html", app_name=app_name, form=form)


# --- API Login Route ---
@auth_bp.route("/api/login", methods=["POST"])
@csrf.exempt  # Exempt API login from CSRF protection (uses JWT instead)
def api_login() -> Response:
    """
    Handles API user login using username/password in JSON request body.

    Validates credentials against configured environment variables and returns
    a JWT access token on success.

    Expected JSON Body:
    {
        "username": "your_username",
        "password": "your_password"
    }

    Returns:
        - 200 OK with {"access_token": "..."} on success.
        - 400 Bad Request if JSON body is missing or lacks credentials.
        - 401 Unauthorized if credentials are invalid.
        - 500 Internal Server Error if server auth config is missing.
    """
    logger.debug(
        f"API login request received for /api/login from {request.remote_addr}"
    )

    if not request.is_json:
        logger.warning(
            f"API login failed from {request.remote_addr}: Request body is not JSON."
        )
        return jsonify(message="Request must be JSON"), 400

    data = request.get_json()
    username_attempt = data.get("username")
    password_attempt = data.get("password")

    if not username_attempt or not password_attempt:
        logger.warning(
            f"API login failed from {request.remote_addr}: Missing 'username' or 'password' in JSON body."
        )
        return jsonify(message="Missing username or password parameter"), 400

    logger.info(
        f"API login attempt for username '{username_attempt}' from {request.remote_addr}"
    )

    # Retrieve configured credentials (same as web login)
    username_env = f"{env_name}_USERNAME"
    password_env = f"{env_name}_PASSWORD"
    expected_username = current_app.config.get(username_env)
    stored_password_hash = current_app.config.get(password_env)

    # --- Validate Server Configuration ---
    if not expected_username or not stored_password_hash:
        error_msg = f"Server authentication configuration error: '{username_env}' or '{password_env}' not set."
        logger.critical(error_msg)  # Critical failure
        return jsonify(message="Server configuration error prevents login."), 500

    # --- Validate Credentials ---
    try:
        is_valid_password = check_password_hash(stored_password_hash, password_attempt)
    except Exception as hash_err:
        logger.error(f"Error during API password hash check: {hash_err}", exc_info=True)
        is_valid_password = False

    if username_attempt == expected_username and is_valid_password:
        # --- Login Success: Create JWT ---
        # Identity can be username or any unique identifier
        access_token = create_access_token(identity=username_attempt)
        logger.info(
            f"API login successful for user '{username_attempt}' from {request.remote_addr}. JWT issued."
        )
        return jsonify(access_token=access_token), 200
    else:
        # --- Login Failure ---
        logger.warning(
            f"Invalid API login attempt for username '{username_attempt}' from {request.remote_addr}."
        )
        return jsonify(message="Bad username or password"), 401


# --- Logout Route ---
@auth_bp.route("/logout")
@login_required  # Requires user to be logged in via session to log out
def logout() -> Response:
    """Logs the user out by clearing the Flask session."""
    username = session.get(
        "username", "Unknown user"
    )  # Get username for logging before clearing
    # Clear specific session keys related to login state
    session.pop("logged_in", None)
    session.pop("username", None)
    # session.clear() # Alternative: Clears the entire session

    logger.info(f"User '{username}' logged out from {request.remote_addr}.")
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("auth.login"))  # Redirect to login page after logout
