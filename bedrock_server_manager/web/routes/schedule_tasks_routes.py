# bedrock-server-manager/bedrock_server_manager/web/routes/schedule_tasks_routes.py
"""
Flask Blueprint handling web routes and API endpoints for managing scheduled tasks
(Linux cron jobs and Windows Task Scheduler tasks) related to server operations.
"""

import platform
import logging
from typing import Dict, Any, Tuple

# Third-party imports
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    Response,
)

# Local imports
from bedrock_server_manager.api import task_scheduler as api_task_scheduler
from bedrock_server_manager.error import (
    MissingArgumentError,
    InvalidInputError,
    TypeError,
    FileOperationError,
    CommandNotFoundError,
    ScheduleError,
    TaskError,
)
from bedrock_server_manager.config.settings import (
    settings,
)
from bedrock_server_manager.config.settings import (
    EXPATH,
)
from bedrock_server_manager.web.routes.auth_routes import login_required, csrf
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)

# Initialize logger
logger = logging.getLogger("bedrock_server_manager")

# Create Blueprint
schedule_tasks_bp = Blueprint(
    "schedule_tasks_routes",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)


# --- Route: Schedule Tasks Page (Linux/Cron) ---
@schedule_tasks_bp.route("/server/<string:server_name>/cron_scheduler", methods=["GET"])
@login_required  # Requires web session
def schedule_tasks_route(server_name: str) -> Response:
    """
    Displays the Linux cron job scheduling management page for a specific server.

    Lists existing cron jobs associated with the server.

    Args:
        server_name: The name of the server passed in the URL.

    Returns:
        Rendered HTML page ('schedule_tasks.html') with cron job data, or redirects
        with a flash message if not on Linux or if errors occur.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed Linux cron schedule page for server '{server_name}'."
    )

    if platform.system() != "Linux":
        msg = "Cron job scheduling is only available on Linux systems."
        flash(msg, "warning")
        logger.warning(
            f"Attempted access to Linux cron page for '{server_name}' on non-Linux OS ({platform.system()})."
        )
        # Redirect to main dashboard or server page? Let's use main for now.
        return redirect(url_for("main_routes.index"))

    table_data = []  # Default empty list
    try:
        # API call to get raw cron job lines for this server
        logger.debug(
            f"Calling API: api_task_scheduler.get_server_cron_jobs for '{server_name}'"
        )
        cron_jobs_response = api_task_scheduler.get_server_cron_jobs(server_name)
        logger.debug(f"Get cron jobs API response: {cron_jobs_response}")

        if cron_jobs_response.get("status") == "error":
            # Error retrieving jobs (e.g., crontab command failed)
            error_msg = f"Error retrieving cron jobs: {cron_jobs_response.get('message', 'Unknown error')}"
            flash(error_msg, "error")
            logger.error(f"{error_msg} for server '{server_name}'")
            # Render template but indicate error
        else:
            cron_jobs_list = cron_jobs_response.get("cron_jobs", [])
            if cron_jobs_list:
                logger.debug(
                    f"Found {len(cron_jobs_list)} raw cron lines for '{server_name}'. Formatting for table..."
                )
                # API call to format the raw lines into structured data for the table
                table_response = api_task_scheduler.get_cron_jobs_table(cron_jobs_list)
                logger.debug(f"Format cron jobs table API response: {table_response}")

                if table_response.get("status") == "error":
                    error_msg = f"Error formatting cron jobs: {table_response.get('message', 'Unknown error')}"
                    flash(error_msg, "error")
                    logger.error(f"{error_msg} for server '{server_name}'")
                else:
                    table_data = table_response.get("table_data", [])
                    logger.debug(
                        f"Successfully formatted {len(table_data)} cron jobs for display."
                    )
            else:
                logger.info(
                    f"No existing cron jobs found specifically for server '{server_name}'."
                )

    except MissingArgumentError as e:  # Catch errors raised directly by API calls
        flash(f"Error preparing scheduler page: {e}", "error")
        logger.error(
            f"Error preparing Linux scheduler page for '{server_name}': {e}",
            exc_info=True,
        )
        # Redirect? Or render with error? Render for now.
    except Exception as e:  # Catch unexpected errors
        flash("An unexpected error occurred while loading scheduled tasks.", "error")
        logger.error(
            f"Unexpected error preparing Linux scheduler page for '{server_name}': {e}",
            exc_info=True,
        )

    logger.debug(
        f"Rendering 'schedule_tasks.html' for '{server_name}' with {len(table_data)} jobs."
    )
    # Pass EXPATH for constructing command examples in the template?
    return render_template(
        "schedule_tasks.html",
        server_name=server_name,
        table_data=table_data,  # List of dicts for the table
        EXPATH=EXPATH,
    )


# --- API Route: Add Cron Job ---
@schedule_tasks_bp.route(
    "/api/server/<string:server_name>/cron_scheduler/add", methods=["POST"]
)
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def add_cron_job_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to add a new Linux cron job.

    Expects JSON body with 'new_cron_job' key containing the full cron job line.

    Args:
        server_name: The server context (used for logging/auth, not directly in cron command).

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 201 Created on success: {"status": "success", "message": "..."}
        - 400 Bad Request on invalid input.
        - 403 Forbidden if not on Linux.
        - 500 Internal Server Error on failure to add job.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Add cron job requested by user '{identity}' (context server: '{server_name}')."
    )

    if platform.system() != "Linux":
        msg = "Adding cron jobs is only supported on Linux."
        logger.error(f"API Add Cron Job failed: {msg}")
        return jsonify(status="error", message=msg), 403  # Forbidden

    # --- Input Validation ---
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        logger.warning("API Add Cron Job: Invalid/missing JSON request body.")
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    cron_string = data.get("new_cron_job")
    logger.debug(f"API Add Cron Job: Received cron string: '{cron_string}'")

    if not cron_string or not isinstance(cron_string, str) or not cron_string.strip():
        msg = "Cron job string ('new_cron_job') is required in request body."
        logger.warning(f"API Add Cron Job: {msg}")
        return jsonify(status="error", message=msg), 400

    # --- Call API Handler ---
    result: Dict[str, Any] = {}
    status_code = 500
    try:
        result = api_task_scheduler.add_cron_job(
            cron_string.strip()
        )  # API func returns dict
        logger.debug(f"API Add Cron Job: Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 201  # Created
            success_msg = result.get("message", "Cron job added successfully.")
            logger.info(f"API Add Cron Job successful: '{cron_string.strip()}'")
            result["message"] = success_msg
        else:
            status_code = 500  # Treat handler errors as internal error
            error_msg = (
                result.get("message", "Unknown error adding cron job.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Add Cron Job failed: {error_msg}")
            result = {"status": "error", "message": error_msg}

    except MissingArgumentError as e:  # Catch errors raised directly by API func
        logger.warning(f"API Add Cron Job: Input error: {e}", exc_info=True)
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except Exception as e:  # Catch unexpected errors during API orchestration
        logger.error(f"API Add Cron Job: Unexpected error: {e}", exc_info=True)
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- API Route: Modify Cron Job ---
@schedule_tasks_bp.route(
    "/api/server/<string:server_name>/cron_scheduler/modify", methods=["POST"]
)
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def modify_cron_job_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to modify an existing Linux cron job.

    Expects JSON body with 'old_cron_job' and 'new_cron_job' keys.

    Args:
        server_name: The server context (used for logging/auth).

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 200 OK on success: {"status": "success", "message": "..."}
        - 400 Bad Request on invalid input.
        - 403 Forbidden if not on Linux.
        - 404 Not Found if the old cron job doesn't exist.
        - 500 Internal Server Error on failure to modify job.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Modify cron job requested by user '{identity}' (context server: '{server_name}')."
    )

    if platform.system() != "Linux":
        msg = "Modifying cron jobs is only supported on Linux."
        logger.error(f"API Modify Cron Job failed: {msg}")
        return jsonify(status="error", message=msg), 403

    # --- Input Validation ---
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        logger.warning("API Modify Cron Job: Invalid/missing JSON request body.")
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    old_cron_string = data.get("old_cron_job")
    new_cron_string = data.get("new_cron_job")
    logger.debug(
        f"API Modify Cron Job: Old='{old_cron_string}', New='{new_cron_string}'"
    )

    if (
        not old_cron_string
        or not isinstance(old_cron_string, str)
        or not old_cron_string.strip()
    ):
        msg = "Original cron job string ('old_cron_job') is required."
        logger.warning(f"API Modify Cron Job: {msg}")
        return jsonify(status="error", message=msg), 400
    if (
        not new_cron_string
        or not isinstance(new_cron_string, str)
        or not new_cron_string.strip()
    ):
        msg = "New cron job string ('new_cron_job') is required."
        logger.warning(f"API Modify Cron Job: {msg}")
        return jsonify(status="error", message=msg), 400

    # --- Call API Handler ---
    result: Dict[str, Any] = {}
    status_code = 500
    try:
        result = api_task_scheduler.modify_cron_job(
            old_cron_string.strip(), new_cron_string.strip()
        )  # API func returns dict
        logger.debug(f"API Modify Cron Job: Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200  # OK
            success_msg = result.get("message", "Cron job modified successfully.")
            logger.info(
                f"API Modify Cron Job successful: Replaced '{old_cron_string.strip()}' with '{new_cron_string.strip()}'"
            )
            result["message"] = success_msg
        else:
            # Check if error message indicates job not found
            error_msg = (
                result.get("message", "Unknown error modifying cron job.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            if "not found" in error_msg.lower():
                status_code = 404  # Not Found
                logger.warning(
                    f"API Modify Cron Job: Old job not found: '{old_cron_string.strip()}'"
                )
            else:
                status_code = 500
                logger.error(f"API Modify Cron Job failed: {error_msg}")
            result = {"status": "error", "message": error_msg}

    except (
        MissingArgumentError,
        TypeError,
    ) as e:  # Catch errors raised directly by API func
        logger.warning(f"API Modify Cron Job: Input error: {e}", exc_info=True)
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except (
        ScheduleError
    ) as e:  # Catch specific ScheduleError (e.g., job not found raised from core)
        logger.error(f"API Modify Cron Job: ScheduleError: {e}", exc_info=True)
        if "not found" in str(e).lower():
            status_code = 404
            result = {"status": "error", "message": f"Could not modify: {e}"}
        else:
            status_code = 500
            result = {"status": "error", "message": f"Error modifying cron job: {e}"}
    except Exception as e:  # Catch unexpected errors
        logger.error(f"API Modify Cron Job: Unexpected error: {e}", exc_info=True)
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- API Route: Delete Cron Job ---
@schedule_tasks_bp.route(
    "/api/server/<string:server_name>/cron_scheduler/delete", methods=["DELETE"]
)
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def delete_cron_job_route(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to delete a specific Linux cron job.

    Expects the cron job string to delete as a URL query parameter named 'cron_string'.

    Args:
        server_name: The server context (used for logging/auth).

    Query Parameters:
        cron_string (str): The exact cron job line string to be deleted (URL encoded).

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 200 OK on success: {"status": "success", "message": "..."} (even if job didn't exist)
        - 400 Bad Request on invalid/missing query parameter.
        - 403 Forbidden if not on Linux.
        - 500 Internal Server Error on failure to delete job.
    """
    identity = get_current_identity() or "Unknown"
    # Include task to delete in initial log if possible
    cron_string_from_query = request.args.get("cron_string", "(Not Provided)")
    logger.info(
        f"API: Delete cron job requested by user '{identity}' (context server: '{server_name}', job: '{cron_string_from_query}')."
    )

    # --- Platform Check ---
    if platform.system() != "Linux":
        msg = "Deleting cron jobs is only supported on Linux."
        logger.error(f"API Delete Cron Job failed: {msg}")
        return jsonify(status="error", message=msg), 403  # Forbidden

    # --- Get Cron String from Query Parameter ---
    # request.args contains URL query parameters (e.g., ?cron_string=...)
    cron_string = request.args.get("cron_string")
    logger.debug(
        f"API Delete Cron Job: Received cron_string from query param: '{cron_string}'"
    )

    # --- Input Validation ---
    if not cron_string or not isinstance(cron_string, str) or not cron_string.strip():
        msg = "Cron job string ('cron_string') is required as a query parameter."
        logger.warning(f"API Delete Cron Job: {msg}")
        return jsonify(status="error", message=msg), 400  # Bad Request

    cron_string_stripped = cron_string.strip()  # Use stripped version

    # --- Call API Handler ---
    result: Dict[str, Any] = {}
    status_code = 500  # Default to internal error
    try:
        logger.info(f"Calling API handler to delete cron job: '{cron_string_stripped}'")
        # Call the API function which handles core logic and returns a dict
        result = api_task_scheduler.delete_cron_job(cron_string_stripped)
        logger.debug(f"API Delete Cron Job '{server_name}': Handler response: {result}")

        # Process the result from the API handler
        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200  # OK
            # Use message from API handler, or provide a default
            success_msg = result.get(
                "message",
                f"Cron job '{cron_string_stripped}' deleted successfully (if it existed).",
            )
            logger.info(f"API Delete Cron Job successful for: '{cron_string_stripped}'")
            result["message"] = success_msg  # Ensure message key exists
        else:
            # Handler indicated failure or returned unexpected format
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error deleting cron job.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Delete Cron Job failed: {error_msg}")
            # Ensure result dict has error status and message for JSON response
            result = {"status": "error", "message": error_msg}

    except MissingArgumentError as e:  # Catch errors raised directly by API func
        logger.warning(
            f"API Delete Cron Job '{server_name}': Input error: {e}", exc_info=True
        )
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except (
        CommandNotFoundError,
        ScheduleError,
        FileOperationError,
    ) as e:  # Catch errors from core funcs via API
        logger.error(
            f"API Delete Cron Job '{server_name}': Core error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"Error deleting cron job: {e}"}
    except Exception as e:  # Catch unexpected errors during API orchestration
        logger.error(
            f"API Delete Cron Job '{server_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    # Return the JSON response and HTTP status code
    logger.debug(
        f"Returning JSON response for delete cron job API '{server_name}' with status code {status_code}."
    )
    return jsonify(result), status_code


# --- Route: Schedule Tasks Page (Windows) ---
@schedule_tasks_bp.route("/server/<string:server_name>/task_scheduler", methods=["GET"])
@login_required  # Requires web session
def schedule_tasks_windows_route(server_name: str) -> Response:
    """
    Displays the Windows Task Scheduler management page for a specific server.

    Lists existing scheduled tasks associated with the server found in the config directory.

    Args:
        server_name: The name of the server passed in the URL.

    Returns:
        Rendered HTML page ('schedule_tasks_windows.html') with task data, or redirects
        with a flash message if not on Windows or if errors occur.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed Windows Task Scheduler page for server '{server_name}'."
    )

    if platform.system() != "Windows":
        msg = "Windows Task Scheduling management is only available on Windows."
        flash(msg, "warning")
        logger.warning(
            f"Attempted access to Windows scheduler page for '{server_name}' on non-Windows OS ({platform.system()})."
        )
        return redirect(url_for("main_routes.index"))

    tasks = []  # Default empty list
    try:
        config_dir = getattr(settings, "_config_dir", None)
        if not config_dir:
            raise FileOperationError("Base configuration directory not set.")

        # API call to get list of task names/paths from config dir
        logger.debug(
            f"Calling API: api_task_scheduler.get_server_task_names for '{server_name}'"
        )
        task_names_response = api_task_scheduler.get_server_task_names(
            server_name, config_dir
        )
        logger.debug(f"Get task names API response: {task_names_response}")

        if task_names_response.get("status") == "error":
            error_msg = f"Error retrieving task names: {task_names_response.get('message', 'Unknown error')}"
            flash(error_msg, "error")
            logger.error(f"{error_msg} for server '{server_name}'")
        else:
            task_name_path_list = task_names_response.get("task_names", [])
            if task_name_path_list:
                task_names_only = [
                    task[0] for task in task_name_path_list
                ]  # Extract just names
                logger.debug(
                    f"Found {len(task_names_only)} associated task names. Getting details..."
                )

                # API call to get details for the found tasks
                task_info_response = api_task_scheduler.get_windows_task_info(
                    task_names_only
                )
                logger.debug(f"Get task info API response: {task_info_response}")

                if task_info_response.get("status") == "error":
                    error_msg = f"Error retrieving task details: {task_info_response.get('message', 'Unknown error')}"
                    flash(error_msg, "error")
                    logger.error(f"{error_msg} for server '{server_name}'")
                else:
                    tasks = task_info_response.get("task_info", [])
                    logger.info(
                        f"Successfully retrieved details for {len(tasks)} Windows tasks for server '{server_name}'."
                    )
            else:
                logger.info(f"No task XML files found for server '{server_name}'.")

    except (
        MissingArgumentError,
        FileOperationError,
    ) as e:  # Catch errors raised directly by API calls
        flash(f"Error preparing scheduler page: {e}", "error")
        logger.error(
            f"Error preparing Windows scheduler page for '{server_name}': {e}",
            exc_info=True,
        )
    except Exception as e:  # Catch unexpected errors
        flash("An unexpected error occurred while loading scheduled tasks.", "error")
        logger.error(
            f"Unexpected error preparing Windows scheduler page for '{server_name}': {e}",
            exc_info=True,
        )

    logger.debug(
        f"Rendering 'schedule_tasks_windows.html' for '{server_name}' with {len(tasks)} tasks."
    )
    return render_template(
        "schedule_tasks_windows.html",
        server_name=server_name,
        tasks=tasks,
    )


# --- API Route: Add Windows Task ---
@schedule_tasks_bp.route(
    "/api/server/<string:server_name>/task_scheduler/add", methods=["POST"]
)
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def add_windows_task_api(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to add a new Windows scheduled task.

    Expects JSON body with command and trigger details.

    Args:
        server_name: The name of the server passed in the URL.

    JSON Request Body Example:
        {
            "command": "backup-all",
            "triggers": [
                {"type": "Daily", "start": "2023-10-27T03:00", "interval": 1},
                {"type": "Weekly", "start": "2023-10-27T05:00", "interval": 1, "days": ["Sunday"]}
            ]
        }

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 201 Created on success: {"status": "success", "message": "...", "created_task_name": "..."}
        - 400 Bad Request on invalid input.
        - 403 Forbidden if not on Windows.
        - 500 Internal Server Error on failure to create task.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Add Windows task requested by user '{identity}' for server '{server_name}'."
    )

    if platform.system() != "Windows":
        msg = "Adding Windows tasks is only supported on Windows."
        logger.error(f"API Add Windows Task failed: {msg}")
        return jsonify(status="error", message=msg), 403

    # --- Input Validation ---
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        logger.warning("API Add Windows Task: Invalid/missing JSON request body.")
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    logger.debug(f"API Add Windows Task '{server_name}': Received data: {data}")
    command = data.get("command")
    triggers = data.get("triggers")

    # Validate command
    valid_commands = [
        "update-server",
        "backup-all",
        "start-server",
        "stop-server",
        "restart-server",
        "scan-players",
    ]
    if not command or command not in valid_commands:
        msg = f"Invalid or missing 'command'. Must be one of: {valid_commands}."
        logger.warning(f"API Add Windows Task '{server_name}': {msg} Got: '{command}'")
        return jsonify(status="error", message=msg), 400

    # Validate triggers (basic structure)
    if not triggers or not isinstance(triggers, list) or not triggers:
        msg = "Missing or invalid 'triggers' list in request body. At least one trigger is required."
        logger.warning(f"API Add Windows Task '{server_name}': {msg}")
        return jsonify(status="error", message=msg), 400
    for i, trigger in enumerate(triggers):
        if (
            not isinstance(trigger, dict)
            or not trigger.get("type")
            or not trigger.get("start")
        ):
            msg = (
                f"Invalid trigger structure at index {i}. Requires 'type' and 'start'."
            )
            logger.warning(
                f"API Add Windows Task '{server_name}': {msg} Got: {trigger}"
            )
            return jsonify(status="error", message=msg), 400

    # --- Prepare Args and Call API Handler ---
    result: Dict[str, Any] = {}
    status_code = 500
    try:
        config_dir = getattr(
            settings, "_config_dir", None
        )  # Get config dir for saving XML
        if not config_dir:
            raise FileOperationError("Base configuration directory not set.")

        # Determine command args and generate task name
        command_args = f"--server {server_name}" if command != "scan-players" else ""

        # Use API helper to generate name (includes timestamp for uniqueness)
        task_name = api_task_scheduler.create_task_name(
            server_name, command
        )  # Pass command if no args

        logger.info(
            f"Attempting to create Windows task '{task_name}' for command '{command}' via API..."
        )
        result = api_task_scheduler.create_windows_task(
            server_name=server_name,
            command=command,
            command_args=command_args,
            task_name=task_name,
            config_dir=config_dir,
            triggers=triggers,
        )
        logger.debug(
            f"API Add Windows Task '{server_name}': Handler response: {result}"
        )

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 201  # Created
            success_msg = result.get(
                "message", f"Task '{task_name}' created successfully."
            )
            logger.info(f"API Add Windows Task successful for '{task_name}'.")
            result["message"] = success_msg
            result["created_task_name"] = task_name  # Return generated name
        else:
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error creating task.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Add Windows Task failed for '{task_name}': {error_msg}")
            result = {"status": "error", "message": error_msg}

    except (
        MissingArgumentError,
        TypeError,
        InvalidInputError,
    ) as e:  # Catch errors raised directly by API func
        logger.warning(
            f"API Add Windows Task '{server_name}': Input error: {e}", exc_info=True
        )
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except (
        TaskError,
        CommandNotFoundError,
        FileOperationError,
    ) as e:  # Catch errors from core funcs via API
        logger.error(
            f"API Add Windows Task '{server_name}': Core task error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"Error creating task: {e}"}
    except Exception as e:  # Catch unexpected errors
        logger.error(
            f"API Add Windows Task '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- API Route: Get Windows Task Details ---
@schedule_tasks_bp.route(
    "/api/server/<string:server_name>/task_scheduler/details", methods=["POST"]
)
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def get_windows_task_details_api_post(server_name: str) -> Tuple[Response, int]:
    """
    API endpoint to get details for a specific Windows scheduled task
    by parsing its saved XML configuration file.

    Expects JSON body with 'task_name' key containing the task name to retrieve details for.

    Args:
        server_name: The server context (used to find the config file).

    Returns:
        JSON response containing task details or an error.
        - 200 OK: {"status": "success", "base_command": "...", "triggers": [...]}
        - 400 Bad Request: Invalid JSON or missing task name.
        - 403 Forbidden if not on Windows.
        - 404 Not Found if task config XML doesn't exist.
        - 500 Internal Server Error on parsing or other errors.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Get Windows task details requested by user '{identity}' for server '{server_name}'."
    )

    if platform.system() != "Windows":
        msg = "Windows Task Scheduler functions are only supported on Windows."
        logger.error(f"API Get Task Details failed: {msg}")
        return jsonify(status="error", message=msg), 403

    # --- Input Validation ---
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        logger.warning(
            f"API Get Task Details '{server_name}': Invalid/missing JSON body."
        )
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    task_name = data.get("task_name")
    if not task_name or not isinstance(task_name, str):
        msg = "Missing or invalid 'task_name' in request body."
        logger.warning(f"API Get Task Details '{server_name}': {msg}")
        return jsonify(status="error", message=msg), 400

    logger.debug(f"API Get Task Details: Request for task_name='{task_name}'")

    result: Dict[str, Any] = {}
    status_code = 500
    try:
        config_dir = getattr(settings, "_config_dir", None)
        if not config_dir:
            raise FileOperationError("Base configuration directory not set.")

        # --- Find XML File Path ---
        # Use the API function which returns list of tuples (name, path)
        task_list_result = api_task_scheduler.get_server_task_names(
            server_name, config_dir
        )
        task_file_path = None
        if task_list_result.get("status") == "success":
            for name, path in task_list_result.get("task_names", []):
                normalized_name = name.lstrip("\\") if name else ""
                if normalized_name == task_name:
                    task_file_path = path
                    break

        if not task_file_path:
            raise FileNotFoundError(
                f"Configuration XML file for task '{task_name}' not found."
            )

        logger.debug(f"API Get Task Details: Found XML path: {task_file_path}")

        # --- Call API Handler to Parse XML ---
        result = api_task_scheduler.get_windows_task_details(
            task_file_path
        )  # API func returns dict
        logger.debug(f"API Get Task Details '{task_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200
            logger.info(
                f"API Get Task Details: Successfully retrieved details for task '{task_name}'."
            )
            # Response format is already {"status": "success", "task_details": {...}} from api func
        else:
            status_code = 500  # Treat handler errors as internal error
            error_msg = (
                result.get("message", "Unknown error parsing task details.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Get Task Details failed for '{task_name}': {error_msg}")
            result = {"status": "error", "message": error_msg}

    except FileNotFoundError as e:
        logger.warning(
            f"API Get Task Details '{server_name}': Task config file not found: {e}",
            exc_info=True,
        )
        status_code = 404
        result = {"status": "error", "message": f"Task configuration not found: {e}"}
    except (MissingArgumentError, FileOperationError) as e:  # Catch setup errors
        logger.error(
            f"API Get Task Details '{server_name}': Configuration/Input error: {e}",
            exc_info=True,
        )
        status_code = 500
        result = {"status": "error", "message": f"Configuration or input error: {e}"}
    except Exception as e:  # Catch unexpected errors
        logger.error(
            f"API Get Task Details '{server_name}': Unexpected error for task '{task_name}': {e}",
            exc_info=True,
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- API Route: Modify Windows Task ---
@schedule_tasks_bp.route(
    "/api/server/<string:server_name>/task_scheduler/task/<path:task_name>",
    methods=["PUT"],
)
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def modify_windows_task_api(server_name: str, task_name: str) -> Tuple[Response, int]:
    """
    API endpoint to modify an existing Windows scheduled task.

    Deletes the existing task specified by `task_name` in the URL and creates a
    new one based on the data provided in the JSON request body. The new task
    will have a newly generated name including a timestamp.

    Args:
        server_name: The server context (used for config path).
        task_name: The current name of the task to modify (from URL path).

    JSON Request Body Example: (Similar to Add Task)
        {
            "command": "backup-all",
            "triggers": [ {"type": "Daily", "start": "...", "interval": ...}, ... ]
        }

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 200 OK on success: {"status": "success", "message": "...", "new_task_name": "..."}
        - 400 Bad Request on invalid input.
        - 403 Forbidden if not on Windows.
        - 500 Internal Server Error on failure.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Modify Windows task '{task_name}' requested by user '{identity}' for server '{server_name}'."
    )

    if platform.system() != "Windows":
        msg = "Modifying Windows tasks is only supported on Windows."
        logger.error(f"API Modify Task failed: {msg}")
        return jsonify(status="error", message=msg), 403

    # --- Input Validation ---
    if not task_name:
        return (
            jsonify(status="error", message="Original task name required in URL path."),
            400,
        )

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        logger.warning(
            f"API Modify Task '{task_name}': Invalid/missing JSON request body."
        )
        return (
            jsonify(status="error", message="Invalid or missing JSON request body."),
            400,
        )

    logger.debug(f"API Modify Task '{task_name}': Received data: {data}")
    new_command = data.get("command")
    new_triggers = data.get("triggers")

    # Validate command
    valid_commands = [
        "update-server",
        "backup-all",
        "start-server",
        "stop-server",
        "restart-server",
        "scan-players",
    ]
    if not new_command or new_command not in valid_commands:
        msg = f"Invalid or missing 'command'. Must be one of: {valid_commands}."
        logger.warning(f"API Modify Task '{task_name}': {msg} Got: '{new_command}'")
        return jsonify(status="error", message=msg), 400

    # Validate triggers
    if not new_triggers or not isinstance(new_triggers, list) or not new_triggers:
        msg = "Missing or invalid 'triggers' list in request body. At least one trigger is required."
        logger.warning(f"API Modify Task '{task_name}': {msg}")
        return jsonify(status="error", message=msg), 400

    # --- Prepare Args and Call API Handler ---
    result: Dict[str, Any] = {}
    status_code = 500
    try:
        config_dir = getattr(settings, "_config_dir", None)
        if not config_dir:
            raise FileOperationError("Base configuration directory not set.")

        # Determine new command args and generate NEW task name
        new_command_args = (
            f"--server {server_name}" if new_command != "scan-players" else ""
        )
        new_task_name = api_task_scheduler.create_task_name(server_name, new_command)

        logger.info(
            f"Calling API handler to modify task '{task_name}' (will be replaced by '{new_task_name}')..."
        )
        # API function handles delete-then-create logic
        result = api_task_scheduler.modify_windows_task(
            old_task_name=task_name,
            server_name=server_name,
            command=new_command,
            command_args=new_command_args,
            new_task_name=new_task_name,  # Pass the newly generated name
            config_dir=config_dir,
            triggers=new_triggers,
        )
        logger.debug(f"API Modify Task '{task_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200  # OK
            success_msg = result.get(
                "message",
                f"Task '{task_name}' modified successfully (new name: '{new_task_name}').",
            )
            logger.info(
                f"API Modify Task successful: '{task_name}' replaced by '{new_task_name}'."
            )
            result["message"] = success_msg
            result["new_task_name"] = new_task_name  # Ensure new name is in response
        else:
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error modifying task.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Modify Task failed for '{task_name}': {error_msg}")
            result = {"status": "error", "message": error_msg}

    except (
        MissingArgumentError,
        TypeError,
        InvalidInputError,
    ) as e:  # Catch input validation errors
        logger.warning(
            f"API Modify Task '{task_name}': Input error: {e}", exc_info=True
        )
        status_code = 400
        result = {"status": "error", "message": f"Invalid input: {e}"}
    except (
        TaskError,
        CommandNotFoundError,
        FileOperationError,
    ) as e:  # Catch core function errors
        logger.error(
            f"API Modify Task '{task_name}': Core task error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"Error modifying task: {e}"}
    except Exception as e:  # Catch unexpected errors
        logger.error(
            f"API Modify Task '{task_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code


# --- API Route: Delete Windows Task ---
# Corrected route path to use task_name from URL
@schedule_tasks_bp.route(
    "/api/server/<string:server_name>/task_scheduler/task/<path:task_name>",
    methods=["DELETE"],
)
@csrf.exempt  # API endpoint
@auth_required  # Requires session OR JWT
def delete_windows_task_api(server_name: str, task_name: str) -> Tuple[Response, int]:
    """
    API endpoint to delete an existing Windows scheduled task and its config file.

    Args:
        server_name: The server context (used to find config file).
        task_name: The name of the task to delete (from URL path).

    Returns:
        JSON response indicating success or failure, with appropriate HTTP status code.
        - 200 OK on success: {"status": "success", "message": "..."}
        - 400 Bad Request on invalid input (missing task name).
        - 403 Forbidden if not on Windows.
        - 500 Internal Server Error on failure.
    """
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Delete Windows task '{task_name}' requested by user '{identity}' for server '{server_name}'."
    )

    if platform.system() != "Windows":
        msg = "Deleting Windows tasks is only supported on Windows."
        logger.error(f"API Delete Task failed: {msg}")
        return jsonify(status="error", message=msg), 403

    if not task_name:  # Check task_name from URL
        return (
            jsonify(status="error", message="Task name is required in URL path."),
            400,
        )

    result: Dict[str, Any] = {}
    status_code = 500
    try:
        config_dir = getattr(settings, "_config_dir", None)
        if not config_dir:
            raise FileOperationError("Base configuration directory not set.")

        # --- Find XML File Path ---
        task_file_path = None
        task_list_result = api_task_scheduler.get_server_task_names(
            server_name, config_dir
        )
        if task_list_result.get("status") == "success":
            for name, path in task_list_result.get("task_names", []):
                normalized_name = name.lstrip("\\") if name else ""
                if normalized_name == task_name:
                    task_file_path = path
                    break
        if not task_file_path:
            logger.warning(
                f"Could not find configuration file path for task '{task_name}'. Will only attempt deletion from scheduler."
            )
            # Proceed without path, delete_windows_task API func handles None path

        # --- Call API Handler ---
        logger.info(
            f"Calling API handler to delete Windows task '{task_name}' (and XML if found: {task_file_path})..."
        )
        result = api_task_scheduler.delete_windows_task(
            task_name, task_file_path
        )  # API func returns dict
        logger.debug(f"API Delete Task '{task_name}': Handler response: {result}")

        if isinstance(result, dict) and result.get("status") == "success":
            status_code = 200  # OK
            success_msg = result.get(
                "message", f"Task '{task_name}' deleted successfully."
            )
            logger.info(f"API Delete Task successful for '{task_name}'.")
            result["message"] = success_msg
        else:
            status_code = 500
            error_msg = (
                result.get("message", "Unknown error deleting task.")
                if isinstance(result, dict)
                else "Handler returned unexpected response."
            )
            logger.error(f"API Delete Task failed for '{task_name}': {error_msg}")
            result = {"status": "error", "message": error_msg}

    except (MissingArgumentError, FileOperationError) as e:  # Catch setup errors
        logger.error(
            f"API Delete Task '{task_name}': Input or Configuration error: {e}",
            exc_info=True,
        )
        status_code = 500  # Treat config errors as internal
        result = {"status": "error", "message": f"Configuration or input error: {e}"}
    except (TaskError, CommandNotFoundError) as e:  # Catch core function errors
        logger.error(
            f"API Delete Task '{task_name}': Core task error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"Error deleting task: {e}"}
    except Exception as e:  # Catch unexpected errors
        logger.error(
            f"API Delete Task '{task_name}': Unexpected error: {e}", exc_info=True
        )
        status_code = 500
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return jsonify(result), status_code
