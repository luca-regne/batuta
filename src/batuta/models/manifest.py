"""Pydantic models for AndroidManifest.xml analysis."""

from pathlib import Path

from pydantic import BaseModel, computed_field

from batuta.models.apk import AppMetadata


class IntentFilter(BaseModel):
    """Intent filter declaration."""

    actions: list[str] = []
    """Action strings (e.g., android.intent.action.MAIN)."""

    categories: list[str] = []
    """Category strings (e.g., android.intent.category.LAUNCHER)."""


class PathPermission(BaseModel):
    """Path-specific permission for content providers."""

    path: str | None = None
    """Exact path match."""

    path_prefix: str | None = None
    """Path prefix match."""

    path_pattern: str | None = None
    """Path pattern match (regex-like)."""

    read_permission: str | None = None
    """Permission required to read this path."""

    write_permission: str | None = None
    """Permission required to write to this path."""


class ComponentInfo(BaseModel):
    """Base model for Android components.

    Includes activities, services, receivers, and providers.
    """

    name: str
    """Component name (short form like .MainActivity or fully qualified)."""

    exported: bool | None = None
    """Exported attribute value. None if not explicitly set."""

    permission: str | None = None
    """Permission required to access this component."""

    intent_filters: list[IntentFilter] = []
    """Intent filters declared for this component."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effectively_exported(self) -> bool:
        """Computed: whether this component is accessible from other apps.

        Logic:
        - exported=True → True
        - exported=False → False
        - exported=None + has intent-filters → True (Android pre-API-31 default)
        - exported=None + no intent-filters → False
        """
        if self.exported is not None:
            return self.exported
        return len(self.intent_filters) > 0


class ActivityInfo(ComponentInfo):
    """Activity component information."""

    launch_mode: str | None = None
    """Launch mode (standard, singleTop, singleTask, singleInstance)."""

    task_affinity: str | None = None
    """Task affinity for the activity."""


class ServiceInfo(ComponentInfo):
    """Service component information."""

    pass


class ReceiverInfo(ComponentInfo):
    """Broadcast receiver component information."""

    pass


class ProviderInfo(ComponentInfo):
    """Content provider component information."""

    authorities: str | None = None
    """Content provider authorities (URI)."""

    read_permission: str | None = None
    """Permission required to read from this provider."""

    write_permission: str | None = None
    """Permission required to write to this provider."""

    grant_uri_permissions: bool = False
    """Whether this provider grants URI permissions."""

    grant_uri_permission_paths: list[str] = []
    """Specific paths that grant URI permissions."""

    path_permissions: list[PathPermission] = []
    """Path-specific permissions."""


class AttackSurface(BaseModel):
    """Summary of the application's attack surface."""

    total_activities: int = 0
    """Total number of activities."""

    total_services: int = 0
    """Total number of services."""

    total_receivers: int = 0
    """Total number of broadcast receivers."""

    total_providers: int = 0
    """Total number of content providers."""

    exported_activities: int = 0
    """Number of exported activities."""

    exported_services: int = 0
    """Number of exported services."""

    exported_receivers: int = 0
    """Number of exported receivers."""

    exported_providers: int = 0
    """Number of exported providers."""

    unprotected_exported: int = 0
    """Number of exported components without permission protection."""

    debuggable: bool = False
    """Whether the app is debuggable."""

    backup_enabled: bool = False
    """Whether backup is allowed."""

    cleartext_traffic: bool = False
    """Whether cleartext network traffic is allowed."""

    grant_uri_providers: int = 0
    """Number of providers that grant URI permissions."""


class ManifestInfo(AppMetadata):
    """Manifest-level application information."""

    debuggable: bool = False
    """Whether android:debuggable is true."""

    allow_backup: bool = True
    """Whether android:allowBackup is true (default true in Android)."""

    uses_cleartext_traffic: bool = True
    """Whether android:usesCleartextTraffic is true (default true pre-API 28)."""

    network_security_config: bool = False
    """Whether android:networkSecurityConfig is present."""

    permissions: list[str] = []
    """Permissions declared by this app (<permission>)."""

    uses_permissions: list[str] = []
    """Permissions requested by this app (<uses-permission>)."""


class ManifestResult(BaseModel):
    """Complete result of AndroidManifest.xml analysis."""

    apk_path: Path
    """Path to the analyzed APK."""

    info: ManifestInfo
    """General manifest information."""

    activities: list[ActivityInfo] = []
    """All activities declared in the manifest."""

    services: list[ServiceInfo] = []
    """All services declared in the manifest."""

    receivers: list[ReceiverInfo] = []
    """All broadcast receivers declared in the manifest."""

    providers: list[ProviderInfo] = []
    """All content providers declared in the manifest."""

    attack_surface: AttackSurface
    """Attack surface summary."""
