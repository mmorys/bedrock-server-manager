# bedrock_server_manager/cli/web.py
"""
Defines the `bsm web` command group for managing the web server.

This module contains the Click command group and subcommands for starting,
stopping, and managing the Flask-based web management interface.
"""

import logging
from typing import Tuple

import click

from bedrock_server_manager.api import web as web_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


@click.group()
def web():
    """Manages the web UI for server administration.

    This command group provides utilities to start and stop the web-based
    management interface, which allows for server administration through a
    browser.
    """
    pass


@web.command("start")
@click.option(
    "-H",
    "--host",
    "hosts",  # Use plural for `multiple=True` for clarity
    multiple=True,
    help="Host address to bind to. Use multiple times for multiple hosts.",
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
def start_web_server(hosts: Tuple[str], debug: bool, mode: str):
    """Starts the web management server.

    In 'direct' mode (default), the server runs in the foreground, printing
    logs directly to your terminal. This is useful for debugging. Press
    Ctrl+C to stop it.

    In 'detached' mode, the server starts as a background process, freeing
    up your terminal. Use 'bsm web stop' to terminate it.

    Args:
        hosts: A tuple of host addresses to bind the server to.
        debug: If True, runs the server in Flask's debug mode.
        mode: The execution mode, either 'direct' or 'detached'.

    Raises:
        click.Abort: If the server fails to start due to a BSMError.
    """
    click.echo(f"Attempting to start web server in '{mode}' mode...")
    if mode == "direct":
        click.secho(
            "Server will run in this terminal. Press Ctrl+C to stop.", fg="cyan"
        )

    try:
        # The API likely expects a list, so we convert the tuple from `multiple=True`.
        host_list = list(hosts)

        response = web_api.start_web_server_api(host_list, debug, mode)

        # Custom response handling is needed here because 'direct' mode
        # blocks and should not print a success message, while 'detached'
        # mode should. The shared _handle_api_response is not suitable.
        if response.get("status") == "error":
            message = response.get("message", "An unknown error occurred.")
            click.secho(f"Error: {message}", fg="red")
            raise click.Abort()
        else:
            if mode == "detached":
                pid = response.get("pid", "N/A")
                message = response.get(
                    "message", f"Web server started in detached mode (PID: {pid})."
                )
                click.secho(f"Success: {message}", fg="green")
            # In 'direct' mode, the process blocks, so the user will see the
            # server's own startup logs instead of a success message from us.

    except BSMError as e:
        click.secho(f"Failed to start web server: {e}", fg="red")
        raise click.Abort()


@web.command("stop")
def stop_web_server():
    """Stops the detached web server process.

    This command finds and terminates the web server process that was
    previously started in 'detached' mode.
    """
    click.echo("Attempting to stop the web server...")
    try:
        response = web_api.stop_web_server_api()
        # The API layer handles the logic (e.g., finding the PID file) and
        # returns a structured response that our utility can handle.
        _handle_api_response(response, "Web server stopped successfully.")
    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    web()
