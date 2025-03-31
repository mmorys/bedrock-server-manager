# bedrock-server-manager/bedrock_server_manager/cli/task_scheduler.py
import os
import time
import logging
import platform
from datetime import datetime
from colorama import Fore, Style
import xml.etree.ElementTree as ET
from bedrock_server_manager.api import task_scheduler as api_task_scheduler
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.config.settings import EXPATH, app_name
from bedrock_server_manager.core.error import InvalidServerNameError
from bedrock_server_manager.utils.general import (
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger("bedrock_server_manager")


def task_scheduler(server_name, base_dir=None):
    """Displays the task scheduler menu and handles user interaction."""
    base_dir = get_base_dir(base_dir)

    if not server_name:
        raise InvalidServerNameError("task_scheduler: server_name is empty.")

    if platform.system() == "Linux":
        _cron_scheduler(server_name, base_dir)
    elif platform.system() == "Windows":
        _windows_scheduler(server_name, base_dir, config_dir=None)
    else:
        print(f"{_ERROR_PREFIX}Unsupported operating system for task scheduling.")
        raise OSError("Unsupported operating system for task scheduling")


def _cron_scheduler(server_name, base_dir):
    """Displays the cron scheduler menu and handles user interaction."""
    if not server_name:
        raise InvalidServerNameError("cron_scheduler: server_name is empty.")

    while True:
        os.system("cls" if platform.system() == "Windows" else "clear")
        print(f"{Fore.MAGENTA}{app_name} - Task Scheduler{Style.RESET_ALL}")
        print(
            f"{Fore.CYAN}Current scheduled task for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
        )

        # Get cron jobs
        cron_jobs_response = api_task_scheduler.get_server_cron_jobs(server_name)
        if cron_jobs_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{cron_jobs_response['message']}")
            time.sleep(2)
            continue

        cron_jobs = cron_jobs_response["cron_jobs"]

        # Display cron jobs using the api to format the table
        if display_cron_job_table(cron_jobs) != 0:
            print(f"{_ERROR_PREFIX}Failed to display cron jobs.")
            time.sleep(2)
            continue

        print(f"{Fore.MAGENTA}What would you like to do?{Style.RESET_ALL}")
        print("1) Add Job")
        print("2) Modify Job")
        print("3) Delete Job")
        print("4) Back")

        choice = input(f"{Fore.CYAN}Enter the number (1-4):{Style.RESET_ALL} ").strip()

        if choice == "1":
            add_cron_job(server_name, base_dir)
        elif choice == "2":
            modify_cron_job(server_name, base_dir)
        elif choice == "3":
            delete_cron_job(server_name, base_dir)
        elif choice == "4":
            return  # Exit the menu
        else:
            print(f"{_WARN_PREFIX}Invalid choice. Please try again.")


def display_cron_job_table(cron_jobs):
    """Displays a table of cron jobs.  Returns 0 on success, non-zero on failure."""
    # Get formatted table data
    table_response = api_task_scheduler.get_cron_jobs_table(cron_jobs)

    if table_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{table_response['message']}")
        return 1  # Indicate failure

    table_data = table_response["table_data"]

    if not table_data:
        print(f"{_INFO_PREFIX}No cron jobs to display.")
        return 0

    print("-------------------------------------------------------")
    print(f"{'CRON JOBS':<15} {'SCHEDULE':<20}  {'COMMAND':<10}")
    print("-------------------------------------------------------")

    for job in table_data:
        print(
            f"{Fore.GREEN}{job['minute']} {job['hour']} {job['day_of_month']} {job['month']} {job['day_of_week']}{Style.RESET_ALL}".ljust(
                15
            )
            + f"{Fore.CYAN}{job['schedule_time']:<25}{Style.RESET_ALL} {Fore.YELLOW}{job['command']}{Style.RESET_ALL}"
        )

    print("-------------------------------------------------------")
    return 0


def add_cron_job(server_name, base_dir):
    """Adds a new cron job."""
    if not server_name:
        raise InvalidServerNameError("add_cron_job: server_name is empty.")

    if platform.system() != "Linux":
        print(f"{_ERROR_PREFIX}Cron jobs are only supported on Linux.")
        return

    print(
        f"{Fore.CYAN}Choose the command for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
    )
    print("1) Update Server")
    print("2) Backup Server")
    print("3) Start Server")
    print("4) Stop Server")
    print("5) Restart Server")
    print("6) Scan Players")

    while True:
        try:
            choice = int(
                input(f"{Fore.CYAN}Enter the number (1-6):{Style.RESET_ALL} ").strip()
            )
            if 1 <= choice <= 6:
                break
            else:
                print(f"{_WARN_PREFIX}Invalid choice, please try again.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    if choice == 1:
        command = f"{EXPATH} update-server --server {server_name}"
    elif choice == 2:
        command = f"{EXPATH} backup-all --server {server_name}"
    elif choice == 3:
        command = f"{EXPATH} start-server --server {server_name}"
    elif choice == 4:
        command = f"{EXPATH} stop-server --server {server_name}"
    elif choice == 5:
        command = f"{EXPATH} restart-server --server {server_name}"
    elif choice == 6:
        command = f"{EXPATH} scan-players"

    # Get cron timing details
    while True:
        month = input(f"{Fore.CYAN}Month (1-12 or *):{Style.RESET_ALL} ").strip()
        month_response = api_task_scheduler.validate_cron_input(month, 1, 12)
        if month_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{month_response['message']}")
            continue

        day = input(f"{Fore.CYAN}Day of Month (1-31 or *):{Style.RESET_ALL} ").strip()
        day_response = api_task_scheduler.validate_cron_input(day, 1, 31)
        if day_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{day_response['message']}")
            continue

        hour = input(f"{Fore.CYAN}Hour (0-23 or *):{Style.RESET_ALL} ").strip()
        hour_response = api_task_scheduler.validate_cron_input(hour, 0, 23)
        if hour_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{hour_response['message']}")
            continue

        minute = input(f"{Fore.CYAN}Minute (0-59 or *):{Style.RESET_ALL} ").strip()
        minute_response = api_task_scheduler.validate_cron_input(minute, 0, 59)
        if minute_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{minute_response['message']}")
            continue

        weekday = input(
            f"{Fore.CYAN}Day of Week (0-7, 0 or 7 for Sunday or *):{Style.RESET_ALL} "
        ).strip()
        weekday_response = api_task_scheduler.validate_cron_input(weekday, 0, 7)
        if weekday_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{weekday_response['message']}")
            continue

        break  # All inputs are valid

    # Get readable schedule time
    schedule_response = api_task_scheduler.convert_to_readable_schedule(
        month, day, hour, minute, weekday
    )
    if schedule_response["status"] == "error":
        schedule_time = "ERROR CONVERTING"
        print(
            f"{_ERROR_PREFIX}Error converting schedule: {schedule_response['message']}"
        )
    else:
        schedule_time = schedule_response["schedule_time"]

    display_command = command.replace(os.path.join(EXPATH), "").strip()
    display_command = display_command.split("--", 1)[0].strip()
    print(
        f"{_INFO_PREFIX}Your cron job will run with the following schedule:{Style.RESET_ALL}"
    )
    print("-------------------------------------------------------")
    print(f"{'CRON JOB':<15} {'SCHEDULE':<20}  {'COMMAND':<10}")
    print("-------------------------------------------------------")
    print(
        f"{Fore.GREEN}{minute} {hour} {day} {month} {weekday}{Style.RESET_ALL}".ljust(
            15
        )
        + f"{Fore.CYAN}{schedule_time:<25}{Style.RESET_ALL} {Fore.YELLOW}{display_command}{Style.RESET_ALL}"
    )
    print("-------------------------------------------------------")

    while True:
        confirm = (
            input(f"{Fore.CYAN}Do you want to add this job? (y/n): ").lower().strip()
        )
        if confirm in ("yes", "y"):
            new_cron_job = f"{minute} {hour} {day} {month} {weekday} {command}"
            # Add the cron job
            add_response = add_cron_job(new_cron_job)
            if add_response["status"] == "error":
                print(f"{_ERROR_PREFIX}{add_response['message']}")
            else:
                print(f"{_OK_PREFIX}Cron job added successfully!")
            return
        elif confirm in ("no", "n", ""):
            print(f"{_INFO_PREFIX}Cron job not added.")
            return
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")


def modify_cron_job(server_name, base_dir):
    """Modifies an existing cron job."""

    if not server_name:
        raise InvalidServerNameError("modify_cron_job: server_name is empty.")

    print(
        f"{_INFO_PREFIX}Current scheduled cron jobs for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
    )
    # Get cron jobs
    cron_jobs_response = api_task_scheduler.get_server_cron_jobs(server_name)
    if cron_jobs_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{cron_jobs_response['message']}")
        return

    cron_jobs = cron_jobs_response["cron_jobs"]
    if not cron_jobs:
        print(f"{_INFO_PREFIX}No scheduled cron jobs found to modify.")
        return

    for i, line in enumerate(cron_jobs):
        print(f"{i + 1}. {line}")

    while True:
        try:
            job_number = int(
                input(
                    f"{Fore.CYAN}Enter the number of the job you want to modify:{Style.RESET_ALL} "
                ).strip()
            )
            if 1 <= job_number <= len(cron_jobs):
                job_to_modify = cron_jobs[job_number - 1]
                break
            else:
                print(f"{_WARN_PREFIX}Invalid selection. Please choose a valid number.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    # Extract the command part
    job_command = " ".join(job_to_modify.split()[5:])

    print(
        f"{_INFO_PREFIX}Modify the timing details for this cron job:{Style.RESET_ALL}"
    )
    # Get cron timing details (UI)
    while True:
        month = input(f"{Fore.CYAN}Month (1-12 or *):{Style.RESET_ALL} ").strip()
        month_response = api_task_scheduler.validate_cron_input(month, 1, 12)
        if month_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{month_response['message']}")
            continue

        day = input(f"{Fore.CYAN}Day of Month (1-31 or *):{Style.RESET_ALL} ").strip()
        day_response = api_task_scheduler.validate_cron_input(day, 1, 31)
        if day_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{day_response['message']}")
            continue

        hour = input(f"{Fore.CYAN}Hour (0-23 or *):{Style.RESET_ALL} ").strip()
        hour_response = api_task_scheduler.validate_cron_input(hour, 0, 23)
        if hour_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{hour_response['message']}")
            continue

        minute = input(f"{Fore.CYAN}Minute (0-59 or *):{Style.RESET_ALL} ").strip()
        minute_response = api_task_scheduler.validate_cron_input(minute, 0, 59)
        if minute_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{minute_response['message']}")
            continue

        weekday = input(
            f"{Fore.CYAN}Day of Week (0-7, 0 or 7 for Sunday or *):{Style.RESET_ALL} "
        ).strip()
        weekday_response = api_task_scheduler.validate_cron_input(weekday, 0, 7)
        if weekday_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{weekday_response['message']}")
            continue

        break  # All inputs are valid

    # Get readable schedule time
    schedule_response = api_task_scheduler.convert_to_readable_schedule(
        month, day, hour, minute, weekday
    )
    if schedule_response["status"] == "error":
        schedule_time = "ERROR CONVERTING"
        print(
            f"{_ERROR_PREFIX}Error converting schedule: {schedule_response['message']}"
        )
    else:
        schedule_time = schedule_response["schedule_time"]

    # Format command (UI-specific formatting)
    display_command = job_command.replace(os.path.join(EXPATH), "").strip()
    display_command = display_command.split("--", 1)[0].strip()
    print(
        f"{_INFO_PREFIX}Your modified cron job will run with the following schedule:{Style.RESET_ALL}"
    )
    print("-------------------------------------------------------")
    print(f"{'CRON JOB':<15} {'SCHEDULE':<20}  {'COMMAND':<10}")
    print("-------------------------------------------------------")
    print(
        f"{Fore.GREEN}{minute} {hour} {day} {month} {weekday}{Style.RESET_ALL}".ljust(
            15
        )
        + f"{Fore.CYAN}{schedule_time:<25}{Style.RESET_ALL} {Fore.YELLOW}{display_command}{Style.RESET_ALL}"
    )
    print("-------------------------------------------------------")

    while True:
        confirm = (
            input(f"{Fore.CYAN}Do you want to modify this job? (y/n): ").lower().strip()
        )
        if confirm in ("yes", "y"):
            new_cron_job = f"{minute} {hour} {day} {month} {weekday} {job_command}"
            # Modify the cron job
            modify_response = modify_cron_job(job_to_modify, new_cron_job)
            if modify_response["status"] == "error":
                print(f"{_ERROR_PREFIX}{modify_response['message']}")
            else:
                print(f"{_OK_PREFIX}Cron job modified successfully!")
            return

        elif confirm in ("no", "n", ""):
            print(f"{_INFO_PREFIX}Cron job not modified.")
            return
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")


def delete_cron_job(server_name, base_dir):
    """Deletes a cron job for the specified server."""

    if not server_name:
        raise InvalidServerNameError("delete_cron_job: server_name is empty.")

    print(
        f"{_INFO_PREFIX}Current scheduled cron jobs for {Fore.YELLOW}{server_name}:{Style.RESET_ALL}"
    )

    # Get cron jobs
    cron_jobs_response = api_task_scheduler.get_server_cron_jobs(server_name)
    if cron_jobs_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{cron_jobs_response['message']}")
        return

    cron_jobs = cron_jobs_response["cron_jobs"]
    if not cron_jobs:
        print(f"{_INFO_PREFIX}No scheduled cron jobs found to delete.")
        return

    for i, line in enumerate(cron_jobs):
        print(f"{i + 1}. {line}")
    print(f"{len(cron_jobs) + 1}. Cancel")

    while True:
        try:
            job_number = int(
                input(
                    f"{Fore.CYAN}Enter the number of the job you want to delete (1-{len(cron_jobs) + 1}):{Style.RESET_ALL} "
                ).strip()
            )
            if 1 <= job_number <= len(cron_jobs):
                job_to_delete = cron_jobs[job_number - 1]
                break
            elif job_number == len(cron_jobs) + 1:
                print(f"{_INFO_PREFIX}Cron job deletion canceled.")
                return  # User canceled
            else:
                print(f"{_WARN_PREFIX}Invalid selection. No matching cron job found.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    while True:
        confirm_delete = (
            input(
                f"{Fore.RED}Are you sure you want to delete this cron job? (y/n):{Style.RESET_ALL} "
            )
            .lower()
            .strip()
        )
        if confirm_delete in ("y", "yes"):
            # Delete the cron job
            delete_response = delete_cron_job(job_to_delete)
            if delete_response["status"] == "error":
                print(f"{_ERROR_PREFIX}{delete_response['message']}")
            else:
                print(f"{_OK_PREFIX}Cron job deleted successfully!")
            return
        elif confirm_delete in ("n", "no", ""):
            print(f"{_INFO_PREFIX}Cron job not deleted.")
            return  # User canceled
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")


def _windows_scheduler(server_name, base_dir, config_dir=None):
    """Displays the Windows Task Scheduler menu and handles user interaction."""
    if config_dir is None:
        config_dir = settings._config_dir

    if not server_name:
        raise InvalidServerNameError("windows_task_scheduler: server_name is empty.")

    if platform.system() != "Windows":
        raise OSError("This function is for Windows only.")
    os.system("cls")
    while True:
        print(f"{Fore.MAGENTA}{app_name} - Task Scheduler{Style.RESET_ALL}")
        print(
            f"{Fore.CYAN}Current scheduled tasks for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
        )

        # Get task names
        task_names_response = api_task_scheduler.get_server_task_names(
            server_name, config_dir
        )
        if task_names_response["status"] == "error":
            print(f"{_ERROR_PREFIX}{task_names_response['message']}")
            time.sleep(2)
            continue  # go back to main menu

        task_names = task_names_response["task_names"]

        if not task_names:
            print(f"{_INFO_PREFIX}No scheduled tasks found.")
        else:
            display_windows_task_table(task_names)

        print(f"{Fore.CYAN}What would you like to do?{Style.RESET_ALL}")
        print("1) Add Task")
        print("2) Modify Task")
        print("3) Delete Task")
        print("4) Back")

        choice = input(f"{Fore.CYAN}Enter the number (1-4):{Style.RESET_ALL} ").strip()
        try:
            if choice == "1":
                add_windows_task(server_name, base_dir, config_dir)
            elif choice == "2":
                modify_windows_task(server_name, base_dir, config_dir)
            elif choice == "3":
                delete_windows_task(server_name, base_dir, config_dir)
            elif choice == "4":
                return  # Exit the menu
            else:
                print(f"{_WARN_PREFIX}Invalid choice. Please try again.")
        except Exception as e:
            print(f"{_ERROR_PREFIX}An error has occurred: {e}")


def display_windows_task_table(task_names):
    """Displays a table of Windows scheduled tasks."""

    # Get detailed task information
    task_info_response = api_task_scheduler.get_windows_task_info(
        [task[0] for task in task_names]
    )
    if task_info_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{task_info_response['message']}")
        return

    task_info = task_info_response["task_info"]

    print(
        "-------------------------------------------------------------------------------"
    )
    print(f"{'TASK NAME':<30} {'COMMAND':<25} {'SCHEDULE':<20}")
    print(
        "-------------------------------------------------------------------------------"
    )

    for task in task_info:
        print(
            f"{Fore.GREEN}{task['task_name']:<30}{Fore.YELLOW}{task['command']:<25}{Fore.CYAN}{task['schedule']:<20}{Style.RESET_ALL}"
        )
    print(
        "-------------------------------------------------------------------------------"
    )


def add_windows_task(server_name, base_dir, config_dir=None):
    """Adds a new Windows scheduled task."""

    if not server_name:
        raise InvalidServerNameError("add_windows_task: server_name is empty.")

    if platform.system() != "Windows":
        print(f"{_ERROR_PREFIX}This function is for Windows only.")
        return

    if config_dir is None:
        config_dir = settings._config_dir

    print(
        f"{Fore.CYAN}Adding task for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
    )

    print(f"{Fore.MAGENTA}Choose the command:{Style.RESET_ALL}")
    print("1) Update Server")
    print("2) Backup Server")
    print("3) Start Server")
    print("4) Stop Server")
    print("5) Restart Server")
    print("6) Scan Players")
    print("7) Cancel")

    while True:
        try:
            choice = int(
                input(f"{Fore.CYAN}Enter the number (1-7):{Style.RESET_ALL} ").strip()
            )
            if 1 <= choice <= 6:
                break
            elif choice == 7:
                print(f"{_INFO_PREFIX}Add task cancelled.")
                return  # User cancelled
            else:
                print(f"{_WARN_PREFIX}Invalid choice, please try again.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    if choice == 1:
        command = "update-server"
        command_args = f"--server {server_name}"
    elif choice == 2:
        command = "backup-all"
        command_args = f"--server {server_name}"
    elif choice == 3:
        command = "start-server"
        command_args = f"--server {server_name}"
    elif choice == 4:
        command = "stop-server"
        command_args = f"--server {server_name}"
    elif choice == 5:
        command = "restart-server"
        command_args = f"--server {server_name}"
    elif choice == 6:
        command = "scan-players"
        command_args = ""

    task_name = (
        f"bedrock_{server_name}_{command.replace('-', '_')}"  # Create a task name
    )

    # Get trigger information from the user
    triggers = get_trigger_details()

    # Create the task
    create_response = api_task_scheduler.create_windows_task(
        server_name, command, command_args, task_name, config_dir, triggers, base_dir
    )
    if create_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{create_response['message']}")
    else:
        print(f"{_OK_PREFIX}Task '{task_name}' added successfully!")


def get_trigger_details():
    """Gets trigger information from the user interactively."""
    triggers = []
    while True:
        print(f"{Fore.MAGENTA}Choose a trigger type:{Style.RESET_ALL}")
        print("1) One Time")
        print("2) Daily")
        print("3) Weekly")
        print("4) Monthly")
        print("5) Add another trigger")
        print("6) Done adding triggers")

        trigger_choice = input(
            f"{Fore.CYAN}Enter the number (1-6):{Style.RESET_ALL} "
        ).strip()

        if trigger_choice == "1":  # One Time
            trigger_data = {"type": "TimeTrigger"}
            while True:
                start_boundary = input(
                    f"{Fore.CYAN}Enter start date and time (YYYY-MM-DD HH:MM):{Style.RESET_ALL} "
                ).strip()
                try:
                    start_boundary_dt = datetime.strptime(
                        start_boundary, "%Y-%m-%d %H:%M"
                    )
                    trigger_data["start"] = start_boundary_dt.isoformat()
                    break  # Valid input
                except ValueError:
                    print(
                        f"{_ERROR_PREFIX}Incorrect format, please use YYYY-MM-DD HH:MM"
                    )
            triggers.append(trigger_data)

        elif trigger_choice == "2":  # Daily
            trigger_data = {"type": "Daily"}
            while True:
                start_boundary = input(
                    f"{Fore.CYAN}Enter start date and time (YYYY-MM-DD HH:MM){Style.RESET_ALL}: "
                ).strip()
                try:
                    start_boundary_dt = datetime.strptime(
                        start_boundary, "%Y-%m-%d %H:%M"
                    )
                    trigger_data["start"] = start_boundary_dt.isoformat()
                    break  # Valid input
                except ValueError:
                    print(
                        f"{_ERROR_PREFIX}Incorrect format, please use YYYY-MM-DD HH:MM"
                    )
            while True:
                try:
                    days_interval = int(
                        input(
                            f"{Fore.CYAN}Enter interval in days:{Style.RESET_ALL} "
                        ).strip()
                    )
                    if days_interval >= 1:
                        trigger_data["interval"] = days_interval
                        break  # Valid input
                    else:
                        print(f"{_WARN_PREFIX}Enter a value greater than or equal to 1")
                except ValueError:
                    print(f"{_ERROR_PREFIX}Must be a valid integer.")
            triggers.append(trigger_data)

        elif trigger_choice == "3":  # Weekly
            trigger_data = {"type": "Weekly"}
            while True:
                start_boundary = input(
                    f"{Fore.CYAN}Enter start date and time (YYYY-MM-DD HH:MM):{Style.RESET_ALL} "
                ).strip()
                try:
                    start_boundary_dt = datetime.strptime(
                        start_boundary, "%Y-%m-%d %H:%M"
                    )
                    trigger_data["start"] = start_boundary_dt.isoformat()
                    break  # Valid input
                except ValueError:
                    print(
                        f"{_ERROR_PREFIX}Incorrect format, please use YYYY-MM-DD HH:MM"
                    )

            while True:  # Loop for days of the week input
                days_of_week_str = input(
                    f"{Fore.CYAN}Enter days of the week (comma-separated: Sun,Mon,Tue,Wed,Thu,Fri,Sat OR 1-7):{Style.RESET_ALL} "
                ).strip()
                days_of_week = [day.strip() for day in days_of_week_str.split(",")]
                valid_days = []
                for day_input in days_of_week:
                    day_response = api_task_scheduler.get_day_element_name(day_input)
                    if day_response["status"] == "success":  # use core function
                        valid_days.append(day_input)
                    else:
                        print(
                            f"{_WARN_PREFIX}Invalid day of week: {day_input}. Skipping."
                        )
                if valid_days:
                    trigger_data["days"] = valid_days
                    break  # Exit if at least one valid day is entered
                else:
                    print(f"{_ERROR_PREFIX}You must enter at least one valid day.")

            while True:
                try:
                    weeks_interval = int(
                        input(
                            f"{Fore.CYAN}Enter interval in weeks:{Style.RESET_ALL} "
                        ).strip()
                    )
                    if weeks_interval >= 1:
                        trigger_data["interval"] = weeks_interval
                        break  # Valid input
                    else:
                        print(f"{_WARN_PREFIX}Enter a value greater than or equal to 1")
                except ValueError:
                    print(f"{_ERROR_PREFIX}Must be a valid integer.")
            triggers.append(trigger_data)

        elif trigger_choice == "4":  # Monthly
            trigger_data = {"type": "Monthly"}
            while True:
                start_boundary = input(
                    f"{Fore.CYAN}Enter start date and time (YYYY-MM-DD HH:MM):{Style.RESET_ALL} "
                ).strip()
                try:
                    start_boundary_dt = datetime.strptime(
                        start_boundary, "%Y-%m-%d %H:%M"
                    )
                    trigger_data["start"] = start_boundary_dt.isoformat()
                    break  # Valid input
                except ValueError:
                    print(
                        f"{_ERROR_PREFIX}Incorrect date format, please use YYYY-MM-DD HH:MM"
                    )

            while True:  # Loop for days input
                days_of_month_str = input(
                    f"{Fore.CYAN}Enter days of the month (comma-separated, 1-31):{Style.RESET_ALL} "
                ).strip()
                days_of_month = [day.strip() for day in days_of_month_str.split(",")]
                valid_days = []
                for day in days_of_month:
                    try:
                        day_int = int(day)
                        if 1 <= day_int <= 31:
                            valid_days.append(day_int)
                        else:
                            print(
                                f"{_WARN_PREFIX}Invalid day of month: {day}. Skipping."
                            )
                    except ValueError:
                        print(f"{_WARN_PREFIX}Invalid day of month: {day}. Skipping.")
                if valid_days:
                    trigger_data["days"] = valid_days
                    break
                else:
                    print(f"{_ERROR_PREFIX}You must enter at least one valid day")

            while True:  # Loop for months input
                months_str = input(
                    f"{Fore.CYAN}Enter months (comma-separated: Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec OR 1-12):{Style.RESET_ALL} "
                ).strip()
                months = [month.strip() for month in months_str.split(",")]
                valid_months = []
                for month_input in months:
                    month_response = api_task_scheduler.get_month_element_name(
                        month_input
                    )
                    if month_response["status"] == "success":  # Use core function
                        valid_months.append(month_input)
                    else:
                        print(f"{_WARN_PREFIX}Invalid month: {month_input}. Skipping.")
                if valid_months:
                    trigger_data["months"] = valid_months
                    break  # Exit loop
                else:
                    print(f"{_ERROR_PREFIX}You must enter at least one valid month.")
            triggers.append(trigger_data)

        elif trigger_choice == "5":
            continue  # Add another trigger
        elif trigger_choice == "6":
            break  # Done adding triggers
        else:
            print(f"{_WARN_PREFIX}Invalid choice.")

    return triggers


def modify_windows_task(server_name, base_dir, config_dir=None):
    """Modifies an existing Windows scheduled task (UI)."""
    if not server_name:
        raise InvalidServerNameError("modify_windows_task: server_name is empty.")

    if platform.system() != "Windows":
        print(f"{_ERROR_PREFIX}This function is for Windows only.")
        return
    # Get task names
    task_names_response = api_task_scheduler.get_server_task_names(
        server_name, config_dir
    )
    if task_names_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{task_names_response['message']}")
        return

    task_names = task_names_response["task_names"]
    if not task_names:
        print(f"{_INFO_PREFIX}No scheduled tasks found to modify.")
        return

    print(
        f"{Fore.CYAN}Select the task to modify for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
    )
    for i, (task_name, file_path) in enumerate(task_names):  # Unpack tuple
        print(f"{i + 1}. {task_name}")
    print(f"{len(task_names) + 1}. Cancel")

    while True:
        try:
            task_index = (
                int(
                    input(
                        f"{Fore.CYAN}Enter the number of the task to modify (1-{len(task_names) + 1}):{Style.RESET_ALL} "
                    ).strip()
                )
                - 1
            )
            if 0 <= task_index < len(task_names):
                selected_task_name, selected_file_path = task_names[
                    task_index
                ]  # Unpack here
                break
            elif task_index == len(task_names):
                print(f"{_INFO_PREFIX}Modify task cancelled.")
                return  # Cancelled
            else:
                print(f"{_WARN_PREFIX}Invalid selection.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    # --- Get existing command and arguments using XML parsing ---
    try:
        tree = ET.parse(selected_file_path)
        root = tree.getroot()

        # Handle namespaces.  Task Scheduler XML *usually* uses this namespace:
        namespaces = {"ns": "http://schemas.microsoft.com/windows/2004/02/mit/task"}

        # Find the Command and Arguments elements, using the namespace
        command_element = root.find(".//ns:Command", namespaces)
        arguments_element = root.find(".//ns:Arguments", namespaces)

        # Extract text, handle None case safely
        command = command_element.text.strip() if command_element is not None else ""
        command_args = (
            arguments_element.text.strip() if arguments_element is not None else ""
        )

    except (FileNotFoundError, ET.ParseError) as e:
        print(f"{_ERROR_PREFIX}Error loading task XML: {e}")
        return

    # --- Get new trigger information from the user ---
    triggers = get_trigger_details()

    # Create a task name
    new_task_name = api_task_scheduler.create_task_name(server_name, command_args)

    # Modify the task
    modify_response = api_task_scheduler.modify_windows_task(
        selected_task_name,
        server_name,
        command,
        command_args,
        new_task_name,
        config_dir,
        triggers,
        base_dir,
    )

    if modify_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{modify_response['message']}")
    else:
        print(
            f"{_OK_PREFIX}Task '{selected_task_name}' modified successfully! (New name: {new_task_name})"
        )


def delete_windows_task(server_name, base_dir, config_dir=None):
    """Deletes a Windows scheduled task (UI)."""

    if not server_name:
        raise InvalidServerNameError("delete_windows_task: server_name is empty.")

    if platform.system() != "Windows":
        print(f"{_ERROR_PREFIX}This function is for Windows only.")
        return
    # Get task names
    task_names_response = api_task_scheduler.get_server_task_names(
        server_name, config_dir
    )

    if task_names_response["status"] == "error":
        print(f"{_ERROR_PREFIX}{task_names_response['message']}")
        return
    task_names = task_names_response["task_names"]
    if not task_names:
        print(f"{_INFO_PREFIX}No scheduled tasks found to delete.")
        return

    print(
        f"{Fore.CYAN}Select the task to delete for {Fore.YELLOW}{server_name}{Fore.CYAN}:{Style.RESET_ALL}"
    )
    for i, (task_name, file_path) in enumerate(task_names):  # Unpack the tuple
        print(f"{i + 1}. {task_name}")
    print(f"{len(task_names) + 1}. Cancel")

    while True:
        try:
            task_index = (
                int(
                    input(
                        f"{Fore.CYAN}Enter the number of the task to delete (1-{len(task_names) + 1}):{Style.RESET_ALL} "
                    ).strip()
                )
                - 1
            )
            if 0 <= task_index < len(task_names):
                selected_task_name, selected_file_path = task_names[
                    task_index
                ]  # Unpack tuple
                break
            elif task_index == len(task_names):
                print(f"{_INFO_PREFIX}Task deletion cancelled.")
                return  # Cancelled
            else:
                print(f"{_WARN_PREFIX}Invalid selection.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")

    # Confirm deletion
    while True:
        confirm_delete = (
            input(
                f"{Fore.RED}Are you sure you want to delete the task {Fore.YELLOW}{selected_task_name}{Fore.RED}? (y/n):{Style.RESET_ALL} "
            )
            .lower()
            .strip()
        )
        if confirm_delete in ("y", "yes"):
            # Delete the task
            delete_response = api_task_scheduler.delete_windows_task(
                selected_task_name, selected_file_path
            )
            if delete_response["status"] == "error":
                print(f"{_ERROR_PREFIX}{delete_response['message']}")
            else:
                print(f"{_OK_PREFIX}Task '{selected_task_name}' deleted successfully!")
            return
        elif confirm_delete in ("n", "no", ""):
            print(f"{_INFO_PREFIX}Task deletion canceled.")
            return  # User canceled
        else:
            print(f"{_WARN_PREFIX}Invalid input.  Please enter 'y' or 'n'.")
