# bedrock_server_manager/api/misc.py
"""Provides API functions for miscellaneous or global operations.

This module contains functions that are not tied to a specific server
instance, such as managing the global download cache for server executables.
Operations are designed to be thread-safe.
"""

import logging
import threading
from typing import Dict, Optional

# Plugin system imports to bridge API functionality.
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
from bedrock_server_manager.core import downloader
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    BSMError,
    UserInputError,
    MissingArgumentError,
)

logger = logging.getLogger(__name__)

# A lock to prevent race conditions during miscellaneous file operations.
_misc_lock = threading.Lock()


@plugin_method("prune_download_cache")
def prune_download_cache(
    download_dir: str, keep_count: Optional[int] = None
) -> Dict[str, str]:
    """Prunes old downloaded server archives (.zip) in a directory.

    This function removes older server archive files from the specified
    download directory, keeping a specified number of the most recent files.
    The operation is thread-safe to prevent concurrent modifications.

    Args:
        download_dir: The path to the directory containing the downloaded
            server archives.
        keep_count: The number of recent archives to keep. If None, the
            value from the `DOWNLOAD_KEEP` setting is used. Defaults to None.

    Returns:
        A dictionary containing the status of the operation ('success', 'error',
        or 'skipped') and a descriptive message.

    Raises:
        MissingArgumentError: If `download_dir` is not provided.
        UserInputError: If `keep_count` or the `DOWNLOAD_KEEP` setting is
            not a valid non-negative integer.
    """
    # Attempt to acquire the lock without blocking. If another operation
    # is in progress, skip this one to avoid conflicts.
    if not _misc_lock.acquire(blocking=False):
        logger.warning(
            "A miscellaneous file operation is already in progress. Skipping concurrent prune."
        )
        return {
            "status": "skipped",
            "message": "A file operation is already in progress.",
        }

    result = {}
    try:
        if not download_dir:
            raise MissingArgumentError("Download directory cannot be empty.")

        effective_keep: int
        try:
            # Determine the number of files to keep, prioritizing the function
            # argument over the global setting.
            if keep_count is None:
                keep_setting = settings.get("DOWNLOAD_KEEP", 3)
                effective_keep = int(keep_setting)
            else:
                effective_keep = int(keep_count)

            if effective_keep < 0:
                raise ValueError("Keep count cannot be negative")

        except (TypeError, ValueError) as e:
            # Catch errors from invalid settings or user input.
            raise UserInputError(
                f"Invalid keep_count or DOWNLOAD_KEEP setting: {e}"
            ) from e

        # --- Plugin Hook: Before Prune ---
        plugin_manager.trigger_event(
            "before_prune_download_cache",
            download_dir=download_dir,
            keep_count=effective_keep,
        )
        logger.info(
            f"API: Pruning download cache directory '{download_dir}'. Keep: {effective_keep}"
        )

        try:
            # Delegate the actual file deletion to the core downloader module.
            downloader.prune_old_downloads(
                download_dir=download_dir, download_keep=effective_keep
            )

            logger.info(f"API: Pruning successful for directory '{download_dir}'.")
            result = {
                "status": "success",
                "message": f"Download cache pruned successfully for '{download_dir}'.",
            }

        except BSMError as e:
            # Handle application-specific errors during pruning.
            logger.error(
                f"API: Failed to prune download cache '{download_dir}': {e}",
                exc_info=True,
            )
            result = {"status": "error", "message": f"Failed to prune downloads: {e}"}
        except Exception as e:
            # Handle any other unexpected errors.
            logger.error(
                f"API: Unexpected error pruning download cache '{download_dir}': {e}",
                exc_info=True,
            )
            result = {
                "status": "error",
                "message": f"Unexpected error pruning downloads: {e}",
            }

        finally:
            # --- Plugin Hook: After Prune ---
            # This hook runs regardless of whether the prune succeeded or failed.
            plugin_manager.trigger_event("after_prune_download_cache", result=result)

    except UserInputError as e:
        # Handle the validation error for keep_count from the outer try block.
        result = {"status": "error", "message": str(e)}
        # Trigger the 'after' hook even on input validation failure.
        plugin_manager.trigger_event("after_prune_download_cache", result=result)

    finally:
        # Ensure the lock is always released, even if errors occur.
        _misc_lock.release()

    return result
