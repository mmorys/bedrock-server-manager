# bedrock-server-manager/bedrock_server_manager/core/logging.py
import logging
import logging.handlers
import os
import platform
from datetime import datetime
import sys

DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_KEEP = 3


def setup_logging(
    log_dir=DEFAULT_LOG_DIR,
    log_filename="bedrock_server_manager.log",
    log_keep=DEFAULT_LOG_KEEP,
    log_level=logging.INFO,
    when="midnight",
    interval=1,
):
    """Sets up the logging configuration with daily rotation.

    Args:
        log_dir (str): Directory to store log files.
        log_filename (str): The base name of the log file.
        log_keep (int): Number of backup log files to keep.
        log_level (int): The minimum log level to record.
        when (str):  Indicates when to rotate. See TimedRotatingFileHandler docs.
        interval (int): The rotation interval.
    """
    logger = logging.getLogger("bedrock_server_manager")
    logger.setLevel(log_level)  # Set logger level

    if not logger.hasHandlers():  # Prevent duplicate handlers
        os.makedirs(log_dir, exist_ok=True)  # Create log directory if it doesn't exist
        log_path = os.path.join(log_dir, log_filename)

        try:
            # Create a rotating file handler
            handler = logging.handlers.TimedRotatingFileHandler(
                log_path, when=when, interval=interval, backupCount=log_keep
            )
            handler.setLevel(log_level)

            # Create a formatter
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)

            # Add the handler to the logger
            logger.addHandler(handler)

            # Add console output
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            console_handler.setLevel(log_level)
            logger.addHandler(console_handler)

        except Exception as e:
            logging.error(f"Failed to create log handler: {e}")

        logger.debug(
            f"Logging setup complete. Dir: {log_dir}, Filename: {log_filename}, Level: {log_level}"
        )

    return logger


def log_separator(logger, app_name=None, app_version="0.0.0"):
    """Writes a separator line to the file handler, including OS, app version,
       app name, Python version, and time.

    Args:
        logger: The logger object.
        app_name: The name of the application.
        app_version: The version of the application.
    """

    os_name = platform.system()
    os_version = platform.release()
    os_info = f"{os_name} {os_version}"
    if os_name == "Windows":
        os_info = f"{os_name} {platform.version()}"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    python_version = platform.python_version()  # Get the Python version

    separator_line = "=" * 100
    info_lines = [
        f"{app_name} v{app_version}",
        f"Operating System: {os_info}",
        f"Python Version: {python_version}",
        f"Timestamp: {current_time}",
    ]
    # logger.debug(f"Writing separator to log files. App: {app_name}, Version: {app_version}")

    for handler in logger.handlers:
        if isinstance(
            handler, (logging.FileHandler, logging.handlers.TimedRotatingFileHandler)
        ):
            if hasattr(handler, "stream") and handler.stream is not None:
                try:
                    handler.stream.write("\n" + separator_line + "\n")
                    for line in info_lines:
                        handler.stream.write(line + "\n")
                    handler.stream.write(separator_line + "\n\n")
                    handler.stream.flush()
                    # logger.debug(f"Separator written to {handler.baseFilename}")
                except ValueError as e:
                    if "I/O operation on closed file" in str(e):
                        # Handle the case where the stream is closed
                        logger.warning(
                            f"Could not write to log file (stream closed): {handler.baseFilename} - {e}"
                        )
                        print(
                            f"Warning: Could not write to log file (stream closed): {e}",
                            file=sys.stderr,
                        )
                    else:
                        # Re-raise other ValueErrors
                        logger.exception(
                            f"ValueError writing to log file {handler.baseFilename}: {e}"
                        )
                        raise
                except Exception as e:  # catch more generic exception
                    logger.exception(
                        f"Unexpected error writing to log file {handler.baseFilename}: {e}"
                    )
                    raise
