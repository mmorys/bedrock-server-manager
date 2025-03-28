# bedrock-server-manager/bedrock_server_manager/web/routes/auth_routes.py
import os
import functools
import logging  # Import logging
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
)

logger = logging.getLogger("bedrock_server_manager")  # Get the logger

auth_bp = Blueprint("auth", __name__)


# --- Helper Function / Decorator for Route Protection ---
def login_required(view):
    """
    Decorator that redirects users to the login page
    if they are not logged in.
    """

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if "logged_in" not in session:
            logger.warning(
                f"Unauthorized access attempt to {request.path} from {request.remote_addr}. Redirecting to login."
            )
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        logger.debug(f"Login required check passed for {request.path}")
        return view(**kwargs)

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
        return redirect(url_for("server_routes.index"))  # Redirect to your main page

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
