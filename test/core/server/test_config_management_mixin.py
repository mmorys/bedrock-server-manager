import pytest
import os
import json
import tempfile
import shutil
from bedrock_server_manager.core.server.config_management_mixin import (
    ServerConfigManagementMixin,
)
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.config.settings import Settings


class TestBedrockServer(ServerConfigManagementMixin, BedrockServerBaseMixin):
    def get_server_properties_path(self):
        return os.path.join(self.server_dir, "server.properties")

    def get_permissions_path(self):
        return os.path.join(self.server_dir, "permissions.json")

    def get_allowlist_path(self):
        return os.path.join(self.server_dir, "allowlist.json")


@pytest.fixture
def config_management_fixture():
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    settings = Settings()
    settings.set("paths.servers", os.path.join(temp_dir, "servers"))
    settings._config_dir_path = os.path.join(temp_dir, "config")

    server = TestBedrockServer(server_name=server_name, settings_instance=settings)
    os.makedirs(server.server_dir, exist_ok=True)

    yield server

    shutil.rmtree(temp_dir)


def test_get_server_properties_path(config_management_fixture):
    server = config_management_fixture
    expected_path = os.path.join(server.server_dir, "server.properties")
    assert server.get_server_properties_path() == expected_path


def test_get_permissions_path(config_management_fixture):
    server = config_management_fixture
    expected_path = os.path.join(server.server_dir, "permissions.json")
    assert server.get_permissions_path() == expected_path


def test_get_allowlist_path(config_management_fixture):
    server = config_management_fixture
    expected_path = os.path.join(server.server_dir, "allowlist.json")
    assert server.get_allowlist_path() == expected_path


def test_get_server_properties(config_management_fixture):
    server = config_management_fixture
    properties_path = server.get_server_properties_path()
    with open(properties_path, "w") as f:
        f.write("key1=value1\n")
        f.write("key2=value2\n")

    properties = server.get_server_properties()
    assert properties == {"key1": "value1", "key2": "value2"}


def test_set_server_property(config_management_fixture):
    server = config_management_fixture
    properties_path = server.get_server_properties_path()
    with open(properties_path, "w") as f:
        f.write("key1=value1\n")

    server.set_server_property("key2", "value2")

    with open(properties_path, "r") as f:
        lines = f.readlines()
        assert "key1=value1\n" in lines
        assert "key2=value2\n" in lines


def test_get_allowlist(config_management_fixture):
    server = config_management_fixture
    allowlist_path = server.get_allowlist_path()
    allowlist_data = [{"name": "player1", "xuid": "12345", "ignoresPlayerLimit": False}]
    with open(allowlist_path, "w") as f:
        json.dump(allowlist_data, f)

    allowlist = server.get_allowlist()
    assert allowlist == allowlist_data


def test_add_to_allowlist(config_management_fixture):
    server = config_management_fixture
    allowlist_data = [{"name": "player1", "xuid": "12345"}]
    server.add_to_allowlist(allowlist_data)

    allowlist_path = server.get_allowlist_path()
    with open(allowlist_path, "r") as f:
        data = json.load(f)
        assert data == [
            {"name": "player1", "xuid": "12345", "ignoresPlayerLimit": False}
        ]


def test_get_formatted_permissions(config_management_fixture):
    server = config_management_fixture
    permissions_path = server.get_permissions_path()
    permissions_data = [{"permission": "operator", "xuid": "12345"}]
    with open(permissions_path, "w") as f:
        json.dump(permissions_data, f)

    permissions = server.get_formatted_permissions({"12345": "player1"})
    assert permissions == [
        {"xuid": "12345", "name": "player1", "permission_level": "operator"}
    ]


def test_set_player_permission(config_management_fixture):
    server = config_management_fixture
    server.set_player_permission("12345", "operator", "player1")

    permissions_path = server.get_permissions_path()
    with open(permissions_path, "r") as f:
        data = json.load(f)
        assert data == [{"permission": "operator", "xuid": "12345", "name": "player1"}]
