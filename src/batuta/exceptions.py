"""Typed exception hierarchy for batuta."""


class BatutaError(Exception):
    """Base exception for all batuta errors."""

    pass


class ToolNotFoundError(BatutaError):
    """Raised when a required external tool is not installed."""

    def __init__(self, tool: str, install_hint: str | None = None):
        self.tool = tool
        self.install_hint = install_hint
        message = f"Required tool not found: {tool}"
        if install_hint:
            message += f"\nInstall: {install_hint}"
        super().__init__(message)


class ADBError(BatutaError):
    """Raised when an ADB command fails."""

    pass


class DeviceNotFoundError(ADBError):
    """Raised when no device is connected or specified device not found."""

    pass


class PackageNotFoundError(ADBError):
    """Raised when a package is not found on the device."""

    def __init__(self, query: str):
        self.query = query
        super().__init__(f"No package found matching: {query}")


class MultiplePackagesFoundError(ADBError):
    """Raised when multiple packages match a query and user must choose."""

    def __init__(self, query: str, packages: list[str]):
        self.query = query
        self.packages = packages
        super().__init__(
            f"Multiple packages match '{query}': {len(packages)} found. "
            "Use --select to choose interactively or provide a more specific query."
        )


class APKPullError(ADBError):
    """Raised when pulling an APK from device fails."""

    pass


class ProcessError(BatutaError):
    """Raised when a subprocess command fails."""

    def __init__(self, command: list[str], returncode: int, stderr: str):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        cmd_str = " ".join(command)
        super().__init__(f"Command failed (exit {returncode}): {cmd_str}\n{stderr}")


class APKBuildError(BatutaError):
    """Raised when APK building with apktool fails."""

    pass


class APKAlignError(BatutaError):
    """Raised when APK alignment with zipalign fails."""

    pass


class APKSignError(BatutaError):
    """Raised when APK signing fails."""

    pass
