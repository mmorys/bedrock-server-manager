# bedrock-server-manager/bedrock_server_manager/api/task_scheduler.py
import os
import re
import logging
from datetime import datetime
import xml.etree.ElementTree as ET
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import InvalidCronJobError
from bedrock_server_manager.utils.general import get_base_dir, get_timestamp
from bedrock_server_manager.core.system import (
    linux as system_linux,
    windows as system_windows,
)


logger = logging.getLogger("bedrock_server_manager")


def get_server_cron_jobs(server_name, base_dir=None):
    """Retrieves the cron jobs for a specific server.

    Args:
        server_name (str): The name of the server.
        base_dir (str, optional): base directory. Defaults to None.

    Returns:
        dict: {"status": "success", "cron_jobs": [...]} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.debug(f"Getting cron jobs for server: {server_name}")
    try:
        cron_jobs = system_linux.get_server_cron_jobs(server_name)
        logger.debug(f"Cron jobs for {server_name}: {cron_jobs}")
        return {"status": "success", "cron_jobs": cron_jobs}
    except Exception as e:
        logger.exception(f"Failed to retrieve cron jobs for {server_name}: {e}")
        return {"status": "error", "message": f"Failed to retrieve cron jobs: {e}"}


def get_cron_jobs_table(cron_jobs):
    """Formats cron job data for display in a table.

    Args:
        cron_jobs (list): A list of cron job strings.

    Returns:
        dict: {"status": "success", "table_data": [...]} or {"status": "error", "message": ...}
    """
    logger.debug(f"Formatting cron jobs for table display: {cron_jobs}")
    try:
        table_data = system_linux.get_cron_jobs_table(cron_jobs)
        logger.debug(f"Formatted cron job table data: {table_data}")
        return {"status": "success", "table_data": table_data}
    except Exception as e:
        logger.exception(f"Error formatting cron job table: {e}")
        return {"status": "error", "message": f"Error formatting cron job table: {e}"}


def add_cron_job(cron_job_string, base_dir=None):
    """Adds a new cron job.

    Args:
        cron_job_string (str): The complete cron job string.
        base_dir (str, optional): The base_dir. defaults to none

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Adding cron job: {cron_job_string}")
    try:
        system_linux._add_cron_job(cron_job_string)
        logger.debug(f"Cron job added: {cron_job_string}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error adding cron job: {e}")
        return {"status": "error", "message": f"Error adding cron job: {e}"}


def modify_cron_job(old_cron_job_string, new_cron_job_string, base_dir=None):
    """Modifies an existing cron job.

    Args:
        old_cron_job_string (str): The existing cron job string.
        new_cron_job_string (str): The new cron job string.
        base_dir (str, optional): The base_dir. defaults to none

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(
        f"Modifying cron job: Old: {old_cron_job_string} New: {new_cron_job_string}"
    )
    try:
        system_linux._modify_cron_job(old_cron_job_string, new_cron_job_string)
        logger.debug(
            f"Cron job modified. Old: {old_cron_job_string}  New: {new_cron_job_string}"
        )
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error modifying cron job: {e}")
        return {"status": "error", "message": f"Error modifying cron job: {e}"}


def delete_cron_job(cron_job_string, base_dir=None):
    """Deletes a cron job.

    Args:
        cron_job_string (str): The cron job string to delete.
        base_dir (str, optional): The base_dir. defaults to none

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Deleting cron job: {cron_job_string}")
    try:
        system_linux._delete_cron_job(cron_job_string)
        logger.debug(f"Cron job deleted: {cron_job_string}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error deleting cron job {cron_job_string}: {e}")
        return {"status": "error", "message": f"Error deleting cron job: {e}"}


def validate_cron_input(value, min_val, max_val):
    """Validates a single cron input value (minute, hour, day, etc.)."""
    logger.debug(f"Validating cron input: value={value}, min={min_val}, max={max_val}")
    try:
        system_linux.validate_cron_input(value, min_val, max_val)
        logger.debug(f"Cron input {value} is valid.")
        return {"status": "success"}
    except InvalidCronJobError as e:
        logger.error(f"Invalid cron input: {e}")
        return {"status": "error", "message": str(e)}


def convert_to_readable_schedule(month, day, hour, minute, weekday):
    """Converts cron schedule components to a human-readable string."""
    logger.debug(
        f"Converting cron schedule to readable format: month={month}, day={day}, hour={hour}, minute={minute}, weekday={weekday}"
    )
    try:
        schedule_time = system_linux.convert_to_readable_schedule(
            month, day, hour, minute, weekday
        )
        if schedule_time is None:
            logger.error("Error converting schedule to readable format")
            return {"status": "error", "message": "Error Converting Schedule"}
        logger.debug(f"Converted schedule: {schedule_time}")
        return {"status": "success", "schedule_time": schedule_time}
    except Exception as e:
        logger.exception(f"Error converting schedule: {e}")
        return {"status": "error", "message": str(e)}


def get_server_task_names(server_name, config_dir=None):
    """Retrieves the scheduled task names for a specific server.

    Args:
        server_name (str): The name of the server.
        config_dir (str, optional): The config directory. Defaults to main config dir.

    Returns:
        dict: {"status": "success", "task_names": [...]} or {"status": "error", "message": ...}
    """
    if config_dir is None:
        config_dir = settings._config_dir
    logger.debug(f"Getting task names for server: {server_name}")
    try:
        task_names = system_windows.get_server_task_names(server_name, config_dir)
        logger.debug(f"Task names for {server_name}: {task_names}")
        return {"status": "success", "task_names": task_names}
    except Exception as e:
        logger.exception(f"Error getting task names for {server_name}: {e}")
        return {"status": "error", "message": f"Error getting task names: {e}"}


def get_windows_task_info(task_names):
    """Retrieves detailed information for a list of Windows tasks.

    Args:
        task_names (list): A list of task names.

    Returns:
        dict: {"status": "success", "task_info": [...]} or {"status": "error", "message": ...}
    """
    logger.debug(f"Getting Windows task info for tasks: {task_names}")
    try:
        task_info = system_windows.get_windows_task_info(task_names)
        logger.debug(f"Task info: {task_info}")
        return {"status": "success", "task_info": task_info}
    except Exception as e:
        logger.exception(f"Error getting task info: {e}")
        return {"status": "error", "message": f"Error getting task info: {e}"}


def create_windows_task(
    server_name, command, command_args, task_name, config_dir, triggers, base_dir=None
):
    """Creates a Windows scheduled task.

    Args:
        server_name (str): The name of the server.
        command (str): The command to execute (e.g., "update-server").
        command_args (str): Arguments for the command.
        task_name (str): The name of the task.
        config_dir (str): The config directory.
        triggers (list): A list of trigger dictionaries (as returned by get_trigger_details).
        base_dir (str, optional): base directory. defaults to None
    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)  # Keep for consistency
    logger.info(f"Creating Windows task: {task_name} for server: {server_name}")
    try:
        xml_file_path = system_windows.create_windows_task_xml(
            server_name, command, command_args, task_name, config_dir, triggers
        )
        system_windows.import_task_xml(xml_file_path, task_name)
        logger.info(f"Created Windows task: {task_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error creating Windows task {task_name}: {e}")
        return {"status": "error", "message": f"Error creating task: {e}"}


def get_windows_task_details(task_file_path):
    """
    Reads a Windows Task Scheduler XML file and extracts detailed information
    including command path, full arguments, base command, and triggers.

    Args:
        task_file_path (str): Path to the XML file for the scheduled task.

    Returns:
        dict: {
                  "status": "success",
                  "task_details": {
                      "command_path": "...", # e.g., C:/Python/python.exe or bedrock-server-manager.exe path
                      "command_args": "...", # Full arguments string, e.g., "start-server --server s1"
                      "base_command": "...", # e.g., "start-server"
                      "triggers": [...]
                  }
              }
              or {"status": "error", "message": ...}
    """
    logger.debug(f"Handler: Loading existing task data from XML: {task_file_path}")
    if not os.path.exists(task_file_path):
        logger.error(f"Handler: Task XML file not found: {task_file_path}")
        return {"status": "error", "message": "Task configuration file not found."}

    try:
        tree = ET.parse(task_file_path)
        root = tree.getroot()
        # Define namespace (adjust if different in your XML)
        namespaces = {"ns": "http://schemas.microsoft.com/windows/2004/02/mit/task"}

        # --- Extract Command Path and Arguments ---
        command_path = ""
        command_args = ""
        base_command = ""

        command_element = root.find(".//ns:Command", namespaces)
        if command_element is not None and command_element.text:
            command_path = command_element.text.strip()

        arguments_element = root.find(".//ns:Arguments", namespaces)
        if arguments_element is not None and arguments_element.text:
            command_args = arguments_element.text.strip()
            # Try to extract base command (first word of args)
            if command_args:
                try:
                    base_command = command_args.split()[0]
                except IndexError:
                    logger.warning(
                        f"Could not extract base command from arguments in {task_file_path}"
                    )
                    base_command = ""  # Or maybe set based on command_path? Depends on your structure.

        logger.debug(
            f"Extracted from XML: Path='{command_path}', Args='{command_args}', BaseCmd='{base_command}'"
        )

        # --- Extract Triggers (Keep existing logic, ensure it matches JS needs) ---
        triggers = []
        trigger_elements = root.findall(".//ns:Triggers/*", namespaces)
        logger.debug(f"Found {len(trigger_elements)} trigger elements in XML.")
        for trigger_elem in trigger_elements:
            trigger_data = {
                "type": trigger_elem.tag.replace(
                    f"{{{namespaces['ns']}}}", ""
                )  # e.g., TimeTrigger, CalendarTrigger
            }
            start_elem = trigger_elem.find("ns:StartBoundary", namespaces)
            if start_elem is not None and start_elem.text:
                try:
                    # Parse ISO string from XML (likely includes T and maybe Z or offset)
                    iso_dt = datetime.fromisoformat(start_elem.text)
                    # Format consistently for datetime-local input: YYYY-MM-DDTHH:MM
                    trigger_data["start"] = iso_dt.strftime("%Y-%m-%dT%H:%M")
                except ValueError:
                    logger.warning(
                        f"Could not parse start boundary format: {start_elem.text} in {task_file_path}"
                    )
                    trigger_data["start"] = ""  # Or handle error differently

            # -- Parse Calendar Trigger Subtypes --
            if trigger_data["type"] == "CalendarTrigger":
                schedule_by_day = trigger_elem.find("ns:ScheduleByDay", namespaces)
                schedule_by_week = trigger_elem.find("ns:ScheduleByWeek", namespaces)
                schedule_by_month = trigger_elem.find("ns:ScheduleByMonth", namespaces)

                if schedule_by_day is not None:
                    trigger_data["subtype"] = "Daily"  # Use 'subtype' or refine 'type'
                    interval_elem = schedule_by_day.find("ns:DaysInterval", namespaces)
                    trigger_data["interval"] = (
                        int(interval_elem.text)
                        if interval_elem is not None and interval_elem.text
                        else 1
                    )

                elif schedule_by_week is not None:
                    trigger_data["subtype"] = "Weekly"
                    interval_elem = schedule_by_week.find(
                        "ns:WeeksInterval", namespaces
                    )
                    trigger_data["interval"] = (
                        int(interval_elem.text)
                        if interval_elem is not None and interval_elem.text
                        else 1
                    )
                    days_elem = schedule_by_week.find("ns:DaysOfWeek", namespaces)
                    days_list = []
                    if days_elem is not None:
                        # Map XML tag names (Monday, Tuesday) to consistent values (e.g., full names)
                        day_mapping = {
                            "Sunday": "Sunday",
                            "Monday": "Monday",
                            "Tuesday": "Tuesday",
                            "Wednesday": "Wednesday",
                            "Thursday": "Thursday",
                            "Friday": "Friday",
                            "Saturday": "Saturday",
                        }
                        days_list = [
                            day_mapping.get(
                                day.tag.replace(f"{{{namespaces['ns']}}}", ""), None
                            )
                            for day in days_elem
                        ]
                        days_list = [
                            d for d in days_list if d
                        ]  # Filter out None if mapping fails
                    # Store as list for JS processing (JS will handle checkbox state)
                    trigger_data["days"] = (
                        days_list  # Changed key to 'days' to match JS expectation
                    )

                elif schedule_by_month is not None:
                    trigger_data["subtype"] = "Monthly"
                    days_of_month_list = []
                    days_elem = schedule_by_month.find("ns:DaysOfMonth", namespaces)
                    if days_elem is not None:
                        days_of_month_list = [
                            d.text
                            for d in days_elem.findall("ns:Day", namespaces)
                            if d.text
                        ]
                    # Store as list of strings for JS (JS will handle input value)
                    trigger_data["days_of_month"] = days_of_month_list  # Changed key

                    months_of_year_list = []
                    months_elem = schedule_by_month.find("ns:Months", namespaces)
                    if months_elem is not None:
                        # Map XML tag names (January, February) to consistent values (e.g., short names Jan, Feb)
                        month_mapping = {
                            "January": "Jan",
                            "February": "Feb",
                            "March": "Mar",
                            "April": "Apr",
                            "May": "May",
                            "June": "Jun",
                            "July": "Jul",
                            "August": "Aug",
                            "September": "Sep",
                            "October": "Oct",
                            "November": "Nov",
                            "December": "Dec",
                        }
                        months_of_year_list = [
                            month_mapping.get(
                                m.tag.replace(f"{{{namespaces['ns']}}}", ""), None
                            )
                            for m in months_elem
                        ]
                        months_of_year_list = [
                            m for m in months_of_year_list if m
                        ]  # Filter out None
                    # Store as list for JS (JS will handle input value)
                    trigger_data["months"] = months_of_year_list  # Changed key

                else:
                    logger.warning(
                        f"Unknown CalendarTrigger subtype in {task_file_path}"
                    )
                    # Keep original type 'CalendarTrigger' or mark as unknown?
                    trigger_data["subtype"] = "UnknownCalendar"

            # Add parsed trigger to list if it has a valid type
            if trigger_data.get("type"):
                # Refine type based on subtype if present
                if trigger_data.get("subtype"):
                    trigger_data["type"] = trigger_data.pop(
                        "subtype"
                    )  # Replace 'CalendarTrigger' with 'Daily', 'Weekly', etc.

                triggers.append(trigger_data)
            else:
                logger.warning(
                    f"Skipping trigger element with no discernible type: {ET.tostring(trigger_elem, encoding='unicode')}"
                )

        logger.debug(
            f"Handler: Extracted details: BaseCmd='{base_command}', Triggers={triggers}"
        )
        return {
            "status": "success",
            "task_details": {
                "command_path": command_path,  # Full path to executable (optional for JS)
                "command_args": command_args,  # Full arguments string (optional for JS)
                "base_command": base_command,  # The command name for the dropdown
                "triggers": triggers,  # List of parsed trigger dictionaries
            },
        }

    except ET.ParseError as e:
        logger.error(f"Handler: Error parsing task XML {task_file_path}: {e}")
        return {"status": "error", "message": f"Error parsing task configuration: {e}"}
    except Exception as e:  # Catch unexpected errors
        logger.exception(
            f"Handler: Unexpected error loading task XML {task_file_path}: {e}"
        )
        return {
            "status": "error",
            "message": f"Unexpected error loading task configuration: {e}",
        }


def modify_windows_task(
    old_task_name,
    server_name,
    command,
    command_args,
    new_task_name,
    config_dir,
    triggers,
    base_dir=None,
):
    """Modifies an existing Windows scheduled task (by deleting and recreating)."""
    base_dir = get_base_dir(base_dir)  # Keep for consistency
    logger.info(
        f"Modifying Windows task. Old: {old_task_name}, New: {new_task_name} for server: {server_name}"
    )
    old_xml_file_path = os.path.join(config_dir, server_name, f"{old_task_name}.xml")

    try:

        # 1. Create the new XML
        new_xml_file_path = system_windows.create_windows_task_xml(
            server_name, "", command_args, new_task_name, config_dir, triggers
        )

        # 2. Delete the old task
        try:
            system_windows.delete_task(old_task_name)
            logger.debug(f"Deleted old task: {old_task_name}")
        except Exception as e:
            logger.warning(f"Failed to remove task XML: {e}")

        if os.path.exists(old_xml_file_path):
            try:
                os.remove(old_xml_file_path)
                logger.debug(f"Deleted old task XML file: {old_xml_file_path}")
            except OSError as e:
                logger.warning(f"Failed to remove task XML file: {e}")

        # 3. Import the new task
        system_windows.import_task_xml(new_xml_file_path, new_task_name)
        logger.info(
            f"Modified Windows task. Old: {old_task_name}, New: {new_task_name}"
        )
        return {"status": "success"}
    except Exception as e:
        logger.exception(
            f"Error modifying Windows task. Old: {old_task_name}, New: {new_task_name}: {e}"
        )
        return {"status": "error", "message": f"Error modifying task: {e}"}


def create_task_name(server_name, command_args):
    """Cleans up task names for modify windows task."""
    logger.debug(f"Creating task name for server: {server_name}, args: {command_args}")
    # Remove '--server' and the server name using regex
    cleaned_args = re.sub(
        r"--server\s+" + re.escape(server_name) + r"\s*", "", command_args
    ).strip()
    # Replace all non-alphanumeric characters with underscores
    sanitized_args = re.sub(r"\W+", "_", cleaned_args)

    new_task_name = f"bedrock_{server_name}_{sanitized_args}_{get_timestamp()}"
    logger.debug(f"Created task name: {new_task_name}")
    return new_task_name


def delete_windows_task(task_name, task_file_path, base_dir=None):
    """Deletes a Windows scheduled task and its associated XML file.

    Args:
        task_name (str): The name of the task to delete.
        task_file_path (str): Path to the XML file.
        base_dir (str, optional): base directory

    Returns:
        dict: {"status": "success"} or {"status": "error", "message": ...}
    """
    base_dir = get_base_dir(base_dir)
    logger.info(f"Deleting Windows task: {task_name}")
    try:
        system_windows.delete_task(task_name)
        # Also remove the XML file
        try:
            os.remove(task_file_path)
            logger.debug(f"Deleted task XML file: {task_file_path}")
        except OSError as e:
            logger.warning(f"Failed to remove task XML file: {e}")  # Log but don't fail
        logger.debug(f"Deleted task: {task_name}")
        return {"status": "success"}
    except Exception as e:
        logger.exception(f"Error deleting task {task_name}: {e}")
        return {"status": "error", "message": f"Error deleting task: {e}"}


def get_day_element_name(day_input):
    """Gets the XML element name for a day of the week."""
    logger.debug(f"Getting day element name for: {day_input}")
    try:
        day_name = system_windows._get_day_element_name(day_input)
        logger.debug(f"Day element name: {day_name}")
        return {"status": "success", "day_name": day_name}
    except Exception as e:
        logger.exception(f"Error getting day element name for: {day_input} - {e}")
        return {"status": "error", "message": str(e)}


def get_month_element_name(month_input):
    """Gets the XML element name for a month."""
    logger.debug(f"Getting month element name for: {month_input}")
    try:
        month_name = system_windows._get_month_element_name(month_input)
        logger.debug(f"Month element name: {month_name}")
        return {"status": "success", "month_name": month_name}
    except Exception as e:
        logger.exception(f"Error getting month element name for {month_input} - {e}")
        return {"status": "error", "message": str(e)}
