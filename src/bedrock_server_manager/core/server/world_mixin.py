# bedrock_server_manager/core/server/world_mixin.py
"""Provides the ServerWorldMixin for the BedrockServer class.

This mixin encapsulates all logic related to managing a server's world files.
This includes exporting the world to a `.mcworld` archive, importing a world
from such an archive, and resetting the world by deleting its directory.
"""
import os
import shutil
import zipfile
import logging
from typing import Optional

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.system import base as system_base_utils
from bedrock_server_manager.error import (
    MissingArgumentError,
    ExtractError,
    FileOperationError,
    BackupRestoreError,
    AppFileNotFoundError,
    ConfigParseError,
)


class ServerWorldMixin(BedrockServerBaseMixin):
    """A mixin for BedrockServer providing world management methods."""

    def __init__(self, *args, **kwargs):
        """Initializes the ServerWorldMixin.

        This constructor calls `super().__init__` to ensure proper method
        resolution order in the context of multiple inheritance. It relies on
        attributes and methods from other mixins or the base class.
        """
        super().__init__(*args, **kwargs)
        # Attributes from BaseMixin: self.server_name, self.server_dir, self.logger, self.settings.
        # This mixin also relies on self.get_world_name() being available from the StateMixin.

    @property
    def _worlds_base_dir_in_server(self) -> str:
        """Returns the path to the 'worlds' subdirectory within the server installation."""
        return os.path.join(self.server_dir, "worlds")

    def _get_active_world_directory_path(self) -> str:
        """Determines the full path to the currently active world directory.

        This path is constructed based on the `level-name` property read from
        `server.properties`.

        Returns:
            The absolute path to the active world directory.

        Raises:
            FileOperationError: If the `get_world_name` method is missing.
            AppFileNotFoundError: If `server.properties` is not found.
            ConfigParseError: If `level-name` is missing from `server.properties`.
        """
        if not hasattr(self, "get_world_name"):
            raise FileOperationError(
                "Internal error: get_world_name method missing. Cannot determine active world directory."
            )

        # This method is expected to be on the final class from StateMixin.
        active_world_name = self.get_world_name()
        return os.path.join(self._worlds_base_dir_in_server, active_world_name)

    def extract_mcworld_to_directory(
        self, mcworld_file_path: str, target_world_dir_name: str
    ) -> str:
        """Extracts a .mcworld file into a named world directory.

        This method will first delete the target world directory if it already
        exists to ensure a clean extraction.

        Args:
            mcworld_file_path: The path to the `.mcworld` file to extract.
            target_world_dir_name: The name of the directory to create within
                the server's `worlds` folder for the extracted contents.

        Returns:
            The full path to the directory where the world was extracted.

        Raises:
            MissingArgumentError: If required arguments are empty.
            AppFileNotFoundError: If the source `.mcworld` file does not exist.
            FileOperationError: If creating or clearing the target directory fails.
            ExtractError: If the `.mcworld` file is not a valid zip archive.
        """
        if not mcworld_file_path:
            raise MissingArgumentError("Path to the .mcworld file cannot be empty.")
        if not target_world_dir_name:
            raise MissingArgumentError("Target world directory name cannot be empty.")

        full_target_extract_dir = os.path.join(
            self._worlds_base_dir_in_server, target_world_dir_name
        )
        mcworld_filename = os.path.basename(mcworld_file_path)

        self.logger.info(
            f"Server '{self.server_name}': Preparing to extract '{mcworld_filename}' into world directory '{target_world_dir_name}'."
        )

        if not os.path.isfile(mcworld_file_path):
            raise AppFileNotFoundError(mcworld_file_path, ".mcworld file")

        # Ensure a clean target directory by removing it if it exists.
        if os.path.exists(full_target_extract_dir):
            self.logger.warning(
                f"Target world directory '{full_target_extract_dir}' already exists. Removing its contents."
            )
            try:
                shutil.rmtree(full_target_extract_dir)
            except OSError as e:
                raise FileOperationError(
                    f"Failed to clear target world directory '{full_target_extract_dir}': {e}"
                ) from e

        # Recreate the empty target directory.
        try:
            os.makedirs(full_target_extract_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Failed to create target world directory '{full_target_extract_dir}': {e}"
            ) from e

        # Extract the world archive.
        self.logger.info(
            f"Server '{self.server_name}': Extracting '{mcworld_filename}'..."
        )
        try:
            with zipfile.ZipFile(mcworld_file_path, "r") as zip_ref:
                zip_ref.extractall(full_target_extract_dir)
            self.logger.info(
                f"Server '{self.server_name}': Successfully extracted world to '{full_target_extract_dir}'."
            )
            return full_target_extract_dir
        except zipfile.BadZipFile as e:
            # Clean up the partially created directory on failure.
            if os.path.exists(full_target_extract_dir):
                shutil.rmtree(full_target_extract_dir, ignore_errors=True)
            raise ExtractError(
                f"Invalid .mcworld file (not a valid zip): {mcworld_filename}"
            ) from e
        except OSError as e:
            raise FileOperationError(
                f"Error extracting world '{mcworld_filename}' for server '{self.server_name}': {e}"
            ) from e
        except Exception as e_unexp:
            raise FileOperationError(
                f"Unexpected error extracting world '{mcworld_filename}' for server '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def export_world_directory_to_mcworld(
        self, world_dir_name: str, target_mcworld_file_path: str
    ):
        """Exports a world directory into a .mcworld file.

        This method archives the contents of a specified world directory into a
        zip file and renames it to have a `.mcworld` extension.

        Args:
            world_dir_name: The name of the world directory to export (e.g., "MyWorld").
            target_mcworld_file_path: The full path where the resulting
                `.mcworld` file should be saved.

        Raises:
            MissingArgumentError: If required arguments are empty.
            AppFileNotFoundError: If the source world directory does not exist.
            FileOperationError: If creating the parent directory for the export fails.
            BackupRestoreError: If creating or renaming the archive fails.
        """
        if not world_dir_name:
            raise MissingArgumentError("Source world directory name cannot be empty.")
        if not target_mcworld_file_path:
            raise MissingArgumentError("Target .mcworld file path cannot be empty.")

        full_source_world_dir = os.path.join(
            self._worlds_base_dir_in_server, world_dir_name
        )
        mcworld_filename = os.path.basename(target_mcworld_file_path)

        self.logger.info(
            f"Server '{self.server_name}': Exporting world '{world_dir_name}' to .mcworld file '{mcworld_filename}'."
        )

        if not os.path.isdir(full_source_world_dir):
            raise AppFileNotFoundError(full_source_world_dir, "Source world directory")

        # Ensure the parent directory for the exported file exists.
        target_parent_dir = os.path.dirname(target_mcworld_file_path)
        if target_parent_dir:
            try:
                os.makedirs(target_parent_dir, exist_ok=True)
            except OSError as e:
                raise FileOperationError(
                    f"Cannot create target directory '{target_parent_dir}': {e}"
                ) from e

        archive_base_name_no_ext = os.path.splitext(target_mcworld_file_path)[0]
        temp_zip_path = archive_base_name_no_ext + ".zip"

        try:
            self.logger.debug(
                f"Creating temporary ZIP archive at '{archive_base_name_no_ext}' for world '{world_dir_name}'."
            )
            # Create a zip archive of the world directory's contents.
            shutil.make_archive(
                base_name=archive_base_name_no_ext,
                format="zip",
                root_dir=full_source_world_dir,
                base_dir=".",
            )
            self.logger.debug(f"Successfully created temporary ZIP: {temp_zip_path}")

            if not os.path.exists(temp_zip_path):
                raise BackupRestoreError(
                    f"Archive process completed but temp zip '{temp_zip_path}' not found."
                )

            # Rename the .zip to .mcworld, overwriting if necessary.
            if os.path.exists(target_mcworld_file_path):
                self.logger.warning(
                    f"Target file '{target_mcworld_file_path}' exists. Overwriting."
                )
                os.remove(target_mcworld_file_path)
            os.rename(temp_zip_path, target_mcworld_file_path)
            self.logger.info(
                f"Server '{self.server_name}': World export successful. Created: {target_mcworld_file_path}"
            )

        except OSError as e:
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)  # Clean up temporary file on failure.
            raise BackupRestoreError(
                f"Failed to create .mcworld for server '{self.server_name}', world '{world_dir_name}': {e}"
            ) from e
        except Exception as e_unexp:
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)  # Clean up temporary file on failure.
            raise BackupRestoreError(
                f"Unexpected error exporting world for server '{self.server_name}', world '{world_dir_name}': {e_unexp}"
            ) from e_unexp

    def import_active_world_from_mcworld(self, mcworld_backup_file_path: str) -> str:
        """Imports a .mcworld file, replacing the server's active world.

        This is a destructive operation that determines the active world from
        `server.properties`, then replaces its contents with the extracted
        contents of the provided `.mcworld` file.

        Args:
            mcworld_backup_file_path: The path to the source `.mcworld` file.

        Returns:
            The name of the world directory that was imported into.

        Raises:
            MissingArgumentError: If the file path is empty.
            AppFileNotFoundError: If the source file does not exist.
            BackupRestoreError: If the import process fails at any stage.
        """
        if not mcworld_backup_file_path:
            raise MissingArgumentError(".mcworld backup file path cannot be empty.")

        mcworld_filename = os.path.basename(mcworld_backup_file_path)
        self.logger.info(
            f"Server '{self.server_name}': Importing active world from backup '{mcworld_filename}'."
        )

        if not os.path.isfile(mcworld_backup_file_path):
            raise AppFileNotFoundError(mcworld_backup_file_path, ".mcworld backup file")

        # 1. Determine the target active world directory name.
        try:
            # This method is expected to be on the final class from StateMixin.
            active_world_dir_name = self.get_world_name()
            self.logger.info(
                f"Target active world name for server '{self.server_name}' is '{active_world_dir_name}'."
            )
        except (AppFileNotFoundError, ConfigParseError, Exception) as e:
            raise BackupRestoreError(
                f"Cannot import world: Failed to get active world name for '{self.server_name}'."
            ) from e

        # 2. Delegate the extraction to the specialized method.
        try:
            self.extract_mcworld_to_directory(
                mcworld_backup_file_path, active_world_dir_name
            )
            self.logger.info(
                f"Server '{self.server_name}': Active world import from '{mcworld_filename}' completed successfully into '{active_world_dir_name}'."
            )
            return active_world_dir_name
        except (
            AppFileNotFoundError,
            ExtractError,
            FileOperationError,
            MissingArgumentError,
            Exception,
        ) as e_extract:
            raise BackupRestoreError(
                f"World import for server '{self.server_name}' failed into '{active_world_dir_name}': {e_extract}"
            ) from e_extract

    def delete_active_world_directory(self) -> bool:
        """Deletes the server's currently active world directory.

        This is a destructive operation. The server will generate a new world
        on its next start.

        Returns:
            True if the directory was successfully deleted or did not exist.

        Raises:
            FileOperationError: If determining the world path fails or if the
                path exists but is not a directory, or if deletion fails.
            AppFileNotFoundError: If `server.properties` is missing.
            ConfigParseError: If `level-name` is missing from `server.properties`.
        """
        try:
            active_world_dir = self._get_active_world_directory_path()
            active_world_name = os.path.basename(active_world_dir)
        except (AppFileNotFoundError, ConfigParseError, Exception) as e:
            self.logger.error(
                f"Server '{self.server_name}': Cannot delete active world, failed to determine path: {e}"
            )
            raise

        self.logger.warning(
            f"Server '{self.server_name}': Attempting to delete active world directory: '{active_world_dir}'. THIS IS A DESTRUCTIVE operation."
        )

        if not os.path.exists(active_world_dir):
            self.logger.info(
                f"Server '{self.server_name}': Active world directory '{active_world_dir}' does not exist. Nothing to delete."
            )
            return True

        if not os.path.isdir(active_world_dir):
            raise FileOperationError(
                f"Path for active world '{active_world_name}' is not a directory: {active_world_dir}"
            )

        # Use the robust deletion utility from the system module.
        success = system_base_utils.delete_path_robustly(
            active_world_dir,
            f"active world directory '{active_world_name}' for server '{self.server_name}'",
        )

        if success:
            self.logger.info(
                f"Server '{self.server_name}': Successfully deleted active world directory '{active_world_dir}'."
            )
        else:
            # The robust utility already logs errors, but we raise to signal failure.
            raise FileOperationError(
                f"Failed to completely delete active world directory '{active_world_name}' for server '{self.server_name}'. Check logs."
            )

        return success

    @property
    def world_icon_filename(self) -> str:
        """Returns the standard filename for the world icon."""
        return "world_icon.jpeg"

    @property
    def world_icon_filesystem_path(self) -> Optional[str]:
        """Returns the absolute path to the world icon for the active world.

        Returns `None` if the active world name cannot be determined.
        """
        try:
            active_world_dir = self._get_active_world_directory_path()
            return os.path.join(active_world_dir, self.world_icon_filename)
        except (AppFileNotFoundError, ConfigParseError, Exception) as e:
            self.logger.warning(
                f"Server '{self.server_name}': Cannot determine world icon path because active world name is unavailable: {e}"
            )
            return None

    def has_world_icon(self) -> bool:
        """Checks if the world_icon.jpeg file exists for the active world.

        Returns:
            True if the icon exists and is a file, False otherwise.
        """
        icon_path = self.world_icon_filesystem_path
        if icon_path and os.path.isfile(icon_path):
            self.logger.debug(
                f"Server '{self.server_name}': World icon found at '{icon_path}'."
            )
            return True

        if icon_path:
            self.logger.debug(
                f"Server '{self.server_name}': World icon not found or not a file at '{icon_path}'."
            )
        # If icon_path is None, a warning was already logged.
        return False
