# bedrock_server_manager/core/server/addon_mixin.py
"""
Provides the ServerAddonMixin class for BedrockServer.

This mixin handles the processing of addon files (.mcaddon, .mcpack),
including extraction, manifest parsing, and installation into the server's
active world directory. It interacts with world and state management mixins.
"""
import os
import glob
import shutil
import zipfile
import tempfile
import json
import re
from typing import Tuple, List

# Local imports
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import (
    MissingArgumentError,
    FileOperationError,
    UserInputError,
    ExtractError,
    AppFileNotFoundError,
    ConfigParseError,
)


class ServerAddonMixin(BedrockServerBaseMixin):
    """
    A mixin for the BedrockServer class that provides methods for managing
    server addons, such as .mcaddon and .mcpack files.

    This includes processing addon archives, extracting their contents,
    reading manifest files, and installing behavior or resource packs
    into the server's active world.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the ServerAddonMixin.

        Calls super().__init__ for proper multiple inheritance setup.
        Relies on attributes (like server_name, server_dir, logger) and methods
        (like get_world_name) being available from other mixins or the base class.
        """
        super().__init__(*args, **kwargs)
        # Attributes from BaseMixin: self.server_name, self.base_dir, self.server_dir, self.logger
        # Methods from other mixins (available on final BedrockServer class):
        # self.get_world_name() (from StateMixin)
        # self.extract_mcworld_to_directory() (from WorldMixin)

    def process_addon_file(self, addon_file_path: str) -> None:
        """
        Processes a given addon file (.mcaddon or .mcpack) for this server.
        Determines file type and delegates to appropriate internal processing.

        Args:
            addon_file_path: Full path to the addon file.
        """
        if not addon_file_path:
            raise MissingArgumentError("Addon file path cannot be empty.")

        self.logger.info(
            f"Server '{self.server_name}': Processing addon file '{os.path.basename(addon_file_path)}'."
        )

        if not os.path.isfile(addon_file_path):
            raise AppFileNotFoundError(addon_file_path, "Addon file")

        addon_file_lower = addon_file_path.lower()
        if addon_file_lower.endswith(".mcaddon"):
            self.logger.debug("Detected .mcaddon file type. Delegating.")
            self._process_mcaddon_archive(addon_file_path)
        elif addon_file_lower.endswith(".mcpack"):
            self.logger.debug("Detected .mcpack file type. Delegating.")
            self._process_mcpack_archive(addon_file_path)
        else:
            err_msg = f"Unsupported addon file type: '{os.path.basename(addon_file_path)}'. Only .mcaddon and .mcpack."
            self.logger.error(err_msg)
            raise UserInputError(err_msg)

    def _process_mcaddon_archive(self, mcaddon_file_path: str) -> None:
        """Processes an .mcaddon file by extracting its contents and handling nested packs/worlds."""
        self.logger.info(
            f"Server '{self.server_name}': Processing .mcaddon '{os.path.basename(mcaddon_file_path)}'."
        )

        temp_dir = tempfile.mkdtemp(prefix=f"mcaddon_{self.server_name}_")
        self.logger.debug(
            f"Created temporary directory for .mcaddon extraction: {temp_dir}"
        )

        try:
            try:
                self.logger.info(
                    f"Extracting '{os.path.basename(mcaddon_file_path)}' to temp dir..."
                )
                with zipfile.ZipFile(mcaddon_file_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
                self.logger.debug(
                    f"Successfully extracted '{os.path.basename(mcaddon_file_path)}'."
                )
            except zipfile.BadZipFile as e:
                self.logger.error(
                    f"Failed to extract '{mcaddon_file_path}': Invalid ZIP. {e}",
                    exc_info=True,
                )
                raise ExtractError(
                    f"Invalid .mcaddon (not zip): {os.path.basename(mcaddon_file_path)}"
                ) from e
            except OSError as e:  # General OS error during zip
                self.logger.error(
                    f"OS error extracting '{mcaddon_file_path}': {e}", exc_info=True
                )
                raise FileOperationError(
                    f"Error extracting '{os.path.basename(mcaddon_file_path)}': {e}"
                ) from e

            self._process_extracted_mcaddon_contents(temp_dir)

        finally:
            if os.path.isdir(temp_dir):
                try:
                    self.logger.debug(f"Cleaning up temp directory: {temp_dir}")
                    shutil.rmtree(temp_dir)
                except OSError as e:
                    self.logger.warning(
                        f"Could not remove temp directory '{temp_dir}': {e}",
                        exc_info=True,
                    )

    def _process_extracted_mcaddon_contents(
        self, temp_dir_with_extracted_files: str
    ) -> None:
        """Processes files found within an extracted .mcaddon archive (e.g., .mcpack, .mcworld)."""

        self.logger.debug(
            f"Server '{self.server_name}': Processing extracted .mcaddon contents in '{temp_dir_with_extracted_files}'."
        )

        # Process .mcworld files (delegates to ServerWorldMixin.extract_mcworld_to_directory via self)
        mcworld_files_found = glob.glob(
            os.path.join(temp_dir_with_extracted_files, "*.mcworld")
        )
        if mcworld_files_found:
            self.logger.info(
                f"Found {len(mcworld_files_found)} .mcworld file(s) in .mcaddon."
            )
            active_world_name = (
                self.get_world_name()
            )  # From StateMixin, raises AppFileNotFoundError/ConfigParseError if fails

            for world_file_path in mcworld_files_found:
                world_filename_basename = os.path.basename(world_file_path)
                self.logger.info(
                    f"Processing extracted world file: '{world_filename_basename}' into active world '{active_world_name}'."
                )
                try:
                    # self.extract_mcworld_to_directory is from ServerWorldMixin
                    # It takes the path to the .mcworld file and the *name* of the target world directory.
                    self.extract_mcworld_to_directory(
                        world_file_path, active_world_name
                    )
                    self.logger.info(
                        f"Successfully processed '{world_filename_basename}' into world '{active_world_name}'."
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to process world file '{world_filename_basename}': {e}",
                        exc_info=True,
                    )
                    raise FileOperationError(
                        f"Failed processing world '{world_filename_basename}' from .mcaddon for server '{self.server_name}': {e}"
                    ) from e

        # Process .mcpack files (delegates to self._process_mcpack_archive)
        mcpack_files_found = glob.glob(
            os.path.join(temp_dir_with_extracted_files, "*.mcpack")
        )
        if mcpack_files_found:
            self.logger.info(
                f"Found {len(mcpack_files_found)} .mcpack file(s) in .mcaddon."
            )
            for pack_file_path in mcpack_files_found:
                pack_filename_basename = os.path.basename(pack_file_path)
                self.logger.info(
                    f"Processing extracted pack file: '{pack_filename_basename}'."
                )
                try:
                    self._process_mcpack_archive(
                        pack_file_path
                    )  # Process it as a standalone .mcpack
                except Exception as e:
                    self.logger.error(
                        f"Failed to process pack file '{pack_filename_basename}': {e}",
                        exc_info=True,
                    )
                    raise FileOperationError(
                        f"Failed processing pack '{pack_filename_basename}' from .mcaddon for server '{self.server_name}': {e}"
                    ) from e

        if not mcworld_files_found and not mcpack_files_found:
            self.logger.warning(
                f"No .mcworld or .mcpack files found in extracted .mcaddon at '{temp_dir_with_extracted_files}'."
            )

    def _process_mcpack_archive(self, mcpack_file_path: str) -> None:
        """Processes an .mcpack file by extracting it and installing based on its manifest."""

        mcpack_filename = os.path.basename(mcpack_file_path)
        self.logger.info(
            f"Server '{self.server_name}': Processing .mcpack '{mcpack_filename}'."
        )

        temp_dir = tempfile.mkdtemp(prefix=f"mcpack_{self.server_name}_")
        self.logger.debug(
            f"Created temporary directory for .mcpack extraction: {temp_dir}"
        )

        try:
            try:
                self.logger.info(f"Extracting '{mcpack_filename}' to temp dir...")
                with zipfile.ZipFile(mcpack_file_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
                self.logger.debug(f"Successfully extracted '{mcpack_filename}'.")
            except zipfile.BadZipFile as e:
                self.logger.error(
                    f"Failed to extract '{mcpack_file_path}': Invalid ZIP. {e}",
                    exc_info=True,
                )
                raise ExtractError(
                    f"Invalid .mcpack (not zip): {mcpack_filename}"
                ) from e
            except OSError as e:
                self.logger.error(
                    f"OS error extracting '{mcpack_file_path}': {e}", exc_info=True
                )
                raise FileOperationError(
                    f"Error extracting '{mcpack_filename}': {e}"
                ) from e

            self._install_pack_from_extracted_data(temp_dir, mcpack_file_path)

        finally:
            if os.path.isdir(temp_dir):
                try:
                    self.logger.debug(f"Cleaning up temp directory: {temp_dir}")
                    shutil.rmtree(temp_dir)
                except OSError as e:
                    self.logger.warning(
                        f"Could not remove temp directory '{temp_dir}': {e}",
                        exc_info=True,
                    )

    def _install_pack_from_extracted_data(
        self, extracted_pack_dir: str, original_mcpack_path: str
    ) -> None:
        """
        Reads manifest.json from extracted pack, determines type, and installs it into this server.
        This combines original _process_manifest_and_install and install_pack.
        """
        # server_name and base_dir are self.server_name and self.base_dir
        original_mcpack_filename = os.path.basename(original_mcpack_path)
        self.logger.debug(
            f"Server '{self.server_name}': Processing manifest for pack from '{original_mcpack_filename}' in '{extracted_pack_dir}'."
        )

        try:
            pack_type, uuid, version_list, addon_name = self._extract_manifest_info(
                extracted_pack_dir
            )
            self.logger.info(
                f"Manifest for '{original_mcpack_filename}': Type='{pack_type}', UUID='{uuid}', Version='{version_list}', Name='{addon_name}'"
            )

            # --- Installation Logic ---
            active_world_name = self.get_world_name()  # From StateMixin

            # Paths within the active world
            active_world_dir = os.path.join(
                self.server_dir, "worlds", active_world_name
            )
            behavior_packs_target_base = os.path.join(
                active_world_dir, "behavior_packs"
            )
            resource_packs_target_base = os.path.join(
                active_world_dir, "resource_packs"
            )
            world_behavior_packs_json = os.path.join(
                active_world_dir, "world_behavior_packs.json"
            )
            world_resource_packs_json = os.path.join(
                active_world_dir, "world_resource_packs.json"
            )

            os.makedirs(behavior_packs_target_base, exist_ok=True)
            os.makedirs(resource_packs_target_base, exist_ok=True)

            version_str = ".".join(map(str, version_list))
            safe_addon_folder_name = (
                re.sub(r'[<>:"/\\|?*]', "_", addon_name) + f"_{version_str}"
            )  # Unique folder for this version

            target_install_path: str
            target_world_json_file: str
            pack_type_friendly_name: str

            if pack_type == "data":  # Behavior pack
                target_install_path = os.path.join(
                    behavior_packs_target_base, safe_addon_folder_name
                )
                target_world_json_file = world_behavior_packs_json
                pack_type_friendly_name = "behavior"
            elif pack_type == "resources":  # Resource pack
                target_install_path = os.path.join(
                    resource_packs_target_base, safe_addon_folder_name
                )
                target_world_json_file = world_resource_packs_json
                pack_type_friendly_name = "resource"
            else:  # Should be caught by _extract_manifest_info earlier
                raise UserInputError(
                    f"Cannot install unknown pack type: '{pack_type}' for '{original_mcpack_filename}'"
                )

            self.logger.info(
                f"Installing {pack_type_friendly_name} pack '{addon_name}' v{version_str} into: {target_install_path}"
            )

            if os.path.isdir(target_install_path):  # Clean install/update
                self.logger.debug(
                    f"Removing existing target directory: {target_install_path}"
                )
                shutil.rmtree(target_install_path)

            shutil.copytree(
                extracted_pack_dir, target_install_path
            )  # dirs_exist_ok=False implicitly after rmtree
            self.logger.debug(f"Copied pack contents to '{target_install_path}'.")

            self._update_world_pack_json_file(
                target_world_json_file, uuid, version_list
            )
            self.logger.info(
                f"Successfully installed and activated {pack_type_friendly_name} pack '{addon_name}' v{version_str} for server '{self.server_name}'."
            )

        except (AppFileNotFoundError, ConfigParseError) as e_manifest:
            self.logger.error(
                f"Failed to process manifest for '{original_mcpack_filename}': {e_manifest}",
                exc_info=True,
            )
            raise
        except (FileOperationError, UserInputError, AppFileNotFoundError) as e_install:
            self.logger.error(
                f"Failed to install pack from '{original_mcpack_filename}': {e_install}",
                exc_info=True,
            )
            raise
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error installing pack '{original_mcpack_filename}': {e_unexp}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Unexpected error processing pack '{original_mcpack_filename}' for server '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def _extract_manifest_info(
        self, extracted_pack_dir: str
    ) -> Tuple[str, str, List[int], str]:
        """Extracts key information (type, uuid, version, name) from manifest.json."""

        manifest_file = os.path.join(extracted_pack_dir, "manifest.json")
        self.logger.debug(f"Attempting to read manifest file: {manifest_file}")

        if not os.path.isfile(manifest_file):
            raise AppFileNotFoundError(manifest_file, "Manifest file")

        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)

            if not isinstance(manifest_data, dict):
                raise ConfigParseError("Manifest content is not a valid JSON object.")

            header = manifest_data.get("header")
            if not isinstance(header, dict):
                raise ConfigParseError("Manifest missing or invalid 'header' object.")

            uuid_val = header.get("uuid")
            version_val = header.get("version")  # list [major, minor, patch]
            name_val = header.get("name")

            modules = manifest_data.get("modules")
            if not isinstance(modules, list) or not modules:
                raise ConfigParseError("Manifest missing or invalid 'modules' array.")

            first_module = modules[0]
            if not isinstance(first_module, dict):
                raise ConfigParseError(
                    "First item in 'modules' array is not valid object."
                )
            pack_type_val = first_module.get("type")

            # Validate extracted fields
            if not (
                uuid_val
                and isinstance(uuid_val, str)
                and version_val
                and isinstance(version_val, list)
                and len(version_val) == 3
                and all(
                    isinstance(v, int) for v in version_val
                )  # Ensure version numbers are int
                and name_val
                and isinstance(name_val, str)
                and pack_type_val
                and isinstance(pack_type_val, str)
            ):
                missing_details = f"uuid: {uuid_val}, version: {version_val}, name: {name_val}, type: {pack_type_val}"
                raise ConfigParseError(
                    f"Invalid manifest structure in {manifest_file}. Details: {missing_details}"
                )

            pack_type_cleaned = pack_type_val.lower()
            # Minecraft uses "data" for behavior packs and "resources" for resource packs.
            # Other types like "skin_pack", "world_template" might appear but are not typically server-side packs.
            if pack_type_cleaned not in ("data", "resources"):
                self.logger.warning(
                    f"Manifest specified pack type '{pack_type_cleaned}', which might not be standard server pack type."
                )
                raise UserInputError(
                    f"Pack type '{pack_type_cleaned}' from manifest is not 'data' or 'resources'."
                )

            self.logger.debug(
                f"Extracted manifest: Type='{pack_type_cleaned}', UUID='{uuid_val}', Version='{version_val}', Name='{name_val}'"
            )
            return pack_type_cleaned, uuid_val, version_val, name_val

        except ValueError as e:
            raise ConfigParseError(
                f"Invalid JSON in manifest '{manifest_file}': {e}"
            ) from e
        except OSError as e:  # File read error
            raise FileOperationError(
                f"Cannot read manifest file '{manifest_file}': {e}"
            ) from e
        # ConfigParseError for missing keys/invalid structure is handled by direct raises above.

    def _update_world_pack_json_file(
        self, world_json_file_path: str, pack_uuid: str, pack_version_list: List[int]
    ) -> None:
        """Updates a world's pack list JSON file (behavior or resource) with a pack entry."""

        json_filename_basename = os.path.basename(world_json_file_path)
        self.logger.debug(
            f"Updating world pack JSON '{json_filename_basename}' for UUID: {pack_uuid}, Version: {pack_version_list}"
        )

        packs_list = []
        try:
            if os.path.exists(world_json_file_path):
                with open(world_json_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        loaded_packs = json.loads(content)
                        if isinstance(loaded_packs, list):
                            packs_list = loaded_packs
                        else:  # File exists, but not a list
                            self.logger.warning(
                                f"'{json_filename_basename}' content not a list. Will overwrite."
                            )
            # else: File doesn't exist, packs_list remains empty.
        except ValueError as e:
            self.logger.warning(
                f"Invalid JSON in '{json_filename_basename}'. Will overwrite. Error: {e}"
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to read world pack JSON '{json_filename_basename}': {e}"
            ) from e

        pack_entry_found = False
        input_version_tuple = tuple(pack_version_list)

        for i, existing_pack_entry in enumerate(packs_list):
            if (
                isinstance(existing_pack_entry, dict)
                and existing_pack_entry.get("pack_id") == pack_uuid
            ):
                pack_entry_found = True
                existing_version_list = existing_pack_entry.get("version")
                if (
                    isinstance(existing_version_list, list)
                    and len(existing_version_list) == 3
                ):
                    existing_version_tuple = tuple(existing_version_list)
                    if input_version_tuple >= existing_version_tuple:
                        if input_version_tuple > existing_version_tuple:
                            self.logger.info(
                                f"Updating pack '{pack_uuid}' in '{json_filename_basename}' from v{existing_version_list} to v{pack_version_list}."
                            )
                        packs_list[i] = {
                            "pack_id": pack_uuid,
                            "version": pack_version_list,
                        }

                else:  # Invalid existing version, overwrite
                    self.logger.warning(
                        f"Pack '{pack_uuid}' in '{json_filename_basename}' has invalid version. Overwriting with v{pack_version_list}."
                    )
                    packs_list[i] = {"pack_id": pack_uuid, "version": pack_version_list}
                break

        if not pack_entry_found:
            self.logger.info(
                f"Adding new pack '{pack_uuid}' v{pack_version_list} to '{json_filename_basename}'."
            )
            packs_list.append({"pack_id": pack_uuid, "version": pack_version_list})

        try:
            os.makedirs(
                os.path.dirname(world_json_file_path), exist_ok=True
            )  # Ensure parent dir
            with open(world_json_file_path, "w", encoding="utf-8") as f:
                json.dump(packs_list, f, indent=2, sort_keys=True)
            self.logger.debug(
                f"Successfully wrote updated packs to '{json_filename_basename}'."
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to write world pack JSON '{json_filename_basename}': {e}"
            ) from e
