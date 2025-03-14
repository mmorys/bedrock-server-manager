# bedrock-server-manager/bedrock_server_manager/web/routes/server_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from bedrock_server_manager.web.utils import server_list_utils, server_actions
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.config import settings
import os

server_bp = Blueprint("server_routes", __name__)  # Create a blueprint


@server_bp.route("/")
def index():
    base_dir = get_base_dir()
    config_dir = settings.CONFIG_DIR
    servers = server_list_utils.get_server_status_list(
        base_dir, config_dir
    )  # Call util function
    return render_template("index.html", servers=servers)


@server_bp.route("/server/<server_name>/start", methods=["POST"])
def start_server_route(server_name):
    base_dir = get_base_dir()
    message = server_actions.start_server_action(
        server_name, base_dir
    )  # Call start_server_action from utils
    return redirect(
        url_for("server_routes.index", message=message)
    )  # Blueprint-aware url_for


@server_bp.route("/server/<server_name>/stop", methods=["POST"])
def stop_server_route(server_name):
    base_dir = get_base_dir()
    message = server_actions.stop_server_action(
        server_name, base_dir
    )  # Call stop_server_action from utils   <--- UPDATED CALL
    return redirect(
        url_for("server_routes.index", message=message)
    )  # Blueprint-aware url_for


@server_bp.route("/server/<server_name>/restart", methods=["POST"])
def restart_server_route(server_name):
    base_dir = get_base_dir()
    message = server_actions.restart_server_action(
        server_name, base_dir
    )  # Call restart_server_action from utils  <--- UPDATED CALL
    return redirect(
        url_for("server_routes.index", message=message)
    )  # Blueprint-aware url_for


@server_bp.route("/server/<server_name>/update", methods=["POST"])
def update_server_route(server_name):
    base_dir = get_base_dir()
    from bedrock_server_manager.cli import update_server

    try:
        update_server(server_name, base_dir)
        message = (
            f"Server '{server_name}' update process initiated."  # Update might be async
        )
    except Exception as e:
        message = f"Error updating server '{server_name}': {e}"
    return redirect(
        url_for("server_routes.index", message=message)
    )  # Blueprint-aware url_for


@server_bp.route("/install", methods=["GET", "POST"])
def install_server_route():
    if request.method == "POST":
        server_name = request.form["server_name"]
        server_version = request.form["server_version"]

        if not server_name:
            flash("Server name cannot be empty.", "error")
            return render_template("install.html")
        if not server_version:
            flash("Server version cannot be empty.", "error")
            return render_template("install.html")
        if ";" in server_name:
            flash("Server name cannot contain semicolons.", "error")
            return render_template("install.html")

        base_dir = get_base_dir()
        config_dir = settings.CONFIG_DIR

        result = server_actions.install_new_server_action(
            server_name, server_version, base_dir, config_dir
        )

        if isinstance(result, str) and "Error" in result:
            flash(result, "error")
            return render_template(
                "install.html", server_name=server_name, server_version=server_version
            )

        elif isinstance(result, dict):
            # Redirect to configure_properties_route, passing server_name
            return redirect(
                url_for(
                    "server_routes.configure_properties_route",
                    server_name=result["server_name"],
                )
            )
        else:
            print(
                f"Unexpected result type from install_new_server_action: {type(result)}"
            )
            flash("An unexpected error occurred.", "error")
            return redirect(url_for("server_routes.index"))

    else:
        return render_template("install.html")


@server_bp.route("/server/<server_name>/configure", methods=["GET", "POST"])
def configure_properties_route(server_name):
    base_dir = get_base_dir()
    server_dir = os.path.join(base_dir, server_name)
    server_properties_path = os.path.join(server_dir, "server.properties")

    if not os.path.exists(server_properties_path):
        flash(f"server.properties not found for server: {server_name}", "error")
        return redirect(url_for("server_routes.index"))

    if request.method == "POST":
        # Handle form submission (save properties)
        try:
            # Iterate through form data and update properties
            for key, value in request.form.items():
                server_base.modify_server_properties(server_properties_path, key, value)

            # Write Config after properties are set
            config_dir = settings.CONFIG_DIR
            server_base.manage_server_config(
                server_name, "server_name", "write", server_name, config_dir
            )
            # Use level-name for write config:
            target_version = server_actions.get_server_properties(
                server_name, base_dir
            ).get("level-name", settings.DEFAULT_CONFIG["RELEASE_TYPE"])
            server_base.manage_server_config(
                server_name, "target_version", "write", target_version, config_dir
            )  # Corrected line
            server_base.manage_server_config(
                server_name, "status", "write", "INSTALLED", config_dir
            )

            # Create a service (using core logic).
            try:
                system_base.create_service(
                    server_name, base_dir, autoupdate=False
                )  # Call core create service
            except Exception as e:
                return f"Failed to create service: {e}"

            flash(
                f"Server properties for '{server_name}' updated successfully!",
                "success",
            )
            return redirect(url_for("server_routes.index"))

        except Exception as e:
            flash(f"Error updating server properties: {e}", "error")
            # Re-render form with current values
            properties = server_actions.get_server_properties(server_name, base_dir)
            return render_template(
                "configure_properties.html",
                server_name=server_name,
                properties=properties,
            )

    else:  # GET request
        # Load and pass existing properties
        properties = server_actions.get_server_properties(server_name, base_dir)
        if not properties:
            flash(
                f"Error: Could not load properties for server {server_name}.", "error"
            )
            return redirect(url_for("server_routes.index"))
        return render_template(
            "configure_properties.html", server_name=server_name, properties=properties
        )
