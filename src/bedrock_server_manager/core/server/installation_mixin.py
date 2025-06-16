# bedrock_server_manager/core/server/installation_mixin.py
"""
Provides the ServerInstallationMixin class for BedrockServer.

This mixin handles validation of server installations, setting filesystem
permissions, and comprehensive deletion of server data including installation files,
configurations, backups, and systemd services.
"""
import os
import shutil
import subprocess

# Local imports
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
    """
    A mixin for the BedrockServer class that provides methods related to
    the installation state, filesystem permissions, and complete removal
    of a server instance.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the ServerInstallationMixin.

        Calls super().__init__ for proper multiple inheritance setup.
        Relies on attributes (like server_name, server_dir, logger,
        bedrock_executable_path, settings, os_type, _server_specific_config_dir,
        get_pid_file_path) and methods (like is_running, stop) from other
        mixins or the base class.
        """
        super().__init__(*args, **kwargs)
        # Attributes like self.server_name, self.server_dir, self.logger,
        # self.bedrock_executable_path are available from BedrockServerBaseMixin.

    def validate_installation(self) -> bool:
        """
        Validates if the server installation exists and seems minimally correct.
        Checks for the existence of the server directory and the server executable.

        Returns:
            True if the server installation is valid.

        Raises:
            AppFileNotFoundError: If the server directory or the executable file within it
                                 does not exist.
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
        """
        Checks if the server installation is valid without raising an exception.
        Returns True if valid, False otherwise.
        """
        try:
            return self.validate_installation()
        except AppFileNotFoundError:
            self.logger.debug(
                f"is_installed check: Server '{self.server_name}' not found or installation invalid."
            )
            return False

    def set_filesystem_permissions(self) -> None:
        """
        Sets appropriate file and directory permissions for this server's installation directory.
        Wraps system_base.set_server_folder_permissions.
        """
        if not self.is_installed():  # Use the non-raising check first
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
            self.logger.error(
                f"Unexpected error setting permissions for '{self.server_dir}': {e_unexp}",
                exc_info=True,
            )
            raise PermissionsError(
                f"Unexpected error setting permissions for '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def delete_server_files(
        self, item_description_prefix: str = "server files for"
    ) -> bool:
        """
        Deletes this server's entire directory (self.server_dir) robustly.
        USE WITH EXTREME CAUTION.

        Args:
            item_description_prefix: A prefix for the logging message.

        Returns:
            True if deletion was successful or path didn't exist, False otherwise.
        """
        self.logger.warning(
            f"Attempting to delete all files for server '{self.server_name}' at: {self.server_dir}. THIS IS DESTRUCTIVE."
        )
        # Construct a meaningful description for the robust deletion utility
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

    def delete_all_data(
        self,
    ) -> None:
        """
        Deletes all data associated with this Bedrock server, including its installation
        directory (self.server_dir), its JSON configuration folder
        (self._server_specific_config_dir), its backups (if BACKUP_DIR configured),
        and its systemd service file (on Linux).

        Raises:
            FileOperationError: If deleting essential directories fails or settings
                                (BACKUP_DIR) are missing when expected.
        """
        # server_name is self.server_name
        # base_dir is self.base_dir
        # effective_config_dir for the server's JSON config is self._server_specific_config_dir
        # global_app_config_dir for PID files is self.app_config_dir

        server_install_dir = self.server_dir  # from BaseMixin
        server_json_config_subdir = self._server_specific_config_dir  # from BaseMixin

        backup_base_dir = self.settings.get("BACKUP_DIR")
        server_backup_dir_path = None
        if backup_base_dir:
            server_backup_dir_path = os.path.join(backup_base_dir, self.server_name)
        else:
            self.logger.debug(
                f"BACKUP_DIR not configured. Skipping backup deletion for '{self.server_name}'."
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

        # Pre-check for existence of any data before attempting complex operations like stopping.
        # This is important because if directories are already gone, stopping might fail unnecessarily.
        primary_data_paths = [server_install_dir, server_json_config_subdir]
        if server_backup_dir_path:
            primary_data_paths.append(server_backup_dir_path)

        any_primary_data_exists = any(
            os.path.exists(p) for p in primary_data_paths if p
        )

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
                f"No data (install, config, backup, or systemd file) found for server '{self.server_name}'. Deletion skipped."
            )
            return

        # Ensure server is stopped before deleting files
        # This relies on self.stop() and self.is_running() from ProcessMixin
        if hasattr(self, "is_running") and hasattr(self, "stop"):
            if self.is_running():
                self.logger.info(
                    f"Server '{self.server_name}' is running. Attempting to stop it before deletion..."
                )
                try:
                    self.stop()  # Timeout is handled by stop()
                except ServerStopError as e:
                    self.logger.warning(
                        f"Failed to stop server '{self.server_name}' cleanly before deletion: {e}. Proceeding with deletion, but server process might linger."
                    )
                except Exception as e_stop:
                    self.logger.error(
                        f"Unexpected error stopping server '{self.server_name}' before deletion: {e_stop}. Proceeding cautiously.",
                        exc_info=True,
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

        # --- Remove systemd service (Linux) ---
        if (
            self.os_type == "Linux"
            and systemd_service_file_path
            and os.path.exists(systemd_service_file_path)
        ):
            self.logger.info(
                f"Processing systemd user service '{systemd_service_name}' for server '{self.server_name}'."
            )
            systemctl_cmd = shutil.which("systemctl")
            if systemctl_cmd:
                try:
                    # Stop and disable the service using --now
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

                    # Remove the service file
                    if not system_base.delete_path_robustly(
                        systemd_service_file_path,
                        f"systemd service file for '{self.server_name}'",
                    ):
                        deletion_errors.append(
                            f"systemd service file '{systemd_service_file_path}'"
                        )
                    else:
                        # Reload systemd daemon
                        reload_cmds = [systemctl_cmd, "--user", "daemon-reload"]
                        reset_failed_cmds = [systemctl_cmd, "--user", "reset-failed"]
                        self.logger.debug(f"Executing: {' '.join(reload_cmds)}")
                        subprocess.run(reload_cmds, check=False, capture_output=True)
                        self.logger.debug(f"Executing: {' '.join(reset_failed_cmds)}")
                        subprocess.run(
                            reset_failed_cmds, check=False, capture_output=True
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
            else:  # systemctl not found, but file exists
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

        # Remove PID file from global app config dir
        pid_file_to_delete = self.get_pid_file_path()  # From BaseMixin
        if os.path.exists(pid_file_to_delete):
            if not system_base.delete_path_robustly(
                pid_file_to_delete, f"PID file for '{self.server_name}'"
            ):
                deletion_errors.append(f"PID file '{pid_file_to_delete}'")

        # --- Remove directories ---
        paths_to_delete_map = {
            "backup": server_backup_dir_path,
            "installation": server_install_dir,
            "JSON configuration": server_json_config_subdir,
        }

        for dir_type, dir_path_val in paths_to_delete_map.items():
            if dir_path_val and os.path.exists(
                dir_path_val
            ):  # Check existence before deleting
                if not system_base.delete_path_robustly(
                    dir_path_val, f"server {dir_type} data for '{self.server_name}'"
                ):
                    deletion_errors.append(f"{dir_type} directory '{dir_path_val}'")
            elif dir_path_val:  # Path was defined but doesn't exist
                self.logger.debug(
                    f"Server {dir_type} data for '{self.server_name}' at '{dir_path_val}' not found, skipping deletion."
                )

        if deletion_errors:
            error_summary = "; ".join(deletion_errors)
            self.logger.error(
                f"Deletion of server '{self.server_name}' completed with errors. Failed items: {error_summary}"
            )
            raise FileOperationError(
                f"Failed to completely delete server '{self.server_name}'. Failed items: {error_summary}"
            )
        else:
            self.logger.info(
                f"Successfully deleted all data for server: '{self.server_name}'."
            )
