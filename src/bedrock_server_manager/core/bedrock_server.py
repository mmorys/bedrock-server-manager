# bedrock_server_manager/core/bedrock_server.py
"""The main BedrockServer class, consolidating all server management functionalities.

This module defines the `BedrockServer` class, which is the central object for
interacting with a single Minecraft Bedrock Server instance. It is constructed
by inheriting from a series of specialized mixin classes, each providing a
distinct set of functionalities (e.g., process management, world management,
backups). This approach keeps the code organized and modular.
"""
import logging
from typing import TYPE_CHECKING, Dict, Any, Optional

if TYPE_CHECKING:
    # This allows for type hinting the Settings class without creating a circular import.
    from bedrock_server_manager.config.settings import Settings

# Import all the mixin classes that will be combined to form the BedrockServer.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.server.installation_mixin import (
    ServerInstallationMixin,
)
from bedrock_server_manager.core.server.state_mixin import ServerStateMixin
from bedrock_server_manager.core.server.process_mixin import ServerProcessMixin
from bedrock_server_manager.core.server.world_mixin import ServerWorldMixin
from bedrock_server_manager.core.server.addon_mixin import ServerAddonMixin
from bedrock_server_manager.core.server.backup_restore_mixin import ServerBackupMixin
from bedrock_server_manager.core.server.systemd_mixin import ServerSystemdMixin
from bedrock_server_manager.core.server.player_mixin import ServerPlayerMixin
from bedrock_server_manager.core.server.config_management_mixin import (
    ServerConfigManagementMixin,
)
from bedrock_server_manager.core.server.install_update_mixin import (
    ServerInstallUpdateMixin,
)
from bedrock_server_manager.error import FileOperationError, ConfigParseError


class BedrockServer(
    # The order of inheritance is important for Method Resolution Order (MRO).
    # More specific mixins should generally come before more general ones.
    # The BaseMixin, which provides the foundational __init__, should be last.
    ServerStateMixin,
    ServerProcessMixin,
    ServerInstallationMixin,
    ServerWorldMixin,
    ServerAddonMixin,
    ServerBackupMixin,
    ServerSystemdMixin,
    ServerPlayerMixin,
    ServerConfigManagementMixin,
    ServerInstallUpdateMixin,
    BedrockServerBaseMixin,
):
    """Represents and manages a single Minecraft Bedrock Server instance.

    This class consolidates functionalities from various mixins to provide a
    comprehensive interface for all server-specific operations. It is the primary
    object used by the API layer to interact with a server.

    An instance of this class is tied to a specific server, identified by its
    unique name.

    Key Attributes (from BedrockServerBaseMixin):
        server_name (str): The unique name of this server instance.
        settings (Settings): The application's global settings object.
        manager_expath (str): Path to the main BSM executable.
        base_dir (str): Base directory where all server installations reside.
        server_dir (str): Full path to this server's installation directory.
        app_config_dir (str): Path to the application's global config directory.
        os_type (str): The current operating system (e.g., "Linux", "Windows").
        logger (logging.Logger): A logger instance for this class.
        bedrock_executable_path (str): Full path to the server's executable.
        server_log_path (str): Full path to the server's main output log file.

    Key Methods (Grouped by Mixin):
        - Installation & Validation: `is_installed()`, `validate_installation()`,
          `set_filesystem_permissions()`, `delete_all_data()`.
        - State Management: `get_status()`, `get_version()`, `set_version()`,
          `get_world_name()`, `get_custom_config_value()`, `set_custom_config_value()`.
        - Process Management: `is_running()`, `get_process_info()`, `start()`,
          `stop()`, `send_command()`.
        - World Management: `export_world_directory_to_mcworld()`,
          `import_active_world_from_mcworld()`, `delete_active_world_directory()`.
        - Addon Management: `process_addon_file()`, `list_world_addons()`,
          `export_addon()`, `remove_addon()`.
        - Backup & Restore: `backup_all_data()`, `restore_all_data_from_latest()`,
          `prune_server_backups()`, `list_backups()`.
        - Systemd Management (Linux-only): `create_systemd_service_file()`,
          `enable_systemd_service()`, `is_systemd_service_active()`.
        - Player Log Scanning: `scan_log_for_players()`.
        - Config File Management: `get_allowlist()`, `add_to_allowlist()`,
          `set_player_permission()`, `get_server_properties()`, `set_server_property()`.
        - Installation & Updates: `is_update_needed()`, `install_or_update()`.
    """

    def __init__(
        self,
        server_name: str,
        settings_instance: Optional["Settings"] = None,
        manager_expath: Optional[str] = None,
    ):
        """Initializes a BedrockServer instance.

        This method calls `super().__init__` which, due to the Method Resolution
        Order (MRO), will correctly call the `__init__` method of every mixin
        in the inheritance chain, starting with `ServerStateMixin` and ending
        with `BedrockServerBaseMixin`.

        Args:
            server_name: The unique name of the server. This will also be used
                as its directory name under the `BASE_DIR`.
            settings_instance: The application's global `Settings` object.
            manager_expath: The full path to the main BSM script/executable. This
                is used, for example, when generating systemd service files
                that need to call back into the BSM application.
        """
        super().__init__(
            server_name=server_name,
            settings_instance=settings_instance,
            manager_expath=manager_expath,
        )
        self.logger.info(
            f"BedrockServer instance '{self.server_name}' fully initialized and ready for operations."
        )

    def __repr__(self) -> str:
        """Provides a developer-friendly string representation of the instance."""
        return (
            f"<BedrockServer(name='{self.server_name}', os='{self.os_type}', "
            f"dir='{self.server_dir}', manager_expath='{self.manager_expath}')>"
        )

    def get_summary_info(self) -> Dict[str, Any]:
        """Returns a dictionary with a comprehensive summary of the server's state.

        This method consolidates information from various other methods into a
        single, convenient dictionary, perfect for API responses or UI displays.
        """
        self.logger.debug(f"Gathering summary info for server '{self.server_name}'.")

        # Safely get process information.
        proc_details = None
        is_server_running = False
        try:
            is_server_running = self.is_running()
            if is_server_running:
                proc_details = self.get_process_info()
        except Exception as e_proc:
            self.logger.warning(
                f"Could not get process status/info for '{self.server_name}': {e_proc}"
            )

        # Safely get world information.
        world_name_val = "N/A"
        has_icon_val = False
        if self.is_installed():
            try:
                world_name_val = self.get_world_name()
                has_icon_val = self.has_world_icon()
            except (FileOperationError, ConfigParseError) as e_world:
                self.logger.warning(
                    f"Error reading world name/icon for '{self.server_name}': {e_world}"
                )
                world_name_val = f"Error ({type(e_world).__name__})"

        # Build the main summary dictionary.
        summary = {
            "name": self.server_name,
            "server_directory": self.server_dir,
            "is_installed": self.is_installed(),
            "status": self.get_status(),
            "is_actually_running_process": is_server_running,
            "process_details": proc_details,
            "version": self.get_version(),
            "world_name": world_name_val,
            "has_world_icon": has_icon_val,
            "os_type": self.os_type,
            "systemd_service_file_exists": None,
            "systemd_service_enabled": None,
            "systemd_service_active": None,
        }

        # Add Linux-specific systemd information if applicable.
        if self.os_type == "Linux":
            try:
                summary["systemd_service_file_exists"] = (
                    self.check_systemd_service_file_exists()
                )
                if summary["systemd_service_file_exists"]:
                    summary["systemd_service_enabled"] = (
                        self.is_systemd_service_enabled()
                    )
                    summary["systemd_service_active"] = self.is_systemd_service_active()
            except (NotImplementedError, Exception) as e_sysd:
                self.logger.warning(
                    f"Error getting systemd info for '{self.server_name}': {e_sysd}"
                )
        return summary
