# bedrock-server-manager/tests/core/system/test_windows.py
import pytest
import os
import subprocess
import platform
import psutil
from xml.etree import ElementTree as ET
from unittest.mock import patch, MagicMock, mock_open, call, ANY
from bedrock_server_manager.core.system import windows
from bedrock_server_manager.core.error import (
    ServerStartError,
    ServerNotFoundError,
    ServerStopError,
    TaskError,
    FileOperationError,
    MissingArgumentError,
    InvalidInputError,
)

# --- Tests for _windows_start_server ---


@patch("subprocess.Popen")
def test_windows_start_server_success(mock_popen, tmp_path):
    """Test successful server start on Windows."""
    server_name = "test_server"
    server_dir = str(tmp_path / "server")
    os.makedirs(server_dir)
    exe_path = os.path.join(server_dir, "bedrock_server.exe")
    # Create a dummy executable file.
    with open(exe_path, "w") as f:
        f.write("")

    # Prepare a mock process object to be returned by Popen.
    mock_process = MagicMock()
    mock_process.pid = 1234  # Simulate a PID
    mock_popen.return_value = mock_process
    # Optionally simulate process output.
    mock_process.stdout.readline.side_effect = [b"Some output\n", b""]

    # Patch builtins.open to capture file operations.
    m_open = mock_open()
    # Use patch.object with create=True to patch CREATE_NO_WINDOW even if it doesn't exist.
    with (
        patch("builtins.open", m_open),
        patch.object(subprocess, "CREATE_NO_WINDOW", 0, create=True),
        patch("platform.system", return_value="Windows"),
    ):
        result = windows._windows_start_server(server_name, server_dir)

    # Retrieve the file handle used when open() was called in append mode.
    file_handle = m_open.return_value.__enter__.return_value

    # Verify that the process object is returned.
    assert result == mock_process

    # Verify that subprocess.Popen was called with the expected arguments.
    mock_popen.assert_called_once_with(
        [exe_path],
        cwd=server_dir,
        stdin=subprocess.PIPE,
        stdout=file_handle,  # Expect the file handle from open()
        stderr=file_handle,  # Expect the file handle from open()
        creationflags=0,  # Patched value
    )


def test_windows_start_server_executable_not_found(tmp_path):
    """Test when the server executable is not found."""
    server_name = "test_server"
    server_dir = str(tmp_path / "server")
    os.makedirs(server_dir)
    # Don't create the executable

    with pytest.raises(ServerNotFoundError):
        windows._windows_start_server(server_name, server_dir)


@patch("subprocess.Popen", side_effect=Exception("Mocked start error"))
def test_windows_start_server_start_failure(mock_popen, tmp_path):
    """Test handling a failure to start the server executable."""
    server_name = "test_server"
    server_dir = str(tmp_path / "server")
    os.makedirs(server_dir)
    exe_path = os.path.join(server_dir, "bedrock_server.exe")
    with open(exe_path, "w") as f:
        f.write("")

    with patch("builtins.open", mock_open()) as mock_file:  # Mock file operations
        with pytest.raises(ServerStartError, match="Failed to start server executable"):
            windows._windows_start_server(server_name, server_dir)
    assert (
        mock_file.return_value.write.call_count == 1
    )  # file should still get written too


@patch("subprocess.Popen")
def test_windows_start_server_output_file_creation_fails(mock_popen, tmp_path):
    """Test server start when output file creation fails."""
    server_name = "test_server"
    server_dir = str(tmp_path / "server")
    os.makedirs(server_dir)
    exe_path = os.path.join(server_dir, "bedrock_server.exe")
    # Create dummy executable file
    with open(exe_path, "w") as f:
        f.write("")

    # Set the side effect for Popen so that the fallback call fails.
    mock_popen.side_effect = Exception("Mocked Popen failure on fallback")

    # Create a custom mock for open() that always raises OSError.
    mock_file = mock_open()
    mock_file.side_effect = OSError("Mocked file open error")

    # Patch subprocess.CREATE_NO_WINDOW (create it if it doesn't exist)
    with patch.object(subprocess, "CREATE_NO_WINDOW", 0, create=True):
        with patch("builtins.open", mock_file):
            with pytest.raises(
                ServerStartError, match="Failed to start server executable"
            ):
                windows._windows_start_server(server_name, server_dir)


# --- Tests for _windows_stop_server ---


@patch("psutil.process_iter")
def test_windows_stop_server_success(mock_process_iter, tmp_path):
    """Test successful server stop on Windows."""
    server_name = "test_server"
    server_dir = str(tmp_path / "servers" / server_name)
    os.makedirs(server_dir)

    # Create a mock process that matches the server we want to stop
    mock_process = MagicMock()
    mock_process.info = {
        "name": "bedrock_server.exe",
        "cwd": server_dir.lower(),  # Use the correct, lowercased path
        "pid": 1234,
        "cmdline": [],
    }
    mock_process.kill.return_value = None  # Simulate successful kill
    mock_process.wait.return_value = None  # Simulate successful wait

    # Make process_iter return our mock process
    mock_process_iter.return_value = [mock_process]

    # Mock psutil.Process to return the same mock process when given the PID
    with patch("psutil.Process", return_value=mock_process) as mock_psutil_process:
        windows._windows_stop_server(server_name, server_dir)

        mock_process.kill.assert_called_once()  # Check kill was called
        mock_process.wait.assert_called_once()  # Check wait was called
        mock_psutil_process.assert_called_with(1234)  # pid passed in


@patch("psutil.process_iter")
def test_windows_stop_server_not_running(mock_process_iter, tmp_path):
    """Test when the server process is not found."""
    server_name = "test_server"
    server_dir = str(tmp_path / "servers" / server_name)
    os.makedirs(server_dir)

    # Make process_iter return an empty list (no matching processes)
    mock_process_iter.return_value = []

    #  No exception should be raised; the function should log and return.
    windows._windows_stop_server(server_name, server_dir)


@patch("psutil.process_iter", side_effect=Exception("Mocked process iteration error"))
def test_windows_stop_server_iteration_error(mock_process_iter, tmp_path):
    """Test handling an error during process iteration."""
    server_name = "test_server"
    server_dir = str(tmp_path / "servers" / server_name)
    os.makedirs(server_dir)
    with pytest.raises(ServerStopError, match="Failed to stop server process"):
        windows._windows_stop_server(server_name, server_dir)


@patch("psutil.process_iter")
def test_windows_stop_server_kill_fail(mock_process_iter, tmp_path):
    """Test server process stop fail"""
    server_name = "test_server"
    server_dir = str(tmp_path / "servers" / server_name)
    os.makedirs(server_dir)

    # Create a mock process that matches the server we want to stop
    mock_process = MagicMock()
    mock_process.info = {
        "name": "bedrock_server.exe",
        "cwd": server_dir.lower(),
        "pid": 1234,
        "cmdline": [],
    }
    mock_process.kill.side_effect = psutil.NoSuchProcess(
        1234
    )  # Simulate process disappearing
    # Make process_iter return our mock process
    mock_process_iter.return_value = [mock_process]

    # Mock psutil.Process to return the same mock process when given the PID
    with patch("psutil.Process", return_value=mock_process):
        windows._windows_stop_server(server_name, server_dir)  # should continue

        mock_process.kill.assert_called_once()  # Check kill was called
        mock_process.wait.assert_not_called()  # Shouldnt be called


# --- Tests for get_windows_task_info ---


@patch("subprocess.run")
def test_get_windows_task_info_success(mock_subprocess_run, tmp_path):
    """Test successfully retrieving task info."""
    task_names = ["test_task1", "test_task2"]
    # Create a *valid* XML output for schtasks (for test_task1)
    xml_output1 = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>2023-01-01T10:00:00</Date>
    <Author>Test User</Author>
    <URI>\\test_task1</URI>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <StartBoundary>2023-01-01T10:00:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-21-1234567890</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>true</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT72H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>C:\\path\\to\\bedrock-server-manager\\bedrock-server-manager</Command>
      <Arguments>start-server --server test_server</Arguments>
    </Exec>
  </Actions>
</Task>
"""
    # Create a *valid* XML output for schtasks (for test_task2)
    xml_output2 = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>2024-05-03T11:23:00</Date>
    <Author>Test User</Author>
    <URI>\\test_task2</URI>
  </RegistrationInfo>
  <Triggers>
   <CalendarTrigger>
      <StartBoundary>2024-01-01T10:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-21-1234567890</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
        <DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>
        <StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>
        <AllowHardTerminate>true</AllowHardTerminate>
        <StartWhenAvailable>false</StartWhenAvailable>
        <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
        <IdleSettings>
            <StopOnIdleEnd>true</StopOnIdleEnd>
            <RestartOnIdle>false</RestartOnIdle>
        </IdleSettings>
        <AllowStartOnDemand>true</AllowStartOnDemand>
        <Enabled>true</Enabled>
        <Hidden>false</Hidden>
        <RunOnlyIfIdle>false</RunOnlyIfIdle>
        <WakeToRun>false</WakeToRun>
        <ExecutionTimeLimit>PT72H</ExecutionTimeLimit>
        <Priority>7</Priority>
      </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>C:\\path\\to\\bedrock-server-manager\\bedrock-server-manager</Command>
      <Arguments>backup --server test_server -t world</Arguments>
    </Exec>
  </Actions>
</Task>
"""
    # Mock subprocess.run to return the XML output for each task
    mock_subprocess_run.side_effect = [
        MagicMock(stdout=xml_output1, returncode=0),  # Success for test_task1
        MagicMock(stdout=xml_output2, returncode=0),  # Success for test_task2
    ]
    mock_settings = MagicMock()
    mock_settings.EXPATH = "C:\\path\\to\\bedrock-server-manager"
    with patch("bedrock_server_manager.core.system.windows.EXPATH", mock_settings):
        result = windows.get_windows_task_info(task_names)
    expected_result = [
        {
            "task_name": "test_task1",
            "command": "start-server",
            "schedule": "One Time: 10:00:00",
        },
        {
            "task_name": "test_task2",
            "command": "backup",
            "schedule": "Daily (every 1 days)",
        },
    ]

    assert result == expected_result
    # check that subprocess was called for each task
    expected_calls = [
        call(
            ["schtasks", "/Query", "/TN", "test_task1", "/XML"],
            capture_output=True,
            text=True,
            check=True,
        ),
        call(
            ["schtasks", "/Query", "/TN", "test_task2", "/XML"],
            capture_output=True,
            text=True,
            check=True,
        ),
    ]
    mock_subprocess_run.assert_has_calls(expected_calls)


def test_get_windows_task_info_invalid_input():
    """Test with invalid input (not a list)."""
    with pytest.raises(TypeError, match="task_names must be a list"):
        windows.get_windows_task_info("not_a_list")


@patch(
    "subprocess.run",
    side_effect=subprocess.CalledProcessError(1, "schtasks", "Mocked schtasks error"),
)
def test_get_windows_task_info_schtasks_error(mock_subprocess_run):
    """Test handling an error from schtasks (other than task not found)."""
    task_names = ["test_task"]
    # Mock settings for EXPATH
    mock_settings = MagicMock()
    mock_settings.EXPATH = "C:\\path\\to\\bedrock-server-manager"
    with patch("bedrock_server_manager.core.system.windows.EXPATH", mock_settings):
        result = windows.get_windows_task_info(task_names)
    assert result == []  # empty if error


@patch("subprocess.run")
def test_get_windows_task_info_xml_parse_error(mock_subprocess_run):
    """Test handling an XML parsing error."""
    task_names = ["test_task"]
    # Mock subprocess.run to return *invalid* XML
    mock_subprocess_run.return_value.stdout = "This is not valid XML"
    mock_subprocess_run.return_value.returncode = 0  # Success
    # Mock settings for EXPATH
    mock_settings = MagicMock()
    mock_settings.EXPATH = "C:\\path\\to\\bedrock-server-manager"
    with patch("bedrock_server_manager.core.system.windows.EXPATH", mock_settings):
        result = windows.get_windows_task_info(task_names)
    assert result == []  # Should return an empty list on parsing error


@patch("subprocess.run")
def test_get_windows_task_info_no_tasks_found(mock_subprocess_run):
    """Test when no tasks are found."""
    task_names = ["nonexistent_task"]
    # Mock subprocess.run to return a non-zero exit code and error message.
    mock_subprocess_run.return_value.returncode = 1
    mock_subprocess_run.return_value.stderr = (
        "ERROR: The system cannot find the file specified."
    )
    mock_subprocess_run.return_value.stdout = ""
    # Mock settings for EXPATH
    mock_settings = MagicMock()
    mock_settings.EXPATH = "C:\\path\\to\\bedrock-server-manager"
    with patch("bedrock_server_manager.core.system.windows.EXPATH", mock_settings):
        result = windows.get_windows_task_info(task_names)
    assert result == []


# --- Tests for _get_schedule_string ---


def test_get_schedule_string_time_trigger():
    """Test extracting schedule from a TimeTrigger."""
    xml_string = """
    <Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <Triggers>
        <TimeTrigger>
          <StartBoundary>2024-01-01T10:30:00</StartBoundary>
          <Enabled>true</Enabled>
        </TimeTrigger>
      </Triggers>
    </Task>
    """
    root = ET.fromstring(xml_string)
    result = windows._get_schedule_string(root)
    assert result == "One Time: 10:30:00"


def test_get_schedule_string_daily_trigger():
    """Test extracting schedule from a Daily CalendarTrigger."""
    xml_string = """
    <Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <Triggers>
        <CalendarTrigger>
          <StartBoundary>2024-01-01T12:00:00</StartBoundary>
          <Enabled>true</Enabled>
          <ScheduleByDay>
            <DaysInterval>2</DaysInterval>
          </ScheduleByDay>
        </CalendarTrigger>
      </Triggers>
    </Task>
    """
    root = ET.fromstring(xml_string)
    result = windows._get_schedule_string(root)
    assert result == "Daily (every 2 days)"


def test_get_schedule_string_weekly_trigger():
    """Test extracting schedule from a Weekly CalendarTrigger."""
    xml_string = """
    <Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <Triggers>
        <CalendarTrigger>
          <StartBoundary>2024-01-01T14:00:00</StartBoundary>
          <Enabled>true</Enabled>
          <ScheduleByWeek>
            <WeeksInterval>1</WeeksInterval>
            <DaysOfWeek>
              <Monday />
              <Wednesday />
              <Friday />
            </DaysOfWeek>
          </ScheduleByWeek>
        </CalendarTrigger>
      </Triggers>
    </Task>
    """
    root = ET.fromstring(xml_string)
    result = windows._get_schedule_string(root)
    assert result == "Weekly (every 1 weeks on Monday, Wednesday, Friday)"


def test_get_schedule_string_monthly_trigger():
    """Test extracting schedule from a Monthly CalendarTrigger."""
    xml_string = """
    <Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <Triggers>
        <CalendarTrigger>
          <StartBoundary>2024-01-01T18:00:00</StartBoundary>
          <Enabled>true</Enabled>
          <ScheduleByMonth>
            <DaysOfMonth>
              <Day>1</Day>
              <Day>15</Day>
            </DaysOfMonth>
            <Months>
              <January />
              <July />
            </Months>
          </ScheduleByMonth>
        </CalendarTrigger>
      </Triggers>
    </Task>
    """
    root = ET.fromstring(xml_string)
    result = windows._get_schedule_string(root)
    assert result == "Monthly"  # Currently simplifies


def test_get_schedule_string_unknown_calendar_trigger():
    """Test unknown CalendarTrigger."""
    xml_string = """
    <Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <Triggers>
        <CalendarTrigger>
          <StartBoundary>2024-01-01T12:00:00</StartBoundary>
          <Enabled>true</Enabled>
          <ScheduleBySomeUnknownType>
            <SomeUnknownInterval>2</SomeUnknownInterval>
          </ScheduleBySomeUnknownType>
        </CalendarTrigger>
      </Triggers>
    </Task>
    """
    root = ET.fromstring(xml_string)
    result = windows._get_schedule_string(root)
    assert result == "CalendarTrigger (Unknown Type)"


def test_get_schedule_string_unknown_trigger():
    """Test an unknown trigger type."""
    xml_string = """
    <Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <Triggers>
        <SomeUnknownTrigger>
          <StartBoundary>2024-01-01T10:00:00</StartBoundary>
        </SomeUnknownTrigger>
      </Triggers>
    </Task>
    """
    root = ET.fromstring(xml_string)
    result = windows._get_schedule_string(root)
    assert result == "Unknown Trigger Type"


def test_get_schedule_string_no_triggers():
    """Test when there are no triggers defined."""
    xml_string = """
    <Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <NoTriggersHere>
      </NoTriggersHere>
    </Task>
    """
    root = ET.fromstring(xml_string)
    result = windows._get_schedule_string(root)
    assert result == "No Triggers"


def test_get_schedule_string_multiple_triggers():
    """Test handling of multiple triggers."""
    xml_string = """
    <Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <Triggers>
        <TimeTrigger>
          <StartBoundary>2024-01-01T10:30:00</StartBoundary>
          <Enabled>true</Enabled>
        </TimeTrigger>
        <CalendarTrigger>
          <StartBoundary>2024-01-01T12:00:00</StartBoundary>
          <Enabled>true</Enabled>
          <ScheduleByDay>
            <DaysInterval>2</DaysInterval>
          </ScheduleByDay>
        </CalendarTrigger>
      </Triggers>
    </Task>
    """
    root = ET.fromstring(xml_string)
    result = windows._get_schedule_string(root)
    assert result == "One Time: 10:30:00, Daily (every 2 days)"


# --- Tests for get_server_task_names ---


def test_get_server_task_names_success(tmp_path):
    """Test successfully retrieving task names."""
    server_name = "test_server"
    config_dir = tmp_path / "config"
    task_dir = config_dir / server_name
    task_dir.mkdir(parents=True)

    # Create some dummy XML files with task names
    def create_task_xml(task_name, file_path):
        task = ET.Element("{http://schemas.microsoft.com/windows/2004/02/mit/task}Task")
        reg_info = ET.SubElement(
            task,
            "{http://schemas.microsoft.com/windows/2004/02/mit/task}RegistrationInfo",
        )
        ET.SubElement(
            reg_info, "{http://schemas.microsoft.com/windows/2004/02/mit/task}URI"
        ).text = f"\\{task_name}"  # Add leading backslash
        tree = ET.ElementTree(task)
        tree.write(file_path, encoding="utf-16")  # Use utf-16

    create_task_xml("task1", task_dir / "task1.xml")
    create_task_xml("task2", task_dir / "task2.xml")
    create_task_xml("task3", task_dir / "task3.xml")

    # Create a non-XML file to make sure it's ignored
    (task_dir / "not_an_xml.txt").touch()

    with patch(
        "bedrock_server_manager.config.settings.CONFIG_DIR",
        str(config_dir),
    ):
        result = windows.get_server_task_names(server_name, str(config_dir))

    # Sort the results for consistent comparison (order might vary)
    result = sorted(result)
    expected_result = sorted(
        [
            ("task1", str(task_dir / "task1.xml")),
            ("task2", str(task_dir / "task2.xml")),
            ("task3", str(task_dir / "task3.xml")),
        ]
    )
    assert result == expected_result


def test_get_server_task_names_no_tasks(tmp_path):
    """Test when no task XML files are found."""
    server_name = "test_server"
    config_dir = tmp_path / "config"
    task_dir = config_dir / server_name
    task_dir.mkdir(parents=True)  # Create the directory, but no XML files

    with patch(
        "bedrock_server_manager.config.settings.CONFIG_DIR",
        str(config_dir),
    ):
        result = windows.get_server_task_names(server_name, str(config_dir))
    assert result == []  # Should return an empty list


def test_get_server_task_names_task_dir_not_found(tmp_path):
    """Test when the task directory doesn't exist."""
    server_name = "test_server"
    config_dir = tmp_path / "config"
    # Don't create the task directory

    with patch(
        "bedrock_server_manager.config.settings.CONFIG_DIR",
        str(config_dir),
    ):
        result = windows.get_server_task_names(server_name, str(config_dir))
    assert result == []


def test_get_server_task_names_xml_parse_error(tmp_path):
    """Test handling an XML parsing error."""
    server_name = "test_server"
    config_dir = tmp_path / "config"
    task_dir = config_dir / server_name
    task_dir.mkdir(parents=True)

    # Create an invalid XML file
    (task_dir / "invalid.xml").write_text("This is not valid XML")
    with patch(
        "bedrock_server_manager.config.settings.CONFIG_DIR",
        str(config_dir),
    ):
        result = windows.get_server_task_names(server_name, str(config_dir))
    # Should return empty list, as it skips
    assert result == []


@patch("os.listdir", side_effect=Exception("Mocked listdir error"))
def test_get_server_task_names_listdir_error(mock_listdir, tmp_path):
    server_name = "test_server"
    config_dir = tmp_path / "config"
    task_dir = config_dir / server_name
    task_dir.mkdir(parents=True)
    with patch(
        "bedrock_server_manager.config.settings.CONFIG_DIR",
        str(config_dir),
    ):
        with pytest.raises(TaskError, match="Error reading tasks"):
            windows.get_server_task_names(server_name, str(config_dir))


# --- Tests for create_windows_task_xml ---


def test_create_windows_task_xml_basic_structure(tmp_path):
    """Test the basic structure of the generated XML."""
    server_name = "test_server"
    command = "start-server"
    command_args = "--server test_server"
    task_name = r"\bedrock-test_server-start-server"  # Use raw string
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Mock settings for EXPATH
    mock_settings = MagicMock()
    mock_settings.EXPATH = "C:\\path\\to\\bedrock-server-manager"

    # Create a dummy trigger to pass to the function
    trigger = {
        "type": "TimeTrigger",  # This is just an example, modify as needed
        "start": "2024-01-01T10:00:00",
        "enabled": True,
    }
    triggers = [trigger]  # Put the trigger inside a list as the function expects a list

    with patch("bedrock_server_manager.core.system.windows.EXPATH", mock_settings):
        xml_file_path = windows.create_windows_task_xml(
            server_name, command, command_args, task_name, str(config_dir), triggers
        )

    # Check if the file was created (you can also inspect the XML content if needed)
    assert xml_file_path.endswith(".xml")
    assert "start-server.xml" in xml_file_path


def test_create_windows_task_xml_command_and_args(tmp_path):
    """Test that the command and arguments are correctly set."""
    server_name = "test_server"
    command = "start-server"
    command_args = "--server test_server --flag some_value"
    task_name = r"\bedrock-test_server-start-server"  # Use raw string
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create a dummy trigger to pass to the function
    trigger = {
        "type": "TimeTrigger",  # This is just an example, modify as needed
        "start": "2024-01-01T10:00:00",
        "enabled": True,
    }
    triggers = [trigger]  # Put the trigger inside a list as the function expects a list

    with patch(
        "bedrock_server_manager.core.system.windows.EXPATH",
        "C:\\path\\to\\bedrock-server-manager",
    ):
        xml_file_path = windows.create_windows_task_xml(
            server_name, command, command_args, task_name, str(config_dir), triggers
        )

    tree = ET.parse(xml_file_path)
    root = tree.getroot()
    actions = root.find(
        ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}Actions"
    )
    exec_action = actions.find(
        ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}Exec"
    )

    command_element = exec_action.find(
        ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}Command"
    )
    arguments_element = exec_action.find(
        ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}Arguments"
    )

    assert command_element is not None
    # Ensure the correct mocked path is used
    assert (
        command_element.text == "C:\\path\\to\\bedrock-server-manager"
    )  # Check mocked path


def test_create_windows_task_xml_existing_triggers(tmp_path):
    """Test including existing triggers."""
    server_name = "test_server"
    command = "start-server"
    command_args = "--server test_server"
    task_name = r"\bedrock-test_server-start-server"  # raw string
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    # Mock settings for EXPATH
    mock_settings = MagicMock()
    mock_settings.EXPATH = "C:\\path\\to\\bedrock-server-manager"

    # Create a dummy existing trigger
    existing_triggers = [
        {"type": "TimeTrigger", "start": "2023-01-01T00:00:00", "enabled": True},
        {"type": "Daily", "start": "2023-01-02T12:00:00", "interval": 2},
    ]

    with patch("bedrock_server_manager.core.system.windows.EXPATH", mock_settings):
        with patch(
            "bedrock_server_manager.core.system.windows.add_trigger"
        ) as mock_add_trigger:
            xml_file_path = windows.create_windows_task_xml(
                server_name,
                command,
                command_args,
                task_name,
                str(config_dir),
                existing_triggers,
            )

    assert os.path.exists(xml_file_path)
    assert mock_add_trigger.call_count == len(existing_triggers)
    mock_add_trigger.assert_has_calls(
        [call(ANY, existing_triggers[0]), call(ANY, existing_triggers[1])],
        any_order=False,
    )  # Check calls to see if in order


# @patch("bedrock_server_manager.core.system.windows._get_trigger_info")
@patch("builtins.open", side_effect=OSError("Mocked write error"))
def test_create_windows_task_xml_file_write_error(mock_open, tmp_path):
    """Test handling a file write error."""
    server_name = "test_server"
    command = "start-server"
    command_args = "--server test_server"
    task_name = r"\bedrock-test_server-start-server"  # Use raw string
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    # Create a dummy trigger to pass to the function
    trigger = {
        "type": "TimeTrigger",  # This is just an example, modify as needed
        "start": "2024-01-01T10:00:00",
        "enabled": True,
    }
    triggers = [trigger]  # Put the trigger inside a list as the function expects a list
    with patch("bedrock_server_manager.core.system.windows.EXPATH", "test_expath"):
        with pytest.raises(TaskError, match="Error writing XML file"):
            windows.create_windows_task_xml(
                server_name, command, command_args, task_name, str(config_dir), triggers
            )


# --- Tests for import_task_xml ---


@patch("subprocess.run")
def test_import_task_xml_success(mock_subprocess_run, tmp_path):
    """Test successful import of a task XML."""
    xml_file_path = tmp_path / "test_task.xml"
    xml_file_path.touch()  # Create a dummy XML file
    task_name = "TestTask"

    # Mock subprocess.run to simulate success
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stdout = (
        "SUCCESS: The scheduled task was created successfully."
    )
    mock_subprocess_run.return_value.stderr = ""

    windows.import_task_xml(str(xml_file_path), task_name)

    # Check that subprocess.run was called with the correct arguments
    mock_subprocess_run.assert_called_once_with(
        ["schtasks", "/Create", "/TN", task_name, "/XML", str(xml_file_path), "/F"],
        check=True,
        capture_output=True,
        text=True,
    )


def test_import_task_xml_missing_xml_file(tmp_path):
    """Test with a missing XML file."""
    xml_file_path = tmp_path / "nonexistent.xml"  # Doesn't exist
    task_name = "TestTask"

    with pytest.raises(FileOperationError, match="XML file not found"):
        windows.import_task_xml(str(xml_file_path), task_name)


def test_import_task_xml_missing_task_name():
    """Test with a missing task_name."""
    xml_file_path = "some_file.xml"  # Doesn't matter for this test

    with pytest.raises(MissingArgumentError, match="Task name is empty"):
        windows.import_task_xml(xml_file_path, "")


@patch(
    "subprocess.run",
    side_effect=subprocess.CalledProcessError(1, "schtasks", "Mocked schtasks error"),
)
def test_import_task_xml_schtasks_error(mock_subprocess_run, tmp_path):
    """Test handling an error from schtasks."""
    xml_file_path = tmp_path / "test_task.xml"
    xml_file_path.touch()
    task_name = "TestTask"

    with pytest.raises(TaskError, match="Failed to import task"):
        windows.import_task_xml(str(xml_file_path), task_name)


@patch("subprocess.run", side_effect=Exception("Mocked unexpected error"))
def test_import_task_xml_unexpected_error(mock_subprocess_run, tmp_path):
    """Test handling an unexpected error."""
    xml_file_path = tmp_path / "test_task.xml"
    xml_file_path.touch()
    task_name = "TestTask"

    with pytest.raises(TaskError, match="An unexpected error occurred while importing"):
        windows.import_task_xml(str(xml_file_path), task_name)


# --- Tests for _get_day_element_name ---


def test_get_day_element_name_valid_short():
    """Test valid short day names."""
    assert windows._get_day_element_name("Mon") == "Monday"
    assert windows._get_day_element_name("tue") == "Tuesday"
    assert windows._get_day_element_name("Wed") == "Wednesday"


def test_get_day_element_name_valid_long():
    """Test valid long day names."""
    assert windows._get_day_element_name("friday") == "Friday"
    assert windows._get_day_element_name("Saturday") == "Saturday"
    assert windows._get_day_element_name("sunday") == "Sunday"


def test_get_day_element_name_valid_number():
    """Test valid day numbers."""
    assert windows._get_day_element_name("1") == "Monday"
    assert windows._get_day_element_name(2) == "Tuesday"
    assert windows._get_day_element_name(7) == "Sunday"


def test_get_day_element_name_invalid():
    """Test invalid day inputs."""
    with pytest.raises(TaskError, match="Invalid day of week input"):
        windows._get_day_element_name("invalid")
    with pytest.raises(TaskError, match="Invalid day of week input"):
        windows._get_day_element_name(0)
    with pytest.raises(TaskError, match="Invalid day of week input"):
        windows._get_day_element_name(8)
    with pytest.raises(TaskError, match="Invalid day of week input"):
        windows._get_day_element_name("Mondays")  # close but not correct


# --- Tests for _get_month_element_name ---


def test_get_month_element_name_valid_short():
    """Test valid short month names."""
    assert windows._get_month_element_name("Jan") == "January"
    assert windows._get_month_element_name("feb") == "February"
    assert windows._get_month_element_name("MAR") == "March"


def test_get_month_element_name_valid_long():
    """Test valid long month names."""
    assert windows._get_month_element_name("April") == "April"
    assert windows._get_month_element_name("august") == "August"
    assert windows._get_month_element_name("december") == "December"


def test_get_month_element_name_valid_number():
    """Test valid month numbers."""
    assert windows._get_month_element_name("1") == "January"
    assert windows._get_month_element_name(5) == "May"
    assert windows._get_month_element_name(12) == "December"


def test_get_month_element_name_invalid():
    """Test invalid month inputs."""
    with pytest.raises(TaskError, match="Invalid month input"):
        windows._get_month_element_name("invalid")
    with pytest.raises(TaskError, match="Invalid month input"):
        windows._get_month_element_name(0)
    with pytest.raises(TaskError, match="Invalid month input"):
        windows._get_month_element_name(13)
    with pytest.raises(TaskError, match="Invalid month input"):
        windows._get_month_element_name("Janu")  # close but not correct


# Continuing in tests/core/system/test_windows.py

# --- Tests for add_trigger ---


def test_add_trigger_time_trigger():
    """Test adding a TimeTrigger."""
    triggers_element = ET.Element("Triggers")
    trigger_data = {
        "type": "TimeTrigger",
        "start": "2024-05-15T09:00:00",
        "enabled": True,
    }
    windows.add_trigger(triggers_element, trigger_data)

    assert len(triggers_element) == 1
    time_trigger = triggers_element.find("TimeTrigger")
    assert time_trigger is not None
    assert time_trigger.find("StartBoundary").text == "2024-05-15T09:00:00"
    assert time_trigger.find("Enabled").text == "true"


def test_add_trigger_daily():
    """Test adding a Daily trigger."""
    triggers_element = ET.Element("Triggers")
    trigger_data = {
        "type": "Daily",
        "start": "2024-05-15T10:00:00",
        "interval": 3,
        "enabled": True,
    }
    windows.add_trigger(triggers_element, trigger_data)

    assert len(triggers_element) == 1
    calendar_trigger = triggers_element.find("CalendarTrigger")
    assert calendar_trigger is not None
    assert calendar_trigger.find("StartBoundary").text == "2024-05-15T10:00:00"
    assert calendar_trigger.find("Enabled").text == "true"
    schedule_by_day = calendar_trigger.find("ScheduleByDay")
    assert schedule_by_day is not None
    assert schedule_by_day.find("DaysInterval").text == "3"


def test_add_trigger_weekly():
    """Test adding a Weekly trigger."""
    triggers_element = ET.Element("Triggers")
    trigger_data = {
        "type": "Weekly",
        "start": "2024-05-15T11:00:00",
        "days": ["mon", "wed", "Fri"],
        "interval": 2,
        "enabled": True,
    }
    windows.add_trigger(triggers_element, trigger_data)

    assert len(triggers_element) == 1
    calendar_trigger = triggers_element.find("CalendarTrigger")
    assert calendar_trigger is not None
    assert calendar_trigger.find("StartBoundary").text == "2024-05-15T11:00:00"
    schedule_by_week = calendar_trigger.find("ScheduleByWeek")
    assert schedule_by_week is not None
    assert schedule_by_week.find("WeeksInterval").text == "2"
    days_of_week = schedule_by_week.find("DaysOfWeek")
    assert days_of_week is not None
    assert len(days_of_week) == 3
    assert days_of_week.find("Monday") is not None
    assert days_of_week.find("Wednesday") is not None
    assert days_of_week.find("Friday") is not None


def test_add_trigger_monthly():
    """Test adding a Monthly trigger."""
    triggers_element = ET.Element("Triggers")
    trigger_data = {
        "type": "Monthly",
        "start": "2024-05-15T12:00:00",
        "days": ["1", "15", "31"],
        "months": ["jan", "July", "DEC"],
        "enabled": True,
    }
    windows.add_trigger(triggers_element, trigger_data)

    assert len(triggers_element) == 1
    calendar_trigger = triggers_element.find("CalendarTrigger")
    assert calendar_trigger is not None
    assert calendar_trigger.find("StartBoundary").text == "2024-05-15T12:00:00"
    schedule_by_month = calendar_trigger.find("ScheduleByMonth")
    assert schedule_by_month is not None
    days_of_month = schedule_by_month.find("DaysOfMonth")
    assert days_of_month is not None
    assert len(days_of_month) == 3
    assert days_of_month.findall("Day")[0].text == "1"
    assert days_of_month.findall("Day")[1].text == "15"
    assert days_of_month.findall("Day")[2].text == "31"
    months = schedule_by_month.find("Months")
    assert months is not None
    assert len(months) == 3
    assert months.find("January") is not None
    assert months.find("July") is not None
    assert months.find("December") is not None


def test_add_trigger_invalid_type():
    """Test with an invalid trigger type."""
    triggers_element = ET.Element("Triggers")
    trigger_data = {"type": "InvalidType", "start": "2024-05-15T13:00:00"}
    with pytest.raises(InvalidInputError, match="Unknown trigger type"):
        windows.add_trigger(triggers_element, trigger_data)


def test_add_trigger_missing_required_fields():
    """Test missing required fields for different trigger types."""
    triggers_element = ET.Element("Triggers")

    # Missing 'start' for all trigger types
    with pytest.raises(KeyError):
        windows.add_trigger(triggers_element, {"type": "TimeTrigger"})

    # Missing 'interval' for Daily
    with pytest.raises(KeyError):
        windows.add_trigger(
            triggers_element, {"type": "Daily", "start": "2024-05-15T14:00:00"}
        )

    # Missing 'days' or 'interval' for Weekly
    with pytest.raises(KeyError):
        windows.add_trigger(
            triggers_element, {"type": "Weekly", "start": "2024-05-15T15:00:00"}
        )

    # Missing 'days' or 'months' for Monthly
    with pytest.raises(KeyError):
        windows.add_trigger(
            triggers_element, {"type": "Monthly", "start": "2024-05-15T16:00:00"}
        )


# --- Tests for delete_task ---


@patch("subprocess.run")
def test_delete_task_success(mock_subprocess_run):
    """Test successful deletion of a task."""
    task_name = "TestTask"

    # Mock subprocess.run to simulate success
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stdout = (
        'SUCCESS: The scheduled task "TestTask" was successfully deleted.'
    )
    mock_subprocess_run.return_value.stderr = ""

    windows.delete_task(task_name)

    # Check that subprocess.run was called with the correct arguments
    mock_subprocess_run.assert_called_once_with(
        ["schtasks", "/Delete", "/TN", task_name, "/F"],
        check=True,
        capture_output=True,
        text=True,
    )


def test_delete_task_missing_task_name():
    """Test with a missing task_name."""
    with pytest.raises(MissingArgumentError, match="task_name is empty"):
        windows.delete_task("")


@patch(
    "subprocess.run",
    side_effect=subprocess.CalledProcessError(
        1, "schtasks", stderr="ERROR: The specified task name does not exist."
    ),
)
def test_delete_task_task_not_found(mock_subprocess_run):
    """Test when the task is not found (schtasks returns an error)."""
    task_name = "NonExistentTask"
    # Should not raise exception
    windows.delete_task(task_name)
    mock_subprocess_run.assert_called_once()


@patch(
    "subprocess.run",
    side_effect=subprocess.CalledProcessError(
        1, "schtasks", stderr="Mocked schtasks error"
    ),
)
def test_delete_task_schtasks_error(mock_subprocess_run):
    """Test handling a generic error from schtasks."""
    task_name = "TestTask"

    with pytest.raises(TaskError, match="Failed to delete task"):
        windows.delete_task(task_name)


@patch("subprocess.run", side_effect=Exception("Mocked unexpected error"))
def test_delete_task_unexpected_error(mock_subprocess_run):
    """Test handling an unexpected error."""
    task_name = "TestTask"

    with pytest.raises(
        TaskError, match="An unexpected error occurred while deleting task"
    ):
        windows.delete_task(task_name)
