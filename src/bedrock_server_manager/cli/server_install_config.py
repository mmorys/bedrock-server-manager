# bedrock_server_manager/cli/server_install_config.py
"""
Click commands for server installation and configuration workflows.

Provides interactive prompts using `questionary` to handle installing servers
and configuring their properties, allowlists, and permissions.
"""

import logging
from typing import Optional, List, Dict, Any

import click
import questionary
from questionary import Validator, ValidationError

from bedrock_server_manager.api import (
    server as server_api,
    server_install_config as config_api,
    player as player_api,
    utils as utils_api,
)
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


# --- Reusable Validators for Questionary ---


class ServerNameValidator(Validator):
    """
    Validates server name format using the `utils_api.validate_server_name_format` API endpoint.
    Ensures server names meet the required criteria (e.g., no special characters, length limits).
    """

    def validate(self, document):
        name = document.text.strip()
        response = utils_api.validate_server_name_format(name)
        if response.get("status") == "error":
            raise ValidationError(
                message=response.get("message", "Invalid server name format."),
                cursor_position=len(document.text),
            )


class PropertyValidator(Validator):
    """
    Validates a server property value using the `config_api.validate_server_property_value` API endpoint.
    Checks if the provided value is valid for the given server property (e.g., numerical ranges, specific keywords).
    """

    def __init__(self, property_name: str):
        self.property_name = property_name

    def validate(self, document):
        value = document.text.strip()
        response = config_api.validate_server_property_value(self.property_name, value)
        if response.get("status") == "error":
            raise ValidationError(
                message=response.get("message", "Invalid value."),
                cursor_position=len(document.text),
            )


# --- Private Helper Functions for Core Logic ---


def _handle_api_response(response: Dict[str, Any], success_msg: str):
    """
    Handles responses from API calls, displaying success or error messages.

    Args:
        response: The dictionary response from an API call.
        success_msg: Default message to display on success if API provides no message.

    Raises:
        click.Abort: If the API response indicates an error.
    """
    if response.get("status") == "error":
        message = response.get("message", "An unknown error occurred.")
        click.secho(f"Error: {message}", fg="red")
        raise click.Abort()
    else:
        message = response.get("message", success_msg)
        click.secho(f"Success: {message}", fg="green")


def _interactive_allowlist_config(server_name: str):
    """
    Manages the interactive workflow for configuring a server's allowlist.

    Fetches the current allowlist, prompts the user to add new players,
    and updates the allowlist via an API call.

    Args:
        server_name: The name of the server whose allowlist is being configured.
    """
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
        if not player_name:
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
        _handle_api_response(save_response, "Allowlist updated successfully.")
    else:
        click.secho("No new players added. Allowlist remains unchanged.", fg="cyan")


def _interactive_permissions_config(server_name: str):
    """
    Manages the interactive workflow for setting player permissions on a server.

    Fetches all known players, allows the user to select a player and assign
    a permission level (member, operator, visitor), then updates via API.

    Args:
        server_name: The name of the server for which permissions are being set.
    """
    click.secho("--- Configure Player Permissions ---", bold=True)
    player_response = player_api.get_all_known_players_api()

    if not player_response.get("players"):
        click.secho(
            "No players found in the global database (players.json).", fg="yellow"
        )
        click.secho(
            "Run 'player scan' or 'player add' to add players first.", fg="cyan"
        )
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
        f"Select permission level for {selected_player['name']}:",
        choices=["member", "operator", "visitor"],
        default="member",
    ).ask()

    if permission is None:
        raise click.Abort()

    perm_response = config_api.configure_player_permission(
        server_name, selected_player["xuid"], selected_player["name"], permission
    )
    _handle_api_response(
        perm_response,
        f"Permission for {selected_player['name']} set to '{permission}'.",
    )


def _interactive_properties_config(server_name: str):
    """
    Manages the interactive workflow for configuring server.properties.

    Fetches current server properties, then interactively prompts the user
    for common properties, validates input, and applies changes via API.

    Args:
        server_name: The name of the server whose properties are being configured.
    """
    click.secho("--- Configure Server Properties ---", bold=True)
    click.echo("Loading current properties...")

    properties_response = config_api.get_server_properties_api(server_name)
    if properties_response.get("status") == "error":
        click.secho(
            f"Could not load server properties: {properties_response.get('message')}",
            fg="red",
        )
        return

    current_properties = properties_response.get("properties", {})
    changes = {}

    def prompt(prop, message, prompter, **kwargs):
        current_val = str(current_properties.get(prop, kwargs.get("default", "")))
        new_val = prompter(message, default=current_val, **kwargs).ask()
        if new_val is not None and new_val != current_val:
            changes[prop] = new_val

    # Use questionary for each property
    prompt(
        "server-name",
        "Server name (visible in LAN list):",
        questionary.text,
        validate=PropertyValidator("server-name"),
    )
    prompt(
        "level-name",
        "World folder name:",
        questionary.text,
        validate=PropertyValidator("level-name"),
    )
    prompt(
        "gamemode",
        "Default gamemode:",
        questionary.select,
        choices=["survival", "creative", "adventure"],
    )
    prompt(
        "difficulty",
        "Game difficulty:",
        questionary.select,
        choices=["peaceful", "easy", "normal", "hard"],
    )
    prompt("allow-cheats", "Allow cheats:", questionary.confirm)
    prompt(
        "max-players",
        "Maximum players:",
        questionary.text,
        validate=PropertyValidator("max-players"),
    )
    prompt("online-mode", "Require Xbox Live authentication:", questionary.confirm)
    prompt("allow-list", "Enable allowlist:", questionary.confirm)
    prompt(
        "default-player-permission-level",
        "Default permission for new players:",
        questionary.select,
        choices=["visitor", "member", "operator"],
    )
    prompt(
        "view-distance",
        "View distance (chunks):",
        questionary.text,
        validate=PropertyValidator("view-distance"),
    )
    prompt(
        "tick-distance",
        "Tick simulation distance (chunks):",
        questionary.text,
        validate=PropertyValidator("tick-distance"),
    )
    prompt("level-seed", "Level seed (leave blank for random):", questionary.text)
    prompt("texturepack-required", "Require Texture Packs:", questionary.confirm)

    if not changes:
        click.secho("\nNo properties were changed.", fg="cyan")
        return

    click.secho("\nApplying the following changes:", bold=True)
    for key, value in changes.items():
        click.echo(f"  - {key}: {value}")

    update_response = config_api.modify_server_properties(server_name, changes)
    _handle_api_response(update_response, "Server properties updated successfully.")


# --- Click Commands ---


@click.command("install-server")
@click.pass_context
def install_server(ctx: click.Context):
    """Interactively installs and configures a new Bedrock server."""
    try:
        click.secho("--- New Bedrock Server Installation ---", bold=True)
        server_name = questionary.text(
            "Enter a name for the new server folder:", validate=ServerNameValidator()
        ).ask()
        if not server_name:
            raise click.Abort()

        target_version = questionary.text(
            "Enter server version (e.g., LATEST, PREVIEW, 1.20.81.01):",
            default="LATEST",
        ).ask()
        if not target_version:
            raise click.Abort()

        click.echo(
            f"Installing server '{server_name}' version '{target_version}'. This may take a moment..."
        )
        install_result = config_api.install_new_server(server_name, target_version)

        if install_result.get(
            "status"
        ) == "error" and "already exists" in install_result.get("message", ""):
            click.secho(install_result.get("message"), fg="yellow")
            if questionary.confirm(
                "Do you want to delete the existing server and reinstall?"
            ).ask():
                click.echo(f"Deleting existing server '{server_name}'...")
                server_api.delete_server_data(
                    server_name
                )  # Assuming this API handles errors
                click.echo("Retrying installation...")
                install_result = config_api.install_new_server(
                    server_name, target_version
                )
            else:
                raise click.Abort()

        _handle_api_response(
            install_result,
            f"Server files installed (Version: {install_result.get('version')}).",
        )

        _interactive_properties_config(server_name)
        if questionary.confirm("Configure allowlist now?", default=False).ask():
            _interactive_allowlist_config(server_name)
        if questionary.confirm(
            "Configure player permissions now?", default=False
        ).ask():
            _interactive_permissions_config(server_name)

        if questionary.confirm("Start server now?", default=True).ask():
            # Find the main 'cli' group from the context object we set in __main__.py
            # Then get the 'server' subgroup, and finally the 'start' command.
            server_group = ctx.obj["cli"].get_command(ctx, "server")
            start_command = server_group.get_command(ctx, "start")

            click.echo("Starting the server in detached mode...")
            # Use ctx.invoke to run the command
            ctx.invoke(start_command, server_name=server_name, mode="detached")

        click.secho("\nInstallation and configuration complete!", fg="green", bold=True)

    except BSMError as e:
        click.secho(f"An application error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nInstallation cancelled.", fg="yellow")


@click.command("update-server")
@click.option("-s", "--server", required=True, help="Name of the server to update.")
def update_server(server: str):
    """Checks for and applies updates to an existing server."""
    click.echo(f"Checking for updates for server '{server}'...")
    try:
        response = config_api.update_server(server)
        _handle_api_response(response, "Update check complete.")
    except BSMError as e:
        click.secho(f"A server update error occurred: {e}", fg="red")
        raise click.Abort()


@click.command("configure-allowlist")
@click.option("-s", "--server", required=True, help="Name of the server to configure.")
def configure_allowlist(server: str):
    """Interactively configure the allowlist for a server."""
    try:
        _interactive_allowlist_config(server)
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nConfiguration cancelled.", fg="yellow")


@click.command("configure-permissions")
@click.option("-s", "--server", required=True, help="Name of the server to configure.")
def configure_permissions(server: str):
    """Interactively set permission levels for known players."""
    try:
        _interactive_permissions_config(server)
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nConfiguration cancelled.", fg="yellow")


@click.command("configure-properties")
@click.option("-s", "--server", required=True, help="Name of the server to configure.")
def configure_properties(server: str):
    """Interactively configure common server.properties settings."""
    try:
        _interactive_properties_config(server)
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nConfiguration cancelled.", fg="yellow")


@click.command("remove-allowlist-players")
@click.option("-s", "--server", required=True, help="Name of the server.")
@click.argument("players", nargs=-1, required=True)
def remove_allowlist_players(server: str, players: tuple[str]):
    """Removes one or more players from a server's allowlist."""
    if not players:
        click.secho("No player names provided.", fg="yellow")
        return

    click.echo(
        f"Attempting to remove {len(players)} player(s) from '{server}' allowlist..."
    )
    try:
        # Call the new, plural-handling API function
        response = config_api.remove_players_from_allowlist(server, list(players))

        # Use the generic handler for the main error/success status
        _handle_api_response(response, "Allowlist update process finished.")

        # Now, parse the detailed response for better user feedback
        if response.get("status") == "success" and response.get("details"):
            details = response["details"]

            removed = details.get("removed", [])
            not_found = details.get("not_found", [])

            if removed:
                click.secho(
                    f"\nSuccessfully removed {len(removed)} player(s):", fg="green"
                )
                for player in removed:
                    click.echo(f"  - {player}")

            if not_found:
                click.secho(
                    f"\n{len(not_found)} player(s) were not found in the allowlist:",
                    fg="yellow",
                )
                for player in not_found:
                    click.echo(f"  - {player}")

    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()
