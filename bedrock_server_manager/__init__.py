# bedrock-server-manager/bedrock_server_manager/__init__.py
import sys
import argparse
import os
from bedrock_server_manager import cli
from bedrock_server_manager.core.player import player
from bedrock_server_manager.core.download import downloader
from bedrock_server_manager.config.settings import settings
from importlib.metadata import version, PackageNotFoundError
from bedrock_server_manager.core import logging as core_logging
from bedrock_server_manager.utils.general import startup_checks
from bedrock_server_manager.core.server import server as server_base
from bedrock_server_manager.core.system import (
    base as system_base,
    linux as system_linux,
)

# Configure logging
logger = core_logging.setup_logging(log_dir=settings.get("LOG_DIR"))

try:
    __version__ = version("bedrock-server-manager")
except PackageNotFoundError:
    __version__ = "0.0.0"


def run_cleanup(args):
    """
    Performs cleanup operations based on command line arguments
    """
    from bedrock_server_manager import cleanup

    # Check for cleanup options and ensure at least one is provided
    if not any([args.cache, args.logs]):
        print("No cleanup options specified. Use --cache, --logs, or both.")
        return
    if args.cache:
        result = cleanup.cleanup_cache(args.verbose)
        if result:
            print(f"Cleaned up {result} __pycache__ directories")
    if args.logs:
        result = cleanup.cleanup_logs(args.log_dir, args.verbose)
        if result:
            print(f"Cleaned up {result} log files")


def main():
    """
    Main entry point for the Bedrock Server Manager application.
    """
    startup_checks()
    system_base.check_prerequisites()
    config_dir = settings._config_dir
    base_dir = settings.get("BASE_DIR")

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Bedrock Server Manager")
    subparsers = parser.add_subparsers(title="commands", dest="subcommand")

    # --- Subparser Definitions ---

    # Helper function to add server argument
    def add_server_arg(parser):
        parser.add_argument("-s", "--server", help="Server name", required=True)

    # main-menu
    main_parser = subparsers.add_parser("main", help="Open Bedrock Server Manager menu")

    # list-servers
    list_parser = subparsers.add_parser(
        "list-servers", help="List all servers and their statuses"
    )
    list_parser.add_argument(
        "-l", "--loop", action="store_true", help="Continuously list servers"
    )

    # get-status
    status_parser = subparsers.add_parser(
        "get-status", help="Get the status of a specific server"
    )
    add_server_arg(status_parser)

    # configure-allowlist
    allowlist_parser = subparsers.add_parser(
        "configure-allowlist", help="Configure the allowlist for a server"
    )
    add_server_arg(allowlist_parser)

    # configure-permissions
    permissions_parser = subparsers.add_parser(
        "configure-permissions", help="Configure permissions for a server"
    )
    add_server_arg(permissions_parser)

    # configure-properties
    config_parser = subparsers.add_parser(
        "configure-properties", help="Configure individual server.properties"
    )
    add_server_arg(config_parser)
    config_parser.add_argument(
        "-p", "--property", help="Name of the property to modify", required=True
    )
    config_parser.add_argument(
        "-v", "--value", help="New value for the property", required=True
    )

    # install-server
    install_parser = subparsers.add_parser(
        "install-server", help="Install a new server"
    )

    # update-server
    update_server_parser = subparsers.add_parser(
        "update-server", help="Update an existing server"
    )
    add_server_arg(update_server_parser)
    update_server_parser.add_argument(
        "-v",
        "--version",
        help="Server version (LATEST, PREVIEW, or specific)",
        default="LATEST",
    )

    # start-server, stop-server, restart-server
    start_server_parser = subparsers.add_parser("start-server", help="Start a server")
    add_server_arg(start_server_parser)
    stop_server_parser = subparsers.add_parser("stop-server", help="Stop a server")
    add_server_arg(stop_server_parser)
    restart_parser = subparsers.add_parser("restart-server", help="Restart a server")
    add_server_arg(restart_parser)

    # install-world, install-addon
    install_world_parser = subparsers.add_parser(
        "install-world", help="Install a world from a .mcworld file"
    )
    add_server_arg(install_world_parser)
    install_world_parser.add_argument("-f", "--file", help="Path to the .mcworld file")
    addon_parser = subparsers.add_parser(
        "install-addon", help="Install an addon (.mcaddon or .mcpack)"
    )
    add_server_arg(addon_parser)
    addon_parser.add_argument("-f", "--file", help="Path to the addon file")

    # attach-console
    attach_parser = subparsers.add_parser(
        "attach-console", help="Attach to the server console (Linux only)"
    )
    add_server_arg(attach_parser)

    # delete-server
    delete_parser = subparsers.add_parser("delete-server", help="Delete a server")
    add_server_arg(delete_parser)

    # backup-server, restore-server
    backup_parser = subparsers.add_parser("backup-server", help="Backup server files")
    add_server_arg(backup_parser)
    backup_parser.add_argument(
        "-t", "--type", help="Backup type (world, config, all)", required=True
    )
    backup_parser.add_argument(
        "-f", "--file", help="Specific file to backup (for config type)"
    )
    backup_parser.add_argument(
        "--no-stop",
        action="store_false",
        dest="change_status",
        default=True,
        help="Don't stop server for backup",
    )
    restore_parser = subparsers.add_parser(
        "restore-server", help="Restore server files from backup"
    )
    add_server_arg(restore_parser)
    restore_parser.add_argument(
        "-f", "--file", help="Path to the backup file", required=True
    )
    restore_parser.add_argument(
        "-t", "--type", help="Restore type (world, config)", required=True
    )
    restore_parser.add_argument(
        "--no-stop",
        action="store_false",
        dest="change_status",
        default=True,
        help="Don't stop server for restore",
    )

    # backup-all, restore-all
    backup_all_parser = subparsers.add_parser(
        "backup-all", help="Back up all server files"
    )
    add_server_arg(backup_all_parser)
    backup_all_parser.add_argument(
        "--no-stop",
        action="store_false",
        dest="change_status",
        default=True,
        help="Don't stop the server before backup",
    )
    restore_all_parser = subparsers.add_parser(
        "restore-all", help="Restore all newest files"
    )
    add_server_arg(restore_all_parser)
    restore_all_parser.add_argument(
        "--no-stop",
        action="store_false",
        dest="change_status",
        default=True,
        help="Don't stop the server before restore",
    )

    # scan-players
    scan_players_parser = subparsers.add_parser(
        "scan-players", help="Scan server logs for player data"
    )

    # add-players (manual player entry - you might want to revisit this)
    add_players_parser = subparsers.add_parser(
        "add-players", help="Manually add player:xuid to players.json"
    )
    add_players_parser.add_argument(
        "-p", "--players", help="<player1:xuid> <player2:xuid> ...", nargs="+"
    )

    # monitor-usage
    monitor_parser = subparsers.add_parser(
        "monitor-usage", help="Monitor server resource usage"
    )
    add_server_arg(monitor_parser)

    # manage-log-files, prune-old-backups, prune-old-downloads (utility commands)
    prune_old_backups_parser = subparsers.add_parser(
        "prune-old-backups", help="Prune old backups"
    )
    add_server_arg(prune_old_backups_parser)
    prune_old_backups_parser.add_argument(
        "-f", "--file-name", help="Specific file name to prune (for config files)."
    )
    prune_old_backups_parser.add_argument(
        "-k", "--keep", help="Number of backups to keep.", type=int
    )

    prune_old_downloads_parser = subparsers.add_parser(
        "prune-old-downloads", help="Prune old downloads"
    )
    prune_old_downloads_parser.add_argument(
        "-d", "--download-dir", help="Downloads directory.", required=True
    )
    prune_old_downloads_parser.add_argument(
        "-k", "--keep", help="Number of downloads to keep.", type=int, required=True
    )

    # manage-script-config, manage-server-config
    manage_script_config_parser = subparsers.add_parser(
        "manage-script-config", help="Manage script config"
    )
    manage_script_config_parser.add_argument(
        "-k", "--key", required=True, help="Config key"
    )
    manage_script_config_parser.add_argument(
        "-o", "--operation", required=True, choices=["read", "write"], help="Operation"
    )
    manage_script_config_parser.add_argument(
        "-v", "--value", help="Value (for write operation)"
    )
    manage_server_config_parser = subparsers.add_parser(
        "manage-server-config", help="Manage server config"
    )
    add_server_arg(manage_server_config_parser)
    manage_server_config_parser.add_argument(
        "-k", "--key", required=True, help="Config key"
    )
    manage_server_config_parser.add_argument(
        "-o", "--operation", required=True, choices=["read", "write"], help="Operation"
    )
    manage_server_config_parser.add_argument(
        "-v", "--value", help="Value (for write operation)"
    )

    # get-installed-version, check-server-status, get-server-status-from-config, get-world-name
    get_installed_version_parser = subparsers.add_parser(
        "get-installed-version", help="Get installed version"
    )
    add_server_arg(get_installed_version_parser)
    check_server_status_parser = subparsers.add_parser(
        "check-server-status", help="Check server status"
    )
    add_server_arg(check_server_status_parser)
    get_server_status_from_config_parser = subparsers.add_parser(
        "get-server-status-from-config", help="Get server status from config"
    )
    add_server_arg(get_server_status_from_config_parser)
    get_world_name_parser = subparsers.add_parser(
        "get-world-name", help="Get world name"
    )
    add_server_arg(get_world_name_parser)

    # check-service-exists, create-service, enable-service, disable-service (systemd)
    check_service_exists_parser = subparsers.add_parser(
        "check-service-exists", help="Check if systemd service exists (Linux)"
    )
    add_server_arg(check_service_exists_parser)
    create_service_parser = subparsers.add_parser(
        "create-service", help="Create systemd service (Linux)"
    )
    add_server_arg(create_service_parser)
    enable_service_parser = subparsers.add_parser(
        "enable-service", help="Enable systemd service (Linux)"
    )
    add_server_arg(enable_service_parser)
    disable_service_parser = subparsers.add_parser(
        "disable-service", help="Disable systemd service (Linux)"
    )
    add_server_arg(disable_service_parser)

    # is-server-running
    is_server_running_parser = subparsers.add_parser(
        "is-server-running", help="Check if server is running"
    )
    add_server_arg(is_server_running_parser)

    # send-command
    send_command_parser = subparsers.add_parser(
        "send-command", help="Send command to server"
    )
    add_server_arg(send_command_parser)
    send_command_parser.add_argument(
        "-c", "--command", help="Command to send", required=True, nargs="+"
    )

    # export-world
    export_world_parser = subparsers.add_parser(
        "export-world", help="Export world to .mcworld"
    )
    add_server_arg(export_world_parser)

    # validate-server
    validate_server_parser = subparsers.add_parser(
        "validate-server", help="Validates a server"
    )
    add_server_arg(validate_server_parser)
    # check-internet-connectivity
    check_internet_parser = subparsers.add_parser(
        "check-internet", help="Checks for internet connectivity"
    )

    # cleanup
    cleanup_parser = subparsers.add_parser(
        "cleanup", help="Clean up project files (cache, logs)"
    )
    cleanup_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    cleanup_parser.add_argument(
        "-c", "--cache", action="store_true", help="Clean up __pycache__ directories"
    )
    cleanup_parser.add_argument(
        "-l", "--logs", action="store_true", help="Clean up log files"
    )
    cleanup_parser.add_argument(
        "--log-dir", default=settings.get("LOG_DIR"), help="Log directory."
    )

    # systemd-stop
    systemd_stop_parser = subparsers.add_parser(
        "systemd-stop", help="Stop sever directly with screen"
    )
    add_server_arg(systemd_stop_parser)
    # systemd-start
    systemd_start_parser = subparsers.add_parser(
        "systemd-start", help="Start sever directly with screen"
    )
    add_server_arg(systemd_start_parser)

    # --- Command Dispatch Table ---
    commands = {
        "main": lambda: cli.main_menu(base_dir, config_dir),
        "list-servers": lambda: (
            cli.list_servers_loop(base_dir, config_dir)
            if args.loop
            else cli.list_servers_status(base_dir, config_dir)
        ),
        "get-status": lambda: print(
            server_base.get_server_status_from_config(args.server, config_dir)
        ),
        "configure-allowlist": lambda: cli.handle_configure_allowlist(
            args.server, base_dir
        ),
        "configure-permissions": lambda: cli.select_player_for_permission(
            args.server, base_dir, config_dir
        ),
        "configure-properties": lambda: server_base.modify_server_properties(
            server_properties=os.path.join(base_dir, args.server, "server.properties"),
            property_name=args.property,
            property_value=args.value,
        ),
        "install-server": lambda: cli.install_new_server(base_dir),
        "update-server": lambda: (
            (
                server_base.manage_server_config(
                    args.server, "target_version", "write", args.version
                )
                if args.version
                else None
            ),
            cli.update_server(args.server, base_dir),
        ),
        "start-server": lambda: cli.handle_start_server(args.server, base_dir),
        "stop-server": lambda: cli.handle_stop_server(args.server, base_dir),
        "install-world": lambda: (
            cli.handle_extract_world(args.server, args.file, base_dir)
            if args.file
            else cli.install_worlds(args.server, base_dir)
        ),
        "install-addon": lambda: (
            cli.handle_install_addon(args.server, args.file, base_dir)
            if args.file
            else cli.install_addons(args.server, base_dir)
        ),
        "restart-server": lambda: cli.restart_server(args.server, base_dir),
        "attach-console": lambda: cli.attach_console(args.server, base_dir),
        "delete-server": lambda: cli.delete_server(args.server, base_dir, config_dir),
        "backup-server": lambda: cli.handle_backup_server(
            args.server, args.type, args.file, args.change_status, base_dir
        ),
        "backup-all": lambda: cli.handle_backup_server(
            args.server, "all", None, args.change_status, base_dir
        ),
        "restore-server": lambda: cli.handle_restore_server(
            args.server, args.file, args.type, args.change_status, base_dir
        ),
        "restore-all": lambda: cli.handle_restore_server(
            args.server, None, "all", args.change_status, base_dir
        ),
        "scan-players": lambda: cli.scan_player_data(base_dir, config_dir),
        "add-players": lambda: cli.handle_add_players(args.players, config_dir),
        "monitor-usage": lambda: cli.monitor_service_usage(args.server, base_dir),
        "prune-old-backups": lambda: cli.handle_prune_old_backups(
            args.server,
            file_name=args.file_name,
            backup_keep=args.keep,
            base_dir=base_dir,
        ),
        "prune-old-downloads": lambda: downloader.prune_old_downloads(
            args.download_dir, args.keep
        ),
        "manage-script-config": lambda: (
            print(settings.get(args.key))
            if args.operation == "read"
            else settings.set(args.key, args.value)
        ),
        "manage-server-config": lambda: (
            print(
                server_base.manage_server_config(
                    args.server, args.key, args.operation, args.value
                )
            )
            if args.operation == "read"
            else server_base.manage_server_config(
                args.server, args.key, args.operation, args.value
            )
        ),
        "get-installed-version": lambda: print(
            server_base.get_installed_version(args.server)
        ),
        "check-server-status": lambda: print(
            server_base.check_server_status(args.server, base_dir)
        ),
        "get-server-status-from-config": lambda: print(
            server_base.get_server_status_from_config(args.server)
        ),
        "get-world-name": lambda: print(
            server_base.get_world_name(args.server, base_dir)
        ),
        "check-service-exists": lambda: print(
            system_linux.check_service_exists(args.server)
        ),
        "create-service": lambda: cli.create_service(args.server, base_dir),
        "enable-service": lambda: cli.enable_service(args.server),
        "disable-service": lambda: cli.disable_service(args.server),
        "is-server-running": lambda: print(
            system_base.is_server_running(args.server, base_dir)
        ),
        "send-command": lambda: server_base.BedrockServer(args.server).send_command(
            " ".join(args.command)
        ),
        "export-world": lambda: cli.handle_export_world(args.server, base_dir),
        "validate-server": lambda: print(
            server_base.validate_server(args.server, base_dir)
        ),
        "check-internet": lambda: print(system_base.check_internet_connectivity()),
        "cleanup": lambda: run_cleanup(args),
        "systemd-stop": lambda: print(cli.handle_systemd_stop(args.server, base_dir)),
        "systemd-start": lambda: print(cli.handle_systemd_start(args.server, base_dir)),
    }

    args = parser.parse_args()
    if args.subcommand in commands:
        try:
            commands[args.subcommand]()  # Execute the function
        except KeyboardInterrupt:
            print("\nOperation interrupted. Exiting...")
            sys.exit(1)
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {type(e).__name__}: {e}")
            sys.exit(1)
    elif args.subcommand is None:
        parser.print_help()  # Display help if no command is provided
    else:
        logger.error("Unimplemented command")  # Should not happen
        sys.exit(1)


if __name__ == "__main__":
    main()
