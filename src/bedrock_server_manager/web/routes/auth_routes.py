# bedrock_server_manager/web/routes/auth_routes.py
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
from enum import Enum, auto
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
from bedrock_server_manager.config.const import env_name

logger = logging.getLogger(__name__)

# --- Blueprint and Extension Setup ---
auth_bp = Blueprint(
    "auth",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)
csrf = CSRFProtect()
jwt = JWTManager()


# --- Forms ---
class LoginForm(FlaskForm):
    """Login form definition using Flask-WTF."""

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
    submit = SubmitField("Log In")


# --- Decorator for Session-Based Authentication ---
def login_required(view: Callable) -> Callable:
    """Decorator enforcing authentication via Flask web session ONLY."""

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs) -> Response:
        if session.get("logged_in"):
            return view(*args, **kwargs)

        logger.warning(
            f"Session authentication failed for path '{request.path}' from {request.remote_addr}."
        )
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
            return redirect(url_for("auth.login", next=request.full_path))
        else:
            return (
                jsonify(error="Unauthorized", message="Valid web session required."),
                401,
            )

    return wrapped_view


# --- Centralized Authentication Logic ---


class AuthResult(Enum):
    """Enumeration for the result of a credential validation attempt."""

    SUCCESS = auto()
    INVALID_CREDENTIALS = auto()
    SERVER_CONFIG_ERROR = auto()


def _validate_credentials(username_attempt: str, password_attempt: str) -> AuthResult:
    """
    Validates a username and password against configured credentials.

    This is the central, shared authentication logic, used by both web and API logins.

    Returns:
        AuthResult: An enum indicating the outcome of the validation.
    """
    username_env = f"{env_name}_USERNAME"
    password_env = f"{env_name}_PASSWORD"
    expected_username = current_app.config.get(username_env)
    stored_password_hash = current_app.config.get(password_env)

    if not expected_username or not stored_password_hash:
        logger.critical(
            f"Server authentication configuration error: '{username_env}' or '{password_env}' not set."
        )
        return AuthResult.SERVER_CONFIG_ERROR

    if username_attempt != expected_username:
        return AuthResult.INVALID_CREDENTIALS

    try:
        if check_password_hash(stored_password_hash, password_attempt):
            return AuthResult.SUCCESS
    except Exception as hash_err:
        logger.error(
            f"Error during password hash check (is '{password_env}' a valid hash?): {hash_err}",
            exc_info=True,
        )

    return AuthResult.INVALID_CREDENTIALS


# --- Web UI Login Route ---
@auth_bp.route("/login", methods=["GET", "POST"])
def login() -> Response:
    """Handles user login for the web UI (session-based)."""
    if session.get("logged_in"):
        return redirect(url_for("main_routes.index"))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        logger.info(f"Web login attempt for '{username}' from {request.remote_addr}")

        auth_result = _validate_credentials(username, password)

        if auth_result == AuthResult.SUCCESS:
            session["logged_in"] = True
            session["username"] = username
            logger.info(
                f"Web login successful for '{username}' from {request.remote_addr}."
            )
            flash("You were successfully logged in!", "success")
            next_url = request.args.get("next") or url_for("main_routes.index")
            return redirect(next_url)

        elif auth_result == AuthResult.SERVER_CONFIG_ERROR:
            flash(
                "Login failed due to a server configuration issue. Please contact the administrator.",
                "danger",
            )
            return render_template("login.html", form=form), 500

        else:  # AuthResult.INVALID_CREDENTIALS
            logger.warning(
                f"Invalid web login attempt for '{username}' from {request.remote_addr}."
            )
            flash("Invalid username or password provided.", "danger")
            return render_template("login.html", form=form), 401

    return render_template("login.html", form=form)


# --- API Login Route ---
@auth_bp.route("/api/login", methods=["POST"])
@csrf.exempt
def api_login() -> Response:
    """Handles API user login (JWT-based)."""
    if not request.is_json:
        return jsonify(message="Request must be JSON"), 400

    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify(message="Missing username or password parameter"), 400

    logger.info(f"API login attempt for '{username}' from {request.remote_addr}")

    auth_result = _validate_credentials(username, password)

    if auth_result == AuthResult.SUCCESS:
        access_token = create_access_token(identity=username)
        logger.info(f"API login successful for '{username}'. JWT issued.")
        return jsonify(access_token=access_token)

    elif auth_result == AuthResult.SERVER_CONFIG_ERROR:
        return jsonify(message="Server configuration error prevents login."), 500

    else:  # AuthResult.INVALID_CREDENTIALS
        logger.warning(
            f"Invalid API login attempt for '{username}' from {request.remote_addr}."
        )
        return jsonify(message="Bad username or password"), 401


# --- Logout Route ---
@auth_bp.route("/logout")
@login_required
def logout() -> Response:
    """Logs the user out by clearing the Flask session."""
    username = session.get("username", "Unknown user")
    session.pop("logged_in", None)
    session.pop("username", None)
    logger.info(f"User '{username}' logged out from {request.remote_addr}.")
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("auth.login"))
