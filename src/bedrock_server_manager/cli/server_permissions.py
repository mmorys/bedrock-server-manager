# bedrock_server_manager/cli/commands/server_permissions.py
from typing import Optional
import click
import questionary

from bedrock_server_manager.api import server_install_config as config_api
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.cli.utils import (
    handle_api_response,
)


def interactive_permissions_workflow(server_name: str):
    """Manages the interactive workflow for setting player permissions."""
    click.secho("--- Configure Player Permissions ---", bold=True)
    player_response = player_api.get_all_known_players_api()

    if not player_response.get("players"):
        click.secho(
            "No players found in the global database (players.json).", fg="yellow"
        )
        click.secho("Run 'bsm player scan' or 'bsm player add' first.", fg="cyan")
        return

    player_map = {
        f"{p['name']} (XUID: {p['xuid']})": p for p in player_response["players"]
    }
    player_choice_str = questionary.select(
        "Select a player to configure:", choices=list(player_map.keys()) + ["Cancel"]
    ).ask()

    if not player_choice_str or player_choice_str == "Cancel":
        raise click.Abort()

    selected_player = player_map[player_choice_str]
    permission = questionary.select(
        f"Select permission for {selected_player['name']}:",
        choices=["member", "operator", "visitor"],
        default="member",
    ).ask()

    if permission is None:
        raise click.Abort()

    perm_response = config_api.configure_player_permission(
        server_name, selected_player["xuid"], selected_player["name"], permission
    )
    handle_api_response(
        perm_response,
        f"Permission for {selected_player['name']} set to '{permission}'.",
    )


@click.group()
def permissions():
    """
    View and manage player permissions.
    Use 'set' without options for an interactive wizard.
    """
    pass


@permissions.command("set")
@click.option("-s", "--server-name", "server_name", required=True, help="The name of the server.")
@click.option(
    "-p", "--player", help="The gamertag of the player. Skips interactive mode."
)
@click.option(
    "-l",
    "--level",
    type=click.Choice(["visitor", "member", "operator"], case_sensitive=False),
    help="The permission level to grant. Skips interactive mode.",
)
def set_perm(server_name: str, player: Optional[str], level: Optional[str]):
    """
    Sets a permission level for a player.

    If --player and --level are provided, sets the permission directly.
    If either is omitted, an interactive wizard is launched.
    """
    try:
        # "Smart" logic: if key optional arguments are missing, go interactive.
        if not player or not level:
            click.secho(
                f"Player or level not specified. Starting interactive permission editor for '{server_name}'...",
                fg="yellow",
            )
            interactive_permissions_workflow(server_name)
            return

        # Direct, non-interactive logic
        click.echo(f"Finding player '{player}' in global database...")
        all_players_resp = player_api.get_all_known_players_api()
        player_data = next(
            (
                p
                for p in all_players_resp.get("players", [])
                if p.get("name", "").lower() == player.lower()
            ),
            None,
        )

        if not player_data or not player_data.get("xuid"):
            click.secho(
                f"Error: Player '{player}' not found in global players list.", fg="red"
            )
            click.secho("Run 'bsm player add' or 'bsm player scan' first.", fg="cyan")
            raise click.Abort()

        xuid = player_data["xuid"]
        click.echo(f"Setting permission for {player} (XUID: {xuid}) to '{level}'...")
        response = config_api.configure_player_permission(
            server_name, xuid, player, level
        )
        handle_api_response(response, "Permission updated successfully.")

    except (click.Abort, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")


@permissions.command("list")
@click.option("-s", "--server-name", "server_name", required=True, help="The name of the server.")
def list_perms(server_name: str):
    """Lists all configured player permissions for a server."""
    response = config_api.get_server_permissions_api(server_name)
    data_wrapper = handle_api_response(response, "Fetched permissions.")
    permissions = data_wrapper.get("data", {}).get("permissions", [])

    if not permissions:
        click.secho(
            f"No permissions file found or it is empty for '{server_name}'.",
            fg="yellow",
        )
        return

    click.secho(f"Permissions for '{server_name}':", bold=True)
    for p in permissions:
        click.echo(
            f" - {p.get('name', 'Unknown Player')} (XUID: {p['xuid']}): {p['permission']}"
        )
