# bedrock_server_manager/core/server/backup_restore_mixin.py
"""
Provides the ServerBackupMixin class for BedrockServer.

This mixin handles all backup and restore operations for a server instance,
including backing up worlds and configuration files, listing available backups,
restoring from backups, and pruning old backup files.
"""
import os
import glob
import re
import shutil
import logging
from typing import Optional, Dict, TYPE_CHECKING, List, Union

# Local imports
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import (
    FileOperationError,
    UserInputError,
    BackupRestoreError,
    MissingArgumentError,
    ConfigurationError,
    AppFileNotFoundError,
    ExtractError,
)
from bedrock_server_manager.utils import (
    general,
)


class ServerBackupMixin(BedrockServerBaseMixin):
    """
    A mixin for the BedrockServer class that provides methods for backing up
    and restoring server data, including worlds and configuration files.
    It also handles pruning of old backups based on retention settings.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the ServerBackupMixin.

        Calls super().__init__ for proper multiple inheritance setup.
        Relies on attributes (like server_name, server_dir, settings, logger) and
        methods (like get_world_name, export_world_directory_to_mcworld,
        import_active_world_from_mcworld) from other mixins or the base class.
        """
        super().__init__(*args, **kwargs)
        # Attributes: self.server_name, self.server_dir, self.logger, self.settings
        # Methods from other mixins: self.get_world_name(), self.export_world_directory_to_mcworld(),
        #                            self.import_active_world_from_mcworld()

    @property
    def server_backup_directory(self) -> Optional[str]:
        """Returns the path to this server's specific backup directory."""
        backup_base_dir = self.settings.get("BACKUP_DIR")
        if not backup_base_dir:
            self.logger.warning(
                f"BACKUP_DIR not configured in settings. Cannot determine backup directory for '{self.server_name}'."
            )
            return None
        return os.path.join(backup_base_dir, self.server_name)

    @staticmethod
    def _find_and_sort_backups(pattern: str) -> List[str]:
        """
        Private static helper to find files using a glob pattern and sort them by
        modification time (newest first).
        """
        files = glob.glob(pattern)
        if not files:
            return []
        # Sort by modification time, descending
        return sorted(files, key=os.path.getmtime, reverse=True)

    def list_backups(self, backup_type: str) -> Union[List[str], Dict[str, List[str]]]:
        """
        Core logic to retrieve a list of backup files for this server.

        Args:
            backup_type: The type of backups to list ("world", "properties", "allowlist", "permissions", or "all").

        Returns:
            - A list of backup file paths, sorted newest first.
            - OR a dictionary of categorized backup file lists for the "all" type.
            - Returns an empty list/dict if the backup directory doesn't exist.

        Raises:
            MissingArgumentError: If `backup_type` is empty.
            UserInputError: If `backup_type` is invalid.
            ConfigurationError: If BACKUP_DIR setting is missing.
            FileOperationError: If a filesystem error occurs.
        """
        if not backup_type:
            raise MissingArgumentError("Backup type cannot be empty.")

        server_bck_dir = self.server_backup_directory
        if not server_bck_dir:
            raise ConfigurationError(
                f"Cannot list backups for '{self.server_name}': Backup directory not configured."
            )

        backup_type_norm = backup_type.lower()
        self.logger.info(
            f"Server '{self.server_name}': Listing '{backup_type_norm}' backups from '{server_bck_dir}'."
        )

        if not os.path.isdir(server_bck_dir):
            self.logger.warning(
                f"Backup directory not found: '{server_bck_dir}'. Returning empty result."
            )
            return {} if backup_type_norm == "all" else []

        try:
            # Define patterns for each backup type
            patterns = {
                "world": os.path.join(server_bck_dir, "*.mcworld"),
                "properties": os.path.join(
                    server_bck_dir, "server_backup_*.properties"
                ),
                "allowlist": os.path.join(server_bck_dir, "allowlist_backup_*.json"),
                "permissions": os.path.join(
                    server_bck_dir, "permissions_backup_*.json"
                ),
            }

            if backup_type_norm in patterns:
                return self._find_and_sort_backups(patterns[backup_type_norm])

            elif backup_type_norm == "all":
                categorized_backups: Dict[str, List[str]] = {}
                for key, pattern in patterns.items():
                    files = self._find_and_sort_backups(pattern)
                    if files:
                        categorized_backups[f"{key}_backups"] = files
                return categorized_backups

            else:
                valid_types = list(patterns.keys()) + ["all"]
                raise UserInputError(
                    f"Invalid backup type: '{backup_type}'. Must be one of {valid_types}."
                )

        except OSError as e:
            self.logger.error(
                f"Filesystem error while listing backups in '{server_bck_dir}': {e}",
                exc_info=True,
            )
            # Re-raise as a custom, more abstract exception
            raise FileOperationError(
                f"Error listing backups for '{self.server_name}' due to a filesystem issue: {e}"
            ) from e

    def prune_server_backups(self, component_prefix: str, file_extension: str) -> None:
        """
        Removes the oldest backups for a specific component of this server.
        Uses BACKUP_KEEP setting for the number of backups to retain.

        Args:
            component_prefix: Prefix for the backup files (e.g., "MyWorld_backup_", "server.properties_backup_").
            file_extension: Extension of the backup files (e.g., "mcworld", "json").
        """
        server_bck_dir = self.server_backup_directory
        if not server_bck_dir:
            raise ConfigurationError(
                f"Cannot prune backups for '{self.server_name}': Backup directory not configured."
            )

        backup_keep_count = self.settings.get(
            "BACKUP_KEEP", 3
        )  # Default to 3 if not set

        self.logger.info(
            f"Server '{self.server_name}': Pruning backups in '{server_bck_dir}' for prefix '{component_prefix}', ext '{file_extension}', keeping {backup_keep_count}."
        )

        if not os.path.isdir(server_bck_dir):
            self.logger.info(
                f"Backup directory '{server_bck_dir}' for server '{self.server_name}' not found. Nothing to prune."
            )
            return

        try:
            num_to_keep = int(backup_keep_count)
            if num_to_keep < 0:
                raise ValueError("Cannot be negative.")
        except ValueError:
            self.logger.error(
                f"Invalid BACKUP_KEEP value '{backup_keep_count}'. Must be int >= 0."
            )
            raise UserInputError(f"Invalid BACKUP_KEEP value: {backup_keep_count}")

        cleaned_ext = file_extension.lstrip(".")
        glob_pattern = os.path.join(
            server_bck_dir, f"{component_prefix}*.{cleaned_ext}"
        )
        self.logger.debug(f"Using glob pattern for pruning: '{glob_pattern}'")

        try:
            # Sort by modification time, newest first
            backup_files = sorted(
                glob.glob(glob_pattern), key=os.path.getmtime, reverse=True
            )

            if len(backup_files) > num_to_keep:
                files_to_delete = backup_files[num_to_keep:]
                self.logger.info(
                    f"Found {len(backup_files)} backups for '{component_prefix}*.{cleaned_ext}'. Deleting {len(files_to_delete)} oldest."
                )
                deleted_count = 0
                for old_backup_path in files_to_delete:
                    try:
                        self.logger.info(
                            f"Removing old backup: {os.path.basename(old_backup_path)}"
                        )
                        os.remove(old_backup_path)
                        deleted_count += 1
                    except OSError as e_del:
                        self.logger.error(
                            f"Failed to remove old backup '{old_backup_path}': {e_del}"
                        )
                if deleted_count < len(files_to_delete):
                    # Not all intended files were deleted, this is an issue.
                    raise FileOperationError(
                        f"Failed to delete all required old backups for '{component_prefix}' for server '{self.server_name}'."
                    )
            else:
                self.logger.info(
                    f"Found {len(backup_files)} backups for '{component_prefix}*.{cleaned_ext}', which is <= {num_to_keep}. No files deleted."
                )
        except OSError as e_glob:  # Error during glob or os.remove
            self.logger.error(
                f"OS error during backup pruning for '{self.server_name}': {e_glob}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Error pruning backups for '{self.server_name}': {e_glob}"
            ) from e_glob

    def _backup_world_data_internal(self) -> str:
        """
        Backs up this server's active world directory as an .mcworld file.
        Returns the path to the created .mcworld backup file.
        """
        active_world_name = self.get_world_name()  # From StateMixin
        active_world_dir_path = os.path.join(
            self.server_dir, "worlds", active_world_name
        )

        server_bck_dir = self.server_backup_directory
        if not server_bck_dir:
            raise ConfigurationError(
                f"Cannot backup world for '{self.server_name}': Backup directory not configured."
            )

        self.logger.info(
            f"Server '{self.server_name}': Starting backup for world '{active_world_name}' from '{active_world_dir_path}'."
        )

        if not os.path.isdir(active_world_dir_path):
            raise AppFileNotFoundError(active_world_dir_path, "Active world directory")

        os.makedirs(server_bck_dir, exist_ok=True)

        timestamp = general.get_timestamp()
        # Sanitize world name for filename if it can contain problematic characters
        safe_world_name_for_file = re.sub(r'[<>:"/\\|?*]', "_", active_world_name)
        backup_filename = f"{safe_world_name_for_file}_backup_{timestamp}.mcworld"
        backup_file_path = os.path.join(server_bck_dir, backup_filename)

        self.logger.info(
            f"Creating world backup: '{backup_filename}' in '{server_bck_dir}'..."
        )
        try:
            # self.export_world_directory_to_mcworld is from ServerWorldMixin
            self.export_world_directory_to_mcworld(active_world_name, backup_file_path)
            self.logger.info(
                f"World backup for '{self.server_name}' created: {backup_file_path}"
            )
            self.prune_server_backups(
                f"{safe_world_name_for_file}_backup_", "mcworld"
            )  # Prune after successful backup
            return backup_file_path
        except (
            BackupRestoreError,
            FileOperationError,
            AppFileNotFoundError,
        ) as e_export:  # Errors from export_world_directory_to_mcworld
            self.logger.error(
                f"Failed to export world '{active_world_name}' for server '{self.server_name}': {e_export}",
                exc_info=True,
            )
            raise  # Re-raise critical export errors
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error exporting world '{active_world_name}' for server '{self.server_name}': {e_unexp}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Unexpected error exporting world '{active_world_name}' for '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def _backup_config_file_internal(
        self, config_filename_in_server_dir: str
    ) -> Optional[str]:
        """
        Backs up a single configuration file from this server's directory.
        Returns the path to the backup file, or None if original file not found.
        """
        file_to_backup_path = os.path.join(
            self.server_dir, config_filename_in_server_dir
        )

        server_bck_dir = self.server_backup_directory
        if not server_bck_dir:
            raise ConfigurationError(
                f"Cannot backup config for '{self.server_name}': Backup directory not configured."
            )

        self.logger.info(
            f"Server '{self.server_name}': Starting backup for config file '{config_filename_in_server_dir}'."
        )

        if not os.path.isfile(file_to_backup_path):
            self.logger.warning(
                f"Config file '{config_filename_in_server_dir}' not found at '{file_to_backup_path}'. Skipping backup."
            )
            return None

        os.makedirs(server_bck_dir, exist_ok=True)

        name_part, ext_part = os.path.splitext(config_filename_in_server_dir)
        timestamp = general.get_timestamp()
        backup_config_filename = f"{name_part}_backup_{timestamp}{ext_part}"
        backup_destination_path = os.path.join(server_bck_dir, backup_config_filename)

        try:
            shutil.copy2(file_to_backup_path, backup_destination_path)
            self.logger.info(
                f"Config file '{config_filename_in_server_dir}' backed up to '{backup_destination_path}'."
            )
            self.prune_server_backups(
                f"{name_part}_backup_", ext_part.lstrip(".")
            )  # Prune after successful backup
            return backup_destination_path
        except OSError as e:
            self.logger.error(
                f"Failed to copy config '{file_to_backup_path}' to '{backup_destination_path}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to copy config '{config_filename_in_server_dir}' for '{self.server_name}': {e}"
            ) from e

    def backup_all_data(self) -> Dict[str, Optional[str]]:
        """
        Performs a full backup of this server: its active world and standard config files.
        Returns a dictionary of backed up components and their paths.
        """
        server_bck_dir = self.server_backup_directory
        if not server_bck_dir:
            raise ConfigurationError(
                f"Cannot backup server '{self.server_name}': Backup directory not configured."
            )

        os.makedirs(
            server_bck_dir, exist_ok=True
        )  # Ensure server's specific backup dir exists

        self.logger.info(
            f"Server '{self.server_name}': Starting full backup into '{server_bck_dir}'."
        )
        backup_results: Dict[str, Optional[str]] = {}
        world_backup_failed = False

        try:
            backup_results["world"] = self._backup_world_data_internal()
        except Exception as e:
            self.logger.error(
                f"CRITICAL: World backup failed for server '{self.server_name}': {e}",
                exc_info=True,
            )
            backup_results["world"] = None
            world_backup_failed = True  # Flag critical failure

        config_files = ["allowlist.json", "permissions.json", "server.properties"]
        for conf_file in config_files:
            try:
                backup_results[conf_file] = self._backup_config_file_internal(conf_file)
            except Exception as e:  # Catch errors from individual config backup
                self.logger.error(
                    f"Failed to back up config '{conf_file}' for '{self.server_name}': {e}",
                    exc_info=True,
                )
                backup_results[conf_file] = None

        if (
            world_backup_failed
        ):  # If world backup (most critical) failed, raise overall error
            raise BackupRestoreError(
                f"Core world backup failed for server '{self.server_name}'. Other components may or may not have succeeded."
            )

        return backup_results

    def _restore_config_file_internal(self, backup_config_file_path: str) -> str:
        """Restores a single config file from backup to this server's directory."""
        backup_filename_basename = os.path.basename(backup_config_file_path)
        self.logger.info(
            f"Server '{self.server_name}': Restoring config from backup '{backup_filename_basename}'."
        )

        if not os.path.isfile(backup_config_file_path):  # Changed from os.path.exists
            raise AppFileNotFoundError(backup_config_file_path, "Backup config file")

        # self.server_dir must exist for restore target
        os.makedirs(self.server_dir, exist_ok=True)

        # Regex to extract original name: (name_part)_backup_YYYYMMDD_HHMMSS(.ext_part)
        match = re.match(r"^(.*?)_backup_\d{8}_\d{6}(\..*)$", backup_filename_basename)
        if not match:
            raise UserInputError(
                f"Could not determine original filename from backup format: '{backup_filename_basename}'"
            )

        original_name_part, original_ext_part = match.group(1), match.group(2)
        target_filename_in_server = f"{original_name_part}{original_ext_part}"
        target_restore_path = os.path.join(self.server_dir, target_filename_in_server)

        self.logger.info(
            f"Restoring '{backup_filename_basename}' as '{target_filename_in_server}' into '{self.server_dir}'..."
        )
        try:
            shutil.copy2(backup_config_file_path, target_restore_path)
            self.logger.info(f"Successfully restored config to: {target_restore_path}")
            return target_restore_path
        except OSError as e:
            self.logger.error(
                f"Failed to copy backup '{backup_filename_basename}' to '{target_restore_path}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to restore config '{target_filename_in_server}' for server '{self.server_name}': {e}"
            ) from e

    def restore_all_data_from_latest(self) -> Dict[str, Optional[str]]:
        """
        Restores this server to its latest backed-up state (active world and config files).
        Returns a dictionary of restored components and their paths in the server directory.
        """
        server_bck_dir = self.server_backup_directory
        if not server_bck_dir or not os.path.isdir(server_bck_dir):
            self.logger.warning(
                f"No backup directory found for server '{self.server_name}' at '{server_bck_dir}'. Cannot restore."
            )
            return {}

        self.logger.info(
            f"Server '{self.server_name}': Starting restore from latest backups in '{server_bck_dir}'."
        )
        os.makedirs(self.server_dir, exist_ok=True)  # Ensure server install dir exists

        restore_results: Dict[str, Optional[str]] = {}
        failures = []

        # Restore World (latest .mcworld)
        try:
            world_backup_files = glob.glob(os.path.join(server_bck_dir, "*.mcworld"))
            # Further filter for this server's world backups, assuming world name is in prefix
            active_world_name = (
                self.get_world_name()
            )  # Get current world name to find its backups
            safe_world_name_prefix = (
                re.sub(r'[<>:"/\\|?*]', "_", active_world_name) + "_backup_"
            )

            relevant_world_backups = [
                fpath
                for fpath in world_backup_files
                if os.path.basename(fpath).startswith(safe_world_name_prefix)
            ]

            if relevant_world_backups:
                latest_world_backup_path = max(
                    relevant_world_backups, key=os.path.getmtime
                )
                self.logger.info(
                    f"Found latest world backup: {os.path.basename(latest_world_backup_path)}"
                )
                # self.import_active_world_from_mcworld is from ServerWorldMixin
                # It restores to the server's currently configured active world.
                imported_world_name_check = self.import_active_world_from_mcworld(
                    latest_world_backup_path
                )
                # The path stored should be the path to the world directory itself.
                restore_results["world"] = os.path.join(
                    self.server_dir, "worlds", imported_world_name_check
                )
            else:
                self.logger.info(
                    f"No .mcworld backups found for active world '{active_world_name}' of server '{self.server_name}'. Skipping world restore."
                )
                restore_results["world"] = None
        except Exception as e_world_restore:  # Catch broad errors for this component
            self.logger.error(
                f"Failed to restore world for '{self.server_name}': {e_world_restore}",
                exc_info=True,
            )
            failures.append(f"World ({type(e_world_restore).__name__})")
            restore_results["world"] = None

        # Restore Config Files
        config_files_to_restore_info = {
            "server.properties": "server.properties_backup_",
            "allowlist.json": "allowlist_backup_",
            "permissions.json": "permissions_backup_",
        }
        for (
            original_conf_name,
            backup_name_prefix_in_glob,
        ) in config_files_to_restore_info.items():
            try:
                name_part, ext_part = os.path.splitext(
                    original_conf_name
                )  # e.g. "server", ".properties"
                # Construct a glob pattern that matches {name_part}_backup_TIMESTAMP{ext_part}
                glob_pattern_for_config = os.path.join(
                    server_bck_dir, f"{name_part}_backup_*{ext_part}"
                )

                self.logger.debug(
                    f"Searching for '{original_conf_name}' backups with pattern: '{os.path.basename(glob_pattern_for_config)}'"
                )

                # Exact regex from original restore_all_server_data for stricter matching of backup format
                backup_file_regex = re.compile(
                    f"^{re.escape(name_part)}_backup_\\d{{8}}_\\d{{6}}{re.escape(ext_part)}$"
                )

                candidate_backups = [
                    os.path.join(server_bck_dir, fname)
                    for fname in os.listdir(server_bck_dir)
                    if backup_file_regex.match(fname)
                ]

                if candidate_backups:
                    latest_config_backup_path = max(
                        candidate_backups, key=os.path.getmtime
                    )
                    self.logger.info(
                        f"Found latest '{original_conf_name}' backup: {os.path.basename(latest_config_backup_path)}"
                    )
                    restored_config_path = self._restore_config_file_internal(
                        latest_config_backup_path
                    )
                    restore_results[original_conf_name] = restored_config_path
                else:
                    self.logger.info(
                        f"No backups found for '{original_conf_name}'. Skipping."
                    )
                    restore_results[original_conf_name] = None
            except Exception as e_conf_restore:
                self.logger.error(
                    f"Failed to restore '{original_conf_name}' for '{self.server_name}': {e_conf_restore}",
                    exc_info=True,
                )
                failures.append(
                    f"{original_conf_name} ({type(e_conf_restore).__name__})"
                )
                restore_results[original_conf_name] = None

        if failures:
            raise BackupRestoreError(
                f"Restore for server '{self.server_name}' completed with errors: {', '.join(failures)}"
            )

        self.logger.info(f"Restore process completed for server '{self.server_name}'.")
        return restore_results
