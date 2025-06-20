# bedrock_server_manager/core/server/backup_restore_mixin.py
"""Provides the ServerBackupMixin for the BedrockServer class.

This mixin encapsulates all backup and restore operations for a server
instance. It handles backing up worlds and configuration files, listing
available backups, restoring from those backups, and pruning old backup files
according to retention policies.
"""
import os
import glob
import re
import shutil
import logging
from typing import Optional, Dict, TYPE_CHECKING, List, Union

# Local application imports.
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
    """A mixin for BedrockServer providing backup, restore, and prune methods.

    This class handles the logic for managing backups of server data, including
    worlds and configuration files. It also includes functionality for pruning
    old backups based on the application's retention settings.
    """

    def __init__(self, *args, **kwargs):
        """Initializes the ServerBackupMixin.

        This constructor calls `super().__init__` to ensure proper method
        resolution order in the context of multiple inheritance. It relies on
        attributes (like `server_name`, `server_dir`, `settings`, `logger`)
        and methods (like `get_world_name`) being available from other mixins
        or the base `BedrockServer` class.
        """
        super().__init__(*args, **kwargs)
        # This mixin depends on attributes from BaseMixin: self.server_name, self.server_dir, self.logger, self.settings.
        # It also depends on methods from other mixins that will be part of the final BedrockServer class, such as:
        # - self.get_world_name() (from StateMixin)
        # - self.export_world_directory_to_mcworld() (from WorldMixin)
        # - self.import_active_world_from_mcworld() (from WorldMixin)

    @property
    def server_backup_directory(self) -> Optional[str]:
        """Returns the path to this server's specific backup directory.

        The path is constructed from the `BACKUP_DIR` setting and the server's name.

        Returns:
            The absolute path to the backup directory, or `None` if `BACKUP_DIR`
            is not configured in the settings.
        """
        backup_base_dir = self.settings.get("BACKUP_DIR")
        if not backup_base_dir:
            self.logger.warning(
                f"BACKUP_DIR not configured in settings. Cannot determine backup directory for '{self.server_name}'."
            )
            return None
        return os.path.join(backup_base_dir, self.server_name)

    @staticmethod
    def _find_and_sort_backups(pattern: str) -> List[str]:
        """Finds files using a glob pattern and sorts them by modification time.

        Args:
            pattern: The glob pattern to search for files.

        Returns:
            A list of file paths sorted from newest to oldest.
        """
        files = glob.glob(pattern)
        if not files:
            return []
        # Sort by modification time, descending (newest first).
        return sorted(files, key=os.path.getmtime, reverse=True)

    def list_backups(self, backup_type: str) -> Union[List[str], Dict[str, List[str]]]:
        """Retrieves a list of available backup files for this server.

        Args:
            backup_type: The type of backups to list. Valid options are:
                "world", "properties", "allowlist", "permissions", or "all".

        Returns:
            If `backup_type` is specific (e.g., "world"), returns a list of
            backup file paths, sorted newest first.
            If `backup_type` is "all", returns a dictionary where keys are
            backup categories (e.g., "world_backups") and values are the
            sorted lists of file paths.
            Returns an empty list or dictionary if the backup directory doesn't exist.

        Raises:
            MissingArgumentError: If `backup_type` is empty.
            UserInputError: If `backup_type` is not a valid option.
            ConfigurationError: If the `BACKUP_DIR` setting is missing.
            FileOperationError: If a filesystem error occurs during listing.
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
            # Define glob patterns for each type of backup.
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
            raise FileOperationError(
                f"Error listing backups for '{self.server_name}' due to a filesystem issue: {e}"
            ) from e

    def prune_server_backups(self, component_prefix: str, file_extension: str):
        """Removes the oldest backups for a component, respecting retention settings.

        This method uses the `BACKUP_KEEP` setting to determine how many recent
        backups of a specific type to retain, deleting any older ones.

        Args:
            component_prefix: The prefix of the backup files to target
                (e.g., "MyWorld_backup_", "server.properties_backup_").
            file_extension: The extension of the backup files (e.g., "mcworld", "json").

        Raises:
            ConfigurationError: If the backup directory is not configured.
            UserInputError: If the `BACKUP_KEEP` setting is invalid.
            FileOperationError: If an OS error occurs during file deletion.
        """
        server_bck_dir = self.server_backup_directory
        if not server_bck_dir:
            raise ConfigurationError(
                f"Cannot prune backups for '{self.server_name}': Backup directory not configured."
            )

        backup_keep_count = self.settings.get("BACKUP_KEEP", 3)

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
        except (ValueError, TypeError):
            raise UserInputError(
                f"Invalid BACKUP_KEEP setting value: '{backup_keep_count}'. Must be a non-negative integer."
            )

        cleaned_ext = file_extension.lstrip(".")
        glob_pattern = os.path.join(
            server_bck_dir, f"{component_prefix}*.{cleaned_ext}"
        )
        self.logger.debug(f"Using glob pattern for pruning: '{glob_pattern}'")

        try:
            # Sort by modification time to identify the oldest files.
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
                    raise FileOperationError(
                        f"Failed to delete all required old backups for '{component_prefix}' for server '{self.server_name}'."
                    )
            else:
                self.logger.info(
                    f"Found {len(backup_files)} backups for '{component_prefix}*.{cleaned_ext}', which is <= {num_to_keep}. No files deleted."
                )
        except OSError as e_glob:
            raise FileOperationError(
                f"Error pruning backups for '{self.server_name}': {e_glob}"
            ) from e_glob

    def _backup_world_data_internal(self) -> str:
        """Backs up the server's active world to a .mcworld file.

        This is an internal helper that orchestrates getting the world name,
        exporting it, and then pruning old world backups.

        Returns:
            The path to the created .mcworld backup file.

        Raises:
            ConfigurationError: If the backup directory is not configured.
            AppFileNotFoundError: If the active world directory does not exist.
            FileOperationError: For any other file I/O errors during the process.
        """
        active_world_name = self.get_world_name()
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
        # Sanitize the world name to ensure it's a valid filename component.
        safe_world_name_for_file = re.sub(r'[<>:"/\\|?*]', "_", active_world_name)
        backup_filename = f"{safe_world_name_for_file}_backup_{timestamp}.mcworld"
        backup_file_path = os.path.join(server_bck_dir, backup_filename)

        self.logger.info(
            f"Creating world backup: '{backup_filename}' in '{server_bck_dir}'..."
        )
        try:
            # This method is expected to be on the final class from WorldMixin.
            self.export_world_directory_to_mcworld(active_world_name, backup_file_path)
            self.logger.info(
                f"World backup for '{self.server_name}' created: {backup_file_path}"
            )
            # Prune old backups after a new one is successfully created.
            self.prune_server_backups(f"{safe_world_name_for_file}_backup_", "mcworld")
            return backup_file_path
        except (
            BackupRestoreError,
            FileOperationError,
            AppFileNotFoundError,
        ) as e_export:
            self.logger.error(
                f"Failed to export world '{active_world_name}' for server '{self.server_name}': {e_export}",
                exc_info=True,
            )
            raise
        except Exception as e_unexp:
            raise FileOperationError(
                f"Unexpected error exporting world '{active_world_name}' for '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def _backup_config_file_internal(
        self, config_filename_in_server_dir: str
    ) -> Optional[str]:
        """Backs up a single configuration file from the server's directory.

        Args:
            config_filename_in_server_dir: The name of the file to back up
                (e.g., "server.properties").

        Returns:
            The path to the created backup file, or `None` if the original
            file was not found.

        Raises:
            ConfigurationError: If the backup directory is not configured.
            FileOperationError: If the file copy operation fails.
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
            # copy2 preserves metadata like modification time.
            shutil.copy2(file_to_backup_path, backup_destination_path)
            self.logger.info(
                f"Config file '{config_filename_in_server_dir}' backed up to '{backup_destination_path}'."
            )
            # Prune old backups of this specific config file.
            self.prune_server_backups(f"{name_part}_backup_", ext_part.lstrip("."))
            return backup_destination_path
        except OSError as e:
            raise FileOperationError(
                f"Failed to copy config '{config_filename_in_server_dir}' for '{self.server_name}': {e}"
            ) from e

    def backup_all_data(self) -> Dict[str, Optional[str]]:
        """Performs a full backup of the server's world and standard configs.

        This method orchestrates the backup of the active world and key
        configuration files (`allowlist.json`, `permissions.json`,
        `server.properties`).

        Returns:
            A dictionary mapping component names to their backup file paths.
            A value will be `None` if that component's backup failed.

        Raises:
            ConfigurationError: If the backup directory is not configured.
            BackupRestoreError: If the critical world backup fails.
        """
        server_bck_dir = self.server_backup_directory
        if not server_bck_dir:
            raise ConfigurationError(
                f"Cannot backup server '{self.server_name}': Backup directory not configured."
            )

        os.makedirs(server_bck_dir, exist_ok=True)

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
            world_backup_failed = True  # Flag that the most critical part failed.

        config_files = ["allowlist.json", "permissions.json", "server.properties"]
        for conf_file in config_files:
            try:
                backup_results[conf_file] = self._backup_config_file_internal(conf_file)
            except Exception as e:
                self.logger.error(
                    f"Failed to back up config '{conf_file}' for '{self.server_name}': {e}",
                    exc_info=True,
                )
                backup_results[conf_file] = None

        # If the world backup failed, the overall operation is considered a failure.
        if world_backup_failed:
            raise BackupRestoreError(
                f"Core world backup failed for server '{self.server_name}'. Other components may or may not have succeeded."
            )

        return backup_results

    def _restore_config_file_internal(self, backup_config_file_path: str) -> str:
        """Restores a single config file from a backup to the server directory.

        This internal helper determines the original filename from the backup's
        timestamped name and copies it to the correct location.

        Args:
            backup_config_file_path: The path to the backup file to restore.

        Returns:
            The path of the restored file in the server directory.

        Raises:
            AppFileNotFoundError: If the backup file does not exist.
            UserInputError: If the backup filename is not in the expected format.
            FileOperationError: If the file copy operation fails.
        """
        backup_filename_basename = os.path.basename(backup_config_file_path)
        self.logger.info(
            f"Server '{self.server_name}': Restoring config from backup '{backup_filename_basename}'."
        )

        if not os.path.isfile(backup_config_file_path):
            raise AppFileNotFoundError(backup_config_file_path, "Backup config file")

        os.makedirs(self.server_dir, exist_ok=True)

        # Regex to extract original name: (name_part)_backup_YYYYMMDD_HHMMSS(.ext_part).
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
            raise FileOperationError(
                f"Failed to restore config '{target_filename_in_server}' for server '{self.server_name}': {e}"
            ) from e

    def restore_all_data_from_latest(self) -> Dict[str, Optional[str]]:
        """Restores the server from the latest available backups.

        This method finds the most recent backup for the active world and each
        standard configuration file and restores them, overwriting current files.

        Returns:
            A dictionary mapping restored components to their paths in the
            server directory. Returns an empty dictionary if no backup
            directory was found.

        Raises:
            BackupRestoreError: If one or more components fail to restore.
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
        os.makedirs(self.server_dir, exist_ok=True)

        restore_results: Dict[str, Optional[str]] = {}
        failures = []

        # Restore World from the latest .mcworld backup for the active world.
        try:
            world_backup_files = glob.glob(os.path.join(server_bck_dir, "*.mcworld"))
            active_world_name = self.get_world_name()
            safe_world_name_prefix = (
                re.sub(r'[<>:"/\\|?*]', "_", active_world_name) + "_backup_"
            )
            relevant_world_backups = [
                f
                for f in world_backup_files
                if os.path.basename(f).startswith(safe_world_name_prefix)
            ]

            if relevant_world_backups:
                latest_world_backup_path = max(
                    relevant_world_backups, key=os.path.getmtime
                )
                self.logger.info(
                    f"Found latest world backup: {os.path.basename(latest_world_backup_path)}"
                )
                # This method is expected to be on the final class from WorldMixin.
                imported_world_name_check = self.import_active_world_from_mcworld(
                    latest_world_backup_path
                )
                restore_results["world"] = os.path.join(
                    self.server_dir, "worlds", imported_world_name_check
                )
            else:
                self.logger.info(
                    f"No .mcworld backups found for active world '{active_world_name}' of server '{self.server_name}'. Skipping world restore."
                )
                restore_results["world"] = None
        except Exception as e_world_restore:
            self.logger.error(
                f"Failed to restore world for '{self.server_name}': {e_world_restore}",
                exc_info=True,
            )
            failures.append(f"World ({type(e_world_restore).__name__})")
            restore_results["world"] = None

        # Restore standard configuration files.
        config_files_to_restore_info = {
            "server.properties": "server.properties_backup_",
            "allowlist.json": "allowlist_backup_",
            "permissions.json": "permissions_backup_",
        }
        for original_conf_name, _ in config_files_to_restore_info.items():
            try:
                name_part, ext_part = os.path.splitext(original_conf_name)
                # Stricter regex to match the exact backup format and avoid false positives.
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
