# bedrock-server-manager/bedrock_server_manager/core/player/player.py
import re
import os
import json
import logging
from bedrock_server_manager.core.error import FileOperationError, InvalidInputError

logger = logging.getLogger("bedrock_server_manager")


def parse_player_argument(player_string):
    """Parses a player string like 'playername:playerid, player2:player2id' into a list of dictionaries."""
    logger.debug(f"Parsing player argument: {player_string}")
    player_pairs = player_string.split(",")
    player_list = []
    for pair in player_pairs:
        player_data = pair.split(":")
        if len(player_data) != 2:
            logger.error(f"Invalid player data format: {pair}")
            raise ValueError(f"Invalid player data format: {pair}")
        player_name, player_id = player_data
        player_list.append({"name": player_name.strip(), "xuid": player_id.strip()})
    logger.debug(f"Parsed player list: {player_list}")
    return player_list


def scan_log_for_players(log_file):
    """Scans a single server_output.txt file for player data.

    Args:
        log_file (str): Path to the server_output.txt file.

    Returns:
        list: A list of dictionaries, each with 'name' and 'xuid' keys,
            or an empty list if no players are found.
    Raises:
        FileOperationError: If the log file cannot be read.
    """
    logger.debug(f"Scanning log file for players: {log_file}")
    players_data = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                match = re.search(
                    r"Player connected:\s*([^,]+),\s*xuid:\s*(\d+)$", line
                )
                if match:
                    player_name = match.group(1)
                    xuid = match.group(2)
                    logger.info(f"Found player: {player_name} with XUID: {xuid}")
                    players_data.append(
                        {"name": player_name, "xuid": xuid}
                    )  # Store as dictionaries
    except OSError as e:
        logger.error(f"Error reading log file {log_file}: {e}")
        raise FileOperationError(
            f"Error reading log file {log_file}: {e}"
        ) from e  # Raise the exception

    logger.debug(f"Players found in log file: {players_data}")
    return players_data  # Return data if all is ok


def save_players_to_json(players_data, config_dir):
    """Saves or updates player data in players.json.

    Args:
        players_data (list): A list of dictionaries, each with 'name' and 'xuid' keys.
        config_dir (str): The directory to save the players.json file to.
    Returns:
        None
    Raises:
        FileOperationError: If there's an error reading or writing the file.
        InvalidInputError: If input data is not in the correct format.
    """
    logger.debug(f"Saving players to JSON: {players_data}")
    players_file = os.path.join(config_dir, "players.json")

    try:
        # Load Existing Data
        if os.path.exists(players_file):
            try:
                with open(players_file, "r") as f:
                    existing_data = json.load(f)
                    # Use .get() for safety, and handle potential missing 'players' key
                    existing_players = {
                        player["xuid"]: player
                        for player in existing_data.get("players", [])
                    }
                logger.debug(f"Existing players loaded: {existing_players}")
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(
                    f"Failed to read or parse existing players.json, creating new: {e}"
                )
                existing_players = {}  # Start with an empty dictionary
        else:
            logger.debug("No existing players.json found, creating new.")
            existing_players = {}

        # Check if players_data is a list and contains dictionaries
        if not isinstance(players_data, list) or not all(
            isinstance(player, dict) for player in players_data
        ):
            logger.error("players_data must be a list of dictionaries.")
            raise InvalidInputError("players_data must be a list of dictionaries.")
        # Merge Data (Update or Add)
        for player in players_data:
            # Basic validation of the player dictionary.
            if (
                not isinstance(player, dict)
                or "xuid" not in player
                or not isinstance(player.get("xuid"), str)
                or "name" not in player
                or not isinstance(player.get("name"), str)
            ):
                logger.error(f"Skipping invalid player data: {player}.")
                continue  # Skip to the next player

            existing_players[player["xuid"]] = player  # XUID as key
        logger.debug(f"Merged player data: {existing_players}")

        # Convert back to a list of dictionaries for JSON serialization
        updated_players = list(existing_players.values())

        # Write to File
        with open(players_file, "w") as f:
            json.dump(
                {"players": updated_players}, f, indent=4
            )  # ensure correct format
        logger.info(f"Players data saved to: {players_file}")

    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to save players to JSON: {e}")
        raise FileOperationError(f"Failed to save players to JSON: {e}") from e
