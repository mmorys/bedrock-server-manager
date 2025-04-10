# bedrock-server-manager/bedrock_server_manager/core/download/downloader.py
"""
Handles downloading, extracting, and managing Minecraft Bedrock Server files.

This module provides functions to:
- Find the correct download URL for stable or preview versions from minecraft.net.
- Extract version information from download URLs.
- Download the server ZIP archive.
- Extract the server files, optionally excluding configuration/world data during updates.
- Prune old downloaded ZIP archives based on configured retention settings.
- Coordinate the overall download and setup process for a server directory.
"""

import re
import requests
import platform
import logging
import os
import zipfile
from typing import Tuple

# Local imports
from bedrock_server_manager.config.settings import settings, app_name
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.error import (
    DownloadExtractError,
    MissingArgumentError,
    InternetConnectivityError,
    FileOperationError,
    DirectoryError,
)

logger = logging.getLogger("bedrock_server_manager")


def lookup_bedrock_download_url(target_version: str) -> str:
    """
    Finds the download URL for a specific or latest Bedrock server version.

    Scrapes the official Minecraft download page to find the URL matching
    the specified version and operating system.

    Args:
        target_version: The desired version identifier:
            - "LATEST": Finds the URL for the latest stable release.
            - "PREVIEW": Finds the URL for the latest preview release.
            - "X.Y.Z.W": Finds the URL for a specific stable version number.
            - "X.Y.Z.W-PREVIEW": Finds the URL for a specific preview version number.

    Returns:
        The direct download URL string for the server ZIP file.

    Raises:
        MissingArgumentError: If `target_version` is None or empty.
        OSError: If the host operating system (platform.system()) is not 'Linux' or 'Windows'.
        InternetConnectivityError: If fetching the download page fails (network error, timeout).
        DownloadExtractError: If the appropriate download link cannot be found on the page
                               or if constructing a specific version URL fails.
    """
    download_page = "https://www.minecraft.net/en-us/download/server/bedrock"
    version_type = ""
    custom_version = ""

    if not target_version:
        raise MissingArgumentError("Target version cannot be empty for lookup.")
    logger.debug(f"Looking up download URL for target version: '{target_version}'")

    target_version_upper = target_version.strip().upper()

    # Determine version type (LATEST/PREVIEW) and specific version number if provided
    if target_version_upper == "PREVIEW":
        version_type = "PREVIEW"
        logger.info("Searching for the latest PREVIEW version URL.")
    elif target_version_upper == "LATEST":
        version_type = "LATEST"
        logger.info("Searching for the latest STABLE version URL.")
    elif target_version_upper.endswith("-PREVIEW"):
        version_type = "PREVIEW"
        # Extract the version number part (e.g., "1.20.1.2" from "1.20.1.2-PREVIEW")
        custom_version = target_version[: -len("-PREVIEW")]
        logger.info(f"Searching for specific PREVIEW version URL: {custom_version}.")
    else:
        version_type = "LATEST"
        custom_version = target_version  # Assumes it's a specific stable version number
        logger.info(f"Searching for specific STABLE version URL: {custom_version}.")

    # Determine the correct regex based on OS and version type
    os_name = platform.system()
    logger.debug(f"Detected operating system: {os_name}")
    if os_name == "Linux":
        if version_type == "PREVIEW":
            regex = (
                r'<a[^>]+href="([^"]+)"[^>]+data-platform="serverBedrockPreviewLinux"'
            )
        else:  # LATEST or specific stable
            regex = r'<a[^>]+href="([^"]+)"[^>]+data-platform="serverBedrockLinux"'
    elif os_name == "Windows":
        if version_type == "PREVIEW":
            regex = (
                r'<a[^>]+href="([^"]+)"[^>]+data-platform="serverBedrockPreviewWindows"'
            )
        else:  # LATEST or specific stable
            regex = r'<a[^>]+href="([^"]+)"[^>]+data-platform="serverBedrockWindows"'
    else:
        logger.error(
            f"Unsupported operating system '{os_name}' for Bedrock server download."
        )
        raise OSError(
            f"Unsupported operating system for Bedrock server download: {os_name}"
        )

    # Fetch the download page content
    try:
        headers = {
            "User-Agent": f"zvortex11325/{app_name}",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept": "text/html",
        }
        logger.debug(f"Requesting URL: {download_page} with headers: {headers}")
        response = requests.get(download_page, headers=headers, timeout=30)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
        download_page_content = response.text
        logger.debug(
            f"Successfully fetched download page (status {response.status_code}), content length: {len(download_page_content)} bytes."
        )
    except requests.exceptions.RequestException as e:
        logger.error(
            f"Failed to fetch Minecraft download page '{download_page}': {e}",
            exc_info=True,
        )
        raise InternetConnectivityError(
            f"Failed to fetch download page '{download_page}': {e}"
        ) from e

    # Search for the download URL using the regex
    match = re.search(regex, download_page_content)

    if match:
        base_download_url = match.group(1)
        logger.debug(f"Found base download URL via regex: {base_download_url}")

        if custom_version:
            # If a specific version was requested, attempt to modify the found URL
            try:
                # Regex breakdown:
                # (bedrock-server-) : Group 1 - Match the prefix literally
                # [0-9.]+?         : Match one or more digits or dots (non-greedy) - the version part
                # (\.zip)          : Group 2 - Match the .zip suffix literally
                modified_url = re.sub(
                    r"(bedrock-server-)[0-9.]+?(\.zip)",
                    rf"\g<1>{custom_version}\g<2>",  # Replace version part with custom_version
                    base_download_url,
                    count=1,  # Only replace the first occurrence
                )
                if modified_url == base_download_url:  # Check if substitution happened
                    logger.warning(
                        f"Could not substitute version '{custom_version}' into base URL '{base_download_url}'. Regex might need update."
                    )
                    raise DownloadExtractError(
                        f"Failed to construct URL for specific version '{custom_version}'."
                    )
                resolved_download_url = modified_url
                logger.info(
                    f"Constructed specific version URL: {resolved_download_url}"
                )
            except Exception as e:
                logger.error(
                    f"Error constructing URL for specific version '{custom_version}': {e}",
                    exc_info=True,
                )
                raise DownloadExtractError(
                    f"Error constructing URL for specific version '{custom_version}': {e}"
                ) from e
        else:
            # Use the URL found directly (LATEST or PREVIEW)
            resolved_download_url = base_download_url
            logger.debug(
                f"Using latest {version_type} download URL found: {resolved_download_url}"
            )

        return resolved_download_url
    else:
        # If no match found with the regex
        error_msg = f"Could not find a download URL matching OS '{os_name}' and version type '{version_type}' on page {download_page}."
        logger.error(error_msg + " The website structure may have changed.")
        raise DownloadExtractError(
            error_msg + " Please check the website or report an issue."
        )


def get_version_from_url(download_url: str) -> str:
    """
    Extracts the Bedrock server version string from its download URL.

    Args:
        download_url: The full download URL string.

    Returns:
        The version string (e.g., "1.20.1.2") extracted from the URL.

    Raises:
        MissingArgumentError: If `download_url` is None or empty.
        DownloadExtractError: If the version number cannot be parsed from the URL format.
    """
    if not download_url:
        raise MissingArgumentError("Download URL cannot be empty to extract version.")

    # Regex: Find 'bedrock-server-' followed by digits and dots, capture the version part.
    match = re.search(r"bedrock-server-([0-9.]+)\.zip", download_url)
    if match:
        version = match.group(1)
        # Clean up trailing dots if any (though unlikely with current URL format)
        cleaned_version = version.rstrip(".")
        logger.debug(f"Extracted version '{cleaned_version}' from URL: {download_url}")
        return cleaned_version
    else:
        error_msg = f"Failed to extract version number from URL format: {download_url}"
        logger.error(error_msg)
        raise DownloadExtractError(error_msg + " URL structure might be unexpected.")


def prune_old_downloads(download_dir: str, download_keep: int) -> None:
    """
    Removes the oldest downloaded server ZIP files, keeping a specified number.

    Args:
        download_dir: The directory containing the downloaded 'bedrock-server-*.zip' files.
        download_keep: The number of most recent ZIP files to retain.

    Raises:
        MissingArgumentError: If `download_dir` is None or empty.
        ValueError: If `download_keep` cannot be converted to a valid integer >= 0.
        DirectoryError: If `download_dir` does not exist or is not a directory.
        FileOperationError: If there's an error accessing files or deleting an old download.
    """
    if not download_dir:
        raise MissingArgumentError("Download directory cannot be empty for pruning.")

    try:
        download_keep = int(download_keep)
        if download_keep < 0:
            raise ValueError("Number of downloads to keep cannot be negative.")
        logger.debug(
            f"Configured to keep {download_keep} downloads in '{download_dir}'."
        )
    except ValueError as e:
        logger.error(
            f"Invalid value for downloads to keep: '{download_keep}'. Must be an integer >= 0."
        )
        raise ValueError(f"Invalid value for downloads to keep: {e}") from e

    if not os.path.isdir(download_dir):
        error_msg = f"Download directory '{download_dir}' does not exist or is not a directory. Cannot prune."
        logger.error(error_msg)
        raise DirectoryError(error_msg)

    logger.info(
        f"Pruning old Bedrock server downloads in '{download_dir}' (keeping {download_keep})..."
    )

    try:
        # Find all bedrock-server zip files in the specified directory
        from pathlib import Path

        dir_path = Path(download_dir)
        download_files = list(dir_path.glob("bedrock-server-*.zip"))

        # Sort files by modification time (oldest first)
        download_files.sort(key=lambda p: p.stat().st_mtime)

        logger.debug(
            f"Found {len(download_files)} potential download files matching pattern."
        )
        # Log found files at debug level if needed:
        # for f in download_files: logger.debug(f" - Found: {f}")

        num_files = len(download_files)
        if num_files > download_keep:
            num_to_delete = num_files - download_keep
            files_to_delete = download_files[:num_to_delete]  # Get the oldest ones
            logger.info(
                f"Found {num_files} downloads. Will delete {num_to_delete} oldest file(s) to keep {download_keep}."
            )

            deleted_count = 0
            for file_path in files_to_delete:
                try:
                    file_path.unlink()  # Use pathlib's unlink
                    logger.info(f"Deleted old download: {file_path}")
                    deleted_count += 1
                except OSError as e:
                    logger.error(
                        f"Failed to delete old server download '{file_path}': {e}",
                        exc_info=True,
                    )
                    # Continue trying to delete others, but report the failure
            if deleted_count < num_to_delete:
                # If some deletions failed, raise an error after trying all
                raise FileOperationError(
                    f"Failed to delete all required old downloads ({num_to_delete - deleted_count} failed). Check logs."
                )

            logger.info(f"Successfully deleted {deleted_count} old download(s).")
        else:
            logger.info(
                f"Found {num_files} download(s), which is not more than the {download_keep} to keep. No files deleted."
            )

    except OSError as e:
        logger.error(
            f"OS error occurred while accessing or pruning downloads in '{download_dir}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Error pruning downloads in '{download_dir}': {e}"
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error occurred while pruning downloads: {e}", exc_info=True
        )
        raise FileOperationError(f"Unexpected error pruning downloads: {e}") from e


def download_server_zip_file(download_url: str, zip_file: str) -> None:
    """
    Downloads a file from a URL and saves it locally, streaming the content.

    Args:
        download_url: The URL of the file to download.
        zip_file: The full local path where the downloaded file should be saved.

    Raises:
        MissingArgumentError: If `download_url` or `zip_file` is None or empty.
        InternetConnectivityError: If the download request fails (network error, timeout, bad status).
        FileOperationError: If the file cannot be opened or written to locally.
    """
    if not download_url:
        raise MissingArgumentError("Download URL cannot be empty for downloading.")
    if not zip_file:
        raise MissingArgumentError("Target file path cannot be empty for downloading.")

    logger.info(f"Attempting to download server from: {download_url}")
    logger.debug(f"Saving downloaded file to: {zip_file}")

    # Ensure target directory exists
    target_dir = os.path.dirname(zip_file)
    try:
        if (
            target_dir
        ):  # Handle case where zip_file might be in current dir (no dirname)
            os.makedirs(target_dir, exist_ok=True)
            logger.debug(f"Ensured target directory exists: {target_dir}")
    except OSError as e:
        logger.error(
            f"Failed to create target directory '{target_dir}' for download: {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Cannot create directory '{target_dir}' for download: {e}"
        ) from e

    try:
        headers = {
            "User-Agent": f"Python Requests/{requests.__version__} ({app_name})"
        }  # Simple UA
        # Use stream=True to download large files efficiently without loading into memory
        with requests.get(
            download_url, headers=headers, stream=True, timeout=60
        ) as response:  # Increased timeout
            response.raise_for_status()  # Check for HTTP errors
            logger.debug(
                f"Download request successful (status {response.status_code}). Starting file write."
            )

            total_size = int(response.headers.get("content-length", 0))
            bytes_written = 0
            # Write the content to the file in chunks
            with open(zip_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):  # 8KB chunks
                    f.write(chunk)
                    bytes_written += len(chunk)
                    # if bytes_written % (1024*1024) == 0: logger.debug(f"Downloaded {bytes_written // (1024*1024)} MB...")

            logger.info(f"Successfully downloaded {bytes_written} bytes to: {zip_file}")
            if total_size != 0 and bytes_written != total_size:
                logger.warning(
                    f"Downloaded size ({bytes_written}) does not match content-length header ({total_size}). File might be incomplete."
                )

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Failed to download Bedrock server from '{download_url}': {e}",
            exc_info=True,
        )
        # Clean up potentially partial file
        if os.path.exists(zip_file):
            try:
                os.remove(zip_file)
                logger.debug(f"Removed potentially incomplete file: {zip_file}")
            except OSError as rm_err:
                logger.warning(
                    f"Could not remove incomplete file '{zip_file}': {rm_err}"
                )
        raise InternetConnectivityError(
            f"Download failed for '{download_url}': {e}"
        ) from e
    except OSError as e:
        logger.error(
            f"Failed to write downloaded content to file '{zip_file}': {e}",
            exc_info=True,
        )
        raise FileOperationError(f"Cannot write to file '{zip_file}': {e}") from e
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during download or file writing: {e}",
            exc_info=True,
        )
        raise FileOperationError(f"Unexpected error during download: {e}") from e


def extract_server_files_from_zip(
    zip_file: str, server_dir: str, is_update: bool
) -> None:
    """
    Extracts files from the downloaded server ZIP archive into the target directory.

    If `is_update` is True, it avoids overwriting specific configuration files
    and the 'worlds' directory to preserve user data.

    Args:
        zip_file: The path to the downloaded Bedrock server ZIP file.
        server_dir: The target directory where server files should be extracted.
        is_update: Boolean flag. If True, performs an update extraction (skipping
                   certain files/dirs). If False, extracts everything (fresh install).

    Raises:
        MissingArgumentError: If `zip_file` or `server_dir` is None or empty.
        FileNotFoundError: If the specified `zip_file` does not exist.
        DownloadExtractError: If `zip_file` is not a valid ZIP archive (e.g., corrupted).
        FileOperationError: If an OS error occurs during directory creation or file extraction.
    """
    if not zip_file:
        raise MissingArgumentError("ZIP file path cannot be empty for extraction.")
    if not server_dir:
        raise MissingArgumentError(
            "Target server directory cannot be empty for extraction."
        )

    logger.debug(f"Extracting server files from '{zip_file}' to '{server_dir}'...")
    logger.debug(
        f"Extraction mode: {'Update (preserving config/worlds)' if is_update else 'Fresh install (extracting all)'}"
    )

    if not os.path.exists(zip_file):
        error_msg = f"Cannot extract: ZIP file not found at '{zip_file}'."
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    # Ensure target directory exists before extraction
    try:
        os.makedirs(server_dir, exist_ok=True)
        logger.debug(f"Ensured target server directory exists: {server_dir}")
    except OSError as e:
        logger.error(
            f"Failed to create target server directory '{server_dir}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Cannot create target directory '{server_dir}': {e}"
        ) from e

    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            if is_update:
                # Define items to preserve (relative paths within the zip)
                # Using forward slashes for cross-platform zip path consistency
                files_to_exclude = {
                    "worlds/",  # Exclude the entire worlds directory
                    "allowlist.json",
                    "permissions.json",
                    "server.properties",
                }
                logger.debug(
                    f"Update mode: Excluding extraction of items matching: {files_to_exclude}"
                )

                extracted_count = 0
                skipped_count = 0
                for member in zip_ref.infolist():
                    # Normalize path separators from zip file
                    member_path = member.filename.replace("\\", "/")
                    should_extract = True

                    # Check if the member path starts with any of the exclusion paths
                    for exclude_item in files_to_exclude:
                        if member_path == exclude_item or member_path.startswith(
                            exclude_item
                        ):
                            logger.debug(
                                f"Skipping extraction of preserved item: {member_path}"
                            )
                            should_extract = False
                            skipped_count += 1
                            break

                    if should_extract:
                        # Perform extraction
                        # zipfile handles directory creation implicitly for file members
                        zip_ref.extract(member, path=server_dir)
                        extracted_count += 1
                        # Reduced verbosity: Log only occasionally or summary after loop
                        # logger.debug(f"Extracted: {os.path.join(server_dir, member.filename)}")

                logger.info(
                    f"Update extraction complete. Extracted {extracted_count} items, skipped {skipped_count} preserved items."
                )

            else:
                # Fresh install: Extract everything
                logger.debug("Fresh install mode: Extracting all files...")
                zip_ref.extractall(server_dir)
                logger.debug(f"Successfully extracted all files to: {server_dir}")

    except zipfile.BadZipFile as e:
        logger.error(
            f"Failed to extract: '{zip_file}' is not a valid or is a corrupted ZIP file. {e}",
            exc_info=True,
        )
        raise DownloadExtractError(f"Invalid ZIP file: '{zip_file}'. {e}") from e
    except (OSError, IOError) as e:  # Catch file system related errors
        logger.error(
            f"File system error during extraction to '{server_dir}': {e}", exc_info=True
        )
        raise FileOperationError(f"Error during file extraction: {e}") from e
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during ZIP extraction: {e}", exc_info=True
        )
        raise FileOperationError(f"Unexpected error during extraction: {e}") from e


def download_bedrock_server(
    server_dir: str, target_version: str = "LATEST"
) -> Tuple[str, str, str]:
    """
    Coordinates the full Bedrock server download and setup process for a directory.

    Checks internet, finds URL, determines version, downloads the ZIP (if needed),
    and returns information needed for extraction. Does NOT perform extraction itself.

    Args:
        server_dir: The target base directory for the server installation.
        target_version: Version identifier ("LATEST", "PREVIEW", "X.Y.Z.W", "X.Y.Z.W-PREVIEW").
                        Defaults to "LATEST".

    Returns:
        A tuple containing:
            - current_version (str): The actual version number downloaded (e.g., "1.20.1.2").
            - zip_file (str): The full path to the downloaded ZIP file.
            - download_dir (str): The specific directory where the ZIP was saved (stable/preview).

    Raises:
        MissingArgumentError: If `server_dir` is None or empty.
        InternetConnectivityError: If internet check fails or download operations fail.
        DirectoryError: If required directories (server_dir, download_dir) cannot be created.
        DownloadExtractError: If the download URL or version cannot be resolved.
        FileOperationError: If file download or directory creation fails due to OS errors.
        ValueError: If target_version format is invalid (caught by called functions).
        OSError: If OS is unsupported (caught by lookup function).
    """
    if not server_dir:
        raise MissingArgumentError(
            "Server directory cannot be empty for download process."
        )

    logger.info(
        f"Starting Bedrock server download process for directory: '{server_dir}'"
    )
    logger.info(f"Requested target version: '{target_version}'")

    # 1. Check Internet Connectivity
    try:
        system_base.check_internet_connectivity()  # Raises InternetConnectivityError on failure
        logger.debug("Internet connectivity check passed.")
    except InternetConnectivityError as e:
        logger.critical(f"Internet connectivity check failed: {e}", exc_info=True)
        raise  # Re-raise the specific error

    # 2. Ensure Base Directories Exist (Download and Server)
    base_download_dir = settings.get("DOWNLOAD_DIR")
    if not base_download_dir:
        raise DirectoryError(
            "DOWNLOAD_DIR setting is missing or empty in configuration."
        )

    try:
        # Ensure server directory exists (might be created by caller, but ensure here)
        os.makedirs(server_dir, exist_ok=True)
        logger.debug(f"Ensured server base directory exists: {server_dir}")
        # Ensure the *base* download directory exists
        os.makedirs(base_download_dir, exist_ok=True)
        logger.debug(f"Ensured base download directory exists: {base_download_dir}")
    except OSError as e:
        logger.error(
            f"Failed to create essential directories (server: '{server_dir}', base download: '{base_download_dir}'): {e}",
            exc_info=True,
        )
        raise DirectoryError(f"Failed to create required directories: {e}") from e

    # 3. Find Download URL and Determine Actual Version
    # This step handles OS check, version parsing, network errors for lookup
    download_url = lookup_bedrock_download_url(target_version)  # Raises various errors
    actual_version = get_version_from_url(download_url)  # Raises DownloadExtractError
    logger.info(f"Resolved download URL for version {actual_version}: {download_url}")

    # 4. Determine Specific Download Subdirectory (stable/preview)
    target_version_upper = target_version.strip().upper()
    if target_version_upper == "PREVIEW" or target_version_upper.endswith("-PREVIEW"):
        version_subdir_name = "preview"
    else:  # LATEST or specific stable version
        version_subdir_name = "stable"

    specific_download_dir = os.path.join(base_download_dir, version_subdir_name)
    logger.debug(f"Using specific download subdirectory: {specific_download_dir}")

    # Ensure the specific download subdirectory exists
    try:
        os.makedirs(specific_download_dir, exist_ok=True)
    except OSError as e:
        logger.error(
            f"Failed to create specific download directory '{specific_download_dir}': {e}",
            exc_info=True,
        )
        raise DirectoryError(
            f"Failed to create download subdirectory '{specific_download_dir}': {e}"
        ) from e

    # 5. Define ZIP File Path and Check if Download Needed
    zip_file_path = os.path.join(
        specific_download_dir, f"bedrock-server-{actual_version}.zip"
    )

    if not os.path.exists(zip_file_path):
        logger.info(
            f"Server version {actual_version} ZIP not found locally. Proceeding with download..."
        )
        # download_server_zip_file handles download errors (network, file write)
        download_server_zip_file(download_url, zip_file_path)
    else:
        logger.info(
            f"Server version {actual_version} ZIP already exists at '{zip_file_path}'. Skipping download."
        )

    # 6. Prune old downloads in the *specific* directory (stable or preview)
    try:
        download_keep = settings.get("DOWNLOAD_KEEP", 3)  # Default to 3 if not set
        prune_old_downloads(specific_download_dir, download_keep)
    except (ValueError, DirectoryError, FileOperationError, MissingArgumentError) as e:
        logger.warning(
            f"Failed to prune old downloads in '{specific_download_dir}': {e}. Continuing process.",
            exc_info=True,
        )
        # Decide if pruning failure should halt the process. Usually not critical.
    except Exception as e:
        logger.warning(
            f"Unexpected error during download pruning: {e}. Continuing process.",
            exc_info=True,
        )

    # 7. Return results needed for extraction stage
    logger.info(f"Download process completed for version {actual_version}.")
    return actual_version, zip_file_path, specific_download_dir
