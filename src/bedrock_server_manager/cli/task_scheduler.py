# bedrock_server_manager/cli/task_scheduler.py
"""
Command-line interface functions for managing scheduled tasks.

Provides interactive menus and calls API functions to handle scheduling of
server operations via Linux cron jobs or Windows Task Scheduler.
"""

import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

try:
    from colorama import Fore, Style, init
except ImportError:

    class DummyStyle:
        def __getattr__(self, name):
            return ""

    Fore = Style = DummyStyle()

    def init(*args, **kwargs):
        pass


from bedrock_server_manager.api import task_scheduler as api_task_scheduler
from bedrock_server_manager.config.const import EXPATH, app_name_title
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    MissingArgumentError,
)
from bedrock_server_manager.utils.general import (
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger(__name__)
APP_DISPLAY_NAME = app_name_title


def task_scheduler(server_name: str, base_dir: Optional[str] = None) -> None:
    """Main entry point for the task scheduler CLI menu."""
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"CLI: Entering task scheduler for server '{server_name}'.")

    if isinstance(
        api_task_scheduler.scheduler, api_task_scheduler.core_task.LinuxTaskScheduler
    ):
        logger.debug("Dispatching to Linux cron scheduler menu.")
        _cron_scheduler(server_name)
    elif isinstance(
        api_task_scheduler.scheduler, api_task_scheduler.core_task.WindowsTaskScheduler
    ):
        logger.debug("Dispatching to Windows Task Scheduler menu.")
        _windows_scheduler(server_name)
    else:
        message = "Task scheduling is not supported or not configured on this operating system."
        print(f"{_ERROR_PREFIX}{message}")
        logger.error(message)


def _cron_scheduler(server_name: str) -> None:
    """Displays the Linux cron job management menu."""
    while True:
        try:
            os.system("clear")
            print(
                f"\n{Fore.MAGENTA}{APP_DISPLAY_NAME} - Cron Job Scheduler{Style.RESET_ALL}"
            )
            print(
                f"{Fore.CYAN}Managing tasks for server: {Fore.YELLOW}{server_name}{Style.RESET_ALL}\n"
            )

            cron_resp = api_task_scheduler.get_server_cron_jobs(server_name)
            if cron_resp.get("status") == "error":
                print(f"{_ERROR_PREFIX}{cron_resp.get('message')}")
            else:
                display_cron_job_table(cron_resp.get("cron_jobs", []))

            print(f"\n{Fore.MAGENTA}Options:{Style.RESET_ALL}")
            print(
                "  1) Add New Cron Job\n  2) Modify Existing Cron Job\n  3) Delete Cron Job\n  4) Back to Advanced Menu"
            )

            choice = input(
                f"{Fore.CYAN}Select an option [1-4]:{Style.RESET_ALL} "
            ).strip()
            if choice == "1":
                add_cron_job(server_name)
            elif choice == "2":
                modify_cron_job(server_name)
            elif choice == "3":
                delete_cron_job(server_name)
            elif choice == "4":
                return
            else:
                print(f"{_WARN_PREFIX}Invalid selection. Please choose again.")
                time.sleep(1.5)
        except (KeyboardInterrupt, EOFError):
            print("\nReturning to previous menu...")
            return
        except Exception as e:
            print(f"\n{_ERROR_PREFIX}An unexpected error occurred: {e}")
            logger.error(
                f"Error in cron scheduler menu for '{server_name}': {e}", exc_info=True
            )
            input("Press Enter to continue...")


def display_cron_job_table(cron_jobs: List[str]) -> None:
    """Displays a formatted table of cron jobs."""
    table_resp = api_task_scheduler.get_cron_jobs_table(cron_jobs)
    if table_resp.get("status") == "error":
        print(f"{_ERROR_PREFIX}{table_resp.get('message')}")
        return

    table_data = table_resp.get("table_data", [])
    if not table_data:
        print(f"{_INFO_PREFIX}No scheduled cron jobs found for this server context.")
        return

    print("-" * 75)
    print(f"{'SCHEDULE (Raw)':<20} {'SCHEDULE (Readable)':<25} {'COMMAND':<25}")
    print("-" * 75)
    for job in table_data:
        raw_schedule = f"{job['minute']} {job['hour']} {job['day_of_month']} {job['month']} {job['day_of_week']}"
        print(
            f"{Fore.GREEN}{raw_schedule:<20}{Style.RESET_ALL}"
            f"{Fore.CYAN}{job.get('schedule_time', 'N/A'):<25}{Style.RESET_ALL} "
            f"{Fore.YELLOW}{job.get('command_display', 'N/A'):<25}{Style.RESET_ALL}"
        )
    print("-" * 75)


def add_cron_job(server_name: str) -> None:
    """CLI handler to interactively add a new cron job."""
    print(f"\n{_INFO_PREFIX}Add New Cron Job")
    command_to_schedule = _get_command_to_schedule(server_name)
    if not command_to_schedule:
        return

    schedule_parts = _get_cron_schedule_details()
    if not schedule_parts:
        return

    minute, hour, dom, month, dow = schedule_parts
    new_cron_string = f"{minute} {hour} {dom} {month} {dow} {command_to_schedule}"

    if _confirm_action(f"Add this cron job?\n  {new_cron_string}"):
        add_resp = api_task_scheduler.add_cron_job(new_cron_string)
        if add_resp.get("status") == "error":
            print(f"{_ERROR_PREFIX}{add_resp.get('message')}")
        else:
            print(f"{_OK_PREFIX}{add_resp.get('message')}")
    else:
        print(f"{_INFO_PREFIX}Cron job not added.")


def modify_cron_job(server_name: str) -> None:
    """CLI handler to interactively modify an existing cron job."""
    print(f"\n{_INFO_PREFIX}Modify Existing Cron Job")

    cron_jobs_resp = api_task_scheduler.get_server_cron_jobs(server_name)
    cron_jobs = cron_jobs_resp.get("cron_jobs", [])
    if not cron_jobs:
        print(f"{_INFO_PREFIX}No existing cron jobs found to modify.")
        return

    job_to_modify = _select_from_list(cron_jobs, "Select the cron job to modify")
    if not job_to_modify:
        return

    old_command = job_to_modify.split(maxsplit=5)[-1]

    print(f"\n{_INFO_PREFIX}Enter NEW schedule details for command: {old_command}")
    new_schedule_parts = _get_cron_schedule_details()
    if not new_schedule_parts:
        return

    minute, hour, dom, month, dow = new_schedule_parts
    new_cron_string = f"{minute} {hour} {dom} {month} {dow} {old_command}"

    if new_cron_string == job_to_modify:
        print(
            f"{_INFO_PREFIX}New schedule is identical to the old one. No change made."
        )
        return

    if _confirm_action(
        f"Apply this modification?\n  Old: {job_to_modify}\n  New: {new_cron_string}"
    ):
        modify_resp = api_task_scheduler.modify_cron_job(job_to_modify, new_cron_string)
        if modify_resp.get("status") == "error":
            print(f"{_ERROR_PREFIX}{modify_resp.get('message')}")
        else:
            print(f"{_OK_PREFIX}{modify_resp.get('message')}")
    else:
        print(f"{_INFO_PREFIX}Cron job not modified.")


def delete_cron_job(server_name: str) -> None:
    """CLI handler to interactively delete an existing cron job."""
    print(f"\n{_INFO_PREFIX}Delete Existing Cron Job")

    cron_jobs_resp = api_task_scheduler.get_server_cron_jobs(server_name)
    cron_jobs = cron_jobs_resp.get("cron_jobs", [])
    if not cron_jobs:
        print(f"{_INFO_PREFIX}No existing cron jobs found to delete.")
        return

    job_to_delete = _select_from_list(cron_jobs, "Select the cron job to delete")
    if not job_to_delete:
        return

    if _confirm_action(
        f"Are you sure you want to delete this cron job?\n  {job_to_delete}",
        is_destructive=True,
    ):
        delete_resp = api_task_scheduler.delete_cron_job(job_to_delete)
        if delete_resp.get("status") == "error":
            print(f"{_ERROR_PREFIX}{delete_resp.get('message')}")
        else:
            print(f"{_OK_PREFIX}{delete_resp.get('message')}")
    else:
        print(f"{_INFO_PREFIX}Cron job not deleted.")


# --- Windows Scheduler ---


def _windows_scheduler(server_name: str) -> None:
    """Displays the Windows Task Scheduler management menu."""
    config_dir = getattr(settings, "config_dir")
    if not config_dir:
        print(f"{_ERROR_PREFIX}Base configuration directory not set.")
        return

    while True:
        try:
            os.system("cls")
            print(
                f"\n{Fore.MAGENTA}{APP_DISPLAY_NAME} - Windows Task Scheduler{Style.RESET_ALL}"
            )
            print(
                f"{Fore.CYAN}Managing tasks for server: {Fore.YELLOW}{server_name}{Style.RESET_ALL}\n"
            )

            task_names_resp = api_task_scheduler.get_server_task_names(
                server_name, config_dir
            )
            if task_names_resp.get("status") == "error":
                print(f"{_ERROR_PREFIX}{task_names_resp.get('message')}")
            else:
                task_list = task_names_resp.get("task_names", [])
                if task_list:
                    display_windows_task_table(task_list)
                else:
                    print(f"{_INFO_PREFIX}No configured tasks found for this server.")

            print(f"\n{Fore.MAGENTA}Options:{Style.RESET_ALL}")
            print(
                "  1) Add New Task\n  2) Modify Existing Task\n  3) Delete Task\n  4) Back to Advanced Menu"
            )

            choice = input(
                f"{Fore.CYAN}Select an option [1-4]:{Style.RESET_ALL} "
            ).strip()
            if choice == "1":
                add_windows_task(server_name, config_dir)
            elif choice == "2":
                modify_windows_task(server_name, config_dir)
            elif choice == "3":
                delete_windows_task(server_name, config_dir)
            elif choice == "4":
                return
            else:
                print(f"{_WARN_PREFIX}Invalid selection. Please choose again.")
                time.sleep(1.5)
        except (KeyboardInterrupt, EOFError):
            print("\nReturning to previous menu...")
            return
        except Exception as e:
            print(f"\n{_ERROR_PREFIX}An unexpected error occurred: {e}")
            logger.error(
                f"Error in Windows scheduler menu for '{server_name}': {e}",
                exc_info=True,
            )
            input("Press Enter to continue...")


def display_windows_task_table(task_name_path_list: List[Tuple[str, str]]) -> None:
    """Displays a formatted table of Windows scheduled tasks."""
    task_names = [task[0] for task in task_name_path_list]
    task_info_resp = api_task_scheduler.get_windows_task_info(task_names)

    if task_info_resp.get("status") == "error":
        print(f"{_ERROR_PREFIX}{task_info_resp.get('message')}")
        return

    task_info_list = task_info_resp.get("task_info", [])
    if not task_info_list:
        print(
            f"{_INFO_PREFIX}No tasks found in Windows Task Scheduler (config files may exist)."
        )
        return

    print("-" * 80)
    print(f"{'TASK NAME':<35} {'COMMAND':<20} {'SCHEDULE (Readable)':<25}")
    print("-" * 80)
    for task in task_info_list:
        print(
            f"{Fore.GREEN}{task.get('task_name', 'N/A'):<35}{Style.RESET_ALL}"
            f"{Fore.YELLOW}{task.get('command', 'N/A'):<20}{Style.RESET_ALL}"
            f"{Fore.CYAN}{task.get('schedule', 'N/A'):<25}{Style.RESET_ALL}"
        )
    print("-" * 80)


def add_windows_task(server_name: str, config_dir: str) -> None:
    """CLI handler to interactively add a new Windows task."""
    print(f"\n{_INFO_PREFIX}Add New Windows Scheduled Task")

    selected_command = _get_command_to_schedule(server_name, is_windows=True)
    if not selected_command:
        return

    command_args = (
        f'--server "{server_name}"' if selected_command != "scan-players" else ""
    )
    task_name = api_task_scheduler.create_task_name(server_name, selected_command)
    print(f"{_INFO_PREFIX}Generated Task Name: {task_name}")

    triggers = _get_trigger_details()
    if not triggers:
        if not _confirm_action(
            "No triggers defined. Create a manually runnable task anyway?"
        ):
            print(f"{_INFO_PREFIX}Add task canceled.")
            return

    create_resp = api_task_scheduler.create_windows_task(
        server_name, selected_command, command_args, task_name, triggers, config_dir
    )
    if create_resp.get("status") == "error":
        print(f"{_ERROR_PREFIX}{create_resp.get('message')}")
    else:
        print(f"{_OK_PREFIX}{create_resp.get('message')}")


def modify_windows_task(server_name: str, config_dir: str) -> None:
    """CLI handler to modify an existing Windows task by replacing it."""
    print(f"\n{_INFO_PREFIX}Modify Existing Windows Task")

    task_list_resp = api_task_scheduler.get_server_task_names(server_name, config_dir)
    task_list = task_list_resp.get("task_names", [])
    if not task_list:
        print(f"{_INFO_PREFIX}No existing tasks found to modify.")
        return

    task_to_modify = _select_from_list(
        [t[0] for t in task_list], "Select the task to modify"
    )
    if not task_to_modify:
        return

    print(
        f"\n{_INFO_PREFIX}The existing task '{task_to_modify}' will be deleted and replaced."
    )
    print(f"{_INFO_PREFIX}Please define the new command and schedule:")

    add_windows_task(server_name, config_dir)


def delete_windows_task(server_name: str, config_dir: str) -> None:
    """CLI handler to interactively delete a Windows task."""
    print(f"\n{_INFO_PREFIX}Delete Existing Windows Task")

    task_list_resp = api_task_scheduler.get_server_task_names(server_name, config_dir)
    task_list = task_list_resp.get("task_names", [])
    if not task_list:
        print(f"{_INFO_PREFIX}No existing tasks found to delete.")
        return

    task_tuple = _select_from_list(
        task_list, "Select the task to delete", display_index=0
    )
    if not task_tuple:
        return

    task_name_to_delete, task_file_path = task_tuple

    if _confirm_action(
        f"Are you sure you want to delete task '{task_name_to_delete}'?",
        is_destructive=True,
    ):
        delete_resp = api_task_scheduler.delete_windows_task(
            task_name_to_delete, task_file_path
        )
        if delete_resp.get("status") == "error":
            print(f"{_ERROR_PREFIX}{delete_resp.get('message')}")
        else:
            print(f"{_OK_PREFIX}{delete_resp.get('message')}")
    else:
        print(f"{_INFO_PREFIX}Task not deleted.")


# --- Helper Functions for CLI ---


def _get_command_to_schedule(
    server_name: str, is_windows: bool = False
) -> Optional[str]:
    """Shared helper to get a command selection from the user."""
    print(f"\n{Fore.MAGENTA}Choose the command to schedule:{Style.RESET_ALL}")
    command_options = {
        1: ("Update Server", "update-server"),
        2: ("Backup Server (All)", "backup-all"),
        3: ("Start Server", "start-server"),
        4: ("Stop Server", "stop-server"),
        5: ("Restart Server", "restart-server"),
        6: ("Scan Players", "scan-players"),
    }
    for idx, (desc, _) in command_options.items():
        print(f"  {idx}) {desc}")
    print(f"  {len(command_options) + 1}) Cancel")

    while True:
        try:
            choice = int(input(f"{Fore.CYAN}Select command:{Style.RESET_ALL} ").strip())
            if 1 <= choice <= len(command_options):
                slug = command_options[choice][1]
                if is_windows:
                    return slug
                # For Linux, construct the full command string
                args = f'--server "{server_name}"' if slug != "scan-players" else ""
                return f"{EXPATH} {slug} {args}".strip()
            elif choice == len(command_options) + 1:
                print(f"{_INFO_PREFIX}Operation canceled.")
                return None
            else:
                print(f"{_WARN_PREFIX}Invalid choice.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")


def _get_cron_schedule_details() -> Optional[Tuple[str, str, str, str, str]]:
    """Shared helper to get cron schedule parts from the user."""
    print(f"\n{_INFO_PREFIX}Enter schedule details (* for any value):")
    prompts = [
        ("Minute", 0, 59),
        ("Hour", 0, 23),
        ("Day of Month", 1, 31),
        ("Month", 1, 12),
        ("Day of Week", 0, 7, "0/7=Sun"),
    ]
    parts = {}
    for name, min_val, max_val, *help_txt in prompts:
        help_str = f" ({help_txt[0]})" if help_txt else ""
        while True:
            val = input(
                f"{Fore.CYAN}{name} ({min_val}-{max_val} or *){help_str}:{Style.RESET_ALL} "
            ).strip()
            # Basic validation can be done here, but API layer handles it robustly
            if val:
                parts[name] = val
                break
            else:
                print(f"{_WARN_PREFIX}Input cannot be empty. Use '*' for any value.")
    return (
        parts["Minute"],
        parts["Hour"],
        parts["Day of Month"],
        parts["Month"],
        parts["Day of Week"],
    )


def _get_trigger_details() -> List[Dict[str, Any]]:
    """Interactively gathers trigger details for Windows tasks."""
    triggers = []
    while True:
        print(f"\n{Fore.MAGENTA}Add Trigger - Choose Type:{Style.RESET_ALL}")
        print("  1) Daily\n  2) Weekly\n  3) Done Adding Triggers")
        choice = input(
            f"{Fore.CYAN}Select trigger type (1-3):{Style.RESET_ALL} "
        ).strip()

        if choice not in ("1", "2"):
            break

        start_str = input(
            f"{Fore.CYAN}Enter start time (HH:MM):{Style.RESET_ALL} "
        ).strip()
        try:
            start_dt = datetime.strptime(start_str, "%H:%M")
            # Set date to today for a valid ISO string
            start_iso = (
                datetime.now()
                .replace(hour=start_dt.hour, minute=start_dt.minute, second=0)
                .isoformat(timespec="seconds")
            )
        except ValueError:
            print(
                f"{_ERROR_PREFIX}Invalid time format. Please use HH:MM. Trigger not added."
            )
            continue

        trigger = {"start": start_iso}
        if choice == "1":  # Daily
            trigger["type"] = "Daily"
            trigger["interval"] = 1
            triggers.append(trigger)
            print(f"{_INFO_PREFIX}Daily trigger added.")
        elif choice == "2":  # Weekly
            trigger["type"] = "Weekly"
            days_str = input(
                f"{Fore.CYAN}Enter days (comma-separated: Mon,Tue,etc.):{Style.RESET_ALL} "
            ).strip()
            trigger["days"] = [d.strip() for d in days_str.split(",") if d.strip()]
            trigger["interval"] = 1
            if trigger["days"]:
                triggers.append(trigger)
                print(f"{_INFO_PREFIX}Weekly trigger added.")
            else:
                print(f"{_WARN_PREFIX}No days specified. Weekly trigger not added.")
    return triggers


def _select_from_list(items: List, prompt: str, display_index=None) -> Any:
    """Helper to have a user select an item from a list."""
    print(f"\n{Fore.MAGENTA}{prompt}:{Style.RESET_ALL}")
    for i, item in enumerate(items):
        display_item = (
            item[display_index]
            if isinstance(item, tuple) and display_index is not None
            else item
        )
        print(f"  {i + 1}) {display_item}")
    print(f"  {len(items) + 1}) Cancel")

    while True:
        try:
            choice = int(
                input(
                    f"{Fore.CYAN}Enter number (1-{len(items) + 1}):{Style.RESET_ALL} "
                ).strip()
            )
            if 1 <= choice <= len(items):
                return items[choice - 1]
            elif choice == len(items) + 1:
                return None
            else:
                print(f"{_WARN_PREFIX}Invalid selection.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")


def _confirm_action(prompt: str, is_destructive: bool = False) -> bool:
    """Helper to get a y/n confirmation from the user."""
    color = Fore.RED if is_destructive else Fore.CYAN
    while True:
        confirm = input(f"{color}{prompt} (y/n):{Style.RESET_ALL} ").strip().lower()
        if confirm in ("y", "yes"):
            return True
        if confirm in ("n", "no", ""):
            return False
        print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")
