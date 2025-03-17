# bedrock-server-manager/tests/config/test_settings.py
import json
import os
import pytest
from unittest.mock import patch, mock_open
from bedrock_server_manager.config.settings import Settings, ConfigError
import logging

# Use a consistent logger name
logger = logging.getLogger("bedrock_server_manager")

# --- Fixtures ---


@pytest.fixture
def tmp_config_dir(tmp_path):
    """
    Provides a temporary directory and patches _get_app_data_dir.
    """
    app_data_dir = tmp_path / "bedrock-server-manager"
    config_dir = app_data_dir / ".config"
    config_dir.mkdir(parents=True, exist_ok=True)

    print(f"tmp_config_dir: app_data_dir = {app_data_dir}")  # DEBUG

    with patch.object(Settings, "_get_app_data_dir", return_value=str(app_data_dir)):
        yield app_data_dir


@pytest.fixture
def settings_obj(tmp_config_dir):
    """Provides a fresh Settings object."""
    print(f"settings_obj: tmp_config_dir = {tmp_config_dir}")  # DEBUG
    return Settings()


@pytest.fixture
def settings_obj_custom_env(tmp_path):
    custom_app_data_dir = tmp_path / "custom_app_data"

    with patch.dict(
        os.environ, {"BEDROCK_SERVER_MANAGER_DATA_DIR": str(custom_app_data_dir)}
    ):
        return Settings()


def test_settings_initialization(settings_obj, tmp_config_dir):
    """
    Tests that a Settings object is initialized correctly.
    """
    config_file_name = "script_config.json"
    assert settings_obj.config_path == str(
        os.path.join(tmp_config_dir, ".config", config_file_name)
    )
    assert settings_obj._settings == settings_obj.default_config
    assert os.path.exists(settings_obj.config_path)


def test_settings_load_from_file(settings_obj, tmp_config_dir):
    """
    Tests loading from an existing config file.
    """
    custom_config = {"BASE_DIR": "/custom/base", "BACKUP_KEEP": 5}
    with open(settings_obj.config_path, "w") as f:
        json.dump(custom_config, f)

    # Create a *new* Settings object to force a reload.  No patching here.
    settings2 = Settings()

    expected_config = settings_obj.default_config.copy()
    expected_config.update(custom_config)
    assert settings2._settings == expected_config


def test_settings_get(settings_obj):
    """Tests the get() method."""
    assert settings_obj.get("BASE_DIR") == settings_obj.default_config["BASE_DIR"]
    assert settings_obj.get("NON_EXISTENT_KEY") is None


def test_settings_set(settings_obj, tmp_config_dir):
    """Tests the set() method."""
    settings_obj.set("BACKUP_KEEP", 12)
    assert settings_obj.get("BACKUP_KEEP") == 12

    with open(settings_obj.config_path, "r") as f:
        config_from_file = json.load(f)
    assert config_from_file["BACKUP_KEEP"] == 12

    # New Settings object to check reloading.  No patching here.
    settings2 = Settings()
    assert settings2.get("BACKUP_KEEP") == 12


def test_settings_set_invalid_json(settings_obj, tmp_config_dir):
    """Test set() with invalid JSON in the config file."""
    with open(settings_obj.config_path, "w") as f:
        f.write("{invalid json")
    settings_obj.set("BASE_DIR", "/new/path")
    with open(settings_obj.config_path, "r") as f:
        config = json.load(f)
    assert config["BASE_DIR"] == "/new/path"


def test_settings_set_oserror(settings_obj):
    """Test set() with a write error."""
    with patch("builtins.open", side_effect=OSError("Mock write error")):
        with pytest.raises(ConfigError, match="Failed to write"):
            settings_obj.set("BASE_DIR", "testdir")


def test_default_config_values(settings_obj):
    """Checks default_config property values."""
    defaults = settings_obj.default_config
    assert defaults["BASE_DIR"].endswith("servers")
    assert defaults["BACKUP_KEEP"] == 3


def test_environment_variable_override(tmp_path):
    """Tests BEDROCK_SERVER_MANAGER_DATA_DIR."""
    custom_data_dir = tmp_path / "custom_data"
    with patch.dict(
        os.environ, {"BEDROCK_SERVER_MANAGER_DATA_DIR": str(custom_data_dir)}
    ):
        settings = Settings()
        expected_config_dir = str(
            custom_data_dir / "bedrock-server-manager" / ".config"
        )
        assert settings._config_dir == expected_config_dir
        assert os.path.exists(settings.config_path)


def test_no_environment_variable_override(tmp_path):
    """Tests behavior without the environment variable."""
    expected_app_data_dir = os.path.join(str(tmp_path), "bedrock-server-manager")
    expected_config_dir = os.path.join(expected_app_data_dir, ".config")
    with patch.dict(os.environ, {}, clear=True):
        # Patch _get_app_data_dir to return the *app data* directory
        with patch.object(
            Settings, "_get_app_data_dir", return_value=expected_app_data_dir
        ):
            settings = Settings()  # Create inside the patch

        assert settings._config_dir == expected_config_dir
        assert os.path.exists(settings.config_path)


def test_get_config_dir(settings_obj_custom_env, tmp_path):
    """Verifies _config_dir with a custom environment."""
    custom_app_data_dir = tmp_path / "custom_app_data"
    expected_config_dir = os.path.join(
        custom_app_data_dir, "bedrock-server-manager", ".config"
    )
    assert settings_obj_custom_env._config_dir == expected_config_dir


def test_settings_load_file_not_found(tmp_config_dir, caplog):
    """Tests file-not-found scenario."""
    config_file = os.path.join(
        tmp_config_dir, ".config", "script_config.json"
    )  # Correct path
    if os.path.exists(config_file):
        os.remove(config_file)
    with caplog.at_level(logging.INFO):
        settings_obj = Settings()  # No patching needed, already handled
    assert "Configuration file not found" in caplog.text
    assert os.path.exists(config_file)
    assert settings_obj._settings == settings_obj.default_config


def test_settings_invalid_json_file(tmp_config_dir, caplog):
    """Tests handling of invalid JSON."""
    config_file = os.path.join(tmp_config_dir, "script_config.json")
    with open(config_file, "w") as f:
        f.write("This is not valid JSON")
    with caplog.at_level(logging.WARNING):
        settings_obj = Settings()  # No patching needed
    assert "Configuration file is not valid JSON" in caplog.text
    assert settings_obj._settings == settings_obj.default_config


def test_settings_read_error(tmp_config_dir):
    """Tests for read errors."""
    config_file = os.path.join(tmp_config_dir, "script_config.json")
    with patch("builtins.open", side_effect=OSError("Mock read error")):
        with pytest.raises(ConfigError, match="Error reading config file"):
            settings_obj = Settings()  # No patching needed
