# bedrock-server-manager/bedrock_server_manager/cli/server_install_config.py
import os
import logging
from colorama import Fore, Style
from bedrock_server_manager.api import server as api_server
from bedrock_server_manager.cli import server as cli_server
from bedrock_server_manager.cli import system as cli_system
from bedrock_server_manager.api import player as api_player
from bedrock_server_manager.api import utils as api_utils
from bedrock_server_manager.api import server_install_config
from bedrock_server_manager.utils.general import (
    select_option,
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)
from bedrock_server_manager.core.error import InvalidServerNameError

logger = logging.getLogger("bedrock_server_manager")


def configure_allowlist(server_name, base_dir=None):
    """Handles the user interaction for configuring the allowlist.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory where servers are stored.

    Raises:
        InvalidServerNameError: If server_name is empty
        # Other exceptions may be raised by configure_allowlist/add_players_to_allowlist
    """
    if not server_name:
        raise InvalidServerNameError("configure_allowlist: server_name is empty.")
    # Get existing players
    response = server_install_config.configure_allowlist(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
        return  # Exit if there's an error getting existing players.

    existing_players = response["existing_players"]  # Get the existing players
    if not existing_players:
        print(
            f"{_INFO_PREFIX}No existing allowlist.json found.  A new one will be created."
        )

    new_players_data = []
    print(f"{_INFO_PREFIX}Configuring allowlist.json")
    # Ask for new players
    while True:
        player_name = input(
            f"{Fore.CYAN}Enter a player's name to add to the allowlist (or type 'done' to finish): {Style.RESET_ALL}"
        ).strip()
        if player_name.lower() == "done":
            break
        if not player_name:
            print(f"{_WARN_PREFIX}Player name cannot be empty. Please try again.")
            continue

        while True:  # Loop to ensure valid input
            ignore_limit_input = input(
                f"{Fore.MAGENTA}Should this player ignore the player limit? (y/n): {Style.RESET_ALL}"
            ).lower()
            if ignore_limit_input in ("yes", "y"):
                ignore_limit = True
                break
            elif ignore_limit_input in ("no", "n", ""):  # Treat empty as "no"
                ignore_limit = False
                break
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

        new_players_data.append(
            {"ignoresPlayerLimit": ignore_limit, "name": player_name}
        )

    # Call the api with the new player data
    response = server_install_config.configure_allowlist(
        server_name, base_dir, new_players_data
    )

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
        return

    if response["added_players"]:  # Use the returned data
        print(f"{_OK_PREFIX}The following players were added to the allowlist:")
        for player in response["added_players"]:
            print(f"{Fore.CYAN}  - {player['name']}{Style.RESET_ALL}")
    else:
        print(
            f"{_INFO_PREFIX}No new players were added. Existing allowlist.json was not modified."
        )


def select_player_for_permission(server_name, base_dir=None, config_dir=None):
    """Selects a player and permission level, then calls configure_permissions."""

    if not server_name:
        raise InvalidServerNameError(
            "select_player_for_permission: server_name is empty."
        )

    # Get player data from api
    player_response = api_player.get_players_from_json(config_dir)
    if player_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{player_response['message']}")
        return

    players_data = player_response["players"]

    if not players_data:
        print(f"{_INFO_PREFIX}No players found in players.json!")
        return

    # Create lists for player names and XUIDs
    player_names = [player["name"] for player in players_data]
    xuids = [player["xuid"] for player in players_data]

    # Display player selection menu
    print(f"{_INFO_PREFIX}Select a player to add to permissions.json:")
    for i, name in enumerate(player_names):
        print(f"{i + 1}. {name}")
    print(f"{len(player_names) + 1}. Cancel")

    while True:
        try:
            choice = int(
                input(f"{Fore.CYAN}Select a player:{Style.RESET_ALL} ").strip()
            )
            if 1 <= choice <= len(player_names):
                selected_name = player_names[choice - 1]
                selected_xuid = xuids[choice - 1]
                break
            elif choice == len(player_names) + 1:
                print(f"{_OK_PREFIX}Operation canceled.")
                return  # User canceled
            else:
                print(f"{_WARN_PREFIX}Invalid choice. Please select a valid number.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    # Prompt for permission level
    permission = select_option(
        "Select a permission level:", "member", "operator", "member", "visitor"
    )

    # Configure permissions
    perm_response = server_install_config.configure_player_permission(
        server_name, selected_xuid, selected_name, permission, base_dir, config_dir
    )

    if perm_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{perm_response['message']}")
    else:
        print(f"{_OK_PREFIX}Permission updated successfully for {selected_name}.")


def configure_server_properties(server_name, base_dir=None):
    """Configures common server properties interactively."""

    if not server_name:
        raise InvalidServerNameError(
            "configure_server_properties: server_name is empty."
        )

    print(f"Configuring server properties for {server_name}")

    # --- Get Existing Properties ---
    properties_response = server_install_config.read_server_properties(
        server_name, base_dir
    )
    if properties_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{properties_response['message']}")
        return

    current_properties = properties_response["properties"]

    # --- Gather User Input ---
    DEFAULT_PORT = "19132"
    DEFAULT_IPV6_PORT = "19133"
    properties_to_update = {}

    # --- Prompts with validation ---
    input_server_name = input(
        f"{Fore.CYAN}Enter server name [Default: {Fore.YELLOW}{current_properties.get('server-name', '')}{Fore.CYAN}]:{Style.RESET_ALL} "
    ).strip()
    properties_to_update["server-name"] = input_server_name or current_properties.get(
        "server-name", ""
    )

    input_level_name = input(
        f"{Fore.CYAN}Enter level name [Default: {Fore.YELLOW}{current_properties.get('level-name', '')}{Fore.CYAN}]:{Style.RESET_ALL} "
    ).strip()
    properties_to_update["level-name"] = input_level_name or current_properties.get(
        "level-name", ""
    )
    properties_to_update["level-name"] = properties_to_update["level-name"].replace(
        " ", "_"
    )  # Clean input

    input_gamemode = select_option(
        "Select gamemode:",
        current_properties.get("gamemode", "survival"),
        "survival",
        "creative",
        "adventure",
    )
    properties_to_update["gamemode"] = input_gamemode

    input_difficulty = select_option(
        "Select difficulty:",
        current_properties.get("difficulty", "easy"),
        "peaceful",
        "easy",
        "normal",
        "hard",
    )
    properties_to_update["difficulty"] = input_difficulty

    input_allow_cheats = select_option(
        "Allow cheats:",
        current_properties.get("allow-cheats", "false"),
        "true",
        "false",
    )
    properties_to_update["allow-cheats"] = input_allow_cheats

    while True:
        input_port = input(
            f"{Fore.CYAN}Enter IPV4 Port [Default: {Fore.YELLOW}{current_properties.get('server-port', DEFAULT_PORT)}{Fore.CYAN}]:{Style.RESET_ALL} "
        ).strip()
        input_port = input_port or current_properties.get("server-port", DEFAULT_PORT)
        validation_result = server_install_config.validate_server_property_value(
            "server-port", input_port
        )
        if validation_result["status"] == "success":
            properties_to_update["server-port"] = input_port
            break
        print(f"{_ERROR_PREFIX}{validation_result['message']}")
    while True:
        input_port_v6 = input(
            f"{Fore.CYAN}Enter IPV6 Port [Default: {Fore.YELLOW}{current_properties.get('server-portv6', DEFAULT_IPV6_PORT)}{Fore.CYAN}]:{Style.RESET_ALL} "
        ).strip()
        input_port_v6 = input_port_v6 or current_properties.get(
            "server-portv6", DEFAULT_IPV6_PORT
        )
        validation_result = server_install_config.validate_server_property_value(
            "server-portv6", input_port_v6
        )
        if validation_result["status"] == "success":
            properties_to_update["server-portv6"] = input_port_v6
            break
        print(f"{_ERROR_PREFIX}{validation_result['message']}")
    input_lan_visibility = select_option(
        "Enable LAN visibility:",
        current_properties.get("enable-lan-visibility", "true"),
        "true",
        "false",
    )
    properties_to_update["enable-lan-visibility"] = input_lan_visibility

    input_allow_list = select_option(
        "Enable allow list:",
        current_properties.get("allow-list", "false"),
        "true",
        "false",
    )
    properties_to_update["allow-list"] = input_allow_list
    while True:
        input_max_players = input(
            f"{Fore.CYAN}Enter max players [Default: {Fore.YELLOW}{current_properties.get('max-players', '10')}{Fore.CYAN}]:{Style.RESET_ALL} "
        ).strip()
        input_max_players = input_max_players or current_properties.get(
            "max-players", "10"
        )
        validation_result = server_install_config.validate_server_property_value(
            "max-players", input_max_players
        )
        if validation_result["status"] == "success":
            properties_to_update["max-players"] = input_max_players
            break
        print(f"{_ERROR_PREFIX}{validation_result['message']}")
    input_permission_level = select_option(
        "Select default permission level:",
        current_properties.get("default-player-permission-level", "member"),
        "visitor",
        "member",
        "operator",
    )
    properties_to_update["default-player-permission-level"] = input_permission_level
    while True:
        input_render_distance = input(
            f"{Fore.CYAN}Default render distance [Default: {Fore.YELLOW}{current_properties.get('view-distance', '10')}{Fore.CYAN}]:{Style.RESET_ALL} "
        ).strip()
        input_render_distance = input_render_distance or current_properties.get(
            "view-distance", "10"
        )
        validation_result = server_install_config.validate_server_property_value(
            "view-distance", input_render_distance
        )
        if validation_result["status"] == "success":
            properties_to_update["view-distance"] = input_render_distance
            break
        print(f"{_ERROR_PREFIX}{validation_result['message']}")
    while True:
        input_tick_distance = input(
            f"{Fore.CYAN}Default tick distance [Default: {Fore.YELLOW}{current_properties.get('tick-distance', '4')}{Fore.CYAN}]:{Style.RESET_ALL} "
        ).strip()
        input_tick_distance = input_tick_distance or current_properties.get(
            "tick-distance", "4"
        )
        validation_result = server_install_config.validate_server_property_value(
            "tick-distance", input_tick_distance
        )
        if validation_result["status"] == "success":
            properties_to_update["tick-distance"] = input_tick_distance
            break
        print(f"{_ERROR_PREFIX}{validation_result['message']}")
    input_level_seed = input(
        f"{Fore.CYAN}Enter level seed:{Style.RESET_ALL} "
    ).strip()  # No default or validation
    properties_to_update["level-seed"] = input_level_seed
    input_online_mode = select_option(
        "Enable online mode:",
        current_properties.get("online-mode", "true"),
        "true",
        "false",
    )
    properties_to_update["online-mode"] = input_online_mode
    input_texturepack_required = select_option(
        "Require texture pack:",
        current_properties.get("texturepack-required", "false"),
        "true",
        "false",
    )
    properties_to_update["texturepack-required"] = input_texturepack_required
    # --- Update Properties ---
    update_response = server_install_config.modify_server_properties(
        server_name, properties_to_update, base_dir
    )

    if update_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{update_response['message']}")
    else:
        print(f"{_OK_PREFIX}Server properties configured successfully.")


def install_new_server(base_dir=None, config_dir=None):
    """Installs a new server."""
    base_dir = get_base_dir(base_dir)

    print("Installing new server...")

    while True:
        server_name = input(
            f"{Fore.MAGENTA}Enter server folder name:{Style.RESET_ALL} "
        ).strip()
        validation_result = api_utils.validate_server_name_format(server_name)
        if validation_result["status"] == "success":
            break
        print(f"{_ERROR_PREFIX}{validation_result['message']}")
    server_dir = os.path.join(base_dir, server_name)
    if os.path.exists(server_dir):
        print(f"{_WARN_PREFIX}Folder {server_name} already exists")
        while True:
            continue_response = (
                input(
                    f"{Fore.RED}Folder {Fore.YELLOW}{server_name}{Fore.RED} already exists, continue? (y/n):{Style.RESET_ALL} "
                )
                .lower()
                .strip()
            )
            if continue_response in ("yes", "y"):
                delete_response = api_server.delete_server_data(
                    server_name, base_dir, config_dir
                )
                if delete_response["status"] == "error":
                    print(f"{_ERROR_PREFIX}{delete_response['message']}")
                    return  # Exit if deletion failed.
                break
            elif continue_response in ("no", "n", ""):
                print(f"{_WARN_PREFIX}Exiting")
                return  # User cancelled
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

    target_version = input(
        f"{Fore.CYAN}Enter server version (e.g., {Fore.YELLOW}LATEST{Fore.CYAN} or {Fore.YELLOW}PREVIEW{Fore.CYAN}):{Style.RESET_ALL} "
    ).strip()
    if not target_version:
        target_version = "LATEST"

    # Main installation call
    install_result = server_install_config.install_new_server(
        server_name, target_version, base_dir, config_dir
    )
    if install_result["status"] == "error":
        print(f"{_ERROR_PREFIX}{install_result['message']}")
        return

    # Configure server properties
    configure_server_properties(server_name, base_dir)

    # Allowlist configuration
    while True:
        allowlist_response = (
            input(f"{Fore.MAGENTA}Configure allow-list? (y/n):{Style.RESET_ALL} ")
            .lower()
            .strip()
        )
        if allowlist_response in ("yes", "y"):
            configure_allowlist(server_name, base_dir)  # call new function
            break
        elif allowlist_response in ("no", "n", ""):
            print(f"{_INFO_PREFIX}Skipping allow-list configuration.")
            break
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")
    # Permissions configuration (interactive)
    while True:
        permissions_response = (
            input(f"{Fore.MAGENTA}Configure permissions? (y/n):{Style.RESET_ALL} ")
            .lower()
            .strip()
        )
        if permissions_response in ("yes", "y"):
            try:
                select_player_for_permission(server_name, base_dir)
            except Exception as e:
                print(f"{_ERROR_PREFIX}Failed to configure permissions: {e}")
            break
        elif permissions_response in ("no", "n", ""):
            print(f"{_INFO_PREFIX}Skipping permissions configuration.")
            break
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

    # Create a service (interactive)
    while True:
        service_response = (
            input(f"{Fore.MAGENTA}Create a service? (y/n):{Style.RESET_ALL} ")
            .lower()
            .strip()
        )
        if service_response in ("yes", "y"):
            cli_system.create_service(server_name, base_dir)
            break
        elif service_response in ("no", "n", ""):
            print(f"{_INFO_PREFIX}Skipping service configuration.")
            break
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

    # Start the server (interactive)
    while True:
        start_choice = (
            input(
                f"{Fore.CYAN}Do you want to start {Fore.YELLOW}{server_name}{Fore.CYAN}? (y/n):{Style.RESET_ALL} "
            )
            .lower()
            .strip()
        )
        if start_choice in ("yes", "y"):
            try:
                cli_server.start_server(server_name, base_dir)
            except Exception as e:
                print(f"{_ERROR_PREFIX}Failed to start server: {e}")
            break
        elif start_choice in ("no", "n", ""):
            print(f"{_INFO_PREFIX}{server_name} not started.")
            break
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")
    print(f"{_OK_PREFIX}Server installation complete.")  # Success message


def update_server(server_name, base_dir=None, config_dir=None):
    """Updates an existing server."""

    if not server_name:
        raise InvalidServerNameError("update_server: server_name is empty.")

    response = server_install_config.update_server(server_name, base_dir, config_dir)

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    elif response["updated"]:
        print(
            f"{_OK_PREFIX}{server_name} updated successfully to version {response['new_version']}."
        )
    else:
        print(f"{_OK_PREFIX}No update needed for {server_name}.")
