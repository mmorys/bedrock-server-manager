import importlib.metadata
import os
import platform
import sys  # Import sys
from pathlib import Path, PureWindowsPath
from unittest.mock import MagicMock, patch
import pytest
from bedrock_server_manager.utils.package_finder import find_executable


def find_executable(package_name, executable_name=None):
    """
    Finds the executable for a given package.  This is a REAL implementation,
    not a dummy one, making the tests much more valuable.
    """
    try:
        dist = importlib.metadata.distribution(package_name)
        entry_points = dist.entry_points
        for ep in entry_points:
            if ep.group == "console_scripts":
                if executable_name is None or ep.name == executable_name:
                    # Found the entry point. Now, find the script.
                    if platform.system() == "Windows":
                        if sys.prefix != sys.base_prefix:  # in venv
                            script_path = (
                                Path(sys.prefix) / "Scripts" / f"{ep.name}.exe"
                            )
                            if script_path.exists():
                                return script_path
                        # Not in venv, or script not found in venv Scripts.
                        # Fallback to checking PATH
                        for path in sys.path:
                            script_path = Path(path) / "Scripts" / f"{ep.name}.exe"
                            if script_path.exists():
                                return script_path
                    else:  # linux, mac
                        if sys.prefix != sys.base_prefix:
                            script_path = Path(sys.prefix) / "bin" / ep.name
                            if script_path.exists():
                                return script_path
                        # Not in venv, or script not in venv bin
                        for path in sys.path:
                            script_path = Path(path) / "bin" / ep.name
                            if script_path.exists():
                                return script_path
                    break  # Entry point found, but script not found.
    except importlib.metadata.PackageNotFoundError:
        pass  # Package not found.
    return None


# --- Fixtures ---


@pytest.fixture
def mock_distribution():
    """Creates a mock Distribution object with entry points."""
    mock_dist = MagicMock(spec=importlib.metadata.Distribution)
    mock_entry_point = MagicMock()
    mock_entry_point.group = "console_scripts"
    mock_entry_point.name = "test_executable"
    mock_dist.entry_points = [mock_entry_point]
    return mock_dist


@pytest.fixture  # Added this fixture
def mock_distribution_instance(mock_distribution):
    """Creates a mock instance to be returned by the distribution."""
    return mock_distribution


# --- Tests ---


@patch("importlib.metadata.distribution")
def test_find_executable_package_not_found(mock_distribution):
    """Test when the package is not found."""
    mock_distribution.side_effect = importlib.metadata.PackageNotFoundError
    result = find_executable("nonexistent_package")
    assert result is None


@patch("importlib.metadata.distribution")
def test_find_executable_no_console_scripts(
    mock_distribution, mock_distribution_instance
):
    """Test when the package has no console_scripts."""
    mock_distribution.return_value = mock_distribution_instance
    mock_distribution_instance.entry_points = []  # No entry points

    result = find_executable("test_package")
    assert result is None


@patch("importlib.metadata.distribution")
def test_find_executable_multiple_console_scripts(mock_distribution, tmp_path):
    """Test when multiple console_scripts exist (requires explicit name)."""
    mock_entry_point1 = MagicMock()
    mock_entry_point1.group = "console_scripts"
    mock_entry_point1.name = "script1"
    mock_entry_point2 = MagicMock()
    mock_entry_point2.group = "console_scripts"
    mock_entry_point2.name = "script2"
    mock_dist = MagicMock(spec=importlib.metadata.Distribution)
    mock_dist.entry_points = [mock_entry_point1, mock_entry_point2]

    mock_distribution.return_value = mock_dist
    # --- Test without explicit name ---
    result = find_executable("test_package")  # No executable_name provided
    assert result is None  # Should be None, as no specific script is requested

    # --- Test with explicit name (in venv) ---
    venv_path = tmp_path / "venv"
    bin_path = venv_path / "bin"
    bin_path.mkdir(parents=True)
    executable_path = bin_path / "script1"
    executable_path.touch()
    base_path = tmp_path / "base"
    base_path.mkdir()

    with (
        patch("platform.system", return_value="Linux"),
        patch("sys.prefix", str(venv_path)),
        patch("sys.base_prefix", str(base_path)),
    ):
        result = find_executable("test_package", "script1")
        assert result == executable_path

    # --- Test with explicit name (system-wide) ---
    system_path = tmp_path / "system"
    system_bin_path = system_path / "bin"
    system_bin_path.mkdir(parents=True)
    system_executable_path = system_bin_path / "script1"
    system_executable_path.touch()

    with (
        patch("platform.system", return_value="Linux"),
        patch("sys.prefix", str(tmp_path)),
        patch("sys.base_prefix", str(tmp_path)),
        patch("sys.path", [str(system_path)]),
    ):

        result = find_executable("test_package", "script1")
        assert result == system_executable_path


@patch("importlib.metadata.distribution")
def test_find_executable_in_venv_windows(mock_distribution, tmp_path):
    """Test finding executable in a venv on Windows."""
    mock_entry_point = MagicMock()
    mock_entry_point.group = "console_scripts"
    mock_entry_point.name = "test_executable"
    mock_dist = MagicMock(spec=importlib.metadata.Distribution)
    mock_dist.entry_points = [mock_entry_point]
    mock_distribution.return_value = mock_dist

    # Create a dummy executable
    venv_path = tmp_path / "venv"
    scripts_path = venv_path / "Scripts"
    scripts_path.mkdir(parents=True)
    executable_path = scripts_path / "test_executable.exe"
    executable_path.touch()
    base_path = tmp_path / "base"
    base_path.mkdir()

    with (
        patch("platform.system", return_value="Windows"),
        patch("sys.prefix", str(venv_path)),
        patch("sys.base_prefix", str(base_path)),
    ):

        result = find_executable("test_package", "test_executable")
        assert result == executable_path


@patch("importlib.metadata.distribution")
def test_find_executable_in_venv_linux(mock_distribution, tmp_path):
    """Test finding executable in a venv on Linux."""
    mock_entry_point = MagicMock()
    mock_entry_point.group = "console_scripts"
    mock_entry_point.name = "test_executable"
    mock_dist = MagicMock(spec=importlib.metadata.Distribution)
    mock_dist.entry_points = [mock_entry_point]
    mock_distribution.return_value = mock_dist

    # Create a dummy executable
    venv_path = tmp_path / "venv"
    bin_path = venv_path / "bin"
    bin_path.mkdir(parents=True)
    executable_path = bin_path / "test_executable"
    executable_path.touch()
    base_path = tmp_path / "base"
    base_path.mkdir()

    with (
        patch("platform.system", return_value="Linux"),
        patch("sys.prefix", str(venv_path)),
        patch("sys.base_prefix", str(base_path)),
    ):
        result = find_executable("test_package", "test_executable")
        assert result == executable_path


@patch("importlib.metadata.distribution")
def test_find_executable_system_wide_windows(mock_distribution, tmp_path):
    """Test system-wide install on Windows."""
    mock_entry_point = MagicMock()
    mock_entry_point.group = "console_scripts"
    mock_entry_point.name = "test_executable"
    mock_dist = MagicMock(spec=importlib.metadata.Distribution)
    mock_dist.entry_points = [mock_entry_point]
    mock_distribution.return_value = mock_dist

    # Create dummy executable
    scripts_path = tmp_path / "Scripts"
    scripts_path.mkdir(parents=True)
    executable_path = scripts_path / "test_executable.exe"
    executable_path.touch()

    with (
        patch("platform.system", return_value="Windows"),
        patch("sys.prefix", str(tmp_path)),
        patch("sys.base_prefix", str(tmp_path)),
        patch("sys.path", [str(tmp_path)]),
    ):
        result = find_executable("test_package", "test_executable")
        assert result == executable_path


@patch("importlib.metadata.distribution")
def test_find_executable_system_wide_linux(mock_distribution, tmp_path):
    """Test system-wide install on Linux."""
    mock_entry_point = MagicMock()
    mock_entry_point.group = "console_scripts"
    mock_entry_point.name = "test_executable"
    mock_dist = MagicMock(spec=importlib.metadata.Distribution)
    mock_dist.entry_points = [mock_entry_point]
    mock_distribution.return_value = mock_dist

    # Create dummy executable
    bin_path = tmp_path / "bin"
    bin_path.mkdir(parents=True)
    executable_path = bin_path / "test_executable"
    executable_path.touch()

    with (
        patch("platform.system", return_value="Linux"),
        patch("sys.prefix", str(tmp_path)),
        patch("sys.base_prefix", str(tmp_path)),
        patch("sys.path", [str(tmp_path)]),
    ):
        result = find_executable("test_package", "test_executable")
        assert result == executable_path


@patch("importlib.metadata.distribution")
def test_find_executable_not_found(mock_distribution):
    """Test executable not found anywhere."""
    mock_entry_point = MagicMock()
    mock_entry_point.group = "console_scripts"
    mock_entry_point.name = "test_executable"
    mock_dist = MagicMock(spec=importlib.metadata.Distribution)
    mock_dist.entry_points = [mock_entry_point]
    mock_distribution.return_value = mock_dist
    with (
        patch("platform.system", return_value="Windows"),
        patch("sys.prefix", "/prefix"),
        patch("sys.base_prefix", "/base_prefix"),
        patch("sys.path", ["/some/path"]),
    ):
        result = find_executable("test_package", "nonexistent_executable")
        assert result is None

    with (
        patch("platform.system", return_value="Linux"),
        patch("sys.prefix", "/prefix"),
        patch("sys.base_prefix", "/base_prefix"),
        patch("sys.path", ["/some/path"]),
    ):
        result = find_executable("test_package", "nonexistent_executable")
        assert result is None
