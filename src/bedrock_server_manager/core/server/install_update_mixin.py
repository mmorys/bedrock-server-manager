# bedrock_server_manager/core/server/install_update_mixin.py
"""
Provides the ServerInstallUpdateMixin class for BedrockServer.

This mixin handles the installation and updating of the Bedrock server software.
It uses the BedrockDownloader class to fetch server files and manages the
process of setting up these files in the server's directory.
"""
import os
import logging  # self.logger from BaseMixin
from typing import TYPE_CHECKING, Optional

# Local imports
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
    """
    A mixin for the BedrockServer class that provides methods for installing
    and updating the Minecraft Bedrock Server software.

    It orchestrates the download process using BedrockDownloader, extracts
    server files, and manages version checking.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the ServerInstallUpdateMixin.

        Calls super().__init__ for proper multiple inheritance setup.
        Relies on attributes (like server_name, server_dir, settings, logger)
        and methods (like is_installed, get_version, set_version, stop,
        is_running, set_status_in_config, set_filesystem_permissions)
        from other mixins or the base class.
        """
        super().__init__(*args, **kwargs)
        # self.server_name, self.server_dir, self.logger, self.settings are available
        # self.set_version() method (from ServerStateMixin) is available on the final class

    def _perform_server_files_setup(
        self, downloader: BedrockDownloader, is_update_operation: bool
    ) -> None:
        """
        CORE HELPER: Extracts server files using the downloader and sets permissions.
        This replaces the original setup_server_files function.
        """
        # downloader.server_dir should match self.server_dir
        zip_file_basename = os.path.basename(
            downloader.get_zip_file_path() or "Unknown.zip"
        )
        self.logger.info(
            f"Server '{self.server_name}': Setting up server files in '{self.server_dir}' from '{zip_file_basename}'. Update: {is_update_operation}"
        )
        try:
            downloader.extract_server_files(
                is_update_operation
            )  # Raises various errors
            self.logger.info(
                f"Server file extraction completed for '{self.server_name}'."
            )
        except (FileError, MissingArgumentError) as e:
            raise ExtractError(
                f"Extraction phase failed for server '{self.server_name}'."
            ) from e

        try:
            self.logger.debug(
                f"Setting permissions for server directory: {self.server_dir}"
            )
            self.set_filesystem_permissions()  # From ServerInstallationMixin
            self.logger.debug(
                f"Server folder permissions set for '{self.server_name}'."
            )
        except Exception as e_perm:  # Catch broad permission errors
            # Original logged warning, but for install/update, this might be critical
            self.logger.error(
                f"Failed to set permissions for '{self.server_dir}' during setup: {e_perm}. Installation may be incomplete."
            )
            raise PermissionsError(
                f"Failed to set permissions for '{self.server_dir}'."
            ) from e_perm

    def is_update_needed(self, target_version_specification: str) -> bool:
        """
        Checks if this server's installed version needs an update based on the target version spec.
        Returns True if an update is needed, False otherwise.
        """
        if not target_version_specification:
            raise MissingArgumentError("Target version specification cannot be empty.")

        # self.get_version() is from ServerStateMixin
        current_installed_version = self.get_version()

        target_spec_upper = target_version_specification.strip().upper()
        is_latest_or_preview = target_spec_upper in ("LATEST", "PREVIEW")

        # Path 1: Target is a specific version string
        if not is_latest_or_preview:
            try:
                # Use BedrockDownloader just for its version parsing logic if needed.
                # We need to compare the numeric part of target_version_specification.
                # BedrockDownloader._custom_version_number can give this.
                # Create a temporary downloader instance for this parsing.
                # It requires server_dir, but it's not used for file operations here.
                temp_downloader_for_parse = BedrockDownloader(
                    settings_obj=self.settings,
                    server_dir=self.server_dir,  # Or a dummy path if downloader allows
                    target_version=target_version_specification,
                )
                # _custom_version_number holds "X.Y.Z.W" from "X.Y.Z.W[-PREVIEW]"
                specific_target_numeric = (
                    temp_downloader_for_parse._custom_version_number
                )
                if not specific_target_numeric:
                    self.logger.warning(
                        f"Could not parse numeric version from specific target '{target_version_specification}'. Assuming update needed."
                    )
                    return True  # Fail safe: assume update needed if parse fails

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
            except Exception as e_parse:  # Errors from BedrockDownloader init or logic
                self.logger.warning(
                    f"Error parsing specific target version '{target_version_specification}': {e_parse}. Assuming update needed.",
                    exc_info=True,
                )
                return True

        # Path 2: Target is LATEST or PREVIEW
        if not current_installed_version or current_installed_version == "UNKNOWN":
            self.logger.info(
                f"Server '{self.server_name}' has version '{current_installed_version}'. Update to '{target_spec_upper}' needed."
            )
            return True

        self.logger.debug(
            f"Server '{self.server_name}': Checking update. Installed='{current_installed_version}', Target='{target_spec_upper}'."
        )
        try:
            downloader = BedrockDownloader(
                settings_obj=self.settings,
                server_dir=self.server_dir,
                target_version=target_spec_upper,
            )
            latest_available_for_spec = (
                downloader.get_version_for_target_spec()
            )  # Fetches from web

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
            self.logger.warning(
                f"Could not get latest version for '{target_spec_upper}' due to: {e_fetch}. Assuming update might be needed to be safe.",
                exc_info=True,
            )
            return True  # Fail safe if we can't check remote version
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error checking update for '{self.server_name}' against '{target_spec_upper}': {e_unexp}",
                exc_info=True,
            )
            return True  # Fail safe

    def install_or_update(
        self, target_version_specification: str, force_reinstall: bool = False
    ) -> None:
        """
        Installs or updates this server to the specified version.
        If force_reinstall is True, it will reinstall even if versions match.
        """
        self.logger.info(
            f"Server '{self.server_name}': Initiating install/update to version spec '{target_version_specification}'. Force: {force_reinstall}"
        )

        is_currently_installed = self.is_installed()  # From ServerInstallationMixin
        current_version = self.get_version()  # From ServerStateMixin

        if not force_reinstall and is_currently_installed:
            if not self.is_update_needed(target_version_specification):
                self.logger.info(
                    f"Server '{self.server_name}' is already at the target version/latest. No action taken."
                )
                return

        if self.is_running():  # From ServerProcessMixin
            self.logger.info(
                f"Server '{self.server_name}' is running. Stopping before install/update."
            )
            try:
                self.stop()  # stop() method from ServerProcessMixin
            except Exception as e_stop:
                raise ServerStopError(
                    f"Failed to stop server '{self.server_name}' before install/update: {e_stop}"
                ) from e_stop

        # Set status to UPDATING (or INSTALLING if not previously installed)
        status_to_set = "UPDATING" if is_currently_installed else "INSTALLING"
        try:
            self.set_status_in_config(status_to_set)  # from ServerStateMixin
        except Exception as e_stat:
            self.logger.warning(
                f"Could not set status to {status_to_set} for '{self.server_name}': {e_stat}"
            )

        downloader = BedrockDownloader(
            settings_obj=self.settings,
            server_dir=self.server_dir,  # Target installation directory
            target_version=target_version_specification,
        )

        try:
            self.logger.info(
                f"Server '{self.server_name}': Preparing download assets for '{target_version_specification}'..."
            )
            downloader.prepare_download_assets()  # Checks internet, gets URL, filename

            actual_version_to_download = downloader.get_actual_version()
            if (
                not actual_version_to_download
            ):  # Should be resolved by prepare_download_assets
                raise DownloadError(
                    f"Could not resolve actual version number for spec '{target_version_specification}'."
                )

            self.logger.info(
                f"Server '{self.server_name}': Downloading version '{actual_version_to_download}'..."
            )
            downloader.prepare_download_assets()

            self.logger.info(
                f"Server '{self.server_name}': Setting up server files (extracting)..."
            )
            is_update_op = (
                is_currently_installed and not force_reinstall
            )  # True if updating existing, False if fresh or forced
            self._perform_server_files_setup(downloader, is_update_op)

            # After successful setup, update the stored version
            self.set_version(actual_version_to_download)  # From ServerStateMixin

            if not is_update_op:
                self.set_status_in_config("INSTALLED")  # Mark as INSTALLED
            else:
                self.set_status_in_config("UPDATED")

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
            raise  # Re-raise specific install/download errors
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
            # Clean up downloaded ZIP file, regardless of success/failure of extraction/setup
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
