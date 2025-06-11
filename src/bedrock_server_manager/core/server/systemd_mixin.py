# bedrock_server_manager/core/server/systemd_mixin.py
import os
import platform
import shutil
import subprocess
import logging

# Local imports
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.system import linux as system_linux_utils
from bedrock_server_manager.error import (
    ServiceError,
    CommandNotFoundError,
    SystemdReloadError,
    FileOperationError,
    InvalidServerNameError,
    MissingArgumentError,
)


class ServerSystemdMixin(BedrockServerBaseMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.server_name, self.base_dir, self.manager_expath, self.logger, self.os_type are available

    def _ensure_linux_for_systemd(self, operation_name: str) -> None:
        """Helper to check if OS is Linux before proceeding with a systemd operation."""
        if self.os_type != "Linux":
            msg = f"Systemd operation '{operation_name}' is only supported on Linux. Server OS: {self.os_type}"
            self.logger.warning(msg)
            raise NotImplementedError(msg)

    @property
    def systemd_service_name_full(self) -> str:
        """Returns the full systemd service name, e.g., 'bedrock-MyServer.service'."""
        # Ensures .service suffix for clarity when passing to generic functions
        return f"bedrock-{self.server_name}.service"

    def check_systemd_service_file_exists(self) -> bool:
        self._ensure_linux_for_systemd("check_systemd_service_file_exists")
        # Call the generic utility
        return system_linux_utils.check_generic_service_file_exists(
            self.systemd_service_name_full
        )

    def create_systemd_service_file(self, autoupdate_on_start: bool = False) -> None:
        self._ensure_linux_for_systemd("create_systemd_service_file")

        if not self.manager_expath or not os.path.isfile(self.manager_expath):
            raise FileOperationError(
                f"Manager executable path (self.manager_expath) is invalid or not set: {self.manager_expath}"
                f" Cannot create systemd service file for '{self.server_name}'."
            )

        description = f"Minecraft Bedrock Server: {self.server_name}"
        working_directory = self.server_dir  # From BaseMixin

        exec_start = f'{self.manager_expath} start-server --server "{self.server_name}" --mode direct'
        exec_stop = f'{self.manager_expath} stop-server --server "{self.server_name}"'

        exec_start_pre = None
        if autoupdate_on_start:
            exec_start_pre = (
                f'{self.manager_expath} update-server --server "{self.server_name}"'
            )
            self.logger.debug(
                f"Autoupdate enabled for service '{self.systemd_service_name_full}'."
            )

        self.logger.info(
            f"Creating/updating systemd service file '{self.systemd_service_name_full}' "
            f"for server '{self.server_name}' with autoupdate: {autoupdate_on_start}."
        )
        try:
            system_linux_utils.create_generic_systemd_service_file(
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
            ServiceError,
            CommandNotFoundError,
            SystemdReloadError,
            FileOperationError,
        ) as e:
            self.logger.error(
                f"Failed to create/update systemd service file for '{self.systemd_service_name_full}': {e}"
            )
            raise

    def enable_systemd_service(self) -> None:
        self._ensure_linux_for_systemd("enable_systemd_service")
        self.logger.info(
            f"Enabling systemd service '{self.systemd_service_name_full}'."
        )
        try:
            system_linux_utils.enable_generic_systemd_service(
                self.systemd_service_name_full
            )
            self.logger.info(
                f"Systemd service '{self.systemd_service_name_full}' enabled successfully."
            )
        except (
            ServiceError,
            CommandNotFoundError,
            MissingArgumentError,
        ) as e:  # MissingArgumentError if service_name_full is somehow empty
            self.logger.error(
                f"Failed to enable systemd service '{self.systemd_service_name_full}': {e}"
            )
            raise

    def disable_systemd_service(self) -> None:
        self._ensure_linux_for_systemd("disable_systemd_service")
        self.logger.info(
            f"Disabling systemd service '{self.systemd_service_name_full}'."
        )
        try:
            system_linux_utils.disable_generic_systemd_service(
                self.systemd_service_name_full
            )
            self.logger.info(
                f"Systemd service '{self.systemd_service_name_full}' disabled successfully."
            )
        except (ServiceError, CommandNotFoundError, MissingArgumentError) as e:
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
