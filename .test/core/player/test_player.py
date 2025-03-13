# bedrock-server-manager/tests/core/player/test_player.py
import pytest
import os
import json
from unittest.mock import patch, mock_open, MagicMock
from bedrock_server_manager.core.error import FileOperationError, InvalidInputError
from bedrock_server_manager.core.player.player import (
    scan_log_for_players,
    save_players_to_json,
)

# --- Fixtures ---


@pytest.fixture
def mock_config_dir(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yield str(config_dir)


# --- Tests for scan_log_for_players ---


def test_scan_log_for_players_finds_players():
    """Test finding players in a log file."""
    log_content = """
    Some random log line...
    Player connected:  SomePlayer, xuid: 1234567890
    Another random line...
    Player connected: AnotherPlayer, xuid: 9876543210
    """
    expected_players = [
        {"name": "SomePlayer", "xuid": "1234567890"},
        {"name": "AnotherPlayer", "xuid": "9876543210"},
    ]
    with patch("builtins.open", mock_open(read_data=log_content)):
        players = scan_log_for_players("dummy_log_file.txt")
        assert players == expected_players


def test_scan_log_for_players_no_players_found():
    """Test when no players are found in the log."""
    log_content = """
    Some random log line...
    No player connections here...
    """
    with patch("builtins.open", mock_open(read_data=log_content)):
        players = scan_log_for_players("dummy_log_file.txt")
        assert players == []


def test_scan_log_for_players_empty_log_file():
    """Test with an empty log file."""
    with patch("builtins.open", mock_open(read_data="")):
        players = scan_log_for_players("dummy_log_file.txt")
        assert players == []


def test_scan_log_for_players_file_read_error():
    """Test handling of file read errors."""
    with patch("builtins.open", side_effect=OSError("Mocked read error")):
        players = scan_log_for_players("dummy_log_file.txt")
        assert players == []  # Should return an empty list


def test_scan_log_for_players_invalid_log_format():
    """Test log lines with slightly invalid formats."""
    log_content = """
    Player connected:  MissingXuid, xuid:
    Player connected: OnlyName,
    xuid: OnlyXuid
    Player connected:  BadFormat, xuid:12345, extra
    """
    with patch("builtins.open", mock_open(read_data=log_content)):
        players = scan_log_for_players("dummy_log_file.txt")
        assert players == []  # all invalid so no extractions


# --- Tests for save_players_to_json ---


def test_save_players_to_json_creates_new_file(mock_config_dir):
    """Test creating a new players.json file."""
    players_data = [
        {"name": "TestPlayer1", "xuid": "1111"},
        {"name": "TestPlayer2", "xuid": "2222"},
    ]
    save_players_to_json(players_data, mock_config_dir)
    players_file = os.path.join(mock_config_dir, "players.json")
    assert os.path.exists(players_file)

    with open(players_file, "r") as f:
        data = json.load(f)
        assert data == {"players": players_data}


def test_save_players_to_json_updates_existing_file(mock_config_dir):
    """Test updating an existing players.json file."""
    # Create an initial players.json
    initial_data = {"players": [{"name": "OldPlayer", "xuid": "1234"}]}
    players_file = os.path.join(mock_config_dir, "players.json")
    with open(players_file, "w") as f:
        json.dump(initial_data, f)

    # New data to be merged
    new_data = [
        {"name": "NewPlayer", "xuid": "5678"},
        {"name": "UpdatedOldPlayer", "xuid": "1234"},  # Update existing
    ]
    save_players_to_json(new_data, mock_config_dir)

    with open(players_file, "r") as f:
        data = json.load(f)
        expected_data = {
            "players": [
                {"name": "UpdatedOldPlayer", "xuid": "1234"},
                {"name": "NewPlayer", "xuid": "5678"},
            ]
        }
        assert data == expected_data


def test_save_players_to_json_empty_player_data(mock_config_dir):
    """Test saving with empty player data (should create/keep empty file)."""
    save_players_to_json([], mock_config_dir)
    players_file = os.path.join(mock_config_dir, "players.json")
    assert os.path.exists(players_file)

    with open(players_file, "r") as f:
        data = json.load(f)
        assert data == {"players": []}  # Should create an empty players list


def test_save_players_to_json_file_write_error(mock_config_dir):
    """Test handling of file write errors."""
    with patch("builtins.open", side_effect=OSError("Mocked write error")):
        with pytest.raises(FileOperationError, match="Failed to save players to JSON"):
            save_players_to_json([{"name": "Test", "xuid": "123"}], mock_config_dir)


def test_save_players_to_json_invalid_input_data(mock_config_dir):
    """Test with invalid input data."""
    # Test 1: Not a list
    invalid_data = "This is not a list"
    with pytest.raises(
        InvalidInputError, match="players_data must be a list of dictionaries."
    ):
        save_players_to_json(invalid_data, mock_config_dir)

    # Test 2: Missing xuid (should be skipped, no exception, log error)
    invalid_data2 = [{"name": "MissingXuid"}]
    with patch("logging.Logger.error") as mock_error:  # Mock the error method
        save_players_to_json(invalid_data2, mock_config_dir)  # NO pytest.raises here!
        mock_error.assert_called_once()  # Check that logger.error was called
    players_file = os.path.join(mock_config_dir, "players.json")
    with open(players_file, "r") as f:
        data = json.load(f)
    assert data == {"players": []}
    mock_error.reset_mock()  # reset the mock

    # Test 3. Mix of good and bad, with type checking
    mixed_data = [
        {"name": "Valid", "xuid": "123"},
        {"name": "MissingXuid"},  # Missing xuid
        {"name": 123, "xuid": "456"},  # Invalid name type
        {"name": "AlsoValid", "xuid": "789"},
    ]
    with patch("logging.Logger.error") as mock_error:
        save_players_to_json(mixed_data, mock_config_dir)
        assert mock_error.call_count == 2  # Check logger.error calls

    with open(players_file, "r") as f:
        data = json.load(f)
    expected_data = {
        "players": [
            {"name": "Valid", "xuid": "123"},
            {"name": "AlsoValid", "xuid": "789"},
        ]
    }
    assert data == expected_data


def test_save_players_to_json_handles_invalid_existing_json(mock_config_dir):
    """Test handling invalid JSON in the existing file."""
    players_file = os.path.join(mock_config_dir, "players.json")
    with open(players_file, "w") as f:
        f.write("This is not valid JSON")

    new_data = [{"name": "NewPlayer", "xuid": "5678"}]
    save_players_to_json(new_data, mock_config_dir)  # Should overwrite

    with open(players_file, "r") as f:
        data = json.load(f)
        # Should have overwritten the invalid JSON and saved the new data
        assert data == {"players": new_data}


def test_save_players_to_json_existing_file_missing_players_key(mock_config_dir):
    """Test when the existing players.json file is missing the 'players' key."""
    players_file = os.path.join(mock_config_dir, "players.json")
    # Create a JSON file without the 'players' key
    with open(players_file, "w") as f:
        json.dump({"some_other_key": "some_value"}, f)

    new_data = [{"name": "NewPlayer", "xuid": "5678"}]
    save_players_to_json(new_data, mock_config_dir)  # should merge

    with open(players_file, "r") as f:
        data = json.load(f)
        # Should have added the 'players' key and saved the new data
        assert data == {"players": [{"name": "NewPlayer", "xuid": "5678"}]}


def test_save_players_to_json_invalid_input_data(mock_config_dir):
    """Test with invalid input data (not a list of dictionaries)."""
    invalid_data = "This is not a list"
    with pytest.raises(
        InvalidInputError, match="players_data must be a list of dictionaries."
    ):
        save_players_to_json(invalid_data, mock_config_dir)


def test_save_players_to_json_skip_invalid_player_entries(mock_config_dir):
    """Test that invalid entries in players_data are skipped."""
    players_data = [
        {"name": "ValidPlayer", "xuid": "1234"},
        {"name": "MissingXuid"},  # Missing xuid, but still a dict
        {"xuid": "MissingName"},  # Missing name, but still a dict
        {"name": 123, "xuid": "789"},  # Invalid name type, but still a dict
        {"name": "AnotherValid", "xuid": "5678"},
    ]
    with patch("logging.Logger.error") as mock_error:
        save_players_to_json(players_data, mock_config_dir)
        assert mock_error.call_count == 3
    players_file = os.path.join(mock_config_dir, "players.json")
    with open(players_file, "r") as f:
        data = json.load(f)
    expected_data = {
        "players": [
            {"name": "ValidPlayer", "xuid": "1234"},
            {"name": "AnotherValid", "xuid": "5678"},
        ]
    }
    assert data == expected_data
