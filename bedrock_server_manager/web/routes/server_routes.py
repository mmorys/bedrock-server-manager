# bedrock-server-manager/bedrock_server_manager/web/routes/server_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import os
import platform
import logging
import json
from bedrock_server_manager import handlers
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.config.settings import EXPATH, app_name
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.web.routes.auth_routes import login_required

logger = logging.getLogger("bedrock_server_manager")

server_bp = Blueprint("server_routes", __name__)


@server_bp.route("/")
@login_required
def index():
    base_dir = get_base_dir()
    # Use the handler to get server status.
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)
    if status_response["status"] == "error":
        flash(f"Error getting server status: {status_response['message']}", "error")
        servers = []  # Provide an empty list so the template doesn't break
    else:
        servers = status_response["servers"]
    logger.debug(f"Rendering index.html with servers: {servers}")
    return render_template("index.html", servers=servers, app_name=app_name)


@server_bp.route("/manage_servers")
@login_required
def manage_server_route():
    base_dir = get_base_dir()
    # Use the handler to get server status.
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)
    if status_response["status"] == "error":
        flash(f"Error getting server status: {status_response['message']}", "error")
        servers = []  # Provide an empty list so the template doesn't break
    else:
        servers = status_response["servers"]
    logger.debug(f"Rendering manage_servers.html with servers: {servers}")
    return render_template("manage_servers.html", servers=servers, app_name=app_name)


@server_bp.route("/advanced_menu")
@login_required
def advanced_menu_route():
    base_dir = get_base_dir()
    # Use the handler to get server status.
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)
    if status_response["status"] == "error":
        flash(f"Error getting server status: {status_response['message']}", "error")
        servers = []  # Provide an empty list so the template doesn't break
    else:
        servers = status_response["servers"]
    logger.debug(f"Rendering advanced_menu.html with servers: {servers}")
    return render_template("advanced_menu.html", servers=servers, app_name=app_name)


@server_bp.route("/server/<server_name>/start", methods=["GET", "POST"])
def start_server_route(server_name):
    base_dir = get_base_dir()
    response = handlers.start_server_handler(server_name, base_dir)
    if response["status"] == "success":
        flash(f"Server '{server_name}' started successfully.", "success")
        logger.debug(f"stop_server_route: server started: {server_name}")
    else:
        flash(f"Error starting server '{server_name}': {response['message']}", "error")
        logger.error(f"Error starting server {server_name}: {response['message']}")
    return redirect(url_for("server_routes.index"))


@server_bp.route("/server/<server_name>/stop", methods=["GET", "POST"])
@login_required
def stop_server_route(server_name):
    base_dir = get_base_dir()
    response = handlers.stop_server_handler(server_name, base_dir)
    if response["status"] == "success":
        flash(f"Server '{server_name}' stopped successfully.", "success")
        logger.debug(f"stop_server_route: server stopped: {server_name}")
    else:
        flash(f"Error stopping server '{server_name}': {response['message']}", "error")
        logger.error(f"Error stopping server {server_name}: {response['message']}")
    return redirect(url_for("server_routes.index"))


@server_bp.route("/server/<server_name>/restart", methods=["GET", "POST"])
@login_required
def restart_server_route(server_name):
    base_dir = get_base_dir()
    response = handlers.restart_server_handler(server_name, base_dir)
    if response["status"] == "success":
        flash(f"Server '{server_name}' restarted successfully.", "success")
        logger.debug(f"restart_server_route: server restarted: {server_name}")
    else:
        flash(
            f"Error restarting server '{server_name}': {response['message']}", "error"
        )
        logger.error(f"Error restarting server {server_name}: {response['message']}")
    return redirect(url_for("server_routes.index"))


@server_bp.route("/server/<server_name>/send", methods=["POST"])
@login_required
def send_command_route(server_name):
    base_dir = get_base_dir()
    data = request.get_json()  # Get the JSON data from the request body
    command = data.get("command")  # Get the 'command' value

    if not command:
        logger.warning(
            f"Received send_command request for {server_name} with empty command."
        )
        return jsonify({"status": "error", "message": "Command cannot be empty."}), 400

    logger.info(f"Received command for {server_name}: {command}")
    result = handlers.send_command_handler(server_name, command, base_dir)
    return jsonify(result)  # Return JSON response


@server_bp.route("/server/<server_name>/update", methods=["GET", "POST"])
@login_required
def update_server_route(server_name):
    base_dir = get_base_dir()
    response = handlers.update_server_handler(server_name, base_dir=base_dir)
    if response["status"] == "success":
        flash(f"Server '{server_name}' Updated successfully.", "success")
        logger.info(f"Server updated: {server_name}")
    else:
        flash(f"Error updating server '{server_name}': {response['message']}", "error")
        logger.error(f"Error updating server {server_name}: {response['message']}")
    return redirect(url_for("server_routes.manage_server_route"))


@server_bp.route("/install", methods=["GET", "POST"])
@login_required
def install_server_route():
    if request.method == "POST":
        server_name = request.form["server_name"]
        server_version = request.form["server_version"]

        if not server_name:
            flash("Server name cannot be empty.", "error")
            logger.warning("Attempted to install server with empty name.")
            return render_template("install.html", app_name=app_name)
        if not server_version:
            flash("Server version cannot be empty.", "error")
            logger.warning(
                f"Attempted to install server {server_name} with empty version."
            )
            return render_template(
                "install.html", server_name=server_name, app_name=app_name
            )
        if ";" in server_name:
            flash("Server name cannot contain semicolons.", "error")
            logger.warning(
                f"Attempted to install server with invalid name: {server_name}"
            )
            return render_template("install.html", app_name=app_name)
        # Validate the format
        validation_result = handlers.validate_server_name_format_handler(server_name)
        if validation_result["status"] == "error":
            flash(validation_result["message"], "error")
            logger.warning(
                f"Server name validation failed: {validation_result['message']}"
            )
            return render_template(
                "install.html",
                server_name=server_name,
                server_version=server_version,
                app_name=app_name,
            )

        base_dir = get_base_dir()
        config_dir = settings.get("CONFIG_DIR")

        # Check if server exists *before* calling the handler.
        server_dir = os.path.join(base_dir, server_name)
        if os.path.exists(server_dir):
            logger.info(
                f"Server {server_name} already exists.  Prompting for confirmation."
            )
            # Render install.html with confirm_delete=True and the server_name.
            return render_template(
                "install.html",
                confirm_delete=True,
                server_name=server_name,
                server_version=server_version,
                app_name=app_name,
            )

        # If server doesn't exist, proceed with installation.
        logger.info(f"Installing new server: {server_name}, version: {server_version}")
        result = handlers.install_new_server_handler(
            server_name, server_version, base_dir, config_dir
        )

        if result["status"] == "error":
            flash(result["message"], "error")
            logger.error(f"Error installing server {server_name}: {result['message']}")
            return render_template(
                "install.html",
                server_name=server_name,
                server_version=server_version,
                app_name=app_name,
            )
        elif result["status"] == "confirm":
            logger.info(
                f"Server {server_name} requires confirmation to proceed (should not occur here)."
            )
            return render_template(
                "install.html",
                confirm_delete=True,
                server_name=result["server_name"],
                server_version=result["server_version"],
                app_name=app_name,
            )
        elif result["status"] == "success":
            logger.info(
                f"Server {server_name} installed successfully.  Redirecting to configure_properties."
            )
            return redirect(
                url_for(
                    "server_routes.configure_properties_route",
                    server_name=result["server_name"],
                    new_install=True,
                )
            )
        else:
            logger.error("An unexpected error occurred during installation.")
            flash("An unexpected error occurred.", "error")
            return redirect(url_for("server_routes.index"))

    else:  # request.method == 'GET'
        return render_template("install.html", app_name=app_name)


@server_bp.route("/install/confirm", methods=["POST"])
@login_required
def confirm_install_route():
    server_name = request.form.get("server_name")
    server_version = request.form.get("server_version")
    confirm = request.form.get("confirm")
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")

    if not server_name or not server_version:
        flash("Missing server name or version.", "error")
        logger.warning("Confirmation request with missing server name or version.")
        return redirect(url_for("server_routes.index"))

    if confirm == "yes":
        logger.info(f"Confirmed deletion and reinstallation of server: {server_name}")
        # Delete existing server data.
        delete_result = handlers.delete_server_data_handler(
            server_name, base_dir, config_dir
        )
        if delete_result["status"] == "error":
            flash(
                f"Error deleting existing server data: {delete_result['message']}",
                "error",
            )
            logger.error(
                f"Error deleting existing server data for {server_name}: {delete_result['message']}"
            )
            return render_template(
                "install.html",
                server_name=server_name,
                server_version=server_version,
                app_name=app_name,
            )

        # Call install_new_server_handler AGAIN, after deletion.
        install_result = handlers.install_new_server_handler(
            server_name, server_version, base_dir, config_dir
        )

        if install_result["status"] == "error":
            flash(install_result["message"], "error")
            logger.error(
                f"Error installing server {server_name} after deletion: {install_result['message']}"
            )
            return render_template(
                "install.html",
                server_name=server_name,
                server_version=server_version,
                app_name=app_name,
            )

        elif install_result["status"] == "success":
            logger.info(
                f"Server {server_name} reinstalled successfully.  Redirecting to configuration."
            )
            return redirect(
                url_for(
                    "server_routes.configure_properties_route",
                    server_name=install_result["server_name"],
                    new_install=True,
                )
            )

        else:
            logger.error(
                "An unexpected error occurred during installation after deletion."
            )
            flash("An unexpected error occurred during installation.", "error")
            return redirect(url_for("server_routes.index"))

    elif confirm == "no":
        logger.info(f"Server installation cancelled for {server_name}.")
        flash("Server installation cancelled.", "info")
        return redirect(url_for("server_routes.index"))
    else:
        logger.warning(
            f"Invalid confirmation value for server {server_name}: {confirm}"
        )
        flash("Invalid confirmation value.", "error")
        return redirect(url_for("server_routes.index"))


@server_bp.route("/server/<server_name>/delete", methods=["POST"])
@login_required
def delete_server_route(server_name):
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")

    # Call the handler to delete the server data
    result = handlers.delete_server_data_handler(server_name, base_dir, config_dir)

    if result["status"] == "success":
        flash(f"Server '{server_name}' deleted successfully.", "success")
        logger.info(f"Server deleted: {server_name}")
    else:
        flash(f"Error deleting server '{server_name}': {result['message']}", "error")
        logger.error(f"Error deleting server {server_name}: {result['message']}")

    return redirect(url_for("server_routes.manage_server_route"))


@server_bp.route("/server/<server_name>/configure_properties", methods=["GET", "POST"])
@login_required
def configure_properties_route(server_name):
    base_dir = get_base_dir()
    server_dir = os.path.join(base_dir, server_name)
    server_properties_path = os.path.join(server_dir, "server.properties")

    if not os.path.exists(server_properties_path):
        flash(f"server.properties not found for server: {server_name}", "error")
        logger.error(f"server.properties not found for server: {server_name}")
        return redirect(url_for("server_routes.advanced_menu_route"))
    # Check if new_install is True, convert to boolean
    new_install_str = request.args.get(
        "new_install", "False"
    )  # Get as string, default "False"
    new_install = new_install_str.lower() == "true"
    logger.debug(
        f"Configuring properties for server: {server_name}, new_install: {new_install}"
    )
    if request.method == "POST":
        # Handle form submission (save properties)
        properties_to_update = {}
        allowed_keys = [
            "server-name",
            "level-name",
            "gamemode",
            "difficulty",
            "allow-cheats",
            "server-port",
            "server-portv6",
            "enable-lan-visibility",
            "allow-list",
            "max-players",
            "default-player-permission-level",
            "view-distance",
            "tick-distance",
            "level-seed",
            "online-mode",
            "texturepack-required",
        ]
        for key in allowed_keys:
            value = request.form.get(key)
            if value is not None:
                if key == "level-name":
                    value = value.replace(" ", "_")
                validation_response = handlers.validate_property_value_handler(
                    key, value
                )
                if validation_response["status"] == "error":
                    flash(validation_response["message"], "error")
                    logger.error(
                        f"Validation error for {key}={value}: {validation_response['message']}"
                    )
                    current_properties = handlers.read_server_properties_handler(
                        server_name, base_dir
                    )["properties"]
                    return render_template(
                        "configure_properties.html",
                        server_name=server_name,
                        properties=current_properties,
                        new_install=new_install,
                        app_name=app_name,
                    )
                properties_to_update[key] = value
        modify_response = handlers.modify_server_properties_handler(
            server_name, properties_to_update, base_dir
        )
        if modify_response["status"] == "error":
            flash(
                f"Error updating server properties: {modify_response['message']}",
                "error",
            )
            logger.error(
                f"Error updating server properties for {server_name}: {modify_response['message']}"
            )
            current_properties = handlers.read_server_properties_handler(
                server_name, base_dir
            )["properties"]
            return render_template(
                "configure_properties.html",
                server_name=server_name,
                properties=current_properties,
                new_install=new_install,
                app_name=app_name,
            )

        # Write server config
        config_dir = settings.get("CONFIG_DIR")
        write_config_response = handlers.write_server_config_handler(
            server_name, "server_name", server_name, config_dir
        )
        if write_config_response["status"] == "error":
            flash(write_config_response["message"], "error")
            logger.error(
                f"Error writing server_name to config: {write_config_response['message']}"
            )

        level_name = request.form.get("level-name")
        write_config_response = handlers.write_server_config_handler(
            server_name, "target_version", level_name, config_dir
        )
        if write_config_response["status"] == "error":
            flash(write_config_response["message"], "error")
            logger.error(
                f"Error writing target_version to config: {write_config_response['message']}"
            )

        write_config_response = handlers.write_server_config_handler(
            server_name, "status", "INSTALLED", config_dir
        )
        if write_config_response["status"] == "error":
            flash(write_config_response["message"], "error")
            logger.error(
                f"Error writing status to config: {write_config_response['message']}"
            )
        flash(f"Server properties for '{server_name}' updated successfully!", "success")
        logger.info(f"Server properties for '{server_name}' updated successfully!")

        # Redirect based on new_install flag
        if new_install:
            return redirect(
                url_for(
                    "server_routes.configure_allowlist_route",
                    server_name=server_name,
                    new_install=new_install,
                )
            )
        else:
            return redirect(url_for("server_routes.advanced_menu_route"))

    else:  # GET request
        properties_response = handlers.read_server_properties_handler(
            server_name, base_dir
        )
        if properties_response["status"] == "error":
            flash(
                f"Error loading properties: {properties_response['message']}", "error"
            )
            logger.error(
                f"Error loading properties for {server_name}: {properties_response['message']}"
            )
            return redirect(url_for("server_routes.advanced_menu_route"))

        return render_template(
            "configure_properties.html",
            server_name=server_name,
            properties=properties_response["properties"],
            new_install=new_install,
            app_name=app_name,
        )


@server_bp.route("/server/<server_name>/configure_allowlist", methods=["GET", "POST"])
@login_required
def configure_allowlist_route(server_name):
    base_dir = get_base_dir()
    new_install_str = request.args.get(
        "new_install", "False"
    )  # Get as string, default "False"
    new_install = new_install_str.lower() == "true"
    logger.debug(
        f"Configuring allowlist for server: {server_name}, new_install: {new_install}"
    )

    if request.method == "POST":
        player_names_raw = request.form.get("player_names", "")
        ignore_limit = (
            request.form.get("ignore_limit") == "on"
        )  # Convert checkbox to boolean

        # Process player names (split into a list, remove empty lines)
        player_names = [
            name.strip() for name in player_names_raw.splitlines() if name.strip()
        ]

        new_players_data = []
        for name in player_names:
            new_players_data.append({"name": name, "ignoresPlayerLimit": ignore_limit})
            logger.debug(f"Adding player to allowlist data: {name}")

        result = handlers.configure_allowlist_handler(
            server_name, base_dir, new_players_data
        )

        if result["status"] == "success":
            flash(f"Allowlist for '{server_name}' updated successfully!", "success")
            logger.info(f"Allowlist for '{server_name}' updated successfully!")
            if new_install:
                return redirect(
                    url_for(
                        "server_routes.configure_permissions_route",
                        server_name=server_name,
                        new_install=new_install,
                    )
                )
            else:
                return redirect(url_for("server_routes.advanced_menu_route"))
        else:
            flash(f"Error updating allowlist: {result['message']}", "error")
            logger.error(
                f"Error updating allowlist for {server_name}: {result['message']}"
            )
            # Re-render the form with the existing and attempted new players
            return render_template(
                "configure_allowlist.html",
                server_name=server_name,
                existing_players=result.get("existing_players", []),
                new_install=new_install,
                app_name=app_name,
            )

    else:  # GET request
        result = handlers.configure_allowlist_handler(server_name, base_dir)
        if result["status"] == "error":
            flash(f"Error loading allowlist: {result['message']}", "error")
            logger.error(
                f"Error loading allowlist for {server_name}: {result['message']}"
            )
            return redirect(url_for("server_routes.advanced_menu_route"))

        existing_players = result.get("existing_players", [])  # Default to empty list
        return render_template(
            "configure_allowlist.html",
            server_name=server_name,
            existing_players=existing_players,
            new_install=new_install,
            app_name=app_name,
        )


@server_bp.route("/server/<server_name>/configure_permissions", methods=["GET", "POST"])
@login_required
def configure_permissions_route(server_name):
    base_dir = get_base_dir()
    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"

    logger.debug(
        f"Configuring permissions for server: {server_name}, new_install: {new_install}"
    )

    if request.method == "POST":
        # Handle form submission (save permissions)
        permissions_data = {}
        for xuid, permission in request.form.items():
            if permission.lower() not in ("visitor", "member", "operator"):
                flash(
                    f"Invalid permission level for XUID {xuid}: {permission}", "error"
                )
                logger.error(f"Invalid permission level for XUID {xuid}: {permission}")
                return redirect(
                    url_for(
                        "server_routes.configure_permissions_route",
                        server_name=server_name,
                        new_install=new_install,
                    )
                )

            permissions_data[xuid] = permission.lower()

        players_response = handlers.get_players_from_json_handler()
        if players_response["status"] == "error":
            # We still want to continue even if we cannot load player names.
            player_names = {}  # Just use an empty dict.
            logger.warning("Failed to load player names from players.json.")
        else:
            player_names = {
                player["xuid"]: player["name"] for player in players_response["players"]
            }

        for xuid, permission in permissions_data.items():
            player_name = player_names.get(xuid, "Unknown Player")
            result = handlers.configure_player_permission_handler(
                server_name, xuid, player_name, permission, base_dir
            )
            if result["status"] == "error":
                flash(
                    f"Error setting permission for {player_name}: {result['message']}",
                    "error",
                )
                logger.error(
                    f"Error setting permission for {player_name} ({xuid}): {result['message']}"
                )
                # Continue to the next player, even on error

        flash(f"Permissions for server '{server_name}' updated.", "success")
        logger.info(f"Permissions for server '{server_name}' updated.")
        if new_install:
            return redirect(
                url_for(
                    "server_routes.configure_service_route",
                    server_name=server_name,
                    new_install=new_install,
                )
            )
        return redirect(url_for("server_routes.advanced_menu_route"))

    else:  # GET request
        players_response = handlers.get_players_from_json_handler()
        if players_response["status"] == "error":
            # Instead of redirecting, flash a message and continue rendering the template.
            flash(
                f"Error loading player data: {players_response['message']}.  No players found.",
                "warning",
            )
            logger.warning(f"Error loading player data: {players_response['message']}")
            players = []  # Provide an empty list so the template doesn't break.
        else:
            players = players_response["players"]
            logger.debug(f"Loaded players for permissions configuration: {players}")

        permissions = {}
        try:
            server_dir = os.path.join(base_dir, server_name)
            permissions_file = os.path.join(server_dir, "permissions.json")
            if os.path.exists(permissions_file):
                with open(permissions_file, "r") as f:
                    permissions_data = json.load(f)
                    for player_entry in permissions_data:
                        permissions[player_entry["xuid"]] = player_entry["permission"]
                logger.debug(f"Loaded existing permissions: {permissions}")
        except (OSError, json.JSONDecodeError) as e:
            flash(f"Error reading permissions.json: {e}", "error")
            logger.error(f"Error reading permissions.json for {server_name}: {e}")

        return render_template(
            "configure_permissions.html",
            server_name=server_name,
            players=players,
            permissions=permissions,
            new_install=new_install,
            app_name=app_name,
        )


@server_bp.route("/server/<server_name>/configure_service", methods=["GET", "POST"])
@login_required
def configure_service_route(server_name):
    base_dir = get_base_dir()
    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"
    logger.debug(
        f"Configuring service for server: {server_name}, new_install: {new_install}"
    )
    if request.method == "POST":
        if platform.system() == "Linux":
            autoupdate = request.form.get("autoupdate") == "on"
            autostart = request.form.get("autostart") == "on"
            response = handlers.create_systemd_service_handler(
                server_name, base_dir, autoupdate, autostart
            )
            if response["status"] == "error":
                flash(response["message"], "error")
                logger.error(
                    f"Error creating systemd service for {server_name}: {response['message']}"
                )
                # Re-render the form with current values
                return render_template(
                    "configure_service.html",
                    server_name=server_name,
                    os=platform.system(),
                    autoupdate=autoupdate,
                    autostart=autostart,
                    new_install=new_install,
                    app_name=app_name,
                )

        elif platform.system() == "Windows":
            autoupdate = request.form.get("autoupdate") == "on"
            response = handlers.set_windows_autoupdate_handler(
                server_name, "true" if autoupdate else "false"
            )  # Convert boolean to string
            if response["status"] == "error":
                flash(response["message"], "error")
                logger.error(
                    f"Error setting Windows autoupdate for {server_name}: {response['message']}"
                )
                # Re-render the form
                return render_template(
                    "configure_service.html",
                    server_name=server_name,
                    os=platform.system(),
                    autoupdate=autoupdate,
                    new_install=new_install,
                    app_name=app_name,
                )
        else:
            flash("Unsupported operating system for service configuration.", "error")
            logger.error(
                f"Unsupported OS for service configuration: {platform.system()}"
            )
            return redirect(url_for("server_routes.advanced_menu_route"))

        flash(f"Service settings for '{server_name}' updated successfully!", "success")
        logger.info(f"Service settings for '{server_name}' updated successfully!")

        # Check if we should start the server
        if new_install:
            if request.form.get("start_server") == "on":  # Check if checkbox is checked
                start_result = handlers.start_server_handler(server_name, base_dir)
                if start_result["status"] == "error":
                    flash(f"Error starting server: {start_result['message']}", "error")
                    logger.error(
                        f"Error starting server {server_name} after install: {start_result['message']}"
                    )
                    #  Even if start fails, continue to index.  User can start manually.
                else:
                    flash(f"Server '{server_name}' started.", "success")
                    logger.info(f"Server '{server_name}' started after install.")
            return redirect(url_for("server_routes.advanced_menu_route"))
        return redirect(url_for("server_routes.advanced_menu_route"))

    else:  # GET request
        if platform.system() == "Linux":
            # For Linux, we don't need to pre-populate any values. systemd handles it.
            logger.debug("Rendering configure_service.html for Linux")
            return render_template(
                "configure_service.html",
                server_name=server_name,
                os=platform.system(),
                new_install=new_install,
                app_name=app_name,
            )
        elif platform.system() == "Windows":
            # Get current autoupdate setting from config.json
            config_dir = settings.get("CONFIG_DIR")
            autoupdate_value = server_base.manage_server_config(
                server_name, "autoupdate", "read", config_dir=config_dir
            )
            # Convert config value to boolean for checkbox
            autoupdate = autoupdate_value == "true" if autoupdate_value else False
            logger.debug(
                f"Rendering configure_service.html for Windows, autoupdate: {autoupdate}"
            )
            return render_template(
                "configure_service.html",
                server_name=server_name,
                os=platform.system(),
                autoupdate=autoupdate,  # Pass the boolean value
                new_install=new_install,
                app_name=app_name,
            )
        else:
            flash("Unsupported operating system for service configuration.", "error")
            logger.error(
                f"Unsupported OS for service configuration: {platform.system()}"
            )
            return redirect(url_for("server_routes.advanced_menu_route"))


@server_bp.route("/server/<server_name>/backup", methods=["GET"])
@login_required
def backup_menu_route(server_name):
    return render_template(
        "backup_menu.html", server_name=server_name, app_name=app_name
    )


@server_bp.route("/server/<server_name>/backup/config", methods=["GET"])
@login_required
def backup_config_select_route(server_name):
    return render_template(
        "backup_config_options.html", server_name=server_name, app_name=app_name
    )


@server_bp.route("/server/<server_name>/backup/action", methods=["POST"])
@login_required
def backup_action_route(server_name):
    base_dir = get_base_dir()
    backup_type = request.form.get("backup_type")  # "world", "config", or "all"
    file_to_backup = request.form.get(
        "file_to_backup"
    )  # Will be None unless backup_type is "config"

    if not backup_type:
        flash("Invalid backup type.", "error")
        logger.warning(
            f"Invalid backup request for {server_name}: No backup type specified."
        )
        return redirect(url_for("server_routes.manage_server_route"))

    if backup_type == "config" and not file_to_backup:
        logger.warning(
            f"Invalid backup request for {server_name}: No file selected for config backup."
        )
        return redirect(
            url_for("server_routes.backup_config_select_route", server_name=server_name)
        )
    logger.info(
        f"Performing backup for server: {server_name}, type: {backup_type}, file: {file_to_backup}"
    )
    if backup_type == "world":
        result = handlers.backup_world_handler(server_name, base_dir)
    elif backup_type == "config":
        result = handlers.backup_config_file_handler(
            server_name, file_to_backup, base_dir
        )
    elif backup_type == "all":
        result = handlers.backup_all_handler(server_name, base_dir)
    else:
        flash("Invalid backup type.", "error")
        logger.error(f"Invalid backup type specified: {backup_type}")
        return redirect(url_for("server_routes.manage_server_route"))

    if result["status"] == "error":
        flash(f"Backup failed: {result['message']}", "error")
        logger.error(f"Backup failed for {server_name}: {result['message']}")
    else:
        flash("Backup completed successfully!", "success")
        logger.info(f"Backup completed successfully for {server_name}")

    # Always redirect back to the main index page after backup
    return redirect(url_for("server_routes.manage_server_route"))


@server_bp.route("/server/<server_name>/restore", methods=["GET"])
@login_required
def restore_menu_route(server_name):
    """Displays the restore menu."""
    logger.info(f"Displaying restore menu for server: {server_name}")
    return render_template(
        "restore_menu.html", server_name=server_name, app_name=app_name
    )


@server_bp.route("/server/<server_name>/restore/select", methods=["POST"])
@login_required
def restore_select_backup_route(server_name):
    """Displays the list of available backups for the selected type."""
    base_dir = get_base_dir()
    restore_type = request.form.get("restore_type")
    if not restore_type:
        flash("No restore type selected.", "error")
        logger.warning(
            f"Restore request for {server_name} with no restore type selected."
        )
        return redirect(url_for("server_routes.index"))

    logger.info(
        f"Displaying backup selection for restore type '{restore_type}' for server: {server_name}"
    )

    # Handle "Restore All" as a special case, since there's no selection.
    if restore_type == "all":
        result = handlers.restore_all_handler(server_name, base_dir)
        if result["status"] == "error":
            flash(f"Error restoring all files: {result['message']}", "error")
            logger.error(
                f"Error restoring all files for {server_name}: {result['message']}"
            )
        else:
            flash("All files restored successfully!", "success")
            logger.info(f"All files restored successfully for {server_name}")
        return redirect(url_for("server_routes.manage_server_route"))

    # Handle other backup types (world, config)
    list_response = handlers.list_backups_handler(server_name, restore_type, base_dir)
    if list_response["status"] == "error":
        flash(f"Error listing backups: {list_response['message']}", "error")
        logger.error(
            f"Error listing backups for {server_name} ({restore_type}): {list_response['message']}"
        )
        return redirect(url_for("server_routes.manage_server_route"))

    return render_template(
        "restore_select_backup.html",
        server_name=server_name,
        restore_type=restore_type,
        backups=list_response["backups"],
        app_name=app_name,
    )


@server_bp.route("/server/<server_name>/restore/action", methods=["POST"])
@login_required
def restore_action_route(server_name):
    """Performs the actual restoration based on the selected backup file and type."""
    base_dir = get_base_dir()
    backup_file = request.form.get("backup_file")
    restore_type = request.form.get("restore_type")

    if not backup_file or not restore_type:
        flash("Invalid restore request.", "error")
        logger.warning(
            f"Invalid restore request for {server_name}: Missing backup file or restore type."
        )
        return redirect(url_for("server_routes.manage_server_route"))

    logger.info(
        f"Restoring server: {server_name}, type: {restore_type}, file: {backup_file}"
    )
    if restore_type == "world":
        result = handlers.restore_world_handler(server_name, backup_file, base_dir)
    elif restore_type == "config":
        result = handlers.restore_config_file_handler(
            server_name, backup_file, base_dir
        )
    else:
        flash("Invalid restore type.", "error")
        logger.error(f"Invalid restore type specified: {restore_type}")
        return redirect(url_for("server_routes.manage_server_route"))

    if result["status"] == "error":
        flash(f"Error during restoration: {result['message']}", "error")
        logger.error(f"Error during restoration for {server_name}: {result['message']}")
    else:
        flash("Restoration completed successfully!", "success")
        logger.info(f"Restoration completed successfully for {server_name}")

    return redirect(url_for("server_routes.manage_server_route"))


@server_bp.route("/install_content")
@login_required
def install_content_menu_route():
    base_dir = get_base_dir()
    # Use the handler to get server status.
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)
    if status_response["status"] == "error":
        flash(f"Error getting server status: {status_response['message']}", "error")
        servers = []  # Provide an empty list so the template doesn't break
    else:
        servers = status_response["servers"]
    logger.debug("Rendering install_content.html")
    return render_template("install_content.html", servers=servers, app_name=app_name)


@server_bp.route("/server/<server_name>/install_world", methods=["GET", "POST"])
@login_required
def install_world_route(server_name):
    base_dir = get_base_dir()
    content_dir = os.path.join(settings.get("CONTENT_DIR"), "worlds")
    logger.info(f"Installing world for server: {server_name}")

    if request.method == "POST":
        selected_file = request.form.get("selected_file")
        if not selected_file:
            flash("No world file selected.", "error")
            logger.warning(
                f"Install world request for {server_name} with no file selected."
            )
            return redirect(url_for("server_routes.install_content_menu_route"))

        # Check if world exists *before* calling handler
        world_name_result = handlers.get_world_name_handler(server_name, base_dir)
        if world_name_result["status"] == "success":  # world exists.
            world_name = world_name_result["world_name"]
            world_path = os.path.join(base_dir, server_name, "worlds", world_name)
            if os.path.exists(world_path):
                # World Exists, confirm overwrite
                logger.info(
                    f"World already exists for {server_name}. Prompting for overwrite."
                )
                return render_template(
                    "confirm_world_overwrite.html",
                    server_name=server_name,
                    selected_file=selected_file,
                    app_name=app_name,
                )
            else:
                # World does not exist
                logger.info(
                    f"World does not exist for {server_name}. Proceeding with installation."
                )
                result = handlers.extract_world_handler(
                    server_name, selected_file, base_dir
                )
                if result["status"] == "error":
                    flash(f"Error importing world: {result['message']}", "error")
                    logger.error(
                        f"Error importing world for {server_name}: {result['message']}"
                    )
                else:
                    flash("World imported successfully!", "success")
                    logger.info(f"World imported successfully for {server_name}")
                return redirect(url_for("server_routes.install_content_menu_route"))
        else:
            # Error getting world.
            flash(f"Error getting world: {world_name_result['message']}", "error")
            logger.error(
                f"Error getting world name for {server_name}: {world_name_result['message']}"
            )
            return redirect(url_for("server_routes.install_content_menu_route"))

    else:  # GET request
        result = handlers.list_content_files_handler(content_dir, ["mcworld"])
        if result["status"] == "error":
            flash(result["message"], "error")
            logger.error(f"Error listing world files: {result['message']}")
            world_files = []
        else:
            world_files = result["files"]
            logger.debug(f"Found world files: {world_files}")
        return render_template(
            "select_world.html",
            server_name=server_name,
            world_files=world_files,
            app_name=app_name,
        )


@server_bp.route("/server/<server_name>/install_world/confirm", methods=["POST"])
@login_required
def confirm_world_overwrite_route(server_name):
    base_dir = get_base_dir()
    selected_file = request.form.get("selected_file")
    confirm = request.form.get("confirm")
    logger.info(
        f"Confirming world overwrite for server: {server_name}, file: {selected_file}, confirm: {confirm}"
    )

    if not selected_file:
        flash("No world file selected.", "error")
        logger.warning(
            f"World overwrite confirmation request for {server_name} with no file selected."
        )
        return redirect(url_for("server_routes.install_content_menu_route"))

    if confirm == "yes":
        # Proceed with world extraction (overwriting existing)
        result = handlers.extract_world_handler(server_name, selected_file, base_dir)
        if result["status"] == "error":
            flash(f"Error importing world: {result['message']}", "error")
            logger.error(
                f"Error importing world (overwrite) for {server_name}: {result['message']}"
            )
        else:
            flash("World imported successfully!", "success")
            logger.info(f"World imported successfully (overwrite) for {server_name}")
    else:
        flash("World import cancelled.", "info")
        logger.info(f"World import cancelled for {server_name}")

    return redirect(url_for("server_routes.install_content_menu_route"))


@server_bp.route("/server/<server_name>/install_addon", methods=["GET", "POST"])
@login_required
def install_addon_route(server_name):
    base_dir = get_base_dir()
    content_dir = os.path.join(settings.get("CONTENT_DIR"), "addons")
    logger.info(f"Installing addon for server: {server_name}")

    if request.method == "POST":
        selected_file = request.form.get("selected_file")
        if not selected_file:
            flash("No addon file selected.", "error")
            logger.warning(
                f"Addon install request for {server_name} with no file selected."
            )
            return redirect(url_for("server_routes.install_content_menu_route"))

        result = handlers.install_addon_handler(server_name, selected_file, base_dir)
        if result["status"] == "error":
            flash(f"Error installing addon: {result['message']}", "error")
            logger.error(
                f"Error installing addon for {server_name}: {result['message']}"
            )
        else:
            flash("Addon installed successfully!", "success")
            logger.info(f"Addon installed successfully for {server_name}")
        return redirect(url_for("server_routes.install_content_menu_route"))

    else:  # GET request
        result = handlers.list_content_files_handler(content_dir, ["mcaddon", "mcpack"])
        if result["status"] == "error":
            flash(result["message"], "error")
            logger.error(f"Error listing addon files: {result['message']}")
            addon_files = []
        else:
            addon_files = result["files"]
            logger.debug(f"Found addon files: {addon_files}")
        return render_template(
            "select_addon.html",
            server_name=server_name,
            addon_files=addon_files,
            app_name=app_name,
        )


@server_bp.route("/server/<server_name>/monitor")
@login_required
def monitor_server_route(server_name):
    """Displays the server monitoring page."""
    logger.info(f"Displaying monitoring page for server: {server_name}")
    return render_template("monitor.html", server_name=server_name, app_name=app_name)


@server_bp.route("/api/server/<server_name>/status")
@login_required
def server_status_api(server_name):
    """Provides server status information as JSON."""
    base_dir = get_base_dir()
    result = handlers.get_bedrock_process_info_handler(server_name, base_dir)
    logger.debug(f"Providing server status API for {server_name}: {result}")
    return jsonify(result)  # Return JSON response


@server_bp.route("/server/<server_name>/schedule", methods=["GET"])
@login_required
def schedule_tasks_route(server_name):
    base_dir = get_base_dir()
    # Get cron jobs using the handler
    cron_jobs_response = handlers.get_server_cron_jobs_handler(server_name)
    if cron_jobs_response["status"] == "error":
        flash(cron_jobs_response["message"], "error")
        logger.error(
            f"Error getting cron jobs for {server_name}: {cron_jobs_response['message']}"
        )
        table_data = []  # Provide empty data if there's an error
    else:
        cron_jobs = cron_jobs_response["cron_jobs"]
        # Get formatted table data using the handler
        table_response = handlers.get_cron_jobs_table_handler(cron_jobs)
        if table_response["status"] == "error":
            flash(table_response["message"], "error")
            logger.error(
                f"Error formatting cron jobs for {server_name}: {table_response['message']}"
            )
            table_data = []
        else:
            table_data = table_response["table_data"]
    logger.info(f"Displaying schedule tasks page for server: {server_name}")
    return render_template(
        "schedule_tasks.html",
        server_name=server_name,
        table_data=table_data,
        EXPATH=EXPATH,
        app_name=app_name,
    )


@server_bp.route("/server/<server_name>/schedule/add", methods=["POST"])
@login_required
def add_cron_job_route(server_name):
    base_dir = get_base_dir()
    data = request.get_json()
    cron_string = data.get("new_cron_job")

    if not cron_string:
        logger.warning(
            f"Add cron job request for {server_name} with empty cron string."
        )
        return jsonify({"status": "error", "message": "Cron string is required."}), 400

    logger.info(f"Adding cron job for {server_name}: {cron_string}")
    add_response = handlers.add_cron_job_handler(cron_string)
    return jsonify(add_response)  # Return JSON response


@server_bp.route("/server/<server_name>/schedule/modify", methods=["POST"])
@login_required
def modify_cron_job_route(server_name):
    base_dir = get_base_dir()
    data = request.get_json()
    old_cron_string = data.get("old_cron_job")
    new_cron_string = data.get("new_cron_job")
    logger.info(
        f"Modifying cron job for {server_name}. Old: {old_cron_string}, New: {new_cron_string}"
    )
    if not old_cron_string or not new_cron_string:
        logger.warning(
            f"Modify cron job request for {server_name} with missing old or new cron string."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Both old and new cron strings are required.",
                }
            ),
            400,
        )

    modify_response = handlers.modify_cron_job_handler(old_cron_string, new_cron_string)
    return jsonify(modify_response)  # Return JSON response


@server_bp.route("/server/<server_name>/schedule/delete", methods=["POST"])
@login_required
def delete_cron_job_route(server_name):
    base_dir = get_base_dir()
    data = request.get_json()
    cron_string = data.get("cron_string")
    logger.info(f"Deleting cron job for {server_name}: {cron_string}")
    if not cron_string:
        logger.warning(
            f"Delete cron job request for {server_name} with empty cron string."
        )
        return jsonify({"status": "error", "message": "Cron string is required."}), 400
    delete_response = handlers.delete_cron_job_handler(cron_string)
    return jsonify(delete_response)  # Return JSON response


@server_bp.route("/server/<server_name>/tasks", methods=["GET"])
@login_required
def schedule_tasks_windows_route(server_name):
    """Displays the Windows Task Scheduler UI."""
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    logger.info(f"Displaying schedule tasks page for server: {server_name}")

    if platform.system() != "Windows":
        flash("Task scheduling is only available on Windows.", "error")
        logger.warning(
            f"Attempted to access Windows task scheduler from non-Windows system."
        )
        return redirect(url_for("server_routes.index"))

    task_names_response = handlers.get_server_task_names_handler(
        server_name, config_dir
    )
    if task_names_response["status"] == "error":
        flash(f"Error getting task names: {task_names_response['message']}", "error")
        logger.error(
            f"Error getting task names for {server_name}: {task_names_response['message']}"
        )
        tasks = []  # Provide an empty list so the template doesn't break
    else:
        task_names = task_names_response["task_names"]
        # Get detailed task info using the handler
        task_info_response = handlers.get_windows_task_info_handler(
            [task[0] for task in task_names]  # Extract task names
        )
        if task_info_response["status"] == "error":
            flash(f"Error getting task info: {task_info_response['message']}", "error")
            logger.error(
                f"Error getting task info for {server_name}: {task_info_response['message']}"
            )
            tasks = []
        else:
            tasks = task_info_response["task_info"]

    return render_template(
        "schedule_tasks_windows.html",
        server_name=server_name,
        tasks=tasks,
        app_name=app_name,
    )


@server_bp.route("/server/<server_name>/tasks/add", methods=["GET", "POST"])
@login_required
def add_windows_task_route(server_name):
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    logger.info(f"Adding Windows task for server: {server_name}")
    if request.method == "POST":
        command = request.form.get("command")
        command_args = f"--server {server_name}"
        if command == "update-server":
            pass  # command args already correct.
        elif command == "backup-all":
            pass
        elif command == "start-server":
            pass
        elif command == "stop-server":
            pass
        elif command == "restart-server":
            pass
        elif command == "scan-players":
            command_args = ""  # No args
        else:
            flash("Invalid command selected.", "error")
            logger.warning(f"Invalid command selected for Windows task: {command}")
            return render_template(
                "add_windows_task.html", server_name=server_name, app_name=app_name
            )

        task_name = f"bedrock_{server_name}_{command.replace('-', '_')}"
        triggers = []

        # Process trigger data (iterate through form data)
        trigger_num = 1
        while True:  # Loop until we run out of trigger data
            trigger_type = request.form.get(f"trigger_type_{trigger_num}")
            if not trigger_type:
                break  # No more triggers

            trigger_data = {"type": trigger_type}
            trigger_data["start"] = request.form.get(f"start_{trigger_num}")

            if trigger_type == "Daily":
                trigger_data["interval"] = int(
                    request.form.get(f"interval_{trigger_num}")
                )
            elif trigger_type == "Weekly":
                trigger_data["interval"] = int(
                    request.form.get(f"interval_{trigger_num}")
                )
                days_of_week_str = request.form.get(f"days_of_week_{trigger_num}", "")
                trigger_data["days"] = [
                    day.strip() for day in days_of_week_str.split(",") if day.strip()
                ]
            elif trigger_type == "Monthly":
                days_of_month_str = request.form.get(f"days_of_month_{trigger_num}", "")
                trigger_data["days"] = [
                    int(day.strip())
                    for day in days_of_month_str.split(",")
                    if day.strip().isdigit()
                ]
                months_str = request.form.get(f"months_{trigger_num}", "")
                trigger_data["months"] = [
                    month.strip() for month in months_str.split(",") if month.strip()
                ]

            triggers.append(trigger_data)
            trigger_num += 1

        # Call handler to create the task
        result = handlers.create_windows_task_handler(
            server_name,
            command,
            command_args,
            task_name,
            config_dir,
            triggers,
            base_dir,
        )

        if result["status"] == "success":
            flash(f"Task '{task_name}' added successfully!", "success")
            logger.info(f"Task '{task_name}' added successfully for {server_name}")
            return redirect(
                url_for(
                    "server_routes.schedule_tasks_windows_route",
                    server_name=server_name,
                )
            )
        else:
            flash(f"Error adding task: {result['message']}", "error")
            logger.error(
                f"Error adding task '{task_name}' for {server_name}: {result['message']}"
            )
            return render_template(
                "add_windows_task.html", server_name=server_name, app_name=app_name
            )

    return render_template(
        "add_windows_task.html", server_name=server_name, app_name=app_name
    )


@server_bp.route(
    "/server/<server_name>/tasks/modify/<task_name>", methods=["GET", "POST"]
)
@login_required
def modify_windows_task_route(server_name, task_name):
    base_dir = get_base_dir()
    config_dir = settings.CONFIG_DIR
    logger.info(f"Modifying Windows task: {task_name} for server: {server_name}")
    # TODO: Implement modify logic (similar to add, but loading existing task data)

    return render_template(
        "modify_windows_task.html",
        server_name=server_name,
        task_name=task_name,
        app_name=app_name,
    )


@server_bp.route("/server/<server_name>/tasks/delete", methods=["POST"])
@login_required
def delete_windows_task_route(server_name):
    base_dir = get_base_dir()
    config_dir = settings.CONFIG_DIR
    task_name = request.form.get("task_name")
    task_file_path = request.form.get("task_file_path")

    logger.info(f"Deleting Windows task: {task_name} for server: {server_name}")
    if not task_name or not task_file_path:
        flash("Invalid task deletion request.", "error")
        logger.warning(
            f"Invalid task deletion request for {server_name}: Missing task name or file path."
        )
        return redirect(url_for("server_routes.index"))

    result = handlers.delete_windows_task_handler(task_name, task_file_path, base_dir)

    if result["status"] == "error":
        flash(f"Error deleting task: {result['message']}", "error")
        logger.error(
            f"Error deleting task {task_name} for server {server_name}: {result['message']}"
        )
    else:
        flash(f"Task '{task_name}' deleted successfully!", "success")
        logger.info(f"Task '{task_name}' deleted successfully for {server_name}")
    return redirect(
        url_for("server_routes.schedule_tasks_windows_route", server_name=server_name)
    )  # redirect back to list of tasks
