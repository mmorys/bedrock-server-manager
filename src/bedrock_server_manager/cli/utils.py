# bedrock_server_manager/cli/utils.py
"""
Defines standalone utility commands and shared helper functions for the CLI.

This module contains general-purpose commands like `list-servers` and
`attach-console`. It also provides shared, reusable components for other CLI
modules, such as API response handlers, interactive prompts, and custom
`questionary` validators.
"""

import functools
import logging
import platform
import time
from typing import Any, Callable, Dict, List, Optional

import click
import questionary
from questionary import ValidationError, Validator

from bedrock_server_manager.api import (
    application as api_application,
    server_install_config as config_api,
    utils as api_utils,
)
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


# --- Custom Decorators ---


def linux_only(func: Callable) -> Callable:
    """A decorator that restricts a Click command to run only on Linux."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if platform.system() != "Linux":
            cmd_name = func.__name__.replace("_", "-")
            click.secho(
                f"Error: The '{cmd_name}' command is only available on Linux.", fg="red"
            )
            raise click.Abort()
        return func(*args, **kwargs)

    return wrapper


# --- Shared Helpers ---


def handle_api_response(response: Dict[str, Any], success_msg: str) -> Dict[str, Any]:
    """Handles responses from API calls, displaying success or error messages.

    If the response indicates an error, it prints an error message and aborts
    the CLI command. Otherwise, it prints a success message. It prioritizes
    the message from the API response over the default `success_msg`.

    Args:
        response: The dictionary response from an API function.
        success_msg: The default success message to display if the response
            does not contain one.

    Returns:
        The `data` dictionary from the API response on success.

    Raises:
        click.Abort: If the API response status is "error".
    """
    if response.get("status") == "error":
        message = response.get("message", "An unknown error occurred.")
        click.secho(f"Error: {message}", fg="red")
        raise click.Abort()

    message = response.get("message", success_msg)
    click.secho(f"Success: {message}", fg="green")
    return response.get("data", {})


class ServerNameValidator(Validator):
    """A `questionary.Validator` to check for valid server name characters."""

    def validate(self, document) -> None:
        """Validates the server name format using the `utils_api`.

        Args:
            document: The questionary document containing the user's input.
        Raises:
            ValidationError: If the server name format is invalid.
        """
        name = document.text.strip()
        response = api_utils.validate_server_name_format(name)
        if response.get("status") == "error":
            raise ValidationError(
                message=response.get("message", "Invalid server name format."),
                cursor_position=len(document.text),
            )


class ServerExistsValidator(Validator):
    """A `questionary.Validator` to check if a server already exists."""

    def validate(self, document) -> None:
        """Validates that the server name exists using the `utils_api`.

        Args:
            document: The questionary document containing the user's input.
        Raises:
            ValidationError: If the server does not exist or the name is invalid.
        """
        server_name = document.text.strip()
        if not server_name:
            return
        response = api_utils.validate_server_exist(server_name)
        if response.get("status") != "success":
            raise ValidationError(
                message=response.get("message", "Server not found."),
                cursor_position=len(document.text),
            )


def get_server_name_interactively() -> Optional[str]:
    """Interactively prompts the user to select an existing server.

    It first attempts to show a list of existing servers for selection. If
    no servers are found, it falls back to a text input prompt.

    Returns:
        The validated server name as a string, or None if the operation
        is cancelled.
    """
    try:
        response = api_application.get_all_servers_data()
        servers = response.get("data", {}).get("servers")
        if servers is None:
            servers = response.get("servers", [])
        server_names = sorted([s["name"] for s in servers if "name" in s])

        if server_names:
            choice = questionary.select(
                "Select a server:", choices=server_names + ["Cancel"]
            ).ask()
            return choice if choice and choice != "Cancel" else None
        else:
            click.secho("No existing servers found.", fg="yellow")
            return questionary.text(
                "Enter the server name:", validate=ServerExistsValidator()
            ).ask()

    except (KeyboardInterrupt, EOFError, click.Abort):
        click.secho("\nOperation cancelled.", fg="yellow")
        return None


class PropertyValidator(Validator):
    """A `questionary.Validator` for a specific server property value.

    Attributes:
        property_name: The name of the server property to validate.
    """

    def __init__(self, property_name: str):
        """Initializes the validator with a property name.

        Args:
            property_name: The name of the server property (e.g., 'level-name').
        """
        self.property_name = property_name

    def validate(self, document) -> None:
        """Validates the property value using the `config_api`.

        Args:
            document: The questionary document containing the user's input.
        Raises:
            ValidationError: If the property value is invalid.
        """
        value = document.text.strip()
        response = config_api.validate_server_property_value(self.property_name, value)
        if response.get("status") == "error":
            raise ValidationError(
                message=response.get("message", "Invalid value."),
                cursor_position=len(document.text),
            )


# --- Standalone Utility Commands ---


def _print_server_table(servers: List[Dict[str, Any]]):
    """Prints a formatted table of server information to the console.

    Args:
        servers: A list of server data dictionaries.
    """
    header = f"{'SERVER NAME':<25} {'STATUS':<15} {'VERSION'}"
    click.secho(header, bold=True)
    click.echo("-" * 65)

    if not servers:
        click.echo("  No servers found.")
    else:
        for server_data in servers:
            name = server_data.get("name", "N/A")
            status = server_data.get("status", "UNKNOWN").upper()
            version = server_data.get("version", "UNKNOWN")

            color_map = {
                "RUNNING": "green",
                "STOPPED": "red",
                "STARTING": "yellow",
                "STOPPING": "yellow",
                "INSTALLING": "bright_cyan",
                "UPDATING": "bright_cyan", 
                "INSTALLED": "bright_magenta",
                "UPDATED": "bright_magenta",
                "UNKNOWN": "bright_black",
            }
            status_color = color_map.get(status, "red")

            status_styled = click.style(f"{status:<10}", fg=status_color)
            name_styled = click.style(name, fg="cyan")
            version_styled = click.style(version, fg="bright_white")

            click.echo(f"  {name_styled:<38} {status_styled:<20} {version_styled}")
    click.echo("-" * 65)


@click.command("list-servers")
@click.option(
    "--loop", is_flag=True, help="Continuously refresh server statuses every 5 seconds."
)
@click.option("--server-name-filter", help="Display status for only a specific server.")
def list_servers(loop: bool, server_name_filter: Optional[str]):
    """Lists all configured servers and their current status."""

    def _display_status():
        response = api_application.get_all_servers_data()
        all_servers = response.get("data", {}).get("servers")
        if all_servers is None:
            all_servers = response.get("servers", [])

        if server_name_filter:
            servers_to_show = [
                s for s in all_servers if s.get("name") == server_name_filter
            ]
        else:
            servers_to_show = all_servers

        _print_server_table(servers_to_show)

    try:
        if loop:
            while True:
                click.clear()
                click.secho(
                    "--- Bedrock Servers Status (Press CTRL+C to exit) ---",
                    fg="magenta",
                    bold=True,
                )
                _display_status()
                time.sleep(5)
        else:
            if not server_name_filter:
                click.secho("--- Bedrock Servers Status ---", fg="magenta", bold=True)
            _display_status()

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
@linux_only
def attach_console(server_name: str):
    """Attaches the terminal to a running server's console (Linux only)."""
    click.echo(f"Attempting to attach to console for server '{server_name}'...")
    try:
        # A successful call to this API will typically use `exec`, replacing
        # this Python process. If the function returns, it indicates an error.
        response = api_utils.attach_to_screen_session(server_name)
        handle_api_response(response, "Attach command issued. Check your terminal.")
    except BSMError as e:
        click.secho(f"An application error occurred: {e}", fg="red")
