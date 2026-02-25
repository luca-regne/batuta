"""Pydantic models for APK information."""

from pathlib import Path

from pydantic import BaseModel


class PackageInfo(BaseModel):
    """Basic package information from a device."""

    package_name: str
    """Full package name (e.g., com.example.app)."""

    app_name: str | None = None
    """Human-readable application name."""

    version_name: str | None = None
    """Version string (e.g., 1.0.0)."""

    version_code: int | None = None
    """Version code (e.g., 100)."""

    apk_path: str | None = None
    """Path to the base APK on device."""

    split_apks: list[str] | None = None
    """Paths to split APKs on device (if app is split)."""

    @property
    def is_split(self) -> bool:
        """Check if this is a split APK."""
        return bool(self.split_apks and len(self.split_apks) > 0)

    @property
    def all_apk_paths(self) -> list[str]:
        """Get all APK paths (base + splits)."""
        paths = []
        if self.apk_path:
            paths.append(self.apk_path)
        if self.split_apks:
            paths.extend(self.split_apks)
        return paths


class PulledAPK(BaseModel):
    """Result of pulling an APK from a device."""

    package_name: str
    """Package name of the pulled app."""

    local_path: Path
    """Local path where APK was saved."""

    is_split: bool = False
    """Whether multiple APKs were pulled."""

    split_paths: list[Path] | None = None
    """Paths to split APKs (if split)."""

    @property
    def all_paths(self) -> list[Path]:
        """Get all pulled APK paths."""
        if self.split_paths:
            return self.split_paths
        return [self.local_path]
