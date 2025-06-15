# bedrock_server_manager/cli/addon.py
"""
Defines the `bsm install-addon` command for server addon management.

This module provides a CLI command to install Minecraft addons (such as
.mcpack or .mcaddon files) onto a specified server, with support for
both direct file path and interactive selection modes.
"""

import logging
import os
from typing import Optional

import click
import questionary

from bedrock_server_manager.api import addon as addon_api
from bedrock_server_manager.api import application as api_application
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


@click.command("install-addon")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the target server."
)
@click.option(
    "-f",
    "--file",
    "addon_file_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to the addon file (.mcpack, .mcaddon); skips interactive menu.",
)
def install_addon(server_name: str, addon_file_path: Optional[str]):
    """Installs a behavior or resource pack addon to a server.

    This command installs an addon from a local file path. An addon is
    typically a `.mcpack` or `.mcaddon` file.

    If the --file option is not provided, the command enters an interactive
    mode, listing available addons from the content directory for selection.

    Args:
        server_name: The name of the server to install the addon on.
        addon_file_path: Direct path to the addon file to be installed.

    Raises:
        click.Abort: If the operation is cancelled by the user or an error occurs.
    """
    try:
        selected_addon_path = addon_file_path

        # If no file is provided, enter interactive mode
        if not selected_addon_path:
            click.secho(
                f"Entering interactive addon installation for server: {server_name}",
                fg="yellow",
            )
            list_response = api_application.list_available_addons_api()
            available_files = list_response.get("files", [])

            if not available_files:
                click.secho(
                    "No addon files found in the content/addons directory. Nothing to install.",
                    fg="yellow",
                )
                return

            file_map = {os.path.basename(f): f for f in available_files}
            choices = sorted(list(file_map.keys())) + ["Cancel"]
            selection = questionary.select(
                "Select an addon to install:", choices=choices
            ).ask()

            if not selection or selection == "Cancel":
                raise click.Abort()  # User explicitly cancelled
            selected_addon_path = file_map[selection]

        # By this point, `selected_addon_path` is set to a valid file path.
        addon_filename = os.path.basename(selected_addon_path)
        click.echo(f"Installing addon '{addon_filename}' to server '{server_name}'...")
        logger.debug(
            f"CLI: Calling addon_api.import_addon for file: {selected_addon_path}"
        )

        response = addon_api.import_addon(server_name, selected_addon_path)
        _handle_api_response(
            response, f"Addon '{addon_filename}' installed successfully."
        )

    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        # This block catches cancellations from prompts (Ctrl+D/Abort) or Ctrl+C.
        click.secho("\nAddon installation cancelled.", fg="yellow")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    install_addon()
