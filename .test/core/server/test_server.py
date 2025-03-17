# bedrock-server-manager/tests/core/server/test_server.py
import os
import subprocess
import platform
import json
import pytest
from unittest.mock import patch, MagicMock, call, mock_open
from bedrock_server_manager.config import settings
from bedrock_server_manager.core.server import backup
from bedrock_server_manager.core.download import downloader
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.core.system import linux as system_linux
from bedrock_server_manager.core.system import windows as system_windows
from bedrock_server_manager.core.server.server import (
    BedrockServer,
    get_world_name,
    validate_server,
    manage_server_config,
    get_installed_version,
    check_server_status,
    get_server_status_from_config,
    update_server_status_in_config,
    configure_allowlist,
    add_players_to_allowlist,
    configure_permissions,
    modify_server_properties,
    _write_version_config,
    install_server,
    no_update_needed,
    delete_server_data,
    start_server_if_was_running,
    stop_server_if_running,
    modify_server_properties,
    _write_version_config,
    install_server,
    no_update_needed,
    delete_server_data,
    start_server_if_was_running,
    stop_server_if_running,
)
from bedrock_server_manager.core.error import (
    ServerStartError,
    ServerStopError,
    ServerNotRunningError,
    SendCommandError,
    ServerNotFoundError,
    InvalidServerNameError,
    MissingArgumentError,
    FileOperationError,
    ConfigError,
    InvalidInputError,
    CommandNotFoundError,
    DirectoryError,
    InstallUpdateError,
)


# --- Fixtures ---
@pytest.fixture
def mock_settings_server(tmp_path):
    """Fixture to mock the settings object."""
    mock_settings = MagicMock()
    mock_settings.BASE_DIR = str(tmp_path / "servers")  # Use a temp dir
    mock_settings.CONFIG_DIR = str(tmp_path / "config")
    # Add other settings attributes as needed, setting defaults
    with patch("bedrock_server_manager.core.server.server.settings", mock_settings):
        yield mock_settings


@pytest.fixture
def mock_bedrock_server(mock_settings_server):
    server_name = "test_server"
    server_dir = os.path.join(mock_settings_server.BASE_DIR, server_name)
    os.makedirs(server_dir, exist_ok=True)

    # Create a dummy executable
    if platform.system() == "Windows":
        exe_name = "bedrock_server.exe"
    else:
        exe_name = "bedrock_server"

    server_path = os.path.join(server_dir, exe_name)
    with open(server_path, "w") as f:
        f.write("")  # Minimal content

    return server_name, server_path, server_dir


# --- Tests for BedrockServer class ---


def test_bedrock_server_init_successful(mock_bedrock_server):
    """Test successful initialization of the BedrockServer class."""
    server_name, server_path, server_dir = mock_bedrock_server
    server = BedrockServer(server_name)
    assert server.server_name == server_name
    assert server.server_path == server_path
    assert server.server_dir == server_dir
    assert server.process is None
    assert server.status == "STOPPED"


def test_bedrock_server_init_server_not_found(mock_settings_server):
    """Test initialization with a server that doesn't exist."""
    server_name = "nonexistent_server"
    with pytest.raises(ServerNotFoundError):
        BedrockServer(server_name)


@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=True)
def test_bedrock_server_is_running_true(mock_is_running, mock_bedrock_server):
    """Test is_running() when the server is running."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    assert server.is_running() is True
    mock_is_running.assert_called_once()


@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=False)
def test_bedrock_server_is_running_false(mock_is_running, mock_bedrock_server):
    """Test is_running() when the server is not running."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    assert server.is_running() is False
    mock_is_running.assert_called_once()


@patch(
    "bedrock_server_manager.core.system.base._get_bedrock_process_info",
    return_value={"pid": 1234},
)
def test_bedrock_server_get_pid(mock_get_info, mock_bedrock_server):
    """Test get_pid()."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    assert server.get_pid() == 1234


@patch(
    "bedrock_server_manager.core.system.base._get_bedrock_process_info",
    return_value=None,
)
def test_bedrock_server_get_pid_not_running(mock_get_info, mock_bedrock_server):
    """Test get_pid() when the server is not running."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    assert server.get_pid() is None


@patch(
    "bedrock_server_manager.core.system.base._get_bedrock_process_info",
    return_value={"cpu_percent": 50.5},
)
def test_bedrock_server_get_cpu_usage(mock_get_info, mock_bedrock_server):
    """Test get_cpu_usage()."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    assert server.get_cpu_usage() == 50.5


@patch(
    "bedrock_server_manager.core.system.base._get_bedrock_process_info",
    return_value={"memory_mb": 1024.7},
)
def test_bedrock_server_get_memory_usage(mock_get_info, mock_bedrock_server):
    """Test get_memory_usage()."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    assert server.get_memory_usage() == 1024.7


@patch(
    "bedrock_server_manager.core.system.base._get_bedrock_process_info",
    return_value={"uptime": 3600},
)
def test_bedrock_server_get_uptime(mock_get_info, mock_bedrock_server):
    """Test get_uptime()."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    assert server.get_uptime() == 3600


# --- Tests for BedrockServer.send_command ---


@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=True)
@patch("subprocess.run")
def test_bedrock_server_send_command_linux(
    mock_subprocess_run, mock_is_running, mock_bedrock_server
):
    """Test sending a command on Linux (using screen)."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    command = "say Hello"

    with patch("platform.system", return_value="Linux"):
        server.send_command(command)

        mock_subprocess_run.assert_called_once_with(
            ["screen", "-S", f"bedrock-{server_name}", "-X", "stuff", f"{command}\n"],
            check=True,
        )


@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=True)
def test_bedrock_server_send_command_windows(mock_is_running, mock_bedrock_server):
    """Test sending a command on Windows (using process.stdin)."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    command = "say Hello"

    # Mock the process object and its stdin
    mock_process = MagicMock()
    mock_process.stdin.write = MagicMock()
    mock_process.stdin.flush = MagicMock()
    server.process = mock_process  # Assign the mocked process

    with patch("platform.system", return_value="Windows"):
        server.send_command(command)
        mock_process.stdin.write.assert_called_once_with(f"{command}\n".encode())
        mock_process.stdin.flush.assert_called_once()


def test_bedrock_server_send_command_missing_command(mock_bedrock_server):
    """Test sending a command with an empty command."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    with pytest.raises(MissingArgumentError):
        server.send_command("")


@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=False)
def test_bedrock_server_send_command_server_not_running(
    mock_is_running, mock_bedrock_server
):
    """Test sending a command when the server is not running."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    command = "say Hello"
    with pytest.raises(ServerNotRunningError):
        server.send_command(command)


@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=True)
@patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "screen"))
def test_bedrock_server_send_command_linux_error(
    mock_subprocess_run, mock_is_running, mock_bedrock_server
):
    """Test handling an error when sending a command on Linux (screen error)."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    command = "say Hello"

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(SendCommandError):
            server.send_command(command)


@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=True)
@patch("subprocess.run", side_effect=FileNotFoundError)
def test_bedrock_server_send_command_linux_screen_not_found(
    mock_subprocess_run, mock_is_running, mock_bedrock_server
):
    """Test when 'screen' command is not found on Linux."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    command = "say Hello"
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(CommandNotFoundError):
            server.send_command(command)


@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=True)
def test_bedrock_server_send_command_windows_process_missing(
    mock_is_running, mock_bedrock_server
):
    """Test Windows command send with a missing process object."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    command = "say Hello"

    with patch("platform.system", return_value="Windows"):
        # Don't set server.process, simulating the error condition
        with pytest.raises(ServerNotRunningError):
            server.send_command(command)


@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=True)
def test_bedrock_server_send_command_windows_stdin_error(
    mock_is_running, mock_bedrock_server
):
    """Test handling error writing into stdin"""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    command = "say Hello"

    # Mock the process object and its stdin
    mock_process = MagicMock()
    mock_process.stdin.write = MagicMock(
        side_effect=Exception("Mocked stdin error")
    )  # added
    mock_process.stdin.flush = MagicMock()  # added
    server.process = mock_process  # Assign the mocked process

    with patch("platform.system", return_value="Windows"):
        with pytest.raises(SendCommandError):
            server.send_command(command)


# --- Tests for BedrockServer.start ---


@patch("bedrock_server_manager.core.server.server.manage_server_config")
@patch(
    "bedrock_server_manager.core.system.base.is_server_running",
    side_effect=[False, True],
)  # Simulate server starting
@patch("subprocess.run")
def test_bedrock_server_start_linux_systemd(
    mock_subprocess_run, mock_is_running, mock_config, mock_bedrock_server
):
    """Test starting the server on Linux (using systemd)."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    service_name = f"bedrock-{server_name}"

    with patch("platform.system", return_value="Linux"):
        server.start()

        mock_subprocess_run.assert_called_once_with(
            ["systemctl", "--user", "start", service_name], check=True
        )
        assert server.status == "RUNNING"
        assert mock_config.call_count == 2


@patch("bedrock_server_manager.core.server.server.manage_server_config")
@patch(
    "bedrock_server_manager.core.system.base.is_server_running",
    side_effect=[False, True],
)  # Simulate server starting
@patch("bedrock_server_manager.core.system.linux._systemd_start_server")
@patch(
    "subprocess.run", side_effect=subprocess.CalledProcessError(1, "systemctl")
)  # Simulate systemctl failure
def test_bedrock_server_start_linux_screen_fallback(
    mock_subprocess_run,
    mock_systemd_start,
    mock_is_running,
    mock_config,
    mock_bedrock_server,
):
    """Test starting the server on Linux (falling back to screen)."""
    server_name, server_path, server_dir = mock_bedrock_server
    server = BedrockServer(server_name)

    with patch("platform.system", return_value="Linux"):
        server.start()

        mock_subprocess_run.assert_called_once()  # systemctl call
        mock_systemd_start.assert_called_once_with(
            server_name, os.path.dirname(server_path)
        )
        assert server.status == "RUNNING"
        assert mock_config.call_count == 2


@patch("bedrock_server_manager.core.server.server.manage_server_config")
@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=True)
def test_bedrock_server_start_already_running(
    mock_is_running, mock_config, mock_bedrock_server
):
    """Test starting the server when it's already running."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)

    with pytest.raises(ServerStartError, match="Server is already running!"):
        server.start()


@patch("bedrock_server_manager.core.server.server.manage_server_config")
@patch(
    "bedrock_server_manager.core.system.base.is_server_running", return_value=False
)  # Always return False
@patch("subprocess.run")
def test_bedrock_server_start_linux_timeout(
    mock_subprocess_run, mock_is_running, mock_config, mock_bedrock_server
):
    """Test that the server start times out if it doesn't start."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(
            ServerStartError, match="Server '.*' failed to start within the timeout."
        ):
            server.start()
        assert server.status == "ERROR"
        assert mock_config.call_count == 2


@patch("bedrock_server_manager.core.system.windows._windows_start_server")
@patch("bedrock_server_manager.core.server.server.manage_server_config")
@patch(
    "bedrock_server_manager.core.system.base.is_server_running",
    side_effect=[False, True],
)
def test_bedrock_server_start_windows(
    mock_is_running, mock_config, mock_windows_start, mock_bedrock_server
):
    """Test starting on windows"""
    server_name, server_path, server_dir = mock_bedrock_server
    server = BedrockServer(server_name)

    with patch("platform.system", return_value="Windows"):
        server.start()

        mock_windows_start.assert_called_once_with(server_name, server_dir)
        assert server.status == "RUNNING"
        assert mock_config.call_count == 2


def test_bedrock_server_start_unsupported_os(mock_bedrock_server):
    """Test start on an unsupported OS."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)

    with patch("platform.system", return_value="Solaris"):  # Unsupported OS
        with pytest.raises(ServerStartError, match="Unsupported operating system"):
            server.start()


# --- Tests for BedrockServer.stop ---


@patch("bedrock_server_manager.core.server.server.manage_server_config")
@patch(
    "bedrock_server_manager.core.system.base.is_server_running",
    side_effect=[True, False],
)  # Simulate server stopping
@patch("subprocess.run")
def test_bedrock_server_stop_linux_systemd(
    mock_subprocess_run, mock_is_running, mock_config, mock_bedrock_server
):
    """Test stopping the server on Linux (using systemd)."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    service_name = f"bedrock-{server_name}"

    with patch("platform.system", return_value="Linux"):
        server.stop()

        mock_subprocess_run.assert_called_once_with(
            ["systemctl", "--user", "stop", service_name], check=True
        )
        assert mock_config.call_count == 2
        assert server.status == "STOPPED"


@patch("bedrock_server_manager.core.server.server.manage_server_config")
@patch(
    "bedrock_server_manager.core.system.base.is_server_running",
    side_effect=[True, False],
)  # Simulate server stopping
@patch("bedrock_server_manager.core.system.linux._systemd_stop_server")
@patch(
    "subprocess.run", side_effect=subprocess.CalledProcessError(1, "systemctl")
)  # systemctl fails
def test_bedrock_server_stop_linux_screen_fallback(
    mock_subprocess_run,
    mock_systemd_stop,
    mock_is_running,
    mock_config,
    mock_bedrock_server,
):
    """Test stopping the server on Linux (falling back to screen)."""
    server_name, server_path, server_dir = mock_bedrock_server
    server = BedrockServer(server_name)
    with patch("platform.system", return_value="Linux"):
        server.stop()

        mock_subprocess_run.assert_called_once()
        mock_systemd_stop.assert_called_once_with(
            server_name, os.path.dirname(server_path)
        )
        assert mock_config.call_count == 2
        assert server.status == "STOPPED"


@patch("bedrock_server_manager.core.server.server.manage_server_config")
@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=False)
def test_bedrock_server_stop_not_running(
    mock_is_running, mock_config, mock_bedrock_server
):
    """Test stopping the server when it's already stopped."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)
    # Shouldn't raise an exception or do anything
    server.stop()
    mock_is_running.assert_called_once()
    mock_config.assert_not_called()


@patch("bedrock_server_manager.core.server.server.manage_server_config")
@patch(
    "bedrock_server_manager.core.system.base.is_server_running", return_value=True
)  # Always true - timeout
@patch("subprocess.run")
def test_bedrock_server_stop_linux_timeout(
    mock_subprocess_run, mock_is_running, mock_config, mock_bedrock_server
):
    """Test that the server stop times out if it doesn't stop."""
    server_name, _, _ = mock_bedrock_server
    server = BedrockServer(server_name)

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(
            ServerStopError, match="Server '.*' failed to stop within the timeout"
        ):
            server.stop()


@patch("bedrock_server_manager.core.system.windows._windows_stop_server")
@patch("bedrock_server_manager.core.server.server.manage_server_config")
@patch(
    "bedrock_server_manager.core.system.base.is_server_running",
    side_effect=[True, False],
)
def test_bedrock_server_stop_windows(
    mock_is_running, mock_config, mock_windows_stop, mock_bedrock_server
):
    """Test stopping on Windows"""
    server_name, server_path, server_dir = mock_bedrock_server
    server = BedrockServer(server_name)

    with patch("platform.system", return_value="Windows"):
        server.stop()
        mock_windows_stop.assert_called_once_with(server_name, server_dir)
        assert mock_config.call_count == 2
        assert server.status == "STOPPED"


@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=True)
def test_bedrock_server_stop_unsupported_os(mock_is_running, mock_bedrock_server):
    """Test stop on unsupported OS"""
    server_name, _, _ = mock_bedrock_server  # Unpack the tuple correctly
    server = BedrockServer(server_name)
    with patch("platform.system", return_value="Solaris"):  # Unsupported OS
        with pytest.raises(
            ServerStopError, match="Unsupported operating system for stopping server."
        ):  # updated match
            server.stop()


# --- Tests for get_world_name ---


def test_get_world_name_successful(tmp_path):
    """Test successful retrieval of the world name."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    properties_file = server_dir / "server.properties"
    # Create a dummy server.properties file
    with open(properties_file, "w") as f:
        f.write("some-property=some-value\n")
        f.write("level-name=MyWorld\n")  # Correct line
        f.write("another-property=another-value\n")

    world_name = get_world_name(server_name, str(base_dir))
    assert world_name == "MyWorld"


def test_get_world_name_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(MissingArgumentError, match="server_name is empty"):
        get_world_name("", "base_dir")


def test_get_world_name_properties_file_not_found(tmp_path):
    """Test when server.properties is not found."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    # Don't create the server directory or properties file

    with pytest.raises(FileOperationError, match="server.properties not found"):
        get_world_name(server_name, str(base_dir))


def test_get_world_name_world_name_not_found(tmp_path):
    """Test when level-name is not found in server.properties."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    properties_file = server_dir / "server.properties"
    # Create a properties file *without* level-name
    with open(properties_file, "w") as f:
        f.write("some-property=some-value\n")

    with pytest.raises(FileOperationError, match="Failed to extract world name"):
        get_world_name(server_name, str(base_dir))


def test_get_world_name_file_not_found(tmp_path):
    """Test when server.properties is not found."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    (base_dir / server_name).mkdir(parents=True)  # Create the server directory

    # We expect the FileOperationError raised when the file is not found
    with pytest.raises(
        FileOperationError, match=f"server.properties not found for {server_name}"
    ):
        get_world_name(server_name, str(base_dir))


@patch("builtins.open", side_effect=OSError("Mocked read error"))
def test_get_world_name_file_read_error(mock_open, tmp_path):  # Add mock_open argument
    """Test handling a file read error (when the file *exists*)."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    properties_file = server_dir / "server.properties"
    properties_file.touch()  # Create an EMPTY file.

    with pytest.raises(
        FileOperationError, match=f"Failed to read server.properties: Mocked read error"
    ):
        get_world_name(server_name, str(base_dir))


# --- Tests for validate_server ---


def test_validate_server_exists_windows(tmp_path):
    """Test server validation on Windows (bedrock_server.exe)."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    exe_path = server_dir / "bedrock_server.exe"
    exe_path.touch()  # Create the dummy executable

    with patch("platform.system", return_value="Windows"):
        assert validate_server(server_name, str(base_dir)) is True


def test_validate_server_exists_linux(tmp_path):
    """Test server validation on Linux (bedrock_server)."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    exe_path = server_dir / "bedrock_server"
    exe_path.touch()

    with patch("platform.system", return_value="Linux"):
        assert validate_server(server_name, str(base_dir)) is True


def test_validate_server_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(MissingArgumentError, match="server_name is empty"):
        validate_server("", "base_dir")


def test_validate_server_server_not_found(tmp_path):
    """Test when the server executable is not found."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    # Don't create the server directory or executable

    with pytest.raises(ServerNotFoundError):
        validate_server(server_name, str(base_dir))


# --- Tests for manage_server_config ---
@pytest.fixture
def mock_config_dir_manage(tmp_path):
    """Fixture to provide a mocked settings object."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yield str(config_dir)


def test_manage_server_config_read_existing_key(mock_config_dir_manage):
    """Test reading an existing key from the config."""
    server_name = "test_server"
    config_dir = mock_config_dir_manage
    server_config_dir = os.path.join(config_dir, server_name)
    os.makedirs(server_config_dir)
    config_file = os.path.join(server_config_dir, f"{server_name}_config.json")

    initial_data = {"key1": "value1", "key2": 123}
    with open(config_file, "w") as f:
        json.dump(initial_data, f)

    value = manage_server_config(server_name, "key1", "read", config_dir=config_dir)
    assert value == "value1"

    value = manage_server_config(server_name, "key2", "read", config_dir=config_dir)
    assert value == 123


def test_manage_server_config_read_nonexistent_key(mock_config_dir_manage):
    """Test reading a key that doesn't exist (should return None)."""
    server_name = "test_server"
    config_dir = mock_config_dir_manage
    server_config_dir = os.path.join(config_dir, server_name)
    os.makedirs(server_config_dir)
    config_file = os.path.join(server_config_dir, f"{server_name}_config.json")
    with open(config_file, "w") as f:
        json.dump({"existing_key": "value"}, f)

    value = manage_server_config(
        server_name, "nonexistent_key", "read", config_dir=config_dir
    )
    assert value is None


def test_manage_server_config_write_new_key(mock_config_dir_manage):
    """Test writing a new key/value pair to the config."""
    server_name = "test_server"
    config_dir = mock_config_dir_manage
    server_config_dir = os.path.join(config_dir, server_name)
    os.makedirs(server_config_dir)
    config_file = os.path.join(server_config_dir, f"{server_name}_config.json")
    with open(config_file, "w") as f:
        json.dump({}, f)

    manage_server_config(
        server_name, "new_key", "write", "new_value", config_dir=config_dir
    )

    with open(config_file, "r") as f:
        data = json.load(f)
    assert data["new_key"] == "new_value"


def test_manage_server_config_write_existing_key(mock_config_dir_manage):
    """Test writing (overwriting) an existing key."""
    server_name = "test_server"
    config_dir = mock_config_dir_manage
    server_config_dir = os.path.join(config_dir, server_name)
    os.makedirs(server_config_dir)
    config_file = os.path.join(server_config_dir, f"{server_name}_config.json")
    with open(config_file, "w") as f:
        json.dump({"existing_key": "old_value"}, f)

    manage_server_config(
        server_name, "existing_key", "write", "new_value", config_dir=config_dir
    )

    with open(config_file, "r") as f:
        data = json.load(f)
    assert data["existing_key"] == "new_value"


def test_manage_server_config_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        manage_server_config("", "key", "read")


def test_manage_server_config_missing_key():
    """Test with a missing key argument."""
    with pytest.raises(MissingArgumentError, match="key or operation is empty"):
        manage_server_config("server_name", "", "read")


def test_manage_server_config_missing_operation():
    """Test with a missing operation argument."""
    with pytest.raises(MissingArgumentError, match="key or operation is empty"):
        manage_server_config("server_name", "key", "")


def test_manage_server_config_invalid_operation():
    """Test with an invalid operation argument."""
    with pytest.raises(InvalidInputError, match="Invalid operation"):
        manage_server_config("server_name", "key", "invalid_op")


def test_manage_server_config_write_missing_value(mock_config_dir_manage):
    """Test 'write' operation with a missing value argument."""
    server_name = "test_server"
    config_dir = mock_config_dir_manage
    with pytest.raises(
        MissingArgumentError, match="Value is required for 'write' operation"
    ):
        manage_server_config(
            server_name, "key", "write", config_dir=config_dir
        )  # No value


@patch("os.makedirs")
def test_manage_server_config_file_read_error(mock_makedirs, mock_config_dir_manage):
    """Test handling a file read error."""
    server_name = "test_server"
    config_dir = mock_config_dir_manage
    server_config_dir = os.path.join(config_dir, server_name)
    config_file = os.path.join(server_config_dir, f"{server_name}_config.json")

    mock_makedirs.return_value = None

    with patch("builtins.open", mock_open()) as mocked_open:
        mocked_open.side_effect = [
            mock_open(read_data="{}").return_value,
            OSError("Mocked read error"),
        ]  # first open it, then error
        with pytest.raises(
            FileOperationError,
            match="Failed to read/parse config file: Mocked read error",
        ):
            manage_server_config(server_name, "key", "read", config_dir=config_dir)


def test_manage_server_config_file_write_error(tmp_path):
    """Test handling a file write error after successful file creation."""
    server_name = "test_server"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    server_config_dir = config_dir / server_name
    server_config_dir.mkdir()
    config_file = server_config_dir / f"{server_name}_config.json"
    # Create a valid file beforehand.
    config_file.write_text("{}")

    # Create a mock file that simulates a successful open (or read) but fails on write.
    mock_file = mock_open(read_data="{}")
    mock_file.return_value.write.side_effect = OSError("Mocked write error")

    with patch("builtins.open", mock_file):
        with pytest.raises(
            FileOperationError,
            match="Failed to write to config file: Mocked write error",
        ):
            manage_server_config(
                server_name, "key", "write", "value", config_dir=str(config_dir)
            )


def test_manage_server_config_creates_config_file(mock_config_dir_manage):
    """Test that the config file is created if it doesn't exist."""
    server_name = "test_server"
    config_dir = mock_config_dir_manage
    server_config_dir = os.path.join(config_dir, server_name)
    config_file = os.path.join(server_config_dir, f"{server_name}_config.json")

    # Ensure the file doesn't exist initially
    assert not os.path.exists(config_file)

    # Perform a read operation (which should trigger file creation)
    manage_server_config(server_name, "some_key", "read", config_dir=config_dir)

    assert os.path.exists(config_file)
    with open(config_file, "r") as f:
        data = json.load(f)
    assert data == {}  # Should be an empty JSON object


def test_manage_server_config_invalid_json(mock_config_dir_manage):
    """Test handling invalid JSON in the config file."""
    server_name = "test_server"
    config_dir = mock_config_dir_manage
    server_config_dir = os.path.join(config_dir, server_name)
    os.makedirs(server_config_dir)
    config_file = os.path.join(server_config_dir, f"{server_name}_config.json")

    with open(config_file, "w") as f:
        f.write("This is not valid JSON")

    with pytest.raises(FileOperationError, match="Failed to read/parse config file"):
        manage_server_config(server_name, "key", "read", config_dir=config_dir)


# --- Tests for get_installed_version ---


@patch(
    "bedrock_server_manager.core.server.server.manage_server_config",
    return_value="1.20.1.2",
)
def test_get_installed_version_successful(mock_manage_config, mock_config_dir_manage):
    """Test successful retrieval of the installed version."""
    server_name = "test_server"
    config_dir = mock_config_dir_manage

    version = get_installed_version(server_name, config_dir)
    assert version == "1.20.1.2"
    mock_manage_config.assert_called_once_with(
        server_name, "installed_version", "read", config_dir=config_dir
    )


@patch(
    "bedrock_server_manager.core.server.server.manage_server_config", return_value=None
)
def test_get_installed_version_not_found(mock_manage_config, mock_config_dir_manage):
    """Test when the installed_version is not found in the config."""
    server_name = "test_server"
    config_dir = mock_config_dir_manage
    version = get_installed_version(server_name, config_dir)
    assert version == "UNKNOWN"
    mock_manage_config.assert_called_once_with(
        server_name, "installed_version", "read", config_dir=config_dir
    )


def test_get_installed_version_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(MissingArgumentError, match="No server name provided"):
        get_installed_version("")


# --- Tests for check_server_status ---


def test_check_server_status_running(tmp_path):
    """Test when the log file indicates the server is running."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    log_file = server_dir / "server_output.txt"
    # Create a dummy log file with the "Server started." message
    with open(log_file, "w") as f:
        f.write("Some log line...\n")
        f.write("Server started.\n")

    status = check_server_status(server_name, str(base_dir))
    assert status == "RUNNING"


def test_check_server_status_starting(tmp_path):
    """Test when the log indicates server is starting."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    log_file = server_dir / "server_output.txt"
    with open(log_file, "w") as f:
        f.write("Starting Server\n")

    status = check_server_status(server_name, str(base_dir))
    assert status == "STARTING"


def test_check_server_status_restarting(tmp_path):
    """Test when the log indicates server is restarting."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    log_file = server_dir / "server_output.txt"
    with open(log_file, "w") as f:
        f.write("Restarting server in 10 seconds\n")

    status = check_server_status(server_name, str(base_dir))
    assert status == "RESTARTING"


def test_check_server_status_stopping(tmp_path):
    """Test when the log indicates server is stopping."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    log_file = server_dir / "server_output.txt"
    with open(log_file, "w") as f:
        f.write("Shutting down server in 10 seconds\n")

    status = check_server_status(server_name, str(base_dir))
    assert status == "STOPPING"


def test_check_server_status_stopped(tmp_path):
    """Test when the log indicates server is stopped."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    log_file = server_dir / "server_output.txt"
    with open(log_file, "w") as f:
        f.write("Quit correctly\n")

    status = check_server_status(server_name, str(base_dir))
    assert status == "STOPPED"


def test_check_server_status_unknown(tmp_path):
    """Test when the log file doesn't contain any status indicators."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    log_file = server_dir / "server_output.txt"
    # Create an empty log file (or one with no relevant messages)
    log_file.touch()

    status = check_server_status(server_name, str(base_dir))
    assert status == "UNKNOWN"


def test_check_server_status_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(MissingArgumentError, match="server_name is empty"):
        check_server_status("", "base_dir")


def test_check_server_status_log_file_not_found(tmp_path):
    """Test when the log file doesn't exist (after max_attempts)."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    # Don't create the log file

    status = check_server_status(
        server_name, str(base_dir), max_attempts=0
    )  # Set max_attempts to 0 for immediate failure
    assert status == "UNKNOWN"


def test_check_server_status_file_read_error(tmp_path):
    """Test handling a file read error."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    # Create log to simulate error
    log_file = server_dir / "server_output.txt"
    log_file.touch()
    with patch("builtins.open", side_effect=OSError("Mocked read error")):
        with pytest.raises(FileOperationError, match="Failed to read server log"):
            check_server_status(server_name, str(base_dir))


# --- Tests for get_server_status_from_config ---
@pytest.fixture
def mock_config_dir_status(tmp_path):
    """Fixture to provide a mocked settings object."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yield str(config_dir)


@patch(
    "bedrock_server_manager.core.server.server.manage_server_config",
    return_value="RUNNING",
)
def test_get_server_status_from_config_successful(
    mock_manage_config, mock_config_dir_status
):
    """Test successful retrieval of the server status."""
    server_name = "test_server"
    config_dir = mock_config_dir_status
    status = get_server_status_from_config(server_name, config_dir)
    assert status == "RUNNING"
    mock_manage_config.assert_called_once_with(
        server_name, "status", "read", config_dir=config_dir
    )


@patch(
    "bedrock_server_manager.core.server.server.manage_server_config", return_value=None
)
def test_get_server_status_from_config_not_found(
    mock_manage_config, mock_config_dir_status
):
    """Test when the status is not found in the config (returns "UNKNOWN")."""
    server_name = "test_server"
    config_dir = mock_config_dir_status
    status = get_server_status_from_config(server_name, config_dir)
    assert status == "UNKNOWN"
    mock_manage_config.assert_called_once_with(
        server_name, "status", "read", config_dir=config_dir
    )


def test_get_server_status_from_config_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(MissingArgumentError, match="server_name is empty"):
        get_server_status_from_config("")


# --- Tests for update_server_status_in_config ---
@pytest.fixture
def mock_config_dir_update(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yield str(config_dir)


@patch("bedrock_server_manager.core.server.server.manage_server_config")
@patch(
    "bedrock_server_manager.core.server.server.check_server_status",
    return_value="RUNNING",
)
@patch(
    "bedrock_server_manager.core.server.server.get_server_status_from_config",
    return_value="STARTING",
)
def test_update_server_status_in_config_successful(
    mock_get_status,
    mock_check_status,
    mock_manage_config,
    tmp_path,
    mock_config_dir_update,
):
    """Test successful update of the server status."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    config_dir = mock_config_dir_update
    update_server_status_in_config(server_name, str(base_dir), config_dir)

    mock_get_status.assert_called_once_with(server_name, config_dir)
    mock_check_status.assert_called_once_with(server_name, str(base_dir))
    mock_manage_config.assert_called_once_with(
        server_name, "status", "write", "RUNNING", config_dir=config_dir
    )


@patch("bedrock_server_manager.core.server.server.manage_server_config")
@patch(
    "bedrock_server_manager.core.server.server.check_server_status",
    return_value="UNKNOWN",
)
@patch(
    "bedrock_server_manager.core.server.server.get_server_status_from_config",
    return_value="installed",
)
def test_update_server_status_in_config_no_update_needed(
    mock_get_status,
    mock_check_status,
    mock_manage_config,
    tmp_path,
    mock_config_dir_update,
):
    """Test when no update is needed (status is 'installed' and check_status is 'UNKNOWN')."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    config_dir = mock_config_dir_update
    update_server_status_in_config(server_name, str(base_dir), config_dir)

    mock_get_status.assert_called_once_with(server_name, config_dir)
    mock_check_status.assert_called_once_with(server_name, str(base_dir))
    mock_manage_config.assert_not_called()  # Should not be called


def test_update_server_status_in_config_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        update_server_status_in_config("", "base_dir")


# --- Tests for configure_allowlist ---


def test_configure_allowlist_loads_existing_data(tmp_path):
    """Test loading existing player data from allowlist.json."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    allowlist_file = server_dir / "allowlist.json"
    existing_data = [
        {"name": "Player1", "ignoresPlayerLimit": False},
        {"name": "Player2", "ignoresPlayerLimit": True},
    ]
    with open(allowlist_file, "w") as f:
        json.dump(existing_data, f)

    loaded_data = configure_allowlist(str(server_dir))
    assert loaded_data == existing_data


def test_configure_allowlist_file_not_found(tmp_path):
    """Test when allowlist.json doesn't exist (should return an empty list)."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    # Don't create allowlist.json

    loaded_data = configure_allowlist(str(server_dir))
    assert loaded_data == []  # Should return an empty list


def test_configure_allowlist_missing_server_dir():
    """Test with a missing server_dir argument."""
    with pytest.raises(MissingArgumentError, match="server_dir is empty"):
        configure_allowlist("")


def test_configure_allowlist_file_read_error(tmp_path):
    """Test handling a file read error."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()  # Create the server directory
    allowlist_file = server_dir / "allowlist.json"
    allowlist_file.touch()  # Create file

    with patch("builtins.open", side_effect=OSError("Mocked read error")):
        with pytest.raises(
            FileOperationError,
            match="Failed to read existing allowlist.json: Mocked read error",
        ):
            configure_allowlist(str(server_dir))


def test_configure_allowlist_invalid_json(tmp_path):
    """Test handling invalid JSON in allowlist.json."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    allowlist_file = server_dir / "allowlist.json"
    with open(allowlist_file, "w") as f:
        f.write("This is not valid JSON")

    with pytest.raises(
        FileOperationError, match="Failed to read existing allowlist.json"
    ):
        configure_allowlist(str(server_dir))


# --- Tests for add_players_to_allowlist ---


def test_add_players_to_allowlist_adds_new_players(tmp_path):
    """Test adding new players to an empty allowlist."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    allowlist_file = server_dir / "allowlist.json"
    new_players = [
        {"name": "Player1", "ignoresPlayerLimit": False},
        {"name": "Player2", "ignoresPlayerLimit": True},
    ]

    add_players_to_allowlist(str(server_dir), new_players)

    with open(allowlist_file, "r") as f:
        data = json.load(f)
    assert data == new_players


def test_add_players_to_allowlist_updates_existing_players(tmp_path):
    """Test adding and updating players in an existing allowlist."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    allowlist_file = server_dir / "allowlist.json"
    initial_data = [
        {"name": "Player1", "ignoresPlayerLimit": False},
    ]
    with open(allowlist_file, "w") as f:
        json.dump(initial_data, f)

    new_players = [
        {"name": "Player2", "ignoresPlayerLimit": True},
        {"name": "Player1", "ignoresPlayerLimit": True},  # Duplicate name
    ]

    add_players_to_allowlist(str(server_dir), new_players)

    with open(allowlist_file, "r") as f:
        data = json.load(f)
    expected_data = [
        {"name": "Player1", "ignoresPlayerLimit": False},  # no change.
        {"name": "Player2", "ignoresPlayerLimit": True},
    ]
    assert data == expected_data


def test_add_players_to_allowlist_no_duplicates(tmp_path):
    """Test adding a player that already exists (should not add a duplicate)."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    allowlist_file = server_dir / "allowlist.json"
    initial_data = [
        {"name": "Player1", "ignoresPlayerLimit": False},
    ]
    with open(allowlist_file, "w") as f:
        json.dump(initial_data, f)

    new_players = [
        {"name": "Player1", "ignoresPlayerLimit": True},  # Duplicate
    ]

    add_players_to_allowlist(str(server_dir), new_players)

    with open(allowlist_file, "r") as f:
        data = json.load(f)
    # The original entry should *not* be modified or duplicated
    assert data == initial_data


def test_add_players_to_allowlist_missing_server_dir():
    """Test with a missing server_dir argument."""
    with pytest.raises(MissingArgumentError, match="server_dir is empty"):
        add_players_to_allowlist("", [{"name": "Player1", "ignoresPlayerLimit": False}])


def test_add_players_to_allowlist_invalid_new_players_type(tmp_path):
    """Test with incorrect data type"""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    with pytest.raises(TypeError, match="new_players must be a list"):
        add_players_to_allowlist(str(server_dir), "invalid")


def test_add_players_to_allowlist_file_write_error(tmp_path):
    """Test handling a file write error."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    new_players = [{"name": "Player1", "ignoresPlayerLimit": False}]

    with patch("builtins.open", side_effect=OSError("Mocked write error")):
        with pytest.raises(
            FileOperationError, match="Failed to save updated allowlist.json"
        ):
            add_players_to_allowlist(str(server_dir), new_players)


def test_add_players_to_allowlist_file_read_error(tmp_path):
    """Test handling a file read error."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    allowlist_file = server_dir / "allowlist.json"
    allowlist_file.touch()  # Create the file to trigger the read attempt
    new_players = [{"name": "Player1", "ignoresPlayerLimit": False}]

    with patch("builtins.open", side_effect=OSError("Mocked read error")):
        with pytest.raises(
            FileOperationError, match="Failed to read existing allowlist.json"
        ):
            add_players_to_allowlist(str(server_dir), new_players)


def test_add_players_to_allowlist_invalid_json(tmp_path):
    """Test handling invalid JSON in the existing file."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    allowlist_file = server_dir / "allowlist.json"
    with open(allowlist_file, "w") as f:
        f.write("This is not valid JSON")

    new_players = [{"name": "Player1", "ignoresPlayerLimit": False}]

    with pytest.raises(
        FileOperationError, match="Failed to read existing allowlist.json"
    ):
        add_players_to_allowlist(str(server_dir), new_players)


# --- Tests for configure_permissions ---


def test_configure_permissions_adds_new_player(tmp_path):
    """Test adding a new player to permissions.json."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    permissions_file = server_dir / "permissions.json"
    xuid = "12345"
    player_name = "TestPlayer"
    permission = "operator"

    configure_permissions(str(server_dir), xuid, player_name, permission)

    with open(permissions_file, "r") as f:
        data = json.load(f)
    expected_data = [{"permission": "operator", "xuid": "12345", "name": "TestPlayer"}]
    assert data == expected_data


def test_configure_permissions_updates_existing_player(tmp_path):
    """Test updating an existing player's permission."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    permissions_file = server_dir / "permissions.json"
    initial_data = [{"permission": "member", "xuid": "12345", "name": "TestPlayer"}]
    with open(permissions_file, "w") as f:
        json.dump(initial_data, f)

    xuid = "12345"
    player_name = "TestPlayer"
    new_permission = "operator"

    configure_permissions(str(server_dir), xuid, player_name, new_permission)

    with open(permissions_file, "r") as f:
        data = json.load(f)
    expected_data = [
        {"permission": "operator", "xuid": "12345", "name": "TestPlayer"}
    ]  # Updated permission
    assert data == expected_data


def test_configure_permissions_existing_player_same_permission(tmp_path):
    """Test when a player already exists with the *same* permission (no change)."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    permissions_file = server_dir / "permissions.json"
    initial_data = [{"permission": "operator", "xuid": "12345", "name": "TestPlayer"}]
    with open(permissions_file, "w") as f:
        json.dump(initial_data, f)

    xuid = "12345"
    player_name = "TestPlayer"
    permission = "operator"

    configure_permissions(str(server_dir), xuid, player_name, permission)

    with open(permissions_file, "r") as f:
        data = json.load(f)
    # Should remain unchanged
    assert data == initial_data


def test_configure_permission_adds_multiple_players(tmp_path):
    """Test adding multiple players."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    permissions_file = server_dir / "permissions.json"

    configure_permissions(str(server_dir), "123", "Player1", "operator")
    configure_permissions(str(server_dir), "456", "Player2", "member")
    configure_permissions(str(server_dir), "789", "Player3", "visitor")

    with open(permissions_file, "r") as f:
        data = json.load(f)

    expected_data = [
        {"permission": "operator", "xuid": "123", "name": "Player1"},
        {"permission": "member", "xuid": "456", "name": "Player2"},
        {"permission": "visitor", "xuid": "789", "name": "Player3"},
    ]
    assert data == expected_data


def test_configure_permissions_missing_server_dir():
    """Test with a missing server_dir argument."""
    with pytest.raises(InvalidServerNameError, match="server_dir is empty"):
        configure_permissions("", "12345", "player_name", "operator")


def test_configure_permissions_missing_xuid():
    """Test with a missing xuid argument."""
    with pytest.raises(MissingArgumentError, match="xuid is empty"):
        configure_permissions("server_dir", "", "player_name", "operator")


def test_configure_permissions_missing_permission():
    """Test with a missing permission argument."""
    with pytest.raises(MissingArgumentError, match="permission is empty"):
        configure_permissions("server_dir", "12345", "player_name", "")


def test_configure_permissions_invalid_permission(tmp_path):
    """Test with an invalid permission level."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()  # make directory
    with pytest.raises(InvalidInputError, match="invalid permission level"):
        configure_permissions(str(server_dir), "12345", "player_name", "invalid")


def test_configure_permissions_server_dir_not_found(tmp_path):
    """Test with a server_dir that doesn't exist."""
    server_dir = tmp_path / "nonexistent_server"  # Doesn't exist
    with pytest.raises(DirectoryError, match="Server directory not found"):
        configure_permissions(str(server_dir), "12345", "player_name", "operator")


def test_configure_permissions_file_write_error(tmp_path):
    """Test handling a file write error."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()

    with patch("builtins.open", side_effect=OSError("Mocked write error")):
        with pytest.raises(
            FileOperationError,
            match="Failed to initialize permissions.json: Mocked write error",
        ):
            configure_permissions(str(server_dir), "12345", "player_name", "operator")


def test_configure_permissions_file_read_error(tmp_path):
    """Test handling a file read/parse error."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    permissions_file = server_dir / "permissions.json"
    permissions_file.touch()  # Create file to trigger read
    with patch("builtins.open", side_effect=OSError("Mocked read error")):
        with pytest.raises(
            FileOperationError, match="Failed to read or parse permissions.json"
        ):
            configure_permissions(str(server_dir), "12345", "player_name", "operator")


def test_configure_permissions_invalid_json(tmp_path):
    """Test handling invalid JSON in the existing file."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    permissions_file = server_dir / "permissions.json"
    with open(permissions_file, "w") as f:
        f.write("This is not valid JSON")

    with pytest.raises(
        FileOperationError, match="Failed to read or parse permissions.json"
    ):
        configure_permissions(str(server_dir), "12345", "TestPlayer", "operator")


def test_configure_permissions_creates_permissions_file(tmp_path):
    """Test if the permission file gets created if it does not exist"""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    permissions_file = server_dir / "permissions.json"
    xuid = "12345"
    player_name = "TestPlayer"
    permission = "operator"

    configure_permissions(str(server_dir), xuid, player_name, permission)

    assert os.path.exists(permissions_file)


# --- Tests for modify_server_properties ---


def test_modify_server_properties_updates_existing_property(tmp_path):
    """Test updating an existing property."""
    server_properties = tmp_path / "server.properties"
    initial_content = "property1=value1\nproperty2=value2\n"
    with open(server_properties, "w") as f:
        f.write(initial_content)

    modify_server_properties(str(server_properties), "property1", "new_value")

    with open(server_properties, "r") as f:
        updated_content = f.read()
    expected_content = "property1=new_value\nproperty2=value2\n"
    assert updated_content == expected_content


def test_modify_server_properties_adds_new_property(tmp_path):
    """Test adding a new property."""
    server_properties = tmp_path / "server.properties"
    initial_content = "property1=value1\n"
    with open(server_properties, "w") as f:
        f.write(initial_content)

    modify_server_properties(str(server_properties), "new_property", "new_value")

    with open(server_properties, "r") as f:
        updated_content = f.read()
    expected_content = "property1=value1\nnew_property=new_value\n"
    assert updated_content == expected_content


def test_modify_server_properties_missing_server_properties():
    """Test with a missing server_properties argument."""
    with pytest.raises(
        MissingArgumentError, match="server_properties file path is empty"
    ):
        modify_server_properties("", "property", "value")


def test_modify_server_properties_file_not_found(tmp_path):
    """Test with a server_properties file that doesn't exist."""
    server_properties = tmp_path / "nonexistent.properties"  # Doesn't exist

    with pytest.raises(
        FileOperationError, match="server_properties file does not exist"
    ):
        modify_server_properties(str(server_properties), "property", "value")


def test_modify_server_properties_missing_property_name(tmp_path):
    """Test with a missing property_name argument."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()  # Create the server directory
    properties_file = server_dir / "server.properties"
    properties_file.touch()  # Create file
    with pytest.raises(MissingArgumentError, match="property_name is empty"):
        modify_server_properties(properties_file, "", "value")


def test_modify_server_properties_invalid_property_value(tmp_path):
    """Test with an invalid property_value (containing control characters)."""
    server_properties = tmp_path / "server.properties"
    server_properties.touch()  # Create the file

    with pytest.raises(
        InvalidInputError, match="property_value contains control characters"
    ):
        modify_server_properties(
            str(server_properties), "property", "value\nwith\x07control\x1fchars"
        )  # \n should be allowed


def test_modify_server_properties_file_write_error(tmp_path):
    """Test handling a file write error."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()  # Create the server directory
    properties_file = server_dir / "server.properties"
    properties_file.touch()  # Create file
    with patch("builtins.open", side_effect=OSError("Mocked write error")):
        with pytest.raises(
            FileOperationError,
            match="Failed to modify property 'property': Mocked write error",
        ):
            modify_server_properties(properties_file, "property", "value")


# --- Tests for _write_version_config ---
@pytest.fixture
def mock_config_dir_version(tmp_path):
    """Fixture to provide a mocked settings object."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yield str(config_dir)


@patch("bedrock_server_manager.core.server.server.manage_server_config")
def test_write_version_config_successful(mock_manage_config, mock_config_dir_version):
    """Test successful writing of the version to the config."""
    server_name = "test_server"
    installed_version = "1.20.1.2"
    config_dir = mock_config_dir_version

    _write_version_config(server_name, installed_version, config_dir)

    mock_manage_config.assert_called_once_with(
        server_name, "installed_version", "write", "1.20.1.2", config_dir=config_dir
    )


def test_write_version_config_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        _write_version_config("", "1.20.1.2")


@patch("bedrock_server_manager.core.server.server.manage_server_config")
def test_write_version_config_empty_version(
    mock_manage_config, mock_config_dir_version
):
    """Test with empty version"""
    server_name = "test_server"
    installed_version = ""  # empty version
    config_dir = mock_config_dir_version

    _write_version_config(server_name, installed_version, config_dir)

    mock_manage_config.assert_called_once_with(
        server_name, "installed_version", "write", "", config_dir=config_dir
    )


# --- Tests for install_server ---


@patch("bedrock_server_manager.core.server.server.start_server_if_was_running")
@patch("bedrock_server_manager.core.server.server._write_version_config")
@patch("bedrock_server_manager.core.system.base.set_server_folder_permissions")
@patch("bedrock_server_manager.core.server.backup.restore_all")
@patch("bedrock_server_manager.core.server.backup.backup_all")
@patch(
    "bedrock_server_manager.core.server.server.stop_server_if_running",
    return_value=False,
)
@patch("bedrock_server_manager.core.download.downloader.extract_server_files_from_zip")
@patch("bedrock_server_manager.core.download.downloader.prune_old_downloads")
def test_install_server_successful_install(
    mock_prune,
    mock_extract,
    mock_stop,
    mock_backup,
    mock_restore,
    mock_permissions,
    mock_write_version,
    mock_start,
    tmp_path,
):
    """Test a successful server installation (not an update)."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    current_version = "1.20.1.2"
    zip_file = str(tmp_path / "bedrock-server-1.20.1.2.zip")  # Convert to string
    server_dir = str(tmp_path / "servers" / server_name)  # Convert to string
    in_update = False
    install_server(
        server_name, str(base_dir), current_version, zip_file, server_dir, in_update
    )  # All to string

    mock_prune.assert_called_once_with(
        os.path.dirname(zip_file), settings.get("DOWNLOAD_KEEP")
    )
    mock_stop.assert_not_called()  # Should not be called during install
    mock_backup.assert_not_called()
    mock_extract.assert_called_once_with(zip_file, server_dir, in_update)
    mock_restore.assert_not_called()  # restore is only for updates
    mock_permissions.assert_called_once_with(server_dir)
    mock_write_version.assert_called_once_with(server_name, current_version)
    mock_start.assert_not_called()


@patch("bedrock_server_manager.core.server.server.start_server_if_was_running")
@patch("bedrock_server_manager.core.server.server._write_version_config")
@patch("bedrock_server_manager.core.system.base.set_server_folder_permissions")
@patch("bedrock_server_manager.core.server.backup.restore_all")
@patch("bedrock_server_manager.core.server.backup.backup_all")
@patch(
    "bedrock_server_manager.core.server.server.stop_server_if_running",
    return_value=True,
)
@patch("bedrock_server_manager.core.download.downloader.extract_server_files_from_zip")
@patch("bedrock_server_manager.core.download.downloader.prune_old_downloads")
def test_install_server_successful_update(
    mock_prune,
    mock_extract,
    mock_stop,
    mock_backup,
    mock_restore,
    mock_permissions,
    mock_write_version,
    mock_start,
    tmp_path,
):
    """Test a successful server *update*."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    current_version = "1.20.1.2"
    zip_file = str(tmp_path / "bedrock-server-1.20.1.2.zip")  # Convert to string
    server_dir = str(tmp_path / "servers" / server_name)  # Convert to string
    in_update = True

    install_server(
        server_name, str(base_dir), current_version, zip_file, server_dir, in_update
    )
    mock_prune.assert_called_once_with(
        os.path.dirname(zip_file), settings.get("DOWNLOAD_KEEP")
    )
    mock_stop.assert_called_once_with(
        server_name, str(base_dir)
    )  # Should be called during update
    mock_backup.assert_called_once_with(server_name, str(base_dir))  # backup occurs
    mock_extract.assert_called_once_with(zip_file, server_dir, in_update)
    mock_restore.assert_called_once_with(
        server_name, str(base_dir)
    )  # should be called on update
    mock_permissions.assert_called_once_with(server_dir)
    mock_write_version.assert_called_once_with(server_name, current_version)
    mock_start.assert_called_once_with(server_name, str(base_dir), True)  # restart


def test_install_server_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        install_server("", "base_dir", "1.20.1.2", "zip_file.zip", "server_dir", False)


@patch(
    "bedrock_server_manager.core.server.backup.backup_all",
    side_effect=Exception("Mocked backup error"),
)
@patch(
    "bedrock_server_manager.core.server.server.stop_server_if_running",
    return_value=True,
)
@patch("bedrock_server_manager.core.download.downloader.prune_old_downloads")
def test_install_server_backup_error(mock_prune, mock_stop, mock_backup, tmp_path):
    """Test handling an error during the backup process (before update)."""
    server_name = "test_server"
    base_dir = str(tmp_path)
    current_version = "1.20.1.2"
    zip_file = "zip_file.zip"
    server_dir = "server_dir"
    in_update = True  # Important:  Simulate an update

    with pytest.raises(InstallUpdateError, match="Backup failed before update"):
        install_server(
            server_name, base_dir, current_version, zip_file, server_dir, in_update
        )


@patch(
    "bedrock_server_manager.core.download.downloader.extract_server_files_from_zip",
    side_effect=Exception("Mocked extraction error"),
)
@patch("bedrock_server_manager.core.download.downloader.prune_old_downloads")
def test_install_server_extraction_error(mock_prune, mock_extract, tmp_path):
    """Test handling an error during file extraction."""
    server_name = "test_server"
    base_dir = str(tmp_path)
    current_version = "1.20.1.2"
    zip_file = "zip_file.zip"
    server_dir = "server_dir"
    in_update = False

    with pytest.raises(InstallUpdateError, match="Failed to extract server files"):
        install_server(
            server_name, base_dir, current_version, zip_file, server_dir, in_update
        )


@patch(
    "bedrock_server_manager.core.server.backup.restore_all",
    side_effect=Exception("Mocked restore error"),
)
@patch("bedrock_server_manager.core.download.downloader.extract_server_files_from_zip")
@patch("bedrock_server_manager.core.server.backup.backup_all")
@patch(
    "bedrock_server_manager.core.server.server.stop_server_if_running",
    return_value=True,
)
@patch("bedrock_server_manager.core.download.downloader.prune_old_downloads")
def test_install_server_restore_error(
    mock_prune, mock_stop, mock_backup, mock_extract, mock_restore, tmp_path
):
    """Test handling an error during data restoration (after update)."""
    server_name = "test_server"
    base_dir = str(tmp_path)
    current_version = "1.20.1.2"
    zip_file = "zip_file.zip"
    server_dir = "server_dir"
    in_update = True  # Simulate an update

    with pytest.raises(InstallUpdateError, match="Restore failed after update"):
        install_server(
            server_name, base_dir, current_version, zip_file, server_dir, in_update
        )


@patch(
    "bedrock_server_manager.core.server.server._write_version_config",
    side_effect=Exception("Mock write error"),
)
@patch("bedrock_server_manager.core.system.base.set_server_folder_permissions")
@patch("bedrock_server_manager.core.download.downloader.extract_server_files_from_zip")
@patch("bedrock_server_manager.core.download.downloader.prune_old_downloads")
def test_install_server_write_version_config_error(
    mock_prune, mock_extract, mock_permissions, mock_write_version, tmp_path
):
    """Test handling an error when setting folder permissions"""
    server_name = "test_server"
    base_dir = str(tmp_path)
    current_version = "1.20.1.2"
    zip_file = "zip_file.zip"
    server_dir = "server_dir"
    in_update = False  # Simulate an update

    with pytest.raises(
        InstallUpdateError, match="Failed to write version to config.json"
    ):
        install_server(
            server_name, base_dir, current_version, zip_file, server_dir, in_update
        )


# --- Tests for no_update_needed ---


@patch(
    "bedrock_server_manager.core.download.downloader.get_version_from_url",
    return_value="1.20.1.2",
)
@patch(
    "bedrock_server_manager.core.download.downloader.lookup_bedrock_download_url",
    return_value="http://example.com/download",
)
def test_no_update_needed_no_update(
    mock_lookup_url, mock_get_version, mock_config_dir_manage
):
    """Test when no update is needed (installed version == latest version)."""
    server_name = "test_server"
    installed_version = "1.20.1.2"
    target_version = "LATEST"
    config_dir = mock_config_dir_manage
    assert no_update_needed(server_name, installed_version, target_version) is True


@patch(
    "bedrock_server_manager.core.download.downloader.get_version_from_url",
    return_value="1.20.2.0",
)
@patch(
    "bedrock_server_manager.core.download.downloader.lookup_bedrock_download_url",
    return_value="http://example.com/download",
)
def test_no_update_needed_update_available(
    mock_lookup_url, mock_get_version, mock_config_dir_manage
):
    """Test when an update is available (installed version < latest version)."""
    server_name = "test_server"
    installed_version = "1.20.1.2"
    target_version = "LATEST"
    config_dir = mock_config_dir_manage
    assert no_update_needed(server_name, installed_version, target_version) is False


def test_no_update_needed_specific_version(mock_config_dir_manage):
    """Test when a specific version is requested (always update)."""
    server_name = "test_server"
    installed_version = "1.20.1.2"
    target_version = "1.19.80.24"  # Specific version
    config_dir = mock_config_dir_manage

    # Should always return False when a specific version is requested
    assert no_update_needed(server_name, installed_version, target_version) is False


def test_no_update_needed_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        no_update_needed("", "1.20.1.2", "LATEST")


def test_no_update_needed_missing_installed_version(mock_config_dir_manage):
    """Test with a missing installed_version (should assume update is needed)."""
    server_name = "test_server"
    installed_version = ""  # Empty
    target_version = "LATEST"
    config_dir = mock_config_dir_manage

    assert no_update_needed(server_name, installed_version, target_version) is False


@patch(
    "bedrock_server_manager.core.download.downloader.lookup_bedrock_download_url",
    side_effect=Exception("Mocked lookup error"),
)
def test_no_update_needed_lookup_error(mock_lookup_url, mock_config_dir_manage):
    """Test when there's an error looking up the download URL (assume update needed)."""
    server_name = "test_server"
    installed_version = "1.20.1.2"
    target_version = "LATEST"
    config_dir = mock_config_dir_manage
    # Should return False (assume update is needed) if lookup fails
    assert no_update_needed(server_name, installed_version, target_version) is False


# --- Tests for delete_server_data ---
@pytest.fixture
def mock_config_dir_delete(tmp_path):
    """Fixture to provide a mocked settings object."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yield str(config_dir)


@patch("bedrock_server_manager.core.system.linux._disable_systemd_service")
@patch("subprocess.run")
def test_delete_server_data_linux(
    mock_subprocess_run, mock_disable_systemd, tmp_path, mock_config_dir_delete
):
    """Test deleting server data on Linux (including systemd service removal)."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    config_dir = mock_config_dir_delete
    config_folder = os.path.join(config_dir, server_name)
    os.makedirs(config_folder)
    service_file = os.path.join(
        os.path.expanduser("~"),
        ".config",
        "systemd",
        "user",
        f"bedrock-{server_name}.service",
    )
    os.makedirs(
        os.path.dirname(service_file), exist_ok=True
    )  # Create necessary parent dirs
    with open(service_file, "w") as f:  # create service file
        f.write("")

    with patch("platform.system", return_value="Linux"):
        with patch("os.remove") as mock_remove:
            delete_server_data(server_name, str(base_dir), config_dir)

            mock_disable_systemd.assert_called_once_with(server_name)
            mock_remove.assert_called_once_with(service_file)
            mock_subprocess_run.assert_called_once()

    assert not os.path.exists(server_dir)
    assert not os.path.exists(config_folder)


@patch("bedrock_server_manager.core.system.base.remove_readonly")
@patch("shutil.rmtree")  # Mock rmtree to prevent actual deletion
@patch("platform.system", return_value="Windows")
@patch("os.path.exists")  # Mock exists *globally*
def test_delete_server_data_windows(
    mock_exists,
    mock_system,
    mock_rmtree,
    mock_remove_readonly,
    tmp_path,
    mock_config_dir_delete,
):
    """Test deleting server data on Windows without affecting real file system."""

    # Setup: Use `tmp_path` to avoid touching real file system
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)  # Creates the test server directory in tmp_path

    config_dir = mock_config_dir_delete
    config_folder = os.path.join(config_dir, server_name)
    os.makedirs(config_folder)  # Creates the config directory in tmp_path

    # Mock os.path.exists to simulate expected behavior
    mock_exists.side_effect = [
        True,
        True,
        False,
        False,
    ]  # Simulate file existence checks

    # Call the function under test
    delete_server_data(server_name, str(base_dir), config_dir)

    # Verify that `rmtree` was called for the mocked directories
    mock_rmtree.assert_any_call(str(server_dir))
    mock_rmtree.assert_any_call(config_folder)

    # Verify that actual deletion did not happen by checking the mock call count
    assert (
        mock_rmtree.call_count == 2
    ), f"Expected rmtree to be called twice, but was called {mock_rmtree.call_count} times."


def test_delete_server_data_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        delete_server_data("", "base_dir", "config_dir")


def test_delete_server_data_server_does_not_exist(tmp_path, mock_config_dir_delete):
    """Test when the server directory and config directory don't exist."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"  # Don't create the directory
    config_dir = mock_config_dir_delete
    # Should not raise an exception
    delete_server_data(server_name, str(base_dir), config_dir)


@patch("shutil.rmtree", side_effect=OSError("Mocked rmtree error"))
def test_delete_server_data_deletion_error(
    mock_rmtree, tmp_path, mock_config_dir_delete
):
    """Test handling an error during directory deletion."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"
    server_dir = base_dir / server_name
    server_dir.mkdir(parents=True)
    config_dir = mock_config_dir_delete
    config_folder = os.path.join(config_dir, server_name)
    os.makedirs(config_folder)

    with pytest.raises(DirectoryError, match="Failed to delete server directory"):
        delete_server_data(server_name, str(base_dir), config_dir)


# --- Tests for start_server_if_was_running ---


@patch("bedrock_server_manager.core.server.server.BedrockServer")
def test_start_server_if_was_running_was_running(mock_bedrock_server, tmp_path):
    """Test restarting the server when it was previously running."""
    server_name = "test_server"
    base_dir = str(tmp_path)
    was_running = True

    # Mock the BedrockServer instance and its start method
    mock_server_instance = MagicMock(spec=BedrockServer)
    mock_bedrock_server.return_value = mock_server_instance

    start_server_if_was_running(server_name, base_dir, was_running)

    mock_bedrock_server.assert_called_once_with(server_name)
    mock_server_instance.start.assert_called_once()


@patch("bedrock_server_manager.core.server.server.BedrockServer")
def test_start_server_if_was_running_not_running(mock_bedrock_server, tmp_path):
    """Test when the server was *not* previously running (no restart)."""
    server_name = "test_server"
    base_dir = str(tmp_path)
    was_running = False

    start_server_if_was_running(server_name, base_dir, was_running)

    # BedrockServer and start should *not* be called
    mock_bedrock_server.assert_not_called()


# --- Tests for stop_server_if_running ---


@patch("bedrock_server_manager.core.server.server.BedrockServer")
@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=True)
def test_stop_server_if_running_was_running(
    mock_is_running, mock_bedrock_server, tmp_path
):
    """Test stopping the server when it is running."""
    server_name = "test_server"
    base_dir = str(tmp_path)

    # Mock BedrockServer instance and stop method
    mock_server_instance = MagicMock(spec=BedrockServer)
    mock_bedrock_server.return_value = mock_server_instance

    result = stop_server_if_running(server_name, base_dir)

    assert result is True  # Server was running
    mock_bedrock_server.assert_called_once_with(server_name)
    mock_server_instance.stop.assert_called_once()


@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=False)
def test_stop_server_if_running_not_running(mock_is_running, tmp_path):
    """Test when the server is *not* running."""
    server_name = "test_server"
    base_dir = str(tmp_path)

    result = stop_server_if_running(server_name, base_dir)

    assert result is False  # Server was not running
    mock_is_running.assert_called_once_with(server_name, base_dir)


def test_stop_server_if_running_missing_server_name():
    """Test with a missing server_name argument."""
    with pytest.raises(InvalidServerNameError, match="server_name is empty"):
        stop_server_if_running("", "base_dir")


@patch("bedrock_server_manager.core.server.server.BedrockServer")
@patch("bedrock_server_manager.core.system.base.is_server_running", return_value=True)
def test_stop_server_if_running_stop_fails(
    mock_is_running, mock_bedrock_server, tmp_path
):
    """Test that True is returned even if stop_server raises an exception."""
    server_name = "test_server"
    base_dir = str(tmp_path)

    # Mock to raise an exception
    mock_server_instance = MagicMock(spec=BedrockServer)
    mock_server_instance.stop.side_effect = Exception("Mocked stop error")
    mock_bedrock_server.return_value = mock_server_instance

    result = stop_server_if_running(server_name, base_dir)
    assert result is True  # Should still return True, as it *was* running
    mock_is_running.assert_called()
    mock_bedrock_server.assert_called()
    mock_server_instance.stop.assert_called()
