"""Pydantic models for APK analysis results."""

from pathlib import Path

from pydantic import BaseModel


class FrameworkMatch(BaseModel):
    """A detected framework with evidence."""

    name: str
    """Framework name (e.g., 'Flutter', 'React Native')."""

    matched_files: list[str]
    """Files/paths that matched the framework signature."""


class FrameworkResult(BaseModel):
    """Result of framework detection analysis."""

    apk_path: Path
    """Path to the analyzed APK."""

    detected_frameworks: list[FrameworkMatch]
    """List of detected frameworks with matched evidence."""

    native_libraries: list[str]
    """All native libraries (.so files) found in the APK."""
