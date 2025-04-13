# bedrock-server-manager/bedrock_server_manager/cli/player.py
"""
Command-line interface functions for managing player data.

Provides handlers for CLI commands related to scanning server logs for player
information and manually adding players to the persistent configuration.
Uses print() for user-facing feedback.
"""

import logging
from typing import Optional, List, Dict, Any

# Local imports
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.utils.general import (
    _OK_PREFIX,
    _ERROR_PREFIX,
    _INFO_PREFIX,
)
from bedrock_server_manager.error import (
    FileOperationError,
    DirectoryError,
    MissingArgumentError,
    TypeError,
)

logger = logging.getLogger("bedrock_server_manager")


def scan_for_players(
    base_dir: Optional[str] = None, config_dir: Optional[str] = None
) -> None:
    """
    CLI handler function to scan all server logs for player data and save unique
    entries to the central players.json file.

    Prints status messages to the console based on the API call result.

    Args:
        base_dir: Optional. The base directory containing server installation folders.
                  Uses the configured default if None.
        config_dir: Optional. The directory where players.json should be saved.
                    Uses the main application config directory if None.
    """
    logger.debug("CLI: Starting player scan process...")
    print(f"{_INFO_PREFIX}Scanning server logs for player data...")

    try:
        # Call the API function
        logger.debug("Calling API: player_api.scan_for_players")
        response: Dict[str, Any] = player_api.scan_for_players(
            base_dir, config_dir
        )  # Returns dict
        logger.debug(f"API response from scan_for_players: {response}")

        # --- User Interaction: Print Result ---
        if response.get("status") == "error":
            message = response.get("message", "Unknown error during player scan.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Player scan failed: {message}")
        elif response.get("players_found"):
            # Success and players were found/saved
            message = response.get(
                "message", "Player data scanned and saved successfully."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Player scan successful, data found and saved.")
        else:
            # Success but no new player data found
            message = response.get(
                "message", "Scan complete. No new player data found in logs."
            )
            print(f"{_INFO_PREFIX}{message}")
            logger.debug(f"CLI: Player scan successful, no new data found.")
        # --- End User Interaction ---

    except (FileOperationError, DirectoryError) as e:
        # Catch errors raised directly by API func setup (e.g., bad base_dir)
        print(f"{_ERROR_PREFIX}Configuration or Directory Error: {e}")
        logger.error(f"CLI: Failed to initiate player scan: {e}", exc_info=True)
    except Exception as e:
        # Catch unexpected errors during the API call
        print(f"{_ERROR_PREFIX}An unexpected error occurred during player scan: {e}")
        logger.error(f"CLI: Unexpected error during player scan: {e}", exc_info=True)


def add_players(players: List[str], config_dir: Optional[str] = None) -> None:
    """
    CLI handler function to add player data (name:xuid) to the players.json file.

    Parses input strings, calls the API function to save the data, and prints
    status messages to the console.

    Args:
        players: A list of player strings, each formatted as "PlayerName:PlayerXUID".
        config_dir: Optional. The directory where players.json resides.
                    Uses the main application config directory if None.

    Raises:
        TypeError: If `players` is not a list (raised directly by API function).
        MissingArgumentError: If `players` list is empty (raised directly by API function).
        # Other errors like InvalidInputError or FileOperationError are caught and printed.
    """
    # Input validation (list type, non-empty) is handled by the API function directly

    logger.debug(f"CLI: Attempting to add {len(players)} players to config.")
    logger.debug(f"Players to add: {players}")
    print(f"{_INFO_PREFIX}Adding provided player data...")

    try:
        # Call the API function
        logger.debug("Calling API: player_api.add_players")
        response: Dict[str, str] = player_api.add_players(
            players, config_dir
        )  # Returns dict
        logger.debug(f"API response from add_players: {response}")

        # --- User Interaction: Print Result ---
        if response.get("status") == "error":
            message = response.get("message", "Unknown error adding players.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Failed to add players: {message}")
        else:
            message = response.get("message", "Players added/updated successfully.")
            print(f"{_OK_PREFIX}{message}")  # Print success message
            logger.debug(f"CLI: Adding players successful.")
        # --- End User Interaction ---

    except (TypeError, MissingArgumentError) as e:
        # Catch input validation errors raised by API func
        print(f"{_ERROR_PREFIX}Input Error: {e}")
        logger.error(f"CLI: Invalid input for add_players: {e}", exc_info=True)
    except FileOperationError as e:
        # Catch config dir errors raised by API func
        print(f"{_ERROR_PREFIX}Configuration Error: {e}")
        logger.error(f"CLI: Configuration error adding players: {e}", exc_info=True)
    except Exception as e:
        # Catch unexpected errors during the API call
        print(f"{_ERROR_PREFIX}An unexpected error occurred while adding players: {e}")
        logger.error(f"CLI: Unexpected error adding players: {e}", exc_info=True)
