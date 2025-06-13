# bedrock_server_manager/core/system/task_scheduler.py
"""
Provides a platform-agnostic interface for scheduling tasks related to Bedrock servers,
with specific implementations for Linux (cron) and Windows (Task Scheduler).
"""

import platform
import os
import logging
import subprocess
import shutil
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
import xml.etree.ElementTree as ET
import re

# Local imports
from bedrock_server_manager.config.const import EXPATH
from bedrock_server_manager.error import (
    CommandNotFoundError,
    SystemError,
    InvalidServerNameError,
    UserInputError,
    MissingArgumentError,
    FileOperationError,
    AppFileNotFoundError,
    PermissionsError,
)

logger = logging.getLogger(__name__)


def get_task_scheduler() -> Optional[Any]:
    """
    Function to get the appropriate task scheduler for the current OS.

    This function checks the operating system and attempts to instantiate the
    correct scheduler class. It handles cases where the necessary command-line
    tools (like 'crontab' or 'schtasks') are not found, returning None in
    such scenarios.

    Returns:
        An instance of LinuxTaskScheduler on Linux,
        an instance of WindowsTaskScheduler on Windows,
        or None if the OS is not supported or a required tool is missing.
    """
    system = platform.system()

    if system == "Linux":
        try:
            # Attempt to create a Linux scheduler, which checks for 'crontab' in its init
            return LinuxTaskScheduler()
        except CommandNotFoundError:
            logger.error(
                "Linux system detected, but the 'crontab' command is missing. Scheduling will be disabled."
            )
            return None

    elif system == "Windows":
        try:
            # Attempt to create a Windows scheduler, which checks for 'schtasks' in its init
            return WindowsTaskScheduler()
        except CommandNotFoundError:
            logger.error(
                "Windows system detected, but the 'schtasks' command is missing. Scheduling will be disabled."
            )
            return None

    else:
        # Handle other operating systems like macOS, etc.
        logger.warning(
            f"Task scheduling is not supported on this operating system: {system}"
        )
        return None


# --- LINUX Task Scheduler Implementation ---
class LinuxTaskScheduler:
    """
    Manages scheduled tasks (cron jobs) for Bedrock servers on Linux systems.
    """

    # --- Class-level constants for cron parsing ---
    _CRON_MONTHS_MAP = {
        "1": "January",
        "jan": "January",
        "january": "January",
        "2": "February",
        "feb": "February",
        "february": "February",
        "3": "March",
        "mar": "March",
        "march": "March",
        "4": "April",
        "apr": "April",
        "april": "April",
        "5": "May",
        "may": "May",
        "6": "June",
        "jun": "June",
        "june": "June",
        "7": "July",
        "jul": "July",
        "july": "July",
        "8": "August",
        "aug": "August",
        "august": "August",
        "9": "September",
        "sep": "September",
        "september": "September",
        "10": "October",
        "oct": "October",
        "october": "October",
        "11": "November",
        "nov": "November",
        "november": "November",
        "12": "December",
        "dec": "December",
        "december": "December",
    }
    _CRON_DAYS_MAP = {
        "0": "Sunday",
        "sun": "Sunday",
        "sunday": "Sunday",
        "1": "Monday",
        "mon": "Monday",
        "monday": "Monday",
        "2": "Tuesday",
        "tue": "Tuesday",
        "tuesday": "Tuesday",
        "3": "Wednesday",
        "wed": "Wednesday",
        "wednesday": "Wednesday",
        "4": "Thursday",
        "thu": "Thursday",
        "thursday": "Thursday",
        "5": "Friday",
        "fri": "Friday",
        "friday": "Friday",
        "6": "Saturday",
        "sat": "Saturday",
        "saturday": "Saturday",
        "7": "Sunday",  # Also map 7 to Sunday
    }

    def __init__(self):
        """
        Initializes the LinuxTaskScheduler.
        Raises:
            CommandNotFoundError: If the 'crontab' command is not available.
        """
        self.crontab_cmd = shutil.which("crontab")
        if not self.crontab_cmd:
            logger.error("'crontab' command not found. Cannot manage cron jobs.")
            raise CommandNotFoundError("crontab")
        logger.debug("LinuxTaskScheduler initialized successfully.")

    def _get_cron_month_name(self, month_input: str) -> str:
        """Converts cron month input (number or name/abbr) to full month name."""
        month_str = str(month_input).strip().lower()
        if month_str in self._CRON_MONTHS_MAP:
            return self._CRON_MONTHS_MAP[month_str]
        else:
            raise UserInputError(
                f"Invalid month value: '{month_input}'. Use 1-12 or name/abbreviation."
            )

    def _get_cron_dow_name(self, dow_input: str) -> str:
        """Converts cron day-of-week input (number or name/abbr) to full day name."""
        dow_str = str(dow_input).strip().lower()
        if dow_str == "7":
            dow_str = "0"
        if dow_str in self._CRON_DAYS_MAP:
            return self._CRON_DAYS_MAP[dow_str]
        else:
            raise UserInputError(
                f"Invalid day-of-week value: '{dow_input}'. Use 0-6, 7, or name/abbreviation (Sun-Sat)."
            )

    @staticmethod
    def _parse_cron_line(line: str) -> Optional[Tuple[str, str, str, str, str, str]]:
        """Parses a standard cron job line into its time/command components."""
        parts = line.strip().split(maxsplit=5)
        if len(parts) == 6:
            return tuple(parts)  # type: ignore
        else:
            logger.warning(f"Could not parse cron line (expected >= 6 parts): '{line}'")
            return None

    @staticmethod
    def _format_cron_command(command_string: str) -> str:
        """Formats the command part of a cron job for display purposes."""
        try:
            command = command_string.strip()
            script_path_str = str(EXPATH)
            if command.startswith(script_path_str):
                command = command[len(script_path_str) :].strip()
            parts = command.split()
            if parts and (
                parts[0].endswith("python")
                or parts[0].endswith("python3")
                or ".exe" in parts[0]
            ):
                command = " ".join(parts[1:])
            main_command = command.split(maxsplit=1)[0]
            return main_command if main_command else command_string
        except Exception as e:
            logger.warning(
                f"Failed to format cron command '{command_string}' for display: {e}. Returning original.",
                exc_info=True,
            )
            return command_string

    def get_server_cron_jobs(self, server_name: str) -> List[str]:
        """
        Retrieves raw cron job lines from the user's crontab that relate to a specific server.
        """
        if not server_name:
            raise InvalidServerNameError("Server name cannot be empty.")

        logger.debug(f"Retrieving cron jobs related to server '{server_name}'...")
        try:
            process = subprocess.run(
                [self.crontab_cmd, "-l"],
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            if process.returncode == 0:
                all_jobs = process.stdout
            elif process.returncode == 1 and "no crontab for" in process.stderr.lower():
                logger.info("No crontab found for the current user.")
                return []
            else:
                error_msg = f"Error running 'crontab -l'. Return code: {process.returncode}. Error: {process.stderr}"
                logger.error(error_msg)
                raise SystemError(error_msg)

            filtered_jobs: List[str] = []
            server_arg_pattern = f'--server "{server_name}"'
            for line in all_jobs.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if server_arg_pattern in line:
                    filtered_jobs.append(line)
            return filtered_jobs
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while getting cron jobs: {e}",
                exc_info=True,
            )
            raise SystemError(f"Unexpected error getting cron jobs: {e}") from e

    def get_cron_jobs_table(self, cron_jobs: List[str]) -> List[Dict[str, str]]:
        """
        Formats a list of cron job strings into structured dictionaries for display.
        """
        table_data: List[Dict[str, str]] = []
        if not cron_jobs:
            return table_data

        for line in cron_jobs:
            parsed_job = self._parse_cron_line(line)
            if not parsed_job:
                continue

            minute, hour, dom, month, dow, raw_command = parsed_job
            try:
                readable_schedule = self.convert_to_readable_schedule(
                    minute, hour, dom, month, dow
                )
            except UserInputError as e:
                readable_schedule = f"{minute} {hour} {dom} {month} {dow}"
                logger.warning(
                    f"Could not convert schedule '{readable_schedule}' to readable format: {e}."
                )

            display_command = self._format_cron_command(raw_command)

            table_data.append(
                {
                    "minute": minute,
                    "hour": hour,
                    "day_of_month": dom,
                    "month": month,
                    "day_of_week": dow,
                    "command": raw_command,
                    "command_display": display_command,
                    "schedule_time": readable_schedule,
                }
            )
        return table_data

    @staticmethod
    def _validate_cron_input(value: str, min_val: int, max_val: int) -> None:
        """Validates a single cron time field value."""
        if value == "*":
            return
        try:
            num = int(value)
            if not (min_val <= num <= max_val):
                raise UserInputError(
                    f"Value '{value}' is out of range ({min_val}-{max_val})."
                )
        except ValueError:
            logger.debug(
                f"Cron value '{value}' is complex; skipping simple range validation."
            )
            pass

    def convert_to_readable_schedule(
        self, minute: str, hour: str, day_of_month: str, month: str, day_of_week: str
    ) -> str:
        """Converts cron time fields into a human-readable description."""
        self._validate_cron_input(minute, 0, 59)
        self._validate_cron_input(hour, 0, 23)
        self._validate_cron_input(day_of_month, 1, 31)
        self._validate_cron_input(month, 1, 12)
        self._validate_cron_input(day_of_week, 0, 7)
        raw_schedule = f"{minute} {hour} {day_of_month} {month} {day_of_week}"
        try:
            if (
                minute == "*"
                and hour == "*"
                and day_of_month == "*"
                and month == "*"
                and day_of_week == "*"
            ):
                return "Every minute"
            if (
                minute != "*"
                and hour != "*"
                and day_of_month == "*"
                and month == "*"
                and day_of_week == "*"
            ):
                return f"Daily at {int(hour):02d}:{int(minute):02d}"
            if (
                minute != "*"
                and hour != "*"
                and day_of_month == "*"
                and month == "*"
                and day_of_week != "*"
            ):
                day_name = self._get_cron_dow_name(day_of_week)
                return f"Weekly on {day_name} at {int(hour):02d}:{int(minute):02d}"
            if (
                minute != "*"
                and hour != "*"
                and day_of_month != "*"
                and month == "*"
                and day_of_week == "*"
            ):
                return f"Monthly on day {int(day_of_month)} at {int(hour):02d}:{int(minute):02d}"
            if (
                minute != "*"
                and hour != "*"
                and day_of_month != "*"
                and month != "*"
                and day_of_week == "*"
            ):
                month_name = self._get_cron_month_name(month)
                return f"Yearly on {month_name} {int(day_of_month)} at {int(hour):02d}:{int(minute):02d}"
            return f"Cron schedule: {raw_schedule}"
        except (ValueError, UserInputError) as e:
            logger.error(
                f"Could not parse specific schedule '{raw_schedule}': {e}",
                exc_info=True,
            )
            raise UserInputError(f"Invalid value in schedule: {raw_schedule}") from e

    def add_job(self, cron_string: str) -> None:
        """Adds a job string to the current user's crontab."""
        if not cron_string or not cron_string.strip():
            raise MissingArgumentError("Cron job string cannot be empty.")
        cron_string = cron_string.strip()

        logger.info(f"Adding cron job: '{cron_string}'")
        try:
            process = subprocess.run(
                [self.crontab_cmd, "-l"],
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            current_crontab = ""
            if process.returncode == 0:
                current_crontab = process.stdout
            elif "no crontab for" not in process.stderr.lower():
                raise SystemError(f"Error reading current crontab: {process.stderr}")

            if cron_string in [line.strip() for line in current_crontab.splitlines()]:
                logger.warning(
                    f"Cron job '{cron_string}' already exists. Skipping addition."
                )
                return

            if not current_crontab.strip():
                new_crontab_content = cron_string + "\n"
            else:
                new_crontab_content = (
                    current_crontab.strip() + "\n" + cron_string + "\n"
                )

            write_process = subprocess.Popen(
                [self.crontab_cmd, "-"],
                stdin=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            _, stderr = write_process.communicate(input=new_crontab_content)
            if write_process.returncode != 0:
                raise SystemError(f"Failed to write updated crontab. Stderr: {stderr}")

            logger.info(f"Successfully added cron job: '{cron_string}'")
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while adding cron job: {e}",
                exc_info=True,
            )
            raise SystemError(f"Unexpected error adding cron job: {e}") from e

    def update_job(self, old_cron_string: str, new_cron_string: str) -> None:
        """Replaces an existing cron job line with a new one."""
        if not old_cron_string or not old_cron_string.strip():
            raise MissingArgumentError("Old cron string cannot be empty.")
        if not new_cron_string or not new_cron_string.strip():
            raise MissingArgumentError("New cron string cannot be empty.")
        old_cron_string = old_cron_string.strip()
        new_cron_string = new_cron_string.strip()
        if old_cron_string == new_cron_string:
            logger.info(
                "Old and new cron strings are identical. No modification needed."
            )
            return

        logger.info(
            f"Attempting to modify cron job: Replace '{old_cron_string}' with '{new_cron_string}'"
        )
        try:
            process = subprocess.run(
                [self.crontab_cmd, "-l"],
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            current_crontab = ""
            if process.returncode == 0:
                current_crontab = process.stdout
            elif "no crontab for" not in process.stderr.lower():
                raise SystemError(f"Error reading current crontab: {process.stderr}")

            lines = current_crontab.splitlines()
            found = False
            updated_lines = []
            for line in lines:
                if line.strip() == old_cron_string:
                    updated_lines.append(new_cron_string)
                    found = True
                else:
                    updated_lines.append(line)
            if not found:
                raise UserInputError(
                    f"Cron job to modify was not found: '{old_cron_string}'"
                )

            new_crontab_content = "\n".join(updated_lines) + "\n"
            write_process = subprocess.Popen(
                [self.crontab_cmd, "-"],
                stdin=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            _, stderr = write_process.communicate(input=new_crontab_content)
            if write_process.returncode != 0:
                raise SystemError(f"Failed to write modified crontab. Stderr: {stderr}")

            logger.info("Successfully modified cron job.")
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while modifying cron job: {e}",
                exc_info=True,
            )
            raise SystemError(f"Unexpected error modifying cron job: {e}") from e

    def delete_job(self, cron_string: str) -> None:
        """Deletes a specific job line from the user's crontab."""
        if not cron_string or not cron_string.strip():
            raise MissingArgumentError("Cron job string to delete cannot be empty.")
        cron_string = cron_string.strip()

        logger.info(f"Attempting to delete cron job: '{cron_string}'")
        try:
            process = subprocess.run(
                [self.crontab_cmd, "-l"],
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            current_crontab = ""
            if process.returncode == 0:
                current_crontab = process.stdout
            elif "no crontab for" not in process.stderr.lower():
                raise SystemError(f"Error reading current crontab: {process.stderr}")

            lines = current_crontab.splitlines()
            updated_lines = [line for line in lines if line.strip() != cron_string]

            if len(lines) == len(updated_lines):
                logger.warning(
                    f"Cron job to delete was not found: '{cron_string}'. No changes made."
                )
                return

            # If the updated list of jobs is empty, remove the crontab entirely.
            if not updated_lines:
                logger.info(
                    "Last cron job removed. Deleting crontab file with 'crontab -r'."
                )
                # Run the remove command. We use check=False because it might fail if the file
                # was already gone for some reason, which is not a critical error.
                subprocess.run([self.crontab_cmd, "-r"], check=False)
            else:
                # If there are still jobs left, write them back to the file.
                new_crontab_content = "\n".join(updated_lines) + "\n"

                write_process = subprocess.Popen(
                    [self.crontab_cmd, "-"],
                    stdin=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                _, stderr = write_process.communicate(input=new_crontab_content)
                if write_process.returncode != 0:
                    raise SystemError(
                        f"Failed to write updated crontab after deletion. Stderr: {stderr}"
                    )

            logger.info(f"Successfully deleted cron job: '{cron_string}'")
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while deleting cron job: {e}",
                exc_info=True,
            )
            raise SystemError(f"Unexpected error deleting cron job: {e}") from e


# ------

# --- WINDOWS Task Scheduler Implementation ---


class WindowsTaskScheduler:
    """
    Manages scheduled tasks for Bedrock servers on Windows systems using Task Scheduler.
    """

    XML_NAMESPACE = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"

    def __init__(self):
        """
        Initializes the WindowsTaskScheduler.
        Raises:
            CommandNotFoundError: If the 'schtasks' command is not available.
        """
        self.schtasks_cmd = shutil.which("schtasks")
        if not self.schtasks_cmd:
            logger.error("'schtasks' command not found. Cannot manage scheduled tasks.")
            raise CommandNotFoundError("schtasks")
        logger.debug("WindowsTaskScheduler initialized successfully.")

    def get_task_info(self, task_names: List[str]) -> List[Dict[str, str]]:
        """
        Retrieves details for specified Windows scheduled tasks.
        """
        if not isinstance(task_names, list):
            raise TypeError("Input 'task_names' must be a list.")
        if not task_names:
            return []

        logger.debug(f"Querying Windows Task Scheduler for tasks: {task_names}")
        task_info_list: List[Dict[str, str]] = []

        for task_name in task_names:
            if not task_name or not isinstance(task_name, str):
                logger.warning(f"Skipping invalid task name provided: {task_name}")
                continue
            try:
                result = subprocess.run(
                    [self.schtasks_cmd, "/Query", "/TN", task_name, "/XML"],
                    capture_output=True,
                    text=True,
                    check=True,
                    encoding="utf-8",
                    errors="replace",
                )
                xml_output = result.stdout
                if xml_output.startswith("\ufeff"):
                    xml_output = xml_output[1:]
                root = ET.fromstring(xml_output)

                arguments_element = root.find(f".//{self.XML_NAMESPACE}Arguments")
                command = ""
                if arguments_element is not None and arguments_element.text:
                    if arguments_text := arguments_element.text.strip():
                        command = arguments_text.split(maxsplit=1)[0]

                schedule = self._get_schedule_string(root)
                task_info_list.append(
                    {"task_name": task_name, "command": command, "schedule": schedule}
                )

            except subprocess.CalledProcessError as e:
                stderr_lower = (e.stderr or "").lower()
                if (
                    "error: the system cannot find the file specified." in stderr_lower
                    or (
                        "error: the specified task name" in stderr_lower
                        and "does not exist" in stderr_lower
                    )
                ):
                    logger.debug(f"Task '{task_name}' not found in Task Scheduler.")
                else:
                    logger.error(
                        f"Error running 'schtasks /Query' for task '{task_name}': {e.stderr}",
                        exc_info=True,
                    )
            except ET.ParseError as e:
                logger.error(
                    f"Error parsing XML output for task '{task_name}': {e}",
                    exc_info=True,
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error processing task '{task_name}': {e}",
                    exc_info=True,
                )

        return task_info_list

    def _get_schedule_string(self, root: ET.Element) -> str:
        """Extracts and formats a human-readable schedule string from task XML triggers."""
        schedule_parts = []
        triggers_container = root.find(f".//{self.XML_NAMESPACE}Triggers")
        if triggers_container is None:
            return "No Triggers"

        for trigger in triggers_container:
            trigger_tag = trigger.tag.replace(self.XML_NAMESPACE, "")
            part = f"Unknown Trigger Type ({trigger_tag})"

            if trigger_tag == "TimeTrigger":
                start_boundary_el = trigger.find(
                    f".//{self.XML_NAMESPACE}StartBoundary"
                )
                time_str = "Unknown Time"
                if start_boundary_el is not None and start_boundary_el.text:
                    try:
                        time_str = start_boundary_el.text.split("T")[1]
                    except IndexError:
                        pass
                part = f"One Time ({time_str})"

            elif trigger_tag == "CalendarTrigger":
                schedule_by_day = trigger.find(f".//{self.XML_NAMESPACE}ScheduleByDay")
                schedule_by_week = trigger.find(
                    f".//{self.XML_NAMESPACE}ScheduleByWeek"
                )
                schedule_by_month = trigger.find(
                    f".//{self.XML_NAMESPACE}ScheduleByMonth"
                )
                if schedule_by_day is not None:
                    interval = schedule_by_day.find(
                        f".//{self.XML_NAMESPACE}DaysInterval"
                    )
                    part = f"Daily (every {interval.text if interval is not None else '1'} days)"
                elif schedule_by_week is not None:
                    interval = schedule_by_week.find(
                        f".//{self.XML_NAMESPACE}WeeksInterval"
                    )
                    days_el = schedule_by_week.find(
                        f".//{self.XML_NAMESPACE}DaysOfWeek"
                    )
                    days = (
                        [d.tag.replace(self.XML_NAMESPACE, "") for d in days_el]
                        if days_el is not None
                        else []
                    )
                    part = f"Weekly (every {interval.text if interval is not None else '1'} weeks on {', '.join(days)})"
                elif schedule_by_month is not None:
                    part = "Monthly"
                else:
                    part = "CalendarTrigger (Unknown Schedule)"

            elif trigger_tag == "LogonTrigger":
                part = "On Logon"
            elif trigger_tag == "BootTrigger":
                part = "On System Startup"

            schedule_parts.append(part)

        return ", ".join(schedule_parts) if schedule_parts else "No Triggers"

    def get_server_task_names(
        self, server_name: str, config_dir: str
    ) -> List[Tuple[str, str]]:
        """Gets a list of task names and their XML file paths associated with a server."""
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")
        if not config_dir:
            raise MissingArgumentError("Config directory cannot be empty.")

        server_task_dir = os.path.join(config_dir, server_name)
        if not os.path.isdir(server_task_dir):
            return []

        task_files: List[Tuple[str, str]] = []
        try:
            for filename in os.listdir(server_task_dir):
                if filename.lower().endswith(".xml"):
                    file_path = os.path.join(server_task_dir, filename)
                    try:
                        tree = ET.parse(file_path)
                        uri_element = tree.getroot().find(
                            f".//{self.XML_NAMESPACE}RegistrationInfo/{self.XML_NAMESPACE}URI"
                        )
                        if uri_element is not None and uri_element.text:
                            task_name = uri_element.text.strip().lstrip("\\")
                            if task_name:
                                task_files.append((task_name, file_path))
                    except ET.ParseError as e:
                        logger.error(
                            f"Error parsing task XML file '{filename}': {e}. Skipping.",
                            exc_info=True,
                        )
        except OSError as e:
            raise FileOperationError(
                f"Error reading tasks from directory '{server_task_dir}': {e}"
            ) from e
        return task_files

    def create_task_xml(
        self,
        server_name: str,
        command: str,
        command_args: str,
        task_name: str,
        config_dir: str,
        triggers: List[Dict[str, Any]],
    ) -> str:
        """Creates an XML definition file for a Windows scheduled task."""
        if not all([server_name, command, task_name, config_dir]):
            raise MissingArgumentError("Required arguments cannot be empty.")
        if not isinstance(triggers, list):
            raise TypeError("Triggers must be a list.")
        if not EXPATH or not os.path.exists(EXPATH):
            raise AppFileNotFoundError(str(EXPATH), "Main script executable")

        try:
            task = ET.Element(
                "Task", version="1.4", xmlns=self.XML_NAMESPACE.strip("{}")
            )
            # Registration Info
            reg_info = ET.SubElement(task, f"{self.XML_NAMESPACE}RegistrationInfo")
            ET.SubElement(reg_info, f"{self.XML_NAMESPACE}Date").text = (
                datetime.now().isoformat(timespec="seconds")
            )
            ET.SubElement(reg_info, f"{self.XML_NAMESPACE}Author").text = (
                f"{os.getenv('USERDOMAIN', '')}\\{os.getenv('USERNAME', 'UnknownUser')}"
            )
            ET.SubElement(reg_info, f"{self.XML_NAMESPACE}Description").text = (
                f"Scheduled task for Bedrock Server Manager: server '{server_name}', command '{command}'."
            )
            ET.SubElement(reg_info, f"{self.XML_NAMESPACE}URI").text = (
                task_name if task_name.startswith("\\") else f"\\{task_name}"
            )
            # Triggers
            triggers_element = ET.SubElement(task, f"{self.XML_NAMESPACE}Triggers")
            for trigger_data in triggers:
                self._add_trigger(triggers_element, trigger_data)
            # Principal
            principals = ET.SubElement(task, f"{self.XML_NAMESPACE}Principals")
            principal = ET.SubElement(
                principals, f"{self.XML_NAMESPACE}Principal", id="Author"
            )
            ET.SubElement(principal, f"{self.XML_NAMESPACE}UserId").text = os.getenv(
                "USERNAME", "UnknownUser"
            )
            ET.SubElement(principal, f"{self.XML_NAMESPACE}LogonType").text = (
                "InteractiveToken"
            )
            ET.SubElement(principal, f"{self.XML_NAMESPACE}RunLevel").text = (
                "LeastPrivilege"
            )
            # Settings
            settings_el = ET.SubElement(task, f"{self.XML_NAMESPACE}Settings")
            ET.SubElement(
                settings_el, f"{self.XML_NAMESPACE}MultipleInstancesPolicy"
            ).text = "IgnoreNew"
            ET.SubElement(
                settings_el, f"{self.XML_NAMESPACE}DisallowStartIfOnBatteries"
            ).text = "true"
            ET.SubElement(
                settings_el, f"{self.XML_NAMESPACE}StopIfGoingOnBatteries"
            ).text = "true"
            ET.SubElement(
                settings_el, f"{self.XML_NAMESPACE}AllowHardTerminate"
            ).text = "true"
            ET.SubElement(
                settings_el, f"{self.XML_NAMESPACE}StartWhenAvailable"
            ).text = "false"
            ET.SubElement(
                settings_el, f"{self.XML_NAMESPACE}ExecutionTimeLimit"
            ).text = "PT0S"
            ET.SubElement(settings_el, f"{self.XML_NAMESPACE}Priority").text = "7"
            ET.SubElement(settings_el, f"{self.XML_NAMESPACE}Enabled").text = "true"
            # Actions
            actions = ET.SubElement(
                task, f"{self.XML_NAMESPACE}Actions", Context="Author"
            )
            exec_action = ET.SubElement(actions, f"{self.XML_NAMESPACE}Exec")
            ET.SubElement(exec_action, f"{self.XML_NAMESPACE}Command").text = str(
                EXPATH
            )
            ET.SubElement(exec_action, f"{self.XML_NAMESPACE}Arguments").text = (
                f"{command} {command_args}".strip()
            )

            # Save XML
            server_config_dir = os.path.join(config_dir, server_name)
            os.makedirs(server_config_dir, exist_ok=True)
            safe_filename = re.sub(r'[\\/*?:"<>|]', "_", task_name) + ".xml"
            xml_file_path = os.path.join(server_config_dir, safe_filename)

            ET.indent(task, space="  ")
            tree = ET.ElementTree(task)
            tree.write(xml_file_path, encoding="utf-16", xml_declaration=True)
            return xml_file_path
        except Exception as e:
            raise FileOperationError(f"Unexpected error creating task XML: {e}") from e

    def import_task_from_xml(self, xml_file_path: str, task_name: str) -> None:
        """Imports a task definition XML file into Windows Task Scheduler."""
        if not xml_file_path:
            raise MissingArgumentError("XML file path cannot be empty.")
        if not task_name:
            raise MissingArgumentError("Task name cannot be empty.")
        if not os.path.isfile(xml_file_path):
            raise AppFileNotFoundError(xml_file_path, "Task XML file")

        logger.info(f"Importing task '{task_name}' from XML file: {xml_file_path}")
        try:
            subprocess.run(
                [
                    self.schtasks_cmd,
                    "/Create",
                    "/TN",
                    task_name,
                    "/XML",
                    xml_file_path,
                    "/F",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            logger.info(f"Task '{task_name}' imported/updated successfully.")
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            if "access is denied" in stderr.lower():
                raise PermissionsError(
                    f"Access denied importing task '{task_name}'. Try running as Administrator."
                ) from e
            raise SystemError(
                f"Failed to import task '{task_name}'. Error: {stderr}"
            ) from e

    def delete_task(self, task_name: str) -> None:
        """Deletes a scheduled task from Windows Task Scheduler by its name."""
        if not task_name:
            raise MissingArgumentError("Task name cannot be empty.")

        logger.info(f"Attempting to delete scheduled task: '{task_name}'")
        try:
            subprocess.run(
                [self.schtasks_cmd, "/Delete", "/TN", task_name, "/F"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            logger.info(f"Task '{task_name}' deleted successfully.")
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip().lower()
            if (
                "the system cannot find the file specified" in stderr
                or "the specified task name" in stderr
                and "does not exist" in stderr
            ):
                logger.info(f"Task '{task_name}' not found. Presumed already deleted.")
                return
            if "access is denied" in stderr:
                raise PermissionsError(
                    f"Access denied deleting task '{task_name}'. Try running as Administrator."
                ) from e
            raise SystemError(
                f"Failed to delete task '{task_name}'. Error: {e.stderr}"
            ) from e

    def _get_day_element_name(self, day_input: Any) -> str:
        """Converts day input to the Task Scheduler XML element name."""
        day_str = str(day_input).strip().lower()
        mapping = {
            "sun": "Sunday",
            "sunday": "Sunday",
            "7": "Sunday",
            "mon": "Monday",
            "monday": "Monday",
            "1": "Monday",
            "tue": "Tuesday",
            "tuesday": "Tuesday",
            "2": "Tuesday",
            "wed": "Wednesday",
            "wednesday": "Wednesday",
            "3": "Wednesday",
            "thu": "Thursday",
            "thursday": "Thursday",
            "4": "Thursday",
            "fri": "Friday",
            "friday": "Friday",
            "5": "Friday",
            "sat": "Saturday",
            "saturday": "Saturday",
            "6": "Saturday",
        }
        if day_str in mapping:
            return mapping[day_str]
        raise UserInputError(
            f"Invalid day of week: '{day_input}'. Use name, abbreviation, or number 1-7 (Mon-Sun)."
        )

    def _get_month_element_name(self, month_input: Any) -> str:
        """Converts month input to the Task Scheduler XML element name."""
        month_str = str(month_input).strip().lower()
        mapping = {
            "jan": "January",
            "1": "January",
            "feb": "February",
            "2": "February",
            "mar": "March",
            "3": "March",
            "apr": "April",
            "4": "April",
            "may": "May",
            "5": "May",
            "jun": "June",
            "6": "June",
            "jul": "July",
            "7": "July",
            "aug": "August",
            "8": "August",
            "sep": "September",
            "9": "September",
            "oct": "October",
            "10": "October",
            "nov": "November",
            "11": "November",
            "dec": "December",
            "12": "December",
        }
        # Add full month names
        for val in list(mapping.values()):
            mapping[val.lower()] = val
        if month_str in mapping:
            return mapping[month_str]
        raise UserInputError(
            f"Invalid month: '{month_input}'. Use name, abbreviation, or number 1-12."
        )

    def _add_trigger(
        self, triggers_element: ET.Element, trigger_data: Dict[str, Any]
    ) -> None:
        """Adds a specific trigger sub-element to the main <Triggers> XML element."""
        trigger_type = trigger_data.get("type")
        start = trigger_data.get("start")
        if not trigger_type:
            raise UserInputError("Trigger data must include a 'type' key.")
        if not start and trigger_type in ("TimeTrigger", "Daily", "Weekly", "Monthly"):
            raise UserInputError(
                f"Trigger type '{trigger_type}' requires a 'start' boundary (YYYY-MM-DDTHH:MM:SS)."
            )

        if trigger_type == "TimeTrigger":
            trigger = ET.SubElement(
                triggers_element, f"{self.XML_NAMESPACE}TimeTrigger"
            )
            ET.SubElement(trigger, f"{self.XML_NAMESPACE}StartBoundary").text = start
        elif trigger_type in ("Daily", "Weekly", "Monthly"):
            trigger = ET.SubElement(
                triggers_element, f"{self.XML_NAMESPACE}CalendarTrigger"
            )
            ET.SubElement(trigger, f"{self.XML_NAMESPACE}StartBoundary").text = start
            if trigger_type == "Daily":
                schedule = ET.SubElement(trigger, f"{self.XML_NAMESPACE}ScheduleByDay")
                ET.SubElement(schedule, f"{self.XML_NAMESPACE}DaysInterval").text = str(
                    trigger_data.get("interval", 1)
                )
            elif trigger_type == "Weekly":
                days = trigger_data.get("days")
                if not days or not isinstance(days, list):
                    raise UserInputError("Weekly trigger requires a list of 'days'.")
                schedule = ET.SubElement(trigger, f"{self.XML_NAMESPACE}ScheduleByWeek")
                ET.SubElement(schedule, f"{self.XML_NAMESPACE}WeeksInterval").text = (
                    str(trigger_data.get("interval", 1))
                )
                days_of_week = ET.SubElement(
                    schedule, f"{self.XML_NAMESPACE}DaysOfWeek"
                )
                for day in days:
                    ET.SubElement(
                        days_of_week,
                        f"{self.XML_NAMESPACE}{self._get_day_element_name(day)}",
                    )
            elif trigger_type == "Monthly":
                days = trigger_data.get("days")
                months = trigger_data.get("months")
                if not days or not isinstance(days, list):
                    raise UserInputError("Monthly trigger requires a list of 'days'.")
                if not months or not isinstance(months, list):
                    raise UserInputError("Monthly trigger requires a list of 'months'.")
                schedule = ET.SubElement(
                    trigger, f"{self.XML_NAMESPACE}ScheduleByMonth"
                )
                days_of_month = ET.SubElement(
                    schedule, f"{self.XML_NAMESPACE}DaysOfMonth"
                )
                for day in days:
                    ET.SubElement(days_of_month, f"{self.XML_NAMESPACE}Day").text = str(
                        day
                    )
                months_el = ET.SubElement(schedule, f"{self.XML_NAMESPACE}Months")
                for month in months:
                    ET.SubElement(
                        months_el,
                        f"{self.XML_NAMESPACE}{self._get_month_element_name(month)}",
                    )
        else:
            raise UserInputError(f"Unsupported trigger type: {trigger_type}")
        ET.SubElement(trigger, f"{self.XML_NAMESPACE}Enabled").text = "true"


# ------
