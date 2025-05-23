# bedrock_server_manager/bedrock_server_manager/utils/cleanup.py
"""
Provides utility functions for cleaning up temporary or generated files,
such as Python bytecode cache and log files.
"""

import os
import shutil
import logging
from typing import Optional

# Local imports
from bedrock_server_manager.core import SCRIPT_DIR
from bedrock_server_manager.config.settings import settings

logger = logging.getLogger("bedrock_server_manager")


def cleanup_cache() -> int:
    """
    Removes __pycache__ directories recursively within the project's script directory.

    Assumes SCRIPT_DIR points to the relevant base directory to scan.

    Returns:
        int: The number of __pycache__ directories successfully deleted.
    """
    deleted_count = 0
    logger.debug(f"Starting __pycache__ cleanup within: {SCRIPT_DIR}")
    if not os.path.isdir(SCRIPT_DIR):
        logger.warning(
            f"SCRIPT_DIR '{SCRIPT_DIR}' is not a valid directory. Skipping cache cleanup."
        )
        return 0

    for root, dirs, _ in os.walk(SCRIPT_DIR):
        if "__pycache__" in dirs:
            cache_dir = os.path.join(root, "__pycache__")
            logger.debug(f"Found cache directory: {cache_dir}")
            try:
                shutil.rmtree(cache_dir)
                logger.info(f"Deleted bytecode cache directory: {cache_dir}")
                deleted_count += 1
            except OSError as e:
                logger.error(
                    f"Error deleting cache directory {cache_dir}: {e}", exc_info=True
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error deleting cache directory {cache_dir}: {e}",
                    exc_info=True,
                )

    if deleted_count > 0:
        logger.info(
            f"Successfully deleted {deleted_count} __pycache__ director(y/ies)."
        )
    else:
        logger.debug("No __pycache__ directories found or deleted.")
    return deleted_count


def cleanup_logs(log_dir: Optional[str] = None) -> int:
    """
    Clears log files from the specified directory.

    IMPORTANT: This function first attempts to close and remove all active
    FileHandlers associated with the 'bedrock_server_manager' logger to prevent
    'file in use' errors on Windows and ensure logs are flushed.
    This modifies the logger's state; logging might cease until handlers
    are re-added (e.g., by calling setup_logging again).

    Args:
        log_dir (Optional[str]): The directory containing the log files to delete.
            If None, defaults to the 'LOG_DIR' setting from the application config.

    Returns:
        int: The number of log files successfully deleted.
    """
    deleted_count = 0
    if log_dir is None:
        log_dir = settings.get("LOG_DIR")

    logger.debug(f"Starting log file cleanup for directory: {log_dir}")

    if not log_dir or not isinstance(log_dir, str):
        logger.error(
            f"Invalid log directory provided or configured: {log_dir}. Aborting log cleanup."
        )
        return 0

    if not os.path.isdir(log_dir):
        logger.warning(f"Log directory '{log_dir}' does not exist. Nothing to clean.")
        return 0

    # Close and remove file handlers associated *specifically* with this logger
    # Note: This doesn't affect handlers from other loggers (e.g., root logger)
    # that might be writing to the same directory.
    app_logger = logging.getLogger(
        "bedrock_server_manager"
    )  # Ensure we target the correct logger
    logger.debug(
        f"Closing and removing file handlers for logger '{app_logger.name}'..."
    )
    handlers_to_remove = [
        h for h in app_logger.handlers if isinstance(h, logging.FileHandler)
    ]

    for handler in handlers_to_remove:
        handler_name = getattr(handler, "baseFilename", str(handler))
        logger.debug(f"Processing handler: {handler_name}")
        try:
            handler.flush()  # Attempt to flush buffer before closing
            handler.close()  # Close the file stream
            app_logger.removeHandler(handler)  # Remove from the logger instance
            logger.debug(f"Closed and removed handler: {handler_name}")
        except Exception as e:
            # This is generally unexpected if the handler was properly added.
            logger.error(
                f"Error closing/removing log handler '{handler_name}': {e}",
                exc_info=True,
            )

    # Now, attempt to delete files within the directory
    logger.info(f"Attempting to delete files within log directory: {log_dir}")
    try:
        # Check again if directory exists, could have been deleted between checks? Unlikely but safe.
        if not os.path.isdir(log_dir):
            logger.warning(
                f"Log directory '{log_dir}' disappeared before file deletion. Skipping."
            )
            return 0

        for item_name in os.listdir(log_dir):
            item_path = os.path.join(log_dir, item_name)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.remove(item_path)
                    logger.info(f"Deleted log file: {item_path}")
                    deleted_count += 1
                elif os.path.isdir(item_path):
                    logger.debug(
                        f"Skipping subdirectory found in log directory: {item_path}"
                    )
                else:
                    logger.debug(
                        f"Skipping non-file item in log directory: {item_path}"
                    )

            except OSError as e:
                logger.error(f"Error deleting log file {item_path}: {e}", exc_info=True)
            except Exception as e:
                logger.error(
                    f"Unexpected error deleting item {item_path}: {e}", exc_info=True
                )

    except FileNotFoundError:
        logger.warning(
            f"Log directory '{log_dir}' not found when trying to list files. Maybe deleted concurrently?"
        )
    except OSError as e:
        logger.error(
            f"Error accessing or listing files in log directory {log_dir}: {e}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"Unexpected error processing log directory {log_dir}: {e}", exc_info=True
        )

    if deleted_count > 0:
        logger.info(f"Successfully deleted {deleted_count} log file(s) from {log_dir}.")
    else:
        logger.debug(f"No log files were deleted from {log_dir}.")

    return deleted_count
