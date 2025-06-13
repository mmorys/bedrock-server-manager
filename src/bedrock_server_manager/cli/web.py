# bedrock_server_manager/cli/web.py
"""
Click command group for managing the application's web server process.
"""

import logging
from typing import Dict, Any, Tuple

import click

from bedrock_server_manager.api import web as web_api
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
def web():
    """Commands for managing the web management interface."""
    pass


@web.command("start")
@click.option(
    "-H",
    "--host",
    multiple=True,
    help="Host address to bind to. Use multiple times for multiple hosts (e.g., --host 127.0.0.1 --host 0.0.0.0).",
)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Run in Flask's debug mode (NOT for production).",
)
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["direct", "detached"], case_sensitive=False),
    default="direct",
    show_default=True,
    help="Run mode: 'direct' blocks the terminal, 'detached' runs in the background.",
)
def start_web_server(host: Tuple[str], debug: bool, mode: str):
    """Starts the web management server."""
    click.echo(f"Attempting to start web server in '{mode}' mode...")
    if mode == "direct":
        click.secho(
            "Server will run in this terminal. Press Ctrl+C to stop.", fg="cyan"
        )

    try:
        # The API likely expects a list, so we convert the tuple from `multiple=True`.
        # Pass an empty list if no hosts are provided, letting the API use its default.
        host_list = list(host)

        response = web_api.start_web_server_api(host_list, debug, mode)

        if response.get("status") == "error":
            click.secho(f"Error: {response.get('message')}", fg="red")
        else:
            if mode == "detached":
                pid = response.get("pid", "N/A")
                message = response.get(
                    "message", f"Web server started in detached mode (PID: {pid})."
                )
                click.secho(f"Success: {message}", fg="green")
            # For 'direct' mode, the process blocks, so no success message is needed here.
            # The user will see the server's own startup logs.
    except BSMError as e:
        click.secho(f"Failed to start web server: {e}", fg="red")
        raise click.Abort()


@web.command("stop")
def stop_web_server():
    """Stops the detached web server process (if implemented)."""
    click.echo("Attempting to stop the web server...")
    try:
        response = web_api.stop_web_server_api()
        # The API itself will return the "not implemented" message, which our handler will print.
        # This is good design, keeping the "not implemented" logic in the API layer.
        _handle_api_response(response, "Web server stopped successfully.")
    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    web()
