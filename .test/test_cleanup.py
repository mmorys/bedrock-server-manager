# bedrock-server-manager/tests/test_cleanup.py
import os
import shutil
import logging
from unittest.mock import patch, MagicMock, call
from bedrock_server_manager.core import SCRIPT_DIR
import pytest
from bedrock_server_manager.cleanup import cleanup_cache, cleanup_logs
from bedrock_server_manager.config import settings

# --- Fixtures ---


@pytest.fixture
def mock_script_dir(tmp_path):
    """Creates a temporary directory structure for testing."""
    script_dir = tmp_path / "script_dir"
    script_dir.mkdir()
    (script_dir / "subdir1").mkdir()
    (script_dir / "subdir1" / "__pycache__").mkdir()
    (script_dir / "subdir2").mkdir()
    (script_dir / "subdir2" / "__pycache__").mkdir()
    (script_dir / "__pycache__").mkdir()
    with patch("bedrock_server_manager.cleanup.SCRIPT_DIR", str(script_dir)):
        yield script_dir


@pytest.fixture
def mock_log_dir(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "log1.txt").touch()
    (log_dir / "log2.txt").touch()

    with patch("bedrock_server_manager.cleanup.settings.settings", str(log_dir)):
        yield log_dir


@pytest.fixture(autouse=True)  # Apply to all tests in this file
def mock_logging_setup():
    with patch("bedrock_server_manager.cleanup.logger") as mock_logger:
        yield mock_logger


# --- Tests for cleanup_cache ---


def test_cleanup_cache_deletes_pycache_directories(mock_script_dir):
    """Test that cleanup_cache removes __pycache__ directories."""
    deleted_count = cleanup_cache()
    assert deleted_count == 3
    assert not (mock_script_dir / "__pycache__").exists()
    assert not (mock_script_dir / "subdir1" / "__pycache__").exists()
    assert not (mock_script_dir / "subdir2" / "__pycache__").exists()
    assert (mock_script_dir / "subdir1").exists()
    assert (mock_script_dir / "subdir2").exists()


def test_cleanup_cache_no_pycache_directories(tmp_path):
    """Test cleanup_cache when there are no __pycache__ directories."""
    with patch("bedrock_server_manager.cleanup.SCRIPT_DIR", str(tmp_path)):
        deleted_count = cleanup_cache()
    assert deleted_count == 0


@patch("bedrock_server_manager.cleanup.logger")
def test_cleanup_cache_verbose_output(mock_logger, mock_script_dir):
    """Test verbose output of cleanup_cache."""
    cleanup_cache(verbose=True)

    expected_calls = [call.info(f"Deleted: {mock_script_dir / '__pycache__'}")]
    mock_logger.info.assert_has_calls(expected_calls, any_order=True)


@patch("bedrock_server_manager.cleanup.logger")
@patch("shutil.rmtree", side_effect=OSError("Mocked rmtree error"))
def test_cleanup_cache_handles_deletion_error(
    mock_rmtree, mock_logger, mock_script_dir
):
    """Test that cleanup_cache handles errors during directory deletion."""
    deleted_count = cleanup_cache()
    assert deleted_count == 0
    mock_logger.error.assert_called()


# --- Tests for cleanup_logs ---


def test_cleanup_logs_deletes_log_files(mock_log_dir):
    """Test that cleanup_logs removes log files."""
    deleted_count = cleanup_logs(log_dir=mock_log_dir)
    assert deleted_count == 2
    assert not (mock_log_dir / "log1.txt").exists()
    assert not (mock_log_dir / "log2.txt").exists()


def test_cleanup_logs_no_log_files(tmp_path):
    """Test cleanup_logs when there are no log files."""
    deleted_count = cleanup_logs(log_dir=tmp_path)
    assert deleted_count == 0


def test_cleanup_logs_verbose_output(mock_log_dir):
    """Test verbose output of cleanup_logs."""
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = mock_get_logger.return_value
        cleanup_logs(log_dir=mock_log_dir, verbose=True)

        expected_calls = [
            call.info(f"Deleted: {os.path.join(str(mock_log_dir), 'log1.txt')}"),
            call.info(f"Deleted: {os.path.join(str(mock_log_dir), 'log2.txt')}"),
            call.info("Deleted 2 log files."),
        ]

        mock_logger.info.assert_has_calls(expected_calls, any_order=True)


@patch("os.remove", side_effect=OSError("Mocked remove error"))
def test_cleanup_logs_handles_deletion_error(mock_remove, mock_log_dir):
    """Test that cleanup_logs handles errors during file deletion."""
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = mock_get_logger.return_value
        deleted_count = cleanup_logs(mock_log_dir)
        assert deleted_count == 0
        assert mock_logger.error.call_count >= 1


@patch("bedrock_server_manager.cleanup.logger")
def test_cleanup_logs_closes_and_removes_handlers(mock_logger, mock_log_dir):
    """Test that log handlers are properly closed and removed."""
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = mock_get_logger.return_value
        # Create mock handlers and attach them to the logger
        mock_handler1 = MagicMock(spec=logging.FileHandler)
        mock_handler2 = MagicMock(spec=logging.FileHandler)
        mock_logger.handlers = [mock_handler1, mock_handler2]

        cleanup_logs(mock_log_dir)

        mock_handler1.close.assert_called_once()
        mock_handler2.close.assert_called_once()
        mock_logger.removeHandler.assert_has_calls(
            [call(mock_handler1), call(mock_handler2)]
        )


@patch("bedrock_server_manager.cleanup.logger")
def test_cleanup_logs_error_closing_handler(mock_logger, mock_log_dir):
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = mock_get_logger.return_value
        # Mock FileHandler to raise exception when close is called
        mock_file_handler = MagicMock(spec=logging.FileHandler)
        mock_file_handler.close.side_effect = Exception("Mocked handler error")
        mock_logger.handlers = [mock_file_handler]

        cleanup_logs(mock_log_dir)

        # Assert that the error message is logged
        mock_logger.error.assert_called_once_with(
            f"Error closing log handler: Mocked handler error"
        )
