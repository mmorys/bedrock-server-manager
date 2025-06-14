# bedrock_server_manager/cli/task_scheduler.py
"""
Click command group for managing scheduled tasks for servers.

Provides an interactive, platform-aware interface for creating, viewing,
and deleting scheduled tasks via cron (Linux) or Task Scheduler (Windows).
"""

import logging
import platform
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

import click
import questionary
from questionary import Validator, ValidationError

from bedrock_server_manager.api import task_scheduler as api_task_scheduler
from bedrock_server_manager.config.const import EXPATH
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)

# --- Helper Functions and Validators ---


class CronTimeValidator(Validator):
    """Ensures cron time input is not empty."""

    def validate(self, document):
        if not document.text.strip():
            raise ValidationError(
                message="Input cannot be empty. Use '*' for any value.",
                cursor_position=0,
            )


class TimeValidator(Validator):
    """Validates that text is in HH:MM format."""

    def validate(self, document):
        try:
            time.strptime(document.text, "%H:%M")
        except ValueError:
            raise ValidationError(
                message="Please enter time in HH:MM format (e.g., 09:30 or 22:00).",
                cursor_position=len(document.text),
            )


def _handle_api_response(response: Dict[str, Any], success_msg: str):
    """Handles API responses, showing success or error messages."""
    if response.get("status") == "error":
        click.secho(f"Error: {response.get('message', 'Unknown error')}", fg="red")
        raise click.Abort()
    else:
        message = response.get("message", success_msg)
        click.secho(f"Success: {message}", fg="green")


def _get_windows_triggers_interactively() -> List[Dict[str, Any]]:
    """
    Interactively guides the user to create one or more triggers for a Windows task.
    This version correctly generates a full ISO datetime string for the API.
    """
    triggers = []
    click.secho("\n--- Configure Task Triggers ---", bold=True)
    click.echo("A task can have multiple triggers (e.g., run daily AND weekly).")

    while True:
        trigger_type = questionary.select(
            "Add a trigger type:", choices=["Daily", "Weekly", "Done Adding Triggers"]
        ).ask()

        if trigger_type is None or trigger_type == "Done Adding Triggers":
            break

        start_time_str = questionary.text(
            "Enter start time (HH:MM):", validate=TimeValidator()
        ).ask()
        if start_time_str is None:
            continue  # User cancelled time entry

        # 1. Parse the user's time input
        start_time_obj = datetime.strptime(start_time_str, "%H:%M").time()

        # 2. Get the current date and time
        now = datetime.now()

        # 3. Combine today's date with the user's desired time
        start_datetime = now.replace(
            hour=start_time_obj.hour,
            minute=start_time_obj.minute,
            second=0,
            microsecond=0,
        )

        # 4. If that time has already passed today, set the start date to tomorrow
        if start_datetime < now:
            start_datetime += timedelta(days=1)
            click.secho(
                f"Info: Time has passed for today, scheduling to start tomorrow.",
                fg="cyan",
            )

        # 5. Format into the full YYYY-MM-DDTHH:MM:SS string the API needs
        start_boundary_iso = start_datetime.isoformat(timespec="seconds")

        # We will store both the API-compliant string and the user-friendly display string
        trigger_data = {
            "type": trigger_type,
            "start": start_boundary_iso,  # For the API
            "start_time_display": start_time_str,  # For the UI summary
        }

        if trigger_type == "Weekly":
            days = questionary.checkbox(
                "Select days of the week:",
                choices=[
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ],
            ).ask()
            if not days:
                click.secho(
                    "Warning: No days selected for weekly trigger. Trigger not added.",
                    fg="yellow",
                )
                continue
            trigger_data["days_of_week"] = days

        triggers.append(trigger_data)
        click.secho(
            f"Success: {trigger_type} trigger for {start_time_str} added.", fg="green"
        )

    return triggers


# --- Platform-Specific Display and Logic ---


def _display_cron_table(cron_jobs: List[str]):
    """Displays a formatted table of cron jobs."""
    table_resp = api_task_scheduler.get_cron_jobs_table(cron_jobs)
    if not table_resp.get("table_data"):
        click.secho("No scheduled cron jobs found for this server.", fg="cyan")
        return
    click.secho(
        f"{'SCHEDULE (Raw)':<20} {'SCHEDULE (Readable)':<25} {'COMMAND'}", bold=True
    )
    click.echo("-" * 80)
    for job in table_resp["table_data"]:
        raw = f"{job['minute']} {job['hour']} {job['day_of_month']} {job['month']} {job['day_of_week']}"
        click.echo(
            f"{click.style(raw, fg='green'):<32} {click.style(job.get('schedule_time', 'N/A'), fg='cyan'):<25} {click.style(job.get('command_display', 'N/A'), fg='yellow')}"
        )
    click.echo("-" * 80)


def _display_windows_task_table(task_info_list: List[Dict]):
    """Displays a formatted table of Windows scheduled tasks."""
    if not task_info_list:
        click.secho("No scheduled tasks found for this server.", fg="cyan")
        return
    click.secho(f"{'TASK NAME':<40} {'COMMAND':<25} {'SCHEDULE'}", bold=True)
    click.echo("-" * 90)
    for task in task_info_list:
        click.echo(
            f"{click.style(task.get('task_name', 'N/A'), fg='green'):<52} {click.style(task.get('command', 'N/A'), fg='yellow'):<25} {click.style(task.get('schedule', 'N/A'), fg='cyan')}"
        )
    click.echo("-" * 90)


def _get_command_to_schedule(
    server_name: str, for_windows: bool
) -> Optional[Tuple[str, str]]:
    """Prompts user to select a command, returns its description and slug."""
    choices = {
        "Update Server": "update-server",
        "Backup Server (All)": "backup create --type all",
        "Start Server": "server start",
        "Stop Server": "server stop",
        "Restart Server": "server restart",
        "Scan Players": "player scan",
    }
    selection = questionary.select(
        "Choose the command to schedule:", choices=list(choices.keys()) + ["Cancel"]
    ).ask()
    if not selection or selection == "Cancel":
        return None

    command_slug = choices[selection]
    if for_windows:
        return selection, command_slug

    args = f'--server "{server_name}"' if "player" not in command_slug else ""
    full_command = f"{EXPATH} {command_slug} {args}".strip()
    return selection, full_command


def _add_cron_job(server_name: str):
    """Interactive workflow to add a new cron job."""
    _, command = _get_command_to_schedule(server_name, for_windows=False) or (
        None,
        None,
    )
    if not command:
        raise click.Abort()

    click.secho("\nEnter schedule details (* for any value):", bold=True)
    m = questionary.text("Minute (0-59):", validate=CronTimeValidator()).ask()
    h = questionary.text("Hour (0-23):", validate=CronTimeValidator()).ask()
    dom = questionary.text("Day of Month (1-31):", validate=CronTimeValidator()).ask()
    mon = questionary.text("Month (1-12):", validate=CronTimeValidator()).ask()
    dow = questionary.text(
        "Day of Week (0-7, 0/7=Sun):", validate=CronTimeValidator()
    ).ask()
    if any(p is None for p in [m, h, dom, mon, dow]):
        raise click.Abort()

    new_cron = f"{m} {h} {dom} {mon} {dow} {command}"
    if questionary.confirm(f"Add this cron job?\n  {new_cron}", default=True).ask():
        resp = api_task_scheduler.add_cron_job(new_cron)
        _handle_api_response(resp, "Cron job added.")
    else:
        click.secho("Operation cancelled.", fg="yellow")


def _add_windows_task(server_name: str):
    """Interactive workflow to add a new Windows task."""
    desc, command_slug = _get_command_to_schedule(server_name, for_windows=True) or (
        None,
        None,
    )
    if not command_slug:
        raise click.Abort()

    triggers = _get_windows_triggers_interactively()
    if not triggers:
        if not questionary.confirm(
            "No triggers defined. Create a manually runnable task?", default=False
        ).ask():
            click.secho("Task creation cancelled.", fg="yellow")
            return

    task_name = api_task_scheduler.create_task_name(server_name, desc)
    command_args = f'--server "{server_name}"' if "player" not in command_slug else ""

    click.secho(f"\nSummary of the task to be created:", bold=True)
    click.echo(f"  Task Name: {task_name}")
    click.echo(f"  Command: {command_slug} {command_args}")
    if triggers:
        click.echo("  Triggers:")
        for t in triggers:
            display_time = t["start_time_display"]
            if t["type"] == "Daily":
                click.echo(f"    - Daily at {display_time}")
            elif t["type"] == "Weekly":
                days_str = ", ".join(t["days_of_week"])
                click.echo(f"    - Weekly on {days_str} at {display_time}")
    else:
        click.echo("  Triggers: None (manual run only)")

    if questionary.confirm(f"\nCreate this task?", default=True).ask():
        resp = api_task_scheduler.create_windows_task(
            server_name=server_name,
            command=command_slug,
            command_args=command_args,
            task_name=task_name,
            triggers=triggers,
        )
        _handle_api_response(resp, "Windows task created.")
    else:
        click.secho("Operation cancelled.", fg="yellow")


# --- Main Click Group and Commands ---


@click.group(invoke_without_command=True)
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="The target server for scheduling.",
)
@click.pass_context
def schedule(ctx, server_name: str):
    """Manage scheduled tasks (cron/Windows Task Scheduler)."""
    os_type = platform.system()
    if os_type not in ("Linux", "Windows"):
        click.secho(
            f"Task scheduling is not supported on this OS ({os_type}).", fg="red"
        )
        return
    ctx.obj = {"server_name": server_name, "os_type": os_type}
    if ctx.invoked_subcommand is None:
        while True:
            try:
                click.clear()
                click.secho(
                    f"--- Task Scheduler for Server: {server_name} ---", bold=True
                )
                ctx.invoke(list_tasks)
                choice = questionary.select(
                    "\nSelect an option:",
                    choices=["Add New Task", "Delete Task", "Exit"],
                ).ask()
                if not choice or choice == "Exit":
                    break
                if choice == "Add New Task":
                    ctx.invoke(add_task)
                if choice == "Delete Task":
                    ctx.invoke(delete_task)
            except (click.Abort, KeyboardInterrupt):
                break
        click.secho("Exiting scheduler menu.", fg="cyan")


@schedule.command("list")
@click.pass_context
def list_tasks(ctx):
    """List all scheduled tasks for the server."""
    server_name, os_type = ctx.obj["server_name"], ctx.obj["os_type"]
    if os_type == "Linux":
        resp = api_task_scheduler.get_server_cron_jobs(server_name)
        _display_cron_table(resp.get("cron_jobs", []))
    elif os_type == "Windows":
        task_names_resp = api_task_scheduler.get_server_task_names(server_name)
        task_info_resp = api_task_scheduler.get_windows_task_info(
            [t[0] for t in task_names_resp.get("task_names", [])]
        )
        _display_windows_task_table(task_info_resp.get("task_info", []))


@schedule.command("add")
@click.pass_context
def add_task(ctx):
    """Interactively add a new scheduled task."""
    server_name, os_type = ctx.obj["server_name"], ctx.obj["os_type"]
    try:
        if os_type == "Linux":
            _add_cron_job(server_name)
        elif os_type == "Windows":
            _add_windows_task(server_name)
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nAdd operation cancelled.", fg="yellow")


@schedule.command("delete")
@click.pass_context
def delete_task(ctx):
    """Interactively delete an existing scheduled task."""
    server_name, os_type = ctx.obj["server_name"], ctx.obj["os_type"]
    try:
        if os_type == "Linux":
            resp, jobs = api_task_scheduler.get_server_cron_jobs(server_name), []
            if resp.get("status") == "success":
                jobs = resp.get("cron_jobs", [])
            if not jobs:
                click.secho("No jobs to delete.", fg="yellow")
                return
            job_to_delete = questionary.select(
                "Select job to delete:", choices=jobs + ["Cancel"]
            ).ask()
            if job_to_delete and job_to_delete != "Cancel":
                if questionary.confirm(
                    f"Delete this job?\n  {job_to_delete}", default=False
                ).ask():
                    _handle_api_response(
                        api_task_scheduler.delete_cron_job(job_to_delete),
                        "Job deleted.",
                    )
        elif os_type == "Windows":
            resp, tasks = api_task_scheduler.get_server_task_names(server_name), []
            if resp.get("status") == "success":
                tasks = resp.get("task_names", [])
            if not tasks:
                click.secho("No tasks to delete.", fg="yellow")
                return
            task_map = {t[0]: t for t in tasks}
            task_name_to_delete = questionary.select(
                "Select task to delete:", choices=list(task_map.keys()) + ["Cancel"]
            ).ask()
            if task_name_to_delete and task_name_to_delete != "Cancel":
                if questionary.confirm(
                    f"Delete task '{task_name_to_delete}'?", default=False
                ).ask():
                    _, file_path = task_map[task_name_to_delete]
                    _handle_api_response(
                        api_task_scheduler.delete_windows_task(
                            task_name_to_delete, file_path
                        ),
                        "Task deleted.",
                    )
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nDelete operation cancelled.", fg="yellow")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    schedule()
