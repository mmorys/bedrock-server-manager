# bedrock-server-manager/bedrock_server_manager/web/routes/schedule_tasks_routes.py
import os
import platform
import logging
from bedrock_server_manager import handlers
from bedrock_server_manager.error import InvalidInputError
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.utils.general import get_timestamp
from bedrock_server_manager.config.settings import EXPATH, app_name
from bedrock_server_manager.web.routes.auth_routes import login_required
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)

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
@schedule_tasks_bp.route("/api/server/<server_name>/schedule/add", methods=["POST"])
@login_required
def add_cron_job_route(server_name):
    """API endpoint to add a new cron job."""
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
@schedule_tasks_bp.route("/api/server/<server_name>/schedule/modify", methods=["POST"])
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
@schedule_tasks_bp.route(
    "/api/server/<server_name>/schedule/delete", methods=["DELETE"]
)
@login_required
def delete_cron_job_route(server_name):
    """API endpoint to delete a specific cron job."""
    logger.info(
        f"API DELETE request received to delete cron job (context: server '{server_name}')."
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
    config_dir = settings._config_dir
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


# --- API Route: Add Windows Task ---
@schedule_tasks_bp.route("/api/server/<server_name>/tasks/add", methods=["POST"])
@login_required
def add_windows_task_api(server_name):
    """API endpoint to add a new Windows scheduled task."""
    logger.info(f"API POST request received for /api/server/{server_name}/tasks/add")
    base_dir = get_base_dir()
    config_dir = settings._config_dir

    # Ensure Windows OS
    if platform.system() != "Windows":
        logger.error(
            f"Add Windows task API called from non-Windows OS for server '{server_name}'."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Task scheduling only available on Windows.",
                }
            ),
            403,
        )  # Forbidden

    # Get JSON data from the request body
    data = request.get_json()
    if not data:
        logger.warning("API Add Windows Task request: Missing JSON body.")
        return (
            jsonify(
                {"status": "error", "message": "Missing or invalid JSON request body."}
            ),
            400,
        )

    logger.debug(f"Received JSON data for add task: {data}")

    # --- Extract data from JSON ---
    command = data.get("command")
    triggers = data.get(
        "triggers"
    )  # Expecting a list of trigger dicts [{type: "...", start: "...", ...}, ...]

    # --- Basic Validation ---
    valid_commands = [  # Keep this list aligned with your capabilities/frontend options
        "update-server",
        "backup-all",
        "start-server",
        "stop-server",
        "restart-server",
        "scan-players",
    ]
    if not command or command not in valid_commands:
        logger.warning(f"API Add Windows Task: Invalid or missing command '{command}'.")
        return (
            jsonify(
                {"status": "error", "message": f"Invalid or missing command specified."}
            ),
            400,
        )
    if not triggers or not isinstance(triggers, list) or len(triggers) == 0:
        logger.warning(
            f"API Add Windows Task: Missing, empty, or invalid triggers data."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "At least one trigger definition is required.",
                }
            ),
            400,
        )
    # TODO: Add deeper validation for the structure and values within each trigger dictionary
    # Example: check if 'type' and 'start' exist in each trigger, check specific fields per type
    for i, trigger in enumerate(triggers):
        if (
            not isinstance(trigger, dict)
            or not trigger.get("type")
            or not trigger.get("start")
        ):
            logger.warning(
                f"API Add Windows Task: Invalid trigger structure at index {i}: {trigger}"
            )
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Invalid trigger structure at index {i}.",
                    }
                ),
                400,
            )
        # Add more checks based on trigger type here if needed

    # --- Determine command arguments and task name ---
    # (This logic assumes task name is derived from command; adjust if needed)
    command_args = f"--server {server_name}"
    if command == "scan-players":
        command_args = (
            ""  # scan-players doesn't need --server arg based on previous examples
        )

    # Generate task name - IMPORTANT: Consider adding a unique identifier (timestamp/UUID)
    # to allow multiple tasks with the same command, otherwise adding again will overwrite.
    task_name_base = command.replace("-", "_")
    # Example with timestamp:
    # from ...utils import get_timestamp # Assuming you have a timestamp util
    # timestamp = get_timestamp(format="%Y%m%d%H%M%S")
    # task_name = f"bedrock_{server_name}_{task_name_base}_{timestamp}"
    # Simpler version (overwrites if command is the same):
    task_name = f"bedrock_{server_name}_{task_name_base}"
    logger.debug(
        f"API Add Windows Task: Determined args='{command_args}', task_name='{task_name}'"
    )

    # --- Call handler to create the task ---
    logger.info(
        f"Calling create_windows_task_handler for task '{task_name}' via API..."
    )
    try:
        result = handlers.create_windows_task_handler(
            server_name=server_name,
            command=command,  # Base command name
            command_args=command_args,  # Generated arguments
            task_name=task_name,  # Generated task name
            config_dir=config_dir,
            triggers=triggers,  # Pass the list of trigger dicts directly
            base_dir=base_dir,
        )
        logger.debug(f"Create task handler result: {result}")

    except InvalidInputError as e:  # Catch specific validation errors from handler/core
        logger.warning(f"Invalid input during task creation for '{task_name}': {e}")
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:  # Catch unexpected errors during handler execution
        logger.exception(
            f"Unexpected error during create_windows_task_handler call for '{task_name}': {e}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "An unexpected error occurred while creating the task.",
                }
            ),
            500,
        )

    # --- Return JSON Response based on handler result ---
    if result and result.get("status") == "success":
        status_code = 201  # HTTP 201 Created is appropriate for successful creation
        logger.info(f"Windows task '{task_name}' added successfully via API.")
        if (
            "message" not in result
        ):  # Add a default success message if handler doesn't provide one
            result["message"] = f"Task '{task_name}' created successfully."
        # Optionally include the created task name or details in the response body
        result["created_task_name"] = task_name
        return jsonify(result), status_code
    else:
        status_code = 500  # Default Internal Server Error for handler failure
        logger.error(
            f"API Add Windows Task failed for '{task_name}': {result.get('message', 'Unknown handler error')}"
        )
        # Ensure result is a dict even if handler failed unexpectedly
        if not isinstance(result, dict):
            result = {"status": "error", "message": "Handler failed unexpectedly."}
        elif "status" not in result:
            result["status"] = "error"
        return jsonify(result), status_code


# --- API Route: Get Windows Task Details ---
@schedule_tasks_bp.route(
    "/api/server/<server_name>/tasks/details/<path:task_name>", methods=["GET"]
)
@login_required
def get_windows_task_details_api(server_name, task_name):
    """API endpoint to get details for a specific Windows scheduled task by parsing its XML config."""
    logger.info(
        f"API GET request received for /api/server/{server_name}/tasks/details/{task_name}"
    )
    config_dir = settings._config_dir

    # Ensure Windows OS
    if platform.system() != "Windows":
        logger.error(
            f"Get Windows task details API called from non-Windows OS for task '{task_name}'."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Task scheduling only available on Windows.",
                }
            ),
            403,
        )

    if not task_name:
        logger.warning(f"API Get Windows Task Details request: Missing task name.")
        return jsonify({"status": "error", "message": "Task name is required."}), 400

    # --- Find the task file path using the HANDLER ---
    task_file_path = None
    try:
        task_list_result = handlers.get_server_task_names_handler(
            server_name, config_dir
        )
        if task_list_result and task_list_result.get("status") == "success":
            task_names_with_paths = task_list_result.get("task_names", [])
            for name, path in task_names_with_paths:
                normalized_name = str(name).lstrip("\\") if name else ""
                if normalized_name == task_name:
                    task_file_path = path
                    break
        if not task_file_path:
            logger.error(
                f"API Get Details: Configuration file path not found for task '{task_name}'."
            )
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Configuration file for task '{task_name}' not found.",
                    }
                ),
                404,
            )
    except Exception as e:
        logger.exception(
            f"Error finding task file path for '{task_name}' during get details API call: {e}"
        )
        return (
            jsonify(
                {"status": "error", "message": "Error finding task configuration path."}
            ),
            500,
        )

    # --- Call the ENHANCED details handler ---
    logger.debug(
        f"Calling handler 'get_windows_task_details_handler' for task '{task_name}' (path: {task_file_path})..."
    )
    try:
        # This handler now returns more details including base_command and structured triggers
        result = handlers.get_windows_task_details_handler(task_file_path)
    except Exception as handler_ex:
        logger.exception(
            f"Unexpected error calling get_windows_task_details_handler for path '{task_file_path}': {handler_ex}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Unexpected error retrieving task details from handler.",
                }
            ),
            500,
        )

    # --- Process handler result ---
    if result and result.get("status") == "success":
        logger.debug(
            f"Successfully retrieved details for task '{task_name}' via API handler."
        )
        task_details = result.get("task_details", {})  # Get the nested details dict
        # Ensure the status is included in the final response for consistency
        response_data = {
            "status": "success",
            **task_details,
        }  # Unpack details (base_command, triggers, etc.)
        return jsonify(response_data), 200  # OK
    else:
        logger.error(
            f"API Get Windows Task Details failed for '{task_name}'. Handler message: {result.get('message')}"
        )
        status_code = 404 if "not found" in result.get("message", "").lower() else 500
        if not isinstance(result, dict):
            result = {
                "status": "error",
                "message": "Handler returned unexpected result.",
            }
        elif "status" not in result:
            result["status"] = "error"
        return jsonify(result), status_code


# --- API Route: Modify Windows Task ---
@schedule_tasks_bp.route(
    "/api/server/<server_name>/tasks/modify/<path:task_name>", methods=["PUT"]
)
@login_required
def modify_windows_task_api(server_name, task_name):
    """
    API endpoint to modify an existing Windows scheduled task.
    Receives the complete desired state (command, triggers) in the JSON payload.
    """
    logger.info(
        f"API PUT request received for /api/server/{server_name}/tasks/modify/{task_name}"
    )
    base_dir = get_base_dir()
    config_dir = settings._config_dir

    # Ensure Windows OS
    if platform.system() != "Windows":
        logger.error(
            f"Modify Windows task API called from non-Windows OS for task '{task_name}'."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Task scheduling only available on Windows.",
                }
            ),
            403,
        )

    # Get JSON data from request body
    data = request.get_json()
    if not data:
        logger.warning(f"API Modify Windows Task request: Missing JSON body.")
        return (
            jsonify({"status": "error", "message": "Missing JSON request body."}),
            400,
        )

    logger.debug(f"Received JSON data for modify task '{task_name}': {data}")

    # --- Extract desired state from JSON ---
    command = data.get("command")  # The new desired command (e.g., "start-server")
    triggers = data.get("triggers")  # The new desired list of triggers

    # --- Basic Validation ---
    valid_commands = [  # Keep this list updated
        "update-server",
        "backup-all",
        "start-server",
        "stop-server",
        "restart-server",
        "scan-players",
    ]
    if not task_name:
        logger.error(
            f"API Modify Windows Task request: Missing original task name in URL."
        )
        return (
            jsonify(
                {"status": "error", "message": "Original task name is required in URL."}
            ),
            400,
        )
    if not command or command not in valid_commands:
        logger.warning(
            f"API Modify Windows Task: Invalid or missing command '{command}' in JSON payload."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Invalid or missing command specified in request body.",
                }
            ),
            400,
        )
    if not triggers or not isinstance(triggers, list) or len(triggers) == 0:
        logger.warning(
            f"API Modify Windows Task: Missing, empty, or invalid triggers data in JSON payload."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "At least one trigger definition is required in request body.",
                }
            ),
            400,
        )
    # TODO: Deeper validation of trigger structure/values

    # --- Determine command args for the NEW command ---
    command_args = f"--server {server_name}"
    if command == "scan-players":
        command_args = ""
    command = data.get("base_command")
    logger.debug(
        f"API Modify Windows Task: Using command='{command}', args='{command_args}' for new/updated task."
    )

    # --- Generate the New Task Name (based on the *submitted* command) ---
    # This allows changing the command to also change the task name, as before
    new_task_name_base = command
    timestamp = get_timestamp()
    new_task_name = f"bedrock_{server_name}_{new_task_name_base}_{timestamp}"
    logger.debug(
        f"API Modify Windows Task: OldName='{task_name}', Generated NewName='{new_task_name}'"
    )

    # --- Call the modify handler ---
    # Pass the OLD name, the NEW desired state (command, args, triggers), and the NEW name
    logger.info(
        f"Calling modify_windows_task_handler for old task '{task_name}', new task '{new_task_name}' via API..."
    )
    try:
        result = handlers.modify_windows_task_handler(
            old_task_name=task_name,  # Original task name from URL
            server_name=server_name,  # Server context
            command=command,  # NEW desired command from JSON
            command_args="",  # Args corresponding to NEW command
            new_task_name=new_task_name,  # Generated new task name
            config_dir=config_dir,
            triggers=triggers,  # NEW trigger definitions from JSON
            base_dir=base_dir,
        )
        logger.debug(f"Modify task handler result: {result}")

    except InvalidInputError as e:
        logger.warning(
            f"Invalid input during task modification handler for '{task_name}': {e}"
        )
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.exception(
            f"Unexpected error during modify_windows_task_handler call for '{task_name}': {e}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "An unexpected error occurred while modifying the task.",
                }
            ),
            500,
        )

    # --- Return JSON Response based on handler result ---
    if result and result.get("status") == "success":
        status_code = 200  # OK
        logger.info(
            f"Windows task '{task_name}' modified successfully via API. New task name is '{new_task_name}'."
        )
        if "message" not in result:
            result["message"] = (
                f"Task '{task_name}' updated successfully as '{new_task_name}'."
            )
        result["new_task_name"] = new_task_name  # Include new name in response
        return jsonify(result), status_code
    else:
        status_code = 500  # Default Internal Server Error
        logger.error(
            f"API Modify Windows Task failed for '{task_name}'. Handler message: {result.get('message', 'Unknown handler error')}"
        )
        if not isinstance(result, dict):
            result = {"status": "error", "message": "Handler failed unexpectedly."}
        elif "status" not in result:
            result["status"] = "error"
        return jsonify(result), status_code


# --- Route: Delete Windows Task ---
@schedule_tasks_bp.route(
    "/api/server/<server_name>/tasks/delete/<path:task_name>", methods=["DELETE"]
)
@login_required
def delete_windows_task_api(server_name, task_name):
    """API endpoint to delete an existing Windows scheduled task."""
    logger.info(
        f"API DELETE request received for /api/server/{server_name}/tasks/delete/{task_name}"
    )
    config_dir = settings._config_dir

    # Ensure Windows OS
    if platform.system() != "Windows":
        logger.error(
            f"Delete Windows task API called from non-Windows OS for task '{task_name}'."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Task scheduling only available on Windows.",
                }
            ),
            403,
        )  # Forbidden

    if not task_name:
        logger.warning(f"API Delete Windows Task request: Missing task name.")
        return jsonify({"status": "error", "message": "Task name is required."}), 400

    logger.info(
        f"Attempting to delete Windows task '{task_name}' via API for server '{server_name}'..."
    )

    # --- Find the task file path ---
    task_file_path = None
    # Use the api to find the path
    get_names_result = handlers.get_server_task_names_handler(server_name, config_dir)
    if get_names_result["status"] == "success":
        task_names_with_paths = get_names_result["task_names"]

    for name, path in task_names_with_paths:
        # Task names from XML might have leading '\', match carefully
        normalized_name = name.lstrip("\\")
        if normalized_name == task_name:
            task_file_path = path
            logger.debug(f"Found config file path for '{task_name}': {task_file_path}")
            break
    if not task_file_path:
        logger.warning(
            f"Could not find configuration file path for task '{task_name}'. Task might only exist in scheduler, not config. Proceeding with scheduler delete only."
        )
        # If deleting the XML is critical, return error here:
        # return jsonify({"status": "error", "message": f"Configuration file for task '{task_name}' not found."}), 404

    # --- End Find Path ---

    # Call the handler
    logger.debug("Calling delete_windows_task_handler...")
    logger.info(task_file_path)
    result = handlers.delete_windows_task_handler(
        task_name, task_file_path
    )  # Pass name and potentially None path
    logger.debug(f"Delete task handler result: {result}")

    if result["status"] == "error":
        status_code = 500
        logger.error(
            f"API Delete Windows Task failed for '{task_name}': {result.get('message', 'Unknown handler error')}"
        )
        return jsonify(result), status_code
    else:
        logger.info(f"Windows task '{task_name}' deleted successfully via API.")
        if "message" not in result:
            result["message"] = f"Task '{task_name}' deleted successfully."
        return jsonify(result), 200  # OK
