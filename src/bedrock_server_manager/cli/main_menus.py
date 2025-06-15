# bedrock_server_manager/cli/main_menus.py
"""
Defines the main interactive menu flows for the application.

This module uses `questionary` to create a user-friendly, menu-driven
interface that acts as a front-end to the application's underlying `click`
commands. It provides a guided experience for users who prefer not to use
direct command-line flags.
"""

import logging

import click
import questionary
from questionary import Separator

from bedrock_server_manager.config.const import app_name_title
from bedrock_server_manager.error import UserExitError
from bedrock_server_manager.utils.get_utils import _get_splash_text

from .utils import get_server_name_interactively, list_servers

logger = logging.getLogger(__name__)


def _world_management_menu(ctx: click.Context, server_name: str):
    """Displays a sub-menu for world management actions.

    Args:
        ctx: The current click command context.
        server_name: The name of the server being managed.
    """
    world_group = ctx.obj["cli"].get_command(ctx, "world")
    if not world_group:
        click.secho("Error: World command group not found.", fg="red")
        return

    menu_map = {
        "Install/Replace World": world_group.get_command(ctx, "install"),
        "Export Current World": world_group.get_command(ctx, "export"),
        "Reset Current World": world_group.get_command(ctx, "reset"),
        "Back": None,
    }

    while True:
        choice = questionary.select(
            f"World Management for '{server_name}':",
            choices=list(menu_map.keys()),
            use_indicator=True,
        ).ask()

        if choice is None or choice == "Back":
            return
        command = menu_map.get(choice)
        if command:
            ctx.invoke(command, server_name=server_name)
            break  # Exit sub-menu after one action for simplicity


def _backup_restore_menu(ctx: click.Context, server_name: str):
    """Displays a sub-menu for backup and restore actions.

    Args:
        ctx: The current click command context.
        server_name: The name of the server being managed.
    """
    backup_group = ctx.obj["cli"].get_command(ctx, "backup")
    if not backup_group:
        click.secho("Error: Backup command group not found.", fg="red")
        return

    menu_map = {
        "Create Backup": backup_group.get_command(ctx, "create"),
        "Restore from Backup": backup_group.get_command(ctx, "restore"),
        "Prune Old Backups": backup_group.get_command(ctx, "prune"),
        "Back": None,
    }

    while True:
        choice = questionary.select(
            f"Backup/Restore for '{server_name}':",
            choices=list(menu_map.keys()),
            use_indicator=True,
        ).ask()

        if choice is None or choice == "Back":
            return
        command = menu_map.get(choice)
        if command:
            ctx.invoke(command, server_name=server_name)
            break  # Exit sub-menu after one action


def main_menu(ctx: click.Context):
    """Displays the main application menu and drives interactive mode.

    Args:
        ctx: The root click command context.

    Raises:
        UserExitError: Propagated to signal a clean exit from the application.
    """
    while True:
        try:
            click.clear()
            click.secho(f"{app_name_title} - Main Menu", fg="magenta", bold=True)
            click.secho(_get_splash_text(), fg="yellow")

            # Display the server status table at the top of the main menu
            ctx.invoke(list_servers, loop=False, server_name_filter=None)

            choice = questionary.select(
                "\nChoose an action:",
                choices=["Install New Server", "Manage Existing Server", "Exit"],
                use_indicator=True,
            ).ask()

            if choice is None or choice == "Exit":
                raise UserExitError()

            if choice == "Install New Server":
                server_group = ctx.obj["cli"].get_command(ctx, "server")
                install_cmd = server_group.get_command(ctx, "install")
                ctx.invoke(install_cmd)
                questionary.press_any_key_to_continue(
                    "Press any key to return to the main menu..."
                ).ask()

            elif choice == "Manage Existing Server":
                server_name = get_server_name_interactively()
                if server_name:
                    manage_server_menu(ctx, server_name)

        except UserExitError:
            # This is a clean exit signal, so we re-raise it for the main entry point to catch.
            click.secho("\nExiting application. Goodbye!", fg="green")
            raise
        except (click.Abort, KeyboardInterrupt):
            # A sub-menu was cancelled (e.g., Ctrl+C), so we loop back to the main menu.
            click.echo("\nAction cancelled. Returning to the main menu.")
            click.pause()
        except Exception as e:
            logger.error(f"Main menu loop error: {e}", exc_info=True)
            click.secho(f"\nAn unexpected error occurred: {e}", fg="red")
            click.pause("Press any key to return to the main menu...")


def manage_server_menu(ctx: click.Context, server_name: str):
    """Displays the menu for managing a specific, existing server.

    Args:
        ctx: The current click command context.
        server_name: The name of the server being managed.
    """
    cli = ctx.obj["cli"]

    def get_cmd(group_name, cmd_name):
        """Helper to safely retrieve a command object."""
        group = cli.get_command(ctx, group_name)
        return group.get_command(ctx, cmd_name) if group else None

    # ---- Define menu sections as separate dictionaries for clarity ----
    control_map = {
        "Start Server": (get_cmd("server", "start"), {}),
        "Stop Server": (get_cmd("server", "stop"), {}),
        "Restart Server": (get_cmd("server", "restart"), {}),
        "Send Command to Server": (get_cmd("server", "send-command"), {}),
    }
    management_map = {
        "Backup or Restore": _backup_restore_menu,
        "Manage World": _world_management_menu,
        "Install Addon": (cli.get_command(ctx, "install-addon"), {}),
    }
    config_map = {
        "Configure Properties": (get_cmd("properties", "set"), {}),
        "Configure Allowlist": (get_cmd("allowlist", "add"), {}),
        "Configure Permissions": (get_cmd("permissions", "set"), {}),
    }
    system_map = {
        "Configure System Service": (get_cmd("system", "configure-service"), {}),
        "Monitor Resource Usage": (get_cmd("system", "monitor"), {}),
        "Schedule Tasks (cron/Windows)": cli.get_command(ctx, "schedule"),
        "Attach to Console (Linux only)": (cli.get_command(ctx, "attach-console"), {}),
    }
    maintenance_map = {
        "Update Server": (get_cmd("server", "update"), {}),
        "Delete Server": (get_cmd("server", "delete"), {}),
    }

    # ---- Combine all maps for easy lookup after a choice is made ----
    full_menu_map = {
        **control_map,
        **management_map,
        **config_map,
        **system_map,
        **maintenance_map,
        "Back to Main Menu": "back",
    }

    # ---- Build the choices list for questionary using Separators ----
    menu_choices = [
        Separator("--- Server Control ---"),
        *control_map.keys(),
        Separator("--- Management ---"),
        *management_map.keys(),
        Separator("--- Configuration ---"),
        *config_map.keys(),
        Separator("--- System & Monitoring ---"),
        *system_map.keys(),
        Separator("--- Maintenance ---"),
        *maintenance_map.keys(),
        Separator("--------------------"),
        "Back to Main Menu",
    ]

    while True:
        click.clear()
        click.secho(f"--- Managing Server: {server_name} ---", fg="magenta", bold=True)
        # Display a mini status for the selected server
        ctx.invoke(list_servers, server_name_filter=server_name)

        choice = questionary.select(
            f"\nSelect an action for '{server_name}':",
            choices=menu_choices,
            use_indicator=True,
        ).ask()

        if choice is None or choice == "Back to Main Menu":
            return

        action = full_menu_map.get(choice)
        if action is None:
            # Should not happen with the new structure, but good practice
            continue

        try:
            # Case 1: Action is a sub-menu function (e.g., _backup_restore_menu)
            if callable(action) and not hasattr(action, "commands"):
                action(ctx, server_name)

            # Case 2: Action is a tuple (command_object, kwargs)
            elif isinstance(action, tuple):
                command_obj, kwargs = action
                if not command_obj:
                    continue  # Command not found

                # Special handling for commands that need extra interactive input
                if command_obj.name == "send-command":
                    cmd_str = questionary.text("Enter command to send:").ask()
                    if cmd_str:
                        kwargs["command_parts"] = cmd_str.split()
                    else:
                        continue

                param_name = "server_name"
                kwargs[param_name] = server_name

                ctx.invoke(command_obj, **kwargs)

                if command_obj.name == "delete":
                    click.echo("\nServer has been deleted. Returning to main menu.")
                    click.pause()
                    return  # Exit this menu completely

            # Case 3: Action is a Click Group (e.g., the 'schedule' group)
            elif hasattr(action, "commands"):
                # Invoke the group, which will then run its own interactive menu
                ctx.invoke(action, server_name=server_name)

            click.pause("\nPress any key to return to the server menu...")

        except Exception as e:
            logger.error(f"Server menu error for action '{choice}': {e}", exc_info=True)
            click.secho(f"An error occurred while executing '{choice}': {e}", fg="red")
            click.pause()
