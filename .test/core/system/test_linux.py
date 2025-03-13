# bedrock-server-manager/tests/core/system/test_linux.py
import pytest
import os
import subprocess
from datetime import datetime
from unittest.mock import patch, call, MagicMock, mock_open
from bedrock_server_manager.config import settings
from bedrock_server_manager.core.system import linux
from bedrock_server_manager.core.error import (
    SystemdReloadError,
    CommandNotFoundError,
    ServiceError,
    InvalidServerNameError,
    ServerStartError,
    ServerStopError,
    ScheduleError,
    InvalidCronJobError,
)

# --- Tests for check_service_exists ---


def test_check_service_exists_exists(tmp_path):
    """Test when the service file exists."""
    server_name = "test_server"
    service_file = (
        tmp_path / ".config" / "systemd" / "user" / f"bedrock-{server_name}.service"
    )
    service_file.parent.mkdir(parents=True)  # Create parent directories
    service_file.touch()  # Create the dummy service file

    with patch("platform.system", return_value="Linux"):
        with patch("os.path.expanduser", return_value=str(tmp_path)):
            result = linux.check_service_exists(server_name)
            assert result is True


def test_check_service_exists_not_exists(tmp_path):
    """Test when the service file does *not* exist."""
    server_name = "test_server"
    # Don't create the service file

    with patch("platform.system", return_value="Linux"):
        with patch("os.path.expanduser", return_value=str(tmp_path)):
            result = linux.check_service_exists(server_name)
            assert result is False


def test_check_service_exists_not_linux():
    """Test on a non-Linux system (should return False)."""
    server_name = "test_server"  # Server name doesn't matter in this case
    with patch("platform.system", return_value="Windows"):
        result = linux.check_service_exists(server_name)
        assert result is False


# --- Tests for enable_user_lingering ---


@patch("getpass.getuser", return_value="testuser")
@patch("subprocess.run")
def test_enable_user_lingering_already_enabled(mock_subprocess_run, mock_getuser):
    """Test when lingering is already enabled (should do nothing)."""
    # Mock subprocess.run to return output indicating lingering is enabled
    mock_subprocess_run.return_value.stdout = "Linger=yes"
    with patch("platform.system", return_value="Linux"):
        linux.enable_user_lingering()  # Should return early

    # Verify that loginctl show-user was called, but not enable-linger
    mock_subprocess_run.assert_called_once_with(
        ["loginctl", "show-user", "testuser"],
        capture_output=True,
        text=True,
        check=False,
    )


@patch("getpass.getuser", return_value="testuser")
@patch("subprocess.run")
def test_enable_user_lingering_enable_success(mock_subprocess_run, mock_getuser):
    """Test successful enabling of lingering."""
    # First call to subprocess.run (show-user) returns empty output (not enabled)
    mock_subprocess_run.return_value.stdout = ""
    # Second call (enable-linger) is mocked to succeed.
    with patch("platform.system", return_value="Linux"):
        linux.enable_user_lingering()

    # Check that both calls were made, in order
    expected_calls = [
        call(
            ["loginctl", "show-user", "testuser"],
            capture_output=True,
            text=True,
            check=False,
        ),
        call(
            ["sudo", "loginctl", "enable-linger", "testuser"],
            check=True,
            capture_output=True,
            text=True,
        ),
    ]
    mock_subprocess_run.assert_has_calls(expected_calls)


@patch("getpass.getuser", return_value="testuser")
@patch("subprocess.run")
def test_enable_user_lingering_enable_failure(mock_subprocess_run, mock_getuser):
    """Test failure to enable lingering."""
    # First call (check lingering) returns a successful result with lingering not enabled.
    successful_check = MagicMock()
    successful_check.stdout = (
        "Linger=no"  # This ensures that lingering is not already enabled.
    )

    # Second call (enable lingering) raises a CalledProcessError.
    enable_failure = subprocess.CalledProcessError(
        1, ["sudo", "loginctl", "enable-linger", "testuser"], output="Mocked error"
    )

    # Set side_effect as a list: first call returns successful_check, second call raises enable_failure.
    mock_subprocess_run.side_effect = [successful_check, enable_failure]

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(SystemdReloadError, match="Failed to enable lingering"):
            linux.enable_user_lingering()


@patch("getpass.getuser", return_value="testuser")
@patch("subprocess.run", side_effect=FileNotFoundError)
def test_enable_user_lingering_loginctl_not_found(mock_subprocess_run, mock_getuser):
    """Test when loginctl is not found."""
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(CommandNotFoundError, match="loginctl command not found"):
            linux.enable_user_lingering()


@patch("getpass.getuser", return_value="testuser")
@patch(
    "subprocess.run", side_effect=[FileNotFoundError, MagicMock()]
)  # First call raises, 2nd is mocked
def test_enable_user_lingering_sudo_not_found(mock_subprocess_run, mock_getuser):
    """Test case for sudo command not found"""
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(
            CommandNotFoundError,
            match="loginctl command not found. Lingering cannot be checked/enabled.",
        ):
            linux.enable_user_lingering()


def test_enable_user_lingering_not_linux():
    """Test on a non-Linux system (should do nothing)."""
    with patch("platform.system", return_value="Windows"):
        linux.enable_user_lingering()  # Should return early and not raise anything


# --- Tests for _create_systemd_service ---


@patch("os.makedirs")
@patch("builtins.open", new_callable=mock_open)
@patch("subprocess.run")
def test_create_systemd_service_success(
    mock_subprocess_run, mock_open_file, mock_makedirs, tmp_path
):
    """Test successful creation of a systemd service file."""
    server_name = "test_server"
    base_dir = str(tmp_path / "servers")
    autoupdate = True

    # Mock settings for EXPATH
    mock_settings = MagicMock()
    mock_settings.EXPATH = "/path/to/bedrock-server-manager"
    with patch("bedrock_server_manager.core.system.linux.settings", mock_settings):
        with patch("platform.system", return_value="Linux"):
            with patch("os.path.expanduser", return_value=str(tmp_path)):
                with patch("os.path.exists", return_value=False):
                    linux._create_systemd_service(server_name, base_dir, autoupdate)

    # Check that os.makedirs was called to create the service directory
    mock_makedirs.assert_called_once_with(
        os.path.join(str(tmp_path), ".config", "systemd", "user"), exist_ok=True
    )

    # Check that the service file was opened for writing
    service_file_path = os.path.join(
        str(tmp_path), ".config", "systemd", "user", f"bedrock-{server_name}.service"
    )
    mock_open_file.assert_called_once_with(service_file_path, "w")

    # Get the handle for the opened file (for checking write calls)
    file_handle = mock_open_file()

    # Construct the *expected* service file content
    expected_service_content = f"""[Unit]
Description=Minecraft Bedrock Server: {server_name}
After=network.target

[Service]
Type=forking
WorkingDirectory={os.path.join(base_dir, server_name)}
Environment="PATH=/usr/bin:/bin:/usr/sbin:/sbin"
ExecStartPre=/path/to/bedrock-server-manager update-server --server {server_name}
ExecStart=/path/to/bedrock-server-manager systemd-start --server {server_name}
ExecStop=/path/to/bedrock-server-manager systemd-stop --server {server_name}
ExecReload=/path/to/bedrock-server-manager systemd-stop --server {server_name} && /path/to/bedrock-server-manager systemd-start --server {server_name}
Restart=always
RestartSec=10
StartLimitIntervalSec=500
StartLimitBurst=3

[Install]
WantedBy=default.target
"""
    # Check that write was called with the correct content
    file_handle.write.assert_called_once_with(expected_service_content)

    # Check that systemctl daemon-reload was called
    mock_subprocess_run.assert_called_once_with(
        ["systemctl", "--user", "daemon-reload"], check=True
    )


@patch("os.makedirs")
@patch("builtins.open", new_callable=mock_open)
@patch("subprocess.run")
def test_create_systemd_service_no_autoupdate(
    mock_subprocess_run, mock_open_file, mock_makedirs, tmp_path
):
    """Test creation with autoupdate=False."""
    server_name = "test_server"
    base_dir = str(tmp_path / "servers")
    autoupdate = False  # Disable autoupdate

    # Mock settings for EXPATH
    mock_settings = MagicMock()
    mock_settings.EXPATH = "/path/to/bedrock-server-manager"
    with patch("bedrock_server_manager.core.system.linux.settings", mock_settings):
        with patch("platform.system", return_value="Linux"):
            with patch("os.path.expanduser", return_value=str(tmp_path)):
                with patch("os.path.exists", return_value=False):
                    linux._create_systemd_service(server_name, base_dir, autoupdate)

    # Construct the *expected* service file content (no ExecStartPre)
    expected_service_content = f"""[Unit]
Description=Minecraft Bedrock Server: {server_name}
After=network.target

[Service]
Type=forking
WorkingDirectory={os.path.join(base_dir, server_name)}
Environment="PATH=/usr/bin:/bin:/usr/sbin:/sbin"

ExecStart=/path/to/bedrock-server-manager systemd-start --server {server_name}
ExecStop=/path/to/bedrock-server-manager systemd-stop --server {server_name}
ExecReload=/path/to/bedrock-server-manager systemd-stop --server {server_name} && /path/to/bedrock-server-manager systemd-start --server {server_name}
Restart=always
RestartSec=10
StartLimitIntervalSec=500
StartLimitBurst=3

[Install]
WantedBy=default.target
"""
    # Get the handle for the opened file (for checking write calls)
    file_handle = mock_open_file()
    # Check write call
    file_handle.write.assert_called_once_with(expected_service_content)


def test_create_systemd_service_not_linux():
    """Test on a non-Linux system (should do nothing)."""
    with patch("platform.system", return_value="Windows"):
        linux._create_systemd_service(
            "test_server", "base_dir", True
        )  # Should return early


def test_create_systemd_service_missing_server_name():
    """Test with a missing server_name argument."""
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(InvalidServerNameError, match="server_name is empty"):
            linux._create_systemd_service("", "base_dir", True)


@patch(
    "subprocess.run",
    side_effect=subprocess.CalledProcessError(1, "systemctl", "Mocked error"),
)
@patch("os.makedirs")
@patch("builtins.open", new_callable=mock_open)
def test_create_systemd_service_systemd_reload_failure(
    mock_open_file, mock_makedirs, mock_subprocess_run, tmp_path
):
    """Test handling failure to reload the systemd daemon."""
    server_name = "test_server"
    base_dir = str(tmp_path / "servers")
    autoupdate = True
    # Mock settings for EXPATH
    mock_settings = MagicMock()
    mock_settings.EXPATH = "/path/to/bedrock-server-manager"
    with patch("bedrock_server_manager.core.system.linux.settings", mock_settings):
        with patch("platform.system", return_value="Linux"):
            with patch("os.path.expanduser", return_value=str(tmp_path)):
                with patch("os.path.exists", return_value=False):
                    with pytest.raises(
                        SystemdReloadError, match="Failed to reload systemd daemon"
                    ):
                        linux._create_systemd_service(server_name, base_dir, autoupdate)


@patch("subprocess.run", side_effect=FileNotFoundError)
@patch("os.makedirs")
@patch("builtins.open", new_callable=mock_open)
def test_create_systemd_service_systemctl_not_found(
    mock_open_file, mock_makedirs, mock_subprocess_run, tmp_path
):
    """Test when systemctl is not found."""
    server_name = "test_server"
    base_dir = str(tmp_path / "servers")
    autoupdate = True
    # Mock settings for EXPATH
    mock_settings = MagicMock()
    mock_settings.EXPATH = "/path/to/bedrock-server-manager"
    with patch("bedrock_server_manager.core.system.linux.settings", mock_settings):
        with patch("platform.system", return_value="Linux"):
            with patch("os.path.expanduser", return_value=str(tmp_path)):
                with patch("os.path.exists", return_value=False):
                    with pytest.raises(
                        CommandNotFoundError, match="systemctl command not found"
                    ):
                        linux._create_systemd_service(server_name, base_dir, autoupdate)


@patch("os.makedirs", side_effect=OSError("Mocked makedirs error"))
@patch("builtins.open", new_callable=mock_open)
def test_create_systemd_service_makedirs_error(mock_open_file, mock_makedirs, tmp_path):
    """Test handling failure to create the service directory"""
    server_name = "test_server"
    base_dir = str(tmp_path / "servers")
    autoupdate = True
    # Mock settings for EXPATH
    mock_settings = MagicMock()
    mock_settings.EXPATH = "/path/to/bedrock-server-manager"
    with patch("bedrock_server_manager.core.system.linux.settings", mock_settings):
        with patch("platform.system", return_value="Linux"):
            with patch("os.path.expanduser", return_value=str(tmp_path)):
                with patch("os.path.exists", return_value=False):
                    with pytest.raises(ServiceError):
                        linux._create_systemd_service(server_name, base_dir, autoupdate)


@patch("os.makedirs")
@patch("builtins.open", side_effect=OSError("Mocked open error"))
def test_create_systemd_service_file_write_error(
    mock_open_file, mock_makedirs, tmp_path
):
    """Test handling failure to write service file."""
    server_name = "test_server"
    base_dir = str(tmp_path / "servers")
    autoupdate = True
    # Mock settings for EXPATH
    mock_settings = MagicMock()
    mock_settings.EXPATH = "/path/to/bedrock-server-manager"
    with patch("bedrock_server_manager.core.system.linux.settings", mock_settings):
        with patch("platform.system", return_value="Linux"):
            with patch("os.path.expanduser", return_value=str(tmp_path)):
                with patch("os.path.exists", return_value=False):
                    with pytest.raises(
                        ServiceError, match="Failed to write systemd service file"
                    ):
                        linux._create_systemd_service(server_name, base_dir, autoupdate)


# --- Tests for enable_systemd_service ---


@patch(
    "bedrock_server_manager.core.system.linux.check_service_exists", return_value=True
)
@patch("subprocess.run")
def test_enable_systemd_service_success(mock_subprocess_run, mock_check_exists):
    """Test successful enabling of the systemd service."""
    server_name = "test_server"
    service_name = f"bedrock-{server_name}"

    with patch("platform.system", return_value="Linux"):
        linux._enable_systemd_service(server_name)

    mock_subprocess_run.assert_any_call(
        ["systemctl", "--user", "is-enabled", service_name],
        capture_output=True,
        text=True,
        check=False,
    )
    mock_subprocess_run.assert_called_with(
        ["systemctl", "--user", "enable", service_name], check=True
    )


@patch(
    "bedrock_server_manager.core.system.linux.check_service_exists", return_value=True
)
@patch("subprocess.run")
def test_enable_systemd_service_already_enabled(mock_subprocess_run, mock_check_exists):
    """Test when the service is already enabled (should do nothing)."""
    server_name = "test_server"
    service_name = f"bedrock-{server_name}"
    # Mock subprocess.run to simulate 'is-enabled' returning 0 (enabled)
    mock_subprocess_run.return_value.returncode = 0
    with patch("platform.system", return_value="Linux"):
        linux._enable_systemd_service(server_name)

    # Only the is-enabled check should have been called
    mock_subprocess_run.assert_called_once_with(
        ["systemctl", "--user", "is-enabled", service_name],
        capture_output=True,
        text=True,
        check=False,
    )


def test_enable_systemd_service_not_linux():
    """Test on a non-Linux system (should do nothing)."""
    with patch("platform.system", return_value="Windows"):
        linux._enable_systemd_service("test_server")  # Should not raise anything


def test_enable_systemd_service_missing_server_name():
    """Test with a missing server_name argument."""
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(InvalidServerNameError, match="server_name is empty"):
            linux._enable_systemd_service("")


@patch(
    "bedrock_server_manager.core.system.linux.check_service_exists", return_value=False
)
def test_enable_systemd_service_service_file_missing(mock_check_exists):
    """Test when the service file doesn't exist."""
    server_name = "test_server"
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(ServiceError, match="Service file for .* does not exist"):
            linux._enable_systemd_service(server_name)
    mock_check_exists.assert_called_once_with(server_name)


@patch(
    "bedrock_server_manager.core.system.linux.check_service_exists", return_value=True
)
@patch("subprocess.run")
def test_enable_systemd_service_enable_failure(mock_subprocess_run, mock_check_exists):
    """Test failure to enable the service (systemctl error)."""
    server_name = "test_server"

    # Simulate the is-enabled check returning a CompletedProcess with non-zero exit code.
    completed_process = subprocess.CompletedProcess(
        args=["systemctl", "--user", "is-enabled", f"bedrock-{server_name}"],
        returncode=1,  # non-zero means "disabled"
        stdout="disabled",
        stderr="",
    )

    # Create a CalledProcessError instance for the enable call.
    error = subprocess.CalledProcessError(1, "systemctl", "Mocked error")

    # Set side_effect as a list: first call returns a CompletedProcess, second call raises CalledProcessError.
    mock_subprocess_run.side_effect = [completed_process, error]

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(ServiceError, match="Failed to enable"):
            linux._enable_systemd_service(server_name)


@patch(
    "bedrock_server_manager.core.system.linux.check_service_exists", return_value=True
)
@patch("subprocess.run", side_effect=FileNotFoundError)
def test_enable_systemd_service_systemctl_not_found(
    mock_subprocess_run, mock_check_exists
):
    """Test when systemctl is not found."""
    server_name = "test_server"
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(CommandNotFoundError, match="systemctl command not found"):
            linux._enable_systemd_service(server_name)


# --- Tests for _disable_systemd_service ---


@patch(
    "bedrock_server_manager.core.system.linux.check_service_exists", return_value=True
)
@patch("subprocess.run")
def test_disable_systemd_service_success(mock_subprocess_run, mock_check_exists):
    """Test successful disabling of the systemd service."""
    server_name = "test_server"
    service_name = f"bedrock-{server_name}"
    mock_subprocess_run.return_value.returncode = (
        0  # Mock that the check if already disabled passes
    )
    with patch("platform.system", return_value="Linux"):
        linux._disable_systemd_service(server_name)
    mock_subprocess_run.assert_any_call(
        ["systemctl", "--user", "is-enabled", service_name],
        capture_output=True,
        text=True,
        check=False,
    )
    mock_subprocess_run.assert_called_with(
        ["systemctl", "--user", "disable", service_name], check=True
    )


@patch(
    "bedrock_server_manager.core.system.linux.check_service_exists", return_value=True
)
@patch("subprocess.run")
def test_disable_systemd_service_already_disabled(
    mock_subprocess_run, mock_check_exists
):
    """Test when the service is already disabled (should do nothing)."""
    server_name = "test_server"
    service_name = f"bedrock-{server_name}"

    # Mock subprocess.run to simulate 'is-enabled' returning non-zero (disabled)
    mock_subprocess_run.return_value.returncode = 1

    with patch("platform.system", return_value="Linux"):
        linux._disable_systemd_service(server_name)

    # Only the is-enabled check should have been called
    mock_subprocess_run.assert_called_once_with(
        ["systemctl", "--user", "is-enabled", service_name],
        capture_output=True,
        text=True,
        check=False,
    )


def test_disable_systemd_service_not_linux():
    """Test on a non-Linux system (should do nothing)."""
    with patch("platform.system", return_value="Windows"):
        linux._disable_systemd_service("test_server")  # Should return early


def test_disable_systemd_service_missing_server_name():
    """Test with a missing server_name argument."""
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(InvalidServerNameError, match="server_name is empty"):
            linux._disable_systemd_service("")


@patch(
    "bedrock_server_manager.core.system.linux.check_service_exists", return_value=False
)
def test_disable_systemd_service_service_file_missing(mock_check_exists):
    """Test when the service file doesn't exist."""
    server_name = "test_server"
    with patch("platform.system", return_value="Linux"):
        # Should not raise an exception; it should log and return
        linux._disable_systemd_service(server_name)
    mock_check_exists.assert_called_once_with(server_name)


@patch(
    "bedrock_server_manager.core.system.linux.check_service_exists", return_value=True
)
@patch("subprocess.run")
def test_disable_systemd_service_disable_failure(
    mock_subprocess_run, mock_check_exists
):
    """Test failure to disable the service (systemctl error)."""
    server_name = "test_server"

    # First call: "is-enabled" check should return a CompletedProcess with returncode 0.
    completed_process = subprocess.CompletedProcess(
        args=["systemctl", "--user", "is-enabled", f"bedrock-{server_name}"],
        returncode=0,  # indicates that the service is enabled
        stdout="enabled",
        stderr="",
    )

    # Second call: "disable" command should raise a CalledProcessError.
    error = subprocess.CalledProcessError(1, "systemctl", "Mocked error")

    # Set side_effect: first call returns CompletedProcess, second call raises error.
    mock_subprocess_run.side_effect = [completed_process, error]

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(ServiceError, match="Failed to disable"):
            linux._disable_systemd_service(server_name)


@patch(
    "bedrock_server_manager.core.system.linux.check_service_exists", return_value=True
)
@patch("subprocess.run", side_effect=FileNotFoundError)
def test_disable_systemd_service_systemctl_not_found(
    mock_subprocess_run, mock_check_exists
):
    """Test when systemctl is not found."""
    server_name = "test_server"
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(CommandNotFoundError, match="systemctl command not found"):
            linux._disable_systemd_service(server_name)


# --- Tests for _systemd_start_server ---


@patch("subprocess.run")
def test_systemd_start_server_success(mock_subprocess_run, tmp_path):
    """Test successful server start using screen."""
    server_name = "test_server"
    server_dir = str(tmp_path / "server")
    os.makedirs(server_dir)

    # Mock settings.EXPATH to a known value
    mock_settings = MagicMock()
    mock_settings.EXPATH = "/path/to/bedrock-server-manager"

    with patch("bedrock_server_manager.core.system.linux.settings", mock_settings):
        with patch("builtins.open", mock_open()) as mock_file:  # Mock file operations
            linux._systemd_start_server(server_name, server_dir)

    # Check that subprocess.run was called with the correct screen command
    expected_command = [
        "screen",
        "-dmS",
        f"bedrock-{server_name}",
        "-L",
        "-Logfile",
        os.path.join(server_dir, "server_output.txt"),
        "bash",
        "-c",
        f'cd "{server_dir}" && exec ./bedrock_server',
    ]
    mock_subprocess_run.assert_called_once_with(expected_command, check=True)
    mock_file.assert_called_once_with(
        os.path.join(server_dir, "server_output.txt"), "w"
    )  # Check file operations


@patch(
    "subprocess.run",
    side_effect=subprocess.CalledProcessError(1, "screen", "Mocked screen error"),
)
def test_systemd_start_server_screen_failure(mock_subprocess_run, tmp_path):
    """Test handling failure to start the server with screen."""
    server_name = "test_server"
    server_dir = str(tmp_path / "server")
    os.makedirs(server_dir)
    mock_settings = MagicMock()
    mock_settings.EXPATH = "/path/to/bedrock-server-manager"

    with patch("bedrock_server_manager.core.system.linux.settings", mock_settings):
        with patch("builtins.open", mock_open()) as mock_file:  # Mock file operations
            with pytest.raises(
                ServerStartError, match="Failed to start server with screen"
            ):
                linux._systemd_start_server(server_name, server_dir)
        assert mock_file.call_count == 1  # Should still be opened


@patch("subprocess.run", side_effect=FileNotFoundError)
def test_systemd_start_server_screen_not_found(mock_subprocess_run, tmp_path):
    """Test when the 'screen' command is not found."""
    server_name = "test_server"
    server_dir = str(tmp_path / "server")
    os.makedirs(server_dir)
    mock_settings = MagicMock()
    mock_settings.EXPATH = "/path/to/bedrock-server-manager"
    with patch("bedrock_server_manager.core.system.linux.settings", mock_settings):
        with patch("builtins.open", mock_open()) as mock_file:  # Mock file operations
            with pytest.raises(CommandNotFoundError, match="screen command not found"):
                linux._systemd_start_server(server_name, server_dir)
        assert mock_file.call_count == 1  # Should still be opened


@patch("subprocess.run")
def test_systemd_start_server_truncate_output_file_fails(mock_subprocess_run, tmp_path):
    """Test handling file operation errors (truncating output file)."""
    server_name = "test_server"
    server_dir = str(tmp_path / "server")
    os.makedirs(server_dir)
    mock_settings = MagicMock()
    mock_settings.EXPATH = "/path/to/bedrock-server-manager"
    with patch("bedrock_server_manager.core.system.linux.settings", mock_settings):
        with patch("builtins.open", side_effect=OSError("Mocked file open error")):
            # Should *not* raise an exception; file operations are not critical
            linux._systemd_start_server(server_name, server_dir)
        mock_subprocess_run.assert_called_once()  # Check if screen is still called


# --- Tests for _systemd_stop_server ---


@patch("subprocess.run")
def test_systemd_stop_server_success(mock_subprocess_run, tmp_path):
    """Test successful server stop using screen."""
    server_name = "test_server"
    server_dir = str(tmp_path)  # Doesn't need to exist for this test

    # Mock subprocess.run for the 'pgrep' command to return a PID
    mock_pgrep_result = MagicMock()
    mock_pgrep_result.returncode = 0  # Success
    mock_pgrep_result.stdout = "1234\n"  # Simulate a PID
    mock_subprocess_run.return_value = mock_pgrep_result

    linux._systemd_stop_server(server_name, server_dir)

    # Check that subprocess.run was called for pgrep *and* for sending "stop"
    expected_calls = [
        call(
            ["pgrep", "-f", f"bedrock-{server_name}"],
            capture_output=True,
            text=True,
            check=False,
        ),
        call(
            ["screen", "-S", f"bedrock-{server_name}", "-X", "stuff", "stop\n"],
            check=False,
        ),
    ]
    mock_subprocess_run.assert_has_calls(expected_calls)


@patch("subprocess.run")
def test_systemd_stop_server_no_screen_session(mock_subprocess_run, tmp_path):
    """Test when no screen session is found (pgrep returns non-zero)."""
    server_name = "test_server"
    server_dir = str(tmp_path)
    # Mock subprocess.run for 'pgrep' to return a non-zero exit code
    mock_pgrep_result = MagicMock()
    mock_pgrep_result.returncode = 1  # Simulate no matching process
    mock_pgrep_result.stdout = ""
    mock_subprocess_run.return_value = mock_pgrep_result

    linux._systemd_stop_server(server_name, server_dir)

    # Check that only pgrep was called, and *not* the screen command
    mock_subprocess_run.assert_called_once_with(
        ["pgrep", "-f", f"bedrock-{server_name}"],
        capture_output=True,
        text=True,
        check=False,
    )


@patch("subprocess.run", side_effect=FileNotFoundError)
def test_systemd_stop_server_pgrep_not_found(mock_subprocess_run, tmp_path):
    """Test when the 'pgrep' command is not found."""
    server_name = "test_server"
    server_dir = str(tmp_path)
    with pytest.raises(CommandNotFoundError, match="pgrep or screen command not found"):
        linux._systemd_stop_server(server_name, server_dir)


@patch("subprocess.run")
def test_systemd_stop_server_unexpected_error(mock_subprocess_run, tmp_path):
    """Test an unexpected error during stop"""
    server_name = "test_server"
    server_dir = str(tmp_path)
    mock_subprocess_run.side_effect = Exception("Unexpected Error")
    with pytest.raises(ServerStopError):
        linux._systemd_stop_server(server_name, server_dir)


# --- Tests for get_server_cron_jobs ---


@patch("subprocess.run")
def test_get_server_cron_jobs_found(mock_subprocess_run):
    """Test retrieving cron jobs for a server (jobs found)."""
    server_name = "test_server"
    # Simulate crontab -l output with relevant and irrelevant jobs
    mock_crontab_output = """
* * * * * /path/to/other/job
0 0 * * * /path/to/bedrock-server-manager command1 --server test_server
30 1 * * * /path/to/bedrock-server-manager scan-players
* * * * * /path/to/another/job
"""
    mock_subprocess_run.return_value.stdout = mock_crontab_output
    mock_subprocess_run.return_value.returncode = 0  # Success

    with patch("platform.system", return_value="Linux"):
        result = linux.get_server_cron_jobs(server_name)

    assert result == [
        "0 0 * * * /path/to/bedrock-server-manager command1 --server test_server",
        "30 1 * * * /path/to/bedrock-server-manager scan-players",
    ]
    mock_subprocess_run.assert_called_once_with(
        ["crontab", "-l"], capture_output=True, text=True, check=False
    )


@patch("subprocess.run")
def test_get_server_cron_jobs_no_jobs_found(mock_subprocess_run):
    """Test when no cron jobs are found for the server."""
    server_name = "test_server"
    # Simulate crontab -l output with *no* relevant jobs
    mock_crontab_output = """
* * * * * /path/to/other/job
* * * * * /path/to/another/job
"""
    mock_subprocess_run.return_value.stdout = mock_crontab_output
    mock_subprocess_run.return_value.returncode = 0

    with patch("platform.system", return_value="Linux"):
        result = linux.get_server_cron_jobs(server_name)
    assert result == "undefined"
    mock_subprocess_run.assert_called_once_with(
        ["crontab", "-l"], capture_output=True, text=True, check=False
    )


@patch("subprocess.run")
def test_get_server_cron_jobs_no_crontab(mock_subprocess_run):
    """Test when the user has no crontab at all."""
    server_name = "test_server"
    # Simulate crontab -l returning an error (no crontab)
    mock_subprocess_run.return_value.returncode = 1
    mock_subprocess_run.return_value.stderr = "no crontab for testuser"
    mock_subprocess_run.return_value.stdout = ""  # No output

    with patch("platform.system", return_value="Linux"):
        result = linux.get_server_cron_jobs(server_name)

    assert result == []  # Should return an empty list
    mock_subprocess_run.assert_called_once_with(
        ["crontab", "-l"], capture_output=True, text=True, check=False
    )


@patch(
    "subprocess.run",
    side_effect=subprocess.CalledProcessError(1, "crontab", "Mocked crontab error"),
)
def test_get_server_cron_jobs_crontab_error(mock_subprocess_run):
    """Test handling an error when running crontab -l."""
    server_name = "test_server"

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(
            ScheduleError,
            match="An unexpected error occurred: Command 'crontab' returned non-zero exit status 1.",
        ):
            linux.get_server_cron_jobs(server_name)


@patch("subprocess.run", side_effect=FileNotFoundError)
def test_get_server_cron_jobs_crontab_not_found(mock_subprocess_run):
    """Test when the 'crontab' command is not found."""
    server_name = "test_server"

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(CommandNotFoundError, match="crontab command not found"):
            linux.get_server_cron_jobs(server_name)


@patch("subprocess.run", side_effect=Exception("Mocked error"))
@patch("platform.system", return_value="Linux")
def test_get_server_cron_jobs_unexpected_error(mock_system, mock_subprocess_run):
    server_name = "test"
    with pytest.raises(ScheduleError, match="An unexpected error occurred"):
        linux.get_server_cron_jobs(server_name)
    mock_subprocess_run.assert_called()


def test_get_server_cron_jobs_missing_server_name():
    """Test with a missing server_name argument."""
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(InvalidServerNameError, match="server_name is empty"):
            linux.get_server_cron_jobs("")


def test_get_server_cron_jobs_not_linux():
    """Test on a non-Linux system (should return an empty list)."""
    server_name = "test_server"  # Doesn't matter
    with patch("platform.system", return_value="Windows"):
        result = linux.get_server_cron_jobs(server_name)
        assert result == []


# --- Tests for _parse_cron_line ---


def test_parse_cron_line_valid():
    """Test parsing a valid cron line."""
    line = "0 5 * * 1 /path/to/command arg1 arg2"
    result = linux._parse_cron_line(line)
    assert result == ("0", "5", "*", "*", "1", "/path/to/command arg1 arg2")


def test_parse_cron_line_invalid_too_few_fields():
    """Test an invalid line with too few fields."""
    line = "0 5 * *"  # Missing day of week and command
    result = linux._parse_cron_line(line)
    assert result is None


def test_parse_cron_line_invalid_empty_line():
    """Test an empty line."""
    line = ""
    result = linux._parse_cron_line(line)
    assert result is None


def test_parse_cron_line_comment_line():
    """Test a comment line (should be treated as invalid)."""
    line = "# This is a comment"
    result = linux._parse_cron_line(line)
    assert result is None


def test_parse_cron_line_extra_whitespace():
    """Test a line with extra whitespace."""
    line = "  0  5   *   *   1   /path/to/command   "
    result = linux._parse_cron_line(line)
    assert result == (
        "0",
        "5",
        "*",
        "*",
        "1",
        "/path/to/command",
    )  # Extra spaces in command should be preserved


# --- Tests for _format_cron_command ---


def test_format_cron_command_typical_case():
    """Test formatting a typical command."""
    command = f"{settings.EXPATH} backup --server my_server -t world"
    result = linux._format_cron_command(command)
    assert result == "backup"


def test_format_cron_command_no_path():
    """Test a command with no path (already formatted)."""
    command = "some_command arg1 arg2"
    result = linux._format_cron_command(command)
    assert result == "some_command"


def test_format_cron_command_path_but_no_arguments():
    """Test a command with the path but no other arguments."""
    command = f"{settings.EXPATH} my_command"
    result = linux._format_cron_command(command)
    assert result == "my_command"


def test_format_cron_command_empty_command():
    """Test an empty command string."""
    command = ""
    result = linux._format_cron_command(command)
    assert result == ""


def test_format_cron_command_with_leading_and_trailing_whitespace():
    """Test a command with extra whitespace."""
    command = f"  {settings.EXPATH}   backup --server my_server -t world  "
    result = linux._format_cron_command(command)
    assert result == "backup"


def test_format_cron_command_with_other_flags():
    command = f'{settings.EXPATH} send-command -server -c "command" '
    result = linux._format_cron_command(command)
    assert result == "send-command"


@patch("bedrock_server_manager.core.system.linux.settings")
def test_format_cron_command_mock_expath(mock_settings):
    """Test with a mocked EXPATH."""
    mock_settings.EXPATH = "/mocked/path/to/bsm"
    command = "/mocked/path/to/bsm backup --server my_server -t world"
    result = linux._format_cron_command(command)
    assert result == "backup"


# --- Tests for get_cron_jobs_table ---


def test_get_cron_jobs_table_empty_input():
    """Test with an empty list of cron jobs."""
    cron_jobs = []
    result = linux.get_cron_jobs_table(cron_jobs)
    assert result == []


def test_get_cron_jobs_table_valid_jobs():
    """Test with a list of valid cron job strings."""
    cron_jobs = [
        "0 0 * * * /path/to/command1",
        "30 1 * * 1 /path/to/command2 arg1 arg2",
    ]
    # Mock _parse_cron_line and convert_to_readable_schedule
    with (
        patch(
            "bedrock_server_manager.core.system.linux._parse_cron_line",
            side_effect=[
                (
                    "0",
                    "0",
                    "*",
                    "*",
                    "*",
                    "/path/to/command1",
                ),  # Return values for first call
                (
                    "30",
                    "1",
                    "*",
                    "*",
                    "1",
                    "/path/to/command2 arg1 arg2",
                ),  # Return values for second call
            ],
        ),
        patch(
            "bedrock_server_manager.core.system.linux.convert_to_readable_schedule",
            side_effect=["Every day at 00:00", "Weekly on Monday at 01:30"],
        ),
        patch(
            "bedrock_server_manager.core.system.linux._format_cron_command",
            side_effect=["command1", "command2"],
        ),
    ):
        result = linux.get_cron_jobs_table(cron_jobs)

        expected_result = [
            {
                "minute": "0",
                "hour": "0",
                "day_of_month": "*",
                "month": "*",
                "day_of_week": "*",
                "command": "command1",
                "schedule_time": "Every day at 00:00",
            },
            {
                "minute": "30",
                "hour": "1",
                "day_of_month": "*",
                "month": "*",
                "day_of_week": "1",
                "command": "command2",
                "schedule_time": "Weekly on Monday at 01:30",
            },
        ]
        assert result == expected_result


def test_get_cron_jobs_table_invalid_job_line():
    """Test with a cron job list that includes an invalid line."""
    cron_jobs = [
        "0 0 * * * /path/to/command1",
        "invalid line",  # Invalid line
        "30 1 * * 1 /path/to/command2",
    ]
    # Mock _parse_cron_line and convert_to_readable_schedule
    with (
        patch(
            "bedrock_server_manager.core.system.linux._parse_cron_line",
            side_effect=[
                ("0", "0", "*", "*", "*", "/path/to/command1"),  # Valid
                None,  # Simulate invalid line parsing
                ("30", "1", "*", "*", "1", "/path/to/command2"),  # Valid
            ],
        ),
        patch(
            "bedrock_server_manager.core.system.linux.convert_to_readable_schedule",
            side_effect=["Every day at 00:00", "Weekly on Monday at 01:30"],
        ),
        patch(
            "bedrock_server_manager.core.system.linux._format_cron_command",
            side_effect=["command1", "command2"],
        ),
    ):
        result = linux.get_cron_jobs_table(cron_jobs)

        expected_result = [  # Only the *valid* entries should be present
            {
                "minute": "0",
                "hour": "0",
                "day_of_month": "*",
                "month": "*",
                "day_of_week": "*",
                "command": "command1",
                "schedule_time": "Every day at 00:00",
            },
            {
                "minute": "30",
                "hour": "1",
                "day_of_month": "*",
                "month": "*",
                "day_of_week": "1",
                "command": "command2",
                "schedule_time": "Weekly on Monday at 01:30",
            },
        ]
        assert result == expected_result


# --- Tests for _add_cron_job ---


@patch("subprocess.run")
@patch("subprocess.Popen")
def test_add_cron_job_success(mock_popen, mock_subprocess_run):
    """Test successfully adding a cron job."""
    cron_string = "0 0 * * * /path/to/command"

    # Mock subprocess.run (for crontab -l) to return an empty crontab initially
    mock_subprocess_run.return_value.stdout = ""
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stderr = ""

    # Mock subprocess.Popen (for writing the new crontab)
    mock_process = MagicMock()
    mock_process.returncode = 0  # Simulate successful write
    mock_popen.return_value = mock_process

    with patch("platform.system", return_value="Linux"):
        linux._add_cron_job(cron_string)

    # Check calls: crontab -l, then crontab -
    expected_calls = [
        call(["crontab", "-l"], capture_output=True, text=True, check=False),
    ]
    mock_subprocess_run.assert_has_calls(expected_calls)

    mock_popen.assert_called_once_with(
        ["crontab", "-"], stdin=subprocess.PIPE, text=True
    )
    mock_process.communicate.assert_called_once_with(input=cron_string + "\n")


@patch("subprocess.run")
@patch("subprocess.Popen")
def test_add_cron_job_existing_crontab(mock_popen, mock_subprocess_run):
    """Test adding to an *existing* crontab."""
    cron_string = "0 0 * * * /path/to/command"
    existing_crontab = "* * * * * /path/to/existing/job\n"  # Existing job

    # Mock subprocess.run (crontab -l) to return existing content
    mock_subprocess_run.return_value.stdout = existing_crontab
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stderr = ""

    # Mock subprocess.Popen
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    with patch("platform.system", return_value="Linux"):
        linux._add_cron_job(cron_string)

    # Check that the new crontab content is correct (appended)
    expected_new_crontab = existing_crontab + cron_string + "\n"
    mock_process.communicate.assert_called_once_with(input=expected_new_crontab)


@patch(
    "subprocess.run",
    side_effect=subprocess.CalledProcessError(1, "crontab", "Mocked crontab error"),
)
def test_add_cron_job_crontab_l_error(mock_subprocess_run):
    """Test handling an error when running 'crontab -l'."""
    cron_string = "0 0 * * * /path/to/command"

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(ScheduleError, match="Failed to add cron job"):
            linux._add_cron_job(cron_string)


@patch("subprocess.run")
@patch(
    "subprocess.Popen",
    side_effect=subprocess.CalledProcessError(1, "crontab", "Mocked crontab error"),
)
def test_add_cron_job_crontab_write_error(mock_popen, mock_subprocess_run):
    """Test handling an error when writing to crontab."""
    cron_string = "0 0 * * * /path/to/command"
    mock_subprocess_run.return_value.stdout = ""  # Simulate empty crontab
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stderr = ""

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(ScheduleError, match="Failed to add cron job"):
            linux._add_cron_job(cron_string)


@patch("subprocess.run", side_effect=FileNotFoundError)
def test_add_cron_job_crontab_not_found(mock_subprocess_run):
    """Test when the 'crontab' command is not found."""
    cron_string = "0 0 * * * /path/to/command"

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(CommandNotFoundError, match="crontab command not found"):
            linux._add_cron_job(cron_string)


def test_add_cron_job_not_linux():
    """Test on a non-Linux system (should do nothing)."""
    cron_string = "0 0 * * * /path/to/command"  # Doesn't matter
    with patch("platform.system", return_value="Windows"):
        linux._add_cron_job(cron_string)  # Should return early


# --- Tests for validate_cron_input ---


def test_validate_cron_input_valid_integer():
    """Test valid integer input."""
    linux.validate_cron_input("5", 0, 59)  # Valid minute
    linux.validate_cron_input("0", 0, 23)  # Valid hour
    linux.validate_cron_input("12", 1, 31)  # Valid day of month
    linux.validate_cron_input("1", 1, 12)  # Valid month
    linux.validate_cron_input("7", 0, 7)  # Valid day of week (0 and 7 are both Sunday)


def test_validate_cron_input_valid_wildcard():
    """Test valid wildcard input."""
    linux.validate_cron_input("*", 0, 59)  # Wildcard is always valid


def test_validate_cron_input_invalid_out_of_range():
    """Test invalid out-of-range input."""
    with pytest.raises(InvalidCronJobError, match="out of range"):
        linux.validate_cron_input("60", 0, 59)  # Invalid minute
    with pytest.raises(InvalidCronJobError, match="out of range"):
        linux.validate_cron_input("-1", 0, 23)  # Invalid hour
    with pytest.raises(InvalidCronJobError, match="out of range"):
        linux.validate_cron_input("32", 1, 31)  # Invalid day of month
    with pytest.raises(InvalidCronJobError, match="out of range"):
        linux.validate_cron_input("0", 1, 12)  # Invalid month
    with pytest.raises(InvalidCronJobError, match="out of range"):
        linux.validate_cron_input("8", 0, 7)  # Invalid Day of Week


def test_validate_cron_input_invalid_non_integer():
    """Test invalid non-integer input."""
    with pytest.raises(InvalidCronJobError, match="not a valid integer or '*'"):
        linux.validate_cron_input("abc", 0, 59)
    with pytest.raises(InvalidCronJobError, match="not a valid integer or '*'"):
        linux.validate_cron_input("1.5", 0, 23)
    with pytest.raises(InvalidCronJobError, match="not a valid integer or '*'"):
        linux.validate_cron_input("1-2", 0, 59)  # Range not supported


# --- Tests for convert_to_readable_schedule ---


def test_convert_to_readable_schedule_every_minute():
    """Test the all-wildcards case."""
    result = linux.convert_to_readable_schedule("*", "*", "*", "*", "*")
    assert result == "Every minute"


def test_convert_to_readable_schedule_daily():
    """Test daily schedule."""
    result = linux.convert_to_readable_schedule(
        "*", "*", "5", "0", "*"
    )  # 5:00 AM every day
    assert result == "Daily at 05:00"


def test_convert_to_readable_schedule_monthly():
    """Test monthly schedule."""
    result = linux.convert_to_readable_schedule(
        "*", "15", "10", "30", "*"
    )  # 10:30 AM on the 15th of every month
    assert result == "Monthly on day 15 at 10:30"


def test_convert_to_readable_schedule_weekly():
    """Test weekly schedule."""
    result = linux.convert_to_readable_schedule(
        "*", "*", "14", "0", "2"
    )  # 2:00 PM every Tuesday (2)
    assert result == "Weekly on Tuesday at 14:00"


def test_convert_to_readable_schedule_specific_date():
    """Test specific date and time."""
    with patch("bedrock_server_manager.core.system.linux.datetime") as mock_datetime:
        # Mock current date
        mock_datetime.now.return_value = datetime(2024, 1, 30)

        # Ensure datetime(...) calls behave as expected
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        # Run the function with the target values
        result = linux.convert_to_readable_schedule("01", "23", "12", "59", "3")

        # The test should expect 2025 instead of 2024
        assert result == "01/23/2025 12:59"


def test_convert_to_readable_schedule_cron_format():
    """Test a schedule that should be displayed in raw cron format."""
    result = linux.convert_to_readable_schedule(
        "1", "2", "*", "3", "4"
    )  # Mixed wildcards and specifics
    assert result == "Cron schedule: 3 * 2 1 4"


def test_convert_to_readable_schedule_invalid_input():
    """Test with invalid day of week."""
    with pytest.raises(InvalidCronJobError, match="Invalid cron input:"):
        linux.convert_to_readable_schedule("*", "*", "0", "0", "8")


def test_convert_to_readable_schedule_invalid_date():
    with pytest.raises(InvalidCronJobError, match="Invalid cron input:"):
        linux.convert_to_readable_schedule("1", "1", "32", "1", "1")  # Invalid date


@patch("subprocess.run")
@patch("subprocess.Popen")
def test_modify_cron_job_success(mock_popen, mock_subprocess_run):
    """Test successfully modifying an existing cron job."""
    old_cron_string = "0 0 * * * /path/to/old/command"
    new_cron_string = "30 1 * * * /path/to/new/command"
    existing_crontab = f"""
* * * * * /path/to/other/job
{old_cron_string}
* * * * * /path/to/another/job
"""
    # Mock subprocess.run (for crontab -l)
    mock_subprocess_run.return_value.stdout = existing_crontab
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stderr = ""

    # Mock subprocess.Popen (for writing the updated crontab)
    mock_process = MagicMock()
    mock_process.returncode = 0  # Simulate successful write
    mock_popen.return_value = mock_process

    with patch("platform.system", return_value="Linux"):
        linux._modify_cron_job(old_cron_string, new_cron_string)

    # Check that crontab -l was called
    mock_subprocess_run.assert_called_once_with(
        ["crontab", "-l"], capture_output=True, text=True, check=False
    )

    # Construct the expected new crontab content.
    # Adjust the expected trailing newline to match the actual behavior.
    expected_new_crontab = (
        "\n* * * * * /path/to/other/job\n"
        "30 1 * * * /path/to/new/command\n"
        "* * * * * /path/to/another/job\n"
    )
    # Check that Popen was called correctly, and with correct input
    mock_popen.assert_called_once_with(
        ["crontab", "-"], stdin=subprocess.PIPE, text=True
    )
    mock_process.communicate.assert_called_once_with(input=expected_new_crontab)


@patch("subprocess.run")
def test_modify_cron_job_old_job_not_found(mock_subprocess_run):
    """Test when the old cron job string is not found."""
    old_cron_string = "0 0 * * * /path/to/old/command"
    new_cron_string = "30 1 * * * /path/to/new/command"
    existing_crontab = """
* * * * * /path/to/other/job
* * * * * /path/to/another/job
"""  # old_cron_string is *not* present
    # Mock subprocess.run (crontab -l)
    mock_subprocess_run.return_value.stdout = existing_crontab
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stderr = ""

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(ScheduleError, match="Cron job to modify not found"):
            linux._modify_cron_job(old_cron_string, new_cron_string)


@patch(
    "subprocess.run",
    side_effect=subprocess.CalledProcessError(1, "crontab", "Mocked crontab error"),
)
def test_modify_cron_job_crontab_l_error(mock_subprocess_run):
    """Test handling an error when running 'crontab -l'."""
    old_cron_string = "0 0 * * * /path/to/old/command"
    new_cron_string = "30 1 * * * /path/to/new/command"

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(
            ScheduleError, match="Failed to update crontab with modified job"
        ):
            linux._modify_cron_job(old_cron_string, new_cron_string)


@patch("subprocess.run")
@patch(
    "subprocess.Popen",
    side_effect=subprocess.CalledProcessError(1, "crontab", "Mocked crontab error"),
)
def test_modify_cron_job_crontab_write_error(mock_popen, mock_subprocess_run):
    """Test handling an error when writing to crontab."""
    old_cron_string = "0 0 * * * /path/to/old/command"
    new_cron_string = "30 1 * * * /path/to/new/command"
    existing_crontab = f"""
* * * * * /path/to/other/job
{old_cron_string}
* * * * * /path/to/another/job
"""
    mock_subprocess_run.return_value.stdout = (
        existing_crontab  # Simulate existing crontab
    )
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stderr = ""
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(
            ScheduleError, match="Failed to update crontab with modified job"
        ):
            linux._modify_cron_job(old_cron_string, new_cron_string)


@patch("subprocess.run", side_effect=FileNotFoundError)
def test_modify_cron_job_crontab_not_found(mock_subprocess_run):
    """Test when the 'crontab' command is not found."""
    old_cron_string = "0 0 * * * /path/to/old/command"
    new_cron_string = "30 1 * * * /path/to/new/command"
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(CommandNotFoundError, match="crontab command not found"):
            linux._modify_cron_job(old_cron_string, new_cron_string)


# --- Tests for _delete_cron_job ---


@patch("subprocess.run")
@patch("subprocess.Popen")
def test_delete_cron_job_success(mock_popen, mock_subprocess_run):
    """Test successfully deleting a cron job."""
    cron_string = "0 0 * * * /path/to/command"
    existing_crontab = f"""
* * * * * /path/to/other/job
{cron_string}
* * * * * /path/to/another/job
"""
    # Mock subprocess.run (for crontab -l)
    mock_subprocess_run.return_value.stdout = existing_crontab
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stderr = ""

    # Mock subprocess.Popen (for writing the updated crontab)
    mock_process = MagicMock()
    mock_process.returncode = 0  # Simulate successful write
    mock_popen.return_value = mock_process

    with patch("platform.system", return_value="Linux"):
        linux._delete_cron_job(cron_string)

    # Check that crontab -l was called
    mock_subprocess_run.assert_called_once_with(
        ["crontab", "-l"], capture_output=True, text=True, check=False
    )

    # Construct the expected new crontab content (job removed)
    expected_new_crontab = """
* * * * * /path/to/other/job
* * * * * /path/to/another/job
"""  # Trailing newline is optional with crontab
    # Check Popen and communicate were called with correct input
    mock_popen.assert_called_once_with(
        ["crontab", "-"], stdin=subprocess.PIPE, text=True
    )
    mock_process.communicate.assert_called_once_with(input=expected_new_crontab)


@patch("subprocess.run")
def test_delete_cron_job_not_found(mock_subprocess_run):
    """Test when the cron job string is not found (should do nothing)."""
    cron_string = "0 0 * * * /path/to/command"
    existing_crontab = """
* * * * * /path/to/other/job
* * * * * /path/to/another/job
"""  # cron_string is *not* present
    # Mock subprocess.run (crontab -l)
    mock_subprocess_run.return_value.stdout = existing_crontab
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stderr = ""
    with patch("platform.system", return_value="Linux"):
        linux._delete_cron_job(cron_string)  # Should return without error

    # crontab -l *should* have been called, but nothing else
    mock_subprocess_run.assert_called_once_with(
        ["crontab", "-l"], capture_output=True, text=True, check=False
    )


@patch(
    "subprocess.run",
    side_effect=subprocess.CalledProcessError(1, "crontab", "Mocked crontab error"),
)
def test_delete_cron_job_crontab_l_error(mock_subprocess_run):
    """Test handling an error when running 'crontab -l'."""
    cron_string = "0 0 * * * /path/to/command"

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(ScheduleError, match="Failed to update crontab"):
            linux._delete_cron_job(cron_string)


@patch("subprocess.run")
@patch(
    "subprocess.Popen",
    side_effect=subprocess.CalledProcessError(1, "crontab", "Mocked crontab error"),
)
def test_delete_cron_job_crontab_write_error(mock_popen, mock_subprocess_run):
    """Test handling an error when writing to crontab."""
    cron_string = "0 0 * * * /path/to/command"
    existing_crontab = f"""
* * * * * /path/to/other/job
{cron_string}
* * * * * /path/to/another/job
"""
    mock_subprocess_run.return_value.stdout = (
        existing_crontab  # Simulate existing crontab
    )
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stderr = ""

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(ScheduleError, match="Failed to update crontab"):
            linux._delete_cron_job(cron_string)


@patch("subprocess.run", side_effect=FileNotFoundError)
def test_delete_cron_job_crontab_not_found(mock_subprocess_run):
    """Test when the 'crontab' command is not found."""
    cron_string = "0 0 * * * /path/to/command"

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(CommandNotFoundError, match="crontab command not found"):
            linux._delete_cron_job(cron_string)


def test_delete_cron_job_not_linux():
    """Test on a non-Linux system (should do nothing)."""
    cron_string = "0 0 * * * /path/to/command"  # Doesn't matter
    with patch("platform.system", return_value="Windows"):
        linux._delete_cron_job(cron_string)  # Should return early
