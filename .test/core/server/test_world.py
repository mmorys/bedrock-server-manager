# bedrock-server-manager/tests/core/server/test_world.py
import pytest
import os
import shutil
import zipfile
from unittest.mock import patch, MagicMock, mock_open
from bedrock_server_manager.core.server.world import (
    extract_world,
    export_world,
    import_world,
)
from bedrock_server_manager.core.error import (
    MissingArgumentError,
    DownloadExtractError,
    FileOperationError,
    BackupWorldError,
    DirectoryError,
)

# --- Fixtures ---


@pytest.fixture
def mock_world_dir(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "level.dat").touch()  # Create a dummy file
    yield str(world_dir)


@pytest.fixture
def mock_server_dir(tmp_path):
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    (server_dir / "worlds").mkdir()
    yield str(server_dir)


# --- Tests for extract_world ---


def test_extract_world_successful(tmp_path):
    """Test successful extraction of a world."""
    # Create a dummy .mcworld file (which is just a zip)
    world_file = tmp_path / "test_world.mcworld"
    with zipfile.ZipFile(world_file, "w") as zf:
        zf.writestr("test_file.txt", "This is a test file.")

    extract_dir = tmp_path / "extracted_world"
    extract_world(str(world_file), str(extract_dir))

    assert extract_dir.exists()
    assert (extract_dir / "test_file.txt").exists()
    assert (extract_dir / "test_file.txt").read_text() == "This is a test file."


def test_extract_world_missing_world_file():
    """Test with a missing world_file argument."""
    with pytest.raises(MissingArgumentError, match="world_file is empty"):
        extract_world("", "extract_dir")


def test_extract_world_missing_extract_dir():
    """Test with a missing extract_dir argument."""
    with pytest.raises(MissingArgumentError, match="extract_dir is empty"):
        extract_world("world_file.mcworld", "")


def test_extract_world_world_file_not_found(tmp_path):
    """Test with a world_file that doesn't exist."""
    world_file = tmp_path / "nonexistent.mcworld"  # Doesn't exist
    extract_dir = tmp_path / "extract"
    with pytest.raises(FileOperationError, match="world_file does not exist"):
        extract_world(str(world_file), str(extract_dir))


def test_extract_world_invalid_zip_file(tmp_path):
    """Test with an invalid .mcworld file (not a zip)."""
    world_file = tmp_path / "invalid.mcworld"
    world_file.write_text("This is not a zip file.")  # Create a non-zip file

    extract_dir = tmp_path / "extract"
    with pytest.raises(DownloadExtractError, match="Invalid zip file"):
        extract_world(str(world_file), str(extract_dir))


@patch("shutil.rmtree", side_effect=OSError("Mocked rmtree error"))
def test_extract_world_remove_existing_dir_error(mock_rmtree, tmp_path):
    """Test handling an error when removing an existing extraction directory."""
    world_file = tmp_path / "test.mcworld"
    # Create dummy zip
    with zipfile.ZipFile(world_file, "w") as zf:
        zf.writestr("test_file.txt", "This is a test file.")

    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()  # make sure the directory exists

    with pytest.raises(
        FileOperationError, match="Failed to remove existing world folder content"
    ):
        extract_world(str(world_file), str(extract_dir))


@patch("zipfile.ZipFile", side_effect=zipfile.BadZipFile)
@patch("os.path.exists", return_value=True)
@patch("shutil.rmtree")  # Mock rmtree
def test_extract_world_zipfile_error(mock_rmtree, mock_exists, mock_zipfile, tmp_path):
    """Test for a generic OSError during zip extraction."""
    world_file = tmp_path / "test.mcworld"
    extract_dir = tmp_path / "extract"

    with pytest.raises(DownloadExtractError, match="Failed to extract world from"):
        extract_world(str(world_file), str(extract_dir))


# --- Tests for export_world ---
def test_export_world_successful(mock_world_dir, tmp_path):
    """Test successful export of a world."""
    backup_file = tmp_path / "backup.mcworld"
    export_world(mock_world_dir, str(backup_file))

    assert backup_file.exists()
    # Verify that it's a valid zip file
    with zipfile.ZipFile(backup_file, "r") as zf:
        assert "level.dat" in zf.namelist()


def test_export_world_missing_world_path():
    """Test with a missing world_path argument."""
    with pytest.raises(MissingArgumentError, match="world_path is empty"):
        export_world("", "backup_file.mcworld")


def test_export_world_missing_backup_file():
    """Test with a missing backup_file argument."""
    with pytest.raises(MissingArgumentError, match="backup_file is empty"):
        export_world("world_path", "")


def test_export_world_world_directory_not_found(tmp_path):
    """Test with a world_path that doesn't exist."""
    world_path = tmp_path / "nonexistent_world"  # Doesn't exist
    backup_file = tmp_path / "backup.mcworld"
    with pytest.raises(DirectoryError, match="World directory '.*' does not exist."):
        export_world(str(world_path), str(backup_file))


@patch("shutil.make_archive", side_effect=OSError("Mocked make_archive error"))
def test_export_world_backup_error(mock_make_archive, mock_world_dir, tmp_path):
    """Test handling an error during the backup process."""
    backup_file = tmp_path / "backup.mcworld"
    with pytest.raises(BackupWorldError, match="Backup of world failed"):
        export_world(mock_world_dir, str(backup_file))


# --- Tests for import_world ---


@patch("bedrock_server_manager.core.server.world.extract_world")
@patch("bedrock_server_manager.core.server.server.get_world_name")
def test_import_world_successful(mock_get_world_name, mock_extract_world, tmp_path):
    """Test successful import of a world."""
    backup_file = tmp_path / "backup.mcworld"
    backup_file.touch()
    server_name = "test_server"
    world_name = "test_world"
    mock_get_world_name.return_value = world_name
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    server_dir = base_dir / server_name
    server_dir.mkdir()

    import_world(server_name, str(backup_file), str(base_dir))

    mock_get_world_name.assert_called_once_with(server_name, str(base_dir))
    mock_extract_world.assert_called_once_with(
        str(backup_file), os.path.join(str(server_dir), "worlds", world_name)
    )


def test_import_world_backup_file_not_found(tmp_path):
    """Test with a backup_file that doesn't exist."""
    backup_file = tmp_path / "nonexistent.mcworld"  # Doesn't exist
    server_name = "test_server"
    with pytest.raises(FileOperationError, match="backup_file does not exist"):
        import_world(server_name, str(backup_file), "base_dir")


@patch("bedrock_server_manager.core.server.server.get_world_name", return_value=None)
def test_import_world_get_world_name_returns_none(mock_get_world_name, tmp_path):
    """Test when get_world_name returns None."""
    backup_file = tmp_path / "backup.mcworld"
    backup_file.touch()
    server_name = "test_server"
    base_dir = tmp_path
    with pytest.raises(
        FileOperationError, match="Failed to get world name from server.properties"
    ):
        import_world(server_name, str(backup_file), str(base_dir))


@patch(
    "bedrock_server_manager.core.server.server.get_world_name",
    side_effect=Exception("Mocked get_world_name error"),
)
def test_import_world_get_world_name_raises_exception(mock_get_world_name, tmp_path):
    """Test when get_world_name raises an exception."""
    backup_file = tmp_path / "backup.mcworld"
    backup_file.touch()  # Create file
    server_name = "test_server"
    base_dir = tmp_path
    with pytest.raises(
        FileOperationError, match="Failed to get world name from server.properties"
    ):
        import_world(server_name, str(backup_file), str(base_dir))
