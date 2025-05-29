# bedrock-server-manager/bedrock_server_manager/api/web.py
import logging
from typing import Dict, Optional, Any, List, Union

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.web.app import run_web_server

# Core imports
from bedrock_server_manager.core import web as core_web_ops
from bedrock_server_manager.core.system import process as core_process_ops
from bedrock_server_manager.error import (
    ConfigurationError,
    ExecutableNotFoundError,
    PIDFileError,
    ProcessManagementError,
    ProcessVerificationError,
    WebServerCoreError,
)

logger = logging.getLogger("bedrock_server_manager")


def start_web_server(
    host: Optional[Union[str, List[str]]] = None,
    debug: bool = False,
    mode: str = "direct",
) -> Dict[str, Any]:
    """
    Starts the Flask/Waitress web server.

    Can run in two modes:
    - 'direct': Runs the server in the current process (blocking).
    - 'detached': Starts the server as a new background process and saves its PID to a file.

    Args:
        host: Optional host address or list of host addresses.
        debug: If True, run in Flask's debug mode.
        mode: "direct" (default) or "detached".

    Returns:
        Dict indicating outcome.
    """
    mode = mode.lower()
    if mode not in ["direct", "detached"]:
        logger.error(f"API: Invalid mode '{mode}' specified for start_web_server.")
        return {
            "status": "error",
            "message": "Invalid mode specified. Must be 'direct' or 'detached'.",
        }

    logger.info(f"API: Attempting to start web server in '{mode}' mode...")
    logger.debug(f"Host='{host}', Debug={debug}")

    if mode == "direct":
        logger.info("API: Running web server directly (blocking process)...")
        try:
            run_web_server(host, debug)  # This blocks
            logger.info("API: Web server (direct mode) stopped.")
            return {"status": "success", "message": "Web server shut down."}
        except RuntimeError as e:  # Flask/Waitress configuration errors
            logger.critical(
                f"API: Failed to start web server due to configuration error: {e}",
                exc_info=True,
            )
            return {"status": "error", "message": f"Configuration error: {e}"}
        except ImportError as e:  # Missing web server dependencies
            logger.critical(f"API: Failed to start web server: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"API: Error running web server directly: {e}", exc_info=True)
            return {"status": "error", "message": f"Error running web server: {e}"}

    elif mode == "detached":
        logger.info("API: Starting web server in detached mode (background process)...")
        try:
            config_dir = getattr(settings, "_config_dir", None)
            if not config_dir:
                raise ConfigurationError(
                    "Application configuration directory not set in settings."
                )

            pid_file_path = core_web_ops.get_web_pid_file_path(config_dir)

            # Check if server might already be running based on PID file
            existing_pid = None
            try:
                existing_pid = core_process_ops.read_pid_from_file(pid_file_path)
            except PIDFileError as e:
                logger.warning(
                    f"API: Problem reading existing PID file '{pid_file_path}': {e}. Attempting to proceed assuming it's stale/corrupt."
                )
                core_process_ops.remove_pid_file_if_exists(
                    pid_file_path
                )  # Clean up problematic file

            if existing_pid is not None:
                if not PSUTIL_AVAILABLE:
                    logger.warning(
                        f"API: PID file '{pid_file_path}' exists (PID {existing_pid}), "
                        "but 'psutil' is not available to verify if the process is running. "
                        "Proceeding with caution. If the server is already running, starting another may cause issues."
                    )
                    # Decide if this is an error or just a warning for the API user.
                    # For now, let's treat it as an error to prevent accidental multiple launches.
                    return {
                        "status": "error",
                        "message": f"PID file for PID {existing_pid} exists but process status cannot be verified (psutil not installed). Please stop manually or remove '{pid_file_path}' if stale.",
                    }
                elif core_process_ops.is_process_running(existing_pid):
                    logger.warning(
                        f"API: Detached web server might already be running (PID {existing_pid} found in '{pid_file_path}' and process exists). Aborting start."
                    )
                    return {
                        "status": "error",
                        "message": f"Web server already running (PID: {existing_pid}). Stop it first or delete the PID file ({pid_file_path}) if it's stale.",
                    }
                else:
                    logger.warning(
                        f"API: Stale PID file found ('{pid_file_path}' with PID {existing_pid}, process not running). Cleaning up before starting new."
                    )
                    core_process_ops.remove_pid_file_if_exists(
                        pid_file_path
                    )  # Clean up stale file before new launch

            # Prepare host arguments for the command
            host_cmd_args = []
            if host:
                if isinstance(host, list):
                    if host:  # Ensure the list is not empty
                        host_cmd_args.append("--host")
                        host_cmd_args.extend(
                            [str(h) for h in host if h]
                        )  # Ensure elements are strings
                elif isinstance(host, str) and host:
                    host_cmd_args.extend(["--host", str(host)])
                else:
                    logger.warning(
                        f"API: Unexpected type or empty value for host: {type(host)}. Ignoring host parameter for detached command."
                    )

            # Use the core_web_ops to launch the detached server
            new_pid = core_web_ops.start_detached_web_server(
                expath=settings._expath,
                config_dir=config_dir,
                host_args=host_cmd_args if host_cmd_args else None,
                debug_flag=debug,
            )
            return {
                "status": "success",
                "pid": new_pid,
                "message": f"Web server started in detached mode (PID: {new_pid}).",
            }
        except ConfigurationError as e:
            logger.error(
                f"API: Configuration error preventing detached start: {e}",
                exc_info=True,
            )
            return {"status": "error", "message": f"Configuration error: {e}"}
        except (ExecutableNotFoundError, ProcessManagementError, PIDFileError) as e:
            logger.error(
                f"API: Failed to manage server process for detached start: {e}",
                exc_info=True,
            )
            return {"status": "error", "message": f"Process management error: {e}"}
        except WebServerCoreError as e:  # Catch any other general core errors
            logger.error(
                f"API: Core error starting detached web server: {e}", exc_info=True
            )
            return {"status": "error", "message": f"Core server error: {e}"}
        except Exception as e:  # General catch-all for unexpected API-level errors
            logger.error(
                f"API: Unexpected error starting detached web server: {e}",
                exc_info=True,
            )
            return {"status": "error", "message": f"Unexpected error: {e}"}


def stop_web_server() -> Dict[str, str]:
    """
    Attempts to stop the detached web server process using its stored PID file.
    Verifies the process identity before termination.
    """
    function_name_api = "API:stop_web_server"
    logger.info(
        f"{function_name_api}: Request received to stop the detached web server process."
    )

    if not PSUTIL_AVAILABLE:
        msg = "Cannot stop server: 'psutil' package is required but not installed for process operations."
        logger.error(f"{function_name_api}: {msg}")
        return {"status": "error", "message": msg}

    try:
        config_dir = getattr(settings, "_config_dir", None)
        if not config_dir:
            raise ConfigurationError(
                "Application configuration directory not set in settings."
            )

        stopped_pid = core_web_ops.stop_running_web_server(
            config_dir=config_dir, expected_server_executable_path=settings._expath
        )

        if stopped_pid is None:
            return {
                "status": "success",
                "message": "Web server process not running (no PID file or process found).",
            }
        else:
            return {
                "status": "success",
                "message": f"Web server process (PID: {stopped_pid}) stopped successfully.",
            }

    except PIDFileError as e:
        logger.error(
            f"{function_name_api}: Error related to PID file: {e}", exc_info=True
        )
        # If the file was problematic (empty/invalid content), it's likely already removed by core.
        return {"status": "error", "message": f"PID file error: {e}"}
    except ProcessVerificationError as e:
        logger.error(
            f"{function_name_api}: Process verification failed: {e}", exc_info=True
        )
        # Core handles removing the PID file if verification fails.
        return {
            "status": "error",
            "message": f"Process verification failed: {e}. Stale PID file removed.",
        }
    except ProcessManagementError as e:
        logger.error(
            f"{function_name_api}: Process management error: {e}", exc_info=True
        )
        # If the core error indicates the process disappeared, it's a success, otherwise an error.
        if "disappeared or was already stopped" in str(e).lower():
            # Extract PID from error message if possible for a better message
            pid_val = "unknown"
            if "PID " in str(e):
                try:
                    pid_val = str(e).split("PID ")[1].split(" ")[0]
                except (IndexError, ValueError):
                    pass
            return {
                "status": "success",
                "message": f"Web server process (PID: {pid_val}) already stopped. PID file removed.",
            }
        return {"status": "error", "message": f"Process management error: {e}"}
    except ConfigurationError as e:
        logger.error(f"{function_name_api}: Configuration error: {e}", exc_info=True)
        return {"status": "error", "message": f"Configuration error: {e}"}
    except WebServerCoreError as e:  # Catch any other specific core errors
        logger.error(
            f"{function_name_api}: Core error stopping web server: {e}", exc_info=True
        )
        return {"status": "error", "message": f"Core server error: {e}"}
    except Exception as e:  # General catch-all for unexpected API-level errors
        logger.error(
            f"{function_name_api}: Unexpected error stopping web server: {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}
