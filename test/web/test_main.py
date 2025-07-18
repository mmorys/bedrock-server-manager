import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os

# Set the path to the themes directory before importing the app
themes_path = os.path.join(os.path.dirname(__file__), "themes")
if not os.path.exists(themes_path):
    os.makedirs(themes_path)


@pytest.fixture(scope="module")
def client():
    """Create a test client for the app."""
    with patch(
        "bedrock_server_manager.instances.get_settings_instance"
    ) as mock_get_settings_instance:
        mock_settings = MagicMock()
        mock_settings.get.return_value = themes_path
        mock_get_settings_instance.return_value = mock_settings
        from bedrock_server_manager.web.main import app

        yield TestClient(app)


def test_read_main(client):
    """Test that the main page loads."""
    response = client.get("/")
    assert response.status_code == 200


def test_static_files(client):
    """Test that static files are served."""
    response = client.get("/static/css/base.css")
    assert response.status_code == 200


def test_themes_files(client):
    """Test that themes files are served."""
    # Create a dummy css file in the themes folder
    with open(os.path.join(themes_path, "test.css"), "w") as f:
        f.write("body {background-color: red;}")
    response = client.get("/themes/test.css")
    assert response.status_code == 200
    os.remove(os.path.join(themes_path, "test.css"))


def test_openapi_json(client):
    """Test that the OpenAPI JSON is available."""
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Bedrock Server Manager"


def test_swagger_ui(client):
    """Test that the Swagger UI is available."""
    response = client.get("/docs")
    assert response.status_code == 200
