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


@patch("bedrock_server_manager.web.routers.server_install_config.get_settings_instance")
@patch("bedrock_server_manager.web.routers.server_install_config.os.path.isdir")
@patch("bedrock_server_manager.web.routers.server_install_config.os.listdir")
def test_get_custom_zips(mock_listdir, mock_isdir, mock_get_settings, client):
    """Test the get_custom_zips route with a successful response."""
    mock_get_settings.return_value.get.return_value = "/fake/path"
    mock_isdir.return_value = True
    mock_listdir.return_value = ["zip1.zip", "zip2.zip"]

    response = client.get("/api/downloads/list")
    assert response.status_code == 200
    assert response.json()["custom_zips"] == ["zip1.zip", "zip2.zip"]


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.install_new_server"
)
@patch(
    "bedrock_server_manager.web.routers.server_install_config.utils_api.validate_server_exist"
)
@patch(
    "bedrock_server_manager.web.routers.server_install_config.utils_api.validate_server_name_format"
)
def test_install_server_api_route_success(
    mock_validate_name, mock_validate_exist, mock_install, client
):
    """Test the install_server_api_route with a successful installation."""
    mock_validate_name.return_value = {"status": "success"}
    mock_validate_exist.return_value = {"status": "error"}
    mock_install.return_value = {"status": "success"}

    response = client.post(
        "/api/server/install",
        json={"server_name": "new-server", "server_version": "LATEST"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.get_server_permissions_api"
)
def test_get_server_permissions_api_route(mock_get_permissions, client):
    """Test the get_server_permissions_api_route with a successful response."""
    mock_get_permissions.return_value = {"status": "success"}
    response = client.get("/api/server/test-server/permissions/get")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.server_install_config.system_api.set_autoupdate"
)
@patch(
    "bedrock_server_manager.web.routers.server_install_config.system_api.create_server_service"
)
def test_configure_service_api_route(mock_create_service, mock_set_autoupdate, client):
    """Test the configure_service_api_route with a successful response."""
    mock_set_autoupdate.return_value = {"status": "success"}
    mock_create_service.return_value = {"status": "success"}
    response = client.post(
        "/api/server/test-server/service/update",
        json={"autoupdate": True, "autostart": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.configure_player_permission"
)
def test_configure_permissions_api_route(mock_configure_permission, client):
    """Test the configure_permissions_api_route with a successful response."""
    mock_configure_permission.return_value = {"status": "success"}
    response = client.put(
        "/api/server/test-server/permissions/set",
        json={
            "permissions": [
                {
                    "xuid": "123",
                    "name": "player1",
                    "permission_level": "operator",
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.get_server_allowlist_api"
)
def test_get_allowlist_api_route(mock_get_allowlist, client):
    """Test the get_allowlist_api_route with a successful response."""
    mock_get_allowlist.return_value = {"status": "success"}
    response = client.get("/api/server/test-server/allowlist/get")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.remove_players_from_allowlist"
)
def test_remove_allowlist_players_api_route(mock_remove_from_allowlist, client):
    """Test the remove_allowlist_players_api_route with a successful response."""
    mock_remove_from_allowlist.return_value = {"status": "success"}
    response = client.request(
        "DELETE",
        "/api/server/test-server/allowlist/remove",
        json={"players": ["player1"]},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.get_server_properties_api"
)
def test_get_server_properties_api_route(mock_get_properties, client):
    """Test the get_server_properties_api_route with a successful response."""
    mock_get_properties.return_value = {"status": "success"}
    response = client.get("/api/server/test-server/properties/get")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.add_players_to_allowlist_api"
)
def test_add_to_allowlist_api_route(mock_add_to_allowlist, client):
    """Test the add_to_allowlist_api_route with a successful response."""
    mock_add_to_allowlist.return_value = {"status": "success"}
    response = client.post(
        "/api/server/test-server/allowlist/add",
        json={"players": ["player1"], "ignoresPlayerLimit": False},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.server_install_config.utils_api.validate_server_exist"
)
@patch(
    "bedrock_server_manager.web.routers.server_install_config.utils_api.validate_server_name_format"
)
def test_install_server_api_route_confirmation_needed(
    mock_validate_name, mock_validate_exist, client
):
    """Test the install_server_api_route when confirmation is needed."""
    mock_validate_name.return_value = {"status": "success"}
    mock_validate_exist.return_value = {"status": "success"}

    response = client.post(
        "/api/server/install",
        json={"server_name": "existing-server", "server_version": "LATEST"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirm_needed"


@patch(
    "bedrock_server_manager.web.routers.server_install_config.utils_api.validate_server_name_format"
)
def test_install_server_api_route_invalid_name(mock_validate_name, client):
    """Test the install_server_api_route with an invalid server name."""
    mock_validate_name.return_value = {
        "status": "error",
        "message": "Invalid server name",
    }

    response = client.post(
        "/api/server/install",
        json={"server_name": "invalid name", "server_version": "LATEST"},
    )
    assert response.status_code == 400
    assert "Invalid server name" in response.json()["detail"]


def test_configure_properties_page(client):
    """Test the configure_properties_page route with a successful response."""
    response = client.get("/server/test-server/configure_properties")
    assert response.status_code == 200
    assert "Server Properties" in response.text


def test_configure_allowlist_page(client):
    """Test the configure_allowlist_page route with a successful response."""
    response = client.get("/server/test-server/configure_allowlist")
    assert response.status_code == 200
    assert "Allowlist" in response.text


def test_configure_permissions_page(client):
    """Test the configure_permissions_page route with a successful response."""
    response = client.get("/server/test-server/configure_permissions")
    assert response.status_code == 200
    assert "Permissions" in response.text


def test_configure_service_page(client):
    """Test the configure_service_page route with a successful response."""
    response = client.get("/server/test-server/configure_service")
    assert response.status_code == 200
    assert "Service" in response.text


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.modify_server_properties"
)
def test_configure_properties_api_route(mock_modify_properties, client):
    """Test the configure_properties_api_route with a successful response."""
    mock_modify_properties.return_value = {"status": "success"}
    response = client.post(
        "/api/server/test-server/properties/set",
        json={"properties": {"level-name": "test"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
