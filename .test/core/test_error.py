# bedrock-server-manager/tests/core/test_error.py
import pytest
from bedrock_server_manager.core.error import (
    ServerNotFoundError,
    CommandNotFoundError,
    BedrockManagerError,
)


def test_server_not_found_error_attributes():
    """Test the custom attributes and __str__ method of ServerNotFoundError."""
    error = ServerNotFoundError("/path/to/server")
    assert error.server_path == "/path/to/server"
    assert error.message == "Server executable not found."
    assert str(error) == "Server executable not found.: /path/to/server"

    error2 = ServerNotFoundError("/another/path", message="Custom message")
    assert error2.server_path == "/another/path"
    assert error2.message == "Custom message"
    assert str(error2) == "Custom message: /another/path"


def test_command_not_found_error_attributes():
    """Test the custom attributes and __str__ of CommandNotFoundError."""
    error = CommandNotFoundError("some_command")
    assert error.command_name == "some_command"
    assert error.message == "Command not found"
    assert str(error) == "Command not found: some_command"

    error2 = CommandNotFoundError("another_command", "Custom Message")
    assert error2.command_name == "another_command"
    assert error2.message == "Custom Message"
    assert str(error2) == "Custom Message: another_command"


def test_bedrock_manager_error_inheritance():
    """Verify that custom exceptions inherit from BedrockManagerError."""
    error = ServerNotFoundError("/path/to/server")
    assert isinstance(error, BedrockManagerError)

    error2 = CommandNotFoundError("some_command")
    assert isinstance(error2, BedrockManagerError)
