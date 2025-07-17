import pytest
import os
import platform
import tempfile
import shutil
from unittest.mock import MagicMock

from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.error import MissingArgumentError, ConfigurationError


@pytest.fixture
def base_server_mixin_fixture():
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    settings = Settings()
    settings.set("paths.servers", os.path.join(temp_dir, "servers"))
    settings._config_dir_path = os.path.join(temp_dir, "config")
    manager_expath = "/path/to/manager"

    yield temp_dir, server_name, settings, manager_expath

    shutil.rmtree(temp_dir)


def test_initialization(base_server_mixin_fixture):
    temp_dir, server_name, settings, manager_expath = base_server_mixin_fixture
    server = BedrockServerBaseMixin(
        server_name=server_name,
        settings_instance=settings,
        manager_expath=manager_expath,
    )

    assert server.server_name == server_name
    assert server.settings == settings
    assert server.logger is not None
    assert server.manager_expath == manager_expath
    assert server.base_dir == os.path.join(temp_dir, "servers")
    assert server.server_dir == os.path.join(temp_dir, "servers", server_name)
    assert server.app_config_dir == os.path.join(temp_dir, "config")
    assert server.os_type == platform.system()


def test_missing_server_name(base_server_mixin_fixture):
    _, _, settings, _ = base_server_mixin_fixture
    with pytest.raises(MissingArgumentError):
        BedrockServerBaseMixin(server_name="", settings_instance=settings)


def test_missing_base_dir_setting(base_server_mixin_fixture):
    _, server_name, settings, _ = base_server_mixin_fixture
    settings.set("paths.servers", None)
    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(server_name=server_name, settings_instance=settings)


def test_missing_config_dir_setting(monkeypatch):
    mock_settings = MagicMock()
    mock_settings.config_dir = None
    monkeypatch.setattr(
        "bedrock_server_manager.core.server.base_server_mixin.get_settings_instance",
        lambda: mock_settings,
    )

    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(server_name="test_server")


def test_bedrock_executable_name(base_server_mixin_fixture):
    _, server_name, settings, _ = base_server_mixin_fixture
    server = BedrockServerBaseMixin(server_name=server_name, settings_instance=settings)
    if platform.system() == "Windows":
        assert server.bedrock_executable_name == "bedrock_server.exe"
    else:
        assert server.bedrock_executable_name == "bedrock_server"


def test_bedrock_executable_path(base_server_mixin_fixture):
    _, server_name, settings, _ = base_server_mixin_fixture
    server = BedrockServerBaseMixin(server_name=server_name, settings_instance=settings)
    expected_path = os.path.join(server.server_dir, server.bedrock_executable_name)
    assert server.bedrock_executable_path == expected_path


def test_server_log_path(base_server_mixin_fixture):
    _, server_name, settings, _ = base_server_mixin_fixture
    server = BedrockServerBaseMixin(server_name=server_name, settings_instance=settings)
    expected_path = os.path.join(server.server_dir, "server_output.txt")
    assert server.server_log_path == expected_path


def test_server_config_dir_property(base_server_mixin_fixture):
    _, server_name, settings, _ = base_server_mixin_fixture
    server = BedrockServerBaseMixin(server_name=server_name, settings_instance=settings)
    expected_path = os.path.join(server.app_config_dir, server.server_name)
    assert server.server_config_dir == expected_path


def test_get_pid_file_path(base_server_mixin_fixture):
    _, server_name, settings, _ = base_server_mixin_fixture
    server = BedrockServerBaseMixin(server_name=server_name, settings_instance=settings)
    expected_filename = f"bedrock_{server_name}.pid"
    expected_path = os.path.join(server.server_config_dir, expected_filename)
    assert server.get_pid_file_path() == expected_path
