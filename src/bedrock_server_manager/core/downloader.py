# bedrock_server_manager/core/downloader.py
"""
Handles downloading, extracting, and managing Minecraft Bedrock Server files.

This module provides:
- A BedrockDownloader class to manage the lifecycle of downloading and setting up
  a specific server version.
- A standalone prune_old_downloads function for general download cache maintenance.
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

# Local imports
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


# --- Standalone Pruning Function ---
def prune_old_downloads(download_dir: str, download_keep: int) -> None:
    """
    Removes the oldest downloaded server ZIP files, keeping a specified number.

    Args:
        download_dir: The directory containing the downloaded 'bedrock-server-*.zip' files.
        download_keep: The number of most recent ZIP files to retain.

    Raises:
        MissingArgumentError: If `download_dir` is None or empty.
        UserInputError: If `download_keep` is not an integer >= 0.
        AppFileNotFoundError: If `download_dir` does not exist or is not a directory.
        FileOperationError: If there's an error accessing files or deleting an old download.
    """
    if not download_dir:
        raise MissingArgumentError("Download directory cannot be empty for pruning.")

    if not isinstance(download_keep, int) or download_keep < 0:
        raise UserInputError(
            f"Invalid value for downloads to keep: '{download_keep}'. Must be an integer >= 0."
        )

    logger.debug(f"Configured to keep {download_keep} downloads in '{download_dir}'.")

    if not os.path.isdir(download_dir):
        error_msg = f"Download directory '{download_dir}' does not exist or is not a directory. Cannot prune."
        logger.error(error_msg)
        raise AppFileNotFoundError(download_dir, "Download directory")

    logger.info(
        f"Pruning old Bedrock server downloads in '{download_dir}' (keeping {download_keep})..."
    )

    try:
        dir_path = Path(download_dir)
        # Find all bedrock-server zip files in the specified directory
        download_files = list(dir_path.glob("bedrock-server-*.zip"))

        # Sort files by modification time (oldest first)
        download_files.sort(key=lambda p: p.stat().st_mtime)

        logger.debug(
            f"Found {len(download_files)} potential download files matching pattern."
        )

        num_files = len(download_files)
        if num_files > download_keep:
            num_to_delete = num_files - download_keep
            files_to_delete = download_files[:num_to_delete]  # Get the oldest ones
            logger.info(
                f"Found {num_files} downloads. Will delete {num_to_delete} oldest file(s) to keep {download_keep}."
            )

            deleted_count = 0
            for file_path_obj in files_to_delete:
                try:
                    file_path_obj.unlink()  # Use pathlib's unlink
                    logger.info(f"Deleted old download: {file_path_obj}")
                    deleted_count += 1
                except OSError as e_unlink:  # Catch specific OSError for unlink
                    logger.error(
                        f"Failed to delete old server download '{file_path_obj}': {e_unlink}",
                        exc_info=True,
                    )
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

    except (
        OSError
    ) as e_os:  # Catch OS-level errors during directory/file access (not unlink specifically)
        logger.error(
            f"OS error occurred while accessing or pruning downloads in '{download_dir}': {e_os}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Error pruning downloads in '{download_dir}': {e_os}"
        ) from e_os
    except Exception as e_generic:  # Catch any other unexpected error
        logger.error(
            f"Unexpected error occurred while pruning downloads: {e_generic}",
            exc_info=True,
        )
        # Wrap in a FileOperationError for consistency if it's truly unexpected during file ops
        raise FileOperationError(
            f"Unexpected error pruning downloads: {e_generic}"
        ) from e_generic


# --- BedrockDownloader Class Definition ---
class BedrockDownloader:
    """
    Manages downloading, extracting, and maintaining Minecraft Bedrock Server files
    for a specific server instance and target version.
    """

    DOWNLOAD_PAGE_URL: str = "https://www.minecraft.net/en-us/download/server/bedrock"
    PRESERVED_ITEMS_ON_UPDATE: Set[str] = {
        "worlds/",
        "allowlist.json",
        "permissions.json",
        "server.properties",
    }

    def __init__(self, settings_obj, server_dir: str, target_version: str = "LATEST"):
        """
        Initializes the BedrockDownloader.

        Args:
            settings_obj: The application's settings object.
            server_dir: The target base directory for the server installation.
            target_version: Version identifier ("LATEST", "PREVIEW", "X.Y.Z.W", "X.Y.Z.W-PREVIEW").
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
        self.server_dir: str = os.path.abspath(server_dir)  # Normalize server_dir
        self.input_target_version: str = target_version.strip()
        self.logger = logging.getLogger(__name__)  # Instance logger

        self.os_name: str = platform.system()
        self.base_download_dir: Optional[str] = self.settings.get("DOWNLOAD_DIR")
        if not self.base_download_dir:
            raise ConfigurationError(
                "DOWNLOAD_DIR setting is missing or empty in configuration."
            )
        self.base_download_dir = os.path.abspath(self.base_download_dir)  # Normalize

        # Attributes populated during the process
        self.resolved_download_url: Optional[str] = None
        self.actual_version: Optional[str] = None  # Version string like "1.20.1.2"
        self.zip_file_path: Optional[str] = None
        self.specific_download_dir: Optional[str] = None

        # Derived from input_target_version
        self._version_type: str = ""  # "LATEST" or "PREVIEW" (type of search)
        self._custom_version_number: str = ""  # Specific "X.Y.Z.W" part if provided

        self._determine_version_parameters()

    def _determine_version_parameters(self) -> None:
        """Parses input_target_version to determine version type and custom number."""
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
            self._version_type = (
                "LATEST"  # Assumes it's a specific stable version number
            )
            self._custom_version_number = self.input_target_version
            self.logger.info(
                f"Instance targeting specific STABLE version '{self._custom_version_number}' for server: {self.server_dir}"
            )

    def _lookup_bedrock_download_url(self) -> str:
        """
        Finds the download URL by calling the official, confirmed Minecraft
        download links API directly. This is the most robust and reliable method.
        """
        self.logger.debug(
            f"Looking up download URL for target: '{self.input_target_version}' "
            f"(type: '{self._version_type}', custom: '{self._custom_version_number}')"
        )

        API_URL = (
            "https://net-secondary.web.minecraft-services.net/api/v1.0/download/links"
        )

        # --- STEP 1: Determine the downloadType identifier for the API ---
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
            self.logger.error(
                f"Unsupported OS '{self.os_name}' for Bedrock server download."
            )
            raise SystemError(
                f"Unsupported OS for Bedrock server download: {self.os_name}"
            )

        self.logger.debug(f"Targeting API downloadType identifier: '{download_type}'")

        # --- STEP 2: Fetch the download data from the API ---
        try:
            app_name = self.settings.get("_app_name", "BedrockServerManager")
            headers = {
                "User-Agent": f"Python/{platform.python_version()} {app_name}/UnknownVersion"
            }
            self.logger.debug(f"Requesting URL: {API_URL} with headers: {headers}")
            response = requests.get(API_URL, headers=headers, timeout=30)
            response.raise_for_status()
            api_data = response.json()
            self.logger.debug(f"Successfully fetched API data: {api_data}")
        except requests.exceptions.RequestException as e:
            self.logger.error(
                f"Failed to query the Minecraft download API: {e}", exc_info=True
            )
            raise InternetConnectivityError(
                f"Could not contact the Minecraft download API: {e}"
            ) from e
        except json.JSONDecodeError as e:
            self.logger.error(
                f"Minecraft download API returned invalid JSON: {e}", exc_info=True
            )
            raise DownloadError(
                "The Minecraft download API returned malformed data."
            ) from e

        # --- STEP 3: Find the correct download link from the API response ---
        all_links = api_data.get("result", {}).get("links", [])
        base_url = None
        for link in all_links:
            if link.get("downloadType") == download_type:
                base_url = link.get("downloadUrl")
                self.logger.info(f"Found URL via API for '{download_type}': {base_url}")
                break

        if not base_url:
            self.logger.error(
                f"API response did not contain a URL for downloadType '{download_type}'."
            )
            self.logger.debug(f"Full API data received: {api_data}")
            raise DownloadError(
                f"The API did not provide a download URL for your system ({download_type})."
            )

        # --- STEP 4: Handle custom version numbers if provided ---
        if self._custom_version_number:
            try:
                # Substitute the custom version into the found URL's version part
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
                    self.logger.error(
                        f"Regex failed to substitute custom version '{self._custom_version_number}' into base URL '{base_url}'. The URL format may have changed."
                    )
                    raise DownloadError(
                        f"Failed to construct URL for specific version '{self._custom_version_number}'. Please check the version number or report an issue."
                    )
                self.resolved_download_url = modified_url
                self.logger.info(
                    f"Constructed specific version URL: {self.resolved_download_url}"
                )
            except Exception as e:
                self.logger.error(
                    f"Error constructing URL for specific version '{self._custom_version_number}': {e}",
                    exc_info=True,
                )
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
        """
        Extracts the Bedrock server version from self.resolved_download_url.
        Sets self.actual_version and returns it.
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
            error_msg = f"Failed to extract version number from URL format: {self.resolved_download_url}"
            self.logger.error(error_msg)
            raise DownloadError(error_msg + " URL structure might be unexpected.")

    def _download_server_zip_file(self) -> None:
        """Downloads the server ZIP file using self.resolved_download_url and self.zip_file_path."""
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
            if target_dir:  # Ensure containing directory for the zip exists
                os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
            self.logger.error(
                f"Failed to create target directory '{target_dir}' for download: {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Cannot create directory '{target_dir}' for download: {e}"
            ) from e

        try:
            app_name = self.settings.get("_app_name", "BedrockServerManager")
            headers = {
                "User-Agent": f"Python Requests/{requests.__version__} ({app_name})"
            }
            with requests.get(
                self.resolved_download_url, headers=headers, stream=True, timeout=120
            ) as response:  # Increased timeout
                response.raise_for_status()
                self.logger.debug(
                    f"Download request successful (status {response.status_code}). Writing to file."
                )
                total_size = int(response.headers.get("content-length", 0))
                bytes_written = 0
                with open(self.zip_file_path, "wb") as f:
                    for chunk in response.iter_content(
                        chunk_size=8192 * 4
                    ):  # 32KB chunks
                        f.write(chunk)
                        bytes_written += len(chunk)
                self.logger.info(
                    f"Successfully downloaded {bytes_written} bytes to: {self.zip_file_path}"
                )
                if total_size != 0 and bytes_written != total_size:
                    self.logger.warning(
                        f"Downloaded size ({bytes_written}) mismatch content-length ({total_size}). File might be incomplete."
                    )
        except requests.exceptions.RequestException as e:
            self.logger.error(
                f"Failed to download server from '{self.resolved_download_url}': {e}",
                exc_info=True,
            )
            if os.path.exists(
                self.zip_file_path
            ):  # Attempt to clean up partial download
                try:
                    os.remove(self.zip_file_path)
                except OSError as rm_err:
                    self.logger.warning(
                        f"Could not remove incomplete file '{self.zip_file_path}': {rm_err}"
                    )
            raise InternetConnectivityError(
                f"Download failed for '{self.resolved_download_url}': {e}"
            ) from e
        except OSError as e:  # For open() or f.write() errors
            self.logger.error(
                f"Failed to write downloaded content to '{self.zip_file_path}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Cannot write to file '{self.zip_file_path}': {e}"
            ) from e
        except Exception as e:  # Catch-all for other unexpected errors
            self.logger.error(
                f"Unexpected error during download or file write: {e}", exc_info=True
            )
            raise FileOperationError(f"Unexpected error during download: {e}") from e

    def _execute_instance_pruning(self) -> None:
        """
        Handles pruning for the specific download directory associated with this instance.
        This method calls the standalone prune_old_downloads.
        """
        if not self.specific_download_dir:
            self.logger.debug(
                "Instance's specific_download_dir not set, skipping instance pruning."
            )
            return
        if not self.settings:  # Should be set in __init__
            self.logger.warning(
                "Instance settings not available, skipping instance pruning."
            )
            return

        try:
            keep_setting = self.settings.get("DOWNLOAD_KEEP", 3)  # Default to 3
            effective_keep = int(keep_setting)
            if effective_keep < 0:
                self.logger.error(
                    f"Invalid DOWNLOAD_KEEP setting ('{keep_setting}') for instance pruning. Must be >= 0. Skipping."
                )
                return

            self.logger.debug(
                f"Instance triggering pruning for '{self.specific_download_dir}' keeping {effective_keep} files."
            )
            prune_old_downloads(
                self.specific_download_dir, effective_keep
            )  # Call standalone

        except (
            UserInputError,
            FileOperationError,
            AppFileNotFoundError,
            MissingArgumentError,
        ) as e:
            self.logger.warning(
                f"Pruning failed for instance's directory '{self.specific_download_dir}': {e}. Continuing main operation.",
                exc_info=False,  # exc_info=True if detailed trace is always wanted for this warning
            )
        except (
            Exception
        ) as e:  # Catch any other unexpected error from prune_old_downloads
            self.logger.warning(
                f"Unexpected error during instance-triggered pruning for '{self.specific_download_dir}': {e}. Continuing.",
                exc_info=True,
            )

    def get_version_for_target_spec(self) -> str:
        """
        Determines and returns the version string corresponding to the instance's
        initialized target_version. Does not download files but makes network requests
        to resolve the URL and version. Populates self.actual_version and self.resolved_download_url.
        """
        self.logger.debug(
            f"Getting prospective version for target spec: '{self.input_target_version}'"
        )

        # STEP 1: Always look up the download URL. This method uses the instance's
        # state (_custom_version_number) to construct the correct final URL
        # for both specific and latest versions. It populates self.resolved_download_url.
        self._lookup_bedrock_download_url()

        # STEP 2: Now that the URL is resolved, parse the definitive version number
        # from it. This populates self.actual_version.
        self._get_version_from_url()

        # STEP 3: Sanity check and return.
        if not self.actual_version:
            # This should ideally not be reached if the above methods are successful.
            raise DownloadError("Could not determine actual version from resolved URL.")

        return self.actual_version

    def prepare_download_assets(self) -> Tuple[str, str, str]:
        """
        Coordinates finding URL, determining version, downloading (if needed),
        and pruning old downloads. Populates instance attributes.

        Returns:
            A tuple (actual_version, zip_file_path, specific_download_dir).
        """
        self.logger.info(
            f"Starting Bedrock server download preparation for directory: '{self.server_dir}'"
        )
        self.logger.info(f"Requested target version: '{self.input_target_version}'")

        system_base.check_internet_connectivity()  # Raises InternetConnectivityError

        try:  # Ensure base server and download directories exist
            os.makedirs(self.server_dir, exist_ok=True)
            if self.base_download_dir:  # Checked in __init__
                os.makedirs(self.base_download_dir, exist_ok=True)
        except OSError as e:
            self.logger.error(
                f"Failed to create essential directories (server: '{self.server_dir}', base_dl: '{self.base_download_dir}'): {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to create required directories: {e}"
            ) from e

        self.get_version_for_target_spec()  # Ensures self.resolved_download_url and self.actual_version are set

        if (
            not self.actual_version
            or not self.resolved_download_url
            or not self.base_download_dir
        ):
            raise DownloadError(
                "Internal error: version or URL not resolved after lookup/parsing."
            )

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
            self.logger.error(
                f"Failed to create specific download directory '{self.specific_download_dir}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to create download subdirectory '{self.specific_download_dir}': {e}"
            ) from e

        self.zip_file_path = os.path.join(
            self.specific_download_dir, f"bedrock-server-{self.actual_version}.zip"
        )

        if not os.path.exists(self.zip_file_path):
            self.logger.info(
                f"Server version {self.actual_version} ZIP not found locally. Downloading..."
            )
            self._download_server_zip_file()
        else:
            self.logger.info(
                f"Server version {self.actual_version} ZIP already exists at '{self.zip_file_path}'. Skipping download."
            )

        self._execute_instance_pruning()  # Prune after potential download

        self.logger.info(
            f"Download preparation completed for version {self.actual_version}."
        )
        if (
            not self.actual_version
            or not self.zip_file_path
            or not self.specific_download_dir
        ):
            raise DownloadError(
                "Critical state missing after download preparation (actual_version, zip_file_path, or specific_download_dir)."
            )
        return self.actual_version, self.zip_file_path, self.specific_download_dir

    def extract_server_files(self, is_update: bool) -> None:
        """
        Extracts files from the downloaded server ZIP archive into the target server directory.
        Assumes prepare_download_assets() has been successfully called.
        """
        if not self.zip_file_path:
            raise MissingArgumentError(
                "ZIP file path not set. Call prepare_download_assets() first."
            )
        if not os.path.exists(self.zip_file_path):  # Check before trying to open
            raise AppFileNotFoundError(self.zip_file_path, "ZIP file to extract")

        self.logger.info(
            f"Extracting server files from '{self.zip_file_path}' to '{self.server_dir}'..."
        )
        self.logger.debug(
            f"Extraction mode: {'Update (preserving config/worlds)' if is_update else 'Fresh install'}"
        )

        try:  # Ensure target server_dir exists for extraction
            os.makedirs(self.server_dir, exist_ok=True)
        except OSError as e:
            self.logger.error(
                f"Failed to create target server directory '{self.server_dir}' for extraction: {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Cannot create target directory '{self.server_dir}' for extraction: {e}"
            ) from e

        try:
            with zipfile.ZipFile(self.zip_file_path, "r") as zip_ref:
                if is_update:
                    self.logger.debug(
                        f"Update mode: Excluding items matching: {self.PRESERVED_ITEMS_ON_UPDATE}"
                    )
                    extracted_count, skipped_count = 0, 0
                    for member in zip_ref.infolist():
                        member_path = member.filename.replace(
                            "\\", "/"
                        )  # Normalize for comparison
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
                else:  # Fresh install
                    self.logger.debug("Fresh install mode: Extracting all files...")
                    zip_ref.extractall(self.server_dir)
                    self.logger.info(
                        f"Successfully extracted all files to: {self.server_dir}"
                    )
        except zipfile.BadZipFile as e:
            self.logger.error(
                f"Failed to extract: '{self.zip_file_path}' is invalid/corrupted ZIP. {e}",
                exc_info=True,
            )
            raise ExtractError(f"Invalid ZIP file: '{self.zip_file_path}'. {e}") from e
        except (OSError, IOError) as e:  # File system errors during extraction
            self.logger.error(
                f"File system error during extraction to '{self.server_dir}': {e}",
                exc_info=True,
            )
            raise FileOperationError(f"Error during file extraction: {e}") from e
        except Exception as e:  # Other unexpected errors
            self.logger.error(
                f"Unexpected error during ZIP extraction: {e}", exc_info=True
            )
            raise ExtractError(f"Unexpected error during extraction: {e}") from e

    def full_server_setup(self, is_update: bool) -> str:
        """
        Convenience method for the full download, preparation, and extraction process.

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
        if (
            not actual_version
        ):  # Should be caught by prepare_download_assets if it fails to set it
            raise DownloadError("Actual version not determined after full setup.")
        return actual_version

    # --- Getters for populated state ---
    def get_actual_version(self) -> Optional[str]:
        """Returns the actual version string resolved (e.g., '1.20.1.2')."""
        return self.actual_version

    def get_zip_file_path(self) -> Optional[str]:
        """Returns the full path to the downloaded server ZIP file."""
        return self.zip_file_path

    def get_specific_download_dir(self) -> Optional[str]:
        """Returns the specific download directory used (e.g., '.../.downloads/stable')."""
        return self.specific_download_dir

    def get_resolved_download_url(self) -> Optional[str]:
        """Returns the fully resolved download URL."""
        return self.resolved_download_url
