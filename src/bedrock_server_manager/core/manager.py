# bedrock_server_manager/core/manager.py
"""Provides the BedrockServerManager, the application's central orchestrator.

This module contains the `BedrockServerManager` class, which acts as the main
entry point for application-wide operations that are not specific to a single
server instance. It manages global settings, server discovery, the central
player database, and provides information for managing the web UI process.
"""
import os
import json
import shutil
import glob
import logging
import platform
from typing import Optional, List, Dict, Any, Union, Tuple

# Local application imports.
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.config.const import EXPATH, app_name_title, package_name
from bedrock_server_manager.error import (
    ConfigurationError,
    FileOperationError,
    UserInputError,
    AppFileNotFoundError,
    InvalidServerNameError,
    MissingArgumentError,
)

logger = logging.getLogger(__name__)


class BedrockServerManager:
    """Manages global settings, server discovery, and application-wide data.

    This class provides a high-level interface for accessing configuration and
    performing operations that span multiple server instances or relate to the
    application as a whole, such as managing the global player database or
    listing all available servers.
    """

    def __init__(self, settings_instance: Optional[Settings] = None):
        """Initializes the BedrockServerManager.

        Args:
            settings_instance: An optional, pre-configured `Settings` object.
                If None, a new `Settings` object will be created. This allows
                for dependency injection during testing.

        Raises:
            ConfigurationError: If critical settings like `BASE_DIR` or
                `CONTENT_DIR` are not configured.
        """
        if settings_instance:
            self.settings = settings_instance
        else:
            self.settings = Settings()
        logger.debug(
            f"BedrockServerManager initialized using settings from: {self.settings.config_path}"
        )

        self.capabilities = self._check_system_capabilities()
        self._log_capability_warnings()

        # Initialize core attributes from the settings object.
        try:
            self._config_dir = self.settings.config_dir
            self._app_data_dir = self.settings.app_data_dir
            self._app_name_title = app_name_title
            self._package_name = package_name
            self._expath = EXPATH
        except Exception as e:
            raise ConfigurationError(f"Settings object is misconfigured: {e}") from e

        self._base_dir = self.settings.get("BASE_DIR")
        self._content_dir = self.settings.get("CONTENT_DIR")

        # Constants for managing the web server process.
        self._WEB_SERVER_PID_FILENAME = "web_server.pid"
        self._WEB_SERVER_START_ARG = ["web", "start"]

        try:
            self._app_version = self.settings.version
        except Exception:
            self._app_version = "0.0.0"

        # Validate that essential directory settings are present.
        if not self._base_dir:
            raise ConfigurationError("BASE_DIR not configured in settings.")
        if not self._content_dir:
            raise ConfigurationError("CONTENT_DIR not configured in settings.")

    # --- Settings Related ---
    def get_setting(self, key: str, default=None) -> Any:
        """Retrieves a setting value by key."""
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any):
        """Sets a setting value by key."""
        self.settings.set(key, value)

    # --- Player Database Management ---
    def _get_player_db_path(self) -> str:
        """Returns the absolute path to the central `players.json` file."""
        return os.path.join(self._config_dir, "players.json")

    def parse_player_cli_argument(self, player_string: str) -> List[Dict[str, str]]:
        """Parses a comma-separated string of 'name:xuid' pairs.

        Args:
            player_string: The comma-separated string of player data, e.g.,
                "PlayerOne:123,PlayerTwo:456".

        Returns:
            A list of dictionaries, each with "name" and "xuid" keys.

        Raises:
            UserInputError: If the format of any pair is invalid.
        """
        if not player_string or not isinstance(player_string, str):
            return []
        logger.debug(f"BSM: Parsing player argument string: '{player_string}'")
        player_list: List[Dict[str, str]] = []
        player_pairs = [
            pair.strip() for pair in player_string.split(",") if pair.strip()
        ]
        for pair in player_pairs:
            player_data = pair.split(":", 1)
            if len(player_data) != 2:
                raise UserInputError(
                    f"Invalid player data format: '{pair}'. Expected 'name:xuid'."
                )
            player_name, player_id = player_data[0].strip(), player_data[1].strip()
            if not player_name or not player_id:
                raise UserInputError(f"Name and XUID cannot be empty in '{pair}'.")
            player_list.append({"name": player_name.strip(), "xuid": player_id.strip()})
        return player_list

    def save_player_data(self, players_data: List[Dict[str, str]]) -> int:
        """Saves or updates player data in the central `players.json` file.

        This method merges the provided player data with existing data. It
        updates entries with matching XUIDs and adds new ones.

        Args:
            players_data: A list of player dictionaries, where each dictionary
                must contain 'name' and 'xuid' keys.

        Returns:
            The total number of players that were added or updated.

        Raises:
            UserInputError: If `players_data` has an invalid format.
            FileOperationError: If creating directories or writing the file fails.
        """
        if not isinstance(players_data, list):
            raise UserInputError("players_data must be a list.")
        for p_data in players_data:
            if not (
                isinstance(p_data, dict)
                and "name" in p_data
                and "xuid" in p_data
                and isinstance(p_data["name"], str)
                and p_data["name"]
                and isinstance(p_data["xuid"], str)
                and p_data["xuid"]
            ):
                raise UserInputError(f"Invalid player entry format: {p_data}")

        player_db_path = self._get_player_db_path()
        try:
            os.makedirs(self._config_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Could not create config directory {self._config_dir}: {e}"
            ) from e

        # Load existing player data into a map for efficient lookup.
        existing_players_map: Dict[str, Dict[str, str]] = {}
        if os.path.exists(player_db_path):
            try:
                with open(player_db_path, "r", encoding="utf-8") as f:
                    loaded_json = json.load(f)
                    if (
                        isinstance(loaded_json, dict)
                        and "players" in loaded_json
                        and isinstance(loaded_json["players"], list)
                    ):
                        for p_entry in loaded_json["players"]:
                            if isinstance(p_entry, dict) and "xuid" in p_entry:
                                existing_players_map[p_entry["xuid"]] = p_entry
            except (ValueError, OSError) as e:
                logger.warning(
                    f"BSM: Could not load/parse existing players.json, will overwrite: {e}"
                )

        updated_count = 0
        added_count = 0
        # Merge new data with existing data.
        for player_to_add in players_data:
            xuid = player_to_add["xuid"]
            if xuid in existing_players_map:
                if existing_players_map[xuid] != player_to_add:
                    existing_players_map[xuid] = player_to_add
                    updated_count += 1
            else:
                existing_players_map[xuid] = player_to_add
                added_count += 1

        if updated_count > 0 or added_count > 0:
            # Sort the final list alphabetically by name before saving.
            updated_players_list = sorted(
                list(existing_players_map.values()),
                key=lambda p: p.get("name", "").lower(),
            )
            try:
                with open(player_db_path, "w", encoding="utf-8") as f:
                    json.dump({"players": updated_players_list}, f, indent=4)
                logger.info(
                    f"BSM: Saved/Updated players. Added: {added_count}, Updated: {updated_count}. Total in DB: {len(updated_players_list)}"
                )
                return added_count + updated_count
            except OSError as e:
                raise FileOperationError(f"Failed to write players.json: {e}") from e

        logger.debug("BSM: No new or updated player data to save.")
        return 0

    def get_known_players(self) -> List[Dict[str, str]]:
        """Retrieves all known players from the central `players.json` file.

        Returns:
            A list of player dictionaries, or an empty list if the file
            doesn't exist or is invalid.
        """
        player_db_path = self._get_player_db_path()
        if not os.path.exists(player_db_path):
            return []
        try:
            with open(player_db_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return []
                data = json.loads(content)
                if (
                    isinstance(data, dict)
                    and "players" in data
                    and isinstance(data["players"], list)
                ):
                    return data["players"]
                logger.warning(
                    f"BSM: Player DB {player_db_path} has unexpected format."
                )
        except (ValueError, OSError) as e:
            logger.error(f"BSM: Error reading player DB {player_db_path}: {e}")
        return []

    def discover_and_store_players_from_all_server_logs(self) -> Dict[str, Any]:
        """Scans all server logs for player data and updates the central DB.

        This method iterates through all directories in the `BASE_DIR`, treats
        each as a potential server, validates it, and then uses that server's
        own `scan_log_for_players` method to find player data. All discovered
        data is then saved to the central `players.json`.

        Returns:
            A dictionary summarizing the results, including counts of players
            found, saved, and any errors encountered.

        Raises:
            AppFileNotFoundError: If the main server base directory is invalid.
            FileOperationError: If saving the final data to `players.json` fails.
        """
        if not self._base_dir or not os.path.isdir(self._base_dir):
            raise AppFileNotFoundError(str(self._base_dir), "Server base directory")

        all_discovered_from_logs: List[Dict[str, str]] = []
        scan_errors_details: List[Dict[str, str]] = []

        logger.info(
            f"BSM: Starting discovery of players from all server logs in '{self._base_dir}'."
        )

        for server_name_candidate in os.listdir(self._base_dir):
            potential_server_path = os.path.join(self._base_dir, server_name_candidate)
            if not os.path.isdir(potential_server_path):
                continue

            logger.debug(f"BSM: Processing potential server '{server_name_candidate}'.")
            try:
                # Instantiate a BedrockServer to use its encapsulated logic.
                server_instance = BedrockServer(
                    server_name=server_name_candidate,
                    settings_instance=self.settings,
                    manager_expath=self._expath,
                )

                # Validate it's a real server before trying to scan its logs.
                if not server_instance.is_installed():
                    logger.debug(
                        f"BSM: '{server_name_candidate}' is not a valid Bedrock server installation. Skipping log scan."
                    )
                    continue

                # Use the instance's own method to scan its log file.
                players_in_log = server_instance.scan_log_for_players()
                if players_in_log:
                    all_discovered_from_logs.extend(players_in_log)
                    logger.debug(
                        f"BSM: Found {len(players_in_log)} players in log for server '{server_name_candidate}'."
                    )

            except FileOperationError as e:
                logger.warning(
                    f"BSM: Error scanning log for server '{server_name_candidate}': {e}"
                )
                scan_errors_details.append(
                    {"server": server_name_candidate, "error": str(e)}
                )
            except Exception as e_instantiate:
                logger.error(
                    f"BSM: Error processing server '{server_name_candidate}' for player discovery: {e_instantiate}",
                    exc_info=True,
                )
                scan_errors_details.append(
                    {
                        "server": server_name_candidate,
                        "error": f"Unexpected error: {str(e_instantiate)}",
                    }
                )

        saved_count = 0
        unique_players_to_save_map = {}
        if all_discovered_from_logs:
            # Consolidate all found players into a unique set by XUID.
            unique_players_to_save_map = {
                p["xuid"]: p for p in all_discovered_from_logs
            }
            unique_players_to_save_list = list(unique_players_to_save_map.values())
            try:
                # Save all unique players to the central database.
                saved_count = self.save_player_data(unique_players_to_save_list)
            except (FileOperationError, Exception) as e_save:
                logger.error(
                    f"BSM: Critical error saving player data to global DB: {e_save}",
                    exc_info=True,
                )
                scan_errors_details.append(
                    {
                        "server": "GLOBAL_PLAYER_DB",
                        "error": f"Save failed: {str(e_save)}",
                    }
                )

        return {
            "total_entries_in_logs": len(all_discovered_from_logs),
            "unique_players_submitted_for_saving": len(unique_players_to_save_map),
            "actually_saved_or_updated_in_db": saved_count,
            "scan_errors": scan_errors_details,
        }

    # --- Web UI Process Management ---
    def start_web_ui_direct(
        self, host: Optional[Union[str, List[str]]] = None, debug: bool = False
    ):
        """Starts the web UI in the current process (a blocking call).

        This is used when the web server is started with `--mode direct`.

        Args:
            host: The host address(es) to bind to.
            debug: If True, runs the underlying Flask app in debug mode.

        Raises:
            RuntimeError or ImportError: If the web application cannot be started.
        """
        logger.info("BSM: Starting web application in direct mode (blocking)...")
        try:
            from bedrock_server_manager.web.app import (
                run_web_server as run_bsm_web_application,
            )

            run_bsm_web_application(host, debug)
            logger.info("BSM: Web application (direct mode) shut down.")
        except (RuntimeError, ImportError) as e:
            logger.critical(
                f"BSM: Failed to start web application directly: {e}", exc_info=True
            )
            raise

    def get_web_ui_pid_path(self) -> str:
        """Returns the path to the PID file for the detached web server."""
        return os.path.join(self._config_dir, self._WEB_SERVER_PID_FILENAME)

    def get_web_ui_expected_start_arg(self) -> List[str]:
        """Returns the expected start arguments used to identify the web server process."""
        return self._WEB_SERVER_START_ARG

    def get_web_ui_executable_path(self) -> str:
        """Returns the path to the main application executable.

        Raises:
            ConfigurationError: If the executable path is not configured.
        """
        if not self._expath:
            raise ConfigurationError(
                "Application executable path (_expath) is not configured."
            )
        return self._expath

    # --- Global Content Directory Management ---
    def _list_content_files(self, sub_folder: str, extensions: List[str]) -> List[str]:
        """An internal helper to list files in a content sub-folder.

        Args:
            sub_folder: The sub-folder within the content directory (e.g., "worlds").
            extensions: A list of file extensions to search for (e.g., [".mcworld"]).

        Returns:
            A sorted list of absolute file paths.

        Raises:
            AppFileNotFoundError: If the main content directory is not found.
            FileOperationError: If there's an OS error scanning the directory.
        """
        if not self._content_dir or not os.path.isdir(self._content_dir):
            raise AppFileNotFoundError(str(self._content_dir), "Content directory")

        target_dir = os.path.join(self._content_dir, sub_folder)
        if not os.path.isdir(target_dir):
            logger.debug(
                f"BSM: Content sub-directory '{target_dir}' not found. Returning empty list."
            )
            return []

        found_files: List[str] = []
        for ext in extensions:
            pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
            try:
                for filepath in glob.glob(os.path.join(target_dir, pattern)):
                    if os.path.isfile(filepath):
                        found_files.append(os.path.abspath(filepath))
            except OSError as e:
                raise FileOperationError(
                    f"Error scanning content directory {target_dir}: {e}"
                ) from e
        return sorted(list(set(found_files)))

    def list_available_worlds(self) -> List[str]:
        """Lists `.mcworld` files from the `content/worlds` directory."""
        return self._list_content_files("worlds", [".mcworld"])

    def list_available_addons(self) -> List[str]:
        """Lists `.mcpack` and `.mcaddon` files from the `content/addons` directory."""
        return self._list_content_files("addons", [".mcpack", ".mcaddon"])

    # --- Application / System Information ---
    def get_app_version(self) -> str:
        """Returns the application version string."""
        return self._app_version

    def get_os_type(self) -> str:
        """Returns the current operating system (e.g., "Linux", "Windows")."""
        return platform.system()

    def _check_system_capabilities(self) -> Dict[str, bool]:
        """
        Checks for external OS-level dependencies and returns their status.
        This is for internal use during initialization.
        """
        caps = {
            "scheduler": False,  # For crontab or schtasks
            "service_manager": False,  # For systemctl
        }
        os_name = self.get_os_type()

        if os_name == "Linux":
            if shutil.which("crontab"):
                caps["scheduler"] = True
            if shutil.which("systemctl"):
                caps["service_manager"] = True

        elif os_name == "Windows":
            if shutil.which("schtasks"):
                caps["scheduler"] = True
            # Eventual support for Windows service management
            if shutil.which("sc.exe"):
                caps["service_manager"] = True

        logger.debug(f"System capability check results: {caps}")
        return caps

    def _log_capability_warnings(self):
        """Logs warnings for any missing capabilities."""
        if not self.capabilities["scheduler"]:
            logger.warning(
                "Scheduler command (crontab/schtasks) not found. Scheduling features will be disabled in UIs."
            )

        if self.get_os_type() == "Linux" and not self.capabilities["service_manager"]:
            logger.warning(
                "systemctl command not found. Systemd service features will be disabled in UIs."
            )

    @property
    def can_schedule_tasks(self) -> bool:
        """Returns True if a system scheduler (crontab, schtasks) is available."""
        return self.capabilities["scheduler"]

    @property
    def can_manage_services(self) -> bool:
        """Returns True if a system service manager (systemctl) is available."""
        return self.capabilities["service_manager"]

    # --- Server Discovery ---
    def validate_server(self, server_name: str) -> bool:
        """Validates if a server installation exists and is minimally correct.

        This method works by attempting to instantiate a `BedrockServer` object
        for the given name and then calling its `is_installed()` method.

        Args:
            server_name: The name of the server to validate.

        Returns:
            True if the server is validly installed, False otherwise.

        Raises:
            MissingArgumentError: If `server_name` is empty.
        """
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty for validation.")

        logger.debug(
            f"BSM: Validating server '{server_name}' using BedrockServer class."
        )
        try:
            server_instance = BedrockServer(
                server_name=server_name,
                settings_instance=self.settings,
                manager_expath=self._expath,
            )
            is_valid = server_instance.is_installed()
            if is_valid:
                logger.debug(f"BSM: Server '{server_name}' validation successful.")
            else:
                logger.debug(
                    f"BSM: Server '{server_name}' validation failed (directory or executable missing)."
                )
            return is_valid
        except (
            ValueError,
            MissingArgumentError,
            ConfigurationError,
            InvalidServerNameError,
            Exception,
        ) as e_val:
            # Treat any error during instantiation or validation as a failure.
            logger.warning(
                f"BSM: Validation failed for server '{server_name}' due to an error: {e_val}"
            )
            return False

    def get_servers_data(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Retrieves status and version for all valid server instances.

        This method discovers servers by iterating through directories in `BASE_DIR`,
        instantiating a `BedrockServer` object for each, validating it, and then
        querying its state using its own methods.

        Returns:
            A tuple containing:
            - A list of dictionaries, one for each valid server.
            - A list of error messages for any servers that failed processing.

        Raises:
            AppFileNotFoundError: If the main server base directory is invalid.
        """
        servers_data: List[Dict[str, Any]] = []
        error_messages: List[str] = []

        if not self._base_dir or not os.path.isdir(self._base_dir):
            raise AppFileNotFoundError(str(self._base_dir), "Server base directory")

        for server_name_candidate in os.listdir(self._base_dir):
            potential_server_path = os.path.join(self._base_dir, server_name_candidate)
            if not os.path.isdir(potential_server_path):
                continue

            try:
                # Instantiate a BedrockServer to leverage its encapsulated logic.
                server = BedrockServer(
                    server_name=server_name_candidate,
                    settings_instance=self.settings,
                    manager_expath=self._expath,
                )

                # Use the instance's own method to validate its installation.
                if not server.is_installed():
                    logger.debug(
                        f"Skipping '{server_name_candidate}': Not a valid server installation."
                    )
                    continue

                # Use the instance's methods to get its current state.
                status = server.get_status()
                version = server.get_version()
                servers_data.append(
                    {"name": server.server_name, "status": status, "version": version}
                )

            except (
                FileOperationError,
                ConfigurationError,
                InvalidServerNameError,
            ) as e:
                msg = f"Could not get info for server '{server_name_candidate}': {e}"
                logger.warning(msg)
                error_messages.append(msg)
            except Exception as e:
                msg = f"An unexpected error occurred while processing server '{server_name_candidate}': {e}"
                logger.error(msg, exc_info=True)
                error_messages.append(msg)

        # Sort the final list alphabetically by server name for consistent output.
        servers_data.sort(key=lambda s: s.get("name", "").lower())
        return servers_data, error_messages
