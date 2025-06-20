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
from typing import Callable, Optional

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


def _perform_service_configuration(
    server_name: str,
    autoupdate: Optional[bool],
    setup_systemd: Optional[bool],
    enable_autostart: Optional[bool],
):
    """
    Core logic to apply service configurations by calling the system API.

    This non-interactive function is the backend for all configuration actions.
    It only acts on settings that are not None.

    Args:
        server_name: The name of the server to configure.
        autoupdate: The desired state for autoupdate, or None to ignore.
        setup_systemd: If True, creates/updates the systemd service. If None, ignores.
        enable_autostart: Sets the systemd service autostart state. If None, ignores.

    Raises:
        BSMError: If any of the underlying API calls fail.
    """
    if autoupdate is not None:
        autoupdate_value = "true" if autoupdate else "false"
        response = system_api.set_autoupdate(server_name, autoupdate_value)
        _handle_api_response(
            response, f"Autoupdate setting configured to '{autoupdate_value}'."
        )

    os_name = platform.system()
    if os_name == "Linux":
        if setup_systemd:
            enable_flag = enable_autostart if enable_autostart is not None else False
            click.secho("\n--- Configuring Systemd Service (Linux) ---", bold=True)
            response = system_api.create_systemd_service(server_name, enable_flag)
            _handle_api_response(response, "Systemd service configured successfully.")
        elif enable_autostart is not None:
            # Handle enabling/disabling an existing service if setup is not requested
            if enable_autostart:
                enable_service(server_name, _called_internally=True)
            else:
                disable_service(server_name, _called_internally=True)


def interactive_service_workflow(server_name: str):
    """Guides the user through an interactive session to configure services."""
    os_name = platform.system()
    if os_name not in ("Windows", "Linux"):
        click.secho(
            f"Automated service configuration is not supported on this OS ({os_name}).",
            fg="red",
        )
        return

    click.secho(
        f"\n--- Interactive Service Configuration for '{server_name}' ---", bold=True
    )

    # 1. Gather Autoupdate preference
    autoupdate_choice = questionary.confirm(
        "Enable check for updates when the server starts?", default=False
    ).ask()

    # 2. Gather Linux Systemd preferences
    setup_systemd_choice = None
    enable_autostart_choice = None
    if os_name == "Linux":
        click.secho("\n--- Systemd Service (Linux) ---", bold=True)
        if questionary.confirm(
            "Create or update the systemd service file for this server?", default=True
        ).ask():
            setup_systemd_choice = True
            enable_autostart_choice = questionary.confirm(
                "Enable the service to start automatically when you log in?",
                default=False,
            ).ask()

    # 3. Execute the configuration
    if autoupdate_choice is None and setup_systemd_choice is None:
        click.secho("No changes selected.", fg="cyan")
        return

    click.echo("\nApplying chosen settings...")
    _perform_service_configuration(
        server_name=server_name,
        autoupdate=autoupdate_choice,
        setup_systemd=setup_systemd_choice,
        enable_autostart=enable_autostart_choice,
    )
    click.secho("\nService configuration complete.", fg="green", bold=True)


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
@click.option(
    "--autoupdate/--no-autoupdate",
    "autoupdate_flag",
    default=None,
    help="Enable or disable checking for updates on server start.",
)
@click.option(
    "--setup-systemd",
    is_flag=True,
    help="[Linux Only] Create or update the systemd service file.",
)
@click.option(
    "--enable-autostart/--no-enable-autostart",
    "autostart_flag",
    default=None,
    help="[Linux Only] Enable or disable the systemd service to start on login.",
)
def configure_service(
    server_name: str,
    autoupdate_flag: Optional[bool],
    setup_systemd: bool,
    autostart_flag: Optional[bool],
):
    """Configures OS-specific service settings for a server.

    If run without configuration flags, this command launches an interactive
    wizard to guide you through the setup. If any flags are used, it applies
    the specified settings directly, making it suitable for scripting.
    """
    try:
        # Check if any flags were used. If not, launch the interactive workflow.
        no_flags_used = (
            autoupdate_flag is None and not setup_systemd and autostart_flag is None
        )
        if no_flags_used:
            click.secho(
                "No configuration flags provided; starting interactive setup...",
                fg="yellow",
            )
            interactive_service_workflow(server_name)
            return

        # Direct, non-interactive logic
        click.secho(
            f"\nApplying service configuration for '{server_name}'...", bold=True
        )
        _perform_service_configuration(
            server_name=server_name,
            autoupdate=autoupdate_flag,
            setup_systemd=setup_systemd,
            enable_autostart=autostart_flag,
        )
        click.secho("\nConfiguration applied successfully.", fg="green")

    except (BSMError, click.Abort, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")


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
