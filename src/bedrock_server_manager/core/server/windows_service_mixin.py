# bedrock_server_manager/core/server/windows_service_mixin.py
"""Provides the ServerWindowsServiceMixin for the BedrockServer class.

This mixin encapsulates all Windows-specific Service management for a
server instance. It allows for the creation, enabling, disabling, removal, and
status checking of Windows Services that manage the Bedrock server process,
facilitating background operation and autostart capabilities.

NOTE: All operations in this mixin require the application to be run with
Administrator privileges.
"""
import os
import subprocess

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.system import windows as system_windows_utils
from bedrock_server_manager.error import (
    SystemError,
    PermissionsError,
    MissingArgumentError,
    AppFileNotFoundError,
)


class ServerWindowsServiceMixin(BedrockServerBaseMixin):
    """A mixin for BedrockServer to manage a Windows Service (Windows-only).

    This class provides methods to create, enable, disable, remove, and check
    the status of a Windows Service associated with the server instance.

    All methods require Administrator privileges.
    """

    def __init__(self, *args, **kwargs):
        """Initializes the ServerWindowsServiceMixin.

        This constructor calls `super().__init__` to ensure proper method
        resolution order in the context of multiple inheritance. It relies on
        attributes (like `server_name`, `server_dir`, `manager_expath`, `os_type`)
        from the base class.
        """
        super().__init__(*args, **kwargs)
        # self.server_name, self.base_dir, self.manager_expath, self.logger, and self.os_type are available from BaseMixin.

    def _ensure_windows_for_service(self, operation_name: str):
        """A helper to verify the OS is Windows before a service operation.

        Args:
            operation_name: The name of the operation being attempted, for logging.

        Raises:
            SystemError: If the operating system is not Windows.
        """
        if self.os_type != "Windows":
            msg = f"Windows Service operation '{operation_name}' is only supported on Windows. Server OS: {self.os_type}"
            self.logger.warning(msg)
            raise SystemError(msg)

    @property
    def windows_service_name(self) -> str:
        """Returns the internal service name (e.g., 'bedrock-MyServer')."""
        return f"bedrock-{self.server_name}"

    @property
    def windows_service_display_name(self) -> str:
        """Returns the user-friendly display name for the service."""
        return f"Bedrock Server ({self.server_name})"

    def check_windows_service_exists(self) -> bool:
        """Checks if the Windows Service for this server exists.

        Returns:
            True if the service exists, False otherwise.
        """
        self._ensure_windows_for_service("check_windows_service_exists")
        # Delegate the check to the generic system utility.
        return system_windows_utils.check_service_exists(self.windows_service_name)

    def create_windows_service(self):
        """Creates or updates the Windows Service for this server.

        Requires Administrator privileges.

        Raises:
            SystemError: If the OS is not Windows.
            AppFileNotFoundError: If the main application executable path is not found.
            PermissionsError: If not run with Administrator privileges.
        """
        self._ensure_windows_for_service("create_windows_service")

        if not self.manager_expath or not os.path.isfile(self.manager_expath):
            raise AppFileNotFoundError(
                str(self.manager_expath),
                f"Manager executable for '{self.server_name}' service",
            )

        # Define the properties for the Windows Service.
        # The command must have quoted paths to handle spaces.
        description = (
            f"Manages the Minecraft Bedrock Server instance named '{self.server_name}'."
        )
        quoted_expath = f"{self.manager_expath}"

        # 2. Quote the server name.
        quoted_server_name = f'"{self.server_name}"'

        # 3. Build the full command by joining the parts.
        command_parts = [
            quoted_expath,
            "service",
            "_run-bedrock",
            "--server",
            quoted_server_name,
        ]
        command = " ".join(command_parts)
        self.logger.info(
            f"Creating/updating Windows service '{self.windows_service_name}' for server '{self.server_name}'."
        )
        try:
            # Delegate the service creation to the generic system utility.
            system_windows_utils.create_windows_service(
                service_name=self.windows_service_name,
                display_name=self.windows_service_display_name,
                description=description,
                command=command,
            )
            self.logger.info(
                f"Windows service '{self.windows_service_name}' created/updated successfully."
            )
        except (MissingArgumentError, SystemError, PermissionsError) as e:
            self.logger.error(
                f"Failed to create/update Windows service '{self.windows_service_name}': {e}"
            )
            raise

    def enable_windows_service(self):
        """Enables the Windows Service (sets start type to Automatic).

        Requires Administrator privileges.

        Raises:
            SystemError: If not on Windows or if the operation fails.
            PermissionsError: If not run with Administrator privileges.
        """
        self._ensure_windows_for_service("enable_windows_service")
        self.logger.info(f"Enabling Windows service '{self.windows_service_name}'.")
        try:
            system_windows_utils.enable_windows_service(self.windows_service_name)
            self.logger.info(
                f"Windows service '{self.windows_service_name}' enabled successfully."
            )
        except (SystemError, PermissionsError, MissingArgumentError) as e:
            self.logger.error(
                f"Failed to enable Windows service '{self.windows_service_name}': {e}"
            )
            raise

    def disable_windows_service(self):
        """Disables the Windows Service (sets start type to Disabled).

        Requires Administrator privileges.

        Raises:
            SystemError: If not on Windows or if the operation fails.
            PermissionsError: If not run with Administrator privileges.
        """
        self._ensure_windows_for_service("disable_windows_service")
        self.logger.info(f"Disabling Windows service '{self.windows_service_name}'.")
        try:
            system_windows_utils.disable_windows_service(self.windows_service_name)
            self.logger.info(
                f"Windows service '{self.windows_service_name}' disabled successfully."
            )
        except (SystemError, PermissionsError, MissingArgumentError) as e:
            self.logger.error(
                f"Failed to disable Windows service '{self.windows_service_name}': {e}"
            )
            raise

    def remove_windows_service(self):
        """Removes (deletes) the Windows Service for this server.

        Requires Administrator privileges. The service should be stopped first.

        Raises:
            SystemError: If not on Windows or if the operation fails.
            PermissionsError: If not run with Administrator privileges.
        """
        self._ensure_windows_for_service("remove_windows_service")
        self.logger.info(f"Removing Windows service '{self.windows_service_name}'.")
        try:
            system_windows_utils.delete_windows_service(self.windows_service_name)
            self.logger.info(
                f"Windows service '{self.windows_service_name}' removed successfully."
            )
        except (SystemError, PermissionsError, MissingArgumentError) as e:
            self.logger.error(
                f"Failed to remove Windows service '{self.windows_service_name}': {e}"
            )
            raise

    def is_windows_service_active(self) -> bool:
        """Checks if the Windows Service for this server is currently running.

        Uses the built-in `sc.exe` command-line tool.

        Returns:
            True if the service is in the 'RUNNING' state, False otherwise.
        """
        self._ensure_windows_for_service("is_windows_service_active")
        try:
            # Use 'sc query' to check the state of the service.
            result = subprocess.check_output(
                ["sc", "query", self.windows_service_name],
                text=True,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            # A running service will have a line like "        STATE              : 4  RUNNING"
            return "STATE" in result and "RUNNING" in result
        except subprocess.CalledProcessError:
            # This error occurs if the service does not exist.
            return False
        except FileNotFoundError:
            # sc.exe not found, which is highly unlikely on Windows.
            self.logger.warning("`sc.exe` command not found.")
            return False

    def is_windows_service_enabled(self) -> bool:
        """Checks if the Windows Service is enabled (set to start automatically).

        Uses the built-in `sc.exe` command-line tool.

        Returns:
            True if the service start type is 'AUTO_START', False otherwise.
        """
        self._ensure_windows_for_service("is_windows_service_enabled")
        try:
            # Use 'sc qc' (query config) to check the start type.
            result = subprocess.check_output(
                ["sc", "qc", self.windows_service_name],
                text=True,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            # An enabled service will have a line like "        START_TYPE         : 2   AUTO_START"
            return "START_TYPE" in result and "AUTO_START" in result
        except subprocess.CalledProcessError:
            # This error occurs if the service does not exist.
            return False
        except FileNotFoundError:
            self.logger.warning("`sc.exe` command not found.")
            return False
