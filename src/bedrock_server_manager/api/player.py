# bedrock_server_manager/api/player.py
"""Provides API-level functions for managing the central player database.

This module interfaces with the `BedrockServerManager` to add, retrieve,
and discover player information (gamertags and XUIDs), which is stored in a
central `players.json` file.
"""

import logging
from typing import Dict, List, Any

# Plugin system imports to bridge API functionality.
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.error import (
    BSMError,
    UserInputError,
)

logger = logging.getLogger(__name__)
bsm = BedrockServerManager()


@plugin_method("add_players_manually_api")
def add_players_manually_api(player_strings: List[str]) -> Dict[str, Any]:
    """Adds or updates player data in the central players.json file.

    This function takes a list of strings, each containing a player's
    gamertag and XUID, parses them, and saves the data to the central
    player database.

    Args:
        player_strings: A list of strings, where each string is expected
            to be in the format "gamertag,xuid". For example:
            `["PlayerOne,1234567890123456", "PlayerTwo,6543210987654321"]`.

    Returns:
        A dictionary containing the status of the operation, a descriptive
        message, and the count of players processed. On error, it returns
        a status and an error message.
    """
    logger.info(f"API: Adding players manually: {player_strings}")
    # --- Input Validation ---
    if (
        not player_strings
        or not isinstance(player_strings, list)
        or not all(isinstance(s, str) for s in player_strings)
    ):
        return {
            "status": "error",
            "message": "Input must be a non-empty list of player strings.",
        }

    result = {}
    parsed_list = []
    try:
        # The core parsing function expects a single comma-separated string.
        combined_input = ",".join(player_strings)
        parsed_list = bsm.parse_player_cli_argument(combined_input)

        # --- Plugin Hook: Before Add ---
        plugin_manager.trigger_event("before_players_add", players_data=parsed_list)

        num_saved = 0
        if parsed_list:
            # Delegate saving to the core manager.
            num_saved = bsm.save_player_data(parsed_list)

        result = {
            "status": "success",
            "message": f"{num_saved} player entries processed and saved/updated.",
            "count": num_saved,
        }

    except UserInputError as e:
        # Handle errors related to invalid player string formats.
        result = {"status": "error", "message": f"Invalid player data: {str(e)}"}

    except BSMError as e:
        # Handle errors during the file-saving process.
        result = {"status": "error", "message": f"Error saving player data: {str(e)}"}

    except Exception as e:
        # Handle any other unexpected errors.
        logger.error(f"API: Unexpected error adding players: {e}", exc_info=True)
        result = {
            "status": "error",
            "message": f"An unexpected error occurred: {str(e)}",
        }

    finally:
        # --- Plugin Hook: After Add ---
        plugin_manager.trigger_event("after_players_add", result=result)

    return result


@plugin_method("get_all_known_players_api")
def get_all_known_players_api() -> Dict[str, Any]:
    """Retrieves all player data from the central players.json file.

    Returns:
        A dictionary containing the operation status and a list of all known
        player objects. On success: `{"status": "success", "players": [...]}`.
        On error: `{"status": "error", "message": "..."}`.
    """
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


@plugin_method("scan_and_update_player_db_api")
def scan_and_update_player_db_api() -> Dict[str, Any]:
    """Scans all server logs to discover and save player data.

    This function iterates through the log files of all managed servers,
    extracts player connection information (gamertag and XUID), and updates
    the central player database with any new findings.

    Returns:
        A dictionary containing the status, a summary message, and detailed
        results of the scan, including counts of players found, saved, and
        any errors encountered.
    """
    logger.info("API: Request to scan all server logs and update player DB.")

    # --- Plugin Hook: Before Scan ---
    plugin_manager.trigger_event("before_player_db_scan")

    result = {}
    try:
        # Delegate the entire discovery and saving process to the core manager.
        scan_result = bsm.discover_and_store_players_from_all_server_logs()

        # Format a comprehensive success message from the scan results.
        message = (
            f"Player DB update complete. "
            f"Entries found in logs: {scan_result['total_entries_in_logs']}. "
            f"Unique players submitted: {scan_result['unique_players_submitted_for_saving']}. "
            f"Actually saved/updated: {scan_result['actually_saved_or_updated_in_db']}."
        )
        if scan_result["scan_errors"]:
            message += f" Scan errors encountered for: {scan_result['scan_errors']}"

        result = {"status": "success", "message": message, "details": scan_result}

    except BSMError as e:
        # Handle application-specific errors during the scan.
        result = {
            "status": "error",
            "message": f"An error occurred during player scan: {str(e)}",
        }

    except Exception as e:
        # Handle any other unexpected errors.
        logger.error(f"API: Unexpected error scanning for players: {e}", exc_info=True)
        result = {
            "status": "error",
            "message": f"An unexpected error occurred during player scan: {str(e)}",
        }

    finally:
        # --- Plugin Hook: After Scan ---
        plugin_manager.trigger_event("after_player_db_scan", result=result)

    return result
