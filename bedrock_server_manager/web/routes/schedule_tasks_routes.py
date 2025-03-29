# bedrock-server-manager/bedrock_server_manager/web/routes/schedule_tasks_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import os
import platform
import logging
from bedrock_server_manager import handlers
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.config.settings import EXPATH, app_name
from bedrock_server_manager.web.routes.auth_routes import login_required

# Initialize logger for this module
logger = logging.getLogger("bedrock_server_manager")

# Create Blueprint for server-related routes
schedule_tasks_bp = Blueprint("schedule_tasks_routes", __name__)


# --- Route: Schedule Tasks Page (Linux/Cron) ---
@schedule_tasks_bp.route("/server/<server_name>/schedule", methods=["GET"])
@login_required
def schedule_tasks_route(server_name):
    """Displays the Linux cron job scheduling page for a server."""
    logger.info(
        f"Route '/server/{server_name}/schedule' accessed - Rendering Linux cron task schedule page."
    )

    # Check OS - redirect if not Linux? Or just show an error? For now, assume access implies Linux.
    if platform.system() != "Linux":
        flash("Cron job scheduling is only available on Linux.", "warning")
        logger.warning(
            f"Attempted to access Linux cron schedule page for '{server_name}' on non-Linux OS."
        )
        # Optionally redirect: return redirect(url_for('main_routes.index'))

    # Get current cron jobs related to this server using the handler
    logger.debug(f"Calling get_server_cron_jobs_handler for '{server_name}'...")
    cron_jobs_response = handlers.get_server_cron_jobs_handler(server_name)
    logger.debug(f"Get cron jobs handler response: {cron_jobs_response}")

    table_data = []  # Default empty list for template
    if cron_jobs_response["status"] == "error":
        error_msg = f"Error retrieving cron jobs for '{server_name}': {cron_jobs_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
    else:
        cron_jobs = cron_jobs_response.get("cron_jobs", [])  # List of raw cron strings
        logger.debug(f"Found {len(cron_jobs)} raw cron job lines for '{server_name}'.")
        # Get formatted table data using the formatting handler
        logger.debug(f"Calling get_cron_jobs_table_handler...")
        table_response = handlers.get_cron_jobs_table_handler(cron_jobs)
        logger.debug(f"Format cron jobs handler response: {table_response}")
        if table_response["status"] == "error":
            error_msg = f"Error formatting cron jobs table for '{server_name}': {table_response.get('message', 'Unknown error')}"
            flash(error_msg, "error")
            logger.error(error_msg)
        else:
            table_data = table_response.get("table_data", [])
            logger.debug(
                f"Successfully formatted {len(table_data)} cron jobs for display."
            )

    # Render the Linux scheduling template
    logger.debug(f"Rendering schedule_tasks.html for '{server_name}'.")
    return render_template(
        "schedule_tasks.html",
        server_name=server_name,
        table_data=table_data,  # Pass formatted data for table display
        EXPATH=EXPATH,  # Pass executable path if needed by template
        app_name=app_name,
    )


# --- API Route: Add Cron Job ---
# Note: These cron routes might need refinement based on how server-specific jobs are managed.
# Currently, they seem to operate on the system's crontab directly via handlers.
@schedule_tasks_bp.route("/server/<server_name>/schedule/add", methods=["POST"])
@login_required
def add_cron_job_route(server_name):
    """API endpoint to add a new cron job."""
    # The server_name is in the URL but might not be strictly needed by the handler if it adds globally?
    logger.info(
        f"API POST request received to add cron job (context: server '{server_name}')."
    )

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for add cron job: {data}")

    if not data or not isinstance(data, dict):
        logger.warning(f"API Add Cron Job request: Empty or invalid JSON body.")
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract the full cron job string
    cron_string = data.get("new_cron_job")
    logger.debug(f"Cron string received: '{cron_string}'")

    if not cron_string or not isinstance(cron_string, str) or not cron_string.strip():
        logger.warning(
            f"API Add Cron Job request: Missing or empty 'new_cron_job' string."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Cron job string ('new_cron_job') is required.",
                }
            ),
            400,
        )

    cron_string = cron_string.strip()  # Use trimmed string

    logger.info(f"Attempting to add cron job via handler: '{cron_string}'")
    # Call the handler to add the job
    logger.debug("Calling add_cron_job_handler...")
    add_response = handlers.add_cron_job_handler(cron_string)
    logger.debug(f"Add cron job handler response: {add_response}")

    # Determine status code
    status_code = (
        200 if add_response and add_response.get("status") == "success" else 500
    )

    if status_code == 200:
        logger.info(f"Cron job added successfully via API: '{cron_string}'")
        if add_response and "message" not in add_response:
            add_response["message"] = "Cron job added successfully."
    else:
        error_message = (
            add_response.get("message", "Unknown error adding cron job")
            if add_response
            else "Add cron handler failed unexpectedly"
        )
        logger.error(f"API Add Cron Job failed: {error_message}")
        if not add_response:
            add_response = {}
        add_response["status"] = "error"
        if "message" not in add_response:
            add_response["message"] = "Failed to add cron job."

    logger.debug(
        f"Returning JSON response for add cron job API with status code {status_code}."
    )
    return jsonify(add_response), status_code


# --- API Route: Modify Cron Job ---
@schedule_tasks_bp.route("/server/<server_name>/schedule/modify", methods=["POST"])
@login_required
def modify_cron_job_route(server_name):
    """API endpoint to modify an existing cron job."""
    logger.info(
        f"API POST request received to modify cron job (context: server '{server_name}')."
    )

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for modify cron job: {data}")

    if not data or not isinstance(data, dict):
        logger.warning(f"API Modify Cron Job request: Empty or invalid JSON body.")
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract old and new cron strings
    old_cron_string = data.get("old_cron_job")
    new_cron_string = data.get("new_cron_job")
    logger.debug(
        f"Old cron string: '{old_cron_string}', New cron string: '{new_cron_string}'"
    )

    # Validate presence
    if (
        not old_cron_string
        or not isinstance(old_cron_string, str)
        or not old_cron_string.strip()
    ):
        logger.warning(
            f"API Modify Cron Job request: Missing or empty 'old_cron_job' string."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Original cron job string ('old_cron_job') is required.",
                }
            ),
            400,
        )
    if (
        not new_cron_string
        or not isinstance(new_cron_string, str)
        or not new_cron_string.strip()
    ):
        logger.warning(
            f"API Modify Cron Job request: Missing or empty 'new_cron_job' string."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "New cron job string ('new_cron_job') is required.",
                }
            ),
            400,
        )

    old_cron_string = old_cron_string.strip()
    new_cron_string = new_cron_string.strip()

    logger.info(
        f"Attempting to modify cron job via handler. From: '{old_cron_string}' To: '{new_cron_string}'"
    )
    # Call the handler to modify the job
    logger.debug("Calling modify_cron_job_handler...")
    modify_response = handlers.modify_cron_job_handler(old_cron_string, new_cron_string)
    logger.debug(f"Modify cron job handler response: {modify_response}")

    # Determine status code
    status_code = (
        200 if modify_response and modify_response.get("status") == "success" else 500
    )

    if status_code == 200:
        logger.info(
            f"Cron job modified successfully via API. Old: '{old_cron_string}', New: '{new_cron_string}'"
        )
        if modify_response and "message" not in modify_response:
            modify_response["message"] = "Cron job modified successfully."
    else:
        error_message = (
            modify_response.get("message", "Unknown error modifying cron job")
            if modify_response
            else "Modify cron handler failed unexpectedly"
        )
        logger.error(f"API Modify Cron Job failed: {error_message}")
        if not modify_response:
            modify_response = {}
        modify_response["status"] = "error"
        if "message" not in modify_response:
            modify_response["message"] = "Failed to modify cron job."

    logger.debug(
        f"Returning JSON response for modify cron job API with status code {status_code}."
    )
    return jsonify(modify_response), status_code


# --- API Route: Delete Cron Job ---
@schedule_tasks_bp.route("/server/<server_name>/schedule/delete", methods=["POST"])
@login_required
def delete_cron_job_route(server_name):
    """API endpoint to delete a specific cron job."""
    logger.info(
        f"API POST request received to delete cron job (context: server '{server_name}')."
    )

    # Get JSON data
    data = request.get_json()
    logger.debug(f"Received JSON data for delete cron job: {data}")

    if not data or not isinstance(data, dict):
        logger.warning(f"API Delete Cron Job request: Empty or invalid JSON body.")
        return (
            jsonify(
                {"status": "error", "message": "Invalid or missing JSON request body."}
            ),
            400,
        )

    # Extract the cron job string to delete
    cron_string = data.get("cron_string")
    logger.debug(f"Cron string to delete: '{cron_string}'")

    if not cron_string or not isinstance(cron_string, str) or not cron_string.strip():
        logger.warning(f"API Delete Cron Job request: Missing or empty 'cron_string'.")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Cron job string ('cron_string') is required.",
                }
            ),
            400,
        )

    cron_string = cron_string.strip()

    logger.info(f"Attempting to delete cron job via handler: '{cron_string}'")
    # Call the handler to delete the job
    logger.debug("Calling delete_cron_job_handler...")
    delete_response = handlers.delete_cron_job_handler(cron_string)
    logger.debug(f"Delete cron job handler response: {delete_response}")

    # Determine status code
    status_code = (
        200 if delete_response and delete_response.get("status") == "success" else 500
    )

    if status_code == 200:
        logger.info(f"Cron job deleted successfully via API: '{cron_string}'")
        if delete_response and "message" not in delete_response:
            delete_response["message"] = "Cron job deleted successfully."
    else:
        error_message = (
            delete_response.get("message", "Unknown error deleting cron job")
            if delete_response
            else "Delete cron handler failed unexpectedly"
        )
        logger.error(f"API Delete Cron Job failed: {error_message}")
        if not delete_response:
            delete_response = {}
        delete_response["status"] = "error"
        if "message" not in delete_response:
            delete_response["message"] = "Failed to delete cron job."

    logger.debug(
        f"Returning JSON response for delete cron job API with status code {status_code}."
    )
    return jsonify(delete_response), status_code


# --- Route: Schedule Tasks Page (Windows) ---
@schedule_tasks_bp.route("/server/<server_name>/tasks", methods=["GET"])
@login_required
def schedule_tasks_windows_route(server_name):
    """Displays the Windows Task Scheduler management page for a server."""
    logger.info(
        f"Route '/server/{server_name}/tasks' accessed - Rendering Windows task schedule page."
    )
    base_dir = get_base_dir()  # Needed? Not directly used here.
    config_dir = settings.get("CONFIG_DIR")
    logger.debug(f"Config directory: {config_dir}")

    # Ensure this is running on Windows
    if platform.system() != "Windows":
        flash("Windows Task Scheduling is only available on Windows.", "error")
        logger.error(
            f"Attempted to access Windows task scheduler page for '{server_name}' from non-Windows OS."
        )
        return redirect(url_for("main_routes.index"))  # Redirect away if not Windows

    # Get task names associated with this server from the config directory
    logger.debug(f"Calling get_server_task_names_handler for '{server_name}'...")
    task_names_response = handlers.get_server_task_names_handler(
        server_name, config_dir
    )
    logger.debug(f"Get task names handler response: {task_names_response}")

    tasks = []  # Default empty list for template
    if task_names_response["status"] == "error":
        error_msg = f"Error retrieving associated task names for '{server_name}': {task_names_response.get('message', 'Unknown error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
    else:
        # Extract just the names from the handler response (which might include paths)
        task_names = [task[0] for task in task_names_response.get("task_names", [])]
        logger.debug(
            f"Found {len(task_names)} task names associated with '{server_name}': {task_names}"
        )

        if task_names:
            # Get detailed information for these tasks using the handler
            logger.debug(
                f"Calling get_windows_task_info_handler for tasks: {task_names}..."
            )
            task_info_response = handlers.get_windows_task_info_handler(task_names)
            logger.debug(f"Get task info handler response: {task_info_response}")

            if task_info_response["status"] == "error":
                error_msg = f"Error retrieving task details for '{server_name}': {task_info_response.get('message', 'Unknown error')}"
                flash(error_msg, "error")
                logger.error(error_msg)
            else:
                tasks = task_info_response.get("task_info", [])
                logger.debug(
                    f"Successfully retrieved details for {len(tasks)} Windows tasks."
                )
        else:
            logger.info(
                f"No Windows tasks found associated with server '{server_name}'."
            )

    # Render the Windows scheduling template
    logger.debug(f"Rendering schedule_tasks_windows.html for '{server_name}'.")
    return render_template(
        "schedule_tasks_windows.html",
        server_name=server_name,
        tasks=tasks,  # Pass the list of task detail dictionaries
        app_name=app_name,
    )


# --- Route: Add Windows Task Page ---
# Uses GET to display form, POST to handle submission
@schedule_tasks_bp.route("/server/<server_name>/tasks/add", methods=["GET", "POST"])
@login_required
def add_windows_task_route(server_name):
    """Displays form (GET) or handles submission (POST) for adding a new Windows scheduled task."""
    logger.info(
        f"Route '/server/{server_name}/tasks/add' accessed, method: {request.method}."
    )
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")
    logger.debug(f"Base directory: {base_dir}, Config directory: {config_dir}")

    # Ensure Windows OS
    if platform.system() != "Windows":
        flash("Windows Task Scheduling is only available on Windows.", "error")
        logger.error(
            f"Attempted to access add Windows task page for '{server_name}' from non-Windows OS."
        )
        return redirect(url_for("main_routes.index"))

    # Handle POST request (form submission)
    if request.method == "POST":
        logger.info(f"Processing POST request to add Windows task for '{server_name}'.")
        try:
            # Extract common task parameters
            command = request.form.get("command")
            logger.debug(f"Form data - command: '{command}'")

            # Determine command arguments based on selected command
            command_args = f"--server {server_name}"  # Default args
            valid_commands = [
                "update-server",
                "backup-all",
                "start-server",
                "stop-server",
                "restart-server",
                "scan-players",
            ]
            if command not in valid_commands:
                flash(
                    "Invalid command selected. Please choose a valid task action.",
                    "error",
                )
                logger.warning(
                    f"Invalid command '{command}' selected for Windows task creation."
                )
                # Re-render form on validation error
                return render_template(
                    "add_windows_task.html", server_name=server_name, app_name=app_name
                )

            if command == "scan-players":
                command_args = (
                    ""  # Scan players might not need server arg? Check handler.
                )

            logger.debug(f"Determined command_args: '{command_args}'")

            # Generate a task name (ensure uniqueness or handle collisions)
            task_name_base = command.replace(
                "-", "_"
            )  # Convert command to snake_case for task name
            task_name = f"bedrock_{server_name}_{task_name_base}"
            # TODO: Consider adding a timestamp or check for existing task_name to prevent collisions if needed.
            logger.debug(f"Generated task name: '{task_name}'")

            # --- Process Trigger Data ---
            triggers = []
            trigger_num = 1
            logger.debug("Parsing trigger data from form...")
            while (
                True
            ):  # Loop through potential trigger sections in the form (trigger_1, trigger_2, ...)
                trigger_type = request.form.get(f"trigger_type_{trigger_num}")
                if not trigger_type:
                    logger.debug(
                        f"No trigger data found for trigger number {trigger_num}. Stopping trigger parsing."
                    )
                    break  # No more triggers found in form

                logger.debug(f"Processing trigger {trigger_num}: Type='{trigger_type}'")
                trigger_data = {"type": trigger_type}

                # Get common start time/date
                start_datetime = request.form.get(f"start_{trigger_num}")
                if not start_datetime:
                    flash(
                        f"Missing start date/time for trigger {trigger_num}.", "error"
                    )
                    logger.warning(f"Missing start datetime for trigger {trigger_num}.")
                    # Re-render form on validation error
                    return render_template(
                        "add_windows_task.html",
                        server_name=server_name,
                        app_name=app_name,
                    )
                trigger_data["start"] = start_datetime
                logger.debug(f"Trigger {trigger_num} - Start: '{start_datetime}'")

                # Get type-specific details
                if trigger_type == "Daily":
                    interval_str = request.form.get(f"interval_{trigger_num}")
                    if (
                        not interval_str
                        or not interval_str.isdigit()
                        or int(interval_str) < 1
                    ):
                        flash(
                            f"Invalid daily interval for trigger {trigger_num}. Must be a positive number.",
                            "error",
                        )
                        logger.warning(
                            f"Invalid daily interval '{interval_str}' for trigger {trigger_num}."
                        )
                        return render_template(
                            "add_windows_task.html",
                            server_name=server_name,
                            app_name=app_name,
                        )
                    trigger_data["interval"] = int(interval_str)
                    logger.debug(
                        f"Trigger {trigger_num} - Daily Interval: {trigger_data['interval']}"
                    )
                elif trigger_type == "Weekly":
                    interval_str = request.form.get(f"interval_{trigger_num}")
                    days_of_week_str = request.form.get(
                        f"days_of_week_{trigger_num}", ""
                    )
                    if (
                        not interval_str
                        or not interval_str.isdigit()
                        or int(interval_str) < 1
                    ):
                        flash(
                            f"Invalid weekly interval for trigger {trigger_num}. Must be a positive number.",
                            "error",
                        )
                        logger.warning(
                            f"Invalid weekly interval '{interval_str}' for trigger {trigger_num}."
                        )
                        return render_template(
                            "add_windows_task.html",
                            server_name=server_name,
                            app_name=app_name,
                        )
                    trigger_data["interval"] = int(interval_str)
                    trigger_data["days"] = [
                        day.strip()
                        for day in days_of_week_str.split(",")
                        if day.strip()
                    ]
                    if not trigger_data["days"]:
                        flash(
                            f"At least one day must be selected for weekly trigger {trigger_num}.",
                            "error",
                        )
                        logger.warning(
                            f"No days selected for weekly trigger {trigger_num}."
                        )
                        return render_template(
                            "add_windows_task.html",
                            server_name=server_name,
                            app_name=app_name,
                        )
                    logger.debug(
                        f"Trigger {trigger_num} - Weekly Interval: {trigger_data['interval']}, Days: {trigger_data['days']}"
                    )
                elif trigger_type == "Monthly":
                    # Add validation for monthly triggers if needed (days, months)
                    days_of_month_str = request.form.get(
                        f"days_of_month_{trigger_num}", ""
                    )
                    months_str = request.form.get(f"months_{trigger_num}", "")
                    trigger_data["days"] = [
                        int(day.strip())
                        for day in days_of_month_str.split(",")
                        if day.strip().isdigit()
                    ]
                    trigger_data["months"] = [
                        month.strip()
                        for month in months_str.split(",")
                        if month.strip()
                    ]
                    # Add validation checks for days/months if necessary
                    logger.debug(
                        f"Trigger {trigger_num} - Monthly Days: {trigger_data['days']}, Months: {trigger_data['months']}"
                    )

                triggers.append(trigger_data)
                trigger_num += 1

            if not triggers:
                flash("At least one trigger must be defined for the task.", "error")
                logger.warning(
                    f"No triggers were defined for the new task '{task_name}'."
                )
                return render_template(
                    "add_windows_task.html", server_name=server_name, app_name=app_name
                )

            logger.debug(f"Parsed triggers for task creation: {triggers}")

            # --- Call handler to create the task ---
            logger.info(
                f"Calling create_windows_task_handler for task '{task_name}'..."
            )
            result = handlers.create_windows_task_handler(
                server_name=server_name,
                command=command,
                command_args=command_args,
                task_name=task_name,
                config_dir=config_dir,
                triggers=triggers,
                base_dir=base_dir,  # Pass base_dir if handler needs it
            )
            logger.debug(f"Create task handler result: {result}")

            # Handle handler response
            if result["status"] == "success":
                success_msg = f"Windows task '{task_name}' added successfully for server '{server_name}'!"
                flash(success_msg, "success")
                logger.info(success_msg)
                # Redirect to the task list page on success
                return redirect(
                    url_for(
                        "schedule_tasks_routes.schedule_tasks_windows_route",
                        server_name=server_name,
                    )
                )
            else:
                error_msg = f"Error adding Windows task '{task_name}': {result.get('message', 'Unknown handler error')}"
                flash(error_msg, "error")
                logger.error(error_msg)
                # Re-render the form, potentially pre-filling with submitted data (complex)
                # For simplicity, just re-render the blank form with the error message.
                return render_template(
                    "add_windows_task.html", server_name=server_name, app_name=app_name
                )

        except Exception as e:
            # Catch unexpected errors during form processing
            error_msg = f"An unexpected error occurred while processing the task creation form: {e}"
            flash(error_msg, "error")
            logger.exception(error_msg)  # Log full traceback
            return render_template(
                "add_windows_task.html", server_name=server_name, app_name=app_name
            )

    # Handle GET request (display the form)
    logger.debug(f"Rendering add_windows_task.html form for '{server_name}'.")
    return render_template(
        "add_windows_task.html", server_name=server_name, app_name=app_name
    )


# --- Helper Function for Modify Task Route ---
def _load_existing_task_data_for_modify(xml_file_path):
    """Helper to load task details for the modify form."""
    logger.debug(f"Loading existing task data from XML: {xml_file_path}")
    if not os.path.exists(xml_file_path):
        logger.error(f"Task XML file not found: {xml_file_path}")
        return {"error": "Task configuration file not found."}

    # Call handler to parse XML
    result = handlers.get_windows_task_details_handler(xml_file_path)
    if result.get("status") == "error":
        logger.error(f"Error parsing task XML {xml_file_path}: {result.get('message')}")
        return {"error": result.get("message", "Failed to parse task configuration.")}

    logger.debug(f"Successfully loaded task data from XML: {result}")
    # Return the dictionary containing 'command', 'triggers', etc.
    return result


# --- Route: Modify Windows Task Page ---
@schedule_tasks_bp.route(
    "/server/<server_name>/tasks/modify/<task_name>", methods=["GET", "POST"]
)
@login_required
def modify_windows_task_route(server_name, task_name):
    """Displays form (GET) or handles submission (POST) for modifying an existing Windows task."""
    logger.info(
        f"Route '/server/{server_name}/tasks/modify/{task_name}' accessed, method: {request.method}."
    )
    base_dir = get_base_dir()
    config_dir = settings.CONFIG_DIR  # Use attribute access if possible
    xml_file_path = os.path.join(config_dir, server_name, f"{task_name}.xml")
    logger.debug(
        f"Base directory: {base_dir}, Config directory: {config_dir}, XML path: {xml_file_path}"
    )

    # Ensure Windows OS
    if platform.system() != "Windows":
        flash("Windows Task Scheduling is only available on Windows.", "error")
        logger.error(
            f"Attempted to access modify Windows task page for '{task_name}' from non-Windows OS."
        )
        return redirect(url_for("main_routes.index"))

    # Handle POST request (form submission for modification)
    if request.method == "POST":
        logger.info(
            f"Processing POST request to modify Windows task '{task_name}' for '{server_name}'."
        )
        try:
            # Extract command from form
            command = request.form.get("command")
            logger.debug(f"Form data - command: '{command}'")

            # Determine command arguments (similar logic to add route)
            command_args = f"--server {server_name}"
            valid_commands = [
                "update-server",
                "backup-all",
                "start-server",
                "stop-server",
                "restart-server",
                "scan-players",
            ]
            if command not in valid_commands:
                flash("Invalid command selected.", "error")
                logger.warning(
                    f"Invalid command '{command}' selected for Windows task modification."
                )
                # Reload existing data to re-render form with error
                existing_task_data = _load_existing_task_data_for_modify(xml_file_path)
                return render_template(
                    "modify_windows_task.html",
                    server_name=server_name,
                    task_name=task_name,
                    **existing_task_data,
                    app_name=app_name,
                )

            if command == "scan-players":
                command_args = ""
            logger.debug(f"Determined command_args: '{command_args}'")

            # Generate the potentially new task name based on the selected command
            new_task_name_base = command.replace("-", "_")
            new_task_name = f"bedrock_{server_name}_{new_task_name_base}"
            logger.debug(
                f"New task name based on selected command: '{new_task_name}' (Old name: '{task_name}')"
            )

            # --- Process Trigger Data (similar logic to add route) ---
            triggers = []
            trigger_num = 1
            logger.debug("Parsing trigger data from modification form...")
            # (Include the same trigger parsing and validation as in the add route)
            while True:
                trigger_type = request.form.get(f"trigger_type_{trigger_num}")
                if not trigger_type:
                    break
                logger.debug(f"Processing trigger {trigger_num}: Type='{trigger_type}'")
                trigger_data = {"type": trigger_type}
                start_datetime = request.form.get(f"start_{trigger_num}")
                if not start_datetime:
                    flash(
                        f"Missing start date/time for trigger {trigger_num}.", "error"
                    )
                    logger.warning(
                        f"Missing start datetime for trigger {trigger_num} during modification."
                    )
                    existing_task_data = _load_existing_task_data_for_modify(
                        xml_file_path
                    )
                    return render_template(
                        "modify_windows_task.html",
                        server_name=server_name,
                        task_name=task_name,
                        **existing_task_data,
                        app_name=app_name,
                    )
                trigger_data["start"] = start_datetime
                if trigger_type == "Daily":
                    interval_str = request.form.get(f"interval_{trigger_num}")
                    if (
                        not interval_str
                        or not interval_str.isdigit()
                        or int(interval_str) < 1
                    ):
                        flash(
                            f"Invalid daily interval for trigger {trigger_num}.",
                            "error",
                        )
                        existing_task_data = _load_existing_task_data_for_modify(
                            xml_file_path
                        )
                        return render_template(
                            "modify_windows_task.html",
                            server_name=server_name,
                            task_name=task_name,
                            **existing_task_data,
                            app_name=app_name,
                        )
                    trigger_data["interval"] = int(interval_str)
                elif trigger_type == "Weekly":
                    interval_str = request.form.get(f"interval_{trigger_num}")
                    days_of_week_str = request.form.get(
                        f"days_of_week_{trigger_num}", ""
                    )
                    if (
                        not interval_str
                        or not interval_str.isdigit()
                        or int(interval_str) < 1
                    ):
                        flash(
                            f"Invalid weekly interval for trigger {trigger_num}.",
                            "error",
                        )
                        existing_task_data = _load_existing_task_data_for_modify(
                            xml_file_path
                        )
                        return render_template(
                            "modify_windows_task.html",
                            server_name=server_name,
                            task_name=task_name,
                            **existing_task_data,
                            app_name=app_name,
                        )
                    trigger_data["interval"] = int(interval_str)
                    trigger_data["days"] = [
                        day.strip()
                        for day in days_of_week_str.split(",")
                        if day.strip()
                    ]
                    if not trigger_data["days"]:
                        flash(
                            f"At least one day must be selected for weekly trigger {trigger_num}.",
                            "error",
                        )
                        existing_task_data = _load_existing_task_data_for_modify(
                            xml_file_path
                        )
                        return render_template(
                            "modify_windows_task.html",
                            server_name=server_name,
                            task_name=task_name,
                            **existing_task_data,
                            app_name=app_name,
                        )
                elif trigger_type == "Monthly":
                    days_of_month_str = request.form.get(
                        f"days_of_month_{trigger_num}", ""
                    )
                    months_str = request.form.get(f"months_{trigger_num}", "")
                    trigger_data["days"] = [
                        int(day.strip())
                        for day in days_of_month_str.split(",")
                        if day.strip().isdigit()
                    ]
                    trigger_data["months"] = [
                        month.strip()
                        for month in months_str.split(",")
                        if month.strip()
                    ]
                triggers.append(trigger_data)
                trigger_num += 1

            if not triggers:
                flash("At least one trigger must be defined for the task.", "error")
                logger.warning(
                    f"No triggers were defined during modification of task '{task_name}'."
                )
                existing_task_data = _load_existing_task_data_for_modify(xml_file_path)
                return render_template(
                    "modify_windows_task.html",
                    server_name=server_name,
                    task_name=task_name,
                    **existing_task_data,
                    app_name=app_name,
                )

            logger.debug(f"Parsed triggers for task modification: {triggers}")

            # --- Call handler to modify the task ---
            # This handler needs to potentially delete the old task and create the new one
            logger.info(
                f"Calling modify_windows_task_handler for old task '{task_name}', new task '{new_task_name}'..."
            )
            result = handlers.modify_windows_task_handler(
                old_task_name=task_name,  # Pass the original task name
                server_name=server_name,
                command=command,
                command_args=command_args,
                new_task_name=new_task_name,  # Pass the potentially new task name
                config_dir=config_dir,
                triggers=triggers,
                base_dir=base_dir,  # Pass base_dir if needed
            )
            logger.debug(f"Modify task handler result: {result}")

            # Handle handler response
            if result["status"] == "success":
                success_msg = f"Windows task '{task_name}' modified successfully! (New name may be '{new_task_name}')"
                flash(success_msg, "success")
                logger.info(success_msg)
                # Redirect to the task list page on success
                return redirect(
                    url_for(
                        "schedule_tasks_routes.schedule_tasks_windows_route",
                        server_name=server_name,
                    )
                )
            else:
                error_msg = f"Error modifying Windows task '{task_name}': {result.get('message', 'Unknown handler error')}"
                flash(error_msg, "error")
                logger.error(error_msg)
                # Re-load existing data (or maybe use submitted data?) and re-render form
                existing_task_data = _load_existing_task_data_for_modify(xml_file_path)
                return render_template(
                    "modify_windows_task.html",
                    server_name=server_name,
                    task_name=task_name,
                    **existing_task_data,
                    app_name=app_name,
                )

        except Exception as e:
            # Catch unexpected errors during form processing
            error_msg = f"An unexpected error occurred while processing the task modification form: {e}"
            flash(error_msg, "error")
            logger.exception(error_msg)  # Log full traceback
            existing_task_data = _load_existing_task_data_for_modify(xml_file_path)
            return render_template(
                "modify_windows_task.html",
                server_name=server_name,
                task_name=task_name,
                **existing_task_data,
                app_name=app_name,
            )

    # Handle GET request (display the modification form)
    else:
        logger.debug(
            f"GET request received for modifying task '{task_name}'. Loading existing data..."
        )
        # Load existing task data from XML to pre-populate the form
        existing_task_data = _load_existing_task_data_for_modify(xml_file_path)

        # Check if loading failed
        if "error" in existing_task_data:
            error_msg = f"Error loading data for task '{task_name}': {existing_task_data['error']}"
            logger.error(error_msg)
            flash(error_msg, "error")
            # Redirect back to the task list if data cannot be loaded
            return redirect(
                url_for(
                    "schedule_tasks_routes.schedule_tasks_windows_route",
                    server_name=server_name,
                )
            )

        # Render the modification form, passing existing data
        logger.debug(
            f"Rendering modify_windows_task.html form with data: {existing_task_data}"
        )
        return render_template(
            "modify_windows_task.html",
            server_name=server_name,
            task_name=task_name,  # Pass original task name
            **existing_task_data,  # Unpack loaded data (command, triggers, etc.)
            app_name=app_name,
        )


# --- Route: Delete Windows Task ---
@schedule_tasks_bp.route("/server/<server_name>/tasks/delete", methods=["POST"])
@login_required
def delete_windows_task_route(server_name):
    """Handles the POST request to delete an existing Windows scheduled task."""
    # This uses POST from a form, not a DELETE API endpoint currently
    logger.info(
        f"Route '/server/{server_name}/tasks/delete' accessed (POST) - Deleting Windows task."
    )
    base_dir = get_base_dir()  # Needed? Not directly used here.
    config_dir = settings.CONFIG_DIR
    logger.debug(f"Config directory: {config_dir}")

    # Ensure Windows OS
    if platform.system() != "Windows":
        flash("Windows Task Scheduling is only available on Windows.", "error")
        logger.error(
            f"Attempted to access delete Windows task action for '{server_name}' from non-Windows OS."
        )
        return redirect(url_for("main_routes.index"))

    # Get task name and potentially its config file path from the form
    task_name = request.form.get("task_name")
    task_file_path = request.form.get(
        "task_file_path"
    )  # Path to the XML file in config dir
    logger.debug(
        f"Received form data - task_name: '{task_name}', task_file_path: '{task_file_path}'"
    )

    # Validate required parameters
    if not task_name or not task_file_path:
        flash("Invalid task deletion request: Missing task name or file path.", "error")
        logger.warning(
            f"Invalid task deletion request for '{server_name}': Missing task name or file path."
        )
        # Redirect back to task list or index
        return redirect(
            url_for(
                "schedule_tasks_routes.schedule_tasks_windows_route",
                server_name=server_name,
            )
        )

    logger.info(
        f"Attempting to delete Windows task '{task_name}' for server '{server_name}'..."
    )
    # Call the handler to delete the task from Task Scheduler and remove the XML file
    logger.debug("Calling delete_windows_task_handler...")
    result = handlers.delete_windows_task_handler(
        task_name, task_file_path, base_dir=None
    )  # base_dir might not be needed? check handler
    logger.debug(f"Delete task handler result: {result}")

    # Flash message based on handler result
    if result["status"] == "error":
        error_msg = f"Error deleting Windows task '{task_name}': {result.get('message', 'Unknown handler error')}"
        flash(error_msg, "error")
        logger.error(error_msg)
    else:
        success_msg = f"Windows task '{task_name}' deleted successfully for server '{server_name}'!"
        flash(success_msg, "success")
        logger.info(success_msg)

    # Redirect back to the list of tasks for that server
    logger.debug(f"Redirecting back to Windows task list for '{server_name}'.")
    return redirect(
        url_for(
            "schedule_tasks_routes.schedule_tasks_windows_route",
            server_name=server_name,
        )
    )
