# bedrock_server_manager/cli/commands/server_properties.py
import click
import questionary

from bedrock_server_manager.api import server_install_config as config_api
from bedrock_server_manager.cli.utils import (
    handle_api_response,
    PropertyValidator,
)


def interactive_properties_workflow(server_name: str):
    """Manages the interactive workflow for configuring server.properties."""
    click.secho("--- Configure Server Properties ---", bold=True)
    click.echo("Loading current properties...")

    properties_response = config_api.get_server_properties_api(server_name)
    if properties_response.get("status") == "error":
        click.secho(
            f"Could not load properties: {properties_response.get('message')}", fg="red"
        )
        return

    current_properties = properties_response.get("properties", {})
    changes = {}

    def prompt(prop, message, prompter, **kwargs):
        # Get the original value from the loaded properties
        original_value_str = current_properties.get(prop, None)

        # Determine the default value for the prompt
        # If the property exists, use it. Otherwise, use the kwarg default.
        default_for_prompt = original_value_str if original_value_str is not None else kwargs.get("default", "")

        # --- Special handling for boolean (confirm) prompts ---
        if prompter == questionary.confirm:
            # Convert the string 'true'/'false' to a boolean for the default
            # All other strings become False, which is a safe default.
            default_bool = str(default_for_prompt).lower() == 'true'
            
            # Ask the user. The result will be a pure boolean: True or False
            new_val_bool = questionary.confirm(message, default=default_bool, **kwargs).ask()

            # If the user cancelled the prompt
            if new_val_bool is None:
                return

            # Compare the new boolean with the original boolean state
            if new_val_bool != default_bool:
                # Store the change as a lowercase string, as Minecraft expects
                changes[prop] = str(new_val_bool).lower()

        # --- Logic for all other prompt types (text, select, etc.) ---
        else:
            # The original value is already a string, so we can use it directly
            # If it's None, fall back to the kwarg default
            current_val_str = original_value_str if original_value_str is not None else str(kwargs.get("default", ""))

            # Ask the user. The result will be a string.
            new_val_str = prompter(message, default=current_val_str, **kwargs).ask()
            
            # If the user cancelled the prompt
            if new_val_str is None:
                return
            
            # Compare the new string value with the original string value
            if new_val_str != current_val_str:
                changes[prop] = new_val_str

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
    handle_api_response(update_response, "Server properties updated successfully.")


@click.group()
def properties():
    """
    View and modify server.properties settings.
    Use 'set' without arguments for an interactive wizard.
    """
    pass


@properties.command("get")
@click.option("-s", "--server-name", required=True, help="The name of the server.")
@click.option("-p", "--property-name", help="Get a single property value.")
def get(server_name: str, property_name: str):
    """Displays server properties. Shows all if no specific property is named."""
    response = config_api.get_server_properties_api(server_name)
    data = handle_api_response(response, "Properties fetched.")
    properties = data.get("properties", {})

    if property_name:
        value = properties.get(property_name)
        if value is not None:
            click.echo(value)
        else:
            click.secho(f"Property '{property_name}' not found.", fg="red")
            raise click.Abort()
    else:
        click.secho(f"Properties for '{server_name}':", bold=True)
        for key, value in sorted(properties.items()):
            click.echo(f"  {key}={value}")


@properties.command("set")
@click.option("-s", "--server-name", required=True, help="The name of the server.")
@click.option(
    "--no-restart", is_flag=True, help="Do not restart the server after applying."
)
@click.argument("properties", nargs=-1)
def set_props(server_name: str, no_restart: bool, properties: tuple[str]):
    """
    Sets one or more server properties.

    PROPERTIES should be in key=value format.
    Example: bsm properties set -s MyServer max-players=15

    If no properties are provided as arguments, an interactive wizard is launched.
    """
    try:
        if not properties:
            click.secho(
                f"No properties specified. Starting interactive properties editor for '{server_name}'...",
                fg="yellow",
            )
            interactive_properties_workflow(server_name)
            return

        # Direct, non-interactive logic
        props_to_update = {}
        for p in properties:
            if "=" not in p:
                click.secho(f"Error: Invalid format '{p}'. Use 'key=value'.", fg="red")
                raise click.Abort()
            key, value = p.split("=", 1)
            props_to_update[key] = value

        click.echo(f"Updating properties for '{server_name}'...")
        response = config_api.modify_server_properties(
            server_name, props_to_update, restart_after_modify=not no_restart
        )
        handle_api_response(response, "Properties updated successfully.")

    except (click.Abort, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")
