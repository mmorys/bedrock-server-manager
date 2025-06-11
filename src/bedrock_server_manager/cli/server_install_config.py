# bedrock_server_manager/cli/server_install_config.py
"""
Command-line interface functions for server installation and configuration workflows.

Provides interactive prompts and calls API functions to handle installing new servers,
and configuring properties, allowlists, and permissions for existing servers.
Uses print() for user interaction and feedback.
"""

import logging
import re
import platform
from typing import Optional, List, Dict, Any

# Third-party imports
try:
    from colorama import Fore, Style, init

    COLORAMA_AVAILABLE = True
except ImportError:

    class DummyStyle:
        def __getattr__(self, name):
            return ""

    Fore = DummyStyle()
    Style = DummyStyle()

    def init(*args, **kwargs):
        pass


# Local imports
from bedrock_server_manager.api import (
    server as server_api,
    server_install_config as config_api,
    player as player_api,
    utils as utils_api,
)
from bedrock_server_manager.cli import server as cli_server, system as cli_system
from bedrock_server_manager.utils.general import (
    select_option,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)

from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    MissingArgumentError,
)

logger = logging.getLogger(__name__)


def configure_allowlist(server_name: str) -> None:
    """CLI handler function to interactively configure the allowlist for a server."""
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Starting interactive allowlist configuration for server '{server_name}'."
    )
    try:
        logger.debug(
            f"Calling API: config_api.get_server_allowlist_api for '{server_name}'"
        )
        response = config_api.get_server_allowlist_api(server_name)
        logger.debug(f"API response from get_server_allowlist_api: {response}")

        existing_players: List[Dict[str, Any]] = []
        if response.get("status") == "error":
            message = response.get(
                "message", "Unknown error reading existing allowlist."
            )
            print(f"{_ERROR_PREFIX}Could not read existing allowlist: {message}")
        else:
            existing_players = response.get("players", [])
            if existing_players:
                print(f"{_INFO_PREFIX}Current players in allowlist:")
                for p in existing_players:
                    print(
                        f"  - {p.get('name', 'Unknown Name')} (Ignores Limit: {p.get('ignoresPlayerLimit', False)})"
                    )
            else:
                print(f"{_INFO_PREFIX}Allowlist is currently empty or file not found.")

        new_players_to_add: List[Dict[str, Any]] = []
        print(f"\n{_INFO_PREFIX}Enter players to add to the allowlist.")
        while True:
            player_name = input(
                f"{Fore.CYAN}Enter player name (or type 'done' to finish):{Style.RESET_ALL} "
            ).strip()
            if player_name.lower() == "done":
                break
            if not player_name:
                continue

            if any(
                p.get("name", "").lower() == player_name.lower()
                for p in existing_players + new_players_to_add
            ):
                print(
                    f"{_WARN_PREFIX}Player '{player_name}' is already in the list. Skipping."
                )
                continue

            ignore_limit_input = select_option(
                f"  Should '{player_name}' ignore player limit?", "n", "y", "n"
            )
            new_players_to_add.append(
                {"name": player_name, "ignoresPlayerLimit": ignore_limit_input == "y"}
            )

        if new_players_to_add:
            logger.debug(
                f"Calling API: config_api.add_players_to_allowlist_api with {len(new_players_to_add)} new entries."
            )
            save_response = config_api.add_players_to_allowlist_api(
                server_name=server_name, new_players_data=new_players_to_add
            )
            logger.debug(
                f"API response from add_players_to_allowlist_api: {save_response}"
            )

            if save_response.get("status") == "error":
                message = save_response.get(
                    "message", "Unknown error saving allowlist."
                )
                print(f"{_ERROR_PREFIX}{message}")
            else:
                message = save_response.get("message", "Allowlist updated.")
                print(f"{_OK_PREFIX}{message}")
        else:
            print(f"{_INFO_PREFIX}No new players entered. Allowlist remains unchanged.")

    except BSMError as e:
        print(f"{_ERROR_PREFIX}{e}")
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")


def remove_allowlist_players(server_name: str, players_to_remove: List[str]) -> None:
    """CLI handler to remove players from a server's allowlist."""
    if not server_name:
        print(f"{_ERROR_PREFIX}Server name must be provided.")
        return
    if not players_to_remove:
        print(f"{_ERROR_PREFIX}At least one player name must be provided.")
        return

    logger.info(
        f"CLI: Removing {len(players_to_remove)} players from allowlist for '{server_name}'."
    )
    print(
        f"{_INFO_PREFIX}Attempting to remove players from allowlist for server '{server_name}'..."
    )

    success_count, not_found_count, error_count = 0, 0, 0
    for player_name in players_to_remove:
        player_name = player_name.strip()
        if not player_name:
            continue
        try:
            response = config_api.remove_player_from_allowlist(server_name, player_name)
            if response.get("status") == "success":
                message = response.get("message", "")
                if "removed successfully" in message.lower():
                    print(f"{_OK_PREFIX}{message}")
                    success_count += 1
                elif "not found" in message.lower():
                    print(f"{_WARN_PREFIX}{message}")
                    not_found_count += 1
            else:
                message = response.get("message", f"Error removing '{player_name}'.")
                print(f"{_ERROR_PREFIX}{message}")
                error_count += 1
        except Exception as e:
            print(f"{_ERROR_PREFIX}Unexpected error removing '{player_name}': {e}")
            error_count += 1

    print(
        f"{_INFO_PREFIX}Allowlist removal finished. Removed: {success_count}, Not Found: {not_found_count}, Errors: {error_count}"
    )


def select_player_for_permission(server_name: str) -> None:
    """
    CLI handler to interactively select a known player and assign a permission level.
    Uses a manual input loop for player selection.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Starting interactive permission configuration for server '{server_name}'."
    )
    try:
        # 1. Get player data from the API
        player_response = player_api.get_all_known_players_api()
        if player_response.get("status") == "error" or not player_response.get(
            "players"
        ):
            print(
                f"{_INFO_PREFIX}No players found in the global player list (players.json)."
            )
            print(
                f"{_INFO_PREFIX}Run the 'scan-players' command or add players manually first."
            )
            return

        # 2. Build the menu data structure exactly as requested
        player_menu_options: Dict[int, Dict[str, str]] = {}
        display_index = 1
        for player_dict in player_response["players"]:
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
                f"{_ERROR_PREFIX}No valid players (with name and XUID) found in the global list."
            )
            return

        cancel_option_num = len(player_menu_options) + 1

        # 3. Print the user-friendly menu
        print(f"\n{_INFO_PREFIX}Select a player to configure permissions:")
        for i, p_data in player_menu_options.items():
            print(
                f"  {i}. {p_data['name']} {Fore.CYAN}(XUID: {p_data['xuid']}){Style.RESET_ALL}"
            )
        print(f"  {cancel_option_num}. Cancel")

        # 4. Use the requested manual input loop for player selection
        selected_player_info: Optional[Dict[str, str]] = None
        while True:
            try:
                choice_str = input(
                    f"{Fore.CYAN}Select player (1-{cancel_option_num}):{Style.RESET_ALL} "
                ).strip()
                choice = int(choice_str)
                logger.debug(f"User entered player selection choice: {choice}")

                if 1 <= choice <= len(player_menu_options):
                    selected_player_info = player_menu_options[choice]
                    logger.debug(f"User selected player: {selected_player_info}")
                    break  # Valid choice, exit loop
                elif choice == cancel_option_num:
                    print(f"{_INFO_PREFIX}Permission configuration canceled.")
                    logger.debug("User canceled permission configuration.")
                    return  # Exit function
                else:
                    print(
                        f"{_WARN_PREFIX}Invalid choice '{choice}'. Please choose a valid number."
                    )
            except ValueError:
                print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
                logger.debug(
                    f"User entered non-numeric input for player selection: '{choice_str}'"
                )

        # 5. Proceed with the logic using the selected player
        if selected_player_info:
            selected_name = selected_player_info["name"]
            selected_xuid = selected_player_info["xuid"]

            print(f"\n{_INFO_PREFIX}Selected player: {selected_name}")

            # The rest of the function remains the same, using select_option for permission level
            permission = select_option(
                f"Select permission level for {selected_name}:",
                "member",  # Default value for this prompt
                "member",
                "operator",
                "visitor",
            )

            perm_response = config_api.configure_player_permission(
                server_name=server_name,
                xuid=selected_xuid,
                player_name=selected_name,
                permission=permission,
            )

            if perm_response.get("status") == "error":
                message = perm_response.get(
                    "message", "Unknown error setting permission."
                )
                print(f"{_ERROR_PREFIX}{message}")
            else:
                message = perm_response.get(
                    "message", f"Permission updated for {selected_name}."
                )
                print(f"{_OK_PREFIX}{message}")

    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"Error in select_player_for_permission for '{server_name}': {e}",
            exc_info=True,
        )


def configure_server_properties(server_name: str) -> None:
    """
    Interactively configures common `server.properties` for a given server.

    This function guides the user through a series of prompts to set key server
    properties. It reads the current values from the server, validates new input
    in real-time, and then writes only the changed values back, triggering a
    server restart if necessary.

    Args:
        server_name: The name of the server to configure.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"CLI: Starting interactive server properties configuration for '{server_name}'."
    )
    print(f"\n{_INFO_PREFIX}Configuring server properties for '{server_name}'.")
    print(f"{_INFO_PREFIX}Press Enter at any prompt to keep the current value.")

    try:
        # 1. Get current properties from the API to display as defaults
        print(f"{_INFO_PREFIX}Loading current properties...")
        properties_response = config_api.get_server_properties_api(server_name)

        if properties_response.get("status") == "error":
            message = properties_response.get(
                "message", "Unknown error reading properties."
            )
            print(f"{_ERROR_PREFIX}Could not load server properties: {message}")
            logger.error(
                f"CLI: Failed to read properties for '{server_name}': {message}"
            )
            return

        current_properties = properties_response.get("properties", {})
        logger.debug(
            f"Loaded current properties for '{server_name}': {current_properties}"
        )

        # 2. Gather new properties from the user interactively
        properties_to_update: Dict[str, str] = {}

        # Helper function to get validated text input from the user
        def get_validated_input(
            prop_name: str, default_value: Any, prompt_text: Optional[str] = None
        ) -> str:
            """Prompts user for a property and validates it using the API until a valid value is entered."""
            while True:
                current_val_str = str(current_properties.get(prop_name, default_value))
                prompt = prompt_text or f"Enter {prop_name}"
                user_input = input(
                    f"{Fore.CYAN}{prompt} [Default: {Fore.YELLOW}{current_val_str}{Fore.CYAN}]:{Style.RESET_ALL} "
                ).strip()

                final_value = (
                    user_input or current_val_str
                )  # Use default if input is empty

                # Use the stateless API validator
                validation_result = config_api.validate_server_property_value(
                    prop_name, final_value
                )

                if validation_result.get("status") == "success":
                    return final_value  # Return the validated value
                else:
                    # Print the validation error and prompt again
                    error_message = validation_result.get("message", "Invalid value.")
                    print(f"{_WARN_PREFIX}{error_message}")
                    logger.debug(
                        f"Input validation for '{prop_name}' failed: {error_message}"
                    )

        # --- Property Prompts ---
        properties_to_update["server-name"] = get_validated_input(
            "server-name", server_name, "Enter server name (visible in LAN list)"
        )

        level_name_raw = get_validated_input(
            "level-name", "Bedrock level", "Enter world folder name"
        )
        # Clean the level name to avoid invalid characters
        properties_to_update["level-name"] = re.sub(
            r'[<>:"/\\|?* ]+', "_", level_name_raw
        ).strip("_")
        if properties_to_update["level-name"] != level_name_raw:
            print(
                f"{_INFO_PREFIX}Note: Level name cleaned to '{properties_to_update['level-name']}'"
            )

        properties_to_update["gamemode"] = select_option(
            "Select default gamemode:",
            current_properties.get("gamemode", "survival"),
            "survival",
            "creative",
            "adventure",
        )
        properties_to_update["difficulty"] = select_option(
            "Select difficulty:",
            current_properties.get("difficulty", "easy"),
            "peaceful",
            "easy",
            "normal",
            "hard",
        )
        properties_to_update["allow-cheats"] = select_option(
            "Allow cheats:",
            current_properties.get("allow-cheats", "false"),
            "true",
            "false",
        )

        properties_to_update["server-port"] = get_validated_input(
            "server-port", "19132", "Enter IPv4 Port (1024-65535)"
        )
        properties_to_update["server-portv6"] = get_validated_input(
            "server-portv6", "19133", "Enter IPv6 Port (1024-65535)"
        )

        properties_to_update["max-players"] = get_validated_input(
            "max-players", "10", "Enter maximum players"
        )

        properties_to_update["online-mode"] = select_option(
            "Require Xbox Live authentication:",
            current_properties.get("online-mode", "true"),
            "true",
            "false",
        )
        properties_to_update["allow-list"] = select_option(
            "Enable allow list (whitelist):",
            current_properties.get("allow-list", "false"),
            "true",
            "false",
        )

        properties_to_update["default-player-permission-level"] = select_option(
            "Default permission for new players:",
            current_properties.get("default-player-permission-level", "member"),
            "visitor",
            "member",
            "operator",
        )

        properties_to_update["view-distance"] = get_validated_input(
            "view-distance", "32", "Enter view distance in chunks"
        )
        properties_to_update["tick-distance"] = get_validated_input(
            "tick-distance", "4", "Enter tick simulation distance (4-12)"
        )

        properties_to_update["level-seed"] = input(
            f"{Fore.CYAN}Enter level seed (leave blank for random) [Current: {current_properties.get('level-seed', 'random')}]:{Style.RESET_ALL} "
        ).strip()

        # 3. Determine which properties have actually changed
        final_changes = {
            key: value
            for key, value in properties_to_update.items()
            if str(value) != str(current_properties.get(key))
        }

        if not final_changes:
            print(
                f"\n{_INFO_PREFIX}No properties were changed. Server configuration is up to date."
            )
            return

        # 4. Call the API to apply only the changes
        print(f"\n{_INFO_PREFIX}Applying the following changes:")
        for key, value in final_changes.items():
            print(f"  - {key}: {value}")

        update_response = config_api.modify_server_properties(
            server_name, final_changes
        )

        # 5. Report the result to the user
        if update_response.get("status") == "error":
            message = update_response.get("message", "Unknown error saving properties.")
            print(f"\n{_ERROR_PREFIX}{message}")
            logger.error(
                f"CLI: Failed to save properties for '{server_name}': {message}"
            )
        else:
            message = update_response.get(
                "message", "Server properties configured successfully."
            )
            print(f"\n{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Configure properties successful for '{server_name}'.")

    except Exception as e:
        print(
            f"\n{_ERROR_PREFIX}An unexpected error occurred during property configuration: {e}"
        )
        logger.error(
            f"CLI: Unexpected error configuring properties for '{server_name}': {e}",
            exc_info=True,
        )


def install_new_server() -> None:
    """CLI handler to guide the user through installing a new Bedrock server instance."""
    print(f"\n{_INFO_PREFIX}Starting New Bedrock Server Installation...")
    try:
        # --- Get Server Name ---
        server_name = ""
        while not server_name:
            s_name = input(
                f"{Fore.MAGENTA}Enter a name for the new server folder:{Style.RESET_ALL} "
            ).strip()
            validation_result = utils_api.validate_server_name_format(s_name)
            if validation_result.get("status") == "success":
                server_name = s_name
            else:
                print(
                    f"{_ERROR_PREFIX}{validation_result.get('message', 'Invalid format.')}"
                )

        # --- Get Target Version ---
        target_version = (
            input(
                f"{Fore.CYAN}Enter server version (e.g., LATEST, PREVIEW, 1.20.81.01) [Default: LATEST]:{Style.RESET_ALL} "
            ).strip()
            or "LATEST"
        )

        # --- Optimistic Installation Attempt ---
        print(
            f"{_INFO_PREFIX}Installing server '{server_name}' version '{target_version}'. This may take a moment..."
        )
        install_result = config_api.install_new_server(server_name, target_version)

        # --- Handle "Directory Exists" Error ---
        if install_result.get(
            "status"
        ) == "error" and "already exists" in install_result.get("message", ""):
            print(f"{_WARN_PREFIX}{install_result.get('message')}")
            overwrite_choice = select_option(
                "Overwrite existing server data?", "n", "y", "n"
            )
            if overwrite_choice == "y":
                print(
                    f"{_INFO_PREFIX}Deleting existing server data for '{server_name}'..."
                )
                delete_response = server_api.delete_server_data(server_name)
                if delete_response.get("status") == "error":
                    print(
                        f"{_ERROR_PREFIX}Failed to delete existing server: {delete_response.get('message')}"
                    )
                    return

                print(f"{_OK_PREFIX}Existing server deleted. Retrying installation...")
                install_result = config_api.install_new_server(
                    server_name, target_version
                )
            else:
                print(f"{_INFO_PREFIX}Installation canceled.")
                return

        # --- Final Installation Check ---
        if install_result.get("status") == "error":
            print(
                f"{_ERROR_PREFIX}Installation failed: {install_result.get('message')}"
            )
            return

        installed_version = install_result.get("version", "UNKNOWN")
        print(
            f"{_OK_PREFIX}Server files installed (Version: {installed_version}). Proceeding with configuration..."
        )

        # --- Configuration Steps ---
        print(f"\n{_INFO_PREFIX}--- Configure Server Properties ---")
        configure_server_properties(server_name)

        if select_option("Configure allowlist now?", "n", "y", "n") == "y":
            print(f"\n{_INFO_PREFIX}--- Configure Allowlist ---")
            configure_allowlist(server_name)

        if select_option("Configure player permissions now?", "n", "y", "n") == "y":
            print(f"\n{_INFO_PREFIX}--- Configure Player Permissions ---")
            select_player_for_permission(server_name)

        if (
            platform.system() in ("Linux", "Windows")
            and select_option("Create and configure OS service now?", "y", "y", "n")
            == "y"
        ):
            print(f"\n{_INFO_PREFIX}--- Configure OS Service ---")
            cli_system.configure_service(server_name)

        # --- Final Step: Start Server ---
        if select_option(f"Start server '{server_name}' now?", "y", "y", "n") == "y":
            print(f"\n{_INFO_PREFIX}--- Start Server ---")
            cli_server.start_server(server_name, "detached")

        print(
            f"\n{_OK_PREFIX}Server installation and configuration complete for '{server_name}'."
        )

    except BSMError as e:
        print(f"{_ERROR_PREFIX}An application error occurred: {e}")
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred during installation: {e}")


def update_server(server_name: str) -> None:
    """CLI handler function to update an existing Bedrock server."""
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    print(f"{_INFO_PREFIX}Checking for updates for server '{server_name}'...")
    try:
        response = config_api.update_server(server_name)
        if response.get("status") == "error":
            print(
                f"{_ERROR_PREFIX}{response.get('message', 'Unknown error during update.')}"
            )
        else:
            # The API message is descriptive for both "updated" and "already up-to-date" cases.
            print(f"{_OK_PREFIX}{response.get('message')}")

    except BSMError as e:
        print(f"{_ERROR_PREFIX}A server update error occurred: {e}")
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred during server update: {e}")
