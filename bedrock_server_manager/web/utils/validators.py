# bedrock-server-manager/bedrock_server_manager/web/validators.py
from flask import request, jsonify, redirect, url_for
from bedrock_server_manager.api.utils import validate_server_exist


def register_server_validation(app):
    @app.before_request
    def check_server_exists():
        # Split the request path into parts
        path_parts = request.path.strip("/").split("/")
        # Look for the 'server' keyword in the URL
        if "server" in path_parts:
            # Get the server name (assumes it's the segment right after 'server')
            index = path_parts.index("server") + 1
            if index < len(path_parts):  # Ensure a server name is present
                server_name = path_parts[index]
                result = validate_server_exist(server_name)
                # If the server doesn't exist, return a JSON error for API endpoints or redirect for others
                if result["status"] == "error":
                    if request.path.startswith("/api/"):
                        return (
                            jsonify({"status": "error", "message": result["message"]}),
                            404,
                        )
                    else:
                        # Redirect to the main route
                        return redirect(url_for("main_routes.index"))
