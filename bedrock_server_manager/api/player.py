# bedrock-server-manager/bedrock_server_manager/api/player.py
"""
Provides API-level functions for managing player data.

This module acts as an interface layer, orchestrating calls to core player
functions for tasks like scanning server logs for player connections and
adding/retrieving players from a persistent JSON store (`players.json`).
Functions typically return a dictionary indicating success or failure status.
"""

import os
import glob
import json
import logging
from typing import Dict, List, Optional, Any

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.core.player import player as player_base
from bedrock_server_manager.error import (
    FileOperationError,
    InvalidInputError,
    MissingArgumentError,
    DirectoryError,
)

logger = logging.getLogger("bedrock_server_manager")


def scan_for_players(
    base_dir: Optional[str] = None, config_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Scans all server log files (`server_output.txt`) within the base directory
    for player connection entries (name and XUID). Found player data is then
    merged and saved into the central `players.json` file in the config directory.

    Args:
        base_dir: Optional. The base directory containing server installation folders.
                  Uses the configured default if None.
        config_dir: Optional. The directory where `players.json` should be saved.
                    Uses the main application config directory if None.

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "players_found": bool, "message": str}
        - {"status": "error", "message": str}
    """
    logger.info("Initiating scan across server logs for player data...")

    try:
        effective_base_dir = get_base_dir(base_dir)
        effective_config_dir = (
            config_dir
            if config_dir is not None
            else getattr(settings, "_config_dir", None)
        )

        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory is not set or available."
            )
        if not os.path.isdir(effective_base_dir):
            # Use DirectoryError consistent with core modules
            raise DirectoryError(
                f"Server base directory does not exist or is not a directory: {effective_base_dir}"
            )

        logger.debug(f"Scanning base directory: {effective_base_dir}")
        logger.debug(f"Using config directory: {effective_config_dir}")

    except (FileOperationError, DirectoryError) as e:
        logger.error(
            f"Configuration or directory error preventing player scan: {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration or directory error: {e}"}

    all_players_data: List[Dict[str, str]] = []
    scan_errors = []

    # Use glob to find potential server directories
    server_pattern = os.path.join(effective_base_dir, "*", "")
    found_server_dirs = glob.glob(server_pattern)

    if not found_server_dirs:
        logger.warning(
            f"No server directories found within '{effective_base_dir}'. Cannot scan for players."
        )
        return {
            "status": "success",
            "players_found": False,
            "message": "No server directories found.",
        }

    for server_folder_path in found_server_dirs:
        # Ensure it's actually a directory before proceeding
        if not os.path.isdir(server_folder_path):
            continue

        server_name = os.path.basename(os.path.normpath(server_folder_path))
        log_file = os.path.join(server_folder_path, "server_output.txt")
        logger.debug(f"Scanning server '{server_name}': checking log file '{log_file}'")

        if not os.path.isfile(log_file):  # Check if it's a file
            logger.debug(f"Log file not found for server '{server_name}'. Skipping.")
            continue

        try:
            # Call the core function to scan this specific log file
            players_in_log = player_base.scan_log_for_players(
                log_file
            )  # Raises FileOperationError on read issue
            if players_in_log:
                logger.info(
                    f"Found {len(players_in_log)} player entries in log for server '{server_name}'."
                )
                # Extend the main list (duplicates will be handled by save_players_to_json)
                all_players_data.extend(players_in_log)
            else:
                logger.debug(
                    f"No player connection entries found in log for server '{server_name}'."
                )
        except FileOperationError as e:
            # Log error for this specific server but continue scanning others
            logger.error(
                f"Error scanning log file for server '{server_name}': {e}",
                exc_info=True,
            )
            scan_errors.append(server_name)
        except Exception as e:
            # Catch unexpected errors during scan for one server
            logger.error(
                f"Unexpected error scanning log file for server '{server_name}': {e}",
                exc_info=True,
            )
            scan_errors.append(server_name)

    # --- Save results (if any players found) ---
    save_error = None
    if all_players_data:
        logger.info(
            f"Found a total of {len(all_players_data)} player entries across all scanned logs. Saving any new players..."
        )
        try:
            # Core function handles merging and saving unique players by XUID
            player_base.save_players_to_json(all_players_data, effective_config_dir)
            logger.info(
                f"Successfully saved/updated unique player data to 'players.json' in '{effective_config_dir}'."
            )
        except (FileOperationError, InvalidInputError) as e:
            save_error = f"Error saving player data to JSON: {e}"
            logger.error(save_error, exc_info=True)
        except Exception as e:
            save_error = f"Unexpected error saving player data: {e}"
            logger.error(save_error, exc_info=True)
    else:
        logger.info("No new player data found in any server logs during this scan.")

    # --- Determine final status ---
    if scan_errors:
        message = f"Scan completed with errors for server(s): {', '.join(scan_errors)}."
        if save_error:
            message += f" Additionally, failed to save results: {save_error}"
        elif all_players_data:
            message += " Player data found in other logs was saved."
        return {"status": "error", "message": message}
    elif save_error:
        return {"status": "error", "message": save_error}
    elif all_players_data:
        return {
            "status": "success",
            "players_found": True,
            "message": "Player scan completed and data saved.",
        }
    else:
        return {
            "status": "success",
            "players_found": False,
            "message": "Player scan completed, no new player data found.",
        }


def add_players(players: List[str], config_dir: Optional[str] = None) -> Dict[str, str]:
    """
    Adds player information (name and XUID) to the central `players.json` file.

    Parses player strings, merges with existing data, and saves back to the file.

    Args:
        players: A list of player strings, each formatted as "PlayerName:PlayerXUID".
        config_dir: Optional. The directory where `players.json` resides. Uses the
                    main application config directory if None.

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "message": "Players added successfully."}
        - {"status": "error", "message": "Error description..."}

    Raises:
        TypeError: If `players` argument is not a list.
        MissingArgumentError: If `players` list is empty.
        FileOperationError: If `config_dir` cannot be determined.
    """
    if not isinstance(players, list):
        raise TypeError("Input 'players' must be a list of strings.")
    if not players:
        raise MissingArgumentError("Player list cannot be empty.")

    logger.info(f"Attempting to add {len(players)} player(s) to players.json.")
    logger.debug(f"Input players: {players}")

    try:
        effective_config_dir = (
            config_dir
            if config_dir is not None
            else getattr(settings, "_config_dir", None)
        )
        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory is not set or available."
            )

        # Join the list into a single comma-separated string for the core parser
        player_string = ",".join(players)

        # Call core functions to parse and save
        # parse_player_argument raises InvalidInputError on format issues
        player_list = player_base.parse_player_argument(player_string)
        # save_players_to_json raises FileOperationError, InvalidInputError
        player_base.save_players_to_json(player_list, effective_config_dir)

        logger.info(
            f"Successfully added/updated {len(player_list)} players in '{effective_config_dir}/players.json'."
        )
        return {"status": "success", "message": "Players added successfully."}

    except (InvalidInputError, FileOperationError) as e:
        # Catch specific errors from core functions
        logger.error(f"Failed to add players: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to add players: {e}"}
    except ValueError as e:
        # Might be raised by parse_player_argument indirectly in some cases
        logger.error(f"Invalid player data format provided: {e}", exc_info=True)
        return {"status": "error", "message": f"Invalid player data format: {e}"}
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while adding players: {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def get_players_from_json(config_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves the list of all known players from the `players.json` file.

    Args:
        config_dir: Optional. The directory where `players.json` resides. Uses the
                    main application config directory if None.

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "players": List[Dict[str, str]]} on success.
        - {"status": "error", "message": str} if the file is not found, cannot be read,
          or has invalid format.

    Raises:
        FileOperationError: If `config_dir` cannot be determined.
    """
    logger.debug("Attempting to retrieve players from players.json...")

    try:
        effective_config_dir = (
            config_dir
            if config_dir is not None
            else getattr(settings, "_config_dir", None)
        )
        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory is not set or available."
            )

        players_file_path = os.path.join(effective_config_dir, "players.json")
        logger.debug(f"Reading players file: {players_file_path}")

        if not os.path.isfile(players_file_path):  # Check if it's a file
            logger.warning(
                f"Player data file 'players.json' not found at: {players_file_path}"
            )
            # Return success but indicate no players found due to missing file
            return {
                "status": "success",
                "players": [],
                "message": "Player file not found.",
            }

        try:
            with open(players_file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    logger.info("Player data file 'players.json' is empty.")
                    return {"status": "success", "players": []}

                players_data = json.loads(content)

            # Validate the structure: expecting {"players": [...]}
            if (
                isinstance(players_data, dict)
                and "players" in players_data
                and isinstance(players_data["players"], list)
            ):
                player_list = players_data["players"]
                # Optional: Further validate each item in the list?
                logger.debug(
                    f"Successfully loaded {len(player_list)} players from 'players.json'."
                )
                return {"status": "success", "players": player_list}
            else:
                error_msg = f"Invalid format in 'players.json'. Expected JSON object with a 'players' list."
                logger.error(error_msg)
                return {"status": "error", "message": error_msg}

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON from 'players.json': {e}", exc_info=True
            )
            return {"status": "error", "message": f"Invalid JSON in players.json: {e}"}
        except OSError as e:
            logger.error(f"Failed to read 'players.json' file: {e}", exc_info=True)
            return {"status": "error", "message": f"Could not read players file: {e}"}

    except FileOperationError as e:  # Catch config dir error
        logger.error(f"Cannot get players: {e}", exc_info=True)
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while retrieving players: {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
