# bedrock-server-manager/bedrock_server_manager/api/task_scheduler.py
"""
Provides API-level functions for managing scheduled tasks across platforms.

This module acts as an interface layer, dispatching calls to the appropriate
platform-specific core system functions (Linux cron or Windows Task Scheduler)
for creating, listing, modifying, and deleting scheduled tasks related to
server management. Functions typically return a dictionary indicating success
or failure status.
"""

import os
import re
import logging
import platform
from typing import Dict, List, Optional, Any

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    InvalidCronJobError,
    MissingArgumentError,
    InvalidInputError,
    FileOperationError,
    CommandNotFoundError,
    ScheduleError,
    TaskError,
    InvalidServerNameError,
)
from bedrock_server_manager.utils.general import get_timestamp
from bedrock_server_manager.core.system import (
    linux as system_linux,
    windows as system_windows,
)

logger = logging.getLogger("bedrock_server_manager")

# --- Linux Cron Functions ---


def get_server_cron_jobs(server_name: str) -> Dict[str, Any]:
    """
    Retrieves cron jobs related to a specific server from the user's crontab.

    (Linux-specific)

    Args:
        server_name: The name of the server to filter jobs for.

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "cron_jobs": List[str]} containing raw cron job lines.
        - {"status": "error", "message": str} if an error occurs or not on Linux.

    Raises:
        MissingArgumentError: If `server_name` is empty.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    if platform.system() != "Linux":
        msg = "Cron jobs are only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.debug(f"Retrieving cron jobs for server '{server_name}'...")
    try:
        # Call core function
        cron_jobs_list = system_linux.get_server_cron_jobs(server_name)
        logger.debug(
            f"Found {len(cron_jobs_list)} cron job(s) for server '{server_name}'."
        )
        return {"status": "success", "cron_jobs": cron_jobs_list}
    except (CommandNotFoundError, ScheduleError, InvalidServerNameError) as e:
        logger.error(
            f"Failed to retrieve cron jobs for server '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to retrieve cron jobs: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error retrieving cron jobs for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error retrieving cron jobs: {e}",
        }


def get_cron_jobs_table(cron_jobs: List[str]) -> Dict[str, Any]:
    """
    Formats a list of raw cron job strings into structured dictionaries for display.

    Args:
        cron_jobs: A list of raw cron job strings (as returned by `get_server_cron_jobs`).

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "table_data": List[Dict[str, str]]} formatted job data.
        - {"status": "error", "message": str} if formatting fails.

    Raises:
        TypeError: If `cron_jobs` is not a list.
    """
    if not isinstance(cron_jobs, list):
        raise TypeError("Input 'cron_jobs' must be a list.")

    logger.debug(f"Formatting {len(cron_jobs)} cron job string(s) for table display...")
    try:
        # Call core function
        table_data = system_linux.get_cron_jobs_table(cron_jobs)
        logger.debug(f"Successfully formatted {len(table_data)} cron jobs.")
        return {"status": "success", "table_data": table_data}
    except (
        Exception
    ) as e:  # Core function handles specific parsing/formatting errors internally
        logger.error(
            f"Error formatting cron job list into table data: {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error formatting cron job table: {e}"}


def add_cron_job(cron_job_string: str) -> Dict[str, str]:
    """
    Adds a new job line to the user's crontab.

    (Linux-specific)

    Args:
        cron_job_string: The complete cron job string (e.g., "* * * * * command --args").

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `cron_job_string` is empty.
    """
    if not cron_job_string or not cron_job_string.strip():
        raise MissingArgumentError("Cron job string cannot be empty.")

    if platform.system() != "Linux":
        msg = "Adding cron jobs is only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(f"Attempting to add cron job: '{cron_job_string}'")
    try:
        # Call core function
        system_linux._add_cron_job(cron_job_string.strip())
        logger.info(f"Successfully added cron job: '{cron_job_string}'")
        return {"status": "success", "message": "Cron job added successfully."}
    except (CommandNotFoundError, ScheduleError) as e:
        logger.error(f"Failed to add cron job '{cron_job_string}': {e}", exc_info=True)
        return {"status": "error", "message": f"Error adding cron job: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error adding cron job '{cron_job_string}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Unexpected error adding cron job: {e}"}


def modify_cron_job(
    old_cron_job_string: str, new_cron_job_string: str
) -> Dict[str, str]:
    """
    Modifies an existing cron job by replacing the old line with the new line.

    (Linux-specific)

    Args:
        old_cron_job_string: The exact existing cron job line to replace.
        new_cron_job_string: The new cron job line to insert.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If either `old_cron_job_string` or `new_cron_job_string` is empty.
    """
    if not old_cron_job_string or not old_cron_job_string.strip():
        raise MissingArgumentError("Old cron job string cannot be empty.")
    if not new_cron_job_string or not new_cron_job_string.strip():
        raise MissingArgumentError("New cron job string cannot be empty.")

    if platform.system() != "Linux":
        msg = "Modifying cron jobs is only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    old_cron_strip = old_cron_job_string.strip()
    new_cron_strip = new_cron_job_string.strip()
    logger.info(
        f"Attempting to modify cron job: Replace '{old_cron_strip}' with '{new_cron_strip}'"
    )

    if old_cron_strip == new_cron_strip:
        logger.info(
            "Old and new cron job strings are identical. No modification needed."
        )
        return {
            "status": "success",
            "message": "No modification needed, jobs are identical.",
        }

    try:
        # Call core function
        system_linux._modify_cron_job(old_cron_strip, new_cron_strip)
        logger.info("Successfully modified cron job.")
        return {"status": "success", "message": "Cron job modified successfully."}
    except (CommandNotFoundError, ScheduleError) as e:
        # ScheduleError can be raised if the old job isn't found
        logger.error(f"Failed to modify cron job: {e}", exc_info=True)
        return {"status": "error", "message": f"Error modifying cron job: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error modifying cron job: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Unexpected error modifying cron job: {e}",
        }


def delete_cron_job(cron_job_string: str) -> Dict[str, str]:
    """
    Deletes a specific job line from the user's crontab.

    (Linux-specific)

    Args:
        cron_job_string: The exact cron job line to find and remove.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `cron_job_string` is empty.
    """
    if not cron_job_string or not cron_job_string.strip():
        raise MissingArgumentError("Cron job string to delete cannot be empty.")

    if platform.system() != "Linux":
        msg = "Deleting cron jobs is only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    cron_strip = cron_job_string.strip()
    logger.info(f"Attempting to delete cron job: '{cron_strip}'")

    try:
        # Call core function (handles job not found gracefully)
        system_linux._delete_cron_job(cron_strip)
        logger.info(
            f"Deletion attempt completed for cron job: '{cron_strip}' (job may not have existed)."
        )
        return {
            "status": "success",
            "message": "Cron job deleted successfully (if it existed).",
        }
    except (CommandNotFoundError, ScheduleError) as e:
        logger.error(f"Failed to delete cron job '{cron_strip}': {e}", exc_info=True)
        return {"status": "error", "message": f"Error deleting cron job: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error deleting cron job '{cron_strip}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error deleting cron job: {e}",
        }


def validate_cron_input(value: str, min_val: int, max_val: int) -> Dict[str, str]:
    """
    Validates a single cron time field string (e.g., minute, hour).

    Args:
        value: The string value to validate (e.g., "*", "5", "10").
        min_val: The minimum allowed integer value.
        max_val: The maximum allowed integer value.

    Returns:
        `{"status": "success"}` or `{"status": "error", "message": str}`.
    """

    logger.debug(
        f"Validating cron field input: Value='{value}', Range=[{min_val}-{max_val}]"
    )
    try:
        # Call core validation function (raises InvalidCronJobError)
        system_linux.validate_cron_input(value, min_val, max_val)
        logger.debug(f"Cron input '{value}' is valid for range [{min_val}-{max_val}].")
        return {"status": "success"}
    except InvalidCronJobError as e:
        logger.warning(f"Invalid cron input: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:  # Catch unexpected validation errors
        logger.error(
            f"Unexpected error during cron input validation for '{value}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected validation error: {e}"}


def convert_to_readable_schedule(
    minute: str, hour: str, day_of_month: str, month: str, day_of_week: str
) -> Dict[str, str]:
    """
    Converts cron time fields into a human-readable schedule description.

    Args:
        minute: Cron minute field ('0'-'59' or '*').
        hour: Cron hour field ('0'-'23' or '*').
        day_of_month: Cron day of month field ('1'-'31' or '*').
        month: Cron month field ('1'-'12' or '*').
        day_of_week: Cron day of week field ('0'-'7' or '*', 0/7=Sun).

    Returns:
        A dictionary: `{"status": "success", "schedule_time": str}` or
        `{"status": "error", "message": str}`.
    """
    logger.debug(
        f"Converting cron fields to readable schedule: M={minute} H={hour} DoM={day_of_month} M={month} DoW={day_of_week}"
    )
    try:
        readable_schedule = system_linux.convert_to_readable_schedule(
            minute, hour, day_of_month, month, day_of_week
        )
        logger.debug(f"Converted schedule: '{readable_schedule}'")
        return {"status": "success", "schedule_time": readable_schedule}
    except InvalidCronJobError as e:
        logger.error(f"Invalid cron values provided for conversion: {e}", exc_info=True)
        return {"status": "error", "message": f"Invalid cron values: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error converting cron schedule: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Unexpected error converting schedule: {e}",
        }


# --- Windows Task Scheduler Functions ---


def get_server_task_names(
    server_name: str, config_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves scheduled task names and their XML file paths associated with a specific server.

    (Windows-specific)

    Args:
        server_name: The name of the server.
        config_dir: Optional. Base directory for server configs. Uses default if None.

    Returns:
        A dictionary: `{"status": "success", "task_names": List[Tuple[str, str]]}` where each tuple
        is (task_name, xml_file_path), or `{"status": "error", "message": str}`.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If `config_dir` cannot be determined.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    if platform.system() != "Windows":
        msg = "Windows Task Scheduler functions are only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.debug(f"Getting Windows task names for server '{server_name}'...")
    try:
        effective_config_dir = (
            config_dir
            if config_dir is not None
            else getattr(settings, "_config_dir", None)
        )
        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory is not set or available."
            )

        # Call core function
        task_name_list = system_windows.get_server_task_names(
            server_name, effective_config_dir
        )
        logger.info(
            f"Found {len(task_name_list)} task file(s) for server '{server_name}'."
        )
        return {"status": "success", "task_names": task_name_list}
    except (TaskError, FileOperationError) as e:  # Catch expected errors
        logger.error(
            f"Failed to get task names for server '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error getting task names: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error getting task names for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting task names: {e}",
        }


def get_windows_task_info(task_names: List[str]) -> Dict[str, Any]:
    """
    Retrieves detailed information (command, schedule) for a list of Windows tasks.

    (Windows-specific)

    Args:
        task_names: A list of task names (including Task Scheduler folder path if applicable).

    Returns:
        A dictionary: `{"status": "success", "task_info": List[Dict[str, str]]}` containing
        details for found tasks, or `{"status": "error", "message": str}`.

    Raises:
        TypeError: If `task_names` is not a list.
    """
    if not isinstance(task_names, list):
        raise TypeError("Input 'task_names' must be a list.")

    if platform.system() != "Windows":
        msg = "Windows Task Scheduler functions are only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.debug(f"Getting detailed info for Windows tasks: {task_names}")
    try:
        # Call core function
        task_info_list = system_windows.get_windows_task_info(task_names)
        logger.info(f"Retrieved info for {len(task_info_list)} Windows task(s).")
        return {"status": "success", "task_info": task_info_list}
    except (CommandNotFoundError, TaskError) as e:  # Catch expected errors
        logger.error(f"Failed to get Windows task info: {e}", exc_info=True)
        return {"status": "error", "message": f"Error getting task info: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error getting Windows task info: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Unexpected error getting task info: {e}",
        }


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

    Args:
        server_name: The name of the server (used for saving XML).
        command: The command to run (e.g., "start", "backup"). Passed to the main script.
        command_args: Additional arguments for the command (e.g., "--server MyServer").
        task_name: The desired name for the task in Task Scheduler (e.g., "MyTasks\\MyBackup").
        triggers: A list of trigger dictionaries defining when the task runs.
        config_dir: Optional. Base directory for server configs. Uses default if None.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If required arguments are empty.
        TypeError: If `triggers` is not a list.
        FileOperationError: If `config_dir` cannot be determined or EXPATH is invalid.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not command:
        raise MissingArgumentError("Command cannot be empty.")
    if not task_name:
        raise MissingArgumentError("Task name cannot be empty.")
    if not isinstance(triggers, list):
        raise TypeError("Triggers must be a list.")

    if platform.system() != "Windows":
        msg = "Creating Windows tasks is only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(
        f"Creating Windows scheduled task '{task_name}' for server '{server_name}' to run command '{command}'..."
    )
    try:
        effective_config_dir = (
            config_dir
            if config_dir is not None
            else getattr(settings, "_config_dir", None)
        )
        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory is not set or available."
            )

        # Call core functions to create XML and import it
        xml_file_path = system_windows.create_windows_task_xml(
            server_name,
            command,
            command_args,
            task_name,
            effective_config_dir,
            triggers,
        )
        system_windows.import_task_xml(xml_file_path, task_name)

        logger.info(
            f"Successfully created and imported Windows task '{task_name}'. XML saved at: {xml_file_path}"
        )
        return {
            "status": "success",
            "message": f"Windows task '{task_name}' created successfully.",
        }

    except (
        TaskError,
        CommandNotFoundError,
        FileOperationError,
        InvalidInputError,
        MissingArgumentError,
    ) as e:
        # Catch specific errors from core XML creation or import
        logger.error(f"Failed to create Windows task '{task_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Error creating task: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error creating Windows task '{task_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Unexpected error creating task: {e}"}


def get_windows_task_details(task_file_path: str) -> Dict[str, Any]:
    """
    API wrapper to read a saved task XML file and extract details.

    Calls the core function responsible for parsing the XML file content.

    Args:
        task_file_path: The full path to the saved task definition XML file.

    Returns:
        A dictionary indicating the outcome:
        - {"status": "success", "task_details": Dict} containing parsed details.
        - {"status": "error", "message": str} if the file is not found or parsing fails.

    Raises:
        MissingArgumentError: If `task_file_path` is empty.
        FileNotFoundError: If `task_file_path` does not exist (raised by core).
        TaskError: If XML parsing fails (raised by core).
    """
    if not task_file_path:
        raise MissingArgumentError("Task file path cannot be empty.")

    logger.debug(f"API: Getting details from Windows task XML file: {task_file_path}")

    try:
        # Call the new XML parsing function from core
        result = system_windows._parse_task_xml_file(task_file_path)

        if result.get("status") == "success":
            logger.debug(
                f"API: Successfully parsed task details from '{task_file_path}'."
            )
        else:
            # Log the error message returned by the core function
            logger.error(
                f"API: Failed to parse task details from '{task_file_path}': {result.get('message')}"
            )
        # Return the dictionary directly from the core function
        return result

    except FileNotFoundError as e:
        logger.error(
            f"API: Task XML file not found error during parsing '{task_file_path}': {e}",
            exc_info=True,
        )
        # Let specific exceptions propagate if needed, or convert to dict here:
        return {
            "status": "error",
            "message": f"Task configuration file not found: {task_file_path}",
        }
    except TaskError as e:  # Catch specific TaskError (e.g., XML parse error) from core
        logger.error(
            f"API: Error parsing task XML '{task_file_path}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error parsing task configuration: {e}"}
    except Exception as e:  # Catch unexpected errors calling the core function
        logger.error(
            f"API: Unexpected error getting task details from '{task_file_path}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting task details: {e}",
        }


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
    Modifies an existing Windows scheduled task by deleting the old one and creating a new one.

    (Windows-specific)

    Args:
        old_task_name: The current name of the task in Task Scheduler.
        server_name: The name of the associated server.
        command: The new command for the task.
        command_args: The new arguments for the task.
        new_task_name: The potentially new name for the task (can be same as old_task_name).
        triggers: The new list of trigger dictionaries.
        config_dir: Optional. Base directory for server configs. Uses default if None.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If required arguments are empty.
        TypeError: If `triggers` is not a list.
        FileOperationError: If `config_dir` cannot be determined or EXPATH invalid.
    """
    # Validate inputs
    if not old_task_name:
        raise MissingArgumentError("Old task name cannot be empty.")
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not command:
        raise MissingArgumentError("Command cannot be empty.")
    if not new_task_name:
        raise MissingArgumentError("New task name cannot be empty.")
    if not isinstance(triggers, list):
        raise TypeError("Triggers must be a list.")

    if platform.system() != "Windows":
        msg = "Modifying Windows tasks is only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(
        f"Attempting to modify Windows task '{old_task_name}' to '{new_task_name}' for server '{server_name}'..."
    )

    try:
        effective_config_dir = (
            config_dir
            if config_dir is not None
            else getattr(settings, "_config_dir", None)
        )
        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory is not set or available."
            )

        # 1. Delete the old task first (core function handles "not found" gracefully)
        logger.debug(f"Step 1: Deleting old task '{old_task_name}' (if it exists)...")
        system_windows.delete_task(
            old_task_name
        )  # Raises TaskError on actual deletion failure

        # 2. Delete the old XML file (if it exists)
        # Construct expected old XML path based on naming convention
        old_safe_filename_base = re.sub(r'[\\/*?:"<>|]', "_", old_task_name)
        old_xml_file_path = os.path.join(
            effective_config_dir, server_name, f"{old_safe_filename_base}.xml"
        )
        if os.path.isfile(old_xml_file_path):
            try:
                logger.debug(
                    f"Step 2: Deleting old task XML file '{old_xml_file_path}'..."
                )
                os.remove(old_xml_file_path)
            except OSError as e:
                # Log warning but continue - maybe permissions issue, but try creating new anyway
                logger.warning(
                    f"Could not delete old task XML file '{old_xml_file_path}': {e}. Proceeding with task creation.",
                    exc_info=True,
                )

        # 3. Create and import the new task definition
        logger.debug(
            f"Step 3: Creating and importing new task definition '{new_task_name}'..."
        )
        # Use the API function which handles XML creation and import
        create_result = create_windows_task(
            server_name=server_name,
            command=command,
            command_args=command_args,
            task_name=new_task_name,
            triggers=triggers,
            config_dir=effective_config_dir,
        )

        if create_result.get("status") == "success":
            logger.info(
                f"Successfully modified Windows task (replaced '{old_task_name}' with '{new_task_name}')."
            )
            return {
                "status": "success",
                "message": "Windows task modified successfully.",
            }
        else:
            # Creation/Import failed, return the error from create_windows_task
            logger.error(
                f"Modification failed during new task creation/import phase for '{new_task_name}'."
            )
            return create_result

    except (
        TaskError,
        CommandNotFoundError,
        FileOperationError,
        InvalidInputError,
        MissingArgumentError,
    ) as e:
        # Catch errors from delete_task or create_windows_task setup
        logger.error(
            f"Failed to modify Windows task '{old_task_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error modifying task: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error modifying Windows task '{old_task_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error modifying task: {e}"}


def create_task_name(server_name: str, command_args: str) -> str:
    """
    Generates a unique, filesystem-safe task name based on server name, arguments, and timestamp.

    Args:
        server_name: The name of the associated server.
        command_args: The arguments string for the command.

    Returns:
        A generated task name string.

    Raises:
        MissingArgumentError: If `server_name` is empty.
    """

    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    logger.debug(
        f"Generating task name for: Server='{server_name}', Args='{command_args}'"
    )
    # Remove --server arg specifically
    cleaned_args = re.sub(r"--server\s+\S+\s*", "", command_args).strip()
    # Replace common problematic characters/sequences
    sanitized = re.sub(r'[\\/*?:"<>|\s\-\.]+', "_", cleaned_args).strip("_")
    # Limit length to avoid overly long names
    max_arg_len = 30
    sanitized_short = sanitized[:max_arg_len]

    timestamp = get_timestamp()
    # Format: bedrock_SERVERNAME_SANITIZEDARGS_TIMESTAMP
    task_name = f"bedrock_{server_name}_{sanitized_short}_{timestamp}"
    # Further ensure name validity for Task Scheduler (avoiding just '\')
    task_name = task_name.replace("\\", "_")

    logger.debug(f"Generated task name: {task_name}")
    return task_name


def delete_windows_task(task_name: str, task_file_path: str) -> Dict[str, str]:
    """
    Deletes a Windows scheduled task and its associated definition XML file.

    (Windows-specific)

    Args:
        task_name: The name of the task in Task Scheduler.
        task_file_path: The full path to the task's definition XML file to delete.

    Returns:
        A dictionary: `{"status": "success", "message": ...}` or `{"status": "error", "message": ...}`.

    Raises:
        MissingArgumentError: If `task_name` or `task_file_path` is empty.
    """
    if not task_name:
        raise MissingArgumentError("Task name cannot be empty.")
    if not task_file_path:
        raise MissingArgumentError("Task file path cannot be empty.")

    if platform.system() != "Windows":
        msg = "Deleting Windows tasks is only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(
        f"Attempting to delete Windows task '{task_name}' and its XML file '{task_file_path}'..."
    )

    delete_errors = []
    # 1. Delete the scheduled task
    try:
        system_windows.delete_task(
            task_name
        )  # Core function handles "not found" gracefully
        logger.info(
            f"Task '{task_name}' deleted successfully from Task Scheduler (or was already removed)."
        )
    except (TaskError, CommandNotFoundError) as e:
        logger.error(
            f"Failed to delete task '{task_name}' from Task Scheduler: {e}",
            exc_info=True,
        )
        delete_errors.append(f"Scheduler deletion failed ({e})")
    except Exception as e:
        logger.error(
            f"Unexpected error deleting task '{task_name}' from Task Scheduler: {e}",
            exc_info=True,
        )
        delete_errors.append(f"Scheduler deletion failed unexpectedly ({e})")

    # 2. Delete the associated XML file
    if os.path.isfile(task_file_path):
        try:
            os.remove(task_file_path)
            logger.info(f"Successfully deleted task XML file: {task_file_path}")
        except OSError as e:
            logger.error(
                f"Failed to delete task XML file '{task_file_path}': {e}", exc_info=True
            )
            delete_errors.append(f"XML file deletion failed ({e})")
        except Exception as e:
            logger.error(
                f"Unexpected error deleting task XML file '{task_file_path}': {e}",
                exc_info=True,
            )
            delete_errors.append(f"XML file deletion failed unexpectedly ({e})")
    else:
        logger.debug(
            f"Task XML file '{task_file_path}' not found. Skipping file deletion."
        )

    # --- Final Result ---
    if delete_errors:
        error_summary = "; ".join(delete_errors)
        return {
            "status": "error",
            "message": f"Task deletion completed with errors: {error_summary}",
        }
    else:
        return {
            "status": "success",
            "message": f"Task '{task_name}' and its definition file deleted successfully.",
        }


def get_day_element_name(day_input: Any) -> Dict[str, str]:
    """
    API wrapper to get the Task Scheduler XML element name for a day of the week.

    Args:
        day_input: User input representing a day (e.g., "Mon", "monday", 1, "1").

    Returns:
        `{"status": "success", "day_name": str}` or `{"status": "error", "message": str}`.
    """
    logger.debug(f"API call: Getting day element name for input '{day_input}'")
    try:
        day_name = system_windows._get_day_element_name(
            day_input
        )  # Raises InvalidInputError
        logger.debug(f"Mapped day input '{day_input}' to XML element name '{day_name}'")
        return {"status": "success", "day_name": day_name}
    except InvalidInputError as e:
        logger.warning(f"Failed to map day input '{day_input}': {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"Unexpected error getting day element name for '{day_input}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error getting day name: {e}"}


def get_month_element_name(month_input: Any) -> Dict[str, str]:
    """
    API wrapper to get the Task Scheduler XML element name for a month.

    Args:
        month_input: User input representing a month (e.g., "Jan", "january", 1, "1").

    Returns:
        `{"status": "success", "month_name": str}` or `{"status": "error", "message": str}`.
    """

    logger.debug(f"API call: Getting month element name for input '{month_input}'")
    try:
        month_name = system_windows._get_month_element_name(
            month_input
        )  # Raises InvalidInputError
        logger.debug(
            f"Mapped month input '{month_input}' to XML element name '{month_name}'"
        )
        return {"status": "success", "month_name": month_name}
    except InvalidInputError as e:
        logger.warning(f"Failed to map month input '{month_input}': {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"Unexpected error getting month element name for '{month_input}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting month name: {e}",
        }
