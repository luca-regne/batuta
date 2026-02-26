"""Android SDK path detection utilities."""

import os
import platform
from pathlib import Path

from batuta.exceptions import ToolNotFoundError


def get_android_home() -> Path | None:
    """Get Android SDK root directory.

    Checks environment variables and common installation locations.

    Returns:
        Path to Android SDK root, or None if not found.
    """
    for env_var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if value := os.environ.get(env_var):
            path = Path(value)
            if path.is_dir():
                return path

    system = platform.system()
    home = Path.home()

    common_locations: list[Path] = []
    if system == "Darwin":  # macOS
        common_locations = [
            home / "Library" / "Android" / "sdk",
            Path("/opt/android-sdk"),
        ]
    elif system == "Linux":
        common_locations = [
            home / "Android" / "Sdk",
            home / "android-sdk",
            Path("/opt/android-sdk"),
        ]
    elif system == "Windows":
        common_locations = [
            home / "AppData" / "Local" / "Android" / "Sdk",
            Path("C:/Android/sdk"),
        ]

    for location in common_locations:
        if location.is_dir():
            return location

    return None


def get_build_tools_path(min_version: str = "30.0.0") -> Path:
    """Get the latest Android build-tools directory.

    Args:
        min_version: Minimum required version (e.g., "30.0.0").

    Returns:
        Path to build-tools directory (e.g., .../build-tools/35.0.0/).

    Raises:
        ToolNotFoundError: If Android SDK or suitable build-tools not found.
    """
    android_home = get_android_home()
    if not android_home:
        raise ToolNotFoundError(
            "Android SDK",
            "Set ANDROID_HOME environment variable or install Android SDK",
        )

    build_tools_dir = android_home / "build-tools"
    if not build_tools_dir.is_dir():
        raise ToolNotFoundError(
            "Android build-tools",
            f"Install build-tools via Android SDK Manager in {android_home}",
        )

    # Find all version directories and sort them
    versions: list[tuple[tuple[int, ...], Path]] = []
    min_version_tuple = tuple(int(x) for x in min_version.split("."))

    for version_dir in build_tools_dir.iterdir():
        if not version_dir.is_dir():
            continue
        try:
            version_tuple = tuple(int(x) for x in version_dir.name.split("."))
            if version_tuple >= min_version_tuple:
                versions.append((version_tuple, version_dir))
        except ValueError:
            # Skip non-version directories
            continue

    if not versions:
        raise ToolNotFoundError(
            f"Android build-tools >= {min_version}",
            f"Install build-tools via Android SDK Manager in {android_home}",
        )

    # Return the latest version
    versions.sort(reverse=True)
    return versions[0][1]


def get_zipalign() -> Path:
    """Get path to zipalign binary.

    Returns:
        Path to zipalign executable.

    Raises:
        ToolNotFoundError: If zipalign not found.
    """
    build_tools = get_build_tools_path()
    zipalign = build_tools / "zipalign"

    # On Windows, add .exe extension
    if platform.system() == "Windows":
        zipalign = build_tools / "zipalign.exe"

    if not zipalign.is_file():
        raise ToolNotFoundError(
            "zipalign",
            f"Expected at {zipalign}, install via Android SDK Manager",
        )

    return zipalign


def get_apksigner() -> Path:
    """Get path to apksigner binary.

    Returns:
        Path to apksigner executable.

    Raises:
        ToolNotFoundError: If apksigner not found.
    """
    build_tools = get_build_tools_path()

    # apksigner is a wrapper script (jar on all platforms)
    if platform.system() == "Windows":
        apksigner = build_tools / "apksigner.bat"
    else:
        apksigner = build_tools / "apksigner"

    if not apksigner.is_file():
        raise ToolNotFoundError(
            "apksigner",
            f"Expected at {apksigner}, install via Android SDK Manager",
        )

    return apksigner
