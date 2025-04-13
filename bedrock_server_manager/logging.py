# bedrock-server-manager/bedrock_server_manager/logging.py
"""
Configures and manages logging for the bedrock-server-manager application.

Provides functions to set up file rotation and console logging,
and to add separator lines to log files for clarity during restarts.
"""

import logging
import logging.handlers
import os
import platform
import sys
from datetime import datetime
from typing import Optional

# --- Constants ---
DEFAULT_LOG_DIR: str = "logs"  # Default directory if not specified by settings
DEFAULT_LOG_KEEP: int = 3  # Default number of backup logs to keep


def setup_logging(
    log_dir: str = DEFAULT_LOG_DIR,
    log_filename: str = "bedrock_server_manager.log",
    log_keep: int = DEFAULT_LOG_KEEP,
    log_level: int = logging.INFO,
    when: str = "midnight",
    interval: int = 1,
) -> logging.Logger:
    """
    Sets up the root logger with timed rotating file and console handlers.

    Configures logging to write detailed information to a specified file
    with daily rotation by default, and outputs a simpler format (level/message)
    to the console. Prevents adding duplicate handlers if called multiple times.

    Args:
        log_dir: Directory to store log files. Defaults to DEFAULT_LOG_DIR.
        log_filename: The base name of the log file.
        log_keep: Number of backup log files to keep. Defaults to DEFAULT_LOG_KEEP.
        log_level: The minimum log level to record (e.g., logging.INFO, logging.DEBUG).
        when: Time interval for rotation (e.g., 'midnight', 'h', 'd').
              See TimedRotatingFileHandler documentation.
        interval: The interval number based on 'when' (e.g., 1 for daily if when='midnight').

    Returns:
        The configured logger instance for "bedrock_server_manager".
    """
    logger = logging.getLogger("bedrock_server_manager")
    logger.setLevel(log_level)  # Set the threshold for the logger

    # Prevent adding handlers multiple times if this function is called again
    if not logger.hasHandlers():
        # Ensure log directory exists
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as e:
            # Log error but try to continue - console logging might still work
            logging.error(
                f"Could not create log directory '{log_dir}': {e}", exc_info=True
            )
            # Attempt console-only setup if dir creation fails
            try:
                console_formatter = logging.Formatter("%(levelname)s: %(message)s")
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(console_formatter)
                console_handler.setLevel(log_level)
                logger.addHandler(console_handler)
                logger.warning(
                    f"File logging disabled due to directory error for '{log_dir}'. Using console logging only."
                )
            except Exception as console_e:
                logging.error(
                    f"Failed to set up even console logging: {console_e}", exc_info=True
                )
            return (
                logger  # Return logger even if only console handler worked or neither
            )

        log_path = os.path.join(log_dir, log_filename)

        try:
            # --- Define Log Formats ---
            # Detailed format for the file
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s"
            )
            # Simple format for the console
            console_formatter = logging.Formatter("%(levelname)s: %(message)s")

            # --- File Handler ---
            # Rotates logs at specified interval
            file_handler = logging.handlers.TimedRotatingFileHandler(
                log_path,
                when=when,
                interval=interval,
                backupCount=log_keep,
                encoding="utf-8",
            )
            file_handler.setLevel(log_level)  # Handler level also respects the setting
            file_handler.setFormatter(file_formatter)  # Use detailed formatter
            logger.addHandler(file_handler)

            # --- Console Handler ---
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(console_formatter)  # Use simple formatter
            logger.addHandler(console_handler)

        except Exception as e:
            # Use the root logger's basic config if our handlers fail
            logging.error(
                f"Failed to configure custom log handlers for {log_path}: {e}",
                exc_info=True,
            )
            # Fallback: attempt to add just a basic console handler if none were added
            if not logger.hasHandlers():
                try:
                    console_formatter = logging.Formatter("%(levelname)s: %(message)s")
                    console_handler = logging.StreamHandler(sys.stdout)
                    console_handler.setFormatter(console_formatter)
                    console_handler.setLevel(log_level)
                    logger.addHandler(console_handler)
                    logger.warning(
                        "Using basic console logging due to configuration error."
                    )
                except Exception as console_e:
                    logging.error(
                        f"Failed to set up fallback console logging: {console_e}",
                        exc_info=True,
                    )

        # Log initial setup message using the configured handlers
        logger.debug(
            f"Logging setup complete. Log path: '{log_path}', Level: {logging.getLevelName(log_level)}, Rotation: {when} (interval {interval}), Keep: {log_keep}"
        )
    else:
        logger.debug("Logging already configured. Skipping setup.")

    return logger


def log_separator(
    logger: logging.Logger,
    app_name: Optional[str] = "BedrockServerManager",
    app_version: str = "0.0.0",
) -> None:
    """
    Writes a separator line with system and app info directly to file handlers.

    This helps visually distinguish application restarts or different runs
    within the log files. Information includes OS, Python version, app name/version,
    and timestamp. It writes directly to the stream of FileHandler instances.

    Args:
        logger: The logger object whose file handlers will be written to.
        app_name: The name of the application (optional).
        app_version: The version of the application (optional).
    """
    try:
        os_name = platform.system()
        os_version = platform.release()
        os_info = f"{os_name} {os_version}"
        if os_name == "Windows":
            os_info = f"{os_name} {platform.version()}"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        python_version = platform.python_version()

        separator_line = "=" * 100
        info_lines = [
            f"{app_name or 'Application'} v{app_version}",
            f"Operating System: {os_info}",
            f"Python Version: {python_version}",
            f"Timestamp: {current_time}",
        ]

        logger.debug(
            f"Attempting to write log separator. App: {app_name}, Version: {app_version}"
        )

        handlers_written = 0
        for handler in logger.handlers:
            # Only write to file-based handlers that seem active
            if isinstance(
                handler,
                (logging.FileHandler, logging.handlers.TimedRotatingFileHandler),
            ):
                # Check if the stream exists and is not closed (basic check)
                if (
                    hasattr(handler, "stream")
                    and handler.stream
                    and not handler.stream.closed
                ):
                    try:
                        handler.stream.write("\n" + separator_line + "\n")
                        for line in info_lines:
                            handler.stream.write(line + "\n")
                        handler.stream.write(separator_line + "\n\n")
                        handler.stream.flush()  # Ensure it's written immediately
                        logger.debug(
                            f"Separator written to handler's stream: {getattr(handler, 'baseFilename', 'Unknown File')}"
                        )
                        handlers_written += 1
                    except ValueError as e:
                        # This specific check helps diagnose closed file issues
                        if "I/O operation on closed file" in str(e):
                            logger.warning(
                                f"Could not write separator to log file (stream closed): {getattr(handler, 'baseFilename', 'Unknown File')} - {e}"
                            )
                        else:
                            # Re-raise other ValueErrors, logging them first
                            logger.exception(
                                f"ValueError writing separator to log file {getattr(handler, 'baseFilename', 'Unknown File')}: {e}"
                            )
                            # Depending on policy, you might re-raise here: raise
                    except Exception as e:
                        # Catch other unexpected errors during write/flush
                        logger.exception(
                            f"Unexpected error writing separator to log file {getattr(handler, 'baseFilename', 'Unknown File')}: {e}"
                        )
                        # Depending on policy, you might re-raise here: raise
                else:
                    logger.debug(
                        f"Skipping handler for separator write (no stream/stream closed): {handler}"
                    )

        if handlers_written == 0:
            logger.debug(
                "Log separator not written to any file handlers (none found or streams closed)."
            )

    except Exception as e:
        # Catch errors happening *before* the loop (e.g., platform calls)
        logger.error(f"Failed to prepare or write log separator: {e}", exc_info=True)
