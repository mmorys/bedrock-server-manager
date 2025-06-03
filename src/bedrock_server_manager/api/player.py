# bedrock-server-manager/src/bedrock_server_manager/api/player.py
"""
Provides API-level functions for managing player data.

This module acts as an interface layer, orchestrating calls to core player
functions for tasks like scanning server logs for player connections and
adding/retrieving players from a persistent JSON store (`players.json`).
Functions typically return a dictionary indicating success or failure status.
"""

import logging
from typing import Dict, List, Optional, Any

from bedrock_server_manager.manager import BedrockServerManager
from bedrock_server_manager.error import (
    FileOperationError,
    InvalidInputError,
    DirectoryError,
    MissingArgumentError,
)

logger = logging.getLogger(__name__)
bsm = BedrockServerManager()


def add_players_manually_api(player_strings: List[str]) -> Dict[str, Any]:
    logger.info(f"API: Adding players manually: {player_strings}")
    if (
        not player_strings
        or not isinstance(player_strings, list)
        or not all(isinstance(s, str) for s in player_strings)
    ):
        return {
            "status": "error",
            "message": "Input must be a non-empty list of player strings.",
        }

    try:
        combined_input = ",".join(player_strings)  # BSM parses comma-separated string
        parsed_list = bsm.parse_player_cli_argument(combined_input)

        num_saved = 0
        if parsed_list:
            num_saved = bsm.save_player_data(parsed_list)

        return {
            "status": "success",
            "message": f"{num_saved} player entries processed and saved/updated.",
            "count": num_saved,
        }
    except InvalidInputError as e:
        return {"status": "error", "message": f"Invalid player data: {str(e)}"}
    except FileOperationError as e:
        return {"status": "error", "message": f"Error saving player data: {str(e)}"}
    except Exception as e:
        logger.error(f"API: Unexpected error adding players: {e}", exc_info=True)
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}


def get_all_known_players_api() -> Dict[str, Any]:
    logger.info("API: Request to get all known players.")
    try:
        players = bsm.get_known_players()
        return {"status": "success", "players": players}
    except Exception as e:
        logger.error(f"API: Unexpected error getting players: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An unexpected error occurred retrieving players: {str(e)}",
        }


def scan_and_update_player_db_api() -> Dict[str, Any]:
    logger.info("API: Request to scan all server logs and update player DB.")
    try:
        result = bsm.discover_and_store_players_from_all_server_logs()
        # result = { "total_entries_in_logs": int, "unique_players_submitted_for_saving": int,
        #            "actually_saved_or_updated_in_db": int, "scan_errors": List }

        message = (
            f"Player DB update complete. "
            f"Entries found in logs: {result['total_entries_in_logs']}. "
            f"Unique players submitted: {result['unique_players_submitted_for_saving']}. "
            f"Actually saved/updated: {result['actually_saved_or_updated_in_db']}."
        )
        if result["scan_errors"]:
            message += f" Scan errors encountered for: {result['scan_errors']}"

        return {"status": "success", "message": message, "details": result}
    except DirectoryError as e:
        return {
            "status": "error",
            "message": f"Directory error during player scan: {str(e)}",
        }
    except FileOperationError as e:  # From BSM save_player_data failure
        return {
            "status": "error",
            "message": f"Failed to save player data after scan: {str(e)}",
        }
    except Exception as e:
        logger.error(f"API: Unexpected error scanning for players: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An unexpected error occurred during player scan: {str(e)}",
        }
