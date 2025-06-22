# bedrock_server_manager/cli/plugins.py
"""
Defines the `bsm plugin` command group for managing plugin configurations.
"""
import logging
from typing import Optional

import click
import questionary

from bedrock_server_manager.api import plugins as plugins_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError, UserInputError

logger = logging.getLogger(__name__)


def interactive_plugin_workflow():
    """
    Guides the user through an interactive session to enable or disable plugins.

    Fetches all discoverable plugins, displays them in a checklist with their
    current status, and allows the user to change their configuration.
    """
    click.echo("Fetching plugin statuses...")
    try:
        # 1. Fetch current state
        response = plugins_api.get_plugin_statuses()
        if response.get("status") != "success":
            _handle_api_response(response, "Failed to retrieve plugin statuses.")
            return

        plugins = response.get("plugins", {})
        if not plugins:
            click.secho("No plugins found or configured to edit.", fg="yellow")
            return

        click.secho("\n--- Interactive Plugin Configuration ---", bold=True)
        click.secho("Use SPACE to toggle, ENTER to confirm.", fg="cyan")

        # 2. Prepare choices for questionary
        initial_enabled_plugins = {
            name for name, is_enabled in plugins.items() if is_enabled
        }
        choices = [
            questionary.Choice(
                title=name, value=name, checked=is_enabled
            )
            for name, is_enabled in sorted(plugins.items())
        ]

        # 3. Prompt the user
        selected_plugins_list = questionary.checkbox(
            "Select the plugins you want to be enabled:",
            choices=choices,
        ).ask()

        # Handle cancellation (user pressed Ctrl+C)
        if selected_plugins_list is None:
            raise click.Abort()

        # 4. Determine changes
        final_enabled_plugins = set(selected_plugins_list)
        plugins_to_enable = final_enabled_plugins - initial_enabled_plugins
        plugins_to_disable = initial_enabled_plugins - final_enabled_plugins

        if not plugins_to_enable and not plugins_to_disable:
            click.secho("No changes made.", fg="cyan")
            return

        # 5. Apply changes
        click.echo("\nApplying changes...")
        for name in sorted(plugins_to_enable):
            click.echo(f"Enabling plugin '{name}'... ", nl=False)
            api_response = plugins_api.set_plugin_status(name, True)
            if api_response.get("status") == "success":
                click.secho("OK", fg="green")
            else:
                click.secho(f"Failed: {api_response.get('message')}", fg="red")

        for name in sorted(plugins_to_disable):
            click.echo(f"Disabling plugin '{name}'... ", nl=False)
            api_response = plugins_api.set_plugin_status(name, False)
            if api_response.get("status") == "success":
                click.secho("OK", fg="green")
            else:
                click.secho(f"Failed: {api_response.get('message')}", fg="red")

        click.secho("\nPlugin configuration updated.", fg="green")

    except (BSMError, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")
    except click.Abort:
        # click.Abort is raised by questionary on Ctrl+C, handle it quietly.
        click.secho("\nOperation cancelled.", fg="yellow")


@click.group()
def plugin():
    """Manages plugin configurations (enable/disable)."""
    pass


@plugin.command("list")
def list_plugins():
    """Lists all discoverable plugins and their current status (enabled/disabled)."""
    click.echo("Fetching plugin statuses...")
    try:
        response = plugins_api.get_plugin_statuses()
        if response.get("status") == "success":
            plugins = response.get("plugins", {})
            if not plugins:
                click.secho("No plugins found or configured.", fg="yellow")
                return

            click.secho("Plugin Statuses:", bold=True)
            # Determine column widths for formatting
            max_name_len = max(len(name) for name in plugins.keys()) if plugins else 20
            max_status_len = len("Disabled")  # "Enabled" or "Disabled"

            header = f"{'Plugin Name':<{max_name_len}} | {'Status':<{max_status_len}}"
            click.secho(header, underline=True)
            click.secho("-" * len(header))

            for name, is_enabled in sorted(plugins.items()):
                status_str = "Enabled" if is_enabled else "Disabled"
                status_color = "green" if is_enabled else "red"
                click.echo(f"{name:<{max_name_len}} | ", nl=False)
                click.secho(f"{status_str:<{max_status_len}}", fg=status_color)
        else:
            _handle_api_response(response, "Failed to retrieve plugin statuses.")

    except BSMError as e:
        click.secho(f"Error listing plugins: {e}", fg="red")


@plugin.command("edit")
def edit_plugins():
    """Opens an interactive menu to enable or disable multiple plugins."""
    interactive_plugin_workflow()


@plugin.command("enable")
@click.argument("plugin_name", required=False)
def enable_plugin(plugin_name: Optional[str]):
    """
    Enables a specific plugin.

    If no plugin name is provided, opens an interactive editor to manage all plugins.
    """
    if not plugin_name:
        click.secho("No plugin specified; launching interactive editor.", fg="yellow")
        interactive_plugin_workflow()
        return

    click.echo(f"Attempting to enable plugin '{plugin_name}'...")
    try:
        response = plugins_api.set_plugin_status(plugin_name, True)
        _handle_api_response(response, f"Plugin '{plugin_name}' enabled successfully.")
    except UserInputError as e:  # Catch specific error for plugin not found
        click.secho(f"Error: {e}", fg="red")
    except BSMError as e:
        click.secho(f"Failed to enable plugin '{plugin_name}': {e}", fg="red")


@plugin.command("disable")
@click.argument("plugin_name", required=False)
def disable_plugin(plugin_name: Optional[str]):
    """
    Disables a specific plugin.

    If no plugin name is provided, opens an interactive editor to manage all plugins.
    """
    if not plugin_name:
        click.secho("No plugin specified; launching interactive editor.", fg="yellow")
        interactive_plugin_workflow()
        return

    click.echo(f"Attempting to disable plugin '{plugin_name}'...")
    try:
        response = plugins_api.set_plugin_status(plugin_name, False)
        _handle_api_response(response, f"Plugin '{plugin_name}' disabled successfully.")
    except UserInputError as e:  # Catch specific error for plugin not found
        click.secho(f"Error: {e}", fg="red")
    except BSMError as e:
        click.secho(f"Failed to disable plugin '{plugin_name}': {e}", fg="red")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    plugin()