import pytest
from unittest.mock import MagicMock
from bedrock_server_manager.web import tasks
from bedrock_server_manager.error import BSMError


def test_create_task():
    """Test creating a new task."""
    task_id = tasks.create_task()
    assert isinstance(task_id, str)
    status = tasks.get_task(task_id)
    assert status["status"] == "pending"


def test_run_task_success():
    """Test running a task that completes successfully."""
    task_id = tasks.create_task()
    target_function = MagicMock(return_value={"status": "success"})
    tasks.run_task(task_id, target_function, "arg1", kwarg1="kwarg1")

    status = tasks.get_task(task_id)
    assert status["status"] == "success"
    assert status["result"] == {"status": "success"}
    target_function.assert_called_once_with("arg1", kwarg1="kwarg1")


def test_run_task_failure():
    """Test running a task that fails."""
    task_id = tasks.create_task()
    target_function = MagicMock(side_effect=BSMError("Task failed"))
    tasks.run_task(task_id, target_function)

    status = tasks.get_task(task_id)
    assert status["status"] == "error"
    assert "Task failed" in status["message"]


def test_get_task_not_found():
    """Test getting the status of a task that does not exist."""
    status = tasks.get_task("invalid_task_id")
    assert status is None
