# bedrock_server_manager/core/bedrock_server.py
import logging
from typing import TYPE_CHECKING, Dict, Any, Optional

if TYPE_CHECKING:
    from bedrock_server_manager.config.settings import Settings

# Import Mixins
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
    """
    Represents and manages a single Minecraft Bedrock Server instance.

    This class consolidates functionalities from various mixins to provide a comprehensive
    interface for server-specific operations. It is initialized with the server's name,
    a global settings instance, and the path to the Bedrock Server Manager executable.

    Key Attributes (from BedrockServerBaseMixin):
        - server_name (str): The unique name of this server instance.
        - settings (Settings): The application's global settings object.
        - manager_expath (str): Path to the BSM executable.
        - base_dir (str): Base directory where all server installations reside.
        - server_dir (str): Full path to this server's installation directory.
        - app_config_dir (str): Path to the application's global configuration directory.
        - _server_specific_config_dir (str): Path to this server's specific JSON config directory.
        - os_type (str): The current operating system type (e.g., "Linux", "Windows").
        - logger (logging.Logger): An instance-specific logger.
        - bedrock_executable_path (str): Full path to the server's bedrock_server executable.
        - server_log_path (str): Full path to the server's main output log file.

    Provided Functionalities (Grouped by Mixin Concept):

    Core & Base (via BedrockServerBaseMixin):
        - Initialization of core paths and attributes.
        - Access to common properties like executable paths and log paths.
        - PID file path generation.

    Installation & Validation (via ServerInstallationMixin):
        - `is_installed() -> bool`: Checks if the server is correctly installed.
        - `validate_installation() -> bool`: Validates installation, raising errors on failure.
        - `set_filesystem_permissions() -> None`: Sets appropriate permissions on server files.
        - `delete_all_data() -> None`: Deletes all server data (install, config, backups, systemd).
                                       (Uses `delete_server_files` internally for directory removal).

    State Management (via ServerStateMixin):
        - `get_status() -> str`: Determines the current operational status (e.g., RUNNING, STOPPED).
        - `get_version() -> str`: Gets the installed game version from server's JSON config.
        - `set_version(version_string: str) -> None`: Sets the game version in JSON config.
        - `get_status_from_config() -> str`: Reads stored status from JSON config.
        - `set_status_in_config(status_string: str) -> None`: Writes status to JSON config.
        - `get_world_name() -> str`: Reads 'level-name' from server.properties.
        - 'get_custom_config_value(key: str) -> None`: Gets a custom value from the server's JSON config.
        - `set_custom_config_value(key: str, value: str) -> None`: Sets a custom value in the server's JSON config.
        - `_manage_json_config(key, operation, value)`: (Internal helper for server JSON config).

    Process Management (via ServerProcessMixin):
        - `is_running() -> bool`: Checks if the server process is currently active.
        - `get_process_info() -> Optional[Dict[str, Any]]`: Gets PID, CPU, Memory, Uptime.
        - `start() -> None`: Starts the server (direct mode: blocking on Win, screen on Lin).
        - `stop() -> None`: Stops the server gracefully, with forceful termination if needed.
        - `send_command(command: str) -> None`: Sends a command to the server console.

    World Management (via ServerWorldMixin):
        - `extract_mcworld_to_directory(mcworld_file_path: str, target_world_dir_name: str) -> str`: Extracts .mcworld.
        - `export_world_directory_to_mcworld(world_dir_name: str, target_mcworld_file_path: str) -> None`: Creates .mcworld.
        - `import_active_world_from_mcworld(mcworld_backup_file_path: str) -> str`: Imports .mcworld to active world.
        - `world_icon_filesystem_path -> Optional[str]`: Property for the world icon's disk path.
        - `has_world_icon() -> bool`: Checks if the world icon file exists.
        - 'delete_active_world_directory() -> bool`: Deletes the active world directory.

    Addon Management (via ServerAddonMixin):
        - `process_addon_file(addon_file_path: str) -> None`: Processes .mcaddon or .mcpack files.
          (Internally handles extraction, manifest parsing, and installation to active world).

    Backup & Restore (via ServerBackupMixin):
        - `backup_all_data() -> Dict[str, Optional[str]]`: Backs up world and config files.
        - `restore_all_data_from_latest() -> Dict[str, Optional[str]]`: Restores from latest backups.
        - `prune_server_backups(component_prefix: str, file_extension: str) -> None`: Prunes old backups for this server.
        - `server_backup_directory -> Optional[str]`: Property for this server's backup path.
        - 'list_backups(backup_type: str) -> Union[List[str], Dict[str, List[str]]]`: Lists backups for this server.

    Systemd Service Management (Linux-only, via ServerSystemdMixin):
        - `check_systemd_service_file_exists() -> bool`: Checks for the .service file.
        - `create_systemd_service_file(autoupdate_on_start: bool = False) -> None`: Creates/updates .service file.
        - `enable_systemd_service() -> None`: Enables the service for autostart.
        - `disable_systemd_service() -> None`: Disables service autostart.
        - `remove_systemd_service_file() -> bool`: Removes the .service file.
        - `is_systemd_service_active() -> bool`: Checks if systemd reports the service as active.
        - `is_systemd_service_enabled() -> bool`: Checks if systemd reports the service as enabled.

    Player Log Scanning (via ServerPlayerMixin):
        - `scan_log_for_players() -> List[Dict[str, str]]`: Scans this server's log for player connections.

    Configuration File Management (via ServerConfigManagementMixin):
        - `get_allowlist() -> List[Dict[str, Any]]`: Reads allowlist.json.
        - `add_to_allowlist(players_to_add: List[Dict[str, Any]]) -> int`: Adds players to allowlist.
        - `remove_from_allowlist(player_name_to_remove: str) -> bool`: Removes player from allowlist.
        - `set_player_permission(xuid: str, permission_level: str, player_name: Optional[str] = None) -> None`: Sets permissions.json entry.
        - `get_formatted_permissions(player_xuid_to_name_map: Dict[str, str]) -> List[Dict[str, Any]]`: Reads and formats permissions.json.
        - `set_server_property(property_key: str, property_value: Any) -> None`: Modifies server.properties.
        - `get_server_properties() -> Dict[str, str]`: Parses server.properties into a dict.
        - `get_server_property(property_key: str, default: Optional[Any] = None) -> Optional[Any]`: Gets a single property value.

    Installation & Updates (via ServerInstallUpdateMixin):
        - `is_update_needed(target_version_specification: str) -> bool`: Checks if an update is required.
        - `install_or_update(target_version_specification: str, force_reinstall: bool = False) -> None`:
          Performs server installation or update using BedrockDownloader.
          (Internally uses `_perform_server_files_setup`).

    Convenience Methods:
        - `get_summary_info() -> Dict[str, Any]`: Returns a comprehensive dictionary of server status and details.
    """

    def __init__(
        self,
        server_name: str,
        settings_instance: Optional["Settings"] = None,
        manager_expath: Optional[str] = None,
    ):
        """
        Initializes a BedrockServer instance.

        Args:
            server_name (str): The unique name of the server. This will also be used
                               as its directory name under the BASE_DIR.
            settings_instance (Settings): The application's global Settings object.
            manager_expath (str): The full path to the main BSM script/executable. This is
                                  used, for example, when generating systemd service files
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
        """
        Provides a developer-friendly string representation of the BedrockServer instance.
        """
        return (
            f"<BedrockServer(name='{self.server_name}', os='{self.os_type}', "
            f"dir='{self.server_dir}', manager_expath='{self.manager_expath}')>"
        )

    def get_summary_info(self) -> Dict[str, Any]:
        """
        Returns a dictionary with common summary information about the server.
        """
        self.logger.debug(f"Gathering summary info for server '{self.server_name}'.")

        proc_details = None
        is_server_running = False
        try:  # Guard is_running and get_process_info calls
            is_server_running = self.is_running()
            if is_server_running:
                proc_details = self.get_process_info()
        except Exception as e_proc:
            self.logger.warning(
                f"Could not get process status/info for '{self.server_name}': {e_proc}"
            )

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
            except NotImplementedError:
                pass
            except Exception as e_sysd:
                self.logger.warning(
                    f"Error getting systemd info for '{self.server_name}': {e_sysd}"
                )
        return summary
