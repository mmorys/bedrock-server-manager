# bedrock_server_manager/cli/system.py
"""
Defines the `bsm system` command group for OS-level server integrations.

This module provides commands to create and manage OS services (e.g.,
systemd on Linux) for autostarting servers and to monitor the resource
usage (CPU, memory) of running server processes.
"""

import functools
import logging
import platform
import time
from typing import Callable

import click
import questionary

from bedrock_server_manager.api import system as system_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


# --- Custom Decorator for OS-specific commands ---


def linux_only(func: Callable) -> Callable:
    """A decorator that restricts a Click command to run only on Linux."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if platform.system() != "Linux":
            click.secho(
                f"Error: The '{func.__name__.replace('_', '-')}' command is only available on Linux.",
                fg="red",
            )
            raise click.Abort()
        return func(*args, **kwargs)

    return wrapper


# --- Click Command Group ---


@click.group()
def system():
    """Manages OS-level integrations and server monitoring."""
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
    """Interactively configures OS-specific service settings.

    This command guides you through setting up system integrations like
    auto-updating and auto-starting for a server. The available options
    depend on your operating system (e.g., systemd for Linux).

    Args:
        server_name: The name of the server to configure.

    Raises:
        click.Abort: If the user cancels or an error occurs.
    """
    os_name = platform.system()
    if os_name not in ("Windows", "Linux"):
        click.secho(
            f"Automated service configuration is not supported on this OS ({os_name}).",
            fg="red",
        )
        return

    try:
        click.secho(f"\n--- Service Configuration for '{server_name}' ---", bold=True)
        autoupdate_value = "false"

        # 1. Autoupdate (Common to Windows & Linux)
        if questionary.confirm(
            "Enable check for updates when the server starts?", default=False
        ).ask():
            autoupdate_value = "true"

        autoupdate_response = system_api.set_autoupdate(server_name, autoupdate_value)
        _handle_api_response(
            autoupdate_response,
            f"Autoupdate setting configured to '{autoupdate_value}'.",
        )

        # 2. Autostart (Linux-only systemd service)
        if os_name == "Linux":
            click.secho("\n--- Systemd Service (Linux) ---", bold=True)
            if questionary.confirm(
                "Create/update systemd service file now?", default=True
            ).ask():
                enable_autostart = questionary.confirm(
                    "Enable the service to start automatically on system boot?",
                    default=False,
                ).ask()

                autostart_response = system_api.create_systemd_service(
                    server_name, enable_autostart
                )
                _handle_api_response(
                    autostart_response, "Systemd service configured successfully."
                )

        click.secho("\nService configuration complete.", fg="green", bold=True)

    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nConfiguration cancelled.", fg="yellow")


@system.command("enable-service")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server service to enable.",
)
@linux_only
def enable_service(server_name: str):
    """Enables the systemd service to autostart at boot (Linux only)."""
    click.echo(f"Attempting to enable systemd service for '{server_name}'...")
    try:
        response = system_api.enable_server_service(server_name)
        _handle_api_response(response, "Service enabled successfully.")
    except BSMError as e:
        click.secho(f"Failed to enable service: {e}", fg="red")
        raise click.Abort()


@system.command("disable-service")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server service to disable.",
)
@linux_only
def disable_service(server_name: str):
    """Disables the systemd service from autostarting at boot (Linux only)."""
    click.echo(f"Attempting to disable systemd service for '{server_name}'...")
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
    """Continuously monitors CPU and memory usage of a server process."""
    click.secho(
        f"Starting resource monitoring for server '{server_name}'. Press CTRL+C to exit.",
        fg="cyan",
    )
    time.sleep(1)

    try:
        while True:
            response = system_api.get_bedrock_process_info(server_name)

            click.clear()
            click.secho(
                f"--- Monitoring Server: {server_name} ---", fg="magenta", bold=True
            )
            click.echo(
                f"(Last updated: {time.strftime('%H:%M:%S')}, Press CTRL+C to exit)\n"
            )

            if response.get("status") == "error":
                click.secho(f"Error: {response.get('message')}", fg="red")
            elif response.get("process_info") is None:
                click.secho("Server process not found (is it running?).", fg="yellow")
            else:
                info = response["process_info"]
                pid_str = info.get("pid", "N/A")
                cpu_str = f"{info.get('cpu_percent', 0.0):.1f}%"
                mem_str = f"{info.get('memory_mb', 0.0):.1f} MB"
                uptime_str = info.get("uptime", "N/A")

                click.echo(f"  {'PID':<15}: {click.style(str(pid_str), fg='cyan')}")
                click.echo(f"  {'CPU Usage':<15}: {click.style(cpu_str, fg='green')}")
                click.echo(
                    f"  {'Memory Usage':<15}: {click.style(mem_str, fg='green')}"
                )
                click.echo(f"  {'Uptime':<15}: {click.style(uptime_str, fg='white')}")

            time.sleep(2)
    except (KeyboardInterrupt, click.Abort):
        click.secho("\nMonitoring stopped.", fg="green")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    system()
