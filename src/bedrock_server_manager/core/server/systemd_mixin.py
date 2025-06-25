# bedrock_server_manager/core/server/systemd_mixin.py
"""Provides the ServerSystemdMixin for the BedrockServer class.

This mixin encapsulates all Linux-specific systemd service management for a
server instance. It allows for the creation, enabling, disabling, removal, and
status checking of systemd user services that manage the Bedrock server process,
facilitating background operation and autostart capabilities.
"""
import os
import platform
import shutil
import subprocess
import logging

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.system import linux as system_linux_utils
from bedrock_server_manager.error import (
    SystemError,
    CommandNotFoundError,
    FileOperationError,
    MissingArgumentError,
    AppFileNotFoundError,
)


class ServerSystemdMixin(BedrockServerBaseMixin):
    """A mixin for BedrockServer to manage a systemd user service (Linux-only).

    This class provides methods to create, enable, disable, remove, and check
    the status of a systemd service associated with the server instance.
    """

    def __init__(self, *args, **kwargs):
        """Initializes the ServerSystemdMixin.

        This constructor calls `super().__init__` to ensure proper method
        resolution order in the context of multiple inheritance. It relies on
        attributes (like `server_name`, `server_dir`, `manager_expath`, `os_type`)
        from the base class.
        """
        super().__init__(*args, **kwargs)
        # self.server_name, self.base_dir, self.manager_expath, self.logger, and self.os_type are available from BaseMixin.

    def _ensure_linux_for_systemd(self, operation_name: str):
        """A helper to verify the OS is Linux before a systemd operation.

        Args:
            operation_name: The name of the operation being attempted, for logging.

        Raises:
            SystemError: If the operating system is not Linux.
        """
        if self.os_type != "Linux":
            msg = f"Systemd operation '{operation_name}' is only supported on Linux. Server OS: {self.os_type}"
            self.logger.warning(msg)
            raise SystemError(msg)

    @property
    def systemd_service_name_full(self) -> str:
        """Returns the full systemd service name (e.g., 'bedrock-MyServer.service')."""
        return f"bedrock-{self.server_name}.service"

    def check_systemd_service_file_exists(self) -> bool:
        """Checks if the systemd service file for this server exists.

        Returns:
            True if the service file exists, False otherwise.
        """
        self._ensure_linux_for_systemd("check_systemd_service_file_exists")
        # Delegate the check to the generic system utility.
        return system_linux_utils.check_service_exists(self.systemd_service_name_full)

    def create_systemd_service_file(self):
        """Creates or updates the systemd user service file for this server.

        Raises:
            SystemError: If the OS is not Linux.
            AppFileNotFoundError: If the main application executable path is not found.
            FileOperationError: If creating directories or writing the service file fails.
            CommandNotFoundError: If `systemctl` is not found for the final daemon-reload.
        """
        self._ensure_linux_for_systemd("create_systemd_service_file")

        if not self.manager_expath or not os.path.isfile(self.manager_expath):
            raise AppFileNotFoundError(
                str(self.manager_expath),
                f"Manager executable for '{self.server_name}' service file",
            )

        # Define the properties for the systemd service unit file.
        description = f"Minecraft Bedrock Server: {self.server_name}"
        working_directory = self.server_dir
        exec_start = f'{self.manager_expath} server start --server "{self.server_name}" --mode direct'
        exec_stop = f'{self.manager_expath} server stop --server "{self.server_name}"'
        exec_start_pre = None  # This field is currently not used.

        self.logger.info(
            f"Creating/updating systemd service file '{self.systemd_service_name_full}' for server '{self.server_name}'."
        )
        try:
            # Delegate the file creation to the generic system utility.
            system_linux_utils.create_systemd_service_file(
                service_name_full=self.systemd_service_name_full,
                description=description,
                working_directory=working_directory,
                exec_start_command=exec_start,
                exec_stop_command=exec_stop,
                exec_start_pre_command=exec_start_pre,
                service_type="simple",
                restart_policy="on-failure",
                restart_sec=10,
                after_targets="network.target",
            )
            self.logger.info(
                f"Systemd service file for '{self.systemd_service_name_full}' created/updated successfully."
            )
        except (
            MissingArgumentError,
            SystemError,
            CommandNotFoundError,
            AppFileNotFoundError,
            FileOperationError,
        ) as e:
            self.logger.error(
                f"Failed to create/update systemd service file for '{self.systemd_service_name_full}': {e}"
            )
            raise

    def enable_systemd_service(self):
        """Enables the systemd user service to start on user login.

        Raises:
            SystemError: If not on Linux or if the `systemctl enable` command fails.
            CommandNotFoundError: If `systemctl` is not found on the system.
        """
        self._ensure_linux_for_systemd("enable_systemd_service")
        self.logger.info(
            f"Enabling systemd service '{self.systemd_service_name_full}'."
        )
        try:
            system_linux_utils.enable_systemd_service(self.systemd_service_name_full)
            self.logger.info(
                f"Systemd service '{self.systemd_service_name_full}' enabled successfully."
            )
        except (SystemError, CommandNotFoundError, MissingArgumentError) as e:
            self.logger.error(
                f"Failed to enable systemd service '{self.systemd_service_name_full}': {e}"
            )
            raise

    def disable_systemd_service(self):
        """Disables the systemd user service from starting on user login.

        Raises:
            SystemError: If not on Linux or if the `systemctl disable` command fails.
            CommandNotFoundError: If `systemctl` is not found on the system.
        """
        self._ensure_linux_for_systemd("disable_systemd_service")
        self.logger.info(
            f"Disabling systemd service '{self.systemd_service_name_full}'."
        )
        try:
            system_linux_utils.disable_systemd_service(self.systemd_service_name_full)
            self.logger.info(
                f"Systemd service '{self.systemd_service_name_full}' disabled successfully."
            )
        except (SystemError, CommandNotFoundError, MissingArgumentError) as e:
            self.logger.error(
                f"Failed to disable systemd service '{self.systemd_service_name_full}': {e}"
            )
            raise

    def remove_systemd_service_file(self) -> bool:
        """Removes the systemd service file for this server if it exists.

        Returns:
            True if the file was removed or did not exist, False otherwise.

        Raises:
            FileOperationError: If removing the file fails.
        """
        self._ensure_linux_for_systemd("remove_systemd_service_file")

        service_file_to_remove = system_linux_utils.get_systemd_user_service_file_path(
            self.systemd_service_name_full
        )

        if os.path.isfile(service_file_to_remove):
            self.logger.info(f"Removing systemd service file: {service_file_to_remove}")
            try:
                os.remove(service_file_to_remove)
                # After removing a file, the systemd daemon should be reloaded.
                systemctl_cmd = shutil.which("systemctl")
                if systemctl_cmd:
                    subprocess.run(
                        [systemctl_cmd, "--user", "daemon-reload"],
                        check=False,
                        capture_output=True,
                    )
                self.logger.info(
                    f"Removed systemd service file for '{self.systemd_service_name_full}' and reloaded daemon."
                )
                return True
            except OSError as e:
                raise FileOperationError(
                    f"Failed to remove systemd service file '{self.systemd_service_name_full}': {e}"
                ) from e
        else:
            self.logger.debug(
                f"Systemd service file for '{self.systemd_service_name_full}' not found. No removal needed."
            )
            return True

    def is_systemd_service_active(self) -> bool:
        """Checks if the systemd user service for this server is currently active.

        Returns:
            True if the service is active, False otherwise or if `systemctl`
            is not found.
        """
        self._ensure_linux_for_systemd("is_systemd_service_active")
        systemctl_cmd = shutil.which("systemctl")
        if not systemctl_cmd:
            return False

        try:
            process = subprocess.run(
                [systemctl_cmd, "--user", "is-active", self.systemd_service_name_full],
                capture_output=True,
                text=True,
                check=False,
            )
            is_active = process.returncode == 0 and process.stdout.strip() == "active"
            self.logger.debug(
                f"Service '{self.systemd_service_name_full}' active status: {process.stdout.strip()} -> {is_active}"
            )
            return is_active
        except Exception as e:
            self.logger.error(
                f"Error checking systemd active status for '{self.systemd_service_name_full}': {e}",
                exc_info=True,
            )
            return False

    def is_systemd_service_enabled(self) -> bool:
        """Checks if the systemd user service for this server is enabled to start on boot.

        Returns:
            True if the service is enabled, False otherwise or if `systemctl`
            is not found.
        """
        self._ensure_linux_for_systemd("is_systemd_service_enabled")
        systemctl_cmd = shutil.which("systemctl")
        if not systemctl_cmd:
            return False

        try:
            process = subprocess.run(
                [systemctl_cmd, "--user", "is-enabled", self.systemd_service_name_full],
                capture_output=True,
                text=True,
                check=False,
            )
            is_enabled = process.returncode == 0 and process.stdout.strip() == "enabled"
            self.logger.debug(
                f"Service '{self.systemd_service_name_full}' enabled status: {process.stdout.strip()} -> {is_enabled}"
            )
            return is_enabled
        except Exception as e:
            self.logger.error(
                f"Error checking systemd enabled status for '{self.systemd_service_name_full}': {e}",
                exc_info=True,
            )
            return False
