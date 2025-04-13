# bedrock-server-manager/bedrock_server_manager/__init__.py
"""
Main entry point for the Bedrock Server Manager command-line interface (CLI).

Handles argument parsing, initial setup (logging, checks), and dispatching
commands to the appropriate handler functions within the `cli` subpackage.
"""

import sys
import argparse
import os
import logging

# --- Initialize Settings and Logger ---
try:

    from bedrock_server_manager.config.settings import (
        settings,
        app_name,
        __version__,
    )
    from bedrock_server_manager.logging import setup_logging, log_separator

    # Configure logging based on settings
    try:
        logger = setup_logging(
            log_dir=settings.get("LOG_DIR"),
            log_keep=settings.get("LOGS_KEEP"),
            log_level=settings.get("LOG_LEVEL"),
        )
        # Log separator after setup
        log_separator(logger, app_name=app_name, app_version=__version__)
    except Exception as log_e:
        # Fallback basic logging if setup fails
        logging.basicConfig(level=logging.WARNING)
        logger = logging.getLogger("bedrock_server_manager_fallback")
        logger.critical(
            f"Failed to initialize file logging: {log_e}. Logging to console only.",
            exc_info=True,
        )

except ImportError as e:
    # Handle case where essential config/logging cannot be imported
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("bedrock_server_manager_critical_error")
    logger.critical(
        f"CRITICAL ERROR: Failed to import core modules ({e}). Cannot start application.",
        exc_info=True,
    )
    print(
        f"CRITICAL ERROR: Failed to import core modules ({e}). Please ensure the package is installed correctly.",
        file=sys.stderr,
    )
    sys.exit(1)
except Exception as e:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("bedrock_server_manager_critical_error")
    logger.critical(
        f"CRITICAL ERROR: Failed during initial settings/logging setup: {e}",
        exc_info=True,
    )
    print(f"CRITICAL ERROR: Failed during initial setup: {e}", file=sys.stderr)
    sys.exit(1)

# --- Import other modules ---
try:
    from bedrock_server_manager.api import (
        utils as api_utils,
        server_install_config as api_server_install_config,
    )
    from bedrock_server_manager.error import FileOperationError
    from bedrock_server_manager.core.download import downloader
    from bedrock_server_manager.utils.general import (
        startup_checks,
        _INFO_PREFIX,
        _OK_PREFIX,
        _WARN_PREFIX,
        _ERROR_PREFIX,
    )
    from bedrock_server_manager.core.server import (
        server as server_base,
    )
    from bedrock_server_manager.core.system import base as system_base
    from bedrock_server_manager.core.system import (
        linux as system_linux,
    )
    from bedrock_server_manager.cli import (
        main_menus,
        utils as cli_utils,
        server_install_config as cli_server_install_config,
        server as cli_server,
        world as cli_world,
        addon as cli_addon,
        backup_restore as cli_backup_restore,
        player as cli_player,
        system as cli_system,
        web as cli_web,
    )
except ImportError as e:
    logger.critical(
        f"CRITICAL ERROR: Failed to import application modules ({e}) after initial setup.",
        exc_info=True,
    )
    print(
        f"CRITICAL ERROR: Failed to import application modules ({e}). Check installation.",
        file=sys.stderr,
    )
    sys.exit(1)


def run_cleanup(args: argparse.Namespace) -> None:
    """
    Performs cleanup operations (__pycache__, logs) based on command line arguments.

    Args:
        args: The parsed command line arguments namespace.
    """
    logger.info("CLI: Running cleanup operations...")
    # Import cleanup module only when needed
    try:
        from bedrock_server_manager.utils import cleanup
    except ImportError as e:
        logger.error(f"Cleanup module not found: {e}", exc_info=True)
        print(f"{_ERROR_PREFIX}Cleanup module failed to import.")
        return

    cleaned_something = False
    # Check if specific cleanup flags are provided
    if not args.cache and not args.logs:
        print(
            f"{_WARN_PREFIX}No cleanup options specified. Use --cache, --logs, or both."
        )
        logger.warning("Cleanup command run without --cache or --logs flag.")
        return

    if args.cache:
        logger.debug("Cleaning up __pycache__ directories...")
        print(f"{_INFO_PREFIX}Cleaning Python cache files (__pycache__)...")
        try:
            deleted_count = cleanup.cleanup_cache()
            if deleted_count > 0:
                print(
                    f"{_OK_PREFIX}Cleaned up {deleted_count} __pycache__ director(y/ies)."
                )
                logger.info(f"Cleaned up {deleted_count} __pycache__ directories.")
                cleaned_something = True
            else:
                print(f"{_INFO_PREFIX}No __pycache__ directories found to clean.")
                logger.info("No __pycache__ directories found.")
        except Exception as e:
            print(f"{_ERROR_PREFIX}Error during cache cleanup: {e}")
            logger.error(f"Error during cache cleanup: {e}", exc_info=True)

    if args.logs:
        log_dir_to_clean = args.log_dir or settings.get("LOG_DIR")
        if not log_dir_to_clean:
            print(
                f"{_ERROR_PREFIX}Log directory not specified via --log-dir or settings."
            )
            logger.error("Cannot clean logs: Log directory not specified.")
            return

        logger.debug(f"Cleaning up log files in '{log_dir_to_clean}'...")
        print(f"{_INFO_PREFIX}Cleaning log files in '{log_dir_to_clean}'...")
        try:
            deleted_count = cleanup.cleanup_logs(log_dir=log_dir_to_clean)
            if deleted_count > 0:
                print(f"{_OK_PREFIX}Cleaned up {deleted_count} log file(s).")
                logger.info(
                    f"Cleaned up {deleted_count} log files from '{log_dir_to_clean}'."
                )
                cleaned_something = True
            else:
                print(
                    f"{_INFO_PREFIX}No log files found to clean in '{log_dir_to_clean}'."
                )
                logger.info(f"No log files found to clean in '{log_dir_to_clean}'.")
        except Exception as e:
            print(f"{_ERROR_PREFIX}Error during log cleanup: {e}")
            logger.error(f"Error during log cleanup: {e}", exc_info=True)

    if cleaned_something:
        logger.info("CLI: Cleanup operations finished.")
    else:
        logger.info("CLI: Cleanup operations finished, nothing was cleaned.")


def main() -> None:
    """
    Main execution function for the CLI.

    Performs initial checks, parses arguments, and dispatches to the appropriate command handler.
    """
    try:
        # --- Initial Checks ---
        logger.info(f"Starting {app_name} v{__version__}...")
        startup_checks(app_name, __version__)  # Handles Python version, creates dirs
        system_base.check_prerequisites()  # Check for screen, systemctl, etc.

        # --- Resolve Base/Config Dirs ---
        base_dir = settings.get("BASE_DIR")
        config_dir = getattr(settings, "_config_dir", None)
        if not base_dir:
            # Base dir is essential, exit if not set
            raise FileOperationError(
                "CRITICAL: BASE_DIR setting is missing or empty. Cannot continue."
            )
        if not config_dir:
            # Config dir is also essential for most operations
            raise FileOperationError(
                "CRITICAL: Configuration directory could not be determined. Cannot continue."
            )

        logger.debug(f"Using Base Directory: {base_dir}")
        logger.debug(f"Using Config Directory: {config_dir}")

        # Update statuses on startup
        try:
            logger.debug("Performing initial update of server statuses...")
            api_utils.update_server_statuses(base_dir, config_dir)
        except Exception as status_update_e:
            logger.warning(
                f"Could not update server statuses on startup: {status_update_e}",
                exc_info=True,
            )

        # --- Argument Parsing ---
        parser = argparse.ArgumentParser(
            description=f"{app_name} - Manage Minecraft Bedrock Servers.",
            epilog="Run a command with -h for specific help, e.g., 'bedrock-server-manager start-server -h'",
        )
        parser.add_argument(
            "-v", "--version", action="version", version=f"{app_name} {__version__}"
        )
        subparsers = parser.add_subparsers(
            title="Available Commands",
            dest="subcommand",
            metavar="COMMAND",
            help="Use '<command> --help' for more information on a specific command.",
        )
        subparsers.required = False

        # --- Subparser Definitions ---

        # Helper function to add --server argument consistently
        def add_server_arg(sub_parser: argparse.ArgumentParser):
            sub_parser.add_argument(
                "-s", "--server", help="Name of the target server", required=True
            )

        # main (Main CLI Menu)
        main_parser = subparsers.add_parser("main", help="Open the main CLI menu")

        # list-servers
        list_parser = subparsers.add_parser(
            "list-servers", help="List all servers and their statuses"
        )
        list_parser.add_argument(
            "-l",
            "--loop",
            action="store_true",
            help="Continuously list server statuses (Ctrl+C to exit)",
        )

        # get-status
        status_parser = subparsers.add_parser(
            "get-status", help="Get the status of a specific server (from config)"
        )
        add_server_arg(status_parser)

        # configure-allowlist
        allowlist_parser = subparsers.add_parser(
            "configure-allowlist",
            help="Interactively configure the allowlist for a server",
        )
        add_server_arg(allowlist_parser)

        # configure-permissions
        permissions_parser = subparsers.add_parser(
            "configure-permissions",
            help="Interactively configure permissions for a server",
        )
        add_server_arg(permissions_parser)

        # configure-properties
        config_parser = subparsers.add_parser(
            "configure-properties",
            help="Configure server.properties interactively or set a single property",
        )
        add_server_arg(config_parser)
        config_parser.add_argument(
            "-p", "--property", help="Name of the property to set directly"
        )
        config_parser.add_argument(
            "-v", "--value", help="New value for the property (use with --property)"
        )

        # install-server
        install_parser = subparsers.add_parser(
            "install-server", help="Install a new server interactively"
        )

        # update-server
        update_server_parser = subparsers.add_parser(
            "update-server", help="Update an existing server to its target version"
        )
        add_server_arg(update_server_parser)

        # start-server, stop-server, restart-server
        start_server_parser = subparsers.add_parser(
            "start-server", help="Start a server"
        )
        add_server_arg(start_server_parser)
        stop_server_parser = subparsers.add_parser("stop-server", help="Stop a server")
        add_server_arg(stop_server_parser)
        restart_parser = subparsers.add_parser(
            "restart-server", help="Restart a server"
        )
        add_server_arg(restart_parser)
        restart_parser.add_argument(
            "--no-warn",
            action="store_false",
            dest="send_message",
            default=True,
            help="Do not send in-game warning before restart",
        )

        # install-world, install-addon
        install_world_parser = subparsers.add_parser(
            "install-world",
            help="Install a world from a .mcworld file (interactive selection or specified file)",
        )
        add_server_arg(install_world_parser)
        install_world_parser.add_argument(
            "-f", "--file", help="Full path to the .mcworld file to install directly"
        )
        addon_parser = subparsers.add_parser(
            "install-addon",
            help="Install an addon (.mcaddon or .mcpack) interactively or from specified file",
        )
        add_server_arg(addon_parser)
        addon_parser.add_argument(
            "-f", "--file", help="Full path to the addon file to install directly"
        )

        # attach-console
        attach_parser = subparsers.add_parser(
            "attach-console",
            help="Attach to the server console screen session (Linux only)",
        )
        add_server_arg(attach_parser)

        # delete-server
        delete_parser = subparsers.add_parser(
            "delete-server", help="Delete ALL data for a server (irreversible!)"
        )
        add_server_arg(delete_parser)
        delete_parser.add_argument(
            "-y",
            "--yes",
            action="store_true",
            help="Bypass confirmation prompt (use with caution!)",
        )

        # backup-server, restore-server
        backup_parser = subparsers.add_parser(
            "backup-server", help="Backup server files (interactive or specified type)"
        )
        add_server_arg(backup_parser)
        backup_parser.add_argument(
            "-t",
            "--type",
            choices=["world", "config", "all"],
            help="Backup type (required if not interactive)",
        )
        backup_parser.add_argument(
            "-f",
            "--file",
            help="Specific relative config file path to backup (required for type 'config')",
        )
        backup_parser.add_argument(
            "--no-stop",
            action="store_false",
            dest="change_status",
            default=True,
            help="Attempt backup without stopping the server (may risk data corruption)",
        )
        restore_parser = subparsers.add_parser(
            "restore-server",
            help="Restore server files from backup (interactive or specified file)",
        )
        add_server_arg(restore_parser)
        restore_parser.add_argument(
            "-f",
            "--file",
            help="Full path to the backup file to restore (required if not interactive)",
        )
        restore_parser.add_argument(
            "-t",
            "--type",
            choices=["world", "config", "all"],
            help="Restore type (required if not interactive)",
        )
        restore_parser.add_argument(
            "--no-stop",
            action="store_false",
            dest="change_status",
            default=True,
            help="Attempt restore without stopping the server (may risk data corruption)",
        )

        # backup-all (shortcut for backup-server -t all)
        backup_all_parser = subparsers.add_parser(
            "backup-all", help="Backup server world and standard configuration files"
        )
        add_server_arg(backup_all_parser)
        backup_all_parser.add_argument(
            "--no-stop",
            action="store_false",
            dest="change_status",
            default=True,
            help="Attempt backup without stopping the server",
        )

        # restore-all (shortcut for restore-server -t all)
        restore_all_parser = subparsers.add_parser(
            "restore-all", help="Restore server world and config from latest backups"
        )
        add_server_arg(restore_all_parser)
        restore_all_parser.add_argument(
            "--no-stop",
            action="store_false",
            dest="change_status",
            default=True,
            help="Attempt restore without stopping the server",
        )

        # scan-players
        scan_players_parser = subparsers.add_parser(
            "scan-players",
            help="Scan all server logs for player connections and update players.json",
        )

        # add-players (manual player entry)
        add_players_parser = subparsers.add_parser(
            "add-players", help="Manually add players to players.json"
        )
        add_players_parser.add_argument(
            "-p",
            "--players",
            help="One or more players in 'PlayerName:XUID' format",
            nargs="+",
            required=True,
        )

        # monitor-usage
        monitor_parser = subparsers.add_parser(
            "monitor-usage",
            help="Monitor live resource usage (CPU/Mem) for a server (Ctrl+C to exit)",
        )
        add_server_arg(monitor_parser)

        # prune-old-backups
        prune_old_backups_parser = subparsers.add_parser(
            "prune-old-backups",
            help="Delete old backups for a server, keeping the newest N",
        )
        add_server_arg(prune_old_backups_parser)
        prune_old_backups_parser.add_argument(
            "-k",
            "--keep",
            help=f"Number of backups to keep (default: from settings, currently {settings.get('BACKUP_KEEP', 'Not Set')})",
            type=int,
        )

        # prune-old-downloads
        prune_old_downloads_parser = subparsers.add_parser(
            "prune-old-downloads", help="Delete old server downloads (zip files)"
        )
        prune_old_downloads_parser.add_argument(
            "-d",
            "--download-dir",
            help="Specific downloads directory (e.g., /path/to/.downloads/stable)",
            required=True,
        )
        prune_old_downloads_parser.add_argument(
            "-k",
            "--keep",
            help=f"Number of downloads to keep (default: from settings, currently {settings.get('DOWNLOAD_KEEP', 'Not Set')})",
            type=int,
        )

        # manage-script-config
        manage_script_config_parser = subparsers.add_parser(
            "manage-script-config", help="Read/Write key in apps specific JSON config"
        )
        manage_script_config_parser.add_argument(
            "-k", "--key", required=True, help="Config key"
        )
        manage_script_config_parser.add_argument(
            "-o",
            "--operation",
            required=True,
            choices=["read", "write"],
            help="Operation: read or write",
        )
        manage_script_config_parser.add_argument(
            "-v", "--value", help="Value to write (required for 'write' operation)"
        )
        # manage-server-config
        manage_server_config_parser = subparsers.add_parser(
            "manage-server-config",
            help="Read/Write key in server's specific JSON config",
        )
        add_server_arg(manage_server_config_parser)
        manage_server_config_parser.add_argument(
            "-k", "--key", required=True, help="Configuration key name"
        )
        manage_server_config_parser.add_argument(
            "-o",
            "--operation",
            required=True,
            choices=["read", "write"],
            help="Operation: read or write",
        )
        manage_server_config_parser.add_argument(
            "-v", "--value", help="Value to write (required for 'write' operation)"
        )

        # get-installed-version
        get_installed_version_parser = subparsers.add_parser(
            "get-installed-version", help="Get installed version from server config"
        )
        add_server_arg(get_installed_version_parser)

        # get-world-name
        get_world_name_parser = subparsers.add_parser(
            "get-world-name",
            help="Get configured world name (level-name) from server properties",
        )
        add_server_arg(get_world_name_parser)

        # check-service-exist, create-service, enable-service, disable-service (systemd)
        check_service_exist_parser = subparsers.add_parser(
            "check-service-exist",
            help="Check if systemd user service file exists (Linux only)",
        )
        add_server_arg(check_service_exist_parser)
        create_service_parser = subparsers.add_parser(
            "create-service",
            help="Interactively create/configure OS service (systemd/Windows autoupdate flag)",
        )
        add_server_arg(create_service_parser)
        enable_service_parser = subparsers.add_parser(
            "enable-service", help="Enable systemd service autostart (Linux only)"
        )
        add_server_arg(enable_service_parser)
        disable_service_parser = subparsers.add_parser(
            "disable-service", help="Disable systemd service autostart (Linux only)"
        )
        add_server_arg(disable_service_parser)

        # is-server-running
        is_server_running_parser = subparsers.add_parser(
            "is-server-running",
            help="Check if server process is currently running (returns True/False)",
        )
        add_server_arg(is_server_running_parser)

        # send-command
        send_command_parser = subparsers.add_parser(
            "send-command", help="Send a command to a running server"
        )
        add_server_arg(send_command_parser)
        send_command_parser.add_argument(
            "-c", "--command", help="Command string to send", required=True, nargs="+"
        )  # Allow spaces in command

        # export-world
        export_world_parser = subparsers.add_parser(
            "export-world",
            help="Export server world to a .mcworld file in backup directory",
        )
        add_server_arg(export_world_parser)

        # validate-server
        validate_server_parser = subparsers.add_parser(
            "validate-server", help="Check if server directory and executable exist"
        )
        add_server_arg(validate_server_parser)

        # check-internet-connectivity
        check_internet_parser = subparsers.add_parser(
            "check-internet", help="Check basic internet connectivity"
        )

        # cleanup
        cleanup_parser = subparsers.add_parser(
            "cleanup", help="Clean up generated files"
        )
        cleanup_parser.add_argument(
            "-c",
            "--cache",
            action="store_true",
            help="Clean up __pycache__ directories",
        )
        cleanup_parser.add_argument(
            "-l",
            "--logs",
            action="store_true",
            help="Clean up log files in configured LOG_DIR",
        )
        cleanup_parser.add_argument(
            "-ld",
            "--log-dir",
            help="Override log directory for cleanup (default: from settings)",
        )

        # systemd-stop / systemd-start (Internal use by systemd service file)
        systemd_stop_parser = subparsers.add_parser(
            "systemd-stop", help=argparse.SUPPRESS
        )  # Hide from help
        add_server_arg(systemd_stop_parser)
        systemd_start_parser = subparsers.add_parser(
            "systemd-start", help=argparse.SUPPRESS
        )  # Hide from help
        add_server_arg(systemd_start_parser)

        # --- Web-Server ---
        web_server_start_parser = subparsers.add_parser(
            "start-web-server", help="Start the web management interface"
        )
        web_server_start_parser.add_argument(
            "-H",
            "--host",
            help="One or more host addresses/hostnames to bind to (space-separated). Default: all IPv4/IPv6.",
            required=False,
            nargs="+",
        )
        web_server_start_parser.add_argument(
            "-d",
            "--debug",
            help="Start Flask development server in debug mode (NOT for production)",
            action="store_true",
        )
        web_server_start_parser.add_argument(
            "-m",
            "--mode",
            choices=["direct", "detached"],
            default="direct",
            help="Run mode: direct (takes over current console) or detached (runs in background)",
        )

        web_server_stop_parser = subparsers.add_parser(
            "stop-web-server",
            help="Stop the detached web server process (NOT IMPLEMENTED)",
        )

        # --- Command Dispatch Dictionary ---
        # Maps subcommand names to lambda functions calling the appropriate CLI handler
        commands = {
            "main": lambda args: main_menus.main_menu(base_dir, config_dir),
            "list-servers": lambda args: (
                cli_utils.list_servers_loop(base_dir, config_dir)
                if args.loop
                else cli_utils.list_servers_status(base_dir, config_dir)
            ),
            "get-status": lambda args: print(
                server_base.get_server_status_from_config(args.server, config_dir)
            ),
            "configure-allowlist": lambda args: cli_server_install_config.configure_allowlist(
                args.server, base_dir
            ),
            "configure-permissions": lambda args: cli_server_install_config.select_player_for_permission(
                args.server, base_dir, config_dir
            ),
            "configure-properties": lambda args: (
                # Call interactive config if only server name provided
                cli_server_install_config.configure_server_properties(
                    args.server, base_dir
                )
                if not args.property
                else
                # Call direct property modification if property and value are given
                (
                    lambda: (
                        (
                            # Validate first
                            validation := api_server_install_config.validate_server_property_value(
                                args.property, args.value
                            ),
                            # Print error or modify
                            (
                                print(f"{_ERROR_PREFIX}{validation.get('message')}")
                                if validation.get("status") == "error"
                                else (
                                    # Modify using core function directly for single property set
                                    server_base.modify_server_properties(
                                        os.path.join(
                                            base_dir, args.server, "server.properties"
                                        ),
                                        args.property,
                                        args.value,
                                    ),
                                    print(
                                        f"{_OK_PREFIX}Property '{args.property}' set to '{args.value}'."
                                    ),
                                )
                            ),
                        )
                        if args.value is not None
                        else print(
                            f"{_ERROR_PREFIX}Value (--value) is required when using --property."
                        )
                    )
                )
            ),
            "install-server": lambda args: cli_server_install_config.install_new_server(
                base_dir, config_dir
            ),
            "update-server": lambda args: cli_server_install_config.update_server(
                args.server, base_dir
            ),
            "start-server": lambda args: cli_server.start_server(args.server, base_dir),
            "stop-server": lambda args: cli_server.stop_server(args.server, base_dir),
            "install-world": lambda args: (
                cli_world.import_world_cli(
                    args.server, args.file, base_dir
                )  # Call direct import if file specified
                if args.file
                else cli_world.install_worlds(
                    args.server, base_dir
                )  # Call interactive menu otherwise
            ),
            "install-addon": lambda args: (
                cli_addon.import_addon(
                    args.server, args.file, base_dir
                )  # Call direct import if file specified
                if args.file
                else cli_addon.install_addons(
                    args.server, base_dir
                )  # Call interactive menu otherwise
            ),
            "restart-server": lambda args: cli_server.restart_server(
                args.server, base_dir, args.send_message
            ),
            "attach-console": lambda args: cli_utils.attach_console(args.server),
            "delete-server": lambda args: cli_server.delete_server(
                args.server, base_dir, config_dir, skip_confirmation=args.yes
            ),
            "backup-server": lambda args: cli_backup_restore.backup_server(
                args.server, args.type, args.file, args.change_status, base_dir
            ),
            "backup-all": lambda args: cli_backup_restore.backup_server(
                args.server,
                "all",
                file_to_backup=None,
                change_status=args.change_status,
                base_dir=base_dir,
            ),
            "restore-server": lambda args: cli_backup_restore.restore_server(
                args.server, args.file, args.type, args.change_status, base_dir
            ),
            "restore-all": lambda args: cli_backup_restore.restore_server(
                args.server,
                "all",
                backup_file=None,
                change_status=args.change_status,
                base_dir=base_dir,
            ),
            "scan-players": lambda args: cli_player.scan_for_players(
                base_dir, config_dir
            ),
            "add-players": lambda args: cli_player.add_players(
                args.players, config_dir
            ),
            "monitor-usage": lambda args: cli_system.monitor_service_usage(
                args.server, base_dir
            ),
            "prune-old-backups": lambda args: cli_backup_restore.prune_old_backups(
                args.server,
                file_name=args.file_name,
                backup_keep=args.keep,
                base_dir=base_dir,
            ),
            "prune-old-downloads": lambda args: downloader.prune_old_downloads(
                args.download_dir, args.keep
            ),  # Call core directly
            "manage-script-config": lambda: (
                print(settings.get(args.key))
                if args.operation == "read"
                else settings.set(args.key, args.value)
            ),
            "manage-server-config": lambda args: (
                # Print return value only for 'read'
                (
                    lambda v: print(
                        v
                        if v is not None
                        else f"{_WARN_PREFIX}Key '{args.key}' not found."
                    )
                )(
                    server_base.manage_server_config(
                        args.server, args.key, "read", config_dir=config_dir
                    )
                )
                if args.operation == "read"
                else
                # Call write operation (returns None), print success/fail based on exception
                (
                    lambda: (
                        (
                            server_base.manage_server_config(
                                args.server,
                                args.key,
                                "write",
                                args.value,
                                config_dir=config_dir,
                            ),
                            print(
                                f"{_OK_PREFIX}Set '{args.key}' to '{args.value}' in {args.server} config."
                            ),
                        )
                        if args.value is not None
                        else print(
                            f"{_ERROR_PREFIX}Value (--value) required for write operation."
                        )
                    )
                )
            ),
            "get-installed-version": lambda args: print(
                server_base.get_installed_version(args.server, config_dir)
            ),
            "get-world-name": lambda args: print(
                server_base.get_world_name(args.server, base_dir)
            ),
            "check-service-exist": lambda args: print(
                system_linux.check_service_exist(args.server)
            ),
            "create-service": lambda args: cli_system.configure_service(
                args.server, base_dir
            ),
            "enable-service": lambda args: cli_system.enable_service(args.server),
            "disable-service": lambda args: cli_system.disable_service(args.server),
            "is-server-running": lambda args: print(
                system_base.is_server_running(args.server, base_dir)
            ),
            "send-command": lambda args: cli_server.send_command(
                args.server, " ".join(args.command), base_dir
            ),  # Join command parts
            "export-world": lambda args: cli_world.export_world(args.server, base_dir),
            "validate-server": lambda args: print(
                api_utils.validate_server_exist(args.server, base_dir)
            ),  # Print the result dict
            "check-internet": lambda args: (
                lambda result: (
                    print(f"{_OK_PREFIX}Internet connectivity OK.")
                    if result
                    else print(f"{_ERROR_PREFIX}Internet connectivity check failed.")
                )
            )(
                system_base.check_internet_connectivity()
            ),  # Call core func and print result
            "cleanup": lambda args: run_cleanup(args),
            "systemd-stop": lambda args: cli_server.systemd_stop_server(
                args.server, base_dir
            ),
            "systemd-start": lambda args: cli_server.systemd_start_server(
                args.server, base_dir
            ),
            "start-web-server": lambda args: cli_web.start_web_server(
                args.host, args.debug, args.mode
            ),
            "stop-web-server": lambda args: cli_web.stop_web_server(),
        }

        # --- Parse Arguments and Execute ---
        args = parser.parse_args()
        logger.debug(f"Parsed arguments: {args}")

        if args.subcommand in commands:
            logger.debug(f"Executing command: {args.subcommand}")
            commands[args.subcommand](args)  # Execute the corresponding lambda function
            logger.debug(f"Command '{args.subcommand}' finished.")
            sys.exit(0)  # Explicit success exit
        elif args.subcommand is None:
            # No command given, show main menu by default
            logger.info("No subcommand provided, launching help display...")
            parser.print_help()  # Print help display
        else:
            # Should not happen if choices are restricted, but handle anyway
            logger.error(f"Unknown subcommand provided: {args.subcommand}")
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user (Ctrl+C).")
        logger.warning("Application terminated by user (KeyboardInterrupt).")
        sys.exit(1)
    except Exception as e:
        # Catch-all for unexpected errors during setup or dispatch
        print(
            f"\n{_ERROR_PREFIX}An critical unexpected error occurred: {type(e).__name__}: {e}"
        )
        logger.critical(
            f"An unexpected critical error occurred in main: {e}", exc_info=True
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
