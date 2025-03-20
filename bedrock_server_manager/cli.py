# bedrock-server-manager/bedrock_server_manager/cli.py
import os
import re
import sys
import time
import logging
import platform
from datetime import datetime
from colorama import Fore, Style
import xml.etree.ElementTree as ET
from bedrock_server_manager import handlers
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.utils.general import (
    select_option,
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)
from bedrock_server_manager.core.error import (
    MissingArgumentError,
    InvalidServerNameError,
    InvalidInputError,
)
from bedrock_server_manager.core.server import server as server_base

logger = logging.getLogger("bedrock_server_manager")


def get_server_name(base_dir=None):
    """Prompts the user for a server name and validates its existence.

    Args:
        base_dir (str): The base directory for servers.

    Returns:
        str: The validated server name, or None if the user cancels.
    """

    while True:
        server_name = input(
            f"{Fore.MAGENTA}Enter server name (or type 'exit' to cancel): {Style.RESET_ALL}"
        ).strip()

        if server_name.lower() == "exit":
            print(f"{_OK_PREFIX}Operation canceled.")
            return None  # User canceled

        response = handlers.validate_server_name_handler(server_name, base_dir)

        if response["status"] == "success":
            print(f"{_OK_PREFIX}Server {server_name} found.")
            return server_name
        else:
            print(f"{_ERROR_PREFIX}{response['message']}")


def list_servers_status(base_dir=None, config_dir=None):
    """Lists the status and version of all servers."""

    response = handlers.get_all_servers_status_handler(base_dir, config_dir)

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
        return

    servers = response["servers"]

    print(f"{Fore.MAGENTA}Servers Status:{Style.RESET_ALL}")
    print("---------------------------------------------------")
    print(f"{'SERVER NAME':<20} {'STATUS':<20} {'VERSION':<10}")
    print("---------------------------------------------------")

    if not servers:
        print("No servers found.")
    else:
        for server_data in servers:
            status = server_data["status"]
            version = server_data["version"]

            if status == "RUNNING":
                status_str = f"{Fore.GREEN}{status}{Style.RESET_ALL}"
            elif status in ("STARTING", "RESTARTING", "STOPPING", "INSTALLED"):
                status_str = f"{Fore.YELLOW}{status}{Style.RESET_ALL}"
            elif status == "STOPPED":
                status_str = f"{Fore.RED}{status}{Style.RESET_ALL}"
            else:
                status_str = f"{Fore.RED}UNKNOWN{Style.RESET_ALL}"

            version_str = (
                f"{Fore.WHITE}{version}{Style.RESET_ALL}"
                if version != "UNKNOWN"
                else f"{Fore.RED}UNKNOWN{Style.RESET_ALL}"
            )
            print(
                f"{Fore.CYAN}{server_data['name']:<20}{Style.RESET_ALL} {status_str:<20}  {version_str:<10}"
            )

    print("---------------------------------------------------")
    print()


def list_servers_loop(base_dir=None, config_dir=None):
    """Continuously lists servers and their statuses."""
    while True:
        os.system("cls" if platform.system() == "Windows" else "clear")
        list_servers_status(base_dir, config_dir)
        time.sleep(5)


def handle_configure_allowlist(server_name, base_dir=None):
    """Handles the user interaction for configuring the allowlist.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory where servers are stored.

    Raises:
        InvalidServerNameError: If server_name is empty
        # Other exceptions may be raised by configure_allowlist/add_players_to_allowlist
    """
    if not server_name:
        raise InvalidServerNameError(
            "handle_configure_allowlist: server_name is empty."
        )
    # Get existing players
    response = handlers.configure_allowlist_handler(server_name, base_dir)
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

    # Call the handler with the new player data
    response = handlers.configure_allowlist_handler(
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


def handle_add_players(players, config_dir):
    """Handles the user interaction and logic for adding players to the players.json file."""

    response = handlers.add_players_handler(players, config_dir)

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
        return

    print("Players added successfully.")  # Only print on success


def select_player_for_permission(server_name, base_dir=None, config_dir=None):
    """Selects a player and permission level, then calls configure_permissions."""

    if not server_name:
        raise InvalidServerNameError(
            "select_player_for_permission: server_name is empty."
        )

    # Get player data from the handler
    player_response = handlers.get_players_from_json_handler(config_dir)
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

    # Call the handler to configure permissions
    perm_response = handlers.configure_player_permission_handler(
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
    properties_response = handlers.read_server_properties_handler(server_name, base_dir)
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
        validation_result = handlers.validate_property_value_handler(
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
        validation_result = handlers.validate_property_value_handler(
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
        validation_result = handlers.validate_property_value_handler(
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
        validation_result = handlers.validate_property_value_handler(
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
        validation_result = handlers.validate_property_value_handler(
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
    update_response = handlers.modify_server_properties_handler(
        server_name, properties_to_update, base_dir
    )

    if update_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{update_response['message']}")
    else:
        print(f"{_OK_PREFIX}Server properties configured successfully.")


def handle_download_bedrock_server(
    server_name, base_dir=None, target_version="LATEST", in_update=False
):
    """Handles downloading and installing the Bedrock server, including UI."""

    if not server_name:
        raise InvalidServerNameError(
            "handle_download_bedrock_server: server_name is empty."
        )

    response = handlers.download_and_install_server_handler(
        server_name, base_dir, target_version, in_update
    )

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Installed Bedrock server version: {response['version']}")
        print(f"{_OK_PREFIX}Bedrock server download process finished")


def install_new_server(base_dir=None, config_dir=None):
    """Installs a new server."""
    base_dir = get_base_dir(base_dir)

    print("Installing new server...")

    while True:
        server_name = input(
            f"{Fore.MAGENTA}Enter server folder name:{Style.RESET_ALL} "
        ).strip()
        validation_result = handlers.validate_server_name_format_handler(server_name)
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
                delete_response = handlers.delete_server_data_handler(
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

    # Main installation handler call
    install_result = handlers.install_new_server_handler(
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
            handle_configure_allowlist(server_name, base_dir)  # call new function
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
            create_service(server_name, base_dir)
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
                handle_start_server(server_name, base_dir)
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

    response = handlers.update_server_handler(server_name, base_dir, config_dir)

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    elif response["updated"]:
        print(
            f"{_OK_PREFIX}{server_name} updated successfully to version {response['new_version']}."
        )
    else:
        print(f"{_OK_PREFIX}No update needed for {server_name}.")


def handle_enable_user_lingering():
    """Handles enabling user lingering, with user interaction."""

    if platform.system() != "Linux":
        print(f"{_INFO_PREFIX}User lingering is only applicable on Linux systems.")
        return

    # Check if lingering is already enabled
    check_response = handlers.check_user_lingering_enabled_handler()
    if check_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{check_response['message']}")
        return  # Exit if we can't check the status.

    if check_response["enabled"]:
        print(f"{_INFO_PREFIX}Lingering is already enabled for the current user.")
        return  # Already enabled

    while True:
        response = (
            input(
                f"{Fore.CYAN}Do you want to enable lingering? (y/n):{Style.RESET_ALL} "
            )
            .lower()
            .strip()
        )
        if response in ("yes", "y"):
            enable_response = handlers.enable_user_lingering_handler()
            if enable_response["status"] == "success":
                print(f"{_OK_PREFIX}Lingering enabled successfully.")
                break  # Success
            else:
                print(f"{_ERROR_PREFIX}{enable_response['message']}")
                # We *don't* return here. This gives the user a chance to try again
                # or to cancel.
        elif response in ("no", "n", ""):
            print(
                f"{_INFO_PREFIX}Lingering not enabled. User services might not start automatically."
            )
            break  # Exit loop.
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")


def create_service(server_name, base_dir=None):
    """Creates a systemd service (Linux) or sets autoupdate config (Windows)."""
    if base_dir is None:
        base_dir = settings.get("BASE_DIR")
    if not server_name:
        raise InvalidServerNameError("create_service: server_name is empty.")
    if platform.system() == "Linux":
        # Ask user if they want auto-update
        while True:
            response = (
                input(
                    f"{Fore.CYAN}Do you want to enable auto-update on start for {Fore.YELLOW}{server_name}{Fore.CYAN}? (y/n):{Style.RESET_ALL} "
                )
                .lower()
                .strip()
            )
            if response in ("yes", "y"):
                autoupdate = True
                break
            elif response in ("no", "n", ""):
                autoupdate = False
                break
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

        while True:
            response = (
                input(
                    f"{Fore.CYAN}Do you want to enable autostart for {Fore.YELLOW}{server_name}{Fore.CYAN}? (y/n):{Style.RESET_ALL} "
                )
                .lower()
                .strip()
            )
            if response in ("yes", "y"):
                autostart = True
                break
            elif response in ("no", "n", ""):
                autostart = False
                break
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

        response = handlers.create_systemd_service_handler(
            server_name, base_dir, autoupdate, autostart
        )
        if response["status"] == "error":
            print(f"{_ERROR_PREFIX}{response['message']}")
            return

        # Call the *handler* for enabling user lingering
        lingering_response = handlers.check_user_lingering_enabled_handler()
        if lingering_response["status"] == "error":
            print(
                f"{_ERROR_PREFIX}Error checking lingering status: {lingering_response['message']}"
            )
        elif not lingering_response["enabled"]:
            handle_enable_user_lingering()  # Call the CLI function for interaction

    elif platform.system() == "Windows":
        while True:
            response = (
                input(
                    f"{Fore.CYAN}Do you want to enable auto-update on start for {Fore.YELLOW}{server_name}{Fore.CYAN}? (y/n):{Style.RESET_ALL} "
                )
                .lower()
                .strip()
            )
            if response in ("yes", "y"):
                autoupdate_value = "true"
                break
            elif response in ("no", "n", ""):
                autoupdate_value = "false"
                break
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

        response = handlers.set_windows_autoupdate_handler(
            server_name, autoupdate_value, base_dir
        )
        if response["status"] == "error":
            print(f"{_ERROR_PREFIX}{response['message']}")
        else:
            print(
                f"{_OK_PREFIX}Successfully updated autoupdate in config.json for server: {server_name}"
            )

    else:
        print(f"{_ERROR_PREFIX}Unsupported operating system for service creation.")
        raise OSError("Unsupported operating system for service creation.")


def enable_service(server_name, base_dir=None):
    """Enables a systemd service (Linux) or handles the Windows case."""
    if not server_name:
        raise InvalidServerNameError("enable_service: server_name is empty.")

    response = handlers.enable_service_handler(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    elif platform.system() == "Windows":
        print(
            "Windows doesn't currently support all script features. You may want to look into Windows Subsystem Linux (wsl)."
        )
    elif platform.system() != "Linux":
        raise OSError("Unsupported OS")
    else:
        print(f"{_OK_PREFIX}Service enabled successfully.")


def disable_service(server_name, base_dir=None):
    """Disables a systemd service (Linux) or handles the Windows case."""
    if not server_name:
        raise InvalidServerNameError("disable_service: server_name is empty.")

    response = handlers.disable_service_handler(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    elif platform.system() == "Windows":
        print(
            "Windows doesn't currently support all script features. You may want to look into Windows Subsystem Linux (wsl)."
        )
    elif platform.system() != "Linux":
        raise OSError("Unsupported OS")
    else:
        print(f"{_OK_PREFIX}Service disabled successfully.")


def handle_start_server(server_name, base_dir=None):
    """Starts the Bedrock server."""
    if not server_name:
        raise InvalidServerNameError("start_server: server_name is empty.")

    response = handlers.start_server_handler(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Server started successfully.")


def handle_systemd_start(server_name, base_dir=None):
    """Starts the Bedrock server."""
    if not server_name:
        raise InvalidServerNameError("start_server: server_name is empty.")

    response = handlers.systemd_start_server_handler(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Server started successfully.")


def handle_stop_server(server_name, base_dir=None):
    """Stops the Bedrock server."""
    if not server_name:
        raise InvalidServerNameError("stop_server: server_name is empty.")

    response = handlers.stop_server_handler(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Server stopped successfully.")


def handle_systemd_stop(server_name, base_dir=None):
    """Stops the Bedrock server."""

    if not server_name:
        raise InvalidServerNameError("start_server: server_name is empty.")

    response = handlers.systemd_stop_server_handler(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Server stopped successfully.")


def restart_server(server_name, base_dir=None):
    """Restarts the Bedrock server."""
    if not server_name:
        raise InvalidServerNameError("restart_server: server_name is empty.")

    response = handlers.restart_server_handler(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Server restarted successfully.")


def _monitor(server_name, base_dir):
    """Monitor for Bedrock server (UI portion)."""

    if not server_name:
        raise InvalidServerNameError("_monitor: server_name is empty.")

    print(f"{_INFO_PREFIX}Monitoring resource usage for: {server_name}")
    try:
        while True:
            response = handlers.get_bedrock_process_info_handler(server_name, base_dir)
            if response["status"] == "error":
                print(f"{_ERROR_PREFIX}{response['message']}")
                return  # Exit if process not found

            process_info = response["process_info"]

            # Clear screen and display output (CLI-specific)
            os.system("cls" if platform.system() == "Windows" else "clear")
            print("---------------------------------")
            print(f" Monitoring:  {server_name} ")
            print("---------------------------------")
            print(f"PID:          {process_info['pid']}")
            print(f"CPU Usage:    {process_info['cpu_percent']:.1f}%")
            print(f"Memory Usage: {process_info['memory_mb']:.1f} MB")
            print(f"Uptime:       {process_info['uptime']}")
            print("---------------------------------")
            print("Press CTRL + C to exit")

            time.sleep(2)  # Update interval

    except KeyboardInterrupt:
        print(f"{_OK_PREFIX}Monitoring stopped.")


def monitor_service_usage(server_name, base_dir=None):
    """Monitors the CPU and memory usage of the Bedrock server."""
    base_dir = get_base_dir(base_dir)
    _monitor(server_name, base_dir)


def attach_console(server_name, base_dir=None):
    """Attaches to the server console."""
    if not server_name:
        raise InvalidServerNameError("attach_console: server_name is empty.")

    if platform.system() == "Linux":
        response = handlers.attach_to_screen_session_handler(server_name, base_dir)
        if response["status"] == "error":
            print(f"{_ERROR_PREFIX}{response['message']}")
    elif platform.system() == "Windows":
        print(
            "Windows doesn't currently support attaching to the console. You may want to look into Windows Subsystem for Linux (WSL)."
        )
    else:
        print("attach_console not supported on this platform")
        raise OSError("Unsupported operating system")


def delete_server(server_name, base_dir=None, config_dir=None):
    """Deletes a Bedrock server."""
    base_dir = get_base_dir(base_dir)

    if not server_name:
        raise InvalidServerNameError("delete_server: server_name is empty.")

    # Confirm deletion
    confirm = (
        input(
            f"{Fore.RED}Are you sure you want to delete the server {Fore.YELLOW}{server_name}{Fore.RED}? This action is irreversible! (y/n):{Style.RESET_ALL} "
        )
        .lower()
        .strip()
    )
    if confirm not in ("y", "yes"):
        print(f"{_INFO_PREFIX}Server deletion canceled.")
        return

    # Call handler to delete server data
    response = handlers.delete_server_data_handler(server_name, base_dir, config_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Server {server_name} deleted successfully.")


def handle_extract_world(server_name, selected_file, base_dir=None, from_addon=False):
    """Handles extracting a world, including stopping/starting the server."""

    if not server_name:
        raise InvalidServerNameError("extract_world: server_name is empty")

    # Call the handler, controlling stop/start based on from_addon
    response = handlers.extract_world_handler(
        server_name, selected_file, base_dir, stop_start_server=not from_addon
    )
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}World extracted successfully.")


def handle_export_world(server_name, base_dir=None):
    """Handles exporting the world."""
    if not server_name:
        raise InvalidServerNameError("export_world: server_name is empty.")

    response = handlers.export_world_handler(server_name, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}World exported successfully to: {response['backup_file']}")


def handle_prune_old_backups(
    server_name, file_name=None, backup_keep=None, base_dir=None
):
    """Prunes old backups, keeping only the most recent ones. (UI and setup)"""
    if not server_name:
        raise InvalidServerNameError("prune_old_backups: server_name is empty.")

    response = handlers.prune_old_backups_handler(
        server_name, file_name, backup_keep, base_dir
    )
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Old backups pruned successfully.")


def handle_backup_server(
    server_name, backup_type, file_to_backup=None, change_status=True, base_dir=None
):
    """Backs up a server's world or a specific configuration file."""
    if not server_name:
        raise InvalidServerNameError("backup_server: server_name is empty.")
    if not backup_type:
        raise MissingArgumentError("backup_server: backup_type is empty.")

    if backup_type == "world":
        response = handlers.backup_world_handler(
            server_name, base_dir, stop_start_server=change_status
        )
    elif backup_type == "config":
        if not file_to_backup:
            raise MissingArgumentError(
                "backup_server: file_to_backup is empty when backup_type is config."
            )
        response = handlers.backup_config_file_handler(
            server_name, file_to_backup, base_dir, stop_start_server=change_status
        )
    elif backup_type == "all":
        response = handlers.backup_all_handler(
            server_name, base_dir, stop_start_server=change_status
        )
    else:
        raise InvalidInputError(f"Invalid backup type: {backup_type}")

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Backup completed successfully.")

    # Prune old backups after the backup is complete.
    prune_response = handlers.prune_old_backups_handler(
        server_name, file_to_backup, base_dir=base_dir
    )
    if prune_response["status"] == "error":
        print(f"{_ERROR_PREFIX}Error pruning old backups: {prune_response['message']}")


def backup_menu(server_name, base_dir):
    """Displays the backup menu and handles user input."""

    if not server_name:
        raise InvalidServerNameError("backup_menu: server_name is empty.")

    while True:
        print(f"{Fore.MAGENTA}What do you want to backup:{Style.RESET_ALL}")
        print("1. Backup World")
        print("2. Backup Configuration File")
        print("3. Backup All")
        print("4. Cancel")

        choice = input(
            f"{Fore.CYAN}Select the type of backup:{Style.RESET_ALL} "
        ).strip()

        if choice == "1":
            handle_backup_server(
                server_name, "world", change_status=True, base_dir=base_dir
            )  # Stop/start server
            break
        elif choice == "2":
            print(
                f"{Fore.MAGENTA}Select configuration file to backup:{Style.RESET_ALL}"
            )
            print("1. allowlist.json")
            print("2. permissions.json")
            print("3. server.properties")
            print("4. Cancel")

            config_choice = input(f"{Fore.CYAN}Choose file:{Style.RESET_ALL} ").strip()
            if config_choice == "1":
                file_to_backup = "allowlist.json"
            elif config_choice == "2":
                file_to_backup = "permissions.json"
            elif config_choice == "3":
                file_to_backup = "server.properties"
            elif config_choice == "4":
                print(f"{_INFO_PREFIX}Backup operation canceled.")
                return  # User canceled
            else:
                print(f"{_WARN_PREFIX}Invalid selection, please try again.")
                continue
            handle_backup_server(
                server_name,
                "config",
                file_to_backup,
                change_status=True,
                base_dir=base_dir,
            )  # Stop/Start
            break
        elif choice == "3":
            handle_backup_server(
                server_name, "all", change_status=True, base_dir=base_dir
            )  # Stop/Start
            break
        elif choice == "4":
            print(f"{_INFO_PREFIX}Backup operation canceled.")
            return
        else:
            print(f"{_WARN_PREFIX}Invalid selection, please try again.")


def handle_restore_server(
    server_name, backup_file, restore_type, change_status=True, base_dir=None
):
    """Restores a server from a backup file."""

    if not server_name:
        raise InvalidServerNameError("restore_server: server_name is empty.")
    if not restore_type:
        raise MissingArgumentError("restore_server: restore_type is empty.")

    if restore_type == "world":
        if not backup_file:
            raise MissingArgumentError("restore_server: backup_file is empty.")
        response = handlers.restore_world_handler(
            server_name, backup_file, base_dir, stop_start_server=change_status
        )
    elif restore_type == "config":
        if not backup_file:
            raise MissingArgumentError("restore_server: backup_file is empty.")
        response = handlers.restore_config_file_handler(
            server_name, backup_file, base_dir, stop_start_server=change_status
        )
    elif restore_type == "all":
        response = handlers.restore_all_handler(
            server_name, base_dir, stop_start_server=change_status
        )
    else:
        raise InvalidInputError(f"Invalid restore type: {restore_type}")

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Restoration completed successfully.")


def restore_menu(server_name, base_dir):
    """Displays the restore menu and handles user interaction."""

    if not server_name:
        raise InvalidServerNameError("restore_menu: server_name is empty.")

    while True:
        print(f"{Fore.MAGENTA}Select the type of backup to restore:{Style.RESET_ALL}")
        print("1. World")
        print("2. Configuration File")
        print("3. Restore All")
        print("4. Cancel")

        choice = input(
            f"{Fore.CYAN}What do you want to restore:{Style.RESET_ALL} "
        ).strip()
        if choice == "1":
            restore_type = "world"
        elif choice == "2":
            restore_type = "config"
        elif choice == "3":
            handle_restore_server(server_name, None, "all", base_dir=base_dir)
            return
        elif choice == "4":
            print(f"{_INFO_PREFIX}Restore operation canceled.")
            return  # User canceled
        else:
            print(f"{_WARN_PREFIX}Invalid selection. Please choose again.")
            continue

        # List available backups (using the handler)
        list_response = handlers.list_backups_handler(
            server_name, restore_type, base_dir
        )
        if list_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{list_response['message']}")
            return  # Exit if no backups found

        backup_files = list_response["backups"]

        # Create a numbered list of backup files (CLI-specific)
        backup_map = {}
        print(f"{Fore.MAGENTA}Available backups:{Style.RESET_ALL}")
        for i, file in enumerate(backup_files):
            backup_map[i + 1] = file
            print(f"{i + 1}. {os.path.basename(file)}")
        print(f"{len(backup_map) + 1}. Cancel")  # Add a cancel option

        while True:
            try:
                choice = int(
                    input(
                        f"{Fore.CYAN}Select a backup to restore (1-{len(backup_map) + 1}):{Style.RESET_ALL} "
                    ).strip()
                )
                if 1 <= choice <= len(backup_map):
                    selected_file = backup_map[choice]
                    handle_restore_server(
                        server_name, selected_file, restore_type, True, base_dir
                    )  # Stop/Start
                    return
                elif choice == len(backup_map) + 1:
                    print(f"{_INFO_PREFIX}Restore operation canceled.")
                    return  # User canceled
                else:
                    print(f"{_WARN_PREFIX}Invalid selection. Please choose again.")
            except ValueError:
                print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")


def handle_install_addon(server_name, addon_file, base_dir=None):
    """Handles the installation of an addon, including stopping/starting the server."""

    if not server_name:
        raise InvalidServerNameError("handle_install_addon: server_name is empty.")

    response = handlers.install_addon_handler(server_name, addon_file, base_dir)
    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    else:
        print(f"{_OK_PREFIX}Addon installed successfully.")


def install_worlds(server_name, base_dir=None, content_dir=None):
    """Provides a menu to select and install .mcworld files."""
    if not server_name:
        raise InvalidServerNameError("install_worlds: server_name is empty.")

    base_dir = get_base_dir(base_dir)
    if content_dir is None:
        content_dir = settings.get("CONTENT_DIR")
        content_dir = os.path.join(content_dir, "worlds")

    # Use the handler to list files
    list_response = handlers.list_content_files_handler(content_dir, ["mcworld"])
    if list_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{list_response['message']}")
        return

    mcworld_files = list_response["files"]

    # Create a list of base file names
    file_names = [os.path.basename(file) for file in mcworld_files]

    # Display the menu and get user selection
    print(f"{_INFO_PREFIX}Available worlds to install:{Style.RESET_ALL}")
    for i, file_name in enumerate(file_names):
        print(f"{i + 1}. {file_name}")
    print(f"{len(file_names) + 1}. Cancel")

    while True:
        try:
            choice = int(
                input(
                    f"{Fore.CYAN}Select a world to install (1-{len(file_names) + 1}):{Style.RESET_ALL} "
                ).strip()
            )
            if 1 <= choice <= len(file_names):
                selected_file = mcworld_files[choice - 1]
                break  # Valid choice
            elif choice == len(file_names) + 1:
                print(f"{_INFO_PREFIX}World installation canceled.")
                return  # User canceled
            else:
                print(f"{_WARN_PREFIX}Invalid selection. Please choose a valid option.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    # Confirm deletion of existing world.
    print(f"{_WARN_PREFIX}Installing a new world will DELETE the existing world!")
    while True:
        confirm_choice = (
            input(
                f"{Fore.RED}Are you sure you want to proceed? (y/n):{Style.RESET_ALL} "
            )
            .lower()
            .strip()
        )
        if confirm_choice in ("yes", "y"):
            break
        elif confirm_choice in ("no", "n"):
            print(f"{_INFO_PREFIX}World installation canceled.")
            return  # User canceled
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")

    # Use handler to extract the world
    extract_response = handlers.extract_world_handler(
        server_name, selected_file, base_dir
    )  # Always stop/start
    if extract_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{extract_response['message']}")
    else:
        print(f"{_OK_PREFIX}World extracted successfully.")


def install_addons(server_name, base_dir, content_dir=None):
    """Installs addons (.mcaddon or .mcpack files) to the server."""

    if not server_name:
        raise InvalidServerNameError("install_addons: server_name is empty.")

    base_dir = get_base_dir(base_dir)
    if content_dir is None:
        content_dir = os.path.join(settings.get("CONTENT_DIR"), "addons")

    # Use handler to list files
    list_response = handlers.list_content_files_handler(
        content_dir, ["mcaddon", "mcpack"]
    )
    if list_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{list_response['message']}")
        return

    addon_files = list_response["files"]
    show_addon_selection_menu(server_name, addon_files, base_dir)


def show_addon_selection_menu(server_name, addon_files, base_dir):
    """Displays the addon selection menu and processes the selected addon."""

    if not server_name:
        raise InvalidServerNameError("show_addon_selection_menu: server_name is empty.")
    if not addon_files:
        raise MissingArgumentError(
            "show_addon_selection_menu: addon_files array is empty."
        )

    addon_names = [os.path.basename(file) for file in addon_files]

    print(f"{_INFO_PREFIX}Available addons to install:{Style.RESET_ALL}")
    for i, addon_name in enumerate(addon_names):
        print(f"{i + 1}. {addon_name}")
    print(f"{len(addon_names) + 1}. Cancel")  # Add cancel option

    while True:
        try:
            choice = int(
                input(
                    f"{Fore.CYAN}Select an addon to install (1-{len(addon_names) + 1}):{Style.RESET_ALL} "
                ).strip()
            )
            if 1 <= choice <= len(addon_names):
                selected_addon = addon_files[choice - 1]  # Use passed in files
                break  # Valid choice
            elif choice == len(addon_names) + 1:
                print(f"{_INFO_PREFIX}Addon installation canceled.")
                return  # User canceled
            else:
                print(f"{_WARN_PREFIX}Invalid selection. Please choose a valid option.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    # Use the *handler* to install the addon
    install_response = handlers.install_addon_handler(
        server_name, selected_addon, base_dir
    )  # Always stop/start
    if install_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{install_response['message']}")
    else:
        print(f"{_OK_PREFIX}Addon installed successfully.")


def scan_player_data(base_dir=None, config_dir=None):
    """Scans server_output.txt files for player data and saves it to players.json."""

    response = handlers.scan_player_data_handler(base_dir, config_dir)

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    elif response["players_found"]:
        print(f"{_OK_PREFIX}Player data scanned and saved successfully.")
    else:
        print(f"{_OK_PREFIX}No player data found.")


def task_scheduler(server_name, base_dir=None):
    """Displays the task scheduler menu and handles user interaction."""
    base_dir = get_base_dir(base_dir)

    if not server_name:
        raise InvalidServerNameError("task_scheduler: server_name is empty.")

    if platform.system() == "Linux":
        _cron_scheduler(server_name, base_dir)
    elif platform.system() == "Windows":
        _windows_scheduler(server_name, base_dir, config_dir=None)
    else:
        print(f"{_ERROR_PREFIX}Unsupported operating system for task scheduling.")
        raise OSError("Unsupported operating system for task scheduling")


def _cron_scheduler(server_name, base_dir):
    """Displays the cron scheduler menu and handles user interaction."""
    if not server_name:
        raise InvalidServerNameError("cron_scheduler: server_name is empty.")

    while True:
        os.system("cls" if platform.system() == "Windows" else "clear")
        print(f"{Fore.MAGENTA}Bedrock Server Manager - Task Scheduler{Style.RESET_ALL}")
        print(
            f"{Fore.CYAN}Current scheduled task for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
        )

        # Get cron jobs using the handler
        cron_jobs_response = handlers.get_server_cron_jobs_handler(server_name)
        if cron_jobs_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{cron_jobs_response['message']}")
            time.sleep(2)
            continue

        cron_jobs = cron_jobs_response["cron_jobs"]

        # Display cron jobs using the handler to format the table
        if display_cron_job_table(cron_jobs) != 0:
            print(f"{_ERROR_PREFIX}Failed to display cron jobs.")
            time.sleep(2)
            continue

        print(f"{Fore.MAGENTA}What would you like to do?{Style.RESET_ALL}")
        print("1) Add Job")
        print("2) Modify Job")
        print("3) Delete Job")
        print("4) Back")

        choice = input(f"{Fore.CYAN}Enter the number (1-4):{Style.RESET_ALL} ").strip()

        if choice == "1":
            add_cron_job(server_name, base_dir)
        elif choice == "2":
            modify_cron_job(server_name, base_dir)
        elif choice == "3":
            delete_cron_job(server_name, base_dir)
        elif choice == "4":
            return  # Exit the menu
        else:
            print(f"{_WARN_PREFIX}Invalid choice. Please try again.")


def display_cron_job_table(cron_jobs):
    """Displays a table of cron jobs.  Returns 0 on success, non-zero on failure."""
    # Use the handler to get formatted table data
    table_response = handlers.get_cron_jobs_table_handler(cron_jobs)

    if table_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{table_response['message']}")
        return 1  # Indicate failure

    table_data = table_response["table_data"]

    if not table_data:
        print(f"{_INFO_PREFIX}No cron jobs to display.")
        return 0

    print("-------------------------------------------------------")
    print(f"{'CRON JOBS':<15} {'SCHEDULE':<20}  {'COMMAND':<10}")
    print("-------------------------------------------------------")

    for job in table_data:
        print(
            f"{Fore.GREEN}{job['minute']} {job['hour']} {job['day_of_month']} {job['month']} {job['day_of_week']}{Style.RESET_ALL}".ljust(
                15
            )
            + f"{Fore.CYAN}{job['schedule_time']:<25}{Style.RESET_ALL} {Fore.YELLOW}{job['command']}{Style.RESET_ALL}"
        )

    print("-------------------------------------------------------")
    return 0


def add_cron_job(server_name, base_dir):
    """Adds a new cron job."""
    if not server_name:
        raise InvalidServerNameError("add_cron_job: server_name is empty.")

    if platform.system() != "Linux":
        print(f"{_ERROR_PREFIX}Cron jobs are only supported on Linux.")
        return

    print(
        f"{Fore.CYAN}Choose the command for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
    )
    print("1) Update Server")
    print("2) Backup Server")
    print("3) Start Server")
    print("4) Stop Server")
    print("5) Restart Server")
    print("6) Scan Players")

    while True:
        try:
            choice = int(
                input(f"{Fore.CYAN}Enter the number (1-6):{Style.RESET_ALL} ").strip()
            )
            if 1 <= choice <= 6:
                break
            else:
                print(f"{_WARN_PREFIX}Invalid choice, please try again.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    if choice == 1:
        command = f"{settings.EXPATH} update-server --server {server_name}"
    elif choice == 2:
        command = f"{settings.EXPATH} backup-all --server {server_name}"
    elif choice == 3:
        command = f"{settings.EXPATH} start-server --server {server_name}"
    elif choice == 4:
        command = f"{settings.EXPATH} stop-server --server {server_name}"
    elif choice == 5:
        command = f"{settings.EXPATH} restart-server --server {server_name}"
    elif choice == 6:
        command = f"{settings.EXPATH} scan-players"

    # Get cron timing details
    while True:
        month = input(f"{Fore.CYAN}Month (1-12 or *):{Style.RESET_ALL} ").strip()
        month_response = handlers.validate_cron_input_handler(month, 1, 12)
        if month_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{month_response['message']}")
            continue

        day = input(f"{Fore.CYAN}Day of Month (1-31 or *):{Style.RESET_ALL} ").strip()
        day_response = handlers.validate_cron_input_handler(day, 1, 31)
        if day_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{day_response['message']}")
            continue

        hour = input(f"{Fore.CYAN}Hour (0-23 or *):{Style.RESET_ALL} ").strip()
        hour_response = handlers.validate_cron_input_handler(hour, 0, 23)
        if hour_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{hour_response['message']}")
            continue

        minute = input(f"{Fore.CYAN}Minute (0-59 or *):{Style.RESET_ALL} ").strip()
        minute_response = handlers.validate_cron_input_handler(minute, 0, 59)
        if minute_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{minute_response['message']}")
            continue

        weekday = input(
            f"{Fore.CYAN}Day of Week (0-7, 0 or 7 for Sunday or *):{Style.RESET_ALL} "
        ).strip()
        weekday_response = handlers.validate_cron_input_handler(weekday, 0, 7)
        if weekday_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{weekday_response['message']}")
            continue

        break  # All inputs are valid

    # Get readable schedule time
    schedule_response = handlers.convert_to_readable_schedule_handler(
        month, day, hour, minute, weekday
    )
    if schedule_response["status"] == "error":
        schedule_time = "ERROR CONVERTING"
        print(
            f"{_ERROR_PREFIX}Error converting schedule: {schedule_response['message']}"
        )
    else:
        schedule_time = schedule_response["schedule_time"]

    display_command = command.replace(os.path.join(settings.EXPATH), "").strip()
    display_command = display_command.split("--", 1)[0].strip()
    print(
        f"{_INFO_PREFIX}Your cron job will run with the following schedule:{Style.RESET_ALL}"
    )
    print("-------------------------------------------------------")
    print(f"{'CRON JOB':<15} {'SCHEDULE':<20}  {'COMMAND':<10}")
    print("-------------------------------------------------------")
    print(
        f"{Fore.GREEN}{minute} {hour} {day} {month} {weekday}{Style.RESET_ALL}".ljust(
            15
        )
        + f"{Fore.CYAN}{schedule_time:<25}{Style.RESET_ALL} {Fore.YELLOW}{display_command}{Style.RESET_ALL}"
    )
    print("-------------------------------------------------------")

    while True:
        confirm = (
            input(f"{Fore.CYAN}Do you want to add this job? (y/n): ").lower().strip()
        )
        if confirm in ("yes", "y"):
            new_cron_job = f"{minute} {hour} {day} {month} {weekday} {command}"
            # Call the handler to add the cron job
            add_response = handlers.add_cron_job_handler(new_cron_job)
            if add_response["status"] == "error":
                print(f"{_ERROR_PREFIX}{add_response['message']}")
            else:
                print(f"{_OK_PREFIX}Cron job added successfully!")
            return
        elif confirm in ("no", "n", ""):
            print(f"{_INFO_PREFIX}Cron job not added.")
            return
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")


def modify_cron_job(server_name, base_dir):
    """Modifies an existing cron job."""

    if not server_name:
        raise InvalidServerNameError("modify_cron_job: server_name is empty.")

    print(
        f"{_INFO_PREFIX}Current scheduled cron jobs for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
    )
    # Get cron jobs (use handler)
    cron_jobs_response = handlers.get_server_cron_jobs_handler(server_name)
    if cron_jobs_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{cron_jobs_response['message']}")
        return

    cron_jobs = cron_jobs_response["cron_jobs"]
    if not cron_jobs:
        print(f"{_INFO_PREFIX}No scheduled cron jobs found to modify.")
        return

    for i, line in enumerate(cron_jobs):
        print(f"{i + 1}. {line}")

    while True:
        try:
            job_number = int(
                input(
                    f"{Fore.CYAN}Enter the number of the job you want to modify:{Style.RESET_ALL} "
                ).strip()
            )
            if 1 <= job_number <= len(cron_jobs):
                job_to_modify = cron_jobs[job_number - 1]
                break
            else:
                print(f"{_WARN_PREFIX}Invalid selection. Please choose a valid number.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    # Extract the command part
    job_command = " ".join(job_to_modify.split()[5:])

    print(
        f"{_INFO_PREFIX}Modify the timing details for this cron job:{Style.RESET_ALL}"
    )
    # Get cron timing details (UI)
    while True:
        month = input(f"{Fore.CYAN}Month (1-12 or *):{Style.RESET_ALL} ").strip()
        month_response = handlers.validate_cron_input_handler(month, 1, 12)
        if month_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{month_response['message']}")
            continue

        day = input(f"{Fore.CYAN}Day of Month (1-31 or *):{Style.RESET_ALL} ").strip()
        day_response = handlers.validate_cron_input_handler(day, 1, 31)
        if day_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{day_response['message']}")
            continue

        hour = input(f"{Fore.CYAN}Hour (0-23 or *):{Style.RESET_ALL} ").strip()
        hour_response = handlers.validate_cron_input_handler(hour, 0, 23)
        if hour_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{hour_response['message']}")
            continue

        minute = input(f"{Fore.CYAN}Minute (0-59 or *):{Style.RESET_ALL} ").strip()
        minute_response = handlers.validate_cron_input_handler(minute, 0, 59)
        if minute_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{minute_response['message']}")
            continue

        weekday = input(
            f"{Fore.CYAN}Day of Week (0-7, 0 or 7 for Sunday or *):{Style.RESET_ALL} "
        ).strip()
        weekday_response = handlers.validate_cron_input_handler(weekday, 0, 7)
        if weekday_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{weekday_response['message']}")
            continue

        break  # All inputs are valid

    # Get readable schedule time
    schedule_response = handlers.convert_to_readable_schedule_handler(
        month, day, hour, minute, weekday
    )
    if schedule_response["status"] == "error":
        schedule_time = "ERROR CONVERTING"
        print(
            f"{_ERROR_PREFIX}Error converting schedule: {schedule_response['message']}"
        )
    else:
        schedule_time = schedule_response["schedule_time"]

    # Format command (UI-specific formatting)
    display_command = job_command.replace(os.path.join(settings.EXPATH), "").strip()
    display_command = display_command.split("--", 1)[0].strip()
    print(
        f"{_INFO_PREFIX}Your modified cron job will run with the following schedule:{Style.RESET_ALL}"
    )
    print("-------------------------------------------------------")
    print(f"{'CRON JOB':<15} {'SCHEDULE':<20}  {'COMMAND':<10}")
    print("-------------------------------------------------------")
    print(
        f"{Fore.GREEN}{minute} {hour} {day} {month} {weekday}{Style.RESET_ALL}".ljust(
            15
        )
        + f"{Fore.CYAN}{schedule_time:<25}{Style.RESET_ALL} {Fore.YELLOW}{display_command}{Style.RESET_ALL}"
    )
    print("-------------------------------------------------------")

    while True:
        confirm = (
            input(f"{Fore.CYAN}Do you want to modify this job? (y/n): ").lower().strip()
        )
        if confirm in ("yes", "y"):
            new_cron_job = f"{minute} {hour} {day} {month} {weekday} {job_command}"
            # Call the handler to modify the cron job
            modify_response = handlers.modify_cron_job_handler(
                job_to_modify, new_cron_job
            )
            if modify_response["status"] == "error":
                print(f"{_ERROR_PREFIX}{modify_response['message']}")
            else:
                print(f"{_OK_PREFIX}Cron job modified successfully!")
            return

        elif confirm in ("no", "n", ""):
            print(f"{_INFO_PREFIX}Cron job not modified.")
            return
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")


def delete_cron_job(server_name, base_dir):
    """Deletes a cron job for the specified server."""

    if not server_name:
        raise InvalidServerNameError("delete_cron_job: server_name is empty.")

    print(
        f"{_INFO_PREFIX}Current scheduled cron jobs for {Fore.YELLOW}{server_name}:{Style.RESET_ALL}"
    )

    # Get cron jobs (use handler)
    cron_jobs_response = handlers.get_server_cron_jobs_handler(server_name)
    if cron_jobs_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{cron_jobs_response['message']}")
        return

    cron_jobs = cron_jobs_response["cron_jobs"]
    if not cron_jobs:
        print(f"{_INFO_PREFIX}No scheduled cron jobs found to delete.")
        return

    for i, line in enumerate(cron_jobs):
        print(f"{i + 1}. {line}")
    print(f"{len(cron_jobs) + 1}. Cancel")

    while True:
        try:
            job_number = int(
                input(
                    f"{Fore.CYAN}Enter the number of the job you want to delete (1-{len(cron_jobs) + 1}):{Style.RESET_ALL} "
                ).strip()
            )
            if 1 <= job_number <= len(cron_jobs):
                job_to_delete = cron_jobs[job_number - 1]
                break
            elif job_number == len(cron_jobs) + 1:
                print(f"{_INFO_PREFIX}Cron job deletion canceled.")
                return  # User canceled
            else:
                print(f"{_WARN_PREFIX}Invalid selection. No matching cron job found.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    while True:
        confirm_delete = (
            input(
                f"{Fore.RED}Are you sure you want to delete this cron job? (y/n):{Style.RESET_ALL} "
            )
            .lower()
            .strip()
        )
        if confirm_delete in ("y", "yes"):
            # Call the handler to delete the cron job
            delete_response = handlers.delete_cron_job_handler(job_to_delete)
            if delete_response["status"] == "error":
                print(f"{_ERROR_PREFIX}{delete_response['message']}")
            else:
                print(f"{_OK_PREFIX}Cron job deleted successfully!")
            return
        elif confirm_delete in ("n", "no", ""):
            print(f"{_INFO_PREFIX}Cron job not deleted.")
            return  # User canceled
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")


def _windows_scheduler(server_name, base_dir, config_dir=None):
    """Displays the Windows Task Scheduler menu and handles user interaction."""
    if config_dir is None:
        config_dir = settings._config_dir

    if not server_name:
        raise InvalidServerNameError("windows_task_scheduler: server_name is empty.")

    if platform.system() != "Windows":
        raise OSError("This function is for Windows only.")

    while True:
        os.system("cls")
        print(f"{Fore.MAGENTA}Bedrock Server Manager - Task Scheduler{Style.RESET_ALL}")
        print(
            f"{Fore.CYAN}Current scheduled tasks for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
        )

        # Get task names using the handler
        task_names_response = handlers.get_server_task_names_handler(
            server_name, config_dir
        )
        if task_names_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{task_names_response['message']}")
            time.sleep(2)
            continue  # go back to main menu

        task_names = task_names_response["task_names"]

        if not task_names:
            print(f"{_INFO_PREFIX}No scheduled tasks found.")
        else:
            display_windows_task_table(task_names)

        print(f"{Fore.CYAN}What would you like to do?{Style.RESET_ALL}")
        print("1) Add Task")
        print("2) Modify Task")
        print("3) Delete Task")
        print("4) Back")

        choice = input(f"{Fore.CYAN}Enter the number (1-4):{Style.RESET_ALL} ").strip()
        try:
            if choice == "1":
                add_windows_task(server_name, base_dir, config_dir)
            elif choice == "2":
                modify_windows_task(server_name, base_dir, config_dir)
            elif choice == "3":
                delete_windows_task(server_name, base_dir, config_dir)
            elif choice == "4":
                return  # Exit the menu
            else:
                print(f"{_WARN_PREFIX}Invalid choice. Please try again.")
        except Exception as e:
            print(f"{_ERROR_PREFIX}An error has occurred: {e}")


def display_windows_task_table(task_names):
    """Displays a table of Windows scheduled tasks."""

    # Use the handler to get detailed task information
    task_info_response = handlers.get_windows_task_info_handler(
        [task[0] for task in task_names]
    )
    if task_info_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{task_info_response['message']}")
        return

    task_info = task_info_response["task_info"]

    print(
        "-------------------------------------------------------------------------------"
    )
    print(f"{'TASK NAME':<30} {'COMMAND':<25} {'SCHEDULE':<20}")
    print(
        "-------------------------------------------------------------------------------"
    )

    for task in task_info:
        print(
            f"{Fore.GREEN}{task['task_name']:<30}{Fore.YELLOW}{task['command']:<25}{Fore.CYAN}{task['schedule']:<20}{Style.RESET_ALL}"
        )
    print(
        "-------------------------------------------------------------------------------"
    )


def add_windows_task(server_name, base_dir, config_dir=None):
    """Adds a new Windows scheduled task."""

    if not server_name:
        raise InvalidServerNameError("add_windows_task: server_name is empty.")

    if platform.system() != "Windows":
        print(f"{_ERROR_PREFIX}This function is for Windows only.")
        return

    if config_dir is None:
        config_dir = settings._config_dir

    print(
        f"{Fore.CYAN}Adding task for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
    )

    print(f"{Fore.MAGENTA}Choose the command:{Style.RESET_ALL}")
    print("1) Update Server")
    print("2) Backup Server")
    print("3) Start Server")
    print("4) Stop Server")
    print("5) Restart Server")
    print("6) Scan Players")
    print("7) Cancel")

    while True:
        try:
            choice = int(
                input(f"{Fore.CYAN}Enter the number (1-7):{Style.RESET_ALL} ").strip()
            )
            if 1 <= choice <= 6:
                break
            elif choice == 7:
                print(f"{_INFO_PREFIX}Add task cancelled.")
                return  # User cancelled
            else:
                print(f"{_WARN_PREFIX}Invalid choice, please try again.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    if choice == 1:
        command = "update-server"
        command_args = f"--server {server_name}"
    elif choice == 2:
        command = "backup-all"
        command_args = f"--server {server_name}"
    elif choice == 3:
        command = "start-server"
        command_args = f"--server {server_name}"
    elif choice == 4:
        command = "stop-server"
        command_args = f"--server {server_name}"
    elif choice == 5:
        command = "restart-server"
        command_args = f"--server {server_name}"
    elif choice == 6:
        command = "scan-players"
        command_args = ""

    task_name = (
        f"bedrock_{server_name}_{command.replace('-', '_')}"  # Create a task name
    )

    # Get trigger information from the user
    triggers = get_trigger_details()

    # Call the handler to create the task
    create_response = handlers.create_windows_task_handler(
        server_name, command, command_args, task_name, config_dir, triggers, base_dir
    )
    if create_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{create_response['message']}")
    else:
        print(f"{_OK_PREFIX}Task '{task_name}' added successfully!")


def get_trigger_details():
    """Gets trigger information from the user interactively."""
    triggers = []
    while True:
        print(f"{Fore.MAGENTA}Choose a trigger type:{Style.RESET_ALL}")
        print("1) One Time")
        print("2) Daily")
        print("3) Weekly")
        print("4) Monthly")
        print("5) Add another trigger")
        print("6) Done adding triggers")

        trigger_choice = input(
            f"{Fore.CYAN}Enter the number (1-6):{Style.RESET_ALL} "
        ).strip()

        if trigger_choice == "1":  # One Time
            trigger_data = {"type": "TimeTrigger"}
            while True:
                start_boundary = input(
                    f"{Fore.CYAN}Enter start date and time (YYYY-MM-DD HH:MM):{Style.RESET_ALL} "
                ).strip()
                try:
                    start_boundary_dt = datetime.strptime(
                        start_boundary, "%Y-%m-%d %H:%M"
                    )
                    trigger_data["start"] = start_boundary_dt.isoformat()
                    break  # Valid input
                except ValueError:
                    print(
                        f"{_ERROR_PREFIX}Incorrect format, please use YYYY-MM-DD HH:MM"
                    )
            triggers.append(trigger_data)

        elif trigger_choice == "2":  # Daily
            trigger_data = {"type": "Daily"}
            while True:
                start_boundary = input(
                    f"{Fore.CYAN}Enter start date and time (YYYY-MM-DD HH:MM){Style.RESET_ALL}: "
                ).strip()
                try:
                    start_boundary_dt = datetime.strptime(
                        start_boundary, "%Y-%m-%d %H:%M"
                    )
                    trigger_data["start"] = start_boundary_dt.isoformat()
                    break  # Valid input
                except ValueError:
                    print(
                        f"{_ERROR_PREFIX}Incorrect format, please use YYYY-MM-DD HH:MM"
                    )
            while True:
                try:
                    days_interval = int(
                        input(
                            f"{Fore.CYAN}Enter interval in days:{Style.RESET_ALL} "
                        ).strip()
                    )
                    if days_interval >= 1:
                        trigger_data["interval"] = days_interval
                        break  # Valid input
                    else:
                        print(f"{_WARN_PREFIX}Enter a value greater than or equal to 1")
                except ValueError:
                    print(f"{_ERROR_PREFIX}Must be a valid integer.")
            triggers.append(trigger_data)

        elif trigger_choice == "3":  # Weekly
            trigger_data = {"type": "Weekly"}
            while True:
                start_boundary = input(
                    f"{Fore.CYAN}Enter start date and time (YYYY-MM-DD HH:MM):{Style.RESET_ALL} "
                ).strip()
                try:
                    start_boundary_dt = datetime.strptime(
                        start_boundary, "%Y-%m-%d %H:%M"
                    )
                    trigger_data["start"] = start_boundary_dt.isoformat()
                    break  # Valid input
                except ValueError:
                    print(
                        f"{_ERROR_PREFIX}Incorrect format, please use YYYY-MM-DD HH:MM"
                    )

            while True:  # Loop for days of the week input
                days_of_week_str = input(
                    f"{Fore.CYAN}Enter days of the week (comma-separated: Sun,Mon,Tue,Wed,Thu,Fri,Sat OR 1-7):{Style.RESET_ALL} "
                ).strip()
                days_of_week = [day.strip() for day in days_of_week_str.split(",")]
                valid_days = []
                for day_input in days_of_week:
                    day_response = handlers.get_day_element_name_handler(day_input)
                    if day_response["status"] == "success":  # use core function
                        valid_days.append(day_input)
                    else:
                        print(
                            f"{_WARN_PREFIX}Invalid day of week: {day_input}. Skipping."
                        )
                if valid_days:
                    trigger_data["days"] = valid_days
                    break  # Exit if at least one valid day is entered
                else:
                    print(f"{_ERROR_PREFIX}You must enter at least one valid day.")

            while True:
                try:
                    weeks_interval = int(
                        input(
                            f"{Fore.CYAN}Enter interval in weeks:{Style.RESET_ALL} "
                        ).strip()
                    )
                    if weeks_interval >= 1:
                        trigger_data["interval"] = weeks_interval
                        break  # Valid input
                    else:
                        print(f"{_WARN_PREFIX}Enter a value greater than or equal to 1")
                except ValueError:
                    print(f"{_ERROR_PREFIX}Must be a valid integer.")
            triggers.append(trigger_data)

        elif trigger_choice == "4":  # Monthly
            trigger_data = {"type": "Monthly"}
            while True:
                start_boundary = input(
                    f"{Fore.CYAN}Enter start date and time (YYYY-MM-DD HH:MM):{Style.RESET_ALL} "
                ).strip()
                try:
                    start_boundary_dt = datetime.strptime(
                        start_boundary, "%Y-%m-%d %H:%M"
                    )
                    trigger_data["start"] = start_boundary_dt.isoformat()
                    break  # Valid input
                except ValueError:
                    print(
                        f"{_ERROR_PREFIX}Incorrect date format, please use YYYY-MM-DD HH:MM"
                    )

            while True:  # Loop for days input
                days_of_month_str = input(
                    f"{Fore.CYAN}Enter days of the month (comma-separated, 1-31):{Style.RESET_ALL} "
                ).strip()
                days_of_month = [day.strip() for day in days_of_month_str.split(",")]
                valid_days = []
                for day in days_of_month:
                    try:
                        day_int = int(day)
                        if 1 <= day_int <= 31:
                            valid_days.append(day_int)
                        else:
                            print(
                                f"{_WARN_PREFIX}Invalid day of month: {day}. Skipping."
                            )
                    except ValueError:
                        print(f"{_WARN_PREFIX}Invalid day of month: {day}. Skipping.")
                if valid_days:
                    trigger_data["days"] = valid_days
                    break
                else:
                    print(f"{_ERROR_PREFIX}You must enter at least one valid day")

            while True:  # Loop for months input
                months_str = input(
                    f"{Fore.CYAN}Enter months (comma-separated: Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec OR 1-12):{Style.RESET_ALL} "
                ).strip()
                months = [month.strip() for month in months_str.split(",")]
                valid_months = []
                for month_input in months:
                    month_response = handlers.get_month_element_name_handler(
                        month_input
                    )
                    if month_response["status"] == "success":  # Use core function
                        valid_months.append(month_input)
                    else:
                        print(f"{_WARN_PREFIX}Invalid month: {month_input}. Skipping.")
                if valid_months:
                    trigger_data["months"] = valid_months
                    break  # Exit loop
                else:
                    print(f"{_ERROR_PREFIX}You must enter at least one valid month.")
            triggers.append(trigger_data)

        elif trigger_choice == "5":
            continue  # Add another trigger
        elif trigger_choice == "6":
            break  # Done adding triggers
        else:
            print(f"{_WARN_PREFIX}Invalid choice.")

    return triggers


def modify_windows_task(server_name, base_dir, config_dir=None):
    """Modifies an existing Windows scheduled task (UI)."""
    if not server_name:
        raise InvalidServerNameError("modify_windows_task: server_name is empty.")

    if platform.system() != "Windows":
        print(f"{_ERROR_PREFIX}This function is for Windows only.")
        return
    # Get task names using handler
    task_names_response = handlers.get_server_task_names_handler(
        server_name, config_dir
    )
    if task_names_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{task_names_response['message']}")
        return

    task_names = task_names_response["task_names"]
    if not task_names:
        print(f"{_INFO_PREFIX}No scheduled tasks found to modify.")
        return

    print(
        f"{Fore.CYAN}Select the task to modify for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
    )
    for i, (task_name, file_path) in enumerate(task_names):  # Unpack tuple
        print(f"{i + 1}. {task_name}")
    print(f"{len(task_names) + 1}. Cancel")

    while True:
        try:
            task_index = (
                int(
                    input(
                        f"{Fore.CYAN}Enter the number of the task to modify (1-{len(task_names) + 1}):{Style.RESET_ALL} "
                    ).strip()
                )
                - 1
            )
            if 0 <= task_index < len(task_names):
                selected_task_name, selected_file_path = task_names[
                    task_index
                ]  # Unpack here
                break
            elif task_index == len(task_names):
                print(f"{_INFO_PREFIX}Modify task cancelled.")
                return  # Cancelled
            else:
                print(f"{_WARN_PREFIX}Invalid selection.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    # --- Get existing command and arguments ---
    try:
        with open(selected_file_path, "r") as file:
            xml_content = file.read()

        # Use a regular expression to find the <Command> and <Arguments> tags and extract their content
        command_match = re.search(r"<Command>(.*?)</Command>", xml_content)
        arguments_match = re.search(r"<Arguments>(.*?)</Arguments>", xml_content)

        # Extract the command and arguments, remove extra spaces
        command = command_match.group(1).strip() if command_match else ""
        command_args = arguments_match.group(1).strip() if arguments_match else ""

    except (FileNotFoundError, ET.ParseError) as e:
        print(f"{_ERROR_PREFIX}Error loading task XML: {e}")
        return
    # --- Get NEW trigger information from the user ---
    triggers = get_trigger_details()

    # Create a task name
    new_task_name = f"bedrock_{server_name}_{command.replace('-', '_')}"

    # Call the handler to modify the task
    modify_response = handlers.modify_windows_task_handler(
        selected_task_name,
        server_name,
        command,
        command_args,
        new_task_name,
        config_dir,
        triggers,
        base_dir,
    )

    if modify_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{modify_response['message']}")
    else:
        print(
            f"{_OK_PREFIX}Task '{selected_task_name}' modified successfully! (New name: {new_task_name})"
        )


def delete_windows_task(server_name, base_dir, config_dir=None):
    """Deletes a Windows scheduled task (UI)."""

    if not server_name:
        raise InvalidServerNameError("delete_windows_task: server_name is empty.")

    if platform.system() != "Windows":
        print(f"{_ERROR_PREFIX}This function is for Windows only.")
        return
    # Get task names using handler
    task_names_response = handlers.get_server_task_names_handler(
        server_name, config_dir
    )

    if task_names_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{task_names_response['message']}")
        return
    task_names = task_names_response["task_names"]
    if not task_names:
        print(f"{_INFO_PREFIX}No scheduled tasks found to delete.")
        return

    print(
        f"{Fore.CYAN}Select the task to delete for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
    )
    for i, (task_name, file_path) in enumerate(task_names):  # Unpack the tuple
        print(f"{i + 1}. {task_name}")
    print(f"{len(task_names) + 1}. Cancel")

    while True:
        try:
            task_index = (
                int(
                    input(
                        f"{Fore.CYAN}Enter the number of the task to delete (1-{len(task_names) + 1}):{Style.RESET_ALL} "
                    ).strip()
                )
                - 1
            )
            if 0 <= task_index < len(task_names):
                selected_task_name, selected_file_path = task_names[
                    task_index
                ]  # Unpack tuple
                break
            elif task_index == len(task_names):
                print(f"{_INFO_PREFIX}Task deletion cancelled.")
                return  # Cancelled
            else:
                print(f"{_WARN_PREFIX}Invalid selection.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    # Confirm deletion
    while True:
        confirm_delete = (
            input(
                f"{Fore.RED}Are you sure you want to delete the task {Fore.YELLOW}{selected_task_name}{Fore.RED}? (y/n):{Style.RESET_ALL} "
            )
            .lower()
            .strip()
        )
        if confirm_delete in ("y", "yes"):
            # Call the handler to delete the task
            delete_response = handlers.delete_windows_task_handler(
                selected_task_name, selected_file_path
            )
            if delete_response["status"] == "error":
                print(f"{_ERROR_PREFIX}{delete_response['message']}")
            else:
                print(f"{_OK_PREFIX}Task '{selected_task_name}' deleted successfully!")
            return
        elif confirm_delete in ("n", "no", ""):
            print(f"{_INFO_PREFIX}Task deletion canceled.")
            return  # User canceled
        else:
            print(f"{_WARN_PREFIX}Invalid input.  Please enter 'y' or 'n'.")


def main_menu(base_dir, config_dir):
    """Displays the main menu and handles user interaction."""
    os.system("cls" if platform.system() == "Windows" else "clear")
    while True:
        print(f"\n{Fore.MAGENTA}Bedrock Server Manager{Style.RESET_ALL}")
        list_servers_status(base_dir, config_dir)

        print("1) Install New Server")
        print("2) Manage Existing Server")
        print("3) Install Content")
        print(
            "4) Send Command to Server"
            + (" (Linux Only)" if platform.system() != "Linux" else "")
        )
        print("5) Advanced")
        print("6) Exit")

        choice = input(f"{Fore.CYAN}Select an option [1-6]{Style.RESET_ALL}: ").strip()
        try:
            if choice == "1":
                install_new_server(base_dir, config_dir)
            elif choice == "2":
                manage_server(base_dir, config_dir)
            elif choice == "3":
                install_content(base_dir, config_dir)
            elif choice == "4":
                server_name = get_server_name(base_dir)
                if server_name:
                    command = input(f"{_INFO_PREFIX}Enter command: ").strip()
                    if not command:
                        logger.warning("No command entered.  Ignoring.")
                        continue  # Go back to the menu loop
                    try:
                        bedrock_server = server_base.BedrockServer(server_name)
                        bedrock_server.send_command(command)
                    except Exception as e:
                        logger.exception(f"Error sending command: {e}")
                else:
                    logger.info("Send command canceled.")
            elif choice == "5":
                advanced_menu(base_dir, config_dir)
            elif choice == "6":
                os.system("cls" if platform.system() == "Windows" else "clear")
                sys.exit(0)
            else:
                logger.warning("Invalid choice")
        except Exception as e:
            logger.exception(f"An error has occurred: {e}")


def manage_server(base_dir, config_dir=None):
    """Displays the manage server menu and handles user interaction."""
    if config_dir is None:
        config_dir = settings._config_dir

    os.system("cls" if platform.system() == "Windows" else "clear")
    while True:
        print(
            f"\n{Fore.MAGENTA}Bedrock Server Manager - Manage Server{Style.RESET_ALL}"
        )
        list_servers_status(base_dir, config_dir)
        print("1) Update Server")
        print("2) Start Server")
        print("3) Stop Server")
        print("4) Restart Server")
        print("5) Backup/Restore")
        print("6) Delete Server")
        print("7) Back")

        choice = input(f"{Fore.CYAN}Select an option [1-7]:{Style.RESET_ALL} ").strip()
        try:
            if choice == "1":
                server_name = get_server_name(base_dir)
                if server_name:
                    update_server(server_name, base_dir)
                else:
                    logger.info("Update canceled.")
            elif choice == "2":
                server_name = get_server_name(base_dir)
                if server_name:
                    handle_start_server(server_name, base_dir)
                else:
                    logger.info("Start canceled.")
            elif choice == "3":
                server_name = get_server_name(base_dir)
                if server_name:
                    handle_stop_server(server_name, base_dir)
                else:
                    logger.info("Stop canceled.")
            elif choice == "4":
                server_name = get_server_name(base_dir)
                if server_name:
                    restart_server(server_name, base_dir)
                else:
                    logger.info("Restart canceled.")
            elif choice == "5":
                backup_restore(base_dir, config_dir)
            elif choice == "6":
                server_name = get_server_name(base_dir)
                if server_name:
                    delete_server(server_name, base_dir, config_dir)
                else:
                    logger.info("Delete canceled.")
            elif choice == "7":
                return  # Go back to the main menu
            else:
                logger.warning("Invalid choice")
        except Exception as e:
            logger.exception(f"An error has occurred: {e}")


def install_content(base_dir, config_dir=None):
    """Displays the install content menu and handles user interaction."""
    if config_dir is None:
        config_dir = settings._config_dir
    os.system("cls" if platform.system() == "Windows" else "clear")
    while True:
        print(
            f"\n{Fore.MAGENTA}Bedrock Server Manager - Install Content{Style.RESET_ALL}"
        )
        list_servers_status(base_dir, config_dir)
        print("1) Import World")
        print("2) Import Addon")
        print("3) Back")

        choice = input(f"{Fore.CYAN}Select an option [1-3]:{Style.RESET_ALL} ").strip()
        try:
            if choice == "1":
                server_name = get_server_name(base_dir)
                if server_name:
                    install_worlds(server_name, base_dir)
                else:
                    logger.info("Import canceled.")
            elif choice == "2":
                server_name = get_server_name(base_dir)
                if server_name:
                    install_addons(server_name, base_dir)
                else:
                    logger.info("Import canceled.")
            elif choice == "3":
                return  # Go back to the main menu
            else:
                logger.warning("Invalid choice")
        except Exception as e:
            logger.exception(f"An error has occurred: {e}")


def advanced_menu(base_dir, config_dir=None):
    """Displays the advanced menu and handles user interaction."""
    if config_dir is None:
        config_dir = settings._config_dir

    os.system("cls" if platform.system() == "Windows" else "clear")
    while True:
        print(
            f"\n{Fore.MAGENTA}Bedrock Server Manager - Advanced Menu{Style.RESET_ALL}"
        )
        list_servers_status(base_dir, config_dir)
        print("1) Configure Server Properties")
        print("2) Configure Allowlist")
        print("3) Configure Permissions")
        print(
            "4) Attach to Server Console"
            + (" (Linux Only)" if platform.system() != "Linux" else "")
        )
        print("5) Schedule Server Task")
        print("6) View Server Resource Usage")
        print("7) Reconfigure Auto-Update")
        print("8) Back")

        choice = input(f"{Fore.CYAN}Select an option [1-8]:{Style.RESET_ALL} ").strip()

        try:
            if choice == "1":
                server_name = get_server_name(base_dir)
                if server_name:
                    configure_server_properties(server_name, base_dir)
                else:
                    logger.info("Configuration canceled.")
            elif choice == "2":
                server_name = get_server_name(base_dir)
                if server_name:
                    handle_configure_allowlist(server_name, base_dir)
                else:
                    logger.info("Configuration canceled.")
            elif choice == "3":
                server_name = get_server_name(base_dir)
                if server_name:
                    select_player_for_permission(server_name, base_dir, config_dir)
                else:
                    logger.info("Configuration canceled.")
            elif choice == "4":
                if platform.system() == "Linux":
                    server_name = get_server_name(base_dir)
                    if server_name:
                        attach_console(server_name, base_dir)
                    else:
                        logger.info("Attach canceled.")
                else:
                    logger.warning("Attach to console is only available on Linux.")

            elif choice == "5":
                server_name = get_server_name(base_dir)
                if server_name:
                    task_scheduler(server_name, base_dir)
                else:
                    logger.info("Schedule canceled.")
            elif choice == "6":
                server_name = get_server_name(base_dir)
                if server_name:
                    monitor_service_usage(server_name, base_dir)
                else:
                    logger.info("Monitoring canceled.")
            elif choice == "7":
                # Reconfigure systemd service / autoupdate
                server_name = get_server_name(base_dir)
                if server_name:
                    create_service(server_name, base_dir)  # Use config
                else:
                    logger.info("Configuration canceled.")
            elif choice == "8":
                return  # Go back to the main menu
            else:
                logger.warning("Invalid choice")
        except Exception as e:
            logger.exception(f"An error has occurred: {e}")


def backup_restore(base_dir, config_dir=None):
    """Displays the backup/restore menu and handles user interaction."""

    if config_dir is None:
        config_dir = settings._config_dir

    os.system("cls" if platform.system() == "Windows" else "clear")
    while True:
        print(
            f"\n{Fore.MAGENTA}Bedrock Server Manager - Backup/Restore{Style.RESET_ALL}"
        )
        list_servers_status(base_dir, config_dir)
        print("1) Backup Server")
        print("2) Restore Server")
        print("3) Back")

        choice = input(f"{Fore.CYAN}Select an option [1-3]:{Style.RESET_ALL} ").strip()

        try:
            if choice == "1":
                server_name = get_server_name(base_dir)
                if server_name:
                    backup_menu(server_name, base_dir)  # Let it raise exceptions
                else:
                    logger.info("Backup canceled.")
            elif choice == "2":
                server_name = get_server_name(base_dir)
                if server_name:
                    restore_menu(server_name, base_dir)  # Let it raise exceptions
                else:
                    logger.info("Restore canceled.")
            elif choice == "3":
                return  # Go back to the main menu
            else:
                logger.warning("Invalid choice")
        except Exception as e:
            logger.exception(f"An error has occurred: {e}")
