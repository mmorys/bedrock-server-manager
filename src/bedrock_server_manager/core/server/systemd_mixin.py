# bedrock_server_manager/core/server/systemd_mixin.py
"""
Provides the ServerSystemdMixin class for BedrockServer.

This mixin handles Linux-specific systemd service management for a server instance.
It allows creating, enabling, disabling, removing, and checking the status of
systemd user services that manage the Bedrock server process.
"""
import os
import platform
import shutil
import subprocess
import logging

# Local imports
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
    """
    A mixin for the BedrockServer class that provides methods for managing
    a systemd user service associated with the server instance (Linux-only).
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the ServerSystemdMixin.

        Calls super().__init__ for proper multiple inheritance setup.
        Relies on attributes (like server_name, server_dir, manager_expath,
        logger, os_type) from the base class.
        """
        super().__init__(*args, **kwargs)
        # self.server_name, self.base_dir, self.manager_expath, self.logger, self.os_type are available

    def _ensure_linux_for_systemd(self, operation_name: str) -> None:
        """Helper to check if OS is Linux before proceeding with a systemd operation."""
        if self.os_type != "Linux":
            msg = f"Systemd operation '{operation_name}' is only supported on Linux. Server OS: {self.os_type}"
            self.logger.warning(msg)
            raise SystemError(msg)

    @property
    def systemd_service_name_full(self) -> str:
        """Returns the full systemd service name, e.g., 'bedrock-MyServer.service'."""
        # Ensures .service suffix for clarity when passing to generic functions
        return f"bedrock-{self.server_name}.service"

    def check_systemd_service_file_exists(self) -> bool:
        self._ensure_linux_for_systemd("check_systemd_service_file_exists")
        # Call the generic utility
        return system_linux_utils.check_service_exists(self.systemd_service_name_full)

    def create_systemd_service_file(self) -> None:
        """
        Creates or updates the systemd user service file for this server.

        Raises:
            SystemError: If not on Linux.
            AppFileNotFoundError: If the BSM manager executable path is not found.
            FileOperationError: If creating directories or writing the service file fails.
            CommandNotFoundError: If `systemctl` is not found for daemon-reload.
        """
        self._ensure_linux_for_systemd("create_systemd_service_file")

        if not self.manager_expath or not os.path.isfile(self.manager_expath):
            raise AppFileNotFoundError(
                str(self.manager_expath),
                f"Manager executable for '{self.server_name}' service file",
            )

        description = f"Minecraft Bedrock Server: {self.server_name}"
        working_directory = self.server_dir  # From BaseMixin

        exec_start = f'{self.manager_expath} server start --server "{self.server_name}" --mode direct'
        exec_stop = f'{self.manager_expath} server stop --server "{self.server_name}"'

        exec_start_pre = f'{self.manager_expath} server write-config --server "{self.server_name}" --key start_method --value detached'
        exec_start_pre = None

        self.logger.info(
            f"Creating/updating systemd service file '{self.systemd_service_name_full}' "
            f"for server '{self.server_name}'."
        )
        try:
            system_linux_utils.create_systemd_service_file(
                service_name_full=self.systemd_service_name_full,
                description=description,
                working_directory=working_directory,
                exec_start_command=exec_start,
                exec_stop_command=exec_stop,
                exec_start_pre_command=exec_start_pre,
                service_type="forking",
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

    def enable_systemd_service(self) -> None:
        """
        Enables the systemd user service for this server to start on user login.

        Raises:
            SystemError: If not on Linux or if enabling the service fails.
            CommandNotFoundError: If `systemctl` is not found.
            MissingArgumentError: If the service name is somehow empty.
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
        except (
            SystemError,
            CommandNotFoundError,
            MissingArgumentError,
        ) as e:  # MissingArgumentError if service_name_full is somehow empty
            self.logger.error(
                f"Failed to enable systemd service '{self.systemd_service_name_full}': {e}"
            )
            raise

    def disable_systemd_service(self) -> None:
        """
        Disables the systemd user service for this server from starting on user login.

        Raises:
            SystemError: If not on Linux or if disabling the service fails.
            CommandNotFoundError: If `systemctl` is not found.
            MissingArgumentError: If the service name is somehow empty.
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
        """Removes the systemd service file for this server if it exists."""
        self._ensure_linux_for_systemd("remove_systemd_service_file")

        service_file_to_remove = system_linux_utils.get_systemd_user_service_file_path(
            self.systemd_service_name_full
        )

        if os.path.isfile(service_file_to_remove):
            self.logger.info(f"Removing systemd service file: {service_file_to_remove}")
            try:
                os.remove(service_file_to_remove)
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
                self.logger.error(
                    f"Failed to remove systemd service file '{service_file_to_remove}': {e}"
                )
                raise FileOperationError(
                    f"Failed to remove systemd service file '{self.systemd_service_name_full}': {e}"
                ) from e
        else:
            self.logger.debug(
                f"Systemd service file for '{self.systemd_service_name_full}' not found. No removal needed."
            )
            return True

    def is_systemd_service_active(self) -> bool:
        """Checks if the systemd user service for this server is currently active."""
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
        """Checks if the systemd user service for this server is enabled."""
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
