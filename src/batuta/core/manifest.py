"""AndroidManifest.xml parser for security analysis."""

import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from pyaxmlparser import APK

from batuta.exceptions import ManifestParseError
from batuta.models.manifest import (
    ActivityInfo,
    AttackSurface,
    IntentFilter,
    ManifestInfo,
    ManifestResult,
    PathPermission,
    ProviderInfo,
    ReceiverInfo,
    ServiceInfo,
)

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
SDK_NAMES = {
    21: "Android 5.0 (Lollipop)",
    22: "Android 5.1 (Lollipop MR1)",
    23: "Android 6.0 (Marshmallow)",
    24: "Android 7.0 (Nougat)",
    25: "Android 7.1 (Nougat MR1)",
    26: "Android 8.0 (Oreo)",
    27: "Android 8.1 (Oreo MR1)",
    28: "Android 9.0 (Pie)",
    29: "Android 10",
    30: "Android 11",
    31: "Android 12",
    32: "Android 12L",
    33: "Android 13",
    34: "Android 14",
    35: "Android 15",
}


def get_sdk_label(level: int | None) -> str:
    """Get human-readable Android version name from SDK level."""
    if level is None:
        return "Unknown"
    return SDK_NAMES.get(level, f"API {level}")


class ManifestParser:
    """Parser for AndroidManifest.xml from APK files."""

    def __init__(self, apk_path: Path):
        """Initialize parser with APK path.

        Args:
            apk_path: Path to the APK file.
        """
        self.apk_path = apk_path
        self.root: ET.Element | None = None

    def parse(self) -> ManifestResult:
        """Parse the AndroidManifest.xml and extract security-relevant information.

        Returns:
            ManifestResult with all parsed data.

        Raises:
            ManifestParseError: If parsing fails.
        """
        try:
            apk = APK(str(self.apk_path))
            manifest_xml = apk.get_android_manifest_xml()

            if not manifest_xml:
                raise ManifestParseError("Failed to extract AndroidManifest.xml")

            self.root = ET.fromstring(manifest_xml)

        except Exception as e:
            raise ManifestParseError(f"Failed to parse manifest: {e}") from e

        manifest_info = self._parse_manifest_info()
        activities = self._parse_activities()
        services = self._parse_services()
        receivers = self._parse_receivers()
        providers = self._parse_providers()

        attack_surface = self._calculate_attack_surface(
            manifest_info, activities, services, receivers, providers
        )

        return ManifestResult(
            apk_path=self.apk_path,
            info=manifest_info,
            activities=activities,
            services=services,
            receivers=receivers,
            providers=providers,
            attack_surface=attack_surface,
        )

    def _get_attr(self, element: ET.Element, attr: str) -> str | None:
        """Get Android namespaced attribute value."""
        return element.get(f"{ANDROID_NS}{attr}")

    def _parse_manifest_info(self) -> ManifestInfo:
        """Parse manifest-level information."""
        if self.root is None:
            raise ManifestParseError("Manifest not loaded")

        package = self.root.get("package", "")
        version_name = self.root.get(f"{ANDROID_NS}versionName")
        version_code_str = self.root.get(f"{ANDROID_NS}versionCode")
        version_code = int(version_code_str) if version_code_str else None

        uses_sdk = self.root.find("uses-sdk")
        min_sdk = None
        target_sdk = None
        if uses_sdk is not None:
            min_sdk_str = self._get_attr(uses_sdk, "minSdkVersion")
            target_sdk_str = self._get_attr(uses_sdk, "targetSdkVersion")
            if min_sdk_str and min_sdk_str.isdigit():
                min_sdk = int(min_sdk_str)
            if target_sdk_str and target_sdk_str.isdigit():
                target_sdk = int(target_sdk_str)
        
        app_elem = self.root.find("application")
        
        # We want to distinguish default Android values and explicitly set values, so we use None for defaults 
        debuggable = None  # Default is false
        allow_backup = None  # Default is true
        uses_cleartext_traffic = None  # Default is false
        network_security_config = False

        if app_elem is not None:
            debuggable_str = self._get_attr(app_elem, "debuggable")
            debuggable = debuggable_str == "true"

            allow_backup_str = self._get_attr(app_elem, "allowBackup")
            if allow_backup_str is not None:
                allow_backup = allow_backup_str == "true"

            cleartext_str = self._get_attr(app_elem, "usesCleartextTraffic")
            if cleartext_str is not None:
                uses_cleartext_traffic = cleartext_str == "true"

            nsc_str = self._get_attr(app_elem, "networkSecurityConfig")
            network_security_config = nsc_str is not None

        permissions = []
        for perm in self.root.findall("permission"):
            name = self._get_attr(perm, "name")
            if name:
                permissions.append(name)

        uses_permissions = []
        for perm in self.root.findall("uses-permission"):
            name = self._get_attr(perm, "name")
            if name:
                uses_permissions.append(name)

        return ManifestInfo(
            package_name=package,
            version_name=version_name,
            version_code=version_code,
            min_sdk=min_sdk,
            target_sdk=target_sdk,
            debuggable=debuggable,
            allow_backup=allow_backup,
            uses_cleartext_traffic=uses_cleartext_traffic,
            network_security_config=network_security_config,
            permissions=permissions,
            uses_permissions=uses_permissions,
        )

    def _parse_intent_filters(self, component: ET.Element) -> list[IntentFilter]:
        """Parse intent filters for a component."""
        filters = []
        for intent_filter in component.findall("intent-filter"):
            actions = []
            categories = []

            for action in intent_filter.findall("action"):
                name = self._get_attr(action, "name")
                if name:
                    actions.append(name)

            for category in intent_filter.findall("category"):
                name = self._get_attr(category, "name")
                if name:
                    categories.append(name)

            filters.append(IntentFilter(actions=actions, categories=categories))

        return filters

    def _parse_activities(self) -> list[ActivityInfo]:
        """Parse all activities."""
        if self.root is None:
            return []

        app_elem = self.root.find("application")
        if app_elem is None:
            return []

        activities = []
        for activity in app_elem.findall("activity"):
            name = self._get_attr(activity, "name")
            if not name:
                continue

            exported_str = self._get_attr(activity, "exported")
            exported = None
            if exported_str is not None:
                exported = exported_str == "true"

            permission = self._get_attr(activity, "permission")
            launch_mode = self._get_attr(activity, "launchMode")
            task_affinity = self._get_attr(activity, "taskAffinity")
            intent_filters = self._parse_intent_filters(activity)

            activities.append(
                ActivityInfo(
                    name=name,
                    exported=exported,
                    permission=permission,
                    launch_mode=launch_mode,
                    task_affinity=task_affinity,
                    intent_filters=intent_filters,
                )
            )

        return activities

    def _parse_services(self) -> list[ServiceInfo]:
        """Parse all services."""
        if self.root is None:
            return []

        app_elem = self.root.find("application")
        if app_elem is None:
            return []

        services = []
        for service in app_elem.findall("service"):
            name = self._get_attr(service, "name")
            if not name:
                continue

            exported_str = self._get_attr(service, "exported")
            exported = None
            if exported_str is not None:
                exported = exported_str == "true"

            permission = self._get_attr(service, "permission")
            intent_filters = self._parse_intent_filters(service)

            services.append(
                ServiceInfo(
                    name=name,
                    exported=exported,
                    permission=permission,
                    intent_filters=intent_filters,
                )
            )

        return services

    def _parse_receivers(self) -> list[ReceiverInfo]:
        """Parse all broadcast receivers."""
        if self.root is None:
            return []

        app_elem = self.root.find("application")
        if app_elem is None:
            return []

        receivers = []
        for receiver in app_elem.findall("receiver"):
            name = self._get_attr(receiver, "name")
            if not name:
                continue

            exported_str = self._get_attr(receiver, "exported")
            exported = None
            if exported_str is not None:
                exported = exported_str == "true"

            permission = self._get_attr(receiver, "permission")
            intent_filters = self._parse_intent_filters(receiver)

            receivers.append(
                ReceiverInfo(
                    name=name,
                    exported=exported,
                    permission=permission,
                    intent_filters=intent_filters,
                )
            )

        return receivers

    def _parse_providers(self) -> list[ProviderInfo]:
        """Parse all content providers."""
        if self.root is None:
            return []

        app_elem = self.root.find("application")
        if app_elem is None:
            return []

        providers = []
        for provider in app_elem.findall("provider"):
            name = self._get_attr(provider, "name")
            if not name:
                continue

            exported_str = self._get_attr(provider, "exported")
            exported = None
            if exported_str is not None:
                exported = exported_str == "true"

            permission = self._get_attr(provider, "permission")
            authorities = self._get_attr(provider, "authorities")
            read_permission = self._get_attr(provider, "readPermission")
            write_permission = self._get_attr(provider, "writePermission")

            grant_uri_str = self._get_attr(provider, "grantUriPermissions")
            grant_uri_permissions = grant_uri_str == "true"

            grant_uri_paths = []
            for grant in provider.findall("grant-uri-permission"):
                path = self._get_attr(grant, "path")
                path_prefix = self._get_attr(grant, "pathPrefix")
                path_pattern = self._get_attr(grant, "pathPattern")
                if path:
                    grant_uri_paths.append(path)
                elif path_prefix:
                    grant_uri_paths.append(f"{path_prefix}*")
                elif path_pattern:
                    grant_uri_paths.append(path_pattern)

            path_permissions = []
            for path_perm in provider.findall("path-permission"):
                path_permissions.append(
                    PathPermission(
                        path=self._get_attr(path_perm, "path"),
                        path_prefix=self._get_attr(path_perm, "pathPrefix"),
                        path_pattern=self._get_attr(path_perm, "pathPattern"),
                        read_permission=self._get_attr(path_perm, "readPermission"),
                        write_permission=self._get_attr(path_perm, "writePermission"),
                    )
                )

            intent_filters = self._parse_intent_filters(provider)

            providers.append(
                ProviderInfo(
                    name=name,
                    exported=exported,
                    permission=permission,
                    authorities=authorities,
                    read_permission=read_permission,
                    write_permission=write_permission,
                    grant_uri_permissions=grant_uri_permissions,
                    grant_uri_permission_paths=grant_uri_paths,
                    path_permissions=path_permissions,
                    intent_filters=intent_filters,
                )
            )

        return providers

    def _calculate_attack_surface(
        self,
        info: ManifestInfo,
        activities: list[ActivityInfo],
        services: list[ServiceInfo],
        receivers: list[ReceiverInfo],
        providers: list[ProviderInfo],
    ) -> AttackSurface:
        """Calculate the attack surface summary."""
        exported_activities = sum(1 for a in activities if a.effectively_exported)
        exported_services = sum(1 for s in services if s.effectively_exported)
        exported_receivers = sum(1 for r in receivers if r.effectively_exported)
        exported_providers = sum(1 for p in providers if p.effectively_exported)

        unprotected = sum(
            1
            for component in [*activities, *services, *receivers, *providers]
            if component.effectively_exported and component.permission is None
        )

        grant_uri_providers = sum(
            1
            for p in providers
            if p.grant_uri_permissions or p.grant_uri_permission_paths
        )

        return AttackSurface(
            total_activities=len(activities),
            total_services=len(services),
            total_receivers=len(receivers),
            total_providers=len(providers),
            exported_activities=exported_activities,
            exported_services=exported_services,
            exported_receivers=exported_receivers,
            exported_providers=exported_providers,
            unprotected_exported=unprotected,
            debuggable=info.debuggable,
            backup_enabled=info.allow_backup,
            cleartext_traffic=info.uses_cleartext_traffic,
            grant_uri_providers=grant_uri_providers,
        )
