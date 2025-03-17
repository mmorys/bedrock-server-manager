import os
import time
import shutil
import pytest
from unittest.mock import patch, MagicMock
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.core.server import server, world
from bedrock_server_manager.utils import general
from bedrock_server_manager.core.server.backup import (
    prune_old_backups,
    backup_world,
    backup_config_file,
    backup_server,
    backup_all,
    restore_config_file,
    restore_server,
    restore_all,
)
from bedrock_server_manager.core.error import (
    MissingArgumentError,
    FileOperationError,
    DirectoryError,
    InvalidInputError,
    BackupWorldError,
    RestoreError,
)

# --- Fixtures ---


@pytest.fixture
def tmp_app_data_dir(tmp_path):
    """Creates a temporary application data directory and patches Settings."""
    app_data_dir = tmp_path / "bedrock-server-manager"
    app_data_dir.mkdir()
    with patch.object(Settings, "_get_app_data_dir", return_value=str(app_data_dir)):
        yield app_data_dir


@pytest.fixture
def settings_obj(tmp_app_data_dir):
    """Provides a Settings object using the temporary directory."""
    return Settings()


# --- Tests for prune_old_backups ---


def test_prune_old_backups_deletes_old_files(tmp_app_data_dir):
    """Test deleting old backups, keeping the specified number."""
    backup_dir = os.path.join(tmp_app_data_dir, "backups")
    os.makedirs(backup_dir)
    backup_keep = 2
    file_prefix = "backup_"
    file_extension = "txt"

    # Create some dummy files with different timestamps
    for i in range(4):
        file_path = os.path.join(backup_dir, f"{file_prefix}{i}.{file_extension}")
        with open(file_path, "w") as f:  # Correctly create files
            f.write("dummy content")
        time.sleep(0.1)  # Ensure different modification times

    prune_old_backups(backup_dir, backup_keep, file_prefix, file_extension)

    remaining_files = sorted(
        [
            f
            for f in os.listdir(backup_dir)
            if os.path.isfile(os.path.join(backup_dir, f))
        ]
    )
    assert remaining_files == ["backup_2.txt", "backup_3.txt"]  # Newest 2


def test_prune_old_backups_keeps_all_files(tmp_app_data_dir):
    """Test when the number of files is less than backup_keep."""
    backup_dir = os.path.join(tmp_app_data_dir, "backups")
    os.makedirs(backup_dir)
    backup_keep = 5
    file_prefix = "backup_"
    file_extension = "txt"

    for i in range(3):
        file_path = os.path.join(backup_dir, f"{file_prefix}{i}.{file_extension}")
        with open(file_path, "w") as f:  # Correctly create files
            f.write("dummy content")

    prune_old_backups(backup_dir, backup_keep, file_prefix, file_extension)

    remaining_files = sorted(
        [
            f
            for f in os.listdir(backup_dir)
            if os.path.isfile(os.path.join(backup_dir, f))
        ]
    )
    assert remaining_files == ["backup_0.txt", "backup_1.txt", "backup_2.txt"]  # All


def test_prune_old_backups_empty_directory(tmp_app_data_dir):
    """Test with an empty backup directory."""
    backup_dir = os.path.join(tmp_app_data_dir, "backups")
    os.makedirs(backup_dir)
    backup_keep = 3
    file_prefix = "backup_"
    file_extension = "txt"

    prune_old_backups(backup_dir, backup_keep, file_prefix, file_extension)
    assert len(os.listdir(backup_dir)) == 0  # Directory should still be empty


def test_prune_old_backups_missing_directory(tmp_app_data_dir):
    """Test with a backup directory that doesn't exist."""
    backup_dir = os.path.join(tmp_app_data_dir, "nonexistent_dir")  # Doesn't exist
    backup_keep = 3
    file_prefix = "backup_"
    file_extension = "txt"

    # Should not raise an exception; should return
    prune_old_backups(backup_dir, backup_keep, file_prefix, file_extension)


def test_prune_old_backups_missing_backup_dir():
    """Test with an empty backup_dir argument."""
    with pytest.raises(MissingArgumentError, match="backup_dir is empty"):
        prune_old_backups("", 3, "prefix_", "txt")


def test_prune_old_backups_invalid_backup_keep(tmp_app_data_dir):
    """Test passing an invalid value for backup_keep (ValueError)."""
    backup_dir = os.path.join(tmp_app_data_dir, "backups")
    os.makedirs(backup_dir)
    backup_keep = "invalid"  # Not an integer
    file_prefix = "backup_"
    file_extension = "txt"
    with pytest.raises(ValueError, match="backup_keep must be a valid integer"):
        prune_old_backups(backup_dir, backup_keep, file_prefix, file_extension)


@patch("os.remove", side_effect=OSError("Mocked remove error"))
def test_prune_old_backups_deletion_error(mock_remove, tmp_app_data_dir):
    """Test handling an error during file deletion."""
    backup_dir = os.path.join(tmp_app_data_dir, "backups")
    os.makedirs(backup_dir)
    backup_keep = 1
    file_prefix = "backup_"
    file_extension = "txt"
    # Create some dummy files
    for i in range(3):
        file_path = os.path.join(backup_dir, f"{file_prefix}{i}.{file_extension}")
        with open(file_path, "w") as f:  # Correctly create files
            f.write("dummy content")

    with pytest.raises(FileOperationError, match="Failed to remove"):
        prune_old_backups(backup_dir, backup_keep, file_prefix, file_extension)


def test_prune_old_backups_no_prefix_no_extension(tmp_app_data_dir):
    """Test with no prefix and no extension."""
    backup_dir = os.path.join(tmp_app_data_dir, "backups")
    os.makedirs(backup_dir)
    backup_keep = 1
    with pytest.raises(
        InvalidInputError, match="Must have either file prefix or file extension"
    ):
        prune_old_backups(backup_dir, backup_keep)


def test_prune_old_backups_only_prefix(tmp_app_data_dir):
    """Test with only a prefix"""
    backup_dir = os.path.join(tmp_app_data_dir, "backups")
    os.makedirs(backup_dir)
    backup_keep = 1
    file_prefix = "backup_"
    file_extension = "txt"

    # Create some dummy files with different timestamps
    for i in range(4):
        file_path = os.path.join(backup_dir, f"{file_prefix}{i}.{file_extension}")
        with open(file_path, "w") as f:  # Correctly create files
            f.write("dummy content")
        time.sleep(0.1)  # Ensure different modification times

    prune_old_backups(backup_dir, backup_keep, file_prefix=file_prefix)
    remaining_files = sorted(
        [
            f
            for f in os.listdir(backup_dir)
            if os.path.isfile(os.path.join(backup_dir, f))
        ]
    )
    assert remaining_files == ["backup_3.txt"]


def test_prune_old_backups_only_extension(tmp_app_data_dir):
    """Test with only a extension"""
    backup_dir = os.path.join(tmp_app_data_dir, "backups")
    os.makedirs(backup_dir)
    backup_keep = 1
    file_prefix = "backup_"
    file_extension = "txt"

    # Create some dummy files with different timestamps
    for i in range(4):
        file_path = os.path.join(backup_dir, f"{file_prefix}{i}.{file_extension}")
        with open(file_path, "w") as f:  # Correctly create files
            f.write("dummy content")
        time.sleep(0.1)  # Ensure different modification times

    prune_old_backups(backup_dir, backup_keep, file_extension=file_extension)
    remaining_files = sorted(
        [
            f
            for f in os.listdir(backup_dir)
            if os.path.isfile(os.path.join(backup_dir, f))
        ]
    )
    assert remaining_files == ["backup_3.txt"]


# --- Tests for backup_world ---


@patch("bedrock_server_manager.core.server.world.export_world")
@patch("bedrock_server_manager.utils.general.get_timestamp", return_value="12345")
def test_backup_world_successful(
    mock_get_timestamp, mock_export_world, tmp_app_data_dir, settings_obj
):
    """Test successful world backup."""
    server_name = "test_server"
    world_path = os.path.join(
        tmp_app_data_dir, "servers", server_name, "worlds", "test_world"
    )
    os.makedirs(world_path)
    backup_dir = settings_obj.get("BACKUP_DIR")
    backup_world(server_name, world_path, backup_dir)

    expected_backup_file = os.path.join(
        backup_dir, f"{os.path.basename(world_path)}_backup_12345.mcworld"
    )
    mock_export_world.assert_called_once_with(world_path, expected_backup_file)


def test_backup_world_world_directory_not_found(tmp_app_data_dir):
    """Test with a world_path that doesn't exist."""
    server_name = "test_server"
    world_path = os.path.join(tmp_app_data_dir, "nonexistent_world")
    backup_dir = os.path.join(tmp_app_data_dir, "backups")

    with pytest.raises(DirectoryError, match="World directory '.*' does not exist."):
        backup_world(server_name, world_path, backup_dir)


# --- Tests for backup_config_file ---


@patch("bedrock_server_manager.utils.general.get_timestamp", return_value="67890")
@patch("shutil.copy2")
def test_backup_config_file_successful(
    mock_copy2, mock_get_timestamp, tmp_app_data_dir, settings_obj
):
    """Test successful backup of a configuration file."""
    file_to_backup = os.path.join(tmp_app_data_dir, "test_config.txt")
    with open(file_to_backup, "w") as f:
        f.write("This is a test config file.")
    backup_dir = settings_obj.get("BACKUP_DIR")

    backup_config_file(file_to_backup, backup_dir)

    expected_backup_file = os.path.join(backup_dir, "test_config_backup_67890.txt")
    mock_copy2.assert_called_once_with(file_to_backup, expected_backup_file)


def test_backup_config_file_missing_file_to_backup():
    """Test with a missing file_to_backup argument."""
    with pytest.raises(MissingArgumentError, match="file_to_backup is empty"):
        backup_config_file("", "backup_dir")


def test_backup_config_file_file_not_found(tmp_app_data_dir):
    """Test with a file_to_backup that doesn't exist."""
    file_to_backup = os.path.join(tmp_app_data_dir, "nonexistent.txt")
    backup_dir = os.path.join(tmp_app_data_dir, "backups")

    with pytest.raises(FileOperationError, match="Configuration file '.*' not found!"):
        backup_config_file(file_to_backup, backup_dir)


@patch("shutil.copy2", side_effect=OSError("Mocked copy error"))
def test_backup_config_file_copy_error(mock_copy2, tmp_app_data_dir):
    """Test handling an error during file copying."""
    file_to_backup = os.path.join(tmp_app_data_dir, "test_config.txt")
    with open(file_to_backup, "w") as f:
        f.write("This is a test config file.")
    backup_dir = os.path.join(tmp_app_data_dir, "backups")
    os.makedirs(backup_dir)
    with pytest.raises(FileOperationError, match="Failed to copy"):
        backup_config_file(file_to_backup, backup_dir)


# --- Tests for backup_server ---


@patch("bedrock_server_manager.core.server.backup.backup_world")
@patch("bedrock_server_manager.core.server.server.get_world_name")
def test_backup_server_world_backup(
    mock_get_world_name, mock_backup_world, tmp_app_data_dir, settings_obj
):
    """Test backing up the world."""
    server_name = "test_server"
    backup_type = "world"
    base_dir = settings_obj.get("BASE_DIR")
    os.makedirs(os.path.join(base_dir, server_name))
    world_name = "test_world"

    mock_get_world_name.return_value = world_name
    backup_server(server_name, backup_type, base_dir)
    mock_get_world_name.assert_called_once_with(server_name, base_dir)

    world_path = os.path.join(base_dir, server_name, "worlds", world_name)
    backup_dir = settings_obj.get("BACKUP_DIR")

    mock_backup_world.assert_called_once_with(server_name, world_path, backup_dir)


@patch("bedrock_server_manager.core.server.backup.backup_config_file")
def test_backup_server_config_backup(
    mock_backup_config_file, tmp_app_data_dir, settings_obj
):
    """Test backing up a configuration file."""
    server_name = "test_server"
    backup_type = "config"
    base_dir = settings_obj.get("BASE_DIR")
    file_to_backup = "test_config.txt"
    server_dir = os.path.join(base_dir, server_name)
    os.makedirs(server_dir)
    config_file_path = os.path.join(server_dir, file_to_backup)
    with open(config_file_path, "w") as f:
        f.write("Config file content")

    backup_server(server_name, backup_type, base_dir, file_to_backup)
    mock_backup_config_file.assert_called_once_with(
        config_file_path, settings_obj.get("BACKUP_DIR")
    )


def test_backup_server_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(MissingArgumentError, match="server_name is empty"):
        backup_server("", "world", "base_dir")


def test_backup_server_missing_backup_type():
    """Test with a missing backup_type argument."""
    with pytest.raises(MissingArgumentError, match="backup_type is empty"):
        backup_server("server_name", "", "base_dir")


def test_backup_server_invalid_backup_type(tmp_app_data_dir, settings_obj):
    """Test with an invalid backup_type."""
    server_name = "test_server"
    backup_type = "invalid_type"
    base_dir = settings_obj.get("BASE_DIR")
    with pytest.raises(InvalidInputError, match="Invalid backup type"):
        backup_server(server_name, backup_type, base_dir)


def test_backup_server_config_backup_missing_file(tmp_app_data_dir, settings_obj):
    """Test config backup with a missing file_to_backup."""
    server_name = "test_server"
    backup_type = "config"
    base_dir = settings_obj.get("BASE_DIR")
    with pytest.raises(MissingArgumentError, match="file_to_backup is empty"):
        backup_server(server_name, backup_type, base_dir)


@patch(
    "bedrock_server_manager.core.server.backup.backup_world",
    side_effect=Exception("Mocked backup error"),
)
@patch("bedrock_server_manager.core.server.server.get_world_name")
def test_backup_server_world_backup_error(
    mock_get_world_name, mock_backup_world, tmp_app_data_dir, settings_obj
):
    """Test handling an error during world backup."""
    server_name = "test_server"
    backup_type = "world"
    base_dir = settings_obj.get("BASE_DIR")
    os.makedirs(os.path.join(base_dir, server_name))
    world_name = "test_world"

    mock_get_world_name.return_value = world_name
    with pytest.raises(BackupWorldError, match="World backup failed"):
        backup_server(server_name, backup_type, base_dir)


@patch("bedrock_server_manager.core.server.server.get_world_name", return_value=None)
def test_backup_server_get_world_name_fails(
    mock_get_world_name, tmp_app_data_dir, settings_obj
):
    """Tests the scenario where get_world_name returns none."""
    server_name = "test_server"
    backup_type = "world"
    base_dir = settings_obj.get("BASE_DIR")
    os.makedirs(os.path.join(base_dir, server_name))
    with pytest.raises(BackupWorldError, match="Could not determine world name"):
        backup_server(server_name, backup_type, base_dir)


# --- Tests for backup_all ---


@patch("bedrock_server_manager.core.server.backup.backup_server")
def test_backup_all_successful(mock_backup_server, tmp_app_data_dir, settings_obj):
    """Test successful backup of all files (world and config)."""
    server_name = "test_server"
    base_dir = settings_obj.get("BASE_DIR")
    server_dir = os.path.join(base_dir, server_name)
    os.makedirs(server_dir)
    # Create dummy config files
    for filename in ["allowlist.json", "permissions.json", "server.properties"]:
        with open(os.path.join(server_dir, filename), "w") as f:
            f.write(f"Dummy content for {filename}")
    # set up the mock calls
    mock_backup_server.side_effect = [None, None, None, None]

    backup_all(server_name, base_dir)
    assert mock_backup_server.call_count == 4
    # Check specific calls with call_args_list (order matters)
    expected_calls = [
        ((server_name, "world", base_dir, ""), {}),  # World backup
        (
            (server_name, "config", base_dir),
            {"file_to_backup": "allowlist.json"},
        ),  # Config backups
        (
            (server_name, "config", base_dir),
            {"file_to_backup": "permissions.json"},
        ),
        (
            (server_name, "config", base_dir),
            {"file_to_backup": "server.properties"},
        ),
    ]
    mock_backup_server.assert_has_calls(expected_calls)


def test_backup_all_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(MissingArgumentError, match="server_name is empty"):
        backup_all("")


@patch(
    "bedrock_server_manager.core.server.backup.backup_server",
    side_effect=Exception("Mocked backup error"),
)
def test_backup_all_backup_error(mock_backup_server, tmp_app_data_dir, settings_obj):
    """Test handling an error during backup."""
    server_name = "test_server"
    base_dir = settings_obj.get("BASE_DIR")
    os.makedirs(os.path.join(base_dir, server_name))
    with pytest.raises(BackupWorldError, match="World backup failed"):
        backup_all(server_name, base_dir)


# --- Tests for restore_config_file ---


@patch("shutil.copy2")
def test_restore_config_file_successful(mock_copy2, tmp_app_data_dir):
    """Test successful restoration of a configuration file."""
    backup_file = os.path.join(tmp_app_data_dir, "config_backup_12345.txt")
    with open(backup_file, "w") as f:
        f.write("Backup content")  # Create a dummy backup file
    server_dir = os.path.join(tmp_app_data_dir, "server")
    os.makedirs(server_dir)
    restore_config_file(backup_file, server_dir)

    expected_target_file = os.path.join(server_dir, "config.txt")
    mock_copy2.assert_called_once_with(backup_file, expected_target_file)


def test_restore_config_file_missing_backup_file():
    """Test with a missing backup_file argument."""
    with pytest.raises(MissingArgumentError, match="backup_file is empty"):
        restore_config_file("", "server_dir")


def test_restore_config_file_missing_server_dir():
    """Test with a missing server_dir argument."""
    with pytest.raises(MissingArgumentError, match="server_dir is empty"):
        restore_config_file("backup.txt", "")


def test_restore_config_file_backup_file_not_found(tmp_app_data_dir):
    """Test with a backup_file that doesn't exist."""
    backup_file = os.path.join(tmp_app_data_dir, "nonexistent.txt")
    server_dir = os.path.join(tmp_app_data_dir, "server")

    with pytest.raises(FileOperationError, match="Backup file '.*' not found!"):
        restore_config_file(backup_file, server_dir)


@patch("shutil.copy2", side_effect=OSError("Mocked copy error"))
def test_restore_config_file_copy_error(mock_copy2, tmp_app_data_dir):
    """Test handling an error during file copying."""
    backup_file = os.path.join(tmp_app_data_dir, "config_backup_12345.txt")
    with open(backup_file, "w") as f:
        f.write("Backup content")
    server_dir = os.path.join(tmp_app_data_dir, "server")
    os.makedirs(server_dir)
    with pytest.raises(
        FileOperationError, match="Failed to restore configuration file"
    ):
        restore_config_file(backup_file, server_dir)


# --- Tests for restore_server ---


@patch("bedrock_server_manager.core.server.world.import_world")
def test_restore_server_world_restore(
    mock_import_world, tmp_app_data_dir, settings_obj
):
    """Test restoring a world backup."""
    server_name = "test_server"
    backup_file = os.path.join(tmp_app_data_dir, "world_backup.mcworld")
    with open(backup_file, "w") as f:
        f.write("Dummy world data")
    restore_type = "world"
    base_dir = settings_obj.get("BASE_DIR")
    os.makedirs(os.path.join(base_dir, server_name))
    restore_server(server_name, backup_file, restore_type, base_dir)
    mock_import_world.assert_called_once_with(server_name, backup_file, base_dir)


@patch("bedrock_server_manager.core.server.backup.restore_config_file")
def test_restore_server_config_restore(
    mock_restore_config_file, tmp_app_data_dir, settings_obj
):
    """Test restoring a configuration file backup."""
    server_name = "test_server"
    backup_file = os.path.join(tmp_app_data_dir, "config_backup.txt")
    with open(backup_file, "w") as f:
        f.write("Dummy config data")
    restore_type = "config"
    base_dir = settings_obj.get("BASE_DIR")
    server_dir = os.path.join(base_dir, server_name)
    os.makedirs(server_dir)  # create server dir

    restore_server(server_name, backup_file, restore_type, base_dir)
    expected_target_file = os.path.join(server_dir, "config.txt")
    mock_restore_config_file.assert_called_once_with(backup_file, server_dir)


def test_restore_server_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(MissingArgumentError, match="server_name is empty"):
        restore_server("", "backup.txt", "world", "base_dir")


def test_restore_server_missing_backup_file():
    """Test with a missing backup_file argument."""
    with pytest.raises(MissingArgumentError, match="backup_file is empty"):
        restore_server("server_name", "", "world", "base_dir")


def test_restore_server_missing_restore_type():
    """Test with a missing restore_type argument."""
    with pytest.raises(MissingArgumentError, match="restore_type is empty"):
        restore_server("server_name", "backup.txt", "", "base_dir")


def test_restore_server_backup_file_not_found(tmp_app_data_dir):
    """Test with a backup_file that doesn't exist."""
    server_name = "test_server"
    backup_file = os.path.join(tmp_app_data_dir, "nonexistent.txt")
    restore_type = "world"
    base_dir = os.path.join(tmp_app_data_dir, "servers")

    with pytest.raises(FileOperationError, match="Backup file '.*' not found!"):
        restore_server(server_name, backup_file, restore_type, base_dir)


def test_restore_server_invalid_restore_type(tmp_app_data_dir):
    """Test with an invalid restore_type."""
    server_name = "test_server"
    backup_file = os.path.join(tmp_app_data_dir, "backup.txt")
    with open(backup_file, "w") as f:
        f.write("Dummy data")
    restore_type = "invalid_type"
    base_dir = os.path.join(tmp_app_data_dir, "servers")
    with pytest.raises(InvalidInputError, match="Invalid restore type"):
        restore_server(server_name, backup_file, restore_type, base_dir)


# --- Tests for restore_all ---


@patch("bedrock_server_manager.core.server.backup.restore_server")
def test_restore_all_successful(mock_restore_server, tmp_app_data_dir, settings_obj):
    """Test successful restoration of all latest backups."""
    server_name = "test_server"
    backup_dir = os.path.join(settings_obj.get("BACKUP_DIR"), server_name)
    os.makedirs(backup_dir)
    # Create some dummy backup files with different timestamps
    with open(os.path.join(backup_dir, "world_backup_1.mcworld"), "w") as f:
        f.write("Dummy data")
    time.sleep(0.1)
    with open(os.path.join(backup_dir, "world_backup_2.mcworld"), "w") as f:
        f.write("Dummy data")  # Latest world
    time.sleep(0.1)
    with open(os.path.join(backup_dir, "server_backup_1.properties"), "w") as f:
        f.write("Dummy data")
    time.sleep(0.1)
    with open(os.path.join(backup_dir, "server_backup_2.properties"), "w") as f:
        f.write("Dummy data")  # Latest properties
    time.sleep(0.1)
    with open(os.path.join(backup_dir, "permissions_backup_1.json"), "w") as f:
        f.write("Dummy data")
    time.sleep(0.1)
    with open(os.path.join(backup_dir, "permissions_backup_2.json"), "w") as f:
        f.write("Dummy data")  # Latest permissions
    time.sleep(0.1)
    with open(os.path.join(backup_dir, "allowlist_backup_1.json"), "w") as f:
        f.write("Dummy data")
    time.sleep(0.1)
    with open(os.path.join(backup_dir, "allowlist_backup_2.json"), "w") as f:
        f.write("Dummy data")  # Latest allowlist
    base_dir = settings_obj.get("BASE_DIR")
    os.makedirs(os.path.join(base_dir, server_name))

    restore_all(server_name, base_dir)

    # Check that restore_server was called with the correct arguments
    expected_calls = [
        (
            (
                server_name,
                os.path.join(backup_dir, "world_backup_2.mcworld"),
                "world",
                base_dir,
            ),
            {},
        ),
        (
            (
                server_name,
                os.path.join(backup_dir, "server_backup_2.properties"),
                "config",
                base_dir,
            ),
            {},
        ),
        (
            (
                server_name,
                os.path.join(backup_dir, "allowlist_backup_2.json"),
                "config",
                base_dir,
            ),
            {},
        ),
        (
            (
                server_name,
                os.path.join(backup_dir, "permissions_backup_2.json"),
                "config",
                base_dir,
            ),
            {},
        ),
    ]
    mock_restore_server.assert_has_calls(expected_calls, any_order=True)


def test_restore_all_missing_server_name(tmp_app_data_dir):
    """Test with a missing server_name argument."""
    with pytest.raises(MissingArgumentError, match="server_name is empty"):
        restore_all("", str(tmp_app_data_dir))


def test_restore_all_no_backups_found(tmp_app_data_dir, settings_obj):
    """Test when no backups are found for the server."""
    server_name = "test_server"
    base_dir = settings_obj.get("BASE_DIR")
    os.makedirs(os.path.join(base_dir, server_name))
    # Should not raise an exception, just log a message
    restore_all(server_name, base_dir)

@patch(
    "bedrock_server_manager.core.server.backup.restore_server",
    side_effect=Exception("Mocked restore error"),
)
def test_restore_all_restore_error(mock_restore_server, tmp_app_data_dir, settings_obj):
    """Test handling an error during restoration."""
    server_name = "test_server"
    backup_dir = os.path.join(settings_obj.get("BACKUP_DIR"), server_name)
    os.makedirs(backup_dir)
    with open(os.path.join(backup_dir, "world_backup_1.mcworld"), "w") as f:
        f.write("Dummy file") # Create a dummy backup file
    base_dir = settings_obj.get("BASE_DIR")
    os.makedirs(os.path.join(base_dir, server_name))

    with pytest.raises(RestoreError, match="Failed to restore world"):
        restore_all(server_name, base_dir)
