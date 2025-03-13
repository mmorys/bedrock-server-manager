# bedrock-server-manager/tests/core/server/test_backup.py
import os
import time
import shutil
import pytest
from unittest.mock import patch, MagicMock
from bedrock_server_manager.config import settings
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

# --- Tests for prune_old_backups ---


def test_prune_old_backups_deletes_old_files(tmp_path):
    """Test deleting old backups, keeping the specified number."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_keep = 2
    file_prefix = "backup_"
    file_extension = "txt"

    # Create some dummy files with different timestamps
    for i in range(4):
        file_path = backup_dir / f"{file_prefix}{i}.{file_extension}"
        file_path.touch()
        time.sleep(0.1)  # Ensure different modification times

    prune_old_backups(str(backup_dir), backup_keep, file_prefix, file_extension)

    remaining_files = sorted([f.name for f in backup_dir.iterdir()])
    assert remaining_files == ["backup_2.txt", "backup_3.txt"]  # Newest 2


def test_prune_old_backups_keeps_all_files(tmp_path):
    """Test when the number of files is less than backup_keep."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_keep = 5
    file_prefix = "backup_"
    file_extension = "txt"

    for i in range(3):
        file_path = backup_dir / f"{file_prefix}{i}.{file_extension}"
        file_path.touch()

    prune_old_backups(str(backup_dir), backup_keep, file_prefix, file_extension)

    remaining_files = sorted([f.name for f in backup_dir.iterdir()])
    assert remaining_files == ["backup_0.txt", "backup_1.txt", "backup_2.txt"]  # All


def test_prune_old_backups_empty_directory(tmp_path):
    """Test with an empty backup directory."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_keep = 3
    file_prefix = "backup_"
    file_extension = "txt"

    prune_old_backups(str(backup_dir), backup_keep, file_prefix, file_extension)
    assert len(list(backup_dir.iterdir())) == 0  # Directory should still be empty


def test_prune_old_backups_missing_directory(tmp_path):
    """Test with a backup directory that doesn't exist."""
    backup_dir = tmp_path / "nonexistent_dir"  # Doesn't exist
    backup_keep = 3
    file_prefix = "backup_"
    file_extension = "txt"

    # Should not raise an exception; should return
    prune_old_backups(str(backup_dir), backup_keep, file_prefix, file_extension)


def test_prune_old_backups_missing_backup_dir():
    """Test with an empty backup_dir argument."""
    with pytest.raises(MissingArgumentError, match="backup_dir is empty"):
        prune_old_backups("", 3, "prefix_", "txt")


def test_prune_old_backups_invalid_backup_keep(tmp_path):
    """Test passing an invalid value for backup_keep (ValueError)."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_keep = "invalid"  # Not an integer
    file_prefix = "backup_"
    file_extension = "txt"
    with pytest.raises(ValueError, match="backup_keep must be a valid integer"):
        prune_old_backups(str(backup_dir), backup_keep, file_prefix, file_extension)


@patch("os.remove", side_effect=OSError("Mocked remove error"))
def test_prune_old_backups_deletion_error(mock_remove, tmp_path):
    """Test handling an error during file deletion."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_keep = 1
    file_prefix = "backup_"
    file_extension = "txt"
    # Create some dummy files
    for i in range(3):
        file_path = backup_dir / f"{file_prefix}{i}.{file_extension}"
        file_path.touch()

    with pytest.raises(FileOperationError, match="Failed to remove"):
        prune_old_backups(str(backup_dir), backup_keep, file_prefix, file_extension)


def test_prune_old_backups_no_prefix_no_extension(tmp_path):
    """Test with no prefix and no extension."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_keep = 1
    with pytest.raises(
        InvalidInputError, match="Must have either file prefix or file extension"
    ):
        prune_old_backups(str(backup_dir), backup_keep)


def test_prune_old_backups_only_prefix(tmp_path):
    """Test with only a prefix"""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_keep = 1
    file_prefix = "backup_"
    file_extension = "txt"

    # Create some dummy files with different timestamps
    for i in range(4):
        file_path = backup_dir / f"{file_prefix}{i}.{file_extension}"
        file_path.touch()
        time.sleep(0.1)  # Ensure different modification times

    prune_old_backups(str(backup_dir), backup_keep, file_prefix=file_prefix)

    remaining_files = sorted([f.name for f in backup_dir.iterdir()])
    assert remaining_files == ["backup_3.txt"]


def test_prune_old_backups_only_extension(tmp_path):
    """Test with only a extension"""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_keep = 1
    file_prefix = "backup_"
    file_extension = "txt"

    # Create some dummy files with different timestamps
    for i in range(4):
        file_path = backup_dir / f"{file_prefix}{i}.{file_extension}"
        file_path.touch()
        time.sleep(0.1)  # Ensure different modification times

    prune_old_backups(str(backup_dir), backup_keep, file_extension=file_extension)

    remaining_files = sorted([f.name for f in backup_dir.iterdir()])
    assert remaining_files == ["backup_3.txt"]


# --- Tests for backup_world ---


@patch("bedrock_server_manager.core.server.world.export_world")
@patch("bedrock_server_manager.utils.general.get_timestamp", return_value="12345")
def test_backup_world_successful(mock_get_timestamp, mock_export_world, tmp_path):
    """Test successful world backup."""
    server_name = "test_server"
    world_path = tmp_path / "worlds" / "test_world"
    world_path.mkdir(parents=True)  # Create the world directory
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    backup_world(server_name, str(world_path), str(backup_dir))

    expected_backup_file = os.path.join(
        str(backup_dir), f"{os.path.basename(world_path)}_backup_12345.mcworld"
    )
    mock_export_world.assert_called_once_with(str(world_path), expected_backup_file)


def test_backup_world_world_directory_not_found(tmp_path):
    """Test with a world_path that doesn't exist."""
    server_name = "test_server"
    world_path = tmp_path / "nonexistent_world"  # Doesn't exist
    backup_dir = tmp_path / "backups"

    with pytest.raises(DirectoryError, match="World directory '.*' does not exist."):
        backup_world(server_name, str(world_path), str(backup_dir))


# --- Tests for backup_config_file ---


@patch("bedrock_server_manager.utils.general.get_timestamp", return_value="67890")
@patch("shutil.copy2")
def test_backup_config_file_successful(mock_copy2, mock_get_timestamp, tmp_path):
    """Test successful backup of a configuration file."""
    file_to_backup = tmp_path / "test_config.txt"
    file_to_backup.write_text("This is a test config file.")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    backup_config_file(str(file_to_backup), str(backup_dir))

    expected_backup_file = os.path.join(str(backup_dir), "test_config_backup_67890.txt")
    mock_copy2.assert_called_once_with(str(file_to_backup), expected_backup_file)


def test_backup_config_file_missing_file_to_backup():
    """Test with a missing file_to_backup argument."""
    with pytest.raises(MissingArgumentError, match="file_to_backup is empty"):
        backup_config_file("", "backup_dir")


def test_backup_config_file_file_not_found(tmp_path):
    """Test with a file_to_backup that doesn't exist."""
    file_to_backup = tmp_path / "nonexistent.txt"  # Doesn't exist
    backup_dir = tmp_path / "backups"

    with pytest.raises(FileOperationError, match="Configuration file '.*' not found!"):
        backup_config_file(str(file_to_backup), str(backup_dir))


@patch("shutil.copy2", side_effect=OSError("Mocked copy error"))
def test_backup_config_file_copy_error(mock_copy2, tmp_path):
    """Test handling an error during file copying."""
    file_to_backup = tmp_path / "test_config.txt"
    file_to_backup.write_text("This is a test config file.")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    with pytest.raises(FileOperationError, match="Failed to copy"):
        backup_config_file(str(file_to_backup), str(backup_dir))


# --- Tests for backup_server ---


@patch("bedrock_server_manager.core.server.backup.backup_world")
@patch("bedrock_server_manager.core.server.server.get_world_name")
def test_backup_server_world_backup(mock_get_world_name, mock_backup_world, tmp_path):
    """Test backing up the world."""
    server_name = "test_server"
    backup_type = "world"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    world_name = "test_world"

    mock_get_world_name.return_value = world_name

    with patch("os.makedirs") as mock_makedirs:  # Mock os.makedirs
        backup_server(server_name, backup_type, str(base_dir))
        mock_get_world_name.assert_called_once_with(server_name, str(base_dir))
        mock_backup_world.assert_called_once()


@patch("bedrock_server_manager.core.server.backup.backup_config_file")
def test_backup_server_config_backup(mock_backup_config_file, tmp_path):
    """Test backing up a configuration file."""
    server_name = "test_server"
    backup_type = "config"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    file_to_backup = "test_config.txt"
    (tmp_path / "servers" / server_name).mkdir()
    (tmp_path / "servers" / server_name / "test_config.txt").touch()
    with patch(
        "bedrock_server_manager.core.server.backup.settings.BACKUP_DIR", str(tmp_path)
    ):
        with patch("os.makedirs") as mock_makedirs:  # Mock os.makedirs
            backup_server(server_name, backup_type, str(base_dir), file_to_backup)
            mock_backup_config_file.assert_called_once()


def test_backup_server_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(MissingArgumentError, match="server_name is empty"):
        backup_server("", "world", "base_dir")


def test_backup_server_missing_backup_type():
    """Test with a missing backup_type argument."""
    with pytest.raises(MissingArgumentError, match="backup_type is empty"):
        backup_server("server_name", "", "base_dir")


def test_backup_server_invalid_backup_type(tmp_path):
    """Test with an invalid backup_type."""
    server_name = "test_server"
    backup_type = "invalid_type"
    base_dir = tmp_path / "servers"
    with patch(
        "bedrock_server_manager.core.server.backup.settings.BACKUP_DIR", str(tmp_path)
    ):
        with patch("os.makedirs") as mock_makedirs:  # Mock os.makedirs
            with pytest.raises(InvalidInputError, match="Invalid backup type"):
                backup_server(server_name, backup_type, str(base_dir))


def test_backup_server_config_backup_missing_file(tmp_path):
    """Test config backup with a missing file_to_backup."""
    server_name = "test_server"
    backup_type = "config"
    base_dir = tmp_path / "servers"
    with patch(
        "bedrock_server_manager.core.server.backup.settings.BACKUP_DIR", str(tmp_path)
    ):
        with patch("os.makedirs") as mock_makedirs:  # Mock os.makedirs
            with pytest.raises(MissingArgumentError, match="file_to_backup is empty"):
                backup_server(server_name, backup_type, str(base_dir))


@patch(
    "bedrock_server_manager.core.server.backup.backup_world",
    side_effect=Exception("Mocked backup error"),
)
@patch("bedrock_server_manager.core.server.server.get_world_name")
def test_backup_server_world_backup_error(
    mock_get_world_name, mock_backup_world, tmp_path
):
    """Test handling an error during world backup."""
    server_name = "test_server"
    backup_type = "world"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    world_name = "test_world"

    mock_get_world_name.return_value = world_name
    with patch("os.makedirs") as mock_makedirs:  # Mock os.makedirs
        with pytest.raises(BackupWorldError, match="World backup failed"):
            backup_server(server_name, backup_type, str(base_dir))


@patch("bedrock_server_manager.core.server.server.get_world_name", return_value=None)
def test_backup_server_get_world_name_fails(mock_get_world_name, tmp_path):
    """Tests the scenario where get_world_name returns none."""
    server_name = "test_server"
    backup_type = "world"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    with patch("os.makedirs") as mock_makedirs:  # Mock os.makedirs
        with pytest.raises(BackupWorldError, match="Could not determine world name"):
            backup_server(server_name, backup_type, str(base_dir))


# --- Tests for backup_all ---


@patch("bedrock_server_manager.core.server.backup.backup_server")
def test_backup_all_successful(mock_backup_server, tmp_path):
    """Test successful backup of all files (world and config)."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    # set up the mock calls
    mock_backup_server.side_effect = [None, None, None, None]
    with patch(
        "bedrock_server_manager.core.server.backup.settings.BASE_DIR", str(base_dir)
    ):
        backup_all(server_name)
        assert mock_backup_server.call_count == 4
        # Check specific calls with call_args_list (order matters)
        expected_calls = [
            (("test_server", "world", str(base_dir), ""), {}),  # World backup
            (
                ("test_server", "config", str(base_dir)),
                {"file_to_backup": "allowlist.json"},
            ),  # Config backups
            (
                ("test_server", "config", str(base_dir)),
                {"file_to_backup": "permissions.json"},
            ),
            (
                ("test_server", "config", str(base_dir)),
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
def test_backup_all_backup_error(mock_backup_server, tmp_path):
    """Test handling an error during backup."""
    server_name = "test_server"
    base_dir = str(tmp_path)

    with pytest.raises(BackupWorldError, match="World backup failed"):
        backup_all(server_name, base_dir)


# --- Tests for restore_config_file ---


@patch("shutil.copy2")
def test_restore_config_file_successful(mock_copy2, tmp_path):
    """Test successful restoration of a configuration file."""
    backup_file = tmp_path / "config_backup_12345.txt"
    backup_file.write_text("Backup content")  # Create a dummy backup file
    server_dir = tmp_path / "server"
    server_dir.mkdir()

    restore_config_file(str(backup_file), str(server_dir))

    expected_target_file = server_dir / "config.txt"
    mock_copy2.assert_called_once_with(str(backup_file), str(expected_target_file))


def test_restore_config_file_missing_backup_file():
    """Test with a missing backup_file argument."""
    with pytest.raises(MissingArgumentError, match="backup_file is empty"):
        restore_config_file("", "server_dir")


def test_restore_config_file_missing_server_dir():
    """Test with a missing server_dir argument."""
    with pytest.raises(MissingArgumentError, match="server_dir is empty"):
        restore_config_file("backup.txt", "")


def test_restore_config_file_backup_file_not_found(tmp_path):
    """Test with a backup_file that doesn't exist."""
    backup_file = tmp_path / "nonexistent.txt"  # Doesn't exist
    server_dir = tmp_path / "server"

    with pytest.raises(FileOperationError, match="Backup file '.*' not found!"):
        restore_config_file(str(backup_file), str(server_dir))


@patch("shutil.copy2", side_effect=OSError("Mocked copy error"))
def test_restore_config_file_copy_error(mock_copy2, tmp_path):
    """Test handling an error during file copying."""
    backup_file = tmp_path / "config_backup_12345.txt"
    backup_file.write_text("Backup content")
    server_dir = tmp_path / "server"
    server_dir.mkdir()

    with pytest.raises(
        FileOperationError, match="Failed to restore configuration file"
    ):
        restore_config_file(str(backup_file), str(server_dir))


# --- Tests for restore_server ---


@patch("bedrock_server_manager.core.server.world.import_world")
def test_restore_server_world_restore(mock_import_world, tmp_path):
    """Test restoring a world backup."""
    server_name = "test_server"
    backup_file = tmp_path / "world_backup.mcworld"
    backup_file.touch()  # create file
    restore_type = "world"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()

    restore_server(server_name, str(backup_file), restore_type, str(base_dir))
    mock_import_world.assert_called_once_with(
        server_name, str(backup_file), str(base_dir)
    )


@patch("bedrock_server_manager.core.server.backup.restore_config_file")
def test_restore_server_config_restore(mock_restore_config_file, tmp_path):
    """Test restoring a configuration file backup."""
    server_name = "test_server"
    backup_file = tmp_path / "config_backup.txt"
    backup_file.touch()  # create file
    restore_type = "config"
    base_dir = tmp_path / "servers"
    (base_dir / server_name).mkdir(parents=True)  # create server dir

    restore_server(server_name, str(backup_file), restore_type, str(base_dir))
    mock_restore_config_file.assert_called_once()


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


def test_restore_server_backup_file_not_found(tmp_path):
    """Test with a backup_file that doesn't exist."""
    server_name = "test_server"
    backup_file = tmp_path / "nonexistent.txt"  # Doesn't exist
    restore_type = "world"
    base_dir = tmp_path / "servers"

    with pytest.raises(FileOperationError, match="Backup file '.*' not found!"):
        restore_server(server_name, str(backup_file), restore_type, str(base_dir))


def test_restore_server_invalid_restore_type(tmp_path):
    """Test with an invalid restore_type."""
    server_name = "test_server"
    backup_file = tmp_path / "backup.txt"
    backup_file.touch()  # create file
    restore_type = "invalid_type"
    base_dir = tmp_path / "servers"

    with pytest.raises(InvalidInputError, match="Invalid restore type"):
        restore_server(server_name, str(backup_file), restore_type, str(base_dir))


# --- Tests for restore_all ---


@patch("bedrock_server_manager.core.server.backup.restore_server")
def test_restore_all_successful(mock_restore_server, tmp_path):
    """Test successful restoration of all latest backups."""
    server_name = "test_server"
    backup_dir = tmp_path / "backups" / server_name
    backup_dir.mkdir(parents=True)
    # Create some dummy backup files with different timestamps
    (backup_dir / "world_backup_1.mcworld").touch()
    time.sleep(0.1)
    (backup_dir / "world_backup_2.mcworld").touch()  # Latest world
    time.sleep(0.1)
    (backup_dir / "server_backup_1.properties").touch()
    time.sleep(0.1)
    (backup_dir / "server_backup_2.properties").touch()  # Latest properties
    time.sleep(0.1)
    (backup_dir / "permissions_backup_1.json").touch()
    time.sleep(0.1)
    (backup_dir / "permissions_backup_2.json").touch()  # Latest permissions
    time.sleep(0.1)
    (backup_dir / "allowlist_backup_1.json").touch()
    time.sleep(0.1)
    (backup_dir / "allowlist_backup_2.json").touch()  # Latest allowlist
    base_dir = tmp_path / "servers"

    with patch(
        "bedrock_server_manager.core.server.backup.settings.BACKUP_DIR",
        str(tmp_path / "backups"),
    ):
        restore_all(server_name, str(base_dir))

    # Check that restore_server was called with the correct arguments
    expected_calls = [
        (
            (
                server_name,
                str(backup_dir / "world_backup_2.mcworld"),
                "world",
                str(base_dir),
            ),
            {},
        ),
        (
            (
                server_name,
                str(backup_dir / "server_backup_2.properties"),
                "config",
                str(base_dir),
            ),
            {},
        ),
        (
            (
                server_name,
                str(backup_dir / "allowlist_backup_2.json"),
                "config",
                str(base_dir),
            ),
            {},
        ),
        (
            (
                server_name,
                str(backup_dir / "permissions_backup_2.json"),
                "config",
                str(base_dir),
            ),
            {},
        ),
    ]
    mock_restore_server.assert_has_calls(expected_calls, any_order=True)


def test_restore_all_missing_server_name(tmp_path):
    """Test with a missing server_name argument."""
    with pytest.raises(MissingArgumentError, match="server_name is empty"):
        restore_all("", str(tmp_path))


def test_restore_all_no_backups_found(tmp_path):
    """Test when no backups are found for the server."""
    server_name = "test_server"
    backup_dir = tmp_path / "backups" / server_name  # directory doesnt exist
    base_dir = tmp_path / "server"
    # Should not raise an exception, just log a message
    with patch(
        "bedrock_server_manager.core.server.backup.settings.BACKUP_DIR",
        str(tmp_path / "backups"),
    ):
        restore_all(server_name, str(base_dir))


@patch(
    "bedrock_server_manager.core.server.backup.restore_server",
    side_effect=Exception("Mocked restore error"),
)
def test_restore_all_restore_error(mock_restore_server, tmp_path):
    """Test handling an error during restoration."""
    server_name = "test_server"
    backup_dir = tmp_path / "backups" / server_name
    backup_dir.mkdir(parents=True)
    (backup_dir / "world_backup_1.mcworld").touch()  # Create a dummy backup file
    base_dir = tmp_path / "servers"
    with patch(
        "bedrock_server_manager.core.server.backup.settings.BACKUP_DIR",
        str(tmp_path / "backups"),
    ):

        with pytest.raises(RestoreError, match="Failed to restore world"):
            restore_all(server_name, str(base_dir))
