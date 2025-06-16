# bedrock_server_manager/cli/cleanup.py
"""
Defines the `bsm cleanup` command for removing generated files.

This module provides a utility command for project maintenance, allowing for
the removal of Python bytecode cache (`__pycache__`) and application logs.
This is useful for creating a clean state or reducing disk space usage.
"""

import logging
import shutil
from pathlib import Path
from typing import Optional

import click

from bedrock_server_manager.config.settings import settings

logger = logging.getLogger(__name__)


# --- Core Cleanup Functions ---


def _cleanup_pycache() -> int:
    """Finds and removes all `__pycache__` directories within the project.

    It traverses up from the current file's location to find the project
    root and then recursively removes all `__pycache__` directories.

    Returns:
        The number of directories deleted.
    """
    try:
        # Assumes this file is at bedrock_server_manager/cli/cleanup.py.
        # .parents[0] is 'cli', .parents[1] is 'bedrock_server_manager',
        # .parents[2] is the project root directory.
        project_root = Path(__file__).resolve().parents[2]
        deleted_count = 0

        for cache_dir in project_root.rglob("__pycache__"):
            if cache_dir.is_dir():
                logger.debug(f"Removing pycache directory: {cache_dir}")
                shutil.rmtree(cache_dir)
                deleted_count += 1
        return deleted_count

    except Exception as e:
        logger.error(f"Error during pycache cleanup: {e}", exc_info=True)
        click.secho(f"An error occurred during cache cleanup: {e}", fg="red")
        return 0


def _cleanup_log_files(log_dir_path: Path) -> int:
    """Deletes all `.log` files in the specified directory.

    Args:
        log_dir_path: The `pathlib.Path` object for the log directory.

    Returns:
        The number of log files deleted.
    """
    if not log_dir_path.is_dir():
        message = f"Log directory '{log_dir_path}' does not exist."
        click.secho(f"Warning: {message}", fg="yellow")
        logger.warning(f"Log cleanup skipped: {message}")
        return 0

    deleted_count = 0
    try:
        for log_file in log_dir_path.glob("*.log"):
            logger.debug(f"Removing log file: {log_file.name}")
            log_file.unlink()
            deleted_count += 1
        return deleted_count
    except Exception as e:
        logger.error(
            f"Error during log cleanup in '{log_dir_path}': {e}", exc_info=True
        )
        click.secho(f"An error occurred during log cleanup: {e}", fg="red")
        return 0


# --- The Click Command ---


@click.command("cleanup")
@click.option(
    "-c",
    "--cache",
    is_flag=True,
    help="Clean up Python bytecode cache files (__pycache__).",
)
@click.option(
    "-l", "--logs", is_flag=True, help="Clean up application log files (*.log)."
)
@click.option(
    "--log-dir",
    "log_dir_override",
    type=click.Path(file_okay=False, resolve_path=True, path_type=Path),
    help="Override the default log directory from settings.",
)
def cleanup(cache: bool, logs: bool, log_dir_override: Optional[Path]):
    """Cleans up generated application files like logs and Python cache.

        This maintenance command helps keep the project directory clean. At
        least one flag (--cache or --logs) must be provided to perform an
    action.

        Args:
            cache: If True, removes `__pycache__` directories.
            logs: If True, removes `.log` files from the log directory.
            log_dir_override: An optional path to specify a custom log directory.

        Raises:
            click.Abort: If log cleaning is requested but no log directory can be found.
    """
    logger.info("CLI: Running cleanup command...")

    if not cache and not logs:
        click.secho(
            "No cleanup options specified. Use --cache, --logs, or both.", fg="yellow"
        )
        logger.warning("Cleanup command run without any action flags.")
        return

    was_anything_cleaned = False

    if cache:
        click.secho("\nCleaning Python cache files (__pycache__)...", bold=True)
        deleted_count = _cleanup_pycache()
        if deleted_count > 0:
            click.secho(
                f"Success: Cleaned up {deleted_count} __pycache__ director(ies).",
                fg="green",
            )
            logger.info(f"Cleaned {deleted_count} __pycache__ directories.")
            was_anything_cleaned = True
        else:
            click.secho("Info: No __pycache__ directories found to clean.", fg="cyan")
            logger.info("No __pycache__ directories found.")

    if logs:
        click.secho("\nCleaning log files...", bold=True)

        # Determine the correct log directory, prioritizing the command-line override.
        final_log_dir = log_dir_override
        if not final_log_dir:
            settings_log_dir = settings.get("LOG_DIR")
            if settings_log_dir:
                final_log_dir = Path(settings_log_dir)

        if not final_log_dir:
            msg = (
                "Log directory not specified via --log-dir or in application settings."
            )
            click.secho(f"Error: {msg}", fg="red")
            logger.error(f"Cannot clean logs: {msg}")
            raise click.Abort()

        click.echo(f"Targeting log directory: {final_log_dir}")
        deleted_count = _cleanup_log_files(final_log_dir)

        if deleted_count > 0:
            click.secho(
                f"Success: Cleaned up {deleted_count} log file(s) from '{final_log_dir}'.",
                fg="green",
            )
            logger.info(f"Cleaned {deleted_count} log files from '{final_log_dir}'.")
            was_anything_cleaned = True
        else:
            click.secho(
                f"Info: No log files found to clean in '{final_log_dir}'.", fg="cyan"
            )
            logger.info(f"No log files found in '{final_log_dir}'.")

    if was_anything_cleaned:
        logger.info("CLI: Cleanup operations finished successfully.")
    else:
        logger.info("CLI: Cleanup operations finished, nothing was cleaned.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cleanup()
