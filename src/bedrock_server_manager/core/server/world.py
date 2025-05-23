# bedrock-server-manager/bedrock_server_manager/core/server/world.py
"""
Handles operations related to Minecraft Bedrock worlds, specifically
extracting worlds from .mcworld archives and exporting world directories
into .mcworld archives.
"""

import os
import shutil
import zipfile
import logging

# Local imports
from bedrock_server_manager.error import (
    MissingArgumentError,
    DownloadExtractError,
    FileOperationError,
    BackupWorldError,
    DirectoryError,
    RestoreError,
    InvalidServerNameError,
)
from bedrock_server_manager.core.server import server

logger = logging.getLogger("bedrock_server_manager")


def extract_world(mcworld_file_path: str, target_extract_dir: str) -> None:
    """
    Extracts the contents of a .mcworld file to a specified directory.

    Deletes the target directory first if it already exists to ensure a clean extraction.

    Args:
        mcworld_file_path: The full path to the source .mcworld file.
        target_extract_dir: The full path to the directory where the world
                            contents should be extracted.

    Raises:
        MissingArgumentError: If `mcworld_file_path` or `target_extract_dir` is empty.
        FileNotFoundError: If `mcworld_file_path` does not exist.
        DownloadExtractError: If `mcworld_file_path` is not a valid ZIP file (.mcworld are zip).
        FileOperationError: If removing the existing target directory fails, or if
                            unzipping the world file fails due to OS errors.
    """
    if not mcworld_file_path:
        raise MissingArgumentError("Path to the .mcworld file cannot be empty.")
    if not target_extract_dir:
        raise MissingArgumentError("Target extraction directory cannot be empty.")

    mcworld_filename = os.path.basename(mcworld_file_path)
    logger.info(
        f"Preparing to extract world from '{mcworld_filename}' into '{target_extract_dir}'."
    )

    if not os.path.isfile(mcworld_file_path):
        error_msg = f".mcworld file not found at: {mcworld_file_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    # --- Ensure clean target directory ---
    if os.path.exists(target_extract_dir):
        logger.warning(
            f"Target directory '{target_extract_dir}' already exists. Removing its contents before extraction."
        )
        try:
            shutil.rmtree(target_extract_dir)
            logger.debug(
                f"Successfully removed existing directory: {target_extract_dir}"
            )
        except OSError as e:
            logger.error(
                f"Failed to remove existing target directory '{target_extract_dir}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to clear target directory '{target_extract_dir}': {e}"
            ) from e

    # Recreate the empty target directory
    try:
        os.makedirs(
            target_extract_dir, exist_ok=True
        )  # exist_ok=True is safe here after rmtree
        logger.debug(f"Ensured target directory exists: {target_extract_dir}")
    except OSError as e:
        logger.error(
            f"Failed to create target directory '{target_extract_dir}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to create target directory '{target_extract_dir}': {e}"
        ) from e

    # --- Extract the world archive ---
    logger.info(f"Extracting world archive '{mcworld_filename}'...")
    try:
        with zipfile.ZipFile(mcworld_file_path, "r") as zip_ref:
            zip_ref.extractall(target_extract_dir)
        logger.info(f"Successfully extracted world to '{target_extract_dir}'.")
    except zipfile.BadZipFile as e:
        logger.error(
            f"Failed to extract '{mcworld_filename}': Invalid or corrupted ZIP file format. {e}",
            exc_info=True,
        )
        # Clean up potentially partially created directory
        if os.path.exists(target_extract_dir):
            shutil.rmtree(target_extract_dir)
        raise DownloadExtractError(
            f"Invalid .mcworld file (not a valid zip): {mcworld_filename}"
        ) from e
    except OSError as e:
        logger.error(
            f"OS error during extraction of '{mcworld_filename}' to '{target_extract_dir}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Error extracting world '{mcworld_filename}': {e}"
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error during extraction of '{mcworld_filename}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Unexpected error extracting world '{mcworld_filename}': {e}"
        ) from e


def export_world(world_dir_path: str, target_mcworld_path: str) -> None:
    """
    Exports (archives) a world directory into a .mcworld file (which is a ZIP archive).

    Args:
        world_dir_path: The full path to the source world directory.
        target_mcworld_path: The full path where the resulting .mcworld file should be saved.

    Raises:
        MissingArgumentError: If `world_dir_path` or `target_mcworld_path` is empty.
        DirectoryError: If `world_dir_path` does not exist or is not a directory.
        BackupWorldError: If creating the ZIP archive fails due to OS errors or other `shutil` issues.
        FileOperationError: If creating the parent directory for the target file fails.
    """
    if not world_dir_path:
        raise MissingArgumentError("Source world directory path cannot be empty.")
    if not target_mcworld_path:
        raise MissingArgumentError("Target .mcworld file path cannot be empty.")

    world_dir_name = os.path.basename(world_dir_path)
    mcworld_filename = os.path.basename(target_mcworld_path)
    logger.info(
        f"Exporting world directory '{world_dir_name}' to .mcworld file '{mcworld_filename}'."
    )
    logger.debug(f"Source: {world_dir_path}")
    logger.debug(f"Target: {target_mcworld_path}")

    if not os.path.isdir(world_dir_path):
        error_msg = (
            f"Source world directory not found or is not a directory: {world_dir_path}"
        )
        logger.error(error_msg)
        raise DirectoryError(error_msg)

    # Ensure the directory for the target .mcworld file exists
    target_dir = os.path.dirname(target_mcworld_path)
    if target_dir:  # Avoid trying to create '.' if path has no directory part
        try:
            os.makedirs(target_dir, exist_ok=True)
            logger.debug(f"Ensured target directory exists: {target_dir}")
        except OSError as e:
            logger.error(
                f"Failed to create target directory '{target_dir}' for .mcworld file: {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Cannot create target directory '{target_dir}': {e}"
            ) from e

    # --- Create the archive ---
    # shutil.make_archive expects the base_name *without* the extension for the first arg.
    # It will create base_name.zip initially.
    archive_base_name = os.path.splitext(target_mcworld_path)[0]
    temp_zip_path = archive_base_name + ".zip"

    try:
        logger.debug(f"Creating temporary ZIP archive: {temp_zip_path}")
        # The root_dir makes paths inside the zip relative to world_dir_path
        shutil.make_archive(
            base_name=archive_base_name, format="zip", root_dir=world_dir_path
        )
        logger.debug(f"Successfully created temporary ZIP: {temp_zip_path}")

        # Rename the created .zip to the desired .mcworld extension
        # Check if temp zip exists before renaming
        if not os.path.exists(temp_zip_path):
            raise BackupWorldError(
                f"Archive process completed but temporary zip file '{temp_zip_path}' not found."
            )

        # Remove target if it exists before renaming (os.rename fails on Windows if target exists)
        if os.path.exists(target_mcworld_path):
            logger.warning(
                f"Target file '{target_mcworld_path}' already exists. Overwriting."
            )
            os.remove(target_mcworld_path)

        os.rename(temp_zip_path, target_mcworld_path)
        logger.info(f"World export successful. Created: {target_mcworld_path}")

    except OSError as e:
        logger.error(
            f"Failed to create or rename world archive for '{world_dir_name}': {e}",
            exc_info=True,
        )
        # Clean up temporary zip if rename failed
        if os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except OSError:
                pass
        raise BackupWorldError(f"Failed to create world backup archive: {e}") from e
    except Exception as e:
        logger.error(
            f"Unexpected error during world export for '{world_dir_name}': {e}",
            exc_info=True,
        )
        # Clean up temporary zip if rename failed
        if os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except OSError:
                pass
        raise BackupWorldError(f"Unexpected error exporting world: {e}") from e


def import_world(server_name: str, mcworld_backup_path: str, base_dir: str) -> None:
    """
    Imports (restores) a world from a .mcworld backup file into a server's world directory.

    Determines the correct target world directory based on the server's
    configured 'level-name' in server.properties.

    Args:
        server_name: The name of the target server.
        mcworld_backup_path: The full path to the source .mcworld backup file.
        base_dir: The base directory containing all server installations.

    Raises:
        MissingArgumentError: If required arguments are empty.
        InvalidServerNameError: If `server_name` is invalid.
        FileNotFoundError: If `mcworld_backup_path` does not exist.
        FileOperationError: If the server's world name cannot be determined from
                            server.properties, or if extraction fails due to OS errors.
        DirectoryError: If the target server directory structure is invalid.
        DownloadExtractError: If the .mcworld file is not a valid ZIP archive.
        RestoreError: General wrapper for import failures.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not mcworld_backup_path:
        raise MissingArgumentError(".mcworld backup file path cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    mcworld_filename = os.path.basename(mcworld_backup_path)
    logger.info(
        f"Importing world for server '{server_name}' from backup '{mcworld_filename}'."
    )

    if not os.path.isfile(mcworld_backup_path):
        error_msg = f".mcworld backup file not found: {mcworld_backup_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    # 1. Determine the target world directory
    try:
        # Use the function from the server module to get the world name
        world_name = server.get_world_name(
            server_name, base_dir
        )  # Raises FileOperationError if props missing/invalid or name missing
        logger.info(f"Target world name for server '{server_name}' is '{world_name}'.")
    except FileOperationError as e:
        logger.error(f"Cannot determine target world directory: {e}", exc_info=True)
        raise RestoreError(
            f"Cannot import world: Failed to get world name for server '{server_name}'."
        ) from e
    except Exception as e:  # Catch unexpected errors from get_world_name
        logger.error(
            f"Unexpected error getting world name for server '{server_name}': {e}",
            exc_info=True,
        )
        raise RestoreError(
            f"Unexpected error getting world name for server '{server_name}'."
        ) from e

    # Construct the full path for extraction
    target_world_dir = os.path.join(base_dir, server_name, "worlds", world_name)
    logger.debug(f"Target directory for world extraction: {target_world_dir}")

    # 2. Delegate to the extract_world function
    try:
        # extract_world handles directory cleaning and extraction
        extract_world(
            mcworld_backup_path, target_world_dir
        )  # Raises FileNotFoundError, DownloadExtractError, FileOperationError
        logger.info(f"World import for server '{server_name}' completed successfully.")
    except (FileNotFoundError, DownloadExtractError, FileOperationError) as e:
        logger.error(
            f"World import failed during extraction phase for server '{server_name}': {e}",
            exc_info=True,
        )
        raise RestoreError(
            f"World import failed for server '{server_name}': {e}"
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error during world import extraction for server '{server_name}': {e}",
            exc_info=True,
        )
        raise RestoreError(
            f"Unexpected error during world import for '{server_name}': {e}"
        ) from e
