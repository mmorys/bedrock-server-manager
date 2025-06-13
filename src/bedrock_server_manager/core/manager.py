# bedrock_server_manager/core/manager.py
"""
Provides the BedrockServerManager class, the central orchestrator for application-wide
operations, settings management, and server discovery.
"""
import os
import json
import re
import glob
import logging
import platform
from typing import Optional, List, Dict, Any, Union, Tuple

# Local imports
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
    """
    Manages application settings, server discovery, global player data,
    and web UI process information.

    This class acts as a central point for accessing configuration and performing
    operations that span across multiple server instances or relate to the
    application as a whole.
    """

    def __init__(self, settings_instance: Optional[Settings] = None):
        """
        Initializes the BedrockServerManager.

        Args:
            settings_instance: An optional pre-configured Settings object.
                               If None, a new Settings object will be created.
        """
        if settings_instance:
            self.settings = settings_instance
        else:
            self.settings = Settings()
        logger.debug(
            f"BedrockServerManager initialized using settings from: {self.settings.config_path}"
        )

        # Resolved paths and values from settings
        try:
            self._config_dir = self.settings.config_dir
            self._app_data_dir = self.settings.app_data_dir
            self._app_name_title = app_name_title
            self._package_name = package_name
            self._expath = EXPATH
        except Exception as e:
            logger.error(
                f"BSM Init Error: Settings object missing expected property. Details: {e}"
            )
            raise ConfigurationError(f"Settings object misconfiguration: {e}") from e

        self._base_dir = self.settings.get("BASE_DIR")
        self._content_dir = self.settings.get("CONTENT_DIR")

        self._WEB_SERVER_PID_FILENAME = "web_server.pid"
        self._WEB_SERVER_START_ARG = ["web", "start"]

        try:
            self._app_version = self.settings.version
        except Exception:
            self._app_version = "0.0.0"

        if not self._base_dir:
            raise ConfigurationError("BASE_DIR not configured in settings.")
        if not self._content_dir:
            raise ConfigurationError("CONTENT_DIR not configured in settings.")

    # --- Settings Related ---
    def get_setting(self, key: str, default=None) -> Any:
        """Retrieves a setting value by key."""
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Sets a setting value by key."""
        self.settings.set(key, value)

    # --- Player Database Management ---
    def _get_player_db_path(self) -> str:
        """Returns the absolute path to the players.json database file."""
        return os.path.join(self._config_dir, "players.json")

    def parse_player_cli_argument(self, player_string: str) -> List[Dict[str, str]]:
        """
        Parses a comma-separated string of 'name:xuid' pairs into a list of dicts.

        Args:
            player_string: The comma-separated string of player data.

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
        """
        Saves or updates player data in the players.json file.

        Merges the provided player data with existing data, updating entries
        with matching XUIDs and adding new ones.

        Args:
            players_data: A list of player dictionaries ({"name": str, "xuid": str}).

        Returns:
            The total number of players added or updated.

        Raises:
            UserInputError: If `players_data` format is invalid.
            FileOperationError: If there's an issue creating directories or writing the file.
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
        """
        Retrieves all known players from the players.json file.

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
        except (ValueError, OSError) as e:
            logger.error(f"BSM: Error reading player DB {player_db_path}: {e}")
        return []

    def discover_and_store_players_from_all_server_logs(self) -> Dict[str, Any]:
        """
        Scans all valid server logs within the base directory for player connection
        information (name, XUID) and updates the central players.json database.

        Returns:
            A dictionary summarizing the results, including counts of entries found,
            unique players submitted for saving, players actually saved/updated,
            and a list of any errors encountered during the scan of individual servers.
            Example: `{"total_entries_in_logs": N, "unique_players_submitted_for_saving": M, ...}`

        Raises:
            AppFileNotFoundError: If the main server base directory is invalid.
            FileOperationError: If there's a critical error saving data to players.json.
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

            # Check if it's a directory first
            if not os.path.isdir(potential_server_path):
                logger.debug(
                    f"BSM: Skipping '{server_name_candidate}', not a directory."
                )
                continue

            logger.debug(f"BSM: Processing potential server '{server_name_candidate}'.")
            try:
                # Instantiate BedrockServer.
                server_instance = BedrockServer(
                    server_name=server_name_candidate,
                    settings_instance=self.settings,
                    manager_expath=self._expath,
                )

                # Validate if it's a proper server installation before trying to scan logs
                if not server_instance.is_installed():
                    logger.debug(
                        f"BSM: '{server_name_candidate}' is not a valid Bedrock server installation. Skipping log scan."
                    )
                    continue

                # Now use BedrockServer to scan its own log
                players_in_log = server_instance.scan_log_for_players()

                if players_in_log:
                    all_discovered_from_logs.extend(players_in_log)
                    logger.debug(
                        f"BSM: Found {len(players_in_log)} players in log for server '{server_name_candidate}'."
                    )

            except (
                FileOperationError
            ) as e:  # Raised by scan_log_for_players if log reading fails
                logger.warning(
                    f"BSM: Error scanning log for server '{server_name_candidate}': {e}"
                )
                scan_errors_details.append(
                    {"server": server_name_candidate, "error": str(e)}
                )
            except (
                Exception
            ) as e_instantiate:  # Catch errors during BedrockServer instantiation or other unexpected issues
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
            unique_players_to_save_map = {
                p["xuid"]: p for p in all_discovered_from_logs
            }
            unique_players_to_save_list = list(unique_players_to_save_map.values())
            try:
                saved_count = self.save_player_data(unique_players_to_save_list)
            except FileOperationError as e:
                logger.error(
                    f"BSM: Critical error saving player data to global DB: {e}",
                    exc_info=True,
                )
                raise  # Re-raise critical save failure
            except Exception as e_save:  # Catch other errors from save_player_data
                logger.error(
                    f"BSM: Unexpected error saving player data to global DB: {e_save}",
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

    # --- Web UI Process Management (Direct Mode and Info for Detached) ---
    def start_web_ui_direct(
        self, host: Optional[Union[str, List[str]]] = None, debug: bool = False
    ) -> None:
        """
        Starts the web UI in the current process (blocking).

        This is typically called when the `--mode direct` is used for starting the web server.

        Args:
            host: Optional host address(es) to bind to.
            debug: If True, run Flask in debug mode.

        Raises:
            RuntimeError/ImportError: If the web application cannot be imported or started.
        """
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
        """Returns the path to the PID file for the detached web server."""
        return os.path.join(self._config_dir, self._WEB_SERVER_PID_FILENAME)

    def get_web_ui_expected_start_arg(self) -> str:
        """Returns the expected start argument used to identify the web server process."""
        return self._WEB_SERVER_START_ARG

    def get_web_ui_executable_path(self) -> str:
        """
        Returns the path to the BSM executable, used for launching/identifying the web server.

        Raises:
            ConfigurationError: If the executable path is not set.
        """
        if not self._expath:
            raise ConfigurationError(
                "Application executable path (_expath) is not configured."
            )
        return self._expath

    # --- Global Content Directory Management ---
    def _list_content_files(self, sub_folder: str, extensions: List[str]) -> List[str]:
        """
        Internal helper to list files with given extensions in a content sub-folder.

        Args:
            sub_folder: The sub-folder within the main content directory (e.g., "worlds").
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
                    if os.path.isfile(
                        filepath
                    ):  # Ensure it's a file, not a dir ending with ext
                        found_files.append(os.path.abspath(filepath))

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
        """Returns the application version string."""
        return self._app_version

    def get_os_type(self) -> str:
        """Returns the current operating system type (e.g., "Linux", "Windows")."""
        return platform.system()

    # --- Server Discovery ---

    def validate_server(self, server_name: str) -> bool:
        """
        Validates if a server installation exists and seems minimally correct
        by attempting to instantiate a BedrockServer object and checking its installed status.

        Args:
            server_name: The name of the server.

        Returns:
            True if the server appears validly installed, False otherwise.

        Raises:
            MissingArgumentError: If `server_name` is empty.
            # Other errors like ConfigurationError could be raised during BedrockServer instantiation
            # if critical settings (like BASE_DIR) are missing from self.settings.
        """
        if not server_name:
            # Raise MissingArgumentError
            raise MissingArgumentError("Server name cannot be empty for validation.")

        logger.debug(
            f"BSM: Validating server '{server_name}' using BedrockServer class."
        )

        try:
            # Instantiate BedrockServer.
            server_instance = BedrockServer(
                server_name=server_name,
                settings_instance=self.settings,
                manager_expath=self._expath,
            )

            # BedrockServer.is_installed() performs the checks for directory and executable
            # and returns True or False
            is_valid = server_instance.is_installed()

            if is_valid:
                logger.debug(
                    f"BSM: Server '{server_name}' validation successful (via BedrockServer.is_installed)."
                )
            else:
                logger.debug(
                    f"BSM: Server '{server_name}' validation failed (via BedrockServer.is_installed). "
                    f"Directory: '{server_instance.server_dir}', Executable: '{server_instance.bedrock_executable_path}'."
                )
            return is_valid

        except (
            ValueError,
            MissingArgumentError,
            ConfigurationError,
        ) as e_val:  # e.g., from BedrockServerBaseMixin if BASE_DIR missing in settings
            logger.warning(
                f"BSM: Validation failed for server '{server_name}' due to configuration issue during BedrockServer instantiation: {e_val}"
            )
            return False  # Treat as not valid if we can't even instantiate properly
        except (
            InvalidServerNameError
        ) as e_name:  # If BedrockServer init were to raise this for bad names
            logger.warning(
                f"BSM: Server name '{server_name}' considered invalid: {e_name}"
            )
            return False
        except (
            Exception
        ) as e_unexp:  # Catch any other unexpected errors during instantiation or is_installed call
            logger.error(
                f"BSM: Unexpected error validating server '{server_name}': {e_unexp}",
                exc_info=True,
            )
            return False  # Default to False on unexpected issues

    def get_servers_data(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Retrieves status and version for all valid server instances by creating
        a BedrockServer object for each potential server and querying its state.

        This method replaces the use of standalone utility functions with the
        more robust and encapsulated methods of the BedrockServer class.

        Returns:
            A tuple containing:
            - A list of dictionaries, one for each successfully processed server.
            - A list of error messages for any servers that failed processing.

        Raises:
            AppFileNotFoundError: If the main server base directory (self._base_dir) is invalid.
        """
        servers_data: List[Dict[str, Any]] = []
        error_messages: List[str] = []

        if not self._base_dir or not os.path.isdir(self._base_dir):
            raise AppFileNotFoundError(str(self._base_dir), "Server base directory")

        # Iterate through items in the base directory, which are potential server names
        for server_name_candidate in os.listdir(self._base_dir):
            potential_server_path = os.path.join(self._base_dir, server_name_candidate)

            # Ensure we are only processing directories
            if not os.path.isdir(potential_server_path):
                logger.debug(
                    f"Skipping '{server_name_candidate}', as it is not a directory."
                )
                continue

            try:
                # Instantiate a BedrockServer for the potential server.
                # This automatically provides access to all its properties and methods.
                server = BedrockServer(
                    server_name=server_name_candidate,
                    settings_instance=self.settings,
                    manager_expath=self._expath,
                )

                # A valid server must be properly installed (dir and executable exist).
                # The is_installed() method handles this check cleanly.
                if not server.is_installed():
                    logger.debug(
                        f"Skipping '{server_name_candidate}': Not a valid server installation."
                    )
                    continue

                # Use the BedrockServer instance's own methods to get its data.
                # get_status() is more powerful as it can check the live process.
                # get_version() reads from the server's specific JSON config.
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
                # These are expected errors that can occur during instantiation or method calls
                msg = f"Could not get info for server '{server_name_candidate}': {e}"
                logger.warning(msg)
                error_messages.append(msg)
            except Exception as e:
                # Catch any other unexpected error for robustness
                msg = f"An unexpected error occurred while processing server '{server_name_candidate}': {e}"
                logger.error(msg, exc_info=True)
                error_messages.append(msg)

        # Sort the results alphabetically by server name
        servers_data.sort(key=lambda s: s.get("name", "").lower())

        return servers_data, error_messages
