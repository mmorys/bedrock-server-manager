# bedrock_server_manager/cli/world.py
"""
Defines the `bsm world` command group for managing server worlds.

This module contains subcommands to install worlds from `.mcworld` files,
export existing worlds, and reset them to their original state, allowing
for easy world management.
"""

import logging
import os
from typing import Optional

import click
import questionary

from bedrock_server_manager.api import application as api_application
from bedrock_server_manager.api import world as world_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


@click.group()
def world():
    """Manages server worlds (install, export, reset).

    This command group provides utilities to manipulate the world data for a
    given server. You can install a world from a `.mcworld` file, export
    the current world for backup or transfer, or reset it to allow the
    server to generate a new one.
    """
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
    help="Path to the .mcworld file to install. Skips interactive menu.",
)
@click.option(
    "--no-stop",
    is_flag=True,
    help="Attempt to install without stopping the server (risks data corruption).",
)
def install_world(server_name: str, world_file_path: Optional[str], no_stop: bool):
    """Installs a world from a .mcworld file, replacing the current world.

    If the --file option is not provided, this command enters an interactive
    mode, listing all available .mcworld files in the designated content
    directory for you to choose from.

    This is a destructive action that will overwrite the existing world.

    Args:
        server_name: The name of the server to install the world on.
        world_file_path: The direct path to the .mcworld file.
        no_stop: If True, skips the safe server stop/start procedure.

    Raises:
        click.Abort: If the operation is cancelled by the user.
    """
    try:
        selected_file = world_file_path

        if not selected_file:
            click.secho(
                f"Entering interactive world installation for server: {server_name}",
                fg="yellow",
            )
            list_response = api_application.list_available_worlds_api()
            available_files = list_response.get("files", [])

            if not available_files:
                click.secho(
                    "No .mcworld files found in the content/worlds directory. Nothing to install.",
                    fg="yellow",
                )
                return

            file_map = {os.path.basename(f): f for f in available_files}
            choices = sorted(list(file_map.keys())) + ["Cancel"]
            selection = questionary.select(
                "Select a world to install:", choices=choices
            ).ask()

            if not selection or selection == "Cancel":
                raise click.Abort()  # User explicitly cancelled
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
            raise click.Abort()  # User declined confirmation

        click.echo(f"Installing world '{filename}'...")
        response = world_api.import_world(
            server_name, selected_file, stop_start_server=(not no_stop)
        )
        _handle_api_response(response, f"World '{filename}' installed successfully.")

    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        # This block catches cancellations from prompts or Ctrl+C.
        click.secho("\nWorld installation cancelled.", fg="yellow")


@world.command("export")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server whose world to export.",
)
def export_world(server_name: str):
    """Exports the server's current world to a .mcworld file.

    This command packages the current world directory into a .mcworld
    archive. The resulting file is saved in the `content/worlds`
    directory and can be used for backups or transferred to other servers.

    Args:
        server_name: The name of the server with the world to export.

    Raises:
        click.Abort: If the export fails due to a BSMError.
    """
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
    """Deletes the current world to allow a new one to be generated.

    This is a destructive operation that permanently removes the server's
    world data. It is useful when you want to start over with a fresh,
    randomly generated world. A confirmation prompt is required unless the
    --yes flag is provided.

    Args:
        server_name: The name of the server whose world will be reset.
        yes: If True, bypasses the interactive confirmation prompt.

    Raises:
        click.Abort: If the reset fails or the user cancels the confirmation.
    """
    if not yes:
        click.secho(
            f"WARNING: This will permanently delete the current world for server '{server_name}'.",
            fg="red",
            bold=True,
        )
        # click.confirm is a great utility that handles the prompt and abort logic.
        click.confirm(
            "This action cannot be undone. Are you sure you want to reset the world?",
            abort=True,
        )

    click.echo(f"Resetting world for server '{server_name}'...")
    try:
        response = world_api.reset_world(server_name)
        _handle_api_response(response, "World has been reset successfully.")
    except BSMError as e:
        click.secho(f"An error occurred during reset: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    world()
