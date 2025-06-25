# bedrock_server_manager/core/server/installation_mixin.py
"""Provides the ServerInstallationMixin for the BedrockServer class.

This mixin handles the validation of server installations, setting filesystem
permissions, and the comprehensive deletion of all server-related data. This
includes the server's installation files, its JSON configuration, all backups,
and any associated systemd services on Linux.
"""
import os
import shutil
import subprocess

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.error import (
    AppFileNotFoundError,
    MissingArgumentError,
    FileOperationError,
    PermissionsError,
    ServerStopError,
)


class ServerInstallationMixin(BedrockServerBaseMixin):
    """A mixin for BedrockServer providing installation, permission, and deletion methods.

    This class handles the validation of an installation's existence, the setting
    of appropriate filesystem permissions, and the complete, destructive removal
    of a server instance and all its associated data.
    """

    def __init__(self, *args, **kwargs):
        """Initializes the ServerInstallationMixin.
        This constructor calls `super().__init__` to ensure proper method
        resolution order in the context of multiple inheritance. It relies on
        attributes and methods from other mixins or the base class.
        """
        super().__init__(*args, **kwargs)
        # Attributes like self.server_name, self.server_dir, self.logger,
        # and self.bedrock_executable_path are available from BedrockServerBaseMixin.
        # Methods like self.is_running() and self.stop() are expected to be
        # available from the ProcessMixin on the final BedrockServer class.

    def validate_installation(self) -> bool:
        """Validates that the server installation is minimally correct.

        This check ensures that the main server directory and the server
        executable file within it both exist.

        Returns:
            True if the server installation is valid.

        Raises:
            AppFileNotFoundError: If the server directory or the executable
                file does not exist.
        """
        self.logger.debug(
            f"Validating installation for server '{self.server_name}' in directory: {self.server_dir}"
        )

        if not os.path.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")

        if not os.path.isfile(self.bedrock_executable_path):
            raise AppFileNotFoundError(
                self.bedrock_executable_path, "Server executable"
            )

        self.logger.debug(
            f"Server '{self.server_name}' installation validation successful."
        )
        return True

    def is_installed(self) -> bool:
        """Checks if the server installation is valid without raising an exception.

        This is a convenience method that wraps `validate_installation` in a
        try-except block.

        Returns:
            True if the installation is valid, False otherwise.
        """
        try:
            return self.validate_installation()
        except AppFileNotFoundError:
            self.logger.debug(
                f"is_installed check: Server '{self.server_name}' not found or installation invalid."
            )
            return False

    def set_filesystem_permissions(self):
        """Sets appropriate file and directory permissions for the server.

        This method wraps the core `system_base.set_server_folder_permissions`
        function to apply the necessary permissions to the server's
        installation directory, which is crucial for proper operation,
        especially on Linux.

        Raises:
            AppFileNotFoundError: If the server is not installed.
            PermissionsError: If setting permissions fails.
        """
        if not self.is_installed():
            raise AppFileNotFoundError(self.server_dir, "Server installation directory")

        self.logger.info(
            f"Setting filesystem permissions for server directory: {self.server_dir}"
        )
        try:
            system_base.set_server_folder_permissions(self.server_dir)
            self.logger.info(f"Successfully set permissions for '{self.server_dir}'.")
        except (MissingArgumentError, AppFileNotFoundError, PermissionsError) as e:
            self.logger.error(f"Failed to set permissions for '{self.server_dir}': {e}")
            raise
        except Exception as e_unexp:
            raise PermissionsError(
                f"Unexpected error setting permissions for '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def delete_server_files(
        self, item_description_prefix: str = "server files for"
    ) -> bool:
        """Deletes the server's entire installation directory (`self.server_dir`).

        THIS IS A DESTRUCTIVE OPERATION. It uses a robust deletion utility to
        handle potential file permission issues.

        Args:
            item_description_prefix: A prefix for the logging message to provide
                context (e.g., "server files for").

        Returns:
            True if deletion was successful or the directory didn't exist,
            False otherwise.
        """
        self.logger.warning(
            f"Attempting to delete all files for server '{self.server_name}' at: {self.server_dir}. THIS IS DESTRUCTIVE."
        )
        description = f"{item_description_prefix} server '{self.server_name}'"

        success = system_base.delete_path_robustly(self.server_dir, description)
        if success:
            self.logger.info(
                f"Successfully deleted server directory for '{self.server_name}'."
            )
        else:
            self.logger.error(
                f"Failed to fully delete server directory for '{self.server_name}'. Review logs for details."
            )
        return success

    def delete_all_data(self):
        """Deletes all data associated with this Bedrock server.

        This is a comprehensive and destructive operation that removes:
        1. The server's installation directory.
        2. The server's JSON configuration subdirectory.
        3. The server's entire backup directory.
        4. The server's systemd service file (on Linux).
        5. The server's PID file.

        It will attempt to stop a running server before deletion.

        Raises:
            FileOperationError: If deleting one or more essential directories or
                files fails.
        """
        server_install_dir = self.server_dir
        server_json_config_subdir = self.server_config_dir

        # Determine the server's backup directory path.
        backup_base_dir = self.settings.get("BACKUP_DIR")
        server_backup_dir_path = (
            os.path.join(backup_base_dir, self.server_name) if backup_base_dir else None
        )

        self.logger.warning(
            f"!!! Preparing to delete ALL data for server '{self.server_name}' !!!"
        )
        self.logger.debug(f"Target installation directory: {server_install_dir}")
        self.logger.debug(
            f"Target JSON configuration directory: {server_json_config_subdir}"
        )
        if server_backup_dir_path:
            self.logger.debug(f"Target backup directory: {server_backup_dir_path}")

        # Check if any data exists to avoid unnecessary stop attempts.
        primary_data_paths = [server_install_dir, server_json_config_subdir]
        if server_backup_dir_path:
            primary_data_paths.append(server_backup_dir_path)
        any_primary_data_exists = any(
            os.path.exists(p) for p in primary_data_paths if p
        )

        # On Linux, also check for a systemd service file.
        systemd_service_file_path = None
        systemd_service_name = f"bedrock-{self.server_name}"
        if self.os_type == "Linux":
            systemd_service_file_path = os.path.join(
                os.path.expanduser("~/.config/systemd/user/"),
                f"{systemd_service_name}.service",
            )
            if os.path.exists(systemd_service_file_path):
                any_primary_data_exists = True

        if not any_primary_data_exists:
            self.logger.info(
                f"No data found for server '{self.server_name}'. Deletion skipped."
            )
            return

        # Ensure the server is stopped before deleting its files.
        if hasattr(self, "is_running") and hasattr(self, "stop"):
            if self.is_running():
                self.logger.info(
                    f"Server '{self.server_name}' is running. Attempting to stop it before deletion..."
                )
                try:
                    self.stop()
                except (ServerStopError, Exception) as e_stop:
                    self.logger.warning(
                        f"Failed to stop server '{self.server_name}' cleanly before deletion: {e_stop}. Proceeding with deletion, but the process might linger."
                    )
            else:
                self.logger.info(
                    f"Server '{self.server_name}' is not running. No stop needed."
                )
        else:
            self.logger.warning(
                "is_running or stop method not found on self. Cannot ensure server is stopped before deletion."
            )

        deletion_errors = []

        # --- 1. Remove systemd service (Linux-only) ---
        if (
            self.os_type == "Linux"
            and systemd_service_file_path
            and os.path.exists(systemd_service_file_path)
        ):
            self.logger.info(
                f"Processing systemd user service '{systemd_service_name}'..."
            )
            systemctl_cmd = shutil.which("systemctl")
            if systemctl_cmd:
                try:
                    # Disable and stop the service in one command.
                    disable_cmds = [
                        systemctl_cmd,
                        "--user",
                        "disable",
                        "--now",
                        systemd_service_name,
                    ]
                    self.logger.debug(f"Executing: {' '.join(disable_cmds)}")
                    res_disable = subprocess.run(
                        disable_cmds, check=False, capture_output=True, text=True
                    )
                    if (
                        res_disable.returncode != 0
                        and "doesn't exist" not in res_disable.stderr.lower()
                        and "no such file" not in res_disable.stderr.lower()
                    ):
                        self.logger.warning(
                            f"systemctl disable --now {systemd_service_name} failed: {res_disable.stderr.strip()}"
                        )

                    # Remove the service file itself.
                    if not system_base.delete_path_robustly(
                        systemd_service_file_path,
                        f"systemd service file for '{self.server_name}'",
                    ):
                        deletion_errors.append(
                            f"systemd service file '{systemd_service_file_path}'"
                        )
                    else:
                        # Reload the systemd daemon to apply changes.
                        self.logger.debug("Reloading systemd user daemon...")
                        subprocess.run(
                            [systemctl_cmd, "--user", "daemon-reload"],
                            check=False,
                            capture_output=True,
                        )
                        subprocess.run(
                            [systemctl_cmd, "--user", "reset-failed"],
                            check=False,
                            capture_output=True,
                        )
                        self.logger.info(
                            f"Systemd service '{systemd_service_name}' removed and daemon reloaded."
                        )
                except Exception as e_systemd:
                    self.logger.error(
                        f"Error managing systemd service '{systemd_service_name}': {e_systemd}",
                        exc_info=True,
                    )
                    deletion_errors.append(
                        f"systemd service interaction for '{systemd_service_name}'"
                    )
            else:
                # If systemctl isn't found, just delete the file.
                self.logger.warning(
                    f"Systemd service file '{systemd_service_file_path}' exists but 'systemctl' not found. Deleting file directly."
                )
                if not system_base.delete_path_robustly(
                    systemd_service_file_path,
                    f"systemd service file (no systemctl) for '{self.server_name}'",
                ):
                    deletion_errors.append(
                        f"systemd service file '{systemd_service_file_path}' (no systemctl)"
                    )

        # --- 2. Remove PID file ---
        pid_file_to_delete = self.get_pid_file_path()
        if os.path.exists(pid_file_to_delete):
            if not system_base.delete_path_robustly(
                pid_file_to_delete, f"PID file for '{self.server_name}'"
            ):
                deletion_errors.append(f"PID file '{pid_file_to_delete}'")

        # --- 3. Remove all directories ---
        paths_to_delete_map = {
            "backup": server_backup_dir_path,
            "installation": server_install_dir,
            "JSON configuration": server_json_config_subdir,
        }
        for dir_type, dir_path_val in paths_to_delete_map.items():
            if dir_path_val and os.path.exists(dir_path_val):
                if not system_base.delete_path_robustly(
                    dir_path_val, f"server {dir_type} data for '{self.server_name}'"
                ):
                    deletion_errors.append(f"{dir_type} directory '{dir_path_val}'")
            elif dir_path_val:
                self.logger.debug(
                    f"Server {dir_type} data for '{self.server_name}' at '{dir_path_val}' not found, skipping deletion."
                )

        # --- Final Check ---
        if deletion_errors:
            error_summary = "; ".join(deletion_errors)
            raise FileOperationError(
                f"Failed to completely delete server '{self.server_name}'. Failed items: {error_summary}"
            )
        else:
            self.logger.info(
                f"Successfully deleted all data for server: '{self.server_name}'."
            )
