# bedrock-server-manager/bedrock_server_manager/cli/player.py
import logging
from bedrock_server_manager.api import player
from bedrock_server_manager.utils.general import (
    _OK_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger("bedrock_server_manager")


def scan_for_players(base_dir=None, config_dir=None):
    """Scans server_output.txt files for player data and saves it to players.json."""

    response = player.scan_for_players(base_dir, config_dir)

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
    elif response["players_found"]:
        print(f"{_OK_PREFIX}Player data scanned and saved successfully.")
    else:
        print(f"{_OK_PREFIX}No player data found.")


def add_players_to_config(players, config_dir):
    """Handles the user interaction and logic for adding players to the players.json file."""

    response = player.add_players(players, config_dir)

    if response["status"] == "error":
        print(f"{_ERROR_PREFIX}{response['message']}")
        return

    print("Players added successfully.")  # Only print on success
