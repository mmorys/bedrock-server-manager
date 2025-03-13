# bedrock-server-manager/tests/core/test_logging.py
import logging
import logging.handlers
import os
from functools import partial
from unittest.mock import patch, MagicMock
import pytest
from bedrock_server_manager.core.logging import (
    setup_logging,
    DEFAULT_LOG_DIR,
    DEFAULT_BACKUP_COUNT,
)


# --- Fixtures ---
@pytest.fixture(autouse=True)  # added autouse
def reset_logging_mocks():
    """Resets logging mocks before each test."""
    logging.getLogger("bedrock_server_manager").handlers = []  # Clear existing handlers
    yield


@pytest.fixture
def mock_log_dir(tmp_path):
    log_dir = tmp_path / "test_logs"
    log_dir.mkdir()
    yield str(log_dir)  # Return as string for os.path.join


# --- Tests ---


def test_setup_logging_creates_log_directory(mock_log_dir):
    """Test that the log directory is created."""
    setup_logging(log_dir=mock_log_dir)
    assert os.path.exists(mock_log_dir)


def test_setup_logging_creates_timed_rotating_file_handler(mock_log_dir):
    """Test that a TimedRotatingFileHandler is created and added to the logger."""
    logger = setup_logging(log_dir=mock_log_dir)
    assert any(
        isinstance(handler, logging.handlers.TimedRotatingFileHandler)
        for handler in logger.handlers
    )


def test_setup_logging_sets_log_level(mock_log_dir):
    """Test that the logger's log level is set correctly."""
    logger = setup_logging(log_dir=mock_log_dir, log_level=logging.DEBUG)
    assert logger.level == logging.DEBUG
    logger = setup_logging(log_dir=mock_log_dir, log_level=logging.WARNING)
    assert logger.level == logging.WARNING


def test_setup_logging_uses_default_values(mock_log_dir):
    """Test that default values are used when not provided."""
    with patch(
        "logging.handlers.TimedRotatingFileHandler"
    ) as MockTimedRotatingFileHandler:
        logger = setup_logging(log_dir=mock_log_dir)  # Call setup_logging
        MockTimedRotatingFileHandler.assert_called_once_with(
            os.path.join(mock_log_dir, "bedrock_server.log"),
            when="midnight",
            interval=1,
            backupCount=DEFAULT_BACKUP_COUNT,  # Use the module-level constant here
        )
    assert len(logger.handlers) == 2


def test_setup_logging_uses_custom_values(mock_log_dir):
    """Test using custom values for log parameters."""
    custom_filename = "custom.log"
    custom_backup_count = 5
    with patch(
        "logging.handlers.TimedRotatingFileHandler"
    ) as MockTimedRotatingFileHandler:
        setup_logging(
            log_dir=mock_log_dir,
            log_filename=custom_filename,
            backup_count=custom_backup_count,
        )
        MockTimedRotatingFileHandler.assert_called_once_with(
            os.path.join(mock_log_dir, custom_filename),
            when="midnight",  # Include default values for TimedRotatingFileHandler
            interval=1,
            backupCount=custom_backup_count,
        )


def test_setup_logging_adds_console_handler(mock_log_dir):
    """Test that a StreamHandler (console output) is added."""
    logger = setup_logging(log_dir=mock_log_dir)
    assert any(
        isinstance(handler, logging.StreamHandler) for handler in logger.handlers
    )


def test_setup_logging_formatter_is_applied(
    tmp_path,
):  # remove mock_log_dir and use tmp_path
    """Test that the formatter is applied to both handlers."""
    logger = setup_logging(log_dir=str(tmp_path))  # use tmp_path
    for handler in logger.handlers:
        assert handler.formatter is not None
        assert isinstance(handler.formatter, logging.Formatter)  # Correct check
        assert (
            handler.formatter._fmt
            == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )


def test_setup_logging_returns_logger(mock_log_dir):
    """Test that the setup_logging returns logger."""
    logger = setup_logging(log_dir=mock_log_dir)
    assert isinstance(logger, logging.Logger)


@patch("os.makedirs")  # We keep the mock
def test_setup_logging_handles_makedirs_error(mock_makedirs, tmp_path):
    """Test that setup_logging handles errors during directory creation."""
    log_dir = str(tmp_path / "logs")  # Convert to string

    # Mock os.makedirs to raise OSError
    mock_makedirs.side_effect = OSError("Mocked makedirs error")
    mock_makedirs.return_value = None

    # Expect a FileNotFoundError, since the parent directory doesn't exist
    with pytest.raises(OSError, match="Mocked makedirs error"):
        # Call setup_logging with exist_ok=False (forced by our mocking)
        setup_logging(log_dir=log_dir)
    mock_makedirs.assert_called_once()  # Check that os.makedirs was called


@patch(
    "logging.handlers.TimedRotatingFileHandler",
    side_effect=Exception("Mocked handler exception"),
)
def test_setup_logging_handles_handler_creation_error(
    mock_handler, mock_log_dir, caplog
):
    """Test that setup_logging handles errors during handler creation gracefully."""
    with caplog.at_level(logging.ERROR):  # capture error logs
        setup_logging(log_dir=mock_log_dir)

    assert (
        "Mocked handler exception" in caplog.text
    )  # Check if the exception message is logged
