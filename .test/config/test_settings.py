import json
import os
import pytest
import importlib
import logging
import sys
from unittest.mock import patch, mock_open
from bedrock_server_manager.config import settings
from bedrock_server_manager.core.error import ConfigError
from bedrock_server_manager.config.settings import (
    load_settings,
    _write_default_config,
    DEFAULT_CONFIG,
    CONFIG_PATH,
    CONFIG_DIR,
    APP_DATA_DIR,
)

# --- Helper Functions ---


@pytest.fixture
def config_dir(tmp_path):
    """Creates a temporary config directory for testing."""
    return tmp_path / ".config"


@pytest.fixture
def script_dir(tmp_path):
    """Creates a temporary config directory for testing."""
    return tmp_path / "script_dir"


@pytest.fixture
def config_file(config_dir):
    return config_dir / "script_config.json"


# --- Tests for _write_default_config ---


def test_write_default_config_creates_file(config_file, config_dir):
    """Test that _write_default_config creates the config file."""
    config_dir.mkdir(parents=True, exist_ok=True)  # Create the directory
    with patch("bedrock_server_manager.config.settings.CONFIG_DIR", str(config_dir)):
        with patch(
            "bedrock_server_manager.config.settings.CONFIG_PATH", str(config_file)
        ):
            _write_default_config()
            assert config_file.exists()


def test_write_default_config_writes_correct_content(config_file, config_dir):
    """Test that _write_default_config writes the correct JSON content."""
    config_dir.mkdir(parents=True, exist_ok=True)  # Create the directory
    with patch("bedrock_server_manager.config.settings.CONFIG_DIR", str(config_dir)):
        with patch(
            "bedrock_server_manager.config.settings.CONFIG_PATH", str(config_file)
        ):
            _write_default_config()
            with open(config_file, "r") as f:
                written_config = json.load(f)
            assert written_config == DEFAULT_CONFIG


def test_write_default_config_raises_error_on_write_failure(config_dir):
    """Test that _write_default_config raises ConfigError on write failure."""
    with patch("bedrock_server_manager.config.settings.CONFIG_DIR", str(config_dir)):
        with patch("builtins.open", side_effect=OSError("Mocked write error")):
            with pytest.raises(ConfigError, match="Failed to write default config"):
                _write_default_config()


# --- Tests for load_settings ---


def test_load_settings_returns_default_config_if_file_not_found(
    config_dir, config_file, script_dir
):
    """Test that load_settings returns default config if file not found."""
    config_dir.mkdir(parents=True, exist_ok=True)
    with patch("bedrock_server_manager.config.settings.CONFIG_DIR", str(config_dir)):
        with patch(
            "bedrock_server_manager.config.settings.APP_DATA_DIR", str(script_dir)
        ):
            with patch(
                "bedrock_server_manager.config.settings.CONFIG_PATH", str(config_file)
            ):
                config = load_settings()
                assert config == DEFAULT_CONFIG
                assert config_file.exists()


def test_load_settings_overrides_defaults_with_user_config(
    config_file, script_dir, config_dir
):
    """Test that load_settings overrides defaults with user-provided config."""
    user_config = {"BASE_DIR": "/custom/base/dir", "BACKUP_KEEP": 10}
    config_dir.mkdir(parents=True, exist_ok=True)
    with patch("bedrock_server_manager.config.settings.CONFIG_DIR", str(config_dir)):
        with patch(
            "bedrock_server_manager.config.settings.APP_DATA_DIR", str(script_dir)
        ):
            with patch(
                "bedrock_server_manager.config.settings.CONFIG_PATH", str(config_file)
            ):
                with open(config_file, "w") as f:
                    json.dump(user_config, f)

                config = load_settings()
                expected_config = DEFAULT_CONFIG.copy()
                expected_config.update(user_config)
                assert config == expected_config


def test_load_settings_handles_invalid_json(config_file, script_dir, config_dir):
    """Test load_settings handles invalid JSON in the config file."""
    config_dir.mkdir(parents=True, exist_ok=True)
    with patch("bedrock_server_manager.config.settings.CONFIG_DIR", str(config_dir)):
        with patch(
            "bedrock_server_manager.config.settings.APP_DATA_DIR", str(script_dir)
        ):
            with patch(
                "bedrock_server_manager.config.settings.CONFIG_PATH", str(config_file)
            ):
                with open(config_file, "w") as f:
                    f.write("This is not valid JSON")  # Write invalid JSON

                config = load_settings()
                assert config == DEFAULT_CONFIG  # Should fall back to defaults
                assert config_file.exists()


def test_load_settings_raises_error_on_read_failure(config_dir, config_file):
    """Test that load_settings raises ConfigError on a file read error."""
    with patch("bedrock_server_manager.config.settings.CONFIG_DIR", str(config_dir)):
        with patch(
            "bedrock_server_manager.config.settings.CONFIG_PATH", str(config_file)
        ):
            with patch("builtins.open", side_effect=OSError("Mocked read error")):
                with pytest.raises(ConfigError, match="Error reading config file"):
                    load_settings()


def test_load_settings_creates_config_directory(config_dir, script_dir):
    """Ensures config directory is created if it doesn't exist"""
    with patch("bedrock_server_manager.config.settings.CONFIG_DIR", str(config_dir)):
        with patch(
            "bedrock_server_manager.config.settings.APP_DATA_DIR", str(script_dir)
        ):
            load_settings()
            assert config_dir.exists()


def test_config_constants_are_loaded_correctly(config_dir, script_dir, config_file):
    # Custom configuration values you want to override
    user_config = {
        "BASE_DIR": "/custom/base",
        "BACKUP_KEEP": 5,
        "DOWNLOAD_KEEP": 2,
        "CONTENT_DIR": "test_content",
        "DOWNLOAD_DIR": "test_downloads",
        "BACKUP_DIR": "test_backups",
        "LOG_DIR": "test_logs",
        "LOG_LEVEL": "DEBUG",
    }
    config_dir.mkdir(parents=True, exist_ok=True)
    with patch("bedrock_server_manager.config.settings.CONFIG_DIR", str(config_dir)):
        with patch(
            "bedrock_server_manager.config.settings.APP_DATA_DIR", str(script_dir)
        ):
            with patch(
                "bedrock_server_manager.config.settings.CONFIG_PATH", str(config_file)
            ):
                with patch(
                    "builtins.open", mock_open(read_data=json.dumps(user_config))
                ):
                    # Reload settings *AFTER* patching open, *BEFORE* calling load_settings
                    importlib.reload(settings)  # Reload is crucial here
                    loaded_config = load_settings()  # Call load_settings after reload

    # The expected configuration should be the defaults overridden by the user config.
    expected_config = {**settings.DEFAULT_CONFIG, **user_config}

    # Assert that the loaded configuration matches our expectation.
    assert loaded_config == expected_config

    # Check if module-level constants reflect the loaded settings.
    assert settings.BASE_DIR == expected_config["BASE_DIR"]
    assert settings.BACKUP_KEEP == expected_config["BACKUP_KEEP"]
    assert settings.DOWNLOAD_KEEP == expected_config["DOWNLOAD_KEEP"]
    assert settings.CONTENT_DIR == expected_config["CONTENT_DIR"]
    assert settings.DOWNLOAD_DIR == expected_config["DOWNLOAD_DIR"]
    assert settings.BACKUP_DIR == expected_config["BACKUP_DIR"]
    assert settings.LOG_DIR == expected_config["LOG_DIR"]
    assert settings.LOG_LEVEL == expected_config["LOG_LEVEL"]


# --- Tests for appdir ---


def test_app_data_and_config_dirs(tmp_path):
    """Test APP_DATA_DIR and APP_CONFIG_DIR with environment variable patching."""
    # Patch os.path.expanduser so that it returns tmp_path, isolating file system effects.
    with patch("os.path.expanduser", return_value=str(tmp_path)):
        # --- Test 1: No environment variable (defaults now to a tmp folder) ---
        expected_app_data_dir = os.path.join(str(tmp_path), "bedrock-server-manager")
        expected_app_config_dir = os.path.join(expected_app_data_dir, ".config")

        with patch.dict(os.environ, {}, clear=True):  # Clear all environment variables
            with patch(
                "bedrock_server_manager.config.settings.APP_DATA_DIR",
                expected_app_data_dir,
            ):
                with patch(
                    "bedrock_server_manager.config.settings.CONFIG_DIR",
                    expected_app_config_dir,
                ):
                    importlib.reload(settings)
                    assert settings.APP_DATA_DIR == expected_app_data_dir
                    assert settings.APP_CONFIG_DIR == expected_app_config_dir

        # --- Test 2: With environment variable ---
        custom_data_dir = str(tmp_path / "custom_data")
        expected_app_data_dir = os.path.join(custom_data_dir, "bedrock-server-manager")
        expected_app_config_dir = os.path.join(expected_app_data_dir, ".config")

        with patch.dict(
            os.environ, {"BEDROCK_SERVER_MANAGER_DATA_DIR": custom_data_dir}
        ):
            with patch(
                "bedrock_server_manager.config.settings.APP_DATA_DIR",
                expected_app_data_dir,
            ):
                with patch(
                    "bedrock_server_manager.config.settings.CONFIG_DIR",
                    expected_app_config_dir,
                ):
                    importlib.reload(settings)
                    assert settings.APP_DATA_DIR == expected_app_data_dir
                    assert settings.APP_CONFIG_DIR == expected_app_config_dir
