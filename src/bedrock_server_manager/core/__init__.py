# bedrock-server-manager/bedrock_server_manager/core/__init__.py
import os

# Determine the absolute path to the package directory
SCRIPT_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
)
