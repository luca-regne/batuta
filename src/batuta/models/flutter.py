"""Pydantic models for Flutter instrumentation results."""

from pathlib import Path

from pydantic import BaseModel


class FlutterPatchResult(BaseModel):
    """Result of reflutter patching operation."""

    package_name: str
    """Package name of the patched app."""

    original_apk: Path
    """Path to original APK."""

    patched_apk: Path
    """Path to reflutter-patched APK (release.RE.apk)."""

    signed_apk: Path
    """Path to signed, installable APK."""

    installed: bool = False
    """Whether the patched APK was installed on device."""

    dump_result: DumpResult | None = None
    """Result of Dart code dump (if performed)."""


class DumpResult(BaseModel):
    """Result of Dart code dump operation."""

    package_name: str
    """Package being dumped."""

    dump_path: Path
    """Path to dump.dart file."""

    formatted_path: Path | None = None
    """Path to formatted JSON (if formatting succeeded)."""

    success: bool
    """Whether dump succeeded."""

    auto_started: bool = False
    """Whether app was auto-started via monkey."""
