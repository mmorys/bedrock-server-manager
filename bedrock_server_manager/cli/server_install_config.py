# bedrock-server-manager/bedrock_server_manager/cli/server_install_config.py
"""
Command-line interface functions for server installation and configuration workflows.

Provides interactive prompts and calls API functions to handle installing new servers,
and configuring properties, allowlists, and permissions for existing servers.
Uses print() for user interaction and feedback.
"""

import logging
import re
import os
import platform
from typing import Optional, List, Dict, Any

# Third-party imports
try:
    from colorama import Fore, Style, init

    COLORAMA_AVAILABLE = True
except ImportError:
    # Define dummy Fore, Style, init if colorama is not installed
    class DummyStyle:
        def __getattr__(self, name):
            return ""

    Fore = DummyStyle()
    Style = DummyStyle()

    def init(*args, **kwargs):
        pass


# Local imports
from bedrock_server_manager.api import server as server_api
from bedrock_server_manager.api import server_install_config as config_api
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.api import utils as utils_api
from bedrock_server_manager.cli import (
    server as cli_server,
)
from bedrock_server_manager.cli import system as cli_system
from bedrock_server_manager.utils.general import (
    select_option,
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)
from bedrock_server_manager.config.settings import (
    settings,
)
from bedrock_server_manager.error import (
    InvalidServerNameError,
    MissingArgumentError,
    FileOperationError,
)

logger = logging.getLogger("bedrock_server_manager")


def configure_allowlist(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    CLI handler function to interactively configure the allowlist for a server.

    Displays existing players, prompts user to add new players, and calls the
    API function to save the changes.

    Args:
        server_name: The name of the server.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        # API/Core errors are caught and printed.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Starting interactive allowlist configuration for server '{server_name}'."
    )
    try:
        # API call to get existing players (read mode)
        logger.debug(
            f"Calling API: config_api.configure_allowlist (read mode) for '{server_name}'"
        )
        response = config_api.configure_allowlist(
            server_name, base_dir, new_players_data=None
        )
        logger.debug(f"API response from configure_allowlist (read): {response}")

        existing_players: List[Dict[str, Any]] = []
        if response.get("status") == "error":
            # Print error but continue, allowing user to potentially create/overwrite
            message = response.get(
                "message", "Unknown error reading existing allowlist."
            )
            print(f"{_ERROR_PREFIX}Could not read existing allowlist: {message}")
            logger.error(
                f"CLI: Failed to read existing allowlist for '{server_name}': {message}"
            )
        else:
            existing_players = response.get("existing_players", [])
            if existing_players:
                print(f"{_INFO_PREFIX}Current players in allowlist:")
                for p in existing_players:
                    print(
                        f"  - {p.get('name', 'Unknown Name')} (Ignores Limit: {p.get('ignoresPlayerLimit', False)})"
                    )
            else:
                print(
                    f"{_INFO_PREFIX}Allowlist is currently empty or file not found. New entries will create the file."
                )

        # --- User Interaction: Add New Players ---
        new_players_to_add: List[Dict[str, Any]] = []
        print(f"\n{_INFO_PREFIX}Enter players to add/update in the allowlist.")
        while True:
            player_name = input(
                f"{Fore.CYAN}Enter player name (or type 'done' to finish):{Style.RESET_ALL} "
            ).strip()
            logger.debug(f"User input for player name: '{player_name}'")
            if player_name.lower() == "done":
                logger.debug("User finished adding players.")
                break
            if not player_name:
                print(f"{_WARN_PREFIX}Player name cannot be empty.")
                continue

            # Check if player already exists (case-insensitive)
            if any(
                p.get("name", "").lower() == player_name.lower()
                for p in existing_players + new_players_to_add
            ):
                print(
                    f"{_WARN_PREFIX}Player '{player_name}' is already in the list or added this session. Skipping duplicate."
                )
                logger.warning(f"User tried to add duplicate player: '{player_name}'")
                continue

            # Get ignoresPlayerLimit setting
            while True:  # Loop for valid y/n input
                ignore_limit_input = (
                    input(
                        f"{Fore.MAGENTA}  Should '{player_name}' ignore player limit? (y/n) [Default: n]:{Style.RESET_ALL} "
                    )
                    .strip()
                    .lower()
                )
                logger.debug(
                    f"User input for ignoresPlayerLimit ('{player_name}'): '{ignore_limit_input}'"
                )
                if ignore_limit_input in ("yes", "y"):
                    ignore_limit = True
                    break
                elif ignore_limit_input in ("no", "n", ""):  # Default empty to no
                    ignore_limit = False
                    break
                else:
                    print(f"{_WARN_PREFIX}Invalid input. Please enter 'y' or 'n'.")

            new_players_to_add.append(
                {"name": player_name, "ignoresPlayerLimit": ignore_limit}
            )
            logger.debug(
                f"Added player '{player_name}' (IgnoreLimit: {ignore_limit}) to temporary list."
            )
        # --- End User Interaction ---

        # Call API to save changes (API function handles merging/writing)
        if new_players_to_add:
            logger.debug(
                f"CLI: Calling API to save/update allowlist for server '{server_name}'."
            )
            logger.debug(
                f"Calling API: config_api.configure_allowlist with {len(new_players_to_add)} new entries."
            )
            save_response = config_api.configure_allowlist(
                server_name, base_dir, new_players_data=new_players_to_add
            )
            logger.debug(
                f"API response from configure_allowlist (save): {save_response}"
            )

            # --- User Interaction: Print Save Result ---
            if save_response.get("status") == "error":
                message = save_response.get(
                    "message", "Unknown error saving allowlist."
                )
                print(f"{_ERROR_PREFIX}{message}")
                logger.error(
                    f"CLI: Failed to save allowlist for '{server_name}': {message}"
                )
            else:
                # Use the count returned by the API if available, otherwise count from input
                added_count = len(
                    save_response.get("added_players", new_players_to_add)
                )
                message = save_response.get(
                    "message", f"{added_count} players added/updated in allowlist."
                )
                print(f"{_OK_PREFIX}{message}")
                logger.debug(
                    f"CLI: Allowlist configuration successful for '{server_name}'."
                )
            # --- End User Interaction ---
        else:
            print(f"{_INFO_PREFIX}No new players entered. Allowlist remains unchanged.")
            logger.debug(
                "CLI: No new players added by user during allowlist configuration."
            )

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to configure allowlist for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error configuring allowlist for '{server_name}': {e}",
            exc_info=True,
        )


def select_player_for_permission(
    server_name: str, base_dir: Optional[str] = None, config_dir: Optional[str] = None
) -> None:
    """
    CLI handler function to interactively select a known player and assign a permission level.

    Retrieves known players from `players.json`, prompts user for selection,
    prompts for permission level, and calls the API function to update `permissions.json`.

    Args:
        server_name: The name of the server.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        config_dir: Optional. Base directory for configuration files. Uses default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        # API errors are caught and printed.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Starting interactive permission configuration for server '{server_name}'."
    )
    try:
        # API call to get known players (requires config_dir)
        logger.debug("Calling API: player_api.get_players_from_json")
        player_response = player_api.get_players_from_json(config_dir=config_dir)
        logger.debug(f"API response from get_players_from_json: {player_response}")

        if player_response.get("status") == "error":
            message = player_response.get(
                "message", "Unknown error getting player list."
            )
            print(f"{_ERROR_PREFIX}Could not load known players: {message}")
            logger.error(
                f"CLI: Failed to get player list for permissions menu: {message}"
            )
            return

        players_data = player_response.get("players", [])
        if not players_data:
            print(
                f"{_INFO_PREFIX}No players found in the global player list (players.json). Cannot assign permissions."
            )
            logger.warning(
                "CLI: Global player list is empty. Cannot configure permissions."
            )
            return

        # Prepare lists for menu
        # Ensure we handle entries potentially missing 'name' or 'xuid' gracefully
        player_menu_options: Dict[int, Dict[str, str]] = {}
        display_index = 1
        for player_dict in players_data:
            name = player_dict.get("name")
            xuid = player_dict.get("xuid")
            if name and xuid:
                player_menu_options[display_index] = {"name": name, "xuid": xuid}
                display_index += 1
            else:
                logger.warning(
                    f"Skipping invalid player entry from global list: {player_dict}"
                )

        if not player_menu_options:
            print(
                f"{_ERROR_PREFIX}No valid players found in global player list after filtering."
            )
            logger.error("CLI: No valid player entries after filtering global list.")
            return

        cancel_option_num = len(player_menu_options) + 1

        # --- User Interaction: Player Selection Menu ---
        print(f"\n{_INFO_PREFIX}Select a player to configure permissions:")
        for i, p_data in player_menu_options.items():
            print(f"  {i}. {p_data['name']} (XUID: {p_data['xuid']})")
        print(f"  {cancel_option_num}. Cancel")
        # --- End User Interaction ---

        selected_player_info: Optional[Dict[str, str]] = None
        while True:  # Loop for valid player selection
            try:
                # --- User Interaction: Get Player Choice ---
                choice_str = input(
                    f"{Fore.CYAN}Select player (1-{cancel_option_num}):{Style.RESET_ALL} "
                ).strip()
                choice = int(choice_str)
                logger.debug(f"User entered player selection choice: {choice}")
                # --- End User Interaction ---

                if 1 <= choice <= len(player_menu_options):
                    selected_player_info = player_menu_options[choice]
                    logger.debug(f"User selected player: {selected_player_info}")
                    break  # Valid choice
                elif choice == cancel_option_num:
                    # --- User Interaction: Print Cancellation ---
                    print(f"{_INFO_PREFIX}Permission configuration canceled.")
                    # --- End User Interaction ---
                    logger.debug("User canceled permission configuration.")
                    return  # Exit function
                else:
                    # --- User Interaction: Print Invalid Choice ---
                    print(
                        f"{_WARN_PREFIX}Invalid choice '{choice}'. Please choose a valid number."
                    )
                    # --- End User Interaction ---
                    logger.debug(
                        f"User entered invalid player selection number: {choice}"
                    )
            except ValueError:
                # --- User Interaction: Print Invalid Input ---
                print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
                # --- End User Interaction ---
                logger.debug(
                    f"User entered non-numeric input for player selection: '{choice_str}'"
                )
            # Loop continues for invalid player selection

        # --- User Interaction: Permission Level Selection ---
        if selected_player_info:
            selected_name = selected_player_info["name"]
            selected_xuid = selected_player_info["xuid"]
            print(
                f"\n{_INFO_PREFIX}Selected player: {selected_name} (XUID: {selected_xuid})"
            )
            # Use the select_option helper for permission level
            permission = select_option(
                f"Select permission level for {selected_name}:",
                "member",
                "operator",
                "member",
                "visitor",
            )
            logger.debug(
                f"User selected permission level '{permission}' for XUID '{selected_xuid}'."
            )
            # --- End User Interaction ---

            # --- Call API Handler ---
            logger.debug(
                f"Calling API: config_api.configure_player_permission for XUID '{selected_xuid}'"
            )
            perm_response = config_api.configure_player_permission(
                server_name=server_name,
                xuid=selected_xuid,
                player_name=selected_name,  # Pass name for potential new entries
                permission=permission,
                base_dir=base_dir,
                # config_dir not needed by API func
            )
            logger.debug(
                f"API response from configure_player_permission: {perm_response}"
            )

            # --- User Interaction: Print Result ---
            if perm_response.get("status") == "error":
                message = perm_response.get(
                    "message", "Unknown error setting permission."
                )
                print(f"{_ERROR_PREFIX}{message}")
                logger.error(
                    f"CLI: Failed to set permission for '{selected_name}': {message}"
                )
            else:
                message = perm_response.get(
                    "message", f"Permission updated successfully for {selected_name}."
                )
                print(f"{_OK_PREFIX}{message}")
                logger.debug(f"CLI: Set permission successful for '{selected_name}'.")
            # --- End User Interaction ---

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to configure permissions for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error configuring permissions for '{server_name}': {e}",
            exc_info=True,
        )


def configure_server_properties(
    server_name: str, base_dir: Optional[str] = None
) -> None:
    """
    CLI handler function to interactively configure common `server.properties`.

    Reads current values, prompts user for new values with defaults and validation,
    and calls the API function to save changes.

    Args:
        server_name: The name of the server.
        base_dir: Optional. Base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        # API/Core errors are caught and printed.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Starting interactive server properties configuration for '{server_name}'."
    )
    print(
        f"\n{_INFO_PREFIX}Configuring server properties for '{server_name}'. Press Enter to keep the current default."
    )

    try:
        # --- Get Existing Properties via API ---
        logger.debug(
            f"Calling API: config_api.read_server_properties for '{server_name}'"
        )
        properties_response = config_api.read_server_properties(server_name, base_dir)
        logger.debug(f"API response from read_server_properties: {properties_response}")

        if properties_response.get("status") == "error":
            message = properties_response.get(
                "message", "Unknown error reading properties."
            )
            print(f"{_ERROR_PREFIX}Could not load current server properties: {message}")
            logger.error(
                f"CLI: Failed to read properties for '{server_name}': {message}"
            )
            return
        current_properties = properties_response.get("properties", {})
        logger.debug(f"Loaded current properties: {current_properties}")

        # --- Gather User Input Interactively ---
        properties_to_update: Dict[str, str] = {}

        # Helper to get input with default
        def get_property_input(
            prop_name: str, default_value: Any, prompt_text: Optional[str] = None
        ) -> str:
            current_val = current_properties.get(prop_name, str(default_value))
            prompt = prompt_text or f"Enter {prop_name}"
            user_input = input(
                f"{Fore.CYAN}{prompt} [Default: {Fore.YELLOW}{current_val}{Fore.CYAN}]:{Style.RESET_ALL} "
            ).strip()
            logger.debug(
                f"User input for '{prop_name}': '{user_input}' (Current: '{current_val}')"
            )
            return (
                user_input or current_val
            )  # Return user input or current value if empty

        # Helper for validated numeric input
        def get_validated_property_input(
            prop_name: str, default_value: Any, prompt_text: Optional[str] = None
        ) -> str:
            while True:
                user_input_raw = get_property_input(
                    prop_name, default_value, prompt_text
                )
                validation_result = config_api.validate_server_property_value(
                    prop_name, user_input_raw
                )
                if validation_result.get("status") == "success":
                    return user_input_raw  # Return validated value
                else:
                    # --- User Interaction: Print Validation Error ---
                    print(
                        f"{_ERROR_PREFIX}{validation_result.get('message', 'Invalid value.')}"
                    )
                    # --- End User Interaction ---
                    logger.debug(
                        f"Validation failed for '{prop_name}': {validation_result.get('message')}"
                    )

        # Server Name
        properties_to_update["server-name"] = get_validated_property_input(
            "server-name", "", "Enter server name (visible in LAN list)"
        )

        # Level Name (with cleaning)
        level_name_input = get_validated_property_input(
            "level-name", "Bedrock level", "Enter world folder name"
        )
        # Clean spaces immediately for user feedback/consistency, API also cleans
        properties_to_update["level-name"] = re.sub(
            r'[<>:"/\\|?* ]+', "_", level_name_input
        ).strip("_")
        if properties_to_update["level-name"] != level_name_input:
            print(
                f"{_INFO_PREFIX}Note: Level name cleaned to '{properties_to_update['level-name']}'"
            )

        # Gamemode (using select_option helper)
        gamemode_options = {"survival", "creative", "adventure"}
        properties_to_update["gamemode"] = select_option(
            "Select default gamemode:",
            current_properties.get("gamemode", "survival"),
            "survival",
            "creative",
            "adventure",
        )
        logger.debug(f"Selected gamemode: {properties_to_update['gamemode']}")

        # Difficulty
        properties_to_update["difficulty"] = select_option(
            "Select difficulty:",
            current_properties.get("difficulty", "easy"),
            "peaceful",
            "easy",
            "normal",
            "hard",
        )
        logger.debug(f"Selected difficulty: {properties_to_update['difficulty']}")

        # Allow Cheats
        properties_to_update["allow-cheats"] = select_option(
            "Allow cheats:",
            current_properties.get("allow-cheats", "false"),
            "true",
            "false",
        )
        logger.debug(f"Selected allow-cheats: {properties_to_update['allow-cheats']}")

        # Ports (validated)
        properties_to_update["server-port"] = get_validated_property_input(
            "server-port", "19132", "Enter IPv4 Port (1024-65535)"
        )
        properties_to_update["server-portv6"] = get_validated_property_input(
            "server-portv6", "19133", "Enter IPv6 Port (1024-65535)"
        )

        # LAN Visibility
        properties_to_update["enable-lan-visibility"] = select_option(
            "Announce server to LAN:",
            current_properties.get("enable-lan-visibility", "true"),
            "true",
            "false",
        )
        logger.debug(
            f"Selected enable-lan-visibility: {properties_to_update['enable-lan-visibility']}"
        )

        # Allow List
        properties_to_update["allow-list"] = select_option(
            "Enable allow list (whitelist):",
            current_properties.get("allow-list", "false"),
            "true",
            "false",
        )
        logger.debug(f"Selected allow-list: {properties_to_update['allow-list']}")

        # Max Players (validated)
        properties_to_update["max-players"] = get_validated_property_input(
            "max-players", "10", "Enter maximum players"
        )

        # Default Permission Level
        properties_to_update["default-player-permission-level"] = select_option(
            "Select default permission level for new players:",
            current_properties.get("default-player-permission-level", "member"),
            "visitor",
            "member",
            "operator",
        )
        logger.debug(
            f"Selected default-player-permission-level: {properties_to_update['default-player-permission-level']}"
        )

        # View Distance (validated)
        properties_to_update["view-distance"] = get_validated_property_input(
            "view-distance", "10", "Enter view distance (chunks, >= 5)"
        )

        # Tick Distance (validated)
        properties_to_update["tick-distance"] = get_validated_property_input(
            "tick-distance", "4", "Enter tick distance (chunks, 4-12)"
        )

        # Level Seed (no validation)
        properties_to_update["level-seed"] = get_property_input(
            "level-seed", "", "Enter level seed (leave blank for random)"
        )

        # Online Mode
        properties_to_update["online-mode"] = select_option(
            "Require Xbox Live authentication (Online Mode):",
            current_properties.get("online-mode", "true"),
            "true",
            "false",
        )
        logger.debug(f"Selected online-mode: {properties_to_update['online-mode']}")

        # Texture Pack Required
        properties_to_update["texturepack-required"] = select_option(
            "Require players to accept texture packs:",
            current_properties.get("texturepack-required", "false"),
            "true",
            "false",
        )
        logger.debug(
            f"Selected texturepack-required: {properties_to_update['texturepack-required']}"
        )

        # --- API Call to Update Properties ---
        logger.debug(
            f"CLI: Calling API to modify server properties for '{server_name}'."
        )
        logger.debug(
            f"Calling API: config_api.modify_server_properties with data: {properties_to_update}"
        )
        update_response = config_api.modify_server_properties(
            server_name, properties_to_update, base_dir
        )
        logger.debug(f"API response from modify_server_properties: {update_response}")

        # --- User Interaction: Print Result ---
        if update_response.get("status") == "error":
            message = update_response.get("message", "Unknown error saving properties.")
            print(f"{_ERROR_PREFIX}{message}")
            # If specific errors were returned:
            if "errors" in update_response and isinstance(
                update_response["errors"], dict
            ):
                for key, err_msg in update_response["errors"].items():
                    print(f"  - {key}: {err_msg}")
            logger.error(
                f"CLI: Failed to save properties for '{server_name}': {message}"
            )
        else:
            message = update_response.get(
                "message", "Server properties configured successfully."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Configure properties successful for '{server_name}'.")
        # --- End User Interaction ---

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to configure properties for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error configuring properties for '{server_name}': {e}",
            exc_info=True,
        )


def install_new_server(
    base_dir: Optional[str] = None, config_dir: Optional[str] = None
) -> None:
    """
    CLI handler function to guide the user through installing a new Bedrock server instance.

    Handles interactive prompts for server name, version, properties, allowlist,
    permissions, service creation, and initial start.

    Args:
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        config_dir: Optional. Base directory for configuration files. Uses default if None.
    """
    logger.debug("CLI: Starting new server installation workflow...")
    print(f"\n{_INFO_PREFIX}Starting New Bedrock Server Installation...")

    try:
        # Resolve directories early
        effective_base_dir = get_base_dir(base_dir)
        effective_config_dir = (
            config_dir
            if config_dir is not None
            else getattr(settings, "_config_dir", None)
        )
        if not effective_config_dir:
            raise FileOperationError("Base configuration directory not set.")

        # --- User Interaction: Get Server Name ---
        server_name: Optional[str] = None
        while True:
            s_name = input(
                f"{Fore.MAGENTA}Enter a name for the new server folder:{Style.RESET_ALL} "
            ).strip()
            logger.debug(f"User input for server name: '{s_name}'")
            if not s_name:
                print(f"{_WARN_PREFIX}Server name cannot be empty.")
                continue
            # Validate format using API function
            validation_result = utils_api.validate_server_name_format(s_name)
            if validation_result.get("status") == "success":
                server_name = s_name
                break
            else:
                print(
                    f"{_ERROR_PREFIX}{validation_result.get('message', 'Invalid format.')}"
                )
                logger.warning(f"Invalid server name format entered: '{s_name}'")
        # --- End User Interaction ---

        # --- User Interaction: Check/Handle Existing Server & Overwrite ---
        server_dir = os.path.join(effective_base_dir, server_name)
        if os.path.exists(server_dir):
            print(f"{_WARN_PREFIX}A directory named '{server_name}' already exists.")
            while True:
                confirm = (
                    input(
                        f"{Fore.RED}Overwrite existing server data? (yes/no):{Style.RESET_ALL} "
                    )
                    .strip()
                    .lower()
                )
                logger.debug(f"User confirmation for overwrite: '{confirm}'")
                if confirm in ("yes", "y"):
                    print(
                        f"{_INFO_PREFIX}Deleting existing server data for '{server_name}'..."
                    )
                    # Use API delete function
                    delete_response = server_api.delete_server_data(
                        server_name, effective_base_dir, effective_config_dir
                    )
                    if delete_response.get("status") == "error":
                        # If deletion fails, abort installation
                        message = delete_response.get(
                            "message", "Unknown error deleting existing server."
                        )
                        print(
                            f"{_ERROR_PREFIX}Failed to delete existing server: {message}"
                        )
                        logger.error(
                            f"CLI: Failed to delete existing server '{server_name}': {message}"
                        )
                        return  # Exit install workflow
                    print(f"{_OK_PREFIX}Existing server '{server_name}' deleted.")
                    logger.debug(
                        f"Deleted existing server '{server_name}' before reinstall."
                    )
                    break  # Proceed with installation
                elif confirm in ("no", "n", ""):
                    print(f"{_INFO_PREFIX}Installation canceled.")
                    logger.debug("User canceled installation due to existing server.")
                    return  # Exit install workflow
                else:
                    print(f"{_WARN_PREFIX}Invalid input. Please enter 'yes' or 'no'.")
        # --- End User Interaction ---

        # --- User Interaction: Get Target Version ---
        target_version = input(
            f"{Fore.CYAN}Enter server version (e.g., {Fore.YELLOW}1.20.81.01{Fore.CYAN}, {Fore.YELLOW}LATEST{Fore.CYAN}, {Fore.YELLOW}PREVIEW{Fore.CYAN}) [Default: LATEST]:{Style.RESET_ALL} "
        ).strip()
        if not target_version:
            target_version = "LATEST"
        logger.debug(f"User selected target version: '{target_version}'")
        # --- End User Interaction ---

        # --- Call Main Installation API ---
        # This API function handles download, extraction, basic config writing (name, target_version)
        print(
            f"{_INFO_PREFIX}Installing server '{server_name}' version '{target_version}'. This may take a moment..."
        )
        logger.debug(f"Calling API: config_api.install_new_server for '{server_name}'")
        install_result = config_api.install_new_server(
            server_name, target_version, effective_base_dir, effective_config_dir
        )
        logger.debug(f"API response from install_new_server: {install_result}")

        if install_result.get("status") == "error":
            message = install_result.get("message", "Unknown installation error.")
            print(f"{_ERROR_PREFIX}Installation failed: {message}")
            logger.error(f"CLI: Installation failed for '{server_name}': {message}")
            return  # Exit workflow on install failure

        installed_version = install_result.get("version", "UNKNOWN")
        print(
            f"{_OK_PREFIX}Server files installed (Version: {installed_version}). Proceeding with configuration..."
        )

        # --- Configuration Steps (Interactive) ---
        try:
            # 1. Configure server.properties
            print(f"\n{_INFO_PREFIX}--- Configure Server Properties ---")
            configure_server_properties(server_name, effective_base_dir)

            # 2. Configure allowlist (Optional)
            print(f"\n{_INFO_PREFIX}--- Configure Allowlist ---")
            while True:
                allowlist_choice = (
                    input(
                        f"{Fore.MAGENTA}Configure allowlist now? (y/n) [Default: n]:{Style.RESET_ALL} "
                    )
                    .strip()
                    .lower()
                )
                logger.debug(f"User choice for allowlist config: '{allowlist_choice}'")
                if allowlist_choice in ("yes", "y"):
                    configure_allowlist(server_name, effective_base_dir)
                    break
                elif allowlist_choice in ("no", "n", ""):
                    print(f"{_INFO_PREFIX}Skipping allowlist configuration.")
                    logger.debug("Skipped allowlist configuration during install.")
                    break
                else:
                    print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

            # 3. Configure permissions (Optional)
            print(f"\n{_INFO_PREFIX}--- Configure Player Permissions ---")
            while True:
                perms_choice = (
                    input(
                        f"{Fore.MAGENTA}Configure player permissions now? (y/n) [Default: n]:{Style.RESET_ALL} "
                    )
                    .strip()
                    .lower()
                )
                logger.debug(f"User choice for permissions config: '{perms_choice}'")
                if perms_choice in ("yes", "y"):
                    select_player_for_permission(
                        server_name, effective_base_dir, effective_config_dir
                    )
                    break
                elif perms_choice in ("no", "n", ""):
                    print(f"{_INFO_PREFIX}Skipping permissions configuration.")
                    logger.debug("Skipped permissions configuration during install.")
                    break
                else:
                    print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

            # 4. Create OS service (Optional)
            print(f"\n{_INFO_PREFIX}--- Configure OS Service ---")
            if platform.system() not in ("Linux", "Windows"):
                print(
                    f"{_INFO_PREFIX}Service creation not supported on this OS ({platform.system()})."
                )
                logger.debug(
                    f"Skipped service configuration (OS not supported): {platform.system()}"
                )
            else:
                while True:
                    service_choice = (
                        input(
                            f"{Fore.MAGENTA}Create and configure OS service now? (y/n) [Default: n]:{Style.RESET_ALL} "
                        )
                        .strip()
                        .lower()
                    )
                    logger.debug(f"User choice for service config: '{service_choice}'")
                    if service_choice in ("yes", "y", ""):
                        cli_system.configure_service(server_name, effective_base_dir)

                        break
                    elif service_choice in ("no", "n"):
                        print(f"{_INFO_PREFIX}Skipping OS service configuration.")
                        logger.debug("Skipped service configuration during install.")
                        break
                    else:
                        print(
                            f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'."
                        )

        except Exception as config_err:
            # Catch errors during the interactive config steps
            print(
                f"\n{_ERROR_PREFIX}An error occurred during post-installation configuration: {config_err}"
            )
            logger.error(
                f"Error during post-install config for '{server_name}': {config_err}",
                exc_info=True,
            )
            print(
                f"{_WARN_PREFIX}Installation core files are present, but configuration was interrupted."
            )
            return  # Exit workflow

        # --- Final Step: Start Server (Optional) ---
        print(f"\n{_INFO_PREFIX}--- Start Server ---")
        while True:
            start_choice = (
                input(
                    f"{Fore.CYAN}Start server '{server_name}' now? (y/n) [Default: y]:{Style.RESET_ALL} "
                )
                .strip()
                .lower()
            )
            logger.debug(f"User choice for starting server: '{start_choice}'")
            if start_choice in ("yes", "y", ""):  # Default empty to yes
                # Call CLI start function
                cli_server.start_server(server_name, effective_base_dir)
                break
            elif start_choice in ("no", "n"):
                print(
                    f"{_INFO_PREFIX}Server '{server_name}' not started. You can start it later from the main menu."
                )
                logger.debug(
                    f"User chose not to start server '{server_name}' after installation."
                )
                break
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

        print(
            f"\n{_OK_PREFIX}Server installation and configuration complete for '{server_name}'."
        )
        logger.debug(
            f"CLI: New server installation workflow completed for '{server_name}'."
        )

    except (MissingArgumentError, InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(f"CLI: Failed to install new server: {e}", exc_info=True)
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred during installation: {e}")
        logger.error(
            f"CLI: Unexpected error during new server installation: {e}", exc_info=True
        )


def update_server(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    CLI handler function to update an existing Bedrock server.

    Calls the API function and prints the result.

    Args:
        server_name: The name of the server to update.
        base_dir: Optional. Base directory for server installations. Uses config default if None.
        # config_dir removed as API update_server doesn't take it directly

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Requesting update for server '{server_name}'...")
    print(
        f"{_INFO_PREFIX}Checking for updates and attempting to update server '{server_name}'..."
    )

    try:
        logger.debug(f"Calling API: config_api.update_server for '{server_name}'")
        # API function handles getting current/target versions, check, download, install
        response: Dict[str, Any] = config_api.update_server(
            server_name, base_dir=base_dir
        )  # send_message defaults true
        logger.debug(f"API response from update_server: {response}")

        # --- User Interaction: Print Result ---
        if response.get("status") == "error":
            message = response.get("message", "Unknown error during server update.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Update server failed for '{server_name}': {message}")
        elif response.get("updated"):
            # Update was performed
            new_version = response.get("new_version", "UNKNOWN")
            message = response.get(
                "message",
                f"Server '{server_name}' updated successfully to version {new_version}.",
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(
                f"CLI: Update server successful for '{server_name}'. New version: {new_version}"
            )
        else:
            # No update was needed
            message = response.get(
                "message", f"Server '{server_name}' is already up-to-date."
            )
            print(f"{_OK_PREFIX}{message}")  # OK prefix still suitable here
            logger.debug(f"CLI: No update needed for server '{server_name}'.")
        # --- End User Interaction ---

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to call update server API for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred during server update: {e}")
        logger.error(
            f"CLI: Unexpected error updating server '{server_name}': {e}", exc_info=True
        )
