# bedrock_server_manager/cli/system.py
"""
Click command group for system-level operations related to servers.

Provides commands to create/configure OS services and monitor resource usage.
"""

import time
import logging
import platform
from typing import Dict, Any

import click
import questionary

from bedrock_server_manager.api import system as system_api
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
def system():
    """Commands for OS-level integrations and monitoring."""
    pass


@system.command("configure-service")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server to configure.",
)
def configure_service(server_name: str):
    """Interactively configure OS-specific service settings."""
    os_name = platform.system()
    if os_name not in ("Windows", "Linux"):
        click.secho(
            f"Automated service configuration is not supported on this OS ({os_name}).",
            fg="red",
        )
        return

    try:
        click.secho(f"--- Configuring Service for '{server_name}' ---", bold=True)

        # 1. Autoupdate (Common to both OSes)
        enable_autoupdate = questionary.confirm(
            "Enable check for updates on server start?", default=False
        ).ask()
        if enable_autoupdate is None:
            raise click.Abort()

        autoupdate_value = "true" if enable_autoupdate else "false"
        autoupdate_response = system_api.set_autoupdate(server_name, autoupdate_value)
        _handle_api_response(autoupdate_response, "Autoupdate setting configured.")

        # 2. Autostart (Linux only)
        if os_name == "Linux":
            click.secho("\n--- Configuring systemd Service (Linux) ---", bold=True)
            enable_autostart = questionary.confirm(
                "Enable service to start automatically on system boot?", default=False
            ).ask()
            if enable_autostart is None:
                raise click.Abort()

            autostart_response = system_api.create_systemd_service(
                server_name, enable_autoupdate, enable_autostart
            )
            _handle_api_response(autostart_response, "Systemd service configured.")

        click.secho("\nService configuration complete.", fg="green", bold=True)

    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nConfiguration cancelled.", fg="yellow")


@system.command("enable-service")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the server."
)
def enable_service(server_name: str):
    """Enables the systemd service to autostart (Linux only)."""
    if platform.system() != "Linux":
        click.secho("This command is only available on Linux.", fg="red")
        return

    click.echo(f"Attempting to enable service for '{server_name}'...")
    try:
        response = system_api.enable_server_service(server_name)
        _handle_api_response(response, "Service enabled successfully.")
    except BSMError as e:
        click.secho(f"Failed to enable service: {e}", fg="red")
        raise click.Abort()


@system.command("disable-service")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the server."
)
def disable_service(server_name: str):
    """Disables the systemd service from autostarting (Linux only)."""
    if platform.system() != "Linux":
        click.secho("This command is only available on Linux.", fg="red")
        return

    click.echo(f"Attempting to disable service for '{server_name}'...")
    try:
        response = system_api.disable_server_service(server_name)
        _handle_api_response(response, "Service disabled successfully.")
    except BSMError as e:
        click.secho(f"Failed to disable service: {e}", fg="red")
        raise click.Abort()


@system.command("monitor")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server to monitor.",
)
def monitor_usage(server_name: str):
    """Continuously monitor CPU and memory usage of a server."""
    click.secho(f"Starting resource monitoring for server '{server_name}'.", fg="cyan")
    click.echo("Press CTRL+C to exit.")
    time.sleep(1)

    try:
        while True:
            response = system_api.get_bedrock_process_info(server_name)

            click.clear()  # The idiomatic way to clear the screen
            click.secho(
                f"--- Monitoring Server: {server_name} ---", fg="magenta", bold=True
            )
            click.echo(
                f"(Last updated: {time.strftime('%H:%M:%S')}, Press CTRL+C to exit)\n"
            )

            if response.get("status") == "error":
                click.secho(f"Error: {response.get('message')}", fg="red")
            elif response.get("process_info") is None:
                click.secho("Server process not found (likely stopped).", fg="yellow")
            else:
                info = response["process_info"]
                click.echo(f"  {'PID':<12}: {info.get('pid', 'N/A')}")
                click.echo(f"  {'CPU Usage':<12}: {info.get('cpu_percent', 0.0):.1f}%")
                click.echo(
                    f"  {'Memory Usage':<12}: {info.get('memory_mb', 0.0):.1f} MB"
                )
                click.echo(f"  {'Uptime':<12}: {info.get('uptime', 'N/A')}")

            time.sleep(2)
    except (KeyboardInterrupt, click.Abort):
        click.secho("\nMonitoring stopped.", fg="green")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    system()
