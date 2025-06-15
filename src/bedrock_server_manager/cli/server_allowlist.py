# bedrock_server_manager/cli/server_allowlist.py
"""
Defines the `bsm allowlist` command group for managing server access.

This module provides a command group for viewing and modifying a server's
`allowlist.json` file. It includes a reusable interactive workflow for
guided editing and direct commands for scriptable changes.
"""

from typing import Tuple

import click
import questionary

from bedrock_server_manager.api import server_install_config as config_api
from bedrock_server_manager.cli.utils import (
    handle_api_response as _handle_api_response,
)
from bedrock_server_manager.error import BSMError


def interactive_allowlist_workflow(server_name: str):
    """Guides the user through an interactive session to edit the allowlist.

    This function fetches the current allowlist, displays it, and then enters
    a loop to prompt the user for new players to add.

    Args:
        server_name: The name of the server whose allowlist is being edited.

    Raises:
        click.Abort: If the user cancels the operation.
    """
    response = config_api.get_server_allowlist_api(server_name)
    existing_players = response.get("players", [])

    click.secho("\n--- Interactive Allowlist Configuration ---", bold=True)
    if existing_players:
        click.echo("Current players in allowlist:")
        for p in existing_players:
            limit_str = (
                click.style(" (Ignores Limit)", fg="yellow")
                if p.get("ignoresPlayerLimit")
                else ""
            )
            click.echo(f"  - {p.get('name')}{limit_str}")
    else:
        click.secho("Allowlist is currently empty.", fg="yellow")

    new_players_to_add = []
    click.echo("\nEnter new players to add. Press Enter on an empty line to finish.")
    while True:
        player_name = questionary.text("Player gamertag:").ask()
        if not player_name or not player_name.strip():
            break

        # Check for duplicates before adding
        if any(
            p["name"].lower() == player_name.lower()
            for p in existing_players + new_players_to_add
        ):
            click.secho(
                f"Player '{player_name}' is already in the list. Skipping.", fg="yellow"
            )
            continue

        ignore_limit = questionary.confirm(
            f"Should '{player_name}' ignore the player limit?", default=False
        ).ask()
        new_players_to_add.append(
            {"name": player_name.strip(), "ignoresPlayerLimit": ignore_limit}
        )

    if new_players_to_add:
        click.echo("Updating allowlist with new players...")
        save_response = config_api.add_players_to_allowlist_api(
            server_name, new_players_to_add
        )
        _handle_api_response(save_response, "Allowlist updated successfully.")
    else:
        click.secho("No new players were added.", fg="cyan")


@click.group()
def allowlist():
    """Manages a server's allowlist to control player access."""
    pass


@allowlist.command("add")
@click.option(
    "-s", "--server", "server_name", required=True, help="The name of the server."
)
@click.option(
    "-p",
    "--player",
    "players",
    multiple=True,
    help="Gamertag of the player to add. Use multiple times for multiple players.",
)
@click.option(
    "--ignore-limit",
    is_flag=True,
    help="Allow player(s) to join even if the server is full.",
)
def add(server_name: str, players: Tuple[str], ignore_limit: bool):
    """Adds players to the allowlist.

    If run without the --player option, this command launches an interactive
    wizard to view and add multiple players. If --player is used, it adds
    the specified player(s) directly.

    Args:
        server_name: The name of the target server.
        players: A tuple of player gamertags to add.
        ignore_limit: If True, applies the 'ignoresPlayerLimit' flag to all added players.
    """
    try:
        if not players:
            click.secho(
                f"No player specified; starting interactive editor for '{server_name}'...",
                fg="yellow",
            )
            interactive_allowlist_workflow(server_name)
            return

        # Direct, non-interactive logic
        player_data_list = [
            {"name": p_name, "ignoresPlayerLimit": ignore_limit} for p_name in players
        ]

        click.echo(
            f"Adding {len(player_data_list)} player(s) to allowlist for server '{server_name}'..."
        )
        response = config_api.add_players_to_allowlist_api(
            server_name, player_data_list
        )

        added_count = response.get("data", {}).get("added_count", 0)
        _handle_api_response(
            response,
            f"Successfully added {added_count} new player(s) to the allowlist.",
        )

    except (click.Abort, KeyboardInterrupt, BSMError):
        # Catch BSMError here as well to provide a consistent cancel message if it aborts.
        click.secho("\nOperation cancelled.", fg="yellow")


@allowlist.command("remove")
@click.option(
    "-s", "--server", "server_name", required=True, help="The name of the server."
)
@click.option(
    "-p",
    "--player",
    "players",
    multiple=True,
    required=True,
    help="Gamertag of the player to remove. Use multiple times for multiple players.",
)
def remove(server_name: str, players: Tuple[str]):
    """Removes one or more players from the allowlist."""
    player_list = list(players)
    click.echo(
        f"Removing {len(player_list)} player(s) from '{server_name}' allowlist..."
    )
    response = config_api.remove_players_from_allowlist_api(server_name, player_list)

    # Use the handler for errors, but provide custom output for success
    if response.get("status") == "error":
        _handle_api_response(response, "")  # Will print the error and abort
        return

    click.secho(response.get("message", "Request processed."), fg="cyan")
    details = response.get("data", {})
    removed = details.get("removed", [])
    not_found = details.get("not_found", [])

    if removed:
        click.secho(f"\nSuccessfully removed {len(removed)} player(s):", fg="green")
        for p in removed:
            click.echo(f"  - {p}")
    if not_found:
        click.secho(
            f"\n{len(not_found)} player(s) not found in allowlist:", fg="yellow"
        )
        for p in not_found:
            click.echo(f"  - {p}")


@allowlist.command("list")
@click.option(
    "-s", "--server", "server_name", required=True, help="The name of the server."
)
def list_players(server_name: str):
    """Lists all players on a server's allowlist."""
    response = config_api.get_server_allowlist_api(server_name)

    # Handle API errors first
    if response.get("status") == "error":
        _handle_api_response(response, "")
        return

    players = response.get("data", {}).get("players", [])

    if not players:
        click.secho(f"The allowlist for server '{server_name}' is empty.", fg="yellow")
        return

    click.secho(f"\nAllowlist for '{server_name}':", bold=True)
    for p in players:
        limit_str = (
            click.style(" (Ignores Player Limit)", fg="yellow")
            if p.get("ignoresPlayerLimit")
            else ""
        )
        click.echo(f"  - {p.get('name')}{limit_str}")
