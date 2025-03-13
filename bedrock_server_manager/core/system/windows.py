# bedrock-server-manager/bedrock_server_manager/core/system/windows.py
import xml.etree.ElementTree as ET
import os
import subprocess
import logging
import psutil
from datetime import datetime
from bedrock_server_manager.config.settings import EXPATH
from bedrock_server_manager.core.error import (
    TaskError,
    FileOperationError,
    MissingArgumentError,
    ServerStartError,
    ServerNotFoundError,
    ServerStopError,
    InvalidInputError,
)

logger = logging.getLogger("bedrock_server_manager")


def _windows_start_server(server_name, server_dir):
    """Starts the Bedrock server on Windows.

    Args:
        server_name (str): The name of the server.
        server_dir (str): The server directory.

    Raises:
        ServerStartError: If the server fails to start.
        ServerNotFoundError: If the server executable is not found.
    """

    # Write an initial message to the server output file
    output_file = os.path.join(server_dir, "server_output.txt")
    exe_path = os.path.join(server_dir, "bedrock_server.exe")
    if not os.path.exists(exe_path):
        raise ServerNotFoundError(exe_path)

    process = None  # Initialize process

    try:
        # Attempt initial write (with "w").
        with open(output_file, "w") as f:
            f.write("Starting Server\n")
    except OSError:
        logger.warning("Failed to truncate server_output.txt. Continuing...")

    # ALWAYS attempt to open for append, even if the initial write failed.
    try:
        with open(output_file, "a") as f:
            process = subprocess.Popen(
                [exe_path],
                cwd=server_dir,
                stdin=subprocess.PIPE,
                stdout=f,
                stderr=f,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
    except (OSError, Exception) as e:
        logger.warning(
            f"Failed to open for redirection or start process: {e}. Using PIPE fallback."
        )
        try:
            process = subprocess.Popen(
                [exe_path],
                cwd=server_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            raise ServerStartError(f"Failed to start server executable: {e}") from e

    if process is None:  # This should never happen, but it's good practice.
        raise ServerStartError("Failed to start server process.")

    logger.info(f"Server {server_name} started successfully. PID: {process.pid}")
    return process


def _windows_stop_server(server_name, server_dir):
    """Stops the Bedrock server on Windows by terminating its process.

    Args:
        server_name (str): The name of the server.
        server_dir (str): The server directory.

    Raises:
        ServerStopError: If stopping the server fails.
    """

    logger.debug(f"Stopping server {server_name}...")
    try:
        # Iterate over all processes to find the one with the matching server name and cwd
        for proc in psutil.process_iter(["pid", "name", "cwd"]):
            try:
                if (
                    proc.info["name"] == "bedrock_server.exe"
                    and proc.info["cwd"]
                    and server_dir.lower() in proc.info["cwd"].lower()
                ):
                    # Found the matching process, so we can stop it
                    pid = proc.info["pid"]
                    process = psutil.Process(pid)
                    process.kill()  # Forcibly kill the process
                    process.wait(timeout=5)
                    logger.info(f"Server {server_name} was forcefully terminated.")
                    return  # Exit the function after stopping
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass  # Continue if process disappears or access denied

        logger.warning(
            f"Server process not found for {server_name}.  It may already be stopped."
        )

    except Exception as e:
        raise ServerStopError(
            f"Failed to stop server process for {server_name}: {e}"
        ) from e


def get_windows_task_info(task_names):
    """Retrieves information about Windows scheduled tasks.

    Args:
        task_names (list): A list of task names (without paths).

    Returns:
        list: A list of dictionaries. Each dictionary represents a task
              and contains 'task_name', 'command', and 'schedule'.
              Returns an empty list if no tasks are found or on error.
    Raises:
        TypeError: If task_names is not a list.
    """
    if not isinstance(task_names, list):
        raise TypeError("task_names must be a list")

    task_info_list = []
    for task_name in task_names:
        try:
            # Use schtasks to get the XML definition of the task.
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", task_name, "/XML"],
                capture_output=True,
                text=True,
                check=True,
            )
            xml_output = result.stdout

            # Parse the XML
            try:
                root = ET.fromstring(xml_output)
            except ET.ParseError:
                logger.error(f"Error parsing XML for task {task_name}")
                continue  # Skip to the next task

            # Extract arguments and get only the first argument (the command)
            arguments_element = root.find(
                ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}Arguments"
            )
            command = ""
            if arguments_element is not None:
                arguments = arguments_element.text.strip()
                if arguments:
                    command = arguments.split()[
                        0
                    ]  # Get only the first word (the command)

            # Extract and format the schedule
            schedule = _get_schedule_string(root)

            task_info_list.append(
                {"task_name": task_name, "command": command, "schedule": schedule}
            )

        except subprocess.CalledProcessError as e:
            if "ERROR: The system cannot find the file specified." not in (
                e.stderr or ""
            ):
                logger.exception(f"Error querying task {task_name}: {e.stderr}")

        except Exception as e:
            logger.exception(
                f"An unexpected error occurred while getting task info for {task_name}: {e}"
            )

    return task_info_list


def _get_schedule_string(root):
    """Extracts and formats the schedule from the task XML.

    Args:
        root (Element): The root element of the parsed XML.

    Returns:
        str: A human-readable schedule string.
    """
    triggers = root.findall(
        ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}Triggers/*"
    )
    if not triggers:
        return "No Triggers"

    schedule_parts = []
    for trigger in triggers:
        if trigger.tag.endswith("TimeTrigger"):
            start_boundary = trigger.find(
                ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}StartBoundary"
            ).text
            schedule_parts.append(
                f"One Time: {start_boundary.split('T')[1]}"
            )  # Extract time
        elif trigger.tag.endswith("CalendarTrigger"):
            if (
                trigger.find(
                    ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}ScheduleByDay"
                )
                is not None
            ):
                days_interval = trigger.find(
                    ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}DaysInterval"
                ).text
                schedule_parts.append(f"Daily (every {days_interval} days)")
            elif (
                trigger.find(
                    ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}ScheduleByWeek"
                )
                is not None
            ):
                weeks_interval = trigger.find(
                    ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}WeeksInterval"
                ).text
                days_of_week = []
                for day_element in trigger.findall(
                    ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}DaysOfWeek/*"
                ):
                    days_of_week.append(
                        day_element.tag.split("}")[-1]
                    )  # Extract day name
                schedule_parts.append(
                    f"Weekly (every {weeks_interval} weeks on {', '.join(days_of_week)})"
                )
            elif (
                trigger.find(
                    ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}ScheduleByMonth"
                )
                is not None
            ):
                schedule_parts.append("Monthly")  # Simplified
            else:
                schedule_parts.append("CalendarTrigger (Unknown Type)")
        else:
            schedule_parts.append("Unknown Trigger Type")

    return ", ".join(schedule_parts)


def get_server_task_names(server_name, config_dir):
    """Gets a list of task names associated with the server.  Also returns file paths.
    Args:
        server_name: Name of server.
        config_dir: Configuration directory.
    Returns:
        List of tuples:  (task_name, file_path) or empty list if none found, or None on error
    Raises:
        TaskError: If there is an error reading the tasks.
    """
    task_dir = os.path.join(config_dir, server_name)
    if not os.path.exists(task_dir):
        return []

    task_files = []
    try:
        for filename in os.listdir(task_dir):
            if filename.endswith(".xml"):
                file_path = os.path.join(task_dir, filename)
                # Extract task name
                try:
                    tree = ET.parse(file_path)
                    root = tree.getroot()
                    reg_info = root.find(
                        ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}RegistrationInfo"
                    )
                    if reg_info is not None:
                        uri_element = reg_info.find(
                            "{http://schemas.microsoft.com/windows/2004/02/mit/task}URI"
                        )
                        if uri_element is not None:
                            task_name = uri_element.text
                            # Task names from XML start with a '\', remove it:
                            if task_name.startswith("\\"):
                                task_name = task_name[1:]
                            task_files.append((task_name, file_path))
                except ET.ParseError:
                    logger.error(f"Error parsing XML file {filename}.  Skipping.")
                    continue

    except Exception as e:
        raise TaskError(f"Error reading tasks from {task_dir}: {e}") from e

    return task_files


def create_windows_task_xml(
    server_name, command, command_args, task_name, config_dir, triggers
):
    """Creates the XML file for a Windows scheduled task.

    Args:
        server_name (str): The name of the server.
        command (str): The command to run (e.g., "start-server").
        command_args (str): Additional command-line arguments.
        task_name (str): The name of the task (for Task Scheduler).
        config_dir (str): The configuration directory.
        triggers (list): A list of trigger dictionaries, as created by
            get_trigger_details.

    Returns:
        str: The path to the created XML file.

    Raises:
        TaskError: If there's an error creating the XML or writing the file.
    """
    task = ET.Element("Task", version="1.2")
    task.set("xmlns", "http://schemas.microsoft.com/windows/2004/02/mit/task")

    reg_info = ET.SubElement(task, "RegistrationInfo")
    ET.SubElement(reg_info, "Date").text = datetime.now().isoformat()
    ET.SubElement(reg_info, "Author").text = (
        f"{os.getenv('USERDOMAIN')}\\{os.getenv('USERNAME')}"
    )
    ET.SubElement(reg_info, "URI").text = task_name

    triggers_element = ET.SubElement(task, "Triggers")
    for trigger_data in triggers:
        add_trigger(triggers_element, trigger_data)

    principals = ET.SubElement(task, "Principals")
    principal = ET.SubElement(principals, "Principal", id="Author")
    try:
        sid = (
            subprocess.check_output(["whoami", "/user", "/fo", "csv"], text=True)
            .strip()
            .splitlines()[-1]
            .split(",")[-1]
            .strip('"')
        )
        ET.SubElement(principal, "UserId").text = sid
    except (subprocess.CalledProcessError, IndexError, OSError):
        # Fallback to username if whoami fails or output is unexpected
        ET.SubElement(principal, "UserId").text = os.getenv("USERNAME")
    ET.SubElement(principal, "LogonType").text = "InteractiveToken"
    ET.SubElement(principal, "RunLevel").text = "LeastPrivilege"

    settings = ET.SubElement(task, "Settings")
    ET.SubElement(settings, "MultipleInstancesPolicy").text = "IgnoreNew"
    ET.SubElement(settings, "DisallowStartIfOnBatteries").text = "true"
    ET.SubElement(settings, "StopIfGoingOnBatteries").text = "true"
    ET.SubElement(settings, "AllowHardTerminate").text = "true"
    ET.SubElement(settings, "StartWhenAvailable").text = "false"
    ET.SubElement(settings, "RunOnlyIfNetworkAvailable").text = "false"
    idle_settings = ET.SubElement(settings, "IdleSettings")
    ET.SubElement(idle_settings, "StopOnIdleEnd").text = "true"
    ET.SubElement(idle_settings, "RestartOnIdle").text = "false"
    ET.SubElement(settings, "AllowStartOnDemand").text = "true"
    ET.SubElement(settings, "Enabled").text = "true"
    ET.SubElement(settings, "Hidden").text = "false"
    ET.SubElement(settings, "RunOnlyIfIdle").text = "false"
    ET.SubElement(settings, "WakeToRun").text = "false"
    ET.SubElement(settings, "ExecutionTimeLimit").text = "PT72H"
    ET.SubElement(settings, "Priority").text = "7"

    actions = ET.SubElement(task, "Actions", Context="Author")
    exec_action = ET.SubElement(actions, "Exec")
    ET.SubElement(exec_action, "Command").text = f"{EXPATH}"
    ET.SubElement(exec_action, "Arguments").text = f"{command} {command_args}"

    task_dir = os.path.join(config_dir, server_name)
    os.makedirs(task_dir, exist_ok=True)

    xml_file_name = f"{command}.xml"
    xml_file_path = os.path.join(task_dir, xml_file_name)
    try:
        ET.indent(task)
        tree = ET.ElementTree(task)
        tree.write(xml_file_path, encoding="utf-16", xml_declaration=True)
        return xml_file_path
    except Exception as e:
        raise TaskError(f"Error writing XML file: {e}") from e


def import_task_xml(xml_file_path, task_name):
    """Imports the XML file into the Windows Task Scheduler.

    Args:
        xml_file_path (str): The path to the XML file.
        task_name (str): The name of the task (for Task Scheduler).

    Raises:
        FileOperationError: If the XML file is not found.
        MissingArgumentError: If the task name is empty.
        TaskError: If importing the task fails.
    """
    if not task_name:
        raise MissingArgumentError("import_task_xml: Task name is empty.")
    if not xml_file_path or not os.path.exists(xml_file_path):
        raise FileOperationError(
            f"import_task_xml: XML file not found: {xml_file_path}"
        )

    try:
        result = subprocess.run(
            ["schtasks", "/Create", "/TN", task_name, "/XML", xml_file_path, "/F"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.debug(f"Task '{task_name}' imported successfully.")
        logger.debug(result.stdout)
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.strip() if e.stderr else ""
        stdout_output = e.stdout.strip() if e.stdout else ""
        raise TaskError(
            f"Failed to import task '{task_name}'. Return Code: {e.returncode}.  Error: {error_output}. Output: {stdout_output}"
        ) from e
    except Exception as e:
        raise TaskError(f"An unexpected error occurred while importing: {e}") from e


def _get_day_element_name(day_input):
    """Converts user input for a day of the week to the correct XML element name.

    Args:
        day_input (str or int): User input for the day (e.g., "Mon", "monday", 1, "1").

    Returns:
        str: The correct XML element name (e.g., "Monday").

    Raises:
        TaskError: If the input is invalid.
    """
    days_mapping = {
        "sun": "Sunday",
        "sunday": "Sunday",
        "mon": "Monday",
        "monday": "Monday",
        "tue": "Tuesday",
        "tuesday": "Tuesday",
        "wed": "Wednesday",
        "wednesday": "Wednesday",
        "thu": "Thursday",
        "thursday": "Thursday",
        "fri": "Friday",
        "friday": "Friday",
        "sat": "Saturday",
        "saturday": "Saturday",
    }
    days_by_number = {
        1: "Monday",
        2: "Tuesday",
        3: "Wednesday",
        4: "Thursday",
        5: "Friday",
        6: "Saturday",
        7: "Sunday",
    }

    # Normalize input
    day_input_str = str(day_input).strip().lower()

    # Check numeric input
    try:
        day_number = int(day_input_str)
        if 1 <= day_number <= 7:
            return days_by_number[day_number]
        else:
            raise TaskError(f"Invalid day of week input: {day_input}")
    except ValueError:
        pass

    # Check string input for full or abbreviated day names
    if day_input_str in days_mapping:
        return days_mapping[day_input_str]

    raise TaskError(f"Invalid day of week input: {day_input}")


def _get_month_element_name(month_input):
    """Converts user input for a month to the correct XML element name.

    Args:
        month_input (str or int): User input for the month (e.g., "Jan", "january", 1, "1").

    Returns:
        str: The correct XML element name (e.g., "January").

    Raises:
        TaskError: If the month input is invalid.
    """
    months_mapping = {
        "jan": "January",
        "january": "January",
        "feb": "February",
        "february": "February",
        "mar": "March",
        "march": "March",
        "apr": "April",
        "april": "April",
        "may": "May",
        "jun": "June",
        "june": "June",
        "jul": "July",
        "july": "July",
        "aug": "August",
        "august": "August",
        "sep": "September",
        "september": "September",
        "oct": "October",
        "october": "October",
        "nov": "November",
        "november": "November",
        "dec": "December",
        "december": "December",
    }

    months_by_number = {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December",
    }

    # Normalize input
    month_input_str = str(month_input).strip().lower()

    # Check numeric input first
    try:
        month_number = int(month_input_str)
        if 1 <= month_number <= 12:
            return months_by_number[month_number]
        else:
            raise TaskError(f"Invalid month input: {month_input}")
    except ValueError:
        pass

    # Check for exact string match
    if month_input_str in months_mapping:
        return months_mapping[month_input_str]

    # Invalid input
    raise TaskError(f"Invalid month input: {month_input}")


def add_trigger(triggers_element, trigger_data):
    """Adds a trigger to the triggers element based on the provided data."""

    trigger_type = trigger_data["type"]

    if trigger_type == "TimeTrigger":
        time_trigger = ET.SubElement(triggers_element, "TimeTrigger")
        ET.SubElement(time_trigger, "StartBoundary").text = trigger_data["start"]
        ET.SubElement(time_trigger, "Enabled").text = "true"

    elif trigger_type == "Daily":
        calendar_trigger = ET.SubElement(triggers_element, "CalendarTrigger")
        ET.SubElement(calendar_trigger, "StartBoundary").text = trigger_data["start"]
        ET.SubElement(calendar_trigger, "Enabled").text = "true"
        schedule_by_day = ET.SubElement(calendar_trigger, "ScheduleByDay")
        ET.SubElement(schedule_by_day, "DaysInterval").text = str(
            trigger_data["interval"]
        )

    elif trigger_type == "Weekly":
        calendar_trigger = ET.SubElement(triggers_element, "CalendarTrigger")
        ET.SubElement(calendar_trigger, "StartBoundary").text = trigger_data["start"]
        ET.SubElement(calendar_trigger, "Enabled").text = "true"
        schedule_by_week = ET.SubElement(calendar_trigger, "ScheduleByWeek")
        days_of_week_element = ET.SubElement(schedule_by_week, "DaysOfWeek")
        for day in trigger_data["days"]:
            day_element_name = _get_day_element_name(day)
            if day_element_name:
                ET.SubElement(days_of_week_element, day_element_name)
        ET.SubElement(schedule_by_week, "WeeksInterval").text = str(
            trigger_data["interval"]
        )

    elif trigger_type == "Monthly":
        calendar_trigger = ET.SubElement(triggers_element, "CalendarTrigger")
        ET.SubElement(calendar_trigger, "StartBoundary").text = trigger_data["start"]
        ET.SubElement(calendar_trigger, "Enabled").text = "true"
        schedule_by_month = ET.SubElement(calendar_trigger, "ScheduleByMonth")
        days_of_month_element = ET.SubElement(schedule_by_month, "DaysOfMonth")
        for day in trigger_data["days"]:
            try:
                day_int = int(day)
                if 1 <= day_int <= 31:
                    ET.SubElement(days_of_month_element, "Day").text = str(day_int)
            except ValueError:
                pass  # Ignore invalid days
        months_element = ET.SubElement(schedule_by_month, "Months")
        for month in trigger_data["months"]:
            month_element_name = _get_month_element_name(month)
            if month_element_name:
                ET.SubElement(months_element, month_element_name)
    else:
        raise InvalidInputError(f"Unknown trigger type: {trigger_type}")


def delete_task(task_name):
    """Deletes a task by its name using schtasks.

    Args:
        task_name (str): The name of the task to delete.

    Raises:
        MissingArgumentError: If task_name is empty.
        TaskError: If deleting the task fails.
    """
    if not task_name:
        raise MissingArgumentError("delete_task: task_name is empty.")

    try:
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.debug(f"Task '{task_name}' deleted successfully.")
        logger.debug(result.stdout)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""  # Handle None stderr
        if "does not exist" in stderr.lower():
            logger.debug(f"Task '{task_name}' not found.")
            return  # Task not found - not an error
        raise TaskError(
            f"Failed to delete task '{task_name}'. "
            f"Return Code: {e.returncode}. Error: {stderr.strip()}. "
            f"Output: {e.stdout.strip() if e.stdout else ''}"
        ) from e
    except Exception as e:
        raise TaskError(f"An unexpected error occurred while deleting task: {e}") from e
