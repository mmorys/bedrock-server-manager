# bedrock-server-manager/bedrock_server_manager/cli/task_scheduler.py
"""
Command-line interface functions for managing scheduled tasks.

Provides interactive menus and calls API functions to handle scheduling of
server operations via Linux cron jobs or Windows Task Scheduler. Uses print()
for user interaction and feedback.
"""

import os
import time
import logging
import platform
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

# Third-party imports
try:
    from colorama import Fore, Style, init

    COLORAMA_AVAILABLE = True
except ImportError:
    # Define dummy Fore, Style, init if colorama is not installed
    class DummyStyle:
        def __getattr__(self, name):
            return ""

    Fore = DummyStyle()
    Style = DummyStyle()

    def init(*args, **kwargs):
        pass


# Local imports
from bedrock_server_manager.api import task_scheduler as api_task_scheduler
from bedrock_server_manager.config.settings import (
    settings,
)
from bedrock_server_manager.config.settings import EXPATH, app_name
from bedrock_server_manager.core.system.linux import _parse_cron_line

from bedrock_server_manager.error import (
    InvalidServerNameError,
    FileOperationError,
)
from bedrock_server_manager.utils.general import (
    get_base_dir,
    _INFO_PREFIX,
    _OK_PREFIX,
    _WARN_PREFIX,
    _ERROR_PREFIX,
)

logger = logging.getLogger("bedrock_server_manager")

APP_DISPLAY_NAME = app_name


def task_scheduler(server_name: str, base_dir: Optional[str] = None) -> None:
    """
    Main entry point for the task scheduler CLI menu.

    Dispatches to the appropriate platform-specific scheduler menu (Linux cron or Windows Task Scheduler).

    Args:
        server_name: The name of the server context for scheduling tasks.
        base_dir: Optional. The base directory for server installations. Uses config default if None.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        OSError: If the operating system is not Linux or Windows.
        FileOperationError: If base_dir determination fails.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    logger.debug(f"CLI: Entering task scheduler main menu for server '{server_name}'.")

    try:
        # Resolve base_dir once, needed by Windows task creation API call later
        effective_base_dir = get_base_dir(base_dir)
        effective_config_dir = getattr(settings, "_config_dir", None)
        if not effective_config_dir:
            raise FileOperationError("Base configuration directory not set.")

        os_name = platform.system()
        if os_name == "Linux":
            logger.debug("Dispatching to Linux cron scheduler menu.")
            _cron_scheduler(server_name)
        elif os_name == "Windows":
            logger.debug("Dispatching to Windows Task Scheduler menu.")
            _windows_scheduler(server_name, effective_base_dir, effective_config_dir)
        else:
            message = f"Task scheduling is not supported on this operating system ({os_name})."
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(message)
            # Consider raising OSError or just returning
            raise OSError(message)

    except (InvalidServerNameError, FileOperationError) as e:
        # Catch errors from this function's setup or get_base_dir
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to initialize task scheduler for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        # Catch unexpected errors during dispatch
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error in task scheduler dispatch for '{server_name}': {e}",
            exc_info=True,
        )


def _cron_scheduler(server_name: str) -> None:
    """
    Displays the Linux cron job management menu and handles user interaction.

    Args:
        server_name: The name of the server context.
    """
    logger.debug(f"Entering Linux cron scheduler menu for server '{server_name}'.")
    while True:
        try:
            os.system("clear")  # Clear screen for Linux
            print(
                f"\n{Fore.MAGENTA}{APP_DISPLAY_NAME} - Cron Job Scheduler{Style.RESET_ALL}"
            )
            print(
                f"{Fore.CYAN}Managing scheduled tasks (cron jobs) for server context: {Fore.YELLOW}{server_name}{Style.RESET_ALL}\n"
            )

            # API call to get cron jobs relevant to this server
            logger.debug(
                f"Calling API: api_task_scheduler.get_server_cron_jobs for '{server_name}'"
            )
            cron_jobs_response = api_task_scheduler.get_server_cron_jobs(server_name)
            logger.debug(f"API get_server_cron_jobs response: {cron_jobs_response}")

            # Display current jobs (or error)
            if cron_jobs_response.get("status") == "error":
                print(
                    f"{_ERROR_PREFIX}{cron_jobs_response.get('message', 'Could not retrieve cron jobs.')}"
                )
            else:
                cron_jobs = cron_jobs_response.get("cron_jobs", [])
                # Display formatted table (handles empty list)
                display_cron_job_table(cron_jobs)  # Handles printing internally

            # --- User Interaction: Menu ---
            print(f"\n{Fore.MAGENTA}Options:{Style.RESET_ALL}")
            print("  1) Add New Cron Job")
            print("  2) Modify Existing Cron Job")
            print("  3) Delete Cron Job")
            print("  4) Back to Advanced Menu")
            # --- End User Interaction ---

            # --- User Interaction: Get Choice ---
            choice = input(
                f"{Fore.CYAN}Select an option [1-4]:{Style.RESET_ALL} "
            ).strip()
            logger.debug(f"Cron scheduler menu choice: '{choice}'")
            # --- End User Interaction ---

            if choice == "1":
                logger.debug("User selected 'Add New Cron Job'.")
                add_cron_job(server_name)  # Handles interaction and API call
                input("\nPress Enter to return to scheduler menu...")
            elif choice == "2":
                logger.debug("User selected 'Modify Existing Cron Job'.")
                modify_cron_job(server_name)  # Handles interaction and API call
                input("\nPress Enter to return to scheduler menu...")
            elif choice == "3":
                logger.debug("User selected 'Delete Cron Job'.")
                delete_cron_job(server_name)  # Handles interaction and API call
                input("\nPress Enter to return to scheduler menu...")
            elif choice == "4":
                logger.debug("Exiting cron scheduler menu.")
                return  # Go back
            else:
                # --- User Interaction: Print Invalid Choice ---
                print(
                    f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose again."
                )
                # --- End User Interaction ---
                logger.warning(f"Invalid cron scheduler menu choice: '{choice}'")
                time.sleep(1.5)  # Pause briefly

        except (KeyboardInterrupt, EOFError):
            print("\nReturning to previous menu...")
            logger.debug(
                "Returning to previous menu due to KeyboardInterrupt/EOFError in cron scheduler."
            )
            return
        except Exception as e:
            # Catch unexpected errors in the menu loop itself
            print(
                f"\n{_ERROR_PREFIX}An unexpected error occurred in the scheduler menu: {e}"
            )
            logger.error(
                f"Error in cron scheduler menu loop for '{server_name}': {e}",
                exc_info=True,
            )
            input("Press Enter to continue...")


def display_cron_job_table(cron_jobs: List[str]) -> None:
    """
    Displays a formatted table of cron jobs using the API formatter.

    Args:
        cron_jobs: A list of raw cron job strings.
    """
    logger.debug(f"Preparing to display {len(cron_jobs)} cron jobs.")
    # API call to get formatted data
    logger.debug("Calling API: api_task_scheduler.get_cron_jobs_table")
    table_response = api_task_scheduler.get_cron_jobs_table(cron_jobs)
    logger.debug(f"API get_cron_jobs_table response: {table_response}")

    # --- User Interaction: Print Table/Messages ---
    if table_response.get("status") == "error":
        print(
            f"{_ERROR_PREFIX}{table_response.get('message', 'Error formatting cron jobs.')}"
        )
        logger.error(
            f"CLI: Failed to format cron jobs table: {table_response.get('message')}"
        )
        return

    table_data = table_response.get("table_data", [])
    if not table_data:
        print(f"{_INFO_PREFIX}No scheduled cron jobs found for this server context.")
        return

    # Print header
    print("-" * 75)
    print(f"{'SCHEDULE (Raw)':<20} {'SCHEDULE (Readable)':<25} {'COMMAND':<25}")
    print("-" * 75)

    # Print rows
    for job in table_data:
        raw_schedule = f"{job['minute']} {job['hour']} {job['day_of_month']} {job['month']} {job['day_of_week']}"
        # Use Fore.RESET to ensure color doesn't bleed if fields are short
        print(
            f"{Fore.GREEN}{raw_schedule:<20}{Style.RESET_ALL}"
            f"{Fore.CYAN}{job.get('schedule_time', 'N/A'):<25}{Style.RESET_ALL} "
            f"{Fore.YELLOW}{job.get('command_display', 'N/A'):<25}{Style.RESET_ALL}"
        )

    print("-" * 75)
    # --- End User Interaction ---


def add_cron_job(server_name: str) -> None:
    """
    CLI handler function to interactively add a new cron job.

    Prompts user for command and schedule details, validates input, confirms,
    and calls the API function to add the job.

    Args:
        server_name: The name of the server context.
    """
    # Platform check is done by API func, but good practice here too
    if platform.system() != "Linux":
        print(f"{_ERROR_PREFIX}Cron jobs are only supported on Linux.")
        return

    logger.debug(
        f"CLI: Starting interactive 'add cron job' workflow for server context '{server_name}'."
    )
    print(f"\n{_INFO_PREFIX}Add New Cron Job")

    # --- User Interaction: Select Command ---
    print(f"{Fore.MAGENTA}Choose the command to schedule:{Style.RESET_ALL}")
    # Command options mapped to the actual commands run by the script
    command_options = {
        1: ("Update Server", f'{EXPATH} update-server --server "{server_name}"'),
        2: ("Backup Server (All)", f'{EXPATH} backup-all --server "{server_name}"'),
        3: ("Start Server", f'{EXPATH} start-server --server "{server_name}"'),
        4: ("Stop Server", f'{EXPATH} stop-server --server "{server_name}"'),
        5: ("Restart Server", f'{EXPATH} restart-server --server "{server_name}"'),
        6: ("Scan Players", f"{EXPATH} scan-players"),
    }
    for idx, (desc, _) in command_options.items():
        print(f"  {idx}) {desc}")
    print(f"  {len(command_options) + 1}) Cancel")

    command_to_schedule: Optional[str] = None
    while True:
        try:
            choice_str = input(
                f"{Fore.CYAN}Select command (1-{len(command_options) + 1}):{Style.RESET_ALL} "
            ).strip()
            choice = int(choice_str)
            logger.debug(f"User command choice: {choice}")
            if 1 <= choice <= len(command_options):
                command_to_schedule = command_options[choice][
                    1
                ]  # Get the full command string
                break
            elif choice == len(command_options) + 1:
                print(f"{_INFO_PREFIX}Add cron job canceled.")
                logger.debug("User canceled adding cron job at command selection.")
                return  # Exit
            else:
                print(f"{_WARN_PREFIX}Invalid choice. Please select a valid number.")
        except ValueError:
            print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
            logger.debug(
                f"User entered non-numeric input for command selection: '{choice_str}'"
            )
    # --- End User Interaction ---

    # --- User Interaction: Get Schedule Details ---
    print(f"\n{_INFO_PREFIX}Enter schedule details (* for any value):")
    minute, hour, day_of_month, month, day_of_week = "*", "*", "*", "*", "*"  # Defaults
    while True:  # Outer loop for re-entry if validation fails
        schedule_valid = True
        schedule_parts: Dict[str, str] = {}
        prompts = [
            ("Minute", 0, 59),
            ("Hour", 0, 23),
            ("Day of Month", 1, 31),
            ("Month", 1, 12),
            ("Day of Week", 0, 7, "0 or 7 for Sunday"),
        ]
        for i, (prompt_name, min_val, max_val, *extra_help) in enumerate(prompts):
            help_text = f" ({extra_help[0]})" if extra_help else ""
            field_value = input(
                f"{Fore.CYAN}{prompt_name} ({min_val}-{max_val} or *){help_text}:{Style.RESET_ALL} "
            ).strip()
            logger.debug(f"User input for '{prompt_name}': '{field_value}'")

            # Validate input using API function
            validation_response = api_task_scheduler.validate_cron_input(
                field_value, min_val, max_val
            )
            if validation_response.get("status") == "error":
                print(
                    f"{_ERROR_PREFIX}{validation_response.get('message', 'Invalid input.')}"
                )
                schedule_valid = False
                break  # Break inner loop (prompting for fields), restart outer loop
            schedule_parts[prompt_name] = field_value

        if not schedule_valid:
            print(f"{_WARN_PREFIX}Please re-enter the schedule details.")
            continue  # Re-start the schedule input loop

        # All fields validated, assign to variables
        minute, hour, day_of_month, month, day_of_week = (
            schedule_parts["Minute"],
            schedule_parts["Hour"],
            schedule_parts["Day of Month"],
            schedule_parts["Month"],
            schedule_parts["Day of Week"],
        )
        break  # Exit outer loop, schedule is valid
    # --- End User Interaction ---

    # --- Display Confirmation ---
    logger.debug("Converting entered schedule to readable format...")
    readable_schedule = (
        f"{minute} {hour} {day_of_month} {month} {day_of_week}"  # Fallback
    )
    try:
        schedule_response = api_task_scheduler.convert_to_readable_schedule(
            minute, hour, day_of_month, month, day_of_week
        )
        if schedule_response.get("status") == "success":
            readable_schedule = schedule_response.get(
                "schedule_time", readable_schedule
            )
        else:
            print(
                f"{_WARN_PREFIX}Could not generate readable schedule: {schedule_response.get('message')}"
            )
    except Exception as e:
        logger.warning(
            f"Error converting schedule to readable format: {e}", exc_info=True
        )

    # --- User Interaction: Confirmation ---
    print(f"\n{_INFO_PREFIX}Confirm Cron Job Details:{Style.RESET_ALL}")
    print("-" * 40)
    print(f"  Schedule (Raw) : {minute} {hour} {day_of_month} {month} {day_of_week}")
    print(f"  Schedule (Est.): {readable_schedule}")
    print(f"  Command        : {command_to_schedule}")
    print("-" * 40)

    while True:
        confirm = (
            input(f"{Fore.CYAN}Add this cron job? (y/n):{Style.RESET_ALL} ")
            .strip()
            .lower()
        )
        logger.debug(f"User confirmation for add cron job: '{confirm}'")
        if confirm in ("yes", "y"):
            # --- Call API to Add ---
            new_cron_string = f"{minute} {hour} {day_of_month} {month} {day_of_week} {command_to_schedule}"
            logger.debug(
                f"Calling API: api_task_scheduler.add_cron_job with string: '{new_cron_string}'"
            )
            add_response = api_task_scheduler.add_cron_job(new_cron_string)
            logger.debug(f"API response from add_cron_job: {add_response}")

            if add_response.get("status") == "error":
                message = add_response.get("message", "Unknown error adding job.")
                print(f"{_ERROR_PREFIX}{message}")
            else:
                message = add_response.get("message", "Cron job added successfully.")
                print(f"{_OK_PREFIX}{message}")
            return  # Exit function after attempting add
        elif confirm in ("no", "n", ""):
            print(f"{_INFO_PREFIX}Cron job not added.")
            logger.debug("User canceled adding cron job at confirmation.")
            return  # Exit function
        else:
            print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")
    # --- End User Interaction ---


def modify_cron_job(server_name: str) -> None:
    """
    CLI handler function to interactively select and modify an existing cron job.

    Lists existing jobs, prompts for selection, gets new schedule details, confirms,
    and calls the API function to modify the job.

    Args:
        server_name: The name of the server context.
    """

    logger.debug(
        f"CLI: Starting interactive 'modify cron job' workflow for server context '{server_name}'."
    )
    print(f"\n{_INFO_PREFIX}Modify Existing Cron Job for Server Context: {server_name}")

    try:
        # --- Get and Display Existing Jobs ---
        logger.debug(
            f"Calling API: api_task_scheduler.get_server_cron_jobs for '{server_name}'"
        )
        cron_jobs_response = api_task_scheduler.get_server_cron_jobs(server_name)
        logger.debug(f"API get_server_cron_jobs response: {cron_jobs_response}")

        if cron_jobs_response.get("status") == "error":
            print(
                f"{_ERROR_PREFIX}{cron_jobs_response.get('message', 'Could not retrieve cron jobs.')}"
            )
            return
        cron_jobs = cron_jobs_response.get("cron_jobs", [])
        if not cron_jobs:
            print(
                f"{_INFO_PREFIX}No existing cron jobs found for this server context to modify."
            )
            return

        # --- User Interaction: Select Job to Modify ---
        print(f"{Fore.MAGENTA}Select the cron job to modify:{Style.RESET_ALL}")
        job_map: Dict[int, str] = {}
        for i, line in enumerate(cron_jobs):
            job_map[i + 1] = line
            # Display raw line for selection
            print(f"  {i + 1}. {line}")
        cancel_option_num = len(job_map) + 1
        print(f"  {cancel_option_num}. Cancel")

        job_to_modify: Optional[str] = None
        while True:
            try:
                choice_str = input(
                    f"{Fore.CYAN}Enter job number (1-{cancel_option_num}):{Style.RESET_ALL} "
                ).strip()
                choice = int(choice_str)
                logger.debug(f"User choice for job modification: {choice}")
                if 1 <= choice <= len(job_map):
                    job_to_modify = job_map[choice]
                    break
                elif choice == cancel_option_num:
                    print(f"{_INFO_PREFIX}Cron job modification canceled.")
                    logger.debug("User canceled modification at job selection.")
                    return
                else:
                    print(
                        f"{_WARN_PREFIX}Invalid selection. Please choose a valid number."
                    )
            except ValueError:
                print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
                logger.debug(
                    f"User entered non-numeric input for job modification selection: '{choice_str}'"
                )
        # --- End User Interaction ---

        # Extract command part (it cannot be modified here, only schedule)
        parsed_old_job = _parse_cron_line(
            job_to_modify
        )  # Use local helper for consistency
        if not parsed_old_job:
            # Should not happen if get_server_cron_jobs works, but handle defensively
            print(
                f"{_ERROR_PREFIX}Could not parse the selected cron job line. Cannot modify."
            )
            logger.error(
                f"Could not parse selected cron job for modification: '{job_to_modify}'"
            )
            return

        _, _, _, _, _, old_command = parsed_old_job
        print(f"\n{_INFO_PREFIX}Modifying schedule for command: {old_command}")

        # --- User Interaction: Get New Schedule ---
        print(f"{_INFO_PREFIX}Enter NEW schedule details (* for any value):")
        minute, hour, day_of_month, month, day_of_week = (
            "*",
            "*",
            "*",
            "*",
            "*",
        )  # Defaults
        while True:  # Outer loop for re-entry if validation fails
            schedule_valid = True
            schedule_parts: Dict[str, str] = {}
            prompts = [
                ("Minute", 0, 59),
                ("Hour", 0, 23),
                ("Day of Month", 1, 31),
                ("Month", 1, 12),
                ("Day of Week", 0, 7, "0 or 7 for Sunday"),
            ]
            for i, (prompt_name, min_val, max_val, *extra_help) in enumerate(prompts):
                help_text = f" ({extra_help[0]})" if extra_help else ""
                field_value = input(
                    f"{Fore.CYAN}{prompt_name} ({min_val}-{max_val} or *){help_text}:{Style.RESET_ALL} "
                ).strip()
                logger.debug(
                    f"User input for modified '{prompt_name}': '{field_value}'"
                )

                validation_response = api_task_scheduler.validate_cron_input(
                    field_value, min_val, max_val
                )
                if validation_response.get("status") == "error":
                    print(
                        f"{_ERROR_PREFIX}{validation_response.get('message', 'Invalid input.')}"
                    )
                    schedule_valid = False
                    break
                schedule_parts[prompt_name] = field_value

            if not schedule_valid:
                print(f"{_WARN_PREFIX}Please re-enter the schedule details.")
                continue

            minute, hour, day_of_month, month, day_of_week = (
                schedule_parts["Minute"],
                schedule_parts["Hour"],
                schedule_parts["Day of Month"],
                schedule_parts["Month"],
                schedule_parts["Day of Week"],
            )
            break  # Exit schedule input loop
        # --- End User Interaction ---

        # Construct new cron string
        new_cron_string = (
            f"{minute} {hour} {day_of_month} {month} {day_of_week} {old_command}"
        )

        if new_cron_string == job_to_modify:
            print(
                f"{_INFO_PREFIX}New schedule is identical to the old one. No modification needed."
            )
            logger.debug("User entered identical schedule during modification.")
            return

        # --- Display Confirmation ---
        logger.debug("Converting modified schedule to readable format...")
        readable_schedule = (
            f"{minute} {hour} {day_of_month} {month} {day_of_week}"  # Fallback
        )
        try:
            schedule_response = api_task_scheduler.convert_to_readable_schedule(
                minute, hour, day_of_month, month, day_of_week
            )
            if schedule_response.get("status") == "success":
                readable_schedule = schedule_response.get(
                    "schedule_time", readable_schedule
                )
            else:
                print(
                    f"{_WARN_PREFIX}Could not generate readable schedule: {schedule_response.get('message')}"
                )
        except Exception as e:
            logger.warning(
                f"Error converting modified schedule to readable format: {e}",
                exc_info=True,
            )

        # --- User Interaction: Confirmation ---
        print(f"\n{_INFO_PREFIX}Confirm Modified Cron Job:{Style.RESET_ALL}")
        print("-" * 40)
        print(f"  Old Schedule : {job_to_modify}")
        print(f"  New Schedule : {new_cron_string}")
        print(f"  New Est. Run : {readable_schedule}")
        print("-" * 40)

        while True:
            confirm = (
                input(f"{Fore.CYAN}Apply this modification? (y/n):{Style.RESET_ALL} ")
                .strip()
                .lower()
            )
            logger.debug(f"User confirmation for modify cron job: '{confirm}'")
            if confirm in ("yes", "y"):
                # --- Call API to Modify ---
                logger.debug(f"Calling API: api_task_scheduler.modify_cron_job")
                modify_response = api_task_scheduler.modify_cron_job(
                    job_to_modify, new_cron_string
                )
                logger.debug(f"API response from modify_cron_job: {modify_response}")

                if modify_response.get("status") == "error":
                    message = modify_response.get(
                        "message", "Unknown error modifying job."
                    )
                    print(f"{_ERROR_PREFIX}{message}")
                else:
                    message = modify_response.get(
                        "message", "Cron job modified successfully."
                    )
                    print(f"{_OK_PREFIX}{message}")
                return  # Exit function after attempting modify
            elif confirm in ("no", "n", ""):
                print(f"{_INFO_PREFIX}Cron job not modified.")
                logger.debug("User canceled modifying cron job at confirmation.")
                return  # Exit function
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")
        # --- End User Interaction ---

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to modify cron job for '{server_name}': {e}", exc_info=True
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error modifying cron job for '{server_name}': {e}",
            exc_info=True,
        )


def delete_cron_job(server_name: str) -> None:
    """
    CLI handler function to interactively select and delete an existing cron job.

    Args:
        server_name: The name of the server context.
    """
    # Platform check done by API funcs
    logger.debug(
        f"CLI: Starting interactive 'delete cron job' workflow for server context '{server_name}'."
    )
    print(f"\n{_INFO_PREFIX}Delete Existing Cron Job for Server Context: {server_name}")

    try:
        # --- Get and Display Existing Jobs ---
        logger.debug(
            f"Calling API: api_task_scheduler.get_server_cron_jobs for '{server_name}'"
        )
        cron_jobs_response = api_task_scheduler.get_server_cron_jobs(server_name)
        logger.debug(f"API get_server_cron_jobs response: {cron_jobs_response}")

        if cron_jobs_response.get("status") == "error":
            print(
                f"{_ERROR_PREFIX}{cron_jobs_response.get('message', 'Could not retrieve cron jobs.')}"
            )
            return
        cron_jobs = cron_jobs_response.get("cron_jobs", [])
        if not cron_jobs:
            print(
                f"{_INFO_PREFIX}No existing cron jobs found for this server context to delete."
            )
            return

        # --- User Interaction: Select Job to Delete ---
        print(f"{Fore.MAGENTA}Select the cron job to delete:{Style.RESET_ALL}")
        job_map: Dict[int, str] = {}
        for i, line in enumerate(cron_jobs):
            job_map[i + 1] = line
            print(f"  {i + 1}. {line}")  # Display raw line
        cancel_option_num = len(job_map) + 1
        print(f"  {cancel_option_num}. Cancel")

        job_to_delete: Optional[str] = None
        while True:
            try:
                choice_str = input(
                    f"{Fore.CYAN}Enter job number (1-{cancel_option_num}):{Style.RESET_ALL} "
                ).strip()
                choice = int(choice_str)
                logger.debug(f"User choice for job deletion: {choice}")
                if 1 <= choice <= len(job_map):
                    job_to_delete = job_map[choice]
                    break
                elif choice == cancel_option_num:
                    print(f"{_INFO_PREFIX}Cron job deletion canceled.")
                    logger.debug("User canceled deletion at job selection.")
                    return
                else:
                    print(
                        f"{_WARN_PREFIX}Invalid selection. Please choose a valid number."
                    )
            except ValueError:
                print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
                logger.debug(
                    f"User entered non-numeric input for job deletion selection: '{choice_str}'"
                )
        # --- End User Interaction ---

        # --- User Interaction: Confirmation ---
        print(f"\n{_WARN_PREFIX}You selected the following job for deletion:")
        print(f"  {job_to_delete}")
        while True:
            confirm = (
                input(
                    f"{Fore.RED}Are you sure you want to delete this cron job? (y/n):{Style.RESET_ALL} "
                )
                .strip()
                .lower()
            )
            logger.debug(f"User confirmation for delete cron job: '{confirm}'")
            if confirm in ("yes", "y"):
                # --- Call API to Delete ---
                logger.debug(
                    f"Calling API: api_task_scheduler.delete_cron_job with string: '{job_to_delete}'"
                )
                delete_response = api_task_scheduler.delete_cron_job(job_to_delete)
                logger.debug(f"API response from delete_cron_job: {delete_response}")

                if delete_response.get("status") == "error":
                    message = delete_response.get(
                        "message", "Unknown error deleting job."
                    )
                    print(f"{_ERROR_PREFIX}{message}")
                else:
                    message = delete_response.get(
                        "message", "Cron job deleted successfully."
                    )
                    print(f"{_OK_PREFIX}{message}")
                return  # Exit function after attempting delete
            elif confirm in ("no", "n", ""):
                print(f"{_INFO_PREFIX}Cron job not deleted.")
                logger.debug("User canceled deleting cron job at confirmation.")
                return  # Exit function
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")
        # --- End User Interaction ---

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to delete cron job for '{server_name}': {e}", exc_info=True
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error deleting cron job for '{server_name}': {e}",
            exc_info=True,
        )


# ============================
# Windows Task Scheduler Menus
# ============================


def _windows_scheduler(server_name: str, base_dir: str, config_dir: str) -> None:
    """
    Displays the Windows Task Scheduler management menu and handles user interaction.

    Args:
        server_name: The name of the server context.
        base_dir: The base directory for server installations.
        config_dir: The base directory for configuration files.
    """
    logger.debug(f"Entering Windows Task Scheduler menu for server '{server_name}'.")
    while True:
        try:
            os.system("cls")  # Clear screen for Windows
            print(
                f"\n{Fore.MAGENTA}{APP_DISPLAY_NAME} - Windows Task Scheduler{Style.RESET_ALL}"
            )
            print(
                f"{Fore.CYAN}Managing scheduled tasks for server: {Fore.YELLOW}{server_name}{Style.RESET_ALL}\n"
            )

            # API call to get associated task names/paths
            logger.debug(
                f"Calling API: api_task_scheduler.get_server_task_names for '{server_name}'"
            )
            task_names_response = api_task_scheduler.get_server_task_names(
                server_name, config_dir
            )
            logger.debug(f"API get_server_task_names response: {task_names_response}")

            # Display current tasks (or error)
            if task_names_response.get("status") == "error":
                print(
                    f"{_ERROR_PREFIX}{task_names_response.get('message', 'Could not retrieve task list.')}"
                )
            else:
                task_name_path_list = task_names_response.get("task_names", [])
                if task_name_path_list:
                    display_windows_task_table(
                        task_name_path_list
                    )  # Handles printing internally
                else:
                    print(
                        f"{_INFO_PREFIX}No scheduled tasks found associated with this server in the config directory."
                    )

            # --- User Interaction: Menu ---
            print(f"\n{Fore.MAGENTA}Options:{Style.RESET_ALL}")
            print("  1) Add New Task")
            print("  2) Modify Existing Task")
            print("  3) Delete Task")
            print("  4) Back to Advanced Menu")
            # --- End User Interaction ---

            # --- User Interaction: Get Choice ---
            choice = input(
                f"{Fore.CYAN}Select an option [1-4]:{Style.RESET_ALL} "
            ).strip()
            logger.debug(f"Windows scheduler menu choice: '{choice}'")
            # --- End User Interaction ---

            if choice == "1":
                logger.debug("User selected 'Add New Task'.")
                add_windows_task(
                    server_name, base_dir, config_dir
                )  # Handles interaction and API call
                input("\nPress Enter to return to scheduler menu...")
            elif choice == "2":
                logger.debug("User selected 'Modify Existing Task'.")
                modify_windows_task(server_name, base_dir, config_dir)
                input("\nPress Enter to return to scheduler menu...")
            elif choice == "3":
                logger.debug("User selected 'Delete Task'.")
                delete_windows_task(
                    server_name, base_dir, config_dir
                )  # Handles interaction and API call
                input("\nPress Enter to return to scheduler menu...")
            elif choice == "4":
                logger.debug("Exiting Windows scheduler menu.")
                return  # Go back
            else:
                # --- User Interaction: Print Invalid Choice ---
                print(
                    f"{_WARN_PREFIX}Invalid selection '{choice}'. Please choose again."
                )
                # --- End User Interaction ---
                logger.warning(f"Invalid Windows scheduler menu choice: '{choice}'")
                time.sleep(1.5)  # Pause briefly

        except (KeyboardInterrupt, EOFError):
            print("\nReturning to previous menu...")
            logger.debug(
                "Returning to previous menu due to KeyboardInterrupt/EOFError in Windows scheduler."
            )
            return
        except Exception as e:
            # Catch unexpected errors in the menu loop itself
            print(
                f"\n{_ERROR_PREFIX}An unexpected error occurred in the scheduler menu: {e}"
            )
            logger.error(
                f"Error in Windows scheduler menu loop for '{server_name}': {e}",
                exc_info=True,
            )
            input("Press Enter to continue...")


def display_windows_task_table(task_name_path_list: List[Tuple[str, str]]) -> None:
    """
    Displays a formatted table of Windows scheduled tasks using the API.

    Args:
        task_name_path_list: List of tuples, where each is (task_name, xml_file_path).
    """
    if not task_name_path_list:  # Check passed list first
        logger.debug("No task names provided to display_windows_task_table.")
        print(f"{_INFO_PREFIX}No configured tasks found to display.")
        return

    logger.debug(
        f"Preparing to display details for {len(task_name_path_list)} Windows tasks."
    )
    task_names_only = [task[0] for task in task_name_path_list]

    # API call to get detailed info for these tasks
    logger.debug(
        f"Calling API: api_task_scheduler.get_windows_task_info for names: {task_names_only}"
    )
    task_info_response = api_task_scheduler.get_windows_task_info(task_names_only)
    logger.debug(f"API get_windows_task_info response: {task_info_response}")

    # --- User Interaction: Print Table/Messages ---
    if task_info_response.get("status") == "error":
        print(
            f"{_ERROR_PREFIX}{task_info_response.get('message', 'Error retrieving task details.')}"
        )
        logger.error(
            f"CLI: Failed to get Windows task details: {task_info_response.get('message')}"
        )
        return

    task_info_list = task_info_response.get("task_info", [])
    if not task_info_list:
        print(
            f"{_INFO_PREFIX}No details found for configured tasks (they might not be registered in Task Scheduler)."
        )
        return

    # Print header
    print("-" * 80)
    print(f"{'TASK NAME':<35} {'COMMAND':<20} {'SCHEDULE (Readable)':<25}")
    print("-" * 80)

    # Print rows
    for task in task_info_list:
        # Use Fore.RESET to prevent color bleeding
        print(
            f"{Fore.GREEN}{task.get('task_name', 'N/A'):<35}{Style.RESET_ALL}"
            f"{Fore.YELLOW}{task.get('command', 'N/A'):<20}{Style.RESET_ALL}"
            f"{Fore.CYAN}{task.get('schedule', 'N/A'):<25}{Style.RESET_ALL}"
        )

    print("-" * 80)
    # --- End User Interaction ---


def add_windows_task(server_name: str, base_dir: str, config_dir: str) -> None:
    """
    CLI handler function to interactively add a new Windows scheduled task.

    Args:
        server_name: The name of the server context.
        base_dir: The base directory for server installations.
        config_dir: The base directory for configuration files.
    """
    logger.debug(
        f"CLI: Starting interactive 'add Windows task' workflow for server '{server_name}'."
    )
    print(f"\n{_INFO_PREFIX}Add New Windows Scheduled Task")

    try:
        # --- User Interaction: Select Command ---
        print(f"{Fore.MAGENTA}Choose the command to schedule:{Style.RESET_ALL}")
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

        selected_command: Optional[str] = None
        while True:
            try:
                choice_str = input(
                    f"{Fore.CYAN}Select command (1-{len(command_options) + 1}):{Style.RESET_ALL} "
                ).strip()
                choice = int(choice_str)
                logger.debug(f"User command choice: {choice}")
                if 1 <= choice <= len(command_options):
                    selected_command = command_options[choice][
                        1
                    ]  # Get the command slug
                    break
                elif choice == len(command_options) + 1:
                    print(f"{_INFO_PREFIX}Add task canceled.")
                    logger.debug(
                        "User canceled adding Windows task at command selection."
                    )
                    return
                else:
                    print(
                        f"{_WARN_PREFIX}Invalid choice. Please select a valid number."
                    )
            except ValueError:
                print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
                logger.debug(
                    f"User entered non-numeric input for command selection: '{choice_str}'"
                )
        # --- End User Interaction ---

        # Determine command args
        command_args = (
            f"--server {server_name}" if selected_command != "scan-players" else ""
        )

        # Generate task name using API helper
        task_name = api_task_scheduler.create_task_name(server_name, selected_command)
        print(
            f"{_INFO_PREFIX}Generated Task Name: {task_name} (You can change this in Task Scheduler later if needed)"
        )

        # --- User Interaction: Get Triggers ---
        print(f"\n{_INFO_PREFIX}Define trigger(s) for the task:")
        triggers = get_trigger_details()  # Interactive helper function
        if not triggers:
            print(
                f"{_WARN_PREFIX}No triggers defined. Task will only be runnable manually."
            )
            logger.warning(
                f"User did not define any triggers for new task '{task_name}'."
            )
            # Ask user if they want to proceed without triggers
            confirm_no_trigger = (
                input(
                    f"{Fore.CYAN}No triggers defined. Create manually runnable task anyway? (y/n):{Style.RESET_ALL} "
                )
                .strip()
                .lower()
            )
            if confirm_no_trigger not in ("y", "yes"):
                print(f"{_INFO_PREFIX}Add task canceled.")
                logger.debug(
                    "User canceled adding Windows task due to no triggers defined."
                )
                return
        # --- End User Interaction ---

        # --- Call API to Create Task ---
        print(f"\n{_INFO_PREFIX}Creating scheduled task '{task_name}'...")
        logger.debug(
            f"Calling API: api_task_scheduler.create_windows_task for task '{task_name}'"
        )
        create_response = api_task_scheduler.create_windows_task(
            server_name=server_name,
            command=selected_command,
            command_args=command_args,
            task_name=task_name,
            config_dir=config_dir,
            triggers=triggers,
        )
        logger.debug(f"API response from create_windows_task: {create_response}")

        # --- User Interaction: Print Result ---
        if create_response.get("status") == "error":
            message = create_response.get("message", "Unknown error creating task.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(f"CLI: Failed to create Windows task '{task_name}': {message}")
        else:
            message = create_response.get(
                "message", f"Task '{task_name}' created successfully."
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(f"CLI: Create Windows task successful for '{task_name}'.")
        # --- End User Interaction ---

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to add Windows task for '{server_name}': {e}", exc_info=True
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error adding Windows task for '{server_name}': {e}",
            exc_info=True,
        )


def get_trigger_details() -> List[Dict[str, Any]]:
    """
    Interactively gathers trigger details (type, time, days, etc.) from the user.

    Returns:
        A list of trigger dictionaries formatted for the Windows task creation API.
        Returns an empty list if the user cancels or provides no valid triggers.
    """
    triggers: List[Dict[str, Any]] = []
    while True:  # Loop for adding multiple triggers
        # --- User Interaction: Trigger Type Menu ---
        print(f"\n{Fore.MAGENTA}Add Trigger - Choose Type:{Style.RESET_ALL}")
        print("  1) One Time")
        print("  2) Daily")
        print("  3) Weekly")
        print("  4) Monthly")
        print("  5) Done Adding Triggers / Cancel")
        trigger_choice = input(
            f"{Fore.CYAN}Select trigger type (1-5):{Style.RESET_ALL} "
        ).strip()
        logger.debug(f"User trigger type choice: '{trigger_choice}'")
        # --- End User Interaction ---

        trigger_data: Dict[str, Any] = (
            {}
        )  # Holds data for the current trigger being built

        # --- Process Trigger Type Choice ---
        if trigger_choice == "1":
            trigger_data["type"] = "TimeTrigger"
            # Get Start Time
            while True:
                start_str = input(
                    f"{Fore.CYAN}Enter start date and time (YYYY-MM-DD HH:MM):{Style.RESET_ALL} "
                ).strip()
                logger.debug(f"User input for start time: '{start_str}'")
                try:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
                    trigger_data["start"] = start_dt.isoformat(
                        timespec="seconds"
                    )  # ISO format needed by XML
                    break
                except ValueError:
                    print(f"{_ERROR_PREFIX}Invalid format. Please use YYYY-MM-DD HH:MM")
            triggers.append(trigger_data)
            print(f"{_INFO_PREFIX}One Time trigger added.")

        elif trigger_choice == "2":
            trigger_data["type"] = "Daily"
            # Get Start Time
            while True:
                start_str = input(
                    f"{Fore.CYAN}Enter start date and time (YYYY-MM-DD HH:MM):{Style.RESET_ALL} "
                ).strip()
                logger.debug(f"User input for start time: '{start_str}'")
                try:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
                    trigger_data["start"] = start_dt.isoformat(timespec="seconds")
                    break
                except ValueError:
                    print(f"{_ERROR_PREFIX}Invalid format. Please use YYYY-MM-DD HH:MM")
            # Get Interval
            while True:
                try:
                    interval_str = input(
                        f"{Fore.CYAN}Enter interval in days (e.g., 1 for every day):{Style.RESET_ALL} "
                    ).strip()
                    logger.debug(f"User input for daily interval: '{interval_str}'")
                    interval = int(interval_str)
                    if interval >= 1:
                        trigger_data["interval"] = interval
                        break
                    else:
                        print(f"{_WARN_PREFIX}Interval must be 1 or greater.")
                except ValueError:
                    print(f"{_ERROR_PREFIX}Please enter a valid number.")
            triggers.append(trigger_data)
            print(f"{_INFO_PREFIX}Daily trigger added.")

        elif trigger_choice == "3":
            trigger_data["type"] = "Weekly"
            # Get Start Time
            while True:
                start_str = input(
                    f"{Fore.CYAN}Enter start date and time (YYYY-MM-DD HH:MM):{Style.RESET_ALL} "
                ).strip()
                logger.debug(f"User input for start time: '{start_str}'")
                try:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
                    trigger_data["start"] = start_dt.isoformat(timespec="seconds")
                    break
                except ValueError:
                    print(f"{_ERROR_PREFIX}Invalid format. Please use YYYY-MM-DD HH:MM")
            # Get Days of Week
            while True:
                days_str = input(
                    f"{Fore.CYAN}Enter days (comma-separated: Mon, Tue, Wed, Thu, Fri, Sat, Sun or 1-7):{Style.RESET_ALL} "
                ).strip()
                logger.debug(f"User input for weekly days: '{days_str}'")
                days_input_list = [d.strip() for d in days_str.split(",") if d.strip()]
                valid_days_for_api = []
                valid = True
                for day_in in days_input_list:
                    # Validate using the API helper (which raises InvalidInputError)
                    try:
                        day_name_result = api_task_scheduler.get_day_element_name(
                            day_in
                        )  # Returns dict
                        if day_name_result.get("status") == "success":
                            valid_days_for_api.append(
                                day_in
                            )  # Pass original valid input back to API
                        else:
                            print(
                                f"{_ERROR_PREFIX}{day_name_result.get('message', f'Invalid day: {day_in}')}"
                            )
                            valid = False
                    except Exception:  # Catch potential direct raises if API changes
                        print(f"{_ERROR_PREFIX}Invalid day format: {day_in}")
                        valid = False
                if valid and valid_days_for_api:
                    trigger_data["days"] = valid_days_for_api
                    break
                elif not valid_days_for_api:
                    print(f"{_ERROR_PREFIX}Please enter at least one valid day.")
            # Get Interval
            while True:
                try:
                    interval_str = input(
                        f"{Fore.CYAN}Enter interval in weeks (e.g., 1 for every week):{Style.RESET_ALL} "
                    ).strip()
                    logger.debug(f"User input for weekly interval: '{interval_str}'")
                    interval = int(interval_str)
                    if interval >= 1:
                        trigger_data["interval"] = interval
                        break
                    else:
                        print(f"{_WARN_PREFIX}Interval must be 1 or greater.")
                except ValueError:
                    print(f"{_ERROR_PREFIX}Please enter a valid number.")
            triggers.append(trigger_data)
            print(f"{_INFO_PREFIX}Weekly trigger added.")

        elif trigger_choice == "4":
            trigger_data["type"] = "Monthly"
            # Get Start Time
            while True:
                start_str = input(
                    f"{Fore.CYAN}Enter start date and time (YYYY-MM-DD HH:MM):{Style.RESET_ALL} "
                ).strip()
                logger.debug(f"User input for start time: '{start_str}'")
                try:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
                    trigger_data["start"] = start_dt.isoformat(timespec="seconds")
                    break
                except ValueError:
                    print(f"{_ERROR_PREFIX}Invalid format. Please use YYYY-MM-DD HH:MM")
            # Get Days of Month
            while True:
                days_str = input(
                    f"{Fore.CYAN}Enter days of month (comma-separated, 1-31):{Style.RESET_ALL} "
                ).strip()
                logger.debug(f"User input for monthly days: '{days_str}'")
                days_input_list = [d.strip() for d in days_str.split(",") if d.strip()]
                valid_days_for_api = []
                valid = True
                for day_in in days_input_list:
                    try:
                        day_num = int(day_in)
                        if 1 <= day_num <= 31:
                            valid_days_for_api.append(
                                str(day_num)
                            )  # API expects list of strings/ints
                        else:
                            print(
                                f"{_WARN_PREFIX}Day '{day_num}' out of range (1-31). Skipping."
                            )
                            valid = False
                    except ValueError:
                        print(f"{_WARN_PREFIX}Invalid day number '{day_in}'. Skipping.")
                        valid = False
                if valid_days_for_api:
                    trigger_data["days"] = valid_days_for_api
                    break
                else:
                    print(
                        f"{_ERROR_PREFIX}Please enter at least one valid day number (1-31)."
                    )
            # Get Months
            while True:
                months_str = input(
                    f"{Fore.CYAN}Enter months (comma-separated: Jan, Feb,...Dec or 1-12):{Style.RESET_ALL} "
                ).strip()
                logger.debug(f"User input for monthly months: '{months_str}'")
                months_input_list = [
                    m.strip() for m in months_str.split(",") if m.strip()
                ]
                valid_months_for_api = []
                valid = True
                for month_in in months_input_list:
                    try:
                        month_name_result = api_task_scheduler.get_month_element_name(
                            month_in
                        )  # Returns dict
                        if month_name_result.get("status") == "success":
                            valid_months_for_api.append(
                                month_in
                            )  # Pass original valid input
                        else:
                            print(
                                f"{_ERROR_PREFIX}{month_name_result.get('message', f'Invalid month: {month_in}')}"
                            )
                            valid = False
                    except Exception:
                        print(f"{_ERROR_PREFIX}Invalid month format: {month_in}")
                        valid = False
                if valid and valid_months_for_api:
                    trigger_data["months"] = valid_months_for_api
                    break
                elif not valid_months_for_api:
                    print(f"{_ERROR_PREFIX}Please enter at least one valid month.")
            triggers.append(trigger_data)
            print(f"{_INFO_PREFIX}Monthly trigger added.")

        elif trigger_choice == "5":
            logger.debug("User finished adding triggers.")
            break  # Exit trigger addition loop
        else:
            print(
                f"{_WARN_PREFIX}Invalid selection '{trigger_choice}'. Please choose again."
            )
            logger.warning(f"Invalid trigger type choice: '{trigger_choice}'")

    if not triggers:
        logger.warning("No valid triggers were defined by the user.")
    return triggers


def modify_windows_task(server_name: str, base_dir: str, config_dir: str) -> None:
    """
    CLI handler function to interactively select and modify an existing Windows task.

    Currently implements modification by deleting the old task and creating a new one
    with the same command but new trigger details provided by the user.

    Args:
        server_name: The name of the server context.
        base_dir: The base directory for server installations.
        config_dir: The base directory for configuration files.
    """
    logger.debug(
        f"CLI: Starting interactive 'modify Windows task' workflow for server '{server_name}'."
    )
    print(f"\n{_INFO_PREFIX}Modify Existing Windows Scheduled Task")

    if platform.system() != "Windows":
        print(f"{_ERROR_PREFIX}This function is only available on Windows.")
        return

    try:
        # --- Get and Select Task to Modify ---
        logger.debug(
            f"Calling API: api_task_scheduler.get_server_task_names for '{server_name}'"
        )
        task_names_response = api_task_scheduler.get_server_task_names(
            server_name, config_dir
        )
        logger.debug(f"API get_server_task_names response: {task_names_response}")

        if task_names_response.get("status") == "error":
            print(
                f"{_ERROR_PREFIX}{task_names_response.get('message', 'Could not retrieve task list.')}"
            )
            return
        task_name_path_list = task_names_response.get("task_names", [])
        if not task_name_path_list:
            print(
                f"{_INFO_PREFIX}No existing tasks found associated with server '{server_name}' to modify."
            )
            return

        # --- User Interaction: Task Selection Menu ---
        print(f"{Fore.MAGENTA}Select the task to modify:{Style.RESET_ALL}")
        task_map: Dict[int, Tuple[str, str]] = {}
        for i, task_tuple in enumerate(task_name_path_list):
            task_map[i + 1] = task_tuple  # Store (name, path) tuple
            print(f"  {i + 1}. {task_tuple[0]}")  # Display only name
        cancel_option_num = len(task_map) + 1
        print(f"  {cancel_option_num}. Cancel")

        selected_task_tuple: Optional[Tuple[str, str]] = None
        while True:
            try:
                choice_str = input(
                    f"{Fore.CYAN}Enter task number (1-{cancel_option_num}):{Style.RESET_ALL} "
                ).strip()
                choice = int(choice_str)
                logger.debug(f"User choice for task modification: {choice}")
                if 1 <= choice <= len(task_map):
                    selected_task_tuple = task_map[choice]
                    break
                elif choice == cancel_option_num:
                    print(f"{_INFO_PREFIX}Task modification canceled.")
                    logger.debug("User canceled modification at task selection.")
                    return
                else:
                    print(
                        f"{_WARN_PREFIX}Invalid selection. Please choose a valid number."
                    )
            except ValueError:
                print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
                logger.debug(
                    f"User entered non-numeric input for task modification selection: '{choice_str}'"
                )
        # --- End User Interaction ---

        old_task_name, old_task_xml_path = selected_task_tuple
        logger.debug(f"User selected task '{old_task_name}' for modification.")

        # --- Get Existing Details (Command/Args - needed for recreate) ---
        # Note: API function get_windows_task_details requires XML path
        logger.debug(
            f"Calling API: api_task_scheduler.get_windows_task_details for path '{old_task_xml_path}'"
        )
        details_response = api_task_scheduler.get_windows_task_details(
            old_task_xml_path
        )
        logger.debug(f"API get_windows_task_details response: {details_response}")
        if details_response.get("status") != "success":
            print(
                f"{_ERROR_PREFIX}Could not load details for task '{old_task_name}': {details_response.get('message')}"
            )
            logger.error(
                f"Failed to get details for task '{old_task_name}' needed for modification."
            )
            return

        # Extract needed info for recreation (original command slug, original args)
        existing_details = details_response.get("task_details", {})
        original_command_slug = existing_details.get("base_command")
        original_command_args = existing_details.get("command_args")

        if not original_command_slug:
            print(
                f"{_ERROR_PREFIX}Could not determine original command from task '{old_task_name}'. Cannot modify."
            )
            logger.error(
                f"Failed to extract base_command for modification of task '{old_task_name}'."
            )
            return
        logger.debug(
            f"Original task command='{original_command_slug}', args='{original_command_args}'"
        )

        # --- User Interaction: Get New Triggers ---
        print(
            f"\n{_INFO_PREFIX}Define NEW trigger(s) for the task (old triggers will be replaced):"
        )
        new_triggers = get_trigger_details()  # Interactive helper function
        if not new_triggers:
            print(f"{_WARN_PREFIX}No new triggers defined. Task modification canceled.")
            logger.warning(
                f"User did not define any triggers for modified task '{old_task_name}'. Canceling."
            )
            return
        # --- End User Interaction ---

        # --- Call API to Modify (Delete + Recreate with new name/triggers) ---
        # The modify API function generates the new name internally
        print(f"\n{_INFO_PREFIX}Modifying scheduled task '{old_task_name}'...")
        logger.debug(
            f"Calling API: api_task_scheduler.modify_windows_task for old task '{old_task_name}'"
        )
        modify_response = api_task_scheduler.modify_windows_task(
            old_task_name=old_task_name,
            server_name=server_name,
            command=original_command_slug,
            command_args=original_command_args,
            new_task_name=old_task_name,
            config_dir=config_dir,
            triggers=new_triggers,
        )
        logger.debug(f"API response from modify_windows_task: {modify_response}")

        # --- User Interaction: Print Result ---
        if modify_response.get("status") == "error":
            message = modify_response.get("message", "Unknown error modifying task.")
            print(f"{_ERROR_PREFIX}{message}")
            logger.error(
                f"CLI: Failed to modify Windows task '{old_task_name}': {message}"
            )
        else:
            new_task_name = modify_response.get(
                "new_task_name", old_task_name
            )  # Get potentially new name
            message = modify_response.get(
                "message",
                f"Task '{old_task_name}' modified successfully (new name: '{new_task_name}').",
            )
            print(f"{_OK_PREFIX}{message}")
            logger.debug(
                f"CLI: Modify Windows task successful. Old='{old_task_name}', New='{new_task_name}'."
            )
        # --- End User Interaction ---

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to modify Windows task for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error modifying Windows task for '{server_name}': {e}",
            exc_info=True,
        )


def delete_windows_task(server_name: str, base_dir: str, config_dir: str) -> None:
    """
    CLI handler function to interactively select and delete an existing Windows task.

    Args:
        server_name: The name of the server context.
        base_dir: The base directory for server installations (unused here but kept for consistency).
        config_dir: The base directory for configuration files.
    """
    logger.debug(
        f"CLI: Starting interactive 'delete Windows task' workflow for server '{server_name}'."
    )
    print(f"\n{_INFO_PREFIX}Delete Existing Windows Scheduled Task")

    if platform.system() != "Windows":
        print(f"{_ERROR_PREFIX}This function is only available on Windows.")
        return

    try:
        # --- Get and Select Task to Delete ---
        logger.debug(
            f"Calling API: api_task_scheduler.get_server_task_names for '{server_name}'"
        )
        task_names_response = api_task_scheduler.get_server_task_names(
            server_name, config_dir
        )
        logger.debug(f"API get_server_task_names response: {task_names_response}")

        if task_names_response.get("status") == "error":
            print(
                f"{_ERROR_PREFIX}{task_names_response.get('message', 'Could not retrieve task list.')}"
            )
            return
        task_name_path_list = task_names_response.get("task_names", [])
        if not task_name_path_list:
            print(
                f"{_INFO_PREFIX}No existing tasks found associated with server '{server_name}' to delete."
            )
            return

        # --- User Interaction: Task Selection Menu ---
        print(f"{Fore.MAGENTA}Select the task to delete:{Style.RESET_ALL}")
        task_map: Dict[int, Tuple[str, str]] = {}
        for i, task_tuple in enumerate(task_name_path_list):
            task_map[i + 1] = task_tuple  # Store (name, path) tuple
            print(f"  {i + 1}. {task_tuple[0]}")  # Display name
        cancel_option_num = len(task_map) + 1
        print(f"  {cancel_option_num}. Cancel")

        selected_task_tuple: Optional[Tuple[str, str]] = None
        while True:
            try:
                choice_str = input(
                    f"{Fore.CYAN}Enter task number (1-{cancel_option_num}):{Style.RESET_ALL} "
                ).strip()
                choice = int(choice_str)
                logger.debug(f"User choice for task deletion: {choice}")
                if 1 <= choice <= len(task_map):
                    selected_task_tuple = task_map[choice]
                    break
                elif choice == cancel_option_num:
                    print(f"{_INFO_PREFIX}Task deletion canceled.")
                    logger.debug("User canceled deletion at task selection.")
                    return
                else:
                    print(
                        f"{_WARN_PREFIX}Invalid selection. Please choose a valid number."
                    )
            except ValueError:
                print(f"{_WARN_PREFIX}Invalid input. Please enter a number.")
                logger.debug(
                    f"User entered non-numeric input for task deletion selection: '{choice_str}'"
                )
        # --- End User Interaction ---

        task_name_to_delete, task_file_path_to_delete = selected_task_tuple
        logger.debug(f"User selected task '{task_name_to_delete}' for deletion.")

        # --- User Interaction: Confirmation ---
        print(
            f"\n{_WARN_PREFIX}You selected task '{task_name_to_delete}' for deletion."
        )
        while True:
            confirm = (
                input(
                    f"{Fore.RED}Are you sure you want to delete this task? (y/n):{Style.RESET_ALL} "
                )
                .strip()
                .lower()
            )
            logger.debug(f"User confirmation for delete Windows task: '{confirm}'")
            if confirm in ("yes", "y"):
                # --- Call API to Delete ---
                logger.debug(
                    f"Calling API: api_task_scheduler.delete_windows_task for task '{task_name_to_delete}'"
                )
                delete_response = api_task_scheduler.delete_windows_task(
                    task_name_to_delete, task_file_path_to_delete
                )
                logger.debug(
                    f"API response from delete_windows_task: {delete_response}"
                )

                if delete_response.get("status") == "error":
                    message = delete_response.get(
                        "message", "Unknown error deleting task."
                    )
                    print(f"{_ERROR_PREFIX}{message}")
                else:
                    message = delete_response.get(
                        "message", "Task deleted successfully."
                    )
                    print(f"{_OK_PREFIX}{message}")
                return  # Exit function after attempting delete
            elif confirm in ("no", "n", ""):
                print(f"{_INFO_PREFIX}Task not deleted.")
                logger.debug("User canceled deleting Windows task at confirmation.")
                return  # Exit function
            else:
                print(f"{_WARN_PREFIX}Invalid input. Please answer 'yes' or 'no'.")
        # --- End User Interaction ---

    except (InvalidServerNameError, FileOperationError) as e:
        print(f"{_ERROR_PREFIX}{e}")
        logger.error(
            f"CLI: Failed to delete Windows task for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:
        print(f"{_ERROR_PREFIX}An unexpected error occurred: {e}")
        logger.error(
            f"CLI: Unexpected error deleting Windows task for '{server_name}': {e}",
            exc_info=True,
        )
