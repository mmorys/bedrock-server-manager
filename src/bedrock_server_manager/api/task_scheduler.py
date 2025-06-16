# bedrock_server_manager/api/task_scheduler.py
"""
Provides API-level functions for managing scheduled tasks across platforms.

This module acts as an interface layer, dispatching calls to the appropriate
platform-specific core system classes (LinuxTaskScheduler or WindowsTaskScheduler)
for creating, listing, modifying, and deleting scheduled tasks. Functions typically
return a dictionary indicating success or failure status.
"""

import os
import re
import logging
from typing import Dict, List, Optional, Any

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.utils.general import get_timestamp
from bedrock_server_manager.core.system import task_scheduler as core_task
from bedrock_server_manager.error import (
    BSMError,
    MissingArgumentError,
    UserInputError,
    FileOperationError,
    SystemError,
    InvalidServerNameError,
)

logger = logging.getLogger(__name__)

# --- Initialize the appropriate scheduler for the current OS ---
scheduler = core_task.get_task_scheduler()


# --- Linux Cron Functions ---


def get_server_cron_jobs(server_name: str) -> Dict[str, Any]:
    """
    Retrieves cron jobs related to a specific server from the user's crontab.
    (Linux-specific)
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    if not isinstance(scheduler, core_task.LinuxTaskScheduler):
        msg = "Cron job operations are only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.debug(f"API: Retrieving cron jobs for server '{server_name}'...")
    try:
        cron_jobs_list = scheduler.get_server_cron_jobs(server_name)
        return {"status": "success", "cron_jobs": cron_jobs_list}
    except BSMError as e:
        logger.error(
            f"Failed to retrieve cron jobs for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to retrieve cron jobs: {e}"}


def get_cron_jobs_table(cron_jobs: List[str]) -> Dict[str, Any]:
    """
    Formats a list of raw cron job strings into structured dictionaries for display.
    (Linux-specific)
    """
    if not isinstance(cron_jobs, list):
        raise TypeError("Input 'cron_jobs' must be a list.")

    if not isinstance(scheduler, core_task.LinuxTaskScheduler):
        msg = "Cron job operations are only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.debug(f"API: Formatting {len(cron_jobs)} cron jobs for table display...")
    try:
        table_data = scheduler.get_cron_jobs_table(cron_jobs)
        return {"status": "success", "table_data": table_data}
    except Exception as e:
        logger.error(
            f"Error formatting cron job list into table data: {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error formatting cron job table: {e}"}


def add_cron_job(cron_job_string: str) -> Dict[str, str]:
    """
    Adds a new job line to the user's crontab.
    (Linux-specific)
    """
    if not cron_job_string or not cron_job_string.strip():
        raise MissingArgumentError("Cron job string cannot be empty.")

    if not isinstance(scheduler, core_task.LinuxTaskScheduler):
        msg = "Cron job operations are only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(f"API: Attempting to add cron job: '{cron_job_string}'")
    try:
        scheduler.add_job(cron_job_string.strip())
        return {"status": "success", "message": "Cron job added successfully."}
    except BSMError as e:
        logger.error(f"Failed to add cron job '{cron_job_string}': {e}", exc_info=True)
        return {"status": "error", "message": f"Error adding cron job: {e}"}


def modify_cron_job(
    old_cron_job_string: str, new_cron_job_string: str
) -> Dict[str, str]:
    """
    Modifies an existing cron job by replacing the old line with the new line.
    (Linux-specific)
    """
    if not old_cron_job_string or not old_cron_job_string.strip():
        raise MissingArgumentError("Old cron job string cannot be empty.")
    if not new_cron_job_string or not new_cron_job_string.strip():
        raise MissingArgumentError("New cron job string cannot be empty.")

    if not isinstance(scheduler, core_task.LinuxTaskScheduler):
        msg = "Cron job operations are only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    old_strip, new_strip = old_cron_job_string.strip(), new_cron_job_string.strip()
    if old_strip == new_strip:
        return {
            "status": "success",
            "message": "No modification needed, jobs are identical.",
        }

    logger.info(
        f"API: Attempting to modify cron job: Replace '{old_strip}' with '{new_strip}'"
    )
    try:
        scheduler.update_job(old_strip, new_strip)
        return {"status": "success", "message": "Cron job modified successfully."}
    except BSMError as e:
        logger.error(f"Failed to modify cron job: {e}", exc_info=True)
        return {"status": "error", "message": f"Error modifying cron job: {e}"}


def delete_cron_job(cron_job_string: str) -> Dict[str, str]:
    """
    Deletes a specific job line from the user's crontab.
    (Linux-specific)
    """
    if not cron_job_string or not cron_job_string.strip():
        raise MissingArgumentError("Cron job string to delete cannot be empty.")

    if not isinstance(scheduler, core_task.LinuxTaskScheduler):
        msg = "Cron job operations are only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    cron_strip = cron_job_string.strip()
    logger.info(f"API: Attempting to delete cron job: '{cron_strip}'")
    try:
        scheduler.delete_job(cron_strip)
        return {
            "status": "success",
            "message": "Cron job deleted successfully (if it existed).",
        }
    except BSMError as e:
        logger.error(f"Failed to delete cron job '{cron_strip}': {e}", exc_info=True)
        return {"status": "error", "message": f"Error deleting cron job: {e}"}


# --- Windows Task Scheduler Functions ---


def get_server_task_names(
    server_name: str, config_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves scheduled task names and their XML file paths associated with a specific server.
    (Windows-specific)
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    if not isinstance(scheduler, core_task.WindowsTaskScheduler):
        msg = "Windows Task Scheduler operations are only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.debug(f"API: Getting Windows task names for server '{server_name}'...")
    try:
        effective_config_dir = config_dir or getattr(settings, "config_dir", None)
        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory is not set or available."
            )

        task_name_list = scheduler.get_server_task_names(
            server_name, effective_config_dir
        )
        return {"status": "success", "task_names": task_name_list}
    except BSMError as e:
        logger.error(
            f"Failed to get task names for server '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error getting task names: {e}"}


def get_windows_task_info(task_names: List[str]) -> Dict[str, Any]:
    """
    Retrieves detailed information for a list of Windows tasks.
    (Windows-specific)
    """
    if not isinstance(task_names, list):
        raise TypeError("Input 'task_names' must be a list.")

    if not isinstance(scheduler, core_task.WindowsTaskScheduler):
        msg = "Windows Task Scheduler operations are only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.debug(f"API: Getting detailed info for Windows tasks: {task_names}")
    try:
        task_info_list = scheduler.get_task_info(task_names)
        return {"status": "success", "task_info": task_info_list}
    except BSMError as e:
        logger.error(f"Failed to get Windows task info: {e}", exc_info=True)
        return {"status": "error", "message": f"Error getting task info: {e}"}


def create_windows_task(
    server_name: str,
    command: str,
    command_args: str,
    task_name: str,
    triggers: List[Dict[str, Any]],
    config_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    Creates a new Windows scheduled task by generating and importing an XML definition.
    (Windows-specific)
    """
    if not all([server_name, command, task_name]):
        raise MissingArgumentError("Server name, command, and task name are required.")
    if not isinstance(triggers, list):
        raise TypeError("Triggers must be a list.")

    if not isinstance(scheduler, core_task.WindowsTaskScheduler):
        msg = "Windows Task operations are only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(
        f"API: Creating Windows task '{task_name}' for server '{server_name}'..."
    )
    try:
        effective_config_dir = config_dir or getattr(settings, "config_dir", None)
        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory is not set or available."
            )

        xml_path = scheduler.create_task_xml(
            server_name,
            command,
            command_args,
            task_name,
            effective_config_dir,
            triggers,
        )
        scheduler.import_task_from_xml(xml_path, task_name)

        return {
            "status": "success",
            "message": f"Windows task '{task_name}' created successfully.",
        }
    except BSMError as e:
        logger.error(f"Failed to create Windows task '{task_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Error creating task: {e}"}


def modify_windows_task(
    old_task_name: str,
    server_name: str,
    command: str,
    command_args: str,
    new_task_name: str,
    triggers: List[Dict[str, Any]],
    config_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    Modifies an existing Windows task by deleting the old one and creating a new one.
    (Windows-specific)
    """
    if not all([old_task_name, server_name, command, new_task_name]):
        raise MissingArgumentError(
            "Old/new task names, server name, and command are required."
        )
    if not isinstance(triggers, list):
        raise TypeError("Triggers must be a list.")

    if not isinstance(scheduler, core_task.WindowsTaskScheduler):
        msg = "Windows Task operations are only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(
        f"API: Modifying Windows task '{old_task_name}' to '{new_task_name}'..."
    )
    try:
        effective_config_dir = config_dir or getattr(settings, "config_dir", None)
        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory is not set or available."
            )

        # 1. Delete the old task
        scheduler.delete_task(old_task_name)

        # 2. Delete the old XML file
        old_safe_filename = re.sub(r'[\\/*?:"<>|]', "_", old_task_name) + ".xml"
        old_xml_path = os.path.join(
            effective_config_dir, server_name, old_safe_filename
        )
        if os.path.isfile(old_xml_path):
            try:
                os.remove(old_xml_path)
            except OSError as e:
                logger.warning(
                    f"Could not delete old task XML '{old_xml_path}': {e}. Proceeding."
                )

        # 3. Create the new task
        return create_windows_task(
            server_name,
            command,
            command_args,
            new_task_name,
            triggers,
            effective_config_dir,
        )
    except BSMError as e:
        logger.error(
            f"Failed to modify Windows task '{old_task_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error modifying task: {e}"}


def delete_windows_task(task_name: str, task_file_path: str) -> Dict[str, str]:
    """
    Deletes a Windows scheduled task and its associated definition XML file.
    (Windows-specific)
    """
    if not task_name:
        raise MissingArgumentError("Task name cannot be empty.")
    if not task_file_path:
        raise MissingArgumentError("Task file path cannot be empty.")

    if not isinstance(scheduler, core_task.WindowsTaskScheduler):
        msg = "Windows Task operations are only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(
        f"API: Deleting Windows task '{task_name}' and file '{task_file_path}'..."
    )
    errors = []

    try:
        scheduler.delete_task(task_name)
    except BSMError as e:
        errors.append(f"Scheduler deletion failed ({e})")
        logger.error(
            f"Failed to delete task '{task_name}' from Task Scheduler: {e}",
            exc_info=True,
        )

    if os.path.isfile(task_file_path):
        try:
            os.remove(task_file_path)
        except OSError as e:
            errors.append(f"XML file deletion failed ({e})")
            logger.error(
                f"Failed to delete task XML file '{task_file_path}': {e}", exc_info=True
            )

    if errors:
        return {
            "status": "error",
            "message": f"Task deletion completed with errors: {'; '.join(errors)}",
        }
    return {
        "status": "success",
        "message": f"Task '{task_name}' and its definition file deleted successfully.",
    }


# --- Platform-Agnostic Helper Functions ---


def create_task_name(server_name: str, command_args: str) -> str:
    """
    Generates a unique, filesystem-safe task name.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    cleaned_args = re.sub(r"--server\s+\S+\s*", "", command_args).strip()
    sanitized = re.sub(r'[\\/*?:"<>|\s\-\.]+', "_", cleaned_args).strip("_")[:30]
    timestamp = get_timestamp()

    task_name = f"bedrock_{server_name}_{sanitized}_{timestamp}"
    return task_name.replace("\\", "_")
