# bedrock_server_manager/cli/server_properties.py
"""
Defines the `bsm properties` command group for server.properties management.

This module provides commands to view and modify settings in a server's
`server.properties` file. It features a comprehensive interactive workflow
for guided configuration and direct commands for scriptable changes.
"""
from typing import Dict, Optional

import click
import questionary

from bedrock_server_manager.api import server_install_config as config_api
from bedrock_server_manager.cli.utils import (
    PropertyValidator,
    handle_api_response as _handle_api_response,
)
from bedrock_server_manager.error import BSMError


def interactive_properties_workflow(server_name: str):
    """Guides a user through an interactive session to edit server properties.

    This function fetches all current properties, then walks the user through
    a series of prompts for common settings. It only records a property as
    changed if the new value differs from the original, and then sends a
    single API request to apply all changes at once.

    Args:
        server_name: The name of the server whose properties are being edited.

    Raises:
        click.Abort: If the user cancels the operation.
    """
    click.secho("\n--- Interactive Server Properties Configuration ---", bold=True)
    click.echo("Loading current server properties...")

    properties_response = config_api.get_server_properties_api(server_name)
    if properties_response.get("status") == "error":
        message = properties_response.get("message", "Could not load properties.")
        click.secho(f"Error: {message}", fg="red")
        raise click.Abort()

    current_properties = properties_response.get("properties", {})
    changes: Dict[str, str] = {}

    def _prompt(prop: str, message: str, prompter, **kwargs):
        """A nested helper to abstract the prompting and change-tracking logic."""
        original_value = current_properties.get(prop)

        if prompter == questionary.confirm:
            default_bool = str(original_value).lower() == "true"
            new_val = prompter(message, default=default_bool, **kwargs).ask()
            if new_val is None:
                return  # User cancelled
            # Record change only if the boolean state differs
            if new_val != default_bool:
                changes[prop] = str(new_val).lower()
        else:
            new_val = prompter(message, default=str(original_value), **kwargs).ask()
            if new_val is None:
                return  # User cancelled
            # Record change only if the string value differs
            if new_val != original_value:
                changes[prop] = new_val

    # --- Begin prompting for common properties ---
    _prompt(
        "server-name",
        "Server name (visible in LAN list):",
        questionary.text,
        validate=PropertyValidator("server-name"),
    )
    _prompt(
        "level-name",
        "World folder name:",
        questionary.text,
        validate=PropertyValidator("level-name"),
    )
    _prompt(
        "gamemode",
        "Default gamemode:",
        questionary.select,
        choices=["survival", "creative", "adventure"],
    )
    _prompt(
        "difficulty",
        "Game difficulty:",
        questionary.select,
        choices=["peaceful", "easy", "normal", "hard"],
    )
    _prompt("allow-cheats", "Allow cheats:", questionary.confirm)
    _prompt(
        "max-players",
        "Maximum players:",
        questionary.text,
        validate=PropertyValidator("max-players"),
    )
    _prompt("online-mode", "Require Xbox Live authentication:", questionary.confirm)
    _prompt("allow-list", "Enable allowlist:", questionary.confirm)
    _prompt(
        "default-player-permission-level",
        "Default permission for new players:",
        questionary.select,
        choices=["visitor", "member", "operator"],
    )
    _prompt(
        "view-distance",
        "View distance (chunks):",
        questionary.text,
        validate=PropertyValidator("view-distance"),
    )
    _prompt(
        "tick-distance",
        "Tick simulation distance (chunks):",
        questionary.text,
        validate=PropertyValidator("tick-distance"),
    )
    _prompt("level-seed", "Level seed (leave blank for random):", questionary.text)
    _prompt("texturepack-required", "Require texture packs:", questionary.confirm)

    if not changes:
        click.secho("\nNo properties were changed.", fg="cyan")
        return

    click.secho("\nApplying the following changes:", bold=True)
    for key, value in changes.items():
        original = current_properties.get(key, "not set")
        click.echo(
            f"  - {key}: {click.style(original, fg='red')} -> {click.style(value, fg='green')}"
        )

    if not questionary.confirm("Save these changes?", default=True).ask():
        raise click.Abort()

    update_response = config_api.modify_server_properties(server_name, changes)
    _handle_api_response(update_response, "Server properties updated successfully.")


@click.group()
def properties():
    """Views and modifies settings in server.properties."""
    pass


@properties.command("get")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="The name of the target server.",
)
@click.option("-p", "--prop", "property_name", help="Display a single property value.")
def get_props(server_name: str, property_name: Optional[str]):
    """Displays server properties from server.properties.

    If a specific property name is provided, only its value will be shown.
    Otherwise, all properties are listed.
    """
    response = config_api.get_server_properties_api(server_name)
    properties = response.get("properties", {})

    # Let the handler manage API errors
    if response.get("status") == "error":
        _handle_api_response(response, "")
        return

    if property_name:
        value = properties.get(property_name)
        if value is not None:
            click.echo(value)
        else:
            click.secho(f"Error: Property '{property_name}' not found.", fg="red")
            raise click.Abort()
    else:
        click.secho(f"\nProperties for '{server_name}':", bold=True)
        max_key_len = max(len(k) for k in properties.keys()) if properties else 0
        for key, value in sorted(properties.items()):
            click.echo(f"  {key:<{max_key_len}} = {value}")


@properties.command("set")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="The name of the target server.",
)
@click.option(
    "-p",
    "--prop",
    "properties",
    multiple=True,
    help="A 'key=value' pair to set. Use multiple times for multiple properties.",
)
@click.option(
    "--no-restart",
    is_flag=True,
    help="Do not restart the server after applying changes.",
)
def set_props(server_name: str, no_restart: bool, properties: tuple[str, ...]):
    """Sets one or more server properties directly.

    If run without the --prop option, this command launches an interactive
    editor. Otherwise, it applies the specified key-value pairs.

    Example: bsm properties set -s MyServer --prop max-players=15 --prop gamemode=creative
    """
    try:
        if not properties:
            click.secho(
                f"No properties specified; starting interactive editor for '{server_name}'...",
                fg="yellow",
            )
            interactive_properties_workflow(server_name)
            return

        props_to_update: Dict[str, str] = {}
        for p in properties:
            if "=" not in p:
                click.secho(f"Error: Invalid format '{p}'. Use 'key=value'.", fg="red")
                raise click.Abort()
            key, value = p.split("=", 1)
            props_to_update[key.strip()] = value.strip()

        click.echo(
            f"Updating {len(props_to_update)} propert(y/ies) for '{server_name}'..."
        )
        response = config_api.modify_server_properties(
            server_name, props_to_update, restart_after_modify=not no_restart
        )
        _handle_api_response(response, "Properties updated successfully.")

    except (click.Abort, KeyboardInterrupt, BSMError):
        click.secho("\nOperation cancelled.", fg="yellow")
