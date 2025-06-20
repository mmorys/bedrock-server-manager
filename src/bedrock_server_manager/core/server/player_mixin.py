# bedrock_server_manager/core/server/player_mixin.py
"""Provides the ServerPlayerMixin for the BedrockServer class.

This mixin is responsible for scanning a server's log files to identify and
extract player connection information, specifically player gamertags and their
corresponding XUIDs.
"""
import os
import re
import logging
from typing import List, Dict, TYPE_CHECKING

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import FileOperationError

if TYPE_CHECKING:
    pass


class ServerPlayerMixin(BedrockServerBaseMixin):
    """A mixin for BedrockServer that provides methods for player discovery.

    This class contains the logic for scanning server logs to find player
    connection entries, which is a primary method for populating the central
    player database.
    """

    def __init__(self, *args, **kwargs):
        """Initializes the ServerPlayerMixin.

        This constructor calls `super().__init__` to ensure proper method
        resolution order in the context of multiple inheritance. It relies on
        attributes (like `server_name`, `server_log_path`, `logger`) being
        available from the base class.
        """
        super().__init__(*args, **kwargs)
        # self.server_name, self.server_log_path, and self.logger are available from BaseMixin.

    def scan_log_for_players(self) -> List[Dict[str, str]]:
        """Scans the server's log file for player connection entries.

        This method reads the server's primary output log file line by line,
        searching for the standard "Player connected" message to extract
        gamertags and XUIDs.

        Returns:
            A list of unique player dictionaries found in the log. Each
            dictionary contains 'name' and 'xuid' keys. An empty list is
            returned if the log file doesn't exist or no players are found.

        Raises:
            FileOperationError: If there is an OS-level error reading the log file.
        """
        log_file = self.server_log_path  # This property is from BaseMixin.
        self.logger.debug(
            f"Server '{self.server_name}': Scanning log file for players: {log_file}"
        )

        if not os.path.isfile(log_file):
            self.logger.warning(
                f"Log file not found or is not a file: {log_file} for server '{self.server_name}'."
            )
            return []

        players_data: List[Dict[str, str]] = []
        # Use a set to track XUIDs and ensure each player is only added once per scan.
        unique_xuids = set()

        try:
            # Open the log file with error handling for encoding issues.
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                for line_number, line_content in enumerate(f, 1):
                    # Regex to find the "Player connected" line and capture name and XUID.
                    match = re.search(
                        r"Player connected:\s*([^,]+),\s*xuid:\s*(\d+)",
                        line_content,
                        re.IGNORECASE,
                    )
                    if match:
                        player_name, xuid = (
                            match.group(1).strip(),
                            match.group(2).strip(),
                        )
                        # Only add the player if they haven't been found in this scan yet.
                        if xuid not in unique_xuids:
                            players_data.append({"name": player_name, "xuid": xuid})
                            unique_xuids.add(xuid)
                            self.logger.debug(
                                f"Found player in log: Name='{player_name}', XUID='{xuid}'"
                            )
        except OSError as e:
            self.logger.error(
                f"Error reading log file '{log_file}' for server '{self.server_name}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Error reading log file '{log_file}' for server '{self.server_name}': {e}"
            ) from e

        num_found = len(players_data)
        if num_found > 0:
            self.logger.info(
                f"Found {num_found} unique player(s) in log for server '{self.server_name}'."
            )
        else:
            self.logger.debug(
                f"No new unique players found in log for server '{self.server_name}'."
            )

        return players_data
