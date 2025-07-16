import unittest
import os
import shutil
import zipfile
import tempfile
from bedrock_server_manager.core.server.backup_restore_mixin import ServerBackupMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.server.config_management_mixin import (
    ServerConfigManagementMixin,
)
from bedrock_server_manager.config.settings import Settings


class TestBedrockServer(
    ServerBackupMixin, ServerConfigManagementMixin, BedrockServerBaseMixin
):
    def get_server_properties_path(self):
        return os.path.join(self.server_dir, "server.properties")

    def get_world_name(self):
        return "Bedrock level"

    def export_world_directory_to_mcworld(self, world_dir_name, output_path):
        zip_dir(os.path.join(self.server_dir, "worlds", world_dir_name), output_path)

    def import_active_world_from_mcworld(self, mcworld_path):
        world_name = os.path.basename(mcworld_path).split("_backup_")[0]
        world_path = os.path.join(self.server_dir, "worlds", world_name)
        os.makedirs(world_path, exist_ok=True)
        with zipfile.ZipFile(mcworld_path, "r") as zip_ref:
            zip_ref.extractall(world_path)
        return world_name


def zip_dir(path, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(path):
            for file in files:
                zipf.write(
                    os.path.join(root, file),
                    os.path.relpath(os.path.join(root, file), path),
                )


class TestServerBackupRestoreMixin(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.server_name = "test_server"
        self.settings = Settings()
        self.settings.set("paths.servers", os.path.join(self.temp_dir, "servers"))
        self.settings.set("paths.backups", os.path.join(self.temp_dir, "backups"))
        self.settings._config_dir_path = os.path.join(self.temp_dir, "config")

        self.server = TestBedrockServer(
            server_name=self.server_name, settings_instance=self.settings
        )
        os.makedirs(self.server.server_dir, exist_ok=True)
        os.makedirs(
            os.path.join(self.server.server_dir, "worlds", "Bedrock level"),
            exist_ok=True,
        )
        with open(os.path.join(self.server.server_dir, "server.properties"), "w") as f:
            f.write("level-name=Bedrock level\n")
        with open(
            os.path.join(self.server.server_dir, "worlds", "Bedrock level", "test.txt"),
            "w",
        ) as f:
            f.write("test content")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_backup_all_data(self):
        results = self.server.backup_all_data()
        self.assertIsNotNone(results["world"])
        backups = self.server.list_backups("all")
        self.assertEqual(len(backups["world_backups"]), 1)
        self.assertTrue(
            os.path.basename(backups["world_backups"][0]).startswith(
                "Bedrock level_backup_"
            )
        )

    def test_list_backups(self):
        backup_dir = self.server.server_backup_directory
        os.makedirs(backup_dir, exist_ok=True)
        self.server.backup_all_data()
        import time

        time.sleep(1)
        self.server.backup_all_data()

        backups = self.server.list_backups("world")
        self.assertEqual(len(backups), 2)

    def test_restore_all_data_from_latest(self):
        self.server.backup_all_data()

        shutil.rmtree(os.path.join(self.server.server_dir, "worlds"))

        self.server.restore_all_data_from_latest()

        self.assertTrue(
            os.path.exists(
                os.path.join(
                    self.server.server_dir, "worlds", "Bedrock level", "test.txt"
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
