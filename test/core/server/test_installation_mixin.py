import pytest
import os
import shutil
import tempfile
from bedrock_server_manager.core.server.installation_mixin import ServerInstallationMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.config.settings import Settings

class TestBedrockServer(ServerInstallationMixin, BedrockServerBaseMixin):
    pass

@pytest.fixture
def installation_mixin_fixture():
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    settings = Settings()
    settings.set("paths.servers", os.path.join(temp_dir, "servers"))
    
    server = TestBedrockServer(
        server_name=server_name,
        settings_instance=settings
    )
    os.makedirs(server.server_dir, exist_ok=True)

    yield server, temp_dir

    shutil.rmtree(temp_dir)

def test_is_installed_true(installation_mixin_fixture):
    server, _ = installation_mixin_fixture
    with open(server.bedrock_executable_path, "w") as f:
        f.write("test")
    assert server.is_installed() is True

def test_is_installed_false(installation_mixin_fixture):
    server, _ = installation_mixin_fixture
    assert server.is_installed() is False

def test_is_installed_dir_exists_no_exe(installation_mixin_fixture):
    server, _ = installation_mixin_fixture
    assert server.is_installed() is False
