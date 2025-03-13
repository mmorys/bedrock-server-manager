# bedrock-server-manager/tests/utils/test_general.py

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import patch, MagicMock, call
from colorama import Fore, Style
from bedrock_server_manager.utils import general
from bedrock_server_manager.config import settings

# --- Fixtures ---


@pytest.fixture
def mock_settings(tmp_path):
    """Fixture to provide a mocked settings object."""
    mock_settings = MagicMock()
    mock_settings.BASE_DIR = str(tmp_path / "servers")
    mock_settings.CONTENT_DIR = str(tmp_path / "content")
    # Add other settings attributes as needed, setting defaults
    with patch("bedrock_server_manager.utils.general.settings", mock_settings):
        yield mock_settings


# --- Tests for startup_checks ---


def test_startup_checks_python_version_ok(mock_settings):
    """Test startup_checks with a valid Python version."""
    with patch("sys.version_info", (3, 10, 0)):
        general.startup_checks()  # Should not raise an exception


def test_startup_checks_python_version_too_low(mock_settings):
    """Test startup_checks with a Python version that's too low."""
    with patch("sys.version_info", (3, 9, 0)):
        with pytest.raises(SystemExit) as e:
            general.startup_checks()


def test_startup_checks_creates_directories(mock_settings):
    """Test startup_checks creates necessary directories."""
    general.startup_checks()
    assert os.path.exists(mock_settings.BASE_DIR)
    assert os.path.exists(mock_settings.CONTENT_DIR)
    assert os.path.exists(os.path.join(mock_settings.CONTENT_DIR, "worlds"))
    assert os.path.exists(os.path.join(mock_settings.CONTENT_DIR, "addons"))


# --- Tests for get_timestamp ---


def test_get_timestamp_format():
    """Test the format of the timestamp returned by get_timestamp."""
    timestamp = general.get_timestamp()
    try:
        datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
    except ValueError:
        pytest.fail("get_timestamp returned an invalid timestamp format.")


# --- Tests for select_option ---


@patch("builtins.input", return_value="")  # Simulate pressing Enter
def test_select_option_default(mock_input):
    """Test select_option when the user chooses the default option."""
    result = general.select_option("Test Prompt", "Default", "Option 1", "Option 2")
    assert result == "Default"
    mock_input.assert_called_once()  # Check that input was called


@patch("builtins.input", return_value="1")
def test_select_option_valid_choice(mock_input):
    """Test select_option with a valid numerical choice."""
    result = general.select_option("Test Prompt", "Default", "Option 1", "Option 2")
    assert result == "Option 1"
    mock_input.assert_called_once()


@patch("builtins.input", side_effect=["invalid", "2"])
def test_select_option_invalid_then_valid(mock_input):
    """Test select_option with an initial invalid input, followed by a valid one."""
    result = general.select_option("Test Prompt", "Default", "Option 1", "Option 2")
    assert result == "Option 2"
    assert mock_input.call_count == 2


@patch("builtins.input", side_effect=["5", "1"])
def test_select_option_out_of_range_then_valid(mock_input):
    """Test an out-of-range choice followed by a valid selection."""
    result = general.select_option("Choose", "Default", "Opt1", "Opt2")
    assert result == "Opt1"
    assert mock_input.call_count == 2


@patch("builtins.print")
@patch("builtins.input", side_effect=["1"])  # Select the first option.
def test_select_option_output(mock_input, mock_print):
    """Verify the printed output of select_option."""
    general.select_option("Test Prompt", "Default", "Option 1", "Option 2")

    expected_calls = [
        call(f"{Fore.MAGENTA}Test Prompt{Style.RESET_ALL}"),
        call("1. Option 1"),
        call("2. Option 2"),
    ]
    mock_print.assert_has_calls(
        expected_calls, any_order=False
    )  # Important: Check order


@patch("builtins.print")
@patch("builtins.input", return_value="")  # Select the default option.
def test_select_option_output_default(mock_input, mock_print):
    general.select_option("Test Prompt", "Default", "Option 1", "Option 2")
    expected_calls = [call(f"Using default: {Fore.YELLOW}Default{Style.RESET_ALL}")]
    mock_print.assert_has_calls(expected_calls)


@patch("builtins.print")
@patch("builtins.input", side_effect=["invalid", "1"])  # Select the first option.
def test_select_option_output_value_error(mock_input, mock_print):
    general.select_option("Test Prompt", "Default", "Option 1", "Option 2")
    expected_calls = [
        call(f"{general._ERROR_PREFIX}Invalid input. Please enter a number.")
    ]
    mock_print.assert_has_calls(expected_calls)


@patch("builtins.print")
@patch("builtins.input", side_effect=["4", "1"])  # Select the first option.
def test_select_option_output_index_error(mock_input, mock_print):
    general.select_option("Test Prompt", "Default", "Option 1", "Option 2")
    expected_calls = [
        call(f"{general._ERROR_PREFIX}Invalid selection. Please try again.")
    ]
    mock_print.assert_has_calls(expected_calls)


# --- Tests for get_base_dir ---


def test_get_base_dir_with_argument(mock_settings):
    """Test get_base_dir when a base_dir argument is provided."""
    custom_dir = "/custom/path"
    result = general.get_base_dir(custom_dir)
    assert result == custom_dir


def test_get_base_dir_without_argument(mock_settings):
    """Test get_base_dir when no argument is provided (uses settings)."""
    result = general.get_base_dir()
    assert result == mock_settings.BASE_DIR


def test_get_base_dir_with_none_argument(mock_settings):
    """Test get_base_dir with explicit None argument."""
    result = general.get_base_dir(None)
    assert result == mock_settings.BASE_DIR
