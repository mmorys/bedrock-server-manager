# bedrock-server-manager/tests/core/system/test_base.py
import pytest
import shutil
import socket
import platform
import stat
import subprocess
import os
from pathlib import Path
import time
from unittest.mock import patch, MagicMock, call
from bedrock_server_manager.core.system import base
from bedrock_server_manager.core.error import (
    MissingPackagesError,
    InternetConnectivityError,
    DirectoryError,
    MissingArgumentError,
    CommandNotFoundError,
    ResourceMonitorError,
    SetFolderPermissionsError,
)

# --- Fixtures ---


@pytest.fixture
def mock_socket():
    """Fixture to mock the socket.socket object."""
    with patch("socket.socket") as mock_socket:
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance  # Always return the instance
        yield mock_socket


# --- Tests for check_prerequisites ---


def test_check_prerequisites_linux_success():
    """Test successful check on Linux (all packages present)."""
    with patch("platform.system", return_value="Linux"):
        with patch(
            "shutil.which", return_value="/path/to/package"
        ):  # Mock 'which' to *find* the packages
            base.check_prerequisites()  # Should not raise an exception


def test_check_prerequisites_linux_missing_packages():
    """Test check on Linux with missing packages."""
    with patch("platform.system", return_value="Linux"):
        with patch(
            "shutil.which", return_value=None
        ):  # Mock 'which' to *not* find the packages
            with pytest.raises(MissingPackagesError, match="Missing required packages"):
                base.check_prerequisites()


def test_check_prerequisites_windows():
    """Test on Windows (should do nothing)."""
    with patch("platform.system", return_value="Windows"):
        # No mocking of 'which' needed on Windows
        base.check_prerequisites()  # Should not raise an exception


def test_check_prerequisites_unsupported_os():
    """Test on an unsupported OS (should do nothing, but log a warning)."""
    with (
        patch("platform.system", return_value="Solaris"),
        patch("bedrock_server_manager.core.system.base.logger") as mock_logger,
    ):

        base.check_prerequisites()  # Should not raise an exception
        mock_logger.warning.assert_called_once_with("Unsupported operating system.")


# --- Tests for check_internet_connectivity ---


@patch("socket.socket")
def test_check_internet_connectivity_success(mock_socket):
    """Test successful internet connection."""
    # Mock the socket to simulate a successful connection
    mock_socket_instance = MagicMock()
    mock_socket.return_value = mock_socket_instance
    # Don't need to mock connect, as successful connection is the default

    base.check_internet_connectivity()  # Should not raise an exception
    mock_socket.assert_called_once()  # Check that socket was created.
    mock_socket_instance.connect.assert_called_once()


@patch("socket.socket")
def test_check_internet_connectivity_failure(mock_socket):
    """Test failed internet connection."""
    # Mock the socket to simulate a connection error
    mock_socket_instance = MagicMock()
    mock_socket.return_value = mock_socket_instance
    mock_socket_instance.connect.side_effect = socket.error("Mocked connection error")

    with pytest.raises(InternetConnectivityError, match="Connectivity test failed"):
        base.check_internet_connectivity()


@patch("socket.socket", side_effect=Exception("Unexpected error"))
def test_check_internet_connectivity_unexpected_error(mock_socket):
    """Test unexpected error during connection check."""
    with pytest.raises(InternetConnectivityError, match="An unexpected error occurred"):
        base.check_internet_connectivity()


def test_check_internet_connectivity_custom_host_port(mock_socket):
    """Test with custom host and port."""
    mock_socket_instance = MagicMock()
    mock_socket.return_value = mock_socket_instance

    base.check_internet_connectivity(host="example.com", port=80)
    mock_socket_instance.connect.assert_called_once_with(("example.com", 80))


def test_check_internet_connectivity_custom_timeout(mock_socket):
    """Test with custom timeout"""
    mock_socket_instance = MagicMock()
    mock_socket.return_value = mock_socket_instance

    base.check_internet_connectivity(timeout=5)
    socket.setdefaulttimeout(5)


# --- Tests for set_server_folder_permissions ---
@patch("os.walk")
@patch("os.chmod")
@patch("os.stat")
def test_set_server_folder_permissions_linux(
    mock_stat, mock_chmod, mock_walk, tmp_path
):
    """Test setting permissions on Linux."""
    server_dir = tmp_path / "server"
    server_dir.mkdir(parents=True, exist_ok=True)

    # Create files and directories within the server directory
    (server_dir / "file1.txt").touch()
    (server_dir / "dir1").mkdir()
    (server_dir / "dir1" / "file2.txt").touch()
    (server_dir / "bedrock_server").touch()  # Dummy executable

    # Set up mock return values for os.walk
    mock_walk.return_value = [
        (str(server_dir), ["dir1"], ["file1.txt", "bedrock_server"]),
        (str(server_dir / "dir1"), [], ["file2.txt"]),
    ]

    def stat_side_effect(path):
        """Side effect for os.stat to simulate different file types."""
        mock_result = MagicMock()
        # Simulate directory or file based on the path
        if Path(path).name == "dir1":
            mock_result.st_mode = 0o40775  # Directory with permissions
        elif Path(path).name == "bedrock_server":
            mock_result.st_mode = 0o100755  # Regular file (executable)
        elif Path(path) == server_dir:
            mock_result.st_mode = 0o40775  # Directory with permissions
        else:
            mock_result.st_mode = 0o100664  # Regular file
        return mock_result

    mock_stat.side_effect = stat_side_effect

    # Mock platform.system, os.chown, os.getuid, and os.getgid
    with (
        patch("platform.system", return_value="Linux"),
        patch("os.chown", create=True) as mock_chown,
        patch("os.getuid", return_value=1000, create=True),
        patch("os.getgid", return_value=1000, create=True),
    ):

        # Call the function *after* setting up all mocks
        base.set_server_folder_permissions(str(server_dir))

        # Check that os.chmod was called with the correct arguments
        expected_calls = [
            call(str(server_dir / "dir1"), 0o775),
            call(str(server_dir / "file1.txt"), 0o664),
            call(str(server_dir / "bedrock_server"), 0o755),
            call(str(server_dir / "dir1" / "file2.txt"), 0o664),
        ]
        mock_chmod.assert_has_calls(expected_calls, any_order=True)


def test_set_server_folder_permissions_missing_server_dir():
    """Test with a missing server_dir argument."""
    with pytest.raises(MissingArgumentError, match="server_dir is empty"):
        base.set_server_folder_permissions("")


def test_set_server_folder_permissions_server_dir_not_found(tmp_path):
    """Test with a server_dir that doesn't exist."""
    server_dir = tmp_path / "nonexistent_server"  # Doesn't exist
    with pytest.raises(
        DirectoryError, match="server_dir '.*' does not exist or is not a directory"
    ):
        base.set_server_folder_permissions(str(server_dir))


from unittest.mock import patch, MagicMock, call
import os, stat
from bedrock_server_manager.core.system import base  # Adjust your import as needed


@patch("os.walk")
@patch("os.chmod")
@patch("os.stat")
@patch("os.path.isdir", return_value=True)
def test_set_server_folder_permissions_windows(
    mock_isdir, mock_stat, mock_chmod, mock_walk, tmp_path
):
    """Test setting permissions on Windows."""
    # Create a temporary server directory structure.
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    (server_dir / "file1.txt").touch()
    (server_dir / "dir1").mkdir()
    (server_dir / "dir1" / "file2.txt").touch()
    # For Windows, the executable is expected to be named "bedrock_server.exe"
    (server_dir / "bedrock_server.exe").touch()

    # Set up os.walk to simulate the directory structure.
    mock_walk.return_value = [
        (str(server_dir), ["dir1"], ["file1.txt", "bedrock_server.exe"]),
        (str(server_dir / "dir1"), [], ["file2.txt"]),
    ]

    # Simulate that each file/directory currently has read-only permissions.
    mock_stat_result = MagicMock()
    mock_stat_result.st_mode = stat.S_IREAD  # 0o400: read-only
    mock_stat.return_value = mock_stat_result

    # Simulate Windows environment.
    with patch("platform.system", return_value="Windows"):
        base.set_server_folder_permissions(str(server_dir))

    expected_mode = stat.S_IREAD | stat.S_IWRITE  # 0o400 | 0o200 = 0o600

    expected_calls = [
        call(str(server_dir / "dir1"), expected_mode),
        call(str(server_dir / "file1.txt"), expected_mode),
        call(str(server_dir / "bedrock_server.exe"), expected_mode),
        call(str(server_dir / "dir1" / "file2.txt"), expected_mode),
    ]

    # Assert that os.chmod was called with the expected calls (order does not matter).
    mock_chmod.assert_has_calls(expected_calls, any_order=True)


# --- Tests for is_server_running ---


@patch("subprocess.run")
def test_is_server_running_linux_running(mock_subprocess_run):
    """Test when the server is running on Linux (screen check)."""
    mock_subprocess_run.return_value.stdout = (
        "Some output\n.bedrock-test_server\nMore output"
    )
    with patch("platform.system", return_value="Linux"):
        result = base.is_server_running(
            "test_server", "base_dir"
        )  # base_dir doesn't matter here
        assert result is True
    mock_subprocess_run.assert_called_once_with(
        ["screen", "-ls"], capture_output=True, text=True, check=False
    )


@patch("subprocess.run")
def test_is_server_running_linux_not_running(mock_subprocess_run):
    """Test when the server is *not* running on Linux."""
    mock_subprocess_run.return_value.stdout = "Some output\nNo matching screen found.\n"
    with patch("platform.system", return_value="Linux"):
        result = base.is_server_running("test_server", "base_dir")
        assert result is False


@patch("subprocess.run", side_effect=FileNotFoundError)
def test_is_server_running_linux_screen_not_found(mock_subprocess_run):
    """Test when the 'screen' command is not found on Linux."""
    with patch("platform.system", return_value="Linux"):
        with pytest.raises(CommandNotFoundError, match="screen command not found."):
            base.is_server_running("test_server", "base_dir")


@patch("psutil.process_iter")
def test_is_server_running_windows_running(mock_process_iter, tmp_path):
    """Test when the server is running on Windows."""
    base_dir = str(tmp_path / "servers")

    # Create mock process info that simulates a running server
    mock_process = MagicMock()
    mock_process.info = {
        "name": "bedrock_server.exe",
        "cwd": os.path.join(
            base_dir, "test_server"
        ).lower(),  # Correct case for comparison
        "pid": 1234,
        "cmdline": [],  # Doesn't matter in this test
    }
    mock_process_iter.return_value = [mock_process]

    with patch("platform.system", return_value="Windows"):
        result = base.is_server_running("test_server", base_dir)
        assert result is True


@patch("psutil.process_iter")
def test_is_server_running_windows_not_running(mock_process_iter, tmp_path):
    """Test when the server is *not* running on Windows."""
    base_dir = str(tmp_path / "servers")
    # Create mock process info that *doesn't* match the server
    mock_process = MagicMock()
    mock_process.info = {
        "name": "some_other_process.exe",  # Different name
        "cwd": "C:\\Some\\Other\\Path",
        "pid": 1234,
        "cmdline": [],
    }
    mock_process_iter.return_value = [mock_process]

    with patch("platform.system", return_value="Windows"):
        result = base.is_server_running("test_server", base_dir)
        assert result is False


@patch("psutil.process_iter")
def test_is_server_running_windows_no_processes(mock_process_iter, tmp_path):
    """Test Windows with *no* processes running."""
    base_dir = str(tmp_path / "servers")
    mock_process_iter.return_value = []  # Empty list - no processes

    with patch("platform.system", return_value="Windows"):
        result = base.is_server_running("test_server", base_dir)
        assert result is False


@patch("psutil.process_iter", side_effect=Exception("Mocked error"))
def test_is_server_running_windows_error(mock_process_iter, tmp_path):
    """Test handling an error on Windows."""
    base_dir = str(tmp_path / "servers")
    with patch("platform.system", return_value="Windows"):
        result = base.is_server_running("test_server", base_dir)  # Don't expect raise
        assert result is False


def test_is_server_running_unsupported_os():
    """Test on an unsupported OS (should return False and log an error)."""
    with (
        patch("platform.system", return_value="Solaris"),
        patch("bedrock_server_manager.core.system.base.logger") as mock_logger,
    ):

        result = base.is_server_running("test_server", "base_dir")
        assert result is False  # Should return False
        mock_logger.error.assert_called_once_with(
            "Unsupported operating system for running check."
        )


# --- Tests for _get_bedrock_process_info ---


@patch("psutil.Process")
@patch("psutil.process_iter")
def test_get_bedrock_process_info_linux_success(
    mock_process_iter, mock_process, tmp_path
):
    """Test successful retrieval of process info on Linux."""
    server_name = "test_server"
    base_dir = str(tmp_path)

    # Mock the screen process
    mock_screen_process = MagicMock()
    mock_screen_process.pid = 1000
    mock_screen_process.info = {
        "pid": 1000,
        "name": "screen",
        "cmdline": [
            "screen",
            "-S",
            f"bedrock-{server_name}",
            "-X",
            "stuff",
            "some_command",
        ],
    }

    # Mock Bedrock server process (child of screen)
    mock_bedrock_process = MagicMock()
    mock_bedrock_process.pid = 1234
    mock_bedrock_process.name.return_value = "bedrock_server"
    mock_bedrock_process.cpu_percent.return_value = 25.0
    mock_bedrock_process.memory_info.return_value.rss = 2 * 1024 * 1024 * 1024
    mock_bedrock_process.create_time.return_value = time.time() - 3600

    # Ensure children() returns the bedrock process
    mock_screen_process.children.return_value = [mock_bedrock_process]

    # Ensure psutil.Process(screen_pid) returns mock_screen_process
    mock_process.side_effect = lambda pid: (
        mock_screen_process if pid == 1000 else mock_bedrock_process
    )

    # Mock process_iter to return the screen process
    mock_process_iter.return_value = [mock_screen_process]

    with (
        patch("platform.system", return_value="Linux"),
        patch("psutil.cpu_count", return_value=4),
    ):
        result = base._get_bedrock_process_info(server_name, base_dir)

    assert result is not None, "Bedrock process info should not be None"
    assert result["pid"] == 1234
    assert result["cpu_percent"] == 25.0 / 4
    assert result["memory_mb"] == 2048
    assert "uptime" in result


@patch("psutil.process_iter")
def test_get_bedrock_process_info_linux_no_screen_process(mock_process_iter, tmp_path):
    """Test when no 'screen' process is found on Linux."""
    server_name = "test_server"
    base_dir = str(tmp_path)  # Doesn't matter in this test

    # Mock process_iter to return *no* matching processes
    mock_process_iter.return_value = []

    with patch("platform.system", return_value="Linux"):
        result = base._get_bedrock_process_info(server_name, base_dir)
        assert result is None  # Should return None


@patch("psutil.Process")
@patch("psutil.process_iter")
def test_get_bedrock_process_info_linux_no_bedrock_process(
    mock_process_iter, mock_process, tmp_path
):
    """Test when no Bedrock server process is found (but screen is running)."""
    server_name = "test_server"
    base_dir = str(tmp_path)
    # Mock the screen process
    mock_screen_process = MagicMock()
    mock_screen_process.pid = 1000
    mock_screen_process.name.return_value = "screen"
    mock_screen_process.cmdline.return_value = [
        "screen",
        "-S",
        f"bedrock-{server_name}",
        "-X",
        "stuff",
        "some_command",
    ]
    mock_process_iter.return_value = [mock_screen_process]

    # Mock the children method to return an *empty list* (no Bedrock process)
    mock_screen_process.children.return_value = []
    mock_process.return_value.oneshot.return_value.__enter__.return_value = []

    with patch("platform.system", return_value="Linux"):
        result = base._get_bedrock_process_info(server_name, base_dir)
        assert result is None


@patch("psutil.Process")
@patch("psutil.process_iter")
def test_get_bedrock_process_info_linux_error(
    mock_process_iter, mock_process, tmp_path
):
    """Test handling an unexpected error during process info retrieval on Linux."""
    server_name = "test_server"
    base_dir = str(tmp_path)

    # Mock the screen process
    mock_screen_process = MagicMock()
    mock_screen_process.pid = 1000
    mock_screen_process.info = {
        "pid": 1000,
        "name": "screen",
        "cmdline": [
            "screen",
            "-S",
            f"bedrock-{server_name}",
            "-X",
            "stuff",
            "some_command",
        ],
    }

    # Mock process_iter to return screen
    mock_process_iter.return_value = [mock_screen_process]

    # Mock Bedrock server process (child of screen)
    mock_bedrock_process = MagicMock()
    mock_bedrock_process.pid = 1234
    mock_bedrock_process.name.return_value = "bedrock_server"

    # Ensure children() returns the Bedrock process
    mock_screen_process.children.return_value = [mock_bedrock_process]

    # Make cpu_percent raise an error
    mock_bedrock_process.cpu_percent.side_effect = Exception("Mocked CPU usage error")

    # Ensure psutil.Process(screen_pid) returns mock_screen_process
    mock_process.side_effect = lambda pid: (
        mock_screen_process if pid == 1000 else mock_bedrock_process
    )

    with patch("platform.system", return_value="Linux"):
        with pytest.raises(ResourceMonitorError, match="Error during monitoring"):
            base._get_bedrock_process_info(server_name, base_dir)


@patch("psutil.Process")
@patch("psutil.process_iter")
def test_get_bedrock_process_info_windows_success(
    mock_process_iter, mock_process, tmp_path
):
    """Test successful retrieval of process info on Windows."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"  # Keep as Path object
    base_dir.mkdir()

    base_dir = str(base_dir)  # Convert to string if needed later


@patch("psutil.process_iter")
def test_get_bedrock_process_info_windows_not_found(mock_process_iter, tmp_path):
    """Test when no Bedrock server process is found on Windows."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"  # Keep as Path object
    base_dir.mkdir()

    base_dir = str(base_dir)  # Convert to string if needed later


@patch("psutil.Process")
@patch("psutil.process_iter")
def test_get_bedrock_process_info_windows_error(
    mock_process_iter, mock_process, tmp_path
):
    """Test handling an unexpected error during process info retrieval on Windows."""
    server_name = "test_server"
    base_dir = tmp_path / "servers"  # Keep as Path object
    base_dir.mkdir()  # Works now

    base_dir = str(base_dir)  # Convert to string if needed later

    # Mock the Bedrock server process
    mock_bedrock_process = MagicMock()
    mock_bedrock_process.info = {
        "name": "bedrock_server.exe",
        "cwd": os.path.join(base_dir, server_name).lower(),
        "pid": 1234,
        "cmdline": [],
    }

    mock_process_iter.return_value = [mock_bedrock_process]

    # Make some operation within the 'with' block raise an exception
    mock_process.return_value = mock_bedrock_process
    mock_bedrock_process.cpu_percent.side_effect = Exception("Mocked CPU usage error")
    mock_process.return_value.oneshot.return_value.__enter__.return_value = (
        mock_bedrock_process
    )

    with patch("platform.system", return_value="Windows"):
        with pytest.raises(ResourceMonitorError, match="Error during monitoring"):
            base._get_bedrock_process_info(server_name, str(base_dir))


def test_get_bedrock_process_info_unsupported_os():
    """Test on an unsupported operating system (should return None)."""
    with (
        patch("platform.system", return_value="Solaris"),
        patch("bedrock_server_manager.core.system.base.logger") as mock_logger,
    ):

        result = base._get_bedrock_process_info("test_server", "base_dir")
        assert result is None  # Should return None
        mock_logger.error.assert_called_once_with("Unsupported OS for monitoring")


# --- Tests for remove_readonly ---


@patch("subprocess.run")
def test_remove_readonly_windows(mock_subprocess_run, tmp_path):
    """Test removing read-only attribute on Windows (using attrib)."""
    # Create a test file.
    test_file = tmp_path / "test_file.txt"
    test_file.touch()

    # Patch os.environ so that SYSTEMROOT is set.
    with patch.dict(os.environ, {"SYSTEMROOT": "C:\\Windows"}):
        # Simulate a Windows environment.
        with patch("platform.system", return_value="Windows"):
            base.remove_readonly(str(test_file))

    # Build the expected command. The function constructs attrib_path as:
    # os.path.join(os.environ['SYSTEMROOT'], 'System32', 'attrib.exe')
    expected_attrib_path = os.path.join("C:\\Windows", "System32", "attrib.exe")
    expected_command = [expected_attrib_path, "-R", str(test_file), "/S"]

    # Assert that subprocess.run was called with the expected command and parameters.
    mock_subprocess_run.assert_called_once_with(
        expected_command, check=True, capture_output=True, text=True
    )


@patch("os.chmod")
@patch("os.stat")
@patch("os.path.isfile", return_value=True)
@patch("platform.system", return_value="Linux")
def test_remove_readonly_linux_file(
    mock_platform, mock_isfile, mock_stat, mock_chmod, tmp_path
):
    """Test removing read-only attribute from a file on Linux."""
    test_file = tmp_path / "test_file.txt"
    test_file.touch()

    # Mock os.stat to return read-only permissions
    mock_stat_result = MagicMock()
    mock_stat_result.st_mode = 0o444  # Read-only
    mock_stat.return_value = mock_stat_result

    base.remove_readonly(str(test_file))

    # Expect chmod to be called with write permissions added
    mock_chmod.assert_called_once_with(str(test_file), 0o444 | stat.S_IWUSR)


@patch("os.path.isfile", return_value=True)
@patch("os.walk")
@patch("os.chmod")
@patch("os.stat")
@patch("os.getuid", return_value=1000, create=True)
@patch("os.getgid", return_value=1000, create=True)
def test_remove_readonly_linux_bedrock_server(
    mock_getgid, mock_getuid, mock_stat, mock_chmod, mock_walk, mock_isfile, tmp_path
):
    """Test handling of 'bedrock_server' file on Linux (executable + write)."""
    test_file = tmp_path / "bedrock_server"
    test_file.touch()

    # Simulate the directory walk returning nothing (it's a file)
    mock_walk.return_value = []

    # Mock os.stat to return read-only permissions
    mock_stat_result = MagicMock()
    mock_stat_result.st_mode = 0o400  # Read-only
    mock_stat.return_value = mock_stat_result

    with patch("platform.system", return_value="Linux"):
        base.remove_readonly(str(test_file))

    # Expect chmod to add both write and execute permissions (0o400 | 0o200 | 0o100 = 0o700)
    mock_chmod.assert_called_once_with(
        str(test_file), 0o400 | stat.S_IWUSR | stat.S_IXUSR
    )


@patch("os.path.isdir", side_effect=lambda p: "test_dir" in p)
@patch(
    "os.path.isfile",
    side_effect=lambda p: p.endswith(".txt") or p.endswith("bedrock_server"),
)
@patch("os.walk")
@patch("os.chmod")
@patch("os.stat")
@patch("os.getuid", return_value=1000, create=True)
@patch("os.getgid", return_value=1000, create=True)
def test_remove_readonly_linux_directory(
    mock_getgid,
    mock_getuid,
    mock_stat,
    mock_chmod,
    mock_walk,
    mock_isfile,
    mock_isdir,
    tmp_path,
):
    """Test removing read-only attribute from a directory on Linux."""
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    test_file = test_dir / "test_file.txt"
    test_file.touch()
    test_file_in_dir = test_dir / "bedrock_server"
    test_file_in_dir.touch()

    # Mock os.walk to return the directory and its files
    mock_walk.return_value = [(str(test_dir), [], ["test_file.txt", "bedrock_server"])]

    # Mock os.stat to return read-only permissions initially
    mock_stat_result_dir = MagicMock()
    mock_stat_result_dir.st_mode = 0o555  # Read/execute only for directory
    mock_stat_result_file = MagicMock()
    mock_stat_result_file.st_mode = 0o444  # Read-only
    mock_stat_result_server = MagicMock()
    mock_stat_result_server.st_mode = 0o555  # Read/execute for bedrock_server

    # Mock the responses based on the path
    def stat_side_effect(path):
        if path == str(test_dir):
            return mock_stat_result_dir
        elif path == str(test_file_in_dir):
            return mock_stat_result_server
        else:
            return mock_stat_result_file

    mock_stat.side_effect = stat_side_effect

    with patch("platform.system", return_value="Linux"):
        base.remove_readonly(str(test_dir))

    # Expect chmod to be called for the directory and both files
    mock_chmod.assert_has_calls(
        [
            call(str(test_dir), 0o755),  # Directory: rwx for user, rx for group/other
            call(str(test_file), 0o644),  # Regular file: rw for user, r for group/other
            call(
                str(test_file_in_dir), 0o755
            ),  # bedrock_server: rwx for user, rx for group/other
        ],
        any_order=False,
    )


def test_remove_readonly_path_not_exists(tmp_path):
    """Test with a path that doesn't exist (shouldn't raise an error)."""
    nonexistent_path = tmp_path / "nonexistent"
    # Should not raise an exception
    base.remove_readonly(str(nonexistent_path))


@patch.dict(os.environ, {"SYSTEMROOT": "C:\\Windows"})
@patch(
    "subprocess.run",
    side_effect=subprocess.CalledProcessError(1, "attrib", "Mocked attrib error"),
)
def test_remove_readonly_windows_error(mock_subprocess_run, tmp_path):
    """Test handling an error with the attrib command on Windows."""
    test_file = tmp_path / "test_file.txt"
    test_file.touch()

    with patch("platform.system", return_value="Windows"):
        with pytest.raises(
            SetFolderPermissionsError,
            match="Failed to remove read-only attribute on Windows",
        ):
            base.remove_readonly(str(test_file))


@patch("os.chmod", side_effect=OSError("Mocked chmod error"))
@patch("platform.system", return_value="Linux")
def test_remove_readonly_linux_error(mock_system, mock_chmod, tmp_path):
    """Test handling an error with os.chmod on Linux."""
    test_file = tmp_path / "test_file.txt"
    test_file.touch()
    with pytest.raises(
        SetFolderPermissionsError, match="Failed to remove read-only attribute on Linux"
    ):
        base.remove_readonly(str(test_file))


def test_remove_readonly_unsupported_os(tmp_path):
    """Test with an unsupported OS"""
    test_file = tmp_path / "test_file.txt"
    test_file.touch()
    with (
        patch("platform.system", return_value="Solaris"),
        patch("bedrock_server_manager.core.system.base.logger") as mock_logger,
    ):
        base.remove_readonly(str(test_file))
        mock_logger.warning.assert_called_once_with(
            f"Unsupported operating system in remove_readonly: Solaris"
        )
