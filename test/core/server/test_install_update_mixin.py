import pytest
import os
import shutil
import zipfile
import tempfile
from unittest.mock import patch, MagicMock

from bedrock_server_manager.core.server.install_update_mixin import (
    ServerInstallUpdateMixin,
)
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.server.config_management_mixin import (
    ServerConfigManagementMixin,
)
from bedrock_server_manager.core.server.world_mixin import ServerWorldMixin
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.core.downloader import BedrockDownloader


class TestBedrockServer(
    ServerInstallUpdateMixin,
    ServerWorldMixin,
    ServerConfigManagementMixin,
    BedrockServerBaseMixin,
):
    def get_server_properties_path(self):
        return os.path.join(self.server_dir, "server.properties")

    def get_world_name(self):
        return "Bedrock level"

    def is_installed(self):
        return False

    def is_running(self):
        return False

    def stop(self):
        pass

    def set_status_in_config(self, status):
        pass

    def set_target_version(self, version):
        pass

    def set_version(self, version):
        pass

    def set_filesystem_permissions(self):
        pass


def zip_dir(path, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(path):
            for file in files:
                zipf.write(
                    os.path.join(root, file),
                    os.path.relpath(os.path.join(root, file), path),
                )


@pytest.fixture
def install_update_fixture():
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    settings = Settings()
    settings.set("paths.servers", os.path.join(temp_dir, "servers"))
    settings.set("paths.downloads", os.path.join(temp_dir, "downloads"))
    settings._config_dir_path = os.path.join(temp_dir, "config")

    server = TestBedrockServer(server_name=server_name, settings_instance=settings)
    os.makedirs(server.server_dir, exist_ok=True)

    yield server

    shutil.rmtree(temp_dir)


@patch("bedrock_server_manager.core.server.install_update_mixin.BedrockDownloader")
@patch(
    "bedrock_server_manager.core.server.install_update_mixin.ServerInstallUpdateMixin._perform_server_files_setup"
)
def test_install_or_update_install(mock_setup, mock_downloader, install_update_fixture):
    server = install_update_fixture
    mock_downloader_instance = mock_downloader.return_value
    mock_downloader_instance.prepare_download_assets.return_value = (
        "1.20.0",
        "/path/to/zip",
        "/path/to/downloads",
    )

    server.install_or_update("LATEST")

    mock_downloader.assert_called_with(
        server_dir=server.server_dir, target_version="LATEST", server_zip_path=None
    )
    mock_downloader_instance.prepare_download_assets.assert_called_once()
    mock_setup.assert_called_with(mock_downloader_instance, False)


@patch("bedrock_server_manager.core.server.install_update_mixin.BedrockDownloader")
@patch(
    "bedrock_server_manager.core.server.install_update_mixin.ServerInstallUpdateMixin._perform_server_files_setup"
)
@patch(
    "bedrock_server_manager.core.server.install_update_mixin.ServerInstallUpdateMixin.is_update_needed",
    return_value=True,
)
def test_install_or_update_update(
    mock_is_update_needed, mock_setup, mock_downloader, install_update_fixture
):
    server = install_update_fixture
    mock_downloader_instance = mock_downloader.return_value
    mock_downloader_instance.prepare_download_assets.return_value = (
        "1.20.0",
        "/path/to/zip",
        "/path/to/downloads",
    )

    with patch.object(server, "is_installed", return_value=True):
        server.install_or_update("LATEST")

    mock_is_update_needed.assert_called_with("LATEST")
    mock_downloader.assert_called_with(
        server_dir=server.server_dir, target_version="LATEST", server_zip_path=None
    )
    mock_downloader_instance.prepare_download_assets.assert_called_once()
    mock_setup.assert_called_with(mock_downloader_instance, True)
