# bedrock_server_manager/core/server/world_mixin.py
import os
import shutil
import zipfile
import logging
from typing import Optional

# Local imports
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Attributes from BaseMixin:
        # self.server_name, self.server_dir, self.logger
        # self.settings (for content dir, etc.)
        # Method from StateMixin: self.get_world_name()

    @property
    def _worlds_base_dir_in_server(self) -> str:
        """Path to the 'worlds' subdirectory within this server's installation."""
        return os.path.join(self.server_dir, "worlds")

    def _get_active_world_directory_path(self) -> str:
        """
        Determines the full path to the currently active world directory for this server,
        based on 'level-name' in server.properties.

        Relies on self.get_world_name() being available (from ServerStateMixin).
        """
        if not hasattr(self, "get_world_name"):
            self.logger.error(
                "get_world_name method not found on self. Cannot determine active world directory."
            )
            raise FileOperationError(
                "Internal error: get_world_name method missing. Cannot determine active world directory."
            )

        active_world_name = (
            self.get_world_name()
        )  # This will raise FileOperationError if props/name missing
        return os.path.join(self._worlds_base_dir_in_server, active_world_name)

    def extract_mcworld_to_directory(
        self, mcworld_file_path: str, target_world_dir_name: str
    ) -> str:
        """
        Extracts a .mcworld file into a specific world directory name within this server's 'worlds' folder.
        The target directory (e.g., server_dir/worlds/MyNewWorld) will be cleaned before extraction.
        """
        if not mcworld_file_path:
            raise MissingArgumentError("Path to the .mcworld file cannot be empty.")
        if not target_world_dir_name:  # Ensure a name is provided
            raise MissingArgumentError("Target world directory name cannot be empty.")

        # Construct the full target path within this server's worlds directory
        full_target_extract_dir = os.path.join(
            self._worlds_base_dir_in_server, target_world_dir_name
        )

        mcworld_filename = os.path.basename(mcworld_file_path)
        self.logger.info(
            f"Server '{self.server_name}': Preparing to extract '{mcworld_filename}' "
            f"into world directory '{target_world_dir_name}' (at '{full_target_extract_dir}')."
        )

        if not os.path.isfile(mcworld_file_path):
            raise AppFileNotFoundError(mcworld_file_path, ".mcworld file")

        # Ensure clean target directory
        if os.path.exists(full_target_extract_dir):
            self.logger.warning(
                f"Target world directory '{full_target_extract_dir}' already exists. Removing its contents."
            )
            try:
                shutil.rmtree(full_target_extract_dir)
            except OSError as e:
                self.logger.error(
                    f"Failed to remove existing world directory '{full_target_extract_dir}': {e}",
                    exc_info=True,
                )
                raise FileOperationError(
                    f"Failed to clear target world directory '{full_target_extract_dir}': {e}"
                ) from e

        try:  # Recreate the empty target directory
            os.makedirs(full_target_extract_dir, exist_ok=True)
        except OSError as e:
            self.logger.error(
                f"Failed to create target world directory '{full_target_extract_dir}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to create target world directory '{full_target_extract_dir}': {e}"
            ) from e

        # Extract the world archive
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
            self.logger.error(
                f"Failed to extract '{mcworld_filename}': Invalid ZIP. {e}",
                exc_info=True,
            )
            if os.path.exists(full_target_extract_dir):
                shutil.rmtree(full_target_extract_dir, ignore_errors=True)
            raise ExtractError(
                f"Invalid .mcworld file (not valid zip): {mcworld_filename}"
            ) from e
        except OSError as e:
            self.logger.error(
                f"OS error extracting '{mcworld_filename}' to '{full_target_extract_dir}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Error extracting world '{mcworld_filename}' for server '{self.server_name}': {e}"
            ) from e
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error extracting '{mcworld_filename}': {e_unexp}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Unexpected error extracting world '{mcworld_filename}' for server '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def export_world_directory_to_mcworld(
        self, world_dir_name: str, target_mcworld_file_path: str
    ) -> None:
        """
        Exports a specific world directory from this server's 'worlds' folder into a .mcworld file.

        Args:
            world_dir_name: The name of the world directory under server_dir/worlds/ to export.
                            Example: "MyBedrockWorld".
            target_mcworld_file_path: Full path where the resulting .mcworld file should be saved.
                                      Example: "/path/to/backups/MyBedrockWorld_backup.mcworld".
        """
        if not world_dir_name:
            raise MissingArgumentError("Source world directory name cannot be empty.")
        if not target_mcworld_file_path:
            raise MissingArgumentError("Target .mcworld file path cannot be empty.")

        # Construct full path to the source world directory within this server
        full_source_world_dir = os.path.join(
            self._worlds_base_dir_in_server, world_dir_name
        )

        mcworld_filename = os.path.basename(target_mcworld_file_path)
        self.logger.info(
            f"Server '{self.server_name}': Exporting world '{world_dir_name}' (from '{full_source_world_dir}') "
            f"to .mcworld file '{mcworld_filename}' (at '{target_mcworld_file_path}')."
        )

        if not os.path.isdir(full_source_world_dir):
            raise AppFileNotFoundError(full_source_world_dir, "Source world directory")

        target_parent_dir = os.path.dirname(target_mcworld_file_path)
        if target_parent_dir:  # Ensure parent directory for the .mcworld file exists
            try:
                os.makedirs(target_parent_dir, exist_ok=True)
            except OSError as e:
                self.logger.error(
                    f"Failed to create parent dir '{target_parent_dir}' for .mcworld: {e}",
                    exc_info=True,
                )
                raise FileOperationError(
                    f"Cannot create target directory '{target_parent_dir}': {e}"
                ) from e

        archive_base_name_no_ext = os.path.splitext(target_mcworld_file_path)[0]

        temp_zip_path = archive_base_name_no_ext + ".zip"

        try:
            self.logger.debug(
                f"Creating temporary ZIP archive at '{archive_base_name_no_ext}' for world '{world_dir_name}'."
            )

            shutil.make_archive(
                base_name=archive_base_name_no_ext,  # Output path without .zip
                format="zip",
                root_dir=full_source_world_dir,  # Go into this directory
                base_dir=".",  # Archive everything in root_dir
            )
            self.logger.debug(f"Successfully created temporary ZIP: {temp_zip_path}")

            if not os.path.exists(temp_zip_path):  # Double check
                raise BackupRestoreError(
                    f"Archive process completed but temp zip '{temp_zip_path}' not found."
                )

            if os.path.exists(
                target_mcworld_file_path
            ):  # Rename requires target not to exist on Windows
                self.logger.warning(
                    f"Target file '{target_mcworld_file_path}' exists. Overwriting."
                )
                os.remove(target_mcworld_file_path)

            os.rename(temp_zip_path, target_mcworld_file_path)
            self.logger.info(
                f"Server '{self.server_name}': World export successful. Created: {target_mcworld_file_path}"
            )

        except OSError as e:
            self.logger.error(
                f"Failed to create/rename archive for world '{world_dir_name}': {e}",
                exc_info=True,
            )
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)  # Cleanup
            raise BackupRestoreError(
                f"Failed to create .mcworld for server '{self.server_name}', world '{world_dir_name}': {e}"
            ) from e
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error exporting world '{world_dir_name}': {e_unexp}",
                exc_info=True,
            )
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)  # Cleanup
            raise BackupRestoreError(
                f"Unexpected error exporting world for server '{self.server_name}', world '{world_dir_name}': {e_unexp}"
            ) from e_unexp

    def import_active_world_from_mcworld(self, mcworld_backup_file_path: str) -> str:
        """
        Imports a world from a .mcworld backup file into this server's
        currently active world directory (determined by 'level-name' in server.properties).
        The active world directory will be cleaned before extraction.

        Args:
            mcworld_backup_file_path: Full path to the source .mcworld backup file.

        Returns:
            The name of the world directory that was imported into (the active world name).

        Raises: (as per original import_world)
        """
        if not mcworld_backup_file_path:
            raise MissingArgumentError(".mcworld backup file path cannot be empty.")

        mcworld_filename = os.path.basename(mcworld_backup_file_path)
        self.logger.info(
            f"Server '{self.server_name}': Importing active world from backup '{mcworld_filename}'."
        )

        if not os.path.isfile(mcworld_backup_file_path):
            raise AppFileNotFoundError(mcworld_backup_file_path, ".mcworld backup file")

        # 1. Determine the target active world directory name
        active_world_dir_name: str
        try:
            # self.get_world_name() is from ServerStateMixin, raises AppFileNotFoundError/ConfigParseError
            active_world_dir_name = self.get_world_name()
            self.logger.info(
                f"Target active world name for server '{self.server_name}' is '{active_world_dir_name}'."
            )
        except (AppFileNotFoundError, ConfigParseError) as e:  # From get_world_name
            self.logger.error(
                f"Cannot determine target world directory for '{self.server_name}': {e}",
                exc_info=True,
            )
            raise BackupRestoreError(
                f"Cannot import world: Failed to get active world name for '{self.server_name}'."
            ) from e
        except Exception as e_get_name:  # Other unexpected errors from get_world_name
            self.logger.error(
                f"Unexpected error getting active world name for '{self.server_name}': {e_get_name}",
                exc_info=True,
            )
            raise BackupRestoreError(
                f"Unexpected error getting active world name for '{self.server_name}'."
            ) from e_get_name

        # 2. Delegate to extract_mcworld_to_directory
        try:
            self.extract_mcworld_to_directory(
                mcworld_backup_file_path, active_world_dir_name
            )
            self.logger.info(
                f"Server '{self.server_name}': Active world import from '{mcworld_filename}' completed successfully into '{active_world_dir_name}'."
            )
            return (
                active_world_dir_name  # Return the name of the world directory restored
            )
        except (
            AppFileNotFoundError,
            ExtractError,
            FileOperationError,
            MissingArgumentError,
        ) as e_extract:  # MissingArgumentError if active_world_dir_name was empty
            self.logger.error(
                f"World import failed for server '{self.server_name}' during extraction into '{active_world_dir_name}': {e_extract}",
                exc_info=True,
            )
            raise BackupRestoreError(
                f"World import for server '{self.server_name}' failed into '{active_world_dir_name}': {e_extract}"
            ) from e_extract
        except (
            Exception
        ) as e_unexp_extract:  # Other unexpected errors from extract_mcworld_to_directory
            self.logger.error(
                f"Unexpected error during world import for server '{self.server_name}' into '{active_world_dir_name}': {e_unexp_extract}",
                exc_info=True,
            )
            raise BackupRestoreError(
                f"Unexpected error during world import for server '{self.server_name}' into '{active_world_dir_name}'."
            ) from e_unexp_extract

    def delete_active_world_directory(self) -> bool:
        """
        Deletes the currently active world directory for this server.
        This is a destructive operation.

        Returns:
            True if the directory was successfully deleted or did not exist.
            False if deletion failed.

        Raises:
            FileOperationError: If determining the active world path fails or robust deletion reports an issue.
            AppFileNotFoundError: If the world directory is not found after path is determined.
            ConfigParseError: If server.properties is invalid.
        """
        try:
            active_world_dir = (
                self._get_active_world_directory_path()
            )  # Can raise AppFileNotFoundError, ConfigParseError
            active_world_name = os.path.basename(active_world_dir)  # For logging
        except (AppFileNotFoundError, ConfigParseError) as e:
            self.logger.error(
                f"Server '{self.server_name}': Cannot delete active world, failed to determine path: {e}"
            )
            raise  # Re-raise error about not finding active world path
        except (
            Exception
        ) as e_path:  # Catch any other unexpected error from path getting
            self.logger.error(
                f"Server '{self.server_name}': Unexpected error getting active world path for deletion: {e_path}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Unexpected error determining active world path for '{self.server_name}'"
            ) from e_path

        self.logger.warning(
            f"Server '{self.server_name}': Attempting to delete active world directory: '{active_world_dir}'."
            " This is a DESTRUCTIVE operation."
        )

        if not os.path.exists(active_world_dir):
            self.logger.info(
                f"Server '{self.server_name}': Active world directory '{active_world_dir}' does not exist. Nothing to delete."
            )
            return True  # Considered success as the goal state (no dir) is met

        if not os.path.isdir(active_world_dir):
            # This case should ideally be rare if get_world_name and path construction are correct.
            self.logger.error(
                f"Server '{self.server_name}': Path '{active_world_dir}' for active world is not a directory. Deletion aborted."
            )
            raise FileOperationError(
                f"Path for active world '{active_world_name}' is not a directory: {active_world_dir}"
            )

        # Use the deletion utility from system_base
        success = system_base_utils.delete_path_robustly(
            active_world_dir,
            f"active world directory '{active_world_name}' for server '{self.server_name}'",
        )

        if success:
            self.logger.info(
                f"Server '{self.server_name}': Successfully deleted active world directory '{active_world_dir}'."
            )
        else:
            # delete_path_robustly already logs errors.
            # Raise an error here to signal that the operation didn't fully complete as expected.
            self.logger.error(
                f"Server '{self.server_name}': Failed to completely delete active world directory '{active_world_dir}'."
            )
            raise FileOperationError(
                f"Failed to completely delete active world directory '{active_world_name}' for server '{self.server_name}'. Check logs."
            )

        return success  # Though if it raises, this won't be reached on failure

    @property
    def world_icon_filename(self) -> str:
        """Standard filename for the world icon."""
        return "world_icon.jpeg"

    @property
    def world_icon_filesystem_path(self) -> Optional[str]:
        """
        Returns the absolute filesystem path to the world_icon.jpeg for the server's active world.
        Returns None if the active world name cannot be determined or if the path would be invalid.
        """
        try:
            active_world_dir = self._get_active_world_directory_path()
            return os.path.join(active_world_dir, self.world_icon_filename)
        except (
            AppFileNotFoundError,
            ConfigParseError,
        ) as e:  # Raised by get_world_name or _get_active_world_directory_path
            self.logger.warning(
                f"Server '{self.server_name}': Cannot determine world icon path because active world name is unavailable: {e}"
            )
            return None
        except Exception as e_unexp:  # Catch any other unexpected errors
            self.logger.error(
                f"Server '{self.server_name}': Unexpected error determining world icon path: {e_unexp}",
                exc_info=True,
            )
            return None

    def has_world_icon(self) -> bool:
        """
        Checks if the world_icon.jpeg file exists for the server's active world.
        Returns True if the icon exists and is a file, False otherwise.
        """
        icon_path = self.world_icon_filesystem_path
        if icon_path and os.path.isfile(icon_path):
            self.logger.debug(
                f"Server '{self.server_name}': World icon found at '{icon_path}'."
            )
            return True

        if icon_path:  # Path was determined but file doesn't exist or not a file
            self.logger.debug(
                f"Server '{self.server_name}': World icon not found or not a file at '{icon_path}'."
            )
        # If icon_path is None, the warning was already logged by world_icon_filesystem_path property
        return False
