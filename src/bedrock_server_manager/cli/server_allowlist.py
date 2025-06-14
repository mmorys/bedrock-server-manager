# bedrock_server_manager/cli/server_allowlist.py
from typing import Optional
import questionary
import click

from bedrock_server_manager.api import server_install_config as config_api
from bedrock_server_manager.cli.utils import (
    handle_api_response,
)


def interactive_allowlist_workflow(server_name: str):
    """Manages the interactive workflow for configuring a server's allowlist."""
    response = config_api.get_server_allowlist_api(server_name)
    existing_players = response.get("players", [])

    click.secho("--- Configure Allowlist ---", bold=True)
    if existing_players:
        click.echo("Current players in allowlist:")
        for p in existing_players:
            click.echo(
                f"  - {p.get('name')} (Ignores Limit: {p.get('ignoresPlayerLimit')})"
            )
    else:
        click.secho("Allowlist is currently empty.", fg="yellow")

    new_players_to_add = []
    click.echo("\nEnter players to add. Press Enter on an empty line to finish.")
    while True:
        player_name = questionary.text("Enter player name:").ask()
        if not player_name or player_name.strip() == "":
            break

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
            {"name": player_name, "ignoresPlayerLimit": ignore_limit}
        )

    if new_players_to_add:
        click.echo("Adding new players to allowlist...")
        save_response = config_api.add_players_to_allowlist_api(
            server_name, new_players_to_add
        )
        handle_api_response(save_response, "Allowlist updated successfully.")
    else:
        click.secho("No new players added. Allowlist remains unchanged.", fg="cyan")


@click.group()
def allowlist():
    """
    Manages server allowlists.
    Use 'add' without options for an interactive wizard.
    """
    pass


@allowlist.command("add")
@click.option(
    "-s", "--server", "server_name", required=True, help="The name of the server."
)
@click.option(
    "-p",
    "--player",
    "player",
    multiple=True,
    help="The gamertag of the player to add. Skips interactive mode.",
)
@click.option(
    "--ignore-limit",
    is_flag=True,
    help="Player can join even if server is full (used with --player).",
)
def add(server_name: str, player: tuple[str], ignore_limit: bool):
    """
    Adds players to the allowlist.

    If --player is provided, adds a single player directly.
    If --player is omitted, an interactive wizard is launched to add multiple players.
    """
    try:
        if not player:
            click.secho(
                f"No player specified. Starting interactive allowlist editor for '{server_name}'...",
                fg="yellow",
            )
            interactive_allowlist_workflow(server_name)
            return

        # Direct, non-interactive logic
        player_data_list = [
            {"name": p_name, "ignoresPlayerLimit": ignore_limit} for p_name in player
        ]

        # 2. Provide clear user feedback about the action.
        click.echo(
            f"Adding {len(player_data_list)} player(s) to allowlist for server '{server_name}'..."
        )

        # 3. Call the API with the correctly formatted list.
        response = config_api.add_players_to_allowlist_api(
            server_name, player_data_list
        )
        if response.get("status") == "success":
            added_count = response.get("added_count", 0)
            success_msg = (
                f"Successfully added {added_count} new player(s) to the allowlist."
            )
            # The generic handler will print the success message.
            handle_api_response(response, success_msg)
        else:
            # Let the generic handler print the error message from the response.
            handle_api_response(response, "An unknown error occurred.")

    except (click.Abort, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")


@allowlist.command("remove")
@click.option(
    "-s", "--server", "server_name", required=True, help="The name of the server."
)
@click.option("-p", "--player", "player", multiple=True, required=True)
def remove(server_name: str, players: tuple[str]):
    """Removes one or more players from the allowlist."""
    click.echo(f"Removing {len(players)} player(s) from '{server_name}' allowlist...")
    response = config_api.remove_players_from_allowlist(server_name, list(players))

    if response.get("status") == "error":
        handle_api_response(response, "")  # This will print the error and abort

    click.secho(response.get("message", "Request processed."), fg="cyan")
    details = response.get("details", {})
    removed = details.get("removed", [])
    not_found = details.get("not_found", [])

    if removed:
        click.secho(f"\nSuccessfully removed {len(removed)} player(s):", fg="green")
        for p in removed:
            click.echo(f"  - {p}")
    if not_found:
        click.secho(f"\n{len(not_found)} player(s) not found:", fg="yellow")
        for p in not_found:
            click.echo(f"  - {p}")


@allowlist.command("list")
@click.option(
    "-s", "--server", "server_name", required=True, help="The name of the server."
)
def list_players(server_name: str):
    """Lists all players on a server's allowlist."""
    response = config_api.get_server_allowlist_api(server_name)
    data = handle_api_response(response, f"Fetched allowlist for '{server_name}'.")
    players = data.get("players", [])

    if not players:
        click.secho(f"Allowlist for '{server_name}' is empty.", fg="yellow")
        return

    click.secho(f"Allowlist for '{server_name}':", bold=True)
    for p in players:
        limit_str = "(Ignores Limit)" if p.get("ignoresPlayerLimit") else ""
        click.echo(f" - {p.get('name')} {limit_str}")
