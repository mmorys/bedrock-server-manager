# bedrock-server-manager/tests/core/download/test_downloader.py
import pytest
import os
import zipfile
import time
import requests
from unittest.mock import patch, MagicMock, mock_open, call
from bedrock_server_manager.core.download import downloader
from bedrock_server_manager.core.error import (
    DownloadExtractError,
    MissingArgumentError,
    InternetConnectivityError,
    FileOperationError,
    DirectoryError,
)

# --- Tests for download_file ---


@patch("requests.get")
def test_download_server_zip_file_successful(mock_get, tmp_path):
    """Test successful download of the server ZIP file."""
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [
        b"mock zip data"
    ]  # Simulate file content
    mock_response.raise_for_status.return_value = None  # No HTTP errors
    mock_get.return_value = mock_response

    download_url = "http://example.com/bedrock-server.zip"
    zip_file = tmp_path / "bedrock-server.zip"

    downloader.download_server_zip_file(
        download_url, str(zip_file)
    )  # Convert Path to string

    assert zip_file.exists()  # Check if the file was created
    assert zip_file.read_bytes() == b"mock zip data"  # Check file content
    mock_get.assert_called_once_with(
        download_url,
        headers={"User-Agent": "zvortex11325/bedrock-server-manager"},
        stream=True,
        timeout=30,
    )


@patch("requests.get")
def test_download_server_zip_file_download_error(mock_get):
    """Test handling of a download error (e.g., network issue)."""
    mock_get.side_effect = requests.exceptions.RequestException("Mocked download error")

    download_url = "http://example.com/bedrock-server.zip"
    zip_file = "dummy_file.zip"  # File path doesn't matter for this test

    with pytest.raises(
        InternetConnectivityError, match="Failed to download Bedrock server"
    ):
        downloader.download_server_zip_file(download_url, zip_file)


@patch("requests.get")
def test_download_server_zip_file_http_error(mock_get, tmp_path):
    """Test handling of an HTTP error (e.g., 404 Not Found)."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "Mocked HTTP error"
    )
    mock_get.return_value = mock_response

    download_url = "http://example.com/bedrock-server.zip"
    zip_file = tmp_path / "bedrock-server.zip"  # file path matters for the open

    with pytest.raises(
        InternetConnectivityError, match="Failed to download Bedrock server"
    ):
        downloader.download_server_zip_file(download_url, str(zip_file))


@patch("builtins.open", side_effect=OSError("Mocked file write error"))
@patch("requests.get")
def test_download_server_zip_file_write_error(mock_get, mock_open, tmp_path):
    """Test handling of a file write error."""
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [
        b"mock zip data"
    ]  # Simulate file content
    mock_response.raise_for_status.return_value = None  # No HTTP errors
    mock_get.return_value = mock_response

    download_url = "http://example.com/bedrock-server.zip"
    zip_file = tmp_path / "bedrock-server.zip"

    with pytest.raises(FileOperationError, match="Failed to write to ZIP file"):
        downloader.download_server_zip_file(download_url, str(zip_file))


def test_download_server_zip_file_missing_url():
    """Test with a missing download URL."""
    with pytest.raises(MissingArgumentError, match="download_url is empty"):
        downloader.download_server_zip_file("", "dummy_file.zip")


def test_download_server_zip_file_missing_filepath():
    """Test with a missing file path."""
    with pytest.raises(MissingArgumentError, match="zip_file is empty"):
        downloader.download_server_zip_file("http://example.com", "")


# --- Tests for extract_server_files_from_zip ---


@patch("zipfile.ZipFile")
def test_extract_server_files_from_zip_fresh_install(mock_zipfile, tmp_path):
    """Test extraction for a fresh server installation (not an update)."""
    mock_zip_instance = (
        mock_zipfile.return_value.__enter__.return_value
    )  # Instance of ZipFile
    mock_zip_instance.infolist.return_value = []  # No files

    zip_file = str(tmp_path / "bedrock-server.zip")  # Dummy path, file doesn't exist
    server_dir = str(tmp_path / "server")

    downloader.extract_server_files_from_zip(zip_file, server_dir, in_update=False)
    mock_zipfile.assert_called_once_with(zip_file, "r")
    mock_zip_instance.extractall.assert_called_once_with(server_dir)
    mock_zip_instance.infolist.assert_not_called()  # Shouldnt be called


@patch("zipfile.ZipFile")
def test_extract_server_files_from_zip_update(mock_zipfile, tmp_path):
    """Test extraction during an update (excluding specific files)."""
    # Create mock ZipInfo objects to simulate files in the ZIP
    mock_zip_info_1 = MagicMock(spec=zipfile.ZipInfo)
    mock_zip_info_1.filename = "worlds/world1/db/somefile.txt"
    mock_zip_info_1.is_dir.return_value = False

    mock_zip_info_2 = MagicMock(spec=zipfile.ZipInfo)
    mock_zip_info_2.filename = "server.properties"
    mock_zip_info_2.is_dir.return_value = False

    mock_zip_info_3 = MagicMock(spec=zipfile.ZipInfo)
    mock_zip_info_3.filename = "new_file.txt"  # Should be extracted
    mock_zip_info_3.is_dir.return_value = False

    mock_zip_info_4 = MagicMock(spec=zipfile.ZipInfo)
    mock_zip_info_4.filename = "bin/bedrock_server"  # Should be extracted
    mock_zip_info_4.is_dir.return_value = False

    mock_zip_info_5 = MagicMock(spec=zipfile.ZipInfo)
    mock_zip_info_5.filename = "a_directory/"  # Should be extracted
    mock_zip_info_5.is_dir.return_value = True

    # Mock the ZipFile instance and its methods
    mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
    mock_zip_instance.infolist.return_value = [
        mock_zip_info_1,
        mock_zip_info_2,
        mock_zip_info_3,
        mock_zip_info_4,
        mock_zip_info_5,
    ]
    mock_zip_instance.extract.return_value = None

    zip_file = str(tmp_path / "bedrock-server.zip")
    server_dir = str(tmp_path / "server")
    with patch("os.makedirs") as mock_makedirs:
        downloader.extract_server_files_from_zip(zip_file, server_dir, in_update=True)

        mock_zipfile.assert_called_once_with(zip_file, "r")
        mock_zip_instance.extractall.assert_not_called()  # extractall should not be called
        mock_zip_instance.extract.assert_has_calls(
            [
                call(
                    mock_zip_info_3, server_dir
                ),  # Only new_file.txt should be extracted
                call(mock_zip_info_4, server_dir),
            ]
        )
        mock_makedirs.assert_called()


def test_extract_server_files_from_zip_missing_zip_file():
    """Test with a missing ZIP file path."""
    with pytest.raises(MissingArgumentError, match="zip_file is empty"):
        downloader.extract_server_files_from_zip("", "server_dir", False)


def test_extract_server_files_from_zip_missing_server_dir():
    """Test with a missing server directory path."""
    with pytest.raises(MissingArgumentError, match="server_dir is empty"):
        downloader.extract_server_files_from_zip("zip_file.zip", "", False)


def test_extract_server_files_from_zip_zip_file_not_found(tmp_path):
    """Test with a ZIP file that doesn't exist."""
    zip_file = str(tmp_path / "nonexistent.zip")  # File doesn't exist
    server_dir = str(tmp_path / "server")
    with pytest.raises(FileOperationError, match="Failed to extract server files"):
        downloader.extract_server_files_from_zip(zip_file, server_dir, False)


@patch("zipfile.ZipFile", side_effect=zipfile.BadZipFile)
def test_extract_server_files_from_zip_invalid_zip(mock_zipfile, tmp_path):
    """Test with an invalid ZIP file."""
    zip_file = str(
        tmp_path / "bedrock-server.zip"
    )  # Dummy path, file doesn't need to exist
    server_dir = str(tmp_path / "server")

    with pytest.raises(DownloadExtractError, match="is not a valid ZIP file"):
        downloader.extract_server_files_from_zip(zip_file, server_dir, False)


@patch("zipfile.ZipFile")
def test_extract_server_files_from_zip_os_error(mock_zipfile, tmp_path):
    """Test for OSError during extraction (e.g., permissions issue)."""

    # Simulate an OSError during extraction
    mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
    mock_zip_instance.extractall.side_effect = OSError("Mocked extraction error")
    mock_zip_instance.extract.side_effect = OSError("Mocked extraction error")

    zip_file = str(tmp_path / "bedrock-server.zip")  # path doesnt have to exist
    server_dir = str(tmp_path / "server")

    with pytest.raises(FileOperationError, match="Failed to extract server files"):
        downloader.extract_server_files_from_zip(zip_file, server_dir, False)


# --- Tests for prune_old_downloads ---


def test_prune_old_downloads_deletes_old_files(tmp_path):
    """Test deleting old downloads, keeping the specified number."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    download_keep = 2

    # Create some dummy files with different timestamps
    for i in range(4):
        file_path = download_dir / f"bedrock-server-{i}.zip"
        file_path.touch()
        time.sleep(0.1)  # Ensure different modification times

    downloader.prune_old_downloads(str(download_dir), download_keep)

    remaining_files = sorted([f.name for f in download_dir.iterdir()])
    assert remaining_files == ["bedrock-server-2.zip", "bedrock-server-3.zip"]


def test_prune_old_downloads_keeps_all_files(tmp_path):
    """Test when the number of files is less than download_keep."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    download_keep = 5

    for i in range(3):
        file_path = download_dir / f"bedrock-server-{i}.zip"
        file_path.touch()

    downloader.prune_old_downloads(str(download_dir), download_keep)

    remaining_files = sorted([f.name for f in download_dir.iterdir()])
    assert remaining_files == [
        "bedrock-server-0.zip",
        "bedrock-server-1.zip",
        "bedrock-server-2.zip",
    ]


def test_prune_old_downloads_empty_directory(tmp_path):
    """Test with an empty download directory."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    download_keep = 3

    downloader.prune_old_downloads(str(download_dir), download_keep)
    assert len(list(download_dir.iterdir())) == 0  # Directory should still be empty


def test_prune_old_downloads_missing_directory(tmp_path):
    """Test with a directory that doesn't exist (should raise an error)."""
    download_dir = tmp_path / "nonexistent_dir"  # Doesn't exist
    download_keep = 3

    with pytest.raises(DirectoryError):
        # Should raise an exception.
        downloader.prune_old_downloads(str(download_dir), download_keep)


def test_prune_old_downloads_missing_download_dir():
    """Test with an empty download_dir argument."""
    with pytest.raises(MissingArgumentError, match="download_dir is empty"):
        downloader.prune_old_downloads("", 3)


def test_prune_old_downloads_invalid_download_keep(tmp_path):
    """Test passing an invalid value for download_keep (ValueError)."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    download_keep = "invalid"  # Not an integer
    with pytest.raises(FileOperationError):
        downloader.prune_old_downloads(str(download_dir), download_keep)


@patch("os.remove", side_effect=OSError("Mocked remove error"))
def test_prune_old_downloads_deletion_error(mock_remove, tmp_path):
    """Test handling of an error during file deletion."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    download_keep = 1

    # Create some dummy files
    for i in range(3):
        file_path = download_dir / f"bedrock-server-{i}.zip"
        file_path.touch()

    with pytest.raises(
        FileOperationError, match="Failed to delete old server download"
    ):
        downloader.prune_old_downloads(str(download_dir), download_keep)


# --- Tests for get_version_from_url ---


def test_get_version_from_url_valid_url():
    """Test extracting the version from a valid download URL."""
    download_url = (
        "https://minecraft.azureedge.net/bin-linux/bedrock-server-1.20.1.2.zip"
    )
    expected_version = "1.20.1.2"
    assert downloader.get_version_from_url(download_url) == expected_version


def test_get_version_from_url_url_with_trailing_period():
    """Test a URL where the version string ends with a period."""
    download_url = "https://example.com/bedrock-server-1.20.1.2..zip"
    expected_version = "1.20.1.2"  # Should still extract correctly
    assert downloader.get_version_from_url(download_url) == expected_version


def test_get_version_from_url_missing_url():
    """Test with a missing download URL."""
    with pytest.raises(MissingArgumentError, match="download_url is empty"):
        downloader.get_version_from_url("")


def test_get_version_from_url_invalid_url_format():
    """Test with a URL that doesn't match the expected format."""
    download_url = "https://example.com/some_other_file.zip"  # No version
    with pytest.raises(
        DownloadExtractError, match="Failed to extract version from URL"
    ):
        downloader.get_version_from_url(download_url)


def test_get_version_from_url_url_with_different_prefix():
    """Test a URL with a different prefix but still containing the version."""
    download_url = "https://some-cdn.net/files/bedrock-server-1.19.80.23.zip"
    expected_version = "1.19.80.23"
    assert downloader.get_version_from_url(download_url) == expected_version


# --- Tests for lookup_bedrock_download_url ---


@patch("requests.get")
def test_lookup_bedrock_download_url_latest_linux(mock_get):
    """Test finding the latest download URL for Linux."""
    mock_response = MagicMock()
    # Simulate the HTML content of the download page
    mock_response.text = """
    <html>
    <a href="https://example.com/latest-linux" data-platform="serverBedrockLinux">Latest Linux</a>
    </html>
    """
    mock_response.raise_for_status.return_value = None  # no errors
    mock_get.return_value = mock_response

    with patch("platform.system", return_value="Linux"):
        url = downloader.lookup_bedrock_download_url("LATEST")
        assert url == "https://example.com/latest-linux"
        mock_get.assert_called_once_with(
            "https://www.minecraft.net/en-us/download/server/bedrock",
            headers={
                "User-Agent": "zvortex11325/bedrock-server-manager",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept": "text/html",
            },
            timeout=30,
        )


@patch("requests.get")
def test_lookup_bedrock_download_url_preview_windows(mock_get):
    """Test finding the preview download URL for Windows."""
    mock_response = MagicMock()
    mock_response.text = """
    <html>
    <a href="https://example.com/preview-windows" data-platform="serverBedrockPreviewWindows">Preview Windows</a>
    </html>
    """
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    with patch("platform.system", return_value="Windows"):
        url = downloader.lookup_bedrock_download_url("PREVIEW")
        assert url == "https://example.com/preview-windows"


@patch("requests.get")
def test_lookup_bedrock_download_url_specific_version_linux(mock_get):
    """Test with a specific version (Linux)."""
    mock_response = MagicMock()
    # Simulate a URL that contains the version number
    mock_response.text = """
        <html>
        <a href="https://example.com/bedrock-server-1.2.3.4.zip" data-platform="serverBedrockLinux">Latest Linux</a>
        </html>
        """
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    with patch("platform.system", return_value="Linux"):
        url = downloader.lookup_bedrock_download_url("1.2.3.4")
        # URL should be updated with new version number
        assert url == "https://example.com/bedrock-server-1.2.3.4.zip"


@patch("requests.get")
def test_lookup_bedrock_download_url_specific_preview_version_windows(mock_get):
    """Test with a specific preview version (Windows)."""
    mock_response = MagicMock()
    mock_response.text = """
        <html><a href="https://example.com/bedrock-server-9.9.9.9.zip" data-platform="serverBedrockPreviewWindows">Preview</a></html>
        """
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    with patch("platform.system", return_value="Windows"):
        url = downloader.lookup_bedrock_download_url(
            "5.6.7.8-preview"
        )  # Request 5.6.7.8
        assert url == "https://example.com/bedrock-server-5.6.7.8.zip"


def test_lookup_bedrock_download_url_missing_target_version():
    """Test with a missing target_version."""
    with pytest.raises(MissingArgumentError, match="target_version is empty"):
        downloader.lookup_bedrock_download_url("")


@patch("requests.get")
def test_lookup_bedrock_download_url_download_page_fetch_error(mock_get):
    """Test handling of an error fetching the download page."""
    mock_get.side_effect = requests.exceptions.RequestException("Mocked download error")

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(
            InternetConnectivityError, match="Failed to fetch download page content"
        ):
            downloader.lookup_bedrock_download_url("LATEST")


@patch("requests.get")
def test_lookup_bedrock_download_url_url_not_found(mock_get):
    """Test when the download URL cannot be found on the page."""
    mock_response = MagicMock()
    mock_response.text = (
        "<html><body>No download links here.</body></html>"  # No matching links
    )
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    with patch("platform.system", return_value="Windows"):
        with pytest.raises(
            DownloadExtractError, match="Could not find a valid download URL"
        ):
            downloader.lookup_bedrock_download_url("LATEST")


@patch("requests.get")
def test_lookup_bedrock_download_url_http_error(mock_get):
    """Test for an HTTP error (e.g., 404) while fetching the download page."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "Mocked HTTP error"
    )
    mock_get.return_value = mock_response

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(InternetConnectivityError):
            downloader.lookup_bedrock_download_url("LATEST")


@patch("platform.system", return_value="UnsupportedOS")
def test_lookup_bedrock_download_url_unsupported_os(mock_get):
    """Test behavior with an unsupported operating system."""
    with pytest.raises(OSError, match="Unsupported operating system"):
        downloader.lookup_bedrock_download_url("LATEST")
