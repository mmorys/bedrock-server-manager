# bedrock_server_manager/cli/player.py
"""
Defines the `bsm player` command group for managing the player database.

This module provides commands to automatically discover players by scanning
server logs and to manually add or update player information, centralizing
player data for use across the application.
"""

import logging
from typing import Tuple

import click

from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


@click.group()
def player():
    """Manages the central player database.

    This command group contains utilities for populating the player database,
    which links player names (gamertags) to their unique Xbox User IDs (XUIDs).
    """
    pass


@player.command("scan")
def scan_for_players():
    """Scans server logs to discover and update players.

    This command iterates through the log files of all configured servers,
    searching for player connection events. It automatically extracts player

    names and their XUIDs, adding new players to the database and
    updating existing ones.

    Raises:
        click.Abort: If a BSMError or an unexpected error occurs during the scan.
    """
    try:
        click.echo("Scanning all server logs for player data...")
        logger.debug("CLI: Calling player_api.scan_and_update_player_db_api")

        response = player_api.scan_and_update_player_db_api()
        _handle_api_response(response, "Player database updated successfully.")

    except BSMError as e:
        click.secho(f"An error occurred during scan: {e}", fg="red")
        raise click.Abort()
    except Exception as e:
        # Catch any other unexpected errors during file I/O or processing.
        click.secho(f"An unexpected error occurred: {e}", fg="red")
        raise click.Abort()


@player.command("add")
@click.option(
    "-p",
    "--player",
    "players",
    multiple=True,
    required=True,
    help="Player to add in 'Gamertag:XUID' format. Use multiple times for multiple players.",
)
def add_players(players: Tuple[str]):
    """Manually adds or updates players in the database.

    Allows for the manual addition of one or more players using the
    'Gamertag:XUID' format. If a player with the same name or XUID already
    exists, their information will be updated. Use the --player option
    multiple times to add several players at once.

    Args:
        players: A tuple of player strings, each in 'Gamertag:XUID' format.

    Raises:
        click.Abort: If a BSMError or an unexpected error occurs.
    """
    try:
        # The API expects a list, so we convert the tuple from `multiple=True`.
        player_list = list(players)
        click.echo(f"Adding/updating {len(player_list)} player(s) in the database...")
        logger.debug(
            f"CLI: Calling player_api.add_players_manually_api with {len(player_list)} players."
        )

        response = player_api.add_players_manually_api(player_list)
        _handle_api_response(response, "Players added/updated successfully.")

    except BSMError as e:
        click.secho(f"An error occurred while adding players: {e}", fg="red")
        raise click.Abort()
    except Exception as e:
        click.secho(f"An unexpected error occurred: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    player()
