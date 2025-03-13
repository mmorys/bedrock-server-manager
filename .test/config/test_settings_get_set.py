# bedrock-server-manager/tests/config/test_settings_get_set.py
import pytest
import os
import json
from unittest.mock import patch, mock_open
from bedrock_server_manager.config.settings import (
    get,
    set,
    load_settings,
    DEFAULT_CONFIG,
    CONFIG_PATH,
)
from bedrock_server_manager.core.error import ConfigError

# --- Fixtures ---


@pytest.fixture
def mock_config_dir(tmp_path):
    config_dir = tmp_path / ".config"
    config_dir.mkdir()
    return str(config_dir)


@pytest.fixture
def mock_config_file(mock_config_dir):
    config_file = os.path.join(mock_config_dir, "script_config.json")
    return str(config_file)


@pytest.fixture
def mock_script_dir(tmp_path):
    """Creates a temporary config directory for testing."""
    script_dir = tmp_path / "script_dir"
    script_dir.mkdir()
    with patch("bedrock_server_manager.config.settings.APP_DATA_DIR", str(script_dir)):
        yield script_dir


# --- Tests for get ---


@patch("bedrock_server_manager.config.settings._settings")
def test_get_existing_key(
    mock_settings, mock_config_file, mock_config_dir, mock_script_dir
):
    """Test getting an existing key."""
    initial_config = {"key1": "value1", "key2": 123}
    mock_settings.get.side_effect = initial_config.get
    with patch("bedrock_server_manager.config.settings.CONFIG_PATH", mock_config_file):
        assert get("key1") == "value1"
        assert get("key2") == 123


def test_get_nonexistent_key(mock_config_file, mock_config_dir, mock_script_dir):
    """Test getting a key that doesn't exist (should return None)."""
    initial_config = {"key1": "value1"}
    # Ensure config file exists
    with patch("bedrock_server_manager.config.settings.CONFIG_PATH", mock_config_file):
        with open(mock_config_file, "w") as f:
            json.dump(initial_config, f)

        load_settings()

        assert get("nonexistent_key") is None


# --- Tests for set ---


def test_set_new_key(mock_config_file, mock_config_dir, mock_script_dir):
    """Test setting a new key/value pair."""
    with patch("bedrock_server_manager.config.settings.CONFIG_PATH", mock_config_file):
        with open(mock_config_file, "w") as f:
            json.dump({}, f)
        load_settings()
        set("new_key", "new_value")
        updated_config = load_settings()  # Reload to get changes
        assert updated_config["new_key"] == "new_value"
        # Also check that the file was written correctly:
        with open(mock_config_file, "r") as f:
            file_contents = json.load(f)
        assert file_contents["new_key"] == "new_value"


def test_set_existing_key(mock_config_file, mock_config_dir, mock_script_dir):
    """Test setting (overwriting) an existing key."""
    initial_config = {"key1": "old_value"}
    with patch("bedrock_server_manager.config.settings.CONFIG_PATH", mock_config_file):
        with open(mock_config_file, "w") as f:
            json.dump(initial_config, f)
        load_settings()
        set("key1", "new_value")
        updated_config = load_settings()
        assert updated_config["key1"] == "new_value"

        # Verify file contents
        with open(mock_config_file, "r") as f:
            file_contents = json.load(f)
            assert file_contents["key1"] == "new_value"


def test_set_write_error(mock_config_file, mock_config_dir, mock_script_dir):
    """Test handling a file write error during set."""
    with patch("bedrock_server_manager.config.settings.CONFIG_PATH", mock_config_file):
        with patch("builtins.open", side_effect=OSError("Mocked write error")):
            with pytest.raises(
                ConfigError, match="Error reading config file: Mocked write error"
            ):
                set("key", "value")
