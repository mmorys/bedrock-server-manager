# bedrock_server_manager/core/server/player_mixin.py
"""
Provides the ServerPlayerMixin class for BedrockServer.

This mixin is responsible for scanning server logs to identify player
connections, extracting player names and XUIDs.
"""
import os
import re
import logging  # self.logger from BaseMixin
from typing import List, Dict, TYPE_CHECKING

# Local imports
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import FileOperationError

if TYPE_CHECKING:
    pass


class ServerPlayerMixin(BedrockServerBaseMixin):
    """
    A mixin for the BedrockServer class that provides methods for
    scanning server logs to discover player connection information.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the ServerPlayerMixin.

        Calls super().__init__ for proper multiple inheritance setup.
        Relies on attributes (like server_name, server_log_path, logger)
        from the base class.
        """
        super().__init__(*args, **kwargs)
        # self.server_name, self.server_log_path, self.logger are available

    def scan_log_for_players(self) -> List[Dict[str, str]]:
        """
        Scans this server's primary log file (e.g., server_output.txt) for player connection entries.
        Returns a list of unique players found (name and XUID).
        """
        log_file = self.server_log_path  # From BaseMixin
        self.logger.debug(
            f"Server '{self.server_name}': Scanning log file for players: {log_file}"
        )

        if not os.path.isfile(log_file):  # Check if it's a file
            self.logger.warning(
                f"Log file not found or not a file: {log_file} for server '{self.server_name}'."
            )
            return []

        players_data: List[Dict[str, str]] = []
        unique_xuids = (
            set()
        )  # To store XUIDs and ensure uniqueness of players returned by this scan

        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                for line_number, line_content in enumerate(f, 1):
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
