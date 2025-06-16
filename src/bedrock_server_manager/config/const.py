# bedrock_server_manager/config/const.py
"""
Defines application-wide constants and utility functions for accessing them.

This module centralizes common identifiers, names, paths, and version information
used throughout the Bedrock Server Manager application.
"""
import os
from importlib.metadata import version, PackageNotFoundError

# Local imports
from bedrock_server_manager.utils import package_finder

# --- Package Constants ---
package_name: str = "bedrock-server-manager"
"""The official package name on PyPI."""

executable_name: str = package_name
"""The name of the main executable script for the application."""

app_name_title: str = package_name.replace("-", " ").title()
"""A user-friendly, title-cased version of the application name."""

env_name: str = package_name.replace("-", "_").upper()
"""The prefix used for environment variables related to this application (e.g., BSM_PASSWORD)."""

# --- Package Information ---
EXPATH: str = package_finder.find_executable(package_name, executable_name)
"""The discovered absolute path to the main application executable."""

SCRIPT_DIR: str = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
"""The root directory of the application scripts (typically the `src` directory)."""


def get_installed_version() -> str:
    """
    Retrieves the installed version of the application package.

    Uses `importlib.metadata.version` to get the version. If the package
    is not found (e.g., in a development environment without installation),
    it defaults to "0.0.0".

    Returns:
        The installed package version string, or "0.0.0" if not found.
    """
    try:
        installed_version = version(package_name)
        return installed_version
    except PackageNotFoundError:
        installed_version = "0.0.0"
        return installed_version
