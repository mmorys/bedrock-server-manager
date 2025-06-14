# bedrock_server_manager/cli/world.py
"""
Click command group for managing server worlds.

Provides commands for exporting, importing (installing), and resetting worlds,
using interactive prompts where necessary.
"""

import os
import logging
from typing import Optional, Dict, Any

import click
import questionary

from bedrock_server_manager.api import application as api_application
from bedrock_server_manager.api import world as world_api
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


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


@click.group()
def world():
    """Commands for installing, exporting, and resetting server worlds."""
    pass


@world.command("install")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the target server."
)
@click.option(
    "-f",
    "--file",
    "world_file_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to the .mcworld file. Skips interactive menu.",
)
@click.option(
    "--no-stop",
    is_flag=True,
    help="Attempt import without stopping the server (risks data corruption).",
)
def install_world(server_name: str, world_file_path: Optional[str], no_stop: bool):
    """
    Installs a world from a .mcworld file. Replaces the current world.

    If --file is not specified, an interactive menu will list available worlds.
    """
    try:
        selected_file = world_file_path

        if not selected_file:
            # Interactive mode
            click.secho(
                f"Entering interactive world installation for server: {server_name}",
                fg="yellow",
            )
            list_response = api_application.list_available_worlds_api()
            available_files = list_response.get("files", [])

            if not available_files:
                click.secho(
                    "No .mcworld files found in the content/worlds directory.",
                    fg="yellow",
                )
                return

            file_map = {os.path.basename(f): f for f in available_files}
            selection = questionary.select(
                "Select a world to install:", choices=list(file_map.keys()) + ["Cancel"]
            ).ask()

            if not selection or selection == "Cancel":
                raise click.Abort()
            selected_file = file_map[selection]

        filename = os.path.basename(selected_file)
        click.secho(
            f"\nWARNING: Installing '{filename}' will REPLACE the current world data for server '{server_name}'.",
            fg="red",
            bold=True,
        )
        if not questionary.confirm(
            "This action cannot be undone. Are you sure?", default=False
        ).ask():
            raise click.Abort()

        click.echo(f"Installing world '{filename}'...")
        response = world_api.import_world(
            server_name, selected_file, stop_start_server=(not no_stop)
        )
        _handle_api_response(response, f"World '{filename}' installed successfully.")

    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        click.secho("World installation cancelled.", fg="yellow")


@world.command("export")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server whose world to export.",
)
def export_world(server_name: str):
    """Exports the server's current world to a .mcworld file."""
    click.echo(f"Attempting to export world for server '{server_name}'...")
    try:
        response = world_api.export_world(server_name)
        _handle_api_response(response, "World exported successfully.")
    except BSMError as e:
        click.secho(f"An error occurred during export: {e}", fg="red")
        raise click.Abort()


@world.command("reset")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server whose world to reset.",
)
@click.option("-y", "--yes", is_flag=True, help="Bypass the confirmation prompt.")
def reset_world(server_name: str, yes: bool):
    """
    Deletes the current world, allowing the server to generate a new one on next start.
    """
    if not yes:
        click.secho(
            f"WARNING: This will permanently delete the current world for server '{server_name}'.",
            fg="red",
            bold=True,
        )
        click.confirm(
            "This action cannot be undone. Are you sure you want to reset the world?",
            abort=True,
        )

    click.echo(f"Resetting world for server '{server_name}'...")
    try:
        response = world_api.reset_world(server_name)
        _handle_api_response(response, "World has been reset.")
    except BSMError as e:
        click.secho(f"An error occurred during reset: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    world()
