# bedrock-server-manager/bedrock_server_manager/core/player/player.py
"""
Manages player information for the Bedrock server.

Provides functions to parse player arguments, scan server logs for player
connection details (name and XUID), and save/update this information
persistently in a JSON file.
"""

import re
import os
import json
import logging
from typing import List, Dict

# Local imports
from bedrock_server_manager.error import FileOperationError, InvalidInputError

logger = logging.getLogger("bedrock_server_manager")


def parse_player_argument(player_string: str) -> List[Dict[str, str]]:
    """
    Parses a command-line style player string into a list of player dictionaries.

    The expected format is "playername1:xuid1,playername2:xuid2,...".

    Args:
        player_string: The comma-separated string containing player name:XUID pairs.

    Returns:
        A list of dictionaries, where each dictionary has 'name' and 'xuid' keys.

    Raises:
        InvalidInputError: If the input string or any player pair within it
                           does not conform to the expected "name:xuid" format.
    """
    if not player_string or not isinstance(player_string, str):
        logger.warning("Received empty or invalid player string for parsing.")
        return []  # Return empty list for empty/invalid input

    logger.debug(f"Attempting to parse player argument string: '{player_string}'")
    player_list: List[Dict[str, str]] = []
    # Split by comma, handling potential whitespace around commas
    player_pairs = [pair.strip() for pair in player_string.split(",") if pair.strip()]

    for pair in player_pairs:
        # Split by colon, expect exactly two parts
        player_data = pair.split(":", 1)  # Split only on the first colon
        if len(player_data) != 2:
            error_msg = f"Invalid player data format in argument: '{pair}'. Expected 'name:xuid'."
            logger.error(error_msg)
            raise InvalidInputError(error_msg)

        player_name = player_data[0].strip()
        player_id = player_data[1].strip()

        if not player_name or not player_id:
            error_msg = f"Invalid player data in argument: '{pair}'. Name and XUID cannot be empty."
            logger.error(error_msg)
            raise InvalidInputError(error_msg)

        player_list.append({"name": player_name, "xuid": player_id})

    logger.debug(f"Successfully parsed player argument into list: {player_list}")
    return player_list


def scan_log_for_players(log_file: str) -> List[Dict[str, str]]:
    """
    Scans a server log file for player connection messages and extracts player data.

    Looks for lines matching the pattern "Player connected: <name>, xuid: <xuid>".

    Args:
        log_file: The absolute path to the server's output log file (e.g., server_output.txt).

    Returns:
        A list of dictionaries, each containing 'name' and 'xuid' for players
        found in the log file. Returns an empty list if the file doesn't exist,
        cannot be read, or contains no matching entries.

    Raises:
        FileOperationError: If an OSError occurs during file reading (excluding FileNotFoundError).
    """
    logger.debug(f"Scanning log file for player connection entries: {log_file}")
    players_data: List[Dict[str, str]] = []
    unique_xuids = set()  # Keep track of XUIDs found to avoid duplicates in the result

    if not os.path.exists(log_file):
        logger.warning(f"Log file not found at '{log_file}'. Cannot scan for players.")
        return []  # Return empty list if log file doesn't exist

    try:
        # Use utf-8 encoding, ignore errors for potential malformed lines
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            line_count = 0
            found_count = 0
            for line in f:
                line_count += 1
                # Regex: Find "Player connected:", capture name (non-comma chars), find "xuid:", capture digits
                match = re.search(
                    r"Player connected:\s*([^,]+),\s*xuid:\s*(\d+)", line, re.IGNORECASE
                )
                if match:
                    player_name = match.group(1).strip()
                    xuid = match.group(2).strip()
                    # Only add if XUID hasn't been seen before in this scan
                    if xuid not in unique_xuids:
                        logger.debug(
                            f"Found player connection in log: Name='{player_name}', XUID='{xuid}'"
                        )
                        players_data.append({"name": player_name, "xuid": xuid})
                        unique_xuids.add(xuid)
                        found_count += 1
                    else:
                        logger.info(
                            f"Duplicate XUID '{xuid}' found for player '{player_name}'. Skipping."
                        )

            logger.debug(
                f"Finished scanning {line_count} lines in '{log_file}'. Found {found_count} unique player entries."
            )

    except OSError as e:
        logger.error(f"Error reading log file '{log_file}': {e}", exc_info=True)
        # Re-raise as a custom error for consistent handling upstream
        raise FileOperationError(f"Error reading log file '{log_file}': {e}") from e
    except Exception as e:
        # Catch any other unexpected exceptions during processing
        logger.error(
            f"Unexpected error scanning log file '{log_file}': {e}", exc_info=True
        )
        # Depending on desired behavior, could return empty list or raise error
        raise FileOperationError(
            f"Unexpected error scanning log '{log_file}': {e}"
        ) from e

    if not players_data:
        logger.info(f"No player connection entries found in log file: {log_file}")

    return players_data


def save_players_to_json(players_data: List[Dict[str, str]], config_dir: str) -> None:
    """
    Saves or updates player data (name and XUID) to a 'players.json' file.

    Loads existing data from 'players.json' in the specified config directory,
    merges the provided `players_data` (using XUID as the unique key),
    and writes the updated list back to the file. Creates the file if it doesn't exist.

    Args:
        players_data: A list of player dictionaries. Each dictionary must contain
                      'name' (str) and 'xuid' (str) keys.
        config_dir: The directory path where 'players.json' should be saved.

    Raises:
        InvalidInputError: If `players_data` is not a list of dictionaries, or if
                           any dictionary within the list lacks 'name' or 'xuid' keys,
                           or if their values are not strings.
        FileOperationError: If there's an OS error creating the directory, or reading/writing
                            the 'players.json' file, or if JSON decoding fails on load.
    """
    if not config_dir:
        raise InvalidInputError(
            "Configuration directory cannot be empty for saving players."
        )

    logger.debug(
        f"Attempting to save/update players data to '{config_dir}/players.json'."
    )
    logger.debug(f"Incoming players data: {players_data}")
    players_file = os.path.join(config_dir, "players.json")

    # Ensure the config directory exists
    try:
        os.makedirs(config_dir, exist_ok=True)
        logger.debug(f"Ensured configuration directory exists: {config_dir}")
    except OSError as e:
        logger.error(
            f"Failed to create configuration directory '{config_dir}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to create config directory '{config_dir}': {e}"
        ) from e

    # --- Input Validation ---
    if not isinstance(players_data, list):
        raise InvalidInputError(
            f"Invalid input: players_data must be a list, got {type(players_data)}."
        )

    validated_players_input = []
    for idx, player in enumerate(players_data):
        if not isinstance(player, dict):
            raise InvalidInputError(
                f"Invalid input: Item at index {idx} is not a dictionary: {player}"
            )
        if (
            "name" not in player
            or not isinstance(player.get("name"), str)
            or not player.get("name")
        ):
            raise InvalidInputError(
                f"Invalid input: Item at index {idx} missing or invalid 'name': {player}"
            )
        if (
            "xuid" not in player
            or not isinstance(player.get("xuid"), str)
            or not player.get("xuid")
        ):
            raise InvalidInputError(
                f"Invalid input: Item at index {idx} missing or invalid 'xuid': {player}"
            )
        validated_players_input.append(player)
    # --- End Input Validation ---

    try:
        # 1. Load Existing Data (if any)
        existing_players: Dict[str, Dict[str, str]] = (
            {}
        )  # Use XUID as key for easy merging
        if os.path.exists(players_file):
            logger.debug(
                f"Found existing players file: {players_file}. Attempting to load."
            )
            try:
                with open(players_file, "r", encoding="utf-8") as f:
                    # Load entire structure, expecting {'players': [...]}
                    loaded_json = json.load(f)
                    if (
                        isinstance(loaded_json, dict)
                        and "players" in loaded_json
                        and isinstance(loaded_json["players"], list)
                    ):
                        # Convert list to dict keyed by XUID
                        for player_entry in loaded_json["players"]:
                            if (
                                isinstance(player_entry, dict)
                                and "xuid" in player_entry
                            ):
                                existing_players[player_entry["xuid"]] = player_entry
                            else:
                                logger.warning(
                                    f"Skipping invalid entry in existing players.json: {player_entry}"
                                )
                        logger.debug(
                            f"Successfully loaded and parsed {len(existing_players)} existing players from file."
                        )
                    else:
                        logger.warning(
                            f"Existing players.json has unexpected structure: {loaded_json}. Starting fresh."
                        )
                        existing_players = {}  # Treat as empty if structure is wrong

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse existing players.json (invalid JSON): {e}. Will overwrite.",
                    exc_info=True,
                )
                existing_players = {}  # Start fresh if JSON is invalid
            except OSError as e:
                logger.error(
                    f"Failed to read existing players file '{players_file}': {e}. Cannot merge.",
                    exc_info=True,
                )
                raise FileOperationError(
                    f"Failed to read existing players file '{players_file}': {e}"
                ) from e
        else:
            logger.debug(
                f"No existing players file found at '{players_file}'. Will create new file."
            )

        # 2. Merge New Data with Existing Data
        # Iterate through the validated input data
        updated_count = 0
        added_count = 0
        for player in validated_players_input:
            xuid = player["xuid"]
            if xuid in existing_players:
                # Update existing entry if name differs
                if existing_players[xuid] != player:
                    logger.debug(
                        f"Updating player data for XUID {xuid}: {existing_players[xuid]} -> {player}"
                    )
                    existing_players[xuid] = player
                    updated_count += 1
            else:
                # Add new player
                logger.debug(f"Adding new player with XUID {xuid}: {player}")
                existing_players[xuid] = player
                added_count += 1

        if updated_count > 0 or added_count > 0:
            logger.info(
                f"Player data merged: {added_count} added, {updated_count} updated."
            )
        else:
            logger.debug("No new players added or existing players updated.")

        # 3. Convert back to a list for JSON serialization
        updated_players_list = list(existing_players.values())
        updated_players_list.sort(key=lambda p: p.get("name", "").lower())

        # 4. Write Updated Data to File
        logger.debug(
            f"Writing {len(updated_players_list)} players to '{players_file}'."
        )
        try:
            with open(players_file, "w", encoding="utf-8") as f:
                # Store under a 'players' key for structure
                json.dump({"players": updated_players_list}, f, indent=4)
            logger.debug(f"Successfully saved players data to: {players_file}")
        except OSError as e:
            logger.error(
                f"Failed to write players data to '{players_file}': {e}", exc_info=True
            )
            raise FileOperationError(
                f"Failed to write players data to '{players_file}': {e}"
            ) from e

    except (InvalidInputError, FileOperationError):
        # Re-raise specific errors already handled
        raise
    except Exception as e:
        # Catch any other unexpected errors during the process
        logger.error(
            f"An unexpected error occurred while saving players to JSON: {e}",
            exc_info=True,
        )
        raise FileOperationError(f"Unexpected error saving players: {e}") from e
