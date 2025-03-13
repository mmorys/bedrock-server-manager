# bedrock-server-manager/bedrock_server_manager/core/download/downloader.py
import re
import requests
import platform
import logging
import glob
import os
import zipfile
from bedrock_server_manager.config import settings
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.core.error import (
    DownloadExtractError,
    MissingArgumentError,
    InternetConnectivityError,
    FileOperationError,
    DirectoryError,
)

logger = logging.getLogger("bedrock_server_manager")


def lookup_bedrock_download_url(target_version):
    """Finds the Bedrock server download URL.

    Args:
        target_version (str): "LATEST", "PREVIEW", a specific version string
            (e.g., "1.20.1.2"), or a specific preview version string (e.g.,
            "1.20.1.2-preview").

    Returns:
        str: The download URL.

    Raises:
        MissingArgumentError: If target_version is empty.
        DownloadExtractError: If the URL cannot be found or there's an error fetching the page.
        OSError: If the operating system is unsupported.
    """
    download_page = "https://www.minecraft.net/en-us/download/server/bedrock"
    version_type = ""
    custom_version = ""
    if not target_version:
        raise MissingArgumentError(
            "lookup_bedrock_download_url: target_version is empty."
        )

    target_version_upper = target_version.upper()

    if target_version_upper == "PREVIEW":
        version_type = "PREVIEW"
        logger.info("Target version is 'preview'.")
    elif target_version_upper == "LATEST":
        version_type = "LATEST"
        logger.info("Target version is 'latest'.")
    elif target_version_upper.endswith("-PREVIEW"):
        version_type = "PREVIEW"
        custom_version = target_version[:-8]
        logger.info(f"Target version is a specific preview version: {custom_version}.")
    else:
        version_type = "LATEST"
        custom_version = target_version
        logger.info(f"Target version is a specific stable version: {custom_version}.")

    # OS-specific download URL regex
    if platform.system() == "Linux":
        if version_type == "PREVIEW":
            regex = (
                r'<a[^>]+href="([^"]+)"[^>]+data-platform="serverBedrockPreviewLinux"'
            )
        else:
            regex = r'<a[^>]+href="([^"]+)"[^>]+data-platform="serverBedrockLinux"'
    elif platform.system() == "Windows":
        if version_type == "PREVIEW":
            regex = (
                r'<a[^>]+href="([^"]+)"[^>]+data-platform="serverBedrockPreviewWindows"'
            )
        else:
            regex = r'<a[^>]+href="([^"]+)"[^>]+data-platform="serverBedrockWindows"'
    else:
        raise OSError("Unsupported operating system for server download.")

    try:
        headers = {
            "User-Agent": "zvortex11325/bedrock-server-manager",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept": "text/html",
        }
        response = requests.get(download_page, headers=headers, timeout=30)
        response.raise_for_status()
        download_page_content = response.text
    except requests.exceptions.RequestException as e:
        raise InternetConnectivityError(
            f"Failed to fetch download page content: {e}"
        ) from e

    match = re.search(regex, download_page_content)

    if match:
        resolved_download_url = match.group(1)
        if custom_version:
            # Construct custom URL by replacing the version number in the URL.
            resolved_download_url = re.sub(
                r"(bedrock-server-)[^/]+(\.zip)",
                rf"\g<1>{custom_version}\g<2>",
                resolved_download_url,
            )
        logger.info("Resolved download URL lookup OK.")
        return resolved_download_url
    else:
        raise DownloadExtractError(
            f"Could not find a valid download URL for {version_type}."
        )


def get_version_from_url(download_url):
    """Extracts the version from the download URL.

    Args:
        download_url (str): The Bedrock server download URL.

    Returns:
        str: The version string (e.g., "1.20.1.2").

    Raises:
        MissingArgumentError: If download_url is empty.
        DownloadExtractError: If the version cannot be extracted.
    """
    if not download_url:
        raise MissingArgumentError("get_version_from_url: download_url is empty.")

    match = re.search(r"bedrock-server-([0-9.]+)", download_url)
    if match:
        version = match.group(1)
        return version.rstrip(".")
    else:
        raise DownloadExtractError("Failed to extract version from URL.")


def prune_old_downloads(download_dir, download_keep):
    """Removes old downloaded server ZIP files, keeping the most recent ones.

    Args:
        download_dir (str): The directory where downloads are stored.
        download_keep (int): How many downloads to keep

    Raises:
        MissingArgumentError: If download_dir is empty.
        ValueError: If download_keep is not a valid integer.
        DirectoryError: If the download directory does not exist or is not a directory.
        FileOperationError: If there is an error deleting old downloads.
    """

    if not download_dir:
        raise MissingArgumentError("prune_old_downloads: download_dir is empty.")

    if not os.path.isdir(download_dir):
        logger.warning(
            f"prune_old_downloads: '{download_dir}' is not a directory or does not exist. Skipping cleanup."
        )
        raise DirectoryError

    logger.info("Cleaning up old Bedrock server downloads...")

    try:
        # Find all zip files and sort by modification time (oldest first)
        download_files = sorted(
            glob.glob(os.path.join(download_dir, "bedrock-server-*.zip")),
            key=os.path.getmtime,
        )

        logger.debug(f"Files found: {download_files} in Dir: {download_dir}")

        download_keep = int(download_keep)  # Could raise ValueError
        num_files = len(download_files)
        if num_files > download_keep:
            logger.debug(
                f"Found {num_files} old server downloads. Keeping the {download_keep} most recent."
            )
            files_to_delete = download_files[:-download_keep]
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    logger.debug(f"Deleted: {file_path}")
                except OSError as e:
                    raise FileOperationError(
                        f"Failed to delete old server download: {e}"
                    ) from e
            logger.info(f"Deleted {len(files_to_delete)} old server downloads.")
        else:
            logger.debug(
                f"Found {num_files} or fewer old server downloads. Keeping all."
            )
    except (OSError, ValueError) as e:
        raise FileOperationError(
            f"An error occurred while managing downloads: {e}"
        ) from e


def download_server_zip_file(download_url, zip_file):
    """Downloads the server ZIP file.

    Args:
        download_url (str): The URL to download from.
        zip_file (str): The path to save the downloaded file to.

    Raises:
        MissingArgumentError: If download_url or zip_file is empty.
        InternetConnectivityError: If there's an error during the download.
        FileOperationError: If there's an error writing to the file.
    """
    if not download_url:
        raise MissingArgumentError("download_server_zip_file: download_url is empty.")
    if not zip_file:
        raise MissingArgumentError("download_server_zip_file: zip_file is empty.")

    logger.info(f"Resolved download URL: {download_url}")

    try:
        headers = {"User-Agent": "zvortex11325/bedrock-server-manager"}
        response = requests.get(download_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()

        with open(zip_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Downloaded Bedrock server ZIP to: {zip_file}")
    except requests.exceptions.RequestException as e:
        raise InternetConnectivityError(
            f"Failed to download Bedrock server from {download_url}: {e}"
        ) from e
    except OSError as e:
        raise FileOperationError(f"Failed to write to ZIP file: {e}") from e
    except Exception as e:
        raise FileOperationError(
            f"An unexpected error occurred during download: {e}"
        ) from e


def extract_server_files_from_zip(zip_file, server_dir, in_update):
    """Extracts server files from the ZIP, handling updates correctly.

    Args:
        zip_file (str): Path to the ZIP file.
        server_dir (str): Directory to extract to.
        in_update (bool): True if this is an update, False for a fresh install.

    Raises:
        MissingArgumentError: If zip_file or server_dir is empty.
        FileOperationError: If the ZIP file does not exist or an error occurs.
        DownloadExtractError: If zip file is invalid
    """
    if not zip_file:
        raise MissingArgumentError("extract_server_files_from_zip: zip_file is empty.")
    if not server_dir:
        raise MissingArgumentError(
            "extract_server_files_from_zip: server_dir is empty."
        )

    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            if in_update:
                logger.info(
                    "Extracting server files (update), excluding critical files..."
                )
                files_to_exclude = {
                    "worlds/",
                    "allowlist.json",
                    "permissions.json",
                    "server.properties",
                }

                for zip_info in zip_ref.infolist():
                    normalized_filename = zip_info.filename.replace("\\", "/")
                    extract = True

                    for exclude_item in files_to_exclude:
                        if normalized_filename.startswith(exclude_item):
                            logger.debug(
                                f"Skipping extraction (excluded): {normalized_filename}"
                            )
                            extract = False
                            break

                    if extract:
                        target_path = os.path.join(server_dir, zip_info.filename)

                        if zip_info.is_dir():
                            os.makedirs(target_path, exist_ok=True)
                        else:
                            # Ensure the directory for the file exists:
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            zip_ref.extract(zip_info, server_dir)

            else:
                logger.info("Extracting server files for fresh installation...")
                zip_ref.extractall(server_dir)

        logger.info("Server files extracted successfully.")
    except zipfile.BadZipFile:
        raise DownloadExtractError(
            f"Failed to extract server files: {zip_file} is not a valid ZIP file."
        )
    except OSError as e:
        raise FileOperationError(f"Failed to extract server files: {e}") from e
    except Exception as e:
        raise FileOperationError(f"A unexpected error has occurred: {e}") from e


def download_bedrock_server(server_dir, target_version="LATEST"):
    """Downloads and installs the Bedrock server.

    Args:
        server_dir (str): The directory of the server.
        target_version (str): "LATEST", "PREVIEW", or a specific version.

    Returns:
        tuple: (version, zip_file, download_dir) on success.

    Raises:
        MissingArgumentError: If server_dir is empty.
        InternetConnectivityError: If there's no internet connection.
        DownloadExtractError: If the download URL cannot be found or version cannot be extracted.
        FileOperationError: If directories cannot be created or file download fails.
    """

    if not server_dir:
        raise MissingArgumentError("download_bedrock_server: server_dir is empty.")

    system_base.check_internet_connectivity()  # Raises exception on failure
    logger.info(f"Requested server version: {target_version}")

    download_dir = settings.DOWNLOAD_DIR

    try:
        os.makedirs(server_dir, exist_ok=True)
        os.makedirs(download_dir, exist_ok=True)
    except OSError as e:
        raise FileOperationError(f"Failed to create directories: {e}") from e

    download_url = lookup_bedrock_download_url(target_version)
    current_version = get_version_from_url(download_url)

    if target_version.upper() == "LATEST":
        download_dir = os.path.join(download_dir, "stable")
    elif target_version.upper() == "PREVIEW":
        download_dir = os.path.join(download_dir, "preview")

    try:
        os.makedirs(download_dir, exist_ok=True)
    except OSError as e:
        raise FileOperationError(f"Failed to create download subdirectory: {e}") from e

    zip_file = os.path.join(download_dir, f"bedrock-server-{current_version}.zip")

    if not os.path.exists(zip_file):
        logger.info("Server ZIP not found. Proceeding with download.")
        download_server_zip_file(download_url, zip_file)  # Raises exception on failure
    else:
        logger.info(
            f"Bedrock server version {current_version} is already downloaded. Skipping download."
        )

    return current_version, zip_file, download_dir
