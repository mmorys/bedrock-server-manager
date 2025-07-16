import unittest
import os
import platform
import tempfile
import shutil
from unittest.mock import MagicMock, patch

from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.error import MissingArgumentError, ConfigurationError


class TestBedrockServerBaseMixin(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.server_name = "test_server"
        self.settings = Settings()
        self.settings.set("paths.servers", os.path.join(self.temp_dir, "servers"))
        self.settings._config_dir_path = os.path.join(self.temp_dir, "config")
        self.manager_expath = "/path/to/manager"

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        server = BedrockServerBaseMixin(
            server_name=self.server_name,
            settings_instance=self.settings,
            manager_expath=self.manager_expath,
        )

        self.assertEqual(server.server_name, self.server_name)
        self.assertEqual(server.settings, self.settings)
        self.assertIsNotNone(server.logger)
        self.assertEqual(server.manager_expath, self.manager_expath)
        self.assertEqual(server.base_dir, os.path.join(self.temp_dir, "servers"))
        self.assertEqual(
            server.server_dir,
            os.path.join(self.temp_dir, "servers", self.server_name),
        )
        self.assertEqual(server.app_config_dir, os.path.join(self.temp_dir, "config"))
        self.assertEqual(server.os_type, platform.system())

    def test_missing_server_name(self):
        with self.assertRaises(MissingArgumentError):
            BedrockServerBaseMixin(server_name="", settings_instance=self.settings)

    def test_missing_base_dir_setting(self):
        self.settings.set("paths.servers", None)
        with self.assertRaises(ConfigurationError):
            BedrockServerBaseMixin(
                server_name=self.server_name, settings_instance=self.settings
            )

    @patch("bedrock_server_manager.core.server.base_server_mixin.get_settings_instance")
    def test_missing_config_dir_setting(self, mock_get_settings):
        mock_settings = MagicMock()
        mock_settings.config_dir = None
        mock_get_settings.return_value = mock_settings

        with self.assertRaises(ConfigurationError):
            BedrockServerBaseMixin(server_name=self.server_name)

    def test_bedrock_executable_name(self):
        server = BedrockServerBaseMixin(
            server_name=self.server_name, settings_instance=self.settings
        )
        if platform.system() == "Windows":
            self.assertEqual(server.bedrock_executable_name, "bedrock_server.exe")
        else:
            self.assertEqual(server.bedrock_executable_name, "bedrock_server")

    def test_bedrock_executable_path(self):
        server = BedrockServerBaseMixin(
            server_name=self.server_name, settings_instance=self.settings
        )
        expected_path = os.path.join(server.server_dir, server.bedrock_executable_name)
        self.assertEqual(server.bedrock_executable_path, expected_path)

    def test_server_log_path(self):
        server = BedrockServerBaseMixin(
            server_name=self.server_name, settings_instance=self.settings
        )
        expected_path = os.path.join(server.server_dir, "server_output.txt")
        self.assertEqual(server.server_log_path, expected_path)

    def test_server_config_dir_property(self):
        server = BedrockServerBaseMixin(
            server_name=self.server_name, settings_instance=self.settings
        )
        expected_path = os.path.join(server.app_config_dir, server.server_name)
        self.assertEqual(server.server_config_dir, expected_path)

    def test_get_pid_file_path(self):
        server = BedrockServerBaseMixin(
            server_name=self.server_name, settings_instance=self.settings
        )
        expected_filename = f"bedrock_{self.server_name}.pid"
        expected_path = os.path.join(server.server_config_dir, expected_filename)
        self.assertEqual(server.get_pid_file_path(), expected_path)


if __name__ == "__main__":
    unittest.main()
