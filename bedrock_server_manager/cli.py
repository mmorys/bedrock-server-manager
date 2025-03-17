# bedrock-server-manager/bedrock_server_manager/cli.py
import os
import sys
import getpass
import subprocess
import time
import platform
import glob
import json
from datetime import datetime
import re
from colorama import Fore, Style
import logging
import xml.etree.ElementTree as ET
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.core.system import linux as system_linux
from bedrock_server_manager.core.system import windows as system_windows
from bedrock_server_manager.utils.general import (
    get_timestamp,
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
    InstallUpdateError,
    ServerStartError,
    ServerStopError,
    CommandNotFoundError,
    ServerNotRunningError,
    FileOperationError,
    BackupWorldError,
    InvalidInputError,
    DirectoryError,
    ScheduleError,
    TaskError,
    InvalidCronJobError,
)
from bedrock_server_manager.core.server import (
    server as server_base,
    world,
    backup,
    addon,
)
from bedrock_server_manager.core.download import downloader
from bedrock_server_manager.core.player import player

logger = logging.getLogger("bedrock_server_manager")


def get_server_name(base_dir=None):
    """Prompts the user for a server name and validates its existence.

    Args:
        base_dir (str): The base directory for servers.

    Returns:
        str: The validated server name, or None if the user cancels.
    """
    base_dir = get_base_dir(base_dir)

    while True:
        server_name = input(
            f"{Fore.MAGENTA}Enter server name (or type 'exit' to cancel): {Style.RESET_ALL}"
        ).strip()

        if server_name.lower() == "exit":
            print(f"{_OK_PREFIX}Operation canceled.")
            return None  # User canceled
        if not server_name:
            print(f"{_WARN_PREFIX}Server name cannot be empty.")
            continue

        try:
            if server_base.validate_server(server_name, base_dir):
                print(f"{_OK_PREFIX}Server {server_name} found.")
                return server_name
        except Exception as e:
            print(f"{_ERROR_PREFIX}{e}")
            #  allowing user to try again
            continue

        print(
            f"{_WARN_PREFIX}Please enter a valid server name or type 'exit' to cancel."
        )


def list_servers_status(base_dir=None, config_dir=None):
    """Lists the status and version of all servers."""

    base_dir = get_base_dir(base_dir)
    if config_dir is None:
        config_dir = settings._config_dir

    print(f"{Fore.YELLOW}Servers Status:{Style.RESET_ALL}")
    print("---------------------------------------------------")
    print(f"{'SERVER NAME':<20} {'STATUS':<20} {'VERSION':<10}")
    print("---------------------------------------------------")

    if not os.path.isdir(base_dir):
        print(f"{_ERROR_PREFIX}Error: {base_dir} does not exist or is not a directory.")
        return

    found_servers = False
    for server_path in glob.glob(os.path.join(base_dir, "*")):  # Find directories
        if os.path.isdir(server_path):
            server_name = os.path.basename(server_path)

            status = Fore.RED + "UNKNOWN" + Style.RESET_ALL
            version = Fore.RED + "UNKNOWN" + Style.RESET_ALL

            status = server_base.get_server_status_from_config(server_name, config_dir)

            if status == "RUNNING":
                status_str = f"{Fore.GREEN}{status}{Style.RESET_ALL}"
            elif status in ("STARTING", "RESTARTING", "STOPPING", "INSTALLED"):
                status_str = f"{Fore.YELLOW}{status}{Style.RESET_ALL}"
            elif status == "STOPPED":
                status_str = f"{Fore.RED}{status}{Style.RESET_ALL}"
            else:
                status_str = f"{Fore.RED}UNKNOWN{Style.RESET_ALL}"

            version = server_base.get_installed_version(server_name, config_dir)
            version_str = (
                f"{Fore.YELLOW}{version}{Style.RESET_ALL}"
                if version != "UNKNOWN"
                else f"{Fore.RED}UNKNOWN{Style.RESET_ALL}"
            )

            print(
                f"{Fore.CYAN}{server_name:<20}{Style.RESET_ALL} {status_str:<20}  {version_str:<10}"
            )
            found_servers = True

    if not found_servers:
        print("No servers found.")

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

    server_dir = os.path.join(base_dir, server_name)

    existing_players = server_base.configure_allowlist(
        server_dir
    )  # exceptions are handled in configure_allowlist
    if not existing_players:
        logger.info("No existing allowlist.json found.  A new one will be created.")
    new_players_data = []
    logger.info("Configuring allowlist.json")

    # Ask for new players
    while True:
        player_name = input(
            f"{Fore.CYAN}Enter a player's name to add to the allowlist (or type 'done' to finish): {Style.RESET_ALL}"
        ).strip()
        if player_name.lower() == "done":
            break
        if not player_name:
            logger.warning("Player name cannot be empty. Please try again.")
            continue

        # Check for duplicates (only among newly added, not existing)
        if any(player["name"] == player_name for player in new_players_data):
            logger.warning(f"Player '{player_name}' was already entered. Skipping.")
            continue
        if any(player["name"] == player_name for player in existing_players):
            logger.warning(
                f"Player '{player_name}' is already in the allowlist. Skipping."
            )
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
                logger.warning("Invalid input. Please answer 'yes' or 'no'.")

        new_players_data.append(
            {"ignoresPlayerLimit": ignore_limit, "name": player_name}
        )

    if new_players_data:
        server_base.add_players_to_allowlist(
            server_dir, new_players_data
        )  # exceptions are handled
    else:
        logger.info(
            "No new players were added. Existing allowlist.json was not modified."
        )


def handle_add_players(players, config_dir):
    """Handles the user interaction and logic for adding players to the players.json file.

    This function parses a string of player data (in the format "playername:playerid, player2:player2id")
    into a list of dictionaries, and then saves this list to the players.json file.
    It interacts with the player.parse_player_argument and player.save_players_to_json functions.

    Args:
        players (list): A list of strings, where each string represents a player in the format "playername:playerid".
                        This is the player data parsed from the command-line arguments.
        config_dir (str): The directory where the players.json file is located.

    Raises:
        ValueError: If the player data string is incorrectly formatted.
        Exception: If any other unexpected error occurs during parsing or saving.
    """
    logger.info("Adding players...")
    try:
        player_string = ",".join(players)  # Join the list into a comma-separated string
        player_list = player.parse_player_argument(player_string)
        player.save_players_to_json(player_list, config_dir)
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {type(e).__name__}: {e}")

    logger.info("Players added.")


def select_player_for_permission(server_name, base_dir=None, config_dir=None):
    """Selects a player and permission level, then calls configure_permissions.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.
        config_dir (str, optional): Config directory. Defaults to main config.

    Returns:
        None

    Raises:
        MissingArgumentError: If server_name is empty.
        InvalidServerNameError: If server_name is invalid
        FileOperationError: if players.json is missing or invalid
        # Other exceptions may be raised by server.configure_permissions
    """

    if config_dir is None:
        config_dir = settings._config_dir

    base_dir = get_base_dir(base_dir)

    players_file = os.path.join(config_dir, "players.json")

    if not server_name:
        raise InvalidServerNameError(
            "select_player_for_permission: server_name is empty."
        )

    server_dir = os.path.join(base_dir, server_name)

    if not os.path.exists(players_file):
        raise FileOperationError(f"No players.json file found at: {players_file}")

    try:
        with open(players_file, "r") as f:
            players_data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise FileOperationError(f"Failed to read or parse players.json: {e}") from e

    if not players_data.get("players"):
        logger.warning("No players found in players.json!")
        return  # Return (not an error, just no players)

    # Create lists for player names and XUIDs
    player_names = [player["name"] for player in players_data["players"]]
    xuids = [player["xuid"] for player in players_data["players"]]

    # Display player selection menu
    logger.info("Select a player to add to permissions.json:")
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
                logger.info("Operation canceled.")
                return  # User canceled
            else:
                logger.warning("Invalid choice. Please select a valid number.")
        except ValueError:
            logger.warning("Invalid input. Please enter a number.")

    # Prompt for permission level
    permission = select_option(
        "Select a permission level:", "member", "operator", "member", "visitor"
    )

    # Call the function to add/update the player in permissions.json
    server_base.configure_permissions(
        server_dir, selected_xuid, selected_name, permission
    )  # Let it raise


def configure_server_properties(server_name, base_dir=None):
    """Configures common server properties interactively.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory where servers are stored.
    Raises:
        MissingArgumentError: If server_name is empty.
        InvalidServerNameError: if the server name is invalid
        FileOperationError: If server.properties cannot be read/written.
        # Other exceptions may be raised by server.modify_server_properties
    """
    base_dir = get_base_dir(base_dir)

    logger.info(f"Configuring server properties for {server_name}")

    if not server_name:
        raise InvalidServerNameError(
            "configure_server_properties: server_name is empty."
        )

    server_dir = os.path.join(base_dir, server_name)

    server_properties = os.path.join(server_dir, "server.properties")
    if not os.path.exists(server_properties):
        raise FileOperationError(f"server.properties not found in: {server_properties}")

    # Default values
    DEFAULT_PORT = "19132"
    DEFAULT_IPV6_PORT = "19133"

    # Read existing properties
    current_properties = {}
    try:
        with open(server_properties, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line:
                    key, value = line.split("=", 1)
                    current_properties[key] = value
    except OSError as e:
        raise FileOperationError(f"Failed to read server.properties {e}") from e

    # Prompts with validation and defaults
    input_server_name = input(
        f"{Fore.CYAN}Enter server name [Default: {Fore.YELLOW}{current_properties.get('server-name', '')}{Fore.CYAN}]:{Style.RESET_ALL} "
    ).strip()
    input_server_name = input_server_name or current_properties.get("server-name", "")
    while ";" in input_server_name:
        logger.error("Server name cannot contain semicolons.")
        input_server_name = input(
            f"{Fore.CYAN}Enter server name [Default: {Fore.YELLOW}{current_properties.get('server-name', '')}{Fore.CYAN}]:{Style.RESET_ALL} "
        ).strip()
        input_server_name = input_server_name or current_properties.get(
            "server-name", ""
        )

    input_level_name = input(
        f"{Fore.CYAN}Enter level name [Default: {Fore.YELLOW}{current_properties.get('level-name', '')}{Fore.CYAN}]:{Style.RESET_ALL} "
    ).strip()
    input_level_name = input_level_name or current_properties.get("level-name", "")
    input_level_name = input_level_name.replace(" ", "_")
    while not re.match(r"^[a-zA-Z0-9_-]+$", input_level_name):
        logger.error(
            "Invalid level-name. Only alphanumeric characters, hyphens, and underscores are allowed (spaces converted to underscores)."
        )
        input_level_name = input(
            f"{Fore.CYAN}Enter level name [Default: {Fore.YELLOW}{current_properties.get('level-name', '')}{Fore.CYAN}]:{Style.RESET_ALL} "
        ).strip()
        input_level_name = input_level_name or current_properties.get("level-name", "")
        input_level_name = input_level_name.replace(" ", "_")

    input_gamemode = select_option(
        "Select gamemode:",
        current_properties.get("gamemode", "survival"),
        "survival",
        "creative",
        "adventure",
    )
    input_difficulty = select_option(
        "Select difficulty:",
        current_properties.get("difficulty", "easy"),
        "peaceful",
        "easy",
        "normal",
        "hard",
    )
    input_allow_cheats = select_option(
        "Allow cheats:",
        current_properties.get("allow-cheats", "false"),
        "true",
        "false",
    )

    while True:
        input_port = input(
            f"{Fore.CYAN}Enter IPV4 Port [Default: {Fore.YELLOW}{current_properties.get('server-port', DEFAULT_PORT)}{Fore.CYAN}]:{Style.RESET_ALL} "
        ).strip()
        input_port = input_port or current_properties.get("server-port", DEFAULT_PORT)
        if re.match(r"^[0-9]+$", input_port) and 1024 <= int(input_port) <= 65535:
            break
        logger.error(
            "Invalid port number. Please enter a number between 1024 and 65535."
        )

    while True:
        input_port_v6 = input(
            f"{Fore.CYAN}Enter IPV6 Port [Default: {Fore.YELLOW}{current_properties.get('server-portv6', DEFAULT_IPV6_PORT)}{Fore.CYAN}]:{Style.RESET_ALL} "
        ).strip()
        input_port_v6 = input_port_v6 or current_properties.get(
            "server-portv6", DEFAULT_IPV6_PORT
        )
        if re.match(r"^[0-9]+$", input_port_v6) and 1024 <= int(input_port_v6) <= 65535:
            break
        logger.error(
            "Invalid IPV6 port number. Please enter a number between 1024 and 65535."
        )

    input_lan_visibility = select_option(
        "Enable LAN visibility:",
        current_properties.get("enable-lan-visibility", "true"),
        "true",
        "false",
    )
    input_allow_list = select_option(
        "Enable allow list:",
        current_properties.get("allow-list", "false"),
        "true",
        "false",
    )

    while True:
        input_max_players = input(
            f"{Fore.CYAN}Enter max players [Default: {Fore.YELLOW}{current_properties.get('max-players', '10')}{Fore.CYAN}]:{Style.RESET_ALL} "
        ).strip()
        input_max_players = input_max_players or current_properties.get(
            "max-players", "10"
        )
        if re.match(r"^[0-9]+$", input_max_players):
            break
        logger.error("Invalid number for max players.")

    input_permission_level = select_option(
        "Select default permission level:",
        current_properties.get("default-player-permission-level", "member"),
        "visitor",
        "member",
        "operator",
    )

    while True:
        input_render_distance = input(
            f"{Fore.CYAN}Default render distance [Default: {Fore.YELLOW}{current_properties.get('view-distance', '10')}{Fore.CYAN}]:{Style.RESET_ALL} "
        ).strip()
        input_render_distance = input_render_distance or current_properties.get(
            "view-distance", "10"
        )
        if (
            re.match(r"^[0-9]+$", input_render_distance)
            and int(input_render_distance) >= 5
        ):
            break
        logger.error(
            "Invalid render distance. Please enter a number greater than or equal to 5."
        )

    while True:
        input_tick_distance = input(
            f"{Fore.CYAN}Default tick distance [Default: {Fore.YELLOW}{current_properties.get('tick-distance', '4')}{Fore.CYAN}]:{Style.RESET_ALL} "
        ).strip()
        input_tick_distance = input_tick_distance or current_properties.get(
            "tick-distance", "4"
        )
        if (
            re.match(r"^[0-9]+$", input_tick_distance)
            and 4 <= int(input_tick_distance) <= 12
        ):
            break
        logger.error("Invalid tick distance. Please enter a number between 4 and 12.")

    input_level_seed = input(
        f"{Fore.CYAN}Enter level seed:{Style.RESET_ALL} "
    ).strip()  # No default or validation

    input_online_mode = select_option(
        "Enable online mode:",
        current_properties.get("online-mode", "true"),
        "true",
        "false",
    )
    input_texturepack_required = select_option(
        "Require texture pack:",
        current_properties.get("texturepack-required", "false"),
        "true",
        "false",
    )

    # Update properties, accumulating any errors.
    server_base.modify_server_properties(
        server_properties, "server-name", input_server_name
    )
    server_base.modify_server_properties(
        server_properties, "level-name", input_level_name
    )
    server_base.modify_server_properties(server_properties, "gamemode", input_gamemode)
    server_base.modify_server_properties(
        server_properties, "difficulty", input_difficulty
    )
    server_base.modify_server_properties(
        server_properties, "allow-cheats", input_allow_cheats
    )
    server_base.modify_server_properties(server_properties, "server-port", input_port)
    server_base.modify_server_properties(
        server_properties, "server-portv6", input_port_v6
    )
    server_base.modify_server_properties(
        server_properties, "enable-lan-visibility", input_lan_visibility
    )
    server_base.modify_server_properties(
        server_properties, "allow-list", input_allow_list
    )
    server_base.modify_server_properties(
        server_properties, "max-players", input_max_players
    )
    server_base.modify_server_properties(
        server_properties, "default-player-permission-level", input_permission_level
    )
    server_base.modify_server_properties(
        server_properties, "view-distance", input_render_distance
    )
    server_base.modify_server_properties(
        server_properties, "tick-distance", input_tick_distance
    )
    server_base.modify_server_properties(
        server_properties, "level-seed", input_level_seed
    )
    server_base.modify_server_properties(
        server_properties, "online-mode", input_online_mode
    )
    server_base.modify_server_properties(
        server_properties, "texturepack-required", input_texturepack_required
    )
    logger.info("Server properties configured")


def handle_download_bedrock_server(
    server_name, base_dir=None, target_version="LATEST", in_update=False
):
    """Handles downloading and installing the Bedrock server, including UI.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.
        target_version (str): "LATEST", "PREVIEW", or a specific version.
        in_update (bool): True if this is an update, False for new install.

    Raises:
        MissingArgumentError: If server_name is empty.
        InvalidServerNameError: if the server name is not valid
        # Other exceptions may be raised by download_bedrock_server, install_server
    """
    base_dir = get_base_dir(base_dir)

    server_dir = os.path.join(base_dir, server_name)

    if not server_name:
        raise InvalidServerNameError(
            "handle_download_bedrock_server: server_name is empty."
        )

    logger.info("Starting Bedrock server download process...")
    current_version, zip_file, download_dir = downloader.download_bedrock_server(
        server_dir, target_version
    )
    server_base.install_server(
        server_name, base_dir, current_version, zip_file, server_dir, in_update
    )

    logger.info(f"Installed Bedrock server version: {current_version}")
    logger.info("Bedrock server download process finished")


def install_new_server(base_dir=None, config_dir=None):
    """Installs a new server.

    Args:
        base_dir (str): The base directory for servers.
        config_dir (str, optional): Config directory.

    Raises:
        InvalidServerNameError: If server name provided contains invalid characters
        InstallUpdateError: If there are errors deleting/creating server files or installing
    """
    base_dir = get_base_dir(base_dir)

    logger.info("Installing new server...")

    while True:
        server_name = input(
            f"{Fore.MAGENTA}Enter server folder name:{Style.RESET_ALL} "
        ).strip()
        if re.match(r"^[a-zA-Z0-9_-]+$", server_name):
            break
        else:
            logger.warning(
                "Invalid server folder name. Only alphanumeric characters, hyphens, and underscores are allowed."
            )

    server_dir = os.path.join(base_dir, server_name)
    if os.path.exists(server_dir):
        logger.warning(f"Folder {server_name} already exists")
        while True:
            continue_response = (
                input(
                    f"{Fore.RED}Folder {Fore.YELLOW}{server_name}{Fore.RED} already exists, continue? (y/n):{Style.RESET_ALL} "
                )
                .lower()
                .strip()
            )
            if continue_response in ("yes", "y"):
                try:
                    delete_server(server_name, base_dir, config_dir)
                except Exception as e:
                    raise InstallUpdateError(
                        f"Failed to delete existing server {server_name}: {e}"
                    ) from e
                break
            elif continue_response in ("no", "n", ""):
                logger.info("Exiting")
                return  # User cancelled
            else:
                logger.warning("Invalid input. Please answer 'yes' or 'no'.")

    target_version = input(
        f"{Fore.CYAN}Enter server version (e.g., {Fore.YELLOW}LATEST{Fore.CYAN} or {Fore.YELLOW}PREVIEW{Fore.CYAN}):{Style.RESET_ALL} "
    ).strip()

    if not target_version:
        target_version = "LATEST"

    # Write server name and target version to config
    try:
        server_base.manage_server_config(
            server_name, "server_name", "write", server_name, config_dir
        )
        server_base.manage_server_config(
            server_name, "target_version", "write", target_version, config_dir
        )
    except Exception as e:
        raise InstallUpdateError(f"Failed to write server config: {e}") from e

    # Download and install the server
    try:
        handle_download_bedrock_server(
            server_name, base_dir, target_version=target_version, in_update=False
        )
    except Exception as e:
        raise InstallUpdateError(f"Failed to install server: {e}") from e

    # Write status after install
    try:
        server_base.manage_server_config(
            server_name, "status", "write", "INSTALLED", config_dir
        )
    except Exception as e:
        raise InstallUpdateError(f"Failed to write server config: {e}") from e

    # Configure server properties
    try:
        configure_server_properties(server_name, base_dir)
    except Exception as e:
        logger.warning(f"Failed to configure server properties: {e}")
        # This isn't *critical* enough to raise InstallUpdateError

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
            logger.info("Skipping allow-list configuration.")
            break
        else:
            logger.warning("Invalid input. Please answer 'yes' or 'no'.")

    # Permissions configuration
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
                logger.warning(f"Failed to configure permissions: {e}")
            break
        elif permissions_response in ("no", "n", ""):
            logger.info("Skipping permissions configuration.")
            break
        else:
            logger.warning("Invalid input. Please answer 'yes' or 'no'.")

    # Create a service
    try:
        create_service(server_name, base_dir)
    except Exception as e:
        logger.warning(f"Failed to create service: {e}")

    # Start the server
    while True:
        start_choice = (
            input(
                f"{Fore.CYAN}Do you want to start the server {Fore.YELLOW}{server_name}{Fore.CYAN} now? (y/n):{Style.RESET_ALL} "
            )
            .lower()
            .strip()
        )
        if start_choice in ("yes", "y"):
            try:
                handle_start_server(server_name, base_dir)
            except Exception as e:
                logger.error(f"Failed to start server: {e}")
            break
        elif start_choice in ("no", "n", ""):
            logger.info(f"Server {server_name} not started.")
            break
        else:
            logger.warning("Invalid input. Please answer 'yes' or 'no'.")


def update_server(server_name, base_dir=None):
    """Updates an existing server.

    Args:
        server_name (str): The name of the server to update.
        base_dir (str): The base directory for servers.

    Raises:
        InvalidServerNameError: If server_name is empty
        InstallUpdateError: If any part of the update process fails.
        # Other exceptions may be raised by the called functions.
    """
    base_dir = get_base_dir(base_dir)

    logger.info(f"Starting update process for server: {server_name}")

    if not server_name:
        raise InvalidServerNameError("update_server: server_name is empty.")

    # Check if the server is running, if so display in game message
    if system_base.is_server_running(server_name, base_dir):
        try:
            bedrock_server = server_base.BedrockServer(server_name)
            bedrock_server.send_command("say Checking for server updates..")
        except Exception as e:
            logger.warning(f"Failed to send message to server: {e}")

    installed_version = server_base.get_installed_version(server_name)
    if installed_version == "UNKNOWN":
        logger.warning("Failed to get the installed version. Attempting update anyway.")

    target_version = server_base.manage_server_config(
        server_name, "target_version", "read"
    )
    if target_version is None:
        logger.warning("Failed to read target_version from config. Using 'LATEST'.")
        target_version = "LATEST"

    if server_base.no_update_needed(server_name, installed_version, target_version):
        logger.info(f"No update needed for server {server_name}.")
        return  # No update required

    # Download and install the update
    try:
        handle_download_bedrock_server(
            server_name, base_dir, target_version=target_version, in_update=True
        )
        logger.info(f"Server {server_name} updated successfully.")
    except Exception as e:
        raise InstallUpdateError(f"Failed to update server {server_name}: {e}") from e


def handle_enable_user_lingering():
    """Handles enabling user lingering, with user interaction."""

    if platform.system() != "Linux":
        return  # Not applicable, just return

    username = getpass.getuser()
    # Check if lingering is already enabled
    try:
        result = subprocess.run(
            ["loginctl", "show-user", username],
            capture_output=True,
            text=True,
            check=False,
        )
        if "Linger=yes" in result.stdout:
            logger.debug(f"Lingering is already enabled for {username}")
            return  # Already enabled
    except FileNotFoundError:
        logger.warning(
            "loginctl command not found.  Lingering cannot be checked/enabled."
        )
        return  # command not found

    while True:
        response = (
            input(
                f"{Fore.CYAN}Do you want to enable lingering? (y/n):{Style.RESET_ALL} "
            )
            .lower()
            .strip()
        )
        if response in ("yes", "y"):
            try:
                system_linux.enable_user_lingering()
                break  # Success
            except Exception as e:
                logger.error(f"Failed to enable lingering: {e}")
                # We *don't* re-raise the exception here.  This is a user-interaction
                # function; we want to give the user a chance to try again, or to
                # choose not to enable lingering.  We log the error, but continue.
        elif response in ("no", "n", ""):
            logger.info(
                "Lingering not enabled. User services might not start automatically."
            )
            break  # Exit loop.
        else:
            logger.warning("Invalid input. Please answer 'yes' or 'no'.")


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
                logger.warning("Invalid input. Please answer 'yes' or 'no'.")

        while True:
            response = (
                input(
                    f"{Fore.CYAN}Do you want to enable autostart on boot for {Fore.YELLOW}{server_name}{Fore.CYAN}? (y/n):{Style.RESET_ALL} "
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
                logger.warning("Invalid input. Please answer 'yes' or 'no'.")
        try:
            system_linux._create_systemd_service(server_name, base_dir, autoupdate)
        except Exception as e:
            raise Exception(f"Failed to create systemd service: {e}") from e

        if autostart:
            enable_service(server_name)
        else:
            disable_service(server_name)

        handle_enable_user_lingering()  # Call the handler

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
                logger.warning("Invalid input. Please answer 'yes' or 'no'.")
        try:
            server_base.manage_server_config(
                server_name, "autoupdate", "write", autoupdate_value
            )
            logger.info(
                f"Successfully updated autoupdate in config.json for server: {server_name}"
            )
        except Exception as e:
            raise Exception(f"Failed to update autoupdate config: {e}") from e

    else:
        logger.error("Unsupported operating system for service creation.")
        raise OSError("Unsupported operating system for service creation.")


def enable_service(server_name):
    """Enables a systemd service (Linux) or handles the Windows case."""
    if platform.system() == "Linux":
        if not server_name:
            raise InvalidServerNameError(
                "_enable_systemd_service: server_name is empty."
            )
        try:
            system_linux._enable_systemd_service(server_name)
        except Exception as e:
            raise e
    elif platform.system() == "Windows":
        logger.info(
            "Windows doesn't currently support all script features. You may want to look into Windows Subsystem Linux (wsl)."
        )
        # Not an error on Windows
    else:
        logger.error("Unsupported operating system for service enabling.")
        raise OSError("Unsupported OS")


def disable_service(server_name):
    """Disables a systemd service (Linux) or handles the Windows case."""
    if platform.system() == "Linux":
        if not server_name:
            raise InvalidServerNameError(
                "_disable_systemd_service: server_name is empty."
            )
        try:
            system_linux._disable_systemd_service(server_name)
        except Exception as e:
            raise e
    elif platform.system() == "Windows":
        logger.info(
            "Windows doesn't currently support all script features. You may want to look into Windows Subsystem Linux (wsl)."
        )
        # Not an error on Windows
    else:
        logger.error("Unsupported operating system for service disabling.")
        raise OSError("Unsupported OS")


def handle_start_server(server_name, base_dir=None):
    """Starts the Bedrock server (UI).

    Raises:
        InvalidServerNameError: If server_name is empty.
        # Other exceptions may be raised by is_server_running and start
    """
    base_dir = get_base_dir(base_dir)
    if not server_name:
        raise InvalidServerNameError("start_server: server_name is empty.")

    if system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is already running.")
        return  # Already running

    logger.info(f"Starting server {server_name}...")
    try:
        bedrock_server = server_base.BedrockServer(
            server_name, os.path.join(base_dir, server_name)
        )
        bedrock_server.start()  # Call start method
        logger.info("Server started successfully.")
    except Exception as e:
        logger.exception(f"Failed to start server: {e}")


def handle_systemd_start(server_name, base_dir=None):
    """Starts the Bedrock server (UI).

    Raises:
        InvalidServerNameError: If server_name is empty.
        # Other exceptions may be raised by is_server_running and start
    """
    base_dir = get_base_dir(base_dir)
    if not server_name:
        raise InvalidServerNameError("start_server: server_name is empty.")

    if system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is already running.")
        return  # Already running

    logger.info(f"Starting server {server_name}...")
    try:
        system_linux._systemd_start_server(
            server_name, os.path.join(base_dir, server_name)
        )
        logger.info("Server started successfully.")
    except Exception as e:
        logger.exception(f"Failed to start server: {e}")


def handle_stop_server(server_name, base_dir=None):
    """Stops the Bedrock server (UI).

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.

    Raises:
        InvalidServerNameError: If server_name is empty.
        # Other exceptions may be raised by is_server_running and BedrockServer.stop
    """
    base_dir = get_base_dir(base_dir)

    if not server_name:
        raise InvalidServerNameError("stop_server: server_name is empty.")

    if not system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is not running.")
        return  # Already stopped

    logger.info(f"Stopping server {server_name}...")
    try:
        bedrock_server = server_base.BedrockServer(
            server_name, os.path.join(base_dir, server_name)
        )
        bedrock_server.stop()  # Stop the server
        logger.info("Server stopped successfully.")
    except Exception as e:
        logger.exception(f"Failed to stop server: {e}")


def handle_systemd_stop(server_name, base_dir=None):
    """Starts the Bedrock server (UI).

    Raises:
        InvalidServerNameError: If server_name is empty.
        # Other exceptions may be raised by is_server_running and start
    """
    base_dir = get_base_dir(base_dir)
    if not server_name:
        raise InvalidServerNameError("start_server: server_name is empty.")

    if not system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is not running.")
        return  # Already stopped

    logger.info(f"Starting server {server_name}...")
    try:
        system_linux._systemd_stop_server(
            server_name, os.path.join(base_dir, server_name)
        )
        logger.info("Server stoped successfully.")
    except Exception as e:
        logger.exception(f"Failed to stop server: {e}")


def restart_server(server_name, base_dir=None):
    """Restarts the Bedrock server.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.
    Raises:
        InvalidServerNameError: if the server name is empty
        # Other exceptions will be raised by handle_start_server and handle_stop_server
    """
    base_dir = get_base_dir(base_dir)

    if not server_name:
        raise InvalidServerNameError("restart_server: server_name is empty.")

    if not system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Server {server_name} is not running. Starting it instead.")
        handle_start_server(
            server_name, base_dir
        )  # Let handle_start_server raise exceptions
        return

    logger.info(f"Restarting server {server_name}...")

    # Send restart warning
    try:
        bedrock_server = server_base.BedrockServer(server_name)
        bedrock_server.send_command("say Restarting server in 10 seconds..")
        time.sleep(10)
    except Exception as e:
        logger.warning(f"Failed to send message to server: {e}")

    # Stop and then start the server.
    try:
        handle_stop_server(server_name, base_dir)  # Use core functions.
    except Exception as e:
        raise ServerStopError(f"Failed to stop server during restart: {e}") from e

    # Small delay before restarting
    time.sleep(2)

    try:
        handle_start_server(server_name, base_dir)  # Use core functions
    except Exception as e:
        raise ServerStartError(f"Failed to start server during restart: {e}") from e


def _monitor(server_name, base_dir):
    """Monitor for Bedrock server (UI portion)."""

    if not server_name:
        raise InvalidServerNameError("_monitor: server_name is empty.")

    logger.info(f"Monitoring resource usage for server: {server_name}")
    try:
        while True:
            process_info = system_base._get_bedrock_process_info(server_name, base_dir)
            if not process_info:
                logger.warning("Server process information not found. Exiting monitor.")
                return

            # Clear screen and display output
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

            time.sleep(1)  # Update interval

    except KeyboardInterrupt:
        logger.info("Monitoring stopped.")


def monitor_service_usage(server_name, base_dir=None):
    """Monitors the CPU and memory usage of the Bedrock server."""
    base_dir = get_base_dir(base_dir)
    _monitor(server_name, base_dir)  # Call monitor


def attach_console(server_name, base_dir=None):
    """Attaches to the server console."""
    base_dir = get_base_dir(base_dir)

    if not server_name:
        raise InvalidServerNameError("attach_console: server_name is empty.")

    if platform.system() == "Linux":
        if not system_base.is_server_running(server_name, base_dir):
            raise ServerNotRunningError(f"Server {server_name} is not running.")
        logger.info(f"Attaching to server {server_name} console...")
        try:
            subprocess.run(["screen", "-r", f"bedrock-{server_name}"], check=True)
        except subprocess.CalledProcessError:
            # This likely means the screen session doesn't exist, even though
            # is_server_running returned True.  This could happen in a race
            # condition, or if the server crashed immediately after the check.
            raise ServerNotRunningError(
                f"Failed to attach to screen session for server: {server_name}"
            ) from None
        except FileNotFoundError:
            raise CommandNotFoundError(
                "screen", message="screen command not found. Is screen installed?"
            ) from None

    elif platform.system() == "Windows":
        logger.info(
            "Windows doesn't currently support attaching to the console. You may want to look into Windows Subsystem for Linux (WSL)."
        )
    else:
        logger.error("attach_console not supported on this platform")
        raise OSError("Unsupported operating system")


def delete_server(server_name, base_dir=None, config_dir=None):
    """Deletes a Bedrock server (UI interaction)."""
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
        logger.info("Server deletion canceled.")
        return

    # Stop the server if it's running
    if system_base.is_server_running(server_name, base_dir):
        logger.warning(f"Stopping server {server_name} before deletion...")
        try:
            handle_stop_server(server_name, base_dir)  # Stop the server
        except Exception as e:
            logger.exception(f"Error stopping server before deletion: {e}")
    try:
        server_base.delete_server_data(
            server_name, base_dir, config_dir
        )  # core function
    except Exception as e:
        raise e


def handle_extract_world(server_name, selected_file, base_dir=None, from_addon=False):
    """Handles extracting a world, including stopping/starting the server.

    Args:
        server_name (str): The name of the server.
        selected_file (str): Path to the .mcworld file.
        base_dir (str): The base directory for servers.
        from_addon (bool): True if called from addon installation, False otherwise.
    Raises:
        InvalidServerNameError: If the server name is empty
        FileOperationError: If world_name could not be found
        # Other exceptions may be raised by extract_world, stop_server_if_running or start_server_if_was_running
    """
    base_dir = get_base_dir(base_dir)

    if not server_name:
        raise InvalidServerNameError("extract_world: server_name is empty.")

    server_dir = os.path.join(base_dir, server_name)
    try:
        world_name = server_base.get_world_name(server_name, base_dir)
        if world_name is None or not world_name:  # Check for None or empty string
            raise FileOperationError("Failed to get world name from server.properties.")
    except Exception as e:
        raise FileOperationError(f"Error getting world name: {e}") from e

    extract_dir = os.path.join(server_dir, "worlds", world_name)

    was_running = False
    if not from_addon:
        was_running = server_base.stop_server_if_running(server_name, base_dir)

    logger.info(f"Installing world {os.path.basename(selected_file)}...")

    try:
        world.extract_world(selected_file, extract_dir)  # Let it raise
    except Exception as e:
        raise e

    # Start the server after world install if it was running and not from an addon
    if not from_addon:
        server_base.start_server_if_was_running(server_name, base_dir, was_running)

    logger.info(f"Installed world to {extract_dir}")


def handle_export_world(server_name, base_dir=None):
    """Handles exporting the world, including getting the world name and backup path.

    Args:
        server_name (str): The name of the server.
        base_dir (str): Server base directory.

    Raises:
        MissingArgumentError: If server_name is empty.
        InvalidServerNameError: If server name is not valid.
        FileOperationError: If world name could not be retrived.
        DirectoryError: If world directory doesn't exist
        # Other exceptions may be raised by world.export_world
    """
    base_dir = get_base_dir(base_dir)

    if not server_name:
        raise InvalidServerNameError("export_world: server_name is empty.")

    try:
        world_folder = server_base.get_world_name(server_name, base_dir)
        if world_folder is None or not world_folder:  # check for empty
            raise FileOperationError("Could not find level-name in server.properties")
    except Exception as e:
        raise FileOperationError(f"Failed to get world name: {e}") from e
    world_path = os.path.join(base_dir, server_name, "worlds", world_folder)
    if not os.path.isdir(world_path):
        logger.warning(
            f"World directory '{world_folder}' does not exist. Skipping world backup."
        )
        return

    timestamp = get_timestamp()
    backup_dir = settings.get("BACKUP_DIR")
    backup_file = os.path.join(backup_dir, f"{world_folder}_backup_{timestamp}.mcworld")

    logger.info(f"Backing up world folder '{world_folder}'...")
    world.export_world(world_path, backup_file)  # use core function


def handle_prune_old_backups(
    server_name, file_name=None, backup_keep=None, base_dir=None
):
    """Prunes old backups, keeping only the most recent ones. (UI and setup)

    Args:
        server_name (str): The name of the server.
        file_name (str, optional): Specific file name to prune (for config files).
        backup_keep (int, optional): How many backups to keep, defaults to config value
        base_dir (str, optional): base directory

    Raises:
        InvalidServerNameError: if server_name is empty
        ValueError: if backup_keep is not an int
        # Other exceptions may be raised by backup.prune_old_backups, get_world_name
    """
    base_dir = get_base_dir(base_dir)
    backup_dir = os.path.join(settings.get("BACKUP_DIR"), server_name)

    if not server_name:
        raise InvalidServerNameError("prune_old_backups: server_name is empty.")

    if backup_keep is None:
        backup_keep = settings.get("BACKUP_KEEP")  # Get from config
        try:
            backup_keep = int(backup_keep)
        except ValueError:
            raise ValueError(
                "Invalid value for BACKUP_KEEP in config file, must be an integer"
            ) from None

    logger.info("Pruning old backups...")

    # Prune world backups (*.mcworld)
    try:
        level_name = server_base.get_world_name(server_name, base_dir)
    except Exception as e:
        level_name = None  # handle exception from get_world_name, prun all files
        logger.warning(
            f"Failed to get world name. Pruning world backups may be inaccurate: {e}"
        )

    if not level_name:  # Still attempt to prune with just extention
        backup.prune_old_backups(backup_dir, backup_keep, file_extension="mcworld")
    else:
        backup.prune_old_backups(
            backup_dir,
            backup_keep,
            file_prefix=f"{level_name}_backup_",
            file_extension="mcworld",
        )

    # Prune config file backups (if file_name is provided)
    if file_name:
        try:
            backup.prune_old_backups(
                backup_dir,
                backup_keep,
                file_prefix=f"{os.path.splitext(file_name)[0]}_backup_",
                file_extension=file_name.split(".")[-1],
            )
        except Exception as e:
            raise e  # Re-raise for consistent error reporting
    logger.info("Done.")


def handle_backup_server(
    server_name, backup_type, file_to_backup=None, change_status=True, base_dir=None
):
    """Backs up a server's world or a specific configuration file (UI).

    Args:
        server_name (str): The name of the server.
        backup_type (str): "world" or "config".
        file_to_backup (str, optional): The file to back up if backup_type is "config".
        change_status (bool): Whether to stop the server before backup.
        base_dir (str): The base directory for servers.

    Raises:
        InvalidServerNameError: If server_name is empty.
        MissingArgumentError: If backup_type is empty or file_to_backup is
            missing for config backups.
        InvalidInputError: if backup type is not world or config.
        # Other exceptions may be raised by called functions.
    """
    base_dir = get_base_dir(base_dir)
    server_dir = os.path.join(base_dir, server_name)

    backup_dir = os.path.join(settings.get("BACKUP_DIR"), server_name)

    if not server_name:
        raise InvalidServerNameError("backup_server: server_name is empty.")
    if not backup_type:
        raise MissingArgumentError("backup_server: backup_type is empty.")

    # Ensure the backup directory exists.
    os.makedirs(backup_dir, exist_ok=True)

    was_running = False
    if change_status:
        was_running = server_base.stop_server_if_running(server_name, base_dir)

    if backup_type == "world":
        try:
            world_name = server_base.get_world_name(server_name, base_dir)
            if world_name is None or not world_name:
                raise FileOperationError(
                    "Could not determine world name; backup may not function"
                )
            world_path = os.path.join(server_dir, "worlds", world_name)

            logger.info("Backing up world...")
            backup.backup_world(server_name, world_path, backup_dir)
        except Exception as e:
            raise BackupWorldError(f"World backup failed {e}") from e

    elif backup_type == "config":
        if not file_to_backup:
            raise MissingArgumentError(
                "backup_server: file_to_backup is empty when backup_type is config."
            )

        full_file_path = os.path.join(server_dir, file_to_backup)
        logger.info(f"Backing up config file: {file_to_backup}")
        try:
            backup.backup_config_file(full_file_path, backup_dir)
        except Exception as e:
            raise FileOperationError(f"Config file backup failed: {e}") from e
    else:
        raise InvalidInputError(f"Invalid backup type: {backup_type}")

    if change_status:
        server_base.start_server_if_was_running(server_name, base_dir, was_running)
    handle_prune_old_backups(
        server_name, file_to_backup, settings.get("BACKUP_KEEP"), base_dir
    )


def handle_backup_all(server_name, base_dir=None, change_status=True):
    """Performs backup of all files (UI).

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.
        change_status (bool): Whether to stop the server before backup.

    Raises:
        InvalidServerNameError: If server_name is empty
        # Exceptions from backup.backup_all will propagate
    """
    base_dir = get_base_dir(base_dir)
    if not server_name:
        raise InvalidServerNameError("backup_all: server_name is empty.")
    logger.info("Performing full backup...")
    backup.backup_all(server_name, base_dir)
    logger.info("All files backed up successfully.")


def backup_menu(server_name, base_dir):
    """Displays the backup menu and handles user input.

    Raises:
    InvalidServerNameError: If server_name is empty.
    # Other exceptions may be raised by handle_backup_server or handle_backup_all

    """

    if not server_name:
        raise InvalidServerNameError("backup_menu: server_name is empty.")

    while True:
        print(f"{Fore.MAGENTA}What do you want to backup:{Style.RESET_ALL}")
        print("1. Backup World")  # Using print for menu options.
        print("2. Backup Configuration File")
        print("3. Backup All")
        print("4. Cancel")

        choice = input(
            f"{Fore.CYAN}Select the type of backup:{Style.RESET_ALL} "
        ).strip()

        if choice == "1":
            try:
                handle_backup_server(
                    server_name, "world", "", True, base_dir
                )  # change status true, let it raise
            except Exception as e:
                raise e
            break  # Exit after backup
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
                logger.info("Backup operation canceled.")
                return  # User canceled
            else:
                logger.warning("Invalid selection, please try again.")
                continue
            try:
                handle_backup_server(
                    server_name, "config", file_to_backup, True, base_dir
                )  # change status to true
            except Exception as e:
                raise e
            break  # Exit menu
        elif choice == "3":
            handle_backup_all(server_name, base_dir)  # Let handle_backup_all raise
            break  # Exit menu
        elif choice == "4":
            logger.info("Backup operation canceled.")
            return  # User canceled
        else:
            logger.warning("Invalid selection, please try again.")


def handle_restore_server(
    server_name, backup_file, restore_type, change_status=True, base_dir=None
):
    """Restores a server from a backup file (UI and workflow).

    Args:
        server_name (str): The name of the server.
        backup_file (str): Path to the backup file.
        restore_type (str): "world" or "config".
        change_status (bool): Whether to stop the server before restoring and restart afterwards.
        base_dir (str): The base directory for servers.

    Raises:
        MissingArgumentError: If server_name, backup_file, or restore_type is empty.
        InvalidServerNameError: if the server name is not valid.
        InvalidInputError: If restore_type is invalid.
        FileOperationError: If backup file does not exist.
        # Other exceptions may be raised by called functions.
    """
    base_dir = get_base_dir(base_dir)

    if not server_name:
        raise InvalidServerNameError("restore_server: server_name is empty.")
    if not backup_file:
        raise MissingArgumentError("restore_server: backup_file is empty.")
    if not restore_type:
        raise MissingArgumentError("restore_server: restore_type is empty.")

    if not os.path.exists(backup_file):
        raise FileOperationError(f"Backup file '{backup_file}' not found!")

    was_running = False
    if change_status:
        was_running = server_base.stop_server_if_running(server_name, base_dir)

    if restore_type == "world":
        logger.info(f"Restoring world from {backup_file}...")
        try:
            backup.restore_server(
                server_name, backup_file, restore_type, base_dir
            )  # core function
        except Exception as e:
            raise e

    elif restore_type == "config":
        logger.info(f"Restoring config file: {os.path.basename(backup_file)}")
        try:
            backup.restore_server(
                server_name, backup_file, restore_type, base_dir
            )  # core function
        except Exception as e:
            raise e
    else:
        raise InvalidInputError(
            f"Invalid restore type in restore_server: {restore_type}"
        )

    if change_status:
        server_base.start_server_if_was_running(server_name, base_dir, was_running)


def handle_restore_all(server_name, base_dir, change_status=True):
    """Restores all newest files (world and configuration files). (UI)

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.
        change_status (bool): Whether to stop the server before restoring and restart afterwards.
    Raises:
        InvalidServerNameError: If server name is empty
        # Other exceptions may be raised by called functions
    """
    if not server_name:
        raise InvalidServerNameError("restore_all: server_name is empty.")
    backup_dir = os.path.join(settings.get("BACKUP_DIR"), server_name)

    if not os.path.isdir(backup_dir):
        logger.debug(f"No backups found for {server_name}.")
        return  # Not an error if no backups exist

    was_running = False
    if change_status:
        was_running = server_base.stop_server_if_running(server_name, base_dir)

    logger.info("Restoring all files...")
    try:
        backup.restore_all(server_name, base_dir)
        logger.info("All restore operations completed.")
    except Exception as e:
        raise e

    if change_status and was_running:
        server_base.start_server_if_was_running(server_name, base_dir, was_running)


def restore_menu(server_name, base_dir):
    """Displays the restore menu and handles user interaction.

    Raises:
        InvalidServerNameError: If server_name is empty.
        # Other exceptions may be raised by handle_restore_server or handle_restore_all
    """

    if not server_name:
        raise InvalidServerNameError("restore_menu: server_name is empty.")
    backup_dir = os.path.join(settings.get("BACKUP_DIR"), server_name)
    if not os.path.isdir(backup_dir):
        logger.warning(f"No backups found for {server_name}.")
        return  # Not an error if no backups exist

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
            # Gather world backups
            backup_files = glob.glob(os.path.join(backup_dir, "*.mcworld"))
            if not backup_files:
                logger.warning("No world backups found.")
                return  # Return to main menu

        elif choice == "2":
            restore_type = "config"
            # Gather config backups
            backup_files = glob.glob(os.path.join(backup_dir, "*_backup_*.json"))
            backup_files += glob.glob(
                os.path.join(backup_dir, "server_backup_*.properties")
            )
            if not backup_files:
                logger.warning("No configuration backups found.")
                return  # Return to main menu
        elif choice == "3":
            handle_restore_all(server_name, base_dir)  # Let it raise exceptions
            return
        elif choice == "4":
            logger.info("Restore operation canceled.")
            return  # User canceled
        else:
            logger.warning("Invalid selection. Please choose again.")
            continue  # Invalid option for restore type, go back to the menu

        # Valid option, ask for specific file.
        break  # Valid option to proceed

    # Create a numbered list of backup files
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
                )  # Let it raise
                return
            elif choice == len(backup_map) + 1:
                logger.info("Restore operation canceled.")
                return  # User canceled

            else:
                logger.warning("Invalid selection. Please choose again.")
        except ValueError:
            logger.warning("Invalid input. Please enter a number.")


def handle_install_addon(server_name, addon_file, base_dir=None):
    """Handles the installation of an addon, including stopping/starting the server.

    Args:
        server_name (str): The name of the server.
        addon_file (str): The path to the addon file.  Can be None if the user
                         is selecting from the content directory.
        base_dir (str): The base directory for servers.
    Raises:
        InvalidServerNameError: If server name is empty.
        MissingArgumentError: If add_on file is empty.
        # Other exceptions may be raised by called functions.
    """
    base_dir = get_base_dir(base_dir)

    if not server_name:
        raise InvalidServerNameError("handle_install_addon: server_name is empty.")

    if not addon_file:
        raise MissingArgumentError("Addon file cannot be None")

    logger.info(f"Installing addon {addon_file}...")

    was_running = server_base.stop_server_if_running(server_name, base_dir)

    try:
        addon.process_addon(addon_file, server_name, base_dir)
    except Exception as e:
        raise e

    server_base.start_server_if_was_running(server_name, base_dir, was_running)

    logger.info(f"Installed addon to {server_name}")


def install_worlds(server_name, base_dir=None, content_dir=None):
    """Provides a menu to select and install .mcworld files.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory where servers are stored.
        content_dir (str): The directory where the content is located.
    Raises:
        InvalidServerNameError: if server_name is empty.
        DirectoryError: If content_dir does not exist
        # Other exceptions may be raised by handle_extract_world

    """
    base_dir = get_base_dir(base_dir)

    if content_dir is None:
        content_dir = settings.get("CONTENT_DIR")
        content_dir = os.path.join(content_dir, "worlds")

    if not server_name:
        raise InvalidServerNameError("install_worlds: server_name is empty.")

    if not os.path.isdir(content_dir):
        logger.warning(
            f"Content directory not found: {content_dir}.  No worlds to install."
        )
        return

    # Use glob to find .mcworld files.
    mcworld_files = glob.glob(os.path.join(content_dir, "*.mcworld"))

    if not mcworld_files:
        logger.warning(f"No .mcworld files found in {content_dir}")
        return

    # Create a list of base file names.
    file_names = [os.path.basename(file) for file in mcworld_files]

    # Display the menu and get user selection
    print(f"{Fore.MAGENTA}Available worlds to install:{Style.RESET_ALL}")
    for i, file_name in enumerate(file_names):
        print(f"{i + 1}. {file_name}")
    print(f"{len(file_names) + 1}. Cancel")  # Add a cancel option

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
                logger.info("World installation canceled.")
                return  # User canceled
            else:
                logger.warning("Invalid selection. Please choose a valid option.")
        except ValueError:
            logger.warning("Invalid input. Please enter a number.")

    # Confirm deletion of existing world.
    logger.warning("Installing a new world will DELETE the existing world!")
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
            logger.info("World installation canceled.")
            return  # User canceled
        else:
            logger.warning("Invalid input. Please answer 'yes' or 'no'.")

    handle_extract_world(server_name, selected_file, base_dir)  # raise errors


def install_addons(server_name, base_dir, content_dir=None):
    """Installs addons (.mcaddon or .mcpack files) to the server.

    Args:
        server_name (str): The name of the server.
        base_dir (str): Base directory
        content_dir (str): The directory where the content is located.

    Raises:
        InvalidServerNameError: If server_name is empty.
        DirectoryError: If content_dir does not exist
        # Other exceptions may be raised by show_addon_selection_menu
    """

    if content_dir is None:
        content_dir = os.path.join(settings.get("CONTENT_DIR"), "addons")

    if not server_name:
        raise InvalidServerNameError("install_addons: server_name is empty.")

    if not os.path.isdir(content_dir):
        logger.warning(
            f"Addon directory not found: {content_dir}.  No addons to install."
        )
        return

    # Use glob to find .mcaddon and .mcpack files
    addon_files = glob.glob(os.path.join(content_dir, "*.mcaddon")) + glob.glob(
        os.path.join(content_dir, "*.mcpack")
    )

    if not addon_files:
        logger.warning(f"No .mcaddon or .mcpack files found in {content_dir}")
        return

    show_addon_selection_menu(server_name, addon_files, base_dir)  # Let it raise


def show_addon_selection_menu(server_name, addon_files, base_dir):
    """Displays the addon selection menu and processes the selected addon.

    Args:
        server_name (str): The name of the server.
        addon_files (list): A list of paths to addon files.
        base_dir (str): Base directory.

    Raises:
        InvalidServerNameError: If server_name is empty.
        MissingArgumentError: If addon_files is empty.
        # Other exceptions may be raised by process_addon
    """

    if not server_name:
        raise InvalidServerNameError("show_addon_selection_menu: server_name is empty.")

    if not addon_files:
        raise MissingArgumentError(
            "show_addon_selection_menu: addon_files array is empty."
        )

    addon_names = [os.path.basename(file) for file in addon_files]

    print(f"{Fore.MAGENTA}Available addons to install:{Style.RESET_ALL}")
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
                logger.info("Addon installation canceled.")
                return  # User canceled
            else:
                logger.warning("Invalid selection. Please choose a valid option.")
        except ValueError:
            logger.warning("Invalid input. Please enter a number.")

    logger.info(f"Processing addon: {addon_names[choice-1]}")

    was_running = server_base.stop_server_if_running(server_name, base_dir)  # use core
    try:
        addon.process_addon(selected_addon, server_name, base_dir)  # Call core
    except Exception as e:
        raise e
    server_base.start_server_if_was_running(
        server_name, base_dir, was_running
    )  # use core


def scan_player_data(base_dir=None, config_dir=None):
    """Scans server_output.txt files for player data and saves it to players.json."""

    base_dir = get_base_dir(base_dir)
    if config_dir is None:
        config_dir = settings._config_dir
    logger.info("Scanning for Players")
    all_players_data = []

    if not os.path.isdir(base_dir):
        raise DirectoryError(f"Error: {base_dir} does not exist or is not a directory.")

    for server_folder in glob.glob(os.path.join(base_dir, "*/")):
        server_name = os.path.basename(os.path.normpath(server_folder))
        logger.info(f"Processing {server_name}")
        log_file = os.path.join(server_folder, "server_output.txt")

        if not os.path.exists(log_file):
            logger.warning(f"Log file not found for {server_name}, skipping.")
            continue

        players_data = player.scan_log_for_players(log_file)  # Call core function
        if players_data:
            logger.info(f"Found Players in {server_name}")
            all_players_data.extend(players_data)
        else:
            logger.info(f"No players found in {server_name}, skipping.")

    if all_players_data:
        try:
            player.save_players_to_json(
                all_players_data, config_dir
            )  # Call core function
        except Exception as e:
            raise FileOperationError(f"Error saving player data: {e}") from e
    else:
        logger.info("No player data found across all servers.")


def task_scheduler(server_name, base_dir=None):
    """Displays the task scheduler menu and handles user interaction.

    Args:
        server_name (str): The name of the server.
        base_dir (str): Base directory.

    Returns:
        None

    Raises:
        InvalidServerNameError: If the server name is empty.
        # Other exceptions may be raised by the called functions.
    """
    base_dir = get_base_dir(base_dir)

    if not server_name:
        raise InvalidServerNameError("task_scheduler: server_name is empty.")

    if platform.system() == "Linux":
        _cron_scheduler(server_name, base_dir)
    elif platform.system() == "Windows":
        _windows_scheduler(server_name, base_dir, config_dir=None)
    else:
        logger.error("Unsupported operating system for task scheduling.")
        raise OSError("Unsupported operating system for task scheduling")


def _cron_scheduler(server_name, base_dir):
    """Displays the cron scheduler menu and handles user interaction.

    Args:
        server_name (str): The name of the server.
        base_dir (str): Base directory.

    Returns:
        None
    Raises:
        InvalidServerNameError, if server_name is empty
        # Other exceptions may be raised by the called functions.
    """
    if not server_name:
        raise InvalidServerNameError("cron_scheduler: server_name is empty.")

    while True:
        os.system("cls" if platform.system() == "Windows" else "clear")
        print(f"{Fore.MAGENTA}Bedrock Server Manager - Task Scheduler{Style.RESET_ALL}")
        print(
            f"{Fore.CYAN}Current scheduled task for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
        )

        try:
            cron_jobs = system_linux.get_server_cron_jobs(server_name)  # core function
        except Exception as e:
            logger.exception(f"Failed to retrieve cron jobs for {server_name}: {e}")
            time.sleep(2)
            continue

        if display_cron_job_table(cron_jobs) != 0:
            logger.error("Failed to display cron job table")
            time.sleep(2)
            continue

        print(f"{Fore.MAGENTA}What would you like to do?{Style.RESET_ALL}")
        print("1) Add Job")
        print("2) Modify Job")
        print("3) Delete Job")
        print("4) Back")

        choice = input(f"{Fore.CYAN}Enter the number (1-4):{Style.RESET_ALL} ").strip()

        if choice == "1":
            try:
                add_cron_job(server_name, base_dir)  # call core
            except Exception as e:
                logger.exception(f"Error adding cron job: {e}")
        elif choice == "2":
            try:
                modify_cron_job(server_name)  # Call core function
            except Exception as e:
                logger.exception(f"Error modifying cron job: {e}")
        elif choice == "3":
            try:
                delete_cron_job(server_name)  # call core function
            except Exception as e:
                logger.exception(f"Error deleting cron job: {e}")
        elif choice == "4":
            return  # Exit the menu
        else:
            logger.warning("Invalid choice. Please try again.")


def display_cron_job_table(cron_jobs):
    """Displays a table of cron jobs.  Returns 0 on success, non-zero on failure."""

    if not cron_jobs:
        logger.info("No cron jobs to display.")
        return 0  # Return 0 for success (no jobs is still a valid state)

    try:
        table_data = system_linux.get_cron_jobs_table(cron_jobs)
        if not table_data:
            logger.info("No valid cron jobs to display.")
            return 0  # Return 0 (no *valid* jobs, but not an error)

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
        return 0  # Success

    except Exception as e:
        logger.exception(f"Error displaying cron job table: {e}")
        return 1  # Indicate failure


def add_cron_job(server_name, base_dir):
    """Adds a new cron job."""
    if not server_name:
        raise InvalidServerNameError("add_cron_job: server_name is empty.")

    if platform.system() != "Linux":
        raise OSError("Cron jobs are only supported on Linux.")

    print(
        f"{Fore.MAGENTA}Choose the command for {Fore.YELLOW}{server_name}{Fore.MAGENTA}:{Style.RESET_ALL}"
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
                logger.warning("Invalid choice, please try again.")
        except ValueError:
            logger.warning("Invalid input. Please enter a number.")

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

    # Get cron timing details. Use a single loop.
    while True:
        try:
            month = input(f"{Fore.CYAN}Month (1-12 or *):{Style.RESET_ALL} ").strip()
            system_linux.validate_cron_input(month, 1, 12)

            day = input(
                f"{Fore.CYAN}Day of Month (1-31 or *):{Style.RESET_ALL} "
            ).strip()
            system_linux.validate_cron_input(day, 1, 31)

            hour = input(f"{Fore.CYAN}Hour (0-23 or *):{Style.RESET_ALL} ").strip()
            system_linux.validate_cron_input(hour, 0, 23)

            minute = input(f"{Fore.CYAN}Minute (0-59 or *):{Style.RESET_ALL} ").strip()
            system_linux.validate_cron_input(minute, 0, 59)

            weekday = input(
                f"{Fore.CYAN}Day of Week (0-7, 0 or 7 for Sunday or *):{Style.RESET_ALL} "
            ).strip()
            system_linux.validate_cron_input(weekday, 0, 7)

        except InvalidCronJobError as e:  # Catch the specific exception
            logger.warning(e)
            continue  # Go back to the beginning of the input loop
        except Exception as e:  # Catch any other unexpected exceptions
            logger.exception(f"Unexpected error during input: {e}")
            return  # Or handle more gracefully

        break  # If no exceptions, break out of the input loop

    schedule_time = system_linux.convert_to_readable_schedule(
        month, day, hour, minute, weekday
    )
    if schedule_time is None:
        schedule_time = "Error Converting"
        logger.error("Error Converting Schedule")

    display_command = command.replace(os.path.join(settings.EXPATH), "").strip()
    display_command = display_command.split("--", 1)[0].strip()
    print(
        f"{Fore.MAGENTA}Your cron job will run with the following schedule:{Style.RESET_ALL}"
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
            try:
                system_linux._add_cron_job(new_cron_job)
                logger.info("Cron job added successfully!")
                return  # Exit after adding
            except Exception as e:
                logger.exception(f"Error adding cron job: {e}")
                return
        elif confirm in ("no", "n", ""):
            logger.info("Cron job not added.")
            return
        else:
            logger.warning("Invalid input. Please answer 'yes' or 'no'.")


def modify_cron_job(server_name):
    """Modifies an existing cron job."""

    if not server_name:
        raise InvalidServerNameError("modify_cron_job: server_name is empty.")

    print(
        f"{Fore.MAGENTA}Current scheduled cron jobs for {Fore.YELLOW}{server_name}{Fore.MAGENTA}:{Style.RESET_ALL}"
    )

    try:
        cron_jobs = system_linux.get_server_cron_jobs(server_name)
    except Exception as e:
        raise e
    if not cron_jobs:
        logger.info("No scheduled cron jobs found to modify.")
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
                logger.warning("Invalid selection. Please choose a valid number.")
        except ValueError:
            logger.warning("Invalid input. Please enter a number.")

    # Extract the command part
    job_command = " ".join(job_to_modify.split()[5:])

    print(
        f"{Fore.MAGENTA}Modify the timing details for this cron job:{Style.RESET_ALL}"
    )
    while True:  # Single Loop
        try:
            month = input(f"{Fore.CYAN}Month (1-12 or *):{Style.RESET_ALL} ").strip()
            system_linux.validate_cron_input(month, 1, 12)

            day = input(
                f"{Fore.CYAN}Day of Month (1-31 or *):{Style.RESET_ALL} "
            ).strip()
            system_linux.validate_cron_input(day, 1, 31)

            hour = input(f"{Fore.CYAN}Hour (0-23 or *):{Style.RESET_ALL} ").strip()
            system_linux.validate_cron_input(hour, 0, 23)

            minute = input(f"{Fore.CYAN}Minute (0-59 or *):{Style.RESET_ALL} ").strip()
            system_linux.validate_cron_input(minute, 0, 59)

            weekday = input(
                f"{Fore.CYAN}Day of Week (0-7, 0 or 7 for Sunday or *):{Style.RESET_ALL} "
            ).strip()
            system_linux.validate_cron_input(weekday, 0, 7)

        except InvalidCronJobError as e:
            logger.warning(e)
            continue  # Go back to the beginning of the input loop
        except Exception as e:  # Catch all other errors
            logger.exception(f"Unexpected error: {e}")
            return

        break  # Break if all inputs are valid

    schedule_time = system_linux.convert_to_readable_schedule(
        month, day, hour, minute, weekday
    )
    if schedule_time is None:
        schedule_time = "ERROR CONVERTING"
        logger.error("Error Converting Schedule")

    # Format command
    display_command = job_command.replace(os.path.join(settings.EXPATH), "").strip()
    display_command = display_command.split("--", 1)[0].strip()
    print(
        f"{Fore.MAGENTA}Your modified cron job will run with the following schedule:{Style.RESET_ALL}"
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
            input(
                f"{Fore.CYAN}Do you want to modify this job? (y/n):{Style.RESET_ALL} "
            )
            .lower()
            .strip()
        )
        if confirm in ("yes", "y"):
            new_cron_job = f"{minute} {hour} {day} {month} {weekday} {job_command}"
            try:
                system_linux._modify_cron_job(job_to_modify, new_cron_job)
                logger.info("Cron job modified successfully!")
                return  # Success and exit
            except Exception as e:
                logger.exception(f"Error modifying cron job: {e}")
                return  # Exit if fail
        elif confirm in ("no", "n", ""):
            logger.info("Cron job not modified.")
            return
        else:
            logger.warning("Invalid input. Please answer 'yes' or 'no'.")


def delete_cron_job(server_name):
    """Deletes a cron job for the specified server. (UI)"""

    if not server_name:
        raise InvalidServerNameError("delete_cron_job: server_name is empty.")

    print(
        f"{Fore.CYAN}Current scheduled cron jobs for {Fore.YELLOW}{server_name}:{Style.RESET_ALL}"
    )

    try:
        cron_jobs = system_linux.get_server_cron_jobs(server_name)
    except Exception as e:
        logger.exception(f"Failed to retrieve cron jobs for {server_name}: {e}")
        return

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
                print(f"{_OK_PREFIX}Cron job deletion canceled.")
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
            try:
                system_linux._delete_cron_job(job_to_delete)  # use core function
            except Exception as e:
                raise e
            logger.info("Cron job deleted successfully!")
            return  # Return the result.
        elif confirm_delete in ("n", "no", ""):
            logger.info("Cron job not deleted.")
            return  # User canceled
        else:
            logger.warning("Invalid input. Please answer 'yes' or 'no'.")


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

        task_names = system_windows.get_server_task_names(server_name, config_dir)
        if not task_names:
            print("No scheduled tasks found.")
        else:
            display_windows_task_table(task_names)

        print(f"{Fore.MAGENTA}What would you like to do?{Style.RESET_ALL}")
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
                delete_windows_task(server_name, config_dir)
            elif choice == "4":
                return  # Exit the menu
            else:
                logger.warning("Invalid choice. Please try again.")
        except Exception as e:
            logger.exception(f"An error has occurred: {e}")


def display_windows_task_table(task_names):
    """Displays a table of Windows scheduled tasks.

     Args:
        task_names (list): A list of task names,
                          as returned by get_server_task_names
    Raises:
        TypeError: if task_names is not a list
    """
    if not isinstance(task_names, list):
        raise TypeError("task_names must be a list")

    task_info = system_windows.get_windows_task_info([task[0] for task in task_names])

    print(
        "-------------------------------------------------------------------------------"
    )
    print(f"{'TASK NAME':<30} {'COMMAND':<25} {'SCHEDULE':<20}")
    print(
        "-------------------------------------------------------------------------------"
    )

    for task in task_info:
        print(
            f"{Fore.GREEM}{task['task_name']:<30}{Fore.YELLOW}{task['command']:<25}{Fore.CYAN}{task['schedule']:<20}{Style.RESET_ALL}"
        )
    print(
        "-------------------------------------------------------------------------------"
    )


def add_windows_task(server_name, base_dir, config_dir=None):
    """Adds a new Windows scheduled task."""

    if not server_name:
        raise InvalidServerNameError("add_windows_task: server_name is empty.")

    if platform.system() != "Windows":
        raise OSError("This function is for Windows only.")

    if config_dir is None:
        config_dir = settings._config_dir

    print(
        f"{Fore.MAGENTA}Adding task for {Fore.YELLOW}{server_name}{Fore.MAGENTA}:{Style.RESET_ALL}"
    )

    print(
        f"{Fore.MAGENTA}Choose the command:{Style.RESET_ALL}"
    )  # Keep print for direct user prompts
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
                logger.info("Add task cancelled.")
                return  # User cancelled
            else:
                logger.warning("Invalid choice, please try again.")
        except ValueError:
            logger.warning("Invalid input. Please enter a number.")

    if choice == 1:
        command = "update-server"
        command_args = f"--server {server_name}"
    elif choice == 2:
        command = "backup-all"  # Use backup-all
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

    # Get trigger information from the user *here*
    triggers = get_trigger_details()

    # Call core function to create the task XML
    try:
        xml_file_path = system_windows.create_windows_task_xml(
            server_name, command, command_args, task_name, config_dir, triggers
        )
        system_windows.import_task_xml(xml_file_path, task_name)  # core function
        logger.info(f"Task '{task_name}' added successfully!")
    except Exception as e:
        raise e  # Re-raise any exception


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
                    logger.error("Incorrect format, please use YYYY-MM-DD HH:MM")
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
                    logger.error("Incorrect format, please use YYYY-MM-DD HH:MM")
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
                        logger.warning("Enter a value greater than or equal to 1")
                except ValueError:
                    logger.error("Must be a valid integer.")
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
                    logger.error("Incorrect format, please use YYYY-MM-DD HH:MM")

            while True:  # Loop for days of the week input
                days_of_week_str = input(
                    f"{Fore.CYAN}Enter days of the week (comma-separated: Sun,Mon,Tue,Wed,Thu,Fri,Sat OR 1-7):{Style.RESET_ALL} "
                ).strip()
                days_of_week = [day.strip() for day in days_of_week_str.split(",")]
                valid_days = []
                for day_input in days_of_week:
                    if system_windows._get_day_element_name(
                        day_input
                    ):  # use core function
                        valid_days.append(day_input)
                    else:
                        logger.warning(f"Invalid day of week: {day_input}. Skipping.")
                if valid_days:
                    trigger_data["days"] = valid_days
                    break  # Exit if at least one valid day is entered
                else:
                    logger.error("You must enter at least one valid day.")

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
                        logger.warning("Enter a value greater than or equal to 1")
                except ValueError:
                    logger.error("Must be a valid integer.")
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
                    logger.error("Incorrect date format, please use YYYY-MM-DD HH:MM")

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
                            logger.warning(f"Invalid day of month: {day}. Skipping.")
                    except ValueError:
                        logger.warning(f"Invalid day of month: {day}. Skipping.")
                if valid_days:
                    trigger_data["days"] = valid_days
                    break
                else:
                    logger.error("You must enter at least one valid day")

            while True:  # Loop for months input
                months_str = input(
                    f"{Fore.CYAN}Enter months (comma-separated: Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec OR 1-12):{Style.RESET_ALL} "
                ).strip()
                months = [month.strip() for month in months_str.split(",")]
                valid_months = []
                for month_input in months:
                    if system_windows._get_month_element_name(
                        month_input
                    ):  # use core function
                        valid_months.append(month_input)
                    else:
                        logger.warning(f"Invalid month: {month_input}. Skipping.")
                if valid_months:
                    trigger_data["months"] = valid_months
                    break  # Exit loop
                else:
                    logger.error("You must enter at least one valid month.")
            triggers.append(trigger_data)

        elif trigger_choice == "5":
            continue  # Add another trigger
        elif trigger_choice == "6":
            break  # Done adding triggers
        else:
            logger.warning("Invalid choice.")

    return triggers


def modify_windows_task(server_name, base_dir, config_dir=None):
    """Modifies an existing Windows scheduled task."""
    if config_dir is None:
        config_dir = settings._config_dir

    if not server_name:
        raise InvalidServerNameError("modify_windows_task: server_name is empty.")

    if platform.system() != "Windows":
        raise OSError("This function is for Windows only.")

    task_names = system_windows.get_server_task_names(server_name, config_dir)
    if not task_names:
        logger.info("No scheduled tasks found to modify.")
        return

    print(
        f"{Fore.MAGENTA}Select the task to modify for {Fore.YELLOW}{server_name}:{Style.RESET_ALL}"
    )
    for i, (task_name) in enumerate(task_names):
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
                selected_task_name, selected_file_path = task_names[task_index]
                break
            elif task_index == len(task_names):
                logger.info("Modify task cancelled.")
                return  # Cancelled
            else:
                logger.warning("Invalid selection.")
        except ValueError:
            logger.warning("Invalid input. Please enter a number.")

    # Load existing XML (for command/args extraction)
    try:
        tree = ET.parse(selected_file_path)
        root = tree.getroot()

        # Get the existing command and arguments
        actions = root.find(
            ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}Actions"
        )
        command = ""  # Default to empty string
        command_args = ""  # Initialize command_args
        if actions is not None:
            exec_action = actions.find(
                ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}Exec"
            )
            if exec_action is not None:
                arguments_element = exec_action.find(
                    ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}Arguments"
                )
                if arguments_element is not None and arguments_element.text is not None:
                    command_args = arguments_element.text.strip()

        # --- Get NEW trigger information from the user ---
        triggers = get_trigger_details()

    except (ET.ParseError, FileNotFoundError) as e:
        raise FileOperationError(f"Error loading or parsing XML: {e}") from e

    # Create a *new* task name
    new_task_name = f"bedrock_{server_name}_{command.replace('-', '_')}"

    try:
        # 1. Create the new XML, using the *existing* command and arguments,
        #    the *new* task name, the *new* triggers, and the config_dir.
        new_xml_file_path = system_windows.create_windows_task_xml(
            server_name, command, command_args, new_task_name, config_dir, triggers
        )

        # 2. Delete the *old* task, using the *original* task name.
        system_windows.delete_task(selected_task_name)

        # 3. Import the *new* task, using the *new* XML file and the *new* name.
        system_windows.import_task_xml(new_xml_file_path, new_task_name)
        logger.info(
            f"Task '{selected_task_name}' modified successfully! (New name: {new_task_name})"
        )

    except Exception as e:
        raise TaskError(f"Failed to modify task: {e}") from e


def delete_windows_task(server_name, config_dir=None):
    """Deletes a Windows scheduled task."""
    if config_dir is None:
        config_dir = settings._config_dir

    if not server_name:
        raise InvalidServerNameError("delete_windows_task: server_name is empty.")

    if platform.system() != "Windows":
        raise OSError("This function is for Windows only.")

    task_names = system_windows.get_server_task_names(server_name, config_dir)
    if not task_names:
        logger.info("No scheduled tasks found to delete.")
        return

    print(
        f"{Fore.MAGENTA}Select the task to delete for {Fore.YELLOW}{server_name}:{Style.RESET_ALL}"
    )
    for i, (task_name) in enumerate(task_names):
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
                selected_task_name, selected_file_path = task_names[task_index]
                break
            elif task_index == len(task_names):
                logger.info("Task deletion cancelled.")
                return  # Cancelled
            else:
                logger.warning("Invalid selection.")
        except ValueError:
            logger.warning("Invalid input. Please enter a number.")

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
            try:
                system_windows.delete_task(selected_task_name)
                logger.info(f"Task '{selected_task_name}' deleted successfully!")
                # Also remove the XML file
                try:
                    os.remove(selected_file_path)
                    logger.info(f"Task XML file '{selected_file_path}' removed.")
                except OSError as e:
                    logger.warning(f"Failed to remove task XML file: {e}")
                    # Not critical, don't raise, task is already deleted.
                return
            except Exception as e:
                raise e

        elif confirm_delete in ("n", "no", ""):
            logger.info("Task deletion canceled.")
            return  # User canceled
        else:
            logger.warning("Invalid input.  Please enter 'y' or 'n'.")


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
