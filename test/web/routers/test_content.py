import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from bedrock_server_manager.web.main import app
from bedrock_server_manager.web.dependencies import validate_server_exists
from bedrock_server_manager.web.auth_utils import create_access_token
from datetime import timedelta
import os

# Test data
TEST_USER = "testuser"


@pytest.fixture
def client():
    """Create a test client for the app, with authentication and mocked dependencies."""
    os.environ["BEDROCK_SERVER_MANAGER_USERNAME"] = TEST_USER
    os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"] = "testpassword"
    os.environ["BEDROCK_SERVER_MANAGER_SECRET_KEY"] = "test-secret-key"

    app.dependency_overrides[validate_server_exists] = lambda: "test-server"

    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=15)
    )
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {access_token}"

    yield client

    del os.environ["BEDROCK_SERVER_MANAGER_USERNAME"]
    del os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"]
    del os.environ["BEDROCK_SERVER_MANAGER_SECRET_KEY"]
    app.dependency_overrides = {}


@patch("bedrock_server_manager.web.routers.content.app_api.list_available_worlds_api")
def test_list_worlds_api_route_success(mock_list_worlds, client):
    """Test the list_worlds_api_route with a successful response."""
    mock_list_worlds.return_value = {
        "status": "success",
        "files": ["world1.mcworld", "world2.mcworld"],
    }
    response = client.get("/api/content/worlds")
    assert response.status_code == 200
    assert response.json()["files"] == ["world1.mcworld", "world2.mcworld"]


@patch("bedrock_server_manager.web.routers.content.app_api.list_available_worlds_api")
def test_list_worlds_api_route_failure(mock_list_worlds, client):
    """Test the list_worlds_api_route with a failed response."""
    mock_list_worlds.return_value = {
        "status": "error",
        "message": "Failed to list worlds",
    }
    response = client.get("/api/content/worlds")
    assert response.status_code == 500
    assert (
        "A critical server error occurred while listing worlds."
        in response.json()["detail"]
    )


@patch("bedrock_server_manager.web.routers.content.app_api.list_available_addons_api")
def test_list_addons_api_route_success(mock_list_addons, client):
    """Test the list_addons_api_route with a successful response."""
    mock_list_addons.return_value = {
        "status": "success",
        "files": ["addon1.mcaddon", "addon2.mcpack"],
    }
    response = client.get("/api/content/addons")
    assert response.status_code == 200
    assert response.json()["files"] == ["addon1.mcaddon", "addon2.mcpack"]


@patch("bedrock_server_manager.web.routers.content.app_api.list_available_addons_api")
def test_list_addons_api_route_failure(mock_list_addons, client):
    """Test the list_addons_api_route with a failed response."""
    mock_list_addons.return_value = {
        "status": "error",
        "message": "Failed to list addons",
    }
    response = client.get("/api/content/addons")
    assert response.status_code == 500
    assert (
        "A critical server error occurred while listing addons."
        in response.json()["detail"]
    )


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
@patch("bedrock_server_manager.web.routers.content.get_settings_instance")
def test_install_world_api_route_success(
    mock_get_settings, mock_isfile, mock_validate_server, client
):
    """Test the install_world_api_route with a successful response."""
    mock_validate_server.return_value = True
    mock_isfile.return_value = True
    mock_get_settings.return_value.get.return_value = "/fake/path"

    response = client.post(
        "/api/server/test-server/world/install",
        json={"filename": "world.mcworld"},
    )
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
@patch("bedrock_server_manager.web.routers.content.get_settings_instance")
def test_install_world_api_route_not_found(
    mock_get_settings, mock_isfile, mock_validate_server, client
):
    """Test the install_world_api_route with a file not found error."""
    mock_validate_server.return_value = True
    mock_isfile.return_value = False
    mock_get_settings.return_value.get.return_value = "/fake/path"

    response = client.post(
        "/api/server/test-server/world/install",
        json={"filename": "world.mcworld"},
    )
    assert response.status_code == 404
    assert "not found for import" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
def test_export_world_api_route_success(mock_validate_server, client):
    """Test the export_world_api_route with a successful response."""
    mock_validate_server.return_value = True

    response = client.post("/api/server/test-server/world/export")
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
def test_reset_world_api_route_success(mock_validate_server, client):
    """Test the reset_world_api_route with a successful response."""
    mock_validate_server.return_value = True

    response = client.delete("/api/server/test-server/world/reset")
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
@patch("bedrock_server_manager.web.routers.content.get_settings_instance")
def test_install_addon_api_route_success(
    mock_get_settings, mock_isfile, mock_validate_server, client
):
    """Test the install_addon_api_route with a successful response."""
    mock_validate_server.return_value = True
    mock_isfile.return_value = True
    mock_get_settings.return_value.get.return_value = "/fake/path"

    response = client.post(
        "/api/server/test-server/addon/install",
        json={"filename": "addon.mcaddon"},
    )
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
@patch("bedrock_server_manager.web.routers.content.get_settings_instance")
def test_install_addon_api_route_not_found(
    mock_get_settings, mock_isfile, mock_validate_server, client
):
    """Test the install_addon_api_route with a file not found error."""
    mock_validate_server.return_value = True
    mock_isfile.return_value = False
    mock_get_settings.return_value.get.return_value = "/fake/path"

    response = client.post(
        "/api/server/test-server/addon/install",
        json={"filename": "addon.mcaddon"},
    )
    assert response.status_code == 404
    assert "not found for import" in response.json()["detail"]
