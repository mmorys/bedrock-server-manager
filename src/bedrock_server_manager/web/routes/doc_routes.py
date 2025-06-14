# bedrock_server_manager/web/routes/doc_routes.py
"""
Flask Blueprint for serving application documentation pages.

This includes user guides, API reference, changelogs, and other
supplementary documentation.
"""
from flask import Blueprint, render_template
from bedrock_server_manager.web.routes.auth_routes import login_required

doc_bp = Blueprint("doc_routes", __name__, url_prefix="/docs")


@doc_bp.route("/")
def doc_index():
    """Renders the main index page for the documentation."""
    return render_template("doc_index.html")


@doc_bp.route("/api")
def api_docs():
    """Renders the API documentation page."""
    return render_template("api_docs.html")


@doc_bp.route("/changelog")
def changelog():
    """Renders the application changelog page."""
    return render_template("changelog.html")
