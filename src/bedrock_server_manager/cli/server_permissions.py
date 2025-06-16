# bedrock_server_manager/cli/server_permissions.py
"""
Defines the `bsm permissions` command group for managing player roles.

This module provides commands to view and set player permission levels
(e.g., member, operator) on a specific server. It integrates with the
global player database to link gamertags to XUIDs.
"""
from typing import Optional

import click
import questionary

from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.api import server_install_config as config_api
from bedrock_server_manager.cli.utils import (
    handle_api_response as _handle_api_response,
)
from bedrock_server_manager.error import BSMError


def interactive_permissions_workflow(server_name: str):
    """Guides the user through setting a player's permission level.

    This interactive workflow fetches all known players, prompts the user to
    select one, and then prompts for the desired permission level before
    calling the API to apply the change.

    Args:
        server_name: The name of the server to configure.

    Raises:
        click.Abort: If the user cancels the operation at any prompt.
    """
    click.secho("\n--- Interactive Permission Configuration ---", bold=True)
    player_response = player_api.get_all_known_players_api()
    all_players = player_response.get("players", [])

    if not all_players:
        click.secho(
            "No players found in the global player database (players.json).",
            fg="yellow",
        )
        click.secho(
            "Run 'bsm player scan' or 'bsm player add' to populate it first.", fg="cyan"
        )
        return

    # Create a user-friendly mapping for the selection prompt
    player_map = {f"{p['name']} (XUID: {p['xuid']})": p for p in all_players}
    choices = sorted(list(player_map.keys())) + ["Cancel"]

    player_choice_str = questionary.select(
        "Select a player to configure permissions for:", choices=choices
    ).ask()

    if not player_choice_str or player_choice_str == "Cancel":
        raise click.Abort()

    selected_player = player_map[player_choice_str]
    permission = questionary.select(
        f"Select permission level for {selected_player['name']}:",
        choices=["member", "operator", "visitor"],
        default="member",
    ).ask()

    if permission is None:  # User pressed Ctrl+C
        raise click.Abort()

    perm_response = config_api.configure_player_permission(
        server_name, selected_player["xuid"], selected_player["name"], permission
    )
    _handle_api_response(
        perm_response,
        f"Permission for {selected_player['name']} set to '{permission}'.",
    )


@click.group()
def permissions():
    """Manages player permission levels on a server."""
    pass


@permissions.command("set")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="The name of the target server.",
)
@click.option(
    "-p",
    "--player",
    "player_name",
    help="The gamertag of the player. Skips interactive mode.",
)
@click.option(
    "-l",
    "--level",
    type=click.Choice(["visitor", "member", "operator"], case_sensitive=False),
    help="The permission level to grant. Skips interactive mode.",
)
def set_perm(server_name: str, player_name: Optional[str], level: Optional[str]):
    """Sets a permission level for a player on a specific server.

    If run without the --player and --level options, this command launches
    an interactive wizard. Otherwise, it sets the permission directly.

    Args:
        server_name: The name of the server to configure.
        player_name: The gamertag of the player.
        level: The permission level to set ('visitor', 'member', or 'operator').
    """
    try:
        if not player_name or not level:
            click.secho(
                f"Player or level not specified; starting interactive editor for '{server_name}'...",
                fg="yellow",
            )
            interactive_permissions_workflow(server_name)
            return

        # Direct, non-interactive logic
        click.echo(f"Finding player '{player_name}' in global database...")
        all_players_resp = player_api.get_all_known_players_api()
        player_data = next(
            (
                p
                for p in all_players_resp.get("players", [])
                if p.get("name", "").lower() == player_name.lower()
            ),
            None,
        )

        if not player_data or not player_data.get("xuid"):
            click.secho(
                f"Error: Player '{player_name}' not found in the global player database.",
                fg="red",
            )
            click.secho(
                "Run 'bsm player add' or 'bsm player scan' to add them first.",
                fg="cyan",
            )
            raise click.Abort()

        xuid = player_data["xuid"]
        click.echo(
            f"Setting permission for {player_name} (XUID: {xuid}) to '{level}'..."
        )
        response = config_api.configure_player_permission(
            server_name, xuid, player_name, level
        )
        _handle_api_response(response, "Permission updated successfully.")

    except (click.Abort, KeyboardInterrupt, BSMError):
        click.secho("\nOperation cancelled.", fg="yellow")


@permissions.command("list")
@click.option(
    "-s", "--server", "server_name", required=True, help="The name of the server."
)
def list_perms(server_name: str):
    """Lists all configured player permissions for a server."""
    response = config_api.get_server_permissions_api(server_name)

    # Handle API errors first
    if response.get("status") == "error":
        _handle_api_response(response, "")
        return

    permissions = response.get("data", []).get("permissions", [])

    if not permissions:
        click.secho(
            f"The permissions file for server '{server_name}' is empty or does not exist.",
            fg="yellow",
        )
        return

    click.secho(f"\nPermissions for '{server_name}':", bold=True)
    for p in permissions:
        # Use styled output for permission levels for better readability
        level = p.get(
            "permission_level", "unknown"
        ).lower()  # API used `permission_level` before, now `permission`
        level_color = {"operator": "red", "member": "green", "visitor": "blue"}.get(
            level, "white"
        )
        level_styled = click.style(level.capitalize(), fg=level_color, bold=True)

        name = p.get("name", "Unknown Player")
        xuid = p.get("xuid", "N/A")
        click.echo(f"  - {name:<20} (XUID: {xuid:<18}) {level_styled}")
