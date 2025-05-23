# bedrock-server-manager/bedrock_server_manager/core/server/addon.py
"""
Manages the processing and installation of Minecraft addons for Bedrock servers.

Handles different addon file types (.mcaddon, .mcpack, .mcworld), extracts
their contents, processes manifests, and installs behavior/resource packs
and worlds into the appropriate server directories. Updates world pack
configuration JSON files accordingly.
"""

import os
import glob
import shutil
import zipfile
import tempfile
import json
import logging
import re
from typing import Tuple, List

# Local imports
from bedrock_server_manager.core.server import server
from bedrock_server_manager.core.server import world
from bedrock_server_manager.error import (
    MissingArgumentError,
    FileOperationError,
    InvalidAddonPackTypeError,
    InvalidServerNameError,
    AddonExtractError,
    DirectoryError,
)

logger = logging.getLogger("bedrock_server_manager")


def process_addon(addon_file: str, server_name: str, base_dir: str) -> None:
    """
    Processes a given addon file (.mcaddon or .mcpack) for a specific server.

    Determines the file type and delegates to the appropriate processing function.

    Args:
        addon_file: The full path to the addon file (.mcaddon or .mcpack).
        server_name: The name of the target server.
        base_dir: The base directory containing all server installations.

    Raises:
        MissingArgumentError: If `addon_file`, `server_name`, or `base_dir` is empty.
        InvalidServerNameError: If the server name is invalid (e.g., contains invalid chars).
                                (Raised indirectly by functions called within).
        FileNotFoundError: If `addon_file` does not exist.
        InvalidAddonPackTypeError: If the `addon_file` extension is not .mcaddon or .mcpack.
        AddonExtractError: If extraction of the addon archive fails (e.g., invalid zip).
                           (Raised by delegated functions).
        FileOperationError: If file/directory operations fail during processing.
                            (Raised by delegated functions).
        DirectoryError: If expected directories are missing or invalid.
                        (Raised by delegated functions).
    """
    if not addon_file:
        raise MissingArgumentError("Addon file path cannot be empty.")
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    logger.info(
        f"Processing addon file '{os.path.basename(addon_file)}' for server '{server_name}'."
    )

    if not os.path.exists(addon_file):
        error_msg = f"Addon file not found at: {addon_file}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    addon_file_lower = addon_file.lower()
    if addon_file_lower.endswith(".mcaddon"):
        logger.debug(f"Detected .mcaddon file type. Delegating to process_mcaddon.")
        process_mcaddon(
            addon_file, server_name, base_dir
        )  # Let it raise specific exceptions
    elif addon_file_lower.endswith(".mcpack"):
        logger.debug(f"Detected .mcpack file type. Delegating to process_mcpack.")
        process_mcpack(
            addon_file, server_name, base_dir
        )  # Let it raise specific exceptions
    else:
        error_msg = f"Unsupported addon file type: '{os.path.basename(addon_file)}'. Only .mcaddon and .mcpack are supported."
        logger.error(error_msg)
        raise InvalidAddonPackTypeError(error_msg)


def process_mcaddon(addon_file: str, server_name: str, base_dir: str) -> None:
    """
    Processes an .mcaddon file by extracting its contents and handling nested packs/worlds.

    An .mcaddon is typically a ZIP archive containing multiple .mcpack and/or .mcworld files.

    Args:
        addon_file: Path to the .mcaddon file.
        server_name: The name of the target server.
        base_dir: The base directory for servers.

    Raises:
        MissingArgumentError: If arguments are empty.
        InvalidServerNameError: If the server name is invalid.
        FileNotFoundError: If `addon_file` does not exist.
        AddonExtractError: If `addon_file` is not a valid ZIP archive.
        FileOperationError: If file/directory operations fail during extraction or processing.
        DirectoryError: If temporary directory processing fails.
    """
    if not addon_file:
        raise MissingArgumentError("mcaddon file path cannot be empty.")
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    logger.info(
        f"Processing .mcaddon: '{os.path.basename(addon_file)}' for server '{server_name}'."
    )

    if not os.path.exists(addon_file):
        raise FileNotFoundError(f"mcaddon file not found: {addon_file}")

    temp_dir = tempfile.mkdtemp(prefix=f"mcaddon_{server_name}_")
    logger.debug(f"Created temporary directory for extraction: {temp_dir}")

    try:
        # Extract the .mcaddon contents
        try:
            logger.info(
                f"Extracting '{os.path.basename(addon_file)}' to temporary directory..."
            )
            with zipfile.ZipFile(addon_file, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
            logger.debug(f"Successfully extracted '{os.path.basename(addon_file)}'.")
        except zipfile.BadZipFile as e:
            logger.error(
                f"Failed to extract '{addon_file}': Invalid or corrupted ZIP file. {e}",
                exc_info=True,
            )
            raise AddonExtractError(
                f"Invalid .mcaddon file (not a zip): {os.path.basename(addon_file)}"
            ) from e
        except OSError as e:
            logger.error(
                f"OS error during extraction of '{addon_file}': {e}", exc_info=True
            )
            raise FileOperationError(
                f"Error extracting '{os.path.basename(addon_file)}': {e}"
            ) from e

        # Process the extracted files (.mcpack, .mcworld)
        _process_extracted_mcaddon_contents(temp_dir, server_name, base_dir)

    finally:
        # Ensure temporary directory is always cleaned up
        if os.path.isdir(temp_dir):
            try:
                logger.debug(f"Cleaning up temporary directory: {temp_dir}")
                shutil.rmtree(temp_dir)
            except OSError as e:
                logger.warning(
                    f"Could not completely remove temporary directory '{temp_dir}': {e}",
                    exc_info=True,
                )


def _process_extracted_mcaddon_contents(
    temp_dir: str, server_name: str, base_dir: str
) -> None:
    """
    Processes files found within an extracted .mcaddon archive (e.g., .mcpack, .mcworld).

    Args:
        temp_dir: Path to the directory containing extracted contents.
        server_name: The name of the target server.
        base_dir: The base directory for servers.

    Raises:
        MissingArgumentError: If arguments are empty.
        InvalidServerNameError: If the server name is invalid.
        DirectoryError: If `temp_dir` is not a valid directory.
        FileOperationError: If processing nested files (worlds/packs) fails.
    """
    if not temp_dir:
        raise MissingArgumentError("Temporary directory path cannot be empty.")
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    if not os.path.isdir(temp_dir):
        raise DirectoryError(
            f"Temporary directory does not exist or is invalid: {temp_dir}"
        )

    logger.debug(f"Processing extracted contents in: {temp_dir}")

    # Process any .mcworld files found
    mcworld_files = glob.glob(os.path.join(temp_dir, "*.mcworld"))
    if mcworld_files:
        logger.info(f"Found {len(mcworld_files)} .mcworld file(s) in .mcaddon.")
        try:
            # Determine the target world directory path ONCE
            world_name = server.get_world_name(
                server_name, base_dir
            )  # Raises FileOperationError if props missing/invalid
            if not world_name:  # Should be caught by get_world_name
                raise FileOperationError(
                    f"Could not determine world name for server '{server_name}'. Cannot install world."
                )
            world_extract_base_dir = os.path.join(base_dir, server_name, "worlds")

            for world_file in mcworld_files:
                world_filename = os.path.basename(world_file)
                logger.info(f"Processing extracted world file: '{world_filename}'")
                # Note: extract_world expects the *target directory* for the world contents,
                # not the base 'worlds' directory.
                target_world_dir = os.path.join(world_extract_base_dir, world_name)
                try:
                    # Use the core world extraction function
                    world.extract_world(
                        world_file, target_world_dir
                    )  # Raises AddonExtractError, FileOperationError
                    logger.info(
                        f"Successfully processed world file '{world_filename}' into '{target_world_dir}'."
                    )
                except Exception as e:  # Catch exceptions from world.extract_world
                    logger.error(
                        f"Failed to process world file '{world_filename}': {e}",
                        exc_info=True,
                    )
                    raise FileOperationError(
                        f"Failed to process world file '{world_filename}': {e}"
                    ) from e

        except FileOperationError as e:  # Catch error from get_world_name
            logger.error(f"Cannot process .mcworld files: {e}", exc_info=True)
            raise  # Re-raise the error

    # Process any .mcpack files found
    mcpack_files = glob.glob(os.path.join(temp_dir, "*.mcpack"))
    if mcpack_files:
        logger.info(f"Found {len(mcpack_files)} .mcpack file(s) in .mcaddon.")
        for pack_file in mcpack_files:
            pack_filename = os.path.basename(pack_file)
            logger.info(f"Processing extracted pack file: '{pack_filename}'")
            try:
                # Delegate to the .mcpack processor
                process_mcpack(pack_file, server_name, base_dir)
            except Exception as e:  # Catch exceptions from process_mcpack
                logger.error(
                    f"Failed to process pack file '{pack_filename}': {e}", exc_info=True
                )
                # Re-raise to signal failure
                raise FileOperationError(
                    f"Failed to process pack file '{pack_filename}': {e}"
                ) from e

    if not mcworld_files and not mcpack_files:
        logger.warning(
            f"No .mcworld or .mcpack files found within the extracted .mcaddon contents in '{temp_dir}'."
        )


def process_mcpack(pack_file: str, server_name: str, base_dir: str) -> None:
    """
    Processes an .mcpack file by extracting it and installing based on its manifest.

    An .mcpack is a ZIP archive containing either a behavior pack or a resource pack.
    Its type is determined by reading the 'manifest.json' file within it.

    Args:
        pack_file: Path to the .mcpack file.
        server_name: The name of the target server.
        base_dir: The base directory for servers.

    Raises:
        MissingArgumentError: If arguments are empty.
        InvalidServerNameError: If the server name is invalid.
        FileNotFoundError: If `pack_file` does not exist.
        AddonExtractError: If `pack_file` is not a valid ZIP archive or manifest is invalid/missing.
        FileOperationError: If file/directory operations fail during extraction or installation.
    """
    if not pack_file:
        raise MissingArgumentError("mcpack file path cannot be empty.")
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    pack_filename = os.path.basename(pack_file)
    logger.info(f"Processing .mcpack: '{pack_filename}' for server '{server_name}'.")

    if not os.path.exists(pack_file):
        raise FileNotFoundError(f"mcpack file not found: {pack_file}")

    temp_dir = tempfile.mkdtemp(prefix=f"mcpack_{server_name}_")
    logger.debug(f"Created temporary directory for extraction: {temp_dir}")

    try:
        # 1. Extract the .mcpack contents
        try:
            logger.info(f"Extracting '{pack_filename}' to temporary directory...")
            with zipfile.ZipFile(pack_file, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
            logger.debug(f"Successfully extracted '{pack_filename}'.")
        except zipfile.BadZipFile as e:
            logger.error(
                f"Failed to extract '{pack_file}': Invalid or corrupted ZIP file. {e}",
                exc_info=True,
            )
            raise AddonExtractError(
                f"Invalid .mcpack file (not a zip): {pack_filename}"
            ) from e
        except OSError as e:
            logger.error(
                f"OS error during extraction of '{pack_file}': {e}", exc_info=True
            )
            raise FileOperationError(f"Error extracting '{pack_filename}': {e}") from e

        # 2. Process the manifest and install the pack
        _process_manifest_and_install(temp_dir, server_name, pack_file, base_dir)

    finally:
        # Ensure temporary directory is always cleaned up
        if os.path.isdir(temp_dir):
            try:
                logger.debug(f"Cleaning up temporary directory: {temp_dir}")
                shutil.rmtree(temp_dir)
            except OSError as e:
                logger.warning(
                    f"Could not completely remove temporary directory '{temp_dir}': {e}",
                    exc_info=True,
                )


def _process_manifest_and_install(
    temp_dir: str, server_name: str, pack_file: str, base_dir: str
) -> None:
    """
    Reads manifest.json from extracted pack, determines type, and installs it.

    Args:
        temp_dir: Path to the directory with extracted pack contents.
        server_name: The name of the target server.
        pack_file: Original path of the .mcpack file (used for logging).
        base_dir: The base directory for servers.

    Raises:
        MissingArgumentError: If arguments are empty.
        InvalidServerNameError: If the server name is invalid.
        AddonExtractError: If manifest.json is missing, invalid, or lacks required info.
        FileOperationError: If installation (copying files, updating JSON) fails.
        InvalidAddonPackTypeError: If manifest specifies an unknown pack type.
    """
    if not temp_dir:
        raise MissingArgumentError("Temporary directory path cannot be empty.")
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not pack_file:
        raise MissingArgumentError("Original pack file path cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    pack_filename = os.path.basename(pack_file)
    logger.debug(
        f"Processing manifest for pack from '{pack_filename}' in '{temp_dir}'."
    )

    try:
        manifest_info = _extract_manifest_info(
            temp_dir
        )  # Raises AddonExtractError if issues
        pack_type, uuid, version, addon_name_from_manifest = manifest_info
        logger.info(
            f"Manifest extracted: Type='{pack_type}', UUID='{uuid}', Version='{version}', Name='{addon_name_from_manifest}'"
        )

        install_pack(  # Raises FileOperationError, InvalidAddonPackTypeError
            pack_type=pack_type,
            extracted_pack_dir=temp_dir,  # Pass the source of extracted files
            server_name=server_name,
            pack_filename=pack_filename,  # Pass original filename for logging
            base_dir=base_dir,
            uuid=uuid,
            version=version,
            addon_name_from_manifest=addon_name_from_manifest,
        )
    except AddonExtractError as e:  # Catch manifest reading errors
        logger.error(
            f"Failed to process manifest for '{pack_filename}': {e}", exc_info=True
        )
        raise  # Re-raise specific error
    except (
        FileOperationError,
        InvalidAddonPackTypeError,
        InvalidServerNameError,
    ) as e:  # Catch installation errors
        logger.error(
            f"Failed to install pack from '{pack_filename}': {e}", exc_info=True
        )
        raise  # Re-raise specific error
    except Exception as e:  # Catch unexpected errors
        logger.error(
            f"Unexpected error processing manifest or installing pack '{pack_filename}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Unexpected error processing pack '{pack_filename}': {e}"
        ) from e


def _extract_manifest_info(extracted_pack_dir: str) -> Tuple[str, str, list, str]:
    """
    Extracts key information (type, uuid, version, name) from manifest.json.

    Args:
        extracted_pack_dir: Path to the directory containing the extracted pack files,
                            including manifest.json.

    Returns:
        A tuple containing: (pack_type, uuid, version_list, addon_name).

    Raises:
        MissingArgumentError: If `extracted_pack_dir` is empty.
        AddonExtractError: If manifest.json is missing, not valid JSON, or lacks
                           required header/module fields (uuid, version, name, type).
    """
    if not extracted_pack_dir:
        raise MissingArgumentError("Extracted pack directory path cannot be empty.")

    manifest_file = os.path.join(extracted_pack_dir, "manifest.json")
    logger.debug(f"Attempting to read manifest file: {manifest_file}")

    if not os.path.isfile(manifest_file):
        logger.error(
            f"Manifest file 'manifest.json' not found in extracted directory: {extracted_pack_dir}"
        )
        raise AddonExtractError(f"Manifest not found in pack: {extracted_pack_dir}")

    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        logger.debug(f"Successfully loaded manifest JSON data.")

        # Validate and extract required fields carefully
        if not isinstance(manifest_data, dict):
            raise AddonExtractError("Manifest content is not a valid JSON object.")

        header = manifest_data.get("header")
        if not isinstance(header, dict):
            raise AddonExtractError("Manifest missing or invalid 'header' object.")

        uuid = header.get("uuid")
        version = header.get("version")  # Should be a list [major, minor, patch]
        addon_name = header.get("name")

        modules = manifest_data.get("modules")
        if not isinstance(modules, list) or not modules:
            raise AddonExtractError("Manifest missing or invalid 'modules' array.")

        # Assuming the type is defined in the first module
        first_module = modules[0]
        if not isinstance(first_module, dict):
            raise AddonExtractError(
                "First item in 'modules' array is not a valid object."
            )
        pack_type = first_module.get("type")

        # Check if all required fields were found and have basic validity
        if not all(
            [
                uuid,
                isinstance(uuid, str),
                version,
                isinstance(version, list),
                len(version) == 3,
                addon_name,
                isinstance(addon_name, str),
                pack_type,
                isinstance(pack_type, str),
            ]
        ):
            missing = [
                field
                for field, value in [
                    ("uuid", uuid),
                    ("version", version),
                    ("name", addon_name),
                    ("type", pack_type),
                ]
                if not value or not isinstance(value, (str, list))  # Basic check
            ]
            logger.error(
                f"Manifest file '{manifest_file}' is missing required fields or has invalid types: {missing}"
            )
            raise AddonExtractError(
                f"Invalid manifest structure in {manifest_file}. Missing fields: {missing}"
            )

        # Clean/validate pack_type (e.g., lower case)
        pack_type = pack_type.lower()
        if pack_type not in ("data", "resources"):
            logger.warning(f"Uncommon pack type found in manifest: '{pack_type}'.")
            raise InvalidAddonPackTypeError(
                f"Uncommon pack type found in manifest: '{pack_type}'. Proceeding, but may cause issues."
            )

        logger.debug(
            f"Extracted manifest details: Type='{pack_type}', UUID='{uuid}', Version='{version}', Name='{addon_name}'"
        )
        return pack_type, uuid, version, addon_name

    except json.JSONDecodeError as e:
        logger.error(
            f"Failed to parse manifest file '{manifest_file}' (Invalid JSON): {e}",
            exc_info=True,
        )
        raise AddonExtractError(f"Invalid JSON in manifest: {manifest_file}") from e
    except OSError as e:
        logger.error(
            f"Failed to read manifest file '{manifest_file}': {e}", exc_info=True
        )
        raise AddonExtractError(f"Cannot read manifest file: {manifest_file}") from e
    except KeyError as e:
        logger.error(
            f"Manifest file '{manifest_file}' is missing expected key: {e}",
            exc_info=True,
        )
        raise AddonExtractError(
            f"Missing key '{e}' in manifest: {manifest_file}"
        ) from e


def install_pack(
    pack_type: str,
    extracted_pack_dir: str,
    server_name: str,
    pack_filename: str,
    base_dir: str,
    uuid: str,
    version: List[int],
    addon_name_from_manifest: str,
) -> None:
    """
    Installs an extracted pack (behavior or resource) into the server's world directory.

    Copies files from the temporary extraction directory to the appropriate
    behavior_packs or resource_packs folder within the world, and updates the
    corresponding world JSON file (world_behavior_packs.json or world_resource_packs.json).

    Args:
        pack_type: The type of pack ('data' for behavior, 'resources' for resource).
        extracted_pack_dir: The temporary directory containing the extracted pack files.
        server_name: The name of the target server.
        pack_filename: The original filename of the .mcpack (for logging).
        base_dir: The base directory containing all server installations.
        uuid: The pack's UUID from its manifest.
        version: The pack's version list (e.g., [1, 0, 0]) from its manifest.
        addon_name_from_manifest: The pack's name from its manifest.

    Raises:
        MissingArgumentError: If required arguments are empty.
        InvalidServerNameError: If the server name is invalid.
        FileOperationError: If determining the world name fails, or if copying files
                            or updating the world pack JSON fails.
        InvalidAddonPackTypeError: If `pack_type` is not 'data' or 'resources'.
    """
    # Validate essential arguments
    if not pack_type:
        raise MissingArgumentError("Pack type cannot be empty.")
    if not extracted_pack_dir:
        raise MissingArgumentError("Extracted pack directory cannot be empty.")
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not pack_filename:
        raise MissingArgumentError("Pack filename cannot be empty (for logging).")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")
    if not uuid:
        raise MissingArgumentError("Pack UUID cannot be empty.")
    if not version or not isinstance(version, list):
        raise MissingArgumentError("Pack version (list) cannot be empty.")
    if not addon_name_from_manifest:
        raise MissingArgumentError("Addon name from manifest cannot be empty.")

    logger.debug(
        f"Preparing to install pack '{addon_name_from_manifest}' (Type: {pack_type}, UUID: {uuid}) from '{pack_filename}' into server '{server_name}'."
    )

    # 1. Determine world name and paths
    try:
        world_name = server.get_world_name(
            server_name, base_dir
        )  # Raises FileOperationError
        if not world_name:  # Should be caught by get_world_name
            raise FileOperationError(
                f"Could not determine world name for server '{server_name}'."
            )
        logger.debug(f"Target world name determined: '{world_name}'.")

        world_dir = os.path.join(base_dir, server_name, "worlds", world_name)
        behavior_packs_base_dir = os.path.join(world_dir, "behavior_packs")
        resource_packs_base_dir = os.path.join(world_dir, "resource_packs")
        behavior_json_path = os.path.join(world_dir, "world_behavior_packs.json")
        resource_json_path = os.path.join(world_dir, "world_resource_packs.json")

        # Ensure base pack directories exist within the world
        os.makedirs(behavior_packs_base_dir, exist_ok=True)
        os.makedirs(resource_packs_base_dir, exist_ok=True)

    except FileOperationError as e:
        logger.error(
            f"Failed to determine world name or paths for server '{server_name}': {e}",
            exc_info=True,
        )
        raise  # Re-raise error related to getting world info
    except OSError as e:
        logger.error(
            f"Failed to create base pack directories in world '{world_name}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to create pack directories in world '{world_name}': {e}"
        ) from e

    # 2. Determine target installation directory and JSON file based on pack type
    # Create a version string for the directory name, e.g., "1.0.0"
    version_str = ".".join(map(str, version))
    # Sanitize addon name for directory usage (replace invalid chars) - basic example
    safe_addon_name = re.sub(r'[<>:"/\\|?*]', "_", addon_name_from_manifest)
    target_addon_dir_name = f"{safe_addon_name}_{version_str}"

    if pack_type == "data":
        target_install_dir = os.path.join(
            behavior_packs_base_dir, target_addon_dir_name
        )
        target_json_file = behavior_json_path
        pack_type_friendly = "behavior"
    elif pack_type == "resources":
        target_install_dir = os.path.join(
            resource_packs_base_dir, target_addon_dir_name
        )
        target_json_file = resource_json_path
        pack_type_friendly = "resource"
    else:
        logger.error(f"Unknown pack type specified for installation: '{pack_type}'")
        raise InvalidAddonPackTypeError(
            f"Cannot install unknown pack type: '{pack_type}'"
        )

    logger.info(
        f"Installing {pack_type_friendly} pack '{addon_name_from_manifest}' v{version_str} into: {target_install_dir}"
    )

    # 3. Copy extracted files to target directory
    try:
        # Remove existing target directory first to ensure clean install/update
        if os.path.isdir(target_install_dir):
            logger.debug(f"Removing existing target directory: {target_install_dir}")
            shutil.rmtree(target_install_dir)

        # Copy contents using copytree
        shutil.copytree(
            extracted_pack_dir, target_install_dir, dirs_exist_ok=False
        )  # Ensure target doesn't exist before copy
        logger.debug(
            f"Successfully copied pack contents from '{extracted_pack_dir}' to '{target_install_dir}'."
        )

    except OSError as e:
        logger.error(
            f"Failed to copy {pack_type_friendly} pack files to '{target_install_dir}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Failed to copy {pack_type_friendly} pack files: {e}"
        ) from e

    # 4. Update the corresponding world JSON file
    try:
        _update_world_pack_json(target_json_file, uuid, version)
        logger.info(
            f"Successfully installed and activated {pack_type_friendly} pack '{addon_name_from_manifest}' v{version_str} for server '{server_name}'."
        )
    except (MissingArgumentError, FileOperationError) as e:
        logger.error(
            f"Pack files copied, but failed to update world JSON '{target_json_file}': {e}",
            exc_info=True,
        )
        # Raise the error, as activation failed
        raise FileOperationError(
            f"Failed to update world activation JSON '{os.path.basename(target_json_file)}': {e}"
        ) from e


def _update_world_pack_json(
    json_file_path: str, pack_uuid: str, pack_version: List[int]
) -> None:
    """
    Updates a world's pack list JSON file (behavior or resource) with a pack entry.

    Adds the pack if it doesn't exist or updates the version if a newer one is provided.

    Args:
        json_file_path: Full path to the world_behavior_packs.json or world_resource_packs.json.
        pack_uuid: The UUID of the pack to add/update.
        pack_version: The version list (e.g., [1, 0, 0]) of the pack.

    Raises:
        MissingArgumentError: If arguments are empty.
        FileOperationError: If reading/writing the JSON file fails or JSON is invalid.
    """
    if not json_file_path:
        raise MissingArgumentError("JSON file path cannot be empty.")
    if not pack_uuid:
        raise MissingArgumentError("Pack UUID cannot be empty.")
    if not pack_version or not isinstance(pack_version, list):
        raise MissingArgumentError("Pack version (list) cannot be empty.")

    json_filename = os.path.basename(json_file_path)
    logger.debug(
        f"Updating world pack JSON file: '{json_filename}' with UUID: {pack_uuid}, Version: {pack_version}"
    )

    packs = []
    # 1. Load existing JSON data, handling file not found or invalid JSON
    try:
        if os.path.exists(json_file_path):
            with open(json_file_path, "r", encoding="utf-8") as f:
                try:
                    content = f.read()
                    # Handle empty file case
                    if not content.strip():
                        logger.debug(
                            f"JSON file '{json_filename}' is empty. Initializing as empty list."
                        )
                        packs = []
                    else:
                        packs = json.loads(content)
                        # Basic validation: should be a list
                        if not isinstance(packs, list):
                            logger.warning(
                                f"JSON file '{json_filename}' does not contain a list. Overwriting with new structure."
                            )
                            packs = []
                        else:
                            logger.debug(
                                f"Loaded {len(packs)} existing pack entries from '{json_filename}'."
                            )
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Failed to parse JSON in '{json_filename}'. File will be overwritten. Error: {e}",
                        exc_info=True,
                    )
                    packs = []  # Reset to empty list if parsing fails
        else:
            logger.debug(
                f"JSON file '{json_filename}' not found. Will create new file with the pack entry."
            )
            packs = []  # Initialize empty list

    except OSError as e:
        logger.error(f"Failed to read JSON file '{json_filename}': {e}", exc_info=True)
        raise FileOperationError(
            f"Failed to read world pack JSON: {json_filename}"
        ) from e

    # 2. Update or add the pack entry
    pack_found = False
    input_version_tuple = tuple(pack_version)  # Convert list to tuple for comparison

    for i, existing_pack in enumerate(packs):
        # Ensure existing entry is valid before accessing keys
        if isinstance(existing_pack, dict) and "pack_id" in existing_pack:
            if existing_pack["pack_id"] == pack_uuid:
                pack_found = True
                # Compare versions if existing entry has a valid version list
                existing_version = existing_pack.get("version")
                if isinstance(existing_version, list):
                    existing_version_tuple = tuple(existing_version)
                    if (
                        input_version_tuple >= existing_version_tuple
                    ):  # Update if same or newer
                        if input_version_tuple > existing_version_tuple:
                            logger.info(
                                f"Updating existing pack '{pack_uuid}' in '{json_filename}' from version {existing_version} to {pack_version}."
                            )
                        else:
                            logger.debug(
                                f"Pack '{pack_uuid}' version {pack_version} already exists in '{json_filename}'. Ensuring entry is correct."
                            )
                        packs[i] = {"pack_id": pack_uuid, "version": pack_version}
                    else:
                        # Input version is older, don't downgrade
                        logger.warning(
                            f"Skipping update for pack '{pack_uuid}' in '{json_filename}'. Existing version {existing_version} is newer than input {pack_version}."
                        )
                else:
                    # Existing entry has invalid version, overwrite it
                    logger.warning(
                        f"Existing entry for pack '{pack_uuid}' in '{json_filename}' has invalid version '{existing_version}'. Overwriting."
                    )
                    packs[i] = {"pack_id": pack_uuid, "version": pack_version}
                break  # Stop searching once found
        else:
            logger.warning(
                f"Skipping invalid entry in '{json_filename}': {existing_pack}"
            )

    if not pack_found:
        logger.info(
            f"Adding new pack entry for UUID '{pack_uuid}', Version: {pack_version} to '{json_filename}'."
        )
        packs.append({"pack_id": pack_uuid, "version": pack_version})

    # 3. Write the updated list back to the JSON file
    try:
        # Ensure parent directory exists (should already, but safeguard)
        os.makedirs(os.path.dirname(json_file_path), exist_ok=True)
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(
                packs, f, indent=4, sort_keys=True
            )  # Use indent and sort for readability
        logger.debug(f"Successfully wrote updated pack list to '{json_filename}'.")
    except OSError as e:
        logger.error(
            f"Failed to write updated JSON to '{json_filename}': {e}", exc_info=True
        )
        raise FileOperationError(
            f"Failed to write world pack JSON: {json_filename}"
        ) from e
