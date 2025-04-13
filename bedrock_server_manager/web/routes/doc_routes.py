# bedrock-server-manager/bedrock_server_manager/web/routes/doc_routes.py
"""
Flask Blueprint for serving docs.
"""
from flask import Blueprint, render_template
from bedrock_server_manager.web.routes.auth_routes import login_required

doc_bp = Blueprint("doc_routes", __name__, url_prefix="/docs")


@doc_bp.route("/getting_started")
def getting_started():
    return render_template("getting_started.html")


@doc_bp.route("/")
def doc_index():
    return render_template("doc_index.html")


@doc_bp.route("/api")
def api_docs():
    return render_template("api_docs.html")


@doc_bp.route("/changelog")
def changelog():
    return render_template("changelog.html")
