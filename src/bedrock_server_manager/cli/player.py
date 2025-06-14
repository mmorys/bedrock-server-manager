# bedrock_server_manager/cli/player.py
"""
Click command group for managing player data.

Provides commands to scan server logs for players and to add them manually.
"""

import logging
from typing import Dict, Any, Tuple

import click

from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


# A helper to reduce code duplication in API response handling
def _handle_api_response(response: Dict[str, Any], success_msg: str):
    """Prints styled success or error message based on API response."""
    if response.get("status") == "error":
        message = response.get("message", "An unknown error occurred.")
        click.secho(f"Error: {message}", fg="red")
        raise click.Abort()
    else:
        # Use the specific message from the API if it exists, otherwise use the default
        message = response.get("message", success_msg)
        # Style message differently if nothing happened vs. a successful change
        if response.get("players_found") or response.get("status") == "success":
            click.secho(f"Success: {message}", fg="green")
        else:  # e.g., scan complete, no new players found
            click.secho(f"Info: {message}", fg="cyan")


@click.group()
def player():
    """Commands for managing the central player database."""
    pass


@player.command("scan")
def scan_for_players():
    """Scans all server logs for players and updates the database."""
    try:
        click.echo("Scanning server logs for player data...")
        logger.debug("CLI: Calling player_api.scan_and_update_player_db_api")

        response = player_api.scan_and_update_player_db_api()

        success_message = "Player database updated successfully."
        _handle_api_response(response, success_message)

    except BSMError as e:
        click.secho(f"A configuration or directory error occurred: {e}", fg="red")
        raise click.Abort()
    except Exception as e:
        click.secho(f"An unexpected error occurred during the scan: {e}", fg="red")
        raise click.Abort()


@player.command("add")
@click.option(
    "-p",
    "--player",
    "players",
    multiple=True,
    required=True,
    help="Player in 'PlayerName:XUID' format. Use this option multiple times for multiple players.",
)
def add_players(players: Tuple[str]):
    """Manually adds one or more players to the player database."""
    try:
        player_list = list(players)  # The API expects a list, not a tuple
        click.echo(f"Adding {len(player_list)} player(s) to the database...")
        logger.debug(
            f"CLI: Calling player_api.add_players_manually_api with {player_list}"
        )

        response = player_api.add_players_manually_api(player_list)

        success_message = "Players added/updated successfully."
        _handle_api_response(response, success_message)

    except BSMError as e:
        click.secho(f"An error occurred while adding players: {e}", fg="red")
        raise click.Abort()
    except Exception as e:
        click.secho(f"An unexpected error occurred: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    player()
