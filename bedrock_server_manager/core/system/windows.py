# bedrock-server-manager/bedrock_server_manager/core/system/windows.py
"""
Provides Windows-specific implementations for system interactions.

Includes functions for starting and stopping the Bedrock server process directly,
and for managing Windows Scheduled Tasks (creating, deleting, querying).
Relies on `psutil` for process management and `schtasks` command-line utility
and `xml.etree.ElementTree` for task scheduling. Requires `pywin32` for
some operations like process start flags.
"""

import xml.etree.ElementTree as ET
import os
import subprocess
import logging
import shutil
import re
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any

# Third-party imports
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Local imports
from bedrock_server_manager.config.settings import EXPATH
from bedrock_server_manager.error import (
    TaskError,
    FileOperationError,
    MissingArgumentError,
    ServerStartError,
    ServerNotFoundError,
    ServerStopError,
    InvalidInputError,
    CommandNotFoundError,
)

logger = logging.getLogger("bedrock_server_manager")

# --- Constants ---
XML_NAMESPACE = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"


def _windows_start_server(
    server_name: str, server_dir: str
) -> Optional[subprocess.Popen]:
    """
    Starts the Bedrock server process on Windows.

    Attempts to redirect stdout/stderr to 'server_output.txt'. If that fails,
    falls back to using PIPEs (less ideal for long-running logs).

    Args:
        server_name: The name of the server (used for logging).
        server_dir: The full path to the server's installation directory.

    Returns:
        The `subprocess.Popen` object representing the started server process,
        or None if startup failed in a way that didn't raise an exception
        (should ideally always raise or return Popen).

    Raises:
        MissingArgumentError: If `server_name` or `server_dir` is empty.
        ServerNotFoundError: If 'bedrock_server.exe' is not found in `server_dir`.
        ServerStartError: If the server process fails to start via `subprocess.Popen`.
        FileOperationError: If directory operations fail.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")

    logger.info(f"Attempting to start server '{server_name}' on Windows...")
    logger.debug(f"Server directory: {server_dir}")

    output_file = os.path.join(server_dir, "server_output.txt")
    exe_path = os.path.join(server_dir, "bedrock_server.exe")

    if not os.path.isfile(exe_path):
        error_msg = f"Server executable not found at: {exe_path}"
        logger.error(error_msg)
        raise ServerNotFoundError(error_msg)

    process: Optional[subprocess.Popen] = None
    stdout_handle = None
    stderr_handle = None

    # Try redirecting output to file first
    try:
        # Open file in append mode, create if not exists
        log_file_handle = open(output_file, "ab")  # Use binary append mode
        stdout_handle = log_file_handle
        stderr_handle = log_file_handle
        logger.debug(f"Opened '{output_file}' for server output redirection.")

        # Try starting with redirection to the file handle
        process = subprocess.Popen(
            [exe_path],
            cwd=server_dir,
            stdin=subprocess.PIPE,
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=subprocess.CREATE_NO_WINDOW,  # Prevent console window popup
            close_fds=True,
        )
        logger.info(
            f"Server '{server_name}' process started (PID: {process.pid}). Output redirected to '{output_file}'."
        )

    except (OSError, Exception) as e_redir:
        logger.warning(
            f"Failed to start server with output redirection to file '{output_file}': {e_redir}. Attempting PIPE fallback.",
            exc_info=True,
        )
        # Clean up file handle if it was opened but Popen failed
        if log_file_handle:
            try:
                log_file_handle.close()
            except Exception:
                pass

        # Fallback to using PIPEs (output will be lost unless read by manager)
        try:
            process = subprocess.Popen(
                [exe_path],
                cwd=server_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,  # Use PIPE
                stderr=subprocess.PIPE,  # Use PIPE
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True,
            )
            logger.warning(
                f"Server '{server_name}' process started (PID: {process.pid}) with output redirected to PIPEs. Logs may be lost."
            )
        except (OSError, Exception) as e_pipe:
            logger.error(
                f"Failed to start server executable even with PIPE fallback: {e_pipe}",
                exc_info=True,
            )
            raise ServerStartError(
                f"Failed to start server executable '{exe_path}': {e_pipe}"
            ) from e_pipe

    # Should have a process by now, otherwise ServerStartError was raised
    if process is None:
        # This path is unlikely but defensively raise error
        logger.error(
            "Server process is None after start attempts, indicating critical failure."
        )
        raise ServerStartError(
            "Failed to obtain server process handle after start attempts."
        )

    return process


def _windows_stop_server(server_name: str, server_dir: str) -> None:
    """
    Stops the Bedrock server on Windows by finding and terminating its process.

    Uses `psutil` to find the process based on executable name and working directory.

    Args:
        server_name: The name of the server (used for logging).
        server_dir: The full path to the server's installation directory, used to
                    identify the correct process.

    Raises:
        MissingArgumentError: If `server_name` or `server_dir` is empty.
        ServerStopError: If `psutil` is unavailable, or if finding/terminating
                         the process fails unexpectedly.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")

    if not PSUTIL_AVAILABLE:
        error_msg = "Cannot stop server on Windows: 'psutil' module is required but not installed."
        logger.error(error_msg)
        raise ServerStopError(error_msg)

    logger.info(f"Attempting to stop server '{server_name}' process on Windows...")
    logger.debug(f"Searching for 'bedrock_server.exe' with CWD matching '{server_dir}'")

    process_found = False
    try:
        # Normalize server_dir path for reliable comparison
        normalized_server_dir = os.path.normpath(server_dir).lower()

        for proc in psutil.process_iter(["pid", "name", "cwd"]):
            try:
                proc_info = proc.info
                # Check name, status, and normalized CWD
                if (
                    proc_info["name"] == "bedrock_server.exe"
                    and proc_info["cwd"]
                    and os.path.normpath(proc_info["cwd"]).lower()
                    == normalized_server_dir
                ):

                    pid_to_terminate = proc_info["pid"]
                    logger.info(
                        f"Found matching server process for '{server_name}' with PID: {pid_to_terminate}. Attempting termination..."
                    )
                    process_to_terminate = psutil.Process(pid_to_terminate)
                    process_to_terminate.kill()  # Send SIGKILL equivalent
                    process_found = True
                    logger.debug(f"Sent kill signal to process {pid_to_terminate}.")

                    # Wait briefly for process to terminate
                    try:
                        process_to_terminate.wait(timeout=5)
                        logger.info(
                            f"Server process {pid_to_terminate} terminated successfully."
                        )
                    except psutil.TimeoutExpired:
                        logger.warning(
                            f"Process {pid_to_terminate} did not terminate within timeout after kill signal."
                        )
                        # Process might be stuck, further action might be needed manually
                    # Stop searching once found and termination attempted
                    break

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process might have disappeared between iteration and access, or permissions issue
                logger.debug(
                    f"Access denied or process disappeared while checking PID {proc.pid}. Skipping."
                )
                continue  # Continue searching
            except Exception as inner_e:
                # Catch unexpected errors during process info access
                logger.warning(
                    f"Unexpected error accessing info for PID {proc.pid}: {inner_e}",
                    exc_info=True,
                )
                continue

        if not process_found:
            logger.info(
                f"No running server process found matching name '{server_name}' and directory '{server_dir}'. Server might already be stopped."
            )

    except Exception as e:
        logger.error(
            f"An unexpected error occurred while trying to stop server '{server_name}': {e}",
            exc_info=True,
        )
        raise ServerStopError(
            f"Unexpected error stopping server '{server_name}': {e}"
        ) from e


# --- Windows Task Scheduler Functions ---


def get_windows_task_info(task_names: List[str]) -> List[Dict[str, str]]:
    """
    Retrieves details (command, schedule) for specified Windows scheduled tasks.

    Uses `schtasks /Query /XML` and parses the XML output.

    Args:
        task_names: A list of exact task names (including any folder path within Task Scheduler,
                    e.g., "MyTasks\\MyServerTask").

    Returns:
        A list of dictionaries, one for each successfully queried task. Each dict contains:
            'task_name' (str): The name of the task.
            'command' (str): The primary command executed by the task (first part of Arguments).
            'schedule' (str): A human-readable summary of the task's triggers.
        Returns an empty list if no tasks are found or errors occur during query/parsing.

    Raises:
        TypeError: If `task_names` is not a list.
        CommandNotFoundError: If the 'schtasks' command is not found.
    """
    if not isinstance(task_names, list):
        raise TypeError("Input 'task_names' must be a list.")
    if not task_names:
        return []  # Return empty list if input list is empty

    schtasks_cmd = shutil.which("schtasks")
    if not schtasks_cmd:
        logger.error("'schtasks' command not found. Cannot query Windows tasks.")
        raise CommandNotFoundError("schtasks")

    logger.debug(f"Querying Windows Task Scheduler for tasks: {task_names}")
    task_info_list: List[Dict[str, str]] = []

    for task_name in task_names:
        if not task_name or not isinstance(task_name, str):
            logger.warning(f"Skipping invalid task name provided: {task_name}")
            continue

        logger.debug(f"Querying task: '{task_name}'")
        try:
            # Query task details as XML
            result = subprocess.run(
                [schtasks_cmd, "/Query", "/TN", task_name, "/XML"],
                capture_output=True,
                text=True,  # Decode output as text
                check=True,  # Raise exception for non-zero exit code
                encoding="utf-8",  # Specify encoding if needed, often utf-8 or locale default
                errors="replace",  # Handle potential decoding errors
            )
            xml_output = result.stdout
            logger.debug(f"Successfully queried XML for task '{task_name}'.")

            # Parse the XML output
            try:
                # Remove potential BOM (Byte Order Mark) before parsing
                if xml_output.startswith("\ufeff"):
                    xml_output = xml_output[1:]
                root = ET.fromstring(xml_output)
            except ET.ParseError as parse_err:
                logger.error(
                    f"Error parsing XML output for task '{task_name}': {parse_err}",
                    exc_info=True,
                )
                logger.debug(
                    f"XML content that failed parsing:\n{xml_output[:500]}..."
                )  # Log snippet
                continue  # Skip this task

            # Extract Command (first argument)
            command = ""
            try:
                # Namespace is important for find
                arguments_element = root.find(f".//{XML_NAMESPACE}Arguments")
                if arguments_element is not None and arguments_element.text:
                    arguments_text = arguments_element.text.strip()
                    if arguments_text:
                        # Extract the first "word" - simplistic, might need refinement
                        command = arguments_text.split(maxsplit=1)[0]
            except Exception as arg_err:
                logger.warning(
                    f"Could not extract command/arguments for task '{task_name}': {arg_err}",
                    exc_info=True,
                )

            # Extract Schedule String
            schedule = _get_schedule_string(root)  # Use helper function

            task_info_list.append(
                {"task_name": task_name, "command": command, "schedule": schedule}
            )
            logger.debug(
                f"Extracted info for '{task_name}': Command='{command}', Schedule='{schedule}'"
            )

        except subprocess.CalledProcessError as e:
            # Handle specific error: Task not found
            stderr_lower = (e.stderr or "").lower()
            if (
                "error: the system cannot find the file specified." in stderr_lower
                or "error: the specified task name" in stderr_lower
                and "does not exist" in stderr_lower
            ):
                logger.debug(f"Task '{task_name}' not found in Task Scheduler.")
            else:
                # Log other schtasks errors
                logger.error(
                    f"Error running 'schtasks /Query' for task '{task_name}': {e.stderr}",
                    exc_info=True,
                )
        except FileNotFoundError:
            # Should be caught by shutil.which, but safeguard
            logger.error("'schtasks' command not found unexpectedly during query.")
            raise CommandNotFoundError("schtasks")  # Re-raise if it happens here
        except Exception as e:
            # Catch unexpected errors during processing for this task
            logger.error(
                f"Unexpected error processing task '{task_name}': {e}", exc_info=True
            )

    logger.info(
        f"Finished querying tasks. Found info for {len(task_info_list)} task(s)."
    )
    return task_info_list


def _get_schedule_string(root: ET.Element) -> str:
    """
    Extracts and formats a human-readable schedule string from task XML triggers.

    Args:
        root: The root ET.Element of the parsed task XML.

    Returns:
        A comma-separated string describing the triggers (e.g., "Daily", "Weekly on Monday, Friday").
        Returns "No Triggers" if none are found. Returns "Unknown Trigger Type" for unrecognized triggers.
    """
    schedule_parts = []
    try:
        # Find all direct children under the Triggers element
        triggers_container = root.find(f".//{XML_NAMESPACE}Triggers")
        if triggers_container is None:
            return "No Triggers"

        for trigger in triggers_container:
            trigger_tag = trigger.tag.replace(
                XML_NAMESPACE, ""
            )  # Get tag name without namespace

            if trigger_tag == "TimeTrigger":
                start_boundary_el = trigger.find(f".//{XML_NAMESPACE}StartBoundary")
                start_time_str = "Unknown Time"
                if start_boundary_el is not None and start_boundary_el.text:
                    try:
                        # Extract time part (e.g., 14:00:00 from 2023-01-01T14:00:00)
                        start_time_str = start_boundary_el.text.split("T")[1]
                    except IndexError:
                        pass  # Handle unexpected format
                schedule_parts.append(f"One Time ({start_time_str})")

            elif trigger_tag == "CalendarTrigger":  # Covers Daily, Weekly, Monthly
                schedule_str = "Unknown Calendar Trigger"
                # Look for specific schedule types within CalendarTrigger
                schedule_by_day = trigger.find(f".//{XML_NAMESPACE}ScheduleByDay")
                schedule_by_week = trigger.find(f".//{XML_NAMESPACE}ScheduleByWeek")
                schedule_by_month = trigger.find(f".//{XML_NAMESPACE}ScheduleByMonth")

                if schedule_by_day is not None:
                    days_interval_el = schedule_by_day.find(
                        f".//{XML_NAMESPACE}DaysInterval"
                    )
                    interval = (
                        days_interval_el.text if days_interval_el is not None else "1"
                    )
                    schedule_str = f"Daily (every {interval} days)"
                elif schedule_by_week is not None:
                    weeks_interval_el = schedule_by_week.find(
                        f".//{XML_NAMESPACE}WeeksInterval"
                    )
                    interval = (
                        weeks_interval_el.text if weeks_interval_el is not None else "1"
                    )
                    days_elements = schedule_by_week.find(
                        f".//{XML_NAMESPACE}DaysOfWeek"
                    )
                    days_list = (
                        [day.tag.replace(XML_NAMESPACE, "") for day in days_elements]
                        if days_elements is not None
                        else []
                    )
                    days_str = ", ".join(days_list) if days_list else "Unknown Days"
                    schedule_str = f"Weekly (every {interval} weeks on {days_str})"
                elif schedule_by_month is not None:
                    # Simplified for now - could parse DaysOfMonth/Months if needed
                    schedule_str = "Monthly"
                else:
                    # Unknown type within CalendarTrigger
                    schedule_str = "CalendarTrigger (Unknown Schedule)"
                schedule_parts.append(schedule_str)

            elif trigger_tag == "LogonTrigger":
                schedule_parts.append("On Logon")
            elif trigger_tag == "BootTrigger":
                schedule_parts.append("On System Startup")
            # Add other common trigger types if needed (e.g., RegistrationTrigger, EventTrigger)
            else:
                schedule_parts.append(f"Unknown Trigger Type ({trigger_tag})")

    except Exception as e:
        logger.warning(f"Error parsing triggers from task XML: {e}", exc_info=True)
        return "Error Parsing Triggers"

    return ", ".join(schedule_parts) if schedule_parts else "No Triggers"


def get_server_task_names(server_name: str, config_dir: str) -> List[Tuple[str, str]]:
    """
    Gets a list of task names and their XML file paths associated with a specific server.

    Scans the server's configuration directory for .xml files and extracts the task name
    (URI) from within each XML.

    Args:
        server_name: The name of the server.
        config_dir: The base configuration directory containing server-specific subfolders.

    Returns:
        A list of tuples, where each tuple is (task_name, xml_file_path).
        Returns an empty list if the server's config directory doesn't exist or contains no valid task XMLs.

    Raises:
        MissingArgumentError: If `server_name` or `config_dir` is empty.
        TaskError: If there's an OS error reading the directory.
        # ET.ParseError might occur but is logged and skipped.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not config_dir:
        raise MissingArgumentError("Config directory cannot be empty.")

    server_task_dir = os.path.join(config_dir, server_name)
    logger.debug(
        f"Scanning for task XML files for server '{server_name}' in directory: {server_task_dir}"
    )

    if not os.path.isdir(server_task_dir):
        logger.debug(
            f"Server config directory does not exist: {server_task_dir}. No tasks found."
        )
        return []

    task_files: List[Tuple[str, str]] = []
    try:
        for filename in os.listdir(server_task_dir):
            if filename.lower().endswith(".xml"):
                file_path = os.path.join(server_task_dir, filename)
                logger.debug(f"Found potential task XML file: {filename}")
                try:
                    tree = ET.parse(file_path)
                    root = tree.getroot()
                    # Find the URI element within RegistrationInfo
                    uri_element = root.find(
                        f".//{XML_NAMESPACE}RegistrationInfo/{XML_NAMESPACE}URI"
                    )
                    if uri_element is not None and uri_element.text:
                        task_name = uri_element.text.strip()
                        # Task names in XML often start with '\', remove it for consistency
                        if task_name.startswith("\\"):
                            task_name = task_name[1:]
                        if task_name:  # Ensure task name is not empty after stripping
                            logger.debug(
                                f"Extracted task name '{task_name}' from file '{filename}'."
                            )
                            task_files.append((task_name, file_path))
                        else:
                            logger.warning(
                                f"Found empty task name (URI) in XML file '{filename}'. Skipping."
                            )
                    else:
                        logger.warning(
                            f"Could not find task name (URI) in XML file '{filename}'. Skipping."
                        )

                except ET.ParseError as parse_err:
                    logger.error(
                        f"Error parsing task XML file '{filename}': {parse_err}. Skipping.",
                        exc_info=True,
                    )
                except Exception as e:  # Catch other unexpected errors during parsing
                    logger.error(
                        f"Unexpected error processing task XML file '{filename}': {e}. Skipping.",
                        exc_info=True,
                    )

    except OSError as e:
        logger.error(
            f"Error listing files in task directory '{server_task_dir}': {e}",
            exc_info=True,
        )
        raise TaskError(
            f"Error reading tasks from directory '{server_task_dir}': {e}"
        ) from e

    logger.info(
        f"Found {len(task_files)} task(s) associated with server '{server_name}'."
    )
    return task_files


def create_windows_task_xml(
    server_name: str,
    command: str,
    command_args: str,
    task_name: str,
    config_dir: str,
    triggers: List[Dict[str, Any]],
) -> str:
    """
    Creates an XML definition file for a Windows scheduled task.

    Args:
        server_name: The name of the server (used for storing the XML).
        command: The command to be run by the task (e.g., "start-server", "backup-all").
                 This will be passed as the first argument to the main script (EXPATH).
        command_args: Additional arguments to pass to the main script (e.g., "--server-name MyServer").
        task_name: The desired name for the task in Task Scheduler (e.g., "BedrockManager\\MyServer Backup").
        config_dir: The base configuration directory where the XML file will be saved
                    (within a server-specific subfolder).
        triggers: A list of trigger dictionaries defining when the task should run.
                  Each dictionary should match the structure expected by `add_trigger`.

    Returns:
        The full path to the generated XML file.

    Raises:
        MissingArgumentError: If required arguments are empty.
        TaskError: If creating the XML structure fails or writing the file fails.
        FileOperationError: If `EXPATH` setting is missing or invalid.
    """
    # --- Validate Arguments ---
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not command:
        raise MissingArgumentError("Command cannot be empty.")
    # command_args can potentially be empty
    if not task_name:
        raise MissingArgumentError("Task name cannot be empty.")
    if not config_dir:
        raise MissingArgumentError("Config directory cannot be empty.")
    if not isinstance(triggers, list):
        raise TypeError("Triggers must be a list.")
    if not EXPATH or not os.path.exists(EXPATH):
        error_msg = f"Main script executable path (EXPATH) is not configured or does not exist: {EXPATH}"
        logger.error(error_msg)
        raise FileOperationError(error_msg)

    logger.info(f"Creating Windows Task XML definition for task '{task_name}'...")
    logger.debug(
        f"Server: {server_name}, Command: {command}, Args: {command_args}, Triggers: {triggers}"
    )

    try:
        # --- Build XML Structure ---
        task = ET.Element(
            "Task", version="1.4"
        )  # Use 1.4 for broader compatibility? 1.2 is common too.
        task.set("xmlns", "http://schemas.microsoft.com/windows/2004/02/mit/task")

        # Registration Info
        reg_info = ET.SubElement(task, f"{XML_NAMESPACE}RegistrationInfo")
        ET.SubElement(reg_info, f"{XML_NAMESPACE}Date").text = datetime.now().isoformat(
            timespec="seconds"
        )  # Format for Task Scheduler
        author = (
            f"{os.getenv('USERDOMAIN', '')}\\{os.getenv('USERNAME', 'UnknownUser')}"
        )
        ET.SubElement(reg_info, f"{XML_NAMESPACE}Author").text = author
        ET.SubElement(reg_info, f"{XML_NAMESPACE}Description").text = (
            f"Scheduled task for Bedrock Server Manager: server '{server_name}', command '{command}'."
        )
        # URI must start with \ according to schema/examples
        uri_task_name = task_name if task_name.startswith("\\") else f"\\{task_name}"
        ET.SubElement(reg_info, f"{XML_NAMESPACE}URI").text = uri_task_name

        # Triggers
        triggers_element = ET.SubElement(task, f"{XML_NAMESPACE}Triggers")
        if not triggers:
            logger.warning(
                "No triggers provided for task. Task will only be runnable on demand."
            )
        else:
            for trigger_data in triggers:
                add_trigger(triggers_element, trigger_data)  # Use helper

        # Principals (Run As)
        principals = ET.SubElement(task, f"{XML_NAMESPACE}Principals")
        principal = ET.SubElement(principals, f"{XML_NAMESPACE}Principal", id="Author")
        try:
            # Attempt to get SID for robustness
            whoami_cmd = shutil.which("whoami")
            if whoami_cmd:
                sid_result = subprocess.run(
                    [whoami_cmd, "/user", "/fo", "csv", "/nh"],
                    capture_output=True,
                    text=True,
                    check=True,
                    encoding="utf-8",
                    errors="replace",
                )
                # Output is typically '"User","SID"'
                parts = sid_result.stdout.strip().split(",")
                if len(parts) == 2:
                    sid = parts[1].strip().strip('"')
                    ET.SubElement(principal, f"{XML_NAMESPACE}UserId").text = sid
                    logger.debug(f"Using current user SID for task principal: {sid}")
                else:
                    raise ValueError("Unexpected output format from whoami.")
            else:
                raise FileNotFoundError("whoami command not found.")
        except (
            subprocess.CalledProcessError,
            IndexError,
            OSError,
            ValueError,
            FileNotFoundError,
        ) as sid_err:
            # Fallback to username if getting SID fails
            username = os.getenv("USERNAME", "UnknownUser")
            ET.SubElement(principal, f"{XML_NAMESPACE}UserId").text = username
            logger.warning(
                f"Failed to get user SID ({sid_err}), falling back to USERNAME: {username}",
                exc_info=True,
            )
        ET.SubElement(principal, f"{XML_NAMESPACE}LogonType").text = (
            "InteractiveToken"  # Run only when user logged on
        )
        ET.SubElement(principal, f"{XML_NAMESPACE}RunLevel").text = (
            "LeastPrivilege"  # Standard user context
        )

        # Settings
        settings_el = ET.SubElement(task, f"{XML_NAMESPACE}Settings")
        ET.SubElement(settings_el, f"{XML_NAMESPACE}MultipleInstancesPolicy").text = (
            "IgnoreNew"  # Don't start if already running
        )
        ET.SubElement(
            settings_el, f"{XML_NAMESPACE}DisallowStartIfOnBatteries"
        ).text = "true"  # Don't start on battery
        ET.SubElement(settings_el, f"{XML_NAMESPACE}StopIfGoingOnBatteries").text = (
            "true"  # Stop if switching to battery
        )
        ET.SubElement(settings_el, f"{XML_NAMESPACE}AllowHardTerminate").text = (
            "true"  # Allow force kill if stop fails
        )
        ET.SubElement(settings_el, f"{XML_NAMESPACE}StartWhenAvailable").text = (
            "false"  # Don't run missed schedules immediately
        )
        ET.SubElement(settings_el, f"{XML_NAMESPACE}RunOnlyIfNetworkAvailable").text = (
            "false"  # Usually not needed for local server mgmt
        )
        idle_settings = ET.SubElement(settings_el, f"{XML_NAMESPACE}IdleSettings")
        ET.SubElement(idle_settings, f"{XML_NAMESPACE}StopOnIdleEnd").text = "true"
        ET.SubElement(idle_settings, f"{XML_NAMESPACE}RestartOnIdle").text = "false"
        ET.SubElement(settings_el, f"{XML_NAMESPACE}AllowStartOnDemand").text = (
            "true"  # Allow manual run
        )
        ET.SubElement(settings_el, f"{XML_NAMESPACE}Enabled").text = (
            "true"  # Task is enabled by default
        )
        ET.SubElement(settings_el, f"{XML_NAMESPACE}Hidden").text = (
            "false"  # Task is visible in UI
        )
        ET.SubElement(settings_el, f"{XML_NAMESPACE}RunOnlyIfIdle").text = (
            "false"  # Don't wait for idle
        )
        ET.SubElement(
            settings_el, f"{XML_NAMESPACE}DisallowStartOnRemoteAppSession"
        ).text = "false"
        ET.SubElement(
            settings_el, f"{XML_NAMESPACE}UseUnifiedSchedulingEngine"
        ).text = "true"
        ET.SubElement(settings_el, f"{XML_NAMESPACE}WakeToRun").text = (
            "false"  # Don't wake computer
        )
        ET.SubElement(settings_el, f"{XML_NAMESPACE}ExecutionTimeLimit").text = (
            "PT0S"  # PT0S means run indefinitely until stopped/completed
        )
        ET.SubElement(settings_el, f"{XML_NAMESPACE}Priority").text = (
            "7"  # Below normal priority
        )

        # Actions (What to Run)
        actions = ET.SubElement(task, f"{XML_NAMESPACE}Actions", Context="Author")
        exec_action = ET.SubElement(actions, f"{XML_NAMESPACE}Exec")
        ET.SubElement(exec_action, f"{XML_NAMESPACE}Command").text = str(
            EXPATH
        )  # Full path to the main script executable
        # Combine command and args correctly
        full_command_args = f"{command} {command_args}".strip()
        ET.SubElement(exec_action, f"{XML_NAMESPACE}Arguments").text = full_command_args

        # --- Save XML to File ---
        # Ensure server-specific config directory exists
        server_config_dir = os.path.join(config_dir, server_name)
        os.makedirs(server_config_dir, exist_ok=True)

        # Generate a safe filename from the task name
        safe_filename_base = re.sub(
            r'[\\/*?:"<>|]', "_", task_name
        )  # Replace invalid chars
        xml_filename = f"{safe_filename_base}.xml"
        xml_file_path = os.path.join(server_config_dir, xml_filename)

        # Write the XML tree to the file
        ET.indent(task, space="  ")  # Pretty print XML
        tree = ET.ElementTree(task)
        # Task Scheduler expects UTF-16 encoding for imported XML files
        tree.write(xml_file_path, encoding="utf-16", xml_declaration=True)

        logger.info(f"Successfully created task XML definition file: {xml_file_path}")
        return xml_file_path

    except OSError as e:
        logger.error(
            f"Failed to create directory or write task XML file '{xml_file_path}': {e}",
            exc_info=True,
        )
        raise TaskError(f"Failed to write task XML file: {e}") from e
    except Exception as e:
        logger.error(
            f"Unexpected error creating task XML for '{task_name}': {e}", exc_info=True
        )
        raise TaskError(f"Unexpected error creating task XML: {e}") from e


def import_task_xml(xml_file_path: str, task_name: str) -> None:
    """
    Imports a task definition XML file into the Windows Task Scheduler.

    Uses `schtasks /Create /XML /F` (force overwrite).

    Args:
        xml_file_path: The full path to the task definition XML file.
        task_name: The desired name for the task in Task Scheduler (e.g., "BedrockManager\\MyTask").
                   This should match the URI inside the XML.

    Raises:
        MissingArgumentError: If `xml_file_path` or `task_name` is empty.
        FileNotFoundError: If `xml_file_path` does not exist.
        CommandNotFoundError: If the 'schtasks' command is not found.
        TaskError: If the `schtasks /Create` command fails.
    """
    if not xml_file_path:
        raise MissingArgumentError("XML file path cannot be empty.")
    if not task_name:
        raise MissingArgumentError("Task name cannot be empty.")

    schtasks_cmd = shutil.which("schtasks")
    if not schtasks_cmd:
        logger.error("'schtasks' command not found. Cannot import task.")
        raise CommandNotFoundError("schtasks")

    if not os.path.isfile(xml_file_path):
        error_msg = f"Task XML file not found: {xml_file_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    logger.info(f"Importing task '{task_name}' from XML file: {xml_file_path}")

    try:
        # Run schtasks /Create command
        # /F flag forces overwrite if task already exists
        process = subprocess.run(
            [schtasks_cmd, "/Create", "/TN", task_name, "/XML", xml_file_path, "/F"],
            check=True,  # Raise exception on non-zero exit code
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        logger.info(f"Task '{task_name}' imported/updated successfully.")
        logger.debug(f"schtasks output: {process.stdout}")

    except subprocess.CalledProcessError as e:
        stderr_output = (e.stderr or "").strip()
        stdout_output = (e.stdout or "").strip()
        error_msg = f"Failed to import task '{task_name}' using 'schtasks /Create'. Return Code: {e.returncode}. Error: {stderr_output}. Output: {stdout_output}"
        logger.error(error_msg, exc_info=True)
        # Provide more specific feedback if possible
        if "access is denied" in stderr_output.lower():
            raise TaskError(
                f"Access denied importing task '{task_name}'. Try running as Administrator."
            ) from e
        else:
            raise TaskError(error_msg) from e
    except FileNotFoundError:  # Should be caught by shutil.which, but safeguard
        logger.error("'schtasks' command not found unexpectedly during import.")
        raise CommandNotFoundError("schtasks") from None
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while importing task '{task_name}': {e}",
            exc_info=True,
        )
        raise TaskError(f"Unexpected error importing task '{task_name}': {e}") from e


def _get_day_element_name(day_input: Any) -> str:
    """
    Converts various day inputs (name, abbreviation, number) to the Task Scheduler XML element name.

    Args:
        day_input: User input representing a day (e.g., "Mon", "monday", 1, "1").

    Returns:
        The corresponding XML element name (e.g., "Monday").

    Raises:
        InvalidInputError: If the input cannot be mapped to a valid day.
    """
    # Allow integers or strings
    day_input_str = str(day_input).strip().lower()

    days_mapping = {
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

    if day_input_str in days_mapping:
        return days_mapping[day_input_str]
    else:
        logger.error(f"Invalid day of week input provided: '{day_input}'")
        raise InvalidInputError(
            f"Invalid day of week: '{day_input}'. Use name, abbreviation, or number 1-7 (Mon-Sun)."
        )


def _get_month_element_name(month_input: Any) -> str:
    """
    Converts various month inputs (name, abbreviation, number) to the Task Scheduler XML element name.

    Args:
        month_input: User input representing a month (e.g., "Jan", "january", 1, "1").

    Returns:
        The corresponding XML element name (e.g., "January").

    Raises:
        InvalidInputError: If the input cannot be mapped to a valid month.
    """
    # Allow integers or strings
    month_input_str = str(month_input).strip().lower()

    months_mapping = {
        "jan": "January",
        "january": "January",
        "1": "January",
        "feb": "February",
        "february": "February",
        "2": "February",
        "mar": "March",
        "march": "March",
        "3": "March",
        "apr": "April",
        "april": "April",
        "4": "April",
        "may": "May",
        "5": "May",
        "jun": "June",
        "june": "June",
        "6": "June",
        "jul": "July",
        "july": "July",
        "7": "July",
        "aug": "August",
        "august": "August",
        "8": "August",
        "sep": "September",
        "september": "September",
        "9": "September",
        "oct": "October",
        "october": "October",
        "10": "October",
        "nov": "November",
        "november": "November",
        "11": "November",
        "dec": "December",
        "december": "December",
        "12": "December",
    }

    if month_input_str in months_mapping:
        return months_mapping[month_input_str]
    else:
        logger.error(f"Invalid month input provided: '{month_input}'")
        raise InvalidInputError(
            f"Invalid month: '{month_input}'. Use name, abbreviation, or number 1-12."
        )


XML_NAMESPACE = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"


def _parse_task_xml_file(task_file_path: str) -> Dict[str, Any]:
    """
    Parses a Windows Task Scheduler XML definition file to extract details.

    Reads the XML file and extracts the main command path, full arguments string,
    attempts to determine a base command action, and parses trigger information.

    Args:
        task_file_path: The full path to the task's .xml configuration file.

    Returns:
        A dictionary:
        - On success: {"status": "success", "task_details": Dict} where task_details contains
                      keys like "command_path", "command_args", "base_command", "triggers".
        - On failure: {"status": "error", "message": str}.

    Raises:
        FileNotFoundError: If the task_file_path does not exist (can be caught by caller).
        TaskError: If XML parsing fails or essential elements are missing.
    """
    function_name = "_parse_task_xml_file"
    logger.debug(f"{function_name}: Parsing task XML file: {task_file_path}")

    if not os.path.isfile(task_file_path):
        raise FileNotFoundError(f"Task XML file not found: {task_file_path}")

    try:
        tree = ET.parse(task_file_path)
        root = tree.getroot()

        # --- Extract Command Path and Arguments ---
        command_path = ""
        command_args = ""
        base_command = ""  # The action slug like 'backup-all'

        # Use the globally (or at least function-scope) defined XML_NAMESPACE
        command_element = root.find(f".//{XML_NAMESPACE}Exec/{XML_NAMESPACE}Command")
        if command_element is not None and command_element.text:
            command_path = command_element.text.strip()

        arguments_element = root.find(
            f".//{XML_NAMESPACE}Exec/{XML_NAMESPACE}Arguments"
        )
        if arguments_element is not None and arguments_element.text:
            command_args = arguments_element.text.strip()
            if command_args:
                try:
                    base_command = command_args.split()[0]
                except IndexError:
                    logger.warning(
                        f"{function_name}: Could not extract base command from arguments: '{command_args}'"
                    )
                    base_command = ""

        logger.debug(
            f"{function_name}: Extracted Command='{command_path}', Args='{command_args}', Base='{base_command}'"
        )

        # --- Extract Triggers ---
        triggers: List[Dict[str, Any]] = []
        triggers_container = root.find(f".//{XML_NAMESPACE}Triggers")
        if triggers_container is not None:
            logger.debug(
                f"{function_name}: Found {len(triggers_container)} trigger element(s)."
            )
            for trigger_elem in triggers_container:
                trigger_data: Dict[str, Any] = {}
                trigger_tag_local = trigger_elem.tag.replace(XML_NAMESPACE, "")
                trigger_data["type"] = trigger_tag_local

                start_elem = trigger_elem.find(f".//{XML_NAMESPACE}StartBoundary")
                if start_elem is not None and start_elem.text:
                    trigger_data["start"] = start_elem.text

                # Parse CalendarTrigger subtypes
                if trigger_tag_local == "CalendarTrigger":
                    schedule_by_day = trigger_elem.find(
                        f".//{XML_NAMESPACE}ScheduleByDay"
                    )
                    schedule_by_week = trigger_elem.find(
                        f".//{XML_NAMESPACE}ScheduleByWeek"
                    )
                    schedule_by_month = trigger_elem.find(
                        f".//{XML_NAMESPACE}ScheduleByMonth"
                    )

                    if schedule_by_day is not None:
                        trigger_data["type"] = "Daily"
                        interval_elem = schedule_by_day.find(
                            f".//{XML_NAMESPACE}DaysInterval"
                        )
                        trigger_data["interval"] = (
                            int(interval_elem.text)
                            if interval_elem is not None and interval_elem.text
                            else 1
                        )
                    elif schedule_by_week is not None:
                        trigger_data["type"] = "Weekly"
                        interval_elem = schedule_by_week.find(
                            f".//{XML_NAMESPACE}WeeksInterval"
                        )
                        trigger_data["interval"] = (
                            int(interval_elem.text)
                            if interval_elem is not None and interval_elem.text
                            else 1
                        )
                        days_elem = schedule_by_week.find(
                            f".//{XML_NAMESPACE}DaysOfWeek"
                        )
                        if days_elem is not None:
                            trigger_data["days"] = [
                                day.tag.replace(XML_NAMESPACE, "") for day in days_elem
                            ]
                        else:
                            trigger_data["days"] = []
                    elif schedule_by_month is not None:
                        trigger_data["type"] = "Monthly"
                        days_elem = schedule_by_month.find(
                            f".//{XML_NAMESPACE}DaysOfMonth"
                        )
                        if days_elem is not None:
                            trigger_data["days_of_month"] = [
                                d.text
                                for d in days_elem.findall(f".//{XML_NAMESPACE}Day")
                                if d.text
                            ]
                        else:
                            trigger_data["days_of_month"] = []
                        months_elem = schedule_by_month.find(
                            f".//{XML_NAMESPACE}Months"
                        )
                        if months_elem is not None:
                            trigger_data["months"] = [
                                m.tag.replace(XML_NAMESPACE, "") for m in months_elem
                            ]
                        else:
                            trigger_data["months"] = []

                logger.debug(f"{function_name}: Parsed trigger data: {trigger_data}")
                triggers.append(trigger_data)
        else:
            logger.debug(f"{function_name}: No <Triggers> element found in XML.")

        # --- Construct Success Response ---
        task_details = {
            "command_path": command_path,
            "command_args": command_args,
            "base_command": base_command,
            "triggers": triggers,
        }
        logger.debug(f"{function_name}: Successfully parsed task details.")
        return {"status": "success", "task_details": task_details}

    except ET.ParseError as e:
        logger.error(
            f"{function_name}: Error parsing task XML file '{task_file_path}': {e}",
            exc_info=True,
        )
        raise TaskError(f"Error parsing task configuration XML: {e}") from e
    except (AttributeError, KeyError, IndexError, ValueError) as e:
        logger.error(
            f"{function_name}: Error extracting data from task XML '{task_file_path}' (likely missing element/attribute or invalid value): {e}",
            exc_info=True,
        )
        raise TaskError(f"Invalid or incomplete task XML structure: {e}") from e
    except Exception as e:
        logger.error(
            f"{function_name}: Unexpected error parsing task XML file '{task_file_path}': {e}",
            exc_info=True,
        )
        raise TaskError(f"Unexpected error parsing task XML: {e}") from e


def add_trigger(triggers_element: ET.Element, trigger_data: Dict[str, Any]) -> None:
    """
    Adds a specific trigger sub-element to the main <Triggers> XML element.

    Args:
        triggers_element: The parent ET.Element (<Triggers>).
        trigger_data: A dictionary containing details for the trigger. Expected keys vary
                      based on 'type':
                      - type="TimeTrigger": {"type": "TimeTrigger", "start": "YYYY-MM-DDTHH:MM:SS"}
                      - type="Daily": {"type": "Daily", "start": "...", "interval": int}
                      - type="Weekly": {"type": "Weekly", "start": "...", "interval": int, "days": List[str|int]}
                      - type="Monthly": {"type": "Monthly", "start": "...", "days": List[str|int], "months": List[str|int]}

    Raises:
        InvalidInputError: If 'type' is missing or unsupported, or if required data
                           for a specific type is missing or invalid.
        TaskError: If converting day/month names fails (via helper functions).
    """
    trigger_type = trigger_data.get("type")
    start_boundary = trigger_data.get("start")  # Common to most calendar/time triggers

    if not trigger_type:
        raise InvalidInputError("Trigger data must include a 'type' key.")
    if not start_boundary and trigger_type in (
        "TimeTrigger",
        "Daily",
        "Weekly",
        "Monthly",
    ):
        # StartBoundary is generally required for these types
        raise InvalidInputError(
            f"Trigger type '{trigger_type}' requires a 'start' boundary (YYYY-MM-DDTHH:MM:SS)."
        )

    logger.debug(f"Adding trigger to XML: Type='{trigger_type}', Data='{trigger_data}'")

    if trigger_type == "TimeTrigger":
        # Simple one-time trigger
        trigger = ET.SubElement(triggers_element, f"{XML_NAMESPACE}TimeTrigger")
        ET.SubElement(trigger, f"{XML_NAMESPACE}StartBoundary").text = start_boundary
        ET.SubElement(trigger, f"{XML_NAMESPACE}Enabled").text = "true"

    elif trigger_type == "Daily":
        interval = trigger_data.get("interval", 1)  # Default to every 1 day
        try:
            interval_str = str(int(interval))
        except ValueError:
            raise InvalidInputError(f"Invalid interval for Daily trigger: '{interval}'")

        trigger = ET.SubElement(triggers_element, f"{XML_NAMESPACE}CalendarTrigger")
        ET.SubElement(trigger, f"{XML_NAMESPACE}StartBoundary").text = start_boundary
        ET.SubElement(trigger, f"{XML_NAMESPACE}Enabled").text = "true"
        schedule = ET.SubElement(trigger, f"{XML_NAMESPACE}ScheduleByDay")
        ET.SubElement(schedule, f"{XML_NAMESPACE}DaysInterval").text = interval_str

    elif trigger_type == "Weekly":
        interval = trigger_data.get("interval", 1)  # Default to every 1 week
        days = trigger_data.get("days")
        if not days or not isinstance(days, list):
            raise InvalidInputError("Weekly trigger requires a list of 'days'.")
        try:
            interval_str = str(int(interval))
        except ValueError:
            raise InvalidInputError(
                f"Invalid interval for Weekly trigger: '{interval}'"
            )

        trigger = ET.SubElement(triggers_element, f"{XML_NAMESPACE}CalendarTrigger")
        ET.SubElement(trigger, f"{XML_NAMESPACE}StartBoundary").text = start_boundary
        ET.SubElement(trigger, f"{XML_NAMESPACE}Enabled").text = "true"
        schedule = ET.SubElement(trigger, f"{XML_NAMESPACE}ScheduleByWeek")
        days_element = ET.SubElement(schedule, f"{XML_NAMESPACE}DaysOfWeek")
        for day in days:
            try:
                day_name = _get_day_element_name(day)  # Raises InvalidInputError
                ET.SubElement(days_element, f"{XML_NAMESPACE}{day_name}")
            except InvalidInputError as e:
                logger.error(f"Skipping invalid day '{day}' for Weekly trigger: {e}")
                # Optionally re-raise if strict validation needed: raise
        ET.SubElement(schedule, f"{XML_NAMESPACE}WeeksInterval").text = interval_str

    elif trigger_type == "Monthly":
        days = trigger_data.get("days")
        months = trigger_data.get("months")
        if not days or not isinstance(days, list):
            raise InvalidInputError(
                "Monthly trigger requires a list of 'days' (day numbers)."
            )
        if not months or not isinstance(months, list):
            raise InvalidInputError("Monthly trigger requires a list of 'months'.")

        trigger = ET.SubElement(triggers_element, f"{XML_NAMESPACE}CalendarTrigger")
        ET.SubElement(trigger, f"{XML_NAMESPACE}StartBoundary").text = start_boundary
        ET.SubElement(trigger, f"{XML_NAMESPACE}Enabled").text = "true"
        schedule = ET.SubElement(trigger, f"{XML_NAMESPACE}ScheduleByMonth")

        days_element = ET.SubElement(schedule, f"{XML_NAMESPACE}DaysOfMonth")
        for day in days:
            try:
                day_num = int(day)
                if 1 <= day_num <= 31:
                    ET.SubElement(days_element, f"{XML_NAMESPACE}Day").text = str(
                        day_num
                    )
                else:
                    raise ValueError("Day out of range")
            except (ValueError, TypeError):
                logger.error(
                    f"Skipping invalid day number '{day}' for Monthly trigger. Must be 1-31."
                )

        months_element = ET.SubElement(schedule, f"{XML_NAMESPACE}Months")
        for month in months:
            try:
                month_name = _get_month_element_name(month)  # Raises InvalidInputError
                ET.SubElement(months_element, f"{XML_NAMESPACE}{month_name}")
            except InvalidInputError as e:
                logger.error(
                    f"Skipping invalid month '{month}' for Monthly trigger: {e}"
                )

    else:
        logger.error(f"Unsupported trigger type encountered: '{trigger_type}'")
        raise InvalidInputError(f"Unsupported trigger type: {trigger_type}")


def delete_task(task_name: str) -> None:
    """
    Deletes a scheduled task from the Windows Task Scheduler by its name.

    Uses `schtasks /Delete /F`.

    Args:
        task_name: The full name of the task to delete (e.g., "BedrockManager\\MyTask").

    Raises:
        MissingArgumentError: If `task_name` is empty.
        CommandNotFoundError: If the 'schtasks' command is not found.
        TaskError: If the `schtasks /Delete` command fails for reasons other than
                   the task not existing.
    """
    if not task_name:
        raise MissingArgumentError("Task name cannot be empty.")

    schtasks_cmd = shutil.which("schtasks")
    if not schtasks_cmd:
        logger.error("'schtasks' command not found. Cannot delete task.")
        raise CommandNotFoundError("schtasks")

    logger.info(f"Attempting to delete scheduled task: '{task_name}'")

    try:
        # Run schtasks /Delete command
        # /F flag forces deletion without confirmation
        process = subprocess.run(
            [schtasks_cmd, "/Delete", "/TN", task_name, "/F"],
            check=True,  # Raise exception on non-zero exit code
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        logger.info(f"Task '{task_name}' deleted successfully.")
        logger.debug(f"schtasks output: {process.stdout}")

    except subprocess.CalledProcessError as e:
        stderr_output = (e.stderr or "").strip()
        # Check specifically for "task not found" which is not a failure in this context
        if (
            "error: the system cannot find the file specified." in stderr_output.lower()
            or "error: the specified task name" in stderr_output.lower()
            and "does not exist" in stderr_output.lower()
        ):
            logger.info(f"Task '{task_name}' not found. Presumed already deleted.")
            return  # Not an error if task doesn't exist

        # Log other errors
        stdout_output = (e.stdout or "").strip()
        error_msg = f"Failed to delete task '{task_name}' using 'schtasks /Delete'. Return Code: {e.returncode}. Error: {stderr_output}. Output: {stdout_output}"
        logger.error(error_msg, exc_info=True)
        if "access is denied" in stderr_output.lower():
            raise TaskError(
                f"Access denied deleting task '{task_name}'. Try running as Administrator."
            ) from e
        else:
            raise TaskError(error_msg) from e
    except FileNotFoundError:  # Should be caught by shutil.which, but safeguard
        logger.error("'schtasks' command not found unexpectedly during delete.")
        raise CommandNotFoundError("schtasks") from None
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while deleting task '{task_name}': {e}",
            exc_info=True,
        )
        raise TaskError(f"Unexpected error deleting task '{task_name}': {e}") from e
