# bedrock-server-manager/src/bedrock_server_manager/core/manager.py
import os
import json
import re
import glob
import logging
import platform
from typing import Optional, List, Dict, Any, Union, Tuple

# Local imports
from bedrock_server_manager.config.settings import Settings, settings as global_settings
from bedrock_server_manager.config.const import EXPATH, app_name_title, package_name
from bedrock_server_manager.core.server import server_utils as core_server_utils
from bedrock_server_manager.error import (
    ConfigError,
    FileOperationError,
    InvalidInputError,
    DirectoryError,
    InvalidServerNameError,
    ConfigurationError,
)

logger = logging.getLogger(__name__)


class BedrockServerManager:
    def __init__(self, settings_instance: Optional[Settings] = None):
        if settings_instance:
            self.settings = settings_instance
        else:
            self.settings = global_settings
        logger.debug(
            f"BedrockServerManager initialized using settings from: {self.settings.config_path}"
        )

        # Resolved paths and values from settings
        try:
            self._config_dir = self.settings.config_dir
            self._app_data_dir = self.settings.app_data_dir
            self._expath = EXPATH
            self._app_name_title = app_name_title
            self._package_name = package_name
        except AttributeError as e:
            # This happens if Settings class is missing the @property getters
            logger.error(
                f"BSM Init Error: Settings object missing expected property. Details: {e}"
            )
            raise ConfigError(f"Settings object misconfiguration: {e}") from e

        self._base_dir = self.settings.get("BASE_DIR")
        self._content_dir = self.settings.get("CONTENT_DIR")

        self._WEB_SERVER_PID_FILENAME = "web_server.pid"
        self._WEB_SERVER_START_ARG = "start-web-server"

        try:
            self._app_version = self.settings.version
        except Exception:
            self._app_version = "0.0.0"

        if not self._base_dir:
            raise ConfigError("BASE_DIR not configured in settings.")
        if not self._content_dir:
            raise ConfigError("CONTENT_DIR not configured in settings.")

    # --- Settings Related ---
    def get_setting(self, key: str, default=None) -> Any:
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        self.settings.set(key, value)

    # --- Player Database Management ---
    def _get_player_db_path(self) -> str:
        return os.path.join(self._config_dir, "players.json")

    def parse_player_cli_argument(self, player_string: str) -> List[Dict[str, str]]:
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
                raise InvalidInputError(
                    f"Invalid player data format: '{pair}'. Expected 'name:xuid'."
                )
            player_name, player_id = player_data[0].strip(), player_data[1].strip()
            if not player_name or not player_id:
                raise InvalidInputError(f"Name and XUID cannot be empty in '{pair}'.")
            player_list.append({"name": player_name.strip(), "xuid": player_id.strip()})
        return player_list

    def scan_single_log_for_players(self, log_file_path: str) -> List[Dict[str, str]]:
        logger.debug(f"BSM: Scanning log file for players: {log_file_path}")
        if not os.path.exists(log_file_path) or not os.path.isfile(log_file_path):
            logger.warning(f"BSM: Log file not found or not a file: {log_file_path}")
            return []

        players_data: List[Dict[str, str]] = []
        unique_xuids = set()
        try:
            with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    match = re.search(
                        r"Player connected:\s*([^,]+),\s*xuid:\s*(\d+)",
                        line,
                        re.IGNORECASE,
                    )
                    if match:
                        player_name, xuid = (
                            match.group(1).strip(),
                            match.group(2).strip(),
                        )
                        if xuid not in unique_xuids:
                            players_data.append({"name": player_name, "xuid": xuid})
                            unique_xuids.add(xuid)
        except OSError as e:
            raise FileOperationError(
                f"Error reading log file '{log_file_path}': {e}"
            ) from e
        logger.debug(
            f"BSM: Found {len(players_data)} unique players in '{log_file_path}'."
        )
        return players_data

    def save_player_data(self, players_data: List[Dict[str, str]]) -> int:
        if not isinstance(players_data, list):
            raise InvalidInputError("players_data must be a list.")
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
                raise InvalidInputError(f"Invalid player entry format: {p_data}")

        player_db_path = self._get_player_db_path()
        try:
            os.makedirs(self._config_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Could not create config directory {self._config_dir}: {e}"
            ) from e

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
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(
                    f"BSM: Could not load/parse existing players.json, will overwrite: {e}"
                )

        updated_count = 0
        added_count = 0
        for player_to_add in players_data:
            xuid = player_to_add["xuid"]
            if xuid in existing_players_map:
                if (
                    existing_players_map[xuid] != player_to_add
                ):  # Check if name or other data changed
                    existing_players_map[xuid] = player_to_add
                    updated_count += 1
            else:
                existing_players_map[xuid] = player_to_add
                added_count += 1

        if updated_count > 0 or added_count > 0:
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
        player_db_path = self._get_player_db_path()
        if not os.path.exists(player_db_path):
            return []
        try:
            with open(player_db_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return []  # Empty file
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
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"BSM: Error reading player DB {player_db_path}: {e}")
        return []

    def discover_and_store_players_from_all_server_logs(self) -> Dict[str, Any]:
        if not self._base_dir or not os.path.isdir(self._base_dir):
            raise DirectoryError(
                f"Invalid or unconfigured server base directory: {self._base_dir}"
            )

        all_discovered_from_logs: List[Dict[str, str]] = []
        scan_errors_details: List[Dict[str, str]] = []

        # Iterate through subdirectories of BASE_DIR
        for server_name in os.listdir(self._base_dir):
            server_path = os.path.join(self._base_dir, server_name)
            if os.path.isdir(server_path):
                log_file = os.path.join(
                    server_path, "server_output.txt"
                )  # Standard log name
                if os.path.isfile(log_file):
                    try:
                        players_in_log = self.scan_single_log_for_players(log_file)
                        if players_in_log:
                            all_discovered_from_logs.extend(players_in_log)
                    except FileOperationError as e:
                        logger.warning(
                            f"BSM: Error scanning log for server '{server_name}': {e}"
                        )
                        scan_errors_details.append(
                            {"server": server_name, "error": str(e)}
                        )
                else:
                    logger.debug(
                        f"BSM: No 'server_output.txt' in '{server_name}'. Skipping."
                    )

        saved_count = 0
        if all_discovered_from_logs:
            # Deduplicate before saving to get a more accurate count of unique players found in logs
            unique_players_to_save_map = {
                p["xuid"]: p for p in all_discovered_from_logs
            }
            unique_players_to_save_list = list(unique_players_to_save_map.values())
            try:
                saved_count = self.save_player_data(unique_players_to_save_list)
            except FileOperationError as e:  # save_player_data could raise this
                raise  # Re-raise critical save failure

        return {
            "total_entries_in_logs": len(all_discovered_from_logs),  # Raw entries found
            "unique_players_submitted_for_saving": (
                len(unique_players_to_save_map) if all_discovered_from_logs else 0
            ),
            "actually_saved_or_updated_in_db": saved_count,
            "scan_errors": scan_errors_details,
        }

    # --- Web UI Process Management (Direct Mode and Info for Detached) ---
    def start_web_ui_direct(
        self, host: Optional[Union[str, List[str]]] = None, debug: bool = False
    ) -> None:
        logger.info("BSM: Starting web application in direct mode (blocking)...")
        try:
            from bedrock_server_manager.web.app import (
                run_web_server as run_bsm_web_application,
            )

            run_bsm_web_application(host, debug)  # This blocks
            logger.info("BSM: Web application (direct mode) shut down.")
        except (RuntimeError, ImportError) as e:
            logger.critical(
                f"BSM: Failed to start web application directly: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"BSM: Unexpected error running web application directly: {e}",
                exc_info=True,
            )
            raise

    def get_web_ui_pid_path(self) -> str:
        return os.path.join(self._config_dir, self._WEB_SERVER_PID_FILENAME)

    def get_web_ui_expected_start_arg(self) -> str:
        return self._WEB_SERVER_START_ARG

    def get_web_ui_executable_path(self) -> str:
        if not self._expath:
            raise ConfigError(
                "Application executable path (_expath) is not configured."
            )
        return self._expath

    # --- Global Content Directory Management ---
    def _list_content_files(self, sub_folder: str, extensions: List[str]) -> List[str]:
        if not self._content_dir or not os.path.isdir(self._content_dir):
            raise DirectoryError(
                f"Invalid or unconfigured content directory: {self._content_dir}"
            )

        target_dir = os.path.join(self._content_dir, sub_folder)
        if not os.path.isdir(target_dir):
            logger.debug(
                f"BSM: Content sub-directory '{target_dir}' not found. Returning empty list."
            )
            return []

        found_files: List[str] = []
        for ext in extensions:
            # Ensure extension includes a dot if glob needs it, or handle it appropriately
            pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
            try:
                for filepath in glob.glob(os.path.join(target_dir, pattern)):
                    if os.path.isfile(
                        filepath
                    ):  # Ensure it's a file, not a dir ending with ext
                        found_files.append(os.path.basename(filepath))
            except OSError as e:
                raise FileOperationError(
                    f"Error scanning content directory {target_dir}: {e}"
                ) from e
        return sorted(list(set(found_files)))  # Sort and unique

    def list_available_worlds(self) -> List[str]:
        """Lists .mcworld files from the content/worlds directory."""
        return self._list_content_files("worlds", [".mcworld"])

    def list_available_addons(self) -> List[str]:
        """Lists .mcpack and .mcaddon files from the content/addons directory."""
        return self._list_content_files("addons", [".mcpack", ".mcaddon"])

    # --- Application / System Information ---
    def get_app_version(self) -> str:
        return self._app_version

    def get_os_type(self) -> str:
        return platform.system()

    # --- Server Discovery (Passive - just lists directories) ---
    def get_servers_data(self) -> Tuple[List[Dict[str, str]], List[str]]:
        """
        Logic to retrieve status and version for all servers.
        Collects data for successfully processed servers and error messages for failures.
        Raises DirectoryError if self._base_dir is invalid.
        """
        servers_data: List[Dict[str, str]] = []
        error_messages: List[str] = []

        if not os.path.isdir(self._base_dir):
            # This is a fundamental setup error for the core operation
            raise DirectoryError(
                f"Server base directory does not exist or is not a directory: {self._base_dir}"
            )

        for item_name in os.listdir(self._base_dir):
            item_path = os.path.join(self._base_dir, item_name)
            if os.path.isdir(item_path):
                server_name = item_name
                try:
                    # These utils functions are expected to raise their specific exceptions
                    # (FileOperationError, InvalidServerNameError, ConfigurationError etc.) on failure.
                    status = core_server_utils.get_server_status_from_config(
                        server_name, self._config_dir
                    )
                    version = core_server_utils.get_installed_version(
                        server_name, self._config_dir
                    )
                    servers_data.append(
                        {"name": server_name, "status": status, "version": version}
                    )
                except (
                    FileOperationError,
                    InvalidServerNameError,
                    ConfigurationError,  # Catching a broader range of core-level issues
                ) as e:
                    # Collect error message for this specific server
                    msg = f"Could not get info for server '{server_name}': {e}"
                    # Core layer might have its own, more detailed/debug logging if needed
                    # logger.debug(f"Core._core_get_all_servers_data: {msg}", exc_info=True)
                    error_messages.append(msg)
                # Any other unexpected exceptions within the loop for a specific server would propagate
                # and be caught by the API layer's generic Exception handler.

        return servers_data, error_messages
