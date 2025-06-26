# bedrock_server_manager/cli/web.py
"""
Defines the `bsm web` command group for managing the web server and its OS integrations.

This module contains the Click command group and subcommands for starting,
stopping, and managing the Flask-based web management interface, as well as
commands for managing its system service (e.g., systemd, Windows Services).
"""

import functools
import logging
import platform
import sys
from typing import Tuple, Callable, Optional, List, Any

import click
import questionary

from bedrock_server_manager.api import web as web_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.error import (
    BSMError,
    MissingArgumentError,
)

if platform.system() == "Windows":
    import win32serviceutil
    import servicemanager
    from bedrock_server_manager.core.system.windows_class import (
        WebServerWindowsService,
        PYWIN32_AVAILABLE,
    )

logger = logging.getLogger(__name__)


# --- Web System Service ---
def requires_web_service_manager(func: Callable) -> Callable:
    """A decorator that restricts a command to systems with a service manager for Web UI."""

    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx: click.Context, *args, **kwargs):
        bsm: BedrockServerManager = ctx.obj["bsm"]
        if not bsm.can_manag_service:
            os_type = bsm.get_os_type()
            if os_type == "Windows":
                msg = "Error: This command requires 'pywin32' to be installed (`pip install pywin32`)."
            else:
                msg = "Error: This command requires a service manager (like systemd), which was not found."
            click.secho(msg, fg="red")
            raise click.Abort()
        return func(*args, **kwargs)

    return wrapper


def _perform_web_service_configuration(
    bsm: BedrockServerManager,
    setup_service: Optional[bool],
    enable_autostart: Optional[bool],
):
    if not bsm.can_manage_services:
        click.secho(
            "System service manager not available. Skipping Web UI service configuration.",
            fg="yellow",
        )
        return

    if setup_service:

        enable_flag = enable_autostart if enable_autostart is not None else False
        os_type = bsm.get_os_type()
        click.secho(
            f"\n--- Configuring Web UI System Service ({os_type}) ---", bold=True
        )
        response = web_api.create_web_ui_service(autostart=enable_flag)
        _handle_api_response(response, "Web UI system service configured successfully.")
    elif enable_autostart is not None:
        click.echo("Applying autostart setting to existing Web UI service...")
        if enable_autostart:
            response = web_api.enable_web_ui_service()
            _handle_api_response(response, "Web UI service enabled successfully.")
        else:
            response = web_api.disable_web_ui_service()
            _handle_api_response(response, "Web UI service disabled successfully.")


def interactive_web_service_workflow(bsm: BedrockServerManager):
    click.secho("\n--- Interactive Web UI Service Configuration ---", bold=True)
    hosts_list_str: Optional[str] = None
    parsed_hosts: List[str] = []
    setup_service_choice = None
    enable_autostart_choice = None

    if bsm.can_manage_services:
        os_type = bsm.get_os_type()
        service_type_str = (
            "Systemd Service (Linux)" if os_type == "Linux" else "Windows Service"
        )
        click.secho(f"\n--- {service_type_str} for Web UI ---", bold=True)
        if os_type == "Windows":
            click.secho(
                "(Note: This requires running the command as an Administrator)",
                fg="yellow",
            )

        if questionary.confirm(
            f"Create or update the {service_type_str} for the Web UI?", default=True
        ).ask():
            setup_service_choice = True
            autostart_prompt = (
                "Enable the Web UI service to start automatically when you log in?"
                if os_type == "Linux"
                else "Enable the Web UI service to start automatically when the system boots?"
            )
            enable_autostart_choice = questionary.confirm(
                autostart_prompt, default=False
            ).ask()
    else:
        click.secho(
            "\nSystem service manager not available. Skipping Web UI service setup.",
            fg="yellow",
        )
        return

    if setup_service_choice is None:
        click.secho("No changes selected for Web UI service.", fg="cyan")
        return

    click.echo("\nApplying chosen settings for Web UI service...")
    try:
        _perform_web_service_configuration(
            bsm=bsm,
            setup_service=setup_service_choice,
            enable_autostart=enable_autostart_choice,
        )
        click.secho("\nWeb UI service configuration complete.", fg="green", bold=True)
    except BSMError as e:
        click.secho(f"Error during Web UI service configuration: {e}", fg="red")
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")


@click.group()
def web():
    """Manages the web UI and its OS service integrations.

    This command group provides utilities to start and stop the web-based
    management interface, and to configure it as a system service for
    autostart and background operation.
    """
    pass


@web.command("start")
@click.option(
    "-H",
    "--host",
    "hosts",
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
    # ... (docstring and existing code for start_web_server remains the same) ...
    """
    click.echo(f"Attempting to start web server in '{mode}' mode...")
    if mode == "direct":
        click.secho(
            "Server will run in this terminal. Press Ctrl+C to stop.", fg="cyan"
        )

    try:
        host_list = list(hosts)
        response = web_api.start_web_server_api(host_list, debug, mode)

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

    except BSMError as e:
        click.secho(f"Failed to start web server: {e}", fg="red")
        raise click.Abort()


@web.command("stop")
def stop_web_server():
    """Stops the detached web server process.
    # ... (docstring and existing code for stop_web_server remains the same) ...
    """
    click.echo("Attempting to stop the web server...")
    try:
        response = web_api.stop_web_server_api()
        _handle_api_response(response, "Web server stopped successfully.")
    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()


@web.group("service")
def web_service_group():
    """Manages OS-level service integrations for the Web UI."""
    pass


@web_service_group.command("configure")
@click.option(
    "--setup-service",
    is_flag=True,
    help="Create or update the system service file for the Web UI.",
)
@click.option(
    "--enable-autostart/--no-enable-autostart",
    "autostart_flag",
    default=None,
    help="Enable or disable Web UI service autostart.",
)
@click.pass_context
def configure_web_service(
    ctx: click.Context,
    setup_service: bool,
    autostart_flag: Optional[bool],
):
    """Configures OS-specific service settings for the Web UI.

    If run without flags, launches an interactive wizard.
    --host is required if --setup-service is used non-interactively.
    """
    bsm: BedrockServerManager = ctx.obj["bsm"]
    if setup_service and not bsm.can_manage_services:
        click.secho(
            "Error: --setup-service is not available (service manager not found).",
            fg="red",
        )
        raise click.Abort()

    try:
        no_flags_used = not setup_service and autostart_flag is None

        if no_flags_used:
            click.secho(
                "No flags provided; starting interactive Web UI service setup...",
                fg="yellow",
            )
            interactive_web_service_workflow(bsm)
            return

        click.secho("\nApplying Web UI service configuration...", bold=True)
        _perform_web_service_configuration(
            bsm=bsm,
            setup_service=setup_service,
            enable_autostart=autostart_flag,
        )
        click.secho("\nWeb UI configuration applied successfully.", fg="green")
    except MissingArgumentError as e:
        click.secho(f"Configuration Error: {e}", fg="red")
    except BSMError as e:
        click.secho(f"Operation failed: {e}", fg="red")
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")


@web_service_group.command("enable")
@requires_web_service_manager
def enable_web_service_cli():
    """Enables the Web UI system service to autostart."""
    click.echo("Attempting to enable Web UI system service...")
    try:
        response = web_api.enable_web_ui_service()
        _handle_api_response(response, "Web UI service enabled successfully.")
    except BSMError as e:
        click.secho(f"Failed to enable Web UI service: {e}", fg="red")
        raise click.Abort()


@web_service_group.command("disable")
@requires_web_service_manager
def disable_web_service_cli():
    """Disables the Web UI system service from autostarting."""
    click.echo("Attempting to disable Web UI system service...")
    try:
        response = web_api.disable_web_ui_service()
        _handle_api_response(response, "Web UI service disabled successfully.")
    except BSMError as e:
        click.secho(f"Failed to disable Web UI service: {e}", fg="red")
        raise click.Abort()


@web_service_group.command("remove")
@requires_web_service_manager
def remove_web_service_cli():
    """Removes the Web UI system service definition."""
    if not questionary.confirm(
        "Are you sure you want to remove the Web UI system service?", default=False
    ).ask():
        click.secho("Removal cancelled.", fg="yellow")
        return
    click.echo("Attempting to remove Web UI system service...")
    try:
        response = web_api.remove_web_ui_service()
        _handle_api_response(response, "Web UI service removed successfully.")
    except BSMError as e:
        click.secho(f"Failed to remove Web UI service: {e}", fg="red")
        raise click.Abort()


@web_service_group.command("status")
@requires_web_service_manager
def status_web_service_cli():
    """Checks the status of the Web UI system service."""
    click.echo("Checking Web UI system service status...")
    try:
        response = web_api.get_web_ui_service_status()
        if response.get("status") == "success":
            click.secho("Web UI Service Status:", bold=True)
            click.echo(
                f"  Service Defined: {click.style(str(response.get('service_exists', False)), fg='cyan')}"
            )
            if response.get("service_exists"):
                click.echo(
                    f"  Currently Active (Running): {click.style(str(response.get('is_active', False)), fg='green' if response.get('is_active') else 'red')}"
                )
                click.echo(
                    f"  Enabled for Autostart: {click.style(str(response.get('is_enabled', False)), fg='green' if response.get('is_enabled') else 'red')}"
                )
            if response.get("message"):
                click.secho(f"  Info: {response.get('message')}", fg="yellow")
        else:
            _handle_api_response(response)
    except BSMError as e:
        click.secho(f"Failed to get Web UI service status: {e}", fg="red")
        raise click.Abort()
