# bedrock_server_manager/cli/plugins.py
"""
Defines the `bsm plugin` command group for managing plugin configurations.
"""
import logging
from typing import Dict, Optional

import click
import questionary
from click.core import Context

from bedrock_server_manager.api import plugins as plugins_api
from bedrock_server_manager.config.const import app_name_title
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError, UserInputError

logger = logging.getLogger(__name__)


def _print_plugin_table(plugins: Dict[str, bool]):
    """
    Prints a formatted table of plugins and their statuses.

    Args:
        plugins: A dictionary mapping plugin names to their enabled status (bool).
    """
    if not plugins:
        click.secho("No plugins found or configured.", fg="yellow")
        return

    click.secho(f"{app_name_title} - Plugin Statuses", fg="magenta", bold=True)
    max_name_len = max(len(name) for name in plugins.keys()) if plugins else 20
    max_status_len = len("Disabled")

    header = f"{'Plugin Name':<{max_name_len}} | {'Status':<{max_status_len}}"
    click.secho(header, underline=True)
    click.secho("-" * len(header))

    for name, is_enabled in sorted(plugins.items()):
        status_str = "Enabled" if is_enabled else "Disabled"
        status_color = "green" if is_enabled else "red"
        click.echo(f"{name:<{max_name_len}} | ", nl=False)
        click.secho(f"{status_str:<{max_status_len}}", fg=status_color)


def interactive_plugin_workflow():
    """
    Guides the user through an interactive session to enable or disable plugins.

    Fetches all discoverable plugins, displays them in a checklist with their
    current status, allows the user to change their configuration, and shows
    the final state.
    """
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

        # 2. Display current plugin statuses
        _print_plugin_table(plugins)

        # 3. Prepare choices for questionary
        initial_enabled_plugins = {
            name for name, is_enabled in plugins.items() if is_enabled
        }
        choices = [
            questionary.Choice(title=name, value=name, checked=is_enabled)
            for name, is_enabled in sorted(plugins.items())
        ]
        cancel_choice_text = "Cancel (no changes will be made)"
        choices.extend([cancel_choice_text])

        # 4. Prompt the user
        selected_plugins_list = questionary.checkbox(
            "Select the plugins you want to toggle:", choices=choices
        ).ask()

        # Handle cancellation
        if selected_plugins_list is None or cancel_choice_text in selected_plugins_list:
            click.secho("\nOperation cancelled by user.", fg="yellow")
            return

        # 5. Determine changes
        final_enabled_plugins = set(selected_plugins_list)
        plugins_to_enable = final_enabled_plugins - initial_enabled_plugins
        plugins_to_disable = initial_enabled_plugins - final_enabled_plugins

        if not plugins_to_enable and not plugins_to_disable:
            click.secho("No changes made.", fg="cyan")
            _print_plugin_table(plugins)
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

        # 7. Display final status table
        final_response = plugins_api.get_plugin_statuses()
        if final_response.get("status") == "success":
            _print_plugin_table(final_response.get("plugins", {}))
        else:
            click.secho("Could not retrieve final plugin statuses.", fg="yellow")

    except (BSMError, KeyboardInterrupt, click.Abort):
        click.secho("\nOperation cancelled.", fg="yellow")


@click.group(invoke_without_command=True)
@click.pass_context
def plugin(ctx: Context):
    """
    Manages plugins. Runs interactively if no subcommand is given.
    """
    # If no subcommand is invoked (e.g., just 'bsm plugin'), run the interactive workflow
    if ctx.invoked_subcommand is None:
        click.secho(
            "No subcommand specified; launching interactive editor.", fg="yellow"
        )
        interactive_plugin_workflow()


@plugin.command("list")
def list_plugins():
    """Lists all discoverable plugins and their current status (enabled/disabled)."""
    try:
        response = plugins_api.get_plugin_statuses()
        if response.get("status") == "success":
            plugins = response.get("plugins", {})
            _print_plugin_table(plugins)
        else:
            _handle_api_response(response, "Failed to retrieve plugin statuses.")
    except BSMError as e:
        click.secho(f"Error listing plugins: {e}", fg="red")


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
    except UserInputError as e:
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
    except UserInputError as e:
        click.secho(f"Error: {e}", fg="red")
    except BSMError as e:
        click.secho(f"Failed to disable plugin '{plugin_name}': {e}", fg="red")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    plugin()
