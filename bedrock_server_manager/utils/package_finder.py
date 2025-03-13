# bedrock-server-manager/bedrock_server_manager/utils/package_finder.py
import importlib.metadata
import sys
import logging
import platform
from pathlib import Path
import site

logger = logging.getLogger("bedrock_server_manager")


def find_executable(package_name: str, executable_name: str = None) -> Path | None:
    """
    Dynamically finds the executable path, handling venv nuances.
    """
    try:
        distribution = importlib.metadata.distribution(package_name)
    except importlib.metadata.PackageNotFoundError:
        logger.warning(f"Package '{package_name}' not found.")
        return None

    if executable_name is None:
        entry_points = distribution.entry_points
        console_scripts = [ep for ep in entry_points if ep.group == "console_scripts"]
        if not console_scripts:
            logger.warning(f"No console_scripts found for package '{package_name}'.")
            return None
        if len(console_scripts) > 1:
            logger.warning(
                f"Multiple console_scripts for {package_name}, please specify executable_name:"
            )
            for ep in console_scripts:
                logger.info(f"  - {ep.name}")
            return None

        executable_name = console_scripts[0].name

    # --- Dynamic bin directory detection ---

    # 1. Check if we're in a virtual environment.
    if sys.prefix != sys.base_prefix:
        # We ARE in a virtual environment.
        if platform.system() == "Windows":
            bin_dir = Path(sys.prefix) / "Scripts"
        else:
            bin_dir = Path(sys.prefix) / "bin"

        executable_path = bin_dir / executable_name
        if platform.system() == "Windows":
            executable_path = bin_dir / (executable_name + ".exe")
        if executable_path.exists():
            return executable_path

    # 2. Fallback:  Handle system-wide and user installs.
    site_packages_dirs = site.getsitepackages()
    if hasattr(site, "getusersitepackages"):
        site_packages_dirs.append(site.getusersitepackages())

    for site_packages_dir_str in site_packages_dirs:
        site_packages_dir = Path(site_packages_dir_str)
        if platform.system() == "Windows":
            potential_bin_dirs = [
                site_packages_dir.parent / "Scripts",  # Same level
                site_packages_dir.parent.parent / "Scripts",  # One level up
                site_packages_dir.parent.parent.parent / "Scripts",  # Two levels up
            ]
        else:
            potential_bin_dirs = [
                site_packages_dir.parent / "bin",  # Same level
                site_packages_dir.parent.parent / "bin",  # One level up
                site_packages_dir.parent.parent.parent / "bin",  # Two levels up
            ]

        for bin_dir in potential_bin_dirs:
            executable_path = bin_dir / executable_name
            if platform.system() == "Windows":
                executable_path = bin_dir / (executable_name + ".exe")
            if executable_path.exists():
                return executable_path

    logger.error(f"Executable '{executable_name}' not found in any location.")
    return None
