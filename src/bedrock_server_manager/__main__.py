# bedrock_server_manager/__main__.py
"""
Main entry point for the Bedrock Server Manager command-line interface (CLI).

This module uses `click` to assemble and manage all available commands.
It handles initial setup and launches the main interactive menu if no
command is specified.
"""

import logging
import sys

import click

# --- Early and Essential Imports ---
try:
    from bedrock_server_manager import __version__
    from bedrock_server_manager.config.settings import Settings
    from bedrock_server_manager.logging import setup_logging, log_separator
    from bedrock_server_manager.config.const import app_name_title
    from bedrock_server_manager.utils.general import startup_checks
    from bedrock_server_manager.core.system import base as system_base
    from bedrock_server_manager.api import utils as api_utils
    from bedrock_server_manager.error import UserExitError
except ImportError as e:
    # Use basic logging for critical failures before the logger is set up
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("bsm_critical_error")
    logger.critical(
        f"CRITICAL ERROR: Failed to import core modules ({e}). Cannot start.",
        exc_info=True,
    )
    print(
        f"CRITICAL ERROR: Failed to import core modules ({e}). Please ensure the package is installed correctly.",
        file=sys.stderr,
    )
    sys.exit(1)

# --- Import all our new Click command modules ---
from bedrock_server_manager.cli import (
    main_menus,
    addon,
    backup_restore,
    cleanup,
    generate_password,
    player,
    server,
    server_install_config,
    system,
    task_scheduler,
    utils,
    web,
    world,
)

# --- Define the main Click group ---


@click.group(
    invoke_without_command=True,
    context_settings=dict(help_option_names=["-h", "--help"]),
)
@click.version_option(
    __version__, "-v", "--version", message=f"{app_name_title} %(version)s"
)
@click.pass_context
def cli(ctx: click.Context):
    """
    The main command group for the Bedrock Server Manager CLI.

    This tool provides a comprehensive suite of commands to install, configure,
    manage, and monitor Minecraft Bedrock servers.

    If no specific command is provided on the command line, the application
    will launch an interactive menu system to guide the user.
    """
    # --- Initial Setup and Checks (runs every time) ---
    try:
        settings = Settings()

        # Configure logging
        log_dir = settings.get("LOG_DIR")
        logger = setup_logging(
            log_dir=log_dir,
            log_keep=settings.get("LOGS_KEEP"),
            file_log_level=settings.get("FILE_LOG_LEVEL"),
            cli_log_level=settings.get("CLI_LOG_LEVEL"),
        )
        log_separator(logger, app_name=app_name_title, app_version=__version__)

        logger.info(f"Starting {app_name_title} v{__version__}...")
        startup_checks(app_name_title, __version__)
        system_base.check_prerequisites()
        api_utils.update_server_statuses()

    except Exception as setup_e:
        click.secho(f"CRITICAL ERROR during startup: {setup_e}", fg="red", bold=True)
        # Use basic logger if full logger failed
        logging.getLogger("bsm_critical_error").critical(
            f"CRITICAL ERROR during startup: {setup_e}", exc_info=True
        )
        sys.exit(1)

    # Pass the main cli group object to the context so sub-menus can invoke other commands
    ctx.obj = {"cli": cli}

    # --- Interactive Mode ---
    # If no subcommand was invoked, run the main interactive menu
    if ctx.invoked_subcommand is None:
        logger.info("No command provided, launching main interactive menu...")
        try:
            main_menus.main_menu(ctx)
        except UserExitError:
            # This is the expected way to exit the menu gracefully
            sys.exit(0)
        except (click.Abort, KeyboardInterrupt):
            # This handles Ctrl+C from the top-level menu
            click.secho("\nOperation cancelled by user.", fg="red")
            sys.exit(1)


# --- Assemble the Commands ---
# Add command groups from our modules
cli.add_command(backup_restore.backup)
cli.add_command(player.player)
cli.add_command(server.server)
cli.add_command(system.system)
cli.add_command(task_scheduler.schedule)
cli.add_command(web.web)
cli.add_command(world.world)

# Add standalone commands from our modules
cli.add_command(addon.install_addon)
cli.add_command(cleanup.cleanup)
cli.add_command(
    generate_password.generate_password_hash_command, name="generate-password"
)
cli.add_command(server_install_config.install_server)
cli.add_command(server_install_config.update_server)
cli.add_command(server_install_config.configure_allowlist)
cli.add_command(server_install_config.configure_permissions)
cli.add_command(server_install_config.configure_properties)
cli.add_command(server_install_config.remove_allowlist_players)
cli.add_command(utils.list_servers)
cli.add_command(utils.attach_console)


def main():
    """Main execution function wrapped for exception handling."""
    try:
        cli()
    except Exception as e:
        # This is a final catch-all for any unexpected errors not handled by Click
        click.secho(
            f"\nFATAL UNEXPECTED ERROR: {type(e).__name__}: {e}", fg="red", bold=True
        )
        logging.getLogger("bsm_critical_error").critical(
            "A fatal, unexpected error occurred.", exc_info=True
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
