# bedrock_server_manager/config/const.py
import os
from importlib.metadata import version, PackageNotFoundError

# Local imports
from bedrock_server_manager.utils import package_finder

# --- Package Constants ---
package_name = "bedrock-server-manager"
executable_name = package_name
app_name_title = package_name.replace("-", " ").title()
env_name = package_name.replace("-", "_").upper()

# --- Package Information ---
EXPATH = package_finder.find_executable(package_name, executable_name)

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def get_installed_version() -> str:
    try:
        installed_version = version(package_name)
        return installed_version
    except PackageNotFoundError:
        installed_version = "0.0.0"
        return installed_version
