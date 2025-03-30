# bedrock-server-manager/bedrock_server_manager/api/web.py
import os
import logging
import subprocess
from bedrock_server_manager.core import SCRIPT_DIR
from bedrock_server_manager.web.app import run_web_server
from bedrock_server_manager.config.settings import EXPATH


logger = logging.getLogger("bedrock_server_manager")


def start_web_server(host=None, debug=False, mode="direct"):
    """Starts the web server with defined host with optional debug mode

    Args:
        host (str, optional): The base directory for servers. Defaults to None.
        debug (bool, optional): Starts the server in debug mode
    """
    if mode == "direct":
        logger.info("Running web-server directly...")
        try:
            run_web_server(host, debug)
            return {"status": "success"}
        except Exception as e:
            logger.exception(f"Error updating server statuses: {e}")
            return {
                "status": "error",
                "message": f"Error updating server statuses: {e}",
            }

    elif mode == "detached":
        logger.info("Running web-server in detached mode...")
        try:
            command = [str(EXPATH), "start-webserver"]
            if host:
                command.extend(["--host", host])
            if debug:
                command.append("--debug")
            command.extend(["--mode", "direct"])

            process = subprocess.Popen(
                command,
                cwd=SCRIPT_DIR,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                ),  # Don't open a console
            )

            logger.info(f"Started web server with PID: {process.pid}")
            return {"status": "success", "process": process.pid}

        except FileNotFoundError:
            logger.error(f"Executable or script not found: {EXPATH}")
            return {"status": "error", "message": f"Executable not found: {EXPATH}"}
        except Exception as e:
            logger.exception(f"Error starting process: {e}")
            return {"status": "error", "message": str(e)}


def stop_web_server():
    try:
        logger.warning("Not implemented")
    except Exception as e:
        logger.exception(f"Error starting process: {e}")
        return {"status": "error", "message": str(e)}
    return {"status": "success"}
