# bedrock-server-manager/bedrock_server_manager/core/error.py
class BedrockManagerError(Exception):
    """Base class for all custom exceptions in this project."""

    pass


class MissingArgumentError(BedrockManagerError):
    """Raised when a required argument is missing."""

    pass


class MissingPackagesError(BedrockManagerError):
    """Raised when required packages are missing."""

    pass


class InvalidInputError(BedrockManagerError):
    """Raised when the input is invalid."""

    pass


class ValueError(BedrockManagerError):
    """Raised when the input is invalid."""

    pass


class ServerNotFoundError(BedrockManagerError):
    """Raised when the server executable is not found."""

    def __init__(self, server_path, message="Server executable not found."):
        self.server_path = server_path
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message}: {self.server_path}"


class ServerNotRunningError(BedrockManagerError):
    """Raised when an operation requires the server to be running, but it's not."""

    pass


class InstallUpdateError(BedrockManagerError):
    pass


class ServerStartError(BedrockManagerError):
    pass


class ServerStopError(BedrockManagerError):
    pass


class ConfigError(BedrockManagerError):
    pass


class ServiceError(BedrockManagerError):
    pass


class DownloadExtractError(BedrockManagerError):
    pass


class AddonExtractError(BedrockManagerError):
    pass


class DirectoryError(BedrockManagerError):
    pass


class SendCommandError(BedrockManagerError):
    pass


class AttachConsoleError(BedrockManagerError):
    pass


class BackupWorldError(BedrockManagerError):
    pass


class DeleteServerError(BedrockManagerError):
    pass


class ScheduleError(BedrockManagerError):
    pass


class ResourceMonitorError(BedrockManagerError):
    pass


class InternetConnectivityError(BedrockManagerError):
    pass


class InvalidServerNameError(BedrockManagerError):
    pass


class InvalidCronJobError(BedrockManagerError):
    pass


class InvalidAddonPackTypeError(BedrockManagerError):
    pass


class TypeError(BedrockManagerError):
    pass


class FileOperationError(BedrockManagerError):
    pass


class BackupConfigError(BedrockManagerError):
    pass


class RestoreError(BedrockManagerError):
    pass


class TaskError(BedrockManagerError):
    pass


class UpdateError(BedrockManagerError):
    pass


class PlayerDataError(BedrockManagerError):
    """Raised when the input is invalid."""

    pass


class DownloadError(BedrockManagerError):
    """Raised when the input is invalid."""

    pass


class FileNotFoundError(BedrockManagerError):
    """Raised when a file path is invalid."""

    pass


# Linux-specific
class SystemdReloadError(BedrockManagerError):
    pass


class CommandNotFoundError(BedrockManagerError):
    def __init__(self, command_name, message="Command not found"):
        self.command_name = command_name
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message}: {self.command_name}"


class SetFolderPermissionsError(BedrockManagerError):
    pass


# Windows-specific
class WindowsStartServerError(BedrockManagerError):  # More specific names
    pass


class WindowsStopServerError(BedrockManagerError):
    pass


class WindowsSetFolderPermissionsError(BedrockManagerError):
    pass


class UserExitError(BedrockManagerError):
    pass
