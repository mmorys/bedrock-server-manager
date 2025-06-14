# bedrock_server_manager/cli/addon.py
"""
Click command for managing server addons (.mcpack, .mcaddon).

Provides a single command to install addons either from a specified file
or via an interactive selection menu.
"""

import os
import logging
from typing import Optional, Dict, Any

import click
import questionary

from bedrock_server_manager.api import addon as addon_api
from bedrock_server_manager.api import application as api_application
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


# A helper to reduce code duplication in API response handling
def _handle_api_response(response: Dict[str, Any], success_msg: str):
    """Prints styled success or error message based on API response."""
    if response.get("status") == "error":
        message = response.get("message", "An unknown error occurred.")
        click.secho(f"Error: {message}", fg="red")
        raise click.Abort()
    else:
        message = response.get("message", success_msg)
        click.secho(f"Success: {message}", fg="green")


@click.command("install-addon")
@click.option("-s", "--server", required=True, help="Name of the target server.")
@click.option(
    "-f",
    "--file",
    "addon_file_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Full path to the addon file (.mcpack, .mcaddon). Skips interactive menu.",
)
def install_addon(server: str, addon_file_path: Optional[str]):
    """
    Installs an addon to the specified Bedrock server.

    This command can install an addon from a local file path provided with the
    --file option. If --file is not specified, it enters an interactive mode,
    listing available addons from the application's content directory for selection.
    """
    try:
        selected_addon_path = addon_file_path

        # If no file is provided via CLI option, enter interactive mode
        if not selected_addon_path:
            click.secho(
                f"Entering interactive addon installation for server: {server}",
                fg="yellow",
            )

            # Get list of available addons from the API
            list_response = api_application.list_available_addons_api()
            available_files = list_response.get("files", [])

            if not available_files:
                # Provide a helpful message if no addons are found
                app_info = api_application.get_application_info_api().get("data", {})
                addon_dir = os.path.join(
                    app_info.get("content_directory", ""), "addons"
                )
                click.secho(
                    f"Warning: No addon files found in '{addon_dir}'.", fg="yellow"
                )
                return

            # Create a mapping from user-friendly basename to full path
            file_map = {os.path.basename(f): f for f in available_files}

            selection = questionary.select(
                "Select an addon to install:",
                choices=list(file_map.keys()) + ["Cancel"],
            ).ask()

            if not selection or selection == "Cancel":
                raise click.Abort()

            selected_addon_path = file_map[selection]

        # At this point, selected_addon_path is guaranteed to be a valid path
        addon_filename = os.path.basename(selected_addon_path)
        click.echo(f"Installing addon '{addon_filename}' to server '{server}'...")
        logger.debug(
            f"CLI: Calling addon_api.import_addon for file: {selected_addon_path}"
        )

        response = addon_api.import_addon(server, selected_addon_path)

        success_message = f"Addon '{addon_filename}' installed successfully."
        _handle_api_response(response, success_message)

    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()
    except click.Abort:
        click.secho("Addon installation cancelled.", fg="yellow")


if __name__ == "__main__":
    # Allows for direct testing of this command
    logging.basicConfig(level=logging.INFO)
    install_addon()
