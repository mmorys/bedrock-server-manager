# bedrock-server-manager/bedrock_server_manager/core/logging.py
import logging
import logging.handlers
import os
import time

DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_KEEP = 3


def setup_logging(
    log_dir=DEFAULT_LOG_DIR,
    log_filename="bedrock_server.log",
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
    os.makedirs(log_dir, exist_ok=True)  # Create log directory if it doesn't exist
    log_path = os.path.join(log_dir, log_filename)

    # Create a logger

    logger.debug(
        f"Setting up logging.  Dir: {log_dir}, Filename: {log_filename}, Level: {log_level}"
    )

    try:
        # Create a rotating file handler
        handler = logging.handlers.TimedRotatingFileHandler(
            log_path, when=when, interval=interval, backupCount=log_keep
        )
        handler.setLevel(log_level)  # Set level on the HANDLER

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
        console_handler.setLevel(log_level)  # Set level on the HANDLER
        logger.addHandler(console_handler)

    except Exception as e:
        logging.error(f"Failed to create log handler: {e}")

    return logger  # return the logger
