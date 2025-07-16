import unittest
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


class TestServerConfigManagementMixin(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.server_name = "test_server"
        self.settings = Settings()
        self.settings.set("paths.servers", os.path.join(self.temp_dir, "servers"))
        self.settings._config_dir_path = os.path.join(self.temp_dir, "config")

        self.server = TestBedrockServer(
            server_name=self.server_name, settings_instance=self.settings
        )
        os.makedirs(self.server.server_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_get_server_properties_path(self):
        expected_path = os.path.join(self.server.server_dir, "server.properties")
        self.assertEqual(self.server.get_server_properties_path(), expected_path)

    def test_get_permissions_path(self):
        expected_path = os.path.join(self.server.server_dir, "permissions.json")
        self.assertEqual(self.server.get_permissions_path(), expected_path)

    def test_get_allowlist_path(self):
        expected_path = os.path.join(self.server.server_dir, "allowlist.json")
        self.assertEqual(self.server.get_allowlist_path(), expected_path)

    def test_get_server_properties(self):
        properties_path = self.server.get_server_properties_path()
        with open(properties_path, "w") as f:
            f.write("key1=value1\n")
            f.write("key2=value2\n")

        properties = self.server.get_server_properties()
        self.assertEqual(properties, {"key1": "value1", "key2": "value2"})

    def test_set_server_property(self):
        properties_path = self.server.get_server_properties_path()
        with open(properties_path, "w") as f:
            f.write("key1=value1\n")

        self.server.set_server_property("key2", "value2")

        with open(properties_path, "r") as f:
            lines = f.readlines()
            self.assertIn("key1=value1\n", lines)
            self.assertIn("key2=value2\n", lines)

    def test_get_allowlist(self):
        allowlist_path = self.server.get_allowlist_path()
        allowlist_data = [
            {"name": "player1", "xuid": "12345", "ignoresPlayerLimit": False}
        ]
        with open(allowlist_path, "w") as f:
            json.dump(allowlist_data, f)

        allowlist = self.server.get_allowlist()
        self.assertEqual(allowlist, allowlist_data)

    def test_add_to_allowlist(self):
        allowlist_data = [{"name": "player1", "xuid": "12345"}]
        self.server.add_to_allowlist(allowlist_data)

        allowlist_path = self.server.get_allowlist_path()
        with open(allowlist_path, "r") as f:
            data = json.load(f)
            self.assertEqual(
                data,
                [{"name": "player1", "xuid": "12345", "ignoresPlayerLimit": False}],
            )

    def test_get_formatted_permissions(self):
        permissions_path = self.server.get_permissions_path()
        permissions_data = [{"permission": "operator", "xuid": "12345"}]
        with open(permissions_path, "w") as f:
            json.dump(permissions_data, f)

        permissions = self.server.get_formatted_permissions({"12345": "player1"})
        self.assertEqual(
            permissions,
            [{"xuid": "12345", "name": "player1", "permission_level": "operator"}],
        )

    def test_set_player_permission(self):
        self.server.set_player_permission("12345", "operator", "player1")

        permissions_path = self.server.get_permissions_path()
        with open(permissions_path, "r") as f:
            data = json.load(f)
            self.assertEqual(
                data, [{"permission": "operator", "xuid": "12345", "name": "player1"}]
            )


if __name__ == "__main__":
    unittest.main()
