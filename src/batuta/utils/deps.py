"""External tool dependency checker."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Final

from batuta.exceptions import ToolNotFoundError
from batuta.utils.config import get_config_value

# Install hints for required tools
TOOL_INSTALL_HINTS: dict[str, str] = {
    "adb": "https://developer.android.com/tools/releases/platform-tools",
    "apktool": "https://apktool.ibotpeaches.com/",
    "jadx": "https://github.com/skylot/jadx",
    "APKEditor": (
        "https://github.com/REAndroid/APKEditor — set APKEDITOR_JAR, "
        "configure ~/.batuta/config.json, or add wrapper script to PATH"
    ),
    "zipalign": "Part of Android SDK build-tools (set ANDROID_HOME)",
    "apksigner": "Part of Android SDK build-tools (set ANDROID_HOME)",
    "keytool": "Part of Java JDK (install JDK and ensure it's on PATH)",
}

APKEDITOR_ENV_VAR: Final[str] = "APKEDITOR_JAR"
APKEDITOR_CONFIG_KEY: Final[str] = "apkeditor_path"
APKEDITOR_JAR_NAME: Final[str] = "APKEditor.jar"


def check_tool(tool: str) -> bool:
    """Check if a tool is available on PATH or via configuration."""

    if tool == "APKEditor":
        return get_apkeditor_command() is not None

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


def _resolve_jar_path(raw_value: str | None) -> Path | None:
    if not raw_value:
        return None

    candidate = Path(raw_value).expanduser()
    if candidate.is_file():
        return candidate

    if candidate.is_dir():
        jar_candidate = candidate / APKEDITOR_JAR_NAME
        if jar_candidate.is_file():
            return jar_candidate

    return None


def get_apkeditor_command() -> list[str] | None:
    """Resolve the APKEditor command via env/config/PATH."""

    jar_path = _resolve_jar_path(os.environ.get(APKEDITOR_ENV_VAR))
    if jar_path is None:
        cfg_value = get_config_value(APKEDITOR_CONFIG_KEY)
        jar_path = _resolve_jar_path(cfg_value if isinstance(cfg_value, str) else None)

    if jar_path is not None:
        return ["java", "-jar", str(jar_path)]

    wrapper = shutil.which("APKEditor")
    if wrapper:
        return [wrapper]

    return None
