# bedrock_server_manager/cli/utils.py
"""
Provides CLI utility commands and modernized interactive helper functions.

Includes commands for listing server statuses and attaching to consoles,
and a `questionary`-based helper for selecting a valid server.
"""

import time
import logging
import platform
from typing import Optional, Dict, Any, List

import click
import questionary
from questionary import Validator, ValidationError

from bedrock_server_manager.api import (
    utils as api_utils,
    application as api_application,
)
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


# --- Modernized Interactive Helper ---


class ServerExistsValidator(Validator):
    """A questionary Validator that uses the API to check if a server exists."""

    def validate(self, document):
        server_name = document.text.strip()
        if not server_name:
            # Let questionary handle empty input if needed by the prompt
            return

        response = api_utils.validate_server_exist(server_name)
        if response.get("status") != "success":
            raise ValidationError(
                message=response.get("message", "Server not found or invalid."),
                cursor_position=len(document.text),
            )


def get_server_name_interactively() -> Optional[str]:
    """
    Prompts the user to enter a server name and validates its existence using a live validator.

    Returns:
        The validated server name as a string, or None if the user cancels.
    """
    try:
        server_name = questionary.text(
            "Enter the server name:",
            validate=ServerExistsValidator(),
            validate_while_typing=False,
        ).ask()

        # .ask() returns None if the user cancels (e.g., Ctrl+C)
        return server_name

    except (KeyboardInterrupt, EOFError):
        # Handle cases where the process is killed more abruptly
        click.secho("\nOperation cancelled.", fg="yellow")
        return None


# --- Utility Commands ---


# Helper similar to other CLI modules for standardized response handling
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


def _print_server_table(servers: List[Dict[str, Any]]):
    """
    Prints a formatted table of server information to the console.

    Args:
        servers: A list of dictionaries, where each dictionary contains
                 details for a server (e.g., name, status, version).
    """
    header = f"{'SERVER NAME':<25} {'STATUS':<20} {'VERSION'}"
    click.secho(header, bold=True)
    click.echo("-" * 65)

    if not servers:
        click.echo("  No servers found.")
    else:
        for server_data in servers:
            name = server_data.get("name", "N/A")
            status = server_data.get("status", "UNKNOWN").upper()
            version = server_data.get("version", "UNKNOWN")

            status_color = {
                "RUNNING": "green",
                "STARTING": "yellow",
                "STOPPING": "yellow",
                "STOPPED": "red",
                "INSTALLED": "blue",
            }.get(status, "red")

            status_styled = click.style(f"{status:<10}", fg=status_color)
            name_styled = click.style(name, fg="cyan")

            click.echo(f"  {name_styled:<38} {status_styled:<20} {version}")

    click.echo("-" * 65)


@click.command("list-servers")
@click.option(
    "-l",
    "--loop",
    is_flag=True,
    help="Continuously list server statuses every 5 seconds.",
)
def list_servers(loop: bool):
    """Lists all servers and their statuses."""
    try:
        if loop:
            while True:
                click.clear()
                click.secho(
                    "--- Bedrock Servers Status (Press CTRL+C to exit) ---",
                    fg="magenta",
                )
                response = api_application.get_all_servers_data()
                servers = response.get("servers", [])
                _print_server_table(servers)
                time.sleep(5)
        else:
            # Run once
            click.secho("--- Bedrock Servers Status ---", fg="magenta")
            response = api_application.get_all_servers_data()
            servers = response.get("servers", [])
            _print_server_table(servers)

    except (KeyboardInterrupt, click.Abort):
        click.secho("\nExiting status monitor.", fg="green")
    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")


@click.command("attach-console")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server's screen session to attach to.",
)
def attach_console(server_name: str):
    """Attaches the terminal to a server's screen session (Linux only)."""
    if platform.system() != "Linux":
        click.secho(
            "Error: This command requires 'screen' and is only available on Linux.",
            fg="red",
        )
        return

    click.echo(f"Attempting to attach to console for server '{server_name}'...")
    # Note: The attach_to_screen_session API might not return in the typical way
    # if it successfully execs into 'screen'. If it returns, it's likely an error
    # or a preliminary check message.
    try:
        response = api_utils.attach_to_screen_session(server_name)
        # If attach_to_screen_session returns (e.g. error before exec), handle it.
        # A successful screen attach might mean this Python script segment is no longer running.
        _handle_api_response(response, "Attach command issued. Check your terminal.")
    except BSMError as e:
        # This handles errors raised directly by the API call itself (e.g., server not found by API)
        click.secho(f"An application error occurred: {e}", fg="red")
        # No click.Abort() here as it might be redundant if _handle_api_response raises it
