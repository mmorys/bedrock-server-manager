# bedrock_server_manager/cli/backup_restore.py
"""
Defines the `bsm backup` command group for server backup and restore.

This module provides a comprehensive suite of commands for creating,
restoring, and managing server backups. It supports both interactive menus
for guided operations and direct command-line flags for automation.
"""

import logging
import os
from typing import Optional, Tuple

import click
import questionary

from bedrock_server_manager.api import backup_restore as backup_restore_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


# ---- Interactive Menu Helpers ----


def _interactive_backup_menu(
    server_name: str,
) -> Tuple[str, Optional[str], bool]:
    """Guides the user through an interactive backup process.

    Args:
        server_name: The name of the server to back up.

    Returns:
        A tuple of (backup_type, file_to_backup, change_status).
        `change_status` indicates if the server should be stopped/started.

    Raises:
        click.Abort: If the user cancels the operation at any prompt.
    """
    click.secho(f"Entering interactive backup for server: {server_name}", fg="yellow")

    # Maps user-friendly choices to API parameters
    backup_type_map = {
        "Backup World Only": ("world", None, True),
        "Backup Everything (World + Configs)": ("all", None, True),
        "Backup a Specific Configuration File": ("config", None, False),
    }

    choice = questionary.select(
        "Select a backup option:",
        choices=list(backup_type_map.keys()) + ["Cancel"],
    ).ask()

    if not choice or choice == "Cancel":
        raise click.Abort()

    b_type, b_file, b_change_status = backup_type_map[choice]

    if b_type == "config":
        # Let user choose which config file to back up
        config_file_map = {
            "allowlist.json": "allowlist.json",
            "permissions.json": "permissions.json",
            "server.properties": "server.properties",
        }
        file_choice = questionary.select(
            "Which configuration file do you want to back up?",
            choices=list(config_file_map.keys()) + ["Cancel"],
        ).ask()

        if not file_choice or file_choice == "Cancel":
            raise click.Abort()
        b_file = config_file_map[file_choice]

    return b_type, b_file, b_change_status


def _interactive_restore_menu(
    server_name: str,
) -> Tuple[str, str, bool]:
    """Guides the user through an interactive restore process.

    Args:
        server_name: The name of the server to restore a backup to.

    Returns:
        A tuple of (restore_type, backup_file_path, change_status).

    Raises:
        click.Abort: If the user cancels or no backups are found.
    """
    click.secho(f"Entering interactive restore for server: {server_name}", fg="yellow")

    restore_type_map = {
        "Restore World": "world",
        "Restore Allowlist": "allowlist",
        "Restore Permissions": "permissions",
        "Restore Properties": "properties",
    }

    choice = questionary.select(
        "What do you want to restore?",
        choices=list(restore_type_map.keys()) + ["Cancel"],
    ).ask()

    if not choice or choice == "Cancel":
        raise click.Abort()
    restore_type = restore_type_map[choice]

    # Fetch and display available backup files for the selected type
    try:
        response = backup_restore_api.list_backup_files(server_name, restore_type)
        backup_files = response.get("backups", [])
        if not backup_files:
            click.secho(
                f"No '{restore_type}' backups found for server '{server_name}'.",
                fg="yellow",
            )
            raise click.Abort()
    except BSMError as e:
        click.secho(f"Error listing backups: {e}", fg="red")
        raise click.Abort()

    # Create a user-friendly list of basenames and map them back to full paths
    file_map = {os.path.basename(f): f for f in backup_files}
    file_choices = sorted(list(file_map.keys()), reverse=True)  # Show newest first

    file_to_restore_basename = questionary.select(
        f"Select a '{restore_type}' backup to restore:",
        choices=file_choices + ["Cancel"],
    ).ask()

    if not file_to_restore_basename or file_to_restore_basename == "Cancel":
        raise click.Abort()
    selected_file_path = file_map[file_to_restore_basename]

    return restore_type, selected_file_path, True


# ---- Click Command Group ----


@click.group()
def backup():
    """Manages server backups (create, restore, prune).

        This command group provides a complete suite of tools for managing
        server data backups. You can create new backups, restore a server
    s    to a previous state, and clean up old backup files.
    """
    pass


@backup.command("create")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the target server."
)
@click.option(
    "-t",
    "--type",
    "backup_type",
    type=click.Choice(["world", "config", "all"], case_sensitive=False),
    help="Type of backup to create; skips interactive menu.",
)
@click.option(
    "-f",
    "--file",
    "file_to_backup",
    help="Specific file to back up (required if --type=config).",
)
@click.option(
    "--no-stop",
    is_flag=True,
    help="Perform backup without stopping the server (risks data corruption).",
)
def create_backup(
    server_name: str,
    backup_type: Optional[str],
    file_to_backup: Optional[str],
    no_stop: bool,
):
    """Creates a backup of server data.

    Backs up server data such as the world, configuration files, or both.
    If run without the --type option, it will launch an interactive menu to
    guide you through the process. After a successful backup, it will
    automatically prune old backups according to your configuration.

    Args:
        server_name: The name of the server to back up.
        backup_type: The type of data to back up ('world', 'config', 'all').
        file_to_backup: The specific config file to back up.
        no_stop: If True, skips the safe server stop/start procedure.

    Raises:
        click.Abort: If the operation is cancelled or an error occurs.
    """

    def _run_backup(b_type: str, f_to_backup: Optional[str], s_name: str, stop: bool):
        """Internal helper to execute the correct API call."""
        if b_type == "world":
            return backup_restore_api.backup_world(s_name, stop_start_server=stop)
        if b_type == "config":
            return backup_restore_api.backup_config_file(
                s_name, f_to_backup, stop_start_server=stop
            )
        if b_type == "all":
            return backup_restore_api.backup_all(s_name, stop_start_server=stop)
        return None

    change_status = not no_stop

    try:
        if not backup_type:
            backup_type, file_to_backup, change_status = _interactive_backup_menu(
                server_name
            )

        if backup_type == "config" and not file_to_backup:
            raise click.UsageError(
                "Option '--file' is required when using '--type config'."
            )

        click.echo(f"Starting '{backup_type}' backup for server '{server_name}'...")
        response = _run_backup(backup_type, file_to_backup, server_name, change_status)
        _handle_api_response(response, "Backup completed successfully.")

        click.echo("Pruning old backups...")
        prune_response = backup_restore_api.prune_old_backups(server_name=server_name)
        _handle_api_response(prune_response, "Pruning complete.")

    except BSMError as e:
        click.secho(f"A backup error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nBackup operation cancelled.", fg="yellow")


@backup.command("restore")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the target server."
)
@click.option(
    "-f",
    "--file",
    "backup_file_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to the backup file to restore; skips interactive menu.",
)
@click.option(
    "--no-stop",
    is_flag=True,
    help="Perform restore without stopping the server (risks data corruption).",
)
def restore_backup(server_name: str, backup_file_path: Optional[str], no_stop: bool):
    """Restores server data from a backup file.

    This command is destructive and will overwrite current server data with
    the contents of the backup file.

    If the --file option is provided, the command will infer the restore
    type from the filename. Otherwise, it launches an interactive menu.

    Args:
        server_name: The name of the server to restore.
        backup_file_path: The path to the backup file.
        no_stop: If True, skips the safe server stop/start procedure.

    Raises:
        click.Abort: If the operation is cancelled or an error occurs.
    """
    change_status = not no_stop

    try:
        if backup_file_path:
            filename = os.path.basename(backup_file_path).lower()
            if "world" in filename:
                restore_type = "world"
            elif (
                "allowlist" in filename
                or "permissions" in filename
                or "properties" in filename
            ):
                restore_type = "config"
            else:
                raise click.UsageError(
                    f"Could not determine restore type from filename '{filename}'."
                )
        else:
            restore_type, backup_file_path, change_status = _interactive_restore_menu(
                server_name
            )

        click.echo(
            f"Starting '{restore_type}' restore for server '{server_name}' from '{os.path.basename(backup_file_path)}'..."
        )

        if restore_type == "world":
            response = backup_restore_api.restore_world(
                server_name, backup_file_path, stop_start_server=change_status
            )
        else:
            response = backup_restore_api.restore_config_file(
                server_name, backup_file_path, stop_start_server=change_status
            )

        _handle_api_response(response, "Restore completed successfully.")

    except BSMError as e:
        click.secho(f"A restore error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nRestore operation cancelled.", fg="yellow")


@backup.command("prune")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server whose backups to prune.",
)
def prune_backups(server_name: str):
    """Deletes old backups for a server, keeping the newest ones.

    This command checks the backup retention policy defined in the main
    configuration and deletes any backup files that are older than the
    configured limit.

    Args:
        server_name: The server whose backups will be pruned.

    Raises:
        click.Abort: If pruning fails due to a BSMError.
    """
    try:
        click.echo(f"Pruning old backups for server '{server_name}'...")
        response = backup_restore_api.prune_old_backups(server_name=server_name)
        _handle_api_response(response, "Pruning complete.")
    except BSMError as e:
        click.secho(f"An error occurred during pruning: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backup()
