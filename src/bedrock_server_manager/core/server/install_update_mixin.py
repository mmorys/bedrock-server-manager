# bedrock_server_manager/core/server/install_update_mixin.py
"""Provides the ServerInstallUpdateMixin for the BedrockServer class.

This mixin encapsulates the logic for installing and updating the Bedrock
server software. It orchestrates the `BedrockDownloader` to fetch the
correct server files and manages the process of extracting and setting up
these files in the server's directory.
"""
import os
import logging
from typing import TYPE_CHECKING, Optional

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.downloader import (
    BedrockDownloader,
)
from bedrock_server_manager.core.system import (
    base as system_base_utils,
)
from bedrock_server_manager.error import (
    MissingArgumentError,
    DownloadError,
    ExtractError,
    FileOperationError,
    InternetConnectivityError,
    PermissionsError,
    ServerStopError,
    AppFileNotFoundError,
    FileError,
    NetworkError,
    SystemError,
    UserInputError,
    ConfigurationError,
    ServerError,
)


class ServerInstallUpdateMixin(BedrockServerBaseMixin):
    """A mixin for BedrockServer providing installation and update methods.

    This class orchestrates the download process using `BedrockDownloader`,
    extracts server files, checks if an update is needed, and handles the
    overall installation and update workflow for a server instance.
    """

    def __init__(self, *args, **kwargs):
        """Initializes the ServerInstallUpdateMixin.

        This constructor calls `super().__init__` to ensure proper method
        resolution order in the context of multiple inheritance. It relies on
        attributes and methods from other mixins or the base class.
        """
        super().__init__(*args, **kwargs)
        # self.server_name, self.server_dir, self.logger, self.settings are available from BaseMixin.
        # Methods like self.is_installed(), self.get_version(), self.set_version(), self.stop(),
        # self.is_running(), self.set_status_in_config(), and self.set_filesystem_permissions()
        # are expected to be available from other mixins on the final BedrockServer class.

    def _perform_server_files_setup(
        self, downloader: BedrockDownloader, is_update_operation: bool
    ):
        """A core helper to extract server files and set permissions.

        This internal method orchestrates the extraction of the downloaded
        server archive and the subsequent application of necessary filesystem
        permissions to the server directory.

        Args:
            downloader: An initialized `BedrockDownloader` instance that has
                already downloaded the server files.
            is_update_operation: A boolean indicating if this is an update to an
                existing installation, which affects how files are extracted.

        Raises:
            ExtractError: If the file extraction process fails.
            PermissionsError: If setting filesystem permissions fails.
        """
        zip_file_basename = os.path.basename(
            downloader.get_zip_file_path() or "Unknown.zip"
        )
        self.logger.info(
            f"Server '{self.server_name}': Setting up server files in '{self.server_dir}' from '{zip_file_basename}'. Update: {is_update_operation}"
        )
        try:
            # Delegate the extraction logic to the downloader.
            downloader.extract_server_files(is_update_operation)
            self.logger.info(
                f"Server file extraction completed for '{self.server_name}'."
            )
        except (FileError, MissingArgumentError) as e:
            raise ExtractError(
                f"Extraction phase failed for server '{self.server_name}'."
            ) from e

        try:
            # Set filesystem permissions after extraction.
            self.logger.debug(
                f"Setting permissions for server directory: {self.server_dir}"
            )
            self.set_filesystem_permissions()
            self.logger.debug(
                f"Server folder permissions set for '{self.server_name}'."
            )
        except Exception as e_perm:
            self.logger.error(
                f"Failed to set permissions for '{self.server_dir}' during setup: {e_perm}. Installation may be incomplete."
            )
            raise PermissionsError(
                f"Failed to set permissions for '{self.server_dir}'."
            ) from e_perm

    def is_update_needed(self, target_version_specification: str) -> bool:
        """Checks if the server's installed version requires an update.

        This method compares the currently installed version against the target
        specification. The target can be a specific version string (e.g.,
        "1.20.10.01") or a dynamic target ("LATEST" or "PREVIEW").

        Args:
            target_version_specification: The target version to check against.

        Returns:
            True if an update is needed, False otherwise.

        Raises:
            MissingArgumentError: If the target version is not specified.
        """
        if not target_version_specification:
            raise MissingArgumentError("Target version specification cannot be empty.")

        current_installed_version = self.get_version()
        target_spec_upper = target_version_specification.strip().upper()
        is_latest_or_preview = target_spec_upper in ("LATEST", "PREVIEW")

        # --- Path 1: Target is a specific version string ---
        if not is_latest_or_preview:
            try:
                # Use a temporary downloader instance to parse the specific version string.
                temp_downloader_for_parse = BedrockDownloader(
                    settings_obj=self.settings,
                    server_dir=self.server_dir,
                    target_version=target_version_specification,
                )
                specific_target_numeric = (
                    temp_downloader_for_parse._custom_version_number
                )
                if not specific_target_numeric:
                    self.logger.warning(
                        f"Could not parse numeric version from specific target '{target_version_specification}'. Assuming update needed."
                    )
                    return True  # Fail-safe: assume update is needed if parse fails.

                if current_installed_version == specific_target_numeric:
                    self.logger.info(
                        f"Server '{self.server_name}' (v{current_installed_version}) matches specific target '{target_version_specification}'. No update needed."
                    )
                    return False
                else:
                    self.logger.info(
                        f"Server '{self.server_name}' (v{current_installed_version}) differs from specific target '{target_version_specification}' (numeric: {specific_target_numeric}). Update needed."
                    )
                    return True
            except Exception as e_parse:
                self.logger.warning(
                    f"Error parsing specific target version '{target_version_specification}': {e_parse}. Assuming update needed.",
                    exc_info=True,
                )
                return True

        # --- Path 2: Target is "LATEST" or "PREVIEW" ---
        if not current_installed_version or current_installed_version == "UNKNOWN":
            self.logger.info(
                f"Server '{self.server_name}' has version '{current_installed_version}'. Update to '{target_spec_upper}' needed."
            )
            return True

        self.logger.debug(
            f"Server '{self.server_name}': Checking update. Installed='{current_installed_version}', Target='{target_spec_upper}'."
        )
        try:
            # This requires a network call to get the latest version info.
            downloader = BedrockDownloader(
                settings_obj=self.settings,
                server_dir=self.server_dir,
                target_version=target_spec_upper,
            )
            latest_available_for_spec = downloader.get_version_for_target_spec()

            if current_installed_version == latest_available_for_spec:
                self.logger.info(
                    f"Server '{self.server_name}' (v{current_installed_version}) is up-to-date with '{target_spec_upper}' (v{latest_available_for_spec}). No update needed."
                )
                return False
            else:
                self.logger.info(
                    f"Server '{self.server_name}' (v{current_installed_version}) needs update to '{target_spec_upper}' (v{latest_available_for_spec})."
                )
                return True
        except (NetworkError, FileError, SystemError, UserInputError) as e_fetch:
            # Fail-safe: if we can't check the remote version, assume an update might be needed.
            self.logger.warning(
                f"Could not get latest version for '{target_spec_upper}' due to: {e_fetch}. Assuming update might be needed to be safe.",
                exc_info=True,
            )
            return True
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error checking update for '{self.server_name}' against '{target_spec_upper}': {e_unexp}",
                exc_info=True,
            )
            return True

    def install_or_update(
        self, target_version_specification: str, force_reinstall: bool = False
    ):
        """Installs or updates the server to a specified version.

        This is the main orchestration method. It checks if an update is needed,
        stops a running server, downloads the software, extracts it, and updates
        the server's status and version information.

        Args:
            target_version_specification: The target version, e.g., "1.20.10.01",
                "LATEST", or "PREVIEW".
            force_reinstall: If True, the server will be reinstalled even if
                the versions already match.

        Raises:
            ServerStopError: If the server is running and fails to stop.
            DownloadError: If the server software download fails.
            ExtractError: If the downloaded archive cannot be extracted.
            PermissionsError: If filesystem permissions cannot be set.
            FileOperationError: For other unexpected file I/O errors.
        """
        self.logger.info(
            f"Server '{self.server_name}': Initiating install/update to version spec '{target_version_specification}'. Force: {force_reinstall}"
        )

        is_currently_installed = self.is_installed()

        # If not forcing, check if an update is actually needed.
        if not force_reinstall and is_currently_installed:
            if not self.is_update_needed(target_version_specification):
                self.logger.info(
                    f"Server '{self.server_name}' is already at the target version/latest. No action taken."
                )
                return

        # Ensure the server is stopped before making changes to its files.
        if self.is_running():
            self.logger.info(
                f"Server '{self.server_name}' is running. Stopping before install/update."
            )
            try:
                self.stop()
            except Exception as e_stop:
                raise ServerStopError(
                    f"Failed to stop server '{self.server_name}' before install/update: {e_stop}"
                ) from e_stop

        # Update the server's status in its config file.
        status_to_set = "UPDATING" if is_currently_installed else "INSTALLING"
        try:
            self.set_status_in_config(status_to_set)
        except Exception as e_stat:
            self.logger.warning(
                f"Could not set status to {status_to_set} for '{self.server_name}': {e_stat}"
            )

        # Attempt to set the target version in the server's config.
        try:
            if not is_currently_installed:
                    self.set_target_version(target_version_specification.upper())
        except Exception as e_set_target:
            self.logger.warning(
                f"Could not set target version for '{self.server_name}': {e_set_target}"
            )

        downloader = BedrockDownloader(
            settings_obj=self.settings,
            server_dir=self.server_dir,
            target_version=target_version_specification,
        )

        try:
            # Prepare and execute the download.
            self.logger.info(
                f"Server '{self.server_name}': Preparing download assets for '{target_version_specification}'..."
            )
            downloader.prepare_download_assets()
            actual_version_to_download = downloader.get_actual_version()
            if not actual_version_to_download:
                raise DownloadError(
                    f"Could not resolve actual version number for spec '{target_version_specification}'."
                )

            self.logger.info(
                f"Server '{self.server_name}': Downloading version '{actual_version_to_download}'..."
            )
            downloader.prepare_download_assets()

            # Extract the downloaded files and set permissions.
            self.logger.info(
                f"Server '{self.server_name}': Setting up server files (extracting)..."
            )
            is_update_op = is_currently_installed and not force_reinstall
            self._perform_server_files_setup(downloader, is_update_op)

            # After successful setup, update the stored version in the config.
            self.set_version(actual_version_to_download)
            self.set_status_in_config("UPDATED" if is_update_op else "INSTALLED")
            self.logger.info(
                f"Server '{self.server_name}' successfully installed/updated to version '{actual_version_to_download}'."
            )

        except (
            NetworkError,
            FileError,
            ServerError,
            SystemError,
            ConfigurationError,
            UserInputError,
        ) as e_install:
            self.logger.error(
                f"Install/Update failed for server '{self.server_name}': {e_install}",
                exc_info=True,
            )
            self.set_status_in_config("ERROR")
            raise  # Re-raise specific, handled errors.
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error during install/update for '{self.server_name}': {e_unexp}",
                exc_info=True,
            )
            self.set_status_in_config("ERROR")
            raise FileOperationError(
                f"Unexpected failure during install/update for '{self.server_name}': {e_unexp}"
            ) from e_unexp
        finally:
            # Always try to clean up the downloaded zip file.
            if (
                downloader
                and downloader.get_zip_file_path()
                and os.path.exists(downloader.get_zip_file_path())
            ):
                try:
                    self.logger.debug(
                        f"Cleaning up downloaded ZIP: {downloader.get_zip_file_path()}"
                    )
                    os.remove(downloader.get_zip_file_path())
                except OSError as e_clean:
                    self.logger.warning(
                        f"Failed to clean up downloaded ZIP '{downloader.get_zip_file_path()}': {e_clean}"
                    )
