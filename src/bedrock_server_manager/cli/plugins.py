# bedrock_server_manager/cli/plugins.py
"""
Defines the `bsm plugin` command group for managing plugin configurations.
"""
import logging
from typing import Dict, Optional, Any

import click
import questionary
from click.core import Context

# Make sure this import points to your API functions module
from bedrock_server_manager.api import plugins as plugins_api
from bedrock_server_manager.config.const import app_name_title
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError, UserInputError

logger = logging.getLogger(__name__)


def _print_plugin_table(plugins: Dict[str, Dict[str, Any]]):
    """
    Prints a formatted table of plugins, their statuses, and versions.
    """
    if not plugins:
        click.secho("No plugins found or configured.", fg="yellow")
        return

    click.secho(
        f"{app_name_title} - Plugin Statuses & Versions", fg="magenta", bold=True
    )

    plugin_names = list(plugins.keys())
    versions = [config.get("version", "N/A") for config in plugins.values()]

    max_name_len = max(len(name) for name in plugin_names) if plugin_names else 20
    max_version_len = max(
        (max(len(v) for v in versions) if versions else 0), len("Version")
    )
    max_status_len = len("Disabled")

    header = f"{'Plugin Name':<{max_name_len}} | {'Status':<{max_status_len}} | {'Version':<{max_version_len}}"
    click.secho(header, underline=True)
    click.secho("-" * len(header))

    for name, config in sorted(plugins.items()):
        is_enabled = config.get("enabled", False)
        version = config.get("version", "N/A")

        status_str = "Enabled" if is_enabled else "Disabled"
        status_color = "green" if is_enabled else "red"

        click.echo(f"{name:<{max_name_len}} | ", nl=False)
        click.secho(f"{status_str:<{max_status_len}}", fg=status_color, nl=False)
        click.echo(f" | {version:<{max_version_len}}")


def interactive_plugin_workflow():
    """
    Guides the user through an interactive session to enable or disable plugins.
    """
    try:
        response = plugins_api.get_plugin_statuses()
        if response.get("status") != "success":
            _handle_api_response(
                response, error_message_prefix="Failed to retrieve plugin statuses"
            )
            return

        plugins: Dict[str, Dict[str, Any]] = response.get(
            "plugins", {}
        )  # plugins is Dict[str, Dict]
        if not plugins:
            click.secho("No plugins found or configured to edit.", fg="yellow")
            return

        _print_plugin_table(plugins)
        click.echo()
        initial_enabled_plugins = {
            name
            for name, config_dict in plugins.items()
            if config_dict.get("enabled", False)
        }

        choices = []
        for name, config_dict in sorted(plugins.items()):
            is_enabled = config_dict.get("enabled", False)
            version = config_dict.get("version", "N/A")
            choice_title = f"{name} (v{version})"  # Display version in choice
            choices.append(
                questionary.Choice(title=choice_title, value=name, checked=is_enabled)
            )

        selected_plugin_names_list = questionary.checkbox(
            "Toggle plugins (space to select, enter to confirm):", choices=choices
        ).ask()

        if selected_plugin_names_list is None:
            click.secho("\nOperation cancelled by user.", fg="yellow")
            return

        final_enabled_plugins = set(selected_plugin_names_list)
        plugins_to_enable = final_enabled_plugins - initial_enabled_plugins
        plugins_to_disable = initial_enabled_plugins - final_enabled_plugins

        if not plugins_to_enable and not plugins_to_disable:
            click.secho("No changes made.", fg="cyan")
            _print_plugin_table(plugins)
            return

        click.echo("\nApplying changes...")
        changes_made = False
        for name in sorted(plugins_to_enable):
            click.echo(f"Enabling plugin '{name}'... ", nl=False)
            api_response = plugins_api.set_plugin_status(name, True)
            if api_response.get("status") == "success":
                click.secho("OK", fg="green")
                changes_made = True
            else:
                click.secho(f"Failed: {api_response.get('message')}", fg="red")

        for name in sorted(plugins_to_disable):
            click.echo(f"Disabling plugin '{name}'... ", nl=False)
            api_response = plugins_api.set_plugin_status(name, False)
            if api_response.get("status") == "success":
                click.secho("OK", fg="green")
                changes_made = True
            else:
                click.secho(f"Failed: {api_response.get('message')}", fg="red")

        if changes_made:
            try:
                click.secho("\nReloading plugins...", fg="cyan")
                plugins_api.reload_plugins()  # Reload plugins after changes
            except BSMError as e:
                click.secho(f"\nError reloading plugins: {e}", fg="red")
            click.secho("\nPlugin configuration updated.", fg="green")
        else:
            click.secho("\nNo changes were successfully applied.", fg="yellow")

        final_response = plugins_api.get_plugin_statuses()
        if final_response.get("status") == "success":
            _print_plugin_table(final_response.get("plugins", {}))
        else:
            click.secho("Could not retrieve final plugin statuses.", fg="yellow")

    except (BSMError, KeyboardInterrupt, click.Abort) as e:
        if isinstance(e, KeyboardInterrupt) or isinstance(e, click.Abort):
            click.secho("\nOperation cancelled by user.", fg="yellow")
        else:
            click.secho(f"\nAn error occurred: {e}", fg="red")


@click.group(invoke_without_command=True)
@click.pass_context
def plugin(ctx: Context):
    """Manages plugins. Runs interactively if no subcommand is given."""
    if ctx.invoked_subcommand is None:
        interactive_plugin_workflow()


@plugin.command("list")
def list_plugins():
    """Lists all discoverable plugins and their current status."""
    try:
        response = plugins_api.get_plugin_statuses()
        if response.get("status") == "success":
            plugins = response.get("plugins", {})
            _print_plugin_table(plugins)
        else:
            _handle_api_response(
                response, error_message_prefix="Failed to retrieve plugin statuses"
            )
    except BSMError as e:
        click.secho(f"Error listing plugins: {e}", fg="red")


@plugin.command("enable")
@click.argument("plugin_name", required=False)
def enable_plugin(plugin_name: Optional[str]):
    """Enables a specific plugin or launches interactive mode."""
    if not plugin_name:
        interactive_plugin_workflow()
        return

    click.echo(f"Attempting to enable plugin '{plugin_name}'...")
    try:
        response = plugins_api.set_plugin_status(plugin_name, True)
        _handle_api_response(
            response, error_message_prefix=f"Failed to enable plugin '{plugin_name}'"
        )
    except UserInputError as e:
        click.secho(f"Error: {e}", fg="red")
    except BSMError as e:
        click.secho(f"Failed to enable plugin '{plugin_name}': {e}", fg="red")


@plugin.command("disable")
@click.argument("plugin_name", required=False)
def disable_plugin(plugin_name: Optional[str]):
    """Disables a specific plugin or launches interactive mode."""
    if not plugin_name:
        interactive_plugin_workflow()
        return

    click.echo(f"Attempting to disable plugin '{plugin_name}'...")
    try:
        response = plugins_api.set_plugin_status(plugin_name, False)
        _handle_api_response(
            response, error_message_prefix=f"Failed to disable plugin '{plugin_name}'"
        )
    except UserInputError as e:
        click.secho(f"Error: {e}", fg="red")
    except BSMError as e:
        click.secho(f"Failed to disable plugin '{plugin_name}': {e}", fg="red")


@plugin.command("reload")
def reload_plugins_cli():
    """Triggers the plugin manager to reload all plugins."""
    click.echo("Attempting to reload plugins...")
    try:
        response = plugins_api.reload_plugins()
        if response.get("status") == "success":
            success_msg = response.get("message", "Plugins reloaded successfully.")
            click.secho(success_msg, fg="green")
        else:
            _handle_api_response(
                response, error_message_prefix="Failed to reload plugins"
            )
    except BSMError as e:
        click.secho(f"Error reloading plugins: {e}", fg="red")
    except Exception as e:
        click.secho(f"An unexpected error occurred: {e}", fg="red", err=True)
        logger.error(
            f"Unexpected error in 'plugin reload' CLI command: {e}", exc_info=True
        )


@plugin.command("trigger-event")
@click.argument("event_name", required=True)
@click.option(
    "--payload-json",
    metavar="<JSON_STRING>",
    help="Optional JSON string to use as the event payload.",
)
def trigger_event_cli(event_name: str, payload_json: Optional[str]):
    """
    Triggers a custom plugin event with an optional JSON payload.
    Example: bsm plugin event trigger myplugin:my_event --payload-json '{"key": "value"}'
    """
    import json  # Local import for json

    click.echo(f"Attempting to trigger custom plugin event '{event_name}'...")

    payload_dict: Optional[Dict[str, Any]] = None
    if payload_json:
        try:
            payload_dict = json.loads(payload_json)
            if not isinstance(payload_dict, dict):
                click.secho(
                    "Error: --payload-json must be a valid JSON object (dictionary).",
                    fg="red",
                )
                return
            click.echo(f"With payload: {payload_dict}")
        except json.JSONDecodeError as e:
            click.secho(f"Error: Invalid JSON provided for payload: {e}", fg="red")
            return
        except Exception as e:  # Catch any other unexpected error during parsing
            click.secho(f"Error parsing payload: {e}", fg="red")
            return

    try:
        response = plugins_api.trigger_external_plugin_event_api(
            event_name, payload_dict
        )

        if response.get("status") == "success":
            success_msg = response.get(
                "message", f"Event '{event_name}' triggered successfully."
            )
            click.secho(success_msg, fg="green")
        else:
            _handle_api_response(
                response, error_message_prefix=f"Failed to trigger event '{event_name}'"
            )
    except (
        UserInputError
    ) as e:  # Catch UserInputError from the API function if event_name is missing
        click.secho(f"Error: {e}", fg="red")
    except BSMError as e:  # Catch other BSM errors
        click.secho(f"Error triggering event '{event_name}': {e}", fg="red")
    except Exception as e:
        click.secho(f"An unexpected error occurred: {e}", fg="red", err=True)
        logger.error(
            f"Unexpected error in 'plugin event trigger' CLI command: {e}",
            exc_info=True,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    plugin()
