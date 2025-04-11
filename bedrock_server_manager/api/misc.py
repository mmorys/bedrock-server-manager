# bedrock-server-manager/api/misc.py
"""
Provides API-level functions for miscellaneous or global operations
not tied to a specific server instance (e.g., pruning downloads).
"""

import logging
from typing import Dict, Optional

# Local imports
from bedrock_server_manager.core.download import downloader
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    FileOperationError,
    DirectoryError,
    ValueError,
    InvalidInputError,
    MissingArgumentError,
)

logger = logging.getLogger("bedrock_server_manager")


def prune_download_cache(
    download_dir: str, keep_count: Optional[int] = None
) -> Dict[str, str]:
    """
    Prunes old downloaded server archives (.zip) in a specified directory.

    Args:
        download_dir: The specific directory containing downloads to prune
                      (e.g., ".../.downloads/stable" or ".../.downloads/preview").
        keep_count: Optional. How many files to keep. If None, uses DOWNLOAD_KEEP setting.

    Returns:
        {"status": "success", "message": str} or {"status": "error", "message": str}

    Raises:
        MissingArgumentError: If `download_dir` is empty.
        ValueError: If `keep_count` or the setting is invalid.
        DirectoryError: If `download_dir` is not a valid directory.
        FileOperationError: If settings are missing or file deletion fails.
    """
    if not download_dir:
        raise MissingArgumentError("Download directory cannot be empty.")

    logger.info(
        f"API: Pruning download cache directory '{download_dir}'. Keep: {keep_count or 'Setting default'}"
    )

    try:
        # Determine keep count
        effective_keep: int
        if keep_count is None:
            keep_setting = settings.get("DOWNLOAD_KEEP", 3)  # Default 3
            try:
                effective_keep = int(keep_setting)
                if effective_keep < 0:
                    raise ValueError("Keep count cannot be negative")
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"Invalid DOWNLOAD_KEEP setting ('{keep_setting}'): {e}"
                ) from e
        else:
            try:
                effective_keep = int(keep_count)
                if effective_keep < 0:
                    raise ValueError("Keep count cannot be negative")
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"Invalid keep_count parameter ('{keep_count}'): {e}"
                ) from e

        # Call core function (raises DirectoryError, FileOperationError)
        downloader.prune_old_downloads(
            download_dir=download_dir, download_keep=effective_keep
        )

        logger.info(f"API: Pruning successful for directory '{download_dir}'.")
        return {
            "status": "success",
            "message": f"Download cache pruned successfully for '{download_dir}'.",
        }

    except (
        ValueError,
        DirectoryError,
        FileOperationError,
        MissingArgumentError,
        InvalidInputError,
    ) as e:
        logger.error(
            f"API: Failed to prune download cache '{download_dir}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to prune downloads: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error pruning download cache '{download_dir}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error pruning downloads: {e}",
        }
