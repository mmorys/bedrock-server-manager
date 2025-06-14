# bedrock_server_manager/cli/server_actions.py
"""
Click command group for direct server management actions.

Provides commands for starting, stopping, restarting, deleting,
and sending commands to Bedrock server instances.
"""

import logging
from typing import Dict, Any, Tuple

import click
import questionary

from bedrock_server_manager.api import server as server_api
from bedrock_server_manager.api import server_install_config as config_api
from bedrock_server_manager.cli.server_allowlist import interactive_allowlist_workflow
from bedrock_server_manager.cli.server_permissions import (
    interactive_permissions_workflow,
)
from bedrock_server_manager.cli.server_properties import interactive_properties_workflow
from bedrock_server_manager.cli.utils import (
    handle_api_response as _handle_api_response,
    ServerNameValidator,
)
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


@click.group()
def server():
    """Commands to manage the lifecycle of individual servers."""
    pass


@server.command("start")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the server to start."
)
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["direct", "detached"], case_sensitive=False),
    default="detached",
    show_default=True,
    help="Mode to start the server in.",
)
def start_server(server_name: str, mode: str):
    """Starts a specific Bedrock server."""
    click.echo(f"Attempting to start server '{server_name}'...")
    try:
        response = server_api.start_server(server_name, mode)
        _handle_api_response(response, f"Server '{server_name}' started successfully.")
    except BSMError as e:
        click.secho(f"Failed to start server: {e}", fg="red")
        raise click.Abort()


@server.command("stop")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the server to stop."
)
def stop_server(server_name: str):
    """Stops a specific Bedrock server."""
    click.echo(f"Attempting to stop server '{server_name}'...")
    try:
        response = server_api.stop_server(server_name)
        _handle_api_response(response, f"Stop signal sent to server '{server_name}'.")
    except BSMError as e:
        click.secho(f"Failed to stop server: {e}", fg="red")
        raise click.Abort()


@server.command("restart")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server to restart.",
)
def restart_server(server_name: str):
    """Restarts a specific Bedrock server."""
    click.echo(f"Attempting to restart server '{server_name}'...")
    try:
        response = server_api.restart_server(server_name)
        _handle_api_response(
            response, f"Restart signal sent to server '{server_name}'."
        )
    except BSMError as e:
        click.secho(f"Failed to restart server: {e}", fg="red")
        raise click.Abort()


@server.command("install")
@click.pass_context
def install(ctx: click.Context):
    """Interactively installs and configures a new Bedrock server."""
    try:
        click.secho("--- New Bedrock Server Installation ---", bold=True)
        server_name = questionary.text(
            "Enter a name for the new server folder:", validate=ServerNameValidator()
        ).ask()
        if not server_name:
            raise click.Abort()

        target_version = questionary.text(
            "Enter server version (LATEST, PREVIEW, 1.20.81.01):",
            default="LATEST",
        ).ask()
        if not target_version:
            raise click.Abort()

        click.echo(f"Installing server '{server_name}' version '{target_version}'...")
        install_result = config_api.install_new_server(server_name, target_version)

        if "already exists" in install_result.get("message", ""):
            click.secho(install_result.get("message"), fg="yellow")
            if questionary.confirm("Delete the existing server and reinstall?").ask():
                click.echo(f"Deleting existing server '{server_name}'...")
                server_api.delete_server_data(server_name)
                click.echo("Retrying installation...")
                install_result = config_api.install_new_server(
                    server_name, target_version
                )
            else:
                raise click.Abort()

        response = _handle_api_response(install_result, "Server files installed.")
        click.secho(f"Installed Version: {response.get('version')}", bold=True)

        interactive_properties_workflow(server_name)
        if questionary.confirm("Configure allowlist now?", default=False).ask():
            interactive_allowlist_workflow(server_name)
        if questionary.confirm(
            "Configure player permissions now?", default=False
        ).ask():
            interactive_permissions_workflow(server_name)

        click.secho("\nInstallation and configuration complete!", fg="green", bold=True)
        start_command = ctx.parent.get_command(ctx, "start")
        if start_command:
            click.echo("Invoking start command...")
            ctx.invoke(start_command, server_name=server_name, mode="detached")
        else:
            click.secho(
                "Error: Could not find the 'start' command to invoke.", fg="red"
            )

    except BSMError as e:
        click.secho(f"An application error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nInstallation cancelled.", fg="yellow")


@server.command("update")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the server to update."
)
def update(server_name: str):
    """Checks for and applies updates to an existing server."""
    click.echo(f"Checking for updates for server '{server_name}'...")
    try:
        response = config_api.update_server(server_name)
        _handle_api_response(response, "Update check complete.")
    except BSMError as e:
        click.secho(f"A server update error occurred: {e}", fg="red")
        raise click.Abort()


@server.command("delete")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the server to delete."
)
@click.option("-y", "--yes", is_flag=True, help="Bypass the confirmation prompt.")
def delete_server(server_name: str, yes: bool):
    """Deletes all data for a server, including worlds and backups."""
    if not yes:
        click.secho(
            f"WARNING: This will delete all data for server '{server_name}', including the installation, worlds, and all backups.",
            fg="yellow",
        )
        # click.confirm with abort=True is the perfect tool for this.
        # It will exit the command if the user enters 'n'.
        click.confirm(
            f"Are you absolutely sure you want to delete '{server_name}'?", abort=True
        )

    click.echo(f"Proceeding with deletion of server '{server_name}'...")
    try:
        response = server_api.delete_server_data(server_name)
        _handle_api_response(
            response, f"Server '{server_name}' and all its data have been deleted."
        )
    except BSMError as e:
        click.secho(f"Failed to delete server: {e}", fg="red")
        raise click.Abort()


@server.command("send-command")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the target server."
)
@click.argument("command", nargs=-1, required=True)
def send_command(server_name: str, command: Tuple[str]):
    """Sends a command to a running server (e.g., say hello world)."""
    # nargs=-1 captures all arguments into a tuple. We join them back into a string.
    command_string = " ".join(command)

    click.echo(f"Sending command to '{server_name}': {command_string}")
    try:
        response = server_api.send_command(server_name, command_string)
        _handle_api_response(response, "Command sent successfully.")
    except BSMError as e:
        click.secho(f"Failed to send command: {e}", fg="red")
        raise click.Abort()


@server.command("write-config")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server to restart.",
)
@click.option(
    "-k",
    "--key",
    "key",
    required=True,
    help="Key to change.",
)
@click.option(
    "-v",
    "--value",
    "value",
    required=True,
    help="Value for Key.",
)
def write_server_config(server_name: str, key: str, value: str):
    """Writes a Key:Value pair to a specific Bedrock server."""
    click.echo(f"Attempting to write config {key} for server '{server_name}'...")
    try:
        response = server_api.write_server_config(server_name, key, value)
        _handle_api_response(
            response, f"{key} set to {value} for server '{server_name}'."
        )
    except BSMError as e:
        click.secho(f"Failed to set {key} for server: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server()
