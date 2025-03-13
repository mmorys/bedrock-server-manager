# bedrock-server-manager/bedrock_server_manager/core/system/linux.py
import platform
import os
import logging
import subprocess
import getpass
import time
from datetime import datetime
from colorama import Fore, Style
from bedrock_server_manager.config import settings
from bedrock_server_manager.core.error import (
    CommandNotFoundError,
    SystemdReloadError,
    ServiceError,
    InvalidServerNameError,
    ScheduleError,
    InvalidCronJobError,
    ServerStartError,
    ServerStopError,
)

logger = logging.getLogger("bedrock_server_manager")


def check_service_exists(server_name):
    """Checks if a systemd service file exists for the given server.

    Args:
        server_name (str): The name of the server.

    Returns:
        bool: True if the service file exists, False otherwise.
    """
    if platform.system() != "Linux":
        return False  # systemd is primarily Linux-specific

    service_name = f"bedrock-{server_name}"
    service_file = os.path.join(
        os.path.expanduser("~"), ".config", "systemd", "user", f"{service_name}.service"
    )
    return os.path.exists(service_file)


def enable_user_lingering():
    """Enables user lingering on Linux (systemd systems).

    This is required for user services to start on boot and run after logout.
    On non-Linux systems, this function does nothing.

    Raises:
        CommandNotFoundError: If loginctl or sudo is not found.
        SystemdReloadError: If enabling lingering fails.
    """
    if platform.system() != "Linux":
        return  # Not applicable

    username = getpass.getuser()

    # Check if lingering is already enabled
    try:
        result = subprocess.run(
            ["loginctl", "show-user", username],
            capture_output=True,
            text=True,
            check=False,
        )
        if "Linger=yes" in result.stdout:
            logger.debug(f"Lingering is already enabled for {username}")
            return  # Already enabled
    except FileNotFoundError:
        raise CommandNotFoundError(
            "loginctl",
            message="loginctl command not found. Lingering cannot be checked/enabled.",
        ) from None

    # If not already enabled, try to enable it
    logger.debug(f"Attempting to enable lingering for user {username}")
    try:
        subprocess.run(
            ["sudo", "loginctl", "enable-linger", username],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Lingering enabled for {username}")
    except subprocess.CalledProcessError as e:
        raise SystemdReloadError(
            f"Failed to enable lingering for {username}.  Error: {e}"
        ) from e
    except FileNotFoundError:
        raise CommandNotFoundError(
            "loginctl or sudo",
            message="loginctl or sudo command not found. Lingering cannot be enabled.",
        ) from None


def _create_systemd_service(server_name, base_dir, autoupdate):
    """Creates a systemd service file (Linux-specific).

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory for servers.
        autoupdate (bool): Whether to enable auto-update on start.

    Raises:
        InvalidServerNameError: If the server name is invalid.
        ServiceError: If there is an error creating the service file.
        CommandNotFoundError: If systemctl is not found.
        SystemdReloadError: If systemd fails to reload.

    """
    if platform.system() != "Linux":
        return  # Not applicable

    if not server_name:
        raise InvalidServerNameError("_create_systemd_service: server_name is empty.")

    server_dir = os.path.join(base_dir, server_name)
    service_name = f"bedrock-{server_name}"
    service_file = os.path.join(
        os.path.expanduser("~"), ".config", "systemd", "user", f"{service_name}.service"
    )

    systemd_dir = os.path.join(os.path.expanduser("~"), ".config", "systemd", "user")
    # Catch OSError when creating directories
    try:
        os.makedirs(systemd_dir, exist_ok=True)
    except OSError as e:
        raise ServiceError(
            f"Failed to create systemd directory: {systemd_dir}: {e}"
        ) from e

    if os.path.exists(service_file):
        logger.debug(f"Reconfiguring service file for {server_name} at {service_file}")

    autoupdate_cmd = ""
    if autoupdate:
        autoupdate_cmd = (
            f"ExecStartPre={settings.EXPATH} update-server --server {server_name}"
        )
        logger.debug("Auto-update enabled on start.")
    else:
        logger.debug("Auto-update disabled on start.")

    service_content = f"""[Unit]
Description=Minecraft Bedrock Server: {server_name}
After=network.target

[Service]
Type=forking
WorkingDirectory={server_dir}
Environment="PATH=/usr/bin:/bin:/usr/sbin:/sbin"
{autoupdate_cmd}
ExecStart={settings.EXPATH} systemd-start --server {server_name}
ExecStop={settings.EXPATH} systemd-stop --server {server_name}
ExecReload={settings.EXPATH} systemd-stop --server {server_name} && {settings.EXPATH} systemd-start --server {server_name}
Restart=always
RestartSec=10
StartLimitIntervalSec=500
StartLimitBurst=3

[Install]
WantedBy=default.target
"""
    try:
        with open(service_file, "w") as f:
            f.write(service_content)
        logger.info(f"Systemd service created for {server_name}")

        # Reload systemd
        try:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
            logger.debug("systemd daemon reloaded.")
        except subprocess.CalledProcessError as e:
            raise SystemdReloadError(f"Failed to reload systemd daemon: {e}") from e
        except FileNotFoundError:
            raise CommandNotFoundError(
                "systemctl",
                message="systemctl command not found.  Is systemd installed?",
            ) from None

    except OSError as e:
        raise ServiceError(
            f"Failed to write systemd service file: {service_file}: {e}"
        ) from e


def _enable_systemd_service(server_name):
    """Enables a systemd service (Linux-specific).

    Args:
        server_name (str): The name of the server.
    Raises:
        InvalidServerNameError: If server_name is empty.
        ServiceError: If the service cannot be enabled or does not exists.
        CommandNotFoundError: If systemctl is not found
    """
    if platform.system() != "Linux":
        return  # Not applicable

    if not server_name:
        raise InvalidServerNameError("_enable_systemd_service: server_name is empty.")

    service_name = f"bedrock-{server_name}"

    if not check_service_exists(server_name):
        raise ServiceError(
            f"Service file for {server_name} does not exist. Cannot enable."
        )

    try:
        # Check if service is enabled
        result = subprocess.run(
            ["systemctl", "--user", "is-enabled", service_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:  # Already enabled
            logger.debug(f"Service {service_name} is already enabled.")
            return
    except FileNotFoundError:
        raise CommandNotFoundError(
            "systemctl",
            message="systemctl command not found, make sure you are on a systemd system",
        ) from None

    try:
        subprocess.run(["systemctl", "--user", "enable", service_name], check=True)
        logger.info(f"Autostart for {server_name} enabled successfully.")
    except subprocess.CalledProcessError as e:
        raise ServiceError(f"Failed to enable {server_name}: {e}") from e


def _disable_systemd_service(server_name):
    """Disables a systemd service (Linux-specific).

    Args:
        server_name (str): The name of the server.

    Raises:
        InvalidServerNameError: If server_name is empty.
        ServiceError: If disabling the service fails.
        CommandNotFoundError: If systemctl is not found.
    """
    if platform.system() != "Linux":
        return  # Not applicable

    if not server_name:
        raise InvalidServerNameError("_disable_systemd_service: server_name is empty.")

    service_name = f"bedrock-{server_name}"

    if not check_service_exists(server_name):
        logger.debug(
            f"Service file for {server_name} does not exist.  No need to disable."
        )
        return

    try:
        # Check if service is disabled
        result = subprocess.run(
            ["systemctl", "--user", "is-enabled", service_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:  # Disabled or not found
            logger.debug(f"Service {service_name} is already disabled.")
            return
    except FileNotFoundError:
        raise CommandNotFoundError(
            "systemctl",
            message="systemctl command not found, make sure you are on a systemd system",
        ) from None

    try:
        subprocess.run(["systemctl", "--user", "disable", service_name], check=True)
        logger.info(f"Server {service_name} disabled successfully.")
    except subprocess.CalledProcessError as e:
        raise ServiceError(f"Failed to disable {server_name}: {e}") from e


def _systemd_start_server(server_name, server_dir):
    """Starts the Bedrock server within a screen session (Linux-specific).

    Args:
        server_name (str): The name of the server.
        server_dir (str): The server directory.

    Raises:
        ServerStartError: If the server fails to start.
        CommandNotFoundError: If the 'screen' command is not found.
    """

    # Clear server_output.txt
    try:
        with open(os.path.join(server_dir, "server_output.txt"), "w") as f:
            f.write("Starting Server\n")
    except OSError:
        logger.warning("Failed to truncate server_output.txt.  Continuing...")
        # Not critical, so don't raise an exception.

    screen_command = [
        "screen",
        "-dmS",
        f"bedrock-{server_name}",
        "-L",
        "-Logfile",
        os.path.join(server_dir, "server_output.txt"),
        "bash",
        "-c",
        f'cd "{server_dir}" && exec ./bedrock_server',
    ]

    try:
        subprocess.run(screen_command, check=True)
        logger.info(f"Server {server_name} started in screen session.")
    except subprocess.CalledProcessError as e:
        raise ServerStartError(f"Failed to start server with screen: {e}") from e
    except FileNotFoundError:
        raise CommandNotFoundError(
            "screen", message="screen command not found.  Is screen installed?"
        ) from None


def _systemd_stop_server(server_name, server_dir):
    """Stops the Bedrock server running in a screen session (Linux-specific).

    Args:
        server_name (str): The name of the server.
        server_dir (str): The server directory

    Raises:
        ServerStopError: If the server fails to stop.
        CommandNotFoundError: If pgrep or screen is not found
    """
    logger.debug(f"Stopping server {server_name}...")

    # Find and kill the screen session.
    try:
        # Use pgrep to find the screen session.
        result = subprocess.run(
            ["pgrep", "-f", f"bedrock-{server_name}"],
            capture_output=True,
            text=True,
            check=False,  # Don't raise exception if not found
        )

        if result.returncode == 0:
            screen_pid = result.stdout.strip()
            logger.debug(f"Found screen PID: {screen_pid}")

            # Send the "stop" command to the Bedrock server *via screen*
            subprocess.run(
                ["screen", "-S", f"bedrock-{server_name}", "-X", "stuff", "stop\n"],
                check=False,  # Don't raise if screen session doesn't exist
            )
            # Give the server some time to stop
            time.sleep(10)
        else:
            logger.warning(
                f"No screen session found for 'bedrock-{server_name}'.  It may already be stopped."
            )

    except FileNotFoundError:
        raise CommandNotFoundError(
            "pgrep or screen", message="pgrep or screen command not found."
        ) from None
    except Exception as e:
        raise ServerStopError(f"An unexpected error occurred: {e}") from e


def get_server_cron_jobs(server_name):
    """Retrieves cron jobs for a specific server.

    Args:
        server_name (str): The name of the server.

    Returns:
        list: A list of strings, each representing a cron job line,
              or an empty list if no jobs are found.
    Raises:
        InvalidServerNameError: If the server name is invalid.
        CommandNotFoundError: If the crontab command is not found.
        ScheduleError: If there is an error listing cron jobs.
    """
    if platform.system() != "Linux":
        logger.debug("Cron jobs are only supported on Linux.")
        return []

    if not server_name:
        raise InvalidServerNameError("get_server_cron_jobs: server_name is empty.")

    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, check=False
        )

        if result.returncode == 1 and "no crontab for" in result.stderr.lower():
            logger.debug("No crontab for current user.")
            return []
        elif result.returncode != 0:
            # Other error
            raise ScheduleError(f"Error running crontab -l: {result.stderr}")

        cron_jobs = result.stdout
        # Filter for lines related to the specific server.
        filtered_jobs = []
        for line in cron_jobs.splitlines():
            if f"--server {server_name}" in line or "scan-players" in line:
                filtered_jobs.append(line)

        if not filtered_jobs:
            logger.warning(
                Fore.YELLOW
                + f"No scheduled cron jobs found for {server_name}."
                + Style.RESET_ALL
            )
            return "undefined"  # No jobs found for this server

        return filtered_jobs

    except FileNotFoundError:
        raise CommandNotFoundError(
            "crontab", message="crontab command not found.  Is cron installed?"
        ) from None
    except Exception as e:
        raise ScheduleError(f"An unexpected error occurred: {e}") from e


def _parse_cron_line(line):
    """Parses a single cron job line into its components.

    Args:
        line (str): A single line from the crontab output.

    Returns:
        tuple or None: A tuple containing (minute, hour, day_of_month, month,
                       day_of_week, command), or None if the line is invalid.
    """
    parts = line.split()
    if len(parts) < 6:
        return None  # Invalid cron line

    minute, hour, day_of_month, month, day_of_week = parts[:5]
    command = " ".join(parts[5:])  # Reassemble the command
    return minute, hour, day_of_month, month, day_of_week, command


def _format_cron_command(command):
    """Formats the command part of a cron job for display.

    Args:
        command (str): The full command string from the cron job.

    Returns:
        str: The formatted command string.
    """
    # Strip leading and trailing whitespace first
    command = command.strip()

    # Convert script path to string if it's a PosixPath
    script_path = str(settings.EXPATH)

    # Remove the script path if it appears at the start of the command
    if command.startswith(script_path):
        command = command[len(script_path) :].strip()

    # Split the command into parts
    parts = command.split()

    # Skip any parts that are python executables or empty
    filtered_parts = [
        part
        for part in parts
        if part and not part.endswith("python") and not part.endswith(".exe")
    ]

    # The first remaining part should be the actual command (like 'backup')
    return filtered_parts[0] if filtered_parts else ""


def get_cron_jobs_table(cron_jobs):
    """Formats cron jobs into a list of dictionaries for display.

     Args:
        cron_jobs (list): A list of cron job strings, as returned by
                          get_server_cron_jobs.

    Returns:
        list: A list of dictionaries, where each dictionary represents a
              cron job.
    """

    table_data = []
    if not cron_jobs:
        return table_data

    for line in cron_jobs:
        parsed_job = _parse_cron_line(line)
        if parsed_job:
            minute, hour, day_of_month, month, day_of_week, command = parsed_job
            schedule_time = convert_to_readable_schedule(
                month, day_of_month, hour, minute, day_of_week
            )
            if schedule_time is None:
                schedule_time = "Invalid Schedule"

            command = _format_cron_command(command)
            table_data.append(
                {
                    "minute": minute,
                    "hour": hour,
                    "day_of_month": day_of_month,
                    "month": month,
                    "day_of_week": day_of_week,
                    "command": command,
                    "schedule_time": schedule_time,
                }
            )
    return table_data


def _add_cron_job(cron_string):
    """Adds a cron job to the user's crontab. (Linux-specific)

    Args:
        cron_string (str): The complete cron job string (e.g., "0 2 * * * command").
    Raises:
        CommandNotFoundError: If 'crontab' command not found
        ScheduleError: If adding the cron job fails.
    """
    if platform.system() != "Linux":
        return

    try:
        # Get existing cron jobs
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, check=False
        )
        existing_crontab = result.stdout
        if result.returncode != 0:
            if "no crontab for" in result.stderr.lower():
                existing_crontab = ""  # Start with an empty crontab
            else:
                raise ScheduleError(f"Error running crontab -l: {result.stderr}")

        # Add the new job and write back to crontab
        new_crontab = existing_crontab + cron_string + "\n"
        process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        process.communicate(input=new_crontab)
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, "crontab")
        logger.debug(f"Cron job added: {cron_string}")
    except subprocess.CalledProcessError as e:
        raise ScheduleError(f"Failed to add cron job: {e}") from e
    except FileNotFoundError:
        raise CommandNotFoundError(
            "crontab", message="crontab command not found"
        ) from None
    except Exception as e:
        raise ScheduleError(f"An unexpected error: {e}") from e


def validate_cron_input(value, min_val, max_val):
    """Validates a single cron input value (minute, hour, day, month, weekday).

    Args:
        value (str): The value to validate (e.g., "1", "5-10", "*").
        min_val (int): The minimum allowed value.
        max_val (int): The maximum allowed value.

    Raises:
        InvalidCronJobError: If input is invalid.
    """
    if value == "*":
        return  # Wildcard is always valid

    try:
        # Check for simple integer values
        num = int(value)
        if not (min_val <= num <= max_val):
            raise InvalidCronJobError(
                f"Invalid cron input: {value} is out of range ({min_val}-{max_val})"
            )

    except ValueError:
        raise InvalidCronJobError(
            f"Invalid cron input: {value} is not a valid integer or '*'"
        ) from None


def convert_to_readable_schedule(month, day_of_month, hour, minute, day_of_week):
    """Converts cron format to a readable schedule string."""
    # Input validation (rely on exceptions from validate_cron_input)
    validate_cron_input(month, 1, 12)
    validate_cron_input(day_of_month, 1, 31)
    validate_cron_input(hour, 0, 23)
    validate_cron_input(minute, 0, 59)
    validate_cron_input(day_of_week, 0, 7)

    # Handle the all-wildcards case FIRST.
    if (
        month == "*"
        and day_of_month == "*"
        and hour == "*"
        and minute == "*"
        and day_of_week == "*"
    ):
        return "Every minute"

    # Handle wildcards and specific values
    try:
        if day_of_month == "*" and day_of_week == "*":
            return f"Daily at {int(hour):02d}:{int(minute):02d}"
        elif day_of_month != "*" and day_of_week == "*" and month == "*":
            return f"Monthly on day {int(day_of_month)} at {int(hour):02d}:{int(minute):02d}"
        elif day_of_month == "*" and day_of_week != "*":
            days_of_week = [
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
            weekday_index = int(day_of_week) % 8  # Handle both 0 and 7 for Sunday
            return f"Weekly on {days_of_week[weekday_index]} at {int(hour):02d}:{int(minute):02d}"
        else:
            # If there are wildcards in other fields, format as cron expression
            if any(
                val == "*" for val in [month, day_of_month, hour, minute, day_of_week]
            ):  # fixed to include day_of_week
                return f"Cron schedule: {minute} {hour} {day_of_month} {month} {day_of_week}"

            # Attempt to create datetime, to further validate and format
            now = datetime.now()
            try:
                # Construct next date time
                next_run = datetime(
                    now.year, int(month), int(day_of_month), int(hour), int(minute)
                )
                if next_run < now:
                    next_run = next_run.replace(year=now.year + 1)
                return next_run.strftime("%m/%d/%Y %H:%M")
            except ValueError:
                raise InvalidCronJobError(
                    f"Invalid date/time values in cron schedule: {minute} {hour} {day_of_month} {month} {day_of_week}"
                ) from None
    except ValueError:
        raise InvalidCronJobError(
            f"Invalid values in cron schedule: {minute} {hour} {day_of_month} {month} {day_of_week}"
        ) from None


def _modify_cron_job(old_cron_string, new_cron_string):
    """Modifies an existing cron job in the user's crontab.

    Args:
        old_cron_string (str): The existing cron job string to be replaced.
        new_cron_string (str): The new cron job string.

    Raises:
        CommandNotFoundError: If 'crontab' command not found.
        ScheduleError: If modifying the cron job fails, or the old job is not found.
    """
    if platform.system() != "Linux":
        return

    try:
        # Get existing cron jobs
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, check=False
        )
        existing_crontab = result.stdout
        if result.returncode != 0 and "no crontab" not in result.stderr.lower():
            raise ScheduleError(f"Error running crontab -l: {result.stderr}")

        # Check if the old job exists.  If not, it's an error.
        if old_cron_string not in existing_crontab:
            raise ScheduleError(f"Cron job to modify not found: {old_cron_string}")

        # Replace the old job with the new job
        new_crontab_lines = [
            new_cron_string if line.strip() == old_cron_string else line
            for line in existing_crontab.splitlines()
        ]
        updated_crontab = "\n".join(new_crontab_lines) + "\n"

        process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        process.communicate(input=updated_crontab)
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, "crontab")
        logger.debug(
            f"Cron job modified. Old: {old_cron_string} New: {new_cron_string}"
        )
    except subprocess.CalledProcessError as e:
        raise ScheduleError(f"Failed to update crontab with modified job: {e}") from e
    except FileNotFoundError:
        raise CommandNotFoundError(
            "crontab", message="crontab command not found"
        ) from None
    except Exception as e:
        raise ScheduleError(f"Unexpected error: {e}") from e


def _delete_cron_job(cron_string):
    """Deletes a specific cron job from the user's crontab.

    Args:
        cron_string (str): The complete cron job string to be deleted.

    Raises:
        CommandNotFoundError: If the 'crontab' command is not found.
        ScheduleError: If there is an error deleting the cron job.
    """
    if platform.system() != "Linux":
        return

    try:
        # Get existing cron jobs
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, check=False
        )
        existing_crontab = result.stdout
        if result.returncode != 0 and "no crontab" not in result.stderr.lower():
            raise ScheduleError(f"Error running crontab -l: {result.stderr}")

        # Check if the job exists. If not, just return (not an error)
        if cron_string not in existing_crontab:
            logger.debug(f"Cron job to delete not found: {cron_string}")
            return

        # Filter out the job to delete
        new_crontab_lines = [
            line
            for line in existing_crontab.splitlines()
            if line.strip() != cron_string
        ]
        updated_crontab = "\n".join(new_crontab_lines)
        if updated_crontab:  # prevent empty crontabs
            updated_crontab += "\n"  # must end in newline

        # Write back to crontab
        process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        process.communicate(input=updated_crontab)
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, "crontab")
        logger.debug(f"Cron job deleted: {cron_string}")
    except subprocess.CalledProcessError as e:
        raise ScheduleError(f"Failed to update crontab: {e}") from e
    except FileNotFoundError:
        raise CommandNotFoundError(
            "crontab", message="crontab command not found"
        ) from None
    except Exception as e:
        raise ScheduleError(f"An unexpected error has occurred: {e}") from e
