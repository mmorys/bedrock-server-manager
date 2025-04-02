# bedrock-server-manager/bedrock_server_manager/web/routes/auth_routes.py
import os
import functools
import logging
import secrets
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_jwt_extended import JWTManager
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token
from wtforms.validators import DataRequired, Length
from wtforms import StringField, PasswordField, SubmitField
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

csrf = CSRFProtect()
jwt = JWTManager()


class LoginForm(FlaskForm):
    """Login form using Flask-WTF."""

    username = StringField(
        "Username",
        validators=[
            DataRequired(message="Username is required."),
            Length(min=1, max=80),
        ],
    )
    password = PasswordField(
        "Password", validators=[DataRequired(message="Password is required.")]
    )
    submit = SubmitField("Login")


# --- Helper Function / Decorator for Route Protection ---
def login_required(view):
    """
    Decorator that checks for a valid WEB SESSION.
    Redirects browser users to login if not authenticated via session.
    Returns 401 for non-browser requests trying to access session-protected routes.
    *** THIS DECORATOR DOES NOT VALIDATE JWT TOKENS ***
    """

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        # 1. Check for active web session ONLY
        if "logged_in" in session:
            # logger.debug(f"Session check passed for user '{session.get('username', 'unknown')}' for path '{request.path}'")
            return view(**kwargs)  # User is logged in via browser session

        # Session not found, determine response type
        best = request.accept_mimetypes.best_match(["application/json", "text/html"])
        is_browser_like = (
            best == "text/html"
            and request.accept_mimetypes[best]
            > request.accept_mimetypes["application/json"]
        )
        # logger.debug(f"Session authentication failed for path '{request.path}'. Browser-like client: {is_browser_like}")

        if is_browser_like:
            # It's likely a browser, redirect to login page
            logger.warning(
                f"Unauthenticated browser access to session-protected route {request.path} from {request.remote_addr}. Redirecting to login."
            )
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        else:
            # It's likely an API client hitting a BROWSER route, return 401
            logger.warning(
                f"Unauthenticated API/non-browser access to session-protected route {request.path} from {request.remote_addr}. Responding with 401."
            )
            return (
                jsonify(
                    error="Unauthorized",
                    message="Authentication required. This endpoint requires a valid web session.",
                ),
                401,
            )

    return wrapped_view


# --- Login Route ---
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handles user login using Flask-WTF Form."""
    if "logged_in" in session:
        return redirect(url_for("main_routes.index"))

    # --- Instantiate the form ---
    form = LoginForm()
    logger.debug(f"LoginForm instantiated for request method: {request.method}")

    # --- Use form.validate_on_submit() ---
    if form.validate_on_submit():
        # --- Form submitted and validated ---
        username_attempt = form.username.data  # Access data via form object
        password_attempt = form.password.data
        logger.info(
            f"Login attempt (validated) for username: '{username_attempt}' from {request.remote_addr}"
        )

        # Get credentials from app config
        expected_username_env = f"{env_name}_USERNAME"
        stored_password_hash_env = f"{env_name}_PASSWORD"
        expected_username = current_app.config.get(expected_username_env)
        stored_password_hash = current_app.config.get(stored_password_hash_env)

        # --- VALIDATION (Server-side config check) ---
        if not expected_username or not stored_password_hash:
            # Log error as before
            logger.error(
                f"{expected_username_env} or {stored_password_hash_env} not set correctly!"
            )
            # Flash message is good, but form validation might already show required field errors
            flash("Application authentication is not configured correctly.", "danger")
            # Render the template again, passing the form to show errors
            return render_template("login.html", app_name=app_name, form=form), 500

        # --- Check Credentials using Hashing ---
        if username_attempt == expected_username and check_password_hash(
            stored_password_hash, password_attempt
        ):
            # --- Login Success ---
            session["logged_in"] = True
            session["username"] = username_attempt
            logger.info(
                f"User '{username_attempt}' logged in successfully from {request.remote_addr}."
            )
            flash("You were successfully logged in!", "success")
            next_url = request.args.get("next") or url_for("main_routes.index")
            logger.debug(f"Redirecting logged in user to: {next_url}")
            return redirect(next_url)
        else:
            # --- Login Failure ---
            logger.warning(
                f"Invalid login attempt for username: '{username_attempt}' from {request.remote_addr}."
            )
            flash("Invalid username or password.", "danger")
            # Render the template again, passing the form (validation might add errors)
            return render_template("login.html", app_name=app_name, form=form), 401

    # --- GET request OR POST request with validation errors ---
    # Pass the form object to the template context
    logger.debug(
        f"Rendering login page for GET request or failed validation from {request.remote_addr}"
    )
    # Any validation errors from a failed POST will be in 'form.errors'
    return render_template("login.html", app_name=app_name, form=form)


@auth_bp.route("/api/login", methods=["POST"])
@csrf.exempt
def api_login():
    """API endpoint to authenticate and receive a JWT access token."""
    logger.debug(f"Received request for /api/login from {request.remote_addr}")

    # Expect credentials in JSON body
    if not request.is_json:
        logger.warning("API login attempt failed: Request missing JSON body.")
        return jsonify({"msg": "Missing JSON in request"}), 400

    username_attempt = request.json.get("username", None)
    password_attempt = request.json.get("password", None)

    if not username_attempt or not password_attempt:
        logger.warning(
            f"API login attempt failed: Missing username or password in JSON body."
        )
        return jsonify({"msg": "Missing username or password parameter"}), 400

    logger.info(
        f"API login attempt for username: '{username_attempt}' from {request.remote_addr}"
    )

    # Get configured credentials from app config (same as web login)
    expected_username_env = f"{env_name}_USERNAME"
    stored_password_hash_env = f"{env_name}_PASSWORD"
    expected_username = current_app.config.get(expected_username_env)
    stored_password_hash = current_app.config.get(stored_password_hash_env)

    # --- Validate Server Config (same check as web login) ---
    if not expected_username or not stored_password_hash:
        logger.error(
            f"API login failed: {expected_username_env} or {stored_password_hash_env} not set correctly!"
        )
        # Avoid overly specific errors to client
        return jsonify({"msg": "Server authentication configuration error."}), 500

    # --- Check Credentials using Hashing (same check as web login) ---
    if username_attempt == expected_username and check_password_hash(
        stored_password_hash, password_attempt
    ):
        # --- Credentials are valid: Generate the JWT ---
        # The 'identity' is stored in the token. It can be the username, user ID, etc.
        # It must be JSON serializable. Username is fine here.
        access_token = create_access_token(identity=username_attempt)
        logger.info(
            f"JWT created successfully for API user '{username_attempt}' from {request.remote_addr}"
        )
        # Return the token to the client
        return jsonify(access_token=access_token), 200  # OK status
    else:
        # --- Invalid Credentials ---
        logger.warning(
            f"Invalid API login attempt for username: '{username_attempt}' from {request.remote_addr}."
        )
        return jsonify({"msg": "Bad username or password"}), 401  # Unauthorized status


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
