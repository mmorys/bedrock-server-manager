# bedrock_server_manager/bedrock_server_manager/cleanup.py
import os
import shutil
import logging
from bedrock_server_manager.core import SCRIPT_DIR
from bedrock_server_manager.config import settings

logger = logging.getLogger("bedrock_server_manager.cleanup")


def cleanup_cache(verbose=False):
    """Removes __pycache__ directories recursively."""
    deleted_count = 0
    for root, dirs, _ in os.walk(SCRIPT_DIR):
        if "__pycache__" in dirs:
            cache_dir = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(cache_dir)
                if verbose:
                    logger.info(f"Deleted: {cache_dir}")
                deleted_count += 1
            except OSError as e:
                logger.error(f"Error deleting {cache_dir}: {e}")  # Log the error
    if verbose:
        logger.info(f"Deleted {deleted_count} __pycache__ directories.")
    return deleted_count


def cleanup_logs(log_dir=settings.LOG_DIR, verbose=False):
    # added feature to clear the logs folder.
    deleted_count = 0
    logger = logging.getLogger("bedrock_server_manager")
    # Get the logger and iterate over a *copy* of its handlers
    for handler in logger.handlers[:]:  # Iterate over a *copy* of the list
        if isinstance(handler, logging.FileHandler):
            try:
                handler.close()  # Close the handler
                logger.removeHandler(handler)  # Remove the handler from the logger
            except Exception as e:
                logger.error(f"Error closing log handler: {e}")  # shouldnt happen

    # *Now* it's safe to delete the files
    try:
        for file in os.listdir(log_dir):
            file_path = os.path.join(log_dir, file)
            try:  # added try/except block
                os.remove(file_path)
                if verbose:
                    logger.info(f"Deleted: {file_path}")
                deleted_count += 1
            except OSError as e:  # Specifically catch OSErrors during file deletion
                logger.error(f"Error deleting {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error deleting files in {log_dir}: {e}")

    if verbose:
        logger.info(f"Deleted {deleted_count} log files.")
    return deleted_count
