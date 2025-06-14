# bedrock_server_manager/cli/main_menus.py
"""
Defines the main interactive menu flows using `questionary`.

These menus drive the application by invoking the underlying `click`
commands, providing a user-friendly alternative to direct command-line use.
"""

import logging
from typing import Optional

import click
import questionary

from bedrock_server_manager.utils.get_utils import _get_splash_text
from bedrock_server_manager.config.const import app_name_title
from bedrock_server_manager.error import UserExitError

# We will get the command objects from the context, so direct imports of CLI functions are no longer needed here.
# However, we still need our interactive helper for selecting a server.
from .utils import get_server_name_interactively, list_servers

logger = logging.getLogger(__name__)


def _world_management_menu(ctx: click.Context, server_name: str):
    """Displays a sub-menu for world management actions."""
    world_group = ctx.obj["cli"].get_command(ctx, "world")
    if not world_group:
        click.secho("Error: World command group not found.", fg="red")
        return

    while True:
        choice = questionary.select(
            f"World Management for '{server_name}':",
            choices=["Install World", "Export World", "Reset World", "Back"],
            use_indicator=True,
        ).ask()

        if choice is None or choice == "Back":
            return

        cmd_name = None
        if choice == "Install World":
            cmd_name = "install"
        elif choice == "Export World":
            cmd_name = "export"
        elif choice == "Reset World":
            cmd_name = "reset"

        if cmd_name:
            cmd = world_group.get_command(ctx, cmd_name)
            if cmd:
                ctx.invoke(cmd, server_name=server_name)
                break  # Exit sub-menu after action
            else:
                click.secho(
                    f"Error: Command '{cmd_name}' not found in world group.", fg="red"
                )
        else:
            click.secho(f"Warning: No action defined for '{choice}'.", fg="yellow")


def _backup_restore_menu(ctx: click.Context, server_name: str):
    """Displays a sub-menu for backup and restore actions."""
    backup_group = ctx.obj["cli"].get_command(ctx, "backup")
    if not backup_group:
        click.secho("Error: Backup command group not found.", fg="red")
        return

    while True:
        choice = questionary.select(
            f"Backup/Restore for '{server_name}':",
            choices=["Create Backup", "Restore Backup", "Prune Backups", "Back"],
            use_indicator=True,
        ).ask()

        if choice is None or choice == "Back":
            return

        cmd_name = None
        if choice == "Create Backup":
            cmd_name = "create"
        elif choice == "Restore Backup":
            cmd_name = "restore"
        elif choice == "Prune Backups":
            cmd_name = "prune"

        if cmd_name:
            cmd = backup_group.get_command(ctx, cmd_name)
            if cmd:
                # Backup commands use 'server' as parameter name
                ctx.invoke(cmd, server=server_name)
                break  # Exit sub-menu after action
            else:
                click.secho(
                    f"Error: Command '{cmd_name}' not found in backup group.", fg="red"
                )
        else:
            click.secho(f"Warning: No action defined for '{choice}'.", fg="yellow")


def main_menu(ctx: click.Context):
    """
    Displays the main application menu and handles top-level user choices.
    This function becomes the main loop for interactive mode.
    """
    while True:
        try:
            click.clear()
            click.secho(f"{app_name_title} - Main Menu", fg="magenta", bold=True)
            click.secho(_get_splash_text(), fg="yellow")

            # Use the list-servers command to display status
            ctx.invoke(list_servers, loop=False)

            choice = questionary.select(
                "\nChoose an action:",
                choices=[
                    "Install New Server",
                    "Manage Existing Server",
                    "Exit",
                ],
                use_indicator=True,
            ).ask()

            if choice is None or choice == "Exit":
                raise UserExitError()

            if choice == "Install New Server":
                # Get the 'install-server' command and invoke it
                cmd = ctx.obj["cli"].get_command(ctx, "install-server")
                ctx.invoke(cmd)

            elif choice == "Manage Existing Server":
                server_name = get_server_name_interactively()
                if server_name:
                    manage_server_menu(ctx, server_name)

        except UserExitError:
            click.secho("\nExiting application.", fg="green")
            raise
        except (click.Abort, KeyboardInterrupt):
            # A sub-menu was cancelled, so we just loop back to the main menu.
            click.echo("\nReturning to main menu...")
            click.pause()
        except Exception as e:
            click.secho(f"\nAn unexpected error occurred: {e}", fg="red")
            logger.error(f"Main menu loop error: {e}", exc_info=True)
            click.pause("Press Enter to continue...")


def manage_server_menu(ctx: click.Context, server_name: str):
    """Displays the menu for managing a specific, existing server."""
    # Command Definitions
    server_group = ctx.obj["cli"].get_command(ctx, "server")
    # world_group is fetched in _world_management_menu, not needed directly here for menu_map
    # addon_group = ctx.obj["cli"].get_command(ctx, "addon") # Not used if install-addon is direct

    # Direct commands (not part of a group mentioned above or used directly)
    install_addon_cmd = ctx.obj["cli"].get_command(ctx, "install-addon")
    configure_props_cmd = ctx.obj["cli"].get_command(ctx, "configure-properties")
    configure_allowlist_cmd = ctx.obj["cli"].get_command(ctx, "configure-allowlist")
    configure_permissions_cmd = ctx.obj["cli"].get_command(ctx, "configure-permissions")
    attach_console_cmd = ctx.obj["cli"].get_command(ctx, "attach-console")
    update_server_cmd = ctx.obj["cli"].get_command(ctx, "update-server")

    # Command Groups
    # backup_group is fetched in _backup_restore_menu
    system_group = ctx.obj["cli"].get_command(ctx, "system")
    schedule_group = ctx.obj["cli"].get_command(ctx, "schedule")
    # Ensure backup_group is available if any direct command from it were used in menu_map
    # For now, _backup_restore_menu handles backup commands internally.
    # backup_group = ctx.obj["cli"].get_command(ctx, "backup")

    menu_map = {
        "Start Server": (server_group.get_command(ctx, "start"), "server_name", {}),
        "Stop Server": (server_group.get_command(ctx, "stop"), "server_name", {}),
        "Restart Server": (server_group.get_command(ctx, "restart"), "server_name", {}),
        "Send Command to Server": (
            server_group.get_command(ctx, "send-command"),
            "server_name",
            {},
        ),
        "----": "separator",
        "Backup or Restore": _backup_restore_menu,  # Handled by its own function
        "Manage World (Install/Export/Reset)": _world_management_menu,  # Handled by its own function
        "Install Addon": (install_addon_cmd, "server", {}),
        "-----": "separator",
        "Configure Properties": (configure_props_cmd, "server", {}),
        "Configure Allowlist": (configure_allowlist_cmd, "server", {}),
        "Configure Permissions": (configure_permissions_cmd, "server", {}),
        "Configure Auto-Update": (
            system_group.get_command(ctx, "configure-service"),
            "server_name",
            {},
        ),
        "------": "separator",
        "Monitor Resource Usage": (
            system_group.get_command(ctx, "monitor"),
            "server_name",
            {},
        ),
        "Schedule Tasks": schedule_group,  # Directly use the Click Group, handled in its own logic branch
        "Attach to Console (Linux only)": (attach_console_cmd, "server_name", {}),
        "-------": "separator",
        "Update Server": (update_server_cmd, "server", {}),
        "Delete Server": (
            server_group.get_command(ctx, "delete"),
            "server_name",
            {"yes": False},  # Let the command handle confirmation interactively
        ),
        "--------": "separator",
        "Back to Main Menu": "back",
    }

    while True:
        click.clear()
        click.secho(f"--- Managing Server: {server_name} ---", fg="magenta", bold=True)
        # Assuming list_servers can handle being called for a deleted server gracefully
        # or we rely on the loop exiting before it's called again.
        # ctx.invoke(list_servers, loop=False) # Maybe comment out or make more robust

        choice = questionary.select(
            f"\nSelect an action for '{server_name}':",
            choices=list(menu_map.keys()),
            use_indicator=True,
        ).ask()

        if choice is None or choice == "Back to Main Menu":
            return

        action_config = menu_map.get(choice)

        if action_config == "separator":
            continue
        if action_config is None:
            click.secho(f"Warning: No action defined for '{choice}'.", fg="yellow")
            continue

        if callable(action_config) and not (
            hasattr(action_config, "commands") or hasattr(action_config, "callback")
        ):
            action_config(ctx, server_name)
        elif isinstance(action_config, tuple):
            command_obj, server_param_key, kwargs_to_pass = action_config
            final_kwargs = {}
            if server_param_key:
                final_kwargs[server_param_key] = server_name
            final_kwargs.update(kwargs_to_pass)

            if command_obj is None:
                click.secho(
                    f"Error: Command object for '{choice}' is None. Check menu_map.",
                    fg="red",
                )
                continue

            if command_obj.name == "send-command":
                cmd_str = questionary.text("Enter command to send:").ask()
                if cmd_str is None:
                    continue
                if cmd_str.strip():
                    final_kwargs["command"] = cmd_str.split()
                    try:
                        ctx.invoke(command_obj, **final_kwargs)
                    except Exception as e:
                        click.secho(f"Error sending command: {e}", fg="red")
            else:
                try:
                    ctx.invoke(command_obj, **final_kwargs)
                    # After a successful invocation, check if the command was 'delete'.
                    # If so, we must exit this menu.
                    if command_obj.name == "delete":
                        # The delete command itself will print success. We just need to exit.
                        click.echo("\nServer deleted. Returning to the main menu.")
                        # We add a pause here so the user can read the message before the
                        # screen clears and returns to the previous menu.
                        click.pause()
                        return  # Exit the manage_server_menu function
                except Exception as e:
                    # The exception will be caught, so the loop continues, which is fine.
                    # This means if deletion fails, the user stays in the menu to try again.
                    click.secho(f"Error executing action '{choice}': {e}", fg="red")

        elif hasattr(action_config, "commands"):
            if action_config.name == "schedule":
                try:
                    ctx.invoke(action_config, server_name=server_name)
                except Exception as e:
                    click.secho(f"Error in '{action_config.name}' menu: {e}", fg="red")
            else:
                click.secho(
                    f"Warning: Menu item '{choice}' points to unhandled Click command group '{action_config.name}'.",
                    fg="yellow",
                )
        else:
            if (
                action_config is not None
                and action_config != "back"
                and action_config != "separator"
            ):
                click.secho(
                    f"Warning: Unhandled menu action type for '{choice}'. Action: {action_config}",
                    fg="yellow",
                )

        # Don't show the server status at the top of the loop anymore,
        # it might have just been deleted.
        click.pause("\nPress Enter to continue...")
