"""External tool dependency checker."""

import shutil

from batuta.exceptions import ToolNotFoundError

# Install hints for required tools
TOOL_INSTALL_HINTS: dict[str, str] = {
    "adb": "https://developer.android.com/tools/releases/platform-tools",
    "apktool": "https://apktool.ibotpeaches.com/",
    "jadx": "https://github.com/skylot/jadx",
    "APKEditor": "https://github.com/REAndroid/APKEditor",
    "zipalign": "Part of Android SDK build-tools (set ANDROID_HOME)",
    "apksigner": "Part of Android SDK build-tools (set ANDROID_HOME)",
    "keytool": "Part of Java JDK (install JDK and ensure it's on PATH)",
}


def check_tool(tool: str) -> bool:
    """Check if a tool is available on PATH.

    Args:
        tool: Name of the tool to check.

    Returns:
        True if the tool is found, False otherwise.
    """
    return shutil.which(tool) is not None


def require(*tools: str) -> None:
    """Require that all specified tools are available.

    Args:
        *tools: Names of tools that must be available.

    Raises:
        ToolNotFoundError: If any tool is not found.
    """
    for tool in tools:
        if not check_tool(tool):
            raise ToolNotFoundError(tool, TOOL_INSTALL_HINTS.get(tool))


def get_tool_path(tool: str) -> str:
    """Get the full path to a tool.

    Args:
        tool: Name of the tool.

    Returns:
        Full path to the tool executable.

    Raises:
        ToolNotFoundError: If the tool is not found.
    """
    path = shutil.which(tool)
    if path is None:
        raise ToolNotFoundError(tool, TOOL_INSTALL_HINTS.get(tool))
    return path
