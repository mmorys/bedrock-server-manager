# bedrock-server-manager/tests/config/test_settings_get_set.py
import pytest
import os
import json
from unittest.mock import patch
from bedrock_server_manager.config.settings import Settings, ConfigError

# --- Fixtures ---

@pytest.fixture
def tmp_config_dir(tmp_path):
    """
    Provides a temporary application data directory and patches _get_app_data_dir.
    This is the same fixture as in your other test file.
    """
    app_data_dir = tmp_path / "bedrock-server-manager"
    config_dir = app_data_dir / ".config"
    config_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(Settings, '_get_app_data_dir', return_value=str(app_data_dir)):
        yield app_data_dir

@pytest.fixture
def settings_obj(tmp_config_dir):
    """Provides a fresh Settings object."""
    return Settings()

# --- Tests for get ---

def test_get_existing_key(settings_obj):
    """Test getting an existing key."""
    settings_obj._settings = {"key1": "value1", "key2": 123} # Directly set for testing
    assert settings_obj.get("key1") == "value1"
    assert settings_obj.get("key2") == 123

def test_get_nonexistent_key(settings_obj):
    """Test getting a key that doesn't exist (should return None)."""
    settings_obj._settings = {"key1": "value1"}  # Set some initial data
    assert settings_obj.get("nonexistent_key") is None

# --- Tests for set ---

def test_set_new_key(settings_obj, tmp_config_dir):
    """Test setting a new key/value pair."""
    settings_obj.set("new_key", "new_value")
    assert settings_obj.get("new_key") == "new_value"

    # Verify file contents
    with open(settings_obj.config_path, "r") as f:
        file_contents = json.load(f)
    assert file_contents["new_key"] == "new_value"

def test_set_existing_key(settings_obj, tmp_config_dir):
    """Test setting (overwriting) an existing key."""
    settings_obj._settings = {"key1": "old_value"}  # Set initial value
    settings_obj.set("key1", "new_value")
    assert settings_obj.get("key1") == "new_value"

    # Verify file contents
    with open(settings_obj.config_path, "r") as f:
        file_contents = json.load(f)
    assert file_contents["key1"] == "new_value"

def test_set_write_error(settings_obj, tmp_config_dir):
    """Test handling a file write error during set."""
    with patch("builtins.open", side_effect=OSError("Mocked write error")):
        with pytest.raises(ConfigError, match="Failed to write to config file"):
            settings_obj.set("key", "value")