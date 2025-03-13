# bedrock-server-manager/tests/core/server/test_addon.py
import os
import zipfile
import json
import pytest
from unittest.mock import patch, MagicMock, mock_open, call
from bedrock_server_manager.core.server import server
from bedrock_server_manager.core.server.addon import (
    process_addon,
    process_mcaddon,
    process_mcpack,
    _process_mcaddon_files,
    _process_manifest,
    _extract_manifest_info,
    install_pack,
    _update_pack_json,
    world,
)
from bedrock_server_manager.core.error import (
    MissingArgumentError,
    FileOperationError,
    InvalidAddonPackTypeError,
    InvalidServerNameError,
    DownloadExtractError,
    DirectoryError,
)

# --- Tests for process_addon ---


def test_process_addon_mcaddon(tmp_path):
    """Test processing a .mcaddon file."""
    addon_file = tmp_path / "test.mcaddon"
    addon_file.touch()  # Create a dummy file
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()

    with patch(
        "bedrock_server_manager.core.server.addon.process_mcaddon"
    ) as mock_process_mcaddon:
        process_addon(str(addon_file), server_name, str(base_dir))
        mock_process_mcaddon.assert_called_once_with(
            str(addon_file), server_name, str(base_dir)
        )


def test_process_addon_mcpack(tmp_path):
    """Test processing a .mcpack file."""
    addon_file = tmp_path / "test.mcpack"
    addon_file.touch()
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()

    with patch(
        "bedrock_server_manager.core.server.addon.process_mcpack"
    ) as mock_process_mcpack:
        process_addon(str(addon_file), server_name, str(base_dir))
        mock_process_mcpack.assert_called_once_with(
            str(addon_file), server_name, str(base_dir)
        )


def test_process_addon_missing_addon_file():
    """Test with a missing addon_file argument."""
    with pytest.raises(MissingArgumentError, match="addon_file is empty"):
        process_addon("", "server_name", "base_dir")


def test_process_addon_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        process_addon("addon_file.mcaddon", "", "base_dir")


def test_process_addon_addon_file_not_found(tmp_path):
    """Test with an addon_file that doesn't exist."""
    addon_file = tmp_path / "nonexistent.mcaddon"  # Doesn't exist
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    with pytest.raises(FileOperationError, match="addon_file does not exist"):
        process_addon(str(addon_file), server_name, str(base_dir))


def test_process_addon_unsupported_file_type(tmp_path):
    """Test with an unsupported file type."""
    addon_file = tmp_path / "test.txt"  # Unsupported type
    addon_file.touch()
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    with pytest.raises(InvalidAddonPackTypeError, match="Unsupported addon file type"):
        process_addon(str(addon_file), server_name, str(base_dir))


# --- Tests for process_mcaddon ---


@patch("bedrock_server_manager.core.server.addon._process_mcaddon_files")
@patch("zipfile.ZipFile")
@patch("tempfile.mkdtemp", return_value="/tmp/mock_temp_dir")
def test_process_mcaddon_successful(
    mock_mkdtemp, mock_zipfile, mock_process_files, tmp_path
):
    """Test successful processing of a .mcaddon file."""
    addon_file = tmp_path / "test.mcaddon"
    addon_file.touch()  # dummy file
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()

    # Mock the ZipFile instance to avoid real file operations
    mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
    mock_zip_instance.extractall.return_value = None

    with patch("shutil.rmtree") as mock_rmtree:
        process_mcaddon(str(addon_file), server_name, str(base_dir))
        mock_zipfile.assert_called_once_with(str(addon_file), "r")
        mock_zip_instance.extractall.assert_called_once_with(
            "/tmp/mock_temp_dir"
        )  # Check temp dir
        mock_process_files.assert_called_once_with(
            "/tmp/mock_temp_dir", server_name, str(base_dir)
        )
        mock_rmtree.assert_called_once_with("/tmp/mock_temp_dir")  # check cleanup


def test_process_mcaddon_missing_addon_file():
    """Test with a missing addon_file argument."""
    with pytest.raises(MissingArgumentError, match="addon_file is empty"):
        process_mcaddon("", "server_name", "base_dir")


def test_process_mcaddon_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        process_mcaddon("addon.mcaddon", "", "base_dir")


def test_process_mcaddon_addon_file_not_found(tmp_path):
    """Test with an addon_file that doesn't exist."""
    addon_file = tmp_path / "nonexistent.mcaddon"
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    with pytest.raises(FileOperationError, match="addon_file does not exist"):
        process_mcaddon(str(addon_file), server_name, str(base_dir))


@patch("zipfile.ZipFile", side_effect=zipfile.BadZipFile)
@patch("tempfile.mkdtemp", return_value="/tmp/mock_temp_dir")
def test_process_mcaddon_invalid_zip_file(mock_mkdtemp, mock_zipfile, tmp_path):
    """Test with an invalid .mcaddon file (not a zip)."""
    addon_file = tmp_path / "invalid.mcaddon"
    addon_file.touch()  # Create a dummy, non-zip file
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    with patch("shutil.rmtree") as mock_rmtree:
        with pytest.raises(DownloadExtractError, match="Not a valid zip file"):
            process_mcaddon(str(addon_file), server_name, str(base_dir))
        mock_rmtree.assert_called_once_with("/tmp/mock_temp_dir")


@patch("zipfile.ZipFile", side_effect=OSError("Mocked zip error"))
@patch("tempfile.mkdtemp", return_value="/tmp/mock_temp_dir")
def test_process_mcaddon_zip_extraction_error(mock_mkdtemp, mock_zipfile, tmp_path):
    """Test handling an OSError during zip extraction."""
    addon_file = tmp_path / "test.mcaddon"
    addon_file.touch()
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()

    with patch("shutil.rmtree") as mock_rmtree:
        with pytest.raises(FileOperationError, match="Failed to unzip .mcaddon file"):
            process_mcaddon(str(addon_file), server_name, str(base_dir))
        mock_rmtree.assert_called_once_with("/tmp/mock_temp_dir")


@patch(
    "bedrock_server_manager.core.server.addon._process_mcaddon_files",
    side_effect=Exception("Mocked processing error"),
)
@patch("zipfile.ZipFile")
@patch("tempfile.mkdtemp", return_value="/tmp/mock_temp_dir")
def test_process_mcaddon_processing_error(
    mock_mkdtemp, mock_zipfile, mock_process_files, tmp_path
):
    """Test handling an error during file processing."""
    addon_file = tmp_path / "test.mcaddon"
    addon_file.touch()
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    # Mock zipfile instance
    mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
    mock_zip_instance.extractall.return_value = None
    with patch("shutil.rmtree") as mock_rmtree:  # Mock rmtree
        with pytest.raises(Exception, match="Mocked processing error"):
            process_mcaddon(str(addon_file), server_name, str(base_dir))
        mock_rmtree.assert_called_with(
            "/tmp/mock_temp_dir"
        )  # check temp dir is cleaned up


# --- Tests for _process_mcaddon_files ---


@patch("bedrock_server_manager.core.server.addon.process_mcpack")
@patch("bedrock_server_manager.core.server.world.extract_world")
@patch("bedrock_server_manager.core.server.server.get_world_name")
def test_process_mcaddon_files_successful(
    mock_get_world_name, mock_extract_world, mock_process_mcpack, tmp_path
):
    """Test successful processing of files within an .mcaddon."""
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    # Create dummy .mcworld and .mcpack files
    (temp_dir / "test.mcworld").touch()
    (temp_dir / "test.mcpack").touch()
    (temp_dir / "random_file.txt").touch()  # Should be ignored

    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    world_name = "test_world"

    mock_get_world_name.return_value = world_name

    _process_mcaddon_files(str(temp_dir), server_name, str(base_dir))
    mock_get_world_name.assert_called_once_with(server_name, str(base_dir))
    mock_extract_world.assert_called_once_with(
        str(temp_dir / "test.mcworld"),
        os.path.join(str(base_dir), server_name, "worlds", world_name),
    )
    mock_process_mcpack.assert_called_once_with(
        str(temp_dir / "test.mcpack"), server_name, str(base_dir)
    )


def test_process_mcaddon_files_missing_temp_dir():
    """Test with a missing temp_dir argument."""
    with pytest.raises(MissingArgumentError, match="temp_dir is empty"):
        _process_mcaddon_files("", "server_name", "base_dir")


def test_process_mcaddon_files_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        _process_mcaddon_files("temp_dir", "", "base_dir")


def test_process_mcaddon_files_temp_dir_not_found(tmp_path):
    """Test with a temp_dir that doesn't exist."""
    temp_dir = tmp_path / "nonexistent"  # Doesn't exist
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    with pytest.raises(
        DirectoryError, match="temp_dir does not exist or is not a directory"
    ):
        _process_mcaddon_files(str(temp_dir), server_name, str(base_dir))


@patch(
    "bedrock_server_manager.core.server.addon.world.extract_world",
    side_effect=Exception("Mocked extraction error"),
)
@patch("bedrock_server_manager.core.server.server.get_world_name")
def test_process_mcaddon_files_world_extraction_error(
    mock_get_world_name, mock_extract_world, tmp_path
):
    """Test handling an error during world extraction."""
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    (temp_dir / "test.mcworld").touch()

    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()

    mock_get_world_name.return_value = "test_world"

    with pytest.raises(FileOperationError, match="Failed to extract world"):
        _process_mcaddon_files(str(temp_dir), server_name, str(base_dir))


@patch(
    "bedrock_server_manager.core.server.server.get_world_name", return_value=None
)  # worldname is None
def test_process_mcaddon_files_get_world_name_fails(mock_get_world_name, tmp_path):
    """Tests the scenario where get_world_name returns none."""
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    (temp_dir / "test.mcworld").touch()

    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    with pytest.raises(FileOperationError, match="Failed to determine world name"):
        _process_mcaddon_files(str(temp_dir), server_name, str(base_dir))


# --- Tests for process_mcpack ---


@patch("bedrock_server_manager.core.server.addon._process_manifest")
@patch("zipfile.ZipFile")
@patch("tempfile.mkdtemp", return_value="/tmp/mock_temp_dir_mcpack")
def test_process_mcpack_successful(
    mock_mkdtemp, mock_zipfile, mock_process_manifest, tmp_path
):
    """Test successful processing of a .mcpack file."""
    pack_file = tmp_path / "test.mcpack"
    pack_file.touch()
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    # Mock ZipFile instance
    mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
    mock_zip_instance.extractall.return_value = None

    with patch("shutil.rmtree") as mock_rmtree:  # Mock rmtree
        process_mcpack(str(pack_file), server_name, str(base_dir))

        mock_zipfile.assert_called_once_with(str(pack_file), "r")
        mock_zip_instance.extractall.assert_called_once_with(
            "/tmp/mock_temp_dir_mcpack"
        )
        mock_process_manifest.assert_called_once_with(
            "/tmp/mock_temp_dir_mcpack", server_name, str(pack_file), str(base_dir)
        )
        mock_rmtree.assert_called_once_with(
            "/tmp/mock_temp_dir_mcpack"
        )  # Check cleanup


def test_process_mcpack_missing_pack_file():
    """Test with a missing pack_file argument."""
    with pytest.raises(MissingArgumentError, match="pack_file is empty"):
        process_mcpack("", "server_name", "base_dir")


def test_process_mcpack_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        process_mcpack("pack.mcpack", "", "base_dir")


def test_process_mcpack_pack_file_not_found(tmp_path):
    """Test with a pack_file that doesn't exist."""
    pack_file = tmp_path / "nonexistent.mcpack"
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    with pytest.raises(FileOperationError, match="pack_file does not exist"):
        process_mcpack(str(pack_file), server_name, str(base_dir))


@patch("zipfile.ZipFile", side_effect=zipfile.BadZipFile)
@patch("tempfile.mkdtemp", return_value="/tmp/mock_temp_dir_mcpack")
def test_process_mcpack_invalid_zip_file(mock_mkdtemp, mock_zipfile, tmp_path):
    """Test with an invalid .mcpack file (not a zip)."""
    pack_file = tmp_path / "invalid.mcpack"
    pack_file.touch()  # Create a dummy, non-zip file
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    with patch("shutil.rmtree") as mock_rmtree:  # Mock rmtree
        with pytest.raises(DownloadExtractError, match="Not a valid zip file"):
            process_mcpack(str(pack_file), server_name, str(base_dir))
        mock_rmtree.assert_called_once_with(
            "/tmp/mock_temp_dir_mcpack"
        )  # Check cleanup


@patch("zipfile.ZipFile", side_effect=OSError("Mocked zip error"))
@patch("tempfile.mkdtemp", return_value="/tmp/mock_temp_dir_mcpack")
def test_process_mcpack_zip_extraction_error(mock_mkdtemp, mock_zipfile, tmp_path):
    """Test handling an OSError during zip extraction."""
    pack_file = tmp_path / "test.mcpack"
    pack_file.touch()  # Create file
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    with patch("shutil.rmtree") as mock_rmtree:  # Mock rmtree
        with pytest.raises(FileOperationError, match="Failed to unzip .mcpack file"):
            process_mcpack(str(pack_file), server_name, str(base_dir))
        mock_rmtree.assert_called_once_with("/tmp/mock_temp_dir_mcpack")


@patch(
    "bedrock_server_manager.core.server.addon._process_manifest",
    side_effect=Exception("Mocked processing error"),
)
@patch("zipfile.ZipFile")
@patch("tempfile.mkdtemp", return_value="/tmp/mock_temp_dir_mcpack")
def test_process_mcpack_manifest_processing_error(
    mock_mkdtemp, mock_zipfile, mock_process_manifest, tmp_path
):
    """Test handling an error during manifest processing."""
    pack_file = tmp_path / "test.mcpack"
    pack_file.touch()  # Create file
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    # Mock zipfile instance
    mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
    mock_zip_instance.extractall.return_value = None
    with patch("shutil.rmtree") as mock_rmtree:  # Mock rmtree
        with pytest.raises(Exception, match="Mocked processing error"):
            process_mcpack(str(pack_file), server_name, str(base_dir))
        mock_rmtree.assert_called_with("/tmp/mock_temp_dir_mcpack")  # check cleanup


# --- Tests for _process_manifest ---


@patch("bedrock_server_manager.core.server.addon.install_pack")
@patch("bedrock_server_manager.core.server.addon._extract_manifest_info")
def test_process_manifest_successful(mock_extract_info, mock_install_pack, tmp_path):
    """Test successful processing of the manifest."""
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    server_name = "test_server"
    pack_file = tmp_path / "test.mcpack"
    pack_file.touch()  # Create file
    base_dir = tmp_path / "servers"
    base_dir.mkdir()

    # Mock the return value of _extract_manifest_info
    mock_extract_info.return_value = ("data", "some-uuid", [1, 2, 3], "My Addon")

    _process_manifest(str(temp_dir), server_name, str(pack_file), str(base_dir))

    mock_extract_info.assert_called_once_with(str(temp_dir))
    mock_install_pack.assert_called_once_with(
        "data",
        str(temp_dir),
        server_name,
        str(pack_file),
        str(base_dir),
        "some-uuid",
        [1, 2, 3],
        "My Addon",
    )


def test_process_manifest_missing_temp_dir():
    """Test with a missing temp_dir argument."""
    with pytest.raises(MissingArgumentError, match="temp_dir is empty"):
        _process_manifest("", "server_name", "pack_file", "base_dir")


def test_process_manifest_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        _process_manifest("temp_dir", "", "pack_file", "base_dir")


def test_process_manifest_missing_pack_file():
    """Test with a missing pack_file argument."""
    with pytest.raises(MissingArgumentError, match="pack_file is empty"):
        _process_manifest("temp_dir", "server_name", "", "base_dir")


@patch(
    "bedrock_server_manager.core.server.addon._extract_manifest_info", return_value=None
)
def test_process_manifest_extract_info_fails(mock_extract_info, tmp_path):
    """Test when _extract_manifest_info returns None (manifest error)."""
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    server_name = "test_server"
    pack_file = tmp_path / "test.mcpack"  # Create dummy file
    pack_file.touch()
    base_dir = tmp_path / "server_dir"
    base_dir.mkdir()
    with pytest.raises(
        FileOperationError,
        match="Failed to process .* due to missing or invalid manifest.json",
    ):
        _process_manifest(str(temp_dir), server_name, str(pack_file), str(base_dir))


# --- Tests for _extract_manifest_info ---


def test_extract_manifest_info_successful(tmp_path):
    """Test successful extraction of manifest information."""
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    manifest_data = {
        "modules": [{"type": "data", "uuid": "module-uuid", "version": [1, 0, 0]}],
        "header": {"uuid": "header-uuid", "version": [2, 1, 0], "name": "My Addon"},
    }
    manifest_file = temp_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest_data, f)

    expected_info = ("data", "header-uuid", [2, 1, 0], "My Addon")
    assert _extract_manifest_info(str(temp_dir)) == expected_info


def test_extract_manifest_info_missing_temp_dir():
    """Test with a missing temp_dir argument."""
    with pytest.raises(MissingArgumentError, match="temp_dir is empty"):
        _extract_manifest_info("")


def test_extract_manifest_info_manifest_file_not_found(tmp_path):
    """Test when manifest.json is not found."""
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    # No manifest.json created
    with pytest.raises(FileOperationError, match="manifest.json not found"):
        _extract_manifest_info(str(temp_dir))


def test_extract_manifest_info_invalid_json(tmp_path):
    """Test with invalid JSON in manifest.json."""
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    manifest_file = temp_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        f.write("This is not valid JSON")

    with pytest.raises(
        FileOperationError, match="Failed to extract info from manifest.json"
    ):
        _extract_manifest_info(str(temp_dir))


def test_extract_manifest_info_missing_keys(tmp_path):
    """Test with missing keys in manifest.json."""
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    # Missing "modules" key
    manifest_data = {
        "header": {"uuid": "header-uuid", "version": [1, 0, 0], "name": "My Addon"}
    }
    manifest_file = temp_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest_data, f)

    with pytest.raises(
        FileOperationError, match="Failed to extract info from manifest.json"
    ):
        _extract_manifest_info(str(temp_dir))


@patch("os.path.exists", return_value=False)
def test_extract_manifest_info_os_error(mock_exists, tmp_path):
    """Test for a generic OSError."""
    temp_dir = tmp_path / "temp"
    expected_message = f"manifest.json not found in {str(temp_dir)}".replace(
        "\\", "\\\\"
    )
    with pytest.raises(FileOperationError, match=expected_message):
        _extract_manifest_info(str(temp_dir))


# --- Tests for install_pack ---


@patch("bedrock_server_manager.core.server.addon._update_pack_json")
@patch("bedrock_server_manager.core.server.server.get_world_name")
def test_install_pack_data_pack_successful(
    mock_get_world_name, mock_update_pack_json, tmp_path
):
    """Test successful installation of a data (behavior) pack."""
    pack_type = "data"
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    (temp_dir / "some_file.txt").touch()  # Create a dummy file
    server_name = "test_server"
    pack_file = "test.mcpack"  # Doesn't need to exist
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    uuid = "some-uuid"
    version = [1, 2, 3]
    addon_name = "MyAddon"
    world_name = "test_world"

    mock_get_world_name.return_value = world_name

    with patch("shutil.copy2") as mock_copy2, patch("shutil.copytree") as mock_copytree:
        install_pack(
            pack_type,
            str(temp_dir),
            server_name,
            pack_file,
            str(base_dir),
            uuid,
            version,
            addon_name,
        )

        mock_get_world_name.assert_called_once_with(server_name, str(base_dir))
        behavior_dir = os.path.join(
            str(base_dir),
            server_name,
            "worlds",
            world_name,
            "behavior_packs",
            f"{addon_name}_{'.'.join(map(str,version))}",
        )
        assert os.path.exists(behavior_dir)
        mock_update_pack_json.assert_called_once()


@patch("bedrock_server_manager.core.server.addon._update_pack_json")
@patch("bedrock_server_manager.core.server.server.get_world_name")
def test_install_pack_resource_pack_successful(
    mock_get_world_name, mock_update_pack_json, tmp_path
):
    """Test successful installation of a resource pack."""
    pack_type = "resources"
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    (temp_dir / "some_file.txt").touch()  # Create a dummy file
    (temp_dir / "some_dir").mkdir()  # Create a dummy directory
    server_name = "test_server"
    pack_file = "test.mcpack"  # Doesn't need to exist
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    uuid = "some-uuid"
    version = [1, 2, 3]
    addon_name = "MyResource"
    world_name = "test_world"

    mock_get_world_name.return_value = world_name

    with patch("shutil.copy2") as mock_copy2, patch("shutil.copytree") as mock_copytree:
        install_pack(
            pack_type,
            str(temp_dir),
            server_name,
            pack_file,
            str(base_dir),
            uuid,
            version,
            addon_name,
        )

        mock_get_world_name.assert_called_once_with(server_name, str(base_dir))
        resource_dir = os.path.join(
            str(base_dir),
            server_name,
            "worlds",
            world_name,
            "resource_packs",
            f"{addon_name}_{'.'.join(map(str,version))}",
        )
        assert os.path.exists(resource_dir)
        mock_update_pack_json.assert_called_once()


def test_install_pack_missing_pack_type():
    """Test with a missing pack_type argument."""
    with pytest.raises(MissingArgumentError, match="type is empty"):
        install_pack(
            "",
            "temp_dir",
            "server_name",
            "pack_file",
            "base_dir",
            "uuid",
            [1, 2, 3],
            "name",
        )


def test_install_pack_missing_temp_dir():
    """Test with a missing temp_dir argument."""
    with pytest.raises(MissingArgumentError, match="temp_dir is empty"):
        install_pack(
            "data",
            "",
            "server_name",
            "pack_file",
            "base_dir",
            "uuid",
            [1, 2, 3],
            "name",
        )


def test_install_pack_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        install_pack(
            "data", "temp_dir", "", "pack_file", "base_dir", "uuid", [1, 2, 3], "name"
        )


def test_install_pack_missing_pack_file():
    """Test with a missing pack_file argument."""
    with pytest.raises(MissingArgumentError, match="pack_file is empty"):
        install_pack(
            "data", "temp_dir", "server_name", "", "base_dir", "uuid", [1, 2, 3], "name"
        )


@patch("bedrock_server_manager.core.server.server.get_world_name", return_value=None)
def test_install_pack_get_world_name_fails(mock_get_world_name, tmp_path):
    """Test when get_world_name returns None."""
    pack_type = "data"
    temp_dir = tmp_path / "temp"
    server_name = "test_server"
    pack_file = "test.mcpack"
    base_dir = str(tmp_path)
    uuid = "some-uuid"
    version = [1, 2, 3]
    addon_name = "MyAddon"
    with pytest.raises(
        FileOperationError, match="Could not find level-name in server.properties"
    ):
        install_pack(
            pack_type,
            str(temp_dir),
            server_name,
            pack_file,
            base_dir,
            uuid,
            version,
            addon_name,
        )


@patch(
    "bedrock_server_manager.core.server.server.get_world_name",
    side_effect=Exception("Mocked get_world_name error"),
)
def test_install_pack_get_world_name_exception(mock_get_world_name, tmp_path):
    """Test for generic exception."""
    pack_type = "data"
    temp_dir = tmp_path / "temp"
    server_name = "test_server"
    pack_file = "test.mcpack"
    base_dir = str(tmp_path)
    uuid = "some-uuid"
    version = [1, 2, 3]
    addon_name = "MyAddon"
    with pytest.raises(FileOperationError, match="Error getting world name"):
        install_pack(
            pack_type,
            str(temp_dir),
            server_name,
            pack_file,
            base_dir,
            uuid,
            version,
            addon_name,
        )


def test_install_pack_invalid_pack_type(tmp_path):
    """Test with an invalid pack_type."""
    pack_type = "invalid_type"
    temp_dir = tmp_path / "temp"
    server_name = "test_server"
    pack_file = "test.mcpack"
    base_dir = str(tmp_path)
    uuid = "some-uuid"
    version = [1, 2, 3]
    addon_name = "MyAddon"
    with patch(
        "bedrock_server_manager.core.server.server.get_world_name",
        return_value="world_name",
    ):
        with pytest.raises(InvalidAddonPackTypeError, match="Unknown pack type"):
            install_pack(
                pack_type,
                str(temp_dir),
                server_name,
                pack_file,
                base_dir,
                uuid,
                version,
                addon_name,
            )


@patch("os.makedirs", side_effect=OSError("Mocked makedirs error"))
@patch("bedrock_server_manager.core.server.server.get_world_name")
def test_install_pack_makedirs_error(mock_get_world_name, mock_makedirs, tmp_path):
    """Test handling an error when creating directories."""
    pack_type = "data"
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    server_name = "test_server"
    pack_file = "test.mcpack"
    base_dir = tmp_path / "servers"
    # base_dir.mkdir()  Don't create the directory
    uuid = "some-uuid"
    version = [1, 2, 3]
    addon_name = "MyAddon"
    world_name = "test_world"

    mock_get_world_name.return_value = world_name

    with pytest.raises(OSError, match="Mocked makedirs error"):
        install_pack(
            pack_type,
            str(temp_dir),
            server_name,
            pack_file,
            str(base_dir),
            uuid,
            version,
            addon_name,
        )


@patch("shutil.copy2", side_effect=OSError("Mocked copy2 error"))
@patch("bedrock_server_manager.core.server.server.get_world_name")
@patch("bedrock_server_manager.core.server.addon._update_pack_json")
def test_install_pack_copy_files_error(
    mock_update_pack_json, mock_get_world_name, mock_copy, tmp_path
):
    """Test handling an error when copying files."""
    pack_type = "data"
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    (temp_dir / "some_file.txt").touch()  # file to copy
    server_name = "test_server"
    pack_file = "test.mcpack"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    uuid = "some-uuid"
    version = [1, 2, 3]
    addon_name = "MyAddon"
    world_name = "test_world"
    mock_get_world_name.return_value = world_name

    with pytest.raises(FileOperationError, match="Failed to copy behavior pack files"):
        install_pack(
            pack_type,
            str(temp_dir),
            server_name,
            pack_file,
            str(base_dir),
            uuid,
            version,
            addon_name,
        )


@patch("shutil.copytree", side_effect=OSError("Mocked copytree error"))
@patch("bedrock_server_manager.core.server.server.get_world_name")
@patch("bedrock_server_manager.core.server.addon._update_pack_json")
def test_install_pack_copy_tree_error(
    mock_update_pack_json, mock_get_world_name, mock_copy, tmp_path
):
    """Test handling an error when copying files."""
    pack_type = "data"
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    (temp_dir / "some_dir").mkdir()  # directory to copy
    server_name = "test_server"
    pack_file = "test.mcpack"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    uuid = "some-uuid"
    version = [1, 2, 3]
    addon_name = "MyAddon"
    world_name = "test_world"
    mock_get_world_name.return_value = world_name

    with pytest.raises(FileOperationError, match="Failed to copy behavior pack files"):
        install_pack(
            pack_type,
            str(temp_dir),
            server_name,
            pack_file,
            str(base_dir),
            uuid,
            version,
            addon_name,
        )


# --- Tests for _update_pack_json ---


def test_update_pack_json_adds_new_pack(tmp_path):
    """Test adding a new pack to an empty JSON file."""
    json_file = tmp_path / "world_behavior_packs.json"
    pack_id = "some-uuid"
    version = [1, 2, 3]

    _update_pack_json(str(json_file), pack_id, version)

    with open(json_file, "r") as f:
        data = json.load(f)
    expected_data = [{"pack_id": pack_id, "version": version}]
    assert data == expected_data


def test_update_pack_json_updates_existing_pack(tmp_path):
    """Test updating an existing pack with a newer version."""
    json_file = tmp_path / "world_behavior_packs.json"
    initial_data = [{"pack_id": "some-uuid", "version": [1, 0, 0]}]
    with open(json_file, "w") as f:
        json.dump(initial_data, f)

    pack_id = "some-uuid"
    new_version = [1, 2, 3]  # Newer version

    _update_pack_json(str(json_file), pack_id, new_version)

    with open(json_file, "r") as f:
        data = json.load(f)
    expected_data = [{"pack_id": pack_id, "version": new_version}]
    assert data == expected_data


def test_update_pack_json_does_not_update_existing_pack_older_version(tmp_path):
    """Test that an existing pack is NOT updated with an older version."""
    json_file = tmp_path / "world_behavior_packs.json"
    initial_data = [{"pack_id": "some-uuid", "version": [2, 0, 0]}]  # Existing newer
    with open(json_file, "w") as f:
        json.dump(initial_data, f)

    pack_id = "some-uuid"
    old_version = [1, 2, 3]  # Older version

    _update_pack_json(str(json_file), pack_id, old_version)

    with open(json_file, "r") as f:
        data = json.load(f)
    # Should remain unchanged
    assert data == initial_data


def test_update_pack_json_adds_multiple_packs(tmp_path):
    """Test adding multiple packs to the JSON file."""
    json_file = tmp_path / "world_behavior_packs.json"
    pack_id_1 = "uuid-1"
    version_1 = [1, 0, 0]
    pack_id_2 = "uuid-2"
    version_2 = [2, 1, 0]

    _update_pack_json(str(json_file), pack_id_1, version_1)
    _update_pack_json(str(json_file), pack_id_2, version_2)

    with open(json_file, "r") as f:
        data = json.load(f)
    expected_data = [
        {"pack_id": pack_id_1, "version": version_1},
        {"pack_id": pack_id_2, "version": version_2},
    ]
    assert data == expected_data


def test_update_pack_json_missing_json_file():
    """Test with a missing json_file argument."""
    with pytest.raises(MissingArgumentError, match="json_file is empty"):
        _update_pack_json("", "pack_id", [1, 2, 3])


def test_update_pack_json_missing_pack_id():
    """Test with a missing pack_id argument."""
    with pytest.raises(MissingArgumentError, match="pack_id is empty"):
        _update_pack_json("some_file.json", "", [1, 2, 3])


def test_update_pack_json_missing_version():
    """Test with a missing version argument."""
    with pytest.raises(MissingArgumentError, match="version is empty"):
        _update_pack_json("some_file.json", "pack_id", [])


@patch("builtins.open", side_effect=OSError("Mocked write error"))
def test_update_pack_json_file_write_error(mock_open, tmp_path):
    """Test handling a file write error."""
    json_file = tmp_path / "test.json"
    with pytest.raises(
        FileOperationError, match="Failed to initialize JSON file"
    ):  # Changed match
        _update_pack_json(str(json_file), "pack_id", [1, 2, 3])


def test_update_pack_json_invalid_json_in_existing_file(tmp_path):
    """Test handling invalid JSON in an existing file."""
    json_file = tmp_path / "world_behavior_packs.json"
    with open(json_file, "w") as f:
        f.write("This is not valid JSON")

    pack_id = "some-uuid"
    version = [1, 2, 3]

    _update_pack_json(str(json_file), pack_id, version)
    with open(json_file) as f:
        data = json.load(f)
    expected_data = [{"pack_id": pack_id, "version": version}]
    assert data == expected_data  # should have overwritten invalid json
