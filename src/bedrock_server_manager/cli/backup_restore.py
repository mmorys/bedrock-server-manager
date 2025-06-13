# bedrock_server_manager/cli/backup_restore.py
"""
Click command group for handling server backup, restore, and management.

Combines direct command-line execution with interactive questionary menus
for a flexible user experience.
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple

import click
import questionary

from bedrock_server_manager.api import backup_restore as backup_restore_api
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


# A helper to reduce code duplication in API response handling
def _handle_api_response(response: Dict[str, Any], success_msg: str):
    """Prints styled success or error message based on API response."""
    if response.get("status") == "error":
        message = response.get("message", "An unknown error occurred.")
        click.secho(f"Error: {message}", fg="red")
        raise click.Abort()
    else:
        message = response.get("message", success_msg)
        click.secho(f"Success: {message}", fg="green")


# ---- Interactive Menu Helpers ----


def _interactive_backup_menu(
    server_name: str,
) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Guides the user through an interactive backup process using questionary.

    Args:
        server_name: The name of the server to back up.

    Returns:
        A tuple containing:
            - backup_type (Optional[str]): Type of backup ('world', 'config', 'all').
            - file_to_backup (Optional[str]): Specific config file if type is 'config'.
            - change_status (bool): Whether to stop/start the server for the backup.
                                    Always True from this menu.
    """
    click.secho(f"Entering interactive backup for server: {server_name}", fg="yellow")

    backup_type_map = {
        "Backup World Only": ("world", None, True),
        "Backup Everything (World + Configs)": ("all", None, True),
        "Backup a Specific Configuration File": ("config", None, False),
    }

    choice = questionary.select(
        "Select backup option:",
        choices=list(backup_type_map.keys()) + ["Cancel"],
    ).ask()

    if not choice or choice == "Cancel":
        raise click.Abort()

    b_type, b_file, b_change_status = backup_type_map[choice]

    if b_type == "config":
        config_file_map = {
            "allowlist.json": "allowlist.json",
            "permissions.json": "permissions.json",
            "server.properties": "server.properties",
        }
        file_choice = questionary.select(
            "Which configuration file to back up?",
            choices=list(config_file_map.keys()) + ["Cancel"],
        ).ask()

        if not file_choice or file_choice == "Cancel":
            raise click.Abort()

        b_file = config_file_map[file_choice]

    return b_type, b_file, b_change_status


def _interactive_restore_menu(
    server_name: str,
) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Guides the user through an interactive restore process using questionary.

    Args:
        server_name: The name of the server to restore.

    Returns:
        A tuple containing:
            - restore_type (Optional[str]): Type of restore ('world', 'allowlist', etc.).
            - backup_file_path (Optional[str]): Full path to the selected backup file.
            - change_status (bool): Whether to stop/start the server for the restore.
                                    Always True from this menu.
    """
    click.secho(f"Entering interactive restore for server: {server_name}", fg="yellow")

    restore_type_map = {
        "Restore World": "world",
        "Restore Allowlist": "allowlist",
        "Restore Permissions": "permissions",
        "Restore Properties": "properties",
    }

    choice = questionary.select(
        "Select what you want to restore:",
        choices=list(restore_type_map.keys()) + ["Cancel"],
    ).ask()

    if not choice or choice == "Cancel":
        raise click.Abort()

    restore_type = restore_type_map[choice]

    # Fetch available backup files for the selected type
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

    # Create a user-friendly list of basenames
    file_choices = [os.path.basename(f) for f in backup_files]

    file_to_restore_basename = questionary.select(
        f"Select a '{restore_type}' backup to restore:",
        choices=file_choices + ["Cancel"],
    ).ask()

    if not file_to_restore_basename or file_to_restore_basename == "Cancel":
        raise click.Abort()

    # Find the full path from the chosen basename
    selected_file_path = next(
        (p for p in backup_files if os.path.basename(p) == file_to_restore_basename),
        None,
    )

    return restore_type, selected_file_path, True


# ---- Click Command Group ----


@click.group()
def backup():
    """Commands for server backup, restore, and management."""
    pass


@backup.command("create")
@click.option("-s", "--server", required=True, help="Name of the target server.")
@click.option(
    "-t",
    "--type",
    "backup_type",
    type=click.Choice(["world", "config", "all"]),
    help="Type of backup. Skips interactive menu.",
)
@click.option(
    "-f", "--file", "file_to_backup", help="File to backup (for type 'config')."
)
@click.option(
    "--no-stop",
    is_flag=True,
    default=False,
    help="Attempt backup without stopping server (risks data corruption).",
)
def create_backup(
    server: str,
    backup_type: Optional[str],
    file_to_backup: Optional[str],
    no_stop: bool,
):
    """
    Backs up server data. Launches an interactive menu if --type is not specified.
    """
    change_status = not no_stop

    try:
        if not backup_type:
            # Interactive Mode
            backup_type, file_to_backup, change_status = _interactive_backup_menu(
                server
            )

        # Validation for non-interactive mode
        if backup_type == "config" and not file_to_backup:
            raise click.UsageError(
                "Option '--file' is required when using '--type config'."
            )

        click.echo(f"Starting '{backup_type}' backup for server '{server}'...")
        logger.debug(
            f"CLI: Initiating '{backup_type}' backup for server '{server}'. Change Status: {change_status}"
        )

        response = None
        if backup_type == "world":
            response = backup_restore_api.backup_world(
                server, stop_start_server=change_status
            )
        elif backup_type == "config":
            response = backup_restore_api.backup_config_file(
                server, file_to_backup, stop_start_server=change_status
            )
        elif backup_type == "all":
            response = backup_restore_api.backup_all(
                server, stop_start_server=change_status
            )

        _handle_api_response(response, "Backup completed successfully.")

        # Prune after a successful backup
        click.echo("Pruning old backups...")
        prune_response = backup_restore_api.prune_old_backups(server_name=server)
        _handle_api_response(prune_response, "Pruning complete.")

    except BSMError as e:
        click.secho(f"A backup error occurred: {e}", fg="red")
        raise click.Abort()
    except click.Abort:
        click.secho("Backup operation cancelled.", fg="yellow")


@backup.command("restore")
@click.option("-s", "--server", required=True, help="Name of the target server.")
@click.option(
    "-f",
    "--file",
    "backup_file",
    help="Full path to the backup file to restore. Skips interactive menu.",
)
@click.option(
    "--no-stop",
    is_flag=True,
    default=False,
    help="Attempt restore without stopping server (risks data corruption).",
)
def restore_backup(server: str, backup_file: Optional[str], no_stop: bool):
    """
    Restores server data from a backup.

    If --file is provided, the command attempts to infer the restore type
    (world, allowlist, permissions, properties) from the filename.
    Otherwise, it launches an interactive menu to select the restore type
    and the specific backup file.
    """
    change_status = not no_stop

    try:
        # Determine restore type from filename if provided, otherwise go interactive
        if backup_file:
            filename = os.path.basename(backup_file).lower()
            if "world" in filename:
                restore_type = "world"
            elif "allowlist" in filename:
                restore_type = "allowlist"
            elif "permissions" in filename:
                restore_type = "permissions"
            elif "properties" in filename:
                restore_type = "properties"
            else:
                raise click.UsageError(
                    f"Could not determine restore type from filename '{filename}'. Please use interactive mode."
                )
        else:
            # Interactive Mode
            restore_type, backup_file, change_status = _interactive_restore_menu(server)

        click.echo(
            f"Starting '{restore_type}' restore for server '{server}' from '{os.path.basename(backup_file)}'..."
        )
        logger.debug(
            f"CLI: Initiating '{restore_type}' restore for server '{server}'. Change Status: {change_status}"
        )

        response = None
        if restore_type == "world":
            response = backup_restore_api.restore_world(
                server, backup_file, stop_start_server=change_status
            )
        else:  # Covers allowlist, permissions, properties
            response = backup_restore_api.restore_config_file(
                server, backup_file, stop_start_server=change_status
            )

        _handle_api_response(response, "Restore completed successfully.")

    except BSMError as e:
        click.secho(f"A restore error occurred: {e}", fg="red")
        raise click.Abort()
    except click.Abort:
        click.secho("Restore operation cancelled.", fg="yellow")


@backup.command("prune")
@click.option(
    "-s", "--server", required=True, help="Name of the server whose backups to prune."
)
def prune_backups(server: str):
    """Deletes old backups for a server, keeping the newest N."""
    try:
        click.echo(f"Pruning old backups for server '{server}'...")
        response = backup_restore_api.prune_old_backups(server_name=server)
        _handle_api_response(response, "Pruning complete.")
    except BSMError as e:
        click.secho(f"An error occurred during pruning: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backup()
