# bedrock-server-manager/bedrock_server_manager/core/server/addon.py
import os
import glob
import shutil
import zipfile
import tempfile
import json
import logging
from bedrock_server_manager.core.server import world
from bedrock_server_manager.core.error import (
    MissingArgumentError,
    FileOperationError,
    InvalidAddonPackTypeError,
    InvalidServerNameError,
    DownloadExtractError,
    DirectoryError,
)
from bedrock_server_manager.core.server import server

logger = logging.getLogger("bedrock_server_manager")


def process_addon(addon_file, server_name, base_dir):
    """Processes the selected addon file (.mcaddon or .mcpack).

    Args:
        addon_file (str): Path to the addon file.
        server_name (str): The name of the server.
        base_dir (str): Base directory.

    Raises:
        MissingArgumentError: If addon_file or server_name is empty.
        FileOperationError: If addon_file does not exist.
        InvalidAddonPackTypeError: If the addon file type is unsupported.
        # Other exceptions might be raised by process_mcaddon or process_mcpack
    """
    if not addon_file:
        raise MissingArgumentError("process_addon: addon_file is empty.")
    if not server_name:
        raise InvalidServerNameError("process_addon: server_name is empty.")
    if not os.path.exists(addon_file):
        raise FileOperationError(
            f"process_addon: addon_file does not exist: {addon_file}"
        )

    if addon_file.lower().endswith(".mcaddon"):
        process_mcaddon(addon_file, server_name, base_dir)  # Let it raise exceptions
    elif addon_file.lower().endswith(".mcpack"):
        process_mcpack(addon_file, server_name, base_dir)  # Let it raise exceptions
    else:
        raise InvalidAddonPackTypeError(f"Unsupported addon file type: {addon_file}")


def process_mcaddon(addon_file, server_name, base_dir):
    """Processes an .mcaddon file (extracts and handles contained files).

    Args:
        addon_file (str): Path to the .mcaddon file.
        server_name (str): The name of the server.
        base_dir (str): Base directory.

    Raises:
        MissingArgumentError: If addon_file or server_name is empty.
        InvalidServerNameError: If server_name is invalid
        FileOperationError: If addon_file doesn't exist or extraction fails.
        DownloadExtractError: If addon_file is not a zip file
        # Other exceptions might be raised by _process_mcaddon_files
    """
    if not addon_file:
        raise MissingArgumentError("process_mcaddon: addon_file is empty.")
    if not server_name:
        raise InvalidServerNameError("process_mcaddon: server_name is empty.")
    if not os.path.exists(addon_file):
        raise FileOperationError(
            f"process_mcaddon: addon_file does not exist: {addon_file}"
        )

    temp_dir = tempfile.mkdtemp()
    logger.debug(f"Extracting {os.path.basename(addon_file)} to {temp_dir}...")

    try:
        with zipfile.ZipFile(addon_file, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(temp_dir)
        raise DownloadExtractError(
            f"Failed to unzip .mcaddon file: {addon_file} (Not a valid zip file)"
        ) from None
    except OSError as e:
        shutil.rmtree(temp_dir)
        raise FileOperationError(f"Failed to unzip .mcaddon file: {e}") from e

    try:
        _process_mcaddon_files(
            temp_dir, server_name, base_dir
        )  # Let it raise exceptions
    finally:
        shutil.rmtree(temp_dir)


def _process_mcaddon_files(temp_dir, server_name, base_dir):
    """Processes the files extracted from an .mcaddon file.

    Args:
        temp_dir (str): Path to the temporary directory.
        server_name (str): The name of the server.
        base_dir (str): Base directory.

    Raises:
        MissingArgumentError: If temp_dir or server_name is empty.
        DirectoryError: If temp_dir is not a directory.
        InvalidServerNameError: If server_name is invalid.
        FileOperationError: If world name cannot be found.
        # Other exceptions may be raised by world.extract_world or process_mcpack
    """

    if not temp_dir:
        raise MissingArgumentError("_process_mcaddon_files: temp_dir is empty.")
    if not server_name:
        raise InvalidServerNameError("_process_mcaddon_files: server_name is empty.")
    if not os.path.isdir(temp_dir):
        raise DirectoryError(
            f"_process_mcaddon_files: temp_dir does not exist or is not a directory: {temp_dir}"
        )

    # Process .mcworld files
    for world_file in glob.glob(os.path.join(temp_dir, "*.mcworld")):
        logger.debug(f"Processing .mcworld file: {os.path.basename(world_file)}")
        try:
            world_name = server.get_world_name(server_name, base_dir)
            if world_name is None or not world_name:
                raise FileOperationError(
                    "Failed to determine world name. Can not install world."
                )
            extract_dir = os.path.join(base_dir, server_name, "worlds", world_name)
            world.extract_world(
                world_file, extract_dir
            )  # Use core function and let it raise exceptions
        except Exception as e:
            raise FileOperationError(
                f"Failed to extract world {world_file}: {e}"
            ) from e

    # Process .mcpack files
    for pack_file in glob.glob(os.path.join(temp_dir, "*.mcpack")):
        logger.debug(f"Processing .mcpack file: {os.path.basename(pack_file)}")
        process_mcpack(pack_file, server_name, base_dir)  # Let it raise exceptions


def process_mcpack(pack_file, server_name, base_dir):
    """Processes an .mcpack file (extracts and processes manifest).

    Args:
        pack_file (str): Path to the .mcpack file.
        server_name (str): The name of the server.
        base_dir (str): Base directory.

    Raises:
        MissingArgumentError: If pack_file or server_name is empty.
        InvalidServerNameError: If server name is invalid.
        FileOperationError: If pack_file doesn't exist or extraction fails.
        DownloadExtractError: If pack_file is not a zip file
        # Other exceptions might be raised by _process_manifest
    """
    if not pack_file:
        raise MissingArgumentError("process_mcpack: pack_file is empty.")
    if not server_name:
        raise InvalidServerNameError("process_mcpack: server_name is empty.")
    if not os.path.exists(pack_file):
        raise FileOperationError(
            f"process_mcpack: pack_file does not exist: {pack_file}"
        )

    temp_dir = tempfile.mkdtemp()
    logger.debug(f"Extracting {os.path.basename(pack_file)} to {temp_dir}...")

    try:
        with zipfile.ZipFile(pack_file, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(temp_dir)
        raise DownloadExtractError(
            f"Failed to unzip .mcpack file: {pack_file} (Not a valid zip file)"
        ) from None
    except OSError as e:
        shutil.rmtree(temp_dir)
        raise FileOperationError(f"Failed to unzip .mcpack file: {e}") from e

    try:
        _process_manifest(temp_dir, server_name, pack_file, base_dir)
    finally:
        shutil.rmtree(temp_dir)


def _process_manifest(temp_dir, server_name, pack_file, base_dir):
    """Processes the manifest.json file within an extracted .mcpack.

    Args:
        temp_dir (str): Path to the temporary directory.
        server_name (str): The name of the server.
        pack_file (str): Original path to the .mcpack file (for logging).
        base_dir (str): Base directory.

    Raises:
        MissingArgumentError: If temp_dir, server_name, or pack_file is empty.
        InvalidServerNameError: if server_name is invalid.
        FileOperationError: If manifest info is missing.
        # Other exceptions may be raised by _extract_manifest_info or install_pack
    """
    if not temp_dir:
        raise MissingArgumentError("process_manifest: temp_dir is empty.")
    if not server_name:
        raise InvalidServerNameError("process_manifest: server_name is empty.")
    if not pack_file:
        raise MissingArgumentError("process_manifest: pack_file is empty.")

    manifest_info = _extract_manifest_info(temp_dir)
    if manifest_info is None:
        raise FileOperationError(
            f"Failed to process {os.path.basename(pack_file)} due to missing or invalid manifest.json"
        )

    pack_type, uuid, version, addon_name_from_manifest = manifest_info

    install_pack(
        pack_type,
        temp_dir,
        server_name,
        pack_file,
        base_dir,
        uuid,
        version,
        addon_name_from_manifest,
    )


def _extract_manifest_info(temp_dir):
    """Extracts information from manifest.json.

    Args:
        temp_dir (str): Path to the temporary directory.

    Returns:
        tuple: (pack_type, uuid, version, addon_name_from_manifest)

    Raises:
        MissingArgumentError: If temp_dir is empty.
        FileOperationError: If manifest.json is missing, invalid, or data is missing.
    """
    manifest_file = os.path.join(temp_dir, "manifest.json")

    if not temp_dir:
        raise MissingArgumentError("_extract_manifest_info: temp_dir is empty.")
    if not os.path.exists(manifest_file):
        raise FileOperationError(f"manifest.json not found in {temp_dir}")

    try:
        with open(manifest_file, "r") as f:
            manifest_data = json.load(f)

        pack_type = manifest_data["modules"][0]["type"]
        uuid = manifest_data["header"]["uuid"]
        version = manifest_data["header"]["version"]
        addon_name_from_manifest = manifest_data["header"]["name"]

        return pack_type, uuid, version, addon_name_from_manifest
    except (OSError, json.JSONDecodeError, KeyError, IndexError) as e:
        raise FileOperationError(
            f"Failed to extract info from manifest.json: {e}"
        ) from e


def install_pack(
    pack_type,
    temp_dir,
    server_name,
    pack_file,
    base_dir,
    uuid,
    version,
    addon_name_from_manifest,
):
    """Installs a pack based on its type (data/resources).

    Args:
        pack_type (str): "data" or "resources".
        temp_dir (str): Path to the temporary directory.
        server_name (str): The name of the server.
        pack_file (str): Original path to the .mcpack file (for logging).
        base_dir (str): The base directory for servers.
        uuid (str): The UUID from the manifest.
        version (list): The version array from the manifest.
        addon_name_from_manifest (str): The addon name from the manifest.

    Raises:
        MissingArgumentError: If required arguments are empty/missing.
        InvalidServerNameError: If the server name is invalid
        FileOperationError: If world name is invalid or file operations fail
        InvalidAddonPackTypeError: If the pack_type is invalid.
    """
    if not pack_type:
        raise MissingArgumentError("install_pack: type is empty.")
    if not temp_dir:
        raise MissingArgumentError("install_pack: temp_dir is empty.")
    if not server_name:
        raise InvalidServerNameError("install_pack: server_name is empty.")
    if not pack_file:
        raise MissingArgumentError("install_pack: pack_file is empty.")

    try:
        world_name = server.get_world_name(server_name, base_dir)
        if not world_name:
            raise FileOperationError("Could not find level-name in server.properties")
    except Exception as e:
        raise FileOperationError(f"Error getting world name: {e}") from e

    behavior_dir = os.path.join(
        base_dir, server_name, "worlds", world_name, "behavior_packs"
    )
    resource_dir = os.path.join(
        base_dir, server_name, "worlds", world_name, "resource_packs"
    )
    behavior_json = os.path.join(
        base_dir, server_name, "worlds", world_name, "world_behavior_packs.json"
    )
    resource_json = os.path.join(
        base_dir, server_name, "worlds", world_name, "world_resource_packs.json"
    )

    # Create directories if they don't exist
    os.makedirs(behavior_dir, exist_ok=True)
    os.makedirs(resource_dir, exist_ok=True)

    if pack_type == "data":
        logger.info(f"Installing behavior pack to {server_name}")
        addon_behavior_dir = os.path.join(
            behavior_dir, f"{addon_name_from_manifest}_{'.'.join(map(str, version))}"
        )
        os.makedirs(addon_behavior_dir, exist_ok=True)
        try:
            # Copy all files from temp_dir to addon_behavior_dir
            for item in os.listdir(temp_dir):
                s = os.path.join(temp_dir, item)
                d = os.path.join(addon_behavior_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            _update_pack_json(behavior_json, uuid, version)
            logger.info(f"Installed {os.path.basename(pack_file)} to {server_name}.")
        except OSError as e:
            raise FileOperationError(f"Failed to copy behavior pack files: {e}") from e

    elif pack_type == "resources":
        logger.info(f"Installing resource pack to {server_name}")
        addon_resource_dir = os.path.join(
            resource_dir, f"{addon_name_from_manifest}_{'.'.join(map(str, version))}"
        )
        os.makedirs(addon_resource_dir, exist_ok=True)
        try:
            # Copy all files from temp_dir to addon_resource_dir
            for item in os.listdir(temp_dir):
                s = os.path.join(temp_dir, item)
                d = os.path.join(addon_resource_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            _update_pack_json(resource_json, uuid, version)
            logger.info(f"Installed {os.path.basename(pack_file)} to {server_name}.")
        except OSError as e:
            raise FileOperationError(f"Failed to copy resource pack files: {e}") from e
    else:
        raise InvalidAddonPackTypeError(f"Unknown pack type: {pack_type}")


def _update_pack_json(json_file, pack_id, version):
    """Updates the world_behavior_packs.json or world_resource_packs.json file.

    Args:
        json_file (str): Path to the JSON file.
        pack_id (str): The pack UUID.
        version (list): The pack version as a list (e.g., [1, 2, 3]).
    Raises:
        MissingArgumentError: If json_file, pack_id, or version is empty.
        FileOperationError: If there's an error reading or writing the JSON file.
    """
    logger.debug(f"Updating {os.path.basename(json_file)}.")

    if not json_file:
        raise MissingArgumentError("_update_pack_json: json_file is empty.")
    if not pack_id:
        raise MissingArgumentError("_update_pack_json: pack_id is empty.")
    if not version:
        raise MissingArgumentError("_update_pack_json: version is empty.")

    if not os.path.exists(json_file):
        try:
            with open(json_file, "w") as f:
                json.dump([], f)  # Create empty JSON array
            logger.debug(f"Created empty JSON file: {json_file}")
        except OSError as e:
            raise FileOperationError(
                f"Failed to initialize JSON file: {json_file}: {e}"
            ) from e

    try:
        with open(json_file, "r") as f:
            try:
                packs = json.load(f)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse JSON in {json_file}.  Creating a new file"
                )
                packs = []

        pack_exists = False
        for i, pack in enumerate(packs):
            if pack["pack_id"] == pack_id:
                pack_exists = True
                pack_version = tuple(pack["version"])
                input_version = tuple(version)
                if input_version > pack_version:
                    packs[i] = {"pack_id": pack_id, "version": version}
                    logger.debug(f"Updated existing pack entry in {json_file}")
                break

        if not pack_exists:
            packs.append({"pack_id": pack_id, "version": version})
            logger.debug(f"Added new pack entry to {json_file}")

        with open(json_file, "w") as f:
            json.dump(packs, f, indent=4)

    except (OSError, TypeError) as e:
        raise FileOperationError(f"Failed to update {json_file}: {e}") from e
