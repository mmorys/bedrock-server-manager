# bedrock-server-manager/bedrock_server_manager/api/player.py
import os
import glob
import json
import logging
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.core.player import player as player_base
from bedrock_server_manager.core.error import (
    FileOperationError,
    PlayerDataError,
)


logger = logging.getLogger("bedrock_server_manager")


def scan_for_players(base_dir=None, config_dir=None):
    """Scans server_output.txt files for player data and saves it to ./config/players.json.

    Args:
        base_dir (str, optional): The base directory. Defaults to None.
        config_dir (str, optional): The config directory. Defaults to the
            main config dir.

    Returns:
        dict: {"status": "success", "players_found": True/False}
            or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    if config_dir is None:
        config_dir = settings._config_dir

    logger.info("Scanning for Players")
    all_players_data = []

    if not os.path.isdir(base_dir):
        logger.error(f"Error: {base_dir} does not exist or is not a directory.")
        return {
            "status": "error",
            "message": f"Error: {base_dir} does not exist or is not a directory.",
        }

    for server_folder in glob.glob(os.path.join(base_dir, "*/")):
        server_name = os.path.basename(os.path.normpath(server_folder))
        log_file = os.path.join(server_folder, "server_output.txt")
        logger.debug(f"Scanning for player data in: {log_file}")

        if not os.path.exists(log_file):
            logger.warning(f"Log file not found for {server_name}, skipping.")
            continue

        try:
            players_data = player_base.scan_log_for_players(log_file)
            if players_data:
                logger.debug(f"Found player data for {server_name}: {players_data}")
                all_players_data.extend(players_data)
        except Exception as e:
            logger.exception(f"Error scanning log for {server_name}: {e}")
            return {
                "status": "error",
                "message": f"Error scanning log for {server_name}: {e}",
            }

    if all_players_data:
        try:
            player_base.save_players_to_json(all_players_data, config_dir)
            logger.info(f"Saved player data to {config_dir}/players.json")
            return {"status": "success", "players_found": True}
        except Exception as e:
            logger.exception(f"Error saving player data: {e}")
            return {"status": "error", "message": f"Error saving player data: {e}"}
    else:
        logger.info("No player data found across all servers.")
        return {"status": "success", "players_found": False}


def add_players(players, config_dir):
    """Adds players to the players.json file.

    Args:
        players (list): A list of strings, where each string represents a player
                        in the format "playername:playerid".
        config_dir (str): The directory where the players.json file is located.

    Returns:
        dict: A dictionary indicating success or failure.
            On success: {"status": "success"}
            On failure: {"status": "error", "message": ...}
    """
    logger.info("Adding players to players.json...")
    try:
        player_string = ",".join(players)  # Join the list into a comma-separated string
        player_list = player_base.parse_player_argument(player_string)
        player_base.save_players_to_json(player_list, config_dir)
        logger.debug(f"Added players: {player_list}")
        return {"status": "success"}
    except PlayerDataError as e:  # Catch specific errors first
        logger.error(f"Error parsing player data: {e}")
        return {"status": "error", "message": f"Error parsing player data: {e}"}
    except FileOperationError as e:
        logger.error(f"Error saving player data: {e}")
        return {"status": "error", "message": f"Error saving player data: {e}"}
    except ValueError as e:
        logger.error(f"Invalid player data format: {e}")
        return {"status": "error", "message": f"Invalid player data format: {e}"}
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred: {type(e).__name__}: {e}"
        )  # Log unexpected errors
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def get_players_from_json(config_dir=None):
    """Retrieves player data from players.json.

    Args:
        config_dir (str, optional): The configuration directory. Defaults to the main config dir.

    Returns:
        dict: {"status": "success", "players": [...]} or {"status": "error", "message": ...}
    """
    if config_dir is None:
        config_dir = settings._config_dir

    players_file = os.path.join(config_dir, "players.json")
    logger.info(f"Retrieving player data from: {players_file}")

    if not os.path.exists(players_file):
        logger.warning(f"No players.json file found at: {players_file}")
        return {
            "status": "error",
            "message": f"No players.json file found at: {players_file}",
        }

    try:
        with open(players_file, "r") as f:
            players_data = json.load(f)
            #  Validate that players_data is structured as expected.
            if (
                not isinstance(players_data, dict)
                or "players" not in players_data
                or not isinstance(players_data["players"], list)
            ):
                logger.error(f"Invalid players.json format in {players_file}")
                return {"status": "error", "message": f"Invalid players.json format."}
            logger.debug(f"Successfully loaded player data: {players_data}")
            return {"status": "success", "players": players_data["players"]}

    except (OSError, json.JSONDecodeError) as e:
        logger.exception(f"Failed to read or parse players.json: {e}")
        return {
            "status": "error",
            "message": f"Failed to read or parse players.json: {e}",
        }
