# bedrock_server_manager/cli/cleanup.py
"""
Provides a 'cleanup' command for removing generated files like caches and logs.
This version integrates detailed logging inspired by the original implementation.
"""

import logging
import shutil
from pathlib import Path

import click

from bedrock_server_manager.config.settings import settings

logger = logging.getLogger(__name__)

# --- Core Cleanup Functions (The "API" part) ---


def _cleanup_pycache() -> int:
    """
    Finds and removes all `__pycache__` directories within the project root.
    Returns the number of directories deleted.
    """
    try:
        project_root = Path(__file__).resolve().parents[2]
        deleted_count = 0

        for cache_dir in project_root.rglob("__pycache__"):
            if cache_dir.is_dir():
                logger.debug(f"Removing pycache directory: {cache_dir}")
                shutil.rmtree(cache_dir)
                deleted_count += 1

        return deleted_count
    except Exception as e:
        # Log the full exception for debugging
        logger.error(f"Error during pycache cleanup: {e}", exc_info=True)
        # Also provide a simple message to the user
        click.secho(f"An error occurred during cache cleanup: {e}", fg="red")
        return 0


def _cleanup_log_files(log_dir_path: Path) -> int:
    """
    Deletes all `.log` files in the specified directory.
    Returns the number of files deleted.
    """
    if not log_dir_path.is_dir():
        click.secho(
            f"Warning: Log directory '{log_dir_path}' does not exist.", fg="yellow"
        )
        logger.warning(f"Log cleanup skipped: Directory '{log_dir_path}' not found.")
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
    "-c", "--cache", is_flag=True, help="Clean up Python cache files (__pycache__)."
)
@click.option(
    "-l", "--logs", is_flag=True, help="Clean up application log files (*.log)."
)
@click.option(
    "--log-dir",
    "log_dir_override",  # Use a different variable name to avoid conflict with the logger name
    type=click.Path(file_okay=False, resolve_path=True, path_type=Path),
    help="Override the log directory specified in settings.",
)
def cleanup(cache: bool, logs: bool, log_dir_override: Path):
    """
    Cleans up generated files such as logs and Python cache.
    You must specify at least one flag (--cache or --logs) to perform an action.
    """
    logger.info("CLI: Running cleanup operations...")

    if not cache and not logs:
        click.secho(
            "No cleanup options specified. Use --cache, --logs, or both.", fg="yellow"
        )
        logger.warning("Cleanup command run without any action flags.")
        return

    cleaned_something = False

    if cache:
        logger.debug("Cleaning up __pycache__ directories...")
        click.secho("\nCleaning Python cache files (__pycache__)...", bold=True)
        deleted_count = _cleanup_pycache()
        if deleted_count > 0:
            msg = f"Cleaned up {deleted_count} __pycache__ director(y/ies)."
            click.secho(f"Success: {msg}", fg="green")
            logger.info(msg)
            cleaned_something = True
        else:
            msg = "No __pycache__ directories found to clean."
            click.secho(f"Info: {msg}", fg="cyan")
            logger.info(msg)

    if logs:
        click.secho("\nCleaning log files...", bold=True)

        # Determine the correct log directory to use
        final_log_dir = log_dir_override
        if not final_log_dir:
            settings_log_dir = settings.get("LOG_DIR")
            if settings_log_dir:
                final_log_dir = Path(settings_log_dir)
            else:
                msg = "Log directory not specified via --log-dir or in application settings."
                click.secho(f"Error: {msg}", fg="red")
                logger.error(f"Cannot clean logs: {msg}")
                raise click.Abort()

        logger.debug(f"Cleaning up log files in '{final_log_dir}'...")
        click.echo(f"Targeting log directory: {final_log_dir}")

        deleted_count = _cleanup_log_files(final_log_dir)
        if deleted_count > 0:
            msg = f"Cleaned up {deleted_count} log file(s) from '{final_log_dir}'."
            click.secho(f"Success: {msg}", fg="green")
            logger.info(msg)
            cleaned_something = True
        else:
            msg = f"No log files found to clean in '{final_log_dir}'."
            click.secho(f"Info: {msg}", fg="cyan")
            logger.info(msg)

    if cleaned_something:
        logger.info("CLI: Cleanup operations finished successfully.")
    else:
        logger.info("CLI: Cleanup operations finished, nothing was cleaned.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cleanup()
