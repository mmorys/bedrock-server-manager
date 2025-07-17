import pytest
import os
import shutil
import zipfile
import tempfile
import time
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


@pytest.fixture
def backup_restore_fixture():
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    settings = Settings()
    settings.set("paths.servers", os.path.join(temp_dir, "servers"))
    settings.set("paths.backups", os.path.join(temp_dir, "backups"))
    settings._config_dir_path = os.path.join(temp_dir, "config")

    server = TestBedrockServer(server_name=server_name, settings_instance=settings)
    os.makedirs(server.server_dir, exist_ok=True)
    os.makedirs(
        os.path.join(server.server_dir, "worlds", "Bedrock level"), exist_ok=True
    )
    with open(os.path.join(server.server_dir, "server.properties"), "w") as f:
        f.write("level-name=Bedrock level\n")
    with open(
        os.path.join(server.server_dir, "worlds", "Bedrock level", "test.txt"), "w"
    ) as f:
        f.write("test content")

    yield server

    shutil.rmtree(temp_dir)


def test_backup_all_data(backup_restore_fixture):
    server = backup_restore_fixture
    results = server.backup_all_data()
    assert results["world"] is not None
    backups = server.list_backups("all")
    assert len(backups["world_backups"]) == 1
    assert os.path.basename(backups["world_backups"][0]).startswith(
        "Bedrock level_backup_"
    )


def test_list_backups(backup_restore_fixture):
    server = backup_restore_fixture
    backup_dir = server.server_backup_directory
    os.makedirs(backup_dir, exist_ok=True)
    server.backup_all_data()
    time.sleep(1)
    server.backup_all_data()

    server.prune_server_backups("Bedrock level_backup_", "mcworld")

    backups = server.list_backups("world")
    assert len(backups) == 2


def test_restore_all_data_from_latest(backup_restore_fixture):
    server = backup_restore_fixture
    server.backup_all_data()

    shutil.rmtree(os.path.join(server.server_dir, "worlds"))

    server.restore_all_data_from_latest()

    assert os.path.exists(
        os.path.join(server.server_dir, "worlds", "Bedrock level", "test.txt")
    )
