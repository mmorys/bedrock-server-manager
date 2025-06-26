# bedrock_server_manager/cli/system.py
"""Defines the `bsm system` command group for OS-level server integrations.

This module provides commands to create and manage OS services (e.g.,
systemd on Linux, Windows Services on Windows) for autostarting servers and to
monitor the resource usage (CPU, memory) of running server processes. It
intelligently adapts to the host system's capabilities, enabling or disabling
features as needed.
"""

import functools
import logging
import time
import platform
import sys
from typing import Callable, Optional, Any

import click
import questionary

from bedrock_server_manager.api import system as system_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.error import BSMError

if platform.system() == "Windows":
    from bedrock_server_manager.core.system.windows_class import (
        BedrockServerWindowsService,
        PYWIN32_AVAILABLE,
    )

    if PYWIN32_AVAILABLE:
        import win32serviceutil
        import servicemanager

logger = logging.getLogger(__name__)


def requires_service_manager(func: Callable) -> Callable:
    """A decorator that restricts a command to systems with a service manager.

    This decorator checks the central `BedrockServerManager` instance to see
    if a known service manager is available (systemd on Linux, pywin32 on Windows).

    Args:
        func: The Click command function to wrap.

    Returns:
        The wrapped function, which will first perform the capability check.
    """

    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx: click.Context, *args, **kwargs):
        """Wrapper that performs the capability check before execution."""
        bsm: BedrockServerManager = ctx.obj["bsm"]
        if not bsm.can_manage_services:
            os_type = bsm.get_os_type()
            if os_type == "Windows":
                msg = "Error: This command requires 'pywin32' to be installed (`pip install pywin32`)."
            else:
                msg = "Error: This command requires a service manager (like systemd), which was not found."
            click.secho(msg, fg="red")
            raise click.Abort()
        return func(*args, **kwargs)

    return wrapper


def _perform_service_configuration(
    bsm: BedrockServerManager,
    server_name: str,
    autoupdate: Optional[bool],
    setup_service: Optional[bool],
    enable_autostart: Optional[bool],
):
    """Applies service configurations by calling the system API.

    This non-interactive function is the backend for all configuration actions.
    It only acts on settings that are not None and respects the system's
    detected capabilities.

    Args:
        bsm: The central BedrockServerManager instance.
        server_name: The name of the server to configure.
        autoupdate: The desired state for autoupdate.
        setup_service: If True, creates/updates the system service.
        enable_autostart: Sets the system service autostart state.

    Raises:
        BSMError: If any of the underlying API calls fail.
    """
    if autoupdate is not None:
        autoupdate_value = "true" if autoupdate else "false"
        response = system_api.set_autoupdate(server_name, autoupdate_value)
        _handle_api_response(
            response, f"Autoupdate setting configured to '{autoupdate_value}'."
        )

    # Only proceed with service configuration if the capability exists.
    if bsm.can_manage_services:
        if setup_service:
            enable_flag = enable_autostart if enable_autostart is not None else False
            os_type = bsm.get_os_type()
            click.secho(f"\n--- Configuring System Service ({os_type}) ---", bold=True)
            response = system_api.create_server_service(server_name, enable_flag)
            _handle_api_response(response, "System service configured successfully.")
        elif enable_autostart is not None:
            # Handle enabling/disabling an existing service if setup is not requested.
            click.echo("Applying autostart setting to existing service...")
            if enable_autostart:
                response = system_api.enable_server_service(server_name)
                _handle_api_response(response, "Service enabled successfully.")
            else:
                response = system_api.disable_server_service(server_name)
                _handle_api_response(response, "Service disabled successfully.")


def interactive_service_workflow(bsm: BedrockServerManager, server_name: str):
    """Guides the user through an interactive session to configure services.

    Args:
        bsm: The central BedrockServerManager instance.
        server_name: The name of the server being configured.
    """
    click.secho(
        f"\n--- Interactive Service Configuration for '{server_name}' ---", bold=True
    )

    # 1. Gather Autoupdate preference.
    autoupdate_choice = questionary.confirm(
        "Enable check for updates when the server starts?", default=False
    ).ask()

    # 2. Gather system service preferences, only if available.
    setup_service_choice = None
    enable_autostart_choice = None
    if bsm.can_manage_services:
        os_type = bsm.get_os_type()
        service_type_str = (
            "Systemd Service (Linux)" if os_type == "Linux" else "Windows Service"
        )
        click.secho(f"\n--- {service_type_str} ---", bold=True)
        if os_type == "Windows":
            click.secho(
                "(Note: This requires running the command as an Administrator)",
                fg="yellow",
            )

        if questionary.confirm(
            f"Create or update the {service_type_str} for this server?",
            default=True,
        ).ask():
            setup_service_choice = True
            autostart_prompt = (
                "Enable the service to start automatically when you log in?"
                if os_type == "Linux"
                else "Enable the service to start automatically when the system boots?"
            )
            enable_autostart_choice = questionary.confirm(
                autostart_prompt,
                default=False,
            ).ask()
    else:
        click.secho(
            "\nSystem service manager not available. Skipping service setup.",
            fg="yellow",
        )

    # 3. Execute the configuration.
    if autoupdate_choice is None and setup_service_choice is None:
        click.secho("No changes selected.", fg="cyan")
        return

    click.echo("\nApplying chosen settings...")
    _perform_service_configuration(
        bsm=bsm,
        server_name=server_name,
        autoupdate=autoupdate_choice,
        setup_service=setup_service_choice,
        enable_autostart=enable_autostart_choice,
    )
    click.secho("\nService configuration complete.", fg="green", bold=True)


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
    "--setup-service",
    is_flag=True,
    help="Create or update the system service file (systemd/Windows Service).",
)
@click.option(
    "--enable-autostart/--no-enable-autostart",
    "autostart_flag",
    default=None,
    help="Enable or disable the system service to start on boot/login.",
)
@click.pass_context
def configure_service(
    ctx: click.Context,
    server_name: str,
    autoupdate_flag: Optional[bool],
    setup_service: bool,
    autostart_flag: Optional[bool],
):
    """Configures OS-specific service settings for a server.

    If run without configuration flags, this command launches an interactive
    wizard to guide you through the setup. If any flags are used, it applies
    the specified settings directly, making it suitable for scripting.
    """
    bsm: BedrockServerManager = ctx.obj["bsm"]

    # Add a guard clause to prevent misuse of flags on incapable systems.
    if setup_service and not bsm.can_manage_services:
        click.secho(
            "Error: --setup-service flag is not available because a service manager was not found.",
            fg="red",
        )
        return

    try:
        no_flags_used = (
            autoupdate_flag is None and not setup_service and autostart_flag is None
        )
        if no_flags_used:
            click.secho(
                "No configuration flags provided; starting interactive setup...",
                fg="yellow",
            )
            interactive_service_workflow(bsm, server_name)
            return

        click.secho(
            f"\nApplying service configuration for '{server_name}'...", bold=True
        )
        _perform_service_configuration(
            bsm=bsm,
            server_name=server_name,
            autoupdate=autoupdate_flag,
            setup_service=setup_service,
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
@requires_service_manager
def enable_service(server_name: str):
    """Enables the system service to autostart at boot/login."""
    click.echo(f"Attempting to enable system service for '{server_name}'...")
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
@requires_service_manager
def disable_service(server_name: str):
    """Disables the system service from autostarting at boot/login."""
    click.echo(f"Attempting to disable system service for '{server_name}'...")
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


@system.command(
    "_run-service",
    hidden=True,
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    ),
)
@click.option("-s", "--server", "server_name", required=True)
@click.pass_context
def _run_service(ctx, server_name: str):
    """
    (Internal use only) Entry point for the Windows Service Manager.
    """
    if platform.system() == "Windows" and PYWIN32_AVAILABLE:

        class ServiceHandler(BedrockServerWindowsService):
            _svc_name_ = f"bedrock-{server_name}"
            _svc_display_name_ = f"Bedrock Server ({server_name})"

        if "debug" in ctx.args:
            # Debug mode runs the service logic in the console and blocks.
            logger.info(f"Starting service '{server_name}' in DEBUG mode.")
            win32serviceutil.DebugService(ServiceHandler, argv=[f"bedrock-{server_name}"])
        else:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(ServiceHandler)
            servicemanager.StartServiceCtrlDispatcher()
    else:
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    system()
