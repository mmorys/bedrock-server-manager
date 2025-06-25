# bedrock_server_manager/core/downloader.py
"""Handles downloading, extracting, and managing Minecraft Bedrock Server files.

This module provides the `BedrockDownloader` class, which manages the lifecycle
of downloading and setting up a specific server version. It also includes a
standalone `prune_old_downloads` function for general maintenance of the
download cache.
"""

import re
import requests
import platform
import logging
import os
import json
import zipfile
from pathlib import Path
from typing import Tuple, Optional, Set

# Local application imports.
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.error import (
    DownloadError,
    ExtractError,
    MissingArgumentError,
    InternetConnectivityError,
    FileOperationError,
    AppFileNotFoundError,
    ConfigurationError,
    UserInputError,
    SystemError,
)

logger = logging.getLogger(__name__)


def prune_old_downloads(download_dir: str, download_keep: int):
    """Removes the oldest downloaded server ZIP files from a directory.

    This function keeps a specified number of the most recent downloads and
    deletes the rest to manage disk space.

    Args:
        download_dir: The directory containing the downloaded
            'bedrock-server-*.zip' files.
        download_keep: The number of most recent ZIP files to retain.

    Raises:
        MissingArgumentError: If `download_dir` is not provided.
        UserInputError: If `download_keep` is not a non-negative integer.
        AppFileNotFoundError: If `download_dir` does not exist.
        FileOperationError: If there's an error accessing or deleting files.
    """
    if not download_dir:
        raise MissingArgumentError("Download directory cannot be empty for pruning.")
    if not isinstance(download_keep, int) or download_keep < 0:
        raise UserInputError(
            f"Invalid value for downloads to keep: '{download_keep}'. Must be an integer >= 0."
        )

    logger.debug(f"Configured to keep {download_keep} downloads in '{download_dir}'.")

    if not os.path.isdir(download_dir):
        raise AppFileNotFoundError(download_dir, "Download directory")

    logger.info(
        f"Pruning old Bedrock server downloads in '{download_dir}' (keeping {download_keep})..."
    )

    try:
        dir_path = Path(download_dir)
        # Find all files matching the bedrock server download pattern.
        download_files = list(dir_path.glob("bedrock-server-*.zip"))

        # Sort files by modification time (oldest first) to identify which to delete.
        download_files.sort(key=lambda p: p.stat().st_mtime)
        logger.debug(
            f"Found {len(download_files)} potential download files matching pattern."
        )

        num_files = len(download_files)
        if num_files > download_keep:
            num_to_delete = num_files - download_keep
            files_to_delete = download_files[:num_to_delete]
            logger.info(
                f"Found {num_files} downloads. Will delete {num_to_delete} oldest file(s) to keep {download_keep}."
            )

            deleted_count = 0
            for file_path_obj in files_to_delete:
                try:
                    file_path_obj.unlink()
                    logger.info(f"Deleted old download: {file_path_obj}")
                    deleted_count += 1
                except OSError as e_unlink:
                    logger.error(
                        f"Failed to delete old server download '{file_path_obj}': {e_unlink}",
                        exc_info=True,
                    )

            # If not all intended files were deleted, raise an error.
            if deleted_count < num_to_delete:
                raise FileOperationError(
                    f"Failed to delete all required old downloads ({num_to_delete - deleted_count} failed). Check logs."
                )
            logger.info(f"Successfully deleted {deleted_count} old download(s).")
        else:
            logger.info(
                f"Found {num_files} download(s), which is not more than the {download_keep} to keep. No files deleted."
            )

    except OSError as e_os:
        raise FileOperationError(
            f"Error pruning downloads in '{download_dir}': {e_os}"
        ) from e_os
    except Exception as e_generic:
        raise FileOperationError(
            f"Unexpected error pruning downloads: {e_generic}"
        ) from e_generic


class BedrockDownloader:
    """Manages the download and extraction of a specific Bedrock Server version.

    This class handles the entire lifecycle for acquiring server files, including:
    - Resolving the correct download URL for a given version spec (e.g., "LATEST").
    - Downloading the server ZIP archive.
    - Extracting the files into a target directory.
    - Pruning the download cache.

    Attributes:
        DOWNLOAD_PAGE_URL: The URL of the Minecraft Bedrock Server download page.
        PRESERVED_ITEMS_ON_UPDATE: A set of files and directories that should not
            be overwritten during an update extraction.
    """

    DOWNLOAD_PAGE_URL: str = "https://www.minecraft.net/en-us/download/server/bedrock"
    PRESERVED_ITEMS_ON_UPDATE: Set[str] = {
        "worlds/",
        "allowlist.json",
        "permissions.json",
        "server.properties",
    }

    def __init__(self, settings_obj, server_dir: str, target_version: str = "LATEST"):
        """Initializes the BedrockDownloader.

        Args:
            settings_obj: The application's `Settings` object.
            server_dir: The target directory for the server installation.
            target_version: The version identifier to download (e.g., "LATEST",
                "PREVIEW", "1.20.10.01", "1.20.10.01-PREVIEW").

        Raises:
            MissingArgumentError: If any of the required arguments are not provided.
            ConfigurationError: If the `DOWNLOAD_DIR` setting is missing.
        """
        if not settings_obj:
            raise MissingArgumentError(
                "Settings object cannot be None for BedrockDownloader."
            )
        if not server_dir:
            raise MissingArgumentError(
                "Server directory cannot be empty for BedrockDownloader."
            )
        if not target_version:
            raise MissingArgumentError(
                "Target version cannot be empty for BedrockDownloader."
            )

        self.settings = settings_obj
        self.server_dir: str = os.path.abspath(server_dir)
        self.input_target_version: str = target_version.strip()
        self.logger = logging.getLogger(__name__)

        self.os_name: str = platform.system()
        self.base_download_dir: Optional[str] = self.settings.get("DOWNLOAD_DIR")
        if not self.base_download_dir:
            raise ConfigurationError(
                "DOWNLOAD_DIR setting is missing or empty in configuration."
            )
        self.base_download_dir = os.path.abspath(self.base_download_dir)

        # These attributes are populated during the download process.
        self.resolved_download_url: Optional[str] = None
        self.actual_version: Optional[str] = (
            None  # The final version string, e.g., "1.20.10.01"
        )
        self.zip_file_path: Optional[str] = None
        self.specific_download_dir: Optional[str] = None  # e.g., .../downloads/stable

        # These attributes are derived from the input_target_version.
        self._version_type: str = ""  # "LATEST" or "PREVIEW"
        self._custom_version_number: str = ""  # "X.Y.Z.W" part if provided

        self._determine_version_parameters()

    def _determine_version_parameters(self):
        """Parses the input version string to set internal version parameters."""
        target_upper = self.input_target_version.upper()
        if target_upper == "PREVIEW":
            self._version_type = "PREVIEW"
            self.logger.info(
                f"Instance targeting latest PREVIEW version for server: {self.server_dir}"
            )
        elif target_upper == "LATEST":
            self._version_type = "LATEST"
            self.logger.info(
                f"Instance targeting latest STABLE version for server: {self.server_dir}"
            )
        elif target_upper.endswith("-PREVIEW"):
            self._version_type = "PREVIEW"
            self._custom_version_number = self.input_target_version[: -len("-PREVIEW")]
            self.logger.info(
                f"Instance targeting specific PREVIEW version '{self._custom_version_number}' for server: {self.server_dir}"
            )
        else:
            self._version_type = "LATEST"  # Assume a specific stable version
            self._custom_version_number = self.input_target_version
            self.logger.info(
                f"Instance targeting specific STABLE version '{self._custom_version_number}' for server: {self.server_dir}"
            )

    def _lookup_bedrock_download_url(self) -> str:
        """Finds the download URL by querying the official Minecraft download API.

        This is the most reliable method as it does not rely on web scraping.

        Returns:
            The resolved download URL for the specified version and OS.

        Raises:
            SystemError: If the operating system is not supported.
            InternetConnectivityError: If the API cannot be reached.
            DownloadError: If the API response is invalid or does not contain
                the required URL.
        """
        self.logger.debug(
            f"Looking up download URL for target: '{self.input_target_version}'"
        )
        API_URL = (
            "https://net-secondary.web.minecraft-services.net/api/v1.0/download/links"
        )

        # 1. Determine the API identifier based on OS and version type.
        if self.os_name == "Linux":
            download_type = (
                "serverBedrockPreviewLinux"
                if self._version_type == "PREVIEW"
                else "serverBedrockLinux"
            )
        elif self.os_name == "Windows":
            download_type = (
                "serverBedrockPreviewWindows"
                if self._version_type == "PREVIEW"
                else "serverBedrockWindows"
            )
        else:
            raise SystemError(
                f"Unsupported OS for Bedrock server download: {self.os_name}"
            )
        self.logger.debug(f"Targeting API downloadType identifier: '{download_type}'")

        # 2. Fetch data from the API.
        try:
            app_name = self.settings.get("_app_name", "BedrockServerManager")
            headers = {
                "User-Agent": f"Python/{platform.python_version()} {app_name}/UnknownVersion"
            }
            response = requests.get(API_URL, headers=headers, timeout=30)
            response.raise_for_status()
            api_data = response.json()
            self.logger.debug(f"Successfully fetched API data: {api_data}")
        except requests.exceptions.RequestException as e:
            raise InternetConnectivityError(
                f"Could not contact the Minecraft download API: {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise DownloadError(
                "The Minecraft download API returned malformed data."
            ) from e

        # 3. Find the correct download link in the response.
        all_links = api_data.get("result", {}).get("links", [])
        base_url = next(
            (
                link.get("downloadUrl")
                for link in all_links
                if link.get("downloadType") == download_type
            ),
            None,
        )

        if not base_url:
            self.logger.error(
                f"API response did not contain a URL for downloadType '{download_type}'."
            )
            raise DownloadError(
                f"The API did not provide a download URL for your system ({download_type})."
            )
        self.logger.info(f"Found URL via API for '{download_type}': {base_url}")

        # 4. If a specific version was requested, substitute it into the URL.
        if self._custom_version_number:
            try:
                modified_url = re.sub(
                    r"(bedrock-server-)[0-9.]+?(\.zip)",
                    rf"\g<1>{self._custom_version_number}\g<2>",
                    base_url,
                    count=1,
                )
                if (
                    modified_url == base_url
                    and self._custom_version_number not in base_url
                ):
                    raise DownloadError(
                        f"Failed to construct URL for specific version '{self._custom_version_number}'. The URL format may have changed."
                    )
                self.resolved_download_url = modified_url
                self.logger.info(
                    f"Constructed specific version URL: {self.resolved_download_url}"
                )
            except Exception as e:
                raise DownloadError(
                    f"Error constructing URL for specific version '{self._custom_version_number}': {e}"
                ) from e
        else:
            self.resolved_download_url = base_url

        if not self.resolved_download_url:
            raise DownloadError(
                "Internal error: Failed to resolve a final download URL."
            )
        return self.resolved_download_url

    def _get_version_from_url(self) -> str:
        """Extracts the version number from the resolved download URL.

        This method populates `self.actual_version`.

        Returns:
            The extracted version string (e.g., "1.20.10.01").

        Raises:
            MissingArgumentError: If the download URL has not been resolved yet.
            DownloadError: If the URL format is unexpected and the version
                cannot be parsed.
        """
        if not self.resolved_download_url:
            raise MissingArgumentError(
                "Download URL is not set. Cannot extract version."
            )

        match = re.search(r"bedrock-server-([0-9.]+)\.zip", self.resolved_download_url)
        if match:
            version = match.group(1).rstrip(".")
            self.logger.debug(
                f"Extracted version '{version}' from URL: {self.resolved_download_url}"
            )
            self.actual_version = version
            return self.actual_version
        else:
            raise DownloadError(
                f"Failed to extract version number from URL format: {self.resolved_download_url}"
            )

    def _download_server_zip_file(self):
        """Downloads the server ZIP file from the resolved URL.

        Raises:
            MissingArgumentError: If the URL or target file path are not set.
            FileOperationError: If directories cannot be created or the file
                cannot be written.
            InternetConnectivityError: If the download request fails.
        """
        if not self.resolved_download_url or not self.zip_file_path:
            raise MissingArgumentError(
                "Download URL or ZIP file path not set. Cannot download."
            )

        self.logger.info(
            f"Attempting to download server from: {self.resolved_download_url}"
        )
        self.logger.debug(f"Saving downloaded file to: {self.zip_file_path}")

        target_dir = os.path.dirname(self.zip_file_path)
        try:
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Cannot create directory '{target_dir}' for download: {e}"
            ) from e

        try:
            app_name = self.settings.get("_app_name", "BedrockServerManager")
            headers = {
                "User-Agent": f"Python Requests/{requests.__version__} ({app_name})"
            }
            # Use a streaming request to handle large files efficiently.
            with requests.get(
                self.resolved_download_url, headers=headers, stream=True, timeout=120
            ) as response:
                response.raise_for_status()
                self.logger.debug(
                    f"Download request successful (status {response.status_code}). Writing to file."
                )
                total_size = int(response.headers.get("content-length", 0))
                bytes_written = 0
                with open(self.zip_file_path, "wb") as f:
                    # Write the file in chunks to avoid high memory usage.
                    for chunk in response.iter_content(chunk_size=8192 * 4):
                        f.write(chunk)
                        bytes_written += len(chunk)
                self.logger.info(
                    f"Successfully downloaded {bytes_written} bytes to: {self.zip_file_path}"
                )
                if total_size != 0 and bytes_written != total_size:
                    self.logger.warning(
                        f"Downloaded size ({bytes_written}) does not match content-length ({total_size}). File might be incomplete."
                    )
        except requests.exceptions.RequestException as e:
            # Clean up partial download on failure.
            if os.path.exists(self.zip_file_path):
                try:
                    os.remove(self.zip_file_path)
                except OSError as rm_err:
                    self.logger.warning(
                        f"Could not remove incomplete file '{self.zip_file_path}': {rm_err}"
                    )
            raise InternetConnectivityError(
                f"Download failed for '{self.resolved_download_url}': {e}"
            ) from e
        except OSError as e:
            raise FileOperationError(
                f"Cannot write to file '{self.zip_file_path}': {e}"
            ) from e
        except Exception as e:
            raise FileOperationError(f"Unexpected error during download: {e}") from e

    def _execute_instance_pruning(self):
        """Calls the standalone prune function for this instance's download directory."""
        if not self.specific_download_dir:
            self.logger.debug(
                "Instance's specific_download_dir not set, skipping instance pruning."
            )
            return
        if not self.settings:
            self.logger.warning(
                "Instance settings not available, skipping instance pruning."
            )
            return

        try:
            keep_setting = self.settings.get("DOWNLOAD_KEEP", 3)
            effective_keep = int(keep_setting)
            if effective_keep < 0:
                self.logger.error(
                    f"Invalid DOWNLOAD_KEEP setting ('{keep_setting}'). Must be >= 0. Skipping."
                )
                return
            self.logger.debug(
                f"Instance triggering pruning for '{self.specific_download_dir}' keeping {effective_keep} files."
            )
            prune_old_downloads(self.specific_download_dir, effective_keep)
        except (
            UserInputError,
            FileOperationError,
            AppFileNotFoundError,
            MissingArgumentError,
            Exception,
        ) as e:
            # Log as a warning and continue, as pruning failure should not block the main operation.
            self.logger.warning(
                f"Pruning failed for instance's directory '{self.specific_download_dir}': {e}. Continuing main operation.",
                exc_info=True,
            )

    def get_version_for_target_spec(self) -> str:
        """Resolves the actual version string for the instance's target.

        This method performs the network requests to find the URL and parse
        the version from it, but does not download the file itself. It populates
        `self.actual_version` and `self.resolved_download_url`.

        Returns:
            The actual version string corresponding to the target specification.

        Raises:
            DownloadError: If a definitive version cannot be resolved.
        """
        self.logger.debug(
            f"Getting prospective version for target spec: '{self.input_target_version}'"
        )
        # 1. Resolve the download URL.
        self._lookup_bedrock_download_url()
        # 2. Parse the version from the resolved URL.
        self._get_version_from_url()
        # 3. Return the result.
        if not self.actual_version:
            raise DownloadError("Could not determine actual version from resolved URL.")
        return self.actual_version

    def prepare_download_assets(self) -> Tuple[str, str, str]:
        """Orchestrates the full download preparation process.

        This method coordinates all steps required before extraction:
        - Checks internet connectivity.
        - Creates necessary directories.
        - Resolves the download URL and version.
        - Downloads the server archive if it's not already present locally.
        - Prunes the download cache.

        Returns:
            A tuple containing the actual version string, the path to the
            downloaded ZIP file, and the specific download directory used.

        Raises:
            InternetConnectivityError: If there's no internet connection.
            FileOperationError: If directories cannot be created.
            DownloadError: If the download process fails.
        """
        self.logger.info(
            f"Starting Bedrock server download preparation for directory: '{self.server_dir}'"
        )
        system_base.check_internet_connectivity()

        try:
            os.makedirs(self.server_dir, exist_ok=True)
            if self.base_download_dir:
                os.makedirs(self.base_download_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Failed to create required directories: {e}"
            ) from e

        # This resolves URL and version, populating instance attributes.
        self.get_version_for_target_spec()

        if (
            not self.actual_version
            or not self.resolved_download_url
            or not self.base_download_dir
        ):
            raise DownloadError(
                "Internal error: version or URL not resolved after lookup."
            )

        # Determine the specific subdirectory (stable or preview).
        version_subdir_name = "preview" if self._version_type == "PREVIEW" else "stable"
        self.specific_download_dir = os.path.join(
            self.base_download_dir, version_subdir_name
        )
        self.logger.debug(
            f"Using specific download subdirectory: {self.specific_download_dir}"
        )
        try:
            os.makedirs(self.specific_download_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Failed to create download subdirectory '{self.specific_download_dir}': {e}"
            ) from e

        self.zip_file_path = os.path.join(
            self.specific_download_dir, f"bedrock-server-{self.actual_version}.zip"
        )

        # Download the file only if it doesn't already exist.
        if not os.path.exists(self.zip_file_path):
            self.logger.info(
                f"Server version {self.actual_version} ZIP not found locally. Downloading..."
            )
            self._download_server_zip_file()
        else:
            self.logger.info(
                f"Server version {self.actual_version} ZIP already exists at '{self.zip_file_path}'. Skipping download."
            )

        # Prune the cache after a potential download.
        self._execute_instance_pruning()
        self.logger.info(
            f"Download preparation completed for version {self.actual_version}."
        )

        if (
            not self.actual_version
            or not self.zip_file_path
            or not self.specific_download_dir
        ):
            raise DownloadError("Critical state missing after download preparation.")
        return self.actual_version, self.zip_file_path, self.specific_download_dir

    def extract_server_files(self, is_update: bool):
        """Extracts files from the downloaded ZIP to the server directory.

        This method assumes `prepare_download_assets()` has been successfully called.
        In update mode, it preserves essential files like worlds and properties.

        Args:
            is_update: If True, performs an update extraction, preserving key
                files. If False, performs a fresh extraction of all files.

        Raises:
            MissingArgumentError: If the ZIP file path is not set.
            AppFileNotFoundError: If the downloaded ZIP file does not exist.
            FileOperationError: If creating the server directory fails or there
                are filesystem errors during extraction.
            ExtractError: If the ZIP file is invalid or corrupted.
        """
        if not self.zip_file_path:
            raise MissingArgumentError(
                "ZIP file path not set. Call prepare_download_assets() first."
            )
        if not os.path.exists(self.zip_file_path):
            raise AppFileNotFoundError(self.zip_file_path, "ZIP file to extract")

        self.logger.info(
            f"Extracting server files from '{self.zip_file_path}' to '{self.server_dir}'..."
        )
        self.logger.debug(
            f"Extraction mode: {'Update (preserving config/worlds)' if is_update else 'Fresh install'}"
        )

        try:
            os.makedirs(self.server_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Cannot create target directory '{self.server_dir}' for extraction: {e}"
            ) from e

        try:
            with zipfile.ZipFile(self.zip_file_path, "r") as zip_ref:
                # In update mode, skip preserved files.
                if is_update:
                    self.logger.debug(
                        f"Update mode: Excluding items matching: {self.PRESERVED_ITEMS_ON_UPDATE}"
                    )
                    extracted_count, skipped_count = 0, 0
                    for member in zip_ref.infolist():
                        member_path = member.filename.replace("\\", "/")
                        should_extract = not any(
                            member_path == item or member_path.startswith(item)
                            for item in self.PRESERVED_ITEMS_ON_UPDATE
                        )
                        if should_extract:
                            zip_ref.extract(member, path=self.server_dir)
                            extracted_count += 1
                        else:
                            self.logger.debug(
                                f"Skipping extraction of preserved item: {member_path}"
                            )
                            skipped_count += 1
                    self.logger.info(
                        f"Update extraction complete. Extracted {extracted_count} items, skipped {skipped_count} preserved items."
                    )
                # In fresh install mode, extract everything.
                else:
                    self.logger.debug("Fresh install mode: Extracting all files...")
                    zip_ref.extractall(self.server_dir)
                    self.logger.info(
                        f"Successfully extracted all files to: {self.server_dir}"
                    )
        except zipfile.BadZipFile as e:
            raise ExtractError(f"Invalid ZIP file: '{self.zip_file_path}'. {e}") from e
        except (OSError, IOError) as e:
            raise FileOperationError(f"Error during file extraction: {e}") from e
        except Exception as e:
            raise ExtractError(f"Unexpected error during extraction: {e}") from e

    def full_server_setup(self, is_update: bool) -> str:
        """A convenience method for the full download and extraction process.

        Args:
            is_update: True if this is an update, False for a fresh install.

        Returns:
            The actual version string of the server that was set up.
        """
        self.logger.info(
            f"Starting full server setup for '{self.server_dir}', version '{self.input_target_version}', update={is_update}"
        )
        actual_version, _, _ = self.prepare_download_assets()
        self.extract_server_files(is_update)
        self.logger.info(
            f"Server setup/update for version {actual_version} completed in '{self.server_dir}'."
        )
        if not actual_version:
            raise DownloadError("Actual version not determined after full setup.")
        return actual_version

    def get_actual_version(self) -> Optional[str]:
        """Returns the resolved actual version string (e.g., '1.20.10.01')."""
        return self.actual_version

    def get_zip_file_path(self) -> Optional[str]:
        """Returns the full path to the downloaded server ZIP file."""
        return self.zip_file_path

    def get_specific_download_dir(self) -> Optional[str]:
        """Returns the specific download directory used (e.g., '.../downloads/stable')."""
        return self.specific_download_dir

    def get_resolved_download_url(self) -> Optional[str]:
        """Returns the fully resolved download URL."""
        return self.resolved_download_url
